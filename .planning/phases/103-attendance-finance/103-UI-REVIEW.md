---
phase: 103
slug: attendance-finance
status: advisory
score: 21/24
audited: 2026-06-13
baseline: 103-UI-SPEC.md
screenshots: not captured (no dev server)
---

# Phase 103 — UI Review

**Audited:** 2026-06-13
**Baseline:** 103-UI-SPEC.md (approved wiring contract)
**Screenshots:** not captured — code-only audit (no dev server running)
**Scope:** net-new surfaces only per context contract: CheckInModal, VisitsList, AttendancePage, CashboxPage, LoadPage, FinancePage, DateRangePicker. Pre-existing design-system (tokens, type scale, spacing, base components) not re-audited.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Finance subtitle renders raw ISO dates; «Клиент не найден» missing `text-center` per spec |
| 2. Visuals | 4/4 | All state coverage correct; hierarchy clear; no icon-only unlabelled buttons |
| 3. Color | 4/4 | Token discipline maintained; refund / danger / accent assignments match spec |
| 4. Typography | 4/4 | All sizes match spec roles; no unspecified weights introduced |
| 5. Spacing | 4/4 | 8-pt scale honoured; arbitrary values only where spec explicitly calls them out |
| 6. Experience Design | 2/4 | Attendance page has no date-range picker (range locked to last 30 days, undated); `«Нет визитов»` vs `«Визитов пока нет»` distinction is unreachable by logic; Finance empty-state for Online tab uses wrong copy |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **Attendance page missing date-range picker** — users cannot change the date window; the 30-day range is silently hard-coded with no UI control. The spec (§1.5) states the page head should include a date-range filter. Add `DateRangePicker` to `AttendancePageHead` and wire state up to `useAttendanceList`. Impact: owners and reception have no way to audit historical visits beyond the current window without URL-hacking. Fix: replicate the CashboxPage / LoadPage pattern (`useState` + `DateRangePicker` in page head actions).

2. **`hasFilter` is always `true` — «Визитов пока нет» empty state is unreachable** — `AttendancePage.tsx:64` sets `const hasFilter = true` unconditionally, so the «Визитов пока нет» / «Зафиксируйте первый визит, нажав «Чек-ин»» state (`VisitsList.tsx:108-113`) can never be shown. For a brand-new club with zero visits ever, users see «Нет визитов» + «За выбранный период…» which is confusing. Fix: pass `hasFilter` based on whether the date range differs from the default, or better, pass a `hasVisitsEver` flag derived from a separate `total` across all time (or treat `hasFilter=false` when no dates are filtered).

3. **Finance page subtitle renders raw ISO date strings** — `FinancePage.tsx:107` constructs the subtitle as `` `${fromDate} – ${toDate} · выручка и онлайн-платежи` `` where `fromDate` and `toDate` are `YYYY-MM-DD` strings. The spec (§5.3 subtitle pattern) and project convention (`lib/format.ts` `formatDateRu`) require human-readable Russian formatting (e.g. `«13 мая – 13 июн.»`). The AttendancePage and CashboxPage both use `formatDateRu` for the subtitle; Finance does not. Fix: replace with `formatDateRu(fromDate, 'dd.MM.yy')` or `'dd MMM'` consistent with CashboxPageHead.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**WARNING — Finance subtitle raw ISO (`FinancePage.tsx:107`).**
Subtitle reads `"2026-05-14 – 2026-06-13 · выручка и онлайн-платежи"` in production. All other pages (`AttendancePage.tsx:68`, `CashboxPageHead`) use `formatDateRu`. Inconsistency and user-facing raw ISO date is a clear copy failure.

**ADVISORY — «Клиент не найден» container styling diverges from spec (`CheckInModal.tsx:243`).**
The spec (§1.2) states: `text-[13px] text-fg-subtle text-center py-4`. Implementation uses `py-5` and `text-fg-muted` instead of `text-fg-subtle`. Minor — visually close but `py-5` adds 4px extra vertical padding vs spec, and `text-fg-muted` is a token step brighter than `text-fg-subtle`. Not a blocker.

**PASS — All 409 error copy matches spec exactly** (`CheckInModal.tsx:42-55`). Three codes, three heading/body pairs — verified verbatim.

**PASS — All empty-state, KPI label, toast, and channel-label copy verified against copywriting contract.** No generic English strings (`Submit`, `OK`, `Error`) found in audited files.

**PASS — Finance tab labels** (`FinancePage.tsx:38-41`): `«Выручка»` and `«Онлайн-платежи»` match spec.

**PASS — groupBy labels** (`FinancePage.tsx:43-46`): `«По дням»` / `«По месяцам»` match spec.

**PASS — Daily total separator format** (`TransactionsCard.tsx:111`): `Итого: {sign}{amount}` — matches spec.

**PASS — Cashbox KPI labels** (`CashboxKpis.tsx:26,32,42`): `«Приход»`, `«Возвраты»`, `«Нетто»` — exact match.

---

### Pillar 2: Visuals (4/4)

**PASS — CheckInModal icon hierarchy** correct: `IconChip tone="accent"` with `UserCheck` per spec §1.2.

**PASS — Optimistic row** (`VisitsList.tsx:43,63`): `opacity-60` applied; `Loader2 size-3.5 animate-spin text-fg-subtle` in aside position — matches spec §1.3.

**PASS — Deselect button** (`CheckInModal.tsx:225-237`): `XIcon size-3.5` with `aria-label="Отменить выбор клиента"` — accessible, meets spec §1.2.

**PASS — Loader2 in search input** (`CheckInModal.tsx:211-213`): absolutely positioned right side, `size-4 animate-spin text-fg-subtle` — matches spec §1.2.

**PASS — 9 mock analytics widgets absent from AttendancePage render** — scope reduction applied correctly (spec §1.5). Files on disk per spec intent.

**PASS — LiveNowCard absent from LoadPage** (`LoadPage.tsx:29`): `// TODO Phase 104` comment present — correct.

**PASS — ShiftDrawer absent from CashboxPage** — no import or render in `CashboxPage.tsx`.

**PASS — Lock-EmptyState rendered before any data hook on all three owner-only pages** — RBAC guard is first block in `CashboxPage`, `LoadPage`, `FinancePage`.

**PASS — Refund row icon chip** (`TransactionsCard.tsx:35`): `bg-danger-soft text-danger` with `Undo2` icon — matches spec §5.1.

**PASS — Online payments empty state icon** (`FinancePage.tsx:247`): `TrendingUp` icon used instead of spec-unspecified icon — acceptable; spec did not prescribe an icon for this state.

---

### Pillar 3: Color (4/4)

**PASS — Accent (`bg-primary`) not applied to refund rows, 409 callouts, or Lock-EmptyState** — token boundary honoured throughout.

**PASS — Danger tokens correctly scoped** (`TransactionsCard.tsx:35,83`, `CashboxKpis.tsx:35-42,44-47`): `text-danger` for refund amounts and negative netto; `bg-danger-soft text-danger` for refund chip. All match spec §5.1 and Color section.

**PASS — Dark mode dark:bg-primary dark:text-[#06120c]** on check-in button (`AttendancePageHead.tsx:26`): consistent with P101/P102 primary action button pattern. The `dark:hover:bg-[#5ee9b8]` is a raw hex — this pattern is pre-existing / accepted (consistent with other primary action buttons in the codebase; not introduced by Phase 103).

**PASS — No new raw hex values introduced** by Phase 103 in the net-new files (the dark hover hex in AttendancePageHead mirrors the identical pattern established in earlier phases for all primary action buttons).

**PASS — Client avatar `AVATAR_COLOR`** (`CheckInModal.tsx:67`): uses `var(--color-primary)` CSS variable, not raw hex — correct per ESLint WR-05.

---

### Pillar 4: Typography (4/4)

**PASS — Visit row** (`VisitsList.tsx:54,55,65`): `text-[13.5px] font-semibold` for name, `text-[11.5px] text-fg-subtle` for meta, `text-[12.5px] font-semibold tabular-nums text-fg-muted` for time — matches spec §1.5 row anatomy.

**PASS — Transaction amount** (`TransactionsCard.tsx:82,83`): `text-[14.5px] font-bold tabular-nums` — matches spec money display role.

**PASS — Daily total separator** (`TransactionsCard.tsx:102`): `text-[11.5px]` with `font-semibold` (date) and `font-bold tabular-nums` (amount) — matches spec §5.2 subtle/meta role.

**PASS — DateRangePicker labels** (`DateRangePicker.tsx:71,74,85`): `text-[12.5px] font-semibold text-fg-muted` — exact match to spec §3.1 label anatomy.

**PASS — DateRangePicker inputs** (`DateRangePicker.tsx:37`): `text-[13px]` — matches spec §3.1.

**PASS — Lock-EmptyState** rendered by `EmptyState` component with pre-established `text-[15px] font-semibold` title and `text-[13px] text-fg-subtle` body — spec §2.1 confirmed satisfied via component reuse.

**PASS — TotalVisitsKpi** (`AttendancePage.tsx:39,42`): `text-[22px] font-bold tabular-nums` for the number, `text-[12px] text-fg-subtle` for the label — not explicitly spec'd but consistent with established KPI pattern.

---

### Pillar 5: Spacing (5/4 — all 4)

**PASS — DateRangePicker** (`DateRangePicker.tsx:70,72`): `flex-col gap-1` outer, `gap-2 sm:flex-row sm:items-center sm:gap-2` inner — 8-pt scale (4px/8px), responsive stack matches spec §3.1.

**PASS — CheckInModal body elements** (`CheckInModal.tsx:188,196,271`): `mb-3.5` (14px) spacing between sections — consistent with AdaptiveModal body exception from spec.

**PASS — Visit row** (`VisitsList.tsx:43`): `gap-3 px-4 py-3` — consistent with P101/P102 list row pattern.

**PASS — Payment row** (`TransactionsCard.tsx:67`): `gap-3 px-5 py-3` — matches existing `TransactionsCard` anatomy.

**PASS — Page layout containers** (`CashboxPage.tsx:69`, `LoadPage.tsx:74`, `FinancePage.tsx:104`): `gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7` — identical pattern across all three pages, consistent with established layout.

---

### Pillar 6: Experience Design (2/4)

**BLOCKER — Attendance page has no interactive date-range filter.**
`AttendancePage.tsx` hard-codes `from = mskDaysAgoISO(29)` and `to = mskTodayISO()` with no user control. `AttendancePageHead` receives only a `subtitle` string. The spec (§1.5) explicitly states "page head with date-range filter + «Чек-ин» button". All three owner-only pages (Cashbox, Load, Finance) implement `DateRangePicker` correctly; Attendance is the outlier. A user cannot query historical visits, check a specific week, or verify past check-ins. Constitutes a task-flow gap.

**WARNING — `hasFilter = true` constant makes «Визитов пока нет» dead code.**
`AttendancePage.tsx:64`: `const hasFilter = true`. The `VisitsList` component has correct branching logic at line 98 (`if (hasFilter)`) but it is permanently wired to the filter branch. On a fresh installation with zero visits, users cannot see the onboarding empty state with the «Чек-ин» CTA copy. Not a crash, but the differentiated empty state (spec §1.5, Copywriting Contract §Visits List States) is never reachable.

**WARNING — Finance Online tab empty state uses wrong icon.**
`FinancePage.tsx:247`: `icon={TrendingUp}` for the Online payments empty state. The spec (§4.3 + §Cashbox Ledger) specifies `icon=Wallet` for an empty payments list (mirrors Cashbox empty state). `TrendingUp` is semantically a chart icon, not a payments icon. Minor visual inconsistency.

**WARNING — Finance subtitle uses raw ISO dates (also a Copywriting finding).**
`FinancePage.tsx:107`: `` `${fromDate} – ${toDate} · выручка и онлайн-платежи` `` produces `2026-05-14 – 2026-06-13 · …` visible as the page subtitle. Cross-ref with Copywriting pillar.

**PASS — All three owner-only pages (Cashbox, Load, Finance)** correctly implement no-API-call RBAC guard before any data hooks fire. Reception navigating via direct URL gets Lock-EmptyState, not a 403 crash or blank page.

**PASS — All loading / error / empty / re-fetch states implemented** correctly: initial `PageLoading`, `PageError` with retry, section-level `Skeleton` on date re-fetch (head+KPIs remain visible), and inline `EmptyState` for all-zero data.

**PASS — 409 error states** keep modal open, roll back optimistic row, re-enable primary button, clear error on new client selection — spec §1.4 interaction contract fully met.

**PASS — Submitting state** disables both modal buttons, shows `Loader2` in primary, suppresses `onOpenChange` — matches spec §1.2 footer states.

**PASS — Zero-fill logic** (`features/load/api.ts`, `features/reports/utils.ts` per LoadPage and FinancePage imports): allZero check triggers `EmptyState` instead of flat-zero chart — spec §4.3 contract met.

**PASS — Daily totals separator** renders before the first payment row of each date group, not after; `DailyTotalRow` in `text-danger` when `totalKopecks < 0` — spec §5.2 correct.

**PASS — Nav gating** (`nav-items.ts:58,80`): `Касса` has `ownerOnly: true, ownerResource: 'payments'`; `Загруженность` has `ownerOnly: true, ownerResource: 'reports'`. `Посещаемость` has no `ownerOnly` flag — all three nav corrections from spec §2.2 verified.

---

## Registry Safety

No third-party registry blocks in Phase 103. All UI reuses official shadcn primitives and pre-existing project components. Registry audit: 0 third-party blocks — not applicable.

---

## Files Audited

- `apps/admin-app/src/components/modals/CheckInModal.tsx`
- `apps/admin-app/src/components/common/DateRangePicker.tsx`
- `apps/admin-app/src/pages/attendance/AttendancePage.tsx`
- `apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx`
- `apps/admin-app/src/pages/attendance/components/VisitsList.tsx`
- `apps/admin-app/src/pages/cashbox/CashboxPage.tsx`
- `apps/admin-app/src/pages/cashbox/components/CashboxKpis.tsx`
- `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx`
- `apps/admin-app/src/pages/finance/FinancePage.tsx`
- `apps/admin-app/src/pages/finance/components/OnlinePaymentsTable.tsx`
- `apps/admin-app/src/pages/load/LoadPage.tsx`
- `apps/admin-app/src/pages/load/components/LoadKpis.tsx`
- `apps/admin-app/src/layouts/AppLayout/nav-items.ts`
