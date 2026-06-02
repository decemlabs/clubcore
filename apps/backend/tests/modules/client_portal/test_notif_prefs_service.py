"""Phase 75 Plan 01 Task 3 — notif_prefs service-layer behavior tests.

Behaviors locked (NOTIF-01 / D-04 / D-05 / D-06):
  - get_client_me returns _NOTIF_DEFAULTS when notif_prefs column is NULL.
  - update_client_profile with notif_prefs writes all four keys (full replace).
  - GET /client/me after PATCH reflects the persisted prefs.
  - update_client_profile with notif_prefs=None leaves the column untouched.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientProfileUpdateRequest,
    NotifPrefs,
)
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── get_client_me — notif_prefs defaults when column is NULL ─────────────────


async def test_get_client_me_returns_notif_defaults_when_null(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-06: get_client_me applies _NOTIF_DEFAULTS when notif_prefs column is NULL."""
    client = await make_client()
    result = await service.get_client_me(db_session, client.id)
    assert result.notif_prefs is not None
    # Default values per _NOTIF_DEFAULTS
    assert result.notif_prefs.promo is True
    assert result.notif_prefs.schedule is True
    assert result.notif_prefs.trainer is True
    assert result.notif_prefs.sound is False


# ── update_client_profile — notif_prefs persistence ──────────────────────────


async def test_update_client_profile_persists_notif_prefs(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """NOTIF-01: update_client_profile writes all four notif_prefs keys."""
    client = await make_client()
    prefs = NotifPrefs(promo=False, schedule=True, trainer=False, sound=True)
    result = await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(notif_prefs=prefs),
    )
    assert result.notif_prefs is not None
    assert result.notif_prefs.promo is False
    assert result.notif_prefs.schedule is True
    assert result.notif_prefs.trainer is False
    assert result.notif_prefs.sound is True


async def test_update_client_profile_notif_prefs_reflected_on_get(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """get_client_me returns persisted prefs after update_client_profile writes them."""
    client = await make_client()
    prefs = NotifPrefs(promo=True, schedule=False, trainer=True, sound=True)
    await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(notif_prefs=prefs),
    )
    # Fetch again to confirm persistence
    result = await service.get_client_me(db_session, client.id)
    assert result.notif_prefs.promo is True
    assert result.notif_prefs.schedule is False
    assert result.notif_prefs.trainer is True
    assert result.notif_prefs.sound is True


async def test_update_client_profile_notif_prefs_none_leaves_untouched(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-05: update_client_profile with notif_prefs=None leaves the column untouched."""
    client = await make_client()
    # First, set prefs to a non-default value
    prefs = NotifPrefs(promo=False, schedule=False, trainer=False, sound=True)
    await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(notif_prefs=prefs),
    )
    # Now update with notif_prefs=None — should not overwrite
    await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(first_name="Тест"),
    )
    result = await service.get_client_me(db_session, client.id)
    # Prefs must still reflect the first write, not defaults
    assert result.notif_prefs.promo is False
    assert result.notif_prefs.schedule is False
    assert result.notif_prefs.trainer is False
    assert result.notif_prefs.sound is True


async def test_update_client_profile_notif_prefs_full_replace(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-05: full replace — second write completely overwrites first write."""
    client = await make_client()
    # Write 1
    await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(
            notif_prefs=NotifPrefs(promo=True, schedule=True, trainer=True, sound=True)
        ),
    )
    # Write 2 — completely different
    result = await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=ClientProfileUpdateRequest(
            notif_prefs=NotifPrefs(promo=False, schedule=False, trainer=False, sound=False)
        ),
    )
    assert result.notif_prefs.promo is False
    assert result.notif_prefs.schedule is False
    assert result.notif_prefs.trainer is False
    assert result.notif_prefs.sound is False
