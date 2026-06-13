---
phase: 104-dashboard-reports-settings
plan: "05"
subsystem: ui
tags: [react, tanstack-query, zod, settings, users, rbac]

requires:
  - phase: 104-04
    provides: SettingsPage.tsx with Profile/Security self-fetching; useMockSettingsData compat bridge
  - phase: 100-foundation-auth
    provides: useSession (current user id/role for self-detection), staffRequest + ApiError

provides:
  - UserSchema + UsersListResponseSchema + UserInviteResponseSchema (features/users/schemas.ts)
  - usersKeys factory (all/lists/list/detail)
  - useUsers (GET /api/v1/users, owner-gated via enabled:can(role,'list','users'))
  - useInviteUser (POST /users?includeInviteLink=true, parses UserInviteResponseSchema)
  - useDeactivateUser / useReactivateUser / useDeleteUser / useRevokeInvitation
  - Wired TeamSection: real list + invite modal (copy-link) + row actions + 409 guards
  - Lock-EmptyState for reception inside TeamSection body (zero users calls)

affects:
  - 104 final gate (last plan of phase)

tech-stack:
  added: []
  patterns:
    - "Owner-gated query: useUsers enabled:can(role,'list','users') — reception fires zero calls"
    - "Invite modal success view: swap modal body to CheckCircle2 + monospace link input + clipboard copy"
    - "UserRowActions: DropdownMenu per user.status with confirm dialogs + 409 toast mapping"
    - "Self-row detection: user.id === currentUserId → show «Это вы» disabled span, no actions"
    - "InviteState union type: form phase | success phase — drives modal body swap"

key-files:
  created:
    - apps/admin-app/src/features/users/schemas.ts
    - apps/admin-app/src/features/users/api.ts
  modified:
    - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
    - apps/admin-app/src/pages/settings/SettingsPage.tsx

key-decisions:
  - "D-104-05-ROLE-TONE: ROLE_TONE map updated from mock Role type (owner/admin/trainer/cashier)
    to real API roles (owner/reception); removed mock features/settings/types Role import"
  - "D-104-05-TEAM-COLS: Simplified TEAM_COLS grid (removed branch/2FA/last-login columns that
    were mock-era fields not present in GET /api/v1/users response; kept Сотрудник/Роль/Статус/Actions)"
  - "D-104-05-INVITE-STATE: Used discriminated union InviteState instead of separate useState
    booleans for form/success phases — cleaner reset on re-open"
  - "D-104-05-TOKEN-ID: For pending_invitation rows, useRevokeInvitation receives user.id as
    tokenId — backend treats it as the invitation token reference per PATTERNS §revoke-invitation"

patterns-established:
  - "Self-fetching TeamSection: reads role+id from useSession(), calls useUsers() conditionally"
  - "Invite success view: replaces modal body in-place without closing/reopening modal"
  - "409 guard via handle409(err): extracted helper function maps ApiError.code to Russian toasts"

requirements-completed: [SET-02]

duration: 4min
completed: "2026-06-13"
---

# Phase 104 Plan 05: Users Admin (TeamSection) Summary

**Owner-only Users admin wired in Settings→Team: real list (GET /api/v1/users), invite with copy-link (POST /users?includeInviteLink), deactivate/reactivate/delete/revoke-invitation with confirm dialogs and 409 guard toasts; reception sees Lock-EmptyState with zero API calls.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-13T19:43:11Z
- **Completed:** 2026-06-13T19:47:00Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Created `features/users/schemas.ts`: `UserSchema` (id, email, fullName, role enum, status enum), `UsersListResponseSchema` (paginated envelope), `UserInviteResponseSchema` (optional inviteLinkUrl + invitationExpiresAt), `UserInviteInput` + `UsersFilter` types
- Created `features/users/api.ts`: `usersKeys` factory; `useUsers` owner-gated (enabled:can(role,'list','users')); `useInviteUser` (POST ?includeInviteLink=true, parses schema from .data); `useDeactivateUser`, `useReactivateUser`, `useDeleteUser`, `useRevokeInvitation` — all with `onSettled` invalidation; CSRF auto via staffRequest; `ApiError` re-exported
- Rewrote `TeamSection` in SectionsBottom.tsx: reception sees Lock-EmptyState inside body with ZERO users API calls (T-104-12 mitigated); owner sees real list with role badges (Владелец/Ресепшн) and status badges (Ожидает/Неактивен); loading 3 skeleton rows; error inline with retry; empty EmptyState with icon=Users
- `InviteModal`: AdaptiveModal with form (Имя и фамилия min 2, Email valid email, Роль RadioGroup default Ресепшн); on submit calls useInviteUser; on success swaps modal body to success view (CheckCircle2 + email notice + read-only monospace link input with select-all + «Копировать ссылку» → navigator.clipboard + toast + expiry date)
- `UserRowActions`: DropdownMenu per status — active+not-self: Деактивировать/Удалить; active+self: «Это вы» disabled span; pending_invitation: Отозвать приглашение; deactivated: Восстановить/Удалить; each behind confirm dialog; `handle409` maps err.code to Russian toasts
- `SettingsPage.tsx`: TeamSection is now propless (self-fetching); removed `data` prop from TeamSection call
- ROLE_TONE and ROLE_LABEL updated to real API roles (owner/reception); removed mock Role type import

## Task Commits

1. **Task 1: features/users domain — schemas + CRUD hooks** - `6ab77bb2` (feat)
2. **Task 2: Wire TeamSection — list, invite modal, row actions, 409 guards** - `633b3a3f` (feat)

## Files Created/Modified

- `apps/admin-app/src/features/users/schemas.ts` — Created: UserSchema + UsersListResponseSchema + UserInviteResponseSchema + input/filter types
- `apps/admin-app/src/features/users/api.ts` — Created: usersKeys + useUsers + useInviteUser + useDeactivateUser + useReactivateUser + useDeleteUser + useRevokeInvitation + ApiError re-export
- `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` — Rewrote TeamSection (self-fetching, wired); added InviteModal + UserRowActions; updated ROLE_TONE/ROLE_LABEL; added all new imports
- `apps/admin-app/src/pages/settings/SettingsPage.tsx` — Removed `data` prop from TeamSection (propless)

## Decisions Made

- **D-104-05-ROLE-TONE**: ROLE_TONE updated from mock role types (owner/admin/trainer/cashier) to API role types (owner/reception). Mock Role import from features/settings/types removed.
- **D-104-05-TEAM-COLS**: Simplified grid columns to Сотрудник/Роль/Статус/Actions — removed branch/2FA/last-login columns since GET /api/v1/users does not provide those fields.
- **D-104-05-INVITE-STATE**: Discriminated union `InviteState = form | success` used instead of separate flags; resets cleanly after modal close delay.
- **D-104-05-TOKEN-ID**: `useRevokeInvitation` receives `user.id` as token ID for pending_invitation rows — this is the identifier the backend uses for invitation revocation.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written. All TypeScript types, hook patterns, and UI-SPEC copy matched without compilation errors.

---

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

None.

## Known Stubs

None — TeamSection reads live data from `useUsers()` (GET /api/v1/users). Invite, deactivate, reactivate, delete, and revoke-invitation all call real endpoints. No mock data in this plan.

## Threat Flags

No new security-relevant surface introduced beyond what the plan's threat model covers.

| Threat Mitigated | File | Description |
|-----------------|------|-------------|
| T-104-12 (Elevation) | SectionsBottom.tsx | `!can(role,'list','users')` → Lock-EmptyState early-return; useUsers `enabled:false` for reception |
| T-104-13 (CSRF) | api.ts | All mutations use staffRequest (auto CSRF); each action behind confirm modal |
| T-104-14 (Info Disclosure) | SectionsBottom.tsx | inviteLinkUrl shown ONLY in success modal; not logged, not toasted |
| T-104-15 (DoS/lockout) | SectionsBottom.tsx | isSelf check → «Это вы» disabled; 409 guards surfaced as toasts |

## Self-Check

- [x] `features/users/schemas.ts` created with `UsersListResponseSchema`
- [x] `features/users/api.ts` has `useUsers`, `useInviteUser`, `useDeactivateUser`, `useReactivateUser`, `useDeleteUser`, `useRevokeInvitation`, `export { ApiError }`
- [x] `SectionsBottom.tsx` has `useUsers`, `can(role, 'list', 'users')`, `cannot_deactivate_last_owner`, `Это вы`
- [x] `SettingsPage.tsx` flipped: `<TeamSection />` (propless)
- [x] Commits `6ab77bb2` and `633b3a3f` exist in git log
- [x] Full gate green: typecheck + lint + 337 tests + build

## Self-Check: PASSED

---
*Phase: 104-dashboard-reports-settings*
*Completed: 2026-06-13*
