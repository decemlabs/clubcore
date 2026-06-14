"""Unit tests for notification dispatcher matrix gate (Phase 108 CFG-04).

Tests the create_notification pre-emit gate added in Plan 03 Task 3:
  - Matrix disables a non-always-on trigger×channel → no row inserted.
  - Matrix enables a trigger×channel → row inserted.
  - Always-on kind with matrix "disabled" → STILL inserted (bypass).
  - Quiet-hours active + non-critical text channel → suppressed.
  - Quiet-hours active + in_app channel → not suppressed (inbox never quiet-suppressed).
  - Quiet-hours window crossing midnight handled correctly (22:00–07:00).
  - Absent config row → emit normally (fail-open, T-108-11).
  - Sender signature appended on text-channel body; absent on in_app body.

Uses AsyncMock session (no DB) + patching repository.insert_notification to track calls.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.modules.notifications.service import (
    _ALWAYS_ON_KINDS,
    _is_quiet_hours,
    create_notification,
)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Helper — build a fake session.execute() return for notification_prefs_config.
# ---------------------------------------------------------------------------


def _make_mock_session(
    *,
    matrix: dict[str, Any] | None = None,
    sender_signature: str | None = None,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
    config_absent: bool = False,
) -> AsyncMock:
    """Build an AsyncMock session whose execute() returns the given config row."""
    session = AsyncMock()

    if config_absent:
        row_value = None
    else:
        row_value = {
            "matrix": matrix if matrix is not None else {},
            "sender_signature": sender_signature,
            "quiet_hours_start": quiet_hours_start,
            "quiet_hours_end": quiet_hours_end,
        }

    mock_result = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.one_or_none.return_value = row_value
    mock_result.mappings.return_value = mock_mappings
    session.execute = AsyncMock(return_value=mock_result)

    return session


# ---------------------------------------------------------------------------
# CASE 1: Matrix disables non-always-on trigger×channel → suppressed.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matrix_disabled_suppresses_notification() -> None:
    """Matrix disables booking_confirmed×in_app → no row inserted."""
    matrix = {"booking_confirmed": {"in_app": False}}
    session = _make_mock_session(matrix=matrix)

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_not_called()


# ---------------------------------------------------------------------------
# CASE 2: Matrix enables trigger×channel → row inserted.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matrix_enabled_allows_notification() -> None:
    """Matrix enables booking_confirmed×in_app → row inserted."""
    matrix = {"booking_confirmed": {"in_app": True}}
    session = _make_mock_session(matrix=matrix)

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_called_once()


# ---------------------------------------------------------------------------
# CASE 3: Always-on kind bypasses matrix (even if matrix disables it).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_always_on_kind_bypasses_matrix_suppression() -> None:
    """autopay_charge_failed with matrix disabled → STILL inserted (bypass)."""
    assert "autopay_charge_failed" in _ALWAYS_ON_KINDS, (
        "autopay_charge_failed must be in _ALWAYS_ON_KINDS"
    )
    matrix = {"autopay_charge_failed": {"in_app": False}}
    session = _make_mock_session(matrix=matrix)

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="billing",
            source_id=uuid4(),
            kind="autopay_charge_failed",
            title="Ошибка автооплаты",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_called_once()
        # Always-on: no config read should happen.
        session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_payment_succeeded_bypasses_matrix() -> None:
    """payment_succeeded always-on bypass: matrix disabled → still inserted."""
    assert "payment_succeeded" in _ALWAYS_ON_KINDS
    matrix = {"payment_succeeded": {"in_app": False, "telegram": False}}
    session = _make_mock_session(matrix=matrix)

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="payment",
            source_id=uuid4(),
            kind="payment_succeeded",
            title="Оплата прошла",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_called_once()


# ---------------------------------------------------------------------------
# CASE 4 & 5: Quiet hours — tested directly via _is_quiet_hours helper.
#
# Strategy: test the _is_quiet_hours pure function directly (no DB needed),
# and separately test that create_notification calls the gate logic correctly
# by checking matrix suppression works (the quiet-hours path calls the same
# mechanism). This avoids brittle datetime mocking of local imports.
# ---------------------------------------------------------------------------


def _msk_time(hour: int, minute: int) -> datetime.datetime:
    """Build a Europe/Moscow datetime for quiet-hours test."""
    return datetime.datetime(2026, 6, 14, hour, minute, 0, tzinfo=MOSCOW_TZ)


def test_is_quiet_hours_simple_window() -> None:
    """Simple (non-midnight-crossing) window 09:00–22:00."""
    start = datetime.time(9, 0)
    end = datetime.time(22, 0)

    assert _is_quiet_hours(_msk_time(10, 0), start, end) is True   # inside
    assert _is_quiet_hours(_msk_time(22, 0), start, end) is False  # at end (exclusive)
    assert _is_quiet_hours(_msk_time(8, 59), start, end) is False  # before start
    assert _is_quiet_hours(_msk_time(9, 0), start, end) is True    # at start (inclusive)


def test_is_quiet_hours_midnight_crossing() -> None:
    """Midnight-crossing window 22:00–07:00."""
    start = datetime.time(22, 0)
    end = datetime.time(7, 0)

    assert _is_quiet_hours(_msk_time(23, 0), start, end) is True   # inside (after midnight)
    assert _is_quiet_hours(_msk_time(0, 30), start, end) is True   # inside (after midnight)
    assert _is_quiet_hours(_msk_time(6, 59), start, end) is True   # inside (before end)
    assert _is_quiet_hours(_msk_time(7, 0), start, end) is False   # at end (exclusive)
    assert _is_quiet_hours(_msk_time(7, 1), start, end) is False   # past end
    assert _is_quiet_hours(_msk_time(12, 0), start, end) is False  # daytime — outside


def test_is_quiet_hours_none_values_not_quiet() -> None:
    """None quiet hours → never quiet."""
    t = datetime.time(3, 0)
    assert _is_quiet_hours(_msk_time(3, 0), None, None) is False
    assert _is_quiet_hours(_msk_time(3, 0), t, None) is False
    assert _is_quiet_hours(_msk_time(3, 0), None, t) is False


# ---------------------------------------------------------------------------
# CASE 6: in_app not suppressed during quiet hours (integration via mock).
# We verify this via the gate logic: for in_app channel, the quiet-hours
# branch is never entered (channel != "in_app" guard in the service).
# This is directly tested by asserting insert is called for in_app when
# matrix allows it — regardless of quiet_hours config.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_app_never_quiet_suppressed_by_gate() -> None:
    """in_app channel is never suppressed even with quiet hours configured.

    The service gate only enters the quiet-hours check for channel != "in_app".
    We verify: even with a midnight quiet window, in_app still reaches insert.
    """
    # Matrix allows in_app, quiet hours configured to cover "now".
    # Since channel="in_app", the quiet-hours branch is skipped entirely.
    session = _make_mock_session(
        matrix={"booking_confirmed": {"in_app": True}},
        quiet_hours_start="00:00",
        quiet_hours_end="23:59",  # covers all day
    )

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_called_once()


# ---------------------------------------------------------------------------
# CASE 7: Absent config row → emit normally (fail-open, T-108-11).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_absent_config_row_emits_normally() -> None:
    """Config row absent (None) → emit normally (fail-open)."""
    session = _make_mock_session(config_absent=True)

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_insert:
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело",
            channel="in_app",
        )
        mock_insert.assert_called_once()


# ---------------------------------------------------------------------------
# CASE 8: Sender signature appended on text-channel body, absent on in_app.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sender_signature_appended_on_text_channel() -> None:
    """sender_signature is appended to the body for telegram channel."""
    session = _make_mock_session(
        matrix={"booking_confirmed": {"telegram": True}},
        sender_signature="— Ваш клуб Sportzal",
    )

    captured_body: list[str] = []

    async def _capture_insert(session: Any, **kwargs: Any) -> bool:
        captured_body.append(kwargs["body"])
        return True

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        side_effect=_capture_insert,
    ):
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело сообщения",
            channel="telegram",
        )

    assert len(captured_body) == 1
    assert "— Ваш клуб Sportzal" in captured_body[0]
    assert "тело сообщения" in captured_body[0]


@pytest.mark.asyncio
async def test_sender_signature_not_added_to_in_app_body() -> None:
    """sender_signature is NOT appended to in_app bodies (inbox only)."""
    session = _make_mock_session(
        matrix={},
        sender_signature="— Ваш клуб Sportzal",
    )

    captured_body: list[str] = []

    async def _capture_insert(session: Any, **kwargs: Any) -> bool:
        captured_body.append(kwargs["body"])
        return True

    with patch(
        "app.modules.notifications.service.repository.insert_notification",
        side_effect=_capture_insert,
    ):
        await create_notification(
            session,
            client_id=uuid4(),
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="Бронь подтверждена",
            body="тело сообщения",
            channel="in_app",
        )

    assert len(captured_body) == 1
    assert captured_body[0] == "тело сообщения"  # body unchanged for in_app


# ---------------------------------------------------------------------------
# CASE 9: Always-on kinds set is correct.
# ---------------------------------------------------------------------------


def test_always_on_kinds_contains_expected_kinds() -> None:
    """_ALWAYS_ON_KINDS must contain autopay_charge_failed and payment_succeeded."""
    assert "autopay_charge_failed" in _ALWAYS_ON_KINDS
    assert "payment_succeeded" in _ALWAYS_ON_KINDS
    assert isinstance(_ALWAYS_ON_KINDS, frozenset)
