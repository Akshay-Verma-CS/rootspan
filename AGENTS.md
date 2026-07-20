# RootSpan agent guide

This file is the operating contract for coding agents and contributors working in this repository. Keep it short, current, and more actionable than the longer planning documents.

## Mission

Build a read-only incident-correlation product that compares healthy and failing telemetry cohorts, ranks the first local divergence, shows supporting and contradicting evidence, and hands the decision to a human responder.

The deterministic correlation pipeline is the product. An LLM may explain verified evidence, but it must not create evidence, own scoring, or perform remediation.

## Read before changing code

Read only the documents relevant to the task, in this order:

1. `README.md` for the product boundary.
2. `docs/PROJECT_STRATEGY.md` for product behavior and scope.
3. `docs/STACK_AND_ARCHITECTURE.md` for component boundaries and contracts.
4. `docs/EXECUTION_PLAN.md` for priority and current build order.
5. `docs/DECISIONS.md` before revisiting an accepted architectural choice.
6. `docs/ENGINEERING_STANDARDS.md` and `docs/DEVELOPMENT_WORKFLOW.md` before implementation.

If documents conflict, accepted decisions and architecture win over examples or older plan text. Update the conflicting document in the same change.

## Repository boundaries

The application layout is:

```text
apps/rootspan-console/  React console and production Nginx image
src/rootspan/api/       versioned HTTP boundary
src/rootspan/domain/    strict shared contracts
src/rootspan/correlation/ deterministic ranking core
src/rootspan/fixtures/  versioned replay scenarios
src/rootspan/lab/       role-configured services, traffic, and smoke checks
src/rootspan/storage/   SQLite persistence
ops/                    RootSpan collector configuration
tests/                  unit, functional, API, and persistence tests
docs/                   plans, standards, and decisions
```

`signoz/` is an upstream source checkout used for reference. Do not edit, format, vendor, or commit it as part of RootSpan unless a task explicitly requires an upstream SigNoz change.

Do not hand-edit generated files or lockfiles. Change their source or dependency declaration, then regenerate them with the owning tool.

## Non-negotiable invariants

- Runtime telemetry access is read-only. Bootstrap credentials are separate from runtime credentials.
- The core depends on `TelemetryGateway` and domain contracts, never raw MCP or HTTP payloads.
- Fixture, MCP, and direct-API gateways return the same domain types.
- Every factual claim and ranked candidate references stored evidence and query provenance.
- Supporting evidence, contradictions, exclusions, and coverage remain visible.
- Insufficient or incomparable evidence produces `INSUFFICIENT_EVIDENCE`; it does not produce a guess.
- Correlation and replay remain usable without an LLM or live SigNoz connection.
- Incident state transitions are persisted before the next stage starts.
- Times are timezone-aware UTC internally; durations use explicit units.
- Secrets, customer payloads, and unbounded high-cardinality attributes never enter fixtures, logs, or Git.

## Implementation loop

For each task:

1. Restate the observable outcome and smallest acceptance test.
2. Inspect the owning contracts and tests before editing.
3. Implement the smallest vertical slice through a real boundary.
4. Add or update tests for success, failure, and insufficient-evidence behavior.
5. Run the narrowest relevant checks, then the repository quality gate.
6. Review the diff for scope, secrets, generated noise, and evidence provenance.
7. Update documentation only when behavior, commands, contracts, or decisions changed.

Prefer extending an existing module over adding a new abstraction. Add a dependency only when the standard library and selected stack cannot meet a measured requirement.

## Expected quality commands

Use the repository `Makefile` as the stable interface once it exists:

```sh
make test
make lint
make typecheck
make verify
make live-verify
```

While bootstrapping, use the owning tool directly:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
pnpm test
pnpm exec tsc --noEmit
pnpm exec playwright test
```

Do not claim a command passed if its manifest, toolchain, service, or dependency was unavailable. Report what ran and what remains unverified.

## Change discipline

- Preserve unrelated user changes and keep diffs task-scoped.
- Never use bulk staging without reviewing `git status` and `git diff` first.
- Avoid speculative frameworks, services, queues, and databases.
- Use explicit typed contracts at process and network boundaries.
- Use structured errors and logs; do not swallow exceptions or log secrets.
- Instrument meaningful stage and external-call boundaries, not every helper.
- Record a new decision in `docs/DECISIONS.md` when changing an accepted architecture, security boundary, or product invariant.

## Definition of done

A change is done when its acceptance behavior works, relevant automated checks pass, failure behavior is explicit, telemetry is appropriate, documentation is accurate, and the diff contains no unrelated or generated noise. For demo-path changes, replay mode and the live path must not drift.
