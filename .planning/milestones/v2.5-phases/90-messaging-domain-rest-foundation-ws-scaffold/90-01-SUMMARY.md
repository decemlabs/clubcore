---
phase: 90-messaging-domain-rest-foundation-ws-scaffold
plan: "01"
subsystem: database
tags: [alembic, sqlalchemy, postgresql, importlinter, audit, messaging]

# Dependency graph
requires:
  - phase: 88-trainer-detail-bio
    provides: "latest migration 0063_seed_trainer_profiles (chain head)"
provides:
  - "message_threads table (0064) with 1:1 client constraint"
  - "messages table (0065) with role CHECK('client'|'staff') + composite index"
  - "app.modules.messaging ORM package with MessageThread + Message models"
  - "app.modules.messaging registered in modules-independent import-linter contract"
  - "Four messaging audit event pairs pre-registered in LOCKED_AUDIT_EVENTS (INFRA-15)"
affects: [90-02, 90-03, 91, 92, 93]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INFRA-15 preemptive module + audit registration before any callsite"
    - "UUIDPkMixin + TimestampMixin ORM base class pattern (from notifications analog)"
    - "CheckConstraint bare-suffix naming (ck_%(table_name)s_%(constraint_name)s template)"
    - "UNIQUE(client_id) for get-or-create ON CONFLICT target"

key-files:
  created:
    - apps/backend/alembic/versions/0064_messaging_threads.py
    - apps/backend/alembic/versions/0065_messaging_messages.py
    - apps/backend/app/modules/messaging/__init__.py
    - apps/backend/app/modules/messaging/models.py
    - apps/backend/tests/messaging/__init__.py
    - apps/backend/tests/messaging/test_models_schema.py
  modified:
    - apps/backend/.importlinter
    - apps/backend/app/core/audit.py

key-decisions:
  - "messaging module package created during Task 1 (not Task 3) — lint-imports requires the module to physically exist for the independence contract to validate"
  - "role column is TEXT + CheckConstraint (not Postgres native ENUM) — matches notifications platform pattern, migration-safe"
  - "ix_messages_thread_sent uses sa.text() for DESC ordering in migration (SQLAlchemy Index does not support descending natively in DDL)"
  - "Only .importlinter change for entire v2.5 milestone — zero ignore_imports edges added"

patterns-established:
  - "TDD RED/GREEN cycle for ORM model metadata tests (pure introspection, no DB connection)"
  - "Preemptive audit event registration in LOCKED_AUDIT_EVENTS before any callsite"
  - "Migration downgrade drops index then table (respects FK dependency order)"

requirements-completed: [MSG-01, MSG-02, MSG-03, MSG-04]

# Metrics
duration: 25min
completed: 2026-06-07
---

# Phase 90 Plan 01: Messaging Domain Foundation Summary

**Alembic migrations 0064/0065 + MessageThread/Message ORM models + import-linter contract + four audit event pairs pre-registered (INFRA-15) — structural foundation with zero service/router code**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-07T09:30:00Z
- **Completed:** 2026-06-07T09:55:00Z
- **Tasks:** 3 (1 chore + 1 feat + 1 TDD feat)
- **Files modified:** 8

## Accomplishments

- message_threads + messages tables created and reversible via Alembic (0064/0065 applied and downgraded cleanly)
- MessageThread + Message ORM models match migrations column-for-column; role constrained to 'client'|'staff' at DB layer (T-90-01 mitigate)
- app.modules.messaging registered in modules-independent contract; only .importlinter change for v2.5 milestone; lint-imports KEPT
- Four messaging audit event pairs pre-registered in LOCKED_AUDIT_EVENTS (INFRA-15 discipline) before any callsite, including Phase 93 bridge events
- mypy --strict + ruff both pass; zero cross-module ORM imports (T-90-02 mitigate)
- 6 schema metadata tests pass (pure introspection, no DB needed)

## Task Commits

Each task was committed atomically:

1. **Task 1: Register module in import-linter + pre-register four audit event pairs** - `be568c72` (chore)
2. **Task 2: Write Alembic migrations 0064 (threads) + 0065 (messages)** - `bb4a46a8` (feat)
3. **Task 3 RED: Failing tests for ORM models** - `e4c7c88b` (test)
4. **Task 3 GREEN: MessageThread + Message ORM models** - `31e20edf` (feat)

## Files Created/Modified

- `apps/backend/.importlinter` — added app.modules.messaging to modules-independent contract (ONE line; only v2.5 milestone change)
- `apps/backend/app/core/audit.py` — appended four messaging audit pairs to LOCKED_AUDIT_EVENTS (v2.5 block)
- `apps/backend/alembic/versions/0064_messaging_threads.py` — message_threads table (id, client_id FK, last_message_at, client_unread_count, UNIQUE(client_id))
- `apps/backend/alembic/versions/0065_messaging_messages.py` — messages table (id, thread_id FK, role CHECK, body, sent_at, read_at, INDEX thread+sent_at)
- `apps/backend/app/modules/messaging/__init__.py` — module docstring package marker
- `apps/backend/app/modules/messaging/models.py` — MessageThread + Message SQLAlchemy ORM models
- `apps/backend/tests/messaging/__init__.py` — empty test package marker
- `apps/backend/tests/messaging/test_models_schema.py` — 6 pure metadata introspection tests

## Decisions Made

- **messaging package created in Task 1 (not Task 3):** lint-imports requires the module to physically exist for the independence contract to validate. Creating __init__.py during the import-linter registration step is a Rule 3 (blocking issue) auto-fix — noted as deviation.
- **TEXT + CheckConstraint for role (not native ENUM):** Matches the notifications/models.py `platform` pattern. Migration-safe: adding values in future phases requires no ALTER TYPE.
- **BARE suffix in CheckConstraint name=:** The SQLAlchemy `ck_%(table_name)s_%(constraint_name)s` NAMING_CONVENTION template adds the prefix automatically. Migration uses FULL names (`ck_messages_role`), ORM uses bare suffix (`role`) — matching the notifications/models.py convention exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created messaging __init__.py during Task 1 instead of Task 3**
- **Found during:** Task 1 (lint-imports verification)
- **Issue:** `uv run lint-imports` failed with "Module 'app.modules.messaging' does not exist" — the independence contract requires the Python package to physically exist to validate the listing
- **Fix:** Created `apps/backend/app/modules/messaging/__init__.py` during Task 1. The Task 3 `<action>` originally wrote the full docstring __init__.py, so the Task 3 action was updated to skip __init__.py creation (already done). The __init__.py content in Task 1 matches the full docstring per the plan's Task 3 spec.
- **Files modified:** apps/backend/app/modules/messaging/__init__.py
- **Verification:** lint-imports KEPT (no violations) after creation
- **Committed in:** be568c72 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking)
**Impact on plan:** Necessary for lint-imports validation. __init__.py content matches plan spec exactly. No scope creep.

## Issues Encountered

None beyond the Rule 3 deviation above.

## User Setup Required

None — no external service configuration required. DB migrations applied automatically.

## Next Phase Readiness

- Plan 02 (REST endpoints) can start from this foundation: message_threads + messages tables exist, ORM models available, audit pairs registered
- Plan 03 (WS scaffold) can extend messaging/router.py built in Plan 02
- Cross-module reads (clients.name) go via raw SQL text() in the repository (D-54-08) — zero ignore_imports edges needed

## Known Stubs

None — this plan is pure infrastructure (migrations + models). No data flows to UI.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced in this plan.

## Self-Check: PASSED

- `apps/backend/alembic/versions/0064_messaging_threads.py` — FOUND
- `apps/backend/alembic/versions/0065_messaging_messages.py` — FOUND
- `apps/backend/app/modules/messaging/__init__.py` — FOUND
- `apps/backend/app/modules/messaging/models.py` — FOUND
- `apps/backend/tests/messaging/__init__.py` — FOUND
- `apps/backend/tests/messaging/test_models_schema.py` — FOUND
- Commit be568c72 — FOUND
- Commit bb4a46a8 — FOUND
- Commit e4c7c88b — FOUND
- Commit 31e20edf — FOUND

---
*Phase: 90-messaging-domain-rest-foundation-ws-scaffold*
*Completed: 2026-06-07*
