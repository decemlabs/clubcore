---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 11
subsystem: testing
tags: [pytest, xfail-strict, anti-oracle, password-reset, httpx, asgi-transport, savepoint, contract-as-code]

requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: User shim at app.modules.auth.models (Plan 41-10 D-41-01/02)
provides:
  - RESET-06 anti-oracle contract-as-code (xfail-strict against not-yet-existing endpoint)
  - 4-case identical-202 + identical-body + 100ms bounded-timing assertion fixture
affects: [44-password-reset-and-multi-user-admin, RESET-01]

tech-stack:
  added: []
  patterns:
    - "xfail-strict for forward-declared contracts (D-41-17)"
    - "Per-test SAVEPOINT-isolated fixture for anti-oracle assertions (D-41-18)"
    - "time.perf_counter() bounded-equal timing assertions for endpoint side-channel hardening"

key-files:
  created:
    - apps/backend/tests/integration/auth/test_password_reset_no_oracle.py
  modified:
    - .planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md

key-decisions:
  - "Imported User via the app.modules.auth.models shim (D-41-01) — keeps the test stable across the Plan-10/11 wave race; the shim re-export keeps the symbol valid both pre- and post-hoist"
  - "Used the project's standard async_client + db_session fixtures (conftest.py) rather than instantiating create_app() ad-hoc — inherits dependency overrides + ASGI lifespan + SAVEPOINT rollback automatically"
  - "Seeded the 'deactivated' case as a present non-owner row labelled by email; is_active/deleted_at columns are not yet on the User ORM (the columns ship with USERS-02 in Phase 43). Assertions read only the response envelope, so the case labels are accurate w.r.t. the eventual endpoint contract"

patterns-established:
  - "Anti-oracle contract pre-registration: write the contract test BEFORE the endpoint lands; mark xfail(strict=True); remove the marker in the same PR that ships the endpoint"
  - "Bounded-timing assertion shape: collect (status, body, perf_counter_delta) tuples per case; assert status set, body set length, and max-min delta against an explicit ms tolerance"

requirements-completed: [RESET-06]

duration: 6min
completed: 2026-05-18
---

# Phase 41 Plan 11: RESET-06 anti-oracle xfail-strict scaffold Summary

**Pre-registered the 4-case identical-202 + identical-body + 100ms-bounded-timing contract for `POST /api/v1/auth/password-reset/request` as an xfail-strict integration test, locking the anti-oracle invariant before Phase 44 ships RESET-01.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-18T (session start)
- **Completed:** 2026-05-18
- **Tasks:** 1
- **Files modified:** 1 created + 1 doc updated

## Accomplishments

- Anti-oracle contract-as-code committed at Phase 41 (D-41-17), the endpoint cannot ship in Phase 44 without satisfying it.
- Per-test SAVEPOINT-isolated fixture seeds 4 canonical cases (active / deactivated / owner / non-existent) per D-41-18.
- `time.perf_counter()`-based 100 ms bounded-timing assertion documents the timing-oracle invariant for the eventual Phase 44 implementation.
- Test reports XFAIL today (endpoint absent → HTTP 404 → assertion fails inside xfail block, pytest counts as expected failure, exit 0).
- `strict=True` ensures that removing the marker without a passing endpoint will fail CI loudly (no silent test deletions).

## Task Commits

1. **Task 1: Author tests/integration/auth/test_password_reset_no_oracle.py** — `1b2b858` (test)

**Plan metadata commit:** (created in the final commit step below)

## Files Created/Modified

- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — Anti-oracle contract; xfail-strict; per-test fixture; 100 ms timing bound.
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` — Logged the codebase-wide mypy strict `User` re-export warning on the Plan-10 shim (~25 pre-existing callsites + this new one); resolution lives in a shim-hardening follow-up, not here.

## Decisions Made

- **Import path:** `from app.modules.auth.models import User` (shim) rather than `from app.core.models import User`. Rationale: matches the plan-checker revision (D-41-01 / D-41-02) and keeps the test stable across the Plan-10 ↔ Plan-11 wave-1 race. The shim is a one-milestone aisle; DEFER-41-shim removes it in v1.7.
- **Fixture vs ad-hoc app:** Reused the project's standard `async_client` and `db_session` fixtures from `apps/backend/tests/conftest.py` rather than instantiating `create_app()` directly in the test body. This inherits the FastAPI lifespan firing, the `get_db` dependency override that pins routes to the SAVEPOINT-bound session, the Redis singleton override, and the connection-skip behaviour when Postgres is unreachable — all for free.
- **User column shape:** `is_active` / `deleted_at` columns are not on the `User` ORM at Phase 41 commit time (the DB column lands via migration 0022, the ORM Mapped attribute lands with USERS-02 in Phase 43). The "deactivated" case is therefore represented as a second reception-role row labelled by email; the contract assertions read only response status / body / timing, so the case labels remain semantically correct against the eventual endpoint.

## Deviations from Plan

None — plan executed exactly as written. The only minor inline judgement (using project fixtures vs the sketch's ad-hoc `create_app()`) was explicitly flagged as discretionary in the plan body ("Fixture-helper notes for the executor").

## Issues Encountered

- Mypy strict reports `Module "app.modules.auth.models" does not explicitly export attribute "User"` for the new test — a pre-existing, codebase-wide issue (~25 existing callsites report the same error post-Plan-10). The proper fix lives in the shim file (add `__all__` or `as User` re-export) which is outside Plan 41-11's scope. Logged in `deferred-items.md` for follow-up.

## User Setup Required

None.

## Next Phase Readiness

- Phase 44 RESET-01 implementation MUST remove the xfail marker from `test_password_reset_no_oracle.py` in the same commit that ships `POST /api/v1/auth/password-reset/request`. `strict=True` guarantees CI surfaces any drift.
- Plan-checker for Phase 44 RESET-01 should explicitly enumerate "remove xfail marker from `tests/integration/auth/test_password_reset_no_oracle.py`" as a done-criterion so the marker removal doesn't slip.

## Self-Check: PASSED

- File exists: `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — FOUND.
- Commit exists: `1b2b858` (test: land RESET-06 anti-oracle xfail-strict contract) — FOUND.
- `pytest tests/integration/auth/test_password_reset_no_oracle.py -v` reports `1 xfailed`, exit 0 — VERIFIED.
- `grep "strict=True"` matches — VERIFIED.
- `grep "max(timings) - min(timings) < 0.100"` matches — VERIFIED.

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Completed: 2026-05-18*
