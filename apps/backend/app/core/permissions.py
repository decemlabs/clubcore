"""RBAC primitives: Role / Action / Resource StrEnums + OWNER_ONLY matrix + can() (RBAC-01).

Source of truth mirrored byte-for-byte from:
  - apps/admin-web/src/shared/session/registry.ts (Resource type + Action type)
  - apps/admin-web/src/shared/session/can.ts (OWNER_ONLY array + can() body)

Phase 6 TEST-06 parity test asserts the backend OWNER_ONLY equals the frontend
one as a set of (action, resource) pairs. Any drift FAILS that test — this
module's StrEnum values and OWNER_ONLY entries are the contract, not a hint.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    RECEPTION = "reception"


class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    REFUND = "refund"
    CANCEL = "cancel"      # Phase 15 INFRA-08 — memberships cancel
    CHECK_IN = "check_in"  # Phase 15 INFRA-08 — visits check-in (value uses underscore)


class Resource(StrEnum):
    DASHBOARD = "dashboard"
    CLIENTS = "clients"
    SCHEDULE = "schedule"
    STAFF = "staff"
    FINANCE = "finance"
    REPORTS = "reports"
    PAYROLL = "payroll"
    COMPENSATION = "compensation"
    TEMPLATES = "templates"
    SETTINGS = "settings"
    OWNER_AREA = "owner-area"  # member-name uses underscore; value contains hyphen
    MEMBERSHIPS = "memberships"            # Phase 15 INFRA-08
    MEMBERSHIP_PLANS = "membership-plans"  # Phase 15 INFRA-08 — kebab on wire (mirrors OWNER_AREA)
    VISITS = "visits"                      # Phase 15 INFRA-08


# Verbatim mirror of apps/admin-web/src/shared/session/can.ts:12-22 (15 entries).
# frozenset for set-membership lookup in can() and parity-set equality in Phase 6.
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset({
    (Action.VIEW, Resource.FINANCE),
    (Action.VIEW, Resource.REPORTS),
    (Action.VIEW, Resource.PAYROLL),
    (Action.VIEW, Resource.COMPENSATION),
    (Action.VIEW, Resource.SETTINGS),
    (Action.VIEW, Resource.OWNER_AREA),
    (Action.EDIT, Resource.TEMPLATES),
    (Action.DELETE, Resource.CLIENTS),
    (Action.REFUND, Resource.FINANCE),
    # Phase 15 INFRA-08 — v1.2 owner-only pairs (memberships + membership-plans).
    # Reception RETAINS (CREATE, MEMBERSHIPS) and (CHECK_IN, VISITS) — NOT listed here.
    (Action.VIEW, Resource.MEMBERSHIP_PLANS),
    (Action.EDIT, Resource.MEMBERSHIP_PLANS),
    (Action.CREATE, Resource.MEMBERSHIP_PLANS),
    (Action.DELETE, Resource.MEMBERSHIP_PLANS),
    (Action.CANCEL, Resource.MEMBERSHIPS),
    (Action.DELETE, Resource.MEMBERSHIPS),
})


def can(role: Role, action: Action, resource: Resource) -> bool:
    """Return True if `role` may perform `action` on `resource`.

    Owner short-circuits to True (D-23). Reception is denied any (action, resource) pair
    in OWNER_ONLY; everything else is allowed. Byte-for-byte semantic mirror of
    apps/admin-web/src/shared/session/can.ts:24-28.
    """
    if role is Role.OWNER:
        return True
    return (action, resource) not in OWNER_ONLY
