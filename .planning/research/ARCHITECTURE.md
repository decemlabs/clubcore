# Architecture Research: v2.2 Membership Self-Service Depth

**Domain:** Backend integration — modular monolith FastAPI + client PWA
**Researched:** 2026-06-03
**Confidence:** HIGH (all findings from live codebase inspection + YooKassa official docs)

---

## Established Architecture Constraints (DO NOT RE-RESEARCH)

The following are locked decisions from v2.0–v2.1 and must be respected:

- **Modular monolith** `app/modules/<domain>/` with `import-linter` enforcing: `modules independent`, `core ⊥ modules`, `integrations ⊥ modules`.
- **client_portal writes** go through Protocol-slot accessors in `app.core.dependencies` only — NO direct `from app.modules.bookings` / `app.modules.memberships` in `client_portal/`. Evidenced by: `cancel_booking_for_client`, `create_booking_for_client`, `create_visit_client_qr`, `invoke_client_checkout_core` slots.
- **client_portal reads** use raw SQL `text()` cross-module SELECTs in `client_portal/repository.py` (D-54-08 precedent from reports), no ORM imports of foreign models.
- **IDOR**: every owned-resource endpoint derives `client_id` from `require_client()` principal only, never from path/query/body. 404-collapse on non-owned resources (anti-oracle).
- **Webhook-locked activation**: membership activation is LOCKED to `payment.succeeded` webhook — redirect-back screen shows only an anti-oracle "ожидаем подтверждение" message.
- **SVC001** commit-gate: public mutating orchestrators commit their own UoW; `client_portal` router calls `await session.commit()` explicitly for write paths.
- **Audit events**: all new events must be pre-registered in `LOCKED_AUDIT_EVENTS` frozenset BEFORE any callsite (INFRA-15 discipline).
- **Money**: integer kopecks throughout; server-authoritative pricing (D-06).
- **TZ**: Europe/Moscow for all user-facing dates; UTC for idempotency keys and wire-protocol invariants.
- **Last migration**: `0051_seed_fit15_promo.py`. Next migration is `0052_*`.

---

## Feature A: Card-on-File + Autopay

### A.1 YooKassa Saved-Method API (HIGH confidence — official docs verified)

YooKassa supports saving payment methods during a regular redirect checkout by including `save_payment_method: true` in the payment create body. After `payment.succeeded`, the `payment_method` object in the webhook payload contains:

```
payment_method.id       — the saved method token (opaque string)
payment_method.type     — "bank_card"
payment_method.saved    — true
payment_method.title    — display string e.g. "Карта *4821"
payment_method.card.last4
payment_method.card.expiry_month / expiry_year
payment_method.card.card_type  — Visa / MasterCard / Mir / etc.
```

To charge with a saved method (autopay): `POST /v3/payments` with `payment_method_id: <token>`, `capture: true`, `amount`, `description`. **No user confirmation required** — this is a server-initiated charge.

Webhook events for autopay are the same as regular payments: `payment.succeeded` / `payment.canceled`. The activation discipline (webhook-locked, anti-oracle return screen) applies identically.

YooKassa does NOT provide a DELETE endpoint for saved payment methods. "Unbind" means deleting the token from your own storage and stop using it. No API call to YooKassa is required for unbind.

**Card type saving**: only `bank_card`, `yoo_money`, `sber_pay`, `t_pay`, `mir_pay`, `sbp` support saving. The PWA currently uses redirect checkout which supports all these.

### A.2 New Table: `client_payment_methods`

A new `client_payment_methods` table is needed to persist the token server-side. It does NOT belong in `online_payments` (that table is a per-payment ledger row, append-only, containing `yookassa_payment_id` — a different concept). It also should NOT be a column on `clients` — a client could have multiple saved methods in future, and token storage is a separate concern from identity.

**Owner**: new `app/modules/payment_methods/` module (greenfield). Justified because:
- The token is a durable client-owned credential, not a per-payment artifact.
- `client_portal` reads and writes it via Protocol-slot (D-20-MODULE).
- `online_payments` references it at autopay-charge time via raw SQL (same as plan-price reads with `text()` — no ORM import needed).
- `import-linter`: add `app.modules.payment_methods` to the independence contract.

**Schema** (Alembic `0052_client_payment_methods.py`):

```
client_payment_methods
  id                UUID PK
  client_id         UUID FK → clients.id ON DELETE RESTRICT NOT NULL
  yookassa_method_id TEXT NOT NULL   — the token from payment_method.id
  method_type       TEXT NOT NULL    — 'bank_card', 'yoo_money', etc.
  card_last4        VARCHAR(4) NULL  — only for bank_card
  card_expiry_month SMALLINT NULL
  card_expiry_year  SMALLINT NULL
  card_brand        TEXT NULL        — 'Visa', 'MasterCard', 'Mir', etc.
  display_title     TEXT NOT NULL    — payment_method.title from YooKassa
  is_active         BOOLEAN NOT NULL DEFAULT TRUE
  autopay_enabled   BOOLEAN NOT NULL DEFAULT FALSE
  created_at        TIMESTAMPTZ server_default now()
  updated_at        TIMESTAMPTZ
  UNIQUE (client_id, yookassa_method_id)  — prevents double-save same token
  INDEX (client_id) WHERE is_active=TRUE
```

**Why `is_active` not soft-delete mixin**: Tokens don't expire at DB layer. `is_active=FALSE` is an explicit unbind (client request or method expired). The `SoftDeleteMixin` pattern (timestamp-based) would add `deleted_at` semantics, which is overkill here and inconsistent with how the existing payment tables track lifecycle.

### A.3 Save Flow — Modification to Checkout

The save-during-payment path modifies the existing `POST /client/checkout/memberships/{plan_id}` handler. The client sends an optional `save_payment_method: bool` field in the checkout body (`ClientCheckoutRequest`). When `true`:

1. `online_payments.service._sell_subject_core` includes `save_payment_method: true` in the YooKassa payment create body (new optional parameter to `YooKassaClient.create_payment`).
2. On `payment.succeeded` webhook, the handler reads `payment_method.saved=true` and `payment_method.id` from the webhook payload.
3. The webhook handler upserts a `client_payment_methods` row via raw SQL inside the same `handle_payment_succeeded` 8-step atomic UoW.

**Critical invariant preserved**: membership activation is still webhook-locked. The method-save is a side-effect inside the same webhook UoW — the same `handle_payment_succeeded` 8-step atomic UoW gains a step 8.5: if `payload.payment_method.saved==true`, raw SQL upsert `client_payment_methods` within the same session before commit. This keeps it atomic.

The `online_payments` row should record `save_payment_method_requested: bool` (a new column on `online_payments`) so the webhook handler knows whether to look for a saved method — but this adds migration complexity. A simpler alternative: always check `payload.payment_method.saved` in the webhook handler and upsert if true, regardless of whether the checkout requested it. YooKassa only sets `saved=true` when explicitly requested, so there's no over-upsert risk.

### A.4 Autopay Flow — New ARQ Cron

Autopay requires a new cron job: `charge_expiring_autopay` that runs once per day (suggested 06:30 MSK, after `expire_memberships` at 06:05 and `send_expiring_notifications` at 06:15).

**Logic**:
1. SELECT clients with `autopay_enabled=TRUE` on their `client_payment_methods` (is_active=TRUE), whose membership `end_date = today + N` (e.g. N=1 — charge 1 day before expiry).
2. For each client, call `online_payments.service._sell_subject_core` with `payment_method_id=<token>` (not `save_payment_method=true` — that's only for binding).
3. YooKassa accepts `payment_method_id` in the create-payment body — no `confirmation` object needed (no user redirect; server-initiated).
4. Wait for `payment.succeeded` webhook — which triggers the normal `handle_payment_succeeded` 8-step UoW that activates the membership.

**Webhook-locked activation preserved**: the autopay charge is just another `POST /v3/payments`. Activation still happens exclusively on `payment.succeeded` webhook — identical discipline to manual checkout.

**Idempotency**: cron idempotency key = `sha256("autopay:{client_id}:{membership_id}:{today_utc}")`. If the cron fires twice or the worker restarts, the idempotency key prevents double-charge.

**Failure handling**: if the charge fails (`payment.canceled` or `transient_error`), the membership expires normally — the `expire_memberships` cron picks it up. Optionally: send a Telegram/email DM "автоплатёж не прошёл". No retry within the same day (too complex for v2.2 scope).

### A.5 Import-Linter: Where Does the Token-Save Live?

Two options for webhook token-save:

**Option A (preferred for webhook)**: `online_payments.service` (specifically the webhook handler) saves the token using raw SQL `INSERT INTO client_payment_methods ... ON CONFLICT DO UPDATE` inside the webhook UoW. This mirrors the D-49-03 / D-54-08 discipline: cross-module writes done via raw `text()` SQL, no ORM import needed. Zero new `ignore_imports` entries required.

**Option B**: Protocol-slot `SavePaymentMethodSlot` registered in `app.core.dependencies`, pointing to `payment_methods.service.save_method`. `online_payments` calls the slot. Cleaner architecturally, but adds composition-root plumbing for a simple INSERT.

**Recommendation**: Option A for the save-in-webhook path (pure raw SQL, zero new edges). For the autopay cron and `client_portal` endpoint writes, go through Protocol-slots (Option B pattern) since the cron and portal need richer business logic.

### A.6 Client-Portal Endpoints (New)

All under `/api/v1/client/` gated by `require_client()`:

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/client/payment-method` | GET | Return active saved method (last4 + brand + expiry) or null | require_client |
| `/client/payment-method` | DELETE | Unbind: set `is_active=FALSE`, `autopay_enabled=FALSE` | require_client + verify_client_csrf |
| `/client/payment-method/autopay` | PATCH | Toggle `autopay_enabled` boolean | require_client + verify_client_csrf |

GET response shape (client-safe, no token exposure):
```json
{
  "id": "<uuid>",
  "type": "bank_card",
  "last4": "4821",
  "brand": "Visa",
  "expiryMonth": 12,
  "expiryYear": 2027,
  "displayTitle": "Карта *4821",
  "autopayEnabled": true
}
```

**IDOR**: `client_id` from `require_client()` only. GET returns 200/null (not 404) when no method exists (D-69-03 precedent).

**Token never exposed to client**: `yookassa_method_id` is never included in any response schema. The client cannot reconstruct the token.

### A.7 Data Flow: Card-on-File

```
[PWA checkout with save_payment_method=true]
    ↓
POST /client/checkout/memberships/{plan_id}
    ↓
client_portal/service.client_checkout_membership
    ↓
invoke_client_checkout_core (Protocol slot)
    ↓
online_payments.service._sell_subject_core
  → YooKassaClient.create_payment(save_payment_method=True)
  → INSERT online_payments row (status=pending)
    ↓
[User completes payment at YooKassa redirect URL]
    ↓
POST /_internal/yookassa/webhook
  → handle_payment_succeeded (8-step atomic UoW)
  → step 5: activate membership (existing)
  → step 8.5: if payment_method.saved: raw SQL upsert client_payment_methods
    ↓
GET /client/payment-method → shows "•••• 4821"
```

```
[Autopay cron: charge_expiring_autopay 06:30 MSK]
    ↓
SELECT clients with autopay_enabled + membership end_date = tomorrow
    ↓
For each: online_payments.service._sell_subject_core(payment_method_id=<token>)
  → no confirmation object (server-initiated)
  → INSERT online_payments row (status=pending)
    ↓
POST /_internal/yookassa/webhook (payment.succeeded)
  → handle_payment_succeeded: renew membership (same 8-step UoW)
```

---

## Feature B: Booking Reschedule

### B.1 Decision: Atomic Move vs. Cancel + Rebook

**Recommendation: atomic move inside the bookings domain.** Rationale:

- Cancel + rebook would require two separate Protocol-slot calls and leave a window where the target slot could be taken between them — a race condition visible at the API level.
- The bookings domain already has `update_slot_status_predicate_gated` (raw SQL cross-module UPDATE) for slot status flips. Reschedule adds a second flip: `old_slot: booked → active`, `new_slot: active → booked`, both within the same transaction.
- A single `reschedule_booking` service function can do this atomically: SELECT FOR UPDATE the old booking, restore the old slot, flip the new slot, UPDATE the booking's `slot_id`.
- This mirrors the `cancel_booking` + `create_booking` discipline but avoids credit deduction (no PT session consumed on reschedule).

**Existing cancel_booking** already does: `old_slot: booked → active` (via `restore_booking_slot` Protocol slot). Reschedule is `cancel_booking` steps 1-4 + `create_booking` steps 5-9, atomically in one UoW, without emitting `booking_cancelled` — emitting `booking_rescheduled` instead.

### B.2 New Audit Events (pre-register before any callsite)

Add to `LOCKED_AUDIT_EVENTS` frozenset:
- `("booking_rescheduled", "booking")` — payload: `booking_id`, `old_slot_id`, `new_slot_id`, `client_id`

### B.3 IDOR + Ownership

The `POST /client/booking/{id}/reschedule` endpoint:
- `booking_id` from path.
- `client_id` from `require_client()` only — never from body.
- Service layer verifies `bookings.client_id == client_id` — 404-collapse on mismatch (anti-oracle, same as cancel).
- New slot: from `slot_id` in request body (client-supplied). Must be an available active future slot.
- The client's PT-package trainer-pin check still applies (cannot reschedule to a different trainer if the package pins one).

### B.4 Cancel-Window Constraint

The existing `CANCEL_WINDOW_HOURS_CLIENT = 24h` applies to reschedule too — cannot reschedule within 24h of the original slot's `start_time`. This is enforced by checking the OLD slot's `start_time`, mirroring cancel logic. Error code: `reschedule_window_expired` (409).

### B.5 New Protocol Slot

Add `reschedule_booking_for_client` to `app.core.dependencies`, wired to `bookings.service.reschedule_booking_for_client` in `app/main.py`. Shape:

```python
async def reschedule_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    new_slot_id: UUID,
) -> BookingResponse: ...
```

The `client_portal/service.py` calls this slot — zero new `ignore_imports` needed (same pattern as `cancel_booking_for_client`).

### B.6 BookingManageSheet Backend — Available Slots Already Exist

`GET /client/slots` already returns bookable active future slots filtered by trainer-pin (`client_portal/router.py`). The BookingManageSheet calendar in the PWA needs to call this existing endpoint when the client selects a reschedule date — no new backend read endpoint needed. The PWA just needs to pass the selected `slot_id` to the new reschedule endpoint.

### B.7 Notification

On successful reschedule, fire a `BOOKING_RESCHEDULED_DM` template (new locked constant in `bookings/notifications.py`) with the new slot time. This mirrors the create-booking `_dispatch_booking_lifecycle_notification` post-commit fire-and-forget pattern. Add `'rescheduled'` to the `booking_notifications.kind` CHECK (new migration needed to widen the CHECK constraint). Email-fallback follows the same Phase 45 D-45-05 pattern.

### B.8 Schema Change

Migration `0053_booking_notifications_reschedule_kind.py` widens `ck_booking_notifications_kind` CHECK to admit `'rescheduled'`.

No new columns on `bookings` table — `slot_id` is updated in-place. The audit trail is preserved via `booking_rescheduled` audit event.

### B.9 Data Flow: Reschedule

```
[PWA: BookingManageSheet user picks new slot]
    ↓
POST /client/booking/{id}/reschedule  { slotId: "<new_slot_uuid>" }
    ↓
client_portal/router  → require_client + verify_client_csrf
    ↓
client_portal/service.reschedule_client_booking
  → reschedule_booking_for_client (Protocol slot)
    ↓
bookings/service.reschedule_booking_for_client
  1. SELECT booking WHERE id=? AND client_id=? FOR UPDATE (IDOR + lock)
  2. Assert booking.status == 'confirmed'  → 404/409
  3. Assert old_slot.start_time > now + 24h  → 409 reschedule_window_expired
  4. Resolve new slot (SlotById Protocol slot) → 404/409
  5. Assert new_slot.status == 'active' AND future
  6. Trainer-pin check (same as create_booking step 3)
  7. UPDATE old_slot booked → active  (raw SQL restore)
  8. UPDATE new_slot active → booked  (raw SQL flip)
  9. UPDATE bookings SET slot_id = new_slot_id WHERE id = booking_id
 10. session.flush() → uq_bookings_slot_confirmed race guard
 11. audit.emit('booking_rescheduled', ...)
 12. session.commit()
 13. Post-commit: fire-and-forget DM notification (BOOKING_RESCHEDULED_DM)
    ↓
Returns updated ClientBookingResponse with new start_time + trainer_name
```

---

## Feature C: Weekly Activity Analytics

### C.1 Data Sources

- `visits` table: `client_id`, `gym_date` (STORED GENERATED column, Europe/Moscow), `checked_in_at`. One row per gym-day per client (UNIQUE constraint enforced).
- `pt_sessions` table: `client_id`, `performed_at` (timestamptz), `cancelled_at` (null = active). Represents PT training sessions.

**Critical finding**: there is NO `duration_minutes` column on either `visits` or `pt_sessions`. A "minutes per day" metric cannot be derived from the current schema. The milestone description says "серверный агрегат минут/тренировок по дням" — this requires a decision:

(a) Add a `duration_minutes` column to `visits` (defaulting to null or a configured gym-session average, e.g. 60 min), or
(b) Limit the aggregate to "workouts per day" (visit count + PT session count) rather than minutes.

**Recommendation for v2.2**: deliver "workouts per day" (count-based). The `minutes` field in the response schema is `null` until a `duration_minutes` column is added in a later milestone. The endpoint name `GET /client/activity/weekly` remains unchanged.

### C.2 Week Boundary Definition

- **"Current week"**: Monday–Sunday in Europe/Moscow. ISO week convention.
- Implementation: `date_trunc('week', now() AT TIME ZONE 'Europe/Moscow')` in Postgres returns Monday 00:00 of the current ISO week. Filter `gym_date >= <monday>` AND `gym_date <= <monday + 6 days>`.
- Always return 7 rows (one per day of the current week), filling zero-activity days with `workouts=0`.

### C.3 Read Pattern: Raw SQL in client_portal/repository.py

Follows D-54-08 / D-69 read discipline:
- No `from app.modules.visits import models` in `client_portal`.
- Raw SQL `text()` SELECT over `visits` and `pt_sessions` tables directly.
- `client_id` always in the WHERE clause (IDOR-safe: derived from `require_client()` principal).

```sql
-- visits per day this week
SELECT
    v.gym_date,
    COUNT(*) AS gym_visits
FROM visits v
WHERE v.client_id = :client_id
  AND v.gym_date >= date_trunc('week', now() AT TIME ZONE 'Europe/Moscow')::date
  AND v.gym_date <= (date_trunc('week', now() AT TIME ZONE 'Europe/Moscow')
                     + interval '6 days')::date
GROUP BY v.gym_date

-- pt sessions per day this week
SELECT
    (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date AS session_date,
    COUNT(*) AS pt_sessions
FROM pt_sessions ps
WHERE ps.client_id = :client_id
  AND ps.cancelled_at IS NULL
  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date
      >= date_trunc('week', now() AT TIME ZONE 'Europe/Moscow')::date
  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date
      <= (date_trunc('week', now() AT TIME ZONE 'Europe/Moscow')
          + interval '6 days')::date
GROUP BY session_date
```

Merge both in Python: build a 7-element list (Mon–Sun), zero-fill missing days, combine `gym_visits + pt_sessions` into `workouts` per day.

### C.4 Response Schema

```python
class DayActivity(BackendSchemaBase):
    date: date          # ISO date of the day
    workouts: int       # visits + pt_sessions count
    minutes: int | None # null until duration tracking added

class WeeklyActivityResponse(BackendSchemaBase):
    week_start: date       # Monday of the current week (Europe/Moscow)
    week_end: date         # Sunday
    days: list[DayActivity]  # always 7 elements
    total_workouts: int
    total_minutes: int | None
```

### C.5 Endpoint

```
GET /api/v1/client/activity/weekly
```

- No path/query parameters — always returns the current week.
- `require_client()` gate — no CSRF (safe GET).
- `client_id` from principal only (IDOR-safe).
- Empty week (no data) → 200 with 7 zero-workout days (D-69-03 precedent).
- No session.commit() — read-only path.

### C.6 No New Migration Required

No schema changes needed for the count-based approach. The existing `visits.gym_date` STORED GENERATED column makes week-boundary filtering straightforward without TZ conversion. The existing `ix_visits_client_id_checked_in_at` index covers per-client queries. `pt_sessions` lacks a `(client_id, performed_at)` index but at single-gym scale this is not a problem. Deferred until profiling indicates a need.

If minutes tracking is added later, that migration adds a nullable `duration_minutes INTEGER` column to `visits` + an app-layer default.

---

## New vs. Modified Components Summary

| Component | Status | Change |
|---|---|---|
| `app/modules/payment_methods/` | **NEW module** | `models.py` + `repository.py` + `service.py` (thin) |
| Alembic `0052_client_payment_methods.py` | **NEW migration** | `client_payment_methods` table |
| `app/integrations/yookassa/client.py` | **MODIFIED** | Add `save_payment_method` param to `create_payment`; add `payment_method_id` param for autopay charge |
| `app/integrations/yookassa/types.py` | **MODIFIED** | Add `payment_method_id` + `payment_method_saved` + `payment_method_title` + `payment_method_card` fields to `YooKassaPaymentResult` |
| `app/modules/online_payments/service.py` | **MODIFIED** | `_sell_subject_core`: accept optional `save_payment_method`, `payment_method_id` params |
| `app/modules/online_payments/router.py` (webhook) | **MODIFIED** | `handle_payment_succeeded`: step 8.5 — raw SQL upsert `client_payment_methods` when `payment_method.saved=true` |
| `app/core/dependencies.py` | **MODIFIED** | Add `reschedule_booking_for_client` Protocol slot; optionally `BindPaymentMethodSlot` |
| `app/main.py` | **MODIFIED** | Wire new Protocol slots at composition root |
| `app/modules/client_portal/router.py` | **MODIFIED** | New endpoints: GET/DELETE `/client/payment-method`, PATCH `/client/payment-method/autopay`, POST `/client/booking/{id}/reschedule`, GET `/client/activity/weekly` |
| `app/modules/client_portal/service.py` | **MODIFIED** | New service functions for all 3 features |
| `app/modules/client_portal/schemas.py` | **MODIFIED** | New request/response schemas for all 3 features |
| `app/modules/client_portal/repository.py` | **MODIFIED** | New raw SQL reads: payment-method GET, weekly activity aggregate |
| `app/modules/bookings/service.py` | **MODIFIED** | New `reschedule_booking_for_client` orchestrator |
| `app/modules/bookings/notifications.py` | **MODIFIED** | Add `BOOKING_RESCHEDULED_DM` locked template constant |
| Alembic `0053_booking_notifications_reschedule.py` | **NEW migration** | Widen `ck_booking_notifications_kind` CHECK to include `'rescheduled'` |
| `app/workers/scheduled/charge_expiring_autopay.py` | **NEW worker** | ARQ cron job for autopay charging |
| `app/core/audit.py` `LOCKED_AUDIT_EVENTS` | **MODIFIED** | Pre-register `("booking_rescheduled", "booking")` + payment-method audit events |
| `app/core/audit_payloads.py` | **MODIFIED** | New payload schemas for new audit events |
| `.importlinter` | **MODIFIED** | Add `app.modules.payment_methods` to `modules-independent` contract |
| `apps/client-pwa/` | **MODIFIED** | Flip `linkedCard`/`weeklyActivity` feature flags; wire new endpoint hooks |
| `apps/backend/openapi.json` + `schema.d.ts` | **MODIFIED** | Per-milestone byte-stable regen + `AssertNonNever` forward-guards |

---

## Dependency-Aware Build Order

Dependencies chain as follows:
- `client_payment_methods` table (migration 0052) must exist before webhook token-save and `client_portal` endpoints can reference it.
- `charge_expiring_autopay` cron depends on both the table and the modified `_sell_subject_core` accepting `payment_method_id`.
- `reschedule` depends on the `reschedule_booking_for_client` Protocol slot + migration 0053.
- `weekly_activity` is independent — pure read, no new migrations needed.

### Recommended Phase Order

**Phase 79 — Payment Methods Foundation + YooKassa Adapter**

Scope:
- New `app/modules/payment_methods/` (models + repo + thin service).
- Alembic `0052_client_payment_methods.py`.
- Extend `YooKassaClient.create_payment` with `save_payment_method` param and `payment_method_id` param (for autopay charges).
- Extend `YooKassaPaymentResult` / `types.py` to surface `payment_method.*` fields from webhook payload.
- Modify `_sell_subject_core` to pass `save_payment_method` to YooKassa when requested.
- Modify `handle_payment_succeeded` webhook handler: step 8.5 — raw SQL upsert token.
- New `GET /client/payment-method`, `DELETE /client/payment-method`, `PATCH /client/payment-method/autopay` endpoints in `client_portal`.
- Pre-register new payment-method audit events.
- Tests: checkout with save flag → webhook → token stored; GET returns masked card; unbind sets is_active=false; autopay_enabled toggle.
- **No autopay cron yet** — foundation only.

**Phase 80 — Autopay Cron**

Scope:
- `app/workers/scheduled/charge_expiring_autopay.py` ARQ cron (06:30 MSK).
- Extend `_sell_subject_core` to accept `payment_method_id` param and omit `confirmation` object in the YooKassa body (server-initiated charge path).
- Wire cron in docker-compose / ARQ settings.
- Tests: autopay charge fires for qualifying clients; idempotency key prevents double-charge; failed charge leaves membership to expire normally via existing `expire_memberships` cron.
- **Depends on Phase 79**.

**Phase 81 — Booking Reschedule**

Scope:
- New `reschedule_booking_for_client` Protocol slot in `app.core.dependencies` + wired in `app/main.py`.
- `bookings/service.reschedule_booking_for_client` (atomic move: restore old slot + flip new slot + update booking.slot_id in one UoW).
- Add `BOOKING_RESCHEDULED_DM` locked template constant in `bookings/notifications.py`.
- Alembic `0053_booking_notifications_reschedule.py` (widen `ck_booking_notifications_kind` CHECK).
- Pre-register `("booking_rescheduled", "booking")` in `LOCKED_AUDIT_EVENTS`.
- `POST /client/booking/{id}/reschedule` endpoint in `client_portal/router.py`.
- Frontend: BookingManageSheet wired to real `GET /client/slots` + new reschedule endpoint.
- Tests: successful reschedule (old slot → active, new slot → booked); IDOR (non-owned booking → 404); window-expired (< 24h to start) → 409; race (new slot taken between lookup and flip) → 409 slot_already_booked.
- **Independent from Phases 79–80** in terms of logic; must come after 79 for migration numbering continuity.

**Phase 82 — Weekly Activity + PWA Flag Flips + OpenAPI Handoff**

Scope:
- `GET /client/activity/weekly` endpoint in `client_portal/router.py`.
- Raw SQL weekly aggregate in `client_portal/repository.py` (visits + pt_sessions, 7-day result, zero-fill missing days).
- `WeeklyActivityResponse` + `DayActivity` schemas.
- PWA: flip `weeklyActivity` flag ON, wire `useWeeklyActivity()` hook.
- PWA: flip `linkedCard` flag ON (connects to Phase 79 endpoints).
- Byte-stable `openapi.json` + `schema.d.ts` regen + new `AssertNonNever` forward-guards for all v2.2 paths.
- Milestone verification gate (live `docker compose up` + `pytest` green + drift gates).
- **Depends on all prior phases** (captures all new endpoints for OpenAPI handoff).

---

## Architecture Constraints Checklist (v2.2 specific)

| Constraint | How Respected |
|---|---|
| `import-linter` modules independent | `payment_methods` added to independence contract; `client_portal` uses Protocol slots or raw SQL only; webhook uses raw SQL for token save — zero new `ignore_imports` needed for features B and C |
| `core ⊥ modules` | New Protocol slots registered in `app.core.dependencies`; wired in composition root `main.py` |
| Webhook-locked activation | Autopay: `payment_method_id` charge produces `payment.succeeded` → normal 8-step UoW activates membership; redirect screen invariant unchanged |
| IDOR anti-oracle | All `client_portal` endpoints: `client_id` from `require_client()` only; non-owned resources → 404-collapse |
| SVC001 commit-gate | `reschedule_booking_for_client` commits own UoW; `client_portal/router` calls `await session.commit()` for PATCH/DELETE payment-method endpoints |
| INFRA-15 (audit events pre-registered) | `booking_rescheduled`, new payment-method events pre-registered in frozenset BEFORE any callsite |
| Server-authoritative pricing (D-06) | Autopay: plan price read from `membership_plans.price_kopecks` via `_read_membership_plan_or_raise` inside `_sell_subject_core` — no price from caller |
| Staff contract frozen | All new endpoints additive under `Client-Portal` tag; zero changes to staff paths; byte-parity drift guard remains green |
| 54-ФЗ receipt on autopay | Autopay `_sell_subject_core` still builds `receipt_items` from plan name/price; `customer_phone` fallback always applies (phone is NOT NULL via OTP auth) |
| D-69-03 empty states | GET payment-method returns 200/null (no method); GET weekly activity returns 200 with 7 zero-workout days |

---

## Open Questions for Phase Planning

1. **Autopay notification on failure**: should `payment.canceled` from an autopay charge trigger a Telegram/email DM to the client? Not strictly required for v2.2, but affects test coverage scope.
2. **`save_payment_method` in checkout body vs. always-save**: should the PWA always request method saving when the client checks a UI checkbox (conditional save), or should v2.2 always save when the client completes checkout (unconditional)? Affects whether `ClientCheckoutRequest` schema needs a new boolean field.
3. **Autopay renewal strategy**: when autopay fires, should it use `renew_membership` (creating a new membership row) or `sell_membership` (creating a new sale from scratch)? Given the existing `renew_membership` Protocol slot in memberships module, the autopay cron should probably call `renew_membership` after the webhook confirms payment, not `sell_membership` + activation. This is the cleaner domain model but requires the webhook handler to distinguish "autopay-initiated renewal" from "fresh purchase". Decision affects audit event shape.
4. **Weekly activity scope**: does "current week" mean the 7 days Mon–Sun of the current ISO week, or the last 7 rolling days? ISO week (Mon–Sun) is the recommended default but confirm with user.

---

## Sources

- Live codebase inspection: `apps/backend/app/modules/client_portal/`, `bookings/service.py`, `online_payments/service.py`, `online_payments/models.py`, `visits/models.py`, `pt_sessions/models.py`, `app/integrations/yookassa/client.py`, `app/integrations/yookassa/types.py`, `apps/backend/.importlinter`, `apps/backend/alembic/versions/` (migrations 0001–0051).
- YooKassa saved payment methods: [Привязка во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment) (MEDIUM confidence — page returns structure, full field schema requires sandbox testing).
- YooKassa autopayments: [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) (HIGH confidence — `payment_method_id` param + no-user-confirmation pattern confirmed).
- YooKassa unbind: no DELETE API endpoint per [YooKassa API reference](https://yookassa.ru/developers/api) — unbind = remove from local storage only (HIGH confidence).
- Project architecture decisions: `.planning/PROJECT.md` (v2.0–v2.1 Current State section).

---
*Architecture research for: clubcore v2.2 — Membership self-service depth*
*Researched: 2026-06-03*
