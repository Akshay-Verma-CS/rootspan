# RootSpan

> Implementation began on July 20, 2026, after Agents of SigNoz opened.

**The first broken thing, not the loudest alert.**

RootSpan is a human-in-the-loop incident correlation engine for SigNoz. When an SLO alert fires, it compares failing requests with equivalent healthy requests and identifies the earliest shared telemetry divergence before errors cascade through the service graph.

It gives the responder a decision-ready incident brief:

- the first divergent operation, with confidence and contradicting evidence;
- side-by-side healthy and failing trace cohorts;
- new or sharply increased log fingerprints;
- metric changes and temporally related deployment/configuration events;
- blast radius across routes, versions, regions, and customer cohorts;
- exact SigNoz queries and trace IDs behind every claim;
- suggested next investigation steps and the owning runbook/team.

RootSpan does **not** modify code or infrastructure. It reduces time to investigate and resolve while the human retains operational authority.

## Implemented product slice

The current build includes:

- a deterministic, attribution-aware healthy/failing trace-cohort analyzer;
- a strict evidence model with supporting and contradicting signals, blast radius, timeline, and next queries;
- fixture and live MCP gateways returning the same strict telemetry contracts;
- bounded MCP trace/log queries plus Query Builder v5 latency and blast-radius aggregation;
- a persisted incident state machine, fingerprint-idempotent SigNoz webhook, and SSE progress feed;
- a versioned FastAPI replay/live API with SQLite persistence;
- a responsive React responder console served by Nginx;
- a three-service OpenTelemetry incident lab with a scoped, resettable inventory timeout;
- a local collector bridge that exports lab traces, logs, metrics, and RootSpan stage spans into SigNoz;
- idempotent bootstrap of a Viewer-only runtime key, webhook channel, error-rate alert, and incident dashboard;
- fixture, API, gateway, persistence, webhook, incident-lab, frontend, Compose, and live-SigNoz checks.

The optional LLM narrator is intentionally not on the critical path. Ranking, abstention, evidence, replay, and live correlation remain deterministic and usable without a model.

## Quickstart

RootSpan uses a project-managed Python 3.13 environment through `uv`.

```sh
uv sync
make frontend-sync
make verify
```

Provision SigNoz and MCP from the committed Foundry casting, then start the complete application:

```sh
export PATH="$HOME/.local/bin:$PATH"
foundryctl gauge
foundryctl forge
foundryctl cast
make bootstrap-signoz
make app-up
make live-verify
```

`make bootstrap-signoz` stores ignored owner-only bootstrap/runtime files, gives the runtime service account only `signoz-viewer`, and provisions the RootSpan dashboard, checkout error-rate alert, and webhook channel. It is safe to rerun and never prints credentials.

`make live-verify` proves replay and live MCP correlation through the production proxy, ordered SQLite state transitions, trace/log/change/topology evidence plus a quantitative latency comparison, reset recovery, three-service propagation, custom metric ingestion, and RootSpan's own stage spans. The failure switch is reset even if an assertion fails.

Running endpoints:

| Component | URL |
| --- | --- |
| RootSpan console | `http://localhost:5173` |
| RootSpan API/OpenAPI | `http://localhost:8001/docs` |
| Gateway lab role | `http://localhost:9001/health` |
| Checkout lab role | `http://localhost:9002/health` |
| Inventory lab role | `http://localhost:9003/health` |
| SigNoz | `http://localhost:8080` |
| SigNoz MCP health | `http://localhost:8000/livez` |
| Manual live investigation | `POST http://localhost:8001/api/v1/incidents/live` |
| SigNoz alert webhook | `POST http://localhost:8001/api/v1/webhooks/signoz` |
| Incident progress | `GET /api/v1/incidents/{id}/events` or `/events/stream` |

Useful commands:

```sh
make healthy       # ten successful baseline requests
make incident      # enable the scoped fault and send ten failing requests
make reset         # disable only the demo fault
make live-smoke    # replay + baseline + incident + recovery assertions
make telemetry-check
make test-webhook  # after app-up; sends a real SigNoz test notification
make app-down      # stop RootSpan; keep its SQLite volume
```

## Failure-testing boundary

The incident lab uses deterministic fault injection: one scoped inventory timeout, a bounded traffic cohort, an explicit reset, and a recovery assertion. This makes the demo reproducible and safe. It is not presented as a chaos-engineering platform; randomized experiments, steady-state hypotheses, abort policies, and experiment scheduling are outside the current slice.

Current limits are deliberate: the bootstrap creates a trace-based checkout error-rate threshold alert rather than a formal multi-window SLO burn alert, live correlation covers one seeded timeout scenario, automatic restart/resume is not implemented, and the optional LLM narrator and direct-HTTP SigNoz fallback remain excluded from the critical path.

Generated Foundry output under `pours/` is intentionally ignored; `casting.yaml` and `casting.yaml.lock` are the reproducible inputs.

Project documents:

- [Project strategy](docs/PROJECT_STRATEGY.md)
- [Selected stack and architecture](docs/STACK_AND_ARCHITECTURE.md)
- [Seven-day build plan](docs/EXECUTION_PLAN.md)
- [Demo and judging plan](docs/DEMO_PLAN.md)
- [Decision record](docs/DECISIONS.md)
- [Engineering standards](docs/ENGINEERING_STANDARDS.md)
- [Development workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [Coding-agent operating guide](AGENTS.md)

Hackathon alignment:

- Target track: **AI & Agent Observability**
- SigNoz roles: SLO alerts, MCP investigation, Query Builder, correlated signals, dashboards, and agent telemetry
- Required deployment: Foundry with `casting.yaml` and `casting.yaml.lock`
- AI assistance will be declared in the submission

Official references: [overview and judging criteria](https://www.wemakedevs.org/hackathons/signoz), [rules](https://www.wemakedevs.org/hackathons/signoz/rules), and [resources](https://www.wemakedevs.org/hackathons/signoz/resources).
