"""Phase 82 — LOCKED registry tests for loyalty_accrued audit event.

Mirrors test_locked_audit_events.py discipline (Phase 50 D-50-23).

Three assertion groups:
  1. ("loyalty_accrued", "loyalty") is in LOCKED_AUDIT_EVENTS.
  2. LoyaltyAccruedPayload validates a welcome sample AND rejects extra fields.
  3. AUDIT_PAYLOAD_SCHEMAS maps ("loyalty_accrued", "loyalty") → LoyaltyAccruedPayload.

Pre-registered BEFORE callsite per INFRA-15 (Phase 82 ACCR-01/ACCR-02).
Single event covers welcome + owner_grant (distinguished by entry_type/actor).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS, LoyaltyAccruedPayload

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
