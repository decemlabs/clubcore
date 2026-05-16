"""PT-sessions HTTP router (Phase 34 D-34-08).

Two `APIRouter` instances are exported here:

- `pt_sessions_router` — mounted at `/api/v1/pt-sessions` by the v1
  aggregator (`app.api.v1.router`). Hosts POST `/pt-sessions` (record),
  POST `/pt-sessions/{id}/cancel`, GET `/pt-sessions/{id}` (filled in by
  34-02 / 34-03).
- `package_scoped_router` — mounted at `/api/v1/pt-packages` so the
  single nested endpoint `GET /pt-packages/{id}/sessions` (PT-19) lives
  alongside its sibling pt-sessions handlers. Subject-side ownership
  principle (D-33-18): implementation lives with the entity that owns the
  data (pt_sessions), even though the URL path is rooted at the parent
  resource.

Plan 34-01 lands the two empty APIRouter instances + module docstring so
the v1 aggregator can import + mount them. Handler attach-points are
filled by Plans 34-02 (record) and 34-03 (cancel/get/list).
"""

from fastapi import APIRouter

pt_sessions_router = APIRouter()
package_scoped_router = APIRouter()
