
## Out-of-scope discoveries (Plan 45-02)

- **Pre-existing ruff E501 in `app/core/audit_payloads.py:534`** — `UserInvitedPayload`
  docstring line is 148 chars (> 100 limit). Phase 43 / USERS-* lineage, NOT touched
  by Plan 45-02. Not blocking this plan (file already shipped to master with the
  violation; no per-file ignore in ruff.toml). Recommend fixing in a Phase 43 cleanup
  pass or Phase 45 verifier sweep.
