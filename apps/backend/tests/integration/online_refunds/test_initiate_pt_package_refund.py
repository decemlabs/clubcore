"""Phase 51 Plan 51-08 — integration smoke test for POST /pt-packages/{id}/refund.

Mirrors the membership refund happy-path; PT-packages skip the must_unfreeze /
renewed-source guards (no freeze concept, no renewal chain in v1.x) so the
critical-path coverage is just one happy test. Deep PT-package coverage is
deferred to Plan 51-10 e2e.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_refunds.models import OnlineRefund


def _refund_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


@pytest.mark.asyncio
async def test_initiate_pt_package_refund_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_pt_package_with_succeeded_online_payment,
    yookassa_create_refund_success,
) -> None:
    """POST /pt-packages/{id}/refund returns 202 + pending OnlineRefund row."""
    _client, _op, _payment, pt_package = await seeded_pt_package_with_succeeded_online_payment()

    idem_key = uuid4()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/pt-packages/{pt_package.id}/refund",
        json={"idempotencyKey": str(idem_key), "reason": "client-request"},
        headers=_refund_headers(authed_client_reception),
    )
    assert response.status_code == 202, response.text

    data = response.json()["data"]
    assert data["status"] == "pending"
    online_refund_id = UUID(data["onlineRefundId"])

    row = await db_session.scalar(select(OnlineRefund).where(OnlineRefund.id == online_refund_id))
    assert row is not None
    assert row.status == "pending"
    assert row.idempotency_key == str(idem_key)
