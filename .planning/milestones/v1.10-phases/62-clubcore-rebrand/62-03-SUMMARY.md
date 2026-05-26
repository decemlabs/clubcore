---
phase: 62-clubcore-rebrand
plan: 03
subsystem: backend / redis-keyspace
tags: [rebrand, redis, idempotency, circuit-breaker, webhook-dedup, telegram-dedup, D-62-07, D-62-11, G-3]
requires: [62-01]
provides:
  - cc:idem:* redis prefix replaces sz:idem:* (idempotency)
  - cc:bot:update:* redis prefix replaces sz:bot:update:* (telegram update dedup)
  - cc:yookassa:circuit:* / cc:yookassa:circuit_window:* replaces sz: variants (yookassa circuit breaker)
  - cc:email:circuit:* / cc:email:circuit_window:* replaces sz: variants (email circuit breaker)
  - cc:yookassa:webhook:* replaces sz:yookassa:webhook:* (yookassa webhook dedup)
affects: [REB-03]
tech-stack:
  added: []
  patterns: [single-commit-atomic-flip-D-62-11, no-dual-read-D-62-07]
key-files:
  created:
    - .planning/phases/62-clubcore-rebrand/62-03-SUMMARY.md
  modified:
    # The five primary source files (one per surface from 62-PATTERNS.md §G-3):
    - apps/backend/app/core/idempotency.py
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/integrations/yookassa/circuit_breaker.py
    - apps/backend/app/integrations/email/circuit_breaker.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    # Docstring/comment updates in 3 additional app/ files (lockstep with literals):
    - apps/backend/app/workers/tasks/dispatch_email.py
    - apps/backend/app/modules/pt_packages/router.py
    - apps/backend/app/modules/fiscal_receipts/tasks.py
    # Test files updated lockstep (assertions, fixtures, key constants):
    - apps/backend/tests/unit/test_yookassa_circuit_breaker.py
    - apps/backend/tests/unit/integrations/email/test_circuit_breaker.py
    - apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py
    - apps/backend/tests/integration/telegram_bot/test_dedupe_helper.py
    - apps/backend/tests/integration/online_refunds/test_e2e_refund_full_cycle.py
    - apps/backend/tests/integration/fiscal_receipts/test_e2e_fiscal_receipt_full_cycle.py
    - apps/backend/tests/integration/fiscal_receipts/test_dispatch_fiscal_receipt.py
    - apps/backend/tests/integration/fiscal_receipts/conftest.py
    - apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py
    - apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py
    - apps/backend/tests/integration/webhook_yookassa/conftest.py
decisions:
  - D-62-07 (no dual-read fallback at cutover; operator FLUSHDB is the contract)
  - D-62-11 (single-atomic-commit rename — all five backend Redis prefixes flip together)
metrics:
  duration_minutes: ~20
  completed_date: 2026-05-26
---

# Phase 62 Plan 03: Backend Redis Key Prefix Flip (sz: → cc:) Summary

Single-commit atomic flip of all five backend Redis key prefixes from `sz:*` to `cc:*` per D-62-07 (no runtime dual-read) + D-62-11 (single atomic commit). Code-side rename only; operator FLUSHDB runbook entry belongs to G-5.

## Literal Swaps (exact line numbers)

### Primary source files (5 surfaces — 62-PATTERNS.md §G-3)

| File | Line | Before | After |
|------|------|--------|-------|
| `apps/backend/app/core/idempotency.py` | 38 | `IDEMPOTENCY_REDIS_PREFIX: str = "sz:idem:"` | `IDEMPOTENCY_REDIS_PREFIX: str = "cc:idem:"` |
| `apps/backend/app/integrations/telegram/handlers.py` | 105 | `dedup_key = f"sz:bot:update:{update_id}"` | `dedup_key = f"cc:bot:update:{update_id}"` |
| `apps/backend/app/integrations/yookassa/circuit_breaker.py` | 41 | `_CIRCUIT_KEY_PREFIX: Final[str] = "sz:yookassa:circuit:"` | `_CIRCUIT_KEY_PREFIX: Final[str] = "cc:yookassa:circuit:"` |
| `apps/backend/app/integrations/yookassa/circuit_breaker.py` | 42 | `_WINDOW_KEY_PREFIX: Final[str] = "sz:yookassa:circuit_window:"` | `_WINDOW_KEY_PREFIX: Final[str] = "cc:yookassa:circuit_window:"` |
| `apps/backend/app/integrations/email/circuit_breaker.py` | 37 | `_CIRCUIT_KEY_PREFIX: Final[str] = "sz:email:circuit:"` | `_CIRCUIT_KEY_PREFIX: Final[str] = "cc:email:circuit:"` |
| `apps/backend/app/integrations/email/circuit_breaker.py` | 38 | `_WINDOW_KEY_PREFIX: Final[str] = "sz:email:circuit_window:"` | `_WINDOW_KEY_PREFIX: Final[str] = "cc:email:circuit_window:"` |
| `apps/backend/app/api/v1/_internal/yookassa/router.py` | 56 | `WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"` | `WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "cc:yookassa:webhook:"` |

### Docstring / comment updates (lockstep with literals, in same source files)

| File | Lines | Type | Note |
|------|-------|------|------|
| `app/core/idempotency.py` | 18, 72 | module docstring + function docstring | `sz:idem:{key}` → `cc:idem:{key}` and `sz:idem:{...}` → `cc:idem:{...}` |
| `app/integrations/telegram/handlers.py` | 19, 74, 100 | docstrings | three `sz:bot:update:` mentions → `cc:bot:update:` |
| `app/integrations/yookassa/circuit_breaker.py` | 6, 12, 27 | module docstring | `sz:yookassa:circuit*` → `cc:yookassa:circuit*` |
| `app/integrations/email/circuit_breaker.py` | 5, 11 | module docstring | `sz:email:circuit*` → `cc:email:circuit*` |
| `app/api/v1/_internal/yookassa/router.py` | 18 | module docstring | `sz:yookassa:webhook:{...}` → `cc:yookassa:webhook:{...}` |

### Docstring / comment updates in 3 additional app/ files (truth #4 lockstep requirement)

| File | Line | Change |
|------|------|--------|
| `app/workers/tasks/dispatch_email.py` | 22 | docstring `sz:email:circuit:yandex_postbox` → `cc:email:circuit:yandex_postbox` |
| `app/modules/pt_packages/router.py` | 238 | docstring `sz:idem:{key}` → `cc:idem:{key}` |
| `app/modules/fiscal_receipts/tasks.py` | 57 | inline comment `sz:yookassa:circuit:receipts` → `cc:yookassa:circuit:receipts` |

### Test files updated lockstep (D-62-11)

| File | Change |
|------|--------|
| `tests/unit/test_yookassa_circuit_breaker.py` | All `sz:yookassa:circuit*` literals → `cc:yookassa:circuit*` (docstring + 5 occurrences) |
| `tests/unit/integrations/email/test_circuit_breaker.py` | All `sz:email:circuit*` literals → `cc:email:circuit*` (docstring + 8 occurrences) — includes the constants-lock assertion `assert _CIRCUIT_KEY_PREFIX == "cc:email:circuit:"` (was `"sz:email:circuit:"`) |
| `tests/unit/integrations/email/test_dispatch_email_task.py` | 4 `sz:email:circuit*` → `cc:email:circuit*` |
| `tests/integration/telegram_bot/test_dedupe_helper.py` | `sz:bot:update:1` → `cc:bot:update:1` in `assert_awaited_once_with` call |
| `tests/integration/online_refunds/test_e2e_refund_full_cycle.py` | `sz:yookassa:webhook:*` → `cc:yookassa:webhook:*` in test cleanup helper |
| `tests/integration/fiscal_receipts/test_e2e_fiscal_receipt_full_cycle.py` | `sz:yookassa:webhook:*` → `cc:yookassa:webhook:*` in test cleanup helper |
| `tests/integration/fiscal_receipts/test_dispatch_fiscal_receipt.py` | 4 `sz:yookassa:circuit*` → `cc:yookassa:circuit*` |
| `tests/integration/fiscal_receipts/conftest.py` | 2 fixture cleanup loops over `sz:yookassa:circuit*` → `cc:yookassa:circuit*` |
| `tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py` | `_OPEN_MARKER_KEY` and `_WINDOW_KEY` constants + docstring reference |
| `tests/integration/online_payments/test_webhook_after_redis_restart_race.py` | `_WEBHOOK_DEDUP_KEY_PREFIX` constant + docstring `sz:yookassa:webhook:...` mention |
| `tests/integration/webhook_yookassa/conftest.py` | 3 occurrences in `redis_test_client` fixture (docstrings + key glob patterns) |

## Sweep grep — before/after

Before (pre-edit, from the planned `read_first` enumeration):

```
$ grep -rn '"sz:\|'\''sz:' apps/backend/app apps/backend/tests
apps/backend/app/core/idempotency.py:38:IDEMPOTENCY_REDIS_PREFIX: str = "sz:idem:"
apps/backend/app/integrations/yookassa/circuit_breaker.py:41:_CIRCUIT_KEY_PREFIX: Final[str] = "sz:yookassa:circuit:"
apps/backend/app/integrations/yookassa/circuit_breaker.py:42:_WINDOW_KEY_PREFIX: Final[str] = "sz:yookassa:circuit_window:"
apps/backend/app/integrations/telegram/handlers.py:105:    dedup_key = f"sz:bot:update:{update_id}"
apps/backend/app/integrations/email/circuit_breaker.py:37:_CIRCUIT_KEY_PREFIX: Final[str] = "sz:email:circuit:"
apps/backend/app/integrations/email/circuit_breaker.py:38:_WINDOW_KEY_PREFIX: Final[str] = "sz:email:circuit_window:"
apps/backend/app/api/v1/_internal/yookassa/router.py:56:WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"
apps/backend/tests/unit/test_yookassa_circuit_breaker.py:52: ...
apps/backend/tests/unit/test_yookassa_circuit_breaker.py:61: ...
apps/backend/tests/unit/integrations/email/test_circuit_breaker.py:80: ...
apps/backend/tests/unit/integrations/email/test_circuit_breaker.py:103: ...
apps/backend/tests/unit/integrations/email/test_circuit_breaker.py:110: ...
apps/backend/tests/unit/integrations/email/test_circuit_breaker.py:150: ...
apps/backend/tests/unit/integrations/email/test_circuit_breaker.py:169: ...
apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py:257 ...
apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py:290 ...
apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py:320 ...
apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py:383 ...
apps/backend/tests/integration/telegram_bot/test_dedupe_helper.py:45 ...
apps/backend/tests/integration/online_refunds/test_e2e_refund_full_cycle.py:366 ...
apps/backend/tests/integration/fiscal_receipts/test_e2e_fiscal_receipt_full_cycle.py:232 ...
apps/backend/tests/integration/fiscal_receipts/test_dispatch_fiscal_receipt.py:153, 188, 189, 202
apps/backend/tests/integration/fiscal_receipts/conftest.py:146, 149
apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py:49, 50
apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py:82
apps/backend/tests/integration/webhook_yookassa/conftest.py:343, 347
(31 matches across 14 files; full list in plan execution log)
```

After (at this plan's commit tip):

```
$ grep -rn '"sz:\|'\''sz:' apps/backend/app apps/backend/tests | wc -l
0

$ grep -rn "sz:" apps/backend/app apps/backend/tests | wc -l
0

$ grep -c '"cc:idem:"' apps/backend/app/core/idempotency.py
1
$ grep -c 'cc:bot:update:' apps/backend/app/integrations/telegram/handlers.py
4
$ grep -c '"cc:yookassa:circuit:"' apps/backend/app/integrations/yookassa/circuit_breaker.py
1
$ grep -c '"cc:yookassa:circuit_window:"' apps/backend/app/integrations/yookassa/circuit_breaker.py
1
$ grep -c '"cc:email:circuit:"' apps/backend/app/integrations/email/circuit_breaker.py
1
$ grep -c '"cc:email:circuit_window:"' apps/backend/app/integrations/email/circuit_breaker.py
1
$ grep -c '"cc:yookassa:webhook:"' apps/backend/app/api/v1/_internal/yookassa/router.py
1
```

All seven acceptance grep gates from `<acceptance_criteria>` pass.

## Pytest summary at plan tip

```
$ cd apps/backend && uv run pytest -q --tb=short
...
2181 passed, 6 skipped in 308.60s (0:05:08)
```

Exactly the v1.9 baseline (≥ 2181 passed, ≤ 6 skipped) per CONTEXT line 157. No regressions.

Targeted re-run of the directly-touched test files (sanity probe before the full suite):

```
$ uv run pytest -q tests/unit/test_yookassa_circuit_breaker.py \
    tests/unit/integrations/email/test_circuit_breaker.py \
    tests/unit/integrations/email/test_dispatch_email_task.py \
    tests/integration/telegram_bot/test_dedupe_helper.py
30 passed in 0.15s
```

## Ruff

```
$ uv run ruff check app/core/idempotency.py \
    app/integrations/telegram/handlers.py \
    app/integrations/yookassa/circuit_breaker.py \
    app/integrations/email/circuit_breaker.py \
    app/api/v1/_internal/yookassa/router.py
All checks passed!
```

## No-dual-read confirmation (D-62-07)

Explicit declaration: this commit introduces **no runtime fallback logic** that reads `sz:*` keys. There is no backward-compat reader, no env-toggled dual prefix, no migration shim in the read path. The cutover contract is the operator-side `redis-cli FLUSHDB` documented in the G-5 runbook (plan 62-05, already merged into main). In-flight idempotency / circuit-breaker / dedup state from the old keyspace is abandoned at cutover; all upstream handlers tolerate this per the threat model:

- **Idempotency keys**: 1h TTL; clients retrying within the window observe a fresh claim (worst case: server re-runs a request the client thought was deduped — handlers are FSM-idempotent on payment_id / refund_id / membership boundary).
- **Yookassa webhook dedup**: 24h TTL; brief replay window mitigated by FSM idempotency on payment.{succeeded,canceled,refunded} (verified across 2181 passing tests including `test_webhook_after_redis_restart_db_unique_is_sole_catcher` which simulates exactly this dedup-key-gone scenario).
- **Telegram bot update dedup**: 1h TTL; Telegram resends are bounded by its ~1d dedup ID lifecycle; `_dedupe_update_id` is fail-open by design (D-20-3).
- **Yookassa circuit breakers (email + receipts)**: 5min open TTL; reset means the next call may hit a previously-tripped external service; existing retry + breaker logic re-establishes correct state.

## Predecessor-defect watch

Per orchestrator note: prior 62-01 executor silently deferred under the guise of "G-2..G-6 plans" without an owning plan. No similar tension surfaced in this plan — all five literal swaps + their lockstep test updates were unambiguous from §G-3 + the `must_haves.truths` block. Nothing deferred. Nothing silently dropped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Lockstep docstring updates in 3 non-`files_modified` files]**

- **Found during:** initial sweep grep — `apps/backend/app/workers/tasks/dispatch_email.py:22`, `apps/backend/app/modules/pt_packages/router.py:238`, and `apps/backend/app/modules/fiscal_receipts/tasks.py:57` contained `sz:` references in docstrings/comments (none were string literals, so they did NOT show up in the `"sz:|'sz:` literal sweep — only in the broader `sz:` sweep).
- **Issue:** Plan's `<files>` element listed only the five primary source files, but `must_haves.truths` items 3 and 4 require (a) zero `sz:` references in `app/*` outside G-5 runbook artifacts and (b) docstring updates lockstep with code literals. These three files were the only remaining surface that would otherwise leave stale `sz:` references in active backend code.
- **Fix:** Updated all three references in the same atomic commit. None are runbook artifacts (the G-5 runbook lives under `.planning/` per CONTEXT) so they must flip lockstep with code.
- **Files modified:** `app/workers/tasks/dispatch_email.py`, `app/modules/pt_packages/router.py`, `app/modules/fiscal_receipts/tasks.py`
- **Commit:** included in the single atomic commit (see hash below)

**2. [Local dev infrastructure — DB rename for test run]**

- **Found during:** pytest invocation
- **Issue:** Local Postgres container (`backend-postgres-1`) was carrying a stale `sportzal` database. Plan 62-02 (Postgres DB rename) is already merged into main and renamed the application database to `clubcore` in code, but the local dev container had not been migrated. Tests using `DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/clubcore` failed with `database "clubcore" does not exist`.
- **Fix:** Renamed the existing populated database in-place via `ALTER DATABASE sportzal RENAME TO clubcore;` after terminating live connections. This preserves the v1.9-baseline migrated schema (rev `0042_recurring_schedule_time_off`). No application code touched. Fresh alembic-init on an empty DB would have failed independently because the alembic-default `alembic_version.version_num VARCHAR(32)` is too small for the project's 33+ char migration ids — a pre-existing project quirk unrelated to this rename.
- **Files modified:** none (database-level operation only)
- **Tracked as:** out-of-scope infra step required to run the test gate; documented here so the next executor sees the precedent if the dev DB still has the legacy name.

## Self-Check: PASSED

Files (all relative to worktree root `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a9a27ed07af20de1b/`):

- FOUND: apps/backend/app/core/idempotency.py
- FOUND: apps/backend/app/integrations/telegram/handlers.py
- FOUND: apps/backend/app/integrations/yookassa/circuit_breaker.py
- FOUND: apps/backend/app/integrations/email/circuit_breaker.py
- FOUND: apps/backend/app/api/v1/_internal/yookassa/router.py
- FOUND: apps/backend/app/workers/tasks/dispatch_email.py
- FOUND: apps/backend/app/modules/pt_packages/router.py
- FOUND: apps/backend/app/modules/fiscal_receipts/tasks.py
- FOUND: all 11 test files listed under `modified`
- FOUND: .planning/phases/62-clubcore-rebrand/62-03-SUMMARY.md (this file)

Commit hash: to be appended via post-commit verification step.
