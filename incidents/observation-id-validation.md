# Incident: Alert classification ran before every observation had an ID

> **Sanitized incident report.** Written up with help from Hermes, the peer engineering agent
> that helps debug OpenClaw. Run identifiers, timestamps, usernames, channel names, and raw logs
> are left out on purpose. Any values shown are illustrative.

## Summary

A scheduled game-market monitor run collected data successfully but failed at report
generation. Alert classification was attempted before every observation had a deterministic
ID. The system **correctly refused to mark the run complete**, so no incorrect alert went out.

## Timeline (relative, sanitized)

| Step | Result |
|---|---|
| Lock acquired, browser scan started | ✅ |
| Market channels read (read-only) | ✅ |
| Browser cleanup and cleanup check | ✅ |
| Normalization | ✅ |
| Alert classification / report generation | ❌ failed: one or more observations had no ID |
| Completion sentinel | ⛔ not written (correct behavior) |
| Delivery | ⛔ skipped (correct behavior) |

## Impact

- No incorrect or duplicate alert was delivered.
- No state was marked complete, so the next run was not misled by a false completion record.
- That run produced no report, which was a gap in monitoring until the fix was rerun.

## Root cause

ID generation was coupled to a later stage instead of running right after normalization. Some
observations could therefore reach alert classification without an ID. Classification depends
on IDs for deduplication and for comparing against previously recorded lows, so it could not
safely continue.

The failure-handling design worked as intended: a missing invariant led to a failed run, not a
partly successful one.

## Fix (smallest safe repair)

1. **Generate and validate IDs immediately after normalization**, before deduplication,
   persistence, or alert classification.
2. **Reject** any observation whose ID is missing or invalid at that boundary, with an
   explicit rejection reason in the run's structured result.
3. **Enforce the invariant at the consumer as well:**

   > Every observation entering alert classification must have a non-empty, valid SHA-256 ID.

   Classification raises an invariant error if this is ever violated, and the run fails safely.

Pipeline order after the fix:

```
normalize → assign ID → validate ID → deduplicate → filter → classify → validate report → deliver
```

## Tests added

The simulated equivalents are in `demo/test_observation_monitor.py`:

- `test_classification_rejects_missing_id`: classification refuses an observation with no ID
- `test_classification_rejects_malformed_id`: classification refuses a non-SHA-256 ID
- `test_faulty_id_generator_never_reaches_classification`: if ID generation breaks, observations
  are rejected at the boundary, and no alert is produced
- Deterministic-ID and duplicate-suppression tests, to confirm reruns stay idempotent

## Verification

- Unit tests pass.
- The affected workflow was rerun. It passed every stage, produced a validated report, and wrote
  its completion sentinel.
- The fix counted as done only after the rerun completed, not when the code change was made.

## Lessons

- Assign identifiers at the boundary where the data becomes canonical.
- Check invariants where data enters a stage, not only where it is produced.
- Refusing to complete is the correct result when a run cannot be validated.
- Verification means rerunning the real workflow. A plausible explanation of the fix is not
  enough.
