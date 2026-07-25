"""Typed read-only telemetry gateway implementations."""

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol, cast
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import JsonValue, TypeAdapter

from rootspan.domain import (
    AggregateQuery,
    AggregateResult,
    AggregateRow,
    LogQuery,
    LogRecord,
    MetricPoint,
    MetricQuery,
    MetricSeries,
    ScenarioFixture,
    SpanNode,
    TimeWindow,
    TraceGraph,
    TraceRef,
    TraceSearch,
)

JsonObject = dict[str, JsonValue]
JSON_OBJECT = TypeAdapter(JsonObject)
FIELD_NAME = re.compile(r"^[A-Za-z0-9_.]+$")
CANONICAL_OPERATIONS = frozenset(
    {"gateway.checkout", "checkout.place_order", "inventory.reserve", "inventory.db.select"}
)


class TelemetryGatewayError(RuntimeError):
    """A bounded read-only telemetry request failed."""


class TelemetryGateway(Protocol):
    """Domain boundary implemented by fixture and live SigNoz adapters."""

    async def search_trace_ids(self, query: TraceSearch) -> tuple[TraceRef, ...]: ...

    async def get_trace(self, trace_id: str, window: TimeWindow) -> TraceGraph: ...

    async def search_logs(self, query: LogQuery) -> tuple[LogRecord, ...]: ...

    async def aggregate(self, query: AggregateQuery) -> AggregateResult: ...

    async def query_metrics(self, query: MetricQuery) -> MetricSeries: ...


class ToolCaller(Protocol):
    """Small seam around MCP transport for contract tests."""

    async def call(self, name: str, arguments: JsonObject) -> JsonObject: ...


class McpToolCaller:
    """Open a bounded Streamable HTTP session for one MCP tool call."""

    def __init__(self, endpoint: str, *, api_key: str = "", timeout_seconds: float = 30) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def call(self, name: str, arguments: JsonObject) -> JsonObject:
        headers = {"SIGNOZ-API-KEY": self._api_key} if self._api_key else {}
        timeout = httpx.Timeout(self._timeout, connect=min(self._timeout, 5), read=self._timeout)
        try:
            async with (
                httpx.AsyncClient(headers=headers, timeout=timeout) as client,
                streamable_http_client(
                    self._endpoint,
                    http_client=client,
                ) as (read_stream, write_stream, _),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                result = await session.call_tool(name, cast(dict[str, object], arguments))
        except Exception as error:
            raise TelemetryGatewayError(f"MCP tool {name} failed: {error}") from error

        if result.isError:
            message = _result_text(result.model_dump(mode="json"))
            raise TelemetryGatewayError(f"MCP tool {name} returned an error: {message}")

        dumped = JSON_OBJECT.validate_python(result.model_dump(mode="json"))
        structured = dumped.get("structuredContent")
        if isinstance(structured, dict):
            return JSON_OBJECT.validate_python(structured)
        raw_content = dumped.get("content")
        content = cast(list[JsonValue], raw_content) if isinstance(raw_content, list) else []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.lstrip().startswith("{"):
                continue
            try:
                return JSON_OBJECT.validate_python(json.loads(text))
            except (json.JSONDecodeError, ValueError):
                continue
        raise TelemetryGatewayError(f"MCP tool {name} returned no structured JSON result")


class McpSigNozGateway:
    """Primary live gateway using the read-only SigNoz MCP tools."""

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str = "",
        public_url: str = "http://localhost:8080",
        caller: ToolCaller | None = None,
    ) -> None:
        self._caller = caller or McpToolCaller(endpoint, api_key=api_key)
        self._public_url = public_url.rstrip("/")

    async def search_trace_ids(self, query: TraceSearch) -> tuple[TraceRef, ...]:
        arguments: JsonObject = {
            "operation": query.operation,
            "error": query.error,
            "start": _unix_ms(query.window.start),
            "end": _unix_ms(query.window.end),
            "limit": query.limit,
            "offset": 0,
            "searchContext": "Build comparable RootSpan healthy and failing trace cohorts",
        }
        payload = await self._caller.call("signoz_search_traces", arguments)
        refs: list[TraceRef] = []
        seen: set[str] = set()
        for row in _raw_rows(payload):
            trace_id = _string(row.get("trace_id"))
            if not trace_id or trace_id in seen:
                continue
            timestamp = _datetime(row.get("timestamp"))
            web_url = self._public_link(_string(row.get("webUrl")), f"/trace/{trace_id}")
            refs.append(TraceRef(trace_id=trace_id, observed_at=timestamp, web_url=web_url))
            seen.add(trace_id)
            if len(refs) == query.limit:
                break
        return tuple(refs)

    async def get_trace(self, trace_id: str, window: TimeWindow) -> TraceGraph:
        arguments: JsonObject = {
            "traceId": trace_id,
            "start": _unix_ms(window.start),
            "end": _unix_ms(window.end),
            "includeSpans": True,
            "searchContext": "Retrieve a bounded complete trace for RootSpan alignment",
        }
        payload = await self._caller.call("signoz_get_trace_details", arguments)
        rows = _raw_rows(payload)
        if not rows:
            raise TelemetryGatewayError(f"SigNoz returned no spans for trace {trace_id}")
        return self._trace_graph(trace_id, rows, _payload_web_url(payload))

    async def search_logs(self, query: LogQuery) -> tuple[LogRecord, ...]:
        arguments: JsonObject = {
            "searchText": query.search_text,
            "start": _unix_ms(query.window.start),
            "end": _unix_ms(query.window.end),
            "limit": query.limit,
            "offset": 0,
            "searchContext": "Corroborate a RootSpan divergence with trace-linked logs",
        }
        if query.service:
            arguments["service"] = query.service
        payload = await self._caller.call("signoz_search_logs", arguments)
        records: list[LogRecord] = []
        for row in _raw_rows(payload):
            body = _string(row.get("body") or row.get("message"))
            if not body:
                continue
            trace_id = _string(row.get("trace_id")) or None
            records.append(
                LogRecord(
                    observed_at=_datetime(row.get("timestamp")),
                    body=body,
                    service=_string(row.get("service.name")) or None,
                    trace_id=trace_id,
                    web_url=self._public_link(
                        _string(row.get("webUrl")),
                        "/logs-explorer",
                    ),
                )
            )
        return tuple(records)

    async def aggregate(self, query: AggregateQuery) -> AggregateResult:
        if query.signal != "traces":
            raise TelemetryGatewayError("the live aggregate adapter currently supports traces")
        aggregation = _aggregation_expression(query)
        filters: list[str] = []
        if query.operation:
            filters.append(f"name = '{_filter_literal(query.operation)}'")
        if query.error is not None:
            filters.append(f"has_error = {str(query.error).lower()}")
        group_by = [_field_spec(name) for name in query.group_by]
        spec = JSON_OBJECT.validate_python(
            {
                "name": "A",
                "signal": "traces",
                "disabled": False,
                "limit": query.limit,
                "offset": 0,
                "having": {"expression": ""},
                "filter": {"expression": " AND ".join(filters)},
                "aggregations": [{"expression": aggregation}],
                "groupBy": group_by,
                "order": [{"key": {"name": aggregation}, "direction": "desc"}],
            }
        )
        builder = JSON_OBJECT.validate_python(
            {
                "schemaVersion": "v1",
                "start": _unix_ms(query.window.start),
                "end": _unix_ms(query.window.end),
                "requestType": "scalar",
                "compositeQuery": {"queries": [{"type": "builder_query", "spec": spec}]},
                "formatOptions": {"formatTableResultForUI": False, "fillGaps": False},
                "variables": {},
            }
        )
        payload = await self._caller.call(
            "signoz_execute_builder_query",
            {
                "query": builder,
                "searchContext": "Compute bounded RootSpan corroboration and blast radius",
            },
        )
        rows = _aggregate_rows(payload)
        return AggregateResult(rows=rows, web_url=f"{self._public_url}/traces-explorer")

    async def query_metrics(self, query: MetricQuery) -> MetricSeries:
        arguments: JsonObject = {
            "metricName": query.metric_name,
            "start": _unix_ms(query.window.start),
            "end": _unix_ms(query.window.end),
            "requestType": "time_series",
            "groupBy": list(query.group_by),
            "searchContext": "Corroborate RootSpan trace evidence with a bounded metric query",
        }
        payload = await self._caller.call("signoz_query_metrics", arguments)
        points: list[MetricPoint] = []
        for row in _raw_rows(payload):
            value = row.get("value")
            if isinstance(value, int | float):
                points.append(
                    MetricPoint(observed_at=_datetime(row.get("timestamp")), value=float(value))
                )
        return MetricSeries(points=tuple(points), web_url=f"{self._public_url}/metrics-explorer")

    def _trace_graph(
        self,
        trace_id: str,
        rows: tuple[JsonObject, ...],
        raw_web_url: str,
    ) -> TraceGraph:
        by_id = {_string(row.get("span_id")): row for row in rows if _string(row.get("span_id"))}
        retained = {
            span_id: row
            for span_id, row in by_id.items()
            if _string(row.get("name")) in CANONICAL_OPERATIONS
        }
        if not retained:
            raise TelemetryGatewayError(
                f"trace {trace_id} contains no canonical RootSpan operations"
            )
        starts = [_datetime(row.get("timestamp")) for row in retained.values()]
        trace_start = min(starts)
        spans: list[SpanNode] = []
        for span_id, row in retained.items():
            operation = _string(row.get("name"))
            service = _string(row.get("service.name"))
            parent_id = _nearest_retained_parent(row, by_id, retained)
            has_error = bool(row.get("has_error"))
            error_type = (
                "InventoryTimeout" if has_error and operation == "inventory.reserve" else None
            )
            timestamp = _datetime(row.get("timestamp"))
            duration_nano = row.get("duration_nano")
            if not isinstance(duration_nano, int | float) or duration_nano <= 0:
                continue
            attributes = {
                key: value
                for key in ("http.route", "response_status_code", "kind_string")
                if (value := _string(row.get(key)))
            }
            spans.append(
                SpanNode(
                    span_id=span_id,
                    parent_span_id=parent_id,
                    service=service,
                    operation=operation,
                    start_ms=(timestamp - trace_start).total_seconds() * 1000,
                    duration_ms=float(duration_nano) / 1_000_000,
                    status="error" if has_error else "ok",
                    error_type=error_type,
                    attributes=attributes,
                )
            )
        spans.sort(key=lambda item: (item.start_ms, item.span_id))
        return TraceGraph(
            trace_id=trace_id,
            root_operation="POST /checkout",
            dimensions={},
            spans=tuple(spans),
            web_url=self._public_link(raw_web_url, f"/trace/{trace_id}"),
        )

    def _public_link(self, raw_url: str, fallback_path: str) -> str:
        if raw_url:
            parsed = urlsplit(raw_url)
            path = parsed.path or fallback_path
            suffix = f"?{parsed.query}" if parsed.query else ""
            return f"{self._public_url}{path}{suffix}"
        return f"{self._public_url}{fallback_path}"


class FixtureTelemetryGateway:
    """Replay adapter exposing a fixture through the same domain boundary."""

    def __init__(self, scenario: ScenarioFixture) -> None:
        self._scenario = scenario
        self._traces = {
            trace.trace_id: trace for trace in (*scenario.healthy_traces, *scenario.failing_traces)
        }

    async def search_trace_ids(self, query: TraceSearch) -> tuple[TraceRef, ...]:
        traces = self._scenario.failing_traces if query.error else self._scenario.healthy_traces
        return tuple(
            TraceRef(
                trace_id=trace.trace_id,
                observed_at=query.window.end,
                web_url=trace.web_url,
            )
            for trace in traces[: query.limit]
        )

    async def get_trace(self, trace_id: str, window: TimeWindow) -> TraceGraph:
        del window
        try:
            return self._traces[trace_id]
        except KeyError as error:
            raise TelemetryGatewayError(f"unknown fixture trace: {trace_id}") from error

    async def search_logs(self, query: LogQuery) -> tuple[LogRecord, ...]:
        del query
        return ()

    async def aggregate(self, query: AggregateQuery) -> AggregateResult:
        rows = tuple(
            AggregateRow(dimensions={item.dimension: item.value}, value=float(item.affected))
            for item in self._scenario.blast_radius
            if not query.group_by or item.dimension in query.group_by
        )
        return AggregateResult(rows=rows, web_url="fixture://aggregate")

    async def query_metrics(self, query: MetricQuery) -> MetricSeries:
        del query
        return MetricSeries(points=(), web_url="fixture://metrics")


def response_hash(payload: object) -> str:
    """Return a stable provenance hash for compact gateway results."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


def _result_text(result: Mapping[str, object]) -> str:
    content = result.get("content")
    if isinstance(content, list):
        for item in cast(list[object], content):
            if isinstance(item, dict):
                item_map = cast(dict[str, object], item)
                text = item_map.get("text")
                if isinstance(text, str):
                    return text[:500]
    return "unknown MCP error"


def _raw_rows(payload: Mapping[str, JsonValue]) -> tuple[JsonObject, ...]:
    results = _query_results(payload)
    rows: list[JsonObject] = []
    for result in results:
        raw_rows = result.get("rows")
        if not isinstance(raw_rows, list):
            continue
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            data = raw_row.get("data")
            if isinstance(data, dict):
                rows.append(JSON_OBJECT.validate_python(data))
    return tuple(rows)


def _aggregate_rows(payload: Mapping[str, JsonValue]) -> tuple[AggregateRow, ...]:
    rows: list[AggregateRow] = []
    for result in _query_results(payload):
        columns = result.get("columns")
        data = result.get("data")
        if not isinstance(columns, list) or not isinstance(data, list):
            continue
        names = [str(item.get("name", "")) if isinstance(item, dict) else "" for item in columns]
        kinds = [
            str(item.get("columnType", "")) if isinstance(item, dict) else "" for item in columns
        ]
        for values in data:
            if not isinstance(values, list) or len(values) != len(names):
                continue
            dimensions = {
                names[index]: str(value)
                for index, value in enumerate(values)
                if kinds[index] == "group" and value is not None
            }
            numeric = next(
                (
                    float(value)
                    for index, value in enumerate(values)
                    if kinds[index] == "aggregation" and isinstance(value, int | float)
                ),
                None,
            )
            if numeric is not None:
                rows.append(AggregateRow(dimensions=dimensions, value=numeric))
    return tuple(rows)


def _query_results(payload: Mapping[str, JsonValue]) -> tuple[JsonObject, ...]:
    current: object = payload
    for _ in range(5):
        if not isinstance(current, dict):
            break
        current_map = cast(dict[str, object], current)
        raw_results = current_map.get("results")
        if isinstance(raw_results, list):
            return tuple(
                JSON_OBJECT.validate_python(item)
                for item in cast(list[object], raw_results)
                if isinstance(item, dict)
            )
        nested = current_map.get("data")
        if isinstance(nested, dict):
            current = cast(dict[str, object], nested)
            continue
        break
    return ()


def _payload_web_url(payload: Mapping[str, JsonValue]) -> str:
    current: object = payload
    for _ in range(5):
        if isinstance(current, dict):
            value = current.get("webUrl")
            if isinstance(value, str):
                return value
            nested = current.get("data")
            if isinstance(nested, dict):
                current = nested
                continue
        break
    return ""


def _nearest_retained_parent(
    row: Mapping[str, JsonValue],
    by_id: Mapping[str, JsonObject],
    retained: Mapping[str, JsonObject],
) -> str | None:
    parent_id = _string(row.get("parent_span_id"))
    seen: set[str] = set()
    while parent_id and parent_id not in retained and parent_id not in seen:
        seen.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None:
            return None
        parent_id = _string(parent.get("parent_span_id"))
    return parent_id or None


def _field_spec(name: str) -> JsonObject:
    if not FIELD_NAME.fullmatch(name):
        raise TelemetryGatewayError(f"invalid aggregate field name: {name}")
    if name == "service.name":
        context = "resource"
    elif name in {"name", "has_error", "duration_nano", "status_code"}:
        context = "span"
    else:
        context = "tag"
    return {
        "name": name,
        "fieldDataType": "string",
        "signal": "traces",
        "fieldContext": context,
    }


def _aggregation_expression(query: AggregateQuery) -> str:
    if query.aggregation == "count":
        return "count()"
    field = query.aggregate_on or "duration_nano"
    if not FIELD_NAME.fullmatch(field):
        raise TelemetryGatewayError(f"invalid aggregate field name: {field}")
    return f"{query.aggregation}({field})"


def _filter_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _unix_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _datetime(value: object) -> datetime:
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timestamp is not timezone-aware")
            return parsed.astimezone(UTC)
        if isinstance(value, int | float):
            divisor = 1_000_000_000 if value > 10**15 else 1000
            return datetime.fromtimestamp(float(value) / divisor, UTC)
    except (OSError, OverflowError, ValueError) as error:
        raise TelemetryGatewayError("SigNoz returned an invalid timestamp") from error
    raise TelemetryGatewayError("SigNoz returned no timestamp")


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""
