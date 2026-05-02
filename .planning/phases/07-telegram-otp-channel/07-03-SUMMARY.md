---
phase: 07-telegram-otp-channel
plan: 03
subsystem: auth
tags: [telegram, otp, exceptions, app-error, fastapi]

# Dependency graph
requires:
  - phase: 02-foundation-fastapi-app-and-error-envelope
    provides: AppError base class + _app_error_handler envelope (D-12)
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: AppError subclassing pattern (CsrfMismatch, InvalidPassword)
  - phase: 05-user-schema-email-password-auth
    provides: AppError subclassing pattern (RateLimited, InvalidAccessToken)
provides:
  - Six declarative AppError subclasses for /auth/telegram/verify failure modes
  - BotNotStarted (409 bot_not_started)
  - OtpExpired (410 otp_expired)
  - OtpInvalid (401 otp_invalid)
  - OtpMaxAttempts (429 otp_max_attempts)
  - OtpAlreadyConsumed (409 otp_consumed)
  - TokenUnknown (404 token_unknown)
affects: [07-04 telegram_service.consume, 07-06 verify router, 07-08 verify error tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-local AppError subclasses (app/modules/auth/exceptions.py) instead of crowding app/core/exceptions.py for narrow domains"
    - "Class-level code + status_code attributes; fields supplied by caller via parent __init__"

key-files:
  created:
    - apps/backend/app/modules/auth/exceptions.py
  modified: []

key-decisions:
  - "Module location: app/modules/auth/exceptions.py (not app/core/exceptions.py) — D-13 narrowness; Telegram-OTP specific"
  - "Declarative classes — no __init__ overrides; fields={deepLinkUrl}/{attemptsRemaining} comes through parent AppError.__init__"
  - "English docstrings (RU narrative belongs to PLAN/SUMMARY per Phase 3 D-05) — avoids ruff RUF002 ambiguous-Cyrillic-character lint"

patterns-established:
  - "Pattern: Module-local exception module — Phase N domains can ship their own exceptions.py inheriting from app.core.exceptions.AppError without registering a new handler"
  - "Pattern: # noqa: N818 on every AppError subclass whose name does not end in `Error` (matches CsrfMismatch / InvalidPassword / RateLimited convention)"

requirements-completed:
  - AUTH-TG-04
  - AUTH-TG-06

# Metrics
duration: ~5min
completed: 2026-05-02
---

# Phase 7 Plan 03: Telegram Verify Failure AppError Subclasses Summary

**Six declarative AppError subclasses for `/auth/telegram/verify` failure modes (D-13), riding the existing `_app_error_handler` envelope without new registration.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-02T19:21:30Z
- **Completed:** 2026-05-02T19:26:20Z
- **Tasks:** 1
- **Files modified:** 1 (1 created)

## Accomplishments
- Created `app/modules/auth/exceptions.py` with all six D-13 failure-mode classes
- Each class exports the exact `code` + `status_code` pair from D-13: BotNotStarted (409 bot_not_started), OtpExpired (410 otp_expired), OtpInvalid (401 otp_invalid), OtpMaxAttempts (429 otp_max_attempts), OtpAlreadyConsumed (409 otp_consumed), TokenUnknown (404 token_unknown)
- Verified that `BotNotStarted("...", fields={"deepLinkUrl": ...})` and `OtpInvalid("...", fields={"attemptsRemaining": n})` propagate `fields` through the parent `AppError.__init__`
- Confirmed FastAPI handler chain: subclasses inherit `AppError`, so the existing `_app_error_handler` (app/core/exceptions.py:81-93) renders `{code, message, fields?}` automatically — zero new wiring

## Task Commits

Each task committed atomically:

1. **Task 1: Create app/modules/auth/exceptions.py with six verify-failure subclasses (D-13)** — `5602f78` (feat)

_Note: This summary commit will be appended below._

## Files Created/Modified
- `apps/backend/app/modules/auth/exceptions.py` (NEW, 74 lines) — six AppError subclasses + module docstring with D-13 mapping table

## Decisions Made
- **English docstrings throughout the source file.** Plan PATTERNS/CONTEXT proposed Russian docstrings, but the project's ruff config selects `RUF` rules (no per-file ignore for `app/modules/`), so RUF002 flags ambiguous Cyrillic letters. Since the Russian narrative requirement (Phase 3 D-05) applies to PLAN/SUMMARY documents, code stays English. The D-13 mapping table in the module docstring captures the same information in English.
- **Declarative classes only** (no `__init__` overrides): fully aligned with the existing `CsrfMismatch` / `InvalidPassword` / `RateLimited` patterns in `app/core/exceptions.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Switched docstrings from Russian to English to satisfy ruff RUF002**
- **Found during:** Task 1 (verify step `uv run ruff check`)
- **Issue:** The plan's `<action>` block contained Russian-language docstrings (e.g., "Эти классы живут в app.modules.auth..."). The project's `pyproject.toml` selects `RUF` lint rules without per-file ignores for `app/modules/`. Ruff RUF002 (ambiguous Cyrillic letters in docstrings) raised six errors and broke the verify gate.
- **Fix:** Translated module docstring + every class docstring to English while preserving the same semantic content (D-13 mapping table, caller responsibilities for `fields`). Russian narrative remains the convention for PLAN/SUMMARY documents per Phase 3 D-05; code stays English-only.
- **Files modified:** `apps/backend/app/modules/auth/exceptions.py`
- **Verification:** `uv run ruff check app/modules/auth/exceptions.py` → "All checks passed!". `uv run mypy --strict` → success. `uv run lint-imports` → 3 contracts kept.
- **Committed in:** `5602f78` (final state of Task 1 commit; the failed-ruff first-write was fixed before commit).

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix was necessary to pass the plan's own verify gate (`uv run ruff check`). No scope creep — the public contract (class names, codes, status codes, fields propagation) is identical to the plan; only documentation language changed.

## Issues Encountered
- Initial ruff run reported six RUF002 errors for Cyrillic letters in docstrings (Я, Е, В, с, е, у). Resolved by translating docstrings to English while preserving semantic content. See deviation above.

## Threat Flags
None — this plan introduces no new network surface, no new auth path, no new file access pattern, and no schema change. The exception classes are pure declarative shapes that ride the already-shipped `_app_error_handler`.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Plan 07-04 (`telegram_service.consume`) can `from app.modules.auth.exceptions import BotNotStarted, OtpExpired, OtpInvalid, OtpMaxAttempts, OtpAlreadyConsumed, TokenUnknown` and raise the appropriate class with the appropriate `fields={}` payload.
- Plan 07-06 (`/auth/telegram/verify` router) needs no new exception handler registration; the existing `register_exception_handlers(app)` call in `app/main.py:create_app` already covers everything.
- Plan 07-08 (verify error tests) can parametrize the D-13 table directly against `body["code"]` / response.status_code without any extra fixture.

## Self-Check: PASSED
- File `apps/backend/app/modules/auth/exceptions.py`: FOUND
- Commit `5602f78`: FOUND in git log
- All six classes import + export expected `code`/`status_code` (verified by inline `python -c` snippet during Task 1 verify gate)
- `mypy --strict`, `ruff`, `lint-imports` all GREEN

---
*Phase: 07-telegram-otp-channel*
*Completed: 2026-05-02*
