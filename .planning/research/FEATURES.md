# Feature Landscape: v2.0 Client PWA — Client-Facing API

**Domain:** Gym member self-service PWA + client-scoped REST API over existing gym CRM
**Researched:** 2026-05-29
**Confidence:** HIGH — based on direct codebase inspection of existing backend domains,
PWA mock data shapes, screen implementations, and established backend patterns

---

## Context

This is a subsequent milestone. The backend (v1.11) exposes ONLY staff (owner/reception) endpoints.
Gym members ("clients") are records managed BY staff. v2.0 adds:
- A new client-facing authentication principal (phone + OTP, isolated from staff JWT)
- Client-scoped REST endpoints over existing domains (memberships, bookings, visits, pt_sessions,
  payments, plans, trainers, schedule)
- PWA screen wiring (Home, Book, Profile, Plans, Checkout, QR) to the real backend

**Client data-scoping invariant:** Every client-scoped endpoint filters by `client_id` from the
authenticated session. Cross-client data access is impossible — this is an ownership guard,
not RBAC. Violations are anti-oracle (identical response regardless of reason).

**Out-of-scope screens stay on mock data:** Chat, Referral, Trainer reviews/ratings,
Notification inbox, Gym-info-from-backend. These are NOT researched as features below.

---

## 1. Client Identity and Onboarding

**Backing domain:** `app/modules/auth/` (OTP infrastructure), `app/modules/clients/` (client records)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Phone + OTP login | Industry standard for RF/CIS gym apps (no email-only). Members expect SMS or Telegram. Staff auth already has Telegram OTP infra (`otp_codes` table). | Medium | New `POST /api/v1/client/auth/otp/request` + `POST /api/v1/client/auth/otp/verify`. Reuse existing `otp_codes` table schema. Phone normalization: E.164 `+7XXXXXXXXXX` strip spaces/dashes/parens. |
| Client record matching by phone | The `clients` table has `phone` + partial-unique `WHERE deleted_at IS NULL`. Matching is the join between the OTP caller and an existing client record. | Medium | Match `clients.phone` to normalized phone from OTP request. If match found: issue client-scoped JWT. If no match: uniform 200 anti-oracle response (see below). |
| Anti-oracle for unknown phone | Standard RF/CIS security baseline. Server must NOT reveal whether a given phone number belongs to a registered client. | Medium | `POST /api/v1/client/auth/otp/request` returns identical 200 `{"message": "Если номер зарегистрирован, OTP отправлен"}` for both known and unknown phones. `_constant_time_floor` discipline (already used in staff auth service). No `client_not_found` error code. |
| Client `/me` endpoint | Every client-authenticated flow needs to know their own profile — name, phone, email, client_id. The PWA ProfileScreen displays `userName`, phone, email. | Low | `GET /api/v1/client/me` returns: `{id, first_name, last_name, phone, email, created_at}`. Staff fields (telegram_user_id, notes, deleted_at) are NOT returned to the client. |
| Client JWT isolation from staff JWT | Staff access tokens (`sz_access` cookie) must not grant access to client endpoints, and vice versa. | Medium | Client session uses a separate JWT claim discriminator (e.g. `"principal": "client"` in payload) and a separate `cc:client:session:` Redis namespace. Staff `require_permission` guards reject client tokens. |
| Refresh + logout | Session lifecycle. PWA settings has a "Выйти из аккаунта" button. | Low | `POST /api/v1/client/auth/refresh` + `POST /api/v1/client/auth/logout`. Reuse refresh-rotation family pattern from staff auth. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Telegram OTP channel | Telegram already primary notification channel; clients with bound telegram can receive OTP there without SMS costs. `clients.telegram_user_id` already stored. | Medium | Optional channel field on request: `{"phone": "+79161234567", "channel": "telegram"}`. Fall back to SMS if no telegram_user_id. Requires sending OTP via Telegram bot (existing bot infra). |
| OTP rate-limiting (anti-spam) | Prevents phone enumeration via OTP flood. Already in staff auth via `cc:otp:rate:`. | Low | Reuse existing pattern — per-phone 60s resend cooldown via `otp_codes` row, per-IP rate limit. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Client self-registration (creating a new client record) | Clients at a physical gym are enrolled by reception; self-registration bypasses the real-world onboarding flow and would create unvalidated client records. | Staff creates client record; client logs in after being enrolled. Unknown phone → anti-oracle. |
| Email/password login for clients | Adds a credential management burden for both client and staff. RF gym members expect phone-based auth. | Phone + OTP only in v2.0. |
| Returning `client_not_found` error | Reveals phone-number roster to potential adversaries. | Uniform 200 anti-oracle response always. |

**Client identity read shape (GET /api/v1/client/me response):**
```
{
  id: uuid,
  first_name: string,
  last_name: string | null,
  phone: string,          // normalized E.164
  email: string | null,   // required for checkout; may be null
  created_at: iso_datetime
}
```

---

## 2. "My Membership" — Home View

**Backing domain:** `app/modules/memberships/` (Membership + MembershipPlan + MembershipFreezePeriod)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Active membership card | The HomeScreen subscription card is the primary UI element — plan name, days remaining, end_date, progress bar, status (active/frozen/expiring/expired). Mock: `getSubInfo(tweaks.subState)`. | Low | `GET /api/v1/client/memberships/active` returns the resolver result: single active or frozen membership for this client. Status: `active`, `frozen`, `expired`, `cancelled`. |
| Days remaining calculation | Client sees "14 дней до 15 мая" not raw timestamps. Calculation is `end_date - today (Europe/Moscow)`. | Low | Backend returns `end_date` (date, not datetime). PWA computes days_remaining client-side using date-fns + Europe/Moscow. Alternatively backend can return `days_remaining` as a derived field. |
| Freeze status display | HomeScreen has warn tone for expiring, danger for expired, shows frozen state. MembershipFreezePeriod already tracked. | Low | Active membership response includes `freeze_status: {is_frozen: bool, frozen_since: date | null, freeze_days_remaining: int | null}`. Derived from open freeze period WHERE `ended_at IS NULL`. |
| Expiring-soon banner | HomeScreen shows "Продлить со скидкой 15%" when `sub.tone === 'warn'`. Backend already sends push notifications at 7d/3d/1d. | Low | PWA shows warn banner if `days_remaining <= 7`. Client-side threshold, no separate endpoint. |
| No active membership state | HomeScreen empty state: "Записей пока нет / Запишись на первую тренировку". | Low | `GET /api/v1/client/memberships/active` returns 404 or `{data: null}`. PWA handles empty state. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Membership history | ProfileScreen has no membership history tab in mock, but it is implied by the "С нами 2 года" display. | Medium | `GET /api/v1/client/memberships?status=expired` returns paginated list of past memberships via `previous_membership_id` chain. Low priority for v2.0. |
| Freeze days remaining in card | Clients want to know how many freeze days they can still use. `freeze_days_limit_snapshot` is on Membership, open period is in MembershipFreezePeriod. | Low | Include in active membership response: `freeze_days_limit: int, freeze_days_used: int`. Computed from sum of closed freeze periods. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Client-initiated freeze/unfreeze | The PWA ProfileScreen has a "Заморозить" button, but the freeze FSM requires staff authorization (reception or owner). Allowing client self-freeze changes the business model. | Show freeze status; redirect to "позвони на ресепшен". Keep freeze as staff-only action in v2.0. |
| Membership cancel via PWA | No cancel button in any screen mock. | Cancel stays staff-only. |

**Active membership read shape (GET /api/v1/client/memberships/active):**
```
{
  id: uuid,
  plan_id: uuid,
  plan_name: string,        // plan_name_snapshot
  status: "active" | "frozen" | "expired" | "cancelled",
  start_date: date,
  end_date: date,           // inclusive
  price_kopecks: int,       // price_kopecks_snapshot
  duration_days: int,       // duration_days_snapshot
  freeze_days_limit: int,   // freeze_days_limit_snapshot
  freeze_days_used: int,    // computed from closed freeze periods
  is_frozen: bool,
  frozen_since: date | null
}
```

---

## 3. Bookings — Self-Booking + View + Cancel

**Backing domain:** `app/modules/bookings/`, `app/modules/schedule/`, `app/modules/pt_packages/`

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Available trainer slots (calendar) | BookScreen Step 1+2: date picker + trainer list with available slots. Mock uses `CALENDAR` (21-day window) + `BUSY_SLOTS` per trainer. | Medium | `GET /api/v1/client/schedule/available-slots?date=YYYY-MM-DD&trainer_id=<optional>` returns trainer availability slots WHERE `status='available'` AND no confirmed booking AND slot date >= today. Paginated by date, grouped by trainer. |
| Trainer catalog for booking | BookScreen Step 2: trainer list with name, spec, price, experience. Shown only when selecting a slot. | Low | `GET /api/v1/client/trainers` returns active trainers with name, specialization, price_per_session_kopecks, experience_years. Staff-side trainers module, client-scoped view. |
| Slot time display grouped by period | BookScreen Step 3: slots grouped into morning/day/evening. Mock: `TIME_SLOTS` + `BUSY_SLOTS`. | Low | Response includes `start_time`, `end_time` per slot. PWA groups client-side. Backend only needs to return available (not busy) slots. |
| Book a slot using PT package credit | BookScreen confirm step: "К оплате: 2 200 ₽ · спишется с привязанной карты". The existing booking model requires a `pt_package_id` — every booking deducts one session. | High | `POST /api/v1/client/bookings` body: `{slot_id, pt_package_id}`. Service: (1) validate client owns pt_package, (2) package has sessions_remaining > 0, (3) slot is available, (4) insert booking with partial-UNIQUE race guard on `(slot_id) WHERE status='confirmed'`. Returns `BookingResponse` with slot details. |
| My upcoming bookings | HomeScreen "Ближайшая запись" card: trainer name, date/time, focus. ProfileScreen has bookings list. Mock: `UPCOMING_BOOKING`. | Low | `GET /api/v1/client/bookings?status=confirmed&upcoming=true` returns paginated bookings for this client_id with slot join (trainer name, start_time, end_time). |
| Cancel my booking within policy | HomeScreen swipe-to-cancel on upcoming card. BookingManageSheet. Policy: "Отменить бесплатно не позднее чем за 6 часов". | Medium | `POST /api/v1/client/bookings/{booking_id}/cancel` — validates: (1) booking belongs to this client (ownership guard), (2) status == 'confirmed', (3) policy window check (slot start - now > 6h → full cancel; else partial credit deduction). Returns updated booking. |
| Booking history (past bookings) | ProfileScreen trainings/visits tabs. | Low | `GET /api/v1/client/bookings?status=completed,cancelled,no_show` with date range filter. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Trainer search/filter in client API | BookScreen has search bar + FilterChips (All / Top / До 2200₽). | Low | `GET /api/v1/client/trainers?search=&min_rating=4.9&max_price=220000` — query params, server-side filter over trainers table. |
| Slot availability dot on calendar days | BookScreen calendar: `hasSlot` per day. | Low | `GET /api/v1/client/schedule/available-days?from=YYYY-MM-DD&to=YYYY-MM-DD` returns array of dates with at least one available slot. Used to render dots on calendar. |
| "In development" placeholder for trainer ratings | TRAINERS mock has `rating: 4.9, reviews: 128` but Trainers domain is catalog-only — no ratings/reviews backend. | None | Return `rating: null, review_count: null` in trainer response. PWA hides rating widget when null. Anti-feature: do NOT fabricate ratings or add a ratings domain in v2.0. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Client booking without a PT package | BookScreen implies PT package ownership is required. Existing booking model requires `pt_package_id NOT NULL`. Allowing "pay at the door" bookings requires a new payment path. | Require an active PT package. If none: surface "Нет доступных занятий — купи пакет" prompt leading to Checkout. |
| Client-initiated no_show marking | No-show transitions are staff/cron-only (`mark_no_show_bookings` ARQ cron at 23:10). | Keep cron-managed. |
| Cancellation credit as money refund | Cancellation outside policy window = no refund (or 50% deduction as shown in mock). | Return policy display string to client; refunds are staff-initiated in billing domain. |

**Booking write shape (POST /api/v1/client/bookings request body):**
```
{
  slot_id: uuid,
  pt_package_id: uuid
}
```

**Booking read shape (response item):**
```
{
  id: uuid,
  status: "confirmed" | "cancelled" | "no_show" | "completed",
  slot: {
    id: uuid,
    start_time: iso_datetime,
    end_time: iso_datetime,
    trainer: { id: uuid, name: string, specialization: string }
  },
  pt_package_id: uuid,
  cancelled_at: iso_datetime | null,
  cancel_reason: string | null,
  created_at: iso_datetime
}
```

---

## 4. Self Check-In via QR

**Backing domain:** `app/modules/visits/` (Visit model, UNIQUE(client_id, gym_date))

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| QR code generation for client | QRSheet shows a QR code. The existing Telegram bot check-in already proves the concept (`/checkin` command). Client needs a web-equivalent. | Medium | `GET /api/v1/client/visits/qr-token` returns a short-lived signed token (HMAC-SHA256 or JWT, 60-120s TTL) encoding `{client_id, issued_at}`. PWA renders this as a QR code client-side (e.g. `qrcode.js`). Token is NOT a static value — it rotates to prevent screenshot replay. |
| QR token verification and check-in | The backend (or a turnstile reader) POSTs the scanned token to record the visit. Existing Telegram checkin uses `channel='telegram_bot'`. | Medium | `POST /api/v1/client/visits/self-checkin` body: `{token: "<signed_token>"}`. Service: (1) verify token signature + expiry, (2) extract client_id from token, (3) call existing visit creation logic with `channel='client_qr'` (new channel literal), (4) DB-level UNIQUE(client_id, gym_date) enforces 1/day. Returns visit row or 409 if already checked in today. |
| 1-per-day enforcement | Visit model has `gym_date STORED GENERATED` column + `UNIQUE(client_id, gym_date)`. Already race-safe. | Low | Reuse existing DB constraint. Service catches `uq_visits_client_id_gym_date` IntegrityError — returns 409 `already_checked_in_today`. |
| Cannot check in for another client | QR token must be client-scoped and tamper-proof. A screenshot of another client's QR must not work. | Medium | Token payload includes `client_id`. HMAC-SHA256 with server secret makes payload unforgeable. Token TTL 60-120s prevents screenshot replay. `POST .../self-checkin` verifies signature before any DB lookup. |
| Active membership required | Cannot check in without an active membership (existing visit service validates this via `ActiveMembershipResolver`). | Low | Same guard already exists for staff check-in. Client gets 422 `no_active_membership` if they try to check in expired. |
| Success UX (QRSuccess screen) | QRSheet has `QRSuccess` state: "Вход зафиксирован · Хорошей тренировки". Shows "14-й визит". | Low | `POST .../self-checkin` response includes `{visit_id, checked_in_at, visit_count_today_month}` to populate the success screen. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| QR auto-refresh before expiry | PWA refreshes the QR token silently before it expires (e.g. at 45s mark of a 60s TTL), so the client doesn't have to tap anything. | Low | Client-side timer polls `GET .../qr-token` before expiry. No server change required. |
| "Screen brightness to max" prompt | QRSheet shows "Яркость на максимум" hint. | None | Client-side only. No backend dependency. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Static QR code (permanent client ID in URL) | Easy to implement but allows screenshot sharing — one client can check in another client. | Short-lived HMAC-signed token with client_id bound inside. |
| QR code that encodes the full client UUID | UUID alone has no tamper protection. | Signed token wrapping the UUID + issued_at. |
| Multi-visit per day via QR | Business rule: 1 visit per gym_date. Already DB-enforced. | Return 409 `already_checked_in_today` with a friendly message. |
| New `visits.channel` values requiring migration | Adding `'client_qr'` requires an Alembic migration to widen the CHECK constraint on `channel`. | Plan the Alembic migration as part of the visit check-in phase. The Check constraint currently has `IN ('reception', 'telegram_bot')` — needs to add `'client_qr'`. |

**QR token endpoint shape:**
```
GET /api/v1/client/visits/qr-token
Response: {
  token: string,        // HMAC-signed JWT, 120s TTL
  expires_at: iso_datetime,
  client_id: uuid       // for display: "Клиент #4821"
}

POST /api/v1/client/visits/self-checkin
Body: { token: string }
Response: {
  visit_id: uuid,
  checked_in_at: iso_datetime,
  gym_date: date,       // Europe/Moscow date
  visit_number: int     // ordinal for "14-й визит" display
}
```

---

## 5. Self-Service Checkout

**Backing domain:** `app/modules/online_payments/`, `app/modules/memberships/`, `app/modules/pt_packages/`

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Membership plan purchase via ЮKassa | PlansSheet → CheckoutSheet. Client selects a plan and pays online. Existing `online_payments` module handles redirect-based ЮKassa flows. | High | `POST /api/v1/client/checkout/membership` body: `{plan_id, confirmation_type: 'redirect'}`. Orchestrates existing `online_payments` service. Returns `{payment_id, confirmation_url, status: 'pending'}`. PWA redirects client to ЮKassa. |
| Membership renewal | HomeScreen "Продлить" button. PlansSheet → CheckoutSheet. Same flow as purchase but targets the existing membership's renewal chain (`previous_membership_id`). | High | Same endpoint or `POST /api/v1/client/checkout/membership/renew` with `{plan_id}`. Service resolves current active membership + creates renewal via existing `renew_membership` logic, triggered on `payment.succeeded` webhook. |
| PT package purchase | BookScreen checkout: "Тренировка с Аней · 2 200 ₽". PT package plans catalog + buy flow. | High | `POST /api/v1/client/checkout/pt-package` body: `{pt_package_plan_id, confirmation_type: 'redirect'}`. Orchestrates existing `online_payments` pt_package path. |
| Client email required for 54-ФЗ fiscal receipt | `online_payments` service already enforces `client_email_required_for_online_payment` 422 if `clients.email IS NULL`. The fiscal receipt path (ЮKassa "Чеки от ЮKassa") requires an email. | Medium | Checkout endpoint checks `client.email`. If null: return 422 `email_required` with `{field: "email", message: "Введи email для чека"}`. PWA surfaces an inline email input field before proceeding. Client can update their email at checkout time — `PATCH /api/v1/client/me` updates `clients.email`. |
| Client email self-update | Client must be able to add/update their email at checkout to satisfy the fiscal receipt requirement. ProfileScreen has "Личные данные" entry. | Low | `PATCH /api/v1/client/me` body: `{email: string}`. Validates email format. Updates `clients.email`. |
| ЮKassa redirect flow | After creating payment, client is redirected to ЮKassa hosted page. Backend activation happens on `payment.succeeded` webhook (existing flow). PWA shows "ожидаем подтверждение" on redirect-back. | Low | Existing webhook handler already processes this. Client-facing redirect-back URL can be `{pwa_base}/checkout/pending?payment_id={id}`. PWA polls `GET /api/v1/client/checkout/{payment_id}/status` until `status == 'succeeded'`. |
| Payment status polling | Client needs to know when membership is activated after ЮKassa redirect. | Low | `GET /api/v1/client/checkout/{payment_id}/status` returns `{payment_id, status: 'pending' | 'succeeded' | 'canceled', membership_id: uuid | null}`. Anti-oracle: returns same response whether payment_id belongs to this client or not (ownership-guarded 404 on mismatch). |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| QR confirmation type | CheckoutSheet mock shows card/Apple Pay options. ЮKassa QR (`confirmation_type='qr'`) is already supported in existing `online_payments`. | Low | Accept `confirmation_type: 'qr'` in checkout request body. Return `qr_code_url` in addition to `confirmation_url`. |
| Promo code field | CheckoutSheet has a promo code input. No promo code domain exists in the backend. | Medium | Anti-feature: do NOT add a promo code domain in v2.0. Show the promo code UI but wire to a placeholder 422 `promo_codes_not_supported` response. Or simply remove the field from the wired checkout. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Cash payment from client PWA | Physical cash is handled by reception. No self-service cash path makes sense. | Online only (ЮKassa). |
| Client-initiated refunds | CheckoutSheet error state shows "Деньги не списали" for slot-busy scenario. But actual refunds (`online_refunds`) are staff-initiated. | Keep refunds as staff-only. Surface "обратитесь на ресепшен" for refund requests. |
| Storing card data in clubcore | CheckoutSheet shows "Visa •••• 4821 · Срок до 09/28" as a saved card. ЮKassa handles card storage on their side; clubcore never stores card data. | PWA saves the last-4 display from a ЮKassa payment response field for display only — no actual card storage. |
| Promo code backend domain | No promo code table exists. Adding one is net-new business domain, out of scope. | Placeholder UI only, or remove from wired checkout. |

**Checkout write shape (POST /api/v1/client/checkout/membership):**
```
Request: {
  plan_id: uuid,
  confirmation_type: "redirect" | "qr"
}
Response: {
  payment_id: uuid,             // internal OnlinePayment.id
  yookassa_payment_id: string,
  status: "pending",
  confirmation_url: string | null,  // redirect URL
  qr_code_url: string | null        // ЮKassa QR
}
```

**Email dependency note:** `clients.email` is nullable. Checkout MUST check it. The 54-ФЗ path in
the existing `online_payments` service already enforces this via `FIS-05 email gate` returning
422 `client_email_required_for_online_payment`. The client API should surface this as a pre-check
with a field-level error so PWA can show an inline email input before the payment is attempted.

---

## 6. History Views

**Backing domain:** `app/modules/visits/`, `app/modules/pt_sessions/`, `app/modules/payments/` + `app/modules/online_payments/`

### Table Stakes

#### 6a. Visit History (ProfileScreen "Визиты" tab)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| List of past visits | Mock: `VISIT_HISTORY` with date, time, duration, kind ("Самостоятельно" vs "С Аней Соколовой"). | Low | `GET /api/v1/client/visits?page=1&page_size=20` — client-scoped, ordered `checked_in_at DESC`. Returns: `{items: [{id, checked_in_at, gym_date, channel, has_pt_session: bool}], total, page, page_size}`. |
| Month summary counter | ProfileScreen shows "14 посещений" for this month. | Low | Include `month_count` in response or separate `GET /api/v1/client/visits/summary` endpoint. |
| Visit "kind" display | Mock distinguishes self-visit vs training visit. | Low | `has_pt_session: bool` in visit item. If true, PWA fetches trainer name from pt_sessions. Or backend joins and returns `trainer_name: string | null`. |

**Visit history read shape:**
```
items: [{
  id: uuid,
  checked_in_at: iso_datetime,
  gym_date: date,              // Europe/Moscow date
  channel: "reception" | "telegram_bot" | "client_qr",
  trainer_name: string | null  // null if no pt_session for this visit
}]
```

#### 6b. Training History (ProfileScreen "Тренировки" tab)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| List of recorded PT sessions | Mock: `TRAINING_HISTORY` with trainer, focus, notes. The `pt_sessions` table has `trainer_id`, `booking_id`, `notes`, `performed_at`. | Low | `GET /api/v1/client/pt-sessions?page=1&page_size=20` — client-scoped via `pt_packages.client_id` → `pt_sessions.pt_package_id`. Returns `{items: [{id, performed_at, trainer_name, focus_area, notes}], total, page, page_size}`. |
| Trainer info per session | Mock shows trainer initials + colors. | Low | JOIN `trainers` on `trainer_id` in response. Return `trainer_name`, `trainer_specialization`. |
| Session notes display | Mock: "Хорошо потянули становую, добавили вес". `pt_sessions.notes` is already stored. | Low | Include `notes` field (max 500 chars per CHECK constraint). |

**Training history data-scoping note:** `pt_sessions` has `pt_package_id` FK. `pt_packages` has
`client_id`. Client access is validated via `pt_packages.client_id = session_client_id`. NO direct
`client_id` on `pt_sessions` — query joins through `pt_packages`.

**Training history read shape:**
```
items: [{
  id: uuid,
  performed_at: iso_datetime,
  trainer_name: string,
  trainer_specialization: string,
  focus_area: string | null,   // maps to pt_sessions focus/notes header
  notes: string | null,
  pt_package_id: uuid
}]
```

#### 6c. Purchase History (ProfileScreen "Покупки" tab)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Unified payment list | Mock: `PURCHASE_HISTORY` with kinds (sub/training/shop) and amounts. Includes refunds. The `payments` table is the append-only ledger: `payment_method`, `subject_kind`, `amount_kopecks` (positive = charge, negative = refund). | Medium | `GET /api/v1/client/payments?page=1&page_size=20` — client-scoped. Query `payments` WHERE `client_id = session_client_id`. No shop purchases in real backend (shop is out of scope). Returns: `{items: [{id, paid_at, subject_kind, description, amount_kopecks, payment_method}], total, page, page_size}`. |
| Refund entries | Mock has `status: 'refund', amount: -1100`. Payments ledger stores refunds as negative `amount_kopecks` rows with `subject_kind` annotated. | Low | Include negative-amount rows. PWA detects `amount_kopecks < 0` as refund display. |
| Monthly grouping + total spend | Mock shows month headers + "Потрачено всего" summary with sub/trainer/shop breakdown. | Low | Client-side aggregation from the paginated list, or backend `GET /api/v1/client/payments/summary` returning monthly totals by subject_kind. |

**Purchase history data-scoping note:** `payments.client_id` is a direct FK. Client access is
straightforward ownership guard on `client_id`. Note: `shop` kind exists in mock but has no backend
domain. Response should not return shop-kind rows since none exist — or filter them client-side.

**Money convention:** All amounts in integer kopecks. PWA formats with `formatMoney(kopecks)` →
`ru-RU RUB` string with NBSPs. Server NEVER returns formatted strings, only integer kopecks.

**Purchase history read shape:**
```
items: [{
  id: uuid,
  paid_at: iso_datetime,
  subject_kind: "membership" | "pt_package" | "pt_session",
  payment_method: "cash" | "online",
  amount_kopecks: int,   // negative = refund
  description: string,   // e.g. "Месячный абонемент · 30 дней"
  yookassa_payment_id: string | null  // for receipt link
}]
```

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Receipt / fiscal receipt link | CheckoutDone shows "Посмотреть чек". `fiscal_receipts` table exists. | Medium | Include `receipt_url: string | null` in payment history item if `fiscal_receipts` row exists and `status = 'succeeded'`. Low priority for v2.0. |
| Date range filter on history | Useful for longer history views. | Low | `?from=YYYY-MM-DD&to=YYYY-MM-DD` query params on all history endpoints. |

### Anti-Features

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Shop purchase history | Shop items (`kind: 'shop'` in mock) have no backend domain. | Filter out shop rows. Return only membership + pt_package + pt_session payment rows. |
| Exposing other clients' payment data | Ownership guard must be applied at query level, not application level. | WHERE clause: `payments.client_id = :session_client_id` — never fetch all then filter in Python. |

---

## Feature Dependencies

```
Client auth (phone OTP → client JWT)
  └──required by──> all other client-scoped endpoints

GET /api/v1/client/me
  └──required by──> Checkout (email check before payment)
  └──required by──> QR token (client_id binding)

Active membership
  └──required by──> QR self-checkin (no membership → 422)
  └──required by──> HomeScreen membership card

PT package ownership
  └──required by──> self-booking (pt_package_id on booking)
  └──required by──> training history (pt_sessions via pt_packages)

Checkout (ЮKassa redirect)
  └──required by──> membership purchase/renewal flow
  └──required by──> PT package purchase flow
  └──depends on──> clients.email NOT NULL (54-ФЗ gate)
  └──depends on──> existing webhook handler (no change needed)

PATCH /api/v1/client/me (email update)
  └──required by──> checkout email gate unblock

Alembic migration: visits.channel widened
  └──required by──> QR self-checkin (new 'client_qr' channel)
```

---

## MVP Recommendation

Priority order for v2.0:

**Phase 1 — Client auth foundation (blocker for everything):**
- Phone OTP request + verify (with anti-oracle)
- Client JWT (isolated from staff session)
- GET /api/v1/client/me

**Phase 2 — Home screen data (highest user-visible impact):**
- GET /api/v1/client/memberships/active
- GET /api/v1/client/trainers (for booking)
- GET /api/v1/client/schedule/available-slots
- GET /api/v1/client/bookings (upcoming + past)

**Phase 3 — QR self check-in:**
- GET /api/v1/client/visits/qr-token
- POST /api/v1/client/visits/self-checkin
- Alembic migration: visits.channel += 'client_qr'

**Phase 4 — Checkout (ЮKassa):**
- PATCH /api/v1/client/me (email update)
- POST /api/v1/client/checkout/membership
- POST /api/v1/client/checkout/pt-package
- GET /api/v1/client/checkout/{payment_id}/status

**Phase 5 — History + booking write:**
- POST /api/v1/client/bookings (self-booking)
- POST /api/v1/client/bookings/{id}/cancel
- GET /api/v1/client/visits (history)
- GET /api/v1/client/pt-sessions (training history)
- GET /api/v1/client/payments (purchase history)

**Defer from v2.0 MVP:**
- Membership history (list of past memberships)
- Receipt/fiscal receipt link in history
- Date range filters on history
- Telegram OTP channel (SMS first, Telegram as follow-on)
- Promo code field (placeholder UI only)

---

## Out-of-Scope Screens (mock-data only, NOT researched as features)

These screens remain on mock data in v2.0. The PWA should show an "in development" placeholder:

| Screen | Reason Out of Scope |
|--------|---------------------|
| Chat (messaging) | No backend domain; requires staff-side admin-web changes (frozen) |
| Referral | No referral domain exists |
| Trainer reviews/ratings | Trainers domain is catalog-only; ratings would be a new domain |
| Notification inbox | Notifications are push-only (Telegram/email); no client-readable inbox exists |
| Gym info from backend | Gym details are static content; no backend domain for hours/address/photos |

---

## Sources

- `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` — v2.0 milestone scope, in/out-of-scope decisions
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/data/*.js` — mock data shapes for all PWA screens
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/HomeScreen.jsx` — subscription card, upcoming booking, QR button, notifications feed
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/BookScreen.jsx` — 3-step booking flow, cancellation policy display
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/ProfileScreen.jsx` — profile card, visits/trainings/purchases tabs, settings
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/QRSheet.jsx` — QR display, scan animation, success state
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — payment flow, card picker, promo code, error states
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/memberships/models.py` — Membership, MembershipPlan, MembershipFreezePeriod ORM
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/visits/models.py` — Visit ORM, gym_date STORED, channel constraint
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/bookings/models.py` — Booking ORM, partial UNIQUE, FSM statuses
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/online_payments/models.py` — OnlinePayment ORM, confirmation_type, fiscal gate
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/clients/models.py` — Client.phone, Client.email nullable, Client.telegram_user_id
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/pt_packages/models.py` — PtPackage sessions_remaining, client_id
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/pt_sessions/models.py` — PtSession, booking_id, notes (max 500)
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/` — OTP infrastructure, anti-oracle patterns, `_constant_time_floor`
- CLAUDE.md conventions: money in kopecks, dates in Europe/Moscow, anti-oracle discipline, pagination `{items, total, page, pageSize}`

---

*Feature research for: v2.0 Frontend Integration — Client PWA (clubcore gym CRM)*
*Researched: 2026-05-29*
