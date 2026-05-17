# Feature Research — v1.5 Schedule + Bookings (PT Slots)

**Domain:** PT-slot booking for a single-zal gym CRM (Russian market)
**Researched:** 2026-05-17
**Confidence:** HIGH for table-stakes classification (triangulated from Mindbody, SimplyBook.me, SuperSaaS, Trainerize/ABC, Goldie, SchedulingKit, Bookafy industry materials). MEDIUM for implementation detail where single-source or Sportzal-specific extrapolation.

**Scope discipline:** ONLY v1.5 themes — trainer availability slots, bookings FSM, PT-package linkage, Telegram notifications, bot `/book`. Anything that drifts toward online payment (ЮKassa), group classes, trainer payroll, email notifications, or waitlist is an explicit anti-feature below.

**Existing primitives this builds on (DO NOT re-research):**
- `trainers` table with `id`, `full_name`, `is_active`, soft-delete pattern (v1.4 Phase 31).
- `pt_packages` with `sessions_remaining`, `status ∈ {active,exhausted,expired,cancelled}`, partial UNIQUE `(client_id) WHERE status='active'`, `register_active_pt_package_resolver` Protocol slot (v1.4 Phase 33).
- `pt_sessions` with atomic decrement, backdating windows B-11 (reception ≤7d / owner unlimited), cancel window B-12 (reception ≤24h / owner anytime), `trainer_name_snapshot NOT NULL` (v1.4 Phase 34).
- `audit_log` + `LOCKED_AUDIT_EVENTS` 51-entry frozenset + `audit.emit` AST literal-string gate.
- `clients.telegram_chat_id` linkage + `build_bot` factory + `HandlerContext` extension pattern (v1.1 / v1.2 / v1.3).
- RBAC `(Action, Resource)` pairs through `OWNER_ONLY` frozenset and `Depends(require_permission)`.
- B-10 invariant (locked): PT-package alone does NOT grant gym floor access. Recording a PT-session does NOT create a Visit row. These remain orthogonal.

---

## REQ-ID Category Prefixes for REQUIREMENTS.md

| Prefix | User-Visible Category | Phases Likely Touched |
|--------|----------------------|----------------------|
| `SLOT` | Trainer availability slot lifecycle | Phase 37 (foundations + CRUD) |
| `BOOK` | Booking FSM + creation / cancel / no-show | Phase 38 (booking service + FSM) |
| `PKG` | PT-package linkage invariants | Phase 38 (pre-flight + guard rails) |
| `NOTIFY` | Telegram notification flows | Phase 38–39 |
| `BOT` | Telegram `/book` command | Phase 39 |

---

## Category SLOT — Trainer Availability Slots

### Table Stakes

| Feature | Why Expected | Complexity | Notes / v1.4 Dependency |
|---------|--------------|------------|--------------------------|
| **One-off slot creation** — `trainer_availability_slots` table with `(id, trainer_id FK, starts_at TIMESTAMPTZ, duration_minutes INT DEFAULT 60, status ∈ {active,cancelled}, created_by_user_id FK)` | Reception needs to publish trainer time. Slot is the atomic bookable unit. | LOW | References `trainers.id` (v1.4). Owner + reception can create. Status `active` on creation. |
| **Per-slot configurable duration (default 60 min)** | Industry standard for PT is fixed 60 min; storing it per-slot is two schema lines and enables future 45/90min variants without migration. | LOW | Include the column with DEFAULT 60; keep UI simple (one value in v1.5). |
| **Slot status: `active` / `cancelled` only** | Any confirmed booking against a slot must survive trainer sickness via cancellation. `draft`/`published` adds an approval hop with zero value at single-operator scale. | LOW | Reception/owner manage slots directly; no trainer self-service in v1.5. |
| **Buffer-time creation guard (10 min)** | Prevents accidental back-to-back bookings with zero prep time. Industry standard (Mindbody, SuperSaaS both offer 10–15 min buffer). | LOW | Enforce at service layer on slot creation: reject if `new.starts_at < existing.starts_at + existing.duration_minutes + 10` for the same trainer. Hardcode 10 min v1.5. |
| **Slot list endpoint** — `GET /api/v1/slots?trainer_id=&from=&to=&status=` | Reception must see available slots to create a booking. Bot must enumerate free slots. | LOW | Returns paginated `{ items, total, page, pageSize }`. Include `is_booked` computed field (true if a `confirmed` booking exists). |
| **Slot-cancelled cascade to confirmed booking** | When a trainer is sick and reception cancels the slot, the linked booking must become `cancelled` and the client notified. Leaving an orphaned `confirmed` booking is a data integrity error. | LOW | Service-layer cascade: on `PATCH /slots/{id}` → `status:cancelled`, find linked `confirmed` booking → transition to `cancelled` → emit audit + Telegram DM. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Bulk slot creation for a week** (same trainer, same time, N occurrences) | Reduces reception repetitive work. | MEDIUM | Requires loop in service or a `repeat_count` param. Adds retry-on-buffer-conflict logic. Defer to v1.5.1. |

### Anti-Features

| Anti-Feature | Why Avoid | Milestone |
|---|---|---|
| **Recurring weekly pattern (rrule/template)** | Separate `slot_templates` table, cron-based expansion, complex "cancel this vs all future" semantics. Disproportionate to 5–10 slots/week at single-zal scale. | v2.x |
| **Vacation / leave blocks on trainer calendar** | Absence of a slot IS unavailability. A separate entity adds schema + UI for zero additional value at this scale. Cancel individual slots for sick days. | v2.x |
| **Draft / pending-review slot status** | No trainer self-service in v1.5; all slots are owner/reception-managed and go live as `active`. | v2.x |
| **Trainer self-service slot publication** | Trainer auth / login role does not exist. Adding it doubles user-management surface. | v2.x |

---

## Category BOOK — Booking FSM + Creation / Cancel / No-Show

### Table Stakes

| Feature | Why Expected | Complexity | Notes / v1.4 Dependency |
|---------|--------------|------------|--------------------------|
| **`bookings` table** with `(id, slot_id FK, client_id FK, pt_package_id FK, status ∈ {confirmed,cancelled,no_show,completed}, created_by_user_id FK, cancelled_at NULL, cancel_reason NULL, no_show_at NULL)` | Core booking record. FSM traces the lifecycle. | MEDIUM | `pt_package_id` stored at creation (snapshot for audit traceability); decrement stays on PT-session creation (not here). |
| **Race-safe partial UNIQUE `(slot_id) WHERE status='confirmed'`** | Prevents concurrent same-slot bookings. DB wins the race (app-layer check is informative only). | LOW | Mirrors v1.2 `UNIQUE(client_id, gym_date)` for visits and v1.3 freeze-period discipline exactly. |
| **Booking creation pre-flight checks** | Users expect an explicit, discriminated error when conditions aren't met. | LOW | Three sequential checks: (1) slot `active` + not already `confirmed`; (2) client has active PT-package via `ActivePtPackageResolver`; (3) `sessions_remaining > 0`. Each returns 409 with discriminating code. |
| **Instant-confirm booking** — `POST /bookings` creates a `confirmed` booking | No approval hop. Reception holds ground truth; request-approve queue adds latency with zero benefit in a 1-operator gym. Industry consensus: instant confirm is the standard for single-operator studios. | LOW | — |
| **Booking cancellation: reception ≤ 24h before slot start, owner anytime** | Mirror of B-12 PT-session cancel window from v1.4. Industry standard 24h window (Goldie, Mindbody, SchedulingKit). | LOW | `confirmed → cancelled`. Does NOT debit PT-package (session not yet consumed). `cancelled_at` + `cancel_reason` stored. |
| **Manual no-show marking** — `POST /bookings/{id}/no_show` (reception + owner) | After slot time passes with no PT-session recorded, staff marks it. Manual is the industry norm at single-trainer scale (Trainerize: "only trainer can mark as no-show"). | LOW | `confirmed → no_show`. Does NOT debit PT-package in v1.5. |
| **`booking_id` optional FK on `pt_sessions`** | Links delivery (PT-session) to reservation (booking). Required for `completed` transition and audit traceability. | LOW | Alembic migration adds nullable `booking_id FK bookings.id ON DELETE SET NULL` to `pt_sessions`. |
| **Booking `completed` transition on PT-session creation** | When a PT-session is recorded with a `booking_id`, the booking must transition `confirmed → completed` in the same transaction. Otherwise booking is never closed automatically and requires a separate manual step. | MEDIUM | Cross-module callback from `pt_sessions.service` to `bookings.service` via a Protocol slot registered in `app/main.py` composition root (mirrors `HandlerContext` / `ActiveMembership` pattern). |
| **Guard: PT-session creation rejected against non-`confirmed` booking** | Prevents recording a session against a cancelled or already-completed booking. | LOW | 409 `booking_not_active` if `booking.status != 'confirmed'`. |
| **Booking FSM central guard + `BOOKING_STATUS_TRANSITIONS` constant** | Mirrors `MEMBERSHIP_STATUS_TRANSITIONS` discipline from v1.3. One source of truth; invalid transitions return 409 `invalid_transition`. | LOW | Declare in `app/modules/bookings/constants.py`. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Two-step reschedule: cancel + rebook** (no atomic endpoint) | Covers the use case via two existing operations. Simple, no new FSM paths. | LOW | Expose as documented workflow in API; no dedicated `PATCH /bookings/{id}/slot_id` needed in v1.5. |
| **No-show DM to client at marking time** | Client awareness. | LOW | Cheap once notification infrastructure is in place (see NOTIFY). Include as P2. |

### Anti-Features

| Anti-Feature | Why Avoid | Milestone |
|---|---|---|
| **Atomic reschedule endpoint** | Requires resolving concurrent-slot races in a single transaction; FSM complexity high; not needed for single-operator UX. | v1.6 |
| **Auto-no-show cron** (flip `confirmed` → `no_show` N hours after slot with no PT-session) | Medium complexity (ARQ job + grace-period config + false-positive risk). Manual no-show is sufficient at single-zal scale. | v1.5.1 |
| **Late-cancel session forfeit penalty** | Would require an exception to the debit-at-delivery invariant (B-12 pattern). Owner enforces this socially for now. | v2.x |
| **Grace credit (no-penalty window within the 24h window)** | Adds policy complexity with no clear MVP benefit. 24h window is already a clear boundary. | v2.x |
| **Online payment at booking** | ЮKassa in v1.7. PT-package is pre-purchased via cash. | v1.7 |
| **Client self-booking via web portal** | Production frontend is built by design team separately; integrates in v2.0. | v2.0 |

---

## Category PKG — PT-Package Linkage Invariants

### Table Stakes

| Feature | Why Expected | Complexity | Notes / v1.4 Dependency |
|---------|--------------|------------|--------------------------|
| **Booking requires active PT-package with `sessions_remaining > 0`** | Package is the entitlement that authorises the session. No package = no booking. | LOW | Uses `register_active_pt_package_resolver` Protocol slot (v1.4 Phase 33). Discriminated 409 codes: `no_active_pt_package` / `pt_package_exhausted`. |
| **Session debit remains on PT-session creation, NOT on booking** | Debit-at-delivery invariant from v1.4: sessions are consumed when the trainer renders service, not when the client reserves a slot. A booking is a reservation; a PT-session is consumption. A no-show booking should NOT silently forfeit a session. | LOW (architectural invariant already locked) | Booking stores `pt_package_id` for audit traceability; `sessions_remaining` is NOT touched. Decrement happens at `POST /pt-sessions` (v1.4 path, unchanged). |
| **`sessions_remaining = 0` at PT-session recording time → 409, booking stays `confirmed`** | The package could be drained by other sessions between booking and delivery. The atomic decrement guard from v1.4 catches this. Reception must resolve (sell new package or cancel booking). | LOW | Inherited from v1.4 single-SQL atomic decrement; no new code. |
| **Guard: PT-session creation against a `booking_id` where booking is not `confirmed`** | Prevents double-debiting or recording against a stale booking. | LOW | 409 `booking_not_active`. Checked before decrement. |
| **PT-package expires/cancels after booking `confirmed` → booking stays `confirmed`, no auto-cascade** | Automatic cascade requires event listeners or a polling job, adding complexity. At single-zal scale, manual resolution (reception sees the 409 at PT-session time) is acceptable. | LOW | No cron / event-listener needed. The issue surfaces naturally when the PT-session is attempted. |
| **B-10 invariant must not be broken: booking does NOT create a Visit row** | A PT booking is a session reservation, not a gym check-in. These are orthogonal. Reception must check-in via `POST /visits` separately if the client needs floor access. | LOW (invariant) | No code path from `bookings.service` → `visits.service`. Import-linter `modules-independent` contract enforces this. |

### Anti-Features

| Anti-Feature | Why Avoid | Milestone |
|---|---|---|
| **Session debit at booking creation** | Breaks debit-at-delivery invariant. A cancellation would require a re-credit flow. Adds refund-like complexity to booking cancellation. | Never (architectural decision) |
| **Pre-authorisation hold ("reserve 1 session at booking, debit at completion")** | Requires a `sessions_reserved` counter alongside `sessions_remaining`. Doubles the counter logic. Overkill for single-zal. | v2.x if needed |
| **Allow booking without any PT-package ("pay later")** | Breaks the entitlement model. Reception can collect cash and sell a package first (v1.4 flow), then book. | Never for v1.5 |

---

## Category NOTIFY — Telegram Notification Flows

**Channel constraint:** Telegram-only for v1.5. Email channel lands in v1.6. All templates follow v1.3 discipline: locked Russian copy, owner sign-off, no oracle leak.

### Table Stakes

| Feature | Why Expected | Complexity | Notes / v1.4 Dependency |
|---------|--------------|------------|--------------------------|
| **Booking confirmation DM to client (immediate)** | Industry-wide standard: instant confirmation after booking (Mindbody, Goldie, SimplyBook.me all fire this). Reduces client uncertainty. | LOW | Sent at `POST /bookings` success. Template: trainer name, date, time, duration. Single locked Russian template. Uses `build_bot` + `client.telegram_chat_id`. |
| **Booking cancellation DM to client (when staff cancels booking or parent slot)** | Client must know the session is off. Not notifying is a real-world complaint (missed trip to gym). | LOW | Sent from booking cancellation service path AND from slot-cancelled cascade. Template: trainer name, date, "contact reception to rebook". No oracle leak. |
| **5 new LOCKED audit events** — `slot_published`, `booking_created`, `booking_cancelled`, `booking_no_show`, `booking_completed` | Audit chain completeness. `LOCKED_AUDIT_EVENTS` grows 51 → 56. AST gate enforces them from first commit. | LOW | Lock all 5 in Phase 37 foundations phase (mirrors v1.3 Phase 24 + v1.4 Phase 30 discipline of pre-locking before callsites land). |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **24h reminder DM to client** | Industry data: reminder sequences reduce no-shows by ~29% (DialogHealth). Single reminder is the minimum useful intervention. | MEDIUM | Requires `booking_notifications` idempotency table with UNIQUE `(booking_id, kind)` mirroring `membership_notifications` (v1.3). New ARQ cron at 06:35 MSK (ordered after existing 06:25 `expire_pt_packages` cron). Scans bookings where `slot.starts_at ∈ [now+23h, now+25h]` and no `reminder_24h` notification row exists. |
| **No-show DM to client at marking time** | Client awareness; reduces "why did my package go missing" support. | LOW | Once confirmation DM infrastructure is in place, this is one extra template + emit from `mark_no_show` path. |
| **1h reminder DM** | Marginal uplift over 24h reminder. | LOW (incremental) | Add `reminder_1h` kind to `booking_notifications`; same cron with different time window. P3 — include only if 24h reminder lands cleanly. |

### Anti-Features

| Anti-Feature | Why Avoid | Milestone |
|---|---|---|
| **Email notifications** | Email channel in v1.6. Sportzal constraint: Telegram-primary. | v1.6 |
| **Trainer receives booking DM** | Requires `telegram_chat_id` column on `trainers` table — not present in v1.4. New schema migration not scoped to v1.5 trainers module. | v1.6 |
| **Push notifications / in-app** | No client mobile app in scope. | v2.x |
| **SMS fallback** | No SMS integration; Telegram is the primary channel for RU/CIS. | Not planned |

---

## Category BOT — Telegram `/book` Command

### Table Stakes

| Feature | Why Expected | Complexity | Notes / v1.4 Dependency |
|---------|--------------|------------|--------------------------|
| **`/book` lists trainer's next free slots via inline keyboard** | Clients expect Telegram self-service matching the `/checkin` pattern from v1.2. Without discovery, the command is unusable. | MEDIUM | Bot queries `GET /slots?trainer_id=&from=now&status=active&is_booked=false`, returns next 5–7 slots. Each inline button: `"14 мая 14:00 (60 мин)"`. Requires `trainer_id` association (see PKG-trainer note below). |
| **Booking confirmation roundtrip** | Industry standard: one confirmation tap before committing (Telegram inline keyboard best practice; prevents accidental taps). | LOW | After slot tap: "Подтвердить запись к [Тренер] на [дата]? ✓ Да / ✗ Отмена". On confirm: call `POST /bookings` server-side, reply "Запись подтверждена!" with date and time. |
| **Guard: no active PT-package or Telegram not linked** | Anti-oracle DM. Mirrors v1.2 `/checkin` `_DM_NO_MEMBERSHIP` discipline: same DM for "not linked", "no package", "package exhausted". | LOW | Use locked Russian DM constants; owner sign-off required. |
| **`HandlerContext` extended with `slots_service` + `bookings_service`** | Bot worker must reach the booking domain without breaking `modules-independent` import-linter contract. | LOW | Mirrors D-10 pattern (v1.2): extend `HandlerContext` dataclass + register from `app/workers/telegram_bot.py:main()` + `app/main.py:create_app()`. |

**PT-package trainer association note:** For `/book` to list a specific trainer's slots, the PT-package must carry a `trainer_id` (either set at sale time or the client selects trainer in the bot flow). For v1.5 simplicity: require `trainer_id` to be optionally captured on `pt_packages` at sale time. If NULL, bot asks client to choose trainer from a one-step inline keyboard before listing slots. This keeps the bot usable even when `trainer_id` is not pre-set.

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **`/cancel_booking` command** | Client self-cancel within the 24h window. | MEDIUM | Requires listing active bookings per client, another inline keyboard, and cancel-window enforcement. Useful but adds bot state complexity. Defer to v1.5.1. |

### Anti-Features

| Anti-Feature | Why Avoid | Milestone |
|---|---|---|
| **Free-text NLP date input** ("next Tuesday at 3pm") | Adds a parsing layer with no existing library in the stack. Inline keyboard covers the use case fully. | Never |
| **Bot-initiated reschedule in one flow** | Cancel + rebook is two operations; making the bot compose them atomically adds stateful multi-step conversation handling. | v1.5.1 |
| **Bot as the primary booking channel (bypassing reception)** | Reception mediates all bookings in v1.5. Bot is a convenience channel, not the primary path. | — |

---

## Feature Dependencies on v1.4 Codebase

```
SLOT creation
    ├──requires──> trainers table + trainer_id FK (v1.4 Phase 31)
    ├──requires──> Resource.SLOTS added to RBAC
    └──requires──> buffer-time validation (new, service-layer)

BOOK creation
    ├──requires──> SLOT (active + not already confirmed)
    ├──requires──> register_active_pt_package_resolver Protocol slot (v1.4 Phase 33)
    ├──requires──> sessions_remaining > 0 (v1.4 atomic decrement pattern)
    └──requires──> partial UNIQUE (slot_id) WHERE status='confirmed'
                   (new Alembic migration, mirrors v1.2 visits discipline)

BOOK → completed
    ├──requires──> pt_sessions table (v1.4 Phase 34)
    ├──requires──> booking_id FK added to pt_sessions
                   (new Alembic migration, nullable ON DELETE SET NULL)
    └──requires──> cross-module callback: pt_sessions service → bookings service
                   via Protocol slot from app/main.py composition root

SLOT-cancelled cascade to BOOK
    └──requires──> BOOK cancellation service path

NOTIFY booking confirmation / cancellation / no-show DM
    ├──requires──> client.telegram_chat_id (v1.1)
    ├──requires──> build_bot factory (v1.3)
    └──requires──> LOCKED_AUDIT_EVENTS extended +5 (locked in Phase 37 foundations)

NOTIFY 24h reminder (differentiator)
    ├──requires──> booking_notifications idempotency table
    │              (new, UNIQUE(booking_id,kind), mirrors membership_notifications v1.3)
    └──requires──> ARQ cron at 06:35 MSK (new, ordered after expire_pt_packages 06:25)

BOT /book
    ├──requires──> client Telegram linkage (v1.1)
    ├──requires──> HandlerContext extended: slots_service + bookings_service
    │              (mirrors D-10 pattern v1.2)
    ├──requires──> SLOT read API (free slots endpoint)
    └──requires──> BOOK creation service

B-10 invariant — must NOT break
    No code path from bookings.service → visits.service
    booking_completed != visit_checked_in (orthogonal tables)
    import-linter modules-independent contract enforces physical separation
```

---

## MVP Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `trainer_availability_slots` CRUD (one-off, active/cancelled) | HIGH | LOW | P1 |
| Booking creation with PT-package pre-flight | HIGH | MEDIUM | P1 |
| Booking FSM (confirmed → cancelled / no_show / completed) + central guard | HIGH | MEDIUM | P1 |
| Race-safe partial UNIQUE on `(slot_id) WHERE status='confirmed'` | HIGH | LOW | P1 |
| `booking_id` FK on `pt_sessions` + `completed` transition on PT-session creation | HIGH | LOW | P1 |
| 5 new LOCKED audit events (locked in Phase 37 before callsites) | HIGH | LOW | P1 |
| Booking cancellation (reception ≤24h / owner anytime) | HIGH | LOW | P1 |
| Slot-cancelled cascade to confirmed booking | HIGH | LOW | P1 |
| Telegram DM: booking confirmed (immediate) | HIGH | LOW | P1 |
| Telegram DM: booking cancelled (client) | HIGH | LOW | P1 |
| Bot `/book`: slot discovery + confirm roundtrip | HIGH | MEDIUM | P1 |
| Bot anti-oracle DM for no-package / not-linked | HIGH | LOW | P1 |
| Buffer-time creation guard (10 min, hardcoded) | MEDIUM | LOW | P2 |
| Manual no-show marking + no-show DM to client | MEDIUM | LOW | P2 |
| 24h reminder DM via ARQ cron + `booking_notifications` idempotency table | MEDIUM | MEDIUM | P2 |
| `trainer_id` optional on PT-package (for bot trainer discovery) | MEDIUM | LOW | P2 |
| 1h reminder DM (incremental once 24h is built) | LOW | LOW | P3 |
| Bot `/cancel_booking` command | LOW | MEDIUM | P3 (v1.5.1) |

**P1 = strictly required for milestone completion. P2 = should ship within v1.5 phases if budget allows. P3 = opportunistic or v1.5.1.**

---

## Complexity Notes Per Category

| Category | Overall Complexity | Key Risk |
|---|---|---|
| SLOT | LOW | Buffer-guard edge cases (overlapping slots across multi-trainer future scenarios; v1.5 is single-trainer-at-a-time so straightforward) |
| BOOK | MEDIUM | Race-safe FSM, partial UNIQUE, three-check pre-flight, cross-module `completed` callback via Protocol slot |
| PKG | LOW | Debit-at-delivery invariant already locked; new guards are 2–3 lines each; main risk is accidental coupling to `visits` (blocked by import-linter) |
| NOTIFY | MEDIUM | 24h reminder cron + `booking_notifications` idempotency table follows v1.3 pattern exactly; risk is cron ordering (must run after `expire_pt_packages` 06:25) |
| BOT | MEDIUM | Inline keyboard pagination, `trainer_id` association logic, HandlerContext extension; main risk is bot state across two-step confirm roundtrip (mitigated by using a single Telegram message + reply markup callback) |

---

## Open Questions for Requirements Step

| # | Question | Default Recommendation | Confidence |
|---|---|---|---|
| Q1 | **`trainer_id` on PT-package at sale time — required or optional?** | Optional; bot asks if NULL. | MEDIUM |
| Q2 | **24h cron reminder — include in v1.5 or defer to v1.5.1?** | Include; same pattern as v1.3 expiring-soon notifications. | HIGH |
| Q3 | **No-show: session forfeited or not?** | NOT forfeited in v1.5 (no penalty). Owner enforces socially. | HIGH — breaking debit-at-delivery for no-show adds a new code branch with no clear user benefit at single-zal scale. |
| Q4 | **`slot_published` audit event fires on creation or on explicit publish action?** | On creation (slot goes `active` immediately). `slot_published` = `slot_created_as_active`. | HIGH |
| Q5 | **PT-package cancel/expire after booking confirmed — auto-cancel booking or leave `confirmed`?** | Leave `confirmed`; surface at PT-session recording time. | MEDIUM — auto-cancel requires event listener; manual surface is simpler and auditable. |
| Q6 | **Slot buffer: 10 min hardcoded or configurable?** | Hardcoded 10 min for v1.5. Configurable is a v2.x settings feature. | HIGH |
| Q7 | **Bot `/book` — list all trainers or only the PT-package's trainer?** | List only the PT-package's trainer (or ask trainer selection if `trainer_id` NULL). | HIGH — showing all trainers when a client already has a trainer-specific package is confusing. |

---

## Explicit Anti-Features Summary (v1.5 Scope Lock)

| Anti-Feature | Category | Reason | Future Milestone |
|---|---|---|---|
| Group classes (capacity > 1) | Scope | Open-gym model; locked by user decision | Never / separate milestone |
| Online payment at booking | Billing | ЮKassa in v1.7 | v1.7 |
| Trainer payroll / commission per session | Billing | No compensation module | v1.8+ |
| Email notifications | Notifications | Email channel in v1.6 | v1.6 |
| Trainer Telegram DMs (booking created / cancelled) | Notifications | No `telegram_chat_id` on trainers; new schema not in v1.5 | v1.6 |
| Recurring slot pattern generation | Slots | Complex cancel semantics; disproportionate at 5–10 slots/week | v2.x |
| Trainer self-service slot publication | Slots | Trainer role / auth does not exist | v2.x |
| Vacation / leave blocks | Slots | Absence of slot = unavailability; no extra entity needed | v2.x |
| Draft / pending-review slot status | Slots | No trainer self-service; slots go live immediately | v2.x |
| Waitlist | Bookings | Capacity = 1; manual coordination sufficient at single-zal scale | v2.x |
| Atomic reschedule endpoint | Bookings | Two-step cancel+rebook covers the use case; race complexity high | v1.6 |
| Auto-no-show cron | Bookings | Manual marking sufficient; ARQ job adds medium complexity | v1.5.1 |
| Late-cancel session forfeit penalty | Policy | Breaks debit-at-delivery invariant | v2.x |
| Bot `/cancel_booking` command | Bot | Adds stateful multi-step bot conversation; low urgency | v1.5.1 |
| Free-text NLP date input in bot | Bot | Inline keyboard sufficient; no parsing library in stack | Never |
| Client self-booking via web portal | Frontend | Design team integrates in v2.0 | v2.0 |
| Pre-authorisation session hold | PKG | Adds `sessions_reserved` counter; overkill for single-zal | v2.x |
| Session debit at booking creation | PKG | Breaks debit-at-delivery architectural invariant | Never |
| Booking creates a Visit row | B-10 | Orthogonal — B-10 invariant locked | Never |

---

## Sources

- [Mindbody — Appointment Options screen (buffer time, cancellation windows)](https://support.mindbodyonline.com/s/article/203259913-Appointment-Options-screen?language=en_US) — buffer time between sessions configuration
- [Mindbody — Booking and Scheduling for Personal Training](https://www.mindbodyonline.com/business/education/blog/booking-scheduling-software-personal-training) — 24h cancel window, instant confirm, session-debit timing
- [SimplyBook.me — Personal Trainer Scheduling](https://simplybook.me/en/scheduling-software-for-fitness--coaches-and-sports-classes/appointment-scheduling-software-for-personal-trainers) — capacity = 1, recurring vs one-off
- [Goldie — Scheduling for Personal Trainers](https://heygoldie.com/customers/personal-trainers) — 24h cancellation window as industry norm, card-on-file to enforce
- [SuperSaaS — Gym and Fitness Studios Booking](https://www.supersaas.com/info/gym-and-fitness-studios-booking-app) — cancellation policies, booking rules
- [ABC Trainerize Idea Forum — Track Appointments as completed / no show](https://ideas.trainerize.com/forums/167887-coach-trainer-trainerize/suggestions/41349247-ability-to-track-appointments-as-completed-no-sh) — manual no-show marking by trainer is the industry pattern
- [SchedulingKit — Appointment Reminders for Gyms](https://schedulingkit.com/appointment-reminders/gyms) — 24h + 2h reminder sequence, no-show reduction stats
- [Alloy Franchise — 3 Key Policies for Personal Training](https://alloyfranchise.com/blog/3-key-policies-for-your-personal-training-business/) — no-show and cancellation policy structures
- [Bookafy — Best Online Booking Systems for Fitness Comparison](https://bookafy.com/best-online-booking-systems-for-fitness-and-personal-trainers-detailed-comparison-buyers-guide-2/) — recurring vs one-off MVP feature matrix
- [Starta.one — Telegram Bot for Training Center Booking](https://starta.one/features/telegram-bot/training-center) — Telegram inline-keyboard booking UX for gyms
- [Nuffield Health — Personal Training Terms](https://www.nuffieldhealth.com/terms/nuffield-health-website-terms-and-conditions/personal-training-terms-and-conditions) — package debit-at-completion (delivery) model
- Internal: `PROJECT.md` v1.5 scope definition, B-10/B-11/B-12 invariants, ARQ cron ordering discipline, `LOCKED_AUDIT_EVENTS` pre-locking pattern, `HandlerContext` extension pattern

---

*Feature research for: PT-slot booking, Sportzal v1.5 Schedule + Bookings milestone*
*Researched: 2026-05-17*
