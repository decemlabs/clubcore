---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "02"
subsystem: api
tags: [fastapi, yookassa, client-portal, online-payments, idor, idempotency, csrf]

# Dependency graph
requires:
  - phase: 71-01
    provides: invoke_client_checkout_core Protocol slot in app.core.dependencies
  - phase: 68-client-auth-foundation
    provides: ClientPrincipal, require_client, verify_client_csrf
  - phase: 49-online-payments
    provides: _sell_subject_core (now exposed as _client_checkout_core slot)

provides:
  - POST /api/v1/client/checkout/memberships/{plan_id} (CPAY-01, 201, server-derived idempotency key)
  - POST /api/v1/client/checkout/pt-packages/{plan_id} (CPAY-02, 201, client-supplied Idempotency-Key)
  - GET /api/v1/client/payments/{payment_id}/status (CPAY-03, anti-oracle coarse status)
  - ClientCheckoutRequest, ClientCheckoutResponse, ClientPaymentStatusResponse schemas
  - fetch_client_payment_status raw-SQL IDOR-safe reader in client_portal repository

affects:
  - 71-03 (integration tests that verify the three endpoints)
  - 71-04 (OpenAPI regen picks up new client paths)
  - Phase 72 (client-portal tag freeze, _v20Checks guards)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Protocol-slot write: client_portal delegates checkout to invoke_client_checkout_core; zero new ignore_imports (D-20-MODULE)
    - Anti-oracle IDOR: raw-SQL SELECT id,status WHERE id=:payment_id AND client_id=:client_id; NotFoundError 404-collapse on None
    - Idempotency split by subject: membership=server-derived per-day sha256 key (D-71-04); PT=client-supplied Idempotency-Key header
    - CSRF ordering: POST checkout endpoints require verify_client_csrf after require_client(); GET status endpoint has no CSRF dep (RBAC-04)

key-files:
  created: []
  modified:
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/client_portal/repository.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/client_portal/router.py

key-decisions:
  - "D-71-04 idempotency split honored: _derive_membership_idempotency_key mirrors the sell-membership:{plan}:{client}:{today_iso} sha256 formula from online_payments.service; PT-package passes client-supplied header straight through"
  - "actor_user_id=None for all client-initiated checkout calls (D-71-02); online_payments.created_by_user_id is nullable; audit.emit accepts None per D-41-10 system-emit path"
  - "ClientCheckoutRequest body is empty (plan_id from path, idempotency_key from header for PT); no amount/price field (CPAY-03 server-authoritative price inside the core)"
  - "404-collapse for non-owned payment status: fetch_client_payment_status returns None for non-owned rows; service raises NotFoundError('payment_not_found') — anti-oracle"

patterns-established:
  - "IDOR-safe coarse status read: SELECT id, status only + mandatory :client_id bind; 404-collapse at service layer — never 403 or existence-signal for non-owned rows"
  - "Checkout via Protocol slot: service calls invoke_client_checkout_core with all params; result.online_payment_id + result.confirmation_url mapped to ClientCheckoutResponse"

requirements-completed: [CPAY-01, CPAY-02, CPAY-03, CPAY-04, CPAY-05]

# Metrics
duration: 4min
completed: "2026-05-30"
---

# Phase 71 Plan 02: Client Checkout Endpoints + IDOR-Safe Status Reader Summary

**Three client ЮKassa checkout + status endpoints under `/api/v1/client` delegating via `invoke_client_checkout_core` Protocol slot, with anti-oracle raw-SQL status reader and idempotency split by subject type (server-derived for membership, client-supplied for PT-package).**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-30T15:09:32Z
- **Completed:** 2026-05-30T15:14:11Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `ClientCheckoutRequest` (empty body), `ClientCheckoutResponse` (`online_payment_id` + `confirmation_url`), `ClientPaymentStatusResponse` (`id` + `status`) to `schemas.py`
- Added `fetch_client_payment_status` to `repository.py`: raw SQL `SELECT id, status FROM online_payments WHERE id = :payment_id AND client_id = :client_id` — IDOR filter + anti-oracle (id+status only; no `OnlinePayment` ORM import per D-20-MODULE)
- Added `client_checkout_membership`, `client_checkout_pt_package`, `get_client_payment_status` service functions; checkout delegates via `invoke_client_checkout_core` with `actor_user_id=None`; membership uses server-derived per-day key; PT uses client-supplied key
- Added three router endpoints: `POST /checkout/memberships/{plan_id}` (201, CSRF), `POST /checkout/pt-packages/{plan_id}` (201, CSRF, `Idempotency-Key` header), `GET /payments/{payment_id}/status` (no CSRF); all with `client_` operation_id prefix

## Task Commits

1. **Task 1: Schemas + IDOR-safe raw-SQL status reader** - `685226f1` (feat)
2. **Task 2: Service write-slot + status read, and router endpoints** - `23637f27` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `apps/backend/app/modules/client_portal/schemas.py` - Added ClientCheckoutRequest, ClientCheckoutResponse, ClientPaymentStatusResponse
- `apps/backend/app/modules/client_portal/repository.py` - Added fetch_client_payment_status (raw-SQL, IDOR-filtered, anti-oracle)
- `apps/backend/app/modules/client_portal/service.py` - Added client_checkout_membership, client_checkout_pt_package, get_client_payment_status; added imports for invoke_client_checkout_core, YooKassaSettings, ClientPrincipal, NotFoundError
- `apps/backend/app/modules/client_portal/router.py` - Added three endpoints + imports for Header, YooKassaSettings, get_yookassa_settings, new schemas

## Decisions Made

- `ClientCheckoutRequest` has no fields: plan_id comes from path param, and for PT the idempotency key comes from the `Idempotency-Key` header (D-71-04). No amount in body (CPAY-03 price authority inside core).
- `_derive_membership_idempotency_key` directly mirrors the formula in `online_payments.service._derive_idempotency_key` (SHA256 of `sell-membership:{plan_id}:{client_id}:{today_iso}` with UTC date) — ensures same replay behavior as the staff path.
- The `cast(Any, result)` pattern for accessing `SellResponse` fields matches the existing service pattern (Protocol slot returns `Any` at the core scope to avoid cross-module import violation).

## Deviations from Plan

None - plan executed exactly as written.

The only implementation note: the `from app.core.dependencies import ClientPrincipal` was consolidated into the existing `from app.core.dependencies import (...)` block and the `from app.core.exceptions` import was expanded to multi-line format. These are formatting/organization choices, not deviations.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Three client endpoints exist under `/api/v1/client` and are ready for integration testing (Plan 71-03)
- `invoke_client_checkout_core` is called correctly with all required params; the core's email gate, replay check, and ЮKassa create are exercised via the existing slot
- `lint-imports`, `mypy`, `ruff` all pass on all four modified files with zero new `ignore_imports`
- Plan 71-04 can regen `openapi.json` + `schema.d.ts` after these endpoints are committed

## Known Stubs

None. The endpoints delegate to the production `_sell_subject_core` slot (wired in Plan 71-01) and the raw-SQL reader is complete.

## Threat Flags

No new threat surface beyond what is modeled in the plan's `<threat_model>`:
- T-71-05 (Information Disclosure) mitigated: SELECT id,status only + 404-collapse
- T-71-06 (Tampering) mitigated: no amount in request body; price read server-side in core
- T-71-07/T-71-08 (DoS/double-charge) mitigated: idempotency split by subject type
- T-71-09 (CSRF) mitigated: POST endpoints carry verify_client_csrf; GET status does not
- T-71-10 (54-ФЗ bypass) mitigated: email gate inside core raises ClientEmailRequiredForOnlinePaymentError

## Self-Check

- `apps/backend/app/modules/client_portal/schemas.py` — `class ClientCheckoutResponse` with `confirmation_url` and `online_payment_id`: FOUND
- `apps/backend/app/modules/client_portal/schemas.py` — `class ClientPaymentStatusResponse` with `id` and `status`: FOUND
- `apps/backend/app/modules/client_portal/repository.py` — `fetch_client_payment_status` with SQL containing `id = :payment_id AND client_id = :client_id`: FOUND
- `apps/backend/app/modules/client_portal/service.py` — `client_checkout_membership`, `client_checkout_pt_package`, `get_client_payment_status`: FOUND
- `apps/backend/app/modules/client_portal/router.py` — POST `/checkout/memberships/{plan_id}`, POST `/checkout/pt-packages/{plan_id}`, GET `/payments/{payment_id}/status`: FOUND
- Commit `685226f1` — feat(71-02): add checkout schemas + IDOR-safe payment-status reader: FOUND
- Commit `23637f27` — feat(71-02): add client checkout + status endpoints under /api/v1/client: FOUND

## Self-Check: PASSED

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
