# Requirements: SportZal Adminka

**Defined:** 2026-04-21
**Core Value:** Владелец зала и ресепшн видят цельный, готовый к ежедневной работе интерфейс управления залом — так, что архитектуру можно показать и продавать как MVP, а позже подключить к нему настоящий API без переписывания UI.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [x] **FOUND-01**: App shell is rendered with top bar (role switcher, theme toggle, notifications bell, profile), collapsible sidebar (shadcn `sidebar-07`/`sidebar-08` basis), and content area
- [x] **FOUND-02**: User can toggle role between Owner/Admin and Reception/Manager from the UI; nav and in-page affordances update accordingly; choice persists via `zustand/middleware#persist` across reload
- [x] **FOUND-03**: User can toggle theme between light / dark / system; choice persists via `zustand/middleware#persist`; blocking `<script>` in `index.html` applies stored theme class before React mounts (no FOUC)
- [x] **FOUND-04**: Interface is rendered entirely in Russian (DD.MM.YYYY dates, Monday week-start, `+7 (XXX) XXX-XX-XX` phone masks, `1 234,56 ₽` money with NBSP, 3-form pluralization, 24h time) — via single `src/i18n/ru.ts` + `Intl.*` helpers
- [x] **FOUND-05**: TanStack Router renders file-based route tree with typed search params; root layout hosts app shell
- [x] **FOUND-06**: ESLint `import/no-restricted-paths` (or `no-restricted-imports`) forbids UI/features from importing `services/mock/**` or `services/http/**` directly — only via hooks → `services` container
- [x] **FOUND-07**: Semantic shadcn tokens (`bg-background`, `text-muted-foreground`, etc.) are used exclusively; raw palette colors (`bg-white`, `text-slate-900`, etc.) are forbidden via ESLint rule

### Data Layer

- [ ] **DATA-01**: Domain types in `entities/*` use branded string UUIDv4 IDs, ISO date strings, integer minor units (kopecks) for money via `Money` type, discriminated unions for variant kinds (e.g. membership `visits | period | hybrid`)
- [ ] **DATA-02**: Every resource has a single Zod schema in `entities/*` reused by both UI forms and mock service validation
- [ ] **DATA-03**: Each domain has a service contract (`ClientsService`, `ScheduleService`, `StaffService`, `FinanceService`, `NotificationsService`, `DashboardService`, `SettingsService`) in `shared/api/contracts/`
- [ ] **DATA-04**: Mock implementations live in `shared/api/services/mock/` as **plain service-layer functions** returning promises (no MSW / no fetch interception) — decision OQ#1
- [ ] **DATA-05**: `shared/api/services/index.ts` picks implementation by `VITE_API_MODE=mock|http`; UI/hooks never branch on mode
- [ ] **DATA-06**: Mock DB is seeded with `@faker-js/faker` using `faker.seed(42)` and persisted to localStorage under a versioned key (`sportzal:mock:v1`)
- [ ] **DATA-07**: Mock services simulate latency (120–300ms) and configurable failure rate
- [ ] **DATA-08**: All list endpoints return a pagination envelope `{ items, total, page, pageSize }` — no bare arrays
- [ ] **DATA-09**: Mock services throw uniform `DomainError { code, message, fields? }` — indistinguishable from future HTTP errors
- [ ] **DATA-10**: Mock services enforce role-based access (return 403-analog `DomainError`) — same enforcement surface as future real backend
- [ ] **DATA-11**: Dev toolbar exposes "Reset mock data" and "Chaos mode" toggles (visible only when `import.meta.env.DEV`)
- [ ] **DATA-12**: TanStack Query is configured with `staleTime: 30_000`, `refetchOnWindowFocus: false`, per-feature `xKeys` factory; route loaders use `queryClient.ensureQueryData` with the same key as hooks (no double-fetch)

### Clients & Memberships

- [ ] **CLIENT-01**: Clients list page shows virtualized DataTable with search (phone/ФИО) and filters (status, tag, expiring-soon, *должник*, source)
- [ ] **CLIENT-02**: Client detail page has tabs *Профиль · Абонементы · Посещения · Платежи · Записи · Заметки*
- [ ] **CLIENT-03**: Create/edit client drawer with form validation (Zod + RHF); ФИО stored as three fields
- [ ] **CLIENT-04**: Sell-membership wizard: template → validity start → discount → payment method
- [ ] **CLIENT-05**: Membership state machine enforced: `pending → active → { frozen | used-up | expired | cancelled }`; freezes modeled as dated `FreezeRecord` periods that extend `validUntil` (computed on read, never hand-edited)
- [ ] **CLIENT-06**: Freeze-membership modal with period picker shows adjusted `validUntil`; overlapping freezes rejected; per-period cap enforced
- [ ] **CLIENT-07**: Membership templates catalog (admin-only create/edit)
- [ ] **CLIENT-08**: Check-in screen (reception home): big search, status badge, *Пропустить* action, quick actions; visit deduction on entry
- [ ] **CLIENT-09**: Expiring-soon list with 7-day and 30-day buckets
- [ ] **CLIENT-10**: Leads / trials mini-pipeline as Kanban board
- [ ] **CLIENT-11**: Client can hold multiple simultaneous memberships; check-in resolves applicable one by scope (`gym|group|pool|sauna|pt`) and time window

### Schedule

- [ ] **SCHED-01**: Week calendar view (default) using `react-big-calendar` with `locale={ru}`, `weekStartsOn: 1`, 24h time, `Europe/Moscow` TZ
- [ ] **SCHED-02**: Day, Month heatmap, Trainer swimlanes, Agenda list views
- [ ] **SCHED-03**: Class occurrence drawer with roster, check-in toggles, cancel action, notes
- [ ] **SCHED-04**: Create one-off class drawer
- [ ] **SCHED-05**: Create recurring series with Outlook-style "only this / this + future / whole series" scope picker; series + exceptions model
- [ ] **SCHED-06**: Class templates catalog (admin-only create/edit)
- [ ] **SCHED-07**: Rooms catalog (admin-only create/edit)
- [ ] **SCHED-08**: Waitlist inbox surface
- [ ] **SCHED-09**: Personal training booking screen (trainer availability + client picker)
- [ ] **SCHED-10**: Capacity vs enrollment invariant enforced in mock service (reject over-booking, offer waitlist)

### Trainers / Staff

- [ ] **STAFF-01**: Staff list with filter by role and status
- [ ] **STAFF-02**: Trainer detail page with tabs (profile, certifications, schedule, PT clients, rate, earnings)
- [ ] **STAFF-03**: Create/edit staff drawer
- [ ] **STAFF-04**: Compensation editor converts plain-language form to structured `Compensation` record; supports the 6 archetypes documented in FEATURES.md
- [ ] **STAFF-05**: Payroll run screen (admin-only); per-occurrence rate snapshot so historical rate changes don't retro-alter payouts
- [ ] **STAFF-06**: Certifications-expiring widget

### Finances

- [ ] **FIN-01**: Finance dashboard with today/month KPI cards and charts
- [ ] **FIN-02**: Transactions list (unified in/out) with heavy filter panel
- [ ] **FIN-03**: Create payment drawer (reception + admin)
- [ ] **FIN-04**: Create expense drawer (admin-only)
- [ ] **FIN-05**: Cash register session: open / running / close with reconciliation (expected vs actual, discrepancy notes)
- [ ] **FIN-06**: Canned reports: daily *касса*, monthly P&L, revenue by source, revenue by method, trainer earnings, outstanding balances, membership sales, refunds log
- [ ] **FIN-07**: Expense categories catalog (admin-only)
- [ ] **FIN-08**: Refund flow with audit trail
- [ ] **FIN-09**: All money values stored and computed as integer minor units (kopecks); display uses `Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })` with NBSP

### Dashboard

- [ ] **DASH-01**: Owner dashboard shows full KPI grid (active memberships, expiring 7/30d, new clients, revenue today/month, MRR-ish, check-ins, classes today, class load %, trainer utilization, outstanding balance)
- [ ] **DASH-02**: Owner dashboard shows revenue chart, by-source pie, today's timeline, top trainers, classes today, expiring soon, birthdays, recent activity
- [ ] **DASH-03**: Reception dashboard shows ops subset only (no financial cards, no trainer revenue, no payroll)
- [ ] **DASH-04**: Dashboard aggregates are computed by a dedicated `DashboardService` (mock aggregates across other services)

### Notifications

- [ ] **NOTF-01**: Notifications bell popover shows last 10 items grouped by day
- [ ] **NOTF-02**: Full notifications page with filters (type, severity, read/unread)
- [ ] **NOTF-03**: Toasts (sonner) for in-session events; critical errors use inline alerts/dialogs, not toasts
- [ ] **NOTF-04**: Read-only notification-rules page listing event types and who receives them
- [ ] **NOTF-05**: Reception sees ops-category notifications only (membership expiring, class filled, low capacity, cash discrepancy); Owner sees all

### Settings

- [ ] **SET-01**: Club info page (name, address, hours, timezone pinned to `Europe/Moscow`, currency pinned to RUB)
- [ ] **SET-02**: Zones / scopes list (e.g. gym, group, pool, sauna, pt)
- [ ] **SET-03**: Working days & holidays calendar
- [ ] **SET-04**: Default theme selection (applies for users without a persisted preference)

### Role-Based Access

- [x] **ROLE-01**: Single `routeRegistry` + `can(role, action, resource)` helper is the source of truth; consumed by sidebar menu filter, TanStack Router `beforeLoad` guard, `<RoleGate>` component wrapping action buttons, and mock services
- [x] **ROLE-02**: Reception/Manager is restricted to check-in, schedule view + enroll, client CRUD (no delete), own-shift cash register, today's *касса* report, ops-category notifications
- [x] **ROLE-03**: Owner/Admin has access to all Reception views plus finances, payroll, compensation, templates, reports, settings
- [x] **ROLE-04**: Destructive actions (refund, delete client, edit recurring series, view other shifts) are Owner-only
- [x] **ROLE-05**: When real auth is added later, only the session source changes; role-gating logic is untouched

### UI & UX Baseline

- [ ] **UI-01**: Canonical List / Detail / Form(Wizard) templates live in `shared/ui` and every module composes them
- [ ] **UI-02**: Every list screen renders empty / loading-skeleton / error as a three-state contract
- [x] **UI-03**: reui.io components (data-grid, date-selector, timeline, filters, stepper) coexist with shadcn via `components.json` `@reui` registry entry; both read the same CSS vars
- [x] **UI-04**: Responsive layout works at 1366×768 (minimum admin resolution) through desktop widths
- [ ] **UI-05**: Basic a11y: keyboard navigation for primary flows, visible focus rings, correct labels on form fields, ARIA on dialogs/drawers
- [ ] **UI-06**: Realistic mock data volume: ~50–100 clients, 2–3 months of schedule occurrences, proportional staff/payments

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Authentication & Multi-Tenant

- **AUTH-01**: Real login screen (email + password)
- **AUTH-02**: Session token storage and refresh
- **AUTH-03**: Multi-club / multi-tenant support

### Integrations

- **INT-01**: Real SMS gateway for notifications
- **INT-02**: Real email provider for notifications
- **INT-03**: Payment gateway integration (acquiring)
- **INT-04**: 54-ФЗ fiscal registrar integration (real receipts)
- **INT-05**: Access control system (turnstile/door) integration
- **INT-06**: Websocket transport for live notifications

### Advanced Features

- **ADV-01**: Reports builder (ad-hoc report composer)
- **ADV-02**: CSV import for clients/memberships
- **ADV-03**: Bulk actions across list tables
- **ADV-04**: Drag-and-drop schedule editing
- **ADV-05**: Audit log with search
- **ADV-06**: Command palette (`cmd+k`) — OQ#4, may promote to v1 if Polish phase has budget
- **ADV-07**: Promo code engine (beyond per-sale `discountAmount`)
- **ADV-08**: Shop / locker-rent POS module
- **ADV-09**: Kids area as distinct module with parent/dependent linkage (v1 defers to single Clients module — OQ#9)
- **ADV-10**: Mobile client portal
- **ADV-11**: i18n runtime with language switcher

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real backend / database | Project goal is frontend foundation on mocks; API plugs in later |
| Real authentication & security | Role is a UI toggle; no login screen in v1 |
| Payment gateway integration | v1 is UI-only, mock payments only |
| Mobile native app | Web admin only |
| i18n / English localization | Russian-only v1; no i18n framework to carry |
| Real SMS / email sending | v1 is a notifications center UI only |
| Fiscal registrar (54-ФЗ) integration | Out of v1; UI surface (fake receipt numbers, badge) only |
| Websocket / live push | v1 notifications are poll (staleTime 60s) |
| Audit log search | Noise for v1 demo; deferred |
| Reports builder | Canned reports only in v1 |
| CSV import | Seed data covers demo volume |
| Bulk actions in tables | Row-by-row only in v1 |
| Drag-to-reschedule in calendar | May be added if `react-big-calendar` supports it cleanly in Phase 4, otherwise deferred |
| Command palette (`cmd+k`) | Deferred to v2 unless Polish phase has budget — OQ#4 |
| Multi-club / multi-tenant | v1 is single-club |
| Kids area as distinct module | v1 defers kids entirely — OQ#9 answered: **not modeled in v1** |
| Access control door integration | UI-side only if any; no real hardware in v1 |
| MSW (Mock Service Worker) | OQ#1 resolved: plain service-layer mocks preferred |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Done |
| FOUND-02 | Phase 1 | Done |
| FOUND-03 | Phase 1 | Done |
| FOUND-04 | Phase 1 | Done |
| FOUND-05 | Phase 1 | Done |
| FOUND-06 | Phase 1 | Done |
| FOUND-07 | Phase 1 | Done |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| DATA-05 | Phase 2 | Pending |
| DATA-06 | Phase 2 | Pending |
| DATA-07 | Phase 2 | Pending |
| DATA-08 | Phase 2 | Pending |
| DATA-09 | Phase 2 | Pending |
| DATA-10 | Phase 2 | Pending |
| DATA-11 | Phase 2 | Pending |
| DATA-12 | Phase 2 | Pending |
| CLIENT-01 | Phase 3 | Pending |
| CLIENT-02 | Phase 3 | Pending |
| CLIENT-03 | Phase 3 | Pending |
| CLIENT-04 | Phase 3 | Pending |
| CLIENT-05 | Phase 3 | Pending |
| CLIENT-06 | Phase 3 | Pending |
| CLIENT-07 | Phase 3 | Pending |
| CLIENT-08 | Phase 3 | Pending |
| CLIENT-09 | Phase 3 | Pending |
| CLIENT-10 | Phase 3 | Pending |
| CLIENT-11 | Phase 3 | Pending |
| SCHED-01 | Phase 4 | Pending |
| SCHED-02 | Phase 4 | Pending |
| SCHED-03 | Phase 4 | Pending |
| SCHED-04 | Phase 4 | Pending |
| SCHED-05 | Phase 4 | Pending |
| SCHED-06 | Phase 4 | Pending |
| SCHED-07 | Phase 4 | Pending |
| SCHED-08 | Phase 4 | Pending |
| SCHED-09 | Phase 4 | Pending |
| SCHED-10 | Phase 4 | Pending |
| STAFF-01 | Phase 5 | Pending |
| STAFF-02 | Phase 5 | Pending |
| STAFF-03 | Phase 5 | Pending |
| STAFF-04 | Phase 5 | Pending |
| STAFF-05 | Phase 5 | Pending |
| STAFF-06 | Phase 5 | Pending |
| FIN-01 | Phase 6 | Pending |
| FIN-02 | Phase 6 | Pending |
| FIN-03 | Phase 6 | Pending |
| FIN-04 | Phase 6 | Pending |
| FIN-05 | Phase 6 | Pending |
| FIN-06 | Phase 6 | Pending |
| FIN-07 | Phase 6 | Pending |
| FIN-08 | Phase 6 | Pending |
| FIN-09 | Phase 6 | Pending |
| DASH-01 | Phase 7 | Pending |
| DASH-02 | Phase 7 | Pending |
| DASH-03 | Phase 7 | Pending |
| DASH-04 | Phase 7 | Pending |
| NOTF-01 | Phase 7 | Pending |
| NOTF-02 | Phase 7 | Pending |
| NOTF-03 | Phase 7 | Pending |
| NOTF-04 | Phase 7 | Pending |
| NOTF-05 | Phase 7 | Pending |
| SET-01 | Phase 7 | Pending |
| SET-02 | Phase 7 | Pending |
| SET-03 | Phase 7 | Pending |
| SET-04 | Phase 7 | Pending |
| ROLE-01 | Phase 1 | Done |
| ROLE-02 | Phase 1 | Done |
| ROLE-03 | Phase 1 | Done |
| ROLE-04 | Phase 1 | Done |
| ROLE-05 | Phase 1 | Done |
| UI-01 | Phase 2 | Pending |
| UI-02 | Phase 2 | Pending |
| UI-03 | Phase 1 | Done |
| UI-04 | Phase 1 | Done |
| UI-05 | Phase 7 | Pending |
| UI-06 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 79 total (across 11 categories)
- Mapped to phases: 79 (100%)
- Unmapped: 0

**Distribution:**
- Phase 1 (Foundation & Shell): 14 requirements — FOUND-01..07, ROLE-01..05, UI-03, UI-04
- Phase 2 (Data Layer + Mocks): 15 requirements — DATA-01..12, UI-01, UI-02, UI-06
- Phase 3 (Clients & Memberships): 11 requirements — CLIENT-01..11
- Phase 4 (Schedule): 10 requirements — SCHED-01..10
- Phase 5 (Trainers / Staff): 6 requirements — STAFF-01..06
- Phase 6 (Finances): 9 requirements — FIN-01..09
- Phase 7 (Dashboard + Notifications + Settings + Polish): 14 requirements — DASH-01..04, NOTF-01..05, SET-01..04, UI-05

---
*Requirements defined: 2026-04-21*
*Traceability mapped: 2026-04-21 by `gsd-roadmapper`.*
*Last updated: 2026-04-21 after resolving OQ#1 (service-layer mocks), OQ#5 (zustand persist), OQ#9 (kids deferred to v2)*
