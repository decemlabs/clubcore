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

# ---------------------------------------------------------------------------
# Advanced analytics constants (Phase 115 ANL-02..04)
# ---------------------------------------------------------------------------

# Live gym-load (ANL-03, ANL-04): rolling-window approximation of "currently present".
# Visit model has only checked_in_at (no checkout column); window ≈ average session length.
LOAD_NOW_WINDOW_MINUTES: int = 120  # rolling window; ~2 h average session

# Visit-anomaly detection (ANL-02)
ANOMALY_WINDOW_DAYS: int = 14  # trailing rolling mean window (std computation)
ANOMALY_SIGMA: float = 2.0  # sigma threshold for spike/drop flag
ANOMALY_LOOKBACK_DAYS: int = 90  # default chart span when no from_date/to_date given

# At-risk member detection (ANL-02): active membership + last visit > threshold
AT_RISK_THRESHOLD_DAYS: int = 14  # days without a visit → at-risk
AT_RISK_MAX_ITEMS: int = 50  # LIMIT cap on at-risk list (DoS guard, T-115-05)

# Cohort retention analysis (ANL-02)
COHORT_DEFAULT_MONTHS: int = 6  # default cohort span when ?cohortMonths omitted
COHORT_MAX_MONTHS: int = 12  # upper bound validated in service (DoS guard, T-115-05)


__all__ = (
    "ANOMALY_LOOKBACK_DAYS",
    "ANOMALY_SIGMA",
    "ANOMALY_WINDOW_DAYS",
    "AT_RISK_MAX_ITEMS",
    "AT_RISK_THRESHOLD_DAYS",
    "COHORT_DEFAULT_MONTHS",
    "COHORT_MAX_MONTHS",
    "CSV_AUDIT_LOG_HEADERS",
    "CSV_CLIENTS_HEADERS",
    "CSV_REVENUE_HEADERS",
    "CSV_TRAINER_USAGE_HEADERS",
    "CSV_VISITS_HEADERS",
    "GRAIN_DAY",
    "GRAIN_MONTH",
    "GRAIN_VALUES",
    "LOAD_NOW_WINDOW_MINUTES",
    "TRAINER_REPORT_REVENUE_NOTE",
)
