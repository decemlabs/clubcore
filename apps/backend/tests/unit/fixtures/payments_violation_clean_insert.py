"""Positive control — INSERT-only is allowed (D-30-08).

This fixture is named `payments_violation_clean_insert.py` for filesystem
grouping with sibling fixtures, but it is NOT a violation: the walker MUST
NOT flag it. Tested by `test_walker_passes_clean_insert_fixture`.
"""

from sqlalchemy import insert  # type: ignore[import-not-found]

from app.modules.payments.models import Payment  # type: ignore[import-not-found]


async def clean_insert(session) -> None:  # type: ignore[no-untyped-def]
    session.add(Payment())
    await session.execute(insert(Payment).values())
