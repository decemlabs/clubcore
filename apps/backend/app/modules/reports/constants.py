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

# ---------------------------------------------------------------------------
# Trainer-usage report constants (Phase 60 RPT-01..04)
# ---------------------------------------------------------------------------

CSV_TRAINER_USAGE_HEADERS: tuple[str, ...] = (
    "trainerNameSnapshot",
    "sessionCount",
    "cancelledSessionCount",
    "totalHours",
    "uniqueClientCount",
    "utilizationPct",
    "revenueRubles",
    "avgRevenuePerSessionRubles",
    "totalAccruedRubles",
    "totalPaidRubles",
)

TRAINER_REPORT_REVENUE_NOTE: str = (
    "Revenue is attributed to pt_packages.trainer_id (assigned at sale). "
    "Packages currently have a single assigned trainer, so per-trainer revenue "
    "is unambiguous; if a package is reassigned during its lifecycle, revenue "
    "accrues to the trainer assigned at sale time. Summing revenue across "
    "trainers may not equal the global PT-package revenue total."
)

__all__ = (
    "CSV_AUDIT_LOG_HEADERS",
    "CSV_CLIENTS_HEADERS",
    "CSV_REVENUE_HEADERS",
    "CSV_TRAINER_USAGE_HEADERS",
    "CSV_VISITS_HEADERS",
    "GRAIN_DAY",
    "GRAIN_MONTH",
    "GRAIN_VALUES",
    "TRAINER_REPORT_REVENUE_NOTE",
)
