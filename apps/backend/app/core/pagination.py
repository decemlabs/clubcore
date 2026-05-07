"""Pagination contract: PageQuery (request) + PaginatedData[T] (response payload) (D-10, API-04).

Phase 4 clean break (D-10): the v1.0 LimitOffsetParams + Page[T] (limit/offset shape) are
DELETED — no in-tree consumers existed (only /healthz, which doesn't paginate). Phase 5+
list endpoints declare:

    @router.get(..., response_model=ResponseEnvelope[PaginatedData[ClientResponse]])
    async def list_clients(query: PageQuery = Depends(), ...): ...

Wire form: { "data": { "items": [...], "total": N, "page": 1, "pageSize": 20 } }
Python attributes: page_size (snake_case); camelCase serialization is inherited from
ContractModel via alias_generator=to_camel (D-09).
"""

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData


class PageQuery(BackendSchemaBase):
    """Page-based pagination query params for list endpoints (D-10).

    Bounds match the deleted LimitOffsetParams.limit (1..100); default page_size=20.
    Wire: ?page=1&pageSize=20 (BackendSchemaBase inherits alias_generator=to_camel and
    accepts both snake_case and camelCase via validate_by_name + validate_by_alias).
    """

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedData[T](ResponseData):
    """Generic paginated payload — sits inside ResponseEnvelope[T] on the wire.

    PEP 695 generic (D-11). Concrete usage:
        response_model=ResponseEnvelope[PaginatedData[ClientResponse]]
    Wire shape: { "items": [...], "total": N, "page": P, "pageSize": S } (camelCase).
    """

    items: list[T]
    total: int
    page: int
    page_size: int
