---
phase: 113-promo-codes-crud
plan: "02"
subsystem: testing
tags: [promo-codes, rbac, integration-tests, asgi-transport, pytest-asyncio]

dependency_graph:
  requires:
    - "113-01 backend CRUD endpoints (PromoCode model, router, service, repository)"
    - "tests/integration/memberships/conftest.py fixture machinery"
  provides:
    - "tests/integration/promo_codes/ — new integration test package (16 tests)"
    - "CRUD happy-path contract tests against real ASGITransport backend"
    - "RBAC parity regression guard: reception 403 on all 3 writes + 200 on list"
    - "CSRF enforcement test: owner without X-CSRF-Token → 403 csrf_mismatch"
    - "D-V32-DRIFT-LESSON contract test: used_count aggregate from real backend response"
  affects:
    - "113-03 frontend wiring — can rely on green backend contract tests"
    - "Phase 117 milestone gate — PROMO-01/PROMO-02 domains have ≥1 real-response test"

tech_stack:
  added: []
  patterns:
    - "make_redemption creates a fresh MembershipPlan per call to avoid uq_online_payments_membership_double_tap partial unique collision"
    - "PromoRedemption requires OnlinePayment stub (NOT NULL FK + exactly_one_subject_fk check)"
    - "Re-export conftest fixtures via noqa: F401 (pytest discovery pattern, mirroring payments/conftest.py)"
    - "_csrf_headers(client) helper inline in tests for self-contained readability"

key_files:
  created:
    - apps/backend/tests/integration/promo_codes/__init__.py
    - apps/backend/tests/integration/promo_codes/conftest.py
    - apps/backend/tests/integration/promo_codes/test_promo_codes_crud.py
    - apps/backend/tests/integration/promo_codes/test_promo_codes_rbac.py

decisions:
  - "make_redemption creates a unique MembershipPlan per call (not reusing one plan) — avoids uq_online_payments_membership_double_tap (client_id + membership_plan_id + date) collision when the same client redeems the same promo twice in one test"
  - "PromoCodeResponse (create/edit) does NOT expose usedCount — only PromoCodeListItemResponse does; test_create_percentage_happy asserts usedCount absent from create response"
  - "Test (9) used_count uses direct DB inserts via make_redemption, not HTTP redemption flow — no redemption HTTP endpoint exists in admin scope; validates the correlated subquery aggregate"

requirements-completed: [PROMO-01, PROMO-02]

duration: ~6 minutes
completed: 2026-06-15
---

# Phase 113 Plan 02: Promo Codes Integration Tests Summary

**16 ASGITransport integration tests covering CRUD happy paths, UPPER-normalization, 409/422 error codes, reception-RBAC (403 on all writes), CSRF enforcement, and the D-V32-DRIFT-LESSON used_count aggregate contract test against the real backend.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-15T09:22:00Z
- **Completed:** 2026-06-15T09:28:00Z
- **Tasks:** 3
- **Files created:** 4

## Accomplishments

- Created `tests/integration/promo_codes/` package with conftest re-exporting memberships fixture machinery
- 10 CRUD behavior tests: create (percentage + fixed), duplicate 409, zero/over-100% 422, edit, 404 not-found, deactivate+re-list, pagination envelope shape, and the real-backend used_count aggregate
- 6 RBAC+CSRF tests: reception 403 on create/edit/deactivate, reception 200 on list, CSRF-missing 403 csrf_mismatch, owner sanity 201

## Task Commits

1. **Task 1: Test package + conftest** - `2a3716b6` (test)
2. **Task 2: CRUD behavior tests + conftest make_redemption fix** - `10e805c3` (test)
3. **Task 3: RBAC + CSRF guard tests + ruff import fix** - `98ebe46b` (test)

## Files Created

- `apps/backend/tests/integration/promo_codes/__init__.py` - Empty package marker
- `apps/backend/tests/integration/promo_codes/conftest.py` - Re-exports memberships fixtures; adds make_promo_code + make_redemption factories; _csrf_headers helper
- `apps/backend/tests/integration/promo_codes/test_promo_codes_crud.py` - 10 CRUD/normalization/conflict/invalid/used_count tests
- `apps/backend/tests/integration/promo_codes/test_promo_codes_rbac.py` - 6 reception 403 + CSRF guard tests

## Decisions Made

- `make_redemption` creates a unique `MembershipPlan` per call (not a shared singleton). The `uq_online_payments_membership_double_tap` partial unique index fires on (client_id, membership_plan_id, date) when status != 'canceled'. Since two `make_redemption` calls for the same client in one test would insert two `OnlinePayment` rows for the same plan on the same day, each call creates its own plan.
- `PromoCodeResponse` (create/edit responses) intentionally does NOT include `usedCount`. This is only in `PromoCodeListItemResponse`. The test explicitly asserts `"usedCount" not in data` to document the contract boundary.
- The used_count test (D-V32-DRIFT-LESSON) uses direct DB inserts via `make_redemption` — no HTTP redemption endpoint exists in the admin CRUD scope. The test validates the correlated scalar subquery in `repository.list_promo_codes`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] OnlinePayment CHECK constraint violation in make_redemption**
- **Found during:** Task 2, first test run of `test_used_count_reflects_promo_redemptions`
- **Issue:** The initial `make_redemption` implementation created an `OnlinePayment` without setting `membership_plan_id` or `pt_package_plan_id`. The `ck_online_payments_exactly_one_subject_fk` constraint `(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)` rejected the INSERT.
- **Fix:** Added `membership_plan_id=plan.id` to the `OnlinePayment` stub, using `make_plan` (re-exported fixture) to create a plan before each call.
- **Files modified:** `apps/backend/tests/integration/promo_codes/conftest.py`
- **Committed in:** `10e805c3` (Task 2)

**2. [Rule 1 - Bug] SAVEPOINT rollback on second make_redemption call**
- **Found during:** Task 2, same test
- **Issue:** Reusing the same `MembershipPlan` for both `OnlinePayment` stubs triggered `uq_online_payments_membership_double_tap` (partial unique index on client_id + membership_plan_id + date WHERE status != 'canceled'). The second INSERT violated the index.
- **Fix:** Changed `make_redemption` to create a new `MembershipPlan` per call (`name=f"PromoTest Plan {_counter['i']}"`) so each `OnlinePayment` stub uses a distinct plan.
- **Files modified:** `apps/backend/tests/integration/promo_codes/conftest.py`
- **Committed in:** `10e805c3` (Task 2)

**3. [Rule 1 - Bug] ruff I001 import ordering in both test files**
- **Found during:** Task 3 ruff check
- **Issue:** `from tests.integration.promo_codes.conftest import _csrf_headers` was not in the correct isort block (missing blank line separation between stdlib/third-party and first-party imports).
- **Fix:** `uv run ruff check --fix` applied automatically.
- **Files modified:** `test_promo_codes_crud.py`, `test_promo_codes_rbac.py`
- **Committed in:** `98ebe46b` (Task 3)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — constraint + index + import bugs found during test execution)
**Impact on plan:** All fixes required for test correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations documented above.

## Threat Surface Scan

No new threat surface introduced. Test files only — no production routes, models, or infrastructure changed.

## Known Stubs

None. Test files only.

## Next Phase Readiness

- 113-03 (frontend wiring of PlansPage promo section) can proceed with confidence: the backend contract is now green-locked by 16 ASGITransport tests.
- Phase 117 milestone gate: PROMO-01/PROMO-02 domains now have ≥1 real-backend contract test (`test_used_count_reflects_promo_redemptions` parses a live list response with the correlated subquery aggregate).

## Self-Check: PASSED

All key files verified present on disk:
- FOUND: apps/backend/tests/integration/promo_codes/__init__.py
- FOUND: apps/backend/tests/integration/promo_codes/conftest.py
- FOUND: apps/backend/tests/integration/promo_codes/test_promo_codes_crud.py
- FOUND: apps/backend/tests/integration/promo_codes/test_promo_codes_rbac.py
- FOUND: .planning/phases/113-promo-codes-crud/113-02-SUMMARY.md

All commits verified in git log:
- FOUND: 2a3716b6 (test package + conftest)
- FOUND: 10e805c3 (CRUD behavior tests + conftest fix)
- FOUND: 98ebe46b (RBAC + CSRF guard tests + ruff fix)

---
*Phase: 113-promo-codes-crud*
*Completed: 2026-06-15*
