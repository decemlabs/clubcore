---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
plan: "01"
subsystem: backend
tags: [weekly-activity, client-portal, idor, tz-safety, zero-fill]
dependency_graph:
  requires: []
  provides: [GET /client/activity/weekly, ClientWeeklyActivityItem schema]
  affects: [client_portal/router.py, client_portal/service.py, client_portal/repository.py, client_portal/schemas.py]
tech_stack:
  added: []
  patterns: [raw-SQL cross-module read (D-54-08), app-side zero-fill, ZoneInfo Moscow anchor, IDOR via require_client()]
key_files:
  created:
    - apps/backend/app/modules/client_portal/schemas.py (ClientWeeklyActivityItem added)
    - apps/backend/tests/unit/client_portal/__init__.py
    - apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py
    - apps/backend/tests/integration/client_portal/test_weekly_activity.py
  modified:
    - apps/backend/app/modules/client_portal/repository.py (fetch_weekly_activity added)
    - apps/backend/app/modules/client_portal/service.py (get_client_weekly_activity added)
    - apps/backend/app/modules/client_portal/router.py (GET /activity/weekly registered)
decisions:
  - "Pass Python date objects (not str) to asyncpg text() params — asyncpg requires native types"
  - "Visit seeding in integration tests uses datetime objects for checked_in_at, not ISO strings"
  - "redis_clean (flush_redis autouse fixture) added to integration test module to clear rate-limit counters between tests"
  - "Pre-existing ruff errors in promo_codes/ and test_client_promo_validate.py are out-of-scope (noted in STATE.md deferred items)"
metrics:
  duration: "465s (~8 min)"
  completed: "2026-06-03"
  tasks_completed: 3
  files_modified: 7
---

# Phase 81 Plan 01: Weekly Activity Endpoint Summary

**One-liner:** GET /client/activity/weekly — IDOR-safe 7-day zero-filled workout aggregate grouped on visits.gym_date STORED column with golden TZ test (21:30 UTC → next Moscow day).

## What Was Built

Implemented the `GET /client/activity/weekly` endpoint (WACT-01) serving exactly 7 zero-filled Mon→Sun day objects for the current Europe/Moscow week, grouped strictly on the `visits.gym_date` STORED generated column.

### Schema (schemas.py)

`ClientWeeklyActivityItem(ResponseData)` with:
- `date: date` — ISO YYYY-MM-DD wire
- `workouts: int` — 0 for days with no visits
- `minutes: int | None = None` — always None in v2.2 (WACT-03 deferred)

### Repository (repository.py)

`fetch_weekly_activity(session, client_id, monday, sunday) -> dict[date, int]`:
- Raw `text()` SQL: `SELECT gym_date, COUNT(*) AS cnt FROM visits WHERE client_id = :client_id AND gym_date BETWEEN :monday AND :sunday GROUP BY gym_date`
- Groups on `visits.gym_date` STORED column — NEVER `DATE(checked_in_at)` (D-81 TZ contract)
- IDOR: mandatory `:client_id` bind param from caller
- Date params passed as Python `date` objects (asyncpg requires native types)

### Service (service.py)

`get_client_weekly_activity(session, client_id) -> list[ClientWeeklyActivityItem]`:
- Moscow-week anchor: `monday = (now_msk - timedelta(days=weekday())).date()`
- App-side 7-day zero-fill via list comprehension
- Always returns exactly 7 items (empty week → all workouts=0)

### Router (router.py)

`GET /activity/weekly` → `client_get_weekly_activity`:
- `require_client()` IDOR gate; no CSRF (safe GET, RBAC-04)
- `operation_id="client_get_weekly_activity"`, tag "Client-Portal"
- `client.id` is the sole source of `client_id` (D-20-IDOR)

### Tests

**Unit tests** (19 tests — `tests/unit/client_portal/test_weekly_activity_tz.py`):
- Golden TZ assertion: `datetime(2026,6,1,21,30,UTC) → gym_date=2026-06-02` (next Moscow day)
- Boundary: 20:59 UTC stays in same Moscow day; exactly midnight is next day
- Week-anchor helper: exactly 7 dates, starts Monday, ends Sunday, consecutive
- Parametrized TZ tests covering key boundary values
- Schema invariants: fields, camelCase serialisation, defaults

**Integration tests** (7 tests — `tests/integration/client_portal/test_weekly_activity.py`):
- Empty week → 7 items, all workouts=0
- minutes=null always (all items)
- Monday visit → Monday bucket workouts=1, others 0
- Response ordered Mon→Sun (strict ascending dates)
- No-auth → 401
- IDOR: client_b's visit absent from client_a's response
- IDOR (reverse): client_a's visit absent from client_b's response

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | bc54c7d4 | Schema ClientWeeklyActivityItem + golden TZ unit tests |
| 2    | aa77c7f2 | fetch_weekly_activity repo + get_client_weekly_activity service |
| 3    | 50ae7b85 | GET /activity/weekly endpoint + integration & IDOR tests |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg requires native Python date objects, not str()**
- **Found during:** Task 2/3 verification
- **Issue:** Passing `str(monday)` and `str(sunday)` to asyncpg text() params caused `AttributeError: 'str' object has no attribute 'toordinal'`. asyncpg requires Python `date` objects, not ISO string representations.
- **Fix:** Changed bind params to pass `monday` and `sunday` as native `date` objects in `fetch_weekly_activity`.
- **Files modified:** `apps/backend/app/modules/client_portal/repository.py`

**2. [Rule 1 - Bug] asyncpg requires native Python datetime for INSERT params**
- **Found during:** Task 3 integration test run
- **Issue:** `monday_noon_utc.isoformat()` string passed to asyncpg INSERT raised `TypeError: expected a datetime.date or datetime.datetime instance, got 'str'`.
- **Fix:** Changed to pass `monday_noon_utc` (datetime object) directly in test seed helper.
- **Files modified:** `apps/backend/tests/integration/client_portal/test_weekly_activity.py`

**3. [Rule 3 - Blocking] Rate limit (429) during integration test OTP flow**
- **Found during:** Task 3 integration test run
- **Issue:** Tests sharing Redis state caused OTP rate limit (429) to trigger on the second test.
- **Fix:** Added `flush_redis` autouse fixture to test module (mirrors `app.state.redis.flushdb()` pattern from test_payment_method_endpoints.py).
- **Files modified:** `apps/backend/tests/integration/client_portal/test_weekly_activity.py`

**4. [Rule 1 - Ruff] EN dash in summary/comment strings**
- **Found during:** ruff check post-implementation
- **Issue:** `Mon–Sun` with EN dash in router summary string and comment triggered RUF001/RUF003.
- **Fix:** Changed to ASCII hyphen `Mon-Sun`.
- **Files modified:** `apps/backend/app/modules/client_portal/router.py`

### Out-of-Scope (Deferred)

Pre-existing ruff errors in `app/modules/promo_codes/models.py`, `app/modules/promo_codes/service.py`, `tests/test_client_promo_validate.py`, and `tests/integration/client_portal/conftest.py` are NOT fixed per deviation rules (pre-existing, out-of-scope, already noted in STATE.md deferred items). All files modified in this plan are ruff-clean.

## Gates Status

| Gate | Result |
|------|--------|
| `uv run ruff check app/modules/client_portal/` | PASS |
| `uv run ruff check tests/integration/client_portal/test_weekly_activity.py` | PASS |
| `uv run ruff check tests/unit/client_portal/` | PASS |
| `uv run mypy --strict app` | PASS (229 files, 0 issues) |
| `uv run lint-imports` | PASS (3 contracts kept, 0 broken) |
| `uv run pytest -q -k "weekly_activity"` | PASS (26 tests) |

## Known Stubs

None. The endpoint returns real data from the database (visits.gym_date STORED column aggregate). The `minutes=None` field is intentional per WACT-01 spec (WACT-03 deferred, not a stub).

## Threat Flags

No new threat surface beyond the plan's threat model. All STRIDE mitigations implemented:
- T-81-01 (IDOR): client_id from require_client() only; integration test asserts IDOR isolation
- T-81-02 (payload disclosure): only {date, workouts:int, minutes:null} exposed
- T-81-03 (spoofing): require_client() gate; 401 test-covered
- T-81-04 (tampering): raw text() SQL with bound params; lint-imports gate passed

## Self-Check: PASSED

Files created/exist:
- apps/backend/app/modules/client_portal/schemas.py — FOUND (ClientWeeklyActivityItem added)
- apps/backend/app/modules/client_portal/repository.py — FOUND (fetch_weekly_activity added)
- apps/backend/app/modules/client_portal/service.py — FOUND (get_client_weekly_activity added)
- apps/backend/app/modules/client_portal/router.py — FOUND (GET /activity/weekly registered)
- apps/backend/tests/unit/client_portal/__init__.py — FOUND
- apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py — FOUND
- apps/backend/tests/integration/client_portal/test_weekly_activity.py — FOUND

Commits verified:
- bc54c7d4 — FOUND
- aa77c7f2 — FOUND
- 50ae7b85 — FOUND
