"""Phase 43 USERS-06 — D-43-20 anti-oracle for /auth/refresh.

Mirrors Phase 41 ``test_password_reset_no_oracle.py`` 4-case discipline.

Contract:
  - For all 3 failure cases (deactivated user / soft-deleted user / refresh-token
    not found) the response MUST be byte-for-byte identical: status 401 +
    identical body shape (no oracle leak of WHICH condition failed).
  - Timing variance across the 3 failure cases MUST be within 100ms tolerance.
  - The active-valid baseline returns 200 with a new cookie pair (sanity).

The forensic audit row for the deactivated-user case is asserted at the
``audit_log.action == 'refresh_failed'`` / ``resource_type == 'session'`` /
``payload.reason == 'account_inactive'`` boundary (Phase 43 D-43-20 — forensic
attribution lives in the audit layer; the HTTP response shape stays uniform).

Fixtures imported from ``tests/integration/users/conftest.py`` (plan 43-07b):
  - ``refresh_client_active`` — active user, fresh refresh cookie.
  - ``refresh_client_deactivated`` — user flipped ``is_active=False`` AFTER
    cookie issuance.
  - ``refresh_client_soft_deleted`` — user soft-deleted (``deleted_at IS NOT
    NULL``) AFTER cookie issuance.
  - ``refresh_client_unknown_token`` — bare client with a syntactically valid
    but never-issued refresh cookie.
  - ``deactivated_user_id`` — UUID of a deactivated user (audit-row consumer).
"""

from __future__ import annotations

import time
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog

pytestmark = pytest.mark.asyncio


async def test_refresh_anti_oracle_four_cases(
    db_session: AsyncSession,
    refresh_client_active: AsyncClient,
    refresh_client_deactivated: AsyncClient,
    refresh_client_soft_deleted: AsyncClient,
    refresh_client_unknown_token: AsyncClient,
    deactivated_user_id: UUID,
) -> None:
    """4-case parity sweep: active=200 baseline; 3 failure cases identical."""
    # Baseline — active user refresh works (200).
    r_active = await refresh_client_active.post("/api/v1/auth/refresh")
    assert r_active.status_code == 200, r_active.text

    # 3 failure cases — measure timing + capture body.
    t0 = time.perf_counter()
    r_deact = await refresh_client_deactivated.post("/api/v1/auth/refresh")
    t_deact = time.perf_counter() - t0

    t1 = time.perf_counter()
    r_soft = await refresh_client_soft_deleted.post("/api/v1/auth/refresh")
    t_soft = time.perf_counter() - t1

    t2 = time.perf_counter()
    r_unknown = await refresh_client_unknown_token.post("/api/v1/auth/refresh")
    t_unknown = time.perf_counter() - t2

    # Status code parity.
    assert r_deact.status_code == r_soft.status_code == r_unknown.status_code == 401, (
        f"status parity broken: deact={r_deact.status_code} "
        f"soft={r_soft.status_code} unknown={r_unknown.status_code}"
    )

    # Body parity — byte-for-byte JSON equality.
    assert r_deact.json() == r_soft.json() == r_unknown.json(), (
        f"body parity broken:\n"
        f"  deact   = {r_deact.json()}\n"
        f"  soft    = {r_soft.json()}\n"
        f"  unknown = {r_unknown.json()}"
    )

    # Timing parity — within 100ms tolerance across the 3 failure cases.
    timings = (t_deact, t_soft, t_unknown)
    spread = max(timings) - min(timings)
    assert spread < 0.100, (
        f"timing oracle: spread={spread:.3f}s across deact={t_deact:.3f}, "
        f"soft={t_soft:.3f}, unknown={t_unknown:.3f}"
    )

    # Forensic audit row for the deactivated case (D-43-20).
    # ``audit.emit`` maps the ``event`` kwarg to ``AuditLog.action`` — the
    # column is ``action`` (see app/core/audit.py:403-404). The fixture
    # ``deactivated_user_id`` resolves to the row that was deactivated BEFORE
    # any login could occur — the audit row comes from the fixture
    # ``refresh_client_deactivated`` which seeds a SEPARATE row, logs in, then
    # flips it. We assert there's at least one refresh_failed/account_inactive
    # audit row in the SAVEPOINT-rolled session — its ``user_id`` payload value
    # is the deactivated-after-login row's id, NOT necessarily
    # ``deactivated_user_id`` (those are two distinct rows by design — see
    # conftest.py:556-598 docstring).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "refresh_failed",
                    AuditLog.resource_type == "session",
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(r.payload.get("reason") == "account_inactive" for r in audit_rows), (
        f"missing refresh_failed/account_inactive audit row; "
        f"rows: {[r.payload for r in audit_rows]}; "
        f"deactivated_user_id (forensic ref only)={deactivated_user_id}"
    )
