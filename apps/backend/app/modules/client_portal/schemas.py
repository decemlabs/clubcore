"""Client-portal Pydantic response schemas (Phase 69 D-69-05).

Client-safe field projection: expose ONLY purchase/display-relevant fields.
NEVER include:
  - freeze_days_limit internals (freeze_days_limit_snapshot)
  - created_by / audit fields (created_at, updated_at, received_by_user_id)
  - soft-delete flags (deleted_at)
  - owner-only economics (price_kopecks_snapshot, duration_days_snapshot)
  - is_active flags
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.core.schemas import ResponseData


class ClientMembershipResponse(ResponseData):
    """Active membership payload with server-derived temporal fields (D-69-02).

    Exposed fields only (D-69-05): no freeze_days_limit_snapshot internals, no audit fields.
    days_until_end and expiring_soon are server-computed; the PWA renders only (D-69-02).
    """

    id: UUID
    plan_name_snapshot: str
    start_date: date
    end_date: date
    status: str
    days_until_end: int  # server-computed (D-69-02)
    expiring_soon: bool  # server-computed (D-69-02): True if 0 <= days_until_end <= 7


class ClientNextBookingResponse(ResponseData):
    """Nearest upcoming confirmed booking — display payload for home + bookings list."""

    id: UUID
    trainer_name: str
    start_time: datetime
    status: str


class ClientHomeResponse(ResponseData):
    """Composite home screen payload (D-69-01).

    Server-side fan-out: reuses get_client_membership + next-booking query.
    Null slots for missing data (D-69-03: own-scope empty is 200/null, not 404).
    """

    membership: ClientMembershipResponse | None  # null if no active membership (D-69-03)
    next_booking: ClientNextBookingResponse | None
    expiring_soon: bool  # convenience field mirroring membership.expiring_soon


class ClientVisitItem(ResponseData):
    """Single visit row for the client visit history (CHIST-01)."""

    id: UUID
    gym_date: date
    checked_in_at: datetime


class ClientPtSessionItem(ResponseData):
    """Single PT-session row for the client PT-session history (CHIST-02)."""

    id: UUID
    trainer_name_snapshot: str
    performed_at: datetime
    cancelled_at: datetime | None = None


class ClientPaymentItem(ResponseData):
    """Single payment / refund row for the client payment history (CHIST-03).

    Includes signed amount_kopecks so refunds (negative) render correctly.
    """

    id: UUID
    subject_kind: str  # 'membership' | 'pt_package' | 'refund'
    amount_kopecks: int  # signed: negative for refunds
    method: str  # 'cash' | 'online'
    received_at: datetime


class ClientCatalogPlanResponse(ResponseData):
    """Active membership plan — client-safe fields only (CPLAN-01, D-69-05)."""

    id: UUID
    name: str
    price_kopecks: int
    duration_days: int


class ClientCatalogPtPackageResponse(ResponseData):
    """Active PT-package plan — client-safe fields only (CPLAN-02, D-69-05)."""

    id: UUID
    name: str
    session_count: int
    price_kopecks: int


class ClientCatalogTrainerResponse(ResponseData):
    """Active trainer — client-safe projection (CPLAN-03, D-69-05).

    NO rates, NO phone, NO is_active flag, NO audit fields.
    specialization is not present in the Trainer model (reserved for future).
    """

    id: UUID
    full_name: str
