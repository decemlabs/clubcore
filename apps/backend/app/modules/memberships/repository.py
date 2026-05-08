"""Memberships repository — single point of access to the `MembershipPlan` ORM (MEM-PLAN-02).

This is the ONLY module in the codebase that imports the `MembershipPlan` ORM model.
The service layer calls these module-level async helpers and never executes
`select(MembershipPlan)` directly. That single rule constructively guarantees
MEM-PLAN-02: "all queries through `list_alive` / `get_alive`".

Soft-delete invariant: every read helper appends `MembershipPlan.deleted_at IS NULL`
as the first predicate. `soft_delete_plan` is the ONLY mutation point that touches
`deleted_at`.

Transaction control: NO `session.commit()` and NO `session.flush()` calls live here.
The caller (service) owns the transactional moment so it can co-write the audit log
row in the same UoW (D-14, mirroring clients D-03).

`from __future__ import annotations` is required: `list_alive` is annotated with
`PaginatedData[MembershipPlan]`, and `MembershipPlan` is a SQLAlchemy ORM class
without a Pydantic core schema. Without PEP 563 deferred evaluation, importing this
module triggers `PaginatedData.__class_getitem__(MembershipPlan)` at runtime, which
delegates to Pydantic's generic schema-builder and raises `PydanticSchemaGenerationError`.
Deferring annotation evaluation keeps the type information for mypy while preventing
the import-time schema build (mirrors clients/repository.py:18-23).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, Row, Select, Subquery, and_, func, select, text, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.core.pagination import PaginatedData
from app.modules.memberships.models import Membership, MembershipFreezePeriod, MembershipPlan
from app.modules.memberships.schemas import (
    MembershipCreateRequest,
    MembershipListQuery,
    MembershipListSort,
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanSort,
    MembershipPlanUpdateRequest,
    MembershipStatus,
)


async def get_alive(session: AsyncSession, plan_id: UUID) -> MembershipPlan | None:
    """Return alive plan by id, or None for missing/soft-deleted (MEM-PLAN-02)."""
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(
        MembershipPlan.id == plan_id,
        MembershipPlan.deleted_at.is_(None),
    )
    result: MembershipPlan | None = await session.scalar(stmt)
    return result


async def list_alive(
    session: AsyncSession, query: MembershipPlanListQuery
) -> PaginatedData[MembershipPlan]:
    """Paginated list of alive plans with optional active filter + sort applied (MEM-PLAN-EP-01).

    Returns a `PaginatedData` instance constructed via `model_construct` to skip
    Pydantic validation against the generic parameter. The SQLAlchemy `MembershipPlan`
    ORM is not a Pydantic-compatible type and `PaginatedData[MembershipPlan](...)` would
    trigger a `PydanticSchemaGenerationError` at the runtime parametrisation step.
    The service layer immediately re-wraps the result as `PaginatedData[MembershipPlanResponse]`,
    so skipping validation here is safe.

    D-08: default filter = alive only; optional `?active` filter; no `?q` (D-09).
    """
    predicates: list[Any] = [MembershipPlan.deleted_at.is_(None)]

    # D-08: optional active filter; omit = both active and inactive alive rows.
    if query.active is not None:
        predicates.append(MembershipPlan.active == query.active)

    # Total count — same predicate list, no ORDER/LIMIT.
    total_stmt = select(func.count()).select_from(MembershipPlan).where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    # Items
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(and_(*predicates))
    if query.sort == MembershipPlanSort.NAME_ASC:
        # Case-insensitive sort; stable tie-break on created_at desc.
        stmt = stmt.order_by(
            func.lower(MembershipPlan.name).asc(), MembershipPlan.created_at.desc()
        )
    else:  # default CREATED_AT_DESC
        # Stable tie-break on id desc.
        stmt = stmt.order_by(MembershipPlan.created_at.desc(), MembershipPlan.id.desc())

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def insert_plan(
    session: AsyncSession,
    data: MembershipPlanCreateRequest,
) -> MembershipPlan:
    """Insert a new plan; caller owns the transactional flush + audit emit (D-14).

    No `created_by_user_id` parameter — plans have no creator FK (MEM-PLAN-01).
    No flush() here — caller (service) catches IntegrityError on its own flush call.
    """
    plan = MembershipPlan(
        name=data.name,
        duration_days=data.duration_days,
        price_kopecks=data.price_kopecks,
        active=data.active,
    )
    session.add(plan)
    return plan


async def update_plan(
    session: AsyncSession,
    plan: MembershipPlan,
    data: MembershipPlanUpdateRequest,
) -> dict[str, object]:
    """Apply PATCH update to an existing alive MembershipPlan.

    Returns a dict of {field_name: previous_value} for the fields that actually
    changed. Service layer uses this to (a) decide whether to emit
    `membership_plan_updated` (D-09 no-op skip) and (b) build the
    `changed_fields` audit payload (D-12).

    Keys can only be `name | price_kopecks | active` because `MembershipPlanUpdateRequest`
    declares no other writable fields (D-07, D-04).
    """
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}

    for key, value in updates.items():
        previous = getattr(plan, key)
        if previous != value:
            changed[key] = previous
            setattr(plan, key, value)

    return changed


async def soft_delete_plan(session: AsyncSession, plan: MembershipPlan) -> MembershipPlan:
    """Soft-delete: set deleted_at to now(); never DELETE the row (MEM-PLAN-02)."""
    plan.deleted_at = datetime.now(tz=UTC)
    return plan


# ===========================================================================
# Phase 17 — Membership instance helpers (MEM-01..04)
# ===========================================================================


async def insert_membership(
    session: AsyncSession,
    data: MembershipCreateRequest,
    *,
    plan: MembershipPlan,
    start_date: date,
    end_date: date,
) -> Membership:
    """Create a Membership row. Caller MUST flush + commit (D-04 + Phase 16 pattern).

    Snapshot fields are copied from the resolved `plan` ORM ref so subsequent
    plan edits never propagate to this row (locked MEM-02). `activation_policy`
    is intentionally omitted — server_default `'purchase_date'` covers it.
    """
    membership = Membership(
        client_id=data.client_id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        start_date=start_date,
        end_date=end_date,
        status="active",
        paid_at=data.paid_at,
        notes=data.notes,
    )
    session.add(membership)
    return membership


async def get_membership(session: AsyncSession, membership_id: UUID) -> Membership | None:
    """Return Membership by id, or None.

    NO soft-delete filter — Memberships have no `deleted_at` column (Phase 17 D-12 /
    CONTEXT.md domain line 12). Cancelled/expired rows are still returned;
    lifecycle is purely status-based.
    """
    stmt: Select[tuple[Membership]] = select(Membership).where(Membership.id == membership_id)
    result: Membership | None = await session.scalar(stmt)
    return result


async def list_memberships(
    session: AsyncSession, query: MembershipListQuery
) -> PaginatedData[Membership]:
    """Paginated list of memberships with optional client_id + status filters (Phase 17 D-09).

    No `deleted_at` filter — Memberships use status, not soft-delete (D-12).
    Sort enum branches per D-09; default CREATED_AT_DESC. Stable tie-break
    appended on every branch (id desc) so identical timestamps don't shuffle
    between pages.

    Phase 24 DEBT-02 (D-24-10..D-24-12): `?expiring=true` forces
    `status='active'` and adds the inclusive date-window predicate
    `today <= end_date <= today + (within - 1)` (Europe/Moscow `today`
    resolved here so the repository owns its own clock — the resolver path
    keeps the explicit-`today`-kwarg purity, but `list_memberships` is the
    operator-facing endpoint and resolves wall-clock once per call). When
    `expiring=False`, `query.within` is silently ignored. Conflict — caller
    passed `status` non-active alongside `expiring=true` — raises
    `ValidationAppError("query_invalid", ...)` -> 422 (D-24-11; no silent
    override).

    Returns `PaginatedData[Membership]` via `model_construct` to skip Pydantic
    validation against the SA ORM generic parameter (mirrors `list_alive`
    rationale at line 60-65 above).
    """
    predicates: list[Any] = []

    if query.client_id is not None:
        predicates.append(Membership.client_id == query.client_id)

    if query.expiring:
        # D-24-11: conflict — expiring forces active; explicit non-active 422.
        if query.status is not None and query.status != MembershipStatus.ACTIVE:
            err = ValidationAppError(
                "query_invalid",
                fields={"status": "incompatible_with_expiring"},
            )
            # AppError stores positional arg as `message`; set `code` per contract.
            err.code = "query_invalid"
            raise err
        # D-24-12: inclusive window — end_date in [today, today + (within - 1)].
        # `today` resolves to Europe/Moscow per S-5 (mirrors _expire_due_memberships).
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
        predicates.append(Membership.status == "active")
        predicates.append(Membership.end_date >= today)
        predicates.append(Membership.end_date <= today + timedelta(days=query.within - 1))
    else:
        # D-24-10: when expiring=False, `within` is silently ignored.
        if query.status is not None:
            predicates.append(Membership.status == query.status.value)

    where_clause = and_(*predicates) if predicates else true()

    total_stmt = select(func.count()).select_from(Membership).where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[Membership]] = select(Membership).where(where_clause)
    if query.sort == MembershipListSort.END_DATE_DESC:
        stmt = stmt.order_by(
            Membership.end_date.desc(),
            Membership.created_at.desc(),
            Membership.id.desc(),
        )
    elif query.sort == MembershipListSort.START_DATE_DESC:
        stmt = stmt.order_by(
            Membership.start_date.desc(),
            Membership.created_at.desc(),
            Membership.id.desc(),
        )
    else:  # CREATED_AT_DESC default
        stmt = stmt.order_by(Membership.created_at.desc(), Membership.id.desc())

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def update_membership_status(
    session: AsyncSession,
    membership: Membership,
    *,
    status: str,
    cancelled_at: datetime | None = None,
    cancel_reason: str | None = None,
) -> Membership:
    """Narrow setter for lifecycle transitions (D-12, D-19).

    Used by both cancel (active -> cancelled, sets cancelled_at + reason) and
    Phase 18 ARQ expire (active -> expired, no extra fields). Caller owns
    flush + commit. No model_dump diff: lifecycle transitions touch a fixed
    set of fields, and audit payload is hand-built per event.
    """
    membership.status = status
    if cancelled_at is not None:
        membership.cancelled_at = cancelled_at
    if cancel_reason is not None:
        membership.cancel_reason = cancel_reason
    return membership


async def find_active_for_client(
    session: AsyncSession,
    client_id: UUID,
    *,
    today: date,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, DEBT-01).

    Tiebreak: ORDER BY end_date DESC, created_at DESC LIMIT 1 (D-17 — silent,
    no structlog warning, no audit event). The composite index
    `ix_memberships_client_id_status_end_date` on
    `(client_id, status, end_date DESC)` covers this query (rightmost column
    is range-scan friendly for the new `end_date >= today` predicate).

    Date filter (DEBT-01, Phase 24): we apply `end_date >= today` here as a
    defence-in-depth backstop. Phase 18's ARQ `expire_memberships` cron is
    the primary `active → expired` flipper, but a missed tick (worker crash,
    deploy window) would otherwise leave a stale `status='active'` row
    passable for visits / Telegram check-in. The resolver is the ultimate
    gate, so it filters by date as well.

    `today` is a required keyword-only argument; callers MUST resolve their
    Europe/Moscow `date` before calling (the service-layer wrapper
    `service.resolve_active_membership_by_client` does this).
    """
    stmt = (
        select(Membership)
        .where(
            Membership.client_id == client_id,
            Membership.status == "active",
            Membership.end_date >= today,
        )
        .order_by(Membership.end_date.desc(), Membership.created_at.desc())
        .limit(1)
    )
    result: Membership | None = await session.scalar(stmt)
    return result


# ===========================================================================
# Phase 18 — Bulk-expire helper (ARQ-02 / D-01 / D-04 / D-05)
# ===========================================================================


async def expire_due_rows(
    session: AsyncSession, today: date
) -> Sequence[Row[tuple[UUID, UUID]]]:
    """Bulk-flip overdue active memberships to expired (Phase 18 D-01 / D-04 / ARQ-02).

    Single-statement `UPDATE memberships SET status='expired' WHERE end_date < :today
    AND status='active' RETURNING id, client_id`. Caller (worker entry via
    `_expire_due_memberships` in service.py) owns flush + commit; this helper
    issues no flush, no commit (mirrors clients D-03 / Phase 16 D-14 — Phase 18
    D-01 inverts the commit ownership: worker is transaction owner, not service).

    Status filter is the SQL-level idempotency gate (Pitfall 4): a row already
    flipped to 'expired' on a previous run is skipped because it no longer
    matches `status='active'`. ARQ `unique=True` is a necessary-not-sufficient
    second line of defence; the SQL is the real gate.

    Inclusive `end_date` semantics (Phase 15 PROJECT.md Key Decisions): the
    strict `<` comparison means a membership ending today stays 'active' until
    tomorrow morning's tick.

    `today` is a `date` (not `CURRENT_DATE`) so the comparison is TZ-unambiguous
    even though the worker container runs `TZ=UTC` (Phase 18 D-05). Production
    callers pass `today=datetime.now(ZoneInfo("Europe/Moscow")).date()`; tests
    pass an explicit `today` for determinism.

    Returns the result of `.all()` on the RETURNING result — a Sequence of
    Row[(membership_id, client_id)] tuples. Caller iterates emitting per-row
    audit events.
    """
    stmt = (
        update(Membership)
        .where(Membership.end_date < today, Membership.status == "active")
        .values(status="expired")
        .returning(Membership.id, Membership.client_id)
    )
    result = await session.execute(stmt)
    return result.all()


# ===========================================================================
# Phase 25 — MembershipFreezePeriod helpers (D-25-16, D-25-18)
# ===========================================================================


async def insert_freeze_period(
    session: AsyncSession,
    *,
    membership_id: UUID,
    started_by: UUID,
    started_at: datetime,
) -> MembershipFreezePeriod:
    """Insert an open freeze period (Phase 25 D-25-16).

    Caller (service) owns flush + commit and handles IntegrityError on the
    partial unique index ``uq_membership_freeze_periods_active_per_membership``
    (raised via ``_is_already_frozen_conflict`` discriminator in Plan 25-03).
    """
    period = MembershipFreezePeriod(
        membership_id=membership_id,
        started_by=started_by,
        started_at=started_at,
        # ended_at intentionally omitted — NULL while period is open.
    )
    session.add(period)
    return period


async def get_open_freeze_period(
    session: AsyncSession, membership_id: UUID
) -> MembershipFreezePeriod | None:
    """Return the open freeze period for ``membership_id``, or None (D-25-16).

    Defence-in-depth: if status='frozen' but no open period exists, that is a
    DB-level invariant violation (manual SQL surgery, bug). Caller raises.
    """
    stmt = (
        select(MembershipFreezePeriod)
        .where(
            MembershipFreezePeriod.membership_id == membership_id,
            MembershipFreezePeriod.ended_at.is_(None),
        )
        .limit(1)
    )
    result: MembershipFreezePeriod | None = await session.scalar(stmt)
    return result


async def get_freeze_period_by_id(
    session: AsyncSession, period_id: UUID
) -> MembershipFreezePeriod | None:
    """Return a freeze period by id, or None. Used by tests / debug paths (D-25-16)."""
    return await session.get(MembershipFreezePeriod, period_id)
