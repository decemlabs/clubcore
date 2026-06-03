---
phase: 79-payment-methods-foundation-card-on-file
plan: 04
type: execute
wave: 3
depends_on: ["79-02", "79-03"]
files_modified:
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py
  - apps/backend/tests/integration/client_portal/test_idor_sweep.py
autonomous: true
requirements: [PAYM-02, PAYM-03, PAYM-04]
must_haves:
  truths:
    - "GET /client/payment-method returns 200 + display data, or 200 + null when no card; token never present"
    - "DELETE /client/payment-method returns 204, soft-deletes, disables autopay, and is idempotent"
    - "PATCH /client/payment-method/autopay enables only with consent (409 otherwise) and disables ungated"
    - "All four endpoints are IDOR-safe: client_id from principal only; non-owned card -> null/404 (anti-oracle)"
    - "Pre-existing ruff I001 in client_portal/router.py is resolved"
  artifacts:
    - path: "apps/backend/app/modules/client_portal/router.py"
      provides: "GET/DELETE/PATCH payment-method endpoints"
      contains: "/payment-method"
    - path: "apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py"
      provides: "Endpoint behavior tests (GET-null, DELETE idempotency, autopay consent gate)"
      contains: "consent_required"
  key_links:
    - from: "apps/backend/app/modules/client_portal/router.py"
      to: "payment_methods.service via client_portal.service"
      via: "require_client() principal -> service call"
      pattern: "require_client\\(\\)"
    - from: "apps/backend/app/modules/client_portal/router.py"
      to: "verify_client_csrf"
      via: "DELETE + PATCH state-changing dep ordering"
      pattern: "verify_client_csrf"
---

<objective>
Expose the four client-portal endpoints: `GET /client/payment-method` (200/null, token-free),
`DELETE /client/payment-method` (204, idempotent soft-delete), and `PATCH
/client/payment-method/autopay` (consent-gated). Wire them through `client_portal.service` to the
`payment_methods` module (Plan 02), enforce IDOR + RBAC-04 + caller-owns-txn discipline, fold the
pre-existing `ruff I001` in `client_portal/router.py`, and prove behavior with integration tests
(GET-null, DELETE idempotency, autopay consent gate, IDOR sweep).

Purpose: This is the user-facing surface delivering PAYM-02/03/04 and the IDOR-safety guarantees.
Output: 3 endpoints, service wiring, ruff I001 fix, endpoint + IDOR tests.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-CONTEXT.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md
@apps/backend/app/modules/payment_methods/schemas.py
@apps/backend/app/modules/payment_methods/service.py

<interfaces>
<!-- Contracts the executor builds against. Extracted from Plan 02 + codebase. -->
payment_methods.service (Plan 02): get_payment_method(session, client_id) -> ClientPaymentMethodResponse|None;
unlink_payment_method(session, client_id) -> None (idempotent); patch_autopay(session, client_id, payload:
ClientAutopayPatchRequest) -> ClientPaymentMethodResponse. Raises ConflictError("no_active_payment_method")
/ ConflictError("consent_required"). Service never commits (caller owns txn).

client_portal/router.py existing patterns:
  - ClientPrincipal + Depends(require_client()) — client.id is the only client_id source (D-20-IDOR).
  - verify_client_csrf dep on state-changing methods; RBAC-04 order: require_client() -> verify_client_csrf -> get_db.
  - ResponseEnvelope[...] + envelope(...) helper; 200/null via response_model=ResponseEnvelope[X | None].
  - GET membership at lines 138-156 (200/null analog); client_cancel_booking lines ~395-430 (DELETE 204 +
    csrf analog); client_update_me lines ~743-780 (PATCH analog). Router commits after service mutate.
  - Pre-existing ruff I001 on the client_portal.schemas import block (lines ~49-72) — fold the fix.
  - Router is included at /client prefix (app/api/v1/router.py line 103).

client_portal/service.py: the orchestration layer that the router calls; per the .importlinter edges
added in Plan 02, client_portal.service may import payment_methods.service + .repository. Add thin
pass-through functions OR call payment_methods.service directly from the router per the existing precedent
(mirror how promo flows are wired) — keep it consistent with the codebase.

Test infra: tests/integration/client_portal/conftest.py (authed-client fixture, csrf token helper, db
session, factories). test_idor_sweep.py is the existing multi-endpoint IDOR matrix to extend.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add GET/DELETE/PATCH endpoints + service wiring + ruff I001 fold</name>
  <files>apps/backend/app/modules/client_portal/router.py, apps/backend/app/modules/client_portal/service.py</files>
  <read_first>
    - apps/backend/app/modules/client_portal/router.py (GET membership 138-156; client_cancel_booking ~395-430; client_update_me ~743-780; the I001 import block ~49-72)
    - apps/backend/app/modules/client_portal/service.py (orchestration layer + how promo_codes.service is invoked)
    - apps/backend/app/modules/payment_methods/service.py (functions to call — Plan 02)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (router section lines 415-494 incl. the ruff I001 fold note)
  </read_first>
  <behavior>
    - GET /payment-method: require_client() only (no csrf — safe method); returns
      ResponseEnvelope[ClientPaymentMethodResponse | None]; envelope(None) when no active card (200/null,
      D-69-03); response never contains yookassa_method_id.
    - DELETE /payment-method: RBAC-04 order require_client() -> verify_client_csrf -> get_db; calls
      service unlink then session.commit(); returns 204 No Content; idempotent no-op when no active card;
      NO YooKassa API call.
    - PATCH /payment-method/autopay: RBAC-04 order; body ClientAutopayPatchRequest; calls patch_autopay
      then session.commit(); returns ResponseEnvelope[ClientPaymentMethodResponse]; 409 when no active
      card; 409 consent_required when enabling without consent_acknowledged; disable ungated.
    - All three: client_id sourced from client.id (principal) only — never URL/body.
  </behavior>
  <action>
    Add the three endpoints to client_portal/router.py following the analog patterns (operation_ids
    client_get_payment_method / client_delete_payment_method / client_patch_payment_method_autopay;
    summaries referencing PAYM-02/03/04 and the 409 codes). Import ClientPaymentMethodResponse +
    ClientAutopayPatchRequest from app.modules.payment_methods.schemas. Wire the handlers to
    payment_methods.service (directly, or via thin client_portal.service pass-throughs — match the existing
    promo precedent; whichever you choose, the .importlinter edges from Plan 02 already permit
    client_portal.service -> payment_methods.{service,repository}). Router commits after each mutating
    service call (caller-owns-txn). DELETE returns Response(status_code=204). Fold the pre-existing ruff
    I001: re-sort the client_portal.schemas import block alphabetically when adding the new imports so
    `ruff check` reports zero I001 in this file.
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app/modules/client_portal/router.py app/modules/client_portal/service.py && uv run mypy app/modules/client_portal/router.py app/modules/client_portal/service.py && uv run lint-imports</automated>
  </verify>
  <acceptance_criteria>
    - ruff check exits 0 with ZERO I001 on client_portal/router.py (the pre-existing debt is gone).
    - mypy + lint-imports exit 0.
    - grep confirms the three operation_ids and `/payment-method` + `/payment-method/autopay` routes.
    - GET handler uses ResponseEnvelope[ClientPaymentMethodResponse | None]; DELETE+PATCH carry
      verify_client_csrf; none accept a client_id param.
  </acceptance_criteria>
  <done>Three IDOR-safe endpoints wired to payment_methods.service; ruff I001 folded; ruff/mypy/imports clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Endpoint behavior tests — GET-null, DELETE idempotency, autopay consent gate</name>
  <files>apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py</files>
  <read_first>
    - apps/backend/tests/integration/client_portal/test_read_endpoints.py (200/null GET assertion style + authed-client fixture)
    - apps/backend/tests/integration/client_portal/test_client_booking.py (csrf-token usage on state-changing calls)
    - apps/backend/tests/integration/client_portal/conftest.py (fixtures + a helper to seed a client_payment_methods row)
  </read_first>
  <behavior>
    - GET with no card -> 200 + data null; response JSON contains NO yookassa_method_id (and no token value).
    - GET with a seeded active card -> 200 + last4/brand/expiry/autopay/consent fields; still no token.
    - DELETE on an existing card -> 204; subsequent GET -> 200 + null; DELETE again -> 204 (idempotent no-op).
    - PATCH enable with consent_acknowledged=true and an active card -> 200, autopay_enabled true,
      consent_recorded_at non-null.
    - PATCH enable with consent_acknowledged=false -> 409 consent_required; autopay stays false.
    - PATCH enable with no active card -> 409 no_active_payment_method.
    - PATCH disable -> 200, autopay_enabled false, consent_recorded_at unchanged (not cleared).
  </behavior>
  <action>
    Create `tests/integration/client_portal/test_payment_method_endpoints.py` covering all behaviors above
    using the authed-client + csrf fixtures and a card-seeding helper (insert a client_payment_methods row
    directly, or reuse the webhook path). Assert the token never appears in any response body (scan the
    serialized JSON for the seeded token string and assert absence). Use httpx ASGITransport +
    pytest-asyncio.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/client_portal/test_payment_method_endpoints.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - All endpoint tests pass (exit 0).
    - A test asserts the seeded token string is absent from GET response bodies.
    - DELETE idempotency (double DELETE -> 204 both times, GET null after) is asserted.
    - The consent-gate trio (enable+consent ok / enable-no-consent 409 / enable-no-card 409 / disable ungated) is asserted.
  </acceptance_criteria>
  <done>Endpoint behavior fully covered: GET-null, token-absence, DELETE idempotency, autopay consent gate.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: IDOR sweep — extend the cross-client anti-oracle matrix to payment-method endpoints</name>
  <files>apps/backend/tests/integration/client_portal/test_idor_sweep.py</files>
  <read_first>
    - apps/backend/tests/integration/client_portal/test_idor_sweep.py (the existing IDOR matrix — add the new endpoints in the same style)
    - apps/backend/tests/integration/client_portal/test_client_booking_idor.py (anti-oracle 404-collapse assertion idiom)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (require_client IDOR discipline lines 648-666)
  </read_first>
  <behavior>
    - Client B seeds an active card. Client A calls GET /client/payment-method -> 200 + null (A never sees
      B's card; client_id is bound to A's principal, not a param).
    - Client A calls DELETE -> 204 no-op; B's card remains active (verified by B's GET still returning it).
    - Client A calls PATCH autopay enable -> 409 no_active_payment_method (A has no card; B's card untouched).
    - No endpoint accepts a client_id param/body that could target B's row (anti-oracle: same response
      whether B's row exists or not — no existence leak).
  </behavior>
  <action>
    Extend test_idor_sweep.py with cases for GET/DELETE/PATCH payment-method asserting cross-client
    isolation per the existing sweep idiom: client A's calls operate only on A's (absent) card and never
    touch or reveal client B's card. Verify B's card is still active after A's DELETE/PATCH attempts.
    Reuse the two-client fixtures already used by the booking IDOR cases.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/client_portal/test_idor_sweep.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - The IDOR sweep passes including the new payment-method cases (exit 0).
    - A test asserts client B's card remains active after client A's DELETE/PATCH attempts.
    - No new endpoint exposes a client_id param (assertion that A's calls cannot target B's row).
  </acceptance_criteria>
  <done>Payment-method endpoints proven IDOR-safe (anti-oracle isolation) in the cross-client sweep.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → /client/payment-method API | All four endpoints cross from an authenticated-but-untrusted client into card state; principal is the only authority for client_id |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-79-11 | Elevation of Privilege (BOLA/IDOR) | GET/DELETE/PATCH payment-method | mitigate | client_id sourced from require_client() principal only; no client_id param/body; non-owned -> 200/null or 204 no-op (anti-oracle, no existence leak) — proven by test_idor_sweep additions |
| T-79-12 | Spoofing / CSRF | DELETE + PATCH (state-changing) | mitigate | verify_client_csrf dep in RBAC-04 order (require_client -> verify_client_csrf -> get_db), mirroring client_cancel_booking |
| T-79-13 | Information Disclosure | GET response token leak | mitigate | response_model uses token-free ClientPaymentMethodResponse; Task 2 asserts the token string is absent from response bodies |
| T-79-14 | Elevation of Privilege | Autopay enable without ФЗ-376 consent | mitigate | patch_autopay 409 consent_required (Plan 02) surfaced as a 409 at the endpoint; Task 2 asserts the gate |
| T-79-SC | Tampering | uv install (supply chain) | accept | No new packages this plan |
</threat_model>

<verification>
- ruff (zero I001 on router.py) + mypy + lint-imports exit 0.
- Endpoint behavior tests + IDOR sweep pass.
- Full phase regression: `uv run pytest tests/integration/client_portal -q` green.
</verification>

<success_criteria>
- GET returns 200/null token-free; DELETE 204 idempotent soft-delete (no YooKassa call); PATCH
  consent-gated enable / ungated disable.
- All four endpoints IDOR-safe (anti-oracle); pre-existing ruff I001 resolved.
</success_criteria>

<output>
Create `.planning/phases/79-payment-methods-foundation-card-on-file/79-04-SUMMARY.md` when done.
</output>
