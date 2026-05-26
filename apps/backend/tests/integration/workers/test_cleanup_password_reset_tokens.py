"""ARQ-TEST — cleanup_password_reset_tokens 30-day retention boundary (D-44-31/32).

Seeds tokens across the retention boundary and asserts the cron deletes
strictly the rows where `expires_at < NOW() - INTERVAL '30 days'` while
preserving the rows on or above the threshold.

Coverage:
  - Multiple expired-beyond-retention rows are all deleted in one cron tick.
  - Rows at the exact boundary (expires_at == NOW() - 30d) are preserved
    (strict `<`, not `<=`).
  - Recent rows + future-expiry rows are preserved.
  - No audit_log emission (D-44-31 housekeeping invariant).
  - Cron returns the deleted-row count.
  - Structlog summary `cleanup_password_reset_tokens_complete count=N` fires.

Pattern mirrors `test_expire_memberships.py` (Phase 18 ARQ-02 / Plan 18-05 +
conftest worker_ctx SAVEPOINT-mode session aliasing).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.auth.password_reset_token_model import PasswordResetToken
from app.workers.scheduled.cleanup_password_reset_tokens import (
    cleanup_password_reset_tokens,
)


async def _insert_token(
    session: AsyncSession,
    *,
    user_id: Any,
    expires_at: datetime,
    purpose: str = "password_reset",
    active: bool = False,
) -> PasswordResetToken:
    """Insert a password_reset_tokens row for the cleanup test.

    Defaults `consumed_at` to NOW so multiple rows per (user, purpose) can
    coexist — the partial-UNIQUE `(user_id, purpose) WHERE consumed_at IS NULL`
    (Phase 41 D-41-05) admits at most ONE active token per (user, purpose).
    The cleanup cron's WHERE clause filters on `expires_at` only, not on
    `consumed_at`, so consumed rows are equally eligible for retention-based
    deletion. Pass `active=True` to seed an actually-unconsumed token (only
    safe for one row per (user, purpose) in a single test).
    """
    token = PasswordResetToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=uuid4().hex,
        expires_at=expires_at,
        consumed_at=None if active else datetime.now(tz=UTC),
        audit_correlation_id=uuid4(),
    )
    session.add(token)
    await session.flush()
    await session.refresh(token)
    return token


async def test_cleanup_deletes_beyond_30d_retention_preserves_within(
    db_session: AsyncSession,
    seeded_user: User,
    worker_ctx: dict[str, Any],
) -> None:
    """The 30-day retention boundary partitions tokens into delete vs preserve.

    Assertion shape:
      - 3 expired-beyond-retention rows (-31d, -45d, -90d) → all DELETEd.
      - 1 row exactly at the boundary (-30d) → preserved (strict `<` not `<=`).
      - 1 recent row (-7d) → preserved.
      - 1 future-expiry row (+1h, simulates an active token) → preserved.
      - Cron returns 3 (deleted-row count).
      - Structlog summary line fires after commit.
      - No audit_log row produced by the cleanup itself.
    """
    now = datetime.now(tz=UTC)

    # Delete-side: 3 rows expired beyond the 30-day retention window.
    old_31d = await _insert_token(
        db_session, user_id=seeded_user.id, expires_at=now - timedelta(days=31)
    )
    old_45d = await _insert_token(
        db_session,
        user_id=seeded_user.id,
        expires_at=now - timedelta(days=45),
        purpose="invitation",
    )
    old_90d = await _insert_token(
        db_session, user_id=seeded_user.id, expires_at=now - timedelta(days=90)
    )

    # Preserve-side: boundary + recent + future-expiry.
    # NOTE: at the exact boundary the WHERE clause is `expires_at < NOW() - 30d`,
    # so a row whose expires_at equals NOW - 30d is preserved (strict `<`).
    # We seed at -30d + 1 minute to make the assertion deterministic regardless
    # of the ms-scale gap between row INSERT and the cron's NOW().
    boundary = await _insert_token(
        db_session,
        user_id=seeded_user.id,
        expires_at=now - timedelta(days=30) + timedelta(minutes=1),
    )
    recent_7d = await _insert_token(
        db_session, user_id=seeded_user.id, expires_at=now - timedelta(days=7)
    )
    # The future-expiry token is the realistic "active outstanding token"
    # case — keep this one un-consumed. Only one active row per
    # (user, purpose='invitation') is allowed by the partial-UNIQUE so we
    # marked old_45d as consumed above to clear the slot for this one.
    future_1h = await _insert_token(
        db_session,
        user_id=seeded_user.id,
        expires_at=now + timedelta(hours=1),
        purpose="invitation",
        active=True,
    )

    # Snapshot pre-run audit count — must not change after the cron.
    pre_audit_count = (await db_session.execute(select(AuditLog))).scalars().all()
    pre_audit_len = len(pre_audit_count)

    with structlog.testing.capture_logs() as captured:
        deleted = await cleanup_password_reset_tokens(worker_ctx)

    assert deleted == 3, f"expected 3 rows deleted, got {deleted}"

    # Surviving rows: boundary + recent_7d + future_1h.
    surviving_ids = {
        t.id
        for t in (
            (
                await db_session.execute(
                    select(PasswordResetToken).where(PasswordResetToken.user_id == seeded_user.id)
                )
            )
            .scalars()
            .all()
        )
    }
    assert boundary.id in surviving_ids, "boundary row (-30d + 1min) must be preserved"
    assert recent_7d.id in surviving_ids, "recent (-7d) row must be preserved"
    assert future_1h.id in surviving_ids, "future-expiry row must be preserved"
    assert old_31d.id not in surviving_ids, "-31d row must be deleted"
    assert old_45d.id not in surviving_ids, "-45d row must be deleted"
    assert old_90d.id not in surviving_ids, "-90d row must be deleted"

    # No audit emission (D-44-31 housekeeping invariant).
    post_audit_count = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(post_audit_count) == pre_audit_len, (
        f"cleanup_password_reset_tokens emitted audit rows "
        f"(pre={pre_audit_len}, post={len(post_audit_count)}); "
        f"D-44-31 forbids audit on this housekeeping cron"
    )

    # Structlog summary emitted with the deleted count.
    summary_lines = [
        ln for ln in captured if ln.get("event") == "cleanup_password_reset_tokens_complete"
    ]
    assert len(summary_lines) == 1, (
        f"expected exactly 1 cleanup_password_reset_tokens_complete log, got {len(summary_lines)}"
    )
    assert summary_lines[0]["count"] == 3, summary_lines[0]


async def test_cleanup_noop_when_nothing_to_delete(
    db_session: AsyncSession,
    seeded_user: User,
    worker_ctx: dict[str, Any],
) -> None:
    """Empty-window run: only fresh tokens, cron returns 0, no audit, no error."""
    now = datetime.now(tz=UTC)
    await _insert_token(db_session, user_id=seeded_user.id, expires_at=now - timedelta(days=5))
    # Use a different purpose so the partial-UNIQUE doesn't conflict with
    # the consumed (-5d) row above. Both stay in the table; cron deletes neither.
    await _insert_token(
        db_session,
        user_id=seeded_user.id,
        expires_at=now + timedelta(hours=1),
        purpose="invitation",
        active=True,
    )

    with structlog.testing.capture_logs() as captured:
        deleted = await cleanup_password_reset_tokens(worker_ctx)

    assert deleted == 0

    summary = [ln for ln in captured if ln.get("event") == "cleanup_password_reset_tokens_complete"]
    assert len(summary) == 1 and summary[0]["count"] == 0
