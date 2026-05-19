---
phase: 42-email-transport-layer-email-otp-fallback
reviewed: 2026-05-19T00:00:00Z
depth: standard
files_reviewed: 45
files_reviewed_list:
  - apps/backend/.importlinter
  - apps/backend/alembic/env.py
  - apps/backend/alembic/versions/0026_email_send_log.py
  - apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py
  - apps/backend/alembic/versions/0028_users_email_verified.py
  - apps/backend/app/api/v1/_internal/__init__.py
  - apps/backend/app/api/v1/_internal/email/__init__.py
  - apps/backend/app/api/v1/_internal/email/router.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/config.py
  - apps/backend/app/core/models.py
  - apps/backend/app/integrations/email/circuit_breaker.py
  - apps/backend/app/integrations/email/client.py
  - apps/backend/app/integrations/email/dispatcher.py
  - apps/backend/app/integrations/email/factory.py
  - apps/backend/app/integrations/email/models.py
  - apps/backend/app/integrations/email/types.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/auth/email_templates.py
  - apps/backend/app/modules/auth/models.py
  - apps/backend/app/modules/auth/router.py
  - apps/backend/app/modules/auth/schemas.py
  - apps/backend/app/modules/auth/service.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/tasks/dispatch_email.py
  - apps/backend/infra/dns/sportzal.ru.zone
  - apps/backend/pyproject.toml
  - apps/backend/ruff.toml
  - apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py
  - apps/backend/tests/integration/email_webhook/__init__.py
  - apps/backend/tests/integration/email_webhook/test_webhook_hmac_and_routing.py
  - apps/backend/tests/integration/test_app_wiring.py
  - apps/backend/tests/integration/test_route_introspection.py
  - apps/backend/tests/unit/integrations/email/__init__.py
  - apps/backend/tests/unit/integrations/email/test_circuit_breaker.py
  - apps/backend/tests/unit/integrations/email/test_client.py
  - apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py
  - apps/backend/tests/unit/integrations/email/test_dispatcher.py
  - apps/backend/tests/unit/integrations/email/test_factory.py
  - apps/backend/tests/unit/test_audit_taxonomy.py
  - apps/backend/tests/unit/test_locked_email_templates_ast.py
  - apps/backend/tests/unit/test_otp_request_body.py
  - apps/backend/tests/unit/test_request_otp_email_constants.py
  - apps/backend/tests/unit/test_workers_eager_import.py
  - apps/backend/tests/unit/workers/test_worker_settings.py
findings:
  critical: 4
  warning: 7
  info: 4
  total: 15
status: issues_found
---

# Phase 42: Code Review Report

**Reviewed:** 2026-05-19
**Depth:** standard
**Files Reviewed:** 45
**Status:** issues_found

## Summary

Phase 42 ships an email transport layer with a real Yandex Cloud Postbox adapter, an ARQ `dispatch_email` task, a Redis sliding-window circuit breaker, a HMAC-signed bounce/complaint webhook under `/api/v1/_internal/email/`, three migrations (`email_send_log`, `otp_codes.channel`, `users.email_verified`), an email-channel OTP fallback on `POST /api/v1/auth/otp/request`, and a fair amount of invariant pytest gate scaffolding.

The transport boundary, circuit-breaker primitives, webhook 401 gate (HMAC-before-parse), anti-oracle 200 ms latency floor in `request_otp_email`, and OTP body Pydantic discriminator are all wired competently. Several non-trivial defects nevertheless slipped past unit tests because the tests mock `audit.emit` itself rather than exercise it.

The most consequential defect: `app/workers/tasks/dispatch_email.py` calls `audit.emit(..., payload=EmailSentPayload(...))` — i.e. it passes the Pydantic model as a single kwarg named `payload`. But `audit.emit`'s signature is `**payload: Any` which means the captured payload kwarg-dict will be `{"payload": <EmailSentPayload>}`, not the flattened model fields. The downstream `schema.model_validate(payload)` will then raise `ValidationError("Extra inputs are not permitted")` on the `payload` key, and the JSONB column will store an unserialisable Pydantic instance. Every production `dispatch_email` job crashes at runtime — the unit tests miss it because they monkey-patch `audit.emit` directly. This is CR-01 below.

The other criticals: the Telegram facade of `/auth/otp/request` (`request_otp_telegram`) has NO anti-oracle latency floor — case B in the AUTH-EM-04 test is intentionally excluded from timing parity, but anyone calling `channel='telegram'` with a known-vs-unknown account still gets a timing oracle on `start_deep_link`'s DB write path; the circuit-breaker sliding-window operations are not pipelined and lose increments under concurrent worker failure bursts; and migration 0027 ships a partial-UNIQUE that will fail to create on any existing deployment where two stale `consumed_at IS NULL` rows exist for the same `(user_id, 'telegram')` pair.

Quality concerns: `EmailSendLog.bounce_type` accepts free-form text (no CHECK), the webhook handler's UPDATE happens before the audit emit but commits AFTER both — but the audit emit boundary doesn't see `actor_email_snapshot` lookup race against ARQ ctx redis pool reuse, and the dispatcher's "ctx['redis'] IS the ArqRedis pool" assumption is unsafe across ARQ versions.

## Critical Issues

### CR-01: `dispatch_email` passes `payload=<Model>` as a single kwarg — `audit.emit` rejects it, every email-send audit emit crashes

**File:** `apps/backend/app/workers/tasks/dispatch_email.py:160-188`
**Issue:**
The ARQ task calls `audit.emit` like this:

```python
await audit.emit(
    session,
    "email_sent",
    actor_user_id=None,
    resource_type="email_send_log",
    resource_id=log_row.id,
    payload=EmailSentPayload(  # <-- ONE kwarg whose value is the model
        audit_correlation_id=envelope.audit_correlation_id,
        template_id=envelope.template_id,
        to_email=envelope.to,
        provider_message_id=result.provider_message_id,
    ),
)
```

`audit.emit`'s real signature (`apps/backend/app/core/audit.py:299-308`) is:

```python
async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    actor_email_snapshot: str | None = None,
    **payload: Any,
) -> None:
```

`**payload` collects every excess kwarg into a dict. The dispatcher's call therefore produces `payload == {"payload": <EmailSentPayload instance>}`. Then `emit()` runs:

```python
schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))
if schema is not None:
    schema.model_validate(payload)   # validates {"payload": <Model>} against EmailSentPayload
```

`EmailSentPayload` has `model_config = ConfigDict(extra="forbid")` (`audit_payloads.py:478`) and four required fields (`audit_correlation_id`, `template_id`, `to_email`, `provider_message_id`). The single-key `{"payload": ...}` input fails validation on the `extra='forbid'` rule AND on every missing required field. Result: `pydantic.ValidationError` propagates out of `audit.emit` → `dispatch_email` task crashes → ARQ retries (`_max_tries=2`) → second crash → job marked failed. **Zero `email_sent` audit rows are ever written; every send appears in `email_send_log` as `status='sent'` but no audit trail exists.**

The same bug appears on the failure branch at line 175-188 with `EmailSendFailedPayload`.

Why the unit tests do not catch this: `tests/unit/integrations/email/test_dispatch_email_task.py:167-170` monkey-patches `app.workers.tasks.dispatch_email.audit.emit` with a plain `fake_emit` that records `kwargs` and never invokes the real validator. The test then asserts `kwargs["payload"]` is the model instance — which it is, at the wrong layer.

The webhook router (`app/api/v1/_internal/email/router.py:181-197`) uses the correct flattened-kwarg pattern (`reason=emit_reason, provider_error_code=None, ...`) — that pattern is also the project convention in `apps/backend/app/modules/memberships/service.py` and is documented at `audit_payloads.py:356-360` ("**payload: Arbitrary JSONB-serialisable kwargs"). The dispatcher is the only callsite using `payload=Model(...)`.

**Fix:**
Flatten the kwargs (mirror the webhook's pattern at lines 181-197 of the router) and stringify the UUID at the JSONB boundary (the existing column is JSONB; raw UUID is not JSON-serialisable through `json.dumps`):

```python
if result.ok:
    await audit.emit(
        session,
        "email_sent",
        actor_user_id=None,
        resource_type="email_send_log",
        resource_id=log_row.id,
        audit_correlation_id=str(envelope.audit_correlation_id),
        template_id=envelope.template_id,
        to_email=envelope.to,
        provider_message_id=result.provider_message_id,
    )
else:
    reason = _audit_reason_for(result)
    await audit.emit(
        session,
        "email_send_failed",
        actor_user_id=None,
        resource_type="email_send_log",
        resource_id=log_row.id,
        audit_correlation_id=str(envelope.audit_correlation_id),
        template_id=envelope.template_id,
        to_email=envelope.to,
        reason=reason,
        provider_error_code=result.error,
    )
```

Additionally, fix the unit tests in `test_dispatch_email_task.py` to either (a) exercise the real `audit.emit` (preferred — let the Pydantic validator run), or (b) assert on the flattened kwargs (`kwargs["reason"]`, `kwargs["template_id"]`, …) instead of `kwargs["payload"].reason`. Without (a), the bug class is invisible to future regressions.

### CR-02: `request_otp_telegram` has NO anti-oracle latency floor — known-vs-unknown telegram-channel timing oracle

**File:** `apps/backend/app/modules/auth/service.py:972-1002`
**Issue:**
The unified `/auth/otp/request` endpoint dispatches by channel (`router.py:401-410`). The email branch calls `request_otp_email` which DOES apply `_constant_time_floor(t_start)` on both branches (`service.py:900`, `:969`). The telegram branch (`channel='telegram'`, the default) calls `request_otp_telegram`, which is documented as a "thin facade" but contains no latency normalisation at all:

```python
async def request_otp_telegram(
    session: AsyncSession,
    redis: Redis,
    *,
    ip: str | None = None,
) -> None:
    ...
    _ = redis
    _ = ip
    _raw_token, _token_hash = await telegram_service.start_deep_link(session)
```

`telegram_service.start_deep_link` issues an INSERT + audit.emit + commit unconditionally — it does not even consult `email` (the unified endpoint suppresses the deep-link URL). That means an attacker probing `POST /auth/otp/request` with `{}` (telegram default) will see a different wall-clock distribution than `POST /auth/otp/request` with `{"email": "nonexistent@x.y"}` (email branch unknown user) and ALSO a different distribution than `{"channel": "email", "email": "verified@x.y"}` (email branch success). The body envelope shape is identical across all of these (per the endpoint contract), but the timing leaks the channel AND, more subtly, leaks that the operator went through the new endpoint rather than `POST /auth/telegram/start`.

The PR's own AUTH-EM-04 anti-oracle integration test (`tests/integration/auth/test_otp_email_anti_oracle.py:147-154`) explicitly excludes case B (telegram-default) from the body-parity / timing-parity assertions with the comment *"Body shape across channels intentionally diverges (different log-emission paths) so case B is NOT included in the body-parity / timing-parity assertions."* The "intentionally diverges" claim is wrong — the endpoint returns `envelope(None)` in both cases (`router.py:411`), so the response body IS identical. The exclusion masks the timing leak rather than ruling it out.

This contradicts D-42-22's "anti-oracle uniformity" spec, which calls out that *every* sub-case of `/auth/otp/request` (regardless of channel) must converge on the same floor.

**Fix:**
Apply the constant-time floor on the telegram facade too, using the same `_constant_time_floor` helper:

```python
async def request_otp_telegram(
    session: AsyncSession,
    redis: Redis,
    *,
    ip: str | None = None,
) -> None:
    t_start = time.perf_counter()
    from app.modules.auth import telegram_service
    _ = redis
    _ = ip
    try:
        _raw_token, _token_hash = await telegram_service.start_deep_link(session)
    finally:
        await _constant_time_floor(t_start)
```

The `try/finally` is mandatory — if `start_deep_link` raises (e.g. on DB conflict), the unprotected exception propagation also leaks timing. Extend `test_otp_email_anti_oracle.py` to include case B in the timing-parity assertion (alongside cases A/C/D); fix the misleading comment that claims body shape diverges.

### CR-03: Circuit-breaker `record_failure` is not atomic — concurrent workers lose increments and can fail to open

**File:** `apps/backend/app/integrations/email/circuit_breaker.py:59-98`
**Issue:**
`record_failure` executes five sequential `await` operations against Redis with no MULTI/EXEC, no pipeline, and no Lua script:

```python
await redis.zadd(window_key, {f"{now_ms}-{uuid4().hex[:8]}": now_ms})  # step 1
await redis.zremrangebyscore(window_key, 0, now_ms - _WINDOW_SECONDS * 1000)  # step 2
await redis.expire(window_key, _WINDOW_SECONDS * 2)  # step 3
count = await redis.zcard(window_key)  # step 4
if count >= _FAILURE_THRESHOLD:
    await redis.set(f"{_CIRCUIT_KEY_PREFIX}{provider}", "1", ex=_OPEN_TTL_SECONDS)  # step 5
```

Concurrent worker semantics under the `Semaphore(5)` cap (D-42-15) — and across multiple worker container replicas — produce two distinct hazards:

1. **Lost-trim race.** Worker A runs `zadd` at t=0; worker B runs `zadd` at t=1ms; worker B's subsequent `zremrangebyscore` runs BEFORE A's, then A's `zremrangebyscore` runs and trims to the same point. Both ZCARDs then read the same trimmed view. This is benign on a near-empty set but pathological at the threshold boundary: in the 5-failure / 60s window, if 5 transient failures arrive in rapid succession across 5 worker tasks, the ZCARD reads can interleave with each other's `zremrangebyscore` calls and any one worker can read `count = 4` even though the actual cardinality is 5, so the breaker fails to open at the exact moment it should. The probability is low but non-zero, and the failure mode is exactly the operational signal the breaker exists to catch.

2. **TTL eviction during increment.** The `expire` call (step 3) refreshes the TTL on the sorted-set key to 120s. If step 1's zadd was the FIRST entry in the window — the sorted set was previously empty and TTL'd out — step 3's `expire` may race against Redis's TTL eviction worker. The redis-py async client does not retry on key-missing during `expire` (it returns 0 silently). The next failure recreates the key without a TTL — the open-marker key gets set at step 5 with TTL=300s but the window key now persists forever, slowly accumulating stale entries (mitigated by `zremrangebyscore` but only once a fresh failure arrives in this provider's window).

The unit test `test_record_failure_trims_stale_window_entries` (test_circuit_breaker.py:106-118) uses single-threaded fakeredis so neither hazard surfaces.

**Fix:**
Use a single Redis pipeline with `transaction=True` (MULTI/EXEC), or, better, a Lua script via `redis.eval(...)` that does ZADD + ZREMRANGEBYSCORE + ZCARD + (conditional) SET atomically. Pipeline form:

```python
async def record_failure(redis: Redis, provider: str) -> None:
    window_key = f"{_WINDOW_KEY_PREFIX}{provider}"
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}-{uuid4().hex[:8]}"
    cutoff = now_ms - _WINDOW_SECONDS * 1000

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zadd(window_key, {member: now_ms})
        pipe.zremrangebyscore(window_key, 0, cutoff)
        pipe.expire(window_key, _WINDOW_SECONDS * 2)
        pipe.zcard(window_key)
        _, _, _, count = await pipe.execute()

    if count >= _FAILURE_THRESHOLD:
        await redis.set(f"{_CIRCUIT_KEY_PREFIX}{provider}", "1", ex=_OPEN_TTL_SECONDS)
```

The `set` on the open-marker can stay outside the MULTI because it is idempotent (TTL refresh) — but moving it into the same EXEC is also fine. Extend tests with a concurrent-asyncio.gather scenario that races 5 `record_failure` calls and asserts the open key is present.

### CR-04: Migration 0027 partial-UNIQUE creation will fail on any deployment with multiple stale `consumed_at IS NULL` rows per user

**File:** `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py:61-90`
**Issue:**
The migration:
1. Adds `otp_codes.channel TEXT NOT NULL DEFAULT 'telegram'` — every pre-existing row is backfilled to `channel='telegram'`.
2. Adds a CHECK constraint.
3. **Immediately creates** a new partial-UNIQUE `uq_otp_codes_user_channel_active ON otp_codes (user_id, channel) WHERE consumed_at IS NULL`.

The migration docstring (lines 30-39) explicitly states there is no pre-existing partial-UNIQUE on `otp_codes(user_id) WHERE consumed_at IS NULL` — so the v1.5 schema permits multiple unconsumed OTP rows per user. The codebase confirms it: `telegram_service.start_deep_link` (`apps/backend/app/modules/auth/telegram_service.py:80-110`) inserts a NEW `OtpCode` row with `user_id=NULL, consumed_at=NULL` every time `/auth/telegram/start` is called and DOES NOT consume prior rows.

In any deployment that has run a Telegram-OTP flow even twice for the same operator without a successful `commit_otp`, `otp_codes` will hold multiple rows with `user_id=<U>, consumed_at=NULL`. After the column default backfill sets all of them to `channel='telegram'`, the new partial-UNIQUE creation will fail with:

```
duplicate key value violates unique constraint "uq_otp_codes_user_channel_active"
```

and `alembic upgrade` will roll back. The migration is theoretically "zero-row backfill" (docstring line 19-22) but practically the row population at deploy time is set by months of real OTP flow — and `telegram_service.start_deep_link` writes a row even before the bot binds the chat, then leaves the row hanging if the operator never completes the flow.

The downgrade (line 93-100) is symmetric — it drops the index, the CHECK, and the column. It does not have to handle re-recreating a non-existent predecessor, so the downgrade direction is clean. The risk is the upgrade direction only.

**Fix:**
Add a defensive pre-upgrade SQL pass that consumes stale rows. The closest project precedent is the Phase 32 / Phase 33 migrations that backfilled denormalised columns; here the safe operation is `UPDATE otp_codes SET consumed_at = now() WHERE user_id IS NOT NULL AND consumed_at IS NULL AND expires_at < now()` (and possibly without the `expires_at` predicate — the migration is the floor anyway). Do this BEFORE the partial-UNIQUE creation:

```python
def upgrade() -> None:
    op.add_column(
        "otp_codes",
        sa.Column("channel", sa.Text(), nullable=False, server_default=sa.text("'telegram'")),
    )
    op.create_check_constraint(
        op.f("ck_otp_codes_channel"),
        "otp_codes",
        "channel IN ('telegram','email')",
    )
    # Pre-emptively consume any stale unconsumed rows so the new partial-UNIQUE
    # creation does not fail on accumulated /auth/telegram/start placeholders.
    op.execute(
        "UPDATE otp_codes SET consumed_at = now() "
        "WHERE consumed_at IS NULL "
        "AND id NOT IN ("
        "    SELECT DISTINCT ON (user_id, channel) id FROM otp_codes "
        "    WHERE consumed_at IS NULL ORDER BY user_id, channel, created_at DESC"
        ")"
    )
    op.create_index(
        _OTP_NEW_UNIQUE, "otp_codes", ["user_id", "channel"],
        unique=True, postgresql_where=sa.text("consumed_at IS NULL"),
    )
```

Verify in staging against a copy of prod data before landing. As an additional belt-and-suspenders, an Alembic `--sql` dry run against a copy of the prod `otp_codes` table should produce zero conflicts on the final `create_index` step.

## Warnings

### WR-01: `EmailSendLog.bounce_type` has no CHECK constraint — webhook can write arbitrary free-form strings

**File:** `apps/backend/app/integrations/email/models.py:81` and `apps/backend/alembic/versions/0026_email_send_log.py:83`
**Issue:**
The model docstring at lines 65-66 declares `bounce_type` should be `'hard' | 'soft' | 'complaint' | NULL` but the column has no CHECK constraint and no DB-side enum. The webhook handler writes the literal strings `"hard"` and `"soft"` (router.py:146, 151) but a future provider event or a typo would silently land malformed data in a forensic column.
**Fix:**
Add a CHECK constraint in a follow-up Alembic migration: `CHECK (bounce_type IN ('hard','soft','complaint') OR bounce_type IS NULL)`. Mirror the `ck_email_send_log_status` pattern at migration 0026 line 90.

### WR-02: Webhook returns 202 on missing `messageId` / unknown `messageId` — silently swallows non-trivial routing bugs

**File:** `apps/backend/app/api/v1/_internal/email/router.py:120-136`
**Issue:**
The webhook returns 202 + a structlog warning when (a) `mail.messageId` is missing entirely or (b) the `provider_message_id` does not match any `EmailSendLog` row. The 202 means Yandex Cloud Postbox will mark the event as delivered and not retry. In case (a) this could be a Postbox API contract change; in case (b) it could be a `dispatch_email` failure that lost the provider_message_id mapping, or a webhook configured for the wrong tenant. Both cases are silently absorbed.
**Fix:**
Return 422 (or 400) on missing `messageId` — the webhook contract requires it. For unknown `messageId`, keep the 202 + warning but emit a structlog WARN with a fixed event name (e.g. `email_webhook_orphan_message_id`) that can drive an ops alert when the rate exceeds a sane threshold.

### WR-03: `request_otp_email` does not lowercase `user.email` before passing it to the dispatcher

**File:** `apps/backend/app/modules/auth/service.py:869, 961-966`
**Issue:**
Line 869 sets `email_lower = email.lower()` and uses it for the DB lookup, but line 963 passes `to=user.email` (the ORM column value) to `get_email_dispatcher()(...)`. If a user was inserted with a mixed-case email — and `users.email` has `unique=True` but no case-insensitive collation in the v1.5 schema — the outbound `From: noreply@... To: User@Example.com` will use the as-stored mixed-case form. The SES-V2 envelope accepts it, but downstream forensic queries on `EmailSendLog.to_address` will be case-inconsistent and break the `ix_email_send_log_to_addr_recorded` index lookup pattern documented in the migration.
**Fix:**
Pass `to=email_lower` (the validated input) or `to=user.email.lower()` to the dispatcher. Better still: add a Pydantic `BeforeValidator` or DB-side `CITEXT` / lowercase functional index — but that crosses Phase 42's deferral fence (Phase 43 owns the `users.email` UNIQUE refactor per `deferred-items.md`). For now, just lowercase at the dispatcher boundary.

### WR-04: `dispatch_email` ARQ task's circuit-open short-circuit still writes an `EmailSendLog` row with `status='rejected'`

**File:** `apps/backend/app/workers/tasks/dispatch_email.py:119-153`
**Issue:**
On a circuit-open short-circuit, the task constructs `EmailSendResult(ok=False, classification='transient_error', error='circuit_open')` and then inserts an `EmailSendLog(... status='rejected', bounce_type=None, ...)`. But `'rejected'` is the status the migration docstring (0026 lines 23-28) reserves for permanent_error from the provider, NOT for circuit-open short-circuits. The forensic query "show me all permanently rejected sends" will conflate breaker shorts with real provider rejections, and ops cannot distinguish a budgeted-out send from a malformed address. Additionally, the `email_send_failed` audit row IS emitted with reason `circuit_open`, but the EmailSendLog row's `status` is the projected enum the migration's CHECK gate enforces — there is no `'circuit_open'` value in the CHECK list (`status IN ('sent','bounced','complained','delivered','rejected')`).
**Fix:**
Either (a) extend the CHECK to include a `'short_circuited'` value (new migration, follow-up phase), or (b) suppress the `EmailSendLog` INSERT entirely on the breaker-short branch (the audit `email_send_failed` row with `reason='circuit_open'` already captures the event for forensics). Option (b) is the cleaner Phase 42-scope fix:

```python
async with _SEMAPHORE:
    if await is_circuit_open(redis, _PROVIDER):
        # Audit-only — do NOT create an EmailSendLog row for shorts.
        async with session_factory() as session:
            await audit.emit(
                session, "email_send_failed", actor_user_id=None,
                resource_type="email_send_log", resource_id=None,
                audit_correlation_id=str(envelope.audit_correlation_id),
                template_id=envelope.template_id,
                to_email=envelope.to,
                reason="circuit_open",
                provider_error_code="circuit_open",
            )
            await session.commit()
        return "failed"
    result = await email_client.send_email(envelope)
    ...
```

Note: option (b) sets `resource_id=None` on the audit row — verify that `AuditLog.resource_id` is nullable (it is, per audit_models — `resource_id: UUID | None`).

### WR-05: `register_arq_pool(ctx["redis"])` reuses the worker's dequeue Redis client as the enqueue pool — version-fragile

**File:** `apps/backend/app/workers/__init__.py:250-255`
**Issue:**
The worker-side compose root passes `ctx["redis"]` directly to `register_arq_pool`. This is documented as "the project-canonical wiring" (line 252-254) but two concerns:

1. ARQ 0.28's `ctx["redis"]` IS the `ArqRedis` pool used by the worker process to dequeue. ARQ 0.29+ has been discussed in the changelog as potentially separating dequeue and enqueue clients (the project pin is `arq>=0.26`, which permits a future bump to 0.29). When that lands, `ctx["redis"]` may no longer be enqueue-capable.

2. The dispatcher's pool reference is stored in module-level `_arq_pool`. If `WorkerSettings.on_shutdown` closes the worker's pool, `_arq_pool` becomes a dangling reference — subsequent enqueues from a cron job that fires AFTER shutdown begins will fail with a confusing closed-connection error rather than a clean "not registered" RuntimeError.

**Fix:**
Either pin `arq` to a major version (`arq>=0.28,<0.29`) in `pyproject.toml` to lock the contract, or build a fresh `create_pool(RedisSettings.from_dsn(...))` in `on_startup` and close it in `on_shutdown` (mirror what `app/main.py:combined_lifespan` does at lines 100-105). The fresh-pool form is more code but is decoupled from ARQ's ctx contract.

### WR-06: HMAC compare consumes `request.headers.get(...)` with `.lower()`-keyed header but verbatim signature value — OK but missing strip()

**File:** `apps/backend/app/api/v1/_internal/email/router.py:87-93`
**Issue:**
The presented header value is read as `presented_sig = request.headers.get("x-email-webhook-signature", "")` and passed straight into `hmac.compare_digest`. The header value is not stripped of whitespace and is not normalised for case. Yandex Cloud Postbox documentation has historically returned hex signatures in lowercase, but a proxy that adds a trailing `\r\n` (defensive parsing) would silently produce a 401. The bigger concern is that hex-comparison is case-insensitive in meaning — `"ab"` and `"AB"` are the same hex byte — but `hmac.compare_digest("ab","AB")` returns False.
**Fix:**
Trim and lowercase before compare:
```python
presented_sig = request.headers.get("x-email-webhook-signature", "").strip().lower()
expected_sig = hmac.new(...).hexdigest()  # already lowercase by hashlib
if not presented_sig or not hmac.compare_digest(presented_sig, expected_sig):
    ...
```

### WR-07: `email_templates.py` autoescape applies only to HTML rendering, but `{{ otp_code }}` interpolation receives raw `str` input

**File:** `apps/backend/app/modules/auth/email_templates.py:51-91`
**Issue:**
`SandboxedEnvironment(autoescape=True)` autoescapes the HTML side, which is correct. But the OTP code originates from `generate_otp_code()` (returns raw 6-digit numeric `str`) — autoescape adds no value because the input is `\d{6}`. The defence-in-depth comment (T-42-05-01) is accurate but the implementation does not actually defend against anything that could exist: the only template variable in the only template is constrained to digits. Not a bug per se, but the rationale block is misleading future maintainers; if a future template variable lands without going through a numeric character class (e.g. `{{ full_name }}`), the autoescape ALSO needs to handle the corresponding text/plain path — which is `_ENV_TEXT` with `autoescape=False`.
**Fix:**
Add an inline assertion or Pydantic field constraint on `otp_code` (e.g. validate `re.fullmatch(r"\d{6}", otp_code)`) so future template variables cannot land without revisiting the autoescape policy. Alternatively, restrict template renders to a `Mapping[str, str]` and assert each value passes through `_safe_template_value` before render — but this is over-engineering for v1.6.

## Info

### IN-01: `_resolve_template` walker eats every miss — no observability on misspellings

**File:** `apps/backend/app/integrations/email/dispatcher.py:54-83`
**Issue:**
The walker raises `KeyError(...)` on miss. The dispatcher does not catch it — it propagates up through `enqueue_email_dispatch` to the caller. The caller in Phase 42 is `request_otp_email` which is invoked from an HTTP route — an uncaught `KeyError` returns 500. The AST gate `test_locked_email_templates_ast.py` is meant to prevent this at CI time, but the gate covers only `get_email_dispatcher()(template_id=...)` callsites — a downstream phase that calls `enqueue_email_dispatch(template_id=...)` directly bypasses the gate. Not a Phase 42 bug; an architectural fragility worth tracking.
**Fix:** Add a structlog error event in the `KeyError` branch citing the bad `template_id` and the known registries. Not a fix to ship in Phase 42 — log this in `deferred-items.md` against Phase 44.

### IN-02: `is_circuit_open` returns `bool(exists)` where `exists` is `int 0|1` — works but obscure

**File:** `apps/backend/app/integrations/email/circuit_breaker.py:46-56`
**Issue:**
`redis.exists(key)` returns `int` (0 or 1+, since EXISTS can be called with multiple keys). Wrapping in `bool(...)` works for the single-key case but is non-obvious; future expansion to "is any circuit open across N providers" would silently break because `bool(2) is True` regardless of which keys exist.
**Fix:** `return await redis.exists(key) == 1` makes the contract explicit.

### IN-03: `infra/dns/sportzal.ru.zone` ships a placeholder DKIM public-key value `<2048-bit-public-key-placeholder>`

**File:** `apps/backend/infra/dns/sportzal.ru.zone:28`
**Issue:**
The zone file is documented as committed before the registrar push (D-42-12). The placeholder `p=<2048-bit-public-key-placeholder>` is a syntactically invalid DKIM record. If an operator copy-pastes the file verbatim into the registrar, DKIM signing will silently fail at Yandex Postbox (every send rejected by recipients). The risk is operator-error, not code-error, but the failure mode is total deliverability collapse.
**Fix:** Add a `;` comment above the line: `; OPERATOR ACTION REQUIRED: replace <2048-bit-public-key-placeholder> with the real Postbox-issued DKIM public key value before applying this zone.` The existing file header mentions this but not at the offending line; co-locate the warning.

### IN-04: `test_dispatch_email_task.py` tests do not exercise real `audit.emit` — bug class invisible

**File:** `apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py:167-301`
**Issue:**
Every test monkey-patches `app.workers.tasks.dispatch_email.audit.emit` with a `fake_emit` that records kwargs and returns None. This is how CR-01 (the `payload=Model(...)` shape error) slipped past CI. The unit tests are exercising the dispatcher's structural call sequence but not the audit emit contract.
**Fix:** Add at least one test (in the integration tier, where a real DB session exists) that calls `dispatch_email` and then queries `audit_log` for the expected row, asserting both that the row exists and that its `payload` JSONB matches the locked Pydantic schema. This would have caught CR-01 immediately.

---

_Reviewed: 2026-05-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
