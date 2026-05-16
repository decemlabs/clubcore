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

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pt_sessions.models import PtSession


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
    )
    session.add(pt_session)
    return pt_session
