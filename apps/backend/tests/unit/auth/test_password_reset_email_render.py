"""RESET-03 / D-44-OWNER-COPY-LOCK — deterministic template render snapshots.

Future edits to ``PASSWORD_RESET_EMAIL`` must update these snapshots AND
re-trigger owner sign-off (D-27-OWNER-COPY-LOCK lineage; D-44-OWNER-COPY-LOCK
v1.6 instance approved 2026-05-19).

These are pattern-match tests rather than byte-for-byte golden-file snapshots
(consistent with Phase 43 plan 13 approach for the HTML side — full-snapshot
diff would be brittle to formatting changes; key-fragment assertions catch
the anti-oracle invariant + structural correctness without false-flake on
whitespace).

The anti-oracle invariant (D-44-25) is the critical assertion: NO ``{{ full_name }}``,
``{full_name}``, or any name-leak path may appear in either the HTML or text
render. Stolen-mailbox replay would otherwise expose the target's full name
to the attacker — see D-42-23 lineage for the original EMAIL_OTP_LOGIN
discipline that this template inherits.
"""

from __future__ import annotations

from app.modules.auth.email_templates import TEMPLATES

# Deterministic test inputs — pinned so future edits to copy can be detected
# via fragment assertions below. The token is a fixed placeholder, never a
# secret, never a real URL-fragment value.
_FIXED_RESET_URL = "https://app.clubcore.ru/auth/password-reset#token=FIXED_TOKEN_FOR_TEST"
_FIXED_EXPIRES_AT_HUMAN = "19 мая 2026 г. 21:30 (МСК)"  # noqa: RUF001


def test_password_reset_email_subject_is_locked_literal() -> None:
    """D-44-26 — subject is a ``Final[str]`` literal; mutation requires owner sign-off."""
    tpl = TEMPLATES["PASSWORD_RESET_EMAIL"]
    assert tpl.subject == "Восстановление пароля Sportzal"


def test_password_reset_email_html_renders_deterministic_snapshot() -> None:
    """Deterministic HTML render — fixed inputs produce byte-stable fragments.

    Asserts:
      - No unresolved Jinja markers (``{{`` / ``}}``) — sandbox actually rendered.
      - Anti-oracle (D-44-25): NO ``full_name`` substitution path exists.
      - ``reset_url`` appears exactly 2x (HTML href + visible link body per
        ``<a href="{{ reset_url }}">{{ reset_url }}</a>`` from
        ``app/modules/auth/email_templates.py``).
      - ``expires_at_human`` appears (locked variable from D-44-25).
      - Helpdesk footer present (``noreply@mail.clubcore.ru``).
    """
    tpl = TEMPLATES["PASSWORD_RESET_EMAIL"]
    rendered = tpl.html.render(
        reset_url=_FIXED_RESET_URL,
        expires_at_human=_FIXED_EXPIRES_AT_HUMAN,
    )

    # No unresolved Jinja markers — confirms the sandbox actually substituted.
    assert "{{" not in rendered
    assert "}}" not in rendered

    # D-44-25 anti-oracle: NO name-leak path may appear. Neither the Jinja
    # variable ``{{ full_name }}``, the legacy f-string form ``{full_name}``,
    # nor the bare identifier ``full_name`` may surface in rendered output.
    assert "full_name" not in rendered
    assert "{full_name}" not in rendered
    # No specific Russian name leaks through either (paranoid anti-oracle).
    assert "Анна" not in rendered
    assert "Иван" not in rendered

    # reset_url appears exactly twice — once in the href attribute and once
    # as the visible link body. The template is
    # ``<a href="{{ reset_url }}">{{ reset_url }}</a>`` at
    # email_templates.py:96 (post-44-02).
    assert rendered.count(_FIXED_RESET_URL) == 2

    # expires_at_human is interpolated exactly once in the HTML body.
    assert rendered.count(_FIXED_EXPIRES_AT_HUMAN) == 1

    # Locked Russian-copy fragments — failure here means the verbatim
    # Russian copy in TEMPLATES drifted and the D-44-OWNER-COPY-LOCK
    # sign-off must be re-issued.
    assert "<h1>Восстановление пароля Sportzal</h1>" in rendered
    assert "Перейдите по ссылке" in rendered
    assert "Ссылка действительна до" in rendered
    assert "проигнорируйте это письмо" in rendered
    assert "Sportzal · noreply@mail.clubcore.ru" in rendered


def test_password_reset_email_text_renders_deterministic_snapshot() -> None:
    """Deterministic text/plain render — same anti-oracle invariants as HTML.

    Note the text template uses ``_ENV_TEXT`` (``autoescape=False`` per
    email_templates.py:52) — explicit passthrough, safe because the only
    variables interpolated are a URL fragment and a pre-formatted Russian
    datetime string. NO HTML escaping of e.g. ``&`` may occur.
    """
    tpl = TEMPLATES["PASSWORD_RESET_EMAIL"]
    rendered = tpl.text.render(
        reset_url=_FIXED_RESET_URL,
        expires_at_human=_FIXED_EXPIRES_AT_HUMAN,
    )

    # No unresolved Jinja markers.
    assert "{{" not in rendered
    assert "}}" not in rendered

    # D-44-25 anti-oracle invariant — text side mirrors HTML side.
    assert "full_name" not in rendered
    assert "{full_name}" not in rendered
    assert "Анна" not in rendered
    assert "Иван" not in rendered

    # reset_url interpolated exactly once in the text body (no anchor tag).
    assert rendered.count(_FIXED_RESET_URL) == 1

    # expires_at_human interpolated exactly once.
    assert rendered.count(_FIXED_EXPIRES_AT_HUMAN) == 1

    # Locked Russian-copy fragments.
    assert "Восстановление пароля Sportzal" in rendered
    assert "Перейдите по ссылке" in rendered
    assert "Ссылка действительна до" in rendered
    assert "проигнорируйте это письмо" in rendered
    assert "Sportzal · noreply@mail.clubcore.ru" in rendered

    # Text side must NOT contain HTML tags — defensive check that we
    # rendered from the .text Template, not the .html one.
    assert "<h1>" not in rendered
    assert "<a " not in rendered
    assert "<p>" not in rendered
