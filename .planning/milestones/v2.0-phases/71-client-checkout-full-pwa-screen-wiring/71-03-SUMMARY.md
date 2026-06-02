---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "03"
subsystem: testing
tags: [pytest, fastapi, yookassa, integration-tests, idor, idempotency, csrf, respx]

# Dependency graph
requires:
  - phase: 71-02
    provides: POST /checkout/memberships/{plan_id}, POST /checkout/pt-packages/{plan_id}, GET /payments/{payment_id}/status endpoints
  - phase: 71-01
    provides: invoke_client_checkout_core Protocol slot, _sell_subject_core

provides:
  - 7 integration tests in tests/integration/client_portal/test_checkout.py covering CPAY-01..05
  - Regression guard for T-71-11 (anti-oracle), T-71-12 (IDOR), T-71-13 (duplicate-webhook)
  - Re-exported webhook harness fixtures in client_portal/conftest.py

affects:
  - Phase 72 (drift gate, _v20Checks — checkout contract is now locked by these tests)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Client OTP auth in tests requires telegram_user_id != NULL (D-02 silent no-op guard)
    - Real-commit harness (webhook_client + webhook_db_session) for duplicate-webhook test
    - SAVEPOINT harness (async_client) for checkout + status CRUD tests
    - respx mock overrides ЮKassa POST /payments — no live network in any test
    - conftest re-export pattern for cross-directory pytest fixtures (noqa: F401)

key-files:
  created:
    - apps/backend/tests/integration/client_portal/test_checkout.py
  modified:
    - apps/backend/tests/integration/client_portal/conftest.py

key-decisions:
  - "PT Idempotency-Key replay test uses two distinct PT plans to avoid uq_online_payments_pt_package_double_tap unique constraint (same client+plan+day constraint is intentional DB behavior)"
  - "Duplicate-webhook test uses real-commit webhook_client harness (not SAVEPOINT) because handle_payment_succeeded uses async with session.begin() which cannot compose with SAVEPOINT mode"
  - "Auth helper makes async_client hold both cc_client_access + clubcore_client_csrf after OTP verify — no separate authed client needed"
  - "webhook_client/webhook_db_session/seeded_online_payment_pending re-exported into client_portal/conftest.py following established clubcore noqa: F401 pattern"

patterns-established:
  - "_seed_client_with_email with telegram_user_id from uuid4().int: non-NULL telegram_user_id required for OTP flow (D-02 silent no-op otherwise)"
  - "Anti-oracle test asserts set(data.keys()) == {'id', 'status'} exactly — no extra keys allowed"

requirements-completed: [CPAY-01, CPAY-02, CPAY-03, CPAY-04, CPAY-05]

# Metrics
duration: 9min
completed: "2026-05-30"
---

# Phase 71 Plan 03: Checkout Integration Tests Summary

**7 integration tests proving Phase 71 checkout criteria: CPAY-01..05 success, IDOR 404-collapse, anti-oracle status projection, and idempotent duplicate-webhook activation — all over ASGITransport with respx ЮKassa mock.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-30T15:17:25Z
- **Completed:** 2026-05-30T15:26:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `test_checkout.py` with 7 integration tests covering all Phase 71 checkout success criteria
- Membership checkout 201 + confirmationUrl/onlinePaymentId (CPAY-01)
- Same-day membership replay returns identical confirmationUrl (CPAY-05 server-derived key)
- PT-package same Idempotency-Key replay + different key + different plan = new payment (CPAY-05/D-71-04)
- Checkout without email → 422 `client_email_required_for_online_payment` (CPAY-04, 54-ФЗ gate)
- Status returns ONLY `id` + `status` keys — anti-oracle regression guard (CPAY-03/T-71-11)
- IDOR 404-collapse: client A gets 404 for client B's payment status (D-20-IDOR/T-71-12)
- Duplicate `payment.succeeded` webhook activates membership exactly once (T-71-13/criterion #2)

## Task Commits

1. **Tasks 1 + 2: Checkout integration tests (combined file)** - `e5bceb0e` (test)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `apps/backend/tests/integration/client_portal/test_checkout.py` - 7 integration tests
- `apps/backend/tests/integration/client_portal/conftest.py` - Re-exported webhook fixtures for duplicate-webhook test

## Decisions Made

- **PT idempotency test uses two distinct PT plans:** The `uq_online_payments_pt_package_double_tap` constraint prevents two non-canceled payments for the same `client+plan+day`. Using a second distinct plan for the "different key → new payment" assertion correctly demonstrates D-71-04 without fighting the DB constraint (which is legitimate application behavior).
- **Real-commit harness for duplicate-webhook test:** `handle_payment_succeeded` uses `async with session.begin()` which cannot compose with the SAVEPOINT-mode `db_session`. The test uses `webhook_client + webhook_db_session` (same pattern as `test_wh05_succeeded_atomic_uow.py`).
- **Auth after OTP sets cookies on `async_client` directly:** After `_auth_as_client(async_client, ...)`, the `async_client` cookie jar holds both `cc_client_access` and `clubcore_client_csrf`. All subsequent POST calls use `async_client` directly with `_checkout_headers(async_client)` — no separate `authed` client needed.

## Deviations from Plan

None - plan executed exactly as written.

The only implementation decision was using two distinct PT package plans in `test_pt_checkout_idempotency_key_replay` to avoid the `uq_online_payments_pt_package_double_tap` unique constraint. This correctly demonstrates the D-71-04 split strategy (client-supplied Idempotency-Key allows same-day repurchase of DIFFERENT plans) while respecting the DB constraint that correctly prevents same client+plan+day double-tap.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 7 checkout integration tests green; checkout contract behavior is locked
- Plan 71-04 can regen `openapi.json` + `schema.d.ts` with the endpoints already tested
- Phase 72 drift gate can reference these tests as the checkout regression suite

## Known Stubs

None. All tests run against the real `_sell_subject_core` (wired via `invoke_client_checkout_core`) and real webhook activation path.

## Threat Flags

No new threat surface introduced — this plan adds tests only, no new endpoints or schemas.

## Self-Check

- `apps/backend/tests/integration/client_portal/test_checkout.py` — FOUND
- `apps/backend/tests/integration/client_portal/conftest.py` — FOUND (modified)
- Commit `e5bceb0e` — test(71-03): add checkout integration tests for CPAY-01..05 + IDOR + duplicate-webhook: FOUND
- `pytest tests/integration/client_portal/test_checkout.py` exits 0 with 7 tests: VERIFIED

## Self-Check: PASSED

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
