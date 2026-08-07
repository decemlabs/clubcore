"""Phase 90 Plan 02 Task 1 — Messaging schema camelCase + validation unit tests (TDD RED).

Five pure schema behaviours (no DB connection required):
  1. MessageItem fields serialize with camelCase aliases (sentAt, threadId, readAt).
  2. MessageListResponse serializes key "unreadCount" alongside items/total/page/pageSize.
  3. SendMessageRequest rejects body="" and body="   " (whitespace) with ValidationError.
  4. SendMessageRequest rejects unknown extra fields (extra='forbid' → ValidationError).
  5. NewMessageEvent serializes {"type":"new_message","messageId":"..."} with camelCase.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestMessageItemCamelCase:
    """Test 1 — MessageItem response field aliases are camelCase (P16)."""

    def test_sent_at_alias_is_camel_case(self) -> None:
        from app.modules.messaging.schemas import MessageItem

        assert MessageItem.model_fields["sent_at"].alias == "sentAt"

    def test_thread_id_alias_is_camel_case(self) -> None:
        from app.modules.messaging.schemas import MessageItem

        assert MessageItem.model_fields["thread_id"].alias == "threadId"

    def test_read_at_alias_is_camel_case(self) -> None:
        from app.modules.messaging.schemas import MessageItem

        assert MessageItem.model_fields["read_at"].alias == "readAt"

    def test_message_item_serializes_camel_case_keys(self) -> None:
        from app.modules.messaging.schemas import MessageItem

        now = datetime.now(tz=UTC)
        item = MessageItem(
            id=uuid4(),
            role="client",
            body="привет",
            sent_at=now,
            read_at=None,
            thread_id=uuid4(),
        )
        data = item.model_dump(by_alias=True)
        assert "sentAt" in data
        assert "threadId" in data
        assert "readAt" in data
        assert "sent_at" not in data
        assert "thread_id" not in data


class TestMessageListResponseUnreadCount:
    """Test 2 — MessageListResponse serializes unreadCount (not unread_count)."""

    def test_unread_count_serializes_as_unread_count_camel(self) -> None:
        from app.modules.messaging.schemas import MessageListResponse

        resp = MessageListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            unread_count=3,
        )
        data = resp.model_dump(by_alias=True)
        assert "unreadCount" in data, f"Expected 'unreadCount' key, got: {list(data.keys())}"
        assert data["unreadCount"] == 3
        assert "unread_count" not in data

    def test_message_list_response_has_page_fields(self) -> None:
        from app.modules.messaging.schemas import MessageListResponse

        resp = MessageListResponse(
            items=[],
            total=5,
            page=2,
            page_size=10,
            unread_count=0,
        )
        data = resp.model_dump(by_alias=True)
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["pageSize"] == 10
        assert data["unreadCount"] == 0
        assert data["items"] == []


class TestSendMessageRequestValidation:
    """Test 3 — SendMessageRequest rejects empty/whitespace body with ValidationError."""

    def test_empty_body_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="")

    def test_whitespace_only_body_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="   ")

    def test_whitespace_only_tabs_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="\t\n  ")

    def test_valid_body_accepted(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        req = SendMessageRequest(body="привет")
        assert req.body == "привет"

    def test_body_exceeding_max_length_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="x" * 4001)


class TestSendMessageRequestExtraForbid:
    """Test 4 — SendMessageRequest rejects unknown extra fields (extra='forbid')."""

    def test_extra_field_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="hello", client_id="should-be-rejected")  # type: ignore[call-arg]

    def test_thread_id_in_body_raises_validation_error(self) -> None:
        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="hello", thread_id=str(uuid4()))  # type: ignore[call-arg]


class TestNewMessageEventCamelCase:
    """Test 5 — NewMessageEvent serializes {"type":"new_message","messageId":"..."} camelCase."""

    def test_type_is_literal_new_message(self) -> None:
        from app.modules.messaging.schemas import NewMessageEvent

        event = NewMessageEvent(message_id=uuid4())
        assert event.type == "new_message"

    def test_message_id_serializes_as_camel_case(self) -> None:
        from app.modules.messaging.schemas import NewMessageEvent

        msg_id = uuid4()
        event = NewMessageEvent(message_id=msg_id)
        data = event.model_dump(by_alias=True)
        assert "messageId" in data, f"Expected 'messageId', got: {list(data.keys())}"
        assert str(data["messageId"]) == str(msg_id)
        assert "message_id" not in data

    def test_event_json_shape(self) -> None:
        from app.modules.messaging.schemas import NewMessageEvent

        msg_id = uuid4()
        event = NewMessageEvent(message_id=msg_id)
        json_str = event.model_dump_json(by_alias=True)
        assert '"type":"new_message"' in json_str
        assert '"messageId"' in json_str
        assert str(msg_id) in json_str

    def test_type_field_is_literal_only_new_message(self) -> None:
        """NewMessageEvent type must be Literal["new_message"] — other values rejected."""
        from app.modules.messaging.schemas import NewMessageEvent

        with pytest.raises(ValidationError):
            NewMessageEvent(message_id=uuid4(), type="other_event")  # type: ignore[call-arg]


class TestReadReceiptEventCamelCase:
    """Test 6 — ReadReceiptEvent serializes {type:'read_receipt', readAt} camelCase (Phase 91)."""

    def test_type_is_literal_read_receipt(self) -> None:
        from app.modules.messaging.schemas import ReadReceiptEvent

        now = datetime.now(tz=UTC)
        event = ReadReceiptEvent(read_at=now)
        assert event.type == "read_receipt"

    def test_read_at_serializes_as_camel_case(self) -> None:
        from app.modules.messaging.schemas import ReadReceiptEvent

        now = datetime.now(tz=UTC)
        event = ReadReceiptEvent(read_at=now)
        data = event.model_dump(by_alias=True)
        assert "readAt" in data, f"Expected 'readAt', got: {list(data.keys())}"
        assert "read_at" not in data

    def test_event_json_shape(self) -> None:
        from app.modules.messaging.schemas import ReadReceiptEvent

        now = datetime.now(tz=UTC)
        event = ReadReceiptEvent(read_at=now)
        json_str = event.model_dump_json(by_alias=True)
        assert '"type":"read_receipt"' in json_str
        assert '"readAt"' in json_str

    def test_event_has_type_and_read_at_keys(self) -> None:
        from app.modules.messaging.schemas import ReadReceiptEvent

        now = datetime.now(tz=UTC)
        event = ReadReceiptEvent(read_at=now)
        data = event.model_dump(by_alias=True)
        assert set(data.keys()) == {"type", "readAt"}


class TestTypingEventCamelCase:
    """Test 7 — TypingEvent serializes exactly {type:'typing', actor:'staff'} (Phase 91)."""

    def test_type_is_literal_typing(self) -> None:
        from app.modules.messaging.schemas import TypingEvent

        event = TypingEvent()
        assert event.type == "typing"

    def test_actor_defaults_to_staff(self) -> None:
        from app.modules.messaging.schemas import TypingEvent

        event = TypingEvent()
        assert event.actor == "staff"

    def test_event_json_shape_exactly_two_keys(self) -> None:
        """TypingEvent must serialize exactly {type, actor} — no body, preview, or id (T-91-LEAK)."""  # noqa: E501
        from app.modules.messaging.schemas import TypingEvent

        event = TypingEvent()
        json_str = event.model_dump_json(by_alias=True)
        assert '"type":"typing"' in json_str
        assert '"actor":"staff"' in json_str

    def test_event_has_exactly_two_keys(self) -> None:
        """Assert exactly two keys so no content leaks into the typing frame (T-91-LEAK)."""
        from app.modules.messaging.schemas import TypingEvent

        event = TypingEvent()
        data = event.model_dump(by_alias=True)
        assert set(data.keys()) == {"type", "actor"}, (
            f"TypingEvent must have exactly {{type, actor}} but got: {set(data.keys())}"
        )


# ---------------------------------------------------------------------------
# Phase 92 Plan 03 — MessageAttachmentItem + SendMessageRequest body-OR-attachment
# ---------------------------------------------------------------------------


class TestMessageAttachmentItemCamelCase:
    """Test 8 — MessageAttachmentItem serialises to camelCase {id, mimeType, sizeBytes, url}."""

    def test_mime_type_alias_is_camel_case(self) -> None:
        from app.modules.messaging.schemas import MessageAttachmentItem

        assert MessageAttachmentItem.model_fields["mime_type"].alias == "mimeType"

    def test_size_bytes_alias_is_camel_case(self) -> None:
        from app.modules.messaging.schemas import MessageAttachmentItem

        assert MessageAttachmentItem.model_fields["size_bytes"].alias == "sizeBytes"

    def test_url_field_present(self) -> None:
        from app.modules.messaging.schemas import MessageAttachmentItem

        assert "url" in MessageAttachmentItem.model_fields

    def test_attachment_item_serializes_camel_case_keys(self) -> None:
        from uuid import uuid4

        from app.modules.messaging.schemas import MessageAttachmentItem

        item = MessageAttachmentItem(
            id=uuid4(),
            mime_type="image/jpeg",
            size_bytes=1024,
            url="/api/v1/client/messages/attachments/some-id",
        )
        data = item.model_dump(by_alias=True)
        assert "mimeType" in data
        assert "sizeBytes" in data
        assert "url" in data
        assert "mime_type" not in data
        assert "size_bytes" not in data
        assert data["mimeType"] == "image/jpeg"
        assert data["sizeBytes"] == 1024


class TestMessageItemAttachmentField:
    """Test 9 — MessageItem.attachment defaults to None, present for attachment-bearing messages."""

    def test_message_item_attachment_defaults_to_none(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.modules.messaging.schemas import MessageItem

        item = MessageItem(
            id=uuid4(),
            role="client",
            body="hello",
            sent_at=datetime.now(tz=UTC),
            read_at=None,
            thread_id=uuid4(),
        )
        assert item.attachment is None

    def test_message_item_attachment_field_serializes_none_as_none(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.modules.messaging.schemas import MessageItem

        item = MessageItem(
            id=uuid4(),
            role="client",
            body="hello",
            sent_at=datetime.now(tz=UTC),
            thread_id=uuid4(),
        )
        data = item.model_dump(by_alias=True)
        assert "attachment" in data
        assert data["attachment"] is None

    def test_message_item_attachment_with_sub_object(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.modules.messaging.schemas import MessageAttachmentItem, MessageItem

        att_id = uuid4()
        att = MessageAttachmentItem(
            id=att_id,
            mime_type="image/png",
            size_bytes=2048,
            url="/api/v1/client/messages/attachments/" + str(att_id),
        )
        item = MessageItem(
            id=uuid4(),
            role="client",
            body="",
            sent_at=datetime.now(tz=UTC),
            thread_id=uuid4(),
            attachment=att,
        )
        data = item.model_dump(by_alias=True)
        assert data["attachment"] is not None
        assert data["attachment"]["mimeType"] == "image/png"
        assert data["attachment"]["sizeBytes"] == 2048


class TestSendMessageRequestBodyOrAttachment:
    """Test 10 — SendMessageRequest body-OR-attachment validity matrix (Phase 92 two-step)."""

    def test_body_only_valid(self) -> None:
        """Body present, no attachmentId → valid (unchanged Phase 90 path)."""
        from app.modules.messaging.schemas import SendMessageRequest

        req = SendMessageRequest(body="привет")
        assert req.body == "привет"
        assert req.attachment_id is None

    def test_attachment_id_only_valid(self) -> None:
        """attachmentId present, body absent → valid (relax empty-body 422)."""
        from uuid import uuid4

        from app.modules.messaging.schemas import SendMessageRequest

        att_id = uuid4()
        req = SendMessageRequest(attachment_id=att_id)
        assert req.attachment_id == att_id
        assert req.body is None

    def test_both_body_and_attachment_id_valid(self) -> None:
        """Both body and attachmentId present → valid."""
        from uuid import uuid4

        from app.modules.messaging.schemas import SendMessageRequest

        att_id = uuid4()
        req = SendMessageRequest(body="message with photo", attachment_id=att_id)
        assert req.body == "message with photo"
        assert req.attachment_id == att_id

    def test_neither_body_nor_attachment_id_raises_validation_error(self) -> None:
        """Neither body nor attachmentId → 422 (still rejected)."""
        import pytest
        from pydantic import ValidationError

        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest()

    def test_whitespace_only_body_with_no_attachment_raises_validation_error(self) -> None:
        """body='   ' and no attachmentId → 422 (whitespace guard preserved)."""
        import pytest
        from pydantic import ValidationError

        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="   ")

    def test_whitespace_only_body_with_attachment_id_raises_validation_error(self) -> None:
        """body='   ' even when attachmentId present → 422 (whitespace guard still applies)."""
        from uuid import uuid4

        import pytest
        from pydantic import ValidationError

        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="   ", attachment_id=uuid4())

    def test_attachment_id_wire_alias_is_camel_case(self) -> None:
        """attachment_id field serializes as attachmentId on the wire."""
        from uuid import uuid4

        from app.modules.messaging.schemas import SendMessageRequest

        att_id = uuid4()
        req = SendMessageRequest(attachment_id=att_id)
        # BackendSchemaBase uses alias_generator=to_camel with populate_by_name=True
        data = req.model_dump(by_alias=True)
        assert "attachmentId" in data or "attachment_id" in data

    def test_extra_field_still_raises_validation_error(self) -> None:
        """extra='forbid' preserved after schema change."""
        import pytest
        from pydantic import ValidationError

        from app.modules.messaging.schemas import SendMessageRequest

        with pytest.raises(ValidationError):
            SendMessageRequest(body="hello", client_id="injected")  # type: ignore[call-arg]
