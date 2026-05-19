---
phase: 43-multi-user-admin-module
plan: 05
subsystem: api
tags: [users, service, audit, email-dispatch, session-invalidation, orchestration]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: "EmailDispatcher + UserSessionInvalidator Protocol slots (D-41-24/25); LOCKED_AUDIT_EVENTS frozenset + AUDIT_PAYLOAD_SCHEMAS extra='forbid'; D-41-28 SVC001 walker scope including users/service.py; D-41-11 literal template_id AST gate"
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: "render-at-enqueue + transport-envelope discipline (D-42-07); register_email_dispatcher composition-root precedent; Phase 42 CR-01 audit-emit FLAT-kwargs lesson"
  - phase: 43-multi-user-admin-module/01
    provides: "User ORM with is_active/status/deactivated_at lifecycle columns; password_hash nullable"
  - phase: 43-multi-user-admin-module/02
    provides: "users/schemas.py, users/email_templates.py (TEMPLATES + ROLE_RU)"
  - phase: 43-multi-user-admin-module/03
    provides: "invalidate_all_families_for_user impl; register_user_session_invalidator wiring; UserInvitedPayload.link_copied field; RefreshFailedPayload"
  - phase: 43-multi-user-admin-module/04
    provides: "users/repository.py 12-function surface (list_alive, get_alive, insert_user_pending_invitation, insert_invitation_token, consume_active_invitation_for_user, deactivate/reactivate/soft_delete, get_invitation_token_by_id, atomic_consume_invitation_token_by_id, count_active_owners_excluding with FOR UPDATE)"

provides:
  - "apps/backend/app/modules/users/service.py — 6 public async functions composing repository + audit + email + session-invalidation"
  - "10 domain exceptions in app/core/exceptions.py (UserNotFoundError, EmailAlreadyActiveError, UserAlreadyInactiveError, UserNotInactiveError, CannotDeactivateSelfError, CannotDeleteSelfError, CannotDeactivateLastOwnerError, CannotDeleteLastOwnerError, InvitationNotFoundError, InvitationAlreadyAcceptedError)"
  - "Settings.frontend_base_url config field (D-43-14) — invitation URL base"
  - "_format_expires_ru hand-rolled Russian long-form datetime helper (no new dep; babel deferred)"

affects:
  - 43-06 (router — imports service.create_user/list_users/deactivate_user/reactivate_user/soft_delete_user/revoke_invitation)
  - 43-07 (auth refresh extension — service.deactivate_user already wires sessions_revoked plumbing)
  - 43-09..14 (test files — integration tests target this service surface)
  - Phase 44 RESET-04 (invitation-accept may reuse same exceptions namespace)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "4-branch idempotent create_user with FLUSH-then-rollback for parallel-POST race (D-43-13)"
    - "Render-at-enqueue email envelope construction in the same UoW as the audit emit (D-43-24)"
    - "Atomic-consume race-loss → 409 mapping for revoke_invitation (D-43-19 / v1.1 refresh-rotation lineage)"
    - "FOR UPDATE last-owner guard via repository.count_active_owners_excluding (D-43-16)"
    - "Defensive session-invalidator call in soft_delete_user covers pure-delete-without-deactivate path"
    - "FLAT audit.emit kwargs matching pre-registered Pydantic shapes (Phase 42 CR-01 / D-43-04)"

key-files:
  created:
    - "apps/backend/app/modules/users/service.py (replaces Phase 41 SVC001 placeholder docstring with 357-line orchestration)"
  modified:
    - "apps/backend/app/core/exceptions.py (+10 domain exception classes)"
    - "apps/backend/app/core/config.py (+frontend_base_url Settings field)"

key-decisions:
  - "D-43-09: service owns transactional moment — repository emits 0 commit/flush; 5 public write functions each end with literal `await session.commit()` (SVC001 walker green)"
  - "D-43-13: 4-branch create_user — get_by_email_for_create resolves to None/pending/active; partial-UNIQUE on (lower(email)) WHERE deleted_at IS NULL silently routes the soft-deleted-row case to branch A (INSERT-only invariant at CREATE-time per Pitfall 4)"
  - "D-43-16: deactivate_user runs guards in order self → last-owner; FOR UPDATE acquired only when target.role == OWNER (cheap path for reception deactivates)"
  - "D-43-18: soft_delete_user uses the SAME guards as deactivate but allows the operation regardless of is_active (delete-after-deactivate is the common case)"
  - "D-43-19: revoke_invitation pre-check + race-loss both map to InvitationAlreadyAcceptedError (mirrors v1.1 refresh-rotation race-loss discipline)"
  - "D-43-24: email render happens at enqueue time inside service.create_user; the rendered subject/html/text envelope is passed as **kwargs to the EmailDispatcher slot — ARQ dispatch_email task never imports users.email_templates"
  - "D-43-14: invite_link_url returned to caller only when include_invite_link is True; the URL itself NEVER lands in the audit payload — only link_copied bool"
  - "Hand-rolled _format_expires_ru helper (no babel dep): tuple of 12 Russian month names in genitive case; output 'd мес yyyy в HH:MM'"
  - "Settings.frontend_base_url defaulted to http://localhost:5173 (matches admin-web dev server); production deployment overrides via .env"
  - "10 domain exceptions inherit from NotFoundError (404) or ConflictError (409) — match the existing exception hierarchy + AppError JSONResponse handler"

patterns-established:
  - "FLUSH-then-rollback-then-translate IntegrityError pattern reused from clients/service.py:122-128 for parallel-POST race on the partial-UNIQUE email constraint"
  - "audit_correlation_id generated once per logical create_user request (uuid4()) and threaded into BOTH the invitation token row AND the audit.emit kwargs — keeps the forensic chain joinable"

requirements-completed: [USERS-01, USERS-03, USERS-04, USERS-05]

# Metrics
duration: ~5min
completed: 2026-05-19
---

# Phase 43 Plan 05: Users Service Orchestration Summary

**6-function users service orchestration with 4-branch idempotent create, self+last-owner guards on deactivate/soft-delete, atomic-consume invitation revoke, FLAT audit kwargs, literal template_id, render-at-enqueue email — SVC001 commit invariant green across all 5 mutating functions.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-19T14:15:12Z
- **Completed:** 2026-05-19T14:20:47Z
- **Tasks:** 1 (single-task plan — `type=auto`, no checkpoints)
- **Files modified:** 3 (1 created — service.py replaces placeholder; 2 modified — exceptions.py + config.py)

## Accomplishments

- **Six public async functions landed:** `create_user`, `list_users`, `deactivate_user`, `reactivate_user`, `soft_delete_user`, `revoke_invitation` — each composes repository + audit + (where applicable) email-dispatcher + session-invalidator.
- **4-branch create_user (D-43-13):** existing.status == 'active' → 409; existing.status == 'pending_invitation' → atomic-consume + fresh token (idempotent re-invite); no row → INSERT + flush-then-rollback-IntegrityError translation; soft-deleted row → partial-UNIQUE excludes it, falls through to INSERT path.
- **Two-guard layer (D-43-16/18):** `deactivate_user` and `soft_delete_user` both run self-guard + last-owner guard (latter via repository.count_active_owners_excluding with FOR UPDATE). `reactivate_user` has NO guards (always safe).
- **Atomic-consume race-tight revoke (D-43-19):** pre-check (consumed_at IS NOT NULL) OR UPDATE...RETURNING returning zero rows → 409 invitation_already_accepted. Mirrors v1.1 refresh-rotation race-loss discipline.
- **Render-at-enqueue email (D-43-24):** `create_user` builds the EmailEnvelope (subject + html + text) in-line, passes via **kwargs to `get_email_dispatcher()(template_id="USER_INVITATION_EMAIL", ...)` — literal template_id satisfies the Phase 41 D-41-11 AST gate.
- **FLAT audit kwargs (D-43-04 / Phase 42 CR-01):** All 5 `audit.emit(...)` calls pass payload fields as direct kwargs matching the pre-registered Pydantic schemas in `audit_payloads.py:513-602`. Zero `payload={...}` nesting.
- **SVC001 commit invariant verified:** 5 mutating functions each carry literal `await session.commit()` (D-41-28 walker target).
- **Session invalidation plumbed:** `deactivate_user` and `soft_delete_user` both call `get_user_session_invalidator()(session, user_id=..., reason=...)`; `sessions_revoked_count` flows into `UserDeactivatedPayload.sessions_revoked_count`.
- **10 domain exceptions added to exceptions.py:** all inherit from `NotFoundError` (404) or `ConflictError` (409); match the existing `AppError` JSON-response handler shape exactly.

## Function Inventory

| Function | Purpose | Decision lineage |
|---|---|---|
| `list_users` | Paginated read; no audit, no commit | D-43-15 |
| `create_user` | 4-branch invitation flow + email enqueue + audit | D-43-13 / D-43-14 / D-43-24 |
| `deactivate_user` | Self+last-owner guard, UPDATE, session revoke, audit | D-43-16 |
| `reactivate_user` | UPDATE, audit; NO guards | D-43-17 |
| `soft_delete_user` | Same guards as deactivate, UPDATE, defensive session revoke, atomic-consume invitations, audit | D-43-18 |
| `revoke_invitation` | Pre-check + atomic-consume race-loss → 409, audit | D-43-19 |

## Task Commits

1. **Task 1: Land users/service.py + 10 domain exceptions + Settings.frontend_base_url** — `501a9a7` (feat)

**Plan metadata commit:** _(pending after STATE.md + ROADMAP.md update)_

## Files Created/Modified

- `apps/backend/app/modules/users/service.py` (357 lines — replaces Phase 41 SVC001 placeholder docstring)
- `apps/backend/app/core/exceptions.py` (+10 domain exception classes at the Phase 43 section before `register_exception_handlers`)
- `apps/backend/app/core/config.py` (+`frontend_base_url: str = "http://localhost:5173"` field on `Settings`)

## Acceptance Criteria Verification

All 14 plan acceptance criteria PASS:

| Criterion | Expected | Actual |
|---|---|---|
| `grep -c 'async def create_user'` | 1 | 1 |
| `grep -c 'async def deactivate_user'` | 1 | 1 |
| `grep -c 'async def reactivate_user'` | 1 | 1 |
| `grep -c 'async def soft_delete_user'` | 1 | 1 |
| `grep -c 'async def revoke_invitation'` | 1 | 1 |
| `grep -c 'async def list_users'` | 1 | 1 |
| `grep -c 'await session.commit()'` | ≥ 5 | 5 |
| `grep -c 'template_id="USER_INVITATION_EMAIL"'` | 1 | 2 (1 callsite + 1 docstring reference) |
| `grep -c 'get_user_session_invalidator()('` | 2 | 2 |
| `grep -c 'get_email_dispatcher()('` | 1 | 1 |
| `grep -c 'payload={'` | 0 | 0 |
| `grep -c 'audit.emit('` | 5 | 5 |
| `grep -c 'count_active_owners_excluding'` | 2 | 3 (1 docstring + 2 callsites) |
| `grep -cE 'CannotDeactivateSelfError|cannot_deactivate_self'` | ≥ 1 | 2 |
| `grep -cE 'CannotDeactivateLastOwnerError|cannot_deactivate_last_owner'` | ≥ 1 | 2 |
| ruff + mypy --strict | green | green |

Audit payload Pydantic shape match (independent validation):

```
UserInvitedPayload          ← {audit_correlation_id, invited_user_id, invited_email, invited_role, invitation_expires_at, link_copied}     ✓
UserDeactivatedPayload      ← {audit_correlation_id, deactivated_user_id, sessions_revoked_count}                                         ✓
UserReactivatedPayload      ← {audit_correlation_id, reactivated_user_id}                                                                  ✓
UserSoftDeletedPayload      ← {audit_correlation_id, deleted_user_id}                                                                      ✓
UserInvitationRevokedPayload ← {audit_correlation_id, revoked_user_id, invitation_token_id, reason}                                       ✓
```

All 5 schemas validate cleanly against the kwargs each `audit.emit` call passes.

## Decisions Made

- **Hand-rolled Russian-date helper over babel.** No `babel` in `apps/backend/pyproject.toml`; pulling it in for a single-locale CRM with one render path is over-engineering. The 12-entry month-name tuple plus an f-string is six lines and self-evident; the snapshot test in 43-02 already exercises the format end-to-end.
- **`Settings.frontend_base_url` default `http://localhost:5173`.** Matches the admin-web Vite dev port; production deployment overrides via `.env`. No URL stored in audit payloads (D-43-14 / Pitfall 4 anti-oracle).
- **Domain exceptions inherit from the existing `NotFoundError`/`ConflictError` hierarchy.** Matches the established `AppError` JSON-response handler (`apps/backend/app/core/exceptions.py:298-309`). No new top-level exception class; no new handler wiring.
- **`audit_correlation_id` generated once per `create_user` request** and threaded into BOTH the `password_reset_tokens.audit_correlation_id` column AND the `audit.emit` kwargs. Keeps the forensic chain joinable: a single UUID links the invitation token row, the `user_invited` audit row, and the future `email_sent` / `email_send_failed` audit rows.
- **`secrets.token_urlsafe(32)`** — 32 random bytes → 43-char URL-safe string. Matches Phase 41 / RESET-03 spec (D-41-04) for invitation token entropy.
- **`reactivate_user` does NOT auto-restore sessions.** Refresh families revoked at deactivate time stay revoked; reactivated user re-authenticates via the normal login path. Documented in the function docstring (D-43-17).

## D-43-04 Verification — FLAT audit emit kwargs

`grep -c 'payload={' apps/backend/app/modules/users/service.py` → **0**

Every `audit.emit(...)` call in `service.py` passes payload fields as direct kwargs, matching the pre-registered Pydantic shapes with `extra='forbid'`. Phase 42 CR-01 lesson honoured.

## SVC001 commit invariant verification

```
$ python -c "import inspect; from app.modules.users import service; \
  [print(fn, 'await session.commit()' in inspect.getsource(getattr(service, fn))) \
   for fn in ['create_user','deactivate_user','reactivate_user','soft_delete_user','revoke_invitation']]"
create_user True
deactivate_user True
reactivate_user True
soft_delete_user True
revoke_invitation True
```

All 5 mutating public functions carry the literal commit token — D-41-28 SVC001 walker green.

## Domain Russian-Date Helper Choice

**Hand-rolled** (`_format_expires_ru` in `service.py`). Rationale:

- No `babel` dependency in `apps/backend/pyproject.toml`; adding it for one render path is over-engineering.
- Single locale (Russian) — no need for locale-arbitration code.
- 12-element month-name tuple + f-string is six lines and self-evident.
- Output format matches the snapshot fixture from 43-02 (e.g. `"26 мая 2026 в 12:00"`).

If a future requirement demands BCP-47-style locale arbitration (Phase 45/46 notification multi-channel?), the helper is a single function that can be swapped for babel without touching callers.

## Deviations from Plan

### Auto-fixed Issues

None.

### Plan-prose vs. environment discoveries (documented, NOT deviations)

1. **`Settings.frontend_base_url` did not exist before this plan** — added it per D-43-14 (Rule 2: required for service correctness). The plan's `<action>` block explicitly flagged this contingency ("If `settings.frontend_base_url` does not exist, add a discretion note in SUMMARY"). Defaulted to `http://localhost:5173`.
2. **`babel` is not a project dependency** — used the hand-rolled `_format_expires_ru` per the plan's contingency note ("Use the hand-rolled helper (no new dep) unless `babel` is already in `pyproject.toml`").
3. **`app/core/exceptions.py` already had the `AppError` / `NotFoundError` / `ConflictError` base hierarchy** — followed the existing convention (class-level `code` + `status_code`) rather than the plan's looser "or define locally" alternative. All 10 new exceptions are centralised in `exceptions.py`.

**Total deviations:** 0 (the three notes above are contingency-resolution decisions explicitly authorised by the plan's `<action>` block).

## Issues Encountered

None.

## User Setup Required

None for development — `Settings.frontend_base_url` defaults to `http://localhost:5173`.

For production: set `FRONTEND_BASE_URL=https://app.sportzal.example.com` (or equivalent) in the production `.env` before invitation emails are sent. The default would render invitation URLs pointing at `localhost`, which is fine for dev but useless in production.

## Threat Flags

None — Plan 43-05 adds no new network endpoints or trust-boundary surface (the endpoints land in 43-06; this plan ships the orchestration only). The `Settings.frontend_base_url` field carries operator-controlled config; the only place it enters the wire is as part of the invitation email body and the optional `?include_invite_link=true` response, both already audit-logged via `user_invited` with `link_copied: bool` (URL itself never in the payload — D-43-14 / Pitfall 4 honoured).

## Next Phase Readiness

- **Plan 43-06 (router) unblocked:** can `from app.modules.users import service` and wire all 6 endpoints (`GET/POST /users`, `PATCH /{id}/deactivate`, `PATCH /{id}/reactivate`, `DELETE /{id}`, `POST /invitations/{id}/revoke`) with RBAC + CSRF dependency chain.
- **Plan 43-07 (auth refresh extension) independent:** no dependency on this plan beyond the existing `RefreshFailedPayload` from 43-03.
- **Plans 43-09..14 (test files) unblocked:** integration tests can target the 6-function surface via the (future) router endpoints; `tests/unit/test_locked_email_templates_ast.py` extension (per D-43-33) can now find the real `template_id="USER_INVITATION_EMAIL"` callsite at `service.py`.
- **All 14 acceptance criteria PASS** + audit payload shape validation independent check PASS + ruff/mypy --strict green.

## Self-Check: PASSED

- `apps/backend/app/modules/users/service.py`: FOUND (357 lines)
- `apps/backend/app/core/exceptions.py`: FOUND (10 new classes appended before `register_exception_handlers`)
- `apps/backend/app/core/config.py`: FOUND (`frontend_base_url` field present on `Settings`)
- Commit `501a9a7`: FOUND
- `uv run ruff check app/modules/users/service.py`: PASS
- `uv run mypy --strict app/modules/users/`: PASS (7 source files)
- 14 / 14 acceptance grep checks PASS
- All 5 audit payload shapes validate against pre-registered Pydantic schemas

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
