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
  - freeze_membership (Phase 25 D-25-07): load → transition guard → preventive
    limit check → INSERT freeze period → flush (translate IntegrityError on
    `uq_membership_freeze_periods_active_per_membership` → 409 already_frozen) →
    update status='frozen' → flush → emit `membership_frozen` → refresh(updated_at)
    → commit.
  - unfreeze_membership (Phase 25 D-25-08): load → transition guard → load open
    period → close period (set ended_at / ended_by) → extend end_date by
    max(1, ceil(delta_seconds / 86400)) → update status='active' → flush →
    emit `membership_unfrozen` → refresh(updated_at) → commit.
  - cancel_membership (Phase 25 D-25-09 frozen-source extension): when source
    status is 'frozen', close the open period without `end_date` extension and
    emit `membership_unfrozen` (with `days_added=0` sentinel) BEFORE the
    existing `membership_cancelled` emit; both rows live in the same UoW so
    audit_log id auto-increment preserves chronology.

D-11 audit payload: membership_plan_created = {name, duration_days, price_kopecks}
  (plan_id is in resource_id column, not payload).
D-12 audit payload: membership_plan_updated = {changed_fields} only — no before/after values.
D-13 audit payload: membership_plan_archived = {} — only resource_id carries the plan id.

Constraint name literal: "uq_membership_plans_name_alive" (D-02 — defined in migration
0004_membership_plans.py and __table_args__).

Service does NOT re-check RBAC; the router-layer `require_permission` dependency gates
access before service is called.
"""

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    AlreadyFrozenError,
    FreezeLimitExceededError,
    InvalidTransitionError,
    MembershipNotFoundError,
    PlanInactiveError,
    PlanInUseError,
    PlanNameExistsError,
    PlanNotFoundError,
)
from app.core.pagination import PaginatedData
from app.modules.memberships import repository
from app.modules.memberships.constants import MEMBERSHIP_STATUS_TRANSITIONS
from app.modules.memberships.models import Membership
from app.modules.memberships.schemas import (
    FreezePeriodResponse,
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


def _is_already_frozen_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by uq_membership_freeze_periods_active_per_membership.

    Direct mirror of `_is_plan_name_conflict` with constraint name substituted
    (Phase 25 D-25-22). Concurrent-INSERT race on the partial unique index —
    second freeze loses and is translated to 409 `already_frozen` by the
    `freeze_membership` service path.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_freeze_periods_active_per_membership":
        return True
    return "uq_membership_freeze_periods_active_per_membership" in str(exc.orig)


def _assert_can_transition(membership: Membership, *, target: str) -> None:
    """Central state-machine guard (INFRA-16, D-24-04).

    Consults `MEMBERSHIP_STATUS_TRANSITIONS` to decide whether `membership.status
    → target` is allowed; raises `InvalidTransitionError` (409 invalid_transition)
    with discriminating `from_status` / `to_status` payload otherwise.

    The two existing per-action helpers (`_assert_can_cancel`, `_assert_can_expire`)
    delegate to this function — they remain importable so the unit-test matrix
    in `tests/unit/memberships/test_state_machine.py` keeps its 9-cell shape.
    """
    allowed = MEMBERSHIP_STATUS_TRANSITIONS.get(membership.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": target},
        )


def _assert_can_cancel(membership: Membership) -> None:
    """Phase 17 + Phase 25 D-25-09: status='active' OR 'frozen' may transition to 'cancelled'.

    Cancel-during-freeze closes the open period without `end_date` extension and
    emits `membership_unfrozen` (with `days_added=0` sentinel) BEFORE the
    `membership_cancelled` audit row in the same UoW.

    Phase 24 INFRA-16 D-24-05: thin wrapper over `_assert_can_transition`.
    """
    _assert_can_transition(membership, target="cancelled")


def _assert_can_expire(membership: Membership) -> None:
    """Phase 17 D-19: only status='active' may transition to 'expired'.

    Phase 24 INFRA-16 D-24-05: thin wrapper over `_assert_can_transition`.
    """
    _assert_can_transition(membership, target="expired")


def _assert_can_freeze(membership: Membership) -> None:
    """Phase 25 D-25-15: only status='active' may transition to 'frozen'.

    Thin wrapper over `_assert_can_transition` — same Phase 24 D-24-05 pattern.
    """
    _assert_can_transition(membership, target="frozen")


def _assert_can_unfreeze(membership: Membership) -> None:
    """Phase 25 D-25-15: only status='frozen' may transition to 'active'.

    Thin wrapper over `_assert_can_transition` — same Phase 24 D-24-05 pattern.
    """
    _assert_can_transition(membership, target="active")


async def _build_membership_response(  # noqa: SVC001 caller-owns-txn — read-only projection helper
    session: AsyncSession, membership: Membership
) -> MembershipResponse:
    """Project a Membership ORM into MembershipResponse with the 4 freeze fields.

    Phase 25 D-25-12 contract — SOLE single-row projector for MembershipResponse
    in this module. Every read path (`get_membership`) and every mutation
    terminal (`create_membership`, `cancel_membership`, `freeze_membership`,
    `unfreeze_membership`) routes through this helper. `list_memberships`
    inlines an equivalent bulk-projection pattern (with prefetched freeze-period
    maps to avoid N+1 queries) but does NOT call this helper per-row.

    Do NOT call `MembershipResponse.model_validate(membership)` directly —
    Pydantic will raise ValidationError because freeze_days_limit_snapshot /
    freeze_days_used / freeze_days_remaining have no defaults on the schema.

    Locked projection mechanism (revision iteration 1):
      1. `MembershipResponse.model_validate(membership, from_attributes=True)`
         — populates existing ORM-mapped fields plus
         `freeze_days_limit_snapshot` (which IS a real ORM column on
         Membership added in Plan 25-01).
      2. `.model_copy(update={...})` overlays the 3 computed/projected fields.

    This avoids the brittle `**membership.__dict__` pattern (SQLAlchemy state
    attributes pollute the dict) and the executor-discretion shortcut.
    """
    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    days_used = await repository.compute_freeze_days_used(
        session, membership.id, today_msk=today_msk
    )
    remaining = max(0, membership.freeze_days_limit_snapshot - days_used)
    current_period: FreezePeriodResponse | None = None
    if membership.status == "frozen":
        period = await repository.get_open_freeze_period(session, membership.id)
        if period is not None:
            current_period = FreezePeriodResponse.model_validate(
                period, from_attributes=True
            )

    # Step 1: validate base ORM (carries freeze_days_limit_snapshot via from_attributes).
    # Step 2: overlay the 3 service-computed fields (cannot come from ORM).
    overlay = {
        "freeze_days_used": days_used,
        "freeze_days_remaining": remaining,
        "current_freeze_period": current_period,
    }
    return MembershipResponse.model_validate(membership, from_attributes=True).model_copy(update=overlay)  # noqa: E501 -- locked Phase 25 D-25-12 projection pattern; grep-acceptance gate


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
    D-17: distinct event `membership_plan_archived` (vs PATCH active=false which emits
    `membership_plan_updated`) — two forensically separate archive paths.

    Phase 17 D-05 / D-06: ANY Membership row (active, expired, cancelled) blocks
    soft-delete with 409 plan_in_use. We perform an EXPLICIT pre-flight count
    BEFORE issuing the UPDATE. The DB-level FK
    `fk_memberships_plan_id_membership_plans ON DELETE RESTRICT` only fires on
    a true `DELETE FROM membership_plans` statement — it does NOT fire for an
    `UPDATE membership_plans SET deleted_at = now()`. The pre-flight check is
    the correctness gate. The IntegrityError translation below remains as a
    defence-in-depth canary against a future hard-delete refactor (T-CONSTRAINT-DRIFT).
    """
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")

    # D-05 / D-06 pre-flight: any referencing membership row blocks soft-delete.
    # Status is irrelevant — cancelled and expired rows keep their FK pointer
    # for audit-trail integrity (D-06).
    in_use_count = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.plan_id == plan.id)
    )
    if in_use_count and in_use_count > 0:
        raise PlanInUseError("plan_in_use")

    await repository.soft_delete_plan(session, plan)

    # D-13: NO extra payload — resource_id pins the plan; no name capture needed.
    # Emitted BEFORE flush so the audit row is enrolled in the same UoW; if a
    # future hard-delete refactor causes flush to raise FK IntegrityError, the
    # rollback masks both the mutation and the audit row co-transactionally.
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
        # Defence-in-depth: rolls back BOTH the soft-delete AND the audit row
        # (Phase 16 D-14). With the pre-flight check above, this branch
        # should never execute under the current soft-delete model — but it
        # remains as a canary if the implementation switches to hard-delete.
        await session.rollback()
        if _is_plan_in_use_conflict(exc):
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
    # on non-{active,frozen} source state; no partial write.
    _assert_can_cancel(membership)

    # Phase 25 D-25-09: if cancelling from frozen, close the open period first.
    # Audit ordering: emit "membership_unfrozen" (with days_added=0 sentinel)
    # BEFORE the existing "membership_cancelled" emit. Both rows live in the
    # same UoW (single commit at function end); audit_log.id auto-increment
    # provides forensic chronology. NO end_date extension — cancellation
    # supersedes freeze (REQUIREMENTS MEM-FRZ-07).
    if membership.status == "frozen":
        period = await repository.get_open_freeze_period(session, membership.id)
        if period is None:
            raise RuntimeError("frozen_membership_without_open_period")
        period.ended_at = datetime.now(tz=UTC)
        period.ended_by = actor.id
        await session.flush()
        await audit.emit(
            session,
            "membership_unfrozen",  # LITERAL — Phase 15 INFRA-11 AST gate
            actor_user_id=actor.id,
            resource_type="membership",  # LITERAL
            resource_id=membership.id,
            client_id=str(membership.client_id),
            freeze_period_id=str(period.id),
            days_added=0,  # sentinel discriminates cancel-from-frozen in audit log
        )

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


# ===========================================================================
# Phase 25 — Freeze cycle service paths (MEM-FRZ-04..05, D-25-07/08)
# ===========================================================================


async def freeze_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
) -> MembershipResponse:
    """Open a freeze period and transition active → frozen (MEM-FRZ-04).

    Order (Phase 25 D-25-07; mirrors cancel_membership: guard BEFORE mutation):
      1. Load — 404 `membership_not_found` if missing.
      2. Transition guard — 409 `invalid_transition` for non-active source
         (via `_assert_can_freeze` thin wrapper).
      3. Preventive limit check — 409 `freeze_limit_exceeded` when cumulative
         days_used already >= snapshot_limit. Document: this guards on the
         *current* ledger; a concurrent close-then-freeze race is impossible
         because the partial unique index serialises freeze inserts per
         membership_id.
      4. INSERT freeze period → flush → catch IntegrityError → discriminate
         via `_is_already_frozen_conflict` → 409 `already_frozen`.
      5. update_membership_status(status='frozen') — narrow setter (no
         cancelled_at / cancel_reason mutation).
      6. Flush.
      7. audit.emit('membership_frozen', ...) — LITERAL strings; payload
         carries client_id (str-cast for JSONB), freeze_period_id,
         started_at (ISO).
      8. Refresh updated_at for the response.
      9. Commit (SVC001 gate enforces).
     10. Return response via `_build_membership_response` so the 4 freeze
         projection fields populate.
    """
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    _assert_can_freeze(membership)

    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    days_used = await repository.compute_freeze_days_used(
        session, membership.id, today_msk=today_msk
    )
    if days_used >= membership.freeze_days_limit_snapshot:
        raise FreezeLimitExceededError(
            "freeze_limit_exceeded",
            fields={
                "limit": membership.freeze_days_limit_snapshot,
                "used": days_used,
            },
        )

    now_utc = datetime.now(tz=UTC)
    period = await repository.insert_freeze_period(
        session,
        membership_id=membership.id,
        started_by=actor.id,
        started_at=now_utc,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_already_frozen_conflict(exc):
            raise AlreadyFrozenError("already_frozen") from exc
        raise

    await repository.update_membership_status(session, membership, status="frozen")
    await session.flush()

    await audit.emit(
        session,
        "membership_frozen",  # LITERAL — Phase 15 INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        freeze_period_id=str(period.id),
        started_at=period.started_at.isoformat(),
    )

    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()

    return await _build_membership_response(session, membership)


async def unfreeze_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
) -> MembershipResponse:
    """Close open freeze period, extend end_date by ceil days, transition
    frozen → active (MEM-FRZ-05). Half-day rounds up; minimum 1 day.

    Order (Phase 25 D-25-08):
      1. Load — 404 `membership_not_found` if missing.
      2. Transition guard — 409 `invalid_transition` for non-frozen source
         (via `_assert_can_unfreeze` thin wrapper).
      3. Load open period via `get_open_freeze_period`. Defence-in-depth:
         status='frozen' implies an open period exists; if not, raise
         RuntimeError so the inconsistency is surfaced rather than silently
         masked.
      4. Set period.ended_at = now(UTC); period.ended_by = actor.id.
      5. days_added = max(1, ceil(delta_seconds / 86400)) — anti-abuse minimum
         (instant freeze→unfreeze still costs 1 day) + client-favouring
         rounding for partial days.
      6. Extend membership.end_date by days_added.
      7. update_membership_status(status='active').
      8. Flush.
      9. audit.emit('membership_unfrozen', ..., days_added=days_added).
     10. Refresh updated_at.
     11. Commit (SVC001 gate enforces).
     12. Return via `_build_membership_response` (current_freeze_period
         resolves to None — status is now 'active').
    """
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    _assert_can_unfreeze(membership)

    period = await repository.get_open_freeze_period(session, membership.id)
    if period is None:
        # Defence-in-depth: status='frozen' implies open period exists.
        raise RuntimeError("frozen_membership_without_open_period")

    now_utc = datetime.now(tz=UTC)
    period.ended_at = now_utc
    period.ended_by = actor.id

    delta_seconds = (period.ended_at - period.started_at).total_seconds()
    days_added = max(1, math.ceil(delta_seconds / 86400))
    membership.end_date = membership.end_date + timedelta(days=days_added)

    await repository.update_membership_status(session, membership, status="active")
    await session.flush()

    await audit.emit(
        session,
        "membership_unfrozen",  # LITERAL — Phase 15 INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        freeze_period_id=str(period.id),
        days_added=days_added,
    )

    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()

    return await _build_membership_response(session, membership)


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
    *,
    today: date | None = None,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, CD-06, DEBT-01).

    Implements MEM-04 tiebreak via `repository.find_active_for_client`:
    ORDER BY end_date DESC, created_at DESC LIMIT 1 (D-17 — silent, no warning,
    no audit event). Used by the Phase 4 D-24 slot pattern from
    `core/dependencies.py`. Returns the SA ORM `Membership` directly; it
    structurally satisfies the `ActiveMembership` Protocol (D-18, declared in
    core/dependencies.py by Plan 17-02), so no DTO conversion at the resolver
    boundary.

    Public per CD-06 — Phase 17-04 wires this into the resolver registration
    via `register_active_membership_resolver(resolve_active_membership_by_client)`.

    Phase 24 DEBT-01: applies `end_date >= today (Europe/Moscow)` defence-in-depth
    filter via the repository. `today=None` resolves to today in Europe/Moscow
    (mirrors `_expire_due_memberships` injection pattern); tests pass an explicit
    `today` for determinism. Closes the v1.2 MEM-04 D-13 known gap where a missed
    ARQ `expire_memberships` tick could leave a stale `status='active'` row
    passable for visits / Telegram check-in.
    """
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    return await repository.find_active_for_client(session, client_id, today=today)


# ===========================================================================
# Phase 18 — Bulk expire orchestrator (D-01 / D-04 / D-05; ARQ-02)
# ===========================================================================


async def _expire_due_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
) -> int:
    """Bulk-flip overdue active memberships to expired + emit per-row audits.

    Phase 18 D-01: this is a private helper consumed ONLY by
    `app.workers.scheduled.expire_memberships:expire_memberships(ctx)`. The
    worker is the transaction owner and calls `await session.commit()` after
    this function returns. The `# noqa: SVC001 caller-owns-txn` marker on the
    def line is the documented opt-out from the AST commit-gate (Phase 15
    INFRA-13 / D-04: marker valid only on private `_`-prefixed helpers; public
    service functions MUST commit themselves). The leading underscore +
    marker is NOT optional — both are required for the gate to pass.

    Phase 18 D-04: bulk SQL is `UPDATE memberships SET status='expired'
    WHERE end_date < :today AND status='active' RETURNING id, client_id`,
    issued via `repository.expire_due_rows`. The status filter is the
    SQL-level idempotency gate (Pitfall 4 mitigation): a row already flipped
    on a previous run is skipped because the WHERE clause no longer matches.
    ARQ `unique=True` is a second line of defence; the SQL is the real gate.

    Phase 18 D-03 / CD-06: this path deliberately does NOT call
    `_assert_can_expire(membership)` — that helper exists for the Phase 17
    TESTS-10 9-cell unit matrix and is reserved for hypothetical per-row
    flows. Calling it here would force a SELECT-FOR-UPDATE pre-flight (N+1)
    that ROADMAP SC #1 explicitly forbids ("single-transaction UPDATE …
    RETURNING").

    Phase 18 D-05: `today=None` resolves to
    `datetime.now(ZoneInfo("Europe/Moscow")).date()`. Tests pass explicit
    `today` for determinism (the fixture inserts a row with
    `end_date = today - timedelta(days=1)` to fake "yesterday").

    Audit emit per row uses LITERAL strings ("membership_expired" /
    "membership") — required by the Phase 15 INFRA-11 AST taxonomy walker.
    Payload shape `{client_id: str(uuid)}` matches LOCKED_AUDIT_EVENTS line
    110 (`("membership_expired", "membership")`); `membership_id` is carried
    in `resource_id` (UUID column), `actor_user_id=None` because the cron is
    system-driven (research ARCHITECTURE.md `actor_kind = 'system'`).

    Returns the number of newly-expired rows (int) — Phase 18 D-02. The
    worker writes this into ARQ's result store automatically.
    """
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    rows = await repository.expire_due_rows(session, today)

    for membership_id, client_id in rows:
        await audit.emit(
            session,
            "membership_expired",  # LITERAL (Phase 15 INFRA-11 AST gate)
            actor_user_id=None,  # system-driven cron — no human actor
            resource_type="membership",  # LITERAL
            resource_id=membership_id,
            client_id=str(client_id),  # JSONB-serialisable
        )

    return len(rows)
