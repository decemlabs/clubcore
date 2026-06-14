---
phase: 109-profile-security-backend-wiring
fixed_at: 2026-06-14T22:35:00Z
review_path: .planning/phases/109-profile-security-backend-wiring/109-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 109: Code Review Fix Report

**Fixed at:** 2026-06-14T22:35:00Z
**Source review:** .planning/phases/109-profile-security-backend-wiring/109-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, IN-01)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Email not lowercased before storage in `update_profile`

**Files modified:** `apps/backend/app/modules/auth/service.py`, `apps/backend/tests/integration/auth/test_profile_update.py`
**Commit:** b811caac
**Applied fix:** In `update_profile`, changed `user.email = email` to `user.email = email.lower()` with a comment explaining the normalization requirement. Added integration test `test_patch_me_mixed_case_email_stored_lowercase_login_succeeds` (Test 8) that sends a mixed-case email (`MixedCase-xxx@Example.COM`), asserts the stored value and API response echo the lowercased form, and confirms login with the canonical lowercase email still succeeds.

---

### WR-01: Silent self-lockout when `cc_refresh` cookie cannot be resolved

**Files modified:** `apps/backend/app/modules/auth/router.py`
**Commit:** bb83684e
**Applied fix:** Added `import structlog` and a module-level `_log = structlog.get_logger(__name__)` to `router.py`. In `change_password_endpoint`, inserted an `if current_family_id is None:` guard that calls `_log.warning("change_password.family_id_unresolved", user_id=..., note=...)` with an explanatory note that all sessions including the caller's will be revoked. The fallback nil-UUID behaviour is preserved; the change makes the degraded path observable in structured logs.

---

### WR-02: Over-broad `IntegrityError` catch in `update_profile`

**Files modified:** `apps/backend/app/modules/auth/service.py`
**Commit:** 5d578add
**Applied fix:** Narrowed the `except IntegrityError` block to inspect `str(exc.orig)` for the known constraint name `uq_users_email_active` (from migration 0022). Only violations matching that constraint are remapped to `ConflictError("email_already_in_use", ...)`. Any other `IntegrityError` is re-raised bare with `raise` so it surfaces as a 500 with a correct diagnostic instead of a misleading `409 email_already_in_use`.

---

### WR-03: Dead confirm-match guard in `ChangePasswordModal.handleSubmit`

**Files modified:** `apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx`
**Commit:** 03688937
**Applied fix:** Removed the unreachable `if (form.newPassword !== form.confirmPassword)` block (lines 90-94 in the original). The `canSubmit` gate at line 65-69 already enforces `newPassword === confirmPassword` before `handleSubmit` can proceed; the block could never be reached. The surrounding `setFieldErrors({})` and `setForm` calls below were preserved unchanged.

---

### IN-01: `ProfileSection.handleSave` sends pre-validation values instead of validated result

**Files modified:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx`
**Commit:** a535b7d0
**Applied fix:** Restructured `handleSave` to run `ProfileUpdateSchema.safeParse` first, then derive the partial delta body from `result.data` (rather than building `body` from raw `form` state before validation and discarding `result.data`). The behaviour is identical today (same two fields), but future schema extensions will be automatically included in what is sent to the mutation rather than silently dropped.

---

## Verification Results

**Backend:**
- `uv run ruff check app/modules/auth/service.py app/modules/auth/router.py` — All checks passed
- `uv run mypy app/modules/auth/service.py app/modules/auth/router.py` — Success: no issues found in 2 source files
- `uv run lint-imports` — Contracts: 3 kept, 0 broken
- `uv run pytest tests/integration/auth/test_profile_update.py tests/integration/auth/test_change_password.py -q` — 15 passed in 5.14s (includes new Test 8 for CR-01)

**Frontend:**
- `pnpm -F @clubcore/admin-app typecheck` — Pass (tsc -b --noEmit, no errors)
- `pnpm -F @clubcore/admin-app lint` — Pass (ESLint, no errors)
- `vitest run src/features/auth` — 27 passed (schemas.test.ts + api.test.ts)

**Skipped (IN-02):** `SecuritySection` hardcoded password-last-changed hint requires a new backend field (`password_changed_at`) on the `User` model and `MeResponse` schema — deferred per scope instructions.

---

_Fixed: 2026-06-14T22:35:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
