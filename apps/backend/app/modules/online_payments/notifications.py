"""Locked Russian DM templates for Phase 52 online-payment notifications (NOT-01).

4 online-payment-event templates. Single template per kind (D-52-06 —
NO A/B variants; the payment surface is one-shot per event).

Owner sign-off (D-52-06 lineage / Phase 52 plan 52-01 close) recorded in
``.planning/phases/52-cross-channel-notifications-v1-6-carry-out/52-01-SUMMARY.md``
before plan close. Modifying these strings post-merge requires a NEW
owner sign-off entry.

Module location (D-52-06 mirror of D-39-02): lives in
``app/modules/online_payments/`` because payment DM copy is owned by
the online_payments domain.

Placeholder substitution (D-39-04 mirror): renderers use
``str.format(**kwargs)`` so any unknown placeholder key raises
``KeyError`` loud at test time — f-strings would silently shadow the
bug.

Anti-oracle hygiene (D-52-08 / C-12):
- Client-facing templates (ONLINE_PAYMENT_SUCCEEDED_DM,
  ONLINE_PAYMENT_REFUNDED_DM) carry NO failure-cause disclosure.
- Owner-alert templates (ONLINE_PAYMENT_CANCELED_DM,
  FISCAL_RECEIPT_FAILED_DM) carry operational identifiers +
  failure reasons so the operator can act.
"""

from __future__ import annotations

from typing import Final

# === Phase 52 NOT-01 — locked Russian DM copy. Owner sign-off recorded in 52-01-SUMMARY.md. ===
# RUF001/E501/RUF003 per-line: Cyrillic letters + locked single-line format are intentional
# (Russian-only product per PROJECT.md i18n locked decision; reviewers diff exact text).

ONLINE_PAYMENT_SUCCEEDED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Оплата на сумму {amount_rub} успешно получена. Ваш абонемент / пакет тренировок активирован. Ждём вас в зале!"  # noqa: E501  # OWNER-COPY-LOCK signed-off 2026-05-23 — see 52-01-SUMMARY.md
)

ONLINE_PAYMENT_REFUNDED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Возврат на сумму {amount_rub} успешно обработан. Средства поступят на ваш счёт в течение нескольких рабочих дней. Если у вас есть вопросы — обратитесь к администратору."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off 2026-05-23 — see 52-01-SUMMARY.md
)

ONLINE_PAYMENT_CANCELED_DM: Final[str] = (
    "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Платёж отменён. payment_id: {payment_id}, yookassa_payment_id: {yookassa_payment_id}. Требуется проверка."  # noqa: E501  # OWNER-COPY-LOCK signed-off 2026-05-23 — see 52-01-SUMMARY.md  # OWNER-ALERT only (NOT-05) — NO client DM
)

FISCAL_RECEIPT_FAILED_DM: Final[str] = (
    "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Ошибка формирования фискального чека. payment_id: {payment_id}, причина: {failure_reason}. Требуется ручная проверка в ЮKassa."  # noqa: E501  # OWNER-COPY-LOCK signed-off 2026-05-23 — see 52-01-SUMMARY.md  # OWNER-ALERT only (NOT-04)
)


def render_online_payment_succeeded_dm(
    *,
    client_name: str,
    amount_rub: str,
) -> str:
    """Render the locked payment-succeeded DM via ``str.format`` (unknown keys raise KeyError)."""
    return ONLINE_PAYMENT_SUCCEEDED_DM.format(
        client_name=client_name,
        amount_rub=amount_rub,
    )


def render_online_payment_refunded_dm(
    *,
    client_name: str,
    amount_rub: str,
) -> str:
    """Render the locked refund-succeeded DM via ``str.format`` (unknown keys raise KeyError)."""
    return ONLINE_PAYMENT_REFUNDED_DM.format(
        client_name=client_name,
        amount_rub=amount_rub,
    )


def render_online_payment_canceled_dm(
    *,
    payment_id: str,
    yookassa_payment_id: str,
) -> str:
    """Render the locked payment-canceled owner-alert DM (D-52-08 — operator-actionable).

    OWNER-ALERT only (NOT-05): this template routes to the owner's Telegram chat,
    NOT to the client. Carries ``payment_id`` + ``yookassa_payment_id`` so the
    operator can locate the row in ЮKassa.
    """
    return ONLINE_PAYMENT_CANCELED_DM.format(
        payment_id=payment_id,
        yookassa_payment_id=yookassa_payment_id,
    )


def render_fiscal_receipt_failed_dm(
    *,
    payment_id: str,
    failure_reason: str,
) -> str:
    """Render the locked fiscal-receipt-failed owner-alert DM (D-52-08 — operator-actionable).

    OWNER-ALERT only (NOT-04): this template routes to the owner's Telegram chat,
    NOT to the client. Carries ``payment_id`` + ``failure_reason`` so the operator
    can identify the failing receipt in ЮKassa and take corrective action.
    """
    return FISCAL_RECEIPT_FAILED_DM.format(
        payment_id=payment_id,
        failure_reason=failure_reason,
    )
