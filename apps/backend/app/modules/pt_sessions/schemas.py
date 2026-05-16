"""PtSession request/response DTOs (Phase 34).

Inputs inherit BackendSchemaBase (camelCase wire ↔ snake_case Python,
`extra='forbid'`). Responses inherit ResponseData. PageQuery is the
pagination base for list endpoints.

Decision references — Phase 34 (34-CONTEXT.md):
- D-34-06: POST /pt-sessions body — {ptPackageId, trainerId, performedAt,
  notes?}. `extra='forbid'` REJECTS clientId (server derives from
  pt_package row per D-34-13a — body has only pt_package_id).
- D-34-07: POST /pt-sessions/{id}/cancel body — {cancelReason: 1..200,
  REQUIRED}.
- D-34-08: GET /pt-packages/{id}/sessions query — {includeCancelled?,
  page?, pageSize?}. Default includeCancelled=true (UI/operator filters).
- D-34-02: PtSessionResponse exposes the full PT-14 column set including
  trainer_name_snapshot for historical UI rendering (B-05).
- D-34-02 / migration 0015_pt_sessions: `notes` max_length=500 and
  `cancel_reason` max_length=200 mirror the DB CHECK constraints
  (defence-in-depth — Pydantic surfaces 422 before the round-trip).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData


class PtSessionCreateRequest(BackendSchemaBase):
    """POST /api/v1/pt-sessions body (PT-15 / D-34-06).

    `extra='forbid'` (inherited) REJECTS unexpected fields with 422.
    Server-validates trainer existence/active via the TrainerById Protocol
    slot (Phase 31 + Phase 34 D-34-12a) and enforces the backdating window
    (B-11) AFTER schema parse.

    `client_id` is derived from the `pt_package` row server-side
    (D-34-13a) and is NOT accepted on the wire — sending it triggers a
    422 via `extra='forbid'`.
    """

    pt_package_id: UUID
    trainer_id: UUID
    performed_at: datetime  # ISO-8601 with offset; backdating window server-side
    notes: str | None = Field(default=None, max_length=500)


class PtSessionCancelRequest(BackendSchemaBase):
    """POST /api/v1/pt-sessions/{id}/cancel body (PT-18 / D-34-07).

    `extra='forbid'`. `cancel_reason` REQUIRED 1..200 (mirrors
    PtPackageCancelRequest 1..200 bounds; defence-in-depth for the DB
    CHECK ck_pt_sessions_cancel_reason_length).
    """

    cancel_reason: str = Field(min_length=1, max_length=200)


class PtSessionListByPackageQuery(PageQuery):
    """GET /api/v1/pt-packages/{id}/sessions query (D-34-08).

    Default `include_cancelled=True` shows all sessions (cancelled + active);
    UI/operator filters client-side or sets `false` for active-only.
    """

    include_cancelled: bool = True


class PtSessionResponse(ResponseData):
    """Outbound representation of a PtSession row (D-34-08).

    Exposes the full PT-14 column set including `trainer_name_snapshot`
    for historical UI rendering after the parent trainer is renamed or
    deactivated (B-05).
    """

    id: UUID
    pt_package_id: UUID
    trainer_id: UUID
    client_id: UUID
    performed_at: datetime
    performed_by_user_id: UUID
    cancelled_at: datetime | None
    cancel_reason: str | None
    trainer_name_snapshot: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
