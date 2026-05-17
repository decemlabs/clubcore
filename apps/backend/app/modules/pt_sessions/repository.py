"""PT-sessions repository — single point of access to the PtSession ORM.

This is the ONLY module in the codebase that imports the PtSession ORM
model from `pt_sessions.models`. Cross-module reads (`pt_packages` metadata)
and cross-module writes (`sessions_remaining` decrement/increment, status
flip `exhausted ↔ active`) go through raw `sa.text()` SQL strings — D-34-04a
keeps the `modules-independent` importlinter contract clean without an
ORM import on the `pt_packages` side.

All cross-module raw SQL statements are marked with
`# noqa: TABLE_REF cross-module SQL per D-34-04a` for grep-ability and use
named parameter binding (`:pt_package_id`) — never f-string interpolation.

Transaction control: NO `session.commit()` and NO `session.flush()` here
(mirrors memberships D-14, pt_packages D-33 caller-owns-txn). The service
layer owns the UoW so it can co-write `audit_log` in the same transaction.

Plan 34-01 lands this header + import surface only. Sale-side helpers
(`atomic_decrement_pt_package`, `atomic_transition_to_exhausted`,
`fetch_pt_package_metadata`, `insert_pt_session`) are filled by 34-02
(this plan); cancel/read-side helpers (`get_pt_session`, `mark_cancelled`,
`atomic_increment_pt_package`, `atomic_transition_exhausted_to_active`,
`list_by_pt_package_paginated`) are filled by 34-03.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.pt_sessions.models import PtSession
from app.modules.pt_sessions.schemas import PtSessionListByPackageQuery


async def atomic_decrement_pt_package(
    session: AsyncSession,
    pt_package_id: UUID,
) -> int | None:
    """Race-safe decrement of ``pt_packages.sessions_remaining`` (PT-16 / D-34-04a).

    Returns new ``sessions_remaining`` on success; ``None`` on 0-row update
    (caller raises 409 ``pt_package_exhausted``). The predicate
    ``sessions_remaining > 0 AND status='active'`` makes THIS UPDATE the SOLE
    arbiter of "can we record a session" — concurrent callers serialise at
    the row lock and the loser observes 0 rows updated. The DB-layer CHECK
    ``sessions_remaining >= 0`` from migration 0014_pt_packages is
    defence-in-depth; the WHERE predicate is the primary gate (PT-16).

    Raw ``sa.text()`` SQL referencing ``pt_packages`` by table name avoids
    importing ``app.modules.pt_packages.models.PtPackage`` and keeps the
    ``modules-independent`` importlinter contract green (D-34-04a).
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET sessions_remaining = sessions_remaining - 1,
            updated_at = now()
        WHERE id = :pt_package_id
          AND sessions_remaining > 0
          AND status = 'active'
        RETURNING sessions_remaining
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.first()
    return None if row is None else int(row[0])


async def atomic_transition_to_exhausted(
    session: AsyncSession,
    pt_package_id: UUID,
) -> bool:
    """Flip ``status='active' → 'exhausted'`` inside the same UoW that just
    consumed the last session (D-34-05 / PT-17).

    The predicate ``WHERE status='active'`` guards against a concurrent
    refund flipping ``status`` to ``cancelled`` mid-transaction — Phase 33
    ``PT_PACKAGE_STATUS_TRANSITIONS`` permits ``active → exhausted`` only,
    so we MUST only flip from active. Returns ``True`` iff exactly one row
    transitioned (defence-in-depth; caller already controls the invariant
    by having observed ``new_remaining == 0`` from
    ``atomic_decrement_pt_package`` earlier in the same UoW).
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET status = 'exhausted',
            updated_at = now()
        WHERE id = :pt_package_id AND status = 'active'
        RETURNING id
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    return result.first() is not None


async def fetch_pt_package_metadata(
    session: AsyncSession,
    pt_package_id: UUID,
) -> dict[str, object] | None:
    """SELECT pt_packages metadata by id (D-34-13a; raw SQL — slot doesn't fit).

    Returns a flat ``dict`` (NOT the ``PtPackage`` ORM) to keep the
    cross-module surface deliberately small. ``None`` = row not found,
    caller raises 404 ``pt_package_not_found``.

    The ``ActivePtPackage`` Protocol slot from Phase 33 (D-33-12) takes a
    ``client_id`` (Telegram-bot lookup shape) and returns ``None`` for
    non-active packages — wrong fit for the id-as-input read needed by
    ``record_pt_session`` / ``cancel_pt_session``. Direct ``text()`` SELECT
    keeps the cross-module dependency reduced to a column name list.
    """
    stmt = sa.text(
        """
        SELECT id, client_id, status, sessions_remaining, end_date
        FROM pt_packages
        WHERE id = :pt_package_id
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def insert_pt_session(
    session: AsyncSession,
    *,
    pt_package_id: UUID,
    trainer_id: UUID,
    client_id: UUID,
    performed_at: datetime,
    performed_by_user_id: UUID,
    trainer_name_snapshot: str,
    notes: str | None,
    booking_id: UUID | None = None,
) -> PtSession:
    """Construct + ``session.add()`` a new ``PtSession`` row.

    Caller-owns-txn (D-03): this function does NOT flush or commit; the
    service layer is responsible for flushing (to surface FK / CHECK errors
    before audit emit) and for committing the surrounding UoW.

    ``trainer_name_snapshot`` is captured by the service from
    ``trainer.full_name`` on the ``TrainerById`` Protocol slot (B-05 /
    D-34-12a) so historical UI rendering survives later trainer rename or
    deactivation. ``client_id`` is sourced from the parent
    ``pt_packages.client_id`` (NOT request body — D-34-13a) so reception
    cannot record a session against an unrelated client by spoofing the id.

    Keyword-only after ``*`` to match the call shape from
    ``service.record_pt_session`` and document field intent at the callsite.
    """
    pt_session = PtSession(
        pt_package_id=pt_package_id,
        trainer_id=trainer_id,
        client_id=client_id,
        performed_at=performed_at,
        performed_by_user_id=performed_by_user_id,
        trainer_name_snapshot=trainer_name_snapshot,
        notes=notes,
        booking_id=booking_id,
    )
    session.add(pt_session)
    return pt_session


# ---------------------------------------------------------------------------
# Cancel + read-side helpers (Plan 34-03 — PT-18 / PT-19).
# ---------------------------------------------------------------------------


async def get_pt_session(
    session: AsyncSession,
    pt_session_id: UUID,
) -> PtSession | None:
    """Return a single PtSession row by id, or None for missing.

    ORM-side read on the local table — no cross-module SQL. Caller raises
    404 ``pt_session_not_found`` on None (cancel + GET endpoints).
    """
    stmt: Select[tuple[PtSession]] = select(PtSession).where(
        PtSession.id == pt_session_id,
    )
    result: PtSession | None = await session.scalar(stmt)
    return result


async def list_by_pt_package_paginated(
    session: AsyncSession,
    pt_package_id: UUID,
    query: PtSessionListByPackageQuery,
) -> PaginatedData[PtSession]:
    """Paginated list of PtSession rows for a parent pt_package (PT-19).

    Mirrors ``pt_packages.repository.list_pt_packages_paginated`` shape:
    ``model_construct`` skips Pydantic validation against the generic
    parameter (the SA ORM is not Pydantic-compatible; runtime
    parametrisation would raise ``PydanticSchemaGenerationError``).

    Ordering: ``performed_at DESC, created_at DESC, id DESC`` (D-34-08 —
    latest-first; deterministic tiebreaker via id for paging stability).
    Filter: ``include_cancelled=False`` → ``cancelled_at IS NULL`` only.
    """
    predicates: list[Any] = [PtSession.pt_package_id == pt_package_id]
    if not query.include_cancelled:
        predicates.append(PtSession.cancelled_at.is_(None))

    total_stmt = select(func.count()).select_from(PtSession).where(*predicates)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[PtSession]] = (
        select(PtSession)
        .where(*predicates)
        .order_by(
            PtSession.performed_at.desc(),
            PtSession.created_at.desc(),
            PtSession.id.desc(),
        )
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = (await session.scalars(stmt)).all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def mark_cancelled(
    session: AsyncSession,
    pt_session: PtSession,
    *,
    cancel_reason: str,
) -> PtSession:
    """In-place setter for ``cancelled_at`` + ``cancel_reason`` (PT-18).

    Caller-owns-txn (D-03): mutates the loaded ORM instance but does NOT
    flush or commit. The service layer flushes before audit emit so FK /
    CHECK violations surface inside the same UoW.

    The CHECK constraint ``cancel_reason IS NULL OR cancelled_at IS NOT
    NULL`` (migration 0015) is satisfied here because both fields are set
    together.
    """
    pt_session.cancelled_at = datetime.now(tz=UTC)
    pt_session.cancel_reason = cancel_reason
    return pt_session


async def atomic_increment_pt_package(
    session: AsyncSession,
    pt_package_id: UUID,
) -> int | None:
    """Race-safe increment of ``pt_packages.sessions_remaining`` (PT-18).

    Returns new ``sessions_remaining`` on success; ``None`` on 0-row
    update — a HARD logic error (caller raises 500): the CHECK invariant
    ``sessions_remaining <= session_count_snapshot`` from migration
    0014_pt_packages would be breached, so the predicate
    ``sessions_remaining < session_count_snapshot`` acts as defence-in-
    depth at the application layer. By the time ``cancel_pt_session``
    calls this, we have already observed a recordable session against
    the package, so the ceiling is mathematically impossible to hit.

    Raw ``sa.text()`` SQL referencing ``pt_packages`` by table name
    avoids importing ``app.modules.pt_packages.models.PtPackage`` and
    keeps the ``modules-independent`` importlinter contract green
    (D-34-04a).
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET sessions_remaining = sessions_remaining + 1,
            updated_at = now()
        WHERE id = :pt_package_id
          AND sessions_remaining < session_count_snapshot
        RETURNING sessions_remaining
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.first()
    return None if row is None else int(row[0])


async def fetch_booking_metadata_for_update(
    session: AsyncSession,
    booking_id: UUID,
) -> dict[str, Any] | None:
    """SELECT bookings metadata + acquire row-lock (Phase 38 D-38-11 / D-38-19).

    The ``FOR UPDATE`` clause is the load-bearing piece for Pitfall 12 / D-38-19:
    it acquires a Postgres row-level lock on the booking row that BLOCKS any
    concurrent UPDATE (notably the future Phase 39 no-show cron's batch
    ``UPDATE bookings SET status='no_show' WHERE status='confirmed' AND
    slot.end_time < now()``) until the surrounding ``record_pt_session`` UoW
    commits or rolls back. The cron cannot mis-classify a booking as no-show
    while a delivery is being recorded for it — clean serialization, no
    optimistic-retry loop required.

    Cross-module raw ``sa.text()`` per D-34-04a / Phase 38 D-38-11 — pt_sessions
    NEVER imports the bookings ORM (the modules-independent importlinter
    contract). This is the only allowable place reading the ``bookings``
    table from this module; writes go through the
    ``register_booking_completer`` Protocol slot in
    ``app.core.dependencies.complete_booking_by_pt_session``.

    Returns a flat ``dict`` (``id``, ``status``, ``pt_package_id``, ``slot_id``)
    for the caller's validation chain (status must be 'confirmed';
    pt_package_id must match the request; slot.trainer_id must match the
    session's trainer). ``None`` = row not found, caller raises 404
    ``booking_not_found``.

    Caller-owns-txn (D-03): no flush, no commit.
    """
    stmt = sa.text(
        """
        SELECT id, status, pt_package_id, slot_id
        FROM bookings
        WHERE id = :booking_id
        FOR UPDATE
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
    )
    result = await session.execute(stmt, {"booking_id": booking_id})
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def fetch_slot_trainer_id(
    session: AsyncSession,
    slot_id: UUID,
) -> UUID | None:
    """SELECT trainer_availability_slots.trainer_id (Phase 38 D-38-11 / PKG-04).

    Cross-module raw ``sa.text()`` per D-34-04a / Phase 38 D-38-11 — pt_sessions
    NEVER imports the schedule ORM (modules-independent contract).
    Used by ``record_pt_session`` to enforce that ``request.trainer_id`` matches
    ``slot.trainer_id`` when a booking_id is provided (PKG-04 trainer-mismatch
    guard); a mismatch raises 409 ``booking_mismatch``.

    Returns ``None`` for missing slot id; caller treats as a data-integrity
    edge case (booking.slot_id should always FK-point at a live slot row).

    Caller-owns-txn (D-03): no flush, no commit.
    """
    stmt = sa.text(
        "SELECT trainer_id FROM trainer_availability_slots WHERE id = :slot_id",  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
    )
    result = await session.execute(stmt, {"slot_id": slot_id})
    row = result.first()
    if row is None:
        return None
    trainer_id_raw = row[0]
    # Defence-in-depth coerce (asyncpg returns UUID natively, but a different
    # driver or test stub could return a str).
    if isinstance(trainer_id_raw, UUID):
        return trainer_id_raw
    return UUID(str(trainer_id_raw))


async def atomic_transition_exhausted_to_active(
    session: AsyncSession,
    pt_package_id: UUID,
) -> bool:
    """Flip ``status='exhausted' → 'active'`` for the parent pt_package (PT-18).

    D-34-11a carve-out: this reverse transition is NOT in the global
    ``PT_PACKAGE_STATUS_TRANSITIONS`` FSM (Phase 33 D-33-04 keeps the FSM
    forward-only — ``exhausted → {cancelled}``). The locally-scoped
    invariant "we just freed one balance unit from an exhausted package"
    inside ``cancel_pt_session`` makes the reverse flip safe under the
    predicate ``WHERE status='exhausted'``: a concurrent refund that
    flipped the package to ``cancelled`` mid-tx silently no-ops this
    UPDATE and the audit payload carries ``package_reactivated=False``
    (correctness over intent — T-34-K mitigation).

    Returns ``True`` iff exactly one row transitioned (used to set the
    ``package_reactivated`` audit bool reflecting actual rowcount truth).
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET status = 'active',
            updated_at = now()
        WHERE id = :pt_package_id AND status = 'exhausted'
        RETURNING id
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    return result.first() is not None
