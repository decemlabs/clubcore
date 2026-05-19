# Phase 42 — Deferred Items

Out-of-scope discoveries logged during plan execution (not auto-fixed,
not in scope for the current plan).

## From plan 42-10 execution (2026-05-19)

### Pre-existing alembic drift (out of scope, not caused by 42-10)
- `tests/integration/test_alembic_clean.py::test_alembic_check_clean` fails at HEAD
  baseline with operations against `booking_notifications`, `membership_notifications`,
  and `users` (UniqueConstraint changes, dropped `channel`/`deleted_at` columns).
- Reproduced BEFORE 42-10 changes (verified via `git stash` round-trip).
- Plan 42-10 touches none of those tables — leaving as-is.
- Suggest assigning to an early Phase 42 plan or a Phase 43 cleanup pass.

### Pre-existing mypy errors in app.modules.auth (out of scope)
- `app/modules/auth/{router,service,telegram_service}.py` have 3 mypy errors
  about `User` not being explicitly exported from `app.modules.auth.models`.
- Surfaced only because mypy --strict on app/api/v1/router.py follows imports.
- Not caused by 42-10; 42-10's own files pass mypy --strict cleanly.
