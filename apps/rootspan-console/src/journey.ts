import type { IncidentBrief } from "./types";

export interface DecisionTrailStep {
  id: "signal" | "compare" | "locate" | "handoff";
  label: string;
  value: string;
  detail: string;
  page: "telemetry" | "evidence";
  state: "observed" | "verified" | "attention" | "safe";
}

export function buildDecisionTrail(incident: IncidentBrief): readonly DecisionTrailStep[] {
  const top = incident.ranked_candidates[0];
  const hasComparableCohorts = incident.cohort.healthy_count > 0 && incident.cohort.failing_count > 0;

  return [
    {
      id: "signal",
      label: "Upstream symptom",
      value: "Checkout SLO burn",
      detail: "Observed impact; not treated as the root cause.",
      page: "telemetry",
      state: "observed",
    },
    {
      id: "compare",
      label: "Matched comparison",
      value: hasComparableCohorts
        ? `${incident.cohort.healthy_count} healthy / ${incident.cohort.failing_count} failing`
        : "No comparable cohorts",
      detail: hasComparableCohorts
        ? `${Math.round(incident.cohort.coverage * 100)}% usable cohort coverage.`
        : "The comparison boundary failed safely.",
      page: "telemetry",
      state: hasComparableCohorts ? "verified" : "attention",
    },
    {
      id: "locate",
      label: top ? "First local divergence" : "Correlation result",
      value: top?.operation ?? "Safe abstention",
      detail: top
        ? `${top.evidence_grade} evidence · ${Math.round(top.local_attribution * 100)}% local attribution.`
        : "No ranked guess was produced without evidence.",
      page: "telemetry",
      state: top ? "attention" : "safe",
    },
    {
      id: "handoff",
      label: "Responder packet",
      value: `${incident.metrics.evidence_count} linked records`,
      detail: "Raw evidence remains inspectable; production authority remains human.",
      page: "evidence",
      state: "safe",
    },
  ];
}
