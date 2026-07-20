# RootSpan engineering standards

These standards turn the project architecture into reviewable coding rules. Optimize for deterministic behavior, evidence integrity, and a reproducible seven-day build—not theoretical flexibility.

## General design rules

- Keep RootSpan a modular monolith. A package boundary does not require a deployed service.
- Make domain logic pure where practical and isolate I/O behind narrow protocols.
- Pass typed data across boundaries; parse external data once at the edge.
- Prefer composition and plain functions over inheritance and framework hooks.
- Keep modules cohesive. Split when responsibilities or reasons to change differ, not to satisfy an arbitrary line count.
- Make invalid states difficult to construct with enums, constrained values, and validated models.
- Use stable identifiers and deterministic ordering wherever output is persisted, hashed, compared, or shown in a demo.
- Avoid hidden global state. Configuration, clocks, gateways, and model clients must be injectable.

## Domain and evidence integrity

The domain contracts in `STACK_AND_ARCHITECTURE.md` are shared vocabulary for the API, database, fixtures, and tests.

- Preserve raw evidence references separately from derived observations.
- Store query tool, typed arguments, time range, response hash, duration, status, and SigNoz deep link for every external evidence query.
- Never mutate an evidence record after it supports a compiled brief. Add a new version or observation.
- Scores expose their component features and penalties; do not return an unexplained number.
- Use `evidence score` or `evidence grade`, not `probability`, unless the value has been calibrated.
- State cohort size, exclusions, matching dimensions, and usable coverage with each result.
- Treat contradictory evidence as first-class data, not prose appended later.
- Keep fixture schemas versioned and deterministic. Sort unordered collections before serialization.

## Python

Target Python 3.13 and manage the environment with `uv`.

- Type all public functions, protocols, models, and non-obvious local structures.
- Use Pydantic v2 at API, persistence, configuration, and external-data boundaries.
- Keep correlation calculations in framework-independent functions or small domain classes.
- Depend on the `TelemetryGateway` protocol; adapters alone may import MCP/httpx response types.
- Use `async` for real concurrent I/O, not for pure computation. Bound all fan-out with a semaphore or worker limit.
- Set explicit timeouts and bounded retries with jitter for network calls. Retry only operations known to be safe.
- Catch exceptions only when adding context, translating to a domain error, retrying safely, or handling an expected failure.
- Use timezone-aware `datetime` values and explicit nanosecond/millisecond field names.
- Avoid `Any`, mutable default arguments, broad `# type: ignore`, and module-level clients.
- Format and lint with Ruff; use the selected static type checker consistently across the repository.

## Python incident lab

Keep the lab deliberately small and reuse the repository's Python environment and OpenTelemetry helpers.

- Use one role-configured entry point rather than independent service projects.
- Give every inbound and outbound HTTP operation an explicit timeout and propagate trace context.
- Emit structured JSON with trace/span correlation and stable event names.
- Keep failure injection explicit, scoped, deterministic, and resettable.
- Keep scenario state process-local and concurrency-safe. Every background task needs cancellation and a shutdown path.
- Share scenario contracts and configuration without importing RootSpan correlation internals.
- Write parameterized tests for handlers, scenario controls, propagation, and dimension preservation.
- Keep service behavior observable and boring; complexity belongs in the system under investigation only when the scenario needs it.

## TypeScript and React

Use TypeScript strict mode and keep the console focused on one evidence-linked incident screen.

- Generate or share API types from stable schemas where practical; do not maintain silent duplicate contracts.
- Keep server state in TanStack Query and ephemeral view state near the component that owns it.
- Separate data transformation from rendering so candidate ranking and timeline formatting are unit-testable.
- Represent loading, empty, partial, insufficient-evidence, failure, and ready states explicitly.
- Every factual claim in the UI must expose its evidence link or evidence identifier.
- Use semantic HTML, keyboard-operable controls, visible focus, sufficient contrast, and reduced-motion support.
- Avoid unsafe non-null assertions, untyped JSON, and effects that duplicate derived state.
- Keep one Playwright smoke test for the golden path and use component/unit tests for edge cases.

## API and persistence

- Version public routes under `/api/v1` and use consistent error envelopes.
- Validate Alertmanager webhooks before deduplication or persistence.
- Make webhook handling idempotent using the alert fingerprint and event identity.
- Persist the stage transition and its input/output references transactionally before scheduling the next stage.
- Keep migrations additive during the sprint. Back up or recreate only disposable local data.
- Bound pagination, trace counts, response sizes, time windows, and concurrent detail requests.
- Do not expose stack traces, credentials, internal paths, or raw sensitive telemetry to the browser.

## Observability

- Use the span names defined in `PROJECT_STRATEGY.md` for stable pipeline stages.
- Add attributes that help compare incidents, such as stage, gateway implementation, query type, cohort size, evidence grade, and outcome.
- Never attach raw prompts, log bodies, access tokens, full query results, or customer identifiers to spans.
- Metrics need a decision they support. Prefer latency, outcome counts, coverage, query count, evidence count, and ranking consistency.
- Logs are structured events with stable names and identifiers; spans carry causal timing.
- Preserve trace context across HTTP, MCP, background work, and incident-lab calls.

## Testing

Use the cheapest test that proves the behavior:

1. Pure unit and property tests for canonicalization, interval math, alignment, scoring, and aggregation.
2. Contract tests shared by fixture, MCP, and API telemetry gateways.
3. Integration tests for webhook-to-brief state transitions and SQLite recovery.
4. Replay acceptance tests for the golden and insufficient-evidence scenarios.
5. One live SigNoz and one browser smoke path for final verification.

Important invariants include shuffled-span determinism, propagated-parent penalties, explicit baseline failure, valid evidence references, bounded query behavior, idempotent webhook delivery, and stable replay output.

Tests must not depend on wall-clock sleeps, live external services, random seeds, or an LLM unless explicitly marked as live tests. Inject clocks, use seeded generators, and keep replay fixtures local.

## Security and dependency hygiene

- Keep secrets in ignored environment files or a secret store; commit only documented examples.
- Pin direct dependencies and commit the owning lockfiles.
- Review a dependency's maintenance, license, size, and transitive impact before adding it.
- Runtime credentials are read-only. Only bootstrap tooling may create SigNoz resources.
- Redact or hash tenant/customer identifiers in durable evidence and fixtures.
- Treat all webhook fields, telemetry attributes, model output, and MCP results as untrusted input.

## Documentation and review

Update documentation in the same change when commands, contracts, architecture, security boundaries, scenarios, or observable behavior change. Comments should explain why a constraint exists, not narrate syntax.

Review in this order: correctness, evidence integrity, security, failure behavior, test quality, operability, maintainability, and style.
