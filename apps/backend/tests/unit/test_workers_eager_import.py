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

Phase 45 D-45-20 extends the gate to ``payment_receipts`` (NOTIFY-14) and
adds an AST-level assertion of the literal import statement in
``app/workers/__init__.py`` — necessary because the root ``tests/conftest.py``
imports ``app.main.create_app`` which transitively pulls the payments
router/models, so a runtime-only ``in Base.metadata.tables`` check
silently passes under pytest even if the eager-import line is removed.
The production cron worker (``arq app.workers.WorkerSettings``) does NOT
load ``app.main``, so the AST scan is the load-bearing gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

_WORKERS_INIT_PATH = Path(__file__).resolve().parents[2] / "app" / "workers" / "__init__.py"


def _eager_imported_symbols() -> set[str]:
    """Return the set of fully-qualified symbols imported from app/workers/__init__.py.

    Walks the module AST and collects every `from <module> import <name>` pair
    as the string `<module>.<name>`. Used by the per-symbol assertions below
    to prove the eager-import line is structurally present in source, not
    merely transitively loaded by some other code path (which is what hides
    REG-29-04 regressions under pytest's conftest-driven import graph).
    """
    tree = ast.parse(_WORKERS_INIT_PATH.read_text(encoding="utf-8"))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                symbols.add(f"{node.module}.{alias.name}")
    return symbols


def test_password_reset_tokens_eager_imported() -> None:
    """Phase 41 INFRA-38 / D-41-29 — password_reset_tokens reachable from worker root.

    Importing ``app.workers`` must surface ``password_reset_tokens`` on
    ``Base.metadata.tables``; the eager-import line in
    ``app/workers/__init__.py`` is the contract.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    assert "password_reset_tokens" in Base.metadata.tables, sorted(Base.metadata.tables.keys())


def test_payment_receipts_eager_imported() -> None:
    """Phase 45 D-45-20 — ``payment_receipts`` reachable from worker root (REG-29-04).

    Importing ``app.workers`` MUST surface ``payment_receipts`` on
    ``Base.metadata.tables``; the eager-import line for
    ``app.modules.payments.models.PaymentReceipt`` in
    ``app/workers/__init__.py`` (plan 45-03) is the contract. Without it,
    the Phase 45 email-mirror cron one-shots (NOTIFY-14) would crash at
    the first INSERT into the idempotency ledger.

    Mirrors Phase 42 (EmailSendLog) + Phase 44 (PasswordResetToken)
    discipline.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    assert "payment_receipts" in Base.metadata.tables, sorted(Base.metadata.tables.keys())


def test_payment_receipts_import_statement_present() -> None:
    """Phase 45 D-45-20 — AST gate for ``PaymentReceipt`` eager-import line.

    The runtime ``Base.metadata.tables`` check above is necessary-but-not-
    sufficient: the root ``tests/conftest.py`` imports
    ``app.main.create_app`` which transitively pulls the payments router
    and registers ``payment_receipts`` on ``Base.metadata`` regardless of
    whether the eager-import line in ``app/workers/__init__.py`` exists.
    The production cron worker (``arq app.workers.WorkerSettings``) does
    NOT load ``app.main`` — so the literal ``from app.modules.payments.models
    import PaymentReceipt`` statement is the actual contract. This test
    asserts the statement is structurally present in source.
    """
    symbols = _eager_imported_symbols()
    assert "app.modules.payments.models.PaymentReceipt" in symbols, (
        "Missing eager-import of PaymentReceipt in app/workers/__init__.py — "
        "cron one-shots will not see payment_receipts in Base.metadata "
        "(REG-29-04). Imported symbols: " + repr(sorted(symbols))
    )


def test_eager_import_statements_mirror_discipline() -> None:
    """Phase 45 D-45-20 — AST gate for the Phase 42 + Phase 44 + Phase 45 trio.

    Pins the discipline as code so future regressions on ANY of these three
    eager-import lines fail loud at unit-test time rather than at 06:05 the
    morning after deploy. New ORM tables that cron jobs touch must extend
    this set (and the per-table runtime test above).
    """
    symbols = _eager_imported_symbols()
    required = {
        "app.integrations.email.models.EmailSendLog",  # Phase 42 D-42-33
        "app.modules.auth.password_reset_token_model.PasswordResetToken",  # Phase 41 D-41-29
        "app.modules.payments.models.PaymentReceipt",  # Phase 45 D-45-20
    }
    missing = required - symbols
    assert not missing, (
        "app/workers/__init__.py is missing eager-import statements for: "
        f"{sorted(missing)} (REG-29-04). All imported: {sorted(symbols)}"
    )


def test_email_send_log_eager_imported() -> None:
    """Phase 42 D-42-33 — ``email_send_log`` reachable from worker root (REG-29-04).

    Importing ``app.workers`` MUST surface ``email_send_log`` on
    ``Base.metadata.tables``; the eager-import line for
    ``app.integrations.email.models.EmailSendLog`` in
    ``app/workers/__init__.py`` (plan 42-09) is the contract. Without it,
    the ARQ ``dispatch_email`` task's bounce/complaint webhook joins would
    crash at the first append.
    """
    import app.workers  # noqa: F401 — trigger eager-import side effect
    from app.core.database import Base

    assert "email_send_log" in Base.metadata.tables, sorted(Base.metadata.tables.keys())


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
