---
phase: 87-notification-inbox
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - apps/backend/app/modules/notifications/repository.py
  - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
  - apps/backend/tests/notifications/test_notifications_endpoints.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 87: Code Review Report (Iteration 3 — Final)

**Reviewed:** 2026-06-06
**Depth:** standard
**Files Reviewed:** 3
**Status:** clean

## Summary

Iteration-3 re-review verifying three iteration-2 findings that were fixed: WR-01 (push-token
INSERT race), IN-01 (Rules of Hooks), and IN-02 (invalid-platform test assertion). All three
are genuinely resolved. No new blocking or warning issues were introduced by the fixes.

### WR-01 — push-token INSERT race (verified resolved)

`upsert_push_token` Step 3 (`repository.py:275–293`) now uses
`pg_insert(...).on_conflict_do_update(index_elements=["token"], index_where=ClientPushToken.unregistered_at.is_(None), ...)`.
This correctly targets the partial unique index `(token) WHERE unregistered_at IS NULL`
(migration 0061). The `set_` dict supplies `client_id`, `platform`,
`unregistered_at=None`, and `updated_at=text("now()")` — all correct field types and values.

Concurrent-race correctness traced: if two transactions T1 (client B) and T2 (client C) both
pass Steps 1–2 for the same token, T1 inserts first; T2's Step 3 hits the partial index
conflict and the DO UPDATE re-points the alive row to client C. Net result: exactly one alive
row (last-writer-wins). No `IntegrityError` is raised. No `session.commit()` is present in
the repository. SAVEPOINT-safe.

Same-client re-register path: Step 2's `UPDATE WHERE client_id=:cid AND token=:tok` matches
the existing row and returns its `id`, so `updated_id is not None` and Step 3 is skipped
entirely — idempotent no-op confirmed.

### IN-01 — Rules of Hooks (verified resolved)

`NotificationsSheet.jsx:128–144`: all hook calls (`useState` ×4, `useRef` ×2,
`useClientNotifications`, `useMarkNotificationRead`, `useMarkAllNotificationsRead`,
`useEffect` ×3) are unconditional and appear before the feature-flag early return at line 233.
No conditional hook calls remain anywhere in the component.

### IN-02 — invalid-platform test assertion (verified resolved)

`test_post_push_token_invalid_platform_returns_error` at line 685 now asserts
`resp.status_code == 422` with a precise message. The test comment was also updated to
accurately describe Pydantic Literal as the primary rejection layer. Correct.

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

All reviewed files meet quality standards. No issues found.

---

_Reviewed: 2026-06-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
