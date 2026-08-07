"""Gym-info module Pydantic schemas (Phase 86 GYM-01/GYM-02).

Response schema uses ResponseData (camelCase wire via alias_generator=to_camel).
Request schema uses BackendSchemaBase (extra='forbid', camelCase inbound).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import EmailStr, Field

from app.core.schemas import BackendSchemaBase, ResponseData


class SocialItem(BackendSchemaBase):
    """Per-item schema for social network entries (WR-06 — T-86-11 mitigation).

    kind is a closed enum so only tg/ig are accepted at PUT time.
    handle is a simple @username pattern; encodeURIComponent in the PWA
    covers any remaining URL-unsafe chars after @ stripping.
    """

    kind: Literal["tg", "ig"]
    label: str = Field(max_length=64)
    handle: str = Field(max_length=64, pattern=r"^@[\w.]+$")


class GymInfoResponse(ResponseData):
    """GET /client/gym, GET /gym, and PUT /gym response payload (GYM-01/GYM-02/CFG-01).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).

    Phase 108 CFG-01: latitude + longitude nullable columns added additively.
    """

    name: str
    address: str
    tagline: str | None = None
    city: str | None = None
    metro: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None
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

    CR-02 / T-86-12: email validated via EmailStr — rejects query-string injection
    (e.g. "user@gym.ru?cc=evil@x.com") because the email grammar forbids '?', '#', '%'.
    Seed value "tverskaya@mygym.ru" passes EmailStr validation.

    WR-06 / T-86-11: social validated via SocialItem — rejects unknown kinds and
    handles with embedded '@' sequences or non-username characters.
    """

    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    tagline: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    metro: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    # Phase 108 CFG-01: gym coordinates (additive). T-108-05 bounds: lat [-90,90], lng [-180,180].
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    hours: list[Any] | None = None
    amenities: list[Any] | None = None
    rules: list[str] | None = None
    social: list[SocialItem] | None = None
