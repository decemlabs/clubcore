
## Out-of-scope discoveries (Plan 45-02)

- **Pre-existing ruff E501 in `app/core/audit_payloads.py:534`** — `UserInvitedPayload`
  docstring line is 148 chars (> 100 limit). Phase 43 / USERS-* lineage, NOT touched
  by Plan 45-02. Not blocking this plan (file already shipped to master with the
  violation; no per-file ignore in ruff.toml). Recommend fixing in a Phase 43 cleanup
  pass or Phase 45 verifier sweep.

## Out-of-scope discoveries (Plan 45-08)

- **Pre-existing failure `tests/integration/bookings/test_bookings_router_smoke.py::test_repository_no_direct_schedule_import`** — the test greps the
  *raw source bytes* of `app/modules/bookings/repository.py` for the literal
  string `"from app.modules.schedule"`. A Phase 40 docstring at lines 50-60
  (function `_slot_trainer_attr`) mentions `from app.modules.schedule.models`
  inside a markdown-style code-comment explaining why importlib.import_module
  is used; the grep cannot distinguish source from docstring. Predates Plan
  45-08 (verified via `git stash` on HEAD before any 45-08 changes).
  Recommend tightening the test to either use AST-walk (skip docstrings) OR
  rephrase the docstring sentence to avoid the literal trigger. Not blocking.

- **Pre-existing failure `tests/integration/bookings/test_create_booking_via_bot.py::test_create_booking_via_bot_pt_package_expired_before_slot`** —
  test expects `PtPackageExpiredBeforeSlotError` but gets
  `PtPackageNotActiveError`. The cause is the active-PT-package resolver's
  upstream SQL filter `(end_date IS NULL OR end_date >= today)` which
  already rejects packages whose end_date is in the past, so the
  service-layer Step 4 Moscow-TZ guard (PtPackageExpiredBeforeSlot) is
  unreachable for the test's fixture shape. The test seeds an
  expired-but-still-active row that the resolver query filters out. Predates
  Plan 45-08. Either the test fixture needs to bypass the resolver filter
  or the assertion needs to accept `PtPackageNotActiveError`. Not blocking.

- **Pre-existing failures listed in 45-03 deferred items still hold**:
  `tests/unit/workers/test_worker_settings.py` (Phase 44 cron count drift),
  `tests/integration/test_route_introspection.py` (Phase 44
  password-reset routes), `tests/integration/telegram/test_handler_start.py`
  + `tests/integration/memberships/test_freeze_resolver.py`
  + `tests/integration/telegram_bot/test_book_callback.py`
  (`HandlerContext.__new__()` arg-count drift from Phase 40 changes).
  All reproduced on the pre-45-08 HEAD; carried forward.

## Out-of-scope discoveries (Plan 45-03)

- **Pre-existing failures in `tests/unit/workers/test_worker_settings.py`** — two tests
  (`test_worker_settings_cron_resolves_to_registered_function`,
  `test_worker_settings_functions_registered`) hard-code
  `len(WorkerSettings.functions) == 6`. Phase 44 D-44-31 added
  `cleanup_password_reset_tokens` to the functions list (count is now 7) but those
  unit-test expectations were not updated. Reproduced on HEAD with `git stash`
  reporting no local changes — proves the regression predates Plan 45-03 (introduced
  by the Phase 44 cron-housekeeping landing). Recommend bumping the asserted count
  to 7 (and the corresponding `cron_jobs` length assertion to 6 if present) in a
  Phase 44 cleanup or Phase 45 verifier sweep.
