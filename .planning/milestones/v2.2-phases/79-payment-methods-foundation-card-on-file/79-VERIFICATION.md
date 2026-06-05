---
phase: 79-payment-methods-foundation-card-on-file
verified: 2026-06-03T14:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "End-to-end card save against YooKassa sandbox"
    expected: >
      Checking out with savePaymentMethod=true in the PWA sends
      save_payment_method=true to YooKassa create_payment, the sandbox returns a
      real bank_card payment_method, payment.succeeded fires, and
      client_payment_methods receives a row with the real token + last4/brand/expiry.
      GET /client/payment-method returns display data (e.g. •••• 4821).
    why_human: >
      Requires live YooKassa sandbox credentials (OPERATOR-PENDING by design in this
      project). The entire save path is integration-tested with respx mocks and real
      Postgres, but the actual YooKassa HTTP roundtrip — including whether
      save_payment_method=true is accepted and the bank_card object is returned — can
      only be confirmed against the live sandbox.
---

# Phase 79: Payment Methods Foundation + Card-on-File — Verification Report

**Phase Goal:** Клиент может привязать карту через чекаут и управлять ею через новые client-portal endpoints.
**Verified:** 2026-06-03T14:00:00Z
**Status:** human_needed (all automated checks pass; one live-credential check deferred)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After successful checkout with `save_payment_method=true`, a row with token, last4, and brand appears in `client_payment_methods`; PAN/CVV never stored | VERIFIED | Webhook step 8.5 in `handlers.py:537-590`; INSERT uses only token+display fields from `YooKassaPaymentMethodInfo`; `test_webhook_save_true_upserts_card_token` passes asserting token, last4, brand, expiry, autopay=false, consent=NULL |
| 2 | `GET /client/payment-method` returns display data or null; `yookassa_method_id` absent from response | VERIFIED | `fetch_active_payment_method` SELECT list explicitly omits `yookassa_method_id` (line 43-44 of repository.py); `ClientPaymentMethodResponse` schema has no such field; `test_get_payment_method_with_card_returns_display_fields` asserts both the field name and the fake token string are absent from response body |
| 3 | `DELETE /client/payment-method` sets `unlinked_at` (soft-delete) and `autopay_enabled=false`; no YooKassa API call; subsequent GET returns null | VERIFIED | `unlink_payment_method` in `repository.py:63-98` uses SELECT FOR UPDATE + UPDATE setting `unlinked_at=now(), autopay_enabled=false`; no YooKassa client import in `service.py` or `repository.py`; `test_delete_payment_method_soft_deletes_and_returns_null` and `test_delete_payment_method_idempotent_no_op` both pass (28 tests total) |
| 4 | `PATCH /client/payment-method/autopay` enables `autopay_enabled=true` only with `consent_recorded_at`; disable is ungated | VERIFIED | `patch_autopay` in `service.py:56-98` raises `ConflictError("consent_required")` on enable without `consent_acknowledged`; `stamp_consent=(payload.enabled and payload.consent_acknowledged)` only writes consent on consented enable; `test_patch_autopay_enable_with_consent_succeeds`, `test_patch_autopay_enable_without_consent_returns_409`, and `test_patch_autopay_disable_ungated` all pass |
| 5 | All four endpoints IDOR-safe: client sees only own card; 404-collapse (anti-oracle: 200/null, 204 no-op, 409) on non-owned client_id | VERIFIED | `client_id` sourced exclusively from `require_client()` principal in all three endpoints; `test_payment_method_get_idor` (200/null not 404), `test_payment_method_delete_idor` (204 no-op, B's card untouched), `test_payment_method_patch_idor` (409 no_active_payment_method, B's card untouched) all pass |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `apps/backend/alembic/versions/0052_client_payment_methods.py` | Migration creating table + partial unique index + column | VERIFIED | Creates `client_payment_methods` with all 9 business columns; partial UNIQUE `uq_client_payment_methods_client_id_alive` on `(client_id) WHERE unlinked_at IS NULL`; adds `save_payment_method` column to `online_payments` |
| `apps/backend/app/modules/payment_methods/models.py` | ClientPaymentMethod ORM model | VERIFIED | Maps table 1:1 including partial unique index in `__table_args__`; `yookassa_method_id` column present with "NEVER serialized to the client" comment |
| `apps/backend/app/modules/payment_methods/repository.py` | Token-free raw-SQL reads + soft-delete + autopay mutation | VERIFIED | `fetch_active_payment_method` SELECT omits `yookassa_method_id`; `unlink_payment_method` uses SELECT FOR UPDATE; `set_autopay` conditionally stamps `consent_recorded_at`; `for_update=True` param added (WR-79-03 fix) |
| `apps/backend/app/modules/payment_methods/schemas.py` | Token-free response schema + consent-gated request schema | VERIFIED | `ClientPaymentMethodResponse` has 7 display fields, no token; `ClientAutopayPatchRequest` extends `BackendSchemaBase` (extra='forbid', WR-01 fix applied) |
| `apps/backend/app/modules/payment_methods/service.py` | Consent-gated service with 409 discipline | VERIFIED | `patch_autopay` raises `ConflictError("no_active_payment_method")` and `ConflictError("consent_required")`; uses `for_update=True` on fetch |
| `apps/backend/app/integrations/yookassa/types.py` | `YooKassaPaymentMethodInfo` dataclass + `payment_method` field on `YooKassaPaymentResult` | VERIFIED | Frozen dataclass with `id/last4/card_type/expiry_month/expiry_year`; `payment_method: YooKassaPaymentMethodInfo | None = None` on `YooKassaPaymentResult` |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` | Webhook step 8.5 raw-SQL upsert with CASE-guarded consent preservation (CR-79-01) | VERIFIED | Step 8.5 at lines 537-590; ON CONFLICT uses inference-predicate form; CASE guard preserves `autopay_enabled`/`consent_recorded_at` when token unchanged, resets on new token |
| `apps/backend/app/modules/client_portal/router.py` | Three endpoints GET/DELETE/PATCH with RBAC-04 dependency ordering | VERIFIED | `client_get_payment_method` (GET, no CSRF dep), `client_delete_payment_method` (DELETE, require_client→verify_client_csrf→get_db), `client_patch_payment_method_autopay` (PATCH, same order); all at lines 794-864 |
| `apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py` | 8 endpoint behavior tests | VERIFIED | Tests for GET-null, GET-with-card+token-absence, DELETE soft-delete, DELETE idempotency, PATCH-enable+consent, PATCH-enable-no-consent 409, PATCH-enable-no-card 409, PATCH-disable ungated |
| `apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py` | 5 webhook save tests (including CR-79-01 consent preservation) | VERIFIED | test 1: save=true row; test 2: save=false no row; test 3: replay idempotency (two distinct payments, one active row); test 4: same-token re-save preserves consent; test 5: new-token re-save resets consent |
| `apps/backend/tests/integration/client_portal/test_idor_sweep.py` | 3 IDOR payment-method sweep tests | VERIFIED | GET/DELETE/PATCH IDOR isolation confirmed; anti-oracle behavior (no 404 leaks) verified |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ClientCheckoutRequest.save_payment_method` | `online_payments.save_payment_method` column | kwargs threading through `client_portal.service` → `online_payments.service._sell_subject_core` → `insert_online_payment` | WIRED | Field traced: `client_portal/schemas.py` → `client_portal/router.py:597,641` → `client_portal/service.py` → `online_payments/service.py:_sell_subject_core` → `online_payments/repository.py:insert_online_payment` |
| `online_payments.save_payment_method` | `client_payment_methods` row via step 8.5 | `handlers.py` reads `row.save_payment_method` + `result.payment_method`, then raw-SQL upsert | WIRED | `if row.save_payment_method and result.payment_method is not None` guard at `handlers.py:537`; upsert follows |
| `client_portal/router.py` payment-method endpoints | `payment_methods.service` | `client_portal.service` pass-throughs (Option B direct import, importlinter ignore edges) | WIRED | `client_portal.service` imports `_payment_methods_service`; three pass-throughs at lines ~945-980; importlinter has three ignore edges declared |
| `GET /client/payment-method` response | excludes `yookassa_method_id` | `fetch_active_payment_method` SELECT omits column; `ClientPaymentMethodResponse` schema omits field | WIRED | Double mitigation: SQL-layer omission + schema-layer omission + test assertion |
| `DELETE /client/payment-method` | soft-delete only (no YooKassa HTTP call) | `unlink_payment_method` repository has no integrations import | WIRED | `repository.py` imports only `sqlalchemy`; `service.py` imports only `repository` and `schemas`; confirmed by grep |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `GET /client/payment-method` handler | `result` from `service.get_payment_method` | `repository.fetch_active_payment_method` raw-SQL SELECT from `client_payment_methods WHERE client_id=:client_id AND unlinked_at IS NULL` | Yes — DB query with client_id bind | FLOWING |
| `DELETE` soft-delete | `unlinked_at=now()` | `repository.unlink_payment_method` SELECT FOR UPDATE + UPDATE against real row | Yes — DB mutation | FLOWING |
| `PATCH autopay` | `autopay_enabled`, `consent_recorded_at` | `repository.set_autopay` UPDATE with conditional consent stamp | Yes — DB mutation | FLOWING |
| Webhook step 8.5 upsert | `yookassa_method_id`, `last4`, `brand`, `expiry_*` | `result.payment_method` from `YooKassaClient.get_payment` re-fetch (respx-mocked in tests, live endpoint in production) | Yes in tests (mock); live requires YooKassa sandbox | FLOWING (tests); HUMAN for live |

### Behavioral Spot-Checks

All checks performed by running the integration test suite directly against a real Postgres 16 instance.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 28 Phase 79 integration tests pass | `uv run pytest tests/integration/client_portal/test_payment_method_endpoints.py tests/integration/client_portal/test_payment_method_webhook_save.py tests/integration/client_portal/test_idor_sweep.py -q` | `28 passed in 15.97s` | PASS |
| ruff clean on all Phase 79 files | `uv run ruff check app/modules/payment_methods/ app/api/v1/_internal/yookassa/handlers.py app/modules/client_portal/router.py ...` | `All checks passed!` | PASS |
| mypy --strict on payment_methods module | `uv run mypy --strict app/modules/payment_methods/` | `Success: no issues found in 5 source files` | PASS |
| importlinter contracts | `uv run lint-imports` | `core must not import modules KEPT; modules cannot import each other KEPT (5 warnings); integrations must not import modules KEPT` | PASS |

### Probe Execution

No probe scripts declared in PLAN files. Phase 79 uses pytest integration tests instead.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| PAYM-01 | 79-01, 79-03 | Token capture from webhook; only token+display fields stored | SATISFIED | Migration columns confirmed; webhook step 8.5 inserts token+last4+brand+expiry; tests assert PAN/CVV absent (never in `YooKassaPaymentMethodInfo`) |
| PAYM-02 | 79-02, 79-04 | GET returns display data or 200/null; `yookassa_method_id` never returned | SATISFIED | SELECT omits token; schema omits field; test asserts both field-name and token-value absent from response |
| PAYM-03 | 79-01, 79-04 | DELETE is local soft-delete via `unlinked_at`; IDOR-safe | SATISFIED | `unlink_payment_method` sets `unlinked_at=now()`; no YooKassa import in service; IDOR sweep test passes |
| PAYM-04 | 79-02, 79-04 | Autopay toggle; enable requires ФЗ-376 consent (`consent_recorded_at`); no real charges in v2.2 | SATISFIED | `patch_autopay` gates on `consent_acknowledged`; stamps `consent_recorded_at=now()`; no charge code exists |
| PAYM-05 | Phase 81 | PWA `linkedCard` flag + `CardSheet` real-endpoint wiring | DEFERRED | Out of scope for Phase 79 per CONTEXT.md; traceability table maps to Phase 81 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| No debt markers found in Phase 79 files | — | — | — | — |

Scanned: `payment_methods/{repository,schemas,service,models}.py`, `handlers.py`, `client_portal/router.py`. No TBD/FIXME/XXX/HACK/PLACEHOLDER found. No empty implementations. No hardcoded stub returns.

**Review issues addressed (from 79-REVIEW.md):**

| Issue | Severity in Review | Status |
|-------|--------------------|--------|
| CR-01: Webhook re-save silently resets autopay consent | BLOCKER | FIXED — CASE guard preserves `autopay_enabled`/`consent_recorded_at` when token matches; tests 4+5 in `test_payment_method_webhook_save.py` cover both paths |
| WR-01: `ClientAutopayPatchRequest` used wrong base class | WARNING | FIXED — now extends `BackendSchemaBase` (extra='forbid'); docstring updated |
| WR-02: Replay-idempotency test never exercised upsert twice | WARNING | FIXED — test 3 seeds two distinct `succeeded` payments for same client, both reach step 8.5 |
| WR-03: `set_autopay` lacked row locking | WARNING | FIXED — `fetch_active_payment_method(for_update=True)` added to `patch_autopay` service path |
| WR-04, WR-05, WR-06 | WARNING | Informational improvements; WR-04 (empty-string fallback), WR-05 (2-digit year), WR-06 (same-day replay intent mismatch) are latent/low-risk; not blocking |
| IN-01, IN-02, IN-03, IN-04 | INFO | Cosmetic/style; no functional impact |

### Human Verification Required

#### 1. Live YooKassa sandbox end-to-end card save

**Test:** Check out via the PWA client with `savePaymentMethod: true` (or send a direct `POST /api/v1/client/checkout/membership` with `"savePaymentMethod": true`) using valid YooKassa sandbox credentials. Complete the redirect confirmation flow. Wait for `payment.succeeded` webhook delivery.

**Expected:** After the webhook fires, `GET /client/payment-method` returns a 200 with non-null `data` containing real `last4`, `brand`, and `expiryYear` values from YooKassa. The `yookassa_method_id` field must not appear anywhere in the response body. PAN/CVV must never appear.

**Why human:** Live YooKassa sandbox credentials are OPERATOR-PENDING by design in this project. The entire save path is tested with `respx` mocks and a real Postgres 16 instance (28 passing tests), but the actual YooKassa HTTP round-trip — whether `save_payment_method=true` is accepted by the sandbox, whether the `bank_card` `payment_method` object is returned in `payment.succeeded`, and whether the redirect confirmation flow completes — requires live operator-configured sandbox credentials.

### Gaps Summary

No gaps found. All five success criteria are met by the codebase:

1. **SC-1 (token save after checkout):** Migration 0052 creates `client_payment_methods`; webhook step 8.5 upserts token+display fields on `save_payment_method=true`; INSERT values come only from `YooKassaPaymentMethodInfo` (no PAN/CVV path exists); test passes.
2. **SC-2 (GET display-only, no token):** Repository SELECT omits `yookassa_method_id`; response schema omits field; test asserts both field-name and token-value absent.
3. **SC-3 (DELETE soft-delete, no YooKassa call):** `unlink_payment_method` sets `unlinked_at` + `autopay_enabled=false`; idempotent no-op on absent card; no YooKassa client import; test confirms subsequent GET is null and second DELETE is 204.
4. **SC-4 (autopay consent gate):** `patch_autopay` raises `ConflictError("consent_required")` on enable without `consent_acknowledged`; disable is ungated; tests cover all four cases.
5. **SC-5 (IDOR-safe):** `client_id` from `require_client()` principal only; anti-oracle responses (200/null, 204 no-op, 409); three IDOR sweep tests pass.

The CR-01 critical review finding (consent wipe on re-save) was fixed before this verification: the CASE-guarded upsert preserves autopay/consent when the token is unchanged and resets it on a new token, with two dedicated tests covering both branches.

---

_Verified: 2026-06-03T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
