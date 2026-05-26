"""Clients repository — single point of access to the `Client` ORM (CLIENTS-09, D-02).

This is the ONLY module in the codebase that imports the `Client` ORM model. The
service layer (Plan 06) calls these module-level async helpers and never executes
`select(Client)` directly. That single rule constructively guarantees CLIENTS-09:
"all queries through `list_alive` / `get_alive`" — the service layer simply has
no reference to the ORM table.

Soft-delete invariant (CLIENTS-05, CLIENTS-09): every read helper appends
`Client.deleted_at IS NULL` as the first predicate. `soft_delete_client` is
the ONLY mutation point that touches `deleted_at`.

Transaction control (D-03): NO `session.commit()` and NO `session.flush()` calls
live here. The caller (Plan 06 service) owns the transactional moment so it can
co-write the audit log row in the same UoW.

`from __future__ import annotations` is required: `list_alive` is annotated with
`PaginatedData[Client]`, and `Client` is a SQLAlchemy ORM class without a Pydantic
core schema. Without PEP 563 deferred evaluation, importing this module triggers
`PaginatedData.__class_getitem__(Client)` at runtime, which delegates to Pydantic's
generic schema-builder and raises `PydanticSchemaGenerationError`. Deferring
annotation evaluation keeps the type information for mypy while preventing the
import-time schema build (Plan 08-08 acknowledged repository import issue).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.core.sql import escape_like_pattern
from app.modules.clients.models import Client
from app.modules.clients.schemas import (
    ClientCreateRequest,
    ClientListQuery,
    ClientSort,
    ClientUpdateRequest,
    EmergencyContact,
)


async def get_alive(session: AsyncSession, client_id: UUID) -> Client | None:
    """Return alive client by id, or None for missing/soft-deleted (CLIENTS-05)."""
    stmt: Select[tuple[Client]] = select(Client).where(
        Client.id == client_id,
        Client.deleted_at.is_(None),
    )
    result: Client | None = await session.scalar(stmt)
    return result


async def list_alive(session: AsyncSession, query: ClientListQuery) -> PaginatedData[Client]:
    """Paginated list of alive clients with filters + sort applied (CLIENTS-03/04).

    Returns a `PaginatedData` instance constructed via `model_construct` to skip
    Pydantic validation against the generic parameter. The SQLAlchemy `Client`
    ORM is not a Pydantic-compatible type and `PaginatedData[Client](...)` would
    trigger a `PydanticSchemaGenerationError` at the runtime parametrisation
    step. The service layer (Plan 06) immediately re-wraps the result as
    `PaginatedData[ClientResponse]`, so skipping validation here is safe.

    Search input ``query.q`` is routed through ``escape_like_pattern`` before
    being wrapped in ``%...%`` so SQL ``LIKE`` metacharacters (``%``, ``_``,
    ``\\``) are treated as literals (CR-01 / Phase 14 PII hardening).
    """

    predicates: list[Any] = [Client.deleted_at.is_(None)]

    # D-12: q ILIKE on lower(last + ' ' + first + ' ' + coalesce(middle, '')) OR phone ILIKE.
    # Note: ClientListQuery.q is already None when shorter than 2 chars (D-12 normaliser).
    if query.q is not None:
        escaped_q = escape_like_pattern(query.q.lower())
        like_pattern = f"%{escaped_q}%"
        full_name_expr = func.lower(
            Client.last_name + " " + Client.first_name + " " + func.coalesce(Client.middle_name, "")
        )
        predicates.append(
            or_(
                full_name_expr.ilike(like_pattern),
                # phone is canonical E.164, ILIKE on raw value is sufficient
                Client.phone.ilike(f"%{escape_like_pattern(query.q)}%"),
            )
        )

    # D-13: tag exact match via ANY() — parameterised bind, no SQL injection.
    if query.tag is not None:
        predicates.append(text(":tag = ANY(clients.tags)").bindparams(tag=query.tag))

    # D-14: gender exact match
    if query.gender is not None:
        predicates.append(Client.gender == query.gender)

    # D-14: createdFrom / createdTo inclusive (DTO normalises date-only to UTC boundaries).
    if query.created_from is not None:
        predicates.append(Client.created_at >= query.created_from)
    if query.created_to is not None:
        predicates.append(Client.created_at <= query.created_to)

    # D-14: hasTelegram bool
    if query.has_telegram is True:
        predicates.append(Client.telegram_user_id.is_not(None))
    elif query.has_telegram is False:
        predicates.append(Client.telegram_user_id.is_(None))

    # Total count — same predicate list, no ORDER/LIMIT.
    total_stmt = select(func.count()).select_from(Client).where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    # Items
    stmt: Select[tuple[Client]] = select(Client).where(and_(*predicates))
    if query.sort == ClientSort.LAST_NAME_ASC:
        # tie-breaker on created_at desc to keep order stable
        stmt = stmt.order_by(Client.last_name.asc(), Client.created_at.desc())
    else:  # default CREATED_AT_DESC
        # stable tie-break on id desc
        stmt = stmt.order_by(Client.created_at.desc(), Client.id.desc())

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def insert_client(
    session: AsyncSession,
    actor_user_id: UUID,
    data: ClientCreateRequest,
) -> Client:
    """Insert a new client; caller owns the transactional flush + audit emit (D-03)."""
    emergency = data.emergency_contact.model_dump() if data.emergency_contact else None

    client = Client(
        last_name=data.last_name,
        first_name=data.first_name,
        middle_name=data.middle_name,
        phone=data.phone,
        email=data.email,
        birthday=data.birthday,
        gender=data.gender,
        tags=data.tags,
        notes=data.notes,
        emergency_contact=emergency,
        telegram_user_id=data.telegram_user_id,
        created_by_user_id=actor_user_id,
    )
    session.add(client)
    return client


async def update_client(
    session: AsyncSession,
    client: Client,
    data: ClientUpdateRequest,
) -> dict[str, object]:
    """Apply PATCH update to an existing alive Client.

    Returns a dict of {field_name: previous_value} for the fields that actually
    changed. Service layer (Plan 06) uses this to (a) decide whether to emit
    `client_updated` (D-09 no-op skip) and (b) attach `previous_phone` to the
    audit payload (D-08).
    """
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}

    for key, value in updates.items():
        # emergency_contact arrives as Pydantic instance; serialise to dict for JSONB.
        if key == "emergency_contact" and value is not None and isinstance(value, EmergencyContact):
            value = value.model_dump()
        # otherwise it's already a dict (model_dump above produced it)
        previous = getattr(client, key)
        if previous != value:
            changed[key] = previous
            setattr(client, key, value)

    return changed


async def soft_delete_client(session: AsyncSession, client: Client) -> Client:
    """Soft-delete: set deleted_at to now(); never DELETE the row (CLIENTS-08)."""
    client.deleted_at = datetime.now(tz=UTC)
    return client
