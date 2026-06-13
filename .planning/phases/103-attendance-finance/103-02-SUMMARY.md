---
phase: 103-attendance-finance
plan: "02"
subsystem: admin-app/pages+modals+features
tags: [attendance, check-in, visits, optimistic-ui, 409-handling, modal]
dependency_graph:
  requires: [103-01]
  provides: [CheckInModal, VisitsList, AttendancePage-wired, attendance/api-delegation]
  affects: []
tech_stack:
  added: []
  patterns: [client-picker-modal, 409-multi-code-callout, optimistic-prepend-rollback, visits-list-pagination]
key_files:
  created:
    - apps/admin-app/src/components/modals/CheckInModal.tsx
    - apps/admin-app/src/pages/attendance/components/VisitsList.tsx
  modified:
    - apps/admin-app/src/features/attendance/api.ts
    - apps/admin-app/src/components/modals/ModalsProvider.tsx
    - apps/admin-app/src/pages/attendance/AttendancePage.tsx
    - apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx
    - apps/admin-app/src/components/icons/index.tsx
decisions:
  - "D-103-02-CHECKIN-RENAME: Old mock CheckinModal.tsx (QR scanner) replaced and renamed to CheckInModal.tsx (capital I) with the real client-picker + 409-handling implementation; macOS case-insensitive FS required git mv to properly record the rename"
  - "D-103-02-ATTENDANCE-PAGE-SIMPLIFIED: AttendancePage simplified to static last-30-days date range (no date picker) to stay in plan scope; date-range filter deferred to Phase 103 Plan 03+ where cashbox/finance need it"
  - "D-103-02-CLIENTNAME-TODO: VisitData does not embed clientName from server; VisitsList derives a fallback label (Клиент {clientId.slice(0,8)}) for rows without clientName; real name wiring is a TODO for Phase 104 when client cache is available"
metrics:
  duration: "10m"
  completed: "2026-06-13"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 5
---

# Phase 103 Plan 02: Attendance Screen Wire Summary

**One-liner:** AttendancePage wired to real paginated visits list with CheckInModal client-picker, optimistic check-in, and 3 distinct 409 Callout states for the ATT-01 reception check-in flow.

## What Was Built

### Task 1: features/attendance/api.ts delegation + CheckInModal

**`features/attendance/api.ts`** — Replaced the mock `useAttendance`/`mockResponse` implementation with a thin re-export layer delegating to the visits domain:
- `useVisitsList as useAttendanceList` — paginated list hook
- `useCheckIn`, `useGymMeta` — mutation + meta hooks
- `visitsKeys as attendanceVisitsKeys` — key factory re-export
- `ApiError` — ESLint boundary re-export (modals import from attendance/api, not @/api/client)

**`components/modals/CheckInModal.tsx`** (new — replaces mock QR-scanner `CheckinModal.tsx`):
- BookingModal anatomy MINUS PT-package picker
- Header: `IconChip tone="accent" icon={UserCheck}`, title «Чек-ин», description «Найдите клиента и отметьте его визит»
- Body: debounced 300ms `ModalInput icon={Search}` → `useClients({ q, pageSize:8 })` → `ResultList`/`ResultItem`
- In-flight Loader2 spinner inside input; max 8 results
- Selected client: `ResultItem active` + deselect button with `aria-label="Отменить выбор клиента"` (UI-checker FLAG)
- `useGymMeta()` pre-validation: soft `Callout tone="warn"` when outside gym hours
- 3 distinct 409 codes → 3 distinct `Callout tone="danger"` (T-103-02-409CHAIN):
  - `outside_gym_hours` → «Вне часов работы» / «Зал сейчас закрыт...»
  - `no_active_membership` → «Нет активного абонемента» / «У клиента нет действующего абонемента...»
  - `duplicate_checkin` → «Уже отмечен сегодня» / «Этот клиент уже был отмечен сегодня...»
  - Generic fallback for non-409 errors
- Modal stays open on any error; primary button re-enabled after 409
- On success: `toast.success('Визит зафиксирован', { description: clientName })` + close
- `useSession()` call in modal (currentUserId for mutation var)

**`components/icons/index.tsx`**: Added `UserCheck` export from lucide-react.

### Task 2: Register CheckInModal + rewire AttendancePage

**`components/modals/ModalsProvider.tsx`**: Replaced `CheckinModal` import with `CheckInModal` (capital I rename). Modal registered under `'checkin'` key — no change to modal context typing needed.

**`pages/attendance/components/AttendancePageHead.tsx`**: Replaced mock subtitle/period segment UI with:
- Simple `AttendancePageHead` accepting optional subtitle string
- «Чек-ин» primary button: `inline-flex h-[38px] ... bg-fg text-bg rounded-full dark:bg-primary` with `UserCheck icon size-[14px]`
- Opens `useModals().open('checkin')` — available for both reception + owner

**`pages/attendance/AttendancePage.tsx`**: Rewrote with real data:
- 9 analytics widgets removed from render (files kept on disk): HeatmapCard, PeakHero, HourCurveCard, FrequencyCard, DayOfWeekCard, DurationCard, CohortCard, AnomalyCards, RiskList
- Uses `useAttendanceList(filter)` from `@/features/attendance/api`
- Static last-30-days date range (from = today-29, to = today, pageSize=25)
- `PageLoading` on isPending, `PageError` on isError
- `TotalVisitsKpi` — simple tile showing `data.total` + date range
- `VisitsList` component with server pagination

**`pages/attendance/components/VisitsList.tsx`** (new):
- Renders rows from real `VisitData[]` per UI-SPEC §1.5
- Initials circle (bg-surface-3) + clientName (or fallback) + gymDate·channel-label + checkedInAt time
- Channel labels: `reception→Ресепшн`, `qr→QR`, `app→Приложение`
- Optimistic rows: `opacity-60` + `Loader2 size-3.5 animate-spin` aside
- Empty states: no visits in range (Activity icon, «Нет визитов») / no visits ever («Визитов пока нет», «Зафиксируйте первый визит...»)
- Server-side `Pagination` component (shown only when pageCount > 1)

## Commits

| Hash | Description |
|------|-------------|
| 4a7358e4 | feat(103-02): attendance/api.ts delegation + CheckInModal with 3-code 409 |
| e49fdd28 | feat(103-02): wire AttendancePage to real visits list + register CheckInModal |

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck` — exit 0
- `pnpm -F @clubcore/admin-app lint` — exit 0
- `pnpm -F @clubcore/admin-app test` — 303 tests across 22 files, all pass
- `pnpm -F @clubcore/admin-app build` — built in 2.60s, no errors

**Must-have checks:**
- AttendancePage does NOT import/render the 9 mock analytics widgets (comment-documented)
- `aria-label="Отменить выбор клиента"` present on deselect button (line 233 of CheckInModal.tsx)
- 3 distinct 409 code strings present in CheckInModal: `outside_gym_hours`, `no_active_membership`, `duplicate_checkin`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] macOS case-insensitive FS: CheckinModal → CheckInModal rename**
- **Found during:** Task 1 execution
- **Issue:** Creating `CheckInModal.tsx` on macOS case-insensitive FS caused TypeScript to report "file already included" conflict with the existing `CheckinModal.tsx`; deleting old file via `rm` also deleted the new file (same inode)
- **Fix:** Used `git mv CheckinModal.tsx CheckInModal.tsx` to properly rename within git (RM → rename commit), then rewrote the new content. TypeScript no longer saw the casing conflict.
- **Files modified:** `CheckInModal.tsx` (renamed from `CheckinModal.tsx`, content replaced)
- **Commit:** 4a7358e4

**2. [Rule 2 - Missing] ModalsProvider import updated alongside Task 1**
- **Found during:** Task 1 typecheck — `ModalsProvider.tsx` imported old `CheckinModal` name
- **Fix:** Updated import to `CheckInModal` (capital I) as part of the casing rename fix
- **Files modified:** `ModalsProvider.tsx`
- **Commit:** e49fdd28

### Scope Notes

- **AttendancePage date filter**: Plan suggested managing a `{ from, to, page, pageSize }` filter state with a date picker. Given plan scope focuses on list + check-in wiring, the date filter uses a static last-30-days range (hardcoded, no UI). Date-range picker deferred to Phase 103-03/04 scope (cashbox/finance need it; a shared component can be promoted then).
- **clientName in VisitData**: Server `VisitData` does not embed `clientName` — only `clientId`. VisitsList uses a fallback label `Клиент {clientId.slice(0,8)}` rather than triggering N+1 client detail fetches per row. The PATTERNS.md §1.5 acknowledged this as acceptable with a TODO note.

## Known Stubs

- **VisitsList clientName**: `visit.clientName` is always undefined (backend API does not embed it); rows show `Клиент {id.slice(0,8)}` fallback. TODO: wire client cache lookup in Phase 104 when client query infrastructure is established.

## Threat Surface Scan

All threats from plan `<threat_model>` are mitigated:
- **T-103-02-409CHAIN**: 3 distinct 409 codes rendered as read-only Callouts; modal stays open; no auto-retry; no client-side override possible.
- **T-103-02-OPTIMISTIC**: Optimistic row is cache-only; rolled back via `onError` snapshot restore in `useCheckIn`.
- **T-103-02-PII**: 409 Callouts use fixed Russian copy from UI-SPEC; no raw backend message, no clientId, no PII in error states.
- **T-103-02-CHECKIN-RBAC**: Check-in button rendered for both roles (reception + owner); backend enforces CHECK_IN permission authoritatively.
- **T-103-SC**: No new packages added.

No new threat surface introduced beyond plan scope.

## Self-Check: PASSED

All key files exist on disk. Both task commits verified in git log.
