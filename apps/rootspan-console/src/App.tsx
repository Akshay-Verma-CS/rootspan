import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  ExternalLink,
  FileSearch,
  Gauge,
  Layers3,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
} from "lucide-react";

import { listIncidents, replayGoldenIncident } from "./api";
import { compactTime, percent, ratio, shortId } from "./format";
import type { DivergenceCandidate, Evidence, IncidentBrief } from "./types";

function scorePercent(candidate: DivergenceCandidate): string {
  return `${Math.round(candidate.score * 100)}%`;
}

function App() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const incidentsQuery = useQuery({ queryKey: ["incidents"], queryFn: listIncidents });
  const replayMutation = useMutation({
    mutationFn: replayGoldenIncident,
    onSuccess: (incident) => {
      queryClient.setQueryData<IncidentBrief[]>(["incidents"], (current = []) => [
        incident,
        ...current.filter((item) => item.incident_id !== incident.incident_id),
      ]);
      setSelectedId(incident.incident_id);
    },
  });
  const incidents = incidentsQuery.data ?? [];
  const incident =
    incidents.find((item) => item.incident_id === selectedId) ?? incidents[0] ?? null;

  if (incidentsQuery.isLoading) {
    return <LoadingState />;
  }

  if (!incident) {
    return (
      <EmptyState
        isPending={replayMutation.isPending}
        error={replayMutation.error}
        onReplay={() => replayMutation.mutate()}
      />
    );
  }

  return (
    <div className="app-shell">
      <TopBar
        incident={incident}
        incidents={incidents}
        selectedId={selectedId}
        onSelect={setSelectedId}
        isPending={replayMutation.isPending}
        onReplay={() => replayMutation.mutate()}
      />
      <main>
        <IncidentHero incident={incident} />
        <div className="primary-grid">
          <ServiceCascade incident={incident} />
          <CandidatePanel incident={incident} />
        </div>
        <CohortComparison incident={incident} />
        <div className="evidence-grid">
          <EvidencePanel incident={incident} />
          <BlastRadius incident={incident} />
        </div>
        <div className="bottom-grid">
          <Timeline incident={incident} />
          <NextQueries incident={incident} />
        </div>
      </main>
    </div>
  );
}

function TopBar({
  incident,
  incidents,
  selectedId,
  onSelect,
  isPending,
  onReplay,
}: {
  incident: IncidentBrief;
  incidents: IncidentBrief[];
  selectedId: string | null;
  onSelect: (value: string) => void;
  isPending: boolean;
  onReplay: () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark"><CircleDot size={19} /></div>
        <div><strong>RootSpan</strong><span>incident intelligence</span></div>
      </div>
      <div className="topbar-actions">
        <div className="live-indicator"><span /> SigNoz connected</div>
        <select
          aria-label="Select incident"
          value={selectedId ?? incident.incident_id}
          onChange={(event) => onSelect(event.target.value)}
        >
          {incidents.map((item) => (
            <option key={item.incident_id} value={item.incident_id}>
              INC-{shortId(item.incident_id)} · {item.scenario}
            </option>
          ))}
        </select>
        <button className="button secondary" onClick={onReplay} disabled={isPending}>
          {isPending ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
          Replay incident
        </button>
      </div>
    </header>
  );
}

function IncidentHero({ incident }: { incident: IncidentBrief }) {
  const top = incident.ranked_candidates[0];
  return (
    <section className="incident-hero">
      <div className="hero-copy">
        <div className="eyebrow"><AlertTriangle size={14} /> SLO burn investigation</div>
        <h1>Checkout degradation isolated to <span>{top?.operation ?? "insufficient evidence"}</span></h1>
        <p>{incident.situation}</p>
        <div className="hero-meta">
          <span><Clock3 size={14} /> analyzed {compactTime(incident.completed_at)}</span>
          <span><Layers3 size={14} /> {incident.metrics.analyzed_trace_count} traces</span>
          <span><FileSearch size={14} /> {incident.metrics.evidence_count} evidence records</span>
        </div>
      </div>
      <div className="confidence-card">
        <span>Evidence confidence</span>
        <strong>{incident.confidence_label}</strong>
        <div className="confidence-ring" style={{ "--score": `${(top?.score ?? 0) * 360}deg` } as CSSProperties}>
          <div>{top ? scorePercent(top) : "—"}<small>score</small></div>
        </div>
        <p>Transparent evidence grade, not a calibrated probability.</p>
      </div>
    </section>
  );
}

function ServiceCascade({ incident }: { incident: IncidentBrief }) {
  const scores = new Map(incident.ranked_candidates.map((item) => [item.service, item]));
  const services = [
    { name: "gateway", operation: "POST /checkout" },
    { name: "checkout", operation: "checkout.place_order" },
    { name: "inventory", operation: "inventory.reserve" },
    { name: "inventory-db", operation: "SELECT stock" },
  ];
  const topService = incident.ranked_candidates[0]?.service;
  return (
    <section className="panel cascade-panel">
      <PanelHeader icon={<Activity size={17} />} title="Service cascade" meta="earliest local divergence" />
      <div className="cascade">
        {services.map((service, index) => {
          const candidate = scores.get(service.name);
          const active = service.name === topService;
          return (
            <div className="cascade-step" key={service.name}>
              <div className={`service-node ${active ? "active" : ""}`}>
                <div className="node-icon">{active ? <AlertTriangle size={18} /> : <Check size={18} />}</div>
                <div><strong>{service.name}</strong><span>{service.operation}</span></div>
                <em>{candidate ? scorePercent(candidate) : "—"}</em>
              </div>
              {index < services.length - 1 && <ChevronRight className="cascade-arrow" size={20} />}
            </div>
          );
        })}
      </div>
      <div className="insight-strip">
        <ShieldCheck size={17} />
        <span>Parent errors were penalized because their self-duration remained normal.</span>
      </div>
    </section>
  );
}

function CandidatePanel({ incident }: { incident: IncidentBrief }) {
  return (
    <section className="panel candidates-panel">
      <PanelHeader icon={<Gauge size={17} />} title="Ranked hypotheses" meta="inspectable score" />
      <div className="candidate-list">
        {incident.ranked_candidates.slice(0, 4).map((candidate) => (
          <div className={`candidate ${candidate.rank === 1 ? "top" : ""}`} key={candidate.operation_key}>
            <div className="candidate-rank">0{candidate.rank}</div>
            <div className="candidate-copy">
              <strong>{candidate.operation}</strong>
              <span>{candidate.service} · {candidate.evidence_grade} evidence</span>
            </div>
            <div className="score-track"><span style={{ width: scorePercent(candidate) }} /></div>
            <b>{scorePercent(candidate)}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function CohortComparison({ incident }: { incident: IncidentBrief }) {
  const top = incident.ranked_candidates[0];
  if (!top) return null;
  const metrics = [
    { label: "Anomalous prevalence", healthy: percent(top.healthy_prevalence), failing: percent(top.failing_prevalence), width: top.failing_prevalence * 100 },
    { label: "Inclusive duration", healthy: "1.0× baseline", failing: ratio(top.inclusive_duration_ratio), width: Math.min(top.inclusive_duration_ratio * 6, 100) },
    { label: "Local / self duration", healthy: "1.0× baseline", failing: ratio(top.exclusive_duration_ratio), width: Math.min(top.exclusive_duration_ratio * 4, 100) },
  ];
  return (
    <section className="panel cohort-panel">
      <PanelHeader
        icon={<Layers3 size={17} />}
        title="Healthy vs failing cohorts"
        meta={`${incident.cohort.healthy_count} matched healthy · ${incident.cohort.failing_count} failing`}
      />
      <div className="cohort-body">
        <div className="cohort-labels">
          <span className="healthy-dot">Healthy</span><span className="failing-dot">Failing</span>
        </div>
        {metrics.map((metric) => (
          <div className="metric-row" key={metric.label}>
            <strong>{metric.label}</strong>
            <div className="metric-values"><span>{metric.healthy}</span><span>{metric.failing}</span></div>
            <div className="dual-track"><i /><b style={{ width: `${metric.width}%` }} /></div>
          </div>
        ))}
        <div className="cohort-facts">
          <div><span>Coverage</span><strong>{percent(incident.cohort.coverage)}</strong></div>
          <div><span>Local attribution</span><strong>{percent(top.local_attribution)}</strong></div>
          <div><span>Error lift</span><strong>{percent(top.error_lift)}</strong></div>
          <div><span>Matched by</span><strong>{incident.cohort.match_dimensions.length} dimensions</strong></div>
        </div>
      </div>
    </section>
  );
}

function EvidencePanel({ incident }: { incident: IncidentBrief }) {
  const top = incident.ranked_candidates[0];
  const relevantIds = new Set([...(top?.supporting_evidence_ids ?? []), ...(top?.contradicting_evidence_ids ?? [])]);
  const evidence = incident.evidence.filter((item) => relevantIds.has(item.id));
  return (
    <section className="panel evidence-panel">
      <PanelHeader icon={<Search size={17} />} title="Evidence ledger" meta="every claim is linked" />
      <div className="evidence-list">
        {evidence.map((item) => <EvidenceRow key={item.id} evidence={item} />)}
      </div>
    </section>
  );
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  const icon = evidence.supports ? <Check size={15} /> : <AlertTriangle size={15} />;
  return (
    <a className={`evidence-row ${evidence.supports ? "support" : "contradiction"}`} href={evidence.web_url} target="_blank" rel="noreferrer">
      <div className="evidence-status">{icon}</div>
      <div><span>{evidence.signal} · {evidence.query_tool}</span><p>{evidence.observation}</p></div>
      <ExternalLink size={14} />
    </a>
  );
}

function BlastRadius({ incident }: { incident: IncidentBrief }) {
  const maxPercentage = Math.max(...incident.blast_radius.map((item) => item.percentage), 1);
  return (
    <section className="panel blast-panel">
      <PanelHeader icon={<Gauge size={17} />} title="Blast radius" meta="affected / total" />
      <div className="blast-list">
        {incident.blast_radius.map((slice) => (
          <div className="blast-row" key={`${slice.dimension}-${slice.value}`}>
            <div><span>{slice.dimension}</span><strong>{slice.value}</strong></div>
            <div className="blast-track"><span style={{ width: `${(slice.percentage / maxPercentage) * 100}%` }} /></div>
            <b>{slice.affected}/{slice.total}<em>{slice.percentage}%</em></b>
          </div>
        ))}
      </div>
    </section>
  );
}

function Timeline({ incident }: { incident: IncidentBrief }) {
  return (
    <section className="panel timeline-panel">
      <PanelHeader icon={<Clock3 size={17} />} title="Incident timeline" meta="change → divergence → alert" />
      <div className="timeline">
        {incident.timeline.map((event, index) => (
          <div className="timeline-row" key={`${event.occurred_at}-${event.title}`}>
            <time>{compactTime(event.occurred_at)}</time>
            <div className={`timeline-marker ${event.kind}`}><span /></div>
            <div><strong>{event.title}</strong><p>{event.detail}</p></div>
            {index < incident.timeline.length - 1 && <div className="timeline-line" />}
          </div>
        ))}
      </div>
    </section>
  );
}

function NextQueries({ incident }: { incident: IncidentBrief }) {
  return (
    <section className="panel query-panel">
      <PanelHeader icon={<TerminalSquare size={17} />} title="Responder handoff" meta="read-only next steps" />
      <div className="query-list">
        {incident.next_queries.map((query, index) => (
          <div className="query" key={query}>
            <span>0{index + 1}</span><p>{query}</p><ArrowRight size={15} />
          </div>
        ))}
      </div>
      <div className="human-boundary"><ShieldCheck size={16} /> Human approval remains required for every production change.</div>
    </section>
  );
}

function PanelHeader({ icon, title, meta }: { icon: ReactNode; title: string; meta: string }) {
  return <div className="panel-header"><div>{icon}<h2>{title}</h2></div><span>{meta}</span></div>;
}

function LoadingState() {
  return <div className="center-state"><RefreshCw className="spin" size={28} /><h1>Loading incident state</h1></div>;
}

function EmptyState({ isPending, error, onReplay }: { isPending: boolean; error: Error | null; onReplay: () => void }) {
  return (
    <div className="empty-shell">
      <div className="empty-brand"><CircleDot size={22} /> RootSpan</div>
      <div className="empty-card">
        <div className="empty-icon"><Sparkles size={28} /></div>
        <span>Evidence-bound incident correlation</span>
        <h1>Find the first broken thing,<br />not the loudest alert.</h1>
        <p>Replay the golden checkout incident to compare healthy and failing trace cohorts, rank the first local divergence, and compile a cited responder handoff.</p>
        <button className="button primary" disabled={isPending} onClick={onReplay}>
          {isPending ? <RefreshCw className="spin" size={17} /> : <Play size={17} />}
          {isPending ? "Analyzing cohorts…" : "Run golden incident"}
        </button>
        {error && <div className="error-message">{error.message}</div>}
      </div>
    </div>
  );
}

export default App;
