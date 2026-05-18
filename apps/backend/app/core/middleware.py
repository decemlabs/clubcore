"""ASGI middleware: request_id correlation + request timing (D-09, D-11).

Phase 41 INFRA-39 / D-41-08 adds ``ActorContextMiddleware`` — sets the
``actor_context_var`` baseline to ``None`` for every request and resets on
response exit. The real identity is written by the ``get_current_user``
dependency (``app/core/dependencies.py``) AFTER auth resolves, because
ASGI middleware runs BEFORE per-route dependencies. The middleware's
outer try/finally is what guarantees no leak across requests sharing the
same asyncio task.
"""

import time
import uuid
from typing import Any

import structlog
import structlog.contextvars
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.actor_context import actor_context_var


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


class ActorContextMiddleware(BaseHTTPMiddleware):
    """Bind ``actor_context_var`` baseline to None on each request (Phase 41 INFRA-39).

    Placed AFTER ``RequestIdMiddleware`` in execution order (i.e. added
    BEFORE it in the reversed ``add_middleware`` sequence — see
    ``register_middleware``). RequestId stays outermost so its
    structlog contextvars are bound first; ActorContext runs second on
    request and establishes the contextvar lifetime envelope.

    The middleware itself only writes ``None`` — the real ``ActorIdentity``
    is set by ``get_current_user`` (``app/core/dependencies.py``) AFTER
    auth resolves, because ASGI middleware runs BEFORE per-route
    dependencies and ``request.state.current_user`` is not yet populated
    at middleware entry. The outer try/finally is what prevents leaks
    across requests sharing the same asyncio task (Pitfall 14 lineage).

    Unauthenticated paths leave the contextvar as None (D-41-10 system-emit
    rule — audit rows from such paths get actor_email_snapshot=NULL).
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        token = actor_context_var.set(None)
        try:
            response: Response = await call_next(request)
            return response
        finally:
            actor_context_var.reset(token)


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
    - app.add_middleware(TimingMiddleware) added FIRST → innermost → runs LAST on request.
    - app.add_middleware(ActorContextMiddleware) added SECOND → middle → runs SECOND on request.
    - app.add_middleware(RequestIdMiddleware) added LAST → outermost → runs FIRST on request.

    This means RequestId binds contextvars BEFORE ActorContext sets its baseline,
    and ActorContext sits BEFORE Timing so the actor_context_var lifetime envelope
    fully contains the request-handler invocation. Reversing this order would
    silently produce timing logs without request_id correlation OR audit rows
    written outside the actor_context_var envelope.
    """
    # TODO Phase X: CORS once frontend integrates (CONTEXT.md Deferred Ideas).
    app.add_middleware(TimingMiddleware)
    # Phase 41 INFRA-39 / D-41-08 — actor_context_var baseline envelope.
    app.add_middleware(ActorContextMiddleware)
    app.add_middleware(RequestIdMiddleware)
