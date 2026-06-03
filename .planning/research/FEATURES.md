# Feature Research

**Domain:** Gym member self-service PWA — v2.2 Membership self-service depth (card-on-file + autopay, booking reschedule, weekly activity)
**Researched:** 2026-06-03
**Confidence:** HIGH — based on YooKassa official docs, codebase inspection of existing PWA components (CardSheet, BookingManageSheet, weekly-activity card), and industry patterns for fitness app UX.

---

## Context

This is a subsequent milestone (v2.2), following v2.1 which shipped flag-flips + small field additions. Three net-new backend capabilities are needed to unlock three existing-but-hidden PWA components:

1. **Card-on-file + autopay** — `CardSheet` exists at `ProfileExtraSheets.jsx:324`, gated by `PROFILE_FEATURE_FLAGS.linkedCard = false`. The sheet already renders: card visual (•••• 4821), autopay toggles, unbind confirm dialog, and a footer note "Данные карты хранятся на стороне платёжного провайдера." Needs: real `payment_method_id` stored per client, `GET /client/payment-method`, `DELETE /client/payment-method`, `PATCH /client/membership/autopay` toggle.

2. **Booking reschedule** — `BookingManageSheet.jsx:179` has a full `reschedule` view wired to mock `CALENDAR` / `BUSY_SLOTS` / `TIME_SLOTS`. The cancel view already offers "Лучше перенесу" as an escape hatch to reschedule. Needs: real available-slots query scoped to the existing booking's trainer, and `POST /client/bookings/{id}/reschedule`.

3. **Weekly activity** — `ProfileScreen.jsx:267-285` has a 7-bar placeholder card gated by `PROFILE_FEATURE_FLAGS.weeklyActivity = false`. It expects minutes/type per day for Mon–Sun. Needs: `GET /client/activity/weekly` returning per-day visit counts and minutes.

**All three features are staff-free** — no changes to `apps/admin-web`, all routes under `require_client()` in `app/modules/client_portal/`.

---

## Feature Landscape

### Table Stakes (Users Expect These)

#### Feature 1: Card-on-file + Autopay

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Display saved card last-4 / type | Fitness app standard (FitBase, YClients, Mindbody all show «•••• 4821»). Users expect to see what card is on file without re-entering. | LOW | `GET /client/payment-method` returns `{payment_method_id, type, last4, card_type, expiry_month, expiry_year, saved_at}`. Data sourced from YooKassa `payment_method` object stored at checkout time. Clubcore never stores raw card data — only `payment_method_id` + display fields. |
| Unbind card | Expected by users who switch cards or want to opt out. The CardSheet already has the UI with confirmation dialog. | LOW | `DELETE /client/payment-method` — removes the stored `payment_method_id` from clubcore DB. YooKassa has no delete endpoint; deletion is managing your own DB record only (confirmed per YooKassa docs). Returns 204. Requires confirmation step in UI (already built). |
| Autopay toggle for membership renewal | Standard in any subscription-based fitness app. Users want the option, and it must be clearly disclosed before enabling. | MEDIUM | `PATCH /client/membership/autopay` body `{enabled: bool}`. Stores `autopay_enabled` flag on membership record (or new `client_payment_settings` table). When enabled + a card is on file + the ARQ `expire_memberships` cron runs → triggers an autopay attempt N days before expiry (see below). |
| Card saved during checkout (implicit binding) | Industry standard: card is saved on the first successful payment, not via a separate "add card" flow. | MEDIUM | During `POST /client/checkout/membership` (or renewal), pass `save_payment_method: true` to YooKassa API. On `payment.succeeded` webhook, store `payment_method.id` + `last4` + `type` + `expiry` in a new `client_payment_methods` table keyed by `client_id`. The existing webhook handler must be extended to capture and persist this. |
| Charge N days before membership expiry (if autopay on) | Core autopay behavior. Users should not be surprised by expiry — the system should renew proactively. | HIGH | The existing `expire_memberships` ARQ cron runs at 06:05 MSK. A new `run_autopay_renewals` cron (e.g. 06:10 MSK, after the expire cron) selects memberships with: `status='active'`, `end_date = today + N` (N = 3 days as shown in CardSheet mock "Спишется за 3 дня до конца"), `autopay_enabled = true`, and client has a `payment_method_id`. Triggers YooKassa autopayment via `payment_method_id` (no user interaction required — this is YooKassa's `безакцептное списание` / autopayment-without-consent flow). Activation still locked to `payment.succeeded` webhook (D-06 anti-oracle invariant preserved). |
| Notification before autopay charge | Users must be informed before being charged. This is both UX expectation and a YooKassa merchant obligation. | MEDIUM | Send a Telegram/email DM 3 days before the auto-charge attempt (same time as the `send_expiring_notifications` cron). Template: "Через 3 дня спишем [amount] ₽ для продления абонемента. Если хочешь отменить — зайди в приложение." New `LOCKED_EMAIL_TEMPLATES` entry; new LOCKED audit event. |
| Failure notification + autopay disable on hard failure | If the card declines (insufficient funds, revoked permission), the member must be notified and autopay must be disabled automatically. | MEDIUM | On `payment.canceled` webhook where `cancellation_details.reason` is `permission_revoked`, `insufficient_funds`, or `card_expired`: set `autopay_enabled = false`, send failure DM. On soft failures (issuer timeout, temporary unavailability): retry logic is application-side (YooKassa does not retry automatically). Industry standard: up to 2–3 retries over 24–48h, then disable. |

**Complexity driver: autopay renewal chain is HIGH because it touches:** existing online_payments webhook handler, existing renewal FSM, existing ARQ cron infrastructure, new payment method storage table, new consent disclosure requirements, and failure/retry handling.

#### Feature 2: Booking Reschedule

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reschedule to a different slot (same trainer) | Standard gym app behavior. BookingManageSheet already shows the UX — date strip + time grid + confirm. The cancel view explicitly nudges toward reschedule ("Лучше перенесу" button). | MEDIUM | `POST /client/bookings/{id}/reschedule` body `{new_slot_id}`. Atomic operation: cancel old booking + create new booking in a single DB transaction. Race-safe: new slot must pass the `(slot_id) WHERE status='confirmed'` partial-UNIQUE check. Returns new `BookingResponse`. |
| Available slots query scoped to booking's trainer | Reschedule view shows only that trainer's future slots (not all trainers). The existing `GET /client/schedule/available-slots` supports `?trainer_id=` but the rescheduling flow must pass the trainer from the original booking automatically. | LOW | `GET /client/schedule/available-slots?trainer_id={original_booking.trainer_id}&from={today}` — already supported in the existing available-slots endpoint. No new endpoint needed; PWA passes trainer_id. |
| Time cutoff — cannot reschedule < 6h before session | Expected: industry standard is 12–24h for PT sessions; this project already uses 6h as the cancellation policy window. Reschedule should honor the same window. | LOW | Server-side check: `slot.start_time - now(UTC) >= 6h`. Return 422 `reschedule_window_expired` if too close. The existing cancel policy check in `POST /client/bookings/{id}/cancel` uses the same 6h window — reuse the helper. |
| Slot availability re-check at confirm time | Between selecting a slot in the UI and tapping confirm, the slot may be taken by another client. | LOW | The atomic reschedule operation handles this via the DB partial-UNIQUE race guard. If new slot is already taken: return 409 `slot_no_longer_available`. PWA shows "Слот занят — выбери другое время." |
| Cannot reschedule to the same slot | Edge case: client picks the same slot they're already booked into. | LOW | Server-side check: `new_slot_id != current_slot_id`. Return 422 `same_slot` if equal. |
| Reschedule only confirmed bookings | Cancelled, no-show, completed bookings cannot be rescheduled. | LOW | FSM guard: `booking.status == 'confirmed'`. Otherwise 422 `booking_not_reschedulable`. |

**Implementation note:** "Atomic move" (cancel + rebook in one transaction) is preferred over "cancel then rebook" because it avoids a race window where the client holds no booking between steps, and it avoids partial state if the rebook fails. One DB transaction: UPDATE old booking to `cancelled` (with `cancel_reason='rescheduled'`) + INSERT new booking into new slot. The partial-UNIQUE guard on the new slot fires within the same transaction.

#### Feature 3: Weekly Activity

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 7-bar chart, Mon–Sun, current week | Standard in every fitness app (Apple Fitness, Google Fit, Strava). The ProfileScreen card already renders placeholder bars for Mon–Sun. Members expect visual confirmation of their weekly rhythm. | LOW | `GET /client/activity/weekly` returns an array of 7 objects: `{date: "YYYY-MM-DD", dow: "Пн"…"Вс", visit_count: int, minutes: int \| null, has_workout: bool}`. Backend queries `visits` (for visit_count) and optionally `pt_sessions` (for minutes). Week = Mon–Sun in Europe/Moscow. |
| Visit count per day | Each bar represents at least one gym visit. Table stakes — the `visits` table is the source. | LOW | Count of `visits WHERE client_id = ? AND gym_date BETWEEN monday AND sunday`. Simple aggregation, no joins needed for visit_count. |
| Total weekly sessions count | Summary line above bars: "3 тренировки за неделю". Expected by anyone with a fitness tracker. | LOW | Sum of visit_counts across the 7 days. Can be computed client-side from the 7-item response, or returned as `total_visits: int` in the response envelope. |

### Differentiators (Competitive Advantage)

#### Card-on-file + Autopay

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Zero-amount card binding (without first payment) | Allows clients to bind a card without making a purchase first (YooKassa "Привязка на нулевую сумму"). Useful for new members who haven't paid yet or want to set up autopay before their membership expires. | HIGH | Requires a separate `POST /client/payment-method/bind` flow: create a 1-kopeck or 0-amount authorization to save the card, then discard the hold. YooKassa supports this via `save_payment_method: true` + `capture: false`. Adds a new UX flow (not currently in CardSheet mock). **Defer to v2.3+ — scope risk.** |
| Card expiry warning notification | Notify members N days before their saved card expires so they can update it before autopay fails. | MEDIUM | Check `payment_methods.expiry_year/month` against current date in a cron. Send DM 30 days before expiry. **Nice-to-have — defer after autopay retry logic is working.** |

#### Booking Reschedule

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Reschedule limit per booking (e.g. max 2 reschedules) | Prevents abuse — a member can't reschedule indefinitely. Some platforms allow only 1 free reschedule per booking. | LOW | Track `reschedule_count` on booking row (default 0, increment on reschedule). Return 422 `reschedule_limit_reached` at threshold. **The current mock doesn't show this limit — treat as v2.3+ differentiator.** |
| Cross-trainer reschedule | Allow rescheduling to a different trainer if the original is unavailable. | HIGH | Requires presenting the full slot catalog (not trainer-scoped). Adds UX complexity. **Anti-feature for v2.2 — scope risk.** |

#### Weekly Activity

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| PT session minutes per day | If a visit had a PT session, show duration (e.g. 60 min bar vs 0 for self-visit). Makes bars meaningful rather than binary. | MEDIUM | Join `visits` → `pt_sessions` (via `booking_id`) → get session duration. PT sessions don't currently store `duration_minutes` — only `performed_at`. **Would require adding a `duration_minutes` field to `pt_sessions` (Alembic migration) or computing from slot `end_time - start_time` via `bookings.slot_id`.** |
| Streak indicator | "3 недели подряд" — motivational metric used by Apple Fitness, Strava, etc. | MEDIUM | Requires querying `visits` across multiple past weeks. Backend-computed. **Nice-to-have — not in the ProfileScreen mock card. Defer.** |
| Comparison to previous week | "На 2 тренировки больше, чем на прошлой неделе." Used by Google Fit. | LOW-MEDIUM | Query two weeks instead of one; return `prev_week_total: int` alongside current. **Defer — not in mock.** |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-renew with cash payment | Some members pay cash. They might expect the system to "remind and charge" for cash too. | Cash autopay is a contradiction — cash requires physical presence at reception. No technical path to charge cash remotely. | Cash memberships show standard expiry notifications (already built in v1.3). No autopay toggle shown when no card on file. |
| Cross-trainer reschedule in v2.2 | Members sometimes want a different trainer when their preferred one is unavailable. | Adds a full trainer-selection UI inside the reschedule flow — doubles UX complexity, adds a new available-slots query pattern, and requires a different cancellation policy (trainer changed = different session type). Scope risk. | Same-trainer reschedule only in v2.2. Cross-trainer = book a new session via BookScreen. |
| Partial refund on reschedule | If a member reschedules to a cheaper slot, they may expect a refund difference. | PT package credits don't have per-slot pricing — the package is the billing unit. Differential refunds require new ledger logic. | Reschedule is free within policy window; no price differential. |
| "Add a card" as a standalone flow (zero-amount binding) | Members want to pre-bind a card before their first purchase. | Zero-amount binding via YooKassa is technically supported but requires a separate flow (`POST /client/payment-method/bind`), an additional YooKassa widget or redirect, and new fraud vectors (binding without any purchase intent). Adds a separate code path that needs its own testing. | Bind-on-first-purchase is the standard pattern. Card gets saved automatically during the first membership payment. Dedicated "add card" flow deferred to v2.3. |
| Weekly activity as a full workout log | Members might expect to view every workout's details from the activity bars. | The activity card is a summary widget, not a workout log. Turning it into a detail view requires a drill-down screen, which is out of scope. | Activity bars show weekly summary only. Detailed workout history already exists in the training history tab (`GET /client/pt-sessions`). |
| Autopay for PT session individual bookings | CardSheet mock shows "Авто-оплата тренировок · Сразу после записи." Charging immediately when a booking is made would bypass the user's active PT package and create a new payment flow. | PT sessions are already paid via PT packages. A separate per-booking autopay creates a double-billing risk and complicates the existing PT package credit model. | Remove the "Авто-оплата тренировок" toggle from the MVP. Show only "Авто-продление абонемента." The per-booking charge toggle requires a separate PT billing model that doesn't exist. |

---

## Feature Dependencies

```
client_payment_methods table (Alembic migration)
  └──required by──> GET /client/payment-method (display card)
  └──required by──> DELETE /client/payment-method (unbind)
  └──required by──> autopay_enabled flag (toggle)
  └──required by──> run_autopay_renewals ARQ cron

save_payment_method: true during checkout (webhook handler extension)
  └──required by──> client_payment_methods table being populated
  └──depends on──> existing payment.succeeded webhook handler (extend, not replace)

Membership.autopay_enabled field (Alembic migration OR client_payment_settings)
  └──required by──> PATCH /client/membership/autopay
  └──required by──> run_autopay_renewals cron (eligibility filter)

run_autopay_renewals ARQ cron
  └──requires──> client_payment_methods (card on file)
  └──requires──> autopay_enabled flag
  └──requires──> existing renew_membership service (D-06: activation locked to webhook)
  └──requires──> existing online_payments.create_payment (autopay path via payment_method_id)
  └──precedes execution of──> expire_memberships cron (charge before expiry date, not after)

Booking reschedule (POST /client/bookings/{id}/reschedule)
  └──requires──> existing available-slots endpoint (GET /client/schedule/available-slots)
  └──requires──> existing booking FSM cancel logic (reuses cancel path)
  └──requires──> existing partial-UNIQUE race guard on (slot_id) WHERE status='confirmed'
  └──no new Alembic migration needed (add reschedule_count col is optional differentiator)

GET /client/activity/weekly
  └──requires──> visits table (already exists, scoped by client_id)
  └──optional join──> pt_sessions via bookings.slot_id (for session minutes — only if duration stored)
  └──no new Alembic migration needed for visit_count-only response
```

### Dependency Notes

- **Autopay cron requires renewal FSM to be unchanged:** The existing `renew_membership` service (v1.3) handles date strategy and `previous_membership_id` chain. The autopay cron calls it via the existing online_payments path — it must NOT duplicate renewal logic.
- **Card binding requires webhook extension, not a new webhook:** The `payment.succeeded` handler already processes membership activations. Adding `payment_method_id` storage extends one `if payment.save_payment_method is True` branch — it does not fork the webhook.
- **Reschedule atomicity requires single-transaction cancel+insert:** The existing cancel path (`POST /client/bookings/{id}/cancel`) must NOT be called as a sub-step — it has its own audit events and session credits logic. The reschedule operation must implement its own single-transaction cancel+insert path that emits `booking_rescheduled` audit events (not `booking_cancelled_by_client`).
- **Weekly activity has no external dependencies** — it is a read-only aggregate over `visits` (already owned by client_portal). If minutes are not stored, bars show binary (visited / not visited). This is table-stakes sufficient.

---

## MVP Definition

### v2.2 Launch With

- [x] **Card display:** `GET /client/payment-method` — show last4, type, expiry if card on file; show "нет привязанной карты" if not.
- [x] **Bind-on-purchase:** Save `payment_method_id` from YooKassa `payment.succeeded` webhook when `save_payment_method: true` was passed at checkout.
- [x] **Unbind:** `DELETE /client/payment-method` — removes from clubcore DB, no YooKassa call needed.
- [x] **Autopay toggle:** `PATCH /client/membership/autopay` — `{enabled: bool}`. Only visible/enabled when a card is on file.
- [x] **Autopay renewal cron:** `run_autopay_renewals` ARQ task — fires 3 days before expiry for eligible memberships, uses `payment_method_id` to charge without user interaction.
- [x] **Autopay failure handling:** On `payment.canceled` with hard-fail reason → disable autopay + send DM notification.
- [x] **Pre-charge notification:** DM 3 days before autopay charge.
- [x] **Reschedule (same trainer):** `POST /client/bookings/{id}/reschedule` body `{new_slot_id}` — atomic cancel+rebook, 6h cutoff guard, slot availability re-check.
- [x] **Weekly activity:** `GET /client/activity/weekly` — 7-item array with `date, dow, visit_count`. No minutes required for MVP (bar height = visit_count, binary 0/1 is sufficient for first version).

### Add After Validation (v2.3+)

- [ ] **PT session minutes on activity bars** — add `duration_minutes` to `pt_sessions` + extend weekly activity endpoint; trigger: user feedback that bars are too simple.
- [ ] **Autopay retry logic** — retry failed autopay 2x over 48h before disabling; trigger: first real autopay failure reports from production.
- [ ] **Card expiry warning** — notify 30 days before card expires; trigger: production launch.
- [ ] **Reschedule count limit** — cap reschedules per booking at 2; trigger: abuse reports.

### Future Consideration (v2.3+)

- [ ] **Zero-amount card binding** — bind a card without a purchase (separate flow); requires additional YooKassa integration surface.
- [ ] **Cross-trainer reschedule** — reschedule to a different trainer's slot.
- [ ] **Weekly streak** — "N недель подряд"; requires multi-week history query.
- [ ] **Weekly comparison to previous week** — "X тренировки больше, чем на прошлой неделе."

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| GET /client/payment-method (display card) | HIGH | LOW | P1 |
| DELETE /client/payment-method (unbind) | HIGH | LOW | P1 |
| PATCH /client/membership/autopay toggle | HIGH | LOW | P1 |
| Save payment_method on checkout webhook | HIGH | MEDIUM | P1 |
| POST /client/bookings/{id}/reschedule | HIGH | MEDIUM | P1 |
| GET /client/activity/weekly (visit count only) | MEDIUM | LOW | P1 |
| run_autopay_renewals ARQ cron | HIGH | HIGH | P1 |
| Autopay failure notification + disable | HIGH | MEDIUM | P1 |
| Pre-charge DM notification (3 days before) | HIGH | LOW | P1 |
| PT session minutes on activity bars | MEDIUM | MEDIUM | P2 |
| Reschedule count limit | LOW | LOW | P2 |
| Card expiry warning notification | MEDIUM | MEDIUM | P2 |
| Zero-amount card binding flow | LOW | HIGH | P3 |
| Weekly streak / comparison | LOW | MEDIUM | P3 |

---

## РФ-Specific Considerations

### YooKassa Saved Payment Methods — What's Available

**Confirmed (HIGH confidence, official docs):**
- YooKassa supports card-on-file via `save_payment_method: true` on any payment request.
- The returned `payment_method` object contains: `type`, `id`, `saved: true`, `card.last4`, `card.first6`, `card.expiry_month`, `card.expiry_year`, `card_type`.
- Autopayments use `payment_method_id` — no user interaction required (безакцептное списание).
- **YooKassa has NO API endpoint to delete a saved payment method.** Unbinding is accomplished by deleting your own DB record of the `payment_method_id`. Once your app stops using an ID, the card is effectively unbound.
- Payment methods that support saving: bank card (Visa, MC, Mir), YooMoney wallet, Mir Pay, SberPay, T-Pay, FPS.
- YooKassa sends a `payment_method.active` webhook notification when a payment method is successfully saved.

**Autopayment merchant requirements (РФ):**
- You must present the user with an "оферта" (terms of service / offer agreement) that specifies: (1) the amount to be charged, (2) the charging frequency, and (3) how to disable autopayments.
- You must obtain explicit user consent before enabling autopayments — the toggle is sufficient consent mechanism IF the UI states the amount and frequency clearly ("Спишется за 3 дня до конца · сумма = стоимость текущего тарифа").
- The footer in `CardSheet` already says "Данные карты хранятся на стороне платёжного провайдера. Мы видим только последние 4 цифры." This is the right disclosure.
- **No HMAC webhook verification for YooKassa** (unlike Stripe) — security model is IP allowlist (`YOOKASSA_TRUSTED_IPS`) + status re-fetch. The existing `verify_yookassa_ip` guard covers this.

### Autopay Consent UI Requirements

The `CardSheet` mock `ToggleRow` label "Авто-продление абонемента · Спишется за 3 дня до конца" satisfies the disclosure requirement IF the charge amount is also shown. The backend `PATCH /client/membership/autopay` response should return `{enabled, next_charge_date, next_charge_amount_kopecks}` so the PWA can display "Следующее списание: 15 мая · 2 500 ₽." This is table stakes for a legally compliant autopay UI in РФ.

**Caveat:** Autopayments via YooKassa require the merchant to have autopayments enabled in their YooKassa account settings (this is not the default — it requires a manager request). This is an OPERATOR-PENDING item, not a code blocker.

---

## Complexity Assessment

### Card-on-file + Autopay — OVERALL HIGH

- **New DB table needed:** `client_payment_methods` (`id, client_id FK, payment_method_id VARCHAR, type, last4, first6, card_type, expiry_month, expiry_year, is_active, created_at`) — Alembic migration required.
- **Webhook extension:** The `payment.succeeded` handler must optionally save the `payment_method` object when `payment.save_payment_method is True`. Single branch addition, no fork.
- **New ARQ cron:** `run_autopay_renewals` — must run after `expire_memberships` (06:05) but before the membership is marked expired. Suggested time: 06:10 MSK. Uses `unique=True` for idempotency.
- **Failure/retry logic:** First-pass MVP can disable-on-first-failure. Retry logic is a v2.3 improvement.
- **Blocked by YooKassa account settings:** Autopayments must be enabled at the YooKassa account level. Mark as OPERATOR-PENDING at close.

### Booking Reschedule — MEDIUM

- **No new table or migration needed** (unless adding `reschedule_count` column — optional).
- **New endpoint:** `POST /client/bookings/{id}/reschedule` — ~50-80 lines of service code.
- **Reuses:** existing available-slots endpoint, existing partial-UNIQUE race guard, existing booking FSM.
- **New audit event:** `booking_rescheduled` — must be added to `LOCKED_AUDIT_EVENTS` before first callsite (INFRA-15 discipline).
- **Key risk:** Atomicity — must not call `cancel` as a sub-operation. Single transaction cancel+insert.

### Weekly Activity — LOW

- **No new table or migration needed.**
- **New read endpoint:** `GET /client/activity/weekly` — ~20-30 lines of SQL aggregate over `visits`.
- **No external dependencies.**
- **Weeks in Europe/Moscow:** Monday = start of week (Russian locale convention). Use `date_trunc('week', current_date AT TIME ZONE 'Europe/Moscow')` for the Monday boundary.
- **If adding minutes:** requires a join to `pt_sessions` via `bookings.slot_id`; `pt_sessions` does not currently store `duration_minutes`, so minutes must be derived from `trainer_availability_slots.end_time - start_time` if the visit has an associated booking. This adds a multi-join chain. MVP ships without minutes; binary visit_count per day is sufficient.

---

## Competitor Feature Analysis

| Feature | YClients (РФ) | Mindbody (US) | Our Approach |
|---------|--------------|---------------|--------------|
| Saved card display | Shows last-4, delete option | Shows last-4, multiple cards | Single card (one active per client); same display format |
| Autopay toggle | Per-service type | Global + per-service | Per-membership only (v2.2); PT bookings excluded |
| Card binding flow | At first purchase | At first purchase OR dedicated add-card | At first purchase in v2.2; zero-amount binding deferred |
| Reschedule cutoff | Configurable (typically 12-24h) | Configurable per class | Fixed 6h (matches existing cancel window, no new config) |
| Reschedule: same vs any trainer | Typically same class type, any instructor | Any available slot | Same-trainer only in v2.2 |
| Reschedule count limit | Typically 1-2 per booking | Varies | No limit in v2.2 MVP (add if abuse occurs) |
| Weekly activity | Visit count bars + active minutes | Detailed workout log | Visit count bars (v2.2); minutes optional in v2.3 |
| Activity granularity | Day-level | Day-level | Day-level (Mon–Sun, Europe/Moscow week) |

---

## Sources

- YooKassa official docs — Autopayments: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics
- YooKassa official docs — Pay with saved method: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved
- YooKassa official docs — Save during payment: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment
- YooKassa autopayment support page: https://yookassa.ru/docs/support/payments/extra/autopayment
- BEAT81 cancellation policy (fitness class reschedule cutoff 12h): https://support.beat81.com/en/articles/431384-how-to-cancel-or-change-your-workout
- Subscription billing best practices: https://www.subscriptionflow.com/2026/01/best-practices-for-recurring-billing-gym-memberships/
- Apple Fitness weekly summary UX: https://support.apple.com/guide/iphone/see-your-activity-summary-iph4c34a8a95/ios
- Codebase: `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — `CardSheet` implementation (line 324)
- Codebase: `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` — reschedule + cancel views
- Codebase: `apps/client-pwa/src/screens/ProfileScreen.jsx` — `PROFILE_FEATURE_FLAGS`, weekly activity card (line 267)
- Codebase: `apps/client-pwa/src/data/index.js` — mock shapes for CALENDAR, BUSY_SLOTS, TIME_SLOTS
- `.planning/PROJECT.md` — v2.2 milestone scope, "Key context" section

---

*Feature research for: v2.2 Membership self-service depth (card-on-file + autopay, booking reschedule, weekly activity)*
*Researched: 2026-06-03*
