"""ASGI middleware: request_id correlation + request timing (D-09, D-11)."""

import time
import uuid
from typing import Any

import structlog
import structlog.contextvars
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Read/generate X-Request-ID; bind structlog contextvars; echo header on response."""

    HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get(self.HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response: Response = await call_next(request)
        response.headers[self.HEADER] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Log request duration (placeholder level; expanded in observability work later)."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        structlog.get_logger().info(
            "request_complete",
            duration_ms=round(duration_ms, 2),
            status_code=response.status_code,
        )
        return response


def register_middleware(app: FastAPI) -> None:
    """Register middleware on the FastAPI app (D-11).

    add_middleware ORDER IS REVERSED from execution order (RESEARCH.md Pitfall 1):
    - app.add_middleware(TimingMiddleware) added FIRST → innermost → runs SECOND on request.
    - app.add_middleware(RequestIdMiddleware) added SECOND → outermost → runs FIRST on request.

    This means RequestId binds contextvars BEFORE Timing logs the request_complete event,
    so the timing log carries the request_id. Reversing this order would silently
    produce timing logs without request_id correlation.
    """
    # TODO Phase X: CORS once frontend integrates (CONTEXT.md Deferred Ideas).
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)
