---
phase: 109-profile-security-backend-wiring
verified: 2026-06-14T23:05:00Z
human_verified: 2026-06-15T02:45:00Z
status: passed
human_verification_status: "completed via automated browser UAT (chrome-devtools-mcp) — 109-UAT.md complete (10/10); BUG-5 (wrong-password logout) found, fixed, re-verified live; profile/email-taken/password-change happy-path all confirmed. See .planning/v3.1-UAT-BROWSER-AUDIT.md"
score: 12/12 must-haves verified + 10/10 browser-UAT
overrides_applied: 0
human_verification:
  - test: "Settings → Профиль — edit full name, click Save"
    expected: "SaveBar appears while dirty; 'Профиль обновлён' toast on save; SaveBar disappears; sidebar/header identity and avatar update to new name without full reload"
    why_human: "SaveBar dirty state, toast visibility, and sidebar real-time refresh require browser rendering"
  - test: "Settings → Профиль — edit email to an ALREADY-USED address, click Save"
    expected: "Inline 'Email уже занят' under the email input; SaveBar stays visible"
    why_human: "Inline field error placement and SaveBar persistence require browser rendering"
  - test: "Settings → Профиль — fix to a unique email, click Save"
    expected: "Success toast, SaveBar clears, identity updates"
    why_human: "Requires a seeded second user in the DB and browser interaction"
  - test: "Settings → Профиль — edit a field, click 'Отменить'"
    expected: "Field reverts to saved value, SaveBar disappears"
    why_human: "Cancel/revert behavior requires browser interaction with the global SaveBar state machine"
  - test: "Settings → Безопасность — click 'Сменить пароль'"
    expected: "Modal opens with title 'Сменить пароль' and three password fields visible"
    why_human: "Modal open/close, field rendering, and AdaptiveModal responsive layout require browser"
  - test: "ChangePasswordModal — enter wrong current password + valid 12-char new (confirm matches), submit"
    expected: "Inline 'Неверный текущий пароль' on the current-password input; modal stays open"
    why_human: "Inline error on a specific field inside a modal requires browser interaction against the live backend"
  - test: "ChangePasswordModal — enter CORRECT current password + new ≥12-char (confirm matches), submit"
    expected: "Modal closes; toast 'Пароль изменён. Другие сессии завершены.'; active-sessions count drops; THIS session stays logged in (no redirect to /login)"
    why_human: "Requires live backend round-trip, session revocation visible in UI, and confirmation the current session survives"
  - test: "ChangePasswordModal — enter new password < 12 chars"
    expected: "Submit button disabled (canSubmit=false); no submission possible"
    why_human: "Button disabled state and submit prevention require browser interaction"
  - test: "ChangePasswordModal — enter new password ≠ confirm"
    expected: "Submit button disabled; if keyboard-submitted, inline 'Пароли не совпадают' on confirm field"
    why_human: "Confirm-mismatch disabled state and potential inline error require browser rendering"
  - test: "Settings page overall — verify theme toggle row is unchanged and theme is NOT sent in PATCH body"
    expected: "ThemeToggle in ProfileSection still functions; a network capture on profile Save shows no 'theme' field in the PATCH body"
    why_human: "Requires DevTools network capture to confirm the PATCH body shape"
---

# Phase 109: Profile & Security Backend Wiring — Verification Report

**Phase Goal:** A staff member can edit their own profile and change their own password from Settings, on real new endpoints, with the existing session-revocation discipline.
**Verified:** 2026-06-14T23:05:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `('profile_updated','user')` is a LOCKED audit event | VERIFIED | Line 298 of `apps/backend/app/core/audit.py`: tuple present in `LOCKED_AUDIT_EVENTS` frozenset; Python import smoke confirmed |
| 2 | `ProfileUpdateRequest` accepts `{fullName?, email?}`, rejects extra fields (theme), enforces EmailStr | VERIFIED | `schemas.py:187-200`; smoke test: camelCase alias works, `theme` raises ValidationError, extra=forbid inherited from BackendSchemaBase |
| 3 | `ChangePasswordRequest` enforces 12-char floor on `newPassword` | VERIFIED | `schemas.py:203-215`; smoke test: `newPassword='short'` raises ValidationError |
| 4 | `update_profile()` stores `email.lower()` (CR-01 fix applied) | VERIFIED | `service.py:1265`: `user.email = email.lower()` with comment; Test 8 (`test_patch_me_mixed_case_email_stored_lowercase_login_succeeds`) passes |
| 5 | `update_profile()` narrows IntegrityError to `uq_users_email_active` constraint (WR-02 fix) | VERIFIED | `service.py:1278`: `if "uq_users_email_active" in orig:` — other IntegrityErrors re-raised as 500 |
| 6 | `revoke_other_sessions_on_password_change()` revokes other families, keeps current alive | VERIFIED | `service.py:1318-1327`: UPDATE filters `family_id != current_family_id AND revoked_at IS NULL`; Redis cleanup only for revoked families; no audit/commit here |
| 7 | `change_password()` verifies current password (timing-equiv), hashes new with Argon2id, revokes others, keeps current session alive | VERIFIED | `service.py:1342-1399`: `verify_password` reused; `hash_password` reused; calls `revoke_other_sessions_on_password_change`; emits `password_changed_revokes_sessions` before commit |
| 8 | `PATCH /api/v1/auth/me` exists: auth FIRST, CSRF second (RBAC-04), echoes MeResponse, duplicate email → 409 | VERIFIED | `router.py:292-328`: `require_authenticated()` FIRST, `verify_csrf` second; returns `ResponseEnvelope[MeResponse]`; all-None body guard → 422; ConflictError propagated as 409 |
| 9 | `POST /api/v1/auth/change-password` exists: auth FIRST, CSRF second, returns 204 No Content | VERIFIED | `router.py:331-401`: `status_code=HTTP_204_NO_CONTENT`, `response_model=None`; current_family_id resolved from cc_refresh cookie; WR-01 log warning on nil-UUID fallback |
| 10 | Integration tests: 15 tests pass (8 profile update + 7 change password), covering happy path, email-taken 409, wrong password, revoke-others-keeps-current, CSRF 403, auth 401, audit rows | VERIFIED | `pytest tests/integration/auth/test_profile_update.py tests/integration/auth/test_change_password.py -q`: **15 passed in 5.04s** |
| 11 | RBAC parity unchanged: 42 entries, no permissions.py change, route introspection green | VERIFIED | `pytest test_route_introspection.py test_rbac_parity.py -v`: **7 passed**; `test_owner_only_count_is_forty_two` PASSED |
| 12 | FE: `ProfileUpdateSchema`/`ChangePasswordSchema` + `useUpdateProfile()`/`useChangePassword()` exist; ProfileSection editable; ChangePasswordModal wired; SettingsPage registers profile | VERIFIED | schemas.ts:112,131; api.ts:138,171; ChangePasswordModal.tsx:50 (`useChangePassword`); SectionsTop.tsx:120 (`useUpdateProfile`), :352 (modal render); SettingsPage.tsx:116 (`registerSave('profile')`); 350/350 FE tests pass |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/audit.py` | `('profile_updated','user')` in LOCKED_AUDIT_EVENTS | VERIFIED | Line 298; frozenset member confirmed by import smoke |
| `apps/backend/app/modules/auth/schemas.py` | `ProfileUpdateRequest` + `ChangePasswordRequest` | VERIFIED | Lines 187-215; both classes present with correct field constraints |
| `apps/backend/app/modules/auth/service.py` | `update_profile()`, `revoke_other_sessions_on_password_change()`, `change_password()` | VERIFIED | Lines 1231, 1298, 1342; all three functions present with correct signatures and logic |
| `apps/backend/app/modules/auth/router.py` | PATCH /me + POST /change-password routes | VERIFIED | Lines 292, 331; both routes registered; `create_app()` smoke confirmed |
| `apps/backend/tests/integration/auth/test_profile_update.py` | 8 integration test scenarios (incl. Test 8 CR-01 mixed-case) | VERIFIED | 371 lines; 8 test functions; all pass |
| `apps/backend/tests/integration/auth/test_change_password.py` | 7 integration test scenarios | VERIFIED | 394 lines; 7 test functions; all pass |
| `apps/admin-app/src/features/auth/schemas.ts` | `ProfileUpdateSchema` + `ChangePasswordSchema` | VERIFIED | Lines 112, 131; both exported with Russian messages and inferred types |
| `apps/admin-app/src/features/auth/api.ts` | `useUpdateProfile()` + `useChangePassword()` | VERIFIED | Lines 138, 171; PATCH/POST via `staffRequest` with `as never` casts; correct invalidation keys |
| `apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx` | AdaptiveModal with useChangePassword wired | VERIFIED | 199 lines; line 50 `useChangePassword()`; line 107 `'Неверный текущий пароль'`; full form state + error handling present |
| `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` | Editable ProfileSection with SaveBar + useUpdateProfile + ChangePasswordModal | VERIFIED | Line 120 `useUpdateProfile()`; lines 127-133 seed from `session.data`; line 352 `<ChangePasswordModal>` |
| `apps/admin-app/src/pages/settings/SettingsPage.tsx` | `registerSave('profile')` + `registerCancel('profile')` | VERIFIED | Lines 116-117 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `service.py` | `audit.py` | `audit.emit('profile_updated', ...)` | WIRED | Line 1285-1292: `await audit.emit(session, 'profile_updated', ...)` before commit |
| `service.py` | `audit.py` | `audit.emit('password_changed_revokes_sessions', ...)` | WIRED | Line 1389-1397 (in change_password); reuses already-locked event |
| `service.py` | `security.py` | `verify_password` + `hash_password` | WIRED | Lines 1374, 1376: both reused, no new crypto |
| `router.py` | `service.py` | `update_profile()` + `change_password()` calls | WIRED | Lines 314, 393 |
| `router.py` | `verify_csrf` | signature dep after `require_authenticated` | WIRED | Lines 297, 341: `verify_csrf` declared SECOND on both routes (RBAC-04 401-before-403) |
| `SectionsTop.tsx` | `useUpdateProfile` + `authKeys.me` | `handleSave` PATCH + invalidate | WIRED | Line 120 import; line 164 `updateProfile.mutate(body, ...)`; hook invalidates `authKeys.me` on success |
| `ChangePasswordModal.tsx` | `useChangePassword` | modal submit | WIRED | Line 6 import; line 50 `useChangePassword()`; line 93 `changePassword.mutate(...)` |
| `SettingsPage.tsx` | `ProfileSection` | `registerSave('profile')` prop | WIRED | Lines 116-117 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ProfileSection` (SectionsTop.tsx) | `session.data` (fullName, email) | `useSession()` → `GET /api/v1/auth/me` → DB | Real User row from Postgres | FLOWING |
| `ChangePasswordModal.tsx` | `changePassword.mutate(result.data)` | `useChangePassword()` → `POST /api/v1/auth/change-password` → `change_password()` service → DB | Real Argon2id hash update + RefreshToken revoke | FLOWING |
| `update_me` route (router.py) | `updated_user` | `update_profile()` → `session.flush()` → DB commit | Real User UPDATE with partial UNIQUE | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Both new routes registered in the app | `create_app()` path/method set check | `('/api/v1/auth/me','PATCH')` and `('/api/v1/auth/change-password','POST')` present | PASS |
| `('profile_updated','user')` in LOCKED_AUDIT_EVENTS | `python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; assert ('profile_updated','user') in LOCKED_AUDIT_EVENTS"` | OK | PASS |
| ProfileUpdateRequest/ChangePasswordRequest import smoke | `python -c` schema validations | camelCase alias, extra=forbid, 12-char floor all confirmed | PASS |
| service functions have correct signatures | `inspect.signature(change_password)` | `current_family_id` parameter present | PASS |
| 15 integration tests pass | `pytest tests/integration/auth/test_profile_update.py tests/integration/auth/test_change_password.py -q` | 15 passed in 5.04s | PASS |
| RBAC parity 42 entries, route introspection clean | `pytest test_route_introspection.py test_rbac_parity.py -v` | 7 passed | PASS |
| mypy --strict on 4 modified backend files | `uv run mypy --strict app/core/audit.py app/modules/auth/schemas.py app/modules/auth/service.py app/modules/auth/router.py` | Success: no issues found in 4 source files | PASS |
| ruff on 4 modified backend files | `uv run ruff check ...` | All checks passed | PASS |
| import-linter | `uv run lint-imports` | Contracts: 3 kept, 0 broken | PASS |
| FE typecheck | `pnpm -F @clubcore/admin-app typecheck` | tsc -b --noEmit clean | PASS |
| FE lint | `pnpm -F @clubcore/admin-app lint` | ESLint clean | PASS |
| FE tests | vitest run | 350 passed (27 test files) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROF-01 | 109-01, 109-02, 109-03, 109-04 | Staff can edit their own profile (full name, email) via PATCH /api/v1/auth/me | SATISFIED | Route exists, service function correct, email lowercased, 409 on duplicate, frontend hooks + ProfileSection wired, 8 integration tests pass |
| PROF-02 | 109-01, 109-02, 109-03, 109-04 | Staff can change their own password (current + new, 12-char floor; revokes other sessions) | SATISFIED | Route exists, verify_password + hash_password reused, revoke-others-except-current confirmed, ChangePasswordModal wired, 7 integration tests pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `SectionsTop.tsx` | ~363 | Hardcoded "47 дней назад" password-last-changed hint in SecuritySection | INFO (IN-02 from review, deferred per scope) | Cosmetic/UX only — backend does not yet expose `password_changed_at`; deferred to future phase per review decision |

No TBD/FIXME/XXX debt markers found in any modified file.

### Human Verification Required

All 12 automated must-haves are verified. The following 10 items from Plan 04 Task 3 (checkpoint:human-verify, auto-approved during autonomous run) require browser verification against the seeded dev stack.

**Prereqs:** `docker compose down -v && docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py` (or equivalent); `pnpm -F @clubcore/admin-app dev` on http://localhost:5173; log in as owner.

#### 1. ProfileSection — full name edit and save (UAT-1, UAT-1b)

**Test:** Go to Settings → Профиль. Edit "Имя и фамилия". Click "Сохранить".
**Expected:** SaveBar appears with animated pulse dot while dirty; toast "Профиль обновлён" on save; SaveBar disappears; sidebar/header identity + avatar update to the new name without a full page reload.
**Why human:** SaveBar reactive state, toast visibility, and sidebar real-time identity refresh require browser rendering and cannot be verified headlessly.

#### 2. ProfileSection — email-taken inline error (UAT-2)

**Test:** Edit the email to an address already used by another seeded user. Click Save.
**Expected:** Inline "Email уже занят" error appears under the email input field; SaveBar remains visible.
**Why human:** Inline field error positioning inside the ProfileSection form requires browser rendering against a live DB with a second seeded user.

#### 3. ProfileSection — unique email save succeeds (UAT-2b)

**Test:** Correct the email to a unique address, click Save.
**Expected:** Success toast, SaveBar clears, identity updates.
**Why human:** Requires a seeded second-user precondition and browser observation of the transition.

#### 4. ProfileSection — cancel reverts field (UAT-3)

**Test:** Edit a field, then click "Отменить".
**Expected:** Field reverts to the last saved value; SaveBar disappears.
**Why human:** Cancel/revert behavior through the global SaveBar state machine requires browser interaction.

#### 5. SecuritySection — "Сменить пароль" opens modal (UAT-4)

**Test:** Go to Безопасность. Click "Сменить пароль".
**Expected:** ChangePasswordModal opens with title "Сменить пароль" and three password fields visible; 2FA toggle + static hint unchanged.
**Why human:** Modal open/close behavior and responsive layout (AdaptiveModal) require browser rendering.

#### 6. ChangePasswordModal — wrong current password inline error (UAT-4b)

**Test:** In the modal, enter a wrong current password + valid 12-char new password with matching confirm. Submit.
**Expected:** Inline "Неверный текущий пароль" on the current-password input; modal stays open.
**Why human:** Requires live backend round-trip (POST /api/v1/auth/change-password → 401) and inline error rendering inside the modal.

#### 7. ChangePasswordModal — successful password change + revoke-others-keeps-current (UAT-5)

**Test:** Enter the CORRECT current password + a new ≥12-char password with matching confirm. Submit.
**Expected:** Modal closes; toast "Пароль изменён. Другие сессии завершены."; active-sessions list count drops (other sessions revoked); THIS session stays logged in (no redirect to /login).
**Why human:** Session revocation visibility in the UI and "no self-lockout" require live backend + browser state observation.

#### 8. ChangePasswordModal — too-short new password disables submit (UAT-6)

**Test:** Enter a new password shorter than 12 characters.
**Expected:** Submit button is disabled (canSubmit=false); no submission possible.
**Why human:** Button disabled state requires browser rendering of the `canSubmit` computed value.

#### 9. ChangePasswordModal — confirm mismatch disables submit (UAT-6b)

**Test:** Enter mismatched new/confirm passwords.
**Expected:** Submit button disabled; if somehow triggered via keyboard, inline "Пароли не совпадают" on confirm field.
**Why human:** Confirm-mismatch gate and any resulting inline error require browser interaction.

#### 10. Theme client-only (not in PATCH body)

**Test:** Edit the profile and save. Capture the PATCH /api/v1/auth/me network request in DevTools.
**Expected:** Request body contains only the changed field(s) (`fullName` and/or `email`); no `theme` key present.
**Why human:** Confirming the absence of a field in a network request body requires browser DevTools network capture.

### Gaps Summary

No automated gaps. All 12 code-level must-haves are verified. Phase status is `human_needed` because 10 browser-UAT items (deferred from Plan 04 Task 3 autonomous run) require human verification against the seeded dev stack.

---

_Verified: 2026-06-14T23:05:00Z_
_Verifier: Claude (gsd-verifier)_
