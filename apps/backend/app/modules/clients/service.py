"""Clients service — orchestration between router and repository (Phase 8 D-03/D-19).

Module-level async functions (D-18). Each mutation function:
  1. Validates / prepares data
  2. Calls `repository.<fn>` (D-02 — service does NOT import the `Client` ORM at runtime)
  3. Handles `IntegrityError` on `uq_clients_phone_alive` → raises `PhoneExistsError` (D-11)
  4. `await audit.emit(session, ...)` (D-03 co-transactional)
  5. `await session.flush()` to surface DB-level constraint conflicts before route exit

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

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClientNotFoundError
from app.core.pagination import PaginatedData
from app.modules.clients import repository
from app.modules.clients.schemas import ClientListQuery, ClientResponse


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
