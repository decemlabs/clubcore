"""Gym-info module Pydantic schemas (Phase 86 GYM-01/GYM-02).

Response schema uses ResponseData (camelCase wire via alias_generator=to_camel).
Request schema uses BackendSchemaBase (extra='forbid', camelCase inbound).
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData


class GymInfoResponse(ResponseData):
    """GET /client/gym and PUT /gym response payload (GYM-01/GYM-02).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).
    """

    name: str
    address: str
    tagline: str | None = None
    city: str | None = None
    metro: str | None = None
    phone: str | None = None
    email: str | None = None
    hours: list[Any] = Field(default_factory=list)
    amenities: list[Any] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    social: list[Any] = Field(default_factory=list)


class GymInfoUpdateRequest(BackendSchemaBase):
    """Owner-only partial upsert request body (GYM-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    Scalar str fields capped via Field(max_length=255) — T-86-03 mitigation
    (unbounded payload DoS deferred to Plan 02 router validation; scalar cap here).
    All fields are optional (partial upsert — exclude_unset semantics in repository).
    """

    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    tagline: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    metro: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    hours: list[Any] | None = None
    amenities: list[Any] | None = None
    rules: list[str] | None = None
    social: list[Any] | None = None
