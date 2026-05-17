# Stack — v1.5 Schedule + Bookings (PT slots)

**Project:** Sportzal
**Milestone:** v1.5 — Schedule + Bookings (PT slots)
**Researched:** 2026-05-17
**Overall confidence:** HIGH (locked stack fully covers v1.5; recommendation is "no new backend runtime libraries")

---

## Recommendation Summary

No new backend runtime dependencies are needed for v1.5. Every capability — slot modeling, race-safe booking, FSM, no-show cron, Telegram `/book` handler — composes directly from the locked stack already in `apps/backend/pyproject.toml`.

The five research questions are answered below with explicit "WHY NOT a library" rationale for each.

---

## Question 1 — Recurring slots: RRULE / iCal library vs. plain column?

**Decision: plain `recurrence_rule TEXT NULL` column + materialization-on-publish. Do NOT add `rrule`, `icalendar`, or `python-recurrence` as a runtime dependency.**

### Rationale

Sportzal is a single-gym MVP with a single trainer-facing surface. v1.5 scope is "trainer publishes 1:1 PT availability windows; capacity = 1." The question is whether recurring availability (e.g. "every Tuesday 10:00") needs RFC 5545 RRULE semantics or can be handled by a lighter pattern.

Evidence against adding `rrule` / `icalendar` now:

1. **Scope: the recurrence is trainer-internal, not calendar-export.** Trainers publish slots that become discrete `trainer_availability_slots` rows. Clients book discrete rows. The recurrence rule is only needed at slot-creation time to expand "repeat this window weekly" into concrete rows. It is NOT needed at booking time (the booking always targets a concrete `slot_id`).

2. **The expansion problem is simple at single-gym scale.** A trainer at one gym publishes at most a few dozen slots per week. "Weekly on Tuesday" is a 52-row expansion per year. A Postgres loop or Python `for each_occurrence_in_date_range` over `start_date / end_date` using `timedelta(weeks=1)` is 10 lines and covers 100% of real-world cases without an RFC 5545 parser.

3. **`rrule` adds 42 KB of complexity for a feature subset that fits in < 20 lines.** The `python-dateutil` library (which ships the `rrule` module) is a large, RFC-faithful parser that handles `BYMONTH`, `BYDAY`, `BYSETPOS`, `EXDATE`, timezone-aware expansion, etc. None of that is needed for "every Tuesday 10:00 for the next N weeks." Introducing `python-dateutil` binds v1.5 to a complex contract for a feature that only needs weekly cadence.

4. **Locked-stack precedent.** v1.2 visits use a `STORED` computed column and `timedelta` arithmetic. v1.3 expiring-soon cron uses `end_date IN (today+1, today+3, today+7)` — bare `date + timedelta`. The project has never reached for a date-arithmetic library.

**Implementation pattern (no new dep):**

```python
# trainer_availability_slots table
# recurrence_rule: TEXT NULL — human-readable note e.g. "weekly:tue,thu"
# One concrete slot row per occurrence; created at publish time.
# Expansion helper in schedule/service.py:

from datetime import date, timedelta

def expand_weekly_slots(
    base_date: date,
    base_time: time,
    duration_minutes: int,
    weeks_ahead: int,
) -> list[date]:
    return [base_date + timedelta(weeks=w) for w in range(weeks_ahead)]
```

A `recurrence_rule` string stored on the slot is useful as a trainer-facing label ("repeating weekly") and as a signal for the admin-web design team when they render the schedule view in v2.0. Store it; don't parse it at runtime.

**If calendar export is requested later (v1.8+):** add `icalendar` at that point, narrowly scoped to `GET /api/v1/trainers/{id}/slots.ics`. v1.5 does not expose a calendar endpoint — see Question 4.

**Confidence: HIGH** — verified via codebase analysis; consistent with all prior milestone patterns.

---

## Question 2 — Booking endpoint idempotency: needed or not?

**Decision: YES, apply `verify_idempotency` + `idempotent_response` from `app/core/idempotency.py`. The helper already exists; no new library needed. Rationale below.**

### Why idempotency matters for `/book`

The booking endpoint is a **state-changing POST** that:
- Requires an active PT-package with `sessions_remaining > 0`
- Inserts a `bookings` row with `status='confirmed'`
- Emits a `booking_created` locked audit event
- Potentially triggers a Telegram confirmation DM

A reception desk worker who double-clicks "Confirm booking" — or a Telegram user whose `/book` confirmation message is redelivered by Telegram after a network hiccup — must not create two booking rows. The partial UNIQUE `(slot_id) WHERE status='confirmed'` guard prevents the DB from accepting the duplicate, but without idempotency the second request returns 409 `conflict` instead of the clean 201 replay, which is a UX regression.

### Why the existing helper is the right tool

`app/core/idempotency.py` (shipped in v1.4, Phase 32) already implements:
- `verify_idempotency` — FastAPI Depends that validates `Idempotency-Key` header
- Route-bound key (`{method}:{path}:{header_value}`) prevents cross-endpoint replay (CR-01 fix from Phase 33 review)
- Redis NX-EX placeholder + stored envelope pattern
- `idempotent_response` composed helper that replays or raises `idempotency_in_flight`

The booking POST is mechanically identical to the v1.4 membership sale and PT-package sale flows. Apply the same pattern: require `Idempotency-Key` header, use `verify_idempotency` as a Depends, wrap handler body with `idempotent_response`.

**Telegram `/book` bot path:** the bot sends a single confirmation message that translates to a single POST to `bookings.service.create_booking`. The Redis `sz:bot:update:{update_id}` dedup (D-20 pattern from Phase 20) already guards the bot path at the outer layer. The booking endpoint idempotency guard adds a second wall for the API path without interfering with the bot path.

**Confidence: HIGH** — `app/core/idempotency.py` is fully shipped, tested, and integrated in v1.4. Zero new library needed.

---

## Question 3 — Telegram `/book` handler: ConversationHandler or single-message pattern?

**Decision: Stay with the existing single-message CommandHandler pattern. Do NOT introduce ConversationHandler for v1.5.**

### Why ConversationHandler is not the right fit here

`ConversationHandler` (ptb 22) implements a per-user FSM that tracks which "state" a conversation is in across multiple message turns. It is the correct tool for multi-step interactive flows like "book a slot: (1) pick date, (2) pick time, (3) confirm." However, the Sportzal design for v1.5 bot booking is deliberately minimal:

> "Telegram bot `/book` — client books a slot via bot when linked + has active PT-package"

The v1.5 MVP booking flow is: `/book` → bot returns the next available confirmed slot for the client's trainer → client sends `/book confirm <slot_id>` or the bot shows an InlineKeyboard with a single "Confirm" button. This is **at most two message turns** and can be handled by two separate `CommandHandler` registrations (`/book` and `/book_confirm`) plus an `InlineKeyboardMarkup` + `CallbackQueryHandler` for the confirmation step.

Evidence against ConversationHandler:

1. **Concurrency constraint.** ptb 22 docs explicitly state: "ConversationHandler heavily relies on incoming updates being processed one by one; when using this handler, `concurrent_updates` should be set to False." The existing bot worker uses the default Application.builder() which does not set `concurrent_updates=False`. Introducing ConversationHandler would require auditing and potentially changing this setting, risking a regression on the existing `/start` and `/checkin` handlers.

2. **Persistence requirement.** ConversationHandler stores per-user state between messages. The ptb built-in persistence options (`PicklePersistence`) are file-based. Using them means bot restarts lose in-flight conversations silently. A Redis-backed custom persistence requires writing a persistence adapter class — which is more complexity than a simple two-step handler.

3. **The `/book` flow can be made stateless.** If the bot sends an InlineKeyboardMarkup with a "Book slot X" button whose `callback_data` encodes the `slot_id`, the `CallbackQueryHandler` receives the `slot_id` directly from the callback payload without needing to remember any conversation state. This is the idiomatic ptb 22 pattern for pick-and-confirm flows and is used throughout the ptb example library.

4. **Precedent.** The existing `/start` and `/checkin` handlers are stateless single-message handlers. They work by making a DB call + DM response within the single update handler. Adding `/book` as a third stateless handler (+ a `CallbackQueryHandler` for the confirm button) follows the same shape. The `build_application` factory in `app/integrations/telegram/bot.py` already supports adding multiple handlers.

**Implementation pattern (no new dep):**

```python
# In app/integrations/telegram/handlers.py — add:
async def book_handler(update, context, ctx: HandlerContext) -> None:
    """List next available slots for the client's linked trainer."""
    # 1. Resolve client by telegram_user_id via ctx.client_by_telegram_resolver
    # 2. Resolve active PT-package (sessions_remaining > 0) via ctx.active_pt_package_resolver
    # 3. Query upcoming confirmed-free slots for the trainer
    # 4. Render InlineKeyboardMarkup with one button per slot:
    #    callback_data=f"book:{slot_id}"
    ...

async def book_callback_handler(update, context, ctx: HandlerContext) -> None:
    """Handle InlineKeyboard 'Book slot X' callback."""
    # Parses callback_query.data = f"book:{slot_id}"
    # Calls bookings_service.create_booking(...)
    # Replies with success or error DM
    ...
```

Register both in `app/workers/telegram_bot.py` using `CommandHandler("book", ...)` and `CallbackQueryHandler(book_callback_handler, pattern=r"^book:")`.

**HandlerContext** needs two new fields: `bookings_service: ModuleType` and an active-pt-package resolver reference. Both follow the D-05/D-10 pattern exactly.

**Confidence: HIGH** — ptb 22 docs confirmed via Context7; inline keyboard pattern verified; no new library.

---

## Question 4 — iCal / `.ics` calendar export: v1.5 or defer?

**Decision: DEFER to v1.8+. Do NOT add `icalendar` in v1.5.**

### Rationale

The v1.5 deliverable is the booking surface itself: trainer publishes slots, clients book, FSM advances, audit events fire. Calendar export is a convenience feature for trainers who want to sync their published slots with Google Calendar / Apple Calendar. It has zero impact on booking correctness.

The `icalendar` library (PyPI: `icalendar`, ~150 KB) is mature and straightforward. Adding it later is a one-phase task (`GET /api/v1/trainers/{id}/slots.ics` + `icalendar.Calendar` builder). There is no architectural coupling that would make it harder to add in v1.8 vs v1.5.

v1.5 must stay tight — 4 phases estimated. Adding a calendar export endpoint adds at minimum one plan per affected phase (schema, endpoint, test, OpenAPI drift gate). The ROI is low: trainers can see their published slots in the admin-web and no client-facing calendar integration is in scope until v2.0.

**When to add:**
- v1.8 Reports milestone is the natural fit — it already ships read-heavy endpoints (`GET /api/v1/audit-log`, dashboard aggregates). A `slots.ics` endpoint is a read-only export, consistent with the v1.8 theme.
- At that point: `uv add icalendar` (current stable: 6.x, HIGH confidence per PyPI) + single endpoint + tests.

**Confidence: HIGH** — deferral is a strategic scope decision, not a technical uncertainty.

---

## Question 5 — No-show detection: ARQ cron vs. inline?

**Decision: ARQ cron. Specifically, a new `mark_no_show_bookings` cron job at ~10 minutes after gym close (e.g., 23:10 Europe/Moscow = 20:10 UTC, `hour=20, minute=10`). No new library needed.**

### Why inline is wrong

"No-show" means the booking reached its scheduled slot end-time without a `completed` transition (i.e., no PT-session was recorded against it). This cannot be detected inline because:

- The booking endpoint only runs when someone sends a request. There is no request at 23:01 saying "the slot just ended."
- The FSM transition `confirmed → no_show` requires knowing that `slot.end_time < now()` AND `booking.status = 'confirmed'`. This is temporal state, not request-driven state.
- Attaching the check to every request that touches bookings ("lazy flip") is an anti-pattern: it produces inconsistent audit timestamps, makes tests non-deterministic, and leaks responsibility into the wrong layer.

### Why ARQ cron is the right tool

ARQ cron is already the established pattern for temporal state transitions in this codebase:

| Cron job | Trigger condition | Time |
|---|---|---|
| `expire_memberships` | `end_date < today` | 06:05 MSK |
| `expire_pt_packages` | `end_date IS NOT NULL AND end_date < today AND status='active'` | 06:25 MSK |
| `send_expiring_notifications` | `end_date IN (today+1, today+3, today+7)` | 06:15 MSK |

`mark_no_show_bookings` follows the same pattern:
- SQL predicate: `WHERE status='confirmed' AND slot_end_time < now()` (using `AT TIME ZONE 'Europe/Moscow'`)
- Idempotent: can run twice safely (second run matches 0 rows)
- Emits `booking_no_show` locked audit event per row (mirrors `membership_expired` per row)
- Schedule: runs once daily after the last gym slot of the day ends. For a typical gym closing at 23:00 MSK: `hour=20, minute=10` UTC = 23:10 MSK. If gym hours vary, add a settings field `gym_close_time` or simply run at `hour=21, minute=0` (midnight MSK) as a safe always-after-close window.

**Implementation pattern (no new dep):**

```python
# app/workers/scheduled/mark_no_show_bookings.py
async def mark_no_show_bookings(ctx: dict) -> int:
    async with ctx["sessionmaker"]() as session:
        result = await session.execute(
            text("""
                UPDATE bookings
                SET status = 'no_show', updated_at = now()
                WHERE status = 'confirmed'
                  AND slot_id IN (
                      SELECT id FROM trainer_availability_slots
                      WHERE start_time + (duration_minutes * interval '1 minute')
                            < now() AT TIME ZONE 'Europe/Moscow'
                  )
                RETURNING id, slot_id, client_id
            """)
        )
        rows = result.fetchall()
        for row in rows:
            await audit.emit(session, "booking_no_show", ...)
        await session.commit()
        return len(rows)
```

Add to `WorkerSettings.cron_jobs` with `unique=True, keep_result=60`. Register in `on_startup` cron-resolution invariant assertion (existing pattern).

**Edge case: booking was already completed before cron runs.** The `WHERE status='confirmed'` predicate excludes `completed` and `cancelled` rows — no double-transition possible.

**Confidence: HIGH** — pattern is a direct extension of `expire_memberships`; no new library; ARQ 0.28.0 already installed.

---

## Locked stack — no changes needed

All v1.5 work fits inside the existing `apps/backend/pyproject.toml` dependencies:

| Capability | Existing tool | Notes |
|---|---|---|
| `trainer_availability_slots` table | SQLAlchemy 2.0 async + Alembic | New ORM model; partial UNIQUE on `(slot_id) WHERE status='confirmed'` in bookings |
| `bookings` table + FSM | SQLAlchemy + declarative transitions constant | `BOOKING_STATUS_TRANSITIONS` mirrors `MEMBERSHIP_STATUS_TRANSITIONS` |
| Race-safe booking | Postgres partial UNIQUE `(slot_id) WHERE status='confirmed'` | Same pattern as `visits` (Phase 19) and `membership_freeze_periods` (Phase 25) |
| No-show cron | ARQ 0.28.0 (already installed) | New `mark_no_show_bookings` cron; existing WorkerSettings + cron_jobs pattern |
| Booking idempotency | `app/core/idempotency.py` (Phase 32, already shipped) | `verify_idempotency` + `idempotent_response` applied to POST /bookings |
| Telegram `/book` handler | python-telegram-bot 22.7 (already installed) | CommandHandler + CallbackQueryHandler; no ConversationHandler |
| Active PT-package check | Existing `get_active_pt_package` Protocol slot + `ActivePtPackageResolver` | Already wired in Phase 33; booking service calls same resolver |
| 5 new audit events | Existing `LOCKED_AUDIT_EVENTS` frozenset + `audit_payloads.py` | Pre-register in Phase 37 foundations: `slot_published`, `booking_created`, `booking_cancelled`, `booking_no_show`, `booking_completed` |
| RBAC | Existing `Resource` + `Action` StrEnums | Add `Resource.SLOTS`, `Resource.BOOKINGS`; reception: `(CREATE, BOOKINGS)`, `(CANCEL, BOOKINGS)`; owner: all |
| Europe/Moscow TZ | stdlib `zoneinfo.ZoneInfo("Europe/Moscow")` | Same as all prior temporal logic |
| Snapshot pattern | Pydantic v2 `int` field + SQLAlchemy `Integer` | `trainer_name_snapshot NOT NULL` on bookings (mirrors `trainer_name_snapshot` on pt_sessions, Phase 34 B-05) |
| Protocol / composition root | `app/core/dependencies.py` | New `ActiveBookingResolver` + `SlotByIdResolver` Protocol slots registered from `app/main.py` composition root |
| Import-linter contracts | `.importlinter` `modules-independent` | Add `schedule`, `bookings` as two new independent entries |
| Cross-module access (bookings → schedule) | Raw `text()` SQL or a new Protocol slot | Same pattern as `pt_sessions → pt_packages` D-34-04a; bookings service uses raw SQL against `trainer_availability_slots`, never `from app.modules.schedule import ...` |

### New Resource and Action enum values

```python
# app/core/permissions.py additions
class Resource(StrEnum):
    # ... existing ...
    SLOTS = "slots"
    BOOKINGS = "bookings"

# OWNER_ONLY additions (reception can create + cancel bookings within window)
# Owner-only: slot CRUD, booking force-cancel after 24h window
OWNER_ONLY_ADDITIONS: frozenset[tuple[Action, Resource]] = frozenset({
    (Action.DELETE, Resource.SLOTS),
    (Action.PATCH, Resource.SLOTS),    # trainer publishes via owner or self-service
})
```

Three-way parity test (backend ↔ admin-web `can.ts` ↔ test snapshot) must be updated in the foundations phase exactly as in v1.4 Phase 30.

---

## Libraries verified rejected

| Candidate | Status | Reason |
|---|---|---|
| `python-dateutil` / `rrule` | REJECT | RFC 5545 RRULE parser for "repeat weekly" is a sledgehammer for a nail. 10 lines of `timedelta(weeks=n)` expansion covers 100% of single-gym recurring slot cases. |
| `icalendar` | DEFER v1.8 | Calendar export is not in v1.5 scope. Deferral adds zero coupling cost. |
| `ConversationHandler` (ptb built-in) | REJECT | Requires `concurrent_updates=False` (breaks existing handlers), needs persistent state store, and the `/book` flow is achievable with 2 stateless handlers + InlineKeyboard. |
| `PicklePersistence` (ptb built-in) | REJECT | File-based; lost on container restart; not appropriate for Sportzal's docker-compose deployment. |
| Redis-backed ptb persistence adapter | REJECT | Would require writing a custom `BasePersistence` subclass. More complexity than stateless handlers + InlineKeyboard callback_data encoding. |
| `python-statemachine` / `transitions` | REJECT | `BOOKING_STATUS_TRANSITIONS: dict[str, frozenset[str]]` + `_assert_can_transition()` is proven at v1.3/v1.4 scale. |
| Celery / Dramatiq | REJECT | ARQ 0.28.0 already installed, covers all async job needs, locked in stack. |
| Any RRULE / scheduling framework (`APScheduler`, `schedule`) | REJECT | ARQ cron is the established pattern; introducing a second job scheduler creates two sources of truth for `WorkerSettings`. |
| `fakeredis[aioredis]` upgrade | NO ACTION | Already in dev deps (`fakeredis>=2.35.1`); the booking idempotency + bot dedup tests reuse the existing `fakeredis` fixture pattern from Phase 32/33. |

---

## Import-linter contract additions

```ini
# .importlinter additions for v1.5
[importlinter:contract:modules-independent]
# add to source_modules list:
#   app.modules.schedule
#   app.modules.bookings
# Both follow the existing modules-independent contract.
# Cross-module access: bookings → schedule uses raw text() SQL (D-34-04a precedent).
```

---

## Dev dependency additions — ZERO

No new dev dependencies. `fakeredis` (already installed) covers Redis mocking for idempotency tests. `pytest-asyncio` + `httpx ASGITransport` cover all new endpoint tests. The existing `SAVEPOINT`-based per-test isolation handles the new tables transparently.

---

## Sources

- `apps/backend/pyproject.toml` — confirmed installed versions (python-telegram-bot 22.7, arq 0.28.0, redis 5.x, SQLAlchemy 2.0, Pydantic 2.11)
- `app/core/idempotency.py` — Phase 32 idempotency helper confirmed shipped and fully functional
- `app/core/dependencies.py` — Protocol slot pattern confirmed; `ActivePtPackageResolver`, `TrainerByIdResolver` etc. all established
- `app/integrations/telegram/` — existing bot.py + handlers.py confirmed stateless single-handler architecture
- `app/workers/__init__.py` — ARQ WorkerSettings pattern confirmed; cron_jobs list + resolution invariant
- Context7 `/python-telegram-bot/python-telegram-bot` — ConversationHandler concurrency constraints verified (concurrent_updates=False requirement; persistence options)
- ptb 22 docs (Context7) — InlineKeyboardMarkup + CallbackQueryHandler pattern confirmed as idiomatic for pick-and-confirm flows
- `.planning/PROJECT.md` v1.5 section — scope confirmed (no group classes, no online payment, Telegram bot /book)
- `.planning/MILESTONES.md` v1.4 section — Phase 32/33/34 patterns confirmed as the implementation precedent

---
*Stack research for: Sportzal v1.5 Schedule + Bookings (PT slots)*
*Researched: 2026-05-17*
