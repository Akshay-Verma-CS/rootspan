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

## Implemented MVP

The current build includes:

- a deterministic, attribution-aware healthy/failing trace-cohort analyzer;
- a strict evidence model with supporting and contradicting signals, blast radius, timeline, and next queries;
- a versioned FastAPI replay API with SQLite persistence;
- a responsive React responder console served by Nginx;
- a three-service OpenTelemetry incident lab with a scoped, resettable inventory timeout;
- a local collector bridge that exports lab traces and metrics into Foundry's SigNoz store;
- fixture, API, persistence, incident-lab, frontend, browser, Compose, and live-ingestion checks.

Live SigNoz query/MCP-backed incident collection is the next integration slice. The checked-in replay fixture already uses the same domain contracts and correlation path as that adapter will use.

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
make app-up
make live-verify
```

`make live-verify` proves replay through the production proxy, SQLite persistence, healthy and failing cohorts, reset recovery, three-service trace propagation, error statuses, and custom metric ingestion. The failure switch is reset even if the incident assertion fails.

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

Useful commands:

```sh
make healthy       # ten successful baseline requests
make incident      # enable the scoped fault and send ten failing requests
make reset         # disable only the demo fault
make live-smoke    # replay + baseline + incident + recovery assertions
make telemetry-check
make app-down      # stop RootSpan; keep its SQLite volume
```

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
