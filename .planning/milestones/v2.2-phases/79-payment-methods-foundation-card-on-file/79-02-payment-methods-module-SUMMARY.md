---
phase: 79-payment-methods-foundation-card-on-file
plan: 02
subsystem: backend-module
tags: [fastapi, sqlalchemy, pydantic, payment-methods, raw-sql, consent-gate]

# Dependency graph
requires:
  - phase: 79-01
    provides: ClientPaymentMethod ORM model + client_payment_methods table (migration 0052)
provides:
  - repository.fetch_active_payment_method: token-free raw-SQL read (unlinked_at IS NULL)
  - repository.unlink_payment_method: idempotent soft-delete (SELECT FOR UPDATE + UPDATE)
  - repository.set_autopay: autopay mutation with optional consent stamp
  - ClientPaymentMethodResponse schema: display fields only, yookassa_method_id excluded
  - ClientAutopayPatchRequest schema: enabled + consent_acknowledged fields
  - service.get_payment_method: 200/null empty-state (D-69-03)
  - service.unlink_payment_method: idempotent no-op wrapper
  - service.patch_autopay: ФЗ-376 consent gate (PAYM-04)
  - .importlinter: two forward-declared ignore edges for client_portal.service
affects:
  - 79-03 — webhook step 8.5 (raw SQL upsert; no service/repository import needed)
  - 79-04 — router endpoints call service.get_payment_method / unlink / patch_autopay

# Tech tracking
tech-stack:
  added: []
  patterns:
    - D-54-08 raw-SQL discipline: text() + :name binds + cast UUID to str + .mappings().one_or_none()
    - D-69-03 empty-state: get_payment_method returns None (200/null), not 404
    - D-32-10/D-49-19 caller-owns-txn: no session.commit() in repository or service
    - ФЗ-376 consent gate: patch_autopay raises ConflictError("consent_required") on enable without consent_acknowledged
    - Token exclusion: SELECT deliberately omits yookassa_method_id; response schema has no such field
    - Idempotent soft-delete: unlink_payment_method SELECT FOR UPDATE + bool return (True/False) discarded by service

key-files:
  created:
    - apps/backend/app/modules/payment_methods/repository.py
    - apps/backend/app/modules/payment_methods/schemas.py
    - apps/backend/app/modules/payment_methods/service.py
  modified:
    - apps/backend/.importlinter

key-decisions:
  - "Repository SELECT deliberately omits yookassa_method_id — both a code invariant and enforced by acceptance criteria grep"
  - "patch_autopay raises ConflictError('no_active_payment_method') for both enable and disable when no card exists (symmetric guard)"
  - "stamp_consent gated on payload.enabled AND payload.consent_acknowledged — disable path never touches consent_recorded_at"
  - "Two forward-declared ignore edges in importlinter (Option B direct edges mirroring promo_codes precedent) — unmatched_ignore_imports_alerting=warn keeps build green until Plan 79-04 ships"
  - "dict[str, Any] return type for fetch_active_payment_method satisfies mypy strict type-arg requirement"

# Metrics
duration: 15min
completed: 2026-06-03
---

# Phase 79 Plan 02: Payment Methods Module Summary

**Token-free raw-SQL repository + ФЗ-376 consent-gated service with client-safe Pydantic schemas for the payment_methods module, with two forward-declared importlinter ignore edges**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-03T12:45:00Z
- **Completed:** 2026-06-03T13:00:39Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `repository.py`: three raw-SQL functions following D-54-08 discipline
  - `fetch_active_payment_method`: SELECT without yookassa_method_id, returns `dict[str, Any] | None`
  - `unlink_payment_method`: SELECT FOR UPDATE + UPDATE soft-delete, idempotent (returns bool)
  - `set_autopay`: conditional consent_recorded_at stamp (only on consented enable)
- `schemas.py`: `ClientPaymentMethodResponse` (7 display fields, no token) + `ClientAutopayPatchRequest` (enabled + consent_acknowledged)
- `service.py`: three service functions with ФЗ-376 consent gate
  - `get_payment_method`: repository read → schema construction (None passes through for 200/null)
  - `unlink_payment_method`: idempotent wrapper (bool discarded; router returns 204 always)
  - `patch_autopay`: active-card check → consent check → set_autopay → re-fetch → return refreshed response
- `.importlinter`: two forward-declared `client_portal.service -> payment_methods.*` ignore edges
- All gates passed: ruff, mypy, lint-imports (3 contracts kept, 0 broken)

## Files Created/Modified

- `apps/backend/app/modules/payment_methods/repository.py` — Raw-SQL active-read + soft-delete + autopay mutation
- `apps/backend/app/modules/payment_methods/schemas.py` — Token-free response schema + autopay-patch request
- `apps/backend/app/modules/payment_methods/service.py` — Consent-gated service with 409 discipline
- `apps/backend/.importlinter` — Two forward-declared ignore edges for Plan 79-04 wiring

## Decisions Made

- `dict[str, Any]` return type for `fetch_active_payment_method` — mypy strict [type-arg] enforcement required explicit parameterization
- Symmetric `no_active_payment_method` guard for both enable and disable paths — prevents toggling a non-existent card regardless of direction
- `stamp_consent=(payload.enabled and payload.consent_acknowledged)` — disable path cleanly never stamps consent_recorded_at
- Option B direct ignore edges (forward-declared) — mirrors promo_codes precedent; `unmatched_ignore_imports_alerting=warn` prevents CI breakage before Plan 79-04 materializes the imports

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new threat surface beyond the plan's threat model:
- T-79-04 (token disclosure): SELECT omits yookassa_method_id; ClientPaymentMethodResponse has no such field (doubly mitigated)
- T-79-05 (consent bypass): patch_autopay raises ConflictError("consent_required") on enable without acknowledgement; consent_recorded_at stamped only on consented enable
- T-79-06 (IDOR): all repository functions filter by client_id (from principal in Plan 79-04); no row id accepted from caller

## Self-Check: PASSED

Files verified:
- apps/backend/app/modules/payment_methods/repository.py: FOUND
- apps/backend/app/modules/payment_methods/schemas.py: FOUND
- apps/backend/app/modules/payment_methods/service.py: FOUND

Commits verified:
- 9bdba963 (repository.py): FOUND
- 03a9e1d9 (schemas.py + service.py): FOUND
- 109d3d76 (.importlinter ignore edges): FOUND
