# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (shipped 2026-05-24) — see [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
- ⏳ **v1.8 Reports + Audit Log read API** — Phases 54-57 (active, started 2026-05-24)

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

<details>
<summary>✅ v1.3 Memberships Extras + Tech-Debt (Phases 24-29) — SHIPPED 2026-05-14</summary>

- [x] Phase 24: Foundations & Tech-Debt Bedrock (5/5 plans) — completed 2026-05-08 — INFRA-15/16 + DEBT-01/02/03
- [x] Phase 25: Memberships — Freeze (backend) (5/5 plans) — completed 2026-05-09 — MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03
- [x] Phase 26: Memberships — Renewal (backend) (4/4 plans) — completed 2026-05-09 — MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04
- [x] Phase 27: Expiring-soon Telegram Notifications (5/5 plans) — completed 2026-05-09 — NTF-01..06 + COPY-01 + TEST-01..03
- [x] Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring (8/8 plans) — completed 2026-05-10 — FE-10/11/12/13 *(1 mock-parity gap deferred to v1.4)*
- [x] Phase 29: Milestone Verification (6/6 plans) — completed 2026-05-14 — DEBT-04 *(7/7 scenarios passed; 3 inline blocker fixes; see milestones/v1.3-VERIFICATION-LOG.md)*

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

<details>
<summary>✅ v1.4 Cash Sales + PT Packages (Phases 30-36) — SHIPPED 2026-05-16</summary>

- [x] Phase 30: Foundations & Tech-Debt Bedrock (4/4 plans) — completed 2026-05-14 — INFRA-17/18/19/20/21/22/23 + DEBT-05
- [x] Phase 31: Trainers Module (2/2 plans) — completed 2026-05-14 — TRN-01..08
- [x] Phase 32: Payment Ledger + Sale Flow + Refund (3/3 plans) — completed 2026-05-15 — PAY-01..10 + REF-01..08
- [x] Phase 33: PT-Package Plans + Instances (3/3 plans) — completed 2026-05-15 — PT-01..13
- [x] Phase 34: PT-Session Recording (3/3 plans) — completed 2026-05-16 — PT-14..22
- [x] Phase 35: OpenAPI Drift Gate (backend-only handoff) (2/2 plans) — completed 2026-05-16 — FE-10 *(FE-11..18 descoped to v2.0 — design team owns production frontends)*
- [x] Phase 36: Milestone Verification (backend-only) (5/5 plans) — completed 2026-05-16 — VER-01..04 *(8/8 scenarios + 20/20 race + 4/4 CI gates passed; 5 inline regression fixes; 44 pre-existing pytest failures → DEFER-36-04-A; see milestones/v1.4-VERIFICATION-LOG.md)*

Full details: [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)

</details>

<details>
<summary>✅ v1.5 Schedule + Bookings (Phases 37-40) — SHIPPED 2026-05-18</summary>

- [x] Phase 37: Foundations Bedrock (5/5 plans) — completed 2026-05-17 — INFRA-24..28 + RBAC/audit/Protocol-slot setup for schedule + bookings
- [x] Phase 38: Schedule Module + Booking Core (6/6 plans) — completed 2026-05-17 — SLOT-01..09 + BOOK-01..10 + PKG-01..06 (partial UNIQUE race, FSM, validity-window guard)
- [x] Phase 39: Notifications + Cron (4/4 plans) — completed 2026-05-18 — NOTIFY-01..05 + CRON-01..05 (Russian DMs, `booking_notifications` idempotency, 23:10 no-show + 06:35 reminder crons)
- [x] Phase 40: Telegram /book + OpenAPI + Verification (5/5 plans) — completed 2026-05-18 — BOT-01..05 + HANDOFF-01..02 + VER-05..08 *(minimal live-Postgres verification PASS; full 10-scenario operator runbook deferred to v1.9 as DEFER-40-01)*

Full details: [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)

</details>

<details>
<summary>✅ v1.6 Email channel + Multi-user admin (Phases 41-46) — SHIPPED 2026-05-21</summary>

- [x] Phase 41: INFRA Bedrock + Anti-Oracle Scaffold (11/11 plans) — completed 2026-05-18 — INFRA-34..40 + RESET-06
- [x] Phase 42: Email Transport Layer + Email OTP Fallback (16/16 plans) — completed 2026-05-19 — EMAIL-01..07 + AUTH-EM-01..04 *(+5 gap-closure plans 42-12..16 closing VERIFICATION CR-01..04 + WR hygiene)*
- [x] Phase 43: Multi-User Admin Module (18/18 plans) — completed 2026-05-19 — USERS-01..07 *(+4 gap-closure plans 43-14..17 closing regression-gate CR-01/03/04 + WR hygiene)*
- [x] Phase 44: Invitation + Password-Reset Flow (11/11 plans) — completed 2026-05-20 — RESET-01..05
- [x] Phase 45: Email Notification Mirrors (13/13 plans) — completed 2026-05-20 — NOTIFY-06..14
- [x] Phase 46: OpenAPI Handoff + Milestone Verification (13/13 plans) — completed 2026-05-21 — HANDOFF-03..04 + VER-09..14 *(7/8 reqs verified; VER-12 + VER-14 deferred to v1.7 as DEFER-46-01/02; see milestones/v1.6-VERIFICATION-LOG.md)*

Full details: [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)

</details>

<details>
<summary>✅ v1.7 Online Payments + 54-ФЗ (Phases 47-53) — SHIPPED 2026-05-24</summary>

- [x] **Phase 47: Bedrock** (7/7 plans) — completed 2026-05-21 — INFRA-34..41 *(Option A import-linter deferral closed in Phase 49)*
- [x] **Phase 48: ЮKassa Integration Adapter** (7/7 plans) — completed 2026-05-22 — ADAPTER-01..06 (async httpx wrapper, IP verifier, receipt builder, respx fixtures)
- [x] **Phase 49: Online Sales Orchestrator** (7/7 plans) — completed 2026-05-22 — PAY-01..08 (`online_payments` module, sell + QR endpoints, anti-oracle return screen, email gate)
- [x] **Phase 50: Webhook FSM + Fiscal Foundation** (6/6 plans) — completed 2026-05-22 — WH-01..06 + FISCAL-01..03 (webhook handler, payment FSM, `record_payment(method='online')`, `fiscal_receipts`, atomic UoW)
- [x] **Phase 51: Fiscal FSM + Refunds** (10/10 plans) — completed 2026-05-23 — FISCAL-04..07 + REFUND-01..04 (receipt FSM, ARQ dispatch + circuit breaker, online refund endpoints)
- [x] **Phase 52: Cross-Channel Notifications + v1.6 Carry-out** (6/6 plans) — completed 2026-05-23 — NOTIFY-01..05 *(CARRY-01/02 operator-pending → DEFER-46-01/02)*
- [x] **Phase 53: Milestone Verification** (4/4 plans) — completed 2026-05-23 — VER-01/02/04/05 verified, VER-03 operator-pending *(16/16 new tests, 0/5 inline regressions; DEFER-46-03 closed; see milestones/v1.7-VERIFICATION-LOG.md)*

Full details: [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)

</details>

<details open>
<summary>⏳ v1.8 Reports + Audit Log read API (Phases 54-57) — ACTIVE 2026-05-24</summary>

- [ ] **Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes** — INFRA-41, INFRA-42, INFRA-43
- [ ] **Phase 55: Revenue + Clients + Visits Reports** — REV-01..05, CLR-01..04, VIS-R-01..04
- [ ] **Phase 56: Audit Log Read API + CSV Export** — AUD-01..06, EXP-01..04
- [ ] **Phase 57: OpenAPI Handoff + Milestone Verification** — HND-01..02, VER-01..02

</details>

---

## Phase Details

### Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes
**Goal**: The `app/modules/reports/` module exists and is architecturally wired: import-linter contract enforced, RBAC enums extended with owner-only reports/audit entries, and aggregation indexes applied so subsequent report queries are performant from day one.
**Depends on**: Phase 53 (v1.7 shipped)
**Requirements**: INFRA-41, INFRA-42, INFRA-43
**Success Criteria** (what must be TRUE):
  1. `app/modules/reports/` is registered in `.importlinter` `modules-independent` and import-linter passes with no violations
  2. `Resource.REPORTS` + `Resource.AUDIT_LOG` + their owner-only RBAC pairs exist in backend enums AND are mirrored byte-for-byte in admin-web `can.ts` + `registry.ts`; three-way parity test is green
  3. The three-way parity test explicitly covers the new v1.8 pairs (its count assertion is bumped)
  4. Alembic migration(s) for aggregation indexes (`payments(received_at)`, `audit_log(created_at)`, `audit_log(action)`, `audit_log(resource_type)`) apply and round-trip clean; `alembic check` green
**Plans**: TBD

### Phase 55: Revenue + Clients + Visits Reports
**Goal**: Owner can query all three read-only aggregate reports (revenue by period, clients snapshot, visits by day/hour) via authenticated JSON endpoints; all monetary values are integer kopecks; all date buckets are deterministic in Europe/Moscow.
**Depends on**: Phase 54
**Requirements**: REV-01, REV-02, REV-03, REV-04, REV-05, CLR-01, CLR-02, CLR-03, CLR-04, VIS-R-01, VIS-R-02, VIS-R-03, VIS-R-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/reports/revenue?from=&to=&groupBy=day` and `groupBy=month` return buckets with integer kopecks broken down by payment method (`cash`/`online`) and subject kind (`membership`/`pt_package`); refund rows reduce net amounts correctly
  2. `GET /api/v1/reports/clients` returns active membership count, expiring-within-N-days count (default 7, param `within` 1..30), and new-clients count for a date range; all counters exclude soft-deleted rows
  3. `GET /api/v1/reports/visits?from=&to=` returns daily visit counts using `visits.gym_date` (no secondary TZ conversion); a separate grouping by hour of day is available for peak-hour analysis; average visits per day for the period is returned
  4. Reception role receives 403 on all `/reports/*` endpoints (RBAC guard + route-introspection gate covers the new routes)
  5. All day/month buckets match Europe/Moscow boundaries (consistent with existing `gym_date STORED` and cron-window discipline)
**Plans**: TBD

### Phase 56: Audit Log Read API + CSV Export
**Goal**: Owner can browse and filter the full 69-event audit log through a paginated JSON endpoint and download any report or audit log as a UTF-8 BOM CSV suitable for Excel.
**Depends on**: Phase 55
**Requirements**: AUD-01, AUD-02, AUD-03, AUD-04, AUD-05, AUD-06, EXP-01, EXP-02, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/audit-log` returns `{items, total, page, pageSize}` ordered `created_at DESC, id DESC`; reception receives 403; owner sees all 69 event kinds
  2. Filters for actor (`actorUserId`, `actorEmailSnapshot` substring match), resource (`resource_type`), event kind (`action`), and time window (`from`/`to` interpreted in Europe/Moscow) each narrow results correctly and can be combined
  3. Pagination is stable across pages (adding a new audit row during pagination does not shift earlier pages due to deterministic `created_at DESC, id DESC` ordering)
  4. CSV download endpoints (`/reports/revenue.csv`, `/reports/clients.csv`, `/reports/visits.csv`, `/audit-log.csv`) stream UTF-8 BOM content with correct RFC 4180 escaping; Cyrillic fields round-trip correctly; monetary columns render as rubles with separator (not raw kopecks); date columns are Europe/Moscow formatted
  5. CSV exports for audit log accept the same filter parameters as the JSON endpoint and produce consistent results
**Plans**: TBD

### Phase 57: OpenAPI Handoff + Milestone Verification
**Goal**: All v1.8 API paths are reflected in byte-stable `openapi.json` and `schema.d.ts` with compile-time forward guards; an operator runbook confirms revenue golden-path, audit filtering, reception 403, and CSV download against a live stack.
**Depends on**: Phase 56
**Requirements**: HND-01, HND-02, VER-01, VER-02
**Success Criteria** (what must be TRUE):
  1. `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts` regenerate byte-stably; CI `git diff --exit-code` is green on both artifacts; all v1.8 paths (`/reports/revenue`, `/reports/clients`, `/reports/visits`, `/audit-log` and their CSV variants) are present in the schema
  2. `schema.contract.test.ts` gains `AssertNonNever` forward-guards for v1.8 paths and the runtime count assertion is bumped to the new total
  3. Correctness tests verify: revenue aggregates match deterministic fixture data (kopecks net-of-refund); Europe/Moscow day-buckets match expected dates at DST boundaries; visits hour-buckets aggregate correctly; audit-log pagination is stable across inserts
  4. RBAC denial is covered by integration tests: reception `GET /api/v1/reports/revenue` and `GET /api/v1/audit-log` both return 403
  5. Operator runbook executes against `docker compose up`: revenue golden-path with known fixture amounts passes, audit log filters narrow as expected, reception 403 confirmed manually, CSV download opens in Excel without mojibake
**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 47. Bedrock | 7/7 | Complete | 2026-05-21 |
| 48. ЮKassa Integration Adapter | 7/7 | Complete | 2026-05-22 |
| 49. Online Sales Orchestrator | 7/7 | Complete | 2026-05-22 |
| 50. Webhook FSM + Fiscal Foundation | 6/6 | Complete | 2026-05-22 |
| 51. Fiscal FSM + Refunds | 10/10 | Complete | 2026-05-23 |
| 52. Cross-Channel Notifications + v1.6 Carry-out | 6/6 | Complete | 2026-05-23 |
| 53. Milestone Verification | 4/4 | Complete | 2026-05-23 |
| 54. Foundations — Module Scaffold + RBAC Parity + Indexes | 0/TBD | Not started | - |
| 55. Revenue + Clients + Visits Reports | 0/TBD | Not started | - |
| 56. Audit Log Read API + CSV Export | 0/TBD | Not started | - |
| 57. OpenAPI Handoff + Milestone Verification | 0/TBD | Not started | - |

---

*Roadmap last updated: 2026-05-24 — v1.8 Reports + Audit Log read API ACTIVE (Phases 54-57). v1.7 Online Payments + 54-ФЗ SHIPPED (Phases 47-53, 47 plans). 48/51 v1.7 requirements delivered; 3 operator-credential-gated (CARRY-01/02, VER-03) acknowledged as deferred at close.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped.*
*v1.6 Coverage: 48/48 v1.6 requirements satisfied (8 INFRA + 11 EMAIL/AUTH-EM + 7 USERS + 5 RESET + 9 NOTIFY + 8 HANDOFF/VER). VER-12 (live RU-domain email-deliverability probe) + VER-14 (15-template owner countersign) ratification deferred to v1.7 as DEFER-46-01/02.*
*v1.7 Coverage: 48/51 v1.7 requirements delivered (8 INFRA + 6 ADAPTER + 8 PAY + 9 WH/FISCAL-foundation + 8 FISCAL-FSM/REFUND + 5 NOTIFY + 4 VER). 3 operator-credential-gated deferred at close: CARRY-01 (DEFER-46-01 live RU email probe) + CARRY-02 (DEFER-46-02 owner countersign) + VER-03 (ЮKassa sandbox walkthrough per D-04).*
*v1.8 Coverage: 30/30 v1.8 requirements mapped (3 INFRA + 5 REV + 4 CLR + 4 VIS-R + 6 AUD + 4 EXP + 2 HND + 2 VER).*
