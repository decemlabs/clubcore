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

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedData

__all__ = (
    "client_has_any_membership",
    "fetch_available_slots",
    "fetch_client_me",
    "fetch_client_membership",
    "fetch_client_next_booking",
    "fetch_client_payment_status",
    "fetch_client_payments_page",
    "fetch_client_pt_sessions_page",
    "fetch_client_visits_page",
    "fetch_membership_plans_catalog",
    "fetch_pt_packages_catalog",
    "fetch_trainers_catalog",
    "update_client_profile",
)


async def client_has_any_membership(
    session: AsyncSession,
    client_id: UUID,
) -> bool:
    """True if the client has EVER had any membership row of any status (D-01 lapsed-vs-newbie).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Membership (D-54-08/D-20-MODULE).
    Verified column source:
      memberships (apps/backend/app/modules/memberships/models.py:88-165):
        client_id  UUID FK to clients.id
        status     String(16) IN ('active', 'expired', 'cancelled', 'frozen')

    IDOR: mandatory :client_id bind param cast to str — result is scoped to the caller's
    own client_id; never queries another client's rows.

    Semantics (D-01):
      - A 'newbie' has ZERO membership rows: returns False.
      - A 'lapsed' member has >=1 rows (typically status='expired' or 'cancelled'): returns True.
      - An 'active' member also has >=1 rows (status='active'): returns True.
      The service layer (get_client_home) uses this in combination with the active-membership
      check to derive the ternary 'active' | 'lapsed' | 'newbie' state.
    """
    row = (
        await session.execute(
            text(
                "SELECT EXISTS("
                "SELECT 1 FROM memberships WHERE client_id = :client_id"
                ") AS ever"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one()
    return bool(row["ever"])


async def fetch_available_slots(
    session: AsyncSession,
    *,
    trainer_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], int]:
    """Active future slots bookable by a client (CBOOK-02 / D-70-04 / T-70-13).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of TrainerAvailabilitySlot
    or Trainer.

    Verified column sources:
      trainer_availability_slots (app/modules/schedule/models.py:64-152):
        id           UUID PK
        trainer_id   UUID FK trainers.id
        start_time   DateTime(timezone=True)
        end_time     DateTime(timezone=True)
        status       String(16) IN ('active','booked','cancelled')
      trainers (app/modules/trainers/models.py:23-43):
        id           UUID PK
        full_name    Text NOT NULL
        is_active    Boolean NOT NULL DEFAULT true
        deleted_at   DateTime NULLABLE (SoftDeleteMixin)

    Filters:
      - s.status = 'active' (open for booking; 'booked'/'cancelled' excluded)
      - s.start_time > now() (future slots only)
      - :trainer_id IS NULL OR s.trainer_id = :trainer_id (PT-package trainer pin)
      - t.is_active = true AND t.deleted_at IS NULL (alive trainers only)

    Returns (rows, total) — rows are dicts with slot_id, trainer_id, trainer_name,
    start_time, end_time. No client_id filter here — caller derives trainer_id
    from the client's active PT-package (or None for all trainers).
    No client_id bind: non-owned public catalog filtered by package trainer pin.
    IDOR: client_id does NOT appear in the SQL — ownership is enforced at the
    service layer (the client's active PT-package is resolved first, then
    trainer_id is extracted from it).
    """
    bind: dict[str, object] = {
        "trainer_id": str(trainer_id) if trainer_id is not None else None,
        "limit": limit,
        "offset": offset,
    }

    # Use CAST(:trainer_id AS UUID) to avoid `:name::type` cast syntax which
    # asyncpg/SQLAlchemy text() parser misinterprets as a double-colon escape.
    trainer_filter = (
        "AND s.trainer_id = CAST(:trainer_id AS UUID) "
        if trainer_id is not None
        else ""
    )
    count_bind: dict[str, object] = {
        "trainer_id": str(trainer_id) if trainer_id is not None else None
    }

    # trainer_filter is a fixed string literal (CAST(:trainer_id AS UUID) or ""),
    # not user input — S608 N/A: owned_sql is a fixed string literal constructed
    # from two constant branches; no user-supplied SQL fragments.
    _base_filter = (
        "WHERE s.status = 'active' "
        "  AND s.start_time > now() "
        f"  {trainer_filter}"
        "  AND t.is_active = true "
        "  AND t.deleted_at IS NULL"
    )
    _join = "FROM trainer_availability_slots s JOIN trainers t ON s.trainer_id = t.id "
    count_sql = "SELECT COUNT(*) AS cnt " + _join + _base_filter
    count_row = (
        await session.execute(text(count_sql), count_bind)
    ).mappings().one()
    total = int(count_row["cnt"])

    list_sql = (
        "SELECT s.id AS slot_id, s.trainer_id, t.full_name AS trainer_name, "
        "  s.start_time, s.end_time " + _join + _base_filter
        + " ORDER BY s.start_time ASC LIMIT :limit OFFSET :offset"
    )
    rows = (
        await session.execute(text(list_sql), bind)
    ).mappings().all()

    return [dict(r) for r in rows], total


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
                "price_kopecks_snapshot, "
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


# ---------------------------------------------------------------------------
# Phase 71 CPAY-03 — IDOR-safe coarse payment status reader
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 999.5 Plan 02 — client profile read + write (raw SQL, no ORM import)
# ---------------------------------------------------------------------------


async def fetch_client_me(
    session: AsyncSession,
    client_id: UUID,
) -> dict[str, object]:
    """SELECT clients profile row for /client/me (Phase 999.5 D-08).

    CROSS-MODULE READ — raw SQL only (D-54-08/D-20-MODULE).
    Verified columns: clients (apps/backend/app/modules/clients/models.py):
      id, first_name, last_name, phone, email, goal,
      height_cm, weight_kg, onboarding_completed_at.

    IDOR: mandatory :client_id bind param + deleted_at IS NULL guard.
    D-20-IDOR 404-collapse: None (non-existent or soft-deleted) → NotFoundError.
    """
    row = (
        await session.execute(
            text(
                "SELECT id, first_name, last_name, phone, email, goal, "
                "  height_cm, weight_kg, onboarding_completed_at, notif_prefs "
                "FROM clients WHERE id = :client_id AND deleted_at IS NULL"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    if row is None:
        raise NotFoundError("client_not_found")
    return dict(row)


async def update_client_profile(
    session: AsyncSession,
    *,
    client_id: UUID,
    payload: Any,  # ClientProfileUpdateRequest at runtime
) -> None:
    """Partial UPDATE on clients row — only non-None payload fields written.

    CROSS-MODULE WRITE — raw SQL text() with bind params (D-54-08/D-20-MODULE).
    SET clause is built from FIXED string literals (never user-supplied SQL).
    Only values are parameterized — prevents SQL injection.

    D-05: onboarding_completed=True → sets onboarding_completed_at = now().
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).
    """
    sets: list[str] = []
    bind: dict[str, object] = {"client_id": str(client_id)}

    if payload.first_name is not None:
        sets.append("first_name = :first_name")
        bind["first_name"] = payload.first_name
    if payload.goal is not None:
        sets.append("goal = :goal")
        bind["goal"] = payload.goal
    if payload.height_cm is not None:
        sets.append("height_cm = :height_cm")
        bind["height_cm"] = payload.height_cm
    if payload.weight_kg is not None:
        sets.append("weight_kg = :weight_kg")
        bind["weight_kg"] = payload.weight_kg
    if payload.email is not None:
        sets.append("email = :email")
        bind["email"] = payload.email
    if payload.notif_prefs is not None:
        # D-05: full replace — write all four keys atomically.
        # Fixed SET literal fragment (S608 discipline); value bound as a JSON
        # string and cast to JSONB using CAST syntax (not ::jsonb, which would
        # conflict with SQLAlchemy's :name→$N param substitution in asyncpg).
        sets.append("notif_prefs = CAST(:notif_prefs AS jsonb)")
        bind["notif_prefs"] = json.dumps(payload.notif_prefs.model_dump())
    if payload.onboarding_completed:
        sets.append("onboarding_completed_at = now()")

    if not sets:
        return  # no-op: nothing to write

    # D-06 / route-consolidation: the partial-unique index on lower(email)
    # WHERE deleted_at IS NULL raises IntegrityError on a duplicate email. Map it
    # to a generic non-enumerating 409 (email_unavailable) — preserves the behavior
    # the removed client_auth PATCH /me used to provide. flush() (not commit) so the
    # constraint fires here while the caller still owns the txn (D-32-10/D-49-19).
    try:
        await session.execute(
            text(
                f"UPDATE clients SET {', '.join(sets)} WHERE id = :client_id AND deleted_at IS NULL"  # noqa: S608
            ),
            bind,
        )
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("email_unavailable") from exc


async def fetch_client_payment_status(
    session: AsyncSession,
    payment_id: UUID,
    client_id: UUID,
) -> dict[str, object] | None:
    """Coarse online payment status for a specific client (CPAY-03, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of OnlinePayment.
    Verified columns (apps/backend/app/modules/online_payments/models.py:58-112):
      - id           PgUUID (UUIDPkMixin)
      - client_id    PgUUID NOT NULL (IDOR filter — fk_online_payments_client_id_clients)
      - status       Text NOT NULL ('pending' | 'succeeded' | 'canceled')

    IDOR: mandatory :payment_id AND :client_id bind params — non-owned rows
    return None; service layer raises NotFoundError → 404-collapse (D-20-IDOR).
    Anti-oracle (CPAY-03): SELECT projects ONLY id + status — never exposes
    membership_plan_id, pt_package_plan_id, amount_kopecks, or activation details.
    """
    row = (
        await session.execute(
            text(
                "SELECT id, status FROM online_payments "
                "WHERE id = :payment_id AND client_id = :client_id"
            ),
            {"payment_id": str(payment_id), "client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    return dict(row) if row else None
