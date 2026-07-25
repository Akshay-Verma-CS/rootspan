import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bot,
  Boxes,
  Braces,
  Check,
  ChevronRight,
  CircleDot,
  ExternalLink,
  FileCode2,
  Github,
  GitPullRequestArrow,
  Network,
  RadioTower,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  TimerReset,
  UserRoundCheck,
  X,
  Zap,
} from "lucide-react";
import { marked } from "marked";
import {
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  architectureStages,
  documentBySlug,
  documents,
  type ProjectDocument,
  searchDocuments,
} from "./content";

const repositoryUrl = "https://github.com/Akshay-Verma-CS/rootspan";

type MermaidApi = (typeof import("mermaid"))["default"];

let mermaidApiPromise: Promise<MermaidApi> | undefined;

function loadMermaid(): Promise<MermaidApi> {
  mermaidApiPromise ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      suppressErrorRendering: true,
      theme: "base",
      fontFamily: "SFMono-Regular, Cascadia Code, Roboto Mono, Consolas, monospace",
      themeVariables: {
        darkMode: true,
        background: "#07111a",
        primaryColor: "#0c2430",
        primaryTextColor: "#edfaff",
        primaryBorderColor: "#25f6e6",
        secondaryColor: "#25152a",
        secondaryTextColor: "#edfaff",
        secondaryBorderColor: "#ff3ca6",
        tertiaryColor: "#262817",
        tertiaryTextColor: "#edfaff",
        tertiaryBorderColor: "#f5f03d",
        lineColor: "#25f6e6",
        textColor: "#edfaff",
        mainBkg: "#0c2430",
        nodeBorder: "#25f6e6",
        clusterBkg: "#09131d",
        clusterBorder: "#3b5664",
        edgeLabelBackground: "#07111a",
        fontSize: "14px",
      },
      flowchart: {
        htmlLabels: true,
        useMaxWidth: true,
        curve: "basis",
      },
      themeCSS: `
        .nodeLabel, .edgeLabel { font-weight: 700; }
        .edgeLabel { color: #edfaff; }
        .labelBkg { background: #07111a; }
      `,
    });
    return mermaid;
  });
  return mermaidApiPromise;
}

const sourceSlugMap: Readonly<Record<string, string>> = {
  "README.md": "overview",
  "PROJECT_STRATEGY.md": "strategy",
  "STACK_AND_ARCHITECTURE.md": "architecture",
  "DECISIONS.md": "decisions",
  "EXECUTION_PLAN.md": "execution",
  "DEMO_PLAN.md": "demo",
  "ENGINEERING_STANDARDS.md": "standards",
  "DEVELOPMENT_WORKFLOW.md": "workflow",
  "AGENTS.md": "agent-guide",
};

function slugFromHash(): string | null {
  const match = window.location.hash.match(/^#\/?docs\/([a-z-]+)$/);
  return match?.[1] ?? null;
}

function openDocument(slug: string): void {
  window.location.hash = `/docs/${slug}`;
}

function scrollToSection(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="section-label">
      <span aria-hidden="true">//</span>
      {children}
    </div>
  );
}

function BrandMark() {
  return (
    <span className="brand" aria-label="RootSpan home">
      <span className="brand-mark" aria-hidden="true">
        R<span>S</span>
      </span>
      <span className="brand-word">
        ROOT<span>SPAN</span>
      </span>
    </span>
  );
}

function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);

  const navigate = (id: string) => {
    setMenuOpen(false);
    scrollToSection(id);
  };

  return (
    <header className="site-header">
      <a className="brand-link" href="#top" aria-label="RootSpan home">
        <BrandMark />
      </a>
      <nav className={menuOpen ? "site-nav is-open" : "site-nav"} aria-label="Primary navigation">
        <button type="button" onClick={() => navigate("system")}>System</button>
        <button type="button" onClick={() => navigate("sentinels")}>Sentinels</button>
        <button type="button" onClick={() => navigate("protocol")}>Protocol</button>
        <button type="button" onClick={() => navigate("docs")}>Docs</button>
      </nav>
      <a className="header-github" href={repositoryUrl} target="_blank" rel="noreferrer">
        <Github size={16} aria-hidden="true" />
        <span>Source</span>
        <ExternalLink size={13} aria-hidden="true" />
      </a>
      <button
        className="menu-toggle"
        type="button"
        aria-label={menuOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? <X aria-hidden="true" /> : <Braces aria-hidden="true" />}
      </button>
    </header>
  );
}

function StatusRibbon() {
  return (
    <div className="status-ribbon" aria-label="Current project capabilities">
      <div className="status-track">
        <span><CircleDot /> SENTINEL MESH: READY</span>
        <span><Activity /> CORRELATION: DETERMINISTIC</span>
        <span><ShieldCheck /> RUNTIME ACCESS: READ ONLY</span>
        <span><GitPullRequestArrow /> HUMAN AUTHORITY: REQUIRED</span>
        <span aria-hidden="true"><CircleDot /> SENTINEL MESH: READY</span>
        <span aria-hidden="true"><Activity /> CORRELATION: DETERMINISTIC</span>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-copy">
        <div className="hero-kicker"><span>INCIDENT INTELLIGENCE</span> / SIGNAL 01</div>
        <h1 data-text="FIND THE FIRST BROKEN THING.">
          FIND THE FIRST<br />
          <span>BROKEN THING.</span>
        </h1>
        <p className="hero-lede">
          RootSpan coordinates read-only system sentinels, compares healthy and failing telemetry,
          and ranks the earliest local divergence before the error cascade hides it.
        </p>
        <div className="hero-actions">
          <button className="cyber-button primary" type="button" onClick={() => scrollToSection("system")}>
            Explore the system <ArrowRight size={17} aria-hidden="true" />
          </button>
          <button className="cyber-button ghost" type="button" onClick={() => openDocument("overview")}>
            <BookOpen size={17} aria-hidden="true" /> Read the docs
          </button>
        </div>
        <div className="hero-proof" aria-label="Product guarantees">
          <span><Check /> Evidence-linked</span>
          <span><Check /> Model-optional</span>
          <span><Check /> Human-controlled</span>
        </div>
      </div>

      <div className="hero-console" aria-label="Simulated RootSpan incident console">
        <div className="console-chrome">
          <span>INCIDENT / RS-042</span>
          <span className="live-indicator"><i /> LIVE ANALYSIS</span>
        </div>
        <div className="console-grid" aria-hidden="true" />
        <div className="console-content">
          <div className="console-alert">
            <span>SLO SIGNAL</span>
            <strong>CHECKOUT ERROR RATE</strong>
            <em>UPSTREAM SYMPTOM DETECTED</em>
          </div>
          <div className="console-path" aria-label="Service investigation path">
            <div><i className="node ok" /><span>gateway</span><small>propagated</small></div>
            <div><i className="node ok" /><span>checkout</span><small>propagated</small></div>
            <div className="active"><i className="node fault" /><span>inventory.reserve</span><small>first divergence</small></div>
            <div><i className="node muted" /><span>database</span><small>observed</small></div>
          </div>
          <div className="console-score">
            <div>
              <span>EVIDENCE GRADE</span>
              <strong>A</strong>
            </div>
            <div className="score-bars">
              <i /><i /><i /><i /><i className="dim" />
            </div>
            <small>12 supporting / 1 contradicting</small>
          </div>
          <div className="console-footer">
            <span><RadioTower size={14} /> 4 SENTINELS ONLINE</span>
            <span>T+ 03.2s</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricStrip() {
  const metrics = [
    { value: "04", label: "system sentinels", icon: Bot },
    { value: "01", label: "local divergence", icon: Zap },
    { value: "100%", label: "claims with provenance", icon: ShieldCheck },
    { value: "00", label: "production writes", icon: UserRoundCheck },
  ];

  return (
    <section className="metric-strip" aria-label="RootSpan product metrics">
      {metrics.map(({ value, label, icon: Icon }) => (
        <div className="metric" key={label}>
          <Icon aria-hidden="true" />
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
    </section>
  );
}

function SystemArchitecture() {
  return (
    <section className="section system-section" id="system">
      <div className="section-heading split-heading">
        <div>
          <SectionLabel>System architecture</SectionLabel>
          <h2>From loud signal<br />to local truth.</h2>
        </div>
        <p>
          The pipeline stays deterministic where trust matters. Agents observe. The correlation core
          scores. Evidence remains inspectable. A human decides what happens next.
        </p>
      </div>

      <div className="architecture-flow">
        {architectureStages.map((stage, index) => (
          <div className={`architecture-stage tone-${stage.tone}`} key={stage.id}>
            <div className="stage-number">{stage.index}</div>
            <div className="stage-icon" aria-hidden="true">
              {index === 0 && <Activity />}
              {index === 1 && <Network />}
              {index === 2 && <Braces />}
              {index === 3 && <UserRoundCheck />}
            </div>
            <h3>{stage.label}</h3>
            <p>{stage.detail}</p>
            <span className="stage-state"><i /> {index === 3 ? "AWAITING HUMAN" : "VERIFIED"}</span>
            {index < architectureStages.length - 1 && (
              <span className="stage-connector" aria-hidden="true"><ChevronRight /></span>
            )}
          </div>
        ))}
      </div>

      <div className="system-boundary">
        <div className="boundary-title">
          <span>TRUST BOUNDARY</span>
          <strong>Deterministic core</strong>
        </div>
        <div className="boundary-items">
          <span><Check /> Cohort construction</span>
          <span><Check /> Trace alignment</span>
          <span><Check /> Divergence scoring</span>
          <span><Check /> Evidence provenance</span>
          <span><Check /> Abstention</span>
        </div>
        <div className="boundary-model">
          <Sparkles aria-hidden="true" />
          <span>MODEL ZONE</span>
          <strong>Explain verified evidence only</strong>
        </div>
      </div>
    </section>
  );
}

const sentinels = [
  { id: "01", name: "Gateway", role: "LEADER", detail: "Owns the active incident lease and compiles bounded findings.", tone: "yellow" },
  { id: "02", name: "Checkout", role: "FOLLOWER", detail: "Separates propagated checkout symptoms from local behavior.", tone: "cyan" },
  { id: "03", name: "Inventory", role: "FOLLOWER", detail: "Corroborates trace divergence with logs, metrics, and changes.", tone: "magenta" },
  { id: "04", name: "Database", role: "FOLLOWER", detail: "Checks the downstream boundary for comparable cohort behavior.", tone: "cyan" },
] as const;

function SentinelMesh() {
  return (
    <section className="section sentinels-section" id="sentinels">
      <div className="sentinel-backdrop" aria-hidden="true">SENTINEL</div>
      <div className="section-heading">
        <SectionLabel>Distributed observation</SectionLabel>
        <h2>One leader.<br /><span>Zero split-brain.</span></h2>
        <p>
          Each incident gets a stable SQLite lease. Followers observe their attached systems in
          parallel. If the leader fails, generation advances and a healthy follower takes control.
        </p>
      </div>

      <div className="sentinel-grid">
        {sentinels.map((sentinel, index) => (
          <article className={`sentinel-card tone-${sentinel.tone}`} key={sentinel.id}>
            <div className="sentinel-topline">
              <span>NODE / {sentinel.id}</span>
              <i className="pulse-dot" />
            </div>
            <div className="sentinel-glyph" aria-hidden="true">
              {index === 0 ? <RadioTower /> : index === 2 ? <Boxes /> : <Bot />}
            </div>
            <div className="sentinel-role">{sentinel.role}</div>
            <h3>{sentinel.name}</h3>
            <p>{sentinel.detail}</p>
            <div className="sentinel-status">
              <span>STATE</span><strong>READY</strong>
            </div>
          </article>
        ))}
      </div>

      <div className="failover-sequence">
        <div className="failover-title"><TimerReset /> LEADER FAILOVER PROTOCOL</div>
        <div className="failover-steps">
          <span><i>1</i> detect failed leader</span>
          <ArrowRight aria-hidden="true" />
          <span><i>2</i> preserve findings</span>
          <ArrowRight aria-hidden="true" />
          <span><i>3</i> advance generation</span>
          <ArrowRight aria-hidden="true" />
          <span><i>4</i> elect healthy follower</span>
        </div>
      </div>
    </section>
  );
}

function EvidenceProtocol() {
  const layers = [
    {
      index: "A",
      title: "Compare",
      icon: GitPullRequestArrow,
      text: "Match healthy and failing traces by route, topology, region, and safe dimensions.",
      tags: ["cohort coverage", "exclusions", "baseline"],
    },
    {
      index: "B",
      title: "Corroborate",
      icon: Boxes,
      text: "Require independent traces, logs, metrics, topology, or change-event support.",
      tags: ["support", "contradictions", "query hash"],
    },
    {
      index: "C",
      title: "Hand off",
      icon: UserRoundCheck,
      text: "Show blast radius, exact queries, competing hypotheses, and the owning runbook.",
      tags: ["deep links", "next query", "human decision"],
    },
  ];

  return (
    <section className="section protocol-section" id="protocol">
      <div className="section-heading split-heading">
        <div>
          <SectionLabel>Evidence protocol</SectionLabel>
          <h2>No evidence.<br /><span>No guess.</span></h2>
        </div>
        <div className="insufficient-card">
          <span>SAFE FAILURE MODE</span>
          <strong>INSUFFICIENT_EVIDENCE</strong>
          <p>Incomparable cohorts trigger abstention—not synthetic certainty.</p>
        </div>
      </div>

      <div className="protocol-grid">
        {layers.map(({ index, title, icon: Icon, text, tags }) => (
          <article className="protocol-card" key={index}>
            <span className="protocol-index">{index}</span>
            <Icon aria-hidden="true" />
            <h3>{title}</h3>
            <p>{text}</p>
            <div className="protocol-tags">
              {tags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>
          </article>
        ))}
      </div>

      <div className="code-window">
        <div className="code-window-bar">
          <span><Terminal /> INCIDENT BRIEF / EVIDENCE CONTRACT</span>
          <span>JSON</span>
        </div>
        <pre><code>{`{
  "first_divergence": "inventory.reserve",
  "evidence_grade": "A",
  "supporting_evidence": 12,
  "contradicting_evidence": 1,
  "coverage": { "healthy": 10, "failing": 10 },
  "authority": "human_responder"
}`}</code></pre>
        <div className="code-annotation">
          <FileCode2 aria-hidden="true" />
          Every factual claim resolves to a stored evidence ID, typed query, response hash, and SigNoz deep link.
        </div>
      </div>
    </section>
  );
}

function DocsExplorer() {
  const [query, setQuery] = useState("");
  const visibleDocuments = useMemo(() => searchDocuments(query), [query]);

  return (
    <section className="section docs-section" id="docs">
      <div className="section-heading docs-heading">
        <div>
          <SectionLabel>Knowledge base</SectionLabel>
          <h2>Read the<br /><span>source of truth.</span></h2>
        </div>
        <label className="docs-search">
          <Search aria-hidden="true" />
          <span className="sr-only">Search project documentation</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search architecture, evidence, deployment…"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} aria-label="Clear search"><X /></button>
          )}
        </label>
      </div>

      <div className="docs-count">
        <span>{String(visibleDocuments.length).padStart(2, "0")} FILES INDEXED</span>
        <span>BUILT DIRECTLY FROM REPOSITORY MARKDOWN</span>
      </div>

      {visibleDocuments.length > 0 ? (
        <div className="docs-grid">
          {visibleDocuments.map((document, index) => (
            <button
              className="doc-card"
              type="button"
              key={document.slug}
              onClick={() => openDocument(document.slug)}
            >
              <span className="doc-card-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="doc-category">{document.category}</span>
              <BookOpen className="doc-icon" aria-hidden="true" />
              <small>{document.label}</small>
              <strong>{document.title}</strong>
              <p>{document.description}</p>
              <span className="doc-meta">{document.readingMinutes} MIN READ <ArrowRight /></span>
            </button>
          ))}
        </div>
      ) : (
        <div className="docs-empty">
          <Search aria-hidden="true" />
          <strong>NO SIGNAL FOUND</strong>
          <p>Try a broader term such as “sentinel”, “evidence”, or “deployment”.</p>
          <button type="button" onClick={() => setQuery("")}>Reset query</button>
        </div>
      )}
    </section>
  );
}

function FinalCallout() {
  return (
    <section className="final-callout">
      <div className="callout-noise" aria-hidden="true" />
      <div>
        <SectionLabel>Operational doctrine</SectionLabel>
        <h2>Evidence before action.<br /><span>Always.</span></h2>
      </div>
      <p>
        RootSpan accelerates investigation without taking production authority away from the people
        accountable for it.
      </p>
      <a className="cyber-button primary" href={repositoryUrl} target="_blank" rel="noreferrer">
        View on GitHub <Github size={17} aria-hidden="true" />
      </a>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <BrandMark />
      <p>Built for Agents of SigNoz // AI & Agent Observability</p>
      <div>
        <button type="button" onClick={() => openDocument("architecture")}>Architecture</button>
        <button type="button" onClick={() => openDocument("decisions")}>Decisions</button>
        <a href={repositoryUrl} target="_blank" rel="noreferrer">GitHub</a>
      </div>
    </footer>
  );
}

function MarkdownDocument({ document: projectDocument }: { document: ProjectDocument }) {
  const articleRef = useRef<HTMLElement>(null);
  const renderedMarkdown = useMemo(
    () => marked.parse(projectDocument.markdown, { gfm: true }) as string,
    [projectDocument.markdown],
  );

  useEffect(() => {
    let cancelled = false;

    const renderDiagrams = async () => {
      const mermaid = await loadMermaid();
      const article = articleRef.current;
      if (cancelled || !article) {
        return;
      }

      const codeBlocks = Array.from(
        article.querySelectorAll<HTMLElement>("pre > code.language-mermaid"),
      );
      if (codeBlocks.length === 0) {
        return;
      }

      const sources = codeBlocks.map((code) => code.textContent ?? "");
      const nodes = codeBlocks.map((code, index) => {
        const frame = document.createElement("figure");
        frame.className = "mermaid-diagram";

        const diagram = document.createElement("div");
        diagram.className = "mermaid";
        diagram.textContent = sources[index];
        diagram.setAttribute("role", "img");
        diagram.setAttribute("aria-label", `${projectDocument.title} diagram ${index + 1}`);

        frame.append(diagram);
        code.parentElement?.replaceWith(frame);
        return diagram;
      });

      try {
        await mermaid.run({ nodes });
      } catch {
        nodes.forEach((node, index) => {
          const frame = node.parentElement;
          if (!frame) {
            return;
          }

          const label = document.createElement("div");
          label.className = "mermaid-error-label";
          label.textContent = "Diagram unavailable — showing its source";

          const pre = document.createElement("pre");
          const code = document.createElement("code");
          code.className = "language-mermaid";
          code.textContent = sources[index];
          pre.append(code);
          frame.replaceChildren(label, pre);
          frame.classList.add("has-error");
        });
      }
    };

    void renderDiagrams();
    return () => {
      cancelled = true;
    };
  }, [projectDocument.title, renderedMarkdown]);

  const handleMarkdownClick = (event: ReactMouseEvent<HTMLElement>) => {
    const anchor = (event.target as HTMLElement).closest("a");
    const href = anchor?.getAttribute("href");
    if (!href || href.startsWith("http") || href.startsWith("#")) {
      return;
    }

    const fileName = href.split("/").at(-1);
    const slug = fileName ? sourceSlugMap[fileName] : undefined;
    if (slug) {
      event.preventDefault();
      openDocument(slug);
    }
  };

  return (
    <article
      ref={articleRef}
      className="markdown-body"
      onClick={handleMarkdownClick}
      dangerouslySetInnerHTML={{ __html: renderedMarkdown }}
    />
  );
}

function DocumentReader({ document: projectDocument }: { document: ProjectDocument }) {
  useEffect(() => {
    document.title = `${projectDocument.title} // RootSpan`;
    window.scrollTo({ top: 0, behavior: "auto" });
    return () => {
      document.title = "RootSpan // Evidence before action";
    };
  }, [projectDocument.title]);

  return (
    <div className="reader-shell">
      <header className="reader-header">
        <a className="brand-link" href="#top" onClick={() => { window.location.hash = "#top"; }}>
          <BrandMark />
        </a>
        <span className="reader-signal"><i /> DOCUMENT SIGNAL / VERIFIED</span>
        <a href={`${repositoryUrl}/blob/main/${projectDocument.sourcePath}`} target="_blank" rel="noreferrer">
          View source <ExternalLink />
        </a>
      </header>
      <div className="reader-layout">
        <aside className="reader-sidebar">
          <button className="reader-back" type="button" onClick={() => { window.location.hash = "#docs"; }}>
            <ArrowLeft /> Back to system
          </button>
          <div className="reader-sidebar-label">DOCUMENT INDEX</div>
          <nav aria-label="Project documents">
            {documents.map((item, index) => (
              <button
                className={item.slug === projectDocument.slug ? "active" : ""}
                type="button"
                key={item.slug}
                onClick={() => openDocument(item.slug)}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                {item.title}
              </button>
            ))}
          </nav>
        </aside>
        <main className="reader-main" id="main-content">
          <div className="reader-meta">
            <span>{projectDocument.category}</span>
            <span>{projectDocument.readingMinutes} MIN READ</span>
            <span>{projectDocument.sourcePath}</span>
          </div>
          <MarkdownDocument document={projectDocument} />
          <div className="reader-end">
            <span>END OF TRANSMISSION</span>
            <button type="button" onClick={() => { window.location.hash = "#docs"; }}>
              Browse all documents <ArrowRight />
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

function LandingPage() {
  useEffect(() => {
    const target = window.location.hash.replace("#", "");
    if (target && !target.startsWith("/docs/")) {
      window.requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView());
    }
  }, []);

  return (
    <div className="site-shell">
      <SiteHeader />
      <StatusRibbon />
      <main id="main-content">
        <Hero />
        <MetricStrip />
        <SystemArchitecture />
        <SentinelMesh />
        <EvidenceProtocol />
        <DocsExplorer />
        <FinalCallout />
      </main>
      <SiteFooter />
    </div>
  );
}

export default function App() {
  const [activeSlug, setActiveSlug] = useState<string | null>(() => slugFromHash());

  useEffect(() => {
    const onHashChange = () => setActiveSlug(slugFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const activeDocument = activeSlug ? documentBySlug(activeSlug) : undefined;
  if (activeDocument) {
    return <DocumentReader document={activeDocument} />;
  }

  return <LandingPage />;
}
