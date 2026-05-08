"""Memberships module constants.

`MEMBERSHIP_STATUS_TRANSITIONS` is the declarative state-machine source of truth
(INFRA-16, Phase 24 D-24-03). Keys are source statuses; values are frozensets of
allowed target statuses. Read-only via `MappingProxyType` so module consumers
cannot mutate it at runtime.

Phase 24 ships the constant with `frozen: frozenset()` as a placeholder. Phase 25
will populate the freeze edges (`active → frozen`, `frozen → {active, cancelled}`)
and Phase 26 may extend the renewal-related edges if necessary. Each downstream
phase keeps the unit-test matrix green.

`str` keys (not `MembershipStatus` enum) keep this module importable from
`models.py` and other low-level modules without a circular import; the schema-layer
enum and the constant share string values.
"""

from collections.abc import Mapping
from types import MappingProxyType

MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"expired", "cancelled"}),  # Phase 25 will add "frozen"
        "expired": frozenset(),  # Phase 26 may extend for renewal mechanics
        "cancelled": frozenset(),  # terminal
        "frozen": frozenset(),  # Phase 25 will add {"active", "cancelled"}
    }
)

__all__ = ["MEMBERSHIP_STATUS_TRANSITIONS"]
