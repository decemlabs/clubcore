# Roadmap: SportZal Adminka

## Overview

Build a React admin panel for a single gym, v1 entirely on mock data. The journey lays down a thin foundation and a disciplined data-layer seam first, then ships the product as four vertical feature slices (Clients & Memberships, Schedule, Staff, Finances), and finally assembles cross-cutting surfaces (Dashboard, Notifications, Settings) and polish. The architectural rule "UI talks to TanStack Query hooks, hooks talk to service contracts, contracts have a mock implementation today and an http implementation later" is installed in Phase 1-2 and defended by every subsequent phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Shell** - App shell, role/theme toggles, router, ESLint boundaries, role registry
- [ ] **Phase 2: Data Layer Contracts + Mock Infrastructure** - Domain types, Zod schemas, service contracts, seeded mock DB, canonical UI templates
- [ ] **Phase 3: Clients & Memberships** - Keystone vertical slice: clients, memberships, freezes, check-in, leads
- [ ] **Phase 4: Schedule** - Calendar views, occurrence drawer, recurring series, rooms/templates, waitlist, PT booking
- [ ] **Phase 5: Trainers / Staff** - Staff CRUD, compensation editor, payroll run, certifications widget
- [ ] **Phase 6: Finances** - Transactions, payments/expenses, cash register, canned reports, refunds
- [ ] **Phase 7: Dashboard + Notifications + Settings + Polish** - KPI grids, notification center, settings, a11y/perf pass

## Phase Details

### Phase 1: Foundation & Shell
**Goal**: A navigable app shell with role and theme toggles, a typed router, enforced architectural boundaries, and a single source of truth for role-based access — nothing feature-specific yet.
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, ROLE-01, ROLE-02, ROLE-03, ROLE-04, ROLE-05, UI-03, UI-04
**Research flag**: LOW (patterns well-documented; re-verify reui.io token/install specifics per OQ#15 before phase end)
**Success Criteria** (what must be TRUE):
  1. User opens the app and sees the shell (top bar with role switcher, theme toggle, notifications bell, profile; collapsible sidebar; content area) rendered entirely in Russian with DD.MM.YYYY/24h/Monday-week conventions
  2. User toggles role between Owner/Admin and Reception/Manager from the top bar; the sidebar menu and action affordances update immediately and the choice survives a hard reload
  3. User toggles theme between light / dark / system with no FOUC on reload; stored preference is applied by a blocking script in `index.html` before React mounts
  4. Developer attempting to import from `services/mock/**` or `services/http/**` inside a component or feature gets an ESLint error; raw palette colors (`bg-white`, `text-slate-900`) are also blocked
  5. A single `routeRegistry` + `can(role, action, resource)` helper exists and is consumed by sidebar filter, TanStack Router `beforeLoad` guard, and `<RoleGate>` — future phases only call into it, never duplicate its rules
**Plans**: 1 (PLAN-P1.md)
**UI hint**: yes

### Phase 2: Data Layer Contracts + Mock Infrastructure
**Goal**: A production-shaped data layer — domain types, Zod schemas, service contracts, a seeded mock DB behind the same interface a real HTTP client will use later — plus canonical List/Detail/Form UI templates that every feature will compose. No feature UI ships yet.
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09, DATA-10, DATA-11, DATA-12, UI-01, UI-02, UI-06
**Research flag**: MEDIUM (resolve OQ#1 mock transport choice is already closed to service-layer, but confirm URL filter/search contract OQ#3, avatar source OQ#16, notifications poll OQ#13, and pagination envelope shape before locking the seam)
**Success Criteria** (what must be TRUE):
  1. Every domain entity has a Zod schema in `entities/*` that validates both UI form input and mock service input, and produces branded IDs, ISO date strings, and `Money` integer-minor-units
  2. Flipping `VITE_API_MODE` between `mock` and (stub) `http` swaps implementations through `shared/api/services/index.ts` with zero UI changes; no component or hook branches on mode
  3. Mock services return `{ items, total, page, pageSize }` pagination envelopes, simulate 120-300ms latency, can be made to fail via a configurable rate, and throw uniform `DomainError { code, message, fields? }` that looks identical to future HTTP errors — including 403-analog errors when a Reception role calls an Owner-only endpoint
  4. Running the app shows `@faker-js/faker` seed-42 data (~50-100 clients, 2-3 months of schedule occurrences, proportional staff/payments) persisted under a versioned localStorage key; a dev toolbar (DEV-only) can reset mock data and toggle chaos mode
  5. Any screen built from the canonical List / Detail / Form(Wizard) templates in `shared/ui` gets empty, loading-skeleton, and error states as a three-state contract for free, and TanStack Query uses per-feature `xKeys` factories with loader `ensureQueryData` sharing the same key as hooks
**Plans**: TBD
**UI hint**: yes

### Phase 3: Clients & Memberships
**Goal**: The keystone vertical slice — everything a reception desk needs for clients, memberships, freezes, and check-in — proving every architectural rule from Phases 1-2 on the highest-leverage surface of the product.
**Depends on**: Phase 2
**Requirements**: CLIENT-01, CLIENT-02, CLIENT-03, CLIENT-04, CLIENT-05, CLIENT-06, CLIENT-07, CLIENT-08, CLIENT-09, CLIENT-10, CLIENT-11
**Research flag**: LOW (patterns known; resolves sub-plan-level OQs #3 URL filter contract, #6 family memberships, #7 access toast, #8 PT sales default, #11 visit deduction, #12 discount model during planning)
**Success Criteria** (what must be TRUE):
  1. User opens the Clients list and filters the virtualized table by status / tag / expiring-soon / *должник* / source, searches by phone or ФИО, and the URL query string reflects the active filters
  2. User opens any client detail page and sees six tabs (*Профиль · Абонементы · Посещения · Платежи · Записи · Заметки*); admin can sell a new membership through a wizard (template → validity start → discount → payment method) and freeze it through a modal that shows the recomputed `validUntil`
  3. Membership lifecycle is enforced end-to-end: state transitions `pending → active → { frozen | used-up | expired | cancelled }` are valid, overlapping freezes are rejected, `validUntil` is computed on read, and a client can hold multiple simultaneous memberships resolved by scope at check-in
  4. Reception opens the check-in screen, searches a client, sees status badge, deducts a visit on entry, and can mark a *Пропустить*; the expiring-soon list surfaces 7-day and 30-day buckets; leads/trials Kanban tracks trial conversion
  5. An Owner can create/edit membership template catalog entries; a Reception cannot — the attempt surfaces a 403-analog `DomainError` from the mock service, not just a hidden button
**Plans**: TBD
**UI hint**: yes

### Phase 4: Schedule
**Goal**: The most complex UI surface — a calendar with multiple views, an occurrence drawer, recurring-series editing with Outlook-style scope, rooms/templates catalogs, a waitlist inbox, and PT booking — all wired to the memberships-scope eligibility resolved in Phase 3.
**Depends on**: Phase 3
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, SCHED-06, SCHED-07, SCHED-08, SCHED-09, SCHED-10
**Research flag**: HIGH (validate react-big-calendar vs alternatives on a real drag-to-reschedule/resource-timeline prototype early in phase; recurring series + exceptions is subtle; capacity/waitlist invariants; membership-scope eligibility on enroll — per SUMMARY.md and OQ#2)
**Success Criteria** (what must be TRUE):
  1. User opens Schedule and switches between Week (default), Day, Month heatmap, Trainer swimlanes, and Agenda list views — all rendered with `locale={ru}`, Monday week start, 24h time, `Europe/Moscow` TZ
  2. Admin creates a one-off class or a recurring series; when editing a recurrence the scope picker asks "only this / this + future / whole series" and the series + exceptions model persists the choice correctly
  3. Reception opens a class occurrence drawer and sees the roster, toggles check-ins, cancels the occurrence, or adds notes; attempting to enroll a client past capacity is rejected by the mock service and offers waitlist
  4. Admin maintains Rooms and Class Templates catalogs (Reception cannot); the waitlist inbox shows outstanding requests across occurrences
  5. Reception books a personal training slot from the PT booking screen by picking a trainer's availability and a client
**Plans**: TBD
**UI hint**: yes

### Phase 5: Trainers / Staff
**Goal**: Staff management with a structured compensation model, payroll runs that snapshot rates per occurrence, and a certifications-expiring widget — unblocked by the schedule/PT data shipped in Phase 4.
**Depends on**: Phase 4
**Requirements**: STAFF-01, STAFF-02, STAFF-03, STAFF-04, STAFF-05, STAFF-06
**Research flag**: MEDIUM (compensation model superset across 6 archetypes; payroll edge cases — co-teaching, no-show, cancellations, historical rate snapshots)
**Success Criteria** (what must be TRUE):
  1. User opens the Staff list, filters by role and status, and opens a trainer detail page with six tabs (profile, certifications, schedule, PT clients, rate, earnings)
  2. Admin creates or edits a staff member and a Compensation record via a plain-language editor that maps to one of the 6 documented archetypes
  3. Admin runs payroll for a period and each computed payout line carries a per-occurrence rate snapshot, so editing a current rate does not retro-alter past payouts
  4. The certifications-expiring widget surfaces trainers whose certs expire within a configurable window
  5. Reception cannot access Payroll or Compensation editor — both route guard and mock service reject the attempt
**Plans**: TBD
**UI hint**: yes

### Phase 6: Finances
**Goal**: Full financial surface — unified transactions list, payment and expense flows, cash register sessions with reconciliation, refunds with audit trail, expense categories catalog, and eight canned reports — with all money in integer minor units end-to-end.
**Depends on**: Phase 5 (trainer earnings report depends on payroll from Phase 5; payment flow depends on memberships from Phase 3)
**Requirements**: FIN-01, FIN-02, FIN-03, FIN-04, FIN-05, FIN-06, FIN-07, FIN-08, FIN-09
**Research flag**: MEDIUM (cash register session semantics, reconciliation UX, canned report shapes, *касса* conventions; settle UI surface for fake receipt numbers / "чек отправлен" badge before coding)
**Success Criteria** (what must be TRUE):
  1. User opens the Finance dashboard and sees today/month KPI cards and charts; the Transactions list (unified in/out) filters by heavy criteria and paginates via the pagination envelope
  2. Reception creates a payment drawer entry against a client/membership; only Admin can create an expense drawer entry or an expense category
  3. Reception opens and runs a cash register session, and closes it with reconciliation (expected vs actual, discrepancy notes) — viewing or reopening other shifts is Owner-only
  4. Admin opens each of the eight canned reports (daily *касса*, monthly P&L, revenue by source, revenue by method, trainer earnings, outstanding balances, membership sales, refunds log) and sees consistent numbers driven by the mock DB
  5. Admin issues a refund through a dedicated flow that records an audit trail; all money values render as `1 234,56 ₽` with NBSP and are stored as integer minor units throughout
**Plans**: TBD
**UI hint**: yes

### Phase 7: Dashboard + Notifications + Settings + Polish
**Goal**: Assemble the Owner and Reception dashboards from now-populated services, ship the full notifications surface (bell, page, toasts, rules), complete Settings (club info, zones, working days, default theme), and run a final polish pass (a11y, responsive at 1366×768, dark-mode QA, route-level code splitting, bundle budget).
**Depends on**: Phase 6
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05, SET-01, SET-02, SET-03, SET-04, UI-05
**Research flag**: LOW (patterns known; settle bundle budget / route-splitting OQ#14; cmd+k OQ#4 include-or-defer decision happens here)
**Success Criteria** (what must be TRUE):
  1. Owner opens the dashboard and sees the full KPI grid (active memberships, expiring 7/30d, new clients, revenue today/month, MRR-ish, check-ins, classes today, class load %, trainer utilization, outstanding balance) plus revenue chart, by-source pie, today's timeline, top trainers, classes today, expiring soon, birthdays, and recent activity; Reception sees only the ops subset (no financial cards, no trainer revenue, no payroll)
  2. User clicks the notifications bell and sees the last 10 items grouped by day; opens the full notifications page and filters by type, severity, and read/unread; in-session events surface as sonner toasts while critical errors remain inline alerts/dialogs
  3. Admin opens the read-only notification-rules page and sees the event-type catalog with recipient mapping; Reception sees only ops-category notifications (membership expiring, class filled, low capacity, cash discrepancy)
  4. Admin opens Settings and edits Club info (TZ pinned to `Europe/Moscow`, currency pinned to RUB), Zones/scopes list, Working days & holidays calendar, and Default theme — the default theme applies to users without a persisted preference
  5. Final polish: keyboard navigation works end-to-end for primary flows, visible focus rings and correct labels on forms/dialogs/drawers, layout is usable at 1366×768 through desktop widths, dashboard aggregates come from a dedicated `DashboardService` with narrow Zustand selectors and route-level code splitting keeping the initial bundle under the agreed budget
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Shell | 1/1 | Done | 2026-04-21 |
| 2. Data Layer Contracts + Mock Infrastructure | 0/TBD | Not started | - |
| 3. Clients & Memberships | 0/TBD | Not started | - |
| 4. Schedule | 0/TBD | Not started | - |
| 5. Trainers / Staff | 0/TBD | Not started | - |
| 6. Finances | 0/TBD | Not started | - |
| 7. Dashboard + Notifications + Settings + Polish | 0/TBD | Not started | - |

---
*Roadmap defined: 2026-04-21 by `gsd-roadmapper`. Granularity: fine. Coverage: 79/79 v1 requirements mapped.*
