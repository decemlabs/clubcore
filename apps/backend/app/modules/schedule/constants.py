"""Schedule module constants (Phase 37 INFRA-31 / D-37-04 / C-04).

SLOT_STATUS_TRANSITIONS is the declarative state-machine source of truth
for trainer-availability-slot lifecycle. Keys are source statuses; values
are frozensets of allowed target statuses. Read-only via MappingProxyType
so module consumers cannot mutate it at runtime.

Transition matrix (INFRA-31):
  - active    → {booked, cancelled}   (publish→booked on booking; →cancelled owner cancel)
  - booked    → {active, cancelled}   (active = booking-cancel restore per ARCHITECTURE.md)
  - cancelled → ∅                     (terminal)

`str` keys (not the schema-layer SlotStatus enum) keep this module
importable from models.py and service.py without a circular import; the
schema-layer enum and the constant share string values.

The `_assert_can_transition` guard helper lives in `service.py` (Phase 38)
next to the service code that consumes it — mirrors v1.3 memberships and
v1.4 pt_packages precedent (see apps/backend/app/modules/pt_packages/service.py:184-197).
"""

from collections.abc import Mapping
from types import MappingProxyType

SLOT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"booked", "cancelled"}),
        "booked": frozenset({"active", "cancelled"}),
        "cancelled": frozenset(),  # terminal
    }
)

# Phase 38 SLOT-04 / C-15 / D-38-07 — minimum gap (in minutes) between any two
# non-cancelled slots for the same trainer. publish_slot uses this constant in
# the buffer-check tstzrange query; reject 409 slot_too_close on violation.
# Hardcoded 10 for v1.5; configurable buffer (per-trainer / per-zal) deferred
# to v1.8 reports milestone alongside .ics export.
SLOT_BUFFER_MINUTES = 10

__all__ = [
    "SLOT_BUFFER_MINUTES",
    "SLOT_STATUS_TRANSITIONS",
]
