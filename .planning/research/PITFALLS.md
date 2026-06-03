# Pitfalls Research

**Domain:** Saved-card autopay + booking reschedule + weekly-activity analytics — v2.2 additions to an existing secure payment system (clubcore gym CRM)
**Researched:** 2026-06-03
**Confidence:** HIGH (YooKassa official docs + codebase analysis + PostgreSQL docs)

---

## Critical Pitfalls

### Pitfall 1: Storing raw card data instead of only the YooKassa `payment_method.id` token

**What goes wrong:**
Any attempt to store PANs, CVVs, or even masked card numbers in the clubcore database instead of (or in addition to) the YooKassa `payment_method.id` opaque token immediately scopes the application into PCI DSS SAQ-D, requiring quarterly audits, network segmentation, and a full assessor engagement — none of which this project has or intends to build.

**Why it happens:**
Developers want to show the user "•••• 4821" in the UI. They fetch the last4 and brand from YooKassa's payment response and store them in a DB column alongside the token. The last4 and brand are technically non-sensitive, but the discipline is easy to violate: a future developer may add expiry month/year, then the full PAN "just for debugging." PCI scope creep starts with one column.

**How to avoid:**
- Store ONLY `payment_method.id` (the opaque YooKassa token) in a dedicated `client_payment_methods` table alongside display metadata (`card_last4`, `card_brand`, `card_exp_month`, `card_exp_year`) that you receive ONCE from the YooKassa payment response and never update.
- Never accept card numbers, CVVs, or expiry dates from the PWA or backend request bodies. The PWA widget handles tokenization entirely on the YooKassa side.
- Add a DB-level check or service-layer assertion: the token column is the only thing your code ever sends to YooKassa for recurring charges.
- `card_last4` and `card_brand` are acceptable for display — they are not cardholder data under PCI. Expiry is borderline; omit it from DB if not needed for display.

**Warning signs:**
- Any migration adding `card_number`, `pan`, `cvv`, `cvc`, or `card_number_encrypted` columns.
- Any endpoint accepting card numbers from the client (PWA body or header).
- Logs containing 16-digit sequences.

**Phase to address:**
Phase 79 (card-on-file backend schema). The migration for `client_payment_methods` must contain ONLY `yookassa_payment_method_id`, `card_last4`, `card_brand`, and display metadata — enforced by code review on the migration file itself before any other phase proceeds.

---

### Pitfall 2: Activating membership on client-reported payment success, not on `payment.succeeded` webhook

**What goes wrong:**
If the autopay charge flow returns a `succeeded` status from the YooKassa API call synchronously and the service immediately activates the renewal membership, a future case where the charge is async (e.g., card issuer two-step capture) will cause a premature activation — the membership goes active before money is received.

**Why it happens:**
The existing v2.0/v2.1 checkout already has the webhook-activation invariant (anti-oracle return screen). Autopay is different because it is server-initiated (no redirect, no user confirmation step), so the developer may assume the synchronous API response is trustworthy and skip the webhook path.

**How to avoid:**
- Apply exactly the same activation discipline as the existing `online_payments` module: `create_payment` with `payment_method_id` → store a pending `online_payments` row → wait for `payment.succeeded` webhook → activate renewal in the webhook handler.
- Never transition a membership to `active` (or create a new renewal membership row) inside the autopay service function that calls YooKassa. Only the webhook handler may do this.
- The autopay task (ARQ worker) is responsible only for creating the payment and recording the pending row. Webhook does the rest.

**Warning signs:**
- Any call to `activate_membership` or creation of a new `Membership` row in the same function that calls `yookassa_client.create_payment(payment_method_id=...)`.
- An autopay ARQ task that calls `await session.commit()` after `create_payment` returns `ok`.

**Phase to address:**
Phase 79 (autopay backend). The ARQ task for scheduled autopay must be designed with a stub: "create payment → store pending row → return; webhook does the rest."

---

### Pitfall 3: Double-charge race on membership renewal autopay

**What goes wrong:**
Two concurrent ARQ task invocations (e.g., cron fires twice due to retry, or a duplicate task is enqueued) both reach `yookassa_client.create_payment(payment_method_id=...)` with different idempotency keys. YooKassa treats them as two distinct charges. The client gets charged twice; membership is activated twice (two rows) or in a broken state.

**Why it happens:**
The existing autopay cron will likely use ARQ `unique=True` to prevent duplicate task scheduling, but if the task is long-running or the worker restarts mid-run, ARQ may enqueue a second copy. Additionally, if the webhook-activation handler is not idempotent, a webhook replay causes a second activation even with a single charge.

**How to avoid:**
- Use a **deterministic idempotency key** for autopay charges, derived from `(client_id, membership_id, renewal_date)` — same pattern as the existing per-day sha256 key for regular checkout (D-71-04). This makes the YooKassa call idempotent regardless of how many times the ARQ task runs.
- The pending `online_payments` row creation must be guarded by a DB UNIQUE constraint on `(client_id, subject_id, idempotency_key)` or on the deterministic key itself, so a duplicate insertion raises an `IntegrityError` that the task handles as "already enqueued, skip."
- The webhook handler must use the existing Redis `cc:yookassa:webhook:` dedup + always re-fetch pattern already in `online_payments/service.py`.
- ARQ task must use `unique=True` keyed to `(client_id, membership_id, renewal_period)`.

**Warning signs:**
- Autopay task generates a random UUID as the idempotency key at runtime (non-deterministic).
- No DB UNIQUE constraint on the pending payment row for autopay.
- Duplicate `payment.succeeded` webhooks triggering duplicate activations (test this explicitly).

**Phase to address:**
Phase 79 (autopay backend). The idempotency key derivation function must be specified in the phase plan before any code is written.

---

### Pitfall 4: No `payment_method.saved` verification before storing the token

**What goes wrong:**
After a regular checkout with `save_payment_method: true`, the developer reads `payment_method.id` from the synchronous `create_payment` response and stores it immediately. But the YooKassa API docs state: verify that `payment_method.saved` is `true` AFTER the payment succeeds. If `saved` is `false` (card issuer declined to tokenize), the stored `payment_method_id` is invalid and autopay charges will fail with `permanent_error`.

**Why it happens:**
The field is available in the `create_payment` response, so it looks safe to read immediately. However, `saved` reflects the actual tokenization outcome, which is only confirmed once the payment transitions to `succeeded`.

**How to avoid:**
- In the `payment.succeeded` webhook handler, check `payment_method.saved == true` before inserting a row into `client_payment_methods`.
- If `saved` is `false`, record the checkout as succeeded (money received) but do NOT create a `client_payment_methods` row. Notify the client that card saving failed separately (or silently — autopay UI flag stays `OFF`).
- Never read `payment_method.id` from the synchronous `create_payment` response for storage purposes. Only trust the data in the verified webhook callback.

**Warning signs:**
- `client_payment_methods` INSERT happens inside the `create_payment` call path, not in the webhook handler.
- No check for `payment_method.saved` field in the webhook processing code.

**Phase to address:**
Phase 79 (card-on-file save flow, webhook handler extension).

---

### Pitfall 5: No API endpoint for unbinding a card on YooKassa side — "unbind" is local-only

**What goes wrong:**
YooKassa has NO `DELETE /v3/payment_methods/{id}` API endpoint. Unbinding a card means the merchant stops using the `payment_method_id` — YooKassa cannot be notified. If the developer tries to call a non-existent deletion endpoint, they get a `permanent_error`. If they expose a "remove card" UI and the backend incorrectly tries to make a YooKassa API call to delete the method, it silently fails or errors.

**Why it happens:**
Most payment gateways (Stripe, Braintree) have a `detach` API for saved payment methods. YooKassa does not. This is a YooKassa-specific constraint that is easy to miss.

**How to avoid:**
- Unbinding = soft-delete the `client_payment_methods` row in your DB (set `unbound_at = now()`). That is the complete operation.
- Autopay toggle = flip a boolean column `autopay_enabled` on the row (or on the client record). No YooKassa API call needed.
- On the `DELETE /client/payment-method` endpoint: no YooKassa API call, just a DB soft-delete + disable autopay flag. Return 200 immediately.
- Document this constraint in the endpoint handler docstring to prevent future developers from adding a YooKassa call.

**Warning signs:**
- Any call to `yookassa_client.*` inside the payment method unbind handler.
- A `YooKassaClient.delete_payment_method` method being added to `app/integrations/yookassa/client.py`.

**Phase to address:**
Phase 79 (card-on-file backend, unbind endpoint).

---

### Pitfall 6: Autopay-on-renewal failure leaving membership in a lapse gap

**What goes wrong:**
Card is declined or expired at renewal time. The autopay charge fails (`payment.canceled` webhook with `cancellation_reason = 'card_expired'` or `insufficient_funds`). The membership expires and the client cannot use the gym, but they receive no clear notification and the UI still shows "автоплатёж включён" because no state transition was triggered.

**Why it happens:**
The happy path (succeeded) is implemented; the failure path (canceled webhook for an autopay charge) updates the `online_payments` row status but no code transitions the autopay state or notifies the client.

**How to avoid:**
- The `payment.canceled` webhook handler must check if the payment was an autopay attempt (via a `metadata.autopay_renewal = true` tag on the payment creation request).
- On autopay cancellation: disable autopay (`autopay_enabled = false`) on the `client_payment_methods` row and emit a Telegram + email notification to the client ("автоплатёж не удался, карта отклонена — обновите данные или продлите вручную").
- Add a `cancellation_reason` field pass-through into `online_payments.cancellation_details` (already exists in the v1.7 schema via `payment.canceled` handler — verify it captures `cancellation_party` and `reason`).
- Consider a retry with backoff (e.g., retry once after 24h for `insufficient_funds`), but NOT for `card_expired` (retrying an expired card is pointless and consumes the idempotency window).

**Warning signs:**
- The `payment.canceled` handler for the autopay case does not update `client_payment_methods`.
- No test for the "autopay fails → membership lapses → client notified" path.

**Phase to address:**
Phase 79 (autopay backend, failure path). Must be spec'd before implementation — failure paths are often deferred to "later" and then forgotten.

---

### Pitfall 7: IDOR oracle from the "card exists vs not" state on `GET /client/payment-method`

**What goes wrong:**
`GET /client/payment-method` returns `404` if no card is saved and `200` with card data if one is. A client who probes another client's `payment_method_id` (guessed UUID) receives differential responses — `404` for their own non-existent card vs. a possible `200` for another client's card if the IDOR guard is missing, leaking the existence of another client's payment method.

**Why it happens:**
The endpoint returns the card for the authenticated client, filtered by `client_id`. The IDOR risk is that the handler might accept a `?client_id=` query param or accept the `payment_method_id` as a path param that could be guessed, leaking existence.

**How to avoid:**
- Follow the D-20-IDOR pattern exactly: `client_id` comes ONLY from `require_client()` principal. No `client_id` in path, query, or body.
- The endpoint is `GET /client/payment-method` (not `/client/payment-methods/{id}`): returns the single card for the current client, or `200` with `null` (not `404`) if none exists — same D-69-03 empty-state discipline as `GET /client/membership`.
- `assert_owns()` logic: repository always filters `WHERE client_id = :client_id AND unbound_at IS NULL`.
- Never leak "no card saved" as a `404` — always return `200 null`.

**Warning signs:**
- The endpoint has a `payment_method_id` path parameter.
- The endpoint returns `404` when no card is saved (vs. `200 null`).
- Any `?client_id=` query param on the endpoint.

**Phase to address:**
Phase 79 (card-on-file GET endpoint, IDOR review).

---

### Pitfall 8: Unbinding a card while an autopay charge is in-flight

**What goes wrong:**
Client clicks "отвязать карту" at 00:01 on the day their membership expires. At 00:05 the autopay cron fires. The unbind handler soft-deletes the `client_payment_methods` row and sets `autopay_enabled = false`. The autopay task, already past the "is autopay enabled?" gate (it read `autopay_enabled = true` before the unbind committed), calls `yookassa_client.create_payment(payment_method_id=...)`. YooKassa accepts the charge (the token is still valid on their side — unbind is local-only). The client is charged despite clicking "remove card."

**Why it happens:**
Race between the unbind handler (web request) and the autopay cron task (background worker). No synchronization between them.

**How to avoid:**
- Use `SELECT FOR UPDATE` on the `client_payment_methods` row inside the autopay task before using the token. If `unbound_at IS NOT NULL` or `autopay_enabled = false`, abort the charge.
- The autopay task must re-check `autopay_enabled` inside the same transaction that issues the `online_payments` INSERT, not in a separate read before the payment API call.
- The unbind handler must also use `SELECT FOR UPDATE` on the row when soft-deleting to serialize with any concurrent autopay read.
- Alternatively: the autopay task uses the deterministic idempotency key (Pitfall 3 mitigation), and the unbind handler additionally checks for a pending `online_payments` row with that key and cancels it if `status = 'pending'` (before the webhook arrives).

**Warning signs:**
- Autopay task reads `autopay_enabled` with a plain `SELECT` (no FOR UPDATE).
- Unbind handler and autopay task operate on the same row without any DB-level synchronization.

**Phase to address:**
Phase 79 (autopay task + unbind endpoint, concurrency contract).

---

### Pitfall 9: РФ consent and disclosure requirements for recurring billing (новый ФЗ-376)

**What goes wrong:**
Russia enacted law 376-FZ (effective March 2026) banning digital services from auto-renewing subscriptions without explicit documented consumer consent. Failure to obtain and store consent before enabling autopay exposes the business to consumer protection complaints and potential fines under consumer rights law.

**Why it happens:**
The developer implements autopay as a technical feature without reading the regulatory requirement. The law targets "digital services" billing periodically — a gym CRM's membership autopay renewal is precisely in scope.

**How to avoid:**
- At the moment the client enables autopay (toggle ON), the UI must show explicit disclosure: the charge amount, frequency (renewal period), and how to cancel. This disclosure must be confirmed (checkbox or "Accept" button) — not just shown.
- Store a `consent_recorded_at` timestamp on the `client_payment_methods` row at the moment autopay is enabled. This is the audit trail of consent.
- Provide a clear "отключить автоплатёж" mechanism (the unbind flow or a separate toggle). The law requires easy opt-out.
- The autopay toggle OFF must also clear `consent_recorded_at` (or log a `consent_revoked_at`).
- Note: The autopay feature must NOT be enabled by default — the user must actively turn it on.

**Warning signs:**
- Autopay enabled at card-save time automatically (no separate consent step).
- No `consent_recorded_at` column on `client_payment_methods`.
- No disclosure shown before enabling autopay in the PWA UI.

**Phase to address:**
Phase 79 (backend: `consent_recorded_at` column in migration) + PWA phase (frontend: consent disclosure UI before enabling autopay). Both required before production.

---

### Pitfall 10: `autopay` requires explicit activation in the YooKassa production account

**What goes wrong:**
Autopayments (recurring charges without user confirmation) work by default only in YooKassa's test shop. In production, this feature must be explicitly enabled by contacting the YooKassa manager. If the production account does not have autopay enabled, all `create_payment(payment_method_id=...)` calls will return `permanent_error` with `forbidden` or `not_allowed` — not a transient error, not a misconfiguration you can fix in code.

**Why it happens:**
The sandbox works fine during development. The production account gate is an operator-level step that has no code equivalent.

**How to avoid:**
- Document this as an OPERATOR-PENDING step (same pattern as D-72-06 for the initial ЮKassa live credential leg): "contact ЮKassa manager to enable autopayments on the production account."
- The autopay ARQ task must check for `permanent_error` with a specific error code and log an operator alert, not retry indefinitely.
- Add a health-check or a startup probe that verifies autopay is enabled (or document the verification step in the operator runbook).

**Warning signs:**
- No operator runbook step for activating autopay on the ЮKassa production account.
- Autopay task retries `permanent_error` responses without distinguishing `not_allowed` (operator gate) from other permanent errors.

**Phase to address:**
Phase 79 (backend ARQ task) — add the `not_allowed` handling and operator alert. Runbook step is an operator action, not a code action.

---

## Reschedule Pitfalls

### Pitfall 11: Slot double-booking race on reschedule (atomicity of move)

**What goes wrong:**
Reschedule is a two-operation sequence: cancel the old booking + create a new booking on the target slot. If implemented as two separate DB operations (not atomic), a second concurrent request can book the target slot between the cancel and the re-create. The client ends up with no booking at all (target slot taken, old slot cancelled) or the old slot stays occupied while the new one is also taken.

**Why it happens:**
The naive implementation calls `cancel_booking(old_booking_id)` and then `create_booking(new_slot_id)` sequentially in the service layer. These are two separate transactions. Between them, another client's booking request arrives for the target slot.

**How to avoid:**
- The reschedule operation must be a single atomic DB transaction: UPDATE old booking status to `'cancelled'` + INSERT new booking for the target slot, both under the same `async with session.begin()` scope.
- The partial UNIQUE `uq_bookings_slot_confirmed` on `(slot_id) WHERE status='confirmed'` is already in place — the INSERT will raise `IntegrityError` if the target slot is taken, allowing the service to return `409 slot_already_booked` and roll back the cancel atomically.
- Use `SELECT ... FOR UPDATE` on the old booking row at the start of the transaction to prevent concurrent reschedules of the same booking.
- The new booking INSERT must use the same `_is_slot_confirmed_conflict` discriminator already in `bookings/service.py`.

**Warning signs:**
- Two separate `await session.commit()` calls in the reschedule handler.
- Reschedule calling `service.cancel_booking()` and then `service.create_booking()` as two independent service calls.

**Phase to address:**
Phase 80 (reschedule backend). The atomicity contract must be in the phase plan before implementation. Write a concurrent-reschedule race test.

---

### Pitfall 12: Reschedule bypassing the client cancel cutoff window

**What goes wrong:**
`POST /client/booking/{id}/cancel` enforces a cutoff window (e.g., must cancel at least N hours before the slot). `POST /client/booking/{id}/reschedule` is a new endpoint. If the service delegates to the existing `cancel_booking_for_client` helper without checking the cutoff, or worse implements its own cancel path that skips the cutoff guard, clients can effectively bypass the cancellation window by rescheduling at the last minute.

**Why it happens:**
The developer implements reschedule as "cancel + create" but uses a lower-level repository call that skips the service-layer FSM guard (the cutoff check lives in the service, not the repository).

**How to avoid:**
- Reschedule must enforce the same cancel cutoff as `client_cancel_booking`. Do not bypass the `cancel_booking_for_client` guard — either call it (and catch `cancel_window_expired` as a 409), or inline the cutoff check explicitly before the atomic transaction.
- The cutoff check must be the first gate in `reschedule_booking`, before any DB mutation.
- Optionally: define a separate reschedule-specific cutoff (e.g., N hours before the ORIGINAL slot start time) — this is a business decision, but must be explicit, not an accident.

**Warning signs:**
- Reschedule service function calls the repository directly to update booking status without going through the cancel service function.
- No test for "reschedule within cutoff window returns 409."

**Phase to address:**
Phase 80 (reschedule backend). Add a test case: `test_reschedule_within_cancel_window_returns_409`.

---

### Pitfall 13: IDOR on the old booking in reschedule

**What goes wrong:**
The reschedule request body contains `new_slot_id`. There is no ownership requirement on the target slot — any authenticated client can book any active slot. However, the OLD booking must be IDOR-verified (the client can only reschedule their own booking). Missing the ownership check on the old booking allows a client to cancel another client's booking and take their slot.

**Why it happens:**
Reschedule is implemented as `POST /client/booking/{booking_id}/reschedule` with `new_slot_id` in the body. The developer verifies that the target slot exists and is available, but forgets to verify that `booking_id` belongs to `client.id`.

**How to avoid:**
- In the reschedule handler: `client_id` comes from `require_client()` only. The first repository query must be `SELECT booking WHERE id = :booking_id AND client_id = :client_id`. If not found → `404 booking_not_found` (404-collapse, D-20-IDOR anti-oracle pattern — same as `client_cancel_booking`).
- The target slot (`new_slot_id`) does not need an ownership check — any active slot is bookable — but it does need an existence + status check (slot must be `'active'`, not `'booked'` or in the past).
- Do not add a `client_id` to the request body or URL for the ownership assertion (D-20-PRINCIPAL: `ClientPrincipal` is the sole identity source).

**Warning signs:**
- Reschedule handler does not filter `WHERE client_id = :client_id` when fetching the old booking.
- A `client_id` field appears in `ClientRescheduleRequest` body schema.

**Phase to address:**
Phase 80 (reschedule backend). The IDOR ownership assertion must be the first operation in the service function. Add test: `test_reschedule_other_client_booking_returns_404`.

---

### Pitfall 14: Reschedule notification fan-out collision with existing booking_notifications idempotency

**What goes wrong:**
The `booking_notifications` table has `UNIQUE (booking_id, kind, channel)`. When a booking is rescheduled, the old booking was already confirmed and may have sent a `'confirmed'` notification. The new booking (new row) has its own `booking_id`. If reschedule is implemented as "mutate the existing booking row" (update `slot_id` in-place) rather than "cancel + create new row," the existing `'confirmed'` notification row for the original slot is orphaned but the constraint prevents sending a new `'confirmed'` for what is now the same `booking_id` with a new slot.

**Why it happens:**
Reschedule-as-in-place-update seems simpler than cancel+create. But it breaks the notification idempotency invariant and makes the audit trail ambiguous (one booking row that silently changed slots).

**How to avoid:**
- Reschedule MUST be cancel-old-booking + create-new-booking (two rows). This is the only way to preserve audit integrity and allow notification re-send.
- The new booking row gets a new `booking_id`, so the `'confirmed'` notification can be sent for the new booking without hitting the UNIQUE constraint.
- Old booking gets a `cancel_reason = 'rescheduled'` to distinguish it from client-initiated cancels in the audit log.
- Do NOT implement reschedule as an UPDATE to `bookings.slot_id`. That would also invalidate the existing `_is_slot_confirmed_conflict` partial UNIQUE (it protects via the old slot_id, not the new one).

**Warning signs:**
- Alembic migration for reschedule adds a `rescheduled_to_slot_id` column to the `bookings` table instead of creating a new booking row.
- Reschedule service function calls `UPDATE bookings SET slot_id = :new_slot_id WHERE id = :booking_id`.

**Phase to address:**
Phase 80 (reschedule backend). Architectural decision must be locked in phase plan: reschedule = cancel + create, not in-place update.

---

## Weekly-Activity Analytics Pitfalls

### Pitfall 15: Timezone / week-boundary bug — `new Date(dateOnlyString)` or UTC midnight assumption

**What goes wrong:**
`GET /client/activity/weekly` returns activity aggregated by day-of-week for the past 7 days. If the backend computes "today" using `datetime.utcnow()` or `datetime.now()` (system TZ), and the server runs in UTC, then a check-in at 23:30 UTC on Monday (which is 02:30 Tuesday Moscow time) appears in the Monday bucket instead of Tuesday. The client sees wrong day labels.

The frontend analogue: `new Date('2026-06-03')` in JavaScript is parsed as midnight UTC, not midnight Moscow time. When formatted for display, it may show as the previous day.

**Why it happens:**
The `visits.gym_date` STORED column already handles this correctly via `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`. But if a new aggregate query bypasses `gym_date` and groups by `DATE(checked_in_at)` (which defaults to UTC in Postgres), it reintroduces the TZ bug.

**How to avoid:**
- The backend aggregate query for `weekly_activity` MUST group on `visits.gym_date` (the STORED GENERATED column), not on `DATE(checked_in_at)` or `DATE_TRUNC(...)`. `gym_date` is already Moscow-TZ-correct per the existing DB discipline (v1.8 precedent: all aggregate queries use `gym_date`).
- "Today" in the 7-day window calculation must use `func.current_date()` in the SQL query (Postgres evaluates `CURRENT_DATE` in the session TZ which is set to `Europe/Moscow` by the DB connection), or compute it in Python using `datetime.now(tz=ZoneInfo('Europe/Moscow')).date()`.
- The response returns ISO date strings (`"2026-06-03"`) — never epoch timestamps. The PWA must use `date-fns` with the `ru` locale for display (already the project convention: `src/shared/i18n/date.ts`).
- Never use `new Date(dateOnlyString)` in the PWA. Use `parseISO` from `date-fns` and pass to `formatDate` with explicit TZ — or better, just use the string directly as a key and derive the day label from the server.

**Warning signs:**
- Aggregate query uses `DATE(v.checked_in_at)` instead of `v.gym_date`.
- Backend uses `datetime.utcnow()` to compute the 7-day start boundary.
- PWA uses `new Date(dayString)` to derive a day-of-week label.

**Phase to address:**
Phase 81 (weekly-activity backend). Add a golden test: a check-in at 21:30 UTC (00:30 next-day Moscow) must bucket to the Moscow calendar date (same pattern as v1.8 VER-02 DST test).

---

### Pitfall 16: N+1 query for per-day visit aggregation

**What goes wrong:**
Naive implementation: load all visits for the client in the 7-day window, then group them in Python. With a few hundred visits per client (long-term members) this is fine, but it sends unnecessary data from Postgres. If implemented with an ORM relationship load (e.g., `await session.execute(select(Visit).where(...))` then group in-memory), it is an ORM N+1 pattern waiting to happen when the query is copied.

**Why it happens:**
The endpoint is a `GET` with simple data, so developers reach for the ORM first.

**How to avoid:**
- Use the reports-module discipline (v1.8 D-54-07/08): raw SQL `text()` query with a `GROUP BY v.gym_date` aggregate directly in Postgres.
- Single query: `SELECT gym_date, COUNT(*) as visit_count FROM visits WHERE client_id = :client_id AND gym_date >= :start_date GROUP BY gym_date ORDER BY gym_date ASC`.
- Returns at most 7 rows. Zero ORM object loading needed.
- The `duration_minutes` field (if included) must also be aggregated server-side if a `duration` column ever exists, not computed in Python per row.

**Warning signs:**
- Service function calls `list_client_visits()` (the paginated history endpoint function) and then re-aggregates in Python.
- Any `for visit in visits:` loop in the weekly-activity service function.

**Phase to address:**
Phase 81 (weekly-activity backend). Spec the SQL aggregate in the phase plan, not just "return last 7 days of visits."

---

### Pitfall 17: Leaking other clients' visit data via missing `client_id` filter

**What goes wrong:**
The aggregate query omits `WHERE client_id = :client_id`, returning activity for ALL clients at the gym. The weekly-activity response then shows inflated or incorrect counts. Worse, if the API is adapted to return per-client identifiers or if the response is used for a trainer-facing view later, it leaks real visit data.

**Why it happens:**
Aggregate queries that use raw SQL `text()` are not filtered by the ORM's column ownership pattern. The developer writes the aggregate, tests it, but forgets the `client_id` filter because the test fixture only has one client.

**How to avoid:**
- Always bind `:client_id` as a parameter in the raw SQL aggregate. This is the D-20-IDOR invariant: every client-scoped endpoint carries a mandatory `client_id` filter at the repository layer.
- Add an integration test with TWO clients having different visit histories. Verify client A's endpoint returns only client A's data.
- The `client_id` filter must be in the `WHERE` clause, not just an application-level post-filter on the result set.

**Warning signs:**
- `weekly_activity` repository function has no `client_id` parameter.
- Test fixture for weekly-activity has only one client.

**Phase to address:**
Phase 81 (weekly-activity backend). Two-client test is mandatory — same pattern as IDOR tests across the codebase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip `consent_recorded_at` column | Simpler migration | No consent audit trail; regulatory risk under ФЗ-376 | Never |
| Store `card_last4` from create_payment response (not webhook) | No extra webhook path | May store last4 for a card that never saved successfully | Never — always read from webhook |
| Implement reschedule as in-place `slot_id` UPDATE | Simpler SQL | Breaks audit trail, notification idempotency, partial UNIQUE | Never |
| Use `datetime.utcnow()` for week start boundary | Trivial to write | DST / TZ bugs that appear only at night and only around DST transitions | Never in this codebase |
| Skip the atomic reschedule transaction | Two separate commits are easier to reason about | Double-booking race window that WILL be hit in production | Never |
| Autopay creates the membership immediately (not via webhook) | Simpler flow | Violates anti-oracle invariant; breaks the single activation gate | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| YooKassa recurring / autopay | Assuming autopay is enabled on production account by default | It is TEST-ONLY by default; requires explicit activation by contacting ЮKassa manager |
| YooKassa saved methods | Calling a non-existent DELETE /v3/payment_methods API | Unbind is local-only: soft-delete the `client_payment_methods` row in your DB |
| YooKassa autopay charge | Using a random UUID as idempotency key | Use deterministic key derived from `(client_id, membership_id, renewal_date)` |
| YooKassa `payment_method.saved` | Reading `payment_method.id` from `create_payment` response to store immediately | Only store after `payment.succeeded` webhook AND `payment_method.saved == true` |
| YooKassa autopay `payment.canceled` | Treating failure as transient and retrying indefinitely | Distinguish `card_expired` (do not retry) from `insufficient_funds` (one retry after 24h) |
| PostgreSQL partial UNIQUE for bookings | Creating a new reschedule booking without leveraging the existing race guard | Re-use `uq_bookings_slot_confirmed` — the INSERT will IntegrityError on race |
| visits.gym_date STORED column | Grouping by `DATE(checked_in_at)` in raw SQL | Always group by `gym_date` — it is already Moscow-TZ-correct |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting `client_id` in the request body for payment-method or reschedule endpoints | IDOR: client manipulates which card/booking is targeted | `ClientPrincipal` from `require_client()` is the ONLY identity source; no `client_id` in body |
| Storing `payment_method.id` token per-user without `unbound_at` soft-delete | Token never expires on YooKassa side; a deleted client's card can still be charged | Soft-delete with `unbound_at` timestamp; autopay task checks `unbound_at IS NULL` before charging |
| Enabling autopay without `consent_recorded_at` | Regulatory non-compliance (ФЗ-376 March 2026); unfair debit charges | Record consent timestamp at the moment of opt-in; disable autopay on unbind |
| Adding `Role.CLIENT` to RBAC for new endpoints | Violates D-20-PRINCIPAL: client principal is isolated from staff roles | All new endpoints use `require_client()` + `ClientPrincipal`, never `require_permission` with `Role.CLIENT` |
| Returning `404` when no card is saved vs `200 null` | Enumeration oracle: third party can probe whether a client has a saved card | Follow D-69-03: empty state = `200 null`, never `404` for own-scope reads |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full visit ORM objects for weekly aggregation | Slow `GET /client/activity/weekly` on long-term members | Single GROUP BY aggregate SQL query (7 rows max) | Even at 1 client, ORM load is unnecessary overhead |
| Autopay cron iterating all clients sequentially | Cron run takes O(N clients) time; approaches timeout window | Batch the SELECT, skip clients with no active autopay; use `unique=True` + per-client ARQ task | At ~100 clients with autopay enabled |
| N+1 slot JOIN for reschedule available-slots list | Slow slot listing for reschedule UI | Reuse existing `list_available_slots` service function (already JOIN-projected) | Unlikely at gym scale, but bad practice |

---

## "Looks Done But Isn't" Checklist

- [ ] **Card save flow:** Verify `payment_method.saved == true` in the `payment.succeeded` webhook handler before inserting `client_payment_methods` row.
- [ ] **Autopay production activation:** Operator runbook includes "contact ЮKassa manager to enable autopayments on production account" — documented as OPERATOR-PENDING, not a code item.
- [ ] **Consent disclosure UI:** The autopay toggle in the PWA shows amount + frequency + opt-out info before enabling. `consent_recorded_at` written to DB on confirmation.
- [ ] **Reschedule atomicity:** A race test: two concurrent reschedule requests for the same booking + same target slot — only one succeeds; other returns `409 slot_already_booked`.
- [ ] **Reschedule IDOR test:** `test_reschedule_other_client_booking_returns_404` exists and passes.
- [ ] **Weekly-activity TZ golden test:** A visit at 21:30 UTC (00:30 Moscow next day) buckets to the Moscow calendar date, not the UTC date.
- [ ] **Weekly-activity two-client IDOR test:** Client A's endpoint returns only client A's visits.
- [ ] **Autopay failure path:** `payment.canceled` webhook for an autopay charge disables `autopay_enabled` and sends a notification. Tested with a fake `cancellation_reason = 'card_expired'` payload.
- [ ] **Unbind race test:** Unbind + concurrent autopay cron — the cron must not charge a card that was unbound.
- [ ] **No `Role.CLIENT` anywhere in new code:** `grep -r "Role.CLIENT"` returns zero results in new files.

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-----------------|--------------|
| Storing PAN instead of YooKassa token (P1) | Phase 79 | Migration review: only `yookassa_payment_method_id` + display fields |
| Activating on client-reported success, not webhook (P2) | Phase 79 | Test: autopay task + webhook handler separation test |
| Double-charge race / non-deterministic idempotency key (P3) | Phase 79 | Race test: two concurrent cron task invocations produce one charge |
| Not verifying `payment_method.saved` before storing token (P4) | Phase 79 | Test: webhook handler with `saved: false` does not insert `client_payment_methods` row |
| Calling non-existent YooKassa DELETE API for unbind (P5) | Phase 79 | Code review: no `yookassa_client.*` call in unbind handler |
| Autopay failure leaving membership lapsed silently (P6) | Phase 79 | Test: `payment.canceled` webhook → `autopay_enabled = false` + notification sent |
| IDOR oracle from card exists vs not (P7) | Phase 79 | Test: no-card state returns `200 null`; other client's card returns `404` collapse |
| Unbind-while-charge-in-flight race (P8) | Phase 79 | Concurrency test: unbind + concurrent autopay → no charge after unbind |
| РФ consent / ФЗ-376 disclosure missing (P9) | Phase 79 (backend column) + PWA phase (UI) | `consent_recorded_at` NOT NULL when `autopay_enabled = true` |
| Autopay not enabled on YooKassa production account (P10) | Phase 79 | Operator runbook contains explicit "request autopay activation" step |
| Double-booking race on reschedule (P11) | Phase 80 | Concurrent reschedule race test; only one succeeds |
| Reschedule bypassing cancel cutoff (P12) | Phase 80 | Test: reschedule within cutoff window returns `409` |
| IDOR on old booking in reschedule (P13) | Phase 80 | Test: client rescheduling another client's booking returns `404` |
| Reschedule as in-place slot_id UPDATE (P14) | Phase 80 | Code review: no `UPDATE bookings SET slot_id = ...` in reschedule path |
| TZ/week-boundary bug in weekly activity (P15) | Phase 81 | Golden test: 21:30 UTC visit buckets to next Moscow calendar day |
| N+1 query for weekly activity (P16) | Phase 81 | Code review: single GROUP BY aggregate SQL, no ORM object loading |
| Missing client_id filter in weekly activity (P17) | Phase 81 | Two-client IDOR test |

---

## Sources

- YooKassa official docs — recurring payments basics: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics (MEDIUM confidence — accessed 2026-06-03; confirms autopay is TEST-ONLY by default; no API DELETE endpoint found confirming "unbind is local-only")
- YooKassa — saving payment method during payment: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment (MEDIUM confidence — accessed 2026-06-03; confirms `payment_method.saved` must be verified post-success)
- YooKassa — autopayments with saved method: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved (MEDIUM confidence — accessed 2026-06-03; confirms no user confirmation step on recurring charges)
- Russia ФЗ-376 auto-renewal ban (March 2026): https://digitalpolicyalert.org/event/34332-bill-amending-article-16-of-law-no-2300-1-on-protection-of-consumer-rights-to-ban-automatic-debits-for-online-subscriptions-376-fz-enters-into-force (MEDIUM confidence — secondary source, law is publicly documented)
- PostgreSQL advisory locks + double booking prevention: https://jsupskills.dev/how-to-solve-the-double-booking-problem/ + https://dteather.com/blogs/postgres-advisory-locks/ (HIGH confidence for the `SELECT FOR UPDATE` + partial UNIQUE pattern, already proven in this codebase)
- Codebase analysis — `apps/backend/app/modules/bookings/models.py`, `visits/models.py`, `client_portal/router.py`, `integrations/yookassa/client.py`, `integrations/yookassa/types.py` (HIGH confidence — direct source)
- Existing pitfall patterns in PROJECT.md v1.7 (anti-oracle return screen, D-71-04 idempotency key, webhook re-fetch discipline) — HIGH confidence, already proven in production

---
*Pitfalls research for: v2.2 Membership self-service depth (saved-card autopay + booking reschedule + weekly-activity)*
*Researched: 2026-06-03*
