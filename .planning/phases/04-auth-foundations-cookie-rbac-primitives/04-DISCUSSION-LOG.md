# Phase 4: Auth Foundations & Cookie/RBAC Primitives - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 04-auth-foundations-cookie-rbac-primitives
**Areas discussed:** JWT design, Schema base + ORM mixins

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| JWT design | Claims shape, secret strategy, TTL location, refresh shape | ✓ |
| Argon2id tuning | Defaults vs explicit pinned + rehash-on-verify | (Claude's discretion — see CONTEXT.md D-27/D-28) |
| Cookie/CSRF helper API | Function signature + module location | (Claude's discretion — see CONTEXT.md D-25/D-26) |
| Schema base + ORM mixins | camelCase Pydantic base, UUIDPk/Timestamp/SoftDelete shape | ✓ |

**User selected:** JWT design + Schema base + ORM mixins.

---

## JWT design

### Question 1 — Secret strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Один SECRET_KEY | Reuse `settings.secret_key` for both access and refresh | ✓ |
| Split jwt_access_secret + jwt_refresh_secret | Two secrets in `Settings`; rotate access without logging everyone out | |

**User's choice:** Single `SECRET_KEY` (recommended).
**Notes:** Pet-project on 1 zal; rotation is a one-shot. Refactor to split is non-breaking later (additive Settings fields with dual-key cutover).

### Question 2 — Access token claims

| Option | Description | Selected |
|--------|-------------|----------|
| Минимальные `{sub, exp, iat, typ}` | Lookup role from DB on every request | |
| Стандартные `{sub, role, typ, iat, exp}` | Embed role; no DB lookup per request; 15-min TTL caps staleness | ✓ |
| Расширенные `+ jti, iss, aud` | jti for blacklist; iss/aud for multi-app | |

**User's choice:** Standard `{sub, role, typ, iat, exp}` (recommended).
**Notes:** Operator role-change reflects within ≤15 min (access TTL) OR via session revoke (Phase 5 admin endpoint, deferred).

### Question 3 — Refresh token shape

| Option | Description | Selected |
|--------|-------------|----------|
| Opaque `secrets.token_urlsafe(32)` | Hash sha256, store row in `refresh_tokens`; simpler revocation | ✓ |
| JWT + hash storage | Symmetry with access; but DB row authoritative anyway | |

**User's choice:** Opaque (recommended).
**Notes:** Phase 5 stores `sha256(token)` in `refresh_tokens.token_hash` with `family_id` / `user_id` / `expires_at` / `revoked_at` columns. Family-rotation is naturally DB-led.

### Question 4 — TTL constants location

| Option | Description | Selected |
|--------|-------------|----------|
| Settings (env-driven) | `access_token_ttl_seconds=900`, `refresh_token_ttl_seconds=2592000`, `jwt_clock_leeway_seconds=30` | ✓ |
| Module-level constants | In `core/security.py` as `timedelta` | |

**User's choice:** Settings (recommended).
**Notes:** `.env.example` documents defaults; staging/prod can tune without code edits.

### Continuation prompt

| Option | Description | Selected |
|--------|-------------|----------|
| Ещё вопросы | sub format, encode/decode location, error mapping | |
| Переходим к Schema base + ORM mixins | Remaining details delegated to Claude's discretion | ✓ |

**User's choice:** Move on. Remaining JWT details (sub = str(uuid), encode/decode in `app/core/security.py`, `jwt.InvalidTokenError` → `InvalidAccessToken(AppError)` 401) recorded under Claude's Discretion in CONTEXT.md D-06.

---

## Schema base + ORM mixins

### Question 1 — Pydantic camelCase base shape

| Option | Description | Selected |
|--------|-------------|----------|
| Один ApiSchema | One BaseModel subclass; all schemas inherit | (rejected initially) |
| Split ApiRequest + ApiResponse | Two bases: forbid extras on input, ignore on output | (initially selected, then revised) |
| ApiSchema + ApiResponse[T] envelope | Generic transport wrapper | ✓ (final, revised twice) |

**User's choice:** Final structure — ContractModel / RequestContract / ResponseData / PaginatedData[T] / ResponseEnvelope[T] / ProblemDetails (full hierarchy with envelope).
**Notes:** User initially picked split bases, then probed envelope pattern with example code, then surfaced backend-first contract reasoning. Final lock: `ResponseEnvelope[T]` wraps every success response; frontend adapts in Phase 10. Naming explicitly avoids "ApiResponse" to prevent transport-wrapper / DTO-base conflation.

### Question 2 — Base location

| Option | Description | Selected |
|--------|-------------|----------|
| `app/core/schemas.py` (new) + extend `pagination.py` | ContractModel hierarchy in schemas.py; PaginatedData[T] in pagination.py | ✓ |
| All in `app/core/schemas.py` | One file for everything | |
| Extend `pagination.py` | Add ContractModel to existing file | |

**User's choice:** Split — schemas.py for hierarchy, pagination.py for paginated payload (recommended).

### Question 3 — UUIDPkMixin source

| Option | Description | Selected |
|--------|-------------|----------|
| `server_default=text('gen_random_uuid()')` | PG-native (PG13+, no pgcrypto); INSERT returns ID via RETURNING | ✓ |
| Python-side `default=uuid4` | Cross-DB (SQLite-friendly), but autogenerate-on-clean less deterministic | |

**User's choice:** PG-native (recommended).

### Question 4 — SoftDeleteMixin index

| Option | Description | Selected |
|--------|-------------|----------|
| Partial index `WHERE deleted_at IS NULL` | Alive-bias; smaller; matches CLIENTS-02 partial-unique semantics | ✓ |
| Plain index | INFRA-02 wording "deleted_at indexed"; supports admin "all deleted" queries | |
| Both | Maximally flexible but doubles write cost | |

**User's choice:** Partial index (recommended).

### Question 5 — ApiRequest vs ApiResponse ConfigDict differences (asked in second batch)

| Option | Description | Selected |
|--------|-------------|----------|
| Request: `extra='forbid'`; Response: `extra='ignore'` + `from_attributes=True` | Strict on input, lenient on output | ✓ |
| One ConfigDict, names as documentation | Identical behavior, naming-only signal | |

**User's choice:** Differentiated configs (recommended). Captured in CONTEXT.md D-09.

### Question 6 — TimestampMixin defaults

| Option | Description | Selected |
|--------|-------------|----------|
| `server_default=func.now()` + `onupdate=func.now()` | DB-managed; immune to multi-instance clock drift; TIMESTAMPTZ | ✓ |
| Python-side `default=datetime.now(UTC)` | ORM-controlled; bypassed by raw SQL | |

**User's choice:** Server-side (recommended).

### Question 7 — Pagination contract flip

| Option | Description | Selected |
|--------|-------------|----------|
| Clean break (delete `LimitOffsetParams`) | No v1.0 consumers exist | ✓ |
| Deprecate one phase | Keep with DeprecationWarning | |

**User's choice:** Clean break (recommended).

### Question 8 — Members → Clients rename

| Option | Description | Selected |
|--------|-------------|----------|
| `git mv` | Preserves history (even though file is mostly empty) | ✓ |
| `rm + mkdir` | Re-create; loses one line of blame | |

**User's choice:** `git mv` (recommended).

### Question 9 — Alembic naming convention

| Option | Description | Selected |
|--------|-------------|----------|
| Standard SA template | `ix_%(column_0_label)s` etc. (official cookbook) | ✓ |
| Custom prefix | `sportzal_*` or similar | |

**User's choice:** SA standard (recommended).

### Question 10 — OWNER_ONLY shape

| Option | Description | Selected |
|--------|-------------|----------|
| `frozenset[tuple[Action, Resource]]` | Set-membership lookup; immutable; order-independent parity | ✓ |
| `list[tuple[Action, Resource]]` | Mirror frontend's array shape | |

**User's choice:** frozenset (recommended).

### Question 11 — Continue or close (with freeform "Что на счет использования generics. typing.Generic[T]")

**User raised:** PEP 695 vs typing.Generic[T] policy.
**Reflected back:** Both work with Pydantic v2; PEP 695 is current `pagination.py` style; Python 3.12+ hard-pinned.
**Outcome:** PEP 695 confirmed (locked as D-11).

### Question 12 — Generics policy

| Option | Description | Selected |
|--------|-------------|----------|
| PEP 695 | `class Page[T](BaseModel)` — current pagination.py style | ✓ |
| typing.Generic[T] | Legacy compatible | |
| Mixed | PEP 695 in ORM/Pydantic, Generic[T] elsewhere | |

**User's choice:** PEP 695 (recommended).

### Question 13 — ApiSchema with envelope (freeform reraise)

**User raised:** "а это `class ApiSchema(BaseModel): ... class ApiResponse(ApiSchema, Generic[T]): data: T`?" with comment "мне кажется это лучше".
**Reflected back:** Verified frontend mock contract (`apps/admin-web/src/shared/api/contracts/_README.md` says bare `{ items, total, page, pageSize }`); flagged that envelope conflicts with the locked frontend integrity rule unless we accept Phase 10 mock/contract rewrite.

### Question 14 — "split + generics?" (freeform)

**User raised:** "а если все таким раздельно но с generics?"
**Reflected back:** Confirmed PEP 695 + split bases work; demoed `Page[T](ApiResponse)`.
**Outcome:** Initially locked as split + no envelope, then reopened in next turn.

### Question 15 — Pydantic base final

| Option | Description | Selected |
|--------|-------------|----------|
| Single ApiSchema, no envelope | Simplest; preserves bare-object contract | |
| Split ApiRequest + ApiResponse, no envelope | Strict in / lenient out; preserves bare-object contract | |
| ApiSchema + ApiResponse[T] envelope | Wraps every response; frontend rewrite needed | (variant rejected — name was wrong) |

**User's choice (freeform):** Backend-first contract with full hierarchy:
- `ContractModel` — общий base для API contract моделей
- `RequestContract` — входящие request body/query payloads
- `ResponseData` — payload внутри success response
- `PaginatedData[T]` — generic pagination payload
- `ResponseEnvelope[T]` — единая transport-обёртка `{ data: T }`
- `ProblemDetails` — error response body

**User's rationale:**
- Backend-first: backend defines stable typed API; frontend adapts.
- Single response protocol for all endpoints.
- Extensible: future `meta`, `requestId`, `warnings`, `traceId` without breaking.
- Naming `ResponseEnvelope[T]` (transport wrapper) ≠ `ResponseData` (DTO base) avoids the wrapper/base conflation that broke earlier names.

Captured as D-07 / D-08 / D-09 / D-10 in CONTEXT.md.

### Question 16 — Error envelope policy

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level errors | Success: `{data}` ; Error: `{code, message, fields}` ; HTTP status discriminates | ✓ |
| Wrapped errors `{error: {code, message, fields}}` | Full envelope protocol on both sides | |

**User's choice:** Top-level (recommended). Locked as D-08.

### Question 17 — Envelope fields in Phase 4

| Option | Description | Selected |
|--------|-------------|----------|
| Only `data` in Phase 4 | Add `requestId`/`meta`/etc. when needed (Optional with None default) | ✓ |
| Phase 4 includes `requestId` + `meta` | Hook RequestIdMiddleware into envelope now | |

**User's choice:** Only `data` (recommended). Locked as D-13.

### Question 18 — Class hierarchy naming

| Option | Description | Selected |
|--------|-------------|----------|
| ApiSchema / ApiRequest / ApiDto / Page[T] / ApiEnvelope[T] | Earlier proposal | |
| ApiSchema + ApiResponse without ApiDto | Minimal naming; risks wrapper/base conflation | |

**User's choice (freeform):** ContractModel / RequestContract / ResponseData / PaginatedData[T] / ResponseEnvelope[T] / ProblemDetails. Locked as D-09.

### Question 19 — Frontend update timing

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 10 | Backend-only Phase 4; frontend adapts when wiring lands | ✓ |
| Phase 4 update README only | Inline doc but mocks lag — drift risk | |

**User's choice:** Phase 10 (recommended). Locked as D-30.

---

## Claude's Discretion

The user did not select these gray areas during multi-select; Claude locked sensible defaults aligned with research/SUMMARY.md and existing patterns:

- **Argon2id parameter policy** — library defaults (`PasswordHasher()` no args), wrapped in `asyncio.to_thread`, with `check_needs_rehash()` policy on verify (D-27). `verify_password` raises `InvalidPassword(AppError)` to keep callers free of library-specific exception handling (D-28).
- **Cookie + CSRF emission helper** — single `issue_session_cookies(response, *, access_token, refresh_token, csrf_token, secure)` in `app/core/security.py`; `Settings.cookie_secure: bool = False` with prod assertion in `create_app()`; `generate_csrf_token() -> str` returns `secrets.token_hex(32)` (D-25/D-26).
- **`get_current_user` / `require_permission` dependencies in Phase 4** — scaffolded as Protocol + registered loader stubs; full wiring lands in Phase 5 when User model exists (D-24).
- **Phase 4 verification approach** — unit tests for security primitives + permissions + schemas; integration test for autogenerate-on-clean smoke; manual import + import-linter checks (D-29).

---

## Deferred Ideas

- Envelope expansion fields (`requestId`, `traceId`, `meta`, `warnings`) — additive when first needed.
- Split JWT secrets — non-breaking refactor when prod / compliance demands.
- `jti` / `iss` / `aud` claims — additive when blacklist or multi-app demands.
- `require_permission` route attachment — Phase 6.
- `verify_csrf` dependency — Phase 6.
- First business migration `0001_auth.py` — Phase 5.
- `audit_log` table — Phase 8.
- Telegram bot worker — Phase 7.
- `pg_trgm` extension — Phase 8.
- OpenAPI export + drift CI — Phase 9.
- Frontend `_README.md` + mock rewrite + PROJECT.md/CLAUDE.md "frontend integrity" amendment — Phase 10.
