# Phase 47: Bedrock — Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 12 file groups (3 modifications, 9 new files)
**Analogs found:** 12 / 12 (100% — every group has a concrete existing analog)

---

## Critical Correction Up-Front (downstream planner READ FIRST)

CONTEXT.md decisions D-47-01/02 and the upstream prompt state Protocol slots
live in **`app/core/services.py`**. This is incorrect against the working tree
as of 2026-05-21. `app/core/services.py` is a 102-line **docstring-only file**
documenting the BusinessService write-path recipe — it declares NO Protocol
classes. Every existing Protocol slot in the codebase
(`CurrentUser`, `ActiveMembership`, `PaymentRecorder`, `PaymentRefunder`,
`SlotById`, `EmailDispatcher`, `UserSessionInvalidator`, etc., 12+ of them)
lives in **`apps/backend/app/core/dependencies.py`**.

The planner MUST extend `app/core/dependencies.py`, NOT `app/core/services.py`,
for the four new Protocol slots
(`YooKassaClientProvider`, `FiscalReceiptDispatcher`, `MembershipActivator`,
`PtPackageActivator`). Either flag this correction in `47-PLAN.md` and proceed
against `dependencies.py`, OR raise it back to the user for confirmation
before planning. Recommended: proceed against `dependencies.py` (the working
tree wins over the discuss-phase reference) and document the correction at
the top of `47-PLAN.md`.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/core/audit.py` (extend `LOCKED_AUDIT_EVENTS`) | config / locked-constant | static frozenset | itself (existing v1.6 block lines 238–259) | exact (same file, append-only extension) |
| `app/core/audit_payloads.py` (9 new payload classes + 9 registry entries) | schema | Pydantic validation | `EmailSentPayload` + v1.6 block lines 465–507 | exact (same file, same pattern) |
| `app/integrations/yookassa/settings.py` (NEW) | config | env → BaseSettings | `EmailProviderSettings` in `app/core/config.py:11-45` | role-match (NOT a standalone file today — see correction below) |
| `app/integrations/yookassa/__init__.py` (NEW skeleton) | package marker | n/a | `app/integrations/email/__init__.py` | exact |
| `app/integrations/yookassa/types.py` (NEW skeleton) | DTO | frozen dataclasses | `app/integrations/email/types.py` | exact |
| `app/integrations/yookassa/client.py` (NEW skeleton) | adapter | async httpx wrapper | `app/integrations/email/client.py:48-194` | exact |
| `app/integrations/yookassa/factory.py` (NEW skeleton) | factory | boot probe | `app/integrations/email/factory.py:39-111` | exact |
| `app/integrations/yookassa/circuit_breaker.py` (NEW skeleton) | infra | Redis sliding window | `app/integrations/email/circuit_breaker.py:46-110` | exact |
| `app/integrations/yookassa/webhook_verifier.py` (NEW skeleton) | dep | FastAPI `Depends()` | `verify_csrf` in `app/core/dependencies.py:879-921` | role-match (no IP-allowlist dep exists yet) |
| `app/integrations/yookassa/_money.py` (NEW) | utility | pure functions | `app/core/formatters.format_money` + `_group_thousands` lines 36-67 | role-match (different direction — wire-format, not display) |
| `app/integrations/yookassa/receipt.py` (NEW skeleton) | builder | pure functions | `app/integrations/email/dispatcher.py:55-` template resolver | partial (no exact analog — skeleton only in P47) |
| `app/core/dependencies.py` (extend with 4 Protocol slots) | composition root | Protocol declarations | `EmailDispatcher` lines 608-679 + `PaymentRecorder` 339-359 | exact (same file, same pattern, append-only) |
| `app/main.py` (wire 4 Protocol slots with no-op placeholders) | composition root | DI wiring | `register_email_dispatcher(enqueue_email_dispatch)` line 257 + earlier register_* calls | exact (same file, established convention) |
| `.importlinter` (preemptive `online_payments` entry + ignores) | tooling | static analysis config | existing `modules-independent` block lines 13–70 | exact |
| `alembic/versions/0033_clients_email_partial_unique.py` (NEW) | migration | DDL + pre-flight SELECT | `0022_users_soft_delete_partial_unique.py` (partial UNIQUE) + `0021_bookings_created_by_user_id_nullable.py` (pre-flight `conn.execute(...).scalar_one()`) | exact (composite — partial-UNIQUE from 0022, pre-flight from 0021) |
| `.env.example` (add `YOOKASSA_*` block) | config | env vars | existing Telegram block lines 38–47 | role-match (no email block in .env.example — email defaults are placeholders in config.py per CLAUDE.md "Telegram-block discipline") |
| `tests/unit/test_locked_audit_events_v17_ast.py` (NEW) | test | AST walker | `tests/unit/test_locked_email_templates_ast.py` (full 323 lines) | exact (mirror byte-for-byte) |

---

## Pattern Assignments

### 1. `app/core/audit.py` — extend `LOCKED_AUDIT_EVENTS` (INFRA-34)

**Analog:** same file, v1.6 block at lines 238–259 (Phase 41 INFRA-34 extension).

**Pattern:** append nine new `(event_name, resource_type)` tuples to the existing frozenset, grouped under a `# v1.7 (Phase 47 lock — emitted in Phases 49/50/51 per INFRA-34)` banner comment. Resource types pre-registered before any callsite ships (INFRA-15 discipline). The docstring block at lines 1–117 should also be extended with a `## v1.7 (Phase 47 lock)` section that names every new pair + the per-event payload key shapes (mirrors the `## v1.6 (Phase 41 lock)` block).

**Concrete excerpt to copy (v1.6 block — `audit.py:238-259`):**
```python
        # v1.6 (Phase 41 lock — emitted in Phases 42/43/44/45 per INFRA-34 / D-41-19)
        # Email transport (Phase 42 EMAIL-01 / EMAIL-04 / EMAIL-06):
        # resource_type is the eventual `email_send_log` table — table itself
        # lands in Phase 42 (migration 0026); pair is pre-registered here per
        # INFRA-34 so the Phase 42 callsite ships green without AST-gate churn.
        ("email_sent", "email_send_log"),
        ("email_send_failed", "email_send_log"),
        # Multi-user admin lifecycle (Phase 43 USERS-03..05 + Phase 44 RESET-03 / RESET-05):
        ("user_invited", "user"),
        ("user_invitation_accepted", "user"),
        ("user_invitation_revoked", "user"),
        ("user_deactivated", "user"),
        ("user_reactivated", "user"),
        ("user_soft_deleted", "user"),
        # Password reset (Phase 44 RESET-01 / RESET-02):
        ("password_reset_requested", "user"),
        ("password_reset_completed", "user"),
        # Payment receipt email (Phase 45 NOTIFY-12):
        ("payment_receipt_emailed", "payment"),
```

**Apply to Phase 47:** insert the 9 v1.7 tuples per CONTEXT.md `<specifics>`
(`online_payment_initiated`, `yookassa_payment_created`, `online_payment_succeeded`,
`online_payment_canceled`, `online_payment_refunded`, `fiscal_receipt_dispatched`,
`fiscal_receipt_succeeded`, `fiscal_receipt_failed`, `yookassa_webhook_received`).
Resource types are TBD by the planner but expected to be
`("online_payment_*", "online_payment")` and `("fiscal_receipt_*", "fiscal_receipt")`
and `("yookassa_webhook_received", "yookassa_webhook")` based on the v1.4/v1.5
naming convention.

**Hard-fail guard (existing — DO NOT touch):** `audit.py:376-381` raises
`AuditEventNotLockedError` on any non-registered pair. New events become legal
at the AST gate level the moment the tuple lands in the frozenset.

---

### 2. `app/core/audit_payloads.py` — 9 new payload classes + 9 registry entries (INFRA-35)

**Analog:** v1.6 block at `audit_payloads.py:465-507` (Phase 42 `EmailSentPayload`, `EmailSendFailedPayload`). v1.6 pattern is the closest because each carries the mandatory `audit_correlation_id: UUID | None` field per D-41-20 — exactly the discipline the v1.7 payloads must inherit per CONTEXT.md "Established Patterns" bullet.

**Imports pattern (excerpt — top of file, lines 33–37):**
```python
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
```

**Core payload-class pattern (excerpt — `EmailSentPayload` lines 468-483):**
```python
class EmailSentPayload(BaseModel):
    """Payload schema for ("email_sent", "email_send_log") — Phase 42 EMAIL-01.

    Emitted by the ARQ `dispatch_email` task after the provider returns 2xx.
    `audit_correlation_id` links back to the triggering business audit row
    (e.g. the `password_reset_requested` row whose flow enqueued the email).
    `provider_message_id` is the provider's deliverability-tracking handle
    (None when the provider did not return one).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    template_id: str
    to_email: str
    provider_message_id: str | None
```

**Registry entry pattern (excerpt — `AUDIT_PAYLOAD_SCHEMAS` dict lines 729-779):**
```python
AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    ...
    # v1.6 (Phase 41 lock — INFRA-35; emitted in Phases 42/43/44/45)
    # Email transport (Phase 42):
    ("email_sent", "email_send_log"): EmailSentPayload,
    ("email_send_failed", "email_send_log"): EmailSendFailedPayload,
    ...
}
```

**Apply to Phase 47:** declare 9 new `class <Event>Payload(BaseModel)` blocks
under a `# v1.7 (Phase 47 lock — INFRA-35; emitted in Phases 49/50/51)` banner.
Each MUST have `model_config = ConfigDict(extra="forbid")` and
`audit_correlation_id: UUID | None` as the first field (D-41-20 lineage).
Add the matching tuple-keyed registry entries to the `AUDIT_PAYLOAD_SCHEMAS`
dict in the same commit.

**Boundary invariant (existing — DO NOT touch):** the module docstring at
lines 29–30 forbids `app.modules.*` imports from this file
(importlinter `core-not-depend-on-modules` contract).

---

### 3. `app/integrations/yookassa/settings.py` — NEW `YooKassaSettings(BaseSettings)` (INFRA-36)

**Analog:** `EmailProviderSettings` in `app/core/config.py:11-45`.

**Note on CONTEXT.md D-47-08 framing:** CONTEXT.md says "mirrors how
`EmailSettings` lives next to `app/integrations/email/`". That framing is
ASPIRATIONAL — today `EmailProviderSettings` is **NOT** a standalone file
under `app/integrations/email/`; it is a nested `BaseModel` inside
`app/core/config.py` and is composed onto `Settings.email`. The Phase 47
intent (per D-47-08) is to deviate from the existing locality and ship a
genuinely standalone `BaseSettings` subclass in
`app/integrations/yookassa/settings.py` with `env_prefix="YOOKASSA_"`. This is
a NEW pattern, not a copy of an existing one. The planner must call this
out in `47-PLAN.md` (deviation rationale: keeps the `Settings` class lean,
makes adapter unit tests easier to mock).

**Imports + class pattern to copy (from `app/core/config.py:1-45`):**
```python
"""Application settings via pydantic-settings (D-15)."""

from datetime import time
from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailProviderSettings(BaseModel):
    """Email transport settings (D-42-28).

    Defaults are sandbox-safe so fresh-clone dev boot does NOT require setting
    email credentials first (mirrors v1.1 Telegram-block discipline in this
    same file). The @model_validator below fails fast at construction when
    provider != 'sandbox' and sandbox_mode=False but credentials/domain/
    webhook secret are missing.
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
            ...
```

**Settings pattern with `model_config` (excerpt — `Settings` class lines 48-55):**
```python
class Settings(BaseSettings):
    """Read configuration from environment + .env file. No prefix; raw env var names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

**Apply to Phase 47:** the new `YooKassaSettings` extends `BaseSettings`
(NOT `BaseModel` — D-47-08 wants real env-loading, unlike
`EmailProviderSettings` which is a sub-block of the host `Settings`). Use
`model_config = SettingsConfigDict(env_prefix="YOOKASSA_", env_file=".env",
env_file_encoding="utf-8", extra="ignore")`. Fields per INFRA-36:
`shop_id: int`, `secret_key: SecretStr`, `return_url: HttpUrl`,
`tax_system_code: int`, `default_vat_code: int`, `sandbox: bool = False`.
A `@model_validator(mode="after")` MAY enforce that non-sandbox mode requires
real `shop_id` + `secret_key` values (mirror lines 30-45) — confirm with
planner.

**`SecretStr` precedent for `secret_key`:** lines 22-23 above + line 27.
`structlog` is already redaction-safe for `SecretStr` (per CONTEXT.md
"Reusable Assets" bullet) — no new redaction config needed.

---

### 4. `app/integrations/yookassa/__init__.py` — NEW package marker

**Analog:** `app/integrations/email/__init__.py` (5 lines, lines 1-5).

**Full file to copy (verbatim shape):**
```python
"""Email integration placeholder.

TODO Phase X+: SMTP/transactional email adapter.
Phase A: empty — no smtplib/aiosmtplib dependency.
"""
```

**Apply to Phase 47:** ship an analogous 4-line docstring announcing the
package's purpose and the phase staging (Phase 47 skeleton, Phase 48 real
client). No exports — symbols are imported by full path elsewhere.

---

### 5. `app/integrations/yookassa/types.py` — NEW skeleton (typed result DTOs)

**Analog:** `app/integrations/email/types.py:27-82` — two frozen dataclasses.

**Imports + class pattern to copy (lines 20-25 + 27-53):**
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class EmailEnvelope:
    """Immutable email payload crossing the dispatch boundary (D-42-16).

    All six fields are mandatory and lock the wire shape ARQ enqueues; do not
    add ``Optional`` defaults here — the dispatcher is responsible for assembling
    a complete envelope before handing it to the transport.
    ...
    """

    to: str
    subject: str
    html: str
    text: str
    template_id: str
    audit_correlation_id: UUID
```

**Classified-result pattern (lines 56-82):**
```python
@dataclass(frozen=True)
class EmailSendResult:
    """Outcome of one transport attempt (D-42-13).

    ``classification`` is the closed taxonomy the dispatcher writes to
    ``email_send_log.status`` and that downstream retry / circuit-breaker logic
    switches on:
    ...
    """

    ok: bool
    classification: Literal["ok", "blocked", "transient_error", "permanent_error"]
    provider_message_id: str | None = None
    error: str | None = None
```

**Apply to Phase 47:** declare frozen dataclass STUBS for
`YooKassaPaymentResult`, `YooKassaRefundResult`, `YooKassaReceiptResult`,
`YooKassaWebhookEvent` per ADAPTER-01. Phase 47 ships just the class shells
(`@dataclass(frozen=True)` + `...` body or minimal field list); Phase 48
fills bodies. The closed-Literal `classification` discipline applies to any
`YooKassa*Result` (use `Literal["ok", "transient_error", "permanent_error", ...]`
matching the email pattern).

---

### 6. `app/integrations/yookassa/client.py` — NEW skeleton (async httpx wrapper)

**Analog:** `app/integrations/email/client.py:48-194`.

**Layer-invariant top-doc to copy (lines 22-26):**
```python
"""...
Layer invariant: this module lives at ``integrations`` layer and MUST NOT
import any module under the per-domain modules package (import-linter
contract 3 -- integrations cannot import modules).
"""
```

**Class shape + classified-failure pattern (excerpt — `EmailClient` lines 48-112):**
```python
class EmailClient:
    """Async Yandex Cloud Postbox SES-V2 adapter (D-42-01 + D-42-02).

    Holds an ``aioboto3.Session`` + endpoint URL + From: address. A fresh
    ``sesv2`` client is opened per ``send_email`` call ...
    Provider SDK retries are disabled via ``Config(retries={'max_attempts': 1})``
    per D-42-02: ARQ owns retry, the breaker (plan 42-08) owns short-circuit.
    """

    def __init__(self, *, session: Any, endpoint_url: str, from_address: str) -> None:
        self._session = session
        self._endpoint_url = endpoint_url
        self._from_address = from_address

    async def send_email(self, envelope: EmailEnvelope) -> EmailSendResult:
        """Send one envelope. NEVER re-raises — every outcome is a value.
        ...
        """
        try:
            async with self._session.client(...) as client:
                response = await client.send_email(...)
            ...
            return EmailSendResult(ok=True, classification="ok", provider_message_id=message_id)
        except ClientError as exc:
            ...
            return EmailSendResult(ok=False, classification="blocked", error=str(exc))
        except Exception as exc:  # outbound boundary -- classify all transport failures
            return EmailSendResult(ok=False, classification="transient_error", error=str(exc))
```

**Sandbox stub pattern (lines 174-194):**
```python
class SandboxEmailClient:
    """No-op stub for dev / CI / preview environments (D-42-29).
    ...
    """

    async def send_email(self, envelope: EmailEnvelope) -> EmailSendResult:
        _log.info("sandbox_email_send", to=envelope.to, ...)
        return EmailSendResult(ok=True, classification="ok", provider_message_id=f"sandbox-{uuid4()}")
```

**Apply to Phase 47:** ship `class YooKassaClient` SKELETON with `__init__`
holding `httpx.AsyncClient` + settings, and method STUBS for `create_payment`,
`get_payment`, `create_refund`, `get_refund` returning `NotImplementedError`
or empty default DTOs. Real bodies land in Phase 48 ADAPTER-02. The
never-re-raise / classified-result discipline must be DOCUMENTED in the
class docstring even though Phase 47 has no real bodies, so Phase 48
implementor cannot deviate. Also ship `SandboxYooKassaClient` skeleton for
the `settings.sandbox=True` path.

---

### 7. `app/integrations/yookassa/factory.py` — NEW skeleton (boot probe)

**Analog:** `app/integrations/email/factory.py:39-111`.

**Locked-signature rationale + function shape (excerpt — lines 1-40):**
```python
"""Email client factory + boot-time domain probe (Phase 42 D-42-29 + D-42-30).

Single entrypoint ``build_email_client`` returns the configured transport for
Wave 3 callers: FastAPI's async lifespan (HTTP-side compose root) and ARQ's
``WorkerSettings.on_startup`` (worker-side compose root). Both callsites are
already coroutine-shaped and ``await`` the factory naturally.

LOCKED async signature -- divergence from ``telegram.bot.build_bot``:
...
The factory is also explicitly **uncached**: a fresh client is constructed
per call so aiohttp connection pools owned by aioboto3 sessions do not leak
across worker container restarts.

Layer invariant: this module lives at ``integrations`` layer and MUST NOT
import from the per-domain modules package (import-linter contract 3).
"""

from __future__ import annotations

import aioboto3
import structlog
from botocore.config import Config

from app.core.config import EmailProviderSettings
from app.integrations.email.client import EmailClient, SandboxEmailClient

_log = structlog.get_logger("integrations.email.factory")


async def build_email_client(
    *, settings: EmailProviderSettings
) -> EmailClient | SandboxEmailClient:
    """Construct a fresh email client per call (no caching).
    ...
    """
    if settings.provider == "sandbox" or settings.sandbox_mode:
        return SandboxEmailClient()

    session = aioboto3.Session(...)
    async with session.client("sesv2", ...) as probe_client:
        resp = await probe_client.get_email_identity(EmailIdentity=settings.from_domain)
    ...
    return EmailClient(session=session, endpoint_url=..., from_address=...)
```

**Apply to Phase 47:** ship `async def build_yookassa_client(*, settings:
YooKassaSettings) -> YooKassaClient | SandboxYooKassaClient` SKELETON. Body
in Phase 47 may be just the sandbox short-circuit + a stubbed return of
`YooKassaClient(...)` with no probe. Phase 48 ADAPTER-03 wires the real
boot-time API probe (`GET /v3/me` or equivalent). Document the
"never raises at boot — degraded mode on probe failure" contract in the
docstring per ADAPTER-03 spec.

---

### 8. `app/integrations/yookassa/circuit_breaker.py` — NEW skeleton (Redis sliding window)

**Analog:** `app/integrations/email/circuit_breaker.py:1-110` (full file is the template).

**Key-prefix + threshold constants pattern (lines 37-41):**
```python
_CIRCUIT_KEY_PREFIX: Final[str] = "sz:email:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "sz:email:circuit_window:"
_FAILURE_THRESHOLD: Final[int] = 5
_WINDOW_SECONDS: Final[int] = 60
_OPEN_TTL_SECONDS: Final[int] = 300  # 5 minutes (D-42-14)
```

**Atomic MULTI/EXEC pipeline pattern (lines 89-104):**
```python
async with redis.pipeline(transaction=True) as pipe:
    pipe.zadd(window_key, {member: now_ms})
    pipe.zremrangebyscore(window_key, 0, cutoff)
    pipe.expire(window_key, _WINDOW_SECONDS * 2)
    pipe.zcard(window_key)
    results = await pipe.execute()

count = int(results[3])

if count >= _FAILURE_THRESHOLD:
    await redis.set(f"{_CIRCUIT_KEY_PREFIX}{provider}", "1", ex=_OPEN_TTL_SECONDS)
    _log.warning("circuit_open", provider=provider, failures_in_window=count, ...)
```

**Apply to Phase 47:** the Phase 47 file can be either (a) the full
implementation copy with `sz:yookassa:circuit:` / `sz:yookassa:circuit_window:`
prefixes (preferred — generic Redis primitive, zero risk in skeleton phase),
or (b) function stubs to be filled in Phase 51 FISCAL-05. Recommend (a)
because it costs ~110 LoC and unblocks Phase 51 entirely. Note: CONTEXT.md
INFRA-37 puts the breaker in Phase 51 FISCAL-05; Phase 47 may ship just an
empty stub if the planner wants strict bedrock-only scope. **Defer to
planner judgment** — both are defensible.

---

### 9. `app/integrations/yookassa/webhook_verifier.py` — NEW skeleton (IP-allowlist `Depends()`)

**Analog:** `verify_csrf` in `app/core/dependencies.py:879-921` (the FastAPI-`Depends()` pattern with a frozenset constant gate). No existing IP-allowlist verifier exists in the codebase — this is a NEW shape.

**`Depends()`-callable pattern (excerpt — `verify_csrf` lines 876-921):**
```python
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


async def verify_csrf(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Double-submit CSRF check (D-07). Short-circuits on safe methods (D-06).

    Validation:
      1. If method is in {GET, HEAD, OPTIONS, TRACE}, return None (read-only —
         no CSRF check; T-06-07 accept).
      2. Otherwise, read `sportzal_csrf` cookie + `X-CSRF-Token` header.
      3. If either is missing OR they don't match (`secrets.compare_digest`,
         constant-time per T-06-05 mitigation), emit `event=csrf_mismatch` and
         raise `CsrfMismatch`.
    ...
    """
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (...):
        await audit.emit(session, "csrf_mismatch", ...)
        raise CsrfMismatch("csrf_mismatch")
```

**Apply to Phase 47:** ship `webhook_verifier.py` containing:
1. `YOOKASSA_TRUSTED_IPS: frozenset[str] = frozenset({"185.71.76.0/27", ...})` — the 6 published CIDRs (CONTEXT.md `<specifics>` instructs to capture from the official webhooks doc and cite the URL in a module docstring). Use `Final[frozenset[str]]` typing.
2. `async def verify_yookassa_ip(request: Request) -> None:` skeleton — the real IP check lands in Phase 48 ADAPTER-05. Phase 47 ships just the import-resolvable name with `raise NotImplementedError` body and the docstring naming the sandbox bypass.

The sandbox-bypass branch (`if settings.sandbox: return`) per D-47-07 should be documented in the docstring so the Phase 48 implementor can't drift.

---

### 10. `app/integrations/yookassa/_money.py` — NEW (kopecks ↔ rubles converters)

**Analog:** `app/core/formatters.format_money` + `_group_thousands` at `app/core/formatters.py:36-67`. Existing `format_money` is **display-side** (kopecks → "1 200 ₽" Russian-locale string). The new `_money.py` is **wire-format** (kopecks → "199.00" plain ASCII for ЮKassa API body) — same DOMAIN (money), different DIRECTION and consumer.

**Pure-function + Final-typed constants pattern to copy (lines 16-44):**
```python
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

_MSK: Final[ZoneInfo] = ZoneInfo("Europe/Moscow")
_NBSP: Final[str] = " "
...


def _group_thousands(value: int) -> str:
    """Render a non-negative int with NBSP between thousand groups (e.g. 1200 -> '1 200')."""
    s = str(value)
    chunks: list[str] = []
    while len(s) > 3:
        chunks.append(s[-3:])
        s = s[:-3]
    chunks.append(s)
    return _NBSP.join(reversed(chunks))


def format_money(kopecks: int) -> str:
    """Render kopecks as a Russian-locale RUB string with NBSPs.

    Examples:
        format_money(0) == "0 ₽"
        format_money(120000) == "1 200 ₽"
        format_money(150) == "1,50 ₽"
        format_money(-5000) == "-50 ₽"
    """
    sign = "-" if kopecks < 0 else ""
    abs_k = abs(kopecks)
    rubles, frac = divmod(abs_k, 100)
    body = _group_thousands(rubles)
    if frac == 0:
        return f"{sign}{body}{_NBSP}₽"
    return f"{sign}{body},{frac:02d}{_NBSP}₽"
```

**Apply to Phase 47:** the new `_money.py` ships TWO pure functions:

```python
"""ЮKassa wire-format money converters (Phase 47 INFRA-39).

Underscore-prefix on the module signals integration-internal use. The single
public money formatter for user-facing display remains
``app.core.formatters.format_money`` — this module is the wire-format
counterpart for ЮKassa API body construction (kopecks-int ↔ "199.00"
two-decimal-string) and webhook parsing.

Pure functions — no I/O. Decimal discipline: never use float arithmetic;
``Decimal`` + ``Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)``
is the canonical conversion path. The 10 edge cases per CONTEXT.md
``<specifics>`` (0, 1, 99, 100, 9999999, rounding, negative, leading zeros,
"199" vs "199.00", non-numeric rejection) are exercised by
``tests/unit/integrations/yookassa/test_money.py``.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN


def kopecks_to_yookassa(kopecks: int) -> str:
    """Convert integer kopecks → ЮKassa wire ``"NNN.NN"`` string.

    Example: ``19900 → "199.00"``. Negative input raises ``ValueError``
    (ЮKassa amounts are always positive — refunds carry separate sign at
    the payment-row level, not at the wire-amount level).
    """
    if kopecks < 0:
        raise ValueError(f"kopecks must be non-negative, got {kopecks}")
    rubles = Decimal(kopecks) / Decimal(100)
    return str(rubles.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def yookassa_to_kopecks(amount: str) -> int:
    """Convert ЮKassa wire ``"NNN.NN"`` string → integer kopecks.

    Example: ``"199.00" → 19900``. Rejects non-numeric, scientific notation,
    or > 2 decimal places (raises ``ValueError``).
    """
    d = Decimal(amount)  # raises decimal.InvalidOperation on bad input
    if d < 0:
        raise ValueError(f"amount must be non-negative, got {amount!r}")
    return int((d * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
```

The 10-edge-case test file lives at `tests/unit/integrations/yookassa/test_money.py` — see Section 12 for the AST test pattern that the converter test file does NOT need to copy (this is a plain unit test).

---

### 11. `app/integrations/yookassa/receipt.py` — NEW skeleton (54-ФЗ builder placeholder)

**Analog:** no exact match. Closest is `app/integrations/email/dispatcher.py:55-` (`_resolve_template` walker — a pure-function module-level helper). Phase 47 ships a SKELETON only; the real `build_receipt_item()` + `PaymentSubject`/`PaymentMode`/`VatCode` enums land in Phase 48 ADAPTER-04.

**Apply to Phase 47:** ship `receipt.py` with:

```python
"""ЮKassa 54-ФЗ receipt item builder (Phase 47 INFRA-36 skeleton; Phase 48 ADAPTER-04).

Phase 47: empty module + module docstring announcing the staged delivery.
Phase 48 ships ``build_receipt_item()`` + the locked-Literal enums
``PaymentSubject`` (``"service"`` locked), ``PaymentMode``
(``"full_payment"``/``"full_prepayment"`` locked), and ``VatCode``
(IntEnum from ``YooKassaSettings.default_vat_code``).

Layer invariant: lives at ``integrations`` layer — MUST NOT import from
``app.modules.*`` (importlinter ``integrations-not-depend-on-modules``).
"""
```

No code body. The locked-Literal enums are pre-mentioned in the docstring so
the Phase 48 implementor cannot drift toward open StrEnum values that would
defeat the AST gate (Pitfall 8 — wrong 54-ФЗ tags).

---

### 12. `app/core/dependencies.py` — extend with 4 new Protocol slots (INFRA-38)

**Analog:** same file, `EmailDispatcher` slot at lines 608-679 (Phase 41 D-41-24). This is the strongest analog because v1.6 EmailDispatcher carries the same shape: composition-root setter + defensive-raise accessor + Protocol class with `__call__`. It's also the most recent precedent (Phase 41, 6 weeks ago) so its conventions are current.

**CRITICAL — file location:** This is `app/core/dependencies.py`, NOT
`app/core/services.py`. See "Critical Correction Up-Front" at the top of
this document.

**Header-comment + Protocol pattern (excerpt — lines 608-679):**
```python
# ─────────────────────────────────────────────────────────────────────────────
# Phase 41 INFRA-40 / D-41-24 — EmailDispatcher Protocol slot (v1.6 email).
#
# Eleventh composition-root carve-out. Phase 42 wires the real implementation
# (enqueues ``dispatch_email`` ARQ task) in BOTH ``app.main.create_app()`` AND
# ``app.workers.__init__.WorkerSettings.on_startup`` (REG-29-03 double-wire
# parity — mirrors register_trainer_by_id_resolver / register_slot_by_id_resolver).
# Phase 41 ships only the slot declaration; no callsite yet.
#
# Defensive-raise accessor (mirrors get_payment_recorder at line ~398;
# NOT the silent-None pattern of resolve_active_membership at line 117) —
# a missing email dispatcher in the email-issuing flow is a hard
# misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class EmailDispatcher(Protocol):
    """Structural type for the email-dispatch callable (Phase 41 D-41-24).
    ...
    """

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None: ...


_email_dispatcher: EmailDispatcher | None = None


def register_email_dispatcher(impl: EmailDispatcher) -> None:
    """Composition-root setter (Phase 41 D-41-24).
    ...
    """
    global _email_dispatcher
    _email_dispatcher = impl


def get_email_dispatcher() -> EmailDispatcher:
    """Defensive accessor (Phase 41 D-41-24) — raises if slot not registered.

    Mirrors ``get_payment_recorder`` defensive-raise pattern (line ~398);
    a missing email dispatcher in an email-issuing flow is a hard
    misconfiguration, not a recoverable state.
    """
    if _email_dispatcher is None:
        raise RuntimeError(
            "EmailDispatcher slot not registered — register via "
            "app.core.dependencies.register_email_dispatcher() in "
            "app/main.py:create_app() AND app/workers/__init__.py "
            "WorkerSettings.on_startup (REG-29-03 double-wire)."
        )
    return _email_dispatcher
```

**`PaymentRecorder` precedent for non-trivial `__call__` signature (lines 339-385):**
```python
class PaymentRecorder(Protocol):
    """Structural type for the sale-side payment recorder (Phase 32 D-32-14).

    Return type ``Any`` is intentional: the concrete return is
    ``app.modules.payments.models.Payment``, but this Protocol lives in
    ``app.core`` which is forbidden from importing ``app.modules.*``
    (importlinter `core-not-depend-on-modules` contract). Callers in the
    modules layer that need typed access cast the result locally.
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        subject_kind: str,
        subject_id: UUID,
        amount_kopecks: int,
        method: str = "cash",
        received_by_user_id: UUID,
        audit_actor: CurrentUser,
    ) -> Any: ...
```

**Apply to Phase 47:** append FOUR Protocol-slot blocks per the established
pattern. The four slots are:
1. `YooKassaClientProvider` — returns the configured `YooKassaClient` instance. Double-wired (FastAPI + ARQ worker per REG-29-03).
2. `FiscalReceiptDispatcher` — enqueues `dispatch_fiscal_receipt` ARQ task. Double-wired (same as EmailDispatcher precedent).
3. `MembershipActivator` — activates a membership atomically inside webhook UoW. Single-wired (HTTP only, no ARQ entry path).
4. `PtPackageActivator` — activates a PT-package. Single-wired (same as #3).

Use `Protocol` from `typing` (already imported, line 20). Return types should
be `Any` for the same reason `PaymentRecorder` returns `Any` (core may not
import `app.modules.*`). Each slot ships with:
- Section divider comment (lines 608-621 style)
- `class XxxYyy(Protocol)` with docstring
- `_xxx_yyy: XxxYyy | None = None` module-level
- `def register_xxx_yyy(impl: XxxYyy) -> None` setter
- `def get_xxx_yyy() -> XxxYyy` defensive-raise accessor (mirrors `get_email_dispatcher` 665-679 — RuntimeError pointing at the wiring sites)

---

### 13. `app/main.py` — wire 4 new Protocol slots with no-op placeholders

**Analog:** existing `register_email_dispatcher(enqueue_email_dispatch)` call at `app/main.py:257` + the 12+ other `register_*` calls in `create_app()`.

**Imports pattern (existing — lines 55-68):**
```python
from app.core.dependencies import (
    register_active_membership_resolver,
    register_active_pt_package_resolver,
    register_booking_completer,
    register_booking_slot_restorer,
    register_client_by_telegram_resolver,
    register_email_dispatcher,
    register_payment_recorder,
    register_payment_refunder,
    register_slot_by_id_resolver,
    register_trainer_by_id_resolver,
    register_user_loader,
    register_user_session_invalidator,  # Phase 43 D-43-26/27 — single-wire.
)
```

**Wire-up pattern (excerpt — lines 251-270, EmailDispatcher + UserSessionInvalidator):**
```python
    # Phase 42 D-42-26 / EMAIL-04 — REG-29-03 double-wire of the EmailDispatcher
    # slot. The IDENTICAL symbol reference ``enqueue_email_dispatch`` is also
    # passed at ``app/workers/__init__.py:WorkerSettings.on_startup`` so the
    # Phase 42 parity test (plan 42-11) sees a byte-equal callable in both
    # processes. The ArqRedis pool itself is registered in the lifespan above
    # because it requires an awaitable factory (``arq.create_pool``).
    register_email_dispatcher(enqueue_email_dispatch)

    # Phase 43 D-43-26/27 — UserSessionInvalidator SINGLE-wire (no ARQ consumer).
    ...
    set_auth_redis_factory(lambda: app.state.redis)
    register_user_session_invalidator(invalidate_all_families_for_user)
```

**Apply to Phase 47:** in `create_app()`, after the existing
`register_user_session_invalidator(...)` block, add four new
`register_yookassa_client_provider(...)`, `register_fiscal_receipt_dispatcher(...)`,
`register_membership_activator(...)`, `register_pt_package_activator(...)`
calls. Phase 47 wires NO-OP placeholders (module-level lambdas or stub
functions that raise NotImplementedError at call time, NOT at registration
time — registration must succeed so `get_*` accessors do not fire the
defensive RuntimeError during request handling). Two viable shapes:

**Option A (preferred — lambda stubs):** Define module-level no-op coroutines in `app/main.py` or in a small `app/integrations/yookassa/_stubs.py`, e.g.:
```python
async def _yookassa_client_provider_noop_stub() -> Any:
    raise NotImplementedError("YooKassa client lands in Phase 48 ADAPTER-02")
```
and wire them. The stubs satisfy the Protocol signature; the defensive accessor returns non-None; any actual callsite (none exist in Phase 47) would raise.

**Option B (deferred-wire):** do NOT call `register_*` in Phase 47; rely on the defensive RuntimeError to surface mis-staging if a Phase 48–50 callsite lands ahead of its wiring. Lower noise, but breaks INFRA-38 wording ("Protocol slot declarations at composition root: ... double-wired").

CONTEXT.md decision D-47-01 says "Empty/no-op wiring at composition root" —
explicitly Option A. The planner picks the concrete shape.

**REG-29-03 double-wire for `YooKassaClientProvider` + `FiscalReceiptDispatcher`:**
the same `register_*` calls must also be added to
`app/workers/__init__.py:WorkerSettings.on_startup` (lines around 252 today)
to match the `register_email_dispatcher(enqueue_email_dispatch)` byte-equal
parity contract. `MembershipActivator` + `PtPackageActivator` are HTTP-only
(single-wire) per D-47-01 — wire ONLY in `app/main.py:create_app()`.

---

### 14. `.importlinter` — preemptive `app.modules.online_payments` entry + ignores (INFRA-40)

**Analog:** same file, existing `modules-independent` contract block at `.importlinter:13-70`.

**Modules-independent block (lines 13-30):**
```ini
[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
    app.modules.clients
    app.modules.memberships
    app.modules.visits
    app.modules.trainers
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications
    app.modules.payments
    app.modules.pt_packages
    app.modules.pt_sessions
    app.modules.users
ignore_imports =
```

**Targeted ignore pattern (lines 53-70 — Phase 45 NOTIFY pattern):**
```ini
    # Phase 45 NOTIFY-11/12/13 (Plan 45-09) — orchestrator-site receipt-email
    # fanout in memberships/service.py needs (a) the PaymentReceipt ORM row
    # to write the idempotency ledger, and (b) format_actor_display to compose
    # the operator display name into the receipt render context. Both are
    # narrowly scoped to memberships/service.py only; the broader
    # modules-independent invariant remains in force for every other file.
    app.modules.memberships.service -> app.modules.payments.models
    app.modules.memberships.service -> app.modules.users.display
    # Phase 45 NOTIFY-11/12/13 (Plan 45-10) — same rationale ...
    app.modules.pt_packages.service -> app.modules.payments.models
    app.modules.pt_packages.service -> app.modules.users.display
```

**Apply to Phase 47:** two edits:

1. Add `app.modules.online_payments` to the `modules =` list (line 29-ish, alphabetical or end-of-list per current convention — keep end-of-list to preserve diff hygiene). Phase 49 actually ships the module body but the contract entry lands preemptively in Phase 47 to fail fast on misplaced imports.

2. Add three targeted ignores per INFRA-40 (mirror lines 53-70 style with a `# Phase 47 INFRA-40` rationale comment):
```ini
    # Phase 47 INFRA-40 — preemptive ignores for v1.7 online-payments module
    # (the module body ships in Phase 49; contract lands now per INFRA-15
    # discipline). Each cross-module edge is narrowly scoped to the
    # online_payments service layer:
    #   - record_payment(method='online') needs payments.models for the
    #     ledger-row return type (mirrors Phase 45 memberships → payments
    #     pattern).
    #   - users.display for the operator display name in receipt context
    #     (mirrors Phase 45 memberships → users pattern).
    #   - email.dispatcher needs online_payments.email_templates so the
    #     central dispatcher walker can resolve v1.7 template IDs (mirrors
    #     Phase 45 dispatcher → auth/users/memberships/bookings/payments
    #     email_templates allowlist at lines 80-91).
    app.modules.online_payments.service -> app.modules.payments.models
    app.modules.online_payments.service -> app.modules.users.display
```

And in the `integrations-not-depend-on-modules` contract (lines 72-91), add:
```ini
    app.integrations.email.dispatcher -> app.modules.online_payments.email_templates
```

The exact source → target tuples MUST be quoted verbatim from INFRA-40 wording:
"`online_payments → payments.models`, `online_payments → users.display`,
`email.dispatcher → online_payments.email_templates`".

---

### 15. `alembic/versions/0033_clients_email_partial_unique.py` — NEW (INFRA-41)

**Analog (composite, two parts):**
- Partial UNIQUE on lower(email): `0022_users_soft_delete_partial_unique.py` (entire file, lines 1-82)
- Pre-flight `conn.execute(...).fetchall()` / `scalar_one()` operator guard: `0021_bookings_created_by_user_id_nullable.py:56-66`

**Header + revision tags pattern (`0022:1-39`):**
```python
"""users.deleted_at + partial-UNIQUE on lower(email) for soft-delete (INFRA-38).

Revision ID: 0022_users_soft_delete_unique
Revises: 0021_bookings_actor_nullable
Create Date: 2026-05-18 18:00:00.000000

Phase 41 INFRA-38 / D-41-15. ...
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0022_users_soft_delete_unique"
down_revision: str | None = "0021_bookings_actor_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXISTING_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"
_NEW_EMAIL_PARTIAL_UNIQUE_INDEX = "uq_users_email_active"
```

**Partial-UNIQUE creation pattern (`0022:46-69`):**
```python
def upgrade() -> None:
    # 1. Add deleted_at column ...
    ...

    # 3. Create partial UNIQUE on lower(email) — only enforce across non-deleted rows.
    #    This is an INDEX (not a constraint) because expression predicates require
    #    an index in Postgres. Mirrors 0008_freeze.py / 0017_bookings.py precedent.
    op.create_index(
        _NEW_EMAIL_PARTIAL_UNIQUE_INDEX,
        "users",
        [text("lower(email)")],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )
```

**Pre-flight operator-guard pattern (`0021:56-66`):**
```python
def downgrade() -> None:
    """Restore NOT NULL — refuses to run if any row has NULL created_by_user_id.

    Operator guard: a bot booking lands with ``created_by_user_id=NULL``; if
    any such row exists, downgrading would either silently violate the
    restored NOT NULL constraint (catastrophic) or trigger a Postgres-side
    failure halfway through the migration (also bad). ...
    """
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM bookings WHERE created_by_user_id IS NULL"
        )
    ).scalar_one()
    if null_count > 0:
        raise RuntimeError(
            "cannot downgrade: NULL created_by_user_id rows present "
            f"({null_count} rows); operator must clean up bot bookings first"
        )
    op.alter_column(...)
```

**Apply to Phase 47:** the new `0033_clients_email_partial_unique.py` ships:

```python
"""clients.email partial UNIQUE on lower(email) for case-insensitive uniqueness (INFRA-41).

Revision ID: 0033_clients_email_partial_unique
Revises: 0032_booking_notifications_widen_kind
Create Date: 2026-05-21 ...

Phase 47 INFRA-41. The clients.email column ALREADY exists (Alembic 0002,
since v1.1) — this migration does NOT add it and does NOT narrow Text → VARCHAR(255)
per D-47-03. It adds ONLY a partial UNIQUE on (lower(email)) WHERE email IS NOT NULL
AND deleted_at IS NULL.

Pre-flight duplicate check (D-47-05): the migration aborts with a RuntimeError
listing offending lower(email) values if any duplicate already exists. Single-gym
pet-project scale makes duplicates unlikely; fail-fast is safer than silent dedup.

Mirrors 0022_users_soft_delete_partial_unique.py partial-UNIQUE pattern + the
operator-guard pre-flight pattern from 0021_bookings_created_by_user_id_nullable.py.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0033_clients_email_partial_unique"
down_revision: str | None = "0032_booking_notifications_widen_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_EMAIL_PARTIAL_UNIQUE_INDEX = "ix_clients_email_lower_unique"


def upgrade() -> None:
    # Pre-flight duplicate check (D-47-05).
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            "SELECT lower(email) AS email_lc, COUNT(*) AS n "
            "FROM clients "
            "WHERE email IS NOT NULL AND deleted_at IS NULL "
            "GROUP BY lower(email) HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        offenders = ", ".join(f"{row.email_lc!r} ({row.n}x)" for row in duplicates)
        raise RuntimeError(
            "cannot apply 0033 — duplicate clients.email (case-insensitive) "
            f"rows present: {offenders}. Operator must dedup manually "
            "(soft-delete, merge, or correct typos) and re-run the migration."
        )

    # Create partial UNIQUE on lower(email).
    op.create_index(
        _NEW_EMAIL_PARTIAL_UNIQUE_INDEX,
        "clients",
        [text("lower(email)")],
        unique=True,
        postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(_NEW_EMAIL_PARTIAL_UNIQUE_INDEX, table_name="clients")
```

**Down-revision pin:** confirm `0032_booking_notifications_widen_kind` is the
current alembic HEAD before pinning. `ls` of the versions directory shows
0032 as the last v1.6 migration — pin to it.

---

### 16. `.env.example` — add `YOOKASSA_*` block (INFRA-36)

**Analog:** the existing Telegram block in `.env.example:38-47`. No email
block exists in the current `.env.example` (email defaults are placeholders
inside `EmailProviderSettings` per CLAUDE.md "fresh-clone dev boot" discipline
— same precedent applies to YooKassa).

**Telegram-block pattern (lines 38-47):**
```bash
# Phase 7 — Telegram OTP channel (D-10, D-03).
# Defaults are intentional placeholders so fresh-clone `docker-compose up`
# + admin-web dev with VITE_API_MODE=http boots without bot credentials.
# The telegram-bot worker REFUSES to start while these placeholders are in
# effect — set real values from @BotFather before running the bot.
TELEGRAM_BOT_TOKEN=placeholder-telegram-bot-token-not-real
TELEGRAM_BOT_USERNAME=placeholder_bot
OTP_DEEP_LINK_TTL_SECONDS=600
OTP_CODE_TTL_SECONDS=300
OTP_MAX_ATTEMPTS=5
```

**Apply to Phase 47:** append a `# Phase 47 — ЮKassa online payments + 54-ФЗ
fiscal receipts (INFRA-36).` banner block. Six entries per D-47-09:
`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL`,
`YOOKASSA_TAX_SYSTEM_CODE`, `YOOKASSA_DEFAULT_VAT_CODE`, `YOOKASSA_SANDBOX`.
All values placeholder-style (e.g.
`YOOKASSA_SHOP_ID=placeholder-shop-id-not-real`,
`YOOKASSA_SECRET_KEY=placeholder-secret-not-real`,
`YOOKASSA_SANDBOX=true`). Banner comment must explicitly call out "no real
credentials in git" per D-47-09.

---

### 17. `tests/unit/test_locked_audit_events_v17_ast.py` — NEW (AST gate test)

**Analog:** `tests/unit/test_locked_email_templates_ast.py` (full 323 lines; full-file copy with substitutions).

**Walker shape pattern (lines 1-118 — module docstring + walker functions):**
```python
"""AST walker for `get_email_dispatcher()(template_id=...)` callsites
— Phase 41 INFRA-36 / D-41-11 / D-41-13.

Mirrors `test_audit_taxonomy.py` shape: static analysis over
`apps/backend/app/**/*.py` that asserts every `get_email_dispatcher()(...)`
callsite passes `template_id=<literal str>` resolving to a member of
`LOCKED_EMAIL_TEMPLATES`.
...
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.audit import LOCKED_EMAIL_TEMPLATES

_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "email_ast_violations"


def _resolve_str_literal(node: ast.expr | None) -> str | None:
    """Return the literal str value if `node` is `ast.Constant(str)`, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_get_email_dispatcher_call(node: ast.Call) -> bool:
    inner = node.func
    if not isinstance(inner, ast.Call):
        return False
    inner_func = inner.func
    return isinstance(inner_func, ast.Name) and inner_func.id == "get_email_dispatcher"


def _extract_template_id_arg(call: ast.Call) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == "template_id":
            return kw.value
    if call.args:
        return call.args[0]
    return None


def _iter_dispatcher_calls(tree: ast.AST) -> Iterator[tuple[int, ast.expr | None]]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_get_email_dispatcher_call(node):
            continue
        yield node.lineno, _extract_template_id_arg(node)


def _collect_violations(py_path: Path) -> list[str]:
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as exc:  # pragma: no cover — defensive
        pytest.fail(f"Could not parse {py_path}: {exc}")

    violations: list[str] = []
    try:
        rel = py_path.relative_to(_REPO_ROOT)
    except ValueError:
        rel = py_path
    for lineno, arg_node in _iter_dispatcher_calls(tree):
        prefix = f"{rel}:{lineno} — get_email_dispatcher()(template_id=...)"
        if arg_node is None:
            violations.append(f"{prefix} missing template_id argument")
            continue
        literal_value = _resolve_str_literal(arg_node)
        if literal_value is None:
            violations.append(f"{prefix} is not a literal str (got {ast.dump(arg_node)})")
            continue
        if literal_value not in LOCKED_EMAIL_TEMPLATES:
            violations.append(f"{prefix} value {literal_value!r} is not in LOCKED_EMAIL_TEMPLATES")
    return violations


def test_real_callsites_pass() -> None:
    """Phase 41: no `get_email_dispatcher()(...)` callsite exists in prod code
    yet — Phase 42 ships the first. Walker therefore collects 0 violations
    against the production tree.
    """
    all_violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        all_violations.extend(_collect_violations(py))
    assert not all_violations, (
        "get_email_dispatcher()(template_id=...) callsite(s) violate the "
        "LOCKED_EMAIL_TEMPLATES literal-only gate.\n"
        "Either fix the literal at the callsite or extend LOCKED_EMAIL_TEMPLATES "
        "in apps/backend/app/core/audit.py.\n"
        "Offenders:\n  " + "\n  ".join(all_violations)
    )
```

**Synthetic-violation fixture test pattern (lines 141-159):**
```python
def test_bogus_template_id_is_rejected() -> None:
    """D-41-13: the synthetic-violation fixture uses literal 'BOGUS_NOT_LOCKED'
    which is NOT in LOCKED_EMAIL_TEMPLATES. Walker MUST report a violation
    that cites the bogus value.
    """
    fixture = _FIXTURE_DIR / "bogus_template_id.py"
    violations = _collect_violations(fixture)
    assert violations, ...
    assert any("BOGUS_NOT_LOCKED" in v for v in violations), ...
```

**Apply to Phase 47:** the new `test_locked_audit_events_v17_ast.py` must
AST-gate TWO targets per the upstream prompt:

1. **`LOCKED_AUDIT_EVENTS` v1.7 events** — walker over `apps/backend/app/**/*.py` that asserts every `await audit.emit(session, "<event>", ..., resource_type="<type>", ...)` call passes literal-str event names from the v1.7 subset of `LOCKED_AUDIT_EVENTS`. Note: the existing `tests/unit/test_audit_taxonomy.py` ALREADY enforces the literal-only gate for all `audit.emit` calls — confirm with the planner whether the new v1.7-specific test is redundant (in which case ship just a `test_v17_events_registered_in_frozenset()` that asserts each of the 9 new identifiers is a member of `LOCKED_AUDIT_EVENTS`), OR ship a positive-fixture test in the style of `test_email_otp_login_real_callsite_present` (lines 162-202) that pins one literal v1.7 callsite per event (these callsites don't exist until Phase 49+, so this test would be a STUB asserting `pytest.skip("v1.7 callsites land in Phase 49")` until then).

2. **`YOOKASSA_TRUSTED_IPS`** — walker over `apps/backend/app/**/*.py` that asserts every `Depends(verify_yookassa_ip)` ATTACHMENT and any place that reads `YOOKASSA_TRUSTED_IPS` does so via the literal frozenset import (no `set(...)`, no dynamic construction). Mirror the `_is_get_email_dispatcher_call` shape but matching `Depends(<Name id='verify_yookassa_ip'>)` patterns.

The synthetic-violation fixture directory pattern (line 39 `_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "email_ast_violations"`) implies a new `tests/unit/fixtures/yookassa_ast_violations/` directory with `bogus_event_name.py` + `non_literal_event.py` fixtures.

**File location:** `apps/backend/tests/unit/test_locked_audit_events_v17_ast.py`
per Claude's Discretion bullet "Create a new ... mirroring
test_locked_email_templates_ast.py. Do not extend a single existing AST gate
test."

---

## Shared Patterns

### Pattern A — Locked-constant + AST-gate discipline (INFRA-15)

**Source:** `app/core/audit.py:139-261` (`LOCKED_AUDIT_EVENTS`) + `app/core/audit.py:264-300` (`LOCKED_EMAIL_TEMPLATES`).

**Apply to:** every new locked constant in Phase 47 — the 9 audit events,
`YOOKASSA_TRUSTED_IPS`, the `PaymentSubject` / `PaymentMode` literals (when
they land in Phase 48). Discipline:

1. The constant ships as a `frozenset[T]` (or `Literal["..."]` union) in a clearly-named module.
2. Registration MUST land BEFORE any consumer callsite (INFRA-15 wording: "before any callsite").
3. The runtime emitter / consumer asserts membership and hard-fails (`raise <SpecificError>`) on miss — no graceful degradation, no DEBUG-only assertion.
4. A static AST walker test in `tests/unit/` asserts every consumer callsite passes a literal `ast.Constant(str)` (not a variable, not an f-string) that is a member of the frozenset.

### Pattern B — Defensive-raise vs silent-None Protocol-slot accessor

**Source:** `app/core/dependencies.py` — two co-existing patterns:
- Silent-None (mirrors `resolve_active_membership` line 117): when "slot unset" is indistinguishable from "no result" at the call site. Used for `ActiveMembership`, `ClientByTelegram`, `SlotById`, `BookingSlotRestorer`, `BookingCompleter`, `ActivePtPackage`, `TrainerById`.
- Defensive-raise (mirrors `get_payment_recorder` line 404, `get_email_dispatcher` line 665): when missing wiring is hard misconfiguration. Used for `PaymentRecorder`, `PaymentRefunder`, `EmailDispatcher`, `UserSessionInvalidator`.

**Apply to:** the 4 new Phase 47 Protocol slots. Recommended classification
(planner confirms):
- `YooKassaClientProvider`: defensive-raise (missing client = misconfig).
- `FiscalReceiptDispatcher`: defensive-raise (missing dispatcher = 54-ФЗ violation risk).
- `MembershipActivator`: defensive-raise (webhook handler can't proceed without activator — Pitfall 3, double activation, requires guaranteed activation path).
- `PtPackageActivator`: defensive-raise (same rationale as MembershipActivator).

### Pattern C — REG-29-03 double-wire vs single-wire at composition root

**Source:** `app/main.py:257` (`register_email_dispatcher` — double-wired with `app/workers/__init__.py:266`) vs `app/main.py:270` (`register_user_session_invalidator` — single-wired, HTTP-only).

**Apply to:** Phase 47 four-slot wiring:
- `YooKassaClientProvider`: DOUBLE-wire (HTTP webhook path AND ARQ `dispatch_fiscal_receipt` task path both call ЮKassa). Add to BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup`.
- `FiscalReceiptDispatcher`: DOUBLE-wire (mirrors EmailDispatcher exactly — same ARQ enqueueing shape).
- `MembershipActivator`: SINGLE-wire (HTTP webhook only — no ARQ entry path for activation).
- `PtPackageActivator`: SINGLE-wire (same rationale).

### Pattern D — Boundary docstring: "MUST NOT import app.modules.*"

**Source:** every file under `app/core/` and `app/integrations/`. Example:
`app/integrations/email/client.py:22-26`:

```python
Layer invariant: this module lives at ``integrations`` layer and MUST NOT
import any module under the per-domain modules package (import-linter
contract 3 -- integrations cannot import modules).
```

**Apply to:** every new file under `app/integrations/yookassa/`. Include the
identical layer-invariant block in the module docstring. The exception bridge
(`integrations.email.dispatcher → modules.<X>.email_templates`) is governed
by explicit `ignore_imports` entries in `.importlinter` — the v1.7
analogous bridge is `integrations.email.dispatcher → online_payments.email_templates`
per INFRA-40 (added preemptively in Phase 47; consumer ships in Phase 52
NOTIFY-02).

---

## No Analog Found

None. Every Phase 47 deliverable has a strong existing analog. The two
"role-match but novel shape" cases are documented above:
- `YooKassaSettings` as standalone `BaseSettings` is a deviation from
  `EmailProviderSettings` (nested `BaseModel`). Pattern transfers cleanly
  but with the deliberate `env_prefix=` divergence.
- `webhook_verifier.verify_yookassa_ip` is the first IP-allowlist
  `Depends()` callable in the codebase — pattern transfers from
  `verify_csrf` but with different gate (CIDR membership vs cookie-equal).

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/**`
- `apps/backend/app/integrations/email/**`
- `apps/backend/app/main.py` + `apps/backend/app/workers/__init__.py`
- `apps/backend/alembic/versions/**`
- `apps/backend/tests/unit/test_locked_email_templates_ast.py`
- `apps/backend/.importlinter`
- `apps/backend/.env.example`

**Files scanned:** ~25 (12 read in full, ~13 inspected via grep / wc).

**Pattern extraction date:** 2026-05-21.

---

## Critical Findings Summary (for planner)

1. **CONTEXT.md `app/core/services.py` reference is WRONG.** Protocol slots
   live in `app/core/dependencies.py`. See "Critical Correction Up-Front"
   at the top of this document. Planner must either flag this in `47-PLAN.md`
   or escalate to the user.

2. **`EmailSettings` does not exist as a standalone file today.** It is
   `EmailProviderSettings` nested in `app/core/config.py`. D-47-08 deliberately
   deviates by putting `YooKassaSettings` in a standalone file under
   `app/integrations/yookassa/`. Document this deviation in `47-PLAN.md`.

3. **`.env.example` has NO email block today.** The Phase 47 `YOOKASSA_*`
   block is the first integration-credential block to land in `.env.example`
   (Telegram block is the only precedent). Pattern transfers cleanly.

4. **Existing `LOCKED_AUDIT_EVENTS` already counts ~58 entries** spanning
   v1.1–v1.6. Adding 9 grows the set to ~67. The hard-fail guard at
   `audit.py:376-381` already enforces unknown-pair rejection — no new gate
   logic needed, only the frozenset extension.

5. **`tests/unit/test_audit_taxonomy.py` already exists** and AST-gates every
   `audit.emit(...)` callsite for literal-only event names. The v1.7 AST
   test target overlaps. Planner should decide whether `test_locked_audit_events_v17_ast.py`
   is redundant on the event side (in which case ship it for
   `YOOKASSA_TRUSTED_IPS` only) or whether it adds positive-fixture-style
   per-callsite literal pinning (mirrors lines 162-202 of the email AST test).
