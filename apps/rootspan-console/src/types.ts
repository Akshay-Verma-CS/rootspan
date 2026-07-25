export type IncidentState =
  | "RECEIVED"
  | "COLLECTING"
  | "COHORTING"
  | "ALIGNING"
  | "CORROBORATING"
  | "COMPILING"
  | "READY"
  | "INSUFFICIENT_EVIDENCE"
  | "FAILED"
  | "CLOSED";
export type Confidence = "high" | "medium" | "low" | "insufficient";
export type SentinelRole = "LEADER" | "FOLLOWER";
export type SentinelOutcome = "READY" | "DEGRADED" | "FAILED";

export interface Evidence {
  id: string;
  signal: "trace" | "log" | "metric" | "change" | "topology";
  operation_key: string;
  supports: boolean;
  observation: string;
  query_tool: string;
  query_args: Record<string, unknown>;
  web_url: string;
  response_hash?: string | null;
  observed_at?: string | null;
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

export interface SentinelFinding {
  sentinel_id: string;
  system: string;
  role: SentinelRole;
  outcome: SentinelOutcome;
  summary: string;
  evidence_ids: string[];
  started_at: string;
  completed_at: string;
  error_code: string | null;
}

export interface SentinelMeshRun {
  leader_id: string;
  previous_leader_ids: string[];
  follower_ids: string[];
  status: SentinelOutcome;
  lease_generation: number;
  started_at: string;
  completed_at: string;
  findings: SentinelFinding[];
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
  sentinel_mesh: SentinelMeshRun | null;
}

export interface IncidentListResponse {
  incidents: IncidentBrief[];
}
