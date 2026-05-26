"""Phase 52 Plan 52-06 — NOTIFY-05 cancellation regression (no client DM + audit fields).

Regression-locks two invariants established in Phase 50 (D-50-25) and Phase 52
(NOT-05 / D-52-12):

1. ``test_cancellation_audit_carries_party_and_reason``:
   A ``payment.canceled`` webhook with ``cancellation_details`` causes the
   ``online_payment_canceled`` audit row to carry both ``cancellation_party``
   and ``cancellation_reason`` in its JSONB payload (Phase 50 behaviour).

2. ``test_cancellation_enqueues_owner_alert_only_no_client_dm``:
   The ``payment.canceled`` handler enqueues ``dispatch_payment_notification``
   with ``kind="payment_canceled"`` EXACTLY ONCE and NEVER enqueues any client
   kind (``kind="payment_succeeded"`` or ``kind="refund_succeeded"``).

Design notes
------------
- Both tests drive the webhook via ``httpx ASGITransport`` + the SHARED real-
  commit ``webhook_engine`` / ``webhook_client`` + ``webhook_db_session``
  fixtures from ``tests/integration/webhook_yookassa/conftest.py``.
  Those fixtures are re-exported via the directory ``conftest.py`` so they
  are visible to tests in this directory without a per-file re-import.
- The ``arq_pool`` is stubbed via ``app.state.arq_pool`` (the handler reads
  ``request.app.state.arq_pool`` in the router) so ``enqueue_job`` calls are
  recorded without spawning a real worker.
- Tests use ``respx.mock`` via the existing ``yookassa_get_payment_canceled``
  conftest fixture so the re-fetch inside ``handle_payment_canceled`` returns
  the expected canceled status without hitting the real ЮKassa API.
- Tests use ``httpx ASGITransport`` / no real network per CLAUDE.md.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog

# ---------------------------------------------------------------------------
# arq_pool stub fixture (scoped to this module)
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_arq_pool() -> AsyncMock:
    """An AsyncMock that records all ``enqueue_job`` calls without dispatching."""
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    return pool


# ---------------------------------------------------------------------------
# Test 1: audit payload carries cancellation_party + cancellation_reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_audit_carries_party_and_reason(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: Any,
    yookassa_get_payment_canceled: Any,
    webhook_payment_canceled_body: Any,
) -> None:
    """payment.canceled webhook → ``online_payment_canceled`` audit row carries
    both ``cancellation_party`` and ``cancellation_reason`` (D-52-12 regression).

    This is Phase 50 behaviour that must not regress across Phase 52 changes.
    The test drives the real webhook route via ASGITransport; no arq_pool is
    wired so the owner-alert enqueue is a no-op (arq_pool=None default).
    """
    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id,
        party="yandex_checkout",
        reason="general_decline",
    )

    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    # Flush the session so committed rows are visible.
    await webhook_db_session.commit()

    # Audit row must carry both fields.
    rows = (
        (
            await webhook_db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "online_payment_canceled",
                    AuditLog.resource_id == seeded_online_payment_pending.online_payment_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected 1 online_payment_canceled audit row; got {len(rows)}"

    payload = rows[0].payload
    assert payload.get("cancellation_party") == "yandex_checkout", (
        f"cancellation_party missing or wrong: {payload}"
    )
    assert payload.get("cancellation_reason") == "general_decline", (
        f"cancellation_reason missing or wrong: {payload}"
    )


# ---------------------------------------------------------------------------
# Test 2: cancel path enqueues owner alert ONLY — no client DM (NOT-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_enqueues_owner_alert_only_no_client_dm(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: Any,
    yookassa_get_payment_canceled: Any,
    webhook_payment_canceled_body: Any,
    stub_arq_pool: AsyncMock,
) -> None:
    """payment.canceled handler enqueues ``dispatch_payment_notification`` with
    ``kind="payment_canceled"`` exactly once and NEVER enqueues a client kind.

    The stub arq_pool is installed on ``app.state.arq_pool`` before the request
    so the handler's ``arq_pool is not None`` guard fires and records the call.

    NOT-05 hard contract: the cancel path must NEVER produce a client DM
    (kind = ``payment_succeeded`` or ``kind="refund_succeeded"``).
    """
    # Install the stub arq_pool so the handler sees it at request time.
    # ``webhook_client._transport`` and ``.app`` are private httpx internals;
    # we use Any to avoid mypy strict complaints about the dynamic attribute access.
    from httpx._transports.asgi import ASGITransport

    raw_transport: Any = webhook_client._transport
    if not isinstance(raw_transport, ASGITransport):
        pytest.skip("webhook_client transport is not ASGITransport — cannot inject arq_pool")
    asgi_app: Any = raw_transport.app
    asgi_app.state.arq_pool = stub_arq_pool

    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id,
        party="yoo_money",
        reason="fraud_suspected",
    )

    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    # ── Assert: exactly ONE enqueue_job call for dispatch_payment_notification ──
    enqueue_calls = stub_arq_pool.enqueue_job.await_args_list
    # Filter only dispatch_payment_notification calls.
    notif_calls = [
        c for c in enqueue_calls if c.args and c.args[0] == "dispatch_payment_notification"
    ]
    assert len(notif_calls) == 1, (
        f"expected exactly 1 dispatch_payment_notification enqueue; "
        f"got {len(notif_calls)} from calls: {enqueue_calls}"
    )

    # The single call must carry kind="payment_canceled".
    notif_kwargs = notif_calls[0].kwargs  # _kwargs={"payment_id": ..., "kind": ...}
    inner_kwargs = notif_kwargs.get("_kwargs", {})
    assert inner_kwargs.get("kind") == "payment_canceled", (
        f"expected kind='payment_canceled'; got {inner_kwargs}"
    )

    # ── Assert: NO client DM kinds are ever enqueued on the cancel path ──
    # The payment_id in _kwargs carries the online_payment.id (not a ledger row).
    client_kinds = {"payment_succeeded", "refund_succeeded"}
    for c in enqueue_calls:
        if c.args and c.args[0] == "dispatch_payment_notification":
            inner = c.kwargs.get("_kwargs", {})
            assert inner.get("kind") not in client_kinds, (
                f"NOT-05 VIOLATED: cancel path must NEVER enqueue a client kind; "
                f"got kind={inner.get('kind')!r} in call {c}"
            )
