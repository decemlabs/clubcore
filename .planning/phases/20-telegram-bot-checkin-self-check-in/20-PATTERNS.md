# Phase 20: Telegram bot `/checkin` self check-in - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 11 (3 modified source + 1 importlinter + 7 test files)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/integrations/telegram/handlers.py` (MODIFY) | integration-handler | event-driven (ptb update) | `handlers.py:35-179` (`start_handler` itself — extension in same file) | exact (self) |
| `apps/backend/app/workers/telegram_bot.py` (MODIFY) | worker entrypoint | long-poll lifespan | `telegram_bot.py:54-67` (existing `main()` body — extension in same file) | exact (self) |
| `apps/backend/app/core/audit.py` (MODIFY) | core taxonomy | static-data (frozenset) | `audit.py:74-117` (existing `LOCKED_AUDIT_EVENTS`) | exact (self) |
| `apps/backend/.importlinter` (MODIFY) | config | import-graph contract | existing D-06 `workers → modules.auth.telegram_service` precedent | role-match (no whitelist syntax in current contracts) |
| `tests/integration/telegram_bot/__init__.py` (NEW) | test pkg marker | n/a | `tests/integration/telegram/__init__.py` | exact |
| `tests/integration/telegram_bot/test_checkin_handler.py` (NEW) | integration test | direct handler call | `tests/integration/telegram/test_handler_start.py` | exact |
| `tests/integration/telegram_bot/test_handler_context_shape.py` (NEW) | regression test | introspection | `test_handler_start.py:101-117` `_build_ctx` shape use | role-match |
| `tests/integration/telegram_bot/test_worker_handlers_registered.py` (NEW) | integration test | factory introspection | `bot.py:43-82` `build_application` (no existing analog test) | partial — bot.py is the SUT |
| `tests/unit/telegram_bot/__init__.py` (NEW) | test pkg marker | n/a | `tests/unit/visits/__init__.py` | exact |
| `tests/unit/telegram_bot/test_format_gym_hours.py` (NEW) | unit helper test | pure-function | `tests/unit/visits/` helpers (e.g. `_assert_within_gym_hours` style) | role-match |
| `tests/unit/telegram_bot/test_hash_telegram_user_id.py` (NEW) | unit helper test | pure-function | mirror of `_hash_token_for_log` (Phase 7); no existing dedicated test | role-match |

## Pattern Assignments

### `app/integrations/telegram/handlers.py` (MODIFY)

**Analog:** `apps/backend/app/integrations/telegram/handlers.py` (Phase 7) — extend in place; do NOT introduce a new file.

**HandlerContext extension pattern** (existing at `handlers.py:35-46`):
```python
class HandlerContext(NamedTuple):
    """Closure passed to every handler -- D-05.

    session_factory   : async_sessionmaker for opening DB sessions per update.
    telegram_service  : the app.modules.auth.telegram_service module
                        (workers->modules.auth, D-06).
    sender            : the app.integrations.telegram.sender module.
    """

    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
```
**Phase 20 extension:** add two fields (D-20-2 + D-10) AFTER `sender`. Field order matters because `telegram_bot.py:58-62` constructs `HandlerContext` positionally — keep existing 3 first, append `visits_service: ModuleType` and `redis: Redis`. NamedTuple defaults are not used here (every field is required).

```python
# Phase 20 additions — extend NamedTuple in same file:
from redis.asyncio import Redis  # NEW IMPORT (Phase 7 already imports `redis.asyncio` indirectly)

class HandlerContext(NamedTuple):
    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType  # D-10 (parallel to telegram_service D-06)
    redis: Redis                # D-20-2
```

**Locked DM constants pattern** (existing at `handlers.py:50-54`):
```python
# Russian copy -- locked per specifics line 253. Single-language by design.
_DM_STRANGER = (
    "Этот Telegram не привязан к аккаунту Sportzal. "
    "Обратитесь к администратору."
)
_DM_REPLAY = "Этот код уже использован, запросите новый."
```
**Phase 20 application:** add 4 module-level `_DM_CHECKIN_OK` / `_DM_NO_MEMBERSHIP` / `_DM_DUPLICATE` / `_DM_OUTSIDE_HOURS` constants verbatim per CONTEXT line 14-18. Cyrillic literals → add `# noqa: RUF001` comment ONLY if ruff complains (see `sender.py:18` precedent).

**Hash helper pattern** (existing at `handlers.py:68-74`):
```python
def _hash_token_for_log(raw_token: str) -> str:
    """sha256(raw_token) hex -- non-secret correlator for structlog events.

    Computed locally with stdlib so the handler does not need to reach into
    `ctx.telegram_service` private helpers (preserves integrations perp modules).
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
```
**Phase 20 mirror:** `_hash_telegram_user_id(tg_user_id: int) -> str` returns `hashlib.sha256(str(tg_user_id).encode("utf-8")).hexdigest()`. Used in `telegram_unknown_checkin` audit payload (D-20-10 PII minimization).

**Handler skeleton pattern — open session, call service, dispatch by exception name** (existing at `handlers.py:106-151`):
```python
async with ctx.session_factory() as session:
    try:
        user, raw_code, otp_row = await ctx.telegram_service.bind_and_issue(
            session, raw_token, chat_id, username,
        )
    except ctx.telegram_service.TelegramUnknownAccount:
        await audit_emit(
            session, "telegram_unknown_start",
            actor_user_id=None, resource_type="otp",
            username=username, chat_id=chat_id,
            deep_link_token_hash=deep_link_token_hash,
        )
        await ctx.sender.send_text_dm(bot, chat_id, _DM_STRANGER)
        return
    except Exception as exc:
        # dispatch by class name to avoid importing the exception classes
        # (integrations perp modules; we import them transitively via the service module).
        cls_name = type(exc).__name__
        if cls_name == "OtpAlreadyConsumed":
            await audit_emit(
                session, "telegram_replay_attempt",
                actor_user_id=None, resource_type="otp",
                chat_id=chat_id, deep_link_token_hash=deep_link_token_hash,
            )
            await ctx.sender.send_text_dm(bot, chat_id, _DM_REPLAY)
            return
        # other -- silent
        logger.warning("telegram_start_rejected", reason=cls_name, ...)
        return
```
**Phase 20 application:** `checkin_handler` body mirrors this string-name dispatch verbatim. Differences:
1. `start_handler` uses `except ctx.telegram_service.TelegramUnknownAccount:` (typed catch via the service-module attribute access) for ONE class. Phase 20 cannot do this for visits exceptions because Phase 19's exception classes live in `app.core.exceptions` (NOT in `app.modules.visits` — verified at `core/exceptions.py:170-227`), and `integrations → core.exceptions` is allowed by `.importlinter` (only `integrations → modules` is forbidden). **Decision pin: Phase 20 still uses string-name dispatch (D-20 CONTEXT line 26) for symmetry with `start_handler` and to keep handlers.py future-proof against any module-relocated exceptions.** A `cls_name = type(exc).__name__` ladder over `"NoActiveMembershipError"` / `"DuplicateCheckinError"` / `"OutsideGymHoursError"` / `"ClientNotLinkedError"` is the locked shape.
2. Handler does NOT call `session.commit()` after the success or rejection branches — Phase 19 service has already committed (`service.py:138, 159, 188, 206`). Handler ONLY commits on the `ClientNotLinkedError` branch (handler-owned audit emit per D-20-10).
3. `_global_error_handler` (`bot.py:32-40`) catches anything that escapes — re-raise on the "any other exception" branch (Phase 7 silent-warn precedent at `handlers.py:145-151` is reused for non-known visit exception classes; for entirely unknown excs, prefer re-raise so the polling-loop logger sees it).

**Defensive update-field guard** (existing at `handlers.py:88-92`):
```python
effective_user = update.effective_user
effective_chat = update.effective_chat
if effective_user is None or effective_chat is None or update.message is None:
    return
```
**Phase 20 application:** copy verbatim at top of `checkin_handler`. Add `update_id` extraction: `update_id = getattr(update, "update_id", None); if update_id is None: return`.

**Redis SET-NX-EX dedup pattern** — NO existing analog in `handlers.py` (Phase 7 OTP path uses DB-level `OtpAlreadyConsumed` instead of Redis dedup). Closest precedent is `redis-py.set(..., nx=True, ex=...)` per D-20-5 — verbatim spec from CONTEXT line 84. Wrapper:
```python
key = f"sz:bot:update:{update_id}"
try:
    set_result = await ctx.redis.set(key, "1", nx=True, ex=3600)
except Exception as exc:  # noqa: BLE001 — fail-open per D-20-3
    logger.warning("bot_redis_dedup_unavailable", update_id=update_id, chat_id=chat_id, error=str(exc))
    set_result = "OK"  # proceed to service call
if set_result is None:  # key existed — silent replay
    logger.debug("bot_replay_skipped", update_id=update_id, chat_id=chat_id)
    return
```
The structlog event names `bot_redis_dedup_unavailable` and `bot_replay_skipped` are NOT audit events (no `LOCKED_AUDIT_EVENTS` extension needed for these — they are pure structlog).

**Audit emit on handler-owned path pattern** (existing at `handlers.py:116-124`):
```python
await audit_emit(
    session,
    "telegram_unknown_start",
    actor_user_id=None,
    resource_type="otp",
    username=username,
    chat_id=chat_id,
    deep_link_token_hash=deep_link_token_hash,
)
```
**Phase 20 mirror for `ClientNotLinkedError`:**
```python
await audit_emit(
    session,
    "telegram_unknown_checkin",   # NEW LOCKED PAIR
    actor_user_id=None,
    resource_type="visit",        # D-20-10 (NOT 'otp' — visits-surface ops query)
    resource_id=None,
    chat_id=chat_id,
    telegram_user_id_hash=_hash_telegram_user_id(tg_user_id),
)
await session.commit()  # handler-owned commit (D-05/D-20-10)
await ctx.sender.send_text_dm(bot, chat_id, _DM_NO_MEMBERSHIP)  # anti-oracle (D-20-9)
```
**`audit_emit` import alias** (existing at `handlers.py:27`):
```python
from app.core.audit import emit as audit_emit
```
The Phase 15 AST taxonomy walker explicitly recognises this rebinding (`test_audit_taxonomy.py:43-44`); Phase 20 reuses the import as-is — no new import.

**`_format_gym_hours(exc) -> str` helper** — no existing analog. Spec from CONTEXT line 92:
```python
def _format_gym_hours(exc: Exception) -> str:
    """Format OutsideGymHoursError.fields as 'HH:MM–HH:MM' (U+2013 EN DASH).

    Strips trailing ':SS' from time.isoformat() output ('07:00:00' → '07:00').
    Defensive: raises RuntimeError if exc.fields is missing 'open'/'close'
    (Phase 19 service.py:99-100, 142 contract — load-bearing for D-20-8).
    """
    fields = getattr(exc, "fields", None) or {}
    try:
        open_t = fields["open"][:5]
        close_t = fields["close"][:5]
    except (KeyError, TypeError) as e:
        raise RuntimeError(
            "OutsideGymHoursError fields contract broken — Phase 19 regression"
        ) from e
    return f"{open_t}–{close_t}"  # U+2013 EN DASH per D-20-8
```

---

### `app/workers/telegram_bot.py` (MODIFY)

**Analog:** `apps/backend/app/workers/telegram_bot.py` itself (extend in place).

**Existing import + ctx construction + handlers list** (`telegram_bot.py:26-67`):
```python
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import HandlerContext, start_handler
from app.modules.auth import telegram_service  # D-06 relaxation
...
async with AsyncExitStack() as stack:
    _engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
    _redis = await stack.enter_async_context(redis_lifespan_manager())

    ctx = HandlerContext(
        session_factory=sessionmaker,
        telegram_service=telegram_service,
        sender=telegram_sender,
    )
    application = build_application(
        token=settings.telegram_bot_token.get_secret_value(),
        handlers=[("start", start_handler)],
        ctx=ctx,
    )
```
**Phase 20 modifications (per CONTEXT lines 32-35):**
1. Line 28: extend import → `from app.integrations.telegram.handlers import HandlerContext, start_handler, checkin_handler`.
2. Line 29: ADD a NEW import line directly under the existing D-06 line:
   ```python
   from app.modules.auth import telegram_service  # D-06 relaxation
   from app.modules.visits import service as visits_service  # D-10 relaxation
   ```
3. Line 56: rename `_redis` → `redis` (drop the leading underscore — it is now consumed, not just a held-open resource).
4. Lines 58-62: extend HandlerContext kwargs:
   ```python
   ctx = HandlerContext(
       session_factory=sessionmaker,
       telegram_service=telegram_service,
       sender=telegram_sender,
       visits_service=visits_service,  # NEW (D-10)
       redis=redis,                    # NEW (D-20-2)
   )
   ```
5. Line 65: extend handlers list → `handlers=[("start", start_handler), ("checkin", checkin_handler)]`.
6. Module docstring (lines 1-12): extend the D-06 paragraph to mention BOTH `auth.telegram_service` (D-06) AND `visits.service` (D-10).

---

### `app/core/audit.py` (MODIFY)

**Analog:** `apps/backend/app/core/audit.py` itself (frozenset extension only).

**Frozenset structure** (`audit.py:74-117`):
```python
LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # v1.1 (Phase 5/6/7/8) ...
        ("telegram_unknown_start", "otp"),
        ...
        # v1.2 (Phase 15 lock — emitted in Phases 16/17/19/20)
        ("visit_created", "visit"),
        ("visit_rejected_no_membership", "visit"),
        ("visit_rejected_duplicate", "visit"),
        ("visit_rejected_outside_hours", "visit"),
    }
)
```
**Phase 20 addition** (CONTEXT line 37):
- Add ONE entry inside the v1.2 block: `("telegram_unknown_checkin", "visit"),`.
- Update the count assertion in `tests/unit/test_audit_taxonomy.py:172` from `28` → `29`.
- Update the docstring inventory block (`audit.py:39-50`) under a new `## v1.2 (Phase 20 — bot self check-in unknown-tg)` line: `- telegram_unknown_checkin   {chat_id, telegram_user_id_hash}    # 'visit' (Phase 20 D-20-10)`.

---

### `apps/backend/.importlinter` (MODIFY — verify, possibly extend)

**Current contracts** (full file shown above): `core-not-depend-on-modules` (forbidden), `modules-independent` (independence), `integrations-not-depend-on-modules` (forbidden). **No existing `workers ⊥ modules` contract** — confirmed by reading `.importlinter` end-to-end. The Phase 7 D-06 import `app.workers.telegram_bot → app.modules.auth.telegram_service` (`telegram_bot.py:29`) does not violate any current contract because `app.workers` is not listed as a `source_modules` anywhere.

**Phase 20 verification action:** confirm running `lint-imports` after Phase 20 source changes still passes (no new contract needed, no `ignore_imports:` line needed). The CONTEXT line 39-41 caveat ("if the contract is whitelist-shaped") is moot — there is NO `workers ⊥ modules` contract. Document this finding in `20-02-PLAN.md`.

---

### `tests/integration/telegram_bot/test_checkin_handler.py` (NEW)

**Analog:** `apps/backend/tests/integration/telegram/test_handler_start.py` — copy structure verbatim.

**Imports + fixtures pattern** (`test_handler_start.py:16-58`):
```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.handlers import HandlerContext, checkin_handler  # NEW
from app.modules.auth import telegram_service
from app.modules.visits import service as visits_service  # NEW for ctx
from tests.conftest import StubTelegramSender


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)
```
The `_refresh_handler_logger` autouse fixture is REQUIRED (same root cause as Phase 7 — cached module-level logger; see `test_handler_start.py:40-58` docstring).

**Update / context double pattern** (`test_handler_start.py:80-98`):
```python
def _build_update(*, deep_link_token: str, username: str | None, chat_id: int) -> SimpleNamespace:
    eff_user = SimpleNamespace(id=chat_id, username=username, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(text=f"/start {deep_link_token}", chat=eff_chat, from_user=eff_user)
    return SimpleNamespace(effective_user=eff_user, effective_chat=eff_chat, message=message)
```
**Phase 20 adaptation:** add `update_id: int` to the SimpleNamespace, message text is `"/checkin"`. `effective_user.id` carries `telegram_user_id`. Example:
```python
def _build_update(*, telegram_user_id: int, chat_id: int, update_id: int) -> SimpleNamespace:
    eff_user = SimpleNamespace(id=telegram_user_id, username=None, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(text="/checkin", chat=eff_chat, from_user=eff_user)
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user, effective_chat=eff_chat, message=message,
    )
```

**HandlerContext build pattern** (`test_handler_start.py:101-117`):
```python
def _build_ctx(db_session: AsyncSession) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
    )
```
**Phase 20 adaptation:** extend with `visits_service` and `redis`:
```python
def _build_ctx(db_session: AsyncSession, redis_client: Any) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
        visits_service=visits_service,
        redis=redis_client,
    )
```

**Test case body pattern** (`test_handler_start.py:125-159`):
```python
async def test_handler_known_username_binds_and_dms(
    db_session: AsyncSession,
    known_user: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    update = _build_update(deep_link_token=raw_token, username=KNOWN_USERNAME, chat_id=KNOWN_CHAT_ID)
    ctx = _build_ctx(db_session)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await start_handler(update, context, ctx)

    # Sender called once with the 6-digit code.
    assert len(stub_telegram_sender.calls) == 1
    ...
```
**Phase 20 adaptation:** use `make_visit_setup` from `tests/integration/visits/conftest.py:180-246` (factory yielding `(client, membership)` with `telegram_user_id` populated) for the happy path. For redis, use `redis_clean` fixture (`tests/integration/visits/conftest.py:69-74`) which calls `flushdb()` — the real `app.state.redis` (single-process testcontainer redis) handles SET-NX-EX correctly. **Do not introduce `fakeredis`** — `redis_clean` proves SET-NX-EX semantics against real redis-py 5+.

**Gym-hours monkeypatch pattern** (`test_visits_self_checkin.py:50-59`):
```python
import app.modules.visits.service as svc_mod
from app.core.config import get_settings
from datetime import time

settings = get_settings()
monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)
```
**Phase 20 reuse:** copy verbatim into the happy-path / no-membership / duplicate / unknown-checkin tests. For the OutsideGymHoursError test, monkeypatch to a closed window (e.g. `time(0, 0)` / `time(0, 1)` so that `now_msk` is outside).

**Test cases needed (CONTEXT lines 44-50):**
1. `test_checkin_happy_path` — visit row + `visit_created` audit + `_DM_CHECKIN_OK` sent
2. `test_checkin_no_active_membership` — `_DM_NO_MEMBERSHIP` + `visit_rejected_no_membership` audit
3. `test_checkin_duplicate` — pre-seed today's visit, then call → `_DM_DUPLICATE` + `visit_rejected_duplicate` audit
4. `test_checkin_outside_hours` — closed-window monkeypatch → `_DM_OUTSIDE_HOURS` formatted with en-dash + `visit_rejected_outside_hours` audit
5. `test_checkin_client_not_linked` — telegram_user_id NOT in clients table → `_DM_NO_MEMBERSHIP` (anti-oracle) + `telegram_unknown_checkin` audit row (handler-emitted)
6. `test_checkin_replay_silent` — call handler twice with same `update_id`; second: no DM, no second visit, `bot_replay_skipped` structlog DEBUG
7. `test_checkin_redis_outage_fail_open` — monkeypatch `ctx.redis.set` to raise `redis.ConnectionError`; assert handler proceeds, `bot_redis_dedup_unavailable` WARN, visit row created

---

### `tests/integration/telegram_bot/test_handler_context_shape.py` (NEW)

**Analog:** none direct. Two-liner introspection test.

**Pattern:**
```python
from app.integrations.telegram.handlers import HandlerContext

def test_handler_context_has_all_phase_20_fields() -> None:
    """Regression guard: HandlerContext._fields must include visits_service + redis."""
    assert "visits_service" in HandlerContext._fields
    assert "redis" in HandlerContext._fields
    # Existing fields stay (don't drop on accident):
    for f in ("session_factory", "telegram_service", "sender"):
        assert f in HandlerContext._fields
```

---

### `tests/integration/telegram_bot/test_worker_handlers_registered.py` (NEW)

**Analog:** `apps/backend/app/integrations/telegram/bot.py:43-82` (the SUT). No existing test for `build_application`.

**Pattern — introspect ptb `Application.handlers`:**
```python
from typing import Any
from types import ModuleType
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import CommandHandler

from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import HandlerContext, checkin_handler, start_handler
from app.modules.auth import telegram_service
from app.modules.visits import service as visits_service


def test_worker_registers_start_and_checkin(db_session: AsyncSession, redis_clean: Any) -> None:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    ctx = HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
        visits_service=visits_service,
        redis=redis_clean,
    )
    app = build_application(
        token="dummy:token",  # ptb doesn't network on construction
        handlers=[("start", start_handler), ("checkin", checkin_handler)],
        ctx=ctx,
    )
    # ptb stores handlers under group 0 by default
    registered = [h for group in app.handlers.values() for h in group]
    cmd_names: set[str] = set()
    for h in registered:
        if isinstance(h, CommandHandler):
            cmd_names.update(h.commands)
    assert {"start", "checkin"} <= cmd_names
```

---

### `tests/unit/telegram_bot/test_format_gym_hours.py` (NEW)

**Analog:** existing `tests/unit/visits/` synchronous helper tests; pure-function pattern. No DB.

**Pattern:**
```python
import pytest

from app.core.exceptions import OutsideGymHoursError
from app.integrations.telegram.handlers import _format_gym_hours


def test_format_gym_hours_basic() -> None:
    exc = OutsideGymHoursError(
        "outside_gym_hours",
        fields={"open": "07:00:00", "close": "23:00:00"},
    )
    assert _format_gym_hours(exc) == "07:00–23:00"  # U+2013 EN DASH


def test_format_gym_hours_non_round() -> None:
    exc = OutsideGymHoursError(
        "outside_gym_hours",
        fields={"open": "07:30:00", "close": "22:45:00"},
    )
    assert _format_gym_hours(exc) == "07:30–22:45"


def test_format_gym_hours_missing_fields_raises() -> None:
    exc = OutsideGymHoursError("outside_gym_hours", fields={})
    with pytest.raises(RuntimeError, match="Phase 19 regression"):
        _format_gym_hours(exc)
```

---

### `tests/unit/telegram_bot/test_hash_telegram_user_id.py` (NEW)

**Analog:** mirror of Phase 7's `_hash_token_for_log` (no dedicated test exists). Pure stdlib hashlib.

**Pattern:**
```python
from app.integrations.telegram.handlers import _hash_telegram_user_id


def test_hash_is_stable() -> None:
    assert _hash_telegram_user_id(12345) == _hash_telegram_user_id(12345)


def test_different_inputs_produce_different_hashes() -> None:
    assert _hash_telegram_user_id(12345) != _hash_telegram_user_id(12346)


def test_hash_is_full_sha256_hex() -> None:
    h = _hash_telegram_user_id(12345)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
```

---

## Shared Patterns

### Audit emit (co-transactional)
**Source:** `apps/backend/app/core/audit.py:120-175`, callsite `apps/backend/app/integrations/telegram/handlers.py:116-124, 132-140`.
**Apply to:** `checkin_handler` ClientNotLinkedError branch ONLY (handler-owned emit). All other paths: Phase 19 service has already committed; handler is forbidden from `session.commit()` after a successful service call.
**Critical contract:** caller owns `await session.commit()` AFTER `audit_emit(...)`. The emit function does NOT flush or commit.

### String-name exception dispatch (integrations ⊥ modules)
**Source:** `handlers.py:127-151` (`type(exc).__name__` ladder).
**Apply to:** All four visit-rejection branches in `checkin_handler`. Even though `app.core.exceptions` (where the visit exceptions live) is import-allowed from integrations, the string-name dispatch is the LOCKED pattern (CONTEXT line 26 + Phase 7 D-04 precedent). Add a docstring comment on the dispatch ladder explaining D-20-9 anti-oracle reuse so a future contributor doesn't "fix" `ClientNotLinkedError` to a 5th honest-UX string.

### Locked code-constant DM strings (Russian-only, no i18n)
**Source:** `handlers.py:50-54` (`_DM_STRANGER` / `_DM_REPLAY`).
**Apply to:** All 4 new `_DM_CHECKIN_OK` / `_DM_NO_MEMBERSHIP` / `_DM_DUPLICATE` / `_DM_OUTSIDE_HOURS` constants. Module-level, all-caps with leading underscore, verbatim from REQUIREMENTS AUTH-TG-11. The `_DM_OUTSIDE_HOURS` is the ONLY string with format-interpolation (`{hours}`).

### Sender double (TEST-03)
**Source:** `apps/backend/tests/conftest.py:165-200` (`StubTelegramSender` + `stub_telegram_sender` fixture; both `send_otp_dm` and `send_text_dm` are monkeypatched).
**Apply to:** All `test_checkin_handler.py` cases — assert `stub_telegram_sender.text_calls == [(chat_id, expected_dm_string)]`. The Phase 20 happy path uses `send_text_dm` (NOT `send_otp_dm`); use `.text_calls` not `.calls`.

### SAVEPOINT-rolled `db_session` fixture
**Source:** `tests/conftest.py` (root) — provides per-test SAVEPOINT-isolated `AsyncSession`.
**Apply to:** All Phase 20 integration tests EXCEPT the worker-registration test, which doesn't touch DB. Phase 19's `db_session_real_commit` (`tests/integration/visits/conftest.py:251-286`) is NOT needed (no concurrent test in Phase 20).

### Defensive update-field guard
**Source:** `handlers.py:88-92`.
**Apply to:** Top of `checkin_handler` — bail silently on missing `effective_user`/`effective_chat`/`message`/`update_id`.

### Telegram-bot logger refresh fixture
**Source:** `test_handler_start.py:40-58` (`_refresh_handler_logger` autouse).
**Apply to:** Both `test_checkin_handler.py` and `test_worker_handlers_registered.py` (the latter only if it asserts on captured structlog events — likely not, but safer to add).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | | | All Phase 20 files have direct or near-direct analogs in Phase 7 / Phase 19 / Phase 15 codebase. |

The novel pieces (Redis SET-NX-EX dedup, `_format_gym_hours`, `_hash_telegram_user_id`) are pure standard-library / redis-py idioms whose specs are pinned by CONTEXT decisions and third-party docs (redis-py `Redis.set(nx=..., ex=...)`, `hashlib.sha256`).

## Metadata

**Analog search scope:**
- `apps/backend/app/integrations/telegram/` (handlers, sender, bot)
- `apps/backend/app/workers/` (telegram_bot)
- `apps/backend/app/core/` (audit, redis, exceptions, audit_models)
- `apps/backend/app/modules/visits/service.py` (consumer surface)
- `apps/backend/.importlinter` (contracts)
- `apps/backend/tests/integration/telegram/`, `tests/integration/visits/`, `tests/unit/`
- `apps/backend/tests/conftest.py` (StubTelegramSender + db_session fixtures)

**Files scanned:** 11

**Pattern extraction date:** 2026-05-08
