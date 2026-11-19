# Application Response

**Prompt:** *"Share a link to something you've built, such as a GitHub repo, project write-up, or
hackathon entry. A small AI agent you've built tells us more than coursework."*

---

I built OpenClaw, a personal AI agent system that turns natural-language requests into
tool-using, scheduled, and auditable workflows. It includes a daily stock observer and a generic
game-market monitor, both designed around structured data, deterministic identifiers,
validation, and safe failure. I also set up Hermes as a peer engineering agent that helps
investigate failures and verify repairs.

OpenClaw is not a trading system. It never places orders, and its stock discoveries are labeled
as research candidates. Building it taught me lessons that apply directly to API-driven
financial infrastructure.

**Idempotency and data correctness.** Every observation gets a SHA-256 ID computed from
normalized fields, so a rerun cannot create duplicate records or repeat an alert. In onboarding
or funding flows, the same property is what stops a retried request from creating a second
account or a second transfer.

**Validation before state changes.** One real failure I investigated with Hermes came from
classification running before every record had a valid ID. The system refused to mark the run
complete. The fix was to validate IDs at the boundary and enforce that invariant with tests,
the same discipline that keeps trading and account state consistent.

**Auditability and failure recovery.** Each run records its state transitions and writes a
completion record only after validation passes. A failed run is marked as failed instead of
partly succeeding, so it can be diagnosed and safely rerun.

**Safe handling of external actions.** Delivery runs last and only after validation. The model
saying "done" is never treated as proof.

The public repository is a sanitized showcase with simulated data, tests, and a sanitized
incident report.
