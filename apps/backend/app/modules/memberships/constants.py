"""Memberships module constants.

`MEMBERSHIP_STATUS_TRANSITIONS` is the declarative state-machine source of truth
(INFRA-16, Phase 24 D-24-03). Keys are source statuses; values are frozensets of
allowed target statuses. Read-only via `MappingProxyType` so module consumers
cannot mutate it at runtime.

Phase 25 populated the freeze edges (active → frozen, frozen → {active, cancelled}).
Phase 26 leaves MEMBERSHIP_STATUS_TRANSITIONS UNCHANGED — renewal creates a new
row (INSERT), it does NOT transition the source. Phase 26 ALSO appends the
RENEWAL_STRATEGY_* literal constants used by service.renew_membership in the
audit payload `start_date_strategy` field (D-26-13).

`str` keys (not `MembershipStatus` enum) keep this module importable from
`models.py` and other low-level modules without a circular import; the schema-layer
enum and the constant share string values.
"""

from collections.abc import Mapping
from types import MappingProxyType

MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"expired", "cancelled", "frozen"}),
        "expired": frozenset(),  # terminal — Phase 26 may extend for renewal mechanics
        "cancelled": frozenset(),  # terminal
        "frozen": frozenset({"active", "cancelled"}),
    }
)

# Phase 26 D-26-13 — start_date strategy literals (audit payload values).
# Captured as module-level constants so tests can assert exact literals; service
# emits these via the audit payload key `start_date_strategy` (D-26-15).
RENEWAL_STRATEGY_FROM_SOURCE_END_DATE = "from_source_end_date"
RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE = "from_today_expired_source"

# Phase 27 D-27-25 — expiring-soon notification kind literals.
# Long-form per REQUIREMENTS NTF-01 verbatim; matches CHECK constraint values
# in migration 0010_notifications.py and audit event suffix
# `expiring_notification_sent_<kind_short>` minus prefix. Used by:
# - repository.find_expiring_candidates kind discriminator (D-27-18)
# - service._send_expiring_notifications row insert + audit emit (D-27-12)
# - migration 0010 CHECK constraint inline literal
EXPIRING_KIND_7D = "expiring_7d"
EXPIRING_KIND_3D = "expiring_3d"
EXPIRING_KIND_1D = "expiring_1d"
EXPIRING_KINDS: tuple[str, ...] = (EXPIRING_KIND_7D, EXPIRING_KIND_3D, EXPIRING_KIND_1D)

__all__ = [
    "EXPIRING_KINDS",
    "EXPIRING_KIND_1D",
    "EXPIRING_KIND_3D",
    "EXPIRING_KIND_7D",
    "MEMBERSHIP_STATUS_TRANSITIONS",
    "RENEWAL_STRATEGY_FROM_SOURCE_END_DATE",
    "RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE",
]
