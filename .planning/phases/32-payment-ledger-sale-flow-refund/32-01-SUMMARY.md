---
phase: 32-payment-ledger-sale-flow-refund
plan: 01
subsystem: backend/payments
tags: [migration, orm, repository, service, router, audit, idempotency, protocol-slot]
requires:
  - 0011_trainers migration head
  - audit_payloads.py PaymentRecordedPayload + RefundIssuedPayload + MembershipRefundedPayload (Phase 30)
  - LOCKED_AUDIT_EVENTS payment_recorded / refund_issued / membership_refunded (Phase 30)
  - Resource.PAYMENTS + (VIEW, PAYMENTS) ∈ OWNER_ONLY (Phase 30)
provides:
  - migration 0012_payments — payments table + memberships.cancellation_reason ALTER
  - app.modules.payments.models.Payment (UUIDPkMixin-only, append-only)
  - app.core.audit_hash.payment_row_hash
  - app.core.idempotency.{verify_idempotency, IDEMPOTENCY_KEY_PATTERN, idempotent_response}
  - app.core.dependencies.{PaymentRecorder, PaymentRefunder, register_*, get_*} with defensive raise
  - app.modules.payments.service.{record_payment, issue_refund} (caller-owns-txn)
  - 3 GET endpoints (/api/v1/payments + /by-client/{id} + /by-membership/{id})
  - MembershipRefundRequest schema (ready for Phase 32 Plan 32-03 consumer)
affects:
  - app/main.py:create_app() — register_payment_recorder/refunder wiring
  - app/api/v1/router.py — mount payments_router
  - app/modules/memberships/{models,schemas,constants}.py — cancellation_reason column + sentinel
  - tests/unit/test_service_commit_gate.py — walker extended for public Protocol-slot opt-out
  - tests/integration/test_route_introspection.py — added require_payments_view_for_subject to _GATE_PREFIXES
tech-stack:
  added:
    - app.core.audit_hash (stdlib-only SHA-256 canonical-JSON)
    - app.core.idempotency (Redis-cached Idempotency-Key envelope)
  patterns:
    - "Defensive-raise accessor on Protocol slot (mirrors register_user_loader)"
    - "TYPE-erased Any return type for cross-boundary Protocol (core ⊥ modules)"
    - "SA Table metadata reflection instead of ORM import for cross-module joins"
    - "Caller-owns-txn marker `# noqa: SVC001 caller-owns-txn` on public service fns"
key-files:
  created:
    - apps/backend/alembic/versions/0012_payments.py
    - apps/backend/app/core/audit_hash.py
    - apps/backend/app/core/idempotency.py
    - apps/backend/app/modules/payments/constants.py
    - apps/backend/app/modules/payments/schemas.py
    - apps/backend/app/modules/payments/repository.py
    - apps/backend/app/modules/payments/permissions.py
    - apps/backend/app/modules/payments/router.py
    - apps/backend/tests/unit/test_audit_hash.py
    - apps/backend/tests/unit/test_idempotency.py
    - apps/backend/tests/integration/payments/__init__.py
    - apps/backend/tests/integration/payments/conftest.py
    - apps/backend/tests/integration/payments/test_payments_list.py
  modified:
    - apps/backend/alembic/env.py (autodiscovery import)
    - apps/backend/app/main.py (composition-root wiring)
    - apps/backend/app/api/v1/router.py (mount payments_router)
    - apps/backend/app/core/dependencies.py (2 Protocol slots + defensive accessors)
    - apps/backend/app/modules/payments/__init__.py (real docstring)
    - apps/backend/app/modules/payments/models.py (real Payment ORM)
    - apps/backend/app/modules/payments/service.py (real bodies)
    - apps/backend/app/modules/memberships/models.py (cancellation_reason col)
    - apps/backend/app/modules/memberships/schemas.py (cancellation_reason field)
    - apps/backend/app/modules/memberships/constants.py (CANCELLATION_REASON_REFUNDED)
    - apps/backend/tests/unit/test_service_commit_gate.py (extended marker scope)
    - apps/backend/tests/integration/test_route_introspection.py (new gate prefix)
decisions:
  - "D-32-10: caller-owns-txn for payments.service.{record_payment, issue_refund} — sale-flow / refund-flow orchestrator owns UoW so audit row + payment row + membership transition co-write atomically."
  - "D-32-14 amended: PaymentRefunder takes (subject_kind, subject_id) NOT original_payment_id. The refunder internally loads the original via repository.get_original_membership_payment, so cross-module callers (memberships.service.refund_membership) never import app.modules.payments.repository — modules-independent contract preserved."
  - "D-32-23: payment_row_hash hashes the 8-column stable projection (id, subject_kind, subject_id, amount_kopecks, method, received_at, received_by_user_id, refund_of). audit_log_id is intentionally OMITTED because it is mutated post-INSERT when the audit row latches on."
metrics:
  duration_minutes: 65
  tasks_completed: 3
  files_created: 13
  files_modified: 12
  unit_tests_added: 25
  integration_tests_added: 9
  completed_date: "2026-05-15"
---

# Phase 32 Plan 01: Payment Ledger Foundations Summary

**One-liner:** Lands the append-only payments ledger schema (migration 0012),
the Payment ORM model, 5 module bodies (router/service/repository/schemas/permissions),
two new core helpers (audit_hash + idempotency), two defensive-raise Protocol
slots (PaymentRecorder + PaymentRefunder) wired exclusively from create_app(),
and 3 read-only GET endpoints — gating Plans 32-02 and 32-03.

## Migration 0012

`apps/backend/alembic/versions/0012_payments.py` lands:

- **CREATE TABLE payments** with 9 columns: subject_kind TEXT NOT NULL,
  subject_id UUID NOT NULL, amount_kopecks INTEGER NOT NULL (signed), method
  TEXT NOT NULL DEFAULT 'cash', received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  received_by_user_id UUID NOT NULL FK users(id) ON DELETE RESTRICT, refund_of
  UUID NULL FK payments(id) ON DELETE RESTRICT, audit_log_id UUID NULL FK
  audit_log(id) ON DELETE SET NULL, id UUID PK DEFAULT gen_random_uuid().
- Two CHECK constraints — `ck_payments_amount_sign_matches_subject_kind` and
  `ck_payments_subject_kind`.
- Three regular indexes — `ix_payments_subject` on (subject_kind, subject_id),
  `ix_payments_received_by_user_id`, `ix_payments_received_at` (DESC).
- Partial UNIQUE — `uq_payments_refund_of_alive ON (refund_of) WHERE refund_of IS NOT NULL`
  enforcing at-most-one refund per sale.
- NO created_at, NO updated_at, NO deleted_at — `received_at` is the single
  temporal column per B-01 INFRA-22.

Also: `ALTER TABLE memberships ADD COLUMN cancellation_reason TEXT NULL` — no
backfill, no CHECK; coexists with the legacy `cancel_reason` column. Plan 32-03
will populate this with the `CANCELLATION_REASON_REFUNDED = "refunded"` sentinel.

Round-trip verified: `upgrade head` → `downgrade -1` → `upgrade head` clean;
`alembic check` reports "No new upgrade operations detected." (autogenerate-stable
without env.py skip-list entry — column-only `postgresql_where` is stable).

## Module Structure: Stubs → Real Bodies

| File | Stub LOC | Real LOC | Δ |
|------|----------|----------|---|
| `app/modules/payments/__init__.py` | 6 | 13 | +7 |
| `app/modules/payments/models.py` | 35 | 118 | +83 |
| `app/modules/payments/service.py` | 11 | 198 | +187 |
| `app/modules/payments/schemas.py` | (new) | 73 | +73 |
| `app/modules/payments/repository.py` | (new) | 245 | +245 |
| `app/modules/payments/permissions.py` | (new) | 65 | +65 |
| `app/modules/payments/router.py` | (new) | 113 | +113 |
| `app/modules/payments/constants.py` | (new) | 24 | +24 |

## Two Protocol Slots (Defensive-Raise)

```python
# app/core/dependencies.py — return type Any because Payment lives in app.modules
class PaymentRecorder(Protocol):
    async def __call__(
        self, session, *, subject_kind, subject_id, amount_kopecks,
        method="cash", received_by_user_id, audit_actor,
    ) -> Any: ...

class PaymentRefunder(Protocol):
    async def __call__(
        self, session, *, subject_kind, subject_id, refund_user_id, reason,
        audit_actor,
    ) -> Any: ...

def get_payment_recorder() -> PaymentRecorder:
    if _payment_recorder is None:
        raise RuntimeError("payment_recorder not registered")
    return _payment_recorder

def get_payment_refunder() -> PaymentRefunder:
    if _payment_refunder is None:
        raise RuntimeError("payment_refunder not registered")
    return _payment_refunder
```

Wired exclusively from `app/main.py:create_app()`. NOT wired in
`app/workers/telegram_bot.py` — verified via `grep` (count == 0). Signature
amended per D-32-14 / PATTERNS.md §14 — refunder takes (subject_kind, subject_id)
so the refund-flow orchestrator never imports `app.modules.payments.repository`.

## Two Core Helpers

### `app/core/audit_hash.py`
- `payment_row_hash(row: Mapping[str, Any]) -> str` → `sha256:<64-hex>`.
- Pure stdlib imports — no `app.modules.*` (lint-imports `core-not-depend-on-modules` green).
- UTC-normalizes datetimes via `astimezone(UTC).isoformat()`; UUIDs → `str()`;
  `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)`.

### `app/core/idempotency.py`
- `IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_:-]{1,128}$"`.
- `verify_idempotency(request, redis)` — FastAPI Depends; raises
  `ValidationAppError("idempotency_key_required" | "idempotency_key_invalid_format")`.
- `begin_idempotency / store_idempotency_response / load_idempotency_response` —
  two-phase Redis flow (`sz:idem:{key}` placeholder → envelope; TTL 3600s).
- `idempotent_response(redis, key, body_bytes)` — composed orchestrator:
  unset → claim & return None; placeholder → `ConflictError("idempotency_in_flight")`;
  envelope hash mismatch → `ValidationAppError("idempotency_key_reuse")`;
  envelope hash match → replay verbatim.

## 3 GET Endpoints + RBAC Matrix

| Endpoint | Owner | Reception | Gate |
|----------|-------|-----------|------|
| GET /api/v1/payments | 200 | **403** | `require_permission(VIEW, PAYMENTS)` — `(VIEW, PAYMENTS) ∈ OWNER_ONLY` |
| GET /api/v1/payments/by-client/{client_id} | 200 | 200 | `require_payments_view_for_subject()` |
| GET /api/v1/payments/by-membership/{membership_id} | 200 | 200 | `require_payments_view_for_subject()` |

Filter parity on global route per PAY-06: `subjectKind`, `subjectId`,
`receivedByUserId`, `receivedFrom`, `receivedTo`. Date window uses half-open
semantic in Europe/Moscow — `receivedFrom` becomes start-of-day MSK,
`receivedTo` becomes start-of-next-day MSK (inclusive on both ends).

## Test Results

- **Migration round-trip:** `alembic upgrade head` + `alembic downgrade -1` +
  `alembic upgrade head` clean. `alembic check` reports "No new upgrade
  operations detected."
- **Append-only AST walker:** 7/7 cases green
  (`tests/unit/test_payments_appendonly.py`) — real `payments/service.py` body
  contains no `update(Payment)` / `delete(Payment)` / `on_conflict_do_update`.
- **SVC001 commit-gate walker:** 7/7 cases green
  (`tests/unit/test_service_commit_gate.py`) — record_payment + issue_refund
  carry `# noqa: SVC001 caller-owns-txn` markers accepted by the extended
  predicate.
- **audit_hash unit tests:** 15/15 cases green — determinism, TZ-independence
  (UTC vs Europe/Moscow vs +5h fixed-offset), 8-column flip parametrize,
  format regex, UUID normalization, None handling, sort-independence.
- **idempotency unit tests:** 10/10 cases green — missing/empty header
  required, bang+space invalid_format, valid_format roundtrip, >128 chars
  invalid, max-length-128 valid, regex pattern allow/reject, body_sha256 hex.
- **Payments integration tests:** 9/9 cases green
  (`tests/integration/payments/test_payments_list.py`) — owner global,
  reception 403 on global, subject_kind filter, received_by_user_id filter,
  half-open MSK date window, reception+owner on /by-client + /by-membership,
  pagination envelope shape, empty page for unknown client id.
- **Wider unit suite:** 428/428 green.
- **Wider integration suite:** 449/449 green (excluding 4 pre-existing
  `test_rbac_parity` failures — logged in `deferred-items.md`).
- **lint-imports:** 3 contracts kept (core ⊥ modules, modules ⊥ each other,
  integrations ⊥ modules).
- **mypy --strict:** clean on `app/modules/payments/`, `app/core/audit_hash.py`,
  `app/core/idempotency.py`, `app/core/dependencies.py` (10 source files).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] SVC001 walker extended to accept marker on public functions**
- **Found during:** Task 3.
- **Issue:** The plan requires `# noqa: SVC001 caller-owns-txn` markers on the
  public `record_payment` and `issue_refund` functions, but the existing
  `tests/unit/test_service_commit_gate.py` walker rejected markers on public
  (non-`_`-prefixed) functions with `"public service functions MUST commit themselves"`.
- **Fix:** Extended the walker's decision tree: the marker now opts out both
  private helpers AND public Protocol-slot service functions. The synthetic
  test `test_synthetic_public_function_with_svc001_is_rejected` was renamed
  to `test_synthetic_public_function_with_svc001_passes` and updated to assert
  the Phase 32 D-32-10 pattern (public Protocol-slot function with marker passes).
- **Files modified:** `apps/backend/tests/unit/test_service_commit_gate.py`.
- **Commit:** `7d2c4b7`.

**2. [Rule 3 - Blocking] Route introspection gate prefix extended**
- **Found during:** Task 3 — `test_every_protected_route_declares_a_gate`
  failed for `/api/v1/payments/by-client/{client_id}` and `/by-membership/{id}`.
- **Issue:** The walker only recognized `require_permission.` and
  `require_authenticated.` qualname prefixes. My new factory
  `require_payments_view_for_subject` produces qualname
  `require_payments_view_for_subject.<locals>._checker`, which the walker
  treated as "no gate".
- **Fix:** Added `"require_payments_view_for_subject."` to `_GATE_PREFIXES`.
  Updated the sanity belt `test_gate_prefixes_match_factory_names` to import
  the new factory and assert its qualname matches the new entry, and the
  tuple-equality check now includes the third entry.
- **Files modified:** `apps/backend/tests/integration/test_route_introspection.py`.
- **Commit:** `7d2c4b7`.

**3. [Rule 1 - Bug / Terminology] Audit event payload field name divergence**
- **Found during:** Task 3 wiring `audit.emit("refund_issued", ...)`.
- **Issue:** The plan body referenced `refund_of=original.id` in the
  audit.emit call for `refund_issued`, but the locked Pydantic schema
  `RefundIssuedPayload` (Phase 30 INFRA-23) declares the field as
  `refund_of_payment_id` — not `refund_of`. Also `subject_kind` on
  RefundIssuedPayload has a `^(membership|pt_package)$` pattern, EXCLUDING
  `'refund'` — so we must pass the ORIGINAL's `subject_kind`, not the new
  refund row's.
- **Fix:** service.issue_refund passes `refund_of_payment_id=original.id`
  and `subject_kind=original.subject_kind` (which is `'membership'` in Phase 32).
- **Files modified:** `apps/backend/app/modules/payments/service.py`.
- **Commit:** `7d2c4b7`.

### Terminology Drift Recorded

- Plan §interfaces and §audit.emit payload references `refund_of` and
  `payment_refunded`. Locked schemas use `refund_of_payment_id` and
  `refund_issued` respectively. Aligned with locked Phase 30 schemas.

### Pre-existing Failures Out of Scope

- `tests/integration/test_rbac_parity.py::test_owner_only_count_is_fifteen`
  asserts `len(OWNER_ONLY) == 15`, but the constant grew to 26 entries in
  Phase 30 INFRA-19. Test fixture not updated alongside Phase 30. Logged in
  `.planning/phases/32-payment-ledger-sale-flow-refund/deferred-items.md`.
  3 other tests in `test_rbac_parity.py` similarly stale (4 deselected during
  the wider integration run).

## REF-02 Readiness for Phase 33 Consumer

- `MembershipRefundRequest(BackendSchemaBase)` schema landed in
  `app/modules/payments/schemas.py` with `reason: str = Field(min_length=1, max_length=200)`.
  `extra='forbid'` inherited from `BackendSchemaBase` — rejects extra wire
  fields including `amountKopecks` (REF-05).
- `PaymentRefunder` Protocol slot signature documented and frozen at
  `(subject_kind, subject_id, refund_user_id, reason, audit_actor)`. The
  Phase 33 pt-packages consumer extends the service.issue_refund's
  `NotImplementedError` branch to handle `subject_kind="pt_package"`.

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: apps/backend/alembic/versions/0012_payments.py
- FOUND: apps/backend/app/core/audit_hash.py
- FOUND: apps/backend/app/core/idempotency.py
- FOUND: apps/backend/app/modules/payments/constants.py
- FOUND: apps/backend/app/modules/payments/schemas.py
- FOUND: apps/backend/app/modules/payments/repository.py
- FOUND: apps/backend/app/modules/payments/service.py
- FOUND: apps/backend/app/modules/payments/permissions.py
- FOUND: apps/backend/app/modules/payments/router.py
- FOUND: apps/backend/tests/unit/test_audit_hash.py
- FOUND: apps/backend/tests/unit/test_idempotency.py
- FOUND: apps/backend/tests/integration/payments/test_payments_list.py

**Commits verified:**
- FOUND: 71a5bc7 — Task 1 (migration + ORM)
- FOUND: 410f15e — Task 2 (audit_hash + idempotency + Protocol slots)
- FOUND: 7d2c4b7 — Task 3 (module bodies + endpoints + tests)
