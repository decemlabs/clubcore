"""Reports module literal constants (Phase 55 REV-01..05, D-03).

Period-grain and subject-kind literals mirror D-03 and the payments
CHECK constraint ck_payments_subject_kind.
"""

from __future__ import annotations

GRAIN_DAY = "day"
GRAIN_MONTH = "month"
GRAIN_VALUES: tuple[str, ...] = (GRAIN_DAY, GRAIN_MONTH)

__all__ = (
    "GRAIN_DAY",
    "GRAIN_MONTH",
    "GRAIN_VALUES",
)
