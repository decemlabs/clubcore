"""Unit tests for visits schemas (Phase 19 VIS-02 / INFRA-12 contract).

Pure Pydantic tests — no DB, no FastAPI, no fixtures beyond stdlib + pytest.

Covers:
- D-01: BackendSchemaBase extra='forbid' seals POST body to {clientId} only
- D-09: no sort field on the wire for VisitListQuery
- camelCase aliasing on VisitResponse serialisation
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.modules.visits.schemas import (
    VisitCreateRequest,
    VisitListQuery,
    VisitResponse,
)

_MSK = ZoneInfo("Europe/Moscow")


class TestVisitCreateRequest:
    """D-01: POST body sealed to {clientId}; extra='forbid' rejects tampering."""

    def test_accepts_client_id_only(self) -> None:
        """Valid request with clientId only parses to a UUID."""
        req = VisitCreateRequest.model_validate({"clientId": str(uuid4())})
        assert req.client_id is not None

    def test_accepts_client_id_snake_case(self) -> None:
        """snake_case key also accepted (validate_by_name=True from BackendSchemaBase)."""
        req = VisitCreateRequest(client_id=uuid4())
        assert req.client_id is not None

    def test_rejects_extra_field_channel(self) -> None:
        """D-01: 'channel' in body → ValidationError (BackendSchemaBase extra='forbid')."""
        with pytest.raises(ValidationError):
            VisitCreateRequest.model_validate(
                {"clientId": str(uuid4()), "channel": "telegram_bot"}
            )

    def test_rejects_extra_field_checked_in_by(self) -> None:
        """D-01: 'checkedInBy' in body → ValidationError (server-computed)."""
        with pytest.raises(ValidationError):
            VisitCreateRequest.model_validate(
                {"clientId": str(uuid4()), "checkedInBy": str(uuid4())}
            )

    def test_rejects_missing_client_id(self) -> None:
        """Required field missing → ValidationError."""
        with pytest.raises(ValidationError):
            VisitCreateRequest.model_validate({})


class TestVisitListQuery:
    """D-09: no sort enum on the wire; from/to inclusive date filters."""

    def test_from_alias_works(self) -> None:
        """'from' wire alias parses into from_ field (avoids Python keyword)."""
        q = VisitListQuery.model_validate({"from": "2026-05-01", "to": "2026-05-07"})
        assert q.from_ is not None
        assert q.to is not None
        assert q.from_ == date(2026, 5, 1)
        assert q.to == date(2026, 5, 7)

    def test_no_sort_field_accepted(self) -> None:
        """D-09: sort is not a wire field; unknown key 'sort' → ValidationError."""
        with pytest.raises(ValidationError):
            VisitListQuery.model_validate({"sort": "checked_in_at_desc"})

    def test_empty_query_has_no_filters(self) -> None:
        """All filters default to None; pagination defaults to page=1, page_size=20."""
        q = VisitListQuery.model_validate({})
        assert q.client_id is None
        assert q.from_ is None
        assert q.to is None
        assert q.page == 1
        assert q.page_size == 20


class TestVisitResponse:
    """camelCase serialisation invariants for VisitResponse."""

    def _make_response(self) -> VisitResponse:
        return VisitResponse.model_validate(
            {
                "id": uuid4(),
                "client_id": uuid4(),
                "membership_id": uuid4(),
                "checked_in_at": datetime.now(tz=UTC),
                "gym_date": datetime.now(_MSK).date(),
                "channel": "reception",
                "checked_in_by": uuid4(),
                "created_at": datetime.now(tz=UTC),
            }
        )

    def test_camelcase_serialisation(self) -> None:
        """All snake_case fields serialise to camelCase when by_alias=True."""
        resp = self._make_response()
        dumped = resp.model_dump(by_alias=True)
        assert "clientId" in dumped
        assert "membershipId" in dumped
        assert "checkedInAt" in dumped
        assert "gymDate" in dumped
        assert "checkedInBy" in dumped
        assert "createdAt" in dumped
        # Snake_case keys must NOT be present at the wire level
        assert "client_id" not in dumped
        assert "gym_date" not in dumped

    def test_checked_in_by_nullable(self) -> None:
        """checkedInBy may be None for the bot path (D-04: channel='telegram_bot')."""
        resp = VisitResponse.model_validate(
            {
                "id": uuid4(),
                "client_id": uuid4(),
                "membership_id": uuid4(),
                "checked_in_at": datetime.now(tz=UTC),
                "gym_date": datetime.now(_MSK).date(),
                "channel": "telegram_bot",
                "checked_in_by": None,
                "created_at": datetime.now(tz=UTC),
            }
        )
        assert resp.checked_in_by is None
        dumped = resp.model_dump(by_alias=True)
        assert dumped["checkedInBy"] is None
