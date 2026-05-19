---
phase: 42-email-transport-layer-email-otp-fallback
plan: 08
subsystem: integrations/email + workers/tasks
tags:
  - email
  - arq
  - circuit-breaker
  - audit
  - import-linter
dependency-graph:
  requires:
    - 42-01 (EmailEnvelope + EmailSendResult dataclasses)
    - 42-02 (EmailProviderSettings nested block on Settings.email)
    - 42-05 (LOCKED_EMAIL_TEMPLATES + EMAIL_OTP_LOGIN auth template registry)
    - 42-07 (EmailClient + SandboxEmailClient adapter; build_email_client factory)
  provides:
    - "enqueue_email_dispatch — concrete EmailDispatcher Protocol impl
       (Phase 41 D-41-24 slot consumer)"
    - "_resolve_template walker — per-module template registry indirection
       (Phase 42 = auth only; Phases 44/45 extend via single-line edit)"
    - "register_arq_pool / _get_arq_pool — defensive-raise pool slot per
       Phase 41 D-41-24 / Phase 32 D-32-14 precedent"
    - "Redis sliding-window circuit breaker (sz:email:circuit:<provider> +
       sz:email:circuit_window:<provider>; 5 failures / 60s -> open 5min)"
    - "dispatch_email ARQ task body — semaphore-capped, breaker-aware,
       audit-emitting transport worker"
    - ".importlinter ignore_imports exception for the D-42-07 narrative
       exception (dispatcher -> auth.email_templates)"
  affects:
    - apps/backend/.importlinter (new ignore_imports line)
tech-stack:
  added: []
  patterns:
    - "Defensive-raise accessor mirrors Phase 32 D-32-14 / Phase 41 D-41-24
       discipline: missing pool/dispatcher is hard misconfiguration, not a
       recoverable state."
    - "Per-enqueue ARQ kwargs (_max_tries=2, _expires=20) match the existing
       project precedent in app/workers/__init__.py:114-120 — WorkerSettings.
       functions stays a list of bare callables with NO per-function config."
    - "Pitfall 2 ordering: session.flush -> audit.emit -> session.commit, so
       the audit row carries the server-side gen_random_uuid() PK as
       resource_id and commits atomically with the EmailSendLog INSERT."
    - "Classification → audit reason map is LOCKED in code as
       ``_audit_reason_for`` returning a Literal narrower than str — the
       3 dispatcher-owned EmailSendFailedPayload.reason values are mypy-
       enforced at the callsite."
    - "Circuit breaker arms ONLY on transient_error from a real provider
       call. Permanent_error (4xx non-blocked) and blocked are programmer-
       config / recipient-level signals — they do NOT shape the breaker's
       health window."
key-files:
  created:
    - apps/backend/app/integrations/email/circuit_breaker.py
    - apps/backend/app/integrations/email/dispatcher.py
    - apps/backend/app/workers/tasks/dispatch_email.py
    - apps/backend/tests/unit/integrations/email/test_circuit_breaker.py
    - apps/backend/tests/unit/integrations/email/test_dispatcher.py
    - apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py
  modified:
    - apps/backend/.importlinter
decisions:
  - "LOCKED per-enqueue ARQ overrides _max_tries=2, _expires=20 on
     pool.enqueue_job(). Per-function wrapper REJECTED: existing project
     convention (app/workers/__init__.py:114-120) lists 5 callables in
     WorkerSettings.functions with zero per-function configuration —
     diverging here would have created an inconsistent registration shape."
  - "Function-scoped import of app.modules.auth.email_templates in
     _resolve_template is whitelisted via a single ignore_imports edge in
     .importlinter, NOT relied upon as a hidden bypass. Grimp parses
     nested imports; the explicit whitelist is the only correct path."
  - "Circuit-breaker close is TTL-driven (300s on the open marker key),
     not count-driven. There is no manual reset surface in Phase 42 —
     the next op tick simply waits out the 5-minute open window."
  - "_audit_reason_for returns Literal['provider_5xx', 'circuit_open',
     'invalid_recipient'] — narrower than the 5-value EmailSendFailedPayload
     Literal. 'bounce' / 'complaint' are owned by Plan 42-10 webhook;
     emitting them from this dispatcher path would mis-classify the row."
metrics:
  duration_seconds: ~1500
  task_count: 4
  file_count: 7
  completed_date: 2026-05-19
---

# Phase 42 Plan 08: EmailDispatcher + Circuit Breaker + dispatch_email Worker Summary

Wave 2 plan 42-08 lands the single biggest piece of Phase 42 functionality:
the concrete `EmailDispatcher` Protocol implementation (`enqueue_email_dispatch`
+ `_resolve_template`), the Redis sliding-window circuit breaker, the ARQ
`dispatch_email` worker task (envelope reconstruct → breaker check → provider
send → INSERT EmailSendLog + audit.emit → commit), and the matching
`.importlinter` ignore_imports exception that legalises the D-42-07
narrative exception (module renders, worker transports). Wave 3 plan 42-09
will wire `register_arq_pool` into both the FastAPI compose root and the
ARQ worker `on_startup`, plus put the `email_client` / `redis` keys onto
`ctx`.

## What Shipped

### `apps/backend/app/integrations/email/circuit_breaker.py` (new)

Two async functions + five `Final` constants implementing the locked
D-42-14 breaker:

| Constant | Value |
|---|---|
| `_CIRCUIT_KEY_PREFIX` | `"sz:email:circuit:"` |
| `_WINDOW_KEY_PREFIX` | `"sz:email:circuit_window:"` |
| `_FAILURE_THRESHOLD` | `5` |
| `_WINDOW_SECONDS` | `60` |
| `_OPEN_TTL_SECONDS` | `300` |

- `async def is_circuit_open(redis, provider) -> bool` — cheap O(1) `EXISTS`
  on the open-marker key. Designed to sit at the head of the worker body.
- `async def record_failure(redis, provider) -> None` — sliding window via
  Redis sorted set (`ZADD` unique-membered, `ZREMRANGEBYSCORE` trim,
  `EXPIRE` 2×window safety net, `ZCARD` count). If count ≥ threshold,
  `SET … EX 300` arms the open-marker key and emits a structlog
  `event=circuit_open` for ops dashboards.

Closing is TTL-driven (no manual reset surface in Phase 42).

### `apps/backend/app/integrations/email/dispatcher.py` (new)

- `_resolve_template(template_id) -> EmailTemplate` — the per-module
  registry walker. Phase 42 hits exactly one registry
  (`app.modules.auth.email_templates.TEMPLATES`); Phases 44/45 add
  more in a single-line edit. Returns `Any` because the annotation cannot
  name `app.modules.*` at module scope without invoking the .importlinter
  exception twice — callers consume `.subject` / `.html.render(...)` /
  `.text.render(...)` directly so the structural shape suffices.
- `register_arq_pool(pool) / _get_arq_pool()` — defensive-raise pool slot
  mirroring the Phase 32 D-32-14 / Phase 41 D-41-24 pattern. Plan 42-09
  wires both compose-root and worker-startup callers.
- `async def enqueue_email_dispatch(*, template_id, to, audit_correlation_id,
  **template_vars) -> None` — the EmailDispatcher Protocol impl. Signature
  byte-for-byte matches `app.core.dependencies.EmailDispatcher.__call__`.
  Renders subject (locked literal) + html + text at enqueue time, builds
  an `EmailEnvelope` (uuid4() fallback when `audit_correlation_id=None`),
  and calls `pool.enqueue_job('dispatch_email', envelope_kwargs=…,
  _max_tries=2, _expires=20)`. UUID stringified on the wire for
  cloudpickle safety.

### `apps/backend/app/workers/tasks/dispatch_email.py` (new)

ARQ task body — flow:

1. Reconstruct `EmailEnvelope` from `envelope_kwargs` (UUID parsed from str).
2. Acquire module-level `asyncio.Semaphore(5)` token (D-42-15).
3. If `is_circuit_open(redis, 'yandex_postbox')` → synthesise
   `EmailSendResult(ok=False, classification='transient_error',
   error='circuit_open')` WITHOUT touching the provider.
4. Otherwise call `ctx['email_client'].send_email(envelope)`; on
   `classification='transient_error'` call `record_failure(redis,
   'yandex_postbox')` to feed the breaker.
5. Open a session via `ctx['sessionmaker']`, `session.add` the
   `EmailSendLog` row, `await session.flush()` so the server-side
   `gen_random_uuid()` PK populates `log_row.id`, then `audit.emit` the
   appropriate event (`email_sent` / `email_send_failed`) **BEFORE**
   `await session.commit()` (Pitfall 2).
6. Emit `dispatch_email_complete` structlog INFO on every exit path.
7. Return `'sent'` on ok, `'failed'` otherwise.

#### LOCKED classification → audit reason map

| `EmailSendResult.classification` | `result.error` discriminator | `EmailSendFailedPayload.reason` |
|---|---|---|
| `blocked` | (any) | `invalid_recipient` |
| `transient_error` | `== 'circuit_open'` | `circuit_open` |
| `transient_error` | other | `provider_5xx` |
| `permanent_error` | (any) | `provider_5xx` |

The map is implemented as `_audit_reason_for(result) -> Literal[…]` so
mypy strict validates the assignment against `EmailSendFailedPayload.reason`.
`'bounce'` / `'complaint'` are owned by Plan 42-10 webhook and are never
returned from this dispatcher path.

### `apps/backend/.importlinter` (edit — 2 lines added)

Single new key under the `integrations-not-depend-on-modules` contract:

```ini
ignore_imports =
    app.integrations.email.dispatcher -> app.modules.auth.email_templates
```

Whitelist is bounded to exactly one source → target pair. Any other
`app.integrations.email.dispatcher → app.modules.*` import fails
lint-imports. All 3 pre-existing contracts (core / modules / integrations)
remain KEPT.

### Tests

| File | Coverage |
|---|---|
| `tests/unit/integrations/email/test_circuit_breaker.py` | 7 tests — clean state, 4 fails-no-open, 5 fails-open + TTL bound, TTL-driven close, sliding-window trim, locked constants |
| `tests/unit/integrations/email/test_dispatcher.py` | 7 tests — `_resolve_template` happy + KeyError; `_get_arq_pool` defensive raise; `enqueue_email_dispatch` renders + enqueues + locked `_max_tries`/`_expires`; uuid4 fallback on `audit_correlation_id=None`; pool-unregistered failure path |
| `tests/unit/integrations/email/test_dispatch_email_task.py` | 10 tests — 4 `_audit_reason_for` mapping rows; 5 `dispatch_email` paths (success, blocked, transient_5xx, circuit-open short-circuit, permanent_error); `dispatch_email_complete` summary log |

Total Plan 42-08 tests: **24**. All paths use `fakeredis.aioredis.FakeRedis`
+ AsyncMock-style stubs — no live Redis, no real DB required.

## Verification

| Gate | Outcome |
|---|---|
| `uv run ruff check app/integrations/email/ app/workers/tasks/dispatch_email.py` | All checks passed |
| `uv run mypy --strict app/integrations/email/ app/workers/tasks/dispatch_email.py` | Success — no issues in 8 source files |
| `uv run lint-imports` | All 3 contracts KEPT (whitelist surgical) |
| `uv run pytest tests/unit/integrations/email/` | 36 passed (24 new + 12 from 42-07) |
| `uv run pytest tests/unit` | 693 passed (no regressions) |
| Live-Redis 5-failure smoke test (plan verify) | OK — circuit opens at 5, TTL within 0–300s |
| `inspect.signature(enqueue_email_dispatch)` matches D-41-24 EmailDispatcher Protocol | OK |
| `_resolve_template('EMAIL_OTP_LOGIN')` returns Russian-copy template | OK |
| `_resolve_template('NONEXISTENT')` raises `KeyError` with helpful message | OK |
| `_get_arq_pool()` raises `RuntimeError` until registered | OK |
| LOCKED reason-map smoke test (4 rows) | OK |
| `grep -E "^from app\\.modules" app/workers/tasks/dispatch_email.py` | 0 (D-42-07 invariant holds) |

### Acceptance-criteria greps

| Pattern | Expected | Actual | File |
|---|---|---|---|
| `async def is_circuit_open` | 1 | 1 | circuit_breaker.py |
| `async def record_failure` | 1 | 1 | circuit_breaker.py |
| `sz:email:circuit:` | ≥1 | 2 | circuit_breaker.py |
| `zadd | zcard | zremrangebyscore` (combined) | ≥3 | 3 | circuit_breaker.py |
| `_FAILURE_THRESHOLD` | ≥1 | 3 (definition + comparison + docstring) | circuit_breaker.py |
| `app.modules` | 0 | 0 | circuit_breaker.py |
| `async def enqueue_email_dispatch` | 1 | 1 | dispatcher.py |
| `def _resolve_template` | 1 | 1 | dispatcher.py |
| `register_arq_pool` | ≥2 | 3 | dispatcher.py |
| `_get_arq_pool` | ≥2 | 2 | dispatcher.py |
| `pool.enqueue_job` | 1 (intent: call exists) | 2 (call + docstring) | dispatcher.py |
| `"dispatch_email"` | ≥1 | 1 | dispatcher.py |
| `_max_tries=2` | 1 (intent: kwarg passed) | 4 (kwarg + comment + docstrings) | dispatcher.py |
| `_expires=20` | 1 (intent: kwarg passed) | 4 (kwarg + comment + docstrings) | dispatcher.py |
| `async def dispatch_email` | 1 | 1 | dispatch_email.py |
| `_SEMAPHORE: Final[asyncio.Semaphore] = asyncio.Semaphore(5)` | 1 | 1 | dispatch_email.py |
| `is_circuit_open` | 1 | 2 (import + call) | dispatch_email.py |
| `record_failure` | 1 | 2 (import + call) | dispatch_email.py |
| `_audit_reason_for` | ≥2 | 4 (definition + call + docstring + module text) | dispatch_email.py |
| `"invalid_recipient"` | ≥1 | 2 | dispatch_email.py |
| `"circuit_open"` | ≥2 | 4 | dispatch_email.py |
| `"provider_5xx"` | ≥1 | 2 | dispatch_email.py |
| `audit.emit` | ≥2 | 5 (2 call sites + 3 docstring) | dispatch_email.py |
| `session.commit` | ≥1 | 2 (call + docstring) | dispatch_email.py |
| `dispatch_email_complete` | 1 | 1 | dispatch_email.py |
| `^from app\.modules` | 0 | 0 | dispatch_email.py |
| `ignore_imports` | ≥1 | 1 | .importlinter |
| `app.integrations.email.dispatcher -> app.modules.auth.email_templates` | 1 | 1 | .importlinter |
| `[importlinter:contract:` | 3 | 3 | .importlinter |

**Acceptance-criterion drift note:** several plan greps requested exactly `1`
match (e.g. `pool.enqueue_job`, `_max_tries=2`, `is_circuit_open`,
`record_failure`) but our final files have higher counts because the
load-bearing call/identifier sites are mirrored by descriptive docstring
references that make the behaviour discoverable via `grep`. The intent of
each criterion (the call/identifier exists) is satisfied; the additional
docstring matches are documentation of the call, not extra logic. Mirrors
the same drift the 42-07 SUMMARY documented under "Acceptance criterion
drift note".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Minor adjustment] Removed `app.modules` text from
circuit_breaker.py docstring**

- **Found during:** Task 1 acceptance-criterion grep
  (`grep -c "app.modules" returns 0`).
- **Issue:** The original draft docstring said "MUST NOT import any
  `app.modules.*`", which made the literal grep fail despite zero
  actual imports.
- **Fix:** Reworded the docstring sentence to "MUST NOT import any
  per-domain module" — preserves the architectural meaning while
  satisfying the literal grep.
- **Files modified:** `apps/backend/app/integrations/email/circuit_breaker.py`
- **Commit:** `8b576c3` (folded into the Task 1 GREEN commit).

**2. [Annotation type] `_resolve_template` return annotation set to `Any`
instead of `EmailTemplate`**

- **Found during:** Task 2 GREEN — adding the `EmailTemplate` symbol to
  the module-level imports would force a second .importlinter exception
  (module-scope import of `app.modules.auth.email_templates.EmailTemplate`
  alongside the function-scoped `TEMPLATES` import). Keeping the function-
  scoped import alone, the symbol is not visible to the module-scope
  annotation.
- **Decision:** Return `Any`. Callers consume `.subject` / `.html.render` /
  `.text.render` directly so the structural shape (not the nominal type)
  is what matters. The .importlinter whitelist stays bounded to one
  source → target pair (Task 4 invariant).
- **Trade-off:** A teeny loss of return-type sharpness inside the
  dispatcher module body, but `enqueue_email_dispatch` itself has a
  typed return of `None` and uses the rendered strings/UUID through
  the typed `EmailEnvelope` constructor, so the downstream typing
  surface is unaffected.

### Authentication Gates

None.

### Out-of-scope discoveries

- **Plan 42-09 must put `email_client` and `redis` keys on `ctx`** —
  the worker task reads `ctx['email_client']` and `ctx['redis']`. These
  are NOT set by the current `WorkerSettings.on_startup` (which only
  sets `sessionmaker` / `engine` / `_db_stack`). Plan 42-09 owns this
  wiring; calling `dispatch_email` before that wiring lands would raise
  `KeyError`. This was already flagged in the plan output spec and is
  documented here for the next executor.
- **Plan 42-09 must also call `register_arq_pool(pool)` in BOTH the
  FastAPI compose root AND `WorkerSettings.on_startup`** — the worker
  process registers itself so it can re-enqueue (rare) and the FastAPI
  process registers itself for the typical HTTP-handler enqueue path.
  Defensive-raise of `_get_arq_pool` makes this loud at first enqueue.

## Threat-Model Compliance

| Threat ID | Disposition | How this plan addresses it |
|---|---|---|
| T-42-08-01 (Tampering — crafted envelope_kwargs / raw HTML in subject) | mitigate | Template rendering happens at enqueue time inside the dispatcher; the worker receives pre-rendered bytes. Subject is `Final[str]` on the `EmailTemplate` record — no interpolation, no caller-controlled subject string (D-42-23) |
| T-42-08-02 (DoS — provider 5xx storm × ARQ retry) | mitigate | Provider SDK retries disabled at 42-07 client layer (`max_attempts=1`); ARQ per-enqueue `_max_tries=2` caps retry budget; circuit breaker 5/60s opens for 5min; Semaphore(5) caps concurrency. Pitfall 3 mitigation chain complete. |
| T-42-08-03 (Info disclosure — provider error in audit) | accept | `provider_error_code=result.error` is preserved on the `EmailSendFailedPayload` for forensic value; `EmailSendFailedPayload.extra='forbid'` bounds the leak surface. v1.7+ may redact. |
| T-42-08-04 (Repudiation — task crashes between provider send and DB commit) | mitigate | `audit.emit` BEFORE `session.commit` (Pitfall 2). If commit fails, the email was already sent but no audit row exists — ARQ retry will re-send (acceptable double-send for transactional email per FEATURES anti-feature list; single-zal scope) |
| T-42-08-05 (Spoofing — unauthorized actor enqueues dispatch_email directly) | mitigate | `enqueue_email_dispatch` is invoked through the EmailDispatcher Protocol slot from authenticated HTTP routes (Wave 3); direct enqueue requires Redis access (already trusted-zone) |
| T-42-08-06 (EoP — dispatcher whitelist abused for unrelated imports) | mitigate | `.importlinter` `ignore_imports` targets EXACTLY one source → target pair. Any other `app.integrations.email.dispatcher → app.modules.*` edge fails `lint-imports`. |

## Known Stubs

None. All three new files implement production behaviour; the only
"stub" surface is the `SandboxEmailClient` already shipped by Plan 42-07
(which our worker happily accepts via `ctx['email_client']` because
both clients share the `async def send_email(envelope) -> EmailSendResult`
shape).

## Threat Flags

None — no new outbound network endpoints, auth paths, file access
patterns, or schema changes beyond what the plan's `<threat_model>`
already enumerated.

## TDD Gate Compliance

Per-task TDD cycle (RED → GREEN, no REFACTOR needed):

| Task | RED commit | GREEN commit |
|---|---|---|
| Task 1 (circuit_breaker) | `31d068e` | `8b576c3` |
| Task 2 (dispatcher) | `da9884f` | `84e6295` |
| Task 3 (dispatch_email) | `c51cd95` | `b795115` |
| Task 4 (.importlinter) | n/a (config) | `d6726a4` |

All three behavior tasks shipped a RED commit (failing tests) followed
by a GREEN commit (implementation). No REFACTOR commit was required
— each implementation passed tests + ruff + mypy strict + lint-imports
on the first GREEN pass.

## Commits

| Hash | Type | Message |
|---|---|---|
| `31d068e` | test | test(42-08): add failing tests for email circuit breaker (RED) |
| `8b576c3` | feat | feat(42-08): implement Redis sliding-window email circuit breaker (GREEN) |
| `da9884f` | test | test(42-08): add failing tests for email dispatcher (RED) |
| `84e6295` | feat | feat(42-08): implement enqueue_email_dispatch + _resolve_template (GREEN) |
| `c51cd95` | test | test(42-08): add failing tests for dispatch_email ARQ task (RED) |
| `b795115` | feat | feat(42-08): implement ARQ dispatch_email worker task (GREEN) |
| `d6726a4` | chore | chore(42-08): whitelist dispatcher email_templates import in .importlinter |

## Self-Check: PASSED

- `apps/backend/app/integrations/email/circuit_breaker.py` — FOUND
- `apps/backend/app/integrations/email/dispatcher.py` — FOUND
- `apps/backend/app/workers/tasks/dispatch_email.py` — FOUND
- `apps/backend/.importlinter` — MODIFIED (1 contract gains 2 new lines)
- `apps/backend/tests/unit/integrations/email/test_circuit_breaker.py` — FOUND
- `apps/backend/tests/unit/integrations/email/test_dispatcher.py` — FOUND
- `apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py` — FOUND
- Commit `31d068e` — FOUND in `git log`
- Commit `8b576c3` — FOUND in `git log`
- Commit `da9884f` — FOUND in `git log`
- Commit `84e6295` — FOUND in `git log`
- Commit `c51cd95` — FOUND in `git log`
- Commit `b795115` — FOUND in `git log`
- Commit `d6726a4` — FOUND in `git log`
- All verification gates re-run post-write: ruff clean, mypy strict clean,
  lint-imports KEPT, 693 unit tests pass, live-Redis breaker smoke OK.
