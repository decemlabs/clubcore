# Project Research Summary

**Project:** clubcore v2.2 — Membership self-service depth
**Domain:** Gym CRM client PWA — card-on-file + autopay, booking reschedule, weekly-activity analytics
**Researched:** 2026-06-03
**Confidence:** HIGH

---

## Executive Summary

v2.2 deepens the already-shipped client PWA by unlocking three hidden UI components — `CardSheet`, `BookingManageSheet` reschedule view, and the weekly-activity bars on `ProfileScreen` — each gated by a feature flag (`linkedCard`, `weeklyActivity`) currently set to `false`. Two of the three features (reschedule, weekly activity) are almost entirely reuse of existing codebase patterns with no new dependencies. The third (card-on-file + autopay) introduces the only genuinely new infrastructure: a `client_payment_methods` table, extension of the `YooKassaClient` adapter, a webhook handler extension, and — depending on the scope decision — an ARQ cron for automated renewal charges.

**The most consequential decision for this milestone: does "autopay" mean UI-only (store token + toggle + consent, NO actual recurring charges) or full execution (ARQ `charge_expiring_autopay` cron that charges the saved card N days before membership expiry)?** Researchers disagreed: STACK.md recommends deferring the cron to v2.3; FEATURES.md and ARCHITECTURE.md include it in v2.2 MVP. The answer affects migration schema, test surface, and phase count. This must be locked before requirements are written.

The key regulatory constraint is РФ ФЗ-376 (effective March 2026): `consent_recorded_at` column is mandatory in migration 0052 regardless of whether the cron ships in v2.2 or v2.3. Additionally, YooKassa autopay requires explicit account manager activation (TEST-ONLY by default) — an OPERATOR-PENDING item with no code equivalent. The `linkedCard` PWA flag stays OFF until the operator confirms production activation.

---

## Key Findings

### Stack

No new Python libraries, no new frontend dependencies. The existing httpx-based `YooKassaClient` handles all new API calls via parameter extension. The `yookassa` SDK and any community async wrappers remain excluded.

**Core changes (all reuse, no version bumps):**
- `YooKassaClient` — extend `create_payment` with `save_payment_method: bool` + `payment_method_id: str | None`; add `get_payment_method()` method
- Alembic — one new table `client_payment_methods` (migration `0052`, next after confirmed-last `0051_seed_fit15_promo`), one CHECK widening `booking_notifications.kind` (migration `0053`)
- ARQ — new `charge_expiring_autopay` cron only if full-execution scope is chosen
- `visits.gym_date` STORED GENERATED column — used directly as week-boundary anchor; no new TZ computation needed

**What NOT to add:** `yookassa` SDK, `aioyookassa`, zero-amount binding flow (`payment_method.active` webhook), `duration_minutes` column on `pt_sessions`.

### Features

**Must have (table stakes):**
- `GET /client/payment-method` — display saved card or 200/null; `yookassa_method_id` token NEVER returned to client
- `DELETE /client/payment-method` — local soft-delete only; no YooKassa API call (YooKassa has no DELETE endpoint)
- `PATCH` autopay toggle — consent disclosure UI required before enabling; `consent_recorded_at` written to DB on opt-in
- Card saved during first checkout (via `save_payment_method: true`; token extracted from `payment.succeeded` webhook when `payment_method.saved == true` — NEVER from the synchronous `create_payment` response)
- `POST /client/booking/{id}/reschedule` — atomic cancel+create (NOT in-place `slot_id` UPDATE); same-trainer only; cancel-window cutoff enforced; partial-UNIQUE race guard reused
- `GET /client/activity/weekly` — 7 items (Mon–Sun, Europe/Moscow), `workouts` count per day, `minutes: null`; uses `visits.gym_date` STORED column directly

**Should have (only if full-execution scope):** `charge_expiring_autopay` cron (06:30 MSK), autopay failure DM, pre-charge DM 3 days before

**Defer to v2.3+:** PT session minutes on bars, zero-amount binding, autopay retry logic, card expiry warning, cross-trainer reschedule, reschedule count limit

**Remove from v2.2 MVP:** "Авто-оплата тренировок" per-booking toggle in CardSheet (double-billing risk with existing PT package credit model)

### Architecture

All three features live exclusively under `require_client()` in `app/modules/client_portal/`. Zero changes to frozen staff contract. One new module (`app/modules/payment_methods/`). Cross-module reads use raw SQL `text()` in `client_portal/repository.py` (D-54-08 discipline). Cross-module writes go through Protocol-slots.

**Major components added/modified:**
1. `app/modules/payment_methods/` (NEW) — token lifecycle; one new import-linter independence entry
2. `YooKassaClient` (MODIFIED) — `save_payment_method` param, `payment_method_id` param, `get_payment_method()` method
3. `online_payments/service.py` webhook handler (MODIFIED) — extra UoW step: raw SQL upsert when `payment_method.saved == true`
4. `client_portal/` (MODIFIED) — new endpoints, repository raw SQL for payment-method GET + weekly activity aggregate
5. `bookings/service.py` (MODIFIED) — `reschedule_booking_for_client` atomic-move
6. `charge_expiring_autopay.py` (NEW, scope-gated) — ARQ cron

**Pre-resolved architectural decisions:**
- Reschedule = cancel-old + create-new (two rows, one transaction), NOT in-place `slot_id` UPDATE
- Token save = inside `payment.succeeded` webhook UoW only, NOT from sync `create_payment` response
- Unbind = local soft-delete only, no YooKassa API call
- Weekly activity = use `gym_date` STORED column, never `DATE(checked_in_at)`

**Researcher disagreements to resolve (decisions, not contradictions):**
- Module placement: column on `client_portal` vs. new `payment_methods` module. Recommend new module (cleaner import-linter, consistent with `promo_codes` precedent).
- Autopay toggle route: `PATCH /client/membership/autopay` vs. `PATCH /client/payment-method/autopay`. Recommend the payment-method route — autopay is a property of the saved card.
- Cron timing: 06:10 vs. 06:30 MSK. Recommend 06:30 (safer buffer after `expire_memberships` at 06:05).

### Critical Pitfalls (top 7)

1. **Storing PAN instead of YooKassa token** — any `card_number`/`pan`/`cvv` column scopes the app into PCI DSS SAQ-D. Code-review the migration file first.
2. **Activating membership in the autopay cron, not the webhook** — cron creates the payment only; `payment.succeeded` webhook activates (D-06 invariant).
3. **Reschedule as in-place `slot_id` UPDATE** — breaks notification idempotency, audit trail, partial-UNIQUE race guard. Cancel+create is the only correct implementation.
4. **Missing ФЗ-376 consent disclosure** — `consent_recorded_at` mandatory in migration 0052; autopay toggle must show charge amount + frequency + opt-out before enabling.
5. **Timezone bug in weekly activity** — group by `visits.gym_date`, never `DATE(checked_in_at)`. Golden test: visit at 21:30 UTC must bucket to next Moscow calendar day (v1.8 VER-02 pattern).
6. **Unbind-while-charge-in-flight race** — autopay cron must re-check `is_active` + `autopay_enabled` inside the same transaction as the `online_payments` INSERT, using `SELECT FOR UPDATE`.
7. **YooKassa autopay not enabled in production** — TEST-ONLY by default; OPERATOR-PENDING runbook step; cron must distinguish `not_allowed` (operator gate, no retry) from `insufficient_funds`.

---

## Implications for Roadmap

### Suggested phases: 4 (UI-only scope) or 5 (full-execution scope)

**Phase 79 — Payment Methods Foundation + Card-on-File**
Everything else depends on migration 0052 and the webhook extension. Highest regulatory/security surface area — ship foundation first, cron second.
Delivers: migration 0052 (with `consent_recorded_at`), `payment_methods` module, YooKassa adapter extension, webhook save-step, GET/DELETE/PATCH payment-method endpoints, payment-method audit events.

**Phase 80 — Autopay Cron [SCOPE-GATED: only if full-execution]**
Highest-risk subfeature; isolating it makes the risk surface independently testable. If UI-only scope, defer to v2.3.
Delivers: `charge_expiring_autopay` ARQ cron (06:30 MSK), charge path extended for `payment_method_id`, autopay failure path (DM + disable), pre-charge notification, deterministic idempotency key.

**Phase 81 — Booking Reschedule**
Fully independent from payment methods. Migration 0053 depends on 0052 for numbering only.
Delivers: `reschedule_booking_for_client` Protocol slot, atomic-move orchestrator, `BOOKING_RESCHEDULED` locked audit event + DM template, migration 0053, `POST /client/booking/{id}/reschedule`, PWA wiring in `BookingManageSheet`.

**Phase 82 — Weekly Activity + PWA Flag Flips + OpenAPI Handoff**
Lowest risk; last so it captures all v2.2 endpoints in one OpenAPI regen.
Delivers: `GET /client/activity/weekly`, raw SQL aggregate (7-item zero-filled), flip `linkedCard` + `weeklyActivity` flags ON, byte-stable `openapi.json` + `schema.d.ts` regen, milestone verification gate. Golden TZ test mandatory.

### Research Flags

- Needs deeper planning research: **Phase 80** — concurrency contract, idempotency key derivation, renewal strategy (`renew_membership` vs `sell_membership`)
- Standard patterns (skip research-phase): Phases 79, 81, 82

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies. YooKassa API fields confirmed from official docs + codebase inspection |
| Features | HIGH | Derived directly from existing PWA component code + YooKassa docs |
| Architecture | HIGH | All patterns verified against live codebase. Migration sequence confirmed |
| Pitfalls | HIGH | YooKassa-specific + codebase-specific pitfalls confirmed from official docs and v1.5/v1.7/v1.8 precedents |

**Overall: HIGH**

### Gaps to address before requirements

1. **The autopay scope decision** (UI-only vs. full-execution cron) — blocking; affects phase count, schema, test surface
2. **`save_payment_method` opt-in:** user-controlled checkbox vs. unconditional always-save at checkout
3. **Autopay cron timing:** 06:10 vs. 06:30 MSK — recommend 06:30
4. **Autopay renewal strategy:** `renew_membership` (chained, preserves `previous_membership_id`) vs. `sell_membership` (fresh sale) — recommend `renew_membership`
5. **"Авто-оплата тренировок" toggle** — confirm removal from v2.2 before PWA wiring

---

### Ready for Requirements

4 research files committed (`5c6d83fb`). Proceed to requirements once the autopay scope decision is resolved.
