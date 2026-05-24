"""Reports router — Phase 54 INFRA-41 scaffold (endpoint bodies land Phase 55).

All reports endpoints are owner-only via
``Depends(require_permission(Action.VIEW, Resource.REPORTS))``
(``(VIEW, REPORTS)`` is in ``OWNER_ONLY`` per D-54-03).

All responses will return ``ResponseEnvelope[...]`` via ``envelope(...)``
(per payments/router.py pattern). Lists use ``PaginatedData[T]``.

Planned Phase 55 surface (bodies not present here):
  - GET /api/v1/reports/revenue      — revenue by period (day/month) from payments ledger.
  - GET /api/v1/reports/clients      — active/expiring/new clients summary.
  - GET /api/v1/reports/visits       — visits by day/hour, peak hours, averages.
  - GET /api/v1/reports/revenue/csv  — CSV export (StreamingResponse).
  - GET /api/v1/reports/clients/csv  — CSV export (StreamingResponse).
  - GET /api/v1/reports/visits/csv   — CSV export (StreamingResponse).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
