# Phase 42: Email Transport Layer + Email OTP Fallback — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 24 (19 new, 5 modified)
**Analogs found:** 24 / 24 (100% coverage — every Phase 42 file has a canonical mirror in the v1.0–v1.5 codebase)

The Phase 42 design intentionally mirrors the **Telegram outbound stack** (v1.1/v1.4 lineage) line-for-line:

| Telegram (existing) | Email (Phase 42) |
|---|---|
| `app/integrations/telegram/sender.py` `SendResult` | `app/integrations/email/types.py` `EmailSendResult` |
| `app/integrations/telegram/bot.py` `build_bot()` | `app/integrations/email/factory.py` `build_email_client()` |
| `app/workers/scheduled/send_*` cron tasks | `app/workers/tasks/dispatch_email.py` task |
| `auth.telegram_service.consume()` Telegram OTP path | `auth.service.request_otp_email()` Email OTP path |
| Alembic 0024 `channel` discriminator on notifications | Alembic 0027 `channel` discriminator on `otp_codes` |
| Alembic 0025 `password_reset_tokens` new table | Alembic 0026 `email_send_log` new table |

That mirror-mapping is the **organising principle** of every pattern assignment below. When the planner writes an action for a Phase 42 file, the analog's body shape (imports, error classification, `audit.emit` placement, commit discipline, log-event naming) transfers verbatim — only the domain nouns change.

---

## File Classification

| File | New/Mod | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|---|
| `app/integrations/email/client.py` | MOD (replace placeholder) | integration | request-response (HTTPS to provider) | `app/integrations/telegram/sender.py` | exact (sender pattern) |
| `app/integrations/email/factory.py` | NEW | integration / factory | DI | `app/integrations/telegram/bot.py` `build_bot()` | exact |
| `app/integrations/email/dispatcher.py` | NEW | Protocol impl (enqueuer) | event-driven (enqueue) | `app/integrations/telegram/sender.py` + `auth.service.issue_tokens` enqueue patterns | partial (no exact "Protocol-impl-as-module-function" precedent yet — Phase 42 establishes it) |
| `app/integrations/email/types.py` | NEW | DTO / dataclass | data-shape | `app/integrations/telegram/sender.py:SendResult` | exact |
| `app/integrations/email/models.py` | NEW | ORM model | persistence | `app/modules/auth/password_reset_token_model.py` | exact |
| `app/workers/tasks/dispatch_email.py` | NEW | ARQ task | event-driven (consume) | `app/workers/scheduled/send_expiring_notifications.py` + `send_booking_reminders.py` | exact (transactional-with-audit task shape) |
| `app/modules/auth/email_templates.py` | NEW | per-module template registry | static data | `app/integrations/telegram/copy.py` (Telegram copy registry) + `auth.telegram_service._OTP_DM_TEMPLATE` | partial (Telegram is f-string; Phase 42 establishes Jinja2 registry) |
| `app/modules/auth/service.py` (`request_otp_email`) | MOD | service entry | request-response | `auth.service.authenticate` (anti-oracle constant-time floor) + `auth.telegram_service.start_deep_link` (OTP mint) | exact |
| `app/modules/auth/router.py` (`/auth/otp/request`) | MOD | HTTP route | request-response | `auth.router.telegram_start` + `telegram_verify` | exact |
| `app/modules/auth/schemas.py` (`OtpRequestBody`) | MOD | Pydantic body | data-shape | `auth.schemas.LoginRequest` + `TelegramVerifyRequest` | exact |
| `app/api/v1/_internal/email/router.py` | NEW | HTTP webhook route | request-response (signed) | `auth.router.telegram_verify` (signed-body verify) + `dependencies.verify_csrf` (HMAC compare_digest) | partial (no `_internal` mount exists yet — Phase 42 establishes the convention) |
| `app/core/config.py` (`EmailProviderSettings`) | MOD | Pydantic settings block | config | `app/core/config.py:Settings` (telegram_bot_token + otp_*_ttl_seconds) | exact |
| `app/main.py` (`register_email_dispatcher`) | MOD | composition root | wiring | `app/main.py:create_app()` existing `register_*` block | exact |
| `app/workers/__init__.py` (WorkerSettings) | MOD | composition root | wiring | `app/workers/__init__.py:WorkerSettings.on_startup` (db_lifespan + cron-resolution invariant) | exact |
| `alembic/versions/0026_email_send_log.py` | NEW | migration (new table) | DDL | `alembic/versions/0025_password_reset_tokens.py` | exact |
| `alembic/versions/0027_otp_codes_channel_discriminator.py` | NEW | migration (column + partial-UNIQUE recreate) | DDL | `alembic/versions/0024_notification_channel_discriminator.py` | exact |
| `alembic/versions/0028_users_email_verified.py` | NEW | migration (column + DEFAULT FALSE) | DDL | `alembic/versions/0022_users_soft_delete_partial_unique.py` (User column add) | role-match |
| `alembic/env.py` | MOD | autogenerate registration | DDL | existing eager-import block at top of file | exact |
| `app/core/models.py` (`User.email_verified`) OR `app/modules/auth/models.py` (`OtpCode.channel`) | MOD | ORM column add | data-shape | `app/core/models.py:User` (`telegram_chat_id`) + `auth.models:OtpCode` shape | exact |
| `infra/dns/sportzal.ru.zone` | NEW | operator runbook (DNS spec) | docs | (no existing DNS zone file — operator runbook precedent: `DEFER-40-01` style header) | none (new artifact class) |
| `tests/integration/auth/test_otp_email_anti_oracle.py` | NEW | integration test | request-response | `tests/integration/auth/test_password_reset_no_oracle.py` | exact |
| `tests/test_compose_root_parity.py` (REG-29-03 parity) | MOD (extend) | integration test | static AST | `tests/integration/test_app_wiring.py` | exact |
| `tests/unit/test_locked_email_templates_ast.py` | MOD (extend) | unit test | static AST | existing file (Phase 41) — fixture extension | exact |
| `tests/unit/test_workers_eager_import.py` | MOD (extend) | unit test | static metadata | existing file (Phase 41) — assert extension | exact |

---

## Pattern Assignments

### 1. `app/integrations/email/types.py` — NEW (DTO, frozen dataclass)

**Analog:** `app/integrations/telegram/sender.py` lines 22–37 (`SendResult` dataclass).

**Imports + dataclass shape pattern** (lines 1–37, mirror verbatim with email-domain failure modes):

```python
from __future__ import annotations
from dataclasses import dataclass

# Mirror SendResult — frozen dataclass with classified failure modes; downstream
# match-statement uses exhaustiveness; transport NEVER re-raises.

@dataclass(frozen=True)
class SendResult:
    ok: bool
    blocked: bool = False
    error: str | None = None
```

**Phase 42 derivation:**

```python
@dataclass(frozen=True)
class EmailEnvelope:
    to: str
    subject: str
    html: str
    text: str
    template_id: str  # MUST be a member of LOCKED_EMAIL_TEMPLATES
    audit_correlation_id: UUID

@dataclass(frozen=True)
class EmailSendResult:
    ok: bool
    classification: Literal["ok", "blocked", "transient_error", "permanent_error"]
    provider_message_id: str | None = None
    error: str | None = None
```

D-42-16 locks the `EmailEnvelope` field list; the classification literals mirror SendResult's `blocked`/`error` discipline.

---

### 2. `app/integrations/email/factory.py` — NEW (`build_email_client`)

**Analog:** `app/integrations/telegram/bot.py` lines 85–96 (`build_bot`).

**Factory shape pattern** (verbatim mirror):

```python
def build_bot(*, token: str) -> Bot:
    """Construct a bare Bot for outbound DM use ...
    Returns a FRESH Bot per call (no caching) — keeps the helper pure ...
    """
    return Bot(token=token)
```

**Phase 42 derivation (`build_email_client`):**

```python
def build_email_client(*, settings: EmailProviderSettings) -> aioboto3.Session:
    """Construct a fresh aioboto3 Session pointed at Yandex Postbox.
    
    Per D-42-02: provider SDK retries disabled (Config(retries={'max_attempts': 1})).
    Per D-42-30: when provider='yandex_postbox' AND sandbox_mode=False, call
    sesv2.get_email_identity(EmailIdentity=settings.from_domain) and assert
    VerificationStatus == 'Success'. Failure → RuntimeError at startup
    (mirrors v1.2 D-18 fail-fast).
    """
    if settings.provider == "sandbox" or settings.sandbox_mode:
        return _SandboxEmailClient()  # D-42-29 log+ok stub
    # ... aioboto3.Session with Config(retries={'max_attempts': 1}) ...
```

`build_bot` returns a FRESH instance per call (no module-level caching) — Phase 42 inherits the same discipline because aioboto3 sessions also carry aiohttp pools that must NOT leak across worker container restarts.

---

### 3. `app/integrations/email/client.py` — MODIFIED (replace placeholder)

**Current state** (`apps/backend/app/integrations/email/client.py` lines 1–5):

```python
"""Email client placeholder.

TODO Phase X+: async SMTP client (likely aiosmtplib) or transactional provider adapter
(SendGrid/Mailgun — provider TBD by region constraints).
"""
```

**Analog (for the real adapter):** `app/integrations/telegram/sender.py:send_otp_dm` lines 39–54.

**Outbound boundary + classified-failure pattern** (lines 39–54):

```python
async def send_otp_dm(bot: Bot, chat_id: int, code: str) -> SendResult:
    """Send the OTP code DM to chat_id. Never re-raises transport errors."""
    try:
        await bot.send_message(chat_id=chat_id, text=_OTP_DM_TEMPLATE.format(code=code))
        return SendResult(ok=True)
    except Forbidden:
        return SendResult(ok=False, blocked=True)
    except BadRequest as exc:
        msg = str(exc).lower()
        if "chat not found" in msg or "chat_id" in msg:
            return SendResult(ok=False, blocked=True)
        return SendResult(ok=False, blocked=False, error=str(exc))
    except Exception as exc:  # outbound boundary -- classify all transport failures
        return SendResult(ok=False, blocked=False, error=str(exc))
```

**Phase 42 derivation:** `EmailClient.send_email(envelope: EmailEnvelope) -> EmailSendResult` — same try/except classification chain, mapping:

- aioboto3 `ClientError` with `Code='MessageRejected' | 'AccountSendingPausedException'` → `EmailSendResult(ok=False, classification="blocked")`
- aioboto3 `ClientError` 5xx response → `EmailSendResult(ok=False, classification="transient_error", error=str(exc))`
- aioboto3 `ClientError` 4xx non-blocked → `EmailSendResult(ok=False, classification="permanent_error", error=str(exc))`
- Bare `Exception` (network) → `EmailSendResult(ok=False, classification="transient_error", error=str(exc))`

The "never re-raises transport errors" invariant from `send_otp_dm` carries over; the ARQ task does its own retry logic on classification, not on raised exceptions.

---

### 4. `app/integrations/email/models.py` — NEW (`EmailSendLog` ORM)

**Analog:** `app/modules/auth/password_reset_token_model.py` lines 1–112 (the most recent v1.6 ORM model; Phase 41 lineage).

**Imports + model declaration pattern** (lines 21–55):

```python
from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin

PasswordResetTokenPurpose = Literal["password_reset", "invitation"]


class PasswordResetToken(Base, UUIDPkMixin, TimestampMixin):
    """Row-per-issued-token ...
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ...
```

**Indexes / __table_args__ pattern** (lines 80–110):

```python
__table_args__ = (
    CheckConstraint("purpose IN ('password_reset', 'invitation')", name="purpose"),
    Index(
        "uq_password_reset_tokens_active",
        "user_id", "purpose",
        unique=True,
        postgresql_where=text("consumed_at IS NULL"),
    ),
    Index("ix_password_reset_tokens_token_hash", "token_hash"),
)
```

**Phase 42 derivation (`EmailSendLog`):**

- `__tablename__ = "email_send_log"`
- Columns per D-42-18: `audit_correlation_id: UUID NOT NULL`, `to_address: Text`, `template_id: Text`, `provider: Text`, `provider_message_id: Text | None`, `status: Text` (CHECK status IN ('sent','bounced','complained','delivered','rejected')), `bounce_type: Text | None`, `recorded_at: TIMESTAMPTZ DEFAULT now()`.
- NO ForeignKey to `users` (recipient may not be a user — webhook tracks raw email).
- `__table_args__`: CheckConstraint on `status` literal set + two NON-UNIQUE indexes (`ix_email_send_log_audit_corr` on `audit_correlation_id`; `ix_email_send_log_to_addr_recorded` on `(to_address, recorded_at DESC)`). NO partial-UNIQUE (D-42-18 — multiple events per `provider_message_id` are legitimate; delivered → bounced is a normal sequence).

---

### 5. `app/integrations/email/dispatcher.py` — NEW (`enqueue_email_dispatch`)

**Analog (Protocol-slot impl):** No direct prior — Phase 42 is the FIRST exercise of the EmailDispatcher slot declared at `app/core/dependencies.py:639-646`. The CLOSEST shape match is the way `app/main.py:create_app` wires concrete functions to slots — but here we need a function-as-Protocol-impl module.

**Analog (ARQ enqueue from sync handler):** No prior — Phase 42 also establishes this. Read the v1.5 telegram-bot pattern as reference for how to obtain the ARQ pool though Phase 42 will need an additional `register_arq_pool` slot or read from `app.state` via FastAPI request.

**Phase 42 derivation (signature from `app/core/dependencies.py` lines 639–646):**

```python
async def enqueue_email_dispatch(
    *,
    template_id: str,                       # AST-gated literal ∈ LOCKED_EMAIL_TEMPLATES
    to: str,
    audit_correlation_id: UUID | None,
    **template_vars: Any,
) -> None:
    """Concrete EmailDispatcher impl (D-42-25).
    
    1. _resolve_template(template_id) → EmailTemplate (subject + jinja2.Template html + text).
    2. Render subject/html/text against template_vars (at enqueue-time inside calling
       module's import-legal context — D-42-07).
    3. Build EmailEnvelope frozen dataclass (D-42-16).
    4. await arq_pool.enqueue_job('dispatch_email', envelope_as_kwargs).
    
    Module renders, worker transports (D-42-07 narrative exception — preserves
    import-linter contract 3 integrations ⊥ modules).
    """
```

**`_resolve_template` helper pattern:** A registry walker that imports per-module template registries lazily:

```python
def _resolve_template(template_id: str) -> EmailTemplate:
    # Phase 42 only registers auth.email_templates; Phases 44/45 extend.
    from app.modules.auth.email_templates import TEMPLATES as AUTH_TEMPLATES
    
    if template_id in AUTH_TEMPLATES:
        return AUTH_TEMPLATES[template_id]
    raise KeyError(f"template_id {template_id!r} not in any per-module registry")
```

---

### 6. `app/workers/tasks/dispatch_email.py` — NEW (ARQ task)

**Analog:** `app/workers/scheduled/send_expiring_notifications.py` lines 1–69 + `send_booking_reminders.py` lines 1–77.

**Module docstring + import block pattern** (`send_expiring_notifications.py` lines 1–37):

```python
"""ARQ scheduled job: send expiring-soon Telegram DMs (Phase 27 NTF-02 / NTF-03).

Per Phase 7 D-06 / Phase 18 D-09 / Phase 27 D-27-06: this worker file MAY import
`app.modules.memberships.service` (single owning-module exception) AND
`app.integrations.telegram.{sender, copy, bot}` (integrations layer is always
allowed for workers — `app/workers/__init__.py:1-21` rationale).

Bot construction (D-27-06 — Option B LOCKED): ...
Transaction ownership (Phase 27 D-27-07 pattern b — multi-session): ...
Observability (Phase 18 specifics line 195): emits one structlog INFO
`send_expiring_notifications_complete count=N` AFTER the helper returns.
"""

from __future__ import annotations
from typing import Any
import structlog

from app.core.config import get_settings
from app.integrations.telegram import copy as telegram_copy
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.memberships import service as memberships_service

_log = structlog.get_logger("workers.scheduled.send_expiring_notifications")
```

**Phase 42 derivation:**

- Worker file MAY import `app.integrations.email.{client, types}` (transport layer, always allowed for workers) — but MUST NOT import `app.modules.*` (D-42-07: worker transports bytes, modules render templates). EmailEnvelope arrives pre-rendered.
- Module-level `_SEMAPHORE: Final[asyncio.Semaphore] = asyncio.Semaphore(5)` (D-42-15).
- Module-level structlog logger: `_log = structlog.get_logger("workers.tasks.dispatch_email")`.

**Task body pattern** (mirror `send_expiring_notifications` lines 41–68 + audit-emit-on-outcome from `app/modules/auth/service.py` lines 184–196):

```python
async def dispatch_email(ctx: dict[str, Any], envelope_kwargs: dict[str, Any]) -> str:
    """Per D-42-13: max_tries=2, timeout=20s, retry_delay=30s.
    
    1. Reconstruct EmailEnvelope from kwargs (cloudpickle-safe per D-42-16).
    2. Acquire _SEMAPHORE (D-42-15 — concurrency cap 5).
    3. Check Redis circuit breaker key sz:email:circuit:yandex_postbox (D-42-14).
       If open: return EmailSendResult.transient_error short-circuit without provider call.
    4. await ctx['email_client'].send_email(envelope).
    5. Open per-send session (ctx['sessionmaker']) — INSERT email_send_log row + audit.emit
       inside one UoW; commit. Mirror `auth.service.authenticate` lines 184-196.
    6. structlog INFO summary line `dispatch_email_complete provider_message_id=... status=...`.
    """
    session_factory = ctx["sessionmaker"]
    email_client = ctx["email_client"]
    envelope = EmailEnvelope(**envelope_kwargs)
    
    async with _SEMAPHORE:
        # Circuit-breaker check (D-42-14)
        if await _is_circuit_open(ctx['redis'], 'yandex_postbox'):
            result = EmailSendResult(ok=False, classification="transient_error", ...)
        else:
            result = await email_client.send_email(envelope)
            # Sliding-window ZADD on 5xx
            if result.classification == "transient_error":
                await _record_circuit_failure(ctx['redis'], 'yandex_postbox')
    
    async with session_factory() as session:
        log_row = EmailSendLog(
            audit_correlation_id=envelope.audit_correlation_id,
            to_address=envelope.to,
            template_id=envelope.template_id,
            provider="yandex_postbox",
            provider_message_id=result.provider_message_id,
            status="sent" if result.ok else "rejected",
            bounce_type=None,
        )
        session.add(log_row)
        await session.flush()  # surface FK/CHECK before audit emit (mirror payments.service:116)
        
        if result.ok:
            await audit.emit(
                session,
                "email_sent",
                actor_user_id=None,
                resource_type="email_send_log",
                resource_id=log_row.id,
                audit_correlation_id=envelope.audit_correlation_id,
                template_id=envelope.template_id,
                to_email=envelope.to,
                provider_message_id=result.provider_message_id,
            )
        else:
            await audit.emit(
                session,
                "email_send_failed",
                actor_user_id=None,
                resource_type="email_send_log",
                resource_id=log_row.id,
                audit_correlation_id=envelope.audit_correlation_id,
                template_id=envelope.template_id,
                to_email=envelope.to,
                reason=_map_classification_to_reason(result.classification),
                provider_error_code=result.error,
            )
        await session.commit()  # Pitfall 2 — emit BEFORE commit
    
    _log.info(
        "dispatch_email_complete",
        status="sent" if result.ok else "failed",
        classification=result.classification,
        template_id=envelope.template_id,
    )
    return "sent" if result.ok else "failed"
```

**Critical convention from `send_expiring_notifications.py:67`:** the `<job_name>_complete` summary log line is LOCKED — `dispatch_email_complete count=N` shape. `job_id` + `job_name` already bound on structlog contextvars by `on_job_start` (`WorkerSettings` lines 228–253).

---

### 7. `app/modules/auth/email_templates.py` — NEW (per-module Jinja2 registry)

**Analog (closest, since no Jinja2 registry exists yet):** `app/integrations/telegram/sender.py:_OTP_DM_TEMPLATE` lines 17–19 (the only existing locked-copy precedent) + `app/integrations/telegram/copy.py` (whole-module Russian copy registry — to be inspected if it follows registry shape).

**Locked Russian copy pattern** (`sender.py:17-19`):

```python
# Russian DM body -- locked copy per CONTEXT line 253. No i18n framework (RU/CIS only).
# RUF001 disabled: Cyrillic letters are intentional (Russian-only product per PROJECT.md).
_OTP_DM_TEMPLATE = "Ваш код: {code}\nДействителен 5 минут."  # noqa: RUF001
```

**Phase 42 derivation (D-42-06 / D-42-23):**

```python
"""Locked email templates owned by auth module (D-42-06 / D-39-02 / D-41-11).

Per-domain template ownership: each module ships its own email-templates.py
next to the calling service. Phase 42 ships EMAIL_OTP_LOGIN (only). Phase 44
adds PASSWORD_RESET + USER_INVITATION here. Phase 45 ships per-module
template files for memberships / bookings / payments.

LOCKED Russian copy (D-27-OWNER-COPY-LOCK lineage) — owner sign-off recorded
at VER-14 (Phase 46) by enumerating LOCKED_EMAIL_TEMPLATES member
EMAIL_OTP_LOGIN.

Render boundary (D-42-07): the dispatcher (app.integrations.email.dispatcher)
imports THIS module at enqueue-time to render against template_vars. The ARQ
task body NEVER imports app.modules.* — it receives the rendered EmailEnvelope
(D-41-03 narrative exception — preserves import-linter contract 3
integrations ⊥ modules).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Final
from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(
    autoescape=True,  # HTML side — defence in depth (D-42-05)
)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(
    autoescape=False,  # text/plain — explicit passthrough
)

@dataclass(frozen=True)
class EmailTemplate:
    subject: str          # Final str — no interpolation (D-42-23 lock)
    html: Template
    text: Template


# RUF001 disabled: Cyrillic letters are intentional (Russian-only product per PROJECT.md).
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_OTP_LOGIN": EmailTemplate(  # noqa: RUF001
        subject="Код входа в Sportzal",
        html=_ENV.from_string(
            "<h1>Код входа в Sportzal</h1>"
            "<p>Ваш код для входа: <strong>{{ otp_code }}</strong></p>"
            "<p>Срок действия: 10 минут. Если вы не запрашивали код — "
            "проигнорируйте это письмо.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Код входа в Sportzal\n\n"
            "Ваш код для входа: {{ otp_code }}\n\n"
            "Срок действия: 10 минут. Если вы не запрашивали код — "
            "проигнорируйте это письмо.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
}
```

Note the ` ` (NBSP literal) usage — mirrors the v1.4 `formatMoney` NBSP-safe lineage from frontend `src/shared/lib/money.ts`.

---

### 8. `app/modules/auth/service.py` — MODIFIED (add `request_otp_email`)

**Analog 1 (anti-oracle constant-time floor):** `app/modules/auth/service.py:authenticate` lines 110–196.

**Anti-oracle pattern** (lines 128–134):

```python
async def authenticate(...) -> User:
    email_lower = email.lower()
    # 1. Rate limit BEFORE Argon2 (D-18). RateLimited is a 429 — propagate.
    await check_login_rate(redis, email_lower)
    user = await session.scalar(select(User).where(User.email == email_lower))
    target_hash = user.password_hash if user is not None else await _get_sentinel_hash()
    try:
        await verify_password(password, target_hash)
    ...
```

The `_get_sentinel_hash()` sentinel-Argon2 trick (lines 52–66) is the **canonical timing-equivalence floor** in the codebase. Phase 42's `request_otp_email` uses an equivalent floor: when the user does not exist OR `email_verified=false` OR `is_active=false`, perform a no-op `asyncio.sleep` (or schedule the same per-row read shape) so total wall-clock matches the populated-branch median within ≤100ms (AUTH-EM-04).

**Analog 2 (OTP mint + atomic commit):** `app/modules/auth/telegram_service.py:start_deep_link` lines 80–110.

**OTP mint pattern** (lines 80–110):

```python
async def start_deep_link(session: AsyncSession) -> tuple[str, str]:
    settings = get_settings()
    raw_token = generate_deep_link_token()
    token_hash = _sha256_hex(raw_token)
    now = datetime.now(tz=UTC)
    row = OtpCode(
        deep_link_token_hash=token_hash,
        code_hash=None,
        user_id=None,
        telegram_chat_id=None,
        expires_at=now + timedelta(seconds=settings.otp_deep_link_ttl_seconds),
        attempts=0,
        consumed_at=None,
    )
    session.add(row)
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the OtpCode placeholder INSERT.
    await audit.emit(
        session, "telegram_deep_link_issued",
        actor_user_id=None, resource_type="otp",
        deep_link_token_hash=token_hash,
    )
    await session.commit()
    return raw_token, token_hash
```

**Phase 42 derivation (`request_otp_email`, D-42-22):**

```python
async def request_otp_email(
    session: AsyncSession,
    redis: Redis,
    email: str,
    *,
    ip: str | None = None,
) -> None:
    """POST /auth/otp/request {channel:'email'} entry (D-42-22 + AUTH-EM-02).
    
    Anti-oracle constant-time floor (mirrors authenticate timing-equivalence):
    user_unknown / email_verified=false / is_active=false ALL return None
    with bounded wall-clock matching the populated branch median (≤100ms).
    
    Per D-42-22:
    - TTL = 600s (10 min — Telegram × 2 per FEATURES SLO).
    - 60s resend cooldown enforced at otp_codes row level.
    - Second request for same (user_id, channel='email') invalidates the first
      via atomic UPDATE-to-consumed + INSERT-new in same UoW (RFC 6238).
    """
    t_start = time.perf_counter()
    email_lower = email.lower()
    audit_correlation_id = uuid4()  # D-42-35
    
    # Lookup — populated branch must do same SQL shape as silent branch.
    user = await session.scalar(select(User).where(User.email == email_lower))
    
    # Three-way guard (D-42-22):
    is_eligible = (
        user is not None
        and getattr(user, "email_verified", False) is True
        # is_active landed in Phase 43 — Phase 42 reads as True if missing
        and getattr(user, "is_active", True) is True
    )
    
    if is_eligible:
        assert user is not None  # narrowed by is_eligible
        # Cooldown check: most-recent un-consumed email-channel otp
        cooldown_row = await session.scalar(
            select(OtpCode).where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
                OtpCode.consumed_at.is_(None),
            ).order_by(OtpCode.created_at.desc())
        )
        if cooldown_row is not None and cooldown_row.created_at > now - timedelta(seconds=60):
            # 202-no-op per D-42-22 — same shape as success.
            await _constant_time_floor(t_start)
            return
        
        # Atomic single-active: consume prior + INSERT new in same UoW (RFC 6238).
        await session.execute(
            update(OtpCode)
            .where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
                OtpCode.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        
        raw_code, code_hash = generate_otp_code()
        otp_row = OtpCode(
            user_id=user.id,
            channel="email",
            deep_link_token_hash="",  # unused for email channel; may relax NOT NULL
            code_hash=code_hash,
            telegram_chat_id=None,
            expires_at=now + timedelta(seconds=600),  # D-42-22 — 10 min TTL
            attempts=0,
            consumed_at=None,
        )
        session.add(otp_row)
        # Pitfall 2: emit BEFORE commit.
        await audit.emit(
            session, "otp_requested",  # piggyback Phase 7 event per D-42-35
            actor_user_id=user.id, resource_type="otp",
            audit_correlation_id=audit_correlation_id,
            channel="email",
        )
        await session.commit()
        
        # AST-gated callsite — first real LOCKED_EMAIL_TEMPLATES exercise (D-42-27 / INFRA-36).
        await get_email_dispatcher()(
            template_id="EMAIL_OTP_LOGIN",  # AST-gated literal
            to=user.email,
            audit_correlation_id=audit_correlation_id,
            otp_code=raw_code,  # **template_vars
        )
    
    # Both branches converge on the same constant-time floor.
    await _constant_time_floor(t_start)
```

`_constant_time_floor` sleeps until `t_start + EMAIL_OTP_FLOOR_MS` has elapsed (mirrors `_get_sentinel_hash` timing discipline). Same `time.perf_counter()` API as RESET-06 (`tests/integration/auth/test_password_reset_no_oracle.py:147`).

---

### 9. `app/modules/auth/router.py` — MODIFIED (extend `/auth/otp/request`)

**Analog:** `app/modules/auth/router.py:telegram_verify` lines 316–362.

**Route signature + body schema pattern** (lines 316–362):

```python
@router.post(
    "/telegram/verify",
    response_model=ResponseEnvelope[LoginResponse],
)
async def telegram_verify(
    payload: TelegramVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    """Verify the 6-digit OTP and issue session cookies ...
    
    On success: mints tokens + cookies identical to /login, then emits
    `login_success` with `channel='telegram'` (D-14). Distinct error codes
    per D-13 ride the AppError envelope handler.
    """
    settings = get_settings()
    try:
        user = await telegram_service.consume(...)
    except BotNotStarted as exc:
        raise BotNotStarted(...)
    ...
```

**Phase 42 derivation (`/auth/otp/request` extension):**

The new route adds the `channel: Literal['telegram', 'email']` discriminator with default `'telegram'` (D-42-22 backwards compat). Dispatch by channel:

```python
@router.post("/otp/request", response_model=ResponseEnvelope[None])
async def otp_request(
    payload: OtpRequestBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Request OTP via configured channel (AUTH-EM-02; D-42-22 anti-oracle).
    
    Default channel='telegram' for backwards compat.
    Always returns 202 with identical body shape (RESET-06 lineage).
    """
    ip = request.client.host if request.client is not None else None
    if payload.channel == "email":
        await service.request_otp_email(session, redis, payload.email, ip=ip)
    else:
        await service.request_otp_telegram(session, redis, ...)
    return envelope(None)  # Always 202 — body identical regardless of branch.
```

Return status 202 set via `status_code=202` in decorator (FastAPI default 200 — explicit override needed). Mirror `auth.router.telegram_start` lines 278–296 envelope-return shape.

---

### 10. `app/modules/auth/schemas.py` — MODIFIED (`OtpRequestBody`)

**Analog:** `app/modules/auth/schemas.py:LoginRequest` lines 24–28 + `TelegramVerifyRequest` lines 77–85.

**Body schema pattern** (lines 24–28):

```python
class LoginRequest(BackendSchemaBase):
    """POST /api/v1/auth/login body."""
    email: EmailStr
    password: str = Field(min_length=12)
```

**Phase 42 derivation:**

```python
class OtpRequestBody(BackendSchemaBase):
    """POST /api/v1/auth/otp/request body (D-42-22 / AUTH-EM-02).
    
    `channel` discriminates between 'telegram' (backwards-compat default) and
    'email' (Phase 42 new). `email` is REQUIRED for channel='email'; for
    channel='telegram' the existing username/chat_id resolution path applies.
    """
    channel: Literal["telegram", "email"] = "telegram"
    email: EmailStr | None = None  # required when channel='email'
    
    @model_validator(mode="after")
    def _email_required_when_email_channel(self) -> "OtpRequestBody":
        if self.channel == "email" and self.email is None:
            raise ValueError("email is required when channel='email'")
        return self
```

camelCase serialization auto via `alias_generator=to_camel` on `BackendSchemaBase` (Phase 4 D-09 lineage — already in place).

---

### 11. `app/api/v1/_internal/email/router.py` — NEW (HMAC webhook)

**Analog 1 (HMAC compare_digest discipline):** `app/core/dependencies.py:verify_csrf` lines 870–913.

**HMAC timing-safe compare pattern** (lines 894–913):

```python
async def verify_csrf(request: Request, ...) -> None:
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (
        cookie_val is None
        or header_val is None
        or not secrets.compare_digest(cookie_val, header_val)
    ):
        await audit.emit(
            session, "csrf_mismatch",
            actor_user_id=None, resource_type="csrf",
            path=request.url.path, method=request.method,
            ip=request.client.host if request.client is not None else None,
            has_cookie=cookie_val is not None,
            has_header=header_val is not None,
        )
        raise CsrfMismatch("csrf_mismatch")
```

**Analog 2 (router shape):** `app/modules/auth/router.py:telegram_status` lines 299–313 (unauthenticated, no CSRF).

**Phase 42 derivation (D-42-17):**

```python
"""Internal email webhook handler — HMAC-signed bounce/complaint events (D-42-17).

NOT mounted under /api/v1/auth or any business module — this is a
TRANSPORT-layer concern (D-42-CD: webhook is a transport concern, not a
feature module). Mounted under /api/v1/_internal/ as the first inhabitant
of that namespace (the _internal mount pattern establishes a precedent
for Phase 43+ provider-callback webhooks).

HMAC verify BEFORE parse (D-42-17): the signature in
`X-Email-Webhook-Signature` is checked against raw body bytes with
`hmac.compare_digest` before any JSON.loads — O(1) timing-safe rejection
of unsigned bodies. Mirrors verify_csrf shape (dependencies.py:894-913).
"""

router = APIRouter()

@router.post("/webhook", status_code=202)
async def email_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Yandex Cloud Postbox bounce/complaint webhook (D-42-17 / EMAIL-07).
    
    1. Compute HMAC-SHA256 of raw body with settings.email.webhook_secret.
    2. compare_digest against X-Email-Webhook-Signature header.
    3. On mismatch: 401 (no audit emit on unsigned bodies — would amplify
       noise from unsigned probes; mirror auth.router silent-401 discipline).
    4. On match: parse payload, UPDATE matching email_send_log row,
       audit.emit("email_send_failed", classification='bounced_hard'|'complained').
       Soft-bounces stay quiet (D-42-19).
    """
    settings = get_settings()
    raw_body = await request.body()
    presented_sig = request.headers.get("x-email-webhook-signature", "")
    expected_sig = hmac.new(
        settings.email.webhook_secret.get_secret_value().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(presented_sig, expected_sig):
        raise InvalidAccessToken("invalid_webhook_signature")  # 401
    
    payload = json.loads(raw_body)
    # ... match by provider_message_id, UPDATE status, audit.emit per D-42-19 ...
```

**Mount in `app/api/v1/router.py`** (Phase 42 adds NEW lines):

```python
from app.api.v1._internal.email.router import router as email_webhook_router
v1.include_router(email_webhook_router, prefix="/_internal/email", tags=["_internal"])
```

This establishes the `_internal` namespace precedent — first inhabitant. Future provider webhooks (Yandex Cloud invoice callbacks, etc.) land here.

---

### 12. `app/core/config.py` — MODIFIED (`EmailProviderSettings` block)

**Analog:** `app/core/config.py` lines 37–46 (`Telegram` placeholder block + `otp_*` settings).

**Settings block pattern** (lines 37–46):

```python
# Phase 7 additions (D-10, D-03): Telegram OTP channel.
# Placeholder defaults so fresh-clone dev boot of `web` + admin-web does NOT
# require setting bot credentials first. ...
telegram_bot_token: SecretStr = SecretStr("placeholder-telegram-bot-token-not-real")
telegram_bot_username: str = "placeholder_bot"  # without leading `@`
otp_deep_link_ttl_seconds: int = 600  # 10 min — AUTH-TG-01
otp_code_ttl_seconds: int = 300       # 5 min  — AUTH-TG-02
otp_max_attempts: int = 5             # AUTH-TG-02
```

**`@model_validator(mode='after')` pattern** (`Settings._gym_hours_range_invariant`, lines 53–61):

```python
@model_validator(mode="after")
def _gym_hours_range_invariant(self) -> "Settings":
    if self.gym_hours_end <= self.gym_hours_start:
        raise ValueError(...)
    return self
```

**Phase 42 derivation (D-42-28, NEW nested Pydantic block):**

```python
from typing import Literal, Self
from pydantic import BaseModel, SecretStr, model_validator

class EmailProviderSettings(BaseModel):
    """Email transport settings (D-42-28). Mirrors v1.1 Telegram-block shape.
    
    Loaded as a nested block on Settings; env vars prefixed `EMAIL_*`.
    """
    provider: Literal["yandex_postbox", "sandbox"] = "sandbox"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    endpoint_url: str = "https://postbox.cloud.yandex.net"
    from_address: str = "noreply@mail.sportzal.ru"
    from_domain: str = ""
    webhook_secret: SecretStr = SecretStr("")
    sandbox_mode: bool = False
    
    @model_validator(mode="after")
    def _validate_production_required(self) -> Self:
        if self.provider != "sandbox" and not self.sandbox_mode:
            if not self.from_domain:
                raise ValueError(
                    "EmailProviderSettings.from_domain required for non-sandbox provider"
                )
            if not self.webhook_secret.get_secret_value():
                raise ValueError(
                    "EmailProviderSettings.webhook_secret required for non-sandbox provider"
                )
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                raise ValueError(
                    "EmailProviderSettings AWS creds required for non-sandbox provider"
                )
        return self


class Settings(BaseSettings):
    ...
    email: EmailProviderSettings = EmailProviderSettings()
```

Boot-time fail-fast mirrors v1.2 D-18 ARQ on_startup discipline.

---

### 13. `app/main.py` — MODIFIED (`register_email_dispatcher` wiring)

**Analog:** `app/main.py:create_app` lines 145–220 (existing 10 `register_*` calls + their import-locality discipline).

**Composition-root register pattern** (lines 145–174):

```python
# D-15: composition root fills the Phase 4 loader slot. This is the ONLY
# place where app.main reaches into app.modules.*. The importlinter
# contract scopes source_modules=app.core, so app.main is intentionally
# outside the scope.
register_user_loader(load_user_by_id)

# Phase 17 MEM-05: second composition-root carve-out ...
register_active_membership_resolver(resolve_active_membership_by_client)

# Phase 19 D-02: third composition-root carve-out — visits self-checkin
# path needs to look up Client by telegram_user_id ...
from app.modules.clients import (
    service as clients_service,
)
register_client_by_telegram_resolver(
    clients_service.resolve_client_by_telegram_user_id,
)

# Phase 31 D-31-14: fourth composition-root carve-out — pt_sessions service
# (Phase 34) will validate trainer existence via this Protocol slot.
# Defensive: bot worker also registers (see telegram_bot.py). Idempotent.
from app.modules.trainers import (
    service as trainers_service,
)
register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
```

**Phase 42 derivation (D-42-26, NEW block added before `app.include_router(api)`):**

```python
# Phase 42 D-42-26 — eleventh composition-root carve-out: EmailDispatcher slot.
# Phase 41 declared the slot (app/core/dependencies.py:639-679); Phase 42 is
# the first phase exercising it. Wired EXCLUSIVELY through
# app.integrations.email.dispatcher.enqueue_email_dispatch — the function
# legally imports app.modules.* at enqueue time (D-42-07 narrative exception).
# Defensive double-wire (REG-29-03): same call MUST appear in
# app/workers/__init__.py WorkerSettings.on_startup.
from app.integrations.email.dispatcher import enqueue_email_dispatch
from app.core.dependencies import register_email_dispatcher

register_email_dispatcher(enqueue_email_dispatch)
```

Import is local to `create_app()` body (mirrors the Phase 19 / Phase 31 patterns at lines 159, 170).

---

### 14. `app/workers/__init__.py` — MODIFIED (`WorkerSettings` extensions)

**Analog:** `app/workers/__init__.py` lines 78–217 — existing eager-imports + `WorkerSettings.functions` list + `on_startup` body.

**Eager-import pattern** (lines 78–99):

```python
# ORM eager-imports (REG-29-04 / D-41-29 — REG-29-04 mirror).
# ...
# Rule: every ORM table added in v1.6+ that the worker namespace might
# touch — directly OR indirectly through a cron job — gets an eager
# import here so the module-load side effect registers the table on
# `Base.metadata` before any worker code runs.
from app.modules.auth.password_reset_token_model import (  # noqa: F401
    PasswordResetToken,  # Phase 41 INFRA-38 / D-41-29 — password_reset_tokens
)
from app.workers.scheduled.expire_memberships import expire_memberships
...
```

**`functions` list pattern** (lines 114–120):

```python
functions: ClassVar[list[Any]] = [
    expire_memberships,
    send_expiring_notifications,
    expire_pt_packages,
    send_booking_reminders,
    mark_no_show_bookings,
]
```

**`on_startup` body pattern** (lines 191–217):

```python
@staticmethod
async def on_startup(ctx: dict[str, Any]) -> None:
    """Open DB lifespan + stash stack in ctx + run cron-resolution invariant.
    ...
    """
    function_names = {f.__name__ for f in WorkerSettings.functions}
    cron_function_names = {c.coroutine.__name__ for c in WorkerSettings.cron_jobs}
    unresolved = cron_function_names - function_names
    assert not unresolved, (...)
    
    stack = AsyncExitStack()
    engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
    ctx["_db_stack"] = stack
    ctx["engine"] = engine
    ctx["sessionmaker"] = sessionmaker
    _log.info("worker_startup_complete", function_count=len(function_names))
```

**Phase 42 derivation (D-42-26 + D-42-33 + EMAIL-04):**

Three additions to this file:

1. **Eager-import the new ORM model** (after the existing PasswordResetToken import at line 92):
   ```python
   from app.integrations.email.models import (  # noqa: F401
       EmailSendLog,  # Phase 42 D-42-33 — email_send_log eager-import (REG-29-04)
   )
   ```

2. **Add `dispatch_email` to `WorkerSettings.functions`** (append to line 114–120 list):
   ```python
   functions: ClassVar[list[Any]] = [
       expire_memberships,
       send_expiring_notifications,
       expire_pt_packages,
       send_booking_reminders,
       mark_no_show_bookings,
       dispatch_email,  # Phase 42 EMAIL-03
   ]
   ```

3. **Extend `on_startup` body** (after the existing engine/sessionmaker stash):
   ```python
   # Phase 42 D-42-26 — REG-29-03 double-wire of EmailDispatcher slot.
   # MUST be IDENTICAL to app.main.create_app() register_email_dispatcher call
   # — the parity test asserts byte-equal symbol reference.
   from app.integrations.email.dispatcher import enqueue_email_dispatch
   from app.integrations.email.factory import build_email_client
   from app.core.dependencies import register_email_dispatcher
   
   ctx["email_client"] = build_email_client(settings=get_settings().email)
   register_email_dispatcher(enqueue_email_dispatch)
   ```

The `ctx["email_client"]` is the worker's mirror of `ctx["engine"]` / `ctx["sessionmaker"]` (Phase 18 D-09 pattern) — task bodies read `ctx["email_client"]` for the configured provider client. EMAIL-04 mandates this verbatim.

---

### 15. `alembic/versions/0026_email_send_log.py` — NEW migration

**Analog:** `alembic/versions/0025_password_reset_tokens.py` lines 1–187.

**Migration docstring + revision header pattern** (lines 1–101):

```python
"""password_reset_tokens unified table (INFRA-38 / D-41-03/04/05).

Revision ID: 0025_password_reset_tokens
Revises: 0024_notif_channel_discriminator
Create Date: 2026-05-18 19:30:00.000000

Phase 41 INFRA-38 — fourth and final v1.6 INFRA-bedrock migration. ...

DESIGN — DB-table over itsdangerous-stateless (D-41-03)
-------------------------------------------------------
...

HASH-AT-REST DISCIPLINE (D-41-04, T-41-09-01)
---------------------------------------------
...
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision: str = "0025_password_reset_tokens"
down_revision: str | None = "0024_notif_channel_discriminator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**`create_table` + indexes pattern** (lines 103–174):

```python
def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        ...
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('password_reset', 'invitation')",
            name=op.f("ck_password_reset_tokens_purpose"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "uq_password_reset_tokens_active",
        "password_reset_tokens",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=text("consumed_at IS NULL"),
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=False,
    )
```

**Phase 42 derivation (D-42-18):**

- Revision header: `revision = "0026_email_send_log"`, `down_revision = "0025_password_reset_tokens"`.
- Table per D-42-18 schema (8 columns including the locked CHECK on `status`).
- **NO ForeignKey to users** (recipient may not exist as User — webhook tracks raw `to_address`).
- **NO partial-UNIQUE** (D-42-18 — multiple events per `provider_message_id` are legitimate).
- Two NON-UNIQUE indexes: `ix_email_send_log_audit_corr` on `audit_correlation_id`; `ix_email_send_log_to_addr_recorded` on `(to_address, recorded_at DESC)`.
- `downgrade()`: drop indexes then table (mirror lines 177–186).

---

### 16. `alembic/versions/0027_otp_codes_channel_discriminator.py` — NEW migration

**Analog:** `alembic/versions/0024_notification_channel_discriminator.py` lines 1–142 (line-for-line mirror).

**ADD COLUMN + CHECK + UNIQUE-recreate pattern** (lines 48–77):

```python
def upgrade() -> None:
    # membership_notifications
    op.add_column(
        "membership_notifications",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'telegram'"),
        ),
    )
    op.create_check_constraint(
        # Pass the literal name through op.f() so the naming_convention
        # (`ck_%(table_name)s_%(constraint_name)s` in app/core/database.py:31)
        # does NOT re-prefix and double the table name. Mirrors the pattern
        # used in 0010_notifications.py line 78 for ck_membership_notifications_kind.
        op.f("ck_membership_notifications_channel"),
        "membership_notifications",
        "channel IN ('telegram','email')",
    )
    op.drop_constraint(
        _MEMBERSHIP_NOTIFS_OLD_UNIQUE,
        "membership_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        _MEMBERSHIP_NOTIFS_NEW_UNIQUE,
        "membership_notifications",
        [*_MEMBERSHIP_NOTIFS_COLS, "channel"],
    )
```

**Phase 42 derivation (D-42-20):**

- `revision = "0027_otp_codes_channel_discriminator"`, `down_revision = "0026_email_send_log"`.
- `op.add_column("otp_codes", sa.Column("channel", sa.Text(), nullable=False, server_default=sa.text("'telegram'")))`.
- `op.create_check_constraint(op.f("ck_otp_codes_channel"), "otp_codes", "channel IN ('telegram','email')")`.
- **DROP** existing partial UNIQUE `(user_id) WHERE consumed_at IS NULL` from `otp_codes` (note: must verify the constraint name from `otp_codes` table — likely `uq_otp_codes_user_active`; resolve at plan-phase from Alembic CLI introspection).
- **RECREATE** partial UNIQUE as `(user_id, channel) WHERE consumed_at IS NULL` with new name `uq_otp_codes_user_channel_active`.
- Zero-row backfill — existing rows inherit `'telegram'` via the column-level DEFAULT (mirrors line 18–20 commentary).
- `downgrade()` reverses verbatim (lines 106–141 pattern).

`op.f()` wrapping (line 64 commentary) — required so the `naming_convention` from `app/core/database.py:31` does NOT double-prefix the table name. Phase 41 0024 explicitly documents this; Phase 42 0027 inherits the lesson byte-for-byte.

---

### 17. `alembic/versions/0028_users_email_verified.py` — NEW migration

**Analog:** No 1:1 — closest is `alembic/versions/0022_users_soft_delete_partial_unique.py` (User-table column add precedent) AND `0024` add-column section (lines 50–58).

**Phase 42 derivation (D-42-21):**

- `revision = "0028_users_email_verified"`, `down_revision = "0027_otp_codes_channel_discriminator"`.
- `op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))`.
- Migration body MUST include the bootstrap-runbook comment per D-42-21:
  ```python
  """users.email_verified BOOLEAN NOT NULL DEFAULT FALSE (D-42-21).
  
  Phase 42 ships the column + the AUTH-EM-02 read ('when channel=email:
  requires user with verified email'). Phase 43 ships the verify-flow
  set side (open conflict #7).
  
  BOOTSTRAP RUNBOOK (operator-action — NOT code):
    Existing operator users default email_verified=FALSE — flip the owner
    account via direct SQL after migration lands:
  
      UPDATE users SET email_verified = TRUE WHERE email = '<owner_email>';
  
    The OWNER's first email-OTP login flow becomes Phase 43's first
    verify-flow consumer naturally.
  """
  ```
- `downgrade()`: `op.drop_column("users", "email_verified")`.

---

### 18. `alembic/env.py` — MODIFIED (register new ORM model)

**Analog:** `alembic/env.py` lines 21–34 — existing ORM-import block.

**Existing pattern** (lines 23–35):

```python
# Register all ORM models with Base.metadata for autogenerate (TEST-08 / Phase 5 INFRA-03).
import app.modules.auth.models
import app.modules.auth.password_reset_token_model  # Phase 41 INFRA-38 / 0025 — D-41-04
import app.modules.bookings.models  # Phase 38 BOOK-01 / 0017
import app.modules.clients.models
...
```

**Phase 42 derivation:** Add one line after line 24:

```python
import app.integrations.email.models  # Phase 42 D-42-33 / 0026 — EMAIL-01 (email_send_log)
```

(Critical: the import is `app.integrations.email.models`, NOT a module-namespaced location, because the transport layer owns the table per D-42-33 — "modules don't read it directly, only the dispatcher + webhook handler do".)

---

### 19. ORM column adds — `User.email_verified` + `OtpCode.channel`

**Analogs:**
- `app/core/models.py:User` lines 32–55 (User column declaration pattern).
- `app/modules/auth/models.py:OtpCode` lines 75–112 (OtpCode column declaration pattern).

**User column pattern** (`core/models.py:46-50`):

```python
telegram_chat_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
    unique=True,
)
```

**OtpCode column pattern** (`auth/models.py:90-108`):

```python
telegram_chat_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
)
...
attempts: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    server_default="0",
)
```

**Phase 42 derivation:**

`app/core/models.py:User` — add `email_verified` column (after line 50):

```python
email_verified: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    server_default=text("FALSE"),
)
```

`app/modules/auth/models.py:OtpCode` — add `channel` column (after line 108):

```python
channel: Mapped[Literal["telegram", "email"]] = mapped_column(
    Text,
    nullable=False,
    server_default=text("'telegram'"),
)
```

The `Literal` typing mirrors `PasswordResetTokenPurpose` from `password_reset_token_model.py:38` — same TypeAlias-as-Literal pattern. `__table_args__` Index for the new partial-UNIQUE on `(user_id, channel) WHERE consumed_at IS NULL` mirrors `password_reset_token_model.py:94-100` byte-for-byte (with `purpose` → `channel`, `password_reset_tokens` → `otp_codes`).

---

### 20. `infra/dns/sportzal.ru.zone` — NEW (operator runbook)

**Analog:** No prior — Phase 42 is the first artifact under `infra/dns/`. The CLOSEST precedent is `DEFER-40-01` runbook discipline (Phase 46 budget); zone-file format is industry-standard BIND syntax.

**Phase 42 derivation (D-42-11 / D-42-12):**

```dns
; sportzal.ru zone — Phase 42 EMAIL-05 operator runbook (D-42-11 / D-42-12).
;
; THIS FILE IS NOT EXECUTED BY CI. The owner applies these records at the
; registrar (Reg.ru or alternate). Committed alongside code so the gate
; cannot land without the DNS spec.
;
; DMARC ladder: Phase 42 = p=none baseline. p=quarantine flip after 7 clean-
; report days (operator-action). p=reject deferred to v1.7.
;
; D-42-09 — subdomain mail.sportzal.ru = single dedicated subdomain for both
; From: envelope and DKIM key. Future mktg.sportzal.ru (marketing) lives on
; a separate subdomain for clean reputation isolation.

$ORIGIN sportzal.ru.
$TTL 3600

; SPF — Yandex Cloud Postbox include macro (per Postbox docs).
mail.sportzal.ru.   TXT   "v=spf1 include:_spf.yandexcloud.net -all"

; DKIM — Yandex Cloud Postbox console issues the selector + key at
; domain-verification time. Insert rendered value below.
sport1._domainkey.mail.sportzal.ru.   TXT   "v=DKIM1; k=rsa; p=<2048-bit-public-key-placeholder>"

; DMARC — p=none baseline (D-42-11).
_dmarc.mail.sportzal.ru.   TXT   "v=DMARC1; p=none; rua=mailto:dmarc-reports@sportzal.ru; pct=100"
```

Mirrors v1.5 `scripts/run_expiring_cron_once.py` (TM-29-02/03) operator-runbook discipline.

---

### 21. `tests/integration/auth/test_otp_email_anti_oracle.py` — NEW

**Analog:** `tests/integration/auth/test_password_reset_no_oracle.py` lines 1–172 (verbatim shape mirror — the RESET-06 test is the precedent that AUTH-EM-04 is explicitly modelled on).

**Fixture seeding pattern** (lines 56–112):

```python
@pytest_asyncio.fixture
async def four_fixture_users(db_session: AsyncSession) -> dict[str, User | None]:
    """Seed the 4 canonical RESET-06 cases per-test (D-41-18)."""
    pw_hash = await hash_password(_FIXTURE_PASSWORD)
    suffix = uuid4().hex[:8]
    active = User(
        email=f"active+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Active Reception",
    )
    ...
    db_session.add_all([active, deactivated, owner])
    await db_session.commit()
    return {"active": active, ..., "nonexistent": None}
```

**Bounded-timing assertion pattern** (lines 145–171):

```python
responses: list[tuple[int, bytes, float]] = []
for email in emails:
    t0 = time.perf_counter()
    resp = await async_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )
    t1 = time.perf_counter()
    responses.append((resp.status_code, resp.content, t1 - t0))

# Status-code parity
statuses = {r[0] for r in responses}
assert statuses == {202}, f"non-uniform statuses: {statuses}"

# Body parity — byte-for-byte
bodies = {r[1] for r in responses}
assert len(bodies) == 1, (
    "response body diverges across the 4 cases — anti-oracle leak: "
    f"{[r[1] for r in responses]}"
)

# Timing parity — bounded-equal within 100 ms
timings = [r[2] for r in responses]
assert max(timings) - min(timings) < 0.100, (
    f"timing oracle: max-min={max(timings) - min(timings):.3f}s > 100ms; "
    f"per-case timings={timings}"
)
```

**Phase 42 derivation (D-42-24, AUTH-EM-04 four cases):**

Reuse the entire test shape with these substitutions:
- Endpoint: `/api/v1/auth/otp/request`
- Body: `{"channel": "email", "email": <e>}`
- Four fixture users per D-42-24:
  1. `email_verified_no_telegram` — User with `email_verified=True`, no `telegram_chat_id`.
  2. `email_verified_with_telegram_default_channel` — User with both; request body OMITS `channel` field (tests backwards-compat default).
  3. `email_unverified` — User exists, `email_verified=False`.
  4. `nonexistent` — Email never inserted.
- Cases 1 + 3 + 4 send `{"channel": "email", ...}`; case 2 sends `{"email": ...}` (no `channel` — exercises Telegram path default).
- Assertion: statuses == {202}; cases 1, 3, 4 bodies are identical; case 1 timing matches cases 3 + 4 within ≤100ms.

The xfail-strict marker WILL NOT apply (Phase 42 ships the endpoint in the same commit — the test goes GREEN at land time, unlike RESET-06 which xfailed for 3 phases).

---

### 22. `tests/test_compose_root_parity.py` — MODIFIED (extend REG-29-03)

**Analog:** `tests/integration/test_app_wiring.py` lines 1–133 (exact existing file — Phase 42 extends).

**AST-walk pattern** (lines 41–51):

```python
def _register_call_names(path: Path) -> set[str]:
    """Walk the module AST and return every ``register_*`` function-call name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.startswith("register_")
        ):
            names.add(node.func.id)
    return names
```

**Slot-non-None assertion pattern** (lines 54–90):

```python
def test_create_app_registers_all_protocol_slots() -> None:
    create_app()
    # Phase 4-34 slots (pre-existing — must not regress).
    assert deps._user_loader is not None, "Phase 5 register_user_loader missing"
    assert deps._active_membership_resolver is not None, (
        "Phase 17 register_active_membership_resolver missing"
    )
    ...
```

**Bot-vs-API parity assertion pattern** (lines 93–132):

```python
def test_bot_main_register_set_is_subset_of_api_main_register_set() -> None:
    main_calls = _register_call_names(_MAIN_PY)
    bot_calls = _register_call_names(_BOT_PY)
    assert bot_calls <= main_calls, (...)
    assert "register_active_pt_package_resolver" in bot_calls, (...)
```

**Phase 42 derivation (D-42-26 REG-29-03 double-wire):**

Add **two assertions** to `test_create_app_registers_all_protocol_slots`:

```python
# Phase 42 D-42-26 — EmailDispatcher slot (REG-29-03 double-wire).
assert deps._email_dispatcher is not None, (
    "Phase 42 register_email_dispatcher missing in create_app()"
)
```

Add a **new parity test** asserting the worker `WorkerSettings.on_startup` body contains a `register_email_dispatcher` call:

```python
def test_worker_on_startup_double_wires_email_dispatcher() -> None:
    """REG-29-03 double-wire: app.workers.WorkerSettings.on_startup MUST register
    EmailDispatcher with the SAME function reference as app.main.create_app().
    """
    workers_py = _BACKEND_ROOT / "app" / "workers" / "__init__.py"
    worker_calls = _register_call_names(workers_py)
    main_calls = _register_call_names(_MAIN_PY)
    
    assert "register_email_dispatcher" in worker_calls, (
        "REG-29-03 violation: WorkerSettings.on_startup does not register "
        "EmailDispatcher — Phase 42 D-42-26 mandates double-wire."
    )
    assert "register_email_dispatcher" in main_calls, (
        "REG-29-03 violation: create_app() does not register EmailDispatcher."
    )
```

(Note: the file path `tests/test_compose_root_parity.py` is the CONTEXT.md-specified location; verify whether to extend the existing `tests/integration/test_app_wiring.py` instead at plan-phase. Recommendation: extend the existing file — preserves the test-discovery surface and avoids duplicate file infrastructure.)

---

### 23. `tests/unit/test_locked_email_templates_ast.py` — MODIFIED (extend)

**Analog:** `tests/unit/test_locked_email_templates_ast.py` lines 1–178 (existing file from Phase 41).

**No code change is required** — the walker `test_real_callsites_pass()` (line 121) already scans `apps/backend/app/**/*.py` for any `get_email_dispatcher()(template_id=...)` callsite. When Phase 42 lands `auth.service.request_otp_email`'s callsite (D-42-27), the walker AUTOMATICALLY picks it up and asserts:
- `template_id="EMAIL_OTP_LOGIN"` is a literal `ast.Constant(str)` ✓
- `"EMAIL_OTP_LOGIN" ∈ LOCKED_EMAIL_TEMPLATES` ✓

Phase 42 verification: re-run the test; the violation list MUST stay empty. The Phase 41 walker scope-extension to `app.modules.*` is exercised on real code for the first time.

If Phase 42 adds a NEW positive fixture (`fixtures/email_ast_violations/passes_real_callsite.py` exercising the EMAIL_OTP_LOGIN literal), use the same fixture-import discipline at line 39 (`_FIXTURE_DIR / "..."`).

---

### 24. `tests/unit/test_workers_eager_import.py` — MODIFIED (extend)

**Analog:** `tests/unit/test_workers_eager_import.py` lines 1–58 (existing file from Phase 41).

**Existing assertion pattern** (lines 23–35):

```python
def test_password_reset_tokens_eager_imported() -> None:
    """Phase 41 INFRA-38 / D-41-29 — password_reset_tokens reachable from worker root.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    assert "password_reset_tokens" in Base.metadata.tables, sorted(
        Base.metadata.tables.keys()
    )
```

**Critical-tables-smoke pattern** (lines 38–58):

```python
def test_v15_critical_tables_still_visible() -> None:
    import app.workers  # noqa: F401
    from app.core.database import Base
    critical_v15 = {
        "memberships",
        "membership_notifications",
        "bookings",
        "booking_notifications",
    }
    visible = set(Base.metadata.tables.keys())
    missing = critical_v15 - visible
    assert not missing, f"v1.5 critical tables not eager-loaded: {sorted(missing)}"
```

**Phase 42 derivation (D-42-33):**

Add a new test function after `test_password_reset_tokens_eager_imported`:

```python
def test_email_send_log_eager_imported() -> None:
    """Phase 42 D-42-33 — email_send_log reachable from worker root (REG-29-04).
    
    Importing `app.workers` must surface `email_send_log` on
    `Base.metadata.tables`; the eager-import line in
    `app/workers/__init__.py` (Phase 42 EMAIL-01) is the contract.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base
    
    assert "email_send_log" in Base.metadata.tables, sorted(
        Base.metadata.tables.keys()
    )
```

---

## Shared Patterns

These cross-cut multiple Phase 42 files. The planner should reference them once at the top of each affected plan action.

### A. Pitfall 2 — `audit.emit` BEFORE `session.commit()`

**Source:** `apps/backend/app/modules/auth/service.py` lines 184–196, `auth.service.revoke_session` lines 552–559, `auth.telegram_service.start_deep_link` lines 100–109.

**Pattern:**

```python
# Pitfall 2: emit BEFORE commit so the audit row commits atomically with
# the [domain mutation].
await audit.emit(
    session, "<event_name>",
    actor_user_id=..., resource_type="<literal_table_name>",
    resource_id=..., audit_correlation_id=...,
    # ... payload kwargs ...
)
await session.commit()
```

**Apply to:** `dispatch_email` task body (`workers/tasks/dispatch_email.py`), `request_otp_email` (`auth.service`), email webhook handler (`api/v1/_internal/email/router.py`).

`resource_type` MUST be a string literal at the callsite — the audit-taxonomy walker test rejects expressions (Phase 15 INFRA-11 / D-11).

### B. `audit_correlation_id` chain seeding

**Source:** D-42-35 + `audit_payloads.py:614` `PasswordResetRequestedPayload` docstring.

**Pattern:**

```python
audit_correlation_id = uuid4()  # generated by request-side handler
# 1. Emit synchronous business audit (e.g. otp_requested) with the correlation_id
await audit.emit(session, "otp_requested", ..., audit_correlation_id=audit_correlation_id, ...)
# 2. Pass into the email envelope so the eventual email_sent / email_send_failed
#    audit row shares the same UUID
await get_email_dispatcher()(
    template_id="EMAIL_OTP_LOGIN", to=..., audit_correlation_id=audit_correlation_id, ...
)
```

**Apply to:** `auth.service.request_otp_email` (chain-starter), `workers/tasks/dispatch_email.py` (chain-continuer), webhook handler (chain-continuer on UPDATE of `email_send_log` row).

### C. `op.f()`-wrapped Alembic naming convention

**Source:** `alembic/versions/0024_notification_channel_discriminator.py:62-66` commentary block.

**Pattern:**

```python
op.create_check_constraint(
    # Pass the literal name through op.f() so the naming_convention
    # (`ck_%(table_name)s_%(constraint_name)s` in app/core/database.py:31)
    # does NOT re-prefix and double the table name.
    op.f("ck_<table>_<column>"),
    "<table>",
    "<predicate>",
)
```

**Apply to:** all three Phase 42 migrations (0026, 0027, 0028) — any CHECK / PK / FK / partial-UNIQUE name MUST be `op.f()`-wrapped.

### D. ARQ worker imports — single-owning-module exception

**Source:** `app/workers/__init__.py` lines 1–62 module docstring + `app/workers/scheduled/send_expiring_notifications.py` lines 1–37.

**Pattern:** Worker files MAY import `app.integrations.*` freely. Worker files MAY import ONE owning module's service layer (`app.modules.<X>.service`). Cross-module imports from a single worker file are forbidden.

**Apply to:** `app/workers/tasks/dispatch_email.py` — MUST NOT import any `app.modules.*` (the email task is owned by the TRANSPORT layer, not a module; envelope arrives pre-rendered per D-42-07).

### E. `from __future__ import annotations` + structlog logger naming

**Source:** Every existing worker file (e.g. `send_expiring_notifications.py:26, 38`).

**Pattern:**

```python
from __future__ import annotations
from typing import Any
import structlog

_log = structlog.get_logger("workers.<package>.<module_name>")
```

**Apply to:** `app/workers/tasks/dispatch_email.py` (logger name `workers.tasks.dispatch_email`).

### F. `<job_name>_complete count=N` summary log convention

**Source:** `app/workers/scheduled/expire_memberships.py:25-27` module-docstring lock + `send_expiring_notifications.py:67`.

**Pattern:**

```python
_log.info("<job_name>_complete", count=count)
return count
```

**Apply to:** `dispatch_email` task body — `_log.info("dispatch_email_complete", status=..., classification=..., template_id=...)`.

### G. Test-fixture-per-test isolation (NOT module-scoped)

**Source:** `tests/integration/auth/test_password_reset_no_oracle.py:56-112` `four_fixture_users` fixture; D-41-18 commentary.

**Pattern:** Phase 42 AUTH-EM-04 test fixtures use `@pytest_asyncio.fixture` (NOT `scope="module"`); per-test seeding via `db_session.add_all([...])` + `await db_session.commit()`; UUID suffix on emails for cross-test uniqueness.

**Apply to:** `tests/integration/auth/test_otp_email_anti_oracle.py`.

---

## No Analog Found

| File | Reason |
|---|---|
| `infra/dns/sportzal.ru.zone` | First DNS zone-file artifact in the repo. The BIND-syntax + operator-runbook header is industry-standard but novel to this codebase. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/integrations/{email,telegram}/` (all files)
- `apps/backend/app/workers/{__init__.py,scheduled/*.py,tasks/*.py}` (all files)
- `apps/backend/app/modules/auth/` (all files)
- `apps/backend/app/core/{config,dependencies,audit,audit_payloads,models}.py`
- `apps/backend/app/main.py` + `app/api/v1/router.py`
- `apps/backend/alembic/versions/0022_…0025_*.py` + `alembic/env.py`
- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py`
- `apps/backend/tests/integration/test_app_wiring.py`
- `apps/backend/tests/unit/test_workers_eager_import.py`
- `apps/backend/tests/unit/test_locked_email_templates_ast.py`
- `apps/backend/tests/unit/test_dependencies_slots_v15.py`

**Files scanned:** ~45 Python files + 4 migration files. Targeted reads via `Grep` + `Read` with line-range offsets to honor the no-re-read constraint.

**Pattern extraction date:** 2026-05-18.

**Key invariants enforced by these patterns:**

1. **Pitfall 2 atomicity** — every `audit.emit` lands BEFORE its sibling `session.commit()` (16 callsites in the v1.5 codebase prove this is universal).
2. **REG-29-03 double-wire** — every cross-process Protocol slot has the same `register_*` call in both `app/main.py:create_app()` AND `app/workers/{telegram_bot.py | __init__.py}` worker entry. Phase 42 EmailDispatcher is the 11th slot exercising this discipline.
3. **REG-29-04 eager-import** — every ORM model the worker might touch is explicitly imported at the top of `app/workers/__init__.py`; the eager-import test pins this as code.
4. **`op.f()`-wrapping** — every constraint name in every Alembic migration is wrapped to avoid double-prefix collisions with `naming_convention`.
5. **Anti-oracle constant-time floor** — both `authenticate` (timing-equivalence via sentinel Argon2) and (future) `request_otp_email` (timing-equivalence via `time.perf_counter()` floor) preserve identical wall-clock latency across populated and silent branches.
6. **Locked-copy AST gates** — `template_id=` literal AND `LOCKED_EMAIL_TEMPLATES` membership enforced statically; the AUDIT_TAXONOMY walker (Phase 15) and INFRA-36 walker (Phase 41) share this discipline.

The planner can now reference each pattern by section number when writing Phase 42 plan actions — every reference is a concrete file path + line range + code excerpt.
