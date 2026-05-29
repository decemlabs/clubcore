"""Integration tests for /api/v1/clients CRUD (CLIENTS-02/05/06/07/08, D-09/10/11).

Each test owns its DB state via the SAVEPOINT-rolled `db_session` fixture
and exercises the full route -> service -> repository -> DB chain through
httpx ASGITransport.

Marquee tests:
  - test_delete_is_soft_delete_phone_reusable (CLIENTS-02 success criterion 3)
  - test_get_returns_404_for_soft_deleted (CLIENTS-05)
  - test_create_duplicate_phone_alive_returns_409_phone_exists (D-11)
  - test_patch_no_op_skips_audit_emit (D-09)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_create_happy_returns_201_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-06 happy path: POST returns 201 + ResponseEnvelope[ClientResponse]."""
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=VALID_CLIENT,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert data["lastName"] == "Иванов"
    assert data["firstName"] == "Иван"
    # id must parse as UUID
    UUID(data["id"])


async def test_create_invalid_phone_returns_422_invalid_phone(
    authed_client_owner: AsyncClient,
) -> None:
    """D-10: phone failing E.164 regex -> 422 from Pydantic validation.

    FRZ-06 / CR-WR-02: body-validation 422s return the curated
    ``{code, message, fields}`` envelope (NOT FastAPI's ``{detail:[...]}``),
    matching the frozen spec's shared ``422_ValidationError`` response.
    """
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "8-999-12-34"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["message"], str) and body["message"]
    assert "detail" not in body  # framework default shape must NOT leak
    assert "phone" in body["fields"]  # offending field surfaced under fields


async def test_create_duplicate_phone_alive_returns_409_phone_exists(
    authed_client_owner: AsyncClient,
) -> None:
    """D-11: second POST with same phone among alive rows -> 409 phone_exists."""
    await _create(authed_client_owner, phone="+79991111111")

    r = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79991111111"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "phone_exists"


async def test_get_returns_404_for_missing_id(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-05: GET on a non-existent UUID -> 404 client_not_found."""
    r = await authed_client_owner.get("/api/v1/clients/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "client_not_found"


async def test_get_returns_404_for_soft_deleted(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-05 + soft-delete invariant: GET on soft-deleted id -> 404."""
    created = await _create(authed_client_owner, phone="+79992222222")
    client_id = created["id"]

    r_del = await authed_client_owner.delete(
        f"/api/v1/clients/{client_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    r_get = await authed_client_owner.get(f"/api/v1/clients/{client_id}")
    assert r_get.status_code == 404
    assert r_get.json()["code"] == "client_not_found"


async def test_patch_partial_update_only_changed_fields(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-07: PATCH with only firstName changes only that field."""
    created = await _create(authed_client_owner, phone="+79993333333")
    client_id = created["id"]

    r_patch = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"firstName": "NewName"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200, r_patch.text

    r_get = await authed_client_owner.get(f"/api/v1/clients/{client_id}")
    body = r_get.json()["data"]
    assert body["firstName"] == "NewName"
    assert body["lastName"] == "Иванов"  # preserved
    assert body["phone"] == "+79993333333"  # preserved


async def test_patch_explicit_null_returns_422_invalid_field(
    authed_client_owner: AsyncClient,
) -> None:
    """D-01: explicit `{"email": null}` rejected at Pydantic boundary -> 422."""
    created = await _create(authed_client_owner, phone="+79994444444")
    client_id = created["id"]

    r = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"email": None},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_patch_no_op_skips_audit_emit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-09: PATCH that changes nothing must not emit `client_updated`.

    Send the same firstName the row already has. The service short-circuits
    before audit.emit when `repository.update_client` returns an empty
    changed dict.
    """
    created = await _create(authed_client_owner, phone="+79995555555")
    client_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"firstName": VALID_CLIENT["firstName"]},  # same as current
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "client_updated",
                AuditLog.resource_id == client_id,
            )
        )
    ).all()
    assert len(rows) == 0, "no-op PATCH must NOT emit client_updated (D-09)"


async def test_delete_is_soft_delete_phone_reusable(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """CLIENTS-02 marquee test: phone is reusable after soft-delete.

    1. POST a client with phone +79991234567.
    2. DELETE it (soft).
    3. POST another client with the SAME phone -> 201 with a new id.
    4. The deleted row is still in DB with deleted_at IS NOT NULL.
    """
    first = await _create(authed_client_owner, phone="+79991234567")
    first_id = UUID(first["id"])

    r_del = await authed_client_owner.delete(
        f"/api/v1/clients/{first_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    second = await _create(authed_client_owner, phone="+79991234567")
    second_id = UUID(second["id"])
    assert second_id != first_id, "new client must have a different id"

    # Direct DB assertion: deleted row remains with deleted_at set.
    deleted_row = await db_session.scalar(select(Client).where(Client.id == first_id))
    assert deleted_row is not None
    assert deleted_row.deleted_at is not None


async def test_delete_returns_204_no_body(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-08: DELETE returns 204 No Content with empty body."""
    created = await _create(authed_client_owner, phone="+79996666666")
    r = await authed_client_owner.delete(
        f"/api/v1/clients/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text
    assert r.content == b""
