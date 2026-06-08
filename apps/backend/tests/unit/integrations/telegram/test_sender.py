"""Unit tests for ``app.integrations.telegram.sender.send_text_dm``.

Phase 40 WARNING-4 — ``send_text_dm`` adds a keyword-only ``reply_markup``
kwarg (default ``None``). These tests pin both the new kwarg-acceptance
behaviour AND the 3-arg positional back-compat that the Phase 7 / Phase 20
callers depend on.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.integrations.telegram.sender import send_text_dm


@pytest.mark.asyncio
async def test_send_text_dm_accepts_reply_markup_kwarg() -> None:
    """The new ``reply_markup`` kwarg is forwarded to ``bot.send_message``.

    Phase 93 BRDG-01: send_text_dm now returns ``sent.message_id`` from the
    sent Message object; the mock must return an object with a ``message_id``
    attribute (not None) for ``result.ok`` to be True.
    """
    sent_msg = SimpleNamespace(message_id=42)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=sent_msg))
    markup_sentinel: Any = SimpleNamespace(_sentinel="markup")
    result = await send_text_dm(bot, 123, "hi", reply_markup=markup_sentinel)
    assert result.ok is True
    assert result.message_id == 42
    bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="hi",
        reply_markup=markup_sentinel,
    )


@pytest.mark.asyncio
async def test_send_text_dm_three_arg_backward_compat() -> None:
    """Pre-Phase-40 callers that pass 3 positional args still work — the
    kwarg defaults to None and ``bot.send_message`` receives ``reply_markup=None``.

    Phase 93 BRDG-01: mock returns a Message-like object with message_id.
    """
    sent_msg = SimpleNamespace(message_id=99)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=sent_msg))
    result = await send_text_dm(bot, 456, "hi")
    assert result.ok is True
    assert result.message_id == 99
    bot.send_message.assert_awaited_once_with(
        chat_id=456,
        text="hi",
        reply_markup=None,
    )
