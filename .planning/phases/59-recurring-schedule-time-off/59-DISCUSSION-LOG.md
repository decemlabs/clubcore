# Phase 59: Recurring Schedule + Time-Off - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 59-recurring-schedule-time-off
**Mode:** `--auto` (all gray areas auto-selected; recommended option chosen per area, no interactive prompts)
**Areas discussed:** Module & schema placement · Recurring pattern table + cron idempotency/horizon · Time-off conflict semantics · RBAC + audit pre-registration · Endpoint surface & cron scheduling

---

## Module & schema placement

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing `app/modules/schedule/` | Both concerns reference slots + trainers; reuse cancel cascade & overlap logic | ✓ |
| New `app/modules/recurring/` module | Would force cross-module imports or Protocol slots for schedule data | |

**Auto-choice:** Extend `app/modules/schedule/` (recommended; research ARCHITECTURE Q2).
**Notes:** Zero new `.importlinter` entry, zero new `ignore_imports` edges (D-59-01).

---

## Recurring pattern table + cron idempotency/horizon

| Option | Description | Selected |
|--------|-------------|----------|
| Materialize-ahead, env horizon=56, ON CONFLICT DO NOTHING | REC-02 verbatim; ALTER slots table (nullable author + UNIQUE) | ✓ |
| Expand-on-read | Research anti-feature; recompute on every query | |
| Research horizon 14/28 days | Superseded by REQUIREMENT default 56 | |

**Auto-choice:** Materialize-ahead, `RECURRING_SLOT_HORIZON_DAYS=56`, DST-safe `zoneinfo` expansion, idempotent `ON CONFLICT (trainer_id, start_time)` (recommended).
**Notes:** Requirement's 56-day default overrides research's 14/28 (D-59-04). PITFALL 7 DST golden test is an acceptance criterion. `created_by_user_id` made nullable for cron-authored slots (D-59-05).

---

## Time-off conflict semantics

| Option | Description | Selected |
|--------|-------------|----------|
| REQUIREMENT REC-03 / D-TIMEOFF-CONFLICT | Auto-cancel active overlaps; 409 on booked; `?force=true` cascades FSM + DM | ✓ |
| Research "block + manual cancel" | 409 only; owner manually cancels each booking first; no auto-cancel | |

**Auto-choice:** REQUIREMENT REC-03 behavior (recommended — it supersedes the older research narrative).
**Notes:** Reuses `cancel_slot` booked→cancelled cross-module raw-SQL cascade (D-38-11) + `_dispatch_booking_dm` (D-59-06). This is the single most important planner-facing nuance: requirement wins over research.

---

## RBAC + audit pre-registration

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing owner-only `SCHEDULE_SLOTS` pairs + 4 new audit events | No new Resource/pairs; no admin-web edits; parity unchanged | ✓ |
| New `Resource.RECURRING` + new OWNER_ONLY pairs | Would touch frozen admin-web (can.ts/registry.ts) unnecessarily | |

**Auto-choice:** Reuse `SCHEDULE_SLOTS` RBAC; pre-register 4 `LOCKED_AUDIT_EVENTS` (recommended).
**Notes:** REC-04 list visible to reception via retained VIEW/LIST (D-59-07). Cron emits structlog summary, not per-slot audit (D-59-09).

---

## Endpoint surface & cron scheduling

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `schedule_router`; daily cron 07:00 MSK (hour=4 UTC) | Mounts recurring/time-off endpoints on existing router; cron after reminders | ✓ |
| Separate new router + arbitrary cron time | More surface area; collision risk with existing cron ordering | |

**Auto-choice:** Extend `schedule_router`; cron `hour=4, minute=0` UTC, `unique=True, keep_result=60` (recommended; planner finalizes exact minute + paths).
**Notes:** Exact paths and migration split (1 vs 3 revisions, head 0041) are Claude's discretion.

---

## Claude's Discretion

- Exact table names, column order, index/constraint names, migration split (head `0041` → `0042+`).
- Endpoint path scheme; cron exact minute (non-colliding).
- Pattern deactivation as `is_active=false` flip vs hard DELETE (recommended: flip).
- Optional nullable `recurring_template_id` provenance FK on generated slots.
- Test file layout and golden timestamps.

## Deferred Ideas

- Retroactive un-cancel on time-off deletion (forward-only re-materialization instead).
- RRULE/EXDATE per-date exceptions, iCal/`.ics` sync, recurring client-trainer bookings.
- Trainer self-service portal (admin-web frozen in v1.9).
- Configurable per-trainer/per-zal slot buffer (deferred from v1.5).
- Per-slot audit event for cron-generated slots (structlog summary only).
- Trainer-usage report consuming these tables (Phase 60).
