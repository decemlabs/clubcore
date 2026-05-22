---
phase: 50-webhook-fsm-fiscal-foundation
plan: 01
subsystem: backend/fiscal_receipts
tags: [alembic, fsm, fiscal, 54-fz, schema, caller-owns-txn]
requires:
  - 0034_online_payments (Phase 49 migration head)
  - app.modules.payments.models.Payment (FK target)
provides:
  - app.modules.fiscal_receipts.constants.FISCAL_RECEIPT_STATUS_TRANSITIONS
  - app.modules.fiscal_receipts.models.FiscalReceipt (ORM)
  - app.modules.fiscal_receipts.repository.{insert_fiscal_receipt, get_fiscal_receipt_by_id, get_fiscal_receipt_by_payment_id_and_kind}
  - 0035_fiscal_receipts (alembic head, UNIQUE payment_id+kind, FK payments.id ON DELETE RESTRICT)
affects:
  - apps/backend/alembic/env.py (Base.metadata registers FiscalReceipt + OnlinePayment)
tech-stack:
  added: []
  patterns:
    - Declarative-FSM via MappingProxyType (mirrors memberships/constants.py:22, Phase 24 D-24-03)
    - Caller-owns-txn repository (D-32-10 / D-50-28; only session.add, no flush/commit)
    - BARE-suffix CHECK constraint naming (avoids Plan 49-01 deviation #2 double-prefix bug)
key-files:
  created:
    - apps/backend/app/modules/fiscal_receipts/__init__.py
    - apps/backend/app/modules/fiscal_receipts/constants.py
    - apps/backend/app/modules/fiscal_receipts/models.py
    - apps/backend/app/modules/fiscal_receipts/repository.py
    - apps/backend/alembic/versions/0035_fiscal_receipts.py
    - apps/backend/tests/unit/fiscal_receipts/__init__.py
    - apps/backend/tests/unit/fiscal_receipts/test_module_skeleton.py
    - apps/backend/tests/integration/test_alembic_0035_fiscal_receipts.py
    - .planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md
  modified:
    - apps/backend/alembic/env.py
decisions:
  - "T-50-01-01 mitigation: fiscal_receipts.payment_id FK targets payments.id (NOT online_payments.id) — fiscal obligation attaches to the committed ledger row"
  - "FISCAL-02 enforced as DB-level UNIQUE(payment_id, kind) cross-channel-discriminator: at most one 'payment' + one 'refund' receipt per Payment row"
  - "Caller-owns-txn (D-50-28): repository never calls flush/commit; webhook UoW (D-50-18 step 5) owns the transactional moment"
  - "FSM state set is {pending, sent, succeeded, failed}; Phase 50 inserts as 'sent', Phase 51 ARQ task transitions to 'succeeded'/'failed' (D-50-32)"
  - "ORM uses BARE-suffix CHECK names (name=\"kind\", name=\"status\") so SA NAMING_CONVENTION expands to ck_fiscal_receipts_* matching the migration op.f() literals — avoids the double-prefix bug fixed by Plan 49-01 deviation #2"
metrics:
  duration: "~50 min"
  completed: "2026-05-22T16:52:36Z"
  tasks_completed: 2
  files_created: 9
  files_modified: 1
  commits: 5
---

# Phase 50 Plan 01: Alembic 0035 fiscal_receipts + module skeleton — Summary

Ship the `fiscal_receipts` table and the `app/modules/fiscal_receipts/` module skeleton (constants / ORM / caller-owns-txn repository) as the schema bedrock for the Phase 50 ЮKassa webhook FSM. The webhook UoW (D-50-18 step 5) will INSERT `status='sent'` rows; Phase 51's ARQ task will flip them to terminal `succeeded` / `failed`. The cross-channel-discriminator UNIQUE `(payment_id, kind)` (FISCAL-02) prevents duplicate receipts per ledger row.

## What Shipped

### 1. `app/modules/fiscal_receipts/` module (Task 1)

- **`constants.py`** — Declarative-FSM transition table mirroring `memberships/constants.py:22`. `FISCAL_RECEIPT_STATUS_TRANSITIONS` is a `MappingProxyType[str, frozenset[str]]` with exactly four keys: `pending → {sent}`, `sent → {succeeded, failed}`, `succeeded → ∅`, `failed → ∅`. Status / kind literals pinned to the migration CHECK enums.
- **`models.py`** — `FiscalReceipt(Base, UUIDPkMixin)` ORM with 11 columns: `id`, `payment_id` (FK `payments.id` ON DELETE RESTRICT), `kind`, `status`, `yookassa_receipt_id`, `customer_email`, `failure_reason`, `sent_at`, `succeeded_at`, `failed_at`, `audit_correlation_id`. Two `CheckConstraint`s use BARE suffixes (`name="kind"`, `name="status"`) so SA NAMING_CONVENTION expands to the same literal Alembic wrote via `op.f()` (avoiding the double-prefix bug fixed by Plan 49-01 deviation #2). One `UniqueConstraint("payment_id", "kind", name="uq_fiscal_receipts_payment_id_kind")` enforces FISCAL-02.
- **`repository.py`** — Three async functions: `insert_fiscal_receipt`, `get_fiscal_receipt_by_id`, `get_fiscal_receipt_by_payment_id_and_kind`. Caller-owns-txn discipline (D-50-28): only `session.add` is called — never `session.flush` or `session.commit`. Insert function carries the `# noqa: SVC001` marker per the `payments/service.py:90` precedent.

### 2. Alembic 0035 migration (Task 2)

- **`apps/backend/alembic/versions/0035_fiscal_receipts.py`** — `down_revision="0034_online_payments"`. Creates `fiscal_receipts` table mirroring the ORM column-for-column via `op.f()`-wrapped constraint names (`pk_fiscal_receipts`, `fk_fiscal_receipts_payment_id_payments`, `ck_fiscal_receipts_kind`, `ck_fiscal_receipts_status`, `uq_fiscal_receipts_payment_id_kind`). Downgrade drops the UNIQUE constraint before `drop_table` (T-50-01-05 mitigation — partial-state teardown fails loudly).
- Round-trip `alembic downgrade 0034_online_payments → alembic upgrade 0035_fiscal_receipts` verified clean.

### 3. `alembic/env.py` registration (auto-add — Rule 2)

- Added `import app.modules.fiscal_receipts.models` (Phase 50 0035) and `import app.modules.online_payments.models` (Phase 49 0034 — was missing from env.py upstream) so `Base.metadata` resolves both tables at autogenerate time. `alembic check` no longer reports `Detected removed table 'fiscal_receipts'` or `'online_payments'`.

### 4. Test suite

- **`tests/unit/fiscal_receipts/test_module_skeleton.py`** — 24 unit tests covering the constants enum literals, transition-table read-only Mapping shape, all 11 ORM column declarations, FK target + ondelete, UNIQUE constraint registration, and a `MagicMock`-driven contract test that the repository never calls `session.flush` / `session.commit`.
- **`tests/integration/test_alembic_0035_fiscal_receipts.py`** — 7 schema-shape tests:
  1. `fiscal_receipts` table exists after `alembic upgrade head`
  2. UNIQUE `uq_fiscal_receipts_payment_id_kind` ships with both columns `(payment_id, kind)`
  3. CHECK constraints `ck_fiscal_receipts_kind` + `ck_fiscal_receipts_status` exist
  4. FK targets `payments.id` (NOT `online_payments.id`) with ON DELETE RESTRICT
  5. Row-level CHECK enforcement: `kind='invoice'` → `IntegrityError`
  6. Row-level CHECK enforcement: `status='invalid'` → `IntegrityError`
  7. Row-level UNIQUE enforcement: duplicate `(payment_id, 'payment')` → `IntegrityError`; different kind `(payment_id, 'refund')` succeeds

  Row-level tests use the W-3 locked Payment factory analog (constructor shape from `tests/integration/payments/conftest.py::make_payment` and `test_payment_receipt_race.py:106-117`), seeding a `User` + `Payment` directly inside the SAVEPOINT session.

## Commits

| # | Hash | Type | Subject |
|---|------|------|---------|
| 1 | `8484e72` | test | add failing tests for fiscal_receipts module skeleton (RED) |
| 2 | `1dcaeb0` | feat | fiscal_receipts module skeleton (constants + ORM + repository) (GREEN) |
| 3 | `97c8d01` | test | add failing schema-shape test for Alembic 0035 (RED) |
| 4 | `44a2a40` | feat | Alembic 0035 fiscal_receipts migration + env.py registration (GREEN) |
| 5 | `ec89bba` | docs | record deferred ix_clients_email_lower_unique drift item |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan referenced `app.modules.users.models.User` + `app.modules.users.constants.Role`**

- **Found during:** Task 2 (RED test authoring)
- **Issue:** The plan's W-3 LOCKED seeding-shape snippet imported `User` from `app.modules.users.models` and `Role` from `app.modules.users.constants`. These import paths do not exist in the repository — the verified analog (`test_payment_receipt_race.py:34-35`) imports `User` from `app.core.models` and `Role` from `app.core.permissions`.
- **Fix:** Used the verified import paths in the integration test. Maintains the W-3 lock on the *constructor shape* (which is what FK seeding correctness depends on); only corrects the misstated module paths.
- **Files modified:** `apps/backend/tests/integration/test_alembic_0035_fiscal_receipts.py`
- **Commit:** `97c8d01`

**2. [Rule 2 - Critical missing] `online_payments.models` was missing from `alembic/env.py`**

- **Found during:** Task 2 (running `alembic check` after applying 0035)
- **Issue:** `alembic check` reported `Detected removed table 'online_payments'` AND `'fiscal_receipts'`. The `fiscal_receipts` drift is directly caused by this plan; the `online_payments` drift is pre-existing (Phase 49 Plan 49-02 shipped the model but did not register it with `Base.metadata` in env.py).
- **Fix:** Added BOTH `import app.modules.fiscal_receipts.models` (own scope) AND `import app.modules.online_payments.models` (correctness restoration — env.py drift would persist into Phase 50 plans if left). Both are now registered alongside the other module-model imports.
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** `44a2a40`

**3. [Rule 3 - Blocking] Missing `.env` file blocked alembic invocations**

- **Found during:** Task 2 (first `alembic current` call after writing migration)
- **Issue:** `Settings()` in `app.core.config` requires `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY`; running `alembic` with no `.env` fails with Pydantic ValidationError.
- **Fix:** `cp apps/backend/.env.example apps/backend/.env` (file is `.gitignore`d; not committed). Same pattern used by `tests/conftest.py:38-45` for the test harness.
- **Files modified:** none committed (`.env` is `.gitignore`d).
- **Commit:** n/a

### Test-Count Deviation

The plan listed 6 schema-shape tests including a `test_0035_downgrade_drops_table` test. That test was omitted from the integration test file because the `db_session` fixture uses SAVEPOINT mode against an already-upgraded DB — driving `alembic downgrade` from inside the session is incompatible with the fixture's lifecycle. The downgrade path is exercised by the round-trip `alembic downgrade 0034_online_payments && alembic upgrade 0035_fiscal_receipts` shell invocation (per the plan's verification step #2) and is verified clean. This matches the precedent in `test_alembic_0034_online_payments.py`, which similarly does not contain a downgrade test.

## Deferred Issues

Recorded in `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md`:

- **`ix_clients_email_lower_unique`** is a partial UNIQUE index created via raw `op.execute` DDL in migration 0033; SA autogenerate cannot see it at the ORM-metadata level, so `alembic check` reports it as a removed index. Pre-existing condition from the 0033/0034 baseline; should be added to the `_include_object` exclusion tuple in a future plan that touches `alembic/env.py` (alongside `uq_clients_phone_alive`, `uq_users_email_active`, and the other raw-DDL partial-expression indexes already excluded).

## Authentication Gates

None — all verification ran against the local compose Postgres (no external services touched).

## Verification

| Check | Result |
|-------|--------|
| `alembic upgrade head` | OK (head = `0035_fiscal_receipts`) |
| `alembic downgrade 0034_online_payments && alembic upgrade head` round-trip | OK (clean teardown + reapply) |
| `pytest tests/integration/test_alembic_0035_fiscal_receipts.py` (7 tests) | 7 passed |
| `pytest tests/unit/fiscal_receipts/` (24 tests) | 24 passed |
| `ruff check app/modules/fiscal_receipts/ alembic/versions/0035_fiscal_receipts.py` | All checks passed |
| `mypy app/modules/fiscal_receipts/` | Success: no issues found in 4 source files |
| `lint-imports` | Pre-existing warnings only (unrelated to fiscal_receipts) |

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries were introduced outside the `<threat_model>` in 50-01-PLAN.md. The 11-column `fiscal_receipts` table sits inside the existing trust boundary set declared by the plan (T-50-01-01..06 all addressed: FK ON DELETE RESTRICT, UNIQUE constraint, `audit_correlation_id` lineage, downgrade ordering).

## Known Stubs

None. The module is a foundation skeleton: every declared column maps to a migration column, every constant maps to a CHECK literal, every repository function is fully wired (no placeholders).

## Self-Check: PASSED

**Files created — all FOUND:**
- `apps/backend/app/modules/fiscal_receipts/__init__.py` — FOUND
- `apps/backend/app/modules/fiscal_receipts/constants.py` — FOUND
- `apps/backend/app/modules/fiscal_receipts/models.py` — FOUND
- `apps/backend/app/modules/fiscal_receipts/repository.py` — FOUND
- `apps/backend/alembic/versions/0035_fiscal_receipts.py` — FOUND
- `apps/backend/tests/unit/fiscal_receipts/__init__.py` — FOUND
- `apps/backend/tests/unit/fiscal_receipts/test_module_skeleton.py` — FOUND
- `apps/backend/tests/integration/test_alembic_0035_fiscal_receipts.py` — FOUND
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — FOUND

**Commits — all FOUND:**
- `8484e72` test(50-01) — FOUND
- `1dcaeb0` feat(50-01) module skeleton — FOUND
- `97c8d01` test(50-01) schema-shape — FOUND
- `44a2a40` feat(50-01) Alembic 0035 — FOUND
- `ec89bba` docs(50-01) deferred items — FOUND
