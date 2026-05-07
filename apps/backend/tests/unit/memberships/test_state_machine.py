"""Unit tests for the Phase 17 membership state-machine guards (TESTS-10, D-19).

Tests `_assert_can_cancel` and `_assert_can_expire` directly against a
SimpleNamespace stub — no DB, no FastAPI, no fixtures. Per D-15 the guards
read only `.status`; the stub need not provide more.

D-19: explicit 9-cell parametrize matrix
  rows by cols = {active, expired, cancelled} by {cancel, expire, create-self}

Allowed (2): active+cancel, active+expire — must NOT raise.
Disallowed (4): expired+cancel, expired+expire, cancelled+cancel,
                cancelled+expire — must raise InvalidTransitionError(409,
                code='invalid_transition') with fields={from_status, to_status}.
N/A (3): every status + create-self — creation is `void -> active`, not a
         state-machine transition; cells are returned-on early so the matrix
         stays at the documented 9-row count.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.exceptions import InvalidTransitionError
from app.modules.memberships.models import Membership
from app.modules.memberships.service import _assert_can_cancel, _assert_can_expire


def _stub_membership(*, status: str) -> Membership:
    """Stub object satisfying the guards' attribute access (.status only).

    The runtime uses `SimpleNamespace` and `cast` to `Membership` so the
    guards' static type signature is satisfied without instantiating a real
    SA ORM row (DB-free unit test).
    """
    return cast(Membership, SimpleNamespace(status=status))


# 9-cell parametrize matrix — keep order grouped by source status so a coverage
# diff in source surfaces gaps loudly. The `expect` column is the assertion shape.
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        # active row — both transitions allowed (active is the only source state).
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        ("active", "create-self", "n/a"),
        # expired row — terminal status; no further transitions.
        ("expired", "cancel", "invalid_transition"),
        ("expired", "expire", "invalid_transition"),
        ("expired", "create-self", "n/a"),
        # cancelled row — terminal status; no further transitions.
        ("cancelled", "cancel", "invalid_transition"),
        ("cancelled", "expire", "invalid_transition"),
        ("cancelled", "create-self", "n/a"),
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    """TESTS-10 / D-19 9-cell matrix for membership lifecycle transitions."""
    if expect == "n/a":
        # Creation is `void → active`, NOT a state-machine cell. The 3 N/A
        # rows keep the matrix at the documented 9-row coverage shape.
        return

    membership = _stub_membership(status=from_status)

    if expect == "ok":
        # Allowed transition — guard must NOT raise.
        if action == "cancel":
            _assert_can_cancel(membership)
        elif action == "expire":
            _assert_can_expire(membership)
        else:
            pytest.fail(f"unreachable: action={action} expect=ok")
        return

    # expect == "invalid_transition"
    expected_to = "cancelled" if action == "cancel" else "expired"
    with pytest.raises(InvalidTransitionError) as exc_info:
        if action == "cancel":
            _assert_can_cancel(membership)
        else:
            _assert_can_expire(membership)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": from_status,
        "to_status": expected_to,
    }
