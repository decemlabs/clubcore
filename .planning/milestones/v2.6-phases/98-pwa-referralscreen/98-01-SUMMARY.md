---
phase: 98-pwa-referralscreen
plan: "01"
subsystem: api
tags: [fastapi, referrals, loyalty, raw-sql, integration-tests, pydantic, idor]

# Dependency graph
requires:
  - phase: 96-referral-core
    provides: referral_codes + referral_captures tables, ReferralCode/ReferralCapture models, client_router, get_or_create_referral_code
  - phase: 97-referral-crediting
    provides: loyalty_ledger referral_accrual rows with referral_capture_id FK, entry_type='referral_accrual'
provides:
  - GET /api/v1/client/referral/summary endpoint returning {code, shareUrl, accruedKopecks, invitees[]}
  - ReferralInviteeItem schema (firstName, joinedAt, status, bonusKopecks) — PII-minimal
  - ReferralSummaryResponse schema (code, shareUrl, accruedKopecks, invitees)
  - get_referral_summary service function with raw-SQL cross-module fold + join
  - 7 integration tests proving empty/pending/joined/PII/IDOR/401/shareUrl invariants
affects: [98-02-pwa-referralscreen-hook, 98-03-pwa-referralscreen-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-module aggregate read via raw text() SQL (D-54-08): SUM fold + LEFT JOIN referral_captures→clients→loyalty_ledger"
    - "accruedKopecks = COALESCE(SUM) WHERE entry_type='referral_accrual' — referral-only, not total loyalty balance"
    - "status='joined' iff loyalty_ledger referral_accrual row exists for the referrer+capture (ll.id IS NOT NULL)"

key-files:
  created:
    - apps/backend/tests/integration/test_referral_summary.py
  modified:
    - apps/backend/app/modules/referrals/schemas.py
    - apps/backend/app/modules/referrals/service.py
    - apps/backend/app/modules/referrals/router.py

key-decisions:
  - "get_referral_summary reuses get_or_create_referral_code for code+shareUrl so the screen always has a stable code"
  - "Cross-module reads (clients, loyalty_ledger) via raw text() in service.py — no repository method added (consistent with resolve_public_code pattern)"
  - "accruedKopecks filtered to entry_type='referral_accrual' only — never exposes total loyalty balance"
  - "IDOR-safe: client_id sourced exclusively from require_client() principal, never path/query/body param"

requirements-completed: [REFER-06]

# Metrics
duration: 18min
completed: 2026-06-08
---

# Phase 98 Plan 01: Backend GET /client/referral/summary Summary

**Aggregate referral read endpoint returning code, shareUrl, referral-only accruedKopecks SUM, and PII-minimal invitees list via raw-SQL cross-module join**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-08T00:00:00Z
- **Completed:** 2026-06-08
- **Tasks:** 3
- **Files modified:** 4 (3 modified + 1 created)

## Accomplishments
- Added `ReferralInviteeItem` + `ReferralSummaryResponse` schemas with PII-minimal field set (first name only, no lastName, no referee client_id) and proper `# wire:` camelCase annotations
- Implemented `get_referral_summary` service function using two raw `text()` reads (COALESCE/SUM fold for accrued, LEFT JOIN for invitees) with D-54-08 cross-module SQL discipline
- Mounted `GET /api/v1/client/referral/summary` on `client_router` with `require_client()` gate, IDOR-safe (T-98-02), mypy/ruff/import-linter clean
- 7 integration tests passing: empty, pending, joined, PII guard (exact 4-key set), shareUrl assertion, 401, and IDOR isolation

## Task Commits

1. **Task 1: Define summary response schemas** - `f37dfc72` (feat)
2. **Task 2: Implement get_referral_summary service + GET /referral/summary route** - `eb140ff2` (feat)
3. **Task 3: Integration tests for the summary endpoint** - `5ad1d94f` (test)

## Files Created/Modified
- `apps/backend/app/modules/referrals/schemas.py` - Added `ReferralInviteeItem` + `ReferralSummaryResponse`; added `datetime` and `Literal` imports
- `apps/backend/app/modules/referrals/service.py` - Added `get_referral_summary` function; imported new schema types
- `apps/backend/app/modules/referrals/router.py` - Added `client_get_referral_summary` handler on `client_router`; imported `ReferralSummaryResponse`
- `apps/backend/tests/integration/test_referral_summary.py` - 7 integration tests (new file)

## Decisions Made
- Reuse `get_or_create_referral_code` to obtain code+shareUrl so the screen always has a code even on first call (minting is idempotent and only commits on first mint)
- Keep cross-module joins inline in `service.py` as raw `text()` SQL rather than adding a repository method — consistent with `resolve_public_code` pattern already in the same file
- `status='joined'` determined by `(ll.id IS NOT NULL)` in the LEFT JOIN — no separate subquery needed
- `bonusKopecks=0` while pending is safe because the LEFT JOIN returns `COALESCE(ll.amount_kopecks, 0)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff E501 line-too-long in test docstrings**
- **Found during:** Task 3 (integration tests)
- **Issue:** Two docstring lines exceeded the 100-char limit in `test_referral_summary.py`
- **Fix:** Shortened docstring lines to fit within 100 chars
- **Files modified:** `apps/backend/tests/integration/test_referral_summary.py`
- **Verification:** `uv run ruff check` clean after fix; all 7 tests still pass
- **Committed in:** `5ad1d94f` (part of task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — line length in test docstrings)
**Impact on plan:** Trivial cosmetic fix. No scope creep. No behavior change.

## Issues Encountered
- The worktree's `apps/backend/` lacked a `.env` file (the main repo has one), causing conftest import failure when loading `YooKassaSettings`. Fixed by symlinking the main repo's `.env` into the worktree backend directory. This is a worktree-local setup artifact, not a code issue.

## Threat Surface Scan
No new network endpoints beyond what is specified in the plan's threat model. The new GET route is registered on the existing `client_router` (no new router instance). All threat model mitigations are implemented:
- T-98-01: PII-minimal schema — `firstName` only, no `lastName`, no `refereeClientId`
- T-98-02: IDOR — `client_id` from `require_client()` only; `test_summary_idor_*` proves isolation
- T-98-03: Spoofing — `require_client()` gate; `test_summary_no_auth_returns_401` proves 401
- T-98-04: accruedKopecks filtered to `entry_type='referral_accrual'`
- T-98-05: Parameterized `text()` binds; no string interpolation of user input

## Next Phase Readiness
- Backend contract is fully implemented and tested. Wave 2 (Plan 98-02) can wire `useClientReferralSummary` React Query hook against this endpoint.
- Route path: `GET /api/v1/client/referral/summary`
- Wire shape: `{ data: { code, shareUrl, accruedKopecks, invitees: [{firstName, joinedAt, status, bonusKopecks}] } }`

## Self-Check

### Files exist:
- `apps/backend/app/modules/referrals/schemas.py` - modified
- `apps/backend/app/modules/referrals/service.py` - modified
- `apps/backend/app/modules/referrals/router.py` - modified
- `apps/backend/tests/integration/test_referral_summary.py` - created

### Commits exist:
- `f37dfc72` - schemas
- `eb140ff2` - service + router
- `5ad1d94f` - tests

## Self-Check: PASSED

---
*Phase: 98-pwa-referralscreen*
*Completed: 2026-06-08*
