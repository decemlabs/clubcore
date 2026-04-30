"""Domain error hierarchy + FastAPI exception handlers (D-12, D-13)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base domain error. Subclasses set class-level `code` and `status_code`."""

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str, *, fields: dict[str, object] | None = None) -> None:
        self.message = message
        self.fields = fields
        super().__init__(message)


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class ValidationAppError(AppError):
    code = "validation_error"
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
