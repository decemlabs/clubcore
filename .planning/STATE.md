---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Membership self-service depth
status: planning
last_updated: "2026-06-03T12:00:00.000Z"
last_activity: 2026-06-03
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-03 — v2.2 Membership self-service depth opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 79 — Payment Methods Foundation + Card-on-File

## Current Position

Phase: 79 of 81 (Payment Methods Foundation + Card-on-File)
Plan: —
Status: Ready to plan
Last activity: 2026-06-03 — Roadmap created; REQUIREMENTS.md traceability filled

Progress: [░░░░░░░░░░] 0%

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
| tech-debt | Pre-existing `ruff I001` in `client_portal/router.py` | noted — quick task or Phase 79 fold-in |
| correctness | WR-75-02: receipt-lookup join heuristic (repeat same-plan purchases) | deferred — out of v2.2 scope |
| human-verify | Phase 76 PDATA-02 live persistence check | deferred by user |
| human-verify | Phase 78 live checks (FIT15 chip + notif toggle) | deferred by user |

## Session Continuity

Last session: 2026-06-03
Stopped at: Roadmap created for v2.2 (Phases 79-81, 11/11 requirements mapped)
Resume: Run `/gsd:plan-phase 79` to begin planning Payment Methods Foundation
