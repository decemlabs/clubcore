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

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    InvalidTransitionError,
    MembershipNotFoundError,
    PlanInactiveError,
    PlanInUseError,
    PlanNameExistsError,
    PlanNotFoundError,
)
from app.core.pagination import PaginatedData
from app.modules.memberships import repository
from app.modules.memberships.models import Membership
from app.modules.memberships.schemas import (
    MembershipCancelRequest,
    MembershipCreateRequest,
    MembershipListQuery,
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanUpdateRequest,
    MembershipResponse,
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


def _is_plan_in_use_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was the FK `fk_memberships_plan_id_membership_plans` (D-05).

    Direct mirror of `_is_plan_name_conflict` with the constraint name swapped to
    the FK name. Different SA error class internally (FK ON DELETE RESTRICT vs
    UNIQUE) but identical translation control flow. asyncpg exposes
    `constraint_name` for both; the `in str(exc.orig)` substring fallback covers
    drivers that don't.

    Per D-06: ANY membership row triggers this — active, expired, AND cancelled.
    The helper does not inspect status; it just identifies the FK shape.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "fk_memberships_plan_id_membership_plans":
        return True
    return "fk_memberships_plan_id_membership_plans" in str(exc.orig)


def _assert_can_cancel(membership: Membership) -> None:
    """Phase 17 D-12 + D-15: only status='active' may transition to 'cancelled'.

    Raised BEFORE any mutation so 409 path leaves zero side effects (D-15
    invariant). Per D-13, end_date being past is irrelevant — Phase 18 ARQ
    has not yet flipped status, so the status field is the gate.
    """
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )


def _assert_can_expire(membership: Membership) -> None:
    """Phase 17 D-19: only status='active' may transition to 'expired'.

    Used by the Phase 18 ARQ scheduled-task path (membership_expired audit
    event). Same shape as `_assert_can_cancel` — guard before mutation, raise
    on non-active source state.
    """
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "expired"},
        )


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
    D-14: emit BEFORE flush — soft-delete only flips deleted_at, BUT the flush
    fires `fk_memberships_plan_id_membership_plans` if any Membership row still
    references this plan (Phase 17 D-05 / D-06: cancelled & expired rows ALSO
    block per the "audit-trail keeps the FK" rule). On FK reject, rollback unwinds
    BOTH the soft-delete AND the audit row co-transactionally (Phase 16 D-14).
    D-17: distinct event `membership_plan_archived` (vs PATCH active=false which emits
    `membership_plan_updated`) — two forensically separate archive paths.
    """
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")

    await repository.soft_delete_plan(session, plan)

    # D-13: NO extra payload — resource_id pins the plan; no name capture needed.
    # Emitted BEFORE flush so the audit row is enrolled in the same UoW; if the
    # flush below raises FK IntegrityError, the rollback masks it co-transactionally.
    await audit.emit(
        session,
        "membership_plan_archived",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        # Rolls back BOTH the soft-delete AND the audit row (Phase 16 D-14).
        await session.rollback()
        if _is_plan_in_use_conflict(exc):
            # Phase 17 D-05 / D-06: ANY membership (active/expired/cancelled) blocks.
            raise PlanInUseError("plan_in_use") from exc
        raise
    await session.commit()


# ===========================================================================
# Phase 17 — Membership instance service paths (MEM-EP-01..04, MEM-AUDIT-01)
# ===========================================================================


async def create_membership(
    session: AsyncSession,
    actor: CurrentUser,
    data: MembershipCreateRequest,
) -> MembershipResponse:
    """Sell a membership (MEM-EP-02).

    Order (Phase 17 D-02 / D-04 / D-08 / D-14):
      1. Resolve plan via `repository.get_alive` — 404 if missing/soft-deleted.
      2. Reject inactive plan — 409 `plan_inactive` (D-02; defence against UI bypass
         where reception's filtered list omits inactive plans but a replayed POST
         can still reference one).
      3. Server-compute dates (D-04): start_date = now(Europe/Moscow)::date;
         end_date = start_date + (duration_days_snapshot - 1) — INCLUSIVE.
      4. Insert with snapshot fields copied from the resolved plan ORM ref.
      5. Flush — surfaces any FK error on `client_id` (e.g. soft-deleted client).
      6. `audit.emit('membership_created', ...)` — MEM-AUDIT-01 payload
         {membership_id [resource_id], client_id, plan_id, end_date}.
         Emitted BEFORE commit per Phase 16 D-14 co-transactional contract.
      7. Commit.

    D-01: NO pre-flight active-membership check. Stacking is allowed; the resolver
    tiebreaks on (end_date DESC, created_at DESC LIMIT 1).
    """
    # 1 + 2: resolve and validate plan
    plan = await repository.get_alive(session, data.plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    if not plan.active:
        raise PlanInactiveError("plan_inactive")

    # 3: server-compute dates (D-04 — Moscow TZ, end_date inclusive)
    start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
    end_date = start_date + timedelta(days=plan.duration_days - 1)

    # 4 + 5: insert with snapshot, then flush to surface FK errors
    membership = await repository.insert_membership(
        session,
        data,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
    )
    await session.flush()

    # 6: emit audit BEFORE commit (Phase 16 D-14 co-transactional contract).
    # MEM-AUDIT-01 payload: membership_id is in resource_id; payload carries
    # client_id, plan_id (str-cast for JSONB-serialisability — UUIDs are not
    # natively JSON-serialisable), end_date (ISO string).
    await audit.emit(
        session,
        "membership_created",  # LITERAL (Phase 15 D-11 — AST gate enforces)
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        plan_id=str(membership.plan_id),
        end_date=membership.end_date.isoformat(),
    )
    # 7: commit the unit of work (SVC001 AST gate enforces explicit commit)
    await session.commit()
    return MembershipResponse.model_validate(membership)


async def cancel_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
    data: MembershipCancelRequest,
) -> MembershipResponse:
    """Cancel a membership (MEM-EP-04, owner-only at the router).

    Order (Phase 17 D-12 + D-14 + D-15 + D-16):
      1. Load row — 404 `membership_not_found` if missing.
      2. Transition guard `_assert_can_cancel(membership)` BEFORE any mutation
         (D-15 invariant — non-active source state raises 409 `invalid_transition`
         leaving zero side effects).
      3. Mutate via `update_membership_status` — status='cancelled',
         cancelled_at=now(UTC), cancel_reason=data.reason.
      4. Flush.
      5. Audit emit — payload OMITS `reason` key when None (D-14 — not `reason=None`).
      6. Refresh `updated_at` so the response carries the fresh server-side timestamp.
      7. Commit.
    """
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    # D-15: transition guard BEFORE any mutation. Raises InvalidTransitionError
    # on non-active source state; no partial write.
    _assert_can_cancel(membership)

    # D-12: mutate (cancelled_at uses UTC; the column is timestamptz so the wall-time
    # encoding is preserved regardless of zone).
    await repository.update_membership_status(
        session,
        membership,
        status="cancelled",
        cancelled_at=datetime.now(tz=UTC),
        cancel_reason=data.reason,
    )
    await session.flush()

    # D-14: emit audit BEFORE commit; OMIT `reason` key when None (NOT reason=None).
    # client_id is str-cast for JSONB-serialisability (UUIDs are not natively
    # JSON-serialisable); resource_id stays UUID-typed (column is UUID, not JSONB).
    kwargs: dict[str, Any] = {} if data.reason is None else {"reason": data.reason}
    await audit.emit(
        session,
        "membership_cancelled",  # LITERAL
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        **kwargs,
    )
    # SA 2.0 expires attributes after flush; refresh `updated_at` for response.
    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()
    return MembershipResponse.model_validate(membership)


async def list_memberships(
    session: AsyncSession,
    query: MembershipListQuery,
) -> PaginatedData[MembershipResponse]:
    """Return paginated memberships matching the query (MEM-EP-01).

    Read-side: no audit emit, no actor. RBAC is enforced at the router.
    """
    page = await repository.list_memberships(session, query)
    return PaginatedData.model_construct(
        items=[MembershipResponse.model_validate(m) for m in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_membership(
    session: AsyncSession,
    membership_id: UUID,
) -> MembershipResponse:
    """Return a membership by id; raise 404 if missing (MEM-EP-03)."""
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")
    return MembershipResponse.model_validate(membership)


async def resolve_active_membership_by_client(
    session: AsyncSession,
    client_id: UUID,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, CD-06).

    Implements MEM-04 tiebreak via `repository.find_active_for_client`:
    ORDER BY end_date DESC, created_at DESC LIMIT 1 (D-17 — silent, no warning,
    no audit event). Used by the Phase 4 D-24 slot pattern from
    `core/dependencies.py`. Returns the SA ORM `Membership` directly; it
    structurally satisfies the `ActiveMembership` Protocol (D-18, declared in
    core/dependencies.py by Plan 17-02), so no DTO conversion at the resolver
    boundary.

    Public per CD-06 — Phase 17-04 wires this into the resolver registration
    via `register_active_membership_resolver(resolve_active_membership_by_client)`.
    """
    return await repository.find_active_for_client(session, client_id)
