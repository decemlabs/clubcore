---
phase: 29-milestone-verification
plan: 02
subsystem: infra
tags: [arq, cron, operator-cli, verification, telegram, postgres]

# Dependency graph
requires:
  - phase: 27-expiring-soon-telegram-notifications
    provides: send_expiring_notifications async cron callable + WorkerSettings.on_startup/on_shutdown
  - phase: 18-arq-scheduled-expire-memberships
    provides: WorkerSettings class (ctx lifecycle + cron-resolution invariant assertion)
provides:
  - apps/backend/scripts/run_expiring_cron_once.py — in-process one-shot operator runner for the 06:15 MSK expiring-soon cron
  - TM-29-02 + TM-29-03 dual env-var safety gate pattern (DATABASE_URL host check + TELEGRAM_SANDBOX_CHAT_ID presence check)
affects: [29-03-debt-04-execution, 29-04-cross-phase-smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator-CLI hybrid pattern: export_openapi.py CLI shape (`async _run() -> int` + sync `main()` + `raise SystemExit(main())`) combined with WorkerSettings.on_startup ctx construction (no inline db_lifespan_manager)"
    - "Defence-in-depth env-var gates for verification-only operator scripts: stderr error + return 1 on missing precondition, fail-closed before any side-effect"

key-files:
  created:
    - apps/backend/scripts/run_expiring_cron_once.py
  modified: []

key-decisions:
  - "Chose script form (not inline `python -c` heredoc) per D-29-03 — single file, no duplicated WorkerSettings.on_startup heredoc; mirrors export_openapi.py operator-CLI convention"
  - "TM-29-03 env-presence guard is explicitly documented as necessary-but-not-sufficient in the module docstring; the load-bearing mitigation (operator's `UPDATE clients SET telegram_user_id = $TELEGRAM_SANDBOX_CHAT_ID`) lives in plans 29-03/29-04"
  - "Script does NOT add CLI arg parsing — single job (fire expiring cron); a separate operator script would own expire_memberships if Phase 29 needed it"
  - "Script bypasses ARQ scheduling entirely — `unique=True` cron guard is irrelevant for direct coroutine invocation (D-29-03)"

patterns-established:
  - "Verification-only operator script pattern: lives under apps/backend/scripts/, invoked via `cd apps/backend && uv run python -m scripts.<name>`, NEVER run by CI or compose stack — single-purpose, one human-readable success line, stderr+exit-1 on guard failure"
  - "Hybrid pattern documentation: when a script's CLI shape comes from one analog (export_openapi.py) and runtime semantics from another (WorkerSettings.on_startup), the module docstring explicitly cites both and the action body calls the staticmethod rather than duplicating its body inline"

requirements-completed: [DEBT-04]

# Metrics
duration: ~7min
completed: 2026-05-14
---

# Phase 29 Plan 02: run_expiring_cron_once.py Summary

**In-process one-shot operator runner for the 06:15 MSK `send_expiring_notifications` cron, gated by DATABASE_URL-host (TM-29-02) and TELEGRAM_SANDBOX_CHAT_ID-presence (TM-29-03) checks, reusing `WorkerSettings.on_startup` to build ctx (no inline db_lifespan_manager).**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-14T07:12:00Z (approx, plan execution start)
- **Completed:** 2026-05-14T07:16:26Z
- **Tasks:** 1 (auto)
- **Files modified:** 1 (created)

## Accomplishments

- Authored `apps/backend/scripts/run_expiring_cron_once.py` (90 lines) — single-purpose operator runner that fires `send_expiring_notifications(ctx)` once against the live stack and prints `Fired send_expiring_notifications once: count=<N>` on success.
- Reused `WorkerSettings.on_startup(ctx)` / `on_shutdown(ctx)` staticmethods rather than re-implementing `db_lifespan_manager()` inline — preserves MH-29-05 invariant that one-shot runners do not fork worker lifecycle logic.
- Layered defence-in-depth env-var guards: TM-29-02 (DATABASE_URL must contain `localhost` or `postgres:5432`) and TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID env must be set), both fail-closed with stderr error + return 1 before any side effect.
- Module docstring explicitly documents that the TM-29-03 env-set check is necessary-but-not-sufficient and points downstream verifiers (plan 29-04 step 6, plan 29-03 fixture seeding) at the load-bearing operator-managed `UPDATE clients SET telegram_user_id = $TELEGRAM_SANDBOX_CHAT_ID` step.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author `apps/backend/scripts/run_expiring_cron_once.py`** — `9f22697` (feat)

_Note: no plan-metadata commit produced inside the worktree — the orchestrator owns the final STATE.md / ROADMAP.md commits after all wave agents complete._

## Files Created/Modified

- `apps/backend/scripts/run_expiring_cron_once.py` (created) — In-process one-shot runner for the 06:15 MSK expiring-soon cron. Mirrors `export_openapi.py` CLI shape; calls `WorkerSettings.on_startup` → `send_expiring_notifications(ctx)` → `WorkerSettings.on_shutdown` in a try/finally. Hard-gated by `DATABASE_URL` host check (TM-29-02) and `TELEGRAM_SANDBOX_CHAT_ID` env-presence (TM-29-03). NEVER invoked by CI or the compose stack.

## Decisions Made

- **Script form chosen over inline `python -c` heredoc:** D-29-03 allowed either approach; the script form avoids duplicating `WorkerSettings.on_startup`-equivalent logic inside a fragile heredoc and gives the runner a copy-pasteable invocation line for plans 29-03 / 29-04.
- **No CLI arg parsing / no `--job` switch:** the runner does exactly one job (fire expiring-soon DMs). Adding `--job expire_memberships` was rejected as scope creep — Phase 29's cross-phase smoke (plan 29-04) only needs the expiring-soon firing; `expire_memberships` is triggered indirectly via DB UPDATE + the scheduled cron, not via this runner.
- **TM-29-03 mitigation scoped to env-presence + docstring narrative:** the runner cannot inspect each candidate client's `telegram_user_id` without re-implementing the cron's SELECT, so the load-bearing data-layer redirect is explicitly delegated to the operator and documented in the docstring. This matches the threat model: env-presence is defence-in-depth; the operator's manual UPDATE is the load-bearing mitigation.

## Deviations from Plan

None — plan executed exactly as written. The plan's grep acceptance criteria caught a near-miss: the initial implementation included the literal string `db_lifespan_manager` inside an indented comment, which the `grep -v '^#'` acceptance check (which only strips column-0 comments) treated as a live reference. Rephrased the comment to "DO NOT re-implement the DB lifespan inline (MH-29-05): call the staticmethod, never the helper." — preserves the documented intent without tripping the grep gate. This was a single-line wording fix inside the same task commit, not a Rule 1/2/3 deviation.

## Issues Encountered

- AST entrypoint check used `python` directly which is not on PATH in the worktree shell; switched to `uv run python -c "..."` to match how every other operator script is invoked. No code change required — `AST OK` confirmed once invoked through `uv run`.

## Verification Evidence

All automated gates green:

```
$ cd apps/backend && uv run ruff check scripts/run_expiring_cron_once.py
All checks passed!

$ cd apps/backend && uv run mypy --strict scripts/run_expiring_cron_once.py
Success: no issues found in 1 source file

$ cd apps/backend && uv run lint-imports --config .importlinter
Contracts: 3 kept, 0 broken.
  - core must not import modules KEPT
  - modules cannot import each other KEPT
  - integrations must not import modules KEPT

$ cd apps/backend && uv run python -c "import ast; t=ast.parse(open('scripts/run_expiring_cron_once.py').read()); names={n.name for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}; assert '_run' in names and 'main' in names"
AST OK
```

All grep acceptance criteria (AC1–AC8) pass:

| # | Criterion | Result |
|---|-----------|--------|
| 1 | `WorkerSettings.on_startup` present | OK |
| 2 | `WorkerSettings.on_shutdown` present | OK |
| 3 | `await send_expiring_notifications(ctx)` present | OK |
| 4 | `TELEGRAM_SANDBOX_CHAT_ID` guard present (TM-29-03) | OK |
| 5 | `localhost` guard present (TM-29-02) | OK |
| 6 | `Fired send_expiring_notifications once: count=` success line present | OK |
| 7 | `db_lifespan_manager` literal NOT present in non-comment lines (count=0) | OK |
| 8 | `_run` + `main` entrypoints exist (AST check) | OK |

## User Setup Required

None — no external service configuration required for plan 29-02 itself. The runner is invoked by the operator during plans 29-03 / 29-04, where they will additionally set `TELEGRAM_SANDBOX_CHAT_ID` and run the load-bearing `UPDATE clients SET telegram_user_id = $TELEGRAM_SANDBOX_CHAT_ID` SQL per D-29-08.

## Next Phase Readiness

- Plan 29-03 (DEBT-04 scenario execution) can now invoke the runner via `cd apps/backend && uv run python -m scripts.run_expiring_cron_once` once fixtures are seeded and TELEGRAM_SANDBOX_CHAT_ID + redirect-UPDATE are in place.
- Plan 29-04 (cross-phase smoke) step 7 uses the same invocation between `UPDATE memberships SET end_date = today + N` pokes for the 7d/3d/1d firings.
- MH-29-08 preserved: no file under `apps/backend/app/**` or `apps/admin-web/src/**` modified. Only `apps/backend/scripts/run_expiring_cron_once.py` created.

## Self-Check

Verifying claims:

- `apps/backend/scripts/run_expiring_cron_once.py` exists: FOUND
- Commit `9f22697` exists: FOUND (`git log --oneline --all | grep 9f22697`)

## Self-Check: PASSED

---
*Phase: 29-milestone-verification*
*Completed: 2026-05-14*
