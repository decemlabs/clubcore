---
phase: 08-clients-module-audit-log
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 4/4 roadmap success criteria verified; 13/13 requirement IDs satisfied
overrides_applied: 0
human_verification:
  - test: "ILIKE wildcard escape (CR-01)"
    expected: "Submitting ?q=%25 (URL-encoded %) returns only rows with literal % in the search columns; not the full table. Confirm pg_trgm GIN indexes are still used (EXPLAIN should show Bitmap Index Scan on ix_clients_*_trgm for prefix-bounded queries)."
    why_human: "Goal text says 'ILIKE on ФИО + phone (pg_trgm GIN)'. The implementation passes literal user input into the LIKE pattern without escaping %, _, \\. This is a real security warning (CR-01 in 08-REVIEW.md): a caller with VIEW,CLIENTS can craft ?q=% to walk the client base. The behaviour observably matches goal text 'ILIKE on …' (the test_list_q_filter_matches_last_name_or_phone integration test passes), so the goal is technically achieved — but the deviation from secure ILIKE practice is one a human owner must explicitly accept or schedule."
  - test: "session.rollback() inside service (CR-02)"
    expected: "Either keep the explicit await session.rollback() inside create_client/update_client (current code) — and accept that under SAVEPOINT-shared sessions this rolls the OUTER transaction — or remove it and rely on get_db teardown. The 239-test suite passes today because the conflict path leaves no other pending mutations to lose; goal is met. A future caller staging multiple operations could lose work."
    why_human: "Goal is mutation + audit landed in one transaction; on the IntegrityError path no audit row is staged anyway, so the rollback does not erase any audit context that was already there. The goal is therefore met. Whether the eager rollback is acceptable for future call patterns is an architectural decision that human review must resolve."
---

# Phase 8: Clients Module + Audit Log Verification Report

**Phase Goal:** Operator can list, search, filter, sort, view, create, edit, and (owner-only) soft-delete clients via `/api/v1/clients/*`; every mutation lands in `audit_log`; a soft-deleted phone can be reused by a new client.

**Verified:** 2026-05-03
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

### Roadmap Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/v1/clients returns {items,total,page,pageSize}; q ILIKE on ФИО + phone (pg_trgm GIN); filters by tag/gender/createdFrom/createdTo/hasTelegram; sort by created_at DESC default or last_name ASC | VERIFIED | `repository.list_alive` lines 56-133 implements every filter; default sort `created_at DESC, id DESC` line 121, `last_name ASC` line 118; pg_trgm extension migration 0002 line 39; GIN trgm indexes on `lower(last_name)` / `lower(first_name)` lines 120-127. Tests `test_clients_list.py` cover q/tag/gender/dateRange/hasTelegram/sort/pagination (10 tests pass). |
| 2 | POST creates with E.164; PATCH partial; DELETE owner-only soft-delete (sets deleted_at); GET 404 for soft-deleted | VERIFIED | E.164 regex `^\+[1-9]\d{1,14}$` schemas.py line 42; PATCH model_dump(exclude_unset) repository.py line 174; DELETE bound to (DELETE,CLIENTS) router.py line 132 — in OWNER_ONLY (Phase 6 D-11); soft_delete_client sets deleted_at repository.py line 196; get_alive returns None for soft-deleted repository.py line 50. Tests: test_create_invalid_phone_returns_422, test_delete_reception_returns_403_forbidden, test_get_returns_404_for_soft_deleted. |
| 3 | After soft-deleting client with phone +79991234567, creating new client with same phone succeeds; partial unique index WHERE deleted_at IS NULL in place; queries flow through list_alive/get_alive (no raw select(Client) in service layer) | VERIFIED | Partial unique index migration 0002 lines 110-116 `postgresql_where=text("deleted_at IS NULL")`. Service.py imports Client only under TYPE_CHECKING (line 54-55) — runtime never sees the ORM table. Marquee test `test_delete_is_soft_delete_phone_reusable` passes (test_clients_crud.py:195). |
| 4 | login, logout, OTP issue/consume, session revoke, family-reuse-detected, client created/updated/soft-deleted produce one audit_log row each with {actor_user_id, action, resource_type, resource_id, payload, created_at}; no GET /audit-log endpoint | VERIFIED | All 16 emit call-sites use the new async `audit.emit(session, ...)` signature (auth/service.py 5x, auth/router.py 1x, telegram_service.py 3x, telegram/handlers.py 4x, clients/service.py 3x). audit.emit body inserts AuditLog row in-transaction (audit.py lines 78-87). Route enumeration confirmed empty audit path: `app.routes` shows only `/api/v1/clients` and `/api/v1/clients/{client_id}` for clients; audit paths = NONE. test_no_audit_log_endpoint_exists passes. |

**Score:** 4/4 roadmap success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| apps/backend/alembic/versions/0002_clients.py | INFRA-04 migration: pg_trgm + clients + audit_log + indexes | VERIFIED + WIRED | All 6 ordered DDL ops present; downgrade is symmetric. |
| apps/backend/app/core/audit_models.py | AuditLog ORM (D-05) | VERIFIED + WIRED | String FK 'users.id'; nullable actor_user_id; PgUUID resource_id; JSONB payload; btree (actor_user_id, created_at). |
| apps/backend/app/core/audit.py | Async emit() with co-transactional DB INSERT | VERIFIED + WIRED | Async signature `(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)`; structlog INFO + session.add(AuditLog); no commit/flush. |
| apps/backend/app/modules/clients/models.py | Client ORM + Gender enum (CLIENTS-01) | VERIFIED + WIRED | Composes Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin; partial unique index in __table_args__; gender CheckConstraint; tags ARRAY default; emergency_contact JSONB. |
| apps/backend/app/modules/clients/schemas.py | All Pydantic DTOs | VERIFIED + WIRED | ClientCreateRequest (required last_name/first_name/phone), ClientUpdateRequest (rejects explicit null D-01), ClientResponse, ClientListQuery (filters + sort + q normaliser), EmergencyContact. |
| apps/backend/app/modules/clients/repository.py | All select/insert/update/soft_delete on Client | VERIFIED + WIRED | 5 module-level async functions; only file importing Client at runtime. list_alive applies deleted_at IS NULL on every read. |
| apps/backend/app/modules/clients/service.py | Service-layer orchestration | VERIFIED + WIRED | 5 functions; Client imported only under TYPE_CHECKING; emits audit before flush (update/soft_delete) or after flush-success (create); D-09 no-op short-circuit; PhoneExistsError translation. |
| apps/backend/app/modules/clients/router.py | 5 endpoints with require_permission + verify_csrf | VERIFIED + WIRED | All 5 endpoints declared; permission/CSRF gates per D-21; mounted at /api/v1/clients via v1 router. |
| apps/backend/app/api/v1/router.py | Clients router included at /clients prefix | VERIFIED + WIRED | `v1.include_router(clients_router, prefix="/clients", tags=["clients"])` line 15. |
| apps/backend/alembic/env.py | include_object filter to skip GIN trgm indexes | VERIFIED + WIRED | _include_object excludes ix_clients_last_name_trgm and ix_clients_first_name_trgm (lines 41-65). |
| apps/backend/tests/integration/clients/* | List/CRUD/RBAC/audit tests | VERIFIED + WIRED | 4 test files covering 30 tests; full suite 239 tests pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| alembic/env.py | app.modules.clients.models | import | WIRED | Line 26 `import app.modules.clients.models`. |
| alembic/env.py | app.core.audit_models | import | WIRED | Line 27 `import app.core.audit_models`. |
| audit.py | audit_models.AuditLog | from import | WIRED | Line 40. |
| schemas.py ClientListQuery | PageQuery | subclass | WIRED | Line 209. |
| schemas.py *Request/*Response | RequestContract / ResponseData | subclass | WIRED | All DTOs inherit; camelCase wire enforced via ContractModel chain. |
| repository.py | Client ORM | select(Client) | WIRED | Lines 48, 111, 115. |
| service.py | repository | function calls only | WIRED | `from app.modules.clients import repository` line 46; calls repository.list_alive / get_alive / insert_client / update_client / soft_delete_client. |
| service.py | audit.emit | await audit.emit(session, ...) before flush | WIRED | client_created emits after successful flush; client_updated emits after early flush; client_soft_deleted emits then flush. All co-transactional. |
| router.py endpoints | service.py functions | await service.<fn> | WIRED | All 5 endpoints delegate to service. |
| v1/router.py | clients/router.py | include_router | WIRED | Line 15. |
| auth call-sites | new audit.emit signature | await audit.emit(session, ...) | WIRED | 13 call-sites in auth + telegram modules confirmed grep-wise; full auth test suite (28 tests) passes. |
| tests | audit_log | select(AuditLog) | WIRED | test_audit_writes.py (5 tests) + auth tests cover audit row assertions. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| GET /api/v1/clients (router.list_clients) | page | service.list_clients → repository.list_alive → SQL select | Yes (real SQL with predicates + count) | FLOWING |
| GET /api/v1/clients/{id} | client | service.get_client → repository.get_alive → session.scalar(select(Client)) | Yes | FLOWING |
| POST/PATCH/DELETE responses | client | repository INSERT/UPDATE → flush → real DB row | Yes | FLOWING |
| audit_log rows | AuditLog payload | service emits via session.add(AuditLog(...)) inside same tx as mutation | Yes (verified by test_audit_writes assertions) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| App boots and registers clients routes | `python -c "create_app() … paths"` | `/api/v1/clients`, `/api/v1/clients/{client_id}` listed | PASS |
| No audit GET endpoint exposed | `[p for p in paths if 'audit' in p.lower()]` | Empty list | PASS |
| Full test suite passes | `pytest -q` | 239 passed | PASS |
| Clients integration tests pass | `pytest tests/integration/clients` | 30 passed in 3.29s | PASS |
| Auth integration tests pass (audit row assertions for login_success/logout/family_reuse_detected/otp_*) | `pytest tests/integration/auth` | 28 passed in 2.35s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-04 | 08-01 | Migration `0002_clients.py` creates clients + audit_log; enables pg_trgm | SATISFIED | Migration file present with all 6 DDL steps; downgrade symmetric. |
| CLIENTS-01 | 08-01, 08-03 | clients table schema with all 14 columns, FKs, soft-delete, audit | SATISFIED | models.py + migration 0002 columns match; FK ON DELETE RESTRICT on created_by_user_id; UUID+timestamps+soft-delete via mixins. |
| CLIENTS-02 | 08-01, 08-08 | Phone uniqueness via partial unique index WHERE deleted_at IS NULL | SATISFIED | Index uq_clients_phone_alive declared in __table_args__ + migration. test_delete_is_soft_delete_phone_reusable passes. |
| CLIENTS-03 | 08-04, 08-07, 08-08 | GET /api/v1/clients returns {items,total,page,pageSize}; q ILIKE on FIO+phone via pg_trgm GIN | SATISFIED (with security caveat) | Envelope shape verified; q implementation works for canonical inputs. NOTE: CR-01 — q is not LIKE-escaped, so wildcards bypass intended search semantics. Goal text says "ILIKE on …", which is satisfied; security hardening is recommended. |
| CLIENTS-04 | 08-03, 08-04 | Filters: tag/gender/createdFrom/createdTo/hasTelegram; sort created_at_desc default + last_name_asc | SATISFIED | Each filter exercised in test_clients_list.py; sort matrix verified. |
| CLIENTS-05 | 08-04, 08-06, 08-08 | GET on missing/soft-deleted returns 404 client_not_found | SATISFIED | get_alive returns None; service raises ClientNotFoundError. test_get_returns_404_for_missing_id + test_get_returns_404_for_soft_deleted pass. |
| CLIENTS-06 | 08-03, 08-06, 08-08 | POST creates with E.164 phone validation; 409 phone_exists on conflict | SATISFIED | Phone regex enforced at Pydantic boundary; PhoneExistsError on uq_clients_phone_alive IntegrityError. test_create_duplicate_phone_alive_returns_409_phone_exists passes. |
| CLIENTS-07 | 08-03, 08-06 | PATCH partial; rejects explicit null per D-01 | SATISFIED | model_dump(exclude_unset) + _reject_explicit_null model_validator. test_patch_explicit_null_returns_422_invalid_field + test_patch_partial_update_only_changed_fields pass. |
| CLIENTS-08 | 08-07, 08-08 | DELETE owner-only soft-delete; never hard-deletes; sets deleted_at | SATISFIED | (DELETE,CLIENTS) in OWNER_ONLY (Phase 6); soft_delete_client sets deleted_at; row remains in DB. test_delete_reception_returns_403_forbidden + test_delete_is_soft_delete_phone_reusable pass. |
| CLIENTS-09 | 08-04, 08-06 | All queries through list_alive/get_alive helpers | SATISFIED | repository.py is the only runtime importer of Client ORM; service.py uses TYPE_CHECKING only. |
| AUDIT-01 | 08-01 | audit_log table with full column set + ON DELETE RESTRICT actor FK | SATISFIED | audit_models.py + migration 0002. |
| AUDIT-02 | 08-02, 08-05, 08-06, 08-08 | Audit writes from auth + clients flows | SATISFIED | All 16 emit call-sites converted; auth tests assert audit rows for login_success/login_failed/session_revoked/family_reuse_detected/otp_issued/otp_consumed; client tests assert client_created/updated/soft_deleted rows. |
| AUDIT-03 | 08-08 | No GET /audit-log endpoint | SATISFIED | Route enumeration shows no audit path; test_no_audit_log_endpoint_exists asserts. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| repository.py | 73-86 | User input interpolated into ILIKE pattern without LIKE-escape (CR-01) | Warning | Privacy/perf concern; does not block goal. |
| service.py | 117-122, 167-172 | Eager `await session.rollback()` inside service after IntegrityError (CR-02) | Warning | Architectural correctness concern; tests pass because no other mutation pending in same UoW. |
| service.py | 95-100 | `_is_phone_conflict` falls back to substring match `"uq_clients_phone_alive" in str(exc.orig)` (WR-05) | Info | Locale-fragile; mitigated by primary `constraint_name` attribute path. |
| repository.py | 178-184 | Dead `isinstance(value, EmergencyContact)` branch (WR-06) | Info | Code-cleanliness only. |
| service.py | 177-179 | `previous_phone` payload value not type-narrowed (WR-01) | Info | Type-discipline only. |
| test_telegram_start.py | (file) | Missing `redis_clean` fixture (WR-04) | Info | Latent flake risk in CI; does not affect Phase 8 goal achievement. |

None of the findings are BLOCKER-level for the phase goal. CR-01/CR-02 are flagged for human acceptance/scheduling — see human_verification block above.

### Human Verification Required

1. **ILIKE wildcard escape (CR-01)**
   - Test: Submit `?q=%25` (URL-encoded `%`) and confirm response does NOT contain every client. Verify pg_trgm GIN indexes serve search queries.
   - Why human: This is a real security warning on a PII table. Goal text is technically met ("ILIKE on …"), but accepting unescaped wildcards is an explicit ownership decision. Recommend scheduling a short follow-up plan to add `_escape_like` + `escape="\\"` and a `?q=%` regression test.

2. **`session.rollback()` boundary (CR-02)**
   - Test: With a future call pattern that stages multiple mutations in one request, confirm IntegrityError on phone collision does not silently lose the un-flushed mutations.
   - Why human: Goal is met (audit + mutation co-transactional on success path; no audit row to lose on failure path). Whether to keep the explicit rollback or rely on `get_db` teardown is an architectural decision, not a Phase 8 acceptance gate.

### Gaps Summary

No goal-blocking gaps. All 4 roadmap success criteria are observably satisfied in the codebase, all 13 declared requirement IDs map to verified artifacts and behaviour, and the full backend test suite (239 tests) is green. Two human-decision items remain — both flagged in 08-REVIEW.md as critical-class code quality findings; neither alters the phase goal's truth on a happy path. They are surfaced here so the human can either schedule a follow-up plan (recommended for CR-01) or accept the deviations explicitly (CR-02).

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
