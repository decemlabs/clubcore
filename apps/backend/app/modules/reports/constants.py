"""Reports module literal constants (Phase 55 REV-01..05, D-03; Phase 56 EXP-01..04, D-15).

Period-grain and subject-kind literals mirror D-03 and the payments
CHECK constraint ck_payments_subject_kind.

CSV column header constants (Phase 56) follow UPPER_SNAKE_CASE and camelCase wire
labels (alias_generator=to_camel discipline, D-15).
"""

from __future__ import annotations

GRAIN_DAY = "day"
GRAIN_MONTH = "month"
GRAIN_VALUES: tuple[str, ...] = (GRAIN_DAY, GRAIN_MONTH)

# ---------------------------------------------------------------------------
# CSV column header constants (Phase 56 EXP-01..04, D-15)
# ---------------------------------------------------------------------------

CSV_AUDIT_LOG_HEADERS: tuple[str, ...] = (
    "createdAt",
    "actorUserId",
    "actorEmailSnapshot",
    "action",
    "resourceType",
    "resourceId",
    "payload",
)

CSV_REVENUE_HEADERS: tuple[str, ...] = (
    "period",
    "netRubles",
    "cashRubles",
    "onlineRubles",
    "membershipRubles",
    "ptPackageRubles",
)

CSV_CLIENTS_HEADERS: tuple[str, ...] = (
    "fromDate",
    "toDate",
    "within",
    "activeMemberships",
    "expiringWithinN",
    "newClients",
)

CSV_VISITS_HEADERS: tuple[str, ...] = ("date", "count")

__all__ = (
    "CSV_AUDIT_LOG_HEADERS",
    "CSV_CLIENTS_HEADERS",
    "CSV_REVENUE_HEADERS",
    "CSV_VISITS_HEADERS",
    "GRAIN_DAY",
    "GRAIN_MONTH",
    "GRAIN_VALUES",
)
