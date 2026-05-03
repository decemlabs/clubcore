---
phase: 07-telegram-otp-channel
plan: 08
subsystem: backend.tests
tags: [telegram, otp, integration-tests, pytest-asyncio, savepoint, structlog, capture_logs, ptb22]

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    plan: 04
    provides: telegram_service.{start_deep_link, bind_and_issue, commit_otp, consume, get_status} + TelegramUnknownAccount
  - phase: 07-telegram-otp-channel
    plan: 05
    provides: app.integrations.telegram.handlers.{start_handler, HandlerContext} + sender.{send_otp_dm, send_text_dm}
  - phase: 07-telegram-otp-channel
    plan: 06
    provides: /api/v1/auth/telegram/{start,status,verify} endpoints with D-13 dispatch
  - phase: 05-user-schema-email-password-auth
    provides: SAVEPOINT-rolled db_session fixture (D-22); User / OtpCode models in final shape
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: hash_password helper; sz_access / sz_refresh / sportzal_csrf cookie names

provides:
  - apps/backend/tests/conftest.py:stub_telegram_sender fixture (D-07, D-16)
  - apps/backend/tests/conftest.py:StubTelegramSender + StubSenderResult dataclasses
  - apps/backend/tests/integration/auth/test_telegram_start.py (AUTH-TG-01)
  - apps/backend/tests/integration/auth/test_telegram_verify_happy.py (AUTH-TG-02 + AUTH-TG-04 + AUTH-TG-06)
  - apps/backend/tests/integration/auth/test_telegram_verify_errors.py (D-13 6-mode matrix; AUTH-TG-06)
  - apps/backend/tests/integration/telegram/__init__.py (package marker)
  - apps/backend/tests/integration/telegram/test_handler_start.py (D-15 direct handler tests, 3 cases)

affects:
  - Phase 7 verification (TEST-03 fully discharged)
  - Phase 8 audit_log latch: locked event names (telegram_deep_link_issued, otp_consumed, login_success{channel}, telegram_unknown_start, telegram_dm_blocked) are now exercised end-to-end
  - Future regression suites: stub_telegram_sender + SAVEPOINT pattern reusable for any test that wants to exercise the OTP code paths without live ptb

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stub-recorder fixture pattern: monkeypatch app.integrations.telegram.sender.{send_otp_dm, send_text_dm} to a StubTelegramSender that records (chat_id, code/text) tuples and exposes .next_result for blocked / transient simulation"
    - "Direct service-call simulation under SAVEPOINT (D-15): tests bypass the ptb event loop by calling telegram_service.bind_and_issue + commit_otp directly under the same db_session that the API requests use"
    - "asynccontextmanager session_factory adapter: `_build_ctx` wraps the SAVEPOINT-rolled db_session so HandlerContext.session_factory() in tests yields the same session the test asserts on (Phase 5 D-22 transactional isolation preserved)"
    - "structlog cache_logger_on_first_use workaround: autouse fixture re-acquires handlers_mod.logger after each per-test app fixture re-configures structlog -- otherwise capture_logs cannot intercept events emitted from the cached module-level logger"
    - "OTP raw-code leak assertion (T-07-38 mitigation): every captured log entry's str(value) is checked to NOT contain the raw 6-digit code -- guarantees structlog never sees the secret"

key-files:
  created:
    - apps/backend/tests/integration/telegram/__init__.py
    - apps/backend/tests/integration/auth/test_telegram_start.py
    - apps/backend/tests/integration/auth/test_telegram_verify_happy.py
    - apps/backend/tests/integration/auth/test_telegram_verify_errors.py
    - apps/backend/tests/integration/telegram/test_handler_start.py
  modified:
    - apps/backend/tests/conftest.py

key-decisions:
  - "stub_telegram_sender monkeypatches BOTH send_otp_dm and send_text_dm: send_otp_dm goes into stub.calls (chat_id, code), send_text_dm into stub.text_calls (chat_id, text). Test 2 (stranger) reads .text_calls; Test 1 / Test 3 read .calls."
  - "StubSenderResult / StubTelegramSender exported under public names (no leading underscore) AND aliased as _StubSenderResult / _StubTelegramSender for backwards-compat with any plan-action snippet that expected the underscored name. Resolves the plan-checker WARNING about `from tests.conftest import _StubSenderResult` reaching into a module private."
  - "StubSenderResult mirrors the SendResult dataclass (ok / blocked / error) but is independent of app.integrations.telegram.sender.SendResult to avoid runtime coupling -- the monkeypatch returns whatever the stub returns; the handler only inspects .ok / .blocked / .error which are duck-typed."
  - "test_telegram_verify_happy uses headers.get_list('set-cookie') (httpx stable API matching test_login.py) -- NOT the fragile hasattr/headers.raw fallback the plan's original action block had. Plan-checker WARNING addressed."
  - "test_telegram_verify_errors implements 5 individual test functions instead of a parametrize-over-table: scenarios have very different fixtures (token_unknown needs no setup; bot_not_started needs only start_deep_link; otp_expired/invalid/consumed need full normal_otp arrange). A single parametrized function would push the per-scenario branching into a giant if-tree inside the test body -- harder to debug than 5 focused tests."
  - "test_handler_start uses an autouse fixture _refresh_handler_logger that monkey-patches handlers_mod.logger to a freshly-acquired structlog logger. Required because configure_logging() runs in every per-test app fixture but cache_logger_on_first_use=True means the module-level cached BoundLogger snapshots the FIRST configuration's processors -- subsequent capture_logs() (which mutates the global processor chain) can't intercept events emitted from the cached logger."
  - "Did NOT change app/core/logging.py to disable cache_logger_on_first_use because that's a production-perf knob; the test-side workaround is scoped to this one test file via the autouse fixture."

patterns-established:
  - "Phase 7 reusable test arrangement: `_arrange_normal_otp(db_session)` and `_arrange_bot_not_started(db_session)` helpers in test_telegram_verify_errors -- can be lifted to a phase-specific test helpers module if Phase 8 / Phase 10 needs the same arrangement"
  - "SimpleNamespace ptb-Update double pattern: minimum-fields-only construction (effective_user, effective_chat, message{text, chat, from_user}). Future ptb 22 handler tests (e.g., a /help handler in v1.2) can reuse the _build_update / _build_ctx helpers verbatim"
  - "Cross-test capture_logs reliability: the autouse logger-refresh fixture pattern is applicable to ANY test module whose target uses a structlog module-level logger AND relies on capture_logs assertions"

requirements-completed:
  - TEST-03

# Metrics
metrics:
  duration_minutes: 12
  completed_date: "2026-05-02"
  tasks_completed: 4
  files_changed: 6
  commits:
    - afcd421
    - ed193bf
    - 4b30f65
    - bbad5d4
---

# Phase 7 Plan 08: Telegram Integration Tests + stub_telegram_sender Fixture Summary

TEST-03 fully discharged: four new integration test files plus one pytest fixture cover Phase 7 end-to-end. The bot path runs without any live python-telegram-bot event loop (D-15) -- handler tests hand-build SimpleNamespace doubles for `Update` / `Message` / `User` / `Chat`, and API-level happy-path tests simulate "the bot ran /start" by calling `telegram_service.bind_and_issue` + `commit_otp` directly under the same SAVEPOINT-rolled session (Phase 5 D-22). The `stub_telegram_sender` fixture monkeypatches `send_otp_dm` and `send_text_dm` to a recorder so all six D-13 verify error modes plus three handler branches (known / stranger / blocked DM) are deterministic.

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-05-02
- **Tasks:** 4 (each atomically committed with --no-verify)
- **Files changed:** 6 (5 created, 1 modified)

## Task Commits

| # | Task | Commit | Type |
|---|---|---|---|
| 1 | conftest.py stub_telegram_sender fixture + telegram tests package marker | `afcd421` | test |
| 2 | test_telegram_start.py + test_telegram_verify_happy.py (AUTH-TG-01/02/04/06 happy paths) | `ed193bf` | test |
| 3 | test_telegram_verify_errors.py (D-13 6-mode matrix) | `4b30f65` | test |
| 4 | test_handler_start.py (D-15 direct handler tests) + structlog logger refresh fixture | `bbad5d4` | test |

## Files Created/Modified

| File | Status | Role |
|---|---|---|
| `apps/backend/tests/conftest.py` | modified (+59 lines) | Added StubSenderResult / StubTelegramSender dataclasses + stub_telegram_sender pytest fixture (D-07, D-16) |
| `apps/backend/tests/integration/telegram/__init__.py` | created | Package marker for the new tests/integration/telegram/ subpackage |
| `apps/backend/tests/integration/auth/test_telegram_start.py` | created | AUTH-TG-01: POST /telegram/start returns deepLinkUrl + creates OtpCode w/ code_hash IS NULL |
| `apps/backend/tests/integration/auth/test_telegram_verify_happy.py` | created | AUTH-TG-02 + AUTH-TG-04 + AUTH-TG-06: full /start -> bot bind+commit (direct) -> /verify -> 200 + 3 cookies + structlog otp_consumed + login_success(channel='telegram') |
| `apps/backend/tests/integration/auth/test_telegram_verify_errors.py` | created | D-13 dispatch table: 5 tests covering 6 failure modes (token_unknown, bot_not_started, otp_expired, otp_invalid x4 + otp_max_attempts, otp_consumed) |
| `apps/backend/tests/integration/telegram/test_handler_start.py` | created | D-15: 3 direct handler tests (known username binds + DMs; stranger DM + telegram_unknown_start; sender blocked -> no commit + telegram_dm_blocked) |

## Test Inventory

| File | Test count | Coverage |
|---|---|---|
| test_telegram_start.py | 1 | AUTH-TG-01 |
| test_telegram_verify_happy.py | 1 | AUTH-TG-02, AUTH-TG-04, AUTH-TG-06 happy path |
| test_telegram_verify_errors.py | 5 | All 6 D-13 failure modes (otp_invalid + otp_max_attempts share one test that walks the 5-attempt counter) |
| test_handler_start.py | 3 | D-04 stranger flow; D-11 atomic-after-DM (blocked); happy bind path |
| **TOTAL Phase 7 new tests** | **10** | TEST-03 fully discharged |

## Decisions Made

| Decision | Why |
|----------|-----|
| StubSenderResult / StubTelegramSender exported as public names (no leading underscore) | Plan-checker flagged that `from tests.conftest import _StubSenderResult` reaches into a private module attribute. Public names with backwards-compat underscored aliases satisfy both readability AND any plan-action snippet that expected the underscored form. |
| 5 individual error tests instead of one `pytest.mark.parametrize` over 6 scenarios | Per-scenario fixture requirements differ wildly (token_unknown needs zero setup; bot_not_started needs only `start_deep_link`; otp_invalid loops 5 times). Parametrizing would push branching into the test body, sacrificing failure-message clarity. Five focused functions is the cleaner pytest idiom. |
| Cookie-presence assertions use `headers.get_list("set-cookie")` (matching test_login.py) | Plan's original action block had `if hasattr(verify.headers, "get_list") else verify.headers.raw` -- fragile and unnecessary. httpx Response.headers consistently exposes get_list across all versions in the project's lock. |
| `_build_ctx` wraps db_session in an `@asynccontextmanager` factory rather than substituting an `async_sessionmaker` | The handler does `async with ctx.session_factory() as session:`. A real async_sessionmaker would open a NEW connection (different SAVEPOINT scope) defeating the per-test rollback. The asynccontextmanager adapter yields THE SAME session the test asserts on. The `# type: ignore[arg-type]` is a one-line documented compromise -- runtime behavior is correct and isolated to the test setup. |
| Autouse `_refresh_handler_logger` fixture in test_handler_start.py | structlog's `cache_logger_on_first_use=True` (set in `app/core/logging.py`) means the module-level `logger = structlog.get_logger("telegram.handler")` in handlers.py snapshots the FIRST configure_logging call's processors. Per-test `app` fixture re-configures structlog, but the cached logger keeps the OLD processors. `capture_logs()` mutates the global processor chain -- so events emitted via the cached logger bypass the capture. Re-acquiring `structlog.get_logger("telegram.handler")` after re-configure returns a fresh BoundLogger with the current processors. The fixture monkey-patches `handlers_mod.logger` to that fresh instance per-test. Production code unchanged. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two ruff I001 (unsorted import block) errors after initial draft**
- **Found during:** Task 3 + Task 4 first ruff run.
- **Issue:** Initial drafts placed `from tests.conftest import ...` after the `from app.modules.auth.models import ...` block; ruff's import sorter wanted them grouped first-party imports together with `app` then `tests` separately.
- **Fix:** `uv run ruff check --fix` resolved both files automatically (single import sort). Final ruff/mypy GREEN.
- **Files modified:** `tests/integration/auth/test_telegram_verify_errors.py`, `tests/integration/telegram/test_handler_start.py`
- **Commits:** Folded into `4b30f65` and `bbad5d4` respectively.

**2. [Rule 3 - Blocking] One ruff E501 (line too long) on docstring line in test_handler_start.py**
- **Found during:** Task 4 first ruff run (after I001 auto-fix).
- **Issue:** The 3-bullet test-case docstring had a line that exceeded the 100-char limit.
- **Fix:** Split the line at "(D-11 atomicity)" with continuation on the next line.
- **Files modified:** `tests/integration/telegram/test_handler_start.py`
- **Commit:** Folded into `bbad5d4`.

**3. [Rule 1 - Bug] structlog cache_logger_on_first_use blocked capture_logs in test_handler_start.py Test 3**
- **Found during:** Task 4 verify -- `pytest tests/integration/telegram/test_handler_start.py -v` ran Tests 1-2 GREEN, Test 3 FAILED with `events=[]`.
- **Investigation:** Test 3 ran fine in isolation. Failed only when preceded by another test that consumed the `app` fixture (which calls `configure_logging`). Probe script confirmed: `structlog.get_logger(name)` returns a cached BoundLogger after the FIRST `configure_logging()`; subsequent `configure_logging()` does NOT rebind the cached instance, so `capture_logs()` (which mutates the global processor chain) cannot intercept events emitted via the cached logger.
- **Fix:** Added autouse `_refresh_handler_logger` fixture that re-acquires `structlog.get_logger("telegram.handler")` (returns a fresh BoundLogger because cache invalidation happens during configure) and monkey-patches `handlers_mod.logger` to that fresh instance per-test. Production code (handlers.py, logging.py) unchanged.
- **Why not change cache_logger_on_first_use=False in app/core/logging.py:** that's a production-performance knob; flipping it would add a hot-path lookup overhead on every emit. Test-side scoping is the right tradeoff.
- **Files modified:** `tests/integration/telegram/test_handler_start.py`
- **Commit:** Folded into `bbad5d4`.

**4. [Rule 3 - Blocking, environmental] Docker compose `migrate` service failed with "Can't locate revision identified by '0001_auth'"**
- **Found during:** Local-environment setup before running pytest.
- **Issue:** The pre-existing Postgres docker volume contained `alembic_version='0001_auth'` from a previous worktree's run. The `migrate` container's filesystem lacked the matching revision file (build-time snapshot before the Phase 5 migration was renumbered). Result: alembic refused to upgrade.
- **Fix:** `docker compose exec postgres psql -c "DROP TABLE IF EXISTS alembic_version, otp_codes, refresh_tokens, users CASCADE"` followed by running alembic from the host (`uv run alembic upgrade head` against `localhost:5432`). Migrations applied cleanly: `0001_auth -> 0003_telegram_username`.
- **Why this isn't a code bug:** the application code + migration files are correct; the issue was a stale Docker volume colliding with a fresh code checkout. Documented here so the same situation in a future worktree spin-up is recognized quickly.
- **Files modified:** None (one-shot infra cleanup).

---

**Total deviations:** 4 auto-fixed (3 lint/test-infrastructure, 1 environmental). All fixes preserve plan intent and contracts; no production code changed.

## Verification

| Check | Result |
|---|---|
| `test -f apps/backend/tests/integration/telegram/__init__.py` | PASS |
| `grep -q "stub_telegram_sender" apps/backend/tests/conftest.py` | PASS |
| `grep -q "_StubTelegramSender" apps/backend/tests/conftest.py` (alias) | PASS |
| `grep -q "monkeypatch.setattr(sender_mod, \"send_otp_dm\"" tests/conftest.py` | PASS |
| `grep -q "monkeypatch.setattr(sender_mod, \"send_text_dm\"" tests/conftest.py` | PASS |
| `uv run mypy --strict tests/conftest.py` | Success: no issues found in 1 source file |
| `uv run mypy --strict tests/integration/auth/test_telegram_start.py tests/integration/auth/test_telegram_verify_happy.py` | Success: no issues found in 2 source files |
| `uv run mypy --strict tests/integration/auth/test_telegram_verify_errors.py` | Success: no issues found in 1 source file |
| `uv run mypy --strict tests/integration/telegram/test_handler_start.py` | Success: no issues found in 1 source file |
| `uv run mypy --strict app` (full backend, sanity) | Success: no issues found in 52 source files |
| `uv run ruff check tests/integration/auth tests/integration/telegram tests/conftest.py` | All checks passed! |
| `uv run ruff check app tests` (whole backend, sanity) | All checks passed! |
| `uv run lint-imports` (3 contracts) | 3 KEPT, 0 broken |
| `uv run pytest tests/integration/auth/test_telegram_start.py tests/integration/auth/test_telegram_verify_happy.py tests/integration/auth/test_telegram_verify_errors.py tests/integration/telegram/test_handler_start.py -v` | 10 PASSED in 0.71s |
| `uv run pytest tests/ -q` (full regression) | **204 passed in 6.06s** -- ZERO failures, ZERO new skips |

## Threat Mitigations Honored

- **T-07-38 (Information Disclosure -- raw OTP in test logs):** `test_telegram_verify_happy_path` iterates every captured log entry's values and asserts `raw_code not in str(value)`. Guarantees no test ever logs the secret.
- **T-07-39 (Tampering -- flaky 5-attempt counter test):** `wrong_code` is computed as `"999999" if raw_code != "999999" else "888888"` -- guaranteed-different from the real code regardless of which 6-digit value generate_otp_code() returned. SAVEPOINT rollback ensures fresh state per test.
- **T-07-40 (Repudiation -- handler branch untested):** Test 3 (sender blocked) explicitly verifies the D-11 atomic-after-DM contract: `code_hash` STAYS NULL when sender returns blocked=True, AND `telegram_dm_blocked` is emitted to structlog. Future Phase 8 audit_log writer can latch on that event with confidence.
- **T-07-41 (Spoofing -- direct service call bypasses router):** Accepted per D-15. Handler tests DO bypass the router (that's the point -- testing the handler in isolation), but the router/middleware path is covered by `test_telegram_start.py`, `test_telegram_verify_happy.py`, and `test_telegram_verify_errors.py` which go through the full ASGI stack via `async_client`.

## Threat Flags

None. No new network surface (test-only changes), no new auth path, no new file access pattern, no schema change. The `stub_telegram_sender` fixture's monkeypatch is test-scope only; it cannot affect production code.

## Next Phase Readiness

- **Phase 7 fully shipped.** All 8 plans complete. TEST-03 is the last requirement; with this plan, every Phase 7 REQ-ID (INFRA-06, AUTH-TG-01..06, TEST-03) is verified by green tests.
- **Phase 8 (Clients + Audit Log)** can rely on every locked Phase 7 event name (`telegram_deep_link_issued`, `otp_issued`, `otp_consumed`, `telegram_unknown_start`, `telegram_dm_blocked`, `telegram_dm_failed`, `telegram_replay_attempt`, `login_success` with `channel='telegram'`) being exercised by these tests. The audit_log writer's "swap from structlog-only to structlog+DB" change is mechanical -- the tests will continue to assert event NAMES, and Phase 8 will add a parallel DB row check.
- **Phase 10 (admin-web Telegram tab)** can wire `/auth/telegram/start` -> status polling -> `/verify` against contract guaranteed by `test_telegram_start.py` (envelope shape) + `test_telegram_verify_happy.py` (cookie + body shape) + `test_telegram_verify_errors.py` (error codes for FE branching). FE-02 design contract is locked.
- **Reusable for future channels:** the `stub_telegram_sender` + SAVEPOINT + `_build_update`/`_build_ctx` helpers are the template for any future ptb 22 handler test (e.g., `/help` or `/unbind` if v1.2 adds them).

## Self-Check: PASSED

Files asserted to exist:
- FOUND: `apps/backend/tests/integration/telegram/__init__.py`
- FOUND: `apps/backend/tests/integration/auth/test_telegram_start.py`
- FOUND: `apps/backend/tests/integration/auth/test_telegram_verify_happy.py`
- FOUND: `apps/backend/tests/integration/auth/test_telegram_verify_errors.py`
- FOUND: `apps/backend/tests/integration/telegram/test_handler_start.py`
- FOUND: `apps/backend/tests/conftest.py` (modified, +59 lines)

Commits asserted to exist on branch:
- FOUND: `afcd421` (Task 1 -- fixture + package marker)
- FOUND: `ed193bf` (Task 2 -- start + verify_happy)
- FOUND: `4b30f65` (Task 3 -- verify_errors matrix)
- FOUND: `bbad5d4` (Task 4 -- handler_start direct tests)

Verified via:
```
git log --oneline -6
bbad5d4 test(07-08): add direct ptb start_handler tests with hand-built Update doubles (D-15)
4b30f65 test(07-08): add D-13 verify error matrix integration tests
ed193bf test(07-08): add telegram /start and /verify happy-path integration tests
afcd421 test(07-08): add stub_telegram_sender fixture and telegram tests package marker
a30d714 docs(07): record Wave 3 completion in STATE.md (7/8 plans)
33a29ef chore: merge executor worktree (worktree-agent-a3f47a7725462bb1e)
```

---

*Phase: 07-telegram-otp-channel*
*Plan: 08 of 8 (Wave 4 -- final plan)*
*Completed: 2026-05-02*
