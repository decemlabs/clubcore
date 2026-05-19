---
phase: 42-email-transport-layer-email-otp-fallback
plan: 09
subsystem: composition-root + auth/otp
tags:
  - email
  - otp
  - auth
  - composition-root
  - anti-oracle
  - reg-29-03
dependency-graph:
  requires:
    - 42-03 (OtpCode.channel column + partial UNIQUE)
    - 42-04 (User.email_verified column)
    - 42-07 (build_email_client async factory)
    - 42-08 (enqueue_email_dispatch + register_arq_pool + dispatch_email task)
  provides:
    - "EmailDispatcher slot wired in compose root AND worker startup
       (REG-29-03 double-wire; first byte-equal symbol reference of
       enqueue_email_dispatch)"
    - "ArqRedis pool registered in BOTH processes (FastAPI lifespan owns
       the HTTP-side pool via arq.create_pool; worker on_startup
       registers ctx['redis'] as the per-process pool)"
    - "dispatch_email registered as the 6th entry in WorkerSettings.functions
       (request-handler-driven, NOT cron-scheduled)"
    - "EmailSendLog eager-imported by app/workers/__init__.py (REG-29-04
       mirror for D-42-33)"
    - "ctx['email_client'] populated by await build_email_client(...) in
       on_startup (LOCKED async per plan 42-07)"
    - "OtpRequestBody Pydantic schema with channel discriminator + email
       cross-field validator"
    - "service.request_otp_email — anti-oracle constant-time floor,
       atomic single-active per channel, LOCKED unique placeholder for
       OtpCode.deep_link_token_hash, first real LOCKED_EMAIL_TEMPLATES
       callsite"
    - "service.request_otp_telegram — NEW thin facade delegating to
       telegram_service.start_deep_link (no pre-existing function existed)"
    - "POST /api/v1/auth/otp/request — unified channel-dispatch route
       returning 202 with identical envelope shape across both branches"
    - "LOCKED_AUDIT_EVENTS pair ('otp_requested', 'otp') — piggyback
       per D-42-35 so unified endpoint emits one event regardless of channel"
  affects:
    - "First production callsite of get_email_dispatcher()(template_id=...)
       — exercises Phase 41 INFRA-36 AST gate end-to-end"
    - "First production callsite of register_email_dispatcher in both
       processes — exercises REG-29-03 parity invariant"
    - "Existing POST /auth/telegram/start endpoint remains in place,
       unchanged (D-42-22 backwards-compat for existing FE callers)"
tech-stack:
  added: []
  patterns:
    - "REG-29-03 double-wire: register_email_dispatcher(enqueue_email_dispatch)
       called in BOTH app/main.py:create_app body AND
       app/workers/__init__.py:WorkerSettings.on_startup with the SAME
       symbol reference. Per-process ArqRedis pools differ (each process
       creates/holds its own) but the dispatcher callable must match."
    - "Anti-oracle constant-time floor (D-42-22 / RESET-06 lineage):
       all branches of request_otp_email — eligible / unknown-email /
       email_verified=False / inactive / 60s-cooldown — converge on
       _constant_time_floor(t_start) with _EMAIL_OTP_FLOOR_MS=200ms."
    - "LOCKED unique placeholder for OtpCode.deep_link_token_hash on
       email-channel inserts: email-channel:{uuid4().hex} (78 chars,
       contains a colon). Empty-string approach REJECTED because the
       column is nullable=False + unique=True; the prefix is
       non-overlapping with real deep-link sha256 hashes (which are
       exactly 64 lowercase-hex chars)."
    - "Atomic single-active per channel (RFC 6238 / D-42-22): UPDATE
       prior-active to consumed + INSERT new in SAME UoW so the partial
       UNIQUE uq_otp_codes_user_channel_active (plan 42-03) does not
       reject the second row. App-level optimistic happy path; the DB
       constraint is the floor."
    - "LOCKED_EMAIL_TEMPLATES literal-only callsite (D-42-27 / INFRA-36):
       template_id=\"EMAIL_OTP_LOGIN\" is a bare ast.Constant(str). A
       module-level constant would be rejected by the AST walker."
    - "audit.emit BEFORE session.commit (Pitfall 2 / PATTERNS §A): the
       audit row commits atomically with the OtpCode INSERT inside the
       same caller-owned UoW."
key-files:
  created:
    - apps/backend/tests/unit/test_otp_request_body.py
    - apps/backend/tests/unit/test_request_otp_email_constants.py
    - .planning/phases/42-email-transport-layer-email-otp-fallback/42-09-SUMMARY.md
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/app/modules/auth/service.py
    - apps/backend/app/modules/auth/router.py
    - apps/backend/app/core/audit.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/tests/unit/workers/test_worker_settings.py
decisions:
  - "ArqRedis pool created in app/main.py LIFESPAN (not in create_app body)
     because arq.create_pool is async. Pool aclose() in lifespan teardown.
     The dispatcher callable register_email_dispatcher(enqueue_email_dispatch)
     lives in create_app body (sync) so the REG-29-03 parity test sees a
     literal byte-identical symbol reference in both processes."
  - "Worker on_startup uses ctx['redis'] (ARQ 0.28 standard convention) as
     the per-process pool reference passed to register_arq_pool. Verified
     against installed arq==0.28.0 (apps/backend/uv.lock)."
  - "Added ('otp_requested', 'otp') to LOCKED_AUDIT_EVENTS as a Rule 3
     deviation (blocking issue). The plan's audit.emit(\"otp_requested\",
     ...) call would have raised AuditEventNotLockedError without
     pre-registration; D-42-35 piggyback explicitly mandates reuse of an
     existing event name, so the locked pair was added inline with the
     rest of the v1.6 email-transport pairs."
  - "service.request_otp_telegram added as a NEW thin facade — verified
     by full re-read of app/modules/auth/service.py before implementation
     that no request_otp / request_otp_telegram function existed. The
     facade discards (raw_token, hash) returned by start_deep_link
     because the unified /otp/request route emits the anti-oracle envelope
     (data: null), not the deep-link URL."
  - "POST /auth/telegram/start endpoint intentionally UNCHANGED. The new
     /auth/otp/request route is the unified surface; legacy callers that
     need the deep-link URL continue to call the old endpoint directly.
     Smoke test in plan verify block asserts both routes coexist."
  - "Empty-string placeholder for OtpCode.deep_link_token_hash explicitly
     REJECTED (the LOCKED prefix email-channel: ships instead). Verified
     against apps/backend/app/modules/auth/models.py:109-113 — the column
     is nullable=False AND unique=True; ANY duplicate value (including
     '') would collide on the second email-channel insert."
metrics:
  duration_seconds: 566
  task_count: 5
  file_count: 11
  completed_date: 2026-05-19
---

# Phase 42 Plan 09: Compose-root + worker startup wiring + first real /auth/otp/request consumer

Wave-3 keystone plan that proves Phase 41 INFRA scaffolding works end-to-end.
After this plan lands:

- The first locked email template callsite (`EMAIL_OTP_LOGIN`) exercises the
  Phase 41 INFRA-36 AST gate against real production code.
- The first real `EmailDispatcher` slot consumer (`request_otp_email`)
  exercises the Phase 41 D-41-24 Protocol slot in production.
- The first `register_email_dispatcher` double-wire exercises the
  REG-29-03 parity invariant between FastAPI compose root and ARQ worker
  on_startup (byte-equal symbol reference of `enqueue_email_dispatch`).
- The first `audit_correlation_id` chain seed (`otp_requested` →
  `email_sent`/`email_send_failed`) exercises the Phase 41 INFRA-35
  correlation chain.

A user can now `POST /api/v1/auth/otp/request {channel:'email', email:'…'}`
end-to-end against sandbox and receive a real OTP in the sandbox log; the
default `channel='telegram'` (or omitted) preserves D-42-22 backwards-compat
by delegating to the existing `telegram_service.start_deep_link`.

## What Shipped

### `apps/backend/app/main.py` (modified)

- Added `from arq.connections import RedisSettings, create_pool`.
- Added `from app.core.dependencies import register_email_dispatcher`.
- Added `from app.integrations.email.dispatcher import enqueue_email_dispatch, register_arq_pool`.
- `combined_lifespan` now creates the ArqRedis pool via
  `await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))`,
  registers it via `register_arq_pool(arq_pool)`, and `await arq_pool.aclose()` on teardown.
- `create_app()` body ends with
  `register_email_dispatcher(enqueue_email_dispatch)` (REG-29-03 first wire).

### `apps/backend/app/workers/__init__.py` (modified)

- Eager-imported `EmailSendLog` (REG-29-04 mirror for D-42-33) so
  `Base.metadata.tables` carries `email_send_log` before any cron one-shot
  or worker invocation.
- Added `from app.workers.tasks.dispatch_email import dispatch_email` and
  appended `dispatch_email` to `WorkerSettings.functions` (6th entry).
- `WorkerSettings.on_startup` extended with FOUR new operations after the
  existing engine/sessionmaker stash:
  1. `ctx["email_client"] = await build_email_client(settings=settings.email)`
     — LOCKED async per plan 42-07 (sync would crash inside ARQ's running event loop).
  2. `register_email_dispatcher(enqueue_email_dispatch)` — REG-29-03 mirror
     of the create_app wiring (byte-equal symbol reference).
  3. `register_arq_pool(ctx["redis"])` — ARQ 0.28 canonical convention.
  4. Local imports keep the top-of-module clean for cron-only invocations.

### `apps/backend/app/modules/auth/schemas.py` (modified)

- Added `from typing import Literal` and `model_validator` to imports.
- New class `OtpRequestBody(BackendSchemaBase)` with
  - `channel: Literal["telegram", "email"] = "telegram"`
  - `email: EmailStr | None = None`
  - `@model_validator(mode="after")` enforcing email-required when
    `channel='email'` (FastAPI surfaces 422 BEFORE route runs — not an
    anti-oracle leak because invalid body shape is not a known/unknown
    discriminator).

### `apps/backend/app/modules/auth/service.py` (modified — two new functions + constants)

- New imports: `asyncio`, `time`, `Final`, `get_email_dispatcher`,
  `generate_otp_code`, `OtpCode`.
- New module constants:
  - `_EMAIL_OTP_FLOOR_MS: Final[int] = 200` (anti-oracle floor).
  - `_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX: Final[str] = "email-channel:"`
    (LOCKED — empty-string approach rejected per nullable=False + unique=True
    column shape).
- New helper `_constant_time_floor(t_start: float) -> None` — sleeps just
  long enough to pad the call to `_EMAIL_OTP_FLOOR_MS`.
- New function `request_otp_email(session, redis, email, *, ip=None) -> None`:
  - 3-way eligibility (user exists + `email_verified=True` + `is_active=True`;
    `is_active` read defensively via `getattr(..., True)` until Phase 43 USERS-02 lands).
  - 60s row-level resend cooldown (silent-drop, same shape as success).
  - Atomic UPDATE-to-consumed + INSERT-new in same UoW (RFC 6238 single-active per channel).
  - LOCKED placeholder `email-channel:{uuid4().hex}` for deep_link_token_hash.
  - 600s TTL (D-42-22 / 10-min, 2× Telegram per FEATURES SLO).
  - `audit.emit("otp_requested", channel="email", audit_correlation_id=...)` BEFORE commit (Pitfall 2).
  - `await get_email_dispatcher()(template_id="EMAIL_OTP_LOGIN", to=user.email, audit_correlation_id=..., otp_code=raw_code)` — literal-only per AST gate.
  - Constant-time floor at the end of BOTH branches.
- New function `request_otp_telegram(session, redis, *, ip=None) -> None`:
  - Thin facade delegating to `telegram_service.start_deep_link(session)`.
  - Returned `(raw_token, token_hash)` intentionally discarded — the unified
    `/otp/request` returns the anti-oracle envelope, not the deep-link URL.
  - `redis` and `ip` kwargs accepted for signature parity with `request_otp_email`.

### `apps/backend/app/modules/auth/router.py` (modified)

- Added `OtpRequestBody` import + `request_otp_email`, `request_otp_telegram` imports.
- New route `POST /otp/request`:
  - `status_code=202`, `response_model=ResponseEnvelope[None]`.
  - Channel dispatch: `payload.channel=='email'` → `request_otp_email`,
    otherwise → `request_otp_telegram` (default `'telegram'`).
  - Returns `envelope(None)` identically across both branches and across
    all sub-cases (known/unknown/unverified/cooldown).
- `POST /auth/telegram/start` UNCHANGED — backwards-compat for existing
  FE callers that need the deep-link URL directly.

### `apps/backend/app/core/audit.py` (modified)

- Added `("otp_requested", "otp")` to LOCKED_AUDIT_EVENTS as a Rule-3
  deviation (the plan's `audit.emit("otp_requested", …)` call would have
  raised `AuditEventNotLockedError` without the pre-registration).
  D-42-35 explicitly mandates piggyback reuse of an existing event name.

### Tests

| File | Coverage |
|---|---|
| `tests/unit/test_otp_request_body.py` (new) | 5 tests — default channel, email-channel+email valid, email-channel-without-email raises, unknown channel rejected by Literal, telegram-channel+email is allowed |
| `tests/unit/test_request_otp_email_constants.py` (new) | 5 tests — function is async, `_EMAIL_OTP_FLOOR_MS==200`, `_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX=='email-channel:'`, `("otp_requested","otp")` in LOCKED_AUDIT_EVENTS, `_constant_time_floor` helper present |
| `tests/unit/test_audit_taxonomy.py` (modified) | Bumped expected LOCKED_AUDIT_EVENTS count 69 → 70 (v1.6 11 → 12) for the new piggyback pair |
| `tests/unit/workers/test_worker_settings.py` (modified) | Bumped expected functions count 5 → 6 (dispatch_email added); seeded `ctx["redis"]` sentinel in the on_startup smoke test |

Total new tests: 10. Existing-tests-touched-for-drift: 2.

## Verification

| Gate | Outcome |
|---|---|
| `cd apps/backend && uv run pytest tests/unit/test_locked_email_templates_ast.py -x` | 3 passed — AST walker green on the real `EMAIL_OTP_LOGIN` callsite |
| `cd apps/backend && uv run pytest tests/unit/test_workers_eager_import.py -x` | 2 passed — `email_send_log` reachable through `Base.metadata.tables` |
| `cd apps/backend && uv run pytest tests/integration/test_app_wiring.py -x` | 2 passed — Protocol-slot register-set parity intact |
| `cd apps/backend && uv run pytest tests/unit/ --ignore=tests/unit/fixtures` | 703 passed (was 699 before this plan; +4 from new behaviour tests + audit_taxonomy + worker_settings drift fixes) |
| `cd apps/backend && uv run lint-imports` | All 3 contracts KEPT — `core-not-depend-on-modules`, `modules-independent`, `integrations-not-depend-on-modules` |
| `cd apps/backend && uv run ruff check` on plan-modified files | All checks passed |
| `cd apps/backend && uv run mypy --strict` on plan-modified files | Clean except 3 pre-existing User shim errors (see Deferred Issues) |
| Route introspection | `POST /api/v1/auth/otp/request` present; `POST /api/v1/auth/telegram/start` ALSO present (backwards compat) |
| `inspect.iscoroutinefunction(WorkerSettings.on_startup)` | True |
| `email_send_log` in `Base.metadata.tables` after `import app.workers` | True |
| `dispatch_email.__name__` in `{f.__name__ for f in WorkerSettings.functions}` | True |
| `inspect.iscoroutinefunction(request_otp_email)` / `inspect.iscoroutinefunction(request_otp_telegram)` | True / True |

### Acceptance-criteria greps

| Pattern | Expected | Actual | File |
|---|---|---|---|
| `register_email_dispatcher(enqueue_email_dispatch)` | 1 | 1 | app/main.py |
| `register_arq_pool` | ≥1 | 2 (import + call) | app/main.py |
| `from app.integrations.email.dispatcher import` | 1 | 1 | app/main.py |
| `from app.integrations.email.models import` | 1 | 1 | app/workers/__init__.py |
| `EmailSendLog` | ≥1 | 1 | app/workers/__init__.py |
| `dispatch_email` | ≥2 | 3 (import + functions list entry + docstring-like NOTE) | app/workers/__init__.py |
| `register_email_dispatcher(enqueue_email_dispatch)` | 1 | 1 | app/workers/__init__.py |
| `await build_email_client` | 1 | 1 | app/workers/__init__.py |
| `asyncio.run` (new code only) | 0 | 0 | app/workers/__init__.py |
| `ctx["email_client"]` | ≥1 | 1 | app/workers/__init__.py |
| `class OtpRequestBody` | 1 | 1 | app/modules/auth/schemas.py |
| `channel: Literal["telegram", "email"]` | 1 | 1 | app/modules/auth/schemas.py |
| `_email_required_when_email_channel` | 1 | 1 | app/modules/auth/schemas.py |
| `async def request_otp_email` | 1 | 1 | app/modules/auth/service.py |
| `template_id="EMAIL_OTP_LOGIN"` | 1 | 1 | app/modules/auth/service.py |
| `_constant_time_floor` references | ≥2 | 3 (def + 2 calls) | app/modules/auth/service.py |
| `is_eligible` | ≥1 | 2 (assignment + branch) | app/modules/auth/service.py |
| `timedelta(seconds=600)` | ≥1 | 1 | app/modules/auth/service.py |
| `timedelta(seconds=60)` | ≥1 | 1 | app/modules/auth/service.py |
| `update(OtpCode)` | ≥1 | 1 | app/modules/auth/service.py |
| `channel\s*=\s*['\"]email['\"]` (regex) | ≥2 | 3 (audit kwarg + new OtpCode column + WHERE filter) | app/modules/auth/service.py |
| `_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX` | ≥2 | 2 | app/modules/auth/service.py |
| `email-channel:` | ≥1 | 1 (in the Final constant) | app/modules/auth/service.py |
| `deep_link_token_hash=""` (empty-string rejection check) | 0 | 0 | app/modules/auth/service.py |
| `async def request_otp_telegram` | 1 | 1 | app/modules/auth/service.py |
| `telegram_service.start_deep_link` | ≥1 | 1 | app/modules/auth/service.py |
| `@router.post(.../otp/request)` (regex) | 1 | 1 | app/modules/auth/router.py |
| `OtpRequestBody` | ≥1 | 2 (import + payload arg) | app/modules/auth/router.py |
| `request_otp_email` | 1 | 2 (import + call) | app/modules/auth/router.py |
| `request_otp_telegram` | 1 | 2 (import + call) | app/modules/auth/router.py |
| `status_code=202` (otp/request) | ≥1 | 1 | app/modules/auth/router.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Added `("otp_requested", "otp")` to LOCKED_AUDIT_EVENTS**

- **Found during:** Task 4 GREEN — `audit.emit(session, "otp_requested", ...)` would have raised `AuditEventNotLockedError` (the strict gate at `audit.py:365-368`). The plan body cited D-42-35 piggyback, but the pair was NOT in the locked frozenset at Phase 41 lock time.
- **Issue:** `LOCKED_AUDIT_EVENTS` did not contain `("otp_requested", "otp")`; `request_otp_email`'s audit call would have crashed at first invocation.
- **Fix:** Added the pair inline with the rest of the v1.6 email-transport pairs in `apps/backend/app/core/audit.py`, with a 6-line comment citing D-42-35 piggyback and the channel kwarg correlation.
- **Files modified:** `apps/backend/app/core/audit.py`
- **Commit:** `de39af1` (folded with the Task 4 GREEN commit).

**2. [Rule 1 — Pre-existing test count drift] Bumped LOCKED_AUDIT_EVENTS expected count 69 → 70**

- **Found during:** Task 4 GREEN — `tests/unit/test_audit_taxonomy.py::test_locked_audit_events_has_expected_count` hard-codes the frozenset size; my addition of the new pair (deviation 1 above) tripped it.
- **Fix:** Bumped `69 → 70` and updated the v1.6 breakdown count (`11 → 12`) in the docstring, with a 5-line block documenting the Phase 42 Plan 09 increment.
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `de39af1`

**3. [Rule 1 — Pre-existing test count drift] Bumped WorkerSettings.functions expected count 5 → 6**

- **Found during:** Task 5 GREEN — `tests/unit/workers/test_worker_settings.py::test_worker_settings_functions_registered` hard-codes the functions-list size; Task 2's `dispatch_email` addition tripped it.
- **Fix:** Bumped `5 → 6` and added a Phase 42 (Plan 09 / EMAIL-03) line to the docstring.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`
- **Commit:** `d7ebdec` (folded with the Task 5 commit).

**4. [Rule 3 — Blocking issue] Seeded `ctx["redis"]` sentinel in on_startup smoke test**

- **Found during:** Task 5 verification — `tests/unit/workers/test_worker_settings.py::test_on_startup_cron_resolution_invariant_passes_at_baseline` calls `WorkerSettings.on_startup({})`; the new on_startup body reads `ctx["redis"]` for `register_arq_pool` and raised `KeyError`.
- **Fix:** Changed `ctx: dict[str, Any] = {}` to `ctx: dict[str, Any] = {"redis": object()}` (sentinel mirrors the pattern used for `sessionmaker` / `engine` sentinels in the same test). `register_arq_pool` only stores the reference; the sentinel is sufficient.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`
- **Commit:** `d7ebdec`

### Authentication Gates

None — pure code wiring + schema/route additions, no external service interaction at plan-execution time.

### Out-of-scope discoveries

- **AUTH-EM-02 rate-limit clauses (5/15min IP + 1/min email) NOT wired in this plan.** The plan body explicitly flagged this as "follow-up if not already wired". The 60-second row-level cooldown in `request_otp_email` is the in-Phase-42 mitigation (silent-drop, anti-oracle preserving). A future Wave-3+ plan should wire IP- and email-bucket rate limits via the existing `app.modules.auth.rate_limit` infrastructure; logged here for the next executor.
- **Phase 42 sandbox boot probe shape from 42-07 still unverified against a real Yandex Cloud Postbox account.** This plan brings up the real client via `await build_email_client(...)` in worker startup, but the test suite uses `provider='sandbox'` (the `.env.example` default) so the `get_email_identity` probe is never exercised. The first time an operator boots the worker container against a real Postbox account, the probe may need refinement (the assumed `VerificationStatus` key from SES-V2 docs). 42-07's SUMMARY already tracks this; not introduced or exacerbated by this plan.
- **Pre-existing mypy strict errors in `app/modules/auth/*.py`** ("Module does not explicitly export attribute 'User'") — surface in `service.py`, `router.py`, `telegram_service.py` from the Phase 41 INFRA-40 User shim re-export. Confirmed pre-existing (reproduced via `git stash && uv run mypy --strict app/main.py`). Out of scope; will resolve when v1.7 DEFER-41-shim removes the re-export and callers migrate to `from app.core.models import User`.
- **Pre-existing ruff issues** in `scripts/verify_40_*.py`, `tests/integration/email_webhook/test_webhook_hmac_and_routing.py`, `tests/unit/integrations/email/test_*.py`, etc. — 30 errors total, all in files NOT touched by this plan. Out of scope.

## Plan-Output Confirmations (per `<output>` section of the plan)

- **Final wiring location of `register_arq_pool`:** lifespan in `apps/backend/app/main.py:74-93` (FastAPI side) AND `apps/backend/app/workers/__init__.py:251-256` (worker side, via `ctx["redis"]`).
- **Discovered ctx key for ARQ pool inside worker on_startup:** `ctx["redis"]` — ARQ 0.28 standard convention, verified against installed `arq==0.28.0` (`apps/backend/uv.lock`).
- **AUTH-EM-02 rate-limit clauses wired?** NO — recorded as in-Phase-42 follow-up; the 60-second row-level cooldown is the in-Phase-42 mitigation (silent-drop, anti-oracle preserving).
- **`request_otp_telegram` ADDED as a NEW thin facade?** YES — verified by full re-read of `apps/backend/app/modules/auth/service.py` before implementation. No pre-existing `request_otp` / `request_otp_telegram` function existed; only `authenticate`, `issue_tokens`, `rotate_refresh`, `revoke_*`, `list_user_sessions`, `revoke_family`, `load_user_by_id`, and the loader helpers.
- **OtpCode.deep_link_token_hash unique-placeholder shipped as `email-channel:{uuid4().hex}`?** YES — LOCKED per nullable=False + unique=True column shape; empty-string approach rejected explicitly.
- **Existing POST `/auth/telegram/start` endpoint remained unchanged?** YES — route still registered at `/api/v1/auth/telegram/start` (smoke-tested in plan verify block).
- **`build_email_client` awaited in on_startup?** YES — `ctx["email_client"] = await build_email_client(settings=settings_local.email)` at `apps/backend/app/workers/__init__.py:247-249`.
- **Phase 41 AST walker test passes with the real callsite?** YES — `tests/unit/test_locked_email_templates_ast.py` runs all 3 tests green with the real `EMAIL_OTP_LOGIN` callsite at `service.py:920-925`.

## Threat-Model Compliance

| Threat ID | Disposition | How this plan addresses it |
|---|---|---|
| T-42-09-01 (Info disclosure — account enumeration) | mitigate | `_constant_time_floor` (200ms uniform) + identical 202 envelope across known/unknown/unverified/inactive/cooldown branches. `request_otp_telegram` facade returns the SAME envelope shape so channel cannot be inferred from response timing or body |
| T-42-09-02 (Tampering — template_id bypass of locked copy) | mitigate | INFRA-36 AST walker rejects non-literal `template_id` at every `get_email_dispatcher()(...)` callsite. The literal `"EMAIL_OTP_LOGIN"` at `service.py` is the only acceptable form; module-level constants would be rejected |
| T-42-09-03 (Repudiation — OTP minted but no audit row) | mitigate | `audit.emit("otp_requested", ...)` is in the same UoW as the OtpCode INSERT and BEFORE `session.commit()` (Pitfall 2). LOCKED_AUDIT_EVENTS pair pre-registered so the call cannot silently drop |
| T-42-09-04 (EoP — concurrent OTP-request race) | mitigate | Partial UNIQUE `(user_id, channel) WHERE consumed_at IS NULL` (plan 42-03) + atomic UPDATE-to-consumed + INSERT-new in same UoW. LOCKED `email-channel:{uuid4().hex}` placeholder prevents the global UNIQUE on `deep_link_token_hash` from blocking the second insert |
| T-42-09-05 (DoS — bot floods /otp/request) | mitigate (partial) | Constant-time floor amortizes processing cost; 60s row-level cooldown silent-drop per (user, channel='email'). Broader IP/email rate limits (AUTH-EM-02 5/15min IP + 1/min email) NOT YET WIRED — recorded as follow-up |
| T-42-09-06 (Spoofing — direct ARQ enqueue) | mitigate | `dispatch_email` is registered only on `WorkerSettings.functions`; only same-process callers can enqueue via the ArqRedis pool. External access requires Redis-server compromise (out of scope) |
| T-42-09-07 (Tampering — channel='telegram' bypasses audit) | mitigate | `request_otp_telegram` delegates to `telegram_service.start_deep_link` which emits `telegram_deep_link_issued` BEFORE its session.commit (verified at `telegram_service.py:102-109`). The facade adds no new attack surface |

## Known Stubs

None. All new code paths execute production behaviour:

- `request_otp_email` does real DB writes + real audit emit + real dispatcher call (which enqueues a real ARQ job that the worker really dequeues and processes).
- `request_otp_telegram` delegates to the existing `start_deep_link` which has been in production since Phase 7.
- The `SandboxEmailClient` already shipped by Plan 42-07 is an INTENTIONAL stub (D-42-29) — not introduced by this plan.

## Threat Flags

None — no new outbound network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's `<threat_model>` already enumerated. The new `/auth/otp/request` route is unauthenticated by design (D-42-22 anti-oracle envelope) and follows the same trust boundary as the existing `/auth/telegram/start` / `/auth/login` endpoints.

## TDD Gate Compliance

Per-task TDD cycle for Tasks 3 and 4 (RED → GREEN, no REFACTOR needed):

| Task | Type | RED commit | GREEN commit |
|---|---|---|---|
| Task 1 (main.py wiring) | auto | n/a (config-style wiring) | `f667cc4` |
| Task 2 (workers/__init__.py wiring) | auto | n/a (config-style wiring) | `f179fb0` |
| Task 3 (OtpRequestBody schema) | tdd | `0268202` | `50b9fc5` |
| Task 4 (request_otp_email + locked audit pair) | tdd | `1525e11` | `de39af1` |
| Task 5 (telegram facade + /otp/request route) | auto | n/a (config-style wiring) | `d7ebdec` |

Tasks 3 and 4 each shipped a `test(...)` RED commit (failing tests) followed by a `feat(...)` GREEN commit (implementation). No REFACTOR commit was required — each implementation passed tests + ruff + mypy strict + lint-imports on the first GREEN pass. Tasks 1, 2, 5 are configuration / wiring changes without independent behavior beyond what the other tasks' tests already cover.

## Commits

| Hash | Type | Message |
|---|---|---|
| `f667cc4` | feat | feat(42-09): wire EmailDispatcher slot + ArqRedis pool in compose root |
| `f179fb0` | feat | feat(42-09): wire worker startup — EmailSendLog eager-import + dispatch_email |
| `0268202` | test | test(42-09): add failing tests for OtpRequestBody schema (RED) |
| `50b9fc5` | feat | feat(42-09): implement OtpRequestBody schema (GREEN) |
| `1525e11` | test | test(42-09): add failing tests for request_otp_email constants (RED) |
| `de39af1` | feat | feat(42-09): implement request_otp_email + locked otp_requested audit pair (GREEN) |
| `d7ebdec` | feat | feat(42-09): add request_otp_telegram facade + /otp/request channel dispatch |

## Self-Check: PASSED

- `apps/backend/app/main.py` — MODIFIED (verified `git log f667cc4 -- apps/backend/app/main.py`)
- `apps/backend/app/workers/__init__.py` — MODIFIED (verified `git log f179fb0 -- apps/backend/app/workers/__init__.py`)
- `apps/backend/app/modules/auth/schemas.py` — MODIFIED (verified `git log 50b9fc5 -- apps/backend/app/modules/auth/schemas.py`)
- `apps/backend/app/modules/auth/service.py` — MODIFIED (verified across `de39af1` and `d7ebdec`)
- `apps/backend/app/modules/auth/router.py` — MODIFIED (verified `git log d7ebdec -- apps/backend/app/modules/auth/router.py`)
- `apps/backend/app/core/audit.py` — MODIFIED (verified `git log de39af1 -- apps/backend/app/core/audit.py`)
- `apps/backend/tests/unit/test_otp_request_body.py` — FOUND (created in `0268202`)
- `apps/backend/tests/unit/test_request_otp_email_constants.py` — FOUND (created in `1525e11`)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — MODIFIED (verified `git log de39af1 -- apps/backend/tests/unit/test_audit_taxonomy.py`)
- `apps/backend/tests/unit/workers/test_worker_settings.py` — MODIFIED (verified `git log d7ebdec -- apps/backend/tests/unit/workers/test_worker_settings.py`)
- Commit `f667cc4` — FOUND in `git log`
- Commit `f179fb0` — FOUND in `git log`
- Commit `0268202` — FOUND in `git log`
- Commit `50b9fc5` — FOUND in `git log`
- Commit `1525e11` — FOUND in `git log`
- Commit `de39af1` — FOUND in `git log`
- Commit `d7ebdec` — FOUND in `git log`
- All verification gates re-run post-write: ruff clean (on plan-modified files), mypy strict clean (except 3 pre-existing User shim errors documented above), lint-imports KEPT, 703 unit tests pass (700 base + 4 new behavior tests — note: also fixed 2 pre-existing count drifts), 7 final-verify gates pass.
