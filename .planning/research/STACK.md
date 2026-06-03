# Stack Research

**Domain:** Gym CRM — client self-service depth (v2.2: card-on-file + autopay, booking reschedule, weekly-activity analytics)
**Researched:** 2026-06-03
**Confidence:** HIGH for YooKassa saved-method flow; HIGH for reschedule (pure reuse); HIGH for weekly-activity (pure SQL)

---

## Executive Summary

v2.2 adds three features on top of a full-stack already shipped. The vast majority of stack work is **reuse** of existing patterns with no new dependencies. The one genuinely new area is YooKassa saved payment methods — and even that slots into the existing `app/integrations/yookassa/client.py` adapter pattern rather than requiring a new SDK or library.

---

## Feature (a): YooKassa Saved Payment Methods + Autopay

### What is new vs. existing

**Existing (do not re-implement):**
- `app/integrations/yookassa/client.py` — `YooKassaClient` with httpx async adapter: `create_payment`, `get_payment`, `create_refund`, `get_refund`, `create_receipt`. The adapter is raw httpx, not the synchronous official `yookassa` SDK (which was explicitly wrapped out of the event loop at v1.7). The adapter pattern, boundary types, and classification taxonomy are all stable.
- `app/integrations/yookassa/types.py` — `YooKassaPaymentResult`, `YooKassaWebhookEvent`, etc.
- `app/modules/online_payments/` — one-off checkout flow, `payment.succeeded` / `payment.canceled` webhook FSM, 54-ФЗ receipts, IP-allowlist verification, Redis dedup.
- `app/modules/client_portal/` — `require_client()`, `ClientPrincipal`, IDOR-safe raw-SQL reads, D-20-MODULE Protocol-slot write discipline.

**What is genuinely new for v2.2:**

#### 1. YooKassa API calls not yet in the client

The existing `YooKassaClient` covers `POST /v3/payments`, `GET /v3/payments/{id}`, `POST /v3/refunds`, `GET /v3/refunds/{id}`, `POST /v3/receipts`. For saved-method flow, two additional operations are needed — both as new methods on the existing adapter class:

| New method | YooKassa endpoint | When used |
|---|---|---|
| `create_payment_with_save` | `POST /v3/payments` (same endpoint, but adds `save_payment_method: true` in body) | First payment to bind a card |
| `create_autopayment` | `POST /v3/payments` (same endpoint, but passes `payment_method_id` instead of `confirmation`) | Autopay charge using saved token |

Both are POST `/v3/payments` — the same endpoint as `create_payment`. The difference is in the request body fields, not the endpoint URL. Options:
- **Option A (recommended):** Extend `create_payment` with new optional parameters (`save_payment_method: bool = False`, `payment_method_id: str | None = None`). This keeps the adapter surface minimal. Autopayments set `payment_method_id` and omit `confirmation` entirely (no redirect needed — user-less flow).
- **Option B:** Add two new methods `create_payment_save_method` and `create_autopayment`. More explicit but duplicates transport logic.

Option A is preferred because both flows return `YooKassaPaymentResult` and share the same classification taxonomy and error handling already implemented.

#### 2. GET /v3/payment_methods/{id} — new endpoint

To read a saved payment method (card last 4, expiry, type) for displaying «•••• 4821» in the PWA, the adapter needs:

```python
async def get_payment_method(self, payment_method_id: str) -> YooKassaPaymentMethodResult
```

- **Endpoint:** `GET /v3/payment_methods/{payment_method_id}`
- **Response structure (verified):**
  ```json
  {
    "id": "pm_xxx",
    "type": "bank_card",
    "saved": true,
    "status": "active",
    "card": {
      "first6": "427631",
      "last4": "4821",
      "expiry_month": "09",
      "expiry_year": "2028",
      "card_type": "Visa",
      "issuer_name": "Sberbank"
    },
    "title": "Bank card *4821"
  }
  ```
- A new frozen dataclass `YooKassaPaymentMethodResult` is needed in `types.py` with fields: `ok`, `classification`, `payment_method_id`, `saved`, `status` (`"pending" | "active" | "inactive"`), `card_last4`, `card_expiry_month`, `card_expiry_year`, `card_type`, `title`.

#### 3. New webhook event type

The existing `YooKassaWebhookEvent.event` literal is:
```python
event: Literal["payment.succeeded", "payment.canceled", "refund.succeeded"]
```

For zero-amount binding, the `payment_method.active` webhook fires after binding completes. For autopay triggered via `POST /v3/payments` with `payment_method_id`, the standard `payment.succeeded` webhook fires — no new event type needed for autopay itself.

**Decision:** Add `"payment_method.active"` to the Literal union only if zero-amount binding flow is used. If v2.2 uses binding-during-payment only (save on first real checkout), the existing `payment.succeeded` handler already carries `payment_method.saved == true` and `payment_method.id` in the response body — no new webhook event needed.

**Recommended binding strategy for v2.2:** Use "save during payment" (binding-during-real-purchase). The client makes a real first checkout with `save_payment_method: true`. On `payment.succeeded` webhook, the `payment_method.id` and card last4 come back in the payment object's `payment_method` sub-object and are stored server-side. This avoids zero-amount binding entirely and the `payment_method.active` event.

#### 4. New server-side storage

A new table (or column on `clients`) to store the saved payment method:

```
client_saved_payment_methods (proposed new table)
  id UUID PK
  client_id UUID FK clients.id ON DELETE CASCADE
  yookassa_payment_method_id TEXT NOT NULL UNIQUE  -- the token
  card_last4 TEXT NOT NULL
  card_expiry_month TEXT NOT NULL
  card_expiry_year TEXT NOT NULL
  card_type TEXT  -- "Visa", "Mastercard", etc.
  title TEXT  -- "Bank card *4821" from YooKassa
  autopay_enabled BOOLEAN NOT NULL DEFAULT false
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now()
  unlinked_at TIMESTAMPTZ  -- soft-delete; NULL = active
  created_at TIMESTAMPTZ (TimestampMixin)
  updated_at TIMESTAMPTZ (TimestampMixin)
  UNIQUE (client_id) WHERE unlinked_at IS NULL  -- one active card per client
```

Alembic migration would be `0052_client_saved_payment_methods.py`.

**"Unbind" semantics (verified from YooKassa docs):** YooKassa does NOT provide a DELETE endpoint for payment methods. "Unbinding" is entirely server-side — set `unlinked_at = now()` on the row. The `yookassa_payment_method_id` token is simply no longer used for future charges. No API call to YooKassa on unbind.

#### 5. New client_portal endpoints

Under `app/modules/client_portal/`:

| Endpoint | Method | Description |
|---|---|---|
| `/client/payment-method` | `GET` | Return linked card (last4, expiry, type, autopay flag) or null |
| `/client/payment-method` | `DELETE` | Soft-unbind (set unlinked_at); no YooKassa API call |
| `/client/payment-method/autopay` | `PATCH` | Toggle `autopay_enabled` |

These follow the existing `require_client()` + IDOR-safe discipline. Write endpoints add `verify_client_csrf`. No `Idempotency-Key` required for unbind/toggle (state is idempotent at DB level via UNIQUE partial index).

#### 6. Webhook handler extension

The existing `handle_payment_succeeded` handler in `online_payments` (triggered by `POST /_internal/yookassa/webhook`) needs to be extended: when `payment_method.saved == true` in the payment object fetched from YooKassa, extract `payment_method.id` + card details and write the `client_saved_payment_methods` row. This happens in the same atomic UoW as the existing 8-step succeeded handler — add it as step 9.

**Invariant preserved:** Activation is still LOCKED to the webhook path. The anti-oracle return screen discipline (D-06) is not affected — the card binding happens server-side, not on redirect.

#### 7. Production gating requirement

YooKassa **requires manager activation** before saved payment methods work in production (confirmed in docs). In sandbox it works by default. This is an operator task, not a code task, but it must be noted in the milestone requirements. The flag `linkedCard` in the PWA stays OFF until the operator confirms the feature is enabled in the YooKassa dashboard.

#### 8. No new Python library

The existing httpx-based `YooKassaClient` handles all new calls. The synchronous official `yookassa` Python SDK was deliberately excluded at v1.7 (D-47 / CLAUDE.md constraints). Do not introduce `yookassa` SDK. Do not introduce `aioyookassa` or any community async wrapper.

---

## Feature (b): Booking Reschedule

### What is genuinely new vs. reuse

**Reuse (no new code needed in these areas):**
- `app/modules/bookings/service.py` — existing `cancel_booking_for_client` and `create_booking_for_client` functions. Reschedule is cancel + re-book under a single transaction.
- `app/modules/schedule/` — available-slots queries already exist.
- `app/modules/client_portal/service.py` + `router.py` — existing `cancel_client_booking` and `create_booking_for_client_request` Protocol-slot delegates. Reschedule reuses these delegates.
- Client CSRF, idempotency, IDOR checks — all inherited from existing patterns.

**What is genuinely new:**

#### 1. Single new endpoint

```
POST /client/booking/{booking_id}/reschedule
Body: { "new_slot_id": UUID }
```

This is a compound operation: cancel the existing booking + create a new one on the new slot, atomically, within the same DB transaction. The existing `cancel_booking_for_client` and `create_booking_for_client` are already composable within a single session.

#### 2. Cancel-window enforcement for reschedule

Reschedule has the same cancel-window guard as cancel. This is already enforced inside `cancel_booking_for_client` — no new logic needed.

#### 3. Slot restore during cancel

The existing `cancel_booking_for_client` calls `restore_booking_slot` (Protocol slot that flips `trainer_availability_slots.status` from `booked` back to `active`). This runs automatically as part of the cancel step.

#### 4. Audit events

Two audit events fire: `booking_cancelled` + `booking_created`. These are already registered in `LOCKED_AUDIT_EVENTS`. No new audit events needed for reschedule.

#### 5. No new notifications needed for v2.2

The existing booking lifecycle notifications (`BOOKING_CANCELLED_BY_CLIENT_DM`, `BOOKING_CONFIRMED_DM`) fire as part of cancel and create respectively. No new template needed for v2.2 (a "reschedule" notification template could be added in a later milestone as a UX improvement).

**Conclusion:** Reschedule is entirely reuse of existing patterns. The only new surface is the endpoint route in `client_portal/router.py` plus a thin service function `reschedule_client_booking` that orchestrates the cancel+create sequence.

---

## Feature (c): Weekly-Activity Aggregation

### What is genuinely new vs. reuse

**Reuse:**
- `app/modules/visits` — `visits` table with `gym_date` STORED GENERATED column (already Europe/Moscow). `client_id` FK allows per-client filter.
- `app/modules/pt_sessions` — `pt_sessions` table with `performed_at` TIMESTAMPTZ + `client_id` FK. No `duration_minutes` column exists on pt_sessions (confirmed by reading the ORM directly).
- `app/modules/schedule` — `trainer_availability_slots` has `start_time` + `end_time` (both TIMESTAMPTZ). Slot duration = `EXTRACT(EPOCH FROM (end_time - start_time)) / 60` in minutes. `pt_sessions.booking_id` → `bookings.slot_id` → slot start/end times.
- `app/modules/client_portal/repository.py` — raw-SQL `text()` cross-module reads already established by D-20-MODULE.
- `app/modules/reports/` — weekly/daily SQL aggregate patterns already exist in `visits` report.

**What is genuinely new:**

#### 1. New endpoint

```
GET /client/activity/weekly
Response: { days: [ { date: "2026-06-03", workouts: 1, minutes: 60 }, ... ] }
```

Always returns exactly 7 entries (rolling last 7 days in Europe/Moscow). If a day has no activity, `workouts: 0, minutes: 0`.

#### 2. Minutes calculation

Visit rows (reception/QR check-in) do NOT have a duration — they are a check-in timestamp only. PT sessions have `performed_at` but no `duration_minutes` column. Options:
- **Option A:** Count visits as a fixed `VISIT_DURATION_MINUTES = 60` constant (configurable per environment). This is defensible: a membership check-in represents one gym session, duration approximated.
- **Option B:** Join PT sessions via `pt_sessions.booking_id → bookings.slot_id → slots.end_time - slots.start_time`. Only works for PT sessions with a booking; walk-in PT sessions and standard visits have no slot link.

**Recommended:** Aggregate separately — PT sessions get slot-derived minutes (via `booking_id → slot` join, fallback to constant when `booking_id IS NULL`), gym visits get a server-configured constant (e.g. `60` minutes). Sum both per day.

SQL pattern (raw `text()`, follows D-20-MODULE raw-SQL cross-module discipline):

```sql
-- Gym visits: fixed duration constant
SELECT
  v.gym_date AS activity_date,
  COUNT(*) AS workout_count,
  COUNT(*) * :visit_minutes AS total_minutes
FROM visits v
WHERE v.client_id = :client_id
  AND v.gym_date >= :week_start
  AND v.gym_date <= :week_end
GROUP BY v.gym_date

UNION ALL

-- PT sessions: slot-derived duration (booking_id -> slot), fallback to constant
SELECT
  (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date AS activity_date,
  COUNT(*) AS workout_count,
  COALESCE(SUM(
    CASE
      WHEN s.id IS NOT NULL
        THEN EXTRACT(EPOCH FROM (s.end_time - s.start_time)) / 60
      ELSE :pt_session_fallback_minutes
    END
  ), 0)::int AS total_minutes
FROM pt_sessions ps
LEFT JOIN bookings b ON b.id = ps.booking_id
LEFT JOIN trainer_availability_slots s ON s.id = b.slot_id
WHERE ps.client_id = :client_id
  AND ps.cancelled_at IS NULL
  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date >= :week_start
  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date <= :week_end
GROUP BY activity_date
```

Then merge by date in Python and fill zeros for days without activity.

#### 3. No new migration needed

`visits`, `pt_sessions`, `bookings`, `trainer_availability_slots` are all existing tables with adequate columns. The query reads from existing indexes: `ix_visits_client_id_checked_in_at` (efficient for client_id filter on 7-day window), `ix_pt_sessions_pt_package_id_performed_at_desc` (suboptimal — not indexed on client_id — but the 7-day window is always small enough that a table scan on the client's own rows is acceptable).

An optional minor improvement: add `ix_pt_sessions_client_id_performed_at` index in migration 0052 or a dedicated `0053`. This is very unlikely to matter for 7 days of data for one client.

---

## Stack Change Summary Table

| Area | Change Type | What Changes | New Dependency? |
|---|---|---|---|
| `app/integrations/yookassa/types.py` | **New dataclass** | Add `YooKassaPaymentMethodResult` frozen dataclass | No |
| `app/integrations/yookassa/client.py` | **Extend** | Add `get_payment_method(...)` method; extend `create_payment(...)` with `save_payment_method: bool` + `payment_method_id: str | None` params | No |
| `alembic/versions/0052_*` | **New migration** | `client_saved_payment_methods` table | No |
| `app/modules/client_portal/` | **Extend** | New ORM class, 4 new endpoints, 3 new service functions, new schemas, repository queries | No |
| `app/modules/online_payments/service.py` | **Extend** | Step 9 in `handle_payment_succeeded`: persist `payment_method` data when `saved == true` | No |
| `apps/client-pwa` | **Extend** | Wire `CardSheet` to real endpoints; wire `weeklyActivity` to `GET /client/activity/weekly`; wire `BookingManageSheet` reschedule to `POST /client/booking/{id}/reschedule` | No |
| `openapi.json` + `schema.d.ts` | **Regen** | New paths added; drift gate runs | No |

---

## Core Technologies (unchanged — all reuse)

| Technology | Version (existing) | Purpose | Why Still Correct |
|---|---|---|---|
| FastAPI | 0.115+ | API framework | No change |
| SQLAlchemy 2.0 async | 2.0 | ORM + raw SQL | No change |
| Alembic async | current | Migrations | One new migration `0052` |
| Pydantic v2 | v2 | Schemas | New frozen dataclasses + response models |
| httpx | current | YooKassa HTTP client | Extend existing `YooKassaClient` |
| Postgres 16 | 16 | RDBMS | One new table |
| Redis 7 | 7 | Session / dedup | No change |
| ARQ | current | Background tasks | No new tasks for v2.2 |
| structlog | current | Logging | No change |
| Python 3.12 + uv | 3.12 | Runtime | No change |
| React 18 + react-router v6 | as-is | Client PWA | Flag flips + query wiring |
| `@clubcore/api-client` | current | Typed API client | New paths added via openapi regen |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|---|---|---|
| `yookassa` Python SDK | Synchronous SDK was deliberately wrapped out of event loop at v1.7; not async-safe | Existing httpx `YooKassaClient` |
| `aioyookassa` community lib | Unvetted; the existing adapter already handles the two new endpoints cleanly | Extend `YooKassaClient.get_payment_method` + `create_payment` params |
| Zero-amount binding flow | Requires `payment_method.active` webhook handler, extra infrastructure, and separate UX flow. Binding during first real payment reuses the existing `payment.succeeded` webhook path exactly. | `save_payment_method: true` on first real checkout |
| Separate autopay-charges ARQ cron | v2.2 goal is card-on-file display + toggle; actual recurring auto-charges are a separate scope boundary | v2.2 stores token + toggle flag only; autopay execution deferred to v2.3 or later |
| New report module for activity | activity endpoint belongs in `client_portal/` not `reports/` (it is per-client scoped data, not owner aggregate) | Extend `client_portal/repository.py` with raw-SQL |
| New `duration_minutes` column on `pt_sessions` | Not needed — slot start/end times are available via `booking_id` join; migration cost exceeds benefit for this feature | SQL `EXTRACT(EPOCH FROM (end_time - start_time)) / 60` join |

---

## YooKassa API Reference (verified 2026-06-03)

### Binding during payment (recommended strategy for v2.2)

Request extension to existing `POST /v3/payments`:
```json
{
  "amount": { "value": "2500.00", "currency": "RUB" },
  "capture": true,
  "save_payment_method": true,
  "confirmation": { "type": "redirect", "return_url": "..." },
  "receipt": { "..." },
  "description": "..."
}
```

On `payment.succeeded` webhook, re-fetch `GET /v3/payments/{id}` (existing discipline — already done). The re-fetched payment object includes:
```json
{
  "payment_method": {
    "id": "pm_xxxxxx",
    "type": "bank_card",
    "saved": true,
    "card": {
      "first6": "427631",
      "last4": "4821",
      "expiry_month": "09",
      "expiry_year": "2028",
      "card_type": "Visa",
      "issuer_name": "Sberbank"
    }
  }
}
```

Store `payment_method.id`, `card.last4`, `card.expiry_month`, `card.expiry_year`, `card.type` in `client_saved_payment_methods`.

### Autopayment request (when auto-charge is triggered in future milestones)

Same `POST /v3/payments` endpoint, different body — `payment_method_id` replaces `confirmation`:
```json
{
  "amount": { "value": "2500.00", "currency": "RUB" },
  "capture": true,
  "payment_method_id": "pm_xxxxxx",
  "description": "...",
  "receipt": { "..." }
}
```

No `confirmation` object needed — no user interaction. Fires standard `payment.succeeded` webhook. Existing webhook handler processes it normally.

### GET /v3/payment_methods/{id}

Read a saved payment method. Useful for `GET /client/payment-method` as a freshness check or when local table data is stale. Returns the `status: "active" | "inactive"` field.

### Webhook event set — no changes needed for v2.2

| Event | When | Status for v2.2 |
|---|---|---|
| `payment.succeeded` | Payment confirmed (including first save-during-payment) | Already handled — extend to extract `payment_method` sub-object when `saved == true` |
| `payment.canceled` | Payment canceled | Already handled |
| `refund.succeeded` | Refund processed | Already handled |
| `payment_method.active` | Zero-amount binding only | Not needed for v2.2 |

The existing `YooKassaWebhookEvent.event` Literal does not need `payment_method.active` for v2.2 if save-during-payment strategy is used.

### Production activation (operator prerequisite)

"Autopayments work only in test shop by default. Contact your YooKassa manager to enable saved payment methods for bank cards, SberPay, T-Pay, СБП and YooMoney wallet." This is an operator-side task. The `linkedCard` PWA flag should stay OFF until the operator confirms the feature is live in the YooKassa dashboard.

---

## Confidence Assessment

| Area | Confidence | Basis |
|---|---|---|
| YooKassa `save_payment_method` field and `payment_method` sub-object in payment response | HIGH | Official yookassa.ru developer docs, multiple pages cross-checked |
| `payment_method_id` request field for autopayments, no `confirmation` needed | HIGH | Official docs on autopayments with saved method |
| No DELETE endpoint for payment methods on YooKassa side | HIGH | Official docs explicitly state this: "YooMoney cannot delete a saved payment method — only on your side" |
| `payment_method.active` webhook only fires for zero-amount binding | HIGH | Official webhooks documentation |
| Reschedule is pure cancel+create reuse with no new infrastructure | HIGH | Codebase read of `cancel_booking_for_client` + `create_booking_for_client` — composable within a single session |
| No `duration_minutes` column on `pt_sessions` | HIGH | Direct ORM read of `app/modules/pt_sessions/models.py` |
| Slot duration derivable from `start_time`/`end_time` | HIGH | Direct ORM read of `app/modules/schedule/models.py` |
| Production YooKassa manager-activation requirement | HIGH | Official docs on autopayment basics |
| Last Alembic migration is 0051, next is 0052 | HIGH | Direct directory listing of `alembic/versions/` |

---

## Sources

- [YooKassa: Binding during payment](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment) — `save_payment_method`, payment_method response fields
- [YooKassa: Autopayments with saved method](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) — `payment_method_id` request field, no confirmation object
- [YooKassa: Autopayment basics](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics) — production manager-activation requirement
- [YooKassa: Zero-amount binding](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment) — `POST /v3/payment_methods`, `payment_method.active` event, status field values
- [YooKassa: Webhooks](https://yookassa.ru/developers/using-api/webhooks) — full event list including `payment_method.active`
- Codebase: `/apps/backend/app/integrations/yookassa/client.py` — confirmed raw httpx adapter, no SDK
- Codebase: `/apps/backend/app/integrations/yookassa/types.py` — existing boundary types, `YooKassaWebhookEvent.event` Literal
- Codebase: `/apps/backend/app/modules/online_payments/models.py` — `OnlinePayment` ORM, no saved-method columns
- Codebase: `/apps/backend/app/modules/bookings/service.py` — `cancel_booking_for_client`, `create_booking_for_client` confirmed composable
- Codebase: `/apps/backend/app/modules/schedule/models.py` — `start_time`/`end_time` TIMESTAMPTZ confirmed on `trainer_availability_slots`
- Codebase: `/apps/backend/app/modules/pt_sessions/models.py` — no `duration_minutes` column confirmed
- Codebase: `/apps/backend/alembic/versions/` — last migration is `0051_seed_fit15_promo.py`
- Codebase: `/apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — CardSheet mock confirmed, `linkedCard`/`weeklyActivity` flag locations

---
*Stack research for: clubcore v2.2 Membership self-service depth*
*Researched: 2026-06-03*
