"""Email-fallback fanout for membership expiring-soon notifications.

Phase 45 D-45-16 / D-45-22 — hoists the Phase 27 D-27-10 variant chooser
from ``app/integrations/telegram/copy.py:pick_variant`` to module scope
so the same A/B selection is shared across Telegram (Phase 27) and
email (Phase 45). ``enqueue_expiring_email_fallback`` branches through
six explicit literal ``template_id`` callsites to satisfy the AST gate
at ``tests/unit/test_locked_email_templates_ast.py:42-46`` — NO
f-strings, NO variable interpolation in the ``template_id`` position.

The helper is module-owned (memberships) per D-45-22 — it consumes the
``EmailDispatcher`` Protocol slot via ``get_email_dispatcher()`` and
NEVER imports from ``app.integrations.email`` directly (preserves
import-linter contract ``integrations-not-depend-on-modules``).

Anti-oracle property (D-27-10 lineage): the per-client variant selection
is a deterministic function of ``client_id.bytes[0]`` only — it does
NOT depend on time, worker identity, or system state. A side-by-side
observer cannot infer client identity from which variant a recipient
received.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal
from uuid import UUID, uuid4

from app.core.dependencies import get_email_dispatcher

Variant = Literal["A", "B"]

# Genitive month names for Russian long-form dates. The trailing `г.`
# (Russian abbreviation for "год") is rendered by the email template
# (memberships/email_templates.py) immediately after the date — kept
# OUT of this helper so the template owns the NBSP placement
# (D-45-17 NBSP discipline; mirrors telegram/copy.py:_format_ru_date).
_RU_MONTHS_GENITIVE: Final[tuple[str, ...]] = (
    "января",  # noqa: RUF001
    "февраля",  # noqa: RUF001
    "марта",  # noqa: RUF001
    "апреля",  # noqa: RUF001
    "мая",  # noqa: RUF001
    "июня",  # noqa: RUF001
    "июля",  # noqa: RUF001
    "августа",  # noqa: RUF001
    "сентября",  # noqa: RUF001
    "октября",  # noqa: RUF001
    "ноября",  # noqa: RUF001
    "декабря",  # noqa: RUF001
)


def select_expiring_variant(client_id: UUID) -> Variant:
    """Deterministic per-client A/B variant (Phase 27 D-27-10 anti-oracle).

    Uses ``client_id.bytes[0] & 1`` — UUIDv4 first byte is uniformly
    random from ``os.urandom``, giving a ~50/50 split that is STABLE
    across processes / restarts / time. Builtin ``hash`` would be
    PYTHONHASHSEED-salted and break the anti-oracle property; this
    helper deliberately avoids it.

    Hoisted from ``app/integrations/telegram/copy.py:pick_variant``
    (Phase 27) per D-45-16 so the same client gets the same variant on
    both channels — a client who received variant A on the Telegram
    expiring DM yesterday receives ``EMAIL_EXPIRING_*_VARIANT_A`` if
    the email fallback fires today.
    """
    return "A" if (client_id.bytes[0] & 1) == 0 else "B"


def _format_ru_date(d: date) -> str:
    """Format a date in Russian long form without the trailing `г.` suffix.

    Returns e.g. ``"16 мая 2026"``. The template ``email_templates.py``
    appends ``&nbsp;г.`` (HTML) / `` г.`` (text) — NBSP discipline lives
    at the render site, not here (mirrors D-45-17 + D-42-23 lineage).
    """
    month_genitive = _RU_MONTHS_GENITIVE[d.month - 1]
    return f"{d.day} {month_genitive} {d.year}"


async def enqueue_expiring_email_fallback(
    *,
    kind: str,
    client_id: UUID,
    client_email: str,
    end_date: date,
) -> UUID:
    """Render + enqueue an expiring-soon email via the EmailDispatcher slot.

    Branches through six explicit literal ``template_id`` callsites — the
    AST gate at ``tests/unit/test_locked_email_templates_ast.py:42-46``
    asserts the ``template_id`` keyword argument at every
    ``get_email_dispatcher()(...)`` callsite resolves to an
    ``ast.Constant(str)`` member of ``LOCKED_EMAIL_TEMPLATES``. NO
    f-strings, NO variable interpolation: each of the six combinations
    of (kind, variant) is dispatched at its own literal-keyed callsite.

    Returns the freshly-generated ``audit_correlation_id``. Caller
    (memberships.service._send_expiring_notifications) stores it on the
    structlog binding for the email-side membership_notifications INSERT
    + the audit emit so the forensic chain reassembles via
    ``email_send_log.audit_correlation_id`` (Phase 42 D-42-18).

    Raises ``ValueError`` on an unknown ``(kind, variant)`` tuple — the
    fanout caller only ever produces ``expiring_{7,3,1}d`` per the
    Phase 27 CHECK constraint, so this branch is defensive only.
    """
    variant = select_expiring_variant(client_id)
    audit_correlation_id = uuid4()
    end_date_ru = _format_ru_date(end_date)
    dispatcher = get_email_dispatcher()

    if kind == "expiring_7d" and variant == "A":
        await dispatcher(
            template_id="EMAIL_EXPIRING_7D_VARIANT_A",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    elif kind == "expiring_7d" and variant == "B":
        await dispatcher(
            template_id="EMAIL_EXPIRING_7D_VARIANT_B",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    elif kind == "expiring_3d" and variant == "A":
        await dispatcher(
            template_id="EMAIL_EXPIRING_3D_VARIANT_A",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    elif kind == "expiring_3d" and variant == "B":
        await dispatcher(
            template_id="EMAIL_EXPIRING_3D_VARIANT_B",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    elif kind == "expiring_1d" and variant == "A":
        await dispatcher(
            template_id="EMAIL_EXPIRING_1D_VARIANT_A",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    elif kind == "expiring_1d" and variant == "B":
        await dispatcher(
            template_id="EMAIL_EXPIRING_1D_VARIANT_B",
            to=client_email,
            audit_correlation_id=audit_correlation_id,
            end_date=end_date_ru,
        )
    else:
        raise ValueError(f"unknown kind/variant: {kind}/{variant}")

    return audit_correlation_id
