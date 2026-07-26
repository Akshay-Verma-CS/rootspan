import { describe, expect, it } from "vitest";

import {
  buildBlastRadiusPlotData,
  buildCandidatePlotData,
  buildEvidenceSignalData,
} from "./visualization";
import type { DivergenceCandidate, Evidence } from "./types";

const candidate: DivergenceCandidate = {
  rank: 1,
  operation_key: "inventory|inventory.reserve",
  service: "inventory",
  operation: "inventory.reserve",
  failing_prevalence: 1,
  healthy_prevalence: 0.125,
  error_lift: 0.875,
  inclusive_duration_ratio: 17,
  exclusive_duration_ratio: 25,
  local_attribution: 0.984,
  score: 0.956,
  evidence_grade: "high",
  supporting_evidence_ids: ["trace:1", "log:1"],
  contradicting_evidence_ids: ["metric:1"],
};

describe("incident visualization data", () => {
  it("plots exact stored candidate aggregates without fabricating a series", () => {
    expect(buildCandidatePlotData([candidate])).toEqual([
      expect.objectContaining({
        operation: "inventory.reserve",
        score: 95.6,
        scoreLabel: "95.6%",
        localAttribution: 98.4,
        healthyPrevalence: 12.5,
        failingPrevalence: 100,
        failingPrevalenceLabel: "100%",
        evidenceCount: 3,
      }),
    ]);
  });

  it("keeps supporting and contradicting evidence visually separate", () => {
    const evidence: Evidence[] = [
      {
        id: "trace:1",
        signal: "trace",
        operation_key: candidate.operation_key,
        supports: true,
        observation: "timeout",
        query_tool: "search_traces",
        query_args: {},
        web_url: "https://example.com/trace",
      },
      {
        id: "trace:2",
        signal: "trace",
        operation_key: candidate.operation_key,
        supports: false,
        observation: "healthy trace",
        query_tool: "search_traces",
        query_args: {},
        web_url: "https://example.com/trace-2",
      },
    ];

    expect(buildEvidenceSignalData(evidence)).toEqual([
      { signal: "trace", supporting: 1, contradicting: 1 },
    ]);
  });

  it("returns empty plot data for an insufficient-evidence incident", () => {
    expect(buildCandidatePlotData([])).toEqual([]);
    expect(buildEvidenceSignalData([])).toEqual([]);
    expect(buildBlastRadiusPlotData({ blast_radius: [] })).toEqual([]);
  });
});
