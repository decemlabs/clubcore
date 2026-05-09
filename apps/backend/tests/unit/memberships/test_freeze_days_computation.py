"""Pure-function tests for Phase 25 D-25-08 step 5 half-day rounds-up rule.

Asserts byte-stable parity with the SQL aggregate
`CEIL((COALESCE(ended_at, now()) - started_at) seconds / 86400)` at the
boundary cases (zero, fractional, exact, just-over-exact).

Anti-abuse minimum: `max(1, math.ceil(delta_seconds / 86400))` — instant
freeze-then-unfreeze still costs 1 day. Client-favouring rounding for
partial days. DB-free pure-function tests; integration coverage of the
SQL aggregate lives in test_freeze_helpers.py.
"""

from __future__ import annotations

import math

import pytest


def _days_added(delta_seconds: float) -> int:
    """Reference implementation of the Phase 25 D-25-08 step 5 rule.

    Mirrors `service.unfreeze_membership`:
        days_added = max(1, math.ceil(delta_seconds / 86400))
    """
    return max(1, math.ceil(delta_seconds / 86400))


@pytest.mark.parametrize(
    ("delta_seconds", "expected"),
    [
        # Instant unfreeze (network round-trip): delta=0 → enforce min 1.
        (0, 1),
        # 1 second still rounds up to 1 day.
        (1, 1),
        # Exactly 1 day = 86400 sec → 1.
        (86400, 1),
        # Just over 1 day → 2.
        (86401, 2),
        # Half day past 1 day → 2.
        (86400 + 86400 // 2, 2),
        # Exactly 1.5 days (float) → 2.
        (86400 * 1.5, 2),
        # Exactly 5 days → 5.
        (86400 * 5, 5),
        # Just over 5 days → 6.
        (86400 * 5 + 1, 6),
        # 14 days exact (typical limit boundary) → 14.
        (86400 * 14, 14),
    ],
)
def test_freeze_days_rounding_rule(delta_seconds: float, expected: int) -> None:
    """D-25-08 step 5: half-day rounds up; minimum 1 day."""
    assert _days_added(delta_seconds) == expected


def test_freeze_days_zero_seconds_clamped_to_one() -> None:
    """Edge: instant unfreeze (delta_seconds=0) → ceil(0/86400)=0 → max(1, 0)=1.

    Anti-abuse: prevents `freeze → unfreeze` loops from gaining unbounded
    extension days at zero cost (mirrors Phase 19 visits 1/day rule
    philosophy).
    """
    assert math.ceil(0 / 86400) == 0
    assert _days_added(0) == 1


def test_freeze_days_fractional_rounds_up() -> None:
    """1.5 days → ceil(1.5) == 2; matches Python math.ceil semantics."""
    assert math.ceil(1.5) == 2
    assert _days_added(86400 * 1.5) == 2


def test_freeze_days_multi_period_sum_byte_stable() -> None:
    """Sum of three periods (1d, 1.5d, 0.5d) → 1 + 2 + 1 = 4 (each ceil'd)."""
    p1 = _days_added(86400)
    p2 = _days_added(86400 * 1.5)
    p3 = _days_added(86400 * 0.5)
    assert (p1, p2, p3) == (1, 2, 1)
    assert p1 + p2 + p3 == 4
