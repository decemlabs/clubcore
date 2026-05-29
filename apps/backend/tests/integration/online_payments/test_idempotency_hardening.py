"""Phase 66 Plan 66-05 — IDM-03 integration tests for online_payments sell endpoints.

Asserts the hardened idempotency behavior (real Postgres + real Redis) for the
four category-A online sell endpoints:
  - POST /api/v1/online-payments/memberships/{plan_id}/sell         (sell_membership_redirect)
  - POST /api/v1/online-payments/memberships/{plan_id}/sell-qr      (sell_membership_qr)
  - POST /api/v1/online-payments/pt-packages/{plan_id}/sell         (sell_pt_package_redirect)
  - POST /api/v1/online-payments/pt-packages/{plan_id}/sell-qr      (sell_pt_package_qr)

Assertions per endpoint:
  1. Replay (same key + same body) returns byte-identical content.
  2. Replay does NOT re-emit AuditLog rows for the created OnlinePayment.
  3. Same key + different body → 422 idempotency_key_reuse.

ЮKassa HTTP calls are mocked via respx (fixtures from conftest and
integrations/yookassa/conftest re-exported by online_payments/conftest).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_csrf") or ""


def _headers(client: AsyncClient, *, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": _csrf_header(client),
        "Idempotency-Key": key,
    }


async def _audit_count_for_payment(session: AsyncSession, online_payment_id: UUID) -> int:
    """Count AuditLog rows where resource_id == online_payment_id."""
    result = await session.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.resource_id == online_payment_id)
    )
    return int(result.scalar_one())


# ===========================================================================
# sell_membership_redirect — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_sell_membership_redirect_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """Replay of sell_membership_redirect returns byte-identical cached response."""
    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex  # 32 chars, passes {16,128}

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_sell_membership_redirect_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """Replay of sell_membership_redirect does NOT re-emit AuditLog rows."""
    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    payment_id = UUID(r1.json()["data"]["onlinePaymentId"])

    count_before = await _audit_count_for_payment(db_session, payment_id)
    assert count_before >= 1, "At least one audit row expected after first submit"

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count_for_payment(db_session, payment_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_sell_membership_redirect_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """Same key + different body (different client) → 422 idempotency_key_reuse."""
    client_a = await make_client_with_email()
    client_b = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_a.id)},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_b.id)},  # different body
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# sell_membership_qr — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_sell_membership_qr_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Replay of sell_membership_qr returns byte-identical cached response."""
    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_sell_membership_qr_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Replay of sell_membership_qr does NOT re-emit AuditLog rows."""
    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    payment_id = UUID(r1.json()["data"]["onlinePaymentId"])

    count_before = await _audit_count_for_payment(db_session, payment_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count_for_payment(db_session, payment_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_sell_membership_qr_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Same key + different body → 422 idempotency_key_reuse."""
    client_a = await make_client_with_email()
    client_b = await make_client_with_email()
    plan = await make_membership_plan()
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json={"clientId": str(client_a.id)},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json={"clientId": str(client_b.id)},
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# sell_pt_package_redirect — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_sell_pt_package_redirect_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_success,
) -> None:
    """Replay of sell_pt_package_redirect returns byte-identical cached response."""
    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_sell_pt_package_redirect_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_success,
) -> None:
    """Replay of sell_pt_package_redirect does NOT re-emit AuditLog rows."""
    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    payment_id = UUID(r1.json()["data"]["onlinePaymentId"])

    count_before = await _audit_count_for_payment(db_session, payment_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count_for_payment(db_session, payment_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_sell_pt_package_redirect_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_success,
) -> None:
    """Same key + different body → 422 idempotency_key_reuse."""
    client_a = await make_client_with_email()
    client_b = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json={"clientId": str(client_a.id)},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json={"clientId": str(client_b.id)},
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# sell_pt_package_qr — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_sell_pt_package_qr_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Replay of sell_pt_package_qr returns byte-identical cached response."""
    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_sell_pt_package_qr_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Replay of sell_pt_package_qr does NOT re-emit AuditLog rows."""
    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    body_json = {"clientId": str(client_row.id)}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    payment_id = UUID(r1.json()["data"]["onlinePaymentId"])

    count_before = await _audit_count_for_payment(db_session, payment_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count_for_payment(db_session, payment_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_sell_pt_package_qr_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """Same key + different body → 422 idempotency_key_reuse."""
    client_a = await make_client_with_email()
    client_b = await make_client_with_email()
    plan = await make_pt_package_plan()
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json={"clientId": str(client_a.id)},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json={"clientId": str(client_b.id)},
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"
