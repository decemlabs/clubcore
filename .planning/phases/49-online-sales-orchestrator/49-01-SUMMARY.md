---
phase: 49-online-sales-orchestrator
plan: 01
subsystem: payments
tags: [yookassa, alembic, postgres, integrations, qr-confirmation, idempotency]

requires:
  - phase: 48-kassa-integration-adapter
    provides: YooKassaClient + YooKassaPaymentResult dataclass (Phase 48 D-48-03..12 baseline)
provides:
  - YooKassaPaymentResult.qr_payload field (backward-compatible default None)
  - YooKassaClient.create_payment accepts confirmation_type Literal['redirect','qr']
  - YooKassaClient.create_payment accepts idempotency_key UUID | str (D-49-08 widening)
  - YooKassaClient.get_payment populates qr_payload on QR re-fetch (BLOCKER #1)
  - online_payments table (Alembic 0034) with 4 indexes + 4 CHECKs + 4 FK columns
  - 3 new respx fixtures (qr_success, qr_422, get_qr_pending) in tests/integrations/yookassa/conftest.py
affects:
  - 49-02-PLAN (online_payments module skeleton — consumes table)
  - 49-03-PLAN (service layer — consumes adapter + table + qr_payload re-fetch)
  - 49-07-PLAN (E2E tests — consumes fixtures)

tech-stack:
  added: []
  patterns:
    - "Partial UNIQUE index per subject_kind (membership/pt_package) — Phase 16/30 pattern"
    - "IMMUTABLE per-day partition expression: (col AT TIME ZONE 'Europe/Moscow')::date"
    - "Idempotency key widening UUID | str — UUID for Phase 48, sha256 hex for Phase 49"
    - "qr_payload extraction on get_payment for QR-replay support (D-49-04 + D-49-09)"

key-files:
  created:
    - apps/backend/alembic/versions/0034_online_payments.py
    - apps/backend/tests/integrations/yookassa/test_client_create_payment.py
    - apps/backend/tests/integration/test_alembic_0034_online_payments.py
  modified:
    - apps/backend/app/integrations/yookassa/types.py
    - apps/backend/app/integrations/yookassa/client.py
    - apps/backend/tests/integrations/yookassa/conftest.py

key-decisions:
  - "Idempotency key result field stays UUID | None — string-keyed calls echo None back; caller already owns the key"
  - "qr_payload populated by get_payment when upstream confirmation.type == 'qr' (D-49-04: row stores no qr_payload, ЮKassa server-side dedup returns current confirmation_data on every GET)"
  - "Partial UNIQUE index expression uses (initiated_at AT TIME ZONE 'Europe/Moscow')::date — DATE(timestamptz) is not IMMUTABLE in Postgres"

patterns-established:
  - "Adapter signature widening pattern: add Literal-typed branch parameter with backward-compatible default; preserve all Phase 48 callsites"
  - "Per-day partial UNIQUE indexes use IMMUTABLE AT TIME ZONE expression (mirror visits.gym_date 0006)"

requirements-completed: [PAY-01, PAY-02, PAY-05]

duration: 35min
completed: 2026-05-22
---

# Phase 49 Plan 01: YooKassa Adapter QR-Patch + Alembic 0034 Summary

**YooKassa adapter extended for QR confirmation_type + widened idempotency_key (UUID | str) + qr_payload extraction on get_payment re-fetch; Alembic 0034 creates online_payments table with 4 indexes + XOR-FK CHECK enforcing PAY-01/PAY-02 invariants.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-22T14:14:00Z
- **Completed:** 2026-05-22T14:29:00Z (effective wall-clock; commits span 11:24–11:28 UTC due to timezone reporting)
- **Tasks:** 2 (both TDD)
- **Files modified:** 6 (3 created + 3 modified)

## Accomplishments

- **PATTERNS.md BLOCKER #1 resolved:** `YooKassaPaymentResult.qr_payload` field added; `YooKassaClient.get_payment` now populates it when upstream `confirmation.type == "qr"`. Plan 49-03 QR-replay re-fetch path can return a SellResponse that satisfies the Pydantic XOR validator without any ORM-side cache.
- **PATTERNS.md BLOCKER #2 resolved:** `YooKassaClient.create_payment(idempotency_key=...)` widened from `UUID` to `UUID | str`. Phase 49 D-49-08 deterministic sha256 hex keys flow verbatim through the `Idempotence-Key` header; ЮKassa server-side dedup is preserved.
- **PAY-05 confirmation_type='qr' branch shipped:** `create_payment` accepts `confirmation_type: Literal['redirect','qr']` defaulting to `'redirect'`; body branches on the parameter; QR success extracts `confirmation.confirmation_data` into `qr_payload`.
- **Alembic 0034 ships:** `online_payments` table + 4 indexes (2 full UNIQUE: yookassa_payment_id + idempotency_key; 2 partial UNIQUE double-tap: membership + pt_package gated by `status != 'canceled' AND <fk> IS NOT NULL`) + 4 CHECK constraints (amount positive, status enum, confirmation_type enum, XOR subject FKs) + 4 FK columns (clients, membership_plans, pt_package_plans, users).
- **3 new respx fixtures** (`yookassa_create_payment_qr_success`, `yookassa_create_payment_qr_422`, `yookassa_get_payment_qr_pending`) — Plan 49-03 QR-replay re-fetch test (`test_replay_qr_sale_refetches_and_returns_qr_payload`) is now driveable without a live sandbox.

## Task Commits

Each task followed TDD red→green:

1. **Task 1 RED: failing tests for QR + UUID|str + get_payment qr_payload** — `9531d84` (test)
2. **Task 1 GREEN: adapter widening for QR + UUID|str + get_payment qr_payload** — `038e3cd` (feat)
3. **Task 2 RED: schema-shape test for online_payments** — `7f05779` (test)
4. **Task 2 GREEN: Alembic 0034 — online_payments table + 4 indexes** — `b18a911` (feat)

## Files Created/Modified

### Created

- `apps/backend/alembic/versions/0034_online_payments.py` — table DDL + 4 indexes + 4 CHECKs + 2 UNIQUEs + 4 FKs. Round-trip clean.
- `apps/backend/tests/integrations/yookassa/test_client_create_payment.py` — 8 tests locking adapter contract (field default, field set, redirect-default preserved, QR returns payload, string idempotency_key verbatim, QR 422 classification, get_payment QR extraction).
- `apps/backend/tests/integration/test_alembic_0034_online_payments.py` — 5 schema-shape tests against live Postgres (table exists, 2 partial UNIQUE indexes, 2 full UNIQUEs, 4 CHECKs, 4 FK targets).

### Modified

- `apps/backend/app/integrations/yookassa/types.py` — appended `qr_payload: str | None = None` to `YooKassaPaymentResult`. Backward compatible.
- `apps/backend/app/integrations/yookassa/client.py` — `create_payment` signature widened (added `confirmation_type` param, widened `idempotency_key` to `UUID | str`); body branches on confirmation_type; success path populates `qr_payload` for QR; `get_payment` extracts `qr_payload` from upstream `confirmation.confirmation_data` when `confirmation.type == "qr"`; failure-path returns now echo only UUID-typed keys (string keys → `None`); module docstring updated for D-49-08 widening.
- `apps/backend/tests/integrations/yookassa/conftest.py` — 3 new respx fixtures + docstring fixture index extended.

## Decisions Made

- **Result `idempotency_key` field stays `UUID | None`.** When a caller passes a `str` key (D-49-08 sha256 hex), the result's `idempotency_key` field is `None` — the caller already owns the key, and widening the dataclass field to `UUID | str | None` would force every Phase 48 consumer to re-type. Documented in the module docstring.
- **`get_payment` extracts `qr_payload` (D-49-04 + D-49-09).** Per D-49-04, the `online_payments` row stores no `qr_payload`. ЮKassa server-side dedup returns the original payment object with current `confirmation.confirmation_data` on every `GET /payments/{id}`, so re-fetch is the correct place to compute it. Without this, the Plan 49-03 service-layer QR-replay path returns an empty `SellResponse` that crashes the Pydantic XOR validator.
- **Per-day partition expression: `(initiated_at AT TIME ZONE 'Europe/Moscow')::date`** — NOT `DATE(initiated_at)`. Postgres rejects `DATE(timestamptz)` in partial-index expressions because it is not IMMUTABLE (result depends on session `TimeZone`). `AT TIME ZONE` with a literal timezone name is IMMUTABLE and mirrors the Phase 6 `visits.gym_date` GENERATED column pattern (0006_visits.py:58).
- **FK target verified as `pt_package_plans` (singular `package`, plural `plans`)** against `app/modules/pt_packages/models.py:64`. Per plan instruction not to use `pt_packages_plans` (incorrect string from earlier draft).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Partial UNIQUE index requires IMMUTABLE expression**
- **Found during:** Task 2 GREEN (Alembic upgrade head)
- **Issue:** Plan-prescribed `DATE(initiated_at)` rejected by Postgres with `functions in index expression must be marked IMMUTABLE` — `DATE(timestamptz)` depends on session `TimeZone`.
- **Fix:** Changed to `((initiated_at AT TIME ZONE 'Europe/Moscow')::date)` with explicit parens to bind `::date`. Mirrors `visits.gym_date` GENERATED column from 0006_visits.py.
- **Files modified:** `apps/backend/alembic/versions/0034_online_payments.py`
- **Verification:** Migration `upgrade head → downgrade -1 → upgrade head` clean twice; 5 schema-shape tests pass.
- **Committed in:** `b18a911`

**2. [Rule 1 — Bug] CHECK / UNIQUE / FK names get double-prefixed when bare strings are passed**
- **Found during:** Task 2 GREEN (first schema-shape test run)
- **Issue:** Plan-prescribed bare-string names (e.g., `name="ck_online_payments_amount_kopecks_positive"`) collide with the `NAMING_CONVENTION` `ck_%(table_name)s_%(constraint_name)s` template — Postgres ended up with `ck_online_payments_ck_online_payments_amount_kopecks_positive` (double-prefix).
- **Fix:** Wrapped every CHECK / UNIQUE / FK name with `op.f(...)` per the established Alembic codebase convention (see 0005_memberships.py:80, 0031_payment_receipts.py:76+86). `op.f()` records the full intended name without re-application of the template.
- **Files modified:** `apps/backend/alembic/versions/0034_online_payments.py`
- **Verification:** Schema-shape test asserting exact CHECK names passes after the fix.
- **Committed in:** `b18a911`

**3. [Rule 3 — Blocking] Local DB at stale revision; alembic_version varchar(32) too narrow for current revision IDs**
- **Found during:** Task 2 GREEN (first `alembic upgrade head`)
- **Issue:** Local Postgres was at `0026_email_send_log`; advancing to head requires writing `0033_clients_email_partial_unique` (33 chars) into `alembic_version.version_num VARCHAR(32)`. asyncpg raised `StringDataRightTruncationError`.
- **Fix:** One-time `ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255);` on the local dev DB to unblock the upgrade chain. This is a dev-environment data fix; no production schema change is involved.
- **Files modified:** none in repo — DB-only operation.
- **Verification:** `alembic upgrade head` completed through to `0034_online_payments`.
- **Note:** This is a pre-existing dev DB hygiene issue (the column was created with the legacy Alembic default), not caused by this plan.

---

**Total deviations:** 3 auto-fixed (2 Rule-1 bugs in plan-prescribed migration body, 1 Rule-3 blocking dev-DB schema fix).
**Impact on plan:** All three fixes were unavoidable to land the migration. Plan body otherwise executed verbatim. No scope creep — every change is recorded in the migration file or limited to the dev DB.

## Issues Encountered

- **Pre-existing test cross-suite ordering flake** (out of scope per SCOPE BOUNDARY): when `tests/integration/test_alembic_0034_online_payments.py` runs BEFORE `tests/integrations/yookassa/test_factory.py` in the same pytest invocation, 5 factory tests fail with `expected=123456 got=999999`. Root cause: the `db_session` fixture starts the FastAPI lifespan which invokes `build_yookassa_client` that performs a real network probe to `https://api.yookassa.ru/v3/me`; combined with a respx-route leak between factory tests, the assertion check gets a stale `account_id`. This is the same class of issue that exists today between `test_alembic_clean.py` and the factory tests (verified by running on the pre-plan tree). Logged for the v1.9 test-debt sweep (analogous to DEFER-46-04). Both files pass in isolation and in reverse order; the new file does not introduce regressions.

## Acceptance Criteria Verification

### Task 1

| Criterion | Result |
|----------|--------|
| `grep "qr_payload: str \| None = None" types.py` returns 1 | PASS (line 91) |
| `grep 'confirmation_type: Literal["redirect", "qr"] = "redirect"' client.py` returns 1 | PASS (line 142) |
| `grep "idempotency_key: UUID \| str" client.py` returns 1 (impl) + 1 (docstring) | PASS (lines 41, 141) |
| `grep -c qr_payload client.py` returns ≥ 4 | PASS (7) |
| `yookassa_create_payment_qr_success` in conftest | PASS (line 63) |
| `yookassa_get_payment_qr_pending` in conftest | PASS (line 107) |
| `pytest tests/integrations/yookassa/ -x -q` exits 0 | PASS (55 passed) |
| `ruff check app/integrations/yookassa/` exits 0 | PASS |
| `mypy app/integrations/yookassa/` exits 0 | PASS (9 source files) |

### Task 2

| Criterion | Result |
|----------|--------|
| `alembic/versions/0034_online_payments.py` exists | PASS |
| `down_revision = "0033_clients_email_partial_unique"` | PASS (line 42) |
| `grep -c op.create_index` returns 2 | PASS |
| `grep -c postgresql_where` returns 2 | PASS |
| `pt_package_plans.id` FK target present (singular `package`) | PASS (line 80) |
| `alembic upgrade head → downgrade -1 → upgrade head` clean | PASS (round-trip twice) |
| `pytest tests/integration/test_alembic_0034_online_payments.py -x -q` exits 0 | PASS (5 passed) |

## Confirmation: FK target table name

The migration's three subject FKs target the **verified** table names:

- `clients.id` (existing since 0002)
- `membership_plans.id` (existing since 0004; confirmed at `app/modules/memberships/models.py:58`)
- `pt_package_plans.id` — **singular `package`, plural `plans`** — confirmed at `app/modules/pt_packages/models.py:64`. The earlier-circulated draft string `pt_packages_plans` was incorrect.
- `users.id` (existing since 0001)

## Migration Round-Trip Verification

```
Running upgrade 0033_clients_email_partial_unique -> 0034_online_payments, online_payments table + 4 indexes (Phase 49 PAY-01 / PAY-02 / D-49-05).
Running downgrade 0034_online_payments -> 0033_clients_email_partial_unique, online_payments table + 4 indexes (Phase 49 PAY-01 / PAY-02 / D-49-05).
Running upgrade 0033_clients_email_partial_unique -> 0034_online_payments, online_payments table + 4 indexes (Phase 49 PAY-01 / PAY-02 / D-49-05).
```

Round-trip clean twice. Schema-shape test asserts: table exists; 2 partial UNIQUE indexes present; 2 full UNIQUEs present; 4 CHECKs present; FK targets {clients, membership_plans, pt_package_plans, users} all present.

## User Setup Required

None — no external service configuration introduced by this plan. (A one-time `ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255);` is required for any dev environment whose local DB is at a revision older than `0027` — recorded under Deviations #3.)

## Next Phase Readiness

- **Plan 49-02** (online_payments module skeleton) can consume the `online_payments` table; ORM model in `app/modules/online_payments/models.py` is intentionally NOT shipped here (per plan note "Plan 49-02 owns the ORM model").
- **Plan 49-03** (service layer): adapter contract (`confirmation_type='qr'`, `idempotency_key: UUID | str`, `get_payment` qr_payload) is locked. Service layer can `await client.create_payment(idempotency_key=sha256_hex, confirmation_type="qr")` per D-49-08 and `await client.get_payment(payment_id)` for the QR-replay re-fetch path (D-49-04 + D-49-09). The `yookassa_get_payment_qr_pending` fixture drives `test_replay_qr_sale_refetches_and_returns_qr_payload`.
- **Plan 49-07** (E2E tests): the 3 new respx fixtures unblock the QR-flow E2E paths.
- Wave 1 bedrock complete; Wave 2 (49-03/04/05/06) may proceed in parallel once Plan 49-02 lands.

## Self-Check: PASSED

Verified all claimed files and commits exist:

- `apps/backend/alembic/versions/0034_online_payments.py` — FOUND
- `apps/backend/tests/integrations/yookassa/test_client_create_payment.py` — FOUND
- `apps/backend/tests/integration/test_alembic_0034_online_payments.py` — FOUND
- `apps/backend/app/integrations/yookassa/types.py` — modified, FOUND
- `apps/backend/app/integrations/yookassa/client.py` — modified, FOUND
- `apps/backend/tests/integrations/yookassa/conftest.py` — modified, FOUND
- Commit `9531d84` — FOUND (test RED Task 1)
- Commit `038e3cd` — FOUND (feat GREEN Task 1)
- Commit `7f05779` — FOUND (test RED Task 2)
- Commit `b18a911` — FOUND (feat GREEN Task 2)

---
*Phase: 49-online-sales-orchestrator*
*Completed: 2026-05-22*
