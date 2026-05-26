"""Email transport adapters (Phase 42 D-42-01 / D-42-02 / D-42-29).

Two classes form the entire transport surface that the ARQ ``dispatch_email``
task (plan 42-08) drives:

- ``EmailClient``: real async Yandex Cloud Postbox SES-V2 adapter built on top
  of aioboto3. Mirrors the classified-failure pattern of
  ``app.integrations.telegram.sender.send_otp_dm`` (PATTERNS.md §3) — every
  transport outcome is returned as an ``EmailSendResult`` value, NEVER as a
  raised exception. ARQ retry / circuit-breaker logic switches on the closed
  ``classification`` Literal, not on exception types.

- ``SandboxEmailClient``: a drop-in stub (D-42-29) used when the operator
  selects ``provider='sandbox'`` or flips ``sandbox_mode=True``. Logs the
  rendered envelope at INFO and returns ``EmailSendResult.ok`` with a
  ``sandbox-<uuid4>`` provider_message_id — no outbound HTTP, no aioboto3
  session construction.

Both classes expose the same ``async def send_email(envelope) -> EmailSendResult``
signature so the factory at ``app/integrations/email/factory.py:build_email_client``
can return either as a drop-in replacement without callers branching on type.

Layer invariant: this module lives at ``integrations`` layer and MUST NOT
import any module under the per-domain modules package (import-linter
contract 3 -- integrations cannot import modules).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.integrations.email.types import EmailEnvelope, EmailSendResult

_log = structlog.get_logger("integrations.email.client")

# Yandex Cloud Postbox / AWS SES-V2 error codes that map to terminal "blocked"
# outcomes (recipient rejected, account paused). Do NOT retry these.
_BLOCKED_ERROR_CODES: frozenset[str] = frozenset(
    {"MessageRejected", "AccountSendingPausedException"}
)


class EmailClient:
    """Async Yandex Cloud Postbox SES-V2 adapter (D-42-01 + D-42-02).

    Holds an ``aioboto3.Session`` + endpoint URL + From: address. A fresh
    ``sesv2`` client is opened per ``send_email`` call (aioboto3's contract
    — sessions are factories, clients are async-context-managed). Provider
    SDK retries are disabled via ``Config(retries={'max_attempts': 1})``
    per D-42-02: ARQ owns retry, the breaker (plan 42-08) owns short-circuit.
    """

    def __init__(
        self,
        *,
        session: Any,
        endpoint_url: str,
        from_address: str,
    ) -> None:
        self._session = session
        self._endpoint_url = endpoint_url
        self._from_address = from_address

    async def send_email(self, envelope: EmailEnvelope) -> EmailSendResult:
        """Send one envelope. NEVER re-raises — every outcome is a value.

        Classification chain (mirror of ``send_otp_dm`` outbound-boundary
        pattern, expanded for the richer SES-V2 failure surface):

        - ``ClientError`` Code ∈ ``_BLOCKED_ERROR_CODES`` → ``blocked``
        - ``ClientError`` HTTP 5xx → ``transient_error``
        - ``ClientError`` HTTP 4xx (non-blocked) → ``permanent_error``
        - any other ``Exception`` → ``transient_error``
        - success → ``ok`` with ``MessageId`` populated as
          ``provider_message_id``
        """
        try:
            async with self._session.client(
                "sesv2",
                endpoint_url=self._endpoint_url,
                config=Config(retries={"max_attempts": 1}),
            ) as client:
                response = await client.send_email(
                    FromEmailAddress=self._from_address,
                    Destination={"ToAddresses": [envelope.to]},
                    Content={
                        "Simple": {
                            "Subject": {"Data": envelope.subject, "Charset": "UTF-8"},
                            "Body": {
                                "Html": {"Data": envelope.html, "Charset": "UTF-8"},
                                "Text": {"Data": envelope.text, "Charset": "UTF-8"},
                            },
                        }
                    },
                )
            message_id = response.get("MessageId") if isinstance(response, dict) else None
            _log.info(
                "email_send_ok",
                to=envelope.to,
                template_id=envelope.template_id,
                provider_message_id=message_id,
            )
            return EmailSendResult(
                ok=True,
                classification="ok",
                provider_message_id=message_id,
            )
        except ClientError as exc:
            err = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
            code = err.get("Code", "") if isinstance(err, dict) else ""
            meta = (
                exc.response.get("ResponseMetadata", {}) if isinstance(exc.response, dict) else {}
            )
            http_status = meta.get("HTTPStatusCode", 0) if isinstance(meta, dict) else 0
            if code in _BLOCKED_ERROR_CODES:
                _log.info(
                    "email_send_blocked",
                    to=envelope.to,
                    template_id=envelope.template_id,
                    error_code=code,
                )
                return EmailSendResult(
                    ok=False,
                    classification="blocked",
                    error=str(exc),
                )
            if isinstance(http_status, int) and http_status >= 500:
                _log.warning(
                    "email_send_transient_error",
                    to=envelope.to,
                    template_id=envelope.template_id,
                    error_code=code,
                    http_status=http_status,
                )
                return EmailSendResult(
                    ok=False,
                    classification="transient_error",
                    error=str(exc),
                )
            _log.warning(
                "email_send_permanent_error",
                to=envelope.to,
                template_id=envelope.template_id,
                error_code=code,
                http_status=http_status,
            )
            return EmailSendResult(
                ok=False,
                classification="permanent_error",
                error=str(exc),
            )
        except Exception as exc:  # outbound boundary -- classify all transport failures
            # Network / timeout / unexpected. Treat as transient — ARQ retry can recover.
            _log.warning(
                "email_send_transient_error",
                to=envelope.to,
                template_id=envelope.template_id,
                error=str(exc),
            )
            return EmailSendResult(
                ok=False,
                classification="transient_error",
                error=str(exc),
            )


class SandboxEmailClient:
    """No-op stub for dev / CI / preview environments (D-42-29).

    Returns ``EmailSendResult.ok`` with a ``sandbox-<uuid4>`` provider_message_id
    without making any outbound call. Logs the rendered envelope at INFO so
    developers can confirm rendering visually in the worker log stream.
    """

    async def send_email(self, envelope: EmailEnvelope) -> EmailSendResult:
        _log.info(
            "sandbox_email_send",
            to=envelope.to,
            subject=envelope.subject,
            text_preview=envelope.text[:80],
            template_id=envelope.template_id,
        )
        return EmailSendResult(
            ok=True,
            classification="ok",
            provider_message_id=f"sandbox-{uuid4()}",
        )
