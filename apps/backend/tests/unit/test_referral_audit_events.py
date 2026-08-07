"""Phase 96 — LOCKED registry tests for referral audit events (REFER-01/REFER-03).

Mirrors test_loyalty_audit_events.py discipline (Phase 82/83).
Enforces INFRA-15 invariant: pairs registered BEFORE any callsite ships.

Group 1 (referral_code_generated):
  1. ("referral_code_generated", "referral") is in LOCKED_AUDIT_EVENTS.
  2. ReferralCodeGeneratedPayload validates a correct sample AND rejects extra fields.
  3. AUDIT_PAYLOAD_SCHEMAS maps ("referral_code_generated", "referral")
     → ReferralCodeGeneratedPayload.

Group 2 (referral_captured):
  4. ("referral_captured", "referral") is in LOCKED_AUDIT_EVENTS.
  5. ReferralCapturedPayload validates a correct sample AND rejects extra fields.
  6. AUDIT_PAYLOAD_SCHEMAS maps ("referral_captured", "referral") → ReferralCapturedPayload.

Pre-registered BEFORE callsite per INFRA-15 (REFER-01/REFER-03).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    ReferralCapturedPayload,
    ReferralCodeGeneratedPayload,
)

# ---------------------------------------------------------------------------
# Group 1: ("referral_code_generated", "referral") is in LOCKED_AUDIT_EVENTS
# ---------------------------------------------------------------------------


def test_referral_code_generated_event_locked() -> None:
    """INFRA-15: referral_code_generated is locked BEFORE any callsite ships."""
    assert ("referral_code_generated", "referral") in LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# Group 2: ReferralCodeGeneratedPayload validates + rejects extras
# ---------------------------------------------------------------------------


def test_referral_code_generated_payload_validates() -> None:
    """Valid sample passes validation with all required fields."""
    payload = ReferralCodeGeneratedPayload(
        client_id=uuid4(),
        referral_code_id=uuid4(),
        code="ABC12345",
    )
    assert payload.code == "ABC12345"
    assert payload.client_id is not None
    assert payload.referral_code_id is not None


def test_referral_code_generated_payload_rejects_extra_fields() -> None:
    """extra='forbid' raises ValidationError when unknown fields are passed."""
    with pytest.raises(ValidationError):
        ReferralCodeGeneratedPayload(
            client_id=uuid4(),
            referral_code_id=uuid4(),
            code="ABC12345",
            foo="bar",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Group 3: AUDIT_PAYLOAD_SCHEMAS maps the pair to ReferralCodeGeneratedPayload
# ---------------------------------------------------------------------------


def test_audit_payload_schemas_registers_referral_code_generated() -> None:
    """AUDIT_PAYLOAD_SCHEMAS registry maps the referral_code_generated pair correctly."""
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("referral_code_generated", "referral")]
        is ReferralCodeGeneratedPayload
    )


# ---------------------------------------------------------------------------
# Group 4: ("referral_captured", "referral") is in LOCKED_AUDIT_EVENTS
# ---------------------------------------------------------------------------


def test_referral_captured_event_locked() -> None:
    """INFRA-15: referral_captured is locked BEFORE any callsite ships (REFER-03)."""
    assert ("referral_captured", "referral") in LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# Group 5: ReferralCapturedPayload validates + rejects extras
# ---------------------------------------------------------------------------


def test_referral_captured_payload_validates() -> None:
    """Capture sample passes validation with all four required UUID fields."""
    payload = ReferralCapturedPayload(
        referee_client_id=uuid4(),
        referrer_client_id=uuid4(),
        referral_capture_id=uuid4(),
        referral_code_id=uuid4(),
    )
    assert payload.referee_client_id is not None
    assert payload.referrer_client_id is not None
    assert payload.referral_capture_id is not None
    assert payload.referral_code_id is not None


def test_referral_captured_payload_rejects_extra_fields() -> None:
    """extra='forbid' raises ValidationError when unknown fields are passed."""
    with pytest.raises(ValidationError):
        ReferralCapturedPayload(
            referee_client_id=uuid4(),
            referrer_client_id=uuid4(),
            referral_capture_id=uuid4(),
            referral_code_id=uuid4(),
            foo="bar",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Group 6: AUDIT_PAYLOAD_SCHEMAS maps the pair to ReferralCapturedPayload
# ---------------------------------------------------------------------------


def test_audit_payload_schemas_registers_referral_captured() -> None:
    """AUDIT_PAYLOAD_SCHEMAS registry maps the referral_captured pair correctly."""
    assert AUDIT_PAYLOAD_SCHEMAS[("referral_captured", "referral")] is ReferralCapturedPayload
