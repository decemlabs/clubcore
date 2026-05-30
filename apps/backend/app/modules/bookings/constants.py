"""Bookings module constants (Phase 37 INFRA-30 / D-37-04 / C-04).

BOOKING_STATUS_TRANSITIONS is the declarative state-machine source of truth
for booking lifecycle. Keys are source statuses; values are frozensets of
allowed target statuses. Read-only via MappingProxyType so module consumers
cannot mutate it at runtime.

Transition matrix (C-04 / INFRA-30):
  - confirmed → {cancelled, no_show, completed}  (exactly 3 legal next states)
  - cancelled → ∅                                 (terminal — no reverse)
  - no_show   → ∅                                 (terminal — Q3: no reverse in v1.5)
  - completed → ∅                                 (terminal — set by pt_session_recorded)

`str` keys (not the schema-layer BookingStatus enum) keep this module
importable from models.py and service.py without a circular import; the
schema-layer enum and the constant share string values.

The `_assert_can_transition` guard helper lives in `service.py` (Phase 38)
next to the service code that consumes it — mirrors v1.3 memberships and
v1.4 pt_packages precedent (see apps/backend/app/modules/pt_packages/service.py:184-197).
"""

from collections.abc import Mapping
from types import MappingProxyType

BOOKING_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "confirmed": frozenset({"cancelled", "no_show", "completed"}),
        "cancelled": frozenset(),  # terminal
        "no_show": frozenset(),  # terminal (Q3 SUMMARY: no reverse in v1.5)
        "completed": frozenset(),  # terminal (set by pt_session_recorded with booking_id)
    }
)

# Phase 38 plan 38-03 / C-05 / BOOK-06 / D-38-16 — reception may only cancel a
# booking when `slot.start_time - datetime.now(UTC) >= CANCEL_WINDOW_HOURS_RECEPTION`;
# owner anytime. Mirrors `pt_sessions.constants.CANCEL_WINDOW_HOURS_RECEPTION`
# shape (B-12). The window is measured against `slot.start_time` (NOT
# `created_at` — D-38-16 explicit), so a booking made far in advance
# automatically locks 24h before the slot fires.
CANCEL_WINDOW_HOURS_RECEPTION = 24

# Phase 70 D-70-05 / D-38-16 — client cancel window, measured against
# slot.start_time (NOT created_at). Independently tunable from the reception
# window; starts identical (24h) for predictable behavior. A booking made
# far in advance automatically locks 24h before the slot fires.
CANCEL_WINDOW_HOURS_CLIENT = 24

__all__ = [
    "BOOKING_STATUS_TRANSITIONS",
    "CANCEL_WINDOW_HOURS_RECEPTION",
    "CANCEL_WINDOW_HOURS_CLIENT",
]
