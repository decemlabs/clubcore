# Phase 5: User Schema + Email/Password Auth - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can log in with email/password, receive httpOnly access + refresh cookies, refresh those cookies safely under parallel-request races, log out (current session and all sessions), and read `/auth/me`. This is the first business migration in v1.1.

**Phase 5 ships:**

1. **First business Alembic migration `0001_auth.py`** — creates `users`, `refresh_tokens`, `otp_codes` (INFRA-03). Final schema for all three; Phase 7 only writes app code, no follow-up migration.
2. **ORM models** — `User`, `RefreshToken`, `OtpCode` under `app/modules/auth/models.py`; compose Phase 4 mixins (`UUIDPkMixin`, `TimestampMixin`).
3. **`/api/v1/auth/*` router** — `POST /login`, `POST /refresh`, `POST /logout`, `POST /logout-all`, `GET /me` (AUTH-EP-01..05, AUTH-LO-01..04).
4. **Refresh-rotation service** — DB-led family rotation (AUTH-05), ~5s reuse-window via `replaced_by_id` chain + short-lived Redis cache (AUTH-06), `family_reuse_detected` revokes whole family (Phase 5 SC #2).
5. **Redis sessions** — lifespan-managed `redis.asyncio.Redis` client; `auth:session:{user_id}:{family_id}` JSON value with TTL = refresh expiry; sibling SET `auth:user_sessions:{user_id}` for logout-all enumeration (AUTH-07, AUTH-LO-02).
6. **Rate limiter** — fixed-window per-email login throttle (AUTH-EP-03) backed by Redis.
7. **Composition wiring** — `register_user_loader(load_user_by_id)` called inside `create_app()` (Phase 4 D-24 slot finally filled). API prefix flip: `app/api/router.py` mounts `v1` at `/api/v1`; `/healthz` reconciled to stay at root.
8. **Seed script `apps/backend/scripts/seed_demo_data.py`** — creates one owner from `SEED_OWNER_EMAIL` + `SEED_OWNER_PASSWORD` (AUTH-EP-04); idempotent (UPSERT-on-conflict by email).
9. **Test infra upgrade (TEST-01)** — `db_session` fixture switches to SAVEPOINT-based per-test rollback against real Postgres; integration tests for login (TEST-02), refresh rotation (TEST-04), alembic-clean idempotency after migration (TEST-08).
10. **Pinned dep** — `redis>=5,<6` added to `apps/backend/pyproject.toml`; `uv lock` regenerated.

**In scope (Phase 5 REQ-IDs):** INFRA-03, AUTH-05, AUTH-06, AUTH-07, AUTH-EP-01, AUTH-EP-02, AUTH-EP-03, AUTH-EP-04, AUTH-EP-05, AUTH-LO-01, AUTH-LO-02, AUTH-LO-03, AUTH-LO-04, TEST-01, TEST-02, TEST-04, TEST-08.

**Out of scope (deferred to later phases):**
- `Depends(require_permission(...))` on routes (Phase 6 — RBAC-02..05). Phase 5 routes use `Depends(get_current_user)` only; permission checks are not yet enforced inline.
- `verify_csrf` dependency (Phase 6 — CSRF-02). Phase 5 emits the `sportzal_csrf` cookie via the existing helper but does not validate it on POST/PATCH/DELETE.
- Telegram OTP flow (Phase 7 — AUTH-TG-*). Phase 5 ships the `otp_codes` table with its final shape, but no `/auth/telegram/*` endpoints and no bot worker process.
- `audit_log` table + DB-row audit writes (Phase 8 — INFRA-04, AUDIT-01..03). Phase 5 emits structured `structlog` events at the audit call sites with stable `event=` names so Phase 8 can swap in DB-row writers without changing call sites.
- Frontend wiring (Phase 10).

</domain>

<decisions>
## Implementation Decisions

### User / RefreshToken / OtpCode schema (INFRA-03)

- **D-01 [LOCKED]:** **`User.full_name` is a single `text NOT NULL` column.** Operators are 1-2 people; the ФИО triple lives on `clients` (CLIENTS-01) because clients are a different domain. `/auth/me` returns `fullName` directly. Renaming later is a single-column migration if ever needed.
- **D-02 [LOCKED]:** **`User.password_hash` is `text NOT NULL`; `User.telegram_chat_id` is `bigint NULL UNIQUE` from day 1.** Phase 5 only mints email/password users (seeded owner + future invites), so the password-hash invariant holds. `telegram_chat_id` must be nullable+unique now so (a) `/auth/me` can derive `hasTelegram = telegram_chat_id IS NOT NULL`, (b) Phase 7 binds via plain `UPDATE users SET telegram_chat_id = ... WHERE id = ...` with no schema change. Phase 7's "Telegram-only signup" path (if it materializes) will need a follow-up migration to make `password_hash` nullable — that's Phase 7's job, not P5's.
- **D-03 [LOCKED]:** **`OtpCode` ships its final Phase 7 shape in `0001_auth.py`** — INFRA-03 already obliges us to create the table now, and "table exists but with placeholder columns" is strictly worse than the final shape. Columns:
  - `id UUID PK` (UUIDPkMixin)
  - `user_id UUID NULL FK users(id) ON DELETE CASCADE` — set on bind, NULL until then
  - `telegram_chat_id BIGINT NULL` — set on bind
  - `deep_link_token_hash TEXT NOT NULL UNIQUE` — sha256 of the `secrets.token_urlsafe(32)` deep-link token (raw never persisted, AUTH-03)
  - `code_hash TEXT NULL` — sha256 of the 6-digit OTP, set after bind
  - `expires_at TIMESTAMPTZ NOT NULL` — deep-link TTL = 10 min initially; on bind, `code_hash` is written and `expires_at` is bumped to OTP TTL = 5 min
  - `attempts INT NOT NULL DEFAULT 0` — incremented on each failed verify; max 5 (AUTH-TG-02)
  - `consumed_at TIMESTAMPTZ NULL`
  - `created_at TIMESTAMPTZ NOT NULL` (TimestampMixin), no `updated_at` needed
- **D-04 [LOCKED]:** **`RefreshToken` carries a `replaced_by_id` self-FK + `replaced_at` so the rotation chain is queryable in DB.** Columns:
  - `id UUID PK` (UUIDPkMixin)
  - `user_id UUID NOT NULL FK users(id) ON DELETE CASCADE`
  - `family_id UUID NOT NULL` — same value across one rotation chain; index `(user_id, family_id)`
  - `token_hash TEXT NOT NULL UNIQUE` — sha256 of the opaque refresh token (Phase 4 D-03)
  - `expires_at TIMESTAMPTZ NOT NULL`
  - `revoked_at TIMESTAMPTZ NULL` — stamped on logout, family-reuse, or explicit revoke
  - `replaced_by_id UUID NULL FK refresh_tokens(id) ON DELETE SET NULL` — points to the row that rotated this one
  - `replaced_at TIMESTAMPTZ NULL` — when this row was rotated
  - `created_at TIMESTAMPTZ NOT NULL` (TimestampMixin)
- **D-05 [LOCKED]:** **`User` does NOT use `SoftDeleteMixin`.** Operators are 1-2 people; hard-delete after data export is acceptable for v1.1. FK `clients.created_by_user_id` (Phase 8) uses `ON DELETE RESTRICT` so an accidental hard-delete is blocked at the DB. `list_alive`/`get_alive` repository helpers (Phase 8 CLIENTS-09) are not needed for users.
- **D-06 [LOCKED]:** **`User` columns (final list):** `id` (UUIDPkMixin), `email TEXT NOT NULL UNIQUE` (citext-considered, but plain TEXT with `LOWER(email)` index is enough at gym scale; do `email.lower()` at the service boundary on insert + login lookup), `password_hash TEXT NOT NULL`, `role` (StrEnum mapped to native PG enum or to TEXT — see D-07), `full_name TEXT NOT NULL`, `telegram_chat_id BIGINT NULL UNIQUE`, `created_at`/`updated_at` (TimestampMixin). No `is_active`, no `email_verified`, no `last_login_at` (last-login goes to `audit_log` in Phase 8).
- **D-07 (Discretion):** **`User.role` is stored as `TEXT` with a CHECK constraint `role IN ('owner', 'reception')`**, not a Postgres native enum. Reasoning: `Role` is a `StrEnum` with two members locked at compile time (PROJECT.md OoS); the migration churn for adding/removing native PG enum values is worse than a CHECK constraint. SQLAlchemy maps via `Enum(Role, native_enum=False, length=16)`.

### Redis session mirror lifecycle (AUTH-07, AUTH-LO-01..02)

- **D-08 [LOCKED]:** **Lifespan-managed Redis client.** `app/core/redis.py` (NEW) exposes `redis_lifespan` and `get_redis(request) -> redis.asyncio.Redis`, mirroring Phase 2 D-06/D-08 engine pattern. `create_app()` composes `db_lifespan` + `redis_lifespan` (use `contextlib.asynccontextmanager` to chain — both touch `app.state`). Single connection pool per process; `decode_responses=True` so we deal in `str` not `bytes`. `redis>=5,<6` added to `pyproject.toml`.
- **D-09 [LOCKED]:** **Redis value shape for sessions = JSON `{family_id, last_seen_at, refresh_token_hash}`** stored under `auth:session:{user_id}:{family_id}` with `EX = settings.refresh_token_ttl_seconds`. `last_seen_at` updated on every successful `/auth/refresh`; `refresh_token_hash` lets the gate short-circuit to 401 fast when the presented hash doesn't match the current one in Redis (without hitting Postgres).
- **D-10 [LOCKED]:** **Sibling SET `auth:user_sessions:{user_id}` of `family_id`s for logout-all.** On every login + refresh: `SADD auth:user_sessions:{user_id} {family_id}` and `EXPIRE auth:user_sessions:{user_id} {refresh_ttl}`. logout-all flow:
  1. `SMEMBERS auth:user_sessions:{user_id}` → list of family_ids.
  2. Redis pipeline: `DEL auth:session:{user_id}:{fid}` for each + `DEL auth:user_sessions:{user_id}`.
  3. SQL: `UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = :uid AND revoked_at IS NULL`.
  4. structlog `event=session_revoked_all`.
  No SCAN. O(n) bounded by the user's active families (typically 1-3).
- **D-11 [LOCKED]:** **`/auth/refresh` gate = Redis-first fast path, Postgres authoritative for state changes.** Flow:
  1. Read `sz_refresh` cookie → compute `sha256(token)`.
  2. Decode the embedded `family_id` (carry it as the second 32-byte segment of the opaque token, or look up by `token_hash` first — see D-12).
  3. `GET auth:session:{user_id}:{family_id}` → if missing OR `refresh_token_hash` doesn't match the presented hash → **suspect**: do NOT 401 yet, fall through to step 4 with the Postgres path so reuse-of-old-family-token correctly fires `family_reuse_detected`.
  4. Open DB tx, `SELECT ... FOR UPDATE` from `refresh_tokens` by `token_hash`. Apply rotation logic + `replaced_by_id` chain checks (D-12). Mint new pair, INSERT new row, UPDATE old row (`replaced_by_id`, `replaced_at`).
  5. Update Redis: `SET auth:session:{user_id}:{family_id}` to new JSON + TTL; `SADD auth:user_sessions:{user_id} {family_id}`.
- **D-12 (Discretion):** **The opaque refresh token does NOT embed `family_id` or `user_id`** — it stays a flat `secrets.token_urlsafe(32)` per Phase 4 D-03. Lookup pattern: `SELECT user_id, family_id, revoked_at, expires_at, replaced_by_id FROM refresh_tokens WHERE token_hash = :h`. The Redis fast-path can't be checked until after the DB lookup tells us `(user_id, family_id)`. Rationale: keeps the token opaque (no info disclosure if logged), avoids parsing concerns, and the Redis fast-path is only an optimization for the hot reuse-window case (D-13) — not the primary gate.
- **D-13 (Discretion):** **Refresh rotation race-window mechanism (AUTH-06) — DB chain + short-lived Redis cache.** Decision was deferred to Claude; the chosen mechanism leverages the `replaced_by_id` column from D-04:
  1. On `/auth/refresh`, after `SELECT ... FOR UPDATE` of the row by `token_hash`, three branches:
     - **Active (`revoked_at IS NULL AND replaced_by_id IS NULL AND expires_at > now()`):** rotate → mint new pair, INSERT new row, UPDATE old (`replaced_by_id = new.id`, `replaced_at = now()`). Cache the new raw pair in Redis at `auth:rotate:{old_token_hash}` for `5s` (`SET ... EX 5 NX`). Return.
     - **Already-replaced within ~5s (`replaced_by_id IS NOT NULL AND replaced_at > now() - interval '5 seconds'`):** look up `auth:rotate:{old_token_hash}` → if hit, return that cached new pair (idempotent same-pair return for parallel callers). Cache miss: fall through to revocation (race window expired between caller and us — extremely unlikely but explicit).
     - **Reuse outside window OR family already revoked:** mark family reuse → `UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = :uid AND family_id = :fid AND revoked_at IS NULL` + delete Redis session keys for that family + structlog `event=family_reuse_detected` + return 401 `family_reuse_detected`.
  2. The 5s constant is derived from `settings.refresh_reuse_window_seconds: int = 5` (new field) so it's tunable without code changes.
- **D-14 (Discretion):** **`/auth/logout` (current session) flow:** read `sz_refresh` from cookie → look up `(user_id, family_id)` → DB `UPDATE refresh_tokens SET revoked_at = now() WHERE family_id = :fid AND revoked_at IS NULL` → Redis `DEL auth:session:{user_id}:{family_id}` + `SREM auth:user_sessions:{user_id} {family_id}` → clear `sz_access` / `sz_refresh` / `sportzal_csrf` cookies via `response.delete_cookie(...)` (matching Path/SameSite of the issuer helper) → structlog `event=session_revoked`. `AUTH-LO-01` satisfied.

### Composition wiring + API surface (claude discretion bucket)

- **D-15 (Discretion):** **`register_user_loader(load_user_by_id)` is called inside `create_app()` after `register_middleware` and before `include_router(api)`.** `load_user_by_id` lives in `app/modules/auth/service.py`: `async def load_user_by_id(session: AsyncSession, user_id: UUID) -> User | None`. `app.main` is exempt from the `core-not-depend-on-modules` import-linter contract (the contract scopes `source_modules = app.core`, not `app.main`) — Phase 4 D-24 already documented this.
- **D-16 (Discretion):** **API prefix flip: `app/api/router.py` mounts `v1` at `prefix="/api/v1"`.** `/healthz` is preserved at the root (Kubernetes liveness convention from Phase 2) by including `health.router` directly on `api` (not on `v1`). Auth router lives at `/api/v1/auth/*`. ROADMAP.md Phase 4 → Phase 5 transition mentioned this flip; Phase 5 owns it because Phase 5 is the first phase with a non-`/healthz` endpoint.
- **D-17 (Discretion):** **Cookie clearing on logout uses a sibling helper `clear_session_cookies(response, *, secure)` in `app/core/security.py`.** Mirrors the `issue_session_cookies` helper from Phase 4 D-25 — same Path/SameSite attributes so browsers actually delete the cookie. `sportzal_csrf` is cleared too because Phase 4 D-26 says it's regenerated on each login/refresh/OTP-verify, so the post-logout state has no CSRF token (frontend will get a fresh one on next login).

### Rate limit (AUTH-EP-03) — claude discretion

- **D-18 (Discretion):** **Fixed-window per-email Redis counter.** Key `ratelimit:login:{email_lower}`; on every failed login (wrong password OR user-not-found): `INCR` + `EXPIRE 900` (15 minutes). If the post-INCR value is >= 5: short-circuit return 429 `rate_limited` BEFORE running Argon2 (still timing-equivalent because the counter check happens BEFORE the user-existence branch and we don't condition on it). Successful login does NOT reset the counter (kept simple — counter expires naturally). Using fixed-window over sliding-window because (a) for a 1-2-user system the boundary effect is irrelevant, (b) sliding-window via sorted set adds 2x ops per hit for no measurable benefit at this scale.
- **D-19 (Discretion):** **Per-email key, NOT per-IP.** Rationale: AUTH-EP-03 says "per email"; per-IP would block coffeeshop networks; per-email+IP would let a single attacker rotate IPs. Phase 5 ships per-email; per-IP is a v1.2+ concern if abuse appears.

### Audit emission strategy (claude discretion bucket)

- **D-20 (Discretion):** **Audit events emit as `structlog` entries with stable `event=` names**, NOT to a DB table (the table lives in Phase 8 — INFRA-04 / AUDIT-01..03). Call sites and event names locked now so Phase 8's DB-row writer can latch on without renaming:
  - `event=login_success` `{user_id, email, ip, user_agent}`
  - `event=login_failed` `{email, reason: 'invalid_credentials' | 'rate_limited', ip}`
  - `event=session_revoked` `{user_id, family_id}`
  - `event=session_revoked_all` `{user_id, family_count}`
  - `event=family_reuse_detected` `{user_id, family_id, presented_token_hash_prefix}` (first 8 hex chars of the hash, never raw)
  - `event=password_changed_revokes_sessions` `{user_id, family_count}` — Phase 5 SC AUTH-LO-03 entry; the password-change endpoint itself is a deferred admin endpoint, but the call site exists for whoever lands it
  - (Phase 7 will add `event=otp_issued`, `event=otp_consumed`)
- **D-21 (Discretion):** **Phase 8 audit-log writer wraps these call sites via a `audit.emit(event, **fields)` helper** that's a no-op in Phase 5 (pure structlog passthrough) and gains a DB INSERT in Phase 8. Phase 5 ships the helper signature in `app/core/audit.py` (or `app/modules/auth/audit.py` — defer to planner) so Phase 8 only changes the implementation, not the call sites.

### Test infrastructure (TEST-01, TEST-02, TEST-04, TEST-08)

- **D-22 [LOCKED]:** **`db_session` fixture upgraded to SAVEPOINT-based per-test rollback.** Current Phase 3 fixture (`apps/backend/tests/conftest.py`) only does session-end rollback. TEST-01 explicitly requires SAVEPOINT-based per-test isolation against real Postgres. Pattern (SQLAlchemy 2.0 cookbook):
  1. Open a connection from the engine.
  2. `BEGIN` outer transaction.
  3. Bind an `AsyncSession` to that connection with `join_transaction_mode="create_savepoint"`.
  4. Yield session.
  5. `ROLLBACK` outer transaction on teardown — wipes everything written during the test, including `COMMIT`s that the service code issued (those become nested savepoints under the outer tx).
- **D-23 [LOCKED]:** **TEST-08 (`alembic upgrade head` then `alembic check`) runs in CI + locally** as `tests/integration/test_alembic_clean.py`. Already exists in skeleton form from Phase 4 (`04-09` plan); Phase 5 keeps the test green after `0001_auth.py` lands — naming convention guarantees deterministic constraint names.
- **D-24 [LOCKED]:** **TEST-02 / TEST-04 are integration tests** under `apps/backend/tests/integration/auth/`. Use existing `async_client` + new SAVEPOINT-based `db_session`. TEST-02 covers login happy/401/429 + cookie-attribute assertions (Path / HttpOnly / SameSite). TEST-04 covers happy rotation, reuse-within-window same-pair return, reuse-outside-window family revocation + `family_reuse_detected` log assertion (use `caplog` + structlog test capture).

### Seed script (AUTH-EP-04)

- **D-25 (Discretion):** **`apps/backend/scripts/seed_demo_data.py` reads `SEED_OWNER_EMAIL` + `SEED_OWNER_PASSWORD` from env**, hashes via `hash_password`, and runs `INSERT ... ON CONFLICT (email) DO NOTHING` (idempotent). Run as `uv run python -m scripts.seed_demo_data`. The compose stack does NOT auto-run it (one-shot operator command, not a service). README updated with the command.

### Cookie + CSRF behavior on /auth/* (no new decisions, just enumeration)

- **D-26 (Discretion):** **`/auth/login` is exempt from CSRF validation** (Phase 6 CSRF-02 will exempt it explicitly); Phase 5 emits all three cookies via Phase 4 `issue_session_cookies(...)`. `/auth/refresh` reissues all three cookies (rotates `sportzal_csrf` per Phase 4 D-26 to invalidate the old value). `/auth/logout` clears all three. `/auth/logout-all` clears all three for the calling browser AND revokes other sessions in DB+Redis (other browsers still have stale cookies but their next request will 401).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock (Python 3.12 + uv + FastAPI + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + structlog), modular-monolith layout, RU/CIS regional constraints, `httpx ASGITransport` + `pytest-asyncio` testing rule.
- `.planning/PROJECT.md` — milestone scope, architectural invariants (`core ⊥ modules`), key decisions table, Out-of-Scope (no multi-tenancy, no stateless-only JWT).
- `.planning/REQUIREMENTS.md` — Phase 5 owns these REQ-IDs (every plan task must trace): `INFRA-03`, `AUTH-05`, `AUTH-06`, `AUTH-07`, `AUTH-EP-01`, `AUTH-EP-02`, `AUTH-EP-03`, `AUTH-EP-04`, `AUTH-EP-05`, `AUTH-LO-01`, `AUTH-LO-02`, `AUTH-LO-03`, `AUTH-LO-04`, `TEST-01`, `TEST-02`, `TEST-04`, `TEST-08`. RBAC enforcement / CSRF / Telegram / clients / OpenAPI / FE belong to Phases 6/7/8/9/10.
- `.planning/ROADMAP.md` Phase 5 section — goal + four numbered success criteria (login + cookies + 429 throttle; refresh rotation + reuse-window same-pair + family revoke; logout + logout-all + /me; SAVEPOINT-based db_session + alembic-clean idempotency).

### Cross-phase context (load-bearing)
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — every Phase 4 D-XX is a Phase 5 input. Especially: D-01 (single secret), D-02 (access claims), D-03 (opaque refresh + sha256), D-04 (HS256 + 30s leeway), D-05 (TTL settings), D-06 (helper signatures), D-07..D-13 (envelope + ProblemDetails), D-15..D-18 (mixins), D-19 (naming convention), D-21..D-23 (RBAC), D-24 (CurrentUser Protocol + register_user_loader slot — Phase 5 fills it), D-25 (issue_session_cookies), D-26 (CSRF token rotation), D-27/D-28 (Argon2 timing + InvalidPassword).
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-VERIFICATION.md` — confirms what shipped and what didn't (the gate tests passed → Phase 5 can rely on those primitives).
- `.planning/phases/03-tests-dev-infrastructure-documentation/03-CONTEXT.md` — D-08 (testing conventions), D-10/D-11 (`app` / `async_client` / `db_session` fixtures — D-22 above replaces the rollback strategy), D-12 (compose Postgres pattern), D-15 (`asgi-lifespan` already in dev-deps).
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-CONTEXT.md` — D-06/D-07/D-08 (lifespan-managed engine + factory pattern — Phase 5's `redis_lifespan` follows this), D-12/D-13 (AppError hierarchy → InvalidPassword/InvalidAccessToken/RateLimited already added in Phase 4), D-15 (Settings shape — Phase 5 adds `refresh_reuse_window_seconds`).

### Research files
- `.planning/research/STACK.md` — dependency choices, `redis>=5,<6` recommendation, reject list (`fastapi-csrf-protect`, `passlib`, `python-jose`, `aiogram`).
- `.planning/research/ARCHITECTURE.md` — file-and-function-level layout for `app/modules/auth/*`, refresh-rotation pseudocode, Redis key schema reference.
- `.planning/research/PITFALLS.md` — directly relevant to Phase 5: #1 (SameSite for Telegram return — already mitigated by D-25/D-26 of Phase 4), #5 (refresh stored hashed — D-03), #7 (parallel-refresh races — AUTH-06 / D-13), #11 (Alembic naming — Phase 4 D-19), #14 (Argon2 timing equivalence — Phase 5 sentinel-hash on user-not-found).
- `.planning/research/SUMMARY.md` — synthesis of merged build order; Phase 5 = "Email/Password Auth" / Phase 2 in research nomenclature.
- `.planning/research/FEATURES.md` — table-stakes for the milestone (login, refresh, logout).

### Source files Phase 5 directly reads or mutates
- `apps/backend/app/main.py` — extend `create_app()` with `redis_lifespan` chain + `register_user_loader(load_user_by_id)` call.
- `apps/backend/app/api/router.py` — flip prefix to `/api/v1` for v1 router; preserve `/healthz` at root.
- `apps/backend/app/api/v1/router.py` — include `auth_router` with `prefix="/auth"` + `tags=["auth"]`.
- `apps/backend/app/core/redis.py` — NEW. `redis_lifespan`, `get_redis` dependency.
- `apps/backend/app/core/config.py` — extend `Settings` with `refresh_reuse_window_seconds: int = 5`. Document in `.env.example`.
- `apps/backend/app/core/security.py` — already has `issue_session_cookies`; add `clear_session_cookies(response, *, secure)` (D-17).
- `apps/backend/app/core/audit.py` — NEW (or `app/modules/auth/audit.py`, planner's call). `emit(event: str, **fields) -> None` — Phase 5 passes through to structlog; Phase 8 adds DB write.
- `apps/backend/app/modules/auth/models.py` — fill out `User`, `RefreshToken`, `OtpCode` ORM models per D-03/D-04/D-06.
- `apps/backend/app/modules/auth/schemas.py` — fill `LoginRequest`, `LoginResponse` (`{user: {id, role, fullName}}`), `MeResponse` (`{id, role, fullName, email, hasTelegram}`). All extend Phase 4 `RequestContract` / `ResponseData`. Use `ResponseEnvelope[T]` on every endpoint.
- `apps/backend/app/modules/auth/service.py` — fill `load_user_by_id`, `authenticate(email, password)`, `issue_tokens(user)`, `rotate_refresh(token)`, `revoke_session(family_id)`, `revoke_all_sessions(user_id)`. Service is the SQL+Redis seam.
- `apps/backend/app/modules/auth/router.py` — fill `/login`, `/refresh`, `/logout`, `/logout-all`, `/me`. Each endpoint declares `response_model=ResponseEnvelope[X]`. `/login` and `/refresh` are CSRF-exempt (Phase 6 wires the dependency).
- `apps/backend/app/modules/auth/rate_limit.py` (or inline in service) — `check_login_rate(email)` per D-18.
- `apps/backend/alembic/versions/0001_auth.py` — NEW. Creates `users`, `refresh_tokens`, `otp_codes` per D-03/D-04/D-06.
- `apps/backend/scripts/seed_demo_data.py` — NEW. Owner upsert per D-25.
- `apps/backend/.env.example` — add `REFRESH_REUSE_WINDOW_SECONDS=5`, `SEED_OWNER_EMAIL=`, `SEED_OWNER_PASSWORD=`.
- `apps/backend/pyproject.toml` — add `redis>=5,<6`; `uv lock` regenerated.
- `apps/backend/tests/conftest.py` — upgrade `db_session` per D-22 (SAVEPOINT-based per-test rollback).
- `apps/backend/tests/integration/auth/test_login.py` — NEW. TEST-02.
- `apps/backend/tests/integration/auth/test_refresh.py` — NEW. TEST-04 + race-window same-pair test + family-reuse revocation test.
- `apps/backend/tests/integration/auth/test_logout.py` — NEW. AUTH-LO-01..04.
- `apps/backend/tests/integration/test_alembic_clean.py` — keep green after `0001_auth.py` (TEST-08).

### Frontend reference (READ-ONLY in Phase 5)
- `apps/admin-web/src/shared/api/services/mock/auth.ts` (or wherever the existing mock auth lives) — reference for the response shape the frontend currently expects. Phase 5 backend is the new source of truth; Phase 10 will reconcile the mock.
- `apps/admin-web/src/shared/session/registry.ts` + `can.ts` — read-only confirmation that `Role` / `Resource` strings still byte-match (Phase 4 already locked this; no change in Phase 5).

### External docs (consulted)
- PyJWT docs (https://pyjwt.readthedocs.io/) — already used in Phase 4.
- argon2-cffi docs (https://argon2-cffi.readthedocs.io/) — `verify` + `check_needs_rehash`.
- redis-py asyncio docs (https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) — `Redis.from_url`, pipeline, `decode_responses`.
- SQLAlchemy 2.0 "Joining a session into an external transaction" cookbook — for the SAVEPOINT-based `db_session` (D-22).
- OWASP Authentication Cheat Sheet 2024 — refresh-token rotation pattern + family revocation on reuse.
- NIST 800-63B 2024 — 12-char password min, no complexity, no rotation, no lockout (rate-limit instead).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (Phase 4 outputs that Phase 5 consumes verbatim)
- `app/core/security.py:encode_access_token` / `decode_access_token` / `generate_refresh_token` / `generate_otp_code` / `generate_deep_link_token` / `generate_csrf_token` / `hash_password` / `verify_password` / `issue_session_cookies` — every auth flow in Phase 5 uses these helpers.
- `app/core/dependencies.py:CurrentUser` Protocol — `User` ORM model (D-06) satisfies it (declares `id: Mapped[UUID]`, `role: Mapped[Role]`).
- `app/core/dependencies.py:register_user_loader` / `get_current_user` / `require_permission` — Phase 5 calls `register_user_loader` from `create_app()` (D-15). `get_current_user` is used by `/auth/me` (and by `/auth/logout` / `/auth/logout-all` to know who's calling). `require_permission` is NOT used by Phase 5 routes (RBAC enforcement is Phase 6).
- `app/core/exceptions.py:InvalidAccessToken` / `InvalidPassword` / `RateLimited` / `ForbiddenError` — Phase 5 raises these from auth flows.
- `app/core/database.py:Base` (with `MetaData(naming_convention=...)`) + `UUIDPkMixin` + `TimestampMixin` — `User`, `RefreshToken`, `OtpCode` models all compose these.
- `app/core/schemas.py:RequestContract` / `ResponseData` / `ResponseEnvelope[T]` / `ProblemDetails` — every Phase 5 schema subclasses these.
- `app/core/permissions.py:Role` — `User.role` column maps via `Enum(Role, native_enum=False, length=16)` (D-07).
- `app/core/middleware.py:RequestIdMiddleware` — emits `x-request-id`; structlog audit events automatically include it via `app.core.logging` config.
- `app/core/config.py:Settings` — already has `secret_key`, `redis_url`, `access_token_ttl_seconds`, `refresh_token_ttl_seconds`, `cookie_secure`. Phase 5 adds `refresh_reuse_window_seconds: int = 5`.

### Established patterns to honor
- **Factory pattern, no module-level `app`** (Phase 2 main.py docstring) — `register_user_loader` lands inside `create_app()` body, not at module load.
- **Lifespan-managed connections** (Phase 2 D-06/D-08) — `redis_lifespan` follows the same shape as `db_lifespan`. Compose them in `create_app(lifespan=combined_lifespan)` via `contextlib.asynccontextmanager` chain.
- **`core ⊥ modules`** (importlinter) — `app.core.audit`, `app.core.redis`, `app.core.dependencies` MUST NOT import from `app.modules.*`. The `register_user_loader(load_user_by_id)` call in `app.main` is the boundary crossing — `app.main` is the composition root.
- **PEP 695 generics** — established (Phase 4 D-11). Phase 5 schemas use `ResponseEnvelope[LoginResponse]`, etc.
- **Russian-narrative + English-code docs style** (Phase 3 D-05) — PLAN.md / SUMMARY.md narrative in Russian, code in English.
- **AppError handler shape** (`{code, message, fields?}`) — Phase 5 errors all extend `AppError`; the existing handler in `app/core/exceptions.py` Just Works.
- **No `tenant_id`, no multi-tenancy** — `User` has no tenant FK. Permanent constraint per PROJECT.md OoS.

### Integration points
- **Phase 6 (RBAC Wiring)** — adds `Depends(require_permission(...))` to clients/users management routes; the parity test reads `app.core.permissions.OWNER_ONLY` (Phase 4) + frontend `can.ts`. Phase 6 also wires `verify_csrf` on POST/PATCH/DELETE; Phase 5 routes will retroactively pick that up except where exempted (`/auth/login` and `/auth/refresh`).
- **Phase 7 (Telegram OTP)** — extends `/auth/*` with `/auth/telegram/start|status|verify`; uses `OtpCode` table that Phase 5 ships in final shape; uses Phase 5 `issue_session_cookies` + Redis session pattern verbatim. Telegram bot worker writes OTP codes through ARQ → `OtpCode.code_hash` set on bind.
- **Phase 8 (Clients + Audit Log)** — adds `audit_log` table; `app.core.audit.emit(...)` (D-21) gains a DB INSERT. Phase 8 also adds `clients.created_by_user_id` FK ON DELETE RESTRICT → users.id.
- **Phase 9 (OpenAPI)** — `/auth/*` routes already declare `response_model=ResponseEnvelope[X]` so OpenAPI export captures them. `ProblemDetails` shows up as the 4xx schema for InvalidPassword / InvalidAccessToken / RateLimited / ForbiddenError.
- **Phase 10 (FE wiring)** — `apps/admin-web/src/shared/api/services/http/auth.ts` calls `/api/v1/auth/login`, etc. Frontend mocks reconciled with the new `ResponseEnvelope[T]` shape.

</code_context>

<specifics>
## Specific Ideas

- **DB-led rotation chain (D-13) is the canonical race-window mechanism.** The Redis cache `auth:rotate:{old_token_hash}` for 5s is an *optimization* on top of the DB chain, not the source of truth. Even if Redis flushes, the DB's `replaced_by_id` chain + `replaced_at` timestamp means the second of two parallel callers can recover the right answer. Do NOT propose pure-Redis race-window mechanisms — they lose correctness on Redis eviction.
- **`OtpCode` final shape NOW (D-03) is intentional even though Phase 7 owns the flow.** The user explicitly wanted "one migration tells one story" inverted here: INFRA-03 already obliges us to create `otp_codes` in `0001_auth.py`, and an empty placeholder column set is strictly worse than the final shape. Phase 7's job is then app code only — no schema churn, no migration ordering risk.
- **`User.full_name` single column (D-01) is a deliberate departure from `clients` ФИО triple.** Operators ≠ clients; the domains are distinct, and 1-2 operator rows don't justify the boilerplate of three columns + composition logic on `/auth/me`. Do NOT propose unifying these "for consistency" later — the consistency is at the contract boundary (`fullName` field), not the schema boundary.
- **`User` has NO `SoftDeleteMixin` (D-05).** Operators are 1-2 people; hard-delete is fine. `ON DELETE RESTRICT` on `clients.created_by_user_id` (Phase 8) protects against accidental orphans. Do NOT add `deleted_at` to users "to match the pattern" — the pattern is contextual.
- **Redis is authoritative for the fast path, NOT for state changes (D-11).** Every state-changing operation (rotate, revoke, logout-all) acquires a DB row lock first; Redis is updated as a follower. This means a Redis flush during ops is recoverable (DB has the truth) but a DB-without-Redis state results in a degraded but correct experience (every refresh hits Postgres). NEVER propose Redis-as-source-of-truth for `revoked_at` or `replaced_by_id`.
- **Audit emission is structlog-now, DB-later (D-20/D-21).** The call sites + event names are LOCKED in Phase 5 so Phase 8's DB writer is a swap-in, not a rewrite. Don't invent new event names in Phase 5 — they're contracts.
- **Per-email rate limit, not per-IP (D-19).** The user is on RU/CIS — coffee-shop / mobile-CGNAT / corporate-NAT addresses are common shared egress points. Per-IP would block legitimate operators sharing networks; per-email is the AUTH-EP-03 letter and the safe default.
- **API prefix flip is Phase 5's responsibility (D-16), not deferred further.** Phase 4 explicitly punted this with a `# TODO Phase B+`; Phase 5 is "Phase B+" because it's the first phase with a non-`/healthz` endpoint. Reconciling `/healthz` to stay at root preserves the Kubernetes liveness contract.
- **`refresh_reuse_window_seconds: int = 5` (D-13) is env-tunable**, not a module constant. Same rationale as Phase 4 D-05 — staging/prod operators can tune without code edits if a real workload shows the 5s window is wrong.

</specifics>

<deferred>
## Deferred Ideas

- **Telegram OTP flow** (`/auth/telegram/start|status|verify`, bot worker process) — Phase 7. Phase 5 ships the `otp_codes` table in final shape but no app code touches it.
- **`Depends(require_permission(...))` on routes + parity test + introspection test** — Phase 6 (RBAC-02..05, TEST-05..07).
- **`Depends(verify_csrf)` on POST/PATCH/DELETE routes** — Phase 6 (CSRF-02). Phase 5 emits the CSRF cookie via `issue_session_cookies` but does not validate.
- **`audit_log` DB table + `audit.emit(...)` → DB INSERT swap-in** — Phase 8 (INFRA-04, AUDIT-01..03). Phase 5 ships call sites + structlog passthrough.
- **Active-sessions UI / device list / per-session revoke** — v1.2 (AUTH-V12-01). Redis JSON value (D-09) does NOT include `ip` / `user_agent` because that's a v1.2 concern.
- **Password reset via Telegram bot DM** — v1.2 (AUTH-V12-02). Phase 5 has no public reset endpoint (admin-only password change is also deferred — the call site for `password_changed_revokes_sessions` exists for whoever lands the admin endpoint).
- **HaveIBeenPwned check on registration / password change** — v1.2 (AUTH-V12-03).
- **Webhook-based Telegram bot mode** — v1.2 (AUTH-V12-04).
- **Public self-registration** — explicit OoS (PROJECT.md). Forever.
- **JWT secret split into access/refresh secrets** — Phase 4 D-01 deferred this; still deferred. `secret_key` is shared.
- **`jti` / `iss` / `aud` claims on access tokens** — Phase 4 D-02 deferred this; still deferred.
- **Per-IP rate limit, captcha, Turnstile** — v1.2+ if abuse appears.
- **Sliding-window rate limit via Redis sorted set** — D-18 chose fixed-window for simplicity; sliding-window is a mechanical upgrade if the boundary effect ever bites.
- **`is_active` / `email_verified` / `last_login_at` on User** — D-06 omitted them. Resurrect if/when the use case emerges; `last_login_at` will live in `audit_log` (Phase 8) anyway.
- **Native Postgres enum for `User.role`** — D-07 chose CHECK constraint; native enum is a v2+ refactor if the role set grows beyond two static values (which PROJECT.md says it never will).
- **Admin-only password-change endpoint + revoke-all-on-password-change** — deferred admin endpoint. The call site exists in Phase 5 (`event=password_changed_revokes_sessions`) but no route ships.
- **`pg_trgm` extension + `clients` partial unique index** — Phase 8 (INFRA-04, CLIENTS-02).

</deferred>

---

*Phase: 05-user-schema-email-password-auth*
*Context gathered: 2026-05-02*
