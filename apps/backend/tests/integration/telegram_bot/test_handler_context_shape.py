"""Regression guard for HandlerContext shape (Phase 20 AUTH-TG-07; Phase 40 BOT-04; Phase 93).

Cheap two-liner: if a future contributor accidentally drops a field from the
NamedTuple, this test fails fast. Phase 40 extended the tuple with
`bookings_service` + `schedule_service` (D-40-04 / D-40-06) appended at the
END to preserve positional construction compatibility. Phase 93 appends
`messaging_service` (D-06 relaxation; reply routing).
"""

from __future__ import annotations

from app.integrations.telegram.handlers import HandlerContext


def test_handler_context_has_all_phase_20_fields() -> None:
    # Phase 20 additions
    assert "visits_service" in HandlerContext._fields
    assert "redis" in HandlerContext._fields
    # Phase 7 fields stay (no accidental drops)
    for f in ("session_factory", "telegram_service", "sender"):
        assert f in HandlerContext._fields


def test_handler_context_has_all_phase_40_fields() -> None:
    # Phase 40 additions (D-40-04 + D-40-06): bookings + schedule modules.
    assert "bookings_service" in HandlerContext._fields
    assert "schedule_service" in HandlerContext._fields


def test_handler_context_has_phase_93_messaging_service_field() -> None:
    # Phase 93: messaging_service appended at END (D-06 relaxation; reply routing).
    assert "messaging_service" in HandlerContext._fields


def test_handler_context_field_order_is_stable() -> None:
    # NamedTuple field order is part of the stable contract — Phase 20 added
    # visits_service + redis at the END of the tuple to preserve positional
    # construction compatibility (the worker uses kwargs, but tests in
    # 20-PATTERNS.md depend on this order for type checkers).
    # Phase 40 BOT-04: bookings_service + schedule_service appended at END
    # (positional construction in workers/telegram_bot.py:main() depends on
    # this order; field-order locked by D-40-04 / D-40-06).
    # Phase 93: messaging_service appended at END (D-06 relaxation; field-order
    # contract preserved — never insert in the middle).
    assert HandlerContext._fields == (
        "session_factory",
        "telegram_service",
        "sender",
        "visits_service",
        "redis",
        "bookings_service",
        "schedule_service",
        "messaging_service",
    )


def test_handler_context_field_count_is_eight() -> None:
    # Phase 93: tuple now has 8 fields (7 from Phase 40 + messaging_service).
    assert len(HandlerContext._fields) == 8


def test_handler_context_last_field_is_messaging_service() -> None:
    # Phase 93: messaging_service is APPENDED at the END (contract).
    assert HandlerContext._fields[-1] == "messaging_service"


def test_handler_context_double_construction_keeps_all_eight_fields() -> None:
    """REG-29-03 extended: HandlerContext exposes 8 fields; positional construction maps 1:1.

    Structural grep-style assertion — does NOT exercise main() (which would
    require live event loop + Redis). Proves all 8 kwargs appear at the
    construction site so the NamedTuple cannot be partially wired.
    Phase 93 adds messaging_service=messaging_service (D-06 relaxation).
    """
    import inspect

    from app.workers import telegram_bot as worker_main_module

    src = inspect.getsource(worker_main_module)
    # Worker constructs HandlerContext with these 8 kwargs
    # (D-40-08 + D-40-04 + D-40-06 + Phase 93 D-06).
    assert "bookings_service=bookings_service" in src
    assert "schedule_service=schedule_service" in src
    assert "messaging_service=messaging_service" in src
    assert "session_factory=" in src
    assert "telegram_service=" in src
    assert "sender=" in src
    assert "visits_service=" in src
    assert "redis=" in src
