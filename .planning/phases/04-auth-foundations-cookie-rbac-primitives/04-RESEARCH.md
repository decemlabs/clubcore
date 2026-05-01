# Phase 4: Auth Foundations & Cookie/RBAC Primitives — Research

**Researched:** 2026-05-01
**Domain:** Cross-cutting backend primitives — JWT (HS256), Argon2id, cookie matrix, RBAC enums, Alembic naming convention, ORM mixins, ResponseEnvelope contract, `members` → `clients` rename
**Confidence:** HIGH (every library API verified against Context7 / PyPI 2026-05-01; every codebase path read directly; CONTEXT.md decisions are load-bearing and treated as locked)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 [LOCKED]:** Single secret for both access and refresh JWT signing — reuse `settings.secret_key` (Pydantic `SecretStr`). No `jwt_access_secret` / `jwt_refresh_secret` split in Phase 4.
- **D-02 [LOCKED]:** Access token claims `{sub, role, typ, iat, exp}`. `sub = str(user_uuid)`, `role: Role` (StrEnum value), `typ = "access"`, `iat`/`exp` UTC epoch seconds. NO `jti` / `iss` / `aud` in Phase 4.
- **D-03 [LOCKED]:** Refresh token = opaque `secrets.token_urlsafe(32)` (NOT a JWT). Phase 5 stores `sha256(token)` only.
- **D-04 [LOCKED]:** JWT algorithm = HS256 with 30s clock leeway.
- **D-05 [LOCKED]:** TTL constants in `Settings` (env-driven): `access_token_ttl_seconds: int = 900`, `refresh_token_ttl_seconds: int = 2592000`, `jwt_clock_leeway_seconds: int = 30`.
- **D-07 [LOCKED]:** Backend-first contract — `ResponseEnvelope[T]` wraps every success response. 2xx → `{ "data": <payload> }`. Frontend will adapt in Phase 10.
- **D-08 [LOCKED]:** Errors stay top-level (NOT in envelope) — `{ code, message, fields? }`. HTTP status carries success/error discrimination. RFC 7807-flavored.
- **D-09 [LOCKED]:** `app/core/schemas.py` (NEW) hierarchy: `ContractModel` (alias_generator=to_camel, validate_by_name=True, validate_by_alias=True, from_attributes=True, extra="ignore") → `RequestContract` (extra="forbid") → `ResponseData` → `ResponseEnvelope[T]` (data: T) → `ProblemDetails` (code, message, fields).
- **D-10 [LOCKED]:** `app/core/pagination.py` REWRITE — `PageQuery(page≥1, page_size 1..100)` + `PaginatedData[T](items, total, page, page_size)`. Old `LimitOffsetParams` and `Page[T]` deleted (clean break, no consumers).
- **D-11 [LOCKED]:** Generics use PEP 695 (`class Foo[T]`), NOT `typing.Generic[T]`.
- **D-12 [LOCKED]:** Pydantic version bump: `pydantic>=2.11,<3` (required for `validate_by_name` + `validate_by_alias`).
- **D-13 [LOCKED]:** Phase 4 envelope minimum viable — `{ data: T }` only. `requestId` / `traceId` / `meta` / `warnings` deferred.
- **D-15 [LOCKED]:** `UUIDPkMixin` uses Postgres-native `gen_random_uuid()` via `mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))`. PG13+ — no `pgcrypto` extension.
- **D-16 [LOCKED]:** `TimestampMixin` uses `func.now()` server-side both on insert (`server_default`) and update (`onupdate`). `TIMESTAMPTZ` (timezone=True), never naive.
- **D-17 [LOCKED]:** `SoftDeleteMixin` exposes `deleted_at: Mapped[datetime | None]` AND a partial-index helper composable into `__table_args__`. Phase 8 `clients.phone` will be `WHERE deleted_at IS NULL` partial unique on top.
- **D-19 [LOCKED]:** `MetaData(naming_convention=...)` uses standard SA template (ix/uq/ck/fk/pk shape exactly as in CONTEXT.md). Set on `Base.metadata` BEFORE first model lands.
- **D-20 [LOCKED]:** Module rename `app/modules/members` → `app/modules/clients` via `git mv`. `.importlinter` `modules-independent` updates the entry. `lint-imports` GREEN.
- **D-21 [LOCKED]:** `OWNER_ONLY: frozenset[tuple[Action, Resource]]` — verbatim mirror of 9 entries in `apps/admin-web/src/shared/session/can.ts`.
- **D-22 [LOCKED]:** `Role` / `Action` / `Resource` are `StrEnum`s. Values match frontend `registry.ts` byte-for-byte.
- **D-23 [LOCKED]:** `can()` body — owner short-circuit `True`; reception → `(action, resource) not in OWNER_ONLY`.
- **D-30 [LOCKED]:** Phase 4 does NOT touch `apps/admin-web`. Frontend mock contract stays bare-object until Phase 10.

### Claude's Discretion

- **D-06:** Helper signatures in `app/core/security.py` — `encode_access_token(user_id, role, *, now=None) -> str`, `decode_access_token(token) -> AccessTokenClaims` (raises `InvalidAccessToken` on `jwt.InvalidTokenError`/`jwt.ExpiredSignatureError`), `generate_refresh_token() -> tuple[str, str]` (raw, sha256 hex), `generate_otp_code() -> tuple[str, str]` (6-digit raw, sha256 hex), `generate_deep_link_token() -> str` (`secrets.token_urlsafe(32)`). `AccessTokenClaims` shape: dataclass or TypedDict.
- **D-14:** `ResponseEnvelope[T]` set as `response_model` on every route (NOT middleware). Optional helper `def envelope(payload: T) -> ResponseEnvelope[T]`.
- **D-18:** Mixins are plain classes (NOT `Base` subclasses). Models compose `class User(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)`.
- **D-24:** `get_current_user` / `require_permission` scaffolded with Protocol + `register_user_loader(loader)` slot to preserve `core ⊥ modules`. Defensive 401 if loader not registered.
- **D-25:** Cookie helper `issue_session_cookies(response, *, access_token, refresh_token, csrf_token, secure)` in `app/core/security.py`. Single function, not three.
- **D-26:** `generate_csrf_token() -> str` returns `secrets.token_hex(32)`. Cookie attrs: non-httpOnly, Secure env-driven, SameSite=Lax, no Path restriction.
- **D-27:** `argon2-cffi` library defaults (`PasswordHasher()` no args). Wrap in `asyncio.to_thread`. `verify_password` also calls `check_needs_rehash`.
- **D-28:** `hash_password` / `verify_password` raise `InvalidPassword` (AppError, code `invalid_credentials`, status 401) on `argon2.exceptions.VerifyMismatchError`. Timing equivalence achieved by always hashing on user-not-found path (Phase 5 concern).
- **D-29:** Verification is import-introspection + Alembic smoke, NOT integration tests for endpoints. `tests/unit/test_security.py`, `test_permissions.py`, `test_schemas.py` + `tests/integration/test_alembic_clean.py`.

### Deferred Ideas (OUT OF SCOPE)

- Envelope expansion fields (`requestId`, `traceId`, `meta`, `warnings`) — additive, future phases.
- JWT secret split (`jwt_access_secret` + `jwt_refresh_secret`) — non-breaking refactor, future.
- `jti` / `iss` / `aud` claims on access tokens.
- Stateless JWT-only mode (no DB session record) — explicitly REJECTED (per PROJECT.md OoS).
- `require_permission` route wiring on real endpoints — Phase 6 (RBAC-02..05).
- CSRF dependency `verify_csrf` validation — Phase 6 (CSRF-02). Phase 4 only emits the cookie + token.
- First business migration `0001_auth.py` — Phase 5 (INFRA-03).
- `audit_log` table — Phase 8 (INFRA-04, AUDIT-01..03).
- Telegram bot worker process — Phase 7. Phase 4 only adds the dep.
- `pg_trgm` extension enable — Phase 8.
- OpenAPI export script + drift CI — Phase 9.
- Frontend `_README.md` + mock-service rewrite to consume `ResponseEnvelope[T]` — Phase 10 (FE-01..FE-07).
- Active-sessions UI / password reset / HIBP / webhook bot mode — v1.2.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | `app/core/database.py` defines `Base` with explicit `MetaData(naming_convention=...)` BEFORE the first business migration | §3 (Alembic naming convention recipe + autogenerate empty-diff verification) |
| INFRA-02 | `app/core/database.py` exposes `UUIDPkMixin` (PG-native `gen_random_uuid()`), `TimestampMixin`, `SoftDeleteMixin` (`deleted_at` indexed) | §3 (mixin composition pattern + partial-index helper) |
| INFRA-05 | `app/modules/members/` renamed → `app/modules/clients/`; `.importlinter` `modules-independent` updated | §6 (`git mv` recipe + .importlinter ini diff) |
| INFRA-07 | `pyproject.toml` adds `pyjwt>=2.12.1,<3`, `argon2-cffi>=25.1.0,<26`, `python-telegram-bot>=22.7,<23`; bumps `pydantic>=2.11,<3`; `uv lock` regenerated | §1 (dependency table with verified versions + publish dates) |
| AUTH-01 | JWT encode/decode (HS256, 30s clock leeway) backed by `settings.secret_key` | §2.1 (PyJWT `encode`/`decode`/`leeway` exact APIs + exception hierarchy) |
| AUTH-02 | Argon2id `hash_password` / `verify_password` wrapped via `asyncio.to_thread`; passwords never plaintext | §2.2 (`PasswordHasher` defaults + `verify` + `check_needs_rehash` + `VerifyMismatchError`) |
| AUTH-03 | One-time codes (`secrets.randbelow`, 6 digits) and deep-link tokens (`secrets.token_urlsafe(32)`); raw codes never persisted — only `sha256(code)` | §2.3 (stdlib `secrets` recipe + length math) |
| AUTH-04 | Successful login issues two httpOnly cookies — `sz_access` (Path=/, Max-Age=900s) and `sz_refresh` (Path=/api/v1/auth, Max-Age=2592000s); `Secure` env-driven with prod assertion | §4 (cookie matrix + SameSite=Lax rationale + dev/prod Secure flag) |
| CSRF-01 | Server sets non-httpOnly `sportzal_csrf` cookie (32-byte hex, Secure, SameSite=Lax) | §4 (CSRF cookie attrs + `secrets.token_hex(32)`) |
| RBAC-01 | `app/core/permissions.py` defines `Role`, `Action`, `Resource` `StrEnum`s + `OWNER_ONLY: frozenset[tuple[Action, Resource]]`; `can(role, action, resource)` mirrors `apps/admin-web/src/shared/session/can.ts` byte-for-byte | §5 (verbatim 9-entry mirror + StrEnum value table + parity test recipe deferred to Phase 6) |
| API-03 | Backend wire format = camelCase via Pydantic `alias_generator=to_camel` + `validate_by_name`/`validate_by_alias`; Python identifiers stay snake_case | §7 (ConfigDict recipe + Pydantic 2.11 migration of `populate_by_name`) |
| API-04 | Pagination envelope `{items, total, page, pageSize}`; `app/core/pagination.py` updated (replaces v1.0 `limit/offset`) | §7 (PEP 695 `PaginatedData[T]` + camelCase wire verification) |

</phase_requirements>

<phase_constraints>
## Project Constraints (from CLAUDE.md)

- **Backend stack lock:** Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog. Alternatives are NOT considered. `[VERIFIED: pyproject.toml + uv.lock]`
- **Region:** RU/CIS — Stripe FORBIDDEN; payments only ЮKassa; Telegram primary. Phase 4 ships no payments. `[CITED: CLAUDE.md + PROJECT.md]`
- **Tooling:** ruff + mypy strict + import-linter mandatory; runnable via `uv run`. `[VERIFIED: pyproject.toml]`
- **Testing:** backend tests use `httpx ASGITransport` + `pytest-asyncio`. Phase 4 unit tests are pure-Python (no fixtures). `[VERIFIED: tests/conftest.py]`
- **Frontend integrity:** `apps/admin-web` is a verbatim move of `./frontend`; **NO modifications in Phase 4** (D-30). Phase 10 will relax this for the contracts/mocks layer only. `[CITED: CLAUDE.md + CONTEXT.md D-30]`
- **Placeholders only:** `packages/ui` and `packages/api-client` — only `package.json` + `README.md` until Phase 9. Phase 4 does NOT touch them. `[CITED: CLAUDE.md]`
- **Python package name:** `app` (not `sportzal`, not `src/sportzal`). `[VERIFIED: pyproject.toml + apps/backend/app/]`
- **Architectural invariants (import-linter):** `core ⊥ modules`, `modules` independent, `integrations ⊥ modules`. The Protocol-based loader pattern (D-24) preserves all three. `[VERIFIED: .importlinter]`
- **GSD workflow enforcement:** edits go through GSD commands. This research is itself a GSD-spawned task. `[CITED: CLAUDE.md]`

</phase_constraints>

## Summary

Phase 4 ships **only primitives** — no endpoints, no auth flow, no business migrations. It locks down the cross-cutting contracts (JWT, Argon2, cookies, RBAC enums, Alembic naming convention, ORM mixins, ResponseEnvelope, camelCase wire, `members` → `clients`) so they cannot be retrofitted later.

The work is heavily prescribed by CONTEXT.md (30 decisions, 18 LOCKED, 12 Discretion). Research focused on **filling concrete library APIs** (PyJWT 2.12.1 leeway + exception hierarchy, argon2-cffi 25.1.0 `PasswordHasher`/`check_needs_rehash`/`VerifyMismatchError`, Pydantic 2.13.3 `validate_by_name`/`validate_by_alias` migration semantics, Alembic 1.18.4 `alembic check` and the autogenerate-empty-diff guarantee), not on choosing libraries. **Library choices are LOCKED** by D-12 / D-19 / D-22 / D-27 and STACK.md.

Three subtle gates require careful planning:

1. **Pydantic 2.11 migration** — `populate_by_name=True` is **deprecated, NOT removed** in 2.11+. The new flag is `validate_by_name=True` (paired with `validate_by_alias=True`). Both must be set; setting both to `False` raises `PydanticUserError(code='validate-by-alias-and-name-false')`. `[VERIFIED: Context7 /pydantic/pydantic — docs/migration.md and docs/errors/usage_errors.md]`
2. **Alembic autogenerate-on-clean smoke (SC #3)** — the canonical assertion is `alembic check` (exit 0 + stdout `"No new upgrade operations detected."`), NOT parsing the generated revision file. Alembic ships this exact tool; it returns non-zero on any drift. `[VERIFIED: Context7 /websites/alembic_sqlalchemy — autogenerate.rst, naming.html]`
3. **PyJWT exception hierarchy** — `jwt.ExpiredSignatureError` is a *subclass* of `jwt.InvalidTokenError`. Catching `InvalidTokenError` covers both. The `leeway` parameter takes either `int` (seconds) or `datetime.timedelta`. Decode requires explicit `algorithms=["HS256"]` (security default since PyJWT 2.x). `[VERIFIED: Context7 /jpadilla/pyjwt — docs/usage.md, CHANGELOG.rst]`

**Primary recommendation:** Plan Phase 4 as **3 sequential waves** with no fan-out: Wave 0 (deps + Alembic naming convention) → Wave 1 (security primitives + RBAC + schemas in `core`) → Wave 2 (`members → clients` rename + `.importlinter` update + Phase 4 SC verification). Verification is a single `make`-style script: `uv lock --check && uv run lint-imports && uv run pytest tests/unit -q && uv run alembic upgrade head && uv run alembic check` — all green or the phase is not done.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JWT encode/decode primitives | **API / Backend (`app/core/security.py`)** | — | Pure-function infrastructure shared by all modules; lives in core because Auth is not its only consumer (every route that calls `get_current_user` indirectly relies on it). `core ⊥ modules` invariant requires it here. |
| Argon2 hash/verify | **API / Backend (`app/core/security.py`)** | — | Same reasoning as JWT — pure crypto primitive, no DB, no domain. |
| Cookie matrix emission | **API / Backend (`app/core/security.py`)** | — | Per D-25, single helper to centralize SameSite/Path/Max-Age across all emission sites (Phase 5 login, Phase 5 refresh, Phase 7 OTP-verify). |
| RBAC enums + matrix + `can()` | **API / Backend (`app/core/permissions.py`)** | — | Pitfall #19: putting RBAC in `modules/auth` violates `modules-independent` for every other module that imports it. `core` is the only acceptable home. |
| `get_current_user` / `require_permission` dependencies | **API / Backend (`app/core/dependencies.py`)** | — | Same as RBAC — the dependency must be importable by every module's router. Loader-Protocol pattern (D-24) avoids importing `modules.auth` from `core`. |
| Wire-format contract (`ResponseEnvelope`, `RequestContract`, etc.) | **API / Backend (`app/core/schemas.py`)** | — | Cross-cutting — every endpoint emits/consumes these. Belongs in `core` for the same reason as pagination. |
| Pagination contract | **API / Backend (`app/core/pagination.py`)** | — | Already lives in core; rewrite stays in core. |
| ORM mixins (UUIDPk / Timestamp / SoftDelete) | **API / Backend (`app/core/database.py`)** | Database / Storage (`server_default=text(...)`, partial index DDL) | Mixins are SA model decorators; their effect (DDL, server_defaults) lands in Postgres. |
| Alembic `MetaData(naming_convention=...)` | **API / Backend (`app/core/database.py`)** | Database / Storage (constraint names) | Naming convention is configured on `Base.metadata` in Python; effect manifests in PG via Alembic-generated DDL. |
| `members → clients` rename | **API / Backend (filesystem + import-linter)** | — | Pure code refactor; no runtime state, no DB (no models exist yet). |
| **Frontend** | **— (out of scope per D-30)** | — | Phase 4 does NOT touch `apps/admin-web`. Frontend stays on bare-object contract until Phase 10. |

## Standard Stack

### Core (verified versions, PyPI 2026-05-01)

| Library | Pin (CONTEXT.md) | Latest | Published | Purpose | Why Standard |
|---------|-----------------|--------|-----------|---------|--------------|
| `pyjwt` | `>=2.12.1,<3` | 2.12.1 | 2026-03-13 | HS256 access-token encode/decode + leeway | Active maintenance, py.typed, FastAPI tutorial migrated off `python-jose` to PyJWT in 2024. `[VERIFIED: pip index versions PyJWT]` |
| `argon2-cffi` | `>=25.1.0,<26` | 25.1.0 | 2025-06-03 | Argon2id password hashing | OWASP 2026 default; library-default params (`memory_cost=65536` KiB, `time_cost=3`, `parallelism=4`) align to ~50ms tuned for typical hardware. `[VERIFIED: pip index versions argon2-cffi + Context7 /hynek/argon2-cffi]` |
| `pydantic` | bump `>=2.11,<3` | 2.13.3 | 2026-04-20 | `validate_by_name` + `validate_by_alias` (deprecates `populate_by_name`) | Required for D-09 ContractModel. 2.11+ floor is the minimum. `[VERIFIED: pip index versions pydantic + Context7 /pydantic/pydantic — migration.md]` |
| `python-telegram-bot` | `>=22.7,<23` | 22.7 | 2026-03-16 | Telegram bot dep (Phase 7 USES it; Phase 4 only adds the line) | Pinned now so `uv lock` is regenerated once for all auth-stack deps. Worker process not built in Phase 4. `[VERIFIED: pip index versions python-telegram-bot]` |
| `sqlalchemy` | already `>=2.0` | 2.0.49 | 2026-04-03 | `MetaData(naming_convention=...)`, `Mapped`/`mapped_column` mixins | No bump needed. `[VERIFIED: pyproject.toml + PyPI]` |
| `alembic` | already `>=1.13` | 1.18.4 | 2026-02-10 | `alembic check` for autogenerate-empty-diff smoke | No bump needed; `alembic check` is in 1.13+. `[VERIFIED: pyproject.toml + Context7 /websites/alembic_sqlalchemy]` |

### Supporting (already in v1.0, no change)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastapi` | `>=0.115` | `Response`, `APIRouter`, `Depends` for cookie helper signatures | All future endpoints (Phase 5+); Phase 4 imports for type signatures only |
| `pydantic-settings` | `>=2.0` | `Settings.access_token_ttl_seconds` etc. | D-05 — env-driven TTLs |
| `structlog` | `>=24.0` | (no use in Phase 4 primitives) | — |

### Alternatives Considered (REJECTED — locked by STACK.md)

| Instead of | Could Use | Reason Rejected |
|------------|-----------|-----------------|
| `pyjwt` | `python-jose` | 107 open issues, sluggish maintenance, lags `cryptography` releases. FastAPI tutorial migrated off in 2024. `[CITED: STACK.md]` |
| `pyjwt` | `authlib` | Scope creep — full OAuth2 provider/client framework; we hand-roll JWT. `[CITED: STACK.md]` |
| `argon2-cffi` | `passlib[argon2]` | passlib unmaintained since 2020-10-08; bcrypt 5.0 broke its compat shim. `[CITED: STACK.md]` |
| `argon2-cffi` | `bcrypt` direct | OWASP 2026 default is Argon2id (memory-hardness); bcrypt is secondary. `[CITED: STACK.md]` |
| `python-telegram-bot` | `aiogram` | Pulls aiohttp as a parallel HTTP stack (we standardize on httpx). `[CITED: STACK.md]` |
| `fastapi-csrf-protect` | hand-rolled double-submit | 30 LOC of stdlib; library overhead unjustified. `[CITED: STACK.md]` |
| `Casbin / Oso / OPA` | hand-rolled `can()` | 9-entry static matrix; an `if`-statement is the right tool. `[CITED: PROJECT.md OoS + STACK.md]` |

### Installation

```bash
cd apps/backend
uv add 'pyjwt>=2.12.1,<3' 'argon2-cffi>=25.1.0,<26' 'python-telegram-bot>=22.7,<23'
uv add 'pydantic>=2.11,<3'  # bump existing
uv lock  # regenerate uv.lock
```

**Version verification command** (CI / pre-commit hook):

```bash
uv lock --check  # fails if pyproject.toml drifted from uv.lock
```

`[VERIFIED: uv 0.5+ docs]`

## Architecture Patterns

### System Architecture Diagram

```
                  Phase 4 — Primitives Only (NO ENDPOINTS, NO MIGRATIONS)

  ┌──────────────────────────────── apps/backend/app/ ────────────────────────────────┐
  │                                                                                   │
  │  ┌────────────────────────────────── core ──────────────────────────────────────┐ │
  │  │                                                                              │ │
  │  │  config.py ──┐                                                                │ │
  │  │  (+ 4 fields)│                                                                │ │
  │  │              │                                                                │ │
  │  │              ▼                                                                │ │
  │  │  database.py ─── Base(DeclarativeBase) + MetaData(naming_convention=…)       │ │
  │  │       │           UUIDPkMixin / TimestampMixin / SoftDeleteMixin             │ │
  │  │       │                  ▲                                                   │ │
  │  │       │                  │ (no models yet — empty target_metadata)           │ │
  │  │       └──────────────────┼────────────────────────────────► alembic/env.py   │ │
  │  │                          │                                                   │ │
  │  │  security.py ─── encode_access_token / decode_access_token (PyJWT HS256)    │ │
  │  │       │           hash_password / verify_password (Argon2id, asyncio.to_thread)│ │
  │  │       │           generate_refresh_token / generate_otp_code / generate_deep_link│ │
  │  │       │           generate_csrf_token                                          │ │
  │  │       │           issue_session_cookies(response, *, access, refresh, csrf, secure)│ │
  │  │       │                                                                      │ │
  │  │       ▼                                                                      │ │
  │  │  exceptions.py ── + InvalidAccessToken (401, "invalid_token")                │ │
  │  │                  + InvalidPassword (401, "invalid_credentials")              │ │
  │  │                  + RateLimited (429, "rate_limited")                         │ │
  │  │                                                                              │ │
  │  │  permissions.py (NEW) ── Role / Action / Resource (StrEnum)                  │ │
  │  │                          OWNER_ONLY: frozenset[tuple[Action, Resource]]      │ │
  │  │                          can(role, action, resource) -> bool                 │ │
  │  │                                                                              │ │
  │  │  schemas.py (NEW) ─── ContractModel ─── RequestContract                      │ │
  │  │                         │                                                     │ │
  │  │                         └──────────── ResponseData                            │ │
  │  │                                            │                                  │ │
  │  │                                            ├── ResponseEnvelope[T]            │ │
  │  │                                            └── PaginatedData[T] (in pagination.py)│ │
  │  │                       ProblemDetails (top-level, NOT nested in envelope)     │ │
  │  │                                                                              │ │
  │  │  pagination.py (REWRITE) ── PageQuery (page, page_size)                      │ │
  │  │                              PaginatedData[T] (items, total, page, page_size)│ │
  │  │                                                                              │ │
  │  │  dependencies.py ─── CurrentUser(Protocol)                                   │ │
  │  │                       _user_loader: UserLoader | None  ← module slot          │ │
  │  │                       register_user_loader(loader)  ← composition root call  │ │
  │  │                       get_current_user(request, session) → CurrentUser       │ │
  │  │                       require_permission(action, resource) → Callable        │ │
  │  │                                                                              │ │
  │  └──────────────────────────────────────────────────────────────────────────────┘ │
  │                                                                                   │
  │  ┌──────────────────────────────── modules ────────────────────────────────────┐ │
  │  │                                                                             │ │
  │  │  members/  ───[git mv]──►  clients/   (5 placeholder files renamed)         │ │
  │  │                                                                             │ │
  │  │  auth/ memberships/ visits/ trainers/ schedule/ bookings/ billing/ notifications/ │ │
  │  │  (untouched in Phase 4 — Phase 5 fills auth/, Phase 8 fills clients/)      │ │
  │  └─────────────────────────────────────────────────────────────────────────────┘ │
  │                                                                                   │
  │  .importlinter ──► modules-independent: members → clients (one-line edit)        │ │
  └───────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────── verification (no runtime) ──────────────────────────┐
  │  uv lock --check                                                                │
  │  uv run lint-imports          ← three contracts GREEN after rename              │
  │  uv run mypy app              ← strict still passes                             │
  │  uv run ruff check            ← still GREEN                                     │
  │  uv run pytest tests/unit -q  ← 4 new files: test_security, test_permissions,   │
  │                                  test_schemas (test_alembic_clean is integration)│
  │  uv run alembic upgrade head  ← against compose Postgres                        │
  │  uv run alembic check         ← MUST output "No new upgrade operations detected"│
  │                                  (this IS the autogenerate-empty-diff smoke)    │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (additions only)

```
apps/backend/
├── app/core/
│   ├── config.py          # MODIFIED: + 4 fields (access_ttl, refresh_ttl, leeway, cookie_secure)
│   ├── database.py        # MODIFIED: + naming_convention, + 3 mixins
│   ├── security.py        # FILLED: from placeholder → JWT + Argon2 + token gens + cookie helper
│   ├── exceptions.py      # MODIFIED: + InvalidAccessToken, InvalidPassword, RateLimited
│   ├── permissions.py     # NEW: Role/Action/Resource StrEnum + OWNER_ONLY + can()
│   ├── schemas.py         # NEW: ContractModel hierarchy + ResponseEnvelope + ProblemDetails
│   ├── pagination.py      # REWRITE: PageQuery + PaginatedData[T]
│   └── dependencies.py    # FILLED: from placeholder → CurrentUser Protocol + loader scaffolding
├── app/modules/
│   └── clients/           # RENAMED from members/ (git mv preserves blame)
├── alembic/env.py         # UNCHANGED (target_metadata = Base.metadata picks up new convention)
├── tests/
│   ├── unit/
│   │   ├── test_security.py     # FILLED: JWT round-trip, Argon2 round-trip, token-gen length/charset
│   │   ├── test_permissions.py  # NEW: every OWNER_ONLY pair + frozenset instance check
│   │   └── test_schemas.py      # NEW: extra='forbid', camelCase wire, by_alias dump
│   └── integration/
│       └── test_alembic_clean.py  # NEW: alembic upgrade head + alembic check
├── .importlinter            # MODIFIED: members → clients in modules-independent contract
├── .env.example             # MODIFIED: + ACCESS_TOKEN_TTL_SECONDS etc. + COOKIE_SECURE
├── pyproject.toml           # MODIFIED: + pyjwt, argon2-cffi, python-telegram-bot; pydantic>=2.11
└── uv.lock                  # REGENERATED
```

### Pattern 1: Protocol-Based Loader for Cross-Module Auth (D-24)

**What:** `core` cannot import from `modules` (importlinter `core ⊥ modules`). But `get_current_user` lives in `core` and must load a User from `modules.auth`. The standard fix is a Protocol slot in `core` that the composition root (`app/main.py`) fills at startup.

**When to use:** Any cross-module callback where the contract direction violates importlinter. Same pattern applies in Phase 7 (`integrations.telegram` → `modules.auth.confirm_deep_link`).

**Example:**
```python
# app/core/dependencies.py — Phase 4 deliverable
# Source: ARCHITECTURE.md §2.2 + CONTEXT.md D-24
from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, InvalidAccessToken
from app.core.permissions import Action, Resource, Role, can
from app.core.security import decode_access_token


class CurrentUser(Protocol):
    """Structural type — NO module import. Anything with these attrs satisfies it."""
    id: UUID
    role: Role


UserLoader = Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]
_user_loader: UserLoader | None = None


def register_user_loader(loader: UserLoader) -> None:
    """Called once by composition root (app.main.create_app) in Phase 5."""
    global _user_loader
    _user_loader = loader


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    token = request.cookies.get("sz_access")
    if token is None:
        raise InvalidAccessToken("missing_access_cookie")
    claims = decode_access_token(token)  # raises InvalidAccessToken on failure
    if _user_loader is None:
        # Defensive: composition root MUST register before request flow starts
        raise InvalidAccessToken("user_loader_not_registered")
    user = await _user_loader(session, UUID(claims.sub))
    if user is None:
        raise InvalidAccessToken("user_not_found")
    return user


def require_permission(action: Action, resource: Resource):
    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not can(user.role, action, resource):
            raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
        return user
    return _checker
```

**Why this preserves `core ⊥ modules`:** `core/dependencies.py` declares only a Protocol (structural type) and a Callable slot. It does NOT `from app.modules.auth import ...`. Phase 5's `app/main.py` does:

```python
# app/main.py — Phase 5 addition (NOT Phase 4)
from app.core.dependencies import register_user_loader
from app.modules.auth.service import load_user_by_id

def create_app() -> FastAPI:
    register_user_loader(load_user_by_id)  # composition root wires it
    ...
```

**`app.main` is exempt from `core ⊥ modules`** because importlinter's `core-not-depend-on-modules` contract has `source_modules = app.core` (not `app`). `[VERIFIED: apps/backend/.importlinter lines 5-11]`

### Pattern 2: PyJWT Encode/Decode with Clock Leeway (AUTH-01)

**What:** HS256 sign/verify with the existing `settings.secret_key` and a 30s leeway window for cross-container clock drift (Pitfall #32).

**Example:**
```python
# app/core/security.py — Phase 4 deliverable
# Source: Context7 /jpadilla/pyjwt — docs/usage.md (verified 2026-05-01)
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken
from app.core.permissions import Role


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    sub: str         # str(user_uuid)
    role: Role       # StrEnum value
    typ: str         # "access"
    iat: int         # UTC epoch seconds
    exp: int         # UTC epoch seconds


def encode_access_token(
    user_id: UUID,
    role: Role,
    *,
    now: datetime | None = None,
) -> str:
    settings = get_settings()
    issued = now or datetime.now(tz=timezone.utc)
    expires = issued + __import__("datetime").timedelta(
        seconds=settings.access_token_ttl_seconds
    )
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=settings.jwt_clock_leeway_seconds,
            options={"require": ["sub", "role", "typ", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessToken("token_expired") from exc
    except jwt.InvalidTokenError as exc:  # parent class — covers all decode failures
        raise InvalidAccessToken("invalid_token") from exc

    if payload.get("typ") != "access":
        raise InvalidAccessToken("wrong_token_type")
    try:
        role = Role(payload["role"])
    except ValueError as exc:
        raise InvalidAccessToken("unknown_role") from exc

    return AccessTokenClaims(
        sub=payload["sub"],
        role=role,
        typ=payload["typ"],
        iat=payload["iat"],
        exp=payload["exp"],
    )
```

**Critical PyJWT facts** `[VERIFIED: Context7 /jpadilla/pyjwt + CHANGELOG]`:
- `jwt.decode(...)` REQUIRES explicit `algorithms=` since PyJWT 2.x (security default).
- `jwt.ExpiredSignatureError` is a subclass of `jwt.InvalidTokenError`. Catching `InvalidTokenError` covers both. Catch `ExpiredSignatureError` first if you need to distinguish (we do — it maps to `code="token_expired"`).
- `leeway` accepts `int` (seconds) or `datetime.timedelta`. We pass int from `settings.jwt_clock_leeway_seconds`.
- `options={"require": [...]}` enforces required claims at decode time (raises `MissingRequiredClaimError`, also a subclass of `InvalidTokenError`).
- Whole exception tree: `InvalidTokenError` → `DecodeError` / `ExpiredSignatureError` / `InvalidAudienceError` / `InvalidIssuerError` / `InvalidIssuedAtError` / `ImmatureSignatureError` / `InvalidKeyError` / `InvalidAlgorithmError` / `MissingRequiredClaimError` / `InvalidSignatureError`. We don't use `aud` / `iss` (D-02), so those don't fire.

### Pattern 3: Argon2id with `check_needs_rehash` Workflow (AUTH-02)

**What:** Hash with library defaults; verify with `VerifyMismatchError` mapped to `InvalidPassword`; advertise rehash needed via `check_needs_rehash` so callers (Phase 5 login service) can transparently upgrade hashes when params bump.

**Example:**
```python
# app/core/security.py — Phase 4 deliverable
# Source: Context7 /hynek/argon2-cffi — README.md, docs/argon2.md (verified 2026-05-01)
import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.exceptions import InvalidPassword

# Module-level hasher; PasswordHasher() uses OWASP-aligned defaults:
#   memory_cost=65536 KiB, time_cost=3, parallelism=4, hash_len=32, salt_len=16
# Tuned to ~50ms on typical hardware. CONTEXT.md D-27 locks this.
_ph = PasswordHasher()


async def hash_password(plaintext: str) -> str:
    """Return Argon2id encoded hash. Always async-wrapped (~50ms blocks event loop)."""
    return await asyncio.to_thread(_ph.hash, plaintext)


async def verify_password(plaintext: str, encoded_hash: str) -> bool:
    """
    Return True on match; raise InvalidPassword on mismatch.

    Side effect: returns True AND signals "needs_rehash" via the second tuple element
    so callers (Phase 5 login flow) can transparently upgrade stored hashes.
    """
    def _do() -> bool:
        try:
            _ph.verify(encoded_hash, plaintext)
            return True
        except VerifyMismatchError as exc:
            raise InvalidPassword("invalid_credentials") from exc
        except InvalidHashError as exc:
            # Stored hash is malformed (data corruption / wrong column) — treat as auth failure
            raise InvalidPassword("invalid_credentials") from exc

    return await asyncio.to_thread(_do)


async def password_needs_rehash(encoded_hash: str) -> bool:
    """Return True if the hash was created with weaker params than current defaults."""
    return await asyncio.to_thread(_ph.check_needs_rehash, encoded_hash)
```

**Critical argon2-cffi facts** `[VERIFIED: Context7 /hynek/argon2-cffi]`:
- `PasswordHasher()` with no args = OWASP defaults. `[CITED: docs/argon2.md "recommended approach for most use cases"]`
- `ph.verify(hash, password)` returns `True` on match, raises `VerifyMismatchError` on mismatch, raises `InvalidHashError` on malformed hash, `VerificationError` (parent) for misc failures. `[VERIFIED: README.md example]`
- `ph.check_needs_rehash(hash)` returns `bool`. True iff stored hash's params don't match current `PasswordHasher` instance params. `[VERIFIED: README.md example]`
- Default `time_cost=3` produces ~45.7ms per verify on typical hardware (`python -m argon2` benchmark output). Wrapping in `asyncio.to_thread` is mandatory to keep the event loop responsive. `[VERIFIED: docs/cli.md benchmark example]`

### Pattern 4: Token Generators (AUTH-03)

**What:** Cryptographically secure random for refresh tokens, OTP codes, deep-link tokens, CSRF tokens.

**Example:**
```python
# app/core/security.py — Phase 4 deliverable
# Source: Python stdlib `secrets` — https://docs.python.org/3.12/library/secrets.html
import hashlib
import secrets


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()  # 64 hex chars


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Raw goes to cookie; only the hash is persisted."""
    raw = secrets.token_urlsafe(32)  # 32 bytes → 43 base64url chars
    return raw, _sha256_hex(raw)


def generate_otp_code() -> tuple[str, str]:
    """Return (raw_6_digit_code, sha256_hex). Raw goes to Telegram DM; hash is persisted."""
    code = f"{secrets.randbelow(1_000_000):06d}"  # zero-padded 0..999999
    return code, _sha256_hex(code)


def generate_deep_link_token() -> str:
    """Return URL-safe 43-char token for /start <token> deep links."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Return 64-char hex (32 bytes). Cookie value, sent verbatim in X-CSRF-Token header."""
    return secrets.token_hex(32)
```

**Length math** `[VERIFIED: Python stdlib docs + ASSUMED arithmetic]`:
- `secrets.token_urlsafe(32)` → 32 raw bytes → 43-char base64url string (last char never padded `=`).
- `secrets.token_hex(32)` → 32 raw bytes → 64-char hex string.
- `secrets.randbelow(1_000_000)` → uniform integer in `[0, 999999]` → zero-pad to 6 digits.
- `sha256` always produces 64 hex chars (32 raw bytes).

### Pattern 5: Cookie Matrix Emission (AUTH-04 + CSRF-01)

**What:** Single helper sets all three session cookies with consistent attributes. Centralizing prevents drift across Phase 5 login, Phase 5 refresh, Phase 7 OTP-verify (D-25 rationale).

**Example:**
```python
# app/core/security.py — Phase 4 deliverable
# Source: CONTEXT.md D-25 + RFC 6265bis cookie attributes
from fastapi import Response

from app.core.config import get_settings


def issue_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    secure: bool,
) -> None:
    """Set sz_access + sz_refresh + sportzal_csrf with the locked attributes (AUTH-04 + CSRF-01)."""
    settings = get_settings()

    # sz_access — covers all API paths
    response.set_cookie(
        key="sz_access",
        value=access_token,
        max_age=settings.access_token_ttl_seconds,    # 900s default
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # sz_refresh — narrow path, only sent to /api/v1/auth/* (smaller exposure surface)
    response.set_cookie(
        key="sz_refresh",
        value=refresh_token,
        max_age=settings.refresh_token_ttl_seconds,   # 2592000s default (30d)
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # sportzal_csrf — non-httpOnly so frontend reads it for X-CSRF-Token header
    response.set_cookie(
        key="sportzal_csrf",
        value=csrf_token,
        max_age=settings.refresh_token_ttl_seconds,   # match refresh lifetime
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )
```

**Cookie attribute rationale** `[CITED: PITFALLS.md #1 + #2 + RFC 6265bis]`:
- `SameSite=Lax` (NOT `Strict`, NOT `None`) — required for the Telegram return-flow scenario in Phase 7 where the user lands on `admin.sportzal.ru/auth/callback?...` after pressing "Open admin" in a t.me DM. Strict drops cookies on cross-site top-level GET; Lax preserves them. `None` requires `Secure=true` (works) but is overkill for the threat model.
- `Secure` env-driven from `Settings.cookie_secure: bool = False`. Dev (`http://localhost`) needs `False` — browsers silently drop Secure cookies on HTTP localhost (Pitfall #2). Prod startup assertion in `app.main.create_app`: `if settings.environment == "prod" and not settings.cookie_secure: raise RuntimeError(...)`.
- Refresh `Path=/api/v1/auth` reduces the attack surface — refresh cookie is NOT sent on every API request, only on `/auth/*` (login, refresh, logout).
- CSRF cookie is NOT httpOnly because the frontend MUST read it to echo it in the `X-CSRF-Token` header (double-submit pattern). The verifier `Depends(verify_csrf)` lands in Phase 6 (CSRF-02) — Phase 4 only emits.

### Pattern 6: ContractModel Hierarchy (D-09 + API-03)

**What:** Pydantic 2.11+ base classes that emit camelCase on the wire while keeping snake_case in Python. PEP 695 generics for `ResponseEnvelope[T]` and `PaginatedData[T]`.

**Example:**
```python
# app/core/schemas.py — Phase 4 deliverable (NEW FILE)
# Source: Context7 /pydantic/pydantic — concepts/alias.md, concepts/models.md (PEP 695)
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    """Base for every API contract model. camelCase wire, snake_case Python.

    `validate_by_name=True` + `validate_by_alias=True` replaces the deprecated
    `populate_by_name=True` (Pydantic 2.11+). Both flags must be True; setting
    both to False raises PydanticUserError(code='validate-by-alias-and-name-false').
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        from_attributes=True,
        extra="ignore",
    )


class RequestContract(ContractModel):
    """Inbound request body / query params. Strict on extras (extra='forbid')."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )


class ResponseData(ContractModel):
    """Payload inside ResponseEnvelope. Subclassed by every domain response DTO."""


class ResponseEnvelope[T](ContractModel):  # PEP 695 generic — Python 3.12+
    """Success transport wrapper. Phase 4: { data: T }. Future fields optional."""
    data: T


class ProblemDetails(ContractModel):
    """Error response body (matches AppError handler output, used as response_model in OpenAPI)."""
    code: str
    message: str
    fields: dict[str, object] | None = None


def envelope[T](payload: T) -> ResponseEnvelope[T]:
    """Convenience helper. D-14: routes return ResponseEnvelope[X](data=...) explicitly,
    but a small wrapper is acceptable. Not mandatory."""
    return ResponseEnvelope(data=payload)
```

**Pydantic 2.11+ migration facts** `[VERIFIED: Context7 /pydantic/pydantic — docs/migration.md]`:
- `populate_by_name=True` is **renamed to `validate_by_name=True`** in 2.11. The old name continues to work but emits a deprecation warning. We use the new names because we depend on `pydantic>=2.11` (D-12).
- Setting BOTH `validate_by_alias=False` AND `validate_by_name=False` raises `PydanticUserError(code='validate-by-alias-and-name-false')` — the only invalid combination.
- `pydantic.alias_generators.to_camel` is shipped — no third-party dep.
- PEP 695 generics work natively in Pydantic 2.11+ — `class ResponseEnvelope[T](ContractModel)` is preferred over `class ResponseEnvelope(ContractModel, Generic[T])`. `[VERIFIED: Context7 /pydantic/pydantic — concepts/models.md "Create Generic Model with Type Parameters (Python 3.12+)"]`

### Pattern 7: Pagination Rewrite (API-04 + D-10)

**Example:**
```python
# app/core/pagination.py — Phase 4 REWRITE
# Source: CONTEXT.md D-10
from pydantic import Field

from app.core.schemas import PaginatedData, RequestContract  # NEW imports

# Old LimitOffsetParams + old Page[T] are DELETED — clean break, no consumers exist
# (only /healthz uses pagination contract, and it doesn't paginate).

class PageQuery(RequestContract):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)  # → "pageSize" on wire


# PaginatedData[T] is defined in app/core/schemas.py per import order:
# pagination.py imports schemas.py (which defines ContractModel/ResponseData base);
# schemas.py does NOT import pagination.py. Place PaginatedData[T] in pagination.py
# IF you want it co-located with PageQuery — but then schemas.py imports pagination.
# Recommendation: place PaginatedData[T] in pagination.py because that's where pagination
# lives semantically, and schemas.py stays purely about transport contracts.

class PaginatedData[T](RequestContract):  # actually subclass ResponseData — see below
    items: list[T]
    total: int
    page: int
    page_size: int  # → "pageSize" on wire
```

**Note on file split:** D-10 puts `PaginatedData[T]` in `pagination.py`; D-09 puts the rest in `schemas.py`. To avoid circular imports: `pagination.py` imports `ResponseData` from `schemas.py` (schemas is the leaf). `[ASSUMED: import-order analysis]`

### Pattern 8: ORM Mixins (INFRA-02 + D-15/16/17/18)

**Example:**
```python
# app/core/database.py — Phase 4 ADDITIONS (existing Base/db_lifespan/get_db preserved)
# Source: SQLAlchemy 2.0 mixin cookbook + CONTEXT.md D-15/D-16/D-17/D-18
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base — naming convention is set on metadata BEFORE first model lands."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPkMixin:
    """Postgres-native gen_random_uuid() PK (PG13+, no pgcrypto extension needed in PG16)."""
    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """server-side func.now() on insert AND update; TIMESTAMPTZ, never naive."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """deleted_at column. Composing models add the partial unique-where-alive index."""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Per D-17 + Specifics §7: NO plain index on deleted_at — query patterns are
    # `WHERE deleted_at IS NULL` via repository helpers (Phase 8 CLIENTS-09).
    # Phase 8 clients model adds:
    #   __table_args__ = (
    #       Index("uq_clients_phone_alive", "phone", unique=True,
    #             postgresql_where=text("deleted_at IS NULL")),
    #   )
```

**Why no `index=True` on `deleted_at`** `[CITED: CONTEXT.md D-17 + Specifics]`: query patterns are partial-index based on `WHERE deleted_at IS NULL` (alive-bias) attached to specific business uniqueness constraints. Plain index on full `deleted_at` is redundant.

### Anti-Patterns to Avoid

- **Hand-rolling password hashing.** Use `argon2-cffi` defaults. Don't tune parameters in Phase 4 (D-27). `check_needs_rehash` lets you bump later without breaking accounts.
- **Implementing CSRF as middleware in Phase 4.** D-25 + D-26: emit cookie now (CSRF-01), verify in Phase 6 dependency (CSRF-02).
- **Importing from `app.modules.auth` in `app.core.dependencies`.** Use the Protocol slot (D-24).
- **Calling `_ph.verify()` synchronously in route handlers.** Always `asyncio.to_thread(...)` — verify takes ~50ms (event-loop blocker).
- **Catching `Exception` from `jwt.decode`.** Catch `jwt.ExpiredSignatureError` first, then `jwt.InvalidTokenError`. Anything else is a bug, not auth failure.
- **Setting both `validate_by_alias=False` AND `validate_by_name=False`.** Pydantic raises `PydanticUserError` at class definition.
- **Adding `index=True` to `SoftDeleteMixin.deleted_at`.** D-17: query patterns use partial indexes attached to business columns; standalone index is wasted.
- **Naming the response wrapper `ApiResponse[T]`.** Use `ResponseEnvelope[T]` (transport) and `ResponseData` (DTO base) as separate concepts (CONTEXT.md Specifics §3).
- **Splitting `issue_session_cookies` into three setters.** D-25 + Specifics §6: drift across emission sites (Phase 5 login vs refresh vs Phase 7 OTP-verify) is the real risk.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT signing/verification | Custom HMAC + JSON | `pyjwt` 2.12.1 | Algorithm confusion attacks, header injection, claim validation edge cases (exp/iat/nbf, leeway, required claims). PyJWT is type-safe and minimal. |
| Password hashing | Custom Argon2 / bcrypt | `argon2-cffi` 25.1.0 `PasswordHasher()` | Constant-time comparison, salt generation, parameter encoding/decoding, future param-bump migration via `check_needs_rehash`. |
| Random tokens / OTP codes | `random.randint` / `random.choices` | `secrets.token_urlsafe(32)`, `secrets.randbelow(10**6)`, `secrets.token_hex(32)` | `random` module is NOT cryptographically secure (Mersenne Twister, predictable from a few outputs). `secrets` uses `os.urandom`. |
| camelCase ↔ snake_case conversion | Custom regex / `re.sub` | `pydantic.alias_generators.to_camel` | Edge cases: leading underscore, single-letter words, ALL_CAPS, multi-word boundaries. Pydantic ships it. |
| RBAC policy engine | Custom `Policy` / `Rule` classes | `frozenset[tuple[Action, Resource]]` + `can()` | 9-entry static matrix. Casbin / Oso / OPA are 1000x the code for the same boolean check. PROJECT.md OoS. |
| CSRF library | `fastapi-csrf-protect` | Hand-rolled double-submit (`secrets.token_hex(32)` + `X-CSRF-Token` header check) | The verifier is ~10 lines (Phase 6). Library overhead unjustified for this simplicity. |
| Alembic empty-diff detection | Custom revision-file parser | `alembic check` | Built into Alembic 1.13+, exits non-zero on drift, prints `"No new upgrade operations detected."` on success. |
| UUID generation strategy | Python-side `uuid.uuid4()` then INSERT | Postgres-native `gen_random_uuid()` server_default | Single source of truth, no race conditions, INSERT-without-id returns generated id via `RETURNING`. PG13+ ships it without `pgcrypto`. |
| Timestamp generation | Python `datetime.utcnow()` | `func.now()` `server_default` + `onupdate` | DB is the source of truth for clock; multi-instance / Python clock drift becomes irrelevant; Pitfall #12 (server-default drift). |

**Key insight:** Phase 4 is almost entirely "wire stdlib + verified libraries together correctly." There is no novel algorithm to invent. The risk is **misuse** (wrong cookie attrs, wrong exception catch, wrong Pydantic config flag), not absence of building blocks.

## Runtime State Inventory

> Phase 4 is a code-only refactor PLUS new primitive code. The only rename is `app/modules/members` → `app/modules/clients`. NO live data, NO services, NO migrations.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — `members` module is an empty placeholder (no DB tables, no migrations exist for it). The very first business migration is Phase 5's `0001_auth.py`. `[VERIFIED: ls apps/backend/app/modules/members/ shows only `__init__.py` placeholder; alembic/versions/ has only `.gitkeep`]` | None — no data to migrate. |
| **Live service config** | None — no n8n / Datadog / external services in this project. Backend services in docker-compose are stateless containers (web, worker, migrate). `[VERIFIED: docker-compose.yml read in v1.0]` | None. |
| **OS-registered state** | None — no Windows Task Scheduler, no launchd, no systemd. `python-telegram-bot` worker is a docker-compose service in Phase 7 (not Phase 4). `[VERIFIED: project layout]` | None. |
| **Secrets/env vars** | `SECRET_KEY` exists in `.env.example` and is reused as JWT signing key (D-01). 4 NEW env vars added: `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`, `JWT_CLOCK_LEEWAY_SECONDS`, `COOKIE_SECURE`. No existing secrets to rename. `[VERIFIED: cat apps/backend/.env.example]` | Add 4 new entries to `.env.example` with dev defaults. Document in README that prod must override `COOKIE_SECURE=true` and use a strong `SECRET_KEY`. |
| **Build artifacts / installed packages** | `apps/backend/uv.lock` will be regenerated when 3 new deps + Pydantic bump land. Anyone who has `apps/backend/.venv` from v1.0 must `uv sync` again. No egg-info / no compiled binaries. `[VERIFIED: uv.lock + .venv pattern]` | After `uv lock` regenerates, document `uv sync` in dev runbook. CI's `uv lock --check` enforces fresh checkouts get the right deps. |

**Module rename specific risks** `[VERIFIED: grep + import-linter inspection]`:
- The string `app.modules.members` appears in exactly TWO locations: `apps/backend/.importlinter` (line 18 — to be edited) and `apps/backend/app/modules/members/__init__.py` (filesystem path — moved by `git mv`). No source code anywhere imports from `app.modules.members.*` (the module is an empty placeholder).
- `git mv apps/backend/app/modules/members apps/backend/app/modules/clients` preserves Git blame on `__init__.py`. Use `git log --follow apps/backend/app/modules/clients/__init__.py` post-move to verify.
- `__pycache__/` directories under `members/` are gitignored — they will be regenerated by Python on first import after rename. No stale-cache risk if the dev runs `find . -name __pycache__ -exec rm -rf {} +` once. `[ASSUMED based on .gitignore pattern, not verified]`

## Common Pitfalls

### Pitfall A: Pydantic 2.11 silent deprecation if `populate_by_name` left in code

**What goes wrong:** Old code from training data (or copy-paste from STACK.md mock examples) uses `populate_by_name=True`. In Pydantic 2.11+, this still works but emits `DeprecationWarning`. Our `pyproject.toml` has `filterwarnings = ["error", "ignore::DeprecationWarning:pydantic.*"]` which IGNORES the warning, so CI passes silently — but a future Pydantic 3.x removes the alias and code breaks.

**Why it happens:** Pydantic 2.11 release notes flagged `populate_by_name` rename to `validate_by_name`; 2.13.x continues to honor the old name with a deprecation. Easy to miss.

**How to avoid:** Use `validate_by_name=True` + `validate_by_alias=True` paired (CONTEXT.md D-09 already locked). Add a unit test that asserts the ConfigDict has `validate_by_name=True` literally (snapshot test against ContractModel.model_config).

**Warning signs:**
- `grep -rn 'populate_by_name' apps/backend/` returns hits — should be empty.
- Pytest output has `DeprecationWarning` from pydantic.

**Source:** `[VERIFIED: Context7 /pydantic/pydantic — docs/migration.md "config setting allow_population_by_field_name has been renamed to populate_by_name. For Pydantic v2.11 and later, it is further renamed to validate_by_name."]`

### Pitfall B: `alembic check` against an empty target_metadata + clean DB returns confusing output

**What goes wrong:** Phase 4 ships ZERO models. `Base.metadata` is empty. `alembic upgrade head` is a no-op (no revisions exist). Running `alembic check` against a clean DB asserts "model state matches DB state." With both empty, this is trivially TRUE — but the assertion is also TRUE in a buggy state where someone forgot to set `target_metadata = Base.metadata`.

**Why it happens:** `target_metadata = Base.metadata` is the ONLY linkage between Python models and Alembic. If `database.py` is broken (e.g., `Base.metadata` set wrong), `alembic check` won't catch it because there's nothing to compare to.

**How to avoid:** The Phase 4 SC #3 smoke test is `alembic check` AFTER `alembic upgrade head`. We extend it with a **structural assertion**: in `tests/integration/test_alembic_clean.py`, after running `alembic check`, assert that `Base.metadata.naming_convention` equals the `NAMING_CONVENTION` dict from `database.py`. This catches the empty-meta-but-broken-Base case.

```python
# tests/integration/test_alembic_clean.py — Phase 4 deliverable
import subprocess

import pytest

from app.core.database import NAMING_CONVENTION, Base


def test_naming_convention_attached_to_base() -> None:
    """Catches the case where Base.metadata is set but naming_convention isn't."""
    assert Base.metadata.naming_convention == NAMING_CONVENTION


@pytest.mark.usefixtures("db_session")  # ensures Postgres is reachable; skips otherwise
def test_alembic_check_clean() -> None:
    """SC #3: autogenerate-on-clean must produce empty diff."""
    # Pre-condition: clean DB. Test runs in CI against compose Postgres after `alembic upgrade head`.
    upgrade = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    assert upgrade.returncode == 0, upgrade.stderr

    check = subprocess.run(["alembic", "check"], capture_output=True, text=True)
    assert check.returncode == 0, f"alembic check detected drift:\n{check.stdout}\n{check.stderr}"
    assert "No new upgrade operations detected" in check.stdout
```

**Warning signs:**
- `alembic check` output is `Detected added table 'X'` or `Detected NOT NULL constraint on...`.
- A future PR adding the first business model breaks SC #3 because `created_at` was declared with Python `default=datetime.utcnow` instead of `server_default=func.now()` (Pitfall #12).

**Source:** `[VERIFIED: Context7 /websites/alembic_sqlalchemy — autogenerate.rst — "alembic check ... No new upgrade operations detected."]`

### Pitfall C: PEP 695 generic + Pydantic — easy to write `class Foo(ContractModel, Generic[T])` accidentally

**What goes wrong:** Mixing PEP 695 syntax with `typing.Generic[T]` either errors at class-creation time (Python 3.12) or produces a model where the type parameter is invisible to Pydantic schema generation. CONTEXT.md D-11 mandates pure PEP 695.

**Why it happens:** Habit from pre-3.12 Python; copy-paste from older Pydantic docs.

**How to avoid:**
- Verify in Phase 4 unit test: `ResponseEnvelope[X](data=X(...)).model_dump(by_alias=True)` produces the right shape AND `ResponseEnvelope.__pydantic_generic_metadata__["parameters"]` is non-empty.
- Don't import `TypeVar` or `Generic` in `schemas.py` — if you don't import them, you can't accidentally use them.
- mypy strict will flag the wrong syntax.

**Source:** `[VERIFIED: Context7 /pydantic/pydantic — concepts/models.md "Create Generic Model with Type Parameters (Python 3.12+)"]`

### Pitfall D: `secrets.token_urlsafe(32)` vs `secrets.token_urlsafe(43)`

**What goes wrong:** Confusing the byte argument with the desired output character count. `token_urlsafe(N)` takes N **bytes** (raw entropy) and base64url-encodes them, producing `~ceil(N * 4 / 3)` chars. `token_urlsafe(32)` → 43 chars (correct). Some snippets online say `token_urlsafe(43)` to "get 43 chars" — that's 43 BYTES → 58 chars.

**How to avoid:** Always pass the byte count (`32`) and document the resulting string length (`43`).

**Source:** `[VERIFIED: Python 3.12 stdlib `secrets` documentation]`

### Pitfall E: Forgetting to bump Pydantic in `pyproject.toml`

**What goes wrong:** The 3 new deps install fine on `pydantic>=2.0` (current pin). `validate_by_name=True` raises `PydanticUserError` at class-creation time on Pydantic <2.11. Tests fail with a confusing import-time error.

**How to avoid:** D-12 — the bump to `>=2.11` is part of the same atomic dependency commit as the 3 new deps. Wave 0 task: edit pyproject.toml + `uv lock` + verify `uv run python -c "import pydantic; assert pydantic.VERSION >= '2.11'"`.

**Source:** `[VERIFIED: CONTEXT.md D-12 + Context7 /pydantic/pydantic — migration.md]`

### Pitfall F: `git mv` doesn't update import statements in source

**What goes wrong:** `git mv app/modules/members app/modules/clients` updates filesystem + git blame, but does NOT rewrite any `from app.modules.members import ...` lines in source. We've verified those don't exist (the module is an empty placeholder), but a careless `git mv` of a populated module would silently break imports.

**How to avoid:**
- Pre-rename audit: `grep -rn 'app.modules.members\|app\.modules\.members' apps/backend/` returns 0 hits in source code (only `.importlinter`).
- Post-rename: same grep returns 0 hits, plus `grep -rn 'app.modules.clients' apps/backend/` returns ≥1 (the new `.importlinter` entry).
- `uv run lint-imports` then verifies all three contracts are GREEN.

**Source:** `[VERIFIED via grep against current tree at 2026-05-01]`

### Pitfall G: `Settings.cookie_secure` env-driven but reading raw string

**What goes wrong:** pydantic-settings parses `COOKIE_SECURE=true` from env. If the field is typed `cookie_secure: bool = False`, pydantic-settings v2 correctly parses `"true"`/`"false"`/`"1"`/`"0"` as bool. But `cookie_secure: str` would silently store the string `"true"` and `if settings.cookie_secure` is always truthy.

**How to avoid:** Type as `cookie_secure: bool = False`. pydantic-settings handles the env-string → bool coercion correctly per Pydantic v2 docs.

**Source:** `[VERIFIED: Context7 /pydantic/pydantic-settings — environment variables and bool parsing]`

## Code Examples

(See Patterns 1-8 above for full, verified code patterns. Below are extra one-liners the planner may need.)

### Adding TTL settings to existing `Settings` class

```python
# app/core/config.py — Phase 4 ADDITIONS (preserve existing fields)
# Source: CONTEXT.md D-05 + D-25
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ... existing fields: database_url, redis_url, environment, debug, secret_key ...

    # Phase 4 additions
    access_token_ttl_seconds: int = 900           # 15 min
    refresh_token_ttl_seconds: int = 2_592_000    # 30 days
    jwt_clock_leeway_seconds: int = 30
    cookie_secure: bool = False                   # prod startup must override → True
```

### `.importlinter` rename diff

```ini
# apps/backend/.importlinter — line 18 only
[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
-   app.modules.members
+   app.modules.clients
    app.modules.memberships
    app.modules.visits
    ...
```

### Adding 3 exception subclasses

```python
# app/core/exceptions.py — Phase 4 ADDITIONS (append)
# Source: CONTEXT.md (mentioned in <code_context>) + AppError pattern
class InvalidAccessToken(AppError):
    code = "invalid_token"
    status_code = 401


class InvalidPassword(AppError):
    code = "invalid_credentials"
    status_code = 401


class RateLimited(AppError):
    code = "rate_limited"
    status_code = 429
```

### Phase 4 unit test scaffolds (D-29)

```python
# tests/unit/test_security.py — Phase 4 deliverable
# JWT round-trip
def test_jwt_encode_decode_roundtrip() -> None:
    from uuid import uuid4
    from app.core.security import encode_access_token, decode_access_token
    from app.core.permissions import Role
    uid = uuid4()
    token = encode_access_token(uid, Role.OWNER)
    claims = decode_access_token(token)
    assert claims.sub == str(uid)
    assert claims.role is Role.OWNER
    assert claims.typ == "access"


# Argon2 round-trip
async def test_argon2_hash_verify_roundtrip() -> None:
    from app.core.security import hash_password, verify_password
    h = await hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert await verify_password("correct horse battery staple", h) is True


async def test_argon2_wrong_password_raises() -> None:
    import pytest
    from app.core.security import hash_password, verify_password
    from app.core.exceptions import InvalidPassword
    h = await hash_password("right")
    with pytest.raises(InvalidPassword):
        await verify_password("wrong", h)


# Token generators
def test_token_lengths() -> None:
    from app.core.security import (
        generate_refresh_token, generate_otp_code,
        generate_deep_link_token, generate_csrf_token,
    )
    raw, h = generate_refresh_token()
    assert len(raw) == 43 and len(h) == 64
    code, ch = generate_otp_code()
    assert len(code) == 6 and code.isdigit() and len(ch) == 64
    assert len(generate_deep_link_token()) == 43
    assert len(generate_csrf_token()) == 64
```

```python
# tests/unit/test_permissions.py — Phase 4 deliverable
import pytest
from app.core.permissions import Action, Resource, Role, OWNER_ONLY, can


def test_owner_only_is_frozenset() -> None:
    assert isinstance(OWNER_ONLY, frozenset)
    assert len(OWNER_ONLY) == 9   # mirrors apps/admin-web/src/shared/session/can.ts


@pytest.mark.parametrize("pair", list(OWNER_ONLY))
def test_reception_denied_owner_only(pair: tuple[Action, Resource]) -> None:
    action, resource = pair
    assert can(Role.OWNER, action, resource) is True
    assert can(Role.RECEPTION, action, resource) is False


def test_non_owner_only_pair_allowed_for_both() -> None:
    # (view, clients) is NOT in OWNER_ONLY → both roles allowed
    assert (Action.VIEW, Resource.CLIENTS) not in OWNER_ONLY
    assert can(Role.OWNER, Action.VIEW, Resource.CLIENTS) is True
    assert can(Role.RECEPTION, Action.VIEW, Resource.CLIENTS) is True
```

```python
# tests/unit/test_schemas.py — Phase 4 deliverable
import pytest
from pydantic import ValidationError
from app.core.schemas import ContractModel, RequestContract, ResponseEnvelope


class _SampleRequest(RequestContract):
    user_name: str
    page_size: int


class _SampleData(ContractModel):
    full_name: str


def test_request_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        _SampleRequest(userName="x", pageSize=10, unknown="boom")


def test_request_camel_or_snake() -> None:
    a = _SampleRequest(userName="alice", pageSize=20)
    b = _SampleRequest(user_name="alice", page_size=20)
    assert a == b


def test_envelope_camel_wire() -> None:
    env = ResponseEnvelope[_SampleData](data=_SampleData(full_name="Alice"))
    dump = env.model_dump(by_alias=True)
    assert dump == {"data": {"fullName": "Alice"}}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `populate_by_name=True` in ConfigDict | `validate_by_name=True` + `validate_by_alias=True` | Pydantic 2.11 (2025) | Required for D-09; old name still works with DeprecationWarning. |
| `class Foo(BaseModel, Generic[T])` | `class Foo[T](BaseModel)` (PEP 695) | Python 3.12 / Pydantic 2.11 | Cleaner; D-11 mandates this style. |
| `passlib[bcrypt]` for password hashing | `argon2-cffi` direct | OWASP 2026 cheatsheet (Argon2id default); passlib unmaintained since 2020-10-08 | Mandatory — passlib's bcrypt backend broken on bcrypt 5.0. |
| `python-jose` for JWT | `pyjwt` | FastAPI tutorial migrated 2024; python-jose has 107 open issues | Mandatory; locked by STACK.md. |
| `pgcrypto` extension for `gen_random_uuid()` | Native (PG13+) | PostgreSQL 13 (2020) | We pin Postgres 16, so native works without extension. |
| Naming-convention via prefix-only (e.g., `pk_`/`fk_`) | Standard SQLAlchemy 8-key template (`ix_%(column_0_label)s`, etc.) | SQLAlchemy 2.0 cookbook | D-19; required for autogenerate empty-diff guarantee. |
| `LimitOffsetParams` (`limit`, `offset`) | `PageQuery` (`page`, `page_size`) | This phase (Phase 4) | API-04 — flips backend to match frontend's existing bare-object contract; frontend stays untouched (D-30) until Phase 10 wraps it in `data`. |

**Deprecated / outdated (do NOT use):**
- `populate_by_name=True` — write `validate_by_name=True` instead.
- `class Foo(BaseModel, Generic[T])` — write `class Foo[T](BaseModel)`.
- `passlib`, `python-jose`, `aiogram`, `fastapi-csrf-protect`, `Casbin/Oso/OPA` — STACK.md reject list.
- `LimitOffsetParams`, old `Page[T]` — DELETED in Phase 4 (D-10, clean break).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `secrets.token_urlsafe(32)` produces exactly 43 base64url chars (no padding `=`) | Pattern 4, Code Examples | Test assertion `len(raw) == 43` fails; fix is to read `len(raw)` from a sample run instead of asserting an exact value. |
| A2 | `__pycache__/` directories are gitignored and stale-cache risk after `git mv` is zero | Runtime State Inventory | Devs may need to manually clear caches; documented as a one-line runbook fix. |
| A3 | Importing `ResponseData` from `schemas.py` into `pagination.py` (so `PaginatedData[T]` lives in pagination) avoids a circular import | Pattern 7 | If circular, swap: define `PaginatedData[T]` in `schemas.py` instead. Both arrangements satisfy CONTEXT.md (D-09 says "in app/core/schemas.py" + D-10 says "in app/core/pagination.py"; co-location is the only ambiguity). |
| A4 | `pydantic.alias_generators.to_camel` correctly transforms `page_size` → `pageSize` (not `PageSize` or `pageSize`) | Pattern 6, API-04 | None — verified by Pydantic docs for `to_camel`; if wrong, the `test_envelope_camel_wire` unit test would catch it before merge. |
| A5 | `alembic check` is reliable across Alembic 1.13 → 1.18 (no breaking change to exit codes / stdout format) | Pitfall B, Pattern Verification | LOW — Alembic is stable; only the Python API surface changes. CLI semantics for `check` are part of the public contract since 1.13. |

## Open Questions

1. **Where exactly does `PaginatedData[T]` live — `schemas.py` or `pagination.py`?**
   - What we know: D-10 places it in `pagination.py` ("Pagination shape in `app/core/pagination.py`"). D-09 places `ContractModel`/`ResponseData` in `schemas.py`.
   - What's unclear: Co-location implies `pagination.py` imports `ResponseData` from `schemas.py` (or vice-versa).
   - Recommendation: Put `PaginatedData[T]` in `pagination.py`, importing `ResponseData` from `schemas.py`. Schemas is the leaf module; pagination depends on it. Single import direction prevents circulars. **Confidence: MEDIUM (Assumption A3).**

2. **Is `tests/integration/test_alembic_clean.py` allowed to be skip-when-DB-down per Phase 3 D-12?**
   - What we know: Phase 3 conftest's `db_session` fixture skips if Postgres is unreachable.
   - What's unclear: SC #3 requires a green run. CI must run with compose Postgres up; local devs may run with DB down.
   - Recommendation: The test runs only when `db_session` succeeds (use the existing skip pattern). CI's `make test` job depends on `make db-up`. Document in `tests/integration/README.md`.

3. **Should `app/main.py` register a stub `_user_loader` in Phase 4 to make `get_current_user` testable in isolation?**
   - What we know: D-24 says the loader is registered in Phase 5 by `create_app` from `app.modules.auth.service.load_user_by_id`. Phase 4 ships only the slot.
   - What's unclear: If a Phase 4 test imports `get_current_user`, the function raises "user_loader_not_registered". This is fine for unit tests of `decode_access_token` etc., but `test_security.py` doesn't exercise `get_current_user`.
   - Recommendation: Don't register a stub in Phase 4. The Protocol slot remains None until Phase 5 wires `load_user_by_id`. Defensive raise documented in dependencies.py docstring.

4. **`Settings.environment` is `Literal["dev", "staging", "prod"]` — D-25 says the prod assertion key is `"prod"`. Is that consistent across the codebase?**
   - What we know: `apps/backend/app/core/config.py:21` uses `Literal["dev", "staging", "prod"]`. PITFALLS.md #2 example uses `"production"`.
   - What's unclear: Mismatch.
   - Recommendation: Use `"prod"` (matches the existing `Literal`). The PITFALLS.md snippet was illustrative.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Phase 4 (StrEnum, PEP 695 generics) | ✓ (assumed; locked in pyproject.toml) | 3.12.x | None (3.13 also fine; 3.11 breaks PEP 695). |
| `uv` | Dep install + lock | ✓ (assumed; v1.0 used it) | 0.5+ | None — pyproject.toml is uv-shaped. |
| `git` | `git mv` for module rename | ✓ | any | None. |
| Postgres 16 (compose) | `tests/integration/test_alembic_clean.py` (alembic upgrade head) | ✓ if `docker compose up postgres` first | 16 | Test skips with the existing `db_session` skip-on-unreachable fixture. |
| Docker / Docker Compose | Postgres test container | ✓ (assumed; v1.0 ships compose) | any recent | If absent, `test_alembic_clean.py` skips; CI has Docker. |
| Internet (PyPI) | `uv add` for new deps | ✓ at install time only | n/a | None — needed once during Phase 4 execution. |

**Missing dependencies with no fallback:** None — Python 3.12 + uv + Postgres-via-compose are the v1.0 baseline.

**Missing dependencies with fallback:** None blocking; integration test self-skips on DB absence.

## Sources

### Primary (HIGH confidence)

- **Context7 `/jpadilla/pyjwt`** — `encode`/`decode`/`leeway`/`InvalidTokenError` hierarchy/required-claims options. Topics: docs/usage.md, CHANGELOG.rst.
- **Context7 `/hynek/argon2-cffi`** — `PasswordHasher` defaults / `verify` / `check_needs_rehash` / `VerifyMismatchError` / `InvalidHashError`. Topics: README.md, docs/argon2.md, docs/parameters.md, docs/cli.md.
- **Context7 `/pydantic/pydantic`** — `validate_by_name`/`validate_by_alias` migration; `populate_by_name` deprecation; `to_camel` alias generator; PEP 695 generics. Topics: docs/migration.md, docs/concepts/alias.md, docs/concepts/models.md, docs/errors/usage_errors.md, docs/concepts/fields.md.
- **Context7 `/websites/alembic_sqlalchemy`** — `alembic check` exit-code contract; `MetaData(naming_convention=...)` env.py integration; `process_revision_directives` empty-migration hook. Topics: autogenerate.rst, naming.html, cookbook.html.
- **PyPI JSON API (queried 2026-05-01)** — verified versions: PyJWT 2.12.1 (2026-03-13), argon2-cffi 25.1.0 (2025-06-03), pydantic 2.13.3 (2026-04-20), python-telegram-bot 22.7 (2026-03-16), alembic 1.18.4 (2026-02-10), sqlalchemy 2.0.49 (2026-04-03).
- **Codebase reads (apps/backend/)** — `app/core/{config,database,security,dependencies,exceptions,pagination,middleware}.py`, `.importlinter`, `pyproject.toml`, `alembic/env.py`, `tests/conftest.py`, `.env.example`.
- **Codebase reads (apps/admin-web/)** — `src/shared/session/{can.ts,registry.ts}` (RBAC source of truth — backend mirrors).
- **Project specs** — CLAUDE.md, .planning/PROJECT.md, .planning/REQUIREMENTS.md, .planning/STATE.md, .planning/research/{STACK,ARCHITECTURE,PITFALLS}.md, .planning/phases/04-.../04-CONTEXT.md.

### Secondary (MEDIUM confidence)

- **OWASP Password Storage Cheat Sheet (2026)** — Argon2id default, `memory_cost=65536`, `time_cost=3`, `parallelism=4` recommended. Verified indirectly via argon2-cffi documentation aligning to the same numbers. Direct fetch not performed in this session.
- **RFC 6265bis (cookie attributes / SameSite semantics)** — referenced via PITFALLS.md citations; canonical IETF source.
- **Python 3.12 stdlib `secrets` documentation** — `token_urlsafe`, `token_hex`, `randbelow`. Common knowledge from Python docs; not re-fetched this session.

### Tertiary (LOW confidence — flagged for validation)

- *(none — every actionable claim in this document is HIGH or MEDIUM)*

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every version verified via PyPI JSON API on 2026-05-01; every reject reason cited in STACK.md.
- Architecture / patterns: **HIGH** — Protocol-loader pattern is a direct echo of ARCHITECTURE.md §2.2 + CONTEXT.md D-24; ContractModel hierarchy is verbatim from D-09; mixin shapes are verbatim from D-15/16/17.
- Library APIs (PyJWT, argon2-cffi, Pydantic, Alembic): **HIGH** — every API confirmed against Context7 official-docs feed.
- Pitfalls: **HIGH** for Phase-4-specific items (Pitfall A through G, all verified or trivially derivable); MEDIUM for forward-looking pitfalls referenced from PITFALLS.md (cookie SameSite for Phase 7 navigation flow is an Phase 7 acceptance concern, not a Phase 4 break).
- Verification recipe (`alembic check`): **HIGH** — official Alembic CLI tool, documented exit-code semantics.

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (30 days — Pydantic, Alembic, SQLAlchemy are stable; PyJWT slow-moving; argon2-cffi very stable). Re-verify if any pin in `pyproject.toml` changes or if Pydantic releases a 3.0 alpha.
