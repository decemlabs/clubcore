"""Unit tests for app.core.pagination — PageQuery + PaginatedData[T] (D-29, API-04)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.pagination import PageQuery, PaginatedData
from app.core.schemas import ContractModel

# ---- PageQuery defaults + bounds ----


def test_page_query_defaults() -> None:
    q = PageQuery()
    assert q.page == 1
    assert q.page_size == 20


def test_page_query_accepts_camel_case_page_size() -> None:
    q = PageQuery.model_validate({"pageSize": 50})
    assert q.page_size == 50


def test_page_query_rejects_page_below_one() -> None:
    with pytest.raises(ValidationError):
        PageQuery(page=0)


def test_page_query_rejects_page_size_above_one_hundred() -> None:
    with pytest.raises(ValidationError):
        PageQuery(page_size=101)


def test_page_query_rejects_page_size_below_one() -> None:
    with pytest.raises(ValidationError):
        PageQuery(page_size=0)


def test_page_query_rejects_unknown_query_param() -> None:
    # PageQuery extends RequestContract (extra='forbid')
    with pytest.raises(ValidationError):
        PageQuery.model_validate({"page": 1, "unknown": "boom"})


# ---- PaginatedData[T] camelCase wire form ----


class _Item(ContractModel):
    full_name: str


def test_paginated_data_dump_emits_page_size_camel_on_wire() -> None:
    pd = PaginatedData[_Item](
        items=[_Item(full_name="a"), _Item(full_name="b")],
        total=2,
        page=1,
        page_size=20,
    )
    dump = pd.model_dump(by_alias=True)
    assert dump == {
        "items": [{"fullName": "a"}, {"fullName": "b"}],
        "total": 2,
        "page": 1,
        "pageSize": 20,
    }


def test_paginated_data_python_attr_uses_snake_case() -> None:
    pd = PaginatedData[_Item](items=[], total=0, page=1, page_size=10)
    assert pd.page_size == 10  # snake_case in Python; pageSize on wire


# ---- v1.0 shape gone (D-10 clean break) ----


def test_old_limit_offset_classes_are_deleted() -> None:
    import app.core.pagination as p

    assert not hasattr(p, "LimitOffsetParams"), "v1.0 LimitOffsetParams must be removed"
    assert not hasattr(p, "Page"), "v1.0 Page[T] (limit/offset) must be removed"
