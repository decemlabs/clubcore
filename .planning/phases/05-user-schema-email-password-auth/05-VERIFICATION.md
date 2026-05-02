---
phase: 05-user-schema-email-password-auth
verified: 2026-05-02T11:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 5: User Schema + Email/Password Auth Verification Report

**Phase Goal:** Operator can log in with email/password, receive httpOnly access + refresh cookies, refresh those cookies safely under parallel-request races, log out (current session and all sessions), and read `/auth/me`.

**Verified:** 2026-05-02
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Seeded owner can POST /api/v1/auth/login with email+password and receive 200 + sz_access + sz_refresh httpOnly cookies + `{user: {id, role, fullName}}`; wrong creds return 401 `invalid_credentials` in timing-equivalent fashion; 6th failed attempt within 15min returns 429 | VERIFIED | `tests/integration/auth/test_login.py` covers: happy path with envelope + 3 cookies (lines 47-83); invalid password → 401 `invalid_credentials` (85-96); unknown email → 401 `invalid_credentials` (98-109); 429 after 5 failures with `code: rate_limited` (111-130). Service: `app/modules/auth/service.py:authenticate` runs `check_login_rate` BEFORE Argon2 verify (lines 109-115); sentinel hash on user-not-found (lines 50-61, 112). All 13 auth tests pass. |
| 2 | After /auth/refresh, previous refresh token is rotated within `family_id`; replaying already-rotated token revokes entire family with `family_reuse_detected` audit event; two parallel refresh calls within ~5s reuse window return same new pair | VERIFIED | `tests/integration/auth/test_refresh.py`: `test_refresh_happy_rotates_token` asserts old row gets `replaced_by_id` + `replaced_at` (68-90); `test_refresh_race_window_returns_same_pair` proves same-pair return via cached `auth:rotate:{old_hash}` (92-121); `test_refresh_reuse_revokes_family` deletes the cache then replays — asserts 401, `family_reuse_detected` event captured via `structlog.testing.capture_logs`, all family rows revoked (123-164). Service: `rotate_refresh` has 3 explicit branches with `with_for_update()` lock (service.py:286-387), NX cache write (322-333), prefix-only audit log (`presented_token_hash_prefix=presented_hash[:8]`, line 385). |
| 3 | POST /auth/logout clears both cookies + deletes Redis session entry + stamps `revoked_at` in DB; POST /auth/logout-all invalidates every active session for current user; GET /auth/me returns 200 with `{id, role, fullName, email, hasTelegram}` for authenticated request and 401 otherwise | VERIFIED | `test_logout.py:test_logout_revokes_family_and_clears_cookies` asserts DB `revoked_at` set, Redis `auth:session:*` deleted, `auth:user_sessions` SREM, `session_revoked` event emitted, all 3 cookies cleared via Max-Age=0 (59-120); `test_logout_unauthenticated_returns_401` (122-129); `test_logout_all_revokes_all_families` proves both families revoked + `session_revoked_all` event (131-179). `test_login.py:test_me_authenticated_returns_user` asserts `{id, role, fullName, email, hasTelegram}` shape (140-159); `test_me_unauthenticated_returns_401` (132-138). Service: `revoke_session`, `revoke_all_sessions` use authoritative DB UPDATE + Redis cleanup (service.py:395-498). Router: `clear_session_cookies` always called regardless of cookie presence (router.py:119). |
| 4 | The pytest `db_session` fixture rolls back via SAVEPOINT between tests against a real Postgres; running `alembic upgrade head` on clean DB followed by `alembic check` produces an empty diff | VERIFIED | `tests/conftest.py:56-108` implements SAVEPOINT pattern: connects to `app.state.engine`, opens outer `trans = await connection.begin()`, binds `async_sessionmaker(..., join_transaction_mode="create_savepoint")`, rolls back on teardown. `tests/integration/test_db_session_savepoint.py` proves contract: two tests insert SAME email and both pass (rollback works). `alembic check` returns "No new upgrade operations detected" (verified live). `tests/integration/test_alembic_clean.py` passes. 132/132 tests pass. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/redis.py` | redis_lifespan + get_redis (D-08) | VERIFIED | Both functions present; `decode_responses=True`; `await client.aclose()` on shutdown; no module imports. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/audit.py` | emit() structlog passthrough with locked event names | VERIFIED | `emit(event, **fields)` resolves logger per call (Wave 5 fix: `structlog.get_logger("audit").info(...)` — enables `capture_logs()` patches). All locked event names documented in module docstring. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/security.py:clear_session_cookies` | Mirrors issue_session_cookies attributes (D-17) | VERIFIED | Three delete_cookie calls with matching Path/HttpOnly/SameSite tuple. sz_refresh Path=`/api/v1/auth`, sportzal_csrf httponly=False. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/models.py` | User, RefreshToken, OtpCode ORM (D-03/D-04/D-06) | VERIFIED | All three classes inherit `Base, UUIDPkMixin, TimestampMixin`. User: email UNIQUE, password_hash NOT NULL, role TEXT+CHECK, full_name single column, telegram_chat_id BIGINT NULL UNIQUE. RefreshToken: family_id, token_hash UNIQUE, replaced_by_id self-FK ON DELETE SET NULL, index on (user_id, family_id). OtpCode in final shape per D-03. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/alembic/versions/0001_auth.py` | Three tables with NAMING_CONVENTION constraints | VERIFIED | `op.create_table("users")`, `op.create_table("otp_codes")`, `op.create_table("refresh_tokens")` (note: order is users → otp_codes → refresh_tokens; refresh_tokens still works because users is created first; otp_codes FK to users is satisfied). All constraint names use `op.f(...)` pattern: `pk_users`, `uq_users_email`, `uq_users_telegram_chat_id`, `ck_users_role`, `fk_refresh_tokens_user_id_users`, `fk_refresh_tokens_replaced_by_id_refresh_tokens`, `fk_otp_codes_user_id_users`, etc. revision='0001_auth', down_revision=None. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/rate_limit.py` | check_login_rate / bump_login_rate | VERIFIED | `_LIMIT = 5`, `_WINDOW_SECONDS = 900`. Key format `ratelimit:login:{email_lower}` per D-19. INCR + EXPIRE pipeline. Raises `RateLimited("rate_limited")`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/service.py` | authenticate, issue_tokens, rotate_refresh, revoke_session, revoke_all_sessions, revoke_sessions_on_password_change, load_user_by_id | VERIFIED | All seven exports present; all locked event names emitted. **Spec deviation noted (acceptable):** `revoke_session` and `revoke_all_sessions` were changed from `async with session.begin():` to autobegin + explicit `session.commit()` to coexist with `get_current_user`'s prior queries on the same session (documented inline at service.py:417-423 and 484-486). The 13 integration tests prove the new pattern preserves correct semantics; this deviation is documented in 05-04-SUMMARY's deviations section and Wave 5 audit logger fix. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/schemas.py` | LoginRequest, LoginResponse, UserPublic, MeResponse | VERIFIED | All four classes present. `LoginRequest` extends `RequestContract` with `email: EmailStr`, `password: str = Field(min_length=12)`. `MeResponse` includes `has_telegram: bool` (camelCase via to_camel). |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/router.py` | 5 endpoints all with response_model=ResponseEnvelope[X] | VERIFIED | `/login`, `/refresh`, `/logout`, `/logout-all`, `/me` — all decorated with ResponseEnvelope. `/login` and `/refresh` do NOT use `Depends(get_current_user)`. `/refresh` reads `request.cookies.get("sz_refresh")` and raises `InvalidAccessToken("missing_refresh_cookie")` when absent. `/logout` ALWAYS calls `clear_session_cookies` regardless of refresh-cookie presence. `/me` casts CurrentUser to User and returns `{id, role, full_name, email, has_telegram}`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/main.py` | combined_lifespan + register_user_loader + prod assertion | VERIFIED | `combined_lifespan` chains `db_lifespan(app), redis_lifespan(app)`. `register_user_loader(load_user_by_id)` called between exception-handler registration and router include. Prod assertion `if settings.environment == "prod" and not settings.cookie_secure: raise RuntimeError`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/api/router.py` | /healthz at root, v1 prefix=/api/v1 | VERIFIED | `api.include_router(health.router)` (root); `api.include_router(v1, prefix="/api/v1")`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/app/api/v1/router.py` | auth_router under /auth with tags | VERIFIED | `v1.include_router(auth_router, prefix="/auth", tags=["auth"])`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/scripts/seed_demo_data.py` | Idempotent owner upsert | VERIFIED | `pg_insert(User).values(...).on_conflict_do_nothing(index_elements=["email"])`. Reads SEED_OWNER_EMAIL/SEED_OWNER_PASSWORD; validates `len(password) < 12`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/tests/conftest.py` | SAVEPOINT db_session + dependency_overrides on get_db & get_redis | VERIFIED | `join_transaction_mode="create_savepoint"`, `await trans.rollback()` on teardown, dependency_overrides for both `get_db` and `get_redis`, `app.dependency_overrides.clear()` in finally. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/tests/integration/test_db_session_savepoint.py` | Two tests with same email both pass | VERIFIED | Both `test_savepoint_first_insert` and `test_savepoint_second_insert_same_email` use `"savepoint-smoke@test.local"`, both pass — proves outer rollback wipes service commits. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/tests/integration/auth/test_login.py` | 6 tests covering AUTH-EP-01..03 + AUTH-LO-04 | VERIFIED | All 6 functions present and pass. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/tests/integration/auth/test_refresh.py` | 4 tests covering TEST-04 three branches | VERIFIED | All 4 functions present and pass; `family_reuse_detected` asserted via `capture_logs`. |
| `/Users/andre/Workspace/Development/clubcore/apps/backend/tests/integration/auth/test_logout.py` | 3 tests covering AUTH-LO-01/02 + 401 unauth | VERIFIED | All 3 functions present and pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| router.login | service.authenticate | direct call | WIRED | router.py:59 calls `authenticate(session, redis, payload.email, payload.password, ip=ip)` |
| router.refresh | request.cookies["sz_refresh"] | direct read | WIRED | router.py:86 `presented = request.cookies.get("sz_refresh")` |
| router.logout / logout-all | clear_session_cookies | direct call | WIRED | router.py:119, 133 — always called regardless of token presence |
| service.authenticate | rate_limit.check_login_rate | called BEFORE verify_password | WIRED | service.py:109 (`check_login_rate`) precedes line 115 (`verify_password`) |
| service.rotate_refresh | refresh_tokens row lock | SELECT...FOR UPDATE | WIRED | service.py:290 `with_for_update()` inside session.begin() block |
| service.revoke_all_sessions | Redis SMEMBERS | smembers + DEL pipeline | WIRED | service.py:471-482; cast for mypy on async smembers |
| main.create_app | register_user_loader | register at composition | WIRED | main.py:75 `register_user_loader(load_user_by_id)` after exception handlers, before router include |
| conftest.async_client | app.dependency_overrides[get_db] / [get_redis] | FastAPI override seam | WIRED | conftest.py:134-135; cleared in finally:142 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| /api/v1/auth/login response | `user` payload | `User` row from `select(User).where(User.email == email_lower)` | Yes — DB query against real Postgres `users` table | FLOWING |
| /api/v1/auth/me response | `u.full_name`, `u.email`, `u.telegram_chat_id` | `register_user_loader(load_user_by_id)` → `session.get(User, user_id)` | Yes — DB lookup by JWT-claim subject | FLOWING |
| Refresh rotation new pair | `(access, raw_refresh, csrf)` | `generate_refresh_token()` + `encode_access_token()` after `with_for_update` row lock | Yes — fresh entropy + DB-row insert + replaced_by_id chain | FLOWING |
| Logout-all family enumeration | `family_ids_raw` | `redis.smembers("auth:user_sessions:{user_id}")` + DB UPDATE on revoked_at | Yes — Postgres authoritative even when Redis SET is empty | FLOWING |
| Audit `family_reuse_detected` | `presented_token_hash_prefix` | `_sha256_hex(presented_token)[:8]` | Yes — never raw token | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite | `uv run pytest` | 132 passed in 2.78s | PASS |
| Auth integration tests | `uv run pytest tests/integration/auth/ -x` | 13 passed in 1.30s | PASS |
| Alembic schema check | `uv run alembic check` | "No new upgrade operations detected" | PASS |
| Importlinter contracts | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |
| `app.modules` not imported by `app.core` | grep -r 'from app.modules' apps/backend/app/core | empty | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| INFRA-03 | 05-03 | First business migration creates users/refresh_tokens/otp_codes | SATISFIED | `alembic/versions/0001_auth.py` creates all three tables; alembic check empty diff |
| AUTH-05 | 05-03, 05-04 | Refresh tokens hashed; family_id rotation; reuse revokes family | SATISFIED | RefreshToken model has token_hash UNIQUE, family_id; rotate_refresh branch C revokes via UPDATE on (user_id, family_id, revoked_at IS NULL); test_refresh_reuse_revokes_family proves it |
| AUTH-06 | 05-01, 05-04 | ~5s reuse-window same-pair return | SATISFIED | refresh_reuse_window_seconds=5 in Settings; rotate_refresh branch B reads `auth:rotate:{old_hash}` cache (NX-protected); test_refresh_race_window_returns_same_pair proves it |
| AUTH-07 | 05-02, 05-04 | Sessions mirror to Redis; logout removes Redis + DB | SATISFIED | issue_tokens writes auth:session:{user_id}:{family_id}; revoke_session DELs the key + stamps revoked_at; test_logout_revokes_family_and_clears_cookies asserts both |
| AUTH-EP-01 | 05-05 | POST /login returns 200 + cookies + {user: {id, role, fullName}} | SATISFIED | router.login returns ResponseEnvelope[LoginResponse] with UserPublic; test_login_happy_returns_envelope_and_three_cookies asserts shape + 3 cookies |
| AUTH-EP-02 | 05-04, 05-05 | Wrong creds 401 invalid_credentials, timing-equivalent | SATISFIED | Sentinel-hash strategy in authenticate; test_login_invalid_password_returns_401 + test_login_unknown_email_returns_401 both assert code=invalid_credentials |
| AUTH-EP-03 | 05-04, 05-05 | 5 failures / 15min → 429 rate_limited | SATISFIED | rate_limit module with _LIMIT=5, _WINDOW=900; check_login_rate runs BEFORE verify; test_login_429_after_5_failures asserts status_code=429, code=rate_limited |
| AUTH-EP-04 | 05-06 | scripts/seed_demo_data.py creates owner from env | SATISFIED | pg_insert.on_conflict_do_nothing; reads SEED_OWNER_EMAIL/PASSWORD; validates 12-char floor |
| AUTH-EP-05 | 05-04, 05-05 | Password min length 12, no complexity rules | SATISFIED | LoginRequest.password = Field(min_length=12); seed script also validates |
| AUTH-LO-01 | 05-05 | /logout revokes current session + clears cookies | SATISFIED | router.logout always calls clear_session_cookies; test_logout_revokes_family_and_clears_cookies asserts revoked_at + Redis cleanup + 3 cookie clears |
| AUTH-LO-02 | 05-04, 05-05 | /logout-all revokes every active session | SATISFIED | revoke_all_sessions enumerates via SMEMBERS + DB UPDATE; test_logout_all_revokes_all_families proves 2 families both revoked |
| AUTH-LO-03 | 05-04 | Password change revokes all sessions (deferred admin endpoint, but call site exists) | SATISFIED | revoke_sessions_on_password_change wrapper exists at service.py:224-244; emits password_changed_revokes_sessions event; documented as not-yet-wired by design |
| AUTH-LO-04 | 05-05 | /me returns {id, role, fullName, email, hasTelegram}; 401 unauth | SATISFIED | router.me returns MeResponse; test_me_authenticated_returns_user + test_me_unauthenticated_returns_401 |
| TEST-01 | 05-07 | db_session SAVEPOINT-based per-test rollback | SATISFIED | conftest.py uses join_transaction_mode="create_savepoint" + outer trans.rollback; test_db_session_savepoint smoke proves contract |
| TEST-02 | 05-08 | Email/password integration tests: 200/401/429 + cookie attrs | SATISFIED | test_login.py asserts Path/HttpOnly/SameSite per cookie; covers all 3 status codes |
| TEST-04 | 05-08 | Refresh tests: happy + reuse-revokes-family + race-window same pair | SATISFIED | test_refresh.py has all three scenarios + family_reuse_detected event captured |
| TEST-08 | 05-03, 05-07 | alembic upgrade head + alembic check produces empty diff | SATISFIED | tests/integration/test_alembic_clean.py passes; manual `alembic check` confirms "No new upgrade operations detected" |

All 17 declared requirement IDs are SATISFIED. No orphaned requirements detected (REQUIREMENTS.md only maps these 17 to Phase 5).

### Anti-Patterns Found

Manual scan of all Phase 5 files surfaced no blockers:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| service.py | 417-423, 484-486 | Documented departure from spec (autobegin pattern instead of `async with session.begin()`) | Info | Acceptable — rationale documented inline; required because `get_current_user` may have already issued a SELECT on the same session (autobegin collision). 13 integration tests prove correctness. |
| router.py | 148 | `cast(User, user)` for `/me` | Info | Documented invariant: register_user_loader binds load_user_by_id at composition. Acceptable. |
| audit.py | 35 | Per-call logger resolution (Wave 5 fix, commit eef0515) | Info | Required for `structlog.testing.capture_logs()` to patch — explicitly tested by test_refresh_reuse_revokes_family and test_logout. |

No TODO/FIXME/PLACEHOLDER comments related to Phase 5 work. No empty implementations. No hardcoded data flowing to user-visible output.

### Human Verification Required

None. All four roadmap success criteria are mechanically verifiable via the integration test suite, which the orchestrator confirmed passes 132/132. The phase delivers a closed end-to-end journey that an operator can execute today: seed → login → /me → refresh (with race tolerance and reuse detection) → logout / logout-all.

### Gaps Summary

No gaps. Every roadmap success criterion has explicit code, schema, and integration-test evidence. Every requirement ID declared in plan frontmatter is satisfied with referenced evidence. The two notable spec deviations (service.py autobegin pattern; audit.py per-call logger resolution) are intentional, documented inline, and validated by the green integration tests.

The orchestrator's pre-flight checks (ruff, mypy strict, lint-imports, alembic check, full pytest) are all green. Re-running each independently during this verification confirmed:

- `uv run pytest` → 132 passed
- `uv run pytest tests/integration/auth/` → 13 passed
- `uv run alembic check` → "No new upgrade operations detected"
- `uv run lint-imports` → 3 kept, 0 broken

Phase 5 goal achieved. Ready to proceed to Phase 6.

---

_Verified: 2026-05-02_
_Verifier: Claude (gsd-verifier)_
