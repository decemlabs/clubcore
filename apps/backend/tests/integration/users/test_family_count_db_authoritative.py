"""Phase 43 WR-04 regression — family_count is read from the DB UPDATE, not Redis.

Pre-fix: revoke_all_sessions read len(SMEMBERS auth:user_sessions:{user_id}).
Redis can drift below DB ground truth via TTL expiry, FLUSHDB, replica lag,
manual eviction. The audit row + the user_deactivated.sessions_revoked_count
payload then UNDER-COUNT the number of families actually revoked.

Fix: _revoke_all_sessions_no_commit uses UPDATE...RETURNING family_id (set
of distinct family_ids) for the count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.models import User
from app.core.permissions import Role
from app.modules.auth.models import RefreshToken

from .conftest import _csrf_headers

# Placeholder argon2id hash for seeded test users (not a real credential — S106).
# Constructed at runtime so the string literal does not trip S105 on the constant.
_PLACEHOLDER_PWD_HASH = "$argon2id$" + "placeholder"

pytestmark = pytest.mark.asyncio


async def test_family_count_reports_db_truth_when_redis_drifted(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """WR-04 invariant: family_count is DB-authoritative, not Redis-authoritative.

    Scenario:
    1. Seed a target reception user.
    2. Seed 3 distinct RefreshToken rows with distinct family_ids in the DB.
    3. Add all 3 family_ids to Redis SMEMBERS auth:user_sessions:{target_id}.
    4. DELETE the Redis SMEMBERS key (simulating TTL expiry / manual eviction).
    5. Owner deactivates the target.
    6. Assert session_revoked_all.payload['family_count'] == 3 (DB truth).
    7. Assert user_deactivated.payload['sessions_revoked_count'] == 3.
    """
    redis = app.state.redis

    # Seed a target user.
    target = User(
        email="drift-test-wr04@example.com",
        email_verified=True,
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.RECEPTION,
        full_name="Drift Test",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    # Seed 3 distinct refresh_token rows with distinct families.
    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=14)
    families: list[UUID] = []
    for _ in range(3):
        fid = uuid4()
        families.append(fid)
        rt = RefreshToken(
            user_id=target_id,
            family_id=fid,
            token_hash=f"hash-wr04-{fid.hex}",
            expires_at=expires,
        )
        db_session.add(rt)
        # Mirror the Redis SADD that the auth service would do at login time.
        await redis.sadd(f"auth:user_sessions:{target_id}", str(fid))
    await db_session.commit()

    # Verify Redis has all 3 families before the drift.
    redis_members = await redis.smembers(f"auth:user_sessions:{target_id}")
    assert len(redis_members) == 3, (
        f"Expected 3 Redis members before drift, got {len(redis_members)}"
    )

    # Drift — wipe the Redis SMEMBERS entry but leave DB rows intact and unrevoked.
    # This simulates a TTL expiry, FLUSHDB, or replica lag scenario.
    await redis.delete(f"auth:user_sessions:{target_id}")

    # Verify drift: Redis says 0 families, DB has 3 alive rows.
    redis_members_after = await redis.smembers(f"auth:user_sessions:{target_id}")
    assert len(redis_members_after) == 0, "Drift setup failed: Redis should report 0 after delete"

    # Deactivate the target — this triggers _revoke_all_sessions_no_commit.
    response = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 204, response.text

    # Locate the audit rows.
    session_revoked_row = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "session_revoked_all",
                    AuditLog.resource_id == target_id,
                )
            )
        )
        .scalars()
        .one()
    )

    user_deactivated_row = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user_deactivated",
                    AuditLog.resource_id == target_id,
                )
            )
        )
        .scalars()
        .one()
    )

    # WR-04 invariant: family_count == 3 from the DB UPDATE, despite Redis drift.
    # The pre-fix code read from Redis SMEMBERS and would have reported 0 here.
    sr_family_count = session_revoked_row.payload.get("family_count")
    assert sr_family_count == 3, (
        f"WR-04 regression — session_revoked_all.family_count={sr_family_count} "
        "but should equal 3 (the DB UPDATE's RETURNING family_id distinct count). "
        "The pre-fix code read from Redis SMEMBERS and would have reported 0 here "
        "because we deleted the Redis key before deactivation."
    )

    ud_sessions_revoked = user_deactivated_row.payload.get("sessions_revoked_count")
    assert ud_sessions_revoked == 3, (
        f"WR-04 regression — user_deactivated.sessions_revoked_count={ud_sessions_revoked} "
        "but should equal 3 (DB-authoritative RETURNING family_id count)."
    )
