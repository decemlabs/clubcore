---
phase: 109-profile-security-backend-wiring
reviewed: 2026-06-14T12:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - apps/backend/app/modules/auth/service.py
  - apps/backend/app/modules/auth/router.py
  - apps/backend/app/modules/auth/schemas.py
  - apps/backend/app/core/audit.py
  - apps/admin-app/src/features/auth/api.ts
  - apps/admin-app/src/features/auth/schemas.ts
  - apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx
  - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
  - apps/admin-app/src/pages/settings/SettingsPage.tsx
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 109: Code Review Report

**Reviewed:** 2026-06-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 109 delivers PATCH /api/v1/auth/me (profile edit, PROF-01) and POST /api/v1/auth/change-password (self-service password change, PROF-02) plus the frontend wiring in SettingsPage/SectionsTop/ChangePasswordModal.

The session-revocation logic in `change_password` is architecturally correct: it revokes all OTHER families while keeping the current one alive, resolved via `sha256(cc_refresh) → RefreshToken.family_id`. The CSRF/auth ordering (RBAC-04) is correct on both new endpoints. The audit payload carries only changed-field name markers and no raw values. The ChangePasswordModal correctly maps `invalid_credentials` to an inline field error.

One BLOCKER was found: `update_profile` stores the email exactly as received from Pydantic `EmailStr` without lowercasing, while `authenticate()` always does `.lower()` on the submitted email before querying `User.email`. A user who updates their email to a mixed-case address (e.g., `Alice@Example.com`) can no longer log in because the login lookup searches for `alice@example.com` and finds no match.

Three warnings: (1) the nil-UUID self-lockout fallback in `change_password_endpoint` silently revokes the caller's own session when `cc_refresh` cannot be resolved, with no 4xx or log escalation; (2) the `IntegrityError` catch in `update_profile` is over-broad and will misreport non-email constraint violations as `email_already_in_use`; (3) the confirm-match safeguard in `ChangePasswordModal.handleSubmit` (lines 91-93) is dead code that can never be reached.

---

## Critical Issues

### CR-01: Email not lowercased before storage in `update_profile` — breaks subsequent login

**File:** `apps/backend/app/modules/auth/service.py:1261`

**Issue:** `update_profile` assigns `user.email = email` directly, where `email` is the value from `ProfileUpdateRequest.email` — a Pydantic `EmailStr`. `email-validator 2.x` normalizes the **domain** to lowercase but preserves the **local part** case (e.g., `Alice@example.com` stays `Alice@example.com`). However, `authenticate()` (line 133) always does `email_lower = email.lower()` before the SQL lookup `User.email == email_lower`. After a staff member updates their email to any mixed-case address, the login query will never match the stored value and the account is effectively locked out. The partial-UNIQUE index is defined on `lower(email)` (migration 0022), so the index correctly prevents duplicate case-insensitive emails — but the stored column value itself is never normalised at write time.

**Fix:**
```python
# service.py update_profile — normalise before assignment
if email is not None:
    user.email = email.lower()
    changed_fields.append("email")
```

---

## Warnings

### WR-01: Silent self-lockout when `cc_refresh` cookie cannot be resolved in `change_password_endpoint`

**File:** `apps/backend/app/modules/auth/router.py:370-384`

**Issue:** When the `cc_refresh` cookie is absent **or** the hash is not found in the database (legitimate scenario: token was rotated between the access-token validation and the subsequent `SELECT` here), `effective_family_id` falls back to `UUID(int=0)`. The exclusion predicate in `revoke_other_sessions_on_password_change` is `RefreshToken.family_id != UUID(int=0)`, which matches **every** real family. All sessions — including the caller's — are revoked. The password change succeeds (204 returned), the user receives the success toast, but their access token expires 15 minutes later and the subsequent `/refresh` call fails because the family is gone. The user is silently logged out with no indication it happened.

The router docstring calls this "extremely unlikely," which is true but understates the consequence. The gap is the missing warning log entry and the absence of any FE handling for the degraded case.

**Fix:** Emit a structured log warning when the fallback fires, so operators can observe it. Optionally, return a custom response header (e.g., `X-Session-Revoke-All: true`) so the frontend can immediately redirect to `/login` instead of leaving the user in a confused state:

```python
# router.py change_password_endpoint — warn on fallback
if current_family_id is None:
    _log.warning(
        "change_password.family_id_unresolved",
        user_id=str(user.id),
        note="cc_refresh cookie absent or hash not found; all sessions will be revoked",
    )
effective_family_id: UUID = (
    current_family_id if current_family_id is not None else UUID(int=0)
)
```

### WR-02: Over-broad `IntegrityError` catch in `update_profile` misreports non-email constraint violations

**File:** `apps/backend/app/modules/auth/service.py:1264-1271`

**Issue:** The `except IntegrityError` block at line 1266 catches **any** `IntegrityError` raised by `session.flush()` and re-raises it as `ConflictError("email_already_in_use", fields={"email": ...})`. The `session.flush()` call flushes the entire pending unit-of-work for the session, not just the two fields being written here. If another part of the same request's UoW (unlikely in this narrow flow, but structurally fragile) raises an `IntegrityError` on a different constraint, the caller receives a misleading 409 with `fields.email` set — which could confuse the frontend into displaying an incorrect "Email already taken" error when the real problem is something else entirely. It also silences the original `IntegrityError` in the error chain beyond the `from exc` context.

The call to `session.rollback()` before the re-raise (line 1267) is correct per Pitfall 2 discipline; the issue is only the over-broad catch scope.

**Fix:** Narrow the catch to email-specific violations by inspecting the constraint name:

```python
from sqlalchemy.exc import IntegrityError

try:
    await session.flush()
except IntegrityError as exc:
    await session.rollback()
    # Only re-map email-unique violations; let others propagate.
    orig = str(exc.orig) if exc.orig else ""
    if "uq_users_email_active" in orig or "ix_users_email_lower_unique" in orig:
        raise ConflictError(
            "email_already_in_use",
            fields={"email": "Этот адрес уже используется"},
        ) from exc
    raise  # unexpected DB constraint — propagate as 500
```

(Verify the exact constraint name against migration 0022.)

### WR-03: Dead confirm-match guard in `ChangePasswordModal.handleSubmit` is unreachable code

**File:** `apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx:90-94`

**Issue:** The `canSubmit` computation (lines 65-69) already requires `form.newPassword === form.confirmPassword`. `handleSubmit` returns immediately at line 72 if `!canSubmit`. The `ChangePasswordSchema.safeParse` at line 75 validates only `currentPassword` and `newPassword` (not `confirmPassword`) and can only fail if those fields violate their respective `min_length` constraints — both of which are also checked by `canSubmit`. Therefore the code path at lines 91-93:

```ts
if (form.newPassword !== form.confirmPassword) {
  setFieldErrors({ confirmPassword: 'Пароли не совпадают' })
  return
}
```

is dead code: it can never be reached. If a developer later weakens the `canSubmit` guard (e.g., to allow partial pre-submission feedback), they may unknowingly rely on this check being meaningful, when in fact it was never tested because it was never reachable.

**Fix:** Remove lines 90-94. The only live confirm-match gate is already `canSubmit`. If a future change needs runtime confirm-match feedback before the user meets the 12-char floor, restructure the validation to run before the `canSubmit` gate.

---

## Info

### IN-01: `ProfileSection.handleSave` sends validated full-form data but mutates with partial delta — subtle API contract gap

**File:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx:141-161`

**Issue:** `handleSave` builds `body` as only the changed fields (lines 143-145), then runs `ProfileUpdateSchema.safeParse` on the **full** form state (line 148), and finally passes the partial `body` to `updateProfile.mutate` (line 161) — not `result.data`. This is intentional and correct for partial PATCH, but `result.data` is computed and then discarded, which is a code smell: the validated object and the object actually sent diverge silently. If `ProfileUpdateSchema` is ever extended (e.g., a new field added to the schema), `result.data` would include the new field but `body` might not — leading to a confusing gap where schema-level validation passes but the field is never sent.

**Fix:** For clarity, derive the partial body after validation succeeds, using the validated data as the source of truth:

```ts
const result = ProfileUpdateSchema.safeParse({ fullName: form.fullName, email: form.email })
if (!result.success) { /* ... */ }

// Build partial body from validated result — consistent with the schema
const body: Partial<ProfileUpdate> = {}
if (!current || result.data.fullName !== current.fullName) body.fullName = result.data.fullName
if (!current || result.data.email !== current.email) body.email = result.data.email

updateProfile.mutate(body, { /* ... */ })
```

### IN-02: `SecuritySection` hardcodes "Последняя смена — 47 дней назад" as static text

**File:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx:361-363`

**Issue:** The `SettingRow` hint for the password row reads: `"Последняя смена — 47 дней назад. Рекомендуем менять каждые 90 дней."` This is static placeholder text. A user who changed their password via the new `POST /change-password` endpoint will still see "47 дней ago" regardless of when the change actually occurred. The backend `MeResponse` does not currently expose a `password_last_changed_at` field, so this cannot be dynamically populated without a schema extension.

No immediate bug, but it is confusing UX and a misleading security indicator. This is a known gap to close in a future phase.

**Fix (deferred):** Add `password_changed_at: datetime | None` to the `User` model and `MeResponse` schema, update it in `change_password`, expose it in the `/me` endpoint, and replace the hardcoded hint with `formatRelativeRu(session.data.passwordChangedAt)`.

---

_Reviewed: 2026-06-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
