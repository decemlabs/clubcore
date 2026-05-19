"""Internal email webhook router -- HMAC-signed bounce/complaint events.

Phase 42 EMAIL-07 / D-42-17 / D-42-19.

NOT mounted under /api/v1/auth or any business module. This endpoint is a
TRANSPORT-layer concern -- the webhook posts back at the email transport, not
at a feature module surface. Mounted under /api/v1/_internal/ as the FIRST
inhabitant of that namespace. Future provider callbacks (invoice webhooks,
SMS-provider callbacks, etc.) land here.

HMAC discipline (D-42-17): the X-Email-Webhook-Signature header is checked
against the raw body bytes with hmac.compare_digest BEFORE any json.loads.
O(1) timing-safe rejection of unsigned probes. Mirrors verify_csrf shape
from app/core/dependencies.py (see PATTERNS.md §11). Diverges from
verify_csrf in ONE place: a 401 here does NOT emit a 'csrf_mismatch'-style
audit row because the surface is unauthenticated-and-public and would amplify
noise from every internet scanner that hits /_internal/* -- the structlog
INFO line on each rejection is the visibility surface.

Audit emission (D-42-19): ONLY hard-bounces and complaints emit
email_send_failed. Soft-bounces, deliveries, and other events stay quiet --
Phase 42 records send-attempt outcomes only; aggressive bounce-driven
email_verified=false flag flipping is deferred to v1.7.

LOCKED reason values (Phase 41 INFRA-35 -- verified against
app/core/audit_payloads.py lines 500-506):
  hard-bounce -> reason='bounce'  (singular; bounce_type='hard' lives on EmailSendLog)
  complaint   -> reason='complaint'
The strings 'bounced_hard' and 'complained' used in earlier drafts are
REJECTED -- they are not members of the EmailSendFailedPayload.reason Literal
and would raise pydantic ValidationError at runtime via extra='forbid'.
The audit.emit call passes the payload kwargs flattened (the audit.emit
signature is `**payload: Any`, not a single `payload=Model` argument); the
LOCKED schema is validated inside emit() via AUDIT_PAYLOAD_SCHEMAS lookup.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.email.models import EmailSendLog

_log = structlog.get_logger("api.v1._internal.email")

router = APIRouter()

# LOCKED-Literal subset this plan emits (see module docstring). Provides
# mypy-strict help against the typo class the earlier draft suffered from.
_WebhookReason = Literal["bounce", "complaint"]


@router.post(
    "/webhook",
    status_code=202,
    response_class=Response,
)
async def email_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Yandex Cloud Postbox bounce/complaint webhook (D-42-17 / EMAIL-07).

    Flow:
      1. Read raw body bytes (no parse yet).
      2. Compute HMAC-SHA256 of raw body with settings.email.webhook_secret.
      3. hmac.compare_digest against X-Email-Webhook-Signature header.
      4. Mismatch / missing -> 401 (no audit emit -- would amplify noise from
         unsigned probes; structlog WARN is the visibility surface).
      5. Parse body, route by eventType -> UPDATE EmailSendLog status.
      6. On hard-bounce/complaint: audit.emit('email_send_failed', ...) with
         LOCKED reason value ('bounce' or 'complaint').
    """
    settings = get_settings()
    raw_body = await request.body()

    presented_sig = request.headers.get("x-email-webhook-signature", "").strip().lower()
    expected_sig = hmac.new(
        settings.email.webhook_secret.get_secret_value().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()  # hashlib produces lowercase hex; normalisation is symmetric.
    if not presented_sig or not hmac.compare_digest(presented_sig, expected_sig):
        # 401 BEFORE parse. Do NOT emit audit -- this would amplify probe
        # noise from internet scanners hitting /_internal/* paths. WR-06:
        # both inputs are normalised (.strip().lower()) so proxy-added
        # whitespace and hex-case variance do not produce false 401s.
        _log.warning(
            "email_webhook_invalid_signature",
            has_header=bool(presented_sig),
        )
        raise HTTPException(status_code=401, detail="invalid_webhook_signature")

    # Past the gate -- now safe to parse.
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc

    # Yandex Cloud Postbox event shape mirrors AWS SES eventBridge:
    #   { "eventType": "Bounce"|"Complaint"|"Delivery"|...,
    #     "mail": { "messageId": "<provider_message_id>", ... },
    #     "bounce": { "bounceType": "Permanent"|"Transient", ... } }
    # Exact shape will be verified during Phase 46 VER-12 live probe -- if
    # upstream differs, adapt parsing here. The fields cited (eventType +
    # mail.messageId + bounce.bounceType) are the canonical SES-V2 contract
    # that Postbox exposes per D-42-01.
    event_type = payload.get("eventType")
    mail = payload.get("mail") or {}
    provider_message_id = mail.get("messageId")

    if not provider_message_id:
        # WR-02: fixed event name for ops alerting; kind discriminator separates
        # missing vs unknown without fragmenting log queries.
        _log.warning(
            "email_webhook_orphan_message_id",
            kind="missing",
            event_type=event_type,
        )
        return Response(status_code=202)

    row = await session.scalar(
        select(EmailSendLog).where(EmailSendLog.provider_message_id == provider_message_id)
    )
    if row is None:
        _log.warning(
            "email_webhook_orphan_message_id",
            kind="unknown",
            provider_message_id=provider_message_id,
            event_type=event_type,
        )
        return Response(status_code=202)

    new_status: str | None = None
    new_bounce_type: str | None = None
    emit_reason: _WebhookReason | None = None

    if event_type == "Bounce":
        bounce_type = (payload.get("bounce") or {}).get("bounceType")
        if bounce_type == "Permanent":
            new_status = "bounced"
            new_bounce_type = "hard"
            emit_reason = "bounce"  # LOCKED Literal value (NOT 'bounced_hard')
        else:
            # Transient (soft) bounce -- D-42-19 stays quiet.
            new_status = "bounced"
            new_bounce_type = "soft"
            emit_reason = None
    elif event_type == "Complaint":
        new_status = "complained"
        new_bounce_type = None
        emit_reason = "complaint"  # LOCKED Literal value (NOT 'complained')
    elif event_type == "Delivery":
        new_status = "delivered"
        new_bounce_type = None
        emit_reason = None
    else:
        _log.warning(
            "email_webhook_unknown_event_type",
            event_type=event_type,
            provider_message_id=provider_message_id,
        )
        return Response(status_code=202)

    await session.execute(
        update(EmailSendLog)
        .where(EmailSendLog.id == row.id)
        .values(status=new_status, bounce_type=new_bounce_type)
    )

    if emit_reason is not None:
        # Pitfall 2 / PATTERNS.md §A: emit audit BEFORE commit so the row
        # enrols in the same UoW as the EmailSendLog UPDATE. audit.emit's
        # signature is `**payload: Any` -- payload kwargs are flattened, and
        # the LOCKED schema (EmailSendFailedPayload) is validated inside
        # emit() via AUDIT_PAYLOAD_SCHEMAS lookup.
        await audit.emit(
            session,
            "email_send_failed",
            actor_user_id=None,
            resource_type="email_send_log",
            resource_id=row.id,
            # UUID fields are str-cast for JSONB serialisability -- mirrors the
            # membership_renewed / expiring_notification_sent_*d pattern in
            # app/modules/memberships/service.py. The LOCKED schema's
            # `audit_correlation_id: UUID | None` accepts the str form (pydantic
            # coerces) and the JSONB column needs a JSON-serialisable value.
            audit_correlation_id=str(row.audit_correlation_id),
            template_id=row.template_id,
            to_email=row.to_address,
            reason=emit_reason,
            provider_error_code=None,
        )

    await session.commit()
    return Response(status_code=202)
