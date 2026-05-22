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

## Plan 49-05 — Out-of-scope discoveries (executor)

### Pre-existing E501 line-too-long in test_route_introspection.py:35
Line 35 (`/api/v1/auth/otp/request` comment) is 108 chars; pre-dates plan 49-05.
Confirmed via `git stash && ruff check` on base. Not modified by this plan.

### Pre-existing mypy errors in app/modules/online_payments/router.py (4 errors)
Errors at lines 185/234/280/323 (now shifted to 208/257/303/346 due to ADDITIVE edits below)
about `confirmation_type: str` not matching `Literal['redirect', 'qr']`. Originate from
Plan 49-04; confirmed via `git stash && mypy` on base. The /return handler added by
this plan introduces ZERO new mypy errors.

### Pre-existing test failure: test_every_protected_route_declares_a_gate
Failing for `/api/v1/auth/password-reset/{request,confirm}` and `/api/v1/users/invitations/accept`
on the base commit (confirmed via `git stash && pytest`). Plan 49-05's EXCLUDED_PATHS
addition for `/api/v1/online-payments/return` works correctly — `/return` does NOT appear
in the missing-gate failure list. Sanity-belt tests
(`test_excluded_paths_set_is_locked`, `test_gate_prefixes_match_factory_names`) pass.
