# Phase 41 deferred items

Items discovered during plan 41-09 execution that are out-of-scope per
SCOPE BOUNDARY (issues NOT directly caused by current task's changes).

## alembic check pre-existing drift (NOT from 41-09)

After 0025 landed and the new ORM module was registered in env.py, `alembic
check` still reports drift from earlier plans:

1. `users.email` UNIQUE constraint — ORM model `app/core/models.py:33`
   still declares `unique=True` on `email`, but migration 0022 dropped
   `uq_users_email` and replaced it with the partial-UNIQUE
   `uq_users_email_active`. Plan 41-05 SUMMARY notes this as documented
   drift; Phase 43 USERS module owns the final `User` ORM mapping per
   D-41-07. Resolution: remove `unique=True` from `User.email` in Phase 43
   or sooner if it surfaces during a touch.
2. `users.deleted_at` column — ORM does NOT declare this column; migration
   0022 added it. Same lineage — Phase 43 owns the ORM mapping (D-41-07).
3. `booking_notifications.channel` + `membership_notifications.channel`
   columns + the recreated `(subject_id, kind, channel)` UNIQUE — ORM
   models in `app/modules/bookings/models.py` and
   `app/modules/memberships/models.py` were NOT updated when migration 0024
   (Plan 41-08) landed. Plan 41-08 SUMMARY explicitly defers the ORM-side
   addition to Phase 45 (NOTIFY-* phase that actually reads the column).

These are tracked here so they don't get repeatedly re-discovered. Plan
41-09 is responsible only for the `password_reset_tokens` schema/ORM
parity — that piece is clean after env.py registration.
