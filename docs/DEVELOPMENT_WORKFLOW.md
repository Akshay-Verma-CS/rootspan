# RootSpan development workflow

This workflow keeps the hackathon implementation fast without sacrificing reproducibility. Work in small vertical slices that leave the demo path healthier after every merge.

## 1. Select the next outcome

Take work from `EXECUTION_PLAN.md` in priority order. Define a small task contract before editing:

```text
Outcome: observable behavior that will exist
Acceptance: automated or repeatable proof
Scope: components and files expected to change
Non-goals: tempting work intentionally deferred
Risks: data, security, compatibility, or demo concerns
```

A task should normally fit one focused session. Split it if it crosses unrelated architecture boundaries or cannot be verified independently.

## 2. Establish a known starting point

- Read `AGENTS.md` and only the task-relevant architecture sections.
- Check `git status`; preserve unrelated and uncommitted work.
- Reproduce a bug or run the closest existing test before changing behavior.
- Confirm required services and toolchains. Do not debug application code when the actual problem is an unavailable dependency.
- For algorithm work, start with a minimal fixture containing the expected result and contradiction.

## 3. Build a thin vertical slice

Prefer an end-to-end slice over completing every layer horizontally. A typical slice is:

```text
fixture or webhook
  -> validated domain contract
  -> one pipeline behavior
  -> persisted evidence/state
  -> API response
  -> minimal UI or replay assertion
```

Start with contracts and an acceptance test. Implement the deterministic path before polish or model narration. Keep live adapters replaceable by fixtures from the first useful version.

## 4. Use a tight verification loop

Run checks from narrowest to broadest:

1. The edited unit or component test.
2. The owning package test suite.
3. Formatter, linter, and type checker for the changed language.
4. Cross-package contract or replay tests.
5. `make verify` once the repository command exists.

Live SigNoz, Docker, browser, and model checks are valuable but slower. Run them when the changed boundary requires them and before declaring the corresponding milestone complete.

When a check cannot run, record the exact command, reason, and remaining risk. Do not silently substitute code inspection for execution.

## 5. Review before committing

Inspect `git diff` and answer:

- Does the change meet the stated acceptance behavior?
- Is any logic duplicated or abstraction premature?
- Are external inputs validated and calls bounded by timeouts, pagination, and concurrency?
- Are errors explicit and useful without leaking sensitive data?
- Does every new claim preserve evidence provenance and contradictions?
- Is insufficient evidence handled without guessing?
- Are telemetry names and attributes stable and low-cardinality?
- Are tests deterministic and meaningful rather than implementation-coupled?
- Did generated files, secrets, recordings, local databases, or unrelated formatting enter the diff?
- Do docs and commands still match reality?

## 6. Commit and integrate

Use small, reviewable commits that leave the repository runnable. Prefer Conventional Commit subjects:

```text
feat(cohorts): match healthy traces by route and region
fix(alignment): exclude overlapping child time once
test(gateway): share telemetry contract cases
docs(workflow): define live verification gate
chore(deps): pin MCP SDK v1
```

Use short-lived branches such as `feat/cohort-selection` for risky or parallel work. Direct commits to `main` are acceptable for a solo sprint only when the change is small, reviewed, and green.

Before pushing:

```sh
git status --short
git diff --check
git diff --cached
```

Stage explicit paths. Do not include `signoz/`, local `.env` files, databases, telemetry captures, build output, or editor/system files.

## 7. Validate milestone exits

Each execution-plan day has an exit test. Treat it as an acceptance gate, not an aspiration.

- Save the exact command or scenario used.
- Capture structured results needed for evaluation.
- Record known limitations and follow-up tasks.
- Keep replay fixtures for important live results.
- Confirm a clean start or clone can reproduce the behavior when deployment files change.

Do not start optional model work until the deterministic fixture path can compile an evidence-linked brief. Do not spend polish time while the golden incident is unreliable.

## Fast triage when blocked

Classify the problem before changing code:

| Class | First action |
| --- | --- |
| Environment | Verify versions, daemon/service health, ports, and credentials. |
| Contract | Capture the smallest sanitized payload and compare it with the domain schema. |
| Algorithm | Reduce to a deterministic fixture and inspect component scores. |
| Integration | Trace one request across the boundary and verify propagation/configuration. |
| Flaky test | Remove time, ordering, randomness, or shared-state dependence; do not add blind retries. |
| Scope | Re-check the priority list and cut optional behavior. |

Escalate a blocked decision only after gathering the smallest useful evidence: observed behavior, expected behavior, exact command, relevant error, and attempted safe alternatives.

## Daily closeout

At the end of a work block:

1. Leave the working tree understandable and report any intentional uncommitted work.
2. Record what passes and what has not been run.
3. Update the execution plan only for meaningful status or scope changes.
4. Note the next smallest outcome and its acceptance test.
5. Ensure the golden demo path still has a known-good replay or live checkpoint.

The workflow is successful when another contributor can resume from Git and the documentation without reconstructing hidden context.
