"""Unit tests for `CsrfMismatch` exception (Phase 6 D-08, D-21)."""

from app.core.exceptions import AppError, CsrfMismatch


def test_csrf_mismatch_is_importable() -> None:
    assert CsrfMismatch is not None


def test_csrf_mismatch_code_is_locked() -> None:
    assert CsrfMismatch.code == "csrf_mismatch"


def test_csrf_mismatch_status_code_is_403() -> None:
    assert CsrfMismatch.status_code == 403


def test_csrf_mismatch_is_app_error_subclass() -> None:
    assert issubclass(CsrfMismatch, AppError)
    instance = CsrfMismatch("csrf_mismatch")
    assert isinstance(instance, AppError)


def test_csrf_mismatch_fields_default_to_none() -> None:
    instance = CsrfMismatch("csrf_mismatch")
    assert instance.message == "csrf_mismatch"
    assert instance.fields is None
