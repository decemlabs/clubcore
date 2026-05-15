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


# ---------------------------------------------------------------------------
# Plan 33-03 EXTENSION: thin-wrapper denial groups (W6 ownership).
#
# The 16-cell matrix above is already exhaustive on the central
# ``_assert_can_transition`` guard. The wrapper-denial groups below pin the
# behaviour of the three thin wrappers individually so a future refactor that
# accidentally rewires a wrapper (e.g., ``_assert_can_expire`` delegating to
# ``target='cancelled'`` instead of ``target='expired'``) is surfaced loudly
# by per-wrapper coverage rather than masked by the central-guard tests.
#
# Each wrapper test asserts both the raise and the ``fields`` payload
# discriminator (``{from_status, to_status}``) so the exact failure mode
# is locked.
# ---------------------------------------------------------------------------


def test_assert_can_cancel_raises_from_cancelled() -> None:
    """D-33-04: ``_assert_can_cancel`` only fails from the terminal source.

    ``cancelled`` is the lone source where every target is disallowed; the
    wrapper raises with ``to_status='cancelled'`` (self-loop) and the
    discriminator payload matches the central-guard shape exactly.
    """
    pt_package = _stub_pt_package(status="cancelled")
    with pytest.raises(InvalidTransitionError) as exc_info:
        _assert_can_cancel(pt_package)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": "cancelled",
        "to_status": "cancelled",
    }


@pytest.mark.parametrize("from_status", ["exhausted", "expired", "cancelled"])
def test_assert_can_expire_raises_from_non_active(from_status: str) -> None:
    """D-33-04: ``_assert_can_expire`` is allowed ONLY from ``active`` source.

    All three non-active source states (exhausted, expired, cancelled) must
    surface ``invalid_transition`` — verifies the wrapper does not silently
    permit expire-of-terminal nor expire-of-exhausted (which would corrupt the
    pt_package_expired audit chain).
    """
    pt_package = _stub_pt_package(status=from_status)
    with pytest.raises(InvalidTransitionError) as exc_info:
        _assert_can_expire(pt_package)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": from_status,
        "to_status": "expired",
    }


@pytest.mark.parametrize("from_status", ["exhausted", "expired", "cancelled"])
def test_assert_can_exhaust_raises_from_non_active(from_status: str) -> None:
    """D-33-04: ``_assert_can_exhaust`` is allowed ONLY from ``active`` source.

    Phase 34 PT-session decrement to zero is the only legal callsite; the
    wrapper must refuse any other source so a sessions_remaining race that
    leaves a non-active row cannot re-flip to exhausted twice.
    """
    pt_package = _stub_pt_package(status=from_status)
    with pytest.raises(InvalidTransitionError) as exc_info:
        _assert_can_exhaust(pt_package)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {
        "from_status": from_status,
        "to_status": "exhausted",
    }


# ---------------------------------------------------------------------------
# Plan 33-03 EXTENSION: refund-of-{exhausted,expired} edge cases.
#
# The cancel + refund orchestrators (33-03) both call
# ``_assert_can_transition(target='cancelled')``. The 16-cell matrix already
# proves these transitions are allowed; the parametrized check below pins the
# happy-path call shape per source to keep wrapper + central-guard agreement
# explicit at the unit-test level (a regression that mis-rewires
# ``_assert_can_cancel`` to target='expired' would otherwise only surface in
# integration).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("from_status", ["active", "exhausted", "expired"])
def test_assert_can_cancel_allows_legal_sources(from_status: str) -> None:
    """D-33-04: ``_assert_can_cancel`` does NOT raise from any legal source.

    Cancel + refund both require target='cancelled'; refund-of-exhausted /
    refund-of-expired are explicit edge cases for the 33-03 refund flow
    (D-33-11). The wrapper must be a no-op for all three sources.
    """
    pt_package = _stub_pt_package(status=from_status)
    _assert_can_cancel(pt_package)  # no raise expected
