"""Domain error hierarchy + FastAPI exception handlers (D-12, D-13)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base domain error. Subclasses set class-level `code` and `status_code`."""

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str = "", *, fields: dict[str, object] | None = None) -> None:
        self.message = message
        self.fields = fields
        super().__init__(message)


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403


class CsrfMismatch(AppError):  # noqa: N818
    """Double-submit CSRF check failure (Phase 6 D-08, D-21).

    Raised by `app.core.dependencies.verify_csrf` when the `clubcore_csrf`
    cookie and `X-CSRF-Token` header are missing or do not match under
    constant-time compare. Distinct from `ForbiddenError` so the frontend
    fetcher can branch: `csrf_mismatch` → refresh CSRF cookie + retry once;
    `forbidden` → propagate as user-actionable error.
    """

    code = "csrf_mismatch"
    status_code = 403


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422


class ClientEmailRequiredForOnlinePaymentError(ValidationAppError):
    """Raised by online_payments.service.sell_* when clients.email IS NULL.

    Phase 49 PAY-06 / D-49-12. Error code is LOCKED LITERAL per
    REQUIREMENTS.md PAY-06 + ROADMAP.md Phase 49 success-criterion #3:
    ``client_email_required_for_online_payment``.
    """

    code = "client_email_required_for_online_payment"
    status_code = 422


class NoActivePtPackageError(ValidationAppError):
    """Raised by client_portal.service when a client has no active PT-package.

    Phase 70 CBOOK-04 / D-70-03. HTTP 422 so the PWA routes the user to
    Plans/Checkout rather than showing a generic conflict error. Distinct
    from PtPackageNotActiveError (409 ConflictError from bookings domain) —
    that error is internal to the staff booking path and uses a different
    status code. client_portal.service maps it to this 422 error so
    client_portal never imports app.modules.bookings (D-20-MODULE).
    """

    code = "no_active_pt_package"
    status_code = 422


class ServiceUnavailableAppError(AppError):
    """503 — upstream integration transient failure (Phase 49 D-49-10)."""

    code = "service_unavailable"
    status_code = 503


class BadGatewayAppError(AppError):
    """502 — upstream integration permanent failure (Phase 49 D-49-10)."""

    code = "bad_gateway"
    status_code = 502


class InvalidAccessToken(AppError):  # noqa: N818
    """JWT decode/expire failure (Phase 4 — used by app.core.security.decode_access_token)."""

    code = "invalid_token"
    status_code = 401


class InvalidPassword(AppError):  # noqa: N818
    """Argon2id verify mismatch / malformed hash.

    Phase 4 — used by app.core.security.verify_password.

    Phase 5 AUTH-EP-02 timing equivalence: callers always run verify_password (with a
    sentinel hash for user-not-found) so this exception fires regardless of whether the
    email exists, masking enumeration.
    """

    code = "invalid_credentials"
    status_code = 401


class InvalidSession(AppError):  # noqa: N818
    """UUID parse failure on cc_access sub claim (Phase 23 D-23-11/D-23-12).

    Wrap site: app.core.dependencies.get_current_user (UUID(claims.sub)).
    Distinct from InvalidAccessToken so FE branches:
      - code='invalid_token' → token expired, auto-refresh UX
      - code='invalid_session' → cookie tampered, force re-login UX
    """

    code = "invalid_session"
    status_code = 401


class RateLimited(AppError):  # noqa: N818
    """Per-actor throttle exhausted (Phase 5 AUTH-EP-03 — 5 failed logins / 15 min)."""

    code = "rate_limited"
    status_code = 429


class ClientNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted client."""

    code = "client_not_found"
    status_code = 404


class PhoneExistsError(ConflictError):
    """Raised on POST/PATCH when phone collides with an alive client (Phase 8 D-11)."""

    code = "phone_exists"
    status_code = 409


class InvalidPhoneError(ValidationAppError):
    """Raised on POST/PATCH when phone fails E.164 regex validation (Phase 8 D-10)."""

    code = "invalid_phone"
    status_code = 422


class PlanNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted plan."""

    code = "plan_not_found"
    status_code = 404


class PlanNameExistsError(ConflictError):
    """Raised on POST/PATCH when name collides with an alive plan (Phase 16 D-02).

    Discriminated against IntegrityError by service.py:_is_plan_name_conflict
    checking constraint name "uq_membership_plans_name_alive".
    """

    code = "plan_name_exists"
    status_code = 409


class PlanInactiveError(ConflictError):
    """Raised on POST /memberships when target plan.active=False (Phase 17 D-02).

    Service-layer defence against UI bypass: the reception sell screen filters
    via ?active=true (Phase 16 D-08), but a malformed/replayed POST can still
    reference a deactivated plan.
    """

    code = "plan_inactive"
    status_code = 409


class PlanInUseError(ConflictError):
    """Raised on DELETE /membership-plans when FK fk_memberships_plan_id_membership_plans
    rejects the delete (Phase 17 D-05).

    Discriminated against IntegrityError by service.py:_is_plan_in_use_conflict
    checking the constraint name. Per D-06: ANY membership row blocks deletion
    (including cancelled and expired — they keep audit-trail FK references).
    """

    code = "plan_in_use"
    status_code = 409


class CannotRenewCancelledError(ConflictError):
    """Raised on POST /memberships/{id}/renew when source status is 'cancelled'.

    Phase 26 MEM-REN-02 / D-26-09. Rationale: cancellation is terminal /
    intentional revocation; renewal would mask cancellation intent. Operator
    must sell a NEW membership via POST /api/v1/memberships instead. If owner
    needs an "uncancel" path, that is a separate endpoint (currently backlog —
    CONTEXT.md Deferred).
    """

    code = "cannot_renew_cancelled"
    status_code = 409


class PlanArchivedError(ConflictError):
    """Raised on POST /memberships/{id}/renew when source.plan is soft-deleted.

    Phase 26 MEM-REN-02 / D-26-08. Distinct from PlanInactiveError
    (active=False = paused but alive — renewal ALLOWED for inactive plans per
    D-26-08). Renewal cannot use a plan that owner archived. Operator must
    sell a new membership using a current alive plan instead. Discriminated
    by repository.get_plan_for_renewal returning (plan, is_archived=True).
    """

    code = "plan_archived"
    status_code = 409


class InvalidTransitionError(ConflictError):
    """Raised on POST /memberships/{id}/cancel for non-active source state (Phase 17 D-12).

    Constructor populates `fields={'from_status': ..., 'to_status': ...}` packed
    into the response envelope's `fields` key (per AppError.__init__ signature at
    core/exceptions.py:13-16).

    Usage:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )
    """

    code = "invalid_transition"
    status_code = 409


class FreezeLimitExceededError(ConflictError):
    """Raised on POST /memberships/{id}/freeze when cumulative freeze days
    would exceed freeze_days_limit_snapshot (Phase 25 MEM-FRZ-04).

    Constructor:
        raise FreezeLimitExceededError(
            "freeze_limit_exceeded",
            fields={"limit": snapshot_limit, "used": days_used},
        )
    """

    code = "freeze_limit_exceeded"
    status_code = 409


class AlreadyFrozenError(ConflictError):
    """Raised on POST /memberships/{id}/freeze when partial unique index
    uq_membership_freeze_periods_active_per_membership rejects concurrent
    INSERT (Phase 25 MEM-FRZ-TEST-03 race).

    Discriminated against IntegrityError by service.py:_is_already_frozen_conflict
    checking constraint name.
    """

    code = "already_frozen"
    status_code = 409


class MembershipNotFoundError(NotFoundError):
    """Raised when GET / POST cancel references a non-existent membership id."""

    code = "membership_not_found"
    status_code = 404


class NoActiveMembershipError(ConflictError):
    """Raised by visits service when client has no active membership today (Phase 19 VIS-03).

    Reception path: 409 visible to UI. Bot path: caught by Phase 20 handler and
    mapped to a generic Russian DM (no oracle leak — Pitfall 8).
    """

    code = "no_active_membership"
    status_code = 409


class DuplicateCheckinError(ConflictError):
    """Raised when (client_id, gym_date) UNIQUE INDEX trips (Phase 19 D-08, VIS-TEST-01).

    Service helper _is_duplicate_visit_conflict translates IntegrityError on
    constraint name uq_visits_client_id_gym_date.

    Constructor convention:
        raise DuplicateCheckinError(
            "duplicate_checkin",
            fields={"client_id": str(client_id), "gym_date": str(gym_date)},
        )
    """

    code = "duplicate_checkin"
    status_code = 409


class OutsideGymHoursError(ConflictError):
    """Raised when wall-clock MSK time is outside [gym_hours_start, gym_hours_end) (Phase 19 D-10).

    Constructor convention:
        raise OutsideGymHoursError(
            "outside_gym_hours",
            fields={"open": gym_hours_start.isoformat(), "close": gym_hours_end.isoformat()},
        )
    """

    code = "outside_gym_hours"
    status_code = 409


class VisitNotFoundError(NotFoundError):
    """Raised by GET /api/v1/visits/{id} on missing row (Phase 19 VIS-EP-02)."""

    code = "visit_not_found"
    status_code = 404


class ClientNotLinkedError(NotFoundError):
    """Bot-path: telegram_user_id has no matching alive Client row (Phase 19 D-12).

    Phase 20 handler maps this to a generic Russian DM (no oracle leak about
    whether the account exists — Pitfall 8). NOT raised on the reception path.
    """

    code = "client_not_linked"
    status_code = 404


class TrainerNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted trainer."""

    code = "trainer_not_found"
    status_code = 404


class TrainerInUseError(ConflictError):
    """Raised on DELETE /trainers/{id} when FK fk_pt_sessions_trainer_id_trainers
    rejects the delete (Phase 31 TRN-05, D-31-07).

    Pre-emptive mapping for Phase 34 pt_sessions FK. Discriminated against IntegrityError
    by service.py:_is_fk_violation checking pgcode == '23503'.
    """

    code = "trainer_in_use"
    status_code = 409


# ─────────────────────────────────────────────────────────────────────────────
# Phase 43 multi-user admin module (USERS-01..05).
# Service-layer domain errors mapped to HTTP per the AppError handler below.
# ─────────────────────────────────────────────────────────────────────────────


class UserNotFoundError(NotFoundError):
    """Raised when target user_id is missing or soft-deleted (D-43-16/17/18)."""

    code = "user_not_found"
    status_code = 404


class EmailAlreadyActiveError(ConflictError):
    """Raised when POST /users targets an email with an active user (D-43-13)."""

    code = "email_already_active"
    status_code = 409


class UserAlreadyInactiveError(ConflictError):
    """Raised when PATCH /users/{id}/deactivate hits an already-inactive user (D-43-16)."""

    code = "user_already_inactive"
    status_code = 409


class UserNotInactiveError(ConflictError):
    """Raised when PATCH /users/{id}/reactivate hits an already-active user (D-43-17)."""

    code = "user_not_inactive"
    status_code = 409


class CannotDeactivateSelfError(ConflictError):
    """Raised when the actor tries to deactivate themselves (D-43-16)."""

    code = "cannot_deactivate_self"
    status_code = 409


class CannotDeleteSelfError(ConflictError):
    """Raised when the actor tries to soft-delete themselves (D-43-18)."""

    code = "cannot_delete_self"
    status_code = 409


class CannotDeactivateLastOwnerError(ConflictError):
    """Raised when deactivating the target would leave zero active owners (D-43-16)."""

    code = "cannot_deactivate_last_owner"
    status_code = 409


class CannotDeleteLastOwnerError(ConflictError):
    """Raised when soft-deleting the target would leave zero active owners (D-43-18)."""

    code = "cannot_delete_last_owner"
    status_code = 409


class InvitationNotFoundError(NotFoundError):
    """Raised when POST /users/invitations/{id}/revoke hits a missing token (D-43-19)."""

    code = "invitation_not_found"
    status_code = 404


class InvitationAlreadyAcceptedError(ConflictError):
    """Raised when the invitation token is already consumed (D-43-19).

    Same code is used for both pre-check (consumed_at IS NOT NULL on get) and
    race-loss (UPDATE...RETURNING returned zero rows because a concurrent
    consume already won). Mirrors v1.1 refresh-rotation race-loss discipline.
    """

    code = "invitation_already_accepted"
    status_code = 409


class InvitationExpiredError(ConflictError):
    """Raised when revoke_invitation hits an expired token (WR-06 / D-43-19 extension).

    Distinct from InvitationAlreadyAcceptedError: an expired token has
    consumed_at IS NULL AND expires_at <= now(). The owner UI distinguishes
    "expired" from "already accepted" via the response code.
    """

    code = "invitation_expired"
    status_code = 409


class PayloadTooLargeError(AppError):
    """Raised when an upload body exceeds the enforced size cap (Phase 92 ATT-02).

    HTTP 413 — the client must reduce the file size and retry.
    Mapped via the shared AppError handler; no special response envelope needed.
    """

    code = "payload_too_large"
    status_code = 413


class UnsupportedMediaTypeError(AppError):
    """Raised when magic-byte validation rejects the uploaded file type (Phase 92 ATT-02).

    HTTP 415 — the file's magic bytes do not match the JPEG/PNG/WebP allowlist.
    Content-Type header is never trusted (T-92-05 LOCKED INVARIANT).
    """

    code = "unsupported_media_type"
    status_code = 415


# ─────────────────────────────────────────────────────────────────────────────
# Phase 112 payments domain errors (REF-01).
# ─────────────────────────────────────────────────────────────────────────────


class CannotRefundRefundError(ConflictError):
    """Raised when the actor tries to refund a refund row itself (Phase 112 REF-01).

    A refund row has subject_kind='refund'; issuing a second-order refund is
    semantically invalid in the append-only ledger model.
    """

    code = "cannot_refund_refund"
    status_code = 409


class OverRefundError(ConflictError):
    """Raised when requested amount_kopecks > original payment amount (Phase 112 REF-01).

    The service compares amount_kopecks against the original sale row's
    amount_kopecks before inserting the negative-amount refund row.
    """

    code = "over_refund"
    status_code = 409


def register_exception_handlers(app: FastAPI) -> None:
    """Attach AppError handler to the FastAPI app. Called once during create_app()."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Normalise FastAPI body/query/path validation 422s to the domain envelope.

        Phase 64 FRZ-06 / CR-WR-02: the curated spec models every 422 as the
        ``{code, message, fields}`` envelope (shared ``422_ValidationError``
        response). FastAPI's default handler returns ``{detail: [...]}``
        (``HTTPValidationError``), which contradicts the frozen contract. This
        handler maps each validation error to ``fields[<dotted-loc>] = <msg>``
        so the runtime emits exactly what the spec promises — matching the
        uniform ``ValidationAppError`` (code ``validation_error``) shape.
        """
        fields: dict[str, object] = {}
        for err in exc.errors():
            loc = tuple(str(part) for part in err.get("loc", ()))
            # Drop the leading source segment ("body"/"query"/"path") for a
            # clean field key; fall back to "__root__" for top-level errors.
            key = ".".join(loc[1:]) if len(loc) > 1 else (loc[0] if loc else "__root__")
            fields[key] = err.get("msg", "")
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request validation failed",
                "fields": fields,
            },
        )
