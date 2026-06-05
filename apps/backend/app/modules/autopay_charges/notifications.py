"""Locked Russian DM templates for Phase 84 autopay notifications (APAY-04).

Two DM copy renderers for autopay outcomes:
- render_autopay_charge_succeeded_dm: success copy for the webhook-confirmed renewal path.
  Keyed on online_payment_id (the webhook created the online_payments row). Owner-signed.
- render_autopay_charge_failed_dm: failure copy for the cron sync-decline path.
  Keyed on autopay_charge_id (a decline has NO online_payments row). Owner-signed.

Copy discipline (D-52-06 mirror):
  - NO A/B variants; one template per outcome (one-shot event).
  - Modifying these strings post-merge requires a NEW owner sign-off entry in the
    phase SUMMARY file.
  - Placeholder substitution via ``str.format(**kwargs)`` so unknown placeholder
    keys raise ``KeyError`` loud at test time (D-39-04 / D-52-08 mirror).

Owner-signed tone: matches the existing ONLINE_PAYMENT_SUCCEEDED_DM discipline
(Phase 52 NOT-01). Client copy is friendly + informative; failure copy includes an
actionable instruction ("обновите карту").

Anti-oracle hygiene (D-52-08 mirror):
  - Success copy carries NO PII beyond first_name + formatted amount + end_date.
  - Failure copy carries NO provider error codes or internal identifiers.

Module location: lives in ``app/modules/autopay_charges/`` because autopay DM copy
is owned by the autopay_charges domain (mirrors payments/email_templates.py → online_payments
discipline).
"""

from __future__ import annotations

from typing import Final

# === Phase 84 APAY-04 — locked Russian autopay DM copy. Owner sign-off required. ===
# RUF001/E501 per-line: Cyrillic letters + locked single-line format are intentional.

AUTOPAY_CHARGE_SUCCEEDED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Ваш абонемент продлён автосписанием на сумму {amount_rub}. Абонемент действует до {end_date}. Ждём вас в зале!"  # noqa: E501  # OWNER-COPY-LOCK APAY-04
)

AUTOPAY_CHARGE_FAILED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Автосписание за продление абонемента на сумму {amount_rub} не прошло. Пожалуйста, обновите карту в приложении или обратитесь к администратору."  # noqa: E501  # OWNER-COPY-LOCK APAY-04
)


def render_autopay_charge_succeeded_dm(
    *,
    client_name: str,
    amount_rub: str,
    end_date: str,
) -> str:
    """Render the locked autopay-succeeded DM via ``str.format`` (unknown keys raise KeyError).

    Args:
        client_name: Client's first name for personalised greeting.
        amount_rub: Formatted RUB amount string (e.g. "1 990,00 ₽"). Pre-formatted by
            ``format_money`` upstream (D-45-17 / D-52-08 mirror) — passed through verbatim.
        end_date: New membership end date in readable form (e.g. "31.12.2026").
    """
    return AUTOPAY_CHARGE_SUCCEEDED_DM.format(
        client_name=client_name,
        amount_rub=amount_rub,
        end_date=end_date,
    )


def render_autopay_charge_failed_dm(
    *,
    client_name: str,
    amount_rub: str,
) -> str:
    """Render the locked autopay-failed DM via ``str.format`` (unknown keys raise KeyError).

    Args:
        client_name: Client's first name for personalised greeting.
        amount_rub: Formatted RUB amount string (e.g. "1 990,00 ₽"). Pre-formatted by
            ``format_money`` upstream — passed through verbatim.
    """
    return AUTOPAY_CHARGE_FAILED_DM.format(
        client_name=client_name,
        amount_rub=amount_rub,
    )
