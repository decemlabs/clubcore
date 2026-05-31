"""Promo code validation service (Phase 999.4 D-06/D-07/D-08/D-09).

Core validate_promo_code function: checks activity window, is_active flag,
applicability, usage limits, then computes and returns the authoritative
discounted amount.

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

No session.commit() — read-only path (D-32-10/D-49-19 caller-owns-txn).
"""

from __future__ import annotations

import structlog
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.modules.promo_codes.models import PromoRedemption


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
) -> tuple[int, int, str]:
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
    tuple[discount_kopecks, new_amount_kopecks, discount_type]
        discount_kopecks:    computed discount in integer kopecks.
        new_amount_kopecks:  price − discount (never < 0).
        discount_type:       'percentage' | 'fixed'.

    Raises
    ------
    PromoNotFoundError    — code not found or soft-deleted.
    PromoInactiveError    — is_active=False.
    PromoNotApplicableError — applicable_to mismatch.
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
    return discount_kopecks, new_amount_kopecks, discount_type


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
    if kind == "membership":
        table = "membership_plans"
    else:
        table = "pt_package_plans"

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


_log = structlog.get_logger("modules.promo_codes.service")


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
        Discount actually granted (plan_price − row.amount_kopecks at record time).
    """
    # Re-check max_uses cap at record time (T-999.4-09 belt-and-suspenders).
    promo_row = (
        await session.execute(
            text("SELECT max_uses FROM promo_codes WHERE id = :id AND deleted_at IS NULL"),
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


__all__ = (
    "validate_promo_code",
    "record_promo_redemption",
    "PromoNotFoundError",
    "PromoInactiveError",
    "PromoExpiredError",
    "PromoNotYetActiveError",
    "PromoNotApplicableError",
    "PromoUsedUpError",
)
