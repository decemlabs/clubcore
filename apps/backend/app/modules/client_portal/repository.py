"""Client-portal repository (app.modules.client_portal.repository) — raw-SQL read aggregator
across memberships, bookings, pt_sessions, payments, and catalog tables.

Phase 69 — CHOME-01..03, CHIST-01..03, CPLAN-01..03.

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().all()`` for list reads; ``.mappings().one_or_none()`` for scalar reads.
  - ``.mappings().one()`` for COUNT scalar reads.
  - Each reader documents verified columns + source file:line of the foreign table.

INVARIANTS:
  - Read-only: no write SQL in this file.
  - ORM model imports from app.modules.*: FORBIDDEN.
  - ORM model imports from app.core.*: ALLOWED (app.core is a free import target).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData

__all__ = (
    "fetch_client_membership",
    "fetch_client_next_booking",
    "fetch_client_payments_page",
    "fetch_client_pt_sessions_page",
    "fetch_client_visits_page",
    "fetch_membership_plans_catalog",
    "fetch_pt_packages_catalog",
    "fetch_trainers_catalog",
)


async def fetch_client_membership(
    session: AsyncSession,
    client_id: UUID,
) -> dict[str, object] | None:
    """Active membership for a specific client (CHOME-01, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Membership.
    Verified columns (apps/backend/app/modules/memberships/models.py:88-165):
      - status                 String(16) ('active' | 'expired' | 'cancelled' | 'frozen')
      - end_date               Date (inclusive)
      - start_date             Date
      - plan_name_snapshot     String(120) NOT NULL
      - client_id              UUID (FK to clients.id)

    days_until_end computed in SQL via (end_date - now()::date in Europe/Moscow TZ).

    IDOR: mandatory :client_id bind param — result scoped to the caller's
    own client_id; NEVER returns rows for a different client.
    Empty state → None (D-69-03: no active membership is 200 with null, not 404).
    """
    row = (
        await session.execute(
            text(
                "SELECT id, plan_name_snapshot, start_date, end_date, status, "
                "(end_date - (now() AT TIME ZONE 'Europe/Moscow')::date) AS days_until_end "
                "FROM memberships "
                "WHERE client_id = :client_id AND status = 'active' "
                "ORDER BY start_date DESC, created_at DESC LIMIT 1"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    return dict(row) if row else None


async def fetch_client_next_booking(
    session: AsyncSession,
    client_id: UUID,
) -> dict[str, object] | None:
    """Nearest upcoming confirmed booking for a client (CHOME-02, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Booking or TrainerAvailabilitySlot.
    Verified columns:
      bookings (apps/backend/app/modules/bookings/models.py:50-172):
        - client_id   UUID (FK to clients.id)
        - slot_id     UUID (FK to trainer_availability_slots.id)
        - status      String(16) ('confirmed' | 'cancelled' | 'no_show' | 'completed')
      trainer_availability_slots (apps/backend/app/modules/schedule/models.py:64-155):
        - start_time  DateTime(timezone=True)
      trainers (apps/backend/app/modules/trainers/models.py:23-43):
        - full_name   Text NOT NULL

    IDOR: mandatory :client_id bind param. Empty → None (D-69-03, 200 null not 404).
    """
    row = (
        await session.execute(
            text(
                "SELECT b.id, t.full_name AS trainer_name, s.start_time, b.status "
                "FROM bookings b "
                "JOIN trainer_availability_slots s ON b.slot_id = s.id "
                "JOIN trainers t ON s.trainer_id = t.id "
                "WHERE b.client_id = :client_id "
                "  AND b.status = 'confirmed' "
                "  AND s.start_time >= now() "
                "ORDER BY s.start_time ASC "
                "LIMIT 1"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    return dict(row) if row else None


async def fetch_client_visits_page(
    session: AsyncSession,
    client_id: UUID,
    page: int,
    page_size: int,
) -> PaginatedData[dict[str, object]]:
    """Paginated visit history for a client (CHIST-01, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit.
    Verified columns (apps/backend/app/modules/visits/models.py:43-113):
      - client_id      UUID (FK to clients.id)
      - gym_date       Date STORED GENERATED (checked_in_at AT TIME ZONE 'Europe/Moscow')::date
      - checked_in_at  DateTime(timezone=True)

    IDOR: mandatory :client_id bind param on both COUNT and SELECT.
    Empty state → empty items list, total=0 (D-69-03: own-scope empty is 200/[], not 404).
    """
    count_row = (
        await session.execute(
            text("SELECT COUNT(*) AS cnt FROM visits WHERE client_id = :client_id"),
            {"client_id": str(client_id)},
        )
    ).mappings().one()
    total = int(count_row["cnt"])
    offset = (page - 1) * page_size
    rows = (
        await session.execute(
            text(
                "SELECT id, gym_date, checked_in_at "
                "FROM visits WHERE client_id = :client_id "
                "ORDER BY gym_date DESC, checked_in_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {"client_id": str(client_id), "limit": page_size, "offset": offset},
        )
    ).mappings().all()
    return PaginatedData(
        items=[dict(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def fetch_client_pt_sessions_page(
    session: AsyncSession,
    client_id: UUID,
    page: int,
    page_size: int,
) -> PaginatedData[dict[str, object]]:
    """Paginated PT-session history for a client (CHIST-02, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of PtSession or PtPackage.
    Verified columns:
      pt_sessions (apps/backend/app/modules/pt_sessions/models.py:47-142):
        - pt_package_id        UUID (FK to pt_packages.id)
        - trainer_name_snapshot Text NOT NULL (snapshot at record time)
        - performed_at         DateTime(timezone=True)
        - cancelled_at         DateTime(timezone=True) NULLABLE
      pt_packages (apps/backend/app/modules/pt_packages/models.py:90-187):
        - client_id            UUID (FK to clients.id)

    IDOR: ownership resolved by JOIN to pt_packages ON pt_sessions.pt_package_id =
    pt_packages.id WHERE pt_packages.client_id = :client_id (CHIST-02 — ownership
    via pt_packages.client_id, never a direct pt_sessions.client_id column).
    COUNT mirrors the same JOIN+filter.
    """
    count_row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt "
                "FROM pt_sessions ps "
                "JOIN pt_packages pkg ON ps.pt_package_id = pkg.id "
                "WHERE pkg.client_id = :client_id"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one()
    total = int(count_row["cnt"])
    offset = (page - 1) * page_size
    rows = (
        await session.execute(
            text(
                "SELECT ps.id, ps.trainer_name_snapshot, ps.performed_at, ps.cancelled_at "
                "FROM pt_sessions ps "
                "JOIN pt_packages pkg ON ps.pt_package_id = pkg.id "
                "WHERE pkg.client_id = :client_id "
                "ORDER BY ps.performed_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {"client_id": str(client_id), "limit": page_size, "offset": offset},
        )
    ).mappings().all()
    return PaginatedData(
        items=[dict(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def fetch_client_payments_page(
    session: AsyncSession,
    client_id: UUID,
    page: int,
    page_size: int,
) -> PaginatedData[dict[str, object]]:
    """Paginated payment + refund history for a client (CHIST-03, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Payment.
    Verified columns (apps/backend/app/modules/payments/models.py:44-98):
      - subject_kind    Text ('membership' | 'pt_package' | 'refund')
      - amount_kopecks  Integer (signed; negative for refunds)
      - method          Text ('cash' | 'online')
      - received_at     DateTime(timezone=True)

    Payments table has NO client_id FK — ownership scoped by joining through the
    subject table (memberships or pt_packages by subject_id).
    Subject-kind 'refund' rows are linked by refund_of to a positive payment row.

    Ownership filter: payments whose subject_kind IN ('membership','pt_package') AND
    subject_id matches a membership/pt_package owned by :client_id; plus refund rows
    linked to those payments via refund_of.

    Simplified IDOR approach: join memberships and pt_packages by subject_id to confirm
    client ownership, union with refund rows linked to owned payments.
    """
    # Ownership-scoped payment query: a payment is "owned" by the client when its
    # subject is a membership/pt_package that belongs to the client, or when it is a
    # refund row linked to such a payment. All filtering is via :client_id bind param
    # — no user-supplied SQL fragments (S608 N/A: owned_sql is a fixed string literal).
    owned_sql = """
        WITH owned_payments AS (
            SELECT p.id, p.subject_kind, p.amount_kopecks, p.method, p.received_at
            FROM payments p
            WHERE
              (p.subject_kind = 'membership'
               AND EXISTS (
                   SELECT 1 FROM memberships m
                   WHERE m.id = p.subject_id AND m.client_id = :client_id
               ))
              OR
              (p.subject_kind = 'pt_package'
               AND EXISTS (
                   SELECT 1 FROM pt_packages pkg
                   WHERE pkg.id = p.subject_id AND pkg.client_id = :client_id
               ))
              OR
              (p.subject_kind = 'refund' AND p.refund_of IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM payments orig
                   WHERE orig.id = p.refund_of
                   AND (
                     (orig.subject_kind = 'membership'
                      AND EXISTS (
                          SELECT 1 FROM memberships m
                          WHERE m.id = orig.subject_id
                          AND m.client_id = :client_id
                      ))
                     OR
                     (orig.subject_kind = 'pt_package'
                      AND EXISTS (
                          SELECT 1 FROM pt_packages pkg
                          WHERE pkg.id = orig.subject_id
                          AND pkg.client_id = :client_id
                      ))
                   )
               ))
        )
    """

    count_row = (
        await session.execute(
            text(owned_sql + "SELECT COUNT(*) AS cnt FROM owned_payments"),  # noqa: S608
            {"client_id": str(client_id)},
        )
    ).mappings().one()
    total = int(count_row["cnt"])
    offset = (page - 1) * page_size
    rows = (
        await session.execute(
            text(
                owned_sql
                + "SELECT id, subject_kind, amount_kopecks, method, received_at "
                "FROM owned_payments "
                "ORDER BY received_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {"client_id": str(client_id), "limit": page_size, "offset": offset},
        )
    ).mappings().all()
    return PaginatedData(
        items=[dict(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def fetch_membership_plans_catalog(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Active membership plan catalog — client-safe fields only (CPLAN-01, D-69-05).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of MembershipPlan.
    Verified columns (apps/backend/app/modules/memberships/models.py:55-85):
      - name            String(120) NOT NULL
      - duration_days   Integer NOT NULL
      - price_kopecks   BigInteger NOT NULL
      - active          Boolean NOT NULL DEFAULT true
      - deleted_at      DateTime NULLABLE (SoftDeleteMixin)

    Client-safe projection: id, name, price_kopecks, duration_days only.
    Filters: active = true AND deleted_at IS NULL.
    No freeze_days_limit, no audit fields (D-69-05).
    No client_id (public-to-authed-client catalog).
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, name, price_kopecks, duration_days "
                "FROM membership_plans "
                "WHERE active = true AND deleted_at IS NULL "
                "ORDER BY price_kopecks ASC"
            ),
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_pt_packages_catalog(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Active PT-package plan catalog — client-safe fields only (CPLAN-02, D-69-05).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of PtPackagePlan.
    Verified columns (apps/backend/app/modules/pt_packages/models.py:61-87):
      - name             String(120) NOT NULL
      - session_count    Integer NOT NULL
      - price_kopecks    BigInteger NOT NULL
      - deleted_at       DateTime NULLABLE (SoftDeleteMixin)

    Client-safe projection: id, name, session_count, price_kopecks only.
    Filters: deleted_at IS NULL (SoftDeleteMixin gate — plan is alive).
    No client_id (public-to-authed-client catalog).
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, name, session_count, price_kopecks "
                "FROM pt_package_plans "
                "WHERE deleted_at IS NULL "
                "ORDER BY price_kopecks ASC"
            ),
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_trainers_catalog(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Active trainers catalog — client-safe fields only (CPLAN-03, D-69-05).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Trainer.
    Verified columns (apps/backend/app/modules/trainers/models.py:23-43):
      - full_name    Text NOT NULL
      - is_active    Boolean NOT NULL DEFAULT true
      - deleted_at   DateTime NULLABLE (SoftDeleteMixin)

    Client-safe projection: id, full_name only.
    Filters: is_active = true AND deleted_at IS NULL.
    NO rates, NO phone, NO is_active flag in output, NO audit fields (D-69-05).
    No client_id (public-to-authed-client catalog).
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, full_name "
                "FROM trainers "
                "WHERE is_active = true AND deleted_at IS NULL "
                "ORDER BY full_name ASC"
            ),
        )
    ).mappings().all()
    return [dict(r) for r in rows]
