"""Unit tests for the membership state-machine guards (Phase 17 + Phase 25).

Tests `_assert_can_cancel`, `_assert_can_expire`, `_assert_can_freeze`, and
`_assert_can_unfreeze` directly against a SimpleNamespace stub — no DB,
no FastAPI, no fixtures. Per D-15 the guards read only `.status`; the stub
need not provide more.

Phase 25 D-25-15: 16-cell parametrize matrix (4 sources x 4 actions).
The 5 allowed cells:
  - ("active", "freeze", "ok")
  - ("active", "expire", "ok")
  - ("active", "cancel", "ok")
  - ("frozen", "unfreeze", "ok")
  - ("frozen", "cancel", "ok")
All other 11 cells expect `InvalidTransitionError(409, code='invalid_transition')`
with `fields={from_status, to_status}`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.exceptions import InvalidTransitionError
from app.modules.memberships.models import Membership
from app.modules.memberships.service import (
    _assert_can_cancel,
    _assert_can_expire,
    _assert_can_freeze,
    _assert_can_unfreeze,
)


def _stub_membership(*, status: str) -> Membership:
    """Stub object satisfying the guards' attribute access (.status only).

    The runtime uses `SimpleNamespace` and `cast` to `Membership` so the
    guards' static type signature is satisfied without instantiating a real
    SA ORM row (DB-free unit test).
    """
    return cast(Membership, SimpleNamespace(status=status))


# 16-cell parametrize matrix — keep order grouped by source status so a coverage
# diff in source surfaces gaps loudly. The `expect` column is the assertion shape.
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        # active source — 4 actions
        ("active", "freeze", "ok"),
        ("active", "unfreeze", "invalid_transition"),
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        # frozen source — 4 actions
        ("frozen", "freeze", "invalid_transition"),
        ("frozen", "unfreeze", "ok"),
        ("frozen", "cancel", "ok"),
        ("frozen", "expire", "invalid_transition"),
        # expired source — terminal; nothing allowed
        ("expired", "freeze", "invalid_transition"),
        ("expired", "unfreeze", "invalid_transition"),
        ("expired", "cancel", "invalid_transition"),
        ("expired", "expire", "invalid_transition"),
        # cancelled source — terminal; nothing allowed
        ("cancelled", "freeze", "invalid_transition"),
        ("cancelled", "unfreeze", "invalid_transition"),
        ("cancelled", "cancel", "invalid_transition"),
        ("cancelled", "expire", "invalid_transition"),
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    """Phase 25 D-25-15 — 16-cell matrix for membership lifecycle transitions."""
    membership = _stub_membership(status=from_status)

    # Dispatch table: action -> (target_status, guard_fn)
    if action == "freeze":
        target = "frozen"
        guard = _assert_can_freeze
    elif action == "unfreeze":
        target = "active"
        guard = _assert_can_unfreeze
    elif action == "cancel":
        target = "cancelled"
        guard = _assert_can_cancel
    elif action == "expire":
        target = "expired"
        guard = _assert_can_expire
    else:
        pytest.fail(f"unreachable: action={action}")

    if expect == "ok":
        # Allowed transition — guard must NOT raise.
        guard(membership)
        return

    # expect == "invalid_transition"
    with pytest.raises(InvalidTransitionError) as exc_info:
        guard(membership)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": from_status,
        "to_status": target,
    }


def test_central_helper_matches_per_helper_guards() -> None:
    """D-24-05: central `_assert_can_transition` agrees with the thin per-action wrappers."""
    from app.modules.memberships.service import _assert_can_transition

    # Allowed in Phase 25:
    _assert_can_transition(_stub_membership(status="active"), target="cancelled")
    _assert_can_transition(_stub_membership(status="active"), target="expired")
    _assert_can_transition(_stub_membership(status="active"), target="frozen")
    _assert_can_transition(_stub_membership(status="frozen"), target="active")
    _assert_can_transition(_stub_membership(status="frozen"), target="cancelled")

    # Disallowed (terminal sources):
    for src in ("expired", "cancelled"):
        for tgt in ("cancelled", "expired", "frozen", "active"):
            with pytest.raises(InvalidTransitionError):
                _assert_can_transition(_stub_membership(status=src), target=tgt)


def test_membership_status_transitions_constant_is_immutable() -> None:
    """D-24-03: MEMBERSHIP_STATUS_TRANSITIONS is a MappingProxyType (read-only)."""
    from types import MappingProxyType

    from app.modules.memberships.constants import MEMBERSHIP_STATUS_TRANSITIONS

    assert isinstance(MEMBERSHIP_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        MEMBERSHIP_STATUS_TRANSITIONS["active"] = frozenset()  # type: ignore[index]


def test_membership_status_transitions_phase25_contents() -> None:
    """D-25-14: Phase 25 contents.

    Freeze edges populated: `active → {expired, cancelled, frozen}` and
    `frozen → {active, cancelled}`. Terminal statuses (`expired`, `cancelled`)
    remain empty. Phase 26 may extend renewal-related edges.
    """
    from app.modules.memberships.constants import MEMBERSHIP_STATUS_TRANSITIONS

    assert MEMBERSHIP_STATUS_TRANSITIONS["active"] == frozenset(
        {"expired", "cancelled", "frozen"}
    )
    assert MEMBERSHIP_STATUS_TRANSITIONS["expired"] == frozenset()
    assert MEMBERSHIP_STATUS_TRANSITIONS["cancelled"] == frozenset()
    assert MEMBERSHIP_STATUS_TRANSITIONS["frozen"] == frozenset({"active", "cancelled"})
    assert set(MEMBERSHIP_STATUS_TRANSITIONS.keys()) == {
        "active",
        "expired",
        "cancelled",
        "frozen",
    }
