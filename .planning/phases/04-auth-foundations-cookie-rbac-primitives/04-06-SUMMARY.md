---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: "06"
subsystem: backend/core
tags: [pagination, pydantic, contracts, api]
dependency_graph:
  requires: [04-05]
  provides: [PageQuery, PaginatedData]
  affects: [Phase 8 list endpoints, Phase 9 OpenAPI]
tech_stack:
  added: []
  patterns:
    - PEP 695 generic (class PaginatedData[T](ResponseData)) — Python 3.12 native syntax
    - Page-based pagination contract (page + page_size) replacing limit/offset
key_files:
  created: []
  modified:
    - apps/backend/app/core/pagination.py
decisions:
  - D-10: PageQuery + PaginatedData[T] shape in pagination.py; old limit/offset (LimitOffsetParams + Page[T]) deleted — clean break
  - D-11: PEP 695 generics only; no typing.Generic[T] or TypeVar anywhere
metrics:
  duration: 5m
  completed_date: "2026-05-02"
---

# Phase 04 Plan 06: Pagination Contract Rewrite Summary

**One-liner:** Clean-break rewrite of `pagination.py` from limit/offset to page-based `PageQuery + PaginatedData[T]` using PEP 695 generics, inheriting camelCase wire format from `ContractModel`.

## What Was Built

`apps/backend/app/core/pagination.py` rewritten per decision D-10. The old `LimitOffsetParams` (limit/offset shape) and `Page[T]` are deleted. Two new classes replace them:

- `PageQuery(RequestContract)`: `page: int = Field(default=1, ge=1)`, `page_size: int = Field(default=20, ge=1, le=100)`. Inherits `extra='forbid'` and `alias_generator=to_camel` — accepts both `?page=1&pageSize=20` (camelCase wire) and `?page=1&page_size=20` (snake_case Python).
- `PaginatedData[T](ResponseData)`: PEP 695 generic with `items: list[T]`, `total: int`, `page: int`, `page_size: int`. Wire form serializes `page_size` as `pageSize` via inherited `alias_generator=to_camel`.

## Acceptance Criteria — Evidence

```
class PageQuery(RequestContract):       ✓ (1 match)
class PaginatedData[T](ResponseData):  ✓ (1 match)
LimitOffsetParams                       ✓ (0 matches — deleted)
Page[T]                                 ✓ (0 matches — deleted)
limit: int                              ✓ (0 matches — deleted)
offset: int                             ✓ (0 matches — deleted)
page: int = Field(default=1, ge=1)     ✓ (1 match)
page_size: int = Field(default=20, ge=1, le=100)  ✓ (1 match)
from app.core.schemas import RequestContract, ResponseData  ✓ (1 match)
TypeVar|Generic[                        ✓ (0 matches — PEP 695 only)
```

## camelCase Wire Round-Trip — Evidence

```python
pd = PaginatedData[_Item](items=[_Item(full_name='a'), _Item(full_name='b')], total=2, page=1, page_size=20)
dump = pd.model_dump(by_alias=True)
# Result: {'items': [{'fullName': 'a'}, {'fullName': 'b'}], 'total': 2, 'page': 1, 'pageSize': 20}
```

Python `page_size` → wire `pageSize`: confirmed via `alias_generator=to_camel` inherited from `ContractModel`.

## Tooling Results

- `uv run mypy app/core/pagination.py`: Success — no issues found (strict mode)
- `uv run ruff check app/core/pagination.py`: All checks passed
- `uv run lint-imports`: 3 contracts kept, 0 broken (46 files analyzed)
- `uv run pytest tests/integration/test_healthz.py -q`: 2 passed (no regression — /healthz doesn't paginate)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The threat mitigations T-04-22 through T-04-24 are implemented as specified:
- T-04-22 (DoS via unbounded page_size): `le=100` cap in place
- T-04-23 (DoS via negative/zero page): `ge=1` on `page` in place
- T-04-24 (over-posting query params): `extra='forbid'` inherited from `RequestContract`

## Self-Check: PASSED

- `apps/backend/app/core/pagination.py`: FOUND
- commit `cbe251c`: FOUND
