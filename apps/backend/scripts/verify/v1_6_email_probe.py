"""Phase 46 / VER-12 — live email-deliverability probe (Plan 46-12 / D-46-19..22).

One-shot throwaway probe. Sends one email each to a yandex.ru + mail.ru +
rambler.ru recipient via the PRODUCTION-shape email transport (the real
``EmailClient`` aioboto3 / Yandex Postbox SES-V2 adapter — NOT the
``SandboxEmailClient`` stub). Captures the per-send ``provider_message_id``
and prints them. The operator then manually fetches the
``Authentication-Results:`` header line from each recipient's mailbox
("show original" / "view source") and pastes the redacted form into
``.planning/milestones/v1.6-VERIFICATION-LOG.md`` under the
``email_deliverability_probe:`` YAML block.

NO IMAP automation per D-46-19 — keeps the probe tiny + avoids credential
plumbing for 3 mailbox providers.

NO ARQ per Plan 46-12 critical note 6 — the production ``EmailDispatcher``
implementation at ``app.integrations.email.dispatcher.enqueue_email_dispatch``
(reachable via ``get_email_dispatcher()``) ENQUEUES into ARQ and returns
``None`` (Protocol signature in ``app.core.dependencies.EmailDispatcher``).
For a one-shot live probe we want SYNC capture of ``provider_message_id``,
which only the worker-side ``EmailClient.send_email`` call returns. So
this script bypasses the ARQ enqueue layer and drives the same transport
adapter (``app.integrations.email.client.EmailClient``) directly, using
the same template (``EMAIL_OTP_LOGIN``, D-46-21) and the same
``EmailEnvelope`` shape that the worker would build. The send path is
byte-identical to production from the SMTP/SES-V2 packet level onwards —
only the queue hop is elided.

Recipient redaction (T-46-12-01): the script prints recipient addresses
ONLY in domain-only form (``***@yandex.ru``) to stdout. The full address
is never echoed. The operator captures the actual address in their own
local notes; the committed VERIFICATION-LOG.md only carries the redacted
form per D-46-20.

Run from ``apps/backend/``:

    PROBE_YANDEX_TO=foo+probe@yandex.ru \\
    PROBE_MAIL_TO=foo+probe@mail.ru \\
    PROBE_RAMBLER_TO=foo+probe@rambler.ru \\
    EMAIL_PROVIDER_API_KEY=<real-yandex-postbox-secret-key> \\
    AWS_ACCESS_KEY_ID=<real-yandex-postbox-access-key-id> \\
    EMAIL_FROM_DOMAIN=mail.sportzal.ru \\
    uv run python -m scripts.verify.v1_6_email_probe

Exit codes:
  0 — all 3 sends returned ok=True with a provider_message_id.
  1 — at least one send raised or returned ok=False.
  2 — operator misconfiguration (env vars / creds missing).
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

# Env setdefault — mirrors export_openapi.py:28-46. MUST precede any
# ``app.*`` import so ``Settings()`` instantiation does not blow up on
# missing required fields (DATABASE_URL / REDIS_URL / SECRET_KEY).
os.environ.setdefault("ENVIRONMENT", "staging")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://probe:probe@localhost:5432/probe")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "x" * 48)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "placeholder-not-used-by-probe")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "placeholder_bot")

# Operator-supplied credentials (NO setdefault — abort cleanly if missing).
# EMAIL_PROVIDER_API_KEY is the locked plan vocabulary (Plan 46-12 truths);
# under the hood Yandex Postbox / SES-V2 expects AWS_SECRET_ACCESS_KEY +
# AWS_ACCESS_KEY_ID, so we accept either naming and normalise.
_secret_key = os.environ.get("EMAIL_PROVIDER_API_KEY") or os.environ.get(
    "AWS_SECRET_ACCESS_KEY"
)
if not _secret_key:
    print(
        "FATAL: EMAIL_PROVIDER_API_KEY (or AWS_SECRET_ACCESS_KEY) must be set; no default.",
        file=sys.stderr,
    )
    print(
        "       Export the staging Yandex Postbox secret key before running.",
        file=sys.stderr,
    )
    sys.exit(2)

_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
if not _access_key:
    print(
        "FATAL: AWS_ACCESS_KEY_ID must be set (Yandex Postbox access-key id).",
        file=sys.stderr,
    )
    sys.exit(2)

_from_domain = os.environ.get("EMAIL_FROM_DOMAIN", "mail.sportzal.ru")
_from_address = os.environ.get("EMAIL_FROM_ADDRESS", f"noreply@{_from_domain}")

RECIPIENTS: dict[str, str | None] = {
    "yandex.ru": os.environ.get("PROBE_YANDEX_TO"),
    "mail.ru": os.environ.get("PROBE_MAIL_TO"),
    "rambler.ru": os.environ.get("PROBE_RAMBLER_TO"),
}
_missing = [provider for provider, addr in RECIPIENTS.items() if not addr]
if _missing:
    print(f"FATAL: missing env-var recipient(s) for: {_missing}", file=sys.stderr)
    print(
        "       Set PROBE_YANDEX_TO + PROBE_MAIL_TO + PROBE_RAMBLER_TO.",
        file=sys.stderr,
    )
    sys.exit(2)

# Safe to import the app now that env is wired.
# NOTE on get_email_dispatcher: the production EmailDispatcher Protocol slot
# at app.core.dependencies.get_email_dispatcher returns the ARQ-enqueueing
# impl (enqueue_email_dispatch), which yields no provider_message_id at the
# enqueue site. We bypass that surface for the probe and drive the same
# EmailClient transport adapter directly to capture the provider id sync.
from app.core.config import EmailProviderSettings  # noqa: E402
from app.integrations.email.client import EmailClient  # noqa: E402
from app.integrations.email.factory import build_email_client  # noqa: E402
from app.integrations.email.types import EmailEnvelope  # noqa: E402
from app.modules.auth.email_templates import TEMPLATES as AUTH_TEMPLATES  # noqa: E402


def _redact(addr: str) -> str:
    """Domain-only redaction (T-46-12-01).

    Personal recipient addresses MUST NOT land in stdout that the operator
    might paste into a committed file. Returns ``***@<domain>``; if the
    address has no '@' it returns the literal '***' so we never leak a
    local-part fragment.
    """
    if "@" not in addr:
        return "***"
    _, _, domain = addr.partition("@")
    return f"***@{domain}"


async def main() -> int:
    # EMAIL_OTP_LOGIN — locked template per D-46-21 (re-used, no probe-only
    # variant introduced). LITERAL string for LOCKED_EMAIL_TEMPLATES AST gate
    # parity (the AST gate scans dispatcher callsites; this script is not a
    # dispatcher callsite, but the literal is preserved for forensic clarity).
    template_id = "EMAIL_OTP_LOGIN"
    template = AUTH_TEMPLATES[template_id]
    fixture_otp = "000000"  # throwaway probe payload (T-46-12-03 accept).

    # Build the production-shape transport. provider='yandex_postbox' +
    # sandbox_mode=False forces the real aioboto3 SES-V2 adapter; the
    # @model_validator on EmailProviderSettings will reject missing creds
    # at construction so we surface configuration errors before any send.
    email_settings = EmailProviderSettings(
        provider="yandex_postbox",
        sandbox_mode=False,
        aws_access_key_id=_access_key,  # type: ignore[arg-type]
        aws_secret_access_key=_secret_key,  # type: ignore[arg-type]
        endpoint_url=os.environ.get(
            "EMAIL_ENDPOINT_URL", "https://postbox.cloud.yandex.net"
        ),
        from_address=_from_address,
        from_domain=_from_domain,
        webhook_secret=os.environ.get(  # type: ignore[arg-type]
            "EMAIL_WEBHOOK_SECRET", "probe-not-used"
        ),
    )

    client: EmailClient | object = await build_email_client(settings=email_settings)
    if not isinstance(client, EmailClient):
        # Sandbox stub would defeat the probe purpose; refuse to proceed.
        print(
            "FATAL: factory returned non-production client; refusing to probe.",
            file=sys.stderr,
        )
        return 2

    rendered_html = template.html.render(otp_code=fixture_otp)
    rendered_text = template.text.render(otp_code=fixture_otp)

    results: dict[str, str] = {}
    for provider_domain, addr in RECIPIENTS.items():
        assert addr is not None  # narrowed by the _missing guard above
        envelope = EmailEnvelope(
            to=addr,
            subject=template.subject,
            html=rendered_html,
            text=rendered_text,
            template_id=template_id,
            audit_correlation_id=uuid4(),
        )
        try:
            result = await client.send_email(envelope)
        except Exception as exc:  # noqa: BLE001 — outbound boundary, classify all
            results[provider_domain] = f"FAIL: {exc!r}"
            print(
                f"{provider_domain}: FAIL ({exc!r})  to={_redact(addr)}",
                file=sys.stderr,
            )
            continue

        if result.ok and result.provider_message_id:
            mid = result.provider_message_id
            results[provider_domain] = mid
            # Machine-readable line: "<domain>: <provider_message_id>" per
            # Plan 46-12 truths bullet 5. Redacted recipient on the same line.
            print(f"{provider_domain}: {mid}  to={_redact(addr)}")
        else:
            label = f"FAIL ({result.classification}: {result.error!r})"
            results[provider_domain] = label
            print(
                f"{provider_domain}: {label}  to={_redact(addr)}",
                file=sys.stderr,
            )

    # Summary block — operator copies + completes the Authentication-Results
    # fields by hand from each recipient mailbox's "show original" view.
    # D-46-20: only the redacted form lands in the committed log.
    print()
    print(
        "--- copy into .planning/milestones/v1.6-VERIFICATION-LOG.md "
        "`email_deliverability_probe:` block ---"
    )
    print("email_deliverability_probe:")
    for provider_domain, addr in RECIPIENTS.items():
        assert addr is not None
        print(f"  {provider_domain.replace('.', '_')}:")
        print(f"    to: \"{_redact(addr)}\"")
        print(f"    provider_message_id: \"{results.get(provider_domain, '')}\"")
        print(
            '    authentication_results: '
            '"<paste verbatim from recipient mailbox \'show original\'>"'
        )
        print('    timestamp: ""')

    # Exit 0 only when all three transports succeeded at the SES-V2 layer.
    # Alignment (SPF/DKIM/DMARC) is captured manually by the operator and is
    # a separate DEFER-46-N concern per D-46-22 (1-of-3 alignment fail is not
    # a milestone-close blocker).
    failed = [p for p, mid in results.items() if mid.startswith("FAIL")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
