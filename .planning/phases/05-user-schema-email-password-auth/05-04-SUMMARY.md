---
phase: 05-user-schema-email-password-auth
plan: 04
subsystem: auth-service
tags: [auth, rate-limit, refresh-rotation, session, redis, postgres]
requirements-completed: [AUTH-05, AUTH-06, AUTH-EP-03, AUTH-LO-03]
requires:
  - apps/backend/app/core/security.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/redis.py
  - apps/backend/app/core/config.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/modules/auth/models.py
provides:
  - app.modules.auth.rate_limit.check_login_rate
  - app.modules.auth.rate_limit.bump_login_rate
  - app.modules.auth.service.load_user_by_id
  - app.modules.auth.service.authenticate
  - app.modules.auth.service.issue_tokens
  - app.modules.auth.service.rotate_refresh
  - app.modules.auth.service.revoke_session
  - app.modules.auth.service.revoke_all_sessions
  - app.modules.auth.service.revoke_sessions_on_password_change
affects:
  - apps/backend/app/modules/auth/rate_limit.py
  - apps/backend/app/modules/auth/service.py
tech-stack:
  added: []
  patterns:
    - "fixed-window per-email rate limiter (Redis INCR + EXPIRE pipeline)"
    - "lazy sentinel-hash for timing-equivalent user-not-found path (Argon2)"
    - "DB-led refresh-rotation with SELECT ... FOR UPDATE row-lock"
    - "auth:rotate:{hash} race-window cache (NX) for idempotent same-pair return"
    - "family-revocation triple-branch state machine (D-13)"
    - "single-begin transaction guard against AsyncSession autobegin collision"
    - "typing.cast over redis-py ResponseT union for mypy strict"
key-files:
  created:
    - apps/backend/app/modules/auth/rate_limit.py
  modified:
    - apps/backend/app/modules/auth/service.py
decisions:
  - "Rate-limit key uses email_lower (D-19); per-IP rejected for RU/CIS NAT pollution"
  - "Sentinel hash generated lazily on first auth call (avoid ~50ms blocking import)"
  - "Forward reference revoke_sessions_on_password_change -> revoke_all_sessions resolved at call time (Python late-binding)"
  - "redis.srem / redis.smembers wrapped with cast(Awaitable[...], ...) — redis-py ResponseT is Union[Awaitable[T], T] across sync/async clients"
  - "revoke_session SELECT and UPDATE share a single async with session.begin() block (autobegin guard per plan D-14 implementation note)"
metrics:
  duration_seconds: 277
  duration_human: "~4 min"
  completed: 2026-05-02
  commits: 3
  tasks_completed: 3
  files_created: 1
  files_modified: 1
  total_lines: 535
---

# Phase 05 Plan 04: Auth Service (Login + Refresh Rotation + Family Revocation) Summary

Service-layer hot path of Phase 5: rate-limited login with timing-equivalent user-not-found, DB-locked refresh rotation with 5-second idempotent-replay window, and family revocation on token reuse — all in `app/modules/auth/service.py` (488 LOC) plus a dedicated `rate_limit.py` (47 LOC).

## Objective Recap

Implement the full SQL+Redis seam for Phase 5 authentication:

- `rate_limit.py` — per-email fixed-window counter (5/15min), gate before Argon2 (D-18, D-19, AUTH-EP-03)
- `service.py` — seven public functions covering login, token mint, rotation, and revocation flows that thin Phase-5 router endpoints (Plan 05-06) can wrap one-to-one

This plan owns the racy parts (parallel `/auth/refresh`, family-reuse detection, password-change revoke). Get it right here so the router stays trivial.

## What Was Built

### rate_limit.py (47 LOC, new)

Two functions in tight scope:

- `check_login_rate(redis, email_lower) -> None` — `GET ratelimit:login:{email_lower}`; raises `RateLimited("rate_limited")` when count >= 5.
- `bump_login_rate(redis, email_lower) -> None` — `INCR + EXPIRE 900` in a single pipeline; INCR-then-EXPIRE order so EXPIRE always lands on a key that exists.

Module constants `_LIMIT = 5`, `_WINDOW_SECONDS = 900` are intentional per plan note (tunability is v1.2; if moved to Settings, env vars must read `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_SECONDS`).

### service.py (488 LOC total)

**Loader / authenticate / issue_tokens / wrapper (Task 2a):**

- `load_user_by_id(session, user_id) -> User | None` — registered via `register_user_loader()` in `create_app()` (Phase 4 D-24 slot fill).
- `authenticate(session, redis, email, password, *, ip=None) -> User`:
  1. `check_login_rate(...)` runs **before** any SQL or Argon2 work (D-18 gate).
  2. Single `SELECT users WHERE email = email.lower()`.
  3. `verify_password(plain, target_hash)` always runs — `target_hash` is the user's hash if found, else a lazily-generated sentinel Argon2 hash. Wall-clock latency identical regardless of user existence (AUTH-EP-02).
  4. Failure path: `bump_login_rate(...)` + `emit("login_failed", ...)` + raise `InvalidPassword`.
  5. `if user is None` after a sentinel-verify pseudo-success: bump + emit + raise (defensive — implausible collision path).
  6. Success: `emit("login_success", user_id, email, ip)` + return user.
- `issue_tokens(session, redis, user) -> (access, refresh, csrf)` — INSERT `RefreshToken` row, `commit()`, then write `auth:session:{user_id}:{family_id}` JSON + `SADD auth:user_sessions:{user_id} family_id` with matching TTLs (D-09, D-10).
- `_write_session_keys(...)` — single private helper shared by `issue_tokens` and `rotate_refresh` (idempotent SET + SADD + EXPIRE pipeline).
- `revoke_sessions_on_password_change(session, redis, user_id) -> int` — wrapper for AUTH-LO-03; delegates to `revoke_all_sessions` and re-emits `password_changed_revokes_sessions`. Locks the event name in source even though the admin password-change endpoint is deferred (Phase 8 audit-DB swap-in needs no rename).

**Rotation + revocation (Task 2b):**

- `rotate_refresh(session, redis, presented_token) -> (access, refresh, csrf)` — three explicit branches inside one `async with session.begin()` block holding `SELECT ... FOR UPDATE` on the old row (D-13):
  - **(A) ACTIVE** (`revoked_at IS NULL AND replaced_by_id IS NULL AND expires_at > now`): mint new pair, INSERT new row, set `replaced_by_id` + `replaced_at`, write `auth:rotate:{old_hash}` JSON `{access, refresh, csrf}` with `ex=refresh_reuse_window_seconds` and `nx=True`, refresh session keys.
  - **(B) REPLACED-WITHIN-WINDOW** (`replaced_by_id IS NOT NULL AND replaced_at > now - W`): GET `auth:rotate:{old_hash}`; on hit return the cached tuple (idempotent same-pair return). Cache miss → fall through to (C).
  - **(C) REUSE/REVOKED** (anything else): UPDATE all alive `refresh_tokens` for `(user_id, family_id)` to `revoked_at = now`, DEL session key, SREM family_id from user_sessions set, emit `family_reuse_detected` with `presented_token_hash_prefix=hash[:8]`, raise `InvalidAccessToken("family_reuse_detected")`.
- `revoke_session(session, redis, presented_token) -> None` — SELECT-by-hash + UPDATE-revoke for single family, both inside one `session.begin()` (autobegin guard per plan note). Idempotent on unknown token. Outside the tx: pipeline DEL `auth:session:{user_id}:{family_id}` + SREM `auth:user_sessions:{user_id}`. Emits `session_revoked`.
- `revoke_all_sessions(session, redis, user_id) -> int` — `SMEMBERS auth:user_sessions:{user_id}` (no SCAN per D-10 — bounded family count), pipeline DEL of all session keys + DEL the user_sessions set, then `UPDATE refresh_tokens SET revoked_at = now WHERE user_id = ? AND revoked_at IS NULL` inside `session.begin()`. Postgres is authoritative even if Redis SET is empty (post-flush degradation OK). Emits `session_revoked_all`. Returns family count.

## How to Verify

All gates run from `apps/backend/`:

```bash
uv run lint-imports                                                      # core ⊥ modules; 3 contracts kept
uv run mypy app/modules/auth/service.py app/modules/auth/rate_limit.py   # mypy strict, 0 errors
uv run ruff check app/modules/auth/service.py app/modules/auth/rate_limit.py  # all checks passed
uv run python -c "from app.modules.auth.service import load_user_by_id, authenticate, issue_tokens, rotate_refresh, revoke_session, revoke_all_sessions, revoke_sessions_on_password_change; from app.modules.auth.rate_limit import check_login_rate, bump_login_rate; print('ok')"
```

All four commands exit 0 / print `ok` on the final tree.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Implement `rate_limit` module | `7b33c3f` | `apps/backend/app/modules/auth/rate_limit.py` (new) |
| 2a | Auth service: loader + authenticate + issue_tokens + revoke_sessions_on_password_change | `4bbe64c` | `apps/backend/app/modules/auth/service.py` (rewrite from placeholder) |
| 2b | Auth service: rotate_refresh + revoke_session + revoke_all_sessions | `7e00b2c` | `apps/backend/app/modules/auth/service.py` (append) |

## Decisions Made

1. **Lazy sentinel hash.** Generating Argon2 at import time blocks the loop ~50ms and slows `pytest` collection across the suite. The `_get_sentinel_hash()` helper computes once on first `authenticate(...)` call; every subsequent call hits the cached `_SENTINEL_HASH`. The first request takes the hit; nothing else in the process does.

2. **`cast(Awaitable[...], ...)` over `redis.srem` and `redis.smembers`.** redis-py shares stubs across sync and async clients — both methods are typed `Union[Awaitable[T], T]`. mypy strict refuses to `await` such a union. Same-shape methods like `redis.delete` evidently have async-specific overloads upstream, but `srem` / `smembers` do not. The cast keeps the annotation honest at the boundary without masking real type errors.

3. **Forward reference `revoke_sessions_on_password_change -> revoke_all_sessions`.** Python resolves names at call time; the wrapper is defined in Task 2a but `revoke_all_sessions` only lands in Task 2b. The combined file (after both tasks) imports cleanly and mypy is satisfied. The plan calls this out explicitly in Task 2a acceptance criteria.

4. **Single-begin block in `revoke_session`.** SQLAlchemy 2.0 `AsyncSession` autobegins on the first statement. SELECT outside `session.begin()` and UPDATE inside it raises `InvalidRequestError("A transaction is already begun on this Session.")`. Both statements live in one block — plan note D-14 catches this and the implementation matches.

5. **Module-level rate-limit constants stay constants.** `_LIMIT = 5`, `_WINDOW_SECONDS = 900` are part of the AUTH-EP-03 contract per D-18; not promoted to `Settings` in this plan. If a future task tunes them, env vars must read `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_SECONDS` (per plan note).

## Deviations from Plan

None of substance.

Two micro-adjustments applied during execution:

1. **Imports added for typing casts.** Plan-prescribed code did not import `typing.cast` or `collections.abc.Awaitable`; mypy strict required casts on `redis.srem` (line 372) and `redis.smembers` (line 456). Added the imports and wrapped both calls. This is **Rule 1** (correctness) — without it, mypy strict fails the gate. Documented in *Decisions Made #2*.
2. **Ruff auto-fix for import block ordering** after appending Task 2b. `ruff check --fix` rewrote the import section (no semantic change). All other code is byte-for-byte from the plan's prescribed listings.

The plan's Task 2a verification command (which includes `uv run mypy` / `lint-imports` / `ruff`) is logically incomplete on Task 2a alone because the forward reference to `revoke_all_sessions` triggers `F821` and the unused `update` / `InvalidAccessToken` imports trigger `F401`. The plan acknowledges this in Task 2a's acceptance criteria ("the combined run after Task 2b is the gate") and the final state is clean. Task 2a was committed with the linter complaints intact (intentional planning artifact); Task 2b's commit is the linter-green gate.

## Authentication Gates

None encountered.

## Acceptance Criteria

| ID | Criterion | Status |
|----|-----------|--------|
| AUTH-05 / AUTH-06 | `rotate_refresh` uses SELECT FOR UPDATE + replaced_by_id chain + 5s window via `auth:rotate:{hash}` cache | met |
| AUTH-07 | `issue_tokens` writes `auth:session:{user_id}:{family_id}` JSON and `auth:user_sessions:{user_id}` SET with TTL | met |
| AUTH-EP-02 | `authenticate` runs sentinel-hash verify on user-not-found (timing equivalence) | met |
| AUTH-EP-03 | Rate-limit runs **before** `verify_password`; 5/15min per email | met |
| AUTH-EP-05 | 12-char password rule is owned by Plan 05-05 schemas (out of scope here, per plan) | scoped out |
| AUTH-LO-02 | `revoke_all_sessions` enumerates via SMEMBERS, deletes Redis keys, UPDATEs Postgres, emits `session_revoked_all` | met |
| AUTH-LO-03 | `revoke_sessions_on_password_change` wraps `revoke_all_sessions` and emits locked `password_changed_revokes_sessions` | met (call site only; admin endpoint deferred) |
| Tooling | mypy strict + ruff + lint-imports green | met |

## Threat Flags

None — all threat-register items in the plan's `<threat_model>` are addressed by the implementation as written. No new untracked surface introduced.

## Self-Check: PASSED

- `apps/backend/app/modules/auth/rate_limit.py` — FOUND
- `apps/backend/app/modules/auth/service.py` — FOUND
- Commit `7b33c3f` — FOUND
- Commit `4bbe64c` — FOUND
- Commit `7e00b2c` — FOUND
