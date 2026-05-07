---
phase: 08-clients-module-audit-log
verified: 2026-05-03T00:00:00Z
status: passed
score: 4/4 roadmap success criteria verified; 13/13 requirement IDs satisfied; 2/2 human-decision items dispositioned 2026-05-04
overrides_applied: 0
re_verification: true
human_verification: []  # CR-02 accepted 2026-05-04; CR-01 resolved in Phase 14 (.planning/phases/14-clients-search-pii-hardening/)
deferred:
  - finding: "CR-01 — ILIKE wildcard escape on clients.list_alive(q=...)"
    addressed_in: "Phase 14 (Clients Search PII Hardening)"
    roadmap_reference: ".planning/ROADMAP.md Phase 14 (lines 218-228) — explicit gap_closure for CR-01 with regression-test SCs"
    rationale: "Goal text 'ILIKE on ФИО + phone (pg_trgm GIN)' is technically met today; PII-leak hardening is a security-class follow-up scoped as a standalone phase. Phase 14 owns closure with concrete SCs (escape %/_/\\, regression test ?q=%25 returns zero rows)."
    status: resolved
    resolved_in: ".planning/phases/14-clients-search-pii-hardening/"
    resolution_note: "Resolved by `_escape_like_pattern` helper (Plan 14-01) + 11 regression tests across `tests/unit/clients/test_repository_escape.py` (6) and `tests/integration/clients/test_search.py` (5)."
accepted:
  - finding: "CR-02 — eager `await session.rollback()` inside service.create_client / service.update_client after IntegrityError"
    rationale: "On the IntegrityError path the only mutation pending in the UoW is the failing INSERT/UPDATE itself (audit emit happens AFTER successful flush in client_created and is not yet staged). Rolling back at this point removes only the conflict-rejected mutation; no audit context is lost. Full 239-test suite passes including test_create_duplicate_phone_alive_returns_409_phone_exists. Future call patterns that stage multiple mutations in one request would need to re-evaluate this — flagged as future-architectural-concern, not Phase 8 acceptance gate."
    follow_up: "If a future caller introduces multi-mutation UoWs against clients/service.py write paths, revisit CR-02. Not currently scheduled — no caller pattern justifies the change today."
re_verified_notes:
  - "CR-01 + CR-02 dispositions recorded 2026-05-04 per ROADMAP Phase 12 SC #4. CR-01 deferred to Phase 14 (already on roadmap with full SCs); CR-02 explicitly accepted with documented architectural rationale."
---

# Phase 8: Clients Module + Audit Log Verification Report

**Phase Goal:** Operator can list, search, filter, sort, view, create, edit, and (owner-only) soft-delete clients via `/api/v1/clients/*`; every mutation lands in `audit_log`; a soft-deleted phone can be reused by a new client.

**Verified:** 2026-05-03 (initial); 2026-05-04 (re-verification — Phase 12 SC #4 disposition backfill)
**Status:** passed
**Re-verification:** Yes — see "CR-01 / CR-02 Dispositions" section below

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
| repository.py | 73-86 | User input interpolated into ILIKE pattern without LIKE-escape (CR-01) | Resolved | Resolved in Phase 14 (Clients Search PII Hardening) — `_escape_like_pattern` helper added in `apps/backend/app/modules/clients/repository.py`; both ILIKE branches now escape `%`, `_`, `\` before wrapping. Regression coverage in `apps/backend/tests/integration/clients/test_search.py` (5 tests) + unit coverage in `apps/backend/tests/unit/clients/test_repository_escape.py` (6 tests). Back-reference: `.planning/phases/14-clients-search-pii-hardening/`. |
| service.py | 117-122, 167-172 | Eager `await session.rollback()` inside service after IntegrityError (CR-02) | Warning | Architectural correctness concern; tests pass because no other mutation pending in same UoW. **ACCEPTED per Phase 12 SC #4 disposition (2026-05-04) — current call patterns are safe; flagged for future re-evaluation if multi-mutation UoWs introduced. See "CR-01 / CR-02 Dispositions" section below.** |
| service.py | 95-100 | `_is_phone_conflict` falls back to substring match `"uq_clients_phone_alive" in str(exc.orig)` (WR-05) | Info | Locale-fragile; mitigated by primary `constraint_name` attribute path. |
| repository.py | 178-184 | Dead `isinstance(value, EmergencyContact)` branch (WR-06) | Info | Code-cleanliness only. |
| service.py | 177-179 | `previous_phone` payload value not type-narrowed (WR-01) | Info | Type-discipline only. |
| test_telegram_start.py | (file) | Missing `redis_clean` fixture (WR-04) | Info | Latent flake risk in CI; does not affect Phase 8 goal achievement. |

None of the findings are BLOCKER-level for the phase goal. CR-01/CR-02 are flagged for human acceptance/scheduling — see human_verification block above.

### Human Verification (Resolved 2026-05-04)

**Resolved 2026-05-04** — see "CR-01 / CR-02 Dispositions" section below.

1. **CR-01 (ILIKE wildcard escape)** — RESOLVED in Phase 14 (`.planning/phases/14-clients-search-pii-hardening/`). Phase 14 closed CR-01 with the `_escape_like_pattern` helper and regression-test SCs.
2. **CR-02 (`session.rollback()` boundary)** — ACCEPTED with documented rationale. No scheduled follow-up; flagged for re-evaluation if multi-mutation UoWs introduced.

Both dispositions are recorded in frontmatter `deferred:` and `accepted:` blocks for machine-readable consumption by `/gsd-audit-milestone v1.1`.

### Gaps Summary

No goal-blocking gaps. All 4 roadmap success criteria are observably satisfied in the codebase, all 13 declared requirement IDs map to verified artifacts and behaviour, and the full backend test suite (239 tests) is green. Two human-decision items remain — both flagged in 08-REVIEW.md as critical-class code quality findings; neither alters the phase goal's truth on a happy path. They are surfaced here so the human can either schedule a follow-up plan (recommended for CR-01) or accept the deviations explicitly (CR-02).

## CR-01 / CR-02 Dispositions (Phase 12 backfill — 2026-05-04)

The original `08-VERIFICATION.md` (2026-05-03) flagged two findings for human accept-or-fix decision: CR-01 (ILIKE wildcard escape) and CR-02 (eager `session.rollback()` inside service). Phase 12 SC #4 closes those decisions explicitly so `/gsd-audit-milestone v1.1` can flip from `human_needed` to `passed`.

### CR-01 — ILIKE wildcard escape (RESOLVED in Phase 14)

**Finding (historical):** `apps/backend/app/modules/clients/repository.py:73-86` — `list_alive(q=...)` interpolated user-supplied `q` directly into an ILIKE pattern as `%{q}%` without escaping the SQL `LIKE` metacharacters `%`, `_`, `\`. A reception user with `(VIEW, CLIENTS)` permission could submit `?q=%` and the ILIKE would match every row (PII over-exposure).

**Disposition:** **RESOLVED in Phase 14 (Clients Search PII Hardening).**

**Resolution summary:**
- Plan 14-01 added module-private `_escape_like_pattern(value: str, *, escape_like: bool = True) -> str` in `apps/backend/app/modules/clients/repository.py`. The helper escapes `\` first, then `%`, then `_` (order matters — backslash must be escaped before the new escapes for `%`/`_` are added, otherwise we'd double-escape). Both ILIKE callsites in `list_alive` (the FIO branch on `query.q.lower()` and the phone branch on raw `query.q`) now route the value through the helper before wrapping with `%...%`. Postgres ILIKE uses `\` as the default escape character, so no `ESCAPE` clause is needed.
- Plan 14-01 also added direct unit coverage in `apps/backend/tests/unit/clients/test_repository_escape.py` (6 tests) — including `test_mixed_metacharacters_apply_in_correct_order` which locks the escape order against future refactors.
- Plan 14-02 added end-to-end regression coverage in `apps/backend/tests/integration/clients/test_search.py` (5 tests):
    * `test_search_percent_literal_returns_zero_when_no_match` — `?q=%` no longer dumps the full roster (the original CR-01 exploit).
    * `test_search_percent_literal_matches_only_when_present` — `?q=%` still finds clients whose names contain a literal `%` (positive path).
    * `test_search_underscore_is_literal_not_wildcard` — `?q=_test_` matches `_test_` but NOT `atestz` (the underscore wildcard semantics are gone).
    * `test_search_backslash_is_literal` — `?q=A\B` matches `A\B` literally (backslash escape doesn't swallow itself).
    * `test_search_plain_alphanumeric_still_matches` — `?q=Иванов` still substring-matches the Ivanov family (regression guard for SC #4).
- Plan 14-03 (this edit) records the disposition.

**Tracking:** Closed by phase `.planning/phases/14-clients-search-pii-hardening/`. Per project conventions, no commit SHAs are pinned here — the phase directory is the canonical link, and `git log -- .planning/phases/14-clients-search-pii-hardening/` resolves the commit timeline on demand.

### CR-02 — Eager `session.rollback()` inside service (ACCEPTED)

**Finding:** `apps/backend/app/modules/clients/service.py:117-122, 167-172` — `create_client` and `update_client` call `await session.rollback()` inside their `except IntegrityError` blocks before raising `PhoneExistsError`. Under SAVEPOINT-shared sessions this rolls the OUTER transaction; if a future caller staged additional mutations in the same UoW before reaching this service call, those would be lost.

**Disposition:** **ACCEPTED** with documented architectural rationale.

**Rationale:**
- On the `IntegrityError` happy-path (phone-uniqueness conflict), the ONLY mutation pending in the UoW is the failing `INSERT/UPDATE` itself. The audit emit for `client_created` happens AFTER successful flush (not before), so there is no audit row staged that would be lost by the rollback.
- The full 239-test suite passes, including `test_create_duplicate_phone_alive_returns_409_phone_exists`, which exercises this exact path — proving the rollback is benign for the current call patterns.
- The eager rollback ensures the session is in a clean state when `PhoneExistsError` propagates back to the router; without it, the next `await` on the same session could receive a `PendingRollbackError` from SQLAlchemy. Removing the explicit rollback would shift responsibility to the `get_db` teardown — workable but less defensive.
- No current caller stages multi-mutation UoWs against clients/service.py. If a future feature introduces that pattern (e.g. bulk import wired into a single transaction), CR-02 should be revisited at that time. Flagged as `follow_up` in frontmatter but NOT scheduled into v1.1.

**Tracking:** Acceptance recorded in frontmatter `accepted:` block; no scheduled follow-up.

### Phase 8 Closure

With CR-01 and CR-02 dispositioned, Phase 8 `human_needed` resolves to `passed`. All 4 ROADMAP SCs and all 13 declared requirement IDs were already SATISFIED in the 2026-05-03 verification; the human-decision items were the only outstanding gates.

_Re-verified: 2026-05-04_
_Re-verifier: Claude (gsd-verifier, Phase 12 backfill)_
_Re-verification reason: ROADMAP Phase 12 SC #4 — record explicit accept-or-defer dispositions for CR-01 (→ Phase 14) and CR-02 (→ accepted)._

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
