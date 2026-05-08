# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- 🚧 **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (planning, started 2026-05-08) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 Phase A: Skeleton (Phases 1-3) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: Monorepo Restructure & Frontend Move (3/3 plans) — completed 2026-04-30
- [x] Phase 2: Backend Skeleton with Quality Tooling (8/8 plans) — completed 2026-04-30
- [x] Phase 3: Tests, Dev Infrastructure & Documentation (6/6 plans) — completed 2026-05-01

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Auth + Clients (Phases 4-14) — SHIPPED 2026-05-07</summary>

- [x] Phase 4: Auth Foundations & Cookie/RBAC Primitives (9/9 plans) — completed 2026-05-02
- [x] Phase 5: User Schema + Email/Password Auth (8/8 plans) — completed 2026-05-03
- [x] Phase 6: RBAC Wiring + Parity Tests (5/5 plans) — completed 2026-05-03
- [x] Phase 7: Telegram OTP Channel (8/8 plans) — completed 2026-05-04
- [x] Phase 8: Clients Module + Audit Log (8/8 plans) — completed 2026-05-04
- [x] Phase 9: OpenAPI Pipeline + packages/api-client (3/3 plans) — completed 2026-05-04
- [x] Phase 10: admin-web Auth + Clients Wiring (8/8 plans) — completed 2026-05-04
- [x] Phase 11: Clients HTTP-mode Shape Adapter *(gap closure)* (2/2 plans) — completed 2026-05-04
- [x] Phase 12: v1.1 Verification Backfill *(gap closure)* (5/5 plans) — completed 2026-05-05
- [x] Phase 12.1: Clients Service Commit Fix *(inline quick-fix `260504-fst`, commit ba14aba)* — completed 2026-05-04
- [x] Phase 13: v1.1 Minor Drift & Hygiene Cleanup *(gap closure)* (4/4 plans) — completed 2026-05-05
- [x] Phase 14: Clients Search PII Hardening *(gap closure, security)* (3/3 plans) — completed 2026-05-07

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.2 Memberships + Visits (Phases 15-23) — SHIPPED 2026-05-08</summary>

- [x] Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting (5/5 plans) — completed 2026-05-07
- [x] Phase 16: Membership Plans Catalog (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 17: Membership Instances + Resolver (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 18: ARQ scheduled `expire_memberships` (6/6 plans) — completed 2026-05-07
- [x] Phase 19: Visits — DB + reception check-in (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 20: Telegram bot `/checkin` self check-in (3/3 plans) — completed 2026-05-08
- [x] Phase 21: OpenAPI drift gate refresh + api-client codegen (1/1 plan) — completed 2026-05-08
- [x] Phase 22: admin-web wiring — memberships + visits + active sessions UI (5/5 plans) — completed 2026-05-08
- [x] Phase 23: Hygiene + active sessions backend *(parallel-eligible)* (1/1 plan) — completed 2026-05-08

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

### 🚧 v1.3 Memberships Extras + Tech-Debt (Phases 24-29) — IN PROGRESS

- [ ] **Phase 24: Foundations & Tech-Debt Bedrock** — INFRA-15/16 + DEBT-01/02/03 (5 reqs) — `LOCKED_AUDIT_EVENTS` extension, `frozen` status CHECK, resolver `end_date >= today` filter, `?expiring=` query, SVC001 walker → auth/service.py
- [ ] **Phase 25: Memberships — Freeze (backend)** — MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03 (14 reqs) — `freeze_days_limit` + `membership_freeze_periods` + freeze/unfreeze endpoints + resolver-rejects-frozen
- [ ] **Phase 26: Memberships — Renewal (backend)** — MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04 (10 reqs) — `previous_membership_id` FK + `POST /renew` with current-price snapshot + resolver tiebreak
- [ ] **Phase 27: Expiring-soon Telegram Notifications** — NTF-01..06 + COPY-01 + TEST-01..03 (10 reqs) — ARQ cron 06:15 Europe/Moscow + 6 locked Russian DM templates (anti-oracle) + idempotency table
- [ ] **Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring** — FE-10..13 (4 reqs) — regenerate `openapi.json` + `schema.d.ts`; FE freeze/renewal UI + expiring-filter on `VITE_API_MODE=http` *(UI phase)*
- [ ] **Phase 29: Milestone Verification** — DEBT-04 (1 req) — 6 human-verification smoke tests + cross-phase integration sweep + verification log

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

---

*Roadmap last updated: 2026-05-08 — v1.3 milestone planning started*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt)*
*v1.3 Coverage: 0/44 v1.3 requirements satisfied (44 mapped to phases, planning phase)*
