# Phase 49 — Deferred items discovered during execution

## Discovered during Plan 49-03 execution (2026-05-22)

### Pre-existing alembic drift in `tests/integration/test_alembic_clean.py`

The `alembic check` autogenerate sees:

- `remove_table 'online_payments'` (alembic 0034 ORM-vs-DB drift)
- `remove_index 'ix_clients_email_lower_unique'` (alembic 0033 ORM-vs-DB drift)
- `remove_index 'uq_online_payments_membership_double_tap'`
- `remove_index 'uq_online_payments_pt_package_double_tap'`

This was failing **before** Plan 49-03 changes (verified via `git stash` +
re-run). Root cause is mismatch between Plan 49-01 / 49-02 generated
migrations and the ORM models — out of scope for the service-layer plan.

Suggested ownership: revisit in a Plan 49-XX cleanup, or roll into the
final Phase 49 verifier pass.

### Plan 49-03 patched item (Rule 3 — blocking issue, fixed inline)

The Alembic `0034_online_payments` migration was missing
`server_default=sa.text("gen_random_uuid()")` on the `id` column, even
though the ORM model declared it (via `UUIDPkMixin`). SQLAlchemy omits
the column from INSERT statements when the ORM declares a server_default,
so inserts hit NOT-NULL on `id`. Fix shipped in this plan:

- `apps/backend/alembic/versions/0034_online_payments.py` — added
  `server_default=sa.text("gen_random_uuid()")` to the `id` column.
- Live test DB patched via one-shot `ALTER TABLE` (no formal migration
  bump — the column was new in 0034 and no production deploy has shipped
  Phase 49 yet, so amending the migration in place is safe).
