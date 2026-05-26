"""Locked Russian DM templates for Phase 27 expiring-soon notifications (NTF-COPY-01).

6 templates (3 windows x 2 variants). Anti-oracle pattern (v1.2 D-5 / Phase 20):
per-client deterministic A/B variant selection prevents send-pattern fingerprinting --
variant choice is a deterministic per-client function independent of system state.

Owner sign-off (D-27-11) is recorded in `.planning/PROJECT.md` Key Decisions table
for v1.3 BEFORE Phase 27 merge -- gated by the human_verification block in plan 27-04.
Modifying these strings post-merge requires a NEW owner sign-off entry.

Date formatter: stdlib month-name table (babel not installed in apps/backend per Task 1
investigation; pyproject.toml + uv.lock both miss babel; `uv run python -c "import babel"`
fails with ModuleNotFoundError). Output shape uses Russian long form with the trailing
year suffix that matches frontend date-fns ``ru`` long format.

Architectural constraint (importlinter `integrations-not-depend-on-modules`): this module
MUST NOT import from app.modules.*. Pure constants + helpers -- no DB, no HTTP, no Bot API.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal
from uuid import UUID

_RU_MONTHS_GENITIVE: Final[tuple[str, ...]] = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


Kind = Literal["expiring_7d", "expiring_3d", "expiring_1d"]
Variant = Literal["A", "B"]


# === Phase 27 NTF-COPY-01 -- locked Russian DM copy. Owner sign-off pending in plan 27-04. ===
# RUF001 per-line: Cyrillic letters mixed with Latin look-alikes (e.g. {end_date} placeholder)
# are intentional (Russian-only product per PROJECT.md i18n locked decision).
# E501 per-line: locked DM copy strings are kept on a single line so reviewers diff exact text.
EXPIRING_7D_VARIANT_A: Final[str] = (
    "Привет! Ваш абонемент истекает {end_date}. Самое время продлить — обратитесь к администратору."  # noqa: E501, RUF001
)
EXPIRING_7D_VARIANT_B: Final[str] = (
    "Напоминаем: ваш абонемент действует до {end_date}. Продление через администратора."  # noqa: E501, RUF001
)
EXPIRING_3D_VARIANT_A: Final[str] = (
    "Через 3 дня заканчивается ваш абонемент ({end_date}). Подойдите к стойке для продления."  # noqa: E501, RUF001
)
EXPIRING_3D_VARIANT_B: Final[str] = (
    "Ваш абонемент действителен до {end_date}. Не забудьте продлить!"  # noqa: E501, RUF001
)
EXPIRING_1D_VARIANT_A: Final[str] = (
    "Завтра ({end_date}) — последний день вашего абонемента. Заходите продлевать."  # noqa: E501, RUF001
)
EXPIRING_1D_VARIANT_B: Final[str] = (
    "Внимание: ваш абонемент истекает завтра, {end_date}. Зайдите к нам, чтобы продлить."  # noqa: E501, RUF001
)


_TEMPLATES: Final[dict[tuple[Kind, Variant], str]] = {
    ("expiring_7d", "A"): EXPIRING_7D_VARIANT_A,
    ("expiring_7d", "B"): EXPIRING_7D_VARIANT_B,
    ("expiring_3d", "A"): EXPIRING_3D_VARIANT_A,
    ("expiring_3d", "B"): EXPIRING_3D_VARIANT_B,
    ("expiring_1d", "A"): EXPIRING_1D_VARIANT_A,
    ("expiring_1d", "B"): EXPIRING_1D_VARIANT_B,
}


def pick_variant(client_id: UUID) -> Variant:
    """Deterministic per-client A/B variant selection (Phase 27 D-27-10 anti-oracle).

    Uses ``client_id.bytes[0] & 1`` -- UUIDv4 first byte from ``os.urandom`` is uniformly
    random, giving a ~50/50 split that is STABLE across processes / restarts / time. We
    deliberately avoid the builtin ``hash`` of the UUID: Python's builtin is salted with
    PYTHONHASHSEED and would yield different variants per worker run, breaking the
    anti-oracle property.
    """
    return "A" if (client_id.bytes[0] & 1) == 0 else "B"


def render_expiring_dm(*, kind: Kind, client_id: UUID, end_date: date) -> str:
    """Render the locked DM template for ``(kind, variant=pick_variant(client_id))``.

    Args:
        kind: One of ``"expiring_7d"`` / ``"expiring_3d"`` / ``"expiring_1d"`` (matches
            Phase 27 audit event suffix and migration CHECK constraint values).
        client_id: Used ONLY for variant picking -- never embedded into the text.
        end_date: Formatted in Russian-locale long form via ``_format_ru_date``.

    Returns:
        Russian-text DM body ready for ``sender.send_text_dm``.
    """
    variant = pick_variant(client_id)
    template = _TEMPLATES[(kind, variant)]
    return template.format(end_date=_format_ru_date(end_date))


def _format_ru_date(d: date) -> str:
    """Format a date in Russian long form, e.g. ``16 мая 2026 г.`` (with year suffix)."""  # noqa: RUF002
    month_genitive = _RU_MONTHS_GENITIVE[d.month - 1]
    return f"{d.day} {month_genitive} {d.year} г."  # noqa: RUF001
