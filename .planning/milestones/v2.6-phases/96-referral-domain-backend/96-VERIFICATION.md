---
phase: 96-referral-domain-backend
verified: 2026-06-08T14:00:00Z
status: passed
score: 5/5
overrides_applied: 0
re_verification: false
---

# Phase 96: Referral Domain Backend — Verification Report

**Phase Goal:** Клиент может получить персональный реферальный код и ссылку; друг может привязать реферера при регистрации; owner может настроить суммы бонусов через API
**Verified:** 2026-06-08T14:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /client/referral/code returns a stable, idempotent code and shareUrl; calling it twice returns the same code | VERIFIED | `service.get_or_create_referral_code`: reads existing via repository first; emits audit only on real insert; returns `{code, shareUrl}` where `shareUrl = f"{settings.pwa_base_url}/i/{code}"`. Integration test `test_get_referral_code_is_idempotent` passes (22/22 green). |
| 2 | POST /client/referral/capture binds referrer↔referee atomically; second call is a no-op (200); self-referral returns 422 | VERIFIED | `service.capture_referral`: idempotency gate (get_capture_by_referee) checked first; SelfReferralError(422) when `code_row.client_id == referee_principal_id`; ReferralCodeNotFoundError(404) for unknown codes; DB UNIQUE on `referee_client_id` defense-in-depth. Tests: `test_capture_is_idempotent_second_call_no_op`, `test_capture_self_referral_returns_422`, `test_capture_unknown_code_returns_404` all green. |
| 3 | GET /i/<code> resolves referral code; always 200; valid:false for unknown codes | VERIFIED | `service.resolve_public_code` never raises — returns `ReferralResolveResponse(valid=False, ...)` for unknown codes. `public_router` at `/i/{code}` has no auth dependency. Tests: `test_resolve_unknown_code_returns_200_valid_false`, `test_resolve_known_code_returns_valid_true`, `test_resolve_is_case_insensitive` all green. |
| 4 | Owner GET/PUT /referral/config works; reception gets 403; seed defaults 50000/30000 kopecks | VERIFIED | `owner_router`: GET+PUT both gated by `require_permission(Action.EDIT, Resource.GYM)`. RBAC-04: `actor` (require_permission) declared before `_csrf` (verify_csrf) in PUT function signature (router.py lines 168-169). Migration 0068 seeds `referrer_bonus_kopecks=50000`, `referee_welcome_kopecks=30000`. Tests: `test_owner_get_config_returns_seed_defaults`, `test_reception_get_config_forbidden`, `test_reception_put_config_forbidden`, `test_owner_put_config_without_csrf_fails`, `test_rbac04_reception_gets_403_before_csrf` all green. |
| 5 | LOCKED audit events referral_code_generated + referral_captured pre-registered before callsite (INFRA-15) | VERIFIED | Both pairs in `LOCKED_AUDIT_EVENTS` frozenset at audit.py lines 481-482, added in Plan 96-01 before service callsites landed in Plan 96-03. `ReferralCodeGeneratedPayload` and `ReferralCapturedPayload` with `extra="forbid"` in audit_payloads.py lines 1358-1385. Registry entries at lines 1493-1494. Unit test suite (8 tests) confirms lock + payload validation. `uv run pytest tests/unit/test_referral_audit_events.py` → 8 passed. |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/audit.py` | LOCKED_AUDIT_EVENTS extended with 2 v2.6 referral pairs | VERIFIED | Lines 479-483: v2.6 block with `("referral_code_generated","referral")` and `("referral_captured","referral")` |
| `apps/backend/app/core/audit_payloads.py` | ReferralCodeGeneratedPayload + ReferralCapturedPayload + registry entries | VERIFIED | Lines 1358-1385: two payload classes with `extra="forbid"`. Lines 1493-1494: AUDIT_PAYLOAD_SCHEMAS registry entries |
| `apps/backend/tests/unit/test_referral_audit_events.py` | 8 unit tests covering lock + payload validation | VERIFIED | 8 tests, all passing: lock assertion, payload validates, extra-field rejection, registry mapping for both pairs |
| `apps/backend/app/modules/referrals/models.py` | ReferralCode, ReferralCapture, ReferralConfig ORM models | VERIFIED | Three models with correct FK constraints (RESTRICT, literal names), UNIQUE constraints noted in migration |
| `apps/backend/app/modules/referrals/schemas.py` | Five wire schemas (camelCase) | VERIFIED | ReferralCodeResponse, ReferralResolveResponse, ReferralCaptureRequest, ReferralConfigResponse, ReferralConfigUpdateRequest — all present with correct field constraints |
| `apps/backend/alembic/versions/0067_referral_tables.py` | DDL for 3 tables + UNIQUE indexes | VERIFIED | Creates referral_config, referral_codes, referral_captures with `uq_referral_codes_code` (op.f()) and `uq_referral_captures_referee_client_id` (literal name, unconditional) |
| `apps/backend/alembic/versions/0068_seed_referral_config.py` | Singleton seed 50000/30000 kopecks | VERIFIED | `ON CONFLICT (id) DO NOTHING` with `CAST(:id AS uuid)` asyncpg pattern; seeds `referrer_bonus_kopecks=50000`, `referee_welcome_kopecks=30000` |
| `apps/backend/app/core/config.py` | pwa_base_url Settings field | VERIFIED | Line 139: `pwa_base_url: str = "http://localhost:5174"` |
| `apps/backend/app/modules/referrals/repository.py` | 5 caller-owns-txn ORM helpers | VERIFIED | `get_code_by_client_id`, `get_code_by_value`, `get_capture_by_referee`, `get_config`, `upsert_config` — no commit/flush, correct explicit type annotations |
| `apps/backend/app/modules/referrals/service.py` | 5 service functions + CROCKFORD_ALPHABET + typed errors | VERIFIED | `CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"` (32 chars, no O/I/L); 3 error classes; 5 service functions |
| `apps/backend/app/modules/referrals/router.py` | public_router, client_router, owner_router | VERIFIED | Three APIRouter instances; no try/except; RBAC-04 ordering confirmed (line 168 require_permission before line 169 verify_csrf) |
| `apps/backend/app/api/v1/router.py` | Three referral routers mounted | VERIFIED | Lines 129-135: Phase-96 block with `referral_public_router`, `referral_client_router` (prefix="/client"), `referral_owner_router` (prefix="/referral") |
| `apps/backend/tests/integration/test_alembic_0067_referral.py` | Schema + seed integration test | VERIFIED | 4 tests: tables exist, seed values correct, both UNIQUE indexes exist by exact name — all passing |
| `apps/backend/tests/integration/test_referral_code.py` | REFER-01 integration tests (5 tests) | VERIFIED | idempotency, Crockford format, single audit row on two calls, distinct codes, 401 gate |
| `apps/backend/tests/integration/test_referral_capture.py` | REFER-03 integration tests (6 tests) | VERIFIED | bind, audit, no-op idempotency, self-referral 422, unknown 404, IDOR principal proof |
| `apps/backend/tests/integration/test_referral_resolve.py` | REFER-02 backend integration tests (5 tests) | VERIFIED | valid:true + first name only, exact key set {valid, referrerFirstName, welcomeBonusKopecks}, unknown → 200/valid:false, case-insensitive |
| `apps/backend/tests/integration/test_referral_config.py` | REFER-07 integration tests (6 tests) | VERIFIED | seed defaults, PUT round-trip, reception 403, CSRF gate, RBAC-04 ordering |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py owner_update_referral_config` | `require_permission(EDIT, GYM)` before `verify_csrf` | Parameter declaration order (RBAC-04) | VERIFIED | Lines 168-169: `actor: Annotated[CurrentUser, Depends(require_permission(...))]` declared before `_csrf: Annotated[None, Depends(verify_csrf)]` |
| `service.capture_referral` | referee from principal only | `referee_principal_id` arg from `require_client()`, never body | VERIFIED | Function signature: `capture_referral(session, referee_principal_id, code_str)`. Router calls `service.capture_referral(session, client.id, payload.code)` — `client.id` is the principal. `ReferralCaptureRequest` has only `code: str` field, no id field (extra=forbid) |
| `app/api/v1/router.py` | `app/modules/referrals/router.py` | include_router x3 | VERIFIED | Lines 133-135: `v1.include_router(referral_public_router)`, `v1.include_router(referral_client_router, prefix="/client")`, `v1.include_router(referral_owner_router, prefix="/referral")` |
| `alembic 0068` | `alembic 0067` | down_revision chain | VERIFIED | 0068 `down_revision = "0067_referral_tables"` confirmed in file |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `service.get_or_create_referral_code` | `existing` / `code_row` | `repository.get_code_by_client_id` → ORM SELECT on referral_codes | Yes — DB query with client_id filter | FLOWING |
| `service.resolve_public_code` | `code_row`, `referrer_first_name` | `repository.get_code_by_value` → ORM SELECT; `text("SELECT first_name FROM clients WHERE id = :cid")` raw SQL | Yes — DB queries; fallback 0 on missing config | FLOWING |
| `service.capture_referral` | `existing_capture`, `code_row` | `repository.get_capture_by_referee` + `repository.get_code_by_value` → ORM SELECTs | Yes — DB queries; referee from principal arg | FLOWING |
| `service.get_referral_config` | `config` | `repository.get_config` → ORM SELECT LIMIT 1 | Yes — seeded by 0068 | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit tests: audit lock + payload validation | `uv run pytest tests/unit/test_referral_audit_events.py -q` | 8 passed in 0.02s | PASS |
| Alembic migration round-trip + schema | `uv run pytest tests/integration/test_alembic_0067_referral.py -q` | 4 passed in 0.93s | PASS |
| Integration: code mint idempotency + audit | `uv run pytest tests/integration/test_referral_code.py -q` | 5 passed | PASS |
| Integration: capture IDOR safety + self-referral + no-op | `uv run pytest tests/integration/test_referral_capture.py -q` | 6 passed | PASS |
| Integration: public resolver PII-minimal + always-200 | `uv run pytest tests/integration/test_referral_resolve.py -q` | 5 passed | PASS |
| Integration: owner config RBAC-04 + reception 403 + CSRF | `uv run pytest tests/integration/test_referral_config.py -q` | 6 passed | PASS |
| **Total** | All referral tests | **30 passed** (8 unit + 4 alembic + 22 integration) | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REFER-01 | 96-01, 96-02, 96-03 | Персональный стабильный реферальный код + shareable ссылка | SATISFIED | GET /client/referral/code idempotent; UNIQUE on code; shareUrl from pwa_base_url; 5 integration tests green |
| REFER-02 (backend) | 96-03 | Deep-link resolve endpoint GET /i/<code> | SATISFIED | `public_router` at `/i/{code}`, no auth, always 200, valid:false for unknown; 5 integration tests green |
| REFER-03 | 96-01, 96-02, 96-03 | Захват реферала при онбординге; self-referral блок; 1-bonus-per-referee | SATISFIED | capture_referral: idempotent + self-referral 422 + UNIQUE constraint at DB level; 6 integration tests green |
| REFER-07 | 96-02, 96-03 | Суммы конфигурируемы через owner-only API + seed | SATISFIED | Migration 0068 seeds 50000/30000; owner GET/PUT /referral/config with RBAC gate; 6 integration tests green |

---

## Security Verification

### IDOR Safety (T-96-05)

`ReferralCaptureRequest` schema has only a single field `code: str` (with `extra="forbid"` via `BackendSchemaBase`). No id/referee field is present or accepted. In `client_capture_referral`, the referee identity is passed exclusively as `client.id` from the `require_client()` principal: `service.capture_referral(session, client.id, payload.code)`. Integration test `test_capture_referee_from_principal_not_body` proves the DB row carries the principal's id regardless of body content.

### PII Exposure (T-96-06)

`resolve_public_code` fetches only `first_name` via raw SQL: `SELECT first_name FROM clients WHERE id = :cid`. The `ReferralResolveResponse` schema has exactly three fields: `valid`, `referrer_first_name`, `welcome_bonus_kopecks`. No `client_id`, `last_name`, `phone`, or other PII is returned. Integration test `test_resolve_known_code_no_pii_leakage` asserts the exact key set `{valid, referrerFirstName, welcomeBonusKopecks}` and explicitly asserts `clientId not in data` and `lastName not in data`.

### Anti-Enumeration (T-96-06)

Unknown codes return `200/valid:false` — never a 404 status code that would reveal code existence to unauthenticated callers. Confirmed in service code and tested by `test_resolve_unknown_code_returns_200_valid_false`.

---

## Anti-Patterns Found

No debt markers (TBD/FIXME/XXX) found in any phase-modified file. No placeholder implementations or stub returns detected. All service functions have substantive implementations with DB queries, audit emission, and error handling. No hardcoded empty arrays/objects flowing to rendering paths.

Notable annotations:
- `_ = actor` in `update_referral_config` and `owner_get_referral_config` is correctly documented as "reserved for future audit emit" — not a stub, a deliberate deferral per CONTEXT decision (config_updated audit event deferred to a later phase).

---

## Human Verification Required

None. All success criteria are verifiable programmatically and have been verified via automated tests and code inspection.

---

## Gaps Summary

No gaps. All 5 ROADMAP success criteria are fully satisfied with code evidence and passing automated tests (30 tests total, 0 failures).

---

_Verified: 2026-06-08T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
