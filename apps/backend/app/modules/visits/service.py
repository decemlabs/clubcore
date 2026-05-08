"""Visits service — anti-fraud chain + audit emits + transactional commits (Phase 19).

PUBLIC ENTRY POINTS:
- create_visit_reception(session, actor, payload) — HTTP path; channel='reception'.
- create_visit_self_checkin(session, telegram_user_id, chat_id) — bot path; channel='telegram_bot'.
- list_visits(session, query) / get_visit(session, visit_id) — read-side delegations.

ANTI-FRAUD CHAIN (private `_create_visit_with_anti_fraud`):
  1. gym_hours window check     → OutsideGymHoursError(409, code='outside_gym_hours')
  2. active_membership resolver → NoActiveMembershipError(409, code='no_active_membership')
  3. INSERT + flush + UNIQUE    → DuplicateCheckinError(409, code='duplicate_checkin')

ORDER LOCKED (D-03). Reception + bot share this chain via the wrappers — see D-04.
Adding a third channel (NFC turnstile, v2+) is one new public wrapper + one new
`channel` enum value in the migration's CHECK constraint.

DEVIATION FROM PHASE 16/17 (D-05 — DO NOT NORMALIZE BACK):
  Rejection paths emit `visit_rejected_*` audit + commit + raise — even though
  the canonical Phase 16/17 service rule is "no commit on raise". Rationale:
    - Pitfall 9 (residual fraud risk): rejection patterns ARE the data the
      audit log uses for anti-fraud detection. A one-sided log (successes
      only) is not useful.
    - VIS-AUDIT-01 + ROADMAP SC#5 explicitly require "every successful or
      rejected check-in writes the locked audit event".
    - The duplicate-checkin path needs `await session.rollback()` first (the
      failed INSERT poisoned the session), THEN a fresh emit + commit.

INFRA-13 commit gate (Phase 15): every public mutation function AND the
private chain commits on EVERY exit branch — no exemption marker needed.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import (
    CurrentUser,
    resolve_active_membership,
    resolve_client_by_telegram_user_id,
)
from app.core.exceptions import (
    ClientNotLinkedError,
    DuplicateCheckinError,
    NoActiveMembershipError,
    OutsideGymHoursError,
    VisitNotFoundError,
)
from app.core.pagination import PaginatedData
from app.modules.visits import repository
from app.modules.visits.schemas import (
    VisitCreateRequest,
    VisitListQuery,
    VisitResponse,
)

_MSK = ZoneInfo("Europe/Moscow")


def _is_duplicate_visit_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_visits_client_id_gym_date` (D-08).

    Mirror of memberships/service.py `_is_plan_in_use_conflict`. Checks
    `constraint_name` attribute first (asyncpg exposes this), then falls back
    to substring search on the stringified exception. The constraint name is
    the literal coupling point with `alembic/versions/0006_visits.py`.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_visits_client_id_gym_date":
        return True
    return "uq_visits_client_id_gym_date" in str(exc.orig)


def _now_msk() -> datetime:
    return datetime.now(_MSK)


def _today_msk() -> date:
    return _now_msk().date()


def _assert_within_gym_hours(now_msk: time) -> None:
    """Raise OutsideGymHoursError if `now_msk` is outside [start, end) (D-10, CD-07).

    Pure synchronous helper — testable without DB. End is exclusive: at 23:00
    the door is closed. Settings invariant `end > start` enforced at boot
    (Plan 19-01 model_validator) — this helper assumes the invariant holds.
    """
    settings = get_settings()
    if not (settings.gym_hours_start <= now_msk < settings.gym_hours_end):
        raise OutsideGymHoursError(
            "outside_gym_hours",
            fields={
                "open": settings.gym_hours_start.isoformat(),
                "close": settings.gym_hours_end.isoformat(),
            },
        )


async def _create_visit_with_anti_fraud(
    session: AsyncSession,
    *,
    client_id: UUID,
    channel: str,
    checked_in_by: UUID | None,
    audit_actor_user_id: UUID | None,
) -> tuple[VisitResponse, date]:
    """Shared anti-fraud chain (D-04). Reception + bot wrappers call this.

    Order: gym_hours → active_membership → insert+UNIQUE (D-03).
    Reject paths emit + commit + raise (D-05).

    Returns (VisitResponse, membership.end_date) on success. The reception path
    discards end_date; the bot path uses it to compute days_remaining for the
    DM (D-22-11). The public VisitResponse schema is UNCHANGED.
    """
    settings = get_settings()
    now_msk_dt = _now_msk()
    now_msk_t = now_msk_dt.time()
    today_msk = now_msk_dt.date()

    # ── Step 1: gym_hours ──────────────────────────────────────────────
    if not (settings.gym_hours_start <= now_msk_t < settings.gym_hours_end):
        await audit.emit(
            session,
            "visit_rejected_outside_hours",
            actor_user_id=audit_actor_user_id,
            resource_type="visit",
            resource_id=None,
            client_id=str(client_id),
            channel=channel,
            current_local_time=now_msk_dt.isoformat(),
            gym_open=settings.gym_hours_start.isoformat(),
            gym_close=settings.gym_hours_end.isoformat(),
        )
        await session.commit()  # D-05 — preserve the rejection audit row
        raise OutsideGymHoursError(
            "outside_gym_hours",
            fields={
                "open": settings.gym_hours_start.isoformat(),
                "close": settings.gym_hours_end.isoformat(),
            },
        )

    # ── Step 2: active_membership ──────────────────────────────────────
    membership = await resolve_active_membership(session, client_id)
    if membership is None:
        await audit.emit(
            session,
            "visit_rejected_no_membership",
            actor_user_id=audit_actor_user_id,
            resource_type="visit",
            resource_id=None,
            client_id=str(client_id),
            channel=channel,
        )
        await session.commit()  # D-05
        raise NoActiveMembershipError(
            "no_active_membership",
            fields={"client_id": str(client_id)},
        )

    # ── Step 3: insert + UNIQUE check ──────────────────────────────────
    visit = await repository.create(
        session,
        client_id=client_id,
        membership_id=membership.id,
        channel=channel,
        checked_in_by=checked_in_by,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()  # poisoned session must roll back first (D-08)
        if _is_duplicate_visit_conflict(exc):
            await audit.emit(
                session,
                "visit_rejected_duplicate",
                actor_user_id=audit_actor_user_id,
                resource_type="visit",
                resource_id=None,
                client_id=str(client_id),
                channel=channel,
                gym_date=str(today_msk),
            )
            await session.commit()  # D-05
            raise DuplicateCheckinError(
                "duplicate_checkin",
                fields={"client_id": str(client_id), "gym_date": str(today_msk)},
            ) from exc
        raise  # un-translated DB error — request boundary's get_db.rollback() cleans up

    # ── Step 4: success ────────────────────────────────────────────────
    membership_end_date = membership.end_date  # captured before commit for D-22-11
    await audit.emit(
        session,
        "visit_created",
        actor_user_id=audit_actor_user_id,
        resource_type="visit",
        resource_id=visit.id,
        client_id=str(client_id),
        membership_id=str(membership.id),
        channel=channel,
    )
    await session.commit()
    return VisitResponse.model_validate(visit), membership_end_date


# ─── Public reception path ───────────────────────────────────────────────────
async def create_visit_reception(
    session: AsyncSession,
    actor: CurrentUser,
    payload: VisitCreateRequest,
) -> VisitResponse:
    """POST /api/v1/visits — reception manual check-in (VIS-EP-03)."""
    visit_response, _end_date = await _create_visit_with_anti_fraud(
        session,
        client_id=payload.client_id,
        channel="reception",
        checked_in_by=actor.id,
        audit_actor_user_id=actor.id,
    )
    return visit_response


# ─── Public bot path (Phase 20 consumer) ─────────────────────────────────────
async def create_visit_self_checkin(
    session: AsyncSession,
    telegram_user_id: int,
    chat_id: int,
) -> tuple[VisitResponse, date]:
    """Bot path — Phase 20 imports this via HandlerContext.visits_service (D-10).

    Looks up Client by telegram_user_id via the resolver (D-02). On None,
    raises ClientNotLinkedError WITHOUT an audit emit — Phase 20 owns the
    `telegram_unknown_checkin` event (its own taxonomy addition). Phase 19
    does NOT emit any audit row for unknown-tg lookups (D-12).

    Returns (VisitResponse, membership.end_date) on success so the Telegram
    handler can compute days_remaining for the DM (D-22-11) without a second
    DB query. The public VisitResponse Pydantic schema is unchanged.
    """
    del chat_id  # forward-compat; Phase 20's handler may use it for DM routing
    client = await resolve_client_by_telegram_user_id(session, telegram_user_id)
    if client is None:
        raise ClientNotLinkedError(
            "client_not_linked",
            fields={"telegram_user_id": str(telegram_user_id)},
        )
    return await _create_visit_with_anti_fraud(
        session,
        client_id=client.id,
        channel="telegram_bot",
        checked_in_by=None,
        audit_actor_user_id=None,
    )


# ─── Read-side ───────────────────────────────────────────────────────────────
async def list_visits(
    session: AsyncSession, query: VisitListQuery
) -> PaginatedData[VisitResponse]:
    """GET /api/v1/visits — paginated list, default sort checked_in_at DESC (VIS-EP-01)."""
    page = await repository.list_by_query(session, query)
    return PaginatedData.model_construct(
        items=[VisitResponse.model_validate(v) for v in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_visit(session: AsyncSession, visit_id: UUID) -> VisitResponse:
    """GET /api/v1/visits/{id} — 404 visit_not_found on missing (VIS-EP-02)."""
    visit = await repository.get(session, visit_id)
    if visit is None:
        raise VisitNotFoundError("visit_not_found", fields={"id": str(visit_id)})
    return VisitResponse.model_validate(visit)
