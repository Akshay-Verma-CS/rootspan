"""Application service joining fixtures, correlation, and persistence."""

from collections.abc import Callable

from rootspan.correlation import CorrelationAnalyzer
from rootspan.domain import IncidentBrief, ScenarioFixture
from rootspan.fixtures.loader import load_scenario
from rootspan.storage import IncidentRepository

ScenarioLoader = Callable[[str], ScenarioFixture]


class IncidentService:
    """Run and retrieve deterministic incident investigations."""

    def __init__(
        self,
        repository: IncidentRepository,
        *,
        analyzer: CorrelationAnalyzer | None = None,
        scenario_loader: ScenarioLoader = load_scenario,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer or CorrelationAnalyzer()
        self._scenario_loader = scenario_loader

    def replay(self, scenario_name: str) -> IncidentBrief:
        scenario = self._scenario_loader(scenario_name)
        brief = self._analyzer.analyze(scenario)
        self._repository.save(brief)
        return brief

    def get(self, incident_id: str) -> IncidentBrief | None:
        return self._repository.get(incident_id)

    def list(self, *, limit: int = 20) -> tuple[IncidentBrief, ...]:
        return self._repository.list(limit=limit)
