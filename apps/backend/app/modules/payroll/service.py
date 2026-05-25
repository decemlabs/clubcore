"""Payroll service — orchestrator for comp-config + accrual lifecycle (Phase 58 PAY-01..07).

Each exported function owns the full unit-of-work for its operation:
  - ``set_comp_config`` — INSERT new versioned comp config + audit emit + commit (PAY-01).
  - ``get_active_comp_config`` — read-only resolver; raises 404 if no config exists (PAY-01).
  - ``compute_accrual_components`` — pure computation helper (PAY-02 / PAY-03); ZERO writes.
  - ``preview_accrual`` — read-only preview endpoint handler (PAY-02 / D-58-12); ZERO writes.
  - ``run_payroll_period`` — INSERT accrual with snapshotted numbers + audit + commit (PAY-03).
  - ``mark_accrual_paid`` — single pending→paid transition + audit + commit (PAY-04).

Subsequent plans append ``list_accruals`` (PAY-05) and
``record_clawback_for_pt_package_refund`` (PAY-06) to this module.

Commit discipline (SVC001):
  Each service function that mutates state owns the final ``session.commit()``.
  Repository helpers flush but do NOT commit.
  ``compute_accrual_components`` and ``preview_accrual`` are read-only — they
  call ZERO session.commit() / session.add() / audit.emit().

Exception conventions:
  ``CompConfigMissingError`` — raised on two paths with different HTTP status codes:
    - GET /payroll/trainer-configs/{trainer_id}: router passes through → 404 (PAY-01 D-58-11).
    - GET /payroll/preview + POST /accruals: router remaps to 422 at the endpoint layer
      (PAY-02 D-58-07 / PAY-03). Same exception class; router decides the HTTP status code.
      This keeps one error class (D-58-09).
  ``PayrollPeriodAlreadyRunError`` — raised when ON CONFLICT returns None (409, D-58-06).
  ``AlreadyPaidError`` — raised on second mark-paid attempt (409, D-58-08).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.payroll import repository
from app.modules.payroll.constants import ERROR_ALREADY_PAID, ERROR_PAYROLL_PERIOD_ALREADY_RUN
from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual
from app.modules.payroll.schemas import (
    PayrollAccrualCreate,
    PayrollPreviewResponse,
    TrainerCompConfigRequest,
)

_MSK = ZoneInfo("Europe/Moscow")


class CompConfigMissingError(NotFoundError):
    """No active compensation config exists for the given trainer + date (PAY-01 D-58-11).

    GET /payroll/trainer-configs/{trainer_id} raises this when
    ``resolve_active_comp_config`` returns None → 404.

    POST /accruals: router remaps to 422 via router-layer remap (D-58-07 / D-58-09),
    same as the preview endpoint. One error class; router decides the HTTP status code.
    """

    code = "comp_config_missing"
    status_code = 404


class PayrollPeriodAlreadyRunError(ConflictError):
    """Accrual INSERT was suppressed by ON CONFLICT DO NOTHING (D-58-06 / PAY-03).

    Raised by ``run_payroll_period`` when ``repository.insert_accrual_on_conflict``
    returns ``None`` — the partial UNIQUE index
    ``uq_trainer_payroll_accruals_period_alive`` already has a live row for this
    (trainer_id, period_start, period_end) triple. Router maps to HTTP 409.
    """

    code = ERROR_PAYROLL_PERIOD_ALREADY_RUN  # "payroll_period_already_run"
    status_code = 409


class AlreadyPaidError(ConflictError):
    """Accrual is already in the 'paid' state (D-58-08 / PAY-04).

    Raised by ``mark_accrual_paid`` when ``select_accrual_for_update`` returns a
    row whose ``status == 'paid'``. Router maps to HTTP 409. There is no unpay path.
    """

    code = ERROR_ALREADY_PAID  # "already_paid"
    status_code = 409


class AccrualNotFoundError(NotFoundError):
    """No TrainerPayrollAccrual row exists for the given accrual_id (PAY-04 D-58-08).

    Raised by ``mark_accrual_paid`` when ``select_accrual_for_update`` returns None.
    Router passes through → 404 not_found.
    """

    code = "not_found"
    status_code = 404


async def set_comp_config(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
    body: TrainerCompConfigRequest,
) -> TrainerCompConfig:
    """INSERT a new versioned comp config for *trainer_id* (PAY-01 / D-58-02 + D-58-17).

    Atomic unit-of-work (orchestrator owns commit) — mirror of D-33-11 sequence:
      1. ``repository.insert_comp_config`` — constructs ORM row + flushes (assigns id).
      2. ``audit.emit("trainer_comp_config_set", ...)`` — BEFORE commit (D-58-17).
      3. ``session.commit()`` — SVC001 gate; atomically commits config row + audit row.
      4. Return the committed config row.

    Existing config rows are NEVER modified. Every call inserts a NEW row with its
    own ``effective_from`` (D-58-02 INSERT-only versioned discipline).
    """
    config = await repository.insert_comp_config(
        session,
        trainer_id=trainer_id,
        commission_pct_bps=body.commission_pct_bps,
        session_fee_kopecks=body.session_fee_kopecks,
        effective_from=body.effective_from,
        created_by_user_id=actor.id,
    )

    # Audit emit BEFORE commit (D-58-17 atomic chain — flush already assigned config.id).
    # Literal strings "trainer_comp_config_set" and "trainer_comp_config" required by
    # INFRA-11 AST gate (tests/unit/test_audit_taxonomy.py).
    await audit.emit(
        session,
        "trainer_comp_config_set",
        actor_user_id=actor.id,
        resource_type="trainer_comp_config",
        resource_id=config.id,
        comp_config_id=str(config.id),
        trainer_id=str(trainer_id),
        commission_pct_bps=body.commission_pct_bps,
        session_fee_kopecks=body.session_fee_kopecks,
        effective_from=str(body.effective_from),
    )

    await session.commit()
    return config


async def get_active_comp_config(
    session: AsyncSession,
    trainer_id: UUID,
    as_of_date: date | None = None,
) -> TrainerCompConfig:
    """Return the active comp config for *trainer_id* as of *as_of_date* (PAY-01 D-58-11).

    If *as_of_date* is None, defaults to today in Europe/Moscow (project TZ discipline).
    Raises ``CompConfigMissingError`` (404) when no config exists.
    """
    resolved_date = as_of_date or datetime.now(_MSK).date()
    config = await repository.resolve_active_comp_config(session, trainer_id, resolved_date)
    if config is None:
        raise CompConfigMissingError("comp_config_missing")
    return config


async def compute_accrual_components(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> tuple[int, int, int, int, TrainerCompConfig]:
    """Compute payroll accrual components for a trainer + period (PAY-02 / PAY-03 / D-58-12).

    This is the SINGLE source of truth for commission + fixed computation reused by
    both preview_accrual (PAY-02) and run_payroll_period (PAY-03) — guaranteeing that
    preview and the persisted accrual produce identical numbers (PITFALL 1
    recompute-drift mitigation / T-58-23).

    Returns:
        (session_count, fixed_kopecks, commission_kopecks, total_kopecks, resolved_config)

    Algorithm:
      1. Resolve comp config as of period_end via repository.resolve_active_comp_config.
         If None OR both commission_pct_bps and session_fee_kopecks are NULL → raise
         CompConfigMissingError (D-58-07 / D-58-09). The router remaps this to 422 on
         the preview/accrual paths; the GET config path keeps its 404.
      2. Fetch (commission_revenue_kopecks, session_count) from
         repository.fetch_trainer_session_revenue for the given period.
      3. commission_kopecks = math.ceil(revenue_kopecks * bps / 10000) when bps is
         non-NULL else 0.  Integer-only: math.ceil on a Python int * int / int
         expression produces an exact rational result via Python's arbitrary-precision
         integers before division; no float intermediate (D-58-04 / T-58-25).
      4. fixed_kopecks = (session_fee_kopecks or 0) * session_count.
      5. total_kopecks = commission_kopecks + fixed_kopecks.

    ZERO writes: no session.commit(), no session.add(), no audit.emit() (D-58-12).
    """
    # Step 1 — resolve config as of period_end (D-58-02 INSERT-only versioned resolver).
    config = await repository.resolve_active_comp_config(session, trainer_id, period_end)
    if config is None or (
        config.commission_pct_bps is None and config.session_fee_kopecks is None
    ):
        raise CompConfigMissingError("comp_config_missing")

    # Step 2 — cross-module revenue + session count read.
    revenue_kopecks, session_count = await repository.fetch_trainer_session_revenue(
        session, trainer_id, period_start, period_end
    )

    # Step 3 — commission: integer-only math.ceil in trainer's favor (D-58-04 / T-58-25).
    # math.ceil(a * b / c) where a, b, c are Python ints: Python evaluates a * b as an
    # exact integer then divides by c using true division — math.ceil returns an int.
    # No float() conversion occurs; this is exact rational arithmetic.
    bps = config.commission_pct_bps
    commission_kopecks: int = math.ceil(revenue_kopecks * bps / 10000) if bps is not None else 0

    # Step 4 — fixed: session fee per conducting session.
    fixed_kopecks: int = (config.session_fee_kopecks or 0) * session_count

    # Step 5 — total.
    total_kopecks: int = commission_kopecks + fixed_kopecks

    return session_count, fixed_kopecks, commission_kopecks, total_kopecks, config


async def preview_accrual(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> PayrollPreviewResponse:
    """Return a read-only payroll preview for a trainer + period (PAY-02 / D-58-12).

    Maps the first four ints from compute_accrual_components into PayrollPreviewResponse.
    NO session.commit(), NO audit.emit(), NO session.add() / INSERT — zero-persistence
    (D-58-12 zero-persistence invariant / T-58-23).

    CompConfigMissingError propagates to the router, which remaps it to 422 for this
    endpoint (see module docstring). This is the router-remap approach (one error class).
    """
    session_count, fixed_kopecks, commission_kopecks, total_kopecks, _config = (
        await compute_accrual_components(session, trainer_id, period_start, period_end)
    )
    return PayrollPreviewResponse(
        session_count=session_count,
        fixed_kopecks=fixed_kopecks,
        commission_kopecks=commission_kopecks,
        total_kopecks=total_kopecks,
    )


async def run_payroll_period(
    session: AsyncSession,
    actor: CurrentUser,
    body: PayrollAccrualCreate,
) -> TrainerPayrollAccrual:
    """INSERT an append-only accrual row snapshotting rate/config at run time (PAY-03 / D-58-03).

    Atomic unit-of-work (orchestrator owns commit) — mirror of D-33-11 sequence:
      1. ``compute_accrual_components`` — resolve config + compute numbers (raises
         ``CompConfigMissingError`` → 422 if no/both-NULL config; router remaps).
      2. ``repository.insert_accrual_on_conflict`` — INSERT ON CONFLICT DO NOTHING
         RETURNING id (D-58-06 DB-wins-the-race). If None → raises
         ``PayrollPeriodAlreadyRunError`` (409 payroll_period_already_run).
      3. ``session.get`` — fetch the inserted row by RETURNING id to build the response.
      4. ``audit.emit("payroll_accrual_created", ...)`` — BEFORE commit (D-58-17).
         Literal strings required by INFRA-11 AST gate.
      5. ``session.commit()`` — SVC001 gate; atomically commits accrual row + audit row.

    Snapshot discipline: snapshot columns come from ``resolved_config`` returned by
    ``compute_accrual_components`` — they are NEVER recomputed. Editing the comp config
    after this call does NOT change these frozen columns (D-58-03 / T-58-28).

    No unpay / void / reverse function — this is an append-only ledger.
    """
    # Step 1 — resolve config + compute amounts (PITFALL 1: reuse shared helper, no drift).
    session_count, _fixed_kopecks, _commission_kopecks, total_kopecks, resolved_config = (
        await compute_accrual_components(
            session, body.trainer_id, body.period_start, body.period_end
        )
    )
    total_kopecks_signed: int = total_kopecks  # positive for regular accruals (D-58-03)

    # Step 2 — INSERT ON CONFLICT DO NOTHING RETURNING (T-58-27 / D-58-06).
    # revenue_kopecks is the commission_revenue_kopecks used in the computation.
    # We re-fetch it from resolved values already computed by compute_accrual_components.
    # commission_kopecks = ceil(revenue * bps / 10000); back-solve revenue for snapshot:
    # revenue_kopecks is NOT returned by compute_accrual_components but we can re-fetch it
    # cheaply (one extra call is safe — it's a read-only cross-module query).
    revenue_kopecks, _sc = await repository.fetch_trainer_session_revenue(
        session, body.trainer_id, body.period_start, body.period_end
    )

    accrual_id = await repository.insert_accrual_on_conflict(
        session,
        trainer_id=body.trainer_id,
        period_start=body.period_start,
        period_end=body.period_end,
        sessions_count=session_count,
        revenue_kopecks=revenue_kopecks,
        commission_pct_bps_snapshot=resolved_config.commission_pct_bps,
        session_fee_kopecks_snapshot=resolved_config.session_fee_kopecks,
        comp_config_id_snapshot=resolved_config.id,
        accrual_kopecks=total_kopecks_signed,
    )
    if accrual_id is None:
        # ON CONFLICT suppressed the insert → duplicate period for this trainer.
        raise PayrollPeriodAlreadyRunError("payroll_period_already_run")

    # Step 3 — fetch the inserted row (RETURNING only gave us the id).
    accrual = await session.get(TrainerPayrollAccrual, accrual_id)
    if accrual is None:
        # Should not happen — just committed, but be defensive.
        raise AccrualNotFoundError("not_found")  # pragma: no cover

    # Step 4 — audit emit BEFORE commit (D-58-17 atomic chain).
    # Literal strings "payroll_accrual_created" and "payroll_accrual" required by
    # INFRA-11 AST gate (tests/unit/test_audit_taxonomy.py). UUIDs + dates str()-cast
    # (58-05 lesson — audit payload must be JSON-serializable primitives).
    await audit.emit(
        session,
        "payroll_accrual_created",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="payroll_accrual",  # LITERAL
        resource_id=accrual.id,
        accrual_id=str(accrual.id),
        trainer_id=str(body.trainer_id),
        period_start=str(body.period_start),
        period_end=str(body.period_end),
        sessions_count=session_count,
        revenue_kopecks=revenue_kopecks,
        accrual_kopecks=total_kopecks_signed,
        comp_config_id_snapshot=str(resolved_config.id),
    )

    # Step 5 — commit (SVC001).
    await session.commit()
    return accrual


async def list_accruals(
    session: AsyncSession,
    trainer_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[TrainerPayrollAccrual], int]:
    """Return (rows, total) for a paginated listing of *trainer_id*'s accruals (PAY-05 / D-58-14).

    Delegates to two repository reads:
      1. ``list_accruals_for_trainer`` — ORDER BY accrued_at DESC, LIMIT/OFFSET page.
      2. ``count_accruals`` — unpaginated COUNT for the envelope ``total`` field.

    Both paid and pending rows surface; clawback rows (negative accrual_kopecks) are
    included — no filter on status or clawback_of_accrual_id (D-58-14 deferred filters).

    Pure read — ZERO writes, ZERO audit.emit(), ZERO session.commit() (SVC001).
    """
    rows = await repository.list_accruals_for_trainer(
        session, trainer_id, page=page, page_size=page_size
    )
    total = await repository.count_accruals(session, trainer_id)
    return rows, total


async def record_clawback_for_pt_package_refund(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    *,
    actor: CurrentUser,
    refund_payment_id: UUID,
    pt_package_id: UUID,
    pt_package_trainer_id: UUID | None,
) -> UUID | None:
    """Append a NEGATIVE clawback row when a refund post-dates a paid accrual (PAY-06 / D-58-20).

    This slot is called by pt_packages.service.refund_pt_package (D-58-20)
    AFTER the pt_package_refunded audit emit and BEFORE session.commit().
    It runs inside the CALLER's session/UoW — the clawback INSERT and audit emit
    commit atomically with the refund (same-UoW atomicity per T-58-34).

    Does NOT call session.commit() — caller owns the transaction (SVC001 /
    # noqa: SVC001 caller-owns-txn marker above mirrors activate_pt_package_from_webhook).

    Algorithm (D-58-20):
      1. If pt_package_trainer_id is None → return None immediately (not commissionable;
         D-58-21 nullable-trainer fallback — no payroll impact).
      2. Find the status='paid' regular accrual covering the refunded package's session
         MSK-dates (attribution: assigned-at-sale). If None → return None (no impact).
      3. Compute clawback_kopecks = abs(original.accrual_kopecks). Full-package refund
         only in v1.9 (partial deferred B-02). The clawback reverses the entire
         commission component that was paid for this accrual period.
      4. repository.insert_clawback_accrual — INSERT negative row (accrual_kopecks <0);
         flush; NO commit.
      5. audit.emit("payroll_clawback_recorded", ...) — BEFORE the caller commits
         (D-58-17 atomic chain; INFRA-11 literal strings).
      6. Return the new clawback accrual id (UUID).

    Args:
        session: The caller's AsyncSession (shared UoW — no new transaction).
        actor: The authenticated user performing the refund (owner-gated upstream).
        refund_payment_id: FK to the refund payment row (source_refund_payment_id).
        pt_package_id: The PT-package being refunded (for audit payload only;
            payroll does NOT read pt_packages ORM — cross-module via caller).
        pt_package_trainer_id: The assigned trainer from the pt_package row (nullable;
            passed by caller so payroll never reads pt_packages — D-58-21).

    Returns:
        UUID of the new clawback accrual row, or None when no payroll impact.
    """
    # Step 1 — NULL trainer_id → package was never commissionable; no clawback.
    if pt_package_trainer_id is None:
        return None  # D-58-21 nullable-trainer fallback

    # Step 2 — find the status='paid' regular accrual covering this package's session dates.
    # attribution: assigned-at-sale (clawback hits pt_package.trainer_id)
    original = await repository.find_paid_accrual_covering_refund(
        session,
        trainer_id=pt_package_trainer_id,
        pt_package_id=pt_package_id,
    )
    if original is None:
        return None  # no paid accrual covers this package → no payroll impact

    # Step 3 — compute clawback amount. v1.9: full-package refund only (partial deferred B-02).
    # The clawback reverses the entire accrual_kopecks of the original paid row.
    # accrual_kopecks on a regular row is always positive (D-58-03); abs() is defensive.
    clawback_kopecks: int = abs(original.accrual_kopecks)

    # Step 4 — INSERT negative clawback row (caller's session; NO commit).
    new_id = await repository.insert_clawback_accrual(
        session,
        original_accrual=original,
        refund_payment_id=refund_payment_id,
        clawback_kopecks=clawback_kopecks,
    )

    # Step 5 — audit emit BEFORE caller's commit (D-58-17 atomic chain).
    # Literal strings "payroll_clawback_recorded" and "payroll_accrual" required by
    # INFRA-11 AST gate (tests/unit/test_audit_taxonomy.py). UUIDs str()-cast (58-05 lesson).
    await audit.emit(
        session,
        "payroll_clawback_recorded",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="payroll_accrual",  # LITERAL
        resource_id=new_id,
        clawback_accrual_id=str(new_id),
        clawback_of_accrual_id=str(original.id),
        trainer_id=str(pt_package_trainer_id),
        source_refund_payment_id=str(refund_payment_id),
        pt_package_id=str(pt_package_id),
        accrual_kopecks=-clawback_kopecks,  # signed negative in audit payload
    )

    # Step 6 — return new clawback id (caller commits the UoW).
    return new_id


async def mark_accrual_paid(
    session: AsyncSession,
    actor: CurrentUser,
    accrual_id: UUID,
) -> TrainerPayrollAccrual:
    """Transition accrual status from 'pending' → 'paid' (PAY-04 / D-58-08).

    Atomic unit-of-work with row-lock (D-58-08 SELECT FOR UPDATE prevents concurrent
    double-pay races — T-58-30). Sequence:
      1. ``select_accrual_for_update`` — row-lock the accrual; None → 404.
      2. Status guard: if ``status == 'paid'`` → raise ``AlreadyPaidError`` (409).
      3. Mutate: ``status = 'paid'``, ``paid_at = now(UTC)``,
         ``paid_by_user_id = actor.id``. Flush to assign server-side timestamp.
      4. ``audit.emit("payroll_accrual_paid", ...)`` — BEFORE commit (D-58-17).
      5. ``session.commit()`` — SVC001 gate.

    NO unpay function — the 'pending' → 'paid' transition is one-way (D-58-08).
    Clawback rows (PAY-06) are separate INSERTs with negative accrual_kopecks.
    """
    # Step 1 — acquire FOR UPDATE row lock.
    accrual = await repository.select_accrual_for_update(session, accrual_id)
    if accrual is None:
        raise AccrualNotFoundError("not_found")

    # Step 2 — status guard.
    if accrual.status == "paid":
        raise AlreadyPaidError("already_paid")

    # Step 3 — single allowed post-INSERT mutation (T-58-28).
    accrual.status = "paid"
    accrual.paid_at = datetime.now(_MSK)
    accrual.paid_by_user_id = actor.id
    await session.flush()  # surfaces constraint violations before audit emit

    # Step 4 — audit emit BEFORE commit (D-58-17).
    # Literal strings "payroll_accrual_paid" and "payroll_accrual" required by
    # INFRA-11 AST gate. UUIDs str()-cast (58-05 lesson).
    await audit.emit(
        session,
        "payroll_accrual_paid",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="payroll_accrual",  # LITERAL
        resource_id=accrual.id,
        accrual_id=str(accrual.id),
        trainer_id=str(accrual.trainer_id),
        paid_by_user_id=str(actor.id),
        accrual_kopecks=accrual.accrual_kopecks,
    )

    # Step 5 — commit (SVC001).
    await session.commit()
    return accrual
