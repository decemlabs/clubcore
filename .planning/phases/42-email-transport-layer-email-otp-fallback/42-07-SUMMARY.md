---
phase: 42-email-transport-layer-email-otp-fallback
plan: 07
subsystem: integrations/email
tags:
  - email
  - integrations
  - aioboto3
  - sandbox
  - factory
dependency-graph:
  requires:
    - 42-01 (EmailEnvelope + EmailSendResult dataclasses)
    - 42-02 (EmailProviderSettings nested block on Settings.email)
  provides:
    - "EmailClient adapter (async Yandex Cloud Postbox SES-V2 transport)"
    - "SandboxEmailClient stub (D-42-29; logs + ok without provider)"
    - "async build_email_client(*, settings) factory (D-42-29 + D-42-30)"
  affects:
    - apps/backend/pyproject.toml (aioboto3 dep + mypy override for aioboto3/botocore)
tech-stack:
  added:
    - "aioboto3 13.4.0 (pinned >=13.0,<14)"
    - "botocore (transitive via aioboto3) — Config + ClientError"
  patterns:
    - "Classified-failure outbound boundary (mirrors telegram.sender.send_otp_dm
       PATTERNS.md §3): every transport outcome is a value-typed EmailSendResult,
       never a raised exception."
    - "LOCKED async factory divergence from telegram.bot.build_bot (sync): the
       non-sandbox branch awaits a real network probe at boot."
    - "Drop-in transport stubbing via SandboxEmailClient — same async send_email
       signature as the real adapter; the factory swaps based on
       EmailProviderSettings without callers branching on type."
key-files:
  created:
    - apps/backend/app/integrations/email/factory.py
    - apps/backend/tests/unit/integrations/email/__init__.py
    - apps/backend/tests/unit/integrations/email/test_client.py
    - apps/backend/tests/unit/integrations/email/test_factory.py
  modified:
    - apps/backend/app/integrations/email/client.py
    - apps/backend/pyproject.toml
    - apps/backend/uv.lock
decisions:
  - "Factory shipped as `async def build_email_client` (LOCKED in plan).
     No convention-discovery deferred — divergence from sync telegram.bot.build_bot
     is intentional and documented in the module docstring."
  - "mypy overrides for aioboto3.* + botocore.* (ignore_missing_imports). Avoids
     pulling heavy boto3-stubs (which generate types for ~400 AWS services) into
     dev install when we only need sesv2."
  - "Non-sandbox path is exercised in integration tier (plan 42-09 wiring) not
     unit tests — exercising a real aioboto3 client requires either a live
     Postbox account or a moto/stub harness that does not exist in this repo
     yet. Plan 42-09 will add wiring tests that fake the session."
metrics:
  duration_seconds: ~900
  task_count: 3
  file_count: 7
  completed_date: 2026-05-19
---

# Phase 42 Plan 07: Yandex Postbox SES-V2 async adapter + factory Summary

Real async Yandex Cloud Postbox SES-V2 adapter (`EmailClient`) plus its no-op
sandbox twin (`SandboxEmailClient`) replaced the placeholder at
`app/integrations/email/client.py`, and a LOCKED-`async def` factory
(`build_email_client`) landed at `app/integrations/email/factory.py` with the
boot-time `/domains` probe wired in. aioboto3 13.4.0 pinned. The transport
seam Wave 3 will plug into is now stable.

## What Shipped

### `apps/backend/app/integrations/email/client.py` (replaced placeholder)

Two classes — same `async def send_email(envelope: EmailEnvelope) -> EmailSendResult`
shape so the factory returns either as a drop-in:

| Class | Behavior |
|---|---|
| `EmailClient` | Holds an `aioboto3.Session` + `endpoint_url` + `from_address`. Opens a fresh `sesv2` client per call with `Config(retries={'max_attempts': 1})` (D-42-02). Calls `send_email` with the SES-V2 `Content.Simple.{Subject, Body.Html, Body.Text}` shape against `FromEmailAddress=self._from_address` and `Destination.ToAddresses=[envelope.to]`. Classifies every outcome (see table below). NEVER re-raises. |
| `SandboxEmailClient` | Logs envelope at INFO (`to`, `subject`, `text_preview` first 80 chars, `template_id`); returns `EmailSendResult(ok=True, classification='ok', provider_message_id=f"sandbox-{uuid4()}")`. Zero outbound calls. |

#### Classification mapping (locked)

| Outcome | `classification` | `ok` | `provider_message_id` | Notes |
|---|---|---|---|---|
| `send_email` returns dict with `MessageId` | `"ok"` | `True` | `MessageId` value | Success branch |
| `ClientError` Code ∈ `{"MessageRejected", "AccountSendingPausedException"}` | `"blocked"` | `False` | `None` | Terminal — do NOT retry |
| `ClientError` HTTP 5xx (any code) | `"transient_error"` | `False` | `None` | ARQ retry can recover |
| `ClientError` HTTP 4xx non-blocked | `"permanent_error"` | `False` | `None` | Operator-alert; no retry |
| Bare `Exception` (network/timeout/etc) | `"transient_error"` | `False` | `None` | Defensive catch-all |

The "never re-raises transport errors" invariant from `send_otp_dm`
(PATTERNS.md §3) carries verbatim — the ARQ dispatcher (plan 42-08)
switches on `classification`, not on exception types.

### `apps/backend/app/integrations/email/factory.py` (new)

`async def build_email_client(*, settings: EmailProviderSettings) -> EmailClient | SandboxEmailClient`

- **Sandbox path (D-42-29):** `provider == "sandbox" OR sandbox_mode` →
  return `SandboxEmailClient()`. Zero I/O; the awaited call returns
  immediately.
- **Non-sandbox path (D-42-30):** construct `aioboto3.Session` with
  secret-unwrapped creds, then await `sesv2.get_email_identity(
  EmailIdentity=settings.from_domain)` inside an `async with` client
  context. If `VerificationStatus != 'Success'` → `RuntimeError` at boot.
  Otherwise return `EmailClient(session=, endpoint_url=, from_address=)`.
- **Fresh per call** — no module-level cache. aiohttp pools owned by
  aioboto3 sessions therefore don't leak across worker container restarts.
- **No `asyncio.run` anywhere** — verified by grep (count 0). The function
  is natively coroutine-shaped; callers await it from FastAPI's async
  lifespan and ARQ's `on_startup` (both async).

### `apps/backend/pyproject.toml`

- New dependency line: `"aioboto3>=13.0,<14"` (D-42-02). Resolves to
  aioboto3 13.4.0 in `uv.lock`.
- New `[[tool.mypy.overrides]]` block:
  ```toml
  [[tool.mypy.overrides]]
  module = ["aioboto3.*", "botocore.*"]
  ignore_missing_imports = true
  ```
  Rationale: aioboto3 and botocore lack `py.typed`. `boto3-stubs` exists
  but generates types for ~400 AWS services we don't use. Our own
  `EmailClient` code stays fully `mypy --strict`-checked; only third-party
  imports are suppressed.

### Test scaffolding

| File | Coverage |
|---|---|
| `tests/unit/integrations/email/__init__.py` | empty marker |
| `tests/unit/integrations/email/test_client.py` | 9 tests — sandbox ok-path, sandbox log content (via stdout capture, structlog target), and the 5-branch classification chain plus the "never re-raises" invariant |
| `tests/unit/integrations/email/test_factory.py` | 3 tests — pins the `inspect.iscoroutinefunction(build_email_client) is True` invariant, and both `provider='sandbox'` and `sandbox_mode=True` branches return `SandboxEmailClient` |

## Verification

| Gate | Outcome |
|---|---|
| `uv run ruff check app/integrations/email/` | All checks passed (5 files) |
| `uv run mypy --strict app/integrations/email/` | Success: no issues found in 5 source files |
| `uv run lint-imports` | `integrations must not import modules` — KEPT (contract 3 intact) |
| `uv run pytest tests/unit/integrations/email/` | 12 passed |
| `uv run pytest tests/unit -x --ignore=tests/unit/fixtures` | 669 passed (no regressions) |
| Inline smoke: `inspect.iscoroutinefunction(build_email_client)` | True |
| Inline smoke: sandbox path returns `SandboxEmailClient` without I/O | OK |
| Inline smoke: sandbox `provider_message_id` starts with `sandbox-` | OK |

### Acceptance-criteria greps

| Pattern | Expected | Actual | File |
|---|---|---|---|
| `class EmailClient` | 1 | 1 | client.py |
| `class SandboxEmailClient` | 1 | 1 | client.py |
| `async def send_email` | ≥2 | 3 (incl. test imports) | client.py |
| `classification="blocked"` | ≥1 | 1 | client.py |
| `classification="transient_error"` | ≥1 | 2 | client.py |
| `classification="permanent_error"` | ≥1 | 1 | client.py |
| `max_attempts` | ≥1 | 2 (Config arg + docstring) | client.py |
| `app.modules` | 0 | 0 | client.py |
| `async def build_email_client` | 1 | 1 | factory.py |
| sync form `def build_email_client` | 0 | 0 | factory.py |
| `asyncio.run` | 0 | 0 | factory.py |
| `import asyncio` | 0 | 0 | factory.py |
| `SandboxEmailClient` | ≥1 | 4 (import + 2 returns + docstring) | factory.py |
| `get_email_identity` | 1 (intent: call exists) | 2 (call + docstring text) | factory.py |
| `VerificationStatus` | 1 | 2 (read + docstring) | factory.py |
| `max_attempts` | 1 | 2 (Config arg + docstring) | factory.py |
| `app.modules` | 0 | 0 | factory.py |

**Acceptance criterion drift note:** The plan asked for exactly `1` match
on `get_email_identity` and `VerificationStatus`, but our final
factory.py has `2` of each because the load-bearing call sites are
mirrored by descriptive docstring references that make the probe semantics
discoverable via `grep`. The intent of the criterion (probe call must
exist) is satisfied; the additional docstring matches are documentation
of the call, not extra logic. Same applies to `max_attempts` in both
files. This is not a deviation from plan behavior, only from the literal
grep counts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Test logic bug] Fixed sandbox-log assertion to capture stdout**

- **Found during:** Task 2 GREEN — RED test
  `test_sandbox_logs_envelope_at_info` failed because it inspected
  `caplog` (stdlib logging records) while structlog in this codebase
  writes to stdout.
- **Fix:** Rewrote the test to use `capsys.readouterr()` and assert
  `envelope.to`, `subject`, `template_id`, and a slice of `text` appear
  in stdout. The implementation was already correct (verified via
  inspecting captured stdout in the failure trace).
- **Files modified:** `apps/backend/tests/unit/integrations/email/test_client.py`
- **Commit:** `f41e004` (Task 2 GREEN — folded with the implementation
  commit since the test was already RED-staged and GREEN required both
  the impl + the test correction to converge)

**2. [Rule 3 — Blocking issue] Add mypy override for aioboto3.* + botocore.***

- **Found during:** Task 2 GREEN — `mypy --strict` rejected `from
  botocore.config import Config` and `from botocore.exceptions import
  ClientError` with `import-untyped`. aioboto3 + botocore ship without
  `py.typed` markers.
- **Fix:** Added `[[tool.mypy.overrides]]` block in `apps/backend/pyproject.toml`
  for `["aioboto3.*", "botocore.*"]` with `ignore_missing_imports = true`.
  Documented rationale in a comment so a future contributor knows why we
  didn't pull `boto3-stubs` (it generates types for ~400 AWS services we
  don't use).
- **Files modified:** `apps/backend/pyproject.toml`
- **Commit:** `f41e004`

**3. [Rule 2 — Defensive type narrowing] Explicit None-check for AWS creds**

- **Found during:** Task 3 — mypy --strict required narrowing `settings.aws_access_key_id`
  / `settings.aws_secret_access_key` from `SecretStr | None` to `SecretStr`
  before calling `.get_secret_value()`. The EmailProviderSettings validator
  already enforces non-None for non-sandbox provider, but mypy can't see
  the runtime invariant.
- **Fix:** Added an explicit `if settings.aws_access_key_id is None or
  settings.aws_secret_access_key is None: raise RuntimeError(...)` guard
  immediately before the `aioboto3.Session(...)` construction. The error
  message notes the validator should have rejected the config earlier, so
  this is a defensive belt-and-suspenders.
- **Files modified:** `apps/backend/app/integrations/email/factory.py`
- **Commit:** `51c9fe5`

### Authentication Gates

None.

### Out-of-scope discoveries

**Settings.env_nested_delimiter still not wired (heads-up from 42-02 SUMMARY):**
Plan 42-02 explicitly deferred adding `env_nested_delimiter='__'` on
`Settings.model_config`. This plan (42-07) does NOT need env-var overrides
of nested `email.*` fields because:

- Sandbox boot uses defaults from `EmailProviderSettings()` instance — no
  env vars required for `web` / `arq` containers to start.
- Non-sandbox boot will require operators to set creds, but those can be
  set by passing `Settings(email=EmailProviderSettings(...))` in a
  bootstrap hook, OR by adding `env_nested_delimiter` in a future small
  plan if `EMAIL__PROVIDER=yandex_postbox` syntax is preferred.

Decision: NOT wiring `env_nested_delimiter` here — it changes env-var
loading globally for ANY future nested block (Telegram, Yandex Cloud
billing, etc.) and deserves its own focused plan. This is consistent with
42-02's deferral rationale and was confirmed in the heads-up from the
upstream 42-02 SUMMARY.

## Threat-Model Compliance

| Threat ID | Disposition | How this plan addresses it |
|---|---|---|
| T-42-07-01 (MITM endpoint_url) | mitigate | `endpoint_url` default `https://postbox.cloud.yandex.net` from `EmailProviderSettings` (plan 42-02); aioboto3 TLS verification default-on; boot probe will refuse to start if the endpoint is unreachable or returns unexpected shape |
| T-42-07-02 (creds leak via structlog) | mitigate | Creds wrapped in `SecretStr` in settings; `.get_secret_value()` is called only once at `aioboto3.Session(...)` construction site; structlog logger emits only `to`, `subject`, `template_id`, `provider_message_id`, `error_code`, `http_status` — never credentials |
| T-42-07-03 (5xx + retry storm DoS) | mitigate | `Config(retries={'max_attempts': 1})` disables boto3 retries (verified in both client.py and factory.py — 4 total matches across `Config(retries=...)` call sites + docstrings). ARQ owns retry; plan 42-08 adds the breaker on top. |
| T-42-07-04 (unverified from_domain delivers) | mitigate | Boot-time `get_email_identity(EmailIdentity=settings.from_domain)` probe asserts `VerificationStatus == 'Success'` and raises `RuntimeError` on miss. App cannot start with an unverified domain. |
| T-42-07-05 (failed sends leave no trace) | mitigate | Classification taxonomy (ok / blocked / transient_error / permanent_error) maps every transport outcome into `EmailSendResult`; structlog emits `email_send_ok`, `email_send_blocked`, `email_send_transient_error`, `email_send_permanent_error` events with `to` + `template_id` + `error_code` + `http_status`. Plan 42-08 will fold these into `email_send_log` rows. |

No new threat surface introduced beyond what the plan's `<threat_model>`
already enumerated.

## Known Stubs

- `SandboxEmailClient` is an INTENTIONAL stub (D-42-29) — it returns
  `EmailSendResult.ok` without making any provider call so dev / CI /
  preview environments can exercise the full dispatch + audit pipeline
  without burning provider quota or leaking real emails. The factory
  selects it via `settings.provider == 'sandbox'` OR `settings.sandbox_mode`,
  both of which are sandbox-safe defaults today. Wave 3 plan 42-09
  ARQ-on_startup wiring is the next consumer.

No accidental stubs (no hardcoded empty data flowing to UI, no "TODO"
placeholders in production code paths).

## Threat Flags

None — no new outbound network endpoints, auth paths, file access
patterns, or schema changes beyond what the plan's `<threat_model>`
already enumerated.

## Open Question (downstream)

The plan body explicitly flags that the `get_email_identity` probe shape
may need refinement once a real Yandex Cloud Postbox is exercised — open
question: does Postbox return the `VerificationStatus` field verbatim
via SES-V2 `get_email_identity`, or under a slightly different key (e.g.
`Status`, `IdentityVerificationStatus`)? Our implementation assumes
verbatim per SES-V2 docs and reads `resp.get("VerificationStatus")`. If
Postbox surfaces the value under a different key the boot probe will
always raise `RuntimeError` (status comes back as `None`).

This will surface in plan 42-09 (worker wiring) the first time an
operator boots the worker container against a real Postbox account, OR
in Phase 46 VER-12 if a verification harness is added before plan 42-09.
Tracked here so the next executor knows where to look.

## Commits

| Hash | Type | Message |
|---|---|---|
| `c9aafd9` | chore | chore(42-07): pin aioboto3>=13.0,<14 for Yandex Postbox SES-V2 adapter |
| `7adb317` | test | test(42-07): add failing tests for EmailClient + SandboxEmailClient (RED) |
| `f41e004` | feat | feat(42-07): implement EmailClient + SandboxEmailClient adapters (GREEN) |
| `51c9fe5` | feat | feat(42-07): add async build_email_client factory + boot-time domain probe |

## Self-Check: PASSED

- `apps/backend/app/integrations/email/client.py` — FOUND (replaced placeholder)
- `apps/backend/app/integrations/email/factory.py` — FOUND (new)
- `apps/backend/pyproject.toml` — MODIFIED (aioboto3 dep + mypy override)
- `apps/backend/uv.lock` — MODIFIED (aioboto3 13.4.0 resolved)
- `apps/backend/tests/unit/integrations/email/__init__.py` — FOUND
- `apps/backend/tests/unit/integrations/email/test_client.py` — FOUND
- `apps/backend/tests/unit/integrations/email/test_factory.py` — FOUND
- Commit `c9aafd9` — FOUND in `git log`
- Commit `7adb317` — FOUND in `git log`
- Commit `f41e004` — FOUND in `git log`
- Commit `51c9fe5` — FOUND in `git log`
- All gates re-verified post-write (ruff + mypy --strict + lint-imports + 669 unit tests)
