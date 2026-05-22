# Phase 50 — Deferred Items

Items discovered during plan execution that are OUT OF SCOPE for the
discovering plan but should be addressed in a future plan or phase.

## From Plan 50-01

### 1. `alembic check` drift: `ix_clients_email_lower_unique` not in env.py `_include_object` exclusion list

- **Discovered during:** Task 2 (Alembic 0035 schema-shape test)
- **Issue:** `uv run alembic check` reports
  `Detected removed index 'ix_clients_email_lower_unique' on 'clients'`
  because migration `0033_clients_email_partial_unique` creates this
  partial UNIQUE via `op.execute` (raw DDL) which SA autogenerate cannot
  see at the ORM-metadata level.
- **Pre-existing:** This drift exists on the 0033/0034 baseline BEFORE
  Plan 50-01 changes; it is **not** caused by the 0035 migration.
- **Fix needed:** Add `"ix_clients_email_lower_unique"` to the
  `_include_object` exclusion tuple in `apps/backend/alembic/env.py:71-88`,
  mirroring the precedent for `uq_clients_phone_alive`,
  `uq_users_email_active`, and the other raw-DDL partial-expression
  indexes already in that list.
- **Owner:** Hygiene cleanup; can be folded into any subsequent phase that
  touches `alembic/env.py` (e.g., when the next module model import is
  added).

## Plan 50-03 — out-of-scope deviations

- `apps/backend/app/core/audit_payloads.py:541` E501 line too long (148 > 100) — pre-existing ruff issue unrelated to Plan 50-03 changes. Logged here per executor scope-boundary discipline; not fixed.
- `apps/backend/tests/integration/memberships/test_freeze_resolver.py::test_telegram_checkin_frozen_oracle_safe_dm` failing on base commit (pre-existing — `HandlerContext.__new__()` missing positional args `bookings_service` and `schedule_service`). Unrelated to Plan 50-03 changes; verified by running on base before any plan edits.
