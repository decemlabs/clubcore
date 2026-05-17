---
phase: 37-foundations-bedrock
plan: 01
subsystem: audit
tags: [audit, pydantic-v2, frozenset, taxonomy, bedrock, schedule, booking]

# Dependency graph
requires:
  - phase: 30-bedrock
    provides: LOCKED_AUDIT_EVENTS frozenset + AUDIT_PAYLOAD_SCHEMAS registry + Pydantic v2 extra='forbid' discipline (INFRA-17 / INFRA-23 / D-30-03)
  - phase: 34-pt-sessions
    provides: PtSessionRecordedPayload 8-field shape — extended additively here with optional booking_id
provides:
  - LOCKED_AUDIT_EVENTS extended 53 -> 58 with 5 v1.5 (event, resource_type) tuples
  - 5 new Pydantic v2 payload schemas (SlotPublished, SlotCancelled, BookingCreated, BookingCancelled, BookingNoShow) with extra='forbid'
  - PtSessionRecordedPayload.booking_id optional UUID field (C-06 completion-via-existing-event)
  - 5 new entries in AUDIT_PAYLOAD_SCHEMAS registry
  - tests/unit/test_audit_payloads.py (NEW; 14 tests) — covers schemas + extension + registry
  - tests/unit/test_audit_taxonomy.py count + v1.5 membership assertions
affects: [37-02-rbac-extension, 37-03-fsm-constants, 37-04-protocol-slots-and-wiring, 38-schedule-bookings, 39-notifications-cron, 40-telegram-book]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "v1.5 audit-event additive extension (5 new (event, resource_type) pairs in a labelled Phase 37 section block — mirrors v1.4 INFRA-17 pre-registration precedent)"
    - "Pydantic v2 additive-field extension on an existing payload schema with default None for back-compat (PtSessionRecordedPayload.booking_id — mirrors Phase 33 D-33-15 PtPackageSoldPayload extension precedent)"
    - "UUID typing in audit payload schemas: uuid.UUID (not str); P13/REG-36-03 enforcement happens at the EMIT callsite using str(uuid), NOT at the schema field type — overrides CONTEXT.md D-37-09 per PATTERNS.md §1 UUID-divergence note"
    - "resource_type discipline: snake_case audit-side identifier ('schedule_slot', 'booking') — distinct from RBAC Resource enum kebab-on-wire values planned for plan 37-02"

key-files:
  created:
    - apps/backend/tests/unit/test_audit_payloads.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py

key-decisions:
  - "UUID fields in v1.5 payload schemas typed as uuid.UUID (mirrors v1.4 precedent in PtSessionRecordedPayload / PtPackagePlanCreatedPayload), NOT str — overrides CONTEXT.md D-37-09. P13/REG-36-03 lesson is honoured at the emit callsite via str(uuid)."
  - "C-06 confirmed: booking_completed is NOT a separate audit event — completion of a booking is signalled by emitting the EXISTING pt_session_recorded event with a non-None booking_id."
  - "Resource_type values for audit pairs use snake_case (schedule_slot, booking) — distinct from RBAC Resource.SCHEDULE_SLOTS = 'schedule-slots' kebab-on-wire values (RBAC mirror lands in plan 37-02)."
  - "PtSessionRecordedPayload extension is additive with default None — every v1.4 emit callsite in pt_sessions/service.py keeps validating without modification."

patterns-established:
  - "Phase 37 (v1.5) audit-event pre-registration block: append-only with a labelled section comment '# v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-24 / C-06)' BEFORE the frozenset closing brace; mirrors the Phase 30 v1.4 block."
  - "Pydantic v2 audit payload schemas inherit plain BaseModel (NOT BackendSchemaBase) with model_config = ConfigDict(extra='forbid'); UUIDs typed as uuid.UUID; ISO-8601 datetime strings as plain str fields (start_time, end_time, no_show_at)."
  - "Test file shape for v1.5 payload schemas: per-schema round_trip + rejects_extra_keys pair + back-compat tests for additive extensions + registry-mapping `is`-identity test."

requirements-completed: [INFRA-24, INFRA-25]

# Metrics
duration: ~16min
completed: 2026-05-17
---

# Phase 37 Plan 01: Audit Taxonomy v1.5 Lock Summary

**LOCKED_AUDIT_EVENTS frozenset extended 53 -> 58 with 5 v1.5 (event, resource_type) tuples; 5 new Pydantic v2 payload schemas added with extra='forbid'; PtSessionRecordedPayload extended additively with optional booking_id UUID for C-06 completion-via-existing-event semantics.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-05-17T12:43:00Z (approx — see commit timestamps)
- **Completed:** 2026-05-17T12:59:02Z
- **Tasks:** 2
- **Files modified:** 3 (+1 created)

## Accomplishments

- **LOCKED_AUDIT_EVENTS 53 -> 58.** Five new (event, resource_type) tuples added in a labelled `# v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-24 / C-06)` section block: `(slot_published, schedule_slot)`, `(slot_cancelled, schedule_slot)`, `(booking_created, booking)`, `(booking_cancelled, booking)`, `(booking_no_show, booking)`. resource_type uses snake_case (audit-side discipline; the RBAC Resource enum kebab values land in plan 37-02).
- **5 new Pydantic v2 payload schemas** with `extra='forbid'`: `SlotPublishedPayload`, `SlotCancelledPayload` (with the SLOT-09 `had_booking` discriminator), `BookingCreatedPayload` (with the `pt_package_id` decrement anchor), `BookingCancelledPayload`, `BookingNoShowPayload`.
- **PtSessionRecordedPayload additive extension.** Appended `booking_id: UUID | None = None` with default `None` so every existing v1.4 emit callsite in `apps/backend/app/modules/pt_sessions/service.py:record_pt_session` continues to validate. C-06 / D-37-05: completion of a booking is now signalled by the EXISTING `pt_session_recorded` event carrying the parent booking reference — there is NO separate `booking_completed` event.
- **AUDIT_PAYLOAD_SCHEMAS registry** grew by 5 entries under a `# v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-25)` section block.
- **Tests.** `tests/unit/test_audit_taxonomy.py` count assertion bumped 53 -> 58 with refreshed breakdown comment and a new `test_locked_audit_events_includes_v15_pairs` membership test mirroring the v1.3 precedent. NEW `tests/unit/test_audit_payloads.py` (14 tests) covers per-schema round-trip, per-schema extra-key rejection, PtSessionRecordedPayload booking_id back-compat (missing + present + extra-rejection), and AUDIT_PAYLOAD_SCHEMAS registry mapping with `is`-identity comparisons.
- **Quality gates.** `ruff check` + `mypy --strict` green on every touched file; full `pytest tests/unit` sweep: 505 passed / 1 skipped — zero regression in adjacent tests.

## Task Commits

Each task was committed atomically (TDD RED/GREEN per task):

1. **Task 1 RED — failing v1.5 audit taxonomy count + membership tests** — `150d922` (test)
2. **Task 1 GREEN — extend LOCKED_AUDIT_EVENTS 53 -> 58 with v1.5 pairs** — `763b1ed` (feat)
3. **Task 2 RED — failing v1.5 audit payload schema tests** — `d09ca91` (test)
4. **Task 2 GREEN — add 5 v1.5 schemas + PtSessionRecordedPayload.booking_id + registry entries** — `9af8738` (feat)

_TDD cycle followed verbatim per task: test → fail → implement → pass. No REFACTOR commits needed — the implementation matched the test contract on first GREEN._

## Files Created/Modified

- `apps/backend/app/core/audit.py` (modified) — extended `LOCKED_AUDIT_EVENTS` frozenset with 5 new v1.5 tuples in a labelled Phase 37 section; module docstring updated with v1.5 paragraph and the `PtSessionRecordedPayload.booking_id` extension note.
- `apps/backend/app/core/audit_payloads.py` (modified) — added 5 new Pydantic v2 BaseModel classes (SlotPublishedPayload, SlotCancelledPayload, BookingCreatedPayload, BookingCancelledPayload, BookingNoShowPayload); extended `PtSessionRecordedPayload` with `booking_id: UUID | None = None`; appended 5 entries to `AUDIT_PAYLOAD_SCHEMAS` dict.
- `apps/backend/tests/unit/test_audit_taxonomy.py` (modified) — bumped count assert from 53 to 58 with refreshed breakdown comment; added `test_locked_audit_events_includes_v15_pairs` membership test; docstring updated with v1.5 paragraph and C-06 note.
- `apps/backend/tests/unit/test_audit_payloads.py` (CREATED) — 14 tests covering the 5 new schemas (round-trip + extra-key rejection), PtSessionRecordedPayload.booking_id back-compat (missing + present + extra-rejection), and AUDIT_PAYLOAD_SCHEMAS registry mapping.

## Decisions Made

- **UUID typing in v1.5 payload schemas: `uuid.UUID` (not `str`)** — overrides CONTEXT.md D-37-09 per PATTERNS.md §1 UUID-divergence note. The existing v1.4 schemas (PtSessionRecordedPayload, PtPackagePlanCreatedPayload, etc.) all type UUIDs as `uuid.UUID`; mirroring that precedent avoids divergence. Pydantic v2 accepts both str and UUID inputs on `model_validate` and stringifies on JSONB serialisation. The P13 / REG-36-03 lesson is enforced at the EMIT callsite (Phase 38 service code will pass `str(uuid)` kwargs), NOT at the schema field type.
- **C-06 confirmed: no separate `booking_completed` event.** Completion of a booking is signalled by emitting the EXISTING `pt_session_recorded` event with a non-None `booking_id`. Phase 38's PT-package integration (PKG-05) will be the first producer.
- **resource_type uses snake_case (audit-side), not kebab (RBAC-side).** `("slot_published", "schedule_slot")` mirrors the existing `("pt_package_plan_created", "pt_package_plan")` precedent in audit.py; the RBAC `Resource.SCHEDULE_SLOTS = "schedule-slots"` kebab-on-wire enum value lands in plan 37-02. These are intentionally distinct discriminators.
- **Additive PtSessionRecordedPayload extension with default `None`** preserves back-compat for the v1.4 emit callsite at `apps/backend/app/modules/pt_sessions/service.py:record_pt_session` — zero code changes required there in Phase 37.

## Deviations from Plan

None — plan executed exactly as written. All Rule 1-3 deviation triggers (bug, missing-critical, blocking) were absent; the plan's task spec was directly implementable from the canonical files referenced.

## Issues Encountered

- **Minor ruff I001 import-block formatting nit in the new test file.** Auto-fixed via `uv run ruff check --fix`; no behavioural change. (Pre-existing project convention: `from __future__ import annotations` is separated from other imports — ruff's isort flagged the absence of the blank-line separator pattern after auto-formatting. Resolved automatically.)

## Threat Flags

None — this plan ships ZERO new endpoints, request handlers, SQL, or trust-boundary surface. The two STRIDE register entries from the plan (`T-37-01-01` taxonomy drift + `T-37-01-02` PII via extra fields) are both mitigated as designed via the count-assert + per-pair membership test (T-37-01-01) and `extra='forbid'` on every new schema with `ValidationError`-raising tests (T-37-01-02).

## Next Phase Readiness

- **Plan 37-02 (RBAC extension)** can proceed immediately — independent of 37-01 changes.
- **Plan 37-03 (FSM constants)** can proceed immediately — independent.
- **Plan 37-04 (Protocol slots + wiring)** can proceed in parallel.
- **Plan 37-05 (importlinter + SVC001)** can proceed independently.
- **Phase 38 (Schedule + Bookings module)** has the full v1.5 audit contract pre-registered: every Phase 38 emit callsite will pass both the LOCKED_AUDIT_EVENTS membership check AND the AUDIT_PAYLOAD_SCHEMAS strict validation on first run.

## TDD Gate Compliance

The plan is `type: execute` (not `type: tdd` at plan level), but each task carried `tdd="true"`. Both tasks followed RED → GREEN strictly:

- Task 1: RED commit `150d922` (test fails — count is 53, expected 58) → GREEN commit `763b1ed` (test passes after frozenset extension).
- Task 2: RED commit `d09ca91` (test fails — ImportError, schemas don't exist) → GREEN commit `9af8738` (test passes after schemas + extension + registry entries are added).

No REFACTOR commits were needed.

## Self-Check: PASSED

Verified via local checks before write-back:

- `git log --oneline -5` shows all 4 task commits (`150d922`, `763b1ed`, `d09ca91`, `9af8738`).
- `cd apps/backend && uv run python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; print(len(LOCKED_AUDIT_EVENTS))"` -> `58`.
- `cd apps/backend && uv run python -c "from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS, SlotPublishedPayload; assert AUDIT_PAYLOAD_SCHEMAS[('slot_published', 'schedule_slot')] is SlotPublishedPayload; print('ok')"` -> `ok`.
- All 5 new (event, resource_type) tuples grep-confirmed present in `audit.py`.
- All 5 new schema classes grep-confirmed present in `audit_payloads.py`.
- All 5 new registry entries grep-confirmed present in `AUDIT_PAYLOAD_SCHEMAS`.
- `PtSessionRecordedPayload.booking_id: UUID | None = None` grep-confirmed present.
- `uv run ruff check app/core/audit.py app/core/audit_payloads.py tests/unit/test_audit_taxonomy.py tests/unit/test_audit_payloads.py` -> all checks passed.
- `uv run mypy app/core/audit.py app/core/audit_payloads.py` -> Success: no issues found in 2 source files.
- `uv run pytest tests/unit -x -q` -> 505 passed / 1 skipped (zero regression).
- `uv run lint-imports` -> 3 contracts kept, 0 broken (importlinter `core-not-depend-on-modules` still satisfied).

---
*Phase: 37-foundations-bedrock*
*Completed: 2026-05-17*
