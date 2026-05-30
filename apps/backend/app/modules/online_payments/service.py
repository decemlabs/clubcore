"""Online payments service — sell orchestrator (Phase 49 PAY-03..06 / D-49-08..20).

ORDER OF OPERATIONS (D-49-10):
  1. Validate clients.email present (D-49-12 — raise ClientEmailRequiredForOnlinePaymentError).
  2. Lookup plan price + name (in-module raw SQL SELECT — BLOCKER #3 + D-49-03 invariant).
  3. Compute deterministic Idempotence-Key (D-49-08).
  4. Replay check via repository.get_online_payment_by_idempotency_key
     (D-49-09).
     - Redirect replay: return SellResponse with the existing
       confirmation_url and qr_payload=None.
     - QR replay: re-fetch via YooKassaClient.get_payment(existing
       .yookassa_payment_id); return SellResponse(confirmation_url=None,
       qr_payload=result.qr_payload, ...). (BLOCKER #1)
  5. Build receipt items via app.integrations.yookassa.receipt
     .build_receipt_item.
  6. Call YooKassaClient.create_payment (boundary returns
     YooKassaPaymentResult — never raises).
  7. Switch on result.classification:
     - ok → INSERT row → emit online_payment_initiated (ROOT) →
       emit yookassa_payment_created (CHILD) → 201
     - validation_error → raise ValidationAppError('yookassa_validation_error') (no DB row)
     - transient_error → raise ServiceUnavailableAppError('yookassa_unavailable') (no DB row)
     - permanent_error → raise BadGatewayAppError('yookassa_permanent_error') (no DB row)

The CALLER (router) owns the commit per caller-owns-txn discipline
(D-32-10 / D-49-19). The service does NOT call session.commit() — FastAPI
dependency commits on response.

Cross-module imports (narrow-scope, per .importlinter ignore_imports):
  - app.modules.clients.models      (D-49-13 — clients.email gate)
  - app.modules.payments.models     (D-49-29 — TYPE_CHECKING only; Phase 50 flips runtime)

Plan-price + plan-name reads use raw SQL `text()` SELECT against the
membership_plans + pt_package_plans tables — NO ORM imports for
MembershipPlan / PtPackagePlan; the D-49-03 invariant ("No other
cross-module imports are added in Phase 49") + BLOCKER #3 are both
preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_payloads import (
    OnlinePaymentInitiatedPayload,
    YookassaPaymentCreatedPayload,
)
from app.core.dependencies import CurrentUser, get_yookassa_client_provider
from app.core.exceptions import (
    BadGatewayAppError,
    ClientEmailRequiredForOnlinePaymentError,
    NotFoundError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.integrations.yookassa.receipt import (
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.clients.models import Client
from app.modules.online_payments import repository
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_QR,
    STATUS_PENDING,
    ErrorCode,
)
from app.modules.online_payments.schemas import SellResponse

if TYPE_CHECKING:
    # D-49-29 — Phase 49 imports defensively; Phase 50 flips to runtime when
    # record_payment(method='online') is called from the webhook handler.
    from app.modules.payments.models import Payment  # noqa: F401

_log = structlog.get_logger("modules.online_payments.service")


def _derive_idempotency_key(*, subject_kind: str, plan_id: UUID, client_id: UUID) -> str:
    """Deterministic Idempotence-Key per PAY-03 (D-49-08).

    UTC today_iso — wire-protocol key must be stable across DST. The
    Europe/Moscow user-facing date convention from CLAUDE.md does NOT
    apply here.
    """
    today_iso = datetime.now(tz=UTC).date().isoformat()
    raw = f"sell-{subject_kind}:{plan_id}:{client_id}:{today_iso}"
    return sha256(raw.encode("utf-8")).hexdigest()


async def _read_client_email_or_raise(session: AsyncSession, client_id: UUID) -> str:
    """FIS-05 gate (D-49-12): raise if clients.email IS NULL."""
    email: str | None = await session.scalar(select(Client.email).where(Client.id == client_id))
    if email is None:
        raise ClientEmailRequiredForOnlinePaymentError(ErrorCode.CLIENT_EMAIL_REQUIRED.value)
    return email


async def _read_membership_plan_or_raise(session: AsyncSession, plan_id: UUID) -> tuple[int, str]:
    """Return (price_kopecks, name) for an alive membership_plans row.

    BLOCKER #3 — raw SQL `text()` SELECT against the membership_plans
    table (NO ORM import of MembershipPlan; preserves D-49-03 invariant
    and the .importlinter contract Plan 49-02 ships).

    Verified columns (apps/backend/app/modules/memberships/models.py:58-90):
      - id            PgUUID
      - name          varchar(120)
      - price_kopecks BigInteger
      - deleted_at    nullable timestamptz
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, price_kopecks, name FROM membership_plans "
                    "WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": str(plan_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFoundError("membership_plan_not_found")
    return int(row["price_kopecks"]), str(row["name"])


async def _read_pt_package_plan_or_raise(session: AsyncSession, plan_id: UUID) -> tuple[int, str]:
    """Return (price_kopecks, name) for an alive pt_package_plans row.

    BLOCKER #3 — raw SQL `text()` SELECT against the pt_package_plans
    table (singular `package`; verified at
    apps/backend/app/modules/pt_packages/models.py:64). NO ORM import.

    Verified columns:
      - id            PgUUID
      - name          varchar(120)
      - price_kopecks BigInteger
      - deleted_at    nullable timestamptz
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, price_kopecks, name FROM pt_package_plans "
                    "WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": str(plan_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFoundError("pt_package_plan_not_found")
    return int(row["price_kopecks"]), str(row["name"])


async def _sell_subject_core(
    session: AsyncSession,
    *,
    subject_kind: Literal["membership", "pt_package"],
    plan_id: UUID,
    client_id: UUID,
    idempotency_key: str,
    actor_user_id: UUID | None,
    confirmation_type: Literal["redirect", "qr"],
    yookassa_settings: YooKassaSettings,
    online_payment_id_override: UUID | None = None,
    return_url_override: str | None = None,
) -> SellResponse:
    """Actor-agnostic sell flow (Phase 71 D-71-01).

    Extracted from the former ``_sell_subject`` body to support BOTH the
    existing staff callers AND the new client_portal checkout write-slot
    (Phase 71 Plan 71-01).  Actor identity is parameterised:

    - Staff callers: ``actor_user_id=actor.id`` (non-None UUID).
    - Client-initiated callers: ``actor_user_id=None`` (D-71-02 — the
      ``created_by_user_id`` column on ``online_payments`` is nullable;
      audit.emit() already supports ``actor_user_id=None`` as the D-41-10
      system-emit path).

    NO ``price_kopecks`` / ``description`` / ``amount`` parameter exists
    here (CPAY-03 price authority, D-71-01): price + name are read
    server-side from ``plan_id`` via ``_read_membership_plan_or_raise`` /
    ``_read_pt_package_plan_or_raise``.  Callers NEVER supply an amount.

    The idempotency key is supplied by the caller:
    - Membership staff/client: caller derives the server-side per-day key.
    - PT-package client path: caller passes the Idempotency-Key header value
      (PWA generates a UUID per checkout intent, D-71-04).

    CR-01/CR-02 (Phase 71 fix): ``online_payment_id_override`` and
    ``return_url_override`` are NEW optional params for the CLIENT path only.
    When both are provided AND a fresh row is being inserted (not a replay):
    - ``online_payment_id_override`` is used as the OnlinePayment PK so the
      PWA can build the poll URL BEFORE the ЮKassa call (payment_id is known
      deterministically client-side).
    - ``return_url_override`` is passed to ``create_payment`` so ЮKassa bakes
      the correct PWA return URL (with payment_id query param) into the
      redirect. Staff callers pass neither → behaviour is byte-identical.

    On the replay branch, both overrides are IGNORED (the replay returns the
    original row's persisted confirmation_url, which already carries the correct
    return_url from the original create call).

    WR-01 (Phase 71 fix): replay check is performed BEFORE the email gate so
    a same-day replay POST for a client whose email was later cleared returns
    the existing confirmation_url instead of a spurious 422 (CPAY-05).

    Uses ``session.flush()`` — caller owns the transaction (D-32-10/D-49-19).
    See module docstring for the 7-step protocol.
    """
    # 3. Idempotency key is supplied by the caller (see docstring).
    idem_key = idempotency_key

    # 4. Replay check FIRST (WR-01: moved before email gate so a cleared email
    #    does not block replay of an already-created redirect row — CPAY-05).
    existing = await repository.get_online_payment_by_idempotency_key(session, idem_key)
    if existing is not None and existing.status != "canceled":
        provider = get_yookassa_client_provider()
        yookassa_client = await provider()
        if existing.confirmation_type == CONFIRMATION_TYPE_QR:
            # BLOCKER #1 — QR replay re-fetches the upstream payment so
            # qr_payload is available; row stores no qr_payload (D-49-04),
            # and stale data is worse than re-computing.
            refetch = await yookassa_client.get_payment(existing.yookassa_payment_id)
            _log.info(
                "online_payment_sell_replay",
                online_payment_id=str(existing.id),
                subject_kind=subject_kind,
                confirmation_type="qr",
                refetch_classification=refetch.classification,
            )
            return SellResponse(
                confirmation_url=None,
                qr_payload=refetch.qr_payload,
                online_payment_id=existing.id,
            )
        # Redirect replay — confirmation_url persisted on the row at create time.
        # CR-01/CR-02 overrides are IGNORED on the replay path (existing row's
        # confirmation_url already carries the correct payment_id return URL).
        _log.info(
            "online_payment_sell_replay",
            online_payment_id=str(existing.id),
            subject_kind=subject_kind,
            confirmation_type="redirect",
        )
        return SellResponse(
            confirmation_url=existing.confirmation_url,
            qr_payload=None,
            online_payment_id=existing.id,
        )

    # CR-01 (fix): a canceled row carries the same idempotency_key as this
    # retry. The replay short-circuit above intentionally skips canceled rows
    # (a same-day retry after cancel MUST create a fresh payment), but the
    # canceled row still occupies uq_online_payments_idempotency_key. Derive a
    # unique key for the fresh INSERT so neither the PK (now a uuid4 override)
    # nor the idempotency_key UNIQUE constraint fires. The partial double-tap
    # index already excludes canceled rows, so the retry is permitted.
    if existing is not None:
        idem_key = f"{idempotency_key}:retry-{uuid4().hex}"

    # 1. FIS-05 email gate — checked AFTER replay (WR-01: replay is side-effect-free;
    #    a cleared email must not block returning an existing confirmation_url).
    customer_email = await _read_client_email_or_raise(session, client_id)

    # 2. Server-side price + description read (CPAY-03 — inside the core,
    #    never from caller).
    if subject_kind == "membership":
        price_kopecks, description = await _read_membership_plan_or_raise(session, plan_id)
    else:
        price_kopecks, description = await _read_pt_package_plan_or_raise(session, plan_id)

    # 5. Build receipt + 6. call ЮKassa.
    receipt_items = [
        build_receipt_item(
            description=description,
            amount_kopecks=price_kopecks,
            payment_subject=PaymentSubject.SERVICE,
            payment_mode=PaymentMode.FULL_PREPAYMENT,
            vat_code=VatCode(int(yookassa_settings.default_vat_code)),
        )
    ]
    provider = get_yookassa_client_provider()
    yookassa_client = await provider()
    result = await yookassa_client.create_payment(
        amount_kopecks=price_kopecks,
        description=description,
        receipt_items=receipt_items,
        customer_email=customer_email,
        idempotency_key=idem_key,
        confirmation_type=confirmation_type,
        return_url=return_url_override,  # CR-01/CR-02: None for staff (uses settings default)
    )

    # 7. Switch on classification.
    if result.classification == "ok":
        assert result.payment_id is not None
        assert result.amount_kopecks is not None
        correlation_id = uuid4()
        row = await repository.insert_online_payment(
            session,
            client_id=client_id,
            membership_plan_id=(plan_id if subject_kind == "membership" else None),
            pt_package_plan_id=(plan_id if subject_kind == "pt_package" else None),
            yookassa_payment_id=result.payment_id,
            idempotency_key=idem_key,
            amount_kopecks=result.amount_kopecks,
            status=STATUS_PENDING,
            confirmation_url=result.confirmation_url,
            confirmation_type=confirmation_type,
            created_by_user_id=actor_user_id,  # None for client-initiated (D-71-02)
            audit_correlation_id=correlation_id,
            id_override=online_payment_id_override,  # CR-01/CR-02: None for staff path
        )
        # surface FK + CHECK + UNIQUE conflicts BEFORE audit emit (D-49-19)
        await session.flush()

        # Audit ROOT — actor_user_id=None accepted by audit.emit() (D-41-10)
        initiated_payload = OnlinePaymentInitiatedPayload(
            audit_correlation_id=None,
            online_payment_id=row.id,
            client_id=row.client_id,
            amount_kopecks=row.amount_kopecks,
            subject_kind=subject_kind,
            subject_id=plan_id,
        )
        await audit.emit(
            session,
            "online_payment_initiated",
            actor_user_id=actor_user_id,
            resource_type="online_payment",
            resource_id=row.id,
            **initiated_payload.model_dump(mode="json"),
        )

        # Audit CHILD — same actor_user_id
        created_payload = YookassaPaymentCreatedPayload(
            audit_correlation_id=correlation_id,
            online_payment_id=row.id,
            yookassa_payment_id=row.yookassa_payment_id,
            idempotency_key=row.idempotency_key,
            confirmation_type=confirmation_type,
        )
        await audit.emit(
            session,
            "yookassa_payment_created",
            actor_user_id=actor_user_id,
            resource_type="online_payment",
            resource_id=row.id,
            **created_payload.model_dump(mode="json"),
        )

        _log.info(
            "online_payment_sell",
            outcome="ok",
            online_payment_id=str(row.id),
            subject_kind=subject_kind,
            confirmation_type=confirmation_type,
            client_id=str(client_id),
        )
        return SellResponse(
            confirmation_url=row.confirmation_url,
            qr_payload=result.qr_payload,
            online_payment_id=row.id,
        )

    _log.warning(
        "online_payment_sell",
        outcome=f"yookassa_{result.classification}",
        error_code=result.error_code,
        subject_kind=subject_kind,
    )
    if result.classification == "validation_error":
        raise ValidationAppError(ErrorCode.YOOKASSA_VALIDATION_ERROR.value)
    if result.classification == "transient_error":
        raise ServiceUnavailableAppError(ErrorCode.YOOKASSA_UNAVAILABLE.value)
    # permanent_error fallthrough
    raise BadGatewayAppError(ErrorCode.YOOKASSA_PERMANENT_ERROR.value)


async def sell_membership(
    session: AsyncSession,
    *,
    plan_id: UUID,
    client_id: UUID,
    confirmation_type: Literal["redirect", "qr"],
    actor: CurrentUser,
    yookassa_settings: YooKassaSettings,
) -> SellResponse:
    """Sell a membership online (Phase 49 PAY-03/05).

    Thin wrapper: derives the server-side per-day idempotency key (D-71-04)
    and delegates to ``_sell_subject_core`` with ``actor_user_id=actor.id``.
    Staff-facing public signature is byte-identical to contract-freeze-v1.11.0.
    """
    idem_key = _derive_idempotency_key(
        subject_kind="membership", plan_id=plan_id, client_id=client_id
    )
    return await _sell_subject_core(
        session,
        subject_kind="membership",
        plan_id=plan_id,
        client_id=client_id,
        idempotency_key=idem_key,
        actor_user_id=actor.id,
        confirmation_type=confirmation_type,
        yookassa_settings=yookassa_settings,
    )


async def sell_pt_package(
    session: AsyncSession,
    *,
    plan_id: UUID,
    client_id: UUID,
    confirmation_type: Literal["redirect", "qr"],
    actor: CurrentUser,
    yookassa_settings: YooKassaSettings,
) -> SellResponse:
    """Sell a PT-package online (Phase 49 PAY-04/05).

    Thin wrapper: derives the server-side per-day idempotency key (D-71-04)
    and delegates to ``_sell_subject_core`` with ``actor_user_id=actor.id``.
    Staff-facing public signature is byte-identical to contract-freeze-v1.11.0.
    """
    idem_key = _derive_idempotency_key(
        subject_kind="pt_package", plan_id=plan_id, client_id=client_id
    )
    return await _sell_subject_core(
        session,
        subject_kind="pt_package",
        plan_id=plan_id,
        client_id=client_id,
        idempotency_key=idem_key,
        actor_user_id=actor.id,
        confirmation_type=confirmation_type,
        yookassa_settings=yookassa_settings,
    )


async def phase49_fiscal_dispatcher_stub(
    *,
    fiscal_receipt_id: UUID,
    audit_correlation_id: UUID | None,
) -> None:
    """Phase-49-only bridge for the FiscalReceiptDispatcher slot (D-49-22).

    Replaces the Phase 47 noop_stub so the success-criterion #6 parity test
    passes; Phase 50 FISCAL-01 swaps this for the real ARQ-enqueue body.
    """
    raise NotImplementedError(
        "Phase 50 FISCAL-01 wires real dispatch — Phase 49 only registers "
        "the slot non-None so the parity test passes."
    )
