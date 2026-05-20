
## Out-of-scope discoveries (Plan 45-02)

- **Pre-existing ruff E501 in `app/core/audit_payloads.py:534`** — `UserInvitedPayload`
  docstring line is 148 chars (> 100 limit). Phase 43 / USERS-* lineage, NOT touched
  by Plan 45-02. Not blocking this plan (file already shipped to master with the
  violation; no per-file ignore in ruff.toml). Recommend fixing in a Phase 43 cleanup
  pass or Phase 45 verifier sweep.

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
