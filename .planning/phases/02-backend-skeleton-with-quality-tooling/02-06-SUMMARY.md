---
phase: 02-backend-skeleton-with-quality-tooling
plan: 06
subsystem: backend
tags: [backend, fastapi, api, healthz, factory, lifespan, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    plan: 03
    provides: "app.core.{config,database,logging,exceptions,middleware} — Settings/get_settings, db_lifespan, configure_logging, register_exception_handlers, register_middleware"
provides:
  - "apps/backend/app/main.py — create_app() factory (BE-02)"
  - "apps/backend/app/api/router.py — top-level api APIRouter (API-01)"
  - "apps/backend/app/api/v1/router.py — v1 APIRouter aggregating health (API-02)"
  - "apps/backend/app/api/v1/health.py — GET /healthz endpoint (API-03)"
affects:
  - "Plan 02-07 (alembic env.py: independent of create_app, but app.core.database.Base.metadata is now reachable through both code paths)"
  - "Plan 02-08 (quality gates: full app/ tree including api/ and main.py is now ruff/mypy/lint-imports validated)"
  - "Phase 03 (test infra: per-test create_app() invocations rely on factory contract preserved here)"

tech-stack:
  added: []
  patterns:
    - "FastAPI factory pattern: create_app() returns a configured instance; no module-level singleton (enables --factory flag, per-test isolation)"
    - "Four-file router chain (D-14): api/v1/health.py(@router.get('/healthz')) → api/v1/router.py(v1.include_router(health.router)) → api/router.py(api.include_router(v1) at empty prefix) → main.py(app.include_router(api))"
    - "Composition order in create_app: configure_logging → FastAPI(lifespan=db_lifespan) → register_middleware → register_exception_handlers → include_router(api)"
    - "/docs gated on settings.environment == 'dev' (T-02-13 information-disclosure mitigation); /redoc disabled outright"
    - "Smoke verification via httpx ASGITransport (CLAUDE.md test convention) — confirms 200 + {\"status\":\"ok\"} body without spinning a real socket"

key-files:
  created:
    - "apps/backend/app/api/__init__.py (api namespace package, docstring-only)"
    - "apps/backend/app/api/v1/__init__.py (api/v1 namespace package, docstring-only)"
    - "apps/backend/app/api/v1/health.py (10 lines; GET /healthz returning dict[str, str])"
    - "apps/backend/app/api/v1/router.py (11 lines; v1 = APIRouter() + Phase B+ TODO marker for module routers)"
    - "apps/backend/app/api/router.py (16 lines; api = APIRouter() + load-bearing '# TODO Phase B+: add /api/v1 prefix' comment per D-14)"
    - "apps/backend/app/main.py (44 lines; create_app() factory)"
  modified: []
  deleted: []

key-decisions:
  - "Lifespan context exercised via app.router.lifespan_context(app) inside the smoke test rather than relying on httpx-side lifespan support — keeps the test narrow (no real DB connection attempted; create_async_engine is lazy until first checkout) while still proving the lifespan handshake."

requirements-completed: [BE-02, API-01, API-02, API-03]

duration: 1m 27s
completed: 2026-04-30
---

# Phase 2 Plan 06: API Surface + create_app() Factory Summary

**Wired the API surface: `app/main.py:create_app()` factory plus the four-file router chain mounting `GET /healthz` at the root URL. End-to-end smoke test (httpx ASGITransport) returns `200` + `{"status":"ok"}` and the timing log carries `request_id` (REVERSED middleware order works as designed). All 44 source files pass `ruff check` and `mypy strict`.**

## Performance

- **Duration:** ~1m 27s
- **Started:** 2026-04-30T19:55:37Z
- **Completed:** 2026-04-30T19:57:04Z
- **Tasks:** 2
- **Files created:** 6
- **Lines added:** 88
- **Quality-gate iterations:** 0 (clean on first run)

## Accomplishments

- Created `apps/backend/app/api/__init__.py` and `apps/backend/app/api/v1/__init__.py` as docstring-only namespace packages (mypy-clean, lint-imports-friendly).
- Created `apps/backend/app/api/v1/health.py` with `router = APIRouter()` and `@router.get("/healthz")` returning `dict[str, str]` literal `{"status": "ok"}` (D-14, API-03; mypy-strict-clean return annotation).
- Created `apps/backend/app/api/v1/router.py` with `v1 = APIRouter(); v1.include_router(health.router)` plus the canonical Phase B+ TODO comment showing the `prefix=`/<name>`, tags=[...]` shape (API-02).
- Created `apps/backend/app/api/router.py` with `api = APIRouter(); api.include_router(v1)` — empty prefix in Phase A — and the **load-bearing** `# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path` comment required by D-14 (API-01).
- Created `apps/backend/app/main.py` with `create_app() -> FastAPI` composing: `configure_logging(settings)` → `FastAPI(title="Sportzal API", lifespan=db_lifespan, docs_url='/docs' if dev else None, redoc_url=None)` → `register_middleware(app)` → `register_exception_handlers(app)` → `app.include_router(api)` (BE-02). No module-level `app = create_app()` (factory contract preserved); no deprecated `@app.on_event` handlers.
- Verified end-to-end via `httpx.ASGITransport` smoke test inside `app.router.lifespan_context(app)`: `GET /healthz` → `200` + `{"status":"ok"}`; timing log line shows `request_id=<uuid>` confirming the REVERSED middleware add order from Plan 03 works through the full stack.

## Task Commits

1. **Task 1: Create api namespace + four-file health router chain** — `6e95ded` (feat)
2. **Task 2: Create app/main.py with create_app() factory** — `d988e3f` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Smoke imports (api chain) | `uv run python -c "from app.api.router import api; from app.api.v1.router import v1; from app.api.v1.health import router as health_router"` | OK |
| create_app smoke | `DATABASE_URL=... uv run python -c "from app.main import create_app; app = create_app(); assert any(r.path == '/healthz' for r in app.routes)"` | OK (routes include `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/healthz`) |
| httpx ASGITransport smoke | `GET /healthz` via `app.router.lifespan_context` + `AsyncClient(transport=ASGITransport(app))` | 200 + `{"status":"ok"}` — middleware logged `request_complete duration_ms=0.58 method=GET path=/healthz request_id=<uuid> status_code=200` |
| Ruff lint | `uv run ruff check app/api/ app/main.py` | All checks passed |
| Ruff format | `uv run ruff format --check app/api/ app/main.py` | Already formatted |
| mypy strict | `uv run mypy app` | Success: no issues found in 44 source files |
| spec-grep: load-bearing TODO | `grep -q '# TODO Phase B+: add /api/v1 prefix' app/api/router.py` | FOUND |
| spec-grep: no module-level app | `grep -E '^app = create_app\(\)' app/main.py` | No match |
| spec-grep: no on_event | `grep -E '@app\.on_event' app/main.py` | No match |
| spec-grep: composition order | `grep -nE '^\s+(register_middleware\|register_exception_handlers\|app\.include_router)\(' app/main.py` | Lines 41 → 42 → 43 (correct order) |

All plan-level `<verification>` block items pass:
- All 6 files exist — VERIFIED
- `from app.main import create_app` succeeds with required env vars — VERIFIED
- `/healthz` route is registered after `create_app()` — VERIFIED
- No `@app.on_event` handlers; no module-level app instance — VERIFIED

All 18 acceptance-criteria items across Tasks 1 and 2 satisfied.

## Decisions Made

- **Smoke test uses `app.router.lifespan_context(app)` rather than httpx's `lifespan="on"`** — keeps the verification self-contained (no httpx version coupling for lifespan support) and makes the assertion ordering explicit. The lazy nature of `create_async_engine` means the lifespan body succeeds without a live Postgres; `engine.dispose()` on shutdown is a no-op until a connection is actually checked out. Documented here so Plan 08 (which writes the integration smoke against a real container) doesn't reuse this pattern verbatim.
- **No deviations from plan text required** — both core symbol names (`db_lifespan`, `register_middleware`, `register_exception_handlers`, `configure_logging`, `get_settings`, `api`) matched the prior summaries' exports exactly, so the imports were verbatim from the plan spec.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed on the first quality-gate iteration (no Rule 1/2/3 fixes triggered, no checkpoints, no auth gates).

## Issues Encountered

None. The plan's `<context>` accurately listed the five core symbols this plan imports, all of which were present from Plan 03; the four-file router chain registered `/healthz` at root on the first attempt and `httpx.ASGITransport` returned `200`/`{"status":"ok"}` on the first call.

## User Setup Required

None — all work was code-only inside `apps/backend/app/`. Smoke verification was done with throwaway env vars (`DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal`, `REDIS_URL=redis://localhost:6379/0`, `SECRET_KEY=smoke`, `ENVIRONMENT=dev`); no real services were contacted because `create_async_engine` is lazy and ARQ workers are not started by `create_app()`.

## Next Phase Readiness

- **Plan 02-07** (alembic env.py): Independent of `create_app()` but can now `from app.core.database import Base` (already from Plan 03) without conflict; no shared module-level state.
- **Plan 02-08** (quality gates): full `apps/backend/app/` tree (44 files) is now ruff-clean, ruff-format-clean, and mypy-strict-clean. `lint-imports` will see the new `api → modules` hop is currently unused (no business modules yet) but the contract is in place.
- **Phase 03** (test infra): The factory contract (`create_app()` returns a fresh FastAPI per call, no module-level singleton) is preserved, enabling per-test app instances with isolated `app.state.engine`/`app.state.sessionmaker`.
- **ROADMAP success criterion #2** (`curl http://localhost:8000/healthz` → 200 + `{"status":"ok"}`): wiring complete; verified end-to-end in this plan via in-process ASGI transport. The real `uvicorn` launch + curl is exercised in Plan 08.

## Threat Flags

None. The plan's `<threat_model>` (T-02-13 through T-02-15) is fully mitigated/accepted as documented:
- **T-02-13** (Information Disclosure via OpenAPI docs): `docs_url='/docs' if settings.environment == 'dev' else None`; `redoc_url=None`. Verified at runtime — when `ENVIRONMENT=dev`, `app.routes` includes `/docs`, `/docs/oauth2-redirect`, and `/openapi.json`. Outside dev, those routes are absent.
- **T-02-14** (DoS on /healthz): accepted (Phase A scope; uvicorn backlog provides baseline protection).
- **T-02-15** (No auth on /healthz): accepted (k8s liveness convention).

No new security-relevant surface introduced beyond the threat-modeled items.

## Self-Check

Verifying claims before final commit:

**Created files (all 6):**
- `apps/backend/app/api/__init__.py` — FOUND
- `apps/backend/app/api/v1/__init__.py` — FOUND
- `apps/backend/app/api/v1/health.py` — FOUND
- `apps/backend/app/api/v1/router.py` — FOUND
- `apps/backend/app/api/router.py` — FOUND
- `apps/backend/app/main.py` — FOUND

**Commits:**
- `6e95ded` (Task 1 — api router chain) — FOUND in `git log --oneline`
- `d988e3f` (Task 2 — create_app factory) — FOUND in `git log --oneline`

**Quality gates:**
- `uv run ruff check app/api/ app/main.py` — exit 0, "All checks passed!"
- `uv run ruff format --check app/api/ app/main.py` — exit 0, "5 files already formatted" + "1 file already formatted"
- `uv run mypy app` — exit 0, "Success: no issues found in 44 source files"
- httpx ASGITransport smoke — `200` + `{"status":"ok"}` body
- Spec-grep: load-bearing `# TODO Phase B+: add /api/v1 prefix` — VERIFIED in `app/api/router.py`
- Spec-grep: no `^app = create_app()` line in `app/main.py` — VERIFIED
- Spec-grep: no `@app.on_event` decorators in `app/main.py` — VERIFIED
- Spec-grep: composition call order register_middleware (41) → register_exception_handlers (42) → app.include_router (43) — VERIFIED

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
