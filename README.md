# OpenClaw Agent System

> **Sanitized showcase.** This repository is a public, privacy-safe write-up inspired by
> OpenClaw, a personal AI agent system I built and run privately. It is **not** the complete
> private system. Private configuration, prompts, credentials, infrastructure details, and real
> data have been left out on purpose. All code in `demo/` and all reports in `examples/` use
> **fictional, simulated data**.

I built OpenClaw, a personal AI agent system that turns natural-language requests into
tool-using, scheduled, and auditable workflows. It includes a daily stock observer and a generic
game-market monitor, both designed around structured data, deterministic identifiers,
validation, and safe failure. I also set up Hermes as a peer engineering agent that helps
investigate failures and verify repairs.

It also runs a daily internship search that finds, filters, and tracks roles across many
sources. It never applies to anything or contacts anyone.

---

## 1. What OpenClaw is

OpenClaw is a personal AI agent system. A request like *"summarize how my watchlist moved
today"* or *"tell me if this item gets listed below its recent low"* is routed to the right
tools and workflow instead of being answered from the model's memory alone.

The agent can use:

- **Memory and context**: preferences, watchlists, and prior results carried across runs
- **Browser automation**: read-only collection from web pages
- **Shell tools**: local scripts for data processing and checks
- **Scheduled jobs**: recurring workflows run by scheduled jobs in my OpenClaw environment
- **Messaging**: delivery of finished reports back to me

The main design rule is that **a plausible model response does not count as success.** A
workflow is only done when it has produced validated structured state, a report, and (where it
applies) a completion record.

## 2. Main capabilities

| Capability | What it means in practice |
|---|---|
| Tool use | Requests are mapped to registered tools (browser, shell, data fetchers) with explicit inputs and outputs |
| Memory and context | Durable context such as watchlists, thresholds, and previous lows informs each run |
| Scheduled workflows | Recurring jobs run without a manual prompt and archive what they produce |
| Structured reports | Outputs are JSON and Markdown with fixed fields, not free-form chat |
| Validation and failure handling | Each stage checks its inputs; failed runs are marked failed, not "mostly done" |
| State reconciliation | Records from many sources are merged into one tracked state that survives partial outages |
| Agent-to-agent debugging | **Hermes**, a peer engineering agent that helps debug OpenClaw, investigates failures and proposes fixes |

## 3. Daily stock observer

A scheduled workflow that produces a daily market observation report.

- **Watchlist monitoring**: tracks a personal list of symbols each trading day.
- **Dynamic discovery**: scans broad market universes for companies behaving unusually,
  not just the names I already follow.
- **Signals used**:
  - movement relative to a benchmark index
  - volume compared with the recent average
  - five-day momentum
  - volatility / intraday range
  - recent news headlines for context
- **Structured archive**: every run saves a structured JSON report so results can be compared
  over time and audited later.
- **Freshness checks**: skips non-trading days and refuses to report on stale market data.
- **Research candidates, not recommendations**: discoveries are labeled as candidates for
  further research. The observer **does not execute trades** and has no brokerage access.

See [`examples/sample_stock_report.md`](examples/sample_stock_report.md) for a simulated report.

## 4. Generic game-market monitor

A scheduled workflow that watches an in-game player marketplace for unusually low prices.

- **Read-only browser collection**: reads selected market channels through a browser. It never
  posts, replies, or sends messages.
- **Explicit filters**: item, direction (buy vs. sell), and currency must all match the
  configuration.
- **Deterministic IDs**: each observation gets a SHA-256 ID computed from normalized fields,
  so the same listing seen on two scans gets the same ID.
- **Deduplication**: repeated observations are suppressed by ID.
- **New-low detection**: selects the lowest valid observation in a rolling time window and
  compares it with the previous low.
- **Run safety**: locks to prevent overlapping runs, cleanup checks for browser sessions,
  explicit failure state, and completion sentinels written only after a run succeeds.
- **No purchases, no outbound messages**: it observes and reports, nothing more.

A self-contained simulation lives in [`demo/observation_monitor.py`](demo/observation_monitor.py).
See [`examples/sample_game_market_report.md`](examples/sample_game_market_report.md) for a
simulated report.

## 5. Daily internship search

A scheduled workflow that finds internship postings, tracks them over time, and sends me a
daily message listing only what changed.

- **Find and track only**: it never applies, never submits a form, and never contacts a
  company or recruiter. Applying is always a manual decision.
- **Many sources, one row per role**: reads public internship lists and public job-board
  APIs. A posting that appears in several places is matched to one tracked role, first by the
  board's own job ID, then by normalized company and title.
- **Explicit filters with reasons**: roles that clearly don't fit (not an internship, wrong
  location, an eligibility requirement I can't meet, a term that has already ended) are hidden
  with a recorded reason, not silently dropped. Unclear cases stay visible with a warning.
- **Outage-safe closing**: a role is marked closed only after it is missing from a
  *successfully read* source on two scans in a row. A failed or blocked source never closes
  anything.
- **Human-owned fields**: statuses I set by hand (such as Applied or Interviewing) are never
  overwritten by a scan.
- **Verified persistence**: the daily run writes to the tracker, reads everything back, and
  exits with an error if anything didn't save. Failed writes stay queued for the next run.
- **Respects blocks**: sites that refuse scripted requests are left alone and checked by
  hand. The search does not try to get around them.
- **Code collects, the agent researches**: a deterministic scanner does the collecting. The
  agent handles only the judgment-heavy part, such as checking whether an unfamiliar company
  really is a startup.

A simulation of the reconciliation rules lives in
[`demo/internship_tracker.py`](demo/internship_tracker.py). See
[`examples/sample_internship_report.md`](examples/sample_internship_report.md) for a simulated
daily message.

## 6. Hermes: peer engineering agent

Hermes is a separate peer engineering agent that helps debug OpenClaw.

- Investigates OpenClaw workflow failures
- Reviews logs and evidence to find the failing stage
- Produces **sanitized** incident reports (see [`incidents/`](incidents/))
- Suggests the **smallest safe repair** instead of broad rewrites
- Requires verification: a fix counts only after the affected workflow is rerun and passes
- Never exposes credentials, and never changes systems without my authorization

## 7. Engineering lessons

- **Idempotency**: rerunning a workflow on the same inputs must not create duplicate alerts
  or records.
- **Absence is not evidence when a read failed**: state only changes on data that was
  actually read successfully.
- **Clear ownership of fields**: automation owns posting state; the human owns decisions.
- **Deterministic identifiers**: IDs come from normalized content, not from scan order or
  wall-clock time.
- **Validation before persistence**: bad data is rejected at the boundary before it is
  stored or acted on.
- **Safe failure**: if any invariant breaks, the run is marked failed and nothing is delivered.
- **Auditable state transitions**: every run records which stages it passed through.
- **Separation of concerns**: observation, classification, persistence, and delivery are
  separate stages with their own checks.
- **External actions only after validation**: messages go out only after the data behind
  them has been validated.

See [`incidents/observation-id-validation.md`](incidents/observation-id-validation.md) for a
real class of bug (sanitized) that taught several of these lessons.

---

## Repository layout

```
openclaw-agent-system/
├── README.md                  # this file
├── ARCHITECTURE.md            # request and scheduled-workflow architecture
├── SECURITY.md                # what was excluded and why
├── DRIVEWEALTH_APPLICATION.md # application write-up
├── demo/
│   ├── agent_runtime.py           # minimal tool-using workflow runtime (simulated)
│   ├── observation_monitor.py     # game-market monitor simulation (simulated)
│   ├── internship_tracker.py      # internship search reconciliation (simulated)
│   ├── requirements.txt
│   ├── test_observation_monitor.py
│   └── test_internship_tracker.py
├── examples/                  # simulated reports with fictional data
└── incidents/                 # sanitized incident write-ups
```

## Running the demo

Requires Python 3.10+. The demo uses only the standard library.

```bash
cd demo
python observation_monitor.py      # simulated monitor run, prints structured JSON
python agent_runtime.py            # simulated workflow runs: success, safe failure, unrouted
python internship_tracker.py       # simulated four-day tracker run, including a source outage
python -m unittest -v              # run the tests (or: pip install -r requirements.txt && pytest -v)
```

The demo makes no network calls, uses no credentials, sends no real messages, and never
applies to anything.
