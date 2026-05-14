# Features — v1.4 Cash Sales + PT Packages

**Domain:** Single-gym CRM, RU/CIS market — "Cash payment ledger + refund flow + trainers catalog + PT-package tariff + PT-session recording"
**Researched:** 2026-05-14
**Confidence:** MEDIUM-HIGH for domain patterns (triangulated from FitBase, 1С:Фитнес-клуб, Mobifitness, Resawod, PushPress, Club-OS, ClickUp Gyms public materials and industry-wide cancellation/refund norms). LOW-MEDIUM where claims rely on a single secondary source — flagged inline.

**Scope discipline:** ONLY the five v1.4 themes. Anything that drifts toward online payments (ЮKassa), fiscal receipts (54-ФЗ), schedule/booking, payroll, or reports is explicitly out of scope and surfaced as "anti-feature" so the discuss-phase can reject it cleanly.

**Existing primitives this builds on (DO NOT re-research):**
- `memberships` with mandatory snapshot pricing (`plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot` NOT NULL), `status ∈ {active, frozen, expired, cancelled}`, central `_assert_can_transition`, `MEMBERSHIP_STATUS_TRANSITIONS`.
- `membership_plans` catalog with `freeze_days_limit` and `duration_days` immutable post-creation; `lower(name)` partial unique on `WHERE deleted_at IS NULL`; soft-delete with 409 `plan_in_use` when FK references exist.
- `visits` with `gym_date STORED` + `UNIQUE (client_id, gym_date)` — DB-level race-proof 1-visit-per-day.
- `audit_log` + `LOCKED_AUDIT_EVENTS` 34-entry frozenset + `audit.emit` AST literal-string gate.
- `clients` CRUD + `users` (reception/owner) — both already have `id` FKs available for "received by whom" and "performed by whom" attribution.
- RBAC `(Action, Resource)` pairs through `OWNER_ONLY` set and `Depends(require_permission)`.

---

## Category 1: Payments (cash)

### Table stakes

| Feature | Complexity | Notes |
|---|---|---|
| **Record sale-payment row at sale time** — `payments` table with `(id, membership_id, amount_kopecks, method='cash', received_by_user_id, received_at, note?)` | S | One row per sale event. Sale endpoint becomes atomic "create membership + insert payment" within a single transaction. Same shape works for both duration-memberships and PT-packages because both reference the same `memberships` table (PT-package is a plan-kind, not a separate table — see Category 4). |
| **Snapshot the price on the payment row** | S | Already half-done — `memberships.price_kopecks_snapshot` exists. The payment row also carries `amount_kopecks` so future partial-payment / discount scenarios don't break the invariant that `payment.amount` = what client actually handed over (may differ from snapshot if a manual discount is applied at sale). For v1.4 MVP, `amount_kopecks == price_kopecks_snapshot` is enforced server-side and the UI doesn't expose a discount field. |
| **"Received by" = reception user_id, not free-text** | S | Use `users.id` FK with `ON DELETE RESTRICT` so the operator can never become orphaned. The audit log already carries `actor_user_id` from `audit.emit`; the payment row stores it denormalised for fast "who took this money" queries on the client card without a join across audit. |
| **Payment timestamp is server-side, never client-supplied** | S | `received_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Reception cannot back-date or forward-date a cash sale (anti-fraud). |
| **Surface payment history on client card** | S | Read-only list under "Платежи" tab: date, amount, method, who received, linked membership. Source = `payments` filtered by `membership_id IN (memberships of client)`. |
| **Surface payment on membership detail** | S | One payment per membership in v1.4 (one sale = one cash event); the detail card shows "Оплачено 3 000 ₽ наличными, принял Анна, 14.05.2026 15:30". |
| **Audit event `payment_recorded`** | S | New entry in `LOCKED_AUDIT_EVENTS`. Payload: `payment_id`, `membership_id`, `amount_kopecks`, `received_by`. Required because this IS the financial event. |

### Differentiators

| Feature | Complexity | Notes |
|---|---|---|
| **Daily cash-drawer summary on owner dashboard** | M | "Today: 5 sales, 12 500 ₽; refunded 1 sale, 3 000 ₽; net 9 500 ₽." Useful for end-of-day reconciliation against physical cash. **Defer to v1.5 reports** — v1.4 only writes the data; reports come next milestone. PROJECT.md explicitly defers reports to v1.5. |
| **Per-reception-user shift totals** | M | "Анна приняла сегодня 4 продажи на 10 000 ₽." Same defer to v1.5. |
| **Note field on payment** (`text NULL`) | S | Reception writes "оплатил частично, остаток обещал в пятницу" — even though v1.4 doesn't model partial payments, a free-text note is a cheap escape hatch for "weird situations". LOW confidence on whether this is actually needed; pet-project owner may prefer the discipline of "no notes, no weirdness". Flag for discuss-phase. |

### Anti-features (do not build in v1.4)

| Anti-feature | Why avoid | What to do instead |
|---|---|---|
| **Card payments / online payments** | PROJECT.md explicit: ЮKassa in v1.6 only. | Hard-code `method='cash'` as a Postgres CHECK on `payments.method`. When v1.6 lands, alter the CHECK to admit `'card'`. |
| **Fiscal receipt printing (54-ФЗ)** | PROJECT.md explicit: gym is grey-zone, no checks. | No `receipt_number`, no `kkm_*` columns, no integration. |
| **Partial payments / installment plans** | Real industry feature (gyms often let clients pay 50/50), but adds state machine on `payments` (paid, due, overdue) that is a milestone of its own. | One payment per sale. If client can't afford full price, reception sells a cheaper plan or no plan. |
| **Discounts / promo codes** | Adds a `discount_kopecks` field, a justification field, an audit event, and an owner-approval workflow. | v1.4 enforces `payment.amount == membership.price_kopecks_snapshot`. Sale flow has no discount UI. |
| **Overpayment / change-given tracking** | In a cash drawer, "client gave 5 000 ₽ for 3 000 ₽ plan, got 2 000 ₽ change" is just normal cash handling — the system records the **price**, not the bill physically handed over. | `payment.amount` is the price, period. No `cash_tendered` / `change_given` columns. |
| **Multi-currency** | Single-gym RU/CIS, kopecks-only. | Inherit existing `_kopecks INT NOT NULL` discipline. |
| **Refund as `payment.amount < 0`** | Tempting because it keeps one table, but breaks the "one payment per sale" invariant and makes the client-card payment list confusing (mixing positive and negative rows that aren't obviously paired). | Separate `refunds` table — see Category 2. |

---

## Category 2: Refunds

### Table stakes

| Feature | Complexity | Notes |
|---|---|---|
| **Separate `refunds` table** with `(id, payment_id FK, amount_kopecks, performed_by_user_id, performed_at, reason TEXT NULL)` | S | One refund per payment, enforced by `UNIQUE (payment_id)`. "Already refunded" → 409 `already_refunded`. Industry norm (LA Fitness, Edge, Club Fitness all treat a refund as a distinct event with its own audit trail). |
| **Refund cancels the linked membership/package** | S | Atomic: refund creation + `memberships.status` transition `{active, frozen} → cancelled`. Add transition to `MEMBERSHIP_STATUS_TRANSITIONS` constant. New literal `cancelled_reason='refunded'` column or a `cancellation_reason` enum on memberships — preferred: a single new column `memberships.cancellation_reason VARCHAR NULL CHECK IN ('refunded','owner_decision', NULL)` so the existing 4-state status stays clean. |
| **Reception can perform refund (no owner approval)** | S | PROJECT.md explicit: "без owner approval". Add `(REFUND, PAYMENTS)` to `Action`/`Resource` enums; do NOT add to `OWNER_ONLY` — reception keeps it. |
| **Full refund only in v1.4** | S | `refund.amount == payment.amount`. Server-side enforced; UI has no amount field, just a "Вернуть деньги" confirm dialog showing the original amount. Eliminates the pro-rata question for MVP. |
| **Audit event `payment_refunded`** + `membership_cancelled` (already locked) | S | Both fire in the same transaction. `payment_refunded` payload: `refund_id`, `payment_id`, `amount_kopecks`, `reason`. |
| **Refund button hidden if already refunded** | S | UI reads `refund_id` on payment surface and disables the button. Server is still authoritative — UNIQUE constraint catches the race. |
| **Refund button hidden if membership has visits/PT-sessions consumed** (configurable per discuss-phase) | S | LOW confidence — this is a policy decision, not a technical one. Industry varies: some gyms refund freely, some lock once a single visit is logged. RECOMMEND: v1.4 ships the technical capability but the UI shows a warning ("Уже было 3 посещения") and lets reception proceed. Owner sees the audit. |

### Differentiators

| Feature | Complexity | Notes |
|---|---|---|
| **Pro-rata refund for PT-packages** ("used 3 of 10 → refund 7/10") | M | Real question, surfaced in milestone_context. Computable: `refund_amount = price * (remaining_sessions / total_sessions)`, ceil to kopeck. Adds a refund-amount field to UI, validation server-side. **RECOMMEND: defer to v1.5 or later** — pet-project owner can do the math by selling a new short package as compensation, or refund full + apologise. Flag for discuss-phase. |
| **Pro-rata refund for duration-memberships** ("30-day plan, used 10 days, refund 20/30") | M | Same shape. Same recommendation: defer. |
| **Refund reason picklist** (sickness / moving / dissatisfaction / other) | S | Cheap to add as a `reason_code` enum alongside free-text `reason`. Useful for v1.5 reports. RECOMMEND: ship the enum even if reports defer — the data is cheap to collect and expensive to backfill. |
| **Owner-only override for refund-after-N-visits** | M | "Reception can refund freely; if ≥1 visit consumed, requires owner role." Adds an RBAC branch. RECOMMEND: do NOT add — PROJECT.md explicit "ресепшен сам", solo-dev simplicity wins. |

### Anti-features

| Anti-feature | Why avoid |
|---|---|
| **Partial refunds with custom amount** | Opens "reception under-refunded by 500 ₽" social-engineering risk. Full refund or no refund. |
| **Refund reversal ("undo refund")** | A refund means cash physically left the drawer. Reversing requires the client to bring it back — that's just a new sale, not a system operation. |
| **Refund to a different payment method** | "Paid cash, refund to card" — adds payout integration. Not relevant for cash-only. |
| **Refund window enforcement** ("14 days from purchase") | Adds time logic and operator confusion. Reception's job is to apply judgement; system records the event. |
| **Refund-pending state** | No async approval needed (reception self-serves) → no need for "pending" status. Synchronous transaction. |

---

## Category 3: Trainers

### Table stakes

| Feature | Complexity | Notes |
|---|---|---|
| **`trainers` table** with `(id, full_name, phone NULL, is_active BOOL NOT NULL DEFAULT true, created_at, updated_at)` | S | Identity-only catalog. No user account, no login, no Telegram link — reception logs sessions **about** a trainer, the trainer does not log in. |
| **Soft-delete via `is_active=false`, not `deleted_at`** | S | Trainers historically attribute past PT-sessions; cannot break FK chain. `is_active=false` means "don't show in pickers for new sessions" but historical references stay intact. **Decision shortcut**: avoid `SoftDeleteMixin` here — use a simple boolean. Different semantics than `clients` where soft-delete = "this person is gone". |
| **Owner-only CRUD** | S | Add `(CREATE, TRAINERS)`, `(UPDATE, TRAINERS)`, `(DELETE, TRAINERS)` to `OWNER_ONLY`. Reception reads-only (needs to pick a trainer when logging a PT-session). |
| **Phone optional, no E.164 enforcement** | S | Trainers are internal staff; reception knows them. Phone is contact info, not a unique key. **Optional**: free-text `phone TEXT NULL`, no unique constraint. Differs deliberately from `clients.phone`. |
| **List endpoint with `?active=true` filter for pickers** | S | Reception PT-session UI calls `GET /api/v1/trainers?active=true` to populate dropdown. Default = all (for owner directory page). |
| **Audit events** `trainer_created`, `trainer_updated`, `trainer_archived`, `trainer_unarchived` | S | Add 4 entries to `LOCKED_AUDIT_EVENTS`. |

### Differentiators

| Feature | Complexity | Notes |
|---|---|---|
| **Trainer profile fields** (specialization, photo, bio) | M | Useful if displayed to clients — but no client-web in v1.4. Skip. |
| **Trainer-client preference link** ("этот клиент работает с этим тренером") | M | Adds a join table. Useful in workflow but not table-stakes when log-flow is "reception picks trainer at session time". Skip for v1.4. |
| **Per-trainer session counter** ("Анна провела 23 ПТ за месяц") | S | Trivial aggregate query off `pt_sessions`. Defer surfacing to v1.5 reports. |

### Anti-features (when does adding schedules/pay become necessary?)

| Anti-feature | When it becomes necessary |
|---|---|
| **Trainer schedule / shift table** | When trainers have fixed hours, when clients book trainers in advance, when a "trainer-not-available" check is needed at booking. **v1.4 = pet project, no schedule, no bookings** — reception logs after-the-fact: "Анна провела ПТ с Иваном в 14:30". |
| **Pay rate / commission per session** | When the gym owes the trainer money the system computes (payroll). PROJECT.md explicit: "тренеры только справочник, расчёт зарплат — не в этом milestone." |
| **Trainer login / Telegram bot for trainers** | When trainers self-log sessions or check their schedule. v1.4 says reception logs everything. Adding trainer auth doubles the user-management surface. |
| **Trainer rating / client feedback** | Client-web feature; no client-web in v1.4 (deferred to Phase J per Out of Scope). |
| **Trainer certifications / expiry tracking** | Compliance feature for chains. Single-gym pet project — owner knows their two trainers personally. |
| **Trainer-availability calendar UI** | Needs schedule first; same defer. |

**Rule of thumb (LOW confidence, but actionable):** when the trainer catalog needs more than 5 columns or the table grows a child table, the milestone has drifted into "schedule/payroll" territory. v1.4 should ship 4 columns max (`id`, `full_name`, `phone`, `is_active`, plus timestamps).

---

## Category 4: PT Packages (tariff)

### Table stakes

| Feature | Complexity | Notes |
|---|---|---|
| **New plan kind `'pt_package'`** on existing `membership_plans` table | S | Add column `membership_plans.kind VARCHAR NOT NULL DEFAULT 'duration' CHECK IN ('duration', 'pt_package')`. Existing rows backfill to `'duration'`. This avoids a separate `pt_packages` table and inherits all soft-delete / `freeze_days_limit` / pricing infrastructure. **RECOMMEND** over a parallel table — re-uses the existing sale flow. |
| **`session_count INT NULL`** on `membership_plans` | S | NULL for duration plans (CHECK enforces `kind='duration' → session_count IS NULL`). NOT NULL > 0 for pt_package plans (CHECK enforces `kind='pt_package' → session_count IS NOT NULL AND session_count > 0`). Immutable post-creation, mirroring `duration_days` and `freeze_days_limit`. |
| **PT-package membership instance reuses `memberships` table** | S | A sold pt_package is a row in `memberships` with `plan_kind_snapshot='pt_package'` + `session_count_snapshot` (mandatory snapshot, mirrors price/duration/freeze-limit snapshots). Inherits status state machine (`active/frozen/expired/cancelled`), inherits resolver tiebreak, inherits cancel/refund flow. |
| **`remaining_sessions INT`** on `memberships` (NULL for duration plans) | S | NOT NULL for pt_package memberships; initial value = `session_count_snapshot`. Decremented by PT-session recording (see Category 5). CHECK `remaining_sessions >= 0`. |
| **Client can have BOTH a duration membership AND a pt_package simultaneously** | S | Resolver already returns at most one row, but the relationship between the two is independent — they are separate `memberships` rows with different `plan_kind_snapshot`. Reception check-in resolves the duration plan; PT-session recording resolves the pt_package. **Decision:** the resolver needs a `kind` parameter, or split into `resolve_active_duration_membership` + `resolve_active_pt_package`. Recommend the latter for clarity. |
| **Expiry policy for pt_packages: duration in days OR session-count** | S | Industry norm: PT-packages expire on **whichever comes first** — N sessions consumed OR N days elapsed. **RECOMMEND** require both `duration_days` AND `session_count` on pt_package plans. Inherits existing `expire_memberships` ARQ cron for the time dimension; session-exhaustion is a separate transition (see Category 5). |
| **Audit events** `pt_package_sold` (or reuse `membership_sold` with `kind` in payload?) | S | RECOMMEND reuse `membership_sold` with `kind` discriminator in the payload, to keep `LOCKED_AUDIT_EVENTS` smaller. Add only the PT-specific events (`pt_session_recorded`, see Category 5). |

### Differentiators

| Feature | Complexity | Notes |
|---|---|---|
| **Multiple pt_packages in flight per client** ("client has 5 sessions left from Aug package + just bought 10 more") | M | Industry handles this with FIFO/LIFO consumption rules. **RECOMMEND** v1.4: only ONE active pt_package per client at a time. If client buys another while one is active, reception either (a) waits until first is done, (b) refunds the old + sells new. Add a partial unique constraint similar to freeze periods: `UNIQUE (client_id, plan_kind_snapshot) WHERE status='active' AND plan_kind_snapshot='pt_package'`. Flag for discuss-phase. LOW confidence on right answer. |
| **Package sharing with family/friend** | M | Some gyms allow "buy 10 PT, use them for spouse too." Adds `beneficiary_client_id` per session. **RECOMMEND** anti-feature for v1.4 — adds attribution ambiguity to reports. |
| **Carry-over of unused sessions after package expires** | S | "5 unused → roll into next purchase." Tempting; adds the question "for how long?" and complicates expire_memberships cron. **RECOMMEND** anti-feature for v1.4 — when package expires by time, remaining sessions are forfeited (industry norm, harsh but defensible). |
| **PT-package freeze** | S | Inherits existing `freeze_days_limit` infra trivially because pt_package is a row in `memberships`. **Decision needed:** does freezing a pt_package pause the time component only, or also "lock" the session balance from any decrement? Recommend: freeze == pause time only; balance is just a counter, freeze doesn't affect it. |

### Anti-features

| Anti-feature | Why avoid |
|---|---|
| **Half-sessions / fractional consumption** ("client did 30 min instead of 60 min, decrement 0.5") | Integer counter is precious. Round to whole sessions. Operator judgement: if the session was substantively done, decrement 1; otherwise don't log it at all. |
| **Group PT (one trainer, multiple clients in one session)** | Different product entirely (small-group training). v1.4 is 1:1. |
| **PT-package with unlimited sessions** | "Unlimited" is a duration plan, not a pt_package. Sell it as a duration plan. |
| **PT-only access to gym** ("PT clients don't need a regular membership to use the floor") | Adds resolver complexity: which kind grants check-in rights? RECOMMEND v1.4: pt_package does NOT grant gym check-in by itself. Client needs ALSO an active duration membership to enter the gym. The two are independent products. Flag for discuss-phase. |
| **Different prices per trainer for same package** | "10 sessions with Senior trainer cost more than 10 with Junior." Adds plan×trainer matrix. v1.4: package price is fixed per plan; trainer choice happens at session-recording time. |

---

## Category 5: PT Sessions (recording)

### Table stakes

| Feature | Complexity | Notes |
|---|---|---|
| **`pt_sessions` table** with `(id, membership_id FK, trainer_id FK, performed_at TIMESTAMPTZ NOT NULL, recorded_by_user_id FK, recorded_at TIMESTAMPTZ NOT NULL DEFAULT now())` | S | One row per consumed session. `membership_id` links to the pt_package membership (which links to client + plan-snapshots). `performed_at` is the actual training time (reception can back-date by hours if logging at end-of-shift). `recorded_at` is server-side immutable. |
| **Atomic decrement of `memberships.remaining_sessions` on insert** | S | Single transaction: insert `pt_sessions` row + `UPDATE memberships SET remaining_sessions = remaining_sessions - 1 WHERE id = $1 AND remaining_sessions > 0 RETURNING remaining_sessions`. If RETURNING is empty → 409 `package_exhausted`. DB-level race-proof (mirrors the visits `gym_date STORED + UNIQUE` discipline). |
| **Auto-transition pt_package membership to `expired` when `remaining_sessions = 0`** | S | In the same transaction: if new balance == 0 → `status → expired`. Or rely on a scheduled check. **RECOMMEND** do it inline — keeps the state machine consistent and makes the "package exhausted" UX feedback synchronous. Add transition to `MEMBERSHIP_STATUS_TRANSITIONS`. |
| **Reception-only recording (PT session log)** | S | `(CREATE, PT_SESSIONS)` permission, NOT in `OWNER_ONLY`. Reception is the day-to-day operator. |
| **Surface session history on client card** | S | Read-only timeline: "14.05 14:30 ПТ с Анной (осталось 7 из 10)". |
| **Surface session history on pt_package membership detail** | S | Same data, scoped to one membership. |
| **Audit event `pt_session_recorded`** | S | Payload: `pt_session_id`, `membership_id`, `trainer_id`, `performed_at`, `remaining_after`. |
| **Performed_at validation: not in the future, not before membership start_date** | S | Cheap server-side check. 409 `invalid_performed_at`. |

### Differentiators

| Feature | Complexity | Notes |
|---|---|---|
| **Undo / cancel a logged session** | M | "Reception logged session by mistake, undo." Adds `pt_sessions.deleted_at` or a separate `pt_session_cancellations` table. Re-credit the balance. **RECOMMEND** ship this for v1.4 — same-day fat-finger is real, and audit captures the cancellation. Owner-only? Reception-only same-day? Flag for discuss-phase. LOW confidence on right policy. |
| **PT-session duration field** | S | `duration_minutes INT NULL`. Useful for trainer payroll later. Cheap to ship now and ignore until v1.5. |
| **PT-session note** | S | `note TEXT NULL` for "client wants to focus on legs next time" or "trainer ran 15 min late". Cheap, opinion-light. |
| **PT-session location** ("downstairs cardio room") | S | Not relevant for single-gym. Skip. |
| **Require gym check-in (visit row) on same day before allowing PT-session log** | M | A client cannot do PT without entering the gym. Linking enforces "must check in first." Trade-off: clients in real gyms sometimes do PT and skip the floor; reception might still log it. **RECOMMEND** anti-feature for v1.4 — keep PT sessions independent of visits. The two events are recorded separately; reports can later join them. Flag for discuss-phase. |

### Anti-features

| Anti-feature | Why avoid |
|---|---|
| **Trainer self-service PT-session logging** | Adds trainer auth — already noted in Category 3. |
| **PT-session scheduling / pre-booking** | Schedule milestone, not v1.4. |
| **Multi-trainer PT-session** ("two trainers ran this together") | 1:1 product. |
| **Decrement multiple sessions in one log entry** ("client did a double session, decrement 2") | Just log two rows. |
| **Tip / gratuity tracking on session** | Cash flow outside the system, owner judgement. |
| **Client signature / confirmation on session log** | Physical-world process; pet-project doesn't model it. |

---

## Dependencies on existing features

### Sale flow integration

**Question:** "Does a PT-package sale need a separate sale flow, or is it the same as membership sale with a different plan type?"

**Answer:** SAME flow. By making `pt_package` a `kind` on `membership_plans` and reusing `memberships` rows for instances, the existing `POST /api/v1/memberships` sell endpoint accepts any plan and atomically:
1. Inserts the `memberships` row with kind-discriminated snapshots (`session_count_snapshot` for pt_package, NULL for duration).
2. Inserts the `payments` row in the same transaction.
3. Emits `membership_sold` + `payment_recorded` audit events.

The sale-flow UI gets ONE new field: when `kind='pt_package'` the form shows `session_count` (read-only, derived from selected plan). The "Записать оплату" panel below is identical for both kinds.

### PT session vs visits

**Question:** "Does PT session decrement need to integrate with visits table, or is it a separate concept entirely?"

**Answer:** SEPARATE concept. PT sessions are NOT visits. A client who does a PT might or might not check in on the gym floor; a client who checks in on the gym floor might or might not do a PT. They are recorded in two different tables (`visits` vs `pt_sessions`), they decrement two different counters (the 1-per-day visit slot vs the package balance), they require different RBAC (`CHECK_IN` vs `CREATE PT_SESSION`), and they emit two different audit events.

**Discuss-phase open question:** should a PT-session log also implicitly create a visit row if there isn't one already? RECOMMEND: NO. Keep them orthogonal. Reception logs each event explicitly. If reports want "client was at the gym on day X" they UNION the two tables.

### Refunds and audit

**Question:** "Do refunds interact with audit log?"

**Answer:** YES — audit is mandatory.

A refund is THE financial event of the milestone. The audit trail is the only retroactive defence against "the system says I refunded 3 000 ₽ but the drawer is short." Every refund emits:
1. `payment_refunded` with `actor_user_id=<reception user>`, payload `(payment_id, refund_id, amount_kopecks, reason)`.
2. `membership_cancelled` with `actor_user_id=<reception user>`, payload `(membership_id, cancellation_reason='refunded')`.

Both events are added to `LOCKED_AUDIT_EVENTS` in the FIRST phase of v1.4 (mirrors v1.3's "freeze audit events locked up-front in Phase 24 before callsites land in Phases 25/26/27"). The `audit.emit` AST literal-string gate then enforces them automatically from each downstream phase's first commit.

### RBAC additions

New `(Action, Resource)` pairs:
- `(CREATE, PAYMENTS)` — implicit on sale (transaction-bundled), not separately exposed.
- `(REFUND, PAYMENTS)` — reception + owner. **NOT** in `OWNER_ONLY`.
- `(CREATE, TRAINERS)`, `(UPDATE, TRAINERS)`, `(DELETE, TRAINERS)` — owner only. ALL in `OWNER_ONLY`.
- `(LIST, TRAINERS)` — both (reception needs to pick).
- `(CREATE, PT_SESSIONS)` — reception + owner. **NOT** in `OWNER_ONLY`.
- `(CANCEL, PT_SESSIONS)` — TBD per discuss-phase (Category 5 differentiator).

### Schema migrations expected

Single migration (preferred) or thin chain (acceptable):
- `0010_payments_refunds.sql` — `payments`, `refunds`, `memberships.cancellation_reason`
- `0011_trainers.sql` — `trainers`
- `0012_pt_packages.sql` — `membership_plans.kind`, `membership_plans.session_count`, `memberships.plan_kind_snapshot`, `memberships.session_count_snapshot`, `memberships.remaining_sessions`
- `0013_pt_sessions.sql` — `pt_sessions`

Plus the carryover from PROJECT.md "Tech-debt carryover" — `mock/memberships.ts` `?status=` filter parity (one-liner).

---

## Open questions for discuss-phase

These are NOT decisions to make in research. They are flagged so the requirements step can either resolve them or explicitly defer them.

| # | Question | Default recommendation | Confidence |
|---|---|---|---|
| Q1 | **Pro-rata refund for partially-used PT-packages?** (Used 3 of 10 → refund 7/10 of price? Or 0%?) | Full refund only in v1.4; pro-rata deferred to v1.5+. | MEDIUM — full-only is operationally simpler; the gym can compensate manually if needed. |
| Q2 | **Pro-rata refund for partially-elapsed duration-memberships?** | Full refund only in v1.4. | MEDIUM |
| Q3 | **Does a PT session require a gym check-in (visit) first, or are they separate events?** | Separate events. PT session is recorded independently. | HIGH — coupling them constrains operator workflow without product gain. |
| Q4 | **Can PT sessions be cancelled / undone (e.g. trainer no-show, fat-finger logging)?** | YES — reception same-day undo; owner anytime. Audit captures the undo. | LOW — depends on whether owner trusts reception. |
| Q5 | **Multiple pt_packages in flight per client?** | NO — one active pt_package at a time. Partial unique constraint enforces. | LOW — real gyms sometimes stack packages. |
| Q6 | **Does an active pt_package alone grant gym floor access?** | NO — client needs an active duration membership to check in. PT-package is purely the PT product. | MEDIUM — RU/CIS gyms sometimes bundle "PT includes floor access on PT day". |
| Q7 | **PT-package expiry: time-based (days), count-based (sessions), or both?** | BOTH — whichever comes first. Inherits existing duration expiry cron, adds session-exhaustion transition. | MEDIUM — some gyms sell "10 sessions, no expiry"; recommendation flags this for owner choice. |
| Q8 | **Refund button when membership has visits/sessions already consumed?** | Show warning, allow proceed. Audit captures it. | LOW — could also be owner-only override. |
| Q9 | **Refund reason: free-text only, enum-only, or both?** | Both — `reason_code` enum (sickness/moving/dissatisfaction/other) + free-text `reason`. | MEDIUM — cheap to collect, valuable for v1.5 reports. |
| Q10 | **Discount field at sale time?** | NO — `payment.amount == membership.price_kopecks_snapshot` enforced. | HIGH — adding discount opens approval-workflow can of worms. |
| Q11 | **Trainer phone format — E.164 or free-text?** | Free-text. Trainers are internal; phone is contact info, not identity. | HIGH — differs deliberately from `clients.phone`. |
| Q12 | **Auto-archive trainer = soft-delete = `is_active=false`?** | YES, boolean only, no `deleted_at`. | HIGH — preserves FK chain for historical PT-sessions. |

---

## Confidence summary

| Category | Confidence | Key uncertainty |
|---|---|---|
| Payments | HIGH | Anti-features (cards, fiscal, partial pay) explicitly excluded by PROJECT.md — no ambiguity. |
| Refunds | MEDIUM-HIGH | Pro-rata question (Q1/Q2) is real but recommendation defensible. |
| Trainers | HIGH | Scope deliberately minimal — owner directory only — and PROJECT.md confirms. |
| PT Packages | MEDIUM | Reuse-`memberships`-vs-separate-table is a real architectural fork; recommendation reuses for snapshot/state-machine inheritance but could go either way. Multi-package flow (Q5) and expiry policy (Q7) are open. |
| PT Sessions | MEDIUM | Visits-coupling (Q3) and cancellation (Q4) are real workflow questions. |

## Sources

- [Resawod gym CRM features](https://resawod.com/en/gym-crm-software/) — PT package expiry & renewal reminders pattern
- [PushPress best gym CRM 2026](https://www.pushpress.com/blog/best-gym-crm-software) — PT package management & expiry tracking
- [Club-OS gym marketing software](https://www.club-os.com/features/gym-marketing-software/) — PT sales & retention model
- [Pipedrive gym CRM](https://www.pipedrive.com/en/industries/gym-crm) — Personal-trainer CRM patterns
- [The Edge Fitness Clubs payments & cancellation policies](https://www.theedgefitnessclubs.com/support/payments-billing-and-cancellation-policies) — Cash refund norms
- [Nolo: Gym membership cancellation laws & refund rights](https://www.nolo.com/legal-encyclopedia/do-i-have-to-pay-gym-membership-while-my-gym-is-temporarily-closed.html) — Industry refund norms (LA Fitness, etc.)
- [California DCA — Health club closures legal guide](https://www.dca.ca.gov/publications/legal_guides/w_9.shtml) — Refund payment-method matching norms
- Internal: `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` (v1.4 scope, explicit anti-features, RU/CIS constraints)
- Internal: v1.3 patterns (mandatory snapshot pricing, central transition guard, LOCKED_AUDIT_EVENTS pre-locking, partial unique on "open period")
