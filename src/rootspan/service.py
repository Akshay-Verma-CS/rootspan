"""Application service joining telemetry, correlation, and persistence."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from opentelemetry import trace

from rootspan.correlation import CorrelationAnalyzer
from rootspan.domain import (
    IncidentBrief,
    IncidentProgress,
    IncidentState,
    ScenarioFixture,
    TimeWindow,
)
from rootspan.fixtures.loader import load_scenario
from rootspan.live import LiveScenarioCollector
from rootspan.storage import IncidentRepository

ScenarioLoader = Callable[[str], ScenarioFixture]
Clock = Callable[[], datetime]


class LiveInvestigationError(RuntimeError):
    """A live investigation failed after its state was safely persisted."""


class IncidentService:
    """Run and retrieve deterministic incident investigations."""

    def __init__(
        self,
        repository: IncidentRepository,
        *,
        analyzer: CorrelationAnalyzer | None = None,
        scenario_loader: ScenarioLoader = load_scenario,
        live_collector: LiveScenarioCollector | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer or CorrelationAnalyzer()
        self._scenario_loader = scenario_loader
        self._live_collector = live_collector
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tracer = trace.get_tracer("rootspan.incidents")

    def replay(self, scenario_name: str) -> IncidentBrief:
        scenario = self._scenario_loader(scenario_name)
        brief = self._analyzer.analyze(scenario)
        self._repository.save(brief)
        return brief

    async def investigate_live(
        self,
        *,
        window: TimeWindow,
        cohort_size: int,
        target_operation: str = "gateway.checkout",
        alert_fingerprint: str | None = None,
    ) -> IncidentBrief:
        """Collect bounded SigNoz evidence and run the deterministic analyzer."""

        if self._live_collector is None:
            raise LiveInvestigationError("live SigNoz collection is not configured")
        if alert_fingerprint:
            existing = self._repository.get_by_fingerprint(alert_fingerprint)
            if existing is not None:
                return existing

        incident_id = str(uuid4())
        self._repository.start_run(
            incident_id=incident_id,
            alert_fingerprint=alert_fingerprint,
            target_operation=target_operation,
            occurred_at=self._clock(),
        )
        try:
            self._transition(
                incident_id,
                IncidentState.COLLECTING,
                "The bounded SigNoz query window was validated; evidence collection is starting.",
            )
            with self._tracer.start_as_current_span("incident.window.build") as span:
                span.set_attribute("rootspan.window.start", window.start.isoformat())
                span.set_attribute("rootspan.window.end", window.end.isoformat())
                span.set_attribute("rootspan.cohort.requested", cohort_size)

            self._transition(
                incident_id,
                IncidentState.COHORTING,
                "Selecting comparable healthy and failing trace cohorts.",
            )
            with self._tracer.start_as_current_span("cohort.select"):
                scenario = await self._live_collector.collect(
                    incident_id=incident_id,
                    window=window,
                    cohort_size=cohort_size,
                    target_operation=target_operation,
                )

            self._transition(
                incident_id,
                IncidentState.ALIGNING,
                "Canonical operations are aligned across the selected trace cohorts.",
            )
            with self._tracer.start_as_current_span("trace.align") as span:
                span.set_attribute("rootspan.cohort.healthy", len(scenario.healthy_traces))
                span.set_attribute("rootspan.cohort.failing", len(scenario.failing_traces))

            self._transition(
                incident_id,
                IncidentState.CORROBORATING,
                "Supporting, contradicting, and blast-radius evidence is being compiled.",
            )
            with self._tracer.start_as_current_span("blast_radius.calculate") as span:
                span.set_attribute("rootspan.blast_radius.slices", len(scenario.blast_radius))
                span.set_attribute(
                    "rootspan.external_evidence.count", len(scenario.external_evidence)
                )

            self._transition(
                incident_id,
                IncidentState.COMPILING,
                "The deterministic divergence ranking and responder brief are being compiled.",
            )
            with self._tracer.start_as_current_span("divergence.rank"):
                brief = self._analyzer.analyze(scenario, incident_id=incident_id)
            with self._tracer.start_as_current_span("brief.compile"):
                self._repository.save(brief)

            self._transition(
                incident_id,
                brief.state,
                (
                    "A ranked evidence-bound brief is ready for human review."
                    if brief.state is IncidentState.READY
                    else "Evidence was insufficient or incomparable; RootSpan abstained."
                ),
            )
            return brief
        except Exception as error:
            self._repository.transition(
                incident_id,
                IncidentState.FAILED,
                occurred_at=self._clock(),
                detail="The investigation stopped safely without changing monitored systems.",
                error=type(error).__name__,
            )
            if isinstance(error, LiveInvestigationError):
                raise
            raise LiveInvestigationError("live telemetry investigation failed") from error

    def _transition(self, incident_id: str, state: IncidentState, detail: str) -> None:
        self._repository.transition(
            incident_id,
            state,
            occurred_at=self._clock(),
            detail=detail,
        )

    def get(self, incident_id: str) -> IncidentBrief | None:
        return self._repository.get(incident_id)

    def list(self, *, limit: int = 20) -> tuple[IncidentBrief, ...]:
        return self._repository.list(limit=limit)

    def progress(self, incident_id: str) -> tuple[IncidentProgress, ...]:
        return self._repository.progress(incident_id)

    def close_alert(self, alert_fingerprint: str) -> str | None:
        """Persist a resolved alert without performing any external action."""

        brief = self._repository.get_by_fingerprint(alert_fingerprint)
        if brief is None:
            return None
        self._transition(
            brief.incident_id,
            IncidentState.CLOSED,
            "The source alert resolved; the immutable evidence packet remains available.",
        )
        self._repository.save(brief.model_copy(update={"state": IncidentState.CLOSED}))
        return brief.incident_id
