# RootSpan seven-day execution plan

Implementation starts on July 20, 2026, in line with the hackathon rules.

## Pre-event readiness

- Keep all work to planning notes and diagrams.
- Follow the selected Python + React stack and component boundaries in `STACK_AND_ARCHITECTURE.md`.
- Lock the golden incident, cohort dimensions, and expected first divergence.
- Confirm model provider, but ensure core correlation works without an LLM.
- Confirm Docker Desktop has at least 4 GB available and its daemon is running.
- Decide team roles and AI-assistance disclosure.

Current local preflight on July 20:

- Docker CLI and daemon `29.4.3` are running.
- Foundry CLI `0.2.14` is installed; `casting.yaml` and its generated lock enable SigNoz MCP.
- SigNoz is healthy, and SigNoz MCP passes both `/livez` and `/readyz`.
- Known Foundry `0.2.14` issue: its generated MCP Docker healthcheck invokes `wget`, which is absent from the current MCP image, so Docker labels the otherwise-ready container unhealthy. Fix or override the generated probe before the final clean-clone demo.
- The current Foundry OpAMP default can replace the committed ingester pipelines with `nop` receivers before organization onboarding. `compose.yaml` therefore runs a RootSpan-owned collector bridge against the same SigNoz telemetry store; `make live-verify` checks the stored traces and metrics directly.
- `uv` `0.11.29` manages CPython `3.13.14` and the checked-in dependency lock.
- Node `26.0.0`, npm `11.12.1`, and pnpm `11.9.0` are available.
- System Python remains `3.9.6`; project commands must run through `uv`.

Current implementation checkpoint:

- Days 1–5 have a working vertical demo slice: deterministic lab, live traces/metrics, replay cohorts, attribution-aware ranking, evidence/contradiction ledger, blast radius, SQLite API, and responder console.
- Alert/MCP-driven live evidence collection and optional narration remain the next slices; replay deliberately does not pretend that those adapters already exist.

## Day 1 — SigNoz and telemetry spine

- Create the event-time repository structure.
- Install Foundry and commit `casting.yaml` plus `casting.yaml.lock` with MCP enabled.
- Bring up the minimal service path and traffic generator.
- Emit correlated traces, structured logs, RED metrics, and comparison dimensions.
- Verify exact evidence queries in SigNoz Query Builder and MCP.

**Exit test:** a clean environment can generate one request and click from its log to the full trace in SigNoz.

## Day 2 — reproducible incident and SLO detection

- Implement the gateway/checkout/inventory path at minimum viable depth.
- Add the scoped `inventory-v2` timeout injector and reset control.
- Generate healthy traffic followed by a failing region/flag cohort.
- Configure SLO/error-budget dashboard and alert.
- Persist seeded ground truth for later evaluation.

**Exit test:** the alert reliably fires upstream while the seeded first divergence remains downstream at `inventory.reserve`.

## Day 3 — cohort selection and trace alignment

- Query failing traces around the alert window.
- Select comparable healthy traces by route and dimensions.
- Normalize spans and construct service/operation trees.
- Align the healthy/failing paths.
- Implement coverage and “insufficient baseline” checks.

**Exit test:** RootSpan can show several aligned trace pairs and identify candidate divergence nodes without an LLM.

## Day 4 — cross-signal ranking

- Score candidate operations by prevalence, rarity, magnitude, precedence, and topology.
- Fingerprint logs and compare template frequencies.
- Compare RED metrics and relevant business counters.
- Ingest deployment/flag events from telemetry.
- Record supporting and contradicting evidence with stable IDs.

**Exit test:** `inventory.reserve` ranks first for explainable, inspectable reasons across repeated runs.

## Day 5 — blast radius and human brief

- Calculate affected request and error-budget shares.
- Segment by region, version, flag, route, and safe customer dimensions.
- Compile machine-readable incident brief.
- Add exact next queries, owner/runbook metadata, and SigNoz deep links.
- Build the single-screen responder UI.

**Exit test:** a responder can determine where the divergence begins, who is affected, and what to inspect next without reading terminal output.

## Day 6 — agent layer and observability

- Add a bounded read-only agent for query planning and evidence explanation.
- Enforce evidence citations and show contradictions.
- Instrument RootSpan’s MCP, algorithm, and model steps with OpenTelemetry.
- Build agent-performance and incident-correlation dashboards.
- Add replay fixtures and the low-confidence/abstention path if stable.

**Exit test:** every factual statement in the brief maps to stored query evidence, and the investigation itself is traceable in SigNoz.

## Day 7 — evaluation and presentation

- Freeze features early.
- Run seeded incidents repeatedly and record ranking accuracy/latency.
- Perform a timed manual investigation for a fair query/time comparison.
- Reproduce from a clean clone using Foundry artifacts.
- Finish README, architecture, limitations, AI disclosure, screenshots, and blog.
- Rehearse and record the four-minute demo.

**Exit test:** five consecutive demos produce the same first-divergence result and a complete evidence packet.

## Current repository structure

```text
.
├── Dockerfile
├── compose.yaml
├── casting.yaml
├── casting.yaml.lock
├── apps/
│   └── rootspan-console/
├── ops/
│   └── rootspan-collector.yaml
├── src/rootspan/
│   ├── api/
│   ├── correlation/
│   ├── domain/
│   ├── fixtures/
│   ├── lab/
│   └── storage/
├── tests/
└── docs/
```

## Priority order under time pressure

1. Correlated SigNoz telemetry.
2. Deterministic incident.
3. Healthy/failing cohort selection.
4. First-divergence algorithm.
5. Evidence-linked result.
6. Blast radius.
7. Polished UI.
8. Model explanation.

If time slips, remove the model before removing cohort comparison or evidence provenance. The algorithm is the product; AI is the interface and investigator.

## Risks

| Risk | Mitigation |
| --- | --- |
| Trace trees vary too much to align | Control the golden service graph first; canonicalize operations and ignore volatile attributes. |
| Healthy baseline is not comparable | Match key dimensions, report coverage, and abstain when coverage is weak. |
| “Root cause” claim overreaches | Say first divergence/ranked hypothesis and expose contradiction evidence. |
| MCP/query latency hurts the demo | Bound queries, cache evidence for an incident, and provide labeled replay fixtures. |
| Project looks like another summary bot | Lead the demo with cohort trace alignment and deterministic ranking before showing any prose. |
| UI duplicates SigNoz | Deep-link raw data to SigNoz; keep RootSpan focused on comparisons and the human handoff. |
| Scope expands into remediation | Maintain read-only tool permissions and explicit non-goals. |

## Definition of done

A judge can inject a scoped failure, watch a SigNoz SLO alert fire on an upstream symptom, and then see RootSpan locate the first downstream divergence across trace cohorts, corroborate it with other signals, quantify the blast radius, and hand a human every piece of evidence needed for the next decision.
