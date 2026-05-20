---
phase: 46-openapi-handoff-milestone-verification
plan: 03
subsystem: docs/handoff
tags: [readme, changelog, handoff, docs]
requires: [46-01]
provides:
  - "README v1.6 changelog block"
  - "Human-readable handoff index for design team"
affects:
  - apps/backend/README.md
tech-stack:
  added: []
  patterns: ["reverse-chronological version changelog in README"]
key-files:
  created:
    - .planning/phases/46-openapi-handoff-milestone-verification/46-03-SUMMARY.md
  modified:
    - apps/backend/README.md
decisions:
  - "Inserted v1.6 block at END of README (no prior version changelog section existed; insertion-above pattern collapses to append)."
  - "Corrected AUTH-EM-01 path from planner's `/api/v1/otp/request` to live router decorator `/api/v1/auth/otp/request` (per 46-01 path-truth note)."
  - "Kept `{user_id}` parameter name verbatim — matches openapi.json paths."
metrics:
  duration: "~3 minutes"
  completed: "2026-05-20"
  tasks_completed: 1
  files_changed: 1
  commits: 1
requirements:
  - HANDOFF-04
---

# Phase 46 Plan 03: Backend README v1.6 Changelog Block Summary

One-liner: Appended a Russian-prose v1.6 H2 changelog section to `apps/backend/README.md` enumerating 11 new endpoints (USERS, RESET, EMAIL, AUTH-EM) with the locked-template constant-count footer pointing to `app/core/audit.py LOCKED_EMAIL_TEMPLATES`.

## What Was Built

Added a new H2 section at the end of `apps/backend/README.md`:

```markdown
## v1.6 — Email channel + Multi-user admin (2026-05-20)

- `POST /api/v1/users` — owner создаёт пользователя; отправляет invitation email (USERS-01, USERS-03).
- `GET /api/v1/users` — список пользователей с фильтрацией по `role` + `is_active` (USERS-04).
- `POST /api/v1/users/{user_id}/deactivate` — soft-deactivate; revokes refresh families (USERS-05).
- `POST /api/v1/users/{user_id}/reactivate` — re-activate (USERS-05).
- `DELETE /api/v1/users/{user_id}` — soft-delete (Alembic 0022 `deleted_at` + partial UNIQUE) (USERS-07).
- `POST /api/v1/users/invitations/accept` — приглашённый юзер устанавливает пароль (RESET-04).
- `POST /api/v1/users/invitations/{token_id}/revoke` — owner отзывает приглашение (RESET-05).
- `POST /api/v1/auth/password-reset/request` — anti-oracle 202, bounded-timing (RESET-01).
- `POST /api/v1/auth/password-reset/confirm` — атомарный consume + revoke всех сессий (RESET-02).
- `POST /api/v1/_internal/email/webhook` — provider bounce/complaint ingestion (EMAIL-04, internal).
- `POST /api/v1/auth/otp/request` — добавлен параметр `channel` (telegram | email) (AUTH-EM-01).

Locked Russian email templates: 15 constants — см. `app/core/audit.py` `LOCKED_EMAIL_TEMPLATES`.
```

11 endpoint bullets (one per new v1.6 surface), each in the `METHOD /path — description (REQ-ID)` shape required by D-46-09. Footer line references the 15-constant `LOCKED_EMAIL_TEMPLATES` frozenset.

## Verification

Acceptance criteria from `46-03-PLAN.md` — all PASS:

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `^## v1.6 — Email channel \+ Multi-user admin (2026-05-20)$` | 1 | 1 | PASS |
| `^- \`POST /api/v1/users\` ` bullet | 1 | 1 | PASS |
| Requirement code refs `(USERS-\|RESET-\|EMAIL-\|AUTH-EM-)` | ≥ 11 | 11 | PASS |
| `LOCKED_EMAIL_TEMPLATES` mention | ≥ 1 | 1 | PASS |
| `15 constants` footer | ≥ 1 | 1 | PASS |
| Title `# sportzal-backend` unchanged | yes | yes | PASS |

### LOCKED_EMAIL_TEMPLATES count verification

Counted entries in `apps/backend/app/core/audit.py:264-288`:

- Phase 42 auth: `EMAIL_OTP_LOGIN` (1)
- Phase 44 users + auth: `USER_INVITATION_EMAIL`, `PASSWORD_RESET_EMAIL` (2)
- Phase 45 memberships expiring (A/B × 7d/3d/1d): 6
- Phase 45 booking lifecycle (confirmed, cancelled-by-client, cancelled-by-owner, reminder-24h): 4
- Phase 45 payment receipts (sale, refund): 2

Total: **15 constants**. Footer line is accurate.

### OpenAPI path-truth verification

Confirmed all 11 documented paths exist verbatim in `apps/backend/openapi.json`:

```
/api/v1/_internal/email/webhook
/api/v1/auth/otp/request
/api/v1/auth/password-reset/confirm
/api/v1/auth/password-reset/request
/api/v1/users
/api/v1/users/{user_id}
/api/v1/users/{user_id}/deactivate
/api/v1/users/{user_id}/reactivate
/api/v1/users/invitations/{token_id}/revoke
/api/v1/users/invitations/accept
```

`DELETE /api/v1/users/{user_id}` and `GET /api/v1/users` share base paths with `POST` variants — all four documented operations map to the two base paths above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected AUTH-EM-01 endpoint path**

- **Found during:** Task 1, plan-block verbatim review against live OpenAPI.
- **Issue:** The plan's verbatim block listed `POST /api/v1/otp/request`, but the actual router decorator (and OpenAPI key) is `/api/v1/auth/otp/request`. This was flagged in `critical_notes` of the executor spawn prompt as a known path-truth correction from the 46-01 SUMMARY.
- **Fix:** Replaced `/api/v1/otp/request` → `/api/v1/auth/otp/request` in the inserted block. README documents the SHIPPED spec.
- **Files modified:** `apps/backend/README.md`
- **Commit:** `0e1aff4`

No other deviations. Plan executed exactly as written with the documented one-line path correction.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `0e1aff4` | docs | docs(46-03): append v1.6 changelog block to backend README |

## Key Decisions Made

- **Insertion point:** No prior version changelog H2 in README → appended at END (one blank line after the last bullet of "Документация" section), per plan instruction §1.
- **Path correction precedence:** Live router decorator beats planner's verbatim block when they disagree. Documented as deviation Rule 1 with explicit cross-reference to the 46-01 SUMMARY path-truth note.
- **No additional README changes:** Plan scope is strictly the v1.6 changelog block — Quick start, Команды, Документация sections untouched.

## Self-Check: PASSED

- File `apps/backend/README.md` modified: FOUND (commit `0e1aff4`, +16 lines)
- File `.planning/phases/46-openapi-handoff-milestone-verification/46-03-SUMMARY.md` created: FOUND (this file)
- Commit `0e1aff4` exists in `git log`: FOUND
- All 6 acceptance grep checks PASS (see verification table above)
- 15-constant footer matches LOCKED_EMAIL_TEMPLATES frozenset count: VERIFIED
- No STATE.md or ROADMAP.md modifications (per parallel_execution constraints): CONFIRMED via `git status`
