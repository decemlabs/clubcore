"""Memberships service — orchestration between router and repository (Phase 16 D-14).

Module-level async functions (mirroring clients service pattern). Each mutation function:
  1. Calls `repository.<fn>` to prepare / mutate the ORM object.
  2. Handles `IntegrityError` on `uq_membership_plans_name_alive` → raises
     `PlanNameExistsError` (D-02, mirror of clients D-11 / PhoneExistsError).
  3. `await audit.emit(session, ...)` (D-14 co-transactional).
  4. `await session.flush()` to surface DB-level constraint conflicts before route exit.
  5. `await session.commit()` to persist the unit of work.
     Tests use SAVEPOINT-mode session, so commit becomes a nested-transaction release
     that the outer fixture rolls back.

Architectural boundary: `from app.modules.memberships import repository` — the service
never imports `MembershipPlan` ORM at runtime. mypy type-checks via the repository
return-type chain.

Audit emit ordering (D-14):
  - create_plan: insert → flush (surface IntegrityError → 409) →
    emit `membership_plan_created` → commit.
    IntegrityError surfaces only on flush, so we can't emit before confirming the row took.
  - update_plan: get → mutate → if changed_previous empty: return early (no emit,
    no flush, no commit — D-09 idempotent no-op). else: flush → emit
    `membership_plan_updated` → refresh(updated_at) → commit.
  - soft_delete_plan: get → mutate (set deleted_at = now()) → emit
    `membership_plan_archived` → flush → commit.

D-11 audit payload: membership_plan_created = {name, duration_days, price_kopecks}
  (plan_id is in resource_id column, not payload).
D-12 audit payload: membership_plan_updated = {changed_fields} only — no before/after values.
D-13 audit payload: membership_plan_archived = {} — only resource_id carries the plan id.

Constraint name literal: "uq_membership_plans_name_alive" (D-02 — defined in migration
0004_membership_plans.py and __table_args__).

Service does NOT re-check RBAC; the router-layer `require_permission` dependency gates
access before service is called.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import PlanNameExistsError, PlanNotFoundError
from app.core.pagination import PaginatedData
from app.modules.memberships import repository
from app.modules.memberships.schemas import (
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanUpdateRequest,
)


def _is_plan_name_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_membership_plans_name_alive` (D-02).

    Direct mirror of clients `_is_phone_conflict` with constraint name substituted.
    Checks `constraint_name` attribute first (asyncpg exposes this), then falls back
    to substring search on the stringified exception for drivers that don't expose it.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_plans_name_alive":
        return True
    return "uq_membership_plans_name_alive" in str(exc.orig)


async def list_plans(
    session: AsyncSession,
    query: MembershipPlanListQuery,
) -> PaginatedData[MembershipPlanResponse]:
    """Return paginated alive plans matching the query (MEM-PLAN-EP-01).

    Read-side: no audit emit, no actor required. RBAC (`VIEW`, `MEMBERSHIP_PLANS`) is
    enforced at the router layer.
    """
    page = await repository.list_alive(session, query)
    return PaginatedData.model_construct(
        items=[MembershipPlanResponse.model_validate(p) for p in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_plan(
    session: AsyncSession,
    plan_id: UUID,
) -> MembershipPlanResponse:
    """Return alive plan by id; raise 404 for missing/soft-deleted (MEM-PLAN-EP-01)."""
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    return MembershipPlanResponse.model_validate(plan)


async def create_plan(
    session: AsyncSession,
    actor: CurrentUser,
    data: MembershipPlanCreateRequest,
) -> MembershipPlanResponse:
    """Create a new membership plan (MEM-PLAN-EP-02).

    Order: insert → flush (surface DB constraints) → emit audit on success (D-14).
    For inserts we cannot emit before flush — the IntegrityError on
    `uq_membership_plans_name_alive` surfaces only when the row hits the DB. Catching
    the IntegrityError and translating to PlanNameExistsError satisfies D-02.
    """
    plan = await repository.insert_plan(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_plan_name_conflict(exc):
            raise PlanNameExistsError("plan_name_exists") from exc
        raise

    # D-11 membership_plan_created payload: name, duration_days, price_kopecks.
    # plan_id is carried in resource_id (not payload).
    await audit.emit(
        session,
        "membership_plan_created",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
        name=plan.name,
        duration_days=plan.duration_days,
        price_kopecks=plan.price_kopecks,
    )
    await session.commit()
    return MembershipPlanResponse.model_validate(plan)


async def update_plan(
    session: AsyncSession,
    actor: CurrentUser,
    plan_id: UUID,
    data: MembershipPlanUpdateRequest,
) -> MembershipPlanResponse:
    """Partial update with PATCH semantics (MEM-PLAN-EP-03, D-07).

    Skips audit emit + flush + commit when no fields actually changed (D-09 no-op).
    Translates name-uniqueness IntegrityError to PlanNameExistsError (D-02).
    D-12: audit payload carries changed_fields list only — no before/after values.
    """
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")

    # changed_previous: dict[field_name, previous_value] — only fields that
    # actually changed value (after pydantic exclude_unset). Empty dict on no-op.
    changed_previous = await repository.update_plan(session, plan, data)

    if not changed_previous:
        # D-09: idempotent no-op PATCH → skip emit, skip flush, skip commit, return current state.
        return MembershipPlanResponse.model_validate(plan)

    # Flush early to surface name-conflict before emitting audit (D-02). For
    # non-name updates this is a cheap UPDATE; for name changes it gives us
    # the IntegrityError we need to translate.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_plan_name_conflict(exc):
            raise PlanNameExistsError("plan_name_exists") from exc
        raise

    # D-12 membership_plan_updated payload:
    #   - changed_fields: sorted list of field names that actually changed
    #   - NO before/after values for any field (D-12 explicitly excludes them)
    payload: dict[str, Any] = {"changed_fields": sorted(changed_previous.keys())}
    await audit.emit(
        session,
        "membership_plan_updated",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
        **payload,
    )
    # SA 2.0 expires the row's attributes after flush by default. Refresh the
    # ORM-managed `updated_at` (server-side `now()`) before Pydantic serialisation
    # so the response carries the fresh value without triggering an implicit
    # lazy-load (which would raise MissingGreenlet under async).
    await session.refresh(plan, attribute_names=["updated_at"])
    await session.commit()
    return MembershipPlanResponse.model_validate(plan)


async def soft_delete_plan(
    session: AsyncSession,
    actor: CurrentUser,
    plan_id: UUID,
) -> None:
    """Soft-delete the plan (MEM-PLAN-EP-04).

    Owner-only enforcement happens at the router via `require_permission`.
    D-13: audit payload is empty (plan_id is carried in resource_id; no extra fields).
    D-14: emit BEFORE flush — soft-delete only flips deleted_at, no constraint risk.
    D-17: distinct event `membership_plan_archived` (vs PATCH active=false which emits
    `membership_plan_updated`) — two forensically separate archive paths.
    """
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")

    await repository.soft_delete_plan(session, plan)

    # D-13: NO extra payload — resource_id pins the plan; no name capture needed.
    await audit.emit(
        session,
        "membership_plan_archived",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
    )
    await session.flush()
    await session.commit()
