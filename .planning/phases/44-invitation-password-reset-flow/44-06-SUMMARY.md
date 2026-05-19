---
phase: 44-invitation-password-reset-flow
plan: 06
subsystem: testing
tags: [audit-log, anti-oracle, password-reset, sqlalchemy, pytest, redis-flush]

# Dependency graph
requires:
  - phase: 44-invitation-password-reset-flow
    provides: "request_password_reset service (Wave 2 / plan 44-04) — dual-branch audit emit per D-44-08"
  - phase: 44-invitation-password-reset-flow
    provides: "anonymous /auth/password-reset/request router + atomic xfail-strict marker removal (plan 44-05, commit 5e58950)"
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: "test_password_reset_no_oracle.py xfail-strict harness (D-41-17) + D-41-10 system-emit rule"
provides:
  - "Audit half of D-44-30 — `password_reset_requested` row asserted in BOTH known-email and unknown-email branches"
  - "redis_clean fixture in test_password_reset_no_oracle.py — flushdb per test, mirrors test_login.py:27-32 pattern"
affects:
  - "Phase 44 plan 07/08/09 (downstream audit-chain assertions, AST gate extensions)"
  - "Any future plan that adds anti-oracle integration tests with rate-limit-sensitive flows"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-branch audit-row assertion (Strategy A — multi-assertion in single integration test) using sqlalchemy `select(AuditLog).where(action == ...)` against the SAVEPOINT-wrapped db_session"
    - "Per-test Redis flush via `redis_clean` fixture for rate-limit-sensitive anti-oracle tests (prevents IP-bucket bleed across tests in the same process under ASGITransport)"

key-files:
  created: []
  modified:
    - "apps/backend/tests/integration/auth/test_password_reset_no_oracle.py — extended with D-44-30 audit-row assertion + redis_clean fixture"

key-decisions:
  - "Strategy A (single test, multi-assertion) over Strategy B (sibling test) — re-uses the existing 4-fixture-user seed, keeps the contract co-located"
  - "redis_clean fixture added (Rule 3 — blocking issue): without it, the new audit assertion flakes after ~5 IP-bumps process-wide because the 3-key reset rate-limiter shares the 127.0.0.1 IP key across tests in the same pytest process"

patterns-established:
  - "AuditLog ORM import path for tests: `from app.core.audit_models import AuditLog` (NOT `app.models.audit` — the plan's read_first hint listed a placeholder path; the actual ORM lives in app.core per D-05 cross-cutting placement)"
  - "JSONB roundtrip: UUIDs are stringified at audit.emit time (matches Phase 43 plan 11 / test_users_invitation_flow.py:177-178); test comparison target is `str(user.id)`, not `user.id`"

requirements-completed: [RESET-01]

# Metrics
duration: ~3 min
completed: 2026-05-19
---

# Phase 44 Plan 06: Anti-Oracle Audit-Row Assertion Extension Summary

**Extended `test_password_reset_no_oracle.py` with dual-branch `password_reset_requested` audit-row assertion (D-44-30) + per-test Redis flush, locking the audit half of RESET-01 against future regression.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-19T21:12:00Z (approx — pre-execution context load)
- **Completed:** 2026-05-19T21:15:31Z
- **Tasks:** 2 (Task 1: test extension; Task 2: blocking checkpoint — auto-approved per orchestrator directive)
- **Files modified:** 1

## Accomplishments

- `audit_log` is now queried at the end of `test_password_reset_request_no_oracle` and the test asserts:
  - Exactly 4 `password_reset_requested` rows (one per case — known active / known deactivated / known owner / unknown email).
  - Known-email branch: `payload["target_user_id"] == str(user.id)` for each of the 3 fixture users; `payload["email_hint"] == email.lower()`.
  - Unknown-email branch (D-44-08 / D-41-10): `payload["target_user_id"] IS NULL`; `payload["email_hint"] == nonexistent_email.lower()`.
  - All 4 rows: `actor_user_id IS NULL` + `actor_email_snapshot IS NULL` (D-41-10 system-emit invariant).
  - All 4 rows: `payload["audit_correlation_id"]` is non-NULL (D-44-08 — every request, even unknown-branch, generates a corr-id).
- New `redis_clean` fixture flushes Redis at the start of the test so the IP rate-limit key (15-min window, 5-request bucket) doesn't bleed from earlier tests in the same pytest process.
- Plan 44-05's atomic xfail-strict marker removal is preserved — this commit adds the assertion to an already-green test (no marker churn).

## Task Commits

1. **Task 1: Audit-row assertion extension (D-44-30)** — `fd990e3` (test) — adds the dual-branch assertion + `redis_clean` fixture to `test_password_reset_no_oracle.py`.
2. **Task 2: [BLOCKING] human-verify checkpoint** — auto-approved per orchestrator directive (no commit). The Wave 3 atomic-land in commit `5e58950` (master) already shipped the endpoint AND removed the xfail marker in the same commit; the audit-row assertion is a follow-on observable that does not destabilise the build. Verification evidence:
   - `grep -c "@pytest.mark.xfail" tests/integration/auth/test_password_reset_no_oracle.py` → `0`.
   - `uv run pytest tests/integration/auth/test_password_reset_no_oracle.py -q` → `1 passed in 2.17s` (NO `xfailed`).
   - `uv run pytest tests/integration/auth/ -q` → `54 passed in 11.33s` (full auth suite green — no regression).
   - `uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_locked_email_templates_ast.py -q` → `12 passed in 0.13s` (SVC001 walker + AST gate still green).

**Plan metadata:** (this SUMMARY.md commit follows below).

## Files Created/Modified

- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — extended:
  - Added imports: `FastAPI`, `Redis`, `select`, `AsyncSession`, `AuditLog`.
  - Added `redis_clean` fixture (per-test flushdb, mirrors `test_login.py:27-32`).
  - Updated `four_fixture_users` fixture signature to depend on `redis_clean` (ensures rate-limit reset BEFORE the user-seed POSTs run).
  - Updated `test_password_reset_request_no_oracle` signature to accept `db_session: AsyncSession` so the audit-row query reuses the SAVEPOINT-wrapped session.
  - Added 60-line audit-row assertion block after the existing status / body / timing assertions.
  - Stored the nonexistent email in a named variable (`nonexistent_email`) so the assertion can key by it.

## Decisions Made

- **Strategy A (in-test multi-assertion) over Strategy B (sibling test).** The 4-case POST loop and the 4 fixture users are already wired; duplicating them in a sibling test would double the seed cost and split the contract. Plan 44-06 lists Strategy A as the preferred default for this exact reason.
- **AuditLog import path: `app.core.audit_models.AuditLog`** (NOT `app.models.audit` as the plan's `read_first` block speculatively listed). Verified via `grep -rn "class AuditLog"` — the ORM lives in `app/core/audit_models.py` per D-05 (audit is a cross-cutting concern; FK to `users.id` is a string ref so the module avoids importing `app.modules.auth.models`).
- **Test fixture seeds 4 users with `is_active=True` by default** — the "deactivated" fixture is a label, not a column-level state (USERS-02 deactivation column lands in Phase 43). All 3 known users hit Branch A of the service (token-issue + audit + email enqueue), which still satisfies D-44-30: the assertion shape is about `target_user_id` payload values, not about which internal service branch fires. Both Branch A (issues token + audit) and Branch B (audit-only, deactivated) emit the same audit shape per the service code in `password_reset_service.py:268-312`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Added per-test Redis flush via `redis_clean` fixture**

- **Found during:** Task 1 (running the test after extending it with the audit-row assertion).
- **Issue:** First test run failed with `expected 4 password_reset_requested audit rows ...; got 0`. Captured stdout showed 4 `password_reset.rate_limited` WARN log lines — every request short-circuited at the rate-limit check before the audit-emit branch. Root cause: the reset rate-limiter's per-IP key (`ratelimit:password_reset:ip:127.0.0.1`, 5/15min) is shared across all tests in the same pytest process (ASGITransport defaults `client.host` to `127.0.0.1`); prior tests (or even a prior run of THIS test in the same process) push the IP counter past the 5-bucket threshold, so all 4 POSTs hit the rate-limit-hit branch (D-44-11: NO audit emit, only structlog WARN).
- **Fix:** Added a `redis_clean` async fixture (`flushdb()` per test) and wired `four_fixture_users` to depend on it so the flush runs BEFORE the 4 POSTs. Mirrors the canonical pattern already established at `tests/integration/auth/test_login.py:27-32` (and identical pattern in `test_refresh.py`, `test_logout.py`, `test_sessions_endpoints.py`, `test_telegram_verify_happy.py`).
- **Files modified:** `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py`.
- **Verification:** Test now passes (`1 passed in 2.17s`); full auth integration suite green (`54 passed in 11.33s`).
- **Committed in:** `fd990e3` (Task 1 commit).

---

**Total deviations:** 1 auto-fixed (1 blocking — Rule 3).

**Impact on plan:** The plan's `<action>` block called out exactly this failure mode in a foresight note ("the 4 rapid POSTs from the same IP" rate-limit-hit hazard, suggesting either fresh-IP simulation or seeded-empty Redis). The fix took the seeded-empty-Redis path (cleaner — matches the established auth-test fixture pattern). No scope creep.

## Issues Encountered

- Pre-existing mypy `attr-defined` error on the `User` import from `app.modules.auth.models` shim (line 51 after edits, line 47 before). Confirmed pre-existing baseline noise by running mypy on the file pre-stash — error existed at the original line number. Out of scope per the executor's SCOPE BOUNDARY rule (not caused by this task's changes). Tracked at the shim layer; will be addressed if/when the auth.models shim is hoisted.

## User Setup Required

None — purely a test-file extension. No new env vars, no new DB migrations, no external service config.

## Next Phase Readiness

- D-44-30 audit-row contract is now locked into the integration suite; any future regression in the dual-branch audit emit (either branch dropping a row, payload-shape drift, or actor_user_id leaking non-None) will fail this test in CI.
- The atomic-land invariant from D-44-29 / D-41-17 is preserved end-to-end: commit `5e58950` (Wave 3) shipped the router endpoint AND removed the xfail marker simultaneously; this plan's commit (`fd990e3`) extends an already-green test in a follow-on commit, with NO marker churn and NO CI-red window on master between the two.
- Plan 44-07+ can proceed assuming the `password_reset_requested` audit shape is anchored by this integration test.

## Atomic-Land Invariant Confirmation

Per the plan's `<output>` directive, document the atomic-land chain:

- **Plan 44-04** (Wave 2): Filled the `request_password_reset` service body with the dual-branch audit emit (`password_reset_service.py:268-327`).
- **Plan 44-05** (Wave 3): SHIPPED the anonymous `/api/v1/auth/password-reset/request` router endpoint AND removed the `@pytest.mark.xfail(strict=True)` marker from `test_password_reset_no_oracle.py` in commit `5e58950` (master). Same commit — no intermediate CI run on master sees a stale xfail-strict that is now XPASS-strict.
- **Plan 44-06** (this plan, Wave 4): Added the audit-row assertion on top of the now-green test in commit `fd990e3`. Did NOT touch the xfail marker (it was already absent — verified pre-execution with `grep -c "@pytest.mark.xfail" ... → 0`).

Atomic-land discipline preserved.

---
*Phase: 44-invitation-password-reset-flow*
*Plan: 06*
*Completed: 2026-05-19*

## Self-Check: PASSED

- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` exists.
- `.planning/phases/44-invitation-password-reset-flow/44-06-SUMMARY.md` exists.
- Commit `fd990e3` exists in `git log --oneline --all`.
