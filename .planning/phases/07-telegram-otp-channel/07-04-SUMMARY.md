---
phase: 07-telegram-otp-channel
plan: 04
subsystem: backend.modules.auth
tags: [telegram, otp, service, schemas, audit, app-error, sqlalchemy-async]

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    plan: 01
    provides: settings.telegram_bot_username / otp_deep_link_ttl_seconds / otp_code_ttl_seconds / otp_max_attempts
  - phase: 07-telegram-otp-channel
    plan: 02
    provides: User.telegram_username column (lower(value) lookup)
  - phase: 07-telegram-otp-channel
    plan: 03
    provides: BotNotStarted / OtpExpired / OtpInvalid / OtpMaxAttempts / OtpAlreadyConsumed / TokenUnknown AppError subclasses
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: generate_deep_link_token / generate_otp_code helpers; RequestContract / ResponseData bases
  - phase: 05-user-schema-email-password-auth
    provides: OtpCode final shape; AppError handler envelope

provides:
  - apps/backend/app/modules/auth/telegram_service.py:start_deep_link / bind_and_issue / commit_otp / consume / get_status (5 async functions)
  - apps/backend/app/modules/auth/telegram_service.py:TelegramUnknownAccount handler-only AppError subclass (D-04)
  - apps/backend/app/modules/auth/schemas.py:TelegramStartResponse / TelegramStatusResponse / TelegramVerifyRequest (3 DTOs)
  - apps/backend/app/core/audit.py docstring listing all 8 Phase 7 locked event names + login_success.channel kwarg

affects:
  - 07-05 bot handler (calls bind_and_issue then commit_otp via injected ctx; catches TelegramUnknownAccount + DMs RU error)
  - 07-06 verify router (calls consume + dispatches D-13 errors; calls start_deep_link + get_status)
  - 07-08 integration tests (parametrize D-13 dispatch; happy path uses bind_and_issue + commit_otp directly via stub_telegram_sender)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atomic-after-DM split: bind_and_issue() returns (user, raw_code, otp_row) without committing; commit_otp() persists state ONLY after sender ok=True (D-11)"
    - "D-19 silent-status pattern: get_status() catches every exception and returns False — no oracle for token validity"
    - "Counter-rewind defense: consume() commits attempts++ BEFORE raising OtpInvalid so dropped responses cannot reset the counter"

key-files:
  created:
    - apps/backend/app/modules/auth/telegram_service.py
  modified:
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/app/core/audit.py

key-decisions:
  - "D-01 bind-existing-only verified by grep: telegram_service.py contains zero `session.add(User(...)` or `insert(User)` statements. bind_and_issue only matches existing Users; commit_otp only mutates the existing User.telegram_chat_id column."
  - "D-11 atomicity implemented as a 3-method split (start_deep_link / bind_and_issue / commit_otp) so the bot handler can interleave the sender DM call between bind and commit. bind_and_issue performs zero session.commit() calls — verified by inspection."
  - "D-13 dispatch order in consume(): TokenUnknown -> OtpAlreadyConsumed -> BotNotStarted -> OtpExpired -> hash compare. Replays of consumed codes therefore report otp_consumed (409), not bot_not_started (409). FE distinguishes via the code field."
  - "D-19 implementation: get_status() wraps the SELECT in a bare try/except returning False; every downstream None/expired/consumed branch also returns False. Never raises."
  - "Plan-checker warning addressed: Task 2 verify replaced the multi-line python -c with single-line semicolon-chained statements (executes cleanly under zsh; no parse failures observed)."
  - "Adapted to actual generate_deep_link_token() signature: it returns str only (apps/backend/app/core/security.py:185-187), not the (raw, hash) tuple the plan's interfaces section described. start_deep_link() computes the hash locally via _sha256_hex helper, mirroring service.py:64-65."

patterns-established:
  - "Module-local _sha256_hex helper mirroring service.py:64-65 — avoids cross-module import of name-mangled app.core.security._sha256_hex"
  - "Handler-only AppError subclass (TelegramUnknownAccount): status_code=403 carried but never rendered to API clients; handler catches, DMs RU error, leaves OtpCode untouched so /verify reports BotNotStarted"

requirements-completed:
  - AUTH-TG-01
  - AUTH-TG-02
  - AUTH-TG-03
  - AUTH-TG-04
  - AUTH-TG-06

# Metrics
metrics:
  duration_minutes: 7
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 3
  commits:
    - 71e0db7
    - 3a9d3b5
---

# Phase 7 Plan 04: Telegram Service + DTOs + Audit Docstring Summary

Auth-module business layer for the Telegram OTP channel landed: `telegram_service.py` exports five async functions (start_deep_link / bind_and_issue / commit_otp / consume / get_status) honoring D-01 bind-existing-only, D-11 atomic-after-DM split, D-13 dispatch table, and D-19 silent-status. Three DTOs extend the Phase 4 contract bases for the upcoming router (07-06), and `audit.py` docstring now lists all eight Phase 7 locked event names so Phase 8's audit_log swap-in stays mechanical.

## Performance

- **Duration:** ~7 min
- **Completed:** 2026-05-02
- **Tasks:** 2 (both atomically committed)
- **Files changed:** 3 (1 created, 2 modified)

## Task Commits

| # | Task | Commit | Type |
|---|---|---|---|
| 1 | telegram_service.py with 5 OTP-lifecycle functions + TelegramUnknownAccount | `71e0db7` | feat |
| 2 | schemas.py 3 DTOs + audit.py Phase 7 docstring | `3a9d3b5` | feat |

## Files Created/Modified

| File | Status | Role |
|---|---|---|
| `apps/backend/app/modules/auth/telegram_service.py` | created | Sibling of service.py; OTP lifecycle business logic |
| `apps/backend/app/modules/auth/schemas.py` | modified (+33 lines) | Added 3 DTOs at end of file |
| `apps/backend/app/core/audit.py` | modified (+9 lines, -2 lines) | Extended locked-event docstring with 7 new Phase 7 names + channel kwarg |

## Function Inventory (telegram_service.py)

| # | Name | Signature | Commits? | Raises? | Notes |
|---|---|---|---|---|---|
| 1 | `start_deep_link(session)` | `-> tuple[str, str]` | YES (single INSERT) | no | Returns (raw_token, sha256_hash); emits telegram_deep_link_issued |
| 2 | `bind_and_issue(session, raw_token, chat_id, username)` | `-> tuple[User, str, OtpCode]` | **NO (D-11)** | TokenUnknown / OtpAlreadyConsumed / OtpExpired / TelegramUnknownAccount | Generates raw_code in-memory only |
| 3 | `commit_otp(session, otp_row, user, raw_code, chat_id)` | `-> None` | YES | no | Mutates User.telegram_chat_id (if NULL) + OtpCode; emits otp_issued |
| 4 | `consume(session, raw_token, raw_code)` | `-> User` | YES (attempts++ + success path) | TokenUnknown / OtpAlreadyConsumed / BotNotStarted / OtpExpired / OtpInvalid / OtpMaxAttempts | D-13 dispatch |
| 5 | `get_status(session, raw_token)` | `-> bool` | no | **NEVER (D-19)** | Wraps SELECT in try/except returning False |

Plus `TelegramUnknownAccount(AppError)` — handler-only exception (status_code=403 documented but never reaches the FE).

## Decisions Made

| Decision | Why |
|----------|-----|
| `start_deep_link` computes the hash locally via `_sha256_hex(raw_token)` instead of unpacking a tuple from `generate_deep_link_token()` | The actual helper signature returns `str` only (`apps/backend/app/core/security.py:185-187`), contrary to the plan's `<interfaces>` text. The plan's `<action>` block already accounted for this with the local `_sha256_hex` helper; the implementation matches the action block exactly. |
| `_sha256_hex` lives locally in `telegram_service.py` (not imported from `app.core.security`) | `app.core.security._sha256_hex` is name-mangled (underscore prefix) so cross-module import would be a private-API leak. `service.py:64-65` already ships its own local copy; this plan mirrors that established pattern. |
| `consume()` uses an explicit `if user_id is None` defensive check before the success-path commit | mypy --strict could not narrow `OtpCode.user_id` (Mapped[UUID \| None]) at the success path. The defensive branch raises `TokenUnknown('user_disappeared')` for the corruption case (code_hash IS NOT NULL but user_id IS NULL — should be impossible after commit_otp ran, but cheap to defend). |
| `get_status()` wraps the SELECT in `try/except Exception:` (no noqa) | D-19 is "never raises" — defense-in-depth even though the helpers themselves cannot fail on string input. Project ruff config does NOT enable BLE001, so the bare except is accepted without noqa noise. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's `<interfaces>` section described `generate_deep_link_token()` as returning `tuple[str, str]`, but the helper actually returns `str` only**
- **Found during:** Task 1 implementation (cross-checking `app/core/security.py:185-187`).
- **Issue:** The plan's interfaces block at line 90 said `def generate_deep_link_token() -> tuple[str, str]: # (raw, sha256_hex)`. The actual signature is `def generate_deep_link_token() -> str:` (returns the raw URL-safe token only; no hash).
- **Fix:** `start_deep_link()` calls `generate_deep_link_token()` for the raw token, then computes the hash locally via `_sha256_hex(raw_token)`. The plan's `<action>` block was already consistent with this approach (it imported `_sha256_hex` and used it elsewhere), so the implementation matches the plan's intent — only the interfaces description was stale.
- **Files modified:** `apps/backend/app/modules/auth/telegram_service.py`
- **Commit:** `71e0db7`

**2. [Rule 3 - Blocking] Three ruff issues on first write of telegram_service.py (I001 import sort, RUF100 unused noqa, SIM103 simplifiable return)**
- **Found during:** Task 1 verify (`uv run ruff check`).
- **Issue:** Initial draft had a `# noqa: BLE001` on the get_status try/except (BLE001 is not enabled in this project's ruff config), an import-block sort warning, and a SIM103 on the final `if otp_row.consumed_at is not None: return False; return True` chain.
- **Fix:** `uv run ruff check --fix` resolved I001 + RUF100 automatically; SIM103 was applied manually as `return otp_row.consumed_at is None`. Final ruff/mypy/lint-imports all GREEN.
- **Files modified:** `apps/backend/app/modules/auth/telegram_service.py` (final state of Task 1 commit)
- **Commit:** `71e0db7`

**3. [Rule 3 - Blocking] Plan Task 2 verify block used a multi-line `python -c` that may fail under zsh parsing**
- **Found during:** Pre-execution review (per orchestrator's PARALLEL EXECUTION instruction explicitly flagging this issue).
- **Issue:** The plan's Task 2 verify gate had a `python -c "from ...; import pytest; raised=False\ntry: ...\nexcept Exception: raised=True\nassert raised, ..."` block. Multi-line python -c is zsh-fragile.
- **Fix:** Restructured the negative-test as a single-line newline-embedded `python -c` invocation with a properly indented `try/except` block on the next line — runs cleanly under zsh. Output: `short-code rejection OK`.
- **No code changes** — this fix only affected the verify-gate command, not the implementation.

---

**Total deviations:** 3 auto-fixed (1 stale-doc bug, 2 blocking lint/parse issues). All fixes preserve the plan's intent and contract.

## Verification

| Check | Result |
|---|---|
| File exists: `apps/backend/app/modules/auth/telegram_service.py` | PASS |
| `grep -c "^async def"` returns 5 | PASS |
| All 5 async functions present (start_deep_link / bind_and_issue / commit_otp / consume / get_status) | PASS |
| `class TelegramUnknownAccount` defined | PASS |
| **D-01 verified:** `! grep -E 'session\.add\(.*User\(\|insert\(User\)' telegram_service.py` | PASS (no User INSERT) |
| **D-13 dispatch:** consume() raises TokenUnknown / OtpAlreadyConsumed / BotNotStarted / OtpExpired / OtpInvalid / OtpMaxAttempts | PASS (verified by code inspection) |
| **D-19 verified:** get_status() wraps SELECT in try/except, every branch returns bool, no `raise` keyword | PASS |
| Three new DTOs import + expose expected fields | PASS (`['deep_link_url', 'deep_link_token']`, `['deep_link_token', 'code']`) |
| TelegramVerifyRequest accepts camelCase: `{'deepLinkToken':'abc','code':'123456'}` | PASS |
| TelegramVerifyRequest rejects 5-digit code | PASS |
| audit.py docstring contains: `telegram_deep_link_issued`, `otp_consumed`, `telegram_replay_attempt` | PASS |
| `uv run mypy --strict app/modules/auth/telegram_service.py` | Success (1 file) |
| `uv run mypy --strict app/modules/auth/schemas.py app/core/audit.py` | Success (2 files) |
| `uv run mypy --strict app` (full backend, sanity) | Success (51 source files) |
| `uv run ruff check app/modules/auth/telegram_service.py` | All checks passed! |
| `uv run ruff check app/modules/auth/schemas.py app/core/audit.py` | All checks passed! |
| `uv run lint-imports` (3 contracts) | All KEPT |

## Threat Mitigations Honored

- **T-07-13 (Tampering — OTP brute force):** `consume()` increments `attempts` and commits BEFORE raising `OtpInvalid`/`OtpMaxAttempts`. An attacker dropping the response cannot rewind the counter.
- **T-07-14 (Repudiation — OTP without audit):** every state-changing path emits a locked event (`telegram_deep_link_issued`, `otp_issued`, `otp_consumed`). Phase 8 audit_log writer will pick these up unchanged.
- **T-07-15 (Information Disclosure — get_status leaks token validity):** D-19 implemented as silent False on every error path including the bare `try/except Exception:` around the SELECT. Unknown / expired / consumed all return False — no oracle.
- **T-07-16 (Information Disclosure — OTP code in logs):** `raw_code` is never passed to `emit()`. Only `code_hash` enters the database; only `user_id` and `chat_id` enter audit events.
- **T-07-18 (EoP — replay):** `consumed_at IS NOT NULL` check is the second branch in `consume()` (right after the row-not-found check), guaranteed to fire before any hash compare. Returns 409 `otp_consumed`.
- **T-07-19 (Tampering — bot-as-oracle):** `TelegramUnknownAccount` carries `status_code=403` but is documented as handler-only — never rendered to API clients. The `/verify` endpoint only ever sees `OtpCode` rows, so a stranger-/start path produces the same `bot_not_started` (409) code as "user never pressed /start". FE single-branch UX preserved.
- **T-07-20 (Tampering — first-bind race):** `commit_otp()` sets `users.telegram_chat_id` only if currently NULL; the UNIQUE index on `users.telegram_chat_id` (Phase 5 D-02) means a parallel attacker with a different chat_id will fail the constraint when their own commit_otp runs.

## Threat Flags

None — no new network surface, no new auth path, no new file access pattern, no schema change. All STRIDE entries from the plan's threat model are addressed by the implementation as designed.

## Next Phase Readiness

- **Plan 07-05 (bot handler)** can `from app.modules.auth import telegram_service` (workers→modules.auth relaxation per D-06 already documented in `app/workers/__init__.py`) and call `telegram_service.bind_and_issue(...)` then `telegram_service.commit_otp(...)` per D-11. The `TelegramUnknownAccount` exception is the catch site for the "stranger /start" branch (D-04 RU DM).
- **Plan 07-06 (router)** can `from app.modules.auth.schemas import TelegramStartResponse, TelegramStatusResponse, TelegramVerifyRequest` and wire the three endpoints. The verify success path calls `telegram_service.consume(...)` then `issue_tokens(...)` + `issue_session_cookies(...)` exactly like `/login` (router.py lines 56-76 pattern).
- **Plan 07-08 (integration tests)** can:
  - parametrize the D-13 table directly against `body["code"]` / `response.status_code`
  - drive the happy path by calling `telegram_service.bind_and_issue(...)` then `telegram_service.commit_otp(...)` directly under the SAVEPOINT-rolled `db_session` (no live ptb event loop needed; D-15 / D-16 stub_telegram_sender pattern from PATTERNS.md lines 718-762)

## Self-Check: PASSED

Files asserted to exist:
- FOUND: `apps/backend/app/modules/auth/telegram_service.py`
- FOUND: `apps/backend/app/modules/auth/schemas.py` (modified)
- FOUND: `apps/backend/app/core/audit.py` (modified)

Commits asserted to exist on branch:
- FOUND: `71e0db7` (Task 1)
- FOUND: `3a9d3b5` (Task 2)

Verified via:
```
git log --oneline -5
3a9d3b5 feat(07-04): add Phase 7 telegram DTOs and extend audit event docstring
71e0db7 feat(07-04): add telegram_service with five OTP-lifecycle functions
```

---

*Phase: 07-telegram-otp-channel*
*Plan: 04 of 8 (Wave 2)*
*Completed: 2026-05-02*
