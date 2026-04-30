"""Structlog configuration. Renderer driven by Settings.environment (D-15)."""

import structlog
from structlog.contextvars import merge_contextvars

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog once during create_app(). Idempotent within process."""
    shared_processors: list[structlog.types.Processor] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor
    if settings.environment == "dev":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
