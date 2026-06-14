---
phase: 104-dashboard-reports-settings
verified: 2026-06-13T22:55:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Owner lands on / — verify KPI/Occupancy/Revenue/TopTrainers cards show real (non-zero or coherently zero) data from the backend; KpiStrip shows kopeck amounts as formatted RUB."
    expected: "All four owner-only widgets render with data; no NaN or blank values; no JS errors in console."
    why_human: "Requires live backend; automated tests mock the data layer. NaN guard code is verified but real data flow requires a browser + running API."
  - test: "Reception lands on / — open Network tab and verify zero calls to /api/v1/reports/* from the dashboard."
    expected: "Only /api/v1/bookings and /api/v1/memberships requests appear; no /reports/* calls at all."
    why_human: "Browser network inspection only; role-switch via dev login."
  - test: "Owner opens Reports page — switch each of the four tabs (Выручка/Клиенты/Посещения/Тренеры) and click «Экспорт CSV» on each."
    expected: "Each tab renders live data; clicking CSV downloads a .csv file (browser save dialog or auto-download); error toast shown if backend unavailable."
    why_human: "CSV blob download is a browser-side side effect; can only be verified in a real browser against a live backend."
  - test: "Owner opens «Журнал действий» page — apply a filter (e.g. by resourceType), paginate to page 2, export CSV."
    expected: "Filtered result updates the list; pagination changes page; CSV downloads current filtered data."
    why_human: "Server-side filtering and keyset pagination correctness requires a live backend with audit events."
  - test: "Owner clicks a row in the Audit log — open the detail modal and inspect the payload display."
    expected: "JSONB payload renders as pretty-printed JSON in a <pre> block; no HTML tags injected; arbitrary values display as escaped text."
    why_human: "XSS guard (no dangerouslySetInnerHTML) is grep-verified, but visual correctness of rendering for edge-case payloads needs human eyes."
  - test: "Owner opens Settings — verify Profile section shows real fullName/email/role from GET /auth/me (read-only) plus working theme toggle; Sessions section lists real active sessions with «Сейчас» badge on the current one."
    expected: "Profile: real name/email/role displayed; no edit fields. Sessions: real list with «Сейчас» badge on current; «Завершить» on other rows."
    why_human: "Requires live backend and real authenticated session."
  - test: "Owner clicks «Завершить» on a non-current session row."
    expected: "Row disappears; toast 'Сессия завершена' appears."
    why_human: "Session revoke is a live POST mutation; requires a second active session to test."
  - test: "Owner clicks «Выйти везде», confirms the modal — verify redirect to /login?state=expired."
    expected: "Confirm modal appears; on confirm, app navigates to /login; session cookie cleared."
    why_human: "Self-revoke via authBus path requires a live session and browser observation of navigation."
  - test: "Owner opens Settings→Team — verify real user list appears with status/role badges; click «+ Пригласить» and invite a test user."
    expected: "Real user list renders; invite modal opens; after submission the success view shows an invite link URL to copy."
    why_human: "Requires live backend /users endpoint and real invite flow."
  - test: "Owner deactivates a user, then reactivates — verify 409 guard: attempt to deactivate self or the only owner."
    expected: "Deactivate/reactivate confirmations fire correctly; self row shows «Это вы» with disabled actions; deactivating last owner shows Russian error toast with 'cannot_deactivate_last_owner'."
    why_human: "409 error path requires a real backend response; toast mapping code is verified but needs live round-trip."
  - test: "Reception opens Reports page, Audit page, and Settings→Team — verify Lock-EmptyState shown and network tab has zero calls to /reports/*, /audit-log, or /users."
    expected: "Lock-EmptyState renders on each page; network tab shows no owner-only API calls."
    why_human: "Zero-call assertion requires browser network tab observation."
---

# Phase 104: Dashboard, Reports + Settings Verification Report

**Phase Goal:** The landing dashboard shows live KPI data; all four reports render with CSV export; owner can manage users and profile/sessions — all on real data.
**Verified:** 2026-06-13T22:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `downloadCsv()` fetches owner-only CSV endpoints with cookie credentials, triggers browser download, throws parseable Error on non-2xx | VERIFIED | `apps/admin-app/src/api/csv.ts` — `credentials:'include'`, `res.blob()`, `URL.createObjectURL`, `revokeObjectURL`, `throw new Error(body.message\|\|'Download failed')` |
| 2 | `appendQuery` and `parseErrorBody` are exported from `api/client.ts` | VERIFIED | Lines 83, 122 in `client.ts`: `export async function parseErrorBody`, `export function appendQuery` |
| 3 | `useClientsReport` and `useTrainersReport` fetch `/reports/clients` and `/reports/trainers`, owner-gated via `can(role,'view','reports')` | VERIFIED | `features/reports/api.ts` lines 106-136; both hooks have `enabled: can(role, 'view', 'reports')` |
| 4 | `useAuditLog` fetches `/audit-log` with server-side filter params + page/pageSize=25, owner-gated via `can(role,'view','audit-log')` | VERIFIED | `features/audit/api.ts` lines 39-60; `pageSize: 25`; `enabled: can(role, 'view', 'audit-log')`; `export { ApiError }` at line 61 |
| 5 | Owner dashboard renders KPI/Occupancy/Revenue/TopTrainers + Schedule + Expiring; reception renders only Schedule + Expiring with zero owner-only calls; ClientMessages and OccupancyNow hidden | VERIFIED | `DashboardPage.tsx` — `isOwner = can(role,'view','reports')` at line 41; owner-only section under `{isOwner && ...}` block; `ClientMessages` and `OccupancyNow` in comments only; `NaN`-safe `safeInt()` in `KpiStrip.tsx` |
| 6 | Reports page renders 4 real-data tabs with per-tab CSV export; reception sees Lock-EmptyState with zero API calls | VERIFIED | `ReportsPage.tsx` — outer component returns Lock-EmptyState before hooks if `!can(role,'view','reports')`; `ReportsPageContent` calls all 4 hooks; `downloadCsv` called with 4 `.csv` endpoints (lines 161, 169, 177, 185); `useReports()` legacy mock not imported |
| 7 | Audit page renders `/audit-log` with server-side filters + page=25 keyset pagination + CSV; JSONB payload via `JSON.stringify` only, never `dangerouslySetInnerHTML` | VERIFIED | `AuditPage.tsx` — outer guard before `AuditPageContent`; `filter.*setPage(1)` resets on filter change; `audit-log.csv` CSV call; `AuditDetailModal.tsx` — `JSON.stringify(event.payload, null, 2)` inside `<pre>`, no `dangerouslySetInnerHTML` |
| 8 | «Журнал действий» owner-only nav entry (`ownerResource:'audit-log'`) present | VERIFIED | `nav-items.ts` line 82-87: `label:'Журнал действий'`, `ownerOnly:true`, `ownerResource:'audit-log'` |
| 9 | ProfileSection read-only (name/email/role from GET /auth/me + theme); SecuritySection lists real sessions with «Сейчас» badge, per-row revoke, self-revoke via authBus→/login | VERIFIED | `features/settings/api.ts` — `useSessions`, `useRevokeSession`, `useRevokeCurrentSession` (calls `publishSessionExpired()`); `SectionsTop.tsx` — `useSession()`, `useSessions()`, «Выйти везде» at line 291, «обратитесь к владельцу» at line 117; no PATCH /auth/me |
| 10 | Owner Settings→Team: real user list, invite with copy-link, deactivate/reactivate/delete/revoke-invitation with 409 guards; reception Lock-EmptyState, zero users calls | VERIFIED | `features/users/api.ts` — `useUsers(enabled: can(role,'list','users'))`, `useInviteUser`(+`includeInviteLink:true`), `useDeactivateUser`, `useReactivateUser`, `useDeleteUser`, `useRevokeInvitation`; `SectionsBottom.tsx` — `cannot_deactivate_last_owner` toast map at line 491, «Это вы» at line 521, `can(role,'list','users')` guard at line 701/707 |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/api/csv.ts` | `downloadCsv()` blob-download helper | VERIFIED | Exports `downloadCsv`; imports `appendQuery`/`parseErrorBody` from `@/api/client`; substantive implementation |
| `apps/admin-app/src/features/reports/schemas.ts` | `ClientsReportSchema` + `TrainersReportSchema` + query types | VERIFIED | `ClientsReportSchema` at line 72; `TrainerRowSchema` + `TrainersReportSchema` at lines 86-99; `totalRevenueKopecks` field present |
| `apps/admin-app/src/features/audit/schemas.ts` | `AuditEventSchema` + `AuditLogResponseSchema` + `AuditFilter` | VERIFIED | All three present; `payload: z.record(z.unknown()).nullable()` at line 20 |
| `apps/admin-app/src/features/audit/api.ts` | `useAuditLog` owner-gated paginated query + `ApiError` re-export | VERIFIED | `useAuditLog` with `pageSize: 25` + `enabled: can(role,'view','audit-log')`; `export { ApiError }` |
| `apps/admin-app/src/features/dashboard/api.ts` | `useScheduleToday` + `useExpiringMemberships` + re-exported owner-only report hooks | VERIFIED | All four owner hooks re-exported; `useDashboard` mock absent; `withinDays:'7'` in memberships call |
| `apps/admin-app/src/pages/dashboard/DashboardPage.tsx` | Role-gated dashboard composition | VERIFIED | `can(role,'view','reports')` gate at line 41; `{isOwner && ...}` blocks |
| `apps/admin-app/src/pages/reports/ReportsPage.tsx` | 4-tab real-data reports + per-tab CSV | VERIFIED | `downloadCsv` present; all 4 `.csv` endpoints; `useClientsReport` + `useTrainersReport` wired; no `useReports()` legacy call |
| `apps/admin-app/src/pages/audit/AuditPage.tsx` | Real audit log + filters + pagination + CSV + owner gate | VERIFIED | `useAuditLog`, `audit-log.csv`, `can(role,'view','audit-log')` early return |
| `apps/admin-app/src/layouts/AppLayout/nav-items.ts` | «Журнал действий» owner-only nav entry | VERIFIED | Present at lines 82-87 with `ownerOnly:true`, `ownerResource:'audit-log'` |
| `apps/admin-app/src/features/settings/schemas.ts` | `SessionSchema` + `SessionsListResponseSchema` | VERIFIED | Both present; `isCurrent: z.boolean()` at line 21 |
| `apps/admin-app/src/features/settings/api.ts` | `useSessions` + `useRevokeSession` + self-revoke authBus path | VERIFIED | All three exported; `publishSessionExpired()` called in `useRevokeCurrentSession` on success |
| `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` | Read-only ProfileSection + wired SecuritySection | VERIFIED | `useSession` + `useSessions` imported; «обратитесь к владельцу» + «Выйти везде» present |
| `apps/admin-app/src/features/users/schemas.ts` | `UserSchema` + `UsersListResponseSchema` + `UserInviteResponseSchema` | VERIFIED | All three present; `status` enum includes `pending_invitation`/`deactivated` |
| `apps/admin-app/src/features/users/api.ts` | Owner-gated `useUsers` + invite/deactivate/reactivate/delete/revoke-invitation mutations | VERIFIED | All five mutations exported; `enabled: can(role,'list','users')`; `includeInviteLink:true`; `export { ApiError }` |
| `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` | Wired TeamSection with invite modal + row actions | VERIFIED | `useUsers` wired; `can(role,'list','users')` gate; `cannot_deactivate_last_owner` mapped; «Это вы» self-badge |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `csv.ts` | `api/client.ts` `appendQuery`/`parseErrorBody` | `import { appendQuery, parseErrorBody } from '@/api/client'` | WIRED | Import confirmed; both functions are exported from `client.ts` |
| `features/reports/api.ts` | `/api/v1/reports/clients` + `/api/v1/reports/trainers` | `staffRequest('get', '/api/v1/reports/clients', ...)` | WIRED | Both calls present; owner-gated via `enabled:can(role,'view','reports')` |
| `features/audit/api.ts` | `/api/v1/audit-log` | `staffRequest('get', '/api/v1/audit-log', ...)` | WIRED | Call present with spread filter params + `pageSize:25`; `enabled:can(role,'view','audit-log')` |
| `DashboardPage.tsx` | `useRevenueReport`/`useVisitsReport`/`useTrainersReport` | `isOwner` condition + re-exported hooks | WIRED | Owner-only hooks mount only when `isOwner=true`; each hook retains its own `enabled:can()` gate |
| `features/dashboard/api.ts` | `/api/v1/bookings` + `/api/v1/memberships` | `staffRequest('get', ...)` no owner gate | WIRED | `useScheduleToday` hits `/api/v1/bookings`; `useExpiringMemberships` hits `/api/v1/memberships` with `expiring:'true',withinDays:'7'`; no `enabled` guard |
| `ReportsPage.tsx` | `csv.ts downloadCsv` + 4 `/api/v1/reports/*.csv` endpoints | `await downloadCsv('/api/v1/reports/revenue.csv', ...)` etc. | WIRED | All 4 CSV calls present at lines 161, 169, 177, 185 |
| `AuditPage.tsx` | `features/audit useAuditLog` + `downloadCsv('/api/v1/audit-log.csv')` | owner-gated query + CSV button | WIRED | `useAuditLog` imported and called; `audit-log.csv` endpoint in CSV handler |
| `nav-items.ts` | `ROUTES.audit` | `ownerOnly:true, ownerResource:'audit-log'` | WIRED | Entry present; `ownerResource: 'audit-log'` confirmed |
| `features/settings/api.ts` | `/api/v1/auth/sessions` + `sessions/{familyId}/revoke` | `staffRequest('get'/'post', ...)` | WIRED | `useSessions` + `useRevokeSession` + `useRevokeCurrentSession` all wired |
| `SectionsTop.tsx` | `@/lib/authBus publishSessionExpired` | self-revoke of current session | WIRED | `publishSessionExpired()` called in `useRevokeCurrentSession.onSuccess`; `SectionsTop` uses `useRevokeCurrentSession` |
| `features/users/api.ts` | `/api/v1/users` (CRUD) | `staffRequest` with owner gate | WIRED | All CRUD endpoints wired; CSRF auto via `staffRequest` for POST/PATCH/DELETE |
| `SectionsBottom.tsx` | `features/users hooks` + `can(role,'list','users')` | owner gate + invite modal + confirms | WIRED | `useUsers` called; gate at lines 701/707; 409 map at line 491 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `DashboardPage.tsx` | `revenueQ.data`, `visitsQ.data`, `clientsQ.data`, `trainersQ.data` | `useRevenueReport`, `useVisitsReport`, `useClientsReport`, `useTrainersReport` → `staffRequest('get', '/api/v1/reports/*')` | Yes — `staffRequest` issues real HTTP; `Schema.parse(raw).data` returns typed data | FLOWING |
| `DashboardPage.tsx` | `scheduleTodayQ.data`, `expiringQ.data` | `useScheduleToday`, `useExpiringMemberships` → `/api/v1/bookings`, `/api/v1/memberships` | Yes — real HTTP calls with no mock path for non-mock `VITE_API_MODE` | FLOWING |
| `ReportsPage.tsx` | `revenueQuery.data`, `clientsQuery.data`, `visitsQuery.data`, `trainersQuery.data` | All four `useXxxReport` hooks → real `/api/v1/reports/*` endpoints | Yes — same hooks as dashboard; `Schema.parse(raw).data` | FLOWING |
| `AuditPage.tsx` | `data.items`, `data.total` | `useAuditLog(filter, role)` → `/api/v1/audit-log` | Yes — `AuditLogResponseSchema.parse(raw).data`; page resets on filter change | FLOWING |
| `SectionsTop.tsx` (SecuritySection) | `sessionsData.items` | `useSessions()` → `/api/v1/auth/sessions` | Yes — `SessionsListResponseSchema.parse(raw).data` | FLOWING |
| `SectionsBottom.tsx` (TeamSection) | `usersQuery.data.items` | `useUsers({}, role)` → `/api/v1/users` | Yes — `UsersListResponseSchema.parse(raw).data`; `enabled:can(role,'list','users')` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| TypeScript compiles without errors | `pnpm -F @clubcore/admin-app typecheck` | Exit 0, no errors | PASS |
| ESLint passes | `pnpm -F @clubcore/admin-app lint` | Exit 0, no errors | PASS |
| 337 unit + smoke tests pass | `pnpm -F @clubcore/admin-app test` | 26 test files, 337 tests passed | PASS |
| Production build succeeds | `pnpm -F @clubcore/admin-app build` | Built in 2.59s, all chunks emitted | PASS |
| `ReportsPage` early-return fires before hooks | Code inspection: outer `ReportsPage()` returns Lock-EmptyState if `!can(role,'view','reports')`, then renders `<ReportsPageContent>` which contains hooks | `ReportsPageContent` function starts at line 137 — hooks only reachable inside it | PASS |
| `AuditPage` early-return fires before hooks | Code inspection: outer `AuditPage()` returns Lock-EmptyState, inner `AuditPageContent` contains `useAuditLog` | Same two-component pattern; `useAuditLog` only in `AuditPageContent` (line 154) | PASS |
| `dangerouslySetInnerHTML` absent from audit components | `grep -rn "dangerouslySetInnerHTML" apps/admin-app/src/pages/audit/` | No output | PASS |
| Payload rendered via `JSON.stringify` + `<pre>` | `AuditDetailModal.tsx` line 47: `JSON.stringify(event.payload, null, 2)` inside `<pre>` | Confirmed | PASS |
| Self-revoke uses authBus, not direct navigate | `features/settings/api.ts` line 91: `publishSessionExpired()` in `useRevokeCurrentSession.onSuccess` | Confirmed — no `navigate()` call in the self-revoke path | PASS |
| No `PATCH /auth/me` in settings | `grep "PATCH\|auth/me" features/settings/api.ts` — comment only: "No PATCH /auth/me endpoint exists" | Confirmed read-only | PASS |

### Probe Execution

Step 7c: SKIPPED — no probe files declared in any PLAN.md for this phase and no conventional `scripts/*/tests/probe-*.sh` exist for admin-app (frontend-only build, no backend probe).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RPT-01 | 104-02 | Dashboard renders real KPI/aggregate data from `/reports/*` with empty-data guards | SATISFIED | `DashboardPage.tsx` wired to all 4 report hooks; `KpiStrip.safeInt()` guards; `isOwner` gate; reception sees zero owner calls |
| RPT-02 | 104-01, 104-03 | Reports screen renders 4 aggregate reports with CSV export | SATISFIED | `ReportsPage.tsx` — 4 real-data tabs, 4 `.csv` calls via `downloadCsv`; `useClientsReport`/`useTrainersReport` added in 104-01 |
| RPT-03 | 104-01, 104-03 | Audit screen renders real `/audit-log` with filters + stable pagination + CSV | SATISFIED | `AuditPage.tsx` — server-side filters, `page=25` keyset pagination, `audit-log.csv` CSV export; owner-only gate |
| SET-01 | 104-04 | Settings reads current staff profile + theme, manages active sessions | SATISFIED | ProfileSection read-only (GET /auth/me); theme toggle intact; SecuritySection wired to real sessions with revoke + self-revoke via authBus |
| SET-02 | 104-05 | Users surface wires owner-only multi-user admin CRUD | SATISFIED | `features/users/api.ts` full CRUD + `useRevokeInvitation`; TeamSection in SectionsBottom wired with invite modal, row actions, 409 toasts, «Это вы» |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Zero `TBD`, `FIXME`, or `XXX` markers in phase-modified files. `TODO` comments present are phase-scoped references (e.g. `// Profile edit deferred — no PATCH /auth/me endpoint (Phase 104)`) — informational, not blocking.

### Human Verification Required

All automated checks (typecheck, lint, 337 tests, build) pass. The following require a browser against a live backend:

#### 1. Owner Dashboard Live KPI Data

**Test:** Sign in as owner, navigate to `/`. Observe KPI cards (revenue, visits, expiring), OccupancyHours, RevenueChart, TopTrainers.
**Expected:** Cards render with real data or coherent zero state; no NaN/blank values; no JS console errors.
**Why human:** Live backend + real session required to verify data flows end-to-end.

#### 2. Reception Dashboard Zero Owner Calls

**Test:** Sign in as reception, navigate to `/`. Open browser Network tab.
**Expected:** Only `/api/v1/bookings` and `/api/v1/memberships` appear; zero `/api/v1/reports/*` requests.
**Why human:** Network tab inspection only.

#### 3. Reports Page — 4 Tabs + CSV Round-Trip

**Test:** Owner → Reports page. Switch all 4 tabs (Выручка/Клиенты/Посещения/Тренеры). On each tab click «Экспорт CSV».
**Expected:** Each tab renders live data; CSV file downloads (browser dialog or auto-download); Russian error toast on network failure.
**Why human:** CSV blob download is a browser-side side effect requiring live backend.

#### 4. Audit Log — Filters + Pagination + CSV

**Test:** Owner → «Журнал действий». Apply resourceType filter, navigate to page 2, click «Экспорт CSV».
**Expected:** Filter narrows results; page 2 loads different items; CSV downloads filtered data.
**Why human:** Server-side keyset pagination correctness requires live audit events.

#### 5. Audit Detail Modal — JSONB Payload Rendering

**Test:** Owner → Audit log → click a row with a non-trivial payload (nested JSON).
**Expected:** Modal shows pretty-printed JSON in monospace `<pre>` block; no HTML tags rendered as markup; `<script>` in payload appears as escaped text.
**Why human:** Visual correctness of edge-case payloads with markup-like content.

#### 6. Settings Profile + Sessions

**Test:** Owner → Settings. Verify Profile section shows real fullName/email/role (read-only). Sessions section lists real sessions with «Сейчас» on current.
**Expected:** Profile: real values from GET /auth/me; no edit inputs. Sessions: real list; current session badged.
**Why human:** Requires live backend + real session.

#### 7. Session Revoke (Non-Current)

**Test:** With two active sessions, owner → Settings → click «Завершить» on non-current session.
**Expected:** Row disappears from list; toast «Сессия завершена».
**Why human:** Requires two simultaneously active sessions.

#### 8. Self-Revoke → /login

**Test:** Owner → Settings → click «Выйти везде» → confirm modal → confirm.
**Expected:** App navigates to `/login?state=expired`; session cookies cleared.
**Why human:** Auth bus publish + RequireAuth subscriber behavior; browser navigation.

#### 9. Users Admin — Invite + Copy Link

**Test:** Owner → Settings → Team → «+ Пригласить». Fill form, submit.
**Expected:** Success view shows invite link URL; «Копировать ссылку» copies to clipboard; toast «Ссылка скопирована».
**Why human:** Invite round-trip + clipboard API requires live backend.

#### 10. Users Admin — 409 Guards + Self Row

**Test:** Owner → try to deactivate own row (should show «Это вы» + disabled actions). With only one owner, try to deactivate that owner.
**Expected:** Self row: «Это вы» badge; action buttons disabled. Last-owner deactivate: Russian toast «Нельзя деактивировать единственного владельца».
**Why human:** 409 backend response required; self-action disable is UI but 409 guard is server-side.

#### 11. Reception Lock States — Zero Calls

**Test:** Sign in as reception → navigate to Reports, Audit, Settings→Team. Open Network tab on each.
**Expected:** Lock-EmptyState shown; zero `/api/v1/reports/*`, `/api/v1/audit-log`, `/api/v1/users` requests.
**Why human:** Network tab inspection only.

### Gaps Summary

No gaps found. All 10 must-have truths verified in codebase. All required artifacts exist, are substantive, wired, and have real data flows. The admin-app gate (typecheck + lint + 337 tests + build) is green.

Status is `human_needed` because 11 behaviors require a live backend and browser to observe the real data round-trips, CSV downloads, session revocation flows, and network call absence assertions — none of which can be confirmed via static analysis or unit tests alone.

---

_Verified: 2026-06-13T22:55:00Z_
_Verifier: Claude (gsd-verifier)_
