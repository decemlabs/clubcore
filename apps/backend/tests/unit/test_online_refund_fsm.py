"""Phase 51 D-51-07 / REFUND-01 — declarative FSM constant tests.

Asserts ONLINE_REFUND_STATUS_TRANSITIONS is a MappingProxyType keyed by
STATUS_* literals with frozenset edges matching D-51-07:
  pending → {succeeded, canceled};  succeeded/canceled = terminal.

Mirrors ``test_online_payment_status_transitions.py`` (Phase 50 D-50-15
analog). Consumed by the refund webhook + poll-cron transition guards
(Plans 51-07 / 51-09) and the POST refund endpoint (Plan 51-08).
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.modules.online_refunds import constants
from app.modules.online_refunds.constants import (
    ONLINE_REFUND_STATUS_TRANSITIONS,
    STATUS_CANCELED,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
)


def test_online_refund_status_transitions_importable() -> None:
    assert ONLINE_REFUND_STATUS_TRANSITIONS is not None


def test_keys_are_the_three_status_literals() -> None:
    assert set(ONLINE_REFUND_STATUS_TRANSITIONS.keys()) == {
        STATUS_PENDING,
        STATUS_SUCCEEDED,
        STATUS_CANCELED,
    }


def test_pending_edges_to_succeeded_and_canceled() -> None:
    assert ONLINE_REFUND_STATUS_TRANSITIONS[STATUS_PENDING] == frozenset(
        {STATUS_SUCCEEDED, STATUS_CANCELED}
    )


def test_succeeded_is_terminal() -> None:
    assert ONLINE_REFUND_STATUS_TRANSITIONS[STATUS_SUCCEEDED] == frozenset()


def test_canceled_is_terminal() -> None:
    assert ONLINE_REFUND_STATUS_TRANSITIONS[STATUS_CANCELED] == frozenset()


def test_constant_is_mapping_proxy_immutable() -> None:
    assert isinstance(ONLINE_REFUND_STATUS_TRANSITIONS, MappingProxyType)


def test_mapping_proxy_rejects_assignment() -> None:
    """Locks the read-only contract (MappingProxyType wrap is in place)."""
    with pytest.raises(TypeError):
        ONLINE_REFUND_STATUS_TRANSITIONS[STATUS_PENDING] = frozenset()  # type: ignore[index]


def test_constant_listed_in_dunder_all() -> None:
    assert "ONLINE_REFUND_STATUS_TRANSITIONS" in constants.__all__
