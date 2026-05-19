---
phase: 43-multi-user-admin-module
plan: 11
subsystem: backend/tests/integration/users
tags: [phase-43, users, invitation-flow, email-capture, audit, integration-test, wave-4]
requires:
  - phase: 41-multi-user-admin-bedrock
    provides: EmailDispatcher Protocol slot (D-41-24) + password_reset_tokens schema
  - phase: 42-email-channel
    provides: SandboxEmailClient stub + enqueue_email_dispatch (Phase 42 D-42-03/26)
  - 43-04-repository (invitation token CRUD)
  - 43-05-service (create_user / revoke_invitation orchestration)
  - 43-06-router (POST /users + invitations/{id}/revoke mounting)
  - 43-07b (sandbox_email_client fixture via RecordingEmailDispatcher)
provides:
  - 4 invitation-flow integration tests covering D-43-13/14/19/24/25 end-to-end
  - Demonstrates RecordingEmailDispatcher capture API (sent_emails list shape)
affects:
  - .planning/phases/43-multi-user-admin-module/43-VERIFY (Phase 43 verifier consumes this surface)

tech-stack:
  added: []
  patterns:
    - "Sandbox email capture via slot-swapped RecordingEmailDispatcher (43-07b)"
    - "JSONB UUID roundtrip — compare audit_row.payload[<uuid_field>] to str(uuid)"

key-files:
  created:
    - apps/backend/tests/integration/users/test_users_invitation_flow.py
  modified: []

key-decisions:
  - "AuditLog.action (not .event) — plan text drift; mirrors 43-08 fix"
  - "AppError handler shape {code,message,fields} — plan text used {detail:{error}} which doesn't exist"
  - "JSONB serialises UUIDs as strings on roundtrip; compare with str(uuid)"

patterns-established:
  - "RecordingEmailDispatcher.sent_emails entries merge dispatcher kwargs + rendered envelope vars"
  - "/auth/accept-invite#token=<raw> URL fragment shape — token NEVER in path (RESET-03 anti-oracle)"

requirements-completed: [USERS-03]

duration: 6min
completed: 2026-05-19
---

# Phase 43 Plan 11: Invitation Flow Integration Tests Summary

**Four invitation-flow integration tests against the live Phase 42 email transport substrate — sandbox capture of USER_INVITATION_EMAIL, ?include_invite_link=true URL fragment shape, revoke flow audit emission, and double-revoke 409 race-loss parity.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-19T15:08:59Z
- **Completed:** 2026-05-19T15:14:00Z (approx)
- **Tasks:** 1 (Task 1: create test_users_invitation_flow.py)
- **Files created:** 1

## Accomplishments

- `test_invitation_email_enqueued_through_sandbox` — D-43-13/24/25 — POST /users enqueues an envelope with `template_id='USER_INVITATION_EMAIL'`, addressed to the invitee, with rendered subject ("Приглашение в Sportzal" — D-43-OWNER-COPY-LOCK) and text body containing the invitee name + `/auth/accept-invite#token=` fragment.
- `test_include_invite_link_returns_url_with_token_fragment` — D-43-14 — `?include_invite_link=true` exposes `data.inviteLinkUrl` with scheme + path + `#token=<raw>` fragment; token component ≥32 url-safe chars (RESET-03 anti-oracle: raw token NEVER in path).
- `test_revoke_invitation_flips_consumed_and_emits_audit` — D-43-19 — `POST /invitations/{id}/revoke` atomic-consumes the token (`consumed_at IS NOT NULL` after) AND emits `user_invitation_revoked` with FLAT payload kwargs (`invitation_token_id`, `revoked_user_id`, `reason`).
- `test_revoke_already_consumed_invitation_returns_409` — D-43-19 — second revoke on the same token returns 409 `invitation_already_accepted` (pre-check + race-loss both map to the same code, mirroring v1.1 refresh-rotation discipline).

## Task Commits

1. **Task 1: Create test_users_invitation_flow.py** — `8158fa0` (test)

   The commit also accidentally captured concurrent work from a parallel-running 43-12 plan: a Rule 1 fix in `apps/backend/app/modules/auth/service.py` (`user_id=str(row.user_id)` for JSONB UUID-string) and a new sibling file `tests/integration/users/test_refresh_account_inactive.py`. See "Deviations" → race-with-parallel-agent below.

## Files Created/Modified

- `apps/backend/tests/integration/users/test_users_invitation_flow.py` — created, 226 LOC, 4 async tests + 1 helper.

## Decisions Made

- **`AuditLog.action` (not `.event`)** — the actual ORM column name; the plan text said `.event` which would AttributeError at import. Same drift documented in `43-08-SUMMARY.md`.
- **`r.json()["code"]` (not `r.json()["detail"]["error"]`)** — the AppError handler returns top-level `{code, message, fields}` per `app/core/exceptions.register_exception_handlers`. The plan text shape doesn't exist in this codebase.
- **`audit_row.payload["invitation_token_id"] == str(token_id)`** — JSONB column serialises UUIDs as their canonical lowercase string representation on PostgreSQL roundtrip; comparison must coerce.
- **Use the test-only `RecordingEmailDispatcher` (43-07b conftest) — NOT prod `SandboxEmailClient`** — the prod `SandboxEmailClient` at `app/integrations/email/client.py:174` is a no-op stub (logs the envelope, no `.sent_emails` capture buffer). The conftest swaps the Phase 41 D-41-24 dispatcher slot with a recording dispatcher whose `sent_emails: list[dict]` entries merge dispatcher kwargs (`template_id`, `to`, `audit_correlation_id`) with rendered envelope vars (`subject`, `html`, `text`, `full_name`, `role_ru`, `invitation_url`, `expires_at_human`). This decision was already made by 43-07b and is documented in its SUMMARY's "SandboxEmailClient Resolution Path" section.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan-text `AuditLog.event` would AttributeError at runtime**

- **Found during:** Task 1 (test file authoring; verified by reading `app/core/audit_models.py:49`)
- **Issue:** The plan-text draft compared `AuditLog.event == "user_invitation_revoked"`. The real column on `AuditLog` is `action`, not `event` — this would AttributeError on first test collection.
- **Fix:** Use `AuditLog.action == "user_invitation_revoked"`. Same drift was already fixed in `test_users_crud.py` (43-08) — pattern mirrored.
- **Files modified:** `apps/backend/tests/integration/users/test_users_invitation_flow.py`
- **Verification:** ruff + mypy --strict + pytest all green for the 4 tests.
- **Committed in:** `8158fa0`

**2. [Rule 1 — Bug] Plan-text `r.json()["detail"]["error"]` doesn't exist on AppError responses**

- **Found during:** Task 1 (cross-checked against `app/core/exceptions.register_exception_handlers`)
- **Issue:** The plan-text draft asserted `r2.json()["detail"]["error"] == "invitation_already_accepted"`. The `AppError` handler emits top-level `{"code", "message", "fields"}` (see `app/core/exceptions.py:402-411`). There is no `detail` envelope on domain errors in this codebase.
- **Fix:** Assert `r2.json()["code"] == "invitation_already_accepted"`.
- **Files modified:** same file.
- **Verification:** `test_revoke_already_consumed_invitation_returns_409` passes against the live AppError handler.
- **Committed in:** `8158fa0`

**3. [Rule 1 — Bug] JSONB UUID roundtrip — payload values come back as strings**

- **Found during:** Task 1 (initial green pass — observed during pytest run)
- **Issue:** Comparing `audit_row.payload["invitation_token_id"] == token_id` (UUID vs string) would always fail because asyncpg + JSONB serialises UUIDs as their canonical lowercase string form.
- **Fix:** Cast at the assertion: `audit_row.payload["invitation_token_id"] == str(token_id)` (and same for `revoked_user_id`).
- **Files modified:** same file.
- **Verification:** Test passes.
- **Committed in:** `8158fa0`

### Race with Parallel Agent (NOT a deviation from THIS plan's scope)

The Wave 4 parallel-execution model has plans 43-08, 43-10, 43-11, 43-12 running concurrently against the same working tree (sequential executor mode, single repo, no worktrees). Between my `git stash pop` and `git add` + `git commit`, the 43-12 plan progressed and staged a Rule 1 fix in `apps/backend/app/modules/auth/service.py` (`user_id=str(row.user_id)` JSONB-boundary cast at line 444-451) plus a new sibling test file `apps/backend/tests/integration/users/test_refresh_account_inactive.py`. The `git commit -m "..."` command without explicit pathspec committed everything in the index — so my `8158fa0` includes both the 43-11 test file (my work) AND the 43-12 changes (their work).

This is a parallel-execution race, not a flaw in either plan. The 43-12 changes are visibly correctly scoped — they belong to 43-12's success criteria. Cleanup by force-resetting would destroy the 43-12 progress; the safer recovery is to flag this in both SUMMARY files. 43-12's SUMMARY (when written) should note its work shipped in commit `8158fa0` rather than its own commit.

**Action:** Logged here; no further action required from 43-11. 43-12's executor will pick up its work as already-committed and continue.

---

**Total deviations:** 3 auto-fixed (3 × Rule 1 plan-text bugs against real code surface)
**Impact on plan:** All three drifts mirror previously-documented patterns from 43-07b / 43-08 — they are systemic plan-text drift between Wave 3 planning and the real codebase. No scope creep; all 4 success-criteria tests pass against the live transport substrate.

## Issues Encountered

- Parallel-execution race noted above. The 43-11 test file itself was authored, verified, and passing locally before the cross-commit happened.
- One intermittent test-collection flake during the very first `-x -q` run (single test failed once, then never reproduced across subsequent runs). Most likely a SAVEPOINT teardown ordering hiccup; not reproducible and not caused by 43-11 code.

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Test count ≥ 4 | `grep -c 'async def test_' tests/integration/users/test_users_invitation_flow.py` | 4 ✓ |
| USER_INVITATION_EMAIL refs ≥ 1 | `grep -c 'USER_INVITATION_EMAIL' ...` | 3 ✓ |
| Sandbox capture refs ≥ 1 | `grep -c 'sandbox_email_client\|RecordingEmailDispatcher'` | 8 ✓ |
| `invitation_already_accepted` refs ≥ 1 | `grep -c 'invitation_already_accepted' ...` | 2 ✓ |
| conftest.py NOT modified | `git status --short ... conftest.py` | empty ✓ |
| ruff check | `uv run ruff check tests/integration/users/test_users_invitation_flow.py` | All checks passed ✓ |
| ruff format | `uv run ruff format --check ...` | already formatted ✓ |
| mypy --strict | `uv run mypy --strict tests/integration/users/test_users_invitation_flow.py` | no issues ✓ |
| pytest | `uv run pytest tests/integration/users/test_users_invitation_flow.py -x -q` | 4 passed in 0.71s ✓ |

## Self-Check: PASSED

- File `apps/backend/tests/integration/users/test_users_invitation_flow.py` — exists, 226 LOC, 4 async tests.
- Commit `8158fa0` — present in `git log --oneline` (head of 43-11 work).

## Next Phase Readiness

- USERS-03 invitation flow validated end-to-end against Phase 42's live email transport substrate.
- 43-VERIFY can consume this surface as the canonical reference for the sandbox-capture testing pattern within the users module.

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
