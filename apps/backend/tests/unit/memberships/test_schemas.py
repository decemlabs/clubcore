"""Unit tests for app.modules.memberships.schemas Pydantic DTOs (Phase 16 Plan 16-05).

Pure Pydantic tests — no DB, no FastAPI, no fixtures beyond stdlib + pytest.
Covers every D-XX decision from 16-CONTEXT.md:
- D-01: trim-only name normalization (preserves casing)
- D-04: PATCH does NOT declare duration_days -> stock 422 from extra='forbid'
- D-05: explicit null in PATCH body is rejected with a clear message
- D-06: Pydantic bounds on duration_days, price_kopecks, name
- Wire camelCase <-> Python snake_case alias_generator pair-test
- Default list query shape (MembershipPlanSort default, pagination defaults)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.memberships.schemas import (
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanSort,
    MembershipPlanUpdateRequest,
)

# --- D-01: trim leading/trailing whitespace ---


def test_create_trims_leading_trailing_whitespace_preserves_casing() -> None:
    """D-01: strip() applied before min_length; internal casing preserved."""
    m = MembershipPlanCreateRequest(
        name="  Базовый  ",
        duration_days=30,
        price_kopecks=250000,
    )
    assert m.name == "Базовый"


def test_create_post_trim_empty_rejected() -> None:
    """D-01 + D-06: whitespace-only name fails min_length=1 after trim."""
    with pytest.raises(ValidationError) as exc_info:
        MembershipPlanCreateRequest(
            name="   ",
            duration_days=30,
            price_kopecks=250000,
        )
    assert "min_length" in str(exc_info.value) or "least 1 character" in str(exc_info.value)


def test_update_trims_name_when_provided() -> None:
    """D-01: strip() applies to PATCH name as well."""
    m = MembershipPlanUpdateRequest.model_validate({"name": "  Премиум  "})
    assert m.name == "Премиум"


# --- D-04: forbid duration_days on PATCH ---


def test_update_rejects_duration_days_field() -> None:
    """D-04: durationDays in PATCH body -> ValidationError (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        MembershipPlanUpdateRequest.model_validate({"durationDays": 90})
    err_str = str(exc_info.value)
    assert "durationDays" in err_str or "duration_days" in err_str


def test_update_rejects_arbitrary_extra_field() -> None:
    """extra='forbid' rejects unknown keys."""
    with pytest.raises(ValidationError):
        MembershipPlanUpdateRequest.model_validate({"foo": "bar"})


# --- D-05: explicit null reject on PATCH ---


def test_update_rejects_explicit_null_name() -> None:
    """D-05: null name in PATCH body -> ValidationError with 'Explicit null' message."""
    with pytest.raises(ValidationError) as exc_info:
        MembershipPlanUpdateRequest.model_validate({"name": None})
    assert "Explicit null" in str(exc_info.value)


def test_update_rejects_explicit_null_price() -> None:
    """D-05: null priceKopecks in PATCH body -> ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MembershipPlanUpdateRequest.model_validate({"priceKopecks": None})
    assert "Explicit null" in str(exc_info.value)


def test_update_rejects_explicit_null_active() -> None:
    """D-05: null active in PATCH body -> ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MembershipPlanUpdateRequest.model_validate({"active": None})
    assert "Explicit null" in str(exc_info.value)


def test_update_omit_all_keys_is_valid_noop() -> None:
    """D-07: all-omitted PATCH is a valid no-op; model_dump(exclude_unset=True) == {}."""
    m = MembershipPlanUpdateRequest()
    assert m.model_dump(exclude_unset=True) == {}


# --- D-06: bounds on Create ---


def test_create_rejects_duration_days_below_one() -> None:
    """D-06: duration_days=0 fails ge=1."""
    with pytest.raises(ValidationError):
        MembershipPlanCreateRequest(
            name="Test",
            duration_days=0,
            price_kopecks=250000,
        )


def test_create_rejects_duration_days_above_3650() -> None:
    """D-06: duration_days=3651 fails le=3650."""
    with pytest.raises(ValidationError):
        MembershipPlanCreateRequest(
            name="Test",
            duration_days=3651,
            price_kopecks=250000,
        )


def test_create_accepts_duration_days_at_bounds() -> None:
    """D-06: boundary values 1 and 3650 are accepted."""
    m_min = MembershipPlanCreateRequest(
        name="Min",
        duration_days=1,
        price_kopecks=0,
    )
    m_max = MembershipPlanCreateRequest(
        name="Max",
        duration_days=3650,
        price_kopecks=0,
    )
    assert m_min.duration_days == 1
    assert m_max.duration_days == 3650


def test_create_rejects_negative_price() -> None:
    """D-06: price_kopecks=-1 fails ge=0."""
    with pytest.raises(ValidationError):
        MembershipPlanCreateRequest(
            name="Test",
            duration_days=30,
            price_kopecks=-1,
        )


def test_create_rejects_price_above_ceiling() -> None:
    """D-06: price_kopecks=10**11+1 fails le=10**11."""
    with pytest.raises(ValidationError):
        MembershipPlanCreateRequest(
            name="Test",
            duration_days=30,
            price_kopecks=10**11 + 1,
        )


def test_create_accepts_price_at_bounds() -> None:
    """D-06: boundary values 0 and 10**11 are accepted."""
    m_min = MembershipPlanCreateRequest(
        name="Free",
        duration_days=30,
        price_kopecks=0,
    )
    m_max = MembershipPlanCreateRequest(
        name="Max Price",
        duration_days=30,
        price_kopecks=10**11,
    )
    assert m_min.price_kopecks == 0
    assert m_max.price_kopecks == 10**11


def test_create_rejects_name_above_120_chars() -> None:
    """D-06: name longer than 120 chars fails max_length=120."""
    with pytest.raises(ValidationError):
        MembershipPlanCreateRequest(
            name="x" * 121,
            duration_days=30,
            price_kopecks=250000,
        )


def test_create_active_defaults_to_true() -> None:
    """D-06: omitting `active` yields True (DB DEFAULT TRUE mirrored in DTO)."""
    m = MembershipPlanCreateRequest(
        name="Test",
        duration_days=30,
        price_kopecks=250000,
    )
    assert m.active is True


# --- Wire alias contract (camelCase <-> snake_case) ---


def test_create_camel_to_snake_alias_pair() -> None:
    """BackendSchemaBase alias_generator maps camelCase wire keys to snake_case."""
    m = MembershipPlanCreateRequest.model_validate(
        {"name": "Test", "durationDays": 30, "priceKopecks": 250000}
    )
    assert m.duration_days == 30
    assert m.price_kopecks == 250000


def test_update_camel_to_snake_alias_pair() -> None:
    """PATCH alias wire: priceKopecks -> price_kopecks; omitted fields are None."""
    m = MembershipPlanUpdateRequest.model_validate({"priceKopecks": 999})
    assert m.price_kopecks == 999
    assert m.name is None
    assert m.active is None


# --- List query defaults ---


def test_list_query_default_sort() -> None:
    """D-08: MembershipPlanListQuery defaults to CREATED_AT_DESC, active=None, page=1, page_size=20.

    Tests all four default values in one assertion set.
    """
    q = MembershipPlanListQuery()
    assert q.sort == MembershipPlanSort.CREATED_AT_DESC
    assert q.active is None
    assert q.page == 1
    assert q.page_size == 20


# --- Response schema smoke ---


def test_response_schema_is_importable() -> None:
    """Smoke: MembershipPlanResponse and MembershipPlanSort are importable and usable."""
    assert MembershipPlanResponse is not None
    assert MembershipPlanSort.NAME_ASC == "name_asc"
    assert MembershipPlanSort.CREATED_AT_DESC == "created_at_desc"
