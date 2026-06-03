---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Membership self-service depth
status: verifying
stopped_at: Phase 79 shipped & verified (5/5); autonomous mode advancing to Phase 80 (Booking Reschedule)
last_updated: "2026-06-03T14:54:46.204Z"
last_activity: 2026-06-03
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 29
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-03 — v2.2 Membership self-service depth opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 80 — booking-reschedule

## Current Position

Phase: 80 (booking-reschedule) — EXECUTING
Plan: 3 of 3
Status: Phase complete — ready for verification
Last activity: 2026-06-03

Milestone progress (real v2.2 = 3 phases): [███░░░░░░░] 1/3 (33%)

## v2.2 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 79. Payment Methods Foundation + Card-on-File | Клиент привязывает карту через чекаут и управляет ею через client-portal | PAYM-01, PAYM-02, PAYM-03, PAYM-04 |
| 80. Booking Reschedule | Клиент переносит бронь атомарно (cancel+create) + PWA wiring | RESCH-01, RESCH-02, RESCH-03 |
| 81. Weekly Activity + PWA Flag Flips + OpenAPI Handoff | Недельная активность + linkedCard/weeklyActivity ON + openapi regen | WACT-01, WACT-02, PAYM-05, HND-01 |

**Coverage:** 11/11 v2.2 requirements mapped (zero orphans, zero duplicates).

## Accumulated Context

### Key v2.2 Scope Decisions (locked)

- **Autopay UI-only (locked)**: store card token + autopay preference + ФЗ-376 `consent_recorded_at`, NO recurring charges. `charge_expiring_autopay` ARQ cron deferred to v2.3 (APAY-01..03)
- **Save-during-payment**: client sends `save_payment_method=true` in checkout body; token captured from `payment.succeeded` webhook (NEVER from sync `create_payment` response)
- **New module**: `app/modules/payment_methods/` added to `.importlinter` `modules-independent` contract
- **Webhook token-save**: raw SQL upsert inside `handle_payment_succeeded` 8-step atomic UoW (step 8.5), zero new `ignore_imports`
- **Reschedule = cancel+create**: atomic cancel-old-slot + create-new-slot in one transaction, NOT in-place `slot_id` UPDATE
- **Weekly activity**: group by `visits.gym_date` STORED column; never `DATE(checked_in_at)`; `minutes=null` (no duration column in schema)
- **Migration sequence**: 0052 = `client_payment_methods`; 0053 = widen `booking_notifications.kind` CHECK for `'rescheduled'`
- **Per-booking autopay toggle removed**: «Авто-оплата тренировок» is an anti-feature (double-billing vs PT-package credit model)

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
| human-verify | Phase 79 live ЮKassa sandbox card-save round-trip | deferred (OPERATOR-PENDING; user "defer & continue" 2026-06-03) |
| tech-debt | **Pre-existing (NOT Phase 79):** `alembic check` / `test_alembic_clean` fails — `app.modules.promo_codes.models` never registered in `alembic/env.py` since the `online_payments.promo_code_id` FK shipped in v2.0 (commit b61054f4). One-line env.py import fixes it. | noted — out of v2.2 scope |
| tech-debt | **Pre-existing (NOT Phase 79):** whole-tree `ruff check` red (~44 errs) in `tests/test_client_promo_validate.py`, `test_client_checkout_promo.py`, `test_client_me_service.py`, `promo_codes/service.py` etc. (incl. F821 undefined names → those promo tests error on collection) | noted — out of v2.2 scope |
| flaky-test | **Pre-existing (NOT Phase 79):** `test_freeze_race::test_concurrent_freeze_race_serialised_by_partial_unique_index` asserts exact 409 *reason-code* distribution under concurrency (timing-dependent: gets `invalid_transition` vs `already_frozen`) | noted — test-quality issue |

## Session Continuity

Last session: 2026-06-03T14:54:46.199Z
Stopped at: Phase 79 shipped & verified (5/5); autonomous mode advancing to Phase 80 (Booking Reschedule)
Resume: Autonomous continues with Phase 80; or run `/gsd:plan-phase 80` manually
