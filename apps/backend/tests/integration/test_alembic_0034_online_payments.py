"""Phase 49 PAY-01/PAY-02 — Alembic 0034 ships online_payments + 4 indexes + 4 CHECKs.

D-49-04 + D-49-05 + D-49-06. The migration creates the ``online_payments``
FSM table with:

- 2 full UNIQUE constraints (``yookassa_payment_id``, ``idempotency_key``)
- 2 partial UNIQUE indexes (``uq_online_payments_membership_double_tap``,
  ``uq_online_payments_pt_package_double_tap``) gated by
  ``status != 'canceled' AND <fk> IS NOT NULL``
- 4 CHECK constraints (amount positive, status enum, confirmation_type
  enum, XOR-of-subject-FKs)
- 4 FK columns (clients, membership_plans, pt_package_plans, users)

The ``db_session`` fixture brings the DB up to head via the FastAPI lifespan
that loads ``Base.metadata``; the migration runner is exercised by the
``alembic upgrade head`` / ``alembic downgrade`` shell invocations in
the plan's verify step.
"""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession


async def test_online_payments_table_exists(db_session: AsyncSession) -> None:
    """Schema-shape baseline — table is reachable after upgrade head."""

    def _has_table(sync_conn: object) -> bool:
        inspector = inspect(sync_conn)
        return inspector.has_table("online_payments")

    conn = await db_session.connection()
    has_table = await conn.run_sync(_has_table)
    assert has_table is True


async def test_online_payments_table_has_partial_unique_indexes(
    db_session: AsyncSession,
) -> None:
    """D-49-05 — both partial UNIQUE double-tap indexes ship in 0034."""

    def _indexes(sync_conn: object) -> set[str]:
        inspector = inspect(sync_conn)
        return {ix["name"] for ix in inspector.get_indexes("online_payments")}

    conn = await db_session.connection()
    index_names = await conn.run_sync(_indexes)
    assert "uq_online_payments_membership_double_tap" in index_names
    assert "uq_online_payments_pt_package_double_tap" in index_names


async def test_online_payments_table_has_full_unique_constraints(
    db_session: AsyncSession,
) -> None:
    """D-49-05 — the two non-partial UNIQUEs surface as unique_constraints."""

    def _uqs(sync_conn: object) -> set[str | None]:
        inspector = inspect(sync_conn)
        return {uc["name"] for uc in inspector.get_unique_constraints("online_payments")}

    conn = await db_session.connection()
    uq_names = await conn.run_sync(_uqs)
    assert "uq_online_payments_yookassa_payment_id" in uq_names
    assert "uq_online_payments_idempotency_key" in uq_names


async def test_online_payments_has_xor_and_enum_check_constraints(
    db_session: AsyncSession,
) -> None:
    """D-49-04 — DB-enforced XOR FK + status / confirmation_type / amount CHECKs."""

    def _checks(sync_conn: object) -> set[str | None]:
        inspector = inspect(sync_conn)
        return {cc["name"] for cc in inspector.get_check_constraints("online_payments")}

    conn = await db_session.connection()
    check_names = await conn.run_sync(_checks)
    assert "ck_online_payments_exactly_one_subject_fk" in check_names
    assert "ck_online_payments_status" in check_names
    assert "ck_online_payments_confirmation_type" in check_names
    assert "ck_online_payments_amount_kopecks_positive" in check_names


async def test_online_payments_has_expected_foreign_keys(
    db_session: AsyncSession,
) -> None:
    """D-49-04 — 4 FK columns pointing at clients, membership_plans, pt_package_plans, users."""

    def _fk_targets(sync_conn: object) -> set[str]:
        inspector = inspect(sync_conn)
        return {fk["referred_table"] for fk in inspector.get_foreign_keys("online_payments")}

    conn = await db_session.connection()
    targets = await conn.run_sync(_fk_targets)
    assert {"clients", "membership_plans", "pt_package_plans", "users"} <= targets
