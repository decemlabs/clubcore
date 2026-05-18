# Phase 41 Deferred Items

Tracks issues discovered during Phase 41 execution that are out of scope for
the current plan's deviation rules (Rule SCOPE BOUNDARY — only fixes for the
current task's direct effects are in scope; pre-existing failures and
unrelated drift live here).

## Pre-existing tests/unit/test_permissions.py failures (discovered 2026-05-18, Plan 41-10)

Four assertions in `apps/backend/tests/unit/test_permissions.py` already fail
on `master` before Plan 41-10 was executed:

- `test_owner_only_has_exactly_twenty_nine_entries` — expects `len(OWNER_ONLY) == 29`, actual is 33.
- `test_action_value_set` — drift on the action enumeration assertion.
- `test_resource_value_set` — drift on the resource enumeration assertion, includes the new `Resource.USERS` values.
- `test_specific_owner_only_membership` — drift on the OWNER_ONLY contents check.

These look like a v1.6 INFRA carve-out forgot to update the matching unit
test when adding the `USERS` resource to `app.core.permissions`. Resolution
belongs in a dedicated permissions-test refresh plan (likely Phase 41 Plan
41-11 INFRA-39 or a follow-up plan that owns the OWNER_ONLY surface),
**not** in Plan 41-10 — Plan 41-10 only hoists `User`, declares 2 new
Protocol slots, extends `.importlinter`, and extends the SVC001 walker scope.

Verified pre-existing via `git stash` round-trip: with the stash applied
(no Plan 41-10 edits), all 4 still fail identically.
