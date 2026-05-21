# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- 🔄 **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (active)

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

### v1.7 Online Payments + 54-ФЗ (Phases 47-53) — ACTIVE

- [x] **Phase 47: Bedrock** (7/7 plans) — completed 2026-05-21 — INFRA-34..41 *(1 scope adjustment: `app.modules.online_payments` modules= entry deferred to Phase 49 commit-1 per import-linter 2.11 limitation, user-approved Option A; 47-VERIFICATION.md: 5/5 success criteria + 8/8 reqs PASSED)*
- [ ] **Phase 48: ЮKassa Integration Adapter** — Pure async httpx wrapper, IP verifier, receipt helpers, and `respx` test fixtures (parallels v1.6 Phase 42 email adapter)
- [ ] **Phase 49: Online Sales Orchestrator** — `online_payments` module, sell + QR endpoints, `return_url` anti-oracle pending screen, email gate, composition root wiring
- [ ] **Phase 50: Webhook FSM + Fiscal Foundation** — Webhook handler, payment FSM, `record_payment(method='online')`, `fiscal_receipts` table, and atomic UoW in a single phase
- [ ] **Phase 51: Fiscal FSM + Refunds** — Receipt webhook FSM, ARQ dispatch with circuit breaker, and online refund endpoints
- [ ] **Phase 52: Cross-Channel Notifications + v1.6 Carry-out** — Telegram + email DMs wired post-commit; DEFER-46-01 (live RU email probe) and DEFER-46-02 (15-template countersign) closed
- [ ] **Phase 53: Milestone Verification** — Operator runbook, race tests, DEFER-46-03 re-run, ≤5 inline regressions hard cap

---

## Phase Details

### Phase 47: Bedrock
**Goal**: Establish all v1.7 infrastructure primitives — audit events, settings, constants, converters, and Protocol slots — before any ЮKassa callsite exists
**Depends on**: Phase 46
**Requirements**: INFRA-34, INFRA-35, INFRA-36, INFRA-37, INFRA-38, INFRA-39, INFRA-40, INFRA-41
**Success Criteria** (what must be TRUE):
  1. `LOCKED_AUDIT_EVENTS` contains all 9 new v1.7 identifiers and the AST gate rejects any non-literal callsite
  2. `YooKassaSettings` loads from `.env` with `SecretStr` for `secret_key`; `.env.example` documents every field; no real credentials appear in git
  3. `YOOKASSA_TRUSTED_IPS` frozenset is present and the AST gate rejects any non-literal `verify_yookassa_ip` callsite
  4. `kopecks_to_yookassa` and `yookassa_to_kopecks` converters pass ≥10 unit tests covering edge cases (0, 1, 99, 100, 9999999, rounding, negative, leading zeros)
  5. Alembic 0033 applies cleanly: `clients.email` column exists with a partial UNIQUE on `lower(email) WHERE email IS NOT NULL AND deleted_at IS NULL`
**Plans**: 7 plans
  - [ ] 47-01-PLAN.md — LOCKED_AUDIT_EVENTS v1.7 extension + 9 payload classes (INFRA-34, INFRA-35)
  - [ ] 47-02-PLAN.md — YooKassaSettings + .env.example placeholders (INFRA-36)
  - [ ] 47-03-PLAN.md — YOOKASSA_TRUSTED_IPS + verify_yookassa_ip skeleton + AST gate (INFRA-37)
  - [ ] 47-04-PLAN.md — 4 Protocol slots + composition-root wiring + parity test (INFRA-38)
  - [ ] 47-05-PLAN.md — kopecks ↔ ЮKassa wire-format converters + ≥10 edge tests (INFRA-39)
  - [ ] 47-06-PLAN.md — Alembic 0033 partial UNIQUE on lower(email) + INFRA-41 wording (INFRA-41)
  - [ ] 47-07-PLAN.md — .importlinter preemptive online_payments registration + ignores (INFRA-40)

### Phase 48: ЮKassa Integration Adapter
**Goal**: Ship the complete async ЮKassa integration layer — httpx client, boot probe, receipt builder, IP verifier, and test fixtures — with no domain module consuming it yet
**Depends on**: Phase 47
**Requirements**: ADAPTER-01, ADAPTER-02, ADAPTER-03, ADAPTER-04, ADAPTER-05, ADAPTER-06
**Success Criteria** (what must be TRUE):
  1. `YooKassaClient.create_payment` and `create_refund` return typed result variants (success/error) and never re-raise SDK exceptions
  2. Boot-time factory logs a structured startup probe result via structlog; a failed probe does not prevent application startup (degraded mode)
  3. `build_receipt_item()` produces items with `payment_subject="service"` and `payment_mode="full_payment"` as Literal constants; AST gate rejects non-literal values
  4. `verify_yookassa_ip` `Depends()` callable returns 403 for IPs outside `YOOKASSA_TRUSTED_IPS`; sandbox flag bypasses the check when `YooKassaSettings.sandbox=True`
  5. `respx` fixtures provide 6 canonical responses (create-success, create-422, get-pending, get-succeeded, refund-success, webhook-payload) usable by all downstream tests
**Plans**: TBD

### Phase 49: Online Sales Orchestrator
**Goal**: Operator can initiate a redirect-based or QR online membership/PT-package sale and receive a `confirmation_url` back from the API
**Depends on**: Phase 48
**Requirements**: PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06, PAY-07, PAY-08
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/online-payments/memberships/{plan_id}/sell` returns `{ confirmation_url, online_payment_id }` when `clients.email IS NOT NULL`
  2. `POST /api/v1/online-payments/memberships/{plan_id}/sell-qr` returns a QR payload string; both sell variants share the same webhook path
  3. Either sell endpoint returns 422 `client_email_required_for_online_payment` when the client has no email address on file
  4. `GET /api/v1/online-payments/return` displays a static "ожидаем подтверждение" screen for all redirect outcomes with no payment-status information exposed
  5. Alembic 0034 applies cleanly: `online_payments` table exists with UNIQUE `(yookassa_payment_id)`, UNIQUE `(idempotency_key)`, and the double-tap partial UNIQUE guard
  6. Startup integration test asserts `YooKassaClientProvider` and `FiscalReceiptDispatcher` slots are non-None (AST parity test)
**Plans**: TBD

### Phase 50: Webhook FSM + Fiscal Foundation
**Goal**: `payment.succeeded` webhook activates a membership/PT-package, records a ledger payment, inserts a `fiscal_receipts` row, and commits atomically; `payment.canceled` records the cancellation reason
**Depends on**: Phase 49
**Requirements**: WH-01, WH-02, WH-03, WH-04, WH-05, WH-06, FISCAL-01, FISCAL-02, FISCAL-03
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/_internal/yookassa/webhook` returns 403 for requests from IPs outside `YOOKASSA_TRUSTED_IPS`; the AST gate test confirms the IP dependency runs before body parse
  2. A simulated `payment.succeeded` event causes the handler to re-fetch the payment via `GET /v3/payments/{id}` before writing to the DB (re-fetch-before-write verified by test)
  3. Redis `SET NX EX 86400` deduplication blocks a second identical webhook delivery from reaching the DB; the DB UNIQUE `(yookassa_payment_id)` provides a second layer of defense
  4. On `payment.succeeded`: `online_payments.status` is `succeeded`, a `payments` ledger row with `method='online'` is inserted, the membership/PT-package is activated, and a `fiscal_receipts(status='sent')` row is inserted — all in the same commit
  5. On `payment.canceled`: `online_payments.status` is `canceled` and the audit payload contains `cancellation_party` and `cancellation_reason` from the webhook body
  6. Alembic 0035 applies cleanly: `fiscal_receipts` table exists with UNIQUE `(payment_id, kind)` and FK to `payments.id`
**Plans**: TBD

### Phase 51: Fiscal FSM + Refunds
**Goal**: Fiscal receipt status is tracked end-to-end with ARQ retry and a circuit breaker; operator can initiate a full online refund that completes when `refund.succeeded` arrives
**Depends on**: Phase 50
**Requirements**: FISCAL-04, FISCAL-05, FISCAL-06, FISCAL-07, REFUND-01, REFUND-02, REFUND-03, REFUND-04
**Success Criteria** (what must be TRUE):
  1. `receipt.succeeded` webhook transitions `fiscal_receipts.status` from `sent` to `succeeded`; `receipt.canceled` transitions it to `failed`
  2. `dispatch_fiscal_receipt` ARQ task retries up to 3 times with exponential backoff; the Redis circuit breaker `sz:yookassa:circuit:receipts` opens on repeated failures and short-circuits subsequent dispatch attempts
  3. ARQ cron `monitor_stale_fiscal_receipts` detects `fiscal_receipts.status = 'pending'` rows older than 90 seconds and emits a `fiscal_receipt_failed` audit event
  4. `POST /api/v1/online-payments/memberships/{id}/refund` returns 202 and a refund row is created; the endpoint is analogous for PT-packages
  5. `refund.succeeded` webhook atomically: writes a refund row to `payments`, transitions membership/PT-package to `refunded`, inserts `fiscal_receipts(kind='refund')`, and enqueues a notification post-commit
  6. ARQ task `poll_pending_refunds` runs every 30 minutes and reconciles any refund row with `status='pending'` older than 30 minutes by calling `GET /v3/refunds/{id}`
**Plans**: TBD

### Phase 52: Cross-Channel Notifications + v1.6 Carry-out
**Goal**: Payment and refund outcomes are communicated to clients via Telegram DM and email; two v1.6 operator deferrals (live email probe + template countersign) are formally closed
**Depends on**: Phase 51
**Requirements**: NOTIFY-01, NOTIFY-02, NOTIFY-03, NOTIFY-04, NOTIFY-05, CARRY-01, CARRY-02
**Success Criteria** (what must be TRUE):
  1. On `payment.succeeded`, client receives a Telegram DM and an email; UNIQUE `(payment_id, kind, channel)` prevents duplicate notifications across restarts
  2. On `refund.succeeded`, client receives a Telegram DM and an email via the same idempotency pattern
  3. When `fiscal_receipts.status` transitions to `failed`, the owner receives a `FISCAL_RECEIPT_FAILED_DM` Telegram alert and a best-effort owner email
  4. `LOCKED_EMAIL_TEMPLATES` frozenset is extended from 15 to 19 entries; AST gate continues to reject non-literal `template_id` arguments
  5. DEFER-46-01 is closed: live RU email-deliverability probe run against yandex.ru + mail.ru + rambler.ru; `Authentication-Results` headers captured to `.planning/handoff/v1.7-email-deliverability-evidence/`
  6. DEFER-46-02 is closed: owner countersigns all 15 v1.6 `LOCKED_EMAIL_TEMPLATES`; `signed_off_at` timestamp recorded in `.planning/handoff/v1.6-template-countersign.md`
**Plans**: TBD

### Phase 53: Milestone Verification
**Goal**: The complete v1.7 online-payment + fiscal-receipt flow is verified end-to-end via operator runbook and race tests; no more than 5 inline regressions are accepted
**Depends on**: Phase 52
**Requirements**: VER-01, VER-02, VER-03, VER-04, VER-05
**Success Criteria** (what must be TRUE):
  1. Operator runbook `v1_7_runbook.sh` executes all curl scenarios (sell → `payment.succeeded` webhook → membership activated → fiscal_receipts row confirmed → refund → idempotency-key replay) without manual intervention and all return expected status codes
  2. Race tests confirm: concurrent double-delivery of `payment.succeeded` is deduplicated by Redis + DB UNIQUE; a webhook arriving after Redis restart is caught by DB UNIQUE; concurrent refund + manual refund command is arbitrated by the partial UNIQUE on `refund_of`
  3. ЮKassa sandbox walkthrough evidence (owner-recorded membership sale + refund session) is captured to `.planning/handoff/v1.7-yookassa-sandbox-evidence/`
  4. DEFER-46-03 is closed: VER-09 scenario 08 cron-chain circuit-breaker fixture re-run confirms parity with the new `FISCAL-05` circuit breaker
  5. Total inline regressions discovered during this phase does not exceed 5; any excess is rolled to v1.8 DEFER list
**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 47. Bedrock | 0/7 | Planned | - |
| 48. ЮKassa Integration Adapter | 0/TBD | Not started | - |
| 49. Online Sales Orchestrator | 0/TBD | Not started | - |
| 50. Webhook FSM + Fiscal Foundation | 0/TBD | Not started | - |
| 51. Fiscal FSM + Refunds | 0/TBD | Not started | - |
| 52. Cross-Channel Notifications + v1.6 Carry-out | 0/TBD | Not started | - |
| 53. Milestone Verification | 0/TBD | Not started | - |

---

*Roadmap last updated: 2026-05-21 — v1.7 Online Payments + 54-ФЗ roadmap created. Phases 47-53 covering 51 requirements across 7 phases. v1.6 ended at Phase 46; v1.7 starts at Phase 47.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped.*
*v1.6 Coverage: 48/48 v1.6 requirements satisfied (8 INFRA + 11 EMAIL/AUTH-EM + 7 USERS + 5 RESET + 9 NOTIFY + 8 HANDOFF/VER). VER-12 (live RU-domain email-deliverability probe) + VER-14 (15-template owner countersign) ratification deferred to v1.7 as DEFER-46-01/02.*
*v1.7 Coverage: 51/51 v1.7 requirements mapped (8 INFRA + 6 ADAPTER + 8 PAY + 9 WH/FISCAL-foundation + 8 FISCAL-FSM/REFUND + 7 NOTIFY/CARRY + 5 VER).*
