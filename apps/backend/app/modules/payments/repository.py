"""Payments repository — single ORM access point for the Payment ledger (Phase 32 PAY-03).

Caller-owns-txn discipline (D-32-10): NO ``session.flush()``, NO
``session.commit()`` calls live here. The service layer owns the
transactional moment so the audit row co-writes with the payment in a
single UoW.

Append-only (B-01 INFRA-22): only INSERT-style ops are present. NO
``update(Payment)``, NO ``delete(Payment)``, NO ``on_conflict_do_update`` —
the AST gate `tests/unit/test_payments_appendonly.py` enforces this at CI.

The cross-membership joins for ``list_payments_for_client`` reach across
modules ONLY through SQL subqueries against the ``memberships`` table —
the repository does NOT import the Membership ORM class (modules-independent
contract preserved).

``from __future__ import annotations`` deferred-evaluation is required so
``PaginatedData[PaymentResponse]`` does not trigger
``PydanticSchemaGenerationError`` at import time (same pitfall as clients
repository).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_REFUND,
)
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentListQuery, PaymentResponse

_MOSCOW = ZoneInfo("Europe/Moscow")


def _start_of_day_moscow_utc(day: Any) -> datetime:
    """Return the UTC datetime corresponding to 00:00:00 Europe/Moscow on `day`."""
    local = datetime.combine(day, time(0, 0, 0), tzinfo=_MOSCOW)
    return local


def _is_refund_of_uniqueness_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by uq_payments_refund_of_alive.

    Mirrors ``memberships.service._is_already_frozen_conflict`` discriminator
    pattern (constraint-name-based check via ``exc.orig.constraint_name`` with
    a fallback substring match for drivers that do not surface the attribute).
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_payments_refund_of_alive":
        return True
    return "uq_payments_refund_of_alive" in str(exc.orig)


async def insert_payment(
    session: AsyncSession,
    *,
    subject_kind: str,
    subject_id: UUID,
    amount_kopecks: int,
    method: str,
    received_by_user_id: UUID,
    refund_of: UUID | None = None,
) -> Payment:
    """Insert a Payment row; caller owns flush + audit emit (D-32-10).

    NO ``session.flush()`` here — the service-layer caller flushes to surface
    FK and partial-UNIQUE conflicts as typed AppError subclasses. Returns the
    transient Payment instance with server-side defaults pending RETURNING.
    """
    payment = Payment(
        subject_kind=subject_kind,
        subject_id=subject_id,
        amount_kopecks=amount_kopecks,
        method=method,
        received_by_user_id=received_by_user_id,
        refund_of=refund_of,
    )
    session.add(payment)
    return payment


async def get_payment_by_id(
    session: AsyncSession, payment_id: UUID
) -> Payment | None:
    """Return Payment by id, or None."""
    stmt: Select[tuple[Payment]] = select(Payment).where(Payment.id == payment_id)
    result: Payment | None = await session.scalar(stmt)
    return result


async def get_original_membership_payment(
    session: AsyncSession,
    membership_id: UUID,
) -> Payment | None:
    """Return the ORIGINAL sale payment for a membership (Phase 32 REF-02).

    Filters on ``subject_kind='membership' AND subject_id=:id AND
    amount_kopecks > 0`` and orders by ``received_at ASC`` so the first
    (chronologically earliest) sale row wins ties. Returns None when the
    membership has no recorded sale (legacy pre-Phase 32 rows).
    """
    stmt: Select[tuple[Payment]] = (
        select(Payment)
        .where(
            Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            Payment.subject_id == membership_id,
            Payment.amount_kopecks > 0,
        )
        .order_by(Payment.received_at.asc())
        .limit(1)
    )
    result: Payment | None = await session.scalar(stmt)
    return result


async def list_payments_filtered(
    session: AsyncSession,
    query: PaymentListQuery,
) -> PaginatedData[PaymentResponse]:
    """Global filtered list (Phase 32 PAY-06).

    Filters: subject_kind / subject_id / received_by_user_id / received_from /
    received_to (half-open in Europe/Moscow). Orders by received_at DESC with
    stable tie-break on id DESC. Returns a PaginatedData wrapping
    PaymentResponse instances (validated from ORM via model_validate).
    """
    predicates: list[Any] = []

    if query.subject_kind is not None:
        predicates.append(Payment.subject_kind == query.subject_kind)
    if query.subject_id is not None:
        predicates.append(Payment.subject_id == query.subject_id)
    if query.received_by_user_id is not None:
        predicates.append(Payment.received_by_user_id == query.received_by_user_id)
    if query.received_from is not None:
        lower = _start_of_day_moscow_utc(query.received_from)
        predicates.append(Payment.received_at >= lower)
    if query.received_to is not None:
        # Half-open upper bound: include all events on received_to in MSK.
        upper = _start_of_day_moscow_utc(query.received_to) + timedelta(days=1)
        predicates.append(Payment.received_at < upper)

    where_clause = and_(*predicates) if predicates else None

    total_stmt = select(func.count()).select_from(Payment)
    if where_clause is not None:
        total_stmt = total_stmt.where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[Payment]] = select(Payment)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.order_by(Payment.received_at.desc(), Payment.id.desc())
    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=[PaymentResponse.model_validate(p) for p in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def list_payments_for_client(
    session: AsyncSession,
    client_id: UUID,
    *,
    page: int,
    page_size: int,
) -> PaginatedData[PaymentResponse]:
    """All payments tied to a client's memberships (Phase 32 PAY-07).

    Joins via SQL subqueries against the ``memberships`` table — the
    repository never imports the Membership ORM class (modules-independent
    contract preserved). Includes both sale rows
    (subject_kind='membership' AND subject_id IN client memberships) AND
    refund rows whose refund_of references those sale payments.
    """
    membership_subq = (
        select(_memberships_table().c.id)
        .where(_memberships_table().c.client_id == client_id)
        .scalar_subquery()
    )
    refund_origin_subq = (
        select(Payment.id)
        .where(
            Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            Payment.subject_id.in_(membership_subq),
        )
        .scalar_subquery()
    )

    where_clause = (
        (Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP)
        & Payment.subject_id.in_(membership_subq)
    ) | (
        (Payment.subject_kind == SUBJECT_KIND_REFUND)
        & Payment.refund_of.in_(refund_origin_subq)
    )

    total_stmt = select(func.count()).select_from(Payment).where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[Payment]] = (
        select(Payment)
        .where(where_clause)
        .order_by(Payment.received_at.desc(), Payment.id.desc())
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=[PaymentResponse.model_validate(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_payments_for_membership(
    session: AsyncSession,
    membership_id: UUID,
    *,
    page: int,
    page_size: int,
) -> PaginatedData[PaymentResponse]:
    """All payments tied to a single membership (Phase 32 PAY-07).

    Includes sale row (subject_kind='membership' AND subject_id=:id) AND any
    refund row whose refund_of references the sale row.
    """
    refund_origin_subq = (
        select(Payment.id)
        .where(
            Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            Payment.subject_id == membership_id,
        )
        .scalar_subquery()
    )

    where_clause = (
        (Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP)
        & (Payment.subject_id == membership_id)
    ) | (
        (Payment.subject_kind == SUBJECT_KIND_REFUND)
        & Payment.refund_of.in_(refund_origin_subq)
    )

    total_stmt = select(func.count()).select_from(Payment).where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[Payment]] = (
        select(Payment)
        .where(where_clause)
        .order_by(Payment.received_at.desc(), Payment.id.desc())
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=[PaymentResponse.model_validate(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _memberships_table() -> Any:
    """Return the ``memberships`` SA Table object via metadata reflection.

    Goes through ``Base.metadata.tables['memberships']`` instead of
    importing the Membership ORM class — keeps the modules-independent
    contract intact (lint-imports ``modules cannot import each other``).
    """
    from app.core.database import Base

    return Base.metadata.tables["memberships"]
