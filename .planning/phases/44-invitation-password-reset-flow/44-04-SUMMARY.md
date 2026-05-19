---
phase: 44-invitation-password-reset-flow
plan: 04
subsystem: auth
tags: [service, anti-oracle, atomic-consume, audit-emit, password-reset, invitation-accept]
requires:
  - 44-01 (constants, reset_rate_limit)
  - 44-02 (PASSWORD_RESET_EMAIL template)
  - 44-03 (skeleton signatures + exceptions)
provides:
  - request_password_reset (RESET-01 anti-oracle envelope)
  - confirm_password_reset (RESET-02 atomic-consume + revoke-all)
  - accept_invitation (RESET-04 UPDATE-only user mutation)
  - _atomic_consume_token (RESET-02/04 single-SQL UPDATE-RETURNING helper)
affects:
  - apps/backend/app/modules/auth/password_reset_service.py
tech-stack:
  added: []
  patterns:
    - Single-SQL UPDATE-RETURNING for race-tight atomic-consume (mirrors Phase 43 D-43-19 invitation revoke)
    - Pre-commit email enqueue via ARQ Protocol slot (mirrors Phase 43 users/service.py:230-240)
    - 500ms wall-clock floor via time.perf_counter + asyncio.sleep (mirrors auth/service._constant_time_floor)
    - Russian-locale Europe/Moscow datetime formatting (inlined duplicate from users/service per import-linter ban)
key-files:
  created: []
  modified:
    - apps/backend/app/modules/auth/password_reset_service.py
decisions:
  - "PASSWORD_RESET_EMAIL enqueue passes RAW template_vars (reset_url + expires_at_human); dispatcher renders subject/html/text at enqueue time. Plan instructions said pre-render envelope but the dispatcher signature only accepts **template_vars — pre-rendered subject/html/text would be silently dropped by Jinja (CR-01 lesson, Phase 43 users/service.py:200-202 commentary)."
  - "audit.emit kwargs use resource_type (not resource_kind as the plan example showed); resource_type matches audit.emit's actual signature at audit.py:308."
  - "Removed unused EmailEnvelope import — dispatcher constructs the envelope internally at dispatcher.py:176; the service has no reason to import the transport DTO."
metrics:
  duration_minutes: 12
  completed_date: 2026-05-19
  tasks_completed: 4
  files_modified: 1
  lines_changed: ~340
  commits: 4
---

# Phase 44 Plan 04: Password Reset Service Body Implementation Summary

One-paragraph: Filled the 4 stub bodies in `apps/backend/app/modules/auth/password_reset_service.py` (Wave 1 skeleton) to ship the anti-oracle reset request envelope, single-UoW confirm flow, and UPDATE-only invitation accept — all preserving the Phase 42 CR-01 flat audit-emit invariant, the Phase 41 D-41-11 literal template_id AST gate, the D-44-14/19 single-SQL atomic-consume race-tightness, and SVC001 service-owns-commit. Three mutating service functions, one atomic-consume helper, ~340 net lines added across 4 atomic commits.

## Canonical Atomic-Consume SQL (Wave 4 test pattern-matching)

The SQLAlchemy 2.0 imperative form lands as:

```python
stmt = (
    update(PasswordResetToken)
    .where(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.purpose == purpose,
        PasswordResetToken.consumed_at.is_(None),
        PasswordResetToken.expires_at > func.now(),
    )
    .values(consumed_at=func.now())
    .returning(
        PasswordResetToken.id,
        PasswordResetToken.user_id,
        PasswordResetToken.audit_correlation_id,
    )
    .execution_options(synchronize_session=False)
)
```

RETURNING projection: `(id, user_id, audit_correlation_id)` — column count + order locked. `token_hash` is `hashlib.sha256(raw_token.encode()).hexdigest()`.

## Module-Level Helpers

| Name | Kind | Purpose |
|------|------|---------|
| `_RESPONSE_FLOOR_SECONDS` | `Final[float] = 0.5` | 500ms wall-clock floor (D-44-07) |
| `_floor_response_time(started)` | `async def` | Awaits `asyncio.sleep(max(0, 0.5 - elapsed))` |
| `_MOSCOW_TZ` | `Final[ZoneInfo]` | `ZoneInfo("Europe/Moscow")` |
| `_RU_MONTHS_GENITIVE` | `Final[tuple[str, ...]]` | 12 Russian month names (genitive case) |
| `_format_expires_ru(dt)` | sync | Russian long-form datetime with `(МСК)` suffix |

`_format_expires_ru` is a verbatim inline duplicate of `app.modules.users.service._format_expires_ru` (lines 80-115) because the import-linter contract forbids `auth -> users` cross-module imports.

## Service Function Surface

| Function | Success | Failure → Exception (HTTP code) |
|----------|---------|----------------------------------|
| `request_password_reset(session, redis, *, email, client_ip) -> None` | Returns `None` for all 4 anti-oracle cases AND rate-limit-hit | `RateLimited` is CAUGHT and silently swallowed to 202; structlog WARN only (D-44-11). No other exception caught here; DB/dispatcher errors propagate as 500 (anti-oracle preserved at the HTTP envelope shape level). |
| `confirm_password_reset(session, *, raw_token, new_password) -> None` | Returns `None` (router maps to HTTP 200 `envelope(None)`) | `WeakPasswordError` (422, D-44-17 — token stays valid for retry); `InvalidOrExpiredTokenError` (410, replay/expired/unknown collapse per D-44-15). |
| `accept_invitation(session, *, raw_token, new_password, full_name) -> tuple[UUID, str, str, str]` | Returns `(user_id, email, role_value, full_name)` for the router to issue cookies (D-44-21) | `WeakPasswordError` (422); `InvalidOrExpiredTokenError` (410); `InvitationAlreadyAcceptedError` (409, millisecond-scale race per D-44-20). |
| `_atomic_consume_token(session, *, raw_token, purpose) -> tuple[UUID, UUID, UUID \| None] \| None` | Returns `(token_id, user_id, audit_correlation_id)` | Returns `None` on zero rows (replay/expired/unknown collapse — D-44-14/15/19). Never raises. |

## Email Enqueue Pattern (PRE-COMMIT, raw template_vars)

```python
await get_email_dispatcher()(
    template_id="PASSWORD_RESET_EMAIL",
    to=email_lower,
    audit_correlation_id=audit_correlation_id,
    reset_url=reset_url,
    expires_at_human=expires_at_human,
)
```

This is BEFORE `await session.commit()` (matches Phase 43 `users/service.py:230-240` ordering — D-44-04 algorithm body, anchor). The dispatcher renders subject/html/text from the locked template at enqueue time (dispatcher.py:171-172).

## Inline Helper Duplication Log

- `_format_expires_ru` — duplicated from `users/service.py:100-115`. Rationale: `auth -> users` import is forbidden by import-linter contract "modules cannot import each other". 15-line copy accepted per 44-CONTEXT § Reusable Assets carve-out. If a third callsite ever needs it, the function should be lifted to `app.core.i18n` (architectural change — Rule 4).
- `_RU_MONTHS_GENITIVE`, `_MOSCOW_TZ` — same duplication rationale.

## Deviations from Plan

### Rule 1 (auto-fix bug) — Plan instruction would have triggered CR-01 defect

**1. [Rule 1 - Bug] Use raw template_vars instead of pre-rendered EmailEnvelope at dispatcher callsite**

- **Found during:** Task 2 (request_password_reset implementation)
- **Issue:** The plan algorithm (step 7a (vi) + 7b) instructed to construct an `EmailEnvelope` dataclass with pre-rendered `subject` / `html_body` / `text_body` via `tpl.html.render(...)` and pass them as kwargs to `get_email_dispatcher()(...)`. This contradicts the dispatcher's actual signature (`apps/backend/app/integrations/email/dispatcher.py:133-138`), which takes `**template_vars` and renders subject/html/text internally at enqueue time. Passing `subject="..."` etc. would be silently absorbed into `**template_vars` and never reach the Jinja template renderer — the EXACT CR-01 defect documented in `users/service.py:200-202` ("passing subject/html/text as **template_vars is silently ignored by Jinja and was the CR-01 defect").
- **Fix:** Followed the plan's own canonical anchor (line 175 — "Match the verbatim kwargs shape that `users/service.py:230-238` uses") and passed raw `reset_url` + `expires_at_human` template_vars. Dispatched the rendering responsibility back to `enqueue_email_dispatch` per Phase 43 D-43-24 contract.
- **Side effect:** Dropped `from app.integrations.email.types import EmailEnvelope` from imports (no longer used in the service). The `EmailEnvelope` transport DTO is internal to `dispatcher.py`.
- **Commit:** f88aa8c (Task 2)

**2. [Rule 1 - Bug] Use `resource_type=` kwarg (not `resource_kind=`) in audit.emit calls**

- **Found during:** Task 2 (request_password_reset audit emit)
- **Issue:** The plan's example `audit.emit(...)` snippets (line 126-137, 354-365, 538-548, 642-651) used `resource_kind=` kwargs. The actual `audit.emit` signature at `app/core/audit.py:303-311` defines `resource_type: str` (positional kwarg, no `resource_kind` alias).
- **Fix:** All three audit.emit calls use `resource_type="user"` matching the canonical signature and the Phase 43 callsites (e.g. `users/service.py:215`).
- **Commit:** f88aa8c (Task 2), d1bc9e3 (Task 3), 513fb7e (Task 4)

### Rule 3 (auto-fix blocking issue) — pre-existing mypy errors out of scope

`mypy --strict` reports 2 errors:
- `apps/backend/app/modules/auth/telegram_service.py:45: error: Module "app.modules.auth.models" does not explicitly export attribute "User"`
- `apps/backend/app/modules/auth/service.py:45: error: Module "app.modules.auth.models" does not explicitly export attribute "User"`

These are pre-existing in unrelated files (NOT this plan's `password_reset_service.py`, which is clean). Out of scope per SCOPE BOUNDARY (only auto-fix issues directly caused by current task's changes). The fix would require adding `__all__ = ["User"]` to `app/modules/auth/models.py` — a Wave 1 / cross-cutting change. Logged as deferred for the orchestrator-level merge to consider; THIS file passes mypy strict.

## Auth Gates

None — fully autonomous execution, no authentication or external-system interactions.

## Known Stubs

None — all 4 stubs filled with substantive UoW bodies.

## Threat Flags

None — no new threat surface introduced beyond what plan 44-04's `<threat_model>` already enumerates (T-44-04-01 through T-44-04-08, all `mitigate` disposition).

## Phase 44 Invariants Verified Green at grep Level

| Invariant | Verification |
|-----------|--------------|
| Phase 42 CR-01 flat audit kwargs | `grep -c "payload=" → 0` |
| Phase 41 D-41-11 literal template_id AST gate | `grep -c 'template_id="PASSWORD_RESET_EMAIL"' → 1` (only request_password_reset enqueues) |
| INSERT-only invariant on accept_invitation | `grep -c "session.add(User(" → 0` |
| 3 service functions all have `await session.commit()` | actual call count: 3 (request line 335, confirm line 422, accept line 504) |
| SVC001 walker | `tests/unit/test_service_commit_gate.py` → 7 passed |
| import-linter contract | `uv run lint-imports` → 3 kept, 0 broken |
| workers eager-import | `tests/unit/test_workers_eager_import.py` → 3 passed |
| Import smoke | `from app.modules.auth.password_reset_service import …` → OK |
| ruff check | `uv run ruff check app/modules/auth/password_reset_service.py` → passed |
| mypy strict (this file) | `uv run mypy --strict … password_reset_service.py` → 0 errors in this file |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `b2a3a31` | `feat(44-04): implement _atomic_consume_token single-SQL UPDATE-RETURNING` |
| 2 | `f88aa8c` | `feat(44-04): implement request_password_reset anti-oracle envelope` |
| 3 | `d1bc9e3` | `feat(44-04): implement confirm_password_reset atomic-consume + rotate + revoke` |
| 4 | `513fb7e` | `feat(44-04): implement accept_invitation atomic-consume + UPDATE-only` |

## Self-Check: PASSED

- Created file: `.planning/phases/44-invitation-password-reset-flow/44-04-SUMMARY.md` — confirmed.
- All 4 commits exist on `worktree-agent-a8826c6383e188f1e` branch (verified via `git log --oneline -5`).
- All grep / pytest / ruff / mypy / lint-imports verifications green at execution time.
