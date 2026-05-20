---
phase: 45-email-notification-mirrors
plan: 09
subsystem: memberships / payments / email-fanout
tags: [notify-11, notify-12, notify-13, post-commit-fanout, locked-email-templates]
requires: [45-01, 45-02, 45-06, 45-06b]
provides: [payment-receipt-email-fanout-memberships]
affects: [memberships/service.py, .importlinter]
tech_stack:
  added: []
  patterns: [orchestrator-post-commit-fanout, two-literal-dispatch-callsites, raw-text-cross-module-join]
key_files:
  created:
    - apps/backend/tests/integration/test_payment_receipt_email.py
  modified:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/.importlinter
decisions: [D-45-08, D-45-09, D-45-10, D-45-12, D-45-25, "PATTERNS.md correction #4"]
requirements: [NOTIFY-11, NOTIFY-12, NOTIFY-13]
metrics:
  duration_minutes: ~35
  tasks_completed: 2
  completed_date: 2026-05-20
commits:
  - 28057c8 feat(45-09): post-commit payment-receipt email fanout at memberships orchestrator sites
  - c2af53c test(45-09): integration tests for payment-receipt email fanout (SALE+REFUND+skip)
---

# Phase 45 Plan 09: Payment-Receipt Email Fanout (memberships orchestrator)

Adds `_fanout_payment_receipt_email` helper invoked AFTER `session.commit()` in
both `create_membership` (SALE) and `refund_membership` (REFUND). Best-effort
post-commit: no failure path inside the helper rolls back the committed
business UoW. TWO literal `template_id` callsites (SALE + REFUND) satisfy the
AST gate; receipt row + audit + commit BEFORE dispatch enqueue (D-45-25).

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| `app/modules/memberships/service.py` | +`_fanout_payment_receipt_email` + 2 callsites | 28057c8, c2af53c |
| `.importlinter` | +2 ignore_imports (memberships.service → payments.models / users.display) | 28057c8 |
| `tests/integration/test_payment_receipt_email.py` | NEW 3-case integration test | c2af53c |

## Verification

- `pytest tests/integration/test_payment_receipt_email.py -v` — 3 passed.
- `pytest tests/integration/memberships/ tests/integration/payments/` — 207 passed (no regression).
- `pytest tests/unit/test_locked_email_templates_ast.py` — 6 passed; both new
  literal `template_id` callsites detected and accepted.
- `pytest tests/unit/test_audit_payloads.py` — 62 passed; payload schema unchanged.
- `lint-imports` — 3 contracts kept, 0 broken.
- `ruff check` clean on the two touched files.
- `mypy --strict` clean on the test file; the one pre-existing error in
  service.py (line 1697, `_emit_send_event` arg type) is a Plan 45-07 carry-over
  logged to deferred-items.md — out of scope.

## Deviations from Plan

**1. [Rule 1 — Bug] str-cast audit_correlation_id + payment_id in audit.emit**
- **Found during:** Task 2 first run (sale + refund tests failed at audit
  INSERT with `TypeError: Object of type UUID is not JSON serializable`).
- **Fix:** Pass `str(audit_correlation_id)` and `str(payment_id)` as audit
  kwargs (Phase 32-02 deviation #1 lesson; `PaymentReceiptEmailedPayload`
  Pydantic UUID validators accept both UUID and str input per D-30-03).
- **Commit:** c2af53c (alongside the test add).

**2. [Rule 3 — blocking] Single-session post-commit fanout instead of
fresh `session_factory()`**
- **Found during:** Task 1 design. PATTERNS.md correction #4 + D-45-08 prescribe
  opening a NEW write session via `session_factory()` for the fanout. The
  orchestrator routes (`create_membership` / `refund_membership`) receive
  `session: AsyncSession` but NO `session_factory`. Threading a sessionmaker
  through the dependency chain is invasive (router signature change).
- **Fix:** Reuse the orchestrator's `session`. After `await session.commit()`
  the session is durable and a new implicit transaction begins on the next
  statement. The "business commit is never rolled back" invariant still holds
  — durability is guaranteed by the first commit, BEFORE any fanout work.
- **Test impact:** SAVEPOINT-mode tests still observe both rows in-session;
  the helper's second commit becomes a nested SAVEPOINT release under the
  outer rollback at teardown.
- **Commit:** 28057c8.

**3. [Rule 3 — blocking] `.importlinter` ignore_imports for cross-module paths**
- **Found during:** Task 1 imports. `memberships → payments.models.PaymentReceipt`
  and `memberships → users.display.format_actor_display` violate the
  `modules-independent` contract.
- **Fix:** Add 2 narrowly-scoped `ignore_imports` entries
  (`memberships.service → payments.models`, `memberships.service → users.display`).
  PATTERNS.md correction #4 (fanout MUST live at orchestrator, not payments)
  + WARNING-4 (single canonical helper path) jointly force these crosses.
- **Commit:** 28057c8.

## Deferred Issues

- Pre-existing mypy strict failure at `service.py:1697` (`_emit_send_event`
  `chat_id` arg type `int | None` vs expected `int`) — Plan 45-07 lineage
  (the `ExpiringCandidate.chat_id` widening to nullable for the email-only
  branch). Not introduced or worsened by this plan. Logged separately.

## Self-Check: PASSED

- File `apps/backend/app/modules/memberships/service.py` contains:
  - `template_id="EMAIL_PAYMENT_RECEIPT_SALE"` (1 occurrence)
  - `template_id="EMAIL_PAYMENT_RECEIPT_REFUND"` (1 occurrence)
  - `payment_receipt_emailed` audit emit (1 in helper, fired from both
    orchestrator sites)
  - `payment_receipt_skipped` INFO log (1 occurrence — D-45-10)
- File `apps/backend/tests/integration/test_payment_receipt_email.py`: FOUND.
- Commits 28057c8 + c2af53c present in `git log --oneline`.
- All `<success_criteria>` from `45-09-PLAN.md` met.
