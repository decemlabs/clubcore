---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Production Admin — Backend Wiring
status: completed
stopped_at: Phase 101 Plan 02 complete (MEM-01 delivered)
last_updated: "2026-06-13T11:41:57Z"
last_activity: "2026-06-13 — Phase 101 Plan 02 complete: membership-plans + pt-package-plans mock→http (schemas/api + PlansPage wired; MEM-01 done)"
progress:
  total_phases: 11
  completed_phases: 1
  total_plans: 8
  completed_plans: 6
  percent: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** v3.0 Production Admin — Backend Wiring. Roadmap created (7 phases, 30/30 requirements mapped). Start with `/gsd:plan-phase 100`.

## Current Position

Phase: 101 of 106 (Clients + Memberships) — In Progress
Plan: 2/4 complete
Status: Plan 02 done (membership-plans + pt-package-plans flip); ready for Plan 03 (memberships sell/lifecycle)
Last activity: 2026-06-13 — Phase 101 Plan 02 complete: membership-plans + pt-package-plans mock→http (schemas/api + PlansPage wired; MEM-01 done)

Progress: [████████░░] 75%

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

- Phase 101 Plan 02 complete. Continue Phase 101: Plan 03 (memberships sell/lifecycle).

### Phase 101 Decisions

- **D-101-01-CLIENTPATH**: API path param is `client_id` (not `id`): `/api/v1/clients/{client_id}` per schema.d.ts
- **D-101-01-NOHOOKFORM**: `@hookform/resolvers` not installed in admin-app (only admin-web) — manual `ClientCreateSchema.safeParse()` used for modal validation
- **D-101-01-CLIENTFILTERTABS**: `ClientFilterTabs.tsx` kept on disk for type compatibility; NOT rendered in new ClientsPage
- **D-101-02-PLANPATH**: Path param is `plan_id` (not `id`): `/membership-plans/{plan_id}` and `/pt-package-plans/{plan_id}` per schema.d.ts
- **D-101-02-DURATIONIMMUTABLE**: MembershipPlanUpdateSchema.omit({durationDays}) prevents client-side send; backend extra=forbid is authority for 422
- **D-101-02-PTUPDATE-NAMEONLY**: PtPackagePlanUpdateSchema accepts only name — sessionCount/priceKopecks/validityDays immutable per backend contract
- **D-101-02-MOCKSTUBS**: Create/Edit plan modals are toast stubs (plan instructs no net-new modal family); delete fully wired; sales/promos/KPIs stay on mock

### Phase 100 Decisions

- **D-100-04-OWNERFLAG**: Gate only Финансы+Отчёты via ownerOnly=true flag on NavItem; all other remaining items visible to all roles (UI-SPEC authoritative on nav visibility; can() matrix is still the single authority via ownerOnly check)
- **D-100-04-RBAC-REHOME**: admin-app is CISO-01 parity source; parity test repointed admin-web → admin-app; admin-web untouched (deleted Phase 105)
- **D-100-04-LEASTPRIV-DEFAULT**: sidebar role defaults to 'reception' while session.isPending; T-100-14 mitigation

### Blockers/Concerns

- Dev DB carry-over: stale `ix_referral_codes_client_id` (migration 0067 amended in place) + possibly polluted `referral_config`. Run `docker compose down -v` + migrate + seed before Phase 106 manual verification. (Non-blocking for test suites — they rebuild schema.)

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

## Session Continuity

Last session: 2026-06-13T11:43:32.181Z
Stopped at: Phase 101 Plan 01 complete (CLI-01, CLI-03 delivered)
Resume: Continue Phase 101 — Plan 02 (membership plans CRUD).
