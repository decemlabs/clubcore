---
phase: 32-payment-ledger-sale-flow-refund
verified: 2026-05-15T00:00:00Z
status: passed
score: 5/5 ROADMAP success criteria verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "REF-02 — POST /api/v1/pt-packages/{id}/refund router endpoint"
    addressed_in: "Phase 33"
    evidence: "ROADMAP.md Phase 33 SC #3: 'POST /api/v1/pt-packages/{id}/refund (reception+owner per B-07) переиспользует payment_refunder Protocol slot'; REQUIREMENTS.md REF-02 explicitly: 'Defined in Phase 33 alongside pt_packages module but RBAC + Protocol slot wired in Phase 32'. Backend Protocol slot PaymentRefunder + MembershipRefundRequest schema landed in Phase 32 as contract."
  - truth: "REF-06 — Admin-web AlertDialog H-13 mitigation (Понимаю, что возврат необратим checkbox)"
    addressed_in: "Phase 35"
    evidence: "REQUIREMENTS.md REF-06 + FE-13 'Refund button on /memberships/$membershipId and /pt-packages/$pt_packageId detail pages. Opens AlertDialog per REF-06'. Phase 35 ROADMAP goal includes 'refund AlertDialog с H-13 mitigation'."
  - truth: "FE-10..18 admin-web sale-with-payment form / PaymentBadge / payment history blocks / mock parity"
    addressed_in: "Phase 35"
    evidence: "ROADMAP.md Phase 35 Requirements: FE-10..18 (9 reqs) — 'admin-web на VITE_API_MODE=http показывает обновлённый sale flow с записью оплаты, refund AlertDialog с H-13 mitigation'."
human_verification: []
---

# Phase 32: Payment Ledger + Sale Flow + Refund — Verification Report

**Phase Goal:** Каждая продажа абонемента фиксируется в append-only ledger с указанием суммы и принявшего сотрудника; reception/owner может выполнить возврат, который атомарно добавляет negative-amount row, переводит membership в `cancelled` со специальным `cancellation_reason='refunded'`, и эмитит forensic-traceable audit chain — без owner-approval gate (B-07 uniform reception).

**Verified:** 2026-05-15
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement — 5 ROADMAP Success Criteria

| # | Success Criterion | Status | Evidence |
|---|------|--------|----------|
| 1 | Migration `0012_payments.py` (UUIDv4 PK, signed amount, subject_kind CHECK, refund_of partial UNIQUE, NO updated_at/deleted_at — AST-guarded) | PASS | `apps/backend/alembic/versions/0012_payments.py` (135 lines): 9-column schema verbatim; CHECK `ck_payments_amount_sign_matches_subject_kind`; partial UNIQUE `uq_payments_refund_of_alive WHERE refund_of IS NOT NULL`; ALTER memberships ADD cancellation_reason TEXT NULL; ORM `Payment(Base, UUIDPkMixin)` ONLY — no TimestampMixin, no SoftDeleteMixin. AST walker `tests/unit/test_payments_appendonly.py` green (32 unit tests). down_revision = `0011_trainers`. |
| 2 | New `app/modules/payments/`; `record_payment`/`issue_refund` caller-owns-txn; Protocol slots `register_payment_recorder/refunder` exclusively from `create_app()`; `create_membership` consumes recorder with snapshot symmetry | PASS | `app/modules/payments/{__init__,constants,models,permissions,repository,router,schemas,service}.py` — 8 module files (real bodies, 13–294 LOC each, no stubs). `PaymentRecorder`/`PaymentRefunder` Protocol classes in `core/dependencies.py` + defensive-raise `get_payment_recorder()/get_payment_refunder()`. Wiring exclusively from `app/main.py` lines `register_payment_recorder(payments_service.record_payment)` + `register_payment_refunder(payments_service.issue_refund)`. `memberships/service.py:565` calls `get_payment_recorder()(... amount_kopecks=membership.price_kopecks_snapshot ...)` — server-derived symmetry, no client-supplied amount. |
| 3 | `POST /api/v1/memberships/{id}/refund` (reception+owner) body `{reason}`; 409 `must_unfreeze_first` / `cannot_refund_renewed_source`; atomic refund row + cancelled transition + cancellation_reason='refunded' + audit chain | PASS | Endpoint at `memberships/router.py:515` (`@router.post("/{membership_id}/refund", ...)`); orchestrator `refund_membership` at `memberships/service.py:690` performs sequence: frozen→`MustUnfreezeFirstError`; `has_renewal_descendants` → `CannotRefundRenewedSourceError`; `get_payment_refunder()` Protocol slot (no direct payments import); `cancellation_reason = CANCELLATION_REASON_REFUNDED`; `audit.emit("membership_refunded", ...)`. `MembershipRefundRequest` in `memberships/schemas.py:227` with `extra='forbid'` (rejects `amount_kopecks`). |
| 4 | `Idempotency-Key` required on POST /memberships; Redis cache `sz:idem:{key}` TTL 1h; replay returns cached; GET /payments owner-only + scoped GETs reception+owner; pagination envelope | PASS | `core/idempotency.py:35` `IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_:-]{1,128}$"`; `IDEMPOTENCY_REDIS_PREFIX = "sz:idem:"`; `verify_idempotency` + `begin_idempotency` (SET NX) + `load_idempotency_response` + `store_idempotency_response`. `memberships/router.py:297` `idempotency_key: Annotated[str, Depends(verify_idempotency)]`. `payments/router.py` — 3 GET endpoints: `/api/v1/payments` (owner-only), `/payments/by-client/{client_id}`, `/payments/by-membership/{membership_id}` (reception+owner via scoped Depends). Filters: subject_kind / subject_id / received_by_user_id / received_from / received_to (`repository.list_payments_filtered`). All return `PaginatedData` envelope. |
| 5 | REF-TEST-01 concurrent race: 2 POST /refund → exactly one succeeds via partial UNIQUE; audit chain traceable via `payment_row_hash` | PASS | `tests/integration/payments/test_payments_refund_race.py::test_concurrent_refund_loses_at_db_layer` PASSED. Audit chain: `tests/integration/payments/test_payments_refund_audit_chain.py` (3 tests) + `test_payments_audit_chain.py` (4 tests) all PASSED — verifies `payment_recorded → refund_issued → membership_refunded` ordering, `payment_row_hash` SHA-256 pattern on both events, deterministic hash, resource_id linkage. NOTE: ROADMAP SC #5 mentions `payment_refunded` but locked event is `refund_issued` (D-32-12 documented terminology drift; `LOCKED_AUDIT_EVENTS` has no `payment_refunded` entry — `refund_issued` is the actual locked name from Phase 30). |

**Score:** 5/5 ROADMAP success criteria verified

---

## Requirements Coverage Matrix (18 requirements)

| Req | Description | Plan | Status | Evidence |
|-----|-------------|------|--------|----------|
| PAY-01 | `payments` table schema | 32-01 | SATISFIED | `alembic/versions/0012_payments.py` columns + CHECK + FK match spec verbatim |
| PAY-02 | Partial UNIQUE `(refund_of) WHERE refund_of IS NOT NULL` | 32-01 | SATISFIED | `uq_payments_refund_of_alive` created with `postgresql_where=text("refund_of IS NOT NULL")` |
| PAY-03 | New `app/modules/payments/` module with caller-owns-txn services | 32-01 | SATISFIED | 8 module files; `service.record_payment` + `service.issue_refund` no internal `await session.commit()` |
| PAY-04 | Protocol slots `register_payment_recorder/refunder` exclusively from create_app() | 32-01 | SATISFIED | `core/dependencies.py` Protocol classes + register/get fns; `app/main.py` 2 wiring lines; NOT wired in `app/workers/telegram_bot.py` |
| PAY-05 | `create_membership` calls recorder; snapshot symmetry server-enforced | 32-02 | SATISFIED | `memberships/service.py:565` `amount_kopecks=membership.price_kopecks_snapshot` |
| PAY-06 | `GET /api/v1/payments` owner-only with filters | 32-01 | SATISFIED | `payments/router.py:38` global GET; `repository.list_payments_filtered` supports all 5 filters |
| PAY-07 | `GET /api/v1/clients/{id}/payments` reception+owner | 32-01 | SATISFIED | `payments/router.py:60` `/by-client/{client_id}` scoped Depends |
| PAY-08 | `GET /api/v1/memberships/{id}/payments` reception+owner | 32-01 | SATISFIED | `payments/router.py:86` `/by-membership/{membership_id}` scoped Depends |
| PAY-09 | `Idempotency-Key` required + Redis cache `sz:idem:{key}` 1h replay | 32-01/02 | SATISFIED | `core/idempotency.py` + `memberships/router.py:297` Depends(verify_idempotency); test suite `tests/integration/payments/test_idempotency.py` |
| PAY-10 | Audit event `payment_recorded` with payload + `payment_row_hash` | 32-02 | SATISFIED | `payments/service.py:127` emits literal; `core/audit_hash.py` `payment_row_hash`; integration tests verify pattern `^sha256:[0-9a-f]{64}$` |
| REF-01 | `POST /memberships/{id}/refund` atomic insert + transition + audit | 32-03 | SATISFIED | `memberships/router.py:515` endpoint + `service.py:690` orchestrator + `cancellation_reason='refunded'` sentinel applied |
| REF-02 | `POST /pt-packages/{id}/refund` (Phase 33 router; Phase 32 contract) | 32-01/03 | SATISFIED (contract) | `PaymentRefunder` Protocol slot accepts subject_kind agnostic signature; ready for pt_packages consumer in Phase 33. Router itself deferred to Phase 33 per REQUIREMENTS.md. |
| REF-03 | Frozen refund → 409 `must_unfreeze_first` (B-08) | 32-03 | SATISFIED | `MustUnfreezeFirstError` raised at `service.py:743` before generic transition check |
| REF-04 | Renewed-source → 409 `cannot_refund_renewed_source` (B-09) | 32-03 | SATISFIED | `has_renewal_descendants` EXISTS query at `memberships/repository.py:614`; `CannotRefundRenewedSourceError` at `service.py:747` |
| REF-05 | Schema rejects explicit `amount_kopecks` | 32-03 | SATISFIED | `MembershipRefundRequest` `extra='forbid'` in `memberships/schemas.py:227` |
| REF-06 | Admin-web AlertDialog + H-13 checkbox | — | DEFERRED | Phase 35 FE-13 |
| REF-07 | Audit `refund_issued` + `membership_refunded` (+ `payment_refunded` per ROADMAP typo) | 32-03 | SATISFIED | Literal `"refund_issued"` at `payments/service.py:200`; `"membership_refunded"` at `memberships/service.py:784`. Note: `payment_refunded` event NOT in `LOCKED_AUDIT_EVENTS` (D-32-12 ROADMAP terminology drift — actual locked event is `refund_issued`). |
| REF-08 | Postgres concurrent refund test REF-TEST-01 | 32-03 | SATISFIED | `tests/integration/payments/test_payments_refund_race.py` PASSED |

**Coverage:** 17/18 SATISFIED in Phase 32; 1/18 DEFERRED to Phase 33 (REF-02 router only); REF-06 deferred to Phase 35 (admin-web FE-13).

---

## Append-Only Invariant Compliance (B-01)

| Check | Result | Evidence |
|-------|--------|----------|
| No `update(Payment)` in payments/service.py | PASS | grep returned 0 matches (only docstring mentions as prohibition) |
| No `delete(Payment)` in payments/service.py | PASS | grep returned 0 matches |
| No `session.delete(<Payment>)` | PASS | grep returned 0 matches |
| No `on_conflict_do_update` in payments | PASS | grep returned 0 matches |
| Payment ORM uses UUIDPkMixin ONLY | PASS | `models.py` `class Payment(Base, UUIDPkMixin)` — NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin (no deleted_at) |
| AST walker `test_payments_appendonly.py` | PASS | Part of 32 unit tests passing in 0.05s |

---

## Audit Event Names Compliance

| Event | Required | Actual | Status |
|-------|----------|--------|--------|
| Sale payment-side | `payment_recorded` | `payment_recorded` (literal at `payments/service.py:127`) | LOCKED MATCH |
| Refund payment-side | `refund_issued` | `refund_issued` (literal at `payments/service.py:200`) | LOCKED MATCH |
| Refund subject-side | `membership_refunded` | `membership_refunded` (literal at `memberships/service.py:784`) | LOCKED MATCH |
| Sale subject-side | `membership_created` | `membership_created` (literal at `memberships/service.py:581`) | LOCKED MATCH |
| ROADMAP SC mention | `payment_refunded` | N/A — NOT in `LOCKED_AUDIT_EVENTS`; D-32-12 documented as ROADMAP terminology drift | DRIFT (acknowledged) |
| ROADMAP SC mention | `membership_sold` | N/A — replaced by `membership_created` per Phase 15 INFRA-11 AST gate | DRIFT (acknowledged) |

The two event-name drifts (`payment_refunded` / `membership_sold`) in ROADMAP SC #3/#5 are explicitly addressed in `32-CONTEXT.md` D-32-12 + Phase 30 `LOCKED_AUDIT_EVENTS` frozenset. Implementation correctly uses the locked names.

---

## Cross-Module Discipline (modules-independent)

| Check | Result |
|-------|--------|
| `memberships/service.py` does NOT import `app.modules.payments` | PASS — grep returned 0 matches |
| `memberships/router.py` does NOT import `app.modules.payments` | PASS — grep returned 0 matches |
| `memberships/repository.py` does NOT import `app.modules.payments` | PASS — grep returned 0 matches |
| `lint-imports` 3-contract result | PASS — `core must not import modules KEPT / modules cannot import each other KEPT / integrations must not import modules KEPT`; 3 kept, 0 broken |
| Refund orchestrator consumes payments via Protocol slot | PASS — `memberships/service.py:757` calls `get_payment_refunder()` from `core.dependencies`, not direct import |

---

## Architectural Gates

| Gate | Result |
|------|--------|
| `mypy --strict app/modules/payments app/core/audit_hash.py app/core/idempotency.py` | PASS — Success: no issues found in 10 source files |
| `ruff check app/modules/payments app/core/audit_hash.py app/core/idempotency.py` | WARNING — 1 RUF100 (unused `noqa: ARG001` on `idempotency.py:62`); cosmetic, not a blocker |
| `lint-imports` | PASS — 3 kept / 0 broken |
| Append-only AST walker (`tests/unit/test_payments_appendonly.py`) | PASS |
| SVC001 commit-gate walker | PASS (caller-owns-txn declarations on `record_payment` + `issue_refund` accepted) |
| `LOCKED_AUDIT_EVENTS` literal-string gate | PASS — both `payments/service.py` emits use string literals |

---

## Test Suite Health

| Suite | Tests | Result |
|-------|-------|--------|
| `tests/integration/payments/` | 41 tests | 41 PASSED in 6.74s |
| `tests/unit/test_audit_hash.py` + `test_idempotency.py` + `test_payments_appendonly.py` | 32 tests | 32 PASSED in 0.05s |
| `test_payments_refund_race.py::test_concurrent_refund_loses_at_db_layer` (REF-TEST-01) | 1 test | PASSED |
| `test_payments_refund_audit_chain.py` (REF-07) | 3 tests | PASSED |
| `test_payments_audit_chain.py` (PAY-10) | 4 tests | PASSED |

**Total Phase 32 test surface: 73 passing tests (41 integration + 32 unit-level Phase 32 unit tests).**

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Migration head is `0012_payments` | grep `down_revision = "0011_trainers"` in `0012_payments.py` | confirmed | PASS |
| Payment model exports | grep `class Payment(Base, UUIDPkMixin)` | confirmed | PASS |
| Idempotency key pattern | grep `IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_:-]{1,128}$"` | confirmed | PASS |
| 3 GET endpoints registered | grep `@router.get` in `payments/router.py` | 3 matches at lines 38, 60, 86 | PASS |
| Refund endpoint registered | grep `"/{membership_id}/refund"` in `memberships/router.py` | line 515 | PASS |

---

## Anti-Patterns Scan

| File | Pattern | Severity | Outcome |
|------|---------|----------|---------|
| `app/core/idempotency.py:62` | unused `# noqa: ARG001` | Info | Cosmetic; ruff `--fix` would resolve. Not blocking. |
| All Phase 32 files | TODO/FIXME/XXX/HACK debt markers | — | None found in the modified files (grep clean) |

---

## Deferred Items (out-of-scope; verified in later phases)

| Item | Addressed In | Evidence |
|------|--------------|----------|
| REF-02 — POST /pt-packages/{id}/refund router | Phase 33 | REQUIREMENTS.md REF-02 + Phase 33 ROADMAP SC #3; Phase 32 ships PaymentRefunder Protocol slot ready for consumer |
| REF-06 — Admin-web AlertDialog (H-13 checkbox) | Phase 35 | REQUIREMENTS.md REF-06; Phase 35 FE-13 |
| FE-10..18 — admin-web sale-with-payment form, PaymentBadge, mock parity, payment history blocks | Phase 35 | ROADMAP Phase 35 Requirements list |
| Pre-existing `test_rbac_parity.py::test_owner_only_count_is_fifteen` stale assertion | Future Phase 30 retrospective fix | Documented in `deferred-items.md`; unrelated to Phase 32 deliverables |

---

## Gaps Summary

**No blocking gaps.** All 5 ROADMAP success criteria verified end-to-end against the codebase. All 18 in-scope requirements satisfied except REF-02 (router scope explicitly belongs to Phase 33 per REQUIREMENTS.md; Protocol slot is in place) and REF-06 (admin-web UI scope explicitly Phase 35).

**One cosmetic ruff warning** (unused `noqa: ARG001`) — non-blocking.

**Two documented event-name drifts** (`payment_refunded` / `membership_sold` in ROADMAP SC text) — addressed via D-32-12 context note; implementation correctly uses `refund_issued` / `membership_created` per `LOCKED_AUDIT_EVENTS` frozenset.

---

## Final Verdict

**PHASE COMPLETE** — Phase 32 goal is observably achieved in the codebase. Every membership sale is recorded in append-only ledger with snapshot-symmetric amount + acceptor; reception/owner can refund atomically via REST endpoint with frozen / renewed-source 409 guards; audit chain (`payment_recorded → refund_issued → membership_refunded`) is forensically traceable via `payment_row_hash`. Architectural invariants (append-only, modules-independent, caller-owns-txn, mandatory snapshot symmetry, defensive-raise Protocol slot accessors, RBAC-04 ordering with idempotency last) hold under static analysis (mypy strict, ruff, lint-imports) and integration tests (41 passing). REF-TEST-01 concurrent race proves DB partial UNIQUE wins.

---

_Verified: 2026-05-15_
_Verifier: Claude (gsd-verifier)_
