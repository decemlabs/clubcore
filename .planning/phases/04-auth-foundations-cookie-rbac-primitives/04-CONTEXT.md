# Phase 4: Auth Foundations & Cookie/RBAC Primitives - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Land all cross-cutting primitives (JWT, Argon2, cookie matrix, RBAC enums + matrix in `core`, Alembic naming convention, ORM mixins, ResponseEnvelope + ProblemDetails contract, `members` → `clients` rename) **before** the first business migration so they cannot be retrofitted later.

**No endpoints, no DB migrations, no auth flow** in Phase 4 — those land in Phase 5 (email/password auth) and Phase 8 (clients). Phase 4 ships:

1. **Foundations** — `MetaData(naming_convention=...)` on `Base`; `UUIDPkMixin` / `TimestampMixin` / `SoftDeleteMixin` in `app/core/database.py`.
2. **Module rename** — `git mv app/modules/members → app/modules/clients`; `.importlinter` `modules-independent` updated.
3. **Security helpers** — `app/core/security.py` filled with PyJWT HS256 encode/decode, Argon2id `hash_password`/`verify_password` via `asyncio.to_thread`, OTP code generator (`secrets.randbelow`) and deep-link token generator (`secrets.token_urlsafe(32)`); raw codes never persisted, only `sha256(code)`.
4. **Cookie matrix helper** — emit `sz_access` (Path=`/`, Max-Age=900, httpOnly, SameSite=Lax) + `sz_refresh` (Path=`/api/v1/auth`, Max-Age=2592000, httpOnly, SameSite=Lax) + `sportzal_csrf` (32-byte hex, non-httpOnly, SameSite=Lax, Secure env-driven). `Secure` env-driven with prod assertion.
5. **RBAC primitives in `core`** — `app/core/permissions.py` with `Role` / `Action` / `Resource` `StrEnum`s, `OWNER_ONLY: frozenset[tuple[Action, Resource]]`, `can(role, action, resource)` byte-mirroring `apps/admin-web/src/shared/session/can.ts`.
6. **Wire format contract** — `app/core/schemas.py` introduces a backend-first contract hierarchy: `ContractModel` / `RequestContract` / `ResponseData` / `ResponseEnvelope[T]` / `ProblemDetails`. All future endpoints return `{ "data": <payload> }` on success (HTTP 2xx); errors stay top-level `{ code, message, fields? }` per existing `AppError` handler.
7. **Pagination contract flip** — replace `LimitOffsetParams` + `Page[T]` (v1.0 limit/offset) with `PageQuery` (page/pageSize) + `PaginatedData[T]` (items/total/page/pageSize) in `app/core/pagination.py`.
8. **Pinned deps** — `apps/backend/pyproject.toml` adds `pyjwt>=2.12.1,<3`, `argon2-cffi>=25.1.0,<26`, `python-telegram-bot>=22.7,<23`; bump `pydantic>=2.11,<3` (required for `validate_by_name` / `validate_by_alias`); `uv lock` regenerated.

**In scope (Phase 4 REQ-IDs):** INFRA-01, INFRA-02, INFRA-05, INFRA-07, AUTH-01, AUTH-02, AUTH-03, AUTH-04, CSRF-01, RBAC-01, API-03, API-04.

**Out of scope (deferred to later phases):**
- Any HTTP endpoint, including `/auth/*` (Phase 5/7) and `/clients/*` (Phase 8).
- DB migrations creating business tables (`users`/`refresh_tokens`/`otp_codes` → Phase 5; `clients`/`audit_log` → Phase 8). Phase 4's only Alembic interaction is the **autogenerate-on-clean** smoke check (must produce empty diff after `MetaData(naming_convention=...)` lands).
- `require_permission` dependency wiring on routes (Phase 6 — RBAC-02..05).
- CSRF dependency `verify_csrf` (Phase 6 — CSRF-02).
- Frontend `apps/admin-web/src/shared/api/contracts/_README.md` and mock-service updates to consume `ResponseEnvelope[T]` — explicitly deferred to **Phase 10** (admin-web Auth + Clients Wiring) per user decision; backend ships envelope contract first.
- OpenAPI export script + `openapi.json` (Phase 9).

</domain>

<decisions>
## Implementation Decisions

### JWT design

- **D-01 [LOCKED]:** **Single secret.** Use existing `settings.secret_key` (Pydantic `SecretStr`) for both access and refresh JWT signing. Phase 4 does not split into `jwt_access_secret` / `jwt_refresh_secret` — pet-project on 1 zal; rotation goes one shot. Refactor to split is non-breaking later (add new fields to `Settings`, accept old key during cutover).
- **D-02 [LOCKED]:** **Access token claims = `{sub, role, typ, iat, exp}`.** `sub = str(user_uuid)`; `role: Role` (StrEnum value, e.g. `"owner"`); `typ = "access"`; `iat`/`exp` UTC epoch seconds. `role` is **embedded** so `require_permission` does not need a DB round-trip per request — staleness mitigated by 15-min access TTL + session-revoke on role change. NOT included in Phase 4: `jti`, `iss`, `aud` (can be added later without breaking decode).
- **D-03 [LOCKED]:** **Refresh token = opaque `secrets.token_urlsafe(32)`**, NOT a JWT. Phase 5 will store `sha256(token)` in `refresh_tokens.token_hash` with `family_id` / `user_id` / `expires_at` / `revoked_at` columns. Rationale: opaque tokens give simpler revocation semantics (lookup-by-hash), avoid claim-vs-DB drift, and family-rotation is naturally DB-led. Decode is hash compare, not signature verify.
- **D-04 [LOCKED]:** **JWT algorithm = HS256 with 30s clock leeway.** Locked by AUTH-01. Not RS256/ES256 (no key-distribution problem in single-process monolith).
- **D-05 [LOCKED]:** **TTL constants live in `Settings` (env-driven), not module constants.** Add to `app/core/config.py`: `access_token_ttl_seconds: int = 900`, `refresh_token_ttl_seconds: int = 2592000`, `jwt_clock_leeway_seconds: int = 30`. `.env.example` documents defaults; staging/prod can tune without code edits.
- **D-06 (Discretion):** **Helper signatures in `app/core/security.py`.**
  - `encode_access_token(user_id: UUID, role: Role, *, now: datetime | None = None) -> str` — convenience wrapper around `jwt.encode`.
  - `decode_access_token(token: str) -> AccessTokenClaims` — `AccessTokenClaims` is a `dataclass` or `TypedDict` with the 5 claim fields; raises `InvalidAccessToken` (subclass of `AppError`, status 401, code `invalid_token`) on `jwt.InvalidTokenError` / `jwt.ExpiredSignatureError`.
  - `generate_refresh_token() -> tuple[str, str]` — returns `(raw_token, sha256_hash)`; only the hash is ever persisted.
  - `generate_otp_code() -> tuple[str, str]` — returns `(raw_6_digit_code, sha256_hash)`; raw is sent to Telegram, hash is stored.
  - `generate_deep_link_token() -> str` — `secrets.token_urlsafe(32)`.

### Pydantic schema base + wire format contract

- **D-07 [LOCKED]:** **Backend-first contract — `ResponseEnvelope[T]` wraps every success response.** Successful 2xx responses always serialize to `{ "data": <payload> }`. This is a deliberate departure from the v1.0 frontend mock contract (bare `{items, total, page, pageSize}`); the frontend will adapt in Phase 10 (mocks + `apps/admin-web/src/shared/api/contracts/_README.md` rewrite). Rationale: backend defines a stable, typed contract; frontend conforms; future fields (`requestId`, `traceId`, `meta`, `warnings`) extend the envelope without breaking consumers.
- **D-08 [LOCKED]:** **Errors stay top-level**, NOT in envelope. Error body is `{ code: str, message: str, fields?: dict | null }` — exact shape already emitted by `app/core/exceptions.py:_app_error_handler`. HTTP status code carries success/error discrimination. RFC 7807-flavored.
- **D-09 [LOCKED]:** **Class hierarchy in `app/core/schemas.py` (NEW file):**

  ```python
  from pydantic import BaseModel, ConfigDict
  from pydantic.alias_generators import to_camel

  class ContractModel(BaseModel):
      """Base for every API contract model. camelCase wire, snake_case Python."""
      model_config = ConfigDict(
          alias_generator=to_camel,
          validate_by_name=True,
          validate_by_alias=True,
          from_attributes=True,
          extra="ignore",
      )

  class RequestContract(ContractModel):
      """Inbound request body / query params. Strict on extras."""
      model_config = ConfigDict(
          alias_generator=to_camel,
          validate_by_name=True,
          validate_by_alias=True,
          extra="forbid",
      )

  class ResponseData(ContractModel):
      """Payload inside ResponseEnvelope. Subclassed by every domain response DTO."""

  class ResponseEnvelope[T](ContractModel):
      """Success transport wrapper. Phase 4: { data: T }. Future fields optional."""
      data: T

  class ProblemDetails(ContractModel):
      """Error response body (matches AppError handler output, used as response_model in OpenAPI)."""
      code: str
      message: str
      fields: dict[str, object] | None = None
  ```

- **D-10 [LOCKED]:** **Pagination shape in `app/core/pagination.py` (REWRITE):**

  ```python
  class PageQuery(RequestContract):
      page: int = Field(default=1, ge=1)
      page_size: int = Field(default=20, ge=1, le=100)  # → pageSize on wire

  class PaginatedData[T](ResponseData):
      items: list[T]
      total: int
      page: int
      page_size: int  # → pageSize on wire
  ```

  Endpoints return `ResponseEnvelope[PaginatedData[ClientResponse]]` for lists, `ResponseEnvelope[ClientResponse]` for single resources. Old `LimitOffsetParams` and v1.0 `Page[T]` (limit/offset shape) are **deleted** (clean break — no v1.0 consumers exist; only `/healthz` which doesn't paginate).

- **D-11 [LOCKED]:** **Generics — PEP 695, NOT `typing.Generic[T]`.** Existing `app/core/pagination.py` already uses PEP 695 (`class Page[T]`); Python 3.12 is hard-pinned in `pyproject.toml`; Pydantic 2.11+ supports PEP 695 generics natively. No `TypeVar` / `Generic` import.
- **D-12 [LOCKED]:** **Pydantic version bump: `pydantic>=2.11,<3`** (required for `validate_by_name=True` + `validate_by_alias=True`, which deprecated `populate_by_name=True` in 2.11). `uv lock` regenerated.
- **D-13 [LOCKED]:** **Phase 4 envelope is `{ data: T }` only — minimum viable.** Optional fields (`requestId`, `traceId`, `meta`, `warnings`) deferred. When added, all become `Optional[...] = None` so existing clients ignore them.
- **D-14 (Discretion):** **`ResponseEnvelope[T]` is set as `response_model` on every route**, not added by middleware. Routes return `ResponseEnvelope[X](data=...)` explicitly. Reasoning: keeps OpenAPI schema honest, types flow through TS codegen (Phase 9), no magic. A small helper `def envelope(payload: T) -> ResponseEnvelope[T]` in `app/core/schemas.py` is acceptable but not mandatory.

### ORM mixins (in `app/core/database.py`)

- **D-15 [LOCKED]:** **`UUIDPkMixin` uses Postgres-native `gen_random_uuid()`** via `mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))`. PG13+ provides this without `pgcrypto`. INSERT without explicit `id` returns the generated UUID via `RETURNING`. Phase 5+ seed scripts and tests do NOT pass `id=` on insert.
- **D-16 [LOCKED]:** **`TimestampMixin` uses `func.now()` server-side**, both on insert and on update:

  ```python
  created_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True), nullable=False, server_default=func.now()
  )
  updated_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True), nullable=False,
      server_default=func.now(), onupdate=func.now()
  )
  ```

  `TIMESTAMPTZ` (timezone=True) — never naive. App clock drift / multi-instance scenarios remain consistent because the DB is the source of truth.

- **D-17 [LOCKED]:** **`SoftDeleteMixin` uses a partial index `WHERE deleted_at IS NULL`** rather than a plain index on `deleted_at`. The mixin emits both the column (`deleted_at: Mapped[datetime | None]`, nullable, default None) and the partial index via `__table_args__` extension hook (since mixins compose into a model's `__table_args__`, document the contract: business models that subclass `SoftDeleteMixin` must merge the mixin's index helper into their `__table_args__`). Aligns with CLIENTS-02 partial-unique-on-phone semantics. Plain index on full `deleted_at` is **not** added — query patterns are `WHERE deleted_at IS NULL` (alive-bias) via `list_alive` / `get_alive` repository helpers (Phase 8 CLIENTS-09).
- **D-18 (Discretion):** **Mixins do NOT subclass `Base`** — they are plain classes with `mapped_column` declarations. Models compose: `class User(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin): ...`. Same pattern as SQLAlchemy 2.0 documentation cookbook.

### Alembic + DB foundations

- **D-19 [LOCKED]:** **`MetaData(naming_convention=...)` uses standard SA template** (not custom prefix):

  ```python
  NAMING_CONVENTION = {
      "ix": "ix_%(column_0_label)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }

  class Base(DeclarativeBase):
      metadata = MetaData(naming_convention=NAMING_CONVENTION)
  ```

  Verified: autogenerate-on-clean must produce empty diff (Phase 4 SC #3) — standard template + zero-models is the only way this gate passes deterministically.

- **D-20 [LOCKED]:** **Module rename `app/modules/members` → `app/modules/clients`** is done via `git mv` (preserves file history for the `__init__.py` placeholder). `.importlinter` `modules-independent` contract updates the entry from `app.modules.members` to `app.modules.clients`. `lint-imports` must stay GREEN after the rename (one of the four Phase 4 SC checks).

### RBAC primitives

- **D-21 [LOCKED]:** **`OWNER_ONLY: frozenset[tuple[Action, Resource]]`** (immutable, set-membership lookup in `can()`). Phase 6 parity test reads `apps/admin-web/src/shared/session/can.ts` (regex extract on the literal array) and asserts `set(backend_pairs) == set(frontend_pairs)` — order-independent. Verbatim mirror of the 9 entries in `can.ts`.
- **D-22 [LOCKED]:** **`Role` / `Action` / `Resource` are `StrEnum`s** (Python 3.11+). String values match `apps/admin-web/src/shared/session/registry.ts`:
  - `Role`: `"owner"` / `"reception"`
  - `Action`: `"view"` / `"create"` / `"edit"` / `"delete"` / `"refund"`
  - `Resource`: 11 values from frontend `Resource` type — `"dashboard"` / `"clients"` / `"schedule"` / `"staff"` / `"finance"` / `"reports"` / `"payroll"` / `"compensation"` / `"templates"` / `"settings"` / `"owner-area"`
- **D-23 [LOCKED]:** **`can()` body — short-circuit owner, blacklist reception:**

  ```python
  def can(role: Role, action: Action, resource: Resource) -> bool:
      if role is Role.OWNER:
          return True
      return (action, resource) not in OWNER_ONLY
  ```

  Byte-for-byte semantic match with `apps/admin-web/src/shared/session/can.ts`.

- **D-24 (Discretion):** **`get_current_user` and `require_permission` dependencies are scaffolded in Phase 4 as Protocol-based stubs** to keep `import-linter` `modules-independent` clean — full wiring with the registered loader (`app.modules.auth.service.load_user_by_id`) happens in Phase 5/6 when User exists. Phase 4 ships:
  - `class CurrentUser(Protocol)` in `app/core/dependencies.py` — minimal shape: `id: UUID`, `role: Role`.
  - `def register_user_loader(loader: Callable[[UUID], Awaitable[CurrentUser | None]]) -> None` — module-level setter writing to a `_loader` slot.
  - `async def get_current_user(...) -> CurrentUser` — reads `sz_access` cookie, decodes JWT, calls registered `_loader(user_id)`. Raises 401 if no loader registered (defensive — composition root MUST register before request).
  - `def require_permission(action: Action, resource: Resource) -> Callable[..., Awaitable[CurrentUser]]` — returns a dependency callable that resolves `current_user` and asserts `can(current_user.role, action, resource)`; raises `ForbiddenError` on fail.

### Cookie + CSRF emission

- **D-25 (Discretion):** **Cookie helper API in `app/core/security.py`** (cookies are part of the security primitives, not a separate module — keeps Phase 4 surface small):

  ```python
  def issue_session_cookies(
      response: Response,
      *,
      access_token: str,
      refresh_token: str,
      csrf_token: str,
      secure: bool,  # from settings.cookie_secure
  ) -> None:
      """Set sz_access + sz_refresh + sportzal_csrf with the locked attributes."""
  ```

  `secure` flag comes from a new `Settings.cookie_secure: bool = False` (defaults dev-friendly; **prod startup assertion** in `app.main.create_app` raises if `environment == "prod" and not cookie_secure`). Same helper handles all three cookies to ensure consistent SameSite/Path/Max-Age across emission sites (Phase 5 login, Phase 5 refresh, Phase 7 OTP verify).

- **D-26 (Discretion):** **`generate_csrf_token() -> str`** in `app/core/security.py` — returns `secrets.token_hex(32)` (32-byte hex per CSRF-01). `sportzal_csrf` cookie attributes locked: non-httpOnly (frontend reads it for `X-CSRF-Token` header), `Secure` env-driven, `SameSite=Lax`, no `Path` restriction (frontend reads on all navigations). The CSRF token is regenerated on each successful login/refresh/OTP-verify (Phase 5/7) to invalidate old values.

### Argon2id parameter policy

- **D-27 (Discretion):** **Use `argon2-cffi` library defaults** (`PasswordHasher()` with no args) for Phase 4. The library's defaults follow OWASP 2026 guidance (`memory_cost=65536` KiB, `time_cost=3`, `parallelism=4`) and tune to ~50–100ms on typical hardware — safe lower bound. **Wrap in `asyncio.to_thread`** per AUTH-02. `verify_password` uses `PasswordHasher.verify()` and **also calls `PasswordHasher.check_needs_rehash()`** — if true, the caller is expected to rehash and update the stored hash (Phase 5 login flow logs an audit event and writes the new hash). This auto-handles future parameter bumps without breaking existing accounts.
- **D-28 (Discretion):** **`hash_password` / `verify_password` raise `InvalidPassword` (AppError subclass, code `invalid_credentials`, status 401) on `argon2.exceptions.VerifyMismatchError`** so callers don't have to catch library-specific exceptions. Timing-equivalence (AUTH-EP-02) is achieved by always running a hash verification even on user-not-found (Phase 5 service uses a sentinel hash for missing-email path).

### Phase 4 verification (no endpoints exist)

- **D-29 (Discretion):** **Verification is import-introspection + Alembic smoke**, not integration tests. Concretely:
  - `tests/unit/test_security.py` — unit tests for JWT round-trip (encode → decode → claims match), Argon2 round-trip (hash → verify → True; verify wrong → InvalidPassword), OTP code length/charset (6 digits), deep-link token length (43 chars after token_urlsafe(32) → base64url).
  - `tests/unit/test_permissions.py` — every `OWNER_ONLY` pair → reception denied, owner allowed; non-`OWNER_ONLY` pair → both allowed; `OWNER_ONLY` is a `frozenset` instance.
  - `tests/unit/test_schemas.py` — `RequestContract` with `extra='forbid'` raises ValidationError on extra; `ContractModel` round-trip with snake/camel both validate; `ResponseEnvelope[X](data=X(...)).model_dump(by_alias=True)["data"]` shape matches; `PaginatedData[X]` serialization has `pageSize` on wire and `page_size` in Python.
  - `tests/integration/test_alembic_clean.py` — Alembic `upgrade head` against clean compose Postgres + autogenerate-on-clean → empty diff (Phase 4 SC #3). Wraps existing Phase 3 conftest pattern.
  - **Manual / one-shot:** `uv run lint-imports` GREEN after rename + `from app.core.permissions import Role, Action, Resource, OWNER_ONLY, can` succeeds (Phase 4 SC #1, #4 — checked once during execution, not a permanent test).

### Frontend sync deferral

- **D-30 [LOCKED]:** **Phase 4 does NOT touch `apps/admin-web`.** Frontend mock contract (`apps/admin-web/src/shared/api/contracts/_README.md` line "Pagination: every list returns `{ items, total, page, pageSize }`"), mock implementations in `apps/admin-web/src/shared/api/services/mock/`, and any consumer hooks all stay on the bare-object contract until Phase 10. Phase 10's responsibility (FE-01..FE-07) extends to:
  - Update `_README.md`: every success response is `{ data: <payload> }`; pagination payloads stay `{ items, total, page, pageSize }` *inside* `data`.
  - Update mock services to wrap return values.
  - Update `packages/api-client/src/fetcher.ts` (Phase 9) to unwrap `.data` before resolving — error path stays top-level.
  - Update domain hooks consuming services if any access response shape directly (most go through Zod contracts, so the change is centralized).

  **PROJECT.md / CLAUDE.md "Frontend integrity" clause needs a one-line update before Phase 10**: frontend mocks/contracts/services may be revised in Phase 10 to consume the backend ResponseEnvelope contract (UI internals — components, routes, theme — still frozen). This is a Phase 10 housekeeping task, NOT Phase 4's job.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock (Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog), package naming `app`, modular-monolith layout, RU/CIS regional constraints (Stripe forbidden, ЮKassa-only, Telegram primary), frontend integrity rule (note: relaxed for Phase 10 service/contract layer per D-30).
- `.planning/PROJECT.md` — milestone scope, architectural invariants (`core ⊥ modules`, `modules` not importing each other, `integrations ⊥ modules`), key decisions table.
- `.planning/REQUIREMENTS.md` — Phase 4 owns these REQ-IDs (every plan task must trace): `INFRA-01`, `INFRA-02`, `INFRA-05`, `INFRA-07`, `AUTH-01`, `AUTH-02`, `AUTH-03`, `AUTH-04`, `CSRF-01`, `RBAC-01`, `API-03`, `API-04`. Other AUTH/CSRF/RBAC/API IDs belong to Phases 5/6/7/9.
- `.planning/ROADMAP.md` Phase 4 section — goal, dependency on Phase 3, five numbered success criteria (developer can `from app.core.permissions import ...`; security helpers callable; alembic autogenerate-on-clean empty; `members` → `clients` renamed and import-linter green; `Page[T]` shape flipped + camelCase wire).

### Cross-phase context (load-bearing)
- `.planning/phases/03-tests-dev-infrastructure-documentation/03-CONTEXT.md` — Phase 3 D-08 (`conventions.md ## Testing` reference shape — Phase 4 unit tests follow the same pytest-asyncio + ASGITransport idioms); D-10/D-11/D-12 (test fixtures + db_session pattern); D-15 (`asgi-lifespan>=2.1` already in dev-deps).
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-CONTEXT.md` — Phase 2 D-00 (canonical FastAPI patterns), D-06/D-07/D-08 (lifespan-managed engine, factory pattern), D-12/D-13 (AppError hierarchy and handler — Phase 4's `InvalidAccessToken` / `InvalidPassword` / `ForbiddenError` extend `AppError`), D-14 (`/healthz` at root via empty-prefix v1 router — Phase 4 does NOT add new endpoints, but the v1 router prefix flip to `/api/v1` is documented as Phase 5+ TODO), D-15 (`Settings` shape — Phase 4 extends with `access_token_ttl_seconds`, `refresh_token_ttl_seconds`, `jwt_clock_leeway_seconds`, `cookie_secure`).
- `.planning/phases/01-monorepo-restructure-frontend-move/01-CONTEXT.md` — `apps/backend/` location, monorepo layout.

### Research files (consulted, must read by planner/researcher)
- `.planning/research/STACK.md` — dependency choices, version pins, reject list (`passlib`, `python-jose`, `authlib`, `aiogram`, `fastapi-csrf-protect`, `Casbin/Oso/OPA`).
- `.planning/research/FEATURES.md` — table-stakes / differentiator / anti-feature breakdown for the milestone.
- `.planning/research/ARCHITECTURE.md` — file-and-function-level layout for v1.1; cross-module RBAC pattern with code samples (Protocol + registered loader); pyproject diff.
- `.planning/research/PITFALLS.md` — 32 pitfalls; Phase 4 directly addresses #1 (SameSite for Telegram return), #2 (Secure flag in dev), #5 (plaintext refresh in Redis — refresh stored hashed), #11 (Alembic naming convention), #12 (UUID PK strategy), #19 (RBAC `core ⊥ modules`), #25 (camelCase wire), #32 (composition root for cross-module callbacks).
- `.planning/research/SUMMARY.md` — synthesis: HIGH confidence merged build order; Phase 4 (this) = "Auth Foundations" / Phase 1 in research nomenclature.

### Source files Phase 4 directly reads or mutates
- `apps/backend/app/core/database.py` — extend with `MetaData(naming_convention=...)`, `UUIDPkMixin`, `TimestampMixin`, `SoftDeleteMixin`. Existing `Base`/`db_lifespan`/`get_db` preserved.
- `apps/backend/app/core/security.py` — currently a placeholder docstring; fill with PyJWT helpers, Argon2 helpers, code/token generators, cookie emission helper.
- `apps/backend/app/core/dependencies.py` — currently empty; add `CurrentUser` Protocol, `register_user_loader`, `get_current_user`, `require_permission` (stubs that work even before Phase 5 wires the loader).
- `apps/backend/app/core/exceptions.py` — extend with `InvalidAccessToken`, `InvalidPassword`, `RateLimited` (subclasses of `AppError`).
- `apps/backend/app/core/config.py` — add `access_token_ttl_seconds`, `refresh_token_ttl_seconds`, `jwt_clock_leeway_seconds`, `cookie_secure` fields.
- `apps/backend/app/core/permissions.py` — NEW. `Role`/`Action`/`Resource` StrEnums, `OWNER_ONLY` frozenset, `can()`.
- `apps/backend/app/core/schemas.py` — NEW. `ContractModel` / `RequestContract` / `ResponseData` / `ResponseEnvelope[T]` / `ProblemDetails`.
- `apps/backend/app/core/pagination.py` — REWRITE. `PageQuery`, `PaginatedData[T]`. Old `LimitOffsetParams` and old `Page[T]` removed.
- `apps/backend/app/modules/members/` — `git mv` to `apps/backend/app/modules/clients/`.
- `apps/backend/.importlinter` — replace `app.modules.members` with `app.modules.clients` in `modules-independent` contract.
- `apps/backend/pyproject.toml` — add `pyjwt`, `argon2-cffi`, `python-telegram-bot`; bump `pydantic>=2.11,<3`; `uv lock` regenerated.
- `apps/backend/.env.example` — add `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`, `JWT_CLOCK_LEEWAY_SECONDS`, `COOKIE_SECURE` with dev defaults.
- `apps/backend/alembic/env.py` — verify `target_metadata = Base.metadata` picks up the new naming convention without code changes.
- `apps/backend/tests/unit/test_security.py` — exists as Phase 3 placeholder; Phase 4 fills with JWT/Argon2/code-gen tests.
- `apps/backend/tests/unit/test_permissions.py`, `test_schemas.py` — NEW.
- `apps/backend/tests/integration/test_alembic_clean.py` — NEW. autogenerate-on-clean smoke (SC #3).

### Frontend reference (READ-ONLY in Phase 4)
- `apps/admin-web/src/shared/session/can.ts` — source of truth for `OWNER_ONLY`. Backend `OWNER_ONLY` is a byte-for-byte mirror. Parity test (Phase 6 — TEST-06) reads this file.
- `apps/admin-web/src/shared/session/registry.ts` — source of truth for `Resource` type and string values. Backend `Resource` StrEnum mirrors this exactly.
- `apps/admin-web/src/shared/api/contracts/_README.md` — current bare-object contract; Phase 4 does NOT modify this file. Phase 10 does (per D-30).

### External docs (consulted during research/planning)
- PyJWT docs (https://pyjwt.readthedocs.io/) — `encode` / `decode` / `InvalidTokenError` hierarchy / `leeway` parameter.
- argon2-cffi docs (https://argon2-cffi.readthedocs.io/) — `PasswordHasher` defaults, `verify`, `check_needs_rehash`.
- Pydantic v2.11 release notes — `validate_by_name` / `validate_by_alias` (replacing `populate_by_name`).
- SQLAlchemy 2.0 ORM docs — `MappedAsDataclass` not used, plain `Mapped` + `mapped_column` per Phase 2 D-08; mixin composition cookbook; `MetaData(naming_convention=...)` reference.
- Alembic docs — autogenerate naming-convention guarantee.
- OWASP ASVS 2024 + NIST 800-63B 2024 — password policy (12-char min, no complexity rules, no forced rotation), account lockout (rejected — DoS amplifier).
- RFC 6265bis — cookie attributes, SameSite semantics.
- RFC 7807 — Problem Details for HTTP APIs (informs `ProblemDetails` shape, though we keep our `{code, message, fields?}` rather than `{type, title, status, detail, instance}` to match existing `AppError` handler).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`apps/backend/app/core/exceptions.py:AppError`** — already emits `{code, message, fields}`. Phase 4 `InvalidAccessToken`, `InvalidPassword`, `RateLimited`, `ForbiddenError` (already exists) all subclass `AppError`. The `_app_error_handler` JSON response shape IS `ProblemDetails` — no behavior change, just new Pydantic schema documenting it for OpenAPI.
- **`apps/backend/app/core/database.py:Base`** — already a `DeclarativeBase` subclass; Phase 4 attaches `metadata = MetaData(naming_convention=...)` directly on this class. No new `Base` introduced.
- **`apps/backend/app/core/database.py:db_lifespan`** — unchanged. Engine + sessionmaker creation works as-is.
- **`apps/backend/app/core/config.py:Settings`** — already has `secret_key: SecretStr`. Phase 4 reuses it as JWT secret (D-01); adds 4 new TTL/cookie fields.
- **`apps/backend/app/core/middleware.py:RequestIdMiddleware`** — emits `x-request-id` header. Phase 4 does NOT extend envelope to include `requestId` yet (D-13), but the future hook is ready.
- **`apps/backend/app/core/pagination.py`** — currently `LimitOffsetParams` + `Page[T]` (limit/offset). Phase 4 rewrites this file with `PageQuery` + `PaginatedData[T]` — clean break, no consumers exist.
- **`apps/backend/app/modules/members/__init__.py`** — empty placeholder; `git mv` to `clients` preserves blame even though it's a single line.
- **`apps/backend/.importlinter`** — three contracts already enforced. Phase 4 only changes one entry (`app.modules.members` → `app.modules.clients`).
- **`apps/backend/tests/conftest.py`** (Phase 3) — `app` / `async_client` / `db_session` fixtures. Phase 4 unit tests are pure-Python (no fixtures needed); the alembic-clean integration test reuses Phase 3's compose Postgres pattern.
- **`apps/backend/alembic/env.py`** (Phase 2) — `target_metadata = Base.metadata` already correctly captures whatever metadata is attached at import time. Phase 4's naming convention applies automatically once `Base.metadata = MetaData(naming_convention=...)` lands.

### Established patterns to honor
- **Factory pattern, no module-level `app`** (Phase 2 main.py docstring) — Phase 4 keeps composition root in `create_app()`. Future `register_user_loader(...)` call lands in `create_app()` in Phase 5.
- **Lifespan-managed engine** (Phase 2 D-06/D-08) — Phase 4 does not add session creation paths outside lifespan.
- **`core ⊥ modules`** (importlinter) — Phase 4's `app/core/permissions.py`, `app/core/schemas.py`, `app/core/dependencies.py` MUST NOT import from `app.modules.*`. The Protocol-based loader pattern (D-24) is the architectural answer.
- **Mixed-language docs** (Phase 3 D-05) — Phase 4 does NOT ship docs (no doc deliverables in REQ-IDs); planning artifacts (PLAN.md / SUMMARY.md) follow established Russian-narrative + English-code style.
- **No multi-tenancy / no `tenant_id`** — Phase 4's `User` shape (Phase 5 lands the model) has no `tenant_id`. Permanent constraint per PROJECT.md Out of Scope.
- **PEP 695 generics** — established in `app/core/pagination.py:Page[T]`; Phase 4 continues this style for `ResponseEnvelope[T]` and `PaginatedData[T]`.

### Integration points
- **Phase 5 (User Schema + Email/Password Auth)** — uses every Phase 4 primitive: `Role`/`Action`/`Resource` enums in `User.role` column; `encode_access_token`/`decode_access_token` in login/refresh services; `hash_password`/`verify_password` in seed + login; `generate_refresh_token` in token issue path; `issue_session_cookies` in login response; `register_user_loader(load_user_by_id)` call in `create_app()`. Mixins compose `User(Base, UUIDPkMixin, TimestampMixin)` (no soft-delete on users), `RefreshToken(Base, UUIDPkMixin)`, `OtpCode(Base, UUIDPkMixin)`.
- **Phase 6 (RBAC Wiring + Parity Tests)** — uses `require_permission` dependency on every business route; parity test (TEST-06) reads `OWNER_ONLY` from `app.core.permissions` and `apps/admin-web/src/shared/session/can.ts`; introspection test (TEST-07) verifies every protected route has a `Depends(require_permission(...))`.
- **Phase 7 (Telegram OTP)** — uses `generate_otp_code`, `generate_deep_link_token`, `issue_session_cookies`; cross-module callback from telegram bot worker → auth service goes through a Protocol DI similar to D-24.
- **Phase 8 (Clients)** — uses `SoftDeleteMixin` partial-index pattern for the partial unique on `phone WHERE deleted_at IS NULL`; `UUIDPkMixin` for `Client.id`; `TimestampMixin` for created_at/updated_at; `PaginatedData[ClientResponse]` for list endpoint; `ResponseEnvelope[T]` on every response.
- **Phase 9 (OpenAPI + api-client)** — `ProblemDetails` shows up in OpenAPI as the response schema for 4xx; `ResponseEnvelope[T]` and `PaginatedData[T]` give clean TS types via `openapi-typescript`; fetcher unwraps `.data` before resolving.
- **Phase 10 (admin-web wiring)** — frontend `_README.md` and mocks updated to consume `ResponseEnvelope[T]`; bare-object contract retired. PROJECT.md/CLAUDE.md "frontend integrity" clause clarified to allow service/contract layer changes (UI internals still frozen).

</code_context>

<specifics>
## Specific Ideas

- **Backend-first contract is a deliberate architectural shift, not a one-off**: the user explicitly chose `ResponseEnvelope[T]` over preserving the v1.0 frontend contract because backend stability + extensibility (future `requestId`, `traceId`, `meta`, `warnings` without breaking shape) outweighs the cost of a one-time frontend mock rewrite in Phase 10. Downstream agents MUST treat this as the locked direction — do NOT propose reverting the envelope to "match the frontend" or duplicating bare-object endpoints "for compatibility".
- **`ProblemDetails` is intentionally NOT RFC 7807 verbatim**: the user prioritized matching the existing `AppError` handler output (`{code, message, fields?}`) over RFC 7807's `{type, title, status, detail, instance}` because the frontend `DomainError { code, message, fields? }` shape is already wired through Zod contracts and TanStack Query mutation handlers. Future RFC 7807 alignment is a v2+ concern.
- **Generic envelope naming separation matters**: `ResponseEnvelope[T]` is the **transport wrapper**; `ResponseData` is the **DTO base for payload classes**. This separation prevents the `ApiResponse[T]` ambiguity that conflated wrapper and base in early drafts. Don't merge them.
- **Pydantic 2.11 floor bump is non-trivial**: the `validate_by_name` / `validate_by_alias` migration deprecates `populate_by_name`. Verify `uv lock` regeneration cleanly resolves the new constraint without forcing other deps to bump unexpectedly.
- **JWT role embedding is a 15-min staleness contract**: the user accepted "role embedded in access token, refreshed every 15 min". Operators changing a user's role expect up to 15 min for the new permissions to take effect — OR explicit session revocation (Phase 5 admin endpoint, deferred). Do not propose stateless invalidation tricks (e.g., revocation lists in Redis) — that's v2 if ever.
- **Cookie helper as one function, not three**: `issue_session_cookies(response, *, access_token, refresh_token, csrf_token, secure)` keeps SameSite/Path/Max-Age centralized. Splitting into `set_access_cookie` / `set_refresh_cookie` / `set_csrf_cookie` is anti-pattern — drift across callers (Phase 5 login vs refresh vs Phase 7 OTP-verify) is the real risk being mitigated.
- **`SoftDeleteMixin` partial-index helper must be composable with table-specific `__table_args__`**: Phase 8 will add `Index("uq_clients_phone_alive", "phone", unique=True, postgresql_where=text("deleted_at IS NULL"))` on top of `SoftDeleteMixin`'s own deleted_at partial index. Document the mixin's contract: it exposes a `__soft_delete_args__` tuple that callers concat into their `__table_args__`.

</specifics>

<deferred>
## Deferred Ideas

- **Envelope expansion fields** (`requestId`, `traceId`, `meta`, `warnings`) — deferred to whichever phase first needs them. Phase 4 ships `{ data: T }` minimum; subsequent fields are additive.
- **JWT secret split into `jwt_access_secret` + `jwt_refresh_secret`** — D-01 deferred until prod deploy or compliance audit demands it. Refactor is non-breaking (additive Settings fields, dual-key cutover).
- **`jti` / `iss` / `aud` claims on access tokens** — D-02 deferred. `jti` only relevant if blacklist-on-revoke is added (currently rely on session revocation in Redis, family rotation for refresh).
- **Stateless JWT-only mode (no DB session record)** — explicitly REJECTED per research/PITFALLS.md and PROJECT.md OoS table. Cannot revoke; family rotation needs DB anyway. Do not revisit.
- **`require_permission` route wiring on real endpoints** — Phase 6 (RBAC-02..05). Phase 4 ships the dependency factory but does not attach it to any route.
- **CSRF dependency `verify_csrf`** — Phase 6 (CSRF-02). Phase 4 emits the cookie + helper; the dependency that validates on POST/PATCH/DELETE is Phase 6's job.
- **First business migration `0001_auth.py`** — Phase 5 (INFRA-03). Phase 4 verifies autogenerate-on-clean is empty.
- **`audit_log` table** — Phase 8 (INFRA-04, AUDIT-01..03).
- **Telegram bot worker process + `python-telegram-bot` integration** — Phase 7 (INFRA-06, AUTH-TG-*). Phase 4 only adds the dep to `pyproject.toml`.
- **`pg_trgm` extension enable** — Phase 8 (INFRA-04 with `0002_clients.py`). Phase 4 does NOT add `CREATE EXTENSION` calls.
- **OpenAPI export script + drift CI** — Phase 9 (API-01, API-02, API-05, API-06, API-07).
- **Frontend `_README.md` + mock-service rewrite to consume `ResponseEnvelope[T]`** — Phase 10 (FE-01..FE-07). PROJECT.md / CLAUDE.md "frontend integrity" amendment lands as Phase 10 housekeeping (one-line clarification: contracts/mocks/services may be revised; UI internals still frozen).
- **Active-sessions UI / password reset / HIBP / webhook bot mode** — v1.2 deferral (already in REQUIREMENTS.md `## v1.2 Requirements`).

</deferred>

---

*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Context gathered: 2026-05-01*
