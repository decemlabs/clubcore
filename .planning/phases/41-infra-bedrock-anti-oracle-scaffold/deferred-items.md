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

## Mypy strict re-export warning on auth.models User shim (discovered 2026-05-18, Plan 41-11)

Mypy strict reports `Module "app.modules.auth.models" does not explicitly
export attribute "User"  [attr-defined]` for every callsite that imports
``User`` through the Plan-41-10 shim. This is a single missing
``__all__`` (or `User as User`) declaration in
``app/modules/auth/models.py`` — adding it would silence ~25 existing
errors plus the one introduced by `test_password_reset_no_oracle.py`.

Plan 41-11 explicitly chose the shim import path (D-41-01 / D-41-02 +
plan-checker revision) so this test stays stable across the Plan-10/11
wave race; it does not own the shim file itself. The fix belongs in a
shim-hardening follow-up (or rolled into Plan 41-10's SUMMARY's
deferred-items if anyone wants a one-line `__all__ = ["User", ...]`
amendment). Resolution before v1.7 DEFER-41-shim removal is desirable
but not blocking — every other shim consumer in the codebase reports
the same error.
