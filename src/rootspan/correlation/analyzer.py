"""Explainable cohort-based first-divergence ranking."""

import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from hashlib import sha256
from math import log2
from statistics import median
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import JsonValue

from rootspan.domain import (
    CohortSummary,
    DivergenceCandidate,
    Evidence,
    IncidentBrief,
    IncidentState,
    RunMetrics,
    ScenarioFixture,
    SpanNode,
    TraceGraph,
)

Clock = Callable[[], datetime]


class CorrelationAnalyzer:
    """Rank local divergence candidates from healthy and failing traces."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def analyze(
        self, scenario: ScenarioFixture, *, incident_id: str | None = None
    ) -> IncidentBrief:
        started_at = self._clock()
        timer_started = perf_counter()
        resolved_id = incident_id or str(uuid4())
        cohort = self._cohort_summary(scenario)

        if (
            not scenario.healthy_traces
            or not scenario.failing_traces
            or cohort.coverage < 0.5
            or min(cohort.healthy_count, cohort.failing_count) < 2
        ):
            return self._insufficient_brief(
                scenario,
                incident_id=resolved_id,
                cohort=cohort,
                started_at=started_at,
                timer_started=timer_started,
            )

        trace_evidence, candidates = self._rank_candidates(scenario, cohort)
        evidence = (*trace_evidence, *scenario.external_evidence)
        completed_at = self._clock()

        if not candidates:
            return self._insufficient_brief(
                scenario,
                incident_id=resolved_id,
                cohort=cohort,
                started_at=started_at,
                timer_started=timer_started,
            )

        top = candidates[0]
        confidence = top.evidence_grade
        situation = (
            f"{top.operation} in {top.service} is the first shared local divergence across "
            f"{cohort.failing_count} failing traces. The result is a ranked hypothesis backed "
            "by cohort telemetry, not an automated root-cause declaration."
        )

        return IncidentBrief(
            incident_id=resolved_id,
            scenario=scenario.name,
            state=IncidentState.READY,
            started_at=started_at,
            completed_at=completed_at,
            target_operation=scenario.target_operation,
            situation=situation,
            confidence_label=confidence,
            cohort=cohort,
            ranked_candidates=tuple(candidates),
            evidence=evidence,
            blast_radius=scenario.blast_radius,
            timeline=scenario.timeline,
            next_queries=scenario.next_queries,
            metrics=RunMetrics(
                analyzed_trace_count=cohort.failing_count + cohort.healthy_count,
                candidate_count=len(candidates),
                evidence_count=len(evidence),
                analysis_duration_ms=round((perf_counter() - timer_started) * 1000, 3),
            ),
            sentinel_mesh=scenario.sentinel_mesh,
        )

    @staticmethod
    def _cohort_summary(scenario: ScenarioFixture) -> CohortSummary:
        usable = min(len(scenario.healthy_traces), len(scenario.failing_traces))
        coverage = min(usable / scenario.requested_per_cohort, 1.0)
        exclusions: list[str] = []
        if len(scenario.healthy_traces) < scenario.requested_per_cohort:
            exclusions.append("healthy cohort smaller than requested")
        if len(scenario.failing_traces) < scenario.requested_per_cohort:
            exclusions.append("failing cohort smaller than requested")
        return CohortSummary(
            failing_count=len(scenario.failing_traces),
            healthy_count=len(scenario.healthy_traces),
            requested_per_cohort=scenario.requested_per_cohort,
            coverage=round(coverage, 3),
            match_dimensions=scenario.match_dimensions,
            exclusions=tuple(exclusions),
        )

    def _rank_candidates(
        self,
        scenario: ScenarioFixture,
        cohort: CohortSummary,
    ) -> tuple[tuple[Evidence, ...], list[DivergenceCandidate]]:
        healthy = self._spans_by_operation(scenario.healthy_traces)
        failing = self._spans_by_operation(scenario.failing_traces)
        healthy_exclusive = self._exclusive_by_operation(scenario.healthy_traces)
        failing_exclusive = self._exclusive_by_operation(scenario.failing_traces)
        candidates: list[DivergenceCandidate] = []
        trace_evidence: list[Evidence] = []

        for operation_key in sorted(set(healthy) & set(failing)):
            healthy_spans = healthy[operation_key]
            failing_spans = failing[operation_key]
            healthy_durations = [span.duration_ms for span in healthy_spans]
            failing_durations = [span.duration_ms for span in failing_spans]
            baseline_median = median(healthy_durations)
            anomaly_threshold = max(baseline_median * 1.5, baseline_median + 20)
            failing_anomalies = sum(
                span.duration_ms > anomaly_threshold or span.error_type is not None
                for span in failing_spans
            )
            healthy_anomalies = sum(
                span.duration_ms > anomaly_threshold or span.error_type is not None
                for span in healthy_spans
            )
            failing_prevalence = failing_anomalies / len(failing_spans)
            healthy_prevalence = healthy_anomalies / len(healthy_spans)
            failing_local_errors = sum(span.error_type is not None for span in failing_spans)
            healthy_local_errors = sum(span.error_type is not None for span in healthy_spans)
            error_lift = max(
                (failing_local_errors / len(failing_spans))
                - (healthy_local_errors / len(healthy_spans)),
                0,
            )
            inclusive_ratio = median(failing_durations) / max(baseline_median, 0.001)
            healthy_self = healthy_exclusive[operation_key]
            failing_self = failing_exclusive[operation_key]
            exclusive_ratio = median(failing_self) / max(median(healthy_self), 0.001)
            inclusive_shift = max(median(failing_durations) - baseline_median, 0)
            exclusive_shift = max(median(failing_self) - median(healthy_self), 0)
            local_attribution = min(exclusive_shift / max(inclusive_shift, 0.001), 1.0)

            supporting = [
                item.id
                for item in scenario.external_evidence
                if item.operation_key == operation_key and item.supports
            ]
            contradicting = [
                item.id
                for item in scenario.external_evidence
                if item.operation_key == operation_key and not item.supports
            ]
            trace_evidence_id = f"trace-diff:{operation_key}"
            supporting.insert(0, trace_evidence_id)
            query_args: dict[str, JsonValue] = {
                "failingTraceIds": [trace.trace_id for trace in scenario.failing_traces],
                "healthyTraceIds": [trace.trace_id for trace in scenario.healthy_traces],
                "operationKey": operation_key,
            }
            response_payload = {
                "failingTraces": [
                    trace.model_dump(mode="json") for trace in scenario.failing_traces
                ],
                "healthyTraces": [
                    trace.model_dump(mode="json") for trace in scenario.healthy_traces
                ],
            }
            trace_evidence.append(
                Evidence(
                    id=trace_evidence_id,
                    signal="trace",
                    operation_key=operation_key,
                    supports=True,
                    observation=(
                        f"Failing median {median(failing_durations):.1f} ms versus healthy "
                        f"{baseline_median:.1f} ms; local/self ratio {exclusive_ratio:.1f}x."
                    ),
                    query_tool="rootspan.compare_trace_cohorts",
                    query_args=query_args,
                    web_url=scenario.failing_traces[0].web_url,
                    response_hash=sha256(
                        json.dumps(
                            response_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest(),
                    observed_at=self._clock(),
                )
            )

            raw_score = (
                0.22 * failing_prevalence
                + 0.18 * error_lift
                + 0.17 * self._ratio_score(inclusive_ratio)
                + 0.23 * self._ratio_score(exclusive_ratio)
                + 0.12 * local_attribution
                + 0.04 * min(len(supporting) - 1, 2)
                - 0.06 * len(contradicting)
            )
            score = min(max(raw_score * max(cohort.coverage, 0.5), 0), 1)
            service, operation = operation_key.split("|", maxsplit=1)
            candidates.append(
                DivergenceCandidate(
                    rank=1,
                    operation_key=operation_key,
                    service=service,
                    operation=operation,
                    failing_prevalence=round(failing_prevalence, 3),
                    healthy_prevalence=round(healthy_prevalence, 3),
                    error_lift=round(error_lift, 3),
                    inclusive_duration_ratio=round(inclusive_ratio, 2),
                    exclusive_duration_ratio=round(exclusive_ratio, 2),
                    local_attribution=round(local_attribution, 3),
                    score=round(score, 3),
                    evidence_grade=self._grade(score, cohort.coverage, len(supporting)),
                    supporting_evidence_ids=tuple(supporting),
                    contradicting_evidence_ids=tuple(contradicting),
                )
            )

        candidates.sort(key=lambda item: (-item.score, item.operation_key))
        ranked = [item.model_copy(update={"rank": rank}) for rank, item in enumerate(candidates, 1)]
        return tuple(trace_evidence), ranked

    def _insufficient_brief(
        self,
        scenario: ScenarioFixture,
        *,
        incident_id: str,
        cohort: CohortSummary,
        started_at: datetime,
        timer_started: float,
    ) -> IncidentBrief:
        completed_at = self._clock()
        return IncidentBrief(
            incident_id=incident_id,
            scenario=scenario.name,
            state=IncidentState.INSUFFICIENT_EVIDENCE,
            started_at=started_at,
            completed_at=completed_at,
            target_operation=scenario.target_operation,
            situation=(
                "RootSpan could not construct comparable healthy and failing cohorts, so it "
                "abstained instead of ranking a divergence."
            ),
            confidence_label="insufficient",
            cohort=cohort,
            ranked_candidates=(),
            evidence=scenario.external_evidence,
            blast_radius=(),
            timeline=scenario.timeline,
            next_queries=scenario.next_queries,
            metrics=RunMetrics(
                analyzed_trace_count=cohort.failing_count + cohort.healthy_count,
                candidate_count=0,
                evidence_count=len(scenario.external_evidence),
                analysis_duration_ms=round((perf_counter() - timer_started) * 1000, 3),
            ),
            sentinel_mesh=scenario.sentinel_mesh,
        )

    @staticmethod
    def _spans_by_operation(traces: Iterable[TraceGraph]) -> dict[str, list[SpanNode]]:
        result: dict[str, list[SpanNode]] = defaultdict(list)
        for trace in traces:
            for span in trace.spans:
                result[span.operation_key].append(span)
        return result

    @classmethod
    def _exclusive_by_operation(cls, traces: Iterable[TraceGraph]) -> dict[str, list[float]]:
        result: dict[str, list[float]] = defaultdict(list)
        for trace in traces:
            for span in trace.spans:
                result[span.operation_key].append(cls._exclusive_duration(span, trace.spans))
        return result

    @staticmethod
    def _exclusive_duration(span: SpanNode, spans: tuple[SpanNode, ...]) -> float:
        span_end = span.start_ms + span.duration_ms
        child_intervals = sorted(
            (
                max(child.start_ms, span.start_ms),
                min(child.start_ms + child.duration_ms, span_end),
            )
            for child in spans
            if child.parent_span_id == span.span_id
        )
        covered = 0.0
        current_start: float | None = None
        current_end: float | None = None
        for start, end in child_intervals:
            if end <= start:
                continue
            if current_start is None or current_end is None:
                current_start, current_end = start, end
            elif start <= current_end:
                current_end = max(current_end, end)
            else:
                covered += current_end - current_start
                current_start, current_end = start, end
        if current_start is not None and current_end is not None:
            covered += current_end - current_start
        return max(span.duration_ms - covered, 0.001)

    @staticmethod
    def _ratio_score(ratio: float) -> float:
        if ratio <= 1:
            return 0
        return min(log2(ratio) / 4, 1)

    @staticmethod
    def _grade(
        score: float,
        coverage: float,
        supporting_count: int,
    ) -> Literal["high", "medium", "low"]:
        if score >= 0.72 and coverage >= 0.8 and supporting_count >= 3:
            return "high"
        if score >= 0.45 and coverage >= 0.5:
            return "medium"
        return "low"
