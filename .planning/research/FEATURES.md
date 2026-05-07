# Feature Research — v1.2 Memberships + Visits

**Domain:** Single-gym CRM, RU/CIS market — "Memberships catalog + per-client membership instances + reception/Telegram visit check-in"
**Researched:** 2026-05-07
**Confidence:** MEDIUM-HIGH (RU CRM market behavior triangulated from FitBase, 1С:Фитнес-клуб, fitness365, impulseCRM, Mobifitness public docs and articles; pet-project anti-fraud heuristics extrapolated from real-club practices documented in those sources)

**Goal of this document:** validate that the **locked v1.2 scope** covers daily-operations table stakes for a single-gym CRM, surface cheap wins inside the locked scope, and explicitly reject features that look reasonable but are out-of-scope traps. Categorized by **Memberships / Visits / admin-web wiring / Anti-fraud**, with complexity (S/M/L) and dependency on existing v1.1 patterns.

---

## TL;DR — Validation of locked v1.2 scope

| Locked scope item | Verdict | Reason |
|---|---|---|
| `MembershipPlan` (name + duration_days + price_kopecks + active flag) | **Sufficient** | Matches FitBase/1С "услуга/абонемент" minimum: name + срок + цена + active toggle. |
| `Membership` instance with **snapshot** of price/duration | **Correct, table-stakes** | Standard CRM pattern — price changes in catalog must not retroactively rewrite sold memberships. FitBase/1С both snapshot. |
| `start_date` = purchase date, `end_date` = `start_date + duration_days` | **Acceptable but missed table-stakes alternative** | Russian market convention is **`start_date = first visit OR fallback day N`** (1С default, FitBase opt-in). Pure purchase-date semantics is simpler but less common; **see "Activation policy" below — recommended addition: explicit `activation_policy: 'purchase_date'` constant column** so v1.3 can flip to `'first_visit'` without migration of existing rows. |
| `status: active | expired | cancelled` | **Sufficient** | Matches market norm. `frozen` deliberately deferred. |
| ARQ daily `expire_memberships` job | **Sufficient with one boundary clarification** | Need explicit decision on **end_date inclusive vs exclusive** — see "Boundary semantics" pitfall in PITFALLS.md (recommendation: inclusive — membership valid through 23:59:59 Europe/Moscow on `end_date`). |
| Manual cancel (owner-only) | **Sufficient for pet-project** | Real CRMs add proportional refund — explicitly out-of-scope per locked v1.3 deferral. v1.2 cancel = "stop counting", **no money refund logic**. |
| Reception manual check-in | **Sufficient** | Matches v1.1 pattern: search → button → audit. |
| Telegram bot `/checkin` | **Sufficient + differentiating** | RU market norm is **QR + turnstile** (Sigur/PocketKey). Telegram bot self-check-in is a cheap-win differentiator for a 1-gym pet project — no turnstile hardware required. |
| Anti-fraud: gym-hours window + 1/day/client → 409 | **Minimum viable, not "real-club grade"** | Sufficient for honest clients; weak against motivated fraud (proxy check-in, friend's phone). Real RU clubs use photo verification at turnstile + biometrics (out-of-scope). **See Anti-Fraud section below for cheap additions inside scope.** |
| `/memberships/*` + `/visits/*` admin-web routes | **Sufficient** | Mirrors v1.1 `/clients/*` wiring pattern. |
| Active sessions UI + revoke | **Out-of-scope-but-tracked, hygiene-grade** | Already-built JWT family infra exists; this is just rendering. S complexity. |

**Headline gap to surface:** v1.2 does not name an explicit **activation policy**. Without that decision encoded as a column-level constant (even if locked to one value), v1.3 will pay a migration cost. **Recommend: add `activation_policy: str = 'purchase_date'` to `Membership` schema today, even though the only allowed value in v1.2 is `'purchase_date'`.** See "Table stakes inside locked scope" item M-2.

---

## Feature Landscape

### Table Stakes (Users Expect These) — INSIDE locked scope

Features users expect from any gym CRM. These are **the locked v1.2 scope re-validated**, plus three small additions the locked scope is silent on.

#### Memberships

| Feature | Why Expected | Complexity | Notes / Dependency |
|---|---|---|---|
| **M-1. MembershipPlan catalog (owner-only CRUD)** | Every RU gym CRM has it (FitBase "Прайс абонементов", 1С "Виды услуг/Пакеты"). Reception sells from a closed list; owner edits prices/active flag. | **S** | Reuses **v1.1 module template** (`router/service/repository/schemas`) + RBAC `OWNER_ONLY` matrix (`{action: 'edit', resource: 'templates'}`). Existing `clients` migration patterns (Alembic naming convention, `MetaData(...)`, `UUIDPkMixin`/`TimestampMixin`) apply directly. Likely **soft-delete** via `SoftDeleteMixin` + partial-unique on `name WHERE deleted_at IS NULL` if name uniqueness is desired. |
| **M-2. Membership instance with price/duration snapshot** | Catalog price changes must not retroactively rewrite sold memberships. Universal in RU CRMs. | **S** | Plain columns `snapshot_price_kopecks INTEGER NOT NULL` + `snapshot_duration_days INTEGER NOT NULL`. **Recommendation: add `activation_policy VARCHAR NOT NULL DEFAULT 'purchase_date'` now** (CHECK constraint to single value `'purchase_date'`); v1.3 will widen the CHECK to include `'first_visit'`. Without this column, v1.3 needs a migration to add it AND backfill semantics. |
| **M-3. Active/expired/cancelled status enum** | Standard tri-state. Matches FitBase ("активен/закончен/расторгнут") and 1С. | **S** | `StrEnum` in `models.py`; ARQ daily job transitions `active → expired` by `end_date` comparison; manual cancel sets `status='cancelled'` + `cancelled_at = now()`. |
| **M-4. ARQ daily expiry job** | Without it, "expired" never appears — reception sees stale data. | **S-M** | First real ARQ scheduled job (skeleton exists from v1.0). Idempotent: `UPDATE memberships SET status='expired' WHERE status='active' AND end_date < CURRENT_DATE`. **Pitfall**: must run AFTER local-midnight Europe/Moscow (see PITFALLS). |
| **M-5. Manual cancel (owner-only)** | Required for "клиент сдал, верну позже / медотвод / переезд". | **S** | RBAC: add `{action: 'cancel', resource: 'memberships'}` to `OWNER_ONLY`. `cancelled_at` timestamp + audit row. **No proportional refund** in v1.2 (deferred to v1.3 billing). |
| **M-6. Audit-log writes (create/cancel/expire)** | v1.1 pattern; without it, "who cancelled this" is unanswerable. | **S** | Reuse v1.1 `audit_log` writer. ARQ-driven `expire` events: log with `actor_user_id = NULL, actor_kind = 'system'`. |

#### Missing-but-trivial (recommended additions inside locked scope)

| Feature | Why It's Table-Stakes | Complexity | Recommendation |
|---|---|---|---|
| **M-7. `paid_at` timestamp on Membership** | Owner sells today — needs to know "когда продал" for end-of-month informal reporting (no billing module yet). 1С/FitBase always store this. | **S** | One nullable timestamp column, set by `POST /memberships`. Even without ЮKassa, this is the seed for v1.3 billing reconciliation. |
| **M-8. `activation_policy` column with single allowed value** | See M-2 — guards v1.3 migration cost. | **S** | `VARCHAR NOT NULL DEFAULT 'purchase_date' CHECK (activation_policy = 'purchase_date')`. Schema-level placeholder. |
| **M-9. `notes` free-text column on Membership** | Reception inevitably needs "оплатил наличными", "акция 1+1", "перенос с прошлого зала". Universal in RU CRMs. | **S** | `TEXT NULL`. No semantic logic; just storage. |

#### Visits

| Feature | Why Expected | Complexity | Notes / Dependency |
|---|---|---|---|
| **V-1. Reception manual check-in (search → button)** | Mirrors v1.1 `/clients/*` UX exactly: ILIKE search → list → action button. | **S** | Reuses `pg_trgm` GIN-indexed search + LIKE-escape from CR-01. New endpoint `POST /visits/check-in` with body `{client_id, channel: 'reception'}`. |
| **V-2. Telegram self check-in `/checkin`** | Anti-stakes for v1.2 differentiation. | **M** | Extends existing ptb-22 long-polling worker (Phase 7). Bot resolves `telegram_chat_id → user → client_id`, calls internal service, replies "✅ Отмечено в HH:MM". Cross-module callback via Protocol (existing pattern). |
| **V-3. Active-membership validation** | Without it, expired clients can self-check-in. | **S** | Service-layer guard: `SELECT 1 FROM memberships WHERE client_id = :id AND status='active' AND CURRENT_DATE BETWEEN start_date AND end_date`. **409 Conflict** if no active membership; bot replies "❌ Активный абонемент не найден". |
| **V-4. Anti-fraud: 1 visit per day per client** | Universal "1 заход в день" cap in RU clubs (premierfit/dorfit рули правила). Without it, accidental double-tap creates noise. | **S** | DB-level: partial unique index `UNIQUE (client_id, (checked_in_at::date AT TIME ZONE 'Europe/Moscow'))`. On conflict → 409. |
| **V-5. Anti-fraud: gym-hours window** | Server-time `08:00–23:00 Europe/Moscow` from env. Outside → 409. | **S** | Env var `GYM_HOURS_START=08:00 / GYM_HOURS_END=23:00`. Service-layer check before insert. **Note**: must use `Europe/Moscow` zone-aware comparison, not UTC. |
| **V-6. Audit-log writes** | v1.1 pattern. | **S** | `actor_user_id` for reception channel; `actor_kind='telegram_bot'` for bot channel. |
| **V-7. Visit-history per client** | Reception needs "когда был последний раз". Standard in every RU CRM. | **S** | Read-only endpoint `GET /clients/:id/visits?limit=20`; renders in client-detail page. |

### Differentiators (Cheap-Win, FIT inside locked scope)

These are not in the explicit locked-scope text but are **computed views over already-locked data** — no new tables, no new domain concepts, very small backend code, clear daily-operations value. Owner saves money on a turnstile by getting these for free in admin-web.

| Feature | Value Proposition | Complexity | Notes / Dependency |
|---|---|---|---|
| **D-1. "Кто сейчас в зале" (currently checked-in)** | Reception/owner glanceable: "сейчас 7 человек". RU CRM staple — Gymdesk/PushPress have it; FitBase displays via attendance dashboard. | **S** | Pure read: `SELECT clients.* FROM visits JOIN clients ON ... WHERE checked_in_at::date = CURRENT_DATE AT TIME ZONE 'Europe/Moscow'`. **No "checkout"** event is in scope, so this is "checked in today" — adequate for a 1-gym pet project where physical presence is loosely tracked. Display as a card on the visits index page. |
| **D-2. "Истекает сегодня / на этой неделе" filter** | Owner runs this once per morning to pre-emptively call clients before silence-churn. Universal upsell hook in RU CRMs. | **S** | Pure read: `SELECT * FROM memberships WHERE status='active' AND end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7`. Add as `?expiringWithinDays=N` query param on `GET /memberships`. **No notifications** — just a filter (notifications deferred to v1.3). |
| **D-3. "Истёк сегодня" filter** | Critical UX moment: client walks in expecting to train, reception sees "истёк сегодня" badge in red, can immediately offer renewal. Without it, reception sees just "expired" with no urgency cue. | **S** | Computed badge in admin-web: if `end_date == today` AND `status='expired'` → render "истёк сегодня" red badge. Pure frontend — no backend change. |
| **D-4. "Renewal stack" — chronological plan history per client** | When client renews 5×, reception needs to see "купил 30-day → 90-day → 90-day → ..." chronologically. Trivial join, but **only valuable if rendered as a timeline** in client-detail. Builds trust ("система помнит всё"). | **S** | Pure read; existing `GET /clients/:id` enrichment OR separate `GET /clients/:id/memberships`. Render as vertical timeline in client-detail tab. |
| **D-5. Telegram bot reply enrichment: "до конца N дней"** | When bot replies "✅ Отмечено", append "Абонемент действует ещё 12 дней" — trivial computation, but converts every check-in into a passive churn-prevention nudge. | **S** | Compute `(end_date - CURRENT_DATE).days` server-side, include in bot reply text. Especially valuable when N ≤ 7 (urgency nudge). |
| **D-6. Reception view: "сегодняшние посещения" log** | End-of-shift reception wants to see "кого я сегодня отмечал" for handoff. Standard in 1С. | **S** | `GET /visits?date=today&channel=reception&actor=:current_user_id`. List view with timestamps. |
| **D-7. Membership "снимок" view (sold-with-these-prices)** | Owner runs catalog price increase, then 3 months later wonders "сколько у меня клиентов на старой цене". Snapshot column already exists (M-2) — only needs a filter UI: "Активные мемберы по проданной цене". | **S** | `GET /memberships?soldPriceMin=...&soldPriceMax=...`. Pure SQL filter. |

### Anti-Features (DO NOT BUILD in v1.2 — explicit reject list)

These are features that look reasonable for a "gym CRM" but cost a lot for a single-gym pet-project. **Each is documented here so v1.2 planners can point at this list when stakeholders ask.**

| Feature | Why Requested | Why Problematic for v1.2 | Alternative / When to Reconsider |
|---|---|---|---|
| **AF-1. Per-class booking / group lessons** | "Mindbody has it" / "FitBase has it". | Requires `Schedule` + `Class` + `Booking` + `Trainer` modules — at minimum 4 new entities, calendar UX (react-big-calendar wiring), waitlists, no-show penalties. Multiplies v1.2 LOC ~3×. | Wait for v1.3+ (already reserved as "trainers / schedule / bookings — TBD" in PROJECT.md). v1.2 ships **time-based** memberships only — no per-class accounting. |
| **AF-2. Family / corporate memberships (one plan, many clients)** | "Семейная карта на двоих, со скидкой". | Requires N:M between `Membership` and `Client`, "primary holder" semantics, billing distribution, per-member visit attribution. Doubles complexity of every membership query. | Single-client memberships only in v1.2. If owner sells to 2 family members, owner sells 2 memberships. Reconsider only if owner brings real demand and business case. |
| **AF-3. Visit-count plans ("10 занятий")** | RU market norm — "пакет на 10/20/30 занятий". | Need decrementing counter, lifecycle "5 of 10 used → 0 of 10 used → expired by count OR by date (whichever first)", refund-on-cancel proportional to unused visits. Cancel-with-partial-use multiplies edge cases. **Already explicitly deferred** in PROJECT.md to v1.3. | v1.2 only ships time-based plans. v1.3 can add `plan_kind: 'time' | 'count'` discriminator. |
| **AF-4. Membership freeze / pause** | RU market table-stakes for **commercial** clubs ("заморозка на отпуск"). | Requires extra state (`frozen`), freeze-window tracking (start/end of pause), end-date arithmetic ("end_date += paused_days"), per-day idle-extension policies. **Already explicitly deferred** in PROJECT.md to v1.3. | Not in v1.2. If owner of pet-project gym wants it informally, owner extends `end_date` manually — no UX. v1.3 introduces real freeze. |
| **AF-5. Proportional refund on cancel** | Russian consumer protection law (ст. 32 ЗоЗПП) requires proportional refund on early cancel. | Requires money math, paid_amount tracking with billing trail, and **really** wants ЮKassa refund integration. v1.2 has no billing module. | v1.2 cancel = "stop counting"; owner handles real-money refund out-of-band (cash or bank transfer). v1.3 billing module owns refund logic. **Document this constraint visibly in admin-web cancel dialog**: "Это не вернёт деньги клиенту — обработайте возврат отдельно". |
| **AF-6. Expiring-soon notifications (Telegram DM, email, SMS)** | Every commercial CRM has it. | Requires notification scheduling (ARQ), per-client opt-in, deduplication ("не слать дважды в один день"), template management, GDPR/152-ФЗ consent tracking. **Already explicitly deferred** in PROJECT.md. | v1.2 ships D-2 ("expiring filter") instead — owner pulls instead of system pushes. Achieves 80% of the value at 5% of complexity. |
| **AF-7. Per-trainer commission / payroll on membership sale** | "Тренер должен получить % с проданного абонемента". | Requires Trainer module (not in v1.2), commission rules engine, payroll calc. RBAC `OWNER_ONLY` already blocks reception from `compensation` resource — keep it that way. | v1.3+ trainers module. v1.2 memberships have no `sold_by_trainer_id`. |
| **AF-8. CSV import of legacy memberships** | "У меня есть Excel с 200 клиентами и их датами окончания". | Bulk import of dated/snapshot data is a UX rabbit hole (validation errors per row, partial commits, idempotent re-runs). | v1.2 reception types them in. v1.3 ships CSV import (already deferred in PROJECT.md). For 1-gym pet project, manual entry of <200 rows is one-evening's work; building robust CSV import is a week. |
| **AF-9. Photo upload on client / facial verification at check-in** | Real RU clubs do this (1С:Фитнес + PocketKey/Sigur — see Anti-Fraud section). | Requires file storage (S3-compatible, MinIO?), image processing, EXIF stripping, GDPR/152-ФЗ implications. **Already explicitly deferred** in PROJECT.md. | v1.2 ships text-only. The TG-bot self-check-in differentiates **without** turnstile hardware — that's the v1.2 value prop. |
| **AF-10. Live websocket "currently in gym" auto-refresh** | "Хочу видеть в реальном времени". | Websocket infra cost (sticky sessions, scaling, FastAPI websocket lifecycle, frontend reconnect logic) for a 1-gym pet project where peak occupancy is ~20 people and reception refreshes the page anyway. | v1.2 D-1 ships as **stale-30s React Query auto-refresh**. Reception clicks refresh. Sufficient. v2+ websocket only if >100 concurrent visits. |
| **AF-11. Multi-gym scoping (`gym_id` on every table)** | "А вдруг откроется второй зал?" | **Explicitly out-of-scope** in PROJECT.md ("Multi-tenancy — добавим только когда появится второй покупатель"). Every preemptive scoping column is structural debt that bleeds through every query. | Add `tenant_id` columns ONLY when second gym is real and paying. Until then, single-tenant assumption. |
| **AF-12. Audit-log read API + UI** | Owner wants to see "кто что сделал". | Already exists in `audit_log` table (writes only). Read API + UI is its own slice with filters, pagination, PII concerns, retention. **Already deferred** in PROJECT.md to v1.3+. | v1.2 audit is write-only — debugging via direct SQL access. v1.3 ships read UI. |

### Anti-Fraud — what real RU gyms actually do, and what fits inside v1.2

**Question from prompt:** Is `gym-hours window + 1/day` enough?

**Verdict:** **Sufficient for an honest single-gym pet project; insufficient against motivated fraud. The locked scope is correct for v1.2 — do not over-engineer.**

#### Real-club fraud landscape (RU/CIS)

Distilled from FitBase, 1С:Фитнес, fitness365, Sigur public docs:

| Fraud vector | Real-club countermeasure | v1.2 self-check-in exposure | v1.2 mitigation |
|---|---|---|---|
| **Friend's card / proxy entry** ("даю свою карту другу") | (a) Photo on file shown to admin at turnstile; (b) facial recognition at turnstile; (c) biometric (fingerprint/palm vein) — 1С + PocketKey/Sigur. | TG-bot `/checkin` is **bound to `telegram_chat_id`** (verified during v1.1 OTP flow → upsert by chat_id). To proxy-check-in, friend would need access to the client's Telegram account. Higher friction than swiping a card. | **Already strong** — Telegram account compromise is a much higher bar than card swap. **Reception manual check-in is the weak spot** (administrator can fake a check-in for a friend) — see CR-mitigations below. |
| **Replay / duplicate check-in** ("отметился, а потом ещё раз через 5 минут") | DB unique constraint on `(client_id, date)`. | Locked: 1/day partial unique index. | **Already adequate** — V-4 covers this. |
| **Off-hours sneak-in** ("пришёл в 7:00, зал работает с 8") | Turnstile schedule + access-list. | Locked: gym-hours window. | **Already adequate** — V-5 covers this. Note: server time, not client local time. |
| **Reception-administrator collusion** ("админ отмечает свою подругу без абонемента") | (a) `Membership` validation BEFORE check-in (system blocks if expired); (b) audit-log + retro-review by owner; (c) photo verification. | Reception can `POST /visits/check-in {client_id}` for any client with active membership; can fake-check-in a real member's record (no money cost, but inflates visit data). | **Acceptable for v1.2** because: (1) `Membership` validation already blocks check-in for clients without active membership — admin can't conjure fake clients; (2) audit-log records `actor_user_id` — owner can retro-review; (3) for 1-gym pet project the single owner often IS the reception, so "collusion" is inapplicable until staff grows. |
| **Expired-but-walked-in client** ("истёк сегодня, реcепшн пропускает") | System hard-blocks at turnstile. Some clubs allow grace window via "истекает сегодня" amber badge but require manual override + audit. | Depends on **boundary semantics** (see PITFALLS.md). Locked: `end_date < CURRENT_DATE` → expired by ARQ. So `end_date == today` is **still active** until midnight. **This is correct behavior** for client UX; reception sees green "active". | **Already adequate** — ARQ daily job runs after midnight, so client whose `end_date == today` can train all day. Surface "истекает сегодня" badge (D-3 differentiator) so reception can offer renewal at the door. |

#### Cheap anti-fraud additions that fit inside locked scope

| Addition | Cost | Value |
|---|---|---|
| **AF-cheap-1. `channel` column on Visit (`reception | telegram_bot`)** | **Already in locked scope.** | Owner can audit-review by channel: "сколько отметок reception сделал сам, без TG-подтверждения от клиента" — high-friction reception fraud signal. |
| **AF-cheap-2. `checked_in_by` column = the User who actioned** | **Already in locked scope.** | For reception channel = staff user_id; for telegram_bot channel = NULL or the client's user_id. Audit-log dedup: who clicked. |
| **AF-cheap-3. Hard-block check-in if Membership.status != 'active'** | S — already implied in V-3. | Admin cannot bypass UI to check in expired client without first reactivating the membership (which is owner-only). Cuts reception-admin collusion vectors. |
| **AF-cheap-4. Daily summary log line per visit (structlog)** | S — reuses v1.0 structlog infra. | `event=visit.checked_in client_id=... channel=... actor=...` — owner greps logs, retroreview. |
| **AF-cheap-5. Telegram bot replies with timestamp + days-remaining** | S (already D-5). | Two-way confirmation: client sees "✅ Отмечено в 18:42, 12 дней до окончания" — if reception fakes a check-in for that client, the client doesn't get the message and can complain. Cheap accountability layer **only on telegram_bot channel**. |

**What we explicitly DO NOT add for anti-fraud in v1.2:**

- IP/device-binding for TG-bot check-in (overkill; bot already binds to `telegram_chat_id`)
- Geofencing ("you must be within 100m of the gym to /checkin") — requires location handler, privacy implications, false negatives (bad GPS indoors)
- Photo verification at reception (out-of-scope per PROJECT.md anti-features)
- "Two-step" admin check-in requiring client TG confirmation (creates UX friction; v1.2 reception channel must remain a single click)

---

## Feature Dependencies

```
M-1 (MembershipPlan)
  └──required-by──> M-2 (Membership instance, snapshots from plan)
                       ├──required-by──> M-3 (status enum)
                       │                    └──required-by──> M-4 (ARQ expire job)
                       ├──required-by──> M-5 (manual cancel)
                       └──required-by──> V-3 (active-membership validation)

V-1 (reception check-in) ──independent──> V-2 (TG bot check-in)
   both depend on V-3 (active-membership validation)
   both required-by V-4 (1/day unique) + V-5 (gym hours)
   both required-by V-6 (audit) + V-7 (visit history)

D-1 ("currently in gym") ──reads──> Visit table — pure-read, no schema change
D-2 ("expiring soon") ──reads──> Membership table — pure-read, parameterized query
D-3 ("expired today" badge) ──reads──> Membership(status, end_date) — pure-frontend
D-4 (renewal stack) ──reads──> Membership filtered by client_id — pure-read
D-5 (TG-bot days-remaining reply) ──reads──> Membership.end_date — text concatenation
D-6 (today's visits) ──reads──> Visit filtered by date+channel — pure-read
D-7 (snapshot price filter) ──reads──> Membership.snapshot_price — pure-SQL filter

M-7 (paid_at) ──seed-for──> v1.3 billing reconciliation
M-8 (activation_policy column) ──seed-for──> v1.3 first-visit activation
```

### Critical Notes

- **M-1 must ship before any Membership-instance work** because instance schema imports plan_id FK.
- **M-2 + M-8 should ship in same migration** — adding `activation_policy` later means backfilling existing rows.
- **V-3 (active-membership validation) is the critical join** between Memberships and Visits modules. It must be a **service-layer call**, not a direct cross-module SQL query, to preserve `modules-independent` import-linter contract. Use the existing v1.1 cross-module Protocol pattern (`HandlerContext`-style).
- **D-1 through D-7 are all post-MVP polish** — none block the v1.2 ship. Recommend cutting any that don't fit phase budget; D-3 + D-2 are the highest ROI.
- **AF-cheap-1 + AF-cheap-2 are already inside locked scope** — they're columns on `Visit`. Just make sure they're queried in the audit views (D-6).

---

## MVP Definition (for v1.2)

### Launch With (locked v1.2 — the minimum viable slice)

#### Memberships module

- [x] **M-1** — `MembershipPlan` CRUD (owner-only)
- [x] **M-2** — `Membership` instance with `snapshot_price_kopecks` + `snapshot_duration_days`
- [+] **M-2-add** — also add `activation_policy VARCHAR DEFAULT 'purchase_date' CHECK (...)` column **even though only one value is allowed in v1.2** (zero-cost forward compat with v1.3 first-visit activation)
- [x] **M-3** — status `active|expired|cancelled`
- [x] **M-4** — ARQ daily `expire_memberships` job
- [x] **M-5** — manual cancel (owner-only)
- [x] **M-6** — audit-log writes (create / cancel / expire)
- [+] **M-7-add** — `paid_at` timestamp column on Membership (one column; seeds v1.3 billing)
- [+] **M-9-add** — `notes` TEXT NULL on Membership (one column; cost = nothing, daily-ops value high)

#### Visits module

- [x] **V-1** — reception manual check-in via admin-web
- [x] **V-2** — Telegram bot `/checkin` (extends existing ptb-22 worker)
- [x] **V-3** — active-membership validation (cross-module via Protocol callback)
- [x] **V-4** — 1/day partial unique index on `(client_id, checked_in_at::date AT TIME ZONE 'Europe/Moscow')`
- [x] **V-5** — gym-hours window from env (`GYM_HOURS_START` / `GYM_HOURS_END`, Europe/Moscow)
- [x] **V-6** — audit-log writes
- [x] **V-7** — visit-history per client

#### admin-web wiring (`VITE_API_MODE=http`)

- [x] `/memberships/plans` — owner-only CRUD list/form
- [x] `/memberships` — list of all memberships (filter by status, by client name search via existing v1.1 ILIKE)
- [x] `/visits` — today's-visits list (filter by date/channel)
- [x] `/visits/check-in` — search-and-button page
- [x] client-detail enhancements — Memberships tab + Visits tab
- [x] Active sessions UI + revoke (renders existing JWT-family data)

#### Hygiene

- [x] CR-01: Argon2 verify-error → 401 (not 500)
- [x] CR-02: invalid UUID in cookie → 401 (not 500)

### Add If Phase Budget Permits (cheap-win differentiators)

Strongest ROI first — pick top-N from this list per phase budget:

- [+] **D-3** — "истёк сегодня" red badge in admin-web membership list (pure frontend, S)
- [+] **D-2** — "истекает в течение N дней" filter (1 query param + 1 frontend filter UI, S)
- [+] **D-5** — TG-bot reply enrichment "до конца N дней" (1 line of bot code, S)
- [+] **D-1** — "Кто сейчас в зале" card on visits page (1 query, S)
- [+] **D-4** — renewal stack timeline in client-detail (1 query, S frontend timeline component)
- [+] **D-6** — today's-visits log filtered by current reception user (1 query param, S)
- [+] **D-7** — filter by snapshot-price range (1 query, S)

### Defer to v1.3+ (already on PROJECT.md deferred list)

- [ ] AF-3: visit-count plans
- [ ] AF-4: freeze
- [ ] AF-5: proportional refund (depends on billing module)
- [ ] AF-6: expiring-soon notifications (Telegram DM, email)
- [ ] AF-8: CSV bulk import
- [ ] AF-9: photo upload, biometrics
- [ ] AF-12: audit-log read API + UI
- [ ] Billing / ЮKassa integration
- [ ] Trainers / schedule / bookings module(s)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| M-1 MembershipPlan CRUD | HIGH | LOW | **P1 (locked)** |
| M-2 Membership instance + snapshots | HIGH | LOW | **P1 (locked)** |
| M-2-add activation_policy column placeholder | LOW (now) HIGH (v1.3) | LOW | **P1 (recommended add)** |
| M-3 status enum | HIGH | LOW | **P1 (locked)** |
| M-4 ARQ daily expire | HIGH | MEDIUM | **P1 (locked)** |
| M-5 manual cancel | HIGH | LOW | **P1 (locked)** |
| M-6 audit | HIGH | LOW | **P1 (locked)** |
| M-7 paid_at column | MEDIUM | LOW | **P1 (recommended add)** |
| M-9 notes column | MEDIUM | LOW | **P1 (recommended add)** |
| V-1 reception check-in | HIGH | LOW | **P1 (locked)** |
| V-2 TG-bot check-in | HIGH | MEDIUM | **P1 (locked)** |
| V-3 active-membership validation | HIGH | LOW | **P1 (locked)** |
| V-4 1/day unique | HIGH | LOW | **P1 (locked)** |
| V-5 gym-hours | MEDIUM | LOW | **P1 (locked)** |
| V-6 audit | HIGH | LOW | **P1 (locked)** |
| V-7 visit history | HIGH | LOW | **P1 (locked)** |
| D-1 currently in gym | MEDIUM | LOW | **P2** |
| D-2 expiring-soon filter | HIGH | LOW | **P2 (highest ROI add)** |
| D-3 "истёк сегодня" badge | HIGH | LOW | **P2 (highest ROI add)** |
| D-4 renewal stack timeline | MEDIUM | LOW | **P2** |
| D-5 TG-bot days-remaining | MEDIUM | LOW | **P2** |
| D-6 today's-visits per-user log | LOW | LOW | **P3** |
| D-7 snapshot-price filter | LOW | LOW | **P3** |
| Active sessions UI + revoke | MEDIUM | LOW | **P1 (locked)** |
| CR-01/CR-02 hygiene | HIGH (security) | LOW | **P1 (locked)** |

**Priority key:**
- **P1**: Must have for v1.2 (locked scope + zero-cost forward-compat columns)
- **P2**: Should have, add if phase budget permits — pick top 3-4 by ROI (recommend D-2, D-3, D-5, D-1)
- **P3**: Nice to have, defer if pressed for time

---

## Competitor Feature Analysis (RU/CIS market)

| Feature | FitBase | 1С:Фитнес-клуб | fitness365 | Our v1.2 Approach |
|---|---|---|---|---|
| Activation policy (purchase vs first-visit) | Configurable per plan: "Активация с первого посещения" toggle (default OFF in some plans, ON in others) | Configurable per plan: "при первом посещении / в день покупки", with "but no later than N days" auto-activation fallback | Service-snapshot model | **v1.2: purchase-date only, but `activation_policy` column placeholder ships now** |
| Snapshot of price at sale | Yes — historical price preserved | Yes — `Пакет услуг` snapshots | Yes | **v1.2: yes — `snapshot_price_kopecks`, `snapshot_duration_days`** |
| Freeze / pause | Yes — first-class feature with date-range tracking | Yes — first-class | Yes | **v1.2: explicitly NO (deferred to v1.3)** |
| Visit-count plans (10/20/30 sessions) | Yes — first-class | Yes — `Виды услуг` discriminator | Yes | **v1.2: explicitly NO (time-based only)** |
| Self check-in | Mobile app (FitBase mobile), QR code at gym | Mobile app, QR code, integrations with Sigur/PocketKey/Gantner turnstiles | Mobile app | **v1.2: Telegram bot `/checkin` (no app, no QR, no turnstile)** — differentiator-by-omission |
| 1/day cap | Yes (configurable per plan: "лимит посещений в день") | Yes (per-plan limit) | Yes | **v1.2: hardcoded 1/day at DB level** |
| Gym-hours window | Yes (per-plan time-band: "утренний абонемент 06–17") | Yes | Yes | **v1.2: single global window from env** |
| Photo at turnstile | Yes (admin-screen photo verification) | Yes (admin-screen + turnstile photo cross-check) | Yes | **v1.2: NO (anti-feature for pet project)** |
| Biometric (fingerprint, palm vein, face) | No (third-party integration) | Yes (Sigur, PocketKey, Gantner integrations) | Limited | **v1.2: NO** |
| Currently-in-gym dashboard | Yes | Yes | Yes | **v1.2: D-1 cheap-win — read-only counter, no real-time updates** |
| Expiring-soon Telegram notification | Yes (push to mobile app + Telegram bot) | Yes | Yes | **v1.2: NO push — D-2 filter (pull-mode)** |
| Cancel with proportional refund | Yes (with billing integration) | Yes | Yes | **v1.2: cancel without refund (no billing module)** |

**Sportzal v1.2's positioning:** **"Single-gym, owner-operated, no turnstile, no biometrics, no payments — but every honest daily-ops scenario covered, with full audit and Telegram-bot self-check-in"**. Trades enterprise features for radical simplicity, suitable for one-gym pet project; differentiates from Russian commercial CRMs by **not** requiring hardware. The locked v1.2 scope correctly identifies this niche.

---

## Sources

### Russian gym CRM market (primary references)

- [FitBase: "Шаг 4. Как создать прайс абонементов"](https://help.fitbase.io/article/16064) — plan catalog model
- [FitBase: "Как запустить клиента в клуб и отметить посещение"](https://help.fitbase.io/article/3811) — check-in UX reference
- [FitBase: "Обновление CRM 15.08.2023"](https://fitbase.io/blog/update15082023) — "активация с первого посещения" toggle and freeze interaction with future-dated cards
- [FitBase: возможности](https://fitbase.io/capabilities) and [Mobifitness: CRM](https://mobifitness.ru/crm/) — feature surface area benchmark
- [1С:Фитнес-клуб — Настройка услуг](https://1eska.ru/projects/publications/1s-fitnes-klub/kak-nastroit-vidy-uslug-v-1s-fitnes-klub/) — service kinds, activation policies, "but no later than N days" fallback
- [1С:Фитнес-клуб — создание пакета услуг и членства](https://www.fitness1c.ru/knowledge-base/prodazhi/nomenklatura/sozdanie-paketa-uslug/) — snapshot pattern + plan→instance separation
- [1С:Фитнес-клуб — пробная тренировка](https://www.fitness1c.ru/knowledge-base/prodazhi/nomenklatura/probnaya-trenirovka/) — alternative entry-flow patterns
- [1С:Фитнес-клуб — главная](https://www.fitness1c.ru/) and [PocketKey integration](https://www.fitness1c.ru/integration-pocketkey) — turnstile/biometric integration landscape
- [1С:Фитнес-клуб — "Как пресечь воровство и махинации сотрудников"](https://www.fitness1c.ru/blog/kak-presech-vorovstvo-i-mahinatsii/) — RU-club fraud taxonomy + countermeasures
- [fitness365: "Как пресечь мошенничество и воровство в фитнес клубе"](https://support.fitness365.ru/база-знаний/мошенничество-в-клубе/) — manager vs admin RBAC, "deception revealed on next visit" pattern (HTTPS cert issue prevented WebFetch deep-read; cited from search snippet)
- [fitness365: абонементная и клубная системы](https://support.fitness365.ru/documentation/руководство-администратора/абонементная-и-клубная-системы/) — visit-cap-per-day plans
- [impulseCRM: возврат денег за абонемент](https://impulsecrm.ru/news/vozvrat-deneg-za-sportivnyy-abonement) — RU consumer-protection law constraints on cancel/refund (anti-feature AF-5 justification)
- [impulseCRM: запись клиентов](https://impulsecrm.ru/vozmozhnosti/zapis-klientov) — self-registration widget patterns
- [Sigur: решение для фитнесов](https://sigur.com/solutions/fitness/) — turnstile + photo + biometric integration patterns (anti-feature AF-9 justification)

### English-market gym CRM (reference, secondary — confirms table-stakes universality, not RU specifics)

- [Gymdesk: attendance tracking](https://gymdesk.com/features/attendance) and [reporting](https://gymdesk.com/features/reporting) — live attendance dashboard pattern (D-1)
- [PushPress](https://www.pushpress.com/) and [GymMaster](https://www.gymmaster.com/) — feature surface benchmark
- [Mindbody-style ClubOS](https://www.club-os.com/) — class-based booking model (anti-feature AF-1 justification)

### Russian consumer law / market context

- [Russian fraud schemes in fitness apps (РИА Новости 2026-05-06)](https://ria.ru/20260506/moshenniki-2090727656.html), [Известия 2026-05-06](https://iz.ru/2091859/2026-05-06/v-mvd-rasskazali-o-novoi-skheme-moshennikov-s-utechkoi-dannykh-iz-fitnes-klubov) — current RU threat landscape (data-leak driven, not in-club fraud)
- [advgazeta: возврат денег за абонемент фитнес-центра](https://www.advgazeta.ru/ag-expert/advices/kak-poluchit-obratno-dengi-pri-vozvrate-abonementa-fitnes-tsentra/) — proportional refund obligation
- [Сеть клубов Премьер-Фит правила посещения](https://www.premierfit.ru/pravila-poseshcheniya-fitnes-kluba), [DorFit правила](https://dorfit.ru/pravila-posesheniya.html) — typical RU club rules, including 1-2-visits-per-day max

### Internal references

- `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` — locked v1.2 scope, Out of Scope list, Key Decisions
- `/Users/andre/Workspace/Development/clubcore/.planning/MILESTONES.md` — v1.1 patterns (module template, audit-log, RBAC byte-parity, OpenAPI drift gate, partial unique index, ARQ skeleton, Telegram OTP worker)
- `/Users/andre/Workspace/Development/clubcore/apps/admin-web/src/shared/session/can.ts` — RBAC `OWNER_ONLY` matrix; v1.2 will add `{action: 'cancel', resource: 'memberships'}` and possibly `{action: 'edit', resource: 'memberships'}` for plan catalog (re-using existing `templates` resource is also acceptable)
- `/Users/andre/Workspace/Development/clubcore/apps/admin-web/CLAUDE.md` — frontend conventions (FSD-lite, Zod-shared schemas, RHF, money in kopecks, dates ISO + Europe/Moscow)

---

*Feature research for: Sportzal v1.2 — Memberships + Visits (single-gym, RU/CIS market, owner+reception roles, Telegram-bot self-check-in)*
*Researched: 2026-05-07*
*Confidence: MEDIUM-HIGH — RU-market feature norms triangulated from multiple primary sources (FitBase, 1С, fitness365, impulseCRM); pet-project anti-fraud heuristics extrapolated rather than primary-sourced (LOW-MEDIUM confidence on anti-fraud "what real clubs actually do day-to-day" but HIGH confidence on "what features exist in the CRM products").*
