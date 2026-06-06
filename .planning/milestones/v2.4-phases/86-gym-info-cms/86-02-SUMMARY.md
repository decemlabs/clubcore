---
phase: 86-gym-info-cms
plan: "02"
subsystem: backend-gym-http
tags: [gym-info, http-router, rbac-04, require-client, integration-tests, gym-01, gym-02]
dependency_graph:
  requires:
    - GymInfo ORM singleton model (86-01)
    - get_gym_info + update_gym_info service (86-01)
    - GymInfoResponse + GymInfoUpdateRequest schemas (86-01)
    - Resource.GYM + OWNER_ONLY (EDIT, GYM) (86-01)
  provides:
    - GET /api/v1/client/gym (require_client gate, GYM-01)
    - PUT /api/v1/gym (require_permission(EDIT, GYM) + verify_csrf, GYM-02)
    - Integration test suite: client-read, owner write-then-read, reception 403, anon reject, unknown-key 422
  affects:
    - apps/backend/app/api/v1/router.py
tech_stack:
  added: []
  patterns:
    - Two-APIRouter pattern (client_router + owner_router in one module file)
    - RBAC-04 require_permission declared BEFORE verify_csrf in owner mutation handler
    - require_client() gate on client-facing GET endpoint (D-20-IDOR not applicable — singleton)
    - ASGITransport integration test harness with SAVEPOINT rollback
    - OTP auth helper + staff login fixtures (mirrors test_loyalty_read + test_loyalty_grant)
key_files:
  created:
    - apps/backend/app/modules/gym/router.py
    - apps/backend/tests/integration/test_gym_info.py
  modified:
    - apps/backend/app/api/v1/router.py
decisions:
  - "D-86-02-SINGLETON-IDOR: D-20-IDOR not applicable to gym GET endpoint — gym_info is shared facility content (not per-client data); T-86-08 accepted; no client_id scoping needed"
  - "D-86-02-TWO-ROUTERS: Two APIRouter instances (client_router + owner_router) in one file follow Phase 82 loyalty pattern — avoids cross-module edge and keeps auth gates clean (D-20-MODULE)"
metrics:
  duration: ~5 minutes
  completed_date: "2026-06-06"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 86 Plan 02: Gym-Info HTTP Router + Integration Tests Summary

Gym HTTP router exposing GET /api/v1/client/gym (require_client gate) and PUT /api/v1/gym (owner-only, RBAC-04 ordered) plus 5-test integration suite proving client read, owner write-then-read persistence, reception 403, anon rejection, and unknown-key 422.

## What Was Built

**Backend gym HTTP router** (`apps/backend/app/modules/gym/router.py`):
- `client_router = APIRouter(tags=["Client-Portal"])` with `GET /gym` endpoint.
  - Handler `client_get_gym_info`: `require_client()` gate, calls `service.get_gym_info(session)`, returns `envelope(result)`.
  - No try/except — AppError (GymInfoNotFoundError → 404) bubbles to _app_error_handler.
  - Docstring notes gym is a singleton: D-20-IDOR not applicable (no per-client data).
- `owner_router = APIRouter(tags=["Gym"])` with `PUT /` endpoint.
  - Handler `owner_update_gym_info`: RBAC-04 ordering — `require_permission(Action.EDIT, Resource.GYM)` declared BEFORE `verify_csrf`.
  - Reception fails at 403 from require_permission before reaching CSRF check (T-86-04).
  - T-86-07: GymInfoUpdateRequest extra='forbid' → 422 on unknown keys.

**v1 Router registration** (`apps/backend/app/api/v1/router.py`):
- Phase 86 comment block with inline imports for `gym_client_router` and `gym_owner_router`.
- `v1.include_router(gym_client_router, prefix="/client")` → `/api/v1/client/gym`
- `v1.include_router(gym_owner_router, prefix="/gym")` → `/api/v1/gym`

**Integration tests** (`apps/backend/tests/integration/test_gym_info.py`):
- `test_client_get_gym_info_returns_seeded_baseline`: authenticated client GETs /api/v1/client/gym → 200, asserts name "Мой зал · Тверская", address "Тверская, 18, 3 этаж", non-empty hours/amenities/rules arrays.
- `test_owner_put_gym_info_updates_and_persists`: owner PUTs `{"tagline": "Новый слоган теста"}` + CSRF → 200; subsequent client GET returns updated tagline (read-after-write).
- `test_reception_put_gym_info_forbidden`: reception PUT → 403.
- `test_anonymous_get_gym_info_rejected`: no-auth GET → 401/403.
- `test_owner_put_gym_info_rejects_unknown_key`: owner PUT with `{"unknownField": "..."}` → 422.

## Verification Results

- `pytest tests/integration/test_gym_info.py -q`: 5 passed
- `mypy --strict app/modules/gym`: no issues found (6 source files including router.py)
- Route dump: `/api/v1/client/gym` and `/api/v1/gym` confirmed mounted
- grep "require_client": matches in router.py client GET handler
- grep "Action.EDIT, Resource.GYM": matches in router.py owner PUT handler
- require_permission declared textually before verify_csrf (RBAC-04 verified)

## Commits

- `080ba4da`: feat(86-02): gym HTTP router — client GET + owner PUT + v1 registration
- `272f3e8f`: test(86-02): gym-info integration tests — client read, owner write, reception 403, anon reject

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed on first attempt without auto-fix triggers.

## Known Stubs

None — both endpoints are fully wired to the service layer (Plan 01's service/repository). The seeded baseline content is readable from DB. No placeholder patterns present.

## Threat Flags

None — all threat mitigations from the plan's threat register are implemented:
- T-86-04 (reception 403): require_permission(EDIT, GYM) + integration test asserting 403
- T-86-05 (anon rejection): require_client() gate + integration test asserting non-200
- T-86-06 (CSRF): verify_csrf dependency on PUT (after require_permission per RBAC-04)
- T-86-07 (unknown keys): extra='forbid' on GymInfoUpdateRequest → 422 + integration test

## Self-Check: PASSED

- [x] `apps/backend/app/modules/gym/router.py` exists (client_router + owner_router)
- [x] `apps/backend/tests/integration/test_gym_info.py` exists (5 tests)
- [x] `apps/backend/app/api/v1/router.py` modified (gym_client_router + gym_owner_router)
- [x] Routes `/api/v1/client/gym` and `/api/v1/gym` confirmed in route dump
- [x] Commits 080ba4da and 272f3e8f verified in git log
- [x] All 5 integration tests green
- [x] mypy --strict app/modules/gym: no issues
