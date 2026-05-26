"""Phase 46 D-46-14 #4 / VER-10 — bounce-webhook + active-send concurrent race.

Real-Postgres concurrent ``POST /api/v1/_internal/email/webhook`` (bounce
notification for ``email_send_log.provider_message_id=X``) + a fresh
``EmailDispatcher.dispatch(...)``-equivalent enqueueing a NEW send to the
same recipient. Outcomes:

- First row: ``status='bounced'`` (webhook UPDATEd the existing row by
  ``provider_message_id``).
- Second row: ``status='sent'`` (the fresh send proceeded independently —
  no cross-row cancellation).

No cross-row cancellation — bounces and active sends are independent per
Phase 42 D-42 best-effort + backoff lineage. Audit correlation IDs on
both events stay intact.

Webhook auth is HMAC-SHA256 over the raw POST body (Phase 42 D-42-17),
header ``X-Email-Webhook-Signature``. We reuse the same ``_sign()``
helper shape used in
``tests/integration/email_webhook/test_webhook_hmac_and_routing.py`` and
patch ``app.api.v1._internal.email.router.get_settings`` so the router
sees a known webhook secret without touching the lru_cached real
settings object.

Mirrors Phase 45 D-45-28 real-commit engine pattern
(``test_payment_receipt_race.py``) — a standalone ``real_commit_engine``
fixture issuing REAL COMMITs, because the bounce-webhook UPDATE +
fresh-send INSERT must race across SEPARATE sessions (the default
SAVEPOINT-wrapped ``db_session`` would serialise them under one outer
transaction and mask the invariant).

The "fresh dispatch" half is simulated by directly INSERTing a fresh
``email_send_log`` row (``status='sent'``) on a second independent
session — this is byte-for-byte what the ARQ worker writes on a normal
``EmailDispatcher`` → ``dispatch_email`` task lifecycle (per
``app/integrations/email/dispatcher.py`` + ``app/workers/tasks.py``).
We assert at the DB layer that:

  1. The webhook UPDATE landed on the EXISTING row (status='bounced').
  2. The fresh INSERT landed as an INDEPENDENT row (status='sent').
  3. Neither commit aborted the other (no cross-row cancellation).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import EmailProviderSettings, Settings, get_settings
from app.main import create_app

_WEBHOOK_SECRET = "test-secret-46-08-bounce-race"  # noqa: S105 -- test fixture, not a real secret


def _sign(body: bytes, secret: str = _WEBHOOK_SECRET) -> str:
    """HMAC-SHA256 hex digest over the raw request body.

    Mirrors the ``_sign()`` helper at
    ``tests/integration/email_webhook/test_webhook_hmac_and_routing.py:65``
    and the router's verification logic at
    ``apps/backend/app/api/v1/_internal/email/router.py:88-92``.
    """
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _patch_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Override the router's ``get_settings()`` so the webhook accepts our test secret.

    The router imports ``get_settings`` at module scope and calls it per
    request — patching the symbol in the router module is sufficient and
    avoids invalidating the lru_cache on the real ``get_settings``.
    Pattern reused verbatim from
    ``tests/integration/email_webhook/test_webhook_hmac_and_routing.py:39-62``.
    """
    base = get_settings()
    overridden = base.model_copy(
        update={
            "email": EmailProviderSettings(
                provider="sandbox",
                sandbox_mode=True,
                webhook_secret=SecretStr(_WEBHOOK_SECRET),
            ),
        }
    )

    def _override() -> Settings:
        return overridden

    monkeypatch.setattr(
        "app.api.v1._internal.email.router.get_settings",
        _override,
    )
    yield


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine — same pattern as Phase 45 D-45-28.

    The default ``db_session`` SAVEPOINT pattern (tests/conftest.py:57)
    composes nested transactions; the webhook UPDATE in one session +
    the fresh INSERT in another cannot race meaningfully inside a single
    outer SAVEPOINT, so we need an engine that issues real COMMITs.

    Skips on unreachable Postgres rather than erroring inside
    ``asyncio.gather``. Cleans up with TRUNCATE on teardown
    (real-commit writes are not rolled back). CASCADE handles any FK
    chain that future migrations may add.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-46-14 #4 bounce-webhook race; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE email_send_log, audit_log, users RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_bounce_webhook_active_send_race(
    real_commit_engine: AsyncEngine,
) -> None:
    """Concurrent bounce-webhook + fresh active-send → independent rows.

    Outcome (Phase 42 D-42 best-effort lineage):
      - Existing row (provider_message_id=X) → status='bounced'.
      - Fresh row (new send to same recipient) → status='sent'.
      - No cross-row cancellation — bounces affect ONLY the matching row.
    """
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    recipient = f"race-bounce+{uuid4().hex[:8]}@local.dev"
    existing_send_id = uuid4()
    existing_corr_id = uuid4()
    fresh_send_id = uuid4()
    fresh_corr_id = uuid4()
    provider_message_id = f"msg-{uuid4().hex}"

    # ── Seed an existing email_send_log row in 'sent' status (the row the
    # webhook will UPDATE to 'bounced'). Columns mirror EmailSendLog model
    # at app/integrations/email/models.py:47-122.
    async with session_factory() as setup:
        await setup.execute(
            text(
                """
                INSERT INTO email_send_log
                    (id, audit_correlation_id, to_address, template_id, provider,
                     provider_message_id, status, bounce_type, recorded_at)
                VALUES
                    (:id, :corr, :rcpt, :tpl, 'yandex_postbox',
                     :pmid, 'sent', NULL, now())
                """
            ),
            {
                "id": existing_send_id,
                "corr": existing_corr_id,
                "rcpt": recipient,
                "tpl": "EMAIL_OTP_LOGIN",
                "pmid": provider_message_id,
            },
        )
        await setup.commit()

    # SES-V2 contract per router.py:110-117 — eventType + mail.messageId +
    # bounce.bounceType. The signature MUST be computed over the EXACT
    # bytes posted as the body (the router signs raw_body, not a
    # re-serialised JSON), so we serialise once and reuse the bytes for
    # both the signature and the POST body.
    webhook_body_dict = {
        "eventType": "Bounce",
        "mail": {"messageId": provider_message_id},
        "bounce": {"bounceType": "Permanent"},
    }
    webhook_body = json.dumps(webhook_body_dict).encode("utf-8")
    webhook_signature = _sign(webhook_body)

    # Build the FastAPI app under a LifespanManager so app.state.sessionmaker
    # is bound (the webhook's Depends(get_db) needs it). The lifespan opens
    # its OWN engine against the same DATABASE_URL — the webhook UPDATE
    # commits via that engine and our session_factory above reads it back
    # under PostgreSQL READ COMMITTED isolation (visible after commit).
    app = create_app()

    async def _bounce_webhook(lifespan_app: object) -> int:
        """Deliver the HMAC-signed bounce notification to /_internal/email/webhook."""
        async with AsyncClient(
            transport=ASGITransport(app=lifespan_app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            r = await client.post(
                "/api/v1/_internal/email/webhook",
                headers={
                    "content-type": "application/json",
                    # Header name is lowercase per router.py:87 — case
                    # tolerance is covered separately by the WR-06 test.
                    "x-email-webhook-signature": webhook_signature,
                },
                content=webhook_body,  # raw bytes — signature is over these exact bytes
            )
            return r.status_code

    async def _fresh_active_send() -> None:
        """Simulate a fresh EmailDispatcher → worker send landing as 'sent'.

        The real dispatcher (``app/integrations/email/dispatcher.py``)
        only ENQUEUES; the ARQ worker (``app/workers/tasks.py``) is what
        writes the ``email_send_log`` row after the provider acks. For
        the race-invariant assertion (no cross-row cancellation) we
        write that row directly in an independent session — byte-for-byte
        what the worker would produce on a normal send-cycle.
        """
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO email_send_log
                        (id, audit_correlation_id, to_address, template_id, provider,
                         provider_message_id, status, bounce_type, recorded_at)
                    VALUES
                        (:id, :corr, :rcpt, :tpl, 'yandex_postbox',
                         :pmid, 'sent', NULL, now())
                    """
                ),
                {
                    "id": fresh_send_id,
                    "corr": fresh_corr_id,
                    "rcpt": recipient,
                    "tpl": "EMAIL_OTP_LOGIN",
                    "pmid": f"msg-{uuid4().hex}",  # DIFFERENT provider message id
                },
            )
            await session.commit()

    async with LifespanManager(app):
        results = await asyncio.gather(
            _bounce_webhook(app),
            _fresh_active_send(),
            return_exceptions=True,
        )

    # Neither half should have raised — the bounce-vs-active-send paths
    # are independent by design.
    for r in results:
        assert not isinstance(r, BaseException), (
            f"unexpected exception in concurrent race: {r!r} — bounce-webhook "
            f"and active-send must NOT cross-cancel"
        )

    webhook_status = results[0]
    assert webhook_status == 202, (
        f"webhook expected 202 Accepted (HMAC valid + row matched), got {webhook_status}"
    )

    # ── Verify DB invariants ────────────────────────────────────────────
    async with session_factory() as verify:
        # Existing row → 'bounced' (the webhook UPDATEd it by provider_message_id).
        existing_status = (
            await verify.execute(
                text("SELECT status FROM email_send_log WHERE id = :id"),
                {"id": existing_send_id},
            )
        ).scalar_one()
        assert existing_status == "bounced", (
            f"existing row expected 'bounced' after webhook UPDATE, got {existing_status!r}"
        )

        existing_bounce_type = (
            await verify.execute(
                text("SELECT bounce_type FROM email_send_log WHERE id = :id"),
                {"id": existing_send_id},
            )
        ).scalar_one()
        assert existing_bounce_type == "hard", (
            f"existing row expected bounce_type='hard' (Permanent → hard), "
            f"got {existing_bounce_type!r}"
        )

        # Fresh row → 'sent' (NOT cancelled by the bounce on the sibling row).
        # Plan 46-08 acceptance also accepts 'queued' if the dispatch lifecycle
        # is ARQ-enqueue-only at the test moment.
        fresh_status = (
            await verify.execute(
                text("SELECT status FROM email_send_log WHERE id = :id"),
                {"id": fresh_send_id},
            )
        ).scalar_one()
        assert fresh_status in ("sent", "queued"), (
            f"fresh row expected status in ('sent','queued') — active send must NOT be "
            f"cancelled by a bounce on a sibling row to the same recipient — "
            f"got {fresh_status!r}"
        )

        # Audit correlation IDs preserved on both rows (forensic chain intact).
        rows = (
            await verify.execute(
                text(
                    """
                    SELECT id, audit_correlation_id
                    FROM email_send_log
                    WHERE to_address = :rcpt
                    ORDER BY recorded_at ASC
                    """
                ),
                {"rcpt": recipient},
            )
        ).all()
        assert len(rows) == 2, (
            f"expected exactly 2 email_send_log rows for {recipient!r} "
            f"(existing + fresh), got {len(rows)}: {rows!r}"
        )
        corr_ids = {row[1] for row in rows}
        assert existing_corr_id in corr_ids, (
            f"existing audit_correlation_id {existing_corr_id!r} missing from {corr_ids!r}"
        )
        assert fresh_corr_id in corr_ids, (
            f"fresh audit_correlation_id {fresh_corr_id!r} missing from {corr_ids!r}"
        )
