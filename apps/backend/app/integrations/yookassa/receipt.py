"""ЮKassa receipt-item builder + 54-ФЗ enum constants.

Phase 48 ADAPTER-04 (D-48-16/17/18). Returns a ``dict[str, Any]`` shaped
per ЮKassa wire format — NOT a typed model — because Phase 49 callers
concatenate items into a list inside the payment-create body, and ЮKassa's
receipt nested object accepts dicts directly (STACK.md §6).

Three enums lock the 54-ФЗ tag values:
    PaymentSubject (StrEnum) — тег 1212; one member in v1.7 (service).
    PaymentMode (StrEnum)    — тег 1214; two members (full_payment, full_prepayment).
    VatCode (IntEnum)        — тег 1199; six members per ЮKassa docs.

AST gate (tests/unit/test_locked_yookassa_constants_ast.py extended per
D-48-18): every ``build_receipt_item(payment_subject=..., payment_mode=...)``
callsite MUST pass literal enum members; variables / f-strings / raw str
are rejected at CI.

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any, Final

from app.integrations.yookassa._money import kopecks_to_yookassa

CURRENCY: Final[str] = "RUB"
_MAX_DESCRIPTION_LEN: Final[int] = 128


class PaymentSubject(StrEnum):
    """ЮKassa тег 1212 — признак предмета расчёта (D-48-17).

    Sportzal v1.7 sells gym memberships and PT-package services only —
    one member. Adding new members requires owner sign-off + AST-gate
    test extension (D-48-18).
    """

    SERVICE = "service"


class PaymentMode(StrEnum):
    """ЮKassa тег 1214 — признак способа расчёта (D-48-17).

    FULL_PREPAYMENT for online membership sales paid before activation
    (most common). FULL_PAYMENT for at-point-of-consumption (drop-in
    classes, PT sessions paid at the desk). Phase 49 orchestrator picks
    per sale type.
    """

    FULL_PAYMENT = "full_payment"
    FULL_PREPAYMENT = "full_prepayment"


class VatCode(IntEnum):
    """ЮKassa тег 1199 — ставка НДС (D-48-17). Full 54-ФЗ enumeration."""

    VAT_NONE = 1  # без НДС
    VAT_0 = 2  # НДС 0%
    VAT_10 = 3  # НДС 10%
    VAT_20 = 4  # НДС 20%
    VAT_10_110 = 5  # НДС 10/110
    VAT_20_120 = 6  # НДС 20/120


def build_receipt_item(
    *,
    description: str,
    amount_kopecks: int,
    payment_subject: PaymentSubject,
    payment_mode: PaymentMode,
    vat_code: VatCode,
    quantity: str = "1.00",
) -> dict[str, Any]:
    """Assemble one 54-ФЗ receipt item per ЮKassa wire format (D-48-16).

    Returns a plain dict (not a typed model) so callers can concatenate
    into ``receipt.items`` lists without unwrap/repack churn.

    Raises:
        ValueError: if description exceeds 128 chars (ЮKassa rejects).
    """
    if len(description) > _MAX_DESCRIPTION_LEN:
        raise ValueError(
            f"description must be ≤ {_MAX_DESCRIPTION_LEN} chars, got {len(description)}"
        )
    return {
        "description": description,
        "quantity": quantity,
        "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": CURRENCY},
        "vat_code": int(vat_code),
        "payment_mode": payment_mode.value,
        "payment_subject": payment_subject.value,
    }
