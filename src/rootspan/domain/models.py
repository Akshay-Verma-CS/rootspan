"""Validated domain models for incident correlation."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, computed_field, model_validator


class DomainModel(BaseModel):
    """Base model with strict input and immutable validated values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IncidentState(StrEnum):
    """Externally visible states of an incident investigation."""

    RECEIVED = "RECEIVED"
    COLLECTING = "COLLECTING"
    COHORTING = "COHORTING"
    ALIGNING = "ALIGNING"
    CORROBORATING = "CORROBORATING"
    COMPILING = "COMPILING"
    READY = "READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class SentinelRole(StrEnum):
    """The coordination role held by a sentinel for one incident."""

    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"


class SentinelOutcome(StrEnum):
    """A sentinel's bounded observation outcome."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class TimeWindow(DomainModel):
    """A bounded, timezone-aware telemetry query window."""

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> "TimeWindow":
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("telemetry query windows must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("telemetry query window end must be after start")
        if self.end - self.start > timedelta(hours=24):
            raise ValueError("telemetry query windows must not exceed 24 hours")
        return self


class TraceSearch(DomainModel):
    """Bounded trace cohort search independent of the backing gateway."""

    operation: str
    window: TimeWindow
    error: bool
    limit: int = Field(ge=1, le=100)


class TraceRef(DomainModel):
    """A lightweight trace reference returned during cohort discovery."""

    trace_id: str
    observed_at: datetime
    web_url: str


class LogQuery(DomainModel):
    """Bounded stable-text log search."""

    search_text: str
    window: TimeWindow
    service: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class LogRecord(DomainModel):
    """Compact log observation used for cross-signal corroboration."""

    observed_at: datetime
    body: str
    service: str | None = None
    trace_id: str | None = None
    web_url: str


class AggregateQuery(DomainModel):
    """One explainable telemetry aggregation."""

    signal: Literal["traces", "logs"]
    aggregation: Literal["count", "p50", "p95", "p99"]
    window: TimeWindow
    operation: str | None = None
    aggregate_on: str | None = None
    group_by: tuple[str, ...] = ()
    error: bool | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class AggregateRow(DomainModel):
    """One group and value returned from a telemetry aggregation."""

    dimensions: dict[str, str]
    value: float


class AggregateResult(DomainModel):
    """Gateway-neutral aggregate result with a raw-data deep link."""

    rows: tuple[AggregateRow, ...]
    web_url: str


class MetricQuery(DomainModel):
    """Bounded metric query independent of SigNoz transport details."""

    metric_name: str
    window: TimeWindow
    group_by: tuple[str, ...] = ()


class MetricPoint(DomainModel):
    """One timestamped metric value."""

    observed_at: datetime
    value: float
    dimensions: dict[str, str] = Field(default_factory=dict)


class MetricSeries(DomainModel):
    """A compact metric result and its SigNoz provenance link."""

    points: tuple[MetricPoint, ...]
    web_url: str


class IncidentProgress(DomainModel):
    """Persisted incident state transition exposed to the console."""

    incident_id: str
    state: IncidentState
    occurred_at: datetime
    detail: str


class SpanNode(DomainModel):
    """One canonicalized span used by the correlation engine."""

    span_id: str
    parent_span_id: str | None = None
    service: str
    operation: str
    start_ms: float = Field(ge=0)
    duration_ms: float = Field(gt=0)
    status: Literal["ok", "error"] = "ok"
    error_type: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

    @property
    def operation_key(self) -> str:
        return f"{self.service}|{self.operation}"


class TraceGraph(DomainModel):
    """A bounded complete trace and its cohort dimensions."""

    trace_id: str
    root_operation: str
    dimensions: dict[str, str]
    spans: tuple[SpanNode, ...]
    web_url: str

    @model_validator(mode="after")
    def validate_tree(self) -> "TraceGraph":
        span_ids = {span.span_id for span in self.spans}
        if len(span_ids) != len(self.spans):
            msg = f"trace {self.trace_id} contains duplicate span IDs"
            raise ValueError(msg)
        missing_parents = {
            span.parent_span_id
            for span in self.spans
            if span.parent_span_id is not None and span.parent_span_id not in span_ids
        }
        if missing_parents:
            msg = f"trace {self.trace_id} references missing parents: {sorted(missing_parents)}"
            raise ValueError(msg)
        return self


class Evidence(DomainModel):
    """An immutable observation and the query provenance behind it."""

    id: str
    signal: Literal["trace", "log", "metric", "change", "topology"]
    operation_key: str
    supports: bool
    observation: str
    query_tool: str
    query_args: dict[str, JsonValue]
    web_url: str
    response_hash: str | None = None
    observed_at: datetime | None = None


class DivergenceCandidate(DomainModel):
    """One explainable first-divergence hypothesis."""

    rank: int = Field(ge=1)
    operation_key: str
    service: str
    operation: str
    failing_prevalence: float = Field(ge=0, le=1)
    healthy_prevalence: float = Field(ge=0, le=1)
    error_lift: float = Field(ge=0, le=1)
    inclusive_duration_ratio: float = Field(ge=0)
    exclusive_duration_ratio: float = Field(ge=0)
    local_attribution: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    evidence_grade: Literal["high", "medium", "low"]
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]


class CohortSummary(DomainModel):
    """Coverage and matching details for the compared trace cohorts."""

    failing_count: int = Field(ge=0)
    healthy_count: int = Field(ge=0)
    requested_per_cohort: int = Field(gt=0)
    coverage: float = Field(ge=0, le=1)
    match_dimensions: tuple[str, ...]
    exclusions: tuple[str, ...] = ()


class BlastRadiusSlice(DomainModel):
    """Affected and total request counts for one bounded dimension."""

    dimension: str
    value: str
    affected: int = Field(ge=0)
    total: int = Field(gt=0)

    @computed_field
    @property
    def percentage(self) -> float:
        return round((self.affected / self.total) * 100, 1)


class TimelineEvent(DomainModel):
    """A timestamped event relevant to the incident."""

    occurred_at: datetime
    kind: Literal["change", "alert", "observation"]
    title: str
    detail: str
    evidence_id: str | None = None


class RunMetrics(DomainModel):
    """Measured properties of a deterministic investigation run."""

    analyzed_trace_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    analysis_duration_ms: float = Field(ge=0)


class SentinelLeaderLease(DomainModel):
    """Persisted ownership of sentinel coordination for one incident."""

    incident_id: str
    leader_id: str
    generation: int = Field(ge=1)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_expiry(self) -> "SentinelLeaderLease":
        if self.expires_at.tzinfo is None:
            raise ValueError("sentinel lease expiry must be timezone-aware")
        return self


class SentinelFinding(DomainModel):
    """One system-scoped agent observation with evidence references."""

    sentinel_id: str
    system: str
    role: SentinelRole
    outcome: SentinelOutcome
    summary: str
    evidence_ids: tuple[str, ...] = ()
    started_at: datetime
    completed_at: datetime
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> "SentinelFinding":
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("sentinel finding timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("sentinel finding completion cannot precede its start")
        if self.outcome is SentinelOutcome.FAILED and self.error_code is None:
            raise ValueError("failed sentinel findings require an error code")
        if self.outcome is not SentinelOutcome.FAILED and self.error_code is not None:
            raise ValueError("only failed sentinel findings may include an error code")
        return self


class SentinelMeshRun(DomainModel):
    """Auditable leader/follower coordination for one investigation."""

    leader_id: str
    previous_leader_ids: tuple[str, ...] = ()
    follower_ids: tuple[str, ...]
    status: SentinelOutcome
    lease_generation: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime
    findings: tuple[SentinelFinding, ...]

    @model_validator(mode="after")
    def validate_mesh(self) -> "SentinelMeshRun":
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("sentinel mesh timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("sentinel mesh completion cannot precede its start")
        finding_ids = [item.sentinel_id for item in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("sentinel findings must have unique sentinel IDs")
        if self.leader_id not in finding_ids:
            raise ValueError("sentinel mesh leader must have a finding")
        expected_followers = tuple(item for item in finding_ids if item != self.leader_id)
        if self.follower_ids != expected_followers:
            raise ValueError("sentinel follower order must match finding order")
        for finding in self.findings:
            expected_role = (
                SentinelRole.LEADER
                if finding.sentinel_id == self.leader_id
                else SentinelRole.FOLLOWER
            )
            if finding.role is not expected_role:
                raise ValueError("sentinel finding role does not match elected leadership")
        return self


class IncidentBrief(DomainModel):
    """Decision-ready output returned to the responder console."""

    incident_id: str
    scenario: str
    state: IncidentState
    started_at: datetime
    completed_at: datetime
    target_operation: str
    situation: str
    confidence_label: Literal["high", "medium", "low", "insufficient"]
    cohort: CohortSummary
    ranked_candidates: tuple[DivergenceCandidate, ...]
    evidence: tuple[Evidence, ...]
    blast_radius: tuple[BlastRadiusSlice, ...]
    timeline: tuple[TimelineEvent, ...]
    next_queries: tuple[str, ...]
    metrics: RunMetrics
    sentinel_mesh: SentinelMeshRun | None = None


class ScenarioFixture(DomainModel):
    """Versioned replay input for one deterministic incident."""

    schema_version: Literal["1.0"]
    name: str
    target_operation: str
    requested_per_cohort: int = Field(gt=0)
    match_dimensions: tuple[str, ...]
    healthy_traces: tuple[TraceGraph, ...]
    failing_traces: tuple[TraceGraph, ...]
    external_evidence: tuple[Evidence, ...]
    blast_radius: tuple[BlastRadiusSlice, ...]
    timeline: tuple[TimelineEvent, ...]
    next_queries: tuple[str, ...]
    sentinel_mesh: SentinelMeshRun | None = None
