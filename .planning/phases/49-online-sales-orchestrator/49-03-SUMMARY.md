---
phase: 49-online-sales-orchestrator
plan: 03
subsystem: online_payments
tags: [yookassa, online-payments, service, tdd, sell, fiscal-stub]

requires:
  - phase: 49-online-sales-orchestrator
    plan: 02
    provides: OnlinePayment ORM + repository + ErrorCode constants + 3 new exceptions + get_yookassa_settings factory
provides:
  - SellRequest / SellResponse Pydantic schemas (XOR root validator on SellResponse)
  - sell_membership / sell_pt_package service entry points (PAY-03..05)
  - _derive_idempotency_key sha256-UTC helper (D-49-08, deterministic across DST)
  - _read_client_email_or_raise FIS-05 gate (D-49-12, locked error code)
  - phase49_fiscal_dispatcher_stub for Plan 49-06 FiscalReceiptDispatcher slot (D-49-22)
  - 2-event audit chain emit per ok branch (online_payment_initiated ROOT
    + yookassa_payment_created CHILD via audit_correlation_id; D-49-19)
  - QR-replay-refetch branch via YooKassaClient.get_payment (BLOCKER #1)
  - 18-test service-layer suite under tests/modules/online_payments/
affects:
  - 49-04-PLAN (router): can wrap service.sell_* in HTTP endpoints
  - 49-06-PLAN (composition root): registers phase49_fiscal_dispatcher_stub
  - 49-07-PLAN (verification): can assert the 4 classification branches

tech-stack:
  added: []
  patterns:
    - "Raw SQL text() SELECT for foreign-module reads (BLOCKER #3 / D-49-03) — preserves .importlinter invariant without ORM cross-imports"
    - "audit_correlation_id chain ROOT(None) → CHILD(uuid4) for 2-event chain inside a single UoW (D-49-19)"
    - "Pydantic model_validator(mode='after') for XOR enforcement on response payloads"
    - "Service hits real YooKassaClient through respx — no ad-hoc httpx stub; respx intercepts at the transport layer"

key-files:
  created:
    - apps/backend/app/modules/online_payments/schemas.py
    - apps/backend/app/modules/online_payments/service.py
    - apps/backend/tests/modules/__init__.py
    - apps/backend/tests/modules/online_payments/__init__.py
    - apps/backend/tests/modules/online_payments/conftest.py
    - apps/backend/tests/modules/online_payments/test_service_sell_membership.py
    - apps/backend/tests/modules/online_payments/test_service_sell_pt_package.py
  modified:
    - apps/backend/alembic/versions/0034_online_payments.py

key-decisions:
  - "Subject FK assignment uses string literal ('membership' / 'pt_package') not SUBJECT_KIND_MEMBERSHIP constant — mypy strict requires Literal type narrowing and the StrEnum-typed constants are not assignable to Literal['membership','pt_package']"
  - "Plan-price + name read via raw SQL text() against membership_plans / pt_package_plans tables — BLOCKER #3 / D-49-03 invariant preserved; .importlinter ignore count remains 3 (UNCHANGED from Plan 49-02)"
  - "NotFoundError imported at module top from app.core.exceptions (BLOCKER #2 — canonical name confirmed at exceptions.py:19)"
  - "QR-replay branch re-fetches via YooKassaClient.get_payment(existing.yookassa_payment_id) to populate qr_payload (BLOCKER #1) — Plan 49-01 patched the adapter so GET surfaces confirmation.confirmation_data when type=='qr'"
  - "Rule 3 inline fix: Alembic 0034 `id` column was missing server_default=gen_random_uuid(); ORM declares it via UUIDPkMixin so SQLAlchemy omits the column from INSERTs and Postgres trips NOT-NULL — patched 0034 in place and the live test DB"

requirements-completed: [PAY-03, PAY-04, PAY-05, PAY-06]

metrics:
  duration: 30min
  completed: 2026-05-22
  tasks: 2
  files: 8
---

# Phase 49 Plan 03: Sell Orchestrator Service Layer + Schema + Fiscal Stub Summary

**Shipped the heart of Phase 49: `service.sell_membership` / `service.sell_pt_package` orchestrators wrapping the Phase 48 ЮKassa adapter with FIS-05 email gate, deterministic per-day idempotency key, 4-branch classification switch, 2-event audit chain, QR replay re-fetch (BLOCKER #1), raw-SQL foreign-plan reads (BLOCKER #3), NotFoundError hoisted to module-top imports (BLOCKER #2), and the Phase 49 fiscal dispatcher stub that Plan 49-06 will register.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2 (both `type="auto"` with `tdd="true"`)
- **Files modified:** 8 (7 created + 1 modified)
- **Commits:** 2 (one per task)

## Accomplishments

- **`SellRequest` / `SellResponse` schemas** with `@model_validator(mode='after')` XOR check (`confirmation_url` xor `qr_payload`).
- **`sell_membership` / `sell_pt_package`** orchestrators implement the 7-step protocol from D-49-10:
  1. FIS-05 email gate (`_read_client_email_or_raise` — raises `ClientEmailRequiredForOnlinePaymentError` with locked code `client_email_required_for_online_payment` on `email IS NULL`).
  2. Plan-price + name read via raw SQL `text()` SELECT.
  3. `_derive_idempotency_key` — sha256 over `sell-<kind>:<plan>:<client>:<UTC date>`.
  4. Replay check via `repository.get_online_payment_by_idempotency_key`:
     - **Redirect replay** returns persisted `confirmation_url`.
     - **QR replay** re-fetches via `YooKassaClient.get_payment(existing.yookassa_payment_id)` and returns `qr_payload` from the GET response (BLOCKER #1).
  5. `build_receipt_item` from `app.integrations.yookassa.receipt`.
  6. `YooKassaClient.create_payment(idempotency_key=<sha256 hex str>, confirmation_type=...)`.
  7. Classification switch: `ok` → INSERT + `session.flush()` + 2 audit emits; `validation_error` → `ValidationAppError`; `transient_error` → `ServiceUnavailableAppError`; `permanent_error` → `BadGatewayAppError`. **No DB row and no audit emit on any failure branch** (D-49-20).
- **2-event audit chain** (D-49-19) — `online_payment_initiated` with `audit_correlation_id=None` (ROOT) then `yookassa_payment_created` with the same `correlation_id` (CHILD). Payloads validated via the locked Pydantic schemas in `app/core/audit_payloads.py`.
- **`phase49_fiscal_dispatcher_stub`** (D-49-22) — async callable that raises `NotImplementedError` with `"Phase 50"` in the message. Plan 49-06 will register it on the `FiscalReceiptDispatcher` slot.
- **18 service-layer tests** under `tests/modules/online_payments/` — all green:
  - 11 in `test_service_sell_membership.py`: email gate, real-receipt-builder happy path (W4), ok-redirect, ok-qr, validation_error (422 no row), transient_error (503 no row), permanent_error (502 no row), redirect-replay, **QR-replay-refetch (BLOCKER #1)**, deterministic-key, fiscal-stub.
  - 7 in `test_service_sell_pt_package.py`: mirror of the same matrix for PT-package, including QR-replay-refetch.

## Task Commits

1. **Task 1 — sell_membership / sell_pt_package / fiscal stub orchestrator:** `31361b2` (feat)
2. **Task 2 — service-layer test suite (18 tests) + Alembic 0034 fix:** `9035f82` (test)

## Files Created/Modified

### Created (Task 1)

- `apps/backend/app/modules/online_payments/schemas.py` — `SellRequest`, `SellResponse` with XOR validator.
- `apps/backend/app/modules/online_payments/service.py` — orchestrator + 4 helpers (`_derive_idempotency_key`, `_read_client_email_or_raise`, `_read_membership_plan_or_raise`, `_read_pt_package_plan_or_raise`) + `_sell_subject` shared body + 2 public entry points + `phase49_fiscal_dispatcher_stub`.

### Created (Task 2)

- `apps/backend/tests/modules/__init__.py` — empty package marker.
- `apps/backend/tests/modules/online_payments/__init__.py` — empty package marker.
- `apps/backend/tests/modules/online_payments/conftest.py` — respx 500 / 404 routes, re-exports of Plan 49-01 fixtures, DB-direct factories (`make_user`, `make_actor`, `make_client_with_email`, `make_client_no_email`, `make_membership_plan`, `make_pt_package_plan`).
- `apps/backend/tests/modules/online_payments/test_service_sell_membership.py` — 11 async tests.
- `apps/backend/tests/modules/online_payments/test_service_sell_pt_package.py` — 7 mirror tests.

### Modified (Task 2)

- `apps/backend/alembic/versions/0034_online_payments.py` — added `server_default=sa.text("gen_random_uuid()")` to the `id` column (Rule 3 deviation — see Deviations below).

## BLOCKER verification (literal output)

### BLOCKER #1 — QR replay re-fetches via `YooKassaClient.get_payment`

```python
$ grep -n "yookassa_client.get_payment" app/modules/online_payments/service.py
214:            refetch = await yookassa_client.get_payment(
```

Single call inside the QR replay branch (line 214) — re-fetches the upstream payment to extract `confirmation.confirmation_data` into `qr_payload`. Test `test_sell_membership_replay_qr_refetches_and_returns_qr_payload` and `test_sell_pt_package_replay_qr_refetches_and_returns_qr_payload` exercise this path and pass without crashing the `SellResponse` XOR validator.

### BLOCKER #2 — `NotFoundError` hoisted to module-top import

```python
from app.core.exceptions import (
    BadGatewayAppError,
    ClientEmailRequiredForOnlinePaymentError,
    NotFoundError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
```

`grep -c NotFoundError app/modules/online_payments/service.py` → **3** (one import + two raises: `membership_plan_not_found`, `pt_package_plan_not_found`).

`grep -n "^from app.core.exceptions import" service.py | grep -c NotFound` returns 0 because the import is multi-line (`(` on the keyword line, identifiers on continuation lines). The intent of BLOCKER #2 (hoist to module top) is satisfied — `NotFoundError` is imported once at the top of the module.

### BLOCKER #3 — Foreign module plan reads via raw SQL, `.importlinter` UNCHANGED

```sql
SELECT id, price_kopecks, name FROM membership_plans
WHERE id = :id AND deleted_at IS NULL

SELECT id, price_kopecks, name FROM pt_package_plans
WHERE id = :id AND deleted_at IS NULL
```

(Multi-line `text("...")` literals inside `_read_membership_plan_or_raise` and `_read_pt_package_plan_or_raise`.)

- `grep -c "from app.modules.memberships.models\|from app.modules.pt_packages.models" app/modules/online_payments/service.py` → **0** (no ORM imports of foreign plans).
- `grep -c "online_payments.service ->" apps/backend/.importlinter` → **3** (UNCHANGED from Plan 49-02; the 3 ignores are `payments.models`, `users.display`, `clients.models`). BLOCKER #3 invariant preserved.

### D-49-19 — Two-event audit chain emit

```python
correlation_id = uuid4()
# ... INSERT online_payment row ...
await session.flush()

# ROOT
initiated_payload = OnlinePaymentInitiatedPayload(audit_correlation_id=None, ...)
await audit.emit(session, "online_payment_initiated", ..., **initiated_payload.model_dump(mode="json"))

# CHILD
created_payload = YookassaPaymentCreatedPayload(audit_correlation_id=correlation_id, ...)
await audit.emit(session, "yookassa_payment_created", ..., **created_payload.model_dump(mode="json"))
```

`session.flush()` precedes both emits so FK / CHECK / UNIQUE violations surface as exceptions BEFORE any audit row hits the log (D-49-19 single-UoW invariant).

### D-49-22 — Phase 49 fiscal stub

```python
async def phase49_fiscal_dispatcher_stub(
    *, fiscal_receipt_id: UUID, audit_correlation_id: UUID | None,
) -> None:
    raise NotImplementedError(
        "Phase 50 FISCAL-01 wires real dispatch — Phase 49 only registers "
        "the slot non-None so the parity test passes."
    )
```

Test `test_phase49_fiscal_dispatcher_stub_raises_not_implemented` asserts both the raise and the `"Phase 50"` substring.

## Test results

```
$ cd apps/backend && uv run pytest tests/modules/online_payments/ --no-header -q
collected 18 items
tests/modules/online_payments/test_service_sell_membership.py ........... [ 55%]
.                                                                        [ 61%]
tests/modules/online_payments/test_service_sell_pt_package.py .......    [100%]
18 passed in 3.92s
```

- `cd apps/backend && uv run ruff check app/modules/online_payments/ tests/modules/online_payments/` → all checks pass.
- `cd apps/backend && uv run mypy app/modules/online_payments/` → no issues.
- `cd apps/backend && uv run lint-imports` → **3 contracts kept, 0 broken** (2 warn-level unmatched ignores for not-yet-shipped Phase 50/52 modules; BLOCKER #3 invariant intact).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Alembic 0034 missing `server_default=gen_random_uuid()` on `id` column**

- **Found during:** Task 2 (running the first happy-path test).
- **Issue:** `OnlinePayment` ORM model uses `UUIDPkMixin` (which sets `server_default=text("gen_random_uuid()")`). SQLAlchemy reads that ORM declaration and omits `id` from the INSERT column list, expecting the database to apply the default. Alembic migration `0034_online_payments.py` had defined the `id` column with `primary_key=True, nullable=False` but NO `server_default` — so Postgres tripped NOT-NULL on every INSERT.
- **Fix:** Added `server_default=sa.text("gen_random_uuid()")` to the `id` column in `apps/backend/alembic/versions/0034_online_payments.py` and ran a one-shot `ALTER TABLE online_payments ALTER COLUMN id SET DEFAULT gen_random_uuid()` against the live test DB so existing tests can run without re-creating the database.
- **Files modified:** `apps/backend/alembic/versions/0034_online_payments.py`.
- **Commit:** `9035f82` (bundled with Task 2 since it unblocked the test suite).
- **Rationale for amending vs. new migration:** Phase 49 has not shipped to production, the 0034 migration was added by Plan 49-01 (same phase), and patching in place preserves the migration's atomic intent (the new `online_payments` table). A separate cleanup migration would clutter the alembic history without adding rollback safety.

**2. [Rule 3 - Blocking] Adjusted subject_kind argument from `SUBJECT_KIND_*` constants to literal strings**

- **Found during:** Task 1 mypy pass.
- **Issue:** mypy strict rejects `subject_kind=SUBJECT_KIND_MEMBERSHIP` (typed `str`) against `_sell_subject(subject_kind: Literal["membership", "pt_package"], ...)` parameter.
- **Fix:** `sell_membership` passes `subject_kind="membership"` literal; `sell_pt_package` passes `subject_kind="pt_package"`. The unused `SUBJECT_KIND_*` constants were removed from imports; the comparison-only callsites inside `_sell_subject` (FK column assignment) were rewritten to use literal-string comparisons.
- **Files modified:** `apps/backend/app/modules/online_payments/service.py`.
- **Commit:** `31361b2` (bundled with Task 1).
- **Impact:** None — the literal strings are byte-equal to the constant values; the AST gate and runtime CHECK constraints both see the same bytes.

### Deferred items logged

- Pre-existing alembic drift in `tests/integration/test_alembic_clean.py` (multiple removed-table / removed-index detections) — out of scope; see `.planning/phases/49-online-sales-orchestrator/deferred-items.md`. Verified failing on `master` before Plan 49-03 changes.

## Test factory naming actually used

Plan named hypothetical factories; the conftest below ships these names:

| Plan-assumed | Actual fixture |
| --- | --- |
| `db_session` | `db_session` (root conftest) |
| `make_client_no_email` | `make_client_no_email` (new in this plan's conftest) |
| `make_client_with_email` | `make_client_with_email` (new in this plan's conftest) |
| `make_membership_plan` | `make_membership_plan` (new in this plan's conftest) |
| `make_pt_package_plan` | `make_pt_package_plan` (new in this plan's conftest) |
| `make_actor` | `make_actor` (new — produces a reception User) |

All factories commit inside the SAVEPOINT-mode `db_session` — nested savepoints release inside the outer per-test transaction the root conftest rolls back at teardown.

## Self-Check: PASSED

- **`apps/backend/app/modules/online_payments/schemas.py`:** FOUND.
- **`apps/backend/app/modules/online_payments/service.py`:** FOUND.
- **`apps/backend/tests/modules/online_payments/conftest.py`:** FOUND.
- **`apps/backend/tests/modules/online_payments/test_service_sell_membership.py`:** FOUND.
- **`apps/backend/tests/modules/online_payments/test_service_sell_pt_package.py`:** FOUND.
- **`apps/backend/alembic/versions/0034_online_payments.py`:** FOUND (modified).
- **Commit `31361b2`** (Task 1 feat) — present in `git log`.
- **Commit `9035f82`** (Task 2 test) — present in `git log`.
- All 18 service-layer tests pass; ruff / mypy / lint-imports green; `.importlinter` ignore count unchanged at 3.
