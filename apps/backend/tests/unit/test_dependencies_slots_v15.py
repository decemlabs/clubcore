"""Unit tests — Phase 37 INFRA-32 / D-37-06 Protocol slot register/get round-trip.

Covers the 3 new v1.5 composition-root slots in `app.core.dependencies`:

  - SlotByIdResolver         → resolve_slot_by_id
  - BookingSlotRestorer      → restore_booking_slot
  - BookingCompleter         → complete_booking_by_pt_session

Each slot has two tests:

  (a) Round-trip — register a stub, call the consumer accessor, assert the stub
      was invoked exactly once with the passed args and its return value is
      propagated verbatim.
  (b) Silent-None — when no resolver is registered, the consumer accessor
      returns ``None`` without raising (D-37-06 — silent-None mirrors v1.4
      ActivePtPackageResolver at dependencies.py:117).

Module-private slot variables are global state, so each test uses
``monkeypatch.setattr`` to set the slot to ``None`` BEFORE the register call
(silent-None case) or BEFORE the test runs (round-trip case — the register
call inside the test installs the stub, then we restore).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest

import app.core.dependencies as deps
from app.core.dependencies import (
    complete_booking_by_pt_session,
    register_booking_completer,
    register_booking_slot_restorer,
    register_slot_by_id_resolver,
    resolve_slot_by_id,
    restore_booking_slot,
)

# ---------------------------------------------------------------------------
# SlotByIdResolver
# ---------------------------------------------------------------------------


async def test_slot_by_id_resolver_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """register_slot_by_id_resolver(stub) → resolve_slot_by_id invokes stub once."""
    monkeypatch.setattr(deps, "_slot_by_id_resolver", None)
    called_with: list[tuple[Any, Any]] = []
    sentinel = object()

    async def stub(session: Any, slot_id: Any) -> Any:
        called_with.append((session, slot_id))
        return sentinel

    register_slot_by_id_resolver(stub)  # type: ignore[arg-type]
    sid = uuid4()
    result = await resolve_slot_by_id(session=None, slot_id=sid)  # type: ignore[arg-type]
    assert result is sentinel
    assert called_with == [(None, sid)]


async def test_slot_by_id_resolver_silent_none_when_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-37-06: unregistered slot returns None without raising (silent-None)."""
    monkeypatch.setattr(deps, "_slot_by_id_resolver", None)
    result = await resolve_slot_by_id(session=None, slot_id=uuid4())  # type: ignore[arg-type]
    assert result is None


# ---------------------------------------------------------------------------
# BookingSlotRestorer
# ---------------------------------------------------------------------------


async def test_booking_slot_restorer_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """register_booking_slot_restorer(stub) → restore_booking_slot invokes stub once."""
    monkeypatch.setattr(deps, "_booking_slot_restorer", None)
    called_with: list[tuple[Any, Any]] = []

    async def stub(session: Any, slot_id: Any) -> None:
        called_with.append((session, slot_id))
        return None

    register_booking_slot_restorer(stub)  # type: ignore[arg-type]
    sid = uuid4()
    result = await restore_booking_slot(session=None, slot_id=sid)  # type: ignore[arg-type]
    assert result is None
    assert called_with == [(None, sid)]


async def test_booking_slot_restorer_silent_none_when_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-37-06: unregistered slot returns None without raising (silent-None)."""
    monkeypatch.setattr(deps, "_booking_slot_restorer", None)
    result = await restore_booking_slot(session=None, slot_id=uuid4())  # type: ignore[arg-type]
    assert result is None


# ---------------------------------------------------------------------------
# BookingCompleter
# ---------------------------------------------------------------------------


async def test_booking_completer_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """register_booking_completer(stub) → complete_booking_by_pt_session invokes stub once."""
    monkeypatch.setattr(deps, "_booking_completer", None)
    called_with: list[tuple[Any, Any]] = []

    async def stub(session: Any, booking_id: Any) -> None:
        called_with.append((session, booking_id))
        return None

    register_booking_completer(stub)  # type: ignore[arg-type]
    bid = uuid4()
    result = await complete_booking_by_pt_session(session=None, booking_id=bid)  # type: ignore[arg-type]
    assert result is None
    assert called_with == [(None, bid)]


async def test_booking_completer_silent_none_when_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-37-06: unregistered slot returns None without raising (silent-None)."""
    monkeypatch.setattr(deps, "_booking_completer", None)
    result = await complete_booking_by_pt_session(  # type: ignore[arg-type]
        session=None, booking_id=uuid4()
    )
    assert result is None


# ---------------------------------------------------------------------------
# Importability of the stub service functions (Phase 38 will replace them).
# ---------------------------------------------------------------------------


async def test_schedule_service_stubs_importable_and_return_none() -> None:
    """schedule.service stubs (resolve_slot_by_id + restore_slot_to_active) return None."""
    from app.modules.schedule import service as schedule_service

    sid = uuid4()
    assert await schedule_service.resolve_slot_by_id(session=None, slot_id=sid) is None  # type: ignore[arg-type]
    assert await schedule_service.restore_slot_to_active(session=None, slot_id=sid) is None  # type: ignore[arg-type]


async def test_bookings_service_stub_importable_and_returns_none() -> None:
    """bookings.service.complete_booking is an async None-returning stub."""
    from app.modules.bookings import service as bookings_service

    bid = uuid4()
    assert await bookings_service.complete_booking(session=None, booking_id=bid) is None  # type: ignore[arg-type]


def test_resolver_callable_aliases_are_exported() -> None:
    """Type aliases used by the composition root must be importable from app.core.dependencies."""
    from app.core.dependencies import (
        BookingCompleterCallable,
        BookingSlotRestorerCallable,
        SlotById,
        SlotByIdResolver,
    )

    # Smoke: aliases evaluate to Callable types; SlotById is a Protocol class.
    _: Callable[..., Awaitable[Any]]
    _ = SlotByIdResolver  # type: ignore[assignment]
    _ = BookingSlotRestorerCallable  # type: ignore[assignment]
    _ = BookingCompleterCallable  # type: ignore[assignment]
    assert SlotById is not None
