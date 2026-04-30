---
phase: 02-backend-skeleton-with-quality-tooling
plan: 02
subsystem: infra
tags: [backend, uv, lockfile, dependency-resolution, python, dev-environment]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    plan: 01
    provides: "apps/backend/pyproject.toml with [project] runtime deps + [tool.uv] dev-dependencies; .gitignore covering .venv but NOT uv.lock"
provides:
  - "apps/backend/uv.lock — 52-package frozen dependency graph (Python 3.12) with content hashes"
  - "apps/backend/.venv/ — installed local virtualenv (gitignored)"
  - "Runnable dev toolchain: `uv run ruff|mypy|lint-imports|pytest|pytest-asyncio` from apps/backend/"
  - "Importable runtime stack: fastapi, sqlalchemy, asyncpg, alembic, pydantic, pydantic_settings, structlog, arq, redis, httpx, uvicorn"
affects:
  - "Plan 02-03..02-07 (write Python source under apps/backend/app/ — depend on installed venv to import locked deps)"
  - "Plan 02-08 (run quality gates: `uv run ruff check`, `uv run mypy app`, `uv run lint-imports`)"
  - "Phase 03 (tests, Dockerfile, docs — base image installs from uv.lock for reproducibility)"

tech-stack:
  added:
    - "uv.lock format v1 (uv 0.11.6 generator) — 52 packages with content hashes"
  patterns:
    - "Lockfile is project state — committed to git, never gitignored"
    - "uv lock + uv sync is a 2-step pattern: resolve (lock) then install (sync)"
    - "`uv run <tool>` is the canonical dev-tool invocation (no global PATH dep)"

key-files:
  created:
    - "apps/backend/uv.lock (88,782 bytes; SHA-256 e46a374894085ddf8fcc06f3c8d4965992c877fe99582bdd1be32c0edef57a63)"
  modified: []
  deleted: []

key-decisions:
  - "Did NOT migrate `[tool.uv] dev-dependencies` to PEP 735 `[dependency-groups]` despite uv 0.11.6 deprecation warning — Plan 01 honored CONTEXT.md D-15 lock; warning is informational and does not block any tool. Future migration is a 1-line PR."
  - "Accepted resolver picks above floor pins on every dep (e.g., fastapi 0.136.1 vs floor 0.115; mypy 1.20.2 vs floor 1.10) — no version-resolution surprises and no conflicts surfaced."
  - "uv selected the locally-installed cpython-3.12.12 over the available-but-not-yet-downloaded 3.12.13 (no preference declared in pyproject — only `>=3.12,<3.13`); both satisfy `requires-python` so this is acceptable. `uv sync` is fully reproducible from the lockfile regardless of which 3.12.x is present."

requirements-completed: [TOOL-01]

duration: 1min
completed: 2026-04-30
---

# Phase 2 Plan 02: uv Environment + Lockfile Summary

**`uv lock` resolved 52 packages against Python 3.12; `uv sync` installed apps/backend/.venv with fastapi 0.136.1, sqlalchemy 2.0.49, mypy 1.20.2, ruff 0.15.12, import-linter 2.11 and the rest of the locked stack — all five dev tools invocable via `uv run` and all 11 runtime deps importable.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-30T19:33:35Z
- **Completed:** 2026-04-30T19:34:35Z
- **Tasks:** 1
- **Files created:** 1 (uv.lock)
- **Packages resolved:** 52
- **Packages installed into .venv:** 52

## Accomplishments

- Generated `apps/backend/uv.lock` via `uv lock` against Python 3.12.12 from the Plan 01 manifest — 52 packages, 88,782 bytes, SHA-256 `e46a374894085ddf8fcc06f3c8d4965992c877fe99582bdd1be32c0edef57a63`.
- Installed `apps/backend/.venv/` via `uv sync` (gitignored per Plan 01).
- Confirmed all five dev tools invocable via `uv run`: ruff 0.15.12, mypy 1.20.2, import-linter 2.11, pytest 9.0.3, pytest-asyncio 1.3.0.
- Confirmed all 11 runtime deps importable in a single Python invocation: `fastapi, sqlalchemy, asyncpg, alembic, pydantic, pydantic_settings, structlog, arq, redis, httpx, uvicorn`.
- Committed `uv.lock` only — `.venv/` correctly excluded by Plan 01's `.gitignore`.

## Task Commits

1. **Task 1: Run uv lock + uv sync from apps/backend/** — `be21758` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Resolved Versions (key deps)

### Runtime (from `[project] dependencies`)

| Package           | Floor pin    | Resolved | Notes                                               |
|-------------------|--------------|----------|-----------------------------------------------------|
| fastapi           | >=0.115      | 0.136.1  | pulls starlette 1.0.0 (just released GA)            |
| sqlalchemy        | >=2.0        | 2.0.49   | async stack via asyncpg                             |
| asyncpg           | >=0.30       | 0.31.0   |                                                     |
| alembic           | >=1.13       | 1.18.4   |                                                     |
| pydantic          | >=2.0        | 2.13.3   | pydantic-core 2.46.3                                |
| pydantic-settings | >=2.0        | 2.14.0   |                                                     |
| structlog         | >=24.0       | 25.5.0   |                                                     |
| arq               | >=0.26       | 0.28.0   |                                                     |
| redis             | >=5.0        | 5.3.1    |                                                     |
| httpx             | >=0.27       | 0.28.1   |                                                     |
| uvicorn[standard] | >=0.30       | 0.46.0   | extras pulled uvloop, watchfiles, websockets, httptools |

### Dev (from `[tool.uv] dev-dependencies`)

| Package         | Floor pin | Resolved |
|-----------------|-----------|----------|
| ruff            | >=0.6     | 0.15.12  |
| mypy            | >=1.10    | 1.20.2   |
| import-linter   | >=2.0     | 2.11     |
| pytest          | >=8.0     | 9.0.3    |
| pytest-asyncio  | >=0.23    | 1.3.0    |

## Files Created/Modified

- `apps/backend/uv.lock` — 88,782 bytes; SHA-256 `e46a374894085ddf8fcc06f3c8d4965992c877fe99582bdd1be32c0edef57a63`. uv lockfile format v1; pins all 52 packages with `version`, `source`, `dependencies`, `wheels[].url`, `wheels[].hash`. Header annotates the resolver state and the source `pyproject.toml`.
- `apps/backend/.venv/` — local virtualenv (created by `uv sync`, gitignored).

## Verification Results

All plan-level verification commands pass (run from `apps/backend/`):

1. `test -f uv.lock` — OK
2. `uv run python --version` → `Python 3.12.12` (matches `^Python 3.12`) — OK
3. `uv run ruff --version` → `ruff 0.15.12` (≥ 0.6) — OK
4. `uv run mypy --version` → `mypy 1.20.2` (≥ 1.10) — OK
5. `uv run lint-imports --version` → `import-linter 2.11` (≥ 2.0) — OK
6. `uv run pytest --version` → `pytest 9.0.3` (≥ 8.0) — OK
7. `uv run python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"` → `1.3.0` — OK
8. `uv run python -c "import fastapi, sqlalchemy, asyncpg, alembic, pydantic, pydantic_settings, structlog, arq, redis, httpx, uvicorn"` — OK (no errors)
9. `grep -q 'name = "sportzal-backend"' apps/backend/uv.lock` — OK
10. `test -d apps/backend/.venv` — OK

Acceptance criteria from `<task>` block: 9/9 satisfied.

Plan-level `<verification>` block: 4/4 satisfied (uv.lock exists+committed; `uv run <tool>` works for ruff/mypy/lint-imports/pytest; all 11 runtime deps importable; Python is 3.12.x in venv).

## Decisions Made

- **Did NOT migrate to PEP 735 `[dependency-groups]`** — `uv lock` and every `uv run` invocation print: `warning: The 'tool.uv.dev-dependencies' field (used in 'pyproject.toml') is deprecated and will be removed in a future release; use 'dependency-groups.dev' instead`. Plan 01 honored CONTEXT.md D-15 lock on `[tool.uv] dev-dependencies` deliberately. The deprecation is forward-looking; uv 0.11.6 still resolves and installs correctly. Migration is a 1-line PR (`[tool.uv] dev-dependencies` → `[dependency-groups] dev`) to be handled when the user chooses, not in Phase 2.
- **Accepted resolver-chosen versions above floor pins for every dep.** No version conflicts; the registry served clean wheels for all 52 packages on macOS x86_64 + Python 3.12. uv's hash-verified install is the supply-chain mitigation per the threat register (T-02-04 mitigate / T-02-05 accept).
- **uv used the local cpython-3.12.12 install** (not 3.12.13 which is "download available"); both satisfy `requires-python = ">=3.12,<3.13"`. The lockfile is portable: `uv sync` on a different 3.12.x will install the same wheels (or build sdists for matching ABIs), so this choice has no reproducibility cost.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes triggered; no Rule 4 architectural questions surfaced.

The deprecation warning is informational and does not affect correctness — explicitly per CONTEXT.md D-15 the team's lock on `[tool.uv] dev-dependencies` is the source of truth for Phase 2.

## Issues Encountered

None. `uv lock` resolved on the first attempt; `uv sync` installed all 52 packages without a single retry. No SSL, hash, or wheel-build issues.

## User Setup Required

None — `uv` was already on PATH (`/Users/andre/.local/bin/uv`, version 0.11.6) and CPython 3.12.12 was already installed in the user's uv-managed Python directory.

For another developer cloning this repo: `cd apps/backend && uv sync` is sufficient to reproduce this venv from the committed `uv.lock` (uv will auto-download CPython 3.12.x if needed).

## Next Phase Readiness

- Plans 03–07 can now write Python that imports any of the 11 runtime deps — the venv has them resolved and installed.
- Plan 08's verification battery has the toolchain it needs: `uv run ruff check .`, `uv run mypy app`, `uv run lint-imports`. The `app/` package will land in Plans 03–06; mypy+lint-imports require it to exist before they have anything to check.
- Phase 3 will consume `uv.lock` for Docker image reproducibility (`uv sync --frozen` in CI / Dockerfile).
- No blockers for Plan 02-03.

## Self-Check

Verifying claims before final commit:

**Created files:**
- `apps/backend/uv.lock` — FOUND (88,782 bytes, contains `name = "sportzal-backend"`)
- `apps/backend/.venv/` — FOUND (directory present; gitignored, not committed — verified via `test -d`, not git)

**Commits:**
- `be21758` (Task 1 — uv.lock) — FOUND in `git log --oneline`

**Verification battery:**
- All 5 `uv run <tool> --version` commands exit 0 with versions ≥ floor pins — VERIFIED
- All 11 runtime imports succeed in a single Python invocation — VERIFIED
- Python inside venv is 3.12.12 (matches `^Python 3.12`) — VERIFIED

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
