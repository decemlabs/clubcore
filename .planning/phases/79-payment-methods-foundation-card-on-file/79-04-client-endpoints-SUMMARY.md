---
phase: 79-payment-methods-foundation-card-on-file
plan: 04
subsystem: backend-api
tags: [fastapi, sqlalchemy, pydantic, payment-methods, idor, csrf, consent-gate, integration-test]

# Dependency graph
requires:
  - phase: 79-02
    provides: payment_methods.service (get_payment_method / unlink_payment_method / patch_autopay)
  - phase: 79-03
    provides: webhook step 8.5 (card rows seeded via save_payment_method path)
provides:
  - GET /client/payment-method: 200/null token-free (D-69-03 empty-state)
  - DELETE /client/payment-method: 204 idempotent soft-delete (no YooKassa call)
  - PATCH /client/payment-method/autopay: ФЗ-376 consent-gated enable / ungated disable
  - IDOR isolation: 200/null + 204 no-op + 409 (anti-oracle, never 404)
  - Endpoint behavior test suite (8 tests: GET-null, token-absence, DELETE idempotency, autopay consent gate)
  - IDOR sweep extension (3 tests: GET/DELETE/PATCH cross-client isolation)
affects:
  - client PWA — PAYM-02/03/04 user-facing surface

# Tech tracking
tech-stack:
  added: []
  patterns:
    - RBAC-04 dependency ordering: require_client() → verify_client_csrf → get_db on DELETE/PATCH
    - D-69-03 empty-state: GET returns 200/null (never 404) when no active card
    - D-32-10/D-49-19 caller-owns-txn: service never commits; router commits after mutate
    - D-20-IDOR: client_id always from require_client() principal; no URL/body param
    - T-79-13 token exclusion: response_model excludes yookassa_method_id; test asserts absence
    - T-79-14 consent gate: 409 consent_required surfaces ФЗ-376 gate from service layer
    - Anti-oracle IDOR: non-owned resource collapses to 200/null (GET), 204 no-op (DELETE), 409 (PATCH) — never 404
    - importlinter Option B: client_portal.router → payment_methods.schemas ignore edge (schema-only boundary cross)

key-files:
  modified:
    - apps/backend/app/modules/client_portal/router.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/.importlinter
    - apps/backend/tests/integration/client_portal/test_idor_sweep.py
  created:
    - apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py

key-decisions:
  - "Thin pass-through pattern in client_portal.service (matching promo_codes precedent): service wraps payment_methods.service; two pre-declared ignore edges matched"
  - "client_portal.router → payment_methods.schemas ignore edge added: schemas-only import for type annotations; keeps router free of business logic from payment_methods module"
  - "ruff I001 resolved: import blocks are properly sorted; no pre-existing I001 violation detected after Plan 79-03 additions"
  - "CSRF double-submit for DELETE/PATCH IDOR tests: Cookie header must include both cc_client_access AND clubcore_client_csrf; X-CSRF-Token header must match cookie value"
  - "ConflictError response format: code='conflict', message=reason-string — assertions use body['message'] not body['code']"

# Metrics
duration: 25min
completed: 2026-06-03
---

# Phase 79 Plan 04: Client Payment-Method Endpoints Summary

**Three IDOR-safe payment-method endpoints (GET/DELETE/PATCH) with ФЗ-376 consent gate, token-free responses, and full behavior + IDOR-sweep test coverage**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-03T13:00:00Z
- **Completed:** 2026-06-03T13:25:19Z
- **Tasks:** 3
- **Files modified:** 4
- **Files created:** 1

## Accomplishments

- **Task 1 — Endpoints + service wiring + ruff I001 fold:**
  - `GET /client/payment-method`: `response_model=ResponseEnvelope[ClientPaymentMethodResponse | None]`; 200/null (D-69-03); no CSRF dep; client_id from principal only
  - `DELETE /client/payment-method`: 204; RBAC-04 ordering (require_client → verify_client_csrf → get_db); idempotent no-op via `payment_methods.service.unlink_payment_method`; NO YooKassa call; caller commits
  - `PATCH /client/payment-method/autopay`: RBAC-04 ordering; 409 consent_required (ФЗ-376) / 409 no_active_payment_method; caller commits
  - Three thin pass-through functions added to `client_portal.service` (matching promo_codes precedent)
  - `importlinter`: `client_portal.router → payment_methods.schemas` edge added; two pre-declared `client_portal.service → payment_methods.*` edges matched
  - ruff I001: import blocks verified sorted; no violations
  - ruff + mypy + lint-imports: all 0 (3 contracts kept)

- **Task 2 — Endpoint behavior tests (8 tests):**
  - GET no-card → 200 + null (D-69-03)
  - GET with card → display fields (last4/brand/expiryMonth/expiryYear/autopayEnabled/consentRecordedAt); token string absent (T-79-13)
  - DELETE → 204; subsequent GET → null; second DELETE → 204 no-op (idempotency)
  - PATCH enable + consent → 200, autopayEnabled=True, consentRecordedAt stamped
  - PATCH enable without consent → 409 consent_required (ФЗ-376 gate, T-79-14)
  - PATCH enable no-card → 409 no_active_payment_method
  - PATCH disable → 200, autopayEnabled=False, consentRecordedAt preserved

- **Task 3 — IDOR sweep extension (3 tests):**
  - GET: client A → 200/null when B has a card; B's row untouched; never 404
  - DELETE: client A → 204 no-op; B's card remains active (unlinked_at IS NULL verified)
  - PATCH: client A → 409 no_active_payment_method (A has no card); B's card untouched
  - `_auth_with_csrf` helper extracts (access_token, csrf_token) from verify response cookies
  - `_seed_active_card_for_idor` / `_fetch_card_active` helpers for victim-data isolation

## Files Created/Modified

- `apps/backend/app/modules/client_portal/router.py` — Three endpoints (GET/DELETE/PATCH) + payment_methods.schemas import
- `apps/backend/app/modules/client_portal/service.py` — Three thin pass-throughs + payment_methods.service import
- `apps/backend/.importlinter` — client_portal.router → payment_methods.schemas ignore edge
- `apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py` — 8 endpoint behavior tests (created)
- `apps/backend/tests/integration/client_portal/test_idor_sweep.py` — 3 IDOR payment-method tests + helpers

## Decisions Made

- Thin pass-through pattern in `client_portal.service` — matches promo_codes precedent; two pre-declared ignore edges from Plan 79-02 matched automatically
- `client_portal.router → payment_methods.schemas` ignore edge — schemas-only import for type annotations keeps business logic boundary clean
- ConflictError response format confirmed: `code="conflict"`, `message=reason-string` — assertions use `body["message"]` not `body["code"]`
- CSRF double-submit for IDOR sweep DELETE/PATCH: `Cookie` header must include both `cc_client_access` AND `clubcore_client_csrf` when sending via raw header (not httpx cookie jar)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CSRF cookie missing from raw Cookie header in IDOR sweep**
- **Found during:** Task 3 (first pytest run on IDOR sweep)
- **Issue:** The `async_client` fixture uses raw `Cookie` headers (not an httpx cookie jar). When sending DELETE/PATCH requests with only `cc_client_access` in the Cookie header, `verify_client_csrf` reads `request.cookies.get("clubcore_client_csrf")` as None → 403 csrf_mismatch
- **Fix:** Changed Cookie header to include both `cc_client_access={access_a}; clubcore_client_csrf={csrf_a}` and set `X-CSRF-Token: {csrf_a}` header
- **Files modified:** `tests/integration/client_portal/test_idor_sweep.py`
- **Commit:** a0786917

**2. [Rule 1 - Bug] Fixed ConflictError assertion format**
- **Found during:** Task 2 (first pytest run on endpoint tests)
- **Issue:** Test asserted `body["code"] == "consent_required"` but ConflictError uses `code="conflict"` (class-level) and puts the reason string in `message`. Actual response: `{"code":"conflict","message":"consent_required",...}`
- **Fix:** Changed assertions to `body["message"] == "consent_required"` / `body["message"] == "no_active_payment_method"`
- **Files modified:** `tests/integration/client_portal/test_payment_method_endpoints.py`
- **Commit:** f570c2e1

## Threat Surface Scan

All threat mitigations from the plan's STRIDE register confirmed implemented:

| Threat | Mitigation Status |
|--------|-------------------|
| T-79-11 (BOLA/IDOR) | MITIGATED: client_id from require_client() only; 200/null + 204 no-op + 409 — never 404; proven by test_idor_sweep.py 3 new cases |
| T-79-12 (CSRF) | MITIGATED: verify_client_csrf dep on DELETE + PATCH in RBAC-04 order; confirmed by CSRF-mismatch 403 in deviated test run |
| T-79-13 (Token disclosure) | MITIGATED: response_model excludes yookassa_method_id; test asserts token string absent from GET response body |
| T-79-14 (Consent bypass) | MITIGATED: 409 consent_required surfaces from service layer; test asserts gate is enforced |

## Known Stubs

None. All three endpoints are fully wired to `payment_methods.service` → `payment_methods.repository` → DB.

## Self-Check: PASSED

Files verified:
- apps/backend/app/modules/client_portal/router.py: FOUND
- apps/backend/app/modules/client_portal/service.py: FOUND
- apps/backend/.importlinter: FOUND
- apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py: FOUND
- apps/backend/tests/integration/client_portal/test_idor_sweep.py: FOUND

Commits verified:
- 5e0edc88 (task 1 — endpoints + service wiring): FOUND
- f570c2e1 (task 2 — endpoint behavior tests): FOUND
- a0786917 (task 3 — IDOR sweep extension): FOUND
