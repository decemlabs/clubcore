---
phase: 109-profile-security-backend-wiring
plan: "01"
subsystem: backend-auth
tags: [profile, password-change, audit, service-layer, schemas]
dependency_graph:
  requires: []
  provides:
    - "('profile_updated','user') locked audit event in LOCKED_AUDIT_EVENTS"
    - "ProfileUpdateRequest + ChangePasswordRequest Pydantic models"
    - "update_profile() service function (PROF-01)"
    - "revoke_other_sessions_on_password_change() helper (PROF-02)"
    - "change_password() service function (PROF-02)"
  affects:
    - apps/backend/app/core/audit.py
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/app/modules/auth/service.py
tech_stack:
  added: []
  patterns:
    - "IntegrityError catch on session.flush() -> ConflictError(fields={'email':...})"
    - "RETURNING family_id exclude-current UPDATE pattern for session revocation"
    - "Pitfall-2 audit emit before commit (all three service functions)"
key_files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/app/modules/auth/service.py
decisions:
  - "D-109-01-CONFLICT: duplicate email caught via IntegrityError on flush; re-raised as ConflictError with fields={'email':...}; route maps to 409 field error"
  - "D-109-01-NOOP-REVOKE: revoke_other_sessions_on_password_change returns 0 when user has only one active family (idempotent)"
  - "D-109-01-NULL-HASH: None password_hash takes same InvalidPassword raise path as mismatch (T-109-03 anti-oracle parity)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-14T18:55:02Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
---

# Phase 109 Plan 01: Profile & Security — Backend Foundation Summary

**One-liner:** Registered `profile_updated` locked audit event + `ProfileUpdateRequest` / `ChangePasswordRequest` Pydantic models + three service functions (`update_profile`, `revoke_other_sessions_on_password_change`, `change_password`) implementing PROF-01/PROF-02 contract with exclude-current session revocation and Argon2id hash reuse.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register profile_updated locked audit event | b6a37bf6 | app/core/audit.py |
| 2 | Add ProfileUpdateRequest + ChangePasswordRequest schemas | 5d722c19 | app/modules/auth/schemas.py |
| 3 | Add update_profile, revoke-others-except-current, change_password | 9796661a | app/modules/auth/service.py |

## What Was Built

### Task 1 — audit.py
Added `("profile_updated", "user")` to `LOCKED_AUDIT_EVENTS` frozenset, placed next to `("password_changed_revokes_sessions", "user")` per Phase 109 grouping. Payload carries only `changed_fields: list[str]` markers — no password, hash, or raw email value (T-109-01 mitigated).

### Task 2 — auth/schemas.py
- `ProfileUpdateRequest(BackendSchemaBase)`: `full_name: str | None = Field(default=None, min_length=2)`, `email: EmailStr | None = None`. Both optional for partial PATCH. `extra='forbid'` inherited from `BackendSchemaBase` kills stray keys like `theme` (client-only, no `User.theme` column). camelCase alias auto-generated.
- `ChangePasswordRequest(BackendSchemaBase)`: `current_password: str = Field(min_length=1)`, `new_password: str = Field(min_length=12)`. 12-char floor reuses the same literal as `LoginRequest.password` verbatim (NIST 800-63B). No new `MeResponse` — PATCH echoes existing; change-password returns 204.

### Task 3 — auth/service.py
Three new functions:

**`update_profile(session, *, user_id, full_name, email) -> User`**
- `session.get(User, user_id)` load; applies only non-None fields
- `session.flush()` fires the partial-UNIQUE on `lower(email) WHERE deleted_at IS NULL`
- `IntegrityError` caught → rollback → `ConflictError("email_already_in_use", fields={'email':...})`
- Emits `profile_updated` with `changed_fields` list BEFORE commit (Pitfall 2)
- Commits, refreshes, returns `User`

**`revoke_other_sessions_on_password_change(session, redis, user_id, *, current_family_id) -> int`**
- `UPDATE RefreshToken SET revoked_at=now WHERE user_id=:uid AND revoked_at IS NULL AND family_id != :current_family_id RETURNING family_id`
- Redis cleanup: `delete auth:session:{uid}:{fid}` + `srem auth:user_sessions:{uid}` for each revoked family only — current family Redis key untouched
- No commit, no audit emit (caller owns UoW boundary)

**`change_password(session, redis, *, user_id, current_password, new_password, current_family_id) -> int`**
- Loads `User`; raises `InvalidPassword` for `None` password_hash (anti-oracle parity T-109-03)
- `await verify_password(current_password, user.password_hash)` — timing-equivalent Argon2id
- `user.password_hash = await hash_password(new_password)`
- Calls `revoke_other_sessions_on_password_change` with `current_family_id`
- Emits already-locked `password_changed_revokes_sessions` BEFORE commit
- Commits; returns revoked-other count. Current refresh token is NOT rotated.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints or trust boundaries introduced (Plan 02 wires the routes). The three service functions operate on the passed `user_id` (route binds to `CurrentUser`) — PROF-02 self-service constraint (T-109-02) enforced at route layer.

## Self-Check: PASSED

Files exist:
- apps/backend/app/core/audit.py — FOUND (modified)
- apps/backend/app/modules/auth/schemas.py — FOUND (modified)
- apps/backend/app/modules/auth/service.py — FOUND (modified)

Commits:
- b6a37bf6 — FOUND (feat: register profile_updated LOCKED audit event)
- 5d722c19 — FOUND (feat: add ProfileUpdateRequest + ChangePasswordRequest schemas)
- 9796661a — FOUND (feat: add update_profile, revoke_other_sessions_on_password_change, change_password)

Verification smoke tests: ALL OK
- `('profile_updated','user') in LOCKED_AUDIT_EVENTS`
- `ProfileUpdateRequest.model_validate({'fullName':'Ivan Petrov'})` → full_name='Ivan Petrov', email=None
- `ProfileUpdateRequest({'theme':'dark'})` → ValidationError (extra forbidden)
- `ChangePasswordRequest({'currentPassword':'x','newPassword':'short'})` → ValidationError (min_length=12)
- `hasattr(service, 'update_profile') and hasattr(service, 'change_password') and hasattr(service, 'revoke_other_sessions_on_password_change')`
- `'current_family_id' in inspect.signature(change_password).parameters`
- `mypy --strict` clean on all 3 files
- `ruff check` clean on all 3 files
