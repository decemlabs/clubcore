---
phase: 05-user-schema-email-password-auth
plan: 02
subsystem: infra
tags: [redis, structlog, cookies, fastapi, lifespan, audit, security]

# Dependency graph
requires:
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: issue_session_cookies, get_settings, JWT/argon2 primitives, structlog setup
provides:
  - app.core.redis.redis_lifespan + get_redis (process-singleton client on app.state.redis)
  - app.core.audit.emit (structlog passthrough with locked Phase-8 event= contract)
  - app.core.security.clear_session_cookies (mirror of issue_session_cookies for browser-correct deletion)
affects:
  - 05-03 (login service uses get_redis + audit.emit)
  - 05-04 (refresh rotation uses get_redis + audit.emit family_reuse_detected)
  - 05-05 (logout uses clear_session_cookies)
  - 05-06 (lifespan composition in app.main)
  - 08 (audit DB writer swap-in without changing call sites)

# Tech tracking
tech-stack:
  added:
    - redis.asyncio (already in deps; first core-level usage)
  patterns:
    - "Lifespan symmetry: redis_lifespan mirrors db_lifespan shape (asynccontextmanager + app.state binding)"
    - "Per-request dependency reads singleton from app.state — no per-request connection"
    - "Cookie issuer/clearer pair: clear_*_cookies must mirror Path/SameSite/HttpOnly of issuer"
    - "Audit emission contract: locked event= names so Phase 8 can swap body without touching call sites"

key-files:
  created:
    - apps/backend/app/core/redis.py
    - apps/backend/app/core/audit.py
  modified:
    - apps/backend/app/core/security.py

key-decisions:
  - "decode_responses=True at lifespan level — Phase 5 services are str-only, no per-call decode burden"
  - "Default redis-py pool sizing accepted (10 conns) for 1-2 operator workload (T-05.02-04)"
  - "type: ignore[no-untyped-call] on redis.asyncio.from_url — library has no type stubs; isolated to one line"
  - "audit.emit accepts **fields: Any — Phase 8 schema is jsonb payload; narrowing now would constrain swap-in"

patterns-established:
  - "core helper file = lifespan + per-request dependency in one module (mirrors database.py)"
  - "Cookie deletion uses delete_cookie with full attribute mirror, not set_cookie max_age=0"
  - "Audit events are documented in module docstring as a locked contract list"

requirements-completed: ["AUTH-07", "AUTH-LO-01", "AUTH-LO-02"]

# Metrics
duration: ~10min
completed: 2026-05-02
---

# Phase 05 Plan 02: Core Helpers (Redis lifespan, Audit emit, Cookie clearer) Summary

**Three core-pure helpers landed: process-singleton Redis client on app.state, structlog audit emitter with locked Phase-8 event names, and clear_session_cookies that mirrors issue_session_cookies attributes for browser-correct deletion.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-02T09:49:56Z
- **Tasks:** 3
- **Files modified:** 3 (2 created, 1 extended)

## Accomplishments
- `redis_lifespan` + `get_redis` mirror the `db_lifespan` / `get_db` shape exactly — Phase 5 sessions, rate-limit, refresh-rotation race window all read one shared client
- `audit.emit(event, **fields)` provides a locked contract surface so Phase 8 (INFRA-04) can add DB row writes without touching any call site; locked event names documented in module docstring
- `clear_session_cookies(response, *, secure)` mirrors `issue_session_cookies` Path/SameSite/HttpOnly attributes verbatim — the drift risk that produces silent no-op deletes is mitigated at the helper level, not at every call site
- `core ⊥ modules` boundary preserved; `lint-imports`, `mypy strict`, and `ruff` all green across the 3 files

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/core/redis.py with redis_lifespan + get_redis** — `28aac1e` (feat)
2. **Task 2: Create app/core/audit.py with emit() structlog passthrough** — `a1da8e2` (feat)
3. **Task 3: Add clear_session_cookies sibling helper to security.py** — `0567156` (feat)

## Files Created/Modified
- `apps/backend/app/core/redis.py` — `redis_lifespan` (asynccontextmanager) + `get_redis(request)` per-request dependency; `decode_responses=True`, `from_url(str(settings.redis_url))`
- `apps/backend/app/core/audit.py` — `emit(event: str, **fields: Any) -> None` structlog passthrough at logger name `"audit"`; locked Phase-8 event-name contract documented in module docstring
- `apps/backend/app/core/security.py` — appended `clear_session_cookies(response, *, secure)` directly below `issue_session_cookies`; mirrors all three cookie attribute tuples (sz_access Path=`/`, sz_refresh Path=`/api/v1/auth`, sportzal_csrf Path=`/` HttpOnly=False)

## Decisions Made
- `type: ignore[no-untyped-call]` localized to the single `from_url(...)` call rather than disabling the rule globally — keeps mypy strict honest everywhere else (see Deviations).
- Did not introduce a `get_redis` async-context wrapper — the singleton is shared across requests by design (same as DB sessionmaker pattern), and `redis.asyncio.Redis` is connection-pool-backed so callers do not need per-request lifecycle management.
- Did not narrow `**fields` typing on `emit()` — Phase 8 will receive a jsonb payload, narrowing now would couple Phase 5 service code to a future schema.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy strict rejected redis.asyncio.from_url as untyped**
- **Found during:** Task 1 verification (`uv run mypy app/core/redis.py`)
- **Issue:** `redis.asyncio.utils.from_url` has no type stubs in `redis==5.3.1`; mypy strict raised `Call to untyped function "from_url" in typed context [no-untyped-call]`. Verification could not complete without resolving.
- **Fix:** Added a targeted `# type: ignore[no-untyped-call]` directly on the `from_url(...)` call site. Scope is limited to the single line; the rest of the module remains under strict typing. The annotated `client: Redis = ...` keeps the return type known to downstream callers.
- **Files modified:** `apps/backend/app/core/redis.py`
- **Verification:** `uv run mypy app/core/redis.py` exits 0; `uv run ruff check app/core/redis.py` exits 0; `lint-imports` exits 0.
- **Committed in:** `28aac1e` (Task 1 commit)

**2. [Rule 1 - Bug] Ruff E501 line-too-long on clear_session_cookies docstring**
- **Found during:** Task 3 verification (`uv run ruff check app/core/security.py`)
- **Issue:** The docstring summary line as written in the plan was 107 characters (project line length is 100). Ruff failed verification.
- **Fix:** Shortened the summary line to "Clear sz_access + sz_refresh + sportzal_csrf, mirroring issue_session_cookies (D-17)." while preserving the D-17 reference. The longer rationale paragraphs that follow are unchanged.
- **Files modified:** `apps/backend/app/core/security.py`
- **Verification:** `uv run ruff check app/core/security.py` exits 0; `uv run mypy app/core/security.py` exits 0.
- **Committed in:** `0567156` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking type-stub gap, 1 bug — line length).
**Impact on plan:** Both fixes were strictly mechanical (type-stub gap, line length). No semantic changes; all acceptance criteria still met (function signature, attributes, count assertions).

## Issues Encountered
None beyond the two auto-fixes above. Plan-level verification block (`mypy app/core/redis.py app/core/audit.py app/core/security.py`, `ruff check ...`, importable smoke test `from app.core.redis import ...; from app.core.audit import emit; from app.core.security import clear_session_cookies; print('ok')`) all pass.

## Threat Model Compliance

All `mitigate` dispositions in the threat register are honored by the implementation:

| Threat ID | Disposition | How mitigated |
|-----------|-------------|---------------|
| T-05.02-01 (Path mismatch on cookie clear) | mitigate | `clear_session_cookies` calls `delete_cookie` with `path="/api/v1/auth"` for `sz_refresh` and `path="/"` for `sz_access`/`sportzal_csrf`, mirroring issuer verbatim. Acceptance criteria assert `path="/api/v1/auth"` appears 2× in `security.py` (issuer + clearer) and `httponly=False` appears 2× — both verified. |
| T-05.02-02 (Tampering via Redis decode) | mitigate | `decode_responses=True` + `encoding="utf-8"` forces text I/O; no pickle path exists. |
| T-05.02-03 (Audit field leakage) | mitigate | Module docstring lists locked event names with non-sensitive payload shapes (`presented_token_hash_prefix`, never raw token). Phase 5 service callers will be guided by this docstring. |
| T-05.02-06 (core ⊥ modules) | mitigate | `lint-imports` runs in verification — `app.core.redis` and `app.core.audit` contain no `from app.modules` imports; contracts kept. |

T-05.02-04 (Redis pool exhaustion) and T-05.02-05 (Repudiation) carry `accept` dispositions per plan; no mitigation work performed.

## Next Phase Readiness
- All three helpers are import-stable and ready for consumption by 05-03 (login service: `get_redis`, `audit.emit('login_success' | 'login_failed', ...)`), 05-04 (refresh rotation: `audit.emit('family_reuse_detected', ...)`), 05-05 (logout: `clear_session_cookies`), and 05-06 (lifespan composition in `app.main`).
- No blockers. `lint-imports`/`mypy strict`/`ruff` all green; `core ⊥ modules` invariant intact.

## Self-Check: PASSED

- `apps/backend/app/core/redis.py` — FOUND
- `apps/backend/app/core/audit.py` — FOUND
- `apps/backend/app/core/security.py` (modified) — FOUND
- Commit `28aac1e` — FOUND (Task 1)
- Commit `a1da8e2` — FOUND (Task 2)
- Commit `0567156` — FOUND (Task 3)

---
*Phase: 05-user-schema-email-password-auth*
*Plan: 02*
*Completed: 2026-05-02*
