---
phase: 09-openapi-pipeline-api-client
plan: 01
subsystem: api
tags: [openapi, fastapi, codegen, drift-gate, python, uv]

# Dependency graph
requires:
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: cookie_secure prod-assertion (Phase 4 D-25) — script must bypass via ENVIRONMENT=dev
  - phase: 05-user-schema-email-password-auth
    provides: /api/v1/auth/login, /auth/refresh, /auth/me, /auth/logout endpoints surfaced in spec
  - phase: 07-telegram-otp-channel
    provides: /api/v1/auth/telegram/{start,status,verify} endpoints surfaced in spec
  - phase: 08-clients-module-audit-log
    provides: clients module routes surfaced in spec
provides:
  - Lifespan-safe OpenAPI export CLI (`scripts/export_openapi.py`)
  - Pinned `info.version="1.1.0"` in FastAPI factory (D-06 byte-stability)
  - First committed `apps/backend/openapi.json` artifact (1376 lines, 11 paths)
  - Byte-stable JSON output contract (`indent=2, sort_keys=True, ensure_ascii=False, "\n"`)
affects: [09-02 (openapi-typescript codegen consumes openapi.json), 09-03 (CI drift-gate diffs openapi.json), 10 (admin-web typed transport)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lifespan-skip OpenAPI export: `create_app().openapi()` bypasses combined_lifespan (no DB/Redis)"
    - "Cwd-independent script paths via `pathlib.Path(__file__).resolve().parents[1]`"
    - "Required Settings fields backfilled with `os.environ.setdefault(...)` for clean-shell portability"

key-files:
  created:
    - apps/backend/scripts/export_openapi.py
    - apps/backend/openapi.json
  modified:
    - apps/backend/app/main.py

key-decisions:
  - "Pin FastAPI version='1.1.0' explicitly in create_app() to remove implicit '0.1.0' default and stabilize info.version across platforms (D-06)."
  - "Backfill all required Settings fields (DATABASE_URL/REDIS_URL/SECRET_KEY/TELEGRAM_*) via os.environ.setdefault — script must run in clean shells with no .env (Rule 3 deviation; CONTEXT D-04 explicitly only mandated ENVIRONMENT=dev but Settings has more required fields without defaults)."
  - "Use pathlib.Path(__file__).resolve().parents[1] for cwd-independent path resolution — script writes apps/backend/openapi.json regardless of caller cwd."
  - "Drop the `# noqa: E402` on the deferred `from app.main` import — ruff did not flag it (RUF100 'unused noqa') because os.environ.setdefault is treated as module-level expression, not a problematic preceding statement."

patterns-established:
  - "Pattern: backend export scripts use stdlib + sync FastAPI factory access; no asyncio, no engine creation"
  - "Pattern: byte-stable JSON output for committed generated artifacts (indent=2, sort_keys=True, ensure_ascii=False, trailing newline)"
  - "Pattern: required Settings fields receive `setdefault` placeholders in scripts that don't actually use those subsystems"

requirements-completed: [API-01]

# Metrics
duration: 4min
completed: 2026-05-03
---

# Phase 9 Plan 01: OpenAPI Export CLI + First Spec Artifact Summary

**Lifespan-safe `scripts/export_openapi.py` CLI plus committed `apps/backend/openapi.json` (1376 lines, 11 paths, info.version='1.1.0') — the source of truth for Phase 9 Plans 02 (TS codegen) and 03 (CI drift-gate).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-03T17:22:51Z
- **Completed:** 2026-05-03T17:26:40Z
- **Tasks:** 3
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- `apps/backend/app/main.py` pins `version="1.1.0"` in `FastAPI(...)` (D-06 byte-stability).
- New `apps/backend/scripts/export_openapi.py` (71 LOC) — lifespan-safe, cwd-independent, byte-stable output. Two consecutive runs produce zero diff.
- First `apps/backend/openapi.json` committed: 11 paths total (8 under `/api/v1/auth/*`, plus `/healthz` and clients routes). `info.title="Sportzal API"`, `info.version="1.1.0"`.
- Confirmed: script does NOT touch Postgres or Redis — `combined_lifespan` (db_lifespan + redis_lifespan) is never entered because `.openapi()` is a sync property invoked outside the ASGI startup path.

## Task Commits

1. **Task 1: Pin FastAPI version="1.1.0"** — `84015e6` (feat) — exact +1/-0 diff in `app/main.py` between `title=` and `lifespan=`.
2. **Task 2: Create export_openapi.py** — `980a059` (feat) — 71 LOC sync CLI; ruff + mypy pass; ran successfully and produced 37266-byte spec.
3. **Task 3: Commit first openapi.json** — `712c582` (feat) — 1376-line tracked artifact; byte-stable across two consecutive runs.

## Files Created/Modified

- `apps/backend/app/main.py` — added `version="1.1.0",` kwarg to `FastAPI(...)` (single-line insertion).
- `apps/backend/scripts/export_openapi.py` — new lifespan-safe export CLI.
- `apps/backend/openapi.json` — first generated, byte-stable spec; tracked in git (not gitignored — Plan 03 drift-gate requires this).

## Decisions Made

- **FastAPI version pinned at 1.1.0** matches the active milestone (v1.1 Auth + Clients) and removes the implicit `"0.1.0"` FastAPI default from `info.version` so the spec is self-documenting and platform-stable.
- **`servers=[...]` deliberately NOT added** — D-06 marks server customization as v1.2+ deferred.
- **No `# noqa: E402` annotation** on the deferred `from app.main` import — ruff correctly does not flag E402 in this file (the only preceding statements are module-level expressions, not imports), so the noqa is unnecessary and would itself be flagged as RUF100.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Backfilled additional required Settings env-vars beyond ENVIRONMENT**
- **Found during:** Task 2 (verifying `uv run python -m scripts.export_openapi`)
- **Issue:** CONTEXT D-04 only mandates `os.environ.setdefault('ENVIRONMENT', 'dev')`, but `Settings` (apps/backend/app/core/config.py) declares five required fields without defaults: `database_url`, `redis_url`, `secret_key`, `telegram_bot_token`, `telegram_bot_username`. The local `apps/backend/.env` predates Phase 7 and is missing the two `telegram_*` fields, so a fresh script run errors with `pydantic_core.ValidationError: 2 validation errors for Settings`. A clean-shell run (CI without `.env`) would also fail on at least the three pre-Phase-7 fields.
- **Fix:** Added 5 additional `os.environ.setdefault(...)` calls (DATABASE_URL, REDIS_URL, SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME) immediately after the ENVIRONMENT setdefault. `setdefault` does not override values an operator/CI provides, so prod/staging environments are unaffected.
- **Files modified:** `apps/backend/scripts/export_openapi.py`
- **Verification:** Script runs successfully (`Wrote .../openapi.json (37266 bytes).`). Two consecutive runs produce byte-identical output.
- **Committed in:** `980a059` (Task 2 commit).

**2. [Rule 1 - Bug] Removed `# noqa: E402` annotation flagged as unused**
- **Found during:** Task 2 (`uv run ruff check scripts/export_openapi.py`)
- **Issue:** Plan instructed `from app.main import create_app  # noqa: E402 — env-prep must come first.`, but ruff returned `RUF100 [*] Unused 'noqa' directive (unused: 'E402')`. Ruff does not flag E402 here — the only preceding statements are `os.environ.setdefault(...)` expressions, which ruff's E402 implementation does not classify as code-before-import in this configuration.
- **Fix:** Replaced the `# noqa: E402` comment with a regular block comment explaining the deferred-import rationale. Code semantics unchanged.
- **Files modified:** `apps/backend/scripts/export_openapi.py`
- **Verification:** `ruff check` exits 0; `ruff format --check` clean.
- **Committed in:** `980a059` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes are correctness-essential. The Settings-backfill makes the script genuinely portable (CONTEXT D-04 narrative claim "can run in any environment that has the Python deps installed"); without it, the script could only run on machines with a full local `.env`. No scope creep.

## Issues Encountered

None — both deviations are documented above. All Task verifications and acceptance criteria passed.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 02 input ready:** `apps/backend/openapi.json` is committed and byte-stable. `pnpm --filter @sportzal/api-client codegen` will read this exact file via the relative path `../../apps/backend/openapi.json`.
- **Plan 03 input ready:** `openapi.json` is tracked (not gitignored), so `git diff --exit-code apps/backend/openapi.json` is meaningful as a CI drift-gate.
- **Phase 9 SC#1** ("Running `uv run python -m scripts.export_openapi` writes `apps/backend/openapi.json` deterministically without touching Postgres or Redis") is achieved end-to-end.

## Self-Check: PASSED

- File `apps/backend/scripts/export_openapi.py` — FOUND
- File `apps/backend/openapi.json` — FOUND
- File `apps/backend/app/main.py` — FOUND (modified)
- Commit `84015e6` (Task 1) — FOUND
- Commit `980a059` (Task 2) — FOUND
- Commit `712c582` (Task 3) — FOUND

---
*Phase: 09-openapi-pipeline-api-client*
*Completed: 2026-05-03*
