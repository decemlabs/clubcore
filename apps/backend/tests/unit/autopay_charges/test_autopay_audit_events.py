"""Phase 84 APAY-01/APAY-03 + INFRA-15 — autopay audit event pre-registration.

Verifies that both autopay charge lifecycle events are pre-registered in
LOCKED_AUDIT_EVENTS and AUDIT_PAYLOAD_SCHEMAS BEFORE any callsite is written
(INFRA-15 discipline — callsites land in Plan 84-02).

Tests:
1. Both (event, resource_type) tuples are in LOCKED_AUDIT_EVENTS.
2. Both tuples have a registered payload schema in AUDIT_PAYLOAD_SCHEMAS.
3. AutopayChargeFailedPayload requires failure_reason and rejects extra keys (extra="forbid").
4. AutopayChargeInitiatedPayload rejects extra keys and constructs correctly.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    AutopayChargeFailedPayload,
    AutopayChargeInitiatedPayload,
)

# ---------------------------------------------------------------------------
# 1. LOCKED_AUDIT_EVENTS registration
# ---------------------------------------------------------------------------


def test_autopay_charge_initiated_in_locked_events() -> None:
    """('autopay_charge_initiated', 'autopay') must be in LOCKED_AUDIT_EVENTS (INFRA-15)."""
    assert ("autopay_charge_initiated", "autopay") in LOCKED_AUDIT_EVENTS, (
        "autopay_charge_initiated must be pre-registered in LOCKED_AUDIT_EVENTS "
        "before any callsite (INFRA-15 — callsite in Plan 84-02)"
    )


def test_autopay_charge_failed_in_locked_events() -> None:
    """('autopay_charge_failed', 'autopay') must be in LOCKED_AUDIT_EVENTS (INFRA-15)."""
    assert ("autopay_charge_failed", "autopay") in LOCKED_AUDIT_EVENTS, (
        "autopay_charge_failed must be pre-registered in LOCKED_AUDIT_EVENTS "
        "before any callsite (INFRA-15 — callsite in Plan 84-02)"
    )


# ---------------------------------------------------------------------------
# 2. AUDIT_PAYLOAD_SCHEMAS registration
# ---------------------------------------------------------------------------


def test_autopay_charge_initiated_payload_registered() -> None:
    """AUDIT_PAYLOAD_SCHEMAS must map ('autopay_charge_initiated', 'autopay')
    to AutopayChargeInitiatedPayload."""
    schema = AUDIT_PAYLOAD_SCHEMAS.get(("autopay_charge_initiated", "autopay"))
    assert schema is AutopayChargeInitiatedPayload, (
        f"Expected AutopayChargeInitiatedPayload, got {schema}"
    )


def test_autopay_charge_failed_payload_registered() -> None:
    """AUDIT_PAYLOAD_SCHEMAS must map ('autopay_charge_failed', 'autopay')
    to AutopayChargeFailedPayload."""
    schema = AUDIT_PAYLOAD_SCHEMAS.get(("autopay_charge_failed", "autopay"))
    assert schema is AutopayChargeFailedPayload, (
        f"Expected AutopayChargeFailedPayload, got {schema}"
    )


# ---------------------------------------------------------------------------
# 3. AutopayChargeFailedPayload — extra="forbid" + required fields
# ---------------------------------------------------------------------------


def test_autopay_charge_failed_payload_rejects_extra_key() -> None:
    """AutopayChargeFailedPayload must reject unknown keys (extra='forbid')."""
    with pytest.raises(ValidationError):
        AutopayChargeFailedPayload(  # type: ignore[call-arg]
            membership_id=UUID("00000000-0000-0000-0000-000000000001"),
            amount_kopecks=100000,
            period_end="2026-07-01",
            failure_reason="permanent_error",
            unknown_extra_field="should_fail",
        )


def test_autopay_charge_failed_payload_requires_failure_reason() -> None:
    """AutopayChargeFailedPayload must require failure_reason."""
    with pytest.raises(ValidationError):
        AutopayChargeFailedPayload(  # type: ignore[call-arg]
            membership_id=UUID("00000000-0000-0000-0000-000000000001"),
            amount_kopecks=100000,
            period_end="2026-07-01",
            # failure_reason omitted — must raise
        )


def test_autopay_charge_failed_payload_constructs_correctly() -> None:
    """AutopayChargeFailedPayload must accept all required fields."""
    mid = UUID("00000000-0000-0000-0000-000000000001")
    payload = AutopayChargeFailedPayload(
        membership_id=mid,
        amount_kopecks=100000,
        period_end="2026-07-01",
        failure_reason="permanent_error",
    )
    assert payload.membership_id == mid
    assert payload.amount_kopecks == 100_000
    assert payload.period_end == "2026-07-01"
    assert payload.failure_reason == "permanent_error"


# ---------------------------------------------------------------------------
# 4. AutopayChargeInitiatedPayload — extra="forbid"
# ---------------------------------------------------------------------------


def test_autopay_charge_initiated_payload_rejects_extra_key() -> None:
    """AutopayChargeInitiatedPayload must reject unknown keys (extra='forbid')."""
    with pytest.raises(ValidationError):
        AutopayChargeInitiatedPayload(  # type: ignore[call-arg]
            membership_id=UUID("00000000-0000-0000-0000-000000000002"),
            amount_kopecks=100000,
            period_end="2026-07-01",
            unknown_extra_field="should_fail",
        )


def test_autopay_charge_initiated_payload_constructs_correctly() -> None:
    """AutopayChargeInitiatedPayload must accept all required fields."""
    mid = UUID("00000000-0000-0000-0000-000000000002")
    payload = AutopayChargeInitiatedPayload(
        membership_id=mid,
        amount_kopecks=199000,
        period_end="2026-08-01",
    )
    assert payload.membership_id == mid
    assert payload.amount_kopecks == 199_000
    assert payload.period_end == "2026-08-01"
