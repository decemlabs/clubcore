---
phase: 43-multi-user-admin-module
plan: 13
subsystem: backend/tests
tags: [users, ast-gate, email-template, infra-36, d-41-11, d-43-33]
requires:
  - "43-05 (literal template_id='USER_INVITATION_EMAIL' callsite in users/service.py:create_user)"
  - "41-03 (LOCKED_EMAIL_TEMPLATES frozenset + AST walker scaffold)"
  - "42-09 + 42-4-11 (precedent EMAIL_OTP_LOGIN positive-assertion pattern)"
provides:
  - "AST-level positive assertion that USER_INVITATION_EMAIL is a literal ast.Constant(str) directly at a callsite inside app/modules/users/service.py"
  - "Regression guard against future const-extraction / variable / f-string refactors at the users.service dispatcher callsite"
affects:
  - "apps/backend/tests/unit/test_locked_email_templates_ast.py (+1 test function, +42 lines)"
tech-stack:
  added: []
  patterns:
    - "Mirror the Phase 42 4-11 'walker logic mirrored locally' idiom (do NOT delegate to _iter_dispatcher_calls so a refactor of the production walker cannot silently weaken the gate)"
key-files:
  created: []
  modified:
    - apps/backend/tests/unit/test_locked_email_templates_ast.py
decisions:
  - "D-43-33 — extension preferred as an explicit per-template positive function (not a parametrized fixture iteration) because the existing Phase 42 4-11 test already used that shape; mirroring it keeps grouping local and the failure message tailored to the offending template"
metrics:
  duration_minutes: 1
  completed_date: 2026-05-19
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
  tests_in_file: 5
  tests_passing: 5
---

# Phase 43 Plan 13: USER_INVITATION_EMAIL AST positive-assertion Summary

Added a real-callsite AST positive assertion that pins literal `template_id="USER_INVITATION_EMAIL"` inside `app/modules/users/service.py`, mirroring the Phase 42 4-11 lesson for `EMAIL_OTP_LOGIN`.

## Style decision (per plan `<output>` directive)

The existing file (`test_locked_email_templates_ast.py`) uses **explicit per-template test functions** for positive assertions — `test_email_otp_login_real_callsite_present` (Phase 42 4-11) inlines the AST walker locally rather than calling `_iter_dispatcher_calls`. The new test mirrors that convention exactly:

- New function name: `test_user_invitation_email_literal_at_users_service_callsite`
- Placement: directly above `test_non_literal_template_id_is_rejected`, grouping it next to the other positive-callsite test
- Walker logic mirrored locally (not delegated) so a future refactor of the production walker (`_iter_dispatcher_calls`) cannot silently weaken this specific gate
- No parametrized fixture introduced — the existing file does not use one, and adding one for two entries would change the file shape unnecessarily

## Tasks Completed

| Task | Name                                                                                  | Commit  | Files                                                          |
| ---- | ------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------- |
| 1    | Extend test_locked_email_templates_ast.py with USER_INVITATION_EMAIL real-callsite    | d1d7d66 | apps/backend/tests/unit/test_locked_email_templates_ast.py     |

## Verification

```
$ cd apps/backend && uv run pytest tests/unit/test_locked_email_templates_ast.py -x -q
.....                                                                    [100%]
5 passed in 0.10s
```

All 5 tests pass:

1. `test_real_callsites_pass` — walker scans `apps/backend/app/**/*.py` and collects 0 violations (both real callsites — EMAIL_OTP_LOGIN in auth.service, USER_INVITATION_EMAIL in users.service — pass the literal-only + LOCKED_EMAIL_TEMPLATES contract)
2. `test_bogus_template_id_is_rejected` — synthetic fixture with `BOGUS_NOT_LOCKED` is flagged
3. `test_email_otp_login_real_callsite_present` — Phase 42 4-11 positive assertion (no regression)
4. **`test_user_invitation_email_literal_at_users_service_callsite`** — new (this plan)
5. `test_non_literal_template_id_is_rejected` — synthetic fixture with variable `chosen_id` is flagged

## Acceptance Criteria

- [x] `grep -c 'USER_INVITATION_EMAIL' apps/backend/tests/unit/test_locked_email_templates_ast.py` → **5** (≥ 1)
- [x] `grep -c 'def test_user_invitation_email_literal_at_users_service_callsite' apps/backend/tests/unit/test_locked_email_templates_ast.py` → **1** (≥ 1)
- [x] `cd apps/backend && uv run pytest tests/unit/test_locked_email_templates_ast.py -x -q` → exit 0, 5 passed

## Deviations from Plan

None — plan executed exactly as written. The plan offered two extension shapes (per-template explicit function vs parametrized list); the existing file used the former (Phase 42 4-11 vintage) so the former was chosen per the plan's "mirror the existing convention exactly" directive.

## Decisions Made

- **D-43-33 follow-through:** The gate is now positive-asserted at both real callsites (`EMAIL_OTP_LOGIN` in auth.service + `USER_INVITATION_EMAIL` in users.service). Any future regression where a developer extracts the literal into a module-level constant or builds the template_id via f-string will fail this specific test, not just the broader walker scan.

## Key Files

- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — +42 lines, +1 test function

## Threat Flags

None — this plan is a test-only hardening of an existing AST gate; introduces no new network endpoint, auth path, file access, or schema change.

## Self-Check: PASSED

Verification:

- `apps/backend/tests/unit/test_locked_email_templates_ast.py`: FOUND (M in git status pre-commit, now committed)
- Commit `d1d7d66`: FOUND in `git log --oneline`
- pytest exit 0, 5/5 passing
