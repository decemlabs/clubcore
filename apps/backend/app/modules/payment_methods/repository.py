"""Payment methods repository (app.modules.payment_methods.repository) — raw-SQL reads + writes.

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` for all SQL — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().one_or_none()`` for scalar reads.
  - Read-only reads return None if absent (200/null empty-state discipline, D-69-03).

INVARIANTS:
  - ORM model imports from app.modules.*: FORBIDDEN (except this module's own models).
  - ORM model imports from app.core.*: ALLOWED.
  - No session.commit() — caller-owns-txn (D-32-10/D-49-19).
  - SELECT MUST NOT include yookassa_method_id (token never wired to client, T-79-01/T-79-04).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_active_payment_method(
    session: AsyncSession,
    client_id: UUID,
    *,
    for_update: bool = False,
) -> dict[str, Any] | None:
    """Fetch the active (unlinked_at IS NULL) card for a client.

    Returns a dict of display+autopay fields or None when no active card exists.
    NEVER returns yookassa_method_id — caller must never expose that column (T-79-04).

    ``for_update=True`` appends ``FOR UPDATE`` so the read-decide-write autopay
    path locks the row within the caller's transaction (WR-79-03 — closes the
    lost-update race on ``consent_recorded_at`` between concurrent
    enable-autopay / unlink-card requests on the same session). Read-only
    callers (GET) leave it False.
    """
    sql = (
        "SELECT id, last4, brand, expiry_month, expiry_year, "
        "autopay_enabled, consent_recorded_at, created_at "
        "FROM client_payment_methods "
        "WHERE client_id = :client_id AND unlinked_at IS NULL"
    )
    if for_update:
        sql += " FOR UPDATE"
    row = (
        (
            await session.execute(
                text(sql),
                {"client_id": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict[str, Any](row) if row is not None else None


async def unlink_payment_method(
    session: AsyncSession,
    client_id: UUID,
) -> bool:
    """Soft-delete the active card row by setting unlinked_at=now() + autopay_enabled=false.

    Returns True if a row was found and unlinked, False if no active card existed
    (idempotency: feeds 204 no-op at the router level).
    Uses SELECT ... FOR UPDATE to lock the row within the caller's transaction.
    No session.commit() — caller-owns-txn.
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id FROM client_payment_methods "
                    "WHERE client_id = :client_id AND unlinked_at IS NULL "
                    "FOR UPDATE"
                ),
                {"client_id": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return False
    await session.execute(
        text(
            "UPDATE client_payment_methods "
            "SET unlinked_at = now(), autopay_enabled = false "
            "WHERE id = :id"
        ),
        {"id": str(row["id"])},
    )
    return True


async def set_autopay(
    session: AsyncSession,
    client_id: UUID,
    *,
    enabled: bool,
    stamp_consent: bool,
) -> None:
    """Update autopay_enabled for the active card; stamp consent_recorded_at when requested.

    stamp_consent=True: set consent_recorded_at=now() (only when enabling with acknowledgement).
    stamp_consent=False: leave consent_recorded_at unchanged (disable path never touches it).
    No session.commit() — caller-owns-txn.
    """
    if stamp_consent:
        await session.execute(
            text(
                "UPDATE client_payment_methods "
                "SET autopay_enabled = :enabled, consent_recorded_at = now() "
                "WHERE client_id = :client_id AND unlinked_at IS NULL"
            ),
            {"enabled": enabled, "client_id": str(client_id)},
        )
    else:
        await session.execute(
            text(
                "UPDATE client_payment_methods "
                "SET autopay_enabled = :enabled "
                "WHERE client_id = :client_id AND unlinked_at IS NULL"
            ),
            {"enabled": enabled, "client_id": str(client_id)},
        )
