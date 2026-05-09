# Phase 25 Deferred Items (out-of-scope discoveries)

## Pre-existing ruff E501 in app/core/permissions.py:45

Discovered during Plan 25-01 verification (`uv run ruff check app/ alembic/`).
The line `PROFILE = "profile"  # ...` is 112 chars (limit 100). Pre-existing
from Phase 22; unrelated to freeze schema work. Not auto-fixed (Rule SCOPE
BOUNDARY: only fix issues directly caused by current task's changes).

Suggested follow-up: separate cleanup commit, or fold into a future Phase 25
plan that touches permissions.py.

## Pre-existing test failures in tests/unit/memberships/test_schemas.py

Discovered during Plan 25-03 Task 4 verification (`uv run pytest tests/unit/`).
After Plan 25-04 added the required `freeze_days_limit` field to
`MembershipPlanCreateRequest` (D-25-10), at least one Phase 17 unit test
(`test_create_trims_leading_trailing_whitespace_preserves_casing` at
test_schemas.py:48) constructs the request without the new required kwarg
and now fails with `freezeDaysLimit Field required`.

This was a pre-existing breakage at Plan 25-04 landing time, NOT caused by
Plan 25-03's service-layer changes. Plan 25-03's scope is service.py only;
fixing schema-layer test fixtures belongs in Plan 25-05 (extended test
matrix). Auto-fix Rule SCOPE BOUNDARY explicitly forbids out-of-scope test
fixes.

Suggested follow-up: Plan 25-05 extends the schema-test fixtures to pass
`freeze_days_limit=14` (or similar) and re-runs the full unit suite.
