"""Unit tests for the activator Protocol kwarg rename (Phase 50 Plan 50-03 Blocker #3).

Phase 49 declared ``MembershipActivator``/``PtPackageActivator`` Protocols
with kwarg ``membership_id`` / ``pt_package_id`` (UUID). The Phase 49 sell
flow never pre-INSERTs a Membership / PtPackage row; the activator must
CREATE the row from the OnlinePayment seed. To remove ambiguity Plan 50-03
RENAMES the Protocol kwarg to ``online_payment_id`` in BOTH activator
Protocols + the corresponding stub function signatures in
``memberships/service.py`` and ``pt_packages/service.py``.

These tests guard against accidental re-introduction of the old kwarg names
during refactoring. They use ``inspect.signature`` against the Protocol's
``__call__`` so the structural shape is asserted, not the concrete impl.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints
from uuid import UUID

from app.core.dependencies import MembershipActivator, PtPackageActivator


def test_membership_activator_protocol_uses_online_payment_id_kwarg() -> None:
    params = inspect.signature(MembershipActivator.__call__).parameters
    assert "online_payment_id" in params, (
        "Plan 50-03 renamed MembershipActivator kwarg to online_payment_id; "
        "got params=" + ", ".join(params)
    )
    assert "membership_id" not in params, "old kwarg `membership_id` must be removed (Blocker #3)"


def test_pt_package_activator_protocol_uses_online_payment_id_kwarg() -> None:
    params = inspect.signature(PtPackageActivator.__call__).parameters
    assert "online_payment_id" in params, (
        "Plan 50-03 renamed PtPackageActivator kwarg to online_payment_id; "
        "got params=" + ", ".join(params)
    )
    assert "pt_package_id" not in params, "old kwarg `pt_package_id` must be removed (Blocker #3)"


def test_membership_activator_kwarg_is_uuid_typed() -> None:
    hints = get_type_hints(MembershipActivator.__call__)
    assert hints.get("online_payment_id") is UUID, (
        "online_payment_id must be typed UUID; got " + repr(hints.get("online_payment_id"))
    )


def test_pt_package_activator_kwarg_is_uuid_typed() -> None:
    hints = get_type_hints(PtPackageActivator.__call__)
    assert hints.get("online_payment_id") is UUID, (
        "online_payment_id must be typed UUID; got " + repr(hints.get("online_payment_id"))
    )


def test_create_app_does_not_fail_on_protocol_rename() -> None:
    """Composition-root smoke (Blocker #7 — app/main.py must remain unedited)."""
    from app.main import create_app

    app = create_app()
    assert app is not None
