"""Cron-resolution invariant extension for expire_pt_packages (Phase 33 D-33-13).

Mirrors the existing tests in tests/unit/workers/test_worker_settings.py for
expire_memberships, but lives at tests/unit/ root per Phase 33 CONTEXT.md
file-path lock (D-33-13 line 221).

Tests cover Pitfall 4 step 6 explicitly for the new cron entry:
  1. expire_pt_packages cron entry resolves to the SAME function object as
     WorkerSettings.functions[..] (identity check, not string match — survives
     ARQ version bumps that re-prefix CronJob.name with 'cron:').
  2. expire_pt_packages appears in WorkerSettings.functions (identity check).
  3. No unresolved cron entries (cron_function_names ⊆ function_names).
  4. expire_pt_packages cron entry has hour=3, minute=25, unique=True,
     keep_result_s=60 (06:25 Europe/Moscow given container TZ=UTC).
"""

from __future__ import annotations

from app.workers import WorkerSettings
from app.workers.scheduled.expire_pt_packages import expire_pt_packages


def test_expire_pt_packages_cron_entry_resolves_to_registered_function() -> None:
    """ARQ-03 / D-33-13: cron entry's coroutine IS the imported function.

    Identity check (not __name__ string match) so the test mirrors the
    on_startup invariant exactly and survives ARQ version bumps that change
    the CronJob.name prefix scheme.
    """
    matching = [
        c for c in WorkerSettings.cron_jobs if c.coroutine is expire_pt_packages
    ]
    assert len(matching) == 1, (
        "Exactly one cron entry must reference the expire_pt_packages function. "
        f"Found {len(matching)} matching entries — registration drift in "
        f"WorkerSettings.cron_jobs ({len(WorkerSettings.cron_jobs)} total)."
    )


def test_expire_pt_packages_in_functions() -> None:
    """ARQ-03: expire_pt_packages registered in WorkerSettings.functions.

    Identity check (mirrors test_worker_settings_functions_registered pattern
    for expire_memberships at tests/unit/workers/test_worker_settings.py).
    """
    assert expire_pt_packages in WorkerSettings.functions, (
        "expire_pt_packages must be in WorkerSettings.functions or the "
        "on_startup cron-resolution assertion will fail at worker boot "
        "(Pitfall 4 step 6 — silent no-op trap at 06:25 every morning)."
    )


def test_no_unresolved_cron_entries() -> None:
    """Pitfall 4 step 6 invariant — every cron_jobs entry resolves into functions.

    Direct mirror of the on_startup runtime assertion in workers/__init__.py:118.
    Catches typo at the registration site at test time, NOT at 06:25 the next
    morning.
    """
    function_names = {f.__name__ for f in WorkerSettings.functions}
    cron_function_names = {c.coroutine.__name__ for c in WorkerSettings.cron_jobs}
    unresolved = cron_function_names - function_names
    assert not unresolved, (
        f"cron_jobs reference function names not in WorkerSettings.functions: "
        f"{sorted(unresolved)}. Add the missing callables to `functions` or "
        f"fix the cron registration."
    )


def test_expire_pt_packages_cron_schedule_locked() -> None:
    """D-33-13: hour=3, minute=25, unique=True, keep_result=60 (06:25 MSK).

    Container TZ=UTC (Phase 18 D-09) means hour=3 UTC == 06:00 Europe/Moscow
    (Moscow does NOT observe DST since 2014 — single year-round +03:00).
    Combined with minute=25 → 06:25 Moscow time as locked in D-33-13.

    ARQ 0.28 stores `keep_result=60` cron kwarg on the CronJob as the
    `keep_result_s` attribute (see test_worker_settings module docstring
    W-1 follow-up).
    """
    matching = [
        c for c in WorkerSettings.cron_jobs if c.coroutine is expire_pt_packages
    ]
    assert len(matching) == 1, "expire_pt_packages cron entry not registered"
    c = matching[0]
    assert c.hour == 3, c.hour
    assert c.minute == 25, c.minute
    assert c.unique is True
    assert c.keep_result_s == 60
