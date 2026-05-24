"""Reports repository — raw-SQL read aggregator (Phase 54 INFRA-41 scaffold).

CROSS-MODULE READ DISCIPLINE (D-54-08 / Phase 49 D-49-03 precedent):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().one_or_none()`` for single-row reads.
  - ``.mappings().all()`` for aggregate/list reads.
  - Each reader documents verified columns + source file:line of the foreign table.

This discipline means zero new ``ignore_imports`` edges in ``.importlinter``
while reading across ``payments``, ``memberships``, ``clients``, ``visits``,
and ``audit_log`` tables.

INVARIANTS:
  - ZERO INSERT / UPDATE / DELETE in this file.
  - No ORM model imports from other modules.

Example reader pattern (from app/modules/online_payments/service.py:116-142):

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _read_membership_plan_or_raise(
        session: AsyncSession, plan_id: UUID
    ) -> tuple[int, str]:
        \"\"\"Return (price_kopecks, name) for an alive membership_plans row.

        Verified columns (app/modules/memberships/models.py:58-90):
          - id            PgUUID
          - name          varchar(120)
          - price_kopecks BigInteger
          - deleted_at    nullable timestamptz
        \"\"\"
        row = (
            await session.execute(
                text(
                    "SELECT id, price_kopecks, name FROM membership_plans "
                    "WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": str(plan_id)},
            )
        ).mappings().one_or_none()
        if row is None:
            raise NotFoundError("membership_plan_not_found")
        return int(row["price_kopecks"]), str(row["name"])

Phase 55 will add concrete reader functions for:
  - ``payments`` table — revenue aggregation by day/month (Europe/Moscow).
  - ``memberships`` + ``clients`` tables — active/expiring/new client counts.
  - ``visits`` table — visit counts by gym_date and hour bucket.
"""

from sqlalchemy import (
    text,  # noqa: F401 — imported for pattern documentation; Phase 55 readers use it.
)

__all__: tuple[str, ...] = ()
