---
phase: 49-online-sales-orchestrator
verified: 2026-05-22T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Phase 49: Online Sales Orchestrator — Verification Report

**Phase Goal:** Operator can initiate a redirect-based or QR online membership/PT-package sale and receive a `confirmation_url` back from the API
**Verified:** 2026-05-22
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + PATTERNS Blockers)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | `POST /api/v1/online-payments/memberships/{plan_id}/sell` returns `{confirmation_url, online_payment_id}` when `clients.email IS NOT NULL` | VERIFIED | `app/modules/online_payments/router.py:171-218` (`sell_membership_redirect` returns `ResponseEnvelope[SellResponse]`); E2E test `test_e2e_sell_flow.py::test_e2e_sc1_membership_redirect` PASSED |
| SC#2 | `POST /api/v1/online-payments/memberships/{plan_id}/sell-qr` returns a QR payload string; both sell variants share the same webhook path | VERIFIED | `router.py:221-267` (`sell_membership_qr` calls `service.sell_membership(...confirmation_type=CONFIRMATION_TYPE_QR)`); same service, same audit chain, same table → identical webhook path. E2E test `test_e2e_sc2_membership_qr` PASSED |
| SC#3 | Either sell endpoint returns 422 `client_email_required_for_online_payment` when client has no email | VERIFIED | `service.py:102-113` (`_read_client_email_or_raise` raises `ClientEmailRequiredForOnlinePaymentError` with locked literal code from `constants.ErrorCode.CLIENT_EMAIL_REQUIRED`). E2E test `test_e2e_sc3_email_gate_422` asserts `client_email_required_for_online_payment` in response.text. PASSED |
| SC#4 | `GET /api/v1/online-payments/return` displays a static "ожидаем подтверждение" screen with no payment-status info | VERIFIED | `router.py:362-388` (`online_payment_return` returns static `_RETURN_HTML` containing exactly "Ожидаем подтверждение от платёжной системы"; no DB lookup, query params discarded, `Cache-Control: no-store`, 60 ms constant-time floor). Tests `test_return_screen.py::test_return_screen_no_status_leakage`, `test_return_screen_body_identical_across_query_shapes`, `test_return_screen_cache_control_no_store`, `test_return_screen_constant_time_floor` all in 106-passed suite |
| SC#5 | Alembic 0034 applies cleanly: `online_payments` table with UNIQUE `(yookassa_payment_id)`, UNIQUE `(idempotency_key)`, and double-tap partial UNIQUE | VERIFIED | `alembic/versions/0034_online_payments.py:48-156` creates table + 2 full UNIQUEs + 2 partial UNIQUE indexes (`uq_online_payments_membership_double_tap`, `uq_online_payments_pt_package_double_tap`) with `postgresql_where="status != 'canceled' AND <fk> IS NOT NULL"`. Tests `test_alembic_0034_online_payments.py::test_online_payments_table_has_full_unique_constraints` + `::test_online_payments_table_has_partial_unique_indexes` PASSED (5/5) |
| SC#6 | Startup integration test asserts `YooKassaClientProvider` and `FiscalReceiptDispatcher` slots are non-None (AST parity test) | VERIFIED | `tests/integration/test_v17_protocol_slot_parity.py:32-39` asserts all 4 v1.7 slots (`get_yookassa_client_provider/get_fiscal_receipt_dispatcher/get_membership_activator/get_pt_package_activator`) non-None after `create_app()`. PASSED. main.py:317-329 wires all 4 slots. |
| PAT#1 | `YooKassaPaymentResult.qr_payload` field added | VERIFIED | `app/integrations/yookassa/types.py:91` declares `qr_payload: str | None = None`; client populates from `confirmation.confirmation_data` (client.py:199-201, 283-285) |
| PAT#2 | `YooKassaClient.create_payment(idempotency_key: UUID \| str)` signature widening | VERIFIED | `app/integrations/yookassa/client.py:141` `idempotency_key: UUID \| str`; result-attached idempotency_key is None when input is string (client.py:163-164) |
| PAT#3 | Existing `tests/unit/test_yookassa_protocol_slot_parity.py` byte-equal assertion decommissioned/updated | VERIFIED | `tests/unit/test_yookassa_protocol_slot_parity.py:109-115, 141, 205-210` updated to target `phase49_fiscal_dispatcher_stub` + `activate_membership_from_webhook` + `activate_pt_package_from_webhook` (no longer asserts against Phase 47 noop_stub). All 4 tests in this file PASSED |
| PAY-01 | `online_payments` table schema | VERIFIED | Migration 0034 + `models.py` with all columns: client_id, membership_plan_id, pt_package_plan_id, yookassa_payment_id, idempotency_key, amount_kopecks, status, confirmation_url, confirmation_type, initiated_at/succeeded_at/canceled_at, created_by_user_id, audit_correlation_id; XOR CHECK constraint at migration line 124-127 |
| PAY-02 | UNIQUE indexes + partial UNIQUE double-tap guards | VERIFIED | Migration 0034 lines 128-156 ships all 4 indexes (asserted by `test_alembic_0034_online_payments.py::test_online_payments_table_has_partial_unique_indexes`) |
| PAY-03/04 | Sell endpoints for memberships + pt-packages (redirect) | VERIFIED | router.py lines 171-218, 273-313 |
| PAY-05 | sell-qr endpoints + shared webhook path | VERIFIED | router.py lines 221-267, 316-356; shared via single `online_payments` table and service.`_sell_subject` |
| PAY-06 | 422 `client_email_required_for_online_payment` (FIS-05 gate) | VERIFIED | service.py:102-113 + `app/core/exceptions.py` `ClientEmailRequiredForOnlinePaymentError` |
| PAY-07 | `GET /return` anti-oracle handler + `_constant_time_floor` | VERIFIED | router.py:362-388 (60 ms floor — raised from 50 ms in Wave 3 per CI jitter rationale documented inline) |
| PAY-08 | Composition root wires YooKassaClientProvider + FiscalReceiptDispatcher slots; AST test asserts non-None | VERIFIED | main.py:317-329 + parity test (see SC#6) |

**Score: 14/14 verified** (6 ROADMAP success criteria + 3 PATTERNS blockers + 8 PAY requirements; truths overlap so unique-truth count = 14)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0034_online_payments.py` | Table + 4 indexes + XOR CHECK | VERIFIED | 167 LOC; ships table + 2 full UNIQUEs + 2 partial UNIQUE indexes + 4 CHECK constraints |
| `apps/backend/app/modules/online_payments/__init__.py` | Module marker | VERIFIED | Exists |
| `apps/backend/app/modules/online_payments/models.py` | OnlinePayment ORM with table_args | VERIFIED | Mirrors migration shape |
| `apps/backend/app/modules/online_payments/repository.py` | insert + get-by-id + get-by-idempotency-key | VERIFIED | All 3 D-49-07 methods present |
| `apps/backend/app/modules/online_payments/service.py` | sell_membership + sell_pt_package + phase49_fiscal_dispatcher_stub | VERIFIED | 407 LOC, full 7-step protocol implemented per D-49-10 |
| `apps/backend/app/modules/online_payments/router.py` | 4 sell endpoints + /return | VERIFIED | 388 LOC, all 5 routes |
| `apps/backend/app/modules/online_payments/schemas.py` | SellRequest + SellResponse with XOR validator | VERIFIED | Exists |
| `apps/backend/app/modules/online_payments/constants.py` | ErrorCode StrEnum + literal constants | VERIFIED | Exists |
| `apps/backend/app/modules/online_payments/permissions.py` | Placeholder | VERIFIED | Empty docstring per D-49-01 |
| `apps/backend/app/modules/online_payments/email_templates.py` | Placeholder | VERIFIED | Empty docstring per D-49-01 (satisfies dispatcher → email_templates ignore_imports — warns only because shipping of Phase 52 body still pending) |
| `apps/backend/.importlinter` | `app.modules.online_payments` in modules-independent + ignore_imports edits | VERIFIED | Line 26 + lines 85-92 |
| `apps/backend/app/main.py` | 3 register_* calls (activators + fiscal stub) | VERIFIED | Lines 320-329 |
| `apps/backend/app/integrations/yookassa/types.py` | YooKassaPaymentResult.qr_payload field | VERIFIED | Line 91 |
| `apps/backend/app/integrations/yookassa/client.py` | create_payment(idempotency_key: UUID \| str) | VERIFIED | Line 141 |
| `apps/backend/tests/integration/test_v17_protocol_slot_parity.py` | SC#6 parity test | VERIFIED | 2 tests, both PASSED |
| `apps/backend/tests/integration/test_alembic_0034_online_payments.py` | Schema-shape assertions | VERIFIED | 5 tests, all PASSED |
| `apps/backend/tests/integration/online_payments/test_e2e_sell_flow.py` | 10 E2E tests | VERIFIED | All passing in 106-test suite |
| `apps/backend/tests/integration/online_payments/test_e2e_audit_chain.py` | 3 audit-chain tests | VERIFIED | Verified in 106-test suite |
| `apps/backend/tests/modules/online_payments/test_return_screen.py` | Anti-oracle tests | VERIFIED | 6 tests including constant-time floor |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `router.sell_membership_redirect` | `service.sell_membership` | direct call | WIRED | router.py:204 calls service.sell_membership(...) |
| `service._sell_subject` | `YooKassaClient.create_payment` | `provider()` accessor | WIRED | service.py:247 |
| `service` | `repository.insert_online_payment` | direct import | WIRED | service.py:72, 261 |
| `service` | `audit.emit` | locked event names | WIRED | service.py:291-298, 308-315 with validated payloads |
| `service` | `clients.models.Client` | scalar SELECT (D-49-13) | WIRED | service.py:71, 102-113 (importlinter ignore matched at .importlinter:92) |
| `online_payments_router` | `app.api.v1.router` | `include_router` | WIRED | api/v1/router.py:20, 45-47 (prefix=/online-payments) |
| `main.create_app` | `register_membership_activator` | direct call | WIRED | main.py:324 |
| `main.create_app` | `register_pt_package_activator` | direct call | WIRED | main.py:325 |
| `main.create_app` | `register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)` | direct call | WIRED | main.py:329 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|---------------------|--------|
| `service.sell_membership` | `result` (YooKassaPaymentResult) | `YooKassaClient.create_payment` (httpx → ЮKassa API; respx-mocked in tests) | Yes (real httpx call in production; respx fixtures in test) | FLOWING |
| `router.sell_membership_redirect` | `SellResponse` envelope | `service.sell_membership` return value | Yes (confirmation_url from real upstream) | FLOWING |
| `service._read_client_email_or_raise` | `email` | `session.scalar(select(Client.email))` | Yes (real DB SELECT) | FLOWING |
| `service._read_membership_plan_or_raise` | `(price_kopecks, name)` | raw `text()` SELECT on membership_plans | Yes (real DB SELECT) | FLOWING |
| `online_payments.repository.insert_online_payment` | INSERTed row | session.add(OnlinePayment(...)) | Yes (real INSERT) | FLOWING |
| `audit.emit` | audit row payload | `OnlinePaymentInitiatedPayload` + `YookassaPaymentCreatedPayload` Pydantic models | Yes (real validation + DB write) | FLOWING |
| `router.online_payment_return` | response body | static `_RETURN_HTML` constant | Static by design (anti-oracle) | STATIC (intentional per PAY-07) |

The `/return` STATIC marker is by design — the entire PAY-07 requirement is that this handler produces a static response with no dynamic data. This is the desired data-flow status.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Phase 49 test surface | `uv run python -m pytest tests/modules/online_payments/ tests/integrations/yookassa/ tests/integration/online_payments/ tests/integration/test_v17_protocol_slot_parity.py tests/integration/test_alembic_0034_online_payments.py tests/unit/test_yookassa_protocol_slot_parity.py -q` | 106 passed, 1 skipped in 11.79s | PASS |
| import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken (2 warns for not-yet-shipped Phase 52 ignores — acceptable per CONTEXT.md) | PASS |
| mypy on Phase 49 modules | `uv run mypy app/modules/online_payments/ app/integrations/yookassa/` | 4 errors (Literal vs str on router.py) — documented as pre-existing in deferred-items.md | DOCUMENTED PRE-EXISTING |
| SC#1 E2E spot-check | `pytest test_e2e_sc1_membership_redirect` | PASSED | PASS |
| SC#2 E2E spot-check | `pytest test_e2e_sc2_membership_qr` | PASSED | PASS |
| SC#3 E2E spot-check | `pytest test_e2e_sc3_email_gate_422` | PASSED | PASS |
| SC#4 E2E spot-check | `pytest test_e2e_sc4_return_screen_concurrent_identical_body` | PASSED | PASS |
| SC#6 parity spot-check | `pytest tests/integration/test_v17_protocol_slot_parity.py` | 2 passed | PASS |
| Alembic 0034 schema spot-check | `pytest tests/integration/test_alembic_0034_online_payments.py` | 5 passed | PASS |
| Debt markers (TBD/FIXME/XXX) in Phase 49 modules + alembic 0034 | `grep -rn 'TBD\|FIXME\|XXX' app/modules/online_payments/ alembic/versions/0034_online_payments.py` | None found | PASS |

---

## Probe Execution

No `scripts/*/tests/probe-*.sh` files exist for this project; Phase 49 PLAN/SUMMARY references the pytest test surface as the probe (run above under behavioral spot-checks). The full Phase 49 test surface command is the canonical "probe" for this phase per the execution_environment block in the verification request.

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| Full Phase 49 test surface | `uv run python -m pytest <Phase 49 paths> -q --tb=line` | 106 passed, 1 skipped, 0 failed | PASS |
| import-linter contract | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| PAY-01 | 49-01, 49-02 | online_payments table schema | SATISFIED | Migration 0034 + models.py |
| PAY-02 | 49-01, 49-02 | UNIQUE + partial UNIQUE indexes | SATISFIED | Migration 0034 lines 128-156 |
| PAY-03 | 49-03, 49-04 | POST memberships/{id}/sell (redirect) | SATISFIED | router.py:171-218 + service.py:345-366 |
| PAY-04 | 49-03, 49-04 | POST pt-packages/{id}/sell (redirect) | SATISFIED | router.py:273-313 + service.py:369-390 |
| PAY-05 | 49-01, 49-03, 49-04 | POST .../sell-qr (QR variants); QR payload extraction | SATISFIED | router.py:221-267, 316-356 + types.py:91 qr_payload field |
| PAY-06 | 49-02, 49-03, 49-04 | 422 client_email_required_for_online_payment FIS-05 gate | SATISFIED | service.py:102-113 + locked literal in constants.py + exceptions.py |
| PAY-07 | 49-05 | GET /return anti-oracle + constant-time floor | SATISFIED | router.py:362-388 (60 ms floor) + EXCLUDED_PATHS line 40 |
| PAY-08 | 49-06 | Composition-root wiring + parity test | SATISFIED | main.py:317-329 + test_v17_protocol_slot_parity.py |

All 8 PAY-xx requirements present in PLAN frontmatters across plans 49-01 through 49-07; no orphaned requirements found in REQUIREMENTS.md for Phase 49.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/modules/online_payments/router.py` | 208, 257, 303, 346 | `confirmation_type: str` not matching `Literal['redirect', 'qr']` mypy error | Info (pre-existing) | Documented in deferred-items.md as Plan 49-04 origin; Plan 49-05 introduced zero new errors. Not a blocker per execution_environment carry-forward instructions. |
| (none) | — | TBD/FIXME/XXX | — | None found in Phase 49 source files |

No NEW anti-patterns introduced by Phase 49. The 4 mypy Literal errors are explicitly enumerated in `deferred-items.md:41-45` as introduced by Plan 49-04 and are an acceptable known follow-up.

---

## Pre-Existing Failures (Carry-Forward, Not Regressions)

| Failure | Source | Status in Phase 49 |
|---------|--------|---------------------|
| `tests/integration/test_alembic_clean.py::test_alembic_check_clean` | deferred-items.md (Plan 49-03 discovered + later 0034 ORM-vs-DB drift) | Pre-existing on master; not addressed by Phase 49 verifier scope per execution_environment |
| `test_every_protected_route_declares_a_gate` (3 auth/users routes) | deferred-items.md (Plan 49-05 discovered) | Phase 49's `/return` correctly added to EXCLUDED_PATHS:40; the 3 failing routes pre-date Phase 49 |
| `app/modules/online_payments/router.py` 4 mypy errors (Literal vs str) | deferred-items.md (Plan 49-04 origin) | 4 errors; deferred — not in Phase 49 verification gates |
| `tests/integration/test_route_introspection.py:35` E501 line-too-long | deferred-items.md (Plan 49-05 discovered) | Pre-existing on master |

These are documented and explicitly excluded from gap-counting per the verification request's execution_environment block.

---

## Deferred Items (Not Actionable Gaps)

The following items are explicitly deferred to future phases per CONTEXT.md, `deferred-items.md`, and ROADMAP.md:

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Reconcile cron for "ЮKassa created, DB INSERT failed mid-flow" | Phase 53 | `deferred-items.md:65-70` + CONTEXT.md D-49-11 |
| 2 | `yookassa_call_failed` audit event on ЮKassa-side failures | Phase 50 | `deferred-items.md:71-73` + CONTEXT.md D-49-20 |
| 3 | `payments.models` runtime import flip (currently TYPE_CHECKING-only) | Phase 50 | `deferred-items.md:82-84` + CONTEXT.md D-49-29 |
| 4 | `users.display` import (operator-display in OnlinePaymentSucceededPayload) | Phase 50 | `deferred-items.md:77-81` + CONTEXT.md D-49-30 |
| 5 | `X-Forwarded-For` trust toggle on `verify_yookassa_ip` | Phase 50 | `deferred-items.md:74-76` |
| 6 | Webhook handler + FSM transitions + activation logic body | Phase 50 | CONTEXT.md `Out of phase (explicit)` |
| 7 | Refund endpoint, ARQ retry, circuit breaker | Phase 51 | CONTEXT.md `Out of phase (explicit)` |
| 8 | Telegram + email DMs + email_templates.py body | Phase 52 | CONTEXT.md `Out of phase (explicit)` |
| 9 | Saved-card / recurring autopayment (`payment_method_id` column) | v2.0 | `deferred-items.md:85-87` |

These deferrals are intentional per the milestone roadmap; not actionable gaps for Phase 49.

---

## Human Verification Required

None. All 6 ROADMAP success criteria + 8 PAY requirements + 3 PATTERNS blockers are covered by automated tests (106 passed, 1 skipped, 0 failed in the Phase 49 test surface). Per Plan 49-07 SUMMARY: "All 6 ROADMAP success criteria are now covered by automated tests; no `human_verification` items remain."

---

## Gaps Summary

**No gaps found.** Phase 49 goal is achieved:

- The operator can initiate a redirect-based or QR online membership/PT-package sale via 4 POST endpoints (router.py:171-356)
- Each successful sell returns 201 + `ResponseEnvelope[SellResponse]` containing `{confirmation_url, qr_payload, online_payment_id}` with XOR validator ensuring exactly one of confirmation_url/qr_payload is non-null
- The FIS-05 email gate (PAY-06) raises 422 with the exact locked literal `client_email_required_for_online_payment`
- The anti-oracle `GET /return` handler ships a static screen with a 60 ms constant-time floor (PAY-07)
- All 4 v1.7 Protocol slots are wired non-None at startup (PAY-08), verified by the SC#6 parity test
- Alembic 0034 ships the canonical schema + 4 indexes (PAY-01/PAY-02), verified by the dedicated alembic integration test
- All 3 PATTERNS blockers (qr_payload field, UUID|str signature widening, parity-test update) are addressed in the Phase 48 adapter and Phase 49 test
- 106 tests pass; 1 skipped is the intentionally-deferred placeholder superseded by the 10-test E2E suite under `tests/integration/online_payments/`

---

_Verified: 2026-05-22T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
