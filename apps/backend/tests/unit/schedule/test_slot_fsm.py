"""Phase 37 INFRA-31 — SLOT_STATUS_TRANSITIONS constants tests.

The _assert_can_transition guard lands in Phase 38 alongside schedule/service.py
(mirrors v1.3/v1.4 precedent at app/modules/pt_packages/service.py:184-197).
This file pins ONLY the declarative matrix contents + immutability.
"""

from types import MappingProxyType

import pytest

from app.modules.schedule.constants import SLOT_STATUS_TRANSITIONS


def test_slot_status_transitions_is_mappingproxy() -> None:
    """D-37-04: SLOT_STATUS_TRANSITIONS is a MappingProxyType (read-only)."""
    assert isinstance(SLOT_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        SLOT_STATUS_TRANSITIONS["active"] = frozenset()  # type: ignore[index]


def test_slot_status_transitions_contents() -> None:
    """INFRA-31: locked transition matrix exactly matches the spec."""
    assert SLOT_STATUS_TRANSITIONS["active"] == frozenset({"booked", "cancelled"})
    assert SLOT_STATUS_TRANSITIONS["booked"] == frozenset({"active", "cancelled"})
    assert SLOT_STATUS_TRANSITIONS["cancelled"] == frozenset()
    assert set(SLOT_STATUS_TRANSITIONS.keys()) == {"active", "booked", "cancelled"}


def test_slot_status_transitions_terminal_states() -> None:
    """`cancelled` has no outgoing transitions (terminal per INFRA-31)."""
    assert len(SLOT_STATUS_TRANSITIONS["cancelled"]) == 0
