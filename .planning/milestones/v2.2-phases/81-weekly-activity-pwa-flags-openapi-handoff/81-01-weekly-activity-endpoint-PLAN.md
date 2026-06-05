---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/tests/integration/client_portal/test_weekly_activity.py
  - apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py
autonomous: true
requirements: [WACT-01]
must_haves:
  truths:
    - "GET /client/activity/weekly returns exactly 7 objects ordered Mon→Sun for the current Europe/Moscow week"
    - "Days with no visits return workouts=0 and minutes=null (zero-fill, never an empty [] array)"
    - "Two visits on the same day produce a single bucket with workouts=2"
    - "A visit checked_in_at=21:30 UTC lands in the NEXT Moscow calendar day's bucket (gym_date STORED column)"
    - "client_a's visits never appear in client_b's response (IDOR-safe, client_id from principal only)"
    - "minutes is always null"
  artifacts:
    - path: "apps/backend/app/modules/client_portal/schemas.py"
      provides: "ClientWeeklyActivityItem response schema (date, workouts:int, minutes:int|None)"
      contains: "class ClientWeeklyActivityItem"
    - path: "apps/backend/app/modules/client_portal/repository.py"
      provides: "fetch_weekly_activity raw-SQL aggregate over visits.gym_date"
      contains: "def fetch_weekly_activity"
    - path: "apps/backend/app/modules/client_portal/service.py"
      provides: "get_client_weekly_activity service with app-side 7-day zero-fill"
      contains: "def get_client_weekly_activity"
    - path: "apps/backend/app/modules/client_portal/router.py"
      provides: "GET /activity/weekly endpoint, Client-Portal tag, require_client()"
      contains: "client_get_weekly_activity"
    - path: "apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py"
      provides: "Golden TZ test (21:30 UTC → next Moscow day) per v1.8 VER-02"
      contains: "test_tz_boundary"
    - path: "apps/backend/tests/integration/client_portal/test_weekly_activity.py"
      provides: "Endpoint behavior + IDOR integration tests"
      contains: "weekly"
  key_links:
    - from: "client_portal/router.py"
      to: "client_portal/service.get_client_weekly_activity"
      via: "service call wrapped in envelope()"
      pattern: "service\\.get_client_weekly_activity"
    - from: "client_portal/service.py"
      to: "client_portal/repository.fetch_weekly_activity"
      via: "repository call + app-side zero-fill"
      pattern: "repository\\.fetch_weekly_activity"
    - from: "client_portal/repository.py"
      to: "visits.gym_date"
      via: "raw SQL GROUP BY gym_date BETWEEN monday AND sunday"
      pattern: "gym_date BETWEEN"
---

<objective>
Build the `GET /client/activity/weekly` endpoint (WACT-01): a read-only, IDOR-safe weekly workout
aggregate returning exactly 7 zero-filled day buckets (Mon→Sun) for the current Europe/Moscow week,
grouped on the `visits.gym_date` STORED generated column.

Purpose: Provides the data source the PWA weekly-activity bars (Plan 02) consume, and the final
v2.2 client-portal path the OpenAPI handoff (Plan 03) freezes into the contract.
Output: New schema + repository function + service function + router endpoint + golden TZ unit test
+ integration tests, all gates green.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-CONTEXT.md
@.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md

<interfaces>
<!-- Contracts the executor implements/consumes. Extracted from PATTERNS.md + codebase. Do NOT re-explore. -->

Response schema base (apps/backend/app/modules/client_portal/schemas.py:21):
  from app.core.schemas import BackendSchemaBase, ResponseData
  ClientVisitItem (line 64) and ClientPtSessionItem (line 72) are sibling ResponseData output schemas.

New schema to add — ClientWeeklyActivityItem(ResponseData):
  date: date            # wire: ISO YYYY-MM-DD
  workouts: int         # per-day visit count, 0 for empty days
  minutes: int | None = None   # ALWAYS None in v2.2 (no duration column — WACT-03 deferred)

gym_date STORED column (apps/backend/app/modules/visits/models.py:77-84):
  gym_date: Mapped[date] = Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)
  table "visits"; columns client_id (UUID FK clients.id), gym_date (Date STORED).
  UNIQUE (client_id, gym_date) — at most one visit row per client per Moscow day.

Repository analog (client_portal/repository.py): fetch_client_visits_page (line 243) and
  fetch_client_membership (line 169). Raw SQL via `from sqlalchemy import text` ONLY — NEVER import
  the Visit ORM model (D-54-08 cross-module read). Bind params via :name + dict; UUID → str().
  `.mappings().all()` for list reads. Moscow-TZ date anchor pattern at line 194:
  `(now() AT TIME ZONE 'Europe/Moscow')::date`.

Router analog (client_portal/router.py): client_get_membership (lines 144-162),
  client_list_visit_history (lines 218-234). router = APIRouter(tags=["Client-Portal"]).
  GET endpoints take `client: Annotated[ClientPrincipal, Depends(require_client())]` and
  `session: Annotated[AsyncSession, Depends(get_db)]`, NO verify_client_csrf (safe method, RBAC-04),
  NO try/except (AppError bubbles), return envelope(result). operation_id uses client_ prefix.

ResponseEnvelope: from app.core.schemas import ResponseEnvelope, envelope.
  response_model=ResponseEnvelope[list[ClientWeeklyActivityItem]].

Integration test harness (tests/integration/client_portal/test_payment_method_endpoints.py:48-84):
  _overridden_app + http_client (ASGITransport) + stub_otp_sender fixtures;
  _auth_as_client imported from tests.integration.client_portal.test_idor_sweep.

Golden TZ unit pattern (tests/unit/visits/test_schemas.py + PATTERNS.md lines 270-292):
  _MSK = ZoneInfo("Europe/Moscow"); 2026-06-01 21:30 UTC → astimezone(_MSK).date() == 2026-06-02.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ClientWeeklyActivityItem schema + golden TZ unit test (RED→GREEN)</name>
  <read_first>
    - apps/backend/app/modules/client_portal/schemas.py (analog: ClientVisitItem line 64, ClientPtSessionItem line 72, ResponseData import line 21)
    - apps/backend/app/modules/visits/models.py (gym_date STORED column lines 77-84 — the bucketing contract)
    - apps/backend/tests/unit/visits/test_schemas.py (v1.8 VER-02 golden TZ pattern; ZoneInfo("Europe/Moscow"))
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (schemas.py + test sections, lines 193-292)
  </read_first>
  <behavior>
    - Schema ClientWeeklyActivityItem serialises date as ISO YYYY-MM-DD, workouts as int, minutes as null.
    - Golden TZ: datetime(2026,6,1,21,30,tzinfo=UTC).astimezone(Europe/Moscow).date() == date(2026,6,2) (next Moscow day).
    - Week-anchor helper: for any datetime in Moscow, Monday = now_msk - timedelta(days=weekday()); Sunday = Monday + 6 days; produces 7 consecutive dates.
  </behavior>
  <action>
    Add `class ClientWeeklyActivityItem(ResponseData)` to client_portal/schemas.py with fields `date: date`, `workouts: int`, `minutes: int | None = None` — mirror the ClientVisitItem ResponseData style; `date` uses the already-imported `datetime.date`. Docstring: ordered Mon→Sun, minutes always None (no duration column, WACT-03 deferred).
    Create apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py with the golden TZ test (`_MSK = ZoneInfo("Europe/Moscow")`): assert a `checked_in_at = datetime(2026,6,1,21,30,tzinfo=UTC)` maps to `gym_date = date(2026,6,2)` (the STORED column `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` equivalent), and that the Monday-anchored 7-date window correctly indexes that gym_date. Also assert the week-anchor helper produces exactly 7 consecutive dates Mon→Sun. Create the `tests/unit/client_portal/__init__.py` package marker if absent. No fenced code in the file beyond standard test source.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/unit/client_portal/test_weekly_activity_tz.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - ClientWeeklyActivityItem importable from app.modules.client_portal.schemas.
    - Golden TZ assertion passes: 21:30 UTC visit → gym_date is the next Moscow calendar day (2026-06-02).
    - Week-anchor helper yields 7 consecutive Mon→Sun dates.
    - `uv run mypy --strict app` exit 0 for the new schema.
  </acceptance_criteria>
  <done>Schema added, golden TZ unit test green, mypy strict clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: fetch_weekly_activity repository + get_client_weekly_activity service + zero-fill</name>
  <read_first>
    - apps/backend/app/modules/client_portal/repository.py (analogs: fetch_client_visits_page line 243, fetch_client_membership line 169; Moscow-TZ date anchor line 194; `from sqlalchemy import text`; __all__ around lines 36-41)
    - apps/backend/app/modules/client_portal/service.py (analogs: get_client_membership, list_client_visits pattern; ZoneInfo Moscow usage)
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (repository section lines 126-189, service section lines 82-123)
    - apps/backend/.importlinter (confirm client_portal raw-SQL contract — no new ignore_imports)
  </read_first>
  <behavior>
    - fetch_weekly_activity returns dict{date:int} of visit counts WHERE client_id = :client_id AND gym_date BETWEEN :monday AND :sunday GROUP BY gym_date.
    - get_client_weekly_activity computes Monday/Sunday from datetime.now(Europe/Moscow), calls repo, app-side zero-fills all 7 days (workouts=0, minutes=None for missing days), returns list ordered Mon→Sun.
    - Empty week → list of 7 items all workouts=0 (never []).
    - Same-day double-count: two rows aggregated to workouts=2 in that one bucket.
  </behavior>
  <action>
    Add `async def fetch_weekly_activity(session, client_id: UUID, monday: date, sunday: date) -> dict[date, int]` to repository.py using raw `text()` SQL: `SELECT gym_date, COUNT(*) AS cnt FROM visits WHERE client_id = :client_id AND gym_date BETWEEN :monday AND :sunday GROUP BY gym_date ORDER BY gym_date ASC`. Bind `client_id` as `str(client_id)`, `monday`/`sunday` as `str(date)`. Use `.mappings().all()`; return `{row["gym_date"]: int(row["cnt"]) for row in rows}`. Add the function name to repository `__all__`. NEVER import the Visit ORM model — raw SQL only (D-54-08); zero new `ignore_imports` in .importlinter. Group strictly on `visits.gym_date` STORED column — NEVER `DATE(checked_in_at)`. NOTE: WACT-01 in REQUIREMENTS.md mentions "(+ pt_sessions)", but the locked 81-CONTEXT decision groups strictly on visits.gym_date for the golden-TZ contract; following CONTEXT per user-decision fidelity (do NOT join pt_sessions).
    Add `async def get_client_weekly_activity(session, client_id: UUID) -> list[ClientWeeklyActivityItem]` to service.py: compute `now_msk = datetime.now(ZoneInfo("Europe/Moscow"))`, `monday = (now_msk - timedelta(days=now_msk.weekday())).date()`, `sunday = monday + timedelta(days=6)`, call `repository.fetch_weekly_activity`, then build the 7-element list via `[ClientWeeklyActivityItem(date=monday+timedelta(days=i), workouts=rows.get(monday+timedelta(days=i),0), minutes=None) for i in range(7)]`.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/unit/client_portal/test_weekly_activity_tz.py -x -q && uv run mypy --strict app && uv run lint-imports</automated>
  </verify>
  <acceptance_criteria>
    - fetch_weekly_activity uses raw text() SQL on visits.gym_date, no Visit ORM import.
    - get_client_weekly_activity always returns a 7-element list ordered Mon→Sun with app-side zero-fill.
    - `uv run lint-imports` exit 0 (zero new ignore_imports; client_portal cross-module raw-SQL contract intact).
    - `uv run mypy --strict app` exit 0.
  </acceptance_criteria>
  <done>Repository + service functions implemented, import-linter + mypy strict green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: GET /activity/weekly endpoint + integration & IDOR tests</name>
  <read_first>
    - apps/backend/app/modules/client_portal/router.py (analogs: client_get_membership lines 144-162, client_list_visit_history lines 218-234; APIRouter tags=["Client-Portal"]; require_client, get_db, envelope imports)
    - apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py (harness lines 48-84: _overridden_app, http_client, stub_otp_sender)
    - apps/backend/tests/integration/client_portal/test_idor_sweep.py (_auth_as_client helper + IDOR assertion style)
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (router section lines 28-79, test behaviors lines 294-301)
  </read_first>
  <behavior>
    - GET /api/v1/client/activity/weekly returns 200 with ResponseEnvelope wrapping a 7-item array.
    - Empty week → exactly 7 items, all workouts=0, minutes=null.
    - One Monday visit → Monday bucket workouts=1, all others 0.
    - Two visits same day → that bucket workouts=2.
    - Response ordered Mon→Sun (dates strictly ascending, 7 consecutive days).
    - IDOR: a visit seeded for client_b does NOT appear in client_a's response.
    - No auth cookie → 401 (require_client guard).
  </behavior>
  <action>
    Register `GET /activity/weekly` in client_portal/router.py: `response_model=ResponseEnvelope[list[ClientWeeklyActivityItem]]`, `operation_id="client_get_weekly_activity"`, summary referencing WACT-01 (Mon–Sun, Europe/Moscow, zero-filled). Handler `async def client_get_weekly_activity(client: Annotated[ClientPrincipal, Depends(require_client())], session: Annotated[AsyncSession, Depends(get_db)])` → `return envelope(await service.get_client_weekly_activity(session, client.id))`. NO verify_client_csrf (safe GET, RBAC-04); NO try/except; client_id comes ONLY from `client.id` (D-20-IDOR). Add `ClientWeeklyActivityItem` to the router's schemas import.
    Create apps/backend/tests/integration/client_portal/test_weekly_activity.py using the _overridden_app/http_client/stub_otp_sender harness and `_auth_as_client`. Seed visits directly via the db_session (insert into visits with explicit checked_in_at so gym_date STORED column computes; use a checked_in_at known to fall in the current Moscow week). Cover the six behaviors above plus the 401-no-auth case. For the same-day-double-count case respect the UNIQUE(client_id,gym_date) — use two different clients OR assert the count semantics with seed data that the schema permits (one row per client per day means workouts=2 requires aggregating across the permitted shape; if the unique index blocks two rows for one client/day, assert the realistic max and document it). For IDOR, seed a visit for a second client and assert it is absent from the first client's buckets.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/client_portal/test_weekly_activity.py -x -q && uv run ruff check && uv run mypy --strict app && uv run pytest -q -k "weekly_activity"</automated>
  </verify>
  <acceptance_criteria>
    - GET /api/v1/client/activity/weekly returns 200 with exactly 7 ordered Mon→Sun items.
    - Empty-week, single-visit, ordering, and IDOR-isolation behaviors all pass.
    - No-auth request returns 401.
    - `uv run ruff check` + `uv run mypy --strict app` + `uv run lint-imports` all exit 0.
    - Full weekly-activity test selection (`-k weekly_activity`) green.
  </acceptance_criteria>
  <done>Endpoint registered and reachable, integration + IDOR + golden TZ tests green, all backend gates exit 0.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client browser → /client/activity/weekly | Authenticated client cookie (aud:"client") crosses; untrusted otherwise |
| service → visits table | Cross-module raw-SQL read of another module's data (D-54-08) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-81-01 | Information Disclosure (IDOR) | client_get_weekly_activity | mitigate | client_id sourced ONLY from `client.id` of require_client() principal; SQL WHERE client_id = :client_id bind param; integration test asserts client_b visits absent from client_a response (D-20-IDOR) |
| T-81-02 | Information Disclosure | weekly-activity payload | mitigate | Payload exposes only {date, workouts:int, minutes:null} — no PII, no visit-level detail, no other-client data; minutes hardcoded null |
| T-81-03 | Spoofing | endpoint auth | mitigate | require_client() enforces aud:"client" cookie; no-auth request returns 401 (test-covered) |
| T-81-04 | Tampering | cross-module read | mitigate | Raw text() SQL with bound params (no string interpolation of client_id); zero new ignore_imports (lint-imports gate) |
| T-81-05 | Denial of Service | aggregate query | accept | Query bounded to 7-day window with UNIQUE(client_id,gym_date) index; at most ~7 rows scanned per client; low-value target |
</threat_model>

<verification>
- `cd apps/backend && uv run ruff check` exit 0
- `cd apps/backend && uv run mypy --strict app` exit 0
- `cd apps/backend && uv run lint-imports` exit 0 (no new ignore_imports)
- `cd apps/backend && uv run pytest -q -k "weekly_activity"` green (unit golden-TZ + integration + IDOR)
- Manual: golden TZ unit test explicitly asserts 21:30 UTC → next Moscow day bucket
</verification>

<success_criteria>
- Roadmap SC1: GET /client/activity/weekly returns exactly 7 zero-filled Mon→Sun objects, workouts per day, minutes=null, grouped on visits.gym_date STORED column.
- Roadmap SC2: Golden TZ test (21:30 UTC → next Moscow calendar day) green.
- WACT-01 satisfied; endpoint exists for Plan 02 to consume and Plan 03 to freeze.
</success_criteria>

<output>
Create `.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-01-SUMMARY.md` when done.
</output>
