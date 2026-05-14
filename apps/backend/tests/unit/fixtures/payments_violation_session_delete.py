"""Synthetic negative fixture — session.delete(<Payment instance>) (B-01 violation)."""
from app.modules.payments.models import Payment  # type: ignore[import-not-found]


async def violate_session_delete(session, payment: Payment) -> None:  # type: ignore[no-untyped-def]
    await session.delete(payment)
