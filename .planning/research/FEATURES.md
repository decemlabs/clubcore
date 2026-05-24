# Feature Research

**Domain:** Trainer completion for single-gym CRM (payroll ledger, recurring schedule, time-off, trainer-utilization report)
**Researched:** 2026-05-24
**Confidence:** HIGH (domain patterns are well-understood; specific design choices align with existing codebase bedrock)

---

## Context: What Already Exists

Before defining new features, the existing bedrock constrains every design decision below:

- **`trainers` table** — `id`, `full_name`, `phone`, `is_active`, `deleted_at`. Soft-deactivate via `is_active`; hard-delete via `deleted_at` partial-unique discipline.
- **`trainer_availability_slots` table** — `trainer_id`, `start_time`, `end_time`, `status` (`active`/`booked`/`cancelled`), `created_by_user_id`, `cancelled_at`, `cancel_reason`. Manual one-off slots only.
- **`pt_sessions` table** — `pt_package_id`, `trainer_id`, `client_id`, `performed_at`, `trainer_name_snapshot`, `booking_id` (nullable). FK to `bookings`. Index `ix_pt_sessions_trainer_id_performed_at_desc` already exists for load analytics.
- **`bookings` table** — `slot_id` → `trainer_availability_slots`. FSM: `confirmed → cancelled / no_show / completed`.
- **`payments` table** — append-only ledger; `subject_kind ∈ ('membership', 'pt_package', 'refund')`, signed `amount_kopecks`, `method`, `received_at`. No `UPDATE`/`DELETE` allowed (AST gate). `subject_kind` CHECK constraint will need extending for payroll accruals.
- **`audit_log` table** — `LOCKED_AUDIT_EVENTS` frozenset, AST literal-string gate. New events must be pre-registered before callsites.
- **`app/modules/reports/`** — v1.8 read-only discipline: no `models.py`, raw-SQL `text()` cross-module reads, zero writes.
- **RBAC** — `Resource`/`Action`/`OWNER_ONLY` with byte-parity across backend + `admin-web/src/shared/session/can.ts` + `registry.ts`.

---

## CATEGORY A — PAYROLL

### PAY-01: Per-trainer compensation model configuration
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** `trainers` table (existing)
- **Description:** Each trainer needs a configurable compensation model. Industry practice (confirmed): most small gyms use one of three models — % of PT-package revenue, fixed amount per conducted session, or both combined. For Sportzal single-gym scope, all three configurations are needed on a per-trainer basis. Configuration lives on the trainer record itself (two nullable columns: `commission_pct` NUMERIC(5,2) and `session_fee_kopecks` INTEGER). Both columns being NULL means "no payroll computed for this trainer" (e.g., salaried employee managed outside the CRM). Either or both can be set simultaneously (hybrid model). Commission % applies to the `amount_kopecks` of PT-package sale payments linked to sessions this trainer conducted. Session fee applies to each non-cancelled `pt_sessions` row for this trainer.
- **New schema:** Two nullable columns on `trainers` table via Alembic migration. No new table needed.
- **RBAC:** Owner-only `PATCH /api/v1/trainers/{id}` already exists; extend schema to include new fields. Reception reads `is_active` only (existing behavior unchanged).
- **Single-gym scope note:** Tiered commission (e.g., "40% up to $5K/mo, 45% above") is an enterprise feature. Not needed. Single flat rate per trainer.

### PAY-02: Payroll period computation (the "payroll run")
- **Category:** Table stake
- **Complexity:** MEDIUM
- **Dependency:** PAY-01 (compensation config); `pt_sessions` (non-cancelled, `performed_at` in period); `payments` (PT-package sale rows linked to sessions via `pt_package_id`); Europe/Moscow TZ discipline
- **Description:** Owner requests a payroll computation for a trainer over a date range (e.g., "1–31 May 2026 MSK"). The computation:
  1. Selects all non-cancelled `pt_sessions` where `trainer_id = ?` AND `performed_at` falls within the period (Europe/Moscow).
  2. For `session_fee_kopecks`: count × fee = fixed component.
  3. For `commission_pct`: find the PT-package sale payment for each session's `pt_package_id` (JOIN `payments WHERE subject_kind='pt_package' AND subject_id=pt_package_id`), sum `amount_kopecks`, apply `commission_pct`. Note: one PT-package payment covers multiple sessions; commission is typically computed on the full package sale price attributed to sessions in the period, NOT per-session proration. **Decision for Sportzal:** commission is applied to the total PT-package sale revenue (the payment row) where at least one session from that package falls in the period. This avoids a "proration per session" complexity that has no single right answer. This is the typical small-gym interpretation.
  4. Total accrual = fixed component + commission component (integer kopecks, no floating-point).
- **Output:** A computed `TrainerPayrollPreview` response (trainer_id, period_start, period_end, session_count, fixed_kopecks, commission_kopecks, total_kopecks). This is a read-only preview endpoint — no persistence yet.
- **RBAC:** Owner-only `GET /api/v1/trainers/{id}/payroll/preview?from=&to=`.

### PAY-03: Payroll accrual recording (append-only ledger row)
- **Category:** Table stake
- **Complexity:** MEDIUM
- **Dependency:** PAY-02 (computed amount); `payments` table append-only discipline (v1.4); `LOCKED_AUDIT_EVENTS`; `audit_log`
- **Description:** Owner confirms the payroll run → system records an **accrual row** as an append-only entry. This is the "commit" step after the preview. Two design options exist:
  - **Option A:** Reuse the existing `payments` table with a new `subject_kind='trainer_payroll'`. Requires extending the CHECK constraint on `subject_kind` and the sign CHECK (payroll accrual amounts are negative from the gym's perspective, i.e., money owed out). Extends the existing audit chain.
  - **Option B:** New `trainer_payroll_accruals` table with its own append-only discipline.

  **Recommendation: Option B (new table).** Reasons: (1) `payments.subject_kind` CHECK constraint is tightly coupled to membership/PT-package revenue semantics — extending it to cover payroll blurs the revenue ledger with the expenses ledger, making revenue reports harder to compute correctly. (2) The v1.4 `amount_sign_matches_subject_kind` CHECK would need a third branch with different sign logic. (3) Payroll accruals have different lifecycle attributes (paid_at, period_start, period_end, session_count_snapshot) that don't fit cleanly in `payments`. (4) The reports module reads `payments` for revenue — mixing payroll there would require all revenue queries to exclude `subject_kind='trainer_payroll'`. New `trainer_payroll_accruals` table keeps revenue ledger clean.

  **New table schema:**
  - `id` UUID PK
  - `trainer_id` UUID FK → `trainers.id` ON DELETE RESTRICT
  - `period_start` DATE NOT NULL (Europe/Moscow calendar date)
  - `period_end` DATE NOT NULL (inclusive)
  - `session_count` INTEGER NOT NULL (snapshot at accrual time)
  - `fixed_kopecks` INTEGER NOT NULL DEFAULT 0
  - `commission_kopecks` INTEGER NOT NULL DEFAULT 0
  - `total_kopecks` INTEGER NOT NULL (= fixed + commission, NOT a CHECK — service computes it)
  - `accrued_at` TIMESTAMPTZ NOT NULL DEFAULT now() (single temporal column, mirrors `payments.received_at` discipline)
  - `accrued_by_user_id` UUID FK → `users.id` ON DELETE RESTRICT
  - `paid_at` TIMESTAMPTZ NULL (NULL = not yet paid; filled in by PAY-04)
  - `paid_by_user_id` UUID FK → `users.id` ON DELETE RESTRICT NULL
  - `audit_log_id` UUID FK → `audit_log.id` ON DELETE SET NULL
  - UNIQUE `(trainer_id, period_start, period_end)` — one accrual per trainer per period (prevents duplicate runs). Partial UNIQUE with WHERE `paid_at IS NULL` is an alternative, but a hard UNIQUE is simpler and forces the owner to void + re-run if they made an error.

  Append-only: no UPDATE/DELETE on accrual rows after creation (except `paid_at`/`paid_by_user_id` via PAY-04 pattern). The AST commit-gate pattern should cover this module.
- **RBAC:** Owner-only `POST /api/v1/trainers/{id}/payroll/accrue`.
- **Audit events (pre-register before callsites):** `trainer_payroll_accrued`.

### PAY-04: Mark payroll accrual as paid
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** PAY-03 (accrual row exists)
- **Description:** Owner records that the accrual was paid out (cash, bank transfer — outside the CRM). This sets `paid_at = now()` and `paid_by_user_id` on the accrual row. This is the **only allowed mutation** on an accrual row after creation (all other fields are immutable). Separate audit event. Not a new ledger row — the accrual row has a `paid_at` column specifically for this lifecycle state.
  - Idempotency: if `paid_at` is already set, return 409 `already_paid`.
  - No "unpay" operation — if owner made an error, they need to note it in audit log manually. At single-gym scope, an "undo paid" operation creates more confusion than it solves.
- **RBAC:** Owner-only `POST /api/v1/trainers/{id}/payroll/accruals/{accrual_id}/mark-paid`.
- **Audit events:** `trainer_payroll_paid`.

### PAY-05: List payroll accruals for a trainer
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** PAY-03
- **Description:** `GET /api/v1/trainers/{id}/payroll/accruals` — paginated list of accrual rows for a trainer, ordered `accrued_at DESC`. Response includes `paid_at` so owner can see unpaid vs paid history. Standard `{items, total, page, pageSize}` envelope.
- **RBAC:** Owner-only.

---

### PAY Anti-features

| Anti-Feature | Why It's Anti-Feature at Single-Gym Scope | What to Do Instead |
|---|---|---|
| Reuse `payments` table for payroll accruals | Blurs revenue ledger with expense ledger; breaks revenue reports; needs CHECK constraint surgery | New `trainer_payroll_accruals` table |
| Tiered commission (% changes by revenue threshold) | Enterprise feature; no second gym to compare tiers | Single flat `commission_pct` per trainer |
| Automatic payroll period detection | No payroll calendar in CRM; owner decides period manually | Manual `from`/`to` params on preview + accrue endpoints |
| "Void" / reverse accrual row | Creates reconciliation complexity; no accounting module to balance against | Mark accruals as paid or not; corrections are new rows with notes (out of v1.9 scope) |
| Integration with 1C/external payroll software | No accounting integration in scope | Export via CSV (v1.10 scope) or manual |
| Per-session commission proration | Ambiguous when a package spans two periods; no single correct answer | Commission on full package sale attributed to period (PAY-02 approach) |
| Payroll for non-PT-session work (floor time, classes) | No class module; hourly floor tracking not in scope | PT-sessions only; floor time tracked manually |

---

## CATEGORY B — RECURRING SCHEDULE SLOTS

### REC-01: Recurring slot pattern (day-of-week + time)
- **Category:** Table stake
- **Complexity:** MEDIUM
- **Dependency:** `trainers` table; `trainer_availability_slots` (existing); time-off blocks (REC-03, needed before generation to avoid conflicts)
- **Description:** Owner/reception defines a recurring availability pattern for a trainer: `trainer_id`, `day_of_week` (0=Monday…6=Sunday, per ISO 8601), `start_time` TIME, `end_time` TIME, `valid_from` DATE, `valid_until` DATE (nullable = open-ended). These are patterns, not slot rows yet.

  **Generate-ahead vs expand-on-read decision:**
  - **Expand-on-read:** Pattern rows only; slots are computed dynamically at query time. Pro: no DB bloat, changes to pattern apply immediately. Con: complex queries, cannot represent exceptions (a specific date cancelled due to time-off), hard to book against a virtual slot.
  - **Generate-ahead:** Pattern triggers insertion of concrete `trainer_availability_slots` rows for N weeks ahead. Pro: existing booking machinery works unchanged, slots are bookable immediately, time-off blocks can cancel/prevent specific generated slots, audit trail of when slot was created. Con: cron job to materialize future slots, DB rows accumulate.

  **Recommendation: Generate-ahead with a bounded horizon (4–8 weeks ahead).** Reasons for this codebase: (1) `bookings` already reference `trainer_availability_slots.id` (FK); reusing the existing slot table means zero changes to booking logic. (2) The existing race-safe partial UNIQUE on `bookings` slot works on concrete slot IDs. (3) A simple ARQ cron that materializes slots up to 8 weeks ahead runs once daily (trivial). (4) Single-gym pet-project — 1 trainer × 5 days × 2 slots/day × 56 days = ~560 slot rows per trainer, perfectly manageable. (5) Exceptions (time-off) cancel specific generated slot rows — this already works with the existing slot cancellation machinery.

  **New table `trainer_recurring_patterns`:**
  - `id` UUID PK
  - `trainer_id` UUID FK → `trainers.id` ON DELETE RESTRICT
  - `day_of_week` SMALLINT NOT NULL CHECK (0..6)
  - `start_time` TIME NOT NULL
  - `end_time` TIME NOT NULL CHECK (end_time > start_time)
  - `valid_from` DATE NOT NULL
  - `valid_until` DATE NULL (open-ended)
  - `is_active` BOOLEAN NOT NULL DEFAULT TRUE (deactivate without deleting; stops future generation)
  - `created_by_user_id` UUID FK → `users.id` ON DELETE RESTRICT
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
  - UNIQUE `(trainer_id, day_of_week, start_time, valid_from)` — prevents duplicate patterns for same trainer+day+time starting same date.

- **RBAC:** Owner-only create/update; reception reads trainer patterns (GET).

### REC-02: Slot materialization cron (generate-ahead)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** REC-01 (patterns exist); `trainer_availability_slots` (existing); REC-03 (time-off blocks must be checked before materializing)
- **Description:** ARQ daily cron (`materialize_recurring_slots`, e.g. 07:00 MSK) scans all active `trainer_recurring_patterns` with `valid_from <= today + 56 days` and `(valid_until IS NULL OR valid_until >= today)`. For each pattern occurrence (each date that matches `day_of_week` within the window), checks if a slot row already exists for that trainer+datetime (prevents duplicates on re-run). If no slot exists AND no time-off block overlaps that window (REC-03), inserts a new `trainer_availability_slots` row with `status='active'`. Idempotent on re-run (SELECT before INSERT or INSERT...ON CONFLICT DO NOTHING). `unique=True` on ARQ cron (same pattern as other crons in this codebase).
- **Horizon:** Configurable via env var `RECURRING_SLOT_HORIZON_DAYS` (default 56, i.e., 8 weeks). Not hardcoded.
- **Audit events:** No per-slot audit event (high volume, low value). Log generation count via structlog INFO.

### REC-03: Trainer time-off / unavailability blocks
- **Category:** Table stake
- **Complexity:** LOW–MEDIUM
- **Dependency:** `trainers` table; `trainer_availability_slots` (existing); bookings (conflict check)
- **Description:** Owner creates a time-off block for a trainer: `trainer_id`, `block_start` TIMESTAMPTZ, `block_end` TIMESTAMPTZ, `reason` TEXT NULL. Effects:
  1. **Prevents generation:** The cron (REC-02) skips slot materialization for any pattern occurrence that overlaps the block window.
  2. **Cancels existing active slots:** When a time-off block is created, any existing `trainer_availability_slots` rows for that trainer that fall within the window AND have `status='active'` are transitioned to `status='cancelled'` with `cancel_reason='trainer_time_off'`. This uses the existing slot cancellation machinery.
  3. **Blocks that overlap booked slots:** If a slot within the block window has `status='booked'` (i.e., a booking exists), the system returns a conflict warning listing the affected bookings. **Owner must explicitly confirm** with `?force=true` to proceed — this cancels the booking(s) (booking FSM `confirmed → cancelled`) and sends cancellation DMs to clients via the existing booking notification machinery. Alternatively, owner resolves conflicts manually before creating the time-off block.

  **New table `trainer_time_off_blocks`:**
  - `id` UUID PK
  - `trainer_id` UUID FK → `trainers.id` ON DELETE RESTRICT
  - `block_start` TIMESTAMPTZ NOT NULL
  - `block_end` TIMESTAMPTZ NOT NULL CHECK (block_end > block_start)
  - `reason` TEXT NULL
  - `created_by_user_id` UUID FK → `users.id` ON DELETE RESTRICT
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
  - No soft-delete — time-off blocks can be deleted (hard-delete) if created in error, but only if no slots were already cancelled due to them (or owner accepts the cancelled slots stay cancelled). Simpler: allow hard-delete unconditionally; the already-cancelled slots stay cancelled (trainer re-creates manually if needed).

- **RBAC:** Owner-only create/delete; reception reads (for UI display).
- **Audit events:** `trainer_time_off_created`, `trainer_time_off_deleted`.

### REC-04: List recurring patterns + time-off blocks for a trainer
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** REC-01, REC-03
- **Description:** `GET /api/v1/trainers/{id}/recurring-patterns` and `GET /api/v1/trainers/{id}/time-off` — list endpoints for the frontend to render the trainer's schedule configuration. Standard `{items, total, page, pageSize}` envelope or simple list (these sets are small).
- **RBAC:** Owner + reception (read-only).

---

### REC Anti-features

| Anti-Feature | Why It's Anti-Feature at Single-Gym Scope | What to Do Instead |
|---|---|---|
| Expand-on-read recurring slots (virtual slots, no DB rows) | Breaks existing booking FK discipline; complex conflict detection with virtual entities | Generate-ahead concrete slot rows (REC-02) |
| Per-occurrence exception on a recurring series (RRULE EXDATE pattern) | Full iCalendar RRULE with EXDATE is over-engineering; no external calendar sync needed | Time-off block cancels specific generated slot rows |
| iCalendar / .ics sync / Google Calendar integration | No external calendar integration in scope for v1.9 | Manual pattern entry in admin UI |
| Client-facing recurring booking (auto-reserve same slot every week) | No client portal in scope; booking is reception/owner-initiated | Manual booking per session or admin-side recurrence |
| Pattern templates (copy pattern across trainers) | Only 1–5 trainers at single-gym scale; copy-paste is fine | Per-trainer pattern creation |
| Unlimited lookahead horizon | Performance risk if misconfigured | Env-var-capped horizon (default 8 weeks) |
| "Soft-delete" time-off blocks | Unnecessary complexity; just allow hard-delete with conflict guard | Hard-delete with conflict check |

---

## CATEGORY C — TRAINER-UTILIZATION REPORT

### RPT-01: Trainer load report (sessions + hours per trainer per period)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** `pt_sessions` (non-cancelled, `performed_at`, `trainer_id`); `trainer_name_snapshot`; v1.8 reports module discipline (raw-SQL `text()`, read-only, no `models.py`); Europe/Moscow TZ
- **Description:** `GET /api/v1/reports/trainers` — owner-only aggregate over `pt_sessions`. Parameters: `from` DATE, `to` DATE (inclusive, Europe/Moscow). Returns per-trainer row:
  - `trainer_id`, `trainer_name` (from `trainers.full_name` JOIN, not snapshot — for current name display)
  - `session_count` (non-cancelled sessions in period)
  - `cancelled_session_count`
  - `total_hours` (sum of `(end_time - start_time)` from linked `bookings`; NULL when no booking → use a configurable default session duration of 60 min, or 0 if no duration available)
  - `unique_client_count` (distinct `client_id` values in period)
  - `utilization_pct` — optional: `session_count / available_slot_count * 100` where `available_slot_count` = total `trainer_availability_slots` for trainer in period. This is the standard "trainer utilization" metric (industry target 65–70%). Note: available_slot_count can be 0 for trainers with no slots → omit or NULL.
  Ordered by `session_count DESC` (top trainers first).
- **RBAC:** Owner-only `(VIEW, REPORTS)` (existing permission); reception 403.
- **New indexes needed:** `trainer_id` on `pt_sessions` already has `ix_pt_sessions_trainer_id_performed_at_desc`. A `performed_at` partial index or the existing composite is sufficient.

### RPT-02: PT-package utilization / revenue attribution per trainer
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** `pt_sessions` (same as RPT-01); `payments` WHERE `subject_kind='pt_package'`; JOIN through `pt_packages` via `pt_sessions.pt_package_id`
- **Description:** Extends RPT-01 response (or a separate section of the same endpoint) with revenue attribution:
  - `revenue_kopecks` — sum of `payments.amount_kopecks` for PT-package sale rows whose package had at least one session by this trainer in the period (same attribution logic as PAY-02 commission computation).
  - `avg_revenue_per_session_kopecks` — `revenue_kopecks / session_count` (integer division).
  This lets the owner see "which trainer generates the most revenue" vs "which trainer conducts the most sessions" — these can diverge if trainers work with different package tiers.
- **RBAC:** Same as RPT-01.

### RPT-03: CSV export for trainer report
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** RPT-01, RPT-02; v1.8 UTF-8-BOM CSV discipline (RFC-4180 excel dialect)
- **Description:** `GET /api/v1/reports/trainers.csv` — same data as RPT-01+02 as StreamingResponse, UTF-8 BOM, RFC-4180 excel dialect. Mirrors v1.8 `/reports/revenue.csv` etc. pattern exactly.
- **RBAC:** Owner-only.

### RPT-04: Payroll accrual summary in trainer report (optional, deferred)
- **Category:** Differentiator
- **Complexity:** LOW
- **Dependency:** PAY-03 (accruals exist); RPT-01
- **Description:** Optionally include `total_accrued_kopecks` and `total_paid_kopecks` for the period from `trainer_payroll_accruals` in the trainer report response. This makes the "top trainers" view also show what was paid out, closing the revenue→cost view for the owner. Low additional complexity once accruals exist.
- **Note:** Can be added in the same phase as RPT-01 since both come from new tables.

---

### RPT Anti-features

| Anti-Feature | Why It's Anti-Feature at Single-Gym Scope | What to Do Instead |
|---|---|---|
| Real-time live dashboard (WebSocket/SSE) | No frontend integration in v1.9; report is owner-initiated | Simple GET endpoint, same as v1.8 |
| Per-client breakdown in trainer report | Client-level view belongs to clients module; trainer report is trainer-level aggregate | Separate client-detail endpoint if ever needed |
| Predictive analytics / forecasting | ML/statistics complexity; no training data volume at single-gym scale | Simple historical aggregates |
| Write operations inside reports module | D-54-07 discipline: reports are strictly read-only | Raw-SQL reads only |
| No-show rate in trainer report | No-shows are bookings-level data; trainer report focuses on conducted sessions | Booking-level reports (separate future feature if needed) |
| Class instructor utilization | No class/group module in Sportzal | PT-session-only scope |

---

## Feature Dependencies

```
PAY-01 (compensation config on trainer)
    └──required by──> PAY-02 (payroll preview computation)
                          └──required by──> PAY-03 (accrue to ledger)
                                                └──required by──> PAY-04 (mark paid)
                                                └──required by──> PAY-05 (list accruals)
                                                └──enhances──> RPT-04 (payroll in trainer report)

REC-01 (recurring pattern)
    └──required by──> REC-02 (materialization cron)
                          └──depends on──> REC-03 (time-off blocks, checked before materializing)
REC-03 (time-off blocks)
    └──uses──> existing slot cancellation machinery (trainer_availability_slots FSM)
    └──uses──> existing booking cancellation + notification machinery (bookings FSM + DMs)

RPT-01 (trainer load report)
    └──reads──> pt_sessions (existing, no new FK)
    └──reads──> trainer_availability_slots (existing, for utilization_pct)
    └──enhances with──> RPT-02 (revenue attribution)
RPT-02 (PT revenue attribution)
    └──reads──> payments WHERE subject_kind='pt_package' (existing)
RPT-03 (CSV)
    └──wraps──> RPT-01 + RPT-02

PAY-02 and RPT-02 share the same "PT-package revenue attribution" logic (JOIN pattern);
    → define a shared raw-SQL fragment or extract to a shared reports helper.
```

### Dependency Notes

- **REC-03 before REC-02:** The cron must know about time-off blocks before materializing slots; both should land in the same phase.
- **PAY-01 before PAY-02/03:** The compensation config must exist on the trainer record before any payroll computation is possible.
- **RPT can proceed independently of PAY and REC:** The report reads only from existing tables (`pt_sessions`, `bookings`, `payments`, `trainers`) plus the new payroll accruals if RPT-04 is included. RPT can be its own phase.
- **No dependency between REC and PAY:** Recurring slots don't affect payroll computation (payroll works from `pt_sessions.performed_at`, not from slots directly).

---

## MVP Definition

### This Milestone (v1.9 — must deliver)

- [x] **PAY-01** — compensation model columns on `trainers` (schema + PATCH endpoint extension)
- [x] **PAY-02** — payroll preview computation endpoint (read-only, no persistence)
- [x] **PAY-03** — payroll accrual recording (`trainer_payroll_accruals` table, append-only)
- [x] **PAY-04** — mark accrual as paid (single mutation allowed on accrual row)
- [x] **PAY-05** — list accruals per trainer
- [x] **REC-01** — recurring pattern table + CRUD
- [x] **REC-02** — slot materialization cron (ARQ daily)
- [x] **REC-03** — time-off blocks (table + create/delete + conflict guard + slot cancellation)
- [x] **REC-04** — list patterns + time-off blocks
- [x] **RPT-01** — trainer load report endpoint
- [x] **RPT-02** — PT-package revenue attribution in trainer report
- [x] **RPT-03** — trainer report CSV export

### Add After Validation (v1.10+)

- [ ] **RPT-04** — payroll accrual summary in trainer report — easy add once PAY-03 ships
- [ ] Trainer report frontend integration — v2.0 (frozen `admin-web` not touched in v1.9)
- [ ] Partial refund for PT-packages (B-02 deferred from v1.4) — affects payroll commission attribution

### Future Consideration (v2.0+)

- [ ] Trainer self-service portal (view own schedule, payroll statements)
- [ ] Per-session commission proration across period boundaries
- [ ] 1C / external payroll export
- [ ] iCal sync for trainer schedules
- [ ] Recurring client-trainer booking automation

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| PAY-01 (compensation config) | HIGH | LOW | P1 |
| PAY-02 (payroll preview) | HIGH | MEDIUM | P1 |
| PAY-03 (accrue to ledger) | HIGH | MEDIUM | P1 |
| PAY-04 (mark paid) | HIGH | LOW | P1 |
| PAY-05 (list accruals) | MEDIUM | LOW | P1 |
| REC-01 (recurring pattern) | HIGH | MEDIUM | P1 |
| REC-02 (slot materialization cron) | HIGH | LOW | P1 |
| REC-03 (time-off blocks) | HIGH | MEDIUM | P1 |
| REC-04 (list patterns + time-off) | MEDIUM | LOW | P1 |
| RPT-01 (trainer load report) | HIGH | LOW | P1 |
| RPT-02 (revenue attribution) | HIGH | LOW | P1 |
| RPT-03 (CSV export) | MEDIUM | LOW | P1 |
| RPT-04 (payroll in report) | MEDIUM | LOW | P2 |

---

## Behavior Notes and Edge Cases by Category

### PAYROLL edge cases

1. **Trainer with no compensation config (both NULL):** `GET /preview` returns `total_kopecks=0` with a note. `POST /accrue` should still be allowed (owner may want to record a manual amount — or block it and require config first). Recommendation: block with 422 `trainer_has_no_compensation_config`.

2. **PT-package sale payment attribution across period boundaries:** A 10-session package sold in April with sessions running May–June. For May payroll, should the commission be on the full package price or prorated? Recommendation (already stated in PAY-02): commission is on the full package sale payment if ANY session from that package falls in the period. This means a trainer could get commission on a package sold before the period. Document this as a known limitation.

3. **Cancelled sessions:** `pt_sessions` rows with `cancelled_at IS NOT NULL` are excluded from both session count and commission computation. This is table stakes — you don't pay for sessions that didn't happen.

4. **Duplicate accrual attempt (same period):** UNIQUE `(trainer_id, period_start, period_end)` on `trainer_payroll_accruals` returns 409 `accrual_already_exists_for_period`. Owner must explicitly note corrections out-of-band.

5. **Trainer deactivated mid-period:** `is_active=false` trainers still have historical `pt_sessions`; payroll still computes correctly over past sessions. No special handling needed.

6. **Rounding:** All amounts in integer kopecks. Commission = `ROUND(sum_pt_revenue_kopecks * commission_pct / 100)` using Python `round()` (banker's rounding) or `math.ceil()` — pick one and document. Recommendation: `round()` (consistent with Python default; industry standard for financial calculations is half-even). Do not use float arithmetic — multiply then integer-divide.

### RECURRING SCHEDULE edge cases

1. **Pattern created with past `valid_from`:** Cron only materializes slots from `today` forward. Slots for dates before today are not retroactively created. If owner wants historical slots, they create them manually (existing flow).

2. **Two patterns overlap for same trainer (same day+time):** UNIQUE `(trainer_id, day_of_week, start_time, valid_from)` on `trainer_recurring_patterns` prevents exact duplicates, but two patterns for the same trainer on the same day with different `valid_from` dates can coexist. The cron must deduplicate before inserting (SELECT existing slot for exact trainer+datetime before INSERT). The slot table already has no UNIQUE on trainer+time, so overlapping patterns would create duplicate slots. Mitigation: cron checks `EXISTS (SELECT 1 FROM trainer_availability_slots WHERE trainer_id=? AND start_time=? AND status != 'cancelled')` before inserting.

3. **Pattern deactivated (`is_active=false`):** Cron skips it. Already-generated future slots remain `active` unless explicitly cancelled. Owner must cancel them manually or via a time-off block if desired. This is correct behavior — deactivating a pattern stops future generation but doesn't retroactively cancel the slots it already created.

4. **Time-off block applied to already-booked slot:** REC-03 conflict guard checks for `booked` slots in the window. Owner must confirm with `?force=true`. When confirmed: booking is cancelled (existing booking FSM), client DM sent (existing notification machinery). This reuses existing infrastructure with no new code paths for notifications.

5. **Materialization cron race (two containers):** ARQ `unique=True` on the cron job prevents parallel runs. The INSERT...ON CONFLICT DO NOTHING pattern handles the edge case of two slots being materialized for the same trainer+datetime.

6. **`valid_until` in the past:** Cron skips patterns where `valid_until < today`. Owner-visible note: patterns automatically stop generating.

### REPORT edge cases

1. **Trainer with no sessions in period:** Returns a row with all counts at 0. Alternatively, filter out zero-session trainers. Recommendation: include only trainers with `session_count > 0` (configurable via `?include_inactive=true` param). Consistent with "top trainers" framing.

2. **`utilization_pct` computation when slot count is 0:** Return NULL for `utilization_pct` when no slots exist for the trainer in the period (avoid division by zero).

3. **Revenue attribution when a PT-package has multiple trainers:** A client buys a 10-session package and trains with two different trainers (5 sessions each). Both trainers appear in the trainer-level report. Revenue is attributed to both — this means revenue is double-counted at the "total" level. This is a known limitation of attribution by trainer participation, not by package. Document clearly; at single-gym scale where one package typically has one trainer, this is acceptable.

4. **`performed_at` timezone consistency:** Must use Europe/Moscow AT TIME ZONE conversion, same as `visits.gym_date` discipline. `pt_sessions.performed_at` is TIMESTAMPTZ; filter as `performed_at >= period_start AT TIME ZONE 'Europe/Moscow'` and `< (period_end + 1 day) AT TIME ZONE 'Europe/Moscow'`.

---

## New LOCKED_AUDIT_EVENTS to Pre-Register (INFRA-15 discipline)

All of the following must be added to `LOCKED_AUDIT_EVENTS` frozenset **before** any callsite lands (per v1.3 precedent):

- `trainer_payroll_accrued`
- `trainer_payroll_paid`
- `trainer_time_off_created`
- `trainer_time_off_deleted`

Optional (if recurring pattern mutations are audited):
- `trainer_recurring_pattern_created`
- `trainer_recurring_pattern_deactivated`

---

## New RBAC Entries Required (three-way parity: backend → admin-web `can.ts` → `registry.ts`)

Existing `Resource.TRAINERS` covers catalog CRUD. New operations stay owner-only:

| Action | Resource | Notes |
|--------|---------|-------|
| VIEW | TRAINER_PAYROLL | New resource — payroll preview + accrual list |
| CREATE | TRAINER_PAYROLL | Accrue + mark paid |
| VIEW | REPORTS | Already exists (v1.8); trainer report reuses this |

Simplest path: add `Resource.TRAINER_PAYROLL` owner-only (both VIEW and CREATE). The trainer report (`RPT-01`) reuses existing `(VIEW, REPORTS)` permission — no new resource needed.

---

## Suggested Phase Grouping

Based on dependencies and complexity, v1.9 naturally splits into 3–4 phases:

1. **Phase 58 — Payroll foundations:** PAY-01 (compensation config columns + PATCH), PAY-02 (preview endpoint), PAY-03 (accruals table + endpoint), PAY-04 (mark paid), PAY-05 (list). LOCKED_AUDIT_EVENTS pre-registration for payroll events.

2. **Phase 59 — Recurring schedule:** REC-01 (patterns table + CRUD), REC-02 (materialization cron), REC-03 (time-off blocks table + endpoint + conflict guard + slot cancellation), REC-04 (list endpoints). LOCKED_AUDIT_EVENTS pre-registration for time-off events.

3. **Phase 60 — Trainer report:** RPT-01 + RPT-02 + RPT-03 (trainer load + revenue + CSV). Optional: RPT-04 (payroll in report).

4. **Phase 61 — OpenAPI handoff:** Byte-stable regen `openapi.json` + `schema.d.ts` + `AssertNonNever` forward-guards (per-milestone discipline). RBAC three-way parity test green.

Phases 58 and 59 can be ordered either way (no inter-dependency). The report (Phase 60) benefits from coming after payroll (accruals available for RPT-04) but can proceed immediately since RPT-01/02/03 have no payroll dependency.

---

## Sources

- [ISSA: Gym Commission Structure for Personal Trainers](https://www.issaonline.com/blog/post/breaking-down-big-gym-pay) — MEDIUM confidence (industry survey)
- [NESTA: How Do Personal Trainers Get Paid at a Gym?](https://www.nestacertified.com/how-do-personal-trainers-get-paid-at-a-gym/) — MEDIUM confidence
- [Wellyx: Gym Commission Structure](https://wellyx.com/blog/gym-commission-structure/) — MEDIUM confidence
- [Gymdesk: Gym Payroll Management](https://gymdesk.com/blog/gym-payroll-management) — MEDIUM confidence
- [SchedulingKit: Fitness Scheduling Best Practices](https://schedulingkit.com/hub/industry-guides/fitness-scheduling-best-practices) — MEDIUM confidence
- [Trainerize: Personal Training KPIs](https://www.trainerize.com/blog/key-performance-indicators-for-personal-trainers/) — MEDIUM confidence
- [SmartHealthClubs: Gym Analytics](https://smarthealthclubs.com/blog/gym-analytics-how-to-use-gym-software-data-for-growth-in-2026/) — MEDIUM confidence
- Existing codebase: `trainers/models.py`, `schedule/models.py`, `pt_sessions/models.py`, `payments/models.py`, `payments/constants.py` — HIGH confidence (direct code inspection)
- `.planning/PROJECT.md` v1.9 milestone scope — HIGH confidence (authoritative)

---
*Feature research for: v1.9 Trainers Complete (trainer payroll, recurring schedule, time-off blocks, trainer-utilization report)*
*Researched: 2026-05-24*
