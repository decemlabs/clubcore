from __future__ import annotations

import pytest

from app.integrations.yookassa.receipt import (
    CURRENCY,
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)


def test_currency_is_rub() -> None:
    assert CURRENCY == "RUB"


def test_payment_subject_has_one_member() -> None:
    assert len(PaymentSubject) == 1
    assert PaymentSubject.SERVICE.value == "service"


def test_payment_mode_has_two_members() -> None:
    assert len(PaymentMode) == 2
    assert PaymentMode.FULL_PAYMENT.value == "full_payment"
    assert PaymentMode.FULL_PREPAYMENT.value == "full_prepayment"


def test_vat_code_has_six_members() -> None:
    assert len(VatCode) == 6
    assert int(VatCode.VAT_NONE) == 1
    assert int(VatCode.VAT_0) == 2
    assert int(VatCode.VAT_10) == 3
    assert int(VatCode.VAT_20) == 4
    assert int(VatCode.VAT_10_110) == 5
    assert int(VatCode.VAT_20_120) == 6


def test_build_receipt_item_emits_wire_shape() -> None:
    item = build_receipt_item(
        description="Месячный абонемент в зал",
        amount_kopecks=199_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PREPAYMENT,
        vat_code=VatCode.VAT_NONE,
    )
    assert item == {
        "description": "Месячный абонемент в зал",
        "quantity": "1.00",
        "amount": {"value": "1990.00", "currency": "RUB"},
        "vat_code": 1,
        "payment_mode": "full_prepayment",
        "payment_subject": "service",
    }


def test_build_receipt_item_full_payment_mode() -> None:
    item = build_receipt_item(
        description="Разовое занятие",
        amount_kopecks=50_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PAYMENT,
        vat_code=VatCode.VAT_20,
    )
    assert item["payment_mode"] == "full_payment"
    assert item["vat_code"] == 4
    assert item["amount"] == {"value": "500.00", "currency": "RUB"}


def test_build_receipt_item_custom_quantity() -> None:
    item = build_receipt_item(
        description="PT-пакет 5 занятий",
        amount_kopecks=750_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PREPAYMENT,
        vat_code=VatCode.VAT_NONE,
        quantity="5.00",
    )
    assert item["quantity"] == "5.00"


def test_build_receipt_item_accepts_exactly_128_char_description() -> None:
    desc = "x" * 128
    item = build_receipt_item(
        description=desc,
        amount_kopecks=10_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PAYMENT,
        vat_code=VatCode.VAT_NONE,
    )
    assert item["description"] == desc


def test_build_receipt_item_rejects_description_over_128_chars() -> None:
    with pytest.raises(ValueError, match="128"):
        build_receipt_item(
            description="x" * 129,
            amount_kopecks=10_000,
            payment_subject=PaymentSubject.SERVICE,
            payment_mode=PaymentMode.FULL_PAYMENT,
            vat_code=VatCode.VAT_NONE,
        )


def test_build_receipt_item_returns_dict_not_model() -> None:
    item = build_receipt_item(
        description="Test",
        amount_kopecks=10_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PAYMENT,
        vat_code=VatCode.VAT_NONE,
    )
    assert type(item) is dict  # plain dict per D-48-16; no typed model
