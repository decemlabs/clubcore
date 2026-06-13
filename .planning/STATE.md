---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Production Admin — Backend Wiring
status: planning
stopped_at: Phase 100 UI-SPEC approved
last_updated: "2026-06-13T08:20:28.293Z"
last_activity: 2026-06-13 — v3.0 roadmap created (Phases 100-106, 30 requirements mapped)
progress:
  total_phases: 11
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** v3.0 Production Admin — Backend Wiring. Roadmap created (7 phases, 30/30 requirements mapped). Start with `/gsd:plan-phase 100`.

## Current Position

Phase: 100 of 106 (Foundation + Authentication)
Plan: —
Status: Ready to plan
Last activity: 2026-06-13 — v3.0 roadmap created (Phases 100-106, 30 requirements mapped)

Progress: [░░░░░░░░░░] 0%

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

- Start Phase 100 plan: `/gsd:plan-phase 100`

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

Last session: 2026-06-13T08:20:28.288Z
Stopped at: Phase 100 UI-SPEC approved
Resume: `/gsd:plan-phase 100` to begin Phase 100 (Foundation + Authentication).
