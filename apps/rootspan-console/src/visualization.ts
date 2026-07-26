import type { DivergenceCandidate, Evidence, IncidentBrief } from "./types";

function toPercent(value: number): number {
  return Math.round(value * 1000) / 10;
}

export interface CandidatePlotDatum {
  evidenceCount: number;
  failingPrevalence: number;
  failingPrevalenceLabel: string;
  healthyPrevalence: number;
  healthyPrevalenceLabel: string;
  inclusiveRatio: number;
  localAttribution: number;
  operation: string;
  operationKey: string;
  rank: number;
  score: number;
  scoreLabel: string;
  selfDurationRatio: number;
  service: string;
}

export interface EvidenceSignalDatum {
  contradicting: number;
  signal: Evidence["signal"];
  supporting: number;
}

export interface BlastRadiusPlotDatum {
  affected: number;
  label: string;
  percentage: number;
  percentageLabel: string;
  total: number;
}

export function buildCandidatePlotData(
  candidates: readonly DivergenceCandidate[],
): CandidatePlotDatum[] {
  return candidates.slice(0, 6).map((candidate) => {
    const failingPrevalence = toPercent(candidate.failing_prevalence);
    const healthyPrevalence = toPercent(candidate.healthy_prevalence);
    const score = toPercent(candidate.score);
    return {
    evidenceCount:
      candidate.supporting_evidence_ids.length + candidate.contradicting_evidence_ids.length,
    failingPrevalence,
    failingPrevalenceLabel: `${failingPrevalence}%`,
    healthyPrevalence,
    healthyPrevalenceLabel: `${healthyPrevalence}%`,
    inclusiveRatio: candidate.inclusive_duration_ratio,
    localAttribution: toPercent(candidate.local_attribution),
    operation: candidate.operation,
    operationKey: candidate.operation_key,
    rank: candidate.rank,
    score,
    scoreLabel: `${score}%`,
    selfDurationRatio: candidate.exclusive_duration_ratio,
    service: candidate.service,
    };
  });
}

export function buildEvidenceSignalData(
  evidence: readonly Evidence[],
): EvidenceSignalDatum[] {
  const signals: Evidence["signal"][] = ["trace", "log", "metric", "change", "topology"];
  return signals
    .map((signal) => ({
      signal,
      supporting: evidence.filter((item) => item.signal === signal && item.supports).length,
      contradicting: evidence.filter((item) => item.signal === signal && !item.supports).length,
    }))
    .filter((datum) => datum.supporting > 0 || datum.contradicting > 0);
}

export function buildBlastRadiusPlotData(
  incident: Pick<IncidentBrief, "blast_radius">,
): BlastRadiusPlotDatum[] {
  return incident.blast_radius.map((slice) => ({
    affected: slice.affected,
    label: `${slice.dimension}: ${slice.value}`,
    percentage: slice.percentage,
    percentageLabel: `${slice.percentage}%`,
    total: slice.total,
  }));
}
