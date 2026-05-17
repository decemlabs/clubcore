"""Tests for v1.5 audit payload schemas (Phase 37 INFRA-25 / C-06).

Covers:
  - The 5 new Pydantic v2 payload schemas (extra='forbid' round-trip + reject).
  - The additive `booking_id: UUID | None = None` extension on the existing
    `PtSessionRecordedPayload` (back-compat preserved for v1.4 callsites in
    apps/backend/app/modules/pt_sessions/service.py).
  - The 5 new entries in `AUDIT_PAYLOAD_SCHEMAS` registry (lookup-by-tuple).

Mirrors PATTERNS.md §8 shape (apps/backend/tests/unit/test_schemas.py:56,90 for
the Pydantic extra-forbid round-trip precedent).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    BookingCancelledPayload,
    BookingCreatedPayload,
    BookingNoShowPayload,
    PtSessionRecordedPayload,
    SlotCancelledPayload,
    SlotPublishedPayload,
)

# ---------------------------------------------------------------------------
# SlotPublishedPayload — Phase 38 SLOT-01
# ---------------------------------------------------------------------------


def test_slot_published_payload_round_trip() -> None:
    """SlotPublishedPayload accepts the full v1.5 SLOT-01 kwarg set."""
    p = SlotPublishedPayload(
        slot_id=uuid4(),
        trainer_id=uuid4(),
        start_time="2026-05-20T10:00:00+03:00",
        end_time="2026-05-20T11:00:00+03:00",
        created_by_user_id=uuid4(),
    )
    assert isinstance(p.slot_id, UUID)
    assert p.start_time == "2026-05-20T10:00:00+03:00"


def test_slot_published_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        SlotPublishedPayload(  # type: ignore[call-arg]
            slot_id=uuid4(),
            trainer_id=uuid4(),
            start_time="2026-05-20T10:00:00+03:00",
            end_time="2026-05-20T11:00:00+03:00",
            created_by_user_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# SlotCancelledPayload — Phase 38 SLOT-07 / SLOT-09
# ---------------------------------------------------------------------------


def test_slot_cancelled_payload_round_trip() -> None:
    """SlotCancelledPayload accepts the SLOT-09 had_booking discriminator."""
    p = SlotCancelledPayload(
        slot_id=uuid4(),
        trainer_id=uuid4(),
        cancelled_by_user_id=uuid4(),
        cancel_reason="trainer unavailable",
        had_booking=True,
    )
    assert p.had_booking is True
    assert p.cancel_reason == "trainer unavailable"


def test_slot_cancelled_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        SlotCancelledPayload(  # type: ignore[call-arg]
            slot_id=uuid4(),
            trainer_id=uuid4(),
            cancelled_by_user_id=uuid4(),
            cancel_reason="trainer unavailable",
            had_booking=False,
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingCreatedPayload — Phase 38 BOOK-02
# ---------------------------------------------------------------------------


def test_booking_created_payload_round_trip() -> None:
    """BookingCreatedPayload accepts the full BOOK-02 kwarg set."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=uuid4(),
    )
    assert isinstance(p.booking_id, UUID)
    assert isinstance(p.pt_package_id, UUID)


def test_booking_created_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingCreatedPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            pt_package_id=uuid4(),
            created_by_user_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingCancelledPayload — Phase 38 BOOK-06
# ---------------------------------------------------------------------------


def test_booking_cancelled_payload_round_trip() -> None:
    """BookingCancelledPayload accepts the full BOOK-06 kwarg set."""
    p = BookingCancelledPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        cancelled_by_user_id=uuid4(),
        cancel_reason="client request",
    )
    assert p.cancel_reason == "client request"


def test_booking_cancelled_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingCancelledPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            cancelled_by_user_id=uuid4(),
            cancel_reason="client request",
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingNoShowPayload — Phase 39 CRON-01
# ---------------------------------------------------------------------------


def test_booking_no_show_payload_round_trip() -> None:
    """BookingNoShowPayload accepts the full CRON-01 kwarg set."""
    p = BookingNoShowPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        no_show_at="2026-05-20T11:15:00+03:00",
    )
    assert p.no_show_at == "2026-05-20T11:15:00+03:00"


def test_booking_no_show_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingNoShowPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            no_show_at="2026-05-20T11:15:00+03:00",
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# PtSessionRecordedPayload.booking_id — C-06 / D-37-05 additive extension
# ---------------------------------------------------------------------------


def _pt_session_base_kwargs() -> dict[str, object]:
    """v1.4 baseline kwargs for PtSessionRecordedPayload — back-compat anchor."""
    return {
        "pt_session_id": uuid4(),
        "pt_package_id": uuid4(),
        "client_id": uuid4(),
        "trainer_id": uuid4(),
        "trainer_name_snapshot": "Иван Иванов",
        "performed_at": "2026-05-20T10:00:00+03:00",
        "performed_by_user_id": uuid4(),
        "sessions_remaining_after": 4,
    }


def test_pt_session_recorded_payload_accepts_missing_booking_id() -> None:
    """C-06 / D-37-05 back-compat: every v1.4 emit callsite (no booking_id) keeps validating.

    `apps/backend/app/modules/pt_sessions/service.py:record_pt_session` is the
    pre-existing v1.4 caller; this test pins its kwarg shape.
    """
    p = PtSessionRecordedPayload(**_pt_session_base_kwargs())  # type: ignore[arg-type]
    assert p.booking_id is None


def test_pt_session_recorded_payload_accepts_booking_id_uuid() -> None:
    """C-06: completion of a booking flows via the EXISTING pt_session_recorded event."""
    booking_id = uuid4()
    p = PtSessionRecordedPayload(**_pt_session_base_kwargs(), booking_id=booking_id)  # type: ignore[arg-type]
    assert p.booking_id == booking_id


def test_pt_session_recorded_payload_still_rejects_extra_keys() -> None:
    """extra='forbid' must remain enforced after the booking_id additive extension."""
    with pytest.raises(ValidationError):
        PtSessionRecordedPayload(  # type: ignore[arg-type, call-arg]
            **_pt_session_base_kwargs(),
            booking_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# AUDIT_PAYLOAD_SCHEMAS registry — INFRA-25
# ---------------------------------------------------------------------------


def test_v15_payload_schemas_registered() -> None:
    """5 new v1.5 (event, resource_type) pairs map to their Pydantic schemas."""
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_published", "schedule_slot")] is SlotPublishedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_cancelled", "schedule_slot")] is SlotCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_created", "booking")] is BookingCreatedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_cancelled", "booking")] is BookingCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_no_show", "booking")] is BookingNoShowPayload
