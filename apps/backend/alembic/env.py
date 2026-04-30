"""Async Alembic env.py (DB-01).

Reads DATABASE_URL from app.core.config.Settings — NOT from alembic.ini's
sqlalchemy.url placeholder. Uses async_engine_from_config + connection.run_sync
cookbook pattern required for asyncpg driver.

Do NOT import the FastAPI application factory module — that would trigger
FastAPI lifespan + structlog configuration during `alembic revision` /
`alembic upgrade` (RESEARCH.md Pitfall 2).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Alembic Config object — provides access to values within alembic.ini.
config = context.config

# Configure stdlib logging from alembic.ini's [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate. Phase A: empty (no models yet); future business
# modules subclass Base, populating Base.metadata at import time.
target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    """Synchronous migration runner invoked via connection.run_sync()."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Build an async engine and bridge to sync migrations via run_sync."""
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = str(settings.database_url)

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Online (async) migration entry — the only mode supported in this project."""
    asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    """Offline migrations are not used; async path always runs."""
    raise NotImplementedError("Offline migrations not supported in async mode")


run_migrations_online()
