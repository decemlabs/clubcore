"""Domain error hierarchy + FastAPI exception handlers (D-12, D-13)."""

from fastapi import FastAPI, Request
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

    Raised by `app.core.dependencies.verify_csrf` when the `sportzal_csrf`
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
