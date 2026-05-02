"""Async SQLAlchemy engine + session, lifespan-managed (D-06, D-07).

Phase 4 additions (D-15..D-19, INFRA-01, INFRA-02):
- Base.metadata uses standard SA naming convention (ix/uq/ck/fk/pk template).
- UUIDPkMixin: Postgres-native gen_random_uuid() primary key (PG13+).
- TimestampMixin: server-side func.now() on insert + update; TIMESTAMPTZ.
- SoftDeleteMixin: deleted_at column; composing models add the partial unique index.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from fastapi import FastAPI, Request
from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models. Future business modules subclass this.

    Phase 4 (D-19, INFRA-01): naming_convention is attached BEFORE the first business
    migration so Alembic produces deterministic constraint names. Phase 4 SC #3 verifies
    autogenerate-on-clean produces an empty diff with the convention in place.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPkMixin:
    """Postgres-native UUIDv4 PK (D-15, INFRA-02).

    PG13+ ships gen_random_uuid() without the pgcrypto extension; PG16 (the project's
    pinned major) is well within range. INSERT without explicit `id` returns the
    generated UUID via RETURNING — seeds and tests do NOT pass `id=` on insert.
    """

    id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Server-side timestamps (D-16, INFRA-02).

    Both columns use func.now() so the database is the source of truth for the clock —
    multi-instance / Python clock drift becomes irrelevant. TIMESTAMPTZ (timezone=True),
    never naive.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """Soft-delete column (D-17, INFRA-02).

    Plain index on `deleted_at` is intentionally NOT added — query patterns are
    partial-index based on `WHERE deleted_at IS NULL` (alive-bias) attached to specific
    business uniqueness constraints. Phase 8's Client model will add:

        __table_args__ = (
            Index(
                "uq_clients_phone_alive", "phone", unique=True,
                postgresql_where=text("deleted_at IS NULL"),
            ),
        )

    Repository helpers (`list_alive` / `get_alive`) enforce the alive filter at the
    service layer (CLIENTS-09, Phase 8).
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: create engine + sessionmaker on startup, dispose on shutdown."""
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    try:
        yield
    finally:
        await engine.dispose()


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request AsyncSession from app.state.sessionmaker (D-07)."""
    session_factory = request.app.state.sessionmaker
    async with session_factory() as session:
        yield session
