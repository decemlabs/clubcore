"""Unit tests for the PaymentRecorder Protocol widening (Phase 50 Plan 50-03 Blocker #2).

Phase 32 declared ``PaymentRecorder.__call__`` with ``audit_actor: CurrentUser``
and ``received_by_user_id: UUID`` as REQUIRED kwargs. The ЮKassa webhook
flow (Plan 50-04) is anonymous — no CurrentUser, no operator UUID. Plan
50-03 widens BOTH kwargs to ``... | None = None`` (option b in the blocker
register). Existing in-person sale callers (memberships/service.py:739-747
and the analog in pt_packages/service.py) continue to pass non-None values;
backward compatibility is preserved because the new defaults are additive.

These tests use ``inspect.signature`` to assert the structural shape so any
future refactor that drops the Optional cannot land green.
"""

from __future__ import annotations

import inspect
import typing
from types import NoneType
from typing import Union, get_type_hints
from uuid import UUID

from app.core.dependencies import CurrentUser, PaymentRecorder


def _annotation_includes_none(annotation: object) -> bool:
    """Return True iff the annotation is ``T | None`` / ``Optional[T]`` / ``Union[T, None]``."""
    origin = typing.get_origin(annotation)
    if origin is Union or origin is type(None) or origin is typing.Union:
        return type(None) in typing.get_args(annotation)
    # Python 3.10+ X | Y syntax resolves to types.UnionType at runtime
    try:
        from types import UnionType
    except ImportError:
        UnionType = None  # type: ignore[assignment]
    if UnionType is not None and isinstance(annotation, UnionType):
        return NoneType in typing.get_args(annotation)
    return False


def test_payment_recorder_audit_actor_is_optional() -> None:
    hints = get_type_hints(PaymentRecorder.__call__)
    assert "audit_actor" in hints
    assert _annotation_includes_none(hints["audit_actor"]), (
        "audit_actor must be widened to CurrentUser | None (Blocker #2); "
        "got " + repr(hints["audit_actor"])
    )


def test_payment_recorder_received_by_user_id_is_optional() -> None:
    hints = get_type_hints(PaymentRecorder.__call__)
    assert "received_by_user_id" in hints
    assert _annotation_includes_none(hints["received_by_user_id"]), (
        "received_by_user_id must be widened to UUID | None (Blocker #2); "
        "got " + repr(hints["received_by_user_id"])
    )


def test_payment_recorder_kwargs_have_optional_defaults() -> None:
    params = inspect.signature(PaymentRecorder.__call__).parameters
    assert params["audit_actor"].default is None, (
        "audit_actor default must be None for additive backward-compat"
    )
    assert params["received_by_user_id"].default is None, (
        "received_by_user_id default must be None for additive backward-compat"
    )


def test_payment_recorder_protocol_preserves_existing_kwargs() -> None:
    params = inspect.signature(PaymentRecorder.__call__).parameters
    for required in ("subject_kind", "subject_id", "amount_kopecks", "method"):
        assert required in params, (
            f"PaymentRecorder Protocol must still expose `{required}` kwarg"
        )


def test_current_user_protocol_still_referenced() -> None:
    """Sanity: CurrentUser is still the non-None branch of the audit_actor union."""
    hints = get_type_hints(PaymentRecorder.__call__)
    args = typing.get_args(hints["audit_actor"])
    # CurrentUser may resolve to its Protocol class at runtime.
    assert any(a is CurrentUser for a in args), (
        "audit_actor union must still include CurrentUser; got args=" + repr(args)
    )
