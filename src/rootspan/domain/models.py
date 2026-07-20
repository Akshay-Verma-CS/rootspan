"""Validated domain models for incident correlation."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, computed_field, model_validator


class DomainModel(BaseModel):
    """Base model with strict input and immutable validated values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IncidentState(StrEnum):
    """Externally visible states of an incident investigation."""

    READY = "READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


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
