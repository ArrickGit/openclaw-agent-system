# Architecture

> This describes the general architecture of OpenClaw at a level that is safe to publish.
> Internal tool schemas, prompts, configuration, and infrastructure are left out. The code in
> `demo/` is a simplified, simulated version of these patterns.

## Interactive request flow

```
User request
    ↓
Agent router
    ↓
Tool selection and execution
    ↓
Validation and structured state
    ↓
Persistence / report generation
    ↓
Delivery to the user
```

| Stage | Responsibility |
|---|---|
| Agent router | Turns a natural-language request into a task: which workflow to run and with what parameters |
| Tool selection and execution | Calls registered tools (browser, shell, data fetchers, memory) and captures their structured outputs |
| Validation and structured state | Checks outputs against explicit rules and records each state transition |
| Persistence / report generation | Writes validated data and renders a report from it |
| Delivery to the user | Sends the finished report. This is the only stage that acts outside the system, and it runs last |

## Scheduled workflow flow

Scheduled jobs in my OpenClaw environment (such as the daily stock observer, the
game-market monitor, and the daily internship search) follow the same pattern without a live
user prompt:

```
Scheduled trigger
    ↓
Stock or market data collection
    ↓
Filtering and normalization
    ↓
Deterministic IDs and deduplication
    ↓
Analysis and alert selection
    ↓
Report validation
    ↓
Delivery
```

### Stage notes

- **Scheduled trigger**: takes a per-workflow lock first, so two overlapping runs cannot
  both write state or both send an alert.
- **Data collection**: read-only. The stock observer fetches market data. The game-market
  monitor reads selected market channels through a browser. Browser sessions are cleaned up
  and the cleanup is checked.
- **Filtering and normalization**: whitespace, case, numbers, and timestamps are put into a
  canonical form. Explicit filters (symbols, item, direction, currency, time window) are applied.
- **Deterministic IDs and deduplication**: a SHA-256 ID is computed from normalized fields
  right after normalization. Records without a valid ID are rejected here and never reach later
  stages.
- **Analysis and alert selection**: benchmark-relative moves, volume, momentum, and range for
  stocks; lowest valid price in a rolling window for the market monitor.
- **Report validation**: required fields present, data fresh (for example, not a
  non-trading day), invariants hold.
- **Delivery**: only after validation passes. A completion sentinel is written only after
  delivery succeeds.

## Tracked-state reconciliation (internship search)

The internship search keeps long-lived state rather than producing one-off reports, so it adds
a reconciliation step between collection and delivery:

```
Scheduled trigger
    ↓
Read each source (record ok / failed per source)
    ↓
Filter, with a recorded reason for anything hidden
    ↓
Match to tracked roles: board job ID → normalized company + title
    ↓
Update posting state (new / still open / missed / closed / reopened)
    ↓
Save → read back → compare   (fail the run if anything didn't save)
    ↓
Daily message listing only what changed
```

Rules that keep this state correct:

- **Absence needs proof.** A missed scan counts only when every source that has listed the
  role was read successfully. A role closes after two consecutive misses, so one outage or
  one flaky read never closes anything.
- **Split ownership.** The scanner owns posting state (open/closed). The human owns
  decisions (Applied, Interviewing, and so on). A scan never writes a human-owned field.
- **No external action beyond the report.** The workflow never applies, submits forms, or
  contacts anyone.

## What counts as success

**Model-generated text is not proof of success.** A model can say "Report complete!" while the
data underneath is stale, empty, or malformed. In OpenClaw a workflow counts as successful only
when it has produced:

1. **Validated state**: structured outputs that passed every validator for that workflow
2. **A report**: rendered from that validated state, not written freehand
3. **A completion record** (where appropriate): a sentinel saying the run finished, which
   stage it reached, and what it produced

If any of these is missing, the run is recorded as **failed**, and nothing is delivered.
`demo/agent_runtime.py` shows this. In the second simulated run the model-style summary
claims success, but validation fails on stale data, so the run fails safely and nothing is
delivered.

## Allowed state transitions

```
pending → running → validating → delivering → completed
   │         │           │            │
   └─────────┴───────────┴────────────┴──→ failed
```

Transitions are recorded in order. Any transition not on this diagram raises an error, so a
run cannot skip validation and jump to delivery.

## Hermes in the loop

```
OpenClaw run fails (status = failed, no completion record)
    ↓
Hermes reviews evidence: stage reached, validation errors, state snapshots
    ↓
Sanitized incident report + smallest safe repair proposal
    ↓
Human authorization
    ↓
Repair applied, tests added
    ↓
Affected workflow rerun; fix counts only when the rerun completes
```
