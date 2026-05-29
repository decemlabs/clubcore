"""Unit tests for ``app.integrations.email.dispatcher`` (Plan 42-08 Task 2).

Covers:
  - ``_resolve_template`` walks the auth.email_templates registry; KeyError on miss
  - ``enqueue_email_dispatch`` renders subject/html/text at enqueue time
  - the rendered envelope kwargs hand off to ``pool.enqueue_job('dispatch_email',
    envelope_kwargs=..., _max_tries=2, _expires=20)`` (LOCKED — D-42-13 per-enqueue
    convention; matches existing project ARQ usage in ``app/workers/__init__.py``)
  - ``_get_arq_pool`` defensive raise until ``register_arq_pool`` runs
  - ``audit_correlation_id=None`` at the Protocol surface still produces a UUID
    on the envelope (uuid4() fallback per the dispatcher's docstring)

260529-olc RUN-03-F1 additions:
  - ``_resolve_template`` resolves all 4 online-payment template_ids (no KeyError)
  - Each template's locked subject matches the owner-signed-off literal
  - Each template renders with the exact dispatcher-supplied vars; body contains
    locked phrasing substrings; var values appear; no leftover ``{{``
  - End-to-end ``enqueue_email_dispatch`` happy-path for SUCCEEDED confirms the
    rendered envelope carries the locked subject + interpolated body fragment
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.integrations.email.dispatcher import (
    _get_arq_pool,
    _resolve_template,
    enqueue_email_dispatch,
    register_arq_pool,
)

# --------------------------------------------------------------------- helpers


class _FakeArqPool:
    """Captures the last ``enqueue_job`` call for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return None


@pytest.fixture(autouse=True)
def _reset_pool_slot() -> Any:
    """Reset the module-level pool slot between tests to keep them order-independent."""
    import app.integrations.email.dispatcher as disp

    disp._arq_pool = None
    yield
    disp._arq_pool = None


# --------------------------------------------------------------------- _resolve_template


def test_resolve_template_returns_email_otp_login_record() -> None:
    """Test 1: _resolve_template('EMAIL_OTP_LOGIN') returns the auth.email_templates record."""
    tpl = _resolve_template("EMAIL_OTP_LOGIN")
    assert tpl.subject == "Код входа в Sportzal"
    # Sanity: html + text are Jinja Templates (have .render method).
    assert hasattr(tpl.html, "render")
    assert hasattr(tpl.text, "render")


def test_resolve_template_raises_keyerror_on_unknown_id() -> None:
    """Test 2: unknown template_id surfaces as KeyError at enqueue time."""
    with pytest.raises(KeyError) as exc_info:
        _resolve_template("NONEXISTENT_TEMPLATE")
    assert "NONEXISTENT_TEMPLATE" in str(exc_info.value)


# --------------------------------------------------------------------- pool accessors


def test_get_arq_pool_raises_when_unregistered() -> None:
    """The defensive accessor is a hard failure surface until compose root wires the pool."""
    with pytest.raises(RuntimeError) as exc_info:
        _get_arq_pool()
    assert "ArqRedis pool not registered" in str(exc_info.value)


def test_register_arq_pool_sets_module_slot() -> None:
    """register_arq_pool replaces the module-level slot; idempotent re-register."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]  # FakeArqPool duck-types ArqRedis
    assert _get_arq_pool() is pool


# --------------------------------------------------------------------- enqueue_email_dispatch


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_renders_and_enqueues() -> None:
    """Test 3: rendered envelope is enqueued with _max_tries=2 and _expires=20."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]
    correlation = uuid4()

    await enqueue_email_dispatch(
        template_id="EMAIL_OTP_LOGIN",
        to="user@example.com",
        audit_correlation_id=correlation,
        otp_code="123456",
    )

    assert len(pool.calls) == 1
    args, kwargs = pool.calls[0]
    assert args == ("dispatch_email",)
    assert kwargs["_max_tries"] == 2
    assert kwargs["_expires"] == 20
    env = kwargs["envelope_kwargs"]
    assert env["to"] == "user@example.com"
    assert env["template_id"] == "EMAIL_OTP_LOGIN"
    assert env["subject"] == "Код входа в Sportzal"
    assert "<strong>123456</strong>" in env["html"]
    assert "Ваш код для входа: 123456" in env["text"]
    # audit_correlation_id is serialised as str(UUID) for cloudpickle safety.
    assert env["audit_correlation_id"] == str(correlation)


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_synthesises_correlation_id_when_none() -> None:
    """audit_correlation_id=None at the Protocol surface -> uuid4() fallback on the envelope."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]

    await enqueue_email_dispatch(
        template_id="EMAIL_OTP_LOGIN",
        to="user@example.com",
        audit_correlation_id=None,
        otp_code="654321",
    )

    _args, kwargs = pool.calls[0]
    env_corr = kwargs["envelope_kwargs"]["audit_correlation_id"]
    # Should be a valid UUID string (uuid4() fallback).
    parsed = UUID(env_corr)
    assert parsed.version == 4


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_raises_when_pool_unregistered() -> None:
    """If compose-root forgot to wire register_arq_pool, the enqueue call must fail loud."""
    # Pool slot is reset by the autouse fixture.
    with pytest.raises(RuntimeError):
        await enqueue_email_dispatch(
            template_id="EMAIL_OTP_LOGIN",
            to="user@example.com",
            audit_correlation_id=None,
            otp_code="123456",
        )


# --------------------------------------------------------------------- 260529-olc RUN-03-F1
# _resolve_template + render tests for all 4 online-payment template_ids.


@pytest.mark.parametrize(
    ("template_id", "expected_subject"),
    [
        ("EMAIL_ONLINE_PAYMENT_SUCCEEDED", "Оплата получена"),  # noqa: RUF001
        ("EMAIL_ONLINE_PAYMENT_REFUNDED", "Возврат обработан"),  # noqa: RUF001
        ("EMAIL_ONLINE_PAYMENT_CANCELED", "Платёж отменён — требуется проверка"),  # noqa: RUF001
        (
            "EMAIL_FISCAL_RECEIPT_FAILED",
            "Ошибка фискального чека — требуется проверка",  # noqa: RUF001
        ),
    ],
)
def test_online_payment_templates_resolve_with_locked_subjects(
    template_id: str,
    expected_subject: str,
) -> None:
    """All 4 online-payment template_ids resolve via _resolve_template (no KeyError).

    Asserts the locked subject literal and confirms html/text have a .render method.
    """
    tpl = _resolve_template(template_id)
    assert tpl.subject == expected_subject
    assert hasattr(tpl.html, "render")
    assert hasattr(tpl.text, "render")


def test_online_payment_succeeded_renders_with_dispatcher_vars() -> None:
    """EMAIL_ONLINE_PAYMENT_SUCCEEDED renders with first_name + amount_rub vars."""
    tpl = _resolve_template("EMAIL_ONLINE_PAYMENT_SUCCEEDED")
    rendered_html: str = tpl.html.render(first_name="Анна", amount_rub="1 500 ₽")  # noqa: RUF001
    rendered_text: str = tpl.text.render(first_name="Анна", amount_rub="1 500 ₽")  # noqa: RUF001
    # Locked phrasing must be present.
    assert "успешно получена" in rendered_html  # noqa: RUF001
    assert "успешно получена" in rendered_text  # noqa: RUF001
    # Supplied var values must appear in output.
    assert "Анна" in rendered_html  # noqa: RUF001
    assert "Анна" in rendered_text  # noqa: RUF001
    assert "1 500 ₽" in rendered_html
    assert "1 500 ₽" in rendered_text
    # No leftover template markers.
    assert "{{" not in rendered_html
    assert "{{" not in rendered_text


def test_online_payment_refunded_renders_with_dispatcher_vars() -> None:
    """EMAIL_ONLINE_PAYMENT_REFUNDED renders with first_name + amount_rub vars."""
    tpl = _resolve_template("EMAIL_ONLINE_PAYMENT_REFUNDED")
    rendered_html: str = tpl.html.render(first_name="Иван", amount_rub="2 000 ₽")  # noqa: RUF001
    rendered_text: str = tpl.text.render(first_name="Иван", amount_rub="2 000 ₽")  # noqa: RUF001
    # Locked phrasing must be present.
    assert "Возврат на сумму" in rendered_html  # noqa: RUF001
    assert "Возврат на сумму" in rendered_text  # noqa: RUF001
    # Supplied var values must appear in output.
    assert "Иван" in rendered_html  # noqa: RUF001
    assert "Иван" in rendered_text  # noqa: RUF001
    assert "2 000 ₽" in rendered_html
    assert "2 000 ₽" in rendered_text
    # No leftover template markers.
    assert "{{" not in rendered_html
    assert "{{" not in rendered_text


def test_online_payment_canceled_renders_with_dispatcher_vars() -> None:
    """EMAIL_ONLINE_PAYMENT_CANCELED renders with payment_id + yookassa_payment_id vars."""
    tpl = _resolve_template("EMAIL_ONLINE_PAYMENT_CANCELED")
    rendered_html: str = tpl.html.render(
        payment_id="pay-abc-123",
        yookassa_payment_id="yk-xyz-789",
    )
    rendered_text: str = tpl.text.render(
        payment_id="pay-abc-123",
        yookassa_payment_id="yk-xyz-789",
    )
    # Locked phrasing must be present.
    assert "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА]" in rendered_html  # noqa: RUF001
    assert "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА]" in rendered_text  # noqa: RUF001
    assert "yookassa_payment_id:" in rendered_html
    assert "yookassa_payment_id:" in rendered_text
    # Supplied var values must appear in output.
    assert "pay-abc-123" in rendered_html
    assert "pay-abc-123" in rendered_text
    assert "yk-xyz-789" in rendered_html
    assert "yk-xyz-789" in rendered_text
    # No leftover template markers.
    assert "{{" not in rendered_html
    assert "{{" not in rendered_text


def test_fiscal_receipt_failed_renders_with_dispatcher_vars() -> None:
    """EMAIL_FISCAL_RECEIPT_FAILED renders with payment_id + failure_reason vars."""
    tpl = _resolve_template("EMAIL_FISCAL_RECEIPT_FAILED")
    rendered_html: str = tpl.html.render(
        payment_id="pay-def-456",
        failure_reason="timeout from ЮKassa",  # noqa: RUF001
    )
    rendered_text: str = tpl.text.render(
        payment_id="pay-def-456",
        failure_reason="timeout from ЮKassa",  # noqa: RUF001
    )
    # Locked phrasing must be present.
    assert "Ошибка формирования фискального чека" in rendered_html  # noqa: RUF001
    assert "Ошибка формирования фискального чека" in rendered_text  # noqa: RUF001
    assert "причина:" in rendered_html  # noqa: RUF001
    assert "причина:" in rendered_text  # noqa: RUF001
    # Supplied var values must appear in output.
    assert "pay-def-456" in rendered_html
    assert "pay-def-456" in rendered_text
    assert "timeout from" in rendered_html
    assert "timeout from" in rendered_text
    # No leftover template markers.
    assert "{{" not in rendered_html
    assert "{{" not in rendered_text


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_online_payment_succeeded_end_to_end() -> None:
    """End-to-end: enqueue_email_dispatch for EMAIL_ONLINE_PAYMENT_SUCCEEDED renders
    and enqueues an envelope with the locked subject and interpolated body fragment.
    """
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]
    correlation = uuid4()

    await enqueue_email_dispatch(
        template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED",
        to="client@example.com",
        audit_correlation_id=correlation,
        first_name="Мария",  # noqa: RUF001
        amount_rub="3 000 ₽",
    )

    assert len(pool.calls) == 1
    args, kwargs = pool.calls[0]
    assert args == ("dispatch_email",)
    assert kwargs["_max_tries"] == 2
    assert kwargs["_expires"] == 20
    env = kwargs["envelope_kwargs"]
    assert env["to"] == "client@example.com"
    assert env["template_id"] == "EMAIL_ONLINE_PAYMENT_SUCCEEDED"
    assert env["subject"] == "Оплата получена"  # noqa: RUF001
    assert "Мария" in env["html"]  # noqa: RUF001
    assert "3 000 ₽" in env["html"]
    assert "успешно получена" in env["html"]  # noqa: RUF001
    assert "{{" not in env["html"]
    assert env["audit_correlation_id"] == str(correlation)
