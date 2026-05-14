"""Payments models stub (Phase 30 INFRA-22 / B-01).

Minimal `Payment` declarative class exists in Phase 30 so the append-only
AST walker (`tests/unit/test_payments_appendonly.py`) can resolve the
`from app.modules.payments.models import Payment` import-tracking target.
Substantive columns/constraints (UUIDv4 PK, signed amount_kopecks, CHECK
on subject_kind, partial UNIQUE on refund_of) land in Phase 32 PAY-01
(migration `0012_payments.py` per ROADMAP Phase 32 SC #1 / D-30-10).

D-30-10 invariant: this file MUST NOT cause Alembic autogenerate to emit
a placeholder migration in Phase 30. Alembic auto-discovery outcome is
MANUAL (see 30-03-SUMMARY.md): `apps/backend/alembic/env.py` lists ORM
modules explicitly (`import app.modules.auth.models`, `clients.models`,
`memberships.models`, `visits.models`); `app.modules.payments.models` is
NOT in that list, so `Base.metadata` does NOT collect a `payments` table
during `alembic upgrade` / `alembic check`. Strategy: UNCONDITIONAL
declarative class is safe and house-style consistent.
"""

from __future__ import annotations

from app.core.database import Base, UUIDPkMixin


class Payment(UUIDPkMixin, Base):
    """Minimal stub. Real columns/constraints land in Phase 32 PAY-01.

    UUIDPkMixin supplies the `id` primary-key column (D-15 / INFRA-02).
    The substantive PAY-01 schema (amount_kopecks, subject_kind, method,
    refund_of, payment_row_hash, audit columns) is added by ALTER in
    Phase 32 — `0012_payments.py` — not by replacement of this class.
    """

    __tablename__ = "payments"
