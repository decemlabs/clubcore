"""Unit tests for D-34-06 backdating-window math in record_pt_session.

Pure-async datetime arithmetic against the service-layer invariants — no
DB roundtrip; we patch ``resolve_trainer_by_id`` to raise a short-circuit
``TrainerNotFoundError`` so the window check fires FIRST and the trainer
lookup never proceeds. This isolates the window math (Step 1 of the
10-step orchestrator) from every other guard.

Boundary cases (B-11 / D-34-06):
  - Future-dated rejected for BOTH roles (PerformedAtInFutureError).
  - Reception 7d-inclusive boundary (just inside): no window error.
  - Reception 8d (just outside): PerformedAtOutOfWindowError.
  - Owner unlimited past: 365d back OK.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.permissions import Role
from app.modules.pt_sessions import service
from app.modules.pt_sessions.constants import BACKDATING_WINDOW_DAYS_RECEPTION
from app.modules.pt_sessions.schemas import PtSessionCreateRequest
from app.modules.pt_sessions.service import (
    PerformedAtInFutureError,
    PerformedAtOutOfWindowError,
    TrainerNotFoundError,
)


def _build_payload(performed_at: datetime) -> PtSessionCreateRequest:
    return PtSessionCreateRequest(
        pt_package_id=uuid4(),
        trainer_id=uuid4(),
        performed_at=performed_at,
        notes=None,
    )


def _actor(role: Role) -> object:
    """A minimal stand-in satisfying the CurrentUser Protocol (id + role)."""
    return SimpleNamespace(id=uuid4(), role=role)


@pytest.fixture
def _short_circuit_trainer_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``resolve_trainer_by_id`` to raise TrainerNotFoundError.

    The window-math guards (Step 1) run BEFORE the trainer Protocol-slot
    resolution (Step 2). When the window check passes, the orchestrator
    proceeds to call ``resolve_trainer_by_id`` and our stub aborts the
    rest of the pipeline immediately — letting the unit assertions
    distinguish "window error raised" from "window OK, fell through to
    trainer lookup."
    """

    async def _stub(_session: object, _trainer_id: object) -> object:
        # Mirroring the real signature; the orchestrator catches None →
        # TrainerNotFoundError. Returning None here triggers that path
        # deterministically when no window-error is raised first.
        return None

    monkeypatch.setattr(
        "app.modules.pt_sessions.service.resolve_trainer_by_id",
        _stub,
    )


@pytest.mark.asyncio
async def test_future_dated_rejected_reception(
    _short_circuit_trainer_lookup: None,
) -> None:
    """B-11 / D-34-06: future-dated performed_at → 422 performed_at_in_future.

    Applies to BOTH roles — recording a session that has not happened yet is
    a semantic error, regardless of role. Owner-unlimited applies only in
    the PAST direction.
    """
    future = datetime.now(UTC) + timedelta(hours=1)
    payload = _build_payload(future)
    actor = _actor(Role.RECEPTION)
    with pytest.raises(PerformedAtInFutureError) as exc:
        await service.record_pt_session(session=None, actor=actor, data=payload)  # type: ignore[arg-type]
    assert exc.value.code == "performed_at_in_future"


@pytest.mark.asyncio
async def test_future_dated_rejected_owner(
    _short_circuit_trainer_lookup: None,
) -> None:
    """B-11 / D-34-06: owner is unlimited in the PAST but NOT in the future."""
    future = datetime.now(UTC) + timedelta(hours=1)
    payload = _build_payload(future)
    actor = _actor(Role.OWNER)
    with pytest.raises(PerformedAtInFutureError) as exc:
        await service.record_pt_session(session=None, actor=actor, data=payload)  # type: ignore[arg-type]
    assert exc.value.code == "performed_at_in_future"


@pytest.mark.asyncio
async def test_reception_7d_boundary_inclusive(
    _short_circuit_trainer_lookup: None,
) -> None:
    """B-11 / D-34-06: reception just INSIDE the 7d window passes the gate.

    ``performed_at = now - (7d - 1s)`` is within the strict-greater-than
    comparison ``delta > timedelta(days=7)`` and must NOT raise
    PerformedAtOutOfWindowError. Falls through to trainer lookup (our stub
    returns None → TrainerNotFoundError).
    """
    inside = datetime.now(UTC) - (
        timedelta(days=BACKDATING_WINDOW_DAYS_RECEPTION) - timedelta(seconds=1)
    )
    payload = _build_payload(inside)
    actor = _actor(Role.RECEPTION)
    with pytest.raises(TrainerNotFoundError):
        await service.record_pt_session(session=None, actor=actor, data=payload)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_reception_8d_rejected(
    _short_circuit_trainer_lookup: None,
) -> None:
    """B-11 / D-34-06: reception 1 second beyond the 7d window → 422."""
    too_old = datetime.now(UTC) - (
        timedelta(days=BACKDATING_WINDOW_DAYS_RECEPTION) + timedelta(seconds=1)
    )
    payload = _build_payload(too_old)
    actor = _actor(Role.RECEPTION)
    with pytest.raises(PerformedAtOutOfWindowError) as exc:
        await service.record_pt_session(session=None, actor=actor, data=payload)  # type: ignore[arg-type]
    assert exc.value.code == "performed_at_out_of_window"


@pytest.mark.asyncio
async def test_owner_unlimited_past(
    _short_circuit_trainer_lookup: None,
) -> None:
    """B-11 / D-34-06: owner 365d in the past passes the window gate."""
    far_past = datetime.now(UTC) - timedelta(days=365)
    payload = _build_payload(far_past)
    actor = _actor(Role.OWNER)
    with pytest.raises(TrainerNotFoundError):
        await service.record_pt_session(session=None, actor=actor, data=payload)  # type: ignore[arg-type]
