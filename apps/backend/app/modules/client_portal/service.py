"""Client-portal service — read + write orchestrator (Phase 69/70/71).

Thin service layer: wires repository functions to response schemas.
No try/except — AppError subclasses bubble to the central _app_error_handler.

Phase 69 (read-only):
  - No session.commit(); SVC001 commit-gate does not apply to read paths.
Phase 70 (write delegates — CBOOK-02..05):
  - Write delegates call through composition-root Protocol slots in
    app.core.dependencies (D-20-MODULE); NO direct app.modules.bookings import.
  - SVC001 commit-gate: slot implementations (bookings/service.py) own commit.
Phase 71 (checkout write + status read — CPAY-01..05):
  - Checkout delegates into the extracted online_payments core via the
    composition-root Protocol slot invoke_client_checkout_core (D-20-MODULE).
  - NO direct app.modules.online_payments import; zero new ignore_imports.
  - No session.commit() — caller-owns-txn (D-32-10 / D-49-19).

D-69-03: Own-scope empty states return None / empty list (200/null), NOT NotFoundError.
D-69-01: get_client_home reuses get_client_membership + next-booking — no duplicated logic.
D-69-02: days_until_end + expiring_soon computed from the raw-SQL result (server-derived).
D-20-MODULE: client_portal writes via Protocol slots only; zero new ignore_imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import (
    ClientPrincipal,
    cancel_booking_for_client,
    create_booking_for_client,
    create_visit_client_qr,
    get_active_pt_package,
    invoke_client_checkout_core,
)
from app.core.exceptions import (
    ConflictError,
    InvalidSession,
    NoActivePtPackageError,
    NotFoundError,
)
from app.core.pagination import PageQuery, PaginatedData
from app.core.security import decode_qr_token, encode_qr_token
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.client_portal import repository
from app.modules.client_portal.schemas import (
    ClientAvailableSlotItem,
    ClientBookingResponse,
    ClientCatalogPlanResponse,
    ClientCatalogPtPackageResponse,
    ClientCatalogTrainerResponse,
    ClientCheckInResponse,
    ClientCheckoutResponse,
    ClientHomeResponse,
    ClientMembershipResponse,
    ClientNextBookingResponse,
    ClientPaymentItem,
    ClientPaymentStatusResponse,
    ClientPtSessionItem,
    ClientQrTokenResponse,
    ClientVisitItem,
)

_EXPIRING_SOON_DAYS = 7  # days threshold for expiring_soon flag (D-69-02)


async def get_client_membership(
    session: AsyncSession,
    client_id: UUID,
) -> ClientMembershipResponse | None:
    """Return active membership with server-derived days_until_end + expiring_soon.

    D-69-03: no active membership → return None (200 null via router), NOT NotFoundError.
    D-69-02: days_until_end is the SQL-computed integer; expiring_soon derived here.
    """
    row = await repository.fetch_client_membership(session, client_id)
    if row is None:
        return None
    r: dict[str, Any] = row
    days_until_end = int(r["days_until_end"])
    return ClientMembershipResponse(
        id=r["id"],
        plan_name_snapshot=str(r["plan_name_snapshot"]),
        start_date=r["start_date"],
        end_date=r["end_date"],
        status=str(r["status"]),
        days_until_end=days_until_end,
        expiring_soon=0 <= days_until_end <= _EXPIRING_SOON_DAYS,
    )


async def _get_client_next_booking(
    session: AsyncSession,
    client_id: UUID,
) -> ClientNextBookingResponse | None:
    """Internal: nearest upcoming booking for client. Empty → None (D-69-03)."""
    row = await repository.fetch_client_next_booking(session, client_id)
    if row is None:
        return None
    r: dict[str, Any] = row
    return ClientNextBookingResponse(
        id=r["id"],
        trainer_name=str(r["trainer_name"]),
        start_time=r["start_time"],
        status=str(r["status"]),
    )


async def get_client_home(
    session: AsyncSession,
    client_id: UUID,
) -> ClientHomeResponse:
    """Composite home screen payload (D-69-01).

    Server-side fan-out: REUSES get_client_membership + the next-booking query function —
    no duplicated query logic. Null slots for missing data (D-69-03).
    """
    membership = await get_client_membership(session, client_id)
    next_booking = await _get_client_next_booking(session, client_id)
    return ClientHomeResponse(
        membership=membership,
        next_booking=next_booking,
        expiring_soon=membership.expiring_soon if membership is not None else False,
    )


async def list_client_visits(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> PaginatedData[ClientVisitItem]:
    """Paginated visit history (CHIST-01)."""
    page_data = await repository.fetch_client_visits_page(
        session, client_id, query.page, query.page_size
    )
    return PaginatedData(
        items=[
            ClientVisitItem(
                id=cast(Any, row)["id"],
                gym_date=cast(Any, row)["gym_date"],
                checked_in_at=cast(Any, row)["checked_in_at"],
            )
            for row in page_data.items
        ],
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


async def list_client_pt_sessions(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> PaginatedData[ClientPtSessionItem]:
    """Paginated PT-session history (CHIST-02)."""
    page_data = await repository.fetch_client_pt_sessions_page(
        session, client_id, query.page, query.page_size
    )
    return PaginatedData(
        items=[
            ClientPtSessionItem(
                id=cast(Any, row)["id"],
                trainer_name_snapshot=str(cast(Any, row)["trainer_name_snapshot"]),
                performed_at=cast(Any, row)["performed_at"],
                cancelled_at=cast(Any, row).get("cancelled_at"),
            )
            for row in page_data.items
        ],
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


async def list_client_payments(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> PaginatedData[ClientPaymentItem]:
    """Paginated payment + refund history (CHIST-03)."""
    page_data = await repository.fetch_client_payments_page(
        session, client_id, query.page, query.page_size
    )
    return PaginatedData(
        items=[
            ClientPaymentItem(
                id=cast(Any, row)["id"],
                subject_kind=str(cast(Any, row)["subject_kind"]),
                amount_kopecks=int(cast(Any, row)["amount_kopecks"]),
                method=str(cast(Any, row)["method"]),
                received_at=cast(Any, row)["received_at"],
            )
            for row in page_data.items
        ],
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


async def list_membership_plans(
    session: AsyncSession,
) -> list[ClientCatalogPlanResponse]:
    """Active membership plans catalog (CPLAN-01, D-69-05)."""
    rows = await repository.fetch_membership_plans_catalog(session)
    return [
        ClientCatalogPlanResponse(
            id=cast(Any, r)["id"],
            name=str(cast(Any, r)["name"]),
            price_kopecks=int(cast(Any, r)["price_kopecks"]),
            duration_days=int(cast(Any, r)["duration_days"]),
        )
        for r in rows
    ]


async def list_pt_packages(
    session: AsyncSession,
) -> list[ClientCatalogPtPackageResponse]:
    """Active PT-package plans catalog (CPLAN-02, D-69-05)."""
    rows = await repository.fetch_pt_packages_catalog(session)
    return [
        ClientCatalogPtPackageResponse(
            id=cast(Any, r)["id"],
            name=str(cast(Any, r)["name"]),
            session_count=int(cast(Any, r)["session_count"]),
            price_kopecks=int(cast(Any, r)["price_kopecks"]),
        )
        for r in rows
    ]


async def list_trainers(
    session: AsyncSession,
) -> list[ClientCatalogTrainerResponse]:
    """Active trainers catalog (CPLAN-03, D-69-05)."""
    rows = await repository.fetch_trainers_catalog(session)
    return [
        ClientCatalogTrainerResponse(
            id=cast(Any, r)["id"],
            full_name=str(cast(Any, r)["full_name"]),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Phase 70 CBOOK-02..05 — booking write delegates + available-slots read
# ---------------------------------------------------------------------------


async def create_booking_for_client_request(
    session: AsyncSession,
    *,
    client_id: UUID,
    slot_id: UUID,
    pt_package_id: UUID,
) -> ClientBookingResponse:
    """Delegate booking creation to the Protocol-slot accessor (D-20-MODULE / CBOOK-03).

    Calls ``app.core.dependencies.create_booking_for_client`` — the composition-root
    slot wired to ``bookings.service.create_booking_for_client`` in ``main.py``.
    NO direct ``app.modules.bookings`` import (D-20-MODULE / zero new ignore_imports).

    CBOOK-04 mapping: PtPackageNotActiveError (code='pt_package_not_active', 409 in
    the bookings domain) is caught HERE (by code match on ConflictError from core.exceptions)
    and re-raised as ValidationAppError(422, 'no_active_pt_package') per D-70-03.
    This maps the domain-specific error to a client-facing precondition failure without
    importing app.modules.bookings (D-20-MODULE).

    Other errors bubble to _app_error_handler:
      - SlotAlreadyBookedError → 409 slot_already_booked (CBOOK-03 race)
      - SlotNotFoundError → 404, TrainerMismatchError → 409, etc.
    """
    try:
        result = await create_booking_for_client(
            session,
            client_id=client_id,
            slot_id=slot_id,
            pt_package_id=pt_package_id,
        )
    except ConflictError as exc:
        # PtPackageNotActiveError (code='pt_package_not_active') lives in
        # app.modules.bookings — importing it here would violate D-20-MODULE.
        # Match by code to remap to 422 ValidationAppError for the PWA (D-70-03 / CBOOK-04).
        if exc.code == "pt_package_not_active":
            raise NoActivePtPackageError("no_active_pt_package") from exc
        raise  # all other ConflictErrors bubble unchanged
    # result is BookingResponse (Pydantic ResponseData model) — access via attribute.
    # slot_start_time + trainer_full_name come from eager-loaded slot.trainer join
    # (bookings/service.py:_booking_response_from_orm builds this).
    r = cast(Any, result)
    return ClientBookingResponse(
        id=r.id,
        slot_id=r.slot_id,
        status=str(r.status),
        start_time=r.slot_start_time,
        trainer_name=str(r.trainer_full_name),
    )


async def cancel_client_booking(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    cancel_reason: str = "",
) -> ClientBookingResponse:
    """Delegate cancel to the Protocol-slot accessor (D-20-MODULE / CBOOK-05).

    Calls ``app.core.dependencies.cancel_booking_for_client`` — the composition-root
    slot wired to ``bookings.service.cancel_booking_for_client`` in ``main.py``.
    NO direct ``app.modules.bookings`` import (D-20-MODULE / zero new ignore_imports).

    Propagates domain errors without catching:
      - BookingNotFoundError → router/handler returns 404 booking_not_found (IDOR anti-oracle)
      - CancelWindowExpiredError → _app_error_handler → 409 cancel_window_expired
    """
    result = await cancel_booking_for_client(
        session,
        client_id=client_id,
        booking_id=booking_id,
        cancel_reason=cancel_reason,
    )
    r = cast(Any, result)
    return ClientBookingResponse(
        id=r.id,
        slot_id=r.slot_id,
        status=str(r.status),
        start_time=r.slot_start_time,
        trainer_name=str(r.trainer_full_name),
    )


# ---------------------------------------------------------------------------
# Phase 70 CCHK-01..03 — QR token issuance + check-in delegate
# ---------------------------------------------------------------------------


def issue_qr_token(client_id: UUID) -> ClientQrTokenResponse:
    """Mint a short-lived QR self check-in JWT for the authenticated client (CCHK-01).

    Called from GET /client/qr-token (require_client gated — D-70-09).
    No membership pre-check (CCHK-01 / D-70-09) — the anti-fraud chain in
    _create_visit_with_anti_fraud handles the active-membership gate at scan time.

    Pure function (no DB access) — encode_qr_token uses only the settings secret
    and the client UUID. expires_in mirrors settings.qr_token_ttl_seconds (~60s).
    """
    settings = get_settings()
    token = encode_qr_token(client_id)
    return ClientQrTokenResponse(
        token=token,
        expires_in=settings.qr_token_ttl_seconds,
    )


async def check_in_via_qr(
    session: AsyncSession,
    *,
    token: str,
) -> ClientCheckInResponse:
    """Validate the QR token and create a visit via the Protocol-slot accessor (CCHK-02).

    Called from POST /client/check-in (token-as-credential endpoint — no require_client).
    decode_qr_token asserts aud='qr' and typ='qr_checkin'; an access/refresh token
    presented here is rejected (401 wrong_token_type / wrong_audience).
    An expired token is rejected (401 token_expired). InvalidAccessToken bubbles
    to _app_error_handler → 401.

    client_id derives ONLY from the verified sub claim (D-70-10) — cross-client
    check-in is structurally impossible (T-70-17): there is no body/path/query
    client_id parameter on the check-in endpoint.

    Calls create_visit_client_qr (composition-root Protocol slot) — never imports
    app.modules.visits directly (D-20-MODULE / zero new ignore_imports).
    DuplicateCheckinError('duplicate_checkin') from uq_visits_client_id_gym_date
    bubbles to _app_error_handler → 409 (criterion #5 same-day replay guard).
    """
    claims = decode_qr_token(token)
    try:
        client_id = UUID(claims.sub)  # sole authoritative source (D-70-10)
    except ValueError as exc:
        raise InvalidSession("invalid_session") from exc
    result = await create_visit_client_qr(session, client_id)
    r = cast(Any, result)
    return ClientCheckInResponse(
        id=r.id,
        gym_date=r.gym_date,
        checked_in_at=r.checked_in_at,
        channel=str(r.channel),
    )


async def list_available_slots(
    session: AsyncSession,
    *,
    client_id: UUID,
    page: int,
    page_size: int,
) -> PaginatedData[ClientAvailableSlotItem]:
    """Return active future slots filtered by the client's active PT-package trainer pin.

    CBOOK-02: GET /client/slots. Client-safe projection (T-70-13).
    Trainer-pin logic: if the active PT-package has trainer_id != None, filter
    to that trainer's active future slots; else return all trainers' active slots.

    Empty PT-package (no active package) → return empty list (D-69-03 own-scope
    empty is 200/[], not an error; the client may not yet have a PT-package
    when browsing the slot catalog).
    """
    pkg = await get_active_pt_package(session, client_id)
    # getattr mirrors bookings/service.py:990 precedent for Protocol-narrow trainer_id
    trainer_id: UUID | None = getattr(pkg, "trainer_id", None) if pkg is not None else None

    offset = (page - 1) * page_size
    rows, total = await repository.fetch_available_slots(
        session,
        trainer_id=trainer_id,
        limit=page_size,
        offset=offset,
    )
    return PaginatedData(
        items=[
            ClientAvailableSlotItem(
                slot_id=cast(Any, r)["slot_id"],
                trainer_id=cast(Any, r)["trainer_id"],
                trainer_name=str(cast(Any, r)["trainer_name"]),
                start_time=cast(Any, r)["start_time"],
                end_time=cast(Any, r)["end_time"],
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Phase 71 CPAY-01..05 — client checkout write-slot + status read
# ---------------------------------------------------------------------------


def _derive_membership_idempotency_key(*, plan_id: UUID, client_id: UUID) -> str:
    """Server-derived per-day deterministic idempotency key for membership checkout (D-71-04).

    Mirrors _derive_idempotency_key in app.modules.online_payments.service:
      raw = 'sell-membership:{plan_id}:{client_id}:{today_iso}'
      key = sha256(raw).hexdigest()

    UTC today_iso — wire-protocol key must be stable across DST. Europe/Moscow
    user-facing date convention does NOT apply here (same rationale as the staff path).
    """
    today_iso = datetime.now(tz=UTC).date().isoformat()
    raw = f"sell-membership:{plan_id}:{client_id}:{today_iso}"
    return sha256(raw.encode("utf-8")).hexdigest()


async def client_checkout_membership(
    session: AsyncSession,
    *,
    plan_id: UUID,
    client: ClientPrincipal,
    yookassa_settings: YooKassaSettings,
) -> ClientCheckoutResponse:
    """Client-initiated membership checkout via ЮKassa redirect (CPAY-01).

    Derives the server-side per-day idempotency key (D-71-04) then delegates
    into the extracted online_payments core via the composition-root Protocol
    slot (D-20-MODULE). actor_user_id=None (D-71-02: client-initiated).
    No session.commit() — caller-owns-txn (D-32-10 / D-49-19).
    """
    idem_key = _derive_membership_idempotency_key(plan_id=plan_id, client_id=client.id)
    result = await invoke_client_checkout_core(
        session,
        subject_kind="membership",
        plan_id=plan_id,
        client_id=client.id,
        idempotency_key=idem_key,
        actor_user_id=None,
        confirmation_type="redirect",
        yookassa_settings=yookassa_settings,
    )
    r = cast(Any, result)
    return ClientCheckoutResponse(
        online_payment_id=r.online_payment_id,
        confirmation_url=str(r.confirmation_url),
    )


async def client_checkout_pt_package(
    session: AsyncSession,
    *,
    plan_id: UUID,
    client: ClientPrincipal,
    idempotency_key: str,
    yookassa_settings: YooKassaSettings,
) -> ClientCheckoutResponse:
    """Client-initiated PT-package checkout via ЮKassa redirect (CPAY-02).

    Passes the client-supplied Idempotency-Key header straight through to the
    core (D-71-04: PT allows same-day repurchase; PWA generates UUID per intent).
    actor_user_id=None (D-71-02: client-initiated).
    No session.commit() — caller-owns-txn (D-32-10 / D-49-19).
    """
    result = await invoke_client_checkout_core(
        session,
        subject_kind="pt_package",
        plan_id=plan_id,
        client_id=client.id,
        idempotency_key=idempotency_key,
        actor_user_id=None,
        confirmation_type="redirect",
        yookassa_settings=yookassa_settings,
    )
    r = cast(Any, result)
    return ClientCheckoutResponse(
        online_payment_id=r.online_payment_id,
        confirmation_url=str(r.confirmation_url),
    )


async def get_client_payment_status(
    session: AsyncSession,
    payment_id: UUID,
    client_id: UUID,
) -> ClientPaymentStatusResponse:
    """Coarse payment status for the authenticated client (CPAY-03).

    Anti-oracle: returns only 'pending' | 'succeeded' | 'canceled'.
    D-20-IDOR: fetch_client_payment_status has mandatory :client_id filter;
    None result → NotFoundError 404-collapse (anti-oracle, non-owned row).
    No session.commit() — read path.
    """
    row = await repository.fetch_client_payment_status(session, payment_id, client_id)
    if row is None:
        raise NotFoundError("payment_not_found")  # D-20-IDOR: 404-collapse
    return ClientPaymentStatusResponse(
        id=cast(Any, row)["id"],
        status=str(cast(Any, row)["status"]),
    )
