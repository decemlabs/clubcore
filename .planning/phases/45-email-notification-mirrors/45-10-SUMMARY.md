---
phase: 45-email-notification-mirrors
plan: 10
subsystem: pt_packages / payments / email-fanout
tags: [notify-11, notify-12, notify-13, post-commit-fanout, locked-email-templates]
requires: [45-01, 45-02, 45-06, 45-06b, 45-09]
provides: [payment-receipt-email-fanout-pt-packages]
affects: [pt_packages/service.py, .importlinter]
tech_stack:
  added: []
  patterns: [orchestrator-post-commit-fanout, two-literal-dispatch-callsites, raw-text-cross-module-join]
key_files:
  created:
    - apps/backend/tests/integration/test_payment_receipt_email_pt.py
  modified:
    - apps/backend/app/modules/pt_packages/service.py
    - apps/backend/.importlinter
decisions: [D-45-08, D-45-09, D-45-10, D-45-12, D-45-25, "PATTERNS.md correction #4"]
requirements: [NOTIFY-11, NOTIFY-12, NOTIFY-13]
metrics:
  duration_minutes: ~12
  tasks_completed: 2
  completed_date: 2026-05-20
commits:
  - 43de18b feat(45-10): post-commit payment-receipt email fanout at pt_packages orchestrator sites
  - 0c72165 test(45-10): integration tests for pt-package payment-receipt email fanout (SALE+REFUND+skip)
---

# Phase 45 Plan 10: Payment-Receipt Email Fanout (pt_packages orchestrator)

Mirrors Plan 45-09 memberships byte-for-byte at the pt_packages
orchestrator sites. `_fanout_payment_receipt_email` helper invoked AFTER
`session.commit()` in both `create_pt_package` (SALE) and
`refund_pt_package` (REFUND). Two literal `template_id` callsites
(SALE + REFUND) satisfy the AST gate; receipt row + audit + commit BEFORE
dispatch enqueue (D-45-25). Total orchestrator callsites now 4
(2 memberships + 2 pt_packages) — PATTERNS.md correction #4 honoured.

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| `app/modules/pt_packages/service.py` | +`_fanout_payment_receipt_email` + 2 callsites | 43de18b |
| `.importlinter` | +2 ignore_imports (pt_packages.service → payments.models / users.display) | 43de18b |
| `tests/integration/test_payment_receipt_email_pt.py` | NEW 3-case integration test | 0c72165 |

## Verification

- `pytest tests/integration/test_payment_receipt_email_pt.py -v` — 3 passed.
- `pytest tests/integration/pt_packages/` — 82 passed (no regression).
- `pytest tests/unit/test_locked_email_templates_ast.py -v` — 6 passed
  (gate accepts the 2 new pt_packages literal callsites).
- `lint-imports` — 3 contracts kept, 0 broken.
- `mypy --strict app/modules/pt_packages/service.py` — clean.
- `mypy --strict tests/integration/test_payment_receipt_email_pt.py` — clean.
- `ruff check` clean on touched files.

## Deviations from Plan

**1. [Rule 1 — Bug] Idempotency-Key required on PT-package refund route**
- **Found during:** Task 2 first run (refund sub-test returned 422
  `idempotency_key_required`).
- **Issue:** Plan 45-09 memberships refund route is
  idempotency-key-optional, so its test passes only X-CSRF-Token. The
  pt_packages refund route enforces Idempotency-Key per D-33-16
  (mirrored across all pt_packages write routes).
- **Fix:** Extend `_csrf_refund_headers` to include
  `Idempotency-Key: uuid4().hex`. Aligns with the pattern in
  `tests/integration/pt_packages/test_pt_package_refund.py:94-96`.
- **Commit:** 0c72165.

Per Plan 45-09's documented deviations (UUID str-cast in audit.emit,
single-session post-commit fanout, narrowly-scoped `.importlinter`
ignore_imports) — all three were mirrored byte-for-byte as expected;
no new divergence introduced beyond the Idempotency-Key fix above.

## Deferred Issues

- Pre-existing `test_freeze_resolver::test_telegram_checkin_frozen_oracle_safe_dm`
  `TypeError: HandlerContext.__new__() missing 2 required positional arguments`
  — already documented in `deferred-items.md` as a Phase 40 carry-over.
  Not introduced or worsened by this plan.

## Self-Check: PASSED

- File `apps/backend/app/modules/pt_packages/service.py`:
  - `template_id="EMAIL_PAYMENT_RECEIPT_SALE"` (1 occurrence)
  - `template_id="EMAIL_PAYMENT_RECEIPT_REFUND"` (1 occurrence)
  - `_fanout_payment_receipt_email` helper present; invoked from
    `create_pt_package` (sale) and `refund_pt_package` (refund).
- File `apps/backend/tests/integration/test_payment_receipt_email_pt.py`: FOUND.
- File `apps/backend/.importlinter` — 2 new pt_packages.service entries present.
- Commits 43de18b + 0c72165 present in `git log --oneline`.
- All `<success_criteria>` from `45-10-PLAN.md` met.
