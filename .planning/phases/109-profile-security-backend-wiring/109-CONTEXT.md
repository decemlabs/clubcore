# Phase 109: Profile & Security — Backend + Wiring - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous)

<domain>
## Phase Boundary

A staff member can edit their own profile (full name, email, theme) and change their own password from Settings, on real new endpoints, with the existing session-revocation discipline. Closes the v3.0 `D-104-04-PROFILE-READONLY` gap.

Two feature requirements: PROF-01 (`PATCH /api/v1/auth/me` — edit own full_name/email; theme stays client-side) and PROF-02 (self password-change: current+new, 12-char NIST policy, revokes OTHER sessions while keeping the current one alive).

**In scope:** new `PATCH /api/v1/auth/me`, new `POST /api/v1/auth/change-password`, FE wiring of ProfileSection (editable) + SecuritySection (password-change modal), one new LOCKED audit event (`profile_updated`), reuse of the existing `password_changed_revokes_sessions` audit event + refresh-family-revoke machinery.

**Out of scope (deferred):** server-side theme persistence (theme remains client-only uiPrefs), email re-verification flow, 2FA, password complexity rules beyond the existing 12-char floor.
</domain>

<decisions>
## Implementation Decisions

### Profile editing (PROF-01)
- **Theme stays client-only.** `PATCH /api/v1/auth/me` handles `{full_name, email}` only. The existing localStorage/uiPrefs theme toggle in ProfileSection satisfies the "theme" part of the profile UI — NO `User.theme` column, NO migration, theme does not sync across devices.
- **Email change:** validate uniqueness (the existing partial-UNIQUE on `lower(email)` + soft-delete); return a 409/422 field error if the email belongs to another user. **No email re-verification** (staff-managed, single club).
- **Identity refresh:** after a successful profile save, invalidate the `authKeys.me` (`['auth','me']`) query so the sidebar/header identity reflects the new full_name immediately (no full reload).
- **Audit:** register a new `profile_updated` LOCKED audit event (resource `user`) in `audit.py` BEFORE the emit callsite (INFRA-15).

### Password change (PROF-02)
- **Revoke OTHER sessions, keep current alive** (success criterion #4). Add a revoke variant that revokes all alive refresh families for the user EXCEPT the current one (identified from the `cc_refresh` cookie / current family). The current device stays logged in.
- **Endpoint:** `POST /api/v1/auth/change-password`, body `{currentPassword, newPassword}`, `verify_csrf`-protected, returns `204 No Content` on success.
- **New-password policy:** reuse the existing **12-char NIST floor** (`min_length=12`, no complexity/rotation) — same validator as login/reset (`auth/schemas.py`).
- **Current session token:** kept valid (NOT rotated) — no re-login on the device that changed the password.
- **Audit:** reuse the already-locked `password_changed_revokes_sessions` event (emit before commit).
- **Current-password verification:** a wrong current password surfaces as a clear field error (timing-equivalent verification, same as login).

### Frontend UX
- **Password-change UI:** a modal (current + new + confirm), mirroring the existing `InviteModal` pattern in SectionsBottom.tsx. Submit calls `useChangePassword()`.
- **Profile edit UI:** ProfileSection becomes inline-editable (full_name + email fields) integrated with the existing global SaveBar (registerSave/registerCancel), mirroring BranchSection.
- **Wrong current password:** inline field error on the current-password input ("Неверный текущий пароль"), mapped from the backend 422/400 response.
- **After password change:** success toast + refetch the sessions list (so the reduced session count is visible).

### RBAC (no change)
- PROF endpoints are **self-service** — gated by authentication only (`require_authenticated()`), NOT by a `Resource` permission. NO change to `permissions.py` / `can.ts` OWNER_ONLY (parity test stays at 42 entries).

### Claude's Discretion
- Exact service-function names, the precise SQL for "revoke all families except current", and whether the current family is passed into the service from the cookie or resolved inside — at plan-phase discretion, following the existing `revoke_session`/`revoke_all_sessions` patterns in `auth/service.py`.
- Password-change endpoint verb (`POST` vs `PATCH`) and exact path — `POST /api/v1/auth/change-password` recommended; finalize at plan-phase.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`GET /api/v1/auth/me`:** `apps/backend/app/modules/auth/router.py:245-265` returns `MeResponse {id, role, full_name, email, has_telegram}` (read-only — the gap to close).
- **User model:** `apps/backend/app/core/models.py:35-116` — `email` (partial UNIQUE on `lower(email)`, soft-delete aware via migration 0022), `password_hash` (nullable since Phase 43), `full_name`, `role`, `status`. **No `theme` column** (theme is client-only).
- **Auth dependency:** `apps/backend/app/core/dependencies.py` — `require_authenticated()` factory + `CurrentUser` protocol (id + role).
- **Password hashing/policy:** `apps/backend/app/core/security.py` (`hash_password` Argon2id, `verify_password` raises `InvalidPassword`); 12-char floor at `auth/schemas.py:25-30` (`LoginRequest` min_length=12).
- **Session revoke machinery:** `auth/service.py:335-360` `revoke_sessions_on_password_change()` (currently revokes ALL — needs an exclude-current variant), `:577-641` `revoke_session()` (single family by token hash), `revoke_all_sessions()`, `:205-227` self-revoke detection (family == current cc_refresh → clear cookies). `RefreshToken` ORM at `auth/models.py:56-94` (family_id, revoked_at, replaced_by_id).
- **Password reset (Phase 44) exemplar:** `auth/password_reset_service.py:128-160` `confirm_password_reset()` = hash + revoke-all + atomic — the closest pattern for the change-password service.
- **Existing sessions UI:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx:180-342` `SecuritySection()` (lists sessions, `POST /api/v1/auth/sessions/{family_id}/revoke`, "Выйти везде" via `revokeCurrentSession`). `ProfileSection()` at `:97-168` (read-only, reads `useSession()`).
- **Audit:** `apps/backend/app/core/audit.py` LOCKED_AUDIT_EVENTS — `password_changed_revokes_sessions` ✓ (already locked), `session_revoked` ✓; `profile_updated` MISSING (register it).

### Established Patterns
- **FE mutation:** `features/auth/api.ts` (`useSession()` key `['auth','me']`), `staffRequest` + zod seam + TanStack Query mutation + invalidate. `useRevokeSession`/`useRevokeCurrentSession` already exist.
- **Settings form:** BranchSection (`SectionsTop.tsx:451-756`) registerSave/registerCancel + SaveBar (mirror for ProfileSection). `InviteModal` (`SectionsBottom.tsx:570-753`) — modal form + validation + submit + toast (mirror for password-change modal).
- **CSRF:** `verify_csrf` declared on mutating endpoints (e.g. `POST /auth/logout` router.py:136, `POST /auth/sessions/{id}/revoke` :194) — new PATCH/POST MUST declare it.

### Integration Points
- New routes register in the auth router (already mounted under `/api/v1/auth`).
- `profile_updated` → `audit.py` LOCKED_AUDIT_EVENTS + emit before commit.
- Contract is additive (NOT byte-stable) — OpenAPI regen + `_v31Checks` forward-guard happen in **Phase 111**, not here.
- Both endpoints self-contain; PROF-01 and PROF-02 can be built in parallel (no ordering dependency).
</code_context>

<specifics>
## Specific Ideas

- `PATCH /api/v1/auth/me` body: `{full_name?, email?}` (camelCase wire); response echoes `MeResponse`.
- `POST /api/v1/auth/change-password` body: `{currentPassword, newPassword}`; `204` on success; wrong current → field error.
- Revoke-others must keep the current refresh family alive (resolve current family from `cc_refresh`).
- Cookie discipline: `cc_access`/`cc_refresh` + `clubcore_csrf` → `X-CSRF-Token`.
- Reuse the 12-char NIST password floor; Argon2id hashing.
</specifics>

<deferred>
## Deferred Ideas

- Server-side theme persistence (User.theme column + cross-device sync) — theme stays client-only this phase.
- Email re-verification on change.
- 2FA (the SecuritySection 2FA toggle remains a mock/hidden-for-future).
- Password complexity rules / rotation / lockout beyond the existing 12-char floor.
</deferred>
