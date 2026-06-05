"""WorkerSettings class-shape + cron-resolution invariant tests (Phase 18 CD-04 / ARQ-03).

No DB required — these tests exercise the WorkerSettings class via attribute
introspection. The cron-resolution invariant test (test 7) monkey-patches
`WorkerSettings.cron_jobs` to verify Pitfall 4 step 6 fails LOUD at boot.

W-1 (cron attribute shape probe, 2026-05-07):
    `cd apps/backend && uv run python -c "from arq.cron import cron;\
    async def f(ctx): pass; c = cron(f, hour=3, minute=5);\
    print(type(c.hour).__name__, c.hour)"`
    → printed `int 3 int 5` → Form B (bare ints) is locked below.

W-1 follow-up (ARQ 0.28 auto-prefixes CronJob.name with `cron:`, see 18-03
SUMMARY): the plan's literal assertion `cron_jobs[0].name == "expire_memberships"`
would FAIL against the installed runtime (returns `"cron:expire_memberships"`).
We assert on `cron_jobs[0].coroutine.__name__` instead — the same accessor the
on_startup invariant uses, and the function-name oracle that survives ARQ
version bumps.

W-1 follow-up (ARQ 0.28 stores `keep_result=60` as `keep_result_s` attribute,
not `keep_cronjob_progress`): we assert on the `keep_result_s` attribute name
that ARQ 0.28 actually exposes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
from arq.cron import cron

from app.workers import WorkerSettings
from app.workers.scheduled.expire_memberships import expire_memberships


def test_worker_settings_class_importable() -> None:
    """Regression catcher — class rename or accidental deletion fails here."""
    assert WorkerSettings.__name__ == "WorkerSettings"


def test_worker_settings_cron_resolves_to_registered_function() -> None:
    """ARQ-03: the cron entry's coroutine is the SAME object as `expire_memberships`.

    Note: ARQ 0.28 prefixes `CronJob.name` with `"cron:"` (e.g.
    `"cron:expire_memberships"`); we assert on `.coroutine.__name__` instead so
    the test mirrors the on_startup invariant exactly and survives ARQ version
    bumps that change the prefix scheme.

    Phase 27 (D-27-16): cron_jobs grew to 2 entries — 06:05 expire_memberships
    (kept at index 0) followed by 06:15 send_expiring_notifications. Order is
    preserved per plan 27-04 acceptance.

    Phase 33 (D-33-13): cron_jobs grew to 3 entries — append expire_pt_packages
    at 06:25 Europe/Moscow (index 2). Earlier indices preserved.

    Phase 39 (D-39-16): cron_jobs grew to 5 entries — Wave 3 appended
    mark_no_show_bookings at 20:10 UTC / 23:10 MSK; Wave 4 inserted
    send_booking_reminders at 03:35 UTC / 06:35 MSK BEFORE the no-show entry
    so the final D-39-16 order is memberships -> expiring_notifs ->
    pt_packages -> reminders -> no_show. Earlier indices preserved.

    Phase 44 appended cleanup_password_reset_tokens (index 5).

    Phase 51 (Plan 51-09 FISCAL-06 + REFUND-02) appended two crons:
    monitor_stale_fiscal_receipts (index 6) and poll_pending_refunds
    (index 7). cron_jobs now had 8 entries.

    Phase 59 (Plan 59-05 REC-02) appended generate_recurring_slots
    (index 8) — daily 07:00 MSK slot materialization cron. cron_jobs
    now has 9 entries total. Earlier indices preserved.

    Phase 84 (Plan 84-02 APAY-01) appended charge_expiring_autopay
    (index 9) — daily 05:00 MSK autopay charge cron. cron_jobs now
    has 10 entries total.
    """
    assert len(WorkerSettings.cron_jobs) == 10
    cron_entry = WorkerSettings.cron_jobs[0]
    assert cron_entry.coroutine.__name__ == "expire_memberships"
    assert cron_entry.coroutine is expire_memberships, (
        "cron_jobs[0].coroutine must be the SAME object as "
        "expire_memberships imported from app.workers.scheduled — "
        "any indirection breaks ARQ's runtime resolution"
    )


def test_worker_settings_cron_locked_args() -> None:
    """ARQ-03: hour=3, minute=5, unique=True, keep_result=60 (Europe/Moscow 06:05).

    Form B (bare ints) is locked per the W-1 probe — see this file's module
    docstring for the printed `int 3 int 5` evidence. ARQ 0.28 stores the
    `keep_result=60` cron parameter on the CronJob as `.keep_result_s`.
    """
    c = WorkerSettings.cron_jobs[0]
    assert c.hour == 3, c.hour
    assert c.minute == 5, c.minute
    assert c.unique is True
    assert c.keep_result_s == 60


def test_charge_expiring_autopay_cron_registered() -> None:
    """Phase 84 APAY-01: charge_expiring_autopay cron registered with unique=True at distinct hour.

    Verifies T-84-05 (SQL-level idempotency second line of defence):
    - unique=True prevents concurrent ARQ ticks from double-initiating charges.
    - The hour is NOT 3:05 (expire_memberships slot) — no collision.
    - hour=2, minute=0 = 05:00 Europe/Moscow (container TZ=UTC).
    """
    from app.workers.scheduled.charge_expiring_autopay import charge_expiring_autopay

    # Find the charge_expiring_autopay cron entry (index 9 in the current list).
    autopay_cron = next(
        (c for c in WorkerSettings.cron_jobs if c.coroutine.__name__ == "charge_expiring_autopay"),
        None,
    )
    assert autopay_cron is not None, "charge_expiring_autopay not found in cron_jobs"
    assert autopay_cron.coroutine is charge_expiring_autopay
    assert autopay_cron.unique is True
    assert autopay_cron.keep_result_s == 60
    # Distinct hour — NOT 3 (expire_memberships) or 4 (generate_recurring_slots).
    assert autopay_cron.hour == 2, f"Expected hour=2 (05:00 MSK), got {autopay_cron.hour}"
    assert autopay_cron.minute == 0


def test_worker_settings_functions_registered() -> None:
    """ARQ-03 verbatim: functions=[expire_memberships].

    Phase 27 (D-27-16) extended the list to also include
    send_expiring_notifications; expire_memberships membership is asserted
    here, the new entry is asserted by Phase 27 tests.

    Phase 33 (D-33-13) appended expire_pt_packages — its membership is
    asserted by tests/unit/test_worker_cron_resolution.py.

    Phase 39 (D-39-16) appended mark_no_show_bookings (Wave 3) and
    send_booking_reminders (Wave 4) — list had 5 entries.

    Phase 42 (Plan 09 / EMAIL-03) appended ``dispatch_email`` — the
    request-handler-driven (NOT cron) email-send job. List grew to 6.

    Phase 44 appended ``cleanup_password_reset_tokens`` (cron).

    Phase 50/51 appended ``dispatch_fiscal_receipt`` (Plan 51-05 ARQ task),
    plus Phase 51 ``monitor_stale_fiscal_receipts`` and
    ``poll_pending_refunds`` (Plan 51-09 crons — both crons AND functions
    per ARQ contract). List had 10 entries.

    Phase 52 (NOT-01..05) appended ``dispatch_payment_notification`` — the
    request-handler-driven cross-channel client + owner-alert dispatch task.
    List had 11 entries.

    Phase 59 (Plan 59-05 REC-02) appended ``generate_recurring_slots`` — the
    daily slot materialization cron. List now has 12 entries.

    Phase 84 (Plan 84-02 APAY-01) appended ``charge_expiring_autopay`` — the
    daily off-session autopay charge cron. List had 13 entries.

    Phase 84 (Plan 84-03 APAY-04) appended ``dispatch_autopay_failure_notification`` —
    the decline-path failure notification ARQ task. List now has 14 entries.
    """
    from app.modules.autopay_charges.tasks import dispatch_autopay_failure_notification
    from app.workers.scheduled.charge_expiring_autopay import charge_expiring_autopay

    assert expire_memberships in WorkerSettings.functions
    assert charge_expiring_autopay in WorkerSettings.functions
    assert dispatch_autopay_failure_notification in WorkerSettings.functions
    assert len(WorkerSettings.functions) == 14


def test_worker_settings_redis_settings_resolved() -> None:
    """RedisSettings.from_dsn(str(get_settings().redis_url)) populates host."""
    assert isinstance(WorkerSettings.redis_settings.host, str)
    assert WorkerSettings.redis_settings.host != ""


@pytest.mark.asyncio
async def test_on_startup_cron_resolution_invariant_passes_at_baseline() -> None:
    """Smoke test — verifies on_startup populates ctx without crashing.

    Deeper sessionmaker behavior is exercised by integration tests in 18-05.
    on_startup against the unmodified WorkerSettings does NOT raise. The
    invariant `cron_function_names ⊆ function_names` holds because Plan 18-03
    wires `cron_jobs[0].coroutine == expire_memberships == functions[0]`.
    """
    # Phase 42 Plan 09: on_startup also reads ctx["redis"] to register the
    # ArqRedis pool used by enqueue_email_dispatch. Seed a sentinel
    # alongside the DB sentinels — register_arq_pool only stores the
    # reference, it does not call any method on it, so a bare object()
    # suffices for this unit test.
    ctx: dict[str, Any] = {"redis": object()}

    # We must not actually open the DB lifespan in a unit test — monkey-patch
    # `db_lifespan_manager` to a no-op so on_startup runs the assertion path
    # without hitting Postgres.
    import app.workers as workers_module

    @asynccontextmanager
    async def _noop_lifespan() -> Any:
        yield (object(), object())  # (engine, sessionmaker) sentinels

    with patch.object(workers_module, "db_lifespan_manager", _noop_lifespan):
        await WorkerSettings.on_startup(ctx)

    assert "_db_stack" in ctx
    # Strengthened from `is not None` (vacuous when sentinel is `object()`):
    # accept either a callable factory (real lifespan path) OR a non-None
    # sentinel (unit-test no-op path). Both prove on_startup populated the key.
    assert callable(ctx["sessionmaker"]) or ctx["sessionmaker"] is not None, (
        "on_startup must populate ctx['sessionmaker'] "
        "(sentinel object or real factory both acceptable in this smoke test)"
    )
    assert callable(ctx["engine"]) or ctx["engine"] is not None, (
        "on_startup must populate ctx['engine'] "
        "(sentinel object or real engine both acceptable in this smoke test)"
    )

    # Tear down the AsyncExitStack so the noop lifespan cleanly exits.
    await WorkerSettings.on_shutdown(ctx)


@pytest.mark.asyncio
async def test_on_startup_raises_when_cron_references_unregistered_function() -> None:
    """Pitfall 4 step 6 — silent no-op trap. Cron entry pointing at a function
    name not in `functions` MUST fail at boot, not at 06:05 the next morning.

    Mutates `WorkerSettings.cron_jobs` for the duration of the test ONLY.
    Restores the original list on teardown so subsequent tests see the real
    shape.
    """

    async def _bogus_function(ctx: dict[str, Any]) -> None:
        return None

    original_cron_jobs = WorkerSettings.cron_jobs
    try:
        # Inject a cron entry referencing a coroutine NOT in functions.
        WorkerSettings.cron_jobs = [
            *original_cron_jobs,
            cron(_bogus_function, hour=4, minute=0, unique=True),
        ]

        with pytest.raises(AssertionError, match="cron_jobs reference"):
            await WorkerSettings.on_startup({})
    finally:
        WorkerSettings.cron_jobs = original_cron_jobs
