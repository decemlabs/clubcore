---
phase: 52-cross-channel-notifications-v1-6-carry-out
plan: "04"
subsystem: backend/notifications
tags: [arq, notifications, telegram, email, idempotency, ast-gate, owner-alert]
dependency_graph:
  requires:
    - 52-01 (payment_notifications table + claim_payment_notification + DM templates)
    - 52-02 (LOCKED_EMAIL_TEMPLATES 19 entries + owner-alert settings)
  provides:
    - dispatch_payment_notification ARQ task (online_payments/tasks.py)
    - task registered in WorkerSettings.functions
    - 4 positive-fixture AST tests for Phase 52 email identifiers
  affects:
    - apps/backend/app/modules/online_payments/tasks.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/test_locked_email_templates_ast.py
tech_stack:
  added: []
  patterns:
    - claim-before-send per-channel idempotency (at-most-once leaning, D-52-02)
    - polymorphic subject routing by kind (payment_canceled → online_payment_id, others → payment_id)
    - owner-alert channel routing via settings.owner_alert_* (D-52-09)
    - literal email template_id at dispatcher callsite (AST gate D-52-07)
    - raw Base.metadata.tables[] joins for cross-module client resolution (modules-independent contract)
    - fresh bot per invocation (D-39-10 aiohttp session leak prevention)
    - best-effort dual-channel fan-out (D-52-02 / D-45-08 — never re-raises)
    - positive-fixture AST test pattern (mirrors D-43-33 / D-44-36 discipline)
key_files:
  created:
    - apps/backend/app/modules/online_payments/tasks.py
  modified:
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/test_locked_email_templates_ast.py
decisions:
  - "D-52-10: polymorphic subject routing in claim step — payment_canceled passes online_payment_id=, all other kinds pass payment_id= (explicit if/else, not **kwargs unpack, so grep acceptance criterion holds)"
  - "Client resolution via Base.metadata.tables['memberships'/'pt_packages'/'clients'] raw SA Table joins — preserves modules-independent import-linter contract without cross-module ORM imports"
  - "failure_reason for fiscal_failed kind hardcoded to 'see fiscal_receipts table' — task receives only payment_id + kind, not failure_reason; owner is directed to the fiscal_receipts table to investigate"
  - "4 positive-fixture tests mirror locally-evaluated walker logic (not delegated to _iter_dispatcher_calls) so a production-walker refactor cannot silently weaken these gates"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-23"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 52 Plan 04: dispatch_payment_notification ARQ Task + AST Positive-Fixture Tests Summary

**One-liner:** `dispatch_payment_notification` ARQ task with per-channel claim-before-send idempotency, polymorphic subject routing by kind, owner-alert channel resolution, 4 literal email template_ids, and 4 AST positive-fixture tests pinning the callsite contract.

## Tasks Completed

| Task | Name | Commit | Key Output |
|------|------|--------|------------|
| 1 | dispatch_payment_notification + worker registration | 6fda202 | tasks.py (516 lines) + worker __init__.py registration |
| 2 | AST positive-fixture tests for 4 new identifiers | 81a2e1a | 4 test functions in test_locked_email_templates_ast.py; all 10 tests pass |

## What Was Built

### Task 1 — dispatch_payment_notification

`app/modules/online_payments/tasks.py` implements the fan-out ARQ task:

**Signature:** `async def dispatch_payment_notification(ctx: dict[str, Any], *, payment_id: str, kind: str) -> str`

**Channel loop (telegram, email):**
1. **Resolve recipient** — client kinds (`payment_succeeded`, `refund_succeeded`): resolve `(first_name, email, telegram_user_id)` via `_resolve_client_row()` which joins `payments → subject (membership|pt_package) → client` using `Base.metadata.tables[]` raw SA Table objects. Owner-alert kinds (`payment_canceled`, `fiscal_failed`): read from `settings.owner_alert_telegram_chat_id` / `settings.owner_alert_email`; if None → log ERROR + continue (never raise, D-52-09).
2. **Claim** — `payment_repo.claim_payment_notification()` with D-52-10 polymorphic routing: `payment_canceled` passes `online_payment_id=payment_uuid`; all other kinds pass `payment_id=payment_uuid`.
3. **Send** — inside `try/except Exception` that calls `_log.exception(...)` and never re-raises (D-52-02 / D-45-08).

**Email dispatch** — `_dispatch_email()` helper with 4 literal `template_id=` arguments (AST gate D-52-07).

**Registered** in `WorkerSettings.functions` after `dispatch_fiscal_receipt` with `# Phase 52 NOT-01..05` comment.

### Task 2 — AST Positive-Fixture Tests

4 test functions added to `tests/unit/test_locked_email_templates_ast.py`:
- `test_email_online_payment_succeeded_literal_at_tasks_callsite`
- `test_email_online_payment_refunded_literal_at_tasks_callsite`
- `test_email_online_payment_canceled_literal_at_tasks_callsite`
- `test_email_fiscal_receipt_failed_literal_at_tasks_callsite`

Each walks `online_payments/tasks.py` AST, collects all `template_id=` keyword args that are `ast.Constant(str)`, and asserts the specific literal is present. The existing `test_real_callsites_pass` global gate is unchanged and passes.

## Decisions Made

### Polymorphic subject routing (D-52-10)
Used explicit `if kind == "payment_canceled": ... else: ...` pattern with named keyword arguments (`online_payment_id=`, `payment_id=`) rather than `**claim_kwargs` dict unpack. This ensures the acceptance criteria `grep -c "online_payment_id="` returns >= 1 and makes the routing visible at the callsite.

### Client resolution via raw metadata tables
Cross-module imports (`Membership`, `PtPackage`, `Client` ORM classes) are forbidden by the modules-independent import-linter contract. Used `Base.metadata.tables['memberships']`, `Base.metadata.tables['pt_packages']`, `Base.metadata.tables['clients']` raw SA Table references (same pattern as `payments/repository.py:_memberships_table()`). This resolves `client.telegram_user_id` + `client.email` for the client DM channels.

### failure_reason stub for fiscal_failed
The ARQ task receives only `payment_id` and `kind`. The `failure_reason` field in the fiscal_failed DM template and email is hardcoded to `"see fiscal_receipts table"` — the operator is directed to look up the `fiscal_receipts` row. This is intentional (not a bug): the dispatch task is enqueued by the seam (Plan 05) which also does not have the failure_reason readily available. The owner can look up the `fiscal_receipts.status` + failure context via the ЮKassa dashboard or the `fiscal_receipts` table.

## Deviations from Plan

None — plan executed exactly as written. The `**claim_kwargs` pattern shown in PATTERNS.md was adapted to explicit keyword args to satisfy the acceptance criteria grep; the plan also explicitly showed explicit keyword args as an option.

## Known Stubs

**1. failure_reason in fiscal_failed owner alerts**
- **Files:** `apps/backend/app/modules/online_payments/tasks.py` (lines in `_dispatch_email` and the Telegram send block for `fiscal_failed`)
- **Stub value:** `failure_reason="see fiscal_receipts table"`
- **Reason:** The ARQ task receives only `(payment_id, kind)` — the failure reason is stored in `fiscal_receipts.failure_reason` and is not passed via ARQ kwargs. The owner alert is still actionable (includes `payment_id` to look up the row). A future task (Phase 53 or later) may extend the task signature to include `failure_reason` or fetch it from the DB; for now the stub is acceptable per the best-effort doctrine (D-52-09).

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced. The task is a worker function (not an HTTP handler). Owner-alert settings were pre-registered in Plan 02 (T-52-06/T-52-11 mitigations already documented there).

## Verification Results

```
10 passed in 0.18s   # uv run pytest tests/unit/test_locked_email_templates_ast.py -q
worker OK             # dispatch_payment_notification in WorkerSettings.functions
Success: no issues found in 1 source file  # mypy --strict tasks.py
All checks passed!    # ruff check tasks.py
```

## Self-Check

- [x] `apps/backend/app/modules/online_payments/tasks.py` — created (516 lines)
- [x] `apps/backend/app/workers/__init__.py` — dispatch_payment_notification registered
- [x] `apps/backend/tests/unit/test_locked_email_templates_ast.py` — 4 new test functions
- [x] Commit 6fda202 — Task 1 (ARQ task + worker registration)
- [x] Commit 81a2e1a — Task 2 (4 AST positive-fixture tests)
- [x] `grep -c "online_payment_id=" tasks.py` → 1 (D-52-10 routing)
- [x] `grep -cE 'template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED"|...' tasks.py` → 4
- [x] `grep -c "def test_email_online_payment|def test_email_fiscal_receipt_failed"` → 4
- [x] `uv run pytest tests/unit/test_locked_email_templates_ast.py -q` → 10 passed
- [x] `uv run mypy --strict app/modules/online_payments/tasks.py` → clean
- [x] `uv run ruff check app/modules/online_payments/tasks.py` → clean
- [x] `uv run python -c "import app.workers; assert ..."` → registered

## Self-Check: PASSED
