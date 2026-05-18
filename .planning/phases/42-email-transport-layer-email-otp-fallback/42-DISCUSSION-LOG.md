# Phase 42: Email Transport Layer + Email OTP Fallback - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 42-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 42-email-transport-layer-email-otp-fallback
**Areas discussed:** Email provider choice; Template engine + render boundary; DNS subdomain layout + DMARC ladder; ARQ dispatch task + circuit breaker; Bounce webhook + email_send_log schema; OTP email channel (anti-oracle + verified-email semantics); EmailDispatcher double-wire; Configuration + sandbox mode; Migration packaging
**Mode:** `--auto` (no AskUserQuestion calls — recommended defaults selected from research and roadmap success criteria; full audit trail of alternatives below)

---

## Email provider choice (open conflict #1)

| Option | Description | Selected |
|--------|-------------|----------|
| Yandex Cloud Postbox (primary) + sandbox stub | РФ-domiciled legal entity, SES-V2-compatible API via aioboto3, 2000 free emails/month, in-region deliverability, ₽-billed | ✓ (D-42-01) |
| Yandex Cloud Postbox + Unisender Go fallback (both implemented) | Belt+suspenders; doubles adapter surface in v1.6; deferred to v1.7+ | |
| Unisender Go (primary) | Pure-РФ alternative; vendor-bespoke SDK locks project to single vendor; less generous free tier | |
| AWS SES (eu-central-1) | $-billed (sanctions risk); degraded yandex.ru/mail.ru deliverability; wrong data-residency story | |
| Resend / Mailgun | Stripe-billed (excluded by CLAUDE.md); no РФ datacentre; rate-limited by RU providers | |
| SendPulse | RU-restricted ToS — disqualified | |

**Auto-mode selection:** Yandex Cloud Postbox as PRIMARY via `aioboto3>=13.0,<14`; Unisender Go documented as escape hatch but NOT implemented in v1.6 (single primary provider + sandbox keeps Phase 42 scope tight). Per STACK.md confidence HIGH.

**Notes:** Provider SDK retries explicitly DISABLED (`Config(retries={'max_attempts': 1})`) — ARQ is the only retry mechanism per PITFALLS 3.

---

## Template engine + render boundary (open conflict #4)

| Option | Description | Selected |
|--------|-------------|----------|
| Jinja2 SandboxedEnvironment | Industry standard; transitive via FastAPI; sandboxed even for first-party; clean HTML+text dual-MIME render with autoescape | ✓ (D-42-05) |
| `Final[str]` f-string templates | Matches v1.5 Telegram DM constant lineage; cleaner AST-grep; weaker around `{end_date}` Russian-long-form + Cyrillic subject RFC 2047 | |
| MJML + mjml-python | Gorgeous responsive HTML; overkill for transactional emails; extra CI build step | |
| Direct `email.message.EmailMessage` only | No template surface; would push interpolation into Python f-strings inline | |

**Auto-mode selection:** Jinja2 SandboxedEnvironment. Dual-MIME (HTML + text) emails with meaningful variable count (`{otp_code}`, `{full_name}`, `{end_date}`) tip the trade vs. f-strings.

**Render boundary:** Module-side render at enqueue time (`enqueue_email_dispatch`); worker transports pre-rendered `EmailEnvelope` bytes. Preserves import-linter contract 3 (`integrations ⊥ modules`). D-41-03 narrative exception honored.

**Notes:** Per-domain template ownership (`app/modules/auth/email_templates.py`) preserves D-39-02 / D-41-11 lineage. Templates do NOT live in `app/integrations/email/templates/`.

---

## DNS subdomain layout + DMARC ladder

| Option | Description | Selected |
|--------|-------------|----------|
| `mail.sportzal.ru` dedicated subdomain + DMARC `p=none` initial | Industry-norm; clean reputation isolation from any future `mktg.*` subdomain; matches Yandex Postbox per-subdomain verification model | ✓ (D-42-09..11) |
| Apex `sportzal.ru` From: | Couples transactional and web reputation; complicates DMARC if web later adds non-email SPF entries | |
| `noreply.sportzal.ru` | Less idiomatic than `mail.*`; same isolation; slightly more typing | |
| `notifications.sportzal.ru` | Long; differentiates poorly from any future "notifications" feature module | |

**Auto-mode selection:** `mail.sportzal.ru` with `noreply@mail.sportzal.ru` From: address. DMARC ladder: `p=none` baseline at Phase 42; `p=quarantine` after 7 clean-report days (operator action); `p=reject` deferred to v1.7.

**Notes:** SPF = `v=spf1 include:_spf.yandexcloud.net -all`. DKIM 2048-bit selector `sport1._domainkey.mail.sportzal.ru` issued by Postbox console at domain verification time. Zone file `infra/dns/sportzal.ru.zone` is owner-runbook (not deploy artifact) — CI cannot execute; registrar push is operator-applied at Reg.ru.

---

## ARQ `dispatch_email` task + circuit breaker

| Option | Description | Selected |
|--------|-------------|----------|
| `max_tries=2, timeout=20, retry_delay=30` + Redis circuit breaker (5×5xx within 60s window opens for 5m) + Semaphore(5) concurrency cap | Per PITFALLS 3; preserves 06:xx cron-window budget; bounded blast radius | ✓ (D-42-13..15) |
| `max_tries=5` with exponential backoff | Same-morning thundering herd risk; collides with cron window | |
| No circuit breaker; just SDK retries | Provider 5xx + SDK retry storm wedges worker — exactly PITFALLS 3 scenario | |
| Move email out of cron path entirely (outbox + drainer) | More complex; defers to v1.7 if cron-window pressure shows in verification | |

**Auto-mode selection:** ARQ owns retry (provider SDK retries disabled). Redis sliding-window circuit breaker keyed by provider. Semaphore-5 caps concurrent provider calls (Yandex Postbox default ~14 emails/sec).

---

## Bounce/complaint webhook + `email_send_log` schema

| Option | Description | Selected |
|--------|-------------|----------|
| `POST /api/v1/_internal/email/webhook` with HMAC-SHA256 BEFORE body parse; `email_send_log` table with `status` enum + `bounce_type` nullable; NO partial UNIQUE (multi-events-per-message-id) | Locked verbatim from ROADMAP success criterion #6; forensic-friendly; passive — no `email_verified` flag flips in Phase 42 | ✓ (D-42-17..19) |
| Webhook with API-key auth (no HMAC) | Doesn't meet ROADMAP success criterion #6 (HMAC before body parse) | |
| Active bounce-driven `email_verified=false` flag flipping at webhook time | Couples bounce policy to schema; explicitly deferred to v1.7 per EMAIL-07 | |
| In-line `audit_log` only (no `email_send_log` table) | Loses provider_message_id → status mapping for webhook UPDATEs | |

**Auto-mode selection:** Webhook records only; aggressive `email_verified=false` flipping deferred to v1.7. `email_send_log.status` lifecycle: `sent` (insert at ARQ task success) → `delivered`/`bounced`/`complained` (UPDATE at webhook receipt) or → `rejected` (insert directly for terminal blocked/permanent_error).

---

## OTP email channel (AUTH-EM-01..04)

| Option | Description | Selected |
|--------|-------------|----------|
| `users.email_verified BOOLEAN DEFAULT FALSE` column + anti-oracle 202 for `email_verified=false`; manual SQL bootstrap for owner; verify-flow set side deferred to Phase 43 | Conservative; preserves anti-oracle; defers open conflict #7 cleanly; Phase 42 only adds the read side | ✓ (D-42-21..22) |
| `email_verified` default TRUE for existing operators (backfill in migration) | Risky — silently grants email-OTP access to all existing users without explicit verification | |
| Trust `users.email IS NOT NULL` (no `email_verified` column at all) | Pushes the verify-flow policy decision into ad-hoc code reads; collides with Phase 43 verify-flow design | |
| Bypass anti-oracle for `email_verified=false` (return 4xx) | Catastrophically breaks PITFALLS 1 + AUTH-EM-04 anti-oracle assertion | |

**Auto-mode selection:** Ship `email_verified` column with FALSE default; AUTH-EM-02 anti-oracle 202 silently drops unverified-email requests with bounded-equal timing; Phase 43 owns the verify-flow set side. Migration body carries operator-bootstrap SQL example as comment (not executed).

**TTL/cooldown/attempts:** 10min TTL (AUTH-EM-02 verbatim); 60s resend cooldown (existing per-user mechanism); max 5 attempts (existing `otp_codes.attempts` field); second request invalidates first (RFC 6238).

**Template `EMAIL_OTP_LOGIN`:** Subject `"Код входа в Sportzal"` (locked Final[str]); body contains only the 6-digit code + 10-min TTL note (no `{full_name}` — anti-oracle for stolen-email replay).

---

## `EmailDispatcher` registration — REG-29-03 double-wire

| Option | Description | Selected |
|--------|-------------|----------|
| Register in BOTH `app/main.py:create_app()` AND `WorkerSettings.on_startup`; parity test extension | REG-29-03 non-negotiable lesson (v1.3 lineage); makes the slot work for both HTTP handler enqueues and ARQ-internal re-enqueues | ✓ (D-42-25..26) |
| Register only in `app/main.py` | ARQ worker container imports the module but registration runs only at FastAPI boot — worker startup might not see the dispatcher | |
| Register only in `WorkerSettings.on_startup` | HTTP handler enqueues would fail with `get_email_dispatcher()` defensive-raise | |

**Auto-mode selection:** Double-wire. Phase 42 is the first phase exercising this slot; the parity test for `EmailDispatcher` extends the existing REG-29-03 test infrastructure.

---

## Configuration + sandbox mode (EMAIL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| `EmailProviderSettings` Pydantic block with `provider: Literal['yandex_postbox','sandbox']` + boot-time validator + domain probe via `sesv2.get_email_identity` | EMAIL-02 verbatim; fail-fast at boot mirrors v1.2 D-18 ARQ on_startup | ✓ (D-42-28..30) |
| `EMAIL_*` env vars without nested Pydantic block | Loses validator + breaks the Settings nested-block convention | |
| Sandbox mode = `moto[ses]` only at test boundary | Doesn't cover docker compose dev path; tests would pass but docker compose up wouldn't have a working email path | |
| Skip boot-time domain probe | Risks production sends from `sandbox.resend.dev` (PITFALLS 6 scenario) | |

**Auto-mode selection:** `EmailProviderSettings` with two-tier sandbox protection (`provider='sandbox'` literal OR `sandbox_mode=True` boolean); `model_validator` enforces non-empty `from_domain` + `webhook_secret` + AWS credentials in non-sandbox; boot-time `sesv2.get_email_identity(EmailIdentity=from_domain)` asserts `VerificationStatus='Success'` for non-sandbox.

**Sandbox mode behavior:** Log envelope at INFO level + return `EmailSendResult.ok(provider_message_id=f'sandbox-{uuid4()}')` without provider call. Used by `docker compose up` dev + CI + unit tests.

---

## Migration packaging

| Option | Description | Selected |
|--------|-------------|----------|
| 3 sequential migrations 0026 → 0028 (email_send_log; otp_codes.channel; users.email_verified) | Mirrors Phase 41 D-41-15 one-logical-change-per-file discipline | ✓ (D-42-31) |
| Single omnibus migration 0026 | Harder to round-trip-verify; loses Alembic-bisectability if any one change has drift | |
| Defer `users.email_verified` to Phase 43 | Couples Phase 42 AUTH-EM-02 read to Phase 43 schema; breaks dependency chain | |

**Auto-mode selection:** 3 separate Alembic files in dependency order. All `op.f()`-wrapped naming convention. Each round-trip clean.

---

## Claude's Discretion

- Exact SQL syntax of migrations 0026 / 0027 / 0028 (follows Phase 41 0024/0025 precedent — planner produces final files).
- Redis sliding-window circuit-breaker primitives (ZADD/ZREMRANGEBYSCORE on TTL'd sorted set is the standard; specifics left to planner).
- Yandex Cloud Postbox SES-V2 request-shape boilerplate (`Destination`, `Content.Simple.*` — provider-doc-derived).
- Module path for the per-module template registry walker helper (`_resolve_template`) — likely `app/integrations/email/dispatcher.py`.
- HTML email visual styling beyond locked Russian copy (plain inline styles allowed for OTP code emphasis; no CSS framework; no `<table>` layout needed).
- Structlog field shape for sandbox-mode envelope logging.
- Where to mount the bounce webhook router (recommend `app/api/v1/_internal/...` existing pattern — pure-transport concern, not a feature module).
- Exact filename of the existing REG-29-03 parity test (verify during plan-phase before extending).

---

## Deferred Ideas

- **Unisender Go fallback adapter implementation** — v1.7+. Documented but not built.
- **`email_verified` verify-flow set side** — Phase 43 (open conflict #7).
- **Aggressive bounce-driven `email_verified=false` flag flipping** — v1.7 (EMAIL-07 explicit).
- **Reply-to / `bounces@sportzal.ru` mailbox** — v1.7+.
- **DMARC `p=quarantine` flip after 7 clean-report days** — Operator action, post-Phase 42.
- **DMARC `p=reject`** — v1.7.
- **`clients.preferred_channel ∈ {auto, telegram, email, both}`** — Phase 45 NOTIFY-* scope.
- **Per-recipient rate limit (≤3 OTPs/hour)** — v1.7+ if abuse appears.
- **Owner weekly digest (bounces, deactivations, failed sends)** — v1.7+; needs ≥1 month of `email_send_log` data.
- **In-app inbox / marketing campaigns / preference centre / TOTP / WebAuthn / custom RBAC roles** — Explicit anti-features per FEATURES.md.
- **`premailer` HTML CSS-inliner** — Skipped per STACK.md.
- **Phase 41 deferred ORM drift items** (`users.email` UNIQUE removal; `users.deleted_at` ORM mapping; `*_notifications.channel` ORM columns) — Phases 43/45 own.
