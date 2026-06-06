"""Integration tests for GET /api/v1/client/trainers/{trainer_id} (TRNR-01, Phase 88).

Covers:
  - Happy path: active trainer with bio/specialization/photo_url → 200 with client-safe fields.
  - Leak guard: response data must NOT contain phone/isActive/deletedAt/createdAt/updatedAt.
  - 404 unknown: random UUID → 404 trainer_not_found.
  - 404 inactive: trainer with is_active=False → 404 (anti-oracle).
  - 404 soft-deleted: trainer with deleted_at set → 404 (anti-oracle).

Anti-enumeration: unknown, inactive, and soft-deleted responses are indistinguishable.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.trainers.models import Trainer

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_trainer_authed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
    trainer_id: str,
) -> tuple[int, dict]:  # type: ignore[type-arg]
    """Auth as client and GET /api/v1/client/trainers/{trainer_id}; return (status, body)."""
    from tests.integration.client_portal.test_idor_sweep import _auth_as_client

    token = await _auth_as_client(async_client, db_session, client)
    resp = await async_client.get(
        f"/api/v1/client/trainers/{trainer_id}",
        headers={"Cookie": f"cc_client_access={token}"},
    )
    return resp.status_code, resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Happy path: active trainer detail
# ---------------------------------------------------------------------------


async def test_client_get_trainer_happy_path(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """TRNR-01: GET /client/trainers/{id} → 200 with id, fullName, photoUrl, specialization, bio."""
    trainer = Trainer(
        full_name="Аня Соколова",
        is_active=True,
        bio="Силовые и функциональный тренинг, 7 лет опыта.",
        specialization="Силовые, функционал",
        photo_url="https://cdn.example.com/anya.jpg",
    )
    db_session.add(trainer)
    await db_session.commit()

    status_code, body = await _get_trainer_authed(
        async_client, db_session, client_a, str(trainer.id)
    )

    assert status_code == 200, body
    data = body["data"]
    assert data["fullName"] == "Аня Соколова"
    assert data["specialization"] == "Силовые, функционал"
    assert data["bio"] == "Силовые и функциональный тренинг, 7 лет опыта."
    assert data["photoUrl"] == "https://cdn.example.com/anya.jpg"
    assert "id" in data


# ---------------------------------------------------------------------------
# Leak guard: owner-only and audit fields must NOT appear in response
# ---------------------------------------------------------------------------


async def test_client_get_trainer_leak_guard(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """T-88-01 leak guard: response must NOT contain phone/isActive/audit fields."""
    trainer = Trainer(
        full_name="Leak Guard Trainer",
        phone="+79991112233",
        is_active=True,
        bio="Bio text",
        specialization="Spec",
    )
    db_session.add(trainer)
    await db_session.commit()

    status_code, body = await _get_trainer_authed(
        async_client, db_session, client_a, str(trainer.id)
    )

    assert status_code == 200, body
    data = body["data"]

    # Client-safe fields must be present
    assert "id" in data
    assert "fullName" in data

    # Owner-only and audit fields must NOT appear (T-88-01 / D-69-05)
    forbidden_fields = [
        "phone",
        "isActive",
        "is_active",
        "deletedAt",
        "deleted_at",
        "createdAt",
        "created_at",
        "updatedAt",
        "updated_at",
        "rates",
    ]
    for field in forbidden_fields:
        assert field not in data, (
            f"ClientTrainerDetailResponse must NOT expose '{field}' (T-88-01 violation)"
        )


# ---------------------------------------------------------------------------
# 404 anti-enumeration cases
# ---------------------------------------------------------------------------


async def test_client_get_trainer_unknown_uuid_returns_404(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """T-88-02: unknown trainer UUID → 404; message identifies trainer_not_found."""
    unknown_id = uuid4()
    status_code, body = await _get_trainer_authed(
        async_client, db_session, client_a, str(unknown_id)
    )
    assert status_code == 404, body
    # NotFoundError raises with message="trainer_not_found"; code="not_found" at class level
    assert body["message"] == "trainer_not_found", body


async def test_client_get_trainer_inactive_returns_404(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """T-88-02: inactive trainer (is_active=False) → 404 (anti-enumeration).

    The 404 response must be indistinguishable from an unknown trainer.
    """
    trainer = Trainer(
        full_name="Inactive Trainer",
        is_active=False,
        bio="Should not be visible.",
    )
    db_session.add(trainer)
    await db_session.commit()

    status_code, body = await _get_trainer_authed(
        async_client, db_session, client_a, str(trainer.id)
    )
    assert status_code == 404, body
    assert body["message"] == "trainer_not_found", body


async def test_client_get_trainer_soft_deleted_returns_404(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """T-88-02: soft-deleted trainer (deleted_at IS NOT NULL) → 404 (anti-enumeration).

    The 404 response must be indistinguishable from an unknown trainer.
    """
    trainer = Trainer(
        full_name="Deleted Trainer",
        is_active=True,
        deleted_at=datetime.now(tz=UTC),
        bio="Should not be visible.",
    )
    db_session.add(trainer)
    await db_session.commit()

    status_code, body = await _get_trainer_authed(
        async_client, db_session, client_a, str(trainer.id)
    )
    assert status_code == 404, body
    assert body["message"] == "trainer_not_found", body


async def test_client_get_trainer_inactive_and_unknown_indistinguishable(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """T-88-02 anti-oracle: inactive and unknown return identical 404 shape (T-88-02)."""
    from tests.integration.client_portal.test_idor_sweep import _auth_as_client

    # Seed inactive trainer
    trainer = Trainer(full_name="Anti-Oracle Inactive", is_active=False)
    db_session.add(trainer)
    await db_session.commit()

    token = await _auth_as_client(async_client, db_session, client_a)
    headers = {"Cookie": f"cc_client_access={token}"}

    resp_inactive = await async_client.get(
        f"/api/v1/client/trainers/{trainer.id}", headers=headers
    )
    resp_unknown = await async_client.get(
        f"/api/v1/client/trainers/{uuid4()}", headers=headers
    )

    # Both must be 404 with identical code+message — indistinguishable (T-88-02)
    assert resp_inactive.status_code == 404
    assert resp_unknown.status_code == 404
    assert resp_inactive.json()["code"] == resp_unknown.json()["code"]
    assert resp_inactive.json()["message"] == resp_unknown.json()["message"]
    assert resp_inactive.json()["message"] == "trainer_not_found"
