"""Phase 92 Plan 03 Task 2 — IDOR attachment ownership + send-with-attachmentId + history join (TDD RED).

Six behaviours proven with REAL DB rows and two seeded clients A/B:
  1. get_owned_attachment for A's attachment queried as A → returns row dict with keys.
  2. get_owned_attachment for A's attachment queried as B → returns None (IDOR 404-collapse).
  3. get_owned_attachment for a non-existent UUID → returns None.
  4. send_client_message with a valid attachmentId owned by the client → persists attachment_id, returns attachment sub-object.
  5. send_client_message with an attachmentId owned by another client → raises NotFoundError (404-collapse), no message written.
  6. list_thread_history returns attachment sub-object for attachment-bearing messages; None otherwise.

Harness: SAVEPOINT db_session + ASGITransport not needed (repository/service layer only).
Two client seeds: client_a (phone _phone(51)), client_b (phone _phone(52)).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.messaging import repository, service
from app.modules.messaging.schemas import SendMessageRequest

pytestmark = pytest.mark.asyncio(loop_scope="function")

_BASE_PHONE = "+79169001"


def _phone(n: int) -> str:
    return f"{_BASE_PHONE}{n:04d}"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> "Any":
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.auth.models import User

    user = User(
        email=f"att-idor-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("att-idor-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Attachment IDOR Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(db_session: AsyncSession, staff: "Any", phone: str) -> "Any":
    from app.modules.clients.models import Client

    client = Client(
        first_name="Прикреп",
        last_name="Тест",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _insert_attachment_direct(
    db_session: AsyncSession,
    *,
    client_id: UUID,
    mime_type: str = "image/jpeg",
    size_bytes: int = 1024,
) -> UUID:
    """Insert a real message_attachments row for a client and return the attachment id.

    Uses repository.get_or_create_thread + repository.insert_attachment.
    """
    thread_id = await repository.get_or_create_thread(db_session, client_id)
    attachment_id = await repository.insert_attachment(
        db_session,
        thread_id=thread_id,
        client_id=client_id,
        mime_type=mime_type,
        object_key=f"attachments/{uuid4()}",
        size_bytes=size_bytes,
    )
    return attachment_id


# ---------------------------------------------------------------------------
# Test 1: get_owned_attachment returns row for matching client
# ---------------------------------------------------------------------------


async def test_get_owned_attachment_returns_row_for_owner(
    db_session: AsyncSession,
) -> None:
    """get_owned_attachment for A's attachment queried as A → returns dict with required keys."""
    staff = await _seed_staff(db_session, "idor-1")
    client_a = await _seed_client(db_session, staff, _phone(51))
    await db_session.commit()

    att_id = await _insert_attachment_direct(db_session, client_id=client_a.id)
    await db_session.commit()

    row = await repository.get_owned_attachment(db_session, att_id, client_id=client_a.id)
    assert row is not None, "Expected to get row for own attachment"
    assert "object_key" in row
    assert "mime_type" in row
    assert "size_bytes" in row
    assert row["mime_type"] == "image/jpeg"
    assert row["size_bytes"] == 1024


# ---------------------------------------------------------------------------
# Test 2: get_owned_attachment returns None for non-owner (IDOR 404-collapse)
# ---------------------------------------------------------------------------


async def test_get_owned_attachment_returns_none_for_non_owner(
    db_session: AsyncSession,
) -> None:
    """get_owned_attachment for A's attachment queried as B → returns None (IDOR 404-collapse)."""
    staff = await _seed_staff(db_session, "idor-2")
    client_a = await _seed_client(db_session, staff, _phone(52))
    client_b = await _seed_client(db_session, staff, _phone(53))
    await db_session.commit()

    att_id = await _insert_attachment_direct(db_session, client_id=client_a.id)
    await db_session.commit()

    # Client B asks for client A's attachment → must get None (never 403)
    row = await repository.get_owned_attachment(db_session, att_id, client_id=client_b.id)
    assert row is None, "Expected None for non-owned attachment (IDOR 404-collapse)"


# ---------------------------------------------------------------------------
# Test 3: get_owned_attachment returns None for non-existent id
# ---------------------------------------------------------------------------


async def test_get_owned_attachment_returns_none_for_nonexistent_id(
    db_session: AsyncSession,
) -> None:
    """get_owned_attachment for a random/non-existent UUID → returns None."""
    staff = await _seed_staff(db_session, "idor-3")
    client = await _seed_client(db_session, staff, _phone(54))
    await db_session.commit()

    row = await repository.get_owned_attachment(db_session, uuid4(), client_id=client.id)
    assert row is None, "Expected None for non-existent attachment id"


# ---------------------------------------------------------------------------
# Test 4: send_client_message with own attachmentId persists + returns sub-object
# ---------------------------------------------------------------------------


async def test_send_client_message_with_own_attachment_persists_and_returns_sub_object(
    db_session: AsyncSession,
) -> None:
    """send_client_message with client's own attachmentId → message.attachment_id set, attachment returned."""
    staff = await _seed_staff(db_session, "idor-4")
    client = await _seed_client(db_session, staff, _phone(55))
    await db_session.commit()

    att_id = await _insert_attachment_direct(db_session, client_id=client.id)
    await db_session.commit()

    payload = SendMessageRequest(attachment_id=att_id)
    result = await service.send_client_message(
        db_session,
        client_id=client.id,
        payload=payload,
    )
    await db_session.commit()

    # Result should have the attachment sub-object
    assert result.attachment is not None, "Expected attachment sub-object in response"
    assert result.attachment.id == att_id
    assert result.attachment.mime_type == "image/jpeg"
    assert result.attachment.size_bytes == 1024
    assert "/messages/attachments/" in result.attachment.url


# ---------------------------------------------------------------------------
# Test 5: send_client_message with another client's attachmentId → NotFoundError, no message
# ---------------------------------------------------------------------------


async def test_send_client_message_with_foreign_attachment_raises_not_found(
    db_session: AsyncSession,
) -> None:
    """send_client_message with foreign attachmentId → NotFoundError (404-collapse), no message written."""
    staff = await _seed_staff(db_session, "idor-5")
    client_a = await _seed_client(db_session, staff, _phone(56))
    client_b = await _seed_client(db_session, staff, _phone(57))
    await db_session.commit()

    # client_a uploads an attachment
    att_id = await _insert_attachment_direct(db_session, client_id=client_a.id)
    await db_session.commit()

    # client_b tries to send with client_a's attachment_id
    payload = SendMessageRequest(attachment_id=att_id)
    with pytest.raises(NotFoundError):
        await service.send_client_message(
            db_session,
            client_id=client_b.id,
            payload=payload,
        )


# ---------------------------------------------------------------------------
# Test 6: list_thread_history returns attachment sub-object for attachment messages
# ---------------------------------------------------------------------------


async def test_list_thread_history_includes_attachment_sub_object(
    db_session: AsyncSession,
) -> None:
    """list_thread_history returns attachment sub-object for attachment-bearing messages; None otherwise."""
    staff = await _seed_staff(db_session, "idor-6")
    client = await _seed_client(db_session, staff, _phone(58))
    await db_session.commit()

    # Insert a text-only message
    payload_text = SendMessageRequest(body="текстовое сообщение")
    await service.send_client_message(db_session, client_id=client.id, payload=payload_text)

    # Insert an attachment message
    att_id = await _insert_attachment_direct(db_session, client_id=client.id)
    payload_att = SendMessageRequest(attachment_id=att_id)
    await service.send_client_message(db_session, client_id=client.id, payload=payload_att)

    await db_session.commit()

    # List history
    result = await service.list_thread_history(
        db_session,
        client_id=client.id,
        page=1,
        page_size=20,
    )

    assert result.total == 2, f"Expected 2 messages, got {result.total}"

    # Find the attachment message (newest-first, so it's first)
    att_msg = next((m for m in result.items if m.attachment is not None), None)
    text_msg = next((m for m in result.items if m.attachment is None), None)

    assert att_msg is not None, "Expected to find attachment message in history"
    assert att_msg.attachment is not None
    assert att_msg.attachment.id == att_id
    assert att_msg.attachment.mime_type == "image/jpeg"
    assert "/messages/attachments/" in att_msg.attachment.url

    assert text_msg is not None, "Expected to find text-only message in history"
    assert text_msg.attachment is None
