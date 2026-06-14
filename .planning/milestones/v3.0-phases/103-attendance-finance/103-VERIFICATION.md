---
phase: 103-attendance-finance
verified: 2026-06-13T21:01:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Reception check-in round-trip: log in as reception staff, open Attendance page, click Чек-ин, search for a client, select them, click Отметить визит."
    expected: "POST /api/v1/visits fires, optimistic row appears with spinner, on success row is replaced by real data and a Sonner toast 'Визит зафиксирован' appears."
    why_human: "Requires a live Docker backend with seeded client and active membership; cannot be exercised by grep or static analysis."
  - test: "Reception check-in 409 flows: force each of the three server 409 codes (outside_gym_hours / no_active_membership / duplicate_checkin) — e.g. attempt duplicate check-in for a client already checked in today."
    expected: "Each 409 code maps to its own distinct Russian Callout inside the modal; modal stays open; optimistic row rolls back; primary button re-enables."
    why_human: "Requires a live backend that returns the specific 409 error codes; not testable from code alone."
  - test: "Reception navigates directly to /cashbox and /load (URL-bar navigation bypassing sidebar)."
    expected: "Both pages show 'Недостаточно прав' Lock-EmptyState. Network tab shows zero calls to /payments or /reports/* from the reception session."
    why_human: "React conditional rendering and enabled:false require a running browser + DevTools network tab to confirm zero API calls."
  - test: "Owner views Cashbox ledger with real payment data including a refund row."
    expected: "Refund rows render with Undo2 icon in bg-danger-soft, title 'Возврат', amount with '−' U+2212 prefix in text-danger (read-only, no dropdown action). Daily total separators appear between date groups with signed totals."
    why_human: "Requires real /payments data from the backend with at least one refund entry."
  - test: "Owner views Load page — hourly heatmap and daily trend chart render without NaN."
    expected: "IntensityHeatmap shows exactly 24 hourly cells; AreaTrendChart shows daily buckets for full date range. All-zero range shows inline EmptyState."
    why_human: "NaN in chart rendering only manifests visually in a browser; requires live /reports/visits data."
  - test: "Owner views Finance page — Revenue tab with day/month toggle and Online-payments tab."
    expected: "Выручка tab renders zero-filled AreaTrendChart; groupBy toggle switches between day/month views and refires the query. Онлайн-платежи tab shows paginated rows with correct formatting. No Неудачные / Выплаты тренерам tabs or Экспорт button are present."
    why_human: "Requires live /reports/revenue and /payments?method=online data from the backend."
---

# Phase 103: Attendance + Finance Wiring — Verification Report

**Phase Goal:** Reception can check in visits on real data; owner can see the cashbox, revenue, and online payments — all without mocks.
**Verified:** 2026-06-13T21:01:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | useVisitsList(filter) fetches GET /api/v1/visits with from/to/clientId/page/pageSize | ✓ VERIFIED | `visits/api.ts:62-77` — builds query from defined filter fields, calls staffRequest('get','/api/v1/visits'), parses VisitsListResponseSchema |
| 2 | useCheckIn() POSTs /api/v1/visits {clientId}, optimistically prepends a row, rolls back on error, does NOT toast 409s | ✓ VERIFIED | `visits/api.ts:116-169` — onMutate prepends optimistic row to all lists, onSuccess invalidates, onError rolls back via listSnapshots; comment on lines 165-166 confirms no 409 toast |
| 3 | usePaymentsLedger(filter, role) fetches global GET /api/v1/payments and is enabled only when can(role,'view','payments') | ✓ VERIFIED | `payments/api.ts:67-83` — `enabled: can(role, 'view', 'payments')` on line 80; role parameter explicit |
| 4 | useVisitsReport + useRevenueReport fetch /reports/visits + /reports/revenue and are enabled only when can(role,'view','reports') | ✓ VERIFIED | `reports/api.ts:61-95` — both hooks: `enabled: can(role, 'view', 'reports')` on lines 72, 92 |
| 5 | fillHourlyBuckets returns exactly 24 points; fillDailyBuckets/fillRevenueBuckets cover every day or month with zero-filled buckets — never NaN | ✓ VERIFIED | `reports/utils.ts:19-72` implemented; `reports/utils.test.ts` 18 tests pass including empty-array NaN checks and month branch |
| 6 | AttendancePage renders real paginated visits list (GET /api/v1/visits) with loading/error/empty states for reception + owner | ✓ VERIFIED | `AttendancePage.tsx:64-94` — uses useAttendanceList, renders PageLoading/PageError/VisitsList; no owner-only guard |
| 7 | CheckInModal opens, selects client, fires POST /api/v1/visits {clientId}, maps 3 distinct 409 codes to Russian Callouts, stays open on error | ✓ VERIFIED | `CheckInModal.tsx:41-54` defines CHECK_IN_ERROR_COPY with 3 keys; `line 233` aria-label="Отменить выбор клиента" present; catch block maps ApiError.code |
| 8 | nav-items.ts gates Касса (ownerOnly + ownerResource:'payments') and Загруженность (ownerOnly + ownerResource:'reports'); Посещаемость stays ungated | ✓ VERIFIED | `nav-items.ts:58, 80` — Касса has ownerOnly:true, ownerResource:'payments'; Загруженность has ownerOnly:true, ownerResource:'reports'; Посещаемость line 79 has neither |
| 9 | Reception navigating to /cashbox or /load sees Lock-EmptyState and fires ZERO owner-only API calls | ✓ VERIFIED | `CashboxPage.tsx:40` guard returns before CashboxPageContent; `LoadPage.tsx:43` guard returns before LoadPageContent; inner hooks therefore never execute for reception |
| 10 | CashboxPage renders real /payments ledger with signed amounts, refund rows read-only, client-side daily totals | ✓ VERIFIED | `CashboxPage.tsx:67-70` computes prikhod/vozvrat/netto; `TransactionsCard.tsx:35,42,48,58,83` handles refundOf, Undo2, text-danger; computeDailyTotals wired in `cashbox/api.ts:34` |
| 11 | LoadPage renders real /reports/visits zero-filled — no NaN; allZero → inline EmptyState | ✓ VERIFIED | `load/api.ts:30-41` applies fillHourlyBuckets+fillDailyBuckets; `LoadPage.tsx:75-97` computes allZero and renders EmptyState; LiveNowCard not imported |
| 12 | FinancePage is owner-gated, renders 2 real tabs (Выручка + Онлайн-платежи), revenue chart zero-filled via fillRevenueBuckets, mock tabs removed | ✓ VERIFIED | `FinancePage.tsx:50-53` TABS array has exactly 2 entries; `FinancePage.tsx:70` Lock-guard; `RevenueChart.tsx:25` calls fillRevenueBuckets; comment line 11 documents removed tabs |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/features/reports/schemas.ts` | VisitsReportSchema + RevenueReportSchema + RevenueBucketSchema | ✓ VERIFIED | All schemas present; RevenueBucketSchema at line 44 |
| `apps/admin-app/src/features/reports/utils.ts` | fillHourlyBuckets / fillDailyBuckets / fillRevenueBuckets | ✓ VERIFIED | All three exported; month branch fully implemented via eachMonthOfInterval |
| `apps/admin-app/src/features/reports/api.ts` | useVisitsReport + useRevenueReport owner-gated | ✓ VERIFIED | Both exported, enabled gates confirmed |
| `apps/admin-app/src/features/visits/api.ts` | useVisitsList + useGymMeta + useCheckIn | ✓ VERIFIED | All three exported; useClientVisits preserved |
| `apps/admin-app/src/features/payments/api.ts` | usePaymentsLedger global owner-gated | ✓ VERIFIED | Exported; usePaymentsByClient preserved |
| `apps/admin-app/src/features/reports/keys.ts` | reportsQueryKeys at ['reports-data'] root | ✓ VERIFIED | Root key 'reports-data' confirmed; no collision with legacy ['reports'] |
| `apps/admin-app/src/components/modals/CheckInModal.tsx` | Client picker + 3-code 409 Callouts + optimistic | ✓ VERIFIED | 291 lines; aria-label at line 233; 3 409 codes at lines 42-53 |
| `apps/admin-app/src/pages/attendance/components/VisitsList.tsx` | Paginated real visits rows | ✓ VERIFIED | 133 lines; CHANNEL_LABELS, optimistic opacity-60, EmptyState variants, Pagination |
| `apps/admin-app/src/features/attendance/api.ts` | Thin delegation to visits domain hooks | ✓ VERIFIED | Pure re-export; no mock import |
| `apps/admin-app/src/features/cashbox/utils.ts` | computeDailyTotals | ✓ VERIFIED | MSK-slice approach documented; 8 tests pass |
| `apps/admin-app/src/components/common/DateRangePicker.tsx` | from/to picker with 366-cap + inversion validation | ✓ VERIFIED | 95 lines; differenceInCalendarDays used; error messages verified |
| `apps/admin-app/src/pages/cashbox/CashboxPage.tsx` | Owner-gated cashbox ledger page | ✓ VERIFIED | Lock-guard before data hooks; CashboxPageContent split |
| `apps/admin-app/src/pages/load/LoadPage.tsx` | Owner-gated zero-filled visits-load page | ✓ VERIFIED | Lock-guard before data hooks; LoadPageContent split |
| `apps/admin-app/src/features/finance/api.ts` | useRevenueReport + useOnlinePayments re-exports | ✓ VERIFIED | 3-line re-export file; ApiError re-exported |
| `apps/admin-app/src/pages/finance/FinancePage.tsx` | Owner-gated 2-tab Finance | ✓ VERIFIED | 279 lines; Lock-guard; TABS array 2 entries |
| `apps/admin-app/src/pages/finance/components/RevenueChart.tsx` | Zero-filled revenue trend + groupBy | ✓ VERIFIED | 66 lines (>30 minimum); fillRevenueBuckets called at line 25 |
| `apps/admin-app/src/pages/finance/components/OnlinePaymentsTable.tsx` | Paginated online payments rows | ✓ VERIFIED | 130 lines; Pagination component wired |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| features/reports/api.ts | can(role,'view','reports') | enabled gate on useQuery | ✓ WIRED | Lines 72, 92 — both hooks gated |
| features/payments/api.ts | can(role,'view','payments') | enabled gate on useQuery | ✓ WIRED | Line 80 |
| features/visits/api.ts | qc.setQueryData (optimistic prepend + rollback) | useCheckIn onMutate/onError | ✓ WIRED | onMutate line 149; onError line 162 |
| layouts/AppLayout/nav-items.ts | Касса + Загруженность ownerOnly | ownerOnly:true + ownerResource | ✓ WIRED | Lines 58, 80 confirmed |
| pages/cashbox/CashboxPage.tsx | can(role,'view','payments') guard | early-return Lock-EmptyState | ✓ WIRED | Line 40 — before any data hook |
| features/cashbox/api.ts | computeDailyTotals | useCashbox transform | ✓ WIRED | Line 34 |
| pages/finance/FinancePage.tsx | 'Недостаточно прав' Lock guard | early-return before hooks | ✓ WIRED | Line 70 — before FinancePageContent |
| features/finance/api.ts | useRevenueReport + usePaymentsLedger | re-export delegation | ✓ WIRED | useOnlinePayments alias confirmed |
| pages/finance/components/RevenueChart.tsx | fillRevenueBuckets | zero-fill before chart | ✓ WIRED | Line 25 |
| components/modals/CheckInModal.tsx | useCheckIn + ApiError.code | mutateAsync + catch ApiError | ✓ WIRED | Line 145: `if (err instanceof ApiError)` |
| components/modals/CheckInModal.tsx | deselect button | aria-label="Отменить выбор клиента" | ✓ WIRED | Line 233 exact match |
| pages/attendance/AttendancePage.tsx | features/attendance/api (useAttendanceList) | hook call | ✓ WIRED | Line 15 import + line 71 call |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| AttendancePage.tsx | data (VisitsListResponse) | useAttendanceList → staffRequest GET /api/v1/visits | Real — staffRequest hits backend | ✓ FLOWING |
| CashboxPage.tsx | data.items (PaymentData[]) | useCashbox → usePaymentsLedger → staffRequest GET /api/v1/payments | Real — staffRequest hits backend | ✓ FLOWING |
| LoadPage.tsx | data.hourly/daily | useLoad → useVisitsReport → staffRequest GET /api/v1/reports/visits | Real — zero-fill applied to real response | ✓ FLOWING |
| FinancePage.tsx (revenue) | data.buckets (RevenueBucket[]) | useRevenueReport → staffRequest GET /api/v1/reports/revenue | Real — fillRevenueBuckets applied | ✓ FLOWING |
| FinancePage.tsx (online) | data.items (PaymentData[]) | useOnlinePayments → staffRequest GET /api/v1/payments?method=online | Real — method filter applied | ✓ FLOWING |
| RevenueChart.tsx | filled (RevenueBucket[]) | fillRevenueBuckets(buckets, fromDate, toDate, groupBy) | Zero-fill always produces non-NaN | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| fillHourlyBuckets returns exactly 24 points | `pnpm -F @clubcore/admin-app test -- src/features/reports/utils.test.ts` | 18/18 pass | ✓ PASS |
| fillDailyBuckets zero-fills correctly | same suite | 18/18 pass | ✓ PASS |
| fillRevenueBuckets covers day + month, no NaN | same suite | 18/18 pass | ✓ PASS |
| computeDailyTotals signed daily grouping | `pnpm -F @clubcore/admin-app test -- src/features/cashbox/utils.test.ts` | 8/8 pass | ✓ PASS |
| visits/schemas extensions parse correctly | `pnpm -F @clubcore/admin-app test -- src/features/visits/schemas.test.ts` | 20/20 pass | ✓ PASS |
| Full test suite (311 tests) | `pnpm -F @clubcore/admin-app test` | 311/311 pass, 23 files | ✓ PASS |
| TypeScript check | `pnpm -F @clubcore/admin-app typecheck` | exit 0 | ✓ PASS |
| ESLint | `pnpm -F @clubcore/admin-app lint` | exit 0 | ✓ PASS |
| Production build | `pnpm -F @clubcore/admin-app build` | built in 2.63s, exit 0 | ✓ PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes defined for this phase. Behavioral spot-checks above are the gate.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ATT-01 | 103-01, 103-02 | Attendance screen renders real visits; reception check-in via /visits/check-in | ✓ SATISFIED | useVisitsList wired; CheckInModal with 3 409 codes implemented; AttendancePage renders real list |
| ATT-02 | 103-01, 103-03 | Load screen renders real hourly/daily aggregate; no NaN on empty buckets | ✓ SATISFIED | fillHourlyBuckets/fillDailyBuckets (18 tests); LoadPage wired to useLoad which zero-fills |
| FIN-01 | 103-01, 103-03 | Cashbox renders real /payments ledger with sell+refund rows; daily totals | ✓ SATISFIED | usePaymentsLedger wired; computeDailyTotals (8 tests); refund rows read-only in TransactionsCard |
| FIN-02 | 103-01, 103-04 | Finance renders real revenue (groupBy day/month) + online payments | ✓ SATISFIED | useRevenueReport + useOnlinePayments wired; RevenueChart zero-fills via fillRevenueBuckets; 2 real tabs |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| visits/api.ts | 165-166 | TODO comment about 409 routing | ℹ️ Info | Intentional documentation, not a stub — hook deliberately does not toast 409; comment explains the design decision |
| attendance/api.ts (via VisitsList) | VisitsList.tsx:36 | `visit.clientName ?? 'Клиент {id.slice(0,8)}'` | ⚠️ Warning | clientName not embedded in server VisitData response — fallback label used; documented as TODO Phase 104 (D-103-02-CLIENTNAME-TODO) |
| load/LoadPage.tsx | 27 | `// TODO Phase 104: wire LiveNow to real-time endpoint` | ℹ️ Info | Intentional deferral; no issue tracker reference needed per plan scope (hide-for-future) |

No `TBD`, `FIXME`, or `XXX` markers found in phase 103 modified files.

**clientName fallback stub assessment:** The `visit.clientName ?? 'Клиент {id.slice(0,8)}'` pattern at VisitsList.tsx line 36 is a known limitation documented in the plan (PATTERNS.md §1.5) and SUMMARY D-103-02-CLIENTNAME-TODO. The server VisitData schema does not embed clientName. The fallback is a graceful degradation — all other row data (gymDate, channel, checkedInAt) flows from real data. This is WARNING-level, not a BLOCKER: the core ATT-01 goal (reception checks in visits on real data) is achieved; the display name is a UX enhancement deferred to Phase 104.

### Human Verification Required

#### 1. Reception check-in round-trip (live backend)

**Test:** Log in as reception staff. Navigate to /attendance. Click «Чек-ин». Search for a client with an active membership. Select them. Click «Отметить визит».
**Expected:** POST /api/v1/visits fires; optimistic row appears immediately with a Loader2 spinner; on success, row is replaced by real data and a Sonner toast «Визит зафиксирован» appears with the client name.
**Why human:** Requires a live Docker backend with seeded client data and an active membership; cannot be exercised by grep or static analysis.

#### 2. Reception check-in 409 flows (3 distinct codes)

**Test:** Force each of the three server 409 codes: (a) attempt check-in outside gym hours; (b) attempt check-in for a client with no active membership; (c) attempt a duplicate check-in for a client already checked in today.
**Expected:** Each 409 code maps to its own distinct Russian Callout inside the modal: «Вне часов работы», «Нет активного абонемента», «Уже отмечен сегодня». Modal stays open after each. Optimistic row rolls back. Primary button re-enables.
**Why human:** Requires a live backend that returns specific 409 error codes for each scenario.

#### 3. Reception zero-calls for owner-only pages

**Test:** Log in as reception. Directly navigate to /cashbox and then /load via the URL bar (not the sidebar, which already hides these items).
**Expected:** Both pages show «Недостаточно прав» Lock-EmptyState. Browser DevTools Network tab shows zero calls to /payments or /reports/* originating from these pages.
**Why human:** The enabled:false TanStack Query guard and React conditional rendering require a running browser + DevTools network inspection to confirm zero API calls.

#### 4. Owner cashbox ledger with refund rows

**Test:** Log in as owner. Navigate to /cashbox. Ensure the date range includes a payment with a refund (refundOf != null).
**Expected:** Refund rows display with Undo2 icon in bg-danger-soft chip, title «Возврат», amount with «−» (U+2212) prefix in text-danger — no dropdown action button. Daily total separator rows appear between date groups. KPIs show Приход / Возвраты / Нетто sums correctly.
**Why human:** Requires real /payments data from the backend with at least one refund entry.

#### 5. Load page zero-fill rendering without NaN

**Test:** Log in as owner. Navigate to /load. Verify the IntensityHeatmap shows 24 hourly cells and the AreaTrendChart shows daily buckets for the full 30-day range. Change date range to a period with no visits.
**Expected:** Charts render without NaN artifacts. All-zero range shows inline EmptyState «Нет данных за этот период» instead of a flat chart.
**Why human:** NaN in chart rendering only manifests visually in a browser.

#### 6. Finance page revenue + online-payments with real data

**Test:** Log in as owner. Navigate to /finance. Verify the Выручка tab renders a zero-filled AreaTrendChart; toggle «По дням» / «По месяцам» to see the groupBy switch. Check Онлайн-платежи tab for paginated rows. Confirm no «Неудачные» / «Выплаты тренерам» tabs and no «Экспорт» button are visible.
**Expected:** Revenue chart renders without NaN; groupBy toggle refires the query; online payments list pages correctly; removed tabs/button absent from the UI.
**Why human:** Requires live /reports/revenue and /payments?method=online data.

### Gaps Summary

No automated gaps found. All 12 observable truths verified. Requirements ATT-01, ATT-02, FIN-01, FIN-02 are fully satisfied in the codebase. The phase gate (typecheck + lint + 311 tests + build) passes.

6 items require human testing against the live Docker backend before the phase can be considered fully complete. These are live integration verifications, not code defects.

---

_Verified: 2026-06-13T21:01:00Z_
_Verifier: Claude (gsd-verifier)_
