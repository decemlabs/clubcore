---
status: partial
phase: 59-recurring-schedule-time-off
source: [59-VERIFICATION.md]
started: 2026-05-25T00:00:00Z
updated: 2026-05-25T00:00:00Z
---

## Current Test

[awaiting human decision on item 2]

## Tests

### 1. Full integration test suite on live Postgres + Redis
expected: All Phase 59 integration + unit tests pass with 0 failures (`uv run pytest tests/integration/schedule/ tests/unit/workers/test_worker_settings.py tests/unit/test_audit_taxonomy.py -v`).
result: passed — orchestrator ran the full backend suite during the regression gate: **2161 passed, 6 skipped, 0 failed**. All Phase 59 schedule integration tests, the worker-settings count gate (cron_jobs 8→9, functions 11→12), and the audit-taxonomy count gate (93) are green.

### 2. WR-06 product decision — PT session credit on owner force-cancel
expected: A confirmed business rule for whether `POST /time-off?force=true` (and the sibling `cancel_slot` booked-cascade) should restore a client's `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking.
result: pending — current behavior does NOT restore the session credit (the client loses a prepaid session). This is a PRE-EXISTING behavior shared with `cancel_slot` (not introduced by Phase 59) and is outside the REC-01..04 scope. It is documented in code at `apps/backend/app/modules/schedule/service.py` (force-cascade callsite, `# NOTE WR-06`). If sessions must be restored, add a cross-module `UPDATE pt_packages SET sessions_remaining = sessions_remaining + 1` (raw `sa.text()` per D-38-11) inside the force-cascade UoW and adjust the audit; otherwise the NOTE comment stands as the documentation. Recommend a dedicated follow-up phase (applies to both code paths) rather than an in-scope Phase 59 change.

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

None blocking the phase goal. Item 1 is satisfied (full suite green). Item 2 is a non-blocking product decision on pre-existing behavior outside REC-01..04 scope.
