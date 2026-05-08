# Phase 25 Deferred Items (out-of-scope discoveries)

## Pre-existing ruff E501 in app/core/permissions.py:45

Discovered during Plan 25-01 verification (`uv run ruff check app/ alembic/`).
The line `PROFILE = "profile"  # ...` is 112 chars (limit 100). Pre-existing
from Phase 22; unrelated to freeze schema work. Not auto-fixed (Rule SCOPE
BOUNDARY: only fix issues directly caused by current task's changes).

Suggested follow-up: separate cleanup commit, or fold into a future Phase 25
plan that touches permissions.py.
