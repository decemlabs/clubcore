# Architecture Research

**Domain:** v1.9 Trainers Complete — payroll-ledger, recurring slots, time-off, trainer-usage report
**Researched:** 2026-05-24
**Confidence:** HIGH (based on direct codebase inspection of all relevant modules)

---

## System Overview

The existing backend is a FastAPI modular monolith with four structural zones enforced by import-linter. The key constraint for v1.9 is that `app.core` may not import `app.modules`, and modules may not import each other directly. All cross-module communication flows through Protocol slots registered in `app/main.py`.

```
┌─────────────────────────────────────────────────────────────┐
│                    app/main.py (composition root)            │
│  register_*(slot) wires Protocol slots at startup            │
│  only file allowed to import across core ↔ modules          │
├──────────────────────┬──────────────────────────────────────┤
│   app/core/          │   app/modules/<domain>/              │
│   permissions.py     │   router.py  service.py  models.py   │
│   dependencies.py    │   schemas.py repository.py ...       │
│   audit.py           │                                      │
│   (Protocol slots)   │   NO cross-module imports (linter)   │
├──────────────────────┴──────────────────────────────────────┤
│   app/integrations/       app/workers/                      │
│   telegram/               scheduled/ (ARQ crons)             │
│   email/                  tasks/ (ARQ jobs)                  │
│   yookassa/               telegram_bot.py                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Question 1: Where Does Payroll Live?

### Decision: New `app/modules/payroll/` module

Payroll is a new business entity with its own ledger table (`payroll_accruals`), endpoints, and audit chain. It belongs in a new module, not in `trainers` (which is catalog-only reference data with soft-delete, no financial logic) and not in `payments` (which is the generic incoming-money ledger, not an outgoing-wages ledger).

**Module file layout:**
```
app/modules/payroll/
├── __init__.py
├── models.py           # TrainerCompConfig + PayrollAccrual ORM
├── schemas.py          # Pydantic request/response + wire shapes
├── repository.py       # DB reads/writes for payroll tables
├── service.py          # run_payroll_period, mark_accrual_paid, list_accruals
├── router.py           # POST /payroll/run, PATCH /{id}/paid, GET /payroll/accruals
└── constants.py        # comp model literals, LOCKED audit events pre-declared
```

### The `payroll_accruals` Table (v1.4 payments discipline)

The payroll ledger follows the same append-only discipline as `payments`. Each accrual is an immutable row; marking it paid is a single-column status flip allowed only once (UNIQUE (trainer_id, period_start, period_end) enforces one run per trainer per period).

```
payroll_accruals
├── id                UUID PK
├── trainer_id        FK -> trainers.id ON DELETE RESTRICT
├── period_start      Date NOT NULL          -- MSK inclusive
├── period_end        Date NOT NULL          -- MSK inclusive
├── comp_model        Text NOT NULL          -- 'pct_of_revenue' | 'fixed_per_session' | 'both'
├── sessions_count    Integer NOT NULL        -- pt_sessions in period (snapshot at run time)
├── revenue_kopecks   Integer NOT NULL        -- sum of pt_package payments in period (snapshot)
├── fixed_per_session_kopecks  Integer NOT NULL DEFAULT 0
├── pct_of_revenue_bps         Integer NOT NULL DEFAULT 0  -- basis points (1% = 100 bps)
├── accrual_kopecks   Integer NOT NULL CHECK (accrual_kopecks >= 0)
├── status            Text NOT NULL CHECK IN ('pending','paid')  server_default='pending'
├── paid_at           DateTime(tz) nullable
├── paid_by_user_id   FK -> users.id ON DELETE RESTRICT nullable
├── audit_log_id      FK -> audit_log.id ON DELETE SET NULL nullable
├── created_at        DateTime(tz) NOT NULL server_default=now()
│
── UNIQUE (trainer_id, period_start, period_end)  -- one run per trainer per period
── INDEX (trainer_id, period_start DESC)
── INDEX (status, period_start DESC)              -- pending accruals listing
```

This follows the v1.4 append-only discipline: no `updated_at`, no `deleted_at`, no UPDATE to `accrual_kopecks`. The `status` flip to `paid` is the only mutation allowed (mirrors the `pt_packages.status` single-transition pattern).

### Where Does Trainer Comp Config Live?

**In the `payroll` module, NOT `trainers`.**

Rationale: comp config is payroll domain data (rate settings, compensation model). The `trainers` module is catalog-only reference data (CRUD with soft-delete + active flag). Mixing financial configuration into the catalog module would couple a financial concept into a non-financial module. A new table `trainer_comp_configs` lives under `payroll/models.py`.

```
trainer_comp_configs
├── id                UUID PK
├── trainer_id        FK -> trainers.id ON DELETE RESTRICT UNIQUE  -- one config per trainer
├── comp_model        Text NOT NULL CHECK IN ('pct_of_revenue','fixed_per_session','both')
├── fixed_per_session_kopecks  Integer NOT NULL DEFAULT 0 CHECK (>= 0)
├── pct_of_revenue_bps         Integer NOT NULL DEFAULT 0 CHECK (>= 0, <= 10000)
├── effective_from    Date NOT NULL
├── created_at        DateTime(tz) NOT NULL server_default=now()
├── updated_by_user_id  FK -> users.id ON DELETE RESTRICT nullable
│
── INDEX (trainer_id)   -- resolver
```

`UNIQUE (trainer_id)` enforces one active config per trainer. Owner can `PUT /payroll/trainer-configs/{trainer_id}` to create or overwrite (upsert semantics: INSERT ... ON CONFLICT DO UPDATE SET ...).

### Cross-Module Read for Payroll Calculation

`payroll.service.run_payroll_period` needs two cross-module reads:

1. **PT-package revenue (from `payments`):** How much revenue came in for this trainer's sessions during the period.
2. **PT-sessions count (from `pt_sessions`):** How many sessions this trainer conducted.

**Mechanism: raw-SQL `text()` reads -- NOT Protocol slots.**

Protocol slots are for callback/write operations (activating memberships, recording payments, completing bookings). Read-only cross-module data is handled with raw-SQL `text()` reads exactly as the v1.8 `reports` module does it (D-54-08 precedent). The payroll service calls a helper in `payroll/repository.py`:

```python
# payroll/repository.py (cross-module read discipline)
# CROSS-MODULE READ: pt_sessions + pt_packages + payments
# Verified columns:
#   pt_sessions: trainer_id, pt_package_id, performed_at, cancelled_at
#     (apps/backend/app/modules/pt_sessions/models.py:52-97)
#   payments: subject_kind, subject_id, amount_kopecks, received_at
#     (apps/backend/app/modules/payments/models.py:52-64)
#   pt_packages: id (FK bridge between pt_sessions.pt_package_id and payments.subject_id)
async def fetch_trainer_session_revenue(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> dict[str, int]:
    row = (
        await session.execute(
            text(
                "SELECT "
                "  COUNT(DISTINCT ps.id) FILTER (WHERE ps.cancelled_at IS NULL) "
                "    AS session_count, "
                "  COALESCE(SUM(p.amount_kopecks) FILTER ("
                "    WHERE p.subject_kind = 'pt_package' AND p.amount_kopecks > 0"
                "  ), 0) AS revenue_kopecks "
                "FROM pt_sessions ps "
                "JOIN pt_packages pkg ON pkg.id = ps.pt_package_id "
                "JOIN payments p "
                "  ON p.subject_id = pkg.id "
                "  AND p.subject_kind = 'pt_package' "
                "  AND p.amount_kopecks > 0 "
                "WHERE ps.trainer_id = :trainer_id "
                "  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date "
                "      BETWEEN :period_start AND :period_end "
            ),
            {
                "trainer_id": str(trainer_id),
                "period_start": period_start,
                "period_end": period_end,
            },
        )
    ).mappings().one()
    return {"session_count": int(row["session_count"]), "revenue_kopecks": int(row["revenue_kopecks"])}
```

No `from app.modules.pt_sessions import ...` or `from app.modules.payments import ...` in `payroll/`. Zero new `ignore_imports` edges in `.importlinter`. The `payroll` module is added to the `modules-independent` contract list before any code lands (INFRA-15 discipline).

**Why not a Protocol slot for this?**

Protocol slots are for bi-directional callbacks where the callee needs to reach back into a different module's write path. The payroll calculation only needs a read-only projection from two tables. Raw-SQL text() reads are cheaper, more direct, and keep the dependency graph flat -- the same choice made for `reports` in v1.8.

### Atomic Audit Chain for Payroll

`payroll.service.run_payroll_period` follows the v1.4 UoW discipline:

```
1. SELECT trainer comp config (own table, no cross-module)
2. fetch_trainer_session_revenue (raw SQL, same session)
3. compute accrual_kopecks
4. INSERT payroll_accruals row
5. audit.emit("payroll_accrual_created", resource_type="payroll_accrual", ...)
6. session.commit()  -- accrual row + audit row atomic
```

`mark_accrual_paid` is a separate UoW:
```
1. SELECT payroll_accrual FOR UPDATE
2. Verify status == 'pending' (409 if already paid)
3. UPDATE status='paid', paid_at=now(), paid_by_user_id=actor.id
4. audit.emit("payroll_accrual_paid", resource_type="payroll_accrual", ...)
5. session.commit()
```

---

## Question 2: Recurring Slots and Time-Off Blocks

### Decision: Extend `app/modules/schedule/`, NOT a new module

Both recurring slots and time-off blocks are schedule domain concerns. They reference `trainer_availability_slots` (the existing table) and `trainers`. A new module would require either cross-module imports (violating the linter) or Protocol slots for what is fundamentally schedule data. The schedule module already owns slot creation, overlap detection, and the `restore_slot_to_active` Protocol slot.

### New Tables in `schedule/models.py`

**`recurring_slot_templates`** -- defines the weekly recurrence pattern:

```
recurring_slot_templates
├── id                UUID PK
├── trainer_id        FK -> trainers.id ON DELETE RESTRICT
├── day_of_week       SmallInteger NOT NULL CHECK (0..6)  -- 0=Mon ISO
├── start_hour        SmallInteger NOT NULL CHECK (0..23)
├── start_minute      SmallInteger NOT NULL CHECK (0..59)
├── duration_minutes  SmallInteger NOT NULL CHECK (> 0)
├── is_active         Boolean NOT NULL DEFAULT TRUE
├── created_by_user_id  FK -> users.id ON DELETE RESTRICT
├── created_at        DateTime(tz) NOT NULL
├── cancelled_at      DateTime(tz) nullable
│
── INDEX (trainer_id, day_of_week)
── PARTIAL INDEX (trainer_id) WHERE is_active = TRUE
```

**`trainer_time_off`** -- blocks of unavailability:

```
trainer_time_off
├── id              UUID PK
├── trainer_id      FK -> trainers.id ON DELETE RESTRICT
├── starts_at       DateTime(tz) NOT NULL
├── ends_at         DateTime(tz) NOT NULL
├── reason          Text nullable
├── created_by_user_id  FK -> users.id ON DELETE RESTRICT
├── created_at      DateTime(tz) NOT NULL
├── cancelled_at    DateTime(tz) nullable  -- soft-cancel (keeps history)
│
── CHECK (ends_at > starts_at)
── INDEX (trainer_id, starts_at)
── PARTIAL INDEX (trainer_id, starts_at, ends_at) WHERE cancelled_at IS NULL
```

### Recurring Slot Expansion Strategy

**ARQ cron generate-ahead, NOT expand-on-read.**

Expand-on-read would require the slot-listing endpoint to dynamically materialize virtual slots on every GET -- adding virtual/real reconciliation logic, complicating the booking FSM (you cannot book a virtual slot), and breaking the `bookings -> schedule` Protocol slot dependency. The existing `trainer_availability_slots` table is the single source of truth for bookable slots; this must stay.

The `generate_recurring_slots` ARQ cron runs daily (07:00 MSK, after the 06:35 reminder cron) and materializes slots for a rolling 14-day window ahead of the current date. Idempotency is enforced by extending the UNIQUE constraint on `trainer_availability_slots` to include `(trainer_id, start_time)` -- the cron uses INSERT ... ON CONFLICT DO NOTHING.

```
generate_recurring_slots cron (ARQ, 07:00 MSK):
  For each active recurring_slot_template:
    For each day in [today+1 .. today+14]:
      Compute start_time = date + start_hour:start_minute (MSK -> UTC)
      Compute end_time = start_time + duration_minutes
      Check: any active trainer_time_off overlaps (start_time, end_time)?
        SELECT WHERE trainer_id=? AND cancelled_at IS NULL
        AND tstzrange(starts_at, ends_at) && tstzrange(start_time, end_time)
      If overlap: skip
      INSERT INTO trainer_availability_slots
        (trainer_id, start_time, end_time, status='active', created_by_user_id=NULL)
        ON CONFLICT (trainer_id, start_time) DO NOTHING
      If rowcount == 1: audit.emit("slot_published", ...)  -- only on real insert
  session.commit()
```

`created_by_user_id` on `trainer_availability_slots` must become nullable (Alembic migration). System-generated slots carry NULL -- distinguishable from manually published slots.

### Time-Off Interaction with Confirmed Bookings

When a time-off block is created that overlaps with existing `status='booked'` slots, the system blocks time-off creation with a 409 conflict.

**Recommended: 409 conflict listing affected slot IDs, requiring owner to resolve manually.**

Automatic cancellation without notifying clients is operationally dangerous and requires cross-module writes (bookings FSM). The owner should manually cancel conflicting bookings via the existing `PATCH /bookings/{id}/cancel` endpoint, then create the time-off block. The time-off creation service queries:

```python
# schedule/repository.py
# SELECT COUNT(*) FROM trainer_availability_slots
# WHERE trainer_id = :trainer_id AND status = 'booked'
# AND tstzrange(start_time, end_time) && tstzrange(:starts_at, :ends_at)
```

If count > 0, raise `409 TimeOffConflictsWithBookings` with affected slot IDs.

The `generate_recurring_slots` cron skips slot generation for any window covered by active `trainer_time_off` rows. It does NOT retroactively cancel already-booked slots that fall within a newly created time-off window; only forward-looking slot generation is blocked.

---

## Question 3: Trainer-Usage Report

### Decision: Extend `app/modules/reports/` -- pure read-only raw-SQL reads

The v1.8 reports module established the D-54-07/D-54-08 discipline: no `models.py`, raw-SQL `text()` cross-module reads, no writes. The trainer-usage report fits exactly in this module with no structural changes to the discipline.

**New endpoint:** `GET /api/v1/reports/trainers` (owner-only)
**New CSV endpoint:** `GET /api/v1/reports/trainers.csv`

**Report shape:**

```python
class TrainerUsageItem(BaseModel):
    trainer_id: UUID
    trainer_name: str
    sessions_count: int           # non-cancelled pt_sessions in period
    bookings_count: int           # confirmed + completed bookings in period
    utilization_hours: float      # sum of (end_time - start_time) hours for booked slots
    revenue_kopecks: int          # sum of positive pt_package payments for trainer's sessions

class TrainerUsageReportResponse(BaseModel):
    trainers: list[TrainerUsageItem]
    from_date: date
    to_date: date
```

**Cross-module raw-SQL read in `reports/repository.py`:**

```python
# CROSS-MODULE READ (D-54-08): pt_sessions, bookings, trainer_availability_slots,
#   payments, pt_packages, trainers
# Verified columns:
#   trainers: id, full_name, deleted_at (apps/.../trainers/models.py:24-43)
#   pt_sessions: trainer_id, pt_package_id, performed_at, cancelled_at, booking_id
#     (apps/.../pt_sessions/models.py:52-111)
#   bookings: id, status, slot_id (apps/.../bookings/models.py)
#   trainer_availability_slots: id, start_time, end_time
#     (apps/.../schedule/models.py:52-130)
#   payments: subject_id, subject_kind, amount_kopecks
#     (apps/.../payments/models.py:52-64)
#   pt_packages: id (FK bridge)
async def fetch_trainer_usage(session, from_date, to_date):
    rows = (await session.execute(
        text("""
            SELECT
                t.id AS trainer_id,
                t.full_name AS trainer_name,
                COUNT(DISTINCT ps.id) FILTER (WHERE ps.cancelled_at IS NULL)
                    AS sessions_count,
                COUNT(DISTINCT b.id) FILTER (
                    WHERE b.status IN ('confirmed','completed')
                ) AS bookings_count,
                COALESCE(SUM(
                    EXTRACT(EPOCH FROM (s.end_time - s.start_time)) / 3600.0
                ) FILTER (WHERE b.status IN ('confirmed','completed')), 0.0)
                    AS utilization_hours,
                COALESCE(SUM(p.amount_kopecks) FILTER (
                    WHERE p.subject_kind = 'pt_package' AND p.amount_kopecks > 0
                ), 0) AS revenue_kopecks
            FROM trainers t
            LEFT JOIN pt_sessions ps
                ON ps.trainer_id = t.id
                AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date
                    BETWEEN :from_date AND :to_date
            LEFT JOIN bookings b ON b.id = ps.booking_id
            LEFT JOIN trainer_availability_slots s ON s.id = b.slot_id
            LEFT JOIN pt_packages pkg ON pkg.id = ps.pt_package_id
            LEFT JOIN payments p
                ON p.subject_id = pkg.id AND p.subject_kind = 'pt_package'
            WHERE t.deleted_at IS NULL
            GROUP BY t.id, t.full_name
            ORDER BY sessions_count DESC, t.full_name
        """),
        {"from_date": from_date, "to_date": to_date},
    )).mappings().all()
    return [dict(r) for r in rows]
```

No new `ignore_imports` edges needed. The `reports` module already has the infrastructure: date range validation, csv_export.py, StreamingResponse pattern, RBAC owner-only guard. The new trainer-usage endpoint reuses all of it verbatim.

---

## Question 4: New LOCKED Audit Events

All new events must be pre-registered in `LOCKED_AUDIT_EVENTS` in `app/core/audit.py` BEFORE any callsite is added (INFRA-15 discipline). Pre-register in the Phase 58 foundations phase.

**New events (7 total):**

| Event | Resource Type | When Emitted |
|---|---|---|
| `payroll_accrual_created` | `payroll_accrual` | `run_payroll_period` -- owner triggers payroll run |
| `payroll_accrual_paid` | `payroll_accrual` | `mark_accrual_paid` -- owner marks paid |
| `trainer_comp_config_set` | `trainer` | `set_trainer_comp_config` -- owner sets comp config |
| `recurring_slot_template_created` | `schedule_slot` | template published |
| `recurring_slot_template_cancelled` | `schedule_slot` | template deactivated |
| `trainer_time_off_created` | `trainer` | time-off block created |
| `trainer_time_off_cancelled` | `trainer` | time-off block cancelled |

`payroll_accrual_created` payload (new `PayrollAccrualCreatedPayload`):
```python
class PayrollAccrualCreatedPayload(AuditPayloadBase):
    accrual_id: UUID
    trainer_id: UUID
    period_start: str       # ISO date
    period_end: str         # ISO date
    comp_model: str
    sessions_count: int
    revenue_kopecks: int
    accrual_kopecks: int
```

`payroll_accrual_paid` payload:
```python
class PayrollAccrualPaidPayload(AuditPayloadBase):
    accrual_id: UUID
    trainer_id: UUID
    paid_by_user_id: UUID
    accrual_kopecks: int
```

---

## Question 5: RBAC Resource / OWNER_ONLY Entries

The existing `Resource.PAYROLL` and `Resource.COMPENSATION` are already declared in `app/core/permissions.py` (they appear in the existing `OWNER_ONLY` entries `(VIEW, PAYROLL)` and `(VIEW, COMPENSATION)`). v1.9 adds the write-side pairs.

**New `OWNER_ONLY` entries to add:**

| Action | Resource | Notes |
|---|---|---|
| `(CREATE, PAYROLL)` | | run payroll period |
| `(EDIT, PAYROLL)` | | mark accrual paid |
| `(LIST, PAYROLL)` | | list accruals (owner-only visibility) |
| `(CREATE, COMPENSATION)` | | set comp config |
| `(EDIT, COMPENSATION)` | | update comp config |

`(VIEW, COMPENSATION)` and `(VIEW, PAYROLL)` are already in OWNER_ONLY (pre-existing frontend entries).

Recurring slots and time-off use the existing `SCHEDULE_SLOTS` resource. Time-off creation/cancellation maps to `(CREATE, SCHEDULE_SLOTS)` and `(CANCEL, SCHEDULE_SLOTS)` which are already owner-only in the existing OWNER_ONLY set.

**Mandatory three-way parity update:** any new `(Action, Resource)` pairs added to backend `OWNER_ONLY` must be mirrored byte-for-byte in `apps/admin-web/src/shared/session/can.ts` (OWNER_ONLY array) and `apps/admin-web/src/shared/session/registry.ts`. The existing parity test (`tests/unit/test_rbac_parity.py`) enforces this at CI. The admin-web files are updated in Phase 58 even though no UI ships in v1.9 (backend-only milestone).

---

## Component Boundaries Summary

| Component | Status | Type | Cross-Module Access Mechanism |
|---|---|---|---|
| `app/modules/payroll/` | NEW | Write + read | Raw-SQL reads from `pt_sessions`, `payments`, `pt_packages` (D-54-08) |
| `app/modules/schedule/` | EXTENDED | Write | Adds 2 new tables; new service methods; new ARQ cron |
| `app/modules/reports/` | EXTENDED | Read-only | Adds `fetch_trainer_usage` raw-SQL reader |
| `app/core/audit.py` | EXTENDED | Core | 7 new events pre-registered |
| `app/core/permissions.py` | EXTENDED | Core | ~5 new OWNER_ONLY entries |
| `app/workers/scheduled/generate_recurring_slots.py` | NEW | ARQ cron | Imports `schedule.service` directly |
| `app/main.py` | NO CHANGE | Composition root | No new Protocol slots needed |

**No new Protocol slots needed for v1.9.** All cross-module access is either raw-SQL text() reads or direct module imports in worker files.

---

## Data Flow Diagrams

### Payroll Run Flow

```
POST /api/v1/payroll/run  (owner only)
    |
    v
payroll.service.run_payroll_period(trainer_id, period_start, period_end)
    |
    +-- payroll.repository.fetch_trainer_comp_config(trainer_id)
    |       SELECT trainer_comp_configs WHERE trainer_id = ...
    |
    +-- payroll.repository.fetch_trainer_session_revenue(trainer_id, period)
    |       Raw SQL text(): JOIN pt_sessions + pt_packages + payments
    |
    +-- compute accrual_kopecks (fixed_per_session * count + pct * revenue)
    |
    +-- payroll.repository.insert_accrual(...)
    |
    +-- audit.emit("payroll_accrual_created", resource_type="payroll_accrual", ...)
    |
    +-- session.commit()  -- accrual + audit row atomic
```

### Recurring Slot Expansion Flow

```
ARQ cron: generate_recurring_slots (daily 07:00 MSK)
    |
    +-- SELECT active recurring_slot_templates
    |
    |   FOR EACH template x day in [today+1 .. today+14]:
    |       |
    |       +-- Check: any active trainer_time_off overlaps this window?
    |       |       SELECT WHERE trainer_id=? AND cancelled_at IS NULL
    |       |       AND tstzrange overlaps computed slot window
    |       |
    |       +-- IF overlap: skip (no insert, no audit)
    |       |
    |       +-- INSERT trainer_availability_slots ON CONFLICT DO NOTHING
    |           IF rowcount == 1:
    |               audit.emit("slot_published", ...)
    |
    +-- session.commit()
```

### Time-Off Creation Flow

```
POST /api/v1/trainer-time-off  (owner only)
    |
    v
schedule.service.create_time_off(trainer_id, starts_at, ends_at)
    |
    +-- schedule.repository.count_booked_slots_in_window(trainer_id, window)
    |       SELECT COUNT(*) FROM trainer_availability_slots
    |       WHERE trainer_id=? AND status='booked'
    |       AND tstzrange(start_time, end_time) && tstzrange(starts_at, ends_at)
    |
    +-- IF count > 0: raise TimeOffConflictsWithBookings (409)
    |
    +-- schedule.repository.insert_time_off(...)
    |
    +-- audit.emit("trainer_time_off_created", resource_type="trainer", ...)
    |
    +-- session.commit()
```

---

## Alembic Migrations Required

| Migration # | Content |
|---|---|
| 0041 | CREATE TABLE `trainer_comp_configs` |
| 0042 | CREATE TABLE `payroll_accruals` |
| 0043 | CREATE TABLE `recurring_slot_templates` |
| 0044 | CREATE TABLE `trainer_time_off` |
| 0045 | ALTER TABLE `trainer_availability_slots` DROP NOT NULL on `created_by_user_id`; ADD UNIQUE (trainer_id, start_time) if not already present |
| 0046 | Performance indexes: payroll_accruals (status, period_start) + trainer_time_off partial |

---

## Suggested Phase Build Order

### Phase 58 -- Foundations: RBAC parity + audit pre-registration + comp-config API

**Why first:** INFRA-15 discipline requires all new LOCKED_AUDIT_EVENTS and OWNER_ONLY entries to exist before any callsite. RBAC parity test must be green before any protected endpoints land. Comp config is a prerequisite for payroll calculation.

Deliverables:
- 7 new LOCKED_AUDIT_EVENTS pre-registered in `audit.py`
- New OWNER_ONLY entries in `permissions.py` + admin-web `can.ts`/`registry.ts` parity (3-way parity test green)
- `app/modules/payroll/` scaffold registered in `.importlinter` modules-independent list
- `TrainerCompConfig` model + Alembic 0041
- `GET /payroll/trainer-configs/{trainer_id}` + `PUT /payroll/trainer-configs/{trainer_id}` endpoints
- `trainer_comp_config_set` audit event wired

### Phase 59 -- Payroll Ledger

**Why second:** depends on comp config from Phase 58.

Deliverables:
- `payroll_accruals` model + Alembic 0042
- `payroll/repository.py` cross-module raw-SQL reader (`fetch_trainer_session_revenue`)
- `payroll.service.run_payroll_period` + `mark_accrual_paid`
- `POST /api/v1/payroll/run`, `PATCH /api/v1/payroll/accruals/{id}/paid`, `GET /api/v1/payroll/accruals`
- `payroll_accrual_created` + `payroll_accrual_paid` audit events wired

### Phase 60 -- Recurring Slots + Time-Off

**Why third:** independent of payroll; pure schedule module extension.

Deliverables:
- `recurring_slot_templates` + `trainer_time_off` models + Alembic 0043/0044
- Alembic 0045: `created_by_user_id` nullable on `trainer_availability_slots` + UNIQUE (trainer_id, start_time)
- Template CRUD endpoints (`POST /trainer-slot-templates`, `DELETE /trainer-slot-templates/{id}`, `GET /trainer-slot-templates`)
- `POST /trainer-time-off`, `DELETE /trainer-time-off/{id}`, `GET /trainer-time-off` endpoints
- `schedule.service.create_time_off` with conflict check (409 on booked slots overlap)
- `recurring_slot_template_created/cancelled` + `trainer_time_off_created/cancelled` audit events wired

### Phase 61 -- Recurring Slot ARQ Cron

**Why fourth:** depends on Phase 60 tables and service methods.

Deliverables:
- `app/workers/scheduled/generate_recurring_slots.py` ARQ cron (07:00 MSK)
- Alembic 0046 performance indexes
- `WorkerSettings` cron list extension + structlog summary line convention
- Integration tests: cron skips time-off windows; idempotent on re-run (ON CONFLICT DO NOTHING); `slot_published` only on actual insert

### Phase 62 -- Trainer-Usage Report

**Why fifth:** depends on pt_sessions/payments data (already exists from v1.4) and schedule data from Phase 60/61. Low risk -- read-only addition to the already-built reports module.

Deliverables:
- `reports/repository.py`: `fetch_trainer_usage` raw-SQL reader
- `reports/service.py`: `get_trainer_usage_report` + `trainer_usage_csv_rows`
- `GET /api/v1/reports/trainers` + `GET /api/v1/reports/trainers.csv`
- Reuses existing RBAC guard, date range validation, CSV export infrastructure

### Phase 63 -- OpenAPI Handoff + Milestone Verification

**Why last:** all business surfaces must be stable before regenerating the OpenAPI artifact.

Deliverables:
- `openapi.json` + `schema.d.ts` byte-stable regen with all v1.9 paths
- `_v19Checks` AssertNonNever guards in `schema.contract.test.ts` (`toHaveLength(N)`)
- Operator runbook `.planning/handoff/v1.9-trainers-runbook.md`
- Milestone verification gate

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Payroll ORM Importing pt_sessions or payments ORM

**What people do:** `from app.modules.pt_sessions.models import PtSession` in `payroll/service.py`.

**Why it's wrong:** violates `modules-independent` import-linter contract. Fails CI immediately.

**Do this instead:** raw-SQL `text()` read in `payroll/repository.py` (D-54-08 pattern).

### Anti-Pattern 2: Protocol Slot for Payroll Revenue Read

**What people do:** add a `PayrollRevenueProvider` Protocol slot in `core/dependencies.py` and wire it in `main.py`.

**Why it's wrong:** Protocol slots are for write-callback dependencies. A read-only aggregation does not need the indirection overhead. The v1.8 reports module has proven that raw-SQL reads are the correct pattern for cross-module aggregations.

**Do this instead:** raw-SQL `text()` read in `payroll/repository.py`.

### Anti-Pattern 3: Time-Off Auto-Cancelling Confirmed Bookings

**What people do:** create time-off block and auto-cancel all `status='booked'` slots within the window.

**Why it's wrong:** requires the schedule module to write into the bookings FSM, a cross-module write dependency. The booking FSM is owned by `bookings.service`; calling it from `schedule.service` would require violating import-linter or adding a `BookingCanceller` Protocol slot.

**Do this instead:** 409 conflict response listing affected slot IDs. Owner resolves conflicts manually via existing `/bookings/{id}/cancel` endpoint.

### Anti-Pattern 4: Emitting Audit Events for ON CONFLICT Rows in the Cron

**What people do:** emit `slot_published` for every slot in the template expansion loop, including rows that already existed (ON CONFLICT DO NOTHING).

**Why it's wrong:** creates spurious audit spam on every daily cron run for slots already generated.

**Do this instead:** check `result.rowcount == 1` after each INSERT; only emit audit when a real new insert occurred.

### Anti-Pattern 5: Comp Config Columns on the Trainers Table

**What people do:** add `fixed_per_session_kopecks` and `pct_of_revenue_bps` columns directly onto the `trainers` table.

**Why it's wrong:** mixes financial configuration into a catalog module. Harder to version comp config history. Creates financial coupling in a non-financial module.

**Do this instead:** separate `trainer_comp_configs` table in the `payroll` module, FK'd to `trainers.id`.

### Anti-Pattern 6: Expand-on-Read for Recurring Slots

**What people do:** don't generate real `trainer_availability_slots` rows; instead, compute virtual slots dynamically in the slot-listing endpoint from `recurring_slot_templates`.

**Why it's wrong:** bookings require a real `trainer_availability_slots` row (the booking FSM transitions `status='active' -> 'booked'`). Virtual slots can't be booked. The `resolve_slot_by_id` Protocol slot in `bookings.service` looks up the real table. This would require a parallel virtual-slot system alongside the real one.

**Do this instead:** ARQ cron generate-ahead writes real rows with ON CONFLICT idempotency.

---

## Integration Points Summary

| Cross-Module Boundary | Mechanism | Notes |
|---|---|---|
| `payroll` reads `pt_sessions` | Raw-SQL `text()` in `payroll/repository.py` | Zero new linter ignores |
| `payroll` reads `payments` | Raw-SQL `text()` in `payroll/repository.py` (same query) | Zero new linter ignores |
| `payroll` reads `pt_packages` | Raw-SQL `text()` in `payroll/repository.py` (JOIN bridge) | Zero new linter ignores |
| `reports` reads `pt_sessions`, `bookings`, `trainer_availability_slots`, `payments`, `trainers` | Raw-SQL `text()` in `reports/repository.py` | Extends v1.8 repository |
| `schedule` cron checks `trainer_time_off` | Direct import within schedule module (same module) | No cross-module boundary |
| `schedule.service` resolves trainer | Existing `resolve_trainer_by_id` Protocol slot | No change needed |
| Worker cron -> `schedule.service` | Direct import in `generate_recurring_slots.py` | Same pattern as `expire_memberships.py` |

---

## Sources

- Direct codebase: `apps/backend/app/core/dependencies.py` (all 16 Protocol slots, lines 1-1223)
- Direct codebase: `apps/backend/app/core/permissions.py` (RBAC, OWNER_ONLY, Resource enum)
- Direct codebase: `apps/backend/app/modules/payments/models.py` (Payment ledger schema)
- Direct codebase: `apps/backend/app/modules/reports/repository.py` (D-54-08 raw-SQL pattern)
- Direct codebase: `apps/backend/app/modules/reports/service.py` (D-54-07 read-only discipline)
- Direct codebase: `apps/backend/app/modules/schedule/models.py` (TrainerAvailabilitySlot)
- Direct codebase: `apps/backend/app/modules/pt_sessions/models.py` (PtSession, existing indexes)
- Direct codebase: `apps/backend/app/modules/trainers/models.py` (Trainer catalog model)
- Direct codebase: `apps/backend/app/workers/scheduled/expire_memberships.py` (ARQ cron pattern)
- Direct codebase: `apps/backend/app/main.py` (composition root, Protocol slot registrations)
- Direct codebase: `apps/backend/.importlinter` (all contracts + ignore_imports edges)
- `.planning/PROJECT.md` (v1.9 scope, architectural decisions log, LOCKED_AUDIT_EVENTS history)

---
*Architecture research for: v1.9 Trainers Complete (Sportzal FastAPI modular monolith)*
*Researched: 2026-05-24*
