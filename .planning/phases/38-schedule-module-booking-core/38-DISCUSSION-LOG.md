# Phase 38: Schedule Module + Booking Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 38-schedule-module-booking-core
**Mode:** `--auto` — Claude auto-selected recommended defaults for all gray areas; no interactive AskUserQuestion calls were made. Single-pass per `modes/auto.md` cap.
**Areas discussed:** Plan structure, Slot model, Booking model, PT-package/session integration, Idempotency & error mapping, Cancel-window & time handling, Audit & compliance, No-show cron forward-link

---

## Plan Structure

| Option | Description | Selected |
|--------|-------------|----------|
| 3 plans (mirror Phase 32) | Combine schedule + bookings + integration into 3 condensed plans | |
| 6 plans grouped by module/table boundary | Atomic commits per module (schedule, bookings-create, bookings-cancel/list, pt-package integration, pt-session integration, lint+importlinter sweep) | ✓ |
| 9 plans 1-per-requirement-cluster | Maximum atomicity (SLOT, BOOK-create, BOOK-cancel, BOOK-list, PKG-trainer, PKG-refund, PKG-session-fk, PKG-session-complete, sweep) | |

**Claude's choice:** 6 plans. **Rationale:** mirrors v1.4 Phase 33/34 cadence (3 plans for sale+refund + 3 for sessions). Atomic enough to bisect; not so granular it creates wave-orchestration overhead.

---

## Slot Model — `status` enum values

| Option | Description | Selected |
|--------|-------------|----------|
| `available / booked / cancelled` | Research ARCHITECTURE.md draft | |
| `active / booked / cancelled` | REQUIREMENTS SLOT-01 + Phase 37 `SLOT_STATUS_TRANSITIONS` already use this | ✓ |

**Claude's choice:** `active`. REQUIREMENTS overrides research draft; FSM constant already locked.

---

## Slot Model — soft-delete

| Option | Description | Selected |
|--------|-------------|----------|
| Add `deleted_at` (SoftDeleteMixin) | Research draft pattern | |
| No soft-delete — cancellation via status flip | REQUIREMENTS SLOT-02 explicitly says "NO DELETE" | ✓ |

**Claude's choice:** No soft-delete. Mirrors REQUIREMENTS lock.

---

## Slot Model — recurrence

| Option | Description | Selected |
|--------|-------------|----------|
| Add `recurrence_rule TEXT NULL` + horizon expansion | Research draft | |
| One-off slots only | REQUIREMENTS SLOT-02 "publish one-off slot" | ✓ |

**Claude's choice:** One-off only. Recurrence deferred to v1.8 reports milestone.

---

## Slot overlap detection

| Option | Description | Selected |
|--------|-------------|----------|
| Postgres `EXCLUDE USING gist` (requires btree_gist) | Research suggestion | |
| App-layer `tstzrange && tstzrange` with `with_for_update()` | PITFALLS Pitfall 2 Tech-debt row accepts for v1.5 single-zal | ✓ |

**Claude's choice:** App-layer. Single-zal, low-concurrency-publish path. EXCLUDE deferred to v2.0.

---

## Booking Model — snapshot columns

| Option | Description | Selected |
|--------|-------------|----------|
| `trainer_name_snapshot` + `slot_*_snapshot` cols | Research draft for display-integrity | |
| No snapshots; use `joinedload` + structural no-hard-delete invariant | REQUIREMENTS BOOK-01 does not list snapshots; soft-delete absent (D-38-04) | ✓ |

**Claude's choice:** No snapshots. The no-hard-delete + ON DELETE RESTRICT pair guarantees readable historical context structurally.

---

## Booking Cancellation Authorization

| Option | Description | Selected |
|--------|-------------|----------|
| Check `booking.created_by_user_id == current_user.id OR owner` | Stricter ownership model | |
| Reception+owner can cancel any booking (gym-staff trusted) | Mirrors v1.4 pt_sessions cancel pattern | ✓ |

**Claude's choice:** Trusted gym-staff. Audit trail records `cancelled_by_user_id` for accountability.

---

## PKG-06 reverse-transition policy

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-revert booking `completed → confirmed` on pt_session cancel | Symmetric pairing | |
| NO auto-revert; operator creates new booking if needed | REQUIREMENTS PKG-06 explicit; FSM constant `completed → ∅` | ✓ |

**Claude's choice:** NO auto-revert. REQUIREMENTS-locked; FSM enforces.

---

## Cross-Module SQL Discipline (booking-completion + refund-guard)

| Option | Description | Selected |
|--------|-------------|----------|
| All raw `sa.text()` (reads + writes) | Simplest single pattern | |
| Hybrid: raw SQL for reads, Protocol slot for writes | Reads inside UoW; writes preserve FSM ownership in bookings module | ✓ |
| All Protocol slots (no raw SQL) | Maximum decoupling but extra round-trip-through-registry overhead | |

**Claude's choice:** Hybrid. Mirrors D-34-04a v1.4 precedent.

---

## Booking partial-UNIQUE nullability of `pt_package_id`

| Option | Description | Selected |
|--------|-------------|----------|
| NOT NULL `pt_package_id` | REQUIREMENTS BOOK-01 + simpler refund-guard query | ✓ |
| NULLABLE `pt_package_id` for future non-PT bookings | PITFALLS Tech-debt row accepts | |

**Claude's choice:** NOT NULL. Group classes anti-scope for v1.5; future non-PT bookings get their own table.

---

## DEFER-36-04-A sweep timing

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep entirely in Phase 38 plan 38-06 | Surface touched anyway; cheap if cheap | ✓ |
| Defer entirely to Phase 40 milestone verification | Keep Phase 38 focused | |
| Spawn dedicated cleanup phase | Adds milestone overhead | |

**Claude's choice:** Sweep in plan 38-06 when surface is open; remaining failures fall through to Phase 40.

---

## Claude's Discretion

All decisions in this discussion were made by Claude under `--auto` mode using recommended defaults from REQUIREMENTS, PITFALLS, ARCHITECTURE research, and v1.4 codebase precedent. The user can audit and override any D-38-NN entry in `38-CONTEXT.md` before `/gsd-plan-phase 38` consumes it.

## Deferred Ideas

Captured under the `<deferred>` section of `38-CONTEXT.md`. Notable cross-milestone deferrals:
- Postgres EXCLUDE constraint for slot-overlap → v2.0
- Snapshot columns on bookings → re-evaluate if hard-delete is ever introduced
- Recurrence (RRULE) → v1.8
- Nullable `pt_package_id` for non-PT bookings → v1.7+
- Manual `POST /bookings/{id}/no_show` endpoint → v1.5.1 if operational need surfaces
- `no_show → confirmed` reopen flow → v1.6 if requested
