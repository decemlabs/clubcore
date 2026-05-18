# Phase 40: Telegram /book + OpenAPI Drift Gate + Milestone Verification — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 8 new/modified
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/integrations/telegram/handlers.py` (APPEND `book_handler` + `book_callback_handler` + `_dedupe_update_id`) | handler / integration | event-driven (PTB update → DB UoW → DM) | same file, `checkin_handler` lines 241-348 + `start_handler` lines 137-238 | exact (same file, same role, same flow) |
| `apps/backend/app/integrations/telegram/handlers.py:HandlerContext` (extend NamedTuple +2 fields) | config / closure DTO | request-response | same file, lines 51-68 (Phase 20 v1.2 D-10 added `visits_service` + `redis`) | exact |
| `apps/backend/app/main.py` (composition root — wire 2 new ctx fields) | composition root | request-response | same file, lines 199-216 (Phase 37 INFRA-33 `register_*` triple) | exact |
| `apps/backend/app/workers/telegram_bot.py` (composition root + handler registration) | composition root / worker | event-driven | same file, lines 56-110 (full main() incl. REG-29-03 double-wiring) | exact (same file) |
| `apps/backend/app/modules/bookings/service.py` (APPEND `create_booking_via_bot`) | service / orchestrator | CRUD (10-step UoW + audit + commit) | same file, `create_booking` lines 627-811 AND `apps/backend/app/modules/visits/service.py:create_visit_self_checkin` lines 233-262 | exact (twin precedent) |
| `apps/backend/app/core/audit_payloads.py` (`BookingCreatedPayload` extend; +Literal `actor_role`) | schema / validation | request-response | same file, `BookingCreatedPayload` lines 376-391 + `AUDIT_PAYLOAD_SCHEMAS` lines 434+ | role-match (no existing Literal discriminant — new pattern) |
| `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` (byte-stable regen) | artifact / generated | batch | `apps/backend/scripts/export_openapi.py` runner + Phase 35 commit `511cbf1` shape | exact |
| `packages/api-client/src/schema.contract.test.ts` (APPEND +10 `AssertNonNever`) | test / compile-time guard | request-response | same file, lines 89-200 (v1.4 surface 36 assertions) | exact |
| `.planning/milestones/v1.5-VERIFICATION-LOG.md` | docs / verification record | batch | `.planning/milestones/v1.4-VERIFICATION-LOG.md` (702 lines, locked template) | exact |
| `.planning/milestones/v1.5-verification-evidence/` | docs / evidence transcripts | file-I/O | `.planning/milestones/v1.4-verification-evidence/` (15 transcript files) | exact |

---

## Pattern Assignments

### 1. `apps/backend/app/integrations/telegram/handlers.py` — APPEND `book_handler` + `book_callback_handler` + `_dedupe_update_id`

**Analog:** same file, `checkin_handler` (Phase 20 D-10).

**Imports pattern** (lines 31-46):
```python
from __future__ import annotations

import hashlib
from datetime import datetime as _datetime
from types import ModuleType
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo as _ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import emit as audit_emit

# NOTE: NO `from app.modules.auth import ...` -- integrations perp modules.
# Domain modules arrive via HandlerContext.
```
Phase 40 will additionally need to import from `app.modules.bookings.notifications` (the D-39-02 carve-out grants integrations import permission for the OWNER-COPY-LOCK signed-off DM strings):
```python
from app.modules.bookings.notifications import (
    BOOKING_CONFIRMED_DM,
    _BOT_BOOK_DENIED_DM,
    render_booking_confirmed_dm,
)
```

**HandlerContext extension** (lines 51-68 — current shape):
```python
class HandlerContext(NamedTuple):
    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType       # Phase 20 D-10
    redis: Redis
    # Phase 40 APPEND (at END of tuple to preserve positional construction):
    # bookings_service: ModuleType   # D-40-04 — create_booking_via_bot dispatch
    # schedule_service: ModuleType   # D-40-06 — list_slots for keyboard render
```
Two new fields go at the END (Phase 20's discipline; see `test_handler_context_field_order_is_stable` in `tests/integration/telegram_bot/test_handler_context_shape.py:21-32`).

**Dedup helper extraction (D-40-08)** — currently INLINED in `checkin_handler` at lines 258-279:
```python
update_id = getattr(update, "update_id", None)
if update_id is None:
    return
# ...
dedup_key = f"sz:bot:update:{update_id}"
try:
    set_result: Any = await ctx.redis.set(dedup_key, "1", nx=True, ex=3600)
except Exception as exc:  # fail-open per D-20-3
    logger.warning(
        "bot_redis_dedup_unavailable",
        update_id=update_id,
        chat_id=chat_id,
        error=str(exc),
    )
    set_result = "OK"  # proceed; DB UNIQUE is the real anti-replay backstop
if set_result is None:
    # Replay (Telegram resent the Update on bot restart). Silent per D-20-4.
    logger.debug("bot_replay_skipped", update_id=update_id, chat_id=chat_id)
    return
```
Phase 40 plan 40-01 extracts to module-level:
```python
async def _dedupe_update_id(redis: Redis, update_id: int, chat_id: int) -> bool:
    """Return True on first-sight (proceed); False on replay (handler should return).

    Fail-open per D-20-3: Redis errors are treated as first-sight (DB UNIQUE
    is the real anti-replay backstop). `sz:bot:update:{update_id}` TTL 1h.
    """
    dedup_key = f"sz:bot:update:{update_id}"
    try:
        set_result: Any = await redis.set(dedup_key, "1", nx=True, ex=3600)
    except Exception as exc:
        logger.warning(
            "bot_redis_dedup_unavailable",
            update_id=update_id, chat_id=chat_id, error=str(exc),
        )
        return True  # fail-open
    if set_result is None:
        logger.debug("bot_replay_skipped", update_id=update_id, chat_id=chat_id)
        return False
    return True
```
Then `checkin_handler` (and the two new Phase 40 handlers) call `if not await _dedupe_update_id(ctx.redis, update_id, chat_id): return`. **Behaviour-preserving refactor — keep the existing `bot_redis_dedup_unavailable` / `bot_replay_skipped` structlog event names verbatim.**

**Handler skeleton pattern** (modeled on `checkin_handler` lines 241-348):
```python
async def book_handler(
    update: Any,
    context: Any,
    ctx: HandlerContext,
) -> None:
    """ptb /book handler (BOT-01/02). Stateless — no ConversationHandler (D-40-03)."""
    bot = context.bot
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    if effective_user is None or effective_chat is None or update.message is None:
        return
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    chat_id: int = effective_chat.id
    tg_user_id: int = effective_user.id

    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    async with ctx.session_factory() as session:
        # 1. Resolve client by telegram_user_id via Protocol-slot (Phase 7 DEBT-06).
        # 2. Resolve active PT-package via register_active_pt_package_resolver.
        # 3. ctx.schedule_service.list_slots(session, SlotListQuery(
        #        trainer_id=pt_package.trainer_id, page=1, page_size=5,
        #        status=SlotStatus.ACTIVE,
        #    ))
        # 4. If any of steps 1-3 yields zero/None -> _BOT_BOOK_DENIED_DM (anti-oracle).
        # 5. Build InlineKeyboardMarkup, 1 button per row (D-40-07):
        #      label = f"{slot.start_time.astimezone(MOSCOW_TZ):%d.%m %H:%M} — {trainer.full_name}"
        #      callback_data = f"BK:{slot.id}"   # 39 bytes, < 64 limit
        # 6. ctx.sender.send_text_dm(bot, chat_id, "Выберите время:", reply_markup=...)
```

**Callback-handler skeleton** (`book_callback_handler` — same file, mirrors `checkin_handler` exception-class string-dispatch at lines 289-323):
```python
async def book_callback_handler(
    update: Any,
    context: Any,
    ctx: HandlerContext,
) -> None:
    """ptb /book callback (BOT-03). Regex r"^BK:[uuid]$" pre-filtered by ptb (D-40-09)."""
    query = update.callback_query
    if query is None or query.data is None:
        return
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    chat_id = query.message.chat.id if query.message else None
    if chat_id is None:
        return
    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    # Parse `BK:{uuid}` — regex on CallbackQueryHandler(pattern=...) already validated shape.
    raw = query.data
    if not raw.startswith("BK:"):
        logger.warning("book_callback_invalid_data", update_id=update_id, data_prefix=raw[:10])
        return
    slot_id = UUID(raw[3:])

    async with ctx.session_factory() as session:
        try:
            booking_response = await ctx.bookings_service.create_booking_via_bot(
                session,
                client_id=...,         # resolved via Phase 7 telegram resolver
                slot_id=slot_id,
                pt_package_id=...,     # resolved via Phase 33 active-pt-package resolver
            )
        except Exception as exc:
            # Anti-oracle D-40-10: EVERY error -> _BOT_BOOK_DENIED_DM (single string).
            cls_name = type(exc).__name__
            logger.warning(
                "book_callback_denied",
                update_id=update_id, chat_id=chat_id, error_class=cls_name,
            )
            await query.edit_message_text(_BOT_BOOK_DENIED_DM)
            return
        # Happy path. Service already committed + emitted booking_created.
        text = render_booking_confirmed_dm(
            client_name=..., trainer_name=..., slot_start_msk=...,
        )
        await query.edit_message_text(text)
```

**Russian DM string-dispatch pattern** (anti-oracle, mirrors `checkin_handler` lines 289-320):
- `cls_name = type(exc).__name__` — string-name dispatch (avoids the import-linter `integrations perp modules` violation).
- ALL 7 `create_booking_via_bot` exceptions (`SlotNotFoundError`, `SlotNotActiveError`, `BookingAlreadyExistsError`, `TrainerMismatchError`, `PtPackageNotActiveError`, `PtPackageExhaustedError`, `PtPackageExpiredBeforeSlotError`) map to the SAME `_BOT_BOOK_DENIED_DM` constant. NO branch-specific copy — that is the anti-oracle (C-12) invariant.

---

### 2. `apps/backend/app/workers/telegram_bot.py` — composition-root wiring of new HandlerContext fields + handler registration

**Analog:** same file, current `main()` body at lines 56-110.

**Module-level imports pattern** (lines 26-48 — current set):
```python
from app.core.dependencies import (
    register_active_membership_resolver,
    register_active_pt_package_resolver,
    register_client_by_telegram_resolver,
    register_slot_by_id_resolver,
    register_trainer_by_id_resolver,
)
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import (
    HandlerContext,
    checkin_handler,
    start_handler,
)
from app.modules.auth import telegram_service
from app.modules.clients import service as clients_service
from app.modules.memberships import service as memberships_service
from app.modules.pt_packages import service as pt_packages_service
from app.modules.schedule import service as schedule_service       # already imported (Phase 37 INFRA-33)
from app.modules.trainers import service as trainers_service
from app.modules.visits import service as visits_service
```
Phase 40 ADDS to the handler import block:
```python
from app.integrations.telegram.handlers import (
    HandlerContext,
    book_callback_handler,   # Phase 40 BOT-03
    book_handler,            # Phase 40 BOT-01/02
    checkin_handler,
    start_handler,
)
from app.modules.bookings import service as bookings_service   # Phase 40 D-40-04
```
(`schedule_service` is already imported — no new module-level import for it.)

**HandlerContext construction (REG-29-03 site)** (lines 99-105):
```python
ctx = HandlerContext(
    session_factory=sessionmaker,
    telegram_service=telegram_service,
    sender=telegram_sender,
    visits_service=visits_service,
    redis=redis,
    # Phase 40 APPEND (positional order matches NamedTuple field order):
    # bookings_service=bookings_service,
    # schedule_service=schedule_service,
)
```

**Handler registration** (lines 106-110):
```python
application = build_application(
    token=settings.telegram_bot_token.get_secret_value(),
    handlers=[("start", start_handler), ("checkin", checkin_handler)],
    ctx=ctx,
)
```
Phase 40 appends `("book", book_handler)` to that list. **NB:** `build_application` currently only accepts `(str, HandlerCallable)` tuples for `CommandHandler` (see `apps/backend/app/integrations/telegram/bot.py:46-83`). The `CallbackQueryHandler` needs either (a) a `build_application` signature widening to accept `("callback", pattern, handler)` shapes, or (b) post-build `application.add_handler(CallbackQueryHandler(...))` inside `main()`. **Planner picks one in 40-01 or 40-03.** D-40-02 + the existing factory shape favour adding the callback registration directly after `build_application` returns (one extra `application.add_handler(CallbackQueryHandler(pattern=r"^BK:...$", callback=_adapter))` line — keeps the factory API stable).

**Resolver registration block** (lines 68-81 — already complete for Phase 40):
```python
register_client_by_telegram_resolver(clients_service.resolve_client_by_telegram_user_id)
register_active_membership_resolver(memberships_service.resolve_active_membership_by_client)
register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)   # DEBT-06
register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)                     # INFRA-33
```
The two resolvers Phase 40 leans on (`active_pt_package` + `slot_by_id`) are already registered here (REG-29-03 already closed for v1.5). No new `register_*` calls in `workers/telegram_bot.py` for Phase 40.

---

### 3. `apps/backend/app/main.py` — composition-root wiring (NOT applicable for HandlerContext)

**Important nuance:** `app.main` does NOT construct `HandlerContext`. It only registers Protocol-slot resolvers (lines 199-216, which Phase 37 INFRA-33 already extended for v1.5). The CONTEXT.md "REG-29-03 double-wiring" claim about `HandlerContext` in `app/main.py:159-214` is **slightly mis-stated** — `app/main.py` shares the *resolver* registration burden with `workers/telegram_bot.py`, not the `HandlerContext` instance itself (which is unique to the worker process).

**Analog:** same file, lines 199-216 — Phase 37 INFRA-33 / D-37-06 carve-out:
```python
# Phase 37 INFRA-33 / D-37-06: eighth-tenth composition-root carve-outs —
# v1.5 schedule + bookings cross-module Protocol slots. Schedule slot
# resolver wired BOTH here AND in app/workers/telegram_bot.py (defensive
# double-wiring per REG-29-03 — the bot's Phase 40 /book handler consumes
# the resolver via bookings.service).
from app.modules.bookings import (
    service as bookings_service,
)
from app.modules.schedule import (
    service as schedule_service,
)

register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
register_booking_slot_restorer(schedule_service.restore_slot_to_active)
register_booking_completer(bookings_service.complete_booking)
```
Phase 40 **does NOT** need to add to `app/main.py` — every resolver that the bot needs is already double-wired. The "double-wiring" lesson applies to the worker file only (`app/workers/telegram_bot.py` needs the new 2 `HandlerContext` fields). Planner should treat the 40-01 plan touch on `app/main.py` as a **no-op verification step**, not an edit.

---

### 4. `apps/backend/app/modules/bookings/service.py` — APPEND `create_booking_via_bot`

**Twin analogs:**
- **In-module:** `create_booking(session, actor, data)` at lines 627-811 — 10-step UoW; SVC001-owning.
- **Cross-module precedent (v1.2 Phase 20 D-10):** `apps/backend/app/modules/visits/service.py:create_visit_self_checkin` lines 233-262 — the self-service split D-40-04 mirrors.

**v1.2 self-service split pattern** (`visits/service.py:233-262`):
```python
async def create_visit_self_checkin(
    session: AsyncSession,
    telegram_user_id: int,
    chat_id: int,
) -> tuple[VisitResponse, date]:
    """Bot path — Phase 20 imports this via HandlerContext.visits_service (D-10).

    Looks up Client by telegram_user_id via the resolver (D-02). On None,
    raises ClientNotLinkedError WITHOUT an audit emit — Phase 20 owns the
    `telegram_unknown_checkin` event (its own taxonomy addition). Phase 19
    does NOT emit any audit row for unknown-tg lookups (D-12).
    """
    del chat_id  # forward-compat
    client = await resolve_client_by_telegram_user_id(session, telegram_user_id)
    if client is None:
        raise ClientNotLinkedError("client_not_linked", fields=...)
    return await _create_visit_with_anti_fraud(
        session,
        client_id=client.id,
        channel="telegram_bot",        # ← locked literal for the bot path
        checked_in_by=None,            # ← no CurrentUser
        audit_actor_user_id=None,      # ← NULL actor; D-40-05 mirror
    )
```

**10-step UoW skeleton (mirror `create_booking` lines 627-811)** for Phase 40:
```python
async def create_booking_via_bot(
    session: AsyncSession,
    *,
    client_id: UUID,
    slot_id: UUID,
    pt_package_id: UUID,
) -> BookingResponse:
    """Telegram /book self-service entry — D-40-04.

    Same 10-step UoW as create_booking. Audit payload carries
    actor_role='telegram_bot' (locked literal in audit_payloads.py).
    Raises the same domain errors as create_booking — the bot handler maps
    every error class to _BOT_BOOK_DENIED_DM (anti-oracle C-12).
    """
    now_utc = datetime.now(UTC)

    # 1. Slot resolve + status guard (lines 677-689).
    slot = await resolve_slot_by_id(session, slot_id)
    if slot is None: raise SlotNotFoundError("slot_not_found")
    if slot.status != "active": raise SlotNotAvailableError("slot_not_available")
    if slot.start_time <= now_utc: raise SlotNotAvailableError("slot_not_available")

    # 2. Active PT-package resolve + id-match + exhausted guard (lines 691-702).
    pt_package = await get_active_pt_package(session, client_id)
    if pt_package is None: raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.id != pt_package_id: raise PtPackageNotActiveError(...)
    if pt_package.sessions_remaining <= 0: raise PtPackageExhaustedError(...)

    # 3. Trainer-mismatch guard (lines 704-710).
    pkg_trainer_id = getattr(pt_package, "trainer_id", None)
    if pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id:
        raise TrainerMismatchError("trainer_mismatch")

    # 4. Moscow-TZ validity-window guard (lines 712-720).
    if (
        pt_package.end_date is not None
        and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()
    ):
        raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")

    # 5. Predicate-gated cross-module slot active→booked UPDATE (lines 722-743).
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session, slot_id, from_status="active", to_status="booked",
    )
    if not slot_flipped:
        await session.refresh(slot, attribute_names=["status"])
        if slot.status == "booked": raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # 6. INSERT booking row — created_by_user_id=NULL (self-service; no actor).
    booking = await repository.insert_booking(
        session,
        slot_id=slot_id, client_id=client_id, pt_package_id=pt_package_id,
        created_by_user_id=None,    # ← NEW: bot path has no authenticated user
    )

    # 7. Flush + uq_bookings_slot_confirmed race translation (lines 763-769 verbatim).
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # 8. audit.emit — LITERAL strings for INFRA-11 AST gate (lines 774-785).
    await audit.emit(
        session,
        "booking_created",                # LITERAL — INFRA-11
        actor_user_id=None,               # ← NULL for telegram_bot path (D-40-05)
        resource_type="booking",          # LITERAL
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        client_id=str(booking.client_id),
        pt_package_id=str(booking.pt_package_id),
        actor_role="telegram_bot",        # LITERAL — D-40-05 new field
        # created_by_user_id intentionally omitted (NULL row path).
    )

    # 9. session.commit() — SVC001 gate.
    await session.commit()

    # 9.5/10. NO post-commit DM dispatch from the service — the BOT HANDLER edits
    # the inline keyboard message to BOOKING_CONFIRMED_DM after this returns
    # (D-40-10 / Phase 7 D-11 atomic-after-DM order: DB commit → message edit).
    # This is the ONE divergence from create_booking's flow at lines 790-805.

    await session.refresh(booking, attribute_names=["created_at", "updated_at"])
    return BookingResponse.model_validate(booking, from_attributes=True)
```

**Discipline invariants to preserve (locked, lines 13-27):**
- **SVC001 caller-owns-txn:** `await session.commit()` at the end (line 788 precedent).
- **INFRA-11 audit literal-string AST gate:** `"booking_created"`, `"booking"`, `"telegram_bot"` are all string literals at the `audit.emit()` callsite — no f-strings, no variables.
- **`extra="forbid"` on `BookingCreatedPayload`** — every kwarg in `audit.emit()` MUST match the schema field set verbatim. Plan 40-02 ships the schema relaxation in lock-step (see audit_payloads section below).

**Error class inventory** (`bookings/service.py` lines 106-186 — these are the 7 raised by `create_booking_via_bot`):
- `SlotNotFoundError(NotFoundError)` line 113
- `SlotNotAvailableError(ConflictError)` line 120
- `SlotAlreadyBookedError(ConflictError)` line 129
- `TrainerMismatchError(ConflictError)` line 139
- `PtPackageExhaustedError(ConflictError)` line 149
- `PtPackageNotActiveError(ConflictError)` line 158
- `PtPackageExpiredBeforeSlotError(ConflictError)` line 168

---

### 5. `apps/backend/app/core/audit_payloads.py` — `BookingCreatedPayload` extension (D-40-05)

**Analog:** same file, `BookingCreatedPayload` lines 376-391 (current schema), and the additive-extension pattern from `PtPackageCancelledPayload` lines 204-223 (Phase 33 D-33-10 — "LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry are untouched — only the per-event Pydantic model body grows").

**Current shape** (lines 376-391):
```python
class BookingCreatedPayload(BaseModel):
    """Payload schema for ("booking_created", "booking") — Phase 38 BOOK-02."""

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    slot_id: UUID
    client_id: UUID
    pt_package_id: UUID
    created_by_user_id: UUID
```

**Phase 40 relaxation** (additive — same pattern as `PtPackageCancelledPayload` adding `prior_status` in Phase 33):
```python
class BookingCreatedPayload(BaseModel):
    """Payload schema for ("booking_created", "booking") — Phase 38 BOOK-02.

    Phase 40 D-40-05 additive extension: `actor_role` Literal discriminates
    reception/owner (existing path) from telegram_bot (Phase 40 self-service
    via /book). `created_by_user_id` becomes Optional because the bot path
    has no authenticated user — NULL means "self-service via bot, see
    actor_role for channel".
    """

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    slot_id: UUID
    client_id: UUID
    pt_package_id: UUID
    created_by_user_id: UUID | None = None
    actor_role: Literal["reception", "owner", "telegram_bot"] = "reception"
```
Add `from typing import Literal` to the import block at top of file (currently only `from datetime import date, datetime` / `from uuid import UUID` / `from pydantic import BaseModel, ConfigDict, Field` are imported — Literal is new).

**Default values rationale:** `actor_role="reception"` default means existing `create_booking` callsites (lines 774-785 in `bookings/service.py`) need **not** add the kwarg explicitly — but the discipline of "every literal at callsite" (INFRA-11) means the planner SHOULD update both callsites in 40-02 to pass `actor_role="reception"` / `"telegram_bot"` explicitly so the AST gate sees a literal at every emit. **Decision:** planner adds the kwarg explicitly to both `create_booking` (Phase 38) and `create_booking_via_bot` (new) in plan 40-02 — preserves INFRA-11 explicitness.

**Registry unchanged** (lines 434+): `("booking_created", "booking"): BookingCreatedPayload` — same key, evolved schema body.

---

### 6. `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` — byte-stable regen (D-40-11)

**Analog:** Phase 35 commit `511cbf1` (single atomic commit holding both artifacts) + `apps/backend/scripts/export_openapi.py` runner.

**Runner pattern** (`scripts/export_openapi.py` lines 47-67):
```python
def main() -> int:
    # D-05: `.openapi()` is a sync property; lifespan never runs.
    spec = create_app().openapi()
    if "paths" not in spec:
        print("openapi() returned no 'paths' — FastAPI surface broken.", file=sys.stderr)
        return 1
    # D-06: byte-stable across macOS↔Linux.
    payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
    target.write_text(payload, encoding="utf-8")
    print(f"Wrote {target} ({len(payload)} bytes).")
    return 0
```
Byte-stability invariants (lines 13-14, locked):
- `indent=2, sort_keys=True, ensure_ascii=False, trailing newline`
- cwd-independent (`pathlib.Path(__file__).resolve().parents[1] / "openapi.json"`)
- No DB / Redis / Telegram touch (env vars backfilled at lines 31-42 with harmless placeholders).

**Frontend regen** runs from `packages/api-client/`:
```bash
pnpm --filter @sportzal/api-client codegen   # regenerates schema.d.ts from ../../apps/backend/openapi.json
```
(Workspace name is `@sportzal/api-client` per `packages/api-client/package.json`; the admin-web filter discrepancy noted in v1.4 verification log line 571 does NOT apply here.)

**Single-atomic-commit pattern** (Phase 35 `511cbf1`): both files in ONE commit so the two CI drift gates (`backend/openapi-drift` + `frontend/schema-drift`) flip green together. Splitting leaves the intermediate commit red on one of the two.

**Pre-regen baseline** (CONTEXT.md confirmed 2026-05-18):
- `apps/backend/openapi.json`: 5479 lines, 0 occurrences of `trainer-slots` / `bookings`.
- `packages/api-client/src/schema.d.ts`: 4086 lines, same frozen state.

---

### 7. `packages/api-client/src/schema.contract.test.ts` — APPEND +10 `AssertNonNever`

**Analog:** same file, v1.4 surface block at lines 80-200 (36 existing assertions).

**Helper pattern** (lines 14-21 — already in place):
```ts
/** Returns false if T resolves to never; true otherwise. */
type AssertNonNever<T> = [T] extends [never] ? false : true

/** Phase 21 D-21-2 conditional probe — present iff the path exists. */
type HasPath<P extends string> = P extends keyof paths ? true : false
```

**v1.4 surface structure to mirror** (lines 80-209 — sectioned by phase / domain):
```ts
// --- v1.4 surface (Phases 31-34, backend-only handoff) -----------------
// operationIds intentionally NOT pinned — see 35-CONTEXT D-35-07.
// ...
// --- v1.4 trainers (Phase 31) ---
type _TrainersListGet = AssertNonNever<paths['/api/v1/trainers']['get']>
type _TrainersListPost = AssertNonNever<paths['/api/v1/trainers']['post']>
// ...

// Static checks for v1.4 surface — each must resolve to true at compile time.
const _v14Checks: [
  _TrainersListGet,
  // ... 35 more entries
] = [true, true, /* ... */]
```

**Phase 40 APPEND block** (mirror the section-headed v1.4 layout), exact 10 entries locked in CONTEXT.md D-40-12 lines 201-225:
```ts
// --- v1.5 surface (Phase 40 HANDOFF-02) ---
type _TrainerSlotsListGet = AssertNonNever<paths['/api/v1/trainer-slots']['get']>
type _TrainerSlotsCreate = AssertNonNever<paths['/api/v1/trainer-slots']['post']>
type _TrainerSlotItemGet = AssertNonNever<paths['/api/v1/trainer-slots/{slot_id}']['get']>
type _TrainerSlotCancel = AssertNonNever<
  paths['/api/v1/trainer-slots/{slot_id}/cancel']['post']
>
type _BookingsCreate = AssertNonNever<paths['/api/v1/bookings']['post']>
type _BookingCancel = AssertNonNever<
  paths['/api/v1/bookings/{booking_id}/cancel']['post']
>
type _ClientBookingsList = AssertNonNever<
  paths['/api/v1/clients/{client_id}/bookings']['get']
>
type _PtPackagesSalePostBody = AssertNonNever<
  paths['/api/v1/pt-packages']['post']['requestBody']
>
type _PtSessionsRecordPostBody = AssertNonNever<
  paths['/api/v1/pt-sessions']['post']['requestBody']
>
type _TrainerSlotsListOkRealised = AssertNonNever<
  paths['/api/v1/trainer-slots']['get']['responses']['200']
>

const _v15Checks: [
  _TrainerSlotsListGet,
  _TrainerSlotsCreate,
  _TrainerSlotItemGet,
  _TrainerSlotCancel,
  _BookingsCreate,
  _BookingCancel,
  _ClientBookingsList,
  _PtPackagesSalePostBody,
  _PtSessionsRecordPostBody,
  _TrainerSlotsListOkRealised,
] = [true, true, true, true, true, true, true, true, true, true]
```

**Optional 11th probe** (CONTEXT.md D-40-12 line 227 — research finding): if `GET /api/v1/bookings/{booking_id}` exists in the regenerated `paths`, add:
```ts
type _BookingItemGet = AssertNonNever<paths['/api/v1/bookings/{booking_id}']['get']>
```
Otherwise omit (locked count is +10). Planner runs `grep -F "/bookings/{booking_id}" apps/backend/openapi.json` post-regen to decide.

---

### 8. `.planning/milestones/v1.5-VERIFICATION-LOG.md` + evidence directory

**Analog:** `.planning/milestones/v1.4-VERIFICATION-LOG.md` (702 lines, locked template per D-40-13).

**Locked section structure** (grep on v1.4 log):
```
YAML frontmatter (lines 1-499):
  phase, milestone, verified_started, verified, status, score,
  overrides_applied, overrides[], human_verification[], race_tests{},
  ci_gates{}, test_suites{}, deferred_items[], sign_off{}, hand_off{}
## Race tests          (line 500)
## CI gates            (line 533)
## admin-web canary    (line 561)
## Test suites         (line 573)
## Deferred items      (line 588)
## Handoff artifacts   (line 604)
## Hand-off            (line 616)
### Final disposition (operator `<email>`)   (line 621)
## Recipe (manual verification sweep)        (line 653)
```

**YAML frontmatter pattern** (lines 1-9):
```yaml
---
phase: 40-telegram-book-openapi-drift-gate-milestone-verification
milestone: v1.5
verified_started: <ISO-8601 Z>
verified: <ISO-8601 Z>
status: passed | failed
score: "<scenarios PASS>/<scenarios total> verified — <race tests>/<race tests total> + <ci gates>/<ci gates total>; <inline regressions>; <deferred items count> rolled to v1.9"
overrides_applied: <int>
overrides:
  - gap: REG-40-NN
    resolved_in: "<short SHA> — <commit subject line>"
    evidence: "<single-paragraph forensic root-cause + fix description>"
```

**Operator scenario block pattern** (lines 27-82 — repeat per scenario):
```yaml
human_verification:
  - test: "01 publish_slot_and_list"
    via: curl                              # D-40-13 vocabulary: curl | telegram | cron | ci
    expected: "POST /api/v1/trainer-slots → 201 + GET /api/v1/trainer-slots?trainer_id=... → 200 with new slot in items"
    actual: "POST → 201 Created (slot_id=...); GET → 200 with total=1, items[0].id matches."
    result: pass
    evidence: "see .planning/milestones/v1.5-verification-evidence/01_publish_slot_and_list.txt"
    notes: "Hermetic re-run: psql DELETE on trainer-slots WHERE trainer_id=... at script head."
```

**CI gates table pattern** (lines 533-545):
```markdown
## CI gates

| Gate                              | Result                  | Notes                                                                          |
|-----------------------------------|-------------------------|--------------------------------------------------------------------------------|
| `ruff check .`                    | pass                    | <delta from baseline>                                                          |
| `mypy --strict app`               | pass                    | <file count>                                                                   |
| `pytest -q`                       | <pass | informational_partial> | <pass>/<fail> (threshold 700 met). <defer roll-forward note>             |
| Drift — `openapi.json`            | pass                    | Phase 40 regen captured                                                        |
| Drift — `schema.d.ts`             | pass                    | Phase 40 regen captured                                                        |

**Gate ordering:** matches `.github/workflows/ci.yml` (ruff → mypy → pytest → drift-openapi → drift-schema_d_ts).
**GHA cross-link:** Operator confirms at `https://github.com/<repo>/actions` for HEAD `<commit-sha>`.
```

**Final disposition block** (lines 621-647 — sign-off): structurally identical for v1.5; substitute operator email + verbatim instruction transcript + sign-off timestamp.

**Evidence directory layout** (mirror `.planning/milestones/v1.4-verification-evidence/`):
```
v1.5-verification-evidence/
├── 01_publish_slot_and_list.txt        # curl HTTP transcripts (`*.txt` per v1.4 convention)
├── 02_book_via_reception.txt
├── 03_concurrent_same_slot.txt
├── 04_cancel_window_24h.txt
├── 05_refund_with_outstanding_booking.txt
├── 06_pt_session_completes_booking.txt
├── telegram/
│   ├── 01_happy_path_keyboard.png      # chat_ids redacted (D-40-15)
│   ├── 02_happy_path_confirmed.png
│   └── 03_anti_oracle_denied.png
├── crons/
│   ├── run_no_show.log                 # stdout + DB query output (D-40-16)
│   └── run_reminders.log
├── ci_ruff.txt
├── ci_mypy.txt
├── ci_pytest.txt
├── ci_drift.txt                        # both openapi + schema gates concatenated
├── ci_frontend_drift.txt               # NEW for v1.5 — frontend codegen gate
└── pytest_full.txt
```
v1.4 used `*.txt`; v1.5 keeps the same extension. Telegram PNGs live in `telegram/` subdir, cron logs in `crons/` subdir (CONTEXT.md D-40-16 specifies these paths explicitly).

**One-shot cron runner usage** (CONTEXT.md D-40-16):
- `apps/backend/scripts/run_no_show_cron_once.py` (Phase 39, shipped)
- `apps/backend/scripts/run_booking_reminders_once.py` (Phase 39, shipped)

Both are imported by 40-05 as runtime tools — Phase 40 writes NO new cron-runner code.

---

## Shared Patterns

### A. Anti-oracle DM (C-12)
**Source:** `apps/backend/app/modules/bookings/notifications.py:35` (the `_BOT_BOOK_DENIED_DM` constant) + dispatch precedent in `handlers.py:289-323` (`checkin_handler` collapses `ClientNotLinkedError` + `NoActiveMembershipError` to the same DM).
**Apply to:** `book_handler` (zero-slot path), `book_callback_handler` (all 7 booking-service exceptions).
```python
_BOT_BOOK_DENIED_DM: Final[str] = "Сейчас бронирование недоступно. Пожалуйста, свяжитесь с администратором — он подскажет ближайшее свободное время."  # NO placeholders
```
Discrimination is **only** in structlog WARNING (`error_class=cls_name`); user-facing string is byte-identical across all failure causes.

### B. String-name exception dispatch (integrations perp modules)
**Source:** `handlers.py:289-323`.
**Apply to:** `book_callback_handler`.
```python
except Exception as exc:
    cls_name = type(exc).__name__
    if cls_name == "SlotAlreadyBookedError": ...
```
Never `from app.modules.bookings.service import SlotAlreadyBookedError` — that crosses the `integrations perp modules` import-linter contract.

### C. Redis SET-NX-EX update-id dedup (D-20-3 fail-open)
**Source:** `handlers.py:264-280` (inlined currently; Phase 40 extracts to `_dedupe_update_id` helper per D-40-08).
**Apply to:** `book_handler`, `book_callback_handler`, and the existing `checkin_handler` (refactor consumer — behaviour-preserving).
Key prefix `sz:bot:update:{update_id}` TTL 1h; Redis error → proceed (DB UNIQUE is the real backstop).

### D. REG-29-03 defensive double-wiring
**Source:** `apps/backend/app/workers/telegram_bot.py:62-81` (the explanatory comment block).
**Apply to:** Plan 40-01 — verifying that every resolver the bot handlers touch is registered in BOTH `app/main.py` and `workers/telegram_bot.py`. Phase 40 needs no new registrations (Phase 37 INFRA-33 closed v1.5 wiring), but the regression test `test_handler_context_double_construction` ships in 40-01.

### E. NamedTuple field-order discipline (extension at END)
**Source:** `tests/integration/telegram_bot/test_handler_context_shape.py:21-32`.
**Apply to:** the 2 new `HandlerContext` fields. The order is part of the contract — positional construction in `workers/telegram_bot.py:99-105` depends on it. Phase 40 appends `bookings_service` + `schedule_service` AFTER `redis`, and the test extends `assert HandlerContext._fields == (...)` accordingly.

### F. SVC001 caller-owns-txn + INFRA-11 audit literal-string gate
**Source:** `bookings/service.py` lines 13-22 (discipline docstring) + audit.emit callsite lines 774-788.
**Apply to:** `create_booking_via_bot`. End with `await session.commit()`; every kwarg key + string value in `audit.emit()` is a literal at the callsite. UUIDs stringified via `str(...)` per D-38-17 / Pitfall 13.

### G. additive Pydantic schema extension (Phase 33 D-33-10 pattern)
**Source:** `audit_payloads.py:204-223` (`PtPackageCancelledPayload` grew `prior_status` additively without disturbing `LOCKED_AUDIT_EVENTS` or `AUDIT_PAYLOAD_SCHEMAS`).
**Apply to:** `BookingCreatedPayload` D-40-05 relaxation. Only the model body grows; registry and frozenset are unchanged.

### H. Byte-stable JSON dump (OpenAPI artifact)
**Source:** `scripts/export_openapi.py:60` — `json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`.
**Apply to:** Plan 40-04 runs the runner verbatim; no algorithm changes. Drift gate compares bytes.

### I. YAML-fronted verification log
**Source:** `.planning/milestones/v1.4-VERIFICATION-LOG.md` lines 1-499 (frontmatter) + sections at lines 500-647.
**Apply to:** `v1.5-VERIFICATION-LOG.md`. Mirror byte-for-byte structure; substitute v1.5 content. Operator sign-off at `### Final disposition (operator <email>)`.

---

## No Analog Found

None — every Phase 40 deliverable has a precedent in the codebase (Phase 7 / Phase 20 / Phase 33 / Phase 35 / Phase 37 / Phase 38 / Phase 39). The only **new** pattern is `Literal[...]` in `audit_payloads.py` (D-40-05) — the file currently has zero `Literal` annotations, so the planner introduces this syntactic element fresh. The semantic precedent is `PtPackageCancelledPayload.prior_status` (Phase 33 D-33-10) which carries the same "additive extension to an existing locked payload" discipline.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/integrations/telegram/` (handlers.py, bot.py, sender)
- `apps/backend/app/workers/telegram_bot.py`
- `apps/backend/app/modules/{bookings,visits,schedule}/service.py` + `bookings/notifications.py`
- `apps/backend/app/core/audit_payloads.py`
- `apps/backend/app/main.py`
- `apps/backend/scripts/export_openapi.py`
- `packages/api-client/src/schema.contract.test.ts`
- `.planning/milestones/v1.4-VERIFICATION-LOG.md` + `v1.4-verification-evidence/`
- `apps/backend/tests/integration/telegram_bot/` (4 test files for Phase 7/20 test-fixture patterns)

**Files scanned:** 14
**Pattern extraction date:** 2026-05-18
