"""Integration tests for /api/v1/_internal/email/webhook (Phase 42 EMAIL-07 / D-42-17 / D-42-19).

Covers:
  - HMAC-SHA256 signature gate (BEFORE body parse, O(1) timing-safe rejection)
  - Hard-bounce / Complaint / Delivery / Soft-bounce routing
  - LOCKED `EmailSendFailedPayload.reason` Literal values: 'bounce' / 'complaint'
  - Audit emit ONLY on hard-bounce + complaint (D-42-19 send-attempt outcomes)
  - Unknown provider_message_id returns 202 without UPDATE / audit

Tests use the project ASGITransport fixture (no real network) and the
SAVEPOINT-wrapped db_session for per-test rollback.

The router module's `get_settings` import is monkeypatched so we can drive a
known webhook secret without touching env / lru_cache invalidation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.audit_payloads import EmailSendFailedPayload
from app.core.config import EmailProviderSettings, Settings, get_settings
from app.integrations.email.models import EmailSendLog

_WEBHOOK_SECRET = "test-webhook-shared-secret"


@pytest.fixture(autouse=True)
def _patch_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Override the router's get_settings() to return a Settings instance with
    a known webhook secret. Avoids touching the lru_cache + env layer.
    """
    base = get_settings()
    overridden = base.model_copy(
        update={
            "email": EmailProviderSettings(
                provider="sandbox",
                sandbox_mode=True,
                webhook_secret=SecretStr(_WEBHOOK_SECRET),
            ),
        }
    )

    def _override() -> Settings:
        return overridden

    monkeypatch.setattr(
        "app.api.v1._internal.email.router.get_settings",
        _override,
    )
    yield


def _sign(body: bytes) -> str:
    return hmac.new(
        _WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


async def _seed_send_log(
    db_session: AsyncSession,
    *,
    provider_message_id: str,
    to_address: str = "user@example.com",
    template_id: str = "auth.login_otp",
    status: str = "sent",
) -> EmailSendLog:
    row = EmailSendLog(
        audit_correlation_id=uuid4(),
        to_address=to_address,
        template_id=template_id,
        provider="yandex_postbox",
        provider_message_id=provider_message_id,
        status=status,
        bounce_type=None,
    )
    db_session.add(row)
    await db_session.flush()
    return row


# ---------------------------------------------------------------------------
# 401 gate tests — HMAC verified BEFORE parse
# ---------------------------------------------------------------------------


async def test_missing_signature_returns_401(async_client: AsyncClient) -> None:
    """Test 1: POST with no X-Email-Webhook-Signature header → 401 immediately."""
    body = json.dumps({"eventType": "Bounce"}).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401


async def test_wrong_signature_returns_401(async_client: AsyncClient) -> None:
    """Test 2: POST with wrong signature → 401 immediately."""
    body = json.dumps({"eventType": "Bounce"}).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": "0" * 64,
        },
    )
    assert response.status_code == 401


async def test_valid_signature_but_unparseable_json_returns_400(
    async_client: AsyncClient,
) -> None:
    """Test 3: valid signature + unparseable JSON → 400 AFTER signature check passes."""
    body = b"not-json-at-all{"
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Event routing tests — UPDATE EmailSendLog + conditional audit emit
# ---------------------------------------------------------------------------


async def test_hard_bounce_updates_row_and_emits_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 4: Bounce + Permanent → status='bounced', bounce_type='hard';
    audit 'email_send_failed' reason='bounce' (LOCKED Literal)."""
    row = await _seed_send_log(db_session, provider_message_id="msg-hard-1")

    body = json.dumps(
        {
            "eventType": "Bounce",
            "mail": {"messageId": "msg-hard-1"},
            "bounce": {"bounceType": "Permanent"},
        }
    ).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 202

    await db_session.refresh(row)
    assert row.status == "bounced"
    assert row.bounce_type == "hard"

    audit_row = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "email_send_failed")
        )
    ).first()
    assert audit_row is not None, "audit row must be emitted for hard-bounce"
    assert audit_row.payload["reason"] == "bounce"  # LOCKED Literal
    assert audit_row.payload["template_id"] == row.template_id
    assert audit_row.payload["to_email"] == row.to_address


async def test_complaint_updates_row_and_emits_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 5: Complaint → status='complained'; audit reason='complaint' (LOCKED Literal)."""
    row = await _seed_send_log(db_session, provider_message_id="msg-complaint-1")

    body = json.dumps(
        {
            "eventType": "Complaint",
            "mail": {"messageId": "msg-complaint-1"},
        }
    ).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 202

    await db_session.refresh(row)
    assert row.status == "complained"
    assert row.bounce_type is None

    audit_row = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "email_send_failed")
        )
    ).first()
    assert audit_row is not None
    assert audit_row.payload["reason"] == "complaint"  # LOCKED Literal


async def test_delivery_updates_row_and_does_not_emit_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 6: Delivery → status='delivered'; NO audit emit (D-42-19)."""
    row = await _seed_send_log(db_session, provider_message_id="msg-delivery-1")

    body = json.dumps(
        {
            "eventType": "Delivery",
            "mail": {"messageId": "msg-delivery-1"},
        }
    ).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 202

    await db_session.refresh(row)
    assert row.status == "delivered"

    audit_count = len(
        (
            await db_session.scalars(
                select(AuditLog).where(AuditLog.action == "email_send_failed")
            )
        ).all()
    )
    assert audit_count == 0, "soft-info events must NOT emit email_send_failed"


async def test_soft_bounce_updates_row_and_does_not_emit_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 7: Bounce + Transient → status='bounced', bounce_type='soft'; NO audit emit."""
    row = await _seed_send_log(db_session, provider_message_id="msg-soft-1")

    body = json.dumps(
        {
            "eventType": "Bounce",
            "mail": {"messageId": "msg-soft-1"},
            "bounce": {"bounceType": "Transient"},
        }
    ).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 202

    await db_session.refresh(row)
    assert row.status == "bounced"
    assert row.bounce_type == "soft"

    audit_count = len(
        (
            await db_session.scalars(
                select(AuditLog).where(AuditLog.action == "email_send_failed")
            )
        ).all()
    )
    assert audit_count == 0, "soft-bounces stay quiet per D-42-19"


async def test_unknown_message_id_returns_202_without_update_or_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 8: unknown provider_message_id → 202, no row UPDATE, no audit."""
    # Seed an unrelated row to prove only the matching row would change.
    other = await _seed_send_log(db_session, provider_message_id="msg-other")

    body = json.dumps(
        {
            "eventType": "Bounce",
            "mail": {"messageId": "msg-does-not-exist"},
            "bounce": {"bounceType": "Permanent"},
        }
    ).encode("utf-8")
    response = await async_client.post(
        "/api/v1/_internal/email/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-email-webhook-signature": _sign(body),
        },
    )
    assert response.status_code == 202

    await db_session.refresh(other)
    assert other.status == "sent", "the unrelated row must NOT be touched"

    audit_count = len(
        (
            await db_session.scalars(
                select(AuditLog).where(AuditLog.action == "email_send_failed")
            )
        ).all()
    )
    assert audit_count == 0


# ---------------------------------------------------------------------------
# Locked Literal regression guard (no DB needed)
# ---------------------------------------------------------------------------


def test_locked_literal_accepts_bounce_and_complaint() -> None:
    """Test 9 (LOCKED Literal regression guard): pydantic accepts the two values
    this plan emits and rejects the older draft strings ('bounced_hard' / 'complained').
    """
    ok = EmailSendFailedPayload(
        audit_correlation_id=uuid4(),
        template_id="X",
        to_email="x@y.z",
        reason="bounce",
        provider_error_code=None,
    )
    assert ok.reason == "bounce"
    ok2 = EmailSendFailedPayload(
        audit_correlation_id=uuid4(),
        template_id="X",
        to_email="x@y.z",
        reason="complaint",
        provider_error_code=None,
    )
    assert ok2.reason == "complaint"

    with pytest.raises(ValidationError):
        EmailSendFailedPayload(
            audit_correlation_id=uuid4(),
            template_id="X",
            to_email="x@y.z",
            reason="bounced_hard",  # type: ignore[arg-type]  # negative test
            provider_error_code=None,
        )
    with pytest.raises(ValidationError):
        EmailSendFailedPayload(
            audit_correlation_id=uuid4(),
            template_id="X",
            to_email="x@y.z",
            reason="complained",  # type: ignore[arg-type]  # negative test
            provider_error_code=None,
        )


def test_audit_correlation_id_uuid_type() -> None:
    """Sanity: EmailSendFailedPayload.audit_correlation_id parses str UUIDs."""
    payload = EmailSendFailedPayload(
        audit_correlation_id=UUID("11111111-1111-1111-1111-111111111111"),
        template_id="X",
        to_email="x@y.z",
        reason="bounce",
        provider_error_code=None,
    )
    assert payload.audit_correlation_id == UUID("11111111-1111-1111-1111-111111111111")
