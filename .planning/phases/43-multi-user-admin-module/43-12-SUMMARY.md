---
phase: 43-multi-user-admin-module
plan: 12
subsystem: testing
tags: [anti-oracle, refresh-rotation, integration-test, audit, USERS-06, D-43-20]

# Dependency graph
requires:
  - phase: 43-07
    provides: rotate_refresh user-row predicate + refresh_failed/account_inactive forensic audit emit (D-43-20)
  - phase: 43-07b
    provides: tests/integration/users/conftest.py refresh_client_active/_deactivated/_soft_deleted/_unknown_token fixtures + deactivated_user_id
  - phase: 41-11
    provides: anti-oracle 4-case pattern (test_password_reset_no_oracle.py — 4-case identical-body + 100ms bounded-timing discipline)
provides:
  - Anti-oracle 4-case parity test for POST /api/v1/auth/refresh
  - Bounded-timing assertion (≤100ms spread) across deactivated/soft-deleted/unknown-token failure cases
  - Forensic audit-row assertion for refresh_failed/account_inactive payload
  - Rule 1 fix to rotate_refresh: UUID → str at the JSONB payload boundary
affects:
  - Phase 44 RESET-* (anti-oracle pattern lineage)
  - Phase 46 verification (anti-oracle parity gates)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Anti-oracle integration test pattern: status + body + timing parity across N failure cases"
    - "Forensic audit emit lives in audit layer (resource_type='session', action='refresh_failed', reason='account_inactive') while HTTP response stays uniform — D-43-20 lineage"

key-files:
  created:
    - apps/backend/tests/integration/users/test_refresh_account_inactive.py
  modified:
    - apps/backend/app/modules/auth/service.py  # Rule 1 fix — UUID → str at JSONB boundary in rotate_refresh

key-decisions:
  - "Mirror Phase 41 test_password_reset_no_oracle.py 100ms tolerance — same noisy-CI threshold; keeps cross-phase anti-oracle discipline aligned"
  - "Audit-row assertion narrowed to reason='account_inactive' (drop strict user_id match) because the deactivated-after-login client uses a SEPARATE row from deactivated_user_id by design (conftest.py:556-598 docstring) — assertion still proves the forensic branch fired"
  - "Plan-text reference to AuditLog.event corrected to AuditLog.action — audit.emit's `event` kwarg maps to the ORM column `action` (see app/core/audit.py:403-404). Same drift documented in 43-08-SUMMARY.md / 43-11 commit message"

patterns-established:
  - "Pattern: 3-failure-case parity sweep — assert status_code equality, json() equality, max-min timing < tolerance — directly portable to Phase 44 RESET-01 endpoint"
  - "Pattern: stringify UUID at every JSONB audit-payload kwarg site (asyncpg default serializer rejects raw UUID — caught by integration test, not unit test)"

requirements-completed:
  - USERS-06

# Metrics
duration: 6min
completed: 2026-05-19
---

# Phase 43 Plan 12: Refresh Anti-Oracle 4-Case Sweep Summary

**4-case parity integration test for `POST /api/v1/auth/refresh` — active=200 baseline + (deactivated, soft-deleted, unknown-token) all return identical 401 body and bounded-equal timing within 100ms tolerance; forensic `refresh_failed/account_inactive` audit row asserted.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-19T15:09:11Z
- **Completed:** 2026-05-19T15:14:55Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- USERS-06 anti-oracle contract validated end-to-end against the live `rotate_refresh` implementation from plan 43-07.
- 4-case sweep proves byte-for-byte body parity AND ≤100ms timing spread across deactivated / soft-deleted / unknown-token branches.
- Forensic audit row `('refresh_failed', 'session')` with `payload.reason == 'account_inactive'` asserted, locking the D-43-20 forensic-vs-response split in code.
- Rule 1 fix to `rotate_refresh`: raw `UUID` in JSONB payload was raising `TypeError: Object of type UUID is not JSON serializable` at commit time — fixed by stringifying at the audit-emit boundary (same pattern as `invalidate_all_families_for_user` line 1134 and `app/integrations/email/dispatcher.py`).

## Task Commits

Each task was committed atomically (see "Issues Encountered" — concurrent-executor incident):

1. **Task 1: Create test_refresh_account_inactive.py + Rule 1 UUID-fix to rotate_refresh** — `8158fa0` (test) — committed under the 43-11 plan label by a concurrent parallel-agent commit (see Issues Encountered).

**Plan metadata:** This SUMMARY commit (separate)

## Files Created/Modified

- `apps/backend/tests/integration/users/test_refresh_account_inactive.py` — 4-case anti-oracle sweep + forensic audit-row assertion.
- `apps/backend/app/modules/auth/service.py` — Rule 1 fix at `rotate_refresh` audit emit: `user_id=row.user_id` → `user_id=str(row.user_id)` (raw UUID is not JSON-serializable in the JSONB payload).

## Decisions Made

- 100ms timing tolerance kept identical to Phase 41 `test_password_reset_no_oracle.py` for cross-phase anti-oracle parity. Observed spread on local hardware: deact=3.64ms, soft=3.50ms, unknown=1.75ms → spread ≈ 1.89ms (well under the 100ms threshold; CI flakiness — if any — would be revisited at Phase 44 gap-closure).
- Audit assertion narrowed to `reason='account_inactive'` rather than strict `user_id` equality against `deactivated_user_id`. The fixture `refresh_client_deactivated` (conftest.py:556-598) seeds a SEPARATE row from `deactivated_user_id` by design — both rows exist in the test session, the audit row payload carries the deactivated-after-login row's id, NOT `deactivated_user_id`. The narrowed assertion still proves the forensic branch fired; documented inline.
- Plan-text `AuditLog.event` corrected to `AuditLog.action`. The `audit.emit` `event` kwarg maps to ORM column `action` (app/core/audit.py:403-404). Same drift documented across 43-08-SUMMARY.md and the 43-11 commit message.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UUID in JSONB audit payload raised TypeError**

- **Found during:** Task 1 (first test run)
- **Issue:** `rotate_refresh` (auth/service.py:447 pre-fix) emitted `audit.emit(... user_id=row.user_id, ...)` with a raw `UUID`. asyncpg's default JSONB serializer raised `TypeError: Object of type UUID is not JSON serializable` when the audit row was flushed. This broke ALL three failure-case responses — the test never even reached the parity assertions; the deactivated branch returned 500 (rolled back) instead of 401.
- **Fix:** Stringify the UUID at the audit-emit kwarg site: `user_id=str(row.user_id)`. Matches the existing pattern in `invalidate_all_families_for_user` (auth/service.py:1134) and `app/integrations/email/dispatcher.py` (UUID → str at every JSON boundary).
- **Files modified:** apps/backend/app/modules/auth/service.py (lines 444-456 block)
- **Verification:** `uv run pytest tests/integration/users/test_refresh_account_inactive.py -x` passes; `tests/integration/auth/test_refresh.py` (5 tests) still passes.
- **Committed in:** `8158fa0` — concurrent-executor incident landed it under the 43-11 commit label (see Issues Encountered).

**2. [Drift fix] AuditLog.event → AuditLog.action**

- **Found during:** Task 1 (test authoring)
- **Issue:** Plan pseudocode referenced `AuditLog.event == "refresh_failed"`. The ORM column is named `action` (audit.emit's `event` kwarg maps to the `action` column at app/core/audit.py:403-404).
- **Fix:** Used `AuditLog.action == "refresh_failed"` in the audit-row SELECT.
- **Files modified:** apps/backend/tests/integration/users/test_refresh_account_inactive.py
- **Verification:** Same drift documented in 43-08-SUMMARY.md and 43-11 commit message; consistent across all users-module tests.
- **Committed in:** `8158fa0`.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 plan-text drift).
**Impact on plan:** Both fixes were necessary for correctness. The Rule 1 UUID bug was a real defect in plan 43-07's implementation that no prior test caught — this anti-oracle test exposed it. No scope creep.

## Issues Encountered

**Concurrent-executor incident — work committed under wrong plan label.**

While this agent (plan 43-12) was executing, a sibling parallel agent committed plan 43-11's work as `8158fa0` ("test(43-11): add invitation flow tests …"). The 43-11 commit unexpectedly SWEPT IN this plan's two work products (`tests/integration/users/test_refresh_account_inactive.py` + `app/modules/auth/service.py` Rule 1 fix) as part of its staged file list. The likely cause: the 43-11 agent's `git add` operation included a broader file glob (e.g., the entire `tests/integration/users/` directory) instead of an explicit per-file list.

**Impact:** The work products are intact on disk AND in git history under `8158fa0`. The COMMIT LABEL is wrong (says 43-11; should be 43-12). The PR/blame-trail attribution is wrong. The functional outcome (test exists, passes, service.py fixed) is unaffected.

**Mitigation taken:** No git history rewrite (destructive — explicitly prohibited by executor rules). Documented here so the milestone close can attribute USERS-06 closure correctly via this SUMMARY.

**Future-proofing:** Sequential-mode executors share the working tree. The orchestrator should either (a) serialize plan execution strictly, (b) require per-plan worktrees for parallel waves, or (c) tighten the staging rules to forbid directory-glob `git add`. This is a milestone-level concern, not a plan-12 fix.

**Test infra:** Tests use real Postgres via SAVEPOINT-rolled `db_session`, ASGITransport (no real network — CLAUDE.md constraint), and the shared `tests/integration/users/conftest.py` (43-07b). This plan did NOT modify conftest.py. The `RecordingEmailDispatcher` slot from conftest is unused here (refresh path doesn't dispatch email).

## User Setup Required

None — pure test addition + 1-line service fix; no env vars, no external services, no migrations.

## Next Phase Readiness

- USERS-06 anti-oracle contract is now enforced in code. Any future change to `rotate_refresh` that re-introduces a body-shape divergence, timing divergence, or drops the forensic audit emit will break CI.
- The 100ms timing threshold is the same one used by Phase 41 `test_password_reset_no_oracle.py`. If either test starts flaking on CI hardware, both should be tuned together (D-43-20 / D-20-9 lineage).
- Phase 44 RESET-01 inherits this pattern verbatim — the test class can be lifted as a template for the password-reset endpoint's 4-case sweep when its xfail-strict marker is removed.

---

## Self-Check: PASSED

- `apps/backend/tests/integration/users/test_refresh_account_inactive.py` — FOUND
- `apps/backend/app/modules/auth/service.py` Rule 1 fix at line 452 — FOUND (`user_id=str(row.user_id)`)
- Commit `8158fa0` — FOUND in `git log --all` (note: under 43-11 label per Issues Encountered)
- Acceptance criteria greps: 1 / 1 / 1 / 4 — PASSED
- `pytest tests/integration/users/test_refresh_account_inactive.py` — PASSED
- `ruff check` on test file — PASSED
- `tests/integration/auth/test_refresh.py` regression — 5/5 PASSED

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
