"""Wire-format contract: ContractModel hierarchy + ResponseEnvelope[T] + ProblemDetails.

Implements decisions D-07..D-14, requirement API-03.

Backend-first contract (D-07):
  - Successful 2xx responses serialize to { "data": <payload> } via ResponseEnvelope[T].
  - Errors stay top-level { code, message, fields? } (D-08) — matches AppError handler output.
  - Wire format is camelCase via pydantic.alias_generators.to_camel; Python identifiers
    stay snake_case.
  - `validate_by_name=True` + `validate_by_alias=True` paired (Pydantic 2.11+) replaces
    the deprecated field aliasing flag. Setting BOTH to False is invalid (raises
    PydanticUserError at class-definition time).
  - PEP 695 generics for ResponseEnvelope[T] (D-11). Uses Python 3.12 syntax natively.

Phase 4 envelope (D-13) is { data: T } only — minimum viable. Optional fields
(requestId, traceId, meta, warnings) deferred to whichever phase first needs them;
they will be additive Optional[...] = None so existing clients ignore them.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    """Base for every API contract model. camelCase wire, snake_case Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        from_attributes=True,
        extra="ignore",
    )


class BackendSchemaBase(ContractModel):
    """Inbound request body / query params. Strict on extras (extra='forbid').

    Locked in Phase 15 (INFRA-12 / D-06) as the single source of truth for v1.2
    inbound DTOs.

    `model_config` keeps `validate_by_name=True + validate_by_alias=True` (Pydantic
    2.11+ canonical pair, D-07). The older deprecated alias flag is intentionally
    NOT used; `tests/unit/test_schemas.py` asserts the deprecated spelling never
    appears in module source.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )


class ResponseData(ContractModel):
    """Payload inside ResponseEnvelope. Subclassed by every domain response DTO."""


class ResponseEnvelope[T](ContractModel):
    """Success transport wrapper. Phase 4: { data: T }. Future fields optional (D-13)."""

    data: T


class ProblemDetails(ContractModel):
    """Error response body — documents the shape emitted by app.core.exceptions._app_error_handler.

    Used as `responses={4xx: {"model": ProblemDetails}}` on routes so OpenAPI carries the
    error schema; the runtime handler body is unchanged (top-level { code, message, fields? }
    per D-08, NOT wrapped in `data`).
    """

    code: str
    message: str
    fields: dict[str, object] | None = None


def envelope[T](payload: T) -> ResponseEnvelope[T]:
    """Convenience helper. D-14: routes return ResponseEnvelope[X](data=...) explicitly,
    but a small wrapper is acceptable (and reduces import noise in route handlers)."""
    return ResponseEnvelope(data=payload)
