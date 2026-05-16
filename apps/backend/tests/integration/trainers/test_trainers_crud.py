"""Integration tests for /api/v1/trainers CRUD (TRN-01..05, D-31-06/D-31-07/D-31-09).

Each test owns its DB state via the SAVEPOINT-rolled `db_session` fixture
and exercises the full route -> service -> repository -> DB chain through
httpx ASGITransport.

Marquee tests:
  - test_create_duplicate_phone_after_soft_delete_succeeds — partial UNIQUE survives
  - test_create_duplicate_phone_returns_409_phone_exists — D-31-03
  - test_delete_returns_409_when_fk_violation — D-31-07 pre-emptive monkeypatch
  - test_patch_deactivate_returns_200_is_active_false — TRN-03
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.trainers.conftest import VALID_TRAINER, _create, _csrf_headers


async def test_create_happy_returns_201_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-02 happy path: POST returns 201 + ResponseEnvelope[TrainerResponse]."""
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json=VALID_TRAINER,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert data["fullName"] == "Иванов Иван"
    UUID(data["id"])
    assert data["isActive"] is True  # new trainers always active (D-31-02)


async def test_create_without_phone_returns_201(
    authed_client_owner: AsyncClient,
) -> None:
    """Phone is optional (D-31-02): POST without phone returns 201."""
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json={"fullName": "Петрова Анна"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["phone"] is None


async def test_create_invalid_phone_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """D-31-05: non-E.164 phone → 422 validation error."""
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json={"fullName": "Test", "phone": "12345"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_create_duplicate_phone_returns_409_phone_exists(
    authed_client_owner: AsyncClient,
) -> None:
    """D-31-03: second POST with same phone among alive rows → 409 phone_exists."""
    await _create(authed_client_owner, phone="+79991111111")
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json={"fullName": "Другой", "phone": "+79991111111"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "phone_exists"


async def test_create_duplicate_phone_after_soft_delete_succeeds(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Partial UNIQUE survives soft-delete: create with same phone after deleted_at is set."""
    from datetime import UTC, datetime

    from sqlalchemy import update as sa_update

    from app.modules.trainers.models import Trainer

    created = await _create(authed_client_owner, phone="+79992222222")
    trainer_id = UUID(created["id"])

    # Simulate soft-delete by setting deleted_at directly
    await db_session.execute(
        sa_update(Trainer)
        .where(Trainer.id == trainer_id)
        .values(deleted_at=datetime.now(tz=UTC))
    )
    await db_session.commit()

    # Same phone should succeed now (partial UNIQUE excludes rows with deleted_at IS NOT NULL)
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json={"fullName": "Новый тренер", "phone": "+79992222222"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    new_id = UUID(r.json()["data"]["id"])
    assert new_id != trainer_id


async def test_get_returns_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-02: GET by id returns envelope wrapping TrainerResponse."""
    created = await _create(authed_client_owner, phone="+79993333333")
    r = await authed_client_owner.get(f"/api/v1/trainers/{created['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert body["data"]["id"] == created["id"]
    assert body["data"]["fullName"] == "Тестовый Тренер"


async def test_get_missing_returns_404_trainer_not_found(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-02: GET random UUID → 404 with code trainer_not_found."""
    r = await authed_client_owner.get(
        "/api/v1/trainers/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "trainer_not_found"


async def test_list_default_returns_pagination_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-04: GET returns {data: {items, total, page, pageSize}} envelope."""
    r = await authed_client_owner.get("/api/v1/trainers")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data


async def test_list_active_true_filters(
    authed_client_owner: AsyncClient,
) -> None:
    """D-31-09: GET ?active=true returns only active trainers."""
    active = await _create(authed_client_owner, phone="+79994444441", full_name="Активный")
    inactive = await _create(authed_client_owner, phone="+79994444442", full_name="Неактивный")

    # Deactivate the second trainer
    await authed_client_owner.patch(
        f"/api/v1/trainers/{inactive['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get("/api/v1/trainers?active=true")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    ids = [item["id"] for item in items]
    assert active["id"] in ids
    assert inactive["id"] not in ids


async def test_list_active_false_filters(
    authed_client_owner: AsyncClient,
) -> None:
    """D-31-09: GET ?active=false returns only inactive trainers."""
    active = await _create(authed_client_owner, phone="+79994444443", full_name="Активный2")  # noqa: RUF001
    inactive = await _create(
        authed_client_owner, phone="+79994444444", full_name="Неактивный2"  # noqa: RUF001
    )

    # Deactivate the second trainer
    await authed_client_owner.patch(
        f"/api/v1/trainers/{inactive['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get("/api/v1/trainers?active=false")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    ids = [item["id"] for item in items]
    assert inactive["id"] in ids
    assert active["id"] not in ids


async def test_patch_deactivate_returns_200_is_active_false(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-03: PATCH {isActive: false} → 200 with isActive=false."""
    created = await _create(authed_client_owner, phone="+79995555551")
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["isActive"] is False


async def test_patch_reactivate_returns_200_is_active_true(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-03: deactivate then PATCH {isActive: true} → 200 with isActive=true."""
    created = await _create(authed_client_owner, phone="+79995555552")

    # Deactivate
    await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )

    # Reactivate
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": True},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["isActive"] is True


async def test_patch_full_name_returns_200_updated(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-03: PATCH {fullName: 'Новое Имя'} → 200 with new name."""
    created = await _create(authed_client_owner, phone="+79995555553")
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"fullName": "Новое Имя"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fullName"] == "Новое Имя"


async def test_patch_missing_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-03: PATCH random UUID → 404."""
    r = await authed_client_owner.patch(
        "/api/v1/trainers/00000000-0000-0000-0000-000000000001",
        json={"fullName": "X"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "trainer_not_found"


async def test_delete_happy_returns_204(
    authed_client_owner: AsyncClient,
) -> None:
    """TRN-05: DELETE → 204; subsequent GET → 404."""
    created = await _create(authed_client_owner, phone="+79996666661")
    r_del = await authed_client_owner.delete(
        f"/api/v1/trainers/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    r_get = await authed_client_owner.get(f"/api/v1/trainers/{created['id']}")
    assert r_get.status_code == 404


async def test_delete_returns_409_when_fk_violation(
    authed_client_owner: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-31-07: pre-emptive FK 409 mapping test — synthetic via monkeypatched IntegrityError.

    Phase 34 will add a real pt_sessions FK; this exercises the mapping logic now.
    Confirms that IntegrityError with pgcode='23503' maps to 409 trainer_in_use.
    """
    from typing import Any as AnyType

    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    class FakePGError:
        pgcode = "23503"

    async def _fake_delete(session: AnyType, trainer: AnyType) -> None:
        raise SAIntegrityError("mocked", {}, FakePGError())

    import app.modules.trainers.repository as repo

    monkeypatch.setattr(repo, "hard_delete_trainer", _fake_delete)

    created = await _create(authed_client_owner, phone="+79990009999")

    r = await authed_client_owner.delete(
        f"/api/v1/trainers/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "trainer_in_use"
