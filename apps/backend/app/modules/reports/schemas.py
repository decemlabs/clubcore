"""Reports module DTOs (Phase 54 INFRA-41 scaffold — bodies land Phase 55).

Schema conventions (mirrors app/modules/payments/schemas.py):
  - Query DTOs extend ``PageQuery`` (pagination + filters).
  - Response DTOs extend ``BackendSchemaBase`` (inherits ``extra='forbid'``).
  - Wire form is camelCase; Python is snake_case (e.g. ``period_grain`` ↔ ``periodGrain``).
  - Money stays integer kopecks in all API responses (formatting deferred to frontend).
  - All date bucketing is deterministic in Europe/Moscow (mirror ``visits.gym_date STORED``
    discipline).

Phase 55 will add:
  - ``RevenueReportQuery`` / ``RevenueReportResponse`` — revenue by period.
  - ``ClientsReportQuery`` / ``ClientsReportResponse`` — active/expiring/new.
  - ``VisitsReportQuery`` / ``VisitsReportResponse`` — visits by day/hour.
"""

from __future__ import annotations
