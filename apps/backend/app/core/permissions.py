"""RBAC primitives: Role / Action / Resource StrEnums + OWNER_ONLY matrix + can() (RBAC-01).

Source of truth mirrored byte-for-byte from:
  - apps/admin-app/src/shared/session/registry.ts (Resource type + Action type)
  - apps/admin-app/src/shared/session/can.ts (OWNER_ONLY array + can() body)

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
    CANCEL = "cancel"  # Phase 15 INFRA-08 — memberships cancel
    CHECK_IN = "check_in"  # Phase 15 INFRA-08 — visits check-in (value uses underscore)
    LIST = "list"  # Phase 37 INFRA-26 / D-37-03a — semantic separation from VIEW for listings
    # NEW Phase 41 INFRA-37 / D-41-22 — USERS mutations (deactivate/reactivate/invitation-revoke).
    UPDATE = "update"


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
    MEMBERSHIPS = "memberships"  # Phase 15 INFRA-08
    MEMBERSHIP_PLANS = "membership-plans"  # Phase 15 INFRA-08 — kebab on wire (mirrors OWNER_AREA)
    VISITS = "visits"  # Phase 15 INFRA-08
    PROFILE = "profile"  # Phase 22 FE-09 — both roles, not OWNER_ONLY
    TRAINERS = "trainers"  # Phase 30 INFRA-18 — v1.4 trainers module
    PAYMENTS = "payments"  # Phase 30 INFRA-18 — v1.4 payments ledger
    PT_PACKAGE_PLANS = "pt-package-plans"  # Phase 30 INFRA-18 — kebab (mirrors MEMBERSHIP_PLANS)
    PT_PACKAGES = "pt-packages"  # Phase 30 INFRA-18 — kebab (multi-word)
    PT_SESSIONS = "pt-sessions"  # Phase 30 INFRA-18 — kebab (multi-word)
    SCHEDULE_SLOTS = "schedule-slots"  # Phase 37 INFRA-26 — v1.5 slot resource (kebab, multi-word)
    BOOKINGS = "bookings"  # Phase 37 INFRA-26 — v1.5 booking resource (single word)
    USERS = "users"  # NEW Phase 41 INFRA-37 / D-41-21 — multi-user admin module (Phase 43)
    # NEW Phase 54 INFRA-42 — kebab on wire (multi-word, mirrors OWNER_AREA / SCHEDULE_SLOTS)
    AUDIT_LOG = "audit-log"
    # Phase 86 GYM-02 — gym-info owner-only write; value mirrors registry.ts Resource union
    GYM = "gym"
    # Phase 113 — promo-codes CRUD: reception retains (LIST, PROMO_CODES). Count grows 42 -> 45.
    PROMO_CODES = "promo-codes"  # kebab (mirrors MEMBERSHIP_PLANS, SCHEDULE_SLOTS)


# Verbatim mirror of apps/admin-app/src/shared/session/can.ts (45 entries after Phase 113).
# frozenset for set-membership lookup in can() and parity-set equality in Phase 6.
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset(
    {
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
        # Phase 30 INFRA-19 — v1.4 owner-only pairs (trainers / payments / pt-package-plans /
        # pt-packages / pt-sessions). Reception RETAINS: (VIEW, TRAINERS) for ?active=true
        # picker (TRN-04), (CREATE, PAYMENTS) for sale flow (PAY-04), (REFUND, MEMBERSHIPS)
        # uniform-reception (B-07), (CREATE, PT_PACKAGES) + (REFUND, PT_PACKAGES) (B-07/PT-07),
        # (CREATE, PT_SESSIONS) (PT-15).
        # Phase 34 D-34-09a removed `(CANCEL, PT_SESSIONS)` — B-12 grants reception a
        # 24h cancel-window; the application layer raises `cancel_window_expired` 403
        # from `pt_sessions.service.cancel_pt_session`, not RBAC. Final OWNER_ONLY size
        # = 25 (was 26 after Phase 30 INFRA-19).
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
        # Phase 37 INFRA-27 note: Action.LIST has no OWNER_ONLY entries in v1.5 —
        # reception sees all listings. Future phases may add (LIST, X) pairs.
        # Phase 37 INFRA-27 — v1.5 owner-only pairs (schedule-slots).
        # Reception RETAINS (NOT listed here): (VIEW, SCHEDULE_SLOTS), (LIST, SCHEDULE_SLOTS)
        # for slot picker (SLOT-08), (CREATE, BOOKINGS) for booking flow (BOOK-02),
        # (CANCEL, BOOKINGS) with 24h cancel-window enforced server-side via
        # `cancel_window_expired` 403 (BOOK-06 / C-05 — mirrors Phase 34 D-34-09a
        # PT-session pattern), (VIEW, BOOKINGS), (LIST, BOOKINGS) for booking lists.
        # Slot publication is owner-only in v1.5 (no trainer self-service per anti-feature list).
        # OVERRIDE D-37-03: CONTEXT.md reads "25 → 35" — that was a miscount that
        # treated reception-retained pairs as restricted. The 6 reception-retained
        # pairs above describe what reception SEES, not what is denied. Correct
        # shipped delta is 25 → 29 (+4 SCHEDULE_SLOTS write pairs only).
        # Final OWNER_ONLY size: 25 -> 29.
        (Action.CREATE, Resource.SCHEDULE_SLOTS),
        (Action.EDIT, Resource.SCHEDULE_SLOTS),
        (Action.DELETE, Resource.SCHEDULE_SLOTS),
        (Action.CANCEL, Resource.SCHEDULE_SLOTS),
        # v1.6 (Phase 41 INFRA-37 / D-41-21 — Multi-user admin; reception has zero USERS perms).
        # D-41-22: reuses Action.{CREATE, UPDATE, DELETE, LIST}; deactivate/reactivate/
        # invitation-revoke all map to Action.UPDATE; soft-delete maps to Action.DELETE.
        (Action.CREATE, Resource.USERS),
        (Action.UPDATE, Resource.USERS),
        (Action.DELETE, Resource.USERS),
        (Action.LIST, Resource.USERS),
        # v1.8 (Phase 54 INFRA-42 / D-54-04) — audit-log read API is owner-only.
        # Reception has ZERO audit perms (403). Reuses Action.VIEW (filterable read)
        # + Action.LIST (paginated listing); no new Action value.
        (Action.VIEW, Resource.AUDIT_LOG),
        (Action.LIST, Resource.AUDIT_LOG),
        # v1.9 Phase 58 INFRA-15 / D-58-15 — Payroll + compensation write/run/refund
        # pairs. Reception has zero payroll visibility beyond existing VIEW entries.
        # Existing (VIEW, PAYROLL) and (VIEW, COMPENSATION) at lines 66-67 remain
        # unchanged. D-58-15 Claude's Discretion: (EDIT, COMPENSATION) collapsed into
        # (CREATE, COMPENSATION) — INSERT-only versioned model makes "edit" semantically
        # identical to "create new version". Final count grows from 35 to 40.
        (Action.CREATE, Resource.COMPENSATION),
        (Action.CREATE, Resource.PAYROLL),
        (Action.EDIT, Resource.PAYROLL),
        (Action.REFUND, Resource.PAYROLL),
        (Action.LIST, Resource.PAYROLL),
        # Phase 86 GYM-02 — gym-info owner-only write (T-86-02 mitigation).
        # Reception is denied EDIT on gym-info content; 403 enforced at router.
        (Action.EDIT, Resource.GYM),
        # Phase 108 CFG-02/03/04 — settings write; owner-only, additive.
        # Resource.SETTINGS already exists in the enum (value "settings").
        # (VIEW, SETTINGS) is already in OWNER_ONLY above — only the EDIT pair is new.
        (Action.EDIT, Resource.SETTINGS),
        # Phase 113 — promo-codes CRUD: reception retains (LIST, PROMO_CODES). Count 42 -> 45.
        (Action.CREATE, Resource.PROMO_CODES),
        (Action.EDIT, Resource.PROMO_CODES),
        (Action.DELETE, Resource.PROMO_CODES),  # deactivate maps to DELETE
    }
)


def can(role: Role, action: Action, resource: Resource) -> bool:
    """Return True if `role` may perform `action` on `resource`.

    Owner short-circuits to True (D-23). Reception is denied any (action, resource) pair
    in OWNER_ONLY; everything else is allowed. Byte-for-byte semantic mirror of
    apps/admin-app/src/shared/session/can.ts:24-28.
    """
    if role is Role.OWNER:
        return True
    return (action, resource) not in OWNER_ONLY
