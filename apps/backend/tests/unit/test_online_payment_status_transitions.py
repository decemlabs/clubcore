"""Phase 50 D-50-15 / WH-04 — declarative FSM constant tests.

Asserts ONLINE_PAYMENT_STATUS_TRANSITIONS is a MappingProxyType keyed by
STATUS_* literals with frozenset edges matching D-50-15:
  pending → {succeeded, canceled};  succeeded/canceled = terminal.

Mirrors the MEMBERSHIP_STATUS_TRANSITIONS contract (Phase 16 / Phase 24) and
is consumed by app/api/v1/_internal/yookassa/handlers.py:_assert_can_transition
(Plan 50-04).
"""

from __future__ import annotations

from types import MappingProxyType


def test_online_payment_status_transitions_importable() -> None:
    from app.modules.online_payments.constants import ONLINE_PAYMENT_STATUS_TRANSITIONS  # noqa: F401


def test_pending_edges_to_succeeded_and_canceled() -> None:
    from app.modules.online_payments.constants import (
        ONLINE_PAYMENT_STATUS_TRANSITIONS,
        STATUS_CANCELED,
        STATUS_PENDING,
        STATUS_SUCCEEDED,
    )

    assert ONLINE_PAYMENT_STATUS_TRANSITIONS[STATUS_PENDING] == frozenset(
        {STATUS_SUCCEEDED, STATUS_CANCELED}
    )


def test_succeeded_is_terminal() -> None:
    from app.modules.online_payments.constants import (
        ONLINE_PAYMENT_STATUS_TRANSITIONS,
        STATUS_SUCCEEDED,
    )

    assert ONLINE_PAYMENT_STATUS_TRANSITIONS[STATUS_SUCCEEDED] == frozenset()


def test_canceled_is_terminal() -> None:
    from app.modules.online_payments.constants import (
        ONLINE_PAYMENT_STATUS_TRANSITIONS,
        STATUS_CANCELED,
    )

    assert ONLINE_PAYMENT_STATUS_TRANSITIONS[STATUS_CANCELED] == frozenset()


def test_constant_is_mapping_proxy_immutable() -> None:
    from app.modules.online_payments.constants import ONLINE_PAYMENT_STATUS_TRANSITIONS

    assert isinstance(ONLINE_PAYMENT_STATUS_TRANSITIONS, MappingProxyType)


def test_constant_listed_in_dunder_all() -> None:
    from app.modules.online_payments import constants

    assert "ONLINE_PAYMENT_STATUS_TRANSITIONS" in constants.__all__
