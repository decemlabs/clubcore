"""Async SQLAlchemy engine + session, lifespan-managed (D-06, D-07)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models. Future business modules subclass this."""


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
