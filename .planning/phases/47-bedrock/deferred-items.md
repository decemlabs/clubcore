# Phase 47 Deferred Items

Items discovered during plan execution that are OUT OF SCOPE for the
current plan but worth logging for later pickup.

## Plan 47-01

### Pre-existing E501 ruff error in audit_payloads.py:534

`app/core/audit_payloads.py` line 534 (inside `UserInvitedPayload`,
Phase 43 vintage) carries a 148-character trailing comment that exceeds
the project's 100-char line-length:

```
    link_copied: bool = False  # Phase 43 D-43-14 — default False = forensic "owner has not yet clicked the copy-link button" at user creation time.
```

- Confirmed pre-existing via `git stash && uv run ruff check` (still fails
  on the unmodified file).
- Not introduced by 47-01; SCOPE BOUNDARY rule — not fixed here.
- Suggested fix: split the trailing comment onto its own line(s) above
  the field, or shorten the rationale. One-line patch.

## Plan 47-04

### Pre-existing mypy strict error: `User` not exported from `app.modules.auth.models`

`uv run mypy --strict` on `app/modules/auth/{service,router,telegram_service}.py`
+ `app/modules/users/router.py` reports:

```
error: Module "app.modules.auth.models" does not explicitly export attribute "User"  [attr-defined]
```

- Confirmed pre-existing on the Phase 47 base (last touch on those files
  is commit `629b433` from Plan 43-17, well before 47-04).
- Not introduced by 47-04; SCOPE BOUNDARY rule — not fixed here.
- Suggested fix: add `User` to `__all__` (or an `__all__ = ["User", ...]`
  block) in `app/modules/auth/models.py`. Tiny patch.

### Pre-existing test_worker_settings.py count drift (Phase 44 added cleanup_password_reset_tokens)

`tests/unit/workers/test_worker_settings.py` has two stale assertions:

- `test_worker_settings_cron_resolves_to_registered_function` — asserts
  `len(WorkerSettings.cron_jobs) == 5`; the actual count is `6` (Phase 44
  D-44-31/32 appended `cleanup_password_reset_tokens` cron).
- `test_worker_settings_functions_registered` — asserts
  `len(WorkerSettings.functions) == 6`; actual is `7` (same Phase 44
  growth).

- Confirmed pre-existing on the Phase 47 base via `git stash` + rerun.
- Not introduced by 47-04; SCOPE BOUNDARY rule — not fixed here.
- Suggested fix: bump both expected counts (5→6, 6→7) AND add explicit
  presence assertions for `cleanup_password_reset_tokens` so future drift
  shows the missing entry rather than a numeric mismatch. Tiny patch.
