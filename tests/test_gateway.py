"""Contract tests for the read-only SigNoz MCP boundary."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import JsonValue

from rootspan.domain import TimeWindow, TraceSearch
from rootspan.gateway import JsonObject, McpSigNozGateway


class RecordedCaller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, JsonObject]] = []

    async def call(self, name: str, arguments: JsonObject) -> JsonObject:
        self.calls.append((name, arguments))
        if name == "signoz_search_traces":
            return _payload(
                [
                    {
                        "trace_id": "trace-live-1",
                        "timestamp": "2026-07-25T08:00:00Z",
                        "webUrl": "http://signoz:8080/trace/trace-live-1",
                    }
                ]
            )
        if name == "signoz_get_trace_details":
            return {
                "data": {
                    "webUrl": "http://signoz:8080/trace/trace-live-1",
                    "data": {
                        "results": [
                            {
                                "rows": [
                                    {"data": row}
                                    for row in (
                                        _span("a", "", "gateway", "gateway.checkout", 0, 500),
                                        _span("auto", "a", "gateway", "POST /checkout", 1, 490),
                                        _span(
                                            "b",
                                            "auto",
                                            "checkout",
                                            "checkout.place_order",
                                            2,
                                            450,
                                        ),
                                        _span(
                                            "c",
                                            "b",
                                            "inventory",
                                            "inventory.reserve",
                                            3,
                                            400,
                                            has_error=True,
                                        ),
                                        _span(
                                            "d",
                                            "c",
                                            "inventory",
                                            "inventory.db.select",
                                            4,
                                            20,
                                        ),
                                    )
                                ]
                            }
                        ]
                    },
                }
            }
        raise AssertionError(f"unexpected tool call: {name}")


def _payload(rows: list[dict[str, JsonValue]]) -> JsonObject:
    return cast(
        JsonObject,
        {"data": {"data": {"results": [{"rows": [{"data": row} for row in rows]}]}}},
    )


def _span(
    span_id: str,
    parent_span_id: str,
    service: str,
    name: str,
    offset_ms: int,
    duration_ms: int,
    *,
    has_error: bool = False,
) -> dict[str, JsonValue]:
    observed = datetime(2026, 7, 25, 8, tzinfo=UTC) + timedelta(milliseconds=offset_ms)
    return {
        "trace_id": "trace-live-1",
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "service.name": service,
        "name": name,
        "timestamp": observed.isoformat(),
        "duration_nano": duration_ms * 1_000_000,
        "has_error": has_error,
    }


@pytest.mark.anyio
async def test_mcp_gateway_returns_domain_types_and_reparents_canonical_spans() -> None:
    caller = RecordedCaller()
    gateway = McpSigNozGateway(
        "http://mcp.invalid/mcp",
        public_url="http://localhost:8080",
        caller=caller,
    )
    window = TimeWindow(
        start=datetime(2026, 7, 25, 7, 55, tzinfo=UTC),
        end=datetime(2026, 7, 25, 8, 5, tzinfo=UTC),
    )

    refs = await gateway.search_trace_ids(
        TraceSearch(operation="gateway.checkout", error=True, limit=10, window=window)
    )
    trace = await gateway.get_trace(refs[0].trace_id, window)

    assert refs[0].web_url == "http://localhost:8080/trace/trace-live-1"
    assert [span.operation for span in trace.spans] == [
        "gateway.checkout",
        "checkout.place_order",
        "inventory.reserve",
        "inventory.db.select",
    ]
    assert trace.spans[1].parent_span_id == "a"
    assert trace.spans[2].error_type == "InventoryTimeout"
    assert [name for name, _ in caller.calls] == [
        "signoz_search_traces",
        "signoz_get_trace_details",
    ]
