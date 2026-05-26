"""Synthetic negative fixture — on_conflict_do_update against Payment (B-01 / D-30-08)."""

from sqlalchemy.dialects.postgresql import insert  # type: ignore[import-not-found]

from app.modules.payments.models import Payment  # type: ignore[import-not-found]


async def violate_on_conflict(session) -> None:  # type: ignore[no-untyped-def]
    stmt = insert(Payment).values().on_conflict_do_update(index_elements=["id"], set_={})
    await session.execute(stmt)
