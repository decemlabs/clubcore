---
phase: 83-bonus-redemption-at-checkout
plan: "02"
subsystem: backend
tags: [loyalty, redemption, webhook, yookassa, promo, idempotency, overdraft]
dependency_graph:
  requires:
    - phase: 83-01
      provides: loyalty_ledger.online_payment_id FK + partial UNIQUE + online_payments.loyalty_redeem_kopecks + loyalty_redeemed audit event
  provides:
    - record_loyalty_redemption (idempotent, overdraft-clamped, audit-emitting)
    - checkout server cap (min(requested, balance, post_promo_price-1))
    - webhook loyalty debit on payment.succeeded
    - promo attribution fix (plan_price - amount - loyalty_redeem_kopecks)
  affects:
    - loyalty/service.py
    - online_payments/repository.py
    - online_payments/service.py
    - client_portal/schemas.py
    - client_portal/service.py
    - client_portal/router.py
    - yookassa/handlers.py
tech_stack:
  added: []
  patterns:
    - pg_insert on_conflict_do_nothing with index_elements + index_where targeting partial UNIQUE INDEX
    - RETURNING-gated audit emit (only on real insert, not conflict replay)
    - server-authoritative bonus clamp at checkout (D-06 pattern extended to loyalty)
    - plan-price lookup hoisted to cover EITHER promo OR loyalty (attribution correctness)
key-files:
  created:
    - apps/backend/tests/integration/test_loyalty_redemption.py
  modified:
    - apps/backend/app/modules/loyalty/service.py
    - apps/backend/app/modules/online_payments/repository.py
    - apps/backend/app/modules/online_payments/service.py
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/client_portal/router.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/.importlinter
key-decisions:
  - "record_loyalty_redemption uses index_elements + index_where (NOT constraint=) for on_conflict_do_nothing — mirrors accrue_welcome_bonus pattern; partial UNIQUE INDEX requires this form"
  - "Promo attribution fix: discount_kopecks_for_redemption = max(0, plan_price - amount_kopecks - loyalty_redeem_kopecks); without this stacked promo+bonus over-attributed to promo"
  - "Plan-price SELECT hoisted to run when EITHER promo_code_id OR loyalty_redeem_kopecks is set — avoids code duplication and ensures correct attribution in both branches"
  - "checkout clamp uses inline raw SQL text() for plan price (D-54-08) — no ORM cross-module import; client_portal.service -> loyalty.service edge added to .importlinter"
  - "Test isolation uses real-commit engine + TRUNCATE (same pattern as webhook_yookassa/conftest.py) — required because webhook handler uses async with session.begin()"
requirements-completed: [REDM-01, REDM-02]
duration: "~35 minutes"
completed: "2026-06-05"
---

# Phase 83 Plan 02: Loyalty Redemption End-to-End Summary

**Server-authoritative bonus redemption: server-clamped checkout, idempotent overdraft-clamped webhook debit, promo attribution fix, and 5-case regression test suite proving D-06 / T-83-05 / T-83-06 / T-83-08**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-05T14:00:00Z
- **Completed:** 2026-06-05T14:35:00Z
- **Tasks:** 2
- **Files modified:** 8 + 1 new test file

## Accomplishments

- `record_loyalty_redemption` service function: idempotent (partial UNIQUE conflict-do-nothing), overdraft-clamped (`actual_debit = min(requested, balance)`), audit-emitting (RETURNING-gated `loyalty_redeemed` event), caller-owns-txn
- Checkout clamp: `loyalty_redeem_kopecks` field on `ClientCheckoutRequest`; server computes `min(requested, balance, post_promo_price - 1)` and persists exact amount on `online_payments.loyalty_redeem_kopecks`
- Webhook: plan-price SELECT hoisted to run for EITHER promo OR loyalty; promo attribution fixed (`plan_price - amount - loyalty_redeem_kopecks`); loyalty debit block calls `record_loyalty_redemption` co-transactionally
- 5 regression tests: idempotency (replay = 1 row), overdraft clamp (SUM >= 0), promo+bonus stacking attribution (regression for T-83-08), no-pay no-debit (D-06), D-06 server cap

## Task Commits

1. **Task 1: record_loyalty_redemption + online_payments plumbing** - `ffb2e035` (feat)
2. **Task 2: Checkout clamp + webhook redemption + promo-attribution fix + tests** - `c4f31d4e` (feat)

## Files Created/Modified

- `apps/backend/app/modules/loyalty/service.py` — added `record_loyalty_redemption` (idempotent, overdraft-clamped, RETURNING-gated audit)
- `apps/backend/app/modules/online_payments/repository.py` — added `loyalty_redeem_kopecks: int | None` kwarg (conditional-include pattern)
- `apps/backend/app/modules/online_payments/service.py` — added `loyalty_redeem_kopecks` param to `_sell_subject_core`; applies after promo override with `max(1, ...)` floor
- `apps/backend/app/modules/client_portal/schemas.py` — added `loyalty_redeem_kopecks: int | None` field (wire: `loyaltyRedeemKopecks`)
- `apps/backend/app/modules/client_portal/service.py` — added bonus clamp block in both checkout functions; raw SQL plan-price read (D-54-08)
- `apps/backend/app/modules/client_portal/router.py` — threads `payload.loyalty_redeem_kopecks` to both checkout service calls
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — hoisted plan-price SELECT; fixed promo attribution; added loyalty redemption block; imported `record_loyalty_redemption`
- `apps/backend/.importlinter` — added `client_portal.service -> loyalty.service` ignore edge (Phase 83 REDM-01)
- `apps/backend/tests/integration/test_loyalty_redemption.py` — 5 integration tests (all green)

## Decisions Made

- `record_loyalty_redemption` uses `index_elements + index_where` for `on_conflict_do_nothing` — required because `uq_loyalty_ledger_online_payment_id` is a partial INDEX (not a named CONSTRAINT); `ON CONFLICT ON CONSTRAINT` only works for named constraints (mirrors `accrue_welcome_bonus` pattern)
- Promo attribution fix: subtract `loyalty_redeem_kopecks` from the discount calculation so stacked promo+bonus payments attribute correctly to each row (T-83-08 regression)
- Plan-price SELECT hoisted outside the `if row.promo_code_id is not None` guard to serve both promo and loyalty attribution in a single DB read
- checkout clamp reads plan price via inline raw SQL (`text("SELECT price_kopecks FROM membership_plans WHERE id = :id")`) — avoids ORM cross-module import (D-54-08); new `.importlinter` edge for loyalty service call
- Tests use real-commit sessions to match the webhook handler's `async with session.begin()` pattern (same as `webhook_yookassa/conftest.py`)

## Deviations from Plan

None — plan executed exactly as written. All five behaviors, all specified threat mitigations (T-83-04..T-83-09), and the exact file list were implemented.

## Known Stubs

None.

## Threat Flags

No new security-relevant surface beyond what the plan's threat_model documents. All STRIDE threats T-83-04..T-83-09 mitigated per plan.

## Self-Check: PASSED

- `apps/backend/app/modules/loyalty/service.py` (record_loyalty_redemption): FOUND
- `apps/backend/tests/integration/test_loyalty_redemption.py`: FOUND
- Commit `ffb2e035`: FOUND
- Commit `c4f31d4e`: FOUND
- mypy --strict app: Success (235 files, 0 issues)
- lint-imports: 3 kept, 0 broken
- ruff check + ruff format --check: all clean
- 5/5 tests green
