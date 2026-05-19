---
phase: 44-invitation-password-reset-flow
plan: 01
subsystem: auth
type: execute
wave: 1
status: complete
requirements:
  - RESET-01
  - RESET-03
tags:
  - rate-limit
  - constants
  - anti-oracle
dependency_graph:
  requires: []
  provides:
    - PASSWORD_RESET_TOKEN_TTL (timedelta=1h)
    - check_reset_rate_ip
    - check_reset_rate_email_minute
    - check_reset_rate_email_hour
    - bump_reset_rate_ip
    - bump_reset_rate_email_minute
    - bump_reset_rate_email_hour
  affects:
    - apps/backend/app/modules/auth/password_reset_service.py (Wave 2 consumer)
tech_stack:
  added: []
  patterns:
    - "Redis fixed-window rate limiter (mirror of auth/rate_limit.py × 3 keys)"
    - "Final[timedelta] module constant (mirror of users/constants.py)"
key_files:
  created:
    - apps/backend/app/modules/auth/constants.py
    - apps/backend/app/modules/auth/reset_rate_limit.py
  modified: []
decisions:
  - "Kept structlog WARN emission OUT of reset_rate_limit.py — centralized in password_reset_service.py per D-44-11 separation of pure-Redis surface vs. observability."
  - "Imports limited to redis.asyncio, typing.Final, app.core.exceptions.RateLimited — zero ORM coupling, zero settings coupling (preserves leaf-module discipline)."
metrics:
  duration: ~4 min
  completed_date: 2026-05-19T20:38:56Z
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 44 Plan 01: Reset TTL Constant & 3-Key Rate Limiter Summary

Ships the two leaf modules that the rest of Phase 44 builds on: the 1-hour password-reset TTL constant (D-44-05, OWASP 2025 floor) and the 3-key fixed-window Redis rate limiter (D-44-10/11/12/13). Pure leaves with no downstream importers yet — Wave 2's `password_reset_service.py` picks them up.

## What Shipped

### Task 1 — `apps/backend/app/modules/auth/constants.py` (NEW, 19 lines)

Single module-level constant:

```python
PASSWORD_RESET_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)
```

Module docstring references D-44-05, RESET-03, and the OWASP 2025 1-hour floor. Mirrors `app/modules/users/constants.py:INVITATION_TOKEN_TTL` shape verbatim. Will be read at token-row INSERT time (`expires_at = now() + PASSWORD_RESET_TOKEN_TTL`) and in the atomic-consume SELECT predicate (`expires_at > now()`).

Commit: `6f77463`

### Task 2 — `apps/backend/app/modules/auth/reset_rate_limit.py` (NEW, 118 lines)

3-key fixed-window Redis topology with the thresholds locked by D-44-10:

| Limiter            | Threshold | Window      | Redis key                                  |
| ------------------ | --------- | ----------- | ------------------------------------------ |
| per-IP             | 5         | 900s (15m)  | `ratelimit:password_reset:ip:<ip>`         |
| per-email/minute   | 1         | 60s         | `ratelimit:password_reset:email_min:<e>`   |
| per-email/hour     | 5         | 3600s (1h)  | `ratelimit:password_reset:email_hour:<e>`  |

Six async helpers exported:

- `check_reset_rate_ip(redis, ip) -> None`
- `check_reset_rate_email_minute(redis, email_lower) -> None`
- `check_reset_rate_email_hour(redis, email_lower) -> None`
- `bump_reset_rate_ip(redis, ip) -> None`
- `bump_reset_rate_email_minute(redis, email_lower) -> None`
- `bump_reset_rate_email_hour(redis, email_lower) -> None`

`check_*` raises `RateLimited("rate_limited")` when `int(raw) >= LIMIT`. `bump_*` does `INCR + EXPIRE` in a single `redis.pipeline()`. All bumps run UNCONDITIONALLY on every request (unlike the login limiter which only bumps on auth failure) so floods against non-existent emails still trip the limit.

The CHECK helpers are invoked BEFORE the user lookup in `request_password_reset` (D-44-13 — anti-oracle parity for unknown-email rate-limited paths).

Commit: `73d3e2a`

## Key Decisions

### D-44-11 — structlog emission stays OUT of this module

The rate-limit module exports a pure Redis surface (3 imports total: `redis.asyncio.Redis`, `typing.Final`, `app.core.exceptions.RateLimited`). The `password_reset.rate_limited` structlog WARN line — required for ops abuse-triage visibility — will live in `password_reset_service.request_password_reset`, where the caller catches `RateLimited` and translates to the 202 envelope. This preserves:

- Anti-oracle public surface (no 429 leaks the limit state).
- Ops visibility via `grep password_reset.rate_limited` on the structlog stream.
- Module purity (no observability coupling at the leaf).

### Verbatim port of `auth/rate_limit.py` shape × 3 keys

Function signatures, key-helper precedent (`_key` → `_key_ip` / `_key_email_minute` / `_key_email_hour`), pipeline pattern, and `RateLimited("rate_limited")` raise all mirror the Phase 5 login limiter line-for-line. The only structural delta is the 3-key topology demanded by RESET-01.

### Imports kept minimal

Per acceptance: only `from redis.asyncio import Redis`, `from typing import Final`, `from app.core.exceptions import RateLimited`. No ORM, no settings, no structlog. import-linter remains green (modules cannot import each other; core must not import modules — both kept).

## Drift From Reference Shape

None of consequence. The login limiter uses bare `_LIMIT` / `_WINDOW_SECONDS` literals (no `Final[int]` annotation); this plan upgrades to `Final[int]` for the 6 threshold/window constants because the plan's acceptance regex explicitly enumerates the 3 LIMIT-name references and the typing.Final import is already paid for. mypy --strict passes both modules.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Plan inconsistency] Import count acceptance mismatch on constants.py**

- **Found during:** Task 1 verification
- **Issue:** Task 1 acceptance criterion states `grep -c "^from\|^import" ... returns exactly 2 (annotations future + Final/timedelta only)`, but the action block's example code contains 3 import lines (`from __future__ import annotations`, `from datetime import timedelta`, `from typing import Final`) — also the shape used by the reference `users/constants.py`.
- **Fix:** Kept the example code's 3-line import block verbatim. The acceptance criterion's count of 2 is a planning-time miscount of 3 example lines; the example code and the cross-referenced reference shape (`app/modules/users/constants.py`) both have 3 imports. Module passes ruff + mypy --strict.
- **Files modified:** `apps/backend/app/modules/auth/constants.py`
- **Commit:** `6f77463`

## Verification Results

Overall verification block (all from plan):

```
$ cd apps/backend && uv run ruff check app/modules/auth/constants.py app/modules/auth/reset_rate_limit.py
All checks passed!

$ cd apps/backend && uv run mypy --strict app/modules/auth/constants.py app/modules/auth/reset_rate_limit.py
Success: no issues found in 2 source files

$ cd apps/backend && uv run python -c "from app.modules.auth import constants, reset_rate_limit; print(constants.PASSWORD_RESET_TOKEN_TTL, hasattr(reset_rate_limit, 'check_reset_rate_ip'))"
1:00:00 True

$ cd apps/backend && uv run lint-imports
Contracts: 3 kept, 0 broken.
```

## Success Criteria

- [x] `PASSWORD_RESET_TOKEN_TTL == timedelta(hours=1)` importable from `app.modules.auth.constants`.
- [x] All 6 rate-limit helpers (3 check + 3 bump) importable from `app.modules.auth.reset_rate_limit`.
- [x] ruff + mypy --strict + import-linter all green.
- [x] No downstream Phase 44 file imports yet (Wave 2 picks these up).

## Commits

| Task | Commit  | Message                                                                |
| ---- | ------- | ---------------------------------------------------------------------- |
| 1    | 6f77463 | feat(44-01): add PASSWORD_RESET_TOKEN_TTL constant (D-44-05)           |
| 2    | 73d3e2a | feat(44-01): add password-reset 3-key rate limiter (D-44-10/11/12/13)  |

## Self-Check: PASSED

- File `apps/backend/app/modules/auth/constants.py` exists.
- File `apps/backend/app/modules/auth/reset_rate_limit.py` exists.
- Commit `6f77463` exists in git log.
- Commit `73d3e2a` exists in git log.
