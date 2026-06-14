---
phase: quick-260614-hux
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/admin-app/src/features/clients/schemas.ts
  - apps/admin-app/src/features/memberships/schemas.ts
  - apps/admin-app/src/features/memberships/schemas.test.ts
  - apps/admin-app/src/features/memberships/api.ts
  - apps/admin-app/src/pages/client/ClientPage.tsx
  - apps/admin-app/src/components/modals/SubscriptionModal.tsx
  - apps/admin-app/src/lib/format.ts
  - apps/admin-app/src/lib/format.test.ts
  - apps/admin-app/src/pages/plans/PlansPage.tsx
  - apps/admin-app/src/pages/client/components/PaymentsTab.tsx
  - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
  - apps/admin-app/src/pages/schedule/SchedulePage.tsx
  - apps/admin-app/src/features/reports/schemas.ts
  - apps/admin-app/src/features/reports/schemas.test.ts
  - apps/admin-app/src/features/reports/utils.ts
  - apps/admin-app/src/features/reports/utils.test.ts
  - apps/admin-app/src/pages/reports/ReportsPage.tsx
  - apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx
  - apps/admin-app/src/features/audit/schemas.ts
  - apps/admin-app/src/features/settings/schemas.ts
  - apps/admin-app/src/features/visits/api.ts
  - apps/admin-app/src/components/modals/NewClientModal.tsx
autonomous: true
requirements: [CLI-01, CLI-02, CLI-03, MEM-01, MEM-02, MEM-03, SCH-02, RPT-01, RPT-02, RPT-03, FIN-01, FIN-02, ATT-01, SET-01]

must_haves:
  truths:
    - "GET /clients list renders the seeded dev client (telegramUserId is an int)"
    - "Петров client page renders the membership row from the flat /memberships shape"
    - "Plans page shows the 5000₽ plan as «5 000 ₽» (not «500 000 ₽»)"
    - "/schedule renders with a trainer present (no trainerId=undefined 422 crash)"
    - "Отчёты (Выручка + Тренеры) and Финансы render with seeded 5000₽ revenue; dashboard Топ тренеры shows real data"
    - "/settings/audit (Журнал действий) renders rows with null actor fields"
    - "Настройки → Активные сессии renders rows with null userAgent"
    - "A UI check-in of a client without a today-visit shows «Визит зафиксирован»"
    - "Duplicate-phone client create shows a localized «Клиент с таким телефоном уже существует» message"
  artifacts:
    - path: "apps/admin-app/src/features/clients/schemas.ts"
      provides: "ClientSchema.telegramUserId accepts number | string | null"
      contains: "telegramUserId"
    - path: "apps/admin-app/src/features/memberships/schemas.ts"
      provides: "Flat MembershipSchema matching real wire shape"
      contains: "planNameSnapshot"
    - path: "apps/admin-app/src/lib/format.ts"
      provides: "formatKopecks(kopecks) divides by 100 then formats RUB"
      contains: "formatKopecks"
    - path: "apps/admin-app/src/features/reports/schemas.ts"
      provides: "Revenue ptPackage casing + flat trainers[] report shape"
      contains: "ptPackage"
    - path: "apps/admin-app/src/features/audit/schemas.ts"
      provides: "Nullable actorUserId + actorEmailSnapshot"
      contains: "actorEmailSnapshot"
    - path: "apps/admin-app/src/features/settings/schemas.ts"
      provides: "Nullable userAgent on SessionSchema"
      contains: "userAgent"
    - path: "apps/admin-app/src/features/visits/api.ts"
      provides: "useCheckIn onMutate guards non-list cache entries"
      contains: "Array.isArray"
  key_links:
    - from: "apps/admin-app/src/pages/client/ClientPage.tsx"
      to: "apps/admin-app/src/features/memberships/schemas.ts"
      via: "m.planNameSnapshot + m.priceKopecksSnapshot fields"
      pattern: "planNameSnapshot|priceKopecksSnapshot"
    - from: "apps/admin-app/src/pages/plans/PlansPage.tsx"
      to: "apps/admin-app/src/lib/format.ts"
      via: "formatKopecks(plan.priceKopecks)"
      pattern: "formatKopecks"
    - from: "apps/admin-app/src/pages/reports/ReportsPage.tsx"
      to: "apps/admin-app/src/features/reports/schemas.ts"
      via: "data.trainers[] rows with renamed fields"
      pattern: "trainers|trainerNameSnapshot|revenueKopecks"
    - from: "apps/admin-app/src/pages/schedule/SchedulePage.tsx"
      to: "apps/admin-app/src/features/schedule/api.ts"
      via: "useTrainerSlots not firing with trainerId=undefined"
      pattern: "enabled|trainerId"
---

<objective>
Fix the 8 frontend schema/format/cache divergences (plus 1 UX localization) found by the v3.0 live-browser UAT audit. Every bug has the same root cause: the admin-app frontend Zod schema, money formatter, or cache logic diverges from the REAL backend wire shape. Unit tests asserted against mock fixtures whose shapes differ from the live API, so none of these were caught pre-wiring.

Purpose: Make the wired admin-app screens render and function correctly against the real backend so the deferred v3.0 live-UAT items can pass. Without these fixes, the clients list, client detail memberships, plans pricing, schedule, reports, finance, dashboard top-trainers, audit log, active-sessions, and UI check-in are all broken on real data.

Output: Frontend-only fixes (no backend edits). Each task is atomic and independently committable — one task per bug. After all tasks, `typecheck` + `lint` + `test` are green and the named live screens render against the running stack.

Scope guards (do NOT touch): GAP-1 membership lifecycle UI trigger (product decision), hero «Удалить клиента» stub, mock sidebar/KPI/2FA chrome.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/gsd-core/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/v3.0-UAT-BROWSER-AUDIT.md
@./CLAUDE.md
@apps/admin-app/CLAUDE.md

# Source files (the bug sites + their consumers)
@apps/admin-app/src/features/clients/schemas.ts
@apps/admin-app/src/features/memberships/schemas.ts
@apps/admin-app/src/features/memberships/api.ts
@apps/admin-app/src/pages/client/ClientPage.tsx
@apps/admin-app/src/components/modals/SubscriptionModal.tsx
@apps/admin-app/src/lib/format.ts
@apps/admin-app/src/pages/plans/PlansPage.tsx
@apps/admin-app/src/pages/client/components/PaymentsTab.tsx
@apps/admin-app/src/pages/client/components/TrainingsTab.tsx
@apps/admin-app/src/pages/schedule/SchedulePage.tsx
@apps/admin-app/src/features/schedule/api.ts
@apps/admin-app/src/features/reports/schemas.ts
@apps/admin-app/src/features/reports/utils.ts
@apps/admin-app/src/pages/reports/ReportsPage.tsx
@apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx
@apps/admin-app/src/features/audit/schemas.ts
@apps/admin-app/src/features/settings/schemas.ts
@apps/admin-app/src/features/visits/api.ts
@apps/admin-app/src/components/modals/NewClientModal.tsx
@apps/admin-app/src/api/client.ts

# Conventions reminder: no semicolons, single quotes, semantic tokens, strict TS,
# money = integer kopecks formatted via lib/format.ts helpers, Russian-only copy.
</context>

<execution_notes>
TASK ORDERING IS LOAD-BEARING. Several tasks share files (ClientPage.tsx, SubscriptionModal.tsx, memberships/api.ts). Execute tasks 1→9 in order and commit each separately:

- Task 2 (BUG-2) renames membership fields (`m.paidAmountKopecks` → `m.priceKopecksSnapshot`, `m.planSnapshot.name` → `m.planNameSnapshot`) in ClientPage/SubscriptionModal/memberships api.
- Task 3 (BUG-3) THEN swaps the kopecks `formatRub(...)` call sites — including the freshly-renamed `m.priceKopecksSnapshot` in ClientPage and the membership amounts in SubscriptionModal/memberships api — to `formatKopecks(...)`.

Running Task 3 before Task 2 would target field names that no longer exist. Do BUG-2 first.

Every schema rename also has unit tests asserting the OLD shape (the mock fixtures that hid the bug). Update those tests in the SAME task so they assert the REAL wire shape — otherwise `pnpm -F @clubcore/admin-app test` stays red.

Real-data verification: the docker stack + admin-app dev server (:5173) are running, DB seeded. Login owner@clubcore.dev / devpassword12345 (reception@clubcore.dev for RBAC-negative checks). Seeded: client «Петров Иван», plan «Месяц безлимит» 5000₽, trainer «Тренер Тестов», a visit today on Петров. For each task: run typecheck + lint + the relevant test file, THEN load the named screen in the browser and confirm it renders without a PageError.
</execution_notes>

<tasks>

<task type="auto">
  <name>Task 1 (BUG-1): clients telegramUserId int vs string</name>
  <files>apps/admin-app/src/features/clients/schemas.ts</files>
  <action>
In `ClientSchema`, change the `telegramUserId` field from `z.string().nullable().optional()` to a union that accepts the integer the backend actually sends (e.g. 999999999): `z.union([z.number(), z.string()]).nullable().optional()`. The backend column is `telegram_user_id: int | None`, serialized as a JSON number, so the current `z.string()` makes `z.array(ClientSchema)` throw and crashes the entire clients list AND client detail.

Leave `ClientCreateSchema.telegramUserId` as `z.string().optional()` — that path is form input (string), not the wire-read field. Only the read schema (`ClientSchema`) needs the union. No consumer reads `client.telegramUserId` for display in the in-scope screens, so no component change is required. Keep no-semicolon / single-quote style.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>With owner logged in at :5173, open /clients — the list renders the seeded dev client (and «Петров Иван») with NO PageError. Open a client detail page — it loads.</human-check>
  </verify>
  <done>`telegramUserId` on `ClientSchema` accepts number | string | null | undefined; typecheck + lint green; /clients list and client detail render against real data.</done>
</task>

<task type="auto">
  <name>Task 2 (BUG-2): memberships flat wire shape</name>
  <files>apps/admin-app/src/features/memberships/schemas.ts, apps/admin-app/src/features/memberships/schemas.test.ts, apps/admin-app/src/features/memberships/api.ts, apps/admin-app/src/pages/client/ClientPage.tsx, apps/admin-app/src/components/modals/SubscriptionModal.tsx</files>
  <action>
Rework `MembershipSchema` from the nested shape (`planSnapshot: MembershipPlanSchema` + `paidAmountKopecks`) to the FLAT shape the real GET /memberships?clientId= returns. Fields (camelCase, alias_generator=to_camel): `id`, `clientId`, `planId`, `planNameSnapshot` (string), `durationDaysSnapshot` (number), `priceKopecksSnapshot` (number), `startDate`, `endDate`, `status` (enum active|frozen|expired|cancelled), `cancelledAt` (nullable), `cancelReason` (nullable), `cancellationReason` (nullable), `paidAt` (nullable), `notes` (nullable), `createdAt`, `updatedAt`, `freezeDaysLimitSnapshot` (number), `freezeDaysUsed` (number), `freezeDaysRemaining` (nullable number), `currentFreezePeriod` (FreezePeriodSchema nullable), `previousMembershipId` (nullable). Mark genuinely-optional fields with `.nullable().optional()` to tolerate omissions; keep `FreezePeriodSchema` as-is. Drop the `MembershipPlanSchema` import if it becomes unused (ESLint noUnusedLocals will flag it). Keep `MembershipsListResponseSchema`, sell/cancel/refund input schemas unchanged.

Update `schemas.test.ts`: the `validMembership` / `minimal` fixtures and the «parses a valid membership with planSnapshot» assertions currently use `planSnapshot` + `paidAmountKopecks` — rewrite them to the flat shape (assert `result.planNameSnapshot` and `result.priceKopecksSnapshot`). This test is the fixture that hid the bug; it MUST assert the real wire shape now.

Update consumers (field rename only — money formatting handled in Task 3):
- `pages/client/ClientPage.tsx` MembershipsSection: `m.planSnapshot.name` → `m.planNameSnapshot`; the `formatRub(m.paidAmountKopecks)` becomes `formatRub(m.priceKopecksSnapshot)` for now (Task 3 swaps it to formatKopecks).
- `components/modals/SubscriptionModal.tsx`: update the local `MembershipPayload` type (`paidAmountKopecks` → `priceKopecksSnapshot`, `planSnapshot: { name }` → `planNameSnapshot: string`) and every read site (`membership.planSnapshot.name` → `membership.planNameSnapshot` in Renew/Freeze/Unfreeze/Cancel/Refund descriptions; `membership.paidAmountKopecks` → `membership.priceKopecksSnapshot` in the Refund button label + the two Refund StatRows). Keep `formatRub(...)` wrapping for now (Task 3 swaps).
- `features/memberships/api.ts`: the `useSellMembership` onSuccess uses `formatRub(data.paidAmountKopecks)` → `formatRub(data.priceKopecksSnapshot)` (Task 3 swaps to formatKopecks). `useFreezeMembership`/`useUnfreezeMembership` optimistic updaters spread `...m` and set `currentFreezePeriod`/`status` — those still typecheck against the flat shape; verify no field references the removed `planSnapshot`/`paidAmountKopecks`.

Grep the whole app for any remaining `planSnapshot`/`paidAmountKopecks` on the MEMBERSHIP domain and align — but DO NOT touch the PT-package domain (`features/pt-packages/schemas.ts`, `pages/client/components/TrainingsTab.tsx`, `BookingModal`), which have their own legitimate `planSnapshot`.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app test -- src/features/memberships/schemas.test.ts && pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>Open «Петров Иван» client page at :5173 — the active membership row («Месяц безлимит») renders with NO PageError in the memberships section.</human-check>
  </verify>
  <done>`MembershipSchema` is flat (planNameSnapshot/priceKopecksSnapshot/...); schemas.test.ts asserts the flat shape and passes; ClientPage + SubscriptionModal + memberships api reference only flat fields; typecheck + lint green; Петров membership row renders.</done>
</task>

<task type="auto">
  <name>Task 3 (BUG-3): money formatRub(kopecks) 100x — add formatKopecks</name>
  <files>apps/admin-app/src/lib/format.ts, apps/admin-app/src/lib/format.test.ts, apps/admin-app/src/pages/plans/PlansPage.tsx, apps/admin-app/src/pages/client/ClientPage.tsx, apps/admin-app/src/pages/client/components/PaymentsTab.tsx, apps/admin-app/src/pages/client/components/TrainingsTab.tsx, apps/admin-app/src/components/modals/SubscriptionModal.tsx, apps/admin-app/src/features/memberships/api.ts</files>
  <action>
`formatRub(value)` calls `RUB.format(value)` with NO division by 100, so call sites passing `*Kopecks` render 100× too high (5000₽ plan → «500 000 ₽»). Do NOT change `formatRub` behavior (cashbox + finance/dashboard charts already pass pre-divided rubles and are correct).

In `lib/format.ts`, add and export `formatKopecks(kopecks: number): string` that divides by 100 then formats: `RUB.format(kopecks / 100)`. Reuse the existing `RUB` Intl formatter. Add a JSDoc one-liner explaining it is for integer-kopecks call sites.

In `lib/format.test.ts`, add a `describe('formatKopecks')` block: `normalizeNbsp(formatKopecks(500000))` contains «5 000» and «₽» (i.e. 5000₽ stored as 500000 kopecks renders as 5 000 ₽). Keep the existing `formatRub` tests unchanged.

Switch ONLY these kopecks call sites from `formatRub(...)` to `formatKopecks(...)` (update the import on each file to include `formatKopecks`):
- `pages/plans/PlansPage.tsx`: `formatRub(plan.priceKopecks)` in MembershipPlanCard (~line 84) AND `formatRub(plan.priceKopecks)` in PtPackagePlanRow (~line 161).
- `pages/client/ClientPage.tsx`: `formatRub(m.priceKopecksSnapshot)` (renamed in Task 2) in MembershipsSection.
- `pages/client/components/PaymentsTab.tsx`: `formatRub(item.amountKopecks)` in PaymentRow (~line 63).
- `pages/client/components/TrainingsTab.tsx`: `formatRub(item.amountKopecks)` in PtPackageRow (~line 71).
- `components/modals/SubscriptionModal.tsx`: 4 sites — `formatRub(p.priceKopecks)` in the plan `<option>`; `formatRub(selectedPlan.priceKopecks)` in the «К оплате» StatRow; `formatRub(membership.priceKopecksSnapshot)` in the Refund button label; `formatRub(membership.priceKopecksSnapshot)` in the «Оплачено» Refund StatRow.
- `features/memberships/api.ts`: `useSellMembership` onSuccess `formatRub(data.priceKopecksSnapshot)` → `formatKopecks(data.priceKopecksSnapshot)` (update import).

Do NOT touch `formatRub` callers that already pass rubles: cashbox (CashboxKpis, TransactionsCard), finance RevenueChart/OnlinePaymentsTable, dashboard RevenueChart/KpiStrip/TopTrainers, reports trainers rows, trainer EarningsCard/PayoutsTab — these already divide by 100 themselves or store rubles. Removing the unused `formatRub` import on any file where it is no longer referenced (lint noUnusedLocals).
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app test -- src/lib/format.test.ts && pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>Open /plans at :5173 — «Месяц безлимит» shows «5 000 ₽» (NOT «500 000 ₽»). Open Петров client page — membership/payment amounts read in plausible rubles.</human-check>
  </verify>
  <done>`formatKopecks` exists + exported + unit-tested; the 9 named kopecks call sites use it; ruble call sites untouched; typecheck + lint + format.test green; Plans shows «5 000 ₽».</done>
</task>

<task type="auto">
  <name>Task 4 (BUG-4): schedule trainerId=undefined → 422</name>
  <files>apps/admin-app/src/pages/schedule/SchedulePage.tsx</files>
  <action>
On load, `useTrainerSlots({ trainerId: selectedTrainerId, fromTime, toTime })` fires with `selectedTrainerId === undefined` (filter defaults to 'all'). `useTrainerSlots` spreads `params as Record<string, string>` into the query, so `trainerId=undefined` is serialized as the literal string «undefined», and the backend returns 422 → PageError, even with a trainer present.

Backend requires a concrete `trainerId`. Fix at the SchedulePage level (do not edit backend, and prefer not to widen the hook contract): when the trainer filter is 'all', default-select the FIRST active trainer for the slots query instead of sending undefined. Concretely: derive `effectiveTrainerId = selectedTrainerId ?? trainers[0]?.id` and pass that to BOTH `useTrainerSlots` and `useBookingsByWeek` (keep client-side calendar filtering by `filters.trainer` unchanged for the 'all' display case — or, since only one trainer exists in single-club scope, the single trainer is the effective view).

Guard the no-trainers case: when `trainers.length === 0` (and trainersQuery is settled), do NOT fire the slots/bookings queries with an undefined trainerId — render a graceful empty state («Нет тренеров» / reuse the existing CalendarX EmptyState copy «Нет слотов на эту неделю») instead of crashing. The cleanest approach: compute `effectiveTrainerId`, and treat `effectiveTrainerId == null` as the empty-trainers branch (skip the data queries by leaving them disabled OR short-circuit to the empty state before the queries resolve). If you choose to gate the hook, you may need a minimal `enabled: !!effectiveTrainerId`-style guard; since `useTrainerSlots` does not currently expose `enabled`, the simpler path is the default-select-first-trainer approach which guarantees a concrete id whenever any trainer exists. Keep no-semicolon / single-quote style and the existing pending/error/empty/WeekCalendar structure.

Note: the seeded stack has trainer «Тренер Тестов», so the default-select path is the one exercised by UAT; the no-trainers branch is defensive.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint && pnpm -F @clubcore/admin-app test -- src/app/router-smoke.test.tsx</automated>
    <human-check>Open /schedule at :5173 as owner — the page renders (calendar or a clean empty state) with NO PageError and NO `GET /trainer-slots?trainerId=undefined` request (check Network tab — the slots request carries a real trainerId).</human-check>
  </verify>
  <done>Schedule never issues trainerId=undefined; it default-selects the first active trainer (or renders a graceful empty state when none exist); typecheck + lint + router-smoke green; /schedule renders.</done>
</task>

<task type="auto">
  <name>Task 5 (BUG-5): reports revenue + trainers schema reconciliation</name>
  <files>apps/admin-app/src/features/reports/schemas.ts, apps/admin-app/src/features/reports/schemas.test.ts, apps/admin-app/src/features/reports/utils.ts, apps/admin-app/src/features/reports/utils.test.ts, apps/admin-app/src/pages/reports/ReportsPage.tsx, apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx</files>
  <action>
Two divergences in the reports domain. Align frontend to the REAL wire shape; backend is authority (no backend edits).

(a) Revenue casing — `RevenueBucketSchema.bySubjectKind` has `pt_package` (snake) but backend sends `ptPackage` (camel, via to_camel alias). Change the field to `ptPackage: z.number()`. Cascade the rename:
   - `features/reports/utils.ts` ZERO_BUCKET (`bySubjectKind: { membership: 0, pt_package: 0 }` → `{ membership: 0, ptPackage: 0 }`).
   - `features/reports/utils.test.ts` — every `pt_package` literal in ZERO_SUBJECT and the sample buckets → `ptPackage`.
   No production component reads `bySubjectKind` for rendering (charts use `netKopecks`), so no page change for (a) beyond the schema/utils/test rename.

(b) Trainers report shape — `TrainersReportSchema` expects `data.rows[]` with `{ trainerId, name, sessionCount, totalHours, uniqueClients, utilizationPct: number, totalRevenueKopecks }`, but backend sends `data.trainers[]` with `{ trainerId, trainerNameSnapshot, sessionCount, cancelledSessionCount, totalHours, uniqueClientCount, utilizationPct: number|null, revenueKopecks, avgRevenuePerSession: number|null, totalAccruedKopecks, totalPaidKopecks }` and the parent object also carries `fromDate`, `toDate`, `revenueAttributionNote`.
   Rework `TrainerRowSchema` to: `trainerId` (string), `trainerNameSnapshot` (string), `sessionCount` (number), `cancelledSessionCount` (number), `totalHours` (number), `uniqueClientCount` (number), `utilizationPct` (z.number().nullable()), `revenueKopecks` (number), `avgRevenuePerSession` (z.number().nullable()), `totalAccruedKopecks` (number), `totalPaidKopecks` (number). Rework `TrainersReportSchema.data` to `{ trainers: z.array(TrainerRowSchema), fromDate: z.string(), toDate: z.string(), revenueAttributionNote: z.string() }`. Mark fields that may be omitted by older payloads with `.optional()` defensively where reasonable (keep nullable ones nullable). Export `TrainerRow`/`TrainersReportData` types unchanged in name.

   Update `schemas.test.ts` TrainersReportSchema block: rebuild the sample to `data.trainers[]` with the new field names (assert `result.trainers[0]?.trainerNameSnapshot` and `result.trainers[0]?.revenueKopecks`), the empty case to `{ data: { trainers: [], fromDate, toDate, revenueAttributionNote } }`, and add a case asserting `utilizationPct: null` parses. Keep the reportsQueryKeys tests unchanged.

   Update consumers:
   - `pages/reports/ReportsPage.tsx` TrainersTab + ReportsTrainerRow: `data.rows` → `data.trainers`; `row.name` → `row.trainerNameSnapshot`; `row.uniqueClients` → `row.uniqueClientCount`; `row.totalRevenueKopecks` → `row.revenueKopecks` (the `maxRevenue` calc + the bar + the `formatRub(row.totalRevenueKopecks / 100)` revenue cell — keep the existing `/100` since revenue is kopecks and this file is NOT in the BUG-3 swap list; render nullable `utilizationPct` as `{row.utilizationPct ?? 0}%` or «—» to avoid `null%`). Update the `TabsGroup`/`TrainersTab` query `data` type annotation from `{ rows: TrainerRow[] }` to `{ trainers: TrainerRow[] }` (plus the extra parent fields if referenced).
   - `pages/dashboard/components/TopTrainers.tsx`: `data?.rows` → `data?.trainers`; `trainer.name` → `trainer.trainerNameSnapshot`; `trainer.totalRevenueKopecks` → `trainer.revenueKopecks` (in sort, maxRevenue, barPct, and the `revenueRub` /100 calc — keep its existing `/100` Math.round logic); render nullable `utilizationPct` defensively (`{trainer.utilizationPct ?? 0}%`); `getInitials(trainer.name)` → `getInitials(trainer.trainerNameSnapshot)`.

   Verify the `TrainersReportData` type is also consumed correctly anywhere else (grep `data.rows`/`.rows` in reports/dashboard) and align. Keep no-semicolon / single-quote style; nullable numeric display must never emit literal «null».
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app test -- src/features/reports/schemas.test.ts src/features/reports/utils.test.ts && pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>As owner at :5173: open /reports → «Выручка» tab renders (5000₽ revenue) and «Тренеры» tab renders the trainer row. Open /finance — renders. Open the dashboard — «Выручка за 30 дней» and «Топ тренеры» show real (non-empty) data.</human-check>
  </verify>
  <done>Revenue uses `ptPackage`; trainers schema is the flat `data.trainers[]` shape with nullable utilizationPct/avgRevenuePerSession; schemas.test + utils.test pass; ReportsPage + TopTrainers read renamed fields and never render «null%»; typecheck + lint green; Отчёты/Финансы/dashboard render with seeded revenue.</done>
</task>

<task type="auto">
  <name>Task 6 (BUG-6): audit log nullable actor fields</name>
  <files>apps/admin-app/src/features/audit/schemas.ts</files>
  <action>
In `AuditEventSchema`, make `actorUserId` and `actorEmailSnapshot` nullable: `actorUserId: z.string().nullable()` and `actorEmailSnapshot: z.string().nullable()`. Real `login_success` rows send `actorEmailSnapshot: null`; system rows like `loyalty_accrued` send BOTH null. The current non-nullable strings make the audit log PageError on essentially every load (login events are ubiquitous).

Check the Wave-2 AuditPage consumer (`pages/settings/...` audit table) for any code that does `.toUpperCase()` / string ops directly on `actorEmailSnapshot` or `actorUserId` without a null guard; if present, add a `?? '—'` (or «Система» for null actor) fallback so the column renders gracefully. Grep `actorEmailSnapshot`/`actorUserId` across pages to confirm. Keep no-semicolon / single-quote style.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>As owner at :5173: open /settings → «Журнал действий» (audit) — seeded events (including login_success / loyalty_accrued with null actor) render with NO PageError.</human-check>
  </verify>
  <done>`actorUserId` + `actorEmailSnapshot` are nullable; the audit consumer null-guards display; typecheck + lint green; Журнал действий renders the seeded events.</done>
</task>

<task type="auto">
  <name>Task 7 (BUG-7): sessions userAgent null</name>
  <files>apps/admin-app/src/features/settings/schemas.ts</files>
  <action>
In `SessionSchema`, change `userAgent: z.string()` to `userAgent: z.string().nullable()`. Real sessions return `userAgent: null` (e.g. API-channel sessions), which makes the Active Sessions widget error and blocks the revoke / self-revoke flow.

Check the Active Sessions consumer (the settings security/sessions section) for direct string ops on `userAgent`; if it renders the value, add a `?? 'Неизвестное устройство'` (or «—») fallback so a null device label renders gracefully. Grep `userAgent` across pages/features to confirm. Keep no-semicolon / single-quote style.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>As owner at :5173: open Настройки → «Активные сессии» — the sessions list renders (current session + any null-userAgent rows) with NO error; the revoke control is reachable.</human-check>
  </verify>
  <done>`userAgent` is nullable with a graceful display fallback; typecheck + lint green; Active Sessions widget renders.</done>
</task>

<task type="auto">
  <name>Task 8 (BUG-8): check-in onMutate crash on gym-meta cache entry</name>
  <files>apps/admin-app/src/features/visits/api.ts</files>
  <action>
`useCheckIn.onMutate` calls `qc.getQueriesData<VisitsListPage>({ queryKey: visitsKeys.all })`. Because `visitsKeys.meta() = [...visitsKeys.all, '_meta']` is also under `visitsKeys.all`, the snapshot loop also matches the gym-meta query, whose cached data has no `.items`. The optimistic loop `{ ...data, items: [optimisticRow, ...data.items] }` throws `TypeError: data.items is not iterable` BEFORE `mutationFn` runs, so the POST never fires and check-in is completely non-functional via the UI (always shows the generic «Не удалось выполнить чек-ин»).

Guard the setQueryData loop in `onMutate`: skip cache entries that are not list pages. Replace the current `if (!data) continue;` with `if (!data || !Array.isArray((data as { items?: unknown }).items)) continue;` so meta entries (no `.items` array) are skipped. Apply the SAME guard to the `onError` rollback loop (it currently iterates `ctx.allSnapshots` and calls `qc.setQueryData(key, data)` — meta entries were never mutated so restoring their original `data` is harmless, but guarding keeps the two loops symmetric and avoids restoring a stale meta snapshot; at minimum ensure the rollback does not assume `.items`). Optionally also scope the snapshot to `visitsKeys.lists()` + `byClient` instead of `visitsKeys.all`, but the Array.isArray guard is the minimal, surgical fix and preserves the existing CR-03 cancel/invalidate-on-`visitsKeys.all` behavior. Keep no-semicolon / single-quote style and the existing optimistic-row shape.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint && pnpm -F @clubcore/admin-app test -- src/features/visits</automated>
    <human-check>At :5173 open the check-in flow (CheckInModal) and check in a client who has NO visit today (use the dev client or create a fresh client — «Петров Иван» already has a today-visit and would 409 «Уже отмечен сегодня»). Expect the «Визит зафиксирован» success toast and a recorded visit (confirm a POST /api/v1/visits fired in Network → 201).</human-check>
  </verify>
  <done>onMutate (and onError rollback) skip non-list cache entries via Array.isArray(data.items); the POST fires; typecheck + lint + visits tests green; a UI check-in of a no-visit client succeeds with «Визит зафиксирован».</done>
</task>

<task type="auto">
  <name>Task 9 (UX-1): localize phone_exists 409 on client create</name>
  <files>apps/admin-app/src/components/modals/NewClientModal.tsx</files>
  <action>
Duplicate-phone client create returns backend 409 `{ code: 'phone_exists' }`. The current `onError` handler in NewClientModal only special-cases `forbidden` and `err.fields` (422); a 409 with code `phone_exists` and no `fields` falls through to `toast.error(err.message || ...)`, surfacing the raw code «phone_exists» (the message body) to the user.

In the `useCreateClient` `onError` ApiError branch, add a case BEFORE the generic fallback: when `err.code === 'phone_exists'`, set an inline field error on the phone field (preferred — `setFieldErrors({ phone: 'Клиент с таким телефоном уже существует' })`) so it shows under the Телефон input like the 422 path. (A `toast.error('Клиент с таким телефоном уже существует')` is an acceptable fallback if inline placement is awkward, but inline-on-phone is the better UX and the field+hint plumbing already exists via `fieldErrors.phone`.) Keep the existing `forbidden` and `err.fields` (422) branches; the new `phone_exists` branch must be checked explicitly because a 409 may carry no `fields`. Russian copy, no semicolons, single quotes.
  </action>
  <verify>
    <automated>pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint</automated>
    <human-check>At :5173 open «Новый клиент», submit a phone that already exists (e.g. «Петров Иван» +79991112201). Expect the localized «Клиент с таким телефоном уже существует» under the Телефон field (or as a toast) — NOT the raw «phone_exists».</human-check>
  </verify>
  <done>409 phone_exists maps to the localized «Клиент с таким телефоном уже существует» (inline on phone field preferred); typecheck + lint green; duplicate-phone create shows the localized message.</done>
</task>

</tasks>

<verification>
After all 9 tasks:

```bash
pnpm -F @clubcore/admin-app typecheck
pnpm -F @clubcore/admin-app lint
pnpm -F @clubcore/admin-app test
```

All three must be green. The test suite must pass with the UPDATED fixtures (memberships flat shape, reports ptPackage casing + trainers[] shape, formatKopecks) — not the old mock shapes.

Live smoke (owner@clubcore.dev / devpassword12345 at :5173, stack running):
- /clients list + a client detail render (BUG-1)
- «Петров Иван» membership row renders (BUG-2)
- /plans shows «5 000 ₽» (BUG-3)
- /schedule renders, no trainerId=undefined request (BUG-4)
- /reports Выручка + Тренеры render; /finance renders; dashboard Выручка + Топ тренеры show real data (BUG-5)
- /settings Журнал действий renders (BUG-6)
- Настройки Активные сессии render (BUG-7)
- UI check-in of a no-visit client → «Визит зафиксирован» (BUG-8)
- duplicate-phone create → localized message (UX-1)
</verification>

<success_criteria>
- All 8 bugs + UX-1 fixed, frontend-only, no backend edits.
- Each task committed separately (atomic, one bug per commit).
- `typecheck` + `lint` + `test` green with fixtures updated to the REAL wire shapes (so the divergence that hid these bugs can no longer re-hide them).
- Every named live screen renders against the running stack without a PageError, and the named functional flows (check-in success, duplicate-phone message) work.
- No scope creep into GAP-1, the delete-client hero stub, or mock chrome.
</success_criteria>

<output>
Create `.planning/quick/260614-hux-fix-v3-0-admin-app-live-uat-bugs-8-fe-sc/260614-hux-SUMMARY.md` when done.
</output>
