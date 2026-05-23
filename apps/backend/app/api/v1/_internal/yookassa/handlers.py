"""ЮKassa webhook business-logic handlers (Phase 50 WH-04..06 / D-50-18 + D-50-25).

The webhook router (``router.py``) owns transport concerns (IP allowlist via
route-level Depends, Redis dedup short-circuit, body parse, dispatch). This
module owns the atomic UoW for each event type.

Two handlers, mirror-shaped:

- ``handle_payment_succeeded``: D-50-18's 8-step UoW —
    1. Extract object_id from webhook body.
    2. **Re-fetch via** ``yookassa_client.get_payment(object_id)`` BEFORE
       any DB write (WH-02 / D-50-12 — the cryptographic anchor that
       replaces HMAC; the body's claimed status is NEVER trusted).
    3. Guard: ``classification != "ok"`` → log + return (next ЮKassa retry
       will re-attempt).
    4. Guard: ``result.status != "succeeded"`` → log + return.
    5. ``webhook_intake_corr = uuid4()`` is the chain ROOT for all audit
       rows in this UoW.
    6. ``async with session.begin():`` opens the SINGLE atomic UoW —
        a. SELECT-FOR-UPDATE the OnlinePayment row.
        b. ``_assert_can_transition`` (InvalidTransitionError → 200 +
           audit-as-forensic per D-50-17).
        c. Mutate row: ``status='succeeded'`` + ``succeeded_at``.
        d. Narrow SELECT of ``clients.email`` (Blocker #4 — NOT a
           relationship traversal; OnlinePayment has no client relationship
           wired and even if it did the eager-load shape is the wrong
           contract here).
        e. ``get_payment_recorder()(... method='online', audit_actor=None,
           received_by_user_id=None)`` — widened Protocol from Plan 50-03
           (Blocker #2).
        f. Activator: ``get_membership_activator()`` /
           ``get_pt_package_activator()`` with ``online_payment_id=row.id``
           (Plan 50-03 kwarg — Blocker #3).
        g. ``insert_fiscal_receipt(status='sent', kind='payment', ...)``.
        h. Emit ``online_payment_succeeded`` audit (CHILD of
           webhook_intake_corr).
        i. Emit ``yookassa_webhook_received`` audit (ROOT — emitted LAST
           per D-50-18 step 8; its audit_log row's own id is the seed for
           subsequent Phase 52 notification chains).
    7. After ``async with`` exits (commit happens here): ``_post_commit_enqueue``
       no-op (Phase 50; Phase 52 NOT-04/05 fills body).

- ``handle_payment_canceled``: D-50-25 mirror — re-fetch, FSM guard,
  status update + ``canceled_at``, emit ``online_payment_canceled`` with
  ``cancellation_party`` + ``cancellation_reason`` from the webhook body's
  ``object.cancellation_details``, then ROOT audit. No activator, no
  fiscal_receipt.

Blocker discipline (Phase 50 PRD blocker register):
- Blocker #1 — REUSE existing ``InvalidTransitionError`` from
  ``app/core/exceptions.py:212``. Do NOT introduce a new transition exception class.
- Blocker #2 — ``PaymentRecorder`` Protocol widened by Plan 50-03; webhook
  passes ``audit_actor=None`` + ``received_by_user_id=None``.
- Blocker #3 — Activator kwarg renamed to ``online_payment_id`` by Plan 50-03;
  webhook passes ``row.id`` (the OnlinePayment seed UUID).
- Blocker #4 — Customer email fetched via narrow scalar
  ``select(Client.email)``, NOT relationship traversal.
- Blocker #7 — This module does NOT modify ``app/main.py`` or
  ``app/workers/__init__.py``. The composition root was wired by Phase 47.

B-4 (Plan 50-04 PRD review):
- ``_select_for_update_online_payment`` carries an INVARIANT docstring
  declaring it MUST be called inside ``async with session.begin()`` — without
  the explicit transaction the row-lock in PostgreSQL is a no-op. The
  acceptance-criteria grep gate scans 5 lines preceding each callsite for
  ``session.begin`` to enforce the invariant at CI time.

W-4 (Plan 50-04 PRD review; extended Plan 51-06 D-51-15):
- ``_post_commit_enqueue`` signature originally locked by CONTEXT.md D-50-19:
  ``(arq_pool, *, online_payment_id, subject_kind, subject_id)``. Plan 51-06
  extended this with ``fiscal_receipt_id: UUID | None = None`` (default None
  preserves Phase 50 callsite compatibility) so the post-commit branch can
  enqueue ``dispatch_fiscal_receipt``. The router now threads
  ``request.app.state.arq_pool`` through to the handler so the enqueue
  actually fires after a successful webhook UoW.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import (
    get_membership_activator,
    get_payment_recorder,
    get_pt_package_activator,
)
from app.core.exceptions import InvalidTransitionError  # Blocker #1 — REUSE existing class
from app.integrations.yookassa.client import YooKassaClient
from app.modules.clients.models import Client
from app.modules.fiscal_receipts.constants import (
    FISCAL_RECEIPT_STATUS_TRANSITIONS,
    KIND_PAYMENT,
    STATUS_SENT,
)
from app.modules.fiscal_receipts.constants import (
    STATUS_FAILED as FR_STATUS_FAILED,
)
from app.modules.fiscal_receipts.constants import (
    STATUS_SUCCEEDED as FR_STATUS_SUCCEEDED,
)
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.fiscal_receipts.repository import insert_fiscal_receipt
from app.modules.online_payments.constants import (
    ONLINE_PAYMENT_STATUS_TRANSITIONS,
    STATUS_CANCELED,
    STATUS_SUCCEEDED,
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds.constants import (
    ONLINE_REFUND_STATUS_TRANSITIONS,
)
from app.modules.online_refunds.constants import (
    STATUS_SUCCEEDED as REFUND_STATUS_SUCCEEDED,
)
from app.modules.online_refunds.models import OnlineRefund
from app.modules.online_refunds.settle import _settle_online_refund
from app.modules.payments.repository import _is_refund_of_uniqueness_conflict
from app.modules.payments.service import AlreadyRefundedError

_log = structlog.get_logger("api.v1._internal.yookassa.handlers")


def _assert_can_transition(row: OnlinePayment, *, target: str) -> None:
    """Central FSM guard (D-50-16). Mirrors memberships/service.py pattern.

    Raises ``InvalidTransitionError`` (existing class from
    ``app/core/exceptions.py:212``) instead of inventing a new
    a new exception class (Blocker #1). The webhook handler catches this
    and returns 200 with an audit-as-forensic emit (D-50-17 —
    ``idempotency_outcome="illegal_transition"``).
    """
    allowed = ONLINE_PAYMENT_STATUS_TRANSITIONS.get(row.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": row.status, "to_status": target},
        )


async def _select_for_update_online_payment(
    session: AsyncSession, *, yookassa_payment_id: str
) -> OnlinePayment | None:
    """SELECT-FOR-UPDATE on the OnlinePayment row by yookassa_payment_id.

    INVARIANT: Caller MUST be inside ``async with session.begin()`` —
    PostgreSQL releases the row lock immediately outside an explicit
    transaction (no-op). All callsites in handlers.py are inside
    session.begin() blocks; the acceptance-criteria grep gate enforces
    this at CI time (5 lines preceding each callsite must contain
    ``session.begin``).

    Returns ``None`` if no row matches (orphan path — caller logs warning +
    returns; the Phase 53 reconcile cron handles recovery).
    """
    stmt = (
        select(OnlinePayment)
        .where(OnlinePayment.yookassa_payment_id == yookassa_payment_id)
        .with_for_update()
    )
    row: OnlinePayment | None = await session.scalar(stmt)
    return row


async def _select_for_update_online_refund(
    session: AsyncSession, *, yookassa_refund_id: str
) -> OnlineRefund | None:
    """SELECT-FOR-UPDATE on the OnlineRefund row by yookassa_refund_id (Phase 51 D-51-11).

    Mirror of ``_select_for_update_online_payment`` for the refund webhook UoW.
    Same INVARIANT: caller MUST be inside ``async with session.begin()`` so the
    row lock holds for the duration of the FSM mutation + child audits.

    Returns ``None`` when no row matches (orphan path — caller logs warning +
    emits ``yookassa_webhook_received`` audit with ``idempotency_outcome='orphan'``;
    DEFER-51 reconcile cron handles recovery).
    """
    stmt = (
        select(OnlineRefund)
        .where(OnlineRefund.yookassa_refund_id == yookassa_refund_id)
        .with_for_update()
    )
    row: OnlineRefund | None = await session.scalar(stmt)
    return row


async def _select_for_update_fiscal_receipt(
    session: AsyncSession, *, yookassa_receipt_id: str
) -> FiscalReceipt | None:
    """SELECT-FOR-UPDATE on the FiscalReceipt row by yookassa_receipt_id (Phase 51 D-51-21).

    Same INVARIANT as the other select-for-update helpers: caller MUST be inside
    ``async with session.begin()``. Returns ``None`` when no row matches (orphan
    path — D-51-25 orphan-receipt reconciliation deferred to Phase 53).
    """
    stmt = (
        select(FiscalReceipt)
        .where(FiscalReceipt.yookassa_receipt_id == yookassa_receipt_id)
        .with_for_update()
    )
    row: FiscalReceipt | None = await session.scalar(stmt)
    return row


def _assert_can_transition_refund(row: OnlineRefund, *, target: str) -> None:
    """Central FSM guard for online_refunds (Phase 51 D-51-11).

    Mirror of ``_assert_can_transition`` against the
    ``ONLINE_REFUND_STATUS_TRANSITIONS`` MappingProxyType (locked literals
    pinned to migration 0037 — plan 51-02). Raises ``InvalidTransitionError``
    (reused class, Blocker #1 lineage); the webhook handler catches and emits
    ``yookassa_webhook_received`` with ``idempotency_outcome='illegal_transition'``.
    """
    allowed = ONLINE_REFUND_STATUS_TRANSITIONS.get(row.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": row.status, "to_status": target},
        )


def _assert_can_transition_receipt(row: FiscalReceipt, *, target: str) -> None:
    """Central FSM guard for fiscal_receipts (Phase 51 D-51-21 / D-51-22).

    Mirror against ``FISCAL_RECEIPT_STATUS_TRANSITIONS`` (Phase 50 D-50-32 locked
    MappingProxyType — frozen). The receipt webhook handlers catch
    ``InvalidTransitionError`` and emit ``yookassa_webhook_received`` with
    ``idempotency_outcome='illegal_transition'`` (no re-fetch — D-51-03 — receipt
    status is informational; webhook body is authoritative).
    """
    allowed = FISCAL_RECEIPT_STATUS_TRANSITIONS.get(row.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": row.status, "to_status": target},
        )


async def _read_customer_email(session: AsyncSession, client_id: UUID) -> str:
    """Fetch the client's email via a narrow scalar SELECT (Blocker #4).

    NOT a relationship traversal: OnlinePayment does not declare a
    ``client`` relationship, and even if it did the eager-load shape
    would be the wrong contract here (we want a single column, not the
    whole Client row inflated into the session identity map). Mirrors
    ``online_payments/service.py:102-113`` (_read_client_email_or_raise).

    Phase 49 sell flow asserts ``clients.email IS NOT NULL`` before
    creating the OnlinePayment row (PAY-06). Reaching here with a NULL
    email means the email was scrubbed post-sale — an operational
    anomaly. Raises ``RuntimeError`` so the webhook UoW rolls back and
    ЮKassa retries (operator gets time to restore the email).
    """
    email = await session.scalar(select(Client.email).where(Client.id == client_id))
    if email is None:
        raise RuntimeError(f"Client {client_id} has no email at webhook time")
    return email


async def _post_commit_enqueue(
    arq_pool: Any | None = None,
    *,
    online_payment_id: UUID,
    subject_kind: Literal["membership", "pt_package"],
    subject_id: UUID,
    fiscal_receipt_id: UUID | None = None,
) -> None:
    """Post-commit notification enqueue (Phase 50 stub → Phase 51 fiscal-dispatch branch).

    Phase 50 shipped this as a pure no-op (single ``_log.info`` call —
    DEFER-50-04). Phase 51 (this commit, D-51-15) ADDS the
    ``fiscal_receipt_id`` branch: when both ``arq_pool`` and
    ``fiscal_receipt_id`` are non-None, enqueues the ARQ task
    ``dispatch_fiscal_receipt`` with ``_max_tries=3`` + ``_expires=60``
    (Pitfall 11 / D-51-Discretion retry contract). Phase 52 will add
    notification branches (NOT-02 refund DM, NOT-04 fiscal-failure DM) —
    out of scope for this plan.

    Signature lineage:
      - Phase 50 (D-50-19): ``(arq_pool, *, online_payment_id, subject_kind,
        subject_id)``.
      - Phase 51 (D-51-15, this plan): adds ``fiscal_receipt_id: UUID | None
        = None`` (default ``None`` preserves Phase 50 callsite compatibility
        and any future caller that has no receipt to dispatch — e.g. the
        cancellation handler in ``handle_payment_canceled``).

    The AST gate at ``tests/integration/webhook_yookassa/test_post_commit_seam.py``
    asserts the EXACT structural shape of this body (one ``_log.info`` Expr
    + one guarded ``await arq_pool.enqueue_job(...)`` If). Any structural
    change requires a lockstep update of that test in the SAME commit
    (PATTERNS.md errata #3).
    """
    _log.info(
        "webhook_post_commit_enqueue_skip",
        online_payment_id=str(online_payment_id),
        subject_kind=subject_kind,
        subject_id=str(subject_id),
        arq_pool_present=arq_pool is not None,
        fiscal_receipt_id=str(fiscal_receipt_id) if fiscal_receipt_id is not None else None,
    )
    if arq_pool is not None and fiscal_receipt_id is not None:
        await arq_pool.enqueue_job(
            "dispatch_fiscal_receipt",
            str(fiscal_receipt_id),
            _max_tries=3,
            _expires=60,
        )


async def handle_payment_succeeded(
    session: AsyncSession,
    yookassa_client: YooKassaClient,
    *,
    body: dict[str, Any],
    arq_pool: Any | None = None,
) -> None:
    """``payment.succeeded`` handler — D-50-18 atomic UoW (8 steps).

    Returns ``None``; the router returns 200 unconditionally. Failure
    branches (orphan row, FSM violation, re-fetch failure) all log via
    structlog and either emit an audit-as-forensic row or return silently
    (idempotent on retry).
    """
    object_obj = body.get("object") or {}
    object_id = object_obj.get("id") if isinstance(object_obj, dict) else None
    if not isinstance(object_id, str) or not object_id:
        _log.warning("yookassa_webhook_missing_object_id", event="payment.succeeded")
        return

    # WH-02 — Re-fetch BEFORE any DB write. This is the cryptographic anchor
    # (D-50-12) that replaces HMAC: we never trust the body's claimed status.
    result = await yookassa_client.get_payment(object_id)
    if result.classification != "ok":
        _log.warning(
            "yookassa_webhook_refetch_failed",
            object_id=object_id,
            classification=result.classification,
        )
        return
    if result.status != STATUS_SUCCEEDED:
        _log.info(
            "yookassa_webhook_pending_skip",
            object_id=object_id,
            status=result.status,
        )
        return

    webhook_intake_corr = uuid4()

    # B-4 invariant: every _select_for_update_online_payment callsite below
    # is inside this `async with session.begin()` block — without it the
    # row lock in PostgreSQL is a no-op.
    async with session.begin():
        row = await _select_for_update_online_payment(session, yookassa_payment_id=object_id)
        if row is None:
            _log.warning(
                "yookassa_webhook_orphan_payment_succeeded",
                object_id=object_id,
            )
            return

        try:
            _assert_can_transition(row, target=STATUS_SUCCEEDED)
        except InvalidTransitionError:
            _log.warning(
                "yookassa_webhook_illegal_transition",
                object_id=object_id,
                from_status=row.status,
                to_status=STATUS_SUCCEEDED,
            )
            # D-50-17: emit audit-as-forensic, NOT 4xx. ЮKassa retries on 4xx;
            # the row state already reflects the terminal outcome.
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=row.id,
                audit_correlation_id=None,
                event_type="payment.succeeded",
                object_id=object_id,
                idempotency_outcome="illegal_transition",
            )
            return

        row.status = STATUS_SUCCEEDED
        row.succeeded_at = datetime.now(UTC)

        # Blocker #4 — narrow scalar SELECT of clients.email, NOT relationship
        # traversal. OnlinePayment has no client relationship wired.
        customer_email = await _read_customer_email(session, row.client_id)

        # Subject-kind dispatch. The 0034 CHECK constraint
        # `(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)`
        # guarantees exactly one is non-None — the assert below is defense in
        # depth and would only fail on a DB-level constraint violation.
        if row.membership_plan_id is not None:
            subject_kind = SUBJECT_KIND_MEMBERSHIP
            subject_id: UUID = row.membership_plan_id
        elif row.pt_package_plan_id is not None:
            subject_kind = SUBJECT_KIND_PT_PACKAGE
            subject_id = row.pt_package_plan_id
        else:  # pragma: no cover — defended at DB CHECK
            raise RuntimeError(
                f"OnlinePayment {row.id} has neither membership_plan_id nor "
                f"pt_package_plan_id — DB CHECK constraint violated"
            )

        # Blocker #2 — widened Protocol from Plan 50-03; webhook passes
        # audit_actor=None + received_by_user_id=None (anonymous flow).
        payment_row = await get_payment_recorder()(
            session,
            subject_kind=subject_kind,
            subject_id=subject_id,
            amount_kopecks=row.amount_kopecks,
            method="online",
            received_by_user_id=None,
            audit_actor=None,
        )
        ledger_payment_id: UUID = payment_row.id

        # Blocker #3 — activator kwarg renamed to online_payment_id by Plan 50-03.
        activator = (
            get_membership_activator()
            if subject_kind == SUBJECT_KIND_MEMBERSHIP
            else get_pt_package_activator()
        )
        await activator(
            session,
            online_payment_id=row.id,
            audit_correlation_id=row.audit_correlation_id,
        )

        # fiscal_receipts INSERT — Plan 50-01 repository, caller-owns-txn.
        # Phase 51 D-51-15: capture the inserted row + flush so ``fr_row.id``
        # is populated (server_default=gen_random_uuid()), so the post-commit
        # hook can enqueue dispatch_fiscal_receipt against the new UUID.
        fr_row = await insert_fiscal_receipt(
            session,
            payment_id=ledger_payment_id,
            kind=KIND_PAYMENT,
            status=STATUS_SENT,
            customer_email=customer_email,
            audit_correlation_id=webhook_intake_corr,
            sent_at=datetime.now(UTC),
        )
        await session.flush()
        fiscal_receipt_row_id: UUID = fr_row.id

        # CHILD audit emit — online_payment_succeeded chained to
        # webhook_intake_corr (D-50-18 step 7). UUIDs are cast to str for
        # JSONB-serialisability (audit.emit writes payload kwargs directly
        # into a JSONB column; Pydantic ``model_validate`` only validates
        # the shape — it does not transform). Mirrors
        # ``memberships/service.py:1925`` pattern.
        await audit.emit(
            session,
            "online_payment_succeeded",
            actor_user_id=None,
            resource_type="online_payment",
            resource_id=row.id,
            audit_correlation_id=str(webhook_intake_corr),
            online_payment_id=str(row.id),
            yookassa_payment_id=object_id,
            amount_kopecks=row.amount_kopecks,
            payment_id=str(ledger_payment_id),
        )

        # ROOT audit emit — D-50-18 step 8, REVERSE order from Phase 49
        # so the audit_log row's own id can be the seed for Phase 52
        # post-commit notification chains.
        await audit.emit(
            session,
            "yookassa_webhook_received",
            actor_user_id=None,
            resource_type="yookassa_webhook",
            resource_id=row.id,
            audit_correlation_id=None,
            event_type="payment.succeeded",
            object_id=object_id,
            idempotency_outcome="processed",
        )

        # Capture locals for the post-commit hook — row is detached after commit.
        op_row_id: UUID = row.id
        subject_kind_local: Literal["membership", "pt_package"] = subject_kind  # type: ignore[assignment]
        subject_id_local: UUID = subject_id
        fiscal_receipt_row_id_local: UUID = fiscal_receipt_row_id

    # Phase 51 D-51-15 — runs AFTER the ``async with session.begin():`` commit
    # boundary so an enqueue failure cannot poison the UoW. ``arq_pool`` is
    # threaded in from the router (``request.app.state.arq_pool``); when
    # ``None`` (e.g. in unit tests that bypass the lifespan) the enqueue is
    # a no-op. ``fiscal_receipt_row_id_local`` is the just-INSERTed
    # fiscal_receipts row id; the worker reads the full row at task entry
    # (plan 51-05).
    await _post_commit_enqueue(
        arq_pool,
        online_payment_id=op_row_id,
        subject_kind=subject_kind_local,
        subject_id=subject_id_local,
        fiscal_receipt_id=fiscal_receipt_row_id_local,
    )


async def handle_payment_canceled(
    session: AsyncSession,
    yookassa_client: YooKassaClient,
    *,
    body: dict[str, Any],
) -> None:
    """``payment.canceled`` handler — D-50-25.

    Mirror of ``handle_payment_succeeded`` minus activator + fiscal_receipt
    (no monetary side effects on cancellation). Adds ``cancellation_party``
    + ``cancellation_reason`` from the webhook body's
    ``object.cancellation_details`` to the ``online_payment_canceled``
    audit emit so Phase 52 NOT-05 can compose user-facing DM bodies.
    """
    object_obj = body.get("object") or {}
    if not isinstance(object_obj, dict):
        _log.warning("yookassa_webhook_missing_object_id", event="payment.canceled")
        return
    object_id = object_obj.get("id")
    if not isinstance(object_id, str) or not object_id:
        _log.warning("yookassa_webhook_missing_object_id", event="payment.canceled")
        return

    # WH-02 still applies — cancellation also re-fetches (the body's
    # claimed status is NEVER trusted, even for the cancel branch).
    result = await yookassa_client.get_payment(object_id)
    if result.classification != "ok":
        _log.warning(
            "yookassa_webhook_refetch_failed",
            object_id=object_id,
            classification=result.classification,
        )
        return
    if result.status != STATUS_CANCELED:
        _log.info(
            "yookassa_webhook_canceled_status_mismatch",
            object_id=object_id,
            status=result.status,
        )
        return

    # cancellation_details comes from the webhook BODY per D-50-25 (the
    # re-fetched GET /v3/payments/{id} response may also carry it, but the
    # body is the canonical Phase 50 source — ЮKassa documents the body
    # shape as the cancellation discriminator).
    details_obj = object_obj.get("cancellation_details") or {}
    details: dict[str, Any] = details_obj if isinstance(details_obj, dict) else {}
    cancellation_party_raw = details.get("party")
    cancellation_reason_raw = details.get("reason")
    cancellation_party: str | None = (
        cancellation_party_raw if isinstance(cancellation_party_raw, str) else None
    )
    cancellation_reason: str | None = (
        cancellation_reason_raw if isinstance(cancellation_reason_raw, str) else None
    )

    webhook_intake_corr = uuid4()

    async with session.begin():
        row = await _select_for_update_online_payment(session, yookassa_payment_id=object_id)
        if row is None:
            _log.warning(
                "yookassa_webhook_orphan_payment_canceled",
                object_id=object_id,
            )
            return

        try:
            _assert_can_transition(row, target=STATUS_CANCELED)
        except InvalidTransitionError:
            _log.warning(
                "yookassa_webhook_illegal_transition",
                object_id=object_id,
                from_status=row.status,
                to_status=STATUS_CANCELED,
            )
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=row.id,
                audit_correlation_id=None,
                event_type="payment.canceled",
                object_id=object_id,
                idempotency_outcome="illegal_transition",
            )
            return

        row.status = STATUS_CANCELED
        row.canceled_at = datetime.now(UTC)

        # CHILD audit emit — online_payment_canceled chained to webhook_intake_corr.
        # UUIDs cast to str for JSONB-serialisability (audit.emit stores
        # payload kwargs directly into a JSONB column; Pydantic
        # ``model_validate`` only validates shape, it does not transform).
        # Mirrors ``memberships/service.py:1925`` pattern.
        await audit.emit(
            session,
            "online_payment_canceled",
            actor_user_id=None,
            resource_type="online_payment",
            resource_id=row.id,
            audit_correlation_id=str(webhook_intake_corr),
            online_payment_id=str(row.id),
            yookassa_payment_id=object_id,
            cancellation_party=cancellation_party,
            cancellation_reason=cancellation_reason,
        )

        # ROOT audit emit — mirror of success path with event_type="payment.canceled".
        await audit.emit(
            session,
            "yookassa_webhook_received",
            actor_user_id=None,
            resource_type="yookassa_webhook",
            resource_id=row.id,
            audit_correlation_id=None,
            event_type="payment.canceled",
            object_id=object_id,
            idempotency_outcome="processed",
        )

    # No _post_commit_enqueue for cancellation in Phase 50 (Phase 52 NOT-05
    # may add a cancellation-DM enqueue here).


async def handle_refund_succeeded(
    session: AsyncSession,
    yookassa_client: YooKassaClient,
    *,
    body: dict[str, Any],
) -> None:
    """``refund.succeeded`` handler — Phase 51 D-51-11 atomic UoW.

    Sequence:
      1. Extract refund object_id from body['object']['id']; defensive guard
         on missing/malformed body (structlog WARNING + return; never raise).
      2. **Re-fetch** via ``yookassa_client.get_refund(object_id)`` BEFORE any
         DB write (D-50-12 / D-51-11 step 2 — cryptographic anchor; the body's
         claimed status is NEVER trusted, even for refund events).
      3. Atomic UoW (``async with session.begin():``):
         a. webhook_intake_corr = uuid4() — chain ROOT.
         b. SELECT-FOR-UPDATE OnlineRefund by yookassa_refund_id.
            On None: structlog WARNING + emit ``yookassa_webhook_received`` with
            ``idempotency_outcome='orphan'``; return.
         c. FSM guard ``_assert_can_transition_refund(target='succeeded')``.
            On InvalidTransitionError: emit ``yookassa_webhook_received`` with
            ``idempotency_outcome='illegal_transition'``; return.
         d-i. Delegate to ``_settle_online_refund(session, online_refund_id=row.id,
              chain_root_corr=webhook_intake_corr,
              chain_root_event='yookassa_webhook_received', ...)``. The helper:
              - mark_succeeded(row); load OnlinePayment + original Payment;
              - PaymentRefunder Protocol call (Phase 32 D-32-14); IntegrityError
                / AlreadyRefundedError on the partial-UNIQUE conflict bubble out
                of the helper (boundary pinned per checker review iter 1);
              - direct subject transition with ``CANCELLATION_REASON_REFUNDED``
                sentinel (Errata #4 — NOT activator; activator slots are
                forward-only);
              - INSERT fiscal_receipts(kind='refund', status='sent');
              - emit ``online_payment_refunded`` + subject_refunded + chain-root
                ``yookassa_webhook_received`` audits.

    Idempotent-replay semantics (REFUND-03 / D-51-05):
      - On ``AlreadyRefundedError`` or ``IntegrityError`` where
        ``_is_refund_of_uniqueness_conflict(exc)`` is True, log
        ``yookassa_refund_idempotent_replay`` and return silently (200 to ЮKassa).
      - The in-flight txn was tainted by the rollback inside ``issue_refund``;
        no further audits emit in this UoW. The Phase 53 reconcile cron can
        re-walk if needed.

    Returns ``None``; the router returns 200 unconditionally.
    """
    object_obj = body.get("object") or {}
    object_id = object_obj.get("id") if isinstance(object_obj, dict) else None
    if not isinstance(object_id, str) or not object_id:
        _log.warning("yookassa_webhook_missing_object_id", yk_event="refund.succeeded")
        return

    # D-50-12 / D-51-11 step 2 — re-fetch before any DB write.
    refund_result = await yookassa_client.get_refund(object_id)
    if refund_result.classification != "ok":
        _log.warning(
            "yookassa_refund_refetch_failed",
            object_id=object_id,
            classification=refund_result.classification,
        )
        return
    if refund_result.status != REFUND_STATUS_SUCCEEDED:
        _log.info(
            "yookassa_refund_pending_skip",
            object_id=object_id,
            status=refund_result.status,
        )
        return

    webhook_intake_corr = uuid4()

    try:
        async with session.begin():
            row = await _select_for_update_online_refund(
                session, yookassa_refund_id=object_id
            )
            if row is None:
                _log.warning(
                    "yookassa_refund_webhook_orphan",
                    object_id=object_id,
                )
                # Chain-completeness: emit the root audit even for orphans so the
                # forensic trail records the delivery (D-51-11).
                await audit.emit(
                    session,
                    "yookassa_webhook_received",
                    actor_user_id=None,
                    resource_type="yookassa_webhook",
                    resource_id=None,
                    audit_correlation_id=None,
                    event_type="refund.succeeded",
                    object_id=object_id,
                    idempotency_outcome="orphan",
                )
                return

            try:
                _assert_can_transition_refund(row, target=REFUND_STATUS_SUCCEEDED)
            except InvalidTransitionError:
                _log.warning(
                    "yookassa_refund_illegal_transition",
                    object_id=object_id,
                    from_status=row.status,
                    to_status=REFUND_STATUS_SUCCEEDED,
                )
                await audit.emit(
                    session,
                    "yookassa_webhook_received",
                    actor_user_id=None,
                    resource_type="yookassa_webhook",
                    resource_id=row.id,
                    audit_correlation_id=None,
                    event_type="refund.succeeded",
                    object_id=object_id,
                    idempotency_outcome="illegal_transition",
                )
                return

            # D-51-18 — delegate the rest of the UoW (steps 3d-3i) to the shared
            # helper so plan 51-09 poll_pending_refunds can reuse it.
            await _settle_online_refund(
                session,
                online_refund_id=row.id,
                chain_root_corr=webhook_intake_corr,
                chain_root_event="yookassa_webhook_received",
                chain_root_event_payload_kwargs={
                    "event_type": "refund.succeeded",
                    "object_id": object_id,
                    "idempotency_outcome": "processed",
                },
            )
    except (AlreadyRefundedError, IntegrityError) as exc:
        # REFUND-03 / D-51-05 idempotent semantics. The registered
        # PaymentRefunder implementation (issue_refund) rolls back its failed
        # flush and re-raises AlreadyRefundedError; defence-in-depth catches
        # raw IntegrityError too (in case a future PaymentRefunder variant
        # surfaces the underlying error directly). The discriminator
        # _is_refund_of_uniqueness_conflict is still consulted on raw
        # IntegrityError to scope this branch narrowly to the partial-UNIQUE
        # path — other IntegrityErrors (FK violations etc.) propagate.
        if isinstance(exc, AlreadyRefundedError) or _is_refund_of_uniqueness_conflict(
            exc
        ):
            _log.warning(
                "yookassa_refund_idempotent_replay",
                yookassa_refund_id=object_id,
            )
            return
        raise


async def handle_receipt_succeeded(
    session: AsyncSession,
    *,
    body: dict[str, Any],
) -> None:
    """``receipt.succeeded`` handler — Phase 51 D-51-21 atomic UoW.

    No re-fetch (D-51-03 — receipt status is informational; webhook body is
    authoritative). Atomic UoW: SELECT-FOR-UPDATE FiscalReceipt by
    yookassa_receipt_id, FSM guard target='succeeded', UPDATE status +
    succeeded_at, emit 2 audits (child fiscal_receipt_succeeded + root
    yookassa_webhook_received).

    Note signature: receipt handlers do NOT take ``yookassa_client`` (D-51-03 —
    no re-fetch surface).
    """
    object_obj = body.get("object") or {}
    object_id = object_obj.get("id") if isinstance(object_obj, dict) else None
    if not isinstance(object_id, str) or not object_id:
        _log.warning("yookassa_webhook_missing_object_id", yk_event="receipt.succeeded")
        return

    async with session.begin():
        row = await _select_for_update_fiscal_receipt(
            session, yookassa_receipt_id=object_id
        )
        if row is None:
            _log.warning(
                "yookassa_receipt_webhook_orphan",
                object_id=object_id,
                yk_event="receipt.succeeded",
            )
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=None,
                audit_correlation_id=None,
                event_type="receipt.succeeded",
                object_id=object_id,
                idempotency_outcome="orphan",
            )
            return

        try:
            _assert_can_transition_receipt(row, target=FR_STATUS_SUCCEEDED)
        except InvalidTransitionError:
            _log.warning(
                "yookassa_receipt_illegal_transition",
                object_id=object_id,
                current_status=row.status,
                target=FR_STATUS_SUCCEEDED,
            )
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=row.id,
                audit_correlation_id=None,
                event_type="receipt.succeeded",
                object_id=object_id,
                idempotency_outcome="illegal_transition",
            )
            return

        row.status = FR_STATUS_SUCCEEDED
        row.succeeded_at = datetime.now(UTC)

        # CHILD audit — fiscal_receipt_succeeded. The locked payload carries
        # audit_correlation_id = the originating dispatch chain UUID (Phase 51
        # plan 51-05 ARQ task records this on the row at INSERT-pending time;
        # Phase 50 D-50-18 step 5 records the webhook intake corr on the
        # 'sent' row). Either way row.audit_correlation_id is the chain anchor.
        await audit.emit(
            session,
            "fiscal_receipt_succeeded",
            actor_user_id=None,
            resource_type="fiscal_receipt",
            resource_id=row.id,
            audit_correlation_id=(
                str(row.audit_correlation_id)
                if row.audit_correlation_id is not None
                else None
            ),
            fiscal_receipt_id=str(row.id),
            yookassa_receipt_id=object_id,
        )

        # ROOT audit — yookassa_webhook_received.
        await audit.emit(
            session,
            "yookassa_webhook_received",
            actor_user_id=None,
            resource_type="yookassa_webhook",
            resource_id=row.id,
            audit_correlation_id=None,
            event_type="receipt.succeeded",
            object_id=object_id,
            idempotency_outcome="processed",
        )


async def handle_receipt_canceled(
    session: AsyncSession,
    *,
    body: dict[str, Any],
) -> None:
    """``receipt.canceled`` handler — Phase 51 D-51-22 atomic UoW.

    Mirror of ``handle_receipt_succeeded`` with target='failed' and
    ``failure_reason`` extracted from ``body['object']['cancellation_details']
    ['reason']`` (D-51-22). Falls back to the literal ``'yookassa_receipt_canceled'``
    when cancellation_details is missing or malformed.

    Phase 52 NOT-04 owner alert (operator should investigate manually) is OUT
    OF SCOPE for this plan — the structlog WARNING + audit row is the Phase 51
    baseline.
    """
    object_obj = body.get("object") or {}
    object_id = object_obj.get("id") if isinstance(object_obj, dict) else None
    if not isinstance(object_id, str) or not object_id:
        _log.warning("yookassa_webhook_missing_object_id", yk_event="receipt.canceled")
        return

    details_obj = (
        object_obj.get("cancellation_details") if isinstance(object_obj, dict) else None
    )
    details: dict[str, Any] = details_obj if isinstance(details_obj, dict) else {}
    failure_reason_raw = details.get("reason")
    failure_reason: str = (
        failure_reason_raw
        if isinstance(failure_reason_raw, str) and failure_reason_raw
        else "yookassa_receipt_canceled"
    )

    async with session.begin():
        row = await _select_for_update_fiscal_receipt(
            session, yookassa_receipt_id=object_id
        )
        if row is None:
            _log.warning(
                "yookassa_receipt_webhook_orphan",
                object_id=object_id,
                yk_event="receipt.canceled",
            )
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=None,
                audit_correlation_id=None,
                event_type="receipt.canceled",
                object_id=object_id,
                idempotency_outcome="orphan",
            )
            return

        try:
            _assert_can_transition_receipt(row, target=FR_STATUS_FAILED)
        except InvalidTransitionError:
            _log.warning(
                "yookassa_receipt_illegal_transition",
                object_id=object_id,
                current_status=row.status,
                target=FR_STATUS_FAILED,
            )
            await audit.emit(
                session,
                "yookassa_webhook_received",
                actor_user_id=None,
                resource_type="yookassa_webhook",
                resource_id=row.id,
                audit_correlation_id=None,
                event_type="receipt.canceled",
                object_id=object_id,
                idempotency_outcome="illegal_transition",
            )
            return

        row.status = FR_STATUS_FAILED
        row.failed_at = datetime.now(UTC)
        row.failure_reason = failure_reason

        # CHILD audit — fiscal_receipt_failed.
        await audit.emit(
            session,
            "fiscal_receipt_failed",
            actor_user_id=None,
            resource_type="fiscal_receipt",
            resource_id=row.id,
            audit_correlation_id=(
                str(row.audit_correlation_id)
                if row.audit_correlation_id is not None
                else None
            ),
            fiscal_receipt_id=str(row.id),
            failure_reason=failure_reason,
        )

        # ROOT audit — yookassa_webhook_received.
        await audit.emit(
            session,
            "yookassa_webhook_received",
            actor_user_id=None,
            resource_type="yookassa_webhook",
            resource_id=row.id,
            audit_correlation_id=None,
            event_type="receipt.canceled",
            object_id=object_id,
            idempotency_outcome="processed",
        )
