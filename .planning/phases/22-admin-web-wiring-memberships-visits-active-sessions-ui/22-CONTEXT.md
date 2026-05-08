# Phase 22: admin-web wiring — memberships + visits + active sessions UI - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 22 wires the admin-web SPA to the live v1.2 backend surface (Phases 16/17/19) on `VITE_API_MODE=http`, ships Pattern α composition on a new client-detail route, ships the reception check-in page with all FE-08 edge cases, lands the cheap-win differentiators D-2/D-3/D-5, and (sequenced after Phase 23) ships the active-sessions UI. The schema.d.ts that Phase 21 froze is the typed transport for memberships/visits/membership-plans paths — Phase 22 is the consumer.

**In scope (the deliverables that flip FE-04..FE-11 and ROADMAP SC#1..SC#5):**

- **NEW** `apps/admin-web/src/features/memberships/{api,components,model,index.ts}` — `useMembershipsByClient`, `useMembershipPlans`, `useCreateMembership`, `useCancelMembership` hooks; `<MembershipsBlock>` component (used by client-detail Pattern α); `<SellMembershipDialog>` component; `MembershipsListPage` (with D-2 "expiring within 7 days" filter); `MembershipPlansPage` (owner-only catalog CRUD UI). All hooks consume `services.memberships.*`. (FE-04, FE-10/D-2)
- **NEW** `apps/admin-web/src/features/visits/{api,components,model,index.ts}` — `useRecentVisitsByClient`, `useGymMeta`, `useCheckIn` hooks; `<RecentVisitsBlock>` component (used by client-detail Pattern α); `CheckInPage` route component implementing all four FE-08 edge cases (a..d). (FE-05, FE-08)
- **NEW** routes `apps/admin-web/src/routes/_protected/membership-plans.tsx` (owner-only `beforeLoad` mirror of `clients.tsx:14-23`), `memberships.tsx`, `visits.tsx` (pure check-in page — see D-22-3), and `clients.$clientId.tsx` (Pattern α stacked-blocks layout). All loaders use `queryClient.ensureQueryData` with the same key as the consuming hook (no waterfall, no double-fetch). (FE-06, FE-07)
- **NEW** `apps/admin-web/src/shared/api/contracts/memberships.ts`, `contracts/visits.ts`, `contracts/visitsMeta.ts` — TypeScript interfaces (`MembershipsService`, `MembershipPlansService`, `VisitsService`) + Zod schemas reused by RHF forms and mock validators.
- **NEW** `apps/admin-web/src/shared/api/services/{mock,http}/memberships.ts`, `visits.ts` — mock impls are READ-ONLY (D-22-7); http impls are full surface; both gated through the existing `services` swap-seam.
- **NEW** backend slice — `GET /api/v1/visits/_meta` endpoint (D-22-1) — returns `{gymHoursStart, gymHoursEnd}` as HH:MM strings, gated by `Depends(require_permission(view, visits))`, cacheable. Forces openapi.json + schema.d.ts re-codegen as part of Wave 1 of Phase 22 plan, before any FE plan that imports `paths['/api/v1/visits/_meta']`.
- **MODIFY** `apps/admin-web/src/shared/session/registry.ts` — extend `routeRegistry` with three new entries (Отметки/`/visits`/`LogIn`, Абонементы/`/memberships`/`Ticket`, Тарифы/`/membership-plans`/`LayoutGrid`) in reception-first order (D-22-4); extend `RouteEntry.navKey` enum if needed.
- **MODIFY** `apps/admin-web/src/shared/session/registry.ts` + `apps/admin-web/src/components/AppShell` (or `shared/ui/app-shell/Sidebar.tsx`) — sidebar filters out owner-only entries when `can(role, 'view', resource)===false` (already the existing pattern for /finance/settings; reused unchanged for /membership-plans).
- **MODIFY** `apps/admin-web/src/features/clients/components/ClientsTable.tsx` — row click navigates to `/clients/$clientId` via `<Link>`; inline edit/delete buttons stay row-local with `event.stopPropagation()`. (D-22-5)
- **MODIFY** `apps/admin-web/eslint.config.js` — extend `import/no-restricted-paths` zones to forbid `features/clients/**` from importing `features/memberships/**` or `features/visits/**` (Pattern α enforcement). NEW negative-test fixtures `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts` mirroring the existing `illegal-mock-import.ts` precedent. (FE-11)
- **MODIFY** `apps/admin-web/.env.example` — no env additions needed (gym hours come from `/visits/_meta`, not from VITE_GYM_HOURS_*).
- **NEW (deferred sub-plan, post-Phase-23 merge)** `apps/admin-web/src/features/auth/components/SessionsList.tsx` + `useActiveSessions` + `useRevokeSession` hooks consuming `paths['/api/v1/auth/sessions']` and `paths['/api/v1/auth/sessions/{family_id}/revoke']` once the Phase 23 codegen lands. The settings/profile page gets a "Активные сессии" section. The "Выйти со всех устройств" button reuses existing `/api/v1/auth/logout-all`. (FE-09 — ordered LAST inside Phase 22; depends on Phase 23 landing in main first.)
- Backend Phase 22 surface (the `/visits/_meta` slice above) bumps `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` once. Existing CI drift gates enforce the regeneration commit (Phase 21 D-21-* invariants hold).
- Cheap-win differentiators **D-3** (red badge "истёк сегодня" inside `<MembershipsBlock>` on `/clients/$clientId`) and **D-2** ("expiring within 7 days" filter chip on `/memberships` list) ship in this phase. **D-5** (Telegram bot success DM with days-remaining) is a backend-only addition to the existing `/checkin` handler — landed within Phase 22 as a small tweak to `apps/backend/app/integrations/telegram/handlers.py` (a one-line interpolation into the success DM constant + an audit-event addendum if needed).

**Out of scope (explicitly deferred):**

- **Membership-plans full CRUD UX polish** — owner-only `/membership-plans` route ships with a working list + create/edit dialog, but advanced features (price-history audit, bulk reactivate, plan archetype templates) are v1.3+. The Phase 22 deliverable is only what MEM-PLAN-EP-* surfaces in REQUIREMENTS.
- **Mock parity for memberships+visits write operations** — D-22-7: mocks are READ-ONLY; create/cancel/check-in throw `DomainError('mock_not_implemented')`. Storybook-quality offline demos for the v1.2 surface are deferred to v1.3+ if a real ops use case (e.g. customer demo without backend) appears.
- **Membership renewal flow / freeze / visit-count plans** — REQUIREMENTS "Future Requirements (deferred to v1.3+)" already lists these; surfaced here only because they would be natural UX additions on `/clients/$clientId`.
- **Photo turnstile / geofencing / per-class booking integration** for visits — same as above, locked v1.3+.
- **D-1, D-4, D-6, D-7 cheap-win differentiators** — FE-10 explicitly defers them.
- **Active-sessions UI without Phase 23** — D-22-2: FE-09 is a sub-plan that runs ONLY after Phase 23 has merged into main. If Phase 23 has not merged when Phase 22's other plans complete, FE-09 ships as a follow-up commit/PR within Phase 22's scope (the phase doesn't close until FE-09 lands), but the memberships/visits/check-in plans do NOT block on Phase 23. Phase 22 verification gates on FE-09 being green; if Phase 23 slips badly, the user re-evaluates whether to punt FE-09 to v1.3 — but the default is to wait for Phase 23.
- **Backend route extensions for `/visits/_meta` beyond `{gymHoursStart, gymHoursEnd}`** — no `nowMsk`, no `maxCheckinPerDay`, no `channelsEnabled`. Static, cacheable response. v1.3+ may add `nowMsk` if reception PCs prove to have bad NTP.
- **Tabbed or two-column layout** on `/clients/$clientId` — D-22-6: stacked blocks only (mobile-friendly, no search-param tab routing).
- **Bulk client-import / CSV / photo upload** on `/clients` — out of v1.2 entirely.
- **Standalone `/memberships` "+ Продать" toolbar dialog** — D-22-8: "Продать абонемент" lives ONLY inline on `/clients/$clientId`. The `/memberships` list gets the D-2 filter and a row-level owner-only cancel control, but no global "+ sell" entry point.
- **Real auth UX for /login** — Phase 11 scope. Phase 22 only adds the SessionsList component to the existing settings/profile area.
- **Backend changes outside `/visits/_meta` + the D-5 DM tweak** — Phase 22 leaves the rest of `apps/backend/app/**` untouched.

</domain>

<decisions>
## Implementation Decisions

### Gym-hours source (FE-08d)

- **D-22-1: NEW backend endpoint `GET /api/v1/visits/_meta`** returning `{gymHoursStart: "07:00", gymHoursEnd: "23:00"}` as HH:MM strings (matching `time.isoformat()` already used in `OutsideGymHoursError.fields`). Auth: `Depends(require_permission(view, visits))` — reception+owner. Response is cacheable: `Cache-Control: public, max-age=300`. Lives in `apps/backend/app/modules/visits/router.py` next to the existing visits routes; uses the validated `BusinessService` template. NO `nowMsk` field, NO `maxCheckinPerDay`, NO `channelsEnabled`. The only data the FE needs is the gym-hours window for the FE-08(d) "outside hours" disable + tooltip.
  - **Implementation order:** This backend slice MUST land in Wave 1 of Phase 22's plan, ahead of any FE plan that imports `paths['/api/v1/visits/_meta']`. The drift gate forces the codegen commit before FE plans typecheck. Mid-phase regeneration of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` is expected and follows the Phase 21 D-21-* byte-stable invariants verbatim.
  - **Trade-off accepted:** Local time skew on a reception PC could leave the button enabled when the server would 409. Acceptable because (a) the worst case is a single 409 + sonner toast surfacing the gym-hours range; (b) gyms are not a high-volume environment where 1-2 retries matter; (c) `nowMsk` would force `Cache-Control: no-cache` and lose cacheability for a marginal benefit.

### Active-sessions UI (FE-09) sequencing vs Phase 23

- **D-22-2: FE-09 ships as the LAST sub-plan inside Phase 22, ordered AFTER Phase 23 merges into main.** Verified at discuss-phase: `packages/api-client/src/schema.d.ts` does NOT include `/api/v1/auth/sessions` or `/api/v1/auth/sessions/{family_id}/revoke` (`grep "/auth/sessions" packages/api-client/src/schema.d.ts` — only `/auth/logout-all` matches; sessions paths are absent). Phase 23 owns these endpoints (HYG-03). Phase 22's other plans (memberships, visits, check-in, Pattern α, sidebar, ESLint, D-2/D-3) do NOT block on Phase 23 and proceed in parallel.
  - **Trade-off accepted:** Phase 22 cannot close until FE-09 lands. If Phase 23 slips beyond the v1.2 milestone deadline, the user re-evaluates: punt FE-09 to v1.3 (REQUIREMENTS update + ROADMAP SC#4 amendment) OR accept the delay. Default at discuss-phase: WAIT for Phase 23. Plan-phase agent sequences FE-09 as a "blocked by Phase 23 main merge" plan with an explicit dependency note.
  - **No mock-only fallback for FE-09.** The active-sessions UI doesn't usefully run on `VITE_API_MODE=mock` because the value is auditing real refresh-rotation families, not demoing a pretty list. Skip the mock impl; the http impl is the deliverable.

### Sidebar / routes layout (FE-06 + UX)

- **D-22-3: `/_protected/visits.tsx` is a PURE check-in page.** Search clients by phone-prefix (top-5 disambiguation per FE-08a) → "Отметить" button (disabled per FE-08b/c/d) → success toast. The page does NOT include a global "today's check-ins" feed. Per-client visit history lives ONLY on `/clients/$clientId` (`<RecentVisitsBlock>`). Reception's audit reconciliation use case (rare, end-of-day) is handled by the Phase 16-style audit log query that's already deferred to v1.3 — Phase 22 does not pre-empt it.
  - **Why not "tabs Отметить / История":** doubles the route surface for a feature reception uses 100x more for check-in than for history. The audit feed is a separate concern, deferred. Single-purpose `/visits` keeps the page snappy and the loader trivial.

- **D-22-4: Sidebar order — reception-first.** Final `routeRegistry` after Phase 22:
  1. `/` — Главная (LayoutDashboard)
  2. `/visits` — Отметки (LogIn)  ← NEW
  3. `/clients` — Клиенты (Users)
  4. `/memberships` — Абонементы (Ticket)  ← NEW
  5. `/membership-plans` — Тарифы (LayoutGrid)  ← NEW (owner-only — filtered out for reception)
  6. `/schedule` — Расписание (CalendarDays)
  7. `/staff` — Сотрудники (UserCog)
  8. `/finance` — Финансы (Wallet)
  9. `/settings` — Настройки (Settings)
  - Owner-only entries (`/finance`, `/settings`, `/membership-plans`) are filtered out for reception by the existing sidebar render rule that consults `can(role, 'view', resource)`. No new sidebar component logic — the existing pattern (Phase 11 Sidebar.tsx) handles this automatically once the registry entries land.
  - `RouteEntry.navKey` may need extension (currently constrained to `'home' | 'clients' | 'schedule' | 'staff' | 'finance' | 'settings'`). Plan-phase agent decides whether to add `'visits' | 'memberships' | 'membership-plans'` enum members or relax the type — both are valid; the i18n dictionary `src/shared/i18n/ru.ts` will gain matching `shell.nav.visits` / `shell.nav.memberships` / `shell.nav.membershipPlans` keys.

- **D-22-5: `/clients` row click navigates to `/clients/$clientId`.** `<ClientsTable>` rows wrap in TanStack Router `<Link to="/clients/$clientId" params={{clientId: c.id}}>` (or programmatic `navigate({to})`). Inline edit/delete action buttons remain row-local; their click handlers stop propagation so they don't navigate. Test fixture: existing `ClientsTable.rbac.test.tsx` extended with a navigation assertion.

### Pattern α composition (FE-07)

- **D-22-6: `routes/_protected/clients.$clientId.tsx` uses STACKED BLOCKS layout.**
  ```
  <ClientDetailPage>
    <ClientProfileCard client={data.client} />        ← inline edit hooks here
    <MembershipsBlock clientId={id}>                  ← from features/memberships
      <SellMembershipCTA clientId={id} />             ← inline button (D-22-8)
      [list rows: snapshot name, period, status badge,
        D-3 "истёк сегодня" red badge,
        owner-only Cancel button per row]
    </MembershipsBlock>
    <RecentVisitsBlock clientId={id} />               ← from features/visits
  </ClientDetailPage>
  ```
  - Loader: `Promise.all([ensureQueryData(clientsKeys.detail(id)), ensureQueryData(membershipsKeys.byClient(id)), ensureQueryData(visitsKeys.recentByClient(id, {limit:20}))])`. NO waterfall. Same keys as the `useClient`/`useMembershipsByClient`/`useRecentVisitsByClient` hooks consume.
  - `features/clients` does NOT import `features/memberships` or `features/visits`. The Pattern α composition lives in the ROUTE file (`clients.$clientId.tsx`), not in `features/clients`. ESLint negative-test fixture proves this.
  - No tabs, no two-column layout. Mobile renders the same stacked order. shadcn `<Card>` + spacing tokens.

### Membership selling UX (MEM-EP-03)

- **D-22-8: "Продать абонемент" lives ONLY inline on `/clients/$clientId`.** Top of `<MembershipsBlock>` renders a `<Button>Продать абонемент</Button>` that opens a shadcn `<Dialog>`:
  - Plan select (populated from `useMembershipPlans()` filtered to `active=true`)
  - Optional `paidAt` (defaults to now, manual today; ЮKassa in v1.3)
  - Optional `notes`
  - Submit → `useCreateMembership({clientId, planId, paidAt, notes})` → optimistic add to the block + sonner toast.
  - Reception is NOT redirected to a "/sell" page — they stay on the client profile. The dialog lives inside the client-detail context.
  - `/memberships` list page does NOT have a global "+ Sell" toolbar entry. The list is purely browse + D-2 filter + owner-only inline cancel. (Reasoning: walk-in flow is "open client → sell" which is shorter via the inline CTA. A bulk-sell flow is a v1.3+ ops scenario, not a Phase 22 concern.)

### Membership cancel UX (MEM-EP-04, owner-only)

- **CD-04 (default to apply): Cancel button is per-row, owner-only, gated by `<RoleGate>` or `can(role, 'cancel', 'memberships')`.** Rendered inline on each `<MembershipsBlock>` row (on `/clients/$clientId`) AND on each row of the `/memberships` list page. Click → confirm dialog with optional `reason` text → `useCancelMembership({membershipId, reason})` → optimistic status flip + toast. Reception sees no cancel UI at all (button is hidden, not greyed; mirrors Phase 11 RoleGate convention).

### Cheap-win differentiators (FE-10)

- **D-22-9: D-3 "истёк сегодня" red badge** lives in `<MembershipsBlock>` on `/clients/$clientId` (NOT in the `/clients` list page — that page only shows phone/name; no membership state). Trigger: row's `endDate === todayMSK && status === 'active'`. Render: shadcn `<Badge variant="destructive">истёк сегодня</Badge>` next to the period text. The check uses a `todayMSK()` helper from `shared/i18n/date.ts` (Europe/Moscow TZ pin). FE-10 wording "in client list memberships block" is interpreted as "the memberships-block component embedded on the client-detail page", consistent with Pattern α.
- **D-22-10: D-2 "expiring within 7 days" filter on `/memberships` list page** — implemented as a URL-search param `?expiring=true` toggle in the page toolbar, mirroring the v1.1 `/clients?q=...` URL-driven pattern. Default OFF (shows all). When ON, the loader filters server-side via `GET /api/v1/memberships?expiringWithinDays=7` (the backend `MEM-EP-01` doesn't explicitly enumerate this filter — plan-phase agent verifies whether to extend the endpoint, OR filter client-side in the React Query selector. Default: client-side filter using returned `endDate` to avoid a Phase 22 backend-route change. If perf becomes a concern at v1.3+ scale, promote to a backend filter.)
- **D-22-11: D-5 "Telegram bot success DM includes days-remaining"** — backend-only one-line tweak inside `apps/backend/app/integrations/telegram/handlers.py` `_DM_SUCCESS` (or equivalent) constant. The locked Russian DM string from Phase 20 (AUTH-TG-11) gains a `{days_remaining}` interpolation. Owner sign-off on the new locked string is REQUIRED per Phase 20 precedent — plan-phase agent surfaces the exact new copy at execution time. The handler computes `days_remaining = (active_membership.end_date - today_msk).days` (inclusive end_date convention).

### ESLint Pattern α enforcement (FE-11)

- **D-22-12: Extend `apps/admin-web/eslint.config.js` `import/no-restricted-paths` rules** with a new zone:
  ```js
  {
    target: ['./src/features/clients/**'],
    from: ['./src/features/memberships/**', './src/features/visits/**'],
    message: 'Pattern α: features/clients must not import features/memberships or features/visits. Compose at the route level (clients.$clientId.tsx).'
  }
  ```
  - **NEW negative-test fixture** `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts` mirroring the existing `__fixtures/features/illegal-mock-import.ts` precedent. The fixture lives under `__fixtures/` which is in `eslint.config.js` `ignores: [...]` — but the FE-11 verification step temporarily un-ignores it and runs ESLint to confirm the rule fires. Existing v1.1 verification harness handles this; plan-phase agent surfaces the exact mechanism.

### Mock-vs-http parity for new domains (FE-04, FE-05)

- **D-22-7: Mock impls are READ-ONLY** — `services.memberships.list`, `services.memberships.byClient`, `services.memberships.listPlans`, `services.visits.recentByClient`, `services.visits.gymMeta` return seeded fixtures (faker.seed(42), localStorage `sportzal:mock:v1`-namespaced). Mutations `services.memberships.create`, `services.memberships.cancel`, `services.visits.checkIn` throw `DomainError('mock_not_implemented', 'Mock does not implement write paths — use VITE_API_MODE=http')`. RBAC enforcement is preserved on read paths (mocks throw `DomainError('forbidden')` when `can(role, 'view', resource)===false`).
  - **Why not full parity:** The v1.2 lifecycle is non-trivial (snapshot-on-create, INCLUSIVE end_date, 1/day visits, gym-hours window, owner-only cancel). Full mock parity would be a 2-3 day plan all on its own (~MEM-04 resolver, MEM-EP-04 transition guard, VIS-01 unique constraint replicas in localStorage). The production target is `VITE_API_MODE=http`. Read-only mock + http-only mutations gives us: storyboard-grade `<MembershipsBlock>` / `<RecentVisitsBlock>` for unit tests, full http-mode integration coverage for write paths (Phases 16/17/19 already have backend tests), and zero risk of mock-vs-http behavioral drift on the high-stakes mutation paths.
  - **Why not minimal stubs:** Read-only with seeded fixtures gives us realistic Faker data for Storybook/dev runs and lets `<MembershipsBlock>` UI tests render against real-shape data. Pure stubs (3-5 hand-written rows) would lose this property.
  - **Test coverage:** mocks get `memberships.read.test.ts` and `visits.read.test.ts` covering: (a) shape parity with the http impl's typed return, (b) RBAC denial on owner-only paths from reception role, (c) mutation methods throw `mock_not_implemented`. NO behavioral tests for create/cancel/check-in on the mock side.

### Plan layout (Claude's discretion — finalised at `/gsd-plan-phase`)

- **CD-01 (default to apply): Phase 22 splits into 5 sub-plans.** Suggested cut:
  1. `22-01-PLAN.md` — Backend `/visits/_meta` endpoint + openapi.json + schema.d.ts re-codegen + contract test extension. Wave 1 (must land first; everything below imports from `paths['/api/v1/visits/_meta']`).
  2. `22-02-PLAN.md` — `features/memberships` (api hooks + keys + `<MembershipsBlock>` + `<SellMembershipDialog>` + `MembershipsListPage` with D-2 + `MembershipPlansPage` owner-only) + contracts/services/{mock,http}/memberships.ts + routes `/_protected/memberships.tsx` + `/_protected/membership-plans.tsx` + sidebar registry extensions for these two.
  3. `22-03-PLAN.md` — `features/visits` (api hooks + keys + `<RecentVisitsBlock>` + `CheckInPage` with all FE-08(a..d) edge cases) + contracts/services/{mock,http}/visits.ts + route `/_protected/visits.tsx` + sidebar registry extension for /visits.
  4. `22-04-PLAN.md` — Pattern α: NEW route `routes/_protected/clients.$clientId.tsx` (stacked-blocks layout) + ClientsTable row-click navigation + ESLint cross-feature import zone + negative-test fixture + D-3 badge in `<MembershipsBlock>` + D-5 Telegram DM days-remaining tweak (owner sign-off on new locked string).
  5. `22-05-PLAN.md` — FE-09 SessionsList + useActiveSessions + useRevokeSession + Logout-all button + settings/profile integration. **Blocked on Phase 23 main merge.** Plan-phase agent flags this dependency explicitly. If Phase 23 is already merged when Phase 22 starts, this plan can run in parallel with 22-02..22-04.
  - Plans 22-02 and 22-03 are parallel-eligible (no shared files; both touch their own feature dir + their own service impls + their own route file). Plan 22-04 depends on 22-02 + 22-03 (imports from features/memberships and features/visits at the route level). Plan 22-05 is independent of 22-02..22-04.
- **CD-02 (default to apply): Atomic-commit-per-task** — same precedent as v1.1 + Phase 21 CD-02. The executor agent does this by default.
- **CD-03 (default to apply): No Storybook stories shipped in Phase 22** — the read-only mock gives us real-shape data for unit tests; Storybook setup is a v1.3+ concern if visual regression becomes a need.

### Defaults if user says nothing at plan-phase review

All `D-22-*` decisions above are LOCKED by this discussion. `CD-*` are Claude's discretion at plan-phase. User overrides at plan-phase review by saying e.g. "actually, full mock parity for memberships (revert D-22-7)" — the planner reflects the change in the relevant `22-NN-PLAN.md` before execution.

### Locked-not-discussed (carried verbatim from PROJECT / REQUIREMENTS / Phase 9-21 decisions)

- **Swap-seam pattern** (CLAUDE.md "Swap seam" rule + Phase 10 D-?): `UI → TanStack Query hook → services.X → { mock | http } impl`. Phase 22 NEW services follow verbatim.
- **Pagination envelope `{items, total, page, pageSize}`** (Phase 4 D-?). Membership list, visits list, plans list — all paginated. Mock fixtures honour the envelope.
- **Money in integer kopecks** + `formatMoney()` helper (`src/shared/lib/money.ts`). All membership snapshot prices and plan prices.
- **Dates as ISO strings** in domain types; display via date-fns `ru` locale + Europe/Moscow TZ pin. Never `new Date(dateOnlyString)`. INCLUSIVE end_date semantics (Phase 15) are honoured at display time ("действует до DD.MM.YYYY включительно" or just date — UX detail at plan-phase).
- **Branded UUIDv4 IDs** — `MembershipId`, `MembershipPlanId`, `VisitId` types in entities/membership/types.ts and entities/visit/types.ts (NEW entity directories — plan-phase decides whether one entity per type or grouped).
- **camelCase wire format** (Phase 4 D-21) — schema.d.ts already emits `gymHoursStart`, `endDate`, `clientId`, `pageSize`, etc. FE consumes these verbatim; no manual snake_case conversion.
- **Russian-only UI** + single `src/shared/i18n/ru.ts` dictionary. NEW shell.nav keys: `shell.nav.visits = "Отметки"`, `shell.nav.memberships = "Абонементы"`, `shell.nav.membershipPlans = "Тарифы"`. NEW domain dictionary entries for membership status labels, action verbs, error codes from `DomainError`.
- **Semantic shadcn tokens only**, raw palette banned (ESLint `no-restricted-syntax` rule). Phase 22 components use `bg-card`, `text-foreground`, `border-border`, `bg-destructive` (for D-3 red badge — `<Badge variant="destructive">`), etc.
- **react-hook-form + Zod via @hookform/resolvers** for the SellMembership dialog. Same Zod schema validates the form AND the mock service input (per CLAUDE.md "Domain types" rule).
- **TanStack Query hygiene** (CLAUDE.md): per-feature `xKeys` factory, `staleTime: 30_000`, `refetchOnWindowFocus: false`, optimistic mutations with `onMutate/onError/onSettled`, route loader uses `queryClient.ensureQueryData` with the SAME key as the hook.
- **RBAC three-way parity** (Phase 15 INFRA-08, TESTS-08): `Resource.{memberships, membership-plans, visits}` already in `apps/admin-web/src/shared/session/registry.ts` lines 13-15 + `OWNER_ONLY` matrix in `can.ts` lines 22-28 (verified at discuss-phase). Phase 22 does NOT extend the RBAC enums; it consumes them.
- **CSRF on mutating methods** — `fetcher.ts` D-11 already attaches `X-CSRF-Token` to non-GET. Phase 22 does NOT touch fetcher.ts.
- **Drift gates green at PR merge** — Phase 21 CD-03 + Phase 9 CI invariants. Phase 22's `/visits/_meta` slice forces a regeneration commit; everything else regenerates trivially (no drift expected from FE-only changes).
- **`features/clients` does NOT import `features/memberships` or `features/visits`** — Pattern α core invariant; ESLint enforces (FE-11 / D-22-12).
- **All loaders use `queryClient.ensureQueryData` with same key as the consuming hook** — FE-06 wording is verbatim and locked.
- **Owner-only `beforeLoad` gate mirrors `clients.tsx:14-23`** — exact source location for plan-phase verbatim copy.
- **Mock latency 120-300ms simulated** + configurable failure rate (CLAUDE.md "Mock realism" rule) — apply to NEW mock methods consistently.
- **Versioned localStorage keys** — `sportzal:mock:v1` namespace already covers v1.1 + v1.2 mock data; Phase 22 does NOT bump the version.
- **No new feature flags / dev-only branches** — `VITE_API_MODE` is the only switch; no `VITE_FEATURE_MEMBERSHIPS=on` style flag.
- **No fetcher.ts edits** — Phase 21 explicitly out-of-scoped these. Phase 22 inherits the contract.
- **`packages/ui` placeholder remains** — PROJECT.md still says "placeholder". Phase 22 does NOT promote it.
- **`apps/client-web` is Phase J territory** — Phase 22 only touches `apps/admin-web`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — pinned РФ/СНГ stack + camelCase wire format Key Decision (Phase 4) + Pagination envelope Key Decision (Phase 4) + INCLUSIVE end_date Key Decision (Phase 15) + `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` Key Decision (Phase 15) + Phase 21 D-21 row.
- `.planning/REQUIREMENTS.md` §"Frontend Wiring — admin-web (Phase 22)" — FE-04 through FE-11 verbatim. The requirements-status table at file end (rows `FE-04..FE-11 | Phase 22 | Pending`) flips to Complete.
- `.planning/REQUIREMENTS.md` §"Hygiene — v1.1 Carryover (Phase 23, parallel-eligible)" — HYG-03 (sessions endpoints) — FE-09 consumer.
- `.planning/REQUIREMENTS.md` §"Memberships — Plans Catalog (Phase 16)" + §"Memberships — Instances (Phase 17)" + §"Visits (Phase 19)" — REQ-IDs Phase 22 consumes via the typed paths.
- `.planning/ROADMAP.md` §"Phase 22: admin-web wiring — memberships + visits + active sessions UI" — Goal + Success Criteria 1-5 + dependency note.
- `.planning/ROADMAP.md` §"Phase 23: Hygiene + active sessions backend (parallel-eligible)" — Success Criterion 3 (sessions endpoints). FE-09 sub-plan blocks on this.
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions; Phase 22's D-22-* will be appended on phase verification.

### CLAUDE.md (admin-web project conventions)
- `apps/admin-web/CLAUDE.md` — Architecture (Layered data flow + Swap seam + Domain types + Role as session + FSD-lite layout + Query hygiene + Canonical templates + Theming) + Conventions (Money/Dates/IDs/Pagination/Forms/Errors/Russian locale/Style tokens/shadcn customization/Mock realism) + Anti-features. Phase 22 follows verbatim.

### Phase 21 outputs (typed transport surface — direct precursor)
- `packages/api-client/src/schema.d.ts` — typed paths Phase 22 consumes:
  - `paths['/api/v1/membership-plans']` (lines 248..) — list/create
  - `paths['/api/v1/membership-plans/{plan_id}']` (lines 272..) — get/patch/delete
  - `paths['/api/v1/memberships']` (lines 306..) — list/create
  - `paths['/api/v1/memberships/{membership_id}']` (lines 340..) — get
  - `paths['/api/v1/memberships/{membership_id}/cancel']` (lines 360..) — owner-only cancel
  - `paths['/api/v1/visits']` (lines 388..) — list/create (check-in)
  - `paths['/api/v1/visits/{visit_id}']` (lines 422..) — get
  - **MISSING (added in Phase 22 22-01-PLAN):** `paths['/api/v1/visits/_meta']`.
  - **MISSING (added in Phase 23, consumed by 22-05-PLAN):** `paths['/api/v1/auth/sessions']`, `paths['/api/v1/auth/sessions/{family_id}/revoke']`.
- `packages/api-client/src/fetcher.ts` (Phase 9 D-09 + D-11) — generic `request<P, M>(method, path, init?)` wrapper. Phase 22 services/http/* call this. NO modifications to fetcher.ts.
- `packages/api-client/src/schema.contract.test.ts` (Phase 21 D-21-4) — type-only smoke test. Phase 22 22-01-PLAN adds an assertion for `paths['/api/v1/visits/_meta']` after the slice lands; 22-05-PLAN adds the conditional sessions-paths assertion uplift (already conditional per D-21-2).
- `packages/api-client/src/index.ts` — barrel export.
- `apps/backend/openapi.json` — current spec; bumped once in 22-01-PLAN by adding `/api/v1/visits/_meta`.

### Phase 16 / 17 / 19 outputs (the v1.2 backend surface Phase 22 consumes)
- `apps/backend/app/api/v1/router.py` — route inclusion order (Phase 21 verified):
  - `include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])` (Phase 16)
  - `include_router(memberships_router, prefix="/memberships", tags=["memberships"])` (Phase 17)
  - `include_router(visits_router, prefix="/visits", tags=["visits"])` (Phase 19) — the `/visits/_meta` route lands inside this router in 22-01-PLAN.
- `apps/backend/app/modules/memberships/router.py` — operation summaries / response_models / status codes for plans + memberships routes. Phase 22 reads to understand owner-only routes (RBAC stays server-side; spec only carries the HTTP truth).
- `apps/backend/app/modules/visits/router.py` — same for visits. Phase 22 22-01-PLAN extends this file with the `_meta` endpoint.
- `apps/backend/app/modules/visits/service.py` lines 88-101, 116-128 — gym-hours window check (`_assert_within_gym_hours`, the main check-in flow). The `/visits/_meta` slice mirrors these constants verbatim (returns `settings.gym_hours_start.isoformat()`, `settings.gym_hours_end.isoformat()`).
- `apps/backend/app/core/config.py` lines 50-58 — `Settings.gym_hours_start: time = time(7, 0)`, `gym_hours_end: time = time(23, 0)` + `_gym_hours_range_invariant` validator. The `_meta` endpoint reads these.
- `apps/backend/app/core/exceptions.py` lines 199-208 — `OutsideGymHoursError(409, code='outside_gym_hours', fields={open, close})`. The `_meta` endpoint serialises the same `time.isoformat()` strings.
- `apps/backend/app/integrations/telegram/handlers.py` — Telegram bot handlers (Phase 20). The D-5 days-remaining tweak (D-22-11) lives here; specifically the success DM constant. Owner sign-off required for the new locked Russian string.

### admin-web codebase — composition
- `apps/admin-web/src/app/main.tsx` — top-level render. Awaits Zustand `persist.rehydrate()` for session + UI prefs. Phase 22 does NOT modify.
- `apps/admin-web/src/app/router.ts` — TanStack Router instance + `RouterContext = { queryClient, getSession }`. Phase 22 routes consume this context in `beforeLoad` + `loader`.
- `apps/admin-web/src/app/queryClient.ts` — single `QueryClient` (`staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1` queries / `retry: 0` mutations).
- `apps/admin-web/src/routes/__root.tsx` — wraps `<AppShell>` around `<Outlet/>`.
- `apps/admin-web/src/routes/_protected.tsx` — protected route layout root. Phase 22 NEW routes mount under `_protected/`.
- `apps/admin-web/src/routes/_protected/clients.tsx` lines 14-23 — owner-only `beforeLoad` precedent for `/membership-plans` (D-22-4 mirrors verbatim). Phase 22 NEW route `clients.$clientId.tsx` is a sibling (the route-segment param syntax is TanStack Router file-based).
- `apps/admin-web/src/routes/_protected/settings.tsx` — settings/profile route; FE-09 sessions list integrates here in 22-05-PLAN (verify route shape at plan-phase; alternative is a dedicated `/settings/sessions.tsx` sub-route).

### admin-web codebase — features (Pattern α reference)
- `apps/admin-web/src/features/clients/` — VALIDATED pattern: `api/{hooks,keys}.ts`, `components/*`, `model/schema.ts`, `index.ts`. Phase 22 NEW features (`memberships`, `visits`) mirror this layout 1:1.
- `apps/admin-web/src/features/clients/api/keys.ts` — query-keys factory pattern (`clientsKeys.all`, `.lists()`, `.list(filter)`, `.details()`, `.detail(id)`). Phase 22 NEW key factories mirror this.
- `apps/admin-web/src/features/clients/api/hooks.ts` — useClientsList / useClient / useCreateClient / useUpdateClient / useDeleteClient + optimistic-mutation pattern with `onMutate/onError/onSettled`. Phase 22 NEW hooks mirror this.
- `apps/admin-web/src/features/clients/components/ClientsTable.tsx` — table component with row actions; Phase 22 modifies this for D-22-5 row-click navigation.
- `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` — shadcn `<Dialog>` + react-hook-form + Zod precedent. `<SellMembershipDialog>` mirrors this.
- `apps/admin-web/src/features/auth/` — auth feature dir; FE-09 SessionsList likely extends this OR lives under `features/auth-sessions/` (plan-phase decides).

### admin-web codebase — shared
- `apps/admin-web/src/shared/api/services/index.ts` — swap-seam (verified: branches on `API_MODE === 'http' ? httpServices : mockServices`, eager imports). Phase 22 extends `mockServices` and `httpServices` consts to include `memberships` and `visits` keys.
- `apps/admin-web/src/shared/api/services/mock/index.ts` lines 10-13 — `services = { auth, clients }`. Phase 22 extends to `{ auth, clients, memberships, visits }`.
- `apps/admin-web/src/shared/api/services/http/index.ts` lines 10-13 — same shape as mock. Phase 22 extends identically.
- `apps/admin-web/src/shared/api/services/http/_envelope.ts` — D-07 `{data: T} → T` unwrap precedent. Phase 22 NEW http impls reuse the helper.
- `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` — adapter pattern between the typed `paths[...]` shape and the domain `Client` type. Phase 22 NEW http impls follow this adapter pattern (e.g. `_membershipsAdapter.ts`).
- `apps/admin-web/src/shared/api/contracts/clients.ts` — `ClientsService` interface + `ClientsListQuery`, `ClientCreateInput`, `ClientUpdateInput` types. Phase 22 NEW contracts mirror this layout.
- `apps/admin-web/src/shared/api/contracts/auth.ts` + `authSchema.ts` — Zod schema pattern (single schema reused by RHF + mock validator). Phase 22 NEW Zod schemas (`sellMembershipSchema`, `cancelMembershipSchema`) mirror this.
- `apps/admin-web/src/shared/api/config/env.ts` — `API_MODE` chokepoint (single-source for `import.meta.env.VITE_API_MODE`). Phase 22 does NOT modify.
- `apps/admin-web/src/shared/api/errors.ts` — error classes; `DomainError` shape used by mocks.
- `apps/admin-web/src/shared/session/registry.ts` lines 1-56 — `Resource` + `Action` + `RouteEntry` + `routeRegistry`. Phase 22 modifies the registry array (D-22-4) and may extend `navKey` enum.
- `apps/admin-web/src/shared/session/can.ts` lines 12-29 — `OWNER_ONLY` matrix (verified at discuss-phase: contains `{view, membership-plans}`, `{edit, membership-plans}`, `{create, membership-plans}`, `{delete, membership-plans}`, `{cancel, memberships}`, `{delete, memberships}` — Phase 15 INFRA-09 entries). Phase 22 does NOT extend this.
- `apps/admin-web/src/shared/session/RoleGate.tsx` — declarative role-gating wrapper. Phase 22 cancel button uses this OR `can()` directly.
- `apps/admin-web/src/shared/i18n/ru.ts` — single Russian dictionary. Phase 22 extends with `shell.nav.{visits,memberships,membershipPlans}` + domain entries (membership status labels, action verbs, dialog copy, D-3 badge text, etc.).
- `apps/admin-web/src/shared/i18n/date.ts` — date helpers + Europe/Moscow TZ pin. Phase 22 needs a `todayMSK()` helper for D-3 badge logic (verify it exists; add if missing).
- `apps/admin-web/src/shared/lib/money.ts` — `formatMoney(kopecks)` → ru-RU RUB string with NBSPs. Phase 22 uses verbatim.
- `apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx` — sidebar render; consumes `routeRegistry` + `can()`. Phase 22 NEW entries auto-render when added to the registry.
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` — profile dropdown; FE-09 may extend this OR add a separate "/settings/sessions" link inside.

### admin-web codebase — fixtures + tests
- `apps/admin-web/src/__fixtures/features/illegal-mock-import.ts` — existing negative-test fixture for the swap-seam ESLint rule. Phase 22 adds sibling `illegal-cross-feature-import.ts` for FE-11 / D-22-12.
- `apps/admin-web/src/__fixtures/api-mode-leak.ts` + `raw-fetch-leak.ts` + `raw-palette.tsx` — additional negative-test fixture precedents (Phase 11).
- `apps/admin-web/eslint.config.js` — current `import/no-restricted-paths` zone (verified: lines 50-71 — only the swap-seam rule). Phase 22 D-22-12 extends with the cross-feature zone.
- `apps/admin-web/src/test/utils.tsx` — `renderWithProviders(ui, {role})` helper. Phase 22 NEW component tests use this.
- `apps/admin-web/src/test/setup.ts` — vitest setup (in-memory localStorage shim). Phase 22 inherits.
- `apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx` — RBAC test precedent. Phase 22 D-22-5 row-click navigation extends this file.
- `apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts` + `clients.rbac.test.ts` — mock test precedents. Phase 22 read-only mock tests follow the RBAC precedent only (no CRUD test for mocks per D-22-7).

### Conventions
- `.planning/codebase/STRUCTURE.md` §"`src/` Tree" + §"Where to Add New Code" — Phase 22 NEW files placement.
- `.planning/codebase/CONVENTIONS.md` — formatting/linting/TS/naming/imports/component-patterns/state-data conventions.
- `.planning/codebase/TESTING.md` — vitest layout (sibling `*.test.ts(x)`).

### Third-party docs (read on demand)
- [TanStack Router file-based routing](https://tanstack.com/router/v1/docs/framework/react/guide/file-based-routing) — `clients.$clientId.tsx` segment param syntax + nested routes.
- [TanStack Router `validateSearch` + `loaderDeps`](https://tanstack.com/router/v1/docs/framework/react/guide/search-params) — for D-22-10 URL-driven `?expiring=true` filter on `/memberships`.
- [TanStack Query `ensureQueryData`](https://tanstack.com/query/latest/docs/react/reference/QueryClient#queryclientensurequerydata) — loader prefetch precedent (Phase 11 + Phase 22 FE-06).
- [shadcn/ui Dialog](https://ui.shadcn.com/docs/components/dialog) + [Badge](https://ui.shadcn.com/docs/components/badge) — used by SellMembershipDialog + D-3 destructive badge.
- [react-hook-form + Zod resolver](https://react-hook-form.com/get-started#SchemaValidation) — SellMembership form precedent.
- [Lucide icons reference](https://lucide.dev/icons) — `LogIn`, `Ticket`, `LayoutGrid` icon names (D-22-4 sidebar entries).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/admin-web/src/shared/api/services/index.ts`** (verified at discuss-phase) — swap-seam branches on `API_MODE === 'http' ? httpServices : mockServices`. Eager imports both. Phase 22 extends both containers with `memberships` and `visits` keys; the seam itself stays unchanged.
- **`apps/admin-web/src/features/clients/`** (full feature) — VALIDATED end-to-end pattern (api/keys.ts + api/hooks.ts + components/ + model/schema.ts + index.ts). Phase 22 NEW features mirror this 1:1.
- **`apps/admin-web/src/features/clients/api/hooks.ts`** lines 1-110 — useClientsList/useClient/useCreateClient/useUpdateClient + optimistic-mutation pattern with `onMutate/onError/onSettled` + `applyOptimisticUpdate` helper. Phase 22 cancel + sell flows reuse this exact pattern.
- **`apps/admin-web/src/features/clients/api/keys.ts`** — `clientsKeys` factory shape. Phase 22 `membershipsKeys` and `visitsKeys` mirror.
- **`apps/admin-web/src/features/clients/components/ClientFormDialog.tsx`** — shadcn `<Dialog>` + RHF + Zod precedent for `<SellMembershipDialog>`.
- **`apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` + `_envelope.ts`** — D-07 envelope unwrap + adapter-between-typed-paths-and-domain-type precedent. NEW http impls (memberships, visits, visitsMeta) reuse `_envelope.ts` and follow the `_clientsAdapter.ts` pattern.
- **`apps/admin-web/src/shared/api/contracts/clients.ts` + `authSchema.ts`** — service interface + Zod schema precedents.
- **`apps/admin-web/src/shared/session/registry.ts`** + **`can.ts`** — Resource/Action/RouteEntry primitives + OWNER_ONLY matrix. Phase 22 EXTENDS the `routeRegistry` array but NOT the OWNER_ONLY entries (Phase 15 already locked them).
- **`apps/admin-web/src/shared/session/RoleGate.tsx`** — declarative role-gating wrapper. Used by Phase 22 cancel buttons.
- **`apps/admin-web/src/shared/lib/money.ts`** — `formatMoney(kopecks)`. Used verbatim.
- **`apps/admin-web/src/shared/i18n/date.ts`** — date helpers + Europe/Moscow TZ pin. May need a `todayMSK()` helper for D-3 badge logic (plan-phase verifies + adds if missing).
- **`apps/admin-web/src/shared/i18n/ru.ts`** — Russian dictionary. Phase 22 appends new keys.
- **`apps/admin-web/eslint.config.js`** lines 50-71 — `import/no-restricted-paths` rule. Phase 22 D-22-12 ADDS a new zone (does NOT modify the existing one).
- **`apps/admin-web/src/__fixtures/features/illegal-mock-import.ts`** — negative-test fixture pattern for ESLint rule verification. Phase 22 mirrors with `illegal-cross-feature-import.ts`.
- **`apps/admin-web/src/test/utils.tsx`** — `renderWithProviders(ui, {role})`. NEW component tests use this.
- **`apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx`** + **`ProfileMenu.tsx`** — sidebar consumes registry + `can()`; profile dropdown + theme + role switcher. Sidebar auto-renders new entries when registry is extended.
- **`packages/api-client/src/fetcher.ts`** — `request<P, M>()` typed transport with single-flight 401→refresh→retry, CSRF on mutations. Phase 22 services/http/* call this. NO modifications.
- **`packages/api-client/src/schema.contract.test.ts`** — type-only smoke test from Phase 21. Phase 22 22-01-PLAN extends with a `paths['/api/v1/visits/_meta']` assertion; 22-05-PLAN's sessions assertion is already conditional per D-21-2.
- **Backend: `apps/backend/app/core/config.py:Settings.gym_hours_start` + `gym_hours_end`** — already typed `time` fields; the `/visits/_meta` slice exposes `.isoformat()` strings.
- **Backend: `apps/backend/app/modules/visits/router.py`** — host file for the NEW `/visits/_meta` route in 22-01-PLAN.

### Established Patterns

- **Pattern α: route-level composition over feature-cross-imports** — features stay independent; route files compose multiple feature blocks. ESLint enforces. Phase 22 is the canonical demo of this pattern (FE-07 + FE-11 + D-22-12).
- **Owner-only `beforeLoad` redirect** (clients.tsx lines 14-23) — `if (!can(role, 'view', resource)) throw redirect({to: '/', search: {forbidden: ...}})`. Phase 22 `/membership-plans` route mirrors verbatim.
- **Loader = `ensureQueryData(queryKey, queryFn)`** with the SAME key as the consuming hook — no waterfall, no double-fetch. Phase 22 NEW routes follow.
- **Mock-vs-http parity** at the contract layer — same TypeScript interface for both impls; the swap-seam picks at boot. Phase 22 inherits; D-22-7 narrows mock writes to `mock_not_implemented`.
- **Atomic-commit-per-task** — v1.1 + Phase 21 CD-02 precedent. Each ~22-NN-PLAN task → its own commit.
- **CI drift gate forces regeneration commit** — Phase 9 D-04..D-09 + Phase 21 D-21-* invariants. Phase 22 22-01-PLAN inherits.
- **Russian dictionary single-source** — never hardcode Russian copy in components. Plan-phase audits.
- **Semantic shadcn tokens only** — `bg-card`, `text-destructive`, etc. ESLint enforces. Phase 22 components verified at plan-phase.
- **Optimistic mutations with onMutate/onError/onSettled** — sell membership + cancel + check-in mutations follow.
- **VersionedlocalStorage namespace `sportzal:mock:v1`** — Phase 22 mock fixtures use this; no version bump.

### Integration Points

- **`apps/admin-web/src/shared/api/services/{mock,http}/index.ts`** — Phase 22 extends `services = { auth, clients, memberships, visits }`.
- **`apps/admin-web/src/shared/session/registry.ts`** — Phase 22 EXTENDS `routeRegistry` array with three NEW entries (D-22-4) + may extend `navKey` enum.
- **`apps/admin-web/src/routes/_protected/`** — Phase 22 ADDS `membership-plans.tsx`, `memberships.tsx`, `visits.tsx`, `clients.$clientId.tsx`. NEW route files trigger TanStack Router codegen → `routeTree.gen.ts` regeneration (auto on `pnpm dev`/`build`).
- **`apps/admin-web/src/features/clients/components/ClientsTable.tsx`** — Phase 22 D-22-5 modifies for row-click navigation.
- **`apps/admin-web/eslint.config.js`** — Phase 22 D-22-12 ADDS Pattern α zone (preserves existing rules).
- **`apps/admin-web/src/__fixtures/features/`** — Phase 22 ADDS `illegal-cross-feature-import.ts`.
- **`apps/admin-web/src/shared/i18n/ru.ts`** — Phase 22 APPENDS keys.
- **`apps/backend/app/modules/visits/router.py`** — Phase 22 22-01-PLAN ADDS `/visits/_meta` GET handler.
- **`apps/backend/app/modules/visits/schemas.py`** (or new `_meta_schemas.py`) — Phase 22 ADDS `VisitsMetaResponse` Pydantic model.
- **`apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`** — Phase 22 22-01-PLAN regenerates (single drift-gate refresh).
- **`packages/api-client/src/schema.contract.test.ts`** — Phase 22 22-01-PLAN extends with `/visits/_meta` assertion + 22-05-PLAN sessions assertion uplift.
- **`apps/backend/app/integrations/telegram/handlers.py`** — Phase 22 D-22-11 (D-5) modifies the success DM constant + days-remaining interpolation.
- **NO changes to** `app/main.tsx`, `app/router.ts`, `app/queryClient.ts`, `__root.tsx`, fetcher.ts, the swap-seam env config, OWNER_ONLY matrix, RBAC enums, the Phase 9/21 export_openapi.py + codegen invariants, the v1.1 mock test files for clients/auth, alembic migrations, docker-compose, .importlinter contracts, or any backend code outside `app/modules/visits/router.py` + `schemas.py` + `app/integrations/telegram/handlers.py`.

</code_context>

<specifics>
## Specific Ideas

- **Pattern α is the headline architectural deliverable.** REQUIREMENTS FE-07 + FE-11 + D-22-6 + D-22-12 all converge: features stay independent, the route file composes them, ESLint enforces. This sets the precedent for v1.3+ when trainers / schedule / bookings ship — each becomes a feature dir, and the routes compose them at the edge.
- **The mock-vs-http asymmetry (D-22-7) is deliberate, not a corner cut.** v1.2 backend tests (Phases 16/17/19) already cover the lifecycle invariants; mock parity for memberships/visits writes would re-implement those invariants in localStorage with no new coverage. Read-only mock + http mutations gives us shape-level confidence on the FE side and behavioural confidence on the BE side, with zero drift surface.
- **D-22-4 sidebar reception-first order** is informed by usage: reception touches `/visits` 50-200×/day (every check-in), `/clients` 5-30×/day (sales + new clients), `/memberships` rarely, `/membership-plans` never (owner-only, hidden). Putting `/visits` second (after `/`) minimises mouse travel for the highest-frequency operation.
- **D-22-1 `/visits/_meta` response is intentionally minimal.** Adding `nowMsk` to defend against client clock skew would force `Cache-Control: no-cache` and lose the cacheability win. The 409 fallback (server tells you the gym hours when you submit at the wrong time) is the safety net. v1.3+ may revisit if real ops feedback shows reception PCs with bad NTP.
- **D-22-2 sequencing FE-09 last** is the explicit answer to "Phase 22 depends on Phase 21 but optionally on Phase 23". The roadmap dependency note is permissive ("Phase 23 may also need to ship..."); Phase 22 reads this as "ship the memberships/visits surface independently, fold sessions UI in once Phase 23 lands, gate phase closure on FE-09".
- **D-22-11 (D-5) requires owner sign-off** on the new locked Russian DM string. Phase 20 AUTH-TG-11 set the precedent: locked Russian copy is owner-approved before merge. The new string is the existing success DM with `, осталось N дн.` appended (or similar — exact copy at plan-phase). The handler computes `(end_date - today_msk).days` using inclusive end_date semantics.
- **Owner sign-off is NOT required for Phase 22 sidebar labels** (Отметки/Абонементы/Тарифы) or ru.ts dictionary additions — those are display strings, not bot output. Per Phase 20 sign-off rules.
- **D-22-10 D-2 filter is client-side by default** to avoid a Phase 22 backend route extension. If perf bites at v1.3+ scale (>1000 active memberships per page), promote to a backend `?expiringWithinDays=` query param. Plan-phase agent decides at execution time based on the typed `paths['/api/v1/memberships']['get']['parameters']['query']` shape — if the param already exists, use it; if not, client-side.
- **22-05-PLAN (FE-09) carries the explicit "blocked on Phase 23" dependency** that the planner respects in the execution wave order. If Phase 23 lands FIRST, 22-05-PLAN can run in parallel with 22-02..22-04. If Phase 23 lands AFTER 22-02..22-04 complete, 22-05-PLAN runs as a final sub-plan + commits.

</specifics>

<deferred>
## Deferred Ideas

- **Full mock parity for memberships+visits write paths** — D-22-7 explicit. Storyboard-quality offline demo for the v1.2 surface revisits in v1.3+ if a customer demo or visual-regression suite requires it.
- **Tabbed or two-column layout** on `/clients/$clientId` — D-22-6 picks stacked. Tabs revisit if the page grows to 4+ blocks (e.g. v1.3+ adds bookings, billing history, tags).
- **`/memberships` "+ Продать" toolbar dialog** — D-22-8 picks inline-only. Bulk-sell revisits if back-office ops need it.
- **`/visits` "today's check-ins" feed** — D-22-3 explicit. Audit-feed UX revisits when the audit-log read endpoint ships in v1.3+.
- **`nowMsk` field on `/visits/_meta`** — defense against client clock skew. Revisits if reception PCs prove to have bad NTP.
- **`maxCheckinPerDay` / `channelsEnabled` on `/visits/_meta`** — config exposure for v1.3+ multi-zal or per-zal customisation.
- **Backend `?expiringWithinDays=` query param on `/api/v1/memberships`** — D-22-10 picks client-side. Promotes to backend filter if perf warrants.
- **Storybook setup** — CD-03 explicit. Visual regression revisits in v1.3+.
- **Backend `nowMsk` echo on `/visits/_meta`** for clock-skew defense — D-22-1 trade-off.
- **D-1, D-4, D-6, D-7 cheap-win differentiators** — FE-10 explicit.
- **Photo turnstile / geofencing / per-class booking** — REQUIREMENTS "Future Requirements (deferred to v1.3+)" already locked.
- **Membership renewal flow / freeze / visit-count plans / hybrid plans** — same.
- **Tag taxonomy / bulk CSV import / photo upload** for clients — same.
- **Audit log read UI** — same.
- **Real auth UX polish** (password reset via Telegram bot DM, HaveIBeenPwned check) — REQUIREMENTS deferred.
- **Punt FE-09 to v1.3 if Phase 23 slips badly** — D-22-2 fallback. Default is to wait; user re-evaluates only if Phase 23 misses the v1.2 deadline.
- **Storyboard-quality dev/demo mode without backend** — coupled to mock parity decision; revisits with D-22-7.

</deferred>

---

*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Context gathered: 2026-05-08*
