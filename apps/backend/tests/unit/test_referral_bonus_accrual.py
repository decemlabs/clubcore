"""Phase 97 — REFER-04: tests for accrue_referral_bonus primitive and audit registry.

TDD RED phase: tests written BEFORE implementation — they must fail until
accrue_referral_bonus is added to loyalty/service.py.

Groups:
  1. Registry: ("referral_bonus_accrued", "referral") is in LOCKED_AUDIT_EVENTS.
  2. Payload: ReferralBonusAccruedPayload validates referrer/referee samples + rejects extras.
  3. Registry: AUDIT_PAYLOAD_SCHEMAS maps the pair to ReferralBonusAccruedPayload.
  4. Service import: accrue_referral_bonus is importable from loyalty.service.
  5. Service signature: function accepts (session, *, client_id, amount_kopecks,
       referral_capture_id, online_payment_id, role) with Literal role.
  6. Service behavior (mocked session):
     a. First call → returns a UUID (inserted_id), emits audit.
     b. Conflict path (RETURNING None) → returns None, no audit emitted.
     c. No session.flush() / session.commit() inside the function.
"""

from __future__ import annotations

import inspect
from typing import get_args, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    ReferralBonusAccruedPayload,
)

# ---------------------------------------------------------------------------
# Group 1: ("referral_bonus_accrued", "referral") is in LOCKED_AUDIT_EVENTS
# ---------------------------------------------------------------------------


def test_referral_bonus_accrued_event_locked() -> None:
    """INFRA-15: referral_bonus_accrued is locked BEFORE any callsite ships."""
    assert ("referral_bonus_accrued", "referral") in LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# Group 2: ReferralBonusAccruedPayload validates + rejects extras
# ---------------------------------------------------------------------------


def test_referral_bonus_accrued_payload_validates_referrer() -> None:
    """Referrer sample passes validation with all required fields."""
    payload = ReferralBonusAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=30_000,
        referral_capture_id=uuid4(),
        online_payment_id=uuid4(),
        role="referrer",
    )
    assert payload.amount_kopecks == 30_000
    assert payload.role == "referrer"


def test_referral_bonus_accrued_payload_validates_referee() -> None:
    """Referee sample passes validation."""
    payload = ReferralBonusAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=15_000,
        referral_capture_id=uuid4(),
        online_payment_id=uuid4(),
        role="referee",
    )
    assert payload.role == "referee"


def test_referral_bonus_accrued_payload_rejects_extra_fields() -> None:
    """extra='forbid' raises ValidationError when unknown fields are passed."""
    with pytest.raises(ValidationError):
        ReferralBonusAccruedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=30_000,
            referral_capture_id=uuid4(),
            online_payment_id=uuid4(),
            role="referrer",
            foo="bar",  # type: ignore[call-arg]
        )


def test_referral_bonus_accrued_payload_rejects_invalid_role() -> None:
    """role must be 'referrer' or 'referee' — other values rejected."""
    with pytest.raises(ValidationError):
        ReferralBonusAccruedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=30_000,
            referral_capture_id=uuid4(),
            online_payment_id=uuid4(),
            role="admin",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Group 3: AUDIT_PAYLOAD_SCHEMAS maps the pair to ReferralBonusAccruedPayload
# ---------------------------------------------------------------------------


def test_audit_payload_schemas_registers_referral_bonus_accrued() -> None:
    """AUDIT_PAYLOAD_SCHEMAS registry maps the referral_bonus_accrued pair correctly."""
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("referral_bonus_accrued", "referral")] is ReferralBonusAccruedPayload
    )


# ---------------------------------------------------------------------------
# Group 4: accrue_referral_bonus is importable from loyalty.service
# ---------------------------------------------------------------------------


def test_accrue_referral_bonus_importable() -> None:
    """accrue_referral_bonus must exist in loyalty.service."""
    from app.modules.loyalty import service as loyalty_service

    assert hasattr(loyalty_service, "accrue_referral_bonus"), (
        "accrue_referral_bonus not found in loyalty.service — implement it"
    )


# ---------------------------------------------------------------------------
# Group 5: Service signature checks
# ---------------------------------------------------------------------------


def test_accrue_referral_bonus_signature() -> None:
    """Signature must be keyword-only after session, with correct types."""
    from app.modules.loyalty.service import accrue_referral_bonus

    sig = inspect.signature(accrue_referral_bonus)
    params = list(sig.parameters.keys())

    assert "session" in params
    assert "client_id" in params
    assert "amount_kopecks" in params
    assert "referral_capture_id" in params
    assert "online_payment_id" in params
    assert "role" in params

    # All after session must be keyword-only (*)
    kw_params = [
        name
        for name, p in sig.parameters.items()
        if name != "session" and p.kind == inspect.Parameter.KEYWORD_ONLY
    ]
    assert set(kw_params) >= {
        "client_id",
        "amount_kopecks",
        "referral_capture_id",
        "online_payment_id",
        "role",
    }


def test_accrue_referral_bonus_return_type_annotation() -> None:
    """Return type must be UUID | None."""
    from app.modules.loyalty.service import accrue_referral_bonus

    hints = get_type_hints(accrue_referral_bonus)
    ret = hints.get("return")
    # Accept both UUID | None and Optional[UUID]
    assert ret is not None, "Return type annotation missing"
    args = get_args(ret)
    assert UUID in args or ret is UUID, f"UUID not in return type args: {ret}"


def test_accrue_referral_bonus_no_flush_no_commit() -> None:
    """The function body must not call session.flush() or session.commit()."""
    import inspect

    from app.modules.loyalty.service import accrue_referral_bonus

    src = inspect.getsource(accrue_referral_bonus)
    assert "session.flush(" not in src, "accrue_referral_bonus must not call session.flush()"
    assert "session.commit(" not in src, "accrue_referral_bonus must not call session.commit()"


# ---------------------------------------------------------------------------
# Group 6: Service behavior (mocked session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accrue_referral_bonus_first_call_returns_uuid_and_emits_audit() -> None:
    """First call inserts a row, returns UUID, and emits referral_bonus_accrued audit."""
    from app.modules.loyalty.service import accrue_referral_bonus

    inserted_id = uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = inserted_id
    session.execute = AsyncMock(return_value=mock_result)

    client_id = uuid4()
    referral_capture_id = uuid4()
    online_payment_id = uuid4()

    with patch("app.modules.loyalty.service.audit") as mock_audit:
        mock_audit.emit = AsyncMock()
        result = await accrue_referral_bonus(
            session,
            client_id=client_id,
            amount_kopecks=30_000,
            referral_capture_id=referral_capture_id,
            online_payment_id=online_payment_id,
            role="referrer",
        )

    assert result == inserted_id
    mock_audit.emit.assert_awaited_once()
    # Verify the emit was called with the correct event
    call_args = mock_audit.emit.call_args
    assert call_args[0][1] == "referral_bonus_accrued"
    assert call_args[1]["resource_type"] == "referral"
    assert call_args[1]["role"] == "referrer"
    assert call_args[1]["amount_kopecks"] == 30_000
    assert call_args[1]["client_id"] == str(client_id)
    assert call_args[1]["referral_capture_id"] == str(referral_capture_id)
    assert call_args[1]["online_payment_id"] == str(online_payment_id)


@pytest.mark.asyncio
async def test_accrue_referral_bonus_conflict_returns_none_no_audit() -> None:
    """Conflict path (ON CONFLICT DO NOTHING → RETURNING None) returns None, no audit."""
    from app.modules.loyalty.service import accrue_referral_bonus

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # conflict — RETURNING empty
    session.execute = AsyncMock(return_value=mock_result)

    with patch("app.modules.loyalty.service.audit") as mock_audit:
        mock_audit.emit = AsyncMock()
        result = await accrue_referral_bonus(
            session,
            client_id=uuid4(),
            amount_kopecks=30_000,
            referral_capture_id=uuid4(),
            online_payment_id=uuid4(),
            role="referee",
        )

    assert result is None
    mock_audit.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_accrue_referral_bonus_role_tagged_in_audit() -> None:
    """role kwarg is plumbed verbatim into the audit emit payload."""
    from app.modules.loyalty.service import accrue_referral_bonus

    inserted_id = uuid4()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = inserted_id
    session.execute = AsyncMock(return_value=mock_result)

    for role in ("referrer", "referee"):
        with patch("app.modules.loyalty.service.audit") as mock_audit:
            mock_audit.emit = AsyncMock()
            await accrue_referral_bonus(
                session,
                client_id=uuid4(),
                amount_kopecks=10_000,
                referral_capture_id=uuid4(),
                online_payment_id=uuid4(),
                role=role,  # type: ignore[arg-type]
            )
        call_kwargs = mock_audit.emit.call_args[1]
        assert call_kwargs["role"] == role, f"Expected role={role!r} in audit emit"
