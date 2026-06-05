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
from sqlalchemy import select, text
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
from app.modules.loyalty.service import record_loyalty_redemption
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
from app.modules.promo_codes.service import record_promo_redemption

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


async def _read_client_receipt_contact(
    session: AsyncSession, client_id: UUID
) -> tuple[str | None, str]:
    """Fetch the client's receipt contact (email OR phone) via a narrow SELECT.

    Returns ``(email_or_None, phone)``. NOT a relationship traversal:
    OnlinePayment declares no ``client`` relationship, and even if it did the
    eager-load shape would be the wrong contract here (we want two columns, not
    the whole Client row inflated into the session identity map). Local twin of
    ``online_payments/service.py::_read_client_receipt_contact_or_raise`` — the
    cross-module import is deliberately NOT taken (D-54-08; same reason the old
    ``_read_customer_email`` was a local SELECT).

    D-10 (Phase 999.5) RETIRED the obsolete Phase-49 PAY-06 invariant that
    required ``clients.email IS NOT NULL`` before creating the OnlinePayment row.
    A «Чек не нужен» phone-only client (email NULL, phone set) is valid: the
    54-ФЗ receipt is fiscalized to the phone. So a NULL email is NO LONGER an
    error here — only a genuinely orphaned ``client_id`` (no matching alive row)
    rolls the webhook UoW back so ЮKassa retries (``RuntimeError`` preserved for
    that case). Phone is DB NOT NULL via the OTP-auth invariant.
    """
    row = (
        await session.execute(
            select(Client.email, Client.phone).where(
                Client.id == client_id, Client.deleted_at.is_(None)
            )
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError(f"Client {client_id} not found at webhook time")
    email: str | None = row.email
    phone: str = row.phone  # NOT NULL — OTP-auth invariant
    return email, phone


async def _post_commit_enqueue(
    arq_pool: Any | None = None,
    *,
    online_payment_id: UUID,
    subject_kind: Literal["membership", "pt_package"],
    subject_id: UUID,
    fiscal_receipt_id: UUID | None = None,
    payment_id: UUID | None = None,
    kind: str | None = None,
) -> None:
    """Post-commit enqueue (Phase 50 stub → Phase 51 fiscal-dispatch → Phase 52 notification).

    Phase 50 shipped this as a pure no-op (single ``_log.info`` call —
    DEFER-50-04). Phase 51 (D-51-15) ADDED the ``fiscal_receipt_id`` branch:
    when both ``arq_pool`` and ``fiscal_receipt_id`` are non-None, enqueues
    ``dispatch_fiscal_receipt`` with ``_max_tries=3`` + ``_expires=60``
    (Pitfall 11 / D-51-Discretion retry contract).

    Phase 52 (D-52-10 / D-52-11, this commit) ADDS the notification branch:
    when ``arq_pool``, ``payment_id``, and ``kind`` are all non-None, enqueues
    ``dispatch_payment_notification`` with ``_max_tries=3`` + ``_expires=60``.

    Signature lineage:
      - Phase 50 (D-50-19): ``(arq_pool, *, online_payment_id, subject_kind,
        subject_id)``.
      - Phase 51 (D-51-15): adds ``fiscal_receipt_id: UUID | None = None``.
      - Phase 52 (D-52-10): adds ``payment_id: UUID | None = None`` +
        ``kind: str | None = None`` (defaults preserve all existing callers).

    The AST gate at ``tests/integration/webhook_yookassa/test_post_commit_seam.py``
    asserts the EXACT structural shape of this body (one ``_log.info`` Expr
    + two guarded ``await arq_pool.enqueue_job(...)`` Ifs). Any structural
    change requires a lockstep update of that test in the SAME commit
    (PATTERNS.md errata #3 / D-52-11).
    """
    _log.info(
        "webhook_post_commit_enqueue",
        online_payment_id=str(online_payment_id),
        subject_kind=subject_kind,
        subject_id=str(subject_id),
        arq_pool_present=arq_pool is not None,
        fiscal_receipt_id=str(fiscal_receipt_id) if fiscal_receipt_id is not None else None,
        payment_id=str(payment_id) if payment_id is not None else None,
        kind=kind,
    )
    if arq_pool is not None and fiscal_receipt_id is not None:
        await arq_pool.enqueue_job(
            "dispatch_fiscal_receipt",
            str(fiscal_receipt_id),
            _max_tries=3,
            _expires=60,
        )
    if arq_pool is not None and payment_id is not None and kind is not None:
        await arq_pool.enqueue_job(
            "dispatch_payment_notification",
            _kwargs={"payment_id": str(payment_id), "kind": kind},
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

        # Blocker #4 — narrow SELECT of clients.(email, phone), NOT relationship
        # traversal. OnlinePayment has no client relationship wired. D-10
        # (Phase 999.5): email-OR-phone — a phone-only client is valid, so a NULL
        # email no longer raises (only a genuinely orphaned client_id does).
        customer_email, customer_phone = await _read_client_receipt_contact(session, row.client_id)

        # Subject-kind dispatch. The 0034 CHECK constraint
        # `(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)`
        # guarantees exactly one is non-None — the assert below is defense in
        # depth and would only fail on a DB-level constraint violation.
        # Explicit union annotation (Phase 63 DEBT-03) so mypy --strict accepts
        # both branch assignments without narrowing the first to a single Literal.
        subject_kind: Literal["membership", "pt_package"]
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

        # Phase 84 APAY-02: autopay discriminator — confirmation_type='autopay' on the
        # online_payments row signals that this payment was initiated by the off-session
        # charge cron, not an interactive redirect/QR checkout. The discriminator drives:
        #   1. method='autopay' vs 'online' in the charge-ledger record (plan 02 arch note).
        #   2. kind='autopay_charge_succeeded' vs 'payment_succeeded' in the success DM.
        # D-06 (webhook-locked activation): the membership renewal is ALWAYS activated here
        # regardless of is_autopay — activation path is unchanged.
        is_autopay: bool = row.confirmation_type == "autopay"

        # Blocker #2 — widened Protocol from Plan 50-03; webhook passes
        # audit_actor=None + received_by_user_id=None (anonymous flow).
        payment_row = await get_payment_recorder()(
            session,
            subject_kind=subject_kind,
            subject_id=subject_id,
            amount_kopecks=row.amount_kopecks,
            method="autopay" if is_autopay else "online",
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
        # D-10 (Phase 999.5): email-preferred-else-phone, never both — mirrors the
        # create_payment contact routing (online_payments/service.py). The phone
        # is the 54-ФЗ fallback when the client has no email («Чек не нужен»).
        fr_row = await insert_fiscal_receipt(
            session,
            payment_id=ledger_payment_id,
            kind=KIND_PAYMENT,
            status=STATUS_SENT,
            customer_email=customer_email,
            customer_phone=(customer_phone if customer_email is None else None),
            audit_correlation_id=webhook_intake_corr,
            sent_at=datetime.now(UTC),
        )
        await session.flush()
        fiscal_receipt_row_id: UUID = fr_row.id

        # Phase 999.4 D-07 / Phase 83 REDM-02: record promo redemption and/or loyalty
        # redemption when this payment carried either (or both).  Plan price lookup is
        # hoisted so it runs whenever EITHER promo_code_id OR loyalty_redeem_kopecks is
        # set — both branches need the plan price for correct attribution (T-83-08).
        # raw SQL only (D-54-08 — no cross-module ORM import from handlers.py).
        _need_plan_price = row.promo_code_id is not None or (
            row.loyalty_redeem_kopecks is not None and row.loyalty_redeem_kopecks > 0
        )
        plan_price_kopecks: int = row.amount_kopecks  # default: attribution == 0
        if _need_plan_price:
            if subject_kind == SUBJECT_KIND_MEMBERSHIP:
                _plan_table = "membership_plans"
            else:
                _plan_table = "pt_package_plans"
            _plan_price_row = (
                (
                    await session.execute(
                        # S608 below is safe: _plan_table is a server-only Literal
                        # ("membership_plans" | "pt_package_plans") chosen by subject_kind,
                        # never user input; no injection surface. The id is a bound param.
                        text(
                            f"SELECT price_kopecks FROM {_plan_table} WHERE id = :id"  # noqa: S608
                        ),
                        {"id": str(subject_id)},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if _plan_price_row is not None:
                plan_price_kopecks = int(_plan_price_row["price_kopecks"])

        if row.promo_code_id is not None:
            # T-83-08 attribution fix: subtract loyalty_redeem_kopecks so that promo
            # discount + loyalty debit together equal plan_price - amount_kopecks.
            # Without this fix a stacked promo+bonus payment over-attributes to promo.
            discount_kopecks_for_redemption = max(
                0,
                plan_price_kopecks - row.amount_kopecks - (row.loyalty_redeem_kopecks or 0),
            )
            if discount_kopecks_for_redemption > 0:
                await record_promo_redemption(
                    session,
                    promo_code_id=row.promo_code_id,
                    client_id=row.client_id,
                    online_payment_id=row.id,
                    discount_kopecks=discount_kopecks_for_redemption,
                )

        # Phase 83 REDM-02: write loyalty redemption ledger row on payment.succeeded.
        # record_loyalty_redemption is idempotent (partial UNIQUE on online_payment_id
        # WHERE entry_type='redemption') + overdraft-clamped — webhook replay is safe
        # (T-83-05 / T-83-06).  Debit only on succeeded; D-06 holds.
        if row.loyalty_redeem_kopecks is not None and row.loyalty_redeem_kopecks > 0:
            await record_loyalty_redemption(
                session,
                client_id=row.client_id,
                online_payment_id=row.id,
                requested_redeem_kopecks=row.loyalty_redeem_kopecks,
            )

        # PAYM-01 / Phase 79 step 8.5: upsert saved card token if save_payment_method=True.
        # Token source: result.payment_method (YooKassaPaymentResult field added in phase 79).
        # raw-SQL upsert — zero new ignore_imports (D-decision: no ORM import from integrations).
        # Idempotent: ON CONFLICT DO UPDATE so webhook replay is safe (T-79-09).
        # PII discipline (T-79-08): log emits client_id + online_payment_id only — no card fields.
        if row.save_payment_method and result.payment_method is not None:
            pm = result.payment_method  # YooKassaPaymentMethodInfo dataclass
            await session.execute(
                text(
                    "INSERT INTO client_payment_methods "
                    "(client_id, yookassa_method_id, last4, brand, "
                    " expiry_month, expiry_year, autopay_enabled) "
                    "VALUES (:client_id, :method_id, :last4, :brand, "
                    "        :expiry_month, :expiry_year, false) "
                    # Partial unique index uq_client_payment_methods_client_id_alive
                    # is a CREATE INDEX (not a CONSTRAINT), so ON CONFLICT must use
                    # the index inference-predicate form
                    # (ON CONFLICT (client_id) WHERE unlinked_at IS NULL) —
                    # NOT ON CONFLICT ON CONSTRAINT.
                    "ON CONFLICT (client_id) WHERE unlinked_at IS NULL "
                    "DO UPDATE SET "
                    "  yookassa_method_id = EXCLUDED.yookassa_method_id, "
                    "  last4 = EXCLUDED.last4, "
                    "  brand = EXCLUDED.brand, "
                    "  expiry_month = EXCLUDED.expiry_month, "
                    "  expiry_year = EXCLUDED.expiry_year, "
                    "  unlinked_at = NULL, "
                    # CR-79-01: only reset autopay/consent when the saved card
                    # token actually CHANGES. Re-saving the SAME card (e.g. a
                    # second membership checkout with savePaymentMethod=true)
                    # MUST preserve the client's existing ФЗ-376 autopay consent
                    # — wiping it silently is an unauthorised authorization-state
                    # regression. A new token ⇒ a new card ⇒ re-consent required.
                    "  autopay_enabled = CASE "
                    "    WHEN client_payment_methods.yookassa_method_id "
                    "         = EXCLUDED.yookassa_method_id "
                    "    THEN client_payment_methods.autopay_enabled "
                    "    ELSE false END, "
                    "  consent_recorded_at = CASE "
                    "    WHEN client_payment_methods.yookassa_method_id "
                    "         = EXCLUDED.yookassa_method_id "
                    "    THEN client_payment_methods.consent_recorded_at "
                    "    ELSE NULL END, "
                    "  updated_at = now()"
                ),
                {
                    "client_id": str(row.client_id),
                    "method_id": pm.id,
                    "last4": pm.last4,
                    "brand": pm.card_type,
                    "expiry_month": pm.expiry_month,
                    "expiry_year": pm.expiry_year,
                },
            )
            _log.info(
                "payment_method_saved",
                client_id=str(row.client_id),
                online_payment_id=str(row.id),
            )

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
        subject_kind_local: Literal["membership", "pt_package"] = subject_kind
        subject_id_local: UUID = subject_id
        fiscal_receipt_row_id_local: UUID = fiscal_receipt_row_id
        is_autopay_local: bool = is_autopay

    # Phase 51 D-51-15 — runs AFTER the ``async with session.begin():`` commit
    # boundary so an enqueue failure cannot poison the UoW. ``arq_pool`` is
    # threaded in from the router (``request.app.state.arq_pool``); when
    # ``None`` (e.g. in unit tests that bypass the lifespan) the enqueue is
    # a no-op. ``fiscal_receipt_row_id_local`` is the just-INSERTed
    # fiscal_receipts row id; the worker reads the full row at task entry
    # (plan 51-05).
    # Phase 84 APAY-02: discriminator — use literal strings at the enqueue site
    # so both branches are structurally unambiguous (plan 02 arch note).
    # CR-01 fix: dispatch_payment_notification looks the subject up by the
    # `payment_id` it receives. For 'payment_succeeded' the task reads the
    # `payments` ledger row (→ ledger_payment_id); for 'autopay_charge_succeeded'
    # it reads the `online_payments` row + claims on online_payment_id (→ op_row_id).
    # Passing ledger_payment_id for autopay made the lookup miss (payments.id !=
    # online_payments.id) and the success DM was silently dropped.
    if is_autopay_local:
        notification_kind: str = "autopay_charge_succeeded"
        notification_payment_id: UUID = op_row_id
    else:
        notification_kind = "payment_succeeded"
        notification_payment_id = ledger_payment_id
    await _post_commit_enqueue(
        arq_pool,
        online_payment_id=op_row_id,
        subject_kind=subject_kind_local,
        subject_id=subject_id_local,
        fiscal_receipt_id=fiscal_receipt_row_id_local,
        payment_id=notification_payment_id,
        kind=notification_kind,
    )


async def handle_payment_canceled(
    session: AsyncSession,
    yookassa_client: YooKassaClient,
    *,
    body: dict[str, Any],
    arq_pool: Any | None = None,
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

        # Capture for post-commit hook — row is detached after commit.
        op_row_id_canceled: UUID = row.id

    # Phase 52 NOT-05 / D-52-10 — owner operator alert (no client DM on cancellation).
    # Keyed on online_payments.id (op_row_id_canceled) because a canceled payment
    # has no ledger payments row (activation is webhook-gated; canceled payments
    # never activate). The dispatch_payment_notification task routes
    # kind="payment_canceled" to claim_payment_notification(online_payment_id=...)
    # via the Plan 01 polymorphic-subject schema — no FK violation occurs.
    if arq_pool is not None:
        await arq_pool.enqueue_job(
            "dispatch_payment_notification",
            _kwargs={"payment_id": str(op_row_id_canceled), "kind": "payment_canceled"},
            _max_tries=3,
            _expires=60,
        )


async def handle_refund_succeeded(
    session: AsyncSession,
    yookassa_client: YooKassaClient,
    *,
    body: dict[str, Any],
    arq_pool: Any | None = None,
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

    # Captured by _settle_online_refund when the UoW settles successfully so
    # the post-commit hook can enqueue dispatch_fiscal_receipt for the
    # just-INSERTed refund-side fiscal_receipts row. Stays None on orphan /
    # illegal-transition / idempotent-replay paths (those exit before
    # _settle_online_refund is called, or roll back the txn).
    settled_locals = None

    try:
        async with session.begin():
            row = await _select_for_update_online_refund(session, yookassa_refund_id=object_id)
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
            settled_locals = await _settle_online_refund(
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
        if isinstance(exc, AlreadyRefundedError) or _is_refund_of_uniqueness_conflict(exc):
            _log.warning(
                "yookassa_refund_idempotent_replay",
                yookassa_refund_id=object_id,
            )
            return
        raise

    # Phase 51 verification gap fix — runs AFTER the ``async with
    # session.begin():`` commit boundary so an enqueue failure cannot poison
    # the UoW. Mirrors the handle_payment_succeeded enqueue path (D-51-15).
    # Only fires when ``_settle_online_refund`` returned (successful UoW
    # commit) — orphan / illegal-transition / idempotent-replay branches
    # exit before reaching the helper, so ``settled_locals`` stays None.
    # Without this hook, the refund-side ``fiscal_receipts(kind='refund',
    # status='sent')`` row would sit forever — 54-ФЗ compliance gap.
    if settled_locals is not None:
        await _post_commit_enqueue(
            arq_pool,
            online_payment_id=settled_locals.online_payment_id,
            subject_kind=settled_locals.subject_kind,
            subject_id=settled_locals.subject_id,
            fiscal_receipt_id=settled_locals.fiscal_receipt_id,
            payment_id=settled_locals.refund_payment_id,
            kind="refund_succeeded",
        )


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
        row = await _select_for_update_fiscal_receipt(session, yookassa_receipt_id=object_id)
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
                str(row.audit_correlation_id) if row.audit_correlation_id is not None else None
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

    details_obj = object_obj.get("cancellation_details") if isinstance(object_obj, dict) else None
    details: dict[str, Any] = details_obj if isinstance(details_obj, dict) else {}
    failure_reason_raw = details.get("reason")
    failure_reason: str = (
        failure_reason_raw
        if isinstance(failure_reason_raw, str) and failure_reason_raw
        else "yookassa_receipt_canceled"
    )

    async with session.begin():
        row = await _select_for_update_fiscal_receipt(session, yookassa_receipt_id=object_id)
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
                str(row.audit_correlation_id) if row.audit_correlation_id is not None else None
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
