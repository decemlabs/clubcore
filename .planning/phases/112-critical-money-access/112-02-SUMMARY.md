---
phase: 112-critical-money-access
plan: "02"
subsystem: backend-users
tags: [rbac, audit, role-change, team-01, infra-15]
dependency_graph:
  requires: [112-01]
  provides: [PATCH /api/v1/users/{user_id}/role, user_role_changed audit event]
  affects: [users module, audit taxonomy, exceptions, test suite]
tech_stack:
  added: []
  patterns:
    - PATCH /{id}/action endpoint (mirror of deactivate_user_endpoint)
    - INFRA-15 pre-registered audit event + payload (before callsite)
    - old_role capture before ORM bulk UPDATE (SQLAlchemy identity-map edge case)
key_files:
  created:
    - apps/backend/tests/integration/users/test_users_role_change.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/app/modules/users/schemas.py
    - apps/backend/app/modules/users/repository.py
    - apps/backend/app/modules/users/service.py
    - apps/backend/app/modules/users/router.py
decisions:
  - id: D-112-02-OLDROLECAPTURE
    text: >
      Capture old_role value BEFORE repository.update_user_role call. SQLAlchemy 2.0
      ORM bulk UPDATE via session.execute(update(User)...) uses synchronize_session='evaluate'
      which mutates the in-memory identity-map entry for the loaded target object.
      Accessing target.role AFTER the UPDATE returns the new value, not the old one.
      Fix: cache old_role_value = target.role.value before the UPDATE.
  - id: D-112-02-AUDITPAYLOAD-CORREID
    text: >
      UserRoleChangedPayload includes audit_correlation_id: UUID | None field (IN-01 terminal
      event, caller passes None). Required because AUDIT_PAYLOAD_SCHEMAS with extra='forbid'
      validates ALL kwargs passed to audit.emit — the change_user_role callsite passes
      audit_correlation_id=None following the UserDeactivatedPayload pattern.
metrics:
  duration: "6 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 7
  files_created: 1
---

# Phase 112 Plan 02: Staff Role Change Backend Summary

Backend for TEAM-01: `PATCH /api/v1/users/{user_id}/role` endpoint with full guard chain, audit, and ASGITransport tests. Owner can change staff user role (owner ↔ reception); role persists immediately and is audited; new role applies on target's NEXT login (no session invalidation).

## What Was Built

### Task 1: Audit registration + payload + exceptions + schema
- `("user_role_changed", "user")` added to `LOCKED_AUDIT_EVENTS` frozenset, placed next to `user_deactivated` in the v1.6 multi-user-admin lifecycle block (INFRA-15 pre-registration before callsite)
- `UserRoleChangedPayload(audit_correlation_id, changed_user_id, old_role, new_role)` added to `audit_payloads.py` with `extra="forbid"` and role pattern `^(owner|reception)$`; registered in `AUDIT_PAYLOAD_SCHEMAS`
- `CannotChangeOwnRoleError` (409 `cannot_change_own_role`) and `CannotChangeLastOwnerRoleError` (409 `cannot_change_last_owner_role`) added to `exceptions.py` next to the existing `CannotDeactivateLastOwnerError` group
- `UserRoleChangeRequest(role: Role)` added to `users/schemas.py` (BackendSchemaBase = extra='forbid')

### Task 2: Repository + service + endpoint
- `update_user_role(session, *, target_user_id, new_role)` in `repository.py` — single UPDATE with `deleted_at IS NULL` defence-in-depth (IN-02 pattern from deactivate_user); no commit/flush (service owns UoW)
- `change_user_role(session, actor, target_user_id, new_role)` in `service.py`:
  - Guard chain: `get_alive` → `UserNotFoundError` → self-guard `CannotChangeOwnRoleError` → (owner-demotion) `count_active_owners_excluding` → `CannotChangeLastOwnerRoleError`
  - `update_user_role` + `audit.emit("user_role_changed")` + `flush` + `commit`
  - NO session invalidation (T-112-13 accepted — role takes effect on next login)
- `change_user_role_endpoint` PATCH `/{user_id}/role` in `router.py`: `require_permission(UPDATE, USERS)` BEFORE `verify_csrf` (RBAC-04), 204 No Content
- ruff + mypy strict clean on `app/modules/users/`

### Task 3: ASGITransport integration tests
- 8 test cases in `test_users_role_change.py` using existing conftest fixtures
- Happy path: promote reception → owner (204), demote non-last owner → reception (204), persist read-back
- Guard tests: reception → 403 forbidden, self-change → 409, last-owner demotion → 409 (or self-409 for combined case), no-CSRF → 403 csrf_mismatch
- Audit assertion: 1 `user_role_changed` row with correct old_role/new_role/changed_user_id fields
- 8/8 green

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Old role value captured before ORM UPDATE, not after**
- **Found during:** Task 3 (audit row test)
- **Issue:** SQLAlchemy 2.0 ORM bulk UPDATE via `session.execute(update(User)...)` uses `synchronize_session='evaluate'` which updates the Python identity-map entry. `target.role` after `update_user_role()` already reflected the new role, causing the audit payload to record `old_role == new_role` (both 'owner' in the test that promoted reception→owner).
- **Fix:** Cache `old_role_value = target.role.value` before calling `repository.update_user_role()`.
- **Files modified:** `apps/backend/app/modules/users/service.py`
- **Commit:** d8ebe736

**2. [Rule 2 - Missing] UserRoleChangedPayload missing audit_correlation_id field**
- **Found during:** Task 3 (first test run crash)
- **Issue:** `AUDIT_PAYLOAD_SCHEMAS` validates ALL kwargs passed to `audit.emit()` with `extra="forbid"`. The service callsite passes `audit_correlation_id=None` following the `UserDeactivatedPayload` pattern; the initially-defined `UserRoleChangedPayload` lacked this field, causing `pydantic_core.ValidationError: Extra inputs are not permitted`.
- **Fix:** Added `audit_correlation_id: UUID | None` as first field of `UserRoleChangedPayload` (IN-01 terminal event; mirrors `UserDeactivatedPayload` shape for the v1.6+ user-admin family).
- **Files modified:** `apps/backend/app/core/audit_payloads.py`
- **Commit:** d8ebe736

## Threat Surface Scan

No new security-relevant surfaces beyond those already listed in the plan's threat register:
- `PATCH /users/{id}/role` is gated by `require_permission(UPDATE, USERS)` (OWNER_ONLY → T-112-08 mitigated)
- Self-guard enforced (T-112-09 mitigated)
- Last-owner guard reuses `count_active_owners_excluding` row-lock (T-112-10 mitigated)
- CSRF protection via `verify_csrf` (T-112-11 mitigated)
- `user_role_changed` audit row co-committed with UPDATE (T-112-12 mitigated)
- No session invalidation (T-112-13 accepted by design)
- CISO-01 byte-parity unaffected — no permissions enum change; `(Action.UPDATE, Resource.USERS)` was already in OWNER_ONLY

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| test_users_role_change.py exists | FOUND |
| service.py exists | FOUND |
| Commit 28cf8e08 (Task 1) | FOUND |
| Commit 3efe75ac (Task 2) | FOUND |
| Commit d8ebe736 (Task 3) | FOUND |
| 8/8 tests green | PASSED |
| ruff + mypy clean on users/ | PASSED |
