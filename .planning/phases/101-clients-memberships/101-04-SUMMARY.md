---
phase: 101-clients-memberships
plan: "04"
subsystem: frontend/clients
tags: [clients, visits, payments, memberships, zod, staffRequest, tdd, per-tab-error, read-only]
dependency_graph:
  requires: [101-01, 101-03]
  provides: [features/visits/schemas.ts, features/visits/api.ts, features/payments/schemas.ts, features/payments/api.ts]
  affects: [pages/client/ClientPage, pages/client/components/ActivityTab, pages/client/components/TrainingsTab, pages/client/components/PaymentsTab]
tech_stack:
  added: []
  patterns:
    - staffRequest + Schema.parse(raw).data (same as auth/api.ts exemplar — P100 pattern)
    - Per-tab inline error isolation (PageError within tab, NOT bubbled to full-page)
    - TDD RED/GREEN cycle — failing test → schema implementation → 10 passing tests
    - usePaymentsByClient uses params (path interpolation), NOT query (by-client/{client_id} scoped path)
key_files:
  created:
    - apps/admin-app/src/features/visits/schemas.ts
    - apps/admin-app/src/features/visits/api.ts
    - apps/admin-app/src/features/visits/schemas.test.ts
    - apps/admin-app/src/features/payments/schemas.ts
    - apps/admin-app/src/features/payments/api.ts
  modified:
    - apps/admin-app/src/pages/client/ClientPage.tsx
    - apps/admin-app/src/pages/client/components/ActivityTab.tsx
    - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
    - apps/admin-app/src/pages/client/components/PaymentsTab.tsx
    - apps/admin-app/src/pages/client/components/ProfileTabs.tsx
decisions:
  - "Per-tab hooks called inside each tab component (clientId prop) — not lifted to ClientPage — preserves per-tab error isolation"
  - "ProfileTabs.counts made optional — real tabs load their own data, no count pre-wiring needed"
  - "TrainingsTab uses usePtPackagesByClient (101-03) — pt-package instances available; shows real PT-package rows with status/sessions"
  - "MembershipsSection added inline in ClientPage above tabs — shows active/frozen memberships via useMembershipsByClient reuse"
  - "Chat/Notes tabs remain on mock data — no backend chat/notes endpoints in Phase 101 scope"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-13"
  tasks_completed: 2
  files_created: 5
  files_modified: 5
  tests_added: 10
---

# Phase 101 Plan 04: Client-Detail Child Reads Summary

**One-liner:** Visits/payments Zod contract layer + by-client hooks wired to real backend; ClientPage activity/trainings/payments tabs on real data with per-tab loading/empty/error isolation; payments read-only (T-101-13-READONLY).

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | visits + payments read feature folders (schemas + by-client hooks) | ccc3dffc | visits/schemas.ts, visits/api.ts, visits/schemas.test.ts, payments/schemas.ts, payments/api.ts |
| 2 | Wire ClientPage tabs to real child reads | e66ad1d1 | ClientPage.tsx, ActivityTab.tsx, TrainingsTab.tsx, PaymentsTab.tsx, ProfileTabs.tsx |

## What Was Built

### Task 1: Visits + Payments Feature Folders

**`features/visits/schemas.ts`** — `VisitSchema` (id/clientId/membershipId/checkedInAt/gymDate/channel/checkedInBy nullable/createdAt) + `VisitsListResponseSchema` (data-wrapped paginated list) + types.

**`features/visits/api.ts`** — `visitsKeys` factory (`all`, `byClient(clientId)`) + `useClientVisits(clientId)` query (`staffRequest('get', '/api/v1/visits', { query: { clientId } })` + `VisitsListResponseSchema.parse(raw).data`, `enabled: !!clientId`, `staleTime: 30_000`) + `ApiError` re-export.

**`features/payments/schemas.ts`** — `PaymentSchema` (id/subjectKind/subjectId/amountKopecks/method/receivedAt/receivedByUserId/refundOf nullable/auditLogId nullable) + `PaymentsListResponseSchema` + types.

**`features/payments/api.ts`** — `paymentsKeys` factory (`all`, `byClient(clientId)`) + `usePaymentsByClient(clientId)` query using the **scoped path** `staffRequest('get', '/api/v1/payments/by-client/{client_id}', { params: { client_id: clientId } })` — NOT `?clientId=` query — + `PaymentsListResponseSchema.parse(raw).data`, `enabled: !!clientId`; `ApiError` re-export.

**`features/visits/schemas.test.ts`** — 10 TDD tests (RED/GREEN cycle): VisitSchema (null checkedInBy, string checkedInBy, gymDate ISO, channel, id/clientId/membershipId, missing fields) + VisitsListResponseSchema (valid list, items array, total/page/pageSize, missing data field). All 10 green.

### Task 2: ClientPage Tabs Wired to Real Data

**`ActivityTab.tsx`** — Rewritten to call `useClientVisits(clientId)` with `clientId` prop. Renders real `VisitData` rows (checkedInAt via `formatTime`, gymDate via `formatDateRu`, channel label). Per-tab states: Skeleton while loading, inline `PageError` on error (NOT full-page), inline `EmptyState` «Нет активности» / «Визиты клиента появятся здесь.» when empty. Mock `ClientDetail['activity']` prop removed.

**`TrainingsTab.tsx`** — Rewritten to call `usePtPackagesByClient(clientId)` (from 101-03 scope). Renders real `PtPackageData` rows (planSnapshot.name, sessionsRemaining/sessionsTotal, amountKopecks via `formatRub`, status badge, createdAt). Per-tab states: Skeleton, inline `PageError`, inline `EmptyState` «Нет тренировок» / «Персональные тренировки появятся здесь.» when empty. Mock `TrainingsTabData` prop removed.

**`PaymentsTab.tsx`** — Rewritten to call `usePaymentsByClient(clientId)` via the scoped `/by-client/{client_id}` path. Renders real `PaymentData` rows (amountKopecks via `formatRub`, method label, receivedAt via `formatDateRu`/`formatTime`; refund rows marked with Undo2 icon + `text-danger`). **NO refund/edit affordance** (T-101-13-READONLY — money actions live on membership lifecycle). Per-tab states: Skeleton, inline `PageError`, inline `EmptyState` «Нет платежей» / «История платежей клиента появятся здесь.» when empty. Mock `PaymentsTabData` prop removed.

**`ClientPage.tsx`** — Major update:
- Added `MembershipsSection` component that calls `useMembershipsByClient(clientId)` (reuse from 101-03); renders active/frozen memberships with status badge + endDate + amount; own per-tab inline `PageError`/`EmptyState` states
- Passes `clientId` to `ActivityTab`, `TrainingsTab`, `PaymentsTab` as prop (hooks called inside each tab — per-tab error isolation preserved)
- Removed dead mock branches for wired tabs (activity/trainings/payments no longer use `clientDetail.*` props)
- Chat/Notes still use `clientDetail.chat`/`clientDetail.notes` — mock kept on disk (no backend endpoint in Phase 101 scope)
- `ProfileTabs` called without `counts` prop (tabs load their own data)

**`ProfileTabs.tsx`** — `counts` prop changed from required (`ClientDetail['counts']`) to optional (`ProfileTabCounts`); counts accessed with optional chaining `counts?.trainings`. Import of `ClientDetail` type removed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ProfileTabs required `counts` prop from mock ClientDetail type**
- **Found during:** Task 2 typecheck
- **Issue:** `ProfileTabs` was typed with `counts: ClientDetail['counts']` (required), but ClientPage no longer passes mock counts after removing clientDetail dependency for wired tabs
- **Fix:** Changed `counts` to optional with `ProfileTabCounts` interface; added optional chaining for count access
- **Files modified:** `ProfileTabs.tsx`
- **Commit:** e66ad1d1

### Design Decisions

**1. TrainingsTab uses `usePtPackagesByClient` (PT-package instances)**
- The plan said to use PT-by-client read "if available, else show empty state"
- `usePtPackagesByClient` was created in 101-03 and is available — wired to TrainingsTab
- Shows real PT-package rows with plan name, sessions remaining, status, and amount

**2. MembershipsSection added inline in ClientPage above tabs**
- Plan required memberships tab to use `useMembershipsByClient` — rendered as an "active memberships" section above the tab area (shows active/frozen memberships)
- This follows the natural page layout without changing the tab structure

**3. Per-tab hook calls (not lifted to ClientPage)**
- Hooks called inside each tab component rather than being lifted to ClientPage
- Preserves per-tab error isolation (a failing payment query does not affect the visits tab)
- Each tab receives only `clientId` prop

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `ChatTab` renders mock `clientDetail.chat` | `ClientPage.tsx` | No backend chat endpoint in Phase 101 scope |
| `NotesTab` renders mock `clientDetail.notes` | `ClientPage.tsx` | No backend notes endpoint in Phase 101 scope |

These stubs do NOT prevent the plan's goal (CLI-02: memberships/visits/payments from real backend) from being achieved.

## Threat Surface Scan

All threats from the plan's threat model are mitigated:

| Flag | File | Status |
|------|------|--------|
| T-101-12-IDOR | `usePaymentsByClient` | MITIGATED — scoped `/by-client/{client_id}` path used; 403/404 collapses to per-tab inline error (PageError), not cross-client render |
| T-101-13-READONLY | `PaymentsTab` | MITIGATED — no refund/edit affordance rendered in PaymentsTab; strictly read-only |
| T-101-14-PII-ERR | all tabs | MITIGATED — errors rendered via `PageError` curated copy «Не удалось загрузить данные», no raw API envelope internals |
| T-101-SC | all | MITIGATED — no new packages installed |

No new security surface beyond the plan's threat model.

## Test Results

- `visits/schemas.test.ts`: 10 tests green (TDD RED/GREEN cycle)
- Full suite: 190 tests passed (12 test files)
- Typecheck: green
- Lint: green
- Build: green (2.59s)

## Self-Check: PASSED

All created files exist on disk:
- `apps/admin-app/src/features/visits/schemas.ts` — FOUND
- `apps/admin-app/src/features/visits/api.ts` — FOUND
- `apps/admin-app/src/features/visits/schemas.test.ts` — FOUND
- `apps/admin-app/src/features/payments/schemas.ts` — FOUND
- `apps/admin-app/src/features/payments/api.ts` — FOUND

All commits verified:
- `ccc3dffc`: feat(101-04): visits + payments read feature folders
- `e66ad1d1`: feat(101-04): wire ClientPage tabs to real child reads
