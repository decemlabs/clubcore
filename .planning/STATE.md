---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: Schedule + Bookings
status: planning
stopped_at: Phase 40 context gathered
last_updated: "2026-05-18T11:22:01.327Z"
last_activity: 2026-05-18
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 15
  completed_plans: 15
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-17)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 39 — notifications-cron

## Current Position

Phase: 40
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-18

Progress: [░░░░░░░░░░] 0%

## v1.5 Milestone Plan

**Phases:** 37 (Foundations Bedrock) → 38 (Schedule Module + Booking Core) → 39 (Notifications + Cron) → 40 (Telegram /book + OpenAPI + Milestone Verification)
**Cadence:** 3 feature phases + 1 terminal verification phase (mirrors v1.4 cadence)
**Requirements:** 57 mapped (11 INFRA/DEBT → Phase 37; 25 SLOT/BOOK/PKG → Phase 38; 10 NOTIFY/CRON → Phase 39; 11 BOT/HANDOFF/VER → Phase 40). 100% coverage.

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table.

**v1.5 bedrock decisions (C-01..C-15, locked in REQUIREMENTS.md):**

- C-01 — Two-module split: `schedule/` (catalog) + `bookings/` (transaction), Protocol-bridged
- C-02 — Partial UNIQUE `(slot_id) WHERE status='confirmed'` on `bookings` — DB wins race
- C-03 — Decrement-at-delivery preserved; booking does NOT debit `sessions_remaining`
- C-04 — Booking FSM: `confirmed → cancelled / no_show / completed` + central guard
- C-05 — Cancel window: reception ≤24h before slot; owner anytime (mirror B-12)
- C-06 — 5 new LOCKED audit events: `slot_published`, `slot_cancelled`, `booking_created`, `booking_cancelled`, `booking_no_show`. `booking_completed` NOT a separate event — carried by `pt_session_recorded` with `booking_id` payload field
- C-10 — No-show is cron-only at 23:10 MSK; no manual endpoint in v1.5
- C-11 — 24h reminder cron at 06:35 MSK + `booking_notifications` idempotency table

**Critical pre-emptions for Phase 37 (from PITFALLS.md):**

- P3: Audit events AND payload schemas pre-registered before any callsite
- P13: All `audit_payloads.py` UUID fields typed as `str`, not `UUID`
- P1: Partial UNIQUE on `bookings` must be conditional (`WHERE status='confirmed'`)
- P8: `BOOKING_STATUS_TRANSITIONS` constant declared before service code lands
- P6: Use `DateTime(timezone=True)` (TIMESTAMPTZ) for all slot time columns

### Pending Todos

- Run `/gsd-plan-phase 37` to create Phase 37 plans (Foundations Bedrock).

### Blockers/Concerns

11 remaining DEFER-36-04-A pytest failures from v1.4 (7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug) — tracked in Deferred Items. Do not let these block Phase 37 start; address during Phase 37 or 38 as a parallel concern.

## Deferred Items

Items carried forward from v1.4 milestone close on 2026-05-16:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| pytest_failures | DEFER-36-04-A — 11 remaining failures (was 44; 33 cleared in Phase 36.1 hot-fix): 7 pt_sessions MissingGreenlet, 3 pt_packages validation_error envelope drift, 1 test_revert_predicate partial-UNIQUE logic bug | partial-resolved | Phase 36-04 → Phase 36.1 | Address during v1.5 cycle (Phase 37 plan 37-01 can include a sweep if cheap; otherwise Phase 38 pre-flight) |
| lint_format | DEFER-36-04-B — `ruff format --check` red on 123 files | acknowledged | Phase 36-04 | Defer to v1.9 doc-debt sweep or a standalone quick task |
| verification_gap | Phase 31 admin-web browser checks (2 scenarios) | acknowledged | Phase 31 | v2.0 Frontend Integration milestone scope |
| quick_task | `260501-ndi` orphan in `.planning/quick/` | acknowledged | v1.0 | Defer to `/gsd-cleanup` |
| uat_gap | Phase 06 + Phase 08 HUMAN-UAT.md pending scenarios | partial | v1.1 | v2.0 Frontend Integration milestone scope |

## Session Continuity

Last session: 2026-05-18T11:22:01.323Z
Stopped at: Phase 40 context gathered
Resume: `/gsd-plan-phase 37`
