import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartNoAxesCombined, Crosshair, FileChartColumnIncreasing, ScanSearch } from "lucide-react";

import {
  buildBlastRadiusPlotData,
  buildCandidatePlotData,
  buildEvidenceSignalData,
} from "./visualization";
import type { IncidentBrief } from "./types";

const gridStroke = "rgba(160, 184, 195, 0.28)";
const axisStroke = "#a2b4bc";
const tooltipStyle = {
  background: "#071019",
  border: "1px solid rgba(37, 246, 230, 0.45)",
  borderRadius: 0,
  color: "#edfaff",
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 11,
};

function PlotEmpty({ message }: { message: string }) {
  return <div className="plot-empty"><ScanSearch size={28} /><p>{message}</p></div>;
}

export function OverviewSignalMap({ incident }: { incident: IncidentBrief }) {
  const data = buildCandidatePlotData(incident.ranked_candidates);
  return (
    <section className="plot-panel overview-signal-map" aria-labelledby="signal-map-title">
      <div className="plot-header">
        <div><Crosshair size={17} /><h2 id="signal-map-title">Divergence signal map</h2></div>
        <span>local attribution × ranked score</span>
      </div>
      {data.length === 0 ? <PlotEmpty message="No comparable candidates were ranked; the safe abstention remains visible." /> : (
        <figure className="plot-figure">
          <div className="plot-legend" aria-label="Plot legend">
            <span><i className="legend-selected" /> selected divergence</span>
            <span><i className="legend-baseline" /> alternate candidate</span>
          </div>
          <div className="chart-frame chart-frame-large">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 16, right: 28, bottom: 12, left: 4 }}>
                <CartesianGrid stroke={gridStroke} strokeDasharray="3 6" />
                <XAxis dataKey="localAttribution" domain={[0, 100]} name="Local attribution" stroke={axisStroke} tick={{ fontSize: 10 }} type="number" unit="%" />
                <YAxis dataKey="score" domain={[0, 100]} name="Ranking score" stroke={axisStroke} tick={{ fontSize: 10 }} type="number" unit="%" />
                <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "#25f6e6", strokeDasharray: "3 6" }} />
                <Scatter data={data} isAnimationActive={false} name="Candidate">
                  {data.map((candidate) => (
                    <Cell fill={candidate.rank === 1 ? "#f5f03d" : "#3b82f6"} key={candidate.operationKey} stroke={candidate.rank === 1 ? "#fff86b" : "#25f6e6"} strokeWidth={2} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <figcaption className="plot-summary">Every point is a ranked operation from the stored incident brief. Hover to inspect its exact aggregate values.</figcaption>
        </figure>
      )}
    </section>
  );
}

export function TelemetryPlots({ incident }: { incident: IncidentBrief }) {
  const data = buildCandidatePlotData(incident.ranked_candidates);
  const top = data[0];
  const durationData = top ? [
    { metric: "Inclusive", baseline: 1, failing: top.inclusiveRatio, failingLabel: `${top.inclusiveRatio}×` },
    { metric: "Self / local", baseline: 1, failing: top.selfDurationRatio, failingLabel: `${top.selfDurationRatio}×` },
  ] : [];

  return (
    <div className="telemetry-plot-grid">
      <section className="plot-panel" aria-labelledby="candidate-score-title">
        <div className="plot-header"><div><ChartNoAxesCombined size={17} /><h2 id="candidate-score-title">Candidate ranking</h2></div><span>percent</span></div>
        {data.length === 0 ? <PlotEmpty message="Candidate plots are unavailable because the incident did not meet the comparison boundary." /> : (
          <figure className="plot-figure">
            <div className="plot-legend"><span><i className="legend-selected" /> score</span><span><i className="legend-healthy" /> local attribution</span></div>
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.slice(0, 4)} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 12 }}>
                  <CartesianGrid horizontal={false} stroke={gridStroke} strokeDasharray="3 6" />
                  <XAxis domain={[0, 100]} stroke={axisStroke} tick={{ fontSize: 10 }} type="number" unit="%" />
                  <YAxis dataKey="operation" stroke={axisStroke} tick={{ fontSize: 10 }} type="category" width={118} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(37, 246, 230, 0.05)" }} />
                  <Bar dataKey="score" fill="#f5f03d" isAnimationActive={false} name="Ranking score" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="scoreLabel" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="right" />
                  </Bar>
                  <Bar dataKey="localAttribution" fill="#25f6e6" isAnimationActive={false} name="Local attribution" radius={0} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="plot-summary">The selected divergence should combine a high deterministic score with local, not inherited, latency.</figcaption>
          </figure>
        )}
      </section>

      <section className="plot-panel" aria-labelledby="prevalence-title">
        <div className="plot-header"><div><FileChartColumnIncreasing size={17} /><h2 id="prevalence-title">Cohort prevalence</h2></div><span>healthy vs failing</span></div>
        {data.length === 0 ? <PlotEmpty message="Healthy/failing prevalence is unavailable without comparable candidates." /> : (
          <figure className="plot-figure">
            <div className="plot-legend"><span><i className="legend-baseline" /> healthy</span><span><i className="legend-failing" /> failing</span></div>
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.slice(0, 4)} margin={{ top: 8, right: 18, bottom: 36, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridStroke} strokeDasharray="3 6" />
                  <XAxis angle={-18} dataKey="service" height={52} stroke={axisStroke} textAnchor="end" tick={{ fontSize: 10 }} />
                  <YAxis
                    domain={[0, 110]}
                    stroke={axisStroke}
                    tick={{ fontSize: 10 }}
                    ticks={[0, 25, 50, 75, 100]}
                    unit="%"
                  />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255, 77, 109, 0.05)" }} />
                  <Bar dataKey="healthyPrevalence" fill="#3b82f6" isAnimationActive={false} name="Healthy prevalence" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="healthyPrevalenceLabel" fill="#9fc3ff" fontFamily="IBM Plex Mono" fontSize={9} position="top" />
                  </Bar>
                  <Bar dataKey="failingPrevalence" fill="#ff4d6d" isAnimationActive={false} name="Failing prevalence" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="failingPrevalenceLabel" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="top" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="plot-summary">Red appears only where the failing cohort contains the operation; blue preserves the healthy baseline.</figcaption>
          </figure>
        )}
      </section>

      <section className="plot-panel duration-plot" aria-labelledby="duration-title">
        <div className="plot-header"><div><Crosshair size={17} /><h2 id="duration-title">Duration multiplier</h2></div><span>{top?.operation ?? "no candidate"}</span></div>
        {durationData.length === 0 ? <PlotEmpty message="Duration ratios are unavailable for a safely abstained incident." /> : (
          <figure className="plot-figure">
            <div className="plot-legend"><span><i className="legend-baseline" /> 1× baseline</span><span><i className="legend-failing" /> failing ratio</span></div>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={durationData} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridStroke} strokeDasharray="3 6" />
                  <XAxis dataKey="metric" stroke={axisStroke} tick={{ fontSize: 10 }} />
                  <YAxis stroke={axisStroke} tick={{ fontSize: 10 }} unit="×" />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255, 77, 109, 0.05)" }} />
                  <Bar dataKey="baseline" fill="#3b82f6" isAnimationActive={false} name="Healthy baseline" radius={0} stroke="#25f6e6" strokeWidth={1} />
                  <Bar dataKey="failing" fill="#ff4d6d" isAnimationActive={false} name="Failing duration" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="failingLabel" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="top" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="plot-summary">Ratios compare the ranked operation with its matched healthy cohort; 1× is the stored baseline.</figcaption>
          </figure>
        )}
      </section>
    </div>
  );
}

export function EvidencePlots({ incident }: { incident: IncidentBrief }) {
  const evidenceData = buildEvidenceSignalData(incident.evidence);
  const blastData = buildBlastRadiusPlotData(incident);
  return (
    <div className="evidence-plot-grid">
      <section className="plot-panel" aria-labelledby="evidence-mix-title">
        <div className="plot-header"><div><FileChartColumnIncreasing size={17} /><h2 id="evidence-mix-title">Evidence signal mix</h2></div><span>{incident.evidence.length} stored records</span></div>
        {evidenceData.length === 0 ? <PlotEmpty message="No stored evidence records are available to plot." /> : (
          <figure className="plot-figure">
            <div className="plot-legend"><span><i className="legend-verified" /> supporting</span><span><i className="legend-failing" /> contradicting</span></div>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={evidenceData} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridStroke} strokeDasharray="3 6" />
                  <XAxis dataKey="signal" stroke={axisStroke} tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} stroke={axisStroke} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(37, 246, 230, 0.05)" }} />
                  <Bar dataKey="supporting" fill="#66e3a4" isAnimationActive={false} name="Supporting records" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="supporting" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="top" />
                  </Bar>
                  <Bar dataKey="contradicting" fill="#ff4d6d" isAnimationActive={false} name="Contradicting records" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="contradicting" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="top" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="plot-summary">Counts come directly from the evidence ledger; contradictions remain visible even when confidence is high.</figcaption>
          </figure>
        )}
      </section>

      <section className="plot-panel" aria-labelledby="blast-plot-title">
        <div className="plot-header"><div><Crosshair size={17} /><h2 id="blast-plot-title">Blast radius distribution</h2></div><span>affected percent</span></div>
        {blastData.length === 0 ? <PlotEmpty message="No quantified blast-radius slices were returned for this incident." /> : (
          <figure className="plot-figure">
            <div className="plot-legend"><span><i className="legend-failing" /> affected scope</span></div>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={blastData} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 16 }}>
                  <CartesianGrid horizontal={false} stroke={gridStroke} strokeDasharray="3 6" />
                  <XAxis domain={[0, 100]} stroke={axisStroke} tick={{ fontSize: 10 }} type="number" unit="%" />
                  <YAxis dataKey="label" stroke={axisStroke} tick={{ fontSize: 9 }} type="category" width={138} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255, 77, 109, 0.05)" }} />
                  <Bar dataKey="percentage" fill="#ff4d6d" isAnimationActive={false} name="Affected" radius={0} stroke="#25f6e6" strokeWidth={1}>
                    <LabelList dataKey="percentageLabel" fill="#edfaff" fontFamily="IBM Plex Mono" fontSize={9} position="right" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="plot-summary">Each bar is a stored affected/total aggregation, not a sampled or inferred estimate.</figcaption>
          </figure>
        )}
      </section>
    </div>
  );
}
