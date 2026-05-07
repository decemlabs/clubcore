"""Visits Pydantic schemas (Phase 19 VIS-02).

POST body is sealed to {clientId} — every other field is server-derived (D-01):
- membershipId resolved via core.dependencies.resolve_active_membership
- checkedInAt defaults to DB now()
- gymDate is the STORED GENERATED column (app NEVER writes it)
- channel is 'reception' for the HTTP path; 'telegram_bot' for the bot path
- checkedInBy is actor.id (reception) or NULL (bot)

The inherited BackendSchemaBase config (extra='forbid') rejects payload tampering
with stock 422 — see Phase 15 INFRA-12.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase


class VisitCreateRequest(BackendSchemaBase):
    """POST /api/v1/visits body (Phase 19 D-01).

    Only clientId is accepted; every other field is server-derived (see module
    docstring). The inherited extra='forbid' rejects payload tampering.
    """

    client_id: UUID


class VisitResponse(BackendSchemaBase):
    """GET / POST response shape (Phase 19 VIS-EP-01..03).

    from_attributes=True allows model_validate(visit_orm) directly.
    extra='ignore' (via ContractModel base) is overridden here because
    we merge BackendSchemaBase.model_config with from_attributes.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        from_attributes=True,
    )

    id: UUID
    client_id: UUID
    membership_id: UUID
    checked_in_at: datetime
    gym_date: date
    channel: str
    checked_in_by: UUID | None
    created_at: datetime


class VisitListQuery(PageQuery):
    """GET /api/v1/visits query parameters (Phase 19 D-09).

    No sort enum — server enforces fixed checked_in_at DESC. Filters are
    inclusive on both date bounds (CD-08). The 'from' alias uses the
    Pydantic field name 'from_' to avoid the Python keyword collision.
    """

    client_id: UUID | None = None
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
