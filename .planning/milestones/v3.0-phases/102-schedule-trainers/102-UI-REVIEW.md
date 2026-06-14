---
phase: 102
slug: schedule-trainers
status: advisory
score: 19/24
audited: 2026-06-13
baseline: 102-UI-SPEC.md
screenshots: not captured (no dev server)
---

# Phase 102 — UI Review

**Audited:** 2026-06-13
**Baseline:** 102-UI-SPEC.md (approved design contract)
**Screenshots:** not captured — no dev server running; audit is code-only
**Scope:** net-new and changed surfaces only (ScheduleManagementModal, BookingModal, BookingDetailModal, SchedulePage calendar merge, PayoutsTab, TrainersPage reduction, TrainerHero/OverviewTab). Pre-existing design system, inherited type-scale, and spacing locked in P100/P101 are not re-flagged.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | 4 copy deviations from contract; all minor/non-blocking |
| 2. Visuals | 4/4 | Visual anatomy matches spec; badge placements and time-off stripe correct |
| 3. Color | 4/4 | No accent overreach; semantic tokens used correctly throughout |
| 4. Typography | 4/4 | Type roles match spec; money display `text-[20px] font-bold tabular-nums` confirmed |
| 5. Spacing | 3/4 | One arbitrary spacing pattern in BookingModal; no broken layouts |
| 6. Experience Design | 4/4 | All required states implemented; 409 paths covered without crashes |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **EmptyState body copy divergence (reception calendar)** — `SchedulePage.tsx:295` renders `«На выбранной неделе слоты ещё не опубликованы.»` but UI-SPEC §Calendar States requires `«Расписание появится здесь.»`. Unambiguous contract violation visible to every reception user when the week has no slots. Fix: change `message` prop on the reception `EmptyState` to the spec string.

2. **Conflict-state dismiss button label is «Назад» not «Отмена»** — `ScheduleManagementModal.tsx:487` uses `«Назад»` for the ghost button in the time-off conflict view. UI-SPEC §2 Copywriting Contract lists `«Отмена»` as the cancel CTA for that footer. The spec also says ghost "Отмена" closes the management modal entirely; «Назад» instead resets to form state (`setConflictData(null)`) which is a behavioral divergence too — the spec says ghost cancels the whole modal, not returns to the form. Decide: align label to «Отмена» and wire to `handleClose`, or accept the UX deviation and update the spec. Current behavior (back-to-form) is arguably better UX, but the label mismatch is a contract deviation.

3. **Mark-paid ConfirmModal uses `tone: 'default'` instead of `tone: 'primary'`** — `PayoutsTab.tsx:447`. UI-SPEC §5.4 specifies `tone: 'primary'` (non-destructive) for the mark-paid confirm. `'default'` may render the confirm button as neutral/secondary rather than a clear affirmative primary. Verify `ConfirmModal` interprets `'default'` identically to `'primary'`; if not, change to `'primary'`.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**WARNING — 4 deviations found:**

**[W1] Reception calendar empty body copy** (`SchedulePage.tsx:295`)
- Actual: `«На выбранной неделе слоты ещё не опубликованы.»`
- Contract: `«Расписание появится здесь.»`
- Impact: copy is more technical and implies editorial agency to reception staff, who have none.

**[W2] Owner calendar empty body copy** (`SchedulePage.tsx:280`)
- Actual: `«Опубликуйте слоты или создайте шаблон расписания.»`
- Contract: `«Опубликуйте слоты или создайте шаблон.»`
- The word `«расписания»` is appended; minor but differs from the spec literal.

**[W3] Conflict state dismiss label** (`ScheduleManagementModal.tsx:487`)
- Actual label: `«Назад»`
- Contract: `«Отмена»`
- Behavioral divergence: «Назад» resets conflict state to form; spec says ghost "Отмена" closes the modal entirely. Both words are readable Russian but spec literal differs. See Top Fix #2.

**[W4] Mark-paid ConfirmModal tone token** (`PayoutsTab.tsx:447`)
- `tone: 'default'` — spec requires `tone: 'primary'`. If ConfirmModal maps `'default'` to a neutral variant this affects the visual signal of a non-destructive financial action. See Top Fix #3.

All spec-required Russian copy for error codes, toast messages, field labels, status badges, and empty states is otherwise correct and complete: slot/template/timeoff error maps (`SLOT_ERROR_COPY`), PT-package error maps (`PT_PACKAGE_ERROR_COPY`), booking status labels (`STATUS_LABEL`/`STATUS_CLASS`), accrual status badges (`STATUS_BADGE`), and all payroll section headings match the contract verbatim.

### Pillar 2: Visuals (4/4)

No deviations found in the net-new surfaces.

- **ScheduleManagementModal:** `AdaptiveModal` with `IconChip tone='accent'` + `CalendarPlus`, ChipGroup tab switcher, three tab bodies — all match spec anatomy. Ghost "Отмена" in `footerActions` present; each tab body renders its own primary button (Опубликовать / Создать шаблон / Заблокировать) inline rather than in `footerActions`, which is an internal layout choice that does not break the visual contract.
- **BookingModal:** `IconChip tone='accent'` + `CalendarCheck`, debounced client search with inline `Loader2` spinner, `ResultItem` selected-client row with `X` deselect button, `Skeleton` rows for PT-package loading, `PlanCards` for package selection, footer info line — all match spec.
- **BookingDetailModal:** `StatRow` anatomy for all fields, status badge with correct class per status, «Отмена брони» ghost-danger-styled button, «Завершить» primary for owner — matches spec including the `text-danger hover:bg-danger-soft hover:text-danger` override pattern.
- **EventBlock:** `«занято»` badge (`bg-fg/10 text-fg text-[8.5px] font-bold uppercase tracking-[0.3px]`) placed in the header row; `«недоступно»` label centered in time-off block; diagonal-stripe `repeating-linear-gradient` on time-off blocks — exact spec.
- **PayoutsTab:** `Panel`+`PanelHead`+`PanelBody` three-panel structure, `StatRow` rows for current config and preview, `«К начислению»` total in `text-[20px] font-bold tabular-nums tracking-[-0.4px]`, `AccrualRow` with `Wallet` icon chip in `bg-primary-soft`, status badges, «Выплатить» row button — all match spec.
- **TrainersPage:** Load/Requests/Earnings sections removed; only «Команда» section rendered; `TrainerFilterTabs` absent (single-tab suppressed); `SectionHead` subtitle `«Тренеров: {total}»` correct; `RosterCard` edit+delete buttons present for owner — all match spec §6.
- **TrainerHero:** `photoUrl` → `img` with initials fallback, `isActive` badge, `specialization` chips — wired per spec §7.4.

**No icon mislabels, no missing aria-labels on interactive elements** (FAB has `aria-label="Управление расписанием"`; deselect X button has `aria-label="Снять выбор клиента"`).

### Pillar 3: Color (4/4)

No accent overreach or semantic token violations in the net-new surfaces.

- Accent (`--primary` / `bg-primary`, `text-primary`) used only on: live event ring, «идёт» badge, `AccrualRow` Wallet chip (`bg-primary-soft`), paid status badge (`bg-primary-soft text-primary-deep`), confirmed booking status badge (`bg-primary-soft text-primary-deep`) — all in the reserved list.
- Destructive path: «Отмена брони» uses `text-danger hover:bg-danger-soft` override on a ghost button; danger Callout for conflict state; `bg-danger-soft text-danger` for clawback badge — correct.
- Warning path: `bg-warning-soft text-warning-deep` for no_show badge and pending accrual badge — correct.
- No hardcoded hex overrides except `#2dd4a4` for client `ResultItem` avatar color in `BookingModal.tsx:229` (the brand primary literal). This is an existing pattern (established in P100/P101 for avatar colors) — not a new violation per scope exclusion.
- Time-off stripe uses `var(--surface-2)` + `var(--surface-3)` — correct semantic tokens, no raw palette.
- TrainerHero isActive dot: `bg-primary` (active) / `bg-fg-subtle` (inactive) — correct.
- FAB dark-mode override `dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]` uses a hardcoded hex but this is an existing P100/P101 pattern for the FAB — inherited, not new.

### Pillar 4: Typography (4/4)

All type roles in net-new surfaces match the spec type scale:

- Modal titles: `AdaptiveModal` renders `text-[17px] font-bold` — inherited, locked.
- Field labels: `text-xs font-semibold` (12px) — inherited.
- `«занято»` badge: `text-[8.5px] font-bold uppercase` — matches spec exactly.
- `«недоступно»` label: `text-[11px] text-fg-subtle` — matches spec.
- Money display: `text-[20px] font-bold tabular-nums tracking-[-0.4px]` — matches spec `money display` role.
- Accrual period label: `text-[13px] font-semibold` — matches spec.
- Status badges: `text-[11px] font-semibold rounded-full` — matches spec.
- PT-package empty state: `text-[13.5px] font-semibold` (title) + `text-[11.5px] text-fg-subtle` (body) — within spec item title/subtle range; not a named spec role but consistent with established P100/P101 patterns.

No new type sizes or weights introduced outside the locked scale.

### Pillar 5: Spacing (3/4)

**WARNING — 1 non-standard pattern found:**

**[W5] BookingModal inline empty state uses `py-5` not `py-24`** (`BookingModal.tsx:250, 285`)
- The `«Клиент не найден»` and `«Нет активных PT-пакетов»` states are rendered as custom `div` elements with `py-5` (20px) rather than the `<EmptyState>` component with `py-24` specified by UI-SPEC §3.3.
- UI-SPEC §3.3 says: `EmptyState (no icon) inline` for both. The custom div implementation achieves the same visual label but without the `EmptyState` component's consistent vertical rhythm (`py-24`).
- In the constrained modal body context, `py-5` is arguably more appropriate than `py-24` (which would force a scroll on mobile), so this is a spec-vs-implementation judgment call. The spec may be incorrect for the modal body constraint. **Advisory only** — do not over-correct.
- No other arbitrary spacing values observed; spacing follows 8-point scale throughout (gap-2, gap-3, gap-4, gap-3.5, mt-4, pt-3, etc.).
- `mt-3.5` appears in `BookingModal.tsx:303` for the api-error Callout; this is 14px (not on the strict 8pt scale) but consistent with P100/P101 established patterns.

All other net-new spacing uses standard scale tokens or inherits from locked modal anatomy.

### Pillar 6: Experience Design (4/4)

All required interaction states are implemented. Full state-coverage audit:

**ScheduleManagementModal:**
- Loading trainers for selects: handled via `trainersQuery.data?.items ?? []` (empty list while loading, selects show only placeholder option)
- Slot tab 409 codes: `SLOT_ERROR_COPY` map covers all 4 spec codes, rendered as `Callout tone='danger'`
- Template tab errors: API errors shown via `Callout tone='danger'`; validationError covers all spec cases
- TimeOff 409 `time_off_booked_conflict`: switches body to conflict callout + StatRow + force-override footer — no crash, modal stays open ✓
- Force mutation in-flight: `Loader2` spinner + disabled state on danger button ✓
- Force non-409 error: `setForceError` → `Callout tone='danger'` with spec copy ✓
- Primary buttons disabled while fields empty ✓; disabled while pending ✓

**BookingModal:**
- Client search: debounced 300ms, `Loader2` in input right while fetching ✓
- Selected client: `ResultItem active` + X deselect button ✓
- Client not found: inline div with spec copy ✓ (uses div not EmptyState — see Pillar 5 note)
- PT-package section hidden until client selected ✓
- PT-packages loading: 3 `Skeleton` rows ✓
- No active PT-packages: inline div with spec copy, primary stays disabled ✓
- 409 `slot_already_booked` / `slot_not_available`: `Callout` + follow-up copy + `queryClient.invalidateQueries({ queryKey: scheduleKeys.all })` — modal stays open ✓
- 409 PT-package codes: all 4 codes in `PT_PACKAGE_ERROR_COPY` ✓
- Success: `toast.success` with spec copy + `onOpenChange(false)` ✓
- `onOpenChange` suppressed while mutation pending: `handleOpenChange = isPending ? () => {} : onOpenChange` ✓

**BookingDetailModal:**
- `showCancel` logic: owner always, reception only when `!within24h` ✓
- `showComplete`: owner only ✓
- 24h reception message in confirm: correct branch on `within24h` ✓
- Cancel 409 `cancel_window_expired`: handled in hook (toasts); both modals close ✓ (both `setConfirmOpen(false)` + `onOpenChange(false)` in catch block)
- Complete handled via hook; no crash on error ✓
- Terminal statuses (cancelled/no_show/completed): no cancel/complete buttons ✓

**SchedulePage calendar:**
- `isPending` (any of 3 queries) → `<PageLoading />` ✓
- `isError` (slots or bookings) → `<PageError onRetry={handleRetry} />` with combined refetch ✓
- Empty state owner: `EmptyState CalendarPlus` + action button opens management modal ✓
- Empty state reception: `EmptyState CalendarX` (no action) ✓
- FAB hidden for reception via `can(role, 'create', 'schedule-slots')` ✓
- Event click routing: available → BookingModal, booked → BookingDetailLoader, time-off/cancelled → no-op ✓

**PayoutsTab:**
- Reception: renders `EmptyState Lock` immediately before any hook fires — no API calls ✓
- Config loading: 3 Skeleton rows ✓
- Config 404 `comp_config_missing`: `Callout tone='warn'` ✓
- Config editor always shown for owner after loading ✓
- Current config read-only StatRow display above editor ✓
- Preview 422 `comp_config_missing` / `unprocessable_entity`: `Callout tone='warn'` ✓
- Preview result: StatRow breakdown + total amount + «Начислить» button ✓
- Accrual run 409 `payroll_period_already_run`: handled in hook, `previewEnabled` cleared ✓
- Accruals list loading: 3 `h-[52px]` Skeleton rows ✓
- Accruals empty: `EmptyState` with spec copy ✓
- Mark-paid 409 `already_paid`: handled in hook ✓
- Mark-paid success: `toast.success('Выплата зафиксирована', { description: formatMoney(…) })` ✓

**TrainersPage:**
- Load/Requests/Earnings sections entirely absent from JSX ✓
- `TrainerFilterTabs` absent (single-tab suppressed) ✓
- `«Тренеров: {total}»` in SectionHead subtitle ✓
- Edit/delete buttons gated by `can(role, …)` ✓
- 409 `trainer_in_use`: `toast.error('Нельзя удалить', { description: '…' })` ✓
- TrainerFormModal wired for both create and edit ✓

**HistoryTab:** mock data with TODO comment — accepted per spec §7.3 ✓
**TrainerKpis:** deferred — not shown per spec §7.4 ✓

---

## Registry Safety

No third-party registries in Phase 102. All new UI reuses existing `AdaptiveModal`, `fields.tsx` primitives, `ConfirmModal`, `EmptyState`, `EventBlock`/`WeekCalendar`. Registry audit: 0 third-party blocks — not applicable.

---

## Files Audited

- `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx`
- `apps/admin-app/src/components/modals/BookingModal.tsx`
- `apps/admin-app/src/components/modals/BookingDetailModal.tsx`
- `apps/admin-app/src/pages/schedule/SchedulePage.tsx`
- `apps/admin-app/src/pages/schedule/components/EventBlock.tsx`
- `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx`
- `apps/admin-app/src/pages/trainer/components/TrainerHero.tsx` (grep scan)
- `apps/admin-app/src/pages/trainer/components/OverviewTab.tsx` (grep scan)
- `apps/admin-app/src/pages/trainers/TrainersPage.tsx`
- `apps/admin-app/src/components/modals/ScheduleManagementModal.test.tsx` (existence confirmed)
- `apps/admin-app/src/components/modals/BookingModal.test.tsx` (existence confirmed)
- Reference: `102-UI-SPEC.md` (full read)
