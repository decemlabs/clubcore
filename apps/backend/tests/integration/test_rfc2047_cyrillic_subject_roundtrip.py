"""Phase 46 D-46-14 #6 / VER-10 -- RFC 2047 Cyrillic subject round-trip.

Renders an email with the Cyrillic subject from
``EMAIL_EXPIRING_7D_VARIANT_A`` (Phase 45 NOTIFY-08 / D-45-15), assembles a
``EmailEnvelope`` and serialises that subject through the standard-library
MIME path (``email.message.EmailMessage``) -- the same RFC 2047 encoded-word
machinery (``=?UTF-8?B?...?=`` / ``=?UTF-8?Q?...?=``) that AWS SES SDK uses
server-side when given ``{"Data": subject, "Charset": "UTF-8"}`` (Phase 42
``app/integrations/email/client.py:93``). Decodes via
``email.header.decode_header`` + ``make_header`` and asserts byte-identical
equality with the original Cyrillic string -- including U+00A0 NBSP.

Catches RFC 2047 encoded-word discipline + NBSP preservation regressions
per Phase 42 D-42-23 / Phase 45 D-45-17 lineage.

NOT a race test in the gather sense -- single-flow encoding contract. No
DB, no Redis, no network, no real Postbox/SES traffic. VER-12 separately
runs the live deliverability probe.
"""

from __future__ import annotations

from email.header import decode_header, make_header
from email.message import EmailMessage
from uuid import uuid4

from app.integrations.email.types import EmailEnvelope
from app.modules.memberships.email_templates import TEMPLATES

# Phase 45 D-45-15 -- pure-literal Cyrillic subject locked at module import.
# Accessed via the TEMPLATES dict (D-41-12 locked registry shape); the
# template id is what dispatcher callsites pass and what the AST gate at
# ``tests/unit/test_locked_email_templates_ast.py`` enforces.
_TEMPLATE_ID = "EMAIL_EXPIRING_7D_VARIANT_A"

# U+00A0 NO-BREAK SPACE. Phase 45 D-45-17 / Phase 42 D-42-23: body
# templates embed literal NBSP between the date and the Russian year
# abbreviation; the dispatcher path must preserve U+00A0 wherever it
# appears. Defined as a named constant (rather than an inline literal)
# both for ruff cleanliness (RUF001 ambiguous-char) and so the NBSP
# discipline contract is grep-able by reviewers.
NBSP = "\u00a0"


def _serialise_subject_via_stdlib(subject: str) -> str:
    """Run ``subject`` through the stdlib MIME pipeline the SES SDK uses.

    AWS SES SDK encodes ``{"Data": s, "Charset": "UTF-8"}`` using RFC 2047
    encoded-words exactly the way ``email.message.EmailMessage`` does when
    you assign a non-ASCII string to ``msg["Subject"]`` and then serialise
    via ``msg.as_string()``. Re-walking that path here means a regression
    in the stdlib encoder, a font/charset misconfig in the template
    module, or accidental BMP-supplementary chars in the locked subject
    would all surface as a round-trip failure -- without needing a real
    SES call (VER-12 covers the live probe).
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    # ``EmailMessage.as_string()`` runs the message through the configured
    # ``email.policy`` Header encoder, which is where RFC 2047 encoded-
    # words are actually emitted (multi-line ``=?utf-8?b?...?=`` folds for
    # non-ASCII input). We extract the Subject header line(s) -- possibly
    # folded across multiple physical lines starting with leading
    # whitespace per RFC 5322 sec 2.2.3 -- and rejoin them into a single
    # logical header value for the decoder.
    serialised = msg.as_string()
    subject_lines: list[str] = []
    in_subject = False
    for line in serialised.splitlines():
        if line.startswith("Subject:"):
            in_subject = True
            subject_lines.append(line[len("Subject:") :].lstrip())
            continue
        if in_subject and line.startswith((" ", "\t")):
            # RFC 5322 folded continuation -- drop the leading fold
            # whitespace, keep the encoded-word payload.
            subject_lines.append(line.lstrip())
            continue
        if in_subject:
            break
    return " ".join(subject_lines)


def test_rfc2047_cyrillic_subject_roundtrip() -> None:
    """Locked Cyrillic subject survives RFC 2047 encode then decode unchanged."""
    template = TEMPLATES[_TEMPLATE_ID]
    rendered_subject = template.subject

    # Sanity: the locked subject contains Cyrillic glyphs (non-ASCII bytes
    # that force RFC 2047 encoded-word emission rather than passthrough).
    assert any(
        "Ѐ" <= c <= "ӿ" for c in rendered_subject
    ), "Subject must contain Cyrillic; otherwise this test would be vacuous."

    envelope = EmailEnvelope(
        to="roundtrip+rfc2047@local.dev",
        subject=rendered_subject,
        html="<p>round-trip test</p>",
        text="round-trip test",
        template_id=_TEMPLATE_ID,
        audit_correlation_id=uuid4(),
    )

    serialised = _serialise_subject_via_stdlib(envelope.subject)

    # Wire form MUST be an RFC 2047 encoded-word (the whole point -- if a
    # transport accidentally sent raw UTF-8 bytes in the Subject header,
    # gateways en route would silently mojibake or quarantine).
    assert "=?" in serialised and "?=" in serialised, (
        f"Subject did not emit an RFC 2047 encoded-word: {serialised!r}"
    )
    assert "UTF-8" in serialised.upper(), (
        f"Subject encoded-word missing UTF-8 charset declaration: {serialised!r}"
    )

    decoded = str(make_header(decode_header(serialised)))
    assert decoded == rendered_subject, (
        "RFC 2047 round-trip failed (byte-identical decode lost):\n"
        f"  original (len={len(rendered_subject)}): {rendered_subject!r}\n"
        f"  decoded  (len={len(decoded)}): {decoded!r}\n"
        f"  wire    : {serialised!r}"
    )


def test_rfc2047_nbsp_in_subject_roundtrip() -> None:
    """NBSP (U+00A0) survives the encode/decode round-trip on the subject line.

    Phase 45 D-45-17 / Phase 42 D-42-23: the body templates embed literal
    U+00A0 NBSP between the date and the Russian year abbreviation
    (Outlook strips plain spaces in that position, breaking Russian
    typography). The locked Phase 45 *subject* happens not to contain
    NBSP, but the dispatcher path must preserve NBSP wherever it appears
    -- a regression where some middleware normalises U+00A0 to U+0020
    would silently re-introduce the Outlook bug. This synthetic case
    proves the MIME encoder doesn't drop NBSPs.
    """
    # Locked Cyrillic subject with explicit U+00A0 NBSP between tokens.
    # Using the named ``NBSP`` constant (rather than literal characters in
    # the string literal) keeps the source file lint-clean (no RUF001
    # ambiguous-char warning) and makes the NBSP discipline contract
    # visually obvious to reviewers.
    nbsp_subject = f"Ваш{NBSP}абонемент{NBSP}скоро{NBSP}истекает"
    assert NBSP in nbsp_subject, "Fixture lost its NBSP at parse time."

    envelope = EmailEnvelope(
        to="roundtrip+nbsp@local.dev",
        subject=nbsp_subject,
        html="<p>nbsp round-trip</p>",
        text="nbsp round-trip",
        template_id=_TEMPLATE_ID,
        audit_correlation_id=uuid4(),
    )

    serialised = _serialise_subject_via_stdlib(envelope.subject)
    decoded = str(make_header(decode_header(serialised)))

    assert decoded == nbsp_subject, (
        "NBSP round-trip failed (byte-identical decode lost):\n"
        f"  original: {nbsp_subject!r}\n"
        f"  decoded : {decoded!r}\n"
        f"  wire    : {serialised!r}"
    )
    assert NBSP in decoded, (
        "NBSP (U+00A0 / 0xA0) was normalised away during MIME round-trip; "
        "Outlook NBSP discipline (D-45-17 / D-42-23) is broken."
    )
