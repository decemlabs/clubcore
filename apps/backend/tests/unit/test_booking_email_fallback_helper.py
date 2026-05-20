"""Unit tests for ``app.modules.bookings.notifications.enqueue_booking_email_fallback``.

Phase 45 Plan 45-08 Task 1 — TDD RED gate. Pins the helper contract:

  - 4 literal ``template_id`` branches (one per booking ``kind``):
    confirmed / cancelled_by_client / cancelled_by_owner / reminder_24h.
  - REMINDER_24H requires ``slot_date``; the 3 lifecycle kinds do not.
  - Unknown kind → ``ValueError``.
  - Returns a freshly-minted ``audit_correlation_id`` (UUID).

The AST gate at ``tests/unit/test_locked_email_templates_ast.py:42-46``
enforces literal ``template_id="EMAIL_BOOKING_..."`` strings statically;
this test focuses on the per-kind dispatch shape via a recording spy.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.core import dependencies as deps_mod
from app.core.dependencies import register_email_dispatcher


class _RecordingEmailDispatcher:
    """Spy satisfying the Phase 41 D-41-24 EmailDispatcher Protocol."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.calls.append(
            {
                "template_id": template_id,
                "to": to,
                "audit_correlation_id": audit_correlation_id,
                **template_vars,
            }
        )


@pytest.fixture
def recorder() -> _RecordingEmailDispatcher:
    prior = deps_mod._email_dispatcher
    rec = _RecordingEmailDispatcher()
    register_email_dispatcher(rec)
    try:
        yield rec
    finally:
        if prior is not None:
            register_email_dispatcher(prior)
        else:
            deps_mod._email_dispatcher = None


@pytest.mark.asyncio
async def test_enqueue_confirmed_fanouts_EMAIL_BOOKING_CONFIRMED(  # noqa: N802 -- upper-case literal pinning
    recorder: _RecordingEmailDispatcher,
) -> None:
    from app.modules.bookings.notifications import enqueue_booking_email_fallback

    aci = await enqueue_booking_email_fallback(
        kind="confirmed",
        client_email="client@example.com",
        trainer_name="Алексей Иванов",
        slot_start_msk="завтра в 19:00",
    )

    assert isinstance(aci, UUID)
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["template_id"] == "EMAIL_BOOKING_CONFIRMED"
    assert call["to"] == "client@example.com"
    assert call["audit_correlation_id"] == aci
    assert call["trainer_name"] == "Алексей Иванов"
    assert call["slot_start_msk"] == "завтра в 19:00"


@pytest.mark.asyncio
async def test_enqueue_cancelled_by_client_fanouts_EMAIL_BOOKING_CANCELLED_BY_CLIENT(  # noqa: N802 -- upper-case literal pinning
    recorder: _RecordingEmailDispatcher,
) -> None:
    from app.modules.bookings.notifications import enqueue_booking_email_fallback

    aci = await enqueue_booking_email_fallback(
        kind="cancelled_by_client",
        client_email="c2@example.com",
        trainer_name="Тренер",
        slot_start_msk="16 мая в 10:00",
    )

    assert isinstance(aci, UUID)
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["template_id"] == "EMAIL_BOOKING_CANCELLED_BY_CLIENT"


@pytest.mark.asyncio
async def test_enqueue_cancelled_by_owner_fanouts_EMAIL_BOOKING_CANCELLED_BY_OWNER(  # noqa: N802 -- upper-case literal pinning
    recorder: _RecordingEmailDispatcher,
) -> None:
    from app.modules.bookings.notifications import enqueue_booking_email_fallback

    aci = await enqueue_booking_email_fallback(
        kind="cancelled_by_owner",
        client_email="c3@example.com",
        trainer_name="Тренер",
        slot_start_msk="17 мая в 11:00",
    )

    assert isinstance(aci, UUID)
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["template_id"] == "EMAIL_BOOKING_CANCELLED_BY_OWNER"


@pytest.mark.asyncio
async def test_enqueue_reminder_24h_fanouts_EMAIL_BOOKING_REMINDER_24H_with_slot_date(  # noqa: N802 -- upper-case literal pinning
    recorder: _RecordingEmailDispatcher,
) -> None:
    from app.modules.bookings.notifications import enqueue_booking_email_fallback

    aci = await enqueue_booking_email_fallback(
        kind="reminder_24h",
        client_email="c4@example.com",
        trainer_name="Тренер",
        slot_start_msk="19:00",
        slot_date="16 мая",
    )

    assert isinstance(aci, UUID)
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["template_id"] == "EMAIL_BOOKING_REMINDER_24H"
    assert call["slot_date"] == "16 мая"


@pytest.mark.asyncio
async def test_enqueue_reminder_24h_missing_slot_date_raises(
    recorder: _RecordingEmailDispatcher,
) -> None:
    from app.modules.bookings.notifications import enqueue_booking_email_fallback

    with pytest.raises(ValueError, match="slot_date"):
        await enqueue_booking_email_fallback(
            kind="reminder_24h",
            client_email="c5@example.com",
            trainer_name="Тренер",
            slot_start_msk="19:00",
        )
    assert recorder.calls == []
