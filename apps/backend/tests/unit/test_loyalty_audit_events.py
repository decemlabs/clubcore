"""Phase 82/83 — LOCKED registry tests for loyalty audit events.

Mirrors test_locked_audit_events.py discipline (Phase 50 D-50-23).

Phase 82 groups (loyalty_accrued):
  1. ("loyalty_accrued", "loyalty") is in LOCKED_AUDIT_EVENTS.
  2. LoyaltyAccruedPayload validates a welcome sample AND rejects extra fields.
  3. AUDIT_PAYLOAD_SCHEMAS maps ("loyalty_accrued", "loyalty") → LoyaltyAccruedPayload.

Phase 83 groups (loyalty_redeemed):
  4. ("loyalty_redeemed", "loyalty") is in LOCKED_AUDIT_EVENTS.
  5. LoyaltyRedeemedPayload validates a negative-amount sample AND rejects extra fields.
  6. AUDIT_PAYLOAD_SCHEMAS maps ("loyalty_redeemed", "loyalty") → LoyaltyRedeemedPayload.

Pre-registered BEFORE callsite per INFRA-15 (ACCR-01/ACCR-02, REDM-02).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    LoyaltyAccruedPayload,
    LoyaltyRedeemedPayload,
)

# ---------------------------------------------------------------------------
# Group 1: ("loyalty_accrued", "loyalty") is in LOCKED_AUDIT_EVENTS
# ---------------------------------------------------------------------------


def test_loyalty_accrued_event_locked() -> None:
    """INFRA-15: loyalty_accrued is locked BEFORE any callsite ships."""
    assert ("loyalty_accrued", "loyalty") in LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# Group 2: LoyaltyAccruedPayload validates + rejects extras
# ---------------------------------------------------------------------------


def test_loyalty_accrued_payload_validates_welcome() -> None:
    """Welcome accrual sample passes validation with all required fields."""
    payload = LoyaltyAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=50_000,
        entry_type="welcome",
        actor="welcome",
    )
    assert payload.amount_kopecks == 50_000
    assert payload.entry_type == "welcome"
    assert payload.actor == "welcome"


def test_loyalty_accrued_payload_validates_owner_grant() -> None:
    """Owner-grant sample passes validation."""
    actor_id = uuid4()
    payload = LoyaltyAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=10_000,
        entry_type="owner_grant",
        actor=f"owner:{actor_id}",
    )
    assert payload.entry_type == "owner_grant"
    assert payload.actor.startswith("owner:")


def test_loyalty_accrued_payload_rejects_extra_fields() -> None:
    """extra='forbid' raises ValidationError when unknown fields are passed."""
    with pytest.raises(ValidationError):
        LoyaltyAccruedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=50_000,
            entry_type="welcome",
            actor="welcome",
            foo="bar",  # type: ignore[call-arg]
        )


def test_loyalty_accrued_payload_rejects_redemption_entry_type() -> None:
    """entry_type='redemption' is NOT valid for LoyaltyAccruedPayload (Phase 83 only)."""
    with pytest.raises(ValidationError):
        LoyaltyAccruedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=-5_000,
            entry_type="redemption",  # type: ignore[arg-type]
            actor="system",
        )


# ---------------------------------------------------------------------------
# Group 3: AUDIT_PAYLOAD_SCHEMAS maps the pair to LoyaltyAccruedPayload
# ---------------------------------------------------------------------------


def test_audit_payload_schemas_registers_loyalty_accrued() -> None:
    """AUDIT_PAYLOAD_SCHEMAS registry maps the loyalty_accrued pair correctly."""
    assert AUDIT_PAYLOAD_SCHEMAS[("loyalty_accrued", "loyalty")] is LoyaltyAccruedPayload


# ---------------------------------------------------------------------------
# Phase 83 Group 4: ("loyalty_redeemed", "loyalty") is in LOCKED_AUDIT_EVENTS
# ---------------------------------------------------------------------------


def test_loyalty_redeemed_event_locked() -> None:
    """INFRA-15: loyalty_redeemed is locked BEFORE any callsite ships (REDM-02)."""
    assert ("loyalty_redeemed", "loyalty") in LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# Phase 83 Group 5: LoyaltyRedeemedPayload validates + rejects extras
# ---------------------------------------------------------------------------


def test_loyalty_redeemed_payload_validates_negative_amount() -> None:
    """Redemption debit sample passes validation (amount_kopecks is negative)."""
    payload = LoyaltyRedeemedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=-5_000,
        online_payment_id=uuid4(),
    )
    assert payload.amount_kopecks == -5_000


def test_loyalty_redeemed_payload_rejects_extra_fields() -> None:
    """extra='forbid' raises ValidationError when unknown fields are passed."""
    with pytest.raises(ValidationError):
        LoyaltyRedeemedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=-5_000,
            online_payment_id=uuid4(),
            foo="bar",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Phase 83 Group 6: AUDIT_PAYLOAD_SCHEMAS maps the pair to LoyaltyRedeemedPayload
# ---------------------------------------------------------------------------


def test_audit_payload_schemas_registers_loyalty_redeemed() -> None:
    """AUDIT_PAYLOAD_SCHEMAS registry maps the loyalty_redeemed pair correctly."""
    assert AUDIT_PAYLOAD_SCHEMAS[("loyalty_redeemed", "loyalty")] is LoyaltyRedeemedPayload
