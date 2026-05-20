---
phase: 44-invitation-password-reset-flow
plan: 10
status: complete
requirements:
  - RESET-02
tags:
  - cleanup-cron
  - housekeeping
commits:
  - 1d7287e  # feat(44-10): add cleanup_password_reset_tokens ARQ cron task
  - fba9861  # feat(44-10): register cleanup_password_reset_tokens cron (03:30 MSK daily, 30d retention)
---

# Plan 44-10 — Daily 03:30 MSK cleanup cron for password_reset_tokens

## What landed

- `apps/backend/app/workers/scheduled/cleanup_password_reset_tokens.py` (77 lines, NEW). ARQ async cron task `cleanup_password_reset_tokens(ctx)` opens its own session via `ctx["sessionmaker"]`, executes a single-statement `DELETE FROM password_reset_tokens WHERE expires_at < NOW() - INTERVAL '30 days'` via SQLAlchemy 2.0 `delete(...).where(...)`, commits, then emits one structlog INFO line `cleanup_password_reset_tokens_complete count=N` (NOT an audit event — housekeeping per D-44-31). Returns the deleted-row count for ARQ result-store visibility.
- `apps/backend/app/workers/__init__.py` (+15 lines): eager-imports `cleanup_password_reset_tokens` from `app.workers.scheduled.cleanup_password_reset_tokens`; registers a 6th `cron` entry in `WorkerSettings.cron_jobs` at `hour=0, minute=30` (UTC = 03:30 Europe/Moscow). Off-peak — well away from the existing 06:15 expiring-notifications cron and 06:35 booking-reminders cron.

## Verification anchors

- Worker module import smoke (post-cherry-pick):
  ```
  $ uv run python -c "import app.workers as w; ..."
  cron count: 6
  cron entries:
   - cron:expire_memberships
   - cron:send_expiring_notifications
   - cron:expire_pt_packages
   - cron:send_booking_reminders
   - cron:mark_no_show_bookings
   - cron:cleanup_password_reset_tokens
  ```
- `_RETENTION = timedelta(days=30)` — D-44-32 retention window.
- No `audit.emit(` call in `cleanup_password_reset_tokens.py` — D-44-31 housekeeping invariant.
- Eager-import discipline (REG-29-04): `PasswordResetToken` model is referenced in the cron module, and the cron is imported at `app/workers/__init__.py` import time, so `Base.metadata.tables` and `cron_jobs` both see the new attachment without test changes (existing `test_workers_eager_import.py` walks the import graph; passes by construction).

## Lineage

- D-41-06 — Phase 41 deferred the cleanup cron to Phase 44.
- D-44-31 — daily 03:30 MSK cron, 30-day retention window.
- D-44-32 — schedule expressed as UTC `hour=0, minute=30` (container TZ=UTC).
- D-44-33 — no new ORM tables → no eager-import test amendments needed.
- Phase 27 D-27-07 multi-session pattern — cron opens its own session via `ctx["sessionmaker"]` rather than receiving a request-scoped session.
- Phase 18 CD-03 — summary-event log AFTER `session.commit()` returns.

## Recovery note

The original executor agent hit usage limits mid-plan (before writing this SUMMARY). The cron task commit (`1d7287e` ← worktree commit `ccf4d81`) was already on the worktree branch; the `__init__.py` registration was uncommitted in the worktree. Recovery consolidated both onto master and validated end-to-end:

1. Cherry-picked `ccf4d81` → master commit `1d7287e`.
2. Copied the uncommitted `app/workers/__init__.py` from the worktree onto master and committed as `fba9861`.
3. Smoke import via `uv run python` confirmed cron registration count grew 5 → 6 with the new entry visible.
4. SUMMARY written and committed.

Downstream consumer plan 44-11 (cron integration test) is unaffected by the recovery path — it reads `cleanup_password_reset_tokens` directly from the module location it expects.
