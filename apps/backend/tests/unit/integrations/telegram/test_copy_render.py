"""Unit tests for render_expiring_dm + _format_ru_date (Phase 27 NTF-COPY-01).

Each (kind, variant) renders the locked template with the formatted Russian
date substituted. We pin the variant via force-A / force-B UUIDs (whose
first byte AND-1 deterministically resolves to "A" or "B").

Locked phrases (per app.integrations.telegram.copy constants and PROJECT.md
D-27-OWNER-COPY-LOCK row):
- 7D-A: "истекает"
- 7D-B: "действует до"
- 3D-A: "Через 3 дня"
- 3D-B: "действителен до"
- 1D-A: "Завтра"
- 1D-B: "истекает завтра"

Modifying these locked phrases requires a NEW owner sign-off entry.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from app.integrations.telegram.copy import _format_ru_date, render_expiring_dm

_FORCE_A = UUID(bytes=b"\x00" * 16)
_FORCE_B = UUID(bytes=b"\x01" + b"\x00" * 15)


def test_format_ru_date_long_form() -> None:
    out = _format_ru_date(date(2026, 5, 16))
    assert out == "16 мая 2026 г."  # noqa: RUF001


@pytest.mark.parametrize(
    ("kind", "client_id", "distinguishing_phrase"),
    [
        ("expiring_7d", _FORCE_A, "истекает"),
        ("expiring_7d", _FORCE_B, "действует до"),
        ("expiring_3d", _FORCE_A, "Через 3 дня"),
        ("expiring_3d", _FORCE_B, "действителен до"),
        ("expiring_1d", _FORCE_A, "Завтра"),
        ("expiring_1d", _FORCE_B, "истекает завтра"),
    ],
)
def test_render_includes_locked_phrase_and_substitutes_date(
    kind: str,
    client_id: UUID,
    distinguishing_phrase: str,
) -> None:
    out = render_expiring_dm(
        kind=kind,  # type: ignore[arg-type]
        client_id=client_id,
        end_date=date(2026, 5, 16),
    )
    assert "{end_date}" not in out, "placeholder must be substituted"
    assert "мая" in out, "Russian month must be present (proves date formatter ran)"
    assert distinguishing_phrase in out, (
        f"missing locked phrase {distinguishing_phrase!r} in {out!r}"
    )
