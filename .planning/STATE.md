---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Production Admin — Backend Wiring
status: completed
stopped_at: v3.0 ALL 7 phases complete + milestone gate green + audit tech_debt — AWAITING USER ARCHIVE DECISION (user chose Stop-no-archive 2026-06-14)
last_updated: "2026-06-14T00:00:00.000Z"
last_activity: "2026-06-14 — v3.0 complete: Phase 106 gate green (byte-stable contract, mypy/lint-imports/pytest 2867/CISO-01 4-3/admin-app 337/client-pwa 222/Redocly), 30/30 requirements, milestone audit = tech_debt (0 blockers). NOT yet archived — user stopped to review before /gsd-complete-milestone v3.0."
progress:
  total_phases: 11
  completed_phases: 7
  total_plans: 24
  completed_plans: 24
  percent: 64
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** v3.0 Production Admin — Backend Wiring. Roadmap created (7 phases, 30/30 requirements mapped). Start with `/gsd:plan-phase 100`.

## Current Position

Phase: 106 of 106 (OpenAPI Handoff + Milestone Gate) — COMPLETE. **All 7 v3.0 phases (100–106) done.**
Plan: all plans complete (24/24)
Status: **v3.0 work + gate COMPLETE; NOT archived.** Milestone audit = `tech_debt` (30/30 requirements satisfied, 0 critical blockers). User chose Stop-no-archive (2026-06-14) to review before archiving.
Resume options:
  - Archive + close: `/gsd-complete-milestone v3.0` then `/gsd-cleanup`
  - Address debt first: see `.planning/v3.0-MILESTONE-AUDIT.md` tech_debt + human_verify_deferred (P101 WR-01 plans-form, live UAT for P101–104, ruff/format tree-wide debt)
  - Live UAT: bring up `docker compose up` and validate the 31 deferred browser items before v3.1 deploy
Last activity: 2026-06-14 — deferred live-UAT pass: P101/P103/P104 verified live (v3.0-UAT-VERIFICATION-PASS.md); fixed INV-01/INV-02 (user-invite, commit 5e3b41f1); REV-01 (revoke-invitation, backend decision) deferred → task_50ae4a5a; P102 payroll/booking data-setup-blocked. (Prior: 260614-hux 8 bug fixes, 260614-j2d GAP-1.)

Progress: [██████████] 100% (7/7 v3.0 work phases; 999.x are historical ledger, not v3.0 work)

## v3.0 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 100. Foundation + Auth | Workspace absorption, API client + CSRF + 401-redirect, zod seam, hide-for-future, staff login/session/role-gate | FND-01, FND-02, FND-03, FND-04, AUTH-01, AUTH-02, AUTH-03 |
| 101. Clients + Memberships | Full client-membership lifecycle on real data (list/detail/CRUD + plans + sell/freeze/renew/cancel) | CLI-01, CLI-02, CLI-03, MEM-01, MEM-02, MEM-03 |
| 102. Schedule + Trainers | Trainer slots/templates/time-off + bookings/PT-sessions + trainer catalog + payroll | SCH-01, SCH-02, TRN-01, TRN-02 |
| 103. Attendance + Finance | Check-in + visits load + cashbox + revenue/online-payments reports | ATT-01, ATT-02, FIN-01, FIN-02 |
| 104. Dashboard + Reports + Settings | Live KPI dashboard + all 4 reports + audit log + profile/sessions + user admin | RPT-01, RPT-02, RPT-03, SET-01, SET-02 |
| 105. admin-web Retirement + RBAC Re-home | Delete admin-web; re-home three-way RBAC parity; CI/workspace/drift-gate clean | ADMW-01, ADMW-02, ADMW-03 |
| 106. OpenAPI Handoff + Milestone Gate | Byte-stable contract; full milestone gate green (mypy+lint+pytest+admin-app+Redocly) | HND-01 |

**Coverage:** 30/30 v3.0 requirements mapped. Execution order: 100 → 101 → 102 → 103 → 104 → 105 → 106.

## Accumulated Context

### v3.0 Architecture Constraints (pre-locked)

- **D-V30-SCOPE-WIRE**: wire-only — no new backend domains/endpoints; every screen maps to an already-shipped endpoint
- **D-V30-BRANCH**: single-club; Branches/Branch-Settings/System-Settings are hidden-for-future (FND-04), not built
- **D-V30-ADMINWEB-DELETE**: admin-web deleted; RBAC re-home mechanic decided at Phase 100 plan (read real coupling first)
- **D-V30-VERSION**: v3.0 is the wiring milestone; production deploy/launch → v3.1+
- **Zod contract seam**: spike 010 Option A — per-domain zod layer adopted lazily as each screen is wired; mock `queryFn` removed when domain goes live
- **Staff principal**: `sz_*` cookies, `X-CSRF-Token` on mutating requests — not `cc_client_*`
- **RBAC decision deferred**: whether parity lives in admin-app `can.ts` vs backend-only authority is decided at Phase 100 plan after reading real coupling in `permissions.py`/`can.ts`/`registry.ts`

### Pending Todos

- Phase 103 complete (all 4 plans). Continue with Phase 104 (Dashboard + Reports + Settings).

### Phase 101 Decisions

- **D-101-01-CLIENTPATH**: API path param is `client_id` (not `id`): `/api/v1/clients/{client_id}` per schema.d.ts
- **D-101-01-NOHOOKFORM**: `@hookform/resolvers` not installed in admin-app (only admin-web) — manual `ClientCreateSchema.safeParse()` used for modal validation
- **D-101-01-CLIENTFILTERTABS**: `ClientFilterTabs.tsx` kept on disk for type compatibility; NOT rendered in new ClientsPage
- **D-101-02-PLANPATH**: Path param is `plan_id` (not `id`): `/membership-plans/{plan_id}` and `/pt-package-plans/{plan_id}` per schema.d.ts
- **D-101-02-DURATIONIMMUTABLE**: MembershipPlanUpdateSchema.omit({durationDays}) prevents client-side send; backend extra=forbid is authority for 422
- **D-101-02-PTUPDATE-NAMEONLY**: PtPackagePlanUpdateSchema accepts only name — sessionCount/priceKopecks/validityDays immutable per backend contract
- **D-101-02-MOCKSTUBS**: Create/Edit plan modals are toast stubs (plan instructs no net-new modal family); delete fully wired; sales/promos/KPIs stay on mock
- **D-101-03-PATH-PARAMS**: Backend membership paths use {membership_id} not {id}; pt-package paths use {pt_package_id} — matched to schema.d.ts
- **D-101-03-RECEIPTX**: lucide-react 0.469 has no ReceiptX icon; used ReceiptText as functional equivalent for RefundScreen icon
- **D-101-03-HISTORY-STUB**: HistoryScreen remains on mock data; no dedicated history endpoint exists in Phase 101 scope
- **D-101-03-CANCEL-GATE**: SubscriptionModal dispatcher returns null for 'cancel' screen when can(role,'cancel','memberships') is false (reception role)
- **D-101-04-PER-TAB-HOOKS**: Hooks called inside each tab component (clientId prop), not lifted to ClientPage — preserves per-tab error isolation
- **D-101-04-TRAININGS-PTPKG**: TrainingsTab uses usePtPackagesByClient (101-03) — PT-package instances available in scope
- **D-101-04-MEMBERSHIPS-SECTION**: MembershipsSection rendered inline in ClientPage above tabs using useMembershipsByClient reuse

### Phase 103 Decisions

- **D-103-01-SESSION-FROM-CALLER**: useCheckIn receives currentUserId as a mutation var from caller rather than calling useSession() internally — avoids hook coupling in mutationFn, keeps hook context-free
- **D-103-01-LEGACY-USEREPORTS**: useReports() + reportsKeys preserved in reports/api.ts so ReportsPage (Phase 104 scope) builds without changes; reportsQueryKeys uses ['reports-data'] root to avoid key collision
- **D-103-01-NOSESSION-VISITS**: visits/api.ts does NOT import useSession — currentUserId is caller-provided via CheckInVars; payments/api.ts accepts role as explicit parameter
- **D-103-02-CHECKIN-RENAME**: Old mock CheckinModal.tsx (QR scanner) replaced/renamed to CheckInModal.tsx with real client-picker + 3-code 409 implementation; git mv used for proper case rename on macOS case-insensitive FS
- **D-103-02-ATTENDANCE-STATIC-RANGE**: AttendancePage uses static last-30-days range (no date picker); date-range filter UI deferred to Phase 103-03+ where cashbox/finance also need it (shared component)
- **D-103-02-CLIENTNAME-TODO**: VisitData does not embed clientName from server; VisitsList shows fallback label; N+1 client fetches avoided; wiring deferred to Phase 104
- **D-103-03-CASHBOX-HOOKS-SPLIT**: CashboxPage split into outer RBAC guard (useSession only) + inner CashboxPageContent (data hooks); same pattern for LoadPage — avoids conditional React hook calls
- **D-103-03-MSK-SLICE**: computeDailyTotals derives MSK date via receivedAt.slice(0,10) (ISO prefix) rather than TZ conversion; date-fns-tz not installed; backend stores MSK-anchored timestamps
- **D-103-03-LOAD-HEATMAP-SINGLE-ROW**: IntensityHeatmap shown with one row ('Часы') for the 24 hourly aggregate buckets; real data is single-period aggregate not a 7-day matrix
- **D-103-03-FAKEREFUND**: «Оформить возврат» dropdown removed from TransactionsCard — no /payments refund endpoint; refund rows are READ-ONLY per T-103-03-FAKEREFUND
- **D-103-04-FINANCE-SPLIT**: FinancePage split into outer RBAC guard (useSession only) + inner FinancePageContent (data hooks) — same pattern as D-103-03-CASHBOX-HOOKS-SPLIT; React Rules of Hooks safe
- **D-103-04-ALLZERO-EMPTYSTATE**: All-zero revenue buckets (after zero-fill) and all-empty online payments both render EmptyState inline — no flat-zero/NaN chart

### Phase 104 Decisions

- **D-104-01-CSVLAYER**: csv.ts lives in api/ layer (not features/) to allow same-layer import of appendQuery/parseErrorBody from client.ts without ESLint boundary violation
- **D-104-01-EXPORT-APPEND**: appendQuery + parseErrorBody exported from client.ts by adding export keyword only — no signature/body changes, no callers broken
- **D-104-01-AUDITPAGE-STUB**: AuditPage.tsx updated minimally to compile with 2-arg useAuditLog (useSession for role, passes empty filter); renders EmptyState stub; Wave 2 (104-02) will wire full data rendering, filters, pagination, CSV, RBAC gate
- **D-104-04-MOCKCOMPAT**: useSettings renamed to useMockSettingsData (not deleted) — other sections (Branch/Hours/Booking/Payments/Notifications/App/Integrations/Billing) still need mock data; ProfileSection and SecuritySection are now self-fetching; TeamSection wired in 104-05
- **D-104-04-SELFREVOKE-AUTHBUS**: useRevokeCurrentSession calls publishSessionExpired() on 204 (not navigate()) — routes through RequireAuth authBus subscriber, same path as mid-session 401 (T-104-09 mitigation)
- **D-104-04-PROFILE-READONLY**: ProfileSection is fully read-only; PATCH /auth/me confirmed absent in backend; code comment added noting edit is deferred
- **D-104-05-ROLE-TONE**: ROLE_TONE updated from mock types (owner/admin/trainer/cashier) to API types (owner/reception); mock Role import removed from SectionsBottom.tsx
- **D-104-05-TEAM-COLS**: Simplified TeamSection grid (Сотрудник/Роль/Статус/Actions) — branch/2FA/last-login not in GET /api/v1/users response
- **D-104-05-TOKEN-ID**: useRevokeInvitation receives user.id as tokenId for pending_invitation rows
- **D-104-03-TABSGROUP**: Inline TabsGroup component (not imported from FinancePage parts) — avoids cross-page import, self-contained Reports module
- **D-104-03-CLIENTS-INLINE-KPI**: ClientsTab uses inline KpiCard instead of existing KpiTile — clients 3-scalar data doesn't match KpiTile's icon+delta contract
- **D-104-03-ACTIVITY-ICON-REUSE**: «Журнал действий» nav entry reuses already-imported Activity icon (consistent with Посещаемость entry)

### Phase 105 Decisions

- **D-105-01-GUARD-REPOINT**: CISO-01 byte-parity guard (`test_byte_parity.py`) repointed admin-web → admin-app; all assertions preserved (`.exists()`, `Role.CLIENT`, `| 'client'`); guard is LIVE (confirmed via python import + `.exists()` check)
- **D-105-02-DOCONLY**: config.py, loyalty/permissions.py, and api-client/README.md comment prose updated; NO config default values changed (frontend_base_url/ws_allowed_origins port numbers unchanged)
- **D-105-03-PARITY-INFRA**: `test_byte_parity.py` setup ERROR is pre-existing (SeaweedFS/S3 not running → lifespan timeout); test function logic correct; full-stack run deferred to Phase 106

### Phase 100 Decisions

- **D-100-04-OWNERFLAG**: Gate only Финансы+Отчёты via ownerOnly=true flag on NavItem; all other remaining items visible to all roles (UI-SPEC authoritative on nav visibility; can() matrix is still the single authority via ownerOnly check)
- **D-100-04-RBAC-REHOME**: admin-app is CISO-01 parity source; parity test repointed admin-web → admin-app; admin-web untouched (deleted Phase 105)
- **D-100-04-LEASTPRIV-DEFAULT**: sidebar role defaults to 'reception' while session.isPending; T-100-14 mitigation

### Blockers/Concerns

- Dev DB carry-over: stale `ix_referral_codes_client_id` (migration 0067 amended in place) + possibly polluted `referral_config`. Run `docker compose down -v` + migrate + seed before Phase 106 manual verification. (Non-blocking for test suites — they rebuild schema.)

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260614-hux | Fix v3.0 admin-app live-UAT bugs (8 FE schema/format/cache divergences + phone_exists localization) | 2026-06-14 | e7924fc4 | Verified (typecheck+lint+340 tests green; all 9 live-browser-verified) | [260614-hux-fix-v3-0-admin-app-live-uat-bugs-8-fe-sc](./quick/260614-hux-fix-v3-0-admin-app-live-uat-bugs-8-fe-sc/) |
| 260614-j2d | GAP-1 — reachable membership lifecycle UI entry points (sell/freeze/renew/cancel/refund) on client page | 2026-06-14 | 126dcb58 | Verified (typecheck+lint+router-smoke green; sell+freeze+RBAC live-verified) | [260614-j2d-wire-membership-lifecycle-ui-entry-point](./quick/260614-j2d-wire-membership-lifecycle-ui-entry-point/) |

## Deferred Items

Carrying forward from v2.6 close (2026-06-08):

| Category | Item | Status |
|----------|------|--------|
| tech-debt | WARN-1 zeroed-referrer-bonus → permanent "pending" invitee under zero-config | deferred → post-v3.0 |
| human-verify | 98-HUMAN-UAT browser-only items (pixel parity, live deep-link round-trip, share chips) | pending — see 98-HUMAN-UAT.md |
| tech-debt | RCPT-02 typing indicator producer (WS consumer wired; no Telegram typing API) | deferred → future |
| human-verify | Phase 94 HUMAN-UAT residual (dark theme + physical-device camera) | pending |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | deferred → /gsd:secure-phase 70 |
| compliance | Phase 81 ФЗ-376 consent wording (concrete ₽ amount vs generic) | needs legal review |

v3.0 in-progress deferrals:

| Category | Item | Status |
|----------|------|--------|
| feature | P101 WR-01 — Plans create/edit form modals (list/gating/delete/API-hooks done; forms are toast stubs) | deferred → follow-up (user-accepted 2026-06-13) |
| human-verify | P100 — login round-trip + 401 redirect | ✅ validated live 2026-06-13 |
| human-verify | P101 — 9 live-backend UAT items (CRUD round-trips, sell/freeze/refund, role gating) | ✅ verified live 2026-06-14 (see v3.0-UAT-VERIFICATION-PASS.md) |
| human-verify | P102 — 5 live items (time-off force-cascade, booking-race, 24h cancel, payroll kopecks, reception zero-payroll-calls) | ⏳ data-setup-blocked (schedule renders post-BUG-4; payroll/booking seeding deferred) |
| human-verify | P103 — 6 live items (check-in + 409 states, reception zero owner-calls, cashbox refund rows, Load no-NaN, Finance tabs) | ✅ verified live 2026-06-14 (duplicate/outside-hours 409 by equivalence) |
| human-verify | P104 — 11 live items (dashboard KPIs+reception zero-calls, reports + CSV, audit filters/payload, sessions revoke, user invite/deactivate) | ✅ verified live 2026-06-14 (invite needed INV-01/02 fix; REV-01 revoke deferred) |
| bug | REV-01 — revoke-invitation broken (FE no body → 422 + passes user.id not token id; list omits token id) | deferred → needs backend contract decision (task_50ae4a5a) |

## Session Continuity

Last session: 2026-06-13T21:44:42.273Z
Stopped at: Phase 104 Plan 03 complete (RPT-02 Reports page + RPT-03 Audit page wired + «Журнал действий» nav entry)
Resume: Phase 104 Plan 03 complete. Continue with Phase 104 Plan 04 (Settings — profile/sessions/users admin).
