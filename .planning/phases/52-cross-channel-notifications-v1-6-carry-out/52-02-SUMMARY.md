---
phase: 52-cross-channel-notifications-v1-6-carry-out
plan: "02"
subsystem: backend/notifications
tags: [email-templates, audit, config, notifications, owner-alert]
dependency_graph:
  requires: []
  provides:
    - LOCKED_EMAIL_TEMPLATES extended to 19 entries
    - email template identifier constants for online payment notifications
    - owner-alert recipient settings (owner_alert_telegram_chat_id, owner_alert_email)
  affects:
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/config.py
tech_stack:
  added: []
  patterns:
    - OWNER-COPY-LOCK Final[str] identifier constants
    - LOCKED_EMAIL_TEMPLATES frozenset literal extension
    - Pydantic BaseSettings optional int|None / str|None fields
key_files:
  created: []
  modified:
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/config.py
decisions:
  - "Owner-alert settings default to None (log-only when unset); no validation rejects None per D-52-09"
  - "Email template constants in email_templates.py are documentation-only; tasks.py must use string literals at callsite per AST gate constraint"
  - "LOCKED_EMAIL_TEMPLATES extended with 4 string literals (not variables) to keep AST gate sound"
metrics:
  duration: "8 minutes"
  completed: "2026-05-23"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 52 Plan 02: Email Template Identifiers + Owner-Alert Config Summary

**One-liner:** 4 `Final[str]` email identifier constants + `LOCKED_EMAIL_TEMPLATES` 15→19 + two None-defaulting Pydantic owner-alert settings for Phase 52 NOT-02/NOT-04.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Email identifiers + LOCKED_EMAIL_TEMPLATES 15→19 | 2322fa5 | email_templates.py, audit.py |
| 2 | Owner-alert recipient settings (default None) | dc553d3 | config.py |

## What Was Built

**Task 1** — Extended `app/modules/online_payments/email_templates.py` from the Phase 49 empty placeholder to define 4 `Final[str]` email template identifier constants with `OWNER-COPY-LOCK` lineage annotations and an AST gate constraint docstring explaining that dispatcher callsites in `tasks.py` must use string literals, not variable references.

Extended `app/core/audit.py`'s `LOCKED_EMAIL_TEMPLATES` frozenset from 15 to 19 entries by adding the 4 new string literals under a `# Phase 52 — online payment notifications (NOT-02 / D-52-07)` comment. All 4 identifiers are string literals (not computed/wildcard) so the AST gate remains sound.

**Task 2** — Added two optional Pydantic settings to `class Settings(BaseSettings)` in `app/core/config.py` near the Telegram block:
- `owner_alert_telegram_chat_id: int | None = None`
- `owner_alert_email: str | None = None`

Documented as Phase 52 NOT-04 owner operator-alert recipients consumed by the `payment_canceled` + `fiscal_failed` notification branches; documented that when unset the dispatch task logs ERROR only (best-effort — never raises, never blocks). Env-var documentation deferred to Phase 53 runbook (VER-01).

## Verification Results

```
ok 19  # len(LOCKED_EMAIL_TEMPLATES)
ok     # both owner_alert_* settings are None by default
Success: no issues found in 2 source files  # mypy --strict email_templates.py + audit.py
Success: no issues found in 1 source file   # mypy --strict config.py
All checks passed!  # ruff check all 3 files
```

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed E501 line-too-long in email_templates.py**
- **Found during:** Task 1 verification (ruff check)
- **Issue:** Two constants with trailing `# OWNER-COPY-LOCK  # owner-alert` comments exceeded 100-char limit
- **Fix:** Moved `# owner-alert` annotations to dedicated comment lines above each constant
- **Files modified:** `apps/backend/app/modules/online_payments/email_templates.py`
- **Commit:** 2322fa5 (included in Task 1 commit)

## Known Stubs

None — this plan defines identifier constants and configuration settings; no data flows to UI rendering.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. The owner-alert settings are consumed by Plan 04's dispatch task and route only to owner channels (T-52-06 mitigation as specified in the threat model).

## Self-Check: PASSED

- `apps/backend/app/modules/online_payments/email_templates.py` — FOUND (modified)
- `apps/backend/app/core/audit.py` — FOUND (modified)
- `apps/backend/app/core/config.py` — FOUND (modified)
- Commit 2322fa5 — Task 1 (email identifiers + frozenset)
- Commit dc553d3 — Task 2 (owner-alert settings)
