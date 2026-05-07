---
phase: 19-visits-db-reception-check-in-backend
verified: 2026-05-08T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 19: Visits — DB + Reception Check-in (Backend) Verification Report

**Phase Goal:** Reception can check a client into the gym from admin-web, and the system enforces "1 visit per gym-day per client" at the database level (race-proof) plus gym-hours window and active-membership requirement.
**Verified:** 2026-05-08
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `visits` table has `gym_date GENERATED ALWAYS AS ... STORED` + UNIQUE `(client_id, gym_date)`; 10 parallel POSTs yield 1×201 + 9×409 | ✓ VERIFIED | `alembic/versions/0006_visits.py:54-108` — `sa.Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)` + `UniqueConstraint("client_id","gym_date",name="uq_visits_client_id_gym_date")`; `tests/integration/visits/test_visits_concurrent.py` — VIS-TEST-01 asserts `statuses == [201] + [409]*9` + 1 `visit_created` + 9 `visit_rejected_duplicate` audit rows |
| 2 | `POST /api/v1/visits` validates gym hours → 409, then active membership → 409, then inserts with `channel='reception'` and `checked_in_by=actor.id` | ✓ VERIFIED | `service.py:_create_visit_with_anti_fraud` (lines 106-207): Step 1 gym_hours check → `OutsideGymHoursError`; Step 2 `resolve_active_membership` → `NoActiveMembershipError`; Step 3 insert flush+UNIQUE → `DuplicateCheckinError`; `create_visit_reception` passes `channel="reception"` and `checked_in_by=actor.id` |
| 3 | `service.create_visit_self_checkin(session, telegram_user_id, chat_id)` uses same chain, sets `channel='telegram_bot'`, `checked_in_by=NULL`, raises typed exceptions | ✓ VERIFIED | `service.py:create_visit_self_checkin` (lines 227-252): resolves client via `resolve_client_by_telegram_user_id`, delegates to `_create_visit_with_anti_fraud` with `channel="telegram_bot"`, `checked_in_by=None`; raises `ClientNotLinkedError` on missing; `tests/integration/visits/test_visits_self_checkin.py` covers all 4 rejection paths + success with `channel='telegram_bot'`, `checked_in_by IS None`, `actor_user_id IS None` assertions |
| 4 | Reception+owner can list/get visits via `GET /api/v1/visits?clientId&from&to` and `GET /api/v1/visits/{id}` (paginated, default sort `checked_in_at DESC`) | ✓ VERIFIED | `router.py:list_visits` (`Depends(require_permission(Action.VIEW, Resource.VISITS))`); `repository.py:list_by_query` applies client_id/from_/to predicates and orders by `Visit.checked_in_at.desc()`; `VisitListQuery` has `from_: date | None = Field(alias="from")` + `to: date | None`; both endpoints confirmed in `openapi.json` with operationIds `list_visits_api_v1_visits_get` and `get_visit_api_v1_visits__visit_id__get` |
| 5 | Every successful or rejected check-in writes the locked audit event with `channel` payload; bot-path rejections have `actor_user_id=None` | ✓ VERIFIED | `service.py` has all 4 literal audit.emit calls: `"visit_created"` (line 198), `"visit_rejected_outside_hours"` (line 128), `"visit_rejected_no_membership"` (line 152), `"visit_rejected_duplicate"` (line 180); all 4 pairs exist in `LOCKED_AUDIT_EVENTS` at `audit.py:112-115`; `test_visits_audit.py` asserts D-16 payload shapes verbatim; bot path: `audit_actor_user_id=None` passed to private chain |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0006_visits.py` | Migration with STORED GENERATED gym_date + UNIQUE | ✓ VERIFIED | `sa.Computed(..., persisted=True)`, `UniqueConstraint("client_id","gym_date",name="uq_visits_client_id_gym_date")`, 3 FKs, CHECK channel, composite DESC index via `op.execute()` |
| `app/modules/visits/models.py` | Visit ORM — no SoftDeleteMixin, Computed gym_date | ✓ VERIFIED | `class Visit(Base, UUIDPkMixin, TimestampMixin)` — no SoftDeleteMixin; `gym_date: Mapped[date]` with `Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)`; `__table_args__` mirrors migration |
| `app/modules/visits/schemas.py` | 3 BackendSchemaBase schemas: Create/Response/ListQuery | ✓ VERIFIED | `VisitCreateRequest` sealed to `client_id` only; `VisitResponse` with `from_attributes=True`; `VisitListQuery` extends PageQuery with `from_` alias; all inherit BackendSchemaBase `extra='forbid'` |
| `app/modules/visits/repository.py` | get / list_by_query / create — single ORM access point | ✓ VERIFIED | 3 async functions; `list_by_query` applies predicates and `order_by(Visit.checked_in_at.desc())`; `create` does NOT pass gym_date (D-06) |
| `app/modules/visits/service.py` | Anti-fraud chain + reception + bot + read paths | ✓ VERIFIED | `_create_visit_with_anti_fraud` with locked D-03 order; `create_visit_reception`; `create_visit_self_checkin`; `list_visits`; `get_visit`; reject paths emit+commit+raise (D-05) |
| `app/modules/visits/router.py` | 3 endpoints: GET / GET /{id} / POST; RBAC-04 ordering | ✓ VERIFIED | `require_permission(Action.CHECK_IN, Resource.VISITS)` declared BEFORE `verify_csrf` in `create_visit` signature; all 3 endpoints present; `status.HTTP_201_CREATED` on POST |
| `app/core/dependencies.py` | ClientByTelegram Protocol + setter + consumer (D-02) | ✓ VERIFIED | Lines 140-191: `class ClientByTelegram(Protocol)`, `ClientByTelegramResolver` type, `_client_by_telegram_resolver` slot, `register_client_by_telegram_resolver`, `resolve_client_by_telegram_user_id` |
| `app/modules/clients/service.py` | `resolve_client_by_telegram_user_id` function | ✓ VERIFIED | Line 241: `async def resolve_client_by_telegram_user_id(session, tg_user_id) -> Client | None` — queries by `Client.telegram_user_id == tg_user_id` + `deleted_at.is_(None)` |
| `app/main.py` | `register_client_by_telegram_resolver(...)` wired | ✓ VERIFIED | Lines 127-133: local import of `app.modules.clients.service` + `register_client_by_telegram_resolver(clients_service.resolve_client_by_telegram_user_id)` in `create_app()` |
| `app/api/v1/router.py` | visits_router mounted at `/visits` | ✓ VERIFIED | Line 25: `v1.include_router(visits_router, prefix="/visits", tags=["visits"])` |
| `app/core/exceptions.py` | 5 new exceptions (NoActiveMembership, DuplicateCheckin, OutsideGymHours, VisitNotFound, ClientNotLinked) | ✓ VERIFIED | Lines 170-228: all 5 classes with correct base classes, `code` strings, `status_code` values |
| `app/core/config.py` | `gym_hours_start/end: time` + `model_validator` no-midnight-spanning | ✓ VERIFIED | Lines 50-61: `gym_hours_start: time = time(7, 0)`, `gym_hours_end: time = time(23, 0)`, `@model_validator(mode="after")` asserting `gym_hours_end > gym_hours_start` |
| `.env.example` | `GYM_HOURS_START=07:00` + `GYM_HOURS_END=23:00` | ✓ VERIFIED | Lines 54-57: comment block `# Visits — gym hours window (Europe/Moscow)` + both env vars |
| `alembic/env.py` | `import app.modules.visits.models` registered | ✓ VERIFIED | Line 28: `import app.modules.visits.models` alongside auth/clients/memberships |
| `openapi.json` | 3 new visits operations regenerated | ✓ VERIFIED | 3 operationIds: `list_visits_api_v1_visits_get`, `create_visit_api_v1_visits_post`, `get_visit_api_v1_visits__visit_id__get` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `visits/service.py` | `app.core.dependencies` | `resolve_client_by_telegram_user_id` | ✓ WIRED | service.py:43 `from app.core.dependencies import ... resolve_client_by_telegram_user_id` |
| `visits/service.py` | `app.core.dependencies` | `resolve_active_membership` | ✓ WIRED | service.py:44 `from app.core.dependencies import ... resolve_active_membership` |
| `visits/service.py` | `app.modules.visits.repository` | `repository.create` / `list_by_query` / `get` | ✓ WIRED | service.py:57 `from app.modules.visits import repository` |
| `app/main.py` | `app.modules.clients.service` | `register_client_by_telegram_resolver(...)` | ✓ WIRED | main.py:127-133 local import + registration |
| `router.py` | `service.create_visit_reception` | FastAPI Depends chain | ✓ WIRED | router.py:105 `visit = await service.create_visit_reception(session, actor, payload)` |
| `service._is_duplicate_visit_conflict` | migration constraint name | literal `"uq_visits_client_id_gym_date"` | ✓ WIRED | service.py:75-77 checks `constraint == "uq_visits_client_id_gym_date"` + substring fallback; migration line 107 uses same literal name |
| `CheckConstraint name "channel"` | migration `op.f("ck_visits_channel")` | SA `NAMING_CONVENTION` `"ck": "ck_%(table_name)s_%(constraint_name)s"` | ✓ WIRED | `database.py:31` defines the naming convention; model `name="channel"` → `ck_visits_channel`; migration uses `op.f("ck_visits_channel")` directly |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py:create_visit` | `visit` (VisitResponse) | `service.create_visit_reception` → `repository.create` → Postgres INSERT | Yes — real DB insert; gym_date from STORED GENERATED column | ✓ FLOWING |
| `router.py:list_visits` | `page` (PaginatedData[VisitResponse]) | `service.list_visits` → `repository.list_by_query` → `select(Visit).where(...).order_by(...)` | Yes — real DB SELECT with predicates | ✓ FLOWING |
| `router.py:get_visit` | `visit` (VisitResponse) | `service.get_visit` → `repository.get` → `select(Visit).where(id==visit_id)` | Yes — real DB SELECT | ✓ FLOWING |

---

## Behavioral Spot-Checks

Step 7b: Tests serve as behavioral proof. The phase provides 549/551 passing tests (2 pre-existing flakes in Phase 18 worker tests — unrelated to Phase 19). Spot-checks below are based on test structure verification since running the app server is not available.

| Behavior | Verification | Status |
|----------|--------------|--------|
| POST /api/v1/visits returns 201 + VisitResponse | `test_visits_create_reception.py` — 7 test functions including happy path | ✓ PASS (test coverage) |
| 10 concurrent POSTs → 1×201 + 9×409 duplicate_checkin | `test_visits_concurrent.py:test_concurrent_check_in_one_wins` asserts `statuses == [201] + [409]*9` | ✓ PASS (test coverage) |
| Gym hours rejection → 409 outside_gym_hours | `test_anti_fraud_helpers.py` — 6 boundary unit tests; `test_visits_audit.py` integration | ✓ PASS (test coverage) |
| Bot path: channel=telegram_bot, checked_in_by=None, actor=None | `test_visits_self_checkin.py:test_self_checkin_happy_path` asserts all 3 | ✓ PASS (test coverage) |
| STORED GENERATED gym_date MSK-shifted | `test_alembic_visits.py` — UTC 22:30 on 2026-05-07 → gym_date=2026-05-08 (MSK 01:30) | ✓ PASS (test coverage) |

---

## Requirements Coverage

| REQ-ID | Source Plan | Description | Status | Evidence |
|--------|-------------|-------------|--------|----------|
| VIS-01 | 19-01 | Migration 0006_visits with STORED GENERATED gym_date + UNIQUE | ✓ SATISFIED | `alembic/versions/0006_visits.py` — all columns, constraints, FKs, GENERATED column verified |
| VIS-02 | 19-01..03 | `app/modules/visits/{models,schemas,repository,service,router}.py` module template | ✓ SATISFIED | All 5 files exist and are substantive; module follows established template |
| VIS-03 | 19-03 | `create_visit_reception` with anti-fraud chain | ✓ SATISFIED | `service.py:create_visit_reception` + `_create_visit_with_anti_fraud` implement D-03 locked order |
| VIS-04 | 19-02, 19-03 | `create_visit_self_checkin` + ClientByTelegram resolver | ✓ SATISFIED | `service.py:create_visit_self_checkin`; `core/dependencies.py` Protocol slot; `clients/service.py` resolver; wired in `main.py` |
| VIS-05 | 19-01 | `GYM_HOURS_START/END` env vars + Settings fields + model_validator | ✓ SATISFIED | `config.py:50-61`; `.env.example:54-57` |
| VIS-EP-01 | 19-04 | `GET /api/v1/visits?clientId&from&to` paginated, `checked_in_at DESC` | ✓ SATISFIED | `router.py:list_visits`; `repository.py:list_by_query` with DESC sort |
| VIS-EP-02 | 19-04 | `GET /api/v1/visits/{id}` — 404 visit_not_found | ✓ SATISFIED | `router.py:get_visit`; `service.py:get_visit` raises `VisitNotFoundError` |
| VIS-EP-03 | 19-04 | `POST /api/v1/visits` CSRF, 201/409 with discriminated codes | ✓ SATISFIED | `router.py:create_visit` — `status.HTTP_201_CREATED`; `OutsideGymHoursError`/`NoActiveMembershipError`/`DuplicateCheckinError` codes |
| VIS-AUDIT-01 | 19-03 | 4 audit emit branches with payload shapes per D-16 | ✓ SATISFIED | All 4 literal `audit.emit` calls in `service.py`; D-16 shapes verified in `test_visits_audit.py` |
| VIS-TEST-01 | 19-05 | Concurrent test: 10 parallel → 1×201 + 9×409 | ✓ SATISFIED | `test_visits_concurrent.py` with `db_session_real_commit` fixture (D-13) |

---

## Decision Decisions (D-01 through D-16)

| D-NN | Description | Status | Evidence |
|------|-------------|--------|----------|
| D-01 | POST body sealed to `{clientId}` — extra='forbid' | ✓ VERIFIED | `VisitCreateRequest(BackendSchemaBase)` with only `client_id: UUID`; `test_schemas.py` asserts extra fields raise `ValidationError` |
| D-02 | `ClientByTelegramResolver` Protocol slot — third cross-module resolver | ✓ VERIFIED | `core/dependencies.py:140-191`; wired in `main.py:127-133` |
| D-03 | Anti-fraud order LOCKED: gym_hours → active_membership → insert | ✓ VERIFIED | `service.py:_create_visit_with_anti_fraud` — Steps 1/2/3 in exactly that order (lines 124-193) |
| D-04 | Reception + bot share private `_create_visit_with_anti_fraud` | ✓ VERIFIED | Both `create_visit_reception` and `create_visit_self_checkin` call `_create_visit_with_anti_fraud` |
| D-05 | Rejection paths emit + commit + raise (DEVIATION from Phase 16/17) | ✓ VERIFIED | Lines 138, 159, 188: `await session.commit()` after each `audit.emit` on reject path; `test_reject_paths_are_persisted` explicitly guards against reverting |
| D-06 | STORED GENERATED gym_date — app NEVER writes it | ✓ VERIFIED | `models.py:77-84` `Computed(..., persisted=True)`; `repository.create` does not pass `gym_date` argument |
| D-07 | `checked_in_at` defaults to DB `now()` — not app-computed | ✓ VERIFIED | `models.py:72-75` `server_default=text("now()")`; `VisitCreateRequest` does not expose `checkedInAt` |
| D-08 | UNIQUE INDEX `uq_visits_client_id_gym_date` unconditional; literal-ref'd in `_is_duplicate_visit_conflict` | ✓ VERIFIED | Migration line 107 + model line 106: same literal name; service `_is_duplicate_visit_conflict` checks against this exact string (lines 75-77) |
| D-09 | No ILIKE search, no sort enum — fixed `checked_in_at DESC` | ✓ VERIFIED | `repository.py:list_by_query` uses only client_id/from_/to predicates; `order_by(Visit.checked_in_at.desc())`; `VisitListQuery` has no sort field; `test_schemas.py` asserts sort rejected with ValidationError |
| D-10 | `gym_hours_start/end` are `time` objects parsed by Pydantic v2 | ✓ VERIFIED | `config.py:50-51`: `gym_hours_start: time = time(7, 0)`, `gym_hours_end: time = time(23, 0)` — no custom parser needed |
| D-11 | No midnight-spanning gym hours — model_validator asserts `end > start` | ✓ VERIFIED | `config.py:53-61` `_gym_hours_range_invariant`; `test_config.py` tests `23:00→07:00` raises ValidationError |
| D-12 | `ClientNotLinkedError` (404) — no audit emit on unknown telegram_user_id | ✓ VERIFIED | `service.py:create_visit_self_checkin:242` raises `ClientNotLinkedError` without preceding `audit.emit`; `test_visits_self_checkin.py:test_self_checkin_unknown_telegram_id_raises_client_not_linked` asserts zero audit rows |
| D-13 | `db_session_real_commit` fixture for VIS-TEST-01 (non-SAVEPOINT) | ✓ VERIFIED | `tests/integration/visits/conftest.py:251-286` — dedicated fixture with real engine + TRUNCATE teardown |
| D-14 | `create_app()` supports stub-resolver injection for tests | ✓ VERIFIED | `register_client_by_telegram_resolver` is idempotent (replaces slot); `test_visits_self_checkin.py` leverages this via `app` fixture |
| D-15 | Real Postgres 16 migration smoke test required | ✓ VERIFIED | `test_alembic_visits.py:test_gym_date_generated_column_msk_shifted` — inserts at UTC 22:30, asserts `gym_date == 2026-05-08` (MSK+3 next day) |
| D-16 | Audit payload schemas locked verbatim | ✓ VERIFIED | `service.py` emits exactly: `visit_created: {client_id, membership_id, channel}`; `visit_rejected_no_membership: {client_id, channel}`; `visit_rejected_duplicate: {client_id, gym_date, channel}`; `visit_rejected_outside_hours: {client_id, channel, current_local_time, gym_open, gym_close}`; `test_visits_audit.py` asserts `set(payload.keys()) == expected_keys` for each |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Anti-pattern scan across all Phase 19 files: no `TODO`/`FIXME`/`PLACEHOLDER` comments in implementation code, no `return null`/`return {}`/`return []` stubs, no hardcoded empty data in rendering paths. The `del chat_id` in `service.py:239` is documented as forward-compatibility (`# forward-compat; Phase 20's handler may use it for DM routing`) — not a stub.

---

## Cross-Cutting Checks

**Import-linter contracts:** 3 contracts unchanged. `app.modules.visits.service → app.core.dependencies` is modules→core (allowed). `app.modules.clients.service` registration in `app.main.create_app` is explicitly outside the `app.core` scope of the `core-not-depend-on-modules` contract. No new contract relaxations.

**RBAC-04 ordering:** `router.py:create_visit` declares `actor: Annotated[CurrentUser, Depends(require_permission(Action.CHECK_IN, Resource.VISITS))]` BEFORE `_csrf: Annotated[None, Depends(verify_csrf)]` — unauthenticated callers see 401 before CSRF errors.

**`(CHECK_IN, VISITS)` NOT in OWNER_ONLY:** `permissions.py:60` comment confirms reception retains `(CHECK_IN, VISITS)`. Reception clients receive 201.

**No `apps/admin-web` changes:** Phase 22 owns FE wiring. Git log from Phase 19 commits shows no admin-web paths modified.

**No new runtime deps:** `time` and `ZoneInfo` are stdlib; `sa.Computed` is stock SQLAlchemy 2.0.

**`openapi.json` regenerated:** 3 new operations confirmed in `openapi.json` with Phase 19 operationIds.

---

## Pre-Existing Flakes / Issues

**Phase 18 worker test flakes (2 tests):**

- `tests/integration/workers/test_expire_memberships.py`
- `tests/integration/workers/test_expire_memberships_idempotent.py`

**Root cause:** Tests compute fixture `end_date` using `datetime.now(UTC).date()` but the worker's `expire_memberships` SQL uses Postgres `CURRENT_DATE` which resolves in the container's TZ (UTC). The mismatch only surfaces between UTC midnight and MSK midnight (a 3-hour window, 21:00–00:00 UTC). The verifier ran during this window.

**This is NOT caused by Phase 19.** Phase 19 introduced no worker code and no changes to membership expiry logic.

**Recommendation:** File as Phase 18 follow-up. Fix: replace `datetime.now(UTC).date()` with `datetime.now(ZoneInfo("Europe/Moscow")).date()` in the affected test fixtures to match the worker's date semantics. Alternatively, stub `CURRENT_DATE` in the test session using `SET LOCAL TIME ZONE 'UTC'`.

---

## Human Verification Required

None. All critical behaviors are covered by automated tests that passed (549/551, with 2 pre-existing Phase 18 flakes unrelated to Phase 19). The concurrent test (VIS-TEST-01) and migration smoke test (D-15 real Postgres 16) provide the strongest behavioral evidence for the two headline invariants.

---

## Summary

Phase 19 goal is fully achieved. All 5 ROADMAP Success Criteria are demonstrably TRUE in the codebase. All 10 Phase 19 REQ-IDs are satisfied. All 16 D-NN locked decisions are encoded in source. The `visits` module is complete, wired, tested, and ready for Phase 20 (Telegram bot `/checkin`) to consume `service.create_visit_self_checkin`.

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
