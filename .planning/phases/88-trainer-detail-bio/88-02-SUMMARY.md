---
phase: 88-trainer-detail-bio
plan: 02
subsystem: api
tags: [fastapi, client-portal, trainers, rbac, integration-tests, anti-enumeration]

requires:
  - phase: 88-01
    provides: "Trainer ORM columns bio/specialization/photo_url + migrations 0062/0063 applied"

provides:
  - "GET /api/v1/client/trainers/{trainer_id} — client-safe trainer detail endpoint (TRNR-01)"
  - "ClientTrainerDetailResponse schema (id, full_name, photo_url, specialization, bio)"
  - "fetch_trainer_detail raw-SQL repository function with 404-collapse filter"
  - "get_trainer_detail service function with NotFoundError anti-enumeration"
  - "Integration tests: client GET happy/leak/404/anti-oracle + owner PATCH bio/reception 403"

affects: [88-03-pwa, openapi-handoff-89]

tech-stack:
  added: []
  patterns:
    - "CROSS-MODULE READ via raw text() SQL in client_portal/repository.py (no ORM import of Trainer)"
    - "404-collapse: NotFoundError('trainer_not_found') for unknown/inactive/soft-deleted (indistinguishable — anti-enumeration T-88-02)"
    - "CAST(:trainer_id AS UUID) asyncpg bind-param pattern for UUID path params in raw SQL"
    - "client-safe projection via SQL SELECT (id, full_name, photo_url, specialization, bio only)"

key-files:
  created:
    - apps/backend/tests/integration/client_portal/test_client_trainer_detail.py
    - apps/backend/tests/integration/trainers/test_trainers_bio_patch.py
  modified:
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/client_portal/repository.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/client_portal/router.py

key-decisions:
  - "D-88-02-404-COLLAPSE: NotFoundError('trainer_not_found') raises generic code='not_found' with message='trainer_not_found'; tests assert body['message']=='trainer_not_found' + status 404; identical response for unknown/inactive/soft-deleted (T-88-02 anti-enumeration)"
  - "D-88-02-CROSS-MODULE-RAW-SQL: fetch_trainer_detail uses raw text() SQL only; NO ORM import of Trainer from trainers module (D-20-MODULE)"

patterns-established:
  - "Anti-enumeration 404-collapse: combined is_active=true AND deleted_at IS NULL filter in WHERE clause makes unknown/inactive/deleted responses indistinguishable"
  - "Test assertion pattern for generic NotFoundError: assert body['message'] == 'trainer_not_found' (not body['code'])"

requirements-completed: [TRNR-01, TRNR-02]

duration: 12min
completed: 2026-06-06
---

# Phase 88 Plan 02: Client Trainer-Detail Endpoint + Tests Summary

**GET /client/trainers/{id} with client-safe projection (id/fullName/photoUrl/specialization/bio) + 404-collapse anti-enumeration + owner PATCH bio tests**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-06T11:01:00Z
- **Completed:** 2026-06-06T11:12:54Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `ClientTrainerDetailResponse` schema: 5 client-safe fields only (id, full_name, photo_url, specialization, bio); no phone/is_active/audit (T-88-01 mitigated)
- Added `fetch_trainer_detail` to client_portal repository: raw `text()` SQL with `CAST(:trainer_id AS UUID)` + `is_active = true AND deleted_at IS NULL` 404-collapse filter; cross-module raw-SQL rule (D-20-MODULE) preserved
- Added `get_trainer_detail` to client_portal service: 404-collapse via `NotFoundError("trainer_not_found")` — identical response for unknown/inactive/soft-deleted (T-88-02 mitigated)
- Added `client_get_trainer` endpoint: `GET /api/v1/client/trainers/{trainer_id}`, `require_client()` guard, returns `ResponseEnvelope[ClientTrainerDetailResponse]`
- `mypy --strict` clean; `lint-imports` contracts all kept; `ruff check` clean
- 9 integration tests passing across two files:
  - `test_client_trainer_detail.py`: happy path (200 + camelCase fields), leak guard (phone/isActive/audit absent), 404 unknown, 404 inactive, 404 soft-deleted, anti-oracle indistinguishable test
  - `test_trainers_bio_patch.py`: owner PATCH happy (200 + echoed bio/specialization/photoUrl), partial PATCH (bio-only), reception PATCH 403

## Task Commits

1. **Task 1: Client-safe detail projection — schema, repository, service, router** — `09712a57` (feat)
2. **Task 2: Integration tests — client GET (happy/404/leak) + owner PATCH (happy/403)** — `a22d7866` (test)

## Files Created/Modified

- `apps/backend/app/modules/client_portal/schemas.py` — `ClientTrainerDetailResponse` added; `ClientCatalogTrainerResponse` docstring updated (removed "(reserved for future)")
- `apps/backend/app/modules/client_portal/repository.py` — `fetch_trainer_detail` added to `__all__` and implemented
- `apps/backend/app/modules/client_portal/service.py` — `get_trainer_detail` added; `ClientTrainerDetailResponse` imported
- `apps/backend/app/modules/client_portal/router.py` — `client_get_trainer` endpoint added after `client_list_trainers`; `ClientTrainerDetailResponse` imported
- `apps/backend/tests/integration/client_portal/test_client_trainer_detail.py` — new (5 tests)
- `apps/backend/tests/integration/trainers/test_trainers_bio_patch.py` — new (3 tests)

## Decisions Made

- **D-88-02-404-COLLAPSE:** Used generic `NotFoundError("trainer_not_found")` (class code = `"not_found"`, message = `"trainer_not_found"`). Tests assert `body["message"] == "trainer_not_found"` rather than `body["code"]`. This matches the 404-collapse anti-enumeration pattern (same response shape for unknown/inactive/soft-deleted).
- **D-88-02-CROSS-MODULE-RAW-SQL:** `fetch_trainer_detail` uses raw `text()` SQL only — zero ORM imports from `app.modules.trainers`. Follows D-20-MODULE discipline; lint-imports contracts remain unbroken.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed I001 import-sort in router.py and service.py**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** `ClientTrainerDetailResponse` inserted mid-block violated isort ordering
- **Fix:** `uv run ruff check --fix` auto-sorted the import blocks
- **Files modified:** `client_portal/router.py`, `client_portal/service.py`
- **Committed in:** `a22d7866` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed assertion pattern for NotFoundError 404-collapse**
- **Found during:** Task 2 first test run
- **Issue:** Tests asserted `body["code"] == "trainer_not_found"` but generic `NotFoundError` has class code `"not_found"`; the detail is in `body["message"]`
- **Fix:** Changed assertions to `body["message"] == "trainer_not_found"` — matches actual error handler serialization
- **Files modified:** `tests/integration/client_portal/test_client_trainer_detail.py`
- **Committed in:** `a22d7866` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 × Rule 1 - Bug)
**Impact on plan:** Both are correctness fixes; no behavior or scope changes.

## Issues Encountered

None — plan executed without blockers after auto-fixes.

## Known Stubs

None — all fields are DB-backed. The `ClientTrainerDetailResponse` reads live data from the `trainers` table (seeded by migration 0063 in Plan 01). No placeholder or mock data.

## Threat Surface Scan

No new security-relevant surfaces beyond the plan's threat model:
- T-88-01 (projection leak): mitigated — `ClientTrainerDetailResponse` omits phone/is_active/audit; leak-guard test asserts absence
- T-88-02 (enumeration oracle): mitigated — combined `is_active=true AND deleted_at IS NULL` WHERE clause + anti-oracle test proves indistinguishable 404
- T-88-07 (EDIT,TRAINERS RBAC): mitigated — existing owner-only RBAC unchanged; reception-403 test confirms the guard holds for bio fields
- T-88-08 (auth): mitigated — `Depends(require_client())` on `client_get_trainer`

## Self-Check

Files created/committed:
- `apps/backend/app/modules/client_portal/schemas.py` — FOUND (modified)
- `apps/backend/app/modules/client_portal/repository.py` — FOUND (modified)
- `apps/backend/app/modules/client_portal/service.py` — FOUND (modified)
- `apps/backend/app/modules/client_portal/router.py` — FOUND (modified)
- `apps/backend/tests/integration/client_portal/test_client_trainer_detail.py` — FOUND (created)
- `apps/backend/tests/integration/trainers/test_trainers_bio_patch.py` — FOUND (created)

Commits verified:
- `09712a57` — FOUND
- `a22d7866` — FOUND

## Self-Check: PASSED

---
*Phase: 88-trainer-detail-bio*
*Completed: 2026-06-06*
