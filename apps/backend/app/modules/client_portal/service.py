"""Client-portal service — read-only orchestrator (Phase 69 CHOME/CHIST/CPLAN).

Thin read-only service layer: wires repository functions to response schemas.
No try/except — AppError subclasses bubble to the central _app_error_handler.
No session.commit() — read-only, SVC001 commit-gate does not apply.

D-69-03: Own-scope empty states return None / empty list (200/null), NOT NotFoundError.
D-69-01: get_client_home reuses get_client_membership + next-booking — no duplicated logic.
D-69-02: days_until_end + expiring_soon computed from the raw-SQL result (server-derived).
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageQuery, PaginatedData
from app.modules.client_portal import repository
from app.modules.client_portal.schemas import (
    ClientCatalogPlanResponse,
    ClientCatalogPtPackageResponse,
    ClientCatalogTrainerResponse,
    ClientHomeResponse,
    ClientMembershipResponse,
    ClientNextBookingResponse,
    ClientPaymentItem,
    ClientPtSessionItem,
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
