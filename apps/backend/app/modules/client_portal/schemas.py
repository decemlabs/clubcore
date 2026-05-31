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
    membership_state: str  # 'active' | 'newbie' | 'lapsed' (D-01); camelCase wire: membershipState


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


# ---------------------------------------------------------------------------
# Phase 70 CBOOK-02..05 — booking write, cancel, and available-slots schemas
# ---------------------------------------------------------------------------


class ClientCreateBookingRequest(ResponseData):
    """POST /client/booking body (Phase 70 CBOOK-03 / T-70-11).

    NO client_id field — the principal from require_client() is the IDOR-safe
    source (T-70-11 mitigated structurally; extra='forbid' rejects any
    injected client_id from the body).

    CR-03 (Phase 71 fix): ``pt_package_id`` is now OPTIONAL. When the client
    omits it (or sends null), the service resolves the client's active PT-package
    server-side via ``get_active_pt_package``. This lets the PWA skip the
    burden of reading and passing the active package UUID, and ensures the
    ``no_active_pt_package`` CBOOK-04 redirect branch is actually reachable
    (previously an empty-string sent by BookScreen always 422'd before the
    service even ran).
    """

    slot_id: UUID
    pt_package_id: UUID | None = None


class ClientBookingResponse(ResponseData):
    """Booking write response payload — client-safe projection (Phase 70 CBOOK-03/05).

    Mirrors BookingResponse from app.modules.bookings.schemas but declared here
    so client_portal never imports app.modules.bookings (D-20-MODULE).

    Mapped from BookingResponse fields:
      id               -> booking id
      slot_id          -> slot_id
      status           -> status (confirmed / cancelled)
      start_time       -> slot_start_time (slot.start_time via eager-loaded join)
      trainer_name     -> trainer_full_name (slot.trainer.full_name)
    end_time is NOT in BookingResponse (no snapshot columns per D-38-08).
    """

    id: UUID
    slot_id: UUID
    status: str
    start_time: datetime
    trainer_name: str


class ClientAvailableSlotItem(ResponseData):
    """Single bookable slot item — client-safe projection (CBOOK-02 / D-69-05 / T-70-13).

    NO owner-only economics. Verified column sources:
      trainer_availability_slots (app/modules/schedule/models.py:64-152):
        id           UUID PK
        trainer_id   UUID FK trainers.id
        start_time   DateTime(timezone=True)
        end_time     DateTime(timezone=True)
        status       String(16)
      trainers (app/modules/trainers/models.py:23-43):
        full_name    Text NOT NULL
    specialization is NOT on the Trainer model in v1 (reserved for future);
    omitted per ClientCatalogTrainerResponse precedent (schemas.py:105-113).
    """

    slot_id: UUID
    trainer_id: UUID
    trainer_name: str
    start_time: datetime
    end_time: datetime


# ---------------------------------------------------------------------------
# Phase 70 CCHK-01..03 — QR self check-in schemas
# ---------------------------------------------------------------------------


class ClientQrTokenResponse(ResponseData):
    """QR self check-in token response (CCHK-01 / D-70-09).

    Returned by GET /client/qr-token (require_client gated, ~60s TTL).
    The PWA renders the token as a QR code for the gym scanner to scan.
    expires_in is informational — the PWA may use it to display a countdown
    and refresh the token before it expires.
    """

    token: str
    expires_in: int  # seconds; mirrors settings.qr_token_ttl_seconds (~60)


class ClientCheckInRequest(ResponseData):
    """POST /client/check-in body (Phase 70 CCHK-02 / D-70-10).

    The signed QR token is the sole credential — client_id is NEVER in the
    body (cross-client check-in structurally impossible, T-70-17).
    extra='forbid' (inherited from ResponseData) rejects any injected
    client_id from the body.
    """

    token: str


class ClientCheckInResponse(ResponseData):
    """Check-in success response — client-safe visit projection (CCHK-02).

    Declared here so client_portal never imports app.modules.visits (D-20-MODULE).
    Mapped from VisitResponse fields:
      id           -> visit id
      gym_date     -> visit date (Moscow TZ)
      checked_in_at -> UTC timestamp of check-in
      channel      -> always 'client_qr' for this path
    """

    id: UUID
    gym_date: date
    checked_in_at: datetime
    channel: str


# ---------------------------------------------------------------------------
# Phase 71 CPAY-01..05 — checkout write + status read schemas
# ---------------------------------------------------------------------------


class ClientCheckoutRequest(ResponseData):
    """Request body for client-initiated checkout (CPAY-01/02).

    No fields required for membership (plan_id in path); for PT the
    idempotency_key is supplied via Idempotency-Key header (D-71-04), not body.
    Phase 999.4 D-06: optional promo_code field (wire: promoCode).
    """

    promo_code: str | None = None  # wire: promoCode (D-06); None = no promo applied


class ClientCheckoutResponse(ResponseData):
    """Checkout response: redirect URL + online_payment_id for status polling (CPAY-03)."""

    online_payment_id: UUID
    confirmation_url: str  # redirect to ЮKassa — never null for redirect flow


class ClientPaymentStatusResponse(ResponseData):
    """Coarse payment status (CPAY-03 anti-oracle).

    Only 'pending' | 'succeeded' | 'canceled' — never activation or membership details.
    Phase 999.4 D-11: receipt_url exposed when a ЮKassa fiscal receipt exists and succeeded.
    Phase 999.5 D-09/D-10: receipt_email and receipt_phone for post-payment receipt display.
    """

    id: UUID
    status: str  # Literal['pending', 'succeeded', 'canceled'] at runtime
    receipt_url: str | None = None    # wire: receiptUrl; None if not yet available (D-11 honest)
    receipt_email: str | None = None  # wire: receiptEmail — D-09 info display
    receipt_phone: str | None = None  # wire: receiptPhone — D-10 phone-fallback receipt contact


# ---------------------------------------------------------------------------
# Phase 999.5 Plan 01 — onboarding profile write + /client/me response schemas
# ---------------------------------------------------------------------------


class ClientProfileUpdateRequest(ResponseData):
    """PATCH /client/me body — onboarding profile write (Phase 999.5 D-08).

    All fields optional (partial update). camelCase wire via alias_generator.
    first_name writes to clients.first_name (wire: firstName — D-06).
    goal, height_cm, weight_kg, onboarding_completed: new fields (Phase 999.5).
    email: separate write path for receipt gate (D-02/D-10).

    NO server-side validation logic here — clamping/enum/email-format enforced
    in Plan 02 service layer. Wire-shape schema only.
    """

    first_name: str | None = None            # wire: firstName — D-06
    goal: str | None = None                  # wire: goal — D-07 (4-value enum enforced in service)
    height_cm: int | None = None             # wire: heightCm
    weight_kg: int | None = None             # wire: weightKg
    onboarding_completed: bool | None = None  # wire: onboardingCompleted — D-05
    email: str | None = None                 # wire: email — D-02/D-10 receipt-email gate


class ClientMeResponse(ResponseData):
    """GET /client/me profile payload — includes onboarding + body-metrics fields (Phase 999.5).

    camelCase wire via alias_generator=to_camel on ResponseData base:
      first_name → firstName, last_name → lastName, height_cm → heightCm,
      weight_kg → weightKg, onboarding_completed_at → onboardingCompletedAt.
    """

    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    goal: str | None = None                          # wire: goal
    height_cm: int | None = None                     # wire: heightCm
    weight_kg: int | None = None                     # wire: weightKg
    onboarding_completed_at: datetime | None = None  # wire: onboardingCompletedAt (D-05)


# ---------------------------------------------------------------------------
# Phase 999.4 Plan 02 — promo code validate schemas (D-06)
# ---------------------------------------------------------------------------


class ClientPromoValidateRequest(ResponseData):
    """POST /client/promo/validate request body (D-06).

    camelCase wire: code, kind, planId (via alias_generator=to_camel on ResponseData).
    Client passes ONLY the code + product kind + planId — never a price (T-999.4-04).
    Server reads plan price and computes authoritative discounted amount.
    """

    code: str      # raw promo code (server normalizes to upper)
    kind: str      # 'sub' | 'pt' (maps to 'membership' | 'pt_package' server-side)
    plan_id: UUID  # wire: planId


class ClientPromoValidateResponse(ResponseData):
    """Promo code validate response — server-authoritative discounted amounts (D-06).

    camelCase wire: discountKopecks, newAmountKopecks, discountType.
    All amounts in integer kopecks (BigInteger discipline — no float, no Decimal).
    """

    discount_kopecks: int    # wire: discountKopecks — computed discount
    new_amount_kopecks: int  # wire: newAmountKopecks — authoritative final amount
    discount_type: str       # wire: discountType — 'percentage' | 'fixed'
