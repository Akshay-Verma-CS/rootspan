# RootSpan

> Pre-event planning notes only. Implementation begins when Agents of SigNoz opens on July 20, 2026.

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

Planning documents:

- [Project strategy](docs/PROJECT_STRATEGY.md)
- [Selected stack and architecture](docs/STACK_AND_ARCHITECTURE.md)
- [Seven-day build plan](docs/EXECUTION_PLAN.md)
- [Demo and judging plan](docs/DEMO_PLAN.md)
- [Decision record](docs/DECISIONS.md)

Hackathon alignment:

- Target track: **AI & Agent Observability**
- SigNoz roles: SLO alerts, MCP investigation, Query Builder, correlated signals, dashboards, and agent telemetry
- Required deployment: Foundry with `casting.yaml` and `casting.yaml.lock`
- AI assistance will be declared in the submission

Official references: [overview and judging criteria](https://www.wemakedevs.org/hackathons/signoz), [rules](https://www.wemakedevs.org/hackathons/signoz/rules), and [resources](https://www.wemakedevs.org/hackathons/signoz/resources).
