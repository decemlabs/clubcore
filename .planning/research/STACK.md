# Stack — v1.6 Email channel + Multi-user admin

**Project:** Sportzal
**Milestone:** v1.6 — Email channel + Multi-user admin
**Researched:** 2026-05-18
**Confidence:** HIGH for email provider primary recommendation; HIGH for template engine; HIGH for token signer; MEDIUM for fallback provider rationale (РФ sanctions landscape moves fast — re-verify in Phase 41)

---

## TL;DR

| Concern | Recommendation | Why |
|---|---|---|
| Email provider (primary) | **Yandex Cloud Postbox** (`postbox.cloud.yandex.net`, SES-V2-compatible) via `aioboto3` | Russian legal entity → no sanctions risk, no DNS/egress filtering, no payment-blocker; AWS SDK contract preserved (no vendor-bespoke API to learn); 2,000 free emails/month covers >3× expected v1.6 volume; РФ data residency satisfies 152-ФЗ; native deliverability to mail.ru/yandex.ru/rambler.ru |
| Email provider (fallback) | **Unisender Go** (`goapi.unisender.ru`) — HTTPS POST API + first-party `unisender-go-api` SDK | Pure-РФ alternative if Yandex Cloud credentials are unavailable; SPF/DKIM/DMARC pre-configured for shared sending domain |
| Sending pattern | **ARQ-enqueued background job, not synchronous from handler** | Same discipline as Telegram OTP (v1.1 D-06 lesson — never block HTTP handler on egress); handler emits `email_send_requested` audit row before enqueue; worker emits `email_sent` / `email_send_failed_*` |
| New docker-compose services? | **No.** Reuse existing `arq-worker` service | Email send is fire-and-forget like the 7 existing cron jobs; another long-running process is unjustified for ≤500 emails/month |
| Template engine | **Jinja2 3.1.x in `SandboxedEnvironment`**, sync mode | Already transitively in dep tree (FastAPI `Jinja2Templates`); industry standard; locked Russian templates live as `.html` + `.txt` siblings under `app/integrations/email/email_templates/` |
| Reset-password token signer | **itsdangerous 2.2.x `URLSafeTimedSerializer`** | Stateless signed token = no DB row, no Redis row, no cleanup cron; max-age built-in; HMAC-SHA256 keyed off `JWT_SECRET_KEY` with `salt='password-reset-v1'` for domain isolation; single-use via `password_changed_at` embedded in payload |
| Anti-oracle on reset endpoint | **POST `/auth/password-reset/request` always returns 202 Accepted regardless of email existence** | Mirrors v1.1 `bot_not_started` / v1.2 `/checkin` "same DM for stranger and active" anti-oracle invariant — never let unauthenticated probe distinguish "user exists" from "user does not" |

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Yandex Cloud Postbox** | SES-V2-compatible endpoint `https://postbox.cloud.yandex.net` | Outbound transactional email (OTP fallback, expiring-soon mirror of Telegram DM, payment receipt, booking confirm/remind, password-reset link, user-invitation link) | (1) Domestic РФ legal entity — no sanctions exposure for operator or gym; (2) **SES-V2-API-compatible** — backend code stays portable: same `send_email` shape works against AWS SES if/when the project ever leaves РФ; (3) 2,000 free emails/month — for 1 gym with ~500 emails/month expected v1.6 load the free tier alone covers >3× margin; (4) AWS Signature V4 auth using static access keys (already supported in Yandex Cloud IAM); (5) 152-ФЗ data residency in-РФ should personal-data scope ever require it; (6) native deliverability to mail.ru/yandex.ru — same datacentres as the recipient providers |
| **aioboto3** | `>=13.0,<14` (wraps boto3 1.35+) | Async SES-V2 client for Postbox endpoint | Async-native (won't block the event loop); thin wrapper over boto3 so configuration is boto3-standard; only need `sesv2.send_email`; the `endpoint_url` parameter overrides AWS default to Postbox endpoint without monkey-patching |
| **Jinja2** | `>=3.1.4,<4` (3.1.x line; 3.1.6 latest) | Render locked Russian email templates (HTML + plain-text alternative MIME parts) | Industry standard in Python web ecosystem; FastAPI already depends on it transitively (`fastapi[all]` ships `jinja2`); `SandboxedEnvironment` for defence-in-depth even though all templates are first-party (consistent with locked-DM-copy discipline from v1.2/v1.3); sync mode correct — template render is CPU-bound µs work, not I/O |
| **itsdangerous** | `>=2.2.0,<3` | Sign reset-password + multi-user-invitation tokens | Stateless (no DB row to clean up, no Redis row to expire); `URLSafeTimedSerializer.dumps(payload)` / `.loads(token, max_age=N)` is the entire API surface; HMAC-SHA256 internally; separate `salt=` per token kind isolates blast radius (`'password-reset-v1'` vs `'user-invitation-v1'`); Python 3.12 supported; same Pallets-project provenance as Jinja2 — no new vendor footprint |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **email-validator** | `>=2.2,<3` (transitive via Pydantic `EmailStr`) | Validate email shape at API boundary | Already present transitively via Pydantic v2 `EmailStr`; **do not** add a separate runtime MX check in the request handler (DNS round-trip during HTTP = anti-pattern); rely on Pydantic-level format validation only; let bounces handle bad domains async |
| **aiosmtplib** | `>=3.0,<6` | Async SMTP client | **Fallback only** for Unisender Go SMTP path (port 465 SSL, `use_tls=True`); if Yandex Cloud Postbox SES-V2-API path works, do not add this dep |
| **unisender-go-api** | latest from PyPI | First-party РФ Unisender Go SDK | **Fallback only** — install instead of aioboto3 if EMAIL_PROVIDER=unisender selected; thin httpx wrapper with sync+async support |
| **premailer** | DO NOT ADD | CSS-inline for HTML emails | Skip — v1.6 templates are deliberately plain (1 H1 + 2-3 paragraphs + 1 CTA button, no CSS classes); inlining is premature optimisation for transactional-only emails |
| **fastapi-mail** | DO NOT ADD | Convenience wrapper on aiosmtplib | Skip — opinionated wrapper that re-implements config layer in Pydantic v1 idioms; conflicts with `app/core/config.py`; direct aiosmtplib/aioboto3 is ~15-20 lines |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **mailpit** (or **MailHog**) | Local SMTP catcher for dev | Add `mailpit` as a docker-compose service **only in a `docker-compose.dev.yml` overlay** if needed — do not pollute canonical `docker-compose.yml`; backend wires to it when `EMAIL_PROVIDER=smtp_dev` env var is set; port 1025 SMTP, port 8025 web UI |
| **moto[ses]** | Mock SES-V2 for unit tests | `moto>=5.0` library mocks AWS service calls including SES-V2; install in dev-deps so `aioboto3` calls in pytest stay offline |
| **respx** | (likely already present transitively via httpx test stack) HTTP mock for Unisender Go fallback path tests | Mocks `httpx` calls if Unisender Go fallback is wired |

---

## Installation

```bash
# Inside apps/backend/, via uv:

# Core (primary path — Yandex Cloud Postbox)
uv add 'aioboto3>=13.0,<14'           # async SES-V2 client (Postbox endpoint)
uv add 'jinja2>=3.1.4,<4'             # explicit dep, not transitive
uv add 'itsdangerous>=2.2.0,<3'       # signed-token serializer (reset + invitation)

# Conditional (only if Unisender Go fallback enabled at deploy time)
# uv add 'unisender-go-api'           # first-party Python SDK
# uv add 'aiosmtplib>=3.0,<6'         # only if SMTP path chosen over JSON API path

# Dev dependencies (PEP 735 [dependency-groups].dev)
uv add --dev 'moto[ses]>=5.0,<6'      # mock SES in tests
# mailpit runs as docker-compose service, not python dep
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not Default |
|-------------|-------------|-----------------|
| Yandex Cloud Postbox | **AWS SES (eu-central-1 / eu-north-1)** | Theoretically the same API surface; rejected because (a) the operator entity is in РФ — paying AWS in $ is increasingly friction-laden post-2022 sanctions, account/billing can fail at any renewal; (b) deliverability from non-РФ AWS region to mail.ru/yandex.ru is unpredictable — Russian providers heavily reputation-filter AWS IP ranges; (c) data residency story is wrong for any future 152-ФЗ scope |
| Yandex Cloud Postbox | **Resend** | Excellent DX, but (a) no РФ legal entity, no РФ datacentre — deliverability to yandex.ru rate-limited by source-IP reputation; (b) payment via Stripe (same blocker as ЮKassa-vs-Stripe in v1.7 billing) — Stripe is already in Out-of-Scope per CLAUDE.md "Stripe запрещён"; (c) no 152-ФЗ compliance story |
| Yandex Cloud Postbox | **Mailgun (US/EU)** | Same Resend objections + Mailgun's Russian deliverability has been observably degraded since 2022 (US-domiciled, no datacentre near РФ recipients) |
| Yandex Cloud Postbox | **SendPulse** | Documented as "restricted service for users from Russia" — disqualified at face for a РФ-market default |
| Yandex Cloud Postbox (primary) | **Unisender Go** (fallback) | Pure-РФ alternative; chosen as documented secondary, **not primary**, because: (a) bespoke HTTP API requires a project-specific SDK (`unisender-go-api`) rather than the standard AWS SDK contract — locks the project to a single vendor; (b) Postbox's free tier is more generous and clearly documented for the v1.6 volume profile (2,000/mo); (c) SES-V2 API skill carry-forward — Postbox → AWS SES is a same-API drop-in if the project ever migrates outside РФ |
| Jinja2 SandboxedEnvironment | **MJML + mjml-python or mrml** | MJML produces gorgeous responsive HTML; rejected because (a) v1.6 emails are 1-screen transactional, responsive design is overkill; (b) extra build step (MJML compiler) adds CI complexity for ~5 templates; (c) Russian-text body content does not benefit from MJML's component library |
| Jinja2 SandboxedEnvironment | **str.format / f-strings on a `.txt` const** | Used for Telegram DMs (`app/modules/.../notifications.py` module-level Russian str constants); rejected for email because (a) emails need both `text/plain` and `text/html` MIME parts — two separate Jinja2 templates is cleaner than parallel f-strings; (b) v1.6 expiring-soon email mirrors a 7d/3d/1d × variant A/B matrix already proved out for Telegram → variable interpolation count is meaningful (`{full_name}`, `{end_date}`, `{plan_name}`, `{reset_link}`) — Jinja2 escaping defaults safer than manual interpolation, especially around the `{end_date}` Russian-long-form date |
| itsdangerous URLSafeTimedSerializer | **PyJWT / python-jose (HS256)** | Already in stack via `python-jose` for auth tokens; rejected for reset-password because (a) reset-token does not need to carry claims beyond `user_id` + `kind`; (b) using JWT for a fundamentally different security context (short-lived, single-use, email-delivered) blurs the threat model — `itsdangerous` having a different `salt=` per kind is clearer domain separation than `aud='password-reset'` inside a JWT and hoping every consumer checks it; (c) reset tokens should NOT be in the same revocation family as access/refresh — itsdangerous is stateless by design, JWT-via-database-revocation-list is the wrong shape |
| itsdangerous URLSafeTimedSerializer | **Random 32-byte CSPRNG token stored in `password_reset_tokens` table** | Classic Django-style approach; rejected because (a) introduces a new table + a cleanup cron just to delete expired rows; (b) itsdangerous gives the same security guarantees stateless if `password_changed_at` is included in the signed payload (token auto-invalidates on use); (c) HMAC over `(user_id, password_changed_at, kind)` is exactly the recipe for "single-use" without a DB row |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Stripe-billed email providers (Resend, Mailgun)** | Stripe is in project Out-of-Scope per CLAUDE.md and PROJECT.md Key Decision row; the same payment-rail risk that excluded Stripe for ЮKassa applies to vendor subscriptions | Yandex Cloud Postbox (bills in ₽ against Yandex.Balance) |
| **Synchronous SMTP/HTTP send from HTTP handler** | Same anti-pattern as synchronous Telegram bot send (v1.1 D-06); an egress hang stalls the FastAPI worker; HTTP request becomes hostage to provider P99 | Enqueue ARQ job; handler emits `email_send_requested` audit row and returns 202/204 |
| **`fastapi-mail` library** | Opinionated wrapper that re-implements config layer in Pydantic v1 idioms; conflicts with `app/core/config.py`; adds 5 transitive deps for what is ~20 lines of direct aiosmtplib/aioboto3 | Direct `aioboto3.client('sesv2', endpoint_url=...)` from `app/integrations/email/client.py` |
| **Storing reset tokens in Redis with TTL** | A signed token that survives Redis flush is a feature, not a bug; signed tokens auto-invalidate on `password_changed_at` change (cheaper than Redis cleanup) | itsdangerous signed token with embedded `password_changed_at` |
| **`POST /auth/password-reset/request` returning 404 when email not found** | Account enumeration oracle — identical anti-pattern to v1.2 D-20-9 `/checkin` "stranger vs expired" and v1.3 expiring-soon "frozen-vs-active" anti-oracles | **Always** return 202 Accepted; worker silently no-ops for unknown email; audit row emitted in both branches for completeness |
| **Different response time for "user exists" vs "does not"** | Timing-side-channel restores the oracle that the 202 hides | Worker enqueues the same dummy work in both branches (e.g. compute a fake hash) or the handler returns 202 immediately before the lookup |
| **Multi-recipient `BCC:` for OTP/reset emails** | Mass-mail anti-pattern + privacy bug | One ARQ job per recipient; provider-side batching is provider's problem |
| **Premailer / CSS inliner** | Premature optimisation — v1.6 templates use 0 CSS classes by design | Plain inline `<style>` block with ≤5 selectors |
| **Custom HMAC implementation for reset tokens** | "Roll-your-own crypto" anti-pattern; signing/timing/encoding edge cases are non-trivial | `itsdangerous` (battle-tested since 2011, Pallets-maintained) |
| **`mailgun-python` SDK** | Vendor lock + sanctioned-vendor risk above | aioboto3 against SES-V2 endpoint (works for both Postbox and AWS SES) |

---

## Stack Patterns by Variant

**If Yandex Cloud credentials are available and provisioned (default path):**
- Use `aioboto3` against `endpoint_url='https://postbox.cloud.yandex.net'`
- Region: `ru-central1`
- Credentials: `YC_POSTBOX_ACCESS_KEY_ID` / `YC_POSTBOX_SECRET_ACCESS_KEY` env vars (separate from any future S3-compat creds; rotation-independent)
- Zero new docker-compose services: ARQ worker already running picks up the new `send_email` job kind

**If Yandex Cloud Postbox account cannot be created yet (deferred-to-Phase-43 path):**
- Use Unisender Go HTTPS POST API via `httpx.AsyncClient` (or `unisender-go-api` SDK)
- Endpoint: `https://goapi.unisender.ru/ru/transactional/api/v1/email/send.json`
- Same ARQ-job shape; only the `EmailProvider` Protocol implementation differs
- Provider selection via env: `EMAIL_PROVIDER ∈ {postbox, unisender, smtp_dev, stub}` defaulting to `postbox`

**If running locally (dev):**
- `mailpit` docker-compose service in `docker-compose.dev.yml` overlay if introduced (NOT canonical compose)
- Backend uses `aiosmtplib` to `mailpit:1025` when `EMAIL_PROVIDER=smtp_dev`
- Confirms templates render and `From:` headers are correct without burning real provider credit

**If running tests:**
- `EMAIL_PROVIDER=stub` — `EmailProvider` Protocol implementation collects calls into an in-memory list
- Asserts in tests: "the rendered body for `expiring_7d_variant_A` was sent to `client@example.com` with `{full_name='Ivan'}`"
- Mirrors existing Telegram-bot test discipline (no real Telegram API calls in pytest)

---

## Integration with Existing Sportzal Patterns

This section is the load-bearing part for the roadmap. It locks how new dependencies plug into shapes already proved by v1.0–v1.5.

### Composition Root Pattern (lifts from v1.1 D-06, v1.2 D-10, v1.4 trainer-resolver, v1.3 REG-29-03)

```
app/integrations/email/
  client.py            # PostboxEmailClient + UnisenderEmailClient + SmtpDevEmailClient + StubEmailClient
                       # implementing the EmailProvider Protocol
  templates.py         # Jinja2 SandboxedEnvironment + render(template_id, ctx) -> (subject, text, html)
  email_templates/
    expiring_7d_variant_A.subject.txt
    expiring_7d_variant_A.text.txt
    expiring_7d_variant_A.html
    ... (≈16 files: 5 templates × where applicable A/B variants × 3 windows × 3 MIME parts)

app/modules/notifications/     # NEW v1.6 module — owns email-channel contracts
  service.py                   # NotificationsService — "send expiring-soon for membership X"
  schemas.py                   # EmailRender payloads (Pydantic, alias_generator=to_camel keeps wire format invariant)
```

- `app/main.py:create_app()` instantiates `EmailProvider` based on `settings.email_provider`, registers it via `register_email_provider(provider)` Protocol slot (parallel to v1.1 `register_user_loader`, v1.2 `register_active_membership_resolver`, v1.4 `register_trainer_by_id_resolver`)
- `app/workers/__init__.py:WorkerSettings.on_startup` performs the same registration for the ARQ worker context — **this is non-negotiable per the v1.3 REG-29-03 regression lesson** (the bot worker silently failed because resolver registrations were forgotten in `app/workers/telegram_bot.py:main()`; same hazard applies here for the ARQ worker)
- `app/workers/telegram_bot.py:main()` does NOT register the email provider — Telegram bot worker doesn't send email (architectural cleanliness; if a Telegram handler ever needs to trigger an email it goes through `notifications.service`, not direct provider call)

### ARQ Job Shape (lifts from v1.2 ARQ-TEST-01, v1.3 expiring-soon Phase 27, v1.5 booking reminders Phase 40)

```python
# app/workers/email_jobs.py
async def send_email(ctx: dict, *, recipient: str, template_id: str, payload: dict) -> None:
    """ARQ task — single recipient, single template, audit-logged."""
    # 1. render template (CPU, ~µs)
    # 2. await provider.send_email(...)
    # 3. on success: audit.emit("email_sent", actor_user_id=None, ...)
    # 4. on transient failure (5xx / connection): raise → ARQ retry
    # 5. on permanent failure (4xx invalid recipient): audit.emit("email_send_failed_permanent", ...); DO NOT raise
```

- `WorkerSettings.functions` extended with `send_email` (existing 7 cron jobs unchanged)
- ARQ `retry` semantics: max 3 retries with exponential backoff (matches v1.5 booking reminders)
- Idempotency: NEW table `email_send_attempts (job_uuid PK, recipient_email, template_id, status, attempted_at)` prevents re-render/re-send on ARQ retry storm (mirrors v1.3 `membership_notifications` and v1.5 `booking_notifications` semantics)

### Audit Events (extends `LOCKED_AUDIT_EVENTS` 56 → ~64)

Provisional list for the roadmap to fix in stone in Phase 41 (canonical Pydantic `audit_payloads.py` model required per the v1.4 INFRA-19 pattern):
- `email_send_requested` — emitted by the HTTP handler before enqueue
- `email_sent` — emitted by ARQ worker on provider 2xx
- `email_send_failed_permanent` — emitted by ARQ worker on 4xx (e.g. invalid recipient)
- `email_send_failed_transient` — emitted by ARQ worker on retry exhaustion
- `password_reset_requested` — always emitted (even if user does not exist) for anti-oracle audit completeness
- `password_reset_completed` — emitted when reset token consumed successfully
- `user_invited` — owner-only multi-user-admin: emitted on `POST /api/v1/users`
- `user_deactivated` — owner-only soft-delete equivalent on users
- `user_activated` — re-enable a deactivated operator

Exact count and naming are roadmap-deferred to Phase 41; what's locked here is the **shape**: each pair `*_requested` + `*_completed/_failed` so failed sends are auditable separately from successful sends, matching v1.4 `payment_recorded` + `payment_refunded` shape, and v1.3 `expiring_notification_sent_{7d,3d,1d}`.

### Reset-Password Single-Use Discipline

```python
# app/modules/auth/password_reset.py
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_serializer = URLSafeTimedSerializer(settings.jwt_secret_key, salt='password-reset-v1')

def issue_token(user_id: UUID, password_changed_at: datetime) -> str:
    return _serializer.dumps({'uid': str(user_id), 'pca': password_changed_at.isoformat()})

def consume_token(token: str, current_password_changed_at: datetime, *, max_age_seconds: int = 3600) -> UUID:
    payload = _serializer.loads(token, max_age=max_age_seconds)  # raises BadSignature / SignatureExpired
    uid = UUID(payload['uid'])
    if payload['pca'] != current_password_changed_at.isoformat():
        raise BadSignature("token consumed (password already changed)")
    return uid
```

The `pca` (password_changed_at) field is the single-use mechanism: as soon as the user's password is updated, every previously-issued reset token mathematically fails the `pca` equality check on next `consume_token`. No DB row, no Redis row, no cleanup cron. Same pattern works for `user-invitation-v1` salt — invitation token expires automatically on first password-set (which updates `password_changed_at`).

Implication: `users` table needs a `password_changed_at TIMESTAMPTZ NOT NULL` column added by Alembic migration in v1.6 Phase 41. v1.1 wrote `password_hash` updates but no explicit `password_changed_at` (the FK chain is fine to read via `users.updated_at` if no separate password-only update path exists, but a dedicated column is cleaner and audit-friendly).

### CSRF + Rate-Limit Surface

- `POST /api/v1/auth/password-reset/request` — **no CSRF dependency** (unauthenticated endpoint, same shape as `/auth/login`); rate-limit `5/15min per IP` matching v1.1 login rate-limit
- `POST /api/v1/auth/password-reset/confirm` — **no CSRF dependency** (unauthenticated, presents token from email); rate-limit `5/15min per IP`; token validated via `consume_token`
- `POST /api/v1/users` (multi-user invite) — owner-only via `Depends(require_permission(Action.CREATE, Resource.USERS))`, CSRF-mandatory (per existing `verify_csrf` discipline on POST/PATCH/DELETE)
- `PATCH /api/v1/users/{id}/deactivate` — owner-only, CSRF-mandatory
- `PATCH /api/v1/users/{id}/activate` — owner-only, CSRF-mandatory
- `Resource.USERS` is a new entry on the `Resource` enum; `(CREATE, USERS)` + `(UPDATE, USERS)` + `(DELETE, USERS)` (used for soft-delete) all join `OWNER_ONLY` (extending 26 → 29). The three-way parity test (backend `permissions.py` ↔ admin-web `can.ts` ↔ `registry.ts`) must be updated. **However, admin-web is frozen at v1.3 baseline per the 2026-05-15 pivot** — only the backend-side `OWNER_ONLY` frozenset is updated; the parity test's `frozen-admin-web` branch already accommodates v1.4+ owner-only additions

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `aioboto3>=13.0` | `boto3>=1.35`, `botocore>=1.35`, `aiohttp>=3.10` | aioboto3 13.x pins boto3 13 line; current backend doesn't ship boto3 yet so cleanroom add is safe; verify against existing pyproject locks before merge |
| `jinja2>=3.1.4` | `MarkupSafe>=2.1` | Both Pallets-project; `MarkupSafe` is already transitive via FastAPI's `jinja2` extra — explicit pin avoids the FastAPI-extras-removal pitfall |
| `itsdangerous>=2.2.0` | Python 3.8+ (we use 3.12) | Standalone, no version-pinning conflicts with auth deps |
| `moto[ses]>=5.0` | `boto3>=1.34` | dev-deps only; tested with aioboto3 13 line per moto changelog |

---

## РФ-Accessibility Verification Notes (MEDIUM confidence, snapshot 2026-05-18)

Sanctions and provider policies move fast. Anchor observations as of the research date — re-verify in Phase 41:

- **Yandex Cloud** continues to operate as a Russian-registered cloud platform with rouble billing; Postbox is GA and not behind a special-application gate.
- **AWS SES** remains technically accessible from РФ networks, but (a) AWS account creation/billing requires a non-РФ-resident credit card in practice, and (b) deliverability to `mail.ru` / `yandex.ru` from US/EU AWS IPs is observably worse than from in-РФ infrastructure — this is the substantive deliverability argument, separate from the legal/payment argument.
- **Resend** has no РФ datacentre; deliverability is reputation-dependent on its US/EU outbound IPs; account creation requires Stripe billing (excluded by project constraint).
- **Mailgun** same shape as Resend; additionally, post-2022 Mailgun has reportedly de-prioritised support for Russian-domain recipients in their reputation pipeline (multiple anecdotal reports — flagged LOW confidence on the specific de-prioritisation claim, but HIGH confidence that Mailgun has no positive РФ deliverability story).
- **Unisender Go** is the РФ-domestic transactional product of Unisender (the largest РФ-domestic email service); GA with documented Python SDK (`unisender-go-api`) and SPF/DKIM/DMARC pre-configured for shared sending domains.
- **SendPulse** explicitly notes "restricted service for users from Russia" — disqualified for the primary use case.

Bottom-line confidence: Yandex Cloud Postbox is the operationally-safest primary choice for a РФ-domiciled gym CRM as of 2026-05. Unisender Go is the documented backup. Re-verification in Phase 41 should check (1) Postbox is still GA and not behind a quota wall for new accounts, and (2) Unisender Go pricing hasn't degraded for the <500/mo volume.

---

## Sources

- [Yandex Cloud Postbox — Service page](https://yandex.cloud/en/services/postbox) — HIGH (official); confirms SES-V2 API + Python SDK support + 152-ФЗ + ISO/PCI DSS/GOST R 57580 compliance claim
- [Yandex Cloud Postbox — Pricing (RU)](https://yandex.cloud/ru/docs/postbox/pricing) — HIGH (official); 2,000 free emails/month, tiered ₽-pricing thereafter (80.32/70.15/59.98 ₽ per 1,000 emails), billed regardless of delivery status
- [Yandex Cloud Postbox — Quotas/Limits](https://yandex.cloud/en/docs/postbox/concepts/limits) — HIGH (official); default quotas raisable via support
- [Yandex Cloud Postbox — Send email via AWS SDK](https://yandex.cloud/en/docs/postbox/operations/send-email) — HIGH (official); confirms Python SDK is officially supported (.NET / Go / JS / Python)
- [Amazon SES Regions list](https://docs.aws.amazon.com/ses/latest/dg/regions.html) — HIGH (official); confirms no РФ region; closest is Stockholm/Frankfurt/Milan/Zurich
- [Amazon SES product page](https://aws.amazon.com/ses/) — HIGH (official); SES baseline reference for the SDK-API-compatibility argument
- [aioboto3 PyPI](https://pypi.org/project/aioboto3/) — HIGH; async wrapper, current major 13.x; tracks boto3 1.35+
- [Jinja2 PyPI](https://pypi.org/project/Jinja2/) — HIGH; latest 3.1.6 in 3.1.x line, MarkupSafe transitive
- [Jinja2 Sandbox docs (stable)](https://jinja.palletsprojects.com/en/stable/sandbox/) — HIGH (official); SandboxedEnvironment is the documented entry point for restricted template render
- [itsdangerous PyPI](https://pypi.org/project/itsdangerous/) — HIGH; 2.2.0 released 2024-04-16, Python 3.8+, used by Flask family; URLSafeTimedSerializer is the documented entry-point for this use case
- [itsdangerous documentation (stable)](https://itsdangerous.palletsprojects.com/) — HIGH (official); confirms HMAC-SHA256 default + `salt=` domain separation + `max_age=` time-bound
- [aiosmtplib PyPI](https://pypi.org/project/aiosmtplib/) — HIGH; 5.1.0 (Jan 2026), Python 3.10+, async SMTP, port 465 SSL via `use_tls=True`
- [aiosmtplib docs — usage](https://aiosmtplib.readthedocs.io/en/latest/usage.html) — HIGH (official); async context-manager pattern for SMTP
- [Unisender Go API reference](https://godocs.unisender.ru/web-api-ref) — HIGH (official); HTTPS POST JSON contract, multiple-datacentre endpoints
- [unisender-go-api PyPI](https://pypi.org/project/unisender-go-api/) — MEDIUM (first-party Python SDK); Python 3.10+, sync + async support
- [SendPulse — RU restriction note (Unisender comparison page)](https://sendpulse.com/ru/features/email/comparison/unisender) — MEDIUM (vendor comparison page); disqualifies SendPulse for РФ operators
- [moto[ses] documentation](https://docs.getmoto.org/en/latest/docs/services/ses.html) — HIGH (official); SES-V2 mocking supported

---

*Stack research for: Sportzal v1.6 Email channel + Multi-user admin*
*Researched: 2026-05-18*
