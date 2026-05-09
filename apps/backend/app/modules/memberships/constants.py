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

__all__ = [
    "MEMBERSHIP_STATUS_TRANSITIONS",
    "RENEWAL_STRATEGY_FROM_SOURCE_END_DATE",
    "RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE",
]
