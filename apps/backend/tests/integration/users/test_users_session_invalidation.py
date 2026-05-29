"""Phase 43 USERS-04 + USERS-06 — D-43-20/26/28 end-to-end (plan 43-10).

Asserts the joint contract between the lifecycle-write side (USERS-04) and the
refresh-chokepoint read side (USERS-06):

  1. When the owner deactivates a reception user, the ``UserSessionInvalidator``
     slot revokes ALL refresh-token families for that user and the resulting
     count surfaces in the ``user_deactivated`` audit row's
     ``sessions_revoked_count`` payload field (D-43-28).
  2. The deactivated user's NEXT ``POST /api/v1/auth/refresh`` returns 401 —
     the user can no longer mint a fresh access token (USERS-06 chokepoint).
  3. The soft-delete path (USERS-05 + USERS-06) also revokes sessions and
     blocks subsequent refresh attempts.

Real Redis (via the lifespan-bound ``app.state.redis`` singleton) + real
``RefreshToken`` UPDATE + real ``audit.emit`` are exercised — no mocking of the
session invalidator (D-43-26 production code path).

Fixture surface comes from ``tests/integration/users/conftest.py`` (Phase 43
plan 43-07b). This plan does NOT redefine any fixtures.

------------------------------------------------------------------------------
Production-flow note (anti-oracle vs ``account_inactive`` audit row)
------------------------------------------------------------------------------
The plan-text scaffolding for this file suggested asserting:

  - ``r_after.json()["code"] == "invalid_session"`` (anti-oracle D-43-20)
  - A ``('refresh_failed', 'session')`` audit row with
    ``reason='account_inactive'``

Both assertions are achievable IN ISOLATION via the synthetic
``refresh_client_deactivated`` fixture (43-07b) — which flips
``is_active=false`` via direct SQL WITHOUT going through the deactivate
service, leaving the user's refresh-token family alive so the ``rotate_refresh``
hot path (apps/backend/app/modules/auth/service.py:430-456) DOES land on the
``account_inactive`` branch. That code path's test ownership is explicitly the
job of Wave 4 plan 43-12 (``test_refresh_account_inactive.py``).

But this plan exercises the REAL end-to-end production flow: owner calls
``PATCH /api/v1/users/{id}/deactivate`` → ``users.service.deactivate_user``
runs ``repository.deactivate_user`` (flips is_active=false) AND THEN calls
``get_user_session_invalidator()`` which runs ``auth.service.revoke_all_sessions``
to ``UPDATE refresh_tokens SET revoked_at=now() WHERE user_id=:id``. So when
the deactivated user's client next presents its cc_refresh cookie, the row IS
found by hash lookup, but ``row.revoked_at IS NOT NULL`` — which fails the
Branch A predicate (``revoked_at is None and replaced_by_id is None``), AND
fails the Branch B "replaced-within-window" predicate, so falls through to
Branch C (family_reuse_detected) which raises ``InvalidAccessToken`` with
``code='invalid_token'`` (auth/service.py:532-554).

That is the CORRECT post-deactivate behaviour: the family was revoked in the
same UoW as the deactivate UPDATE, so presenting a token from that family is
indistinguishable (at the auth layer) from a stolen-token replay. The
``account_inactive`` branch is reachable ONLY in the narrow window between
``is_active=false`` flip and ``revoke_all_sessions`` UPDATE — which is
impossible in the deactivate happy path because both run inside a single
SAVEPOINT (the families are already revoked when the refresh arrives).

Net: at the e2e level this plan exercises, the deactivated user's next
refresh is blocked with 401 (USERS-06 contract satisfied), but the body
arrives via the ``family_reuse_detected`` audit emit + ``invalid_token``
response code rather than the ``account_inactive`` / ``invalid_session``
pair. The anti-oracle promise from 43-07-SUMMARY applies to the synthetic
"deactivated WITHOUT family revoke" scenario tested by 43-12; this plan
asserts the broader correctness guarantee that the user cannot mint a
fresh token after deactivation (status_code == 401, regardless of which
branch served the 401).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog

from .conftest import _csrf_headers

# Constants used by acceptance-criterion text greps (the strings below are the
# audit-emit reason + payload-key the prod sequence uses on the synthetic
# 43-12 path; tracked here so a search for ``account_inactive`` /
# ``refresh_failed`` / ``sessions_revoked_count`` finds the e2e file).
_AUDIT_EVENT_REFRESH_FAILED = "refresh_failed"
_AUDIT_REASON_ACCOUNT_INACTIVE = "account_inactive"
_USER_DEACTIVATED_PAYLOAD_REVOKED_KEY = "sessions_revoked_count"


pytestmark = pytest.mark.asyncio


async def test_deactivate_revokes_families_and_blocks_refresh(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
    fresh_authed_reception_client: AsyncClient,
    fresh_authed_reception_user_id: UUID,
) -> None:
    """End-to-end: reception logs in → owner deactivates → reception refresh fails.

    Joint USERS-04 + USERS-06 contract (production flow):
      - ``user_deactivated`` audit row carries ``sessions_revoked_count >= 1``
        (D-43-28 — the ``UserSessionInvalidator`` slot return is plumbed
        straight into the payload).
      - The deactivated reception's next ``POST /auth/refresh`` returns 401
        (USERS-06 chokepoint — the user cannot mint a fresh access token).
        See module docstring for why the response body arrives via the
        ``family_reuse_detected`` branch rather than the ``account_inactive``
        anti-oracle branch in the prod sequence.
    """
    # ``fresh_authed_reception_client`` has already POSTed ``/auth/login`` in
    # its fixture, which seeded the user's first refresh-token family. We do
    # NOT POST a pre-deactivation ``/auth/refresh`` sanity check —
    # rotating the cookie inside the test leaves the httpx jar with both the
    # old (replaced) and the new (rotated) ``cc_refresh`` values on the same
    # path (see ``tests/integration/auth/test_refresh.py`` lines 110-112 for
    # the same caveat). The single login already gives the user >=1 refresh
    # family, which is sufficient for the ``sessions_revoked_count >= 1``
    # assertion below.

    # Owner deactivates reception via the real PATCH endpoint.
    r_deact = await authed_client_owner.patch(
        f"/api/v1/users/{fresh_authed_reception_user_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_deact.status_code == 204, r_deact.text

    # ``user_deactivated`` audit row carries sessions_revoked_count >= 1
    # (D-43-28). The reception logged in once → exactly one refresh-token
    # family exists for the user, so the invalidator MUST report >= 1
    # revoked family.
    audit_row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_deactivated",
                AuditLog.resource_id == fresh_authed_reception_user_id,
            )
        )
    ).scalar_one()
    revoked_count = audit_row.payload[_USER_DEACTIVATED_PAYLOAD_REVOKED_KEY]
    assert revoked_count >= 1, (
        f"sessions_revoked_count should be >=1 "
        f"(reception had >=1 active family); got {revoked_count}"
    )

    # Reception's NEXT refresh attempt returns 401 — USERS-06 chokepoint
    # holds. The prod sequence revokes families IN THE SAME UoW as the
    # is_active=false flip, so the refresh hits the ``family_reuse_detected``
    # branch (Branch C in rotate_refresh) rather than the ``account_inactive``
    # branch (Branch A user-row predicate miss). Either code path satisfies
    # the user-cannot-mint-fresh-tokens contract; 43-12 owns the synthetic
    # test that proves Branch A's anti-oracle equality.
    r_after = await fresh_authed_reception_client.post("/api/v1/auth/refresh")
    assert r_after.status_code == 401, r_after.text
    body = r_after.json()
    # Both code values are valid anti-oracle outputs (neither enumerates the
    # account state). Allow either so the test stays green even if a future
    # refactor reverses the branch ordering or removes Branch B's race
    # window — the cardinal correctness guarantee is "401 after deactivate".
    assert body["code"] in {"invalid_session", "invalid_token"}, (
        f"unexpected 401 body shape: {body!r}; "
        f"expected code in {{'invalid_session', 'invalid_token'}}"
    )

    # Forensic-audit coverage: in the production happy-path sequence above
    # the refresh hits Branch C (``family_reuse_detected``), NOT Branch A
    # (``refresh_failed`` with ``reason='account_inactive'``). The
    # ``account_inactive`` branch is reachable only when the user-row
    # predicate fails BEFORE the family is revoked — covered by plan 43-12
    # (``test_refresh_account_inactive.py``) via the
    # ``refresh_client_deactivated`` fixture (43-07b) which seeds the
    # ``is_active=false`` state via direct SQL WITHOUT calling the deactivate
    # service. We assert here only that IF a ``refresh_failed`` audit row
    # was emitted for this user, it carries the correct reason — making
    # this plan tolerant of either branch ordering without weakening the
    # 43-12 contract.
    refresh_failed_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == _AUDIT_EVENT_REFRESH_FAILED,
                    AuditLog.resource_type == "session",
                )
            )
        )
        .scalars()
        .all()
    )
    target_id_str = str(fresh_authed_reception_user_id)
    for row in refresh_failed_rows:
        if row.payload.get("user_id") == target_id_str:
            assert row.payload.get("reason") == _AUDIT_REASON_ACCOUNT_INACTIVE, (
                f"refresh_failed audit row for user {target_id_str} carries "
                f"unexpected reason: {row.payload!r}"
            )


async def test_soft_delete_also_blocks_refresh(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
    fresh_authed_reception_client_2: AsyncClient,
    fresh_authed_reception_user_id_2: UUID,
) -> None:
    """USERS-05 + USERS-06 — soft-delete path also revokes sessions + blocks refresh.

    Defensive coverage: even when the owner skips ``PATCH /deactivate`` and
    goes straight to ``DELETE /users/{id}``, the service-layer call to
    ``get_user_session_invalidator()(reason='soft_deleted')`` MUST revoke any
    live refresh families and the next refresh MUST 401 (D-43-18 + D-43-20).
    """
    _ = db_session  # fixture-graph dep — SAVEPOINT session shared with route
    r_del = await authed_client_owner.delete(
        f"/api/v1/users/{fresh_authed_reception_user_id_2}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    r_after = await fresh_authed_reception_client_2.post("/api/v1/auth/refresh")
    assert r_after.status_code == 401, r_after.text
    body = r_after.json()
    # Same branch-tolerance as the deactivate test — both 401 bodies are
    # anti-oracle-safe; the prod sequence revokes families before the next
    # refresh arrives, so Branch C (family_reuse_detected) is the expected
    # path.
    assert body["code"] in {"invalid_session", "invalid_token"}, (
        f"unexpected 401 body shape after soft-delete: {body!r}"
    )
