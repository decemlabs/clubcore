"""WH-01 — IP gate verification (Phase 50 success criterion #1).

The route-level ``Depends(verify_yookassa_ip)`` runs BEFORE body parse. The
``YOOKASSA_SANDBOX=true`` default in .env.example bypasses the verifier (Phase
47 D-47-07), so we exercise the 403 branch by overriding the dependency to
raise the same ``HTTPException(403)``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.yookassa.webhook_verifier import verify_yookassa_ip
from app.modules.online_payments.models import OnlinePayment
from tests.integration.webhook_yookassa.conftest import (
    SeededOnlinePayment,
    trusted_ip_header,
)


@pytest.mark.asyncio
async def test_wh01_post_from_untrusted_ip_returns_403(
    app: FastAPI,
    webhook_client: AsyncClient,
    seeded_online_payment_pending: SeededOnlinePayment,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Untrusted-IP POST returns 403 and NO online_payments mutation occurs."""

    async def _reject() -> None:
        raise HTTPException(status_code=403, detail="forbidden_ip")

    app.dependency_overrides[verify_yookassa_ip] = _reject
    try:
        before_status = await webhook_db_session.scalar(
            select(OnlinePayment.status).where(
                OnlinePayment.id == seeded_online_payment_pending.online_payment_id
            )
        )
        assert before_status == "pending"

        body = webhook_payment_succeeded_body(
            seeded_online_payment_pending.yookassa_payment_id
        )
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=body,
            headers={"X-Real-IP": "1.1.1.1"},
        )
        assert response.status_code == 403, response.text

        await webhook_db_session.commit()  # flush any pending writes (none expected)
        after_status = await webhook_db_session.scalar(
            select(OnlinePayment.status).where(
                OnlinePayment.id == seeded_online_payment_pending.online_payment_id
            )
        )
        assert after_status == "pending", (
            "WH-01: rejected webhook MUST NOT mutate online_payments.status"
        )
    finally:
        app.dependency_overrides.pop(verify_yookassa_ip, None)


@pytest.mark.asyncio
async def test_wh01_post_from_trusted_ip_does_not_403(
    webhook_client: AsyncClient,
    webhook_payment_succeeded_body: Any,
    yookassa_get_payment_succeeded: Any,
) -> None:
    """Trusted-IP POST does NOT 403 (handler may 200 on orphan path — that's fine)."""
    # No seed — handler short-circuits at orphan path with 200; the IP gate
    # is what we're verifying here.
    body = webhook_payment_succeeded_body("00000000-0000-0000-0000-000000000000")
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=body,
        headers=trusted_ip_header(),
    )
    assert response.status_code == 200, response.text
    assert response.text == "ok"
