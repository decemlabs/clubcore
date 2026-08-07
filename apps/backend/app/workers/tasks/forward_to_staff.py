"""ARQ task: forward_to_staff — Phase 93 BRDG-01.

Per D-42-07 (module renders, worker transports): this worker file MUST NOT
import ``app.modules.*`` — workers⊥modules contract. All data needed to
render the staff DM (client name, phone, message body, object_key) is
passed as primitive kwargs from the messaging router at enqueue time
(cloudpickle-safe per D-42-16).

Behaviour:
- When ``settings.staff_telegram_chat_id`` is None: log + return "skipped"
  (bridge disabled, client send already succeeded).
- Text-only message: render DM via ``sender.send_text_dm`` to staff chat.
- Photo attachment: stream bytes from storage via ``ctx["storage"].open_stream``
  then call ``sender.send_photo`` with the concatenated bytes + caption.
- On SendResult.ok: write Redis chat_forwarding_log anchor
  ``cc:messaging:tg_msg:{tg_message_id}`` → JSON {thread_id, client_id},
  TTL 7 days (604800 s). Plan 02's reply handler consumes this anchor.
- On SendResult not ok: log warning, write NO Redis key (stale anchor is
  worse than absent), return "failed".

ARQ ctx keys required:
  - "redis"       : redis.asyncio.Redis — for chat_forwarding_log SET
  - "storage"     : Storage — for photo bytes when attachment present
  - "bot"         : telegram.Bot — outbound Telegram client (wired in on_startup)
  - "sessionmaker": not used here; present in ctx per ARQ convention

ARQ config (D-42-13): per-enqueue ``_max_tries=2, _expires=20`` from
the messaging router (mirrors dispatch_email convention).
"""

from __future__ import annotations

import json
from typing import Any, Final

import structlog

from app.core.config import get_settings
from app.integrations.telegram import sender as telegram_sender

# NOTE: import ONLY from app.integrations.* and app.core.* — never from
# app.modules.* (workers⊥modules contract; D-42-07 / workers/__init__.py:1-21)

_log: Final = structlog.get_logger("workers.tasks.forward_to_staff")

# Telegram transport hard limits (WR-01 / WR-02). The messaging body cap (4000)
# was chosen for the PWA UI, not the Telegram transport, so the rendered DM
# (identity header + body) can exceed these. We truncate the rendered text to
# fit; for photo captions the remainder is delivered as a follow-up text DM so
# nothing is silently dropped.
_TG_TEXT_LIMIT: Final = 4096  # sendMessage hard limit
_TG_CAPTION_LIMIT: Final = 1024  # send_photo caption hard limit
_TRUNCATION_MARK: Final = "…"

# Russian DM template — concise identity header for single-gym operator.
_DM_TEMPLATE = "Новое сообщение от клиента\nИмя: {client_name}\nТелефон: {client_phone}\n\n{body}"  # noqa: RUF001


def _render_dm(client_name: str, client_phone: str, body: str) -> str:
    """Render the staff-facing DM body with client identity + message."""
    return _DM_TEMPLATE.format(
        client_name=client_name,
        client_phone=client_phone,
        body=body,
    )


def _truncate(text: str, limit: int) -> str:
    """Truncate ``text`` to ``limit`` chars, appending an ellipsis marker."""
    if len(text) <= limit:
        return text
    return text[: limit - len(_TRUNCATION_MARK)] + _TRUNCATION_MARK


async def forward_to_staff(
    ctx: dict[str, Any],
    *,
    client_id: str,
    message_id: str,
    thread_id: str,
    body: str,
    client_name: str,
    client_phone: str,
    attachment_id: str | None = None,
    object_key: str | None = None,
) -> str:
    """Forward a client message to the staff Telegram DM/group chat.

    All args are primitives (str | None) — cloudpickle-safe (D-42-16).
    Returns "skipped" when bridge is disabled, "sent" on success, "failed"
    on Telegram transport error.
    """
    settings = get_settings()
    staff_chat_id = settings.staff_telegram_chat_id

    if staff_chat_id is None:
        _log.info(
            "telegram_bridge_disabled",
            reason="STAFF_TELEGRAM_CHAT_ID not set — forward_to_staff is a no-op",
            message_id=message_id,
        )
        return "skipped"

    bot = ctx["bot"]
    redis = ctx["redis"]
    caption = _render_dm(client_name, client_phone, body)

    if attachment_id is not None and object_key is not None:
        # Photo attachment: stream from storage, forward as inline image.
        storage = ctx["storage"]
        chunks: list[bytes] = []
        async for chunk in storage.open_stream(object_key):
            chunks.append(chunk)
        photo_bytes = b"".join(chunks)
        # WR-01: Telegram photo captions are capped at 1024 chars. Send a
        # truncated caption with the photo, then deliver the FULL rendered DM
        # as a follow-up text message so the staff never miss content the
        # client believes was delivered (the client message is already
        # committed + acknowledged).
        caption_for_photo = _truncate(caption, _TG_CAPTION_LIMIT)
        result = await telegram_sender.send_photo(
            bot, staff_chat_id, photo_bytes, caption=caption_for_photo
        )
        if result.ok and len(caption) > _TG_CAPTION_LIMIT:
            await telegram_sender.send_text_dm(
                bot, staff_chat_id, _truncate(caption, _TG_TEXT_LIMIT)
            )
    else:
        # Text-only message. WR-02: the rendered DM (header + up-to-4000-char
        # body) can exceed Telegram's 4096-char sendMessage limit, so truncate.
        result = await telegram_sender.send_text_dm(
            bot, staff_chat_id, _truncate(caption, _TG_TEXT_LIMIT)
        )

    if result.ok and result.message_id is not None:
        # Write chat_forwarding_log anchor for Plan 02's reply routing.
        anchor_key = f"cc:messaging:tg_msg:{result.message_id}"
        mapping = json.dumps({"thread_id": thread_id, "client_id": client_id})
        await redis.set(anchor_key, mapping, ex=604800)  # 7 days TTL
        _log.info(
            "client_message_forwarded",
            message_id=message_id,
            thread_id=thread_id,
            client_id=client_id,
            tg_message_id=result.message_id,
            has_photo=attachment_id is not None,
        )
        return "sent"
    elif result.ok:
        # Send succeeded but no message_id returned — should not happen with PTB.
        _log.warning(
            "forward_to_staff_no_tg_message_id",
            message_id=message_id,
        )
        return "sent"
    else:
        _log.warning(
            "forward_to_staff_failed",
            message_id=message_id,
            blocked=result.blocked,
            error=result.error,
        )
        return "failed"
