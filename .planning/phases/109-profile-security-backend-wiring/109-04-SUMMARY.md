---
phase: 109-profile-security-backend-wiring
plan: 04
subsystem: settings-ui
tags: [react, typescript, tanstack-query, zod, modal, save-bar, profile, password]

# Dependency graph
requires:
  - phase: 109-03
    provides: useUpdateProfile + useChangePassword hooks + ProfileUpdateSchema + ChangePasswordSchema
provides:
  - Editable ProfileSection (SaveBar-integrated, PATCH /auth/me, inline email-taken error)
  - ChangePasswordModal (current/new/confirm, client validation, inline wrong-current-password)
  - SecuritySection "Сменить пароль" trigger wired to ChangePasswordModal
  - SettingsPage registers ProfileSection save/cancel alongside BranchSection
affects:
  - 109-05-verification (browser-UAT of live round-trips)
  - 111-openapi-handoff-milestone-gate

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BranchSection-style SaveBar integration: registerSave/registerCancel props + serverDataRef + markDirty(ID)"
    - "InviteModal-style AdaptiveModal form: useState + ChangePasswordSchema.safeParse + no react-hook-form (D-101-01-NOHOOKFORM)"
    - "Partial PATCH body: only changed fields sent to PATCH /auth/me (compared to serverDataRef.current)"
    - "ApiError.code === 'invalid_credentials' → inline 'Неверный текущий пароль' (T-109-19)"
    - "Avatar reads session.data.fullName (server) until authKeys.me invalidation completes (UI-SPEC)"

key-files:
  created:
    - apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx
  modified:
    - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
    - apps/admin-app/src/pages/settings/SettingsPage.tsx

key-decisions:
  - "D-109-04-PARTIAL-PATCH: ProfileSection handleSave compares form state to serverDataRef and sends only changed fields — avoids unnecessary full-body PATCH if only one field changed"
  - "D-109-04-INVALID-CREDS: wrong current password discriminated by err.code === 'invalid_credentials' (HTTP 401) — maps to inline 'Неверный текущий пароль' on currentPassword field (T-109-19 anti-oracle: no oracle beyond what backend already returns)"
  - "D-109-04-PROFILE-TOAST: section-specific toast 'Профиль обновлён' shown in ProfileSection.onSuccess — consistent with UI-SPEC section A which names it; SettingsPage also shows 'Настройки сохранены' aggregate if multiple sections saved"

requirements-completed: [PROF-01, PROF-02]

# Metrics
duration: 5min
completed: 2026-06-14
---

# Phase 109 Plan 04: Profile & Security UI Wiring Summary

**Editable ProfileSection (full_name + email) wired to PATCH /auth/me via the global SaveBar (BranchSection pattern), and new ChangePasswordModal (AdaptiveModal, current/new/confirm, useChangePassword) opened from SecuritySection — closes D-104-04-PROFILE-READONLY**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-14T19:15:25Z
- **Completed:** 2026-06-14T19:20:00Z
- **Tasks:** 2 code tasks (committed individually) + 1 checkpoint task (auto-approved, browser-UAT deferred)
- **Files modified:** 3 (2 modified + 1 created)

## Accomplishments

- Converted `ProfileSection` from read-only to inline-editable (full_name + email inputs) with the `BranchSection` SaveBar pattern — `registerSave`/`registerCancel` props, `serverDataRef`, `fieldErrors` state, `markDirty(ID_PROFILE)`
- `handleSave` sends only changed fields (partial PATCH), validates via `ProfileUpdateSchema.safeParse`, calls `useUpdateProfile`, shows "Профиль обновлён" toast on success; inline "Email уже занят" on 409 `err.fields.email`
- Avatar/Initials still reads `session.data.fullName` (server) until `authKeys.me` invalidation completes — per UI-SPEC: no premature display of dirty form value
- Created `ChangePasswordModal` mirroring `InviteModal` structure — `AdaptiveModal` with `IconChip(Lock, accent)`, three `type="password"` inputs (T-109-17), `ChangePasswordSchema.safeParse` + UI-only confirm-match check
- Submit disabled until all fields non-empty AND `newPassword.length >= 12` AND `newPassword === confirmPassword`
- Wrong current password (HTTP 401, `err.code === 'invalid_credentials'`) → inline "Неверный текущий пароль" on `currentPassword` field (modal stays open, T-109-19)
- Success → modal closes + toast "Пароль изменён. Другие сессии завершены." + `['auth','sessions']` invalidated by hook (sessions count drops in SecuritySection)
- Wired SecuritySection "Сменить пароль" `GhostBtn` to open the modal via `pwModalOpen` state; 2FA toggle + static hint unchanged (deferred per CONTEXT.md)
- `SettingsPage` now passes `registerSave('profile')` / `registerCancel('profile')` to `ProfileSection` — mirrors `BranchSection` registration
- Theme toggle row unchanged; theme NOT in the PATCH body (client-only per D-109-CONTEXT)
- No `react-hook-form` introduced (D-101-01-NOHOOKFORM strictly enforced)
- typecheck + lint + 350 tests (27 test files including router-smoke) all green

## Task Commits

1. **Task 1: ChangePasswordModal + SecuritySection trigger** — `0353b032`
2. **Task 2: Register ProfileSection in SettingsPage** — `14b24c75`

## Files Created/Modified

- `apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx` — New: AdaptiveModal with 3 password fields, client validation, useChangePassword wiring, inline field errors
- `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` — Converted ProfileSection to inline-editable; wired SecuritySection modal trigger; added ChangePasswordModal import + useState
- `apps/admin-app/src/pages/settings/SettingsPage.tsx` — Added registerSave/registerCancel props to ProfileSection mount

## Decisions Made

- **D-109-04-PARTIAL-PATCH:** ProfileSection `handleSave` compares the dirty form state against `serverDataRef.current` and sends only the changed fields to `PATCH /auth/me`. This avoids sending unchanged data and is consistent with the backend's partial-PATCH semantics (accepts `full_name?` / `email?` as optional).
- **D-109-04-INVALID-CREDS:** Wrong current password is discriminated by `err.code === 'invalid_credentials'` (the backend's `InvalidPassword` class maps to HTTP 401 with `code: "invalid_credentials"`). Mapped to the generic inline message "Неверный текущий пароль" per T-109-19 (no more specific oracle than the backend already provides).
- **D-109-04-PROFILE-TOAST:** Section-specific "Профиль обновлён" toast emitted in `ProfileSection.handleSave onSuccess`, consistent with UI-SPEC section A. The aggregate `SettingsPage` "Настройки сохранены" toast fires when multiple dirty sections are saved together (no conflict — both toasts are appropriate in different flows).

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Human Verification (browser-UAT)

Task 3 (checkpoint:human-verify) was auto-approved per autonomous checkpoint policy. The following 6 browser-UAT items require human verification against the seeded dev stack:

**Prereqs:** `docker compose down -v` + migrate + seed; `pnpm -F @clubcore/admin-app dev` on http://localhost:5173; log in as owner.

| # | Step | Expected Result |
|---|------|----------------|
| UAT-1 | Settings → Профиль → edit "Имя и фамилия" | SaveBar appears at bottom with animated pulse dot |
| UAT-1b | Click "Сохранить" | Toast "Профиль обновлён", SaveBar disappears, sidebar/header identity + avatar update to new name (no reload) |
| UAT-2 | Edit email to an ALREADY-USED address → Save | Inline "Email уже занят" under email field; SaveBar stays visible |
| UAT-2b | Fix to unique email → Save | Success: toast + SaveBar clears + identity updates |
| UAT-3 | Edit a field → click "Отменить" | Field reverts to saved value, SaveBar disappears |
| UAT-4 | Безопасность → "Сменить пароль" | Modal opens with title "Сменить пароль", 3 password fields visible |
| UAT-4b | Wrong current password + valid 12-char new (confirm matches) → submit | Inline "Неверный текущий пароль" on current-password input; modal stays open |
| UAT-5 | Correct current password + new ≥12-char (confirm matches) → submit | Modal closes; toast "Пароль изменён. Другие сессии завершены."; active-sessions count drops; THIS session stays logged in (no redirect to /login) |
| UAT-6 | New password < 12 chars → observe submit button | Submit button disabled (canSubmit=false); no submission possible |
| UAT-6b | New password ≠ confirm → observe submit button | Submit button disabled; if attempted via keyboard: inline "Пароли не совпадают" on confirm field |

## Known Stubs

None — no stubs exist in the components produced by this plan. ProfileSection reads real `useSession()` data; ChangePasswordModal calls real `useChangePassword()` mutation.

## Threat Surface Scan

No new network endpoints introduced. Both ProfileSection and ChangePasswordModal use existing hooks from Plan 03 (`useUpdateProfile`, `useChangePassword`) which attach CSRF via `staffRequest`.

| Threat | Status |
|--------|--------|
| T-109-17: password field masking | All three ChangePasswordModal inputs are `type="password"`; fields reset on modal close via setTimeout pattern |
| T-109-19: wrong-current-password anti-oracle | Generic inline message "Неверный текущий пароль" — no additional info beyond backend response |
| T-109-21: stale sidebar identity | useUpdateProfile invalidates authKeys.me on success; sidebar refreshes from fresh /auth/me fetch |
| T-109-SC: no new packages | No new npm packages — all primitives (AdaptiveModal/ModalButton/IconChip/SaveBar) already existed |

## Self-Check: PASSED

Files exist:
- `apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx` — created ✓
- `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` — modified ✓
- `apps/admin-app/src/pages/settings/SettingsPage.tsx` — modified ✓

Commits exist: `0353b032`, `14b24c75` ✓

Tests: 350/350 passed (27 test files) ✓
Typecheck: clean ✓
Lint: clean ✓
