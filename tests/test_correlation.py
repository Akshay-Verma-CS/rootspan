"""Core first-divergence behavior and safety invariants."""

from datetime import UTC, datetime

from rootspan.correlation import CorrelationAnalyzer
from rootspan.domain import IncidentState
from rootspan.fixtures.loader import load_scenario


def fixed_clock() -> datetime:
    return datetime(2026, 7, 20, 4, 5, tzinfo=UTC)


def test_inventory_is_ranked_above_propagated_parent_errors() -> None:
    fixture = load_scenario("inventory-cohort-timeout")
    brief = CorrelationAnalyzer(clock=fixed_clock).analyze(fixture, incident_id="incident-1")

    assert brief.state is IncidentState.READY
    assert brief.confidence_label == "high"
    assert brief.ranked_candidates[0].operation_key == "inventory|inventory.reserve"
    assert brief.ranked_candidates[0].exclusive_duration_ratio > 10
    assert brief.ranked_candidates[0].local_attribution > 0.9
    assert brief.ranked_candidates[0].score > brief.ranked_candidates[1].score


def test_every_candidate_references_existing_evidence() -> None:
    fixture = load_scenario("inventory-cohort-timeout")
    brief = CorrelationAnalyzer(clock=fixed_clock).analyze(fixture, incident_id="incident-2")
    evidence_ids = {item.id for item in brief.evidence}

    for candidate in brief.ranked_candidates:
        assert set(candidate.supporting_evidence_ids) <= evidence_ids
        assert set(candidate.contradicting_evidence_ids) <= evidence_ids


def test_analyzer_abstains_without_a_healthy_baseline() -> None:
    fixture = load_scenario("inventory-cohort-timeout").model_copy(update={"healthy_traces": ()})
    brief = CorrelationAnalyzer(clock=fixed_clock).analyze(fixture, incident_id="incident-3")

    assert brief.state is IncidentState.INSUFFICIENT_EVIDENCE
    assert brief.confidence_label == "insufficient"
    assert brief.ranked_candidates == ()
