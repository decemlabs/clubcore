# Phase 59: Recurring Schedule + Time-Off - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults grounded in REQUIREMENTS REC-01..04, STATE.md D-TIMEOFF-CONFLICT, and v1.9 research; review before planning)

<domain>
## Phase Boundary

The **recurring-schedule + time-off** layer for v1.9. Four requirements
(REC-01..04) extend the EXISTING `app/modules/schedule/` module (Phase
37/38 slot machinery) — they are NOT a new module. The phase adds:

1. **Recurring availability patterns (REC-01)** — owner defines a weekly
   recurrence per trainer (`day_of_week` 0..6, `start_time`/`end_time`,
   `valid_from`, nullable `valid_until`, `is_active`). New table with
   `UNIQUE (trainer_id, day_of_week, start_time, valid_from)`.

2. **ARQ daily materialization cron (REC-02)** — a new
   `app/workers/scheduled/generate_recurring_slots.py` cron materializes
   concrete `trainer_availability_slots` rows for a rolling
   `RECURRING_SLOT_HORIZON_DAYS` (env, default **56**) window ahead.
   Idempotent (`unique=True` cron + `INSERT … ON CONFLICT DO NOTHING`),
   skips windows covered by active time-off blocks.

3. **Time-off blocks + conflict guard (REC-03)** — owner creates/deletes a
   trainer time-off block (`block_start`/`block_end`, `reason`). Creation:
   - **cancels** overlapping `active` slots (`cancel_reason='trainer_time_off'`);
   - on overlap with a `booked` slot → **409** listing the conflicting
     bookings;
   - `?force=true` **cascades** booking-FSM cancellation + a client DM via
     the existing notification machinery, then proceeds.

4. **List views (REC-04)** — owner/reception both read the list of a
   trainer's recurring patterns and time-off blocks.

**In scope (REC-01..04):**
- 1–3 new Alembic migrations (head is `0041`; new revisions start `0042`):
  `recurring_slot_templates` table, `trainer_time_off` table, and an ALTER on
  `trainer_availability_slots` (nullable `created_by_user_id` + UNIQUE
  `(trainer_id, start_time)` for cron idempotency). Planner decides whether to
  split or combine.
- Schema, schemas, repository, service, router additions inside
  `app/modules/schedule/` (NOT a new module).
- 1 new ARQ cron file `app/workers/scheduled/generate_recurring_slots.py`
  registered in `app/workers/__init__.py` `cron_jobs`.
- New env var `RECURRING_SLOT_HORIZON_DAYS: int = 56` in `app/core/config.py`.
- 4 new `LOCKED_AUDIT_EVENTS` pre-registered before any callsite (INFRA-15).
- Endpoints: recurring-pattern CRUD (create / list / deactivate-or-delete),
  time-off create / delete / list. Exact paths at plan time.
- Integration tests: DST/MSK expansion golden test (PITFALL 7), horizon +
  idempotency (PITFALL 8), time-off-skips-generation, active-slot
  cancellation on time-off, 409-on-booked + `?force=true` cascade + DM,
  REC-04 list visibility for both roles.

**Out of scope (later phases / explicit anti-features):**
- Trainer-usage report incl. revenue attribution + CSV (RPT-01..04 → Phase 60).
- OpenAPI handoff / `schema.d.ts` regen (HND-01 → Phase 61).
- `apps/admin-web` UI for schedule (frozen in v1.9). **No admin-web edits are
  expected this phase** — RBAC reuses existing `SCHEDULE_SLOTS` pairs (see
  D-59-08), so the three-way parity test does not change.
- RRULE/EXDATE calendar semantics, per-date exceptions, iCal sync, recurring
  client-trainer bookings, trainer self-service portal (research anti-features).
- Expand-on-read recurring slots (materialize-ahead is the locked strategy).
- Retroactive cancellation of already-`booked` slots that fall inside a
  newly created time-off window — the cron only blocks FORWARD generation;
  existing booked slots are handled exclusively through the REC-03 409/force
  path at time-off-creation time.

</domain>

<decisions>
## Implementation Decisions

> **REQUIREMENTS REC-01..04 + STATE.md `D-TIMEOFF-CONFLICT` are authoritative
> and supersede the older v1.9 research where they conflict.** The research
> (`.planning/research/ARCHITECTURE.md` Q2) described a "block + manual cancel"
> time-off model and a 14/28-day horizon; the LOCKED requirement evolved to
> auto-cancel-active + 409-then-`force=true`-cascade with a 56-day horizon.
> **The requirement wins.** The research remains the source of truth for
> module placement, DST expansion, idempotency, and audit/RBAC structure.

### Module & schema placement (D-59-01)
- **D-59-01:** Recurring patterns + time-off live in the EXISTING
  `app/modules/schedule/` module (research ARCHITECTURE Q2 — both are schedule
  concerns referencing `trainer_availability_slots` + `trainers`; a new module
  would force cross-module imports or Protocol slots for what is schedule
  data). NO new module, NO new `.importlinter` entry, zero new
  `ignore_imports` edges. `schedule.service` already owns slot creation,
  overlap detection, `cancel_slot`'s booked→cancelled cascade, and the
  `restore_slot_to_active` Protocol slot — all reused here.

### Recurring pattern table (D-59-02)
- **D-59-02:** New table (recommended name `recurring_slot_templates`;
  planner may rename — Claude's discretion) with the REC-01 columns:
  `trainer_id` FK, `day_of_week SMALLINT CHECK 0..6`, `start_time TIME`,
  `end_time TIME CHECK end_time > start_time`, `valid_from DATE NOT NULL`,
  `valid_until DATE NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`.
  **`UNIQUE (trainer_id, day_of_week, start_time, valid_from)`** is the REC-01
  verbatim contract. FK to `trainers.id` `ON DELETE RESTRICT` (mirrors
  `trainer_availability_slots`). Deactivation is an `is_active` flip (and/or
  hard delete — planner picks; REC-04 implies patterns stay listable, so
  prefer the `is_active=false` flip over hard delete for audit continuity).

### Cron materialization, horizon & idempotency (D-59-03..05)
- **D-59-03:** Generation strategy is **materialize-ahead** (NOT expand-on-read).
  A new `app/workers/scheduled/generate_recurring_slots.py` ARQ cron, owned by
  the schedule module (imports `schedule.service` only — single-module-import
  worker rule, Phase 7 D-06 / Phase 18 D-09). The service helper does the
  bulk `INSERT … ON CONFLICT DO NOTHING` and does NOT commit
  (`# noqa: SVC001 caller-owns-txn`); the cron function owns the
  `session.commit()` (exact pattern of `expire_pt_packages.py`).
- **D-59-04:** Horizon is env-driven: `RECURRING_SLOT_HORIZON_DAYS: int = 56`
  in `app/core/config.py` (REC-02 verbatim default; overrides research's
  14/28). Generation window:
  `now() < slot_start_utc <= now() + (HORIZON_DAYS days)`. DST/MSK expansion
  per PITFALL 7 — expand `(day_of_week, start_time_local)` through
  `zoneinfo.ZoneInfo('Europe/Moscow')` then `.astimezone(timezone.utc)`;
  NEVER add raw `timedelta` to a naive datetime, NEVER store
  `TIMESTAMP WITHOUT TIME ZONE`. Golden test mandatory:
  `expand(MONDAY, 10:00, from=2026-03-30) == 2026-03-30 07:00:00+00:00`.
- **D-59-05:** Idempotency requires an Alembic ALTER on
  `trainer_availability_slots`: (a) make `created_by_user_id` **nullable**
  (cron-generated slots have no human author — current FK is NOT NULL
  RESTRICT), and (b) add **`UNIQUE (trainer_id, start_time)`** so
  `ON CONFLICT (trainer_id, start_time) DO NOTHING` is a real no-op on
  repeat ticks (PITFALL 8). Cron: `unique=True, keep_result=60`. Generation
  query MUST `AND NOT EXISTS` against active `trainer_time_off` windows so
  blocked dates are skipped (PITFALL 9 inverse). Provenance column linking a
  generated slot back to its template (e.g. nullable `recurring_template_id`
  FK) is **Claude's discretion** — useful for audit but not required by REC.

### Time-off conflict semantics (D-59-06) — LOCKED, supersedes research
- **D-59-06:** New `trainer_time_off` table (`trainer_id` FK,
  `block_start`/`block_end` TIMESTAMPTZ, `reason TEXT`). `create_time_off`
  service, in a single UoW (SVC001 — service owns the explicit commit):
  1. Query confirmed bookings overlapping `[block_start, block_end]` for the
     trainer (JOIN `trainer_availability_slots` ON `booked` status). If any
     exist AND `force` is falsy → raise typed conflict → **409** with the
     conflicting booking IDs (and slot IDs) in the response body.
     `error_code` is snake_case (project convention).
  2. If `?force=true`: cascade-cancel each conflicting booking through the
     booking FSM (`confirmed → cancelled`, `cancel_reason='trainer_time_off'`),
     emit `booking_cancelled` per booking, and fire the client DM via the
     existing `_dispatch_booking_dm` / notification machinery
     (`bookings.service` pattern). This is the EXACT cross-module raw-SQL
     UPDATE-on-bookings + audit + DM discipline already implemented in
     `schedule.service.cancel_slot`'s booked→cancelled cascade (D-38-11) —
     **reuse that pattern**, do NOT add a `from app.modules.bookings import`.
  3. Cancel overlapping **`active`** (un-booked) slots:
     `cancel_reason='trainer_time_off'` (reuse the existing `slot_cancelled`
     audit + the `active → cancelled` transition; no new audit event needed
     for this leg).
  4. INSERT the time-off row, emit `trainer_time_off_created`, commit.
  - Time-off deletion (REC-03 "создаёт/удаляет"): removes the block; emits
    `trainer_time_off_cancelled`. Deleting a block does NOT retroactively
    re-create previously cancelled slots (forward-only; the next cron tick
    re-materializes future slots for now-unblocked windows).

### RBAC (D-59-07..08)
- **D-59-07:** REC-04 list endpoints are visible to **both owner and
  reception** — they use the reception-RETAINED `(VIEW, SCHEDULE_SLOTS)` /
  `(LIST, SCHEDULE_SLOTS)` pairs (permissions.py:103 — these are explicitly
  NOT in OWNER_ONLY). Do NOT gate the list endpoints owner-only.
- **D-59-08:** All WRITE operations (pattern create/deactivate, time-off
  create/delete, force-cascade) reuse the EXISTING owner-only
  `SCHEDULE_SLOTS` pairs already in `OWNER_ONLY`
  (`(CREATE|EDIT|DELETE|CANCEL, SCHEDULE_SLOTS)`, permissions.py:114-117).
  **No new `Resource`, no new `OWNER_ONLY` pairs, no `can.ts`/`registry.ts`
  edits.** Three-way RBAC parity test is unchanged (admin-web stays frozen).

### Audit pre-registration (D-59-09)
- **D-59-09:** Pre-register exactly **4 new `LOCKED_AUDIT_EVENTS`** in
  `app/core/audit.py` BEFORE any `audit.emit(...)` callsite (INFRA-15):
  - `("recurring_slot_template_created", "schedule_slot")`
  - `("recurring_slot_template_cancelled", "schedule_slot")`
  - `("trainer_time_off_created", "trainer")`
  - `("trainer_time_off_cancelled", "trainer")`
  (subject-kind strings per research ARCHITECTURE audit table; planner verifies
  against current `audit_payloads.py` payload conventions.) The materialization
  cron does **NOT** emit a per-slot audit event (high volume) — it emits a
  structlog ops-summary line `generate_recurring_slots_complete count=N` AFTER
  commit, the locked summary-event shape for all scheduled jobs. Time-off's
  active-slot cancellation reuses the EXISTING `slot_cancelled` event; the
  force-cascade reuses the EXISTING `booking_cancelled` event. No new events
  for those legs.

### Claude's Discretion
- Exact table names (`recurring_slot_templates` vs `recurring_slot_patterns`),
  column order, index list, and constraint names in the Alembic migration(s).
- Whether the schema migration is 1 combined revision or split across
  `0042`/`0043`/`0044` (head is `0041`).
- Endpoint path scheme and whether they mount on the existing
  `schedule_router` or a sibling router (recommended: extend `schedule_router`;
  research suggested `/api/v1/trainer-time-off` + recurring-template paths).
- Whether to add a nullable `recurring_template_id` provenance FK on generated
  slots (D-59-05).
- Pattern deactivation as `is_active=false` flip vs hard DELETE (recommended:
  flip, for REC-04 listability + audit continuity).
- Exact cron clock time (recommended `hour=4, minute=0` UTC = 07:00 MSK, the
  research-specified slot AFTER the 06:35 reminder cron and before any
  evening tick — but it sits in the existing cron-ordering comment block;
  planner picks a non-colliding minute).
- Test file layout and the deterministic golden timestamps used.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (source of truth on scope — these WIN over research)
- `.planning/REQUIREMENTS.md` §"REC-01..04" — verbatim contract: pattern
  columns + `UNIQUE (trainer_id, day_of_week, start_time, valid_from)`;
  `RECURRING_SLOT_HORIZON_DAYS` default 56; idempotent cron; the time-off
  active-cancel / 409-on-booked / `?force=true` cascade + DM behavior.
- `.planning/ROADMAP.md` §"Phase 59: Recurring Schedule + Time-Off" — goal
  line ("Recurring slot patterns + ARQ cron generation + time-off blocks +
  conflict guard (REC-01..04)").
- `.planning/STATE.md` §"D-TIMEOFF-CONFLICT" — the locked decision that
  supersedes the research's manual-cancel model.
- `.planning/PROJECT.md` — v1.9 milestone goal (Trainers Complete; admin-web
  frozen; schedule EXTENDED not replaced).

### v1.9 research (locked for placement/DST/idempotency/audit — NOT for the
### time-off behavior, which the requirement overrides)
- `.planning/research/ARCHITECTURE.md` §"Question 2: Recurring Slots and
  Time-Off Blocks" (L188-300) — module placement (extend schedule),
  `recurring_slot_templates` + `trainer_time_off` schema sketch, expansion
  strategy, audit-event table (L374-377), RBAC reuse of `SCHEDULE_SLOTS`
  (L419), new-files table (L434). **NOTE:** the "block + manual cancel"
  time-off model here is SUPERSEDED by REC-03 / D-TIMEOFF-CONFLICT.
- `.planning/research/PITFALLS.md` §"Pitfall 7" (DST expansion — Europe/Moscow
  `zoneinfo`, golden test), §"Pitfall 8" (horizon limit + `ON CONFLICT DO
  NOTHING` idempotency), §"Pitfall 9" (time-off vs confirmed booking; cron
  `NOT EXISTS` skip of time-off windows). These three are LOCKED inputs to
  D-59-04..06.
- `.planning/research/SUMMARY.md` §"REC-01..04" + §"Phase 60/61" notes —
  context only; the actual ROADMAP folds REC-01..04 into ONE phase (59), not
  the research's split 60/61. Follow the ROADMAP.
- `.planning/research/STACK.md` — confirms zero new deps (`zoneinfo` stdlib
  + existing ARQ).

### Backend code under direct edit / extension (READ before planning)
- `apps/backend/app/modules/schedule/models.py` — `TrainerAvailabilitySlot`
  (status FSM, CHECK constraints, the two btree indexes). The cron-idempotency
  ALTER (nullable `created_by_user_id` + `UNIQUE (trainer_id, start_time)`)
  lands against this table. New recurring/time-off models added alongside.
- `apps/backend/app/modules/schedule/constants.py` — `SLOT_STATUS_TRANSITIONS`,
  `SLOT_BUFFER_MINUTES`. New recurring/time-off constants land here.
- `apps/backend/app/modules/schedule/service.py` — `publish_slot` (overlap +
  buffer check), `cancel_slot` (L390+; the `active→cancelled` path AND the
  `booked→cancelled` cross-module raw-SQL cascade per D-38-11). The time-off
  conflict logic (D-59-06) REUSES the cancel_slot cascade pattern verbatim.
- `apps/backend/app/modules/schedule/router.py`, `repository.py`, `schemas.py`
  — extend with recurring/time-off endpoints, queries, DTOs.
- `apps/backend/app/workers/__init__.py` §155-260 — `WorkerSettings.cron_jobs`
  list + `on_startup` cron-name invariant. New `generate_recurring_slots`
  registration goes here (`unique=True, keep_result=60`).
- `apps/backend/app/workers/scheduled/expire_pt_packages.py` — EXACT template
  for the new cron file (caller-owns-txn, service helper `# noqa: SVC001`,
  post-commit `_complete count=N` structlog summary).
- `apps/backend/app/workers/scheduled/__init__.py` — single-module-import
  worker discipline (the cron may import `schedule.service` ONLY).
- `apps/backend/app/core/config.py` — env-var field pattern; new
  `recurring_slot_horizon_days: int = 56`.
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset; 4 new
  events pre-registered (D-59-09). `app/core/audit_payloads.py` — payload
  dataclass conventions for the new events.
- `apps/backend/app/core/permissions.py` §36/54 (`SCHEDULE_SLOTS` resource),
  §103 (reception-retained VIEW/LIST), §114-117 (owner-only write pairs) —
  confirms NO new RBAC needed (D-59-07/08).
- `apps/backend/alembic/versions/0041_payroll_foundations.py` (current head) +
  2-3 recent revisions — Alembic style (naming convention, FK ON DELETE,
  CHECK literal names matching `__table_args__`).

### Backend code referenced read-only (do NOT edit, must understand)
- `apps/backend/app/modules/bookings/service.py` §347 `_dispatch_booking_dm`,
  §1311+ owner cancel path (`booking_cancelled` 4-key payload, eager-load
  requirement before DM). The `?force=true` cascade (D-59-06) drives client
  DMs through this machinery — understand the eager-load + fire-and-forget
  discipline; do NOT import bookings into schedule (raw-SQL cross-module
  UPDATE per D-38-11 is the sanctioned path).

### Test infrastructure
- `apps/backend/tests/conftest.py` — `authed_client_owner`,
  `authed_client_reception`, SAVEPOINT isolation, factory builders. New
  recurring-template + time-off factories land in/near here.
- `apps/backend/tests/integration/` (schedule dir) — existing slot test
  shape; new recurring/time-off integration tests mirror it.
- `apps/backend/tests/unit/workers/test_worker_settings.py` — the cron-name
  invariant test; the new cron must register without breaking it.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`schedule.service.cancel_slot` booked→cancelled cascade (D-38-11)** —
  cross-module raw-`sa.text()` UPDATE on `bookings` (`WHERE status='confirmed'`
  → `RETURNING id`, 0-row = InternalConsistencyError) + `slot_cancelled` +
  `booking_cancelled` audit in one UoW. EXACT template for the REC-03
  `?force=true` cascade.
- **`expire_pt_packages.py` ARQ cron** — caller-owns-txn pattern, service
  helper `# noqa: SVC001`, post-commit `<job>_complete count=N` structlog
  summary, `unique=True, keep_result=60`. Template for
  `generate_recurring_slots.py`.
- **`TrainerAvailabilitySlot` model + its partial/btree indexes** — the
  materialization target; only an ALTER (nullable author + UNIQUE) is needed.
- **`SLOT_STATUS_TRANSITIONS` FSM + `_assert_can_transition`** — `active →
  cancelled` is already legal; time-off's active-slot cancel reuses it.
- **`_dispatch_booking_dm` + notification machinery** — client DM on
  force-cascade, no new notification code.
- **DB-wins-the-race `INSERT … ON CONFLICT DO NOTHING`** — used on visits,
  memberships, payments, `membership_notifications` cron; REC-02 mirrors it.
- **Existing owner-only `SCHEDULE_SLOTS` RBAC pairs** — write ops need no new
  permission tuples; reception-retained VIEW/LIST covers REC-04.

### Established Patterns
- **Materialize-ahead + bounded horizon + idempotent cron** (PITFALL 8) —
  never expand-on-read; `now() < start <= now()+HORIZON`.
- **Europe/Moscow `zoneinfo` expansion** (PITFALL 7) — `gym_date STORED` +
  cron `hour=UTC` precedent; never naive `timedelta`.
- **Cross-module write via raw `sa.text()` (D-38-11 / D-34-04a)** — schedule
  touches `bookings` only through predicate-gated raw SQL; zero
  `ignore_imports` edges.
- **SVC001 commit-gate** — service helpers never commit; the orchestrator
  (endpoint handler or cron function) owns the single `session.commit()`.
- **Single-module-import worker rule** — a scheduled file imports exactly one
  owning module's service.
- **`{items, total, page, pageSize}` pagination envelope** — REC-04 list
  endpoints mirror it.
- **snake_case `error_code` in 4xx** — the REC-03 booked-conflict 409 uses
  one (e.g. `time_off_booked_conflict`; planner finalizes wording).

### Integration Points
- `app/workers/__init__.py` `cron_jobs` — register `generate_recurring_slots`.
- `app/modules/schedule/router.py` — new recurring + time-off endpoints
  mounted under `/api/v1/` (extend existing `schedule_router`).
- `app/core/config.py` — new `recurring_slot_horizon_days` env field.
- `app/core/audit.py` — 4 new `LOCKED_AUDIT_EVENTS` tuples.
- `bookings` table (raw SQL only) — force-cascade UPDATE target.

</code_context>

<specifics>
## Specific Ideas

- **REQUIREMENT-vs-RESEARCH conflict (must be respected by planner):** the
  v1.9 research's time-off section says "block with 409 + owner manually
  cancels, no auto-cancel." REC-03 + `D-TIMEOFF-CONFLICT` EVOLVED past that:
  active-slot overlaps ARE auto-cancelled (`cancel_reason='trainer_time_off'`),
  and booked overlaps return 409 UNLESS `?force=true`, which DOES cascade the
  booking FSM + DM. **Implement the requirement, not the research narrative.**
- The DST golden test (PITFALL 7) is a phase ACCEPTANCE criterion, mirroring
  Phase 57's VER-02 MSK-offset golden test:
  `expand(MONDAY, 10:00, from=2026-03-30) == 2026-03-30 07:00:00+00:00`.
- **Verify at plan time** that `trainer_availability_slots.created_by_user_id`
  can be safely made nullable (no existing NOT-NULL-dependent code path /
  query asserts it). Cron-generated slots will carry NULL author.
- The cron MUST add `AND NOT EXISTS (… active trainer_time_off overlap …)` to
  its generation predicate — generating a slot inside a time-off window is the
  inverse failure of PITFALL 9.
- Time-off deletion is forward-only: it does not resurrect previously
  cancelled slots; the next cron tick re-materializes future windows.

</specifics>

<deferred>
## Deferred Ideas

- **Retroactive un-cancel on time-off deletion** — explicitly NOT done;
  forward-only re-materialization via the next cron tick.
- **RRULE/EXDATE per-date exceptions, iCal/`.ics` sync, recurring
  client-trainer bookings** — research anti-features; future milestone.
- **Trainer self-service portal / "my schedule"** — admin-web frozen in v1.9.
- **Configurable per-trainer/per-zal slot buffer** — already deferred from
  v1.5 (`SLOM_BUFFER_MINUTES` hardcoded 10); not reopened here.
- **Per-slot audit event for cron-generated slots** — intentionally omitted
  (volume); structlog summary only. A future observability milestone could
  add a `recurring_slots_generated` aggregate event if needed.
- **Trainer-usage report consuming these tables** — Phase 60 (RPT-01..04).

None of the above are scope creep into Phase 59.

</deferred>

---

*Phase: 59-recurring-schedule-time-off*
*Context gathered: 2026-05-25*
