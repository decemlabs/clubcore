---
phase: 44-invitation-password-reset-flow
plan: 03
subsystem: auth
tags:
  - service-skeleton
  - atomic-consume
  - exceptions
  - locked-signatures
dependency_graph:
  requires:
    - phase-41-d-41-04-password-reset-tokens-table
    - phase-41-d-41-28-svc001-target-file-coverage
    - phase-43-app-core-exceptions-invitationalreadyacceptederror
  provides:
    - auth-module-locked-service-signatures
    - auth-module-410-422-409-exception-surface
  affects:
    - waves: [44-04, 44-05, 44-06, 44-07]
tech_stack:
  added: []
  patterns:
    - typed-skeleton-with-notimplementederror
    - re-export-via-subclass-preserves-isinstance
key_files:
  created: []
  modified:
    - apps/backend/app/modules/auth/exceptions.py
    - apps/backend/app/modules/auth/password_reset_service.py
decisions:
  - rule-1-fix-omitted-invitation-token-ttl-import-import-linter-violation
metrics:
  duration: 1h
  completed: 2026-05-19
requirements_touched:
  - RESET-02
  - RESET-04
---

# Phase 44 Plan 03: Service Skeleton + 3 Exceptions Summary

Skeleton for `app/modules/auth/password_reset_service.py` with 3 public service stubs + 1 private atomic-consume helper at locked signatures, and 3 new exceptions in `app/modules/auth/exceptions.py` covering the 410/422/409 wire surface Wave 2 will raise from.

## Shipped Surface

### Functions in `app/modules/auth/password_reset_service.py`

| Function | Signature | Returns | Purpose |
| --- | --- | --- | --- |
| `_atomic_consume_token` | `(session: AsyncSession, *, raw_token: str, purpose: Literal["password_reset", "invitation"])` | `tuple[UUID, UUID, UUID \| None] \| None` | Single-SQL UPDATE…RETURNING by `token_hash`. None ⇒ replay/expired/unknown (anti-oracle collapse per D-44-14/19). No commit — caller-owns-UoW (D-03 / SVC001). |
| `request_password_reset` | `(session: AsyncSession, redis: Redis, *, email: str, client_ip: str)` | `None` | RESET-01 anti-oracle issuance. 4-case identical envelope (D-44-06), 500ms constant-time floor (D-44-07), 3-key rate-limit (D-44-10/13), dual-branch audit emit (D-44-08), email enqueue only in active branch (D-44-09). Service-owns-commit. |
| `confirm_password_reset` | `(session: AsyncSession, *, raw_token: str, new_password: str)` | `None` | RESET-02 atomic-consume + Argon2id rehash + revoke-all + audit emit + 410-on-failure / 422-on-weak-password (D-44-15/16/17). Service-owns-commit. NO new login cookies issued post-reset (D-44-16 step 5). |
| `accept_invitation` | `(session: AsyncSession, *, raw_token: str, new_password: str, full_name: str \| None)` | `tuple[UUID, str, str, str]` | RESET-04 invitation-accept atomic-consume + UPDATE-only user-row mutation (D-44-19/20). Returns `(user_id, email, role, full_name)` for caller-side `issue_tokens` + `issue_session_cookies` per D-44-21. 409 on UPDATE 0-rows race (D-44-20). Service-owns-commit. |

All four bodies are `raise NotImplementedError("Wave 2 plan 44-04 fills this body.")` — total 4 occurrences, matching the acceptance criterion.

### Exception classes in `app/modules/auth/exceptions.py`

| Class | `code` | `status_code` | Decision | Raised by |
| --- | --- | --- | --- | --- |
| `InvalidOrExpiredTokenError` | `"invalid_or_expired_token"` | 410 | D-44-15 / D-44-19 | `confirm_password_reset`, `accept_invitation` — atomic-consume returned None. |
| `WeakPasswordError` | `"weak_password"` | 422 | D-44-17 | `confirm_password_reset`, `accept_invitation` — strength predicate fails BEFORE atomic-consume. |
| `InvitationAlreadyAcceptedError` | `"invitation_already_accepted"` | 409 | D-44-20 | `accept_invitation` — pending-user UPDATE returned 0 rows. |

All three extend `AppError` (verified via the smoke-import isinstance chain).

## Cross-module identity for `InvitationAlreadyAcceptedError`

The Phase 43 codebase already ships an `InvitationAlreadyAcceptedError` in `app/core/exceptions.py` (registered at line 387, used by the Phase 43 users module). To avoid two distinct exception classes carrying the same domain meaning, the new `app.modules.auth.exceptions.InvitationAlreadyAcceptedError` **subclasses** the existing core class. Wire shape (`code="invitation_already_accepted"`, `status_code=409`) is inherited verbatim, and `isinstance(e, core.InvitationAlreadyAcceptedError)` still holds at Phase 43 callsites — no Phase 43 regression risk.

## Deviations from Plan

### Rule 1 — Fix plan bug: omit `INVITATION_TOKEN_TTL` import to satisfy locked import-linter contract

- **Found during:** Task 2 — `uv run lint-imports` failed with:
  > `app.modules.auth is not allowed to import app.modules.users:`
  > `app.modules.auth.password_reset_service -> app.modules.users.constants (l.51)`
- **Issue:** The plan's required-imports block in Task 2 listed
  `from app.modules.users.constants import INVITATION_TOKEN_TTL` AND the
  acceptance criteria also demanded `uv run lint-imports` exits 0 —
  internally contradictory. The locked architectural rule (CLAUDE.md
  "Tooling: import-linter … обязательны с Phase A") and the
  `modules cannot import each other` contract together make the original
  import block unconstructible.
- **Fix:** Omitted the `INVITATION_TOKEN_TTL` import. Replaced the line with a
  multi-line explanatory comment at the same import-block location,
  documenting (a) why it was removed, (b) that `accept_invitation`'s D-44-20
  invariant ("NEVER INSERTs a users row, NEVER re-issues an invitation
  token") means the constant is not needed at the accept callsite, and
  (c) a future-architecture pointer (move to `app.core` if a Phase ≥45
  flow ever does need it from `auth`).
- **Files modified:** `apps/backend/app/modules/auth/password_reset_service.py`
- **Commit:** `6f4e93d`
- **Plan ripple:** Wave 2's `accept_invitation` body (plan 44-04 or 44-06)
  should NOT reach for `INVITATION_TOKEN_TTL` from `users.constants`; if a
  Wave 2 author needs the value, inline `timedelta(days=7)` locally or
  raise a Rule-4 architectural decision to relocate the constant.

### Note — `http_status` vs `status_code` attribute name in Plan's verify command

- **Not a deviation in shipped code** — the plan's `<verify>` block for Task 1
  used `InvalidOrExpiredTokenError.http_status` in the smoke assertion. The
  actual codebase `AppError` base class uses `status_code` (verified at
  `app/core/exceptions.py:11`). I executed the verify with the correct
  attribute name; the smoke assertion passed. The shipped exceptions match
  the codebase convention (`status_code`), not the plan's typo. Wave 2 will
  read `status_code` from these classes — no further action needed.

### Pre-existing mypy errors in unrelated files (not introduced by this plan)

`uv run mypy --strict app/modules/auth/password_reset_service.py` reports 2
pre-existing errors in `auth/service.py:45` and `auth/telegram_service.py:45`
(`Module "app.modules.auth.models" does not explicitly export attribute "User"`).
These predate Phase 44 and are out of scope per the Rule-scope-boundary.
Logged for awareness; not addressed.

## Wave-1 Sibling-Plan Dependency

Plan 44-03 ships imports from siblings 44-01 (`app/modules/auth/constants.py`
+ `app/modules/auth/reset_rate_limit.py`) and 44-02 (`PASSWORD_RESET_EMAIL`
entry in `app/modules/auth/email_templates.py`). The plan frontmatter
declares `depends_on: []` and `wave: 1` — parallel sibling plans are
expected to merge atomically. In this isolated worktree at the
parallel-plan stage, those sibling modules are not present on disk, so:

- `uv run mypy --strict app/modules/auth/password_reset_service.py` reports
  2 additional errors (lines 41-42) for the missing `reset_rate_limit` and
  `constants` modules.
- `uv run python -c "from app.modules.auth import password_reset_service"`
  raises `ImportError: cannot import name 'reset_rate_limit'`.

Both deltas resolve automatically once the wave-1 sibling worktrees land
(orchestrator merges 44-01 + 44-02 + 44-03 together). The skeleton's wire
shape — function signatures, exception identities, import paths — is
correct; the verifications that pass independently of the wave merge
(ruff, lint-imports, SVC001 walker, workers eager-import) all exit 0.

## Verification Snapshot

| Check | Scope | Result |
| --- | --- | --- |
| `uv run ruff check app/modules/auth/exceptions.py` | Task 1 | exit 0 |
| `uv run mypy --strict app/modules/auth/exceptions.py` | Task 1 | exit 0 (Success: no issues) |
| Smoke import + code/status assertions (3 classes) | Task 1 | `OK` |
| `uv run ruff check app/modules/auth/password_reset_service.py` | Task 2 | exit 0 |
| `uv run lint-imports` | Task 2 | exit 0 (3 contracts kept, 0 broken) |
| `uv run pytest tests/unit/test_workers_eager_import.py -q` | Task 2 (D-44-33) | 3 passed |
| `uv run pytest tests/unit/test_service_commit_gate.py -q` | Task 2 (SVC001) | 7 passed |
| `uv run mypy --strict app/modules/auth/password_reset_service.py` | Task 2 | exits 1 due to missing wave-1-sibling modules (`constants`, `reset_rate_limit`) — see Wave-1 Sibling-Plan Dependency above |
| `uv run python -c "from app.modules.auth import password_reset_service"` | Task 2 | ImportError pending wave-1 sibling merge — see above |

10 acceptance-criteria greps for Task 2 all match (4× `async def …`, 4× `raise NotImplementedError`, 4× required leaf-module import lines).

## Commits

| Task | Commit | Message |
| --- | --- | --- |
| 1 | `521fcd9` | `feat(44-03): add 3 password-reset+invitation exceptions to auth.exceptions` |
| 2 | `6f4e93d` | `feat(44-03): replace password_reset_service placeholder with typed skeleton` |

## Self-Check: PASSED

- `apps/backend/app/modules/auth/exceptions.py` — FOUND (modified, +59 lines)
- `apps/backend/app/modules/auth/password_reset_service.py` — FOUND (replaced, 252 lines)
- Commit `521fcd9` — FOUND in `git log`
- Commit `6f4e93d` — FOUND in `git log`
- All 6 acceptance-grep checks for Task 1 — PASS
- All 10 acceptance-grep checks for Task 2 — PASS
- ruff (both files) — exit 0
- mypy (`exceptions.py` standalone) — exit 0
- import-linter (full project) — exit 0
- SVC001 walker (`test_service_commit_gate.py`) — 7 passed
- workers eager-import test — 3 passed
- mypy on `password_reset_service.py` — pending wave-1-sibling merge (44-01 contributes `constants.py` + `reset_rate_limit.py`); deviation transparently documented above
