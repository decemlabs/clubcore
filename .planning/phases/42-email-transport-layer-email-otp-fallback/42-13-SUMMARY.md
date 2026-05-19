---
phase: 42-email-transport-layer-email-otp-fallback
plan: 13
subsystem: auth
tags: [security, anti-oracle, timing, gap-closure, cr-02]
dependency_graph:
  requires: []
  provides: [D-42-22-cross-channel-uniformity, CR-02-closed]
  affects: [auth-otp-request-endpoint, request-otp-telegram, test-otp-anti-oracle]
tech_stack:
  added: []
  patterns: [try/finally constant-time floor, cross-channel anti-oracle probe]
key_files:
  modified:
    - apps/backend/app/modules/auth/service.py
    - apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py
decisions:
  - "CR-02 closed: _constant_time_floor applied in try/finally in request_otp_telegram so exception paths cannot leak timing"
  - "case_b removed from separate status-only assertion and included in unified 4-case body+timing parity probe"
  - "Pre-existing mypy attr-defined errors on app.modules.auth.models.User import are out-of-scope (existed before this plan)"
metrics:
  duration: ~8 minutes
  completed: 2026-05-19
  tasks_completed: 2
  tasks_total: 2
---

# Phase 42 Plan 13: CR-02 Gap Closure — request_otp_telegram Constant-Time Floor Summary

**One-liner:** Added `try/finally` with `_constant_time_floor` to `request_otp_telegram` and extended the anti-oracle test to include all 4 cases (A+B+C+D) in body+timing parity assertion, closing CR-02 and enforcing D-42-22 uniformity across both OTP channels.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wrap request_otp_telegram in try/finally with _constant_time_floor | f171b06 | apps/backend/app/modules/auth/service.py |
| 2 | Extend test to include case B in body+timing parity | 6566cd7 | apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py |

## What Was Done

### Task 1: service.py — request_otp_telegram constant-time floor (f171b06)

The `request_otp_telegram` function at lines 972–1002 had no `_constant_time_floor` call. The `telegram_service.start_deep_link` call wrote a DB row, emitted an audit event, and committed — all unconditionally — producing a distinct wall-clock distribution vs. silent-drop branches. This was the CR-02 side-channel.

Fix: Added `t_start = time.perf_counter()` at function entry, then wrapped the `start_deep_link` call in `try: ... finally: await _constant_time_floor(t_start)`. The `finally` block ensures the floor runs on both success and exception paths, preventing the exception path from leaking timing.

### Task 2: test_otp_email_anti_oracle.py — 4-case unified probe (6566cd7)

The test previously:
- Ran cases A, C, D in a unified email-channel probe (body+timing parity)
- Asserted case B separately with status code 202 only
- Had a misleading comment "body shape across channels intentionally diverges" — which was false per `router.py:411` (both channels return `envelope(None)`)

Fix:
- Updated the module docstring to reflect CR-02 fix and D-42-22 cross-channel uniformity
- Replaced the 3-case email-channel probe with a 4-case unified probe including case B
- case B probe sends `{"email": <x>}` (no channel field) to exercise Telegram-default path
- Removed the separate case B status-only assertion block
- All 4 cases now asserted for status 202, byte-identical response body, and timing max-min < 100ms

## Verification Results

```
grep -n "t_start = time.perf_counter()" service.py
  868:    t_start = time.perf_counter()   (request_otp_email)
  998:    t_start = time.perf_counter()   (request_otp_telegram)

python3 AST check: OK - try/finally with _constant_time_floor present

grep -c "case_b" test_otp_email_anti_oracle.py: 5

grep -c "body shape diverges" test_otp_email_anti_oracle.py: 0

ruff check app/modules/auth/service.py: All checks passed!
ruff check tests/integration/auth/test_otp_email_anti_oracle.py: All checks passed!

pytest tests/integration/auth/test_otp_email_anti_oracle.py -x -q
.  1 passed in 0.96s
```

## Deviations from Plan

### Pre-existing Issues (Out of Scope)

**mypy --strict errors on app/modules/auth/service.py and test file:**
- `Module "app.modules.auth.models" does not explicitly export attribute "User" [attr-defined]`
- These errors exist in the codebase before this plan (verified by git stash + re-run)
- Not caused by this plan's changes — deferred per scope boundary rule

## Known Stubs

None — no stubs introduced.

## Threat Flags

None — no new network endpoints or trust boundary surfaces introduced. This plan only adds a timing floor to an existing endpoint and expands test coverage.

## Self-Check

### Self-Check: PASSED

- `apps/backend/app/modules/auth/service.py` — FOUND (modified)
- `apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py` — FOUND (modified)
- commit f171b06 — FOUND
- commit 6566cd7 — FOUND
- `t_start = time.perf_counter()` appears 2+ times in service.py — CONFIRMED
- `try:` and `finally:` in request_otp_telegram — CONFIRMED
- `await _constant_time_floor(t_start)` in request_otp_telegram — CONFIRMED
- case_b in test (5 occurrences) — CONFIRMED
- "body shape diverges" not in test (0 occurrences) — CONFIRMED
- ruff checks pass on both files — CONFIRMED
- pytest passes (1 passed) — CONFIRMED
