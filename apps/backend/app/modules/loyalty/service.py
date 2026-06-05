"""Loyalty service (Phase 82 ACCR-01/ACCR-02/LOYL-01/LOYL-02/LOYL-03).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).
All reads use raw SQL text() — no cross-module ORM import of Client (D-54-08).

Idempotency note (welcome accrual):
  uq_loyalty_ledger_welcome is a partial UNIQUE INDEX (not a named UNIQUE CONSTRAINT).
  PostgreSQL ON CONFLICT ON CONSTRAINT works only for named constraints; for partial
  unique indexes we must use index_elements + index_where. We conflict on
  (client_id) WHERE entry_type = 'welcome' — exactly matching the migration's
  op.create_index partial predicate.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import literal_column, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.pagination import PageQuery, PaginatedData
from app.modules.loyalty.models import LoyaltyLedger
from app.modules.loyalty.schemas import (
    ClientLoyaltyBalanceResponse,
    ClientLoyaltyGrantResponse,
    ClientLoyaltyHistoryItem,
    LoyaltyGrantRequest,
)

_log = structlog.get_logger("modules.loyalty.service")

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

WELCOME_BONUS_KOPECKS: int = 50_000  # 500 ₽ welcome bonus (ACCR-01)


# ---------------------------------------------------------------------------
# Typed error classes (D-09 distinct per-reason codes)
# ---------------------------------------------------------------------------


class LoyaltyClientNotFoundError(NotFoundError):
    """Client not found when attempting loyalty grant."""

    code = "client_not_found"
    status_code = 404


class LoyaltyGrantNegativeError(ValidationAppError):
    """Owner grant amount must be positive (> 0)."""

    code = "grant_amount_must_be_positive"
    status_code = 422


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def accrue_welcome_bonus(
    session: AsyncSession,
    client_id: UUID,
) -> None:
    """Insert a one-time welcome accrual of WELCOME_BONUS_KOPECKS (ACCR-01).

    Idempotency: uses pg_insert on_conflict_do_nothing with index_elements +
    index_where matching the partial UNIQUE INDEX uq_loyalty_ledger_welcome
    (client_id WHERE entry_type='welcome'). Using index_elements instead of
    constraint= because the migration creates a partial UNIQUE INDEX (not a
    named UNIQUE CONSTRAINT) — PostgreSQL ON CONFLICT ON CONSTRAINT only works
    for named constraints. The RETURNING clause gating ensures we only emit
    the loyalty_accrued audit event when a row was actually inserted — replay
    calls return None from scalar_one_or_none() and emit nothing.

    flush only — never commit (caller-owns-txn).
    """
    stmt = (
        pg_insert(LoyaltyLedger)
        .values(
            client_id=client_id,
            entry_type="welcome",
            amount_kopecks=WELCOME_BONUS_KOPECKS,
            category=None,
            reason=None,
        )
        .on_conflict_do_nothing(
            index_elements=["client_id"],
            index_where=literal_column("entry_type") == "welcome",
        )
        .returning(LoyaltyLedger.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()

    if inserted_id is None:
        # Conflict path — row already exists; idempotent replay, emit nothing.
        _log.info(
            "loyalty_welcome_conflict",
            client_id=str(client_id),
            msg="welcome bonus already accrued — no-op",
        )
        return

    # Real insert — emit loyalty_accrued co-transactionally.
    await audit.emit(
        session,
        "loyalty_accrued",
        actor_user_id=None,  # system-initiated; no staff actor
        resource_type="loyalty",
        resource_id=inserted_id,
        client_id=str(client_id),
        entry_id=str(inserted_id),
        amount_kopecks=WELCOME_BONUS_KOPECKS,
        entry_type="welcome",
        actor="welcome",
    )
    _log.info(
        "loyalty_welcome_accrued",
        client_id=str(client_id),
        entry_id=str(inserted_id),
        amount_kopecks=WELCOME_BONUS_KOPECKS,
    )


async def owner_grant_loyalty(
    session: AsyncSession,
    actor: CurrentUser,
    client_id: UUID,
    payload: LoyaltyGrantRequest,
) -> ClientLoyaltyGrantResponse:
    """Insert an owner_grant ledger row and return the new balance (ACCR-02).

    Raises:
        LoyaltyGrantNegativeError (422): when amount_kopecks <= 0.
        LoyaltyClientNotFoundError (404): when client_id does not exist.

    flush only — never commit (caller-owns-txn).
    """
    if payload.amount_kopecks <= 0:
        raise LoyaltyGrantNegativeError("grant_amount_must_be_positive")

    # Existence check via raw SQL — D-54-08: no ORM import of Client.
    exists_row = (
        await session.execute(
            text("SELECT 1 FROM clients WHERE id = :cid AND deleted_at IS NULL LIMIT 1"),
            {"cid": str(client_id)},
        )
    ).fetchone()
    if exists_row is None:
        raise LoyaltyClientNotFoundError("client_not_found")

    # Insert owner_grant row (unconditional — no conflict guard for grants).
    stmt = (
        pg_insert(LoyaltyLedger)
        .values(
            client_id=client_id,
            entry_type="owner_grant",
            amount_kopecks=payload.amount_kopecks,
            category=payload.category,
            reason=payload.reason,
        )
        .returning(LoyaltyLedger.id)
    )
    result = await session.execute(stmt)
    entry_id: UUID = result.scalar_one()

    # Emit loyalty_accrued co-transactionally.
    actor_str = f"owner:{actor.id}"
    await audit.emit(
        session,
        "loyalty_accrued",
        actor_user_id=actor.id,
        resource_type="loyalty",
        resource_id=entry_id,
        client_id=str(client_id),
        entry_id=str(entry_id),
        amount_kopecks=payload.amount_kopecks,
        entry_type="owner_grant",
        actor=actor_str,
    )

    # Compute new balance (SUM fold including the just-inserted row).
    # flush first so the new row is visible to this session's read.
    await session.flush()
    balance_kopecks = await _sum_balance(session, client_id)

    _log.info(
        "loyalty_owner_grant",
        client_id=str(client_id),
        entry_id=str(entry_id),
        amount_kopecks=payload.amount_kopecks,
        category=payload.category,
        actor=actor_str,
        new_balance=balance_kopecks,
    )
    return ClientLoyaltyGrantResponse(
        entry_id=entry_id,
        balance_kopecks=balance_kopecks,
    )


async def get_client_loyalty_balance(
    session: AsyncSession,
    client_id: UUID,
) -> ClientLoyaltyBalanceResponse:
    """Return {balance_kopecks: SUM(amount_kopecks) COALESCE 0} (LOYL-01/LOYL-03).

    D-54-08: raw SQL text() — no ORM import of Client.
    D-69-03: empty ledger returns 0, never 404.
    """
    balance_kopecks = await _sum_balance(session, client_id)
    return ClientLoyaltyBalanceResponse(balance_kopecks=balance_kopecks)


async def list_client_loyalty_history(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> PaginatedData[ClientLoyaltyHistoryItem]:
    """Return paginated signed ledger rows for the principal (LOYL-02).

    Ordered created_at DESC. D-54-08: raw SQL text().
    D-20-IDOR: client_id always from the caller's principal, never from the URL.
    """
    count_row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM loyalty_ledger "
                "WHERE client_id = :cid"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().one()
    total = int(count_row["cnt"])

    offset = (query.page - 1) * query.page_size
    rows = (
        await session.execute(
            text(
                "SELECT id, entry_type, amount_kopecks, created_at "
                "FROM loyalty_ledger "
                "WHERE client_id = :cid "
                "ORDER BY created_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {
                "cid": str(client_id),
                "limit": query.page_size,
                "offset": offset,
            },
        )
    ).mappings().all()

    items = [
        ClientLoyaltyHistoryItem(
            id=row["id"],
            type=row["entry_type"],
            amount_kopecks=row["amount_kopecks"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return PaginatedData[ClientLoyaltyHistoryItem](
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _sum_balance(session: AsyncSession, client_id: UUID) -> int:
    """SUM(amount_kopecks) COALESCE 0 for the given client_id (LOYL-03)."""
    row = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(amount_kopecks), 0) AS balance "
                "FROM loyalty_ledger WHERE client_id = :cid"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().one()
    return int(row["balance"])
