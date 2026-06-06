"""Integration tests for owner PATCH bio/specialization/photo_url + reception 403 (Phase 88).

Covers:
  - Owner happy path: PATCH /trainers/{id} with bio/specialization/photo_url → 200, echoed fields.
  - Reception 403: PATCH /trainers/{id} with bio as reception → 403 (OWNER_ONLY: EDIT,TRAINERS).

Harness: authed_client_owner / authed_client_reception fixtures from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.trainers.conftest import _create, _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_owner_patch_bio_fields_returns_200_and_echoes(
    authed_client_owner: AsyncClient,
) -> None:
    """TRNR-02: owner PATCH {bio, specialization, photo_url} → 200; response echoes all three."""
    created = await _create(
        authed_client_owner, phone="+79998880101", full_name="Биографический Тренер"
    )

    bio_text = "Опытный тренер с 10 годами практики."  # noqa: RUF001
    patch_payload = {
        "bio": bio_text,
        "specialization": "Кроссфит, выносливость",
        "photoUrl": "https://cdn.example.com/trainer.jpg",
    }
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json=patch_payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["bio"] == bio_text, data
    assert data["specialization"] == "Кроссфит, выносливость", data
    assert data["photoUrl"] == "https://cdn.example.com/trainer.jpg", data


async def test_owner_patch_bio_only_returns_200_and_echoes(
    authed_client_owner: AsyncClient,
) -> None:
    """TRNR-02: owner PATCH with only bio (partial PATCH semantics, D-01) → 200; bio echoed."""
    created = await _create(
        authed_client_owner, phone="+79998880102", full_name="Только Био Тренер"
    )

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"bio": "Краткое описание тренера."},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["bio"] == "Краткое описание тренера.", data
    # Other profile fields remain None (no data set yet)
    assert data.get("specialization") is None, data
    assert data.get("photoUrl") is None, data


async def test_reception_patch_bio_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """T-88-07: (EDIT,TRAINERS) in OWNER_ONLY → reception PATCH bio → 403 forbidden."""
    created = await _create(authed_client_owner, phone="+79998880103", full_name="RBAC Тренер")

    r = await authed_client_reception.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"bio": "Попытка записи от ресепшена."},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden", r.json()


async def test_owner_patch_javascript_photo_url_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """CR-01: owner PATCH photo_url='javascript:alert(1)' → 422 (scheme rejected at API boundary)."""
    created = await _create(
        authed_client_owner, phone="+79998880104", full_name="XSS Test Тренер"
    )

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"photoUrl": "javascript:alert(1)"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_patch_https_photo_url_returns_200(
    authed_client_owner: AsyncClient,
) -> None:
    """CR-01: owner PATCH photo_url with valid https URL → 200, echoed in response."""
    created = await _create(
        authed_client_owner, phone="+79998880105", full_name="HTTPS URL Тренер"
    )

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"photoUrl": "https://cdn.example.com/a.jpg"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["photoUrl"] == "https://cdn.example.com/a.jpg", r.json()
