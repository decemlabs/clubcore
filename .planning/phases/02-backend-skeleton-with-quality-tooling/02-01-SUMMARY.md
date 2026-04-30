---
phase: 02-backend-skeleton-with-quality-tooling
plan: 01
subsystem: infra
tags: [backend, scaffolding, tooling, uv, ruff, mypy, import-linter, alembic, python, fastapi]

requires:
  - phase: 01-monorepo-restructure-frontend-move
    provides: "apps/ directory at repo root; pnpm-workspace.yaml registers apps/* and packages/*"
provides:
  - "apps/backend/ directory with all six Phase-2 tooling config files"
  - "pyproject.toml ready for `uv lock` (Plan 02): Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, structlog, ARQ, redis, httpx, uvicorn — plus dev-deps ruff/mypy/import-linter/pytest/pytest-asyncio"
  - "ruff.toml selecting 11 rule families (E, F, I, B, UP, ASYNC, S, DTZ, N, SIM, RUF) with line-length=100 and per-file-ignores for alembic/env.py"
  - "mypy strict + pydantic.mypy plugin + alembic.env override (no-untyped-call)"
  - "importlinter.ini with three architectural contracts (forbidden core→modules, independence over 9 modules, forbidden integrations→modules)"
  - "alembic.ini pointing to script_location = alembic with prepend_sys_path = . (env.py + versions/.gitkeep land in Plan 07)"
  - ".env.example with working dev defaults for DATABASE_URL, REDIS_URL, ENVIRONMENT, DEBUG, SECRET_KEY"
  - ".gitignore covering Python/.venv/cache artifacts (uv.lock NOT ignored — committed)"
  - "Legacy empty root-level backend/ directory removed"
affects:
  - "Plan 02-02 (uv environment + lockfile generation)"
  - "Plan 02-03..02-07 (write Python source under apps/backend/app/)"
  - "Plan 02-08 (run quality gates: ruff, mypy, lint-imports, synthetic-violation)"
  - "Phase 03 (tests, Dockerfile, docs — all consume apps/backend/ structure)"

tech-stack:
  added:
    - "Python 3.12 (pinned via requires-python)"
    - "uv (project manifest convention, dev-dependencies under [tool.uv])"
    - "FastAPI 0.115+ (declared, not yet imported)"
    - "SQLAlchemy 2.0 async + asyncpg (declared)"
    - "Alembic async (config only; env.py in Plan 07)"
    - "Pydantic v2 + pydantic-settings (declared)"
    - "structlog, ARQ, redis, httpx, uvicorn[standard] (declared)"
    - "ruff 0.6+ (lint+format; standalone ruff.toml)"
    - "mypy 1.10+ strict + pydantic.mypy plugin"
    - "import-linter 2.0+ (three contracts)"
    - "pytest 8.0+ + pytest-asyncio (declared as dev-dep)"
  patterns:
    - "Standalone ruff.toml (not [tool.ruff] in pyproject) per CONTEXT.md"
    - "Mixed import-linter contract types: forbidden + independence + forbidden"
    - "root_packages (plural) for future-proofing if workers/integrations split"
    - "Alembic placeholder sqlalchemy.url, runtime override from Settings.database_url"
    - "Working dev defaults in .env.example, not placeholders"
    - "uv.lock committed (lockfile is project state)"

key-files:
  created:
    - "apps/backend/.gitignore"
    - "apps/backend/.env.example"
    - "apps/backend/pyproject.toml"
    - "apps/backend/ruff.toml"
    - "apps/backend/importlinter.ini"
    - "apps/backend/alembic.ini"
  modified: []
  deleted:
    - "backend/ (legacy empty root-level directory; was untracked)"

key-decisions:
  - "Honored CONTEXT.md D-15 lock on `[tool.uv] dev-dependencies` over PEP 735 `[dependency-groups]`; both work today with uv, user can flip in a single PR if desired"
  - "Standalone ruff.toml under [lint] section (ruff v0.6+ convention) — not nested under [tool.ruff.lint]"
  - "importlinter root_packages plural form (one app today; future-proof for additional top-level packages)"
  - "alembic.ini sqlalchemy.url is a non-empty placeholder string — env.py overrides it from Settings.database_url at runtime; empty value would trigger 'no driver' before env.py runs"
  - "S101 (assert) ignored globally in ruff — pytest will use asserts when it lands in Phase 3"
  - "Per-file-ignore for alembic/env.py: skip S (bandit) and I001 (import order) since Alembic API is untyped and template-generated"

patterns-established:
  - "Tooling-config separation: ruff/import-linter/alembic each get their own canonical INI/TOML file; mypy stays inside pyproject.toml (no separate mypy.ini)"
  - "Floor-pinned dependencies (>=X.Y) with uv.lock as the freeze-target"
  - "Three architectural contracts (core⊥modules, modules⊥each-other, integrations⊥modules) named verbatim — Plan 08 synthetic-violation test asserts these strings appear in stderr"

requirements-completed: [TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06]

duration: 2min
completed: 2026-04-30
---

# Phase 2 Plan 01: Backend Skeleton — Tooling Configs Summary

**apps/backend/ scaffolded with six tooling configs (uv pyproject, ruff, mypy strict, three import-linter contracts, alembic, env example, gitignore) and legacy empty root backend/ removed — ready for `uv lock` and Python source in subsequent plans.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-30T19:28:36Z
- **Completed:** 2026-04-30T19:30:50Z
- **Tasks:** 6
- **Files created:** 6
- **Files deleted:** 1 directory (untracked)

## Accomplishments

- Removed legacy empty root-level `backend/` directory left over from pre-monorepo state (was untracked; no git artifact)
- Created `apps/backend/` with `.gitignore` (Python build/cache ignores; `uv.lock` intentionally not ignored) and `.env.example` with working dev defaults
- Wrote `pyproject.toml` declaring the locked stack (FastAPI 0.115+, SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, pydantic-settings, structlog, ARQ, redis, httpx, uvicorn) plus dev-deps (ruff, mypy, import-linter, pytest, pytest-asyncio); mypy strict + pydantic.mypy plugin + alembic.env override
- Wrote standalone `ruff.toml` selecting 11 rule families (E, F, I, B, UP, ASYNC, S, DTZ, N, SIM, RUF), line-length 100 (matches frontend Prettier), per-file-ignore for `alembic/env.py`
- Wrote `importlinter.ini` with three locked contracts (verbatim from CONTEXT.md D-01): forbidden core→modules, independence over 9 modules, forbidden integrations→modules — contract names are load-bearing for Plan 08 synthetic-violation assertion
- Wrote `alembic.ini` with `script_location = alembic`, `prepend_sys_path = .`, placeholder sqlalchemy.url (env.py overrides at runtime in Plan 07), UTC file_template, standard logger sections

## Task Commits

Each task was committed atomically (Task 1 had no git artifact since the deleted directory was untracked; its action is documented in the Task 2 commit body):

1. **Task 1: Delete empty root-level backend/** — _no separate commit (untracked; documented in `dff231b` body)_
2. **Task 2: Create .gitignore + .env.example** — `dff231b` (feat)
3. **Task 3: Create pyproject.toml** — `1e4c7f4` (feat)
4. **Task 4: Create ruff.toml** — `852c99c` (feat)
5. **Task 5: Create importlinter.ini** — `786af68` (feat)
6. **Task 6: Create alembic.ini** — `4ce749a` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Files Created/Modified

- `apps/backend/.gitignore` — Python build/cache ignores (`.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`, `*.pyc`); `uv.lock` deliberately absent
- `apps/backend/.env.example` — DATABASE_URL (asyncpg DSN), REDIS_URL, ENVIRONMENT (dev/staging/prod), DEBUG, SECRET_KEY (intentionally non-secret in dev)
- `apps/backend/pyproject.toml` — `[project]` with name `sportzal-backend`, requires-python `>=3.12,<3.13`, runtime + uv dev-deps; `[tool.mypy]` strict + pydantic.mypy plugin; `[[tool.mypy.overrides]]` for `alembic.env`
- `apps/backend/ruff.toml` — `[lint] select` 11 codes, ignore `S101`; `[lint.per-file-ignores]` for `alembic/env.py`; `[format]` quote-style double, indent space; `target-version = "py312"`, `line-length = 100`
- `apps/backend/importlinter.ini` — `[importlinter] root_packages = app`; three contracts: `core-not-depend-on-modules`, `modules-independent`, `integrations-not-depend-on-modules` with the nine module packages explicitly listed
- `apps/backend/alembic.ini` — `[alembic] script_location = alembic`, `prepend_sys_path = .`, placeholder sqlalchemy.url, UTC file_template; standard `[loggers]/[handlers]/[formatters]` blocks
- `backend/` (root) — directory removed (was empty, untracked)

## Verification Results

All six plan-level verification commands pass:

1. `test ! -e backend` — OK
2. `ls apps/backend/` shows: `.gitignore`, `.env.example`, `pyproject.toml`, `ruff.toml`, `importlinter.ini`, `alembic.ini` — OK
3. `pyproject.toml` parses as valid TOML — OK
4. `ruff.toml` parses as valid TOML — OK
5. `importlinter.ini` exposes the three contract sections — OK (`importlinter:contract:modules-independent` present, with all 9 modules)
6. `alembic.ini` `[alembic] script_location` resolves to `alembic` — OK

## Decisions Made

- **Followed CONTEXT.md D-15 lock on `[tool.uv] dev-dependencies`** over PEP 735 `[dependency-groups]`. RESEARCH.md surfaced that `[dependency-groups]` is the modern upstream convention; both keys work with uv today (uv merges them). Honoring the user lock per planner-context-fidelity rule. Documented in pyproject.toml comment so a future migration is one-line.
- **Standalone `ruff.toml` with `[lint]` (not `[tool.ruff.lint]`)** — ruff v0.6+ convention for standalone configs (the `[tool.ruff.*]` form is for embedded-in-pyproject usage).
- **`root_packages` (plural) in importlinter.ini** — keeps the door open for future top-level packages without an INI rewrite.
- **Non-empty placeholder for `sqlalchemy.url` in alembic.ini** — `env.py` (Plan 07) will override via `Settings.database_url`. An empty value can trigger "no driver" errors before env.py loads.
- **Per-file-ignore for `alembic/env.py`** in ruff: `S` (bandit) and `I001` (import order) skipped because Alembic's template-generated env.py uses untyped APIs and a non-PEP 8 import structure.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes triggered; no Rule 4 architectural questions surfaced.

## Issues Encountered

None — Task 1 (root `backend/` removal) had no git artifact because the directory was already untracked, but this was anticipated by the plan (action is filesystem-only). Documented inline in the Task 2 commit body so the deletion intent stays in the git log.

## User Setup Required

None — no external service configuration required. Configs are local-only; `uv lock` runs in Plan 02 against the manifest written here.

## Next Phase Readiness

- `pyproject.toml` is ready to be consumed by `uv lock` in Plan 02-02 (next plan).
- `ruff.toml`, `importlinter.ini`, and the mypy block in `pyproject.toml` are ready for the quality-gate runs in Plan 02-08.
- `alembic.ini` is ready for `alembic/env.py` + `versions/.gitkeep` in Plan 02-07.
- `.env.example` matches the Settings shape locked by CONTEXT.md D-15 (consumed by `app/core/config.py` in Plan 02-03 or 02-04).
- No blockers; Plan 02-02 can proceed immediately.

## Self-Check

Verifying claims before final commit:

**Created files:**
- `apps/backend/.gitignore` — FOUND
- `apps/backend/.env.example` — FOUND
- `apps/backend/pyproject.toml` — FOUND
- `apps/backend/ruff.toml` — FOUND
- `apps/backend/importlinter.ini` — FOUND
- `apps/backend/alembic.ini` — FOUND

**Commits:**
- `dff231b` (Task 2 — .gitignore + .env.example) — FOUND
- `1e4c7f4` (Task 3 — pyproject.toml) — FOUND
- `852c99c` (Task 4 — ruff.toml) — FOUND
- `786af68` (Task 5 — importlinter.ini) — FOUND
- `4ce749a` (Task 6 — alembic.ini) — FOUND

**Deleted:**
- `backend/` (root) — confirmed via `test ! -e backend`

## Self-Check: PASSED

---

## Post-Hoc Addendum (2026-04-30, during Plan 02-08 execution)

`apps/backend/importlinter.ini` was renamed to `apps/backend/.importlinter` ahead of Plan 02-08's
synthetic-violation battery. Reason: import-linter auto-discovers `.importlinter` (canonical
filename) when run as a bare `uv run lint-imports` (no `--config` flag) — and ROADMAP success
criterion #3 wording calls for `uv run lint-imports` verbatim. With the previous filename
(`importlinter.ini`), the tool either required `--config importlinter.ini` or relied on
fallback discovery that is brittle across versions. The rename is content-preserving
(only the filename changed; the three locked architectural contracts from D-01 are unchanged
and were re-verified KEPT after the rename).

- Commit: `72880b1` — `chore(02-08): rename importlinter.ini to .importlinter for auto-discovery`
- Affected key-file row in this SUMMARY (`apps/backend/importlinter.ini`) should be read as
  `apps/backend/.importlinter` from this commit forward.

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
