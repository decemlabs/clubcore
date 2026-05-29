"""Online payments router (Phase 49 PAY-03..06 / D-49-14, D-49-25).

Four POST sell endpoints (membership x {redirect, qr}, pt-package x
{redirect, qr}) mounted under ``/api/v1/online-payments/*``. Plan 49-05
appends the anonymous ``GET /return`` handler (separate file section to keep
the threat-model surface bounded — D-49-26).

RBAC-04 ordering (D-49-25 — enforced statically by
``tests/integration/test_route_introspection.py``):
``Depends(require_permission(...))`` → ``Depends(verify_csrf)`` →
``Depends(verify_idempotency)``. The 401→403→422 invariant is preserved by
FastAPI's signature-order dependency resolution.

Two-layer idempotency model (D-49-16):
- Outer (this router): operator-supplied ``Idempotency-Key`` header,
  validated + Redis-deduped via ``app.core.idempotency`` (5-second window
  via TTL on the placeholder; full replay via the cached envelope).
- Inner (service-layer): deterministic key derived from
  ``(subject_kind, plan_id, client_id, today_iso)`` passed to ЮKassa as
  ``Idempotence-Key`` header (D-49-08).

Settings DI (BLOCKER #5 — Plan 49-02): ``Depends(get_yookassa_settings)``
imports the ``@lru_cache(maxsize=1)`` factory shipped by Plan 49-02 at
``app/integrations/yookassa/settings.py``. The factory is process-scoped
and parallel to the lifespan-managed ``YooKassaSettings`` instantiated by
``create_app()`` for the shared ``http_client``.

Permission mapping (D-49-24 — both reception+owner; no new ``OWNER_ONLY``):
- ``/memberships/*``  → ``require_permission(CREATE, MEMBERSHIPS)``
- ``/pt-packages/*``  → ``require_permission(CREATE, PT_PACKAGES)``
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    CurrentUser,
    get_yookassa_client_provider,
    require_permission,
    verify_csrf,
)
from app.core.idempotency import (
    idempotent_execute,
    verify_idempotency,
)
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.settings import (
    YooKassaSettings,
    get_yookassa_settings,
)
from app.modules.online_payments import service
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_QR,
    CONFIRMATION_TYPE_REDIRECT,
)
from app.modules.online_payments.schemas import SellRequest, SellResponse
from app.modules.online_refunds import service as online_refunds_service
from app.modules.online_refunds.schemas import (
    OnlineRefundRequest,
    OnlineRefundResponse,
)

router = APIRouter(tags=["Payments"])


# ─── Phase 49 PAY-07 / D-49-17 — Anti-oracle return-screen constants ────────

_RETURN_HTML: Final[str] = (
    '<!doctype html><html lang="ru"><head>'
    '<meta charset="utf-8"><title>Оплата</title>'
    "</head><body>"
    "<h1>Оплата получена</h1>"
    "<p>Ожидаем подтверждение от платёжной системы. "
    "Эту страницу можно закрыть.</p>"
    "</body></html>"
)

# Phase 49 D-49-18 (revised per W3) — constant-time floor (PITFALLS Pitfall 4).
# Original D-49-18 specified 50 ms; W3 raised the floor to 60 ms to give the
# test (20 ms tolerance = 40 ms minimum assertion) headroom for CI scheduler
# jitter without sacrificing UX (60 ms is well below the 100 ms human
# perception threshold). Mirrors the anti-oracle uniformity discipline of
# auth/service.py:_constant_time_floor.
_RETURN_FLOOR_SECONDS: Final[float] = 0.060


# ─── Membership sell endpoints ──────────────────────────────────────────────


@router.post(
    "/memberships/{plan_id}/sell",
    response_model=ResponseEnvelope[SellResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Sell a membership online (redirect flow); reception+owner; CSRF + Idempotency-Key required"
    ),
)
async def sell_membership_redirect(
    plan_id: UUID,
    payload: SellRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> Response:
    """PAY-03 — membership redirect flow.

    Returns 201 + ``ResponseEnvelope[SellResponse]`` with
    ``confirmation_url`` populated and ``qr_payload`` NULL on success.
    Error mapping (service layer): 422 ``client_email_required_for_online_payment``,
    422 ``yookassa_validation_error``, 503 ``yookassa_unavailable``,
    502 ``yookassa_permanent_error``.

    Idempotency claim+replay+store delegated to the shared
    ``idempotent_execute`` orchestrator (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).
    """
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        sell_response = await service.sell_membership(
            session,
            plan_id=plan_id,
            client_id=payload.client_id,
            confirmation_type=CONFIRMATION_TYPE_REDIRECT,
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
        body_bytes = json.dumps(
            envelope(sell_response).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@router.post(
    "/memberships/{plan_id}/sell-qr",
    response_model=ResponseEnvelope[SellResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Sell a membership online (QR flow); reception+owner; CSRF + Idempotency-Key required"
    ),
)
async def sell_membership_qr(
    plan_id: UUID,
    payload: SellRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> Response:
    """PAY-05 — membership QR flow.

    Returns 201 + ``ResponseEnvelope[SellResponse]`` with ``qr_payload``
    populated and ``confirmation_url`` NULL on success. QR replays re-fetch
    upstream so the second click also receives a valid ``qr_payload``
    (D-49-09 + Plan 49-03 BLOCKER #1).

    Idempotency claim+replay+store delegated to the shared
    ``idempotent_execute`` orchestrator (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).
    """
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        sell_response = await service.sell_membership(
            session,
            plan_id=plan_id,
            client_id=payload.client_id,
            confirmation_type=CONFIRMATION_TYPE_QR,
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
        body_bytes = json.dumps(
            envelope(sell_response).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


# ─── PT-package sell endpoints ──────────────────────────────────────────────


@router.post(
    "/pt-packages/{plan_id}/sell",
    response_model=ResponseEnvelope[SellResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Sell a PT-package online (redirect flow); reception+owner; CSRF + Idempotency-Key required"
    ),
)
async def sell_pt_package_redirect(
    plan_id: UUID,
    payload: SellRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> Response:
    """PAY-04 — PT-package redirect flow. Same shape as membership variant.

    Idempotency delegated to the shared ``idempotent_execute`` orchestrator
    (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).
    """
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        sell_response = await service.sell_pt_package(
            session,
            plan_id=plan_id,
            client_id=payload.client_id,
            confirmation_type=CONFIRMATION_TYPE_REDIRECT,
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
        body_bytes = json.dumps(
            envelope(sell_response).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@router.post(
    "/pt-packages/{plan_id}/sell-qr",
    response_model=ResponseEnvelope[SellResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Sell a PT-package online (QR flow); reception+owner; CSRF + Idempotency-Key required"
    ),
)
async def sell_pt_package_qr(
    plan_id: UUID,
    payload: SellRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> Response:
    """PAY-05 — PT-package QR flow. Same shape as membership QR variant.

    Idempotency delegated to the shared ``idempotent_execute`` orchestrator
    (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).
    """
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        sell_response = await service.sell_pt_package(
            session,
            plan_id=plan_id,
            client_id=payload.client_id,
            confirmation_type=CONFIRMATION_TYPE_QR,
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
        body_bytes = json.dumps(
            envelope(sell_response).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


# ─── Phase 49 PAY-07 / D-49-17, D-49-18, D-49-26 — Anti-oracle return screen ─


@router.get(
    "/return",
    include_in_schema=False,  # PAY-07 — not documented; browser-target URL
)
async def online_payment_return() -> Response:
    """PAY-07 anonymous-by-design return-URL screen (D-49-17 / D-49-18 / W3).

    NO auth, NO CSRF, NO DB. Response body is static HTML with no payment
    status, payment ID, client name, or amount — eliminates the payment-
    status oracle. ЮKassa may append ``?payment_id=...`` to the URL on
    redirect; the handler accepts query params via request.query_params
    but discards them (D-49-17 — never bind as path/query model because
    that creates differential rendering).

    Constant-time floor (D-49-18 / W3, 60 ms) mirrors auth/service.py
    _constant_time_floor discipline. Phase 49 has exactly one callsite
    so the floor is embedded; extract to a helper if Phase 50+ adds more.
    """
    start = time.perf_counter()
    response = Response(
        content=_RETURN_HTML,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
    elapsed = time.perf_counter() - start
    await asyncio.sleep(max(0.0, _RETURN_FLOOR_SECONDS - elapsed))
    return response


# ─── Phase 51 REFUND-01 / D-51-08 — Operator-facing refund endpoints ────────
#
# Errata #2 Option A (PATTERNS.md): appended to the EXISTING
# ``app/modules/online_payments/router.py`` rather than a parallel
# ``app/api/v1/online_payments/`` package — avoids double-mounting at the
# ``/online-payments`` prefix and keeps the user-facing namespace cohesive.
#
# Two endpoints (membership refund + PT-package refund) — RBAC-04 ordering
# (D-49-25): auth → require_permission → verify_csrf. NO outer Idempotency-
# Key header here — refunds use a caller-supplied ``idempotency_key`` in the
# REQUEST BODY (D-51-Discretion) which is forwarded to the ЮKassa
# ``Idempotence-Key`` header BY the service after the step-1 replay check.
#
# Permission mapping (D-51-24 — both reception+owner; no new OWNER_ONLY):
#   /memberships/{id}/refund   → require_permission(REFUND, MEMBERSHIPS)
#   /pt-packages/{id}/refund   → require_permission(REFUND, PT_PACKAGES)


@router.post(
    "/memberships/{membership_id}/refund",
    response_model=ResponseEnvelope[OnlineRefundResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary=(
        "Initiate online refund of a membership (Phase 51 REFUND-01). "
        "Full refund only (partial deferred to v1.8 B-02). "
        "Returns 202; completion awaits ЮKassa refund.succeeded webhook."
    ),
)
async def refund_membership_online(
    membership_id: UUID,
    payload: OnlineRefundRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[OnlineRefundResponse]:
    """REFUND-01 — POST /api/v1/online-payments/memberships/{id}/refund.

    RBAC-04 ordering: auth → require_permission(REFUND, MEMBERSHIPS) →
    verify_csrf (D-49-25). Service applies Phase 32 guards (frozen / renewed-
    source / FSM) BEFORE calling ЮKassa; emits the
    ``online_refund_initiated`` audit row inside the single UoW.

    Error mapping (raised from the service layer):
      - 404 membership_not_found / online_payment_not_found / original_payment_not_found
      - 409 must_unfreeze_first / cannot_refund_renewed_source / invalid_transition
        / refund_already_in_flight
      - 422 yookassa_validation_error
      - 503 yookassa_unavailable
      - 502 yookassa_permanent_error

    IDM-07 classification B (v1.11-idempotency-audit.md / 66-03): ``verify_idempotency``
    is intentionally absent. The body-level ``payload.idempotency_key`` is forwarded
    verbatim to ЮKassa ``Idempotence-Key`` (operator-contract idempotency at the
    provider). The DB partial UNIQUE ``uq_online_refunds_alive_per_online_payment``
    (`(payment_id) WHERE status != 'failed'`) surfaces 409 ``refund_already_in_flight``
    on concurrent double-tap — this is the load-bearing race defence. Adding a
    header-level ``Idempotency-Key`` would be a redundant third layer; the 202 async
    return makes verbatim-replay semantics awkward. Decision binding for 66-03/66-04.
    """
    provider = get_yookassa_client_provider()
    yookassa_client: YooKassaClient = await provider()
    resp = await online_refunds_service.initiate_online_refund(
        session,
        actor,
        membership_id=membership_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        yookassa_client=yookassa_client,
    )
    return envelope(resp)


@router.post(
    "/pt-packages/{pt_package_id}/refund",
    response_model=ResponseEnvelope[OnlineRefundResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary=(
        "Initiate online refund of a PT-package (Phase 51 REFUND-01). "
        "Full refund only. Returns 202; completion awaits ЮKassa "
        "refund.succeeded webhook."
    ),
)
async def refund_pt_package_online(
    pt_package_id: UUID,
    payload: OnlineRefundRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[OnlineRefundResponse]:
    """REFUND-01 — POST /api/v1/online-payments/pt-packages/{id}/refund.

    Mirrors ``refund_membership_online``. No freeze / renewed-source guards
    for PT-packages (no freeze concept, no renewal chain in v1.x).

    IDM-07 classification B (v1.11-idempotency-audit.md / 66-03): ``verify_idempotency``
    is intentionally absent — same rationale as ``refund_membership_online`` above.
    Body-level ``payload.idempotency_key`` forwarded to ЮKassa; DB partial UNIQUE
    ``uq_online_refunds_alive_per_online_payment`` is the load-bearing race defence.
    Decision binding for 66-03/66-04.
    """
    provider = get_yookassa_client_provider()
    yookassa_client: YooKassaClient = await provider()
    resp = await online_refunds_service.initiate_online_refund(
        session,
        actor,
        pt_package_id=pt_package_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        yookassa_client=yookassa_client,
    )
    return envelope(resp)
