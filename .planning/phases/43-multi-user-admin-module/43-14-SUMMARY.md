---
phase: 43-multi-user-admin-module
plan: 14
subsystem: users-invitation-flow
tags: [bug-fix, invitation, email, audit, timezone]
dependency_graph:
  requires: [43-05, 43-11]
  provides: [USERS-03-functional-correctness, WR-02-overwrite-policy, WR-06-expired-revoke, WR-07-msk-datetime, IN-01-audit-correlation]
  affects: [apps/backend/app/modules/users/service.py, apps/backend/app/modules/users/repository.py, apps/backend/app/core/exceptions.py]
tech_stack:
  added: []
  patterns: [ZoneInfo-Europe/Moscow, render-at-enqueue, overwrite-policy, expired-token-guard]
key_files:
  created:
    - apps/backend/tests/unit/users/test_format_expires_ru.py
    - apps/backend/tests/integration/users/test_invitation_email_envelope.py
    - apps/backend/tests/integration/users/test_revoke_expired_invitation.py
    - apps/backend/tests/integration/users/test_reinvite_overrides_pending_user_data.py
  modified:
    - apps/backend/app/modules/users/service.py
    - apps/backend/app/modules/users/repository.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/tests/integration/users/test_users_invitation_flow.py
    - .planning/phases/43-multi-user-admin-module/43-CONTEXT.md
decisions:
  - "WR-02 overwrite policy: Branch B overwrites full_name/role from the re-invite POST body (vs raise 409 mismatch). Rationale: matches operator UX of POST-to-fix-typo; the existing partial-UNIQUE + flush surfaces any real constraint violation."
  - "TEMPLATES import removed from service.py after CR-01 fix (ROLE_RU still used). Ruff would flag unused import."
metrics:
  duration: "~35 minutes"
  completed: "2026-05-19T18:53:55Z"
  tasks_completed: 7
  files_changed: 9
---

# Phase 43 Plan 14: Invitation Flow Gap-Closure Summary

**One-liner:** Close 5 REVIEW findings (CR-01 empty email, WR-02 silent re-invite, WR-06 expired-revoke, WR-07 UTC→MSK, IN-01 spurious correlation IDs) with 3 source patches, 4 new test files, and 2 CONTEXT.md deferral notes.

## What Was Built

Plan 43-14 closed all findings from the Phase 43 code review that centered on the invitation flow:

### CR-01 (BLOCKER): Invitation email arrived empty

**Root cause:** `service.create_user` pre-rendered the template locally and passed `subject`/`html`/`text` as `**envelope_fields` to the dispatcher. The dispatcher ignores unknown keys (those are not Jinja template variables) and re-renders against the actual template — but the real variables (`full_name`, `role_ru`, `invitation_url`, `expires_at_human`) were never passed. Result: `Здравствуйте, !` with an empty `<a href="">`.

**Fix:** Dropped the local render (deleted `TEMPLATES` import, `render_kwargs`, `envelope_fields` variables). Now passes raw template vars directly matching the Phase 42 `EMAIL_OTP_LOGIN` callsite pattern.

### WR-02 (WARNING): Re-invite silently kept old full_name/role

**Fix:** Branch B now applies **overwrite policy** — `existing.full_name = data.full_name` and `existing.role = data.role` before the atomic-consume. This is the most operator-UX-friendly choice: POST-to-fix-typo works as expected.

### WR-06 (WARNING): Revoking an expired token succeeded silently

**Fix (two-layer):**
1. Service-layer pre-check: `if token.expires_at <= now: raise InvitationExpiredError("invitation_expired")` — owner UI now sees 409 `invitation_expired` instead of 204.
2. Repository defence-in-depth: `atomic_consume_invitation_token_by_id` now filters on `PasswordResetToken.expires_at > _now_utc()` so the race window between the pre-check and the UPDATE is covered.
3. Added `InvitationExpiredError` to `app/core/exceptions.py` (409 `invitation_expired`).

### WR-07 (WARNING): Expiry timestamp rendered in UTC in a Russian-language email

**Fix:** `_format_expires_ru` now calls `dt.astimezone(_MOSCOW_TZ)` before formatting, and appends `(МСК)` suffix. Added `_MOSCOW_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Moscow")` module constant (mirrors `integrations/telegram/handlers.py` precedent).

### IN-01 (INFO): Fabricated uuid4() at terminal events

**Fix:** `deactivate_user`, `reactivate_user`, `soft_delete_user`, and `revoke_invitation` now pass `audit_correlation_id=None`. `create_user` keeps `audit_correlation_id=str(audit_correlation_id)` (it chains to email_send_* downstream rows). `uuid4` import retained (still used by `create_user`).

### IN-03 + IN-04 (INFO): Deferred

Both recorded in `43-CONTEXT.md ## Deferred Ideas`:
- **IN-03:** `INVITATION_TOKEN_TTL` → `Settings` field deferred to v1.7.
- **IN-04:** `ck_users_role` naming-cleanup deferred to future Alembic pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing test `test_invitation_email_enqueued_through_sandbox` asserted on email["subject"] and email["text"]**
- **Found during:** Task 6 (regression suite)
- **Issue:** `test_users_invitation_flow.py::test_invitation_email_enqueued_through_sandbox` asserted `email["subject"]` and `email["text"]` — keys that were present in the PRE-FIX recorder (old code passed pre-rendered `subject`/`html`/`text` as kwargs). After CR-01 fix, recorder captures raw template vars instead.
- **Fix:** Updated assertions to check `email["full_name"]` and `email["invitation_url"]` — the actual post-fix keys in the recorder.
- **Files modified:** `apps/backend/tests/integration/users/test_users_invitation_flow.py`
- **Commit:** `60a71d1`

**2. [Rule 1 - Bug] ruff RUF001/RUF002 on Cyrillic `(МСК)` in service.py strings and docstrings**
- **Found during:** Task 1 verification
- **Issue:** ruff RUF001 (ambiguous Cyrillic chars in string literals) and RUF002 (in docstrings) raised 9 errors.
- **Fix:** Added `# noqa: RUF001` to the f-string literal; removed `(МСК)` from the docstring example text to avoid RUF002 on that line. Replaced verbose docstring with concise form.
- **Files modified:** `apps/backend/app/modules/users/service.py`

**3. [Rule 3 - Deviation] `TEMPLATES` import removed post-CR-01**
- After the CR-01 fix, `TEMPLATES` became unused at runtime. Per the plan: "remove the import if ruff complains." Ruff would flag it as F401. Removed from `service.py`. `ROLE_RU` still used.
- The AST walker test (`43-13`) inspects for the literal `template_id="USER_INVITATION_EMAIL"` string in the file — still present at the dispatcher callsite. Walker does not require the `TEMPLATES` import.

## Known Stubs

None. All invitation flow changes are functional end-to-end.

## Threat Flags

No new network endpoints, auth paths, or schema changes were introduced. The `InvitationExpiredError` addition to `exceptions.py` is a response code only — no new surface.

## Grep Verification Matrix

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -c '"subject":' service.py` | 0 | 0 |
| `grep -c '"html":' service.py` | 0 | 0 |
| `grep -c 'envelope_fields' service.py` | 0 | 0 |
| `grep -cE '\(МСК\)' service.py` | ≥1 | 3 (literal + noqa comment; key invariant met) |
| `grep -c 'ZoneInfo' service.py` | ≥1 | 3 |
| `grep -c 'invitation_url=invitation_url' service.py` | 1 | 1 |
| `grep -c 'full_name=user.full_name' service.py` | 1 | 1 |
| `grep -c 'role_ru=role_ru' service.py` | 1 | 1 |
| `grep -c 'expires_at_human=expires_at_human' service.py` | 1 | 1 |
| `grep -c 'class InvitationExpiredError' exceptions.py` | 1 | 1 |
| `grep -c '"invitation_expired"' exceptions.py` | ≥1 | 1 |
| `grep -c 'InvitationExpiredError' service.py` | ≥2 | 3 |
| `grep -c 'audit_correlation_id=None' service.py` | 4 | 4 |
| `grep -c 'PasswordResetToken.expires_at > _now_utc()' repository.py` | ≥1 | 1 |
| `grep -c 'existing.full_name = data.full_name' service.py` | 1 | 1 |
| `grep -c 'existing.role = data.role' service.py` | 1 | 1 |
| `grep -c 'await session.commit()' service.py` | ≥5 | 5 |
| ruff + mypy --strict on 3 files | green | PASS |
| lint-imports | 0 broken | PASS |

## Test Results

Full regression suite (Task 6): **80 passed, 1 xfailed** (xfail is the RESET-06 anti-oracle test — expected).

New test files:
- `tests/unit/users/test_format_expires_ru.py` — 3 passed
- `tests/integration/users/test_invitation_email_envelope.py` — 2 passed
- `tests/integration/users/test_revoke_expired_invitation.py` — 2 passed
- `tests/integration/users/test_reinvite_overrides_pending_user_data.py` — 1 passed

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `229b000` | fix | Close CR-01/WR-02/WR-06/WR-07/IN-01 in users invitation flow |
| `3d75730` | test | Unit tests for _format_expires_ru MSK conversion (WR-07) |
| `ab91bd9` | test | Integration test for CR-01 — invitation email carries invitation_url kwarg |
| `d684f6a` | test | Integration test for WR-06 — expired invitation revoke returns 409 |
| `fb5ac4e` | test | Integration test for WR-02 — re-invite overwrites full_name/role |
| `60a71d1` | fix | Update test_invitation_email_enqueued_through_sandbox for CR-01 fix |
| `22f1952` | docs | Record IN-03 + IN-04 deferrals in CONTEXT.md Deferred Ideas |

## Self-Check: PASSED
