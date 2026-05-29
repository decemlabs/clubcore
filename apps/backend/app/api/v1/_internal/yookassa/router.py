"""ЮKassa webhook intake router — payment lifecycle events (Phase 50 WH-01 / D-50-04).

Anonymous-by-design transport surface mounted under ``/api/v1/_internal/yookassa/``.
The route uses a route-level dependency on ``verify_yookassa_ip`` (D-50-04) so
the IP allowlist runs BEFORE the body is parsed — bogus traffic from non-ЮKassa
IPs never reaches the JSON parser. This is the second ``/_internal/*`` inhabitant
after ``/_internal/email/webhook`` (Phase 42 EMAIL-07).

D-50-04 / D-50-07 / D-50-08 / D-50-09 / D-50-10 discipline:

1. **IP allowlist** (route-level Depends; Phase 48-shipped ``verify_yookassa_ip``)
   returns 403 ``forbidden_ip`` for non-ЮKassa origins. The structlog warning is
   emitted by the verifier; the audit-DB row is the Phase 50 handler's responsibility.
2. **Body parse + defensive guards** (D-50-08): invalid JSON / missing ``event`` /
   missing ``object.id`` return 200 ``ok`` with structlog warning — ЮKassa retries
   on non-2xx, and a malformed body should not amplify retry storms.
3. **Redis dedup** (D-50-07 / D-50-09 / D-50-10): ``SET NX EX 86400`` on
   ``cc:yookassa:webhook:{event_type}:{object_id}``. The 24h TTL covers ЮKassa's
   maximum retry window. Dedup runs BEFORE re-fetch (D-50-10) so duplicate
   deliveries do not waste outbound rate-budget on GET /v3/payments/{id}.
4. **Event dispatch**: ``payment.succeeded`` → ``handle_payment_succeeded``;
   ``payment.canceled`` → ``handle_payment_canceled``; everything else logs an
   INFO line and returns 200 (forward-compat — new ЮKassa event types added later
   won't error out the webhook).
5. **Response shape** (D-50-08): always 200 ``text/plain`` ``ok``. ЮKassa's
   contract treats any 2xx as delivered; the handlers own all forensic detail.
"""

from __future__ import annotations

from typing import Annotated, Any, Final

import structlog
from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._internal.yookassa.handlers import (
    handle_payment_canceled,
    handle_payment_succeeded,
    handle_receipt_canceled,  # Phase 51 D-51-22 (NEW)
    handle_receipt_succeeded,  # Phase 51 D-51-21 (NEW)
    handle_refund_succeeded,  # Phase 51 D-51-11 (NEW)
)
from app.core.database import get_db
from app.core.dependencies import get_yookassa_client_provider
from app.core.redis import get_redis
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.webhook_verifier import verify_yookassa_ip

_log = structlog.get_logger("api.v1._internal.yookassa")

# Redis dedup key prefix (D-50-07 / D-50-09). 24h TTL covers ЮKassa's
# documented retry window — `Phase 50 CONTEXT.md` cites this lifetime
# explicitly. The full key shape is `{prefix}{event_type}:{object_id}`.
WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "cc:yookassa:webhook:"
WEBHOOK_DEDUP_TTL_SECONDS: Final[int] = 86400  # 24h matches ЮKassa retry window

router = APIRouter(tags=["Internal"])


@router.post(
    "/webhook",
    include_in_schema=False,
    dependencies=[Depends(verify_yookassa_ip)],
)
async def yookassa_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    yookassa_client_provider: Annotated[Any, Depends(get_yookassa_client_provider)],
) -> Response:
    """ЮKassa webhook intake — payment lifecycle events (Phase 50 WH-01..06 / D-50-04).

    IP allowlist runs at route-level Depends (BEFORE body parse). Redis dedup
    ``SET NX EX 86400`` short-circuits duplicate deliveries. On unique delivery,
    dispatches to per-event handler which owns the atomic UoW.

    IDM-07 / D-66-WEBHOOK-EXCLUDE / D-11-IDM-WEBHOOK:
    This endpoint is NOT wired to ``verify_idempotency``. It uses a separate Redis
    dedup path on ``WEBHOOK_DEDUP_KEY_PREFIX`` (``cc:yookassa:webhook:``) with 86400s
    TTL — independent of the operator-facing ``cc:idem:`` namespace. There is no
    ``current_user`` to scope to (IP-authenticated transport callback from ЮKassa;
    the route-level ``Depends(verify_yookassa_ip)`` is the authentication gate).
    Adding user-scoped ``verify_idempotency`` here would break the handler (no
    ``current_user``) and is architecturally incorrect — D-11-IDM-WEBHOOK.
    """
    yookassa_client: YooKassaClient = await yookassa_client_provider()

    try:
        body = await request.json()
    except Exception:
        _log.warning("yookassa_webhook_invalid_json")
        return Response(status_code=200, content="ok", media_type="text/plain")

    if not isinstance(body, dict):
        _log.warning("yookassa_webhook_non_object_body")
        return Response(status_code=200, content="ok", media_type="text/plain")

    event_type_raw = body.get("event", "")
    event_type: str = event_type_raw if isinstance(event_type_raw, str) else ""
    object_obj = body.get("object") or {}
    object_id_raw = object_obj.get("id", "") if isinstance(object_obj, dict) else ""
    object_id: str = object_id_raw if isinstance(object_id_raw, str) else ""

    if not event_type or not object_id:
        _log.warning(
            "yookassa_webhook_missing_fields",
            has_event=bool(event_type),
            has_object_id=bool(object_id),
        )
        return Response(status_code=200, content="ok", media_type="text/plain")

    dedup_key = f"{WEBHOOK_DEDUP_KEY_PREFIX}{event_type}:{object_id}"
    acquired = await redis.set(dedup_key, "1", nx=True, ex=WEBHOOK_DEDUP_TTL_SECONDS)
    if not acquired:
        _log.info(
            "yookassa_webhook_dedup_hit",
            event_type=event_type,
            object_id=object_id,
        )
        return Response(status_code=200, content="ok", media_type="text/plain")

    if event_type == "payment.succeeded":
        # Phase 51 D-51-15 — thread ``app.state.arq_pool`` so the post-commit
        # hook can enqueue ``dispatch_fiscal_receipt``. Pool is populated by
        # ``combined_lifespan`` (app/main.py); tests that bypass the lifespan
        # leave the attribute unset, in which case the handler receives
        # ``None`` and the enqueue branch is a no-op.
        arq_pool = getattr(request.app.state, "arq_pool", None)
        await handle_payment_succeeded(session, yookassa_client, body=body, arq_pool=arq_pool)
    elif event_type == "payment.canceled":
        # Phase 52 D-52-10 — thread arq_pool so the owner alert can be enqueued
        # post-commit. Mirrors the payment.succeeded branch (line 121).
        arq_pool = getattr(request.app.state, "arq_pool", None)
        await handle_payment_canceled(session, yookassa_client, body=body, arq_pool=arq_pool)
    elif event_type == "refund.succeeded":
        # Phase 51 D-51-11 — refund webhook re-fetches via yookassa_client.get_refund
        # before any DB write (D-50-12 doctrine inherited).
        # Thread arq_pool so the post-commit hook enqueues
        # dispatch_fiscal_receipt for the refund-side fiscal_receipts row —
        # symmetric to the payment.succeeded branch above (verification gap fix).
        arq_pool = getattr(request.app.state, "arq_pool", None)
        await handle_refund_succeeded(session, yookassa_client, body=body, arq_pool=arq_pool)
    elif event_type == "receipt.succeeded":
        # Phase 51 D-51-21 — receipt handlers do NOT take yookassa_client
        # (D-51-03 — no re-fetch; receipt status is informational, the body is
        # the authoritative source).
        await handle_receipt_succeeded(session, body=body)
    elif event_type == "receipt.canceled":
        # Phase 51 D-51-22 — same no-refetch shape as receipt.succeeded.
        await handle_receipt_canceled(session, body=body)
    else:
        _log.info(
            "yookassa_webhook_unsupported_event_type",
            event_type=event_type,
        )

    return Response(status_code=200, content="ok", media_type="text/plain")
