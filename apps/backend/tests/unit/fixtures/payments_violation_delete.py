"""Synthetic negative fixture — DELETE against Payment (B-01 violation)."""

from sqlalchemy import delete  # type: ignore[import-not-found]

from app.modules.payments.models import Payment  # type: ignore[import-not-found]


async def violate_delete(session) -> None:  # type: ignore[no-untyped-def]
    await session.execute(delete(Payment).where(Payment.id == "x"))
