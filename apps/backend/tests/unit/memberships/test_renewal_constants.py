"""Phase 26 D-26-13 — renewal strategy constants + exception class registration.

Asserts the two literal string values frozen by RENEWAL_STRATEGY_*. Service's
audit payload uses these via `start_date_strategy` key; integration tests
assert exact match against these constants. Drift would silently break
forensic SQL like:
    SELECT COUNT(*) FROM audit_log
    WHERE event='membership_renewed'
      AND payload->>'start_date_strategy' = 'from_today_expired_source';

Also covers the two new 409 exception classes registered in core/exceptions
(D-26-09): CannotRenewCancelledError and PlanArchivedError. Both must subclass
ConflictError so register_exception_handlers serialises them uniformly to
JSONResponse({code, message, fields}) at status 409.

Last, covers the schema extension on MembershipResponse (D-26-21):
previous_membership_id: UUID | None defaulting to None and surfacing as
camelCase `previousMembershipId` on the wire via BackendSchemaBase
alias_generator.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from app.core.exceptions import (
    AppError,
    CannotRenewCancelledError,
    ConflictError,
    PlanArchivedError,
)
from app.modules.memberships.constants import (
    MEMBERSHIP_STATUS_TRANSITIONS,
    RENEWAL_STRATEGY_FROM_SOURCE_END_DATE,
    RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE,
)
from app.modules.memberships.schemas import MembershipResponse, MembershipStatus

# ---------------------------------------------------------------------------
# Constants (Phase 26 D-26-13)
# ---------------------------------------------------------------------------


def test_renewal_strategy_from_source_end_date_literal() -> None:
    """D-26-13: literal value frozen as 'from_source_end_date'."""
    assert RENEWAL_STRATEGY_FROM_SOURCE_END_DATE == "from_source_end_date"


def test_renewal_strategy_from_today_expired_source_literal() -> None:
    """D-26-13: literal value frozen as 'from_today_expired_source'."""
    assert RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE == "from_today_expired_source"


def test_renewal_strategies_are_distinct() -> None:
    """Defence-in-depth: copy-paste accident would collapse the two literals."""
    assert RENEWAL_STRATEGY_FROM_SOURCE_END_DATE != RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE


def test_membership_status_transitions_unchanged_in_phase_26() -> None:
    """D-26-24: renewal is INSERT, not transition. State machine 4x4 untouched."""
    assert MEMBERSHIP_STATUS_TRANSITIONS["active"] == frozenset({"expired", "cancelled", "frozen"})
    assert MEMBERSHIP_STATUS_TRANSITIONS["frozen"] == frozenset({"active", "cancelled"})
    assert MEMBERSHIP_STATUS_TRANSITIONS["expired"] == frozenset()
    assert MEMBERSHIP_STATUS_TRANSITIONS["cancelled"] == frozenset()


# ---------------------------------------------------------------------------
# Exceptions (Phase 26 D-26-09)
# ---------------------------------------------------------------------------


def test_cannot_renew_cancelled_error_is_conflict_409() -> None:
    """CannotRenewCancelledError raises as 409 with code cannot_renew_cancelled."""
    err = CannotRenewCancelledError("cannot_renew_cancelled")
    assert isinstance(err, ConflictError)
    assert isinstance(err, AppError)
    assert err.code == "cannot_renew_cancelled"
    assert err.status_code == 409


def test_plan_archived_error_is_conflict_409() -> None:
    """PlanArchivedError raises as 409 with code plan_archived."""
    err = PlanArchivedError("plan_archived")
    assert isinstance(err, ConflictError)
    assert isinstance(err, AppError)
    assert err.code == "plan_archived"
    assert err.status_code == 409


def test_renewal_error_codes_are_distinct_from_plan_inactive() -> None:
    """plan_archived must not collide with the existing plan_inactive 409."""
    assert PlanArchivedError.code != "plan_inactive"
    assert CannotRenewCancelledError.code != "invalid_transition"


# ---------------------------------------------------------------------------
# Schema (Phase 26 D-26-21)
# ---------------------------------------------------------------------------


def _build_minimal_membership_response(
    *,
    previous_membership_id: object | None = ...,
) -> MembershipResponse:
    """Build a minimal MembershipResponse for schema-shape assertions."""
    base: dict[str, object] = {
        "id": uuid4(),
        "client_id": uuid4(),
        "plan_id": uuid4(),
        "plan_name_snapshot": "Standard 30",
        "duration_days_snapshot": 30,
        "price_kopecks_snapshot": 200_000,
        "start_date": date(2026, 5, 1),
        "end_date": date(2026, 5, 30),
        "status": MembershipStatus.ACTIVE,
        "cancelled_at": None,
        "cancel_reason": None,
        "paid_at": None,
        "notes": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "freeze_days_limit_snapshot": 14,
        "freeze_days_used": 0,
        "freeze_days_remaining": 14,
        "current_freeze_period": None,
    }
    if previous_membership_id is not ...:
        base["previous_membership_id"] = previous_membership_id
    return MembershipResponse(**base)


def test_membership_response_declares_previous_membership_id_field() -> None:
    """previous_membership_id is a registered Pydantic field."""
    assert "previous_membership_id" in MembershipResponse.model_fields


def test_membership_response_previous_membership_id_defaults_to_none() -> None:
    """Field is optional and defaults to None for backwards compatibility."""
    response = _build_minimal_membership_response()
    assert response.previous_membership_id is None


def test_membership_response_serialises_camelcase_previous_membership_id() -> None:
    """BackendSchemaBase alias_generator emits previousMembershipId on the wire."""
    source_id = uuid4()
    response = _build_minimal_membership_response(previous_membership_id=source_id)
    dumped = response.model_dump(by_alias=True, mode="json")
    assert "previousMembershipId" in dumped
    assert dumped["previousMembershipId"] == str(source_id)
