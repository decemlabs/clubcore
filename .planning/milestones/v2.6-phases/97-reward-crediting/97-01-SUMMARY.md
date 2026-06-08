---
phase: 97-reward-crediting
plan: "01"
subsystem: infra
tags: [audit, pydantic, referral, locked-events, infra-15]

# Dependency graph
requires:
  - phase: 96-referral-domain
    provides: LOCKED_AUDIT_EVENTS v2.6 block pattern (referral_code_generated, referral_captured); ReferralCapturedPayload shape; AUDIT_PAYLOAD_SCHEMAS registry v2.6 entries

provides:
  - ("referral_bonus_accrued", "referral") in LOCKED_AUDIT_EVENTS frozenset
  - ReferralBonusAccruedPayload class with extra='forbid' and Literal role discriminator
  - AUDIT_PAYLOAD_SCHEMAS[("referral_bonus_accrued", "referral")] = ReferralBonusAccruedPayload
  - Unit tests proving registration + payload contract (7 assertions)

affects:
  - 97-02-PLAN (migration/service primitives — can now reference the event)
  - 97-03-PLAN (payment.succeeded webhook callsite — legally emits referral_bonus_accrued)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INFRA-15 pre-registration: LOCKED event + typed payload committed before any callsite"
    - "Pydantic extra='forbid' + Literal discriminator for role validation"
    - "TDD RED (test commit) -> GREEN (implementation already in Task 1) gate sequence"

key-files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_payloads.py

key-decisions:
  - "resource_type='referral' for referral_bonus_accrued follows Phase 96 referral-domain precedent"
  - "role: Literal['referrer','referee'] discriminates the two sides of a bilateral bonus without separate event names"
  - "referral_capture_id field serves as idempotency anchor (mirrors online_payment_id in LoyaltyRedeemedPayload)"

patterns-established:
  - "INFRA-15 v2.6 block in LOCKED_AUDIT_EVENTS: append new event inside the same comment block as Phase 96 sibling events"
  - "Bilateral audit payloads use a Literal role discriminator rather than two distinct event names"

requirements-completed: [REFER-04]

# Metrics
duration: 12min
completed: 2026-06-08
---

# Phase 97 Plan 01: Referral Bonus Accrued — Audit Pre-Registration Summary

**LOCKED audit event `referral_bonus_accrued` pre-registered with typed Pydantic payload and 7-assertion unit test suite, satisfying INFRA-15 before any callsite exists**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-08
- **Completed:** 2026-06-08
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Appended `("referral_bonus_accrued", "referral")` to `LOCKED_AUDIT_EVENTS` v2.6 block in `audit.py`, satisfying INFRA-15 for Phase 97
- Added `ReferralBonusAccruedPayload` class with `extra='forbid'`, six typed fields, and `Literal["referrer", "referee"]` role discriminator after `ReferralCapturedPayload` in `audit_payloads.py`
- Mapped `("referral_bonus_accrued", "referral"): ReferralBonusAccruedPayload` in `AUDIT_PAYLOAD_SCHEMAS`
- Extended `tests/unit/test_audit_payloads.py` with 7 assertions covering registration, both valid roles, and three negative validation cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Register referral_bonus_accrued + add ReferralBonusAccruedPayload** - `edbccd2b` (feat)
2. **Task 2 RED: Add failing tests for registration + payload contract** - `785ef137` (test)

_Note: Task 2 is TDD. The test commit (RED gate) was made first; tests pass against Task 1 implementation (GREEN confirmed immediately after: 7 passed)._

## Files Created/Modified

- `apps/backend/app/core/audit.py` — appended `("referral_bonus_accrued", "referral")` to v2.6 block in `LOCKED_AUDIT_EVENTS`
- `apps/backend/app/core/audit_payloads.py` — added `ReferralBonusAccruedPayload` class + registry entry in `AUDIT_PAYLOAD_SCHEMAS`
- `apps/backend/tests/unit/test_audit_payloads.py` — added 7 test functions + `ReferralBonusAccruedPayload` import

## Decisions Made

- `resource_type="referral"` follows Phase 96 referral-domain precedent (not `"loyalty"` — the bonus is referral-domain even though it lands in `loyalty_ledger`)
- `role: Literal["referrer", "referee"]` as a discriminator field within a single payload class (not two separate event names) — consistent with Phase 97 design: one event, two rows per webhook
- `referral_capture_id` is mandatory (not optional) in the payload to enforce idempotency-anchor visibility in audit records

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Worktree had no `.env` file, causing `YooKassaSettings()` module-level init to fail when running pytest. Resolved by copying `.env` from the main checkout (`.env` is gitignored; this is expected for fresh worktrees). Pre-existing issue, not caused by this plan's changes.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- INFRA-15 gate satisfied: Plans 97-02 and 97-03 can now safely reference `referral_bonus_accrued` in migrations and callsites without `AuditEventNotLockedError`
- No blockers

## Self-Check

Verified:
- `apps/backend/app/core/audit.py` — `("referral_bonus_accrued", "referral")` is present
- `apps/backend/app/core/audit_payloads.py` — `ReferralBonusAccruedPayload` class defined + registry entry present
- `apps/backend/tests/unit/test_audit_payloads.py` — 7 new test functions added
- Commits `edbccd2b` and `785ef137` exist in worktree git log
- `uv run python -c "..."` assertion passed: OK
- `mypy --strict`: Success: no issues found in 2 source files
- `ruff check`: All checks passed
- `lint-imports`: Contracts: 3 kept, 0 broken
- `pytest -k "referral_bonus_accrued or ReferralBonusAccrued" -q`: 7 passed

## Self-Check: PASSED

---
*Phase: 97-reward-crediting*
*Completed: 2026-06-08*
