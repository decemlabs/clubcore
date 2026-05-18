"""REG-29-04 — assert critical ORM tables are visible from worker import root.

Cron one-shots (``app/workers/scheduled/<job>.py``) read ``Base.metadata``
to verify that tables exist before issuing SELECTs. Without eager imports
in ``app/workers/__init__.py``, SQLAlchemy lazy-loading means the cron
sees an empty metadata view and the first query fails with a reflection
error.

The v1.3 expiring-notifications regression that birthed REG-29-04 was
exactly this: the cron job ran the SELECT inline before any service-layer
import had registered the `membership_notifications` table on
`Base.metadata`, and the worker crashed at 06:15 the morning after
deploy. The fix was to add eager imports for every ORM module in the
workers package's `__init__.py`; this test pins that discipline as code.

Phase 41 INFRA-38 / D-41-29 extends the gate to ``password_reset_tokens``
ahead of Phase 44's RESET-* endpoint landing.
"""

from __future__ import annotations


def test_password_reset_tokens_eager_imported() -> None:
    """Phase 41 INFRA-38 / D-41-29 — password_reset_tokens reachable from worker root.

    Importing ``app.workers`` must surface ``password_reset_tokens`` on
    ``Base.metadata.tables``; the eager-import line in
    ``app/workers/__init__.py`` is the contract.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    assert "password_reset_tokens" in Base.metadata.tables, sorted(
        Base.metadata.tables.keys()
    )


def test_v15_critical_tables_still_visible() -> None:
    """Smoke — stable v1.5 worker-touched tables remain visible from import root.

    Guards against accidental import-order regressions in
    ``app/workers/__init__.py``. The set below names tables that v1.5 cron
    jobs actively SELECT/UPDATE (expire_memberships, send_booking_reminders,
    mark_no_show_bookings, send_expiring_notifications) — if any of them
    regressed to lazy-load, the worker would crash at first tick.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    critical_v15 = {
        "memberships",
        "membership_notifications",
        "bookings",
        "booking_notifications",
    }
    visible = set(Base.metadata.tables.keys())
    missing = critical_v15 - visible
    assert not missing, f"v1.5 critical tables not eager-loaded: {sorted(missing)}"
