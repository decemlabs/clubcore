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
