# Pitfalls Research

**Domain:** Trainer payroll-ledger + recurring schedule + time-off + utilization report — added to existing single-gym CRM (Sportzal v1.9)
**Researched:** 2026-05-24
**Confidence:** HIGH (all pitfalls derived directly from the existing system's own Key Decisions in PROJECT.md and the established v1.2–v1.8 discipline)

---

## Critical Pitfalls

### Pitfall 1: Recompute Drift — Payroll Run Computed from Live Data That Subsequently Changes

**What goes wrong:**
A payroll run for 2026-05-01..2026-05-31 aggregates `pt_sessions` and `payments` rows at run-time, then marks the trainer as "paid." After the run is marked paid, a client issues a refund against a PT-package sold in May. The original commission that was already paid out is now overstated relative to net revenue. Alternatively, a session is retroactively backdated (reception has a ≤7d backdating window, owner has unlimited per B-11 in v1.4), silently shifting that session across the period boundary after the run has closed.

**Why it happens:**
Treating payroll as a recomputable view over live tables rather than a point-in-time snapshot. Developers assume sessions are immutable — but `payments` (refunds) are not, and backdating shifts sessions out from under a closed period.

**How to avoid:**
Mirror the v1.4 append-only ledger discipline exactly. A payroll run creates an **immutable accrual row** (`trainer_payroll_entries`) at the moment it executes — not a view. The row records: `period_start`, `period_end`, `run_at` (UTC timestamp), `gross_revenue_kopecks`, `session_count`, `rate_snapshot_numerator`, `rate_snapshot_denominator`, `config_id_snapshot`, `amount_kopecks`, `status='unpaid'|'paid'`. Once the row exists, subsequent refunds and backdated sessions do NOT mutate it. Adjustments appear as new signed-amount rows in the next period — same discipline as the `payments` ledger signed-amount semantics and the `refund_of` partial UNIQUE chain.

**Warning signs:**
- `SELECT SUM(payments.amount)` is called at payroll run-time but no row is inserted into a payroll entries table
- No `trainer_payroll_entries` table exists; the "payroll" endpoint only returns a computed total
- A refund endpoint that does not check whether the original payment appears in an accrual row with `status='paid'`

**Phase to address:**
Payroll scaffold phase (first payroll phase). The `trainer_payroll_entries` schema must encode immutability at the DB level: no `UPDATE`/`DELETE` allowed by business code, `run_at NOT NULL`, `rate_snapshot_numerator NOT NULL`.

---

### Pitfall 2: Double-Paying a Period — Missing Idempotency Guard on the Run Operation

**What goes wrong:**
A payroll run for 2026-05-01..2026-05-31 is triggered twice — cron restart, or the owner double-clicks "Run payroll." Both executions pass the "does a run already exist?" check before either commits, resulting in two run header rows and twice the accrual entries for the same trainer + period.

A second form: inconsistent period boundary semantics between SQL queries. One query uses `>=start AND <end` (half-open), another uses `>=start AND <=end` (inclusive). A session on the boundary day appears in both the May run and the June run.

**Why it happens:**
Application-level `SELECT ... WHERE trainer_id = :id AND period_start = :start` followed by `INSERT` is not atomic — classic TOCTOU race. Half-open vs. inclusive date boundary inconsistency is a recurring error pattern when the developer copies from Python `range()` habits.

**How to avoid:**
Use `INSERT INTO trainer_payroll_runs ... ON CONFLICT (trainer_id, period_start, period_end) DO NOTHING RETURNING id`. If `RETURNING` yields no row, a run already exists — service returns 409 `payroll_period_already_run`. This is the same DB-wins-the-race pattern as `UNIQUE (client_id, gym_date)` on visits (Phase 19) and `UNIQUE (membership_id) WHERE ended_at IS NULL` on freeze periods (Phase 25). Period boundaries must be canonically **inclusive start, inclusive end** matching the existing `memberships.end_date` and `visits.gym_date` discipline: `session_date >= :period_start AND session_date <= :period_end` in all SQL.

**Warning signs:**
- No UNIQUE constraint on `(trainer_id, period_start, period_end)` in `trainer_payroll_runs`
- Two `payroll_runs` rows with identical `(trainer_id, period_start, period_end)` are possible in the schema
- `pt_sessions.session_date` compared with `<` in one query and `<=` in another across the codebase

**Phase to address:**
Payroll scaffold phase (schema). UNIQUE key must be in the Alembic migration, not only in the application layer.

---

### Pitfall 3: Percentage Rounding — Sum-of-Parts Does Not Equal the Whole; Float Arithmetic Errors

**What goes wrong:**
Trainer earns 33% of a PT-package sale of 3333 RUB (333 300 kopecks). `333300 * 0.33 = 110 000.000...` — exact here, but `int(333300 * 0.33)` may produce `109 999` due to IEEE 754 float representation. At scale, accumulated error across many sessions drifts by rubles per period. If two trainers split revenue attribution (e.g. one sold, one conducted), individually rounding each share can produce a sum that does not match the original amount.

**Why it happens:**
Using Python float arithmetic (`kopecks * float_rate`) before truncating to integer. Storing `commission_rate` as `FLOAT` or `NUMERIC(5,2)` on the trainer row instead of integer numerator/denominator.

**How to avoid:**
Always compute in integer arithmetic. Store rate as `rate_numerator: int` and `rate_denominator: int` (e.g. 33% = 33, 100) — never as a float column. Compute: `math.ceil(amount_kopecks * rate_numerator // rate_denominator)`. Using `ceil` rounds in the trainer's favour, matching the freeze-day ceil discipline from Phase 25 (`_compute_days_used` uses ceil so the client never loses partial days — analogously, the trainer never loses a partial kopeck on rounding). Never use `FLOAT` or `REAL` for money in Postgres. Use `Decimal` only as a transient computation tool. For multi-trainer attribution splits, use the "largest remainder" method: sum the rounded parts, add the residual to the last entry to make the total exact.

**Warning signs:**
- `commission_rate FLOAT` or `NUMERIC(5,2)` column in the trainer config schema
- `amount = int(kopecks * rate)` using Python float multiplication
- Two attribution rows whose `amount_kopecks` values do not sum to the original `payment.amount_kopecks`

**Phase to address:**
Payroll scaffold phase (schema + `_compute_commission` helper). Write a dedicated unit test: `assert _compute_commission(333300, 33, 100) == 110009` (ceil) and a split test: `assert sum(split_commission(500000, [30, 20])) == 150000`.

---

### Pitfall 4: Refund After Payroll — No Clawback; Paid Commission Is Silently Stale

**What goes wrong:**
A PT-package sold in May is refunded in June. The May payroll was already run and marked paid. The June refund correctly appends a negative payment row to the `payments` ledger (v1.4 signed-amount semantics), but nothing deducts the corresponding commission from the trainer's already-paid May accrual. The trainer has been overpaid relative to net revenue, with no audit trail of the discrepancy.

**Why it happens:**
The existing refund flow (`refund_issued` → `payment_refunded` audit chain, Phase 34/v1.4) touches `payments`, `memberships`/`pt_packages`, and audit log only. It has no payroll hook. Developers wire up the refund path before the payroll path exists and never revisit it.

**How to avoid:**
The refund endpoint (both cash `POST /memberships/{id}/refund` and online `refund.succeeded` webhook handler) must check whether `original_payment_id` appears in `trainer_payroll_entries.source_payment_id` with `status='paid'`. If yes, emit a **negative accrual adjustment row** in the same atomic UoW as the refund ledger row: `amount_kopecks = -_compute_commission(refund_amount, rate_snapshot_numerator, rate_snapshot_denominator)`, `adjustment_reason='refund_clawback'`, FK to the original accrual row and the refund payment row. This preserves append-only discipline — the May accrual row is never modified; the clawback is a new entry visible in the trainer's ledger. The pattern is identical to how the `payments` ledger handles refunds: new signed-amount row, never an UPDATE.

**Warning signs:**
- The refund service has no lookup against `trainer_payroll_entries`
- No `adjustment_reason` concept in the `trainer_payroll_entries` schema
- The trainer commission view for May shows a positive total with no clawback line after a June refund of a May package

**Phase to address:**
Payroll phase that implements the accrual model. The clawback hook must be designed into the refund integration path before the payroll "paid" status is introduced — not retrofitted.

---

### Pitfall 5: Rate Config Changes Mid-Period — No Snapshot, Retroactive Recomputation

**What goes wrong:**
Trainer config shows 30% commission. Owner changes it to 25% on May 15. A payroll run for the full month of May now computes all sessions at 25%, silently underpaying the trainer for May 1–14. Alternatively, the rate is stored as a mutable column on the `trainers` row, and any payroll run always reads the current value.

**Why it happens:**
Treating the compensation rate as a live lookup rather than a point-in-time snapshot — the exact mistake that motivated mandatory snapshot pricing on memberships in v1.2 (Phase 17: `price_kopecks_snapshot NOT NULL`, `plan_name_snapshot NOT NULL`). The lesson was already paid for in the memberships domain and must not be re-learned in the payroll domain.

**How to avoid:**
Mirror the membership snapshot discipline exactly. Create a `trainer_compensation_configs` table with `valid_from date`, `rate_numerator int`, `rate_denominator int`, `fixed_per_session_kopecks int` (nullable). This table is INSERT-only — a rate change creates a new row with a new `valid_from`; the old row is never updated. When a payroll run executes, it snapshots the config in effect as of `period_end` and stores `rate_snapshot_numerator`, `rate_snapshot_denominator`, and `config_id_snapshot` in the accrual row. The accrual row permanently carries the rate that was in effect — subsequent config changes cannot alter it.

**Warning signs:**
- `trainers.commission_rate` or similar mutable column on the trainer row used at payroll run-time
- No `valid_from` or versioned config table for compensation
- Payroll run SQL: `SELECT commission_rate FROM trainers WHERE id = :id` without a temporal join

**Phase to address:**
Payroll scaffold phase (schema design). The `trainer_compensation_configs` INSERT-only discipline must be established and documented as a Key Decision before any payroll run logic is written.

---

### Pitfall 6: Revenue Attribution Ambiguity — Who Sold vs. Who Conducted

**What goes wrong:**
A PT-package is sold by Trainer A (assigned at package creation via `pt_packages.trainer_id`) but two sessions are conducted by Trainer B (recorded in `pt_sessions.trainer_id` via the session recording endpoint). If payroll is computed as "% of PT-package revenue for packages this trainer conducted," Trainer B gets commission on a sale they were not responsible for. If computed as "% of revenue for packages this trainer was assigned to," Trainer A gets commission on sessions they did not conduct.

**Why it happens:**
The existing v1.4 data model ties a PT-package to one trainer at sale time (`pt_packages.trainer_id`) and records each session against the conducting trainer (`pt_sessions.trainer_id`). The distinction between selling and conducting was not needed before payroll and was never encoded as a Key Decision. Payroll logic written without this decision produces an ambiguous result.

**How to avoid:**
Decide and document the attribution model as a Key Decision before writing any payroll SQL. The recommended model for Sportzal's single-gym context: **% of PT-package revenue** → attribute to `pt_packages.trainer_id` (the trainer assigned at sale, who is effectively the responsible trainer in a single-gym model); **fixed per session** → attribute to `pt_sessions.trainer_id` (the conductor). Both models use unambiguous existing columns. Document this as `D-5x-PAYROLL-ATTRIBUTION` in Key Decisions. All payroll queries must carry a `-- attribution: assigned-at-sale trainer` or `-- attribution: conducting trainer` comment to prevent silent drift.

**Warning signs:**
- A payroll SQL query JOINs `pt_sessions` with `payments` via trainer without a comment explaining which trainer attribution is intended
- A single payroll query mixes `pt_packages.trainer_id` and `pt_sessions.trainer_id` without explicit intent
- No "attribution model" documented in project Key Decisions or phase plans

**Phase to address:**
Payroll design phase (the first payroll phase plan). Attribution model must be a locked decision before the payroll SQL is written — not clarified after tests fail.

---

### Pitfall 7: DST Expansion Bugs for Recurring Slots in Europe/Moscow

**What goes wrong:**
Europe/Moscow has not observed DST since 2014 (permanently UTC+3). However, generating recurring slots by adding `timedelta(weeks=n)` to a naive UTC timestamp instead of expanding `(day_of_week, local_time)` through the Europe/Moscow timezone is architecturally wrong even if it produces correct results today. If the code ever runs in a different TZ context, or Russia re-adopts DST, all stored slot UTC timestamps will be wrong. Additionally, `datetime(year, month, day, hour, minute)` without `tzinfo` creates a naive datetime — comparisons against `TIMESTAMPTZ` Postgres columns will fail or produce silent TZ-offset errors.

**Why it happens:**
Developers assume "MSK is always UTC+3, so I can just add 3 hours to UTC" and write naive datetime arithmetic instead of using `zoneinfo`. This is architecturally inconsistent with the `gym_date STORED AS (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` discipline that every other date computation in this system follows.

**How to avoid:**
Use `zoneinfo.ZoneInfo('Europe/Moscow')` for all recurring slot expansion — the same pattern as `gym_date STORED` and the cron `hour=3, minute=5` (UTC) = 06:05 MSK equivalence. Expand `(day_of_week, start_time_local)` to concrete `TIMESTAMPTZ` values using: `datetime(year, month, day, hour, minute, tzinfo=ZoneInfo('Europe/Moscow')).astimezone(timezone.utc)`. Store as `TIMESTAMPTZ` in Postgres (never `TIMESTAMP WITHOUT TIME ZONE`). Never add raw `timedelta` to a naive datetime. Write a golden test: `expand_recurring_slot(day_of_week=MONDAY, local_time=time(10, 0), from_date=date(2026, 3, 30))` must produce `2026-03-30 07:00:00+00:00`.

**Warning signs:**
- `slot_start = datetime(year, month, day, hour, minute)` anywhere in slot expansion code (no `tzinfo`)
- `next_occurrence = base_dt + timedelta(weeks=n)` without re-normalising through `ZoneInfo('Europe/Moscow')`
- Slot column declared as `TIMESTAMP` not `TIMESTAMPTZ` in the Alembic migration

**Phase to address:**
Recurring slots phase. The golden test must be part of the phase acceptance criteria, mirroring the VER-02 DST/MSK-offset golden test from Phase 57.

---

### Pitfall 8: Infinite or Excessive Slot Generation — No Horizon Limit

**What goes wrong:**
A recurring rule "every Monday 10:00 until further notice" triggers slot expansion on each cron tick. Without a generation horizon, a single cron run generates years of future Monday slots — O(years * trainers * rules) rows. With no idempotency guard, each cron tick re-inserts duplicate rows, driving contention on `trainer_availability_slots`.

Even with a UNIQUE constraint preventing duplicates, the expansion query scans the entire `trainer_recurring_rules` table and attempts an INSERT for every possible future date up to the horizon — O(horizon_in_weeks) per rule per tick.

**Why it happens:**
Forgetting that "generate ongoing" means "generate only a bounded window ahead" — the same issue as unbounded pagination without `LIMIT`. Also, omitting `unique=True` on the ARQ cron job, allowing parallel expansion runs.

**How to avoid:**
Adopt the ARQ cron `unique=True` + idempotent INSERT discipline. Expansion query generates slots only within `NOW() < slot_start_utc <= NOW() + INTERVAL '4 weeks'` (configurable horizon). SQL: `INSERT INTO trainer_availability_slots ... ON CONFLICT (trainer_id, slot_start_utc) DO NOTHING` — explicit no-op on conflict, mirroring the `membership_notifications` `INSERT ... ON CONFLICT DO NOTHING` cron pattern. ARQ cron: `unique=True, keep_result=60`. On cron restart, the second tick silently skips already-generated slots.

**Warning signs:**
- Expansion loop has no `limit_date` or horizon parameter
- No `UNIQUE (trainer_id, slot_start_utc)` index on `trainer_availability_slots`
- Slot expansion called synchronously inside an HTTP request instead of via an ARQ task
- ARQ expansion cron missing `unique=True`

**Phase to address:**
Recurring slots phase. UNIQUE constraint and cron horizon limit must be in the schema migration and ARQ config from day one — not optimizations to add after the first performance complaint.

---

### Pitfall 9: Time-Off Overlapping an Already-Confirmed Booking — Silent Orphan or Cascade

**What goes wrong:**
Trainer Ivan has a confirmed booking for Monday 10:00 (`bookings.status = 'confirmed'`). The owner creates a time-off block covering that Monday. Two failure modes:

1. The time-off insertion succeeds silently, leaving the confirmed booking in place. The client arrives Monday morning; the trainer is absent.
2. The system auto-cancels the booking without notifying the client (or worse, auto-cancels without an audit event).

The inverse: the recurring slot expansion cron generates a new slot for a date that falls inside an existing time-off block, making that slot bookable when it should be blocked.

**Why it happens:**
Time-off blocks and bookings live in different tables. The slot generation cron and the time-off insert path do not cross-check against the bookings FSM. Developers treat time-off as a schedule concern and bookings as a separate concern — missing the invariant that they must be consistent.

**How to avoid:**
Time-off creation endpoint: before inserting the time-off block, `SELECT` confirmed bookings that overlap: `SELECT b.id FROM bookings b JOIN trainer_availability_slots s ON b.slot_id = s.id WHERE s.trainer_id = :trainer_id AND s.slot_start_utc BETWEEN :off_start AND :off_end AND b.status = 'confirmed'`. If any exist, return **409** with the conflicting booking IDs in the response body — requiring the owner to explicitly cancel those bookings first. The API must not auto-cancel silently; the v1.5 booking FSM (`confirmed → cancelled_by_owner`) is the correct cancellation path, which emits the `booking_cancelled` audit event and triggers client notifications. Recurring slot expansion: the expansion query must add `AND NOT EXISTS (SELECT 1 FROM trainer_time_off_blocks WHERE trainer_id = :trainer_id AND :slot_start_utc BETWEEN off_start AND off_end)` to skip blocked windows.

**Warning signs:**
- `POST /trainer-time-off` has no query against `bookings` before committing the insert
- Recurring expansion cron joins only `trainer_recurring_rules`, not `trainer_time_off_blocks`
- `bookings.status = 'confirmed'` rows whose `slot_start_utc` falls inside a time-off block after insertion

**Phase to address:**
Time-off phase. The conflict check must be part of the time-off creation service, not a post-launch addition.

---

### Pitfall 10: Report Read-Only Discipline Leak — Importing ORM Models from Other Modules

**What goes wrong:**
The trainer utilization report needs data from `pt_sessions`, `bookings`, `trainer_availability_slots`, `payments`, and `trainers` tables. The natural instinct is to import `app.modules.pt_sessions.models.PTSession` and `app.modules.trainers.models.Trainer` into `app.modules.reports.service`. This violates the `modules-independent` import-linter contract and couples the reports module to the internal ORM of four other modules — the exact mistake D-54-07/D-54-08 was designed to prevent.

**Why it happens:**
ORM queries feel more natural than raw SQL for developers who know SQLAlchemy. The D-54-07/D-54-08 discipline was established for the v1.8 reports module but must be actively re-applied to the v1.9 trainer report — it is not automatic.

**How to avoid:**
Apply D-54-07 / D-54-08 exactly as established in v1.8. `app/modules/reports/` has **no `models.py`** and uses only `sqlalchemy.text()` for all queries. The `.importlinter` config must be verified to reject any cross-module import from `reports`. Write the trainer-usage report as a raw SQL CTE over table names (`pt_sessions`, `bookings`, `trainer_availability_slots`, `payments`, `trainers`), not ORM class names. The zero-new-import-linter-ignores rule (established in Phase 54) must hold for the trainer report.

**Warning signs:**
- `from app.modules.trainers.models import Trainer` in any file under `app/modules/reports/`
- `import-linter` CI gate fails after the trainer report module is extended
- `models.py` created inside `app/modules/reports/`

**Phase to address:**
Trainer report phase. The import-linter contract must be verified clean before any report code is merged. Zero new `[importlinter:contracts]` ignores is a hard constraint.

---

### Pitfall 11: Aggregation Over Soft-Deleted Trainers — Silently Dropping Historical Sessions

**What goes wrong:**
A trainer is deactivated (`trainers.is_active = False` — the existing soft-delete via `is_active` from v1.4). Their historical `pt_sessions` rows remain in the database. The trainer utilization report adds `WHERE trainers.is_active = TRUE` — the correct filter for "who can I book right now" endpoints — but this is wrong for a historical report. All sessions conducted by deactivated trainers are silently excluded. The report understates total PT utilization and omits deactivated trainers from the top-trainer ranking entirely.

**Why it happens:**
Copying the `is_active = TRUE` filter from live-view endpoints (booking creation, trainer picker) into a historical aggregation query. The v1.8 clients report correctly excludes soft-deleted clients from the "new clients" counter — but historical session counting is a different semantics. The two cases must not be conflated.

**How to avoid:**
Historical reports must aggregate over **all** `pt_sessions` rows regardless of current trainer `is_active` status — the session happened and the revenue was collected. Join against `trainers` with `LEFT JOIN` (not `INNER JOIN`) to include the trainer name, and use `pt_sessions.trainer_name_snapshot` (which exists as `NOT NULL` per v1.4 B-05) for display — this is already robust to soft-deletion and does not require any join at all for the name column. If grouping by `trainer_id`, include an `is_active` indicator column for context but never filter on it.

**Warning signs:**
- Report SQL includes `JOIN trainers ON ... WHERE trainers.is_active = TRUE`
- Total session count in the report is less than `SELECT COUNT(*) FROM pt_sessions WHERE session_date BETWEEN :start AND :end`
- `trainer_name_snapshot` column not used in report aggregation; instead, a JOIN to `trainers.full_name` is the sole name source

**Phase to address:**
Trainer report phase. Golden test: insert a session for a trainer, deactivate the trainer via `is_active = False`, run the report — the session must appear in the results.

---

### Pitfall 12: Period-Boundary Off-by-One in the Utilization Report

**What goes wrong:**
Owner requests "May 2026 utilization." Backend computes `from_date=2026-05-01`, `to_date=2026-05-31`. The SQL uses `WHERE session_date >= :from AND session_date < :to` — this drops all May 31 sessions. The inverse error: `to_date=2026-06-01` with `<=`, double-counting June 1 sessions in both May and June reports.

**Why it happens:**
Python `range()` and `datetime` arithmetic use half-open intervals `[start, end)`. This habit bleeds into SQL `WHERE` clauses. The existing system uses inclusive `end_date` semantics throughout (memberships, visits, reports in v1.8) — the convention is established but must be consciously followed.

**How to avoid:**
Standardize on the existing inclusive `end_date` semantics from v1.2 and v1.8. All report period filters: `date_column >= :period_start AND date_column <= :period_end`. This matches `memberships.end_date` (inclusive), `visits.gym_date` (inclusive), and the v1.8 revenue/visits report discipline. Write a golden test mirroring the v1.8 VER-02 pattern: a session on `period_end` date must appear in the report; a session on `period_end + 1 day` must not.

**Warning signs:**
- `session_date < :to_date` in any report SQL when `to_date` is the last day of the desired period
- Report total differs by 1 from a direct `SELECT COUNT(*) FROM pt_sessions WHERE session_date BETWEEN :start AND :end`

**Phase to address:**
Trainer report phase. Must be verified by the same golden-test discipline as VER-02 from Phase 57.

---

### Pitfall 13: Concurrent Payroll Runs — Race Condition Producing Duplicate Accrual Rows

**What goes wrong:**
Two HTTP requests (or two ARQ task invocations after a worker restart) both call the payroll run endpoint for the same trainer and period within milliseconds of each other. Both execute the application-layer "does a run exist?" check before either inserts the header row. Both pass. Both insert duplicate `trainer_payroll_runs` header rows and twice the accrual entries — doubling the payout liability for the period.

**Why it happens:**
Application-layer `SELECT ... WHERE` followed by `INSERT` is not atomic — classic TOCTOU. Developers who rely on the "check then act" pattern miss that the gap between the SELECT and INSERT is a valid race window, especially under concurrent requests.

**How to avoid:**
Do not use check-then-insert. Use `INSERT INTO trainer_payroll_runs ... ON CONFLICT (trainer_id, period_start, period_end) DO NOTHING RETURNING id`. If `RETURNING` yields no row, the run already exists — return 409 `payroll_period_already_run`. This is the DB-wins-the-race discipline applied throughout this system: visits `UNIQUE (client_id, gym_date)` (Phase 19), freeze periods `UNIQUE (membership_id) WHERE ended_at IS NULL` (Phase 25), booking race-safe `UNIQUE (slot_id) WHERE status='confirmed'` (Phase 38/v1.5). If payroll runs are triggered via an ARQ job, set `unique=True` on the task (matches `expire_memberships` and `send_expiring_notifications` discipline).

**Warning signs:**
- `SELECT count(*) FROM trainer_payroll_runs WHERE trainer_id = :id AND period_start = :start` followed by `INSERT` (TOCTOU race)
- No UNIQUE constraint on `(trainer_id, period_start, period_end)` in the migration
- ARQ payroll task without `unique=True`

**Phase to address:**
Payroll scaffold phase. UNIQUE constraint and `INSERT ... ON CONFLICT DO NOTHING RETURNING` must be in the first implementation.

---

### Pitfall 14: Slot Generation Race — Concurrent Cron Runs Inserting Duplicate Slots

**What goes wrong:**
Two ARQ worker processes (or a slow cron tick overlapping with the next scheduled run) both execute slot expansion simultaneously. Without `INSERT ... ON CONFLICT DO NOTHING`, the second run raises an `IntegrityError` from the UNIQUE constraint. If the `IntegrityError` is not caught and treated as idempotent success, the ARQ job fails, triggering retry logic, producing misleading error logs and potentially running a third time.

**Why it happens:**
Slot expansion cron is not declared `unique=True` in `WorkerSettings`. `IntegrityError` from the UNIQUE constraint is not caught as a success condition — it propagates as an unhandled exception and fails the job.

**How to avoid:**
ARQ cron: `unique=True, keep_result=60` (matches `expire_memberships` / `send_expiring_notifications` / `send_booking_reminders` discipline). SQL: `INSERT INTO trainer_availability_slots ... ON CONFLICT (trainer_id, slot_start_utc) DO NOTHING`. In the service layer: if a batch INSERT raises `IntegrityError` for any other reason (not the expected UNIQUE conflict), re-raise it. Log successful idempotent skips at `DEBUG` not `ERROR`. A cron restart must produce the same slot set — not a larger one.

**Warning signs:**
- Slot expansion cron missing `unique=True` in `WorkerSettings`
- `INSERT INTO trainer_availability_slots` without `ON CONFLICT DO NOTHING`
- ARQ job failure logs showing `UniqueViolation` errors from slot expansion

**Phase to address:**
Recurring slots phase. Both `unique=True` and `ON CONFLICT DO NOTHING` are day-one requirements, not optimizations.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `commission_rate FLOAT` on trainer row | Simple schema, one column | Float rounding errors in kopeck computation; rate change retroactively alters past accruals | Never — use integer numerator/denominator + versioned config rows |
| Payroll as live query view (no accrual rows) | No new table needed | Refunds, backdated sessions, and rate changes all silently alter amounts reported as "paid" | Never — accrual rows are required for audit chain integrity |
| `is_active = TRUE` filter in historical session reports | Matches live endpoints | Drops all history from deactivated trainers; understates utilization | Never in historical aggregation — only in live availability queries |
| Unbounded recurring slot generation | Simpler code, no horizon logic | O(years) slot rows; lock contention; storage waste | Never — cap at configurable horizon (4 weeks default) |
| Time-off insertion without checking confirmed bookings | Simpler insert | Trainer absent from confirmed appointment; client shows up to empty gym | Never — conflict check is a correctness requirement, not an optimization |
| Clawback via UPDATE to existing accrual row | Simpler than new adjustment row | Destroys audit chain; violates append-only ledger discipline | Never — signed-amount adjustment rows only |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `pt_sessions` + payroll accrual | JOIN on trainer without clarifying conducting vs. selling attribution | Decide and document attribution model first; use `pt_sessions.trainer_id` for fixed-per-session; use `pt_packages.trainer_id` for %-of-revenue |
| Refund flow + payroll | Refund issued without checking whether accrual row exists for the original payment | Lookup `trainer_payroll_entries.source_payment_id` in refund service; emit signed-amount clawback row in same UoW |
| Recurring slots + bookings | Slot generation ignores time-off blocks | Expansion cron joins against `trainer_time_off_blocks` to skip blocked windows |
| Time-off insertion + bookings FSM | Time-off inserted over confirmed booking without conflict check | `SELECT` confirmed bookings in the time range before INSERT; return 409 with conflict list |
| `trainer_availability_slots` + payroll | Payroll run counts slots (capacity) instead of sessions (actual completed work) | Payroll must aggregate `pt_sessions` (completed), never `trainer_availability_slots` (availability) |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Trainer report scans all `pt_sessions` without index on `session_date` | `/reports/trainers` endpoint times out | Add btree index `(session_date, trainer_id)` in the trainer-report Alembic migration — mirrors v1.8 Alembic 0040 audit-log indexes | From day one at small gym scale (no grace period at 500+ sessions) |
| Slot expansion query has no horizon window | Cron job takes >30s generating slots years into the future | `WHERE slot_start_utc <= NOW() + INTERVAL '4 weeks'` in expansion query | At 5+ trainers each with 3+ recurring rules |
| Payroll run aggregates all-time sessions without period index | `POST /payroll/run` slow after multi-month operation | Period filter on `session_date` uses the `(session_date, trainer_id)` composite index | After approximately 6 months of daily sessions |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Payroll endpoints accessible by reception role | Reception can trigger or view payroll, exposing individual trainer compensation | Owner-only RBAC via `OWNER_ONLY` set, `require_permission`, and route-introspection guard; three-way parity test with admin-web `can.ts` (extending `Resource` enum + `OWNER_ONLY` pairs) |
| Trainer utilization report exposes per-trainer revenue to reception | Revenue attribution data is owner-confidential | Report endpoint uses a new owner-only `Resource` entry mirroring `Resource.AUDIT_LOG` precedent (Phase 54) |
| `POST /payroll/mark-paid` without CSRF token | Replay attack marks payroll paid without owner action | CSRF dependency on all mutating POST/PATCH/DELETE — existing v1.1 discipline; no exception for payroll endpoints |

---

## "Looks Done But Isn't" Checklist

- [ ] **Payroll accrual rows:** Looks done when the endpoint returns correct totals — verify that `trainer_payroll_entries` rows are actually written, and that a second call to the same period+trainer returns 409, not a new row
- [ ] **Rate snapshot:** Looks done when rate is displayed correctly on the run — verify that changing `trainer_compensation_configs` AFTER the run does NOT change the stored `rate_snapshot_numerator` on existing accrual rows
- [ ] **Clawback:** Looks done when refunds work — verify that a refund issued after a payroll run with `status='paid'` creates a negative accrual adjustment row, not a silent omission
- [ ] **Time-off conflict check:** Looks done when time-off saves — verify via test that creating time-off over a date with a confirmed booking returns 409 with booking IDs in the response body
- [ ] **Recurring slots idempotency:** Looks done when slots appear after first cron run — verify that running the expansion cron twice produces the same row count (not double)
- [ ] **Deactivated trainer in report:** Looks done when active trainer stats are correct — verify that a deactivated trainer's historical `pt_sessions` appear in the utilization report
- [ ] **LOCKED_AUDIT_EVENTS pre-registration:** Looks done when audit rows appear — verify that all new payroll events (`payroll_accrual_created`, `payroll_marked_paid`, `payroll_adjustment_created`) are added to `LOCKED_AUDIT_EVENTS` in the bedrock phase BEFORE any callsite (INFRA-15 discipline from Phase 24)
- [ ] **RBAC three-way parity:** Looks done when backend 403s are correct — verify the three-way parity test (backend `OWNER_ONLY` + admin-web `can.ts` + `registry.ts`) is green after adding payroll and trainer-report `Resource` entries

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Recompute drift (payroll is a live view, no accrual rows) | HIGH | Schema migration to add `trainer_payroll_entries` + data migration to backfill from historical aggregates using rate snapshots; re-verify all past periods |
| Double-paid period (missing UNIQUE on runs) | MEDIUM | Add UNIQUE constraint; identify and audit duplicate run rows; write corrective negative adjustment entries to cancel the extra accruals |
| Wrong rounding mode discovered after payroll run | LOW | Write corrective adjustment entries for the rounding delta; no schema change needed |
| Missing clawback (refund issued post paid-payroll, no adjustment row) | MEDIUM | Identify all refunds of payments in already-paid payroll periods via SQL; write manual negative adjustment entries; add the clawback hook to the refund service going forward |
| Time-off inserted over confirmed bookings (bookings orphaned) | MEDIUM | Identify confirmed bookings inside time-off blocks via SQL; cancel them through the booking FSM with audit trail; add the conflict check before time-off insert |
| Read-only discipline violated (ORM import in reports module) | LOW | Remove the ORM import; rewrite affected query as `text()`; `import-linter` CI gate prevents this from reaching main if enforced from the first commit |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Recompute drift — payroll as view not ledger | Payroll scaffold (Phase 58 est.) | Test: update a payment post-run; verify accrual row unchanged |
| Double-paying a period — missing UNIQUE | Payroll scaffold | Test: call payroll run twice for same period+trainer; second call returns 409 |
| Percentage rounding integer error | Payroll scaffold | Unit test: `_compute_commission(333300, 33, 100)` produces `math.ceil` result |
| Refund-after-payroll clawback | Payroll accrual + refund integration | Test: mark payroll paid, issue refund, verify negative adjustment row created |
| Rate config mid-period retroactive change | Payroll scaffold (schema) | Test: change config post-run; verify `rate_snapshot_numerator` on accrual unchanged |
| Revenue attribution (sold vs. conducted) | Payroll design (first payroll phase plan) | Key Decision documented before payroll SQL written |
| DST expansion bugs for recurring slots | Recurring slots phase | Golden test: `expand_slot(MONDAY, 10:00 MSK)` produces correct UTC timestamp |
| Infinite/excessive slot generation | Recurring slots phase | Test: two cron runs produce same row count; horizon limits slots to 4 weeks |
| Time-off vs. confirmed booking conflict | Time-off phase | Test: time-off over confirmed booking returns 409 with conflicting booking IDs |
| Read-only discipline leak (ORM import in reports) | Trainer report phase | `import-linter` CI gate fails before merge; zero new ignores |
| Aggregation over soft-deleted trainers | Trainer report phase | Test: deactivated trainer sessions appear in period report |
| Period-boundary off-by-one | Trainer report phase | Golden test: session on `period_end` appears; session on `period_end + 1` does not |
| Concurrent payroll run race | Payroll scaffold | Race test: two concurrent run requests; only one succeeds, second returns 409 |
| Slot generation race | Recurring slots phase | Race test: two concurrent cron ticks; slot count identical after both ticks |

---

## Sources

- Sportzal PROJECT.md Key Decisions: snapshot pricing (Phase 17 / v1.2), ceil rounding for freeze (Phase 25 / v1.3), UNIQUE idempotency keys on notifications (Phase 27 / v1.3), DB-wins-the-race pattern for visits and freeze (Phase 19/25), append-only ledger with signed-amount refunds (v1.4), LOCKED_AUDIT_EVENTS pre-registration before callsites (INFRA-15 / Phase 24 / v1.3), read-only reports discipline D-54-07/D-54-08 (Phase 54 / v1.8), `trainer_name_snapshot NOT NULL` on pt_sessions (B-05 / v1.4), `gym_date STORED AT TIME ZONE 'Europe/Moscow'` canonical TZ discipline (Phase 19 / v1.2), `unique=True, keep_result=60` ARQ cron pattern (Phase 18/27/v1.5), booking race-safe `UNIQUE (slot_id) WHERE status='confirmed'` (v1.5), `INSERT ... ON CONFLICT DO NOTHING` idempotency (v1.3/v1.5/v1.6), three-way RBAC parity test (v1.1 through v1.8)

---
*Pitfalls research for: trainer payroll-ledger + recurring schedule + time-off + utilization report (Sportzal v1.9)*
*Researched: 2026-05-24*
