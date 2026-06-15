"""Promo code validation + admin CRUD service (Phase 999.4 + Phase 113).

Core validate_promo_code function: checks activity window, is_active flag,
applicability, usage limits, then computes and returns the authoritative
discounted amount.

Phase 113 admin CRUD (PROMO-01/PROMO-02):
  - create_promo_code — UPPER-normalize code, insert, commit
  - update_promo_code — load alive or 404, apply partial patch, commit
  - deactivate_promo_code — load alive or 404, set is_active=False, commit

Error discipline: each failure reason raises a distinct ValidationAppError subclass
with a stable `code` attribute (D-09 — per-reason error codes for the client PWA
to map to localized messages). No try/except — errors bubble to _app_error_handler.

Money discipline: all amounts are integer kopecks (BigInteger).
Percentage discount uses integer floor division only — no float, no Decimal.
discount_value for 'percentage' is stored as percent*100 integer
  (10% → 1000, per D-999.4-01-C).

Plan price is read via raw SQL text() SELECT (D-54-08 cross-module precedent;
no ORM import of MembershipPlan / PtPackagePlan from foreign modules).
Usage counts are raw SQL text() COUNT queries on promo_redemptions.

No session.commit() in read-only paths (D-32-10/D-49-19 caller-owns-txn).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy import exc as sa_exc
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ValidationAppError
from app.modules.promo_codes.models import PromoRedemption

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.promo_codes.models import PromoCode
    from app.modules.promo_codes.schemas import (
        PromoCodeCreateRequest,
        PromoCodeUpdateRequest,
    )

_log = structlog.get_logger("modules.promo_codes.service")


# ---------------------------------------------------------------------------
# D-09 distinct per-reason error classes (stable code= attribute)
# ---------------------------------------------------------------------------


class PromoNotFoundError(ValidationAppError):
    """Promo code not found (unknown code or soft-deleted)."""

    code = "not_found"
    status_code = 422


class PromoInactiveError(ValidationAppError):
    """Promo code is_active=False."""

    code = "inactive"
    status_code = 422


class PromoExpiredError(ValidationAppError):
    """Promo code valid_until is in the past."""

    code = "expired"
    status_code = 422


class PromoNotYetActiveError(ValidationAppError):
    """Promo code valid_from is in the future."""

    code = "not_yet_active"
    status_code = 422


class PromoNotApplicableError(ValidationAppError):
    """Promo code's applicable_to does not match the requested product kind."""

    code = "not_applicable"
    status_code = 422


class PromoUsedUpError(ValidationAppError):
    """Promo code usage limit reached (global max_uses or per_client per_client_limit)."""

    code = "used_up"
    status_code = 422


# ---------------------------------------------------------------------------
# Phase 113 — admin CRUD error classes
# ---------------------------------------------------------------------------


class PromoCodeNotFoundError(AppError):
    """Admin CRUD: promo code not found or soft-deleted (PROMO-01)."""

    code = "promo_code_not_found"
    status_code = 404


class PromoCodeAlreadyExistsError(AppError):
    """Admin CRUD: alive promo code with same UPPER(code) already exists (PROMO-01)."""

    code = "promo_code_already_exists"
    status_code = 409


class PromoCodeValidationError(ValidationAppError):
    """Admin CRUD: generic promo code validation failure."""

    code = "promo_code_validation_error"
    status_code = 422


# ---------------------------------------------------------------------------
# Kind mapping: PWA shorthand → DB applicable_to value
# ---------------------------------------------------------------------------

_KIND_MAP: dict[str, str] = {
    "sub": "membership",
    "pt": "pt_package",
}


# ---------------------------------------------------------------------------
# validate_promo_code
# ---------------------------------------------------------------------------


async def validate_promo_code(
    session: AsyncSession,
    *,
    code: str,
    kind: str,
    plan_id: UUID,
    client_id: UUID,
) -> tuple[int, int, str, UUID]:
    """Validate a promo code and return authoritative discounted amounts (D-06/D-09).

    Parameters
    ----------
    session:
        Active async SQLAlchemy session (read-only; no commit).
    code:
        Raw promo code string (normalized to UPPER internally).
    kind:
        Product kind from the client: 'sub' (membership) or 'pt' (pt_package).
    plan_id:
        UUID of the membership_plans or pt_package_plans row.
    client_id:
        UUID of the authenticated client (for per_client_limit check).

    Returns
    -------
    tuple[discount_kopecks, new_amount_kopecks, discount_type, promo_id]
        discount_kopecks:    computed discount in integer kopecks.
        new_amount_kopecks:  price - discount (never < 0; zero raises PromoNotApplicableError).
        discount_type:       'percentage' | 'fixed'.
        promo_id:            UUID of the PromoCode row (CR-02 — eliminates second lookup).

    Raises
    ------
    PromoNotFoundError    — code not found or soft-deleted.
    PromoInactiveError    — is_active=False.
    PromoNotApplicableError — applicable_to mismatch or zero final amount (100% discount).
    PromoExpiredError     — now > valid_until.
    PromoNotYetActiveError — now < valid_from.
    PromoUsedUpError      — max_uses or per_client_limit reached.
    """
    # Step 1: Normalize code and fetch the alive PromoCode row.
    upper_code = code.upper()
    promo_row = (
        await session.execute(
            text(
                "SELECT id, discount_type, discount_value, max_uses, per_client_limit, "
                "valid_from, valid_until, is_active, applicable_to "
                "FROM promo_codes "
                "WHERE upper(code) = :code AND deleted_at IS NULL"
            ),
            {"code": upper_code},
        )
    ).mappings().one_or_none()

    if promo_row is None:
        raise PromoNotFoundError("not_found")

    promo_id: UUID = promo_row["id"]
    is_active: bool = bool(promo_row["is_active"])
    discount_type: str = str(promo_row["discount_type"])
    discount_value: int = int(promo_row["discount_value"])
    max_uses: int | None = promo_row["max_uses"]
    per_client_limit: int | None = promo_row["per_client_limit"]
    valid_from: datetime | None = promo_row["valid_from"]
    valid_until: datetime | None = promo_row["valid_until"]
    applicable_to: str | None = promo_row["applicable_to"]

    # Step 2: is_active check.
    if not is_active:
        raise PromoInactiveError("inactive")

    # Step 3: Applicability check — map client kind to DB applicable_to value.
    mapped_kind = _KIND_MAP.get(kind, kind)  # 'sub'→'membership', 'pt'→'pt_package'
    if applicable_to is not None and applicable_to != mapped_kind:
        raise PromoNotApplicableError("not_applicable")

    # Step 4: Time window check.
    now = datetime.now(UTC)
    if valid_from is not None:
        # valid_from may be timezone-aware or naive depending on DB driver.
        # Ensure we compare TZ-aware with TZ-aware.
        _vf = valid_from if valid_from.tzinfo is not None else valid_from.replace(tzinfo=UTC)
        if now < _vf:
            raise PromoNotYetActiveError("not_yet_active")
    if valid_until is not None:
        _vu = valid_until if valid_until.tzinfo is not None else valid_until.replace(tzinfo=UTC)
        if now > _vu:
            raise PromoExpiredError("expired")

    # Step 5: Usage limit checks (raw SQL COUNT on promo_redemptions).
    if max_uses is not None:
        global_count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                    "WHERE promo_code_id = :promo_id"
                ),
                {"promo_id": str(promo_id)},
            )
        ).mappings().one()
        global_count = int(global_count_row["cnt"])
        if global_count >= max_uses:
            raise PromoUsedUpError("used_up")

    if per_client_limit is not None:
        client_count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                    "WHERE promo_code_id = :promo_id AND client_id = :client_id"
                ),
                {"promo_id": str(promo_id), "client_id": str(client_id)},
            )
        ).mappings().one()
        client_count = int(client_count_row["cnt"])
        if client_count >= per_client_limit:
            raise PromoUsedUpError("used_up")

    # Step 6: Read plan price_kopecks via raw SQL (D-54-08 — no cross-module ORM import).
    price_kopecks = await _read_plan_price(session, kind=mapped_kind, plan_id=plan_id)

    # Step 7: Compute discount (integer kopecks only — no float, no Decimal).
    if discount_type == "percentage":
        # discount_value is percent*100 (10% → 1000).
        # discount = floor(price * percent_hundredths / 100 / 100)
        # = (price * discount_value) // 100 // 100
        discount_kopecks = (price_kopecks * discount_value) // 100 // 100
    else:  # 'fixed'
        # Caps at plan price — newAmount never negative.
        discount_kopecks = min(discount_value, price_kopecks)

    new_amount_kopecks = max(0, price_kopecks - discount_kopecks)

    # CR-03 fix: reject a zero final amount before it reaches ЮKassa.
    # ЮKassa requires amount > 0; a 100% discount via a fixed code >= plan price
    # would produce 0 ₽ and be rejected by ЮKassa at payment creation time.
    # Raise PromoNotApplicableError so the client sees a clear per-reason error
    # (code='not_applicable') instead of a downstream ЮKassa validation failure.
    if new_amount_kopecks <= 0:
        raise PromoNotApplicableError("promo_results_in_zero_amount")

    return discount_kopecks, new_amount_kopecks, discount_type, promo_id


async def _read_plan_price(
    session: AsyncSession,
    *,
    kind: str,
    plan_id: UUID,
) -> int:
    """Read price_kopecks for a membership_plans or pt_package_plans row (D-54-08).

    Raw SQL text() SELECT — no ORM import of foreign-module models.
    Raises PromoNotFoundError if the plan row is absent or soft-deleted.
    """
    table = "membership_plans" if kind == "membership" else "pt_package_plans"

    row = (
        await session.execute(
            text(
                f"SELECT price_kopecks FROM {table} "  # noqa: S608 — table is internal, not user input
                "WHERE id = :id AND deleted_at IS NULL"
            ),
            {"id": str(plan_id)},
        )
    ).mappings().one_or_none()

    if row is None:
        raise PromoNotFoundError(f"{table}_not_found")

    return int(row["price_kopecks"])


# ---------------------------------------------------------------------------
# record_promo_redemption
# ---------------------------------------------------------------------------


async def record_promo_redemption(
    session: AsyncSession,
    *,
    promo_code_id: UUID,
    client_id: UUID,
    online_payment_id: UUID,
    discount_kopecks: int,
) -> None:
    """Record a PromoRedemption ledger row on successful payment (D-07).

    Idempotent: uses ``on_conflict_do_nothing`` on the UNIQUE(online_payment_id)
    constraint (``uq_promo_redemptions_online_payment_id``) so a webhook replay
    does NOT double-insert.

    Race-safety belt-and-suspenders: re-checks ``max_uses`` at record time.
    If the global cap is already met when we arrive here (e.g. a concurrent
    checkout validated against an in-flight count), we log and return WITHOUT
    raising — the discount was already granted at checkout validation time and
    there is no safe way to undo the ЮKassa redirect.  The residual over-grant
    under extreme concurrency is bounded to at most 1-per-payment and is
    accepted for single-gym scale (T-999.4-09).

    ``session.flush()`` only — caller (webhook handler) owns the commit.

    Parameters
    ----------
    session:
        Active async SQLAlchemy session (caller owns txn).
    promo_code_id:
        UUID of the PromoCode row (read from online_payments.promo_code_id).
    client_id:
        UUID of the authenticated client (from online_payments.client_id).
    online_payment_id:
        UUID of the OnlinePayment row (from online_payments.id).
    discount_kopecks:
        Discount actually granted (plan_price - row.amount_kopecks at record time).
    """
    # CR-01 fix: acquire row lock on the promo_codes row BEFORE the COUNT check so
    # concurrent webhook handlers serialise on this promo code and cannot both pass
    # the cap check for the same promo code (T-999.4-09 race-safe enforcement).
    # Also reads per_client_limit for WR-01 re-check below.
    promo_row = (
        await session.execute(
            text(
                "SELECT max_uses, per_client_limit FROM promo_codes "
                "WHERE id = :id AND deleted_at IS NULL FOR UPDATE"
            ),
            {"id": str(promo_code_id)},
        )
    ).mappings().one_or_none()

    if promo_row is None:
        # PromoCode was soft-deleted between checkout and succeeded.
        # Log and skip — do not raise inside the webhook path.
        _log.warning(
            "record_promo_redemption_promo_not_found",
            promo_code_id=str(promo_code_id),
            online_payment_id=str(online_payment_id),
        )
        return

    max_uses = promo_row["max_uses"]
    if max_uses is not None:
        count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                    "WHERE promo_code_id = :promo_id"
                ),
                {"promo_id": str(promo_code_id)},
            )
        ).mappings().one()
        global_count = int(count_row["cnt"])
        if global_count >= max_uses:
            _log.warning(
                "record_promo_redemption_cap_already_met",
                promo_code_id=str(promo_code_id),
                online_payment_id=str(online_payment_id),
                global_count=global_count,
                max_uses=max_uses,
            )
            return

    # WR-01 fix: also re-check per_client_limit at record time (not just max_uses).
    # Concurrent per_client_limit=1 redemptions for the same client can both pass
    # validate_promo_code simultaneously; this re-check (serialised by the FOR UPDATE
    # lock above) prevents the second redemption row from being written.
    per_client_limit = promo_row["per_client_limit"]
    if per_client_limit is not None:
        client_count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                    "WHERE promo_code_id = :promo_id AND client_id = :client_id"
                ),
                {"promo_id": str(promo_code_id), "client_id": str(client_id)},
            )
        ).mappings().one()
        client_count = int(client_count_row["cnt"])
        if client_count >= per_client_limit:
            _log.warning(
                "record_promo_redemption_per_client_cap_met",
                promo_code_id=str(promo_code_id),
                online_payment_id=str(online_payment_id),
                client_id=str(client_id),
                client_count=client_count,
                per_client_limit=per_client_limit,
            )
            return

    # Insert idempotently — on_conflict_do_nothing on UNIQUE(online_payment_id).
    stmt = (
        pg_insert(PromoRedemption)
        .values(
            promo_code_id=promo_code_id,
            client_id=client_id,
            online_payment_id=online_payment_id,
            discount_kopecks=discount_kopecks,
        )
        .on_conflict_do_nothing(constraint="uq_promo_redemptions_online_payment_id")
    )
    await session.execute(stmt)
    await session.flush()
    _log.info(
        "record_promo_redemption",
        promo_code_id=str(promo_code_id),
        online_payment_id=str(online_payment_id),
        discount_kopecks=discount_kopecks,
    )


# ---------------------------------------------------------------------------
# Phase 113 — admin CRUD service functions
# ---------------------------------------------------------------------------


async def create_promo_code(
    session: AsyncSession,
    actor: User,
    payload: PromoCodeCreateRequest,
) -> PromoCode:
    """Create a promo code (PROMO-01).

    Normalizes code to UPPER (strip + upper) before persistence.
    Raises PromoCodeAlreadyExistsError on alive-uniqueness constraint violation
    (uq_promo_codes_code_alive partial UNIQUE on upper(code) WHERE deleted_at IS NULL).

    Returns the inserted PromoCode ORM instance.
    """
    from app.modules.promo_codes import repository

    normalized_code = payload.code.strip().upper()
    try:
        promo = await repository.insert_promo_code(
            session,
            code=normalized_code,
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            max_uses=payload.max_uses,
            per_client_limit=payload.per_client_limit,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            applicable_to=payload.applicable_to,
            description=payload.description,
        )
        await session.commit()
        _log.info(
            "promo_code_created",
            code=normalized_code,
            actor_id=str(actor.id),
        )
        return promo
    except sa_exc.IntegrityError as exc:
        await session.rollback()
        # The partial unique index uq_promo_codes_code_alive fires on duplicate alive code
        if "uq_promo_codes_code_alive" in str(exc.orig):
            raise PromoCodeAlreadyExistsError(
                f"A promo code with code '{normalized_code}' already exists"
            ) from exc
        raise


async def update_promo_code(
    session: AsyncSession,
    actor: User,
    promo_id: UUID,
    payload: PromoCodeUpdateRequest,
) -> PromoCode:
    """Partially edit an alive promo code (PROMO-01).

    Only fields present in the request (exclude_unset) are applied.
    Code is UPPER-normalized if provided. Raises PromoCodeNotFoundError on
    missing/soft-deleted promo, PromoCodeAlreadyExistsError on alive-uniqueness conflict.

    Returns the updated PromoCode ORM instance.
    """
    from app.modules.promo_codes import repository

    promo = await repository.get_alive(session, promo_id)
    if promo is None:
        raise PromoCodeNotFoundError(f"Promo code {promo_id} not found")

    # Build the update dict from only the fields the caller explicitly set
    raw_values = payload.model_dump(exclude_unset=True)
    if not raw_values:
        return promo  # no-op PATCH

    # Normalize code if present
    if "code" in raw_values and raw_values["code"] is not None:
        raw_values["code"] = str(raw_values["code"]).strip().upper()

    try:
        await repository.update_promo_code(session, promo, values=raw_values)
        await session.commit()
        _log.info(
            "promo_code_updated",
            promo_id=str(promo_id),
            fields=list(raw_values.keys()),
            actor_id=str(actor.id),
        )
        return promo
    except sa_exc.IntegrityError as exc:
        await session.rollback()
        if "uq_promo_codes_code_alive" in str(exc.orig):
            raise PromoCodeAlreadyExistsError(
                "A promo code with that code already exists"
            ) from exc
        raise


async def deactivate_promo_code(
    session: AsyncSession,
    actor: User,
    promo_id: UUID,
) -> None:
    """Deactivate (soft - sets is_active=False) an alive promo code (PROMO-01).

    Raises PromoCodeNotFoundError if the code is missing or already soft-deleted.
    """
    from app.modules.promo_codes import repository

    promo = await repository.get_alive(session, promo_id)
    if promo is None:
        raise PromoCodeNotFoundError(f"Promo code {promo_id} not found")

    await repository.deactivate_promo_code(session, promo_id=promo_id)
    await session.commit()
    _log.info(
        "promo_code_deactivated",
        promo_id=str(promo_id),
        actor_id=str(actor.id),
    )


__all__ = (
    "PromoCodeAlreadyExistsError",
    "PromoCodeNotFoundError",
    "PromoCodeValidationError",
    "PromoExpiredError",
    "PromoInactiveError",
    "PromoNotApplicableError",
    "PromoNotFoundError",
    "PromoNotYetActiveError",
    "PromoUsedUpError",
    "create_promo_code",
    "deactivate_promo_code",
    "record_promo_redemption",
    "update_promo_code",
    "validate_promo_code",
)
