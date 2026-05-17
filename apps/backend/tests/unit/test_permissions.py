"""Unit tests for app.core.permissions — Role/Action/Resource/OWNER_ONLY/can() (D-29, RBAC-01)."""

from __future__ import annotations

import pytest

from app.core.permissions import OWNER_ONLY, Action, Resource, Role, can

# ---- Structural guards (Phase 6 parity test will compare to frontend) ----


def test_owner_only_is_frozenset_instance() -> None:
    assert isinstance(OWNER_ONLY, frozenset)


def test_owner_only_has_exactly_twenty_nine_entries() -> None:
    # Mirrors apps/admin-web/src/shared/session/can.ts.
    # Composition: 9 v1.1 + 6 v1.2 INFRA-08 + 11 v1.4 INFRA-19
    #              - 1 v1.4 Phase 34 D-34-09a removal of `(CANCEL, PT_SESSIONS)`
    #              + 4 v1.5 Phase 37 INFRA-27 SCHEDULE_SLOTS write pairs
    #                (CREATE / EDIT / DELETE / CANCEL).
    # Phase 37 INFRA-27 explicitly documents the 25 -> 29 delta (see
    # app/core/permissions.py:108 "Final OWNER_ONLY size: 25 -> 29").
    # Phase 6 TEST-06 / Phase 15 TESTS-08 / Phase 30 INFRA-19 add regex-based parity tests
    # against can.ts (tests/integration/test_rbac_parity.py covers the cross-codebase
    # mirror; this assertion is the structural-only drift tripwire).
    assert len(OWNER_ONLY) == 29


def test_role_value_set() -> None:
    assert {r.value for r in Role} == {"owner", "reception"}


def test_action_value_set() -> None:
    # 5 v1.1 + 2 v1.2 INFRA-08 (cancel, check_in) + 1 v1.5 Phase 37 INFRA-26/D-37-03a (list).
    # Phase 37 added `LIST` as a semantic separation from `VIEW` for listings — see
    # app/core/permissions.py:28.
    assert {a.value for a in Action} == {
        "view",
        "create",
        "edit",
        "delete",
        "refund",
        "cancel",
        "check_in",
        "list",
    }


def test_resource_value_set() -> None:
    # Verbatim from apps/admin-web/src/shared/session/registry.ts
    # (22 values: 11 v1.1 + 3 v1.2 + 1 v1.2 FE-09 + 5 v1.4 INFRA-18 + 2 v1.5 Phase 37 INFRA-26).
    # Note: OWNER_AREA / MEMBERSHIP_PLANS / PT_PACKAGE_PLANS / PT_PACKAGES / PT_SESSIONS /
    # SCHEDULE_SLOTS Python identifiers map to hyphenated string values.
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
        "memberships",
        "membership-plans",
        "visits",
        "profile",  # Phase 22 FE-09 — both-roles own-account surface
        "trainers",  # Phase 30 INFRA-18
        "payments",  # Phase 30 INFRA-18
        "pt-package-plans",  # Phase 30 INFRA-18
        "pt-packages",  # Phase 30 INFRA-18
        "pt-sessions",  # Phase 30 INFRA-18
        "schedule-slots",  # Phase 37 INFRA-26 — v1.5 slot resource (kebab, multi-word)
        "bookings",  # Phase 37 INFRA-26 — v1.5 booking resource (single word)
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
    """Spot-check 29 locked entries (drift tripwire).

    Composition: v1.1 + v1.2 INFRA-08 + v1.4 INFRA-19 - Phase 34 D-34-09a
                 + 4 v1.5 Phase 37 INFRA-27 SCHEDULE_SLOTS write pairs.
    """
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
        # Phase 15 INFRA-08
        (Action.VIEW, Resource.MEMBERSHIP_PLANS),
        (Action.EDIT, Resource.MEMBERSHIP_PLANS),
        (Action.CREATE, Resource.MEMBERSHIP_PLANS),
        (Action.DELETE, Resource.MEMBERSHIP_PLANS),
        (Action.CANCEL, Resource.MEMBERSHIPS),
        (Action.DELETE, Resource.MEMBERSHIPS),
        # Phase 30 INFRA-19 - v1.4 owner-only pairs
        # (Phase 34 D-34-09a removed (CANCEL, PT_SESSIONS))
        (Action.CREATE, Resource.TRAINERS),
        (Action.EDIT, Resource.TRAINERS),
        (Action.DELETE, Resource.TRAINERS),
        (Action.VIEW, Resource.PT_PACKAGE_PLANS),
        (Action.CREATE, Resource.PT_PACKAGE_PLANS),
        (Action.EDIT, Resource.PT_PACKAGE_PLANS),
        (Action.DELETE, Resource.PT_PACKAGE_PLANS),
        (Action.VIEW, Resource.PAYMENTS),
        (Action.CANCEL, Resource.PT_PACKAGES),
        (Action.DELETE, Resource.PT_PACKAGES),
        # Phase 37 INFRA-27 - v1.5 SCHEDULE_SLOTS owner-only writes
        # (reception RETAINS VIEW + LIST on SCHEDULE_SLOTS for slot-picker per SLOT-08;
        #  reception RETAINS all BOOKINGS pairs incl. CANCEL with 24h server-side window
        #  per BOOK-06 / C-05).
        (Action.CREATE, Resource.SCHEDULE_SLOTS),
        (Action.EDIT, Resource.SCHEDULE_SLOTS),
        (Action.DELETE, Resource.SCHEDULE_SLOTS),
        (Action.CANCEL, Resource.SCHEDULE_SLOTS),
    })
    assert expected == OWNER_ONLY


def test_reception_retains_v1_4_rights() -> None:
    """Phase 30 INFRA-19: reception MUST retain these rights (NOT in OWNER_ONLY).

    Source of truth: REQUIREMENTS.md §INFRA-19 verbatim list. INFRA-18 forbids new
    Action values; reception's "(LIST, TRAINERS)" right is expressed semantically via
    (VIEW, TRAINERS) — owner-only is CRUD writes only (CREATE/EDIT/DELETE).
    """
    retained_pairs = [
        (Action.VIEW, Resource.TRAINERS),       # TRN-04 reception picker
        (Action.CREATE, Resource.PAYMENTS),     # PAY-04 sale-flow
        (Action.REFUND, Resource.MEMBERSHIPS),  # B-07 uniform-reception
        (Action.CREATE, Resource.PT_PACKAGES),  # PT-07 reception sells
        (Action.REFUND, Resource.PT_PACKAGES),  # B-07 / REF-02
        (Action.CREATE, Resource.PT_SESSIONS),  # PT-15 reception records
    ]
    for action, resource in retained_pairs:
        assert (action, resource) not in OWNER_ONLY, (
            f"({action}, {resource}) erroneously in OWNER_ONLY"
        )
        assert can(Role.RECEPTION, action, resource) is True, (
            f"reception should be allowed ({action}, {resource})"
        )
