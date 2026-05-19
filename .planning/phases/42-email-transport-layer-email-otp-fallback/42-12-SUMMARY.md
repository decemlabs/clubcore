---
phase: 42-email-transport-layer-email-otp-fallback
plan: 12
subsystem: email-transport / audit
tags: [bug-fix, cr-01, audit, dispatch-email, integration-test, pydantic]
dependency_graph:
  requires:
    - 42-08 (dispatch_email task)
    - 42-09 (worker startup + ctx wiring)
    - 42-11 (EmailSentPayload / EmailSendFailedPayload schemas)
  provides:
    - Flattened audit.emit call sites in dispatch_email.py (both ok and fail branches)
    - Integration test exercising REAL audit.emit + audit_log DB query
    - Unit test regression guards (assert "payload" not in kwargs)
  affects:
    - audit_log table (email_sent / email_send_failed rows now land correctly)
    - EmailSendLog INSERT (no longer rolls back due to audit.emit raising)
tech_stack:
  added: []
  patterns:
    - flattened-audit-emit-kwargs (mirrors app/api/v1/_internal/email/router.py:181-197)
    - savepoint-sessionmaker-for-worker-tests (mirrors tests/integration/workers/conftest.py)
key_files:
  modified:
    - apps/backend/app/workers/tasks/dispatch_email.py
    - apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py
  created:
    - apps/backend/tests/integration/email/__init__.py
    - apps/backend/tests/integration/email/test_dispatch_email_audit_integration.py
decisions:
  - "AuditLog column is action (not event_name) — plan spec said event_name but actual ORM uses action"
  - "Integration test uses _SavepointSessionmaker pattern from workers/conftest.py to share the SAVEPOINT-wrapped db_session with the worker call"
  - "No pytestmark module-level marker needed — tests inherit asyncio mode from project pytest.ini"
  - "grep 'monkeypatch.setattr.*audit.emit' returns 1 due to a comment in the test file; actual code has 0 monkey-patches"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-19"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
  files_created: 2
requirements:
  - EMAIL-03
---

# Phase 42 Plan 12: CR-01 Fix — Flatten audit.emit kwargs in dispatch_email.py Summary

**One-liner:** Flattened `payload=<Model>` to individual kwargs in dispatch_email.py success and failure branches, fixing the Pydantic ValidationError that crashed every production ARQ job and prevented any `email_sent` audit row from ever landing.

## What Was Done

**Root cause (CR-01):** `dispatch_email.py:160-172/175-188` called `audit.emit(... payload=EmailSentPayload(...))`. Since `audit.emit`'s signature is `**payload: Any`, the collected kwargs dict became `{"payload": <Model>}`. Downstream `EmailSentPayload.model_validate({"payload": <Model>})` raised `ValidationError` (`extra='forbid'` + 4 missing required fields). Every production `dispatch_email` job crashed at the audit step; the `EmailSendLog` INSERT rolled back because `session.commit()` was never reached.

**Why tests didn't catch it:** The unit tests in `test_dispatch_email_task.py` monkey-patched `audit.emit` with a `fake_emit` that recorded kwargs without ever running the real Pydantic validator. Tests asserted `kwargs["payload"].field` — wrong layer, always passing.

### Task 1: Fix dispatch_email.py

- Removed `payload=EmailSentPayload(...)` kwarg from the ok branch
- Removed `payload=EmailSendFailedPayload(...)` kwarg from the fail branch
- Both branches now use flattened kwargs: `audit_correlation_id=str(envelope.audit_correlation_id)`, `template_id=envelope.template_id`, `to_email=envelope.to`, `provider_message_id=result.provider_message_id` / `reason=reason`, `provider_error_code=result.error`
- `audit_correlation_id` is str-cast at the boundary (mirrors `router.py:192` convention for JSONB serialisability)
- Removed now-unused `EmailSentPayload` / `EmailSendFailedPayload` imports
- Commit: 688ae24

### Task 2: Rewrite unit tests

- Replaced all `payload = kwargs["payload"]; payload.field` assertions with direct `kwargs["field"]` lookups
- Added `assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"` to all 5 tests exercising audit emit
- Added `assert kwargs["audit_correlation_id"] == str(envelope.audit_correlation_id)` to success-path test
- Added `isinstance(kwargs["audit_correlation_id"], str)` guards to all fail-path tests
- Updated module docstring to document the `fake_emit` limitation and the new integration test
- Commit: d8e93ac

### Task 3: Add integration test

- Created `tests/integration/email/__init__.py` (empty, per project convention)
- Created `tests/integration/email/test_dispatch_email_audit_integration.py` with:
  - `test_dispatch_email_success_writes_email_sent_audit_row`: runs real `audit.emit`, queries `AuditLog.action == "email_sent"` from the DB, asserts 1 row with all 4 `EmailSentPayload` fields in JSONB
  - `test_dispatch_email_failure_writes_email_send_failed_audit_row`: same for fail path with `reason='provider_5xx'`, `provider_error_code='HTTP 503'`
- NO monkey-patch of `audit.emit` anywhere in the file (actual code: 0 monkey-patches)
- Uses `_SavepointSessionmaker` pattern from `tests/integration/workers/conftest.py` to share the SAVEPOINT-wrapped `db_session`
- Commit: dae2b7f

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c "payload=Email" dispatch_email.py` | 0 |
| `grep -c "audit_correlation_id=str(envelope.audit_correlation_id)" dispatch_email.py` | 2 |
| `grep -c '"payload" not in kwargs' test_dispatch_email_task.py` | 6 (≥5 required) |
| `uv run ruff check app/workers/tasks/dispatch_email.py` | PASS |
| `uv run mypy --strict app/workers/tasks/dispatch_email.py` | PASS |
| `uv run ruff check tests/integration/email/test_dispatch_email_audit_integration.py` | PASS |
| `uv run mypy --strict tests/integration/email/test_dispatch_email_audit_integration.py` | PASS |
| `pytest tests/unit/integrations/email/test_dispatch_email_task.py -x` | 10 passed |
| `pytest tests/integration/email/test_dispatch_email_audit_integration.py -x` | 2 passed |

## Deviations from Plan

### Auto-discovered

**1. [Rule 1 - Bug] AuditLog.action column — plan spec said event_name**
- **Found during:** Task 3 (writing integration test)
- **Issue:** The plan spec in `<action>` for Task 3 says `AuditLog.event_name` but the actual ORM model (`app/core/audit_models.py:49`) maps the event column as `action = mapped_column(Text, ...)`. The `audit.emit()` function stores the event name as `AuditLog(action=event, ...)`.
- **Fix:** Used `AuditLog.action` (correct column name) in the integration test's `select(AuditLog).where(AuditLog.action == "email_sent", ...)` query.
- **Files modified:** `tests/integration/email/test_dispatch_email_audit_integration.py`
- **Commit:** dae2b7f

**2. [Rule 1 - Bug] pytest_asyncio / _PROVIDER unused imports**
- **Found during:** Task 3 ruff check
- **Issue:** The plan template suggested importing `pytest_asyncio` and `_PROVIDER` but neither was used in the final test code (no `@pytest_asyncio.fixture` needed, and `_PROVIDER` not referenced in assertions).
- **Fix:** Removed unused imports; ran `ruff --fix` for import ordering.
- **Files modified:** `tests/integration/email/test_dispatch_email_audit_integration.py`
- **Commit:** dae2b7f

## Known Stubs

None — all data flows are fully wired. The integration test confirms real `email_sent` audit rows land in `audit_log` with correct JSONB payloads.

## Threat Flags

None — this plan only fixes an existing code path. No new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- `apps/backend/app/workers/tasks/dispatch_email.py` — FOUND (modified)
- `apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py` — FOUND (modified)
- `apps/backend/tests/integration/email/__init__.py` — FOUND (created)
- `apps/backend/tests/integration/email/test_dispatch_email_audit_integration.py` — FOUND (created)
- Task 1 commit 688ae24 — FOUND
- Task 2 commit d8e93ac — FOUND
- Task 3 commit dae2b7f — FOUND
