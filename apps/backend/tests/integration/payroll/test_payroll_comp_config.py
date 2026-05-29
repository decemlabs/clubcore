"""Integration tests for PUT/GET /api/v1/payroll/trainer-configs/{trainer_id} (Phase 58 PAY-01).

Coverage:
  - Owner can PUT a new comp config (INSERT-only versioned — D-58-02).
  - Two consecutive PUTs create 2 rows; GET returns the latest (D-58-10 / D-58-11).
  - Owner can GET the active config; resolves latest effective_from <= today.
  - 404 comp_config_missing when no config exists for the trainer.
  - Resolver returns the correct row when multiple versions exist for one trainer.
  - Reception receives 403 on PUT (T-58-17).
  - Reception receives 403 on GET (T-58-17).
  - Pydantic rejects commission_pct_bps > 10000 with 422 (T-58-20 mitigation).
  - audit_log row written with event='trainer_comp_config_set' on every PUT
    (D-58-17 atomic audit chain verified by direct SQL SELECT).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return the X-CSRF-Token header from the client's cookie jar."""
    token: str = client.cookies.get("clubcore_csrf") or ""
    return {"X-CSRF-Token": token}


async def test_owner_can_put_comp_config(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """Owner PUT returns 200 with the newly created config row (PAY-01 D-58-10)."""
    trainer = await make_trainer()
    body = {
        "commissionPctBps": 1000,
        "sessionFeeKopecks": 200000,
        "effectiveFrom": "2026-01-01",
    }
    r = await authed_client_owner.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json=body,
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert UUID(data["id"])  # non-null UUID
    assert data["trainerId"] == str(trainer.id)
    assert data["commissionPctBps"] == 1000
    assert data["sessionFeeKopecks"] == 200000
    assert data["effectiveFrom"] == "2026-01-01"
    assert data["createdAt"] is not None


async def test_owner_put_creates_new_row_does_not_update(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    db_session: AsyncSession,
) -> None:
    """Two PUTs produce 2 rows (INSERT-only versioned, D-58-02); GET returns latest."""
    trainer = await make_trainer()
    url = f"/api/v1/payroll/trainer-configs/{trainer.id}"
    headers = _csrf(authed_client_owner)

    r1 = await authed_client_owner.put(
        url,
        json={"commissionPctBps": 500, "effectiveFrom": "2026-01-01"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.put(
        url,
        json={"commissionPctBps": 1000, "effectiveFrom": "2026-02-01"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    # Assert 2 rows exist in DB for this trainer.
    count_result = await db_session.execute(
        sa.text("SELECT COUNT(*) FROM trainer_comp_configs WHERE trainer_id = :tid"),
        {"tid": str(trainer.id)},
    )
    assert count_result.scalar() == 2, "Expected 2 config rows (INSERT-only versioned)"

    # GET should return the row with the latest effective_from <= today (bps=1000).
    r_get = await authed_client_owner.get(url, headers=headers)
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["data"]["commissionPctBps"] == 1000


async def test_owner_can_get_active_comp_config(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
) -> None:
    """Owner GET returns the active config row seeded via the factory (PAY-01 D-58-11)."""
    trainer = await make_trainer()
    seeded = await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=750,
        session_fee_kopecks=150000,
        effective_from=date(2026, 1, 1),
    )

    r = await authed_client_owner.get(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == str(seeded.id)
    assert data["trainerId"] == str(trainer.id)
    assert data["commissionPctBps"] == 750
    assert data["sessionFeeKopecks"] == 150000
    assert data["effectiveFrom"] == "2026-01-01"


async def test_get_returns_404_when_no_config(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """GET on a trainer with no config rows returns 404 comp_config_missing (PAY-01 D-58-11)."""
    trainer = await make_trainer()
    r = await authed_client_owner.get(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "comp_config_missing"


async def test_get_resolves_latest_effective_from(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
) -> None:
    """GET resolves to the row with the highest effective_from <= today (D-58-02 resolver).

    Seeds 3 config rows for one trainer with effective_from = 2026-01-01,
    2026-02-01, 2026-03-01. A GET on a date >= 2026-03-01 must return the
    2026-03-01 row (latest, not the middle or earliest).
    """
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=100,
        effective_from=date(2026, 1, 1),
    )
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=200,
        effective_from=date(2026, 2, 1),
    )
    latest = await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=300,
        effective_from=date(2026, 3, 1),
    )

    # The service resolves as-of MSK today (>= 2026-03-01 in the test env).
    r = await authed_client_owner.get(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == str(latest.id), f"Expected latest row (bps=300, {latest.id}), got {data}"
    assert data["commissionPctBps"] == 300


async def test_reception_forbidden_on_put(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
) -> None:
    """(CREATE, COMPENSATION) ∈ OWNER_ONLY → reception receives 403 (T-58-17)."""
    trainer = await make_trainer()
    r = await authed_client_reception.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json={"commissionPctBps": 1000, "effectiveFrom": "2026-01-01"},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_reception_forbidden_on_get(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
) -> None:
    """(VIEW, COMPENSATION) ∈ OWNER_ONLY → reception receives 403 (T-58-17)."""
    trainer = await make_trainer()
    r = await authed_client_reception.get(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_put_rejects_bps_over_10000(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """commission_pct_bps > 10000 → 422 from Pydantic Field(le=10000) (T-58-20 mitigation)."""
    trainer = await make_trainer()
    r = await authed_client_owner.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json={"commissionPctBps": 20000, "effectiveFrom": "2026-01-01"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_audit_emitted_on_put(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    db_session: AsyncSession,
) -> None:
    """PUT emits audit row event='trainer_comp_config_set' (D-58-17 atomic chain)."""
    trainer = await make_trainer()
    body = {
        "commissionPctBps": 500,
        "sessionFeeKopecks": 100000,
        "effectiveFrom": "2026-01-01",
    }
    r = await authed_client_owner.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json=body,
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    # Verify audit_log row exists with the expected event + payload.
    rows = (
        (
            await db_session.execute(
                sa.text(
                    "SELECT payload FROM audit_log "
                    "WHERE action = 'trainer_comp_config_set' "
                    "  AND resource_type = 'trainer_comp_config' "
                    "ORDER BY created_at DESC"
                ),
            )
        )
        .mappings()
        .all()
    )

    assert len(rows) >= 1, "Expected at least 1 audit_log row with event='trainer_comp_config_set'"
    payload = dict(rows[0]["payload"])
    assert str(payload["trainer_id"]) == str(trainer.id)
    assert payload["commission_pct_bps"] == 500
    assert payload["session_fee_kopecks"] == 100000
