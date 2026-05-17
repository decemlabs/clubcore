# Project Research Summary

**Project:** Sportzal
**Domain:** PT-slot booking integrated into existing gym CRM (v1.5 Schedule + Bookings)
**Researched:** 2026-05-17
**Confidence:** HIGH — all 4 dimensions derived from live codebase archaeology + triangulated industry sources

---

## Executive Summary

Sportzal v1.5 closes the last empty business-module gap by adding a minimal viable PT-booking surface: trainers publish 1:1 availability windows, clients book individual slots, and a `confirmed → cancelled / no_show / completed` FSM tracks the lifecycle with race-safe DB enforcement. The domain is well-understood (industry standard: instant-confirm, 24h cancel window, manual no-show marking, session-debit at delivery rather than reservation), and every required capability composes cleanly from the v1.4 locked stack — no new backend runtime libraries are needed. The architectural pattern (two independent modules bridged by Protocol slots from the composition root) is identical to the `pt_packages` / `pt_sessions` split from v1.4 and already has five precedents in the codebase.

The primary risk is infrastructure correctness at the start of Phase 37, not feature complexity. Three confirmed recurring incidents (REG-29-03 bot resolver double-wiring, REG-29-04 eager ORM import in cron runners, REG-36-03 UUID stringify in audit payloads) WILL happen again in v1.5 callsites unless the foundation plan pre-empts them explicitly. The `BOOKING_STATUS_TRANSITIONS` constant, all 5 `LOCKED_AUDIT_EVENTS` entries, all 5 `audit_payloads.py` payload schemas, the 3 new Protocol slot definitions, and `TIMESTAMPTZ` column types for slot times must ALL land in Phase 37 before any module service code is written — this is the single highest-leverage action in the entire milestone.

Feature scope is tightly bounded. P1 features (booking creation + FSM + race-safe UNIQUE + audit chain + Telegram confirmation DM + bot `/book`) are all low-to-medium complexity and directly supported by v1.4 patterns. The one genuine complexity bump is the cross-module `completed` callback (PT-session recording triggers booking completion via Protocol slot in the same transaction) and the 24h reminder cron (requires a new `booking_notifications` idempotency table). Both have direct v1.4 precedents. Group classes, online payment, trainer Telegram DMs, and recurring slot templates are explicitly out of scope and must not creep in.

---

## Key Findings

### Recommended Stack

No new backend runtime dependencies. The full v1.5 feature set — slot modeling, race-safe booking, FSM, no-show cron, Telegram `/book` handler — composes from the already-locked v1.4 stack. The five candidate libraries evaluated were all rejected: `python-dateutil`/`rrule` (10 lines of `timedelta` covers 100% of single-gym weekly recurrence), `icalendar` (calendar export deferred to v1.8), `ConversationHandler` (stateless CommandHandler + InlineKeyboard callback covers the two-step `/book` flow without the `concurrent_updates=False` regression risk), and `python-statemachine`/`transitions` (the `BOOKING_STATUS_TRANSITIONS` dict constant pattern is proven at scale).

**Core technologies reused without change:**
- `SQLAlchemy 2.0 async + Alembic` — 3 migrations: `0016_trainer_availability_slots`, `0017_bookings`, `0018_pt_sessions_booking_id` (nullable ALTER)
- `ARQ 0.28.0` — new `mark_no_show_bookings` cron, exact pattern of `expire_memberships`
- `app/core/idempotency.py` (Phase 32, shipped) — `Depends(verify_idempotency)` on `POST /bookings`, route-bound key (CR-01 discipline)
- `python-telegram-bot 22.7` — stateless `CommandHandler("book") + CallbackQueryHandler(pattern=r"^book:")`, no ConversationHandler
- `app/core/dependencies.py` Protocol slots — 3 new slots added, same pattern as 7 existing ones
- `stdlib zoneinfo.ZoneInfo("Europe/Moscow")` — all temporal logic, same as prior milestones

### Expected Features

**Definitely v1.5 (P1 — table stakes):**
- `trainer_availability_slots` CRUD — one-off slots, `active`/`cancelled`/`booked` status, `TIMESTAMPTZ` start/end
- Booking creation with three-check pre-flight (slot active, active PT-package, sessions_remaining > 0)
- Booking FSM: `confirmed → cancelled / no_show / completed` with central `BOOKING_STATUS_TRANSITIONS` guard
- Race-safe partial UNIQUE `(slot_id) WHERE status='confirmed'` — DB wins the race
- `booking_id` optional FK on `pt_sessions`; `completed` transition triggered atomically on PT-session record
- 5 new LOCKED audit events: `slot_published`, `booking_created`, `booking_cancelled`, `booking_no_show`, `booking_completed`
- Booking cancellation: reception ≤24h before slot, owner anytime — mirror of B-12 PT-sessions
- Slot-cancelled cascade: cancelling a slot transitions any linked `confirmed` booking to `cancelled` + DM
- Telegram DM on booking confirmed (immediate) and booking cancelled
- Telegram bot `/book`: slot discovery via InlineKeyboard + one-tap confirmation roundtrip
- Anti-oracle bot DM: single constant for all negative outcomes (no PT-package / no slots / not linked)

**Include if cheap (P2 — differentiators):**
- Buffer-time guard at slot publish: 10 min hardcoded (prevents back-to-back slot collisions for same trainer)
- Manual no-show marking `POST /bookings/{id}/no_show` + no-show DM to client
- 24h reminder DM via ARQ cron at 06:35 MSK + `booking_notifications` idempotency table (UNIQUE `(booking_id, kind)`) — mirrors `membership_notifications` from v1.3
- `trainer_id` optional FK on `pt_packages` (enables bot trainer discovery; bot asks selection if NULL)
- PT-package refund guard: block refund if outstanding `confirmed` bookings exist (409 `outstanding_bookings_exist`)
- PT-package validity-window guard at booking: reject if `slot.start_time.date() > pt_package.end_date`

**Out of scope — do not add:**
- Group classes / capacity > 1 (never for v1.5)
- Online payment at booking (v1.7 ЮKassa)
- Trainer Telegram DMs (v1.6 — no `telegram_chat_id` on trainers table yet)
- Email notifications (v1.6)
- Recurring slot template with `slot_templates` table (v2.x)
- Trainer self-service slot publication (v2.x — no trainer auth role)
- Auto-no-show cron (v1.5.1 — manual marking sufficient)
- Atomic reschedule endpoint (v1.6)
- Bot `/cancel_booking` command (v1.5.1)
- Waitlist (v2.x)
- iCal `.ics` export (v1.8)

### Architecture Approach

Two independent modules (`app/modules/schedule/` and `app/modules/bookings/`) bridged by 3 new Protocol slots registered from the `app/main.py` composition root. The `modules-independent` import-linter contract remains intact — `bookings` never imports from `schedule`; cross-module access uses the Protocol slot pattern or raw `sa.text()` SQL (D-34-04a discipline). The `schedule` module owns the catalog concern (trainer publishes availability windows); the `bookings` module owns the transaction concern (client reserves a window). This mirrors the `pt_packages` / `pt_sessions` bounded-context split from v1.4 exactly.

**Major components:**
1. `app/modules/schedule/` — `TrainerAvailabilitySlot` ORM + CRUD service + `SLOT_STATUS_TRANSITIONS` constant + 4 REST endpoints; provides `resolve_slot_by_id` and `restore_slot_to_available` as concrete Protocol implementations
2. `app/modules/bookings/` — `Booking` ORM with partial UNIQUE + `BOOKING_STATUS_TRANSITIONS` constant + `create_booking` (atomic slot-status flip + INSERT in single UoW) + `cancel_booking` + `complete_booking` (called by `pt_sessions.service` via Protocol slot) + 4 REST endpoints
3. `app/core/dependencies.py` additions — `SlotByIdResolver`, `BookingSlotRestorer`, `BookingCompleter` Protocol types + register/get functions (3 new slots)
4. `app/workers/scheduled/mark_no_show_bookings.py` — new ARQ cron at 23:10 MSK; idempotent `WHERE status='confirmed' AND slot_end_time < now()`; emits `booking_no_show` per row
5. Telegram bot additions — `book_handler` + `book_callback_handler`; `HandlerContext` extended with `bookings_service`; `callback_data = "BK:{slot_uuid}"` (39 bytes, within 64-byte Telegram limit)
6. `alembic/` — migrations `0016` (trainer_availability_slots with TIMESTAMPTZ), `0017` (bookings with partial UNIQUE), `0018` (pt_sessions ALTER ADD booking_id nullable)

**Key data flow — booking creation:**
`POST /bookings` → `require_permission(CREATE, BOOKINGS)` → (1) `get_active_pt_package` Protocol slot, (2) `get_slot_by_id` Protocol slot, (3) INSERT booking + UPDATE slot to `booked` in single UoW + emit `booking_created` → `await session.commit()` → 201

**Key data flow — booking completion:**
`POST /pt-sessions` (with `booking_id`) → existing v1.4 atomic decrement + `SELECT FOR UPDATE` on booking row → `get_booking_completer()(session, booking_id)` → `UPDATE bookings SET status='completed' WHERE id=:id AND status='confirmed'` + emit `booking_completed` → single `await session.commit()`

### Critical Pitfalls

The following 5 pitfalls MUST be prevented in Phase 37 (foundations) before any callsite lands. All 20 pitfalls are documented in `PITFALLS.md`.

1. **Audit events not pre-registered before first callsite commit (P3 / INFRA-15 repeat)** — Extend `LOCKED_AUDIT_EVENTS` AND add all 5 `audit_payloads.py` schemas AND bump `test_audit_taxonomy.py` count in the first plan of Phase 37, before any service code lands. The AST gate passes silently if events are not pre-registered; the runtime `emit()` call fails on first POST — a hard-to-catch gap when unit tests mock `audit.emit`.

2. **UUID stringify bug in audit callsites (P13 / REG-36-03 confirmed repeat)** — All `audit_payloads.py` schemas must type `id` fields as `str`, not `UUID`. Callsites must call `str(booking.id)` explicitly. This is a confirmed recurring bug from v1.4 pt_sessions. Pre-defining schemas in Phase 37 with correct types prevents introduction in Phases 38-39.

3. **Partial UNIQUE on bookings missing or unconditional (P1)** — Migration `0017` must create `UNIQUE INDEX uq_bookings_slot_confirmed ON bookings (slot_id) WHERE status='confirmed'`. An unconditional `UNIQUE(slot_id)` would forbid any rebooking after cancellation. A concurrent race test against real Postgres 16 (not a mock) must pass — same discipline as VIS-TEST-01.

4. **BOOKING_STATUS_TRANSITIONS constant not defined before service uses it (P8)** — Declare in `app/modules/bookings/constants.py` in Phase 37 before the bookings service is written. The `complete_booking` SQL path must include `WHERE status='confirmed'` predicate. Mirror of v1.3 Phase 24 / v1.4 Phase 30 discipline.

5. **TIMESTAMPTZ vs TIMESTAMP WITHOUT TIME ZONE for slot times (P6)** — Use `DateTime(timezone=True)` in the `TrainerAvailabilitySlot` ORM model. Bare `DateTime()` defaults to `TIMESTAMP WITHOUT TIME ZONE`, causing the no-show cron to fire 3 hours late (container TZ=UTC, slots entered in Moscow local time). Non-recoverable post-data-entry without a data migration.

**Additional Phase 37 must-do:**
- Register all Protocol slots BEFORE `include_router(api)` in `create_app()` + add startup integration test asserting all resolver slots non-None (P17)
- Confirm B-10 test still passes: `POST /visits` for PT-package-only client → 409 (P20)

---

## Implications for Roadmap

### Phase 37 — Foundations Bedrock

**Rationale:** Every prior milestone (v1.3 Phase 24, v1.4 Phase 30) proved that pre-registering audit events and architectural contracts before callsites land eliminates an entire class of CI failures. No migrations, no new module code.

**Delivers:**
- `LOCKED_AUDIT_EVENTS` extended to N+5 entries (5 new pairs: slot/booking lifecycle)
- 5 `audit_payloads.py` Pydantic schemas with `str`-typed UUID fields and `extra='forbid'`
- `BOOKING_STATUS_TRANSITIONS` + `SLOT_STATUS_TRANSITIONS` constants
- 3 new Protocol slot types + register/get functions in `app/core/dependencies.py`
- `Resource.SCHEDULE_SLOTS` + `Resource.BOOKINGS` in `app/core/permissions.py`; `OWNER_ONLY` extended with slot publish/cancel pairs
- Taxonomy test count bumped; RBAC parity test updated with admin-web frozen comment
- Startup integration test: `create_app()` resolvers all non-None
- B-10 regression test confirmed passing

**Avoids:** P3, P8, P13, P17, P20

**Research flag:** Standard patterns — no phase research needed. Mirrors v1.3 Phase 24 and v1.4 Phase 30 exactly.

---

### Phase 38 — Schedule Module + Booking Core

**Rationale:** `bookings.service.create_booking` consumes `get_slot_by_id`; the concrete implementation in `schedule.service` must exist first. Both modules land in this phase to keep the atomic create transaction (slot flip + booking INSERT) testable end-to-end.

**Delivers:**
- Migration `0016_trainer_availability_slots` (TIMESTAMPTZ, partial index on available status, soft-delete, buffer-time guard in service)
- `app/modules/schedule/` fully implemented (models, schemas, repository, service, constants, router — 4 endpoints)
- `register_slot_resolver` + `register_booking_slot_restorer` wired in `app/main.py` AND `app/workers/telegram_bot.py` (REG-29-03 double-wiring — including confirmation that `register_active_pt_package_resolver` is also present in bot worker)
- Migration `0017_bookings` (partial UNIQUE `uq_bookings_slot_confirmed`, snapshot fields, `pt_package_id NOT NULL FK`)
- `app/modules/bookings/` fully implemented (models, schemas, repository, service, constants, router — 4 endpoints)
- `POST /bookings` with `Depends(verify_idempotency)` route-bound (CR-01 discipline)
- Atomic create: booking INSERT + slot status flip `available → booked` in single UoW
- Booking cancellation with `datetime.now(UTC)` 24h window (no naive datetime)
- PT-package refund guard: raw-SQL count of outstanding bookings → 409 Option A
- PT-package validity-window guard at booking creation
- Concurrent race test: two simultaneous `POST /bookings` for same slot — only one wins

**Avoids:** P1, P2, P4, P5 (partial), P6, P7, P14, P18, P19

**Research flag:** Standard patterns — no phase research needed.

---

### Phase 39 — Bookings Completion + PT-Sessions Wiring + No-Show Cron

**Rationale:** The `complete_booking` Protocol slot and the `booking_id` FK on `pt_sessions` form a single cross-module transaction and must land together. No-show cron and 24h reminder cron land here alongside PT-session wiring to avoid splitting ARQ job additions.

**Delivers:**
- Migration `0018_pt_sessions_booking_id` (nullable `booking_id UUID NULL REFERENCES bookings(id) ON DELETE SET NULL`)
- `pt_sessions.service` modified: `SELECT FOR UPDATE` on booking row, then call `get_booking_completer()` in same UoW before commit
- `register_booking_completer` wired in `app/main.py` only (not bot worker)
- Guard: `record_pt_session` rejects `booking_id` where `booking.status != 'confirmed'` → 409
- Guard: `cancel_booking` rejects if existing `pt_sessions` row references this booking → 409
- `app/workers/scheduled/mark_no_show_bookings.py` — ARQ cron at 23:10 MSK; mirrors `expire_memberships`
- `scripts/run_no_show_cron_once.py` — one-shot runner with eager mapper import (REG-29-04 prevention)
- `booking_notifications` table with UNIQUE `(booking_id, kind)` + 24h reminder cron at 06:35 MSK
- No-show DM to client at manual `POST /bookings/{id}/no_show`

**Avoids:** P5 (causality inversion — SELECT FOR UPDATE + same-UoW commit), P11, P12

**Research flag:** Standard patterns — no phase research needed.

---

### Phase 40 — Telegram /book Bot + OpenAPI Drift Refresh + Milestone Verification

**Rationale:** Bot integration depends on full bookings service (Phases 38-39). Single-phase OpenAPI regen avoids per-phase drift-gate churn (v1.4 Phase 35 lesson). Verification is the terminal gate.

**Delivers:**
- `book_handler` + `book_callback_handler` in `app/integrations/telegram/handlers.py`
- `HandlerContext` extended with `bookings_service: ModuleType`
- `callback_data = "BK:{slot_uuid}"` (39 bytes); unit test asserting ≤ 64 bytes for all keyboard builders
- Single anti-oracle DM constant `_DM_NO_BOOKING_AVAILABLE`; owner sign-off `D-40-OWNER-COPY-LOCK` in PROJECT.md
- `/book` wired in `build_application`; `register_slot_resolver` confirmed in `telegram_bot.py:main()`
- `openapi.json` byte-stable regen + `schema.d.ts` regenerated + ~8 new `AssertNonNever` forward-guards
- Milestone verification: operator scenarios, Telegram sandbox `/book` end-to-end, concurrent race test, 4 CI gates

**Avoids:** P10 (REG-29-03 repeat — bot missing resolver), P15 (callback_data overflow), P16 (anti-oracle DM leak)

**Research flag:** Standard patterns — no phase research needed.

---

### Phase Ordering Rationale

- **Foundations-first**: audit events + FSM constants + Protocol slot types + RBAC additions before any service code — eliminates the CI-failure-on-first-commit class of bugs (INFRA-15 / Phase 30 lesson)
- **Schedule before Bookings close coupling**: `bookings.service` consumes `get_slot_by_id` from `schedule.service`; integration tests for booking creation cannot run without a real slot resolver
- **PT-sessions wiring after bookings core**: the `complete_booking` Protocol slot registered from `app/main.py`; `pt_sessions.service` calls it; the slot must exist before the caller code is modified
- **Bot and OpenAPI last**: terminal concerns that depend on all service code being stable; single-phase regen avoids multiple drift-gate commits

### Research Flags

**Phases needing deeper research during planning:** None. All patterns across all 4 phases are direct extensions of established v1.3/v1.4 precedents. Research was performed at this stage.

**Standard patterns (no `/gsd-research-phase` needed):**
- Phase 37: mirrors v1.3 Phase 24 (audit taxonomy) and v1.4 Phase 30 (RBAC + Protocol foundations)
- Phase 38: mirrors v1.4 Phase 32-33 (idempotency + Protocol slots + partial UNIQUE)
- Phase 39: mirrors v1.3 Phase 27 (ARQ cron + notification idempotency) and v1.4 Phase 34 (PT-session atomic decrement + cross-module callback)
- Phase 40: mirrors v1.2 Phase 20 (Telegram bot + anti-oracle DMs) and v1.4 Phase 35 (OpenAPI drift gate)

---

## Open Questions for REQUIREMENTS.md Step

| # | Question | Default Recommendation | Must Resolve Before |
|---|----------|----------------------|---------------------|
| Q1 | `trainer_id` on `pt_packages` — required for bot or optional (bot asks if NULL)? | Optional; bot presents trainer picker inline if NULL | Phase 38 plan (affects pt_packages schema) |
| Q2 | 24h cron reminder — P2 in v1.5 or defer to v1.5.1? | Include in Phase 39 (same pattern as v1.3 expiring-soon) | Phase 39 plan |
| Q3 | `no_show` — terminal in v1.5, or allow `no_show → confirmed` reverse within N hours? | Terminal (Option C); document in `constants.py` with Key Decision reference | Phase 37 plan (FSM constant) |
| Q4 | `slot_published` — fires on creation (slot goes active immediately) or on explicit publish action? | On creation; `slot_published` = `slot_created_as_active` | Phase 37 plan (taxonomy) |
| Q5 | PT-package expires after booking confirmed — auto-cancel or leave `confirmed`? | Leave `confirmed`; 409 surfaces at PT-session time (matches "block-then-explain" pattern) | Phase 38 plan |
| Q6 | Slot buffer — hardcoded 10 min or configurable? | Hardcoded 10 min for v1.5 | Phase 38 plan |
| Q7 | Owner-copy lock for anti-oracle bot DM | `D-40-OWNER-COPY-LOCK` sign-off in PROJECT.md before Phase 40 merges | Before Phase 40 |
| Q8 | `pt_package_id` on `bookings` — NOT NULL or nullable? | NOT NULL for v1.5 | Phase 38 plan (migration) |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All decisions verified against live `pyproject.toml`; 5 candidate libraries evaluated and explicitly rejected |
| Features | HIGH (P1) / MEDIUM (P2) | P1 table-stakes triangulated from 10+ industry sources; P2 differentiators are Sportzal-specific extrapolation |
| Architecture | HIGH | All decisions derived from live codebase; 7 existing Protocol slots confirmed; import-linter contracts verified |
| Pitfalls | HIGH | 17 of 20 are confirmed repeats of documented incidents (REG-29-03, REG-29-04, REG-36-03, INFRA-15, VIS-TEST-01, D-34-04a, CR-01) |

**Overall confidence:** HIGH

### Gaps to Address

- **Audit event baseline count discrepancy:** ARCHITECTURE.md states 53 entries; PROJECT.md and PITFALLS.md state 51. Phase 36.1 hot-fix may have added entries. REQUIREMENTS.md must verify the exact current count before Phase 37 plan specifies the target. The delta is always +5 regardless of baseline.
- **`register_active_pt_package_resolver` in bot worker confirmed missing:** PITFALLS.md line 842 confirms this is NOT currently present in `telegram_bot.py:main()`. Must be added in Phase 38 as part of the schedule resolver double-wiring — not deferred to Phase 40.
- **Q1 (trainer_id on pt_packages):** If added, requires an Alembic migration in Phase 38. Must be locked before Phase 38 planning begins.
- **Q3 (no_show reverse transition):** Option C (terminal) is simplest but may generate a support request for late-arriving clients. Document the limitation explicitly.

---

## Sources

### Primary (HIGH confidence — live codebase)
- `apps/backend/app/core/dependencies.py` — 7 existing Protocol slots confirmed
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` confirmed at research time
- `apps/backend/app/core/idempotency.py` — CR-01 route-binding confirmed shipped (Phase 32)
- `apps/backend/app/workers/telegram_bot.py` — `register_active_pt_package_resolver` confirmed missing in bot worker (gap to close in Phase 38)
- `apps/backend/app/.importlinter` — `schedule` and `bookings` already in `modules-independent`
- `apps/backend/app/workers/__init__.py` — ARQ WorkerSettings + cron-resolution invariant confirmed
- `apps/backend/app/modules/pt_sessions/service.py` — D-34-04a cross-module raw SQL pattern confirmed
- `.planning/PROJECT.md` — v1.5 scope, B-10/B-12 invariants, Key Decisions table
- `.planning/MILESTONES.md` — REG-29-03, REG-29-04, REG-36-03, INFRA-15 incident reports verbatim

### Secondary (HIGH confidence — official docs)
- Context7 `/python-telegram-bot/python-telegram-bot` — `ConversationHandler` `concurrent_updates=False` requirement confirmed; InlineKeyboard + CallbackQueryHandler as idiomatic pick-and-confirm pattern
- Telegram Bot API — `callback_data` 64-byte hard limit confirmed

### Tertiary (MEDIUM confidence — industry triangulation)
- Mindbody, Goldie, SimplyBook.me, SchedulingKit, Trainerize, Bookafy, SuperSaaS — 24h cancel window, instant-confirm, manual no-show marking as industry norms for single-operator PT studios
- Nuffield Health PT Terms — debit-at-delivery (not debit-at-reservation) model confirmed as industry standard
- DialogHealth / SchedulingKit — 24h reminder reduces no-shows ~29% (supports P2 reminder cron in v1.5)

---
*Research completed: 2026-05-17*
*Ready for roadmap: yes*
