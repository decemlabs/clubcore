---
phase: 60-trainer-usage-report
plan: "01"
subsystem: backend/reports
tags: [pydantic, schemas, constants, rpt-01, rpt-02, rpt-04]
dependency_graph:
  requires: []
  provides:
    - TrainerUsageReportQuery
    - TrainerUsageRow
    - TrainerUsageReportResponse
    - CSV_TRAINER_USAGE_HEADERS
    - TRAINER_REPORT_REVENUE_NOTE
  affects:
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/constants.py
tech_stack:
  added: []
  patterns:
    - Pydantic v2 BackendSchemaBase query DTO (alias_generator=to_camel)
    - Pydantic v2 ResponseData row + envelope DTOs
    - Module-level constants with __all__ export discipline
key_files:
  modified:
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/constants.py
decisions:
  - "camelCase English CSV headers (matches v1.8 CSV_REVENUE_HEADERS convention per D-60-11)"
  - "TRAINER_REPORT_REVENUE_NOTE as single source of truth for envelope default (D-60-07)"
  - "utilization_pct: float | None and avg_revenue_per_session: int | None (nullable per D-60-06 / D-60-03)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-25"
  tasks_completed: 2
  files_modified: 2
---

# Phase 60 Plan 01: Trainer-Usage Report Wire Contracts Summary

Defines Pydantic v2 DTOs and module constants as stable typed contracts for all downstream Phase 60 plans (repository, service, router, tests).

## What Was Built

### constants.py — New Symbols

**CSV_TRAINER_USAGE_HEADERS** (10-element `tuple[str, ...]`):
```python
CSV_TRAINER_USAGE_HEADERS: tuple[str, ...] = (
    "trainerNameSnapshot",       # index 0
    "sessionCount",              # index 1
    "cancelledSessionCount",     # index 2
    "totalHours",                # index 3
    "uniqueClientCount",         # index 4
    "utilizationPct",            # index 5
    "revenueRubles",             # index 6
    "avgRevenuePerSessionRubles", # index 7
    "totalAccruedRubles",        # index 8
    "totalPaidRubles",           # index 9
)
```

Column order mirrors the JSON row field order for diffability (D-60-11). All headers are camelCase ASCII per the v1.8 convention verified at `CSV_REVENUE_HEADERS:30-37` (`"period"`, `"netRubles"`, ...).

**TRAINER_REPORT_REVENUE_NOTE** (module-scope `str`):
```
"Revenue is attributed to pt_packages.trainer_id (assigned at sale). "
"Packages currently have a single assigned trainer, so per-trainer revenue "
"is unambiguous; if a package is reassigned during its lifecycle, revenue "
"accrues to the trainer assigned at sale time. Summing revenue across "
"trainers may not equal the global PT-package revenue total."
```

This constant is the single source of truth for the RPT-02 double-count disclosure (D-60-07). It documents that `pt_packages.trainer_id` (assigned-at-sale, D-58-21) is the attribution key.

### schemas.py — New Classes

**TrainerUsageReportQuery(BackendSchemaBase)**:
- `from_date: date` — required, wire: `fromDate`
- `to_date: date` — required, wire: `toDate`
- No defaults (period is always explicit per RPT-01 / CONTEXT L59-62)
- `BackendSchemaBase` provides `extra='forbid'` + `alias_generator=to_camel`

**TrainerUsageRow(ResponseData)** — 11 fields in locked order:
| Field | Type | Wire Key | Notes |
|-------|------|----------|-------|
| `trainer_id` | `UUID` | `trainerId` | |
| `trainer_name_snapshot` | `str` | `trainerNameSnapshot` | from trainers.full_name, no is_active filter (PITFALL 11) |
| `session_count` | `int` | `sessionCount` | non-cancelled pt_sessions |
| `cancelled_session_count` | `int` | `cancelledSessionCount` | |
| `total_hours` | `float` | `totalHours` | 0.0 when no booking-linked sessions (D-60-04) |
| `unique_client_count` | `int` | `uniqueClientCount` | COUNT DISTINCT pt_packages.client_id |
| `utilization_pct` | `float \| None` | `utilizationPct` | None = 0 active\|booked slots (D-60-06) |
| `revenue_kopecks` | `int` | `revenueKopecks` | attributed via pt_packages.trainer_id (D-58-21) |
| `avg_revenue_per_session` | `int \| None` | `avgRevenuePerSession` | None when session_count == 0 |
| `total_accrued_kopecks` | `int` | `totalAccruedKopecks` | signed, nets clawbacks (D-58-03) |
| `total_paid_kopecks` | `int` | `totalPaidKopecks` | |

**TrainerUsageReportResponse(ResponseData)**:
- `trainers: list[TrainerUsageRow]`
- `from_date: date`
- `to_date: date`
- `revenue_attribution_note: str = TRAINER_REPORT_REVENUE_NOTE` — default sourced from constants module

## Confirmation: v1.8 CSV Convention is camelCase English

`CSV_REVENUE_HEADERS` at `constants.py:30-37` = `("period", "netRubles", "cashRubles", "onlineRubles", "membershipRubles", "ptPackageRubles")` — all camelCase ASCII. This IS the v1.8 convention that D-60-11 mandates matching. The Russian example in CONTEXT.md L401-403 was illustrative only; the codebase is authoritative.

## Verification Results

- `ruff check` on both files: 0 errors
- `mypy --strict` on both files: 0 errors
- Python smoke test (query parsing, None→null serialization, envelope default): PASSED
- Import guard (`! grep -rE "from app.modules.(pt_sessions|trainers|...)"` both files): PASSED
- `CSV_TRAINER_USAGE_HEADERS` len == 10: PASSED
- `__all__` exports both new symbols: PASSED

## Commits

- `4100f99f` — feat(60-01): add CSV_TRAINER_USAGE_HEADERS + TRAINER_REPORT_REVENUE_NOTE to constants.py
- `c349daa9` — feat(60-01): add TrainerUsageReportQuery + TrainerUsageRow + TrainerUsageReportResponse to schemas.py

## Deviations from Plan

None — plan executed exactly as written. The acceptance criterion `grep -c 'utilization_pct: float | None'` expecting 1 occurrence was satisfied after removing the type-annotation text from the class docstring (docstring used plain English description instead of Python type syntax to avoid false duplication).

## Known Stubs

None. Both files are complete contracts with no placeholder values.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan only adds Pydantic DTOs and string constants — no trust boundary changes.

## Self-Check: PASSED

Files confirmed to exist:
- `apps/backend/app/modules/reports/constants.py` — FOUND (modified)
- `apps/backend/app/modules/reports/schemas.py` — FOUND (modified)

Commits confirmed:
- `4100f99f` — FOUND
- `c349daa9` — FOUND
