"""PT-packages service — orchestration between router and repository (Phase 33).

Module-level async functions (mirror clients / memberships service pattern).

Discipline invariants (Phase 30 walkers — all must remain green):
  - SVC001 caller-owns-txn (test_service_commit_gate): every public mutating
    orchestrator MUST end with `await session.commit()`. Private helpers may
    use `# noqa: SVC001 caller-owns-txn` on the def line.
  - audit.emit literal-string AST gate (INFRA-11 / test_audit_taxonomy):
    every emit() call uses literal strings for `event` and `resource_type`.
  - audit_payloads.py extra='forbid' validation (D-30-03): emit kwargs MUST
    match the per-event Pydantic schema (PtPackagePlanCreatedPayload /
    PtPackagePlanUpdatedPayload / PtPackagePlanArchivedPayload). Drift
    causes pydantic.ValidationError at runtime.
  - modules-independent contract (.importlinter / Phase 30 INFRA-20):
    NO direct imports of app.modules.{memberships,payments,trainers,clients,
    users}. Cross-module communication is via app.core.* Protocol slots
    (Plans 33-02 and 33-03 consume `get_payment_recorder()` /
    `get_payment_refunder()` for the sale + refund flows).

Phase 33 Plan 33-01 scope (this file):
  - Plan-CRUD service paths (create / update / archive) — all 3 own UoW and
    emit one audit event each.
  - FSM guard (_assert_can_transition + _assert_can_cancel / _expire / _exhaust)
    + constraint-name discriminators — exposed for sibling Plans 33-02 / 33-03.
  - 7 error classes — `FieldImmutableError`, `PtPackagePlanNotFoundError`,
    `PtPackagePlanInUseError`, `PtPackagePlanNameConflictError`,
    `PtPackageNotFoundError`, `ActivePtPackageAlreadyExistsError`,
    `InvalidTransitionError`. Pre-provided here so sibling plans need not
    edit service.py during Wave 2.
  - `resolve_active_pt_package` public resolver delegate — Plan 33-02 wires
    this into `core.dependencies` via `register_active_pt_package_resolver`.

Constraint name literals (D-33 mirrors):
  - "uq_pt_package_plans_name_alive"        — discriminator for plan-name 409
  - "uq_pt_packages_active_per_client"      — discriminator for active-pkg race 409
Both defined in migrations 0013 / 0014 and __table_args__ in models.py.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedData
from app.modules.pt_packages import repository
from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_packages.schemas import (
    PtPackagePlanCreateRequest,
    PtPackagePlanListQuery,
    PtPackagePlanResponse,
    PtPackagePlanUpdateRequest,
)

# ---------------------------------------------------------------------------
# Error classes (per-module subclasses with .code class attribute)
# ---------------------------------------------------------------------------


class PtPackagePlanNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted plan."""

    code = "pt_package_plan_not_found"
    status_code = 404


class PtPackagePlanNameConflictError(ConflictError):
    """Raised on POST/PATCH when name collides with an alive plan (D-33-02 mirror of D-02).

    Discriminated against IntegrityError by service.py:_is_pt_package_plan_name_conflict
    checking constraint name "uq_pt_package_plans_name_alive".
    """

    code = "pt_package_plan_name_conflict"
    status_code = 409


class PtPackagePlanInUseError(ConflictError):
    """Raised on DELETE /pt-package-plans when at least one pt_packages row references
    the plan (D-33-08; pre-flight via repository.has_instances_for_plan).
    """

    code = "plan_in_use"
    status_code = 409


class FieldImmutableError(ConflictError):
    """Raised on PATCH /pt-package-plans when a mutation targets an immutable field
    (session_count / price_kopecks / validity_days) per D-33-07.

    Fields payload carries ``{"field": <field_name>}`` so admin-web can surface
    a precise message. 409 (NOT 422) — the schema layer admits the keys to
    enable this discrimination.
    """

    code = "field_immutable"
    status_code = 409


class PtPackageNotFoundError(NotFoundError):
    """Raised when GET / cancel / refund references a non-existent PT-package id."""

    code = "pt_package_not_found"
    status_code = 404


class ActivePtPackageAlreadyExistsError(ConflictError):
    """Raised on POST /pt-packages when the client already has an active PT-package.

    Plan 33-02 (sale flow / D-33-09) catches IntegrityError on
    ``uq_pt_packages_active_per_client`` via _is_active_pt_package_conflict
    discriminator AND performs a defensive pre-flight via
    repository.find_active_for_client. Both branches raise this error.
    """

    code = "active_pt_package_already_exists"
    status_code = 409


class InvalidTransitionError(ConflictError):
    """Raised by ``_assert_can_transition`` on disallowed PT-package status moves.

    Constructor populates ``fields={'from_status': ..., 'to_status': ...}``.
    Mirrors memberships InvalidTransitionError shape but lives in this module
    so importlinter modules-independent contract stays clean.
    """

    code = "invalid_transition"
    status_code = 409


# ---------------------------------------------------------------------------
# Constraint-name discriminators (mirror memberships.service _is_plan_name_conflict)
# ---------------------------------------------------------------------------


def _is_pt_package_plan_name_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_pt_package_plans_name_alive` (D-33-02).

    Mirrors memberships._is_plan_name_conflict. Checks the `constraint_name`
    attribute first (asyncpg exposes it), then falls back to substring search
    on the stringified exception for drivers that don't expose it.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_pt_package_plans_name_alive":
        return True
    return "uq_pt_package_plans_name_alive" in str(exc.orig)


def _is_active_pt_package_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_pt_packages_active_per_client` (D-33-09).

    Sibling Plan 33-02 (sale flow) translates this IntegrityError to 409
    ``active_pt_package_already_exists``. Provided here so service.py is
    not re-edited in Wave 2.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_pt_packages_active_per_client":
        return True
    return "uq_pt_packages_active_per_client" in str(exc.orig)


# ---------------------------------------------------------------------------
# FSM guards (D-33-04 / mirror memberships._assert_can_transition)
# ---------------------------------------------------------------------------


def _assert_can_transition(pt_package: PtPackage, *, target: str) -> None:
    """Central state-machine guard (D-33-04).

    Consults `PT_PACKAGE_STATUS_TRANSITIONS` to decide whether
    `pt_package.status → target` is allowed; raises ``InvalidTransitionError``
    (409 invalid_transition) with discriminating `from_status` / `to_status`
    payload otherwise.
    """
    allowed = PT_PACKAGE_STATUS_TRANSITIONS.get(pt_package.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": pt_package.status, "to_status": target},
        )


def _assert_can_cancel(pt_package: PtPackage) -> None:
    """D-33-04: cancellation is allowed from active / exhausted / expired sources.

    Cancelled source → 409 ``invalid_transition``. Used by cancel-without-refund
    (Plan 33-03) AND refund (Plan 33-03; refund transitions to cancelled with
    the 'refunded' sentinel).
    """
    _assert_can_transition(pt_package, target="cancelled")


def _assert_can_expire(pt_package: PtPackage) -> None:
    """D-33-04: only active source may transition to expired (ARQ cron — Plan 33-02)."""
    _assert_can_transition(pt_package, target="expired")


def _assert_can_exhaust(pt_package: PtPackage) -> None:
    """D-33-04: only active source may transition to exhausted (Phase 34 PT-session decrement)."""
    _assert_can_transition(pt_package, target="exhausted")


# ---------------------------------------------------------------------------
# Immutability gate helper (D-33-07) — extracted so unit tests can target it
# directly without spinning up a DB session.
# ---------------------------------------------------------------------------


def _validate_immutability(
    plan: PtPackagePlan, data: PtPackagePlanUpdateRequest
) -> None:
    """Raise FieldImmutableError if a non-None update value differs from current.

    D-33-07: session_count / price_kopecks / validity_days are all immutable
    post-creation. The schema includes them as Optional so the service layer
    can discriminate 409 ``field_immutable`` from stock 422 ``extra='forbid'``.

    A matching value (e.g., {"session_count": current_value}) is a no-op and
    does NOT raise — only an actual mutation does.
    """
    if data.session_count is not None and data.session_count != plan.session_count:
        raise FieldImmutableError(
            "field_immutable", fields={"field": "session_count"}
        )
    if data.price_kopecks is not None and data.price_kopecks != plan.price_kopecks:
        raise FieldImmutableError(
            "field_immutable", fields={"field": "price_kopecks"}
        )
    if data.validity_days is not None and data.validity_days != plan.validity_days:
        raise FieldImmutableError(
            "field_immutable", fields={"field": "validity_days"}
        )


# ---------------------------------------------------------------------------
# Plan-CRUD public read paths (no audit, no commit)
# ---------------------------------------------------------------------------


async def list_pt_package_plans(
    session: AsyncSession,
    query: PtPackagePlanListQuery,
) -> PaginatedData[PtPackagePlanResponse]:
    """Return paginated plans matching the query (PT-02 / D-33-06)."""
    page = await repository.list_plans_paginated(session, query)
    return PaginatedData.model_construct(
        items=[PtPackagePlanResponse.model_validate(p) for p in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_pt_package_plan(
    session: AsyncSession,
    plan_id: UUID,
) -> PtPackagePlanResponse:
    """Return alive plan by id; 404 ``pt_package_plan_not_found`` otherwise."""
    plan = await repository.get_plan_alive(session, plan_id)
    if plan is None:
        raise PtPackagePlanNotFoundError("pt_package_plan_not_found")
    return PtPackagePlanResponse.model_validate(plan)


# ---------------------------------------------------------------------------
# Plan-CRUD public mutators (each owns UoW + emits one audit event)
# ---------------------------------------------------------------------------


async def create_pt_package_plan(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtPackagePlanCreateRequest,
) -> PtPackagePlanResponse:
    """Create a new PT-package plan (PT-02 / D-33-02 + D-33-15).

    Order:
      1. Insert via repository.insert_plan.
      2. Flush — surfaces ``uq_pt_package_plans_name_alive`` 409 conflict.
      3. Emit ``pt_package_plan_created`` (payload matches
         PtPackagePlanCreatedPayload extra='forbid' — D-30-03 / D-33-15).
      4. Commit (SVC001 gate).
    """
    plan = await repository.insert_plan(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_pt_package_plan_name_conflict(exc):
            raise PtPackagePlanNameConflictError(
                "pt_package_plan_name_conflict"
            ) from exc
        raise

    # D-33-15: payload must match PtPackagePlanCreatedPayload exactly —
    # {plan_id, name, session_count, price_kopecks, validity_days}.
    # plan_id is the same UUID as resource_id (carried via both columns —
    # resource_id is the DB column on audit_log, plan_id is in the JSONB
    # payload for downstream query convenience).
    await audit.emit(
        session,
        "pt_package_plan_created",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="pt_package_plan",  # LITERAL
        resource_id=plan.id,
        plan_id=plan.id,
        name=plan.name,
        session_count=plan.session_count,
        price_kopecks=plan.price_kopecks,
        validity_days=plan.validity_days,
    )
    await session.commit()
    return PtPackagePlanResponse.model_validate(plan)


async def update_pt_package_plan(
    session: AsyncSession,
    actor: CurrentUser,
    plan_id: UUID,
    data: PtPackagePlanUpdateRequest,
) -> PtPackagePlanResponse:
    """Patch a plan; 409 ``field_immutable`` on session_count / price_kopecks /
    validity_days mutation attempts (D-33-07).

    Order:
      1. Load via repository.get_plan_alive (404 if archived/missing).
      2. Immutability gate (_validate_immutability) — raises FieldImmutableError
         BEFORE any mutation so 409 leaves zero side effects.
      3. Apply mutable updates via repository.update_plan_row (returns
         ``{field: previous_value}`` for changed fields).
      4. If nothing changed → early return (no audit emit, no commit) —
         mirrors memberships D-09 idempotent-no-op PATCH semantics.
      5. Flush — surfaces name-conflict 409.
      6. Emit ``pt_package_plan_updated`` with ``changed_fields`` payload.
      7. Refresh updated_at; commit.
    """
    plan = await repository.get_plan_alive(session, plan_id)
    if plan is None:
        raise PtPackagePlanNotFoundError("pt_package_plan_not_found")

    # D-33-07 immutability gate — BEFORE any mutation.
    _validate_immutability(plan, data)

    changed = await repository.update_plan_row(session, plan, name=data.name)
    if not changed:
        # No-op PATCH (name omitted or unchanged) → return current state,
        # skip audit + commit (mirrors memberships D-09).
        return PtPackagePlanResponse.model_validate(plan)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_pt_package_plan_name_conflict(exc):
            raise PtPackagePlanNameConflictError(
                "pt_package_plan_name_conflict"
            ) from exc
        raise

    # D-33-15: PtPackagePlanUpdatedPayload requires {plan_id, changed_fields}.
    payload: dict[str, Any] = {
        "plan_id": plan.id,
        "changed_fields": sorted(changed.keys()),
    }
    await audit.emit(
        session,
        "pt_package_plan_updated",  # LITERAL
        actor_user_id=actor.id,
        resource_type="pt_package_plan",  # LITERAL
        resource_id=plan.id,
        **payload,
    )
    await session.refresh(plan, attribute_names=["updated_at"])
    await session.commit()
    return PtPackagePlanResponse.model_validate(plan)


async def archive_pt_package_plan(
    session: AsyncSession,
    actor: CurrentUser,
    plan_id: UUID,
) -> None:
    """Soft-delete a plan (D-33-08); 409 ``plan_in_use`` if any pt_packages row references it.

    Order:
      1. Load via repository.get_plan_alive (404 if already archived/missing).
      2. Pre-flight repository.has_instances_for_plan → 409 plan_in_use.
      3. Flip deleted_at = now(UTC).
      4. Emit ``pt_package_plan_archived`` with {plan_id} payload.
      5. Flush + commit.
    """
    plan = await repository.get_plan_alive(session, plan_id)
    if plan is None:
        raise PtPackagePlanNotFoundError("pt_package_plan_not_found")

    if await repository.has_instances_for_plan(session, plan.id):
        raise PtPackagePlanInUseError("plan_in_use")

    await repository.soft_delete_plan(session, plan)

    # D-33-15: PtPackagePlanArchivedPayload requires {plan_id} only —
    # NO `name` field (extra='forbid' would reject it).
    await audit.emit(
        session,
        "pt_package_plan_archived",  # LITERAL
        actor_user_id=actor.id,
        resource_type="pt_package_plan",  # LITERAL
        resource_id=plan.id,
        plan_id=plan.id,
    )
    await session.flush()
    await session.commit()


# ---------------------------------------------------------------------------
# Active-PT-package resolver (D-33-12) — Plan 33-02 wires this into
# `core.dependencies.register_active_pt_package_resolver` from app/main.py.
# Plan 33-02 will own the dependency wiring; service.py exports the function.
# ---------------------------------------------------------------------------


async def resolve_active_pt_package(
    session: AsyncSession, client_id: UUID
) -> PtPackage | None:
    """Public resolver delegate (D-33-12).

    Phase 34 PT-session sale consumes via the ``ActivePtPackage`` Protocol
    slot in ``core.dependencies``. Silent-None semantics (mirror
    ``_active_membership_resolver``): None = "no active package", not an
    error.
    """
    return await repository.find_active_for_client(session, client_id)
