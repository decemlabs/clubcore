"""Unit tests for app.core.schemas — ContractModel hierarchy + ResponseEnvelope[T] + ProblemDetails.

Covers D-29, API-03.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from app.core.exceptions import AppError
from app.core.schemas import (
    BackendSchemaBase,
    ContractModel,
    ProblemDetails,
    ResponseData,
    ResponseEnvelope,
    envelope,
)


class _Sample(ContractModel):
    full_name: str
    page_size: int = 20


class _SampleRequest(BackendSchemaBase):
    user_name: str
    page_size: int = 20


# ---- ContractModel config (Pitfall A guard) ----


def test_contract_model_config_uses_to_camel_alias_generator() -> None:
    assert ContractModel.model_config["alias_generator"] is to_camel


def test_contract_model_config_pairs_validate_by_name_and_alias() -> None:
    cfg = ContractModel.model_config
    assert cfg["validate_by_name"] is True
    assert cfg["validate_by_alias"] is True


def test_contract_model_config_uses_extra_ignore() -> None:
    assert ContractModel.model_config["extra"] == "ignore"


def test_contract_model_config_has_from_attributes_true() -> None:
    assert ContractModel.model_config["from_attributes"] is True


def test_backend_schema_base_config_uses_extra_forbid() -> None:
    assert BackendSchemaBase.model_config["extra"] == "forbid"


def test_no_populate_by_name_in_module_source() -> None:
    """Pitfall A: populate_by_name is the deprecated 2.11 alias of validate_by_name.

    We pin pydantic>=2.11 (D-12) so the new flags are mandatory; the old alias
    emits DeprecationWarning silently swallowed by our pyproject filterwarnings.
    Catch its presence at the source level.
    """
    import app.core.schemas as schemas_module

    src = inspect.getsource(schemas_module)
    assert "populate_by_name" not in src


# ---- camelCase wire / snake_case Python ----


def test_request_accepts_both_camel_and_snake() -> None:
    # Use model_validate to pass camelCase keys (mypy only knows about snake_case kwargs)
    a = _SampleRequest.model_validate({"userName": "alice", "pageSize": 10})
    b = _SampleRequest(user_name="alice", page_size=10)
    assert a.user_name == "alice"
    assert b.user_name == "alice"
    assert a.page_size == 10 == b.page_size


def test_request_dump_by_alias_emits_camel_case() -> None:
    s = _SampleRequest(user_name="alice", page_size=10)
    assert s.model_dump(by_alias=True) == {"userName": "alice", "pageSize": 10}


def test_request_extra_forbid_raises_on_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _SampleRequest.model_validate({"userName": "x", "pageSize": 10, "unknown": "boom"})


# ---- ResponseEnvelope[T] (D-07, D-13) ----


def test_response_envelope_wraps_payload_in_data_key() -> None:
    env = ResponseEnvelope[_Sample](data=_Sample(full_name="Alice"))
    dump = env.model_dump(by_alias=True)
    assert dump == {"data": {"fullName": "Alice", "pageSize": 20}}


def test_envelope_helper_returns_response_envelope_instance() -> None:
    e = envelope(_Sample(full_name="Bob"))
    assert isinstance(e, ResponseEnvelope)
    assert e.data.full_name == "Bob"


# ---- ProblemDetails (D-08) — matches AppError handler body ----


def test_problem_details_accepts_optional_fields_none() -> None:
    pd = ProblemDetails(code="x", message="y")
    assert pd.fields is None


def test_problem_details_dump_matches_app_error_handler_body_shape() -> None:
    """The runtime _app_error_handler emits {code, message, fields}; ProblemDetails documents it."""
    pd = ProblemDetails(code="not_found", message="missing", fields={"id": "abc"})
    dump = pd.model_dump()
    assert dump == {"code": "not_found", "message": "missing", "fields": {"id": "abc"}}


def test_app_error_subclass_attributes_present() -> None:
    # Smoke: runtime handler shape (exceptions.py) hasn't drifted to invalidate ProblemDetails.
    # AppError exposes code, status_code, and via __init__ message+fields.
    assert AppError.code == "app_error"
    assert AppError.status_code == 500


def test_response_data_is_subclass_of_contract_model() -> None:
    assert issubclass(ResponseData, ContractModel)
