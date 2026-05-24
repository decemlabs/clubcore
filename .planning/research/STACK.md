# Stack Research: v1.9 Trainers Complete

**Project:** Sportzal
**Milestone:** v1.9 — Trainers Complete (payroll-ledger + recurring schedule + trainer-usage report)
**Researched:** 2026-05-24
**Confidence:** HIGH — no new dependencies are needed; all findings are based on direct inspection of the existing locked stack and codebase

---

## Verdict: Zero New Dependencies

All four v1.9 features are fully implementable with the locked stack as it stands today.
No library should be added to `pyproject.toml`.

The sections below explain exactly which existing primitives to reuse for each feature.

---

## Feature A: Trainer Payroll Ledger

### Pattern to reuse: v1.4 `payments` append-only ledger

The `payments` table and its service are the exact model for the payroll ledger.

**What to replicate:**

- Append-only ORM model with NO `TimestampMixin` and NO `SoftDeleteMixin` — single temporal column only (`accrued_at`), mirroring `payments.received_at` (D-32-01..D-32-04).
- `session.add()` only — no `UPDATE` or `DELETE` against the new ledger table. The SVC001 AST commit-gate must cover the new service file.
- `LOCKED_AUDIT_EVENTS` pre-registration before any callsite (INFRA-15 discipline — v1.3 Phase 24 precedent). New payroll events (`payroll_accrual_recorded`, `payroll_period_run`, `payroll_marked_paid`) must be added to the frozenset in `app/core/audit.py` in the first payroll phase, before any service code that emits them.
- Atomic audit chain: INSERT ledger row → `session.flush()` → `audit.emit(...)` → `session.commit()` — identical to `payments.service.record_payment`.
- `# noqa: SVC001 caller-owns-txn` on any Protocol-slot helpers that participate in a larger UoW.

**What changes vs. v1.4 payments:**

- New `subject_kind` value: `'payroll'` (or name it `'trainer_payroll'`). The existing `payments` table CHECK constraint `ck_payments_subject_kind` only allows `'membership'`, `'pt_package'`, and `'refund'` — payroll is a different business concept and needs its OWN table (`trainer_payroll_ledger`), not a new `subject_kind` on the existing `payments` table. This avoids polluting the revenue report query (which sums `payments` for client-facing transactions) with payroll entries.
- A separate `trainer_compensation_config` table (per-trainer configurable rate: `pct_of_pt_revenue NUMERIC(5,4)` and/or `fixed_per_session_kopecks INTEGER`) with `UNIQUE (trainer_id)` — owner-settable. The compensation config is read-only by the payroll run job; mutations go through a dedicated service.

**Money math (integer kopecks throughout):**

- Percentage comp: `floor(pt_package_revenue_kopecks * pct_of_pt_revenue)` — Python `int(decimal.Decimal(kopecks) * decimal.Decimal(pct))` with `ROUND_DOWN` rounding mode. The Python `decimal` stdlib module is sufficient; no new library needed.
- Fixed-per-session: `fixed_per_session_kopecks * session_count` — pure integer arithmetic.
- Combined: sum both components. The ledger row stores the gross accrual in kopecks (integer, always positive for accrual rows, negative for paid-marking rows if reversals are modeled, mirroring the v1.4 signed-amount pattern).

**No new library needed for decimal math.** Python's `decimal.Decimal` with `ROUND_DOWN` rounding (stdlib since Python 2.4) handles kopeck-accurate percentage calculations. `Decimal('5000000') * Decimal('0.30')` = `Decimal('1500000.0')` — call `int(result.to_integral_value(rounding=ROUND_DOWN))`. Do not introduce `mpmath`, `gmpy2`, or any external numeric library.

**Payroll period run:**

- Owner triggers via `POST /api/v1/payroll/run` with `{trainer_id, period_from, period_to}` query.
- Service queries `pt_sessions` (non-cancelled, within period, for trainer) → computes accrual → INSERTs ledger row → emits audit → commits. Cross-module reads via Protocol slot (same pattern as `bookings.service` querying `pt_packages`).
- Raw-SQL cross-module read of `pt_sessions` is acceptable per D-54-08 (same discipline as reports module). No ORM import of `PtSession` in the payroll module.

**"Paid" marking:**

- Separate `POST /api/v1/payroll/{ledger_row_id}/mark-paid` endpoint. Appends a new row (negative amount = disbursement, or a status-flip on the accrual row with `paid_at` nullable column). The append-only pattern means a status column (`accrued` / `paid`) on the ledger row is simpler — no second negative-amount row needed, since payroll disbursement is not a client-facing financial transaction that needs double-entry. Keep it as a nullable `paid_at TIMESTAMPTZ` on the ledger row (not append-only flip — an UPDATE, but a single-column update that is acceptable per the "mark as paid" semantics; document explicitly in the ORM docstring why this deviates from strict append-only).

---

## Feature B: Recurring Trainer Availability Slots (Day-of-Week Patterns)

### Approach: Generation-on-write via service layer, not a recurrence library

**Verdict: Do NOT add `python-dateutil` or any rrule library.** Sportzal's recurrence model is simple: day-of-week + time pattern, repeated for N weeks (or until date). This does not require RFC 5545 RRULE semantics. A custom generator is 15 lines of Python stdlib code.

**Why python-dateutil is not warranted:**

- The recurrence model is "every Monday at 10:00 for 4 weeks" — not "every 3rd Friday of a month except on public holidays with EXDATE exceptions." rrule was designed for calendar app complexity that Sportzal does not have.
- `python-dateutil` is ~300KB, adds a transitive `six` dependency risk (older versions), and requires mypy stubs via `types-python-dateutil`. None of this is justified for DOW + time repetition.
- The existing code already handles datetime arithmetic with Python stdlib `datetime` + `zoneinfo.ZoneInfo('Europe/Moscow')`. v1.2's `gym_date STORED` column, v1.3's `expire_memberships` cron, and v1.5's slot overlap detection all use stdlib datetime — the pattern is established.

**Recommended implementation:**

```python
# Conceptual — generate concrete slot datetimes from a recurring pattern.
# No external library needed.
from datetime import date, timedelta, time as dt_time
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

def generate_slot_datetimes(
    *,
    weekday: int,           # 0=Monday .. 6=Sunday
    start_time: dt_time,    # naive time in Moscow
    end_time: dt_time,
    from_date: date,        # inclusive
    to_date: date,          # inclusive
) -> list[tuple[datetime, datetime]]:
    slots = []
    current = from_date
    while current <= to_date:
        if current.weekday() == weekday:
            start = datetime.combine(current, start_time, tzinfo=MSK)
            end = datetime.combine(current, end_time, tzinfo=MSK)
            slots.append((start, end))
        current += timedelta(days=1)
    return slots
```

**Where generation runs:**

- Owner sends `POST /api/v1/schedule/recurring-patterns` with `{trainer_id, weekday, start_time, end_time, from_date, to_date}`.
- Service generates concrete datetimes, then calls `publish_slot()` for each — reusing the existing overlap-check + buffer-check + audit chain exactly as for manual slots.
- No ARQ cron needed for slot generation. Generation-on-write is immediate and bounded (max ~52 slots per year per pattern, trivially fast).
- The `trainer_recurring_patterns` table stores the pattern for display/deletion (soft-cancel all matching slots). It does NOT drive slot generation lazily — generate eagerly on creation.

**Timezone handling:** Use `zoneinfo.ZoneInfo('Europe/Moscow')` (Python 3.9+ stdlib, already available in Python 3.12). The existing codebase uses `datetime.now(UTC)` for UTC-aware datetimes; for MSK-local slot generation, `datetime.combine(date, time, tzinfo=MSK)` produces the correct tz-aware datetime. No `pytz` or `babel` needed.

---

## Feature C: Trainer Time-Off / Unavailability Blocks

### Pattern to reuse: Partial-unique constraint + overlap detection (v1.5 slot discipline)

**No new library needed.**

- New ORM model `TrainerTimeOff` (table `trainer_time_offs`): `trainer_id FK`, `starts_at TIMESTAMPTZ`, `ends_at TIMESTAMPTZ`, `reason TEXT`, `created_by_user_id FK`. Inherits `Base + UUIDPkMixin + TimestampMixin`.
- Overlap detection for slot publication: extend `schedule.repository.find_overlapping_slots_for_update` to also check `trainer_time_offs` for the same trainer. Use the existing `tstzrange` operator pattern already in place for slot overlap.
- Recurring-slot generation: the generator skips dates that fall within a time-off block (check before calling `publish_slot`).
- No ARQ cron needed — time-off is a write-once record; slot cancellation on time-off creation is handled synchronously (owner creates time-off → service cancels any conflicting existing slots in the same transaction, mirroring the `cancel_slot` booked-cascade pattern).

---

## Feature D: Trainer-Usage / Top-Trainers Report

### Pattern to reuse: v1.8 reports module read-only discipline (D-54-07/08)

**No new library needed.**

- New endpoints in `app/modules/reports/router.py` (or a new `trainer_reports` sub-section of the same router).
- Strictly read-only: no `models.py`, raw-SQL `text()` cross-module reads per D-54-08. Reads across `pt_sessions`, `bookings`, `trainer_availability_slots`, `trainers`, `payments`.
- Owner-only RBAC — extend `OWNER_ONLY` with `(VIEW, TRAINER_USAGE)` mirrored byte-for-byte into admin-web `can.ts` (three-way parity test green requirement).
- Date aggregation deterministic in `Europe/Moscow` — use `AT TIME ZONE 'Europe/Moscow'` in raw SQL, same as `fetch_revenue_buckets` and `fetch_visits_daily`.
- CSV export follows the v1.8 UTF-8 BOM + RFC-4180 excel dialect pattern in `csv_export.py`.

**Metrics derivable from existing tables (no new tables or columns needed):**

```sql
-- Top trainers by completed PT sessions (non-cancelled) in period
SELECT
    t.id AS trainer_id,
    t.full_name,
    COUNT(ps.id) FILTER (WHERE ps.cancelled_at IS NULL) AS sessions_completed,
    COUNT(ps.id) FILTER (WHERE ps.cancelled_at IS NOT NULL) AS sessions_cancelled
FROM pt_sessions ps
JOIN trainers t ON t.id = ps.trainer_id
WHERE (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date
GROUP BY t.id, t.full_name
ORDER BY sessions_completed DESC;

-- PT utilization: slots vs bookings vs sessions
SELECT
    t.id AS trainer_id,
    t.full_name,
    COUNT(DISTINCT s.id) AS slots_published,
    COUNT(DISTINCT b.id) FILTER (WHERE b.status != 'cancelled') AS bookings_confirmed,
    COUNT(DISTINCT ps.id) FILTER (WHERE ps.cancelled_at IS NULL) AS sessions_completed
FROM trainers t
LEFT JOIN trainer_availability_slots s ON s.trainer_id = t.id
    AND (s.start_time AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date
LEFT JOIN bookings b ON b.slot_id = s.id
LEFT JOIN pt_sessions ps ON ps.trainer_id = t.id
    AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date
WHERE t.deleted_at IS NULL
GROUP BY t.id, t.full_name
ORDER BY sessions_completed DESC;
```

Both queries are expressible in raw SQL with no new indexes beyond what v1.4 already added (`ix_pt_sessions_trainer_id_performed_at_desc` — already exists in `pt_sessions/models.py:131`). A covering index on `trainer_availability_slots(trainer_id, start_time)` already exists as `ix_trainer_availability_slots_trainer_start_time`.

---

## ARQ Cron: What v1.9 Adds

- **Recurring-slot generation:** NO new cron. Generation is on-write (eagerly on `POST /schedule/recurring-patterns`). ARQ cron is the wrong tool here — patterns are gym-config-level writes, not time-driven operations.
- **Payroll run:** NO automated cron for payroll. Payroll runs are owner-initiated (sensitive financial operation, not safe to automate without explicit owner trigger). The service function is callable ad-hoc; no `arq.cron(...)` entry needed.
- **Time-off expiry cleanup:** NO cron needed. Time-off blocks are soft-deactivatable; no auto-expiry is required for v1.9.

**Cron count stays at current 8 jobs** (expire_memberships, send_expiring_notifications, expire_pt_packages, send_booking_reminders, mark_no_show_bookings, cleanup_password_reset_tokens, monitor_stale_fiscal_receipts, poll_pending_refunds).

---

## Existing Primitives Inventory for v1.9

| What v1.9 needs | Existing primitive to reuse | Location |
|---|---|---|
| Append-only ledger rows | `Payment` ORM + `record_payment()` pattern | `app/modules/payments/` |
| Integer kopeck math | Python stdlib `decimal.Decimal` with `ROUND_DOWN` | stdlib |
| Audit chain (pre-register events) | `LOCKED_AUDIT_EVENTS` frozenset + `audit.emit()` | `app/core/audit.py` |
| Per-row hash for audit traceability | `payment_row_hash()` pattern (optional — payroll is simpler) | `app/core/audit_hash.py` |
| Overlap detection (tstzrange) | `find_overlapping_slots_for_update()` | `app/modules/schedule/repository.py` |
| Day-of-week slot generation | `datetime.combine` + `zoneinfo.ZoneInfo('Europe/Moscow')` | stdlib |
| MSK timezone | `zoneinfo.ZoneInfo('Europe/Moscow')` (already used everywhere) | stdlib |
| Raw-SQL cross-module read | `text()` + `.mappings().all()` pattern | `app/modules/reports/repository.py` |
| CSV export (UTF-8 BOM + RFC-4180) | `csv_export.py` helpers | `app/modules/reports/csv_export.py` |
| Owner-only RBAC guard | `require_permission` + `OWNER_ONLY` extension | `app/core/dependencies.py` |
| Three-way RBAC parity | `Resource` StrEnum + `OWNER_ONLY` pairs | `app/core/rbac.py` + `admin-web/can.ts` |
| Protocol-slot cross-module resolver | `register_*` pattern in `app/main.py` | `app/core/dependencies.py` |
| Soft-delete pattern | `SoftDeleteMixin` + partial UNIQUE | `app/core/database.py` |
| SAVEPOINT test isolation | Existing pytest fixtures | `tests/conftest.py` |
| SVC001 commit-gate AST walker | Existing test | `tests/unit/test_service_commit_gate.py` |
| Append-only AST walker | Existing test | `tests/unit/test_payments_appendonly.py` |

---

## What NOT to Add

| Package | Reason |
|---|---|
| `python-dateutil` / `dateutil.rrule` | DOW+time recurrence is 15 lines of stdlib datetime; rrule complexity is not needed; would add types-python-dateutil dev dep for mypy |
| `mpmath`, `gmpy2`, `sympy` | Integer kopeck arithmetic needs only `decimal.Decimal` from stdlib |
| `pandas`, `numpy` | All aggregation is done in Postgres SQL; no in-process data frames needed |
| `celery`, `dramatiq` | ARQ is the locked task queue; do not introduce a second queue |
| Any `pytz` | `zoneinfo` (stdlib Python 3.9+) is the project convention; `datetime.now(UTC)` already present |
| `icalendar`, `recurring_ical_events` | iCal RFC-5545 complexity is not required; DOW pattern is internally modeled |
| `babel` (for locale formatting) | v1.9 is backend-only; formatting is frontend concern (v2.0); CSV export uses existing pattern |

---

## Alembic Migrations Required

Current revision: `0040`. v1.9 will add new revisions (start at `0041`):

| Migration | Purpose |
|---|---|
| `0041_trainer_compensation_config` | New table `trainer_compensation_configs` — per-trainer payroll rates |
| `0042_trainer_payroll_ledger` | New table `trainer_payroll_ledger` — append-only accrual rows |
| `0043_trainer_recurring_patterns` | New table `trainer_recurring_patterns` — DOW+time pattern definitions |
| `0044_trainer_time_offs` | New table `trainer_time_offs` — unavailability blocks |
| `0045_trainer_report_indexes` | New indexes over `pt_sessions(trainer_id, performed_at)` if needed (may already be covered by `ix_pt_sessions_trainer_id_performed_at_desc`) |

All migrations follow the existing `NAMING_CONVENTION` in `alembic/env.py`. No new Alembic plugins needed.

---

## Sources

- Direct codebase inspection (no external lookup needed — stack is locked):
  - `/apps/backend/pyproject.toml` — confirmed current deps; no additions required
  - `/apps/backend/app/modules/payments/models.py` — append-only ledger discipline
  - `/apps/backend/app/modules/payments/service.py` — `record_payment` / `issue_refund` UoW pattern
  - `/apps/backend/app/modules/payments/constants.py` — `SUBJECT_KIND_*` pattern
  - `/apps/backend/app/modules/reports/repository.py` — D-54-08 raw-SQL read-only pattern
  - `/apps/backend/app/modules/schedule/models.py` — `TrainerAvailabilitySlot` + tstzrange overlap discipline
  - `/apps/backend/app/modules/schedule/service.py` — `publish_slot` overlap/buffer check pattern
  - `/apps/backend/app/modules/pt_sessions/models.py` — `ix_pt_sessions_trainer_id_performed_at_desc` already exists
  - `/apps/backend/app/modules/trainers/models.py` — `Trainer` catalog-only baseline
  - `/apps/backend/app/workers/__init__.py` — ARQ WorkerSettings + cron registration discipline
  - `/apps/backend/app/workers/scheduled/expire_memberships.py` — canonical cron job shape
  - `/apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` + INFRA-15 pre-registration discipline
  - `.planning/PROJECT.md` — v1.9 milestone scope, v1.4/v1.8 decisions locked

---

*Stack research for: v1.9 Trainers Complete*
*Researched: 2026-05-24*
