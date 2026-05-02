"""Unit tests for app.core.permissions — Role/Action/Resource/OWNER_ONLY/can() (D-29, RBAC-01)."""

from __future__ import annotations

import pytest

from app.core.permissions import OWNER_ONLY, Action, Resource, Role, can

# ---- Structural guards (Phase 6 parity test will compare to frontend) ----


def test_owner_only_is_frozenset_instance() -> None:
    assert isinstance(OWNER_ONLY, frozenset)


def test_owner_only_has_exactly_nine_entries() -> None:
    # Mirrors apps/admin-web/src/shared/session/can.ts:12-22 (9 entries).
    # Phase 6 TEST-06 will add a regex-based parity test against can.ts.
    assert len(OWNER_ONLY) == 9


def test_role_value_set() -> None:
    assert {r.value for r in Role} == {"owner", "reception"}


def test_action_value_set() -> None:
    assert {a.value for a in Action} == {"view", "create", "edit", "delete", "refund"}


def test_resource_value_set() -> None:
    # Verbatim from apps/admin-web/src/shared/session/registry.ts (11 values).
    # Note: OWNER_AREA Python identifier maps to "owner-area" string value (hyphen).
    assert {r.value for r in Resource} == {
        "dashboard",
        "clients",
        "schedule",
        "staff",
        "finance",
        "reports",
        "payroll",
        "compensation",
        "templates",
        "settings",
        "owner-area",
    }


def test_owner_area_value_uses_hyphen_not_underscore() -> None:
    """Frontend uses 'owner-area' (kebab); Python identifier uses underscore (D-22)."""
    assert Resource.OWNER_AREA.value == "owner-area"


# ---- can() body (D-23) ----


_ALL_PAIRS: list[tuple[Action, Resource]] = [
    (a, r) for a in Action for r in Resource
]
_ALL_PAIRS.sort(key=lambda p: (p[0].value, p[1].value))

_OWNER_ONLY_SORTED: list[tuple[Action, Resource]] = sorted(
    OWNER_ONLY, key=lambda p: (p[0].value, p[1].value)
)


@pytest.mark.parametrize("action,resource", _ALL_PAIRS)
def test_owner_can_do_anything(action: Action, resource: Resource) -> None:
    # Owner short-circuits to True for every (action, resource) pair (D-23).
    assert can(Role.OWNER, action, resource) is True


@pytest.mark.parametrize("action,resource", _OWNER_ONLY_SORTED)
def test_reception_denied_for_every_owner_only_pair(action: Action, resource: Resource) -> None:
    assert can(Role.RECEPTION, action, resource) is False


def test_reception_allowed_for_non_owner_only_pair() -> None:
    # (view, clients) is NOT in OWNER_ONLY → reception allowed.
    assert (Action.VIEW, Resource.CLIENTS) not in OWNER_ONLY
    assert can(Role.RECEPTION, Action.VIEW, Resource.CLIENTS) is True


def test_specific_owner_only_membership() -> None:
    """Spot-check the 9 known-locked entries — drift tripwire."""
    expected = frozenset({
        (Action.VIEW, Resource.FINANCE),
        (Action.VIEW, Resource.REPORTS),
        (Action.VIEW, Resource.PAYROLL),
        (Action.VIEW, Resource.COMPENSATION),
        (Action.VIEW, Resource.SETTINGS),
        (Action.VIEW, Resource.OWNER_AREA),
        (Action.EDIT, Resource.TEMPLATES),
        (Action.DELETE, Resource.CLIENTS),
        (Action.REFUND, Resource.FINANCE),
    })
    assert expected == OWNER_ONLY
