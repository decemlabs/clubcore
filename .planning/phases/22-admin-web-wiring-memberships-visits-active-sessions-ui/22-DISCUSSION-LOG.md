# Phase 22: admin-web wiring — memberships + visits + active sessions UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 22-admin-web-wiring-memberships-visits-active-sessions-ui
**Areas discussed:** Gym-hours source for FE-08d, Routes layout + sidebar + check-in placement, Mock realism + client-detail composition

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Sessions UI vs Phase 23 timing | FE-09 needs GET /api/v1/auth/sessions + per-family revoke — neither is in schema.d.ts yet. Phase 23 owns the endpoints and is parallel-eligible. Decide: defer FE-09 to a Phase-22 sub-plan after Phase 23 merge, reorder Phase 23 before Phase 22, or punt FE-09 to v1.3. | (skipped — Claude defaulted to "defer to last sub-plan inside Phase 22, gated on Phase 23 main merge" per D-22-2) |
| Gym-hours source for FE-08d | REQUIREMENTS says 'GET /api/v1/visits/_meta (or env-mirrored config)'. The endpoint does NOT exist in backend (verified). Decide: add /visits/_meta endpoint (forces drift-gate refresh inside Phase 22) vs mirror gym_hours via VITE_GYM_HOURS_* env in admin-web vs hardcoded for now. | ✓ |
| Routes layout + sidebar + check-in placement | routeRegistry has 6 entries today. Decide: sidebar labels/icons for memberships / membership-plans / visits, whether /visits IS the reception check-in page or split into /visits/check-in + /visits/history, owner-only items hidden vs greyed for reception, /clients row-click navigation to /clients/$clientId. | ✓ |
| Mock realism + client-detail composition | Two coupled choices: (1) mock/http parity for memberships/visits (full lifecycle vs minimal stubs vs read-only mock + http-only mutations); (2) Pattern α layout on clients.$clientId.tsx (stacked blocks vs tabs), placement of 'Sell membership' (MEM-EP-03) and owner-only cancel controls. | ✓ |

---

## Gym-hours source for FE-08d

| Option | Description | Selected |
|--------|-------------|----------|
| A. GET /api/v1/visits/_meta endpoint | Phase 22 adds the backend route + Pydantic schema + tests; codegen regenerates schema.d.ts mid-phase. Single source of truth, no env-sync risk. ~30 LOC backend + ~1 hook. | ✓ |
| B. VITE_GYM_HOURS_* env mirror | No backend change. admin-web reads VITE_GYM_HOURS_START/END at boot. .env.example must stay in sync with backend manually. | |
| C. Hardcoded with TODO | Trivially fast; revisits in v1.3+ when ops actually wants to change hours. | |

**User's choice:** A. GET /api/v1/visits/_meta endpoint
**Notes:** Recommended option accepted with no overrides.

### `/visits/_meta` auth gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Require login (view, visits) | Gated behind Depends(require_permission(view, visits)). Reception+owner can read; consistent with the rest of /api/v1/visits/*. | ✓ |
| Public (no auth) | Anyone can fetch gym hours. Simpler; mirrors the public /healthz pattern. No-secret data. | |

**User's choice:** Require login (view, visits)
**Notes:** Recommended option accepted.

### Include server clock (nowMsk) in `/visits/_meta` response?

| Option | Description | Selected |
|--------|-------------|----------|
| No — keep response static | {gymHoursStart, gymHoursEnd} only. Response is cacheable (Cache-Control: public, max-age=300). FE uses local Date() and accepts skew; worst case is a 409 on submit + toast. | ✓ |
| Yes — add nowMsk | {gymHoursStart, gymHoursEnd, nowMsk}. Response must be no-cache. Defends against client clock drift on a reception PC. | |

**User's choice:** No — keep response static
**Notes:** Recommended option accepted. v1.3+ may revisit if reception PCs prove to have bad NTP.

---

## Routes layout + sidebar + check-in placement

### What is `/_protected/visits.tsx`?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure check-in page | Search clients by phone prefix → disambiguation → 'Check in' button. Today's-history shown inline ONLY for the matched client (the 'already checked in HH:MM' badge per FE-08b). No global history feed; full history lives on /clients/$clientId. | ✓ |
| Combined check-in + today's feed | Top: search+check-in. Bottom: today's check-ins list (reception audit). Adds a list/feed surface; useful for end-of-day reconciliation. | |
| Tabs: 'Отметить' / 'История' | Two-tab layout. History tab is paginated all-time (filter by date, paginated). | |

**User's choice:** Pure check-in page
**Notes:** Single-purpose route. Audit reconciliation deferred until the audit-log read UI ships.

### Sidebar treatment of owner-only `/membership-plans` for reception?

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden entirely for reception | If can(reception, view, membership-plans)=false, the sidebar entry is filtered out. Mirrors /finance and /settings which are already filtered for reception today via routeRegistry+can(). | ✓ |
| Greyed out with lock icon | Always rendered; clicking shows a 'Owner only' tooltip / does nothing. More discoverable but visually noisy for reception. | |

**User's choice:** Hidden entirely for reception
**Notes:** Mirrors existing precedent.

### Row-click on `/clients` list → `/clients/$clientId` navigation?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — row click navigates | ClientsTable rows become Link to /clients/$clientId. Inline edit/delete buttons stay on the row (event.stopPropagation). Minimal code change, expected admin-panel UX. | ✓ |
| No — detail page reached only via 'Open' action | Add an explicit 'Open' / 'Details' button per row; row click stays inert. Safer if power users rely on row-level inline actions today. | |

**User's choice:** Yes — row click navigates

### Sidebar order + labels for the new v1.2 entries?

| Option | Description | Selected |
|--------|-------------|----------|
| Reception-first | / → Главная / /visits → 'Отметки' (LogIn icon) / /clients → Клиенты / /memberships → 'Абонементы' (Ticket) / /membership-plans → 'Тарифы' (LayoutGrid, owner-only) / /schedule / /staff / /finance / /settings. Reception's most-used route (Отметки) sits high; sales/catalog are grouped together. | ✓ |
| Domain-grouped | / → Главная / /clients / /memberships / /visits / /membership-plans (owner-only) / /schedule / /staff / /finance / /settings. Workflow order — sell membership, then check in, with the catalog on the side. | |
| Two sidebar groups | Group A 'Операции': / /visits /clients /memberships. Group B 'Каталог и администрирование': /membership-plans /schedule /staff /finance /settings. Visually clearer; needs a small Sidebar.tsx refactor to render group headers. | |

**User's choice:** Reception-first
**Notes:** Optimised for reception's check-in frequency.

### Which icon for `/visits`?

| Option | Description | Selected |
|--------|-------------|----------|
| LogIn | lucide LogIn arrow-into-door. Reads as 'check in'. Already in lucide-react. | ✓ |
| ScanLine | Suggests scanning / kiosk; closer to future hardware turnstile, less semantic for manual phone-search. | |
| CircleCheck | Generic 'success/check'; might clash with status indicators elsewhere. | |

**User's choice:** LogIn

---

## Mock realism + client-detail composition

### Mock realism for memberships + visits services?

| Option | Description | Selected |
|--------|-------------|----------|
| B. Read-only mock + http-only mutations | Seeded fixtures power list/get; create/cancel/check-in throw DomainError('mock_not_implemented'). Mock tests cover RBAC + shape. Demos: browsing works, selling/checking-in does not. Cost: ~1 day. Dev still runs without backend for the read paths used by /clients/$clientId blocks. | ✓ |
| A. Full parity (mirror v1.1 clients precedent) | Mock implements the full lifecycle: INCLUSIVE end_date, snapshot-on-create, 1/day visit rule, gym-hours window, owner-only cancel. New test files mirror v1.1 layout. Cost: ~2-3 days; one of the biggest plans in Phase 22. Best if you want offline storybook-quality demos. | |
| C. Minimal seeded stubs | 5-10 hand-written fixtures, mutations succeed but skip validation. Shape tests only. Cost: hours. Risk: silent drift between mock and real UX. | |

**User's choice:** B. Read-only mock + http-only mutations
**Notes:** Backend tests already cover the lifecycle invariants; mock parity for writes would re-implement them in localStorage for no new coverage.

### Client-detail page (`clients.$clientId.tsx`) layout?

| Option | Description | Selected |
|--------|-------------|----------|
| A. Stacked blocks | Vertical stack: Profile card → MembershipsBlock (with 'Продать абонемент' CTA + owner-only cancel inline on each row) → RecentVisitsBlock. Matches FE-07 wording verbatim. Mobile-friendly. No tab routing complexity. | ✓ |
| B. Tabs (Обзор / Абонементы / Визиты) | Three tabs with TanStack Router search-param state ?tab=memberships. Cleaner separation but adds search-schema + per-tab loaders. Each tab can ensureQueryData independently. | |
| C. Two-column desktop layout | Profile card left, Memberships+Visits stacked right. Wastes horizontal space on smaller laptops; needs responsive collapse to A. | |

**User's choice:** A. Stacked blocks

### Where does 'Sell membership' (POST /api/v1/memberships) live?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline CTA on client-detail | 'Продать абонемент' button at the top of MembershipsBlock on /clients/$clientId. Opens a Dialog with plan dropdown + paidAt + notes. Reception's natural flow: client walks in → open profile → sell. No separate route. | ✓ |
| Toolbar action on /memberships list | '+ Продать' button in /memberships toolbar opens a dialog with client autocomplete + plan + paidAt. Useful for back-office bulk entry; one extra click for the walk-in flow. | |
| Both | Same Dialog component reused; reception uses inline, owner can also bulk-sell from /memberships. ~30 LOC extra. | |

**User's choice:** Inline CTA on client-detail
**Notes:** Walk-in flow only; bulk-sell deferred.

---

## Claude's Discretion

- **FE-09 sequencing (Sessions UI)** — area was offered for discussion but not selected. Defaulted to D-22-2: FE-09 ships as the LAST sub-plan inside Phase 22, ordered AFTER Phase 23 merges into main. Phase 22 verification gates on FE-09 being green; if Phase 23 slips beyond v1.2 deadline, user re-evaluates whether to punt FE-09 to v1.3.
- **Cancel button placement** (CD-04) — owner-only inline per-row in `<MembershipsBlock>` (on `/clients/$clientId`) AND on each row of `/memberships` list page. Reception sees no cancel UI. Mirrors existing `<RoleGate>` precedent.
- **Plan layout** (CD-01) — 5 sub-plans suggested: 22-01 (backend `/visits/_meta` + codegen), 22-02 (features/memberships + routes + sidebar), 22-03 (features/visits + check-in route + sidebar), 22-04 (Pattern α route + ESLint + D-3 + D-5), 22-05 (FE-09 sessions UI, blocked on Phase 23). 22-02 and 22-03 are parallel-eligible.
- **Atomic commits per task** (CD-02) — same as v1.1 + Phase 21 precedent.
- **No Storybook stories shipped** (CD-03) — visual regression revisits in v1.3+.
- **D-22-10 D-2 filter implementation** — client-side by default (uses returned endDate); plan-phase agent verifies whether `paths['/api/v1/memberships']['get']['parameters']['query']` already exposes `expiringWithinDays`; if so, use the backend filter.
- **NavKey enum extension** — plan-phase decides whether to add `'visits' | 'memberships' | 'membership-plans'` to the `RouteEntry.navKey` enum or relax the type.
- **Owner sign-off on D-5 days-remaining DM string** — plan-phase surfaces the exact new copy at execution time per Phase 20 AUTH-TG-11 precedent.

## Deferred Ideas

- Full mock parity for memberships+visits write paths (storyboard-quality offline demo) — v1.3+
- Tabbed/two-column layout on `/clients/$clientId` — v1.3+ if 4+ blocks
- `/memberships` "+ Продать" toolbar dialog (bulk-sell back-office flow) — v1.3+
- `/visits` "today's check-ins" feed (audit reconciliation) — depends on audit-log read UI
- `nowMsk` field on `/visits/_meta` (clock-skew defense) — v1.3+ if NTP issues
- `maxCheckinPerDay` / `channelsEnabled` on `/visits/_meta` (multi-zal config) — v1.3+
- Backend `?expiringWithinDays=` query param on `/api/v1/memberships` — promote if perf warrants
- Storybook setup (visual regression) — v1.3+
- D-1, D-4, D-6, D-7 cheap-win differentiators — already deferred by FE-10
- Photo turnstile / geofencing / per-class booking integration — REQUIREMENTS deferred
- Membership renewal flow / freeze / visit-count / hybrid plans — REQUIREMENTS deferred
- Tag taxonomy / bulk CSV import / photo upload (clients) — REQUIREMENTS deferred
- Audit log read UI — REQUIREMENTS deferred
- Real auth UX polish (password reset via Telegram bot DM, HaveIBeenPwned) — REQUIREMENTS deferred
- Punt FE-09 to v1.3 if Phase 23 slips badly — fallback only
