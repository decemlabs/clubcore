"""Phase 37 INFRA-30 — BOOKING_STATUS_TRANSITIONS constants tests.

The _assert_can_transition guard lands in Phase 38 alongside bookings/service.py
(mirrors v1.3/v1.4 precedent at app/modules/pt_packages/service.py:184-197).
This file pins ONLY the declarative matrix contents + immutability.
"""
from types import MappingProxyType

import pytest

from app.modules.bookings.constants import BOOKING_STATUS_TRANSITIONS


def test_booking_status_transitions_is_mappingproxy() -> None:
    """D-37-04: BOOKING_STATUS_TRANSITIONS is a MappingProxyType (read-only)."""
    assert isinstance(BOOKING_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        BOOKING_STATUS_TRANSITIONS["confirmed"] = frozenset()  # type: ignore[index]


def test_booking_status_transitions_contents() -> None:
    """C-04: confirmed → {cancelled, no_show, completed}; other states terminal."""
    assert BOOKING_STATUS_TRANSITIONS["confirmed"] == frozenset(
        {"cancelled", "no_show", "completed"}
    )
    assert BOOKING_STATUS_TRANSITIONS["cancelled"] == frozenset()
    assert BOOKING_STATUS_TRANSITIONS["no_show"] == frozenset()
    assert BOOKING_STATUS_TRANSITIONS["completed"] == frozenset()
    assert set(BOOKING_STATUS_TRANSITIONS.keys()) == {
        "confirmed",
        "cancelled",
        "no_show",
        "completed",
    }


def test_booking_status_transitions_count_3_legal_from_confirmed() -> None:
    """INFRA-30: enumerates exactly 3 legal transitions from confirmed."""
    assert len(BOOKING_STATUS_TRANSITIONS["confirmed"]) == 3


def test_booking_status_transitions_terminal_states() -> None:
    """All non-confirmed states are terminal (Q3 SUMMARY: no_show has no reverse in v1.5)."""
    for terminal in ("cancelled", "no_show", "completed"):
        assert len(BOOKING_STATUS_TRANSITIONS[terminal]) == 0
