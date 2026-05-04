"""Clients service — orchestration between router and repository (Phase 8 D-03/D-19).

Module-level async functions (D-18). Each mutation function:
  1. Validates / prepares data
  2. Calls `repository.<fn>` (D-02 — service does NOT import the `Client` ORM at runtime)
  3. Handles `IntegrityError` on `uq_clients_phone_alive` → raises `PhoneExistsError` (D-11)
  4. `await audit.emit(session, ...)` (D-03 co-transactional)
  5. `await session.flush()` to surface DB-level constraint conflicts before route exit
  6. `await session.commit()` to persist the unit of work (Phase 12.1 — was missing pre-fix,
     so successful 201/200/204 responses were rolled back at request scope exit; mirrors
     the auth/service.py pattern). Tests use SAVEPOINT-mode session, so commit becomes a
     nested-transaction release the outer fixture rolls back.

Architectural boundary (D-02 / CLIENTS-09):
  - `from app.modules.clients import repository` — fine.
  - The runtime module never imports the `Client` ORM. mypy still type-checks
    via the repository return-type chain.

Audit emit ordering:
  - create_client: insert → flush (may raise IntegrityError) → emit on success.
    For inserts the IntegrityError surfaces only on flush, so we can't emit
    before confirming the row took.
  - update_client / soft_delete_client: mutate → emit → flush.
    For update_client we still flush early on phone change to surface a phone
    collision before emitting (see body).

D-08 audit payload shapes (PII-aware — no full state dump):
  - client_created      : {full_name, phone, has_email, has_telegram}
  - client_updated      : {changed_fields, previous_phone?}
  - client_soft_deleted : {full_name, phone}  (captured BEFORE deleted_at is set)

D-09 no-op skip:
  - update_client returns the current ClientResponse without emitting / flushing
    when `repository.update_client` reports zero changed fields.

Service does NOT re-check RBAC; the router-layer `require_permission` dependency
(Plan 07) gates access before service is called.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import ClientNotFoundError, PhoneExistsError
from app.core.pagination import PaginatedData
from app.modules.clients import repository
from app.modules.clients.schemas import (
    ClientCreateRequest,
    ClientListQuery,
    ClientResponse,
    ClientUpdateRequest,
)

if TYPE_CHECKING:
    from app.modules.clients.models import Client


async def list_clients(
    session: AsyncSession,
    query: ClientListQuery,
) -> PaginatedData[ClientResponse]:
    """Return paginated alive clients matching the query (CLIENTS-03/04).

    Read-side: no audit emit, no actor required. RBAC (`VIEW`, `CLIENTS`) is
    enforced at the router layer (Plan 07).
    """
    page = await repository.list_alive(session, query)
    return PaginatedData[ClientResponse](
        items=[ClientResponse.model_validate(c) for c in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_client(
    session: AsyncSession,
    client_id: UUID,
) -> ClientResponse:
    """Return alive client by id; raise 404 for missing/soft-deleted (CLIENTS-05)."""
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")
    return ClientResponse.model_validate(client)


def _full_name(client: "Client") -> str:
    """Render a Client's full name for audit payloads (last first [middle])."""
    parts = [client.last_name, client.first_name]
    if client.middle_name:
        parts.append(client.middle_name)
    return " ".join(parts)


def _is_phone_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_clients_phone_alive` (D-11)."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_clients_phone_alive":
        return True
    return "uq_clients_phone_alive" in str(exc.orig)


async def create_client(
    session: AsyncSession,
    actor: CurrentUser,
    data: ClientCreateRequest,
) -> ClientResponse:
    """Create a new client (CLIENTS-06).

    Order: insert → flush (surface DB constraints) → emit audit on success (D-03).
    For inserts we cannot emit before flush — the IntegrityError on
    `uq_clients_phone_alive` surfaces only when the row hits the DB. Catching
    the IntegrityError and translating to PhoneExistsError satisfies D-11.
    """
    client = await repository.insert_client(session, actor.id, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    # D-08 client_created payload: minimal PD-safe fields only
    # (no notes / birthday / emergency_contact).
    await audit.emit(
        session,
        "client_created",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=_full_name(client),
        phone=client.phone,
        has_email=client.email is not None,
        has_telegram=client.telegram_user_id is not None,
    )
    await session.commit()
    return ClientResponse.model_validate(client)


async def update_client(
    session: AsyncSession,
    actor: CurrentUser,
    client_id: UUID,
    data: ClientUpdateRequest,
) -> ClientResponse:
    """Partial update with PATCH semantics (CLIENTS-07, D-01).

    Skips audit emit + flush when no fields actually changed (D-09 no-op).
    Translates phone-uniqueness IntegrityError to PhoneExistsError (D-11).
    """
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")

    # changed_previous: dict[field_name, previous_value] — only fields that
    # actually changed value (after pydantic exclude_unset). Empty dict on no-op.
    changed_previous = await repository.update_client(session, client, data)

    if not changed_previous:
        # D-09: idempotent no-op PATCH → skip emit, skip flush, return current state.
        return ClientResponse.model_validate(client)

    # Flush early to surface phone-conflict before emitting audit (D-11). For
    # non-phone updates this is a cheap UPDATE; for phone changes it gives us
    # the IntegrityError we need to translate.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    # D-08 client_updated payload:
    #   - changed_fields: sorted list of field names that actually changed
    #   - previous_phone: only when phone was among the changed fields
    payload: dict[str, object] = {"changed_fields": sorted(changed_previous.keys())}
    if "phone" in changed_previous:
        payload["previous_phone"] = changed_previous["phone"]

    await audit.emit(
        session,
        "client_updated",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        **payload,
    )
    # SA 2.0 expires the row's attributes after flush by default. Refresh the
    # ORM-managed `updated_at` (server-side `now()`) before Pydantic
    # serialisation so the response carries the fresh value without triggering
    # an implicit lazy-load (which would raise MissingGreenlet under async).
    await session.refresh(client, attribute_names=["updated_at"])
    await session.commit()
    return ClientResponse.model_validate(client)


async def soft_delete_client(
    session: AsyncSession,
    actor: CurrentUser,
    client_id: UUID,
) -> None:
    """Soft-delete the client (CLIENTS-08).

    Owner-only enforcement happens at the router via `require_permission` (Plan 07).
    Captures `full_name` and `phone` BEFORE the soft-delete sets `deleted_at`, so
    the audit payload reflects pre-deletion state (D-08).
    """
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")

    # Capture before mutating — soft-delete only sets deleted_at, but capture
    # makes the audit payload independent of post-delete ORM state.
    captured_full_name = _full_name(client)
    captured_phone = client.phone

    await repository.soft_delete_client(session, client)

    # Emit BEFORE flush — soft-delete only flips deleted_at, no constraint risk.
    await audit.emit(
        session,
        "client_soft_deleted",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=captured_full_name,
        phone=captured_phone,
    )
    await session.flush()
    await session.commit()
