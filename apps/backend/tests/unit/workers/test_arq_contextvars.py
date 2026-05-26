"""ARQ-05 / Pitfall 14 — on_job_start/on_job_end contextvars hook tests.

The hooks mirror RequestIdMiddleware (`app/core/middleware.py:21-25`):
clear THEN bind on entry; clear on exit. This file proves the bind→end→
bind→end shape leaves no leakage between consecutive runs in the same
asyncio task — the silent oracle-leak class Pitfall 14 documents.

No DB, no Redis — pure structlog contextvars introspection.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from app.workers import WorkerSettings


@pytest.fixture(autouse=True)
def _isolate_contextvars() -> Iterator[None]:
    """Clear structlog contextvars before AND after each test in this file.

    Without this isolation, a stray bind from a previous test (or from the
    test's own pre-run state) pollutes assertions on `get_contextvars()`.
    """
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


@pytest.mark.asyncio
async def test_on_job_start_binds_job_id_and_job_name() -> None:
    """ARQ-05 verbatim: job_id + job_name bound on contextvars."""
    ctx: dict[str, Any] = {
        "job_id": "abc-123",
        "function_name": "expire_memberships",
    }
    await WorkerSettings.on_job_start(ctx)

    bound = structlog.contextvars.get_contextvars()
    assert bound.get("job_id") == "abc-123", bound
    assert bound.get("job_name") == "expire_memberships", bound


@pytest.mark.asyncio
async def test_on_job_end_clears_contextvars() -> None:
    """on_job_end empties contextvars (prevents leak across runs)."""
    await WorkerSettings.on_job_start({"job_id": "abc-123", "function_name": "expire_memberships"})
    assert structlog.contextvars.get_contextvars(), "precondition: bound"

    await WorkerSettings.on_job_end({})

    assert structlog.contextvars.get_contextvars() == {}


@pytest.mark.asyncio
async def test_bind_end_bind_end_no_leakage_between_runs() -> None:
    """Pitfall 14: two consecutive runs in the same asyncio task must not leak.

    bind(job_id=A) → end → bind(job_id=B) → end. After the second bind, the
    contextvars dict contains job_id=B and NOT job_id=A (verified explicitly
    because the bind shape is clear+bind, not merge).
    """
    # Run 1
    await WorkerSettings.on_job_start({"job_id": "run-1", "function_name": "expire_memberships"})
    assert structlog.contextvars.get_contextvars().get("job_id") == "run-1"
    await WorkerSettings.on_job_end({})
    assert structlog.contextvars.get_contextvars() == {}

    # Run 2 — different job_id; must not see run-1's id at any point.
    await WorkerSettings.on_job_start({"job_id": "run-2", "function_name": "expire_memberships"})
    bound = structlog.contextvars.get_contextvars()
    assert bound.get("job_id") == "run-2"
    assert "run-1" not in bound.values(), f"leakage from run-1 into run-2 contextvars: {bound}"
    await WorkerSettings.on_job_end({})
    assert structlog.contextvars.get_contextvars() == {}


@pytest.mark.asyncio
async def test_on_job_start_clears_stale_bindings_before_binding() -> None:
    """clear-then-bind shape — pre-existing bindings are wiped, not merged.

    Mirrors RequestIdMiddleware (`clear_contextvars` BEFORE `bind_contextvars`).
    A future refactor that drops the `clear_contextvars` line would let stale
    keys (e.g. a leftover `request_id` from prior in-process work) bleed into
    the cron job's log lines — this test catches that regression.
    """
    structlog.contextvars.bind_contextvars(stale_key="must_be_cleared")
    assert structlog.contextvars.get_contextvars().get("stale_key") == "must_be_cleared"

    await WorkerSettings.on_job_start({"job_id": "x", "function_name": "expire_memberships"})

    bound = structlog.contextvars.get_contextvars()
    assert "stale_key" not in bound, f"on_job_start failed to clear stale bindings; got {bound}"
    assert bound.get("job_id") == "x"
