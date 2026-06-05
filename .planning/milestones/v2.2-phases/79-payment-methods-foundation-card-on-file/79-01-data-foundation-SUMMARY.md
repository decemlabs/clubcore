---
phase: 79-payment-methods-foundation-card-on-file
plan: 01
subsystem: database
tags: [postgres, alembic, sqlalchemy, payment-methods, migrations]

# Dependency graph
requires:
  - phase: 51-online-refunds
    provides: online_payments table (base for save_payment_method column add)
  - phase: 68-client-auth
    provides: clients table (FK target for client_payment_methods.client_id)
provides:
  - Migration 0052 — client_payment_methods table + save_payment_method column on online_payments
  - ClientPaymentMethod ORM model (app.modules.payment_methods.models)
  - save_payment_method: Mapped[bool] on OnlinePayment ORM model
  - app.modules.payment_methods package registered in importlinter (INFRA-15)
  - Live schema verified: table + partial unique index predicate + column all present
affects:
  - 79-02 — repository and service layer reads ClientPaymentMethod
  - 79-03 — webhook step 8.5 writes to client_payment_methods via raw SQL upsert
  - 79-04 — endpoint schemas project ClientPaymentMethod columns

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Partial UNIQUE index via Index(postgresql_where=text(...)) in __table_args__ — literal
      name NOT wrapped in op.f() per 0034/0037/0046 precedent
    - Single-active-card lifecycle via explicit unlinked_at column (no SoftDeleteMixin)
    - ADD COLUMN with server_default (metadata-only on Postgres 16 — negligible lock)

key-files:
  created:
    - apps/backend/alembic/versions/0052_client_payment_methods.py
    - apps/backend/app/modules/payment_methods/__init__.py
    - apps/backend/app/modules/payment_methods/models.py
  modified:
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/alembic/env.py
    - apps/backend/.importlinter

key-decisions:
  - "Partial UNIQUE index name uq_client_payment_methods_client_id_alive is a literal string in both migration and ORM __table_args__ — not via op.f()"
  - "ClientPaymentMethod uses UUIDPkMixin + TimestampMixin without SoftDeleteMixin — lifecycle tracked via unlinked_at column"
  - "yookassa_method_id stored plaintext (consistent with existing yookassa_payment_id handling); column comment mandates it is never serialized to client"
  - "save_payment_method defaults to false at DB level (server_default); never client-writable post-checkout (T-79-02)"
  - "app.modules.payment_methods registered in importlinter modules-independent contract per INFRA-15 discipline"

patterns-established:
  - "Single-active-card constraint: partial UNIQUE on (client_id) WHERE unlinked_at IS NULL — DB enforces one active card per client"
  - "Token column with plaintext + comment guard pattern: yookassa_method_id with explicit never-wire-to-client comment"

requirements-completed: [PAYM-01, PAYM-03, PAYM-04]

# Metrics
duration: 20min
completed: 2026-06-03
---

# Phase 79 Plan 01: Data Foundation Summary

**Migration 0052 creates client_payment_methods with partial-UNIQUE alive index; ClientPaymentMethod ORM model and save_payment_method intent column on OnlinePayment verified on local Postgres 16 stack**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-03T13:00:00Z
- **Completed:** 2026-06-03T13:20:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Migration 0052 creates `client_payment_methods` table with 9 business columns + UUID PK + timestamps
- Partial UNIQUE index `uq_client_payment_methods_client_id_alive` on `(client_id) WHERE unlinked_at IS NULL` enforces single active card per client (T-79-03)
- `online_payments.save_payment_method` boolean column added via ADD COLUMN (metadata-only on PG16)
- `ClientPaymentMethod` ORM model maps table 1:1 including the partial unique index in `__table_args__`
- `save_payment_method: Mapped[bool]` added to `OnlinePayment` model
- `app.modules.payment_methods.models` registered in `alembic/env.py` for autogenerate
- `app.modules.payment_methods` registered in `.importlinter` modules-independent contract (INFRA-15)
- `alembic downgrade -1` + `alembic upgrade head` round-trip verified clean
- Schema verified via async SQL introspection: table + index predicate + column all present (SCHEMA_OK)

## Files Created/Modified

- `apps/backend/alembic/versions/0052_client_payment_methods.py` — Migration DDL (table + index + column add)
- `apps/backend/app/modules/payment_methods/__init__.py` — Package marker
- `apps/backend/app/modules/payment_methods/models.py` — ClientPaymentMethod ORM model
- `apps/backend/app/modules/online_payments/models.py` — Added Boolean import + save_payment_method column
- `apps/backend/alembic/env.py` — Registered payment_methods.models for autogenerate
- `apps/backend/.importlinter` — Registered app.modules.payment_methods in modules-independent contract

## Decisions Made

- Partial UNIQUE index name is a literal string (not via `op.f()`) per 0034/0037/0046 create_index precedent
- `unlinked_at` column tracks lifecycle; no `SoftDeleteMixin` (matches online_payments single-temporal-column discipline)
- `yookassa_method_id` stored as plaintext `Text` — consistent with existing `yookassa_payment_id` handling; comment mandates it is NEVER serialized to client
- `save_payment_method` server_default false at DB level (T-79-02: no client-writable flip path)

## Deviations from Plan

### Auto-added (Rule 2 — Missing Critical)

**1. [Rule 2 - Missing Critical] Registered app.modules.payment_methods in .importlinter**
- **Found during:** Task 3 (post-migration)
- **Issue:** Plan 79-01 did not explicitly list the importlinter registration as a task, but PATTERNS.md lines 619-643 and INFRA-15 discipline require every new module to be registered before first commit to prevent architectural drift
- **Fix:** Added `app.modules.payment_methods` to the `modules-independent` contract in `.importlinter`
- **Files modified:** apps/backend/.importlinter
- **Verification:** `uv run lint-imports` exits with 3 contracts kept, 0 broken
- **Committed in:** 7e0b31ed

---

**Total deviations:** 1 auto-added (missing critical — INFRA-15 compliance)
**Impact on plan:** No scope creep; registration is required before downstream phases use the module.

## Threat Surface Scan

No new threat surface beyond what the plan's threat model covers:
- T-79-01 (yookassa_method_id column): plaintext, never-wire comment applied in model
- T-79-02 (save_payment_method): server_default false, not client-writable
- T-79-03 (partial UNIQUE constraint): DB-enforced single active card

## Self-Check: PASSED

Files verified:
- apps/backend/alembic/versions/0052_client_payment_methods.py: FOUND
- apps/backend/app/modules/payment_methods/__init__.py: FOUND
- apps/backend/app/modules/payment_methods/models.py: FOUND

Commits verified:
- c827eb75 (migration 0052): FOUND
- 691dbf01 (ClientPaymentMethod model): FOUND
- 7e0b31ed (importlinter registration): FOUND
