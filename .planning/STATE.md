---
gsd_state_version: 1.0
milestone: v2.4
milestone_name: Content & Communication — Client-First
status: executing
stopped_at: Phase 86 UI-SPEC approved
last_updated: "2026-06-06T05:39:14.382Z"
last_activity: 2026-06-06
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 3
  completed_plans: 1
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 86 — Gym-Info / CMS

## Current Position

Phase: 86 (Gym-Info / CMS) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Last activity: 2026-06-06

## v2.4 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 86. Gym-Info / CMS | Клиент видит gym-info из БД; owner управляет через write-API; baseline засеян | GYM-01, GYM-02, GYM-03 |
| 87. Notification Inbox | In-app лента уведомлений от системных событий; read/mark-all; push-token регистрация; PWA wired | INBOX-01, INBOX-02, INBOX-03, INBOX-04, INBOX-05 |
| 88. Trainer Detail / Bio | Полный профиль тренера (bio/специализация/фото); owner write-API; seed; PWA TrainerDetailSheet wired | TRNR-01, TRNR-02, TRNR-03, TRNR-04 |
| 89. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts regen + `_v24Checks` forward-guards + milestone gate зелёный | HND-01 |

**Coverage:** 13/13 v2.4 requirements mapped (zero orphans, zero duplicates). Execution order: 86 → 87 → 88 → 89.

<details>
<summary>v2.3 Roadmap Summary (shipped)</summary>

| Phase | Goal | Requirements |
|-------|------|--------------|
| 82. Loyalty Foundation — Ledger + Balance + Accrual | Append-only бонус-ledger, balance + history read API, welcome auto-credit, owner-grant API, audit events | LOYL-01, LOYL-02, LOYL-03, ACCR-01, ACCR-02, ACCR-03 |
| 83. Bonus Redemption at Checkout | Server-authoritative `discount_kopecks` recompute + webhook-locked redemption (образец `promo_codes`) + PWA `clubBonuses` flag flip | REDM-01, REDM-02, REDM-03 |
| 84. Real Autopay Charge | Off-session YooKassa charge cron для истекающих autopay-абонементов + charge-ledger + notifications (изолированный highest-risk блок) | APAY-01, APAY-02, APAY-03, APAY-04 |
| 85. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts regen + `_v23Checks` forward-guards + staff drift gate | HND-01 |

**Coverage:** 14/14 v2.3 requirements mapped (zero orphans, zero duplicates). Execution order: 82 → 83 → 84 → 85.

</details>

<details>
<summary>v2.2 Roadmap Summary (shipped)</summary>

| Phase | Goal | Requirements |
|-------|------|--------------|
| 79. Payment Methods Foundation + Card-on-File | Клиент привязывает карту через чекаут и управляет ею через client-portal | PAYM-01, PAYM-02, PAYM-03, PAYM-04 |
| 80. Booking Reschedule | Клиент переносит бронь атомарно (cancel+create) + PWA wiring | RESCH-01, RESCH-02, RESCH-03 |
| 81. Weekly Activity + PWA Flag Flips + OpenAPI Handoff | Недельная активность + linkedCard/weeklyActivity ON + openapi regen | WACT-01, WACT-02, PAYM-05, HND-01 |

**Coverage:** 11/11 v2.2 requirements mapped (zero orphans, zero duplicates).

</details>

## Accumulated Context

### Key v2.4 Milestone Constraints (locked, D-86-STAFF)

- **Staff gate**: owner-only write-API + seeds, NO admin-web UI; `apps/admin-web` frozen (не трогаем)
- **Client-only**: все клиентские read-эндпоинты под `require_client()`, IDOR-safe (client_id только из principal)
- **Staff contract**: байт-в-байт с `contract-freeze-v1.11.0` — drift gate должен быть зелёным
- **Inbox source**: только системные события (бронь/платёж/autopay) — нет broadcast/ручного-composer
- **Trainer reviews out of scope**: только bio/detail; REVW-* → v2
- **Module discipline**: D-20-MODULE (raw-SQL reads / Protocol-slot writes; zero new `ignore_imports` по возможности) + D-20-IDOR

### Key v2.2 Scope Decisions (locked)

- **Autopay UI-only (locked)**: store card token + autopay preference + ФЗ-376 `consent_recorded_at`, NO recurring charges. `charge_expiring_autopay` ARQ cron deferred to v2.3 (APAY-01..03)
- **Save-during-payment**: client sends `save_payment_method=true` in checkout body; token captured from `payment.succeeded` webhook (NEVER from sync `create_payment` response)
- **New module**: `app/modules/payment_methods/` added to `.importlinter` `modules-independent` contract
- **Webhook token-save**: raw SQL upsert inside `handle_payment_succeeded` 8-step atomic UoW (step 8.5), zero new `ignore_imports`
- **Reschedule = cancel+create**: atomic cancel-old-slot + create-new-slot in one transaction, NOT in-place `slot_id` UPDATE
- **Weekly activity**: group by `visits.gym_date` STORED column; never `DATE(checked_in_at)`; `minutes=null` (no duration column in schema)
- **Migration sequence**: 0052 = `client_payment_methods`; 0053 = widen `booking_notifications.kind` CHECK for `'rescheduled'`
- **Per-booking autopay toggle removed**: «Авто-оплата тренировок» is an anti-feature (double-billing vs PT-package credit model)

### Key v2.3 Phase 83 Decisions

- **REDM-03 PWA wiring**: `bonusOn` + `balanceKopecks` lifted to `CheckoutSheet` scope (mirrors `savePaymentMethod` pattern) so `launchCheckout` can include `loyaltyRedeemKopecks` in request body; `bonusEstimateKopecks` is display-only (D-06 invariant — never mutates server-derived `total`/`discount`)
- **Bonus section hidden on zero/loading/error**: mirrors CardSheet "no card = no section" pattern — no empty state copy shown
- **openapi.json regen**: additive only; Phase 85 owns byte-stable freeze

### Key v2.3 Phase 84 Plan 03 Decisions

- **D-84-09 Migration 0057 widen payment_notifications.kind CHECK**: 'autopay_charge_succeeded' added (4→5 kinds); raw DDL per D-84-01; Rule 2 auto-fix (missing constraint for correctness)
- **D-84-10 Autopay success recipient via online_payments.client_id**: direct column read instead of payments-ledger chain (_resolve_client_row not applicable for online_payment_id-keyed kind)
- **D-84-11 import-linter edge online_payments.tasks → autopay_charges.notifications**: one narrow ignore edge for success DM renderer import; scoped to tasks.py only

### Key v2.3 Phase 84 Plan 02 Decisions

- **D-84-05 Webhook discriminator test location**: plan specified test_charge_expiring_autopay.py but `async with session.begin()` in handler conflicts with SAVEPOINT db_session; moved to webhook_yookassa/ (real-commit fixtures)
- **D-84-06 UUID→str at audit emit**: AutopayCharge audit payloads require str for JSONB; Pydantic validates UUID from str (matches all other v1.4 emit callsites)
- **D-84-07 is_autopay_local capture**: row is detached after session.begin() exits; capture discriminator before commit boundary
- **D-84-08 Literal kind via if/else**: notification_kind local var with if/else produces literal 'autopay_charge_succeeded'/'payment_succeeded' at assignment site

### Key v2.3 Phase 84 Plan 01 Decisions

- **D-84-01 Raw DDL for CHECK modification**: `op.drop_constraint` passes name through naming convention template → double-prefix on already-expanded names. Use `op.execute("ALTER TABLE ... DROP/ADD CONSTRAINT ...")` for modifying constraints on existing locked tables (migration 0056 precedent for online_payments check widening)
- **D-84-02 Alembic _include_object skip-list for plain indexes**: Indexes created via `op.f()` in migration but absent from ORM `__table_args__` appear as "removed" orphans in `alembic check` autogenerate diff. Must add literal names to skip-list (same lineage as loyalty_ledger indexes)
- **D-84-03 Dedicated autopay_charge_notifications table**: Phase 52 `payment_notifications` XOR CHECK + partial-unique indexes cannot accommodate a third subject FK (decline path has no online_payments row). Separate additive table per-plan discipline
- **D-84-04 online_payment_id without FK on autopay_charges**: Cross-module nullable UUID column (D-54-08) — Plan 02 writes it via raw SQL after successful YooKassa call; no declarative FK to keep modules-independent

### Key v2.0/v2.1 Decisions (carry-forward)

- **D-20-PRINCIPAL**: `ClientPrincipal` + `require_client()` + `aud:"client"` — `Role.CLIENT` BANNED
- **D-20-MODULE**: `client_portal/` raw-SQL reads (D-54-08); Protocol-slot writes; zero new `ignore_imports`
- **D-20-IDOR**: Every client-scoped endpoint carries `client_id` from principal only; 404-collapse on non-owned
- **D-06 webhook-locked activation**: membership activation locked to `payment.succeeded` only

### Pending Todos

- **Future milestones sequence (post-v2.2)** — v2.3 autopay cron + v2.4 staff-side content domains. See `.planning/todos/pending/2026-06-02-future-milestones-sequence-post-v2-1.md`

### Blockers/Concerns

None.

## Deferred Items

**v2.3 close (2026-06-06) — acknowledged open artifacts (10):** 8 quick-tasks with empty status fields (historical shipped work — the 999.x DONE/SHIPPED roadmap markers: `260529-ny2`, `260529-olc`, `260601-*` client-pwa tasks); 1 pending todo (`future-milestones-sequence` — intentional next-milestone planning); 1 verification gap (Phase 83 `human_needed` — live-ЮKassa bonus-redemption E2E, OPERATOR-PENDING by design, auto-deferred). None block v2.3 completion; logic paths covered by ASGITransport/respx suites.

Items carried forward from v2.1 close:

| Category | Item | Status |
|----------|------|--------|
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| backlog | RUN-05 trainer accrual scenario (D-67-03) | Phase 999.x / future |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit bucket, QR post-decode existence, cancel idempotency) | deferred → `/gsd:secure-phase 70` |
| backlog | Promo-code admin CRUD UI (999.4 — only seeded codes exist) | deferred (admin-web frozen) |
| production | RUN-01 live ЮKassa credentialed checkout leg (D-72-06) | OPERATOR-PENDING by design |
| tech-debt | Pre-existing `ruff I001` in `client_portal/router.py` | ✅ closed — folded into Phase 79 (79-04) |
| correctness | WR-75-02: receipt-lookup join heuristic (repeat same-plan purchases) | deferred — out of v2.2 scope |
| human-verify | Phase 76 PDATA-02 live persistence check | deferred by user |
| human-verify | Phase 78 live checks (FIT15 chip + notif toggle) | deferred by user |
| human-verify | Phase 83 live ЮKassa bonus-redemption end-to-end (checkout with loyaltyRedeemKopecks → webhook → loyalty_ledger redemption row + balance decrease) | deferred — OPERATOR-PENDING (live YooKassa); ASGITransport tests cover the logic path |
| human-verify | Phase 82 PWA loyalty surface (Profile LoyaltyBalanceCard + BonusHistorySheet) | ✅ VERIFIED in browser 2026-06-06 — dev client w/ seeded 800₽ (welcome 500₽ + owner_grant 300₽): Profile shows «Бонусный счёт · ДОСТУПНО БОНУСОВ 800 ₽»; history sheet lists «Приветственный бонус +500 ₽» + «Бонус от зала +300 ₽» grouped under ИЮНЬ 2026 with correct dates (LOYL-01/02/03 read path live) |
| human-verify | Phase 83 PWA CheckoutSheet bonus UX (toggle, estimate row + ~ chip + pay-button prefix, section-hidden-on-zero) | ✅ VERIFIED in browser 2026-06-06 — БОНУСЫ КЛУБА section shows real «На счёте 800 ₽»; toggle ON adds «Бонусы [~] −800 ₽» row, К оплате recalculates 5000→4200 ₽, «Ваша выгода 800 ₽», pay button «Оплатить · ~4 200 ₽» (the ~ prefix surfaces the D-06 display-only-estimate invariant). Section-hidden-on-zero still covered by 8 vitest behaviors |
| human-verify | Phase 84 live off-session autopay charge (cron → real YooKassa charge on saved card → payment.succeeded webhook → renewal activation + charge-ledger + Telegram/email) | deferred — OPERATOR-PENDING (live YooKassa creds + a real saved card); respx tests + full skip/idempotency/double-charge/transient suites cover the logic path |
| human-verify | Phase 79/81.1 live ЮKassa card-save round-trip (PWA checkout opt-in → webhook → CardSheet) | ✅ VERIFIED in browser 2026-06-03 — test card 5555…4477 → 3DS → success → webhook step-8.5 saved real 36-char token; `online_payments.save_payment_method=t`, status succeeded |
| human-verify | Phase 80 live PWA reschedule slot-list population (dev server + reseed) | ✅ VERIFIED in browser 2026-06-03 — same-trainer slot listed + reschedule executed (atomic cancel+create, slot flip, PT-credit preserved, booking_rescheduled audit) |
| human-verify | Phase 80 live Telegram reschedule-DM delivery | deferred (OPERATOR-PENDING; code+tests prove send; no live Telegram chat) |
| human-verify | Phase 81 activity-bars visual rendering (heights/colors/zero-day baseline) | ✅ VERIFIED in browser 2026-06-03 — Пн/Ср/Пт filled, Вт/Чт/Сб/Вс flat, matches seeded visits |
| human-verify | Phase 81 CardSheet with a real saved card | ✅ VERIFIED in browser 2026-06-03 — card •••• 4477 displayed; autopay+ФЗ-376 consent enable (consent_recorded_at set) + unlink (soft-delete, GET→null) all exercised |
| compliance | Phase 81 ФЗ-376 consent disclosure shows generic "стоимость текущего тарифа" not a concrete ₽ amount (REVIEW IN-04) | **needs legal review** — interpolate concrete amount if required for compliance |
| tech-debt | **Pre-existing (NOT Phase 79):** `alembic check` / `test_alembic_clean` fails — `app.modules.promo_codes.models` never registered in `alembic/env.py` since the `online_payments.promo_code_id` FK shipped in v2.0 (commit b61054f4). One-line env.py import fixes it. | noted — out of v2.2 scope |
| tech-debt | **Pre-existing (NOT Phase 79):** whole-tree `ruff check` red (~44 errs) in `tests/test_client_promo_validate.py`, `test_client_checkout_promo.py`, `test_client_me_service.py`, `promo_codes/service.py` etc. (incl. F821 undefined names → those promo tests error on collection) | noted — out of v2.2 scope |
| flaky-test | **Pre-existing (NOT Phase 79):** `test_freeze_race::test_concurrent_freeze_race_serialised_by_partial_unique_index` asserts exact 409 *reason-code* distribution under concurrency (timing-dependent: gets `invalid_transition` vs `already_frozen`) | noted — test-quality issue |

## Post-Close Full Test + Browser Verification (2026-06-03)

Ran the complete test suite + live browser verification of all v2.2 features after milestone close.

**Automated:** PWA 131/131 Vitest; backend 2505 passed (full suite); mypy --strict app clean; lint-imports 3/0; openapi/schema.d.ts drift gates clean. Remaining backend failures all PRE-EXISTING (test_alembic_clean, flaky test_freeze_race, 7 promo-validate errors).

**Browser (real PWA + live YooKassa test shop):** weekly-activity bars, CardSheet (display + ФЗ-376 autopay consent + unlink), booking reschedule (atomic + audit + PT-credit), and the full save-card checkout round-trip (test card → 3DS → webhook step-8.5 → real token in CardSheet) — all PASS.

**Two bugs found & fixed during verification (committed):**

1. `fix(v2.2)` — Phase 80 added `booking_rescheduled` to LOCKED_AUDIT_EVENTS but left the count-lock guard tests at 100; full-suite run caught it → bumped to 101 (`test_audit_taxonomy`, `test_phase51_audit_chain_invariants`).
2. `fix(client-pwa)` — **BookingManageSheet white-screened on any real booking** (`b.price.toLocaleString()` on undefined; real `/client/home` nextBooking has no price/hoursTo) → made reschedule+cancel unreachable in the live PWA despite passing mock-based Vitest. Derived hoursTo/date/time from startTime, guarded price/refund, added a real-shape regression test.

## Session Continuity

Last session: 2026-06-06T05:39:14.377Z
Stopped at: Phase 86 UI-SPEC approved
Resume: Start Phase 86 with /gsd:plan-phase 86

## Operator Next Steps

- Start Phase 86 with /gsd:plan-phase 86
