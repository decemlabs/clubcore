"""Pagination primitives: LimitOffsetParams + generic Page[T] (BE-08)."""

from pydantic import BaseModel, Field


class LimitOffsetParams(BaseModel):
    """Bounded limit/offset pagination params for list endpoints."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class Page[T](BaseModel):
    """Generic page envelope for list responses. Mirrors the contract documented
    in CLAUDE.md Domain Conventions: never return bare arrays."""

    items: list[T]
    total: int
    limit: int
    offset: int
