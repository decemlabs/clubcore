"""SQL helpers shared across modules (INFRA-10).

`escape_like_pattern` was hoisted from `app.modules.clients.repository` in
Phase 15 so future modules (memberships, visits) can reuse it without
introducing a `modules → modules` import (banned by import-linter contract
`modules-independent`). Pure-function, no DB / Pydantic / SQLAlchemy types.
"""


def escape_like_pattern(value: str, *, escape_like: bool = True) -> str:
    """Escape SQL LIKE/ILIKE metacharacters in user-supplied search input.

    Postgres ILIKE treats ``%`` (any sequence) and ``_`` (any single char) as
    wildcards, and uses ``\\\\`` as the default escape character. To make a
    user query match LITERAL text, we double-escape backslashes first
    (so we don't re-escape escapes added in the next step), then escape
    ``%`` and ``_``.

    Order matters: backslash MUST be escaped before ``%`` and ``_``, otherwise
    the backslashes we add to escape ``%``/``_`` would themselves be doubled.

    CR-01 (Phase 8 -> Phase 14): without this helper, a reception user
    could ``?q=%`` and dump the full client roster.

    Args:
        value: User-supplied search input (NOT yet wrapped in % … %).
        escape_like: When False, returns ``value`` unchanged (opt-out for
            callers that already escape upstream).

    Returns:
        The input with backslashes / percent / underscore escaped for safe
        interpolation into a Postgres ILIKE pattern.
    """
    if not escape_like:
        return value
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
