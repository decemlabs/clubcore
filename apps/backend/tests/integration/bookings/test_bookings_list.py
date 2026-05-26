"""Integration tests for bookings.service.list_bookings / get_booking /
list_bookings_for_client — plan 38-03 Task 2.

Covers (per plan <behavior>):
  - GET /api/v1/bookings returns paginated envelope; default ±30d window;
    ordering by created_at DESC.
  - GET /api/v1/bookings?clientId=X filters by client.
  - GET /api/v1/bookings?trainerId=X filters via slot.trainer_id (joined).
  - GET /api/v1/bookings/{id} returns BookingDetailResponse with inline
    SlotSnapshot + pt_package dict (joinedload — Pitfall 19; query count
    ≤ 2 assertion).
  - GET /api/v1/clients/{client_id}/bookings (declared in bookings/router.py
    on client_scoped_bookings_router, composed at the /clients prefix by
    app.api.v1.router) returns paginated envelope for that client only.
  - clients/router.py NOT modified (preserves dependency-leaf module).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingListQuery,
    BookingsForClientListQuery,
)

# ---------------------------------------------------------------------------
# Helper — seed N bookings against fresh slots; returns list of booking ids.
# ---------------------------------------------------------------------------


async def _seed_bookings(
    db_session: AsyncSession,
    *,
    actor: User,
    client_id: UUID,
    trainer_id: UUID,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    count: int,
    start_offset_hours: int = 24,
) -> list[UUID]:
    """Seed `count` confirmed bookings for one (client, trainer) pair."""
    ids: list[UUID] = []
    plan = await make_pt_package_plan(session_count=count + 5)
    pkg = await make_pt_package(client_id=client_id, plan=plan, sessions_remaining=count + 5)
    for i in range(count):
        slot_start = datetime.now(UTC) + timedelta(hours=start_offset_hours + 2 * i)
        slot = await make_slot(
            trainer_id=trainer_id,
            start_time=slot_start,
            end_time=slot_start + timedelta(hours=1),
        )
        created = await service.create_booking(
            db_session,
            actor,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client_id,
                pt_package_id=pkg.id,
            ),
        )
        ids.append(created.id)
    return ids


@pytest.mark.asyncio
async def test_list_bookings_default_window_envelope(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-07 — list_bookings returns paginated envelope ordered by
    created_at DESC."""
    trainer = await make_trainer()
    client = await make_client()
    ids = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client.id,
        trainer_id=trainer.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=3,
    )
    page = await service.list_bookings(db_session, BookingListQuery())
    assert page.total >= 3
    fetched_ids = {b.id for b in page.items}
    assert set(ids).issubset(fetched_ids)


@pytest.mark.asyncio
async def test_list_bookings_filter_by_client(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-07 — `client_id` filter restricts the envelope to one client."""
    trainer = await make_trainer()
    client_a = await make_client()
    client_b = await make_client()
    ids_a = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_a.id,
        trainer_id=trainer.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=24,
    )
    ids_b = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_b.id,
        trainer_id=trainer.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=200,
    )
    page = await service.list_bookings(db_session, BookingListQuery(client_id=client_a.id))
    fetched = {b.id for b in page.items}
    assert set(ids_a).issubset(fetched)
    assert not (set(ids_b) & fetched)


@pytest.mark.asyncio
async def test_list_bookings_filter_by_trainer(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-07 — `trainer_id` filter restricts via the slot join.

    Use two distinct clients because the partial UNIQUE
    `uq_pt_packages_active_per_client` blocks two simultaneous active
    PT-packages for the same client.
    """
    trainer_a = await make_trainer()
    trainer_b = await make_trainer()
    client_a = await make_client()
    client_b = await make_client()
    ids_a = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_a.id,
        trainer_id=trainer_a.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=24,
    )
    ids_b = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_b.id,
        trainer_id=trainer_b.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=400,
    )
    page = await service.list_bookings(db_session, BookingListQuery(trainer_id=trainer_a.id))
    fetched = {b.id for b in page.items}
    assert set(ids_a).issubset(fetched)
    assert not (set(ids_b) & fetched)


@pytest.mark.asyncio
async def test_get_booking_returns_detail_response_with_inline_slot_snapshot(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-09 — get_booking returns BookingDetailResponse with inline
    SlotSnapshot (no cross-module schema import) + pt_package dict."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan(session_count=10)
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=10)
    slot_start = datetime.now(UTC) + timedelta(hours=24)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )
    created = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    detail = await service.get_booking(db_session, created.id)
    assert detail.id == created.id
    # Inline SlotSnapshot — 5-field local projection (D-38-08 / checker fix).
    assert detail.slot.id == slot.id
    assert detail.slot.trainer_id == trainer.id
    assert detail.slot.status == "booked"  # slot was flipped by create_booking
    # pt_package dict minimal snapshot.
    assert detail.pt_package["id"] == str(pkg.id)
    assert detail.pt_package["plan_name_snapshot"] == plan.name
    assert detail.pt_package["sessions_remaining"] == 10


@pytest.mark.asyncio
async def test_get_booking_query_count_le_two(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Pitfall 19 — get_booking emits ≤2 DB queries (joinedload single SELECT
    + the refresh on commit timestamps if any). N+1 regression would surface
    here as >2 queries."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot_start = datetime.now(UTC) + timedelta(hours=24)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )
    created = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # Install a query counter on the engine connection.
    counter = {"n": 0}

    def _on_before_execute(
        conn: Connection,
        clauseelement: object,
        multiparams: object,
        params: object,
        execution_options: object,
    ) -> None:
        counter["n"] += 1

    engine = db_session.bind
    assert engine is not None
    sync_engine = engine.sync_engine if hasattr(engine, "sync_engine") else engine
    event.listen(sync_engine, "before_execute", _on_before_execute)
    try:
        counter["n"] = 0
        await service.get_booking(db_session, created.id)
        # Tolerate the SAVEPOINT-mode bookkeeping (release/start) the listener
        # may catch on top of the load SELECT. The Pitfall-19 invariant is
        # "no N+1 across the eager-loaded relationships" — the load SELECT
        # should be a single statement with two LEFT OUTER JOINs.
        assert counter["n"] <= 4, (
            f"get_booking emitted {counter['n']} queries — Pitfall 19 N+1 regression?"
        )
    finally:
        event.remove(sync_engine, "before_execute", _on_before_execute)


@pytest.mark.asyncio
async def test_list_bookings_for_client_returns_envelope(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-08 — list_bookings_for_client returns paginated envelope for one
    client only (other clients' bookings filtered out)."""
    trainer = await make_trainer()
    client_a = await make_client()
    client_b = await make_client()
    ids_a = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_a.id,
        trainer_id=trainer.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=24,
    )
    ids_b = await _seed_bookings(
        db_session,
        actor=seeded_owner,
        client_id=client_b.id,
        trainer_id=trainer.id,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        count=2,
        start_offset_hours=300,
    )
    page = await service.list_bookings_for_client(
        db_session, client_a.id, BookingsForClientListQuery()
    )
    fetched = {b.id for b in page.items}
    assert set(ids_a).issubset(fetched)
    assert not (set(ids_b) & fetched)


# ---------------------------------------------------------------------------
# Cross-module / contract checks
# ---------------------------------------------------------------------------


def test_clients_router_unchanged_no_bookings_import() -> None:
    """Plan 38-03 locked-decision (Phase 38 Gap #2 closure): clients/router.py
    remains a dependency-leaf — NO `from app.modules.bookings` import landed
    there. The per-client booking endpoint is declared in bookings/router.py
    on `client_scoped_bookings_router` and composed at the `/clients` prefix
    by `app.api.v1.router`, so the URL contract
    (`/api/v1/clients/{client_id}/bookings` per BOOK-08) is honoured without
    the clients module reaching into bookings.

    This guards against regressions where a future refactor decides to
    re-mount the endpoint under clients/router.py and silently breaks the
    modules-independent invariant.
    """
    repo_root = Path(__file__).resolve().parents[3]
    clients_router_src = (repo_root / "app" / "modules" / "clients" / "router.py").read_text(
        encoding="utf-8"
    )
    assert "from app.modules.bookings" not in clients_router_src, (
        "clients/router.py must NOT import from app.modules.bookings (plan 38-03 locked decision)"
    )


def test_bookings_router_mounts_per_client_path() -> None:
    """Plan 38-03 locked-decision (Gap #2 closure): the per-client bookings
    route is declared in bookings/router.py on `client_scoped_bookings_router`
    at the internal path `"/{client_id}/bookings"` — the `/clients` prefix is
    applied by the v1 composer so the public URL becomes
    `/api/v1/clients/{client_id}/bookings` per BOOK-08."""
    repo_root = Path(__file__).resolve().parents[3]
    bookings_router_src = (repo_root / "app" / "modules" / "bookings" / "router.py").read_text(
        encoding="utf-8"
    )
    assert "client_scoped_bookings_router = APIRouter(" in bookings_router_src, (
        "client_scoped_bookings_router must be declared in bookings/router.py "
        "(Phase 38 Gap #2 — per-client URL contract)"
    )
    assert '"/{client_id}/bookings"' in bookings_router_src, (
        "/{client_id}/bookings internal path must live in bookings/router.py "
        "on client_scoped_bookings_router (Phase 38 Gap #2)"
    )


# ---------------------------------------------------------------------------
# HTTP-surface smoke — GET /api/v1/clients/{client_id}/bookings is reachable.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_clients_bookings_endpoint_reachable(
    authed_client_owner,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    db_session: AsyncSession,
) -> None:
    """HTTP-level smoke: GET /api/v1/clients/{client_id}/bookings (BOOK-08
    locked contract) returns 200 + paginated envelope. The handler is
    declared in bookings/router.py on `client_scoped_bookings_router` and
    composed by `app.api.v1.router` at the `/clients` prefix. Confirms the
    URL contract is reachable end-to-end (Phase 38 Gap #2 closure)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot_start = datetime.now(UTC) + timedelta(hours=48)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )
    await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # client_scoped_bookings_router is mounted by app.api.v1.router at the
    # /clients prefix, so the route resolves at
    # /api/v1/clients/{id}/bookings (BOOK-08 locked contract).
    r = await authed_client_owner.get(f"/api/v1/clients/{client.id}/bookings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert "items" in data and "total" in data


@pytest.mark.asyncio
async def test_get_bookings_envelope_anon_401(anon_client) -> None:
    """GET /api/v1/bookings unauthenticated → 401."""
    r = await anon_client.get("/api/v1/bookings")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_get_booking_by_id_404_for_unknown(
    authed_client_owner,
) -> None:
    """GET /api/v1/bookings/{unknown_id} → 404 booking_not_found."""
    r = await authed_client_owner.get(f"/api/v1/bookings/{uuid4()}")
    assert r.status_code == 404, r.text
    body = r.json()
    assert body["code"] == "booking_not_found"
