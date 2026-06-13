# Phase 104: Dashboard, Reports + Settings - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the admin-app **dashboard** (landing KPIs), **reports** (all 4 aggregate reports
+ CSV export), **audit log** (owner-only, filters + CSV), and **settings** (profile +
theme + active sessions + owner-only user admin) from mocks to the real backend over
the P100 transport seam. The last domain-wiring phase.

**In scope:** dashboard KPI composition from existing `/reports/*` + bookings/memberships
(role-gated cards); reports page with revenue/clients/visits/trainers + CSV download;
audit-log screen (filters, keyset pagination, CSV, owner-only); settings profile
(read/edit-if-endpoint-exists + theme) + active sessions (list/revoke); owner-only Users
admin (invite/list/deactivate/reactivate/soft-delete); a shared `downloadCsv()` helper;
nav entries for any newly-reachable owner-only screens.

**Out of scope:** admin-web deletion + RBAC re-home enforcement (Phase 105); OpenAPI
handoff + milestone gate (Phase 106); any new backend endpoints (wire-only). Multi-branch
/ hidden-for-future screens stay hidden. No staff-chat backend → ClientMessages hidden.
</domain>

<decisions>
## Implementation Decisions

### Dashboard composition & reception
- Dashboard `/` composes KPIs from the **existing `/api/v1/reports/{revenue,clients,visits,
  trainers}`** + bookings/memberships reads (NO new `/dashboard` endpoint — wire-only).
  Empty-data guards (reuse P103 zero-fill + null guards) prevent NaN/null crashes (criterion 1).
- **Universal landing dashboard with role-gated cards:** owner sees the full set; the
  **owner-only KPI / Occupancy / Revenue / TopTrainers cards are gated via
  `can(role,'view','reports')`** (those data sources are owner-only — reception fires ZERO
  owner-only calls via `enabled:`). **Reception sees only the operational widgets**:
  ScheduleToday (bookings — both roles) + ExpiringMemberships (memberships — both roles).
- **Wire:** KpiStrip, OccupancyHours/Now (reports/visits), RevenueChart (reports/revenue),
  TopTrainers (reports/trainers) — all owner-only; ScheduleToday (bookings), ExpiringMemberships
  (memberships ?expiring) — both roles. **Hide:** ClientMessages (no staff-chat backend).
  ActivityFeed → owner-only from `/audit-log` if cheap, else hide (note).

### Reports page + CSV export
- Reports page renders **all 4 reports**: revenue (groupBy day|month — wired P103), visits
  (wired P103), **clients** (NEW: `/reports/clients?fromDate&toDate&within` →
  `{activeCount, expiringCount, newClientsCount, withinDays}`), **trainers** (NEW:
  `/reports/trainers?fromDate&toDate` → `{rows[{trainerId,name,sessionCount,totalHours,
  uniqueClients,utilizationPct,totalRevenueKopecks,...}]}`). Extend `features/reports`.
- **Shared `downloadCsv(endpoint, filename, query)` helper** (new, e.g. `src/api/csv.ts` or
  in `api/client.ts`): `fetch(url,{credentials:'include'})` → `res.blob()` → anchor download.
  GET is CSRF-exempt (no header needed). Server returns UTF-8 BOM + RFC-4180 (Cyrillic-safe).
  Wire CSV buttons for all 4 reports (`/reports/{revenue,clients,visits,trainers}.csv`) +
  audit-log (`/audit-log.csv`). On error → Russian toast.
- Owner-only (Отчёты already nav-gated, P100/P103). Lock-EmptyState for reception.

### Audit log
- Wire `AuditPage` to **`GET /api/v1/audit-log`** (owner-only): filters `actorUserId`,
  `actorEmailSnapshot`, `resourceType`, `action`, `from`, `to`, `page`, `pageSize`;
  response `{items,total,page,pageSize}` ordered **`created_at DESC, id DESC`** (stable
  keyset pagination — criterion 3). Item fields: id/createdAt/actorUserId/actorEmailSnapshot/
  action/resourceType/resourceId/payload(JSONB). CSV via `downloadCsv` → `/audit-log.csv`.
- **Ensure AuditPage is reachable owner-only** — confirm its route/nav; add a «Журнал
  действий» owner-only nav entry (`ownerResource:'audit-log'`) if missing. Reception → gated
  «Недостаточно прав» state (zero owner-only calls via `enabled:`).

### Settings (profile / sessions) + Users
- **Profile edit — planner MUST confirm the endpoint first:** check for `PATCH /api/v1/auth/me`
  (or `/users/me`). **If it exists → wire ProfileSection edit** (fullName + any supported
  fields, CSRF on the mutation). **If NOT → profile is READ-ONLY** (display name/email/role
  from `GET /auth/me`) + **theme** (already client-side via use-theme) and edit is **deferred
  with an explicit note** (do not invent an endpoint). Either way theme toggle stays.
- **Active sessions:** wire `GET /api/v1/auth/sessions` (paginated: familyId/createdAt/
  lastUsedAt/userAgent/channel/isCurrent) + `POST /api/v1/auth/sessions/{familyId}/revoke`
  (CSRF, 204, idempotent). Self-service (any authenticated role). Mark the current session;
  **self-revoke → clears cookies → redirect to /login** (reuse the authBus/session-expiry path).
- **Users admin (owner-only):** invite `POST /api/v1/users {email,fullName,role}` (+`?includeInviteLink`
  → show the invite URL), list `GET /api/v1/users` (paginated; status active|pending_invitation),
  deactivate `PATCH /users/{id}/deactivate` (409 self/last-owner/already-inactive guards),
  reactivate `PATCH /users/{id}/reactivate`, soft-delete `DELETE /users/{id}`, optional
  invitation revoke. Surface in **Settings→Team section (reuse the mock team UI) OR a dedicated
  owner-only screen** (Claude's discretion). Reception → gated. can() resource `users`.

### Conventions (all)
- Wire camelCase; `Schema.parse(raw).data`; `ApiError` from feature module (ESLint boundary);
  Russian-only copy; admin-app semicolons; integer kopecks via `formatRub(kopecks/100)`;
  MSK dates via the P103 `mskTodayISO`/`mskDaysAgoISO`/`parseISO` helpers (no date-fns-tz);
  `EmptyState` uses `message` prop. Keep mock files behind `VITE_API_MODE=mock`; remove the
  dead default-mock branch for wired screens. Reception makes ZERO owner-only API calls.

### Claude's Discretion
- Dashboard card decomposition + role-gating wiring; Reports page tab/card layout; the
  `downloadCsv` helper location; Users-admin placement (Settings→Team vs dedicated screen);
  audit filter controls; test organization — following P100–P103 exemplars.
</decisions>

<code_context>
## Existing Code Insights (verified — wire camelCase)

### Backend endpoints (all reports/audit/users OWNER-ONLY; profile/sessions self-service)
- **Reports** (owner-only): `/reports/revenue` (groupBy day|month), `/reports/visits`
  (daily/hourly sparse + averagePerDay), `/reports/clients` (activeCount/expiringCount/
  newClientsCount/withinDays; param `within` 1-30), `/reports/trainers` (rows[] per-trainer
  usage/revenue). `.csv` variants for ALL FOUR (StreamingResponse, UTF-8 BOM, RFC-4180).
- **Audit** (owner-only): `GET /api/v1/audit-log` (filters actorUserId/actorEmailSnapshot/
  resourceType/action/from/to/page/pageSize; ordered created_at DESC,id DESC) + `.csv`.
- **Auth/profile/sessions** (self-service): `GET /auth/me`; **`PATCH /auth/me` — EXISTENCE
  UNCONFIRMED, planner verifies**; `GET /auth/sessions` (paginated, familyId/createdAt/
  lastUsedAt/userAgent/channel/isCurrent); `POST /auth/sessions/{familyId}/revoke` (CSRF,204).
- **Users** (owner-only, CSRF): `GET /users` (paginated; active?/deleted?), `POST /users`
  ({email,fullName,role}, ?includeInviteLink → inviteLinkUrl + invitationExpiresAt),
  `PATCH /users/{id}/deactivate` (409 guards), `PATCH /users/{id}/reactivate`,
  `DELETE /users/{id}` (soft-delete), `POST /users/invitations/{tokenId}/revoke`.

### admin-app current (files to flip — apps/admin-app/src/)
- `features/dashboard/{api.ts,types.ts}` (useDashboard) + `mocks/dashboard.ts`;
  page `pages/dashboard/DashboardPage.tsx` (KpiStrip/Occupancy/ScheduleToday/Expiring/
  RevenueChart/TopTrainers/ClientMessages/ActivityFeed).
- `features/reports/*` (EXISTS P103: useRevenueReport/useVisitsReport + fillBuckets + downloadCsv?)
  — EXTEND with useClientsReport + useTrainersReport; page `pages/reports/ReportsPage.tsx`.
- `features/audit/{api.ts}` (useAuditLog mock) + `mocks/audit.ts`; page `pages/audit/AuditPage.tsx`.
- `features/settings/{api.ts}` (useSettings mock); page `pages/settings/SettingsPage.tsx`
  (ProfileSection + SecuritySection[sessions] + TeamSection[users] + others).
- **NEW** `features/users/` (owner CRUD) + maybe `features/profile/`/extend auth; `src/api/csv.ts`.
- **Exemplars:** P100 `features/auth` (useSession, authBus self-expiry for self-revoke);
  P101-103 `features/{clients,memberships,reports,payments}` (staffRequest, owner-gating
  enabled:can pattern, Lock-EmptyState). P103 `features/reports` (fillBuckets, mskTodayISO).
- can() resources (admin-app `shared/session/can.ts`, ported P100): `reports`, `audit-log`,
  `users`, `settings`, `profile`, `dashboard` — owner-only matrix already includes reports/
  audit-log/users (verify). nav-items.ts: Отчёты gated; add audit + (maybe) users entries.

### admin-web analog
- `features/auth/` profile + active-sessions UI (http-only, D-22-2) — sessions porting analog.
- v1.6 users module exists backend-side; admin-web users-admin UI may exist — check
  `apps/admin-web/src/features/users/` for an invite/deactivate analog. Audit/reports/CSV
  have NO admin-web UI → admin-app is first; use P100-P103 patterns.
</code_context>

<specifics>
## Specific Ideas

- Dashboard KPIs are owner-only (reports) → reception dashboard is operational-only; gate cards, don't 403.
- CSV download is a net-new pattern: fetch credentials:include → blob → anchor; GET no CSRF.
- PATCH /auth/me existence is UNCONFIRMED — profile edit may be read-only+deferred.
- Self-revoke of the current session must log the user out (authBus path).
- Users-admin is the FIRST UI for the users module (no admin-web analog confirmed).
- All money kopecks; MSK dates; Russian-only.
</specifics>

<deferred>
## Deferred Ideas

- admin-web deletion + RBAC re-home enforcement → Phase 105.
- OpenAPI handoff + full milestone gate → Phase 106.
- Profile edit — deferred ONLY if no PATCH /auth/me endpoint exists.
- ClientMessages dashboard widget — no staff-chat backend (hidden).
- Roles/permission-matrix editor (RolesPage ComingSoon) — future (Users admin ≠ Roles editor).
- Multi-branch / hidden-for-future screens — stay hidden.
</deferred>
