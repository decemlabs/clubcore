"""Phase 43 CR-01 regression — invitation email envelope carries the rendered invitation_url.

Pre-fix: app/modules/users/service.py:create_user pre-rendered the template
locally AND passed subject/html/text as **template_vars to the dispatcher.
The dispatcher re-renders with **template_vars as Jinja inputs -> unknown
keys (subject/html/text) silently ignored -> the actual template variables
(full_name, role_ru, invitation_url, expires_at_human) defaulted to Jinja
Undefined -> empty string -> email arrived with empty invitation link.

This test asserts the dispatched email envelope carries the raw template
variable ``invitation_url`` as a direct kwarg (i.e. the URL was correctly
threaded through to the dispatcher's recording surface).

Fixture conventions mirror test_users_invitation_flow.py exactly:
  - ``authed_client_owner`` + ``sandbox_email_client`` from conftest.py
  - ``RecordingEmailDispatcher.sent_emails`` as the capture buffer
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .conftest import RecordingEmailDispatcher, _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_invitation_email_envelope_carries_invitation_url(
    authed_client_owner: AsyncClient,
    sandbox_email_client: RecordingEmailDispatcher,
) -> None:
    """CR-01 — dispatched email kwargs must contain the rendered invitation URL.

    The RecordingEmailDispatcher captures exactly the kwargs passed to the
    dispatcher slot. After the CR-01 fix, service.create_user passes raw
    template vars (full_name, role_ru, invitation_url, expires_at_human) —
    NOT pre-rendered subject/html/text. The presence of ``invitation_url``
    as a non-empty string containing ``accept-invite#token=`` confirms the
    fix is in effect.
    """
    # Reset recorder so a prior test's email does not pollute the count.
    sandbox_email_client.sent_emails.clear()

    response = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "cr01-regression@example.com",
            "fullName": "Иван Петров",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 201, response.text

    sent = sandbox_email_client.sent_emails
    assert len(sent) == 1, f"expected 1 captured email; got {len(sent)}"
    envelope = sent[0]

    # template_id must be the locked literal (AST gate D-41-11).
    assert envelope["template_id"] == "USER_INVITATION_EMAIL"

    # CR-01 regression: invitation_url must be present as a direct kwarg.
    # Pre-fix: only 'subject', 'html', 'text' were passed (pre-rendered
    # envelope fields), so invitation_url was absent / Jinja-Undefined.
    assert "invitation_url" in envelope, (
        "CR-01 regression — 'invitation_url' is missing from the dispatcher "
        "kwargs. The service likely passed pre-rendered envelope fields "
        "(subject/html/text) instead of raw template vars."
    )

    invitation_url: str = envelope["invitation_url"]
    assert "accept-invite#token=" in invitation_url, (
        f"CR-01 regression — invitation_url does not contain the token "
        f"fragment: {invitation_url!r}. Expected 'accept-invite#token=...'."
    )
    assert invitation_url.startswith(("http://", "https://")), (
        f"CR-01 regression — invitation_url is not a valid HTTP URL: {invitation_url!r}"
    )

    # full_name must be present (Jinja-Undefined pre-fix yielded empty greeting).
    assert envelope.get("full_name") == "Иван Петров", (
        "CR-01 regression — full_name is missing or wrong in dispatcher kwargs. "
        "Expected 'Иван Петров'."
    )


async def test_invitation_email_subject_via_locked_template(
    authed_client_owner: AsyncClient,
    sandbox_email_client: RecordingEmailDispatcher,
) -> None:
    """Defence-in-depth — the correct locked template_id is routed to the dispatcher.

    When the service passes raw template vars, the dispatcher resolves the
    subject from the LOCKED EmailTemplate registry (D-43-23). This test
    confirms the correct template_id is forwarded; the subject itself is
    tested at the unit level in test_email_template_render.py.
    """
    sandbox_email_client.sent_emails.clear()

    response = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "subject-test@example.com",
            "fullName": "Тест",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 201, response.text

    sent = sandbox_email_client.sent_emails
    assert len(sent) == 1
    envelope = sent[0]

    # The RecordingEmailDispatcher is a test-only recorder, not the prod
    # dispatcher, so it does not call _resolve_template. It captures the
    # template_id literal that the service passes — which must be the locked
    # string (D-41-11 AST gate). The actual subject rendering is exercised
    # by test_email_template_render.py against the TEMPLATES registry.
    assert envelope["template_id"] == "USER_INVITATION_EMAIL", (
        "CR-01 regression — wrong template_id in dispatcher kwargs. "
        f"Got {envelope['template_id']!r}; expected 'USER_INVITATION_EMAIL'."
    )
    # Confirm the expires_at_human kwarg is present and non-empty (WR-07 marker).
    assert envelope.get("expires_at_human"), (
        "WR-07 regression — expires_at_human is missing from dispatcher kwargs."
    )
