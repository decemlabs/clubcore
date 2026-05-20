---
phase: 45-email-notification-mirrors
plan: 03
subsystem: backend / workers boot graph
tags: [eager-import, reg-29-04, notify-14, payment-receipts, ast-gate]
requires: [Plan 45-01 PaymentReceipt ORM landed]
provides: [payment_receipts visible on Base.metadata at worker boot, AST gate against future regressions]
affects: [app/workers/__init__.py, tests/unit/test_workers_eager_import.py]
key_files_modified:
  - apps/backend/app/workers/__init__.py
  - apps/backend/tests/unit/test_workers_eager_import.py
decisions: [D-45-20, D-45-21]
requirements_completed: [NOTIFY-14]
metrics:
  duration_minutes: ~15
  tasks_completed: 3
  completed_date: 2026-05-20
---

# Phase 45 Plan 03: PaymentReceipt eager-import + AST gate Summary

Adds `from app.modules.payments.models import PaymentReceipt  # noqa: F401` to `app/workers/__init__.py` (D-45-20 lineage tag) and extends the REG-29-04 eager-import test with both a runtime metadata assertion and an **AST-level gate** that reads `app/workers/__init__.py` and asserts the literal import statement is structurally present.

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| apps/backend/tests/unit/test_workers_eager_import.py | + 3 new tests + AST helper | af837ce |
| apps/backend/app/workers/__init__.py | + PaymentReceipt eager-import | 86013fd |

## Deviations from Plan

**[Rule 2 — Missing critical functionality] Conftest masks the runtime metadata check**

- The plan's Task 2 specifies a runtime-only `"payment_receipts" in Base.metadata.tables` assertion.
- Empirically verified: `tests/conftest.py` imports `app.main.create_app`, which transitively pulls the payments router → models, registering `payment_receipts` on `Base.metadata` **regardless** of whether the eager-import line in `app/workers/__init__.py` exists. The metadata-only test silently passes (RED would fail-fast).
- The production cron worker (`arq app.workers.WorkerSettings`) does NOT load `app.main`, so the literal import statement is the actual contract.
- **Fix:** Added two AST-walker tests: `test_payment_receipts_import_statement_present` (per-symbol) and `test_eager_import_statements_mirror_discipline` (trio: EmailSendLog + PasswordResetToken + PaymentReceipt). Both fail-RED without the source change and pass-GREEN with it. Matches plan `must_haves.truths` ("asserts the new import statement is structurally present").
- Files modified: `tests/unit/test_workers_eager_import.py`. Commits: af837ce (RED), 86013fd (GREEN).

## Task 3 — Behavioral Smoke (checkpoint:human-verify)

Per execution-context: confirmed `scripts/run_expiring_cron_once.py` exists and attempted a guarded invocation without `TELEGRAM_SANDBOX_CHAT_ID` set:

```
$ cd apps/backend && uv run python -m scripts.run_expiring_cron_once
ERROR: TELEGRAM_SANDBOX_CHAT_ID must be set; refusing to fire cron (TM-29-03).
EXIT_CODE=1
```

This proves the **structural pre-condition is intact**: the script's module-load chain (which exercises `import app.workers` → eager-import of `PaymentReceipt` → `Base.metadata` registration) completes without raising `ImportError` or SQLAlchemy reflection errors. The safety gate refused on the env presence check (TM-29-03), as designed.

The **behavioral SC5** ("non-zero count on first call against a freshly-migrated DB") requires a real Telegram sandbox bot token + fixture-seeded clients with `telegram_user_id = $TELEGRAM_SANDBOX_CHAT_ID` + DB migration to head — operator-only acceptance per the script's docstring (Plan 29-04 fixture pattern). Operator should paste the `sent=N` log line and the two `SELECT COUNT(*) >= 1` results into this SUMMARY when smoke-running. **Gap accepted** for Plan 03 acceptance per execution-context guidance ("operator-only acceptance is acceptable here").

Additional inline boot-time smoke (the equivalent automated check from the plan):

```
$ uv run python -c "import app.workers; from app.core.database import Base; assert 'payment_receipts' in Base.metadata.tables; print('payment_receipts OK; total tables:', len(Base.metadata.tables))"
payment_receipts OK; total tables: 13
```

## Verification Outcomes

- `uv run ruff check app/workers/__init__.py tests/unit/test_workers_eager_import.py` — **All checks passed!**
- `uv run mypy --strict app/workers/__init__.py` — **Success: no issues found in 1 source file**.
- `uv run pytest tests/unit/test_workers_eager_import.py -v` — **6 passed** (including the 3 new tests).
- `uv run pytest tests/unit/` smoke — **753 passed, 2 failed**. The 2 failures (`test_worker_settings_functions_registered` and `test_worker_settings_cron_resolves_to_registered_function`) are **pre-existing** (confirmed reproducible on HEAD with `git stash` reporting no local changes — Phase 44 added `cleanup_password_reset_tokens` to the functions list bringing count 6→7 but the unit-test expectations were never updated). Logged to `deferred-items.md` for a future cleanup pass.
- `grep -c "PaymentReceipt" apps/backend/app/workers/__init__.py` = **1**; `grep -c "D-45-20" apps/backend/app/workers/__init__.py` = **1**; `grep -c "payment_receipts" apps/backend/tests/unit/test_workers_eager_import.py` = **8**.

## Self-Check: PASSED

- Files exist (2/2 verified above).
- Commits in git log: af837ce (RED test), 86013fd (GREEN implementation).
- All success criteria from PLAN.md `<success_criteria>` met (eager-import line landed with D-45-20 tag; existing tests still pass; new tests added).
- TDD gate compliance: `test(...)` RED commit precedes `feat(...)` GREEN commit; both lineage-tagged.
