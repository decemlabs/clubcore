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

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser, get_payment_recorder, get_payment_refunder
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.pagination import PaginatedData
from app.modules.pt_packages import repository
from app.modules.pt_packages.constants import (
    CANCELLATION_REASON_REFUNDED,
    PAYMENT_SUBJECT_KIND_PT_PACKAGE,
    PT_PACKAGE_STATUS_TRANSITIONS,
)
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_packages.schemas import (
    PtPackageCancelRequest,
    PtPackageCreateRequest,
    PtPackageListQuery,
    PtPackagePlanCreateRequest,
    PtPackagePlanListQuery,
    PtPackagePlanResponse,
    PtPackagePlanUpdateRequest,
    PtPackageRefundRequest,
    PtPackageResponse,
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


# ---------------------------------------------------------------------------
# Instance-side orchestrators (Plan 33-02 — sale + read APIs)
# ---------------------------------------------------------------------------


async def create_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtPackageCreateRequest,
) -> PtPackageResponse:
    """Sell a PT-package (Phase 33 PT-07 / D-33-09 / D-33-17 / D-33-16).

    Owns the UoW (await session.commit() at end). 10-step recipe:
      1. Load plan via repository.get_plan_alive (404 pt_package_plan_not_found
         when missing or archived — D-33-08 archive guard).
      2. Server-enforced snapshot symmetry (D-33-17) — reject
         ``amount_kopecks != plan.price_kopecks`` with 422 ``amount_mismatch``
         BEFORE any side effect (no instance row, no payment row, no audit).
      3. Defensive pre-flight: reject if client already has an active
         PT-package (D-33-09). Partial UNIQUE
         ``uq_pt_packages_active_per_client`` is the DB-final race gate;
         pre-check is the friendly 409 path.
      4. Server-compute dates (D-33-09 / mirrors memberships D-04):
         ``start_date = now(Europe/Moscow)::date``;
         ``end_date = start_date + plan.validity_days - 1`` (inclusive) when
         ``plan.validity_days IS NOT NULL`` else NULL (бессрочный — D-33-14).
      5. Insert pt_packages row with full snapshot suite + sessions_remaining
         = plan.session_count + status='active' via repository.insert_pt_package.
      6. ``await session.flush()`` — surfaces FK errors on client_id (e.g.
         soft-deleted client) and the partial UNIQUE on active-per-client
         (race-safe DB gate) which is translated to 409
         ``active_pt_package_already_exists`` via
         _is_active_pt_package_conflict.
      7. Record payment in the same UoW via the ``get_payment_recorder()``
         Protocol slot (modules-independent contract — NEVER direct payments
         import). Server derives ``amount_kopecks`` from the snapshot — client
         cannot supply it.
      8. ``audit.emit('pt_package_sold', ...)`` with payload matching the
         additively-extended PtPackageSoldPayload schema (10 keys: 9 D-33-15
         verbatim keys + payment_id forensic anchor).
      9. ``await session.commit()`` (SVC001 gate).
      10. Return PtPackageResponse with computed ``is_active`` field.
    """
    # 1: load alive plan (404 pt_package_plan_not_found if archived/missing).
    plan = await repository.get_plan_alive(session, data.plan_id)
    if plan is None:
        raise PtPackagePlanNotFoundError("pt_package_plan_not_found")

    # 2: snapshot symmetry server-enforcement (D-33-17). Reject mismatched
    # amounts BEFORE any mutation — no pt_packages row, no payments row,
    # no audit emit. Fields payload discriminates the failure for
    # admin-web (mirrors Phase 32 amount_mismatch shape).
    if data.amount_kopecks != plan.price_kopecks:
        raise ValidationAppError(
            "amount_mismatch",
            fields={
                "expected": plan.price_kopecks,
                "received": data.amount_kopecks,
            },
        )

    # 3: defensive pre-flight on active-per-client invariant. DB partial
    # UNIQUE is the final race gate (step 6); this is the friendly path
    # that surfaces the 409 without bumping into IntegrityError.
    existing = await repository.find_active_for_client(session, data.client_id)
    if existing is not None:
        raise ActivePtPackageAlreadyExistsError(
            "active_pt_package_already_exists"
        )

    # 4: server-compute dates (Europe/Moscow business day; inclusive end).
    start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
    end_date: date | None = (
        start_date + timedelta(days=plan.validity_days - 1)
        if plan.validity_days is not None
        else None
    )

    # 5 + 6: insert with snapshot, flush to surface DB-final 409 race gate.
    pt_package = await repository.insert_pt_package(
        session,
        data,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_active_pt_package_conflict(exc):
            raise ActivePtPackageAlreadyExistsError(
                "active_pt_package_already_exists"
            ) from exc
        raise

    # 7: record payment in the same UoW via Protocol slot (modules-independent
    # contract — NEVER `from app.modules.payments import ...`). Server derives
    # amount from the snapshot — client cannot supply it (D-33-17 invariant).
    # Recorder is caller-owns-txn: internally flushes + emits payment_recorded
    # audit but does NOT commit. We own the surrounding UoW.
    payment = await get_payment_recorder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package.id,
        amount_kopecks=pt_package.price_kopecks_snapshot,
        method="cash",
        received_by_user_id=actor.id,
        audit_actor=actor,
    )

    # 8: emit subject-side audit BEFORE commit (Phase 16 D-14 co-transactional).
    # Payload matches the additively-extended PtPackageSoldPayload schema:
    # 9 D-33-15 verbatim keys + payment_id forensic anchor (10 total).
    # `start_date` / `end_date` are passed as `date` objects — the schema
    # accepts `date` and `date | None` (audit_payloads.py / Phase 33
    # additive extension). UUIDs are JSONB-serialisable via Pydantic.
    # Payload kwargs use str / ISO-string casts so the JSONB column stores
    # natively-serialisable values (psycopg has no default adapter for UUID /
    # date). Pydantic's PtPackageSoldPayload schema coerces ISO strings back
    # to UUID / date during validate (D-30-03 extra='forbid' enforcement).
    # Mirrors `memberships.service.create_membership` precedent.
    await audit.emit(
        session,
        "pt_package_sold",  # LITERAL (INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        plan_id=str(pt_package.plan_id),
        plan_name_snapshot=pt_package.plan_name_snapshot,
        session_count_snapshot=pt_package.session_count_snapshot,
        price_kopecks_snapshot=pt_package.price_kopecks_snapshot,
        validity_days_snapshot=pt_package.validity_days_snapshot,
        start_date=pt_package.start_date.isoformat(),
        end_date=(
            pt_package.end_date.isoformat()
            if pt_package.end_date is not None
            else None
        ),
        payment_id=str(payment.id),
    )

    # 9: commit (SVC001 AST gate enforces explicit commit on orchestrator).
    await session.commit()

    # 10: refresh + return response (computed is_active derived from status).
    await session.refresh(pt_package)
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)


async def get_pt_package_by_id(
    session: AsyncSession,
    pt_package_id: UUID,
) -> PtPackageResponse:
    """Read a single PT-package instance (D-33-06 read tier; reception+owner).

    Pure read — does NOT commit. Returns the full snapshot suite +
    sessions_remaining + start/end_date + status + computed ``is_active``.
    """
    pt_package = await repository.get_pt_package(session, pt_package_id)
    if pt_package is None:
        raise PtPackageNotFoundError("pt_package_not_found")
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)


async def list_pt_packages(
    session: AsyncSession,
    query: PtPackageListQuery,
) -> PaginatedData[PtPackageResponse]:
    """Paginated PT-package list with optional client_id + status filters.

    Read tier — reception+owner (D-33-06). Returns envelope {items, total,
    page, pageSize}.
    """
    page = await repository.list_pt_packages_paginated(session, query)
    return PaginatedData.model_construct(
        items=[
            PtPackageResponse.model_validate(p, from_attributes=True)
            for p in page.items
        ],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


# ---------------------------------------------------------------------------
# ARQ cron helper (Plan 33-02 / D-33-13 / D-33-14)
# ---------------------------------------------------------------------------


async def _expire_due_pt_packages(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
) -> int:
    """Bulk-flip overdue active PT-packages to expired (D-33-13).

    Caller-owns-txn helper. The ARQ worker
    (``app.workers.scheduled.expire_pt_packages.expire_pt_packages``) is the
    transaction owner — this helper issues the bulk UPDATE + per-row audit
    emit BUT does NOT commit. The ``# noqa: SVC001 caller-owns-txn`` marker
    on the def line is the Phase 30 INFRA-21 walker contract.

    Idempotency: ``WHERE status='active'`` predicate (in the repository
    helper) makes same-day re-runs no-ops. NULL-end-date rows are excluded
    by the SQL filter — бессрочные packages never expire by time
    (D-33-14 contract).

    Args:
        session: AsyncSession in an active transaction (worker-owned).
        today: Override the comparison date (tests pass a fixed date for
            determinism). Production passes None → defaults to
            ``now(Europe/Moscow)::date``.

    Returns:
        int — number of rows whose status flipped from 'active' to 'expired'
        on this run.
    """
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    rows = await repository.expire_due_pt_packages_bulk_returning(session, today)

    for row in rows:
        pt_package_id, client_id, row_end_date = row
        # row_end_date is `date | None` at the type-system level but the
        # SQL `end_date IS NOT NULL` predicate guarantees non-None here.
        # Defensive isinstance check for mypy + future-proofing.
        end_iso = row_end_date.isoformat() if isinstance(row_end_date, date) else ""
        await audit.emit(
            session,
            "pt_package_expired",  # LITERAL (INFRA-11 AST gate)
            actor_user_id=None,  # system-driven cron
            resource_type="pt_package",  # LITERAL
            resource_id=pt_package_id,
            pt_package_id=str(pt_package_id),
            client_id=str(client_id),
            end_date=end_iso,  # PtPackageExpiredPayload expects ISO str
        )

    return len(rows)


# ---------------------------------------------------------------------------
# Plan 33-03 — Cancel + Refund terminal-lifecycle orchestrators
# ---------------------------------------------------------------------------


async def cancel_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    pt_package_id: UUID,
    data: PtPackageCancelRequest,
) -> PtPackageResponse:
    """Cancel a PT-package without refund (PT-08, owner-only at the router).

    D-33-10 sequence (orchestrator owns the UoW — explicit ``await
    session.commit()`` at end; SVC001 gate enforces):

      1. Load instance — 404 ``pt_package_not_found`` if missing.
      2. Capture ``prior_status`` BEFORE mutation (forensic audit field;
         additively-extended PtPackageCancelledPayload requires it).
      3. ``_assert_can_transition(target='cancelled')`` — 409
         ``invalid_transition`` from the terminal ``cancelled`` source; legal
         sources are ``active``, ``exhausted``, ``expired``.
      4. Mutate via ``update_pt_package_status(status='cancelled',
         cancellation_reason=<free-text reason>)`` — NOT the
         ``CANCELLATION_REASON_REFUNDED`` sentinel; that sentinel is reserved
         for ``refund_pt_package`` so an offline audit scan can discriminate
         refund-driven cancellations from operator-driven ones via the
         cancellation_reason column alone.
      5. Flush — surfaces deferred constraint violations (none expected
         for a pure status-mutation, but maintains parity with
         ``cancel_membership``).
      6. ``audit.emit('pt_package_cancelled', ...)`` with payload matching
         PtPackageCancelledPayload extra='forbid' schema (4 keys:
         ``pt_package_id``, ``client_id``, ``cancellation_reason``,
         ``prior_status``).
      7. Refresh ``updated_at`` so the response carries the fresh
         server-side timestamp.
      8. Commit (SVC001 gate).
      9. Return ``PtPackageResponse``.

    NO payment ledger touch (distinct from refund per D-33-10) — use case is
    an operator-side correction of a sales error with manual cash handling
    out-of-band.

    UUID kwargs str-cast for JSONB serialisability (Phase 32-02 deviation #1
    lesson — raw UUIDs fail the JSON encoder). Pydantic UUID fields on
    PtPackageCancelledPayload accept str input.
    """
    # 1. Load
    pt_package = await repository.get_pt_package(session, pt_package_id)
    if pt_package is None:
        raise PtPackageNotFoundError("pt_package_not_found")

    # 2. Capture prior_status BEFORE mutation (audit forensic field).
    prior_status = pt_package.status

    # 3. FSM guard — 409 invalid_transition for cancelled source.
    _assert_can_transition(pt_package, target="cancelled")

    # 4. Mutate — free-text reason, NOT the 'refunded' sentinel.
    await repository.update_pt_package_status(
        session,
        pt_package,
        status="cancelled",
        cancellation_reason=data.reason,
    )

    # 5. Flush — surfaces any deferred constraint violations.
    await session.flush()

    # 6. Emit subject-side audit BEFORE commit (Phase 16 D-14
    # co-transactional). Payload matches PtPackageCancelledPayload
    # extra='forbid' schema with the Plan 33-03 additive prior_status field.
    await audit.emit(
        session,
        "pt_package_cancelled",  # LITERAL (INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        cancellation_reason=data.reason,
        prior_status=prior_status,
    )

    # 7. Refresh updated_at for the response (SA 2.0 expires attrs after flush).
    await session.refresh(pt_package, attribute_names=["updated_at"])

    # 8. Commit (SVC001 gate enforces explicit commit).
    await session.commit()

    # 9. Return response.
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)


async def refund_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    pt_package_id: UUID,
    data: PtPackageRefundRequest,
) -> PtPackageResponse:
    """Refund a PT-package (REF-02 / PT-13, reception+owner per B-07).

    D-33-11 sequence (orchestrator owns the UoW — explicit ``await
    session.commit()`` at end; SVC001 gate enforces):

      1. Load instance — 404 ``pt_package_not_found`` if missing.
      2. ``_assert_can_transition(target='cancelled')`` — 409
         ``invalid_transition`` from the terminal ``cancelled`` source;
         legal sources are ``active``, ``exhausted``, ``expired``.
      3. Call PaymentRefunder Protocol slot via ``get_payment_refunder()``
         with ``subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE`` (locally-pinned
         literal — NEVER ``from app.modules.payments import ...`` per
         modules-independent contract). The refunder internally:
           - Loads the ORIGINAL sale-side payment row by (subject_kind,
             subject_id) via ``get_original_pt_package_payment``.
           - INSERTs a negative-amount refund row with ``refund_of=
             original.id`` and emits ``refund_issued`` payment-side audit.
           - Raises ``OriginalPaymentNotFoundError`` (404
             ``original_payment_not_found``) when no sale row exists.
           - Raises ``AlreadyRefundedError`` (409 ``already_refunded``) on
             ``uq_payments_refund_of_alive`` race.
      4. Transition status to 'cancelled' via ``update_pt_package_status``;
         set ``cancellation_reason = CANCELLATION_REASON_REFUNDED`` sentinel
         (D-33-08 / mirrors Phase 32 D-32-08).
      5. Flush — surfaces deferred constraint violations.
      6. Emit ``pt_package_refunded`` audit row (subject-side); audit chain
         ordering is ``payment_recorded`` (sale-time) → ``refund_issued``
         (payment-side, inside ``issue_refund``) → ``pt_package_refunded``
         (subject-side, emitted here).
      7. Refresh ``updated_at`` for the response.
      8. Commit (SVC001 gate).
      9. Return ``PtPackageResponse``.

    v1.4 has NO PT-package freeze guard (no freeze concept) and NO renewed-
    source guard (no PT-package renewal). Only ``invalid_transition`` (FSM)
    + ``already_refunded`` (DB race) + ``original_payment_not_found`` (data
    integrity) surfaces are possible.

    Modules-independent contract: this orchestrator does NOT import
    ``app.modules.payments.*``; cross-module communication is exclusively
    through the ``get_payment_refunder()`` Protocol slot in
    ``app.core.dependencies``.

    UUID kwargs str-cast for JSONB serialisability (Phase 32-02 deviation #1
    lesson). Pydantic UUID validators on PtPackageRefundedPayload accept
    both UUID and well-formed str input.
    """
    # 1. Load
    pt_package = await repository.get_pt_package(session, pt_package_id)
    if pt_package is None:
        raise PtPackageNotFoundError("pt_package_not_found")

    # 2. FSM guard — 409 invalid_transition for cancelled source. Fires
    # BEFORE the refunder is invoked so the second-attempt case (already
    # cancelled instance) surfaces as invalid_transition, NOT already_refunded
    # (the DB partial UNIQUE remains the gate for the concurrent race; see
    # REF-TEST-02).
    _assert_can_transition(pt_package, target="cancelled")

    # 3. Consume PaymentRefunder Protocol slot (defensive raise on unregistered;
    # D-32-14). The refunder owns its own flush + IntegrityError catch +
    # OriginalPaymentNotFoundError raise; this orchestrator never re-catches.
    refund_payment = await get_payment_refunder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package_id,
        refund_user_id=actor.id,
        reason=data.reason,
        audit_actor=actor,
    )

    # 4. Transition status + set cancellation_reason sentinel ('refunded').
    await repository.update_pt_package_status(
        session,
        pt_package,
        status="cancelled",
        cancellation_reason=CANCELLATION_REASON_REFUNDED,
    )

    # 5. Flush — surfaces any deferred constraint violations.
    await session.flush()

    # 6. Emit subject-side audit (payment-side `refund_issued` already emitted
    # inside `issue_refund`). LOCKED event name "pt_package_refunded" per
    # audit.py:LOCKED_AUDIT_EVENTS. Payload matches PtPackageRefundedPayload
    # extra='forbid' schema (4 keys: pt_package_id, client_id,
    # refund_payment_id, reason).
    await audit.emit(
        session,
        "pt_package_refunded",  # LITERAL (INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        refund_payment_id=str(refund_payment.id),
        reason=data.reason,
    )

    # 7. Refresh updated_at for the response.
    await session.refresh(pt_package, attribute_names=["updated_at"])

    # 8. Commit (SVC001 gate enforces explicit commit).
    await session.commit()

    # 9. Return response.
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)
