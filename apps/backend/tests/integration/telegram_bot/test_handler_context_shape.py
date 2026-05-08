"""Regression guard for HandlerContext shape (Phase 20 AUTH-TG-07).

Cheap two-liner: if a future contributor accidentally drops `visits_service`
or `redis` from the NamedTuple, this test fails fast.
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


def test_handler_context_field_order_is_stable() -> None:
    # NamedTuple field order is part of the stable contract — Phase 20 added
    # visits_service + redis at the END of the tuple to preserve positional
    # construction compatibility (the worker uses kwargs, but tests in
    # 20-PATTERNS.md depend on this order for type checkers).
    assert HandlerContext._fields == (
        "session_factory",
        "telegram_service",
        "sender",
        "visits_service",
        "redis",
    )
