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

from typing import Final

# === Phase 39 NOTIFY-01 -- locked Russian DM copy. Owner sign-off pending in plan 39-01. ===
# RUF001/E501/RUF003 per-line: Cyrillic letters + locked single-line format are intentional
# (Russian-only product per PROJECT.md i18n locked decision; reviewers diff exact text).
BOOKING_CONFIRMED_DM: Final[str] = "Здравствуйте, {client_name}! Ваша запись подтверждена: тренер {trainer_name}, {slot_start_msk} (МСК). Ждём вас в зале!"  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
BOOKING_CANCELLED_BY_CLIENT_DM: Final[str] = "Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена по вашей просьбе. Будем рады видеть вас снова — обратитесь к администратору, чтобы записаться заново."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
BOOKING_CANCELLED_BY_OWNER_DM: Final[str] = "Здравствуйте, {client_name}! К сожалению, ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена. Приносим извинения за неудобства — администратор поможет подобрать другое время."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
BOOKING_REMINDER_24H_DM: Final[str] = "Здравствуйте, {client_name}! Напоминаем о вашей записи: завтра, {slot_start_msk} (МСК), вас ждёт тренер {trainer_name}. Пожалуйста, не опаздывайте."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md
_BOT_BOOK_DENIED_DM: Final[str] = "Сейчас бронирование недоступно. Пожалуйста, свяжитесь с администратором — он подскажет ближайшее свободное время."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md  # NOTIFY-02 anti-oracle: NO placeholders, NO failure-cause disclosure (C-12)


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
