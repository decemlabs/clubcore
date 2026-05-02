---
phase: 07-telegram-otp-channel
plan: 05
subsystem: integrations
tags: [telegram, python-telegram-bot, ptb22, factory, dataclass, namedtuple, integrations-perp-modules, structlog]

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    provides: Settings.telegram_bot_token / telegram_bot_username (07-01); AppError subclasses incl. OtpAlreadyConsumed dispatch by class name (07-03)
provides:
  - app.integrations.telegram.sender.send_otp_dm (SOLE outbound boundary, D-07)
  - app.integrations.telegram.sender.send_text_dm (generic DM helper for stranger / replay paths)
  - app.integrations.telegram.sender.SendResult (frozen dataclass: ok, blocked, error)
  - app.integrations.telegram.handlers.HandlerContext (NamedTuple: session_factory, telegram_service, sender)
  - app.integrations.telegram.handlers.start_handler (D-04, D-05, D-11, D-20 atomic-after-DM)
  - app.integrations.telegram.bot.build_application (factory; D-09 -- no module-level Application)
  - app.integrations.telegram.bot.HandlerCallable (Callable type alias)
  - app.integrations.telegram.bot._global_error_handler (resilience; bot survives handler raises)
affects: [07-04 telegram_service (handlers consume bind_and_issue / commit_otp / TelegramUnknownAccount via ctx closure), 07-07 worker entry (constructs HandlerContext + calls build_application), 07-08 handler tests (call start_handler directly with hand-built Update + stub_telegram_sender fixture)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-layer integration: bot.py = factory only; handlers.py = ptb callbacks consuming HandlerContext closure; sender.py = sole outbound DM boundary"
    - "HandlerContext NamedTuple closure (D-05): integrations layer stays free of app.modules.* imports while still calling domain functions through injected ModuleType references"
    - "Class-name dispatch for cross-layer exceptions: handler catches `Exception`, dispatches by `type(exc).__name__ == 'OtpAlreadyConsumed'` to avoid importing the exception class from app.modules.auth.exceptions (preserves integrations perp modules)"
    - "Frozen dataclass SendResult{ok, blocked, error}: outbound boundary returns typed result instead of raising (D-07); per-DM atomicity (D-11) becomes branchable in plain code without try/except in the handler"
    - "Per-handler closure adapter with default-arg binding (`_h=handler, _c=ctx`) inside build_application: avoids late-binding bug while wrapping (update, context, ctx) handlers into ptb's two-arg CommandHandler signature"
    - "Application factory with no module-level instance (D-09): `build_application(*, token, handlers, ctx) -> Application[Any, ...]` -- live instance lives in worker main()'s scope only"
    - "Global error handler hooked via `application.add_error_handler(_global_error_handler)`: long-polling loop never crashes on a handler raise (resilience)"

key-files:
  created: []
  modified:
    - apps/backend/app/integrations/telegram/__init__.py
    - apps/backend/app/integrations/telegram/sender.py
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/integrations/telegram/bot.py

key-decisions:
  - "D-05 implementation: HandlerContext NamedTuple shape locked as (session_factory: async_sessionmaker[AsyncSession], telegram_service: ModuleType, sender: ModuleType). NamedTuple chosen over dataclass for immutability + tuple-style structural typing in tests (D-15 hand-builds the closure)."
  - "D-07 implementation: SendResult is a frozen dataclass with kwarg-default `blocked=False, error=None`. Both Forbidden and BadRequest('chat not found' / 'chat_id') translate to blocked=True; all other Exceptions classify as transient (blocked=False, error=str(exc)). sender NEVER re-raises -- verified by `grep -E 'raise ' app/integrations/telegram/sender.py` returning empty."
  - "D-09 implementation: build_application is keyword-only, returns `Application[Any, Any, Any, Any, Any, Any]` (ptb 22's six-generic Application). NO module-level Application instance -- verified by `! grep -E '^application = Application' app/integrations/telegram/bot.py`."
  - "D-11 atomic-after-DM: bind_and_issue runs first (returns user, raw_code, otp_row in-memory; no commit yet). send_otp_dm runs next. Only on SendResult.ok=True does the handler call commit_otp -- otherwise no DB writes. blocked=True emits telegram_dm_blocked, transient emits telegram_dm_failed."
  - "D-20 single-use replay: handler dispatches OtpAlreadyConsumed by `type(exc).__name__` (avoids importing the exception class from app.modules.auth, preserving integrations perp modules). Replay path emits telegram_replay_attempt + DMs Russian 'Этот код уже использован, запросите новый.'"
  - "Plan-checker D-05 fix: handler does NOT use `ctx.telegram_service._sha256_hex(raw_token)` (option (c)/private-attr access -- architectural smell). Instead computes `deep_link_token_hash` locally via stdlib `hashlib.sha256(raw_token.encode('utf-8')).hexdigest()` in `_hash_token_for_log` helper. Preserves CONTEXT structlog event payloads (telegram_unknown_start / telegram_replay_attempt / telegram_start_rejected all carry deep_link_token_hash) without reaching into module privates."

patterns-established:
  - "Frozen-dataclass + bool-flag-pair return contract: makes happy/blocked/transient branches readable in linear code (no try/except for outbound classification)"
  - "ModuleType-typed dependency injection: handler module never imports its dependencies' source files; the `ctx.telegram_service` and `ctx.sender` references are typed as ModuleType and resolved at runtime by the worker entrypoint"
  - "Class-name string dispatch for cross-architectural-boundary exception handling: when contracts forbid an import, `type(exc).__name__ == 'X'` is the structurally-stable substitute for `isinstance(exc, X)`"
  - "Default-arg loop-variable capture: `async def _adapter(update, context, _h=handler, _c=ctx): ...` is the canonical Python pattern for binding loop variables into closures (avoids the LEGB late-binding pitfall that bites every developer once)"

requirements-completed:
  - AUTH-TG-02
  - AUTH-TG-05
  - AUTH-TG-06

# Metrics
duration: ~3min
completed: 2026-05-02
---

# Phase 7 Plan 05: Telegram Integration Wiring (sender + handlers + bot factory) Summary

**Three placeholder files in `app/integrations/telegram/` filled in: `sender.py` (sole outbound DM boundary with typed SendResult), `handlers.py` (start_handler + HandlerContext closure realising D-04 stranger / D-11 atomic-after-DM / D-20 replay), and `bot.py` (no-module-level Application factory + global error handler). The integrations perp modules importlinter contract is preserved -- domain calls reach handlers only through the injected HandlerContext.**

## Performance

- **Started:** 2026-05-02T19:39:20Z
- **Completed:** 2026-05-02T19:42:40Z
- **Duration:** ~3 min
- **Tasks:** 3
- **Files modified:** 4 (no creates -- all four files were placeholders with `TODO Phase X+` docstrings)

## Accomplishments

- `sender.send_otp_dm(bot, chat_id, code) -> SendResult` is the SOLE outbound DM boundary (D-07). Russian template `"Ваш код: {code}\nДействителен 5 минут."` locked verbatim per CONTEXT specifics line 253. `Forbidden` and `BadRequest("chat not found" / "chat_id")` translate to `SendResult(ok=False, blocked=True)`; all other `Exception` classify to `SendResult(ok=False, blocked=False, error=str(exc))`. Verified: `grep -E 'raise ' sender.py` is empty -- the function NEVER re-raises.
- `sender.send_text_dm(bot, chat_id, text) -> SendResult` is a generic counterpart used by `handlers.py` for the stranger (D-04) and replay (D-20) Russian DMs. Identical SendResult classification.
- `handlers.HandlerContext` is a `NamedTuple(session_factory, telegram_service, sender)` -- D-05 closure shape. NamedTuple was chosen over dataclass so `D-15` handler tests can construct the closure with positional args + structural-tuple inspection.
- `handlers.start_handler(update, context, ctx)` implements D-11 atomic-after-DM exactly:
  1. Parse `/start <token>` (silent debug log on shape mismatch).
  2. Compute non-secret `deep_link_token_hash = sha256(raw_token).hexdigest()` locally for structlog correlation.
  3. Open `ctx.session_factory()`; call `ctx.telegram_service.bind_and_issue(session, raw_token, chat_id, username)`.
  4. On `TelegramUnknownAccount` (D-04 stranger): emit `telegram_unknown_start` + DM fixed Russian + return (no commit).
  5. On `OtpAlreadyConsumed` (dispatched by `type(exc).__name__` -- D-20 replay): emit `telegram_replay_attempt` + DM Russian + return.
  6. On other exceptions (TokenUnknown / OtpExpired / etc.): emit `telegram_start_rejected {reason=cls_name}` + return silently (don't leak token validity).
  7. Otherwise: `await ctx.sender.send_otp_dm(bot, chat_id, raw_code)`. On `ok=True` call `ctx.telegram_service.commit_otp(...)`; on `blocked=True` emit `telegram_dm_blocked`; on transient emit `telegram_dm_failed`.
- `bot.build_application(*, token, handlers, ctx) -> Application[Any, ...]` is a keyword-only factory (D-09). Per-handler `_adapter` closure binds `(update, context, ctx)` handlers into ptb's `(update, context)` `CommandHandler` shape via default-arg loop-variable capture. `application.add_error_handler(_global_error_handler)` ensures the long-polling loop survives any handler raise.
- `__init__.py` docstring updated to document the three-layer split + the `integrations perp modules` constraint, replacing the original `TODO Phase X+` placeholder.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel worktree):

1. **Task 1: Implement sender.py (send_otp_dm + SendResult) and refresh __init__.py docstring (D-07)** -- `e40956b` (feat)
2. **Task 2: Implement handlers.py (start_handler + HandlerContext) -- D-04, D-05, D-11, D-20** -- `d0aac5b` (feat)
3. **Task 3: Implement bot.py build_application factory (D-09)** -- `58d009e` (feat)

## Files Created/Modified

- `apps/backend/app/integrations/telegram/__init__.py` -- replaced placeholder docstring with three-layer architecture summary + integrations perp modules constraint reminder.
- `apps/backend/app/integrations/telegram/sender.py` -- ~76 lines. `SendResult` frozen dataclass + `send_otp_dm` + `send_text_dm`. Imports only `telegram.Bot` / `telegram.error.{Forbidden, BadRequest}`.
- `apps/backend/app/integrations/telegram/handlers.py` -- ~155 lines. `HandlerContext` NamedTuple + Russian DM constants + `_parse_start_token` + `_hash_token_for_log` (stdlib sha256) + `start_handler`. NO `from app.modules.auth` anywhere -- domain modules reach the handler only through `ctx`.
- `apps/backend/app/integrations/telegram/bot.py` -- ~80 lines. `HandlerCallable` type alias + `_global_error_handler` + `build_application` factory. Imports only `telegram` SDK + own `app.integrations.telegram.handlers` module.

## Decisions Made

- **`Application` type-parameterised as `Application[Any, Any, Any, Any, Any, Any]`** -- ptb 22's `Application` class has six type parameters (`BT`, `CCT`, `UD`, `CD`, `BD`, `JQ`). Using `Any` for all six lets the factory return value flow through `mypy --strict` without forcing the worker to declare them. The actual application object inherits sensible defaults from `Application.builder()`.
- **`update: Any, context: Any` in `start_handler` signature** -- the public function signature uses `Any` so that callers (worker entrypoint via the `_adapter` closure in `build_application`) do not need to import `telegram.Update` / `ContextTypes.DEFAULT_TYPE` at the call site. Internal usage still type-checks (chat_id is `int`, username is `str | None`). Keeps the handler's PUBLIC signature decoupled from ptb types -- handler tests (D-15) hand-build `SimpleNamespace` doubles without satisfying any ptb stub.
- **`_hash_token_for_log` is a private module function (NOT a method on HandlerContext)** -- the hash is purely a structlog correlator (no security role). Defining it as a free function keeps the handler test surface flat: tests can either mock it or just observe the resulting log payload.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed redundant `# noqa: BLE001` directives in sender.py to satisfy ruff RUF100**
- **Found during:** Task 1 verify step `uv run ruff check`.
- **Issue:** The plan's `<action>` block placed `# noqa: BLE001` on the two `except Exception as exc:` lines in `sender.py`. The project's `ruff.toml` does NOT include `BLE` in `select`, so RUF100 (unused-noqa) flagged both directives. Two errors broke the verify gate.
- **Fix:** Removed the noqa directives and replaced them with plain trailing comments (`# outbound boundary -- classify all transport failures`). The semantic intent is preserved in the comment; the lint suppression was unnecessary because BLE rules are not active.
- **Files modified:** `apps/backend/app/integrations/telegram/sender.py`
- **Commit:** Fold into `e40956b` (Task 1 final commit -- the ruff failure was caught and fixed before commit).

**2. [Rule 3 - Blocking] Added `# noqa: RUF001` on the `_OTP_DM_TEMPLATE` Russian string in sender.py**
- **Found during:** Task 1 verify step `uv run ruff check`.
- **Issue:** RUF001 (string-contains-ambiguous-Cyrillic) raised four errors on `"Ваш код: {code}\nДействителен 5 минут."` -- characters `е` (Cyrillic IE), `с` (Cyrillic ES), and two more `е`s. The Russian copy is locked by CONTEXT specifics line 253 and PROJECT.md (RU/CIS-only product), so the string cannot be transliterated.
- **Fix:** Added `# noqa: RUF001` on the assignment line plus a two-line comment explaining the intent. This is the same precedent established in Phase 7 Plan 03 (the exceptions.py SUMMARY documented the same RUF tension and chose English docstrings for module-internal docs; here the constant IS the user-facing copy and must remain Russian).
- **Files modified:** `apps/backend/app/integrations/telegram/sender.py`
- **Commit:** Fold into `e40956b`.

**3. [Rule 3 - Blocking] Removed `# noqa: ARG001` from `_global_error_handler` in bot.py**
- **Found during:** Task 3 verify step `uv run ruff check`.
- **Issue:** RUF100 flagged the `# noqa: ARG001` on the `update: object` parameter as unused (ARG rules are not in `select`). The plan didn't include the noqa, but I added it preemptively expecting a unused-argument warning -- which never fires because ARG isn't enabled.
- **Fix:** Dropped the noqa directive. The `update` parameter is correctly accepted as part of the ptb-required `(update, context)` error-handler signature.
- **Files modified:** `apps/backend/app/integrations/telegram/bot.py`
- **Commit:** Fold into `58d009e`.

**4. [Rule 4 - Architectural deferral, plan-checker ack] Replaced `ctx.telegram_service._sha256_hex(raw_token)` with stdlib `hashlib.sha256(...)` in handlers.py**
- **Found during:** Pre-execution plan-checker warning embedded in this plan's prompt context.
- **Issue:** The plan's original `<action>` for `handlers.py` called `ctx.telegram_service._sha256_hex(raw_token)`. Reaching into a module's private (underscore-prefixed) helper is an architectural smell: the private contract could change in 07-04 (sibling Wave 2 plan, not yet executed) and break the handler. The integrations perp modules importlinter contract is statically enforced on `import` AST nodes, so `ctx.telegram_service._sha256_hex` would technically pass lint-imports -- but it would still violate the spirit of the boundary.
- **Fix:** Added `_hash_token_for_log(raw_token: str) -> str` private helper in `handlers.py` that uses stdlib `hashlib.sha256(raw_token.encode("utf-8")).hexdigest()`. Identical output (sha256 hex) to whatever 07-04 chooses to expose, with zero coupling to its internal API. Preserves CONTEXT structlog event payloads exactly (`deep_link_token_hash` field is unchanged on `telegram_unknown_start` / `telegram_replay_attempt` / `telegram_start_rejected` events).
- **Why not option (a) -- have bind_and_issue return the hash:** would force a coupling on 07-04's return tuple shape that the plan does not lock; would require changing CONTEXT line 19 `bind_and_issue(...)` signature.
- **Why not option (b) -- drop the field:** would silently mutate the structlog audit contract documented in CONTEXT lines 90 + 156. Phase 8 audit_log latches these field names.
- **Why not option (c) -- expose `compute_token_hash` public in telegram_service:** valid, but creates a duplicate API surface for a one-line stdlib call. Stdlib import is the simplest viable fix.
- **Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
- **Commit:** Folded into `d0aac5b` (Task 2 commit).

---

**Total deviations:** 4 auto-fixed (3 blocking ruff issues, 1 architectural cleanup acked by plan-checker).
**Impact on plan:** Public contracts (function signatures, return shapes, event names, Russian copy, importlinter compliance) are identical to the plan. Only internal noqa directives + the private hash-helper substitution differ. No scope creep.

## Issues Encountered

- Three RUF100 / RUF001 dance issues during ruff runs -- all auto-fixed inside the same task. None changed any externally-observable contract. Rationale captured in Deviations 1-3 above.
- Plan-checker's pre-flight warning about `_sha256_hex` reach-in (Deviation 4) was the only architecturally-meaningful deviation; resolved by stdlib substitution before Task 2 commit.

## Verification

| Check | Result |
|---|---|
| `from app.integrations.telegram.sender import send_otp_dm, SendResult` smoke import | PASS |
| `grep -q "Ваш код: {code}" sender.py` | PASS |
| `grep -q "Forbidden"` and `grep -q "BadRequest"` in sender.py | PASS |
| `! grep -E "^from app\.modules\.auth"` against handlers.py / sender.py / bot.py | PASS (zero matches across all three) |
| `! grep -E "^import app\.modules\.auth"` against handlers.py | PASS |
| `grep -q "class HandlerContext(NamedTuple)"` in handlers.py | PASS |
| `grep -q "Этот Telegram не привязан"` and `grep -q "Этот код уже использован"` in handlers.py | PASS |
| `grep -q "telegram_replay_attempt"` and `grep -q "telegram_dm_blocked"` in handlers.py | PASS |
| `! grep -E "^application = Application"` in bot.py | PASS (no module-level instance -- D-09) |
| `grep -q "def build_application"` and `grep -q "add_error_handler"` in bot.py | PASS |
| `from app.integrations.telegram.bot import build_application` smoke import | PASS |
| `! grep -rE 'arq\|enqueue\|@task\|Worker' app/integrations/telegram/` (D-12) | PASS (zero matches) |
| `grep -E "raise " app/integrations/telegram/sender.py` (D-07 sender never re-raises) | PASS (zero matches) |
| `uv run mypy --strict app/integrations/telegram/{sender,__init__,handlers,bot}.py` | Success: no issues found in 4 source files |
| `uv run mypy --strict app` (whole package, sanity) | Success: no issues found in 50 source files |
| `uv run ruff check app` (whole package, sanity) | All checks passed! |
| `uv run lint-imports` (3 importlinter contracts) | All 3 KEPT, 0 broken |

## Threat Flags

None new. Phase 7 STRIDE register entries T-07-21..T-07-27 are all addressed by this plan's implementation:

| Threat ID | Mitigation Status |
|---|---|
| T-07-21 (Tampering: malformed /start) | Mitigated by `_parse_start_token` strict validator -- shape mismatch returns silently with debug log |
| T-07-22 (Information Disclosure: bot-as-oracle) | Mitigated by D-04 fixed Russian DM identical for all unknown usernames; OtpCode untouched; /verify returns identical bot_not_started for "stranger" and "user never started bot" |
| T-07-23 (DoS: handler exception kills polling) | Mitigated by `_global_error_handler` registered via `application.add_error_handler` |
| T-07-24 (Information Disclosure: OTP in logs) | Mitigated -- raw_code never appears in any structlog event in handlers.py; sender logs nothing (relies on caller) |
| T-07-25 (Spoofing: first-bind race) | Mitigated by D-20 OtpAlreadyConsumed dispatch -- second /start with same token DMs "уже использован" + emits telegram_replay_attempt |
| T-07-26 (Tampering: bypass integrations perp modules via monkeypatch) | Accepted -- runtime monkeypatch is test-only (D-16); contract is static AST-level |
| T-07-27 (Repudiation: DM blocked unrecorded) | Mitigated by `telegram_dm_blocked` event with chat_id (Phase 8 audit_log latch) |

## User Setup Required

None for this plan. Wave 3 plan 07-07 (worker entry) will require `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BOT_USERNAME` env vars to be set (already documented in `.env.example` per 07-01 SUMMARY).

## Next Phase Readiness

- **07-04 (sibling Wave 2, telegram_service):** can implement `bind_and_issue(session, raw_token, chat_id, username) -> tuple[User, str, OtpCode]` (raises `TelegramUnknownAccount`), `commit_otp(session, otp_row, user, raw_code, chat_id) -> None`, and exception class `TelegramUnknownAccount`. Handler `start_handler` already imports nothing from `app.modules.auth` -- it consumes these via `ctx.telegram_service` (ModuleType). The handler dispatches `OtpAlreadyConsumed` by class-name string, so 07-04 is free to define that exception in `app/modules/auth/exceptions.py` (already shipped per 07-03) without breaking the handler.
- **07-07 (Wave 3, worker entry):** can `from app.integrations.telegram.bot import build_application`, `from app.integrations.telegram.handlers import HandlerContext, start_handler`, `from app.integrations.telegram import sender as telegram_sender`, then construct `HandlerContext(session_factory=sessionmaker, telegram_service=telegram_service, sender=telegram_sender)` and call `build_application(token=..., handlers=[("start", start_handler)], ctx=ctx)`. The `Application[Any, ...]` return type is compatible with `application.initialize()` / `start_polling()` lifecycle calls.
- **07-08 (Wave 3, handler tests):** can hand-build `SimpleNamespace` doubles for `update` / `context` (D-15 pattern) and call `await start_handler(update, context, ctx)` directly. The `stub_telegram_sender` fixture (D-16, defined in `tests/conftest.py` per 07-08 plan) monkeypatches `app.integrations.telegram.sender.send_otp_dm` to a recorder; the `HandlerContext.sender` reference is a ModuleType, so the monkeypatch is observed when the handler calls `ctx.sender.send_otp_dm(...)`.

## Self-Check: PASSED

- `apps/backend/app/integrations/telegram/__init__.py` -- FOUND, contains "Telegram integration -- python-telegram-bot 22 wiring" docstring.
- `apps/backend/app/integrations/telegram/sender.py` -- FOUND, contains `SendResult` dataclass + `send_otp_dm` + `send_text_dm`.
- `apps/backend/app/integrations/telegram/handlers.py` -- FOUND, contains `HandlerContext(NamedTuple)` + `start_handler` + Russian DM constants.
- `apps/backend/app/integrations/telegram/bot.py` -- FOUND, contains `build_application` factory + `_global_error_handler`.
- Commit `e40956b` (Task 1 sender + __init__) -- FOUND in `git log`.
- Commit `d0aac5b` (Task 2 handlers) -- FOUND in `git log`.
- Commit `58d009e` (Task 3 bot factory) -- FOUND in `git log`.

---

*Phase: 07-telegram-otp-channel*
*Plan: 05 of 8*
*Completed: 2026-05-02*
