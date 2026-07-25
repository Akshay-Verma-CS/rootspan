# RootSpan demo and presentation plan

## Four-minute demo

### 0:00–0:25 — establish the problem

“Alerts show where pain surfaces, not necessarily where failure begins. During an incident, humans lose time comparing dashboards, traces, and logs before they can make the first useful decision.”

Show the healthy SigNoz SLO dashboard.

### 0:25–0:50 — create a misleading incident

Enable the scoped `inventory-v2` timeout. The checkout/gateway SLO begins burning and a SigNoz alert opens the RootSpan incident.

Make the scope visible but do not reveal it verbally yet.

### 0:50–1:50 — show the first divergence

RootSpan elects the gateway sentinel as incident leader and shows its checkout, inventory, and database followers observing their attached scopes. Then it displays matched healthy and failing trace cohorts. Upstream gateway/checkout spans show propagated symptoms. The first shared behavioral split is highlighted at `inventory.reserve`.

Show the transparent ranking factors:

- percentage of failing traces containing the divergence;
- rarity in matched healthy traces;
- latency/error magnitude;
- temporal position before upstream failures;
- cross-signal support and contradictions.

Open one representative trace in SigNoz.

### 1:50–2:35 — corroborate instead of hallucinating

The evidence panel shows:

- newly frequent inventory timeout log fingerprint;
- inventory p95 change against baseline;
- flag/version event shortly before SLO burn;
- unaffected cohorts as boundary/contradicting evidence;
- exact Query Builder or MCP evidence reference for every claim.

Explain that deterministic code computed the evidence and the model only summarized it.

### 2:35–3:15 — quantify blast radius

Reveal that the failure affects only the `inventory-v2` flag cohort in one region. Show affected requests as both counts and percentages, plus error-budget burn.

This converts “checkout is down” into an actionable operational boundary.

### 3:15–3:45 — hand control to the human

Open the incident brief:

- situation and impact;
- first-divergence hypothesis with confidence;
- supporting and contradicting evidence;
- exact next queries;
- owner and relevant runbook;
- links back to SigNoz.

Export/copy the brief. Do not recommend or execute a production change in the demo.

### 3:45–4:00 — close

“RootSpan does not replace the responder. It removes the searching and comparison work between the alert and the human’s first correct decision.”

## Visual hierarchy

The main screen should prioritize three visuals:

1. service cascade with first divergence highlighted;
2. healthy-versus-failing trace cohort comparison;
3. evidence/blast-radius incident brief.

Avoid a chatbot-first layout. A text box would make the project look generic before judges see the differentiated engineering.

## SigNoz panels to show

- SLO/error-budget burn and alert state;
- healthy versus incident error rate and p95;
- affected traffic by flag/region/version;
- RootSpan stage latency: query, cohort, alignment, correlation, explanation;
- MCP/model calls, failures, token cost, and evidence coverage.

## Evaluation story

After implementation, collect rather than invent these numbers:

- median alert-to-brief time across repeated seeded runs;
- correct first-divergence ranking rate;
- cohort coverage;
- number of manual SigNoz interactions needed with and without RootSpan;
- percentage of brief claims linked to raw evidence;
- low-confidence/abstention behavior.

Use “reduced investigation time in our controlled incident” rather than making an unproven production SLA claim.

## Demo resilience

- Seed deterministic healthy and failing traffic.
- Keep representative trace IDs ready.
- Cache one completed incident as a clearly labeled replay fallback.
- Pre-open exact SigNoz dashboard, query, alert, and trace URLs.
- Warm the stack and reset the incident before presenting.
- Run the golden path five times before recording.

## Evidence to capture for the README and blog

- first successful correlated log-to-trace navigation;
- a bad baseline comparison and how cohort matching fixed it;
- trace tree alignment visualization;
- transparent ranking breakdown;
- contradicting evidence or abstention case;
- blast-radius counts and denominators;
- RootSpan’s own investigation trace in SigNoz;
- the Sentinel Mesh leader, follower outcomes, and `sentinel.observe` spans;
- timed manual versus RootSpan-assisted investigation;
- limitations discovered during real implementation.

## Likely judge questions

**How is this different from an AI log summarizer?**
The core output comes from deterministic cohort selection, trace-tree alignment, divergence ranking, cross-signal calculations, and evidence provenance. The model is not asked to guess root cause from a prompt full of logs.

**Why compare cohorts instead of one healthy and one failing trace?**
Individual traces contain noise and unrelated variation. A repeated divergence across matched failing traces, rare in matched healthy traces, is stronger and gives measurable coverage/confidence.

**Why not remediate automatically?**
The product targets the expensive investigation gap while preserving enterprise change controls. It can hand off to existing runbooks and incident processes without requiring write access to production.

**Why use SigNoz deeply?**
SigNoz detects the SLO impact, stores every evidence signal, exposes query/MCP access, provides raw-data verification and deep links, and observes RootSpan’s own investigation pipeline.

**Are the sentinels just multiple LLMs voting?**
No. They are autonomous read-only observers with system-scoped capabilities and deterministic lease-based coordination. Their findings reference telemetry evidence; the correlation engine owns scoring. A generative planner can be added behind the same bounded contracts, but model consensus never substitutes for evidence.

**Does “first divergence” prove root cause?**
No. RootSpan explicitly presents a ranked hypothesis with coverage, confidence, boundaries, and contradicting evidence. It helps a human reach the correct decision faster without disguising uncertainty.
