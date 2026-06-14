---
phase: 109
slug: profile-security-backend-wiring
audited: 2026-06-14
baseline: 109-UI-SPEC.md (approved design contract)
screenshots: not captured (code-only audit; no dev server verified)
---

# Phase 109 — UI Review

**Audited:** 2026-06-14
**Baseline:** 109-UI-SPEC.md — WIRING phase, interaction/state contracts only; inherited design system
**Screenshots:** not captured (code-only audit)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All contract strings present; one label token mismatch (`text-fg-muted` vs spec `text-fg-subtle`) affects field labels |
| 2. Visuals | 3/4 | Spec-required icon (`Building2`) used for ProfileSection card instead of a person/profile icon; avatar seeded with live `session.data.fullName` correctly deferred; modal mirrors InviteModal pattern |
| 3. Color | 4/4 | All accents on spec-declared elements; semantic tokens throughout; zero raw palette values in Phase 109 additions |
| 4. Typography | 3/4 | Modal field labels use `text-[12px]` vs spec's `text-[12.5px] font-semibold text-fg-subtle`; minor drift acceptable in a wiring phase |
| 5. Spacing | 3/4 | `mb-3.5` (14px) between modal field groups is non-standard (not in 8-point scale); `mb-1` on last confirm group is asymmetric vs prior groups |
| 6. Experience Design | 3/4 | All 7 ProfileSection states and 6 modal states implemented; one gap: modal "Cancel" button not disabled during submission (spec requires disabled) |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **Modal cancel button not disabled during submission** (`ChangePasswordModal.tsx:124`) — user can click "Отмена" while a submission is in-flight, resetting state and losing the pending request's error response; spec requires `disabled={form.submitting}` on the ghost button — add `disabled={form.submitting}` to `ModalButton variant="ghost"`.

2. **ProfileSection uses `Building2` icon** (`SectionsTop.tsx:206`) — the ProfileSection `SectionCard` passes `icon={Building2}` (a building/office icon) which is semantically wrong for a personal profile card; `Building2` is already the icon for BranchSection; spec does not mandate the exact icon but inheriting BranchSection's icon creates visual duplication and wrong semantic signal — replace with `User` or `UserCircle` from Lucide.

3. **Sessions invalidation key mismatch** (`api.ts:179`) — `useChangePassword` invalidates `['auth', 'sessions']` but `useSessions` in `features/settings/api.ts` likely registers under `settingsKeys.sessions` (e.g. `['settings', 'sessions']`); if the keys differ the session count in SecuritySection will NOT update after password change (silent failure of the post-submit behaviour contract) — verify the sessions query key matches `useChangePassword`'s invalidation target.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

All copywriting contract strings are correctly implemented:

- ProfileSection desc: "Личные данные. Имя и email можно изменить." — PASS (`SectionsTop.tsx:209`)
- `full_name` placeholder: "Имя и фамилия" — PASS (`SectionsTop.tsx:260`)
- `email` placeholder: "email@example.com" — PASS (`SectionsTop.tsx:276`)
- Inline error "Email уже занят" — PASS (`SectionsTop.tsx:178`)
- Load error: "Не удалось загрузить профиль." + "Повторить" — PASS (`SectionsTop.tsx:221-228`)
- Toast "Профиль обновлён" — PASS (`SectionsTop.tsx:168`)
- Toast "Не удалось сохранить. Попробуйте ещё раз." — PASS (`SectionsTop.tsx:183`)
- Modal title "Сменить пароль" — PASS (`ChangePasswordModal.tsx:119`)
- Modal description — PASS (`ChangePasswordModal.tsx:121`)
- Current password placeholder "Текущий пароль" — PASS (`ChangePasswordModal.tsx:143`)
- New password placeholder "Новый пароль (не менее 12 символов)" — PASS (`ChangePasswordModal.tsx:163`)
- Confirm placeholder "Повторите новый пароль" — PASS (`ChangePasswordModal.tsx:183`)
- Modal primary CTA "Сменить пароль" / "Сохраняем…" — PASS (`ChangePasswordModal.tsx:132-133`)
- Modal cancel "Отмена" — PASS (`ChangePasswordModal.tsx:124`)
- Inline error "Неверный текущий пароль" — PASS (`ChangePasswordModal.tsx:107`)
- Inline error "Пароль должен содержать не менее 12 символов" — PASS (propagated from `ChangePasswordSchema` in `schemas.ts:30` via `ChangePasswordModal.tsx:83`)
- Toast "Пароль изменён. Другие сессии завершены." — PASS (`ChangePasswordModal.tsx:96`)
- Toast "Не удалось изменить пароль. Попробуйте ещё раз." — PASS (`ChangePasswordModal.tsx:109`)

**WARNING:** Inline error for confirm-mismatch ("Пароли не совпадают") is NEVER shown. The `canSubmit` guard silently prevents submission when `newPassword !== confirmPassword` but no inline error text is rendered below the confirm field to explain why. The spec explicitly declares this as a visible client-side error state (`ChangePasswordModal.tsx:191-195` — `fieldErrors.confirmPassword` render path exists but `setFieldErrors({ confirmPassword: ... })` is never called on mismatch). Score kept at 3 rather than 2 because the string exists in the spec but the trigger is absent rather than the string itself being wrong.

### Pillar 2: Visuals (3/4)

**WARNING — ProfileSection icon:** `SectionCard id="profile"` receives `icon={Building2}` (`SectionsTop.tsx:206`). `Building2` is a building/headquarters icon and is already used for `BranchSection` (line 679). A personal profile card should use a person-type icon. This creates visual duplication across two adjacent cards in the settings list.

**PASS — modal structure:** `ChangePasswordModal` correctly uses `AdaptiveModal` + `IconChip tone="accent" icon={Lock}` + `ModalButton` as specified. The pattern mirrors InviteModal.

**PASS — avatar deferral:** Avatar reads `session.data.fullName` (server-authoritative post-invalidation), not the form's in-progress `form.fullName`. This correctly implements the spec requirement at `SectionsTop.tsx:235-238`.

**PASS — skeleton states:** ProfileSection pending state renders a 16×16 avatar skeleton + two line skeletons (`SectionsTop.tsx:212-216`). SecuritySection session rows use 52px skeleton rows matching the spec height constant.

**PASS — role chip:** Owner chip uses `bg-primary-soft text-primary-deep dark:text-primary` (accent) per spec; reception chip uses `bg-surface-3 text-fg-muted` (neutral) (`SectionsTop.tsx:244-249`).

### Pillar 3: Color (4/4)

All Phase 109 additions use semantic tokens exclusively. Grepped `ChangePasswordModal.tsx` and Phase 109 additions in `SectionsTop.tsx` — zero raw hex/rgb values in new code.

Accent (`bg-primary`, `bg-primary-soft`, `text-primary-deep`, `dark:text-primary`) is used only on:
- SaveBar save button — inherited, not changed
- "Сейчас" session badge — inherited, not changed
- Owner role chip (`SectionsTop.tsx:245`) — matches spec
- Modal `IconChip tone="accent"` (`ChangePasswordModal.tsx:120`) — matches spec

Error states (`text-danger`) used only on field error messages and destructive actions — matches spec.

`PaymentsSection` acquirer logo backgrounds use inline `style={{ background: a.bg }}` with hardcoded hex values (`#0095da`, `#005baa`, `#1a1a1a`) but this is pre-existing code not introduced in Phase 109.

### Pillar 4: Typography (3/4)

Spec declares field labels at `text-[12.5px] font-semibold` with `text-fg-subtle`. Implementation uses `text-[12px] font-semibold text-fg-muted` in both `ChangePasswordModal.tsx:138,158,178` and `SectionsTop.tsx:255,270`.

- Spec token: `text-fg-subtle`
- Actual token: `text-fg-muted`

These are different semantic tokens — `fg-muted` is typically lighter/more de-emphasized than `fg-subtle`. In practice the visual difference may be subtle, but it is a contract deviation on token selection.

The 0.5px font-size difference (`12px` vs `12.5px`) on field labels is likewise a minor drift. Both issues are consistent across all field labels — this is a systemic pattern not an isolated mistake.

All other typography (body text at `text-[13.5px]`, section headings at `text-[16px] font-bold`, supporting text at `text-[11px]`) matches the spec.

### Pillar 5: Spacing (3/4)

The `ChangePasswordModal.tsx` uses `mb-3.5` (14px) between the first two field groups and `mb-1` (4px) below the last field group before the footer.

- `mb-3.5` = 14px — not a declared spacing scale value (xs=4, sm=8, md=16, lg=24). Closest is `sm` (8px) or `md` (16px). 14px is an arbitrary value.
- The asymmetry between `mb-3.5` on groups 1–2 and `mb-1` on group 3 (`ChangePasswordModal.tsx:137,157,177`) creates inconsistent visual weight in the modal form.

The spec states "Modal uses AdaptiveModal component — internal padding/radius managed by that component" and notes the inherited 8-point scale. The 14px gap deviates from the scale without a documented exception.

`SectionsTop.tsx` ProfileSection spacing is consistent with BranchSection — `gap-2` between field wrappers, `mb-1.5` below labels — both are on the 8-point scale. No issues there.

### Pillar 6: Experience Design (3/4)

**State coverage — ProfileSection:**
- Idle: form seeded from `serverDataRef.current` via `useEffect` on `session.data` — PASS
- Dirty: `markDirty(ID_PROFILE)` called on every `patch()` call — PASS
- Saving: SaveBar shows "Сохраняем…" (inherited SaveBar behaviour, not controlled from this component; `submitting` state not tracked at ProfileSection level — the SaveBar itself owns this)
- Success: toast "Профиль обновлён" + `authKeys.me` invalidation — PASS (`SectionsTop.tsx:168-170`)
- Error network: toast "Не удалось сохранить. Попробуйте ещё раз." — PASS (`SectionsTop.tsx:183`)
- Error email taken: inline `fieldErrors.email = 'Email уже занят'` — PASS (`SectionsTop.tsx:178`)
- Cancel: resets form to `serverDataRef.current`, clears `fieldErrors` — PASS (`SectionsTop.tsx:190-195`)

**State coverage — ChangePasswordModal:**
- Form initial: three inputs, all password type — PASS
- Submit disabled condition: `!form.submitting && currentPassword.length > 0 && newPassword.length >= 12 && newPassword === confirmPassword` — PASS (`ChangePasswordModal.tsx:65-69`)
- Submitting: button shows "Сохраняем…" + disabled — PASS (`ChangePasswordModal.tsx:128-133`)
- Success: modal closes + toast + sessions invalidated — PASS (`ChangePasswordModal.tsx:94-97`)
- Error wrong password: inline field error on currentPassword — PASS (`ChangePasswordModal.tsx:107`)
- Error server/network: toast error — PASS (`ChangePasswordModal.tsx:109`)
- Close/reset: `setTimeout(300ms)` reset on `onOpenChange(false)` — PASS (`ChangePasswordModal.tsx:53-60`)

**BLOCKER — cancel button not disabled during submission:**
`ModalButton variant="ghost"` at `ChangePasswordModal.tsx:124` lacks `disabled={form.submitting}`. The spec mandates: "Submit button shows 'Сохраняем…' + disabled; inputs remain visible but not re-triggerable" and the modal footer contract shows `[Отмена (ghost)]` as dismissable — but during submission the cancel should not race with the in-flight mutation. The primary button is correctly disabled; the ghost cancel is not.

**WARNING — confirm mismatch error never shown:** `canSubmit` blocks submission silently when `newPassword !== confirmPassword`. No `fieldErrors.confirmPassword` is ever set (no `setFieldErrors({ confirmPassword: 'Пароли не совпадают' })` call exists). The spec declares this as a visible error state. The `fieldErrors.confirmPassword` render path at `ChangePasswordModal.tsx:191-195` is dead code.

**WARNING — sessions key mismatch risk:** `useChangePassword` invalidates `['auth', 'sessions']` (`api.ts:179`). The `useSessions` hook is defined in `features/settings/api.ts` and its key is likely `settingsKeys.sessions`. If the actual key is `['settings', 'sessions']` (not `['auth', 'sessions']`), the SecuritySection session list will not update after a password change — the toast shows but the session count stays stale. This is a functional correctness risk, not a visual one, but it belongs in the Experience Design pillar.

---

## Registry Safety

Registry audit: Phase 109 uses no third-party registries. All components are shadcn official (already initialized). No `npx shadcn add` commands were required — all components reused from existing codebase. No registry flags.

---

## Files Audited

- `/apps/admin-app/src/pages/settings/components/ChangePasswordModal.tsx`
- `/apps/admin-app/src/pages/settings/components/SectionsTop.tsx` (ProfileSection + SecuritySection)
- `/apps/admin-app/src/pages/settings/SettingsPage.tsx`
- `/apps/admin-app/src/features/auth/api.ts`
- `/apps/admin-app/src/features/auth/schemas.ts`
- `/apps/admin-app/src/components/settings/controls.tsx` (partial — SectionCard/SettingRow)
- `.planning/phases/109-profile-security-backend-wiring/109-UI-SPEC.md`
- `.planning/phases/109-profile-security-backend-wiring/109-CONTEXT.md`
