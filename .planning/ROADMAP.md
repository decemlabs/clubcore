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
- ✅ **v1.8 Reports + Audit Log read API** — Phases 54-57 (shipped 2026-05-24) — see [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 Trainers Complete** — Phases 58-61 (shipped 2026-05-26) — see [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)

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

<details>
<summary>✅ v1.8 Reports + Audit Log read API (Phases 54-57) — SHIPPED 2026-05-24</summary>

- [x] **Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes** (3/3 plans) — completed 2026-05-24 — INFRA-41/42/43 (read-only `reports/` scaffold, `Resource.AUDIT_LOG` parity 33→35, Alembic 0040 audit indexes)
- [x] **Phase 55: Revenue + Clients + Visits Reports** (2/2 plans) — completed 2026-05-24 — REV-01..05 + CLR-01..04 + VIS-R-01..04 (day/month grain, net-of-refund kopecks, Europe/Moscow buckets)
- [x] **Phase 56: Audit Log Read API + CSV Export** (2/2 plans) — completed 2026-05-24 — AUD-01..06 + EXP-01..04 (filtered keyset pagination + UTF-8 BOM CSV)
- [x] **Phase 57: OpenAPI Handoff + Milestone Verification** (3/3 plans) — completed 2026-05-24 — HND-01..02 + VER-01..02 *(8 paths byte-stable + DST golden tests; VER-01 live runbook operator-pending per D-12)*

Full details: [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)

</details>

<details>
<summary>✅ v1.9 Trainers Complete (Phases 58-61) — SHIPPED 2026-05-26</summary>

- [x] Phase 58: Payroll Foundations + Ledger (9/9 plans) — completed 2026-05-25 — PAY-01..06 (comp-config API + read-only preview + append-only accrual ledger + pending→paid + PT-refund clawback Protocol slot; integer `math.ceil` rounding; 4 new LOCKED_AUDIT_EVENTS + 5 OWNER_ONLY pairs)
- [x] Phase 59: Recurring Schedule + Time-Off (5/5 plans) — completed 2026-05-25 — REC-01..04 (Alembic 0042 recurring_slot_templates + trainer_time_off + slot ALTER; daily ARQ cron `generate_recurring_slots` 04:00 UTC `unique=True` materializing over RECURRING_SLOT_HORIZON_DAYS env; time-off cascades + DM via existing notification machinery)
- [x] Phase 60: Trainer-Usage Report (4/4 plans) — completed 2026-05-25 — RPT-01..04 (owner-only `GET /reports/trainers` + `.csv` with 4-CTE raw-SQL read; signed-SUM payroll netted with clawbacks; D-54-07/08 read-only discipline preserved)
- [x] Phase 61: OpenAPI Handoff + Milestone Verification (4/4 plans) — completed 2026-05-26 — HND-01 (byte-stable openapi.json + schema.d.ts regen with 14 v1.9 path×method combos; 14-entry `_v19Checks` AssertNonNever + `toHaveLength(14)`; milestone-gate green; `.planning/handoff/v1.9-trainers-runbook.md` authored, live walkthrough OPERATOR-PENDING per D-61-12)

Full details: [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)

</details>

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 58. Payroll Foundations + Ledger | v1.9 | 9/9 | Complete | 2026-05-25 |
| 59. Recurring Schedule + Time-Off | v1.9 | 5/5 | Complete | 2026-05-25 |
| 60. Trainer-Usage Report | v1.9 | 4/4 | Complete | 2026-05-25 |
| 61. OpenAPI Handoff + Milestone Verification | v1.9 | 4/4 | Complete | 2026-05-26 |

---

*Roadmap last updated: 2026-05-26 — v1.9 Trainers Complete SHIPPED (Phases 58-61, 22 plans, 15/15 requirements; tag `v1.9`). All 8 business domains ✅. Next: v1.10 API Handoff + Production Hardening.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped.*
*v1.6 Coverage: 48/48 v1.6 requirements satisfied (8 INFRA + 11 EMAIL/AUTH-EM + 7 USERS + 5 RESET + 9 NOTIFY + 8 HANDOFF/VER). VER-12 (live RU-domain email-deliverability probe) + VER-14 (15-template owner countersign) ratification deferred to v1.7 as DEFER-46-01/02.*
*v1.7 Coverage: 48/51 v1.7 requirements delivered (8 INFRA + 6 ADAPTER + 8 PAY + 9 WH/FISCAL-foundation + 8 FISCAL-FSM/REFUND + 5 NOTIFY + 4 VER). 3 operator-credential-gated deferred at close: CARRY-01 (DEFER-46-01 live RU email probe) + CARRY-02 (DEFER-46-02 owner countersign) + VER-03 (ЮKassa sandbox walkthrough per D-04).*
*v1.8 Coverage: 30/30 v1.8 requirements mapped (3 INFRA + 5 REV + 4 CLR + 4 VIS-R + 6 AUD + 4 EXP + 2 HND + 2 VER).*
*v1.9 Coverage: 15/15 v1.9 requirements mapped (6 PAY + 4 REC + 4 RPT + 1 HND).*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (BACKLOG)

**Goal:** Restore `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking — in both code paths: `POST /time-off?force=true` (Phase 59, `schedule/service.py:925`) and `cancel_slot` booked-cascade (`schedule/service.py:~471-504`). Closes the pre-v1.9 WR-06 documented limitation.

**Product decision (locked 2026-05-26):** Option B — always restore on owner-initiated cancellation. Rationale: client must never lose a prepaid PT session due to gym-side cancellation (industry norm; alternative leaks support burden and invites disputes).

**Requirements:** TBD (target ~3 reqs: restore-on-time-off-force, restore-on-cancel-slot-cascade, audit-event emission)

**Plans:** 0 plans

Plans:
- [ ] TBD — cross-module raw `sa.text()` UPDATE on `pt_packages.sessions_remaining` (pattern D-38-11), same UoW as booking cascade, in both schedule paths
- [ ] TBD — register `pt_session_credit_restored` in `LOCKED_AUDIT_EVENTS` with payload `{client_id, pt_package_id, booking_id, cancel_reason, sessions_remaining_before/after}`
- [ ] TBD — regression tests pinning new behavior in `tests/integration/schedule/test_time_off.py::test_create_time_off_force_cascades_booking_and_dispatches_dm` + equivalent for `cancel_slot` cascade
- [ ] TBD — remove `NOTE WR-06` block at `schedule/service.py:937` once behavior is fixed

**Source:** Phase 59 UAT WR-06 pending item; product decision recorded in this conversation 2026-05-26. Promote with `/gsd:review-backlog` when v1.10 milestone opens.
