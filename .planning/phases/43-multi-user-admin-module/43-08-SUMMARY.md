---
phase: 43-multi-user-admin-module
plan: 08
subsystem: backend/tests/integration/users
tags: [phase-43, users, integration-tests, audit-log, wave-4]
requires:
  - users-module Wave 2 (43-04..43-06) — service.create_user / list_users + router
  - users tests conftest fixtures (43-07b) — authed_client_owner / seeded_active_reception_email
provides:
  - 6 end-to-end integration tests covering POST /api/v1/users 4-branch matrix + GET /users pagination
  - real audit_log SELECT assertions (no mock-only path) for user_invited event
affects:
  - apps/backend/tests/integration/users/test_users_crud.py (new)
  - apps/backend/app/modules/users/service.py (Rule 1 fix — UUID/datetime stringification at audit boundary)
  - apps/backend/app/integrations/email/dispatcher.py (Rule 3 fix — users.email_templates registry wired)
  - apps/backend/.importlinter (ignore_imports extended for new dispatcher → users.email_templates edge)
tech_added: []
patterns:
  - JSONB boundary serialization: `str(uuid_value)` + `dt.isoformat()` at audit.emit() callsites
  - Per-module email template registry: walker in `_resolve_template` plus matching .importlinter exception
key_files_created:
  - apps/backend/tests/integration/users/test_users_crud.py
  - .planning/phases/43-multi-user-admin-module/deferred-items.md
key_files_modified:
  - apps/backend/app/modules/users/service.py
  - apps/backend/app/integrations/email/dispatcher.py
  - apps/backend/.importlinter
decisions:
  - "Audit payload UUIDs serialized as str() at the service-layer emit boundary (REG-36-03 lineage carried forward — JSONB has no UUID-aware serializer; Pydantic schemas accept str → UUID coercion during validation)"
  - "Per-module template walker takes a new branch for `users.email_templates`; the comment in dispatcher.py:81-83 had pre-flagged this as the Phase 43/44/45 extension point"
  - "Tests target real AuditLog.action column (not a `event` column — the ORM stores audit event under `action`, matching audit.emit(event=...) parameter mapping in app/core/audit.py:402)"
  - "Error envelope assertion uses `r.json()['code']` (not nested `detail.error`) per app/core/exceptions.register_exception_handlers shape — mirrors clients/test_clients_crud.py:96"
metrics:
  duration_minutes: 28
  tasks_completed: 1
  files_created: 2
  files_modified: 3
  test_count: 6
  audit_log_select_count: 5
  commit: f5eb2c5
completed: "2026-05-19T15:14:58Z"
---

# Phase 43 Plan 08: USERS-01/02/03/05 Integration Tests Summary

**One-liner:** 6 integration tests over httpx ASGITransport land the full D-43-13 POST /users 4-branch matrix (no-row → 201, pending → idempotent re-invite, active → 409 `email_already_active`, soft-deleted → INSERT new id) plus GET /users pagination + D-43-10 response denylist; surfaces two real product bugs (audit JSONB UUID-serialization in users/service.py, missing users template registry in integrations/email/dispatcher.py) which are fixed in the same commit.

## What Was Built

One file at `apps/backend/tests/integration/users/test_users_crud.py` with 6 async tests:

1. `test_create_happy_returns_201_and_emits_user_invited` — D-43-13 branch A.
2. `test_create_with_include_invite_link_returns_url_and_audit_link_copied_true` — D-43-14 escape-hatch path; verifies `link_copied=True` in audit payload AND raw URL is NOT in payload (Pitfall 4 anti-oracle).
3. `test_create_pending_user_idempotent_re_invite` — D-43-13 branch B; same email POSTed twice keeps the same user.id and produces two `user_invited` audit rows.
4. `test_create_email_already_active_returns_409` — D-43-13 branch C; consumes `seeded_active_reception_email` fixture from 43-07b conftest.
5. `test_soft_deleted_email_can_be_re_invited_with_new_id` — D-43-13 branch D / USERS-05; create → soft-delete → re-create same email returns a different user.id (partial-UNIQUE permits INSERT path).
6. `test_list_users_paginated_envelope_no_password_leak` — USERS-02 / D-43-10 denylist (passwordHash, telegramChatId, emailVerified, passwordChangedAt absent) + required fields present (id, email, fullName, role, isActive, status, createdAt, isDeactivated).

### Test Discipline (D-43-33 / D-43-34)

- Fixtures consumed by name from `tests/integration/users/conftest.py` (43-07b): `authed_client_owner`, `db_session`, `seeded_active_reception_email`. Zero redefinitions.
- Audit assertions hit `AuditLog` via real `select(AuditLog).where(AuditLog.action == ...)`; five distinct SELECT sites (one per test that exercises an audit-emitting endpoint).
- No `monkeypatch` use; no `actor_context_var` patching. ContextVar is populated naturally through the real `ActorContextMiddleware` because tests authenticate via the standard `/api/v1/auth/login` cookie flow.

### Real audit_log rows observed per test

| Test | event/action | rows | resource_id |
|------|-------------|------|-------------|
| test_create_happy_returns_201_and_emits_user_invited | `user_invited` | 1 | new user.id |
| test_create_with_include_invite_link_returns_url_and_audit_link_copied_true | `user_invited` (link_copied=true) | 1 | new user.id |
| test_create_pending_user_idempotent_re_invite | `user_invited` (re-issued) | 2 | same user.id |
| test_create_email_already_active_returns_409 | none (409 short-circuits) | 0 | — |
| test_soft_deleted_email_can_be_re_invited_with_new_id | `user_invited` (deleted row) | ≥1 | old user.id |
| test_list_users_paginated_envelope_no_password_leak | none (read-side) | 0 | — |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Audit emit payload had raw UUID + datetime instances (asyncpg JSONB serializer rejects them)**

- **Found during:** Task 1, first test run (`test_create_happy_returns_201_and_emits_user_invited` failed with `TypeError: Object of type UUID is not JSON serializable`).
- **Issue:** `app/modules/users/service.py` (Phase 43 plan 43-05) passed `audit_correlation_id=audit_correlation_id` (UUID), `invited_user_id=user.id` (UUID), `invitation_expires_at=token.expires_at` (datetime) directly. The Pydantic schema `UserInvitedPayload` accepts UUID / datetime instances during validation, but `audit.emit` stores the original kwargs (not the validated model) into `AuditLog.payload` JSONB — asyncpg's JSON encoder has no UUID/datetime adapter. Pre-existing pattern in `app/modules/auth/service.py:rotate_refresh` already stringified UUIDs at the audit boundary (REG-36-03 / Phase 42 discipline); the users service had drifted from this convention.
- **Fix:** Wrap UUIDs with `str(...)` and datetimes with `.isoformat()` at every users-service `audit.emit` callsite (5 events: `user_invited`, `user_deactivated`, `user_reactivated`, `user_soft_deleted`, `user_invitation_revoked`). Pydantic schemas accept str → UUID/datetime coercion during validation, so the FORBID-extra invariant holds.
- **Files modified:** `apps/backend/app/modules/users/service.py`.
- **Commit:** bdd4a5e.

**2. [Rule 3 — Blocking] Per-module template walker in `_resolve_template` did not know about `users.email_templates`**

- **Found during:** Task 1, first test run (raised `KeyError: "template_id 'USER_INVITATION_EMAIL' not in any per-module registry (Phase 42 only: auth.email_templates); add the per-module import here when Phase 44/45 register additional template files."`).
- **Issue:** Phase 43 plan 43-02 landed the `app/modules/users/email_templates.py` registry with `USER_INVITATION_EMAIL`, and plan 43-05 issued the dispatcher call with the literal `template_id="USER_INVITATION_EMAIL"`. But the resolver in `app/integrations/email/dispatcher.py:_resolve_template` only walks the auth module; Phase 43 never extended it. The comment on lines 81-83 of `dispatcher.py` had pre-flagged this exact extension point ("add the per-module import here when Phase 44/45 register additional template files"); the Phase 43 wave 2 plans never carried out the extension. Without this, every POST /api/v1/users would 500 in production once email dispatch left the sandbox.
- **Fix:** Added `from app.modules.users.email_templates import TEMPLATES as USERS_TEMPLATES` (function-scoped) plus a second registry check before the KeyError; added the matching `app.integrations.email.dispatcher -> app.modules.users.email_templates` line to `apps/backend/.importlinter` `ignore_imports` so the existing `integrations-not-depend-on-modules` contract stays GREEN. Verified via `lint-imports`: `integrations must not import modules` stays KEPT.
- **Files modified:** `apps/backend/app/integrations/email/dispatcher.py`, `apps/backend/.importlinter`.
- **Commit:** bdd4a5e.

### Plan-text vs runtime drift (test-side adaptations)

The plan-text test stubs referenced `AuditLog.event` (the ORM column is `AuditLog.action` per `app/core/audit_models.py:49`) and `r.json()["detail"]["error"]` (the AppError handler at `app/core/exceptions.py:399-411` emits `{"code", "message", "fields"}`). These two drifts in the plan-text snippet were corrected to match the real surface; no production code was touched for this adaptation.

### Out-of-Scope Deferred

- **Stale `*@test.local` rows in `users` table:** Two leaked rows (`cr04-*@test.local`) from pre-Phase-43 tests broke `test_list_users_paginated_envelope_no_password_leak` because Pydantic v2 EmailStr rejects the RFC-2606 reserved `.local` TLD when validating the response. The rows were deleted manually (one-time `DELETE FROM users WHERE email LIKE '%@test.local'`) and logged in `.planning/phases/43-multi-user-admin-module/deferred-items.md` for the v1.9 doc-debt / test-debt sweep. Root cause is a CR-04 lineage test that issues a non-SAVEPOINT commit; out of scope for Phase 43.

## Pre-Existing Issues (Out of Scope)

- **Import-linter contract `modules cannot import each other` BROKEN** — `app.modules.users.repository` imports `app.modules.auth.password_reset_token_model` (plan 43-04). Already documented in `43-07b-SUMMARY.md`; not touched by this plan.

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| All tests pass | `pytest tests/integration/users/test_users_crud.py -q` | 6/6 PASS |
| ≥6 async tests | `grep -c 'async def test_' tests/integration/users/test_users_crud.py` | 6 PASS |
| ≥3 AuditLog references | `grep -c 'AuditLog' tests/integration/users/test_users_crud.py` | 15 PASS |
| 0 monkeypatch uses | `grep -c 'monkeypatch' tests/integration/users/test_users_crud.py` | 0 PASS |
| 0 actor_context_var uses | `grep -c 'actor_context_var' tests/integration/users/test_users_crud.py` | 0 PASS |
| conftest.py + __init__.py untouched | `git diff --name-only HEAD~2 HEAD` | does not list those files PASS |
| ruff check clean | `ruff check tests/integration/users/test_users_crud.py app/modules/users/service.py app/integrations/email/dispatcher.py` | All checks passed! PASS |
| ruff format clean | `ruff format --check ...` | clean PASS |
| mypy strict clean | `mypy --strict ...` | Success: no issues found in 3 source files PASS |
| integrations contract KEPT | `lint-imports` | integrations must not import modules KEPT PASS |
| Adjacent suite unaffected | `pytest tests/unit/test_locked_email_templates_ast.py tests/integration/auth/ -q` | 51 passed, 1 xfailed PASS |

## Self-Check: PASSED

- File `apps/backend/tests/integration/users/test_users_crud.py` — exists, 282 LOC, 6 async tests.
- File `.planning/phases/43-multi-user-admin-module/deferred-items.md` — exists.
- Modified file `apps/backend/app/modules/users/service.py` — exists, 5 `str(...)` stringifications at audit boundaries.
- Modified file `apps/backend/app/integrations/email/dispatcher.py` — exists, users template walker branch present.
- Modified file `apps/backend/.importlinter` — exists, ignore_imports extended.
- Commit `bdd4a5e` — present in `git log --oneline`.
- Commit `f5eb2c5` — present in `git log --oneline` (docstring tweak to satisfy `monkeypatch` zero-grep acceptance criterion).
