"""Notifications service (Phase 87 INBOX-01..04).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).

Dedup approach: repository.insert_notification uses pg_insert ON CONFLICT DO NOTHING
on the named UNIQUE constraint (not IntegrityError + rollback) — SAVEPOINT-safe so
callers in event hooks / webhook handlers don't break the outer transaction (T-87-03).

Public API (consumed by Plan 02 client router + Plan 03 event hooks):
  create_notification         — co-transactional insert with UNIQUE dedup (T-87-03)
  list_client_notifications   — paginated inbox read with unread_count
  mark_notification_read      — UPDATE WHERE client_id (IDOR-safe, T-87-01)
  mark_all_notifications_read — bulk mark-read scoped to caller (T-87-01)
  register_push_token         — idempotent upsert (alive) push-token (T-87-04)

Phase 108 CFG-04 additions:
  _ALWAYS_ON_KINDS   — payment/autopay-failure triggers that bypass all gating (T-108-10)
  create_notification now gates on notification_prefs_config matrix + quiet hours
  before inserting (read via raw sa.text() SELECT — no settings-module import per D-54-08).
"""

from __future__ import annotations

from datetime import time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageQuery
from app.modules.notifications import repository
from app.modules.notifications.schemas import (
    ClientNotificationItem,
    ClientNotificationsListResponse,
    ClientPushTokenRegisterRequest,
)

_log = structlog.get_logger("modules.notifications.service")

# ---------------------------------------------------------------------------
# Phase 108 CFG-04 — notification matrix gate constants.
# ---------------------------------------------------------------------------

# Europe/Moscow timezone for quiet-hours computation per project discipline (C-07).
_MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Deterministic singleton PK from migration 0071_seed_settings.
_NOTIFICATION_PREFS_CONFIG_ID = "00000000-0000-0000-0000-000000000005"

# Always-on triggers — these CANNOT be suppressed by the matrix or quiet hours.
# Ground: 7 notification kinds from notifications/models.py:
#   booking_confirmed, booking_cancelled_by_client, booking_cancelled_by_owner,
#   booking_rescheduled, payment_succeeded, autopay_charge_succeeded,
#   autopay_charge_failed.
#
# Always-on = payment/autopay-FAILURE + payment confirmation (T-108-10 mitigation).
# autopay_charge_succeeded is an informational success; it is owner-toggleable.
# autopay_charge_failed is a failure alert; disabling it could hide billing issues.
# payment_succeeded is a transaction confirmation; disabling it removes purchase receipts.
#
# NOTE: Security notification kinds (e.g. "account_locked", "login_suspicious") are
# also conceptually always-on, but NO such kind exists in the current enum.
# When a security kind is added to notifications/models.py, add it here.
_ALWAYS_ON_KINDS: frozenset[str] = frozenset(
    {
        "autopay_charge_failed",  # T-108-10: billing failure — never silence
        "payment_succeeded",  # T-108-10: purchase receipt — never silence
        # Future security kinds (e.g. "login_suspicious") go here.
    }
)


def _channel_enabled(matrix: dict[str, Any], kind: str, channel: str) -> bool:
    """Return True iff the matrix enables this kind × channel combination.

    Matrix shape: {kind: {channel: bool}}.
    Fail-open: absent key → True (emit normally). This mirrors the
    never-raise / fail-open contract for the full gate.
    """
    kind_cfg = matrix.get(kind)
    if not isinstance(kind_cfg, dict):
        return True
    val = kind_cfg.get(channel)
    if val is None:
        return True
    return bool(val)


def _parse_hhmm_time(s: str | None) -> time | None:
    """Parse "HH:MM" string to datetime.time; return None on any error."""
    if not s:
        return None
    try:
        parts = str(s).split(":")
        return time(int(parts[0]), int(parts[1]), 0)
    except (IndexError, ValueError, TypeError):
        return None


def _is_quiet_hours(
    now_msk: Any,
    quiet_start: time | None,
    quiet_end: time | None,
) -> bool:
    """Return True iff the Moscow-TZ current time falls within the quiet window.

    Handles windows that cross midnight (e.g. 22:00–07:00):
      - If start < end: simple range [start, end).
      - If start >= end: window wraps midnight (start..23:59 OR 00:00..end).
    Returns False when either quiet_start or quiet_end is None (no quiet hours).
    """
    if quiet_start is None or quiet_end is None:
        return False
    current: time = now_msk.time().replace(second=0, microsecond=0)
    if quiet_start < quiet_end:
        return bool(quiet_start <= current < quiet_end)
    # Midnight-crossing window.
    return bool(current >= quiet_start or current < quiet_end)


async def create_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,
    source_id: UUID,
    kind: str,
    title: str,
    body: str,
    channel: str = "in_app",
) -> None:
    """Insert one in-app inbox row co-transactionally (caller-owns-txn).

    Idempotent: ON CONFLICT DO NOTHING on the named UNIQUE constraint
    uq_in_app_notifications_client_source_kind — duplicate calls return silently
    without raising or rolling back the session (SAVEPOINT-safe, T-87-03).

    Never raises — callers (event hooks, webhook handlers) depend on fire-and-return
    semantics. The dedup conflict is logged at INFO level for observability.

    Phase 108 CFG-04 pre-emit gate:
      - Always-on kinds (_ALWAYS_ON_KINDS): bypass all gating — always insert.
      - For other kinds: read notification_prefs_config via raw SQL (no settings import).
        * Matrix disabled for kind×channel → suppress (log + return, no insert).
        * Quiet hours active + channel != "in_app" → suppress (no deferred queue per D-108).
        * in_app channel is NEVER quiet-hours-suppressed (it is an inbox, not a push).
      - Config row absent → fail-open (emit normally per T-108-11).
      - Any DB error reading config → fail-open (never raise from this path).

    Sender signature (forward-ready for text channels):
      - For non-in_app channels, append sender_signature to the body when set.
      - in_app bodies are untouched.
    """
    # Phase 108 CFG-04: matrix + quiet-hours + always-on gate.
    # Always-on bypass first — no config read needed for these kinds.
    if kind not in _ALWAYS_ON_KINDS:
        try:
            row = (
                await session.execute(
                    sa.text(  # noqa: TABLE_REF
                        "SELECT matrix, sender_signature, "
                        "       quiet_hours_start, quiet_hours_end "
                        "FROM notification_prefs_config "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": _NOTIFICATION_PREFS_CONFIG_ID},
                )
            ).mappings().one_or_none()

            if row is not None:
                matrix: dict[str, Any] = row["matrix"] or {}

                # Matrix gate: if the matrix explicitly disables this kind×channel → suppress.
                if not _channel_enabled(matrix, kind, channel):
                    _log.info(
                        "notification_suppressed_by_matrix",
                        kind=kind,
                        channel=channel,
                        client_id=str(client_id),
                    )
                    return

                # Quiet-hours gate: suppress non-in_app channels during quiet window.
                # in_app is an inbox and is NEVER quiet-hours-suppressed.
                if channel != "in_app":
                    import datetime as _dt  # local import to keep module-level clean

                    now_msk = _dt.datetime.now(_MOSCOW_TZ)
                    qs = _parse_hhmm_time(row["quiet_hours_start"])
                    qe = _parse_hhmm_time(row["quiet_hours_end"])
                    if _is_quiet_hours(now_msk, qs, qe):
                        _log.info(
                            "notification_suppressed_quiet_hours",
                            kind=kind,
                            channel=channel,
                            client_id=str(client_id),
                        )
                        return

                # Sender signature: append to text-channel bodies (Telegram/email, not in_app).
                # The dispatcher is in_app-only today; this branch is forward-ready for
                # the moment text channels are wired (Phase B+).
                if channel != "in_app":
                    sig = row["sender_signature"]
                    if sig:
                        body = f"{body}\n\n{sig}"

        except Exception:  # noqa: BLE001 — never raise from gate; fail-open (T-108-11)
            _log.warning(
                "notification_gate_config_read_error",
                kind=kind,
                channel=channel,
                client_id=str(client_id),
                exc_info=True,
            )
            # Fall through — emit normally.

    inserted = await repository.insert_notification(
        session,
        client_id=client_id,
        source_type=source_type,
        source_id=source_id,
        kind=kind,
        title=title,
        body=body,
    )
    if not inserted:
        _log.info(
            "notification_dedup_conflict",
            client_id=str(client_id),
            source_type=source_type,
            source_id=str(source_id),
            kind=kind,
            msg="duplicate notification suppressed",
        )


async def list_client_notifications(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> ClientNotificationsListResponse:
    """Return paginated inbox rows for the principal (INBOX-01).

    Ordered newest-first (created_at DESC). Includes server-computed unread_count.
    D-20-IDOR: client_id always from the caller's principal, never from the URL.
    """
    total, unread_count = await repository.count_notifications(session, client_id)
    offset = (query.page - 1) * query.page_size
    rows = await repository.list_notifications(
        session,
        client_id,
        limit=query.page_size,
        offset=offset,
    )
    items = [
        ClientNotificationItem(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            body=row["body"],
            read_at=row["read_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return ClientNotificationsListResponse(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        unread_count=unread_count,
    )


async def mark_notification_read(
    session: AsyncSession,
    *,
    client_id: UUID,
    notification_id: UUID,
) -> ClientNotificationItem:
    """Mark a single notification read; idempotent for own rows, 404 for non-owned (WR-02 fix).

    Idempotency contract: marking an already-read OWN notification is a no-op → 200.
    Only genuinely absent or cross-client IDs return 404 (IDOR-safe, T-87-01).

    Two-phase approach (WR-02):
      1. Attempt UPDATE WHERE id=:id AND client_id=:cid AND read_at IS NULL.
         (Updates only if the row is unread — no-op if already read.)
      2. Fetch the row owned by this client regardless of read state.
         If None → the ID does not exist or belongs to another client → 404.
         Otherwise → return current state (read or just-marked-read).

    Returns the current item state.
    No session.commit() — caller-owns-txn.
    """
    # Attempt to mark as read (no-op if already read — UPDATE matches 0 rows).
    await repository.mark_read(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )

    # Fetch the row owned by this client (IDOR-safe: WHERE client_id = :cid).
    row = await repository.fetch_one_owned(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )
    if row is None:
        # Genuinely not found or belongs to a different client — 404.
        raise NotFoundError("notification_not_found")

    return ClientNotificationItem(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        body=row["body"],
        read_at=row["read_at"],
        created_at=row["created_at"],
    )


async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> None:
    """Mark all unread notifications as read for the calling client (INBOX-01).

    UPDATE WHERE client_id=:cid AND read_at IS NULL — scoped at SQL level (T-87-01).
    No session.commit() — caller-owns-txn.
    """
    await repository.mark_all_read(session, client_id=client_id)


async def register_push_token(
    session: AsyncSession,
    *,
    client_id: UUID,
    payload: ClientPushTokenRegisterRequest,
) -> None:
    """Idempotent upsert of a push token for the calling client (INBOX-02).

    Globally unique by token (CR-03): device tokens are physically unique per device;
    registering an existing-alive token for a new client first soft-deletes any
    other client's alive row for that token, then assigns it to the calling client.
    A same-client re-registration of the same token is a no-op (alive row updated).
    A previously unregistered token is revived (unregistered_at → NULL).
    T-87-04: platform constrained by DB CheckConstraint (web/android/ios).

    No session.commit() — caller-owns-txn.
    """
    await repository.upsert_push_token(
        session,
        client_id=client_id,
        token=payload.token,
        platform=payload.platform,
    )
