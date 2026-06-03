"""Locked Russian DM templates for Phase 39 booking notifications (NOTIFY-01 / NOTIFY-02).

4 booking-event templates + 1 anti-oracle constant. Single template per kind (D-39-04 --
NO A/B variants; the booking surface is one-shot per booking, not recurring).

Owner sign-off (D-27 lineage / Phase 39 plan 39-01 close) recorded in
``.planning/phases/39-notifications-cron/39-01-SUMMARY.md`` before plan close.
Modifying these strings post-merge requires a NEW owner sign-off entry.

Module location (D-39-02): lives in ``app/modules/bookings/`` (not in
``app/integrations/telegram/copy.py``) because booking DM copy is owned by the
bookings domain. The Phase 18 D-09 single-owning-module-per-worker exception
permits both bookings/workers AND the Phase 40 Telegram bot worker to import
this module directly -- ``_BOT_BOOK_DENIED_DM`` lives here despite being
consumed by the Phase 40 bot (single source of truth for booking-domain DM copy).

Placeholder substitution (D-39-04): renderers use ``str.format(**kwargs)`` so any
unknown placeholder key raises ``KeyError`` loud at test time -- f-strings would
silently shadow the bug. The caller (in ``bookings/service.py``, plans 39-02 / 39-04)
pre-formats ``slot_start_msk`` via
``slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")`` per D-39-11.
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID, uuid4

from app.core.dependencies import get_email_dispatcher

# === Phase 39 NOTIFY-01 -- locked Russian DM copy. Owner sign-off pending in plan 39-01. ===
# RUF001/E501/RUF003 per-line: Cyrillic letters + locked single-line format are intentional
# (Russian-only product per PROJECT.md i18n locked decision; reviewers diff exact text).
BOOKING_CONFIRMED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Ваша запись подтверждена: тренер {trainer_name}, {slot_start_msk} (МСК). Ждём вас в зале!"  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
)
BOOKING_CANCELLED_BY_CLIENT_DM: Final[str] = (
    "Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена по вашей просьбе. Будем рады видеть вас снова — обратитесь к администратору, чтобы записаться заново."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
)
BOOKING_CANCELLED_BY_OWNER_DM: Final[str] = (
    "Здравствуйте, {client_name}! К сожалению, ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена. Приносим извинения за неудобства — администратор поможет подобрать другое время."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
)
BOOKING_REMINDER_24H_DM: Final[str] = (
    "Здравствуйте, {client_name}! Напоминаем о вашей записи: завтра, {slot_start_msk} (МСК), вас ждёт тренер {trainer_name}. Пожалуйста, не опаздывайте."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
)
_BOT_BOOK_DENIED_DM: Final[str] = (
    "Сейчас бронирование недоступно. Пожалуйста, свяжитесь с администратором — он подскажет ближайшее свободное время."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md  # NOTIFY-02 anti-oracle: NO placeholders, NO failure-cause disclosure (C-12)
)
# Phase 80 RESCH-02 — reschedule notification DM (pending owner sign-off before merge).
BOOKING_RESCHEDULED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} перенесена. Новое время: {new_slot_start_msk} (МСК). Ждём вас в зале!"  # noqa: E501, RUF001  # OWNER-COPY-LOCK — requires owner sign-off before merge
)


def render_booking_confirmed_dm(
    *,
    client_name: str,
    trainer_name: str,
    slot_start_msk: str,
) -> str:
    """Render the locked confirmation DM via ``str.format`` (unknown keys raise KeyError)."""
    return BOOKING_CONFIRMED_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot_start_msk,
    )


def render_booking_cancelled_by_client_dm(
    *,
    client_name: str,
    trainer_name: str,
    slot_start_msk: str,
) -> str:
    """Render the locked client-initiated cancellation DM via ``str.format`` (unknown keys raise KeyError)."""  # noqa: E501
    return BOOKING_CANCELLED_BY_CLIENT_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot_start_msk,
    )


def render_booking_cancelled_by_owner_dm(
    *,
    client_name: str,
    trainer_name: str,
    slot_start_msk: str,
) -> str:
    """Render the locked owner-initiated cancellation DM via ``str.format`` (unknown keys raise KeyError)."""  # noqa: E501
    return BOOKING_CANCELLED_BY_OWNER_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot_start_msk,
    )


def render_booking_reminder_24h_dm(
    *,
    client_name: str,
    trainer_name: str,
    slot_start_msk: str,
) -> str:
    """Render the locked 24h reminder DM via ``str.format`` (unknown keys raise KeyError)."""
    return BOOKING_REMINDER_24H_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot_start_msk,
    )


def render_booking_rescheduled_dm(
    *,
    client_name: str,
    trainer_name: str,
    new_slot_start_msk: str,
) -> str:
    """Render the locked reschedule DM via ``str.format`` (unknown keys raise KeyError).

    ``new_slot_start_msk`` must be pre-formatted by the caller as
    ``new_slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")``
    per D-39-11 placeholder convention.
    """
    return BOOKING_RESCHEDULED_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        new_slot_start_msk=new_slot_start_msk,
    )


# ---------------------------------------------------------------------------
# Phase 45 NOTIFY-09/10 — email-fallback fanout (D-45-05 / D-45-06 / D-45-22).
# ---------------------------------------------------------------------------


async def enqueue_booking_email_fallback(
    *,
    kind: Literal["confirmed", "cancelled_by_client", "cancelled_by_owner", "reminder_24h"],
    client_email: str,
    trainer_name: str,
    slot_start_msk: str,
    slot_date: str | None = None,
) -> UUID:
    """Render + enqueue a booking lifecycle/reminder email via the EmailDispatcher slot.

    Phase 45 D-45-22 — 4 explicit literal ``template_id`` branches satisfy the
    AST gate at ``tests/unit/test_locked_email_templates_ast.py:42-46``
    (NO f-strings, NO variable interpolation in the ``template_id`` position).

    Branches map ``kind`` → ``template_id``:
      - ``confirmed`` → ``EMAIL_BOOKING_CONFIRMED`` (D-45-05 FSM hook).
      - ``cancelled_by_client`` → ``EMAIL_BOOKING_CANCELLED_BY_CLIENT`` (D-45-05).
      - ``cancelled_by_owner`` → ``EMAIL_BOOKING_CANCELLED_BY_OWNER`` (D-45-05).
      - ``reminder_24h`` → ``EMAIL_BOOKING_REMINDER_24H`` (D-45-06 cron only).

    ``slot_date`` is REQUIRED for ``reminder_24h`` (the email body renders the
    Russian-formatted slot date in the subject-line preview); the 3 lifecycle
    kinds do not consume it (their subject says only "Запись подтверждена" /
    similar — the slot start carries enough context).

    Returns:
        UUID — freshly-minted ``audit_correlation_id``. Caller
        (``bookings/service.py``) stores it on the structlog binding for the
        email-side ``booking_notifications`` INSERT so the forensic chain
        reassembles via ``email_send_log.audit_correlation_id`` (Phase 42 D-42-18).

    Raises:
        ValueError: on an unknown ``kind`` (defensive — the helper's caller
            in ``bookings/service.py`` only ever passes one of the 4 literal
            strings from the Literal type above).
        ValueError: when ``kind == "reminder_24h"`` and ``slot_date`` is None
            (defensive — the cron caller pre-formats this before invoking).
    """
    audit_correlation_id = uuid4()
    dispatcher = get_email_dispatcher()

    if kind == "confirmed":
        await dispatcher(
            template_id="EMAIL_BOOKING_CONFIRMED",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            trainer_name=trainer_name,
            slot_start_msk=slot_start_msk,
        )
    elif kind == "cancelled_by_client":
        await dispatcher(
            template_id="EMAIL_BOOKING_CANCELLED_BY_CLIENT",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            trainer_name=trainer_name,
            slot_start_msk=slot_start_msk,
        )
    elif kind == "cancelled_by_owner":
        await dispatcher(
            template_id="EMAIL_BOOKING_CANCELLED_BY_OWNER",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            trainer_name=trainer_name,
            slot_start_msk=slot_start_msk,
        )
    elif kind == "reminder_24h":
        if slot_date is None:
            raise ValueError("reminder_24h requires slot_date")
        await dispatcher(
            template_id="EMAIL_BOOKING_REMINDER_24H",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            trainer_name=trainer_name,
            slot_start_msk=slot_start_msk,
            slot_date=slot_date,
        )
    else:  # pragma: no cover — defensive; the Literal type narrows callers.
        raise ValueError(f"unknown booking email kind: {kind}")

    return audit_correlation_id
