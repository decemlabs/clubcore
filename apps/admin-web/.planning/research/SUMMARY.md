# Research Summary: SportZal Adminka

**Domain:** React admin panel for a single gym / fitness club (Russia, RU-only UI, light + dark themes).
**Constraints:** Frontend-only v1 on mock data, two roles (Owner/Admin, Reception/Manager) via UI toggle (no login), shadcn/ui + reui.io, architecture must let a real HTTP API slot in later without touching UI.
**Synthesized:** 2026-04-21 from STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md.
**Overall confidence:** HIGH on stack/architecture/locale; MEDIUM-HIGH on domain model; MEDIUM on some reui.io specifics.

---

## TL;DR

- **Boring stack, one seam:** Vite + React 19 + TS strict, shadcn/ui as base, reui.io as an additive registry for data-grid / date-selector / timeline / filters. TanStack Router + Query, Zustand for UI/session, RHF + Zod for forms. All three research docs converge on this.
- **The whole project lives or dies by one architectural rule:** *UI never imports mocks directly.* Components → TanStack Query hooks → `services.*` container → mock or http implementation behind the same `ClientsService`/`ScheduleService`/etc. interfaces. That is the swap seam and the single acceptance criterion for v1.
- **Mock layer must feel real:** typed async services with latency + failure injection, deterministic `faker.seed(42)`, pagination envelopes, same Zod schemas reused for mock validation and form validation, localStorage-versioned persistence. Two approaches were studied (plain service-layer mocks vs MSW); both are viable, pick one consciously — see Open Questions #1.
- **Gym domain is stable:** every competitor (1Fit, FitBase, Mindbody, TeamUp, ClubManager, Glofox, Zen Planner) exposes the same module set — Clients & Memberships, Schedule, Trainers/Staff, Finances, Dashboard, Notifications, Settings. Innovate on polish, not structure. The Clients & Memberships check-in screen is the highest-leverage screen in the whole app.
- **Russian locale and domain vocabulary are first-class** (ДД.ММ.ГГГГ, Monday start, `+7 (XXX) XXX-XX-XX`, `1 234,56 ₽` with NBSP, pluralization with 3 forms, ФИО as three fields, *абонемент / заморозка / касса*). No i18n framework — one `ru.ts` dictionary + `Intl.*` helpers.

---

## Recommended Stack

Details in STACK.md. Minimum version set the roadmap should plan around:

| Layer | Choice | Version |
|---|---|---|
| Runtime | React | 19 |
| Build | Vite | 6 |
| Language | TypeScript strict | 5.6+ |
| Styling | Tailwind CSS v4 (CSS-first `@theme`) | v4 |
| Components (base) | shadcn/ui (`new-york`, neutral) | current |
| Components (overlay) | reui.io (`@reui` registry in `components.json`) | current |
| Routing | TanStack Router (file-based, typed search) | 1.x |
| Server state | TanStack Query | 5 |
| UI/session state | Zustand (+ `persist` middleware) | 5 |
| Forms | react-hook-form + zod + `@hookform/resolvers` | rhf 7, zod 3 |
| Tables | `@tanstack/react-table` 8 (shadcn Data Table + reui Data Grid on top) | 8 |
| Calendar | `react-big-calendar` + date-fns `ru` localizer | 1.15+ |
| Charts | shadcn `<Chart>` → Recharts | 3 |
| Dates | date-fns (+ `ru` locale) | 4 |
| Icons | lucide-react | current |
| Toasts | sonner | current |
| Mocks | MSW 2 **or** plain service-layer mocks (decision pending, see OQ#1) | — |
| Fake data | `@faker-js/faker` with fixed seed | 9 |
| PM / tooling | pnpm 9, ESLint 9 flat, Prettier (+ tailwind plugin), Vitest | — |

Default shadcn blocks to start from: `sidebar-07`/`sidebar-08` (collapsible sidebar with user switcher, basis for the Owner ↔ Reception toggle) and `dashboard-01` (KPI + table + chart layout).

**Hard-coded RU**: no i18next/react-intl. Single `src/i18n/ru.ts` + `Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow' })`, `Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })`, `Intl.PluralRules('ru-RU')` helper.

---

## Domain model (high level)

From FEATURES.md — use as the type-generation reference, not as a spec.

**Core entities:** `Client`, `Membership`, `MembershipTemplate`, `FreezeRecord`, `Visit`, `Lead`, `Room`, `ClassTemplate`, `ClassOccurrence` (+ `RecurrenceRule` + exceptions), `Enrollment`, `PersonalTrainingSlot`, `Staff` (role ∈ owner/admin/reception/trainer/...), `Compensation`, `Payment`, `CashRegisterSession`, `Notification`.

**Conventions (from PITFALLS.md):** branded string IDs (UUIDv4), ISO strings for dates/datetimes (never `Date` in domain types), money as integer minor units (kopecks) with `Money` type, enums as TS string-literal unions backed by Zod enums, discriminated unions for membership kind (`visits` | `period` | `hybrid`), pagination envelopes `{ items, total, page, pageSize }`.

**Membership state machine (one paragraph):** `pending` on purchase → `active` on activation (may be same moment or scheduled) → optionally `frozen` via dated `FreezeRecord` periods that extend `validUntil` (cap freeze days per period, reject overlaps) → `used-up` when visits depleted OR `expired` when `validUntil` passes OR `cancelled` on refund. A client can hold multiple active memberships simultaneously (e.g. group-only + PT pack); check-in resolves which one applies by scope (`gym|group|pool|sauna|pt`) and time window. Freezes extend the end date; this must be a derived computation, never a hand-edited field.

**Role matrix headline:** Reception/Manager gets ops-only views (check-in, schedule view + enroll, client CRUD, own-shift cash register, today's *касса* report, ops-category notifications). Owner/Admin gets everything plus finances, payroll, compensation, templates, reports, settings, audit. Destructive actions (refund, delete client, edit recurring series, view other shifts) are owner-only. Full matrix in FEATURES.md §7. Must be encoded once in a `routeRegistry` + `can(role, action, resource)` helper consumed by sidebar, route guards, mock services, and action buttons.

---

## Architecture principles

From ARCHITECTURE.md. These are non-negotiable; the rest of the codebase follows mechanically.

1. **Layered data flow:** `UI → TanStack Query hooks → services.X → { mock | http } impl`. Components import only hooks. Enforce via ESLint `import/no-restricted-paths` (or `no-restricted-imports`).
2. **The swap seam:** a single `src/shared/api/services/index.ts` that picks implementation by `VITE_API_MODE=mock|http`. Each domain has a contract (`ClientsService`, `ScheduleService`, …) in `shared/api/contracts/`; implementations in `services/mock/` and `services/http/`. Migration to real API = write http impls + flip default; UI/hooks/schemas/routes don't change.
3. **Domain types are the contract.** Branded IDs, ISO strings, integer minor units for money, discriminated unions for variant kinds, one Zod schema per resource reused by UI forms AND mock service validation, `DomainError { code, message, fields? }` uniform across mock and future http.
4. **Role as session:** `useSession()` (Zustand + `persist`) exposes `{ role }`. `<RoleGate role="owner">...</RoleGate>` wraps actions; route guards live in TanStack Router `beforeLoad`. When real auth ships, only the session source changes. Mock services should still enforce role server-side-style (return 403-analog `DomainError`) so habits match real backend.
5. **Folder layout — feature-first FSD-lite:**
   ```
   src/
     app/                  # providers, queryClient, router, index.css
     routes/               # TanStack Router file tree (thin)
     features/<domain>/    # api/ (hooks + keys) · components/ · model/ · index.ts
     entities/<entity>/    # types + schemas + pure helpers (no hooks, no UI)
     shared/
       ui/                 # shadcn + reui primitives (copied)
       api/{contracts,services/{mock,http}}
       session/            # store + RoleGate
       lib/ config/ theme/
   ```
   Features depend on entities + shared; **features do not import other features**. Mocks are central (cross-feature refs in the seeded DB), not per-feature.
6. **Query hygiene:** per-feature `xKeys` factory, stable serializable keys, `enabled: !!id` on dependents, `staleTime: 30_000`, `refetchOnWindowFocus: false`, optimistic mutations with `onMutate`/`onError`/`onSettled`, route `loader` uses `queryClient.ensureQueryData` with the same key the hook uses (no double-fetch).
7. **Canonical screen templates:** define once — **List** (toolbar + filters + virtualized DataTable + pagination + empty/error states), **Detail** (breadcrumb + header + tabs + side panel), **Form/Wizard** (grouped sections, sticky submit, dirty-guard). Every module composes these.
8. **Theming:** single `:root` / `.dark` block in `app/index.css` using shadcn tokens; ban raw palette colors (ESLint). Blocking `<script>` in `index.html` applies stored theme class before React mounts (no FOUC). reui components read the same CSS vars.

---

## v1 Module Scope (proposed)

Each module must ship the following to "feel real." Lifted from FEATURES.md §10 must-have checklist and cross-checked against ARCHITECTURE / PITFALLS.

### Foundation
- App shell (top bar: role switcher, theme toggle, notifications bell, profile; left nav; content)
- Role switcher (Owner ↔ Reception) driving nav + in-page affordances, persisted
- Theme toggle (light / dark / system) with no FOUC
- Mock data layer: typed services, Zod-validated, seeded faker, latency + failure injection, localStorage-versioned persistence, pagination envelopes, dev "Reset mock data" + chaos-mode toggle
- Notifications center (bell popover + full page + toasts)
- Canonical List / Detail / Form templates in `shared/ui`

### Clients & Memberships (vertical slice #1 — highest leverage)
- Clients list (filters: status, tag, expiring-soon, *должник*, source; search by phone/ФИО; virtualized table)
- Client detail with tabs: *Профиль · Абонементы · Посещения · Платежи · Записи · Заметки*
- Create/edit client (drawer)
- Sell-membership wizard (template → validity start → discount → payment method)
- Freeze-membership modal (period picker, shows adjusted `validUntil`)
- Membership templates catalog (admin)
- **Check-in screen** (reception home): big search, status badge, *Пропустить*, quick actions
- Expiring-soon list (7 / 30 day buckets)
- Leads / trials mini-pipeline (Kanban)

### Schedule
- Week calendar (default), Day, Month heatmap, Trainer swimlanes, Agenda list
- Class occurrence drawer (roster, check-in toggles, cancel, notes)
- Create one-off class drawer
- Create recurring series with Outlook-style "only this / this + future / whole series" scope picker
- Class templates + Rooms catalogs (admin)
- Waitlist inbox
- PT booking screen (trainer availability + client picker)

### Trainers / Staff
- Staff list + Trainer detail tabs (profile, certs, schedule, PT clients, rate, earnings)
- Create/edit staff; Compensation editor (plain-language → Compensation struct)
- Payroll run screen (admin-only)
- Certifications-expiring widget

### Finances
- Finance dashboard (today / month KPI cards + charts)
- Transactions list (unified in/out, heavy filter panel)
- Create payment / expense drawer (admin-only for expenses)
- Cash register open / running / close with reconciliation
- Canned reports: daily *касса*, monthly P&L, revenue by source, by method, trainer earnings, outstanding balances, membership sales, refunds log
- Expense categories catalog; Refund flow

### Dashboard
- Owner dashboard: full KPI grid (active memberships, expiring 7/30d, new clients, revenue today/month, MRR-ish, check-ins, classes today, class load %, trainer utilization, outstanding balance) + revenue chart + by-source pie + today's timeline + top trainers + classes today + expiring soon + birthdays + recent activity
- Reception dashboard: ops subset only (no financial cards, no trainer revenue)

### Notifications
- Bell popover (last 10, grouped by day) + full page (filters: type/severity/read)
- Toasts for in-session events
- Read-only notification-rules page

### Settings (minimum)
- Club info (name, address, hours, timezone, currency)
- Zones / scopes list; Working days & holidays; Default theme

---

## Critical do's and don'ts

A curated shortlist — ~10 items the team must tattoo into the codebase.

1. **DO** funnel all data access through `TanStack Query hook → service interface`. **DON'T** let any component import from `mocks/**` or `services/mock/**` or `services/http/**` directly. Enforce with ESLint.
2. **DO** keep the `services.*` container as the single swap point. **DON'T** branch on "is this mock?" anywhere in UI/hook code.
3. **DO** store money as integer minor units (kopecks) and dates as ISO strings (date-only for memberships). **DON'T** use IEEE-754 floats for money or `new Date(someDateOnlyString)` — it will break at DST / TZ boundaries.
4. **DO** model memberships as a discriminated union (`visits` / `period` / `hybrid`) and freezes as periods; compute effective `validUntil` on read. **DON'T** model a freeze as a boolean.
5. **DO** validate in the mock service with the same Zod schema the form uses, and throw `DomainError` with `fields` — so mock errors are indistinguishable from future server errors. **DON'T** let mocks "always succeed."
6. **DO** simulate latency (120–300ms) and optional failure rate in the mock. **DON'T** ship instant mocks; they hide loading/empty/error branches.
7. **DO** enforce roles in both the sidebar (menu filter), the router (`beforeLoad` guard), action buttons (`<RoleGate>`), AND the mock service (403-analog). **DON'T** rely on client-side hiding as "security."
8. **DO** use semantic shadcn tokens (`bg-background`, `text-muted-foreground`, etc.) and forbid raw palette colors (`bg-white`, `text-slate-900`). **DON'T** hand-customize `components/ui/*`; put customizations in wrappers. Comment any intentional divergence (`// SHADCN-DIVERGENCE: …`).
9. **DO** always return a pagination envelope `{ items, total, page, pageSize }` from every list endpoint — even in v1 with 80 rows. **DON'T** return bare arrays; every table will have to change later.
10. **DO** render List screens via the shared virtualized DataTable and render empty / loading-skeleton / error states as a three-state contract. **DON'T** use toasts for critical errors (inline alerts / dialogs only); toasts are for non-blocking acks and undo windows.
11. **DO** configure calendars/date pickers with `locale={ru}`, `weekStartsOn: 1`, 24h time, DD.MM.YYYY. **DON'T** rely on host locale defaults.
12. **DO** keep TZ pinned to `Europe/Moscow` and document it; date math uses date-fns with locale. **DON'T** scatter `Date` across domain types.
13. **DO** seed faker with `faker.seed(42)` and version the localStorage key (`sportzal:mock:v1`). **DON'T** ship unseeded faker; demos will look broken.
14. **DO** keep scope to the must-have checklist. **DON'T** build the v1 anti-features (real auth, websockets, audit log search, reports builder, CSV import, bulk actions, real SMS/email/fiscalization, payment gateways, mobile portal, DnD schedule editing, i18n runtime, multi-club) — they are explicitly out.

---

## Recommended phase order (for roadmapper)

All four research docs agree. Proposed 7–8 phases:

1. **Foundation & Shell** — Vite scaffold, Tailwind v4, shadcn init + reui registry wired, core components installed, app shell (`sidebar-07` adapted), role switcher, theme toggle (no FOUC), TanStack Router root + `_app` layout, QueryClient with defaults, ESLint boundary rules, folder layout. Deliverable: you can navigate between placeholder pages and toggle role/theme.
2. **Data Layer Contracts + Mock Infrastructure** — `entities/` domain types (branded IDs, ISO strings, `Money`), shared Zod schemas, service contracts (`shared/api/contracts`), `DomainError`, mock DB (seeded faker + localStorage persistence + versioned key), latency & failure injection, pagination helpers, `services` container swap point, dev toolbar (reset mocks, chaos toggle), canonical List/Detail/Form templates in `shared/ui`, notifications store skeleton. No feature UI yet.
3. **Clients & Memberships** — vertical slice #1, highest-leverage (exercises every architectural rule). Ships Clients list, Client detail with tabs, create/edit, sell-membership wizard, freeze modal, membership templates catalog, check-in screen, expiring-soon, leads mini-pipeline. Membership state machine implemented + tested against mock.
4. **Schedule** — most complex UI; depends on clients & memberships for enrollment. Calendar views (week/day/month/trainer), occurrence drawer, recurring series with scope picker (series + exceptions model), rooms + class templates catalogs, waitlist, PT booking. Validate `react-big-calendar` on a real drag-to-reschedule prototype early in this phase.
5. **Trainers / Staff** — staff CRUD, compensation editor, PT clients list, earnings/payroll (with per-occurrence rate snapshot so historical rate changes don't retro-alter payouts), certifications widget.
6. **Finances** — transactions, payment/expense drawer, cash register open/close with reconciliation, canned reports (8 listed above), refunds, discounts/promos. Integer-minor-units money throughout.
7. **Dashboard + Notifications + Polish** — assemble KPI grid from the now-populated services (dashboard service aggregates across features), notification triggers (membership expiring, class filled, cert expiring, cash discrepancy, etc.), toasts for in-session events, performance pass (route-level code splitting, memoized aggregates, narrow Zustand selectors, bundle analysis).
8. **Settings + v1 hardening** (optional, can fold into 7) — club info, zones, working days, default theme; a11y audit; dark-mode QA; responsive QA at 1366×768; final pitfall checklist sweep.

**Research flags (which phases likely need `/gsd-research-phase` during planning):**

- **Phase 4 (Schedule):** HIGH research need. Validate react-big-calendar vs FullCalendar-free resource-timeline UX; recurring series + exceptions is subtle; waitlist/capacity invariants; membership-scope eligibility on enroll. Possibly revisit OQ#1 (scheduler final choice).
- **Phase 6 (Finances):** MEDIUM research need. Cash-register session semantics, reconciliation UX, canned report shapes, *касса* conventions. Fiscal regime (54-ФЗ) is out of scope but UI surface decisions (fake receipt numbers, "чек отправлен" badge) should be settled before coding.
- **Phase 2 (Data layer):** MEDIUM research need. Resolve MSW vs service-layer mocks (OQ#1) and pagination/filter URL contract (OQ#6) before locking the seam.
- **Phase 5 (Staff):** MEDIUM research need. Compensation model superset, payroll edge cases (co-teaching, no-show, cancellations, historical snapshots).
- **Phase 1, 3, 7, 8:** LOW — patterns are well documented, stack is boring on purpose.

---

## Open questions (for requirements / roadmap phase)

Consolidated from all four research docs. Each tagged with where to answer.

1. **Mock transport: MSW 2 vs plain service-layer mocks.** STACK.md recommends MSW (realistic network tab, easier test reuse). ARCHITECTURE.md recommends service-layer (trivially local swap, less build complexity, MSW as future escape hatch for integration tests). Both are defensible. **Tag:** REQUIREMENTS — pick before Phase 2.
2. **Scheduler final choice.** `react-big-calendar` is the recommendation; trade-off is lack of free Resource/Timeline. Prototype drag-to-reschedule in Phase 4 and revisit FullCalendar (paid) if UX limits show. **Tag:** PHASE-4 PLAN.
3. **Canonical URL filter/search contract.** Decide the query-string shape (`?status=active&subscription=expiring&page=2&sort=-createdAt`) before Clients list — it becomes the de-facto future API contract. **Tag:** PHASE-3 PLAN (earlier if possible).
4. **Command palette (`cmd+k`).** Nice UX, ~half a day. Include in v1 or defer to Polish? **Tag:** ROADMAP.
5. **Role/theme persistence behavior.** Persist via `zustand/middleware#persist`? Demos may prefer "always reset to Owner/light" on load. **Tag:** REQUIREMENTS.
6. **Family memberships model.** One membership linked to multiple clients (shared pool) vs parent + dependents? Default: shared-pool. **Tag:** PHASE-3 PLAN.
7. **Access control simulation.** Show a *"дверь открыта"* toast on check-in vs pure informational? Default: informational. **Tag:** PHASE-3 PLAN.
8. **PT sales model default.** Pre-paid pack (membership-like) vs ad-hoc per-session. Support both; pick the seeded default. **Tag:** PHASE-3 PLAN.
9. **Kids area modeling.** Distinct module vs `membershipType = kids` + age gate? Default: latter. **Tag:** REQUIREMENTS.
10. **Shop / locker-rent POS.** Out of v1, but keep `source: 'shop' | 'rental'` enum values? **Tag:** ROADMAP confirm.
11. **Visit deduction semantics.** On entry vs on class attendance. Default: on entry. **Tag:** PHASE-3 PLAN.
12. **Discount model depth.** Per-sale `discountAmount` free-form + thin promos list vs code engine. Default: the former. **Tag:** PHASE-3 PLAN.
13. **Notifications transport.** v1 is poll (`GET /api/notifications`, staleTime 60s). Confirm no simulated websocket. **Tag:** PHASE-2 PLAN.
14. **Bundle budget / route-splitting.** rbc + recharts + reui patterns risk >500 KB gz initial. Decide by dashboard phase. **Tag:** PHASE-7 PLAN.
15. **reui.io verification.** Exact token names, install paths, and dark-mode strategy should be re-verified against reui docs before Phase 1 finishes (noted by PITFALLS.md as MEDIUM confidence). **Tag:** PHASE-1 PLAN.
16. **Avatar source.** Deterministic service (DiceBear) so reload doesn't churn demo images. **Tag:** PHASE-2 PLAN.

---

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | HIGH | STACK.md verified live via Context7 across shadcn/ui, reui.io, TanStack Router/Query/Table, MSW, RHF/Zod, Zustand, Recharts, rbc, faker. Versions and install commands are current. |
| Architecture | HIGH | ARCHITECTURE.md patterns are mainstream and match TanStack Query v5 / TanStack Router v1 docs. Swap seam design is pragmatic and testable. One genuine tradeoff (MSW vs service-layer) is called out. |
| Features / domain | MEDIUM-HIGH | Module set is the well-known intersection of 7+ vendors; domain vocabulary (*абонемент / заморозка / касса*) is stable. Specific vendor screen parity was not freshly verified (WebFetch blocked during research), so "vendor X has screen Y" claims are MEDIUM; "every vendor has this module" claims are HIGH. |
| Pitfalls | HIGH on generic React/TanStack/shadcn/locale; MEDIUM on reui.io specifics and some gym domain edge cases. Research pass ran without live WebFetch/Context7 and flags this internally. |
| Overall readiness for requirements & roadmap | HIGH | The four docs agree on structure and priorities; the remaining open questions are product choices, not architectural unknowns. |

**Known gaps:**

- reui.io token naming, current CLI install flow, and dark-mode class strategy need a re-verification pass before Phase 1 ends (called out in PITFALLS §3 and ARCHITECTURE §9).
- MSW vs service-layer decision is open; roadmap should place it as a Phase 2 entry gate.
- No live vendor screenshot verification; module set is derived from training-data synthesis.

---

## Sources

- **`.planning/research/STACK.md`** — Full stack decisions, install commands, `components.json` config, theming, file layout, alternatives considered, open decisions. Context7-verified 2026-04-21.
- **`.planning/research/FEATURES.md`** — Gym/CRM domain deep-dive: entity field lists, membership types & lifecycle, check-in UX, schedule objects, compensation models, finance/*касса* model, KPIs, notifications catalog, full role matrix, competitive landscape, anti-features, v1 must-have checklist.
- **`.planning/research/ARCHITECTURE.md`** — Mock-first frontend architecture: service contracts, swap seam, TanStack Query hook patterns with optimistic updates, mock DB strategy (MSW vs service-layer decision), role/session abstraction, routing structure, folder layout, forms, state templates, theming, migration path diff.
- **`.planning/research/PITFALLS.md`** — Mock-first migration traps, shadcn/ui + reui mixing pitfalls, admin UX traps, role toggling traps, gym domain modeling pitfalls (membership/freeze/capacity/payroll/recurrence), React + TanStack Query pitfalls, performance traps, Russian-locale specifics, greenfield-admin traps, phase-specific warnings, and an anti-features list of 20 things to explicitly not build in v1.

---
*Synthesized for `/gsd-new-project` Phase 7. Downstream consumers: `gsd-roadmapper` for phase structuring, requirements definition for resolving Open Questions.*
