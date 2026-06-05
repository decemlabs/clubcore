"""Autopay charge service — Phase 84 APAY-01/02/03.

`_charge_expiring_autopay_memberships` is the caller-owns-txn helper invoked
by the `charge_expiring_autopay` ARQ cron (app/workers/scheduled/).

Architecture:
- Eligibility: raw SQL joining memberships → membership_plans → clients →
  client_payment_methods (alive + autopay_enabled + consent_recorded_at IS NOT NULL).
- Claim-before-charge: INSERT autopay_charges ON CONFLICT (membership_id, period_end)
  DO NOTHING — the DB-level double-charge guard (T-84-01).
- Deterministic idempotency_key: sha256 hex of "{membership_id}:{period_end}" — the
  belt-and-suspenders provider-level double-charge guard against crash-between-claim-
  and-provider (T-84-02).
- On ok: insert online_payments row (confirmation_type='autopay') so the existing
  payment.succeeded webhook can activate the renewal (D-06 webhook-locked activation).
- On non-ok: NO online_payments row (yookassa_payment_id is NOT NULL — no row without
  a payment id). UPDATE claim status='failed'. Collect declined claim id for post-commit
  failure notification enqueue (Plan 03).
- NEVER commits: the calling cron fn owns the transaction (# noqa: SVC001 discipline).

Cross-module ORM access: uses Base.metadata.tables[...] for non-autopay-charges
tables (D-54-08 — never import another module's ORM).

ФЗ-376 compliance: the eligibility JOIN requires consent_recorded_at IS NOT NULL.
A membership without recorded consent is NEVER charged regardless of any other flag.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import get_yookassa_client_provider
from app.integrations.yookassa.receipt import (
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)
from app.integrations.yookassa.settings import YooKassaSettings

_log = structlog.get_logger("modules.autopay_charges.service")

_TZ_MOSCOW = ZoneInfo("Europe/Moscow")

# Window default (APAY-01 configurable). Tests may pass an explicit window_days.
_DEFAULT_WINDOW_DAYS = 3


def _autopay_charges_table() -> Any:
    """Return the autopay_charges SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["autopay_charges"]


def _online_payments_table() -> Any:
    """Return the online_payments SA Table via metadata — no cross-module ORM import."""
    from app.core.database import Base

    return Base.metadata.tables["online_payments"]


def _idempotency_key(membership_id: UUID, period_end: date) -> str:
    """Deterministic sha256 hex key for (membership_id, period_end).

    T-84-02: stable across process restarts — if the cron crashes between the
    claim INSERT and the YooKassa call, the next tick derives the SAME key so
    the provider deduplicates the second attempt.

    The key is ASCII-safe (hex digits only) and opaque to ЮKassa. UUID form is
    not required — the adapter accepts any str (D-48-11 / D-49-08).
    """
    raw = f"{membership_id}:{period_end.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _charge_expiring_autopay_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    *,
    today: date | None = None,
    window_days: int = _DEFAULT_WINDOW_DAYS,
) -> tuple[int, list[UUID]]:
    """Find eligible expiring memberships and initiate off-session autopay charges.

    Called ONLY by `app.workers.scheduled.charge_expiring_autopay:charge_expiring_autopay`.
    The cron fn owns the transaction and calls `await session.commit()` after this returns.
    This function NEVER calls session.commit() (# noqa: SVC001 caller-owns-txn).

    ФЗ-376: consent_recorded_at IS NOT NULL is enforced at the eligibility JOIN level.
    A missing consent row is NEVER charged, regardless of autopay_enabled or any other
    flag.

    D-06 (webhook-locked activation): this function initiates the charge and creates the
    online_payments row so the existing payment.succeeded webhook can activate the renewal.
    It NEVER creates or extends a membership directly.

    Args:
        session: AsyncSession owned by the calling cron fn.
        today: Reference date (defaults to Europe/Moscow today). Tests pass explicit value.
        window_days: Memberships expiring in [today, today+window_days] are candidates.

    Returns:
        (count, declined_charge_ids): count of attempted charges (ok + failed),
        declined_charge_ids holds autopay_charges.id for each non-ok provider response.
        The cron enqueues dispatch_autopay_failure_notification(autopay_charge_id=id)
        for each id in this list, AFTER commit (post-commit discipline).
    """
    from datetime import datetime

    if today is None:
        today = datetime.now(_TZ_MOSCOW).date()

    window_end = today + timedelta(days=window_days)

    # Eligibility query — raw SQL (D-54-08: no cross-module ORM import).
    # Joins:
    #   m (memberships) → mp (membership_plans) for price_kopecks
    #   m → c (clients) for receipt contact (email preferred, phone fallback)
    #   m → cpm (client_payment_methods) alive card with consent + autopay on
    # Filters:
    #   m.status = 'active' AND m.end_date IN [today, window_end]
    #   cpm.unlinked_at IS NULL (alive card)
    #   cpm.autopay_enabled = true
    #   cpm.consent_recorded_at IS NOT NULL  ← ФЗ-376
    # Skip conditions (NOT EXISTS):
    #   Already-renewed: a membership covering the next period already exists
    #     (end_date > m.end_date in memberships for the same client/plan)
    #   Already-succeeded: an autopay_charges row with status='succeeded' for this period
    # Note: status='failed' rows are NOT skipped by the NOT EXISTS guard — they are
    #   already skipped by the ON CONFLICT DO NOTHING claim INSERT below (the claim row
    #   already exists). The plan says "next tick skips failed periods" — the CONFLICT
    #   is the mechanism.
    eligibility_sql = text(
        """
        SELECT
            m.id            AS membership_id,
            m.end_date      AS period_end,
            m.client_id     AS client_id,
            mp.id           AS plan_id,
            mp.price_kopecks AS amount_kopecks,
            mp.name         AS plan_name,
            c.email         AS client_email,
            c.phone         AS client_phone,
            cpm.yookassa_method_id AS yookassa_method_id
        FROM memberships m
        JOIN membership_plans mp ON mp.id = m.plan_id
        JOIN clients c ON c.id = m.client_id
        JOIN client_payment_methods cpm
            ON cpm.client_id = m.client_id
            AND cpm.unlinked_at IS NULL
            AND cpm.autopay_enabled = true
            AND cpm.consent_recorded_at IS NOT NULL
        WHERE
            m.status = 'active'
            AND m.end_date >= :today
            AND m.end_date <= :window_end
            AND NOT EXISTS (
                -- Already-renewed: a membership covering the next period exists
                SELECT 1 FROM memberships m2
                WHERE m2.client_id = m.client_id
                  AND m2.plan_id = m.plan_id
                  AND m2.start_date > m.end_date
                  AND m2.status IN ('active', 'frozen')
            )
        """
        # Note: already-failed autopay_charges rows block re-charge via the
        # ON CONFLICT DO NOTHING claim INSERT — no extra NOT EXISTS needed here.
    )
    rows = (
        (await session.execute(eligibility_sql, {"today": today, "window_end": window_end}))
        .mappings()
        .all()
    )

    yookassa_settings = YooKassaSettings()
    provider = get_yookassa_client_provider()
    yookassa_client = await provider()

    count = 0
    declined_charge_ids: list[UUID] = []

    for row in rows:
        membership_id: UUID = row["membership_id"]
        period_end: date = row["period_end"]
        client_id: UUID = row["client_id"]
        plan_id: UUID = row["plan_id"]
        amount_kopecks: int = row["amount_kopecks"]
        plan_name: str = row["plan_name"]
        client_email: str | None = row["client_email"]
        client_phone: str = row["client_phone"]
        yookassa_method_id: str = row["yookassa_method_id"]

        # Derive deterministic idempotency key (T-84-02).
        idem_key = _idempotency_key(membership_id, period_end)

        # CLAIM-BEFORE-CHARGE: INSERT ON CONFLICT DO NOTHING (T-84-01 double-charge guard).
        # RETURNING id gives us the newly-inserted claim row id.
        # rowcount == 0 means the period is already claimed (pending or failed) → skip.
        claim_result = await session.execute(
            text(
                "INSERT INTO autopay_charges "
                "(id, membership_id, period_end, status, amount_kopecks, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :membership_id, :period_end, 'pending', "
                ":amount_kopecks, now(), now()) "
                "ON CONFLICT (membership_id, period_end) DO NOTHING "
                "RETURNING id"
            ),
            {
                "membership_id": str(membership_id),
                "period_end": period_end,
                "amount_kopecks": amount_kopecks,
            },
        )
        claim_row = claim_result.fetchone()
        if claim_row is None:
            # Conflict: this period is already claimed. Skip.
            _log.info(
                "autopay_charge_skipped_already_claimed",
                membership_id=str(membership_id),
                period_end=str(period_end),
            )
            continue

        claim_id: UUID = claim_row[0]

        # Build 54-ФЗ receipt item.
        # Plan name truncated to 128 chars (build_receipt_item guard).
        description = f"Автопродление: {plan_name}"[:128]
        receipt_items = [
            build_receipt_item(
                description=description,
                amount_kopecks=amount_kopecks,
                payment_subject=PaymentSubject.SERVICE,
                payment_mode=PaymentMode.FULL_PREPAYMENT,
                vat_code=VatCode(int(yookassa_settings.default_vat_code)),
            )
        ]

        # Off-session charge via saved card.
        # T-84-11 PII discipline: yookassa_method_id used ONLY here, never logged.
        result = await yookassa_client.create_payment(
            amount_kopecks=amount_kopecks,
            description=description,
            receipt_items=receipt_items,
            customer_email=client_email,
            customer_phone=(client_phone if client_email is None else None),
            idempotency_key=idem_key,
            payment_method_id=yookassa_method_id,
        )

        if result.classification == "ok":
            # Success path: create the online_payments row so the payment.succeeded
            # webhook can discover it and activate the renewal (D-06 webhook-locked).
            assert result.payment_id is not None  # guaranteed by classification='ok'
            assert result.amount_kopecks is not None

            audit_correlation_id = uuid4()
            online_payment_id = uuid4()

            # Insert online_payments row via raw SQL (D-54-08: no cross-module ORM import).
            # confirmation_type='autopay' is the webhook discriminator (Task 3 / Plan 02
            # architecture note) — the webhook reads this value to choose:
            #   method='autopay' (charge-ledger) + kind='autopay_charge_succeeded' (notification).
            await session.execute(
                text(
                    "INSERT INTO online_payments "
                    "(id, client_id, membership_plan_id, pt_package_plan_id, "
                    " yookassa_payment_id, idempotency_key, amount_kopecks, "
                    " status, confirmation_url, confirmation_type, "
                    " created_by_user_id, audit_correlation_id, save_payment_method, "
                    " initiated_at) "
                    "VALUES "
                    "(:id, :client_id, :membership_plan_id, NULL, "
                    " :yookassa_payment_id, :idempotency_key, :amount_kopecks, "
                    " 'pending', NULL, 'autopay', "
                    " NULL, :audit_correlation_id, false, "
                    " now())"
                ),
                {
                    "id": str(online_payment_id),
                    "client_id": str(client_id),
                    "membership_plan_id": str(plan_id),
                    "yookassa_payment_id": result.payment_id,
                    "idempotency_key": idem_key,
                    "amount_kopecks": result.amount_kopecks,
                    "audit_correlation_id": str(audit_correlation_id),
                },
            )

            # UPDATE claim row: link to online_payments row + store yookassa_payment_id.
            # status stays 'pending' — the webhook flips it to 'succeeded'.
            await session.execute(
                text(
                    "UPDATE autopay_charges "
                    "SET online_payment_id = :online_payment_id, "
                    "    yookassa_payment_id = :yookassa_payment_id, "
                    "    updated_at = now() "
                    "WHERE id = :claim_id"
                ),
                {
                    "online_payment_id": str(online_payment_id),
                    "yookassa_payment_id": result.payment_id,
                    "claim_id": str(claim_id),
                },
            )

            await audit.emit(
                session,
                "autopay_charge_initiated",  # LITERAL (INFRA-11 AST gate)
                actor_user_id=None,  # system-driven cron
                resource_type="autopay",  # LITERAL
                resource_id=claim_id,
                # UUIDs are cast to str for JSONB-serialisability (Pydantic validates UUID
                # from str — the model field is UUID so model_validate accepts both).
                membership_id=str(membership_id),
                amount_kopecks=amount_kopecks,
                period_end=period_end.isoformat(),
            )

            _log.info(
                "autopay_charge_initiated",
                membership_id=str(membership_id),
                period_end=str(period_end),
                claim_id=str(claim_id),
                online_payment_id=str(online_payment_id),
            )
            count += 1

        else:
            # Failure path: NO online_payments row (yookassa_payment_id is NOT NULL —
            # a provider decline has no payment id, so we cannot insert the row).
            # UPDATE claim status='failed' so the next tick does NOT retry (T-84-12).
            failure_reason = result.classification
            if result.error_code:
                failure_reason = f"{result.classification}:{result.error_code}"

            await session.execute(
                text(
                    "UPDATE autopay_charges "
                    "SET status = 'failed', "
                    "    failure_reason = :failure_reason, "
                    "    updated_at = now() "
                    "WHERE id = :claim_id"
                ),
                {
                    "failure_reason": failure_reason,
                    "claim_id": str(claim_id),
                },
            )

            await audit.emit(
                session,
                "autopay_charge_failed",  # LITERAL (INFRA-11 AST gate)
                actor_user_id=None,  # system-driven cron
                resource_type="autopay",  # LITERAL
                resource_id=claim_id,
                # UUIDs cast to str for JSONB-serialisability (JSONB payload).
                membership_id=str(membership_id),
                amount_kopecks=amount_kopecks,
                period_end=period_end.isoformat(),
                failure_reason=failure_reason,
            )

            _log.info(
                "autopay_charge_failed",
                membership_id=str(membership_id),
                period_end=str(period_end),
                claim_id=str(claim_id),
                failure_reason=failure_reason,
            )

            # Collect the claim id for the cron's post-commit failure notification enqueue.
            # T-84-12b: the failure notification is keyed on autopay_charges.id (the always-
            # present claim anchor) — NOT online_payment_id (which doesn't exist on decline).
            declined_charge_ids.append(claim_id)
            count += 1

    return count, declined_charge_ids
