# Phase 42: Email Transport Layer + Email OTP Fallback — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults auto-selected from STACK.md / ARCHITECTURE.md / PITFALLS.md research)

<domain>
## Phase Boundary

Ship a **channel-agnostic outbound email transport** end-to-end and prove the slot wiring with the **first real consumer** (email-channel OTP fallback on `/auth/otp/request`). Concretely: a real async provider adapter replaces the `client.py` placeholder; an ARQ `dispatch_email` task carries pre-rendered envelopes; the Phase-41 `EmailDispatcher` Protocol slot is double-wired in `app/main.py:create_app()` AND `WorkerSettings.on_startup` (REG-29-03); a per-provider Redis circuit breaker protects the 06:xx cron chain; a signed bounce webhook records send-attempt outcomes into `email_send_log`; DNS records for `mail.sportzal.ru` (SPF/DKIM/DMARC `p=none`) are committed alongside code as an operator-action runbook; `otp_codes` grows a `channel` discriminator; `EMAIL_OTP_LOGIN` (the first locked email template — exercises Phase 41 INFRA-36 AST gate for the first time) is rendered + delivered + verified anti-oracle.

Requirements in scope: **EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07, AUTH-EM-01, AUTH-EM-02, AUTH-EM-03, AUTH-EM-04** (11 reqs per `.planning/REQUIREMENTS.md` traceability table).

**Out of scope (forwarded to later phases or v1.7):**
- The 14 remaining LOCKED templates (invitation, password-reset, expiring, booking, payment receipts) — Phases 44 / 45 own the rendering callsites; their identifiers are already pre-locked at Phase 41.
- `users.email_verified` **set-side** flow (verify endpoint, owner-triggered re-verify) — Phase 43 (open conflict #7).
- Unisender Go fallback **implementation** — documented as escape hatch; not wired in v1.6 (D-42-03).
- Aggressive bounce-driven `email_verified=false` flag flipping — v1.7 (EMAIL-07 explicit defer).
- DMARC ladder progression `p=none → p=quarantine → p=reject` — operator-actions outside Phase 42 code.

</domain>

<decisions>
## Implementation Decisions

### Email provider choice (open conflict #1 — RESOLVED)

- **D-42-01 (Yandex Cloud Postbox as PRIMARY):** `https://postbox.cloud.yandex.net` (SES-V2-API compatible). Per `.planning/research/STACK.md` confidence HIGH: РФ-domiciled legal entity (no sanctions exposure), in-region datacentres for mail.ru/yandex.ru deliverability, 2,000 free emails/month covers ~3× expected v1.6 volume, AWS SDK contract preserves portability to AWS SES if the project ever leaves РФ. Bills in ₽ against Yandex.Balance (matches the same payment-rail discipline that excluded Stripe in v1.7 billing).
- **D-42-02 (`aioboto3` async SES-V2 client):** `aioboto3>=13.0,<14`. Standard `sesv2` client with `endpoint_url='https://postbox.cloud.yandex.net'` override; AWS Signature V4 over Yandex Cloud IAM static access keys. **Provider SDK retries disabled** (`Config(retries={'max_attempts': 1})`) — ARQ is the only retry mechanism (PITFALLS pitfall 3 mitigation: provider 5xx + ARQ retry storm collides with 06:xx cron window).
- **D-42-03 (Unisender Go = documented escape hatch, NOT implemented in v1.6):** `provider: Literal['yandex_postbox', 'sandbox']` for v1.6. Unisender Go remains the documented Plan-B for the case Yandex Cloud credentials become unavailable, but the adapter is **not** built in Phase 42 — keeps the scope tight, the abstraction honest (one real impl + one no-op sandbox), and avoids premature provider-portability gymnastics. Adding `'unisender_go'` is a Phase-42-shaped follow-up in v1.7+ if needed (single `EmailProvider` concrete class addition; Protocol surface untouched).
- **D-42-04 (REJECTED: Resend / Mailgun / AWS SES direct / SendPulse):** All disqualified per STACK.md `## What NOT to Use` — Stripe billing (Resend, Mailgun), no РФ datacentre (Resend, Mailgun, AWS SES direct), or RU-restricted ToS (SendPulse).

### Template engine + render boundary (open conflict #4 — RESOLVED)

- **D-42-05 (Jinja2 `SandboxedEnvironment` for HTML + text):** `jinja2>=3.1.4,<4`. Emails are dual-MIME-part (`text/plain` + `text/html`) and v1.6 templates carry meaningful variable interpolation (`{full_name}`, `{otp_code}`, `{end_date}` Russian-long-form, `{reset_link}`). Jinja's `autoescape=True` on the HTML side and explicit passthrough on the text side is safer than parallel f-strings around Russian-locale dates. `SandboxedEnvironment` for defence-in-depth even on first-party templates (mirrors the locked-DM-copy discipline from v1.2/v1.3). Already transitively in dep tree via FastAPI; explicit `uv add 'jinja2>=3.1.4,<4'` pins it.
- **D-42-06 (Per-domain template ownership preserved — D-39-02 + D-41-11):** Templates live next to their owning module — `app/modules/auth/email_templates.py` for Phase 42's only template, `EMAIL_OTP_LOGIN`. Module-level `TEMPLATES: Final[dict[str, EmailTemplate]]` registry. Each `EmailTemplate` record = `(subject: Final[str], html: jinja2.Template, text: jinja2.Template)`. NO copy in `integrations/email/` — that layer transports bytes, not Russian-locale strings.
- **D-42-07 (Module renders, worker transports — narrative exception D-41-03 honored):** The `EmailDispatcher` slot implementation (`enqueue_email_dispatch`) renders subject/html/text **at enqueue time** inside the calling module's context (which legally imports `app.modules.auth.email_templates`). The ARQ task `dispatch_email` receives the already-rendered `EmailEnvelope` and never imports `app.modules.*` — preserving import-linter contract 3 (`integrations ⊥ modules`). `template_id` is carried in the envelope only for audit emission.
- **D-42-08 (REJECTED: `Final[str]` f-strings):** Marginal AST-grep-ability advantage doesn't pay for Russian-locale interpolation edge cases (NBSP in money, RFC 2047 encoded-word in Cyrillic subjects, `{end_date}` long-form rendering). Locked-template AST gate (Phase 41 INFRA-36) already enforces template_id literal at every dispatch callsite — that gate doesn't weaken with Jinja2.

### DNS + subdomain layout (EMAIL-05 — RESOLVED)

- **D-42-09 (Subdomain = `mail.sportzal.ru`):** Single dedicated subdomain for both `From:` envelope and DKIM key. Matches industry norm; preserves clean reputation isolation from any future `mktg.sportzal.ru` (marketing) subdomain; matches Yandex Cloud Postbox's per-subdomain verification model.
- **D-42-10 (`From:` address = `noreply@mail.sportzal.ru`):** Display name `"Sportzal"` (UTF-8; provider SDK handles RFC 2047 encoded-word automatically). Replies bounce. A separate `bounces@sportzal.ru` mailbox or in-app inbox surface is deferred to v1.7.
- **D-42-11 (DMARC ladder = `p=none` baseline at Phase 42):** Zone file `infra/dns/sportzal.ru.zone` documents:
  - `mail.sportzal.ru. TXT "v=spf1 include:_spf.yandexcloud.net -all"` (Yandex Cloud Postbox SPF macro per Postbox docs)
  - `sport1._domainkey.mail.sportzal.ru. TXT "v=DKIM1; k=rsa; p=<2048-bit-public-key>"` (Postbox console issues the selector + key at domain verification time; zone-file carries the rendered value)
  - `_dmarc.mail.sportzal.ru. TXT "v=DMARC1; p=none; rua=mailto:dmarc-reports@sportzal.ru; pct=100"`
  - DMARC `rua` reports addressed to a single owner mailbox. `p=quarantine` flip after 7 clean-report days (operator-action, NOT code); `p=reject` deferred to v1.7.
- **D-42-12 (Zone file is operator-runbook, not deploy artifact):** The file is committed in `infra/dns/sportzal.ru.zone` so the gate cannot land without the DNS spec; actual registrar push is owner-applied at Reg.ru (or alternate). CI cannot execute it; this is documented in the file's header.

### ARQ `dispatch_email` task + circuit breaker (EMAIL-03 / EMAIL-06)

- **D-42-13 (Task config = `max_tries=2, timeout=20s, retry_delay=30s`):** Per PITFALLS 3. Provider SDK retries = 0/1 (D-42-02). On `EmailSendResult.ok` → `audit.emit("email_sent", actor_user_id=None, resource_id=<email_send_log.id>, audit_correlation_id=...)`. On `EmailSendResult.blocked` (recipient blocked, terminal) → `audit.emit("email_send_failed", classification='blocked')` with NO retry. On `EmailSendResult.transient_error` (5xx / network) → ARQ retries once; final failure emits `email_send_failed` with classification 'transient_error'. On `EmailSendResult.permanent_error` (4xx non-blocked) → emit immediately, no retry.
- **D-42-14 (Redis circuit breaker key + window):** Key `sz:email:circuit:yandex_postbox`, TTL 300s, opened when 5xx count reaches **5 within sliding 60s window**. Sliding window via Redis sorted-set with score=timestamp; head-of-task body checks `EXISTS` on the circuit key + reads the window. If open, task short-circuits to `EmailSendResult.transient_error` without touching the provider (preserves cron-window budget). Closing happens implicitly by TTL expiry; no manual reset surface in Phase 42.
- **D-42-15 (Concurrency cap via `asyncio.Semaphore(5)`):** Module-level `_SEMAPHORE: Final[asyncio.Semaphore] = asyncio.Semaphore(5)` inside `dispatch_email` task module. Yandex Cloud Postbox default rate limit is ~14 emails/sec — 5 concurrent leaves a safe margin and softens any burst from a cron tick. Semaphore is process-scoped (per worker container); container restarts naturally break burst patterns.
- **D-42-16 (`EmailEnvelope` shape — locked):** `app/integrations/email/types.py`:
  ```python
  @dataclass(frozen=True)
  class EmailEnvelope:
      to: str
      subject: str
      html: str
      text: str
      template_id: str  # MUST be a member of LOCKED_EMAIL_TEMPLATES
      audit_correlation_id: UUID
  ```
  ARQ enqueue passes envelope fields as kwargs (ARQ pickles via cloudpickle; frozen dataclass is fine). Worker reconstructs the dataclass inside the task body.

### Bounce/complaint webhook + `email_send_log` (EMAIL-07)

- **D-42-17 (Webhook path = `POST /api/v1/_internal/email/webhook`):** Locked verbatim from ROADMAP success criterion #6. HMAC-SHA256 signature in `X-Email-Webhook-Signature` header; computed over raw body bytes with secret `EMAIL_WEBHOOK_SECRET`; verified via `hmac.compare_digest` **BEFORE body parse** (O(1) timing-safe rejection of unsigned bodies — preserves the ROADMAP success criterion #6 invariant). Yandex Cloud Postbox event-delivery webhooks support per-domain secrets; secret lives in `EmailProviderSettings.webhook_secret: SecretStr`.
- **D-42-18 (`email_send_log` table schema — Alembic 0026):**
  ```sql
  CREATE TABLE email_send_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_correlation_id UUID NOT NULL,
    to_address TEXT NOT NULL,
    template_id TEXT NOT NULL,
    provider TEXT NOT NULL,                 -- 'yandex_postbox' | 'sandbox'
    provider_message_id TEXT NULL,          -- populated by send-time on ok; nullable for short-circuit/sandbox
    status TEXT NOT NULL CHECK (status IN ('sent','bounced','complained','delivered','rejected')),
    bounce_type TEXT NULL,                  -- 'hard' | 'soft' | 'transient' | NULL
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX ix_email_send_log_audit_corr ON email_send_log(audit_correlation_id);
  CREATE INDEX ix_email_send_log_to_addr_recorded ON email_send_log(to_address, recorded_at DESC);
  ```
  NO partial UNIQUE — multiple events per `provider_message_id` (delivered → bounced) are legitimate. INSERT happens inside the ARQ task on every send outcome (success creates `status='sent'` row; webhook later UPDATEs to `'delivered' | 'bounced' | 'complained'`).
- **D-42-19 (Webhook handler is owner-visible-zero-side-effect):** Phase 42 records send-attempt outcomes only; **NO** automatic `users.email_verified=false` flag flipping on bounce. EMAIL-07 explicitly defers that to v1.7. Phase 42 webhook handler validates HMAC, parses payload, UPDATEs the matching `email_send_log` row, emits `audit.emit("email_send_failed", ...)` ONLY for hard-bounce/complaint classifications (soft-bounces stay quiet).

### OTP email channel (AUTH-EM-01..04)

- **D-42-20 (Alembic 0027 — `otp_codes.channel` discriminator):** Verbatim per AUTH-EM-01: `channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')`. DROP existing partial `UNIQUE (user_id) WHERE consumed_at IS NULL`; recreate as `UNIQUE (user_id, channel) WHERE consumed_at IS NULL`. Zero-row backfill — existing rows inherit `channel='telegram'`. Naming convention `op.f()`-wrapped (mirrors Phase 41 0024 lesson).
- **D-42-21 (Alembic 0028 — `users.email_verified`):** `users.email_verified BOOLEAN NOT NULL DEFAULT FALSE`. Phase 42 ships the **column + the AUTH-EM-02 read** ("when `channel='email'`: requires user with verified email"). Phase 43 ships the verify-flow set side (open conflict #7). For Phase 42 bootstrap: existing operator users default `email_verified=false` — the anti-oracle 202 is preserved because false silently drops the request with the same response shape as success (D-42-22). The migration body carries a **comment** documenting that operators are flipped via direct SQL (`UPDATE users SET email_verified = true WHERE email = '<owner_email>';`) during owner-bootstrap; the OWNER's first email-OTP login flow becomes Phase 43's first verify-flow consumer naturally.
- **D-42-22 (AUTH-EM-02 anti-oracle + TTL + cooldown — locked):** `POST /api/v1/auth/otp/request {channel: 'email'}`:
  - Default `channel='telegram'` for backwards compat (existing clients send no `channel` field → unchanged behaviour).
  - `channel='email'` requires resolved user with `email_verified=true`. If user does not exist OR `email_verified=false` OR `is_active=false`: response is **identical 202 shape** (no email enqueued, no audit emit for the unknown branch — but a constant-time-floor sleep matches the populated-branch median time within 100ms per AUTH-EM-04 assertion).
  - TTL = **10 minutes** (Telegram × 2 to absorb provider lag per FEATURES SLO).
  - 60-second resend cooldown enforced at the `otp_codes` row level (CHECK on `created_at > now() - interval '60 seconds'` rejected as 202-no-op).
  - Max 5 attempts per code (existing infrastructure — `otp_codes.attempts` increments on `/auth/otp/verify`).
  - Second OTP request for same `(user_id, channel='email')` **invalidates the first** via atomic UPDATE-to-consumed + INSERT-new in same UoW (RFC 6238 single-active discipline).
- **D-42-23 (AUTH-EM-03 `EMAIL_OTP_LOGIN` template — locked Russian copy):** `app/modules/auth/email_templates.py:TEMPLATES["EMAIL_OTP_LOGIN"]`:
  - Subject: `"Код входа в Sportzal"` (locked `Final[str]`; no interpolation).
  - HTML body: H1 = "Код входа в Sportzal", paragraph "Ваш код для входа: <strong>{otp_code}</strong>", paragraph "Срок действия: 10 минут. Если вы не запрашивали код — проигнорируйте это письмо.", footer "Sportzal · noreply@mail.sportzal.ru".
  - Plain-text body: same content, no markup, NBSP literal U+00A0 where the HTML uses `&nbsp;` (mirrors the v1.4 `formatMoney` NBSP-safe lineage).
  - Owner sign-off recorded at VER-14 (Phase 46) by enumerating `LOCKED_EMAIL_TEMPLATES` member `EMAIL_OTP_LOGIN` — D-27-OWNER-COPY-LOCK pattern preserved.
  - No PII beyond the 6-digit code; specifically NOT `{full_name}` (anti-oracle for stolen-email replay).
- **D-42-24 (AUTH-EM-04 `test_otp_email_anti_oracle.py`):** Integration test asserting four cases:
  1. User with NO Telegram + `email_verified=true` → `channel='email'` OTP path enqueues + sends + verifies via `/auth/otp/verify` end-to-end.
  2. User with Telegram + email, default request (no `channel` field) → `channel='telegram'` path unchanged.
  3. `channel='email'` request for user without `email_verified=true` → response 202 with **identical body** to case 1 (no enqueue, no audit emit, constant-time floor sleep — 100ms tolerance).
  4. `channel='email'` request for completely unknown email → response 202 with identical body to cases 1 and 3.
  Bounded-equal timing uses `time.perf_counter()` deltas per RESET-06 precedent.

### `EmailDispatcher` registration — REG-29-03 double-wire (EMAIL-04)

- **D-42-25 (Concrete impl = `enqueue_email_dispatch` in `app/integrations/email/dispatcher.py`):** Signature matches Phase 41 D-41-24 slot exactly:
  ```python
  async def enqueue_email_dispatch(
      *,
      template_id: str,
      to: str,
      audit_correlation_id: UUID | None,
      **template_vars: Any,
  ) -> None
  ```
  Body: looks up the template via per-module registry lookup (helper `_resolve_template(template_id) -> EmailTemplate` walks the known per-module registries — `auth.email_templates.TEMPLATES` for Phase 42; Phases 44/45 extend the walker); renders subject/html/text against `template_vars`; builds `EmailEnvelope`; `await arq_pool.enqueue_job('dispatch_email', envelope)`.
- **D-42-26 (Both call sites register identical implementation):**
  - `app/main.py:create_app()` — after Redis pool created: `register_email_dispatcher(enqueue_email_dispatch)`.
  - `app/workers/__init__.py:WorkerSettings.on_startup` — same `register_email_dispatcher(...)` call AND `ctx['email_client'] = build_email_client(settings)` (per EMAIL-04 verbatim — mirrors `ctx['engine']` / `ctx['sessionmaker']` from v1.2 Phase 18).
  - REG-29-03 parity test (`tests/test_compose_root_parity.py` or similar; verify exact filename during plan-phase) extended to assert both call sites register identical Protocol implementation.
- **D-42-27 (First real LOCKED_EMAIL_TEMPLATES callsite — exercises INFRA-36 AST gate):** `app/modules/auth/service.py:request_otp_email` (NEW function) is the first real `get_email_dispatcher()(template_id="EMAIL_OTP_LOGIN", to=..., audit_correlation_id=..., otp_code="123456")` callsite. Phase 41's `tests/test_locked_email_templates_ast.py` AST-walker test verifies this callsite passes; the existing synthetic-violation fixture continues to fail. The Phase 41 walker scope extension to `app.modules.*` is now exercised on real code.

### Configuration / secrets / sandbox mode (EMAIL-02)

- **D-42-28 (`EmailProviderSettings` Pydantic block):** `app/core/config.py`:
  ```python
  class EmailProviderSettings(BaseModel):
      provider: Literal['yandex_postbox', 'sandbox'] = 'sandbox'
      aws_access_key_id: SecretStr | None = None
      aws_secret_access_key: SecretStr | None = None
      endpoint_url: str = 'https://postbox.cloud.yandex.net'
      from_address: str = 'noreply@mail.sportzal.ru'
      from_domain: str = ''                       # validated non-empty in non-sandbox
      webhook_secret: SecretStr = SecretStr('')   # validated non-empty in non-sandbox
      sandbox_mode: bool = False                  # belt+suspenders alongside provider='sandbox'

      @model_validator(mode='after')
      def _validate_production_required(self) -> Self:
          if self.provider != 'sandbox' and not self.sandbox_mode:
              if not self.from_domain:
                  raise ValueError('EmailProviderSettings.from_domain is required for non-sandbox provider')
              if not self.webhook_secret.get_secret_value():
                  raise ValueError('EmailProviderSettings.webhook_secret is required for non-sandbox provider')
              if not self.aws_access_key_id or not self.aws_secret_access_key:
                  raise ValueError('EmailProviderSettings AWS credentials required for non-sandbox provider')
          return self
  ```
  Loaded via existing `Settings` root model + `env_prefix='EMAIL_'` pattern. Fail-fast at app boot — same discipline as v1.2 D-18 ARQ on_startup.
- **D-42-29 (Sandbox mode behaviour):** When `provider='sandbox'` OR `sandbox_mode=True`: `EmailClient.send_email` logs the rendered envelope at INFO level (subject + first 80 chars of text body + `to`) and returns `EmailSendResult.ok(provider_message_id=f'sandbox-{uuid4()}')` without calling any provider. NO mail leaves the process. Used by `docker compose up` dev environment, unit tests, and CI. NOT the same as `moto[ses]` (which wraps the boto3 client at the test boundary — moto is for unit-test isolation of the real client code path).
- **D-42-30 (Boot-time domain probe):** When `provider='yandex_postbox'` AND `sandbox_mode=False`, `build_email_client(settings)` calls `sesv2.get_email_identity(EmailIdentity=settings.from_domain)` and asserts `VerificationStatus == 'Success'`. Failure → `RuntimeError` at app startup (mirrors v1.2 D-18 fail-fast). Probe is skipped in sandbox mode. ROADMAP success criterion #5 verbatim.

### Migration packaging (mechanical — derives from decisions above)

- **D-42-31 (3 sequential migrations 0026 → 0028):**
  - `0026_email_send_log` — D-42-18 schema (table + 2 indexes).
  - `0027_otp_codes_channel_discriminator` — D-42-20 channel column + partial-UNIQUE recreate.
  - `0028_users_email_verified` — D-42-21 boolean column + DEFAULT FALSE.
  Migration order is intentional: 0026 has no FK dependencies; 0027 is mechanically tied to AUTH-EM-01; 0028 lands last because Phase 43 will reference it for the verify-flow.
- **D-42-32 (No omnibus migration):** Mirrors Phase 41 D-41-15 — one logical change per Alembic file, naming convention `op.f()`-wrapped, round-trip clean.

### Eager-import discipline (REG-29-04 mirror)

- **D-42-33 (`email_send_log` ORM model + eager-import):** New `EmailSendLog` ORM model in `app/integrations/email/models.py` (transport layer owns the table since modules don't read it directly — only the dispatcher + webhook handler do). `alembic/env.py` imports it; `app/workers/__init__.py` eager-imports it for the boot-time `Base.metadata.tables.keys()` invariant. `tests/unit/test_workers_eager_import.py` extended to assert `email_send_log` appears. Per REG-29-04 / NOTIFY-14 lineage.

### Audit emission patterns

- **D-42-34 (`email_sent` / `email_send_failed` emission shape — INFRA-35 payloads):** Phase 41 pre-registered both event names in `LOCKED_AUDIT_EVENTS` and shipped matching `EmailSentPayload` / `EmailSendFailedPayload` Pydantic models in `audit_payloads.py`. Phase 42 callsites:
  - Inside ARQ `dispatch_email` task body on success: `audit.emit("email_sent", actor_user_id=None, resource_type="email_send_log", resource_id=<send_log_row.id>, audit_correlation_id=<envelope.audit_correlation_id>, payload=EmailSentPayload(...))`.
  - Inside webhook handler on hard-bounce/complaint: `audit.emit("email_send_failed", ..., payload=EmailSendFailedPayload(classification='bounced_hard'|'complained', ...))`.
  - Inside ARQ task on terminal blocked/permanent_error: same `email_send_failed` emit with appropriate classification.
- **D-42-35 (`audit_correlation_id` chain seed):** The OTP request handler (`auth.service.request_otp_email`) **generates** a new `audit_correlation_id = uuid4()` at the entry of an email-OTP request, emits `otp_email_requested` (... wait — that event was NOT pre-registered in Phase 41). Decision: piggyback on the existing `otp_requested` audit event (Phase 7 lineage) for the request-side emission; pass the request's `audit_correlation_id` into the envelope. The ARQ task's `email_sent` emit carries the same correlation_id → the audit log query `WHERE audit_correlation_id = <X>` returns both rows for forensic continuity. **No new audit event names** required in Phase 42 beyond the two pre-registered.

### Claude's Discretion

- Exact SQL syntax of migrations 0026 / 0027 / 0028 (Alembic conventions follow Phase 41 0024 / 0025 precedent).
- Internal Redis sliding-window implementation for circuit breaker (ZADD + ZREMRANGEBYSCORE on TTL'd sorted set is standard; specific Redis primitives left to planner).
- Yandex Cloud Postbox SES-V2 API request shape boilerplate (`Destination`, `Content.Simple.Subject.Data`, `Content.Simple.Body.Html.Data`, etc.) — implementation detail.
- Exact module path for the per-module template registry walker helper (`_resolve_template`) — likely `app/integrations/email/dispatcher.py`.
- HTML email template visual styling beyond the locked Russian copy (no CSS framework; plain inline styles allowed for the OTP code emphasis only; `<table>` layout NOT required at this volume).
- Exact log format inside sandbox mode envelope logging (structlog field shape).
- Whether the webhook handler is registered under `app/api/v1/_internal/...` (existing pattern) or a new `app/modules/email/router.py` (new module). Recommend the former — webhook is a transport concern, not a feature module; pure-`_internal` mount in main `app/api/v1/__init__.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 42 source-of-truth specs (locked)
- `.planning/REQUIREMENTS.md` §§ EMAIL-01..07 + AUTH-EM-01..04 — locked requirements; non-negotiable acceptance criteria
- `.planning/REQUIREMENTS.md` §§ Open Conflicts — conflict #1 (provider) + #4 (template engine) resolved by THIS document
- `.planning/ROADMAP.md` §§ Phase 42 — goal + 6 success criteria + dependency declaration on Phase 41
- `.planning/PROJECT.md` — current state (v1.5 shipped 2026-05-18 + Phase 41 complete 2026-05-18; 67 LOCKED_AUDIT_EVENTS post-Phase-41; 33-entry OWNER_ONLY; 8 Protocol slots including `EmailDispatcher` declared but not wired; 11 business tables post-Phase-41)
- `.planning/STATE.md` — Phase 41 marked complete 2026-05-18; v1.6 phase plan table

### Phase 41 lineage (Phase 42 builds on these decisions verbatim)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/41-CONTEXT.md` — D-41-01..29 (User ORM hoist, `password_reset_tokens` table, ContextVar actor capture, `LOCKED_EMAIL_TEMPLATES` shape, `EmailDispatcher` Protocol signature, REG-29-03 double-wire discipline, REG-29-04 eager-import, RESET-06 anti-oracle xfail test)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` — pre-existing ORM drift in `users.email` UNIQUE + `users.deleted_at` + `*_notifications.channel` (Phase 43 / Phase 45 own these; Phase 42 must NOT touch the `User` ORM beyond adding `email_verified`)
- `apps/backend/app/core/dependencies.py` — `EmailDispatcher` Protocol + `register_email_dispatcher` + `get_email_dispatcher` (Phase 42's slot-wiring target; signature already locked)
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` (67 entries — includes `('email_sent', 'email_send_log')` + `('email_send_failed', 'email_send_log')`); `LOCKED_EMAIL_TEMPLATES` frozenset (15 identifiers — Phase 42 exercises `EMAIL_OTP_LOGIN` first)
- `apps/backend/app/core/audit_payloads.py` — `EmailSentPayload` + `EmailSendFailedPayload` Pydantic models (extra='forbid', audit_correlation_id UUID|None)
- `apps/backend/app/core/permissions.py` — `Resource.USERS` + 4 OWNER_ONLY entries (Phase 42 doesn't add new entries; this is reference for the multi-user phase 43)
- `apps/backend/app/core/actor_context.py` + `app/core/middleware.py` — ActorContext ContextVar runtime; Phase 42 audit emissions read from this contextvar transparently
- `apps/backend/alembic/versions/0022_users_soft_delete_unique.py` → `0025_password_reset_tokens.py` — most recent migrations; Phase 42 lands 0026 → 0028
- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — Phase 41 xfail-strict scaffolding; Phase 42 does NOT touch this (Phase 44 owns).

### v1.6 research (HIGH confidence — must read for Phase 42 trade-off rationale)
- `.planning/research/STACK.md` §§ TL;DR + Recommended Stack — provider scorecard (Yandex Cloud Postbox primary, Unisender Go fallback documented); Jinja2 SandboxedEnvironment vs f-strings trade-offs; `What NOT to Use` table (Resend / Mailgun / Stripe-billed providers / synchronous SMTP / fastapi-mail rejected with reasons)
- `.planning/research/PITFALLS.md` §§ Pitfall 1 (email breaks anti-oracle) + Pitfall 2 (cross-channel double-pings) + Pitfall 3 (provider 5xx + ARQ retry storm) + Pitfall 6 (provider secret rotting at env boundary) + Pitfall 7 (REG-29-04 eager-import) — all Phase 42 surface
- `.planning/research/ARCHITECTURE.md` — modular monolith additions, `app/integrations/email/` transport-layer shape (Protocol slot pattern, per-domain template ownership precedent), ARQ task vs synchronous-handler discipline
- `.planning/research/FEATURES.md` — 11 anti-features (esp. plaintext password email, dual-email-per-user, multi-channel OTP race, app-layer bounce retry) — Phase 42 implementation must NOT enable these
- `.planning/research/SUMMARY.md` — 7 open conflicts table (conflicts #1 + #4 resolved here; #5 resolved at Phase 41; #2 + #3 + #6 + #7 deferred to Phases 43/44/45/46)

### v1.0–v1.5 codebase landmarks (Phase 42 extends or mirrors)
- `apps/backend/app/integrations/email/client.py` — current placeholder (TODO line 2-4); Phase 42 replaces with real `send_email` adapter
- `apps/backend/app/integrations/email/templates/` — directory exists but empty in placeholder state
- `apps/backend/app/integrations/telegram/bot.py` + `telegram/sender.py` — mirror shape: `build_bot(settings)` factory + `SendResult` dataclass with classified failure modes (Phase 42 `EmailSendResult` mirrors this exactly)
- `apps/backend/app/modules/auth/service.py` — `request_otp` existing function (Telegram path); Phase 42 adds parallel `request_otp_email` function with anti-oracle constant-time floor
- `apps/backend/app/modules/auth/models.py` (or `app/core/models.py:User` post-Phase-41) — User ORM; Phase 42 adds `email_verified BOOLEAN NOT NULL DEFAULT FALSE` via Alembic 0028 + ORM column
- `apps/backend/app/modules/auth/models.py:otp_codes` — Phase 42 adds `channel TEXT NOT NULL DEFAULT 'telegram'` column + recreates partial UNIQUE via Alembic 0027
- `apps/backend/app/workers/__init__.py` — `WorkerSettings.functions` list + `on_startup`/`on_job_start`/`on_job_end` hooks; Phase 42 adds `dispatch_email` function entry + `register_email_dispatcher` call in `on_startup` + `email_client` build into `ctx`
- `apps/backend/app/workers/tasks/notifications.py` + `tasks/reminders.py` — existing ARQ task shapes (Phase 18 + Phase 39 lineage); Phase 42 `dispatch_email` task mirrors structure
- `apps/backend/app/main.py:create_app` — composition root; Phase 42 adds `register_email_dispatcher(enqueue_email_dispatch)` call after Redis pool init
- `apps/backend/app/core/config.py` — existing `Settings` shape with nested provider blocks (TelegramBotSettings precedent); Phase 42 adds `EmailProviderSettings`
- `apps/backend/tests/test_compose_root_parity.py` (or equivalent — verify exact filename during plan-phase) — REG-29-03 double-wire parity test; Phase 42 extends to assert `EmailDispatcher` registered in both compose root and worker startup
- `apps/backend/tests/test_locked_email_templates_ast.py` (Phase 41) — Phase 42 extends fixtures to assert the new `EMAIL_OTP_LOGIN` callsite passes
- `apps/backend/tests/unit/test_workers_eager_import.py` (Phase 41) — Phase 42 extends to assert `email_send_log` table appears in `Base.metadata.tables.keys()`

### Verification + governance lineage
- `.planning/milestones/v1.5-VERIFICATION-LOG.md` — REG-29-01/03/04 regression precedents; DEFER-40-01 runbook-scaffolding lesson (Phase 46 budgets this; Phase 42 contributes runbook fragments for the email path)
- `apps/backend/scripts/run_expiring_cron_once.py` — operator one-shot pattern (TM-29-02/03); Phase 42's circuit breaker + sandbox mode must be exercisable via similar one-shot mechanic for the verification phase

### Yandex Cloud Postbox external docs (re-verify at plan-phase)
- Yandex Cloud Postbox SES-V2 endpoint reference (provider-supplied; verify current URL at plan-time)
- Yandex Cloud IAM static access key issuance flow (operator-action; documented in EMAIL-05 runbook artifact)
- Yandex Cloud Postbox webhook signature scheme (HMAC-SHA256 over raw body; secret per domain configured in Postbox console)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/app/integrations/telegram/sender.py:SendResult`** — `Final[dataclass]` with classified failure modes (`ok` | `blocked` | `bad_request` | `network_error`). Phase 42's `EmailSendResult` mirrors this exactly with email-domain failure modes (`ok` | `blocked` | `transient_error` | `permanent_error`). Same `match` exhaustiveness discipline downstream.
- **`apps/backend/app/integrations/telegram/bot.py:build_bot`** — DI-injectable factory taking settings → returns client. Phase 42's `app/integrations/email/factory.py:build_email_client` is a line-for-line shape mirror.
- **`apps/backend/app/core/dependencies.py:EmailDispatcher`** Protocol + `register_email_dispatcher` + `get_email_dispatcher` — Phase 41 D-41-24 ready-to-wire slot. Phase 42 first exercises the slot.
- **`apps/backend/app/core/audit.py:LOCKED_EMAIL_TEMPLATES`** — Phase 41 INFRA-36 frozenset (15 identifiers, `EMAIL_OTP_LOGIN` member of). AST walker test `test_locked_email_templates_ast.py` already in place. Phase 42 ships the first real callsite.
- **`apps/backend/app/core/audit_payloads.py:EmailSentPayload` + `EmailSendFailedPayload`** — Phase 41 INFRA-35 Pydantic schemas with `extra='forbid'` + `audit_correlation_id`. Phase 42 emits them.
- **`apps/backend/app/workers/__init__.py:WorkerSettings.functions`** + on_startup hooks — existing ARQ task registry; Phase 42 appends `dispatch_email`.
- **`apps/backend/app/workers/tasks/notifications.py`** — Phase 27 / Phase 39 ARQ task shape with `audit.emit` on outcomes + idempotency-row INSERT. Phase 42's `dispatch_email` mirrors structure.
- **`apps/backend/app/modules/auth/service.py:request_otp`** — Telegram OTP request entry; Phase 42's `request_otp_email` is a parallel function with constant-time floor + verified-email guard + anti-oracle 202.
- **`apps/backend/app/modules/auth/rate_limit.py`** — existing per-IP / per-user rate limit infrastructure; Phase 42 reuses for the 60s OTP resend cooldown.
- **`apps/backend/app/core/middleware.py:ActorContextMiddleware`** (Phase 41 D-41-08) — request-scoped actor identity ContextVar. Phase 42 audit emissions transparently pick up the actor for non-anonymous paths (e.g., `/auth/otp/verify` for already-authenticated step-up flows). For the unauthenticated `/auth/otp/request` path, actor stays None (per D-41-10).
- **`apps/backend/alembic/versions/0024_notification_channel_discriminator.py`** (Phase 41) — `channel TEXT NOT NULL DEFAULT 'telegram' CHECK ...` migration shape. Phase 42's 0027 `otp_codes.channel` migration mirrors line-for-line with `op.f()`-wrapped naming.
- **`apps/backend/alembic/versions/0025_password_reset_tokens.py`** (Phase 41) — partial-UNIQUE pattern with `purpose` column. Phase 42's `email_send_log` table has no partial-UNIQUE (multiple-events-per-message-id is intentional) but borrows the same Alembic-naming + ORM-registration discipline.

### Established Patterns

- **Protocol slot double-wire (REG-29-03):** Phase 41 declared the slot; Phase 42 is the first phase exercising it. Both `app/main.py:create_app()` AND `WorkerSettings.on_startup` register identical implementation. Parity test asserts byte-equality.
- **Per-domain template ownership (D-39-02 / D-41-11):** `EMAIL_OTP_LOGIN` lives in `app/modules/auth/email_templates.py`, NOT in `app/integrations/email/templates/`. Phase 42 establishes the precedent for Phase 44 (`auth.password_reset_email_templates`) and Phase 45 (per-module locked email copy).
- **Module renders, worker transports (D-41-03 narrative exception):** Render happens at enqueue-time inside the module's import-legal context; the ARQ task receives pre-rendered bytes (`EmailEnvelope`); workers never import `app.modules.*`. Preserves contract 3 (`integrations ⊥ modules`).
- **Always async via ARQ (v1.1 D-06 lineage):** Email send never inline in HTTP handler — same discipline as Telegram bot send. `request_otp_email` returns 202 immediately; the email leaves the system asynchronously.
- **Anti-oracle constant-time floor (D-20-9 / RESET-06 lineage):** Both `email_verified=false` and unknown-email branches return identical 202 with bounded-equal timing (≤100ms tolerance). `time.perf_counter()` deltas verified in `test_otp_email_anti_oracle.py`.
- **Locked-copy AST gate (INFRA-36 / D-41-11):** `template_id="EMAIL_OTP_LOGIN"` must be a literal string; the AST walker rejects expressions. Phase 42 exercises this for the first time.
- **Migration order = dependency order (D-41-16 lineage):** 0026 (email_send_log) → 0027 (otp_codes.channel) → 0028 (users.email_verified). All independent; lexical-order convention preserved.
- **REG-29-04 eager-import:** `email_send_log` ORM model registered in `alembic/env.py` AND eager-imported in `app/workers/__init__.py`. Test asserts via AST introspection.
- **Provider SDK retries = 0/1; ARQ owns retry (PITFALLS 3):** `Config(retries={'max_attempts': 1})` on boto3 client. ARQ `max_tries=2, timeout=20s`.
- **Sandbox mode = log + ok-return (no provider call):** Belt+suspenders via `provider='sandbox'` literal AND explicit `sandbox_mode: bool`. Used in dev compose + unit tests + CI.

### Integration Points

- **Phase 43 entry seam** — Phase 42 ships `users.email_verified` column (Alembic 0028) defaulting to FALSE. Phase 43 USERS-03 invitation-accept flow flips this to TRUE on first invite acceptance. Phase 43 may also add an owner-initiated `PATCH /api/v1/users/{id}/verify-email` surface (open conflict #7 owns the policy).
- **Phase 44 entry seam** — Phase 42's `EmailDispatcher` slot wiring + `LOCKED_EMAIL_TEMPLATES` AST gate first exercise + ARQ `dispatch_email` task are all dependencies for Phase 44's `PASSWORD_RESET_EMAIL` + `USER_INVITATION_EMAIL` template callsites. Phase 44 adds zero new infra at the transport layer.
- **Phase 45 entry seam** — Phase 42's `EmailEnvelope` shape + dispatcher API + circuit breaker are the universal contract Phase 45 NOTIFY-08..13 consume for expiring-soon / booking / payment-receipt email mirrors. Phase 45 adds zero new transport infrastructure.
- **Phase 46 entry seam** — OpenAPI drift gate. Phase 42 adds new paths: `POST /api/v1/auth/otp/request` body schema extension (added `channel: Literal['telegram','email']` field — schema change but not new path), `POST /api/v1/_internal/email/webhook` (new path under `_internal` mount). OpenAPI byte-diff at Phase 42 commit time must include these two surface additions; `schema.d.ts` forward-guards bump by ~2.
- **No new admin-web surface:** v1.6 admin-web stays frozen mock-reference (Phase 41 D-41-23 lineage). Phase 42 contributes zero admin-web changes.

</code_context>

<specifics>
## Specific Ideas

- **Yandex Cloud Postbox specifically chosen for РФ legal entity + AWS SDK contract preservation (D-42-01).** The portability story is load-bearing: same `send_email` shape works against AWS SES if Yandex Cloud ever becomes unavailable. This matters more than provider-bespoke features (no Resend tags, no SES configuration sets — anti-feature per PITFALLS 1).
- **Jinja2 over f-strings explicitly motivated by Russian-locale dual-MIME render (D-42-05).** F-strings work for Telegram DM constants because there's only `text/plain` and minimal variable interpolation. Email adds HTML + text MIME parts + `{end_date}` long-form rendering — Jinja's autoescape + sandbox is the right trade.
- **Single primary provider + sandbox stub in v1.6 (D-42-03).** Unisender Go fallback adapter is documented as an escape hatch but NOT built — preserves the "one real impl + one no-op sandbox" simplicity of the Phase 42 scope. Provider Protocol surface stays clean for the future addition.
- **Conservative `email_verified=false` default + manual SQL flip for bootstrap (D-42-21).** Phase 42 ships the column NOW (read side); Phase 43 ships the verify-flow set side. Bootstrap path: `UPDATE users SET email_verified = true WHERE email = '<owner_email>';` documented in migration body. This avoids reactivating the AST gate AND avoids inventing a verify-flow policy in Phase 42 (open conflict #7).
- **Sandbox mode = log + ok-return (D-42-29).** No `moto`-style intercept at this layer. Test isolation uses moto separately; sandbox mode is for dev compose + ops verification + CI.
- **Module-side render boundary (D-42-07).** Crisp invariant: workers transport bytes, modules render templates. Preserves import-linter contract 3 + makes the `template_id` carriage purely audit-correlative.
- **3 migrations, not omnibus (D-42-31).** Mirrors Phase 41 D-41-15 discipline. Each migration tells one logical story; round-trip verification is per-migration.

</specifics>

<deferred>
## Deferred Ideas

- **Unisender Go fallback adapter** — Documented as Plan-B in STACK.md. Implementation deferred to v1.7+ if Yandex Cloud Postbox accessibility ever becomes an operator concern. Concrete adapter shape: `app/integrations/email/providers/unisender_go.py` with `EmailProvider` Protocol implementation. ~80 lines.
- **`email_verified` set-side flow (verify endpoint, expiry, owner-triggered re-verify)** — Phase 43 (open conflict #7 — trust owner-entered addresses vs click-to-verify). Phase 42 schema-adds the column with conservative FALSE default; bootstrap path is manual SQL.
- **Aggressive bounce-driven `email_verified=false` flag flipping** — v1.7 per EMAIL-07 explicit defer. Phase 42 records send-attempt outcomes only; bounce → policy-change is a v1.7 surface.
- **Reply-to / `bounces@sportzal.ru` address + in-app inbox surface** — v1.7+. Phase 42 sends `noreply@mail.sportzal.ru` only.
- **DMARC `p=quarantine` flip after 7 clean-report days** — Operator-action, not code. Phase 42 zone file ships `p=none` baseline only.
- **DMARC `p=reject`** — v1.7 (per EMAIL-05 explicit ladder).
- **`clients.preferred_channel ∈ {auto, telegram, email, both}`** — Phase 45 NOTIFY-* scope (FEATURES P2 — admin-web edit only, no client-facing UI).
- **Rate-limit per recipient (≤3 OTPs/hour to same email)** — v1.7+ if abuse appears. Phase 42 reuses the existing per-user 60s resend cooldown via `otp_codes` rows (AUTH-EM-02 verbatim).
- **Owner weekly digest (bounces, deactivations, failed sends)** — v1.7+ (FEATURES "defer" rationale — needs ≥1 month of `email_send_log` data before signal is useful).
- **In-app inbox / marketing campaigns / preference centre / TOTP / WebAuthn / custom RBAC roles** — Explicit anti-features per FEATURES.md. Out of v1.6 scope.
- **Unisender Go SMTP fallback path (port 465 SSL via `aiosmtplib`)** — Deferred along with the Unisender Go HTTP API path. Single provider in v1.6.
- **`premailer` HTML CSS-inliner** — Skipped per STACK.md (premature optimisation for plain transactional emails).
- **Phase 41 deferred ORM drift items** (`users.email` UNIQUE removal, `users.deleted_at` ORM mapping, `*_notifications.channel` ORM columns) — Owned by Phases 43/45 respectively per `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md`. Phase 42 MUST NOT touch these — only adds `email_verified` to User.

### Reviewed Todos (not folded)
No todos matched Phase 42 scope (gsd-sdk todo.match-phase returned `todo_count=0` on 2026-05-18).

</deferred>

---

*Phase: 42-email-transport-layer-email-otp-fallback*
*Context gathered: 2026-05-18*
*Mode: --auto (recommended defaults from STACK.md / ARCHITECTURE.md / PITFALLS.md)*
