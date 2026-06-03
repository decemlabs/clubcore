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
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Register all ORM models with Base.metadata for autogenerate (TEST-08 / Phase 5 INFRA-03).
import app.modules.auth.models
import app.modules.auth.password_reset_token_model  # Phase 41 INFRA-38 / 0025 — D-41-04
import app.integrations.email.models  # Phase 42 D-42-33 / 0026 -- EMAIL-01 (email_send_log)
import app.modules.bookings.models  # Phase 38 BOOK-01 / 0017
import app.modules.client_auth.models  # Phase 68 CAUTH / 0043+0044
import app.modules.clients.models
import app.modules.fiscal_receipts.models  # Phase 50 FISCAL-01 / 0035
import app.modules.memberships.models
import app.modules.online_payments.models  # Phase 49 PAY-01 / 0034
import app.modules.online_refunds.models  # Phase 51 REFUND-01 / 0036
import app.modules.payroll.models  # Phase 58 PAY-01..06 / 0041
import app.modules.payments.models  # Phase 32 PAY-01
import app.modules.pt_packages.models  # Phase 33 PT-01 / PT-04
import app.modules.pt_sessions.models  # Phase 34 PT-14 / 0015
import app.modules.schedule.models  # Phase 38 SLOT-01 / 0016
import app.modules.trainers.models  # Phase 31 TRN-01
import app.modules.visits.models
import app.modules.payment_methods.models  # Phase 79 PAYM-01..04 / 0052
import app.core.audit_models  # noqa: F401

# Alembic Config object — provides access to values within alembic.ini.
config = context.config

# Configure stdlib logging from alembic.ini's [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate. Phase A: empty (no models yet); future business
# modules subclass Base, populating Base.metadata at import time.
target_metadata = Base.metadata


def _include_object(
    object_: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Skip raw-DDL GIN trigram expression indexes from autogenerate comparison.

    These indexes are created via op.execute() in the Phase 8 clients
    migration because `lower(col) gin_trgm_ops` cannot be reliably
    expressed in SQLAlchemy `__table_args__`. Excluding them here keeps
    `alembic check` clean (TEST-08 supporting; Pitfall 1 from RESEARCH.md).

    Only affects autogenerate diffing; actual upgrade/downgrade sequences
    are unchanged.
    """
    return not (
        type_ == "index"
        and name
        in (
            "ix_clients_last_name_trgm",
            "ix_clients_first_name_trgm",
            "uq_clients_phone_alive",
            "uq_membership_plans_name_alive",
            "uq_membership_freeze_periods_active_per_membership",
            "uq_trainers_phone_alive",  # Phase 31: partial index, skip autogenerate drift
            "uq_pt_package_plans_name_alive",  # Phase 33: partial expression index
            # Phase 33: partial index on (client_id) WHERE status='active'
            "uq_pt_packages_active_per_client",
            # Phase 41 INFRA-38: partial UNIQUE on lower(email) WHERE deleted_at IS NULL
            "uq_users_email_active",
            # Phase 42 D-42-18: index has `recorded_at DESC` expression in
            # migration DDL; SQLAlchemy Index can't surface DESC on the second
            # column at the ORM layer, so autogenerate sees a column-vs-expr
            # mismatch. Skip — same D-25-05 lineage as the partial-index entries.
            "ix_email_send_log_to_addr_recorded",
        )
    )


def do_run_migrations(connection: Connection) -> None:
    """Synchronous migration runner invoked via connection.run_sync()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,  # Pitfall 1: skip raw-DDL GIN trgm indexes
    )
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
