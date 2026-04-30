# Feature Landscape — Gym / Fitness Club Management

**Domain:** Gym / fitness club management CRM (tracker-room + group classes + personal training)
**Target market:** Russia / CIS, small-to-mid single-club operators (later multi-club)
**Researched:** 2026-04-21
**Confidence:** MEDIUM-HIGH (domain is mature and well-documented; training data covers 1Fit, Mindbody, FitBase, TeamUp, ClubManager, Glofox, Zen Planner). Direct scraping of current vendor pages was blocked in this session — vendor feature lists below reflect training-data knowledge and industry-standard modules rather than freshly verified 2026 screenshots. Nothing here should be read as "vendor X literally has screen Y labelled Z today"; read it as "this is the standard module set every vendor in this space converges on."

---

## 0. How to Read This Document

This file exists to seed **realistic mocks and screens** for SportZal Adminka (frontend-only, RU-first, mock data, shadcn/ui + reui.io). It is not a product spec. Everything here should be:

- **Pickable** — you can lift a field list straight into a TypeScript type.
- **Mockable** — every screen listed can be filled with plausible fake data.
- **Localized** — Russian domain terms are preserved in *italics* where the Russian word is what receptionists actually say out loud (*абонемент*, *заморозка*, *касса*). English is used for the structural/CRUD vocabulary.

Scope boundaries repeated from `PROJECT.md`:
- Two roles only: **Owner/Admin** vs **Reception/Manager**, switched via UI toggle (no login).
- No real backend, no real payments, no SMS/email sending, no 54-ФЗ fiscal integration — only the *UI affordances* that imply those systems exist.
- Russian UI, English code/docs.

---

## 1. Clients & Memberships (*Клиенты и абонементы*)

This is the heart of every gym CRM. Reception spends 80% of their day on this module. Owner spends most reporting time here too.

### 1.1 Client record — canonical field list

Split into "must-have for v1 mock" vs "nice to show on detail screen".

**Core identity (must-have):**
| Field | Type | Notes |
|---|---|---|
| `id` | string (uuid) | Internal |
| `lastName` / `firstName` / `middleName` | string | *Фамилия / Имя / Отчество* — three separate fields, Russian clubs expect *отчество* optional but present |
| `phone` | string (E.164-ish, RU default +7) | **Primary identifier** for reception search. Unique-ish. |
| `email` | string | Optional but common |
| `birthday` | date | Drives age, birthday notifications, and legal-minor flag |
| `gender` | enum: `male` / `female` / `other` | Useful for segmentation reports |
| `photo` | url | Avatar for reception "is this the right person" check-in screen |
| `createdAt` | datetime | "Client since" |
| `status` | enum: `active` / `frozen` / `expired` / `archived` / `lead` | Derived from memberships but cached for list filtering |

**Contact & admin:**
| Field | Type | Notes |
|---|---|---|
| `source` | enum: `walk-in` / `referral` / `instagram` / `vk` / `ads` / `other` | *Откуда узнали о нас* — marketing attribution |
| `referredBy` | clientId | *Кто привёл* |
| `tags` | string[] | Free-form: *VIP*, *проблемный*, *должник*, *постоянник* |
| `notes` | markdown-ish text | Internal notes from reception/trainer |
| `emergencyContact` | { name, phone, relation } | Required in many clubs; critical for minors |
| `address` | string | Rarely used; keep optional |

**Health & waiver:**
| Field | Type | Notes |
|---|---|---|
| `medicalNotes` | text | *Медицинские противопоказания* — knee, heart, pregnancy, etc. |
| `waiverSigned` | boolean + date | *Подписан договор оферты* |
| `medicalCertUntil` | date nullable | *Медсправка действует до* — required for pool/kids/some group classes |
| `photoConsent` | boolean | For using photos in social media |

**Loyalty / account-level:**
| Field | Type | Notes |
|---|---|---|
| `balance` | money | *Депозит на счёте* — for personal training pre-pay, shop, etc. |
| `bonusPoints` | number | Optional loyalty program |
| `totalSpent` | money (derived) | LTV |
| `visitCount` | number (derived) | Total visits ever |
| `lastVisitAt` | datetime (derived) | Used to flag *уснувшие клиенты* |

### 1.2 Membership (*Абонемент*) — types

Russian/CIS gyms converge on these archetypes. Owner should be able to define them; in v1 mock we seed a reasonable catalog.

| Type | RU | Description | Unit of limit |
|---|---|---|---|
| Unlimited | *Безлимит* | Enter any time during validity window | Days only |
| Visit-limited | *Ограниченный / по посещениям* | 8, 12, 16 visits | Visits + expiry |
| Single entry | *Разовое посещение* | One-off pay-per-entry | 1 visit, 1 day |
| Day-only | *Дневной* | Valid e.g. 07:00–17:00 weekdays | Days + time window |
| Evening / prime-time | *Вечерний* | Opposite of above | Days + time window |
| Group-only | *Только групповые* | Cannot use free weights floor | Days, class-type filter |
| Gym-floor only | *Только тренажёрный зал* | No group classes | Days |
| Personal training pack | *Персональные тренировки* | 5/10/20 PT sessions with trainer | Sessions + expiry |
| Family | *Семейный* | N people share balance of visits or days | Shared across linked clients |
| Kids | *Детский* | For under-18; often ties to kids-schedule | Days + age gate |
| Student | *Студенческий* | Discount with student ID | Days, proof field |
| Corporate | *Корпоративный* | B2B contract, employer pays | Days, employer link |
| Freeze extension | *Заморозка* | Not a membership per se — state of an existing one | — |
| Trial | *Пробная / гостевая* | 1-day or 1-class free pass for leads | 1 visit |

### 1.3 Membership — data model

```ts
type Membership = {
  id: string
  clientId: string
  templateId: string          // which type from the catalog
  nameSnapshot: string        // name at purchase time (prices/titles drift)
  priceSnapshot: money
  purchasedAt: datetime
  activatedAt: datetime | null  // often !== purchasedAt; client may buy today, start Monday
  validFrom: date
  validUntil: date
  visitsTotal: number | null    // null = unlimited
  visitsUsed: number
  visitsRemaining: number | null // derived
  status: 'pending' | 'active' | 'frozen' | 'expired' | 'cancelled' | 'used-up'
  freezes: FreezeRecord[]
  timeWindow: { from: 'HH:mm', to: 'HH:mm', daysOfWeek: number[] } | null
  allowedScopes: Array<'gym' | 'group' | 'pool' | 'sauna' | 'pt'>
  soldByStaffId: string
  paymentId: string
  notes: string
}

type FreezeRecord = {
  id: string
  from: date
  to: date
  daysUsed: number
  reason: string        // "болезнь" / "отпуск" / "travel"
  createdByStaffId: string
  createdAt: datetime
}
```

### 1.4 Membership lifecycle — state machine

```
  (none)
    │  purchase
    ▼
 ┌────────┐   activate (immediate or scheduled)   ┌────────┐
 │ pending│ ─────────────────────────────────────▶│ active │
 └────────┘                                        └────┬───┘
                                                        │
           ┌───────────── freeze ────────────────┐      │
           ▼                                     │      │
       ┌────────┐    unfreeze / freeze expires   │      │
       │ frozen │ ───────────────────────────────┘      │
       └────────┘                                       │
                                                        │ visits depleted
                                                        ▼
                                                 ┌──────────┐
                                                 │ used-up  │
                                                 └──────────┘
                                                        │
                                                        │ validUntil passed
                                                        ▼
                                                 ┌──────────┐
                                                 │ expired  │
                                                 └──────────┘

  anywhere ── cancel/refund ──▶ ┌───────────┐
                                │ cancelled │
                                └───────────┘
```

Rules worth encoding:
- `frozen` extends `validUntil` by the freeze duration (most clubs) — UI must show both original and adjusted end date.
- Most Russian clubs cap total freeze days (e.g. 14 days per 6-month *абонемент*).
- A client can have **multiple active memberships simultaneously** (e.g. group-only + PT pack). Check-in picks the applicable one.
- Auto-renewal (*автопродление*) is **out of v1 scope** but leave the flag in the type so the UI can show a disabled toggle.

### 1.5 Visit / check-in (*Посещение*)

```ts
type Visit = {
  id: string
  clientId: string
  membershipId: string | null       // null = paid single entry at desk
  checkInAt: datetime
  checkOutAt: datetime | null
  zone: 'gym' | 'group' | 'pool' | 'pt'
  classId: string | null            // if entered for a group class
  staffId: string                   // receptionist who let them in
  paymentId: string | null          // if walk-in pay
  note: string
}
```

### 1.6 Alerts / notifications this module produces

- Membership expiring in **7 / 3 / 1 days** (three distinct triggers).
- Membership expired (transitioned today).
- Visits remaining ≤ 2.
- Freeze ending tomorrow.
- Birthday today / this week.
- Medical certificate expiring / expired.
- *Должник* — client entered but has outstanding balance.
- New lead / trial client created.
- Family membership: one member overused share.

### 1.7 Check-in screen — "can this person enter?"

This is the single most-used screen in the whole CRM. Reception view should be optimised for this.

**UX requirements:**
- **Big search bar** with autocomplete on phone + last name. Barcode/QR card scan is a nice-to-have in mock (show a button that opens a fake scanner).
- Result card with: photo, name, **big status badge** (green *Можно*, amber *Внимание*, red *Нельзя*), active memberships, visits remaining, expiry, medical cert status, any *заморозка* or *блок*.
- **Primary action button:** *Пропустить* — logs a visit, decrements counter, records zone.
- Secondary: *Продать разовое*, *Продать абонемент*, *Снять с заморозки*, *Записать на занятие*.
- Recent check-ins strip at the bottom (last 10 today) — fast undo if wrong client.

### 1.8 Screens for module "Clients & Memberships"

1. **Clients list** — table with filters (status, tag, expiring-soon, *должник*, source), columns: photo, name, phone, active *абонемент*, expiry, visits left, last visit. Sortable, paginated, quick-search.
2. **Client detail** — tabs: *Профиль* · *Абонементы* · *Посещения* · *Платежи* · *Записи на занятия* · *Заметки*.
3. **Client create/edit** drawer/modal.
4. **Sell membership** wizard: pick template → pick validity start → apply discount → choose payment method → confirm.
5. **Freeze membership** modal: pick dates, reason, show updated *valid until*.
6. **Membership templates** (admin only) — catalog CRUD.
7. **Check-in** (reception home) — as above.
8. **Visit history** — global list, filterable by zone/staff/day.
9. **Expiring soon** — dedicated list (7/30 day buckets) that backs the dashboard widget.
10. **Leads / trials** — lightweight pipeline (Kanban: *Новый* → *Связались* → *Пробное* → *Купил* → *Потерян*).

---

## 2. Schedule (*Расписание*)

### 2.1 Objects involved

```ts
type Room = { id, name, capacity, zone: 'group'|'pool'|'ring'|'cycle'|'other', color }

type ClassTemplate = {   // "Йога для начинающих, 60 мин"
  id, name, description, level: 'beginner'|'medium'|'advanced',
  defaultTrainerId, defaultRoomId, defaultCapacity, durationMinutes,
  color, tags: string[], allowedMembershipScopes
}

type ClassOccurrence = {
  id, templateId,
  startAt, endAt, roomId, trainerId, capacity,
  status: 'scheduled' | 'cancelled' | 'completed',
  cancelReason?: string,
  enrollments: Enrollment[],
  waitlist: Enrollment[],
  notes
}

type RecurrenceRule = {
  templateId, roomId, trainerId,
  daysOfWeek: number[], startTime: 'HH:mm', durationMinutes,
  fromDate, toDate | null,
  exceptions: date[]
}

type Enrollment = {
  id, classOccurrenceId, clientId, membershipId | null,
  enrolledAt, status: 'booked'|'checked-in'|'no-show'|'cancelled',
  source: 'self'|'reception'|'trainer'
}

type PersonalTrainingSlot = {
  id, trainerId, clientId, startAt, endAt, status,
  membershipId, notes
}
```

### 2.2 Calendar UX

Default vendor pattern is FullCalendar-style:
- **Day** view (reception's daily ops).
- **Week** view (default for both roles — 7-column grid, time on Y-axis, classes as colored blocks).
- **Month** view (owner overview, occupancy heat per day).
- **List / agenda** view (filterable).
- **Trainer swimlanes** view — one row per trainer, useful for PT scheduling.
- **Room swimlanes** view — prevents double-booking *зала*.

Interactions to mock:
- Click empty slot → *Создать занятие* drawer.
- Click class → detail drawer with roster, cancel, duplicate, edit-one-vs-series.
- Drag to move; drag edge to resize. (Mock-only: just record the change locally.)
- Filter chips: by trainer, by room, by class type, by *тип абонемента, который пускают*.
- "This week vs same week last month" toggle (occupancy compare) — nice-to-have.

### 2.3 Enrollment flows

- **Self-booking** simulated via "Записать клиента" from client card — no public portal in v1.
- **Capacity full** → offer waitlist; promote waitlist automatically when someone cancels (show a toast *"Из листа ожидания зачислён(а) Иванова И."*).
- **Cancellation window** — display rule ("*отмена бесплатно за 4 часа*") but don't enforce penalties; just show warning.
- **No-show** — mark via class roster screen; optionally deduct visit per club rule (toggle in class template).
- **Membership eligibility** check on enroll: class must match client's active membership scopes and time-window.

### 2.4 Recurring vs one-off vs cancellation

- Recurring rule generates weekly occurrences. Edits should ask "*Только это занятие / Это и все последующие / Вся серия*" (standard Outlook/Google Calendar pattern).
- Cancellation = occurrence becomes `status: cancelled` but stays visible (struck-through) for a few days with reason. Enrollments auto-marked for refund/credit.
- Public holidays — admin can bulk-cancel a day.

### 2.5 Role differences on schedule

- **Reception:** sees today+week, can enroll clients, check them in, mark no-show, cancel a single occurrence with admin approval, sell *разовое* on the fly.
- **Admin:** can edit templates, recurrence rules, trainers' rates, see historical load, export.

### 2.6 Screens for module "Schedule"

1. **Calendar (week)** — default home for schedule module.
2. **Calendar (day)** — reception-oriented.
3. **Calendar (month / heatmap)** — owner overview.
4. **Trainer swimlanes** — PT-centric view.
5. **Class occurrence detail** drawer — roster, check-in toggles, cancel, notes.
6. **Create class** drawer — one-off.
7. **Create recurring series** drawer — recurrence rule editor.
8. **Class templates catalog** (admin).
9. **Rooms catalog** (admin).
10. **Waitlist inbox** — cross-class list of people waiting.
11. **PT booking** — trainer-availability picker + client link.

---

## 3. Trainers / Staff (*Тренеры и персонал*)

### 3.1 Staff record

```ts
type Staff = {
  id, role: 'owner'|'admin'|'reception'|'trainer'|'cleaner'|'other',
  lastName, firstName, middleName,
  phone, email, photo, bio,
  specializations: string[],       // "йога", "кроссфит", "ТРХ"
  certifications: { title, issuedBy, issuedAt, expiresAt, fileUrl }[],
  hiredAt, terminatedAt | null,
  status: 'active'|'on-leave'|'inactive',
  colorTag,                        // for their classes in calendar
  workSchedule: WeeklyAvailability,// which hours they normally work
  compensation: Compensation,
  socialLinks, notes
}
```

### 3.2 Compensation models (all must be representable in UI)

| Model | RU | Mechanics |
|---|---|---|
| Fixed salary | *Оклад* | Fixed monthly amount; absences/overtime tracked separately |
| Hourly | *Почасовая ставка* | Rate × hours worked (timesheet) |
| Per class | *Ставка за занятие* | Fixed amount per conducted group class, sometimes with capacity bonuses |
| % of class revenue | *Процент с выручки занятия* | % × (attendees × ticket price) |
| % of PT session | *Процент с персоналки* | % × PT price, often 40–60% |
| Hybrid | *Оклад + %* | Base + % — most common for senior trainers |
| Rent-the-hall | *Аренда зала* | Trainer pays club, keeps all fees — inverse case |

Data:
```ts
type Compensation = {
  baseSalaryMonthly?: money
  hourlyRate?: money
  perClassRate?: money
  perClassBonusPerHead?: money
  groupClassRevenuePct?: number     // 0..100
  ptRevenuePct?: number
  currency: 'RUB'
  notes: string
}
```

### 3.3 Earnings calculation (reporting)

Per period (month default), per trainer:
- List of conducted classes with attendees & computed pay.
- List of PT sessions with computed pay.
- Base salary line.
- Adjustments (bonuses, penalties, advances — *аванс*).
- Total to pay, amount already paid, outstanding.

### 3.4 Screens for module "Trainers / Staff"

1. **Staff list** — filter by role, status, specialization.
2. **Trainer detail** — tabs: *Профиль* · *Сертификаты* · *Расписание* · *Клиенты (PT)* · *Ставка* · *Начисления*.
3. **Create/edit staff** drawer.
4. **Compensation editor** — plain-language form translating to Compensation struct.
5. **Payroll run** — monthly list of staff with computed earnings + "mark as paid" (admin only).
6. **Certifications expiring** widget.

---

## 4. Finances (*Финансы*)

### 4.1 Income sources (types to model)

| Source | RU | Notes |
|---|---|---|
| Membership sale | *Продажа абонемента* | Biggest line |
| Single entry | *Разовое посещение* | Walk-in pay-per-entry |
| Personal training | *Персональные тренировки* | Either pre-pay package or per-session |
| Group class walk-in | *Разовое на групповое* | Pay-per-class without membership |
| Shop / café | *Магазин / бар* | Protein, water, towel rent, snacks |
| Rentals | *Аренда* | Locker rent, hall rent to outside trainer |
| Fines / penalties | *Штрафы* | No-show fees, late cancel — rare but possible |
| Misc | *Прочее* | Gift card sales, freeze fee, transfer fee |

### 4.2 Expense categories

| Category | RU |
|---|---|
| Salaries & payroll | *Зарплата* |
| Rent | *Аренда помещения* |
| Utilities | *Коммуналка* |
| Equipment purchase | *Покупка инвентаря* |
| Equipment maintenance | *Ремонт / обслуживание* |
| Cleaning | *Клининг* |
| Marketing & ads | *Маркетинг* |
| Software / subscriptions | *ПО / подписки* |
| Taxes & fees | *Налоги / сборы* |
| Other | *Прочее* |

### 4.3 Payment model

```ts
type Payment = {
  id, at: datetime, amount: money,
  direction: 'in' | 'out',
  method: 'cash' | 'card' | 'transfer' | 'certificate' | 'balance',
  source?: 'membership'|'single'|'pt'|'shop'|'rental'|'penalty'|'misc',
  categoryId?: string,           // for expenses
  clientId?: string,
  membershipId?: string,
  staffId: string,               // who processed it
  cashRegisterId: string,        // *касса*
  isRefund: boolean,
  receiptNumber?: string,        // fake for mock
  note
}

type CashRegisterSession = {
  id, openedAt, closedAt | null,
  openedByStaffId, closedByStaffId,
  openingFloat: money,
  cashIn: money, cashOut: money,
  cardIn: money, transferIn: money,
  expectedClosingCash: money,
  actualClosingCash | null,
  discrepancy | null,
  status: 'open'|'closed',
}
```

### 4.4 Russian 54-ФЗ / *онлайн-касса* — scope note

**In v1, we only simulate the surface:** show a *"чек отправлен"* badge on a successful cash/card payment, show a "cashier session" (*смена кассы*) open/close pair with opening float + closing reconciliation, and optionally a fake receipt number. **We do NOT** integrate with Atol/Evotor/Mercury/YooKassa or any fiscal driver. A banner somewhere in settings can say "фискализация 54-ФЗ появится при подключении бэкенда".

### 4.5 Reports to include

- **Daily cash report** (*Касса за день*) — reception's end-of-shift screen. Opening float, ins by method, outs, expected vs actual, discrepancy.
- **Monthly P&L** — income by source, expenses by category, net.
- **Revenue by source** — pie + trend.
- **Revenue by payment method** — cash / card / transfer share (Russian operators obsess over this).
- **Trainer earnings report** — per trainer period earnings, matches payroll run.
- **Outstanding balances** — clients with negative balance or unpaid sessions.
- **Membership sales report** — count & revenue by template, by month, conversion from trials.
- **Refunds log**.
- **Discounts applied** — who gave how much, to whom.

### 4.6 Screens for module "Finances"

1. **Finance dashboard** — today / week / month top cards + charts.
2. **Transactions list** — unified in/out list with huge filter panel.
3. **Create payment / expense** drawer.
4. **Cash register session** — open, running, close.
5. **Reports** — list of canned reports, each its own page.
6. **Expense categories** management (admin).
7. **Refund** flow — linked to original payment.
8. **Discounts & promos** (admin) — codes and fixed discounts.

---

## 5. Dashboard (home) KPIs

The owner's landing page. Aim for **one glance = state of the club**.

### 5.1 KPI cards (top row)

| KPI | Computation | RU label |
|---|---|---|
| Active memberships | count where `status=active` | *Активных абонементов* |
| Expiring in 7 days | count where `validUntil in [today, +7d]` | *Заканчиваются за 7 дней* |
| Expiring in 30 days | similar | *Заканчиваются за 30 дней* |
| New clients this week | count `createdAt >= monday` | *Новых клиентов за неделю* |
| Revenue today | sum payments.in today | *Выручка за сегодня* |
| Revenue this month | sum payments.in MTD | *Выручка за месяц* |
| MRR-ish | sum active memberships' price / duration, projected monthly | *Повторяющаяся выручка (оценка)* |
| Check-ins today | count visits today | *Посещений сегодня* |
| Classes today | count class occurrences today | *Занятий сегодня* |
| Class load % | attendees / capacity avg | *Заполняемость групповых* |
| Trainer utilization | PT booked hours / PT available hours | *Загрузка тренеров* |
| Outstanding balance | sum negative balances | *Долгов на сумму* |

### 5.2 Widgets (below cards)

- **Revenue chart** (line) — last 30 / 90 days, toggle.
- **Revenue by source** pie — this month.
- **Check-ins today timeline** — spark histogram by hour.
- **Top trainers** — by PT hours or revenue this month.
- **Classes today** — mini-agenda list with % full bar.
- **Expiring soon** list — top 5 with quick-call buttons.
- **Birthdays this week** — fun, drives retention calls.
- **Recent activity** — feed of last 10 actions (check-ins, sales, freezes).

### 5.3 Role differences on dashboard

- **Admin/Owner:** all of the above + financial cards + trainer utilization + payroll due.
- **Reception/Manager:** check-ins today, classes today, expiring soon, birthdays, daily *касса* card (today only, no monthly revenue), no salaries, no trainer revenue.

---

## 6. Notifications (*Центр уведомлений*)

### 6.1 Notification types (event catalog)

Grouped by what generates them. Each produces an in-app notification entry.

**Client / membership:**
- Membership expiring 7/3/1 days (per membership).
- Membership expired today.
- Visits left ≤ 2.
- Freeze starting / ending.
- Birthday today / tomorrow.
- Medical certificate expiring.
- New lead registered.
- Trial completed — sales follow-up cue.
- Client returned after long pause (*уснувший вернулся*).

**Schedule:**
- Class cancelled.
- Class filled to 100% capacity (reception cue to close door-sales).
- Class filled to <30% 2 hours before start (owner cue).
- Waitlist promotion happened.
- PT session in 30 minutes.

**Staff:**
- Certification expiring.
- Trainer requested time off.
- Payroll run due (end of month).
- Schedule change affects trainer.

**Finance:**
- Large payment received (> threshold).
- Refund issued.
- Cash register discrepancy at close.
- Daily *касса* closed summary.

**System / admin:**
- New client registered (reception action).
- New staff added.
- Settings changed.

### 6.2 Notification data model

```ts
type Notification = {
  id, createdAt,
  type: enum (see above),
  severity: 'info'|'success'|'warning'|'critical',
  title, body,
  entityRef?: { kind: 'client'|'membership'|'class'|'payment'|'staff', id },
  audience: Array<'owner'|'admin'|'reception'>,
  readByStaffIds: string[],         // per-staff read state
  actionUrl?: string,
  dismissible: boolean,
  expiresAt?: datetime,
}
```

### 6.3 UI pieces

- **Bell icon** in top bar with unread count.
- **Popover** — last 10, grouped by day, quick actions (*Отметить прочитанным*, *Открыть*).
- **Full notifications page** — filterable by type/severity/read.
- **Mark all as read** action.
- **Filter chips** — All / Unread / Critical / Today.
- **Settings** (admin) — which event types fire, for which audience. (In v1: read-only list showing the config, no real toggles.)
- **Toast** popups for real-time events done *during this session* (new check-in, payment received).

Severity-to-icon/color:
| Severity | Example | Default color |
|---|---|---|
| info | New client | muted/blue |
| success | Payment received | green |
| warning | Expiring in 3 days, low class load | amber |
| critical | Expired, cash discrepancy, cert expired | red |

---

## 7. Role Visibility Matrix

Legend: ✅ full · 👁️ read-only · 🙈 hidden · ⚠️ limited (see note)

| Area / screen | Owner/Admin | Reception/Manager |
|---|---|---|
| Dashboard — financial cards | ✅ | 🙈 |
| Dashboard — ops cards (check-ins, classes, birthdays) | ✅ | ✅ |
| Clients list | ✅ | ✅ |
| Client create/edit | ✅ | ✅ |
| Client archive/delete | ✅ | 🙈 |
| Sell membership | ✅ | ✅ |
| Freeze membership | ✅ | ⚠️ only within club rules |
| Refund / cancel membership | ✅ | 🙈 (request only) |
| Membership templates catalog | ✅ | 👁️ |
| Check-in | ✅ | ✅ |
| Schedule — view | ✅ | ✅ |
| Schedule — edit single occurrence | ✅ | ⚠️ cancel-only |
| Schedule — edit recurring series | ✅ | 🙈 |
| Class templates / rooms | ✅ | 👁️ |
| PT booking | ✅ | ✅ |
| Staff list | ✅ | 👁️ names + phones only |
| Staff detail — profile | ✅ | 👁️ |
| Staff detail — compensation | ✅ | 🙈 |
| Staff detail — earnings | ✅ | 🙈 |
| Payroll run | ✅ | 🙈 |
| Finance — transactions list | ✅ | ⚠️ only own-shift today |
| Finance — create income | ✅ | ✅ |
| Finance — create expense | ✅ | 🙈 |
| Cash register — open/close own shift | ✅ | ✅ |
| Cash register — other shifts | ✅ | 🙈 |
| Reports | ✅ | 🙈 (except daily *касса*) |
| Discounts / promos | ✅ | 👁️ apply-only |
| Settings — club info, hours, zones | ✅ | 🙈 |
| Settings — membership catalog | ✅ | 🙈 |
| Notifications — full list | ✅ | ⚠️ only ops/client/schedule categories |
| Notifications — settings | ✅ | 🙈 |
| Audit log | ✅ | 🙈 |

---

## 8. Competitive Landscape (brief)

All five below converge on the same core module set. They differ mostly in market focus (gym vs studio vs multi-club), price tier, and whether they own the client-facing mobile app. Their **admin screens** are remarkably similar — which is why the module breakdown above is confidence-MEDIUM-HIGH even without fresh scraping.

| Product | Home market | Notes (standard admin screens observed in training data) |
|---|---|---|
| **1Fit** | CIS (KZ-origin, also RU) | Hybrid: consumer subscription marketplace + club admin. Club admin has clients / *абонементы* / schedule / finances / reports. Strong PT and group class booking. |
| **Mindbody** | US / global | Huge SaaS. Classes-first (yoga/pilates studios). Screens: schedule, clients, staff, pricing options (~= *абонементы*), POS, reports, marketing. |
| **FitBase** | Russia | Purpose-built for RU gyms. Clients, *абонементы*, *касса*, schedule, trainers, finances, 54-ФЗ integration, access control hardware. |
| **TeamUp** | UK / EU | Studio-focused (boxing, CF, yoga). Schedule + membership + online booking. Lean admin. |
| **ClubManager** | RU / CIS | Club-focused. Clients, *абонементы*, finances, *касса*, access control, reports. |
| (Also common) **Glofox, Zen Planner, Wodify, Mobifitness, Rukovoditel** | — | Same module set, different UX polish. |

**Common screens across all vendors:**
1. Dashboard / home KPI page.
2. Clients list + client profile with tabs.
3. Membership / pricing-option catalog and sale flow.
4. Calendar (week is default).
5. Class roster / check-in.
6. Staff list & staff profile with schedule & rate.
7. Payroll / trainer earnings.
8. POS / payment entry.
9. *Касса* / cashier session close.
10. Reports hub.
11. Notifications / activity feed.
12. Settings (club, hours, categories, users).

**What they typically don't do** that we also shouldn't build in v1:
- Full marketing automation (email drips, SMS campaigns).
- Built-in access-control device drivers (turnstiles).
- Mobile client app (separate product).
- Full accounting / chart of accounts (they integrate to 1С / QuickBooks).
- Video on demand.

---

## 9. Anti-Features (explicitly NOT v1)

| Anti-feature | Why avoid | What to do instead |
|---|---|---|
| Real SMS/email sending | Needs providers, credentials, costs | UI shows "уведомление отправлено" badge, nothing leaves the app |
| Real 54-ФЗ fiscalization | Driver/HW dependency | Fake receipt number & status badge |
| Real payment gateway | Scope creep | "Mark as paid" modal with method picker |
| Online client self-booking portal | Separate product | Reception books on client's behalf |
| Multi-club / franchise | 10× data complexity | Single-club model; add `clubId` field in types but hide UI |
| Custom report builder | Massive UX surface | Ship ~8 canned reports |
| Role/permission editor | Over-engineering for 2 roles | Hard-coded role matrix in code |
| Audit log search | Not needed in mock | Log to console only |
| i18n framework | RU-only per spec | Hard-coded RU strings (but keep them in one `strings.ts`-ish file for later extraction) |
| Real auth, 2FA, invites | No backend | Role-switcher toggle in UI |
| Hardware integrations (turnstiles, card printers, barcode scanners) | Hardware dependency | "Scan card" button opens a fake modal |
| Mobile-first design | Desktop admin panel | Desktop-first, tablet acceptable, phone not targeted |

---

## 10. Must-Have v1 Screens — Checklist

This is the short list for roadmap phases. Ordered roughly by build dependency.

### Foundation (comes before any module)
- [ ] App shell: top bar (role switcher, theme toggle, notifications bell, profile) + left nav + content area
- [ ] Role switcher (Owner ↔ Reception) affecting nav & in-screen affordances
- [ ] Theme toggle (light / dark) via shadcn/reui tokens
- [ ] Mock data layer: typed repos + React Query-ish hooks, swappable to real API
- [ ] Global notifications center (popover + full page)

### Clients & Memberships
- [ ] Clients list (filters, search, tags)
- [ ] Client detail with tabs (profile, memberships, visits, payments, enrollments, notes)
- [ ] Client create/edit form
- [ ] Sell-membership wizard
- [ ] Freeze-membership modal
- [ ] Membership templates catalog (admin)
- [ ] **Check-in / front-desk screen** (reception home)
- [ ] Expiring-soon list (7 / 30 day buckets)
- [ ] Leads / trials mini pipeline

### Schedule
- [ ] Week calendar (default)
- [ ] Day calendar
- [ ] Month heatmap (owner)
- [ ] Trainer swimlanes view
- [ ] Class occurrence detail drawer with roster & check-in
- [ ] Create one-off class drawer
- [ ] Create recurring series drawer with Outlook-style edit-scope
- [ ] Class templates catalog (admin)
- [ ] Rooms catalog (admin)
- [ ] Waitlist inbox
- [ ] PT booking screen (trainer availability + client picker)

### Trainers / Staff
- [ ] Staff list
- [ ] Trainer detail tabs (profile, certificates, schedule, PT clients, rate, earnings)
- [ ] Create/edit staff form
- [ ] Compensation editor (plain-language form)
- [ ] Payroll run screen (admin)
- [ ] Certifications-expiring widget

### Finances
- [ ] Finance dashboard (today / month)
- [ ] Transactions list with filters
- [ ] Create payment / expense drawer
- [ ] Cash register open/close flow
- [ ] Canned reports: daily *касса*, monthly P&L, by source, by method, trainer earnings, outstanding balances, membership sales, refunds log
- [ ] Expense categories catalog
- [ ] Refund flow

### Dashboard
- [ ] Owner dashboard with full KPI grid + charts
- [ ] Reception dashboard (ops-only subset)

### Notifications
- [ ] Bell popover with unread count
- [ ] Full notifications page with filters
- [ ] Mark all as read
- [ ] Toasts for in-session events
- [ ] (read-only) notification-rules page

### Settings (minimum)
- [ ] Club info (name, address, hours, timezone, currency)
- [ ] Zones / scopes list (gym, group, pool, etc.)
- [ ] Working days & holidays
- [ ] Theme default

---

## 11. Gaps / Open Questions (to resolve during design or phase-specific research)

1. **Family memberships** — how are they modeled? One membership attached to multiple clients, vs parent client with dependents? v1 mock can do "linked clients + shared visit pool" but confirm in design.
2. **Access control** — do we pretend turnstile integration (show a *"дверь открыта"* toast on check-in) or stay purely informational? Default: informational.
3. **PT as membership vs PT as session block** — Russian clubs sometimes sell PT as pre-paid packs (membership-like), sometimes ad-hoc per session. v1 should support both paths; pick one as default seed.
4. **Kids area** — does v1 need a distinct "kids" module (group classes for under-18) or is it just `membershipType = kids` + age check? Recommendation: latter.
5. **Locker rent / shop POS** — in or out? Recommendation: out of v1, but leave `source: 'shop'|'rental'` enum values so reports can show zero-value lines.
6. **Attendance-based deduction** vs **entry-based deduction** for visit-limited memberships — most clubs deduct on entry, not on class attendance. Confirm.
7. **Discount model** — per-client discount %, promo codes, bundle discounts? Recommendation: per-sale `discountAmount` free-form + a thin promos list, no code engine.
8. **Timezone** — single-club means single TZ, but date math still needs a TZ in types. Use club's TZ string (default Europe/Moscow).
9. **Currency** — RUB hard-coded v1; type already generic.
10. **Avatar source** — use a deterministic avatar service for mocks (e.g. DiceBear) so reloads don't churn images.

---

## 12. Sources & Confidence

- **Training-data synthesis** on vendor module sets (1Fit, Mindbody, FitBase, TeamUp, ClubManager, Glofox, Zen Planner, Wodify, Mobifitness) — MEDIUM-HIGH confidence. The module decomposition above is the intersection they all share; individual vendor feature parity of specific screens was not freshly verified this session.
- **Russian gym operational vocabulary** (*абонемент*, *заморозка*, *касса*, *смена кассы*, *онлайн-касса*, *разовое*, *безлимит*) — HIGH confidence; these are stable domain terms.
- **54-ФЗ fiscal regime** — awareness only, explicitly out of build scope. Confidence on scope boundary: HIGH. Confidence on implementation details: not relevant.
- **Compensation models for trainers** — MEDIUM confidence. Real clubs vary widely; the six archetypes listed are the common superset.
- **Calendar UX patterns** — HIGH confidence. FullCalendar + Outlook-style recurrence editing is industry default; reui.io/shadcn have calendar primitives to compose from.
- **Direct vendor screenshot verification** — NOT performed this session (WebFetch blocked by certificate/model errors in environment). Downgrade any claim phrased as "vendor X has screen Y" to MEDIUM and verify during actual design if that matters.

**Overall confidence this document is sufficient to design realistic mocks:** HIGH. The module set, fields, states, and role matrix are stable domain knowledge; SportZal Adminka does not need to innovate here — it needs to render the standard set cleanly.
