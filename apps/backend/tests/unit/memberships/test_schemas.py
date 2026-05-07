"""Unit tests for app.modules.memberships.schemas Pydantic DTOs (Phase 16 + Phase 17).

Pure Pydantic tests — no DB, no FastAPI, no fixtures beyond stdlib + pytest.

Phase 16 — covers every D-XX decision from 16-CONTEXT.md:
- D-01: trim-only name normalization (preserves casing)
- D-04: PATCH does NOT declare duration_days -> stock 422 from extra='forbid'
- D-05: explicit null in PATCH body is rejected with a clear message
- D-06: Pydantic bounds on duration_days, price_kopecks, name
- Wire camelCase <-> Python snake_case alias_generator pair-test
- Default list query shape (MembershipPlanSort default, pagination defaults)

Phase 17 — covers MembershipCreateRequest + MembershipCancelRequest (D-03/D-10/D-11):
- paid_at ISO timestamp accept + omitted-is-None default
- notes max_length=1000 (T-17-02 mitigation)
- extra='forbid' on Create (server-computed startDate must NOT be in body)
- explicit-null guard on Cancel reason (D-11 mirror of Phase 16 D-05)
- reason max_length=500 (T-17-01 mitigation, half the notes ceiling)
- camelCase aliasing on paidAt + clientId
- MembershipResponse camelCase wire on all snapshot fields (D-10)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.memberships.schemas import (
    MembershipCancelRequest,
    MembershipCreateRequest,
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanSort,
    MembershipPlanUpdateRequest,
    MembershipResponse,
    MembershipStatus,
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


# ===========================================================================
# Phase 17 — MembershipCreateRequest + MembershipCancelRequest tests
# ===========================================================================


# --- D-03: paid_at semantics ----------------------------------------------


def test_create_accepts_paid_at_iso() -> None:
    """D-03: explicit ISO paidAt parses to a datetime."""
    m = MembershipCreateRequest.model_validate(
        {
            "clientId": str(uuid4()),
            "planId": str(uuid4()),
            "paidAt": "2026-05-01T10:00:00Z",
        }
    )
    assert m.paid_at is not None
    assert isinstance(m.paid_at, datetime)
    assert m.paid_at == datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC)


def test_create_paid_at_omitted_is_none() -> None:
    """D-03: omitting paidAt yields None."""
    m = MembershipCreateRequest.model_validate(
        {"clientId": str(uuid4()), "planId": str(uuid4())}
    )
    assert m.paid_at is None


# --- D-03: notes max_length ------------------------------------------------


def test_create_rejects_notes_over_1000_chars() -> None:
    """D-03 / T-17-02: notes longer than 1000 chars fails max_length=1000."""
    with pytest.raises(ValidationError):
        MembershipCreateRequest.model_validate(
            {
                "clientId": str(uuid4()),
                "planId": str(uuid4()),
                "notes": "x" * 1001,
            }
        )


def test_create_accepts_notes_at_1000_chars() -> None:
    """Boundary: exactly 1000 chars is accepted."""
    m = MembershipCreateRequest.model_validate(
        {
            "clientId": str(uuid4()),
            "planId": str(uuid4()),
            "notes": "x" * 1000,
        }
    )
    assert m.notes is not None
    assert len(m.notes) == 1000


# --- extra='forbid' on Create ----------------------------------------------


def test_create_rejects_extra_field() -> None:
    """extra='forbid' (BackendSchemaBase): server-computed startDate rejected with 422."""
    with pytest.raises(ValidationError):
        MembershipCreateRequest.model_validate(
            {
                "clientId": str(uuid4()),
                "planId": str(uuid4()),
                "startDate": "2026-01-01",  # server-computed; must not be in body
            }
        )


def test_create_rejects_arbitrary_extra_field() -> None:
    """extra='forbid' rejects any unknown field."""
    with pytest.raises(ValidationError):
        MembershipCreateRequest.model_validate(
            {
                "clientId": str(uuid4()),
                "planId": str(uuid4()),
                "foo": "bar",
            }
        )


# --- D-11: explicit-null guard on Cancel reason ----------------------------


def test_cancel_rejects_explicit_null_reason() -> None:
    """D-11 (mirror of Phase 16 D-05): explicit null reason raises ValidationError.

    Error message must match the locked guard string verbatim.
    """
    with pytest.raises(ValidationError) as exc_info:
        MembershipCancelRequest.model_validate({"reason": None})
    assert "Explicit null" in str(exc_info.value)
    # Locked message shape — must name the rejected key
    assert "reason" in str(exc_info.value)


def test_cancel_rejects_reason_over_500_chars() -> None:
    """D-11 / T-17-01: reason longer than 500 chars fails max_length=500."""
    with pytest.raises(ValidationError):
        MembershipCancelRequest.model_validate({"reason": "x" * 501})


def test_cancel_accepts_reason_at_500_chars() -> None:
    """Boundary: exactly 500 chars is accepted."""
    m = MembershipCancelRequest.model_validate({"reason": "x" * 500})
    assert m.reason is not None
    assert len(m.reason) == 500


def test_cancel_accepts_empty_body() -> None:
    """D-11: empty body is valid; reason defaults to None."""
    m = MembershipCancelRequest.model_validate({})
    assert m.reason is None


def test_cancel_no_args_is_valid() -> None:
    """Constructing without kwargs yields reason=None (default field)."""
    m = MembershipCancelRequest()
    assert m.reason is None


# --- camelCase aliasing on Create -------------------------------------------


def test_create_camel_case_aliasing_paid_at() -> None:
    """Wire alias: paidAt -> paid_at; round-trip via model_dump(by_alias=True)."""
    m = MembershipCreateRequest.model_validate(
        {
            "clientId": str(uuid4()),
            "planId": str(uuid4()),
            "paidAt": "2026-05-01T10:00:00Z",
        }
    )
    dumped = m.model_dump(by_alias=True)
    assert "paidAt" in dumped


def test_create_camel_case_aliasing_client_id() -> None:
    """Wire alias: clientId -> client_id (validated population)."""
    cid = str(uuid4())
    pid = str(uuid4())
    m = MembershipCreateRequest.model_validate(
        {"clientId": cid, "planId": pid}
    )
    assert str(m.client_id) == cid
    assert str(m.plan_id) == pid


# --- MembershipResponse camelCase wire (D-10) -------------------------------


def test_response_serialises_plan_name_snapshot_camelcase() -> None:
    """D-10: snapshot fields serialise to camelCase in the wire payload."""
    today = datetime.now(tz=UTC).date()
    response = MembershipResponse(
        id=uuid4(),
        client_id=uuid4(),
        plan_id=uuid4(),
        plan_name_snapshot="Базовый",
        duration_days_snapshot=30,
        price_kopecks_snapshot=250000,
        start_date=today,
        end_date=today + timedelta(days=29),
        status=MembershipStatus.ACTIVE,
        cancelled_at=None,
        cancel_reason=None,
        paid_at=None,
        notes=None,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    dumped = response.model_dump(by_alias=True)
    # D-10 snapshot fields in camelCase
    assert "planNameSnapshot" in dumped
    assert "durationDaysSnapshot" in dumped
    assert "priceKopecksSnapshot" in dumped
    assert dumped["planNameSnapshot"] == "Базовый"
    assert dumped["durationDaysSnapshot"] == 30
    assert dumped["priceKopecksSnapshot"] == 250000
    # Lifecycle fields in camelCase
    assert "startDate" in dumped
    assert "endDate" in dumped
    assert "cancelledAt" in dumped
    assert "cancelReason" in dumped
    assert "paidAt" in dumped
    assert "createdAt" in dumped
    assert "updatedAt" in dumped


def test_response_status_serialises_as_string_value() -> None:
    """MembershipStatus enum serialises as its string value, not the Python member."""
    today = datetime.now(tz=UTC).date()
    response = MembershipResponse(
        id=uuid4(),
        client_id=uuid4(),
        plan_id=uuid4(),
        plan_name_snapshot="Test",
        duration_days_snapshot=30,
        price_kopecks_snapshot=100,
        start_date=today,
        end_date=today,
        status=MembershipStatus.CANCELLED,
        cancelled_at=datetime.now(tz=UTC),
        cancel_reason="test",
        paid_at=None,
        notes=None,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    dumped = response.model_dump(by_alias=True)
    assert dumped["status"] == "cancelled"
