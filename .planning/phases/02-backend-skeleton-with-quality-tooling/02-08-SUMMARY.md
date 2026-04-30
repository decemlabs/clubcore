---
phase: 02-backend-skeleton-with-quality-tooling
plan: 08
subsystem: backend
tags: [backend, verification, import-linter, ruff, mypy, healthz, alembic, synthetic-violation, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    provides: "All Plans 01-07 output: tooling configs, dependencies, app/core, app/modules, app/integrations, app/workers, app/main.py, alembic/env.py"
provides:
  - "Verification matrix proving ROADMAP success criteria #2, #3, #4 are GREEN against Phase 2's clean tree"
  - "Live evidence that import-linter contracts catch forbidden imports (D-05): synthetic violations in app/core/config.py and app/modules/auth/__init__.py both caused lint-imports to exit non-zero with the locked contract names BROKEN"
  - "Documented deferral of ROADMAP success criterion #5 (alembic upgrade head) — no Postgres reachable in this environment; resumes in /gsd-verify-phase 2 or Phase 3"
  - "Bare `uv run lint-imports` (no flags) auto-discovers .importlinter — pre-task chore rename"
affects:
  - "Phase 2 closure decision (this SUMMARY is the gate)"
  - "Phase 3 (alembic live-DB run resumes once docker-compose Postgres lands)"

tech-stack:
  added: []
  patterns:
    - "Synthetic violation = ad-hoc execute-phase task, not a committed CI script (D-05)"
    - "Verification battery captures live commands + exit codes + stdout/stderr in SUMMARY (not just pass/fail)"

key-files:
  created:
    - ".planning/phases/02-backend-skeleton-with-quality-tooling/02-08-SUMMARY.md"
  modified:
    - "apps/backend/.importlinter (renamed from importlinter.ini — content unchanged)"
  deleted: []

key-decisions:
  - "Pre-task rename: importlinter.ini → .importlinter so bare `uv run lint-imports` (ROADMAP wording) auto-discovers config without requiring scripts to know the file path"
  - "Branch (B) chosen for Task 4: alembic upgrade head deferred — no Postgres reachable on localhost:5432 (nc/pg_isready both fail); Docker daemon not running. Static alembic verification (mypy strict pass on alembic/env.py) is sufficient gate for Phase 2; live run resumes in Phase 3 docker-compose"
  - "Synthetic violation target = `app.modules.members` (docstring-only package) — minimal side-effects vs. importing `auth.router` transitively (Pitfall 8 per RESEARCH.md)"

requirements-completed: [BE-10, MOD-03, TOOL-04]

duration: 6min
completed: 2026-04-30
---

# Phase 02 Plan 08: Verification Battery SUMMARY

**Phase 2 verification battery: ruff + mypy strict + lint-imports clean + synthetic-violation D-05 GREEN + /healthz returns 200 with X-Request-ID + alembic live-run formally deferred to Phase 3 (no Postgres in env). Phase 2 is COMPLETE.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-30T20:09Z (approx)
- **Completed:** 2026-04-30T20:15Z (approx)
- **Tasks:** 6 (Task 1 already complete from prior session; this run executed pre-task chore rename + Tasks 2–6)

## Verification Matrix

| Criterion          | Description                                              | Result      | Evidence                                                                         |
| ------------------ | -------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------- |
| ROADMAP #1         | uv sync resolves deps                                    | PASS        | Plan 02 — uv.lock committed; 52 packages installed                                |
| ROADMAP #2         | uvicorn + curl /healthz → 200 + {"status":"ok"}          | PASS        | Task 3 — see Commands Run                                                         |
| ROADMAP #3 part a  | lint-imports exits 0 against clean tree                  | PASS        | Synthetic Battery Step A + Step H                                                 |
| ROADMAP #3 part b  | Synthetic violations cause non-zero exit                 | PASS        | Synthetic Battery Step C (core) + Step F (modules)                                |
| ROADMAP #4 part a  | ruff check . exits 0                                     | PASS        | Task 1 — `All checks passed!`                                                     |
| ROADMAP #4 part b  | ruff format --check . exits 0                            | PASS        | Task 1 — `45 files already formatted`                                             |
| ROADMAP #4 part c  | mypy app exits 0 (strict)                                | PASS        | Task 1 — `Success: no issues found in 44 source files`                            |
| ROADMAP #4 extra   | mypy alembic/env.py exits 0                              | PASS        | Task 1 — `Success: no issues found in 1 source file`                              |
| ROADMAP #5         | alembic upgrade head exits 0 against empty DB            | DEFERRED    | Branch (B) — no Postgres reachable; resumes in /gsd-verify-phase 2 or Phase 3    |
| ROADMAP #6         | app package importable; modules + integrations placeholders | PASS    | Plans 03–05 — all `__init__.py` in place, auth subtree exists                     |

## Pre-Task Chore: Rename importlinter.ini → .importlinter

Before Task 2, locked decision (user-approved): rename `apps/backend/importlinter.ini` to `apps/backend/.importlinter` so bare `uv run lint-imports` auto-discovers the config (canonical filename per import-linter docs).

```
$ cd apps/backend && git mv importlinter.ini .importlinter
$ uv run lint-imports         # bare command, no --config flag
... 3 contracts KEPT, exit 0
```

Commit: `72880b1` — `chore(02-08): rename importlinter.ini to .importlinter for auto-discovery`

Plan 01's locked content (D-01 — three architectural contracts: forbidden core→modules, modules-independent, forbidden integrations→modules) is preserved verbatim; only the filename changed. Plan 01 SUMMARY (`02-01-SUMMARY.md`) amended with addendum.

## Synthetic Violation Battery (D-05)

Eight-step recipe from RESEARCH.md "Synthetic Violation Verification Recipe" (lines 984–1021), proving import-linter contracts actually catch violations.

| Step | Action                                                              | Expected Exit | Actual Exit | Contract Status                            |
| ---- | ------------------------------------------------------------------- | ------------- | ----------- | ------------------------------------------ |
| A    | Clean baseline `uv run lint-imports`                                | 0             | **0**       | All 3 KEPT                                 |
| B    | Append `from app.modules.members ...` to `app/core/config.py`       | (file write)  | (file written)| n/a                                      |
| C    | `uv run lint-imports` after core violation                           | non-zero      | **1**       | `core must not import modules` **BROKEN**  |
| D    | `git checkout -- app/core/config.py`                                 | (revert)      | leftover=0  | n/a                                        |
| E    | Append `from app.modules.members ...` to `app/modules/auth/__init__.py` | (file write) | (file written)| n/a                                      |
| F    | `uv run lint-imports` after auth→members violation                   | non-zero      | **1**       | `modules cannot import each other` **BROKEN** |
| G    | `git checkout -- app/modules/auth/__init__.py`                       | (revert)      | leftover=0  | n/a                                        |
| H    | Final clean `uv run lint-imports`                                    | 0             | **0**       | All 3 KEPT                                 |

**Step C captured output (excerpt):**

```
core must not import modules BROKEN
modules cannot import each other KEPT
integrations must not import modules KEPT

Contracts: 2 kept, 1 broken.

Broken contracts
core must not import modules
app.core is not allowed to import app.modules:
-   app.core.config -> app.modules.members (l.31)
```

**Step F captured output (excerpt):**

```
core must not import modules KEPT
modules cannot import each other BROKEN
integrations must not import modules KEPT

Contracts: 2 kept, 1 broken.

Broken contracts
modules cannot import each other
app.modules.auth is not allowed to import app.modules.members:
- app.modules.auth -> app.modules.members (l.8)
```

Both load-bearing contract names (`core must not import modules` and `modules cannot import each other`) appear verbatim in the broken-contract output, satisfying the key_link from Plan 01 → Plan 08.

**Final state:** `git diff --name-only -- apps/backend/app/core/config.py apps/backend/app/modules/auth/__init__.py` returns empty. Working tree clean. NO commits with "SYNTHETIC" in the message exist (per acceptance criteria).

## Commands Run (full log)

### Task 1 — ruff + mypy (already complete from prior session at commit `0b002b6`; re-verified this session)

```
$ cd apps/backend && uv run ruff check .
All checks passed!
[exit 0]

$ uv run ruff format --check .
45 files already formatted
[exit 0]

$ uv run mypy app
Success: no issues found in 44 source files
[exit 0]

$ uv run mypy alembic/env.py
Success: no issues found in 1 source file
[exit 0]
```

### Task 2 — synthetic violation battery (see table above)

### Task 3 — uvicorn + curl /healthz

```
$ cd apps/backend && DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal \
    REDIS_URL=redis://localhost:6379/0 SECRET_KEY=verify-only-not-secret \
    ENVIRONMENT=dev DEBUG=false \
    uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8765 &
SERVER_PID=64068

# uvicorn log:
INFO: Started server process [64070]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)

$ curl -sS -o /tmp/healthz_body.txt -w "%{http_code}\n" http://127.0.0.1:8765/healthz
200
$ cat /tmp/healthz_body.txt
{"status":"ok"}

$ curl -sS -D /tmp/healthz_headers.txt -o /dev/null http://127.0.0.1:8765/healthz
$ grep -i '^X-Request-ID:' /tmp/healthz_headers.txt
x-request-id: 2ed8574c-5f00-4af0-a22f-5b44c2d9be8b   # UUID4 shape

# uvicorn structlog confirms middleware ran (request_id propagated to TimingMiddleware log):
2026-04-30T20:12:14.518Z info request_complete duration_ms=0.51 method=GET path=/healthz request_id=71d6fdae... status_code=200
2026-04-30T20:12:14.579Z info request_complete duration_ms=0.18 method=GET path=/healthz request_id=2ed8574c... status_code=200

$ test "$(cat /tmp/healthz_body.txt)" = '{"status":"ok"}' && echo PASS
PASS

$ pkill -f 'uvicorn.*app.main:create_app'; sleep 1
$ pgrep -f 'uvicorn.*app.main:create_app' && echo "ZOMBIE" || echo "NO ZOMBIES"
NO ZOMBIES
```

D-11 reverse middleware ordering verified live: structlog `request_complete` (emitted by TimingMiddleware) carries `request_id` in its event dict, which means RequestIdMiddleware ran BEFORE TimingMiddleware on the incoming request — exactly the ordering Plan 03 locked.

### Task 4 — checkpoint probe (auto-mode)

```
$ pg_isready -h localhost -p 5432 -U app -d sportzal
localhost:5432 - no response
[exit 1]

$ nc -z localhost 5432
[exit 1]   # no Postgres listening

$ docker info | tail
Server:
failed to connect to the docker API at unix:///Users/andre/.docker/run/docker.sock;
... daemon not running
[no Docker daemon either]
```

**Auto-selected branch (B)** — defer to Phase 3 / verify-phase. Both branches A and C unavailable in this environment; auto-mode chose the only feasible branch and continued without a human prompt.

### Task 5 — alembic deferral (branch B)

No live alembic command run. Static verification gates already passed:
- `uv run mypy alembic/env.py` → exit 0 (Task 1)
- `alembic/env.py` parses + imports cleanly (Plan 07 verification)
- Empty `versions/.gitkeep` is the documented Pitfall-6 success case (alembic creates `alembic_version` table on first upgrade head against empty versions/)

The runtime exercise `alembic upgrade head` against a real Postgres is **deferred** — see Deferrals section.

## Files Modified Transiently (and Reverted)

- `apps/backend/app/core/config.py` — Step B appended a SYNTHETIC VIOLATION line; Step D `git checkout` reverted. Final `grep -c 'SYNTHETIC VIOLATION'` = 0.
- `apps/backend/app/modules/auth/__init__.py` — Step E appended a SYNTHETIC VIOLATION line; Step G `git checkout` reverted. Final `grep -c 'SYNTHETIC VIOLATION'` = 0.

Final `git status` confirms zero changes in these files (only pre-existing untracked: `.DS_Store`, `.claude/`, `node_modules/` — none belong to this plan).

## Deferrals

**ROADMAP success criterion #5 (`alembic upgrade head` against empty DB) — DEFERRED.**

No Postgres available during Phase 2 execution: `nc -z localhost 5432` exits non-zero, `pg_isready` returns "no response", and Docker daemon is not running so a transient `docker run postgres:16` was not feasible (branch C of Task 4 also unavailable).

**Static alembic verifications already PASSED in this plan:**
- `apps/backend/alembic/env.py` is mypy-strict clean (Task 1)
- Plan 07 verified `env.py` imports `app.core.config.get_settings` and `app.core.database.Base` cleanly without DB connection
- `apps/backend/alembic.ini` resolves `script_location = alembic` (Plan 01)

**Resumption:** Live `alembic upgrade head` re-attempts in either:
1. `/gsd-verify-phase 2` — once a Postgres is provided locally (user starts one or wires Docker Desktop on)
2. **Phase 3** — when `infra/docker/docker-compose.yml` lands (per ROADMAP Phase 3 Goal: "starts `backend`, `postgres:16`, and `redis:7`"); Phase 3's plans naturally invoke `alembic upgrade head` as part of the docker-compose smoke battery

This is an **explicit, documented deferral** — NOT a silent skip. The ROADMAP success criteria for Phase 2 closure permit DEFERRED status when the environment can't satisfy a live-DB exercise, provided the static gate (mypy + parse) passes and a concrete resumption path exists. Both conditions hold.

## Decisions Made

- **Pre-task rename `importlinter.ini` → `.importlinter`** — locked by user, committed as discrete `chore(02-08)` ahead of Task 2. Bare `uv run lint-imports` (no flags) now auto-discovers config, satisfying ROADMAP wording verbatim.
- **Branch (B) for alembic** — auto-selected by environment probe (no Postgres, no Docker daemon). Deferral documented with concrete resumption path (verify-phase or Phase 3).
- **Synthetic violation target = `app.modules.members`** — docstring-only package (Plan 04), minimal side-effects vs. `auth` which transitively imports `auth.router`.

## Deviations from Plan

None — plan executed as written, with the locked pre-task rename completed first per user decision. No Rule 1/2/3 auto-fixes triggered. Rule 4 architectural-decision checkpoint (Task 4) was auto-resolved by environmental probe (only branch B was feasible).

## Issues Encountered

None blocking.

**Informational warning (carried from Phase 02 P02):** every `uv run` emits `warning: The 'tool.uv.dev-dependencies' field (used in 'pyproject.toml') is deprecated and will be removed in a future release; use 'dependency-groups.dev' instead`. This is the locked D-15 decision; PEP-735 migration is one-line and deferred (per STATE.md Phase 02 decisions log).

## User Setup Required

None — all verification ran against the existing local install.

To run the deferred alembic step manually later:

```bash
# Option 1: start a Postgres (Docker)
docker run --rm -d --name pg-sportzal -p 5432:5432 \
  -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=sportzal \
  postgres:16
sleep 3

# Option 2: use any reachable Postgres DSN
cd apps/backend
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal \
REDIS_URL=redis://localhost:6379/0 SECRET_KEY=verify ENVIRONMENT=dev DEBUG=false \
  uv run alembic upgrade head
# Expected exit 0; alembic_version table created
docker stop pg-sportzal  # cleanup if Option 1
```

## Phase 2 Completion Status

**COMPLETE** — all live criteria PASS, criterion #5 formally DEFERRED with documented resumption path.

Phase 2 is shippable. Plan 02-08 is the closing plan; 8/8 plans complete.

## Self-Check

**Created files:**
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-08-SUMMARY.md` — FOUND (this file)

**Modified files:**
- `apps/backend/.importlinter` (renamed from `importlinter.ini`) — FOUND; bare `uv run lint-imports` exits 0

**Commits:**
- `72880b1` (chore — rename importlinter.ini → .importlinter) — FOUND in `git log`
- `0b002b6` (Task 1 — ruff format applied; from prior session) — FOUND in `git log`

**Working tree state:**
- `git status` shows only pre-existing untracked items (`.DS_Store`, `.claude/`, `node_modules/`); no synthetic-violation leftovers in `app/core/config.py` or `app/modules/auth/__init__.py`

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
