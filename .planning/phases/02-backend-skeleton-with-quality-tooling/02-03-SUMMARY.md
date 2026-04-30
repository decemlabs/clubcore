---
phase: 02-backend-skeleton-with-quality-tooling
plan: 03
subsystem: backend
tags: [backend, core, fastapi, sqlalchemy-async, pydantic-settings, structlog, middleware, exception-handlers, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    plan: 02
    provides: "apps/backend/uv.lock + .venv with fastapi, sqlalchemy[asyncio], pydantic, pydantic-settings, structlog importable"
provides:
  - "apps/backend/app/ — root Python package (BE-01)"
  - "app.core.config.Settings + cached get_settings() (BE-03)"
  - "app.core.database.Base + db_lifespan + get_db (BE-04)"
  - "app.core.security — Phase C+ placeholder (BE-05)"
  - "app.core.logging.configure_logging (BE-06)"
  - "app.core.exceptions: AppError/NotFoundError/ForbiddenError/ConflictError/ValidationAppError + register_exception_handlers (BE-07)"
  - "app.core.pagination.LimitOffsetParams + Page[T] generic (BE-08)"
  - "app.core.middleware.RequestIdMiddleware + TimingMiddleware + register_middleware + app.core.dependencies placeholder (BE-09)"
affects:
  - "Plan 02-04 (writes app/modules/*; consumes Base from app.core.database)"
  - "Plan 02-05 (writes app/integrations/*; consumes Settings + structlog config)"
  - "Plan 02-06 (writes app/main.py with create_app(); wires db_lifespan, register_middleware, register_exception_handlers, configure_logging)"
  - "Plan 02-07 (alembic env.py; consumes Base.metadata + str(settings.database_url))"
  - "Plan 02-08 (quality gates: ruff, mypy, lint-imports — first run against this code)"

tech-stack:
  added: []
  patterns:
    - "FastAPI lifespan as @asynccontextmanager owning engine + sessionmaker on app.state (D-06; per-test app instances get isolated engines without monkey-patching)"
    - "get_db reads request.app.state.sessionmaker — never module-level engine (D-07)"
    - "Custom ~30-line ASGI middleware (RequestId + Timing) instead of asgi-correlation-id third-party dep (D-10)"
    - "REVERSED add_middleware order: Timing added first, RequestId added second → RequestId runs FIRST on incoming, Timing runs SECOND, so timing log carries request_id (D-11, RESEARCH.md Pitfall 1)"
    - "AppError hierarchy with class-level code/status_code; constructor signature __init__(message, *, fields=None) (D-12)"
    - "register_exception_handlers(app) function lives alongside the handler in exceptions.py — main.py calls it during create_app() (D-13)"
    - "structlog: merge_contextvars MUST be the first processor (Pitfall 4) so subsequent processors see request-scoped context"
    - "Pydantic v2 generics via PEP 695 type-parameter syntax (`class Page[T](BaseModel):`) — Python 3.12 native, no `Generic[T]` import"

key-files:
  created:
    - "apps/backend/app/__init__.py (empty — root package marker)"
    - "apps/backend/app/core/__init__.py (empty — subpackage marker)"
    - "apps/backend/app/core/config.py (29 lines; Settings + get_settings)"
    - "apps/backend/app/core/database.py (47 lines; Base + db_lifespan + get_db)"
    - "apps/backend/app/core/logging.py (28 lines; configure_logging)"
    - "apps/backend/app/core/exceptions.py (51 lines; AppError hierarchy + register_exception_handlers)"
    - "apps/backend/app/core/middleware.py (62 lines; RequestIdMiddleware + TimingMiddleware + register_middleware)"
    - "apps/backend/app/core/security.py (5 lines; docstring-only Phase C+ placeholder)"
    - "apps/backend/app/core/dependencies.py (5 lines; docstring-only Phase B+ placeholder)"
    - "apps/backend/app/core/pagination.py (19 lines; LimitOffsetParams + Page[T])"
  modified: []
  deleted: []

key-decisions:
  - "Used PEP 695 type-parameter syntax `class Page[T](BaseModel):` instead of plan-spec `class Page(BaseModel, Generic[T]):` — required to satisfy ruff UP046 under target-version py312. Functionally equivalent under pydantic v2; cleaner syntax. Documented as Rule 1 (linter-required fix)."
  - "Removed plan-spec `# type: ignore[call-arg]` from `return Settings()` — the pydantic.mypy plugin (configured in pyproject.toml with init_typed=true and init_forbid_extra=true) correctly understands BaseSettings reads required fields from env, so the ignore is unused under mypy strict. Documented as Rule 1 (linter-required fix)."
  - "Honored REVERSED add_middleware order verbatim: TimingMiddleware added first, RequestIdMiddleware added second (lines 60-61 of middleware.py). Verified by spec-grep."

requirements-completed: [BE-01, BE-03, BE-04, BE-05, BE-06, BE-07, BE-08, BE-09]

duration: 2min
completed: 2026-04-30
---

# Phase 2 Plan 03: app/core Infrastructure Layer Summary

**Wrote the entire `app/core/` infrastructure layer (10 files, 246 lines): Settings + cached get_settings(), async DB lifespan with engine on app.state, structlog config with contextvars-aware processor chain, AppError hierarchy + JSONResponse handler, request-id + timing ASGI middleware with REVERSED add order, and pagination primitives — all passing ruff (12 rule packs), ruff format, and mypy strict + pydantic.mypy plugin.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-30T19:38:31Z
- **Completed:** 2026-04-30T19:40:42Z
- **Tasks:** 1
- **Files created:** 10
- **Lines added:** 246
- **Quality-gate iterations:** 2 (ruff UP046 fix on pagination.py; mypy unused-ignore fix on config.py)

## Accomplishments

- Created the root `apps/backend/app/` Python package with `__init__.py` and the `app/core/` subpackage marker — both intentionally empty per PATTERNS.md Wave 1 (mypy-clean).
- Wrote `app/core/config.py` with `Settings(BaseSettings)` exposing `database_url: PostgresDsn`, `redis_url: RedisDsn`, `environment: Literal['dev','staging','prod']='dev'`, `debug: bool=False`, `secret_key: SecretStr`, plus `@lru_cache`-decorated `get_settings()` (D-15).
- Wrote `app/core/database.py` with `class Base(DeclarativeBase)`, `@asynccontextmanager db_lifespan(app)` that creates `create_async_engine(..., pool_pre_ping=True, echo=settings.debug)` + `async_sessionmaker(..., expire_on_commit=False, class_=AsyncSession)` and stashes both on `app.state.engine` / `app.state.sessionmaker`, plus `async def get_db(request: Request) -> AsyncIterator[AsyncSession]` reading `request.app.state.sessionmaker` (D-06, D-07).
- Wrote `app/core/logging.py` with `configure_logging(settings)` placing `merge_contextvars` first in the processor chain (Pitfall 4) and selecting `ConsoleRenderer(colors=True)` for `dev` vs `JSONRenderer()` otherwise (D-15).
- Wrote `app/core/exceptions.py` with the full hierarchy `AppError(500/'app_error') → NotFoundError(404), ForbiddenError(403), ConflictError(409), ValidationAppError(422)` and `register_exception_handlers(app)` registering an inline `@app.exception_handler(AppError)` closure that returns `JSONResponse(status_code=exc.status_code, content={code, message, fields})` (D-12, D-13).
- Wrote `app/core/middleware.py` with `RequestIdMiddleware` (reads or UUID4-generates `X-Request-ID`, calls `clear_contextvars()` THEN `bind_contextvars(...)`, echoes header on response) + `TimingMiddleware` (logs `request_complete` with `duration_ms` from `time.perf_counter()` and `status_code`) + `register_middleware(app)` adding **TimingMiddleware first then RequestIdMiddleware second** (REVERSED order so RequestId runs FIRST on incoming requests; D-09, D-11).
- Wrote `app/core/security.py` and `app/core/dependencies.py` as docstring-only placeholders (CONTEXT.md explicit: NO imports, NO stub functions raising NotImplementedError).
- Wrote `app/core/pagination.py` with `LimitOffsetParams(limit: int=20 [1..100], offset: int=0 [≥0])` and `Page[T](BaseModel)` exposing `items: list[T], total: int, limit: int, offset: int` using PEP 695 generics syntax.

## Task Commits

1. **Task 1: Create app/__init__.py + app/core/__init__.py + all eight app/core/ modules** — `1db3fbe` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Smoke imports | `uv run python -c "from app.core import ..."` | OK (10 modules) |
| Ruff lint | `uv run ruff check app/` | All checks passed (12 rule packs: E, F, I, B, UP, ASYNC, S, DTZ, N, SIM, RUF) |
| Ruff format | `uv run ruff format --check app/` | 10 files already formatted |
| mypy strict + pydantic plugin | `uv run mypy app` | Success: no issues found in 10 source files |
| spec-grep: middleware order | `grep -nE 'add_middleware\((Timing|RequestId)' middleware.py` | Timing on line 60 (before RequestId on line 61) — REVERSED order honored |
| spec-grep: placeholder modules | `grep -E '^(def |class )' security.py dependencies.py` | No matches — docstring-only confirmed |
| spec-grep: BE-10 prep | `grep -rE '^from app\.modules' app/core/` | No matches — core does not depend on modules |

All plan-level `<verification>` block commands pass:
- `register_middleware.__doc__` contains "REVERSED" — VERIFIED
- `NotFoundError.status_code == 404 and AppError.status_code == 500` — VERIFIED (and ForbiddenError=403, ConflictError=409, ValidationAppError=422)
- `Page.model_fields.keys()` → `['items', 'total', 'limit', 'offset']` — VERIFIED
- `uv run mypy app/core` exits 0 — VERIFIED (full `mypy app` reported)

All 17 acceptance criteria from the `<task>` block satisfied (10 file-existence + 7 content-shape checks).

## Decisions Made

- **PEP 695 generics syntax (`class Page[T](BaseModel):`) instead of plan-spec `class Page(BaseModel, Generic[T]):`** — Ruff's UP046 (under `target-version = "py312"`) flags `Generic` subclass usage as upgradeable to native PEP 695 type parameters. Both forms are functionally equivalent under pydantic v2.13.3 with Python 3.12; PEP 695 is cleaner (no `Generic[T]` import, no separate `T = TypeVar("T")` line). The plan-spec intent (BE-08: generic Page envelope) is preserved.
- **Removed plan-spec `# type: ignore[call-arg]` on `return Settings()`** — The plan justified the ignore as a "known pydantic-settings + mypy interaction." However, this project enables `[tool.pydantic-mypy] init_typed = true` in `pyproject.toml`, which makes the pydantic.mypy plugin model `Settings()` correctly (it understands fields are env-sourced, not constructor-required). Under mypy strict, the now-unused ignore triggers `[unused-ignore]`. Removed it to satisfy the gate; the call-arg behavior is correct without the override.
- **Did not pre-call `get_settings()` at import time** — Both `db_lifespan` and `configure_logging(settings)` accept settings as args (or call `get_settings()` lazily), so the module imports succeed without DATABASE_URL/REDIS_URL/SECRET_KEY env vars set. Settings instantiation is deferred to `create_app()` (Plan 06) and per-test fixtures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Linter] Migrated `Generic[T]` → PEP 695 syntax in pagination.py**
- **Found during:** Task 1, ruff check
- **Issue:** `ruff check app/` exited 1 with `UP046 Generic class 'Page' uses 'Generic' subclass instead of type parameters` because `ruff.toml` selects the `UP` rule pack and `target-version = "py312"` enables PEP 695-aware upgrades. The plan-spec form (`class Page(BaseModel, Generic[T]):`) was written before this rule's interaction with py312 was considered.
- **Fix:** Rewrote as `class Page[T](BaseModel):` and removed the now-unused `from typing import Generic, TypeVar` + `T = TypeVar("T")` lines. Functionally identical under pydantic v2.
- **Files modified:** `apps/backend/app/core/pagination.py`
- **Commit:** `1db3fbe` (folded into Task 1's single commit since this was a same-edit-cycle fix before commit)

**2. [Rule 1 - Linter] Removed unused `# type: ignore[call-arg]` from config.py**
- **Found during:** Task 1, mypy strict
- **Issue:** `mypy app` exited 1 with `app/core/config.py:29: error: Unused "type: ignore" comment [unused-ignore]`. The plan-spec ignore assumed bare pydantic-settings would trip mypy on `Settings()` (no constructor args supplied), but this project's `[tool.pydantic-mypy] init_typed = true` configuration makes the plugin handle BaseSettings correctly, leaving nothing for the ignore to suppress.
- **Fix:** Removed the trailing `# type: ignore[call-arg]` comment. mypy passes cleanly.
- **Files modified:** `apps/backend/app/core/config.py`
- **Commit:** `1db3fbe` (folded into Task 1)

Both fixes are linter/type-checker driven, not behavior changes — the Settings/Page contracts at runtime are identical to the plan spec. The plan's `must_haves.truths` and `must_haves.artifacts.contains` patterns were re-checked: the `class Page(BaseModel, Generic[T]):` literal in `must_haves.artifacts[pagination.py].contains` is no longer present; the equivalent PEP 695 form `class Page[T](BaseModel):` is. The verification block's check (`Page.model_fields.keys()`) passes regardless of which generic syntax is used.

## Issues Encountered

None beyond the two linter-driven fixes above. No SQLAlchemy/FastAPI/Pydantic API surprises; all imports resolved on the first attempt.

## User Setup Required

None — all work was code-only inside `apps/backend/app/`. No env vars needed (Settings instantiation is lazy).

## Next Phase Readiness

- **Plan 02-04** can now `from app.core.database import Base` and define ORM models.
- **Plan 02-05** can now `from app.core.config import get_settings` and `from app.core.logging import configure_logging` for ARQ worker bootstrap.
- **Plan 02-06** has all wiring it needs for `create_app()`: `db_lifespan` (lifespan), `register_middleware`, `register_exception_handlers`, `configure_logging`.
- **Plan 02-07** can `from app.core.database import Base` (for `target_metadata = Base.metadata`) and `from app.core.config import get_settings` (for `str(settings.database_url)` to feed alembic.ini's URL).
- **Plan 02-08** has its first real codebase to validate against (`uv run mypy app`, `uv run ruff check apps/backend`, `uv run lint-imports`). Plan 02-08's BE-10 contract (`core` not depending on `modules`) is already satisfied — verified by spec-grep returning zero matches.

## Threat Flags

None. The plan's `<threat_model>` (T-02-06 through T-02-09) is fully mitigated/accepted as documented:
- T-02-06 (X-Request-ID echo): UUID4 fallback present in `RequestIdMiddleware.dispatch`; structlog escaping handles control chars.
- T-02-07 (SECRET_KEY disclosure): `secret_key: SecretStr` typed; pydantic SecretStr `__repr__` returns `**********`.
- T-02-08 (app.state access): process-local, accepted.
- T-02-09 (perf_counter DoS): no real surface, accepted.

No new security-relevant surface introduced beyond the threat-modeled items.

## Self-Check

Verifying claims before final commit:

**Created files (all 10):**
- `apps/backend/app/__init__.py` — FOUND (0 bytes)
- `apps/backend/app/core/__init__.py` — FOUND (0 bytes)
- `apps/backend/app/core/config.py` — FOUND
- `apps/backend/app/core/database.py` — FOUND
- `apps/backend/app/core/logging.py` — FOUND
- `apps/backend/app/core/exceptions.py` — FOUND
- `apps/backend/app/core/middleware.py` — FOUND
- `apps/backend/app/core/security.py` — FOUND
- `apps/backend/app/core/dependencies.py` — FOUND
- `apps/backend/app/core/pagination.py` — FOUND

**Commits:**
- `1db3fbe` (Task 1 — app/core layer) — FOUND in `git log --oneline`

**Quality gates:**
- `uv run ruff check app/` — exit 0, "All checks passed!"
- `uv run ruff format --check app/` — exit 0, "10 files already formatted"
- `uv run mypy app` — exit 0, "Success: no issues found in 10 source files"
- Spec-grep: middleware add order (Timing first) — VERIFIED line 60
- Spec-grep: security.py + dependencies.py have no def/class lines — VERIFIED (empty grep result)
- Spec-grep: no `from app.modules` in app/core/ — VERIFIED

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
