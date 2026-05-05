---
phase: 13
plan: 01
subsystem: housekeeping
tags: [cleanup, contracts, telegram, dx]
requirements-completed: [housekeeping]
success-criteria-closed: [SC-1, SC-3, SC-4]
dependency-graph:
  requires: []
  provides:
    - "Telegram contract types byte-aligned with backend"
    - "Fresh-clone dev boot without TELEGRAM_BOT_TOKEN/USERNAME"
    - "members/ module tree absent (already gone in baseline)"
  affects:
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/services/mock/auth.ts
    - apps/backend/app/core/config.py
    - apps/backend/.env.example
    - apps/backend/app/workers/telegram_bot.py
tech-stack:
  added: []
  patterns:
    - "Sentinel placeholder env values + worker fail-fast guard for fresh-clone DX"
key-files:
  created: []
  modified:
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/services/mock/auth.ts
    - apps/backend/app/core/config.py
    - apps/backend/.env.example
    - apps/backend/app/workers/telegram_bot.py
decisions:
  - "Use sentinel-string placeholder ('placeholder-telegram-bot-token-not-real') over None/empty default to keep SecretStr typing clean and make grepability obvious"
  - "Worker exits with code 2 on placeholder token (not 1) to distinguish 'mis-configured' from generic runtime error"
  - "Inline `import structlog` was lifted to module-level imports per ruff/mypy convention"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-05"
  tasks-completed: 3
  tasks-planned: 3
  commits: 2
---

# Phase 13 Plan 01: v1.1 Minor Cleanup Summary

Three independent v1.1 cleanups: drop dead `expiresAt` from Telegram frontend contracts, verify obsolete `app/modules/members/` is gone (baseline already clean), and add fresh-clone-friendly placeholder defaults for `TELEGRAM_BOT_TOKEN`/`TELEGRAM_BOT_USERNAME` with a worker-side fail-fast guard.

## What Was Done

### Task 1 — Drop dead `expiresAt` from Telegram contracts (SC #1)

- Removed `expiresAt: string` from `TelegramStartResponse` and `expiresAt?: string` from `TelegramStatusResponse` in `apps/admin-web/src/shared/api/contracts/auth.ts`.
- Removed the corresponding `expiresAt` writes in the mock impl `apps/admin-web/src/shared/api/services/mock/auth.ts` so mock and http impls stay shape-equal.
- Verified backend schemas (`apps/backend/app/modules/auth/schemas.py`) only return `deep_link_url`/`deep_link_token` (start) and `bound` (status).
- `pnpm typecheck` exits 0; `grep -c expiresAt` on the contracts file returns 0.
- Commit: `d0e7649`

### Task 2 — Delete `app/modules/members/` (SC #3)

- The directory was already absent in the baseline working tree — fully removed by Phase 4-02 (`git mv members → clients`, commit `9e2f652`). No `__pycache__` artifacts present.
- All acceptance criteria already satisfied at the start of this plan: `test ! -d apps/backend/app/modules/members` exits 0, `uv run lint-imports` GREEN (3/3 contracts kept), `uv run mypy app` GREEN, no `app.modules.members` import references in source.
- No commit produced for this task — see Deviations.

### Task 3 — Telegram env placeholder defaults + worker guard (SC #4)

- `apps/backend/app/core/config.py`: added `SecretStr("placeholder-telegram-bot-token-not-real")` and `"placeholder_bot"` defaults for the two telegram fields with rationale comment.
- `apps/backend/.env.example`: replaced the empty `TELEGRAM_BOT_TOKEN=` / `TELEGRAM_BOT_USERNAME=` lines with documented placeholders, including a multi-line comment explaining the constraint.
- `apps/backend/app/workers/telegram_bot.py`:
  - Lifted `import structlog` to module-level imports.
  - Added module-level constant `_PLACEHOLDER_TELEGRAM_BOT_TOKEN` (with `# noqa: S105` to silence the false-positive hardcoded-password lint).
  - Added a guard immediately after `configure_logging(settings)` that logs `telegram_bot_placeholder_token` via structlog and `raise SystemExit(2)` before any AsyncExitStack / db / redis / ptb work runs.
- Verified: `uv run ruff check app` and `uv run mypy app` GREEN; `Settings(_env_file=None)` with no `TELEGRAM_*` env vars loads the placeholder defaults without raising; full test suite (`uv run pytest -x tests/`) passes 243/243.
- Commit: `b3885bb`

## Verification

- Frontend: `cd apps/admin-web && pnpm typecheck` exits 0; `grep -c expiresAt apps/admin-web/src/shared/api/contracts/auth.ts` → 0.
- Backend lint: `cd apps/backend && uv run ruff check app` GREEN.
- Backend types: `cd apps/backend && uv run mypy app` GREEN (58 files, no issues).
- Architecture: `cd apps/backend && uv run lint-imports` GREEN (3/3 contracts kept).
- Tests: `cd apps/backend && uv run pytest -x tests/` GREEN (243 passed).
- Filesystem: `apps/backend/app/modules/members/` absent.
- Boot smoke: `Settings(_env_file=None)` with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_BOT_USERNAME` unset returns the placeholder values without raising.

## Deviations from Plan

### 1. [Rule 3 – Out-of-scope baseline state] Task 2 produced no commit because the directory was already gone

- **Found during:** Task 2 read-first step.
- **Issue:** `find apps/backend/app/modules/members/` returned `No such file or directory`. The plan assumed an empty `members/` directory with `__pycache__` was still present in the working tree, but it had already been removed by Phase 4-02 commit `9e2f652` (`git mv members → clients`). No tracked files reference `app.modules.members` anymore (only `app.modules.memberships` — a different module — appears in `.importlinter`).
- **Fix:** No file change required. All acceptance criteria for SC #3 (`test ! -d`, `uv run lint-imports`, `uv run mypy`) were already satisfied at the start of this plan. No commit produced for Task 2.
- **Files modified:** none.
- **Commit:** none.

### 2. [Rule 1 – Lint false-positive] Added `# noqa: S105` to the placeholder constant

- **Found during:** Task 3 ruff verification.
- **Issue:** `ruff` flagged the module-level constant `_PLACEHOLDER_TELEGRAM_BOT_TOKEN = "placeholder-telegram-bot-token-not-real"` as `S105 Possible hardcoded password assigned`. The string is intentionally a non-secret sentinel — that is the entire point of the design.
- **Fix:** Append `# noqa: S105` to the assignment so the lint stays clean while preserving the sentinel behavior. The string itself is unchanged (it MUST match the value in `app/core/config.py` for the equality guard to fire).
- **Files modified:** `apps/backend/app/workers/telegram_bot.py`.
- **Commit:** `b3885bb` (combined with the Task 3 changes).

### 3. [Rule 1 – Lint hygiene] Lifted `import structlog` to module-level imports

- **Found during:** Task 3 implementation.
- **Issue:** Plan suggested an in-function `import structlog` but this would trip ruff's `PLC0415` if enabled later, and is inconsistent with the rest of the file (all other imports are module-level).
- **Fix:** Added `import structlog` to the top-of-file imports next to the stdlib block (per ruff isort convention: third-party group). Verified `uv run ruff check app` stays green.
- **Files modified:** `apps/backend/app/workers/telegram_bot.py`.
- **Commit:** `b3885bb`.

## Commits

| Task | Commit  | Message                                                     |
| ---- | ------- | ----------------------------------------------------------- |
| 1    | d0e7649 | feat(13-01): drop dead expiresAt field from Telegram contracts |
| 2    | —       | (no commit — baseline already satisfied criteria)           |
| 3    | b3885bb | feat(13-01): add safe placeholder defaults for Telegram bot env vars |

## Self-Check: PASSED

- File `apps/admin-web/src/shared/api/contracts/auth.ts`: FOUND, no `expiresAt` lines.
- File `apps/admin-web/src/shared/api/services/mock/auth.ts`: FOUND, no `expiresAt` writes.
- File `apps/backend/app/core/config.py`: FOUND, contains placeholder defaults.
- File `apps/backend/.env.example`: FOUND, contains placeholder defaults + rationale comment.
- File `apps/backend/app/workers/telegram_bot.py`: FOUND, contains `_PLACEHOLDER_TELEGRAM_BOT_TOKEN` constant and `raise SystemExit(2)` guard.
- Commit `d0e7649`: FOUND in `git log`.
- Commit `b3885bb`: FOUND in `git log`.
