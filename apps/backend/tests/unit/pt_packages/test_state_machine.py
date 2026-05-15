"""Unit tests for the PT-package state-machine guards (Phase 33 D-33-04).

Tests ``_assert_can_transition``, ``_assert_can_cancel``, ``_assert_can_expire``,
and ``_assert_can_exhaust`` directly against a SimpleNamespace stub — no DB,
no FastAPI, no fixtures. The guards read only ``.status``; the stub need
not provide more.

D-33-04 transition matrix (4 sources x 4 actions = 16 cells):
  - active    → {exhausted, expired, cancelled}
  - exhausted → {cancelled}              (refund of exhausted)
  - expired   → {cancelled}              (refund of expired)
  - cancelled → ∅                        (terminal)

Allowed cells: 5 — (active, cancel/expire/exhaust), (exhausted, cancel),
(expired, cancel). All other 11 cells expect
``InvalidTransitionError(409, code='invalid_transition')`` with
``fields={from_status, to_status}``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.modules.pt_packages.models import PtPackage
from app.modules.pt_packages.service import (
    InvalidTransitionError,
    _assert_can_cancel,
    _assert_can_exhaust,
    _assert_can_expire,
    _assert_can_transition,
)


def _stub_pt_package(*, status: str) -> PtPackage:
    """Stub object satisfying the guards' attribute access (.status only).

    The runtime uses ``SimpleNamespace`` and ``cast`` to ``PtPackage`` so the
    guards' static type signature is satisfied without instantiating a real
    SA ORM row (DB-free unit test).
    """
    return cast(PtPackage, SimpleNamespace(status=status))


# 16-cell parametrize matrix — keep order grouped by source status so a coverage
# diff in source surfaces gaps loudly. The `expect` column is the assertion shape.
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        # active source — 4 actions
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        ("active", "exhaust", "ok"),
        ("active", "noop", "invalid_transition"),  # target='active' from active
        # exhausted source — refund-only path to cancelled
        ("exhausted", "cancel", "ok"),
        ("exhausted", "expire", "invalid_transition"),
        ("exhausted", "exhaust", "invalid_transition"),
        ("exhausted", "noop", "invalid_transition"),
        # expired source — refund-only path to cancelled
        ("expired", "cancel", "ok"),
        ("expired", "expire", "invalid_transition"),
        ("expired", "exhaust", "invalid_transition"),
        ("expired", "noop", "invalid_transition"),
        # cancelled source — terminal; nothing allowed
        ("cancelled", "cancel", "invalid_transition"),
        ("cancelled", "expire", "invalid_transition"),
        ("cancelled", "exhaust", "invalid_transition"),
        ("cancelled", "noop", "invalid_transition"),
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    """D-33-04 — 16-cell matrix for PT-package lifecycle transitions.

    The ``noop`` synthetic action targets ``status='active'`` from any source;
    no source state may transition TO active (the only path to active is via
    INSERT during sale). This proves the FSM has no rehydrate-from-terminal
    paths.
    """
    pt_package = _stub_pt_package(status=from_status)

    # Dispatch table: action -> (target_status, guard_fn or None for noop)
    if action == "cancel":
        target = "cancelled"
        guard = _assert_can_cancel
    elif action == "expire":
        target = "expired"
        guard = _assert_can_expire
    elif action == "exhaust":
        target = "exhausted"
        guard = _assert_can_exhaust
    elif action == "noop":
        # No wrapper for "→ active"; call the central guard directly.
        target = "active"
        guard = None
    else:
        pytest.fail(f"unreachable: action={action}")

    if expect == "ok":
        # Allowed transition — guard must NOT raise.
        assert guard is not None
        guard(pt_package)
        return

    # expect == "invalid_transition"
    with pytest.raises(InvalidTransitionError) as exc_info:
        if guard is None:
            _assert_can_transition(pt_package, target=target)
        else:
            guard(pt_package)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": from_status,
        "to_status": target,
    }


def test_central_helper_matches_per_action_guards() -> None:
    """D-33-04: central ``_assert_can_transition`` agrees with the per-action wrappers."""
    # Allowed cells per the FSM
    _assert_can_transition(_stub_pt_package(status="active"), target="cancelled")
    _assert_can_transition(_stub_pt_package(status="active"), target="expired")
    _assert_can_transition(_stub_pt_package(status="active"), target="exhausted")
    _assert_can_transition(_stub_pt_package(status="exhausted"), target="cancelled")
    _assert_can_transition(_stub_pt_package(status="expired"), target="cancelled")

    # Terminal sources reject every target
    for src in ("cancelled",):
        for tgt in ("active", "exhausted", "expired", "cancelled"):
            with pytest.raises(InvalidTransitionError):
                _assert_can_transition(_stub_pt_package(status=src), target=tgt)

    # exhausted source only allows cancelled
    for tgt in ("active", "exhausted", "expired"):
        with pytest.raises(InvalidTransitionError):
            _assert_can_transition(_stub_pt_package(status="exhausted"), target=tgt)

    # expired source only allows cancelled
    for tgt in ("active", "exhausted", "expired"):
        with pytest.raises(InvalidTransitionError):
            _assert_can_transition(_stub_pt_package(status="expired"), target=tgt)


def test_pt_package_status_transitions_constant_is_immutable() -> None:
    """D-33-04: PT_PACKAGE_STATUS_TRANSITIONS is a MappingProxyType (read-only)."""
    from types import MappingProxyType

    from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS

    assert isinstance(PT_PACKAGE_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        PT_PACKAGE_STATUS_TRANSITIONS["active"] = frozenset()  # type: ignore[index]


def test_pt_package_status_transitions_phase33_contents() -> None:
    """D-33-04: locked transition matrix exactly matches the spec.

    Active → 3 targets (exhausted, expired, cancelled).
    Exhausted → 1 target (cancelled).
    Expired → 1 target (cancelled).
    Cancelled → ∅ (terminal).
    """
    from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS

    assert PT_PACKAGE_STATUS_TRANSITIONS["active"] == frozenset(
        {"exhausted", "expired", "cancelled"}
    )
    assert PT_PACKAGE_STATUS_TRANSITIONS["exhausted"] == frozenset({"cancelled"})
    assert PT_PACKAGE_STATUS_TRANSITIONS["expired"] == frozenset({"cancelled"})
    assert PT_PACKAGE_STATUS_TRANSITIONS["cancelled"] == frozenset()
    assert set(PT_PACKAGE_STATUS_TRANSITIONS.keys()) == {
        "active",
        "exhausted",
        "expired",
        "cancelled",
    }
