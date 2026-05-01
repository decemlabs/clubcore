# STACK Research: v1.1 Auth + Clients

**Researched:** 2026-05-01
**Mode:** Project Research — incremental dependencies only
**Overall confidence:** HIGH (versions verified against PyPI/npm 2026-05-01)

## Executive Summary

The v1.0 lockfile already covers ~80% of v1.1's needs (FastAPI, SQLAlchemy async, redis 5.3.1 transitively via arq, httpx, structlog, ARQ). Five new Python packages and two new JS packages are needed. Two libraries are explicitly rejected: **passlib** (5+ years without release; bcrypt 5.0 broke its compat shim) and **python-jose** (107 open issues, sluggish maintenance, cryptography pin churn). Telegram client choice splits on transport: **python-telegram-bot 22.7** uses httpx (already locked) and integrates cleanly with FastAPI's loop; aiogram pulls in aiohttp as a parallel HTTP stack. Frontend: pin **openapi-typescript 7.13.0** for codegen + a hand-rolled fetch wrapper (no `openapi-fetch` — it would compete with TanStack Query conventions in `services/http/`).

---

## 1. Telegram Bot Client

**Recommendation: `python-telegram-bot >= 22.7`**

| Criterion | python-telegram-bot 22.7 | aiogram 3.27.0 | pyrogram | raw httpx |
|---|---|---|---|---|
| HTTP transport | **httpx >=0.27,<0.29** (matches our stack) | aiohttp (parallel stack) | own MTProto | manual |
| Active maintenance | Yes (release 2026-03-16) | Yes (2026-04-03) | Slowing | n/a |
| Coexists with ARQ worker | Yes — separate asyncio task or its own ARQ-managed process | Yes, but adds aiohttp event-loop quirks | Heavy | DIY |
| One-time-code verification (no polling) | Trivial (`Bot.send_message`) | Trivial | Overkill | OK |
| Long-polling for inbound `/start <token>` | First-class via `Application.run_polling()` | First-class via `Dispatcher.start_polling()` | Yes | DIY |
| Webhook option later | Yes | Yes | Limited | DIY |
| Type hints / mypy strict | Good (PEP 561 since v20) | Good | Weak | n/a |

**Why python-telegram-bot over aiogram:** transport coherence. Our backend already uses httpx for outbound HTTP; ptb piggybacks on that, avoiding a second async HTTP stack (aiohttp) inside the same process. ptb 22.x is current (March 2026), v22 dropped Python 3.8, requires httpx, and is type-friendly.

**Reject:** `pyrogram` (uses Telegram MTProto API — overkill for a bot, requires `api_id/api_hash` user app credentials), `raw httpx` (re-implements update parsing, retries, parameter-encoding edge cases for free).

**Integration cost:** LOW — single new dep. Run mode: separate ARQ worker process or a dedicated `python -m app.workers.telegram` entrypoint launched by docker-compose. Do **not** run polling inside the FastAPI ASGI app.

**Place in codebase:**
- `app/integrations/telegram/client.py` — synchronous send-helper functions (one-time codes, deep-link generation) used by `app/modules/auth/service.py`.
- `app/workers/telegram_bot.py` — `Application.builder().token(...).build()` long-poller for `/start <token>`; on incoming code, calls into a public function from `app/modules/auth/service.py`.
- Import-linter contract `integrations ⊥ modules` is preserved if module imports the integration (not the reverse). The bot worker is in `workers/`, allowed to import both.

**Versions to pin:** `python-telegram-bot>=22.7,<23` (semver-stable since v20).

---

## 2. JWT Library

**Recommendation: `PyJWT >= 2.12.1`**

| Criterion | PyJWT 2.12.1 | python-jose 3.5.0 | authlib 1.7.0 |
|---|---|---|---|
| Maintenance | Active (push 2026-04-27) | Active but 107 open issues, lagging cryptography releases | Active, broader OAuth focus |
| Pure JWT scope | Yes — minimal API surface | Yes — but JOSE-wide (JWS/JWE/JWK) you don't need | Sprawling (OAuth1/2 server+client) |
| Type hints / mypy strict | Yes (py.typed) | Partial; some Stubs gaps | Partial |
| FastAPI tutorial uses it | OAuth2PasswordBearer doc switched to PyJWT (2024) | Deprecated in tutorial | n/a |

**Why PyJWT over python-jose:** the 107-issue python-jose backlog includes critical-path items like cryptography pins lagging by major versions; the FastAPI security tutorial migrated off python-jose to PyJWT in 2024. Authlib is a fine library but its scope (OAuth provider/client framework) is overkill — we hand-roll access/refresh in `auth/service.py` and call `jwt.encode`/`jwt.decode` directly.

**Reject:** `python-jose` (maintenance lag, dependency drift), `authlib` (scope creep).

**Place in codebase:**
- `app/core/security.py` — `encode_access(sub, role) -> str`, `encode_refresh(sub, family_id) -> str`, `decode(token) -> Claims` (Pydantic model). Uses `HS256` against `settings.jwt_secret`. Refresh rotation = generate new family member, mark old `jti` revoked in Redis set `auth:revoked:{family_id}`.
- `app/api/dependencies.py` — `current_subject = Depends(get_current_subject)` extracts cookie, calls decode, looks up user via `app/modules/auth`.

**Versions to pin:** `pyjwt>=2.12.1,<3` (extras: `pyjwt[crypto]` only if you switch to RS256; for HS256 not needed).

---

## 3. Password Hashing

**Recommendation: `argon2-cffi >= 25.1.0`** — direct, no passlib wrapper.

| Criterion | argon2-cffi 25.1.0 | bcrypt 5.0.0 (direct) | passlib 1.7.4 |
|---|---|---|---|
| Last release | 2025+ | 2024+ | **2020-10-08** (5.5 years stale) |
| OWASP 2026 default | **Argon2id** | bcrypt acceptable, second choice | n/a |
| Async-safe | Yes (cffi releases GIL); wrap in `asyncio.to_thread` for >50ms hashes | Same | Same |
| Type hints / mypy strict | py.typed | py.typed | None |
| Compat with bcrypt 5.0 | n/a | n/a | **Broken** — passlib's bcrypt backend reads `bcrypt.__about__.__version__` which 5.0 removed |

**Why argon2-cffi over bcrypt:** OWASP's 2026 password-storage cheat sheet recommends Argon2id as the default; bcrypt is the secondary fallback. Argon2id has memory-hardness (resists GPU/ASIC attacks).

**Reject explicitly:**
- **`passlib`** — no release since 2020-10-08; bcrypt 5.0 backend is broken. Do **not** add `passlib` even as a "convenience wrapper."
- **`bcrypt` direct** — works, but Argon2id is the modern default.

**Place in codebase:**
- `app/core/security.py` — `hash_password(pw: str) -> str`, `verify_password(pw: str, hashed: str) -> bool`. Wrap calls in `await asyncio.to_thread(...)` from `auth/service.py` because Argon2id default params (~50ms) shouldn't block the event loop.

**Versions to pin:** `argon2-cffi>=25.1.0,<26`.

---

## 4. Frontend OpenAPI Codegen

**Recommendation: `openapi-typescript@^7.13.0`** as a `devDependency` in `packages/api-client`. **Hand-roll the fetch wrapper.** Do **not** add `openapi-fetch`.

| Tool | Verdict |
|---|---|
| `openapi-typescript` 7.13.0 | **Adopt** — generates `paths`/`components` types only, no runtime, no client classes |
| `openapi-fetch` 0.17.0 | **Reject** — duplicates the `services/http/` swap-seam wrapper convention |
| `openapi-generator-cli` (Java) | **Reject** — heavy, opinionated client classes |
| `orval` | **Reject** — generates React Query hooks; clashes with hand-written `xKeys` factories |

**Why openapi-typescript over openapi-fetch:** the architectural rule is _"`UI → TanStack Query hook → services.X → { mock | http } impl`"_. Hooks own keys, optimistic updates, error mapping — that's the project's contract. `openapi-fetch` would be a parallel data layer; `openapi-typescript` only contributes **types**, leaving the swap seam intact.

**Recommended config:**
```bash
openapi-typescript ../backend/openapi.json -o src/generated/schema.ts \
  --enum --alphabetize --immutable --root-types --properties-required-by-default
```

**CI drift check:** `pnpm --filter @sportzal/api-client run codegen && git diff --exit-code packages/api-client/src/generated/schema.ts` — runs after backend writes `apps/backend/openapi.json` (FastAPI: `app.openapi()` dumped in a `make export-openapi` target).

**Place in codebase:**
- `packages/api-client/src/generated/schema.ts` — generated, committed for CI drift visibility.
- `packages/api-client/src/client.ts` — hand-rolled `request<P, M>(...)` wrapper.
- `apps/admin-web/src/shared/api/services/http/{auth,clients}.ts` — implements the contracts using `@sportzal/api-client`.

**Versions to pin:** `openapi-typescript@^7.13.0` (devDependency).

---

## 5. CSRF for Cookie-Based JWT

**Recommendation: Double-submit cookie + custom header — DO NOT add `fastapi-csrf-protect`.**

**Why hand-rolled over fastapi-csrf-protect:** the requirement is small (one cookie write at `/auth/login`, one header check on mutating endpoints), library overhead isn't justified. Standard double-submit pattern: on login, set non-httpOnly `sportzal_csrf` cookie (random 32-byte hex); a `Depends(verify_csrf)` on every state-mutating route compares the cookie value with the `X-CSRF-Token` header (timing-safe).

**Cookie flags (locked decisions):**
- Access JWT: `HttpOnly, Secure, SameSite=Lax, Path=/, Max-Age=900` (~15min).
- Refresh JWT: `HttpOnly, Secure, SameSite=Lax, Path=/api/v1/auth, Max-Age=2592000` (~30d). Path-scoping reduces exposure.
- CSRF: `Secure, SameSite=Lax, Path=/, Max-Age=2592000`, **NOT** HttpOnly (frontend must read it).

**Place in codebase:**
- `app/api/dependencies.py` — `verify_csrf(...)` raises `HTTPException(403)` on mismatch. Applied via router-level `dependencies=[Depends(verify_csrf)]` on POST/PATCH/DELETE routes (skip for `/auth/login` itself).
- `apps/admin-web/src/shared/api/services/http/client.ts` — fetch wrapper auto-injects `X-CSRF-Token` from `document.cookie`.

---

## 6. Redis Client / Connection Pool

**Recommendation: Use existing `redis>=5.0` (resolved 5.3.1 in uv.lock); share one `redis.asyncio.Redis` pool between FastAPI and ARQ; do not add a second Redis package.**

**Findings:**
- ARQ 0.28 declares `redis[hiredis]<6,>=4.2.0` — already pulls in redis-py.
- `apps/backend/uv.lock` resolves `redis 5.3.1`.
- redis-py 7.x is **too new** for arq 0.28 (`<6` upper bound) — keep at 5.x until arq lifts the cap.
- `aioredis` is dead (merged into redis-py 4.2+).

**Connection pool sharing strategy:**
- ARQ owns its own pool (created internally from `RedisSettings`).
- FastAPI gets a dedicated `redis.asyncio.Redis(connection_pool=ConnectionPool.from_url(REDIS_URL, max_connections=20, decode_responses=True))` built in `app/core/lifespan.py`, exposed via `app.state.redis`.
- Two pools (one for ARQ workers, one for the API process) is **correct** — they're separate Python processes when deployed.
- **Separate key prefixes**: `arq:*` for ARQ internals (default), `auth:revoked:*` and `auth:session:*` for our auth state.

**Place in codebase:**
- `app/core/lifespan.py` — `app.state.redis = Redis.from_url(settings.redis_url, max_connections=20, decode_responses=True)`; close on shutdown.
- `app/api/dependencies.py` — `def get_redis(request: Request) -> Redis: return request.app.state.redis`.
- `app/modules/auth/service.py` — uses Redis for: (a) one-time-code TTL store (`auth:otc:{code}` → `user_id`, TTL 300s), (b) refresh-family revocation set (`auth:revoked:{family}` SADD jti), (c) optional session listing.

**Versions to pin:** keep current `redis>=5.0`; **do not bump to >=7** until arq lifts its `<6` cap.

---

## Final Dependency Diff

### `apps/backend/pyproject.toml` — add to `[project].dependencies`:

```toml
"python-telegram-bot>=22.7,<23",
"pyjwt>=2.12.1,<3",
"argon2-cffi>=25.1.0,<26",
```

### `packages/api-client/package.json` — add to `devDependencies`:

```json
"openapi-typescript": "^7.13.0"
```

### Reject list (do NOT add):

| Library | Reason |
|---|---|
| `passlib` | No release since 2020; bcrypt 5.0 broke its compat shim |
| `python-jose` | 107 open issues, slow on `cryptography` releases |
| `authlib` | Scope creep — full OAuth provider/client; we hand-roll JWT |
| `pyrogram` | MTProto user-API client; overkill for a bot |
| `aiogram` | Pulls aiohttp as parallel HTTP stack |
| `aioredis` | Dead — merged into redis-py 4.2+ |
| `fastapi-csrf-protect` | Single-maintainer wrapper around 30 LOC of stdlib |
| `openapi-fetch` | Competes with `services/http/` swap-seam convention |
| `openapi-generator-cli` / `orval` | Generate clients/hooks that conflict with TanStack Query keys-factory pattern |

---

## Roadmap Implications

- **Phase 01 (Auth scaffolding):** add the 3 Python deps + 1 JS dep upfront, before any business code. Re-run `uv lock` and `pnpm install` as a single atomic commit.
- **Phase 02 (auth endpoints):** Telegram bot worker added to `docker-compose.yml` as a fourth service (`bot`) alongside `web` / `worker` / `migrate`.
- **Phase 03 (clients CRUD):** no new deps; consumes the auth dependencies via `Depends(require_permission(action, resource))`.
- **Phase 04 (frontend wiring):** `packages/api-client` first real code; `openapi-typescript` codegen wired into `pnpm codegen` script with the CI drift check.

## Open Questions / Gaps

1. **OpenAPI export step:** how does the backend dump `openapi.json` for codegen? Options: (a) one-shot `python -m app.cli export-openapi > openapi.json` (preferred, no live server needed), (b) hit `/openapi.json` of a running container in CI. Pick (a) — added to `app/cli.py` in Phase 01.
2. **CSRF on Telegram deep-link callback:** the `/auth/telegram/callback` endpoint can't require CSRF because it's hit by the bot worker (server-side), not the browser. Mark it as the only POST without `Depends(verify_csrf)` — document this exception explicitly.
3. **mypy stubs for PyJWT:** PyJWT 2.12 ships `py.typed`; `types-pyjwt` should be unnecessary. Verify on first `mypy --strict` run; add only if needed.
4. **redis-py upper bound:** track arq issue tracker for the `<6` cap. When arq supports redis-py 6+, bump together.
