---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "01"
subsystem: api
tags: [fastapi, online-payments, protocol-slot, composition-root, yookassa, audit]

requires:
  - phase: 49-online-payments
    provides: _sell_subject / sell_membership / sell_pt_package + OnlinePayment model
  - phase: 68-client-auth-foundation
    provides: ClientPrincipal, require_client, cc_client_* cookies
  - phase: 70-client-bookings-qr-self-check-in
    provides: Phase 70 complete — checkout plan 71-01 execution unblocked

provides:
  - _sell_subject_core actor-agnostic helper in app.modules.online_payments.service
  - register_client_checkout_core / invoke_client_checkout_core Protocol slot in app.core.dependencies
  - Composition-root wiring of _sell_subject_core into the client checkout slot in app.main

affects:
  - 71-02-PLAN (client_portal checkout + status endpoints — will call invoke_client_checkout_core)
  - Phase 72 (OpenAPI handoff + drift gate; relies on staff contract byte-identical after refactor)

tech-stack:
  added: []
  patterns:
    - Protocol-slot triplet (SellSubjectCoreCallable + register_client_checkout_core + invoke_client_checkout_core) mirroring UserLoader/ClientLoader pattern in app.core.dependencies
    - Actor-agnostic helper with actor_user_id=UUID|None; None passes the D-41-10 system-emit path for client-initiated calls
    - Caller-supplied idempotency key passed to _sell_subject_core; thin wrappers derive server-side key then delegate

key-files:
  created: []
  modified:
    - apps/backend/app/modules/online_payments/service.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/main.py

key-decisions:
  - "D-71-01 extraction: _sell_subject_core accepts actor_user_id: UUID | None and idempotency_key: str; no amount/price parameter (CPAY-03 server-authoritative price)"
  - "D-71-02 attribution: created_by_user_id=actor_user_id=None for client-initiated; audit.emit() already supports None via D-41-10 system-emit path — no fake staff user invented"
  - "D-20-MODULE compliance: SellSubjectCoreCallable uses Callable[..., Awaitable[Any]] — avoids any app.modules.online_payments import inside app.core; lint-imports 0 new ignore_imports"
  - "Staff callers sell_membership / sell_pt_package refactored as thin wrappers that derive the idempotency key then delegate — staff public signatures byte-identical to contract-freeze-v1.11.0"

patterns-established:
  - "Actor-agnostic core helper: parameterise actor_user_id as UUID | None; None is the client-initiated path; never invent a fake staff user"
  - "Caller-derived idempotency key: the core accepts the key as a parameter; each caller (staff membership, staff PT, future client) determines its key strategy externally"

requirements-completed: [CPAY-01, CPAY-02, CPAY-03, CPAY-04, CPAY-05]

duration: 5min
completed: "2026-05-30"
---

# Phase 71 Plan 01: Extract _sell_subject_core + Protocol Slot Summary

**Actor-agnostic `_sell_subject_core` helper extracted from `_sell_subject`, with `invoke_client_checkout_core` Protocol slot wired at composition root — enabling client_portal checkout without importing online_payments internals (D-20-MODULE).**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-30T15:01:20Z
- **Completed:** 2026-05-30T15:06:34Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Extracted `_sell_subject_core` from `_sell_subject` body: email gate, server-side price read, replay check, ЮKassa create, DB insert with `created_by_user_id=actor_user_id` (nullable for client path), and the ROOT+CHILD audit chain — all now in one actor-agnostic helper
- Refactored `sell_membership` and `sell_pt_package` as thin wrappers that derive the per-day idempotency key and delegate to `_sell_subject_core` with `actor_user_id=actor.id`; staff public signatures and behavior byte-identical to `contract-freeze-v1.11.0`
- Added `register_client_checkout_core` / `invoke_client_checkout_core` Protocol slot triplet to `app.core.dependencies`, using `Callable[..., Awaitable[Any]]` so no runtime import of `app.modules.online_payments` occurs — lint-imports stays clean with zero new `ignore_imports`
- Wired `_sell_subject_core` into the slot at composition root in `app/main.py`; 55 online_payments integration tests pass

## Task Commits

1. **Task 1: Extract _sell_subject_core actor-agnostic helper** - `99949f72` (feat)
2. **Task 2: Register client_checkout_core Protocol slot + composition-root wiring** - `26b196dc` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `apps/backend/app/modules/online_payments/service.py` - New `_sell_subject_core` helper; refactored `sell_membership` / `sell_pt_package` as thin wrappers
- `apps/backend/app/core/dependencies.py` - New `SellSubjectCoreCallable` type alias, `_client_checkout_core` slot, `register_client_checkout_core`, `invoke_client_checkout_core`
- `apps/backend/app/main.py` - Added `register_client_checkout_core` to top-level import; added composition-root wiring call after Phase 70 QR slot

## Decisions Made

- Used `Callable[..., Awaitable[Any]]` for `SellSubjectCoreCallable` instead of a TYPE_CHECKING-guarded `SellResponse` reference, because import-linter follows `TYPE_CHECKING` branches as static dependencies and the `core-not-depend-on-modules` contract would break. `Any` return type at the core slot scope; caller casts.
- Kept `_derive_idempotency_key` call in both `sell_membership` and `sell_pt_package` wrappers (membership and PT-package both use the server-side per-day key for the staff path; the client PT-package path will supply a client-generated key in Plan 71-02).

## Deviations from Plan

None - plan executed exactly as written.

The only implementation decision point was the `TYPE_CHECKING` approach for `SellResponse`: the plan specified a TYPE_CHECKING-guarded import, but import-linter statically follows `TYPE_CHECKING` branches. Resolved by using `Callable[..., Awaitable[Any]]` instead — the plan's intent (zero runtime import of `app.modules.online_payments` inside `app.core`) is fully preserved; this is a valid implementation of the described approach, not a deviation.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `_sell_subject_core` is accessible via `invoke_client_checkout_core` for Plan 71-02's `client_portal` checkout service
- Staff online_payments tests all green — staff contract preserved
- lint-imports, mypy, ruff all pass on all three modified files
- Plan 71-02 (client_portal checkout + status endpoints) can proceed immediately

## Self-Check

- `apps/backend/app/modules/online_payments/service.py` — modified, `_sell_subject_core` defined at line 170
- `apps/backend/app/core/dependencies.py` — modified, `register_client_checkout_core` at line 1676
- `apps/backend/app/main.py` — modified, `register_client_checkout_core(_sell_subject_core)` at line 601
- Commit `99949f72` — feat(71-01): extract _sell_subject_core actor-agnostic helper
- Commit `26b196dc` — feat(71-01): register client_checkout_core Protocol slot + composition-root wiring

## Self-Check: PASSED

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
