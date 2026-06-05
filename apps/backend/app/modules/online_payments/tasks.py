"""ARQ task — cross-channel fan-out for online-payment notifications (Phase 52 NOT-01).

Dispatches BOTH a Telegram DM and an email for each payment event kind, with
per-channel idempotency via ``payment_notifications`` (D-52-02). Single task
handles all four notification kinds:

    payment_succeeded  — client DM + email (Telegram: chat_id, email: client.email)
    refund_succeeded   — client DM + email (same recipient resolution via ledger row)
    payment_canceled   — owner-alert only  (no client DM per NOT-05)
    fiscal_failed      — owner-alert only  (NOT-04)

Claim-before-send (D-52-02): the idempotency INSERT happens BEFORE the channel
send. A crash mid-send leaves the row claimed (at-most-once leaning), preventing
duplicate client DMs on retry storms.

Best-effort (D-52-02 / D-45-08): a send failure on one channel NEVER blocks the
other and NEVER rolls back the financial commit. The task runs in the background
worker, fully decoupled from the webhook that wrote the payment row.

Owner-alert routing (D-52-09): ``payment_canceled`` and ``fiscal_failed`` route to
``settings.owner_alert_telegram_chat_id`` / ``settings.owner_alert_email``.
When either setting is None, a structlog ERROR is emitted and the channel is
skipped without raising (best-effort, never crashes the task).

Email template_id gate (D-52-07 / AST gate): every ``template_id=`` argument
passed to ``get_email_dispatcher()(...)`` is a STRING LITERAL — never a variable
reference. The AST gate in ``tests/unit/test_locked_email_templates_ast.py``
enforces this statically.

Bot construction (D-39-10 / D-27-06 mirror): fresh Bot per task invocation via
``build_bot(token=...)``. NEVER cached at module scope (aiohttp session leak risk
under repeated ARQ runs).

Cross-module boundary (D-06 / D-09 / modules-independent import-linter contract):
client + membership + pt_package tables are referenced via
``Base.metadata.tables[<name>]`` (raw SA Table objects), not by importing those
ORM classes. This preserves the modules-independent contract while allowing the
SQL join to resolve ``client.telegram_user_id`` / ``client.email`` from a
``payments.id`` ledger row.
"""

from __future__ import annotations

from typing import Any, Final
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.dependencies import get_email_dispatcher
from app.core.formatters import format_money
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.autopay_charges import notifications as autopay_notifications
from app.modules.online_payments import notifications as payment_notifications
from app.modules.online_payments import repository as payment_repo

_log: Final = structlog.get_logger("modules.online_payments.tasks")
_MAX_TRIES: Final[int] = 3

# Notification kinds whose recipient is the owner (operator alert — NOT a client DM).
_OWNER_ALERT_KINDS: Final[frozenset[str]] = frozenset({"payment_canceled", "fiscal_failed"})


# ---------------------------------------------------------------------------
# Recipient resolution helpers
# ---------------------------------------------------------------------------


def _memberships_table() -> Any:
    """Return the ``memberships`` SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["memberships"]


def _pt_packages_table() -> Any:
    """Return the ``pt_packages`` SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["pt_packages"]


def _clients_table() -> Any:
    """Return the ``clients`` SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["clients"]


def _payments_table() -> Any:
    """Return the ``payments`` SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["payments"]


async def _resolve_client_row(
    session: AsyncSession,
    payment_uuid: UUID,
) -> tuple[str, str | None, int | None] | None:
    """Resolve (first_name, email, telegram_user_id) from a ``payments.id`` ledger row.

    Handles all three ``subject_kind`` values:
    - ``'membership'``:  payments.subject_id → memberships.client_id → clients
    - ``'pt_package'``:  payments.subject_id → pt_packages.client_id → clients
    - ``'refund'``:      payments.refund_of  → original payment → same as above

    Returns None if the payment row does not exist or the client cannot be resolved.
    Cross-module tables accessed via ``Base.metadata.tables[<name>]`` (raw SA
    Table objects) so the modules-independent import-linter contract is preserved.
    """
    payments = _payments_table()
    memberships = _memberships_table()
    pt_packages = _pt_packages_table()
    clients = _clients_table()

    # Step 1: fetch the payment row (or follow refund_of for refund kind).
    payment_row = await session.execute(
        select(
            payments.c.subject_kind,
            payments.c.subject_id,
            payments.c.refund_of,
        ).where(payments.c.id == payment_uuid)
    )
    payment = payment_row.first()
    if payment is None:
        _log.warning("payment_notification_payment_not_found", payment_id=str(payment_uuid))
        return None

    subject_kind: str = payment.subject_kind
    subject_id: UUID = payment.subject_id
    refund_of: UUID | None = payment.refund_of

    # For refund rows follow the chain to the original sale payment.
    if subject_kind == "refund":
        if refund_of is None:
            _log.warning(
                "payment_notification_refund_missing_refund_of",
                payment_id=str(payment_uuid),
            )
            return None
        # Re-read the original sale payment.
        origin_row = await session.execute(
            select(
                payments.c.subject_kind,
                payments.c.subject_id,
            ).where(payments.c.id == refund_of)
        )
        origin = origin_row.first()
        if origin is None:
            _log.warning(
                "payment_notification_origin_payment_not_found",
                payment_id=str(payment_uuid),
                refund_of=str(refund_of),
            )
            return None
        subject_kind = origin.subject_kind
        subject_id = origin.subject_id

    # Step 2: resolve client_id from the membership or pt_package row.
    if subject_kind == "membership":
        client_id_row = await session.execute(
            select(memberships.c.client_id).where(memberships.c.id == subject_id)
        )
    elif subject_kind == "pt_package":
        client_id_row = await session.execute(
            select(pt_packages.c.client_id).where(pt_packages.c.id == subject_id)
        )
    else:
        _log.warning(
            "payment_notification_unknown_subject_kind",
            payment_id=str(payment_uuid),
            subject_kind=subject_kind,
        )
        return None

    client_id_result = client_id_row.scalar_one_or_none()
    if client_id_result is None:
        _log.warning(
            "payment_notification_subject_not_found",
            payment_id=str(payment_uuid),
            subject_kind=subject_kind,
            subject_id=str(subject_id),
        )
        return None

    # Step 3: fetch client contact fields.
    client_row = await session.execute(
        select(
            clients.c.first_name,
            clients.c.email,
            clients.c.telegram_user_id,
        ).where(clients.c.id == client_id_result)
    )
    client = client_row.first()
    if client is None:
        _log.warning(
            "payment_notification_client_not_found",
            payment_id=str(payment_uuid),
            client_id=str(client_id_result),
        )
        return None

    return client.first_name, client.email, client.telegram_user_id


async def _resolve_payment_amount(session: AsyncSession, payment_uuid: UUID) -> int:
    """Return ``|amount_kopecks|`` for the payment row (always positive for display)."""
    payments = _payments_table()
    row = await session.execute(
        select(payments.c.amount_kopecks).where(payments.c.id == payment_uuid)
    )
    kopecks: int | None = row.scalar_one_or_none()
    return abs(kopecks) if kopecks is not None else 0


async def _resolve_yookassa_payment_id(session: AsyncSession, online_payment_uuid: UUID) -> str:
    """Return the ЮKassa payment_id string from an online_payments row.

    Used for the payment_canceled owner-alert DM which needs yookassa_payment_id.
    """
    from app.core.database import Base

    online_payments = Base.metadata.tables["online_payments"]
    row = await session.execute(
        select(online_payments.c.yookassa_payment_id).where(
            online_payments.c.id == online_payment_uuid
        )
    )
    yookassa_id: str | None = row.scalar_one_or_none()
    return yookassa_id or ""


# ---------------------------------------------------------------------------
# Email dispatch helper — all template_id are STRING LITERALS (AST gate)
# ---------------------------------------------------------------------------


async def _resolve_autopay_membership_end_date(
    session: AsyncSession,
    online_payment_uuid: UUID,
) -> str:
    """Resolve the new membership end_date for an autopay-confirmed renewal.

    Looks up the newest active membership for the client associated with the
    online_payments row (via membership_plan_id → memberships). Returns the
    end_date as a formatted "DD.MM.YYYY" string, or "" if not resolvable.

    Cross-module tables accessed via ``Base.metadata.tables[<name>]``
    (D-54-08 modules-independent pattern).
    """
    from app.core.database import Base

    online_payments = Base.metadata.tables["online_payments"]
    memberships = _memberships_table()

    # Fetch (client_id, membership_plan_id) from the online_payments row.
    op_row = await session.execute(
        select(
            online_payments.c.client_id,
            online_payments.c.membership_plan_id,
        ).where(online_payments.c.id == online_payment_uuid)
    )
    op = op_row.first()
    if op is None or op.membership_plan_id is None:
        return ""

    # Pick the newest active membership for this client + plan (webhook just activated it).
    mem_row = await session.execute(
        select(memberships.c.end_date)
        .where(memberships.c.client_id == op.client_id)
        .where(memberships.c.plan_id == op.membership_plan_id)
        .where(memberships.c.status == "active")
        .order_by(memberships.c.end_date.desc())
        .limit(1)
    )
    mem = mem_row.first()
    if mem is None:
        return ""

    end_date: Any = mem.end_date
    # Format as "DD.MM.YYYY" (Russian date display convention).
    try:
        formatted: str = end_date.strftime("%d.%m.%Y")
        return formatted
    except AttributeError:
        return str(end_date)


async def _dispatch_email(
    kind: str,
    to: str,
    *,
    first_name: str = "",
    amount_rub: str = "",
    payment_id: str = "",
    yookassa_payment_id: str = "",
    failure_reason: str = "",
    end_date: str = "",
) -> None:
    """Dispatch an email for the given payment notification kind.

    Every ``template_id=`` argument is a string literal — required by the AST gate
    in ``tests/unit/test_locked_email_templates_ast.py`` (D-52-07 / D-41-11).
    """
    dispatcher = get_email_dispatcher()
    audit_correlation_id = uuid4()
    if kind == "payment_succeeded":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            first_name=first_name,
            amount_rub=amount_rub,
        )
    elif kind == "autopay_charge_succeeded":
        # Phase 84 APAY-04: autopay renewal success email (client-facing, owner-signed).
        # Keyed on online_payment_id (the webhook created the online_payments row).
        # STRING LITERAL template_id required by AST gate (D-52-07).
        await dispatcher(
            template_id="EMAIL_AUTOPAY_CHARGE_SUCCEEDED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            first_name=first_name,
            amount_rub=amount_rub,
            end_date=end_date,
        )
    elif kind == "refund_succeeded":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_REFUNDED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            first_name=first_name,
            amount_rub=amount_rub,
        )
    elif kind == "payment_canceled":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_CANCELED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            payment_id=payment_id,
            yookassa_payment_id=yookassa_payment_id,
        )
    elif kind == "fiscal_failed":
        await dispatcher(
            template_id="EMAIL_FISCAL_RECEIPT_FAILED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            payment_id=payment_id,
            failure_reason=failure_reason,
        )
    else:  # pragma: no cover
        raise ValueError(f"unknown payment notification kind: {kind!r}")


# ---------------------------------------------------------------------------
# ARQ task entry point
# ---------------------------------------------------------------------------


async def dispatch_payment_notification(ctx: dict[str, Any], *, payment_id: str, kind: str) -> str:
    """ARQ task body. Returns ``'sent'`` | ``'partial'`` | ``'skipped'``.

    ctx keys required (wired in WorkerSettings.on_startup):
      - sessionmaker: async_sessionmaker[AsyncSession]
      - job_try: int (provided by ARQ runtime; defaults to 1 if absent)

    ``payment_id`` is an OPAQUE subject id whose column meaning depends on ``kind``
    (D-52-10 / Plan 01 Option A polymorphic subject):
      - payment_succeeded / refund_succeeded / fiscal_failed →
            payment_id == payments.id (ledger row exists)
      - payment_canceled →
            payment_id == online_payments.id (NO ledger row for canceled payments)

    The claim step routes the DB column accordingly (see CLAIM block below).
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["sessionmaker"]
    settings = get_settings()

    # D-39-10: fresh Bot per invocation — never cached at module scope
    # (aiohttp session leak risk under repeated ARQ runs).
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    payment_uuid = UUID(payment_id)

    # Resolve contextual data used across channels (loaded once, shared).
    # Loaded inside a fresh read-session; the per-channel claim sessions are
    # independent UoWs that open their own sessions via session_factory.
    is_owner_alert = kind in _OWNER_ALERT_KINDS

    if not is_owner_alert:
        # Client kinds — resolve from the payments ledger row.
        # autopay_charge_succeeded uses online_payments.id as payment_uuid;
        # other client kinds use payments.id.
        async with session_factory() as session:
            if kind == "autopay_charge_succeeded":
                # Recipient resolution for autopay success: online_payments row →
                # memberships → clients (via client_id on online_payments directly).
                op_clients = _clients_table()
                from app.core.database import Base as _Base

                _online_payments_tbl = _Base.metadata.tables["online_payments"]
                op_row = await session.execute(
                    select(
                        _online_payments_tbl.c.client_id,
                    ).where(_online_payments_tbl.c.id == payment_uuid)
                )
                op = op_row.first()
                if op is None:
                    _log.error(
                        "payment_notification_client_not_resolvable",
                        payment_id=payment_id,
                        kind=kind,
                    )
                    return "skipped"
                client_row_result = await session.execute(
                    select(
                        op_clients.c.first_name,
                        op_clients.c.email,
                        op_clients.c.telegram_user_id,
                    ).where(op_clients.c.id == op.client_id)
                )
                client_data = client_row_result.first()
                if client_data is None:
                    _log.error(
                        "payment_notification_client_not_resolvable",
                        payment_id=payment_id,
                        kind=kind,
                    )
                    return "skipped"
                client_first_name = client_data.first_name
                client_email = client_data.email
                client_telegram_user_id = client_data.telegram_user_id
                # Resolve the online_payments amount_kopecks.
                op_amount_row = await session.execute(
                    select(_online_payments_tbl.c.amount_kopecks).where(
                        _online_payments_tbl.c.id == payment_uuid
                    )
                )
                amount_kopecks = abs(op_amount_row.scalar_one_or_none() or 0)
                # Resolve new membership end date for the success DM.
                autopay_end_date = await _resolve_autopay_membership_end_date(session, payment_uuid)
            else:
                client_result = await _resolve_client_row(session, payment_uuid)
                if client_result is None:
                    _log.error(
                        "payment_notification_client_not_resolvable",
                        payment_id=payment_id,
                        kind=kind,
                    )
                    return "skipped"
                client_first_name, client_email, client_telegram_user_id = client_result
                amount_kopecks = await _resolve_payment_amount(session, payment_uuid)
                autopay_end_date = ""
        amount_rub = format_money(amount_kopecks)
    else:
        # Owner-alert kinds — context data fetched per channel below.
        client_first_name = ""
        client_email = None
        client_telegram_user_id = None
        amount_rub = ""
        autopay_end_date = ""

    channels_sent: list[str] = []

    for channel in ("telegram", "email"):
        # ── STEP 1: resolve recipient ─────────────────────────────────────
        if channel == "telegram":
            if is_owner_alert:
                tg_chat_id = settings.owner_alert_telegram_chat_id
                if tg_chat_id is None:
                    _log.error(
                        "owner_alert_telegram_not_configured",
                        kind=kind,
                        payment_id=payment_id,
                    )
                    continue  # best-effort — never raise (D-52-09)
                chat_id: int = tg_chat_id
            else:
                if client_telegram_user_id is None:
                    _log.info(
                        "payment_notification_channel_skipped",
                        payment_id=payment_id,
                        kind=kind,
                        channel=channel,
                        reason="no_telegram_user_id",
                    )
                    continue  # no idempotency row for absent channel
                chat_id = client_telegram_user_id
        else:  # email
            if is_owner_alert:
                owner_email = settings.owner_alert_email
                if owner_email is None:
                    _log.error(
                        "owner_alert_email_not_configured",
                        kind=kind,
                        payment_id=payment_id,
                    )
                    continue  # best-effort — never raise (D-52-09)
                email_addr: str = owner_email
            else:
                if client_email is None:
                    _log.info(
                        "payment_notification_channel_skipped",
                        payment_id=payment_id,
                        kind=kind,
                        channel=channel,
                        reason="no_email",
                    )
                    continue  # no idempotency row for absent channel
                email_addr = client_email

        # ── STEP 2: CLAIM via idempotency INSERT (claim-before-send, D-52-02) ──
        # D-52-10 polymorphic subject routing:
        #   - payment_canceled: online_payment_id (no payments ledger row for canceled)
        #   - autopay_charge_succeeded: online_payment_id (the webhook created the
        #     online_payments row; there is a payments row too, but the task is enqueued
        #     with the online_payments.id so we key on that for unambiguous idempotency)
        #   - all other kinds: payment_id (the payments.id ledger row exists)
        if kind in ("payment_canceled", "autopay_charge_succeeded"):
            claimed = await payment_repo.claim_payment_notification(
                session_factory,
                kind=kind,
                channel=channel,
                online_payment_id=payment_uuid,
            )
        else:
            claimed = await payment_repo.claim_payment_notification(
                session_factory,
                kind=kind,
                channel=channel,
                payment_id=payment_uuid,
            )
        if not claimed:
            _log.info(
                "payment_notification_idempotent_replay",
                payment_id=payment_id,
                kind=kind,
                channel=channel,
            )
            continue  # already sent in a prior invocation or concurrent task

        # ── STEP 3: SEND — best-effort; failure never blocks the other channel ──
        try:
            if channel == "telegram":
                if kind == "payment_succeeded":
                    text = payment_notifications.render_online_payment_succeeded_dm(
                        client_name=client_first_name,
                        amount_rub=amount_rub,
                    )
                elif kind == "autopay_charge_succeeded":
                    # Phase 84 APAY-04: autopay renewal success DM (client-facing).
                    text = autopay_notifications.render_autopay_charge_succeeded_dm(
                        client_name=client_first_name,
                        amount_rub=amount_rub,
                        end_date=autopay_end_date,
                    )
                elif kind == "refund_succeeded":
                    text = payment_notifications.render_online_payment_refunded_dm(
                        client_name=client_first_name,
                        amount_rub=amount_rub,
                    )
                elif kind == "payment_canceled":
                    # Fetch yookassa_payment_id for the owner-alert DM.
                    async with session_factory() as session:
                        yookassa_pid = await _resolve_yookassa_payment_id(session, payment_uuid)
                    text = payment_notifications.render_online_payment_canceled_dm(
                        payment_id=payment_id,
                        yookassa_payment_id=yookassa_pid,
                    )
                elif kind == "fiscal_failed":
                    # failure_reason not available in task args; use payment_id
                    # as the sole identifier — owner checks ЮKassa manually.
                    text = payment_notifications.render_fiscal_receipt_failed_dm(
                        payment_id=payment_id,
                        failure_reason="see fiscal_receipts table",
                    )
                else:  # pragma: no cover
                    raise ValueError(f"unknown kind for Telegram DM: {kind!r}")
                await telegram_sender.send_text_dm(bot, chat_id=chat_id, text=text)
            else:  # email
                kwargs: dict[str, str] = {}
                if kind == "payment_succeeded":
                    kwargs = {
                        "first_name": client_first_name,
                        "amount_rub": amount_rub,
                    }
                elif kind == "autopay_charge_succeeded":
                    # Phase 84 APAY-04: autopay success email (client-facing).
                    kwargs = {
                        "first_name": client_first_name,
                        "amount_rub": amount_rub,
                        "end_date": autopay_end_date,
                    }
                elif kind == "refund_succeeded":
                    kwargs = {
                        "first_name": client_first_name,
                        "amount_rub": amount_rub,
                    }
                elif kind == "payment_canceled":
                    async with session_factory() as session:
                        yookassa_pid = await _resolve_yookassa_payment_id(session, payment_uuid)
                    kwargs = {
                        "payment_id": payment_id,
                        "yookassa_payment_id": yookassa_pid,
                    }
                elif kind == "fiscal_failed":
                    kwargs = {
                        "payment_id": payment_id,
                        "failure_reason": "see fiscal_receipts table",
                    }
                await _dispatch_email(kind, email_addr, **kwargs)
        except Exception:
            _log.exception(
                "payment_notification_send_failed",
                payment_id=payment_id,
                kind=kind,
                channel=channel,
            )
            # Never re-raise — one channel failure must not block the other
            # and must not roll back the financial commit (D-52-02 / D-45-08).
            continue

        channels_sent.append(channel)
        _log.info(
            "payment_notification_sent",
            payment_id=payment_id,
            kind=kind,
            channel=channel,
        )

    if not channels_sent:
        return "skipped"
    if len(channels_sent) == 2:
        return "sent"
    return "partial"
