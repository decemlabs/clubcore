"""Referral service (Phase 96 REFER-01/REFER-02/REFER-03/REFER-07).

Transaction discipline (D-03 caller-owns-txn): all three mutating service functions
flush + commit inside the service layer, matching gym.service.update_gym_info.
All cross-module client reads use raw SQL text() — no ORM import of Client (D-54-08).

INFRA-15: both audit pairs (referral_code_generated, referral_captured) are pre-
registered in LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS by Plan 96-01 before
any callsite here.

Idempotency:
  get_or_create_referral_code — pg_insert on_conflict_do_nothing with RETURNING; audit
    emitted only on real insert (RETURNING-gated, WR-01-iter2 fix). Lost-race path
    re-reads the winner row by client_id and returns it without emitting audit.
  capture_referral — pg_insert on_conflict_do_nothing with RETURNING; audit emitted
    only when RETURNING returns a new id (RETURNING-gated, CR-WR-01 fix).

IDOR safety:
  capture_referral receives the referee identity as an explicit argument from the
  require_client() principal — it is NEVER read from the request body (T-96-05).
"""

from __future__ import annotations

import secrets
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import Settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, ValidationAppError
from app.modules.referrals import repository
from app.modules.referrals.models import ReferralCapture, ReferralCode
from app.modules.referrals.schemas import (
    ReferralCodeResponse,
    ReferralConfigResponse,
    ReferralConfigUpdateRequest,
    ReferralInviteeItem,
    ReferralResolveResponse,
    ReferralSummaryResponse,
)

_log = structlog.get_logger("modules.referrals.service")

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no O/I/L (ambiguous)
_CODE_LENGTH = 8

# ---------------------------------------------------------------------------
# Typed error classes (D-09 distinct per-reason codes)
# ---------------------------------------------------------------------------


class ReferralCodeNotFoundError(NotFoundError):
    """Referral code string does not match any live code row."""

    code = "referral_code_not_found"
    status_code = 404


class SelfReferralError(ValidationAppError):
    """Client attempted to capture their own referral code."""

    code = "self_referral_not_allowed"
    status_code = 422


class ReferralConfigNotFoundError(NotFoundError):
    """Singleton referral-config row is absent (seed migration not yet run)."""

    code = "referral_config_not_found"
    status_code = 404


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _generate_unique_code(
    session: AsyncSession,
    *,
    max_attempts: int = 3,
) -> str:
    """Generate an 8-char Crockford-base32 code unique in referral_codes.

    Uses a raw-SQL existence check (D-54-08 pattern) and bounded retry on
    collision. RuntimeError after exhausting attempts (should be astronomically
    rare with 32^8 = ~1.1e12 candidates in a small table).
    """
    for _ in range(max_attempts):
        candidate = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(_CODE_LENGTH))
        result = (
            await session.execute(
                text("SELECT 1 FROM referral_codes WHERE code = :code"),
                {"code": candidate},
            )
        ).fetchone()
        if result is None:
            return candidate
    raise RuntimeError("failed to generate unique referral code after retries")


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def get_or_create_referral_code(
    session: AsyncSession,
    client_id: UUID,
    settings: Settings,
) -> ReferralCodeResponse:
    """Return the stable referral code for *client_id*, minting one on first call.

    Idempotent: if a code already exists (common path) or the concurrent-mint race
    is lost, returns the winner row without emitting a second referral_code_generated
    audit event (INFRA-15 gating — no duplicate audit).

    Caller-owns-txn: flush + commit here (D-03). Matches gym.service.update_gym_info
    discipline. pg_insert on_conflict_do_nothing is the authoritative idempotency
    guarantee (WR-01-iter2 fix: eliminates TOCTOU IntegrityError 500 from concurrent
    first-time mints for the same client_id hitting uq_referral_codes_client_id).
    """
    # Fast-path: most calls are idempotent returns, no write needed.
    existing = await repository.get_code_by_client_id(session, client_id)
    if existing is not None:
        share_url = f"{settings.pwa_base_url}/i/{existing.code}"
        _log.debug(
            "referral_code_existing",
            client_id=str(client_id),
            code=existing.code,
        )
        return ReferralCodeResponse(code=existing.code, share_url=share_url)

    # First mint — generate candidate code, insert atomically with bounded retry.
    # Bare ON CONFLICT DO NOTHING (no index target) covers BOTH unique constraints:
    #   - uq_referral_codes_client_id: concurrent same-client mint race
    #   - uq_referral_codes_code: code-string collision with a *different* client
    #     (vanishingly rare — two clients drawing the same 8-char code in the window
    #     between _generate_unique_code's SELECT dedup and this INSERT).
    # RETURNING is None on either conflict; we then re-read by client_id to
    # distinguish the two cases (WR-01-iter3 fix).
    mint_max_attempts = 5
    row = None
    for _attempt in range(mint_max_attempts):
        new_code_str = await _generate_unique_code(session)
        stmt = (
            pg_insert(ReferralCode)
            .values(client_id=client_id, code=new_code_str)
            .on_conflict_do_nothing()
            .returning(ReferralCode.id, ReferralCode.code)
        )
        row = (await session.execute(stmt)).one_or_none()
        if row is not None:
            break  # real insert — proceed to audit emit
        # Conflict fired (DO NOTHING — transaction stays valid, no IntegrityError).
        winner = await repository.get_code_by_client_id(session, client_id)
        if winner is not None:
            # Concurrent same-client mint won the race — return winner (no audit emit).
            _log.info(
                "referral_code_concurrent_no_op",
                client_id=str(client_id),
                msg="concurrent mint won — returning existing code",
            )
            return ReferralCodeResponse(
                code=winner.code,
                share_url=f"{settings.pwa_base_url}/i/{winner.code}",
            )
        # No winner for this client_id → code-string collided with another client.
        # Regenerate and retry (no audit emit, transaction still valid).
        _log.warning(
            "referral_code_string_collision_retry",
            client_id=str(client_id),
            attempt=_attempt + 1,
        )
    if row is None:
        raise RuntimeError(
            "referral code minting exhausted retries on code-string collisions"
        )

    code_row_id: UUID = row[0]
    code_row_code: str = row[1]
    share_url = f"{settings.pwa_base_url}/i/{code_row_code}"

    # RETURNING-gated audit emit — only on real insert (INFRA-15).
    # Payload UUID fields are str() here: JSONB serialization uses stdlib
    # json.dumps which cannot handle UUID objects; Pydantic v2 coerces str
    # back to UUID at model_validate time so ReferralCodeGeneratedPayload
    # validates correctly with string inputs.
    await audit.emit(
        session,
        "referral_code_generated",
        actor_user_id=None,  # client-initiated; no staff actor
        resource_type="referral",
        resource_id=code_row_id,
        client_id=str(client_id),
        referral_code_id=str(code_row_id),
        code=code_row_code,
    )
    await session.commit()
    _log.info(
        "referral_code_generated",
        client_id=str(client_id),
        referral_code_id=str(code_row_id),
        code=code_row_code,
    )
    return ReferralCodeResponse(code=code_row_code, share_url=share_url)


async def resolve_public_code(
    session: AsyncSession,
    code_str: str,
    settings: Settings,
) -> ReferralResolveResponse:
    """Resolve a public deep-link code — always 200, valid=False for unknown codes.

    Returns first name only for the referrer (T-96-06: no PII beyond first name).
    Never raises 404 — unknown code returns valid=False with welcomeBonusKopecks=0
    (anti-enumeration: no existence oracle for unauthenticated callers).

    Read-only — no flush, no commit.
    """
    code_row = await repository.get_code_by_value(session, code_str)

    # Fetch welcome bonus from config (fallback to 0 when config missing).
    config = await repository.get_config(session)
    welcome_bonus = config.referee_welcome_kopecks if config is not None else 0

    if code_row is None:
        _log.debug("referral_code_resolve_unknown", code=code_str.upper())
        return ReferralResolveResponse(
            valid=False,
            referrer_first_name=None,
            welcome_bonus_kopecks=0,
        )

    # Fetch referrer first_name via raw SQL — D-54-08: no ORM import of Client.
    # WR-02: filter deleted_at IS NULL; missing row means referrer is soft-deleted
    # → treat code as invalid (anti-oracle: still 200, valid=False).
    row = (
        await session.execute(
            text(
                "SELECT first_name FROM clients "
                "WHERE id = :cid AND deleted_at IS NULL"
            ),
            {"cid": str(code_row.client_id)},
        )
    ).mappings().one_or_none()

    if row is None:
        # Referrer is soft-deleted — code is no longer valid.
        _log.debug(
            "referral_code_resolve_deleted_referrer",
            code=code_str.upper(),
        )
        return ReferralResolveResponse(
            valid=False,
            referrer_first_name=None,
            welcome_bonus_kopecks=0,
        )

    return ReferralResolveResponse(
        valid=True,
        referrer_first_name=row["first_name"],
        welcome_bonus_kopecks=welcome_bonus,
    )


async def get_referral_summary(
    session: AsyncSession,
    client_id: UUID,
    settings: Settings,
) -> ReferralSummaryResponse:
    """Return the aggregate referral summary for the authenticated client (REFER-06).

    One round-trip for the PWA ReferralScreen: stable code + shareUrl, the
    referral-only accrued bonus sum, and the invited-friends list.

    Steps:
      1. code + shareUrl — reuse get_or_create_referral_code (idempotent mint).
      2. accruedKopecks — COALESCE/SUM fold over loyalty_ledger filtered to
         entry_type='referral_accrual' for this client (NOT total balance).
      3. invitees — raw LEFT JOIN: referral_captures → clients → loyalty_ledger,
         newest first; status='joined' iff an accrual row exists for the referrer.

    All cross-module reads use raw text() SQL (D-54-08: no ORM import of Client
    or LoyaltyLedger). UUIDs bound as str(client_id). deleted_at IS NULL on clients.
    Read-only after get_or_create_referral_code (which commits only on first mint).
    IDOR-safe: client_id is always the caller's principal (T-98-02).
    """
    # Step 1: code + shareUrl (minting on first call — idempotent).
    code_response = await get_or_create_referral_code(session, client_id, settings)
    code = code_response.code
    share_url = code_response.share_url

    # Step 2: accruedKopecks — SUM of this client's own referral_accrual rows.
    # Mirrors loyalty/service.py _sum_balance fold, filtered to referral entries.
    accrual_row = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(amount_kopecks), 0) AS accrued "
                "FROM loyalty_ledger "
                "WHERE client_id = :cid AND entry_type = 'referral_accrual'"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().one()
    accrued_kopecks = int(accrual_row["accrued"])

    # Step 3: invitees — cross-module raw-SQL join (D-54-08).
    # referral_captures WHERE referrer_client_id = me → one row per invited friend.
    # JOIN clients (deleted_at IS NULL guard — WR-02) for first_name.
    # LEFT JOIN loyalty_ledger to detect whether the referrer bonus has been credited.
    # status = 'joined' when the accrual row exists (ll.id IS NOT NULL).
    # bonusKopecks = accrual amount (0 while pending).
    rows = (
        await session.execute(
            text(
                "SELECT c.first_name AS first_name, "
                "       rc.created_at AS joined_at, "
                "       COALESCE(ll.amount_kopecks, 0) AS bonus_kopecks, "
                "       (ll.id IS NOT NULL) AS joined "
                "FROM referral_captures rc "
                "JOIN clients c ON c.id = rc.referee_client_id AND c.deleted_at IS NULL "
                "LEFT JOIN loyalty_ledger ll "
                "  ON ll.referral_capture_id = rc.id "
                "  AND ll.client_id = :cid "
                "  AND ll.entry_type = 'referral_accrual' "
                "WHERE rc.referrer_client_id = :cid "
                "ORDER BY rc.created_at DESC"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().all()

    invitees = [
        ReferralInviteeItem(
            first_name=r["first_name"],
            joined_at=r["joined_at"],
            status="joined" if r["joined"] else "pending",
            bonus_kopecks=int(r["bonus_kopecks"]),
        )
        for r in rows
    ]

    return ReferralSummaryResponse(
        code=code,
        share_url=share_url,
        accrued_kopecks=accrued_kopecks,
        invitees=invitees,
    )


async def capture_referral(
    session: AsyncSession,
    referee_principal_id: UUID,
    code_str: str,
) -> None:
    """Bind referee→referrer using the referral code string.

    Idempotent via pg_insert on_conflict_do_nothing — concurrent requests
    for the same referee produce one insert; the second gets RETURNING=None and returns
    silently (WR-01 fix: no TOCTOU 500 from IntegrityError).

    Raises:
        ReferralCodeNotFoundError (404): code_str does not match any live code, or
            the referrer client is soft-deleted (WR-02 fix).
        SelfReferralError (422): resolved referrer is the same as the referee.

    IDOR safety: referee identity comes ONLY from *referee_principal_id* (the
    require_client() principal argument), never from any request body field
    (T-96-05 mitigate).

    Caller-owns-txn: flush + commit here (D-03). Matches gym.service.update_gym_info
    discipline. Audit emitted only when RETURNING returns a new id (RETURNING-gated,
    INFRA-15 — no duplicate audit on concurrent no-op).
    """
    # Resolve the code first (raises 404 if absent).
    code_row = await repository.get_code_by_value(session, code_str)
    if code_row is None:
        raise ReferralCodeNotFoundError("referral_code_not_found")

    # Self-referral guard (T-96-08).
    if code_row.client_id == referee_principal_id:
        raise SelfReferralError("self_referral_not_allowed")

    # WR-02: reject capture against a soft-deleted referrer's code.
    referrer_alive = (
        await session.execute(
            text("SELECT 1 FROM clients WHERE id = :cid AND deleted_at IS NULL"),
            {"cid": str(code_row.client_id)},
        )
    ).fetchone()
    if referrer_alive is None:
        raise ReferralCodeNotFoundError("referral_code_not_found")

    # WR-01: idempotent insert via ON CONFLICT DO NOTHING + RETURNING.
    # Concurrent second insert for the same referee_client_id hits the DB UNIQUE
    # constraint (uq_referral_captures_referee_client_id) and returns RETURNING=None
    # → no-op path, no IntegrityError 500.
    stmt = (
        pg_insert(ReferralCapture)
        .values(
            referee_client_id=referee_principal_id,
            referrer_client_id=code_row.client_id,
            referral_code_id=code_row.id,
        )
        .on_conflict_do_nothing(index_elements=["referee_client_id"])
        .returning(ReferralCapture.id)
    )
    capture_id: UUID | None = await session.scalar(stmt)
    if capture_id is None:
        # Conflict — idempotent no-op (referee already captured, first binding wins).
        _log.info(
            "referral_capture_no_op",
            referee_client_id=str(referee_principal_id),
            msg="capture already exists — no-op",
        )
        return

    # RETURNING-gated audit emit — only on real insert (INFRA-15).
    # Payload UUID fields are str() here: JSONB serialization uses stdlib
    # json.dumps which cannot handle UUID objects; Pydantic v2 coerces str
    # back to UUID at model_validate time so ReferralCapturedPayload
    # validates correctly with string inputs.
    await audit.emit(
        session,
        "referral_captured",
        actor_user_id=None,  # client-initiated; no staff actor
        resource_type="referral",
        resource_id=capture_id,
        referee_client_id=str(referee_principal_id),
        referrer_client_id=str(code_row.client_id),
        referral_capture_id=str(capture_id),
        referral_code_id=str(code_row.id),
    )
    await session.commit()  # CR-01 fix: service owns the transactional moment
    _log.info(
        "referral_captured",
        referee_client_id=str(referee_principal_id),
        referrer_client_id=str(code_row.client_id),
        referral_capture_id=str(capture_id),
        referral_code_id=str(code_row.id),
    )


async def get_referral_config(session: AsyncSession) -> ReferralConfigResponse:
    """Return singleton referral config. 404 via ReferralConfigNotFoundError if seed missing."""
    config = await repository.get_config(session)
    if config is None:
        raise ReferralConfigNotFoundError("referral_config_not_found")
    return ReferralConfigResponse(
        referrer_bonus_kopecks=config.referrer_bonus_kopecks,
        referee_welcome_kopecks=config.referee_welcome_kopecks,
    )


async def update_referral_config(
    session: AsyncSession,
    actor: CurrentUser,
    data: ReferralConfigUpdateRequest,
) -> ReferralConfigResponse:
    """Upsert the singleton referral config. Caller-owns-txn: flush + commit here (D-03).

    Matches gym.service.update_gym_info discipline: singleton write owns the
    transactional moment. No audit event this phase (referral_config_updated
    is explicitly deferred per CONTEXT).

    actor is accepted for future audit emission — not used in v2.6.
    """
    _ = actor  # reserved for future audit emit
    config = await repository.upsert_config(session, data)
    await session.flush()
    await session.commit()
    return ReferralConfigResponse(
        referrer_bonus_kopecks=config.referrer_bonus_kopecks,
        referee_welcome_kopecks=config.referee_welcome_kopecks,
    )
