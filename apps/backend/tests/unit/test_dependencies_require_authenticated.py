"""Unit tests for require_authenticated factory + require_permission audit emit (Phase 6 D-01, D-03, D-23)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from app.core.dependencies import require_authenticated, require_permission
from app.core.exceptions import ForbiddenError
from app.core.permissions import Action, Resource, Role


def _stub_user(role: Role) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role)


def _stub_request(
    path: str = "/_t/delete/clients", host: str | None = "127.0.0.1"
) -> SimpleNamespace:
    client = SimpleNamespace(host=host) if host is not None else None
    url = SimpleNamespace(path=path)
    return SimpleNamespace(url=url, client=client)


def test_require_authenticated_factory_qualname_prefix() -> None:
    """TEST-07 (Plan 06-05) discriminates by __qualname__.startswith('require_authenticated.')."""
    dep = require_authenticated()
    assert dep.__qualname__.startswith("require_authenticated.")


async def test_require_authenticated_returns_user_unchanged() -> None:
    dep = require_authenticated()
    user = _stub_user(Role.RECEPTION)
    result = await dep(user=user)  # type: ignore[arg-type]
    assert result is user


def test_require_permission_factory_qualname_prefix() -> None:
    dep = require_permission(Action.DELETE, Resource.CLIENTS)
    assert dep.__qualname__.startswith("require_permission.")


def test_require_authenticated_qualname_distinct_from_require_permission() -> None:
    """TEST-07 must not false-positive: the two factories' closures have distinct qualnames."""
    auth_dep = require_authenticated()
    perm_dep = require_permission(Action.DELETE, Resource.CLIENTS)
    assert not auth_dep.__qualname__.startswith("require_permission.")
    assert not perm_dep.__qualname__.startswith("require_authenticated.")


async def test_require_permission_emits_rbac_forbidden_for_reception() -> None:
    dep = require_permission(Action.DELETE, Resource.CLIENTS)
    user = _stub_user(Role.RECEPTION)
    request = _stub_request()
    with capture_logs() as captured:
        with pytest.raises(ForbiddenError):
            await dep(request=request, user=user)  # type: ignore[arg-type]
    events = [c for c in captured if c.get("event") == "rbac_forbidden"]
    assert len(events) == 1
    ev = events[0]
    assert ev["user_id"] == str(user.id)
    assert ev["role"] == "reception"
    assert ev["action"] == "delete"
    assert ev["resource"] == "clients"
    assert ev["path"] == "/_t/delete/clients"
    assert ev["ip"] == "127.0.0.1"


async def test_require_permission_no_emit_for_owner() -> None:
    dep = require_permission(Action.DELETE, Resource.CLIENTS)
    user = _stub_user(Role.OWNER)
    request = _stub_request()
    with capture_logs() as captured:
        result = await dep(request=request, user=user)  # type: ignore[arg-type]
    assert result is user
    assert not [c for c in captured if c.get("event") == "rbac_forbidden"]


async def test_require_permission_emits_with_ip_none_when_client_missing() -> None:
    dep = require_permission(Action.DELETE, Resource.CLIENTS)
    user = _stub_user(Role.RECEPTION)
    request = _stub_request(host=None)
    with capture_logs() as captured:
        with pytest.raises(ForbiddenError):
            await dep(request=request, user=user)  # type: ignore[arg-type]
    ev = [c for c in captured if c.get("event") == "rbac_forbidden"][0]
    assert ev["ip"] is None
