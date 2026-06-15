---
phase: 108-editable-settings-backend-wiring
plan: "05"
subsystem: frontend
tags: [settings, zod, tanstack-query, rbac, react-router-dom, form-wiring, lock-card]
dependency_graph:
  requires:
    - "108-04 (8 TanStack Query hooks for gym/hours/booking/notifications, Zod schemas)"
    - "108-03 (_ALWAYS_ON_KINDS: payment_succeeded, autopay_charge_failed)"
  provides:
    - "BranchSection (CFG-01) wired to useGymInfo/useUpdateGymInfo with local state + Zod"
    - "HoursSection (CFG-02) wired to useWorkingHours/useUpdateWorkingHours, 7-day schedule grid"
    - "BookingSection (CFG-03) wired to useBookingConfig/useUpdateBookingConfig, kopecks↔rubles"
    - "NotificationsSection (CFG-04) wired to useNotificationPrefs/useUpdateNotificationPrefs, always-on disabled rows"
    - "SettingsPage SaveBar wired to call real mutations via per-section handler registry"
    - "Navigate-away guard via react-router-dom v6 useBlocker"
  affects:
    - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
    - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
    - apps/admin-app/src/pages/settings/SettingsPage.tsx
tech_stack:
  added: []
  patterns:
    - "No react-hook-form: local useState + Zod safeParse() on submit (D-101-01-NOHOOKFORM)"
    - "registerSave/registerCancel props: sections register mutation handlers into SettingsPage handlersRef Map"
    - "SaveBar calls all dirty-section save handlers via Promise.allSettled; partial failures reported"
    - "Navigate-away guard: useBlocker(BlockerFunction) from react-router-dom v6; custom dialog UI"
    - "InlineToggle + InlineStepper: controlled local components bypassing controls.tsx internal state"
    - "_ALWAYS_ON_KINDS: disabled role='switch' buttons with aria-checked locked on, title hint"
    - "noShowPenaltyKopecks: form stores/displays rubles (÷100), submit multiplies ×100"
    - "Reception zero-calls: Lock card via can(role,'edit','settings'/'gym') before query renders"
key_files:
  created: []
  modified:
    - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
    - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
    - apps/admin-app/src/pages/settings/SettingsPage.tsx
decisions:
  - "D-108-05-NOHOOKFORM: react-hook-form is a phantom dependency in admin-app (not in package.json/pnpm-lock.yaml); used local useState + Zod safeParse per D-101-01-NOHOOKFORM pattern established in Phase 101"
  - "D-108-05-INLINE-CONTROLS: Existing controls.tsx Toggle/Stepper have internal state; for wired sections InlineToggle/InlineStepper inline components own no internal state — caller (section form state) is the single source of truth"
  - "D-108-05-HANDLER-REGISTRY: SettingsPage holds handlersRef<Map<string,SectionHandlers>> updated on every section render; SaveBar onSave iterates dirty set, calls save() on each registered section, uses Promise.allSettled for partial-success reporting"
  - "D-108-05-REACT-ROUTER-BLOCKER: Plan spec said TanStack Router useBlocker; admin-app uses react-router-dom v6 (not TanStack Router); imported useBlocker + BlockerFunction from react-router-dom"
  - "D-108-05-TRIGGER-FALLBACK: NotificationPrefs.matrix is opaque JSONB Record<string,unknown>; DEFAULT_TRIGGERS array defines the canonical display list with default values; server data merged on top"
requirements_completed: []
metrics:
  duration: "~45 minutes"
  completed: "2026-06-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
---

# Phase 108 Plan 05: Settings UI Wiring Summary

**Four settings sections wired to real API hooks (CFG-01..04) using local state + Zod safeParse; SaveBar calls real mutations; react-router-dom v6 navigate-away guard with Save/Leave/Stay dialog**

## Performance

- **Duration:** ~45 minutes
- **Completed:** 2026-06-14
- **Tasks:** 2/2 completed (+ checkpoint auto-deferred)
- **Files modified:** 3

## Accomplishments

- BranchSection, HoursSection, BookingSection fully wired with Skeleton/error+retry/success states and reception Lock cards (zero API calls)
- NotificationsSection self-fetches prefs; matrix toggles controllable per trigger/channel; `payment_succeeded` + `autopay_charge_failed` always-on disabled rows
- SettingsPage SaveBar now calls real mutations: handler registry pattern, partial-save error reporting via `Promise.allSettled`
- Navigate-away guard with full custom dialog (Сохранить и уйти / Уйти без сохранения / Остаться)
- noShowPenaltyKopecks: form displays rubles (÷100), submit converts ×100 — implemented exactly per D-108-04-KOPECKS-COMMENT

## Task Commits

1. **Task 1: BranchSection/HoursSection/BookingSection wiring** — `dccc8ef5` (feat)
2. **Task 2: NotificationsSection + SaveBar mutations + navigate-away guard** — `b3741363` (feat)

## Files Created/Modified

- `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` — Rewrote BranchSection, HoursSection, BookingSection to self-fetch via Plan 04 hooks; ProfileSection + SecuritySection + PaymentsSection unchanged
- `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` — Rewrote NotificationsSection to self-fetch; removed `{ data: SettingsData }` prop; added imports for useNotificationPrefs/useUpdateNotificationPrefs/NotificationPrefsUpdateSchema
- `apps/admin-app/src/pages/settings/SettingsPage.tsx` — Added handlersRef save/cancel registry; wired SaveBar to real mutations; added useBlocker navigate-away guard from react-router-dom

## Decisions Made

- **D-108-05-NOHOOKFORM**: react-hook-form not in package.json (phantom dep). Used local `useState` + `Zod.safeParse()` per decision D-101-01-NOHOOKFORM from Phase 101.
- **D-108-05-INLINE-CONTROLS**: Existing `Toggle`/`Stepper` in controls.tsx have internal state which conflicts with form-owned state. Created `InlineToggle` and `InlineStepper` controlled components with no internal state so the section form state is the single source of truth.
- **D-108-05-HANDLER-REGISTRY**: `handlersRef<Map<string, SectionHandlers>>` updated on every section render via `useEffect([...form state])`. `SaveBar.onSave` iterates `dirty` set, calls registered `save()` per section via `Promise.allSettled`, clears dirty only on full success.
- **D-108-05-REACT-ROUTER-BLOCKER**: Plan spec referenced TanStack Router `useBlocker`. admin-app uses `react-router-dom` v6 (confirmed from package.json). Imported `useBlocker` + `type BlockerFunction` from `react-router-dom`.
- **D-108-05-TRIGGER-FALLBACK**: `NotificationPrefs.matrix` is opaque JSONB. Defined `DEFAULT_TRIGGERS: TriggerDef[]` as canonical display list; `buildMatrixState()` merges server data on top with boolean defaults.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] react-hook-form phantom dependency**
- **Found during:** Task 1 (BranchSection implementation)
- **Issue:** Plan spec said "use react-hook-form + Zod resolver" but react-hook-form is NOT in apps/admin-app/package.json or pnpm-lock.yaml. @hookform/resolvers is entirely absent. Prior execution context had written broken code using these phantom deps.
- **Fix:** Rewrote all four sections using local `useState` per field + `Zod.safeParse()` on submit, following the pattern established in D-101-01-NOHOOKFORM (Phase 101 ClientCreateModal).
- **Files modified:** SectionsTop.tsx, SectionsBottom.tsx
- **Verification:** typecheck + lint pass, 340/340 tests pass, build succeeds

**2. [Rule 1 - Bug] useBlocker import source**
- **Found during:** Task 2 (navigate-away guard)
- **Issue:** Plan spec referenced TanStack Router `useBlocker`. admin-app uses react-router-dom v6, not TanStack Router.
- **Fix:** Imported `useBlocker` and `type BlockerFunction` from `react-router-dom`.
- **Files modified:** SettingsPage.tsx
- **Verification:** typecheck passes with proper `BlockerFunction` type annotation

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug; plan spec referenced deps/packages not present in this app)
**Impact on plan:** Both fixes necessary for correctness. Functional behavior identical to plan intent. No scope creep.

## Deferred Human Verification (browser-UAT)

Task 3 was `type="checkpoint:human-verify"` — auto-deferred per autonomous policy. The following items require browser testing against a running stack:

1. **CFG-01 BranchSection (owner):** Visit /settings → BranchSection shows skeleton then loads gym data from GET /api/v1/gym. Edit name/address → SaveBar appears. Save → toast "Настройки сохранены", dirty cleared.
2. **CFG-01 BranchSection (reception):** Lock card visible, no GET /api/v1/gym network call in DevTools.
3. **CFG-01 field error 422:** Backend responds with 422 `fields.name` → error shown inline below name field.
4. **CFG-02 HoursSection (owner):** Schedule grid shows 7 days. Toggle a day closed (row grays out). Add a break via inline form. Save → success.
5. **CFG-02 HoursSection (reception):** Lock card, zero API calls.
6. **CFG-03 BookingSection (owner):** Step buttons change scheduleStepMinutes (active pill highlights). noShowPenalty field shows rubles (e.g. "500"), submitted as 50000 kopecks — verify in backend logs.
7. **CFG-03 noShowPenaltyKopecks conversion:** Enter 500 ₽ in form; network PUT body must contain `noShowPenaltyKopecks: 50000`.
8. **CFG-04 NotificationsSection (owner):** Matrix loads; toggle a cell → changes color. `payment_succeeded` + `autopay_charge_failed` rows show disabled toggles locked on with hover hint.
9. **CFG-04 senderSignature:** Type lowercase → auto-uppercased. Type 12+ chars → truncated to 11. Type digits → Zod error "только латинские заглавные буквы".
10. **CFG-04 quiet hours:** Change start/end time → SaveBar shows. Save → success.
11. **SaveBar multi-section:** Dirty BranchSection + NotificationsSection → SaveBar count=2. Save → both mutations fire simultaneously (DevTools network: 2 concurrent PUT requests).
12. **SaveBar partial failure:** Temporarily break one endpoint (network throttle/disable) → only failed section stays dirty, error toast appears.
13. **Navigate-away guard:** Dirty a section, click sidebar nav to another page → guard dialog appears. "Остаться" → stay on settings. "Уйти без сохранения" → navigate away, changes lost. "Сохранить и уйти" → saves then navigates.
14. **Navigate-away guard (clean):** No dirty sections → navigate away freely without dialog.
15. **Reception overall:** No settings GET endpoints fired in DevTools for reception role.

## Known Stubs

None — all wired sections self-fetch from real API hooks. AppSection, BillingSection, IntegrationsSection remain on mock data per plan (not in scope for Phase 108-05).

## Threat Flags

None — no new network endpoints or auth paths introduced. All mutations consume endpoints threat-modeled in Phase 108-02.

## Self-Check: PASSED

Files modified:
- apps/admin-app/src/pages/settings/components/SectionsTop.tsx: FOUND
- apps/admin-app/src/pages/settings/components/SectionsBottom.tsx: FOUND
- apps/admin-app/src/pages/settings/SettingsPage.tsx: FOUND

Commits:
- dccc8ef5 (Task 1): FOUND
- b3741363 (Task 2): FOUND

Verification:
- typecheck: PASSED (0 errors)
- lint: PASSED (0 warnings)
- tests: PASSED (340/340, 26 test files)
- build: PASSED (92.01 kB gzipped to 26.81 kB for SettingsPage chunk)
