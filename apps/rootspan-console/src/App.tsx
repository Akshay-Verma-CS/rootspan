import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Clock3,
  Crown,
  ExternalLink,
  FileSearch,
  Gauge,
  Layers3,
  LayoutDashboard,
  Play,
  RefreshCw,
  RadioTower,
  Search,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
} from "lucide-react";

import { listIncidents, replayGoldenIncident, runLiveIncident } from "./api";
import { compactTime, percent, ratio, shortId } from "./format";
import { buildDecisionTrail } from "./journey";
import { EvidencePlots, OverviewSignalMap, TelemetryPlots } from "./Visualizations";
import type { DivergenceCandidate, Evidence, IncidentBrief } from "./types";

type WorkspacePage = "overview" | "telemetry" | "evidence" | "handoff";

const workspacePages: readonly { id: WorkspacePage; label: string; caption: string }[] = [
  { id: "overview", label: "Overview", caption: "Ranked result" },
  { id: "telemetry", label: "Telemetry", caption: "Plotted cohorts" },
  { id: "evidence", label: "Evidence", caption: "Cited signals" },
  { id: "handoff", label: "Handoff", caption: "Human decision" },
];

function scorePercent(candidate: DivergenceCandidate): string {
  return `${Math.round(candidate.score * 100)}%`;
}

function App() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activePage, setActivePage] = useState<WorkspacePage>("overview");
  const incidentsQuery = useQuery({ queryKey: ["incidents"], queryFn: listIncidents });
  const replayMutation = useMutation({
    mutationFn: replayGoldenIncident,
    onSuccess: (incident) => {
      queryClient.setQueryData<IncidentBrief[]>(["incidents"], (current = []) => [
        incident,
        ...current.filter((item) => item.incident_id !== incident.incident_id),
      ]);
      setSelectedId(incident.incident_id);
      setActivePage("overview");
    },
  });
  const liveMutation = useMutation({
    mutationFn: runLiveIncident,
    onSuccess: (newIncident) => {
      queryClient.setQueryData<IncidentBrief[]>(["incidents"], (current = []) => [
        newIncident,
        ...current.filter((item) => item.incident_id !== newIncident.incident_id),
      ]);
      setSelectedId(newIncident.incident_id);
      setActivePage("overview");
    },
  });
  const incidents = incidentsQuery.data ?? [];
  const incident =
    incidents.find((item) => item.incident_id === selectedId) ?? incidents[0] ?? null;

  const navigateToPage = (page: WorkspacePage) => {
    setActivePage(page);
    window.requestAnimationFrame(() => {
      document.getElementById("incident-content")?.scrollIntoView({ behavior: "smooth" });
    });
  };

  if (incidentsQuery.isLoading) {
    return <LoadingState />;
  }

  if (!incident) {
    return (
      <EmptyState
        isReplayPending={replayMutation.isPending}
        isLivePending={liveMutation.isPending}
        error={liveMutation.error ?? replayMutation.error}
        onReplay={() => replayMutation.mutate()}
        onLive={() => liveMutation.mutate()}
      />
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#incident-content">Skip to incident workspace</a>
      <div className="chrome-stack">
        <TopBar
          incident={incident}
          incidents={incidents}
          selectedId={selectedId}
          activePage={activePage}
          onNavigate={navigateToPage}
          onSelect={(value) => {
            setSelectedId(value);
            setActivePage("overview");
          }}
          isPending={replayMutation.isPending}
          isLivePending={liveMutation.isPending}
          onReplay={() => replayMutation.mutate()}
          onLive={() => liveMutation.mutate()}
        />
        <StatusRibbon incident={incident} />
      </div>
      {liveMutation.error && <div className="error-message top-error">{liveMutation.error.message}</div>}
      <main id="incident-content">
        <WorkspaceNavigation activePage={activePage} onNavigate={navigateToPage} />
        {activePage === "overview" && (
          <section className="workspace-page overview-page" aria-labelledby="overview-title">
            <IncidentHero incident={incident} visual={<OverviewSignalMap incident={incident} />} />
            <DecisionTrail incident={incident} onNavigate={navigateToPage} />
          </section>
        )}
        {activePage === "telemetry" && (
          <section className="workspace-page console-section" aria-labelledby="telemetry-title">
            <SectionIntro
              index="02"
              eyebrow="Telemetry surface"
              title="Compare healthy and failing cohorts"
              description="Verified incident aggregates are plotted with the same evidence boundary used by the deterministic ranker. Red marks failing data; blue preserves the healthy baseline."
              titleId="telemetry-title"
            />
            <div className="primary-grid">
              <ServiceCascade incident={incident} />
              <CandidatePanel incident={incident} />
            </div>
            <TelemetryPlots incident={incident} />
            <CohortComparison incident={incident} />
          </section>
        )}
        {activePage === "evidence" && (
          <section className="workspace-page console-section" aria-labelledby="evidence-title">
            <SectionIntro
              index="03"
              eyebrow="Evidence packet"
              title="Inspect supporting and contradicting signals"
              description={`${incident.metrics.evidence_count} stored records, ${incident.sentinel_mesh?.findings.length ?? 0} sentinel observations, and quantified blast-radius slices.`}
              titleId="evidence-title"
            />
            <EvidencePlots incident={incident} />
            <SentinelMeshPanel incident={incident} />
            <div className="evidence-grid">
              <EvidencePanel incident={incident} />
              <BlastRadius incident={incident} />
            </div>
          </section>
        )}
        {activePage === "handoff" && (
          <section className="workspace-page console-section" aria-labelledby="handoff-title">
            <SectionIntro
              index="04"
              eyebrow="Human handoff"
              title="Review the timeline and next read-only checks"
              description="The console stops at a cited investigation packet. Production authority stays with the responder."
              titleId="handoff-title"
            />
            <div className="bottom-grid">
              <Timeline incident={incident} />
              <NextQueries incident={incident} />
            </div>
          </section>
        )}
        <WorkspacePager activePage={activePage} onNavigate={navigateToPage} />
      </main>
    </div>
  );
}

function TopBar({
  incident,
  incidents,
  selectedId,
  activePage,
  onNavigate,
  onSelect,
  isPending,
  isLivePending,
  onReplay,
  onLive,
}: {
  incident: IncidentBrief;
  incidents: IncidentBrief[];
  selectedId: string | null;
  activePage: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
  onSelect: (value: string) => void;
  isPending: boolean;
  isLivePending: boolean;
  onReplay: () => void;
  onLive: () => void;
}) {
  const isLiveEvidence = incident.scenario.startsWith("live-");
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">R<span>S</span></div>
        <div className="brand-word">ROOT<span>SPAN</span></div>
      </div>
      <nav className="console-nav" aria-label="Incident sections">
        {workspacePages.map((page) => (
          <button aria-current={activePage === page.id ? "page" : undefined} key={page.id} onClick={() => onNavigate(page.id)} type="button">
            {page.label}
          </button>
        ))}
      </nav>
      <div className="topbar-actions">
        <div className={`live-indicator ${isLiveEvidence ? "" : "replay"}`}>
          <span /> {isLiveEvidence ? "Live SigNoz evidence" : "Replay evidence"}
        </div>
        <IncidentPicker
          incident={incident}
          incidents={incidents}
          selectedId={selectedId}
          onSelect={onSelect}
        />
        <button className="button secondary" onClick={onReplay} disabled={isPending}>
          {isPending ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
          {isPending ? "Replaying…" : "Replay incident"}
        </button>
        <button className="button primary" onClick={onLive} disabled={isLivePending}>
          {isLivePending ? <RefreshCw className="spin" size={16} /> : <Activity size={16} />}
          {isLivePending ? "Collecting…" : "Investigate live"}
        </button>
      </div>
    </header>
  );
}

function IncidentPicker({
  incident,
  incidents,
  selectedId,
  onSelect,
}: {
  incident: IncidentBrief;
  incidents: IncidentBrief[];
  selectedId: string | null;
  onSelect: (value: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedIncidentId = selectedId ?? incident.incident_id;
  const selectedIndex = Math.max(incidents.findIndex((item) => item.incident_id === selectedIncidentId), 0);
  const [activeIndex, setActiveIndex] = useState(selectedIndex);
  const pickerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listboxRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  useEffect(() => {
    if (!isOpen) return;
    setActiveIndex(selectedIndex);
    listboxRef.current?.focus();

    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, [isOpen, selectedIndex]);

  const chooseIncident = (index: number) => {
    const nextIncident = incidents[index];
    if (!nextIncident) return;
    onSelect(nextIncident.incident_id);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const handleListboxKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, incidents.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Home") {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActiveIndex(incidents.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      chooseIncident(activeIndex);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      triggerRef.current?.focus();
    }
  };

  return (
    <div className="incident-picker" ref={pickerRef}>
      <button
        aria-controls={listboxId}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={`Select incident. Current incident INC-${shortId(incident.incident_id)}`}
        className="incident-picker-trigger"
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setIsOpen(true);
          }
        }}
        ref={triggerRef}
        type="button"
      >
        <span className={`picker-signal ${incident.scenario.startsWith("live-") ? "live" : "replay"}`} />
        <span className="picker-copy">
          <strong>INC-{shortId(incident.incident_id)}</strong>
          <small>{incident.scenario}</small>
        </span>
        <ChevronDown className="picker-chevron" size={16} />
      </button>
      {isOpen && (
        <div
          aria-activedescendant={`${listboxId}-option-${activeIndex}`}
          aria-label="Available incidents"
          className="incident-picker-menu"
          id={listboxId}
          onKeyDown={handleListboxKeyDown}
          ref={listboxRef}
          role="listbox"
          tabIndex={-1}
        >
          <div className="picker-menu-header">
            <span>Incident archive</span>
            <strong>{incidents.length.toString().padStart(2, "0")} records</strong>
          </div>
          <div className="picker-options">
            {incidents.map((item, index) => {
              const isSelected = item.incident_id === selectedIncidentId;
              const isActive = index === activeIndex;
              const isLive = item.scenario.startsWith("live-");
              return (
                <button
                  aria-selected={isSelected}
                  className={`picker-option ${isSelected ? "selected" : ""} ${isActive ? "active" : ""}`}
                  id={`${listboxId}-option-${index}`}
                  key={item.incident_id}
                  onClick={() => chooseIncident(index)}
                  onMouseEnter={() => setActiveIndex(index)}
                  role="option"
                  tabIndex={-1}
                  type="button"
                >
                  <span className={`picker-signal ${isLive ? "live" : "replay"}`} />
                  <span className="picker-option-copy">
                    <strong>INC-{shortId(item.incident_id)}</strong>
                    <small>{item.scenario}</small>
                  </span>
                  <span className="picker-option-meta">
                    <small>{isLive ? "LIVE" : "REPLAY"}</small>
                    {isSelected && <Check size={15} />}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="picker-menu-footer">↑↓ navigate · enter select · esc close</div>
        </div>
      )}
    </div>
  );
}

function StatusRibbon({ incident }: { incident: IncidentBrief }) {
  const meshState = incident.sentinel_mesh?.status ?? "REPLAY";
  return (
    <div className="status-ribbon" aria-label="Investigation guarantees">
      <div className="status-track">
        <span><RadioTower size={13} /> SENTINEL MESH: {meshState}</span>
        <span><Activity size={13} /> CORRELATION: DETERMINISTIC</span>
        <span><ShieldCheck size={13} /> RUNTIME ACCESS: READ ONLY</span>
        <span><Crown size={13} /> HUMAN AUTHORITY: REQUIRED</span>
      </div>
    </div>
  );
}

function pageIcon(page: WorkspacePage): ReactNode {
  if (page === "overview") return <LayoutDashboard size={17} />;
  if (page === "telemetry") return <BarChart3 size={17} />;
  if (page === "evidence") return <FileSearch size={17} />;
  return <BookOpenCheck size={17} />;
}

function WorkspaceNavigation({
  activePage,
  onNavigate,
}: {
  activePage: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
}) {
  return (
    <nav className="workspace-nav" aria-label="Incident workspace pages">
      <div className="workspace-nav-copy">
        <span>Incident workspace</span>
        <strong>Evidence before action</strong>
      </div>
      <ol>
        {workspacePages.map((page, index) => (
          <li key={page.id}>
            <button
              aria-current={activePage === page.id ? "page" : undefined}
              className={activePage === page.id ? "active" : ""}
              data-testid={`workspace-page-${page.id}`}
              onClick={() => onNavigate(page.id)}
              type="button"
            >
              <span className="workspace-page-number">0{index + 1}</span>
              {pageIcon(page.id)}
              <span><strong>{page.label}</strong><small>{page.caption}</small></span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function WorkspacePager({
  activePage,
  onNavigate,
}: {
  activePage: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
}) {
  const activeIndex = workspacePages.findIndex((page) => page.id === activePage);
  const previous = workspacePages[activeIndex - 1];
  const next = workspacePages[activeIndex + 1];
  return (
    <nav className="workspace-pager" aria-label="Incident workspace pagination">
      <button disabled={!previous} onClick={() => previous && onNavigate(previous.id)} type="button">
        <ChevronLeft size={16} />
        <span><small>Previous</small><strong>{previous?.label ?? "Start"}</strong></span>
      </button>
      <div><span>PAGE</span><strong>0{activeIndex + 1} / 04</strong></div>
      <button disabled={!next} onClick={() => next && onNavigate(next.id)} type="button">
        <span><small>Next</small><strong>{next?.label ?? "Complete"}</strong></span>
        <ChevronRight size={16} />
      </button>
    </nav>
  );
}

function IncidentHero({ incident, visual }: { incident: IncidentBrief; visual?: ReactNode }) {
  const top = incident.ranked_candidates[0];
  const score = Math.round((top?.score ?? 0) * 100);
  return (
    <section className={`incident-hero ${visual ? "with-visual" : ""}`}>
      <div className="hero-copy">
        <div className="eyebrow"><span>SLO BURN INVESTIGATION</span> / SIGNAL 01</div>
        <h1 id="overview-title">CHECKOUT DEGRADATION<br />ISOLATED TO <span>{top?.operation ?? "INSUFFICIENT EVIDENCE"}</span></h1>
        <p>{incident.situation}</p>
        <div className="hero-meta">
          <span><Clock3 size={14} /> analyzed {compactTime(incident.completed_at)}</span>
          <span><Layers3 size={14} /> {incident.metrics.analyzed_trace_count} traces</span>
          <span><FileSearch size={14} /> {incident.metrics.evidence_count} evidence records</span>
        </div>
      </div>
      <aside className="incident-console" aria-label="Ranked incident result">
        <div className="console-chrome">
          <span>INCIDENT / INC-{shortId(incident.incident_id)}</span>
          <span className="console-live"><i /> {incident.scenario.startsWith("live-") ? "LIVE ANALYSIS" : "REPLAY ANALYSIS"}</span>
        </div>
        <div className="console-signal">
          <span>UPSTREAM SLO SIGNAL</span>
          <strong>CHECKOUT ERROR RATE</strong>
          <em>SYMPTOM, NOT ROOT CAUSE</em>
        </div>
        <div className="console-divergence">
          <span>FIRST LOCAL DIVERGENCE</span>
          <strong>{top?.operation ?? "SAFE ABSTENTION"}</strong>
          <small>{top?.service ?? "No comparable evidence"} · {top ? `${percent(top.local_attribution)} local attribution` : "No ranked guess"}</small>
        </div>
        <div className="console-grade">
          <div>
            <span>EVIDENCE GRADE</span>
            <strong>{incident.confidence_label}</strong>
          </div>
          <div className="grade-bars" aria-hidden="true">
            {[20, 40, 60, 80, 100].map((threshold) => <i className={score < threshold ? "dim" : ""} key={threshold} />)}
          </div>
          <small>{top ? `${score}% inspectable ranking score` : "insufficient evidence"}</small>
        </div>
      </aside>
      {visual && <div className="hero-visual">{visual}</div>}
    </section>
  );
}

function SectionIntro({
  index,
  eyebrow,
  title,
  description,
  titleId,
}: {
  index: string;
  eyebrow: string;
  title: string;
  description: string;
  titleId?: string;
}) {
  return (
    <div className="section-intro">
      <span className="section-index">{index}</span>
      <div>
        <small>// {eyebrow}</small>
        <h2 id={titleId}>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}

function DecisionTrail({
  incident,
  onNavigate,
}: {
  incident: IncidentBrief;
  onNavigate: (page: WorkspacePage) => void;
}) {
  const steps = buildDecisionTrail(incident);
  return (
    <nav className="decision-trail" aria-label="Incident evidence journey">
      <div className="decision-trail-label">
        <span>Decision trail</span>
        <strong>Follow the claim to its evidence</strong>
      </div>
      <ol>
        {steps.map((step, index) => (
          <li className={`decision-step ${step.state}`} key={step.id}>
            <button onClick={() => onNavigate(step.page)} type="button">
              <span className="decision-index">0{index + 1}</span>
              <div>
                <small>{step.label}</small>
                <strong>{step.value}</strong>
                <p>{step.detail}</p>
              </div>
              <ChevronRight size={17} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ol>
    </nav>
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
    <section className="panel cascade-panel" id="service-cascade">
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
    <section className="panel candidates-panel" id="ranked-hypotheses">
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
    <section className="panel cohort-panel" id="cohort-comparison">
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

function SentinelMeshPanel({ incident }: { incident: IncidentBrief }) {
  const mesh = incident.sentinel_mesh;
  if (!mesh) return null;
  return (
    <section className="panel sentinel-panel" id="sentinel-mesh">
      <PanelHeader
        icon={<RadioTower size={17} />}
        title="Sentinel mesh"
        meta={`${mesh.status.toLowerCase()} · lease generation ${mesh.lease_generation}`}
      />
      {mesh.previous_leader_ids.length > 0 && (
        <div className="failover-strip">
          Leadership moved from {mesh.previous_leader_ids.join(", ")} to {mesh.leader_id}.
        </div>
      )}
      <div className="sentinel-grid">
        {mesh.findings.map((finding) => (
          <article
            className={`sentinel-card ${finding.outcome.toLowerCase()}`}
            key={finding.sentinel_id}
          >
            <div className="sentinel-title">
              <div>
                {finding.role === "LEADER" ? <Crown size={15} /> : <RadioTower size={15} />}
                <strong>{finding.system}</strong>
              </div>
              <span>{finding.role.toLowerCase()}</span>
            </div>
            <p>{finding.summary}</p>
            <div className="sentinel-meta">
              <span>{finding.outcome.toLowerCase()}</span>
              <span>{finding.evidence_ids.length} evidence refs</span>
              {finding.error_code && <span>{finding.error_code}</span>}
            </div>
            {finding.evidence_ids.length > 0 && (
              <div className="sentinel-evidence">
                {finding.evidence_ids.slice(0, 2).map((evidenceId) => {
                  const evidence = incident.evidence.find((item) => item.id === evidenceId);
                  return evidence ? (
                    <a href={evidence.web_url} key={evidenceId} target="_blank" rel="noreferrer">
                      {evidenceId}
                    </a>
                  ) : <span key={evidenceId}>{evidenceId}</span>;
                })}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function EvidencePanel({ incident }: { incident: IncidentBrief }) {
  const top = incident.ranked_candidates[0];
  const relevantIds = new Set([...(top?.supporting_evidence_ids ?? []), ...(top?.contradicting_evidence_ids ?? [])]);
  const evidence = incident.evidence.filter((item) => relevantIds.has(item.id));
  return (
    <section className="panel evidence-panel" id="evidence-ledger">
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
    <section className="panel blast-panel" id="blast-radius">
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
    <section className="panel timeline-panel" id="incident-timeline">
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
    <section className="panel query-panel" id="responder-handoff">
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

function EmptyState({
  isReplayPending,
  isLivePending,
  error,
  onReplay,
  onLive,
}: {
  isReplayPending: boolean;
  isLivePending: boolean;
  error: Error | null;
  onReplay: () => void;
  onLive: () => void;
}) {
  return (
    <div className="empty-shell">
      <div className="empty-brand"><CircleDot size={22} /> RootSpan</div>
      <div className="empty-card">
        <div className="empty-icon"><Sparkles size={28} /></div>
        <span>Evidence-bound incident correlation</span>
        <h1>Find the first broken thing,<br />not the loudest alert.</h1>
        <p>Replay the golden checkout incident to compare healthy and failing trace cohorts, rank the first local divergence, and compile a cited responder handoff.</p>
        <div className="empty-actions">
          <button className="button primary" disabled={isLivePending} onClick={onLive}>
            {isLivePending ? <RefreshCw className="spin" size={17} /> : <Activity size={17} />}
            {isLivePending ? "Collecting SigNoz evidence…" : "Investigate live"}
          </button>
          <button className="button secondary" disabled={isReplayPending} onClick={onReplay}>
            {isReplayPending ? <RefreshCw className="spin" size={17} /> : <Play size={17} />}
            {isReplayPending ? "Analyzing replay…" : "Run golden replay"}
          </button>
        </div>
        {error && <div className="error-message">{error.message}</div>}
      </div>
    </div>
  );
}

export default App;
