"""ARQ task — autopay failure notification dispatcher (Phase 84 APAY-04).

``dispatch_autopay_failure_notification`` is the background task enqueued by the
``charge_expiring_autopay`` cron (Plan 02) AFTER commit for each declined charge. It
notifies the client on both Telegram + email that the autopay renewal did not succeed
and asks them to update their card.

Architecture:
  - Keyed on ``autopay_charge_id`` (autopay_charges.id), NOT online_payment_id.
    A sync decline creates NO online_payments row (yookassa_payment_id is NOT NULL
    invariant — no payment id exists on decline), so idempotency MUST be anchored
    on the always-present autopay_charges.id.
  - Idempotency via ``claim_autopay_failure_notification`` (UNIQUE(autopay_charge_id,
    kind, channel) in autopay_charge_notifications). A replayed task invocation
    finds the claim already inserted and skips the send on all channels.
  - Best-effort (D-52-02 / D-45-08 mirror): a send failure on one channel NEVER
    blocks the other and NEVER re-raises. The outer try/except continues to the
    next channel.
  - Recipient resolution via raw SQL metadata-table reads (D-54-08 — no cross-module
    ORM import): autopay_charges → memberships → clients.

Cross-module boundary: recipient (first_name, email, telegram_user_id) is resolved
via ``Base.metadata.tables[<name>]`` raw SA Table objects (D-54-08). No ORM import
from memberships or clients modules.

Bot construction (D-39-10 / D-27-06 mirror): fresh Bot per task invocation via
``build_bot(token=...)``. NEVER cached at module scope (aiohttp session leak risk
under repeated ARQ runs).

Email template_id gate (D-52-07 / AST gate): every ``template_id=`` argument
passed to ``get_email_dispatcher()(...)`` is a STRING LITERAL.
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
from app.modules.autopay_charges import repository as autopay_repo

_log: Final = structlog.get_logger("modules.autopay_charges.tasks")


# ---------------------------------------------------------------------------
# Metadata-table accessors (D-54-08 — no cross-module ORM import)
# ---------------------------------------------------------------------------


def _autopay_charges_table() -> Any:
    """Return the autopay_charges SA Table via metadata."""
    from app.core.database import Base

    return Base.metadata.tables["autopay_charges"]


def _memberships_table() -> Any:
    """Return the memberships SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["memberships"]


def _clients_table() -> Any:
    """Return the clients SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["clients"]


# ---------------------------------------------------------------------------
# Recipient resolution helper
# ---------------------------------------------------------------------------


async def _resolve_failure_recipient(
    session: AsyncSession,
    charge_uuid: UUID,
) -> tuple[str, str | None, int | None, int] | None:
    """Resolve (first_name, email, telegram_user_id, amount_kopecks) for a failed charge.

    Joins autopay_charges → memberships → clients via metadata table objects.
    Returns None if any row in the chain is missing.

    Cross-module tables accessed via ``Base.metadata.tables[<name>]``
    (D-54-08 modules-independent pattern).
    """
    autopay_charges = _autopay_charges_table()
    memberships = _memberships_table()
    clients = _clients_table()

    # Step 1: fetch membership_id + amount_kopecks from the autopay_charges row.
    charge_row = await session.execute(
        select(
            autopay_charges.c.membership_id,
            autopay_charges.c.amount_kopecks,
        ).where(autopay_charges.c.id == charge_uuid)
    )
    charge = charge_row.first()
    if charge is None:
        _log.warning(
            "autopay_failure_notification_charge_not_found",
            autopay_charge_id=str(charge_uuid),
        )
        return None

    membership_id: UUID = charge.membership_id
    amount_kopecks: int = charge.amount_kopecks

    # Step 2: resolve client_id from memberships row.
    mem_row = await session.execute(
        select(memberships.c.client_id).where(memberships.c.id == membership_id)
    )
    client_id = mem_row.scalar_one_or_none()
    if client_id is None:
        _log.warning(
            "autopay_failure_notification_membership_not_found",
            autopay_charge_id=str(charge_uuid),
            membership_id=str(membership_id),
        )
        return None

    # Step 3: fetch client contact fields.
    client_row = await session.execute(
        select(
            clients.c.first_name,
            clients.c.email,
            clients.c.telegram_user_id,
        ).where(clients.c.id == client_id)
    )
    client = client_row.first()
    if client is None:
        _log.warning(
            "autopay_failure_notification_client_not_found",
            autopay_charge_id=str(charge_uuid),
            client_id=str(client_id),
        )
        return None

    return client.first_name, client.email, client.telegram_user_id, amount_kopecks


# ---------------------------------------------------------------------------
# ARQ task entry point
# ---------------------------------------------------------------------------


async def dispatch_autopay_failure_notification(
    ctx: dict[str, Any], *, autopay_charge_id: str
) -> str:
    """ARQ task body for autopay failure notifications. Returns 'sent' | 'partial' | 'skipped'.

    Notifies the client that their autopay renewal failed and asks them to update
    their card. Loops both channels (Telegram + email); each channel is individually
    idempotent via ``claim_autopay_failure_notification``.

    ctx keys required (wired in WorkerSettings.on_startup):
      - sessionmaker: async_sessionmaker[AsyncSession]

    ``autopay_charge_id`` is the ``autopay_charges.id`` UUID (string) for the declined
    charge. There is NO online_payments row for a sync decline, so idempotency keys
    on the always-present autopay_charges.id (NOT online_payment_id).

    Best-effort (D-52-02 / D-45-08 mirror):
      - A send failure on one channel NEVER blocks the other channel.
      - A send failure NEVER re-raises — the exception is caught, logged, and the
        channel loop continues to the next channel.
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["sessionmaker"]
    settings = get_settings()

    # D-39-10: fresh Bot per invocation — never cached at module scope.
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    charge_uuid = UUID(autopay_charge_id)

    # Resolve recipient once (shared across channels).
    async with session_factory() as session:
        result = await _resolve_failure_recipient(session, charge_uuid)

    if result is None:
        _log.error(
            "autopay_failure_notification_skipped_unresolvable",
            autopay_charge_id=autopay_charge_id,
        )
        return "skipped"

    client_first_name, client_email, client_telegram_user_id, amount_kopecks = result
    amount_rub = format_money(amount_kopecks)

    channels_sent: list[str] = []

    for channel in ("telegram", "email"):
        # ── STEP 1: resolve recipient for this channel ────────────────────
        if channel == "telegram":
            if client_telegram_user_id is None:
                _log.info(
                    "autopay_failure_notification_channel_skipped",
                    autopay_charge_id=autopay_charge_id,
                    channel=channel,
                    reason="no_telegram_user_id",
                )
                continue  # no idempotency row for absent channel
            chat_id: int = client_telegram_user_id
        else:  # email
            if client_email is None:
                _log.info(
                    "autopay_failure_notification_channel_skipped",
                    autopay_charge_id=autopay_charge_id,
                    channel=channel,
                    reason="no_email",
                )
                continue  # no idempotency row for absent channel
            email_addr: str = client_email

        # ── STEP 2: CLAIM via idempotency INSERT (claim-before-send, D-52-02) ──
        # Keyed on autopay_charge_id (NOT online_payment_id — decline has no online_payments row).
        claimed = await autopay_repo.claim_autopay_failure_notification(
            session_factory,
            channel=channel,
            autopay_charge_id=charge_uuid,
        )
        if not claimed:
            _log.info(
                "autopay_failure_notification_idempotent_replay",
                autopay_charge_id=autopay_charge_id,
                channel=channel,
            )
            continue  # already sent in a prior invocation or concurrent task

        # ── STEP 3: SEND — best-effort; failure never blocks the other channel ──
        try:
            if channel == "telegram":
                text = autopay_notifications.render_autopay_charge_failed_dm(
                    client_name=client_first_name,
                    amount_rub=amount_rub,
                )
                await telegram_sender.send_text_dm(bot, chat_id=chat_id, text=text)
            else:  # email
                dispatcher = get_email_dispatcher()
                await dispatcher(
                    template_id="EMAIL_AUTOPAY_CHARGE_FAILED",
                    to=email_addr,
                    audit_correlation_id=uuid4(),
                    first_name=client_first_name,
                    amount_rub=amount_rub,
                )
        except Exception:
            _log.exception(
                "autopay_failure_notification_send_failed",
                autopay_charge_id=autopay_charge_id,
                channel=channel,
            )
            # Never re-raise — one channel failure must not block the other
            # (D-52-02 / D-45-08 best-effort discipline).
            continue

        channels_sent.append(channel)
        _log.info(
            "autopay_failure_notification_sent",
            autopay_charge_id=autopay_charge_id,
            channel=channel,
        )

    if not channels_sent:
        return "skipped"
    if len(channels_sent) == 2:
        return "sent"
    return "partial"
