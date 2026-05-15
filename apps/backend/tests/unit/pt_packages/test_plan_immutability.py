"""Unit tests for the D-33-07 plan-immutability gate.

Tests ``_validate_immutability`` directly — a pure synchronous helper that
compares incoming ``PtPackagePlanUpdateRequest`` values against the current
``PtPackagePlan`` ORM row and raises ``FieldImmutableError(409)`` on any
mutation attempt to session_count / price_kopecks / validity_days.

No DB session needed — the function operates on in-memory objects.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.modules.pt_packages.models import PtPackagePlan
from app.modules.pt_packages.schemas import PtPackagePlanUpdateRequest
from app.modules.pt_packages.service import (
    FieldImmutableError,
    _validate_immutability,
)


def _stub_plan(
    *,
    name: str = "10 тренировок",
    session_count: int = 10,
    price_kopecks: int = 500000,
    validity_days: int | None = 30,
) -> PtPackagePlan:
    """In-memory PT-package plan stub with adjustable attribute values."""
    return cast(
        PtPackagePlan,
        SimpleNamespace(
            name=name,
            session_count=session_count,
            price_kopecks=price_kopecks,
            validity_days=validity_days,
        ),
    )


@pytest.mark.parametrize(
    ("field", "new_value", "current_value"),
    [
        ("session_count", 15, 10),
        ("session_count", 1, 10),
        ("price_kopecks", 600000, 500000),
        ("price_kopecks", 1, 500000),
        ("validity_days", 60, 30),
        ("validity_days", 1, 30),
    ],
)
def test_field_immutable_raises_409_field_immutable(
    field: str, new_value: int, current_value: int
) -> None:
    """D-33-07: mutating any of the 3 immutable fields raises FieldImmutableError.

    The error carries ``fields={'field': <field_name>}`` so admin-web can
    surface a precise message.
    """
    plan = _stub_plan(**{field: current_value})
    data = PtPackagePlanUpdateRequest(**{field: new_value})

    with pytest.raises(FieldImmutableError) as exc_info:
        _validate_immutability(plan, data)
    assert exc_info.value.code == "field_immutable"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {"field": field}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_count", 10),
        ("price_kopecks", 500000),
        ("validity_days", 30),
    ],
)
def test_field_immutable_same_value_is_no_op(field: str, value: int) -> None:
    """D-33-07: PATCH with a matching value (no real change) does NOT raise."""
    plan = _stub_plan()
    data = PtPackagePlanUpdateRequest(**{field: value})
    # Should not raise — matching value is a permitted no-op.
    _validate_immutability(plan, data)


def test_field_immutable_omitted_fields_are_no_op() -> None:
    """Empty PATCH body (all immutable fields omitted) is a permitted no-op."""
    plan = _stub_plan()
    data = PtPackagePlanUpdateRequest()  # all fields None
    # Should not raise.
    _validate_immutability(plan, data)


def test_field_immutable_name_only_change_is_no_op_for_gate() -> None:
    """Mutating ``name`` (mutable per D-33-07) does NOT trip the immutability gate.

    The gate only inspects session_count / price_kopecks / validity_days.
    """
    plan = _stub_plan()
    data = PtPackagePlanUpdateRequest(name="20 тренировок")
    # Should not raise — name is mutable.
    _validate_immutability(plan, data)


def test_field_immutable_first_field_short_circuits() -> None:
    """When multiple immutable fields all differ, the gate raises on the first one.

    D-33-07 order: session_count → price_kopecks → validity_days. The error
    payload should name session_count.
    """
    plan = _stub_plan()
    data = PtPackagePlanUpdateRequest(
        session_count=15,  # changed
        price_kopecks=600000,  # also changed — but should not be reached
        validity_days=60,  # also changed — but should not be reached
    )
    with pytest.raises(FieldImmutableError) as exc_info:
        _validate_immutability(plan, data)
    assert exc_info.value.fields == {"field": "session_count"}


def test_validity_days_null_to_int_attempt_raises() -> None:
    """Changing validity_days from NULL to a value (or vice versa) is immutable."""
    plan = _stub_plan(validity_days=None)
    data = PtPackagePlanUpdateRequest(validity_days=30)
    with pytest.raises(FieldImmutableError) as exc_info:
        _validate_immutability(plan, data)
    assert exc_info.value.fields == {"field": "validity_days"}
