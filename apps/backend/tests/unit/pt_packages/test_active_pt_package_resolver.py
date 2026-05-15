"""Unit tests for ActivePtPackage Protocol slot machinery (Phase 33 D-33-12).

5 tests cover the silent-None semantics + slot wiring:
  1. get_active_pt_package returns None when slot unregistered (silent-None;
     mirrors _active_membership_resolver line 117 — NOT defensive raise).
  2. register_active_pt_package_resolver sets the slot module-global.
  3. Double-register replaces the slot (last-write-wins; mirrors WR-05).
  4. get_active_pt_package delegates verbatim to the registered resolver.
  5. app.main.create_app() wires the live ``pt_packages.service
     .resolve_active_pt_package`` delegate (identity check).
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies as deps


@pytest.fixture(autouse=True)
def restore_pt_package_resolver_slot() -> Iterator[None]:
    """Snapshot + restore _active_pt_package_resolver so tests don't leak across each other."""
    original = deps._active_pt_package_resolver
    try:
        yield
    finally:
        deps._active_pt_package_resolver = original


async def test_get_active_pt_package_silent_none_when_unregistered() -> None:
    """D-33-12: silent-None when slot unset — NO RuntimeError (distinct from payment_recorder)."""
    deps._active_pt_package_resolver = None
    session = AsyncMock(spec=AsyncSession)
    result = await deps.get_active_pt_package(session, uuid4())
    assert result is None


def test_register_active_pt_package_resolver_sets_slot() -> None:
    """register_* writes the resolver function into the module-level slot."""
    deps._active_pt_package_resolver = None
    stub = AsyncMock()
    deps.register_active_pt_package_resolver(stub)
    assert deps._active_pt_package_resolver is stub


def test_register_active_pt_package_resolver_replaces_existing() -> None:
    """Double-register: last write wins (idempotent slot, mirrors WR-05)."""
    deps._active_pt_package_resolver = None
    stub_a = AsyncMock()
    stub_b = AsyncMock()
    deps.register_active_pt_package_resolver(stub_a)
    deps.register_active_pt_package_resolver(stub_b)
    assert deps._active_pt_package_resolver is stub_b


async def test_get_active_pt_package_delegates_to_registered_resolver() -> None:
    """get_active_pt_package(session, client_id) forwards to the registered resolver."""
    deps._active_pt_package_resolver = None
    sentinel: object = object()
    stub = AsyncMock(return_value=sentinel)
    deps.register_active_pt_package_resolver(stub)

    session = AsyncMock(spec=AsyncSession)
    client_id: UUID = uuid4()
    result = await deps.get_active_pt_package(session, client_id)
    assert result is sentinel
    stub.assert_awaited_once_with(session, client_id)


async def test_main_create_app_wires_live_resolver() -> None:
    """D-33-12: create_app() registers pt_packages_service.resolve_active_pt_package.

    Identity check — the LIVE function from the module IS the slot value
    after create_app() runs (no indirection / wrapping).
    """
    deps._active_pt_package_resolver = None

    # Import the live wiring at call time so the snapshot+restore fixture
    # is the only thing that can flip the slot.
    from app.main import create_app
    from app.modules.pt_packages import service as pt_packages_service

    create_app()
    assert deps._active_pt_package_resolver is pt_packages_service.resolve_active_pt_package
