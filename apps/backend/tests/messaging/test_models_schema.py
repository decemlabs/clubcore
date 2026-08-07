"""Pure metadata introspection tests for messaging ORM models (Phase 90 MSG-01).

No DB connection needed — these tests verify SQLAlchemy metadata only.

Test 1: Table names are correct
Test 2: Import registers both tables on Base.metadata
Test 3: Required columns are present
Test 4: Message check constraint contains the role values
"""

from __future__ import annotations

from app.modules.messaging.models import Message, MessageThread


class TestTableNames:
    def test_message_thread_tablename(self) -> None:
        assert MessageThread.__tablename__ == "message_threads"

    def test_message_tablename(self) -> None:
        assert Message.__tablename__ == "messages"


class TestMetadataRegistration:
    def test_both_tables_registered_on_base_metadata(self) -> None:
        from app.core.database import Base

        assert "message_threads" in Base.metadata.tables
        assert "messages" in Base.metadata.tables


class TestColumns:
    def test_message_has_role_and_body(self) -> None:
        col_names = {c.name for c in Message.__table__.columns}
        assert "role" in col_names
        assert "body" in col_names

    def test_message_thread_has_required_columns(self) -> None:
        col_names = {c.name for c in MessageThread.__table__.columns}
        assert "client_unread_count" in col_names
        assert "last_message_at" in col_names


class TestCheckConstraint:
    def test_message_role_check_constraint(self) -> None:
        table_args = Message.__table_args__
        check_expressions = []
        for arg in table_args:
            if hasattr(arg, "sqltext"):
                check_expressions.append(str(arg.sqltext))
        assert any("role IN ('client','staff')" in expr for expr in check_expressions), (
            f"Expected role check constraint not found. Constraints: {check_expressions}"
        )
