import { describe, expect, it } from "vitest";

import { buildDecisionTrail } from "./journey";
import type { DecisionTrailStep } from "./journey";
import type { IncidentBrief } from "./types";

function incident(overrides: Partial<IncidentBrief> = {}): IncidentBrief {
  return {
    incident_id: "incident-1",
    scenario: "inventory-cohort-timeout",
    state: "READY",
    started_at: "2026-07-20T04:00:00Z",
    completed_at: "2026-07-20T04:00:03Z",
    target_operation: "POST /checkout",
    situation: "A deterministic fixture incident.",
    confidence_label: "high",
    cohort: {
      failing_count: 5,
      healthy_count: 5,
      requested_per_cohort: 5,
      coverage: 1,
      match_dimensions: ["route", "region", "topology"],
      exclusions: [],
    },
    ranked_candidates: [
      {
        rank: 1,
        operation_key: "inventory|inventory.reserve",
        service: "inventory",
        operation: "inventory.reserve",
        failing_prevalence: 1,
        healthy_prevalence: 0,
        error_lift: 1,
        inclusive_duration_ratio: 17,
        exclusive_duration_ratio: 25,
        local_attribution: 1,
        score: 1,
        evidence_grade: "high",
        supporting_evidence_ids: ["trace:1"],
        contradicting_evidence_ids: [],
      },
    ],
    evidence: [],
    blast_radius: [],
    timeline: [],
    next_queries: [],
    metrics: {
      analyzed_trace_count: 10,
      candidate_count: 4,
      evidence_count: 9,
      analysis_duration_ms: 3200,
    },
    sentinel_mesh: null,
    ...overrides,
  };
}

function stepById(
  steps: readonly DecisionTrailStep[],
  id: DecisionTrailStep["id"],
): DecisionTrailStep {
  const step = steps.find((item) => item.id === id);
  if (!step) {
    throw new Error(`Missing decision trail step: ${id}`);
  }
  return step;
}

describe("decision trail", () => {
  it("turns a ready incident into a complete judge-readable journey", () => {
    const steps = buildDecisionTrail(incident());

    expect(steps.map((step) => step.id)).toEqual(["signal", "compare", "locate", "handoff"]);
    expect(stepById(steps, "compare").value).toBe("5 healthy / 5 failing");
    expect(stepById(steps, "locate")).toMatchObject({
      value: "inventory.reserve",
      state: "attention",
    });
    expect(stepById(steps, "handoff")).toMatchObject({
      value: "9 linked records",
      page: "evidence",
    });
  });

  it("makes insufficient evidence an explicit safe outcome", () => {
    const steps = buildDecisionTrail(incident({
      state: "INSUFFICIENT_EVIDENCE",
      confidence_label: "insufficient",
      cohort: {
        failing_count: 0,
        healthy_count: 0,
        requested_per_cohort: 5,
        coverage: 0,
        match_dimensions: [],
        exclusions: ["no comparable baseline"],
      },
      ranked_candidates: [],
      metrics: {
        analyzed_trace_count: 0,
        candidate_count: 0,
        evidence_count: 0,
        analysis_duration_ms: 800,
      },
    }));

    expect(stepById(steps, "compare")).toMatchObject({
      value: "No comparable cohorts",
      state: "attention",
    });
    expect(stepById(steps, "locate")).toMatchObject({
      value: "Safe abstention",
      state: "safe",
    });
    expect(stepById(steps, "locate").detail).toContain("No ranked guess");
  });
});
