# Decision record

## DR-001 — Human-in-the-loop investigation over autonomous remediation

**Date:** July 18, 2026
**Status:** Accepted before implementation

### Context

Autonomous SRE remediation is an obvious hackathon direction and likely to be crowded. More importantly, many companies will not grant a probabilistic agent code or infrastructure write access during an incident. A polished remediation demo would therefore spend significant effort defending a trust model that weakens adoption.

### Decision

Build a read-only incident correlation product that minimizes investigation time and gives the responder evidence for the next decision. Do not execute code, deployment, or infrastructure changes.

### Consequences

- Product value is measured through MTTI/MTTR reduction and evidence quality, not number of automated actions.
- Human authority becomes a product strength rather than a missing automation feature.
- The technical investment moves to cohort selection, trace alignment, cross-signal ranking, blast-radius analysis, and evidence provenance.
- RootSpan can integrate with existing runbooks and incident-management systems later without owning remediation.

## DR-002 — First-divergence correlation over generic incident summarization

**Date:** July 18, 2026
**Status:** Accepted before implementation

### Context

Change timelines, alert summaries, log clustering, and conversational observability already exist as product patterns. A generic combination would be useful but not sufficiently distinctive for the hackathon.

### Decision

Make cohort-based first-divergence analysis the core: compare matched healthy and failing traces, find the earliest operation whose behavior repeatedly separates, and require corroboration from logs, metrics, topology, or change events.

### Consequences

- The demo has a visual and technically inspectable centerpiece.
- The core can work without an LLM, improving determinism and credibility.
- The system must expose coverage, competing candidates, and contradictions rather than overclaiming root cause.
- Scope remains one excellent seeded incident before additional scenarios.

## DR-003 — Python product core, Go incident lab, TypeScript console

**Date:** July 18, 2026
**Status:** Superseded by DR-006 on July 20, 2026

### Context

RootSpan needs fast iteration on structured MCP responses, statistical comparisons, evidence schemas, and an optional model layer. Its incident lab needs predictable concurrent services with strong OpenTelemetry instrumentation. A single-language choice optimizes repository simplicity but not the two different workloads.

### Decision

Build the RootSpan modular monolith in Python, the observable incident lab in Go, and only the browser console in TypeScript/React. Use SQLite rather than an external application database.

### Consequences

- Python keeps correlation and evidence work concise and testable.
- Go demonstrates a realistic, typed, polyglot OTel target system.
- The project has two backend toolchains, but the boundary is simple: the lab emits telemetry and RootSpan reads it from SigNoz.
- No additional runtime language will be introduced during the sprint.

The sprint-speed estimate in DR-006 supersedes this choice before incident-lab implementation begins.

## DR-004 — Programmatic SigNoz MCP access without an LLM in the data path

**Date:** July 18, 2026
**Status:** Accepted before implementation

### Context

The SigNoz MCP server exposes structured tools for trace search/detail, logs, aggregations, metrics, alerts, dashboards, Query Builder v5, and SigNoz UI deep links. Passing every correlation query through a model would add latency, nondeterminism, and unverifiable query selection.

### Decision

RootSpan will act as a normal MCP client and invoke SigNoz tools deterministically. The core depends on a `TelemetryGateway` protocol with MCP, direct v5 API, and fixture implementations. The optional model can propose bounded read-only follow-up queries but does not own cohort construction or scoring.

### Consequences

- SigNoz MCP remains central to the project and visible in RootSpan's traces.
- Correlation can run and be tested without a model.
- The stable MCP Python SDK v1 line will be pinned because v2 remains prerelease during the hackathon dates.
- Direct Query Builder v5 access remains a fallback/contract oracle rather than a second unstructured data path.

## DR-005 — Modular monolith over distributed RootSpan services

**Date:** July 18, 2026
**Status:** Accepted before implementation

### Context

The processing stages have clear boundaries, but deploying each as a service would add queues, failure modes, configuration, and tracing work without improving a bounded hackathon workload.

### Decision

Keep alert ingestion, orchestration, SigNoz access, cohorting, alignment, correlation, blast-radius analysis, and brief compilation in one Python process with explicit modules and a persisted state machine. Stream progress to the UI with SSE.

### Consequences

- Fewer containers and a more reliable clean-clone demo.
- Stage boundaries remain visible through domain interfaces and OpenTelemetry spans.
- SQLite persistence and leases are sufficient for the bounded workload; automatic restart/resume remains future work, and no Celery, Redis, Kafka, or Temporal is required.

## DR-006 — Python incident lab over a separate Go toolchain

**Date:** July 20, 2026
**Status:** Accepted

### Context

The selected hybrid design used Python for RootSpan and Go for the observable incident lab. A back-of-the-envelope estimate put the Python-lab implementation at approximately 48 hours and the Go-lab implementation at approximately 55 hours for one contributor. The extra time comes from duplicate service scaffolding, OpenTelemetry configuration, testing, container builds, and context switching. The incident lab is a controlled demonstration target, not the shipped correlation engine.

### Decision

Use Python 3.13 for both the RootSpan modular monolith and the role-configured incident-lab processes. Keep React/TypeScript for the responder console. Run gateway, checkout, inventory, and traffic generation as separate Compose processes so trace propagation and service boundaries remain real.

### Consequences

- One backend environment, lockfile, configuration system, test runner, and OTel helper layer reduce delivery time and integration risk.
- The lab remains distributed at runtime even though it shares an implementation language.
- Structured JSON logs go through the Collector; traces and metrics use OTLP.
- The project gives up a small polyglot demonstration benefit in exchange for approximately seven hours of expected demo and reliability work.
- Go is not introduced unless a measured Python limitation blocks the golden incident.

## DR-007 — Application-owned OTLP bridge for reproducible Foundry ingestion

**Date:** July 20, 2026
**Status:** Accepted for the local hackathon deployment

### Context

Foundry `0.2.14` generated the intended SigNoz ingester configuration, but the current OpAMP server applied a pre-onboarding default containing `nop` receivers and exporters. The ingester container stayed up while ports 4317/4318 refused connections. Relying on manual organization onboarding or mutating the generated container would make a clean demo nondeterministic.

### Decision

Run a small `rootspan-collector` service from the application Compose file. It accepts OTLP from RootSpan and the lab, then uses SigNoz's native ClickHouse trace, metric, and metadata exporters against the Foundry telemetry store over `signoz-network`.

### Consequences

- A clean application start has a deterministic telemetry ingestion path independent of OpAMP onboarding state.
- SigNoz remains the telemetry backend, query surface, and demo UI.
- `make telemetry-check` verifies three-service trace propagation, the expected failing cohort, and custom metrics in SigNoz storage.
- The bridge is local-deployment scaffolding, not a second product data store, and can be removed when a clean Foundry cast exposes active OTLP pipelines reliably.

## DR-008 — Incident-scoped Sentinel Mesh with deterministic leadership

**Date:** July 26, 2026
**Status:** Accepted

### Context

A single investigator can become a bottleneck when an incident crosses multiple attached systems. Deploying an unbounded swarm of model-driven agents would add cost, correlated hallucinations, split-brain risk, and new operational dependencies. RootSpan still needs a credible agent-native workflow without weakening its evidence and human-authority invariants.

### Decision

Run a logical Sentinel Mesh inside the existing modular monolith. Each live incident elects one leader through an atomic SQLite lease and delegates bounded read-only observations to gateway, checkout, inventory, and database sentinels. Followers execute concurrently, return typed findings and evidence references, and never score or remediate. Failed leaders transfer coordination to a healthy follower by advancing the lease generation; failed followers remain visible as degraded results.

The initial sentinel policy is deterministic and autonomous. A future model planner may select among the same schema-limited capabilities, but leader election, evidence existence, scoring, abstention, and production authority remain deterministic.

### Consequences

- The project gains an observable multi-agent workflow without adding deployed services, a queue, or a model dependency.
- Sentinel leadership and failover are reproducible, persisted, and testable without wall-clock sleeps or external systems.
- One failing observer does not erase healthy findings; total mesh failure stops the investigation safely.
- SigNoz receives stable spans for election, delegation, observation, and failover.
- The console can show which systems were observed, which sentinel led, and whether coverage degraded.
