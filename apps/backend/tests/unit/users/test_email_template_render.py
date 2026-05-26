"""Phase 43 D-43-25 — golden-file snapshot test for USER_INVITATION_EMAIL render.

Pitfall 6 mitigation (Russian copy + Jinja sandbox + NBSP discipline). The
test asserts byte-exact equality so any accidental copy mutation (a missing
NBSP, a moved comma, a stray period) is caught at unit-test time before
deployment.
"""

from __future__ import annotations

from pathlib import Path

from app.modules.users.email_templates import TEMPLATES


def test_user_invitation_email_renders_against_snapshot() -> None:
    template = TEMPLATES["USER_INVITATION_EMAIL"]
    rendered_text = template.text.render(
        full_name="Иван Иванов",
        role_ru="администратор стойки",
        invitation_url="https://localhost:5173/auth/accept-invite#token=test",
        expires_at_human="26 мая 2026 в 12:00",
    )
    snapshot_path = (
        Path(__file__).resolve().parent.parent / "fixtures" / "email_user_invitation_snapshot.txt"
    )
    snapshot = snapshot_path.read_text(encoding="utf-8")
    assert rendered_text == snapshot, (
        "USER_INVITATION_EMAIL text render drifted from snapshot. "
        "If the change is intentional + owner-signed-off, regenerate the snapshot "
        "(D-43-OWNER-COPY-LOCK)."
    )


def test_user_invitation_email_subject_locked() -> None:
    """D-43-OWNER-COPY-LOCK — subject is a Final[str] literal; mutation requires owner sign-off."""
    assert TEMPLATES["USER_INVITATION_EMAIL"].subject == "Приглашение в Sportzal"
