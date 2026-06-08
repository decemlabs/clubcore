"""MEM-FRZ-06 — frozen membership excluded from resolver, oracle-safe DM.

Phase 25 D-25-17 invariant: `resolve_active_membership_by_client` and
`find_active_for_client` are NOT modified in Phase 25. Frozen rows are
excluded by the existing `Membership.status == 'active'` predicate. If a
future Phase 26 tiebreak refactor surfaces frozen rows, this test fails
loudly.

Also asserts the Telegram /checkin oracle-safe DM (Phase 20 D-5): a frozen
client receives the SAME generic Russian "no active membership" DM as a
stranger or a client without any membership — no oracle leak about freeze
status.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, time, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest
import structlog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.visits.service as visits_svc_mod
from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.handlers import HandlerContext, checkin_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.memberships.service import resolve_active_membership_by_client
from app.modules.visits import service as visits_service
from tests.conftest import StubTelegramSender

_MSK = ZoneInfo("Europe/Moscow")


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 66 IDM-07: freeze_membership now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234080",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_frozen_membership_excluded_from_resolver(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-FRZ-06 part 1: frozen membership → resolver returns None.

    The existing `Membership.status == 'active'` predicate in
    `find_active_for_client` naturally excludes the frozen row.
    """
    plan = await make_plan(name="Resolver Frozen")
    client = await _create_client(authed_client_reception, phone="+79991234081")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    # Freeze the active membership via HTTP
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "frozen"

    # Resolver MUST return None for a frozen-only client.
    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is None, (
        "MEM-FRZ-06: resolve_active_membership_by_client MUST exclude frozen rows. "
        "If this fails, a Phase 26 tiebreak refactor likely surfaced frozen rows; "
        "Phase 25 D-25-17 invariant requires the resolver path to remain untouched."
    )


async def test_frozen_membership_visits_endpoint_no_active_membership(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MEM-FRZ-06 part 2: reception POST /api/v1/visits → 409 no_active_membership.

    The Phase 19 NoActiveMembershipError raise path is triggered because the
    resolver returns None for the frozen client.
    """
    plan = await make_plan(name="Resolver Visits")
    client = await _create_client(authed_client_reception, phone="+79991234082")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    # Freeze
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200

    # Open gym hours so this isn't a hours-rejection — use monkeypatch so the
    # mutation is undone at test teardown (avoids leaking into later tests
    # that read default gym_hours_start='07:00').
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(visits_svc_mod, "get_settings", lambda: settings)

    # POST /visits — should hit NoActiveMembershipError → 409 no_active_membership
    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": str(client_uuid)},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "no_active_membership"


# --- Telegram /checkin oracle-safe DM (Phase 20 D-5) -----------------------


def _today_msk() -> date:
    from datetime import datetime as _dt

    return _dt.now(_MSK).date()


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh cached module-level structlog logger (matches checkin_handler tests)."""
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


def _build_update(*, telegram_user_id: int, chat_id: int, update_id: int) -> SimpleNamespace:
    eff_user = SimpleNamespace(id=telegram_user_id, username=None, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(text="/checkin", chat=eff_chat, from_user=eff_user)
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_ctx(db_session: AsyncSession, redis_client: Any) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
        visits_service=visits_service,
        redis=redis_client,
        # Phase 40 D-40-04/06: checkin_handler does not consume these, but the
        # NamedTuple constructor requires every field — benign placeholders.
        bookings_service=cast(Any, None),
        schedule_service=cast(Any, None),
        # Phase 93 D-06 relaxation: messaging_service appended; not consumed by
        # the freeze-resolver checkin path — benign placeholder.
        messaging_service=cast(Any, None),
    )


def _open_gym_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(visits_svc_mod, "get_settings", lambda: settings)


async def test_telegram_checkin_frozen_oracle_safe_dm(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MEM-FRZ-06 part 3: Telegram /checkin on frozen membership generic DM.

    The frozen client receives the SAME "no active membership" Russian DM
    as a client without any membership (oracle-safe per Phase 20 D-5).
    No leak that the membership exists but is frozen.
    """
    _open_gym_hours(monkeypatch)

    # Seed creator/owner
    creator = User(
        email=f"frozen-tg-owner-{uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$notreal",  # noqa: S106
        role=Role.OWNER,
        full_name="Frozen TG Owner",
    )
    db_session.add(creator)
    await db_session.flush()

    plan = MembershipPlan(
        name=f"FrozenPlan-{uuid4().hex[:8]}",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    tg_user_id = 71_000_999
    chat_id = 555_999_001
    phone_suffix = uuid4().int % 10**7
    client = Client(
        last_name=f"Frozen-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7903{phone_suffix:07d}",
        telegram_user_id=tg_user_id,
        created_by_user_id=creator.id,
    )
    db_session.add(client)
    await db_session.flush()

    today = _today_msk()
    # Active membership FROZEN
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=29),
        status="frozen",
        activation_policy="purchase_date",
    )
    db_session.add(membership)
    await db_session.flush()
    client_id_str = str(client.id)
    await db_session.commit()

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=9001)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    # Oracle-safe DM: same string as a client without ANY membership.
    expected_dm = "У вас нет активного абонемента. Обратитесь к администратору."  # noqa: RUF001
    assert stub_telegram_sender.text_calls == [(chat_id, expected_dm)], (
        "MEM-FRZ-06: frozen client MUST receive the same generic 'no active "
        "membership' DM as a stranger — Phase 20 D-5 oracle-safe invariant."
    )

    # Audit row for visit_rejected_no_membership (same code path as no-membership case).
    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "visit_rejected_no_membership")
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
