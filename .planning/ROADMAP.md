# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- 🚧 **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (in progress)

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

---

### 🚧 v1.5 Schedule + Bookings (PT slots) (In Progress)

**Milestone Goal:** Close the last empty business-module gap. Trainers publish 1:1 PT availability windows; clients book individual sessions via reception, owner, or Telegram bot `/book`; the booking lifecycle (`confirmed → cancelled / no_show / completed`) is race-safe at the DB layer and audit-traceable end-to-end. Group classes (capacity > 1) remain explicitly out of scope.

## Phase Details (v1.5)

### Phase 37: Foundations Bedrock
**Goal**: All architectural contracts, RBAC permissions, audit taxonomy, FSM constants, and Protocol slot signatures for schedule + bookings are locked before any module service code is written
**Depends on**: Phase 36 (v1.4 complete)
**Requirements**: INFRA-24, INFRA-25, INFRA-26, INFRA-27, INFRA-28, INFRA-29, INFRA-30, INFRA-31, INFRA-32, INFRA-33, DEBT-06
**Success Criteria** (what must be TRUE):
  1. `LOCKED_AUDIT_EVENTS` frozenset contains exactly 58 entries (live baseline 53 + 5 new v1.5 events; supersedes the original "56" target per pattern-mapper verification of HEAD) and `test_audit_taxonomy.py` count assertion passes CI (INFRA-24/25)
  2. `Resource.SCHEDULE_SLOTS` and `Resource.BOOKINGS` are importable from `app.core.permissions`; the RBAC parity test passes with the updated `OWNER_ONLY` frozenset (INFRA-26/27)
  3. `import-linter` `modules-independent` contract rejects any direct import between `app.modules.schedule` and `app.modules.bookings` or between those modules and existing business modules (INFRA-28)
  4. `BOOKING_STATUS_TRANSITIONS` and `SLOT_STATUS_TRANSITIONS` constants exist in their respective module `constants.py` files and a unit test asserts the complete legal transition set (INFRA-30/31)
  5. A startup integration test asserts all three new Protocol slots (`SlotByIdResolver`, `BookingSlotRestorer`, `BookingCompleter`) are non-None after `create_app()` returns; `register_active_pt_package_resolver` is also present in `telegram_bot.py:main()` (INFRA-32/33, DEBT-06)
**Plans**: 5 plans
- [x] 37-01-PLAN.md — Audit taxonomy: extend LOCKED_AUDIT_EVENTS 53->58 + 5 Pydantic v2 payload schemas + PtSessionRecordedPayload.booking_id extension + count-assert refresh (INFRA-24, INFRA-25)
- [x] 37-02-PLAN.md — RBAC extension: Resource.SCHEDULE_SLOTS + Resource.BOOKINGS + Action.LIST + 4 OWNER_ONLY pairs + frontend registry.ts/can.ts byte-parity mirror + TEST-06 refresh (INFRA-26, INFRA-27)
- [x] 37-03-PLAN.md — FSM constants: schedule/constants.py:SLOT_STATUS_TRANSITIONS + bookings/constants.py:BOOKING_STATUS_TRANSITIONS (MappingProxyType) + unit tests (guard deferred to Phase 38 per v1.3/v1.4 precedent) (INFRA-30, INFRA-31)
- [x] 37-04-PLAN.md — Protocol slots + composition-root wiring: 3 new slots in dependencies.py + stub functions in schedule/service.py + bookings/service.py + main.py register chain + telegram_bot.py defensive double-wire (DEBT-06 + INFRA-33) + startup integration test + AST bot-subset-of-main parity test (INFRA-32, INFRA-33, DEBT-06)
- [x] 37-05-PLAN.md — Import-linter negative fixture (.importlinter contract already enumerates schedule+bookings on HEAD — no edit) + SVC001 walker scope extension for new service.py files (INFRA-28, INFRA-29)

### Phase 38: Schedule Module + Booking Core
**Goal**: Trainer availability slots can be published and listed; clients can be booked into slots with race-safe DB enforcement; PT-package integration (trainer_id column, refund guard, validity-window guard) and all booking read/write endpoints are operational
**Depends on**: Phase 37
**Requirements**: SLOT-01, SLOT-02, SLOT-03, SLOT-04, SLOT-05, SLOT-06, SLOT-07, SLOT-08, SLOT-09, BOOK-01, BOOK-02, BOOK-03, BOOK-04, BOOK-05, BOOK-06, BOOK-07, BOOK-08, BOOK-09, BOOK-10, PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06
**Success Criteria** (what must be TRUE):
  1. Owner can publish a slot (`POST /api/v1/trainer-slots`) and see it returned in `GET /api/v1/trainer-slots`; a second publish with an overlapping time range or within 10-minute buffer returns 409 `slot_overlap` or `slot_too_close` respectively (SLOT-01..06)
  2. Owner can cancel a slot with an outstanding confirmed booking via `PATCH /api/v1/trainer-slots/{id}/cancel` — the booking atomically transitions to `cancelled` in the same DB transaction and both `slot_cancelled` and `booking_cancelled` audit events are emitted (SLOT-07/09, BOOK-06)
  3. Two concurrent `POST /api/v1/bookings` requests for the same slot result in exactly one 201 and one 409 `slot_already_booked` (BOOK-02/03, BOOK-10); a single booking for a slot with `sessions_remaining = 0` returns 409 `pt_package_exhausted` (BOOK-04/05)
  4. `POST /api/v1/pt-packages/{id}/refund` returns 409 `outstanding_bookings_exist` when a confirmed booking against that package exists (PKG-03); `POST /api/v1/pt-sessions` with a `booking_id` atomically transitions the parent booking to `completed` in the same UoW as the session decrement (PKG-04/05)
  5. All booking and slot list endpoints (`GET /api/v1/bookings`, `GET /api/v1/trainer-slots`, `GET /api/v1/clients/{id}/bookings`) return paginated `{items, total, page, pageSize}` envelopes and honor their documented query filters (BOOK-07/08/09, SLOT-08)
**Plans**: 6 plans *(wave layout revised 2026-05-17 per plan-checker BLOCKER on 38-04 dependency_correctness — 38-04 moved from Wave 1 to Wave 3; see 38-CONTEXT.md §D-38-01 for rationale)*

_Wave 1 (alone):_
- [x] 38-01-PLAN.md — schedule-module: Alembic 0016 + schedule/{models,repository,schemas,router}.py + real schedule/service.py publish/list/get/cancel (active-only) (SLOT-01..06, SLOT-08, SLOT-09)

_Wave 2 (depends on 38-01):_
- [x] 38-02-PLAN.md — booking-core-create: Alembic 0017 (partial UNIQUE uq_bookings_slot_confirmed) + bookings/{models,repository,schemas,router}.py + real create_booking UoW + BOOK-TEST-01 race test (BOOK-01..05, BOOK-10)

_Wave 3 (parallel after 38-02 — all three depend on bookings table + 0017 alembic revision; zero files_modified overlap):_
- [x] 38-03-PLAN.md — booking-cancel-and-list: cancel_booking (24h reception window) + slot-cancel booked->cancelled cascade + list/get endpoints (SLOT-07, BOOK-06..09)
- [x] 38-04-PLAN.md — pt-package-trainer-and-refund-guard: Alembic 0018 + trainer_id schema/service + refund outstanding-bookings guard (PKG-01, PKG-02, PKG-03)
- [x] 38-05-PLAN.md — pt-session-booking-completion: Alembic 0019 + booking_id schema/service + SELECT FOR UPDATE + completion via Protocol slot + PKG-06 no-revert (PKG-04, PKG-05, PKG-06)

_Wave 4 (serial after all):_
- [x] 38-06-PLAN.md — svc001-and-importlinter-greens: CI gates + SVC001 + lint-imports + B-10 regression + optional DEFER-36-04-A sweep

### Phase 39: Notifications + Cron
**Goal**: Clients receive Telegram DMs for booking confirmation and cancellation; overdue confirmed bookings are auto-marked no-show by cron at 23:10 MSK; 24-hour reminders are sent by cron at 06:35 MSK with idempotency enforcement
**Depends on**: Phase 38
**Requirements**: NOTIFY-01, NOTIFY-02, NOTIFY-03, NOTIFY-04, NOTIFY-05, CRON-01, CRON-02, CRON-03, CRON-04, CRON-05
**Success Criteria** (what must be TRUE):
  1. A linked client receives the correct locked Russian DM when a booking is created (`BOOKING_CONFIRMED_DM`) and a different DM depending on who cancelled (`BOOKING_CANCELLED_BY_CLIENT_DM` vs `BOOKING_CANCELLED_BY_OWNER_DM`); owner copy-lock sign-off is recorded in PROJECT.md (NOTIFY-01/03/04)
  2. Running `run_no_show_cron_once.py` against a live stack with at least one overdue confirmed booking marks it `no_show` and emits `booking_no_show`; re-running the script processes zero rows (CRON-01/04)
  3. Running `run_booking_reminders_once.py` against a live stack sends `BOOKING_REMINDER_24H_DM` to linked clients with bookings in the 23h-25h window and inserts a `booking_notifications` idempotency row per send; re-running the script sends zero DMs (CRON-02/05, NOTIFY-05)
  4. Both new ARQ crons appear in `WorkerSettings.cron_jobs` with `unique=True, keep_result=60` and `on_job_start`/`on_job_end` structlog context vars fire on each cron tick (CRON-03)
**Plans**: 4 plans

_Wave 1 (alone):_
- [ ] 39-01-PLAN.md — notifications-module-and-copy: 4 locked Russian DM templates + `_BOT_BOOK_DENIED_DM` anti-oracle + 4 `render_*_dm` helpers + unit tests + owner copy-lock sign-off (NOTIFY-01, NOTIFY-02)

_Wave 2 (serial after 39-01):_
- [ ] 39-02-PLAN.md — send-on-create-and-cancel: `_dispatch_booking_dm` private helper + post-commit dispatch in `create_booking` / `cancel_booking` (actor.role discriminator) + per-cancelled-booking cascade in `schedule.cancel_slot` + integration tests (NOTIFY-03, NOTIFY-04)

_Wave 3 (serial after 39-02 — same-file conflict on bookings/service.py per D-39-01 Revision 2026-05-17):_
- [ ] 39-03-PLAN.md — no-show-cron-and-table: Alembic 0020_booking_notifications + `BookingNotification` ORM (no `telegram_chat_id` per D-39-03; ON DELETE RESTRICT per D-39-13) + `_mark_no_show_bookings` helper (SELECT FOR UPDATE OF b per D-39-07) + ARQ worker + `run_no_show_cron_once.py` + integration tests (NOTIFY-05, CRON-01, CRON-03, CRON-04)

_Wave 4 (serial after 39-03 — needs `BookingNotification` ORM + Alembic 0020 + same-file conflict on bookings/service.py):_
- [ ] 39-04-PLAN.md — reminder-cron: `_send_booking_reminders` multi-session helper + ARQ worker + `WorkerSettings.cron_jobs` final D-39-16 order (reminders BEFORE no-show) + `run_booking_reminders_once.py` + integration tests (CRON-02, CRON-03, CRON-05)

### Phase 40: Telegram /book + OpenAPI Drift Gate + Milestone Verification
**Goal**: Clients can book PT slots directly via Telegram bot `/book` using an anti-oracle InlineKeyboard flow; OpenAPI artifact is byte-stably regenerated with all v1.5 paths; 6 operator scenarios + Telegram sandbox smoke + concurrent race test confirm the full milestone is production-ready
**Depends on**: Phase 39
**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, HANDOFF-01, HANDOFF-02, VER-05, VER-06, VER-07, VER-08
**Success Criteria** (what must be TRUE):
  1. A Telegram-linked client with an active PT-package can send `/book`, receive an InlineKeyboard of up to 5 upcoming slots, tap one, and receive `BOOKING_CONFIRMED_DM`; a client without an active PT-package (or with no slots available) receives only `_BOT_BOOK_DENIED_DM` with no discriminating information (BOT-01..05)
  2. `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts` are byte-stable after regen; `git diff --exit-code` on both artifacts passes in CI; `schema.contract.test.ts` forward-guard includes `AssertNonNever` assertions for all new v1.5 paths (HANDOFF-01/02)
  3. All 6 operator curl scenarios pass against a live `docker compose up` stack: publish + list slot, book via reception, concurrent same-slot booking (one 201 / one 409), 24h cancel window (reception fails, owner succeeds), PT-package refund with outstanding booking (409), PT-session with `booking_id` completes the booking (VER-05)
  4. All 4 backend CI gates (ruff, mypy strict, pytest including BOOK-TEST-01 race, OpenAPI drift) are green; operator sign-off recorded in `.planning/milestones/v1.5-VERIFICATION-LOG.md` (VER-08)
**Plans**: TBD

---

## Progress

**Execution Order:** 37 → 38 → 39 → 40

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 37. Foundations Bedrock | 5/5 | Complete   | 2026-05-17 |
| 38. Schedule Module + Booking Core | 6/6 | Complete   | 2026-05-17 |
| 39. Notifications + Cron | 0/4 | Planned     | - |
| 40. Telegram /book + OpenAPI + Verification | 0/TBD | Not started | - |

---

*Roadmap last updated: 2026-05-17 — Phase 39 plans created (4 plans, 10 requirements covered: NOTIFY-01..05 + CRON-01..05) across 4 serial waves (39-01 → 39-02 → 39-03 → 39-04) per the 2026-05-17 D-39-01 revision (the original 3-wave layout claimed disjoint files_modified for Wave 2 but missed that 39-02 + 39-03 both edit bookings/service.py — same-file conflict forces serial execution). Phase 38 plans created previously (6 plans, 25 requirements: SLOT-01..09 + BOOK-01..10 + PKG-01..06). v1.5 Schedule + Bookings (PT slots) roadmap shipped 2026-05-17 (Phases 37-40, 57/57 requirements mapped). Prior milestones v1.0-v1.4 collapsed above.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0 Frontend Integration milestone per the 2026-05-15 pivot.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped (11 INFRA/DEBT → Phase 37; 25 SLOT/BOOK/PKG → Phase 38; 10 NOTIFY/CRON → Phase 39; 11 BOT/HANDOFF/VER → Phase 40).*
