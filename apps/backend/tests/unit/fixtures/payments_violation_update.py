"""Synthetic negative fixture — UPDATE against Payment (B-01 violation).

Imported by test_payments_appendonly.py to assert the walker catches the
update(Payment) shape. NOT executed at runtime; parsed by the AST walker only.
"""

from sqlalchemy import update  # type: ignore[import-not-found]

from app.modules.payments.models import Payment  # type: ignore[import-not-found]


async def violate_update(session) -> None:  # type: ignore[no-untyped-def]
    await session.execute(update(Payment).where(Payment.id == "x").values(amount_kopecks=0))
