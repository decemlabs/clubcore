---
phase: 02-backend-skeleton-with-quality-tooling
plan: 07
subsystem: database
tags: [backend, alembic, async, migrations, sqlalchemy, asyncpg, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling/01
    provides: alembic.ini (script_location, prepend_sys_path, placeholder sqlalchemy.url, [loggers]), pyproject.toml mypy override for alembic.env, ruff per-file-ignore for alembic/env.py
  - phase: 02-backend-skeleton-with-quality-tooling/03
    provides: app.core.config.get_settings (Settings.database_url: PostgresDsn), app.core.database.Base (DeclarativeBase)

provides:
  - Async Alembic env.py reading DATABASE_URL via app.core.config.Settings (overrides alembic.ini placeholder)
  - Standard Alembic 1.13+ script.py.mako template (Mako placeholders intact)
  - Empty alembic/versions/ directory tracked by zero-byte .gitkeep
  - Wired migration entry point ready for `alembic revision` / `alembic upgrade head`

affects: [02-08, Phase B (business migrations), Phase 3 (docker-compose Postgres)]

tech-stack:
  added: []
  patterns:
    - "async_engine_from_config + connection.run_sync(do_run_migrations) cookbook pattern (asyncpg-compatible)"
    - "env.py is single source of truth for sqlalchemy.url at runtime (alembic.ini value is a placeholder)"
    - "env.py imports only Base + get_settings — never the FastAPI factory module (Pitfall 2)"

key-files:
  created:
    - apps/backend/alembic/env.py
    - apps/backend/alembic/script.py.mako
    - apps/backend/alembic/versions/.gitkeep
  modified: []

key-decisions:
  - "env.py reuses Plan 03 Base (Base.metadata == target_metadata) — no separate Alembic-only metadata"
  - "run_migrations_offline raises NotImplementedError — async-online is the only supported mode (T-02-18 accepted)"
  - "Docstring rephrased to avoid literal 'from app.main' / 'create_app' tokens — preserves Pitfall 2 warning while satisfying acceptance grep that asserts those tokens are absent"

patterns-established:
  - "Pattern: env.py reads sqlalchemy.url from Settings via configuration['sqlalchemy.url'] = str(settings.database_url) before calling async_engine_from_config"
  - "Pattern: do_run_migrations(connection: Connection) is sync; bridged via await connection.run_sync(do_run_migrations) inside async with engine.connect()"
  - "Pattern: NullPool poolclass for migration engine (no connection reuse needed; Alembic does single-shot work)"

requirements-completed: [DB-01, DB-02]

duration: 1m 59s
completed: 2026-04-30
---

# Phase 02 Plan 07: Alembic Async Setup Summary

**Async Alembic env.py reading Settings.database_url via async_engine_from_config + run_sync cookbook, plus standard script.py.mako and empty versions/.gitkeep — wired for asyncpg-driven migrations.**

## Performance

- **Duration:** 1m 59s
- **Started:** 2026-04-30T20:00:31Z
- **Completed:** 2026-04-30T20:02:30Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- `alembic/env.py` configured for async migrations: imports `Base` from `app.core.database` and `get_settings` from `app.core.config`, overrides `sqlalchemy.url` at runtime with `Settings.database_url`, and bridges async/sync via `connection.run_sync(do_run_migrations)`.
- Standard Alembic 1.13+ `script.py.mako` template in place — `alembic revision -m "msg"` will work in Phase B without further configuration.
- `alembic/versions/` directory created and tracked via zero-byte `.gitkeep` (matches `infra/docker/.gitkeep` convention from Phase 1).
- `uv run ruff check .` and `uv run mypy app` both clean — no regressions on the rest of the backend.
- env.py loads cleanly when imported as a module spec under stub env vars (`importlib.util.spec_from_file_location` + `module_from_spec` succeeds without ImportError).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create alembic/env.py with async migration setup** — `b770787` (feat)
2. **Task 2: Create alembic/script.py.mako + alembic/versions/.gitkeep** — `3e1ff9f` (feat)

**Plan metadata commit:** (this SUMMARY + STATE/ROADMAP updates) — see final commit.

## Files Created/Modified

- `apps/backend/alembic/env.py` — Async migration runner. Imports `Base` and `get_settings`; uses `async_engine_from_config` + `connection.run_sync` cookbook; `run_migrations_offline` raises `NotImplementedError`; `target_metadata = Base.metadata` for autogenerate.
- `apps/backend/alembic/script.py.mako` — Standard Alembic 1.13+ migration template with the canonical Mako placeholders (`${message}`, `${up_revision}`, `${imports}`, `${upgrades}`, etc.).
- `apps/backend/alembic/versions/.gitkeep` — Zero-byte directory tracker. `versions/` contains nothing else (verified: `ls alembic/versions/ | grep -v '^\.gitkeep$'` returns empty).

## Decisions Made

- **No `noqa` on the trailing `run_migrations_online()` module-level call** — ruff S/I001 already disabled for `alembic/env.py` via `[lint.per-file-ignores]` from Plan 01; `asyncio.run()` at module level is the standard Alembic invocation pattern.
- **Docstring rephrased** to avoid literal substrings `from app.main` and `create_app`. The plan's acceptance grep treats these as forbidden anywhere in the file (not just imports). The Pitfall 2 warning is preserved using equivalent wording ("Do NOT import the FastAPI application factory module").
- **`run_migrations_offline` kept** (raises `NotImplementedError`) rather than removed — preserves the conventional Alembic env.py shape so future readers see the explicit policy decision instead of an absent function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan-spec docstring contained tokens that fail the plan's own acceptance grep**

- **Found during:** Task 1 verification (running the plan's `<automated>` chain)
- **Issue:** The plan's verbatim env.py docstring contains the substring `app.main.create_app`. The plan's acceptance criteria states `! grep -q 'from app.main' alembic/env.py` and `! grep -q 'create_app' alembic/env.py` must both succeed (i.e., neither token may appear *anywhere* in the file). The literal docstring trips both checks.
- **Fix:** Rephrased the docstring's Pitfall 2 warning to "Do NOT import the FastAPI application factory module — that would trigger FastAPI lifespan + structlog configuration during `alembic revision` / `alembic upgrade` (RESEARCH.md Pitfall 2)." The semantic warning is preserved; the forbidden tokens are removed.
- **Files modified:** `apps/backend/alembic/env.py`
- **Verification:** Full plan-spec verification chain passes (`grep -q` for required tokens; `! grep -q` for forbidden tokens; `python -c "import ast; ast.parse(...)"`); ruff + mypy clean; module loads under `importlib.util`.
- **Committed in:** `b770787` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — plan-spec self-inconsistency between literal code and grep acceptance criteria)
**Impact on plan:** Cosmetic. Pitfall 2 warning preserved with equivalent wording. No scope creep.

## Issues Encountered

- **Initial `&&`-chained verification command exit-code 1** — Diagnosed by running each step separately; root cause was the docstring tokens described above. Resolved on first iteration; no rebuild loop.

## Deferred Items

- **Live `alembic upgrade head` smoke test** — deferred to Plan 08 (conditional on a reachable Postgres) or to Phase 3 once `infra/docker/docker-compose.yml` brings up a Postgres container. Wiring is verified; live DB connectivity is not.

## User Setup Required

None — no external service configuration required. The migration runner only activates when `alembic` is invoked explicitly (Plan 08+).

## Next Phase Readiness

- Plan 08 can now run `uv run alembic upgrade head` against an empty Postgres and expect exit 0 (Pitfall 6 — empty `versions/` is valid).
- Phase B (business modules) can run `uv run alembic revision --autogenerate -m "..."` — `target_metadata = Base.metadata` will pick up any subclass of `Base` registered at import time.
- No regressions: `uv run ruff check .` and `uv run mypy app` both pass on 44 source files.

## Self-Check: PASSED

- [x] `apps/backend/alembic/env.py` exists
- [x] `apps/backend/alembic/script.py.mako` exists
- [x] `apps/backend/alembic/versions/.gitkeep` exists (0 bytes)
- [x] Commit `b770787` exists in git log
- [x] Commit `3e1ff9f` exists in git log
- [x] env.py contains `from app.core.config import get_settings`, `from app.core.database import Base`, `async_engine_from_config`, `await connection.run_sync(do_run_migrations)`, `target_metadata = Base.metadata`
- [x] env.py contains neither `from app.main` nor `create_app`
- [x] `python -c "import ast; ast.parse(open('alembic/env.py').read())"` exits 0
- [x] `uv run ruff check .` clean
- [x] `uv run mypy app` clean (44 files)
- [x] `versions/` directory contains only `.gitkeep`

---
*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
