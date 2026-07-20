export type IncidentState = "READY" | "INSUFFICIENT_EVIDENCE" | "FAILED";
export type Confidence = "high" | "medium" | "low" | "insufficient";

export interface Evidence {
  id: string;
  signal: "trace" | "log" | "metric" | "change" | "topology";
  operation_key: string;
  supports: boolean;
  observation: string;
  query_tool: string;
  query_args: Record<string, unknown>;
  web_url: string;
}

export interface DivergenceCandidate {
  rank: number;
  operation_key: string;
  service: string;
  operation: string;
  failing_prevalence: number;
  healthy_prevalence: number;
  error_lift: number;
  inclusive_duration_ratio: number;
  exclusive_duration_ratio: number;
  local_attribution: number;
  score: number;
  evidence_grade: "high" | "medium" | "low";
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
}

export interface CohortSummary {
  failing_count: number;
  healthy_count: number;
  requested_per_cohort: number;
  coverage: number;
  match_dimensions: string[];
  exclusions: string[];
}

export interface BlastRadiusSlice {
  dimension: string;
  value: string;
  affected: number;
  total: number;
  percentage: number;
}

export interface TimelineEvent {
  occurred_at: string;
  kind: "change" | "alert" | "observation";
  title: string;
  detail: string;
  evidence_id: string | null;
}

export interface IncidentBrief {
  incident_id: string;
  scenario: string;
  state: IncidentState;
  started_at: string;
  completed_at: string;
  target_operation: string;
  situation: string;
  confidence_label: Confidence;
  cohort: CohortSummary;
  ranked_candidates: DivergenceCandidate[];
  evidence: Evidence[];
  blast_radius: BlastRadiusSlice[];
  timeline: TimelineEvent[];
  next_queries: string[];
  metrics: {
    analyzed_trace_count: number;
    candidate_count: number;
    evidence_count: number;
    analysis_duration_ms: number;
  };
}

export interface IncidentListResponse {
  incidents: IncidentBrief[];
}
