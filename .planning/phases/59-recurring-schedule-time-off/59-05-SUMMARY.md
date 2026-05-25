---
phase: 59-recurring-schedule-time-off
plan: "05"
subsystem: backend/workers/schedule
tags: [arq, cron, recurring-slots, dst-safety, idempotency, time-off, audit]
dependency_graph:
  requires:
    - 59-03  # slot_published payload widened (created_by_user_id: UUID | None)
    - 59-04  # recurring templates CRUD + time-off endpoints already on base
  provides:
    - REC-02  # daily idempotent materialization cron at 07:00 MSK
  affects:
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/modules/schedule/repository.py
    - apps/backend/app/workers/__init__.py
tech_stack:
  added:
    - "ARQ cron: generate_recurring_slots (hour=4 UTC, minute=0, unique=True, keep_result=60)"
    - "pg_insert().on_conflict_do_nothing(index_elements=['trainer_id','start_time']).returning()"
    - "ZoneInfo('Europe/Moscow') + .astimezone(UTC) for DST-safe expansion"
  patterns:
    - "caller-owns-txn SVC001 pattern (service helper + cron wrapper)"
    - "Python-side time-off pre-filter to avoid asyncpg parameter-binding pitfall"
    - "slot_published only on RETURNING rows (not ON CONFLICT no-ops)"
key_files:
  created:
    - apps/backend/app/workers/scheduled/generate_recurring_slots.py
    - apps/backend/tests/integration/schedule/test_generate_recurring_slots.py
  modified:
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/modules/schedule/repository.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/workers/test_worker_settings.py
decisions:
  - "Python-side time-off pre-filter (list_active_time_off_for_trainers) instead of SQL NOT EXISTS subquery — asyncpg positional parameter binding ($N) is incompatible with named-param ::type casts in sa.text(); moving the filter to Python eliminates the binding complexity while keeping the guarantee"
  - "Per-row pg_insert() for the bulk INSERT rather than unnest() array approach — the unnest() approach with ::uuid[]::timestamptz[] type-cast params hit asyncpg syntax errors; pg_insert() uses SQLAlchemy's native asyncpg dialect which generates correct $N parameters automatically"
  - "audit.emit queries freshly-inserted slot rows via SELECT ... WHERE id.in_(inserted_ids) to get start_time/end_time for SlotPublishedPayload — cleaner than threading the data through the inserted_ids list"
metrics:
  duration: "590s (~10 min)"
  completed: "2026-05-25"
  tasks_completed: 2
  files_changed: 6
---

# Phase 59 Plan 05: Recurring Slot Materialization Cron Summary

Daily idempotent ARQ cron (07:00 MSK, 04:00 UTC) that materializes concrete `trainer_availability_slots` from active `recurring_slot_templates` over a 56-day rolling horizon, skipping time-off windows and emitting `slot_published` only on real inserts.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | DST-safe generation helper + bulk INSERT repo | 34a89d2b | service.py, repository.py, test_generate_recurring_slots.py |
| 2 | Cron file + WorkerSettings registration + count-bump test | 40df38d7 | generate_recurring_slots.py, workers/__init__.py, test_worker_settings.py |

## What Was Built

### Task 1: DST-safe generation helper + bulk INSERT repo

**`_expand_template_occurrences`** (service.py) — pure module-level function:
- Expands `(day_of_week, local_time_local, end_time_local, from_date, to_date)` to a list of UTC-aware datetime pairs
- Uses `ZoneInfo("Europe/Moscow")` + `.astimezone(UTC)` — never naive timedelta arithmetic (PITFALL 7)
- Moscow has been permanently UTC+3 with no DST since 2014-10-26; ZoneInfo handles this correctly and remains future-safe
- DST golden assertion: `expand(MONDAY, time(10,0), from=2026-03-30)` → `2026-03-30 07:00:00+00:00` ✓

**`_generate_recurring_slots`** (service.py, `# noqa: SVC001 caller-owns-txn`):
- Materializes slots for `now() < slot_start_utc <= now() + RECURRING_SLOT_HORIZON_DAYS`
- Pre-fetches active time-off blocks in Python via `list_active_time_off_for_trainers()`, then filters candidates (PITFALL 9 inverse / T-59-16)
- Calls `bulk_insert_recurring_slots()` which uses `pg_insert().on_conflict_do_nothing(["trainer_id","start_time"]).returning(id)` — idempotent (PITFALL 8 / T-59-13)
- Re-queries inserted rows to emit `slot_published` with full payload — only on real inserts, never on conflict no-ops (ROADMAP SC#2 / T-59-14)
- `created_by_user_id=None` on all emitted audit rows (cron actor — no human author, D-59-05)
- Test override param `now: datetime | None = None` for deterministic integration tests

**Repository additions**:
- `list_active_recurring_templates(session)` — fetches all `is_active=True` templates (no pagination, bounded by O(trainers × days_per_week))
- `list_active_time_off_for_trainers(session, trainer_ids)` — fetches time-off blocks for pre-filter
- `bulk_insert_recurring_slots(session, rows)` — `pg_insert().values([...]).on_conflict_do_nothing().returning(id)`; returns ids actually inserted

### Task 2: Cron file + WorkerSettings registration

**`generate_recurring_slots.py`** (new cron file):
- Cloned from `expire_pt_packages.py` structure verbatim
- Single-module import: `from app.modules.schedule import service as schedule_service`
- Transaction owner: `async with session_factory() as session: count = await schedule_service._generate_recurring_slots(session); await session.commit()`
- Post-commit summary log: `_log.info("generate_recurring_slots_complete", count=count)` — NOT an audit event

**`workers/__init__.py`**:
- Added eager ORM imports for `RecurringSlotTemplate` and `TrainerTimeOff` (REG-29-04 pattern)
- Appended `generate_recurring_slots` to `functions` list (11 → 12)
- Added `cron(generate_recurring_slots, hour=4, minute=0, unique=True, keep_result=60)` to `cron_jobs` (8 → 9)
- 04:00 UTC = 07:00 MSK, non-colliding with existing buckets: 00:30, 03:05-03:35, 20:10

**`test_worker_settings.py`**: bumped `len(cron_jobs) == 8` → 9, `len(functions) == 11` → 12

## Tests

| Test | Status | What It Covers |
|------|--------|----------------|
| `test_expand_dst_golden_monday_10am` | PASS | PITFALL 7 / T-59-15: ZoneInfo UTC+3 gives 07:00 UTC for 10:00 MSK 2026-03-30 |
| `test_expand_no_match_on_wrong_day` | PASS | expand returns [] when no day-of-week match in range |
| `test_generate_recurring_slots_inserts_and_audits` | PASS | PITFALL 8 / T-59-13: first run N>0, second run 0; slot_published emitted for real inserts only; created_by_user_id IS NULL |
| `test_generate_recurring_slots_skips_time_off_window` | PASS | PITFALL 9 inverse / T-59-16: slot inside time-off window absent from inserted set |
| `test_generate_recurring_slots_no_templates_returns_zero` | PASS | Helper returns 0 when no active templates |
| `test_worker_settings_cron_resolves_to_registered_function` | PASS | cron_jobs == 9 entries |
| `test_worker_settings_functions_registered` | PASS | functions == 12 entries |
| `test_on_startup_cron_resolution_invariant_passes_at_baseline` | PASS | on_startup cron-name ⊆ function-names invariant holds |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg incompatibility with sa.text() named params + ::type casts**
- **Found during:** Task 1 implementation / test run
- **Issue:** The initial `bulk_insert_recurring_slots` implementation used `sa.text()` with `unnest(:trainer_ids::uuid[], ...)` — asyncpg uses $N positional parameter binding and raises `PostgresSyntaxError: syntax error at or near ":"` when named params appear before `::type` casts in raw SQL
- **Fix:** Replaced the `sa.text()` unnest approach with SQLAlchemy's `pg_insert().values([...]).on_conflict_do_nothing().returning()` which uses the asyncpg dialect's native parameter generation ($N). Moved the time-off overlap filter to a Python-side pre-fetch (`list_active_time_off_for_trainers`) to avoid the complex NOT EXISTS subquery binding issue
- **Files modified:** `app/modules/schedule/repository.py` (complete redesign of `bulk_insert_recurring_slots`), `app/modules/schedule/service.py` (added `_overlaps_any_time_off` inline + pre-fetch call)
- **Commit:** 34a89d2b (included in Task 1 commit)

## Lint/Type Status

- `uv run ruff check` on all new/modified files: clean (1 pre-existing SIM102 in existing `create_time_off` code, 3 pre-existing `# noqa: TABLE_REF` warnings — all out of scope)
- `uv run mypy app/modules/schedule/service.py app/modules/schedule/repository.py`: clean
- `uv run mypy app/workers/scheduled/generate_recurring_slots.py app/workers/__init__.py`: clean (3 pre-existing errors in unrelated modules)
- `uv run lint-imports`: Contracts: 3 kept, 0 broken. Single-module import rule satisfied (`generate_recurring_slots.py` imports `app.modules.schedule` only)

## Known Stubs

None — all materialization logic is fully wired.

## Threat Flags

None — all new surface is within the cron actor trust boundary documented in the plan's threat model (T-59-13 through T-59-16). No new network endpoints, auth paths, or file access patterns introduced.

## Self-Check

### Files Exist
- `apps/backend/app/workers/scheduled/generate_recurring_slots.py` ✓
- `apps/backend/app/modules/schedule/service.py` (modified, `_generate_recurring_slots` present) ✓
- `apps/backend/tests/integration/schedule/test_generate_recurring_slots.py` ✓

### Commits Exist
- 34a89d2b (Task 1) ✓
- 40df38d7 (Task 2) ✓

## Self-Check: PASSED
