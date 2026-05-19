---
phase: 44-invitation-password-reset-flow
plan: 08
subsystem: auth
tags:
  - integration-test
  - invitation-accept
  - insert-only-invariant
  - reset-04
  - reset-05
  - pitfall-4
requires:
  - 44-04 (accept_invitation service body — atomic-consume + UPDATE-only)
  - 44-05 (POST /api/v1/users/invitations/accept anonymous endpoint)
  - 43-08 (Phase 43 D-43-13 4-branch idempotent create_user)
  - 43-11 (RecordingEmailDispatcher pattern reference)
  - 43-19 (POST /invitations/{id}/revoke — RESET-05 cross-coverage)
provides:
  - apps/backend/tests/integration/auth/test_invitation_accept.py (9 tests)
  - apps/backend/tests/integration/auth/test_invitation_accept_insert_only.py (1 test)
  - RESET-04 lifecycle coverage at integration level
  - RESET-05 cross-coverage at the auth/users module seam
  - Pitfall 4 INSERT-only invariant grep-discoverable security claim
affects:
  - apps/backend/tests/integration/auth/ (2 new files)
tech-stack:
  added: []
  patterns:
    - SAVEPOINT-rolled per-test session via project ``db_session`` fixture (Phase 5 D-22).
    - Per-file local fixture machinery (RecordingEmailDispatcher + owner-authed AsyncClient + ``_app_overrides``) parallel to ``tests/integration/users/conftest.py`` to keep the auth-package suite self-contained.
    - ``_extract_raw_token`` helper — splits the captured invitation URL on ``#token=`` to pull the raw URL-safe token from the recorder's envelope (mirrors ``test_users_invitation_flow.py``).
    - httpx Set-Cookie assertion via ``r.cookies`` jar membership (NOT raw ``set-cookie`` header) because httpx's ``response.headers["set-cookie"]`` only exposes the last server header when multiple Set-Cookie lines are sent.
key-files:
  created:
    - apps/backend/tests/integration/auth/test_invitation_accept.py
    - apps/backend/tests/integration/auth/test_invitation_accept_insert_only.py
    - .planning/phases/44-invitation-password-reset-flow/44-08-SUMMARY.md
  modified: []
decisions:
  - "Local fixtures (not shared via conftest) — both new files redefine the small fixture set (RecordingEmailDispatcher + owner login + _app_overrides) rather than importing from tests/integration/users/conftest.py. Rationale: pytest's package-local conftest model means importing the users conftest into an auth test would create implicit cross-package coupling; keeping fixtures local makes the auth suite self-explanatory and the INSERT-only carrier file independently greppable as a security claim."
  - "Accept happy-path uses an 18-char password ('newpass-1234-strong') instead of the 11-char minimum the service enforces (D-44-17: >=8 chars). Reason: the test exercises end-to-end Argon2 verify by calling /auth/login with the freshly-set password, and LoginRequest.password has min_length=12 — an 11-char password would 422 at the login schema and never reach the Argon2 verify. Documented inline."
  - "Race-with-soft-delete (Test 5) asserts consumed_at IS NOT NULL on the token row even though the service raises 409 — verified against the 44-04 implementation order: atomic-consume fires BEFORE the user-row UPDATE per `password_reset_service.accept_invitation` body. If a future plan re-orders these calls, the assertion must change in lockstep."
  - "RESET-05 cross-coverage (Tests 6+7) landed inline in test_invitation_accept.py instead of as cross-reference comments. Phase 43 test_users_invitation_flow.py covers the symmetrical 'double-revoke' path (consumed-by-revoke + revoke-again) but does NOT cover 'consumed-by-accept + revoke' nor 'revoked + accept'. Inline coverage closes the RESET-05 acceptance criteria explicitly in the same file as RESET-04."
  - "Cookie name verification anchored on app/core/security.py:issue_session_cookies (lines 222–252): sz_access (Path=/), sz_refresh (Path=/api/v1/auth/), sportzal_csrf (Path=/, NOT HttpOnly). Test 1 asserts membership in r.cookies for all three names verbatim."
metrics:
  duration_minutes: 18
  completed_date: 2026-05-20
  tasks_completed: 2
  files_created: 3
  files_modified: 0
  lines_changed: ~1126
  tests_added: 10
  commits: 2
---

# Phase 44 Plan 08: Invitation-Accept Integration Tests Summary

Two new integration test files cover the Phase 44 RESET-04 invitation-accept lifecycle at the HTTP boundary AND the Pitfall 4 INSERT-only invariant at the accept point. 10 tests total (9 lifecycle + 1 INSERT-only), all passing against real Postgres via the project's SAVEPOINT-rolled `db_session` fixture. The INSERT-only file is intentionally a single-test, self-contained, grep-discoverable security-claim carrier for Phase 46 verification — the file's module docstring and test name both reference "Pitfall 4" and "INSERT-only" explicitly. The full 97-test auth+users integration suite (54 prior auth + 33 prior users + 10 new) passes green.

## Test Catalogue

### `tests/integration/auth/test_invitation_accept.py` (9 tests)

| # | Test name | What it verifies |
| - | --------- | ---------------- |
| 1 | `test_accept_happy_path_atomic_consume_password_set_email_verified_cookies_issued` | Full RESET-04 happy path: password_hash set (Argon2), status→active, email_verified→true, consumed_at non-NULL, LoginResponse envelope, Set-Cookie {sz_access, sz_refresh, sportzal_csrf}, exactly one `user_invitation_accepted` audit row with `accepted_user_id` + `invitation_token_id` pinned, end-to-end /auth/login with the new password succeeds. |
| 2 | `test_accept_replay_returns_410_with_identical_body` | Replay of a consumed token returns 410 `invalid_or_expired_token` (D-44-15 anti-oracle); no second audit row emitted. |
| 3 | `test_accept_expired_invitation_returns_410` | Token row with `expires_at < now()` collapses into the 410 bucket; consumed_at remains NULL (predicate filtered it out, no atomic-consume fired). |
| 4 | `test_accept_full_name_branch_overwrite` | D-44-23 COALESCE: non-empty `fullName` overwrites owner's value (self-healing typo correction). |
| 5 | `test_accept_full_name_branch_preserve_on_empty` | D-44-23 COALESCE: empty-string `fullName` preserves owner's original. |
| 6 | `test_accept_full_name_branch_preserve_on_omitted` | D-44-23 COALESCE: omitted `fullName` (None branch) preserves owner's original. |
| 7 | `test_accept_race_with_soft_delete_returns_409` | D-44-20 race: soft-delete between token-issue and accept ⇒ 409 `invitation_already_accepted`. consumed_at IS NOT NULL (atomic-consume fired BEFORE the user-row UPDATE per 44-04 body order). No `user_invitation_accepted` audit row. |
| 8 | `test_accept_with_revoked_token_returns_410` | RESET-05 cross-coverage — revoking via Phase 43 D-43-19 sets consumed_at; subsequent accept folds into the 410 anti-oracle bucket. |
| 9 | `test_revoke_already_accepted_invitation_returns_409` | RESET-05 cross-coverage — revoke after accept returns 409 `invitation_already_accepted` (mirror of the Phase 43 double-revoke 409 path). |

### `tests/integration/auth/test_invitation_accept_insert_only.py` (1 test)

| # | Test name | What it verifies |
| - | --------- | ---------------- |
| 1 | `test_soft_deleted_email_re_invite_accept_lands_as_new_user_id` | Pitfall 4 at the accept boundary: create A → soft-delete A → re-invite same email → INSERT new B with distinct id (partial-UNIQUE allows) → accept B's token → `accepted_user_id == B.id != A.id`; row A untouched (deleted_at stays non-NULL, password_hash unchanged, status unchanged); audit row pins to B.id. |

## Cookie Matrix Verified (D-44-21)

Pinned against `app/core/security.py:issue_session_cookies` (lines 222–252 of HEAD as of plan 44-05 land):

| Cookie name | Path | HttpOnly | Notes |
| ----------- | ---- | -------- | ----- |
| `sz_access` | `/` | Yes | Covers all API paths. |
| `sz_refresh` | `/api/v1/auth` | Yes | Narrow path; only sent to auth-module endpoints. |
| `sportzal_csrf` | `/` | No | Read by frontend JS for the X-CSRF-Token header. |

Test 1 asserts all three names appear in `r.cookies` after a successful accept. The 3 names match the verbatim VERBATIM mirror in `users/router.py:accept_invitation_endpoint` (plan 44-05 § "Canonical /auth/login Mirror") which calls `issue_session_cookies(response, access_token=, refresh_token=, csrf_token=, secure=settings.cookie_secure)`.

## Race-with-Soft-Delete: Consumed-At Order (44-04 implementation pin)

`password_reset_service.accept_invitation` (apps/backend/app/modules/auth/password_reset_service.py:472–513) sequences the body as:

1. Weak-password gate (returns 422 before any DB write).
2. `_atomic_consume_token` — `UPDATE password_reset_tokens SET consumed_at = NOW() WHERE … RETURNING …`. **This fires FIRST** and sets `consumed_at` to non-NULL.
3. `await hash_password(new_password)` — Argon2id (CPU-bound, no DB writes).
4. `UPDATE users SET … WHERE id = :user_id AND status = 'pending_invitation' AND is_active IS TRUE AND deleted_at IS NULL RETURNING …`. **If zero rows match here, raise 409.**

Therefore in Test 5 (race-with-soft-delete) the test asserts:

- `consumed_at IS NOT NULL` on the token row (step 2 fired even though step 4 failed).
- The 409 response is raised from step 4.
- No `user_invitation_accepted` audit row exists for the target user (the audit-emit step 5 never ran).

If a future plan re-orders steps 2 and 4 (e.g., to guard the token-consume behind the user-row UPDATE success), this assertion's expectation MUST change to `consumed_at IS NULL`. The test's inline comment documents this dependency explicitly.

## Drift from Phase 43 Invitation-Flow Test Patterns

Minimal — the new tests mirror the Phase 43 `test_users_invitation_flow.py` shape (RecordingEmailDispatcher + raw-token extraction from `#token=` fragment + audit-row select-by-action assertion). Differences:

1. **Fixture scope** — Phase 43 uses `tests/integration/users/conftest.py` package-local fixtures (`authed_client_owner`, `sandbox_email_client`, `db_session`). The new files define equivalents LOCAL to each file (named `owner_client`, `sandbox_email_client`, `anon_client`, `_seeded_owner`, `_app_overrides`) so the auth-package suite does not cross-import the users conftest. This makes the INSERT-only carrier file especially fully self-contained as a grep target.
2. **Owner email** — fixtures use distinct OWNER_EMAIL constants (`accept-flow-owner@example.com`, `insert-only-owner@example.com`) to avoid the rare cross-test collision that could happen if both files were ever loaded in the same module via shared `seeded_owner`. SAVEPOINT isolation guarantees zero overlap in practice; the distinct emails are belt-and-braces.
3. **httpx Set-Cookie assertion** — uses `r.cookies` jar membership rather than parsing `r.headers["set-cookie"]`. Reason: httpx's Headers proxy collapses multi-value Set-Cookie headers into a single concatenated string and the jar is the only reliable parse boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] /auth/login min_length=12 mismatch with /invitations/accept >=8 service gate**

- **Found during:** Task 1 (Test 1 — end-to-end /auth/login with the freshly-set password).
- **Issue:** The plan's example password (`"newpass1234"`, 11 chars) passes the service-layer weak-password gate (D-44-17 requires >=8 chars) but fails `LoginRequest.password = Field(min_length=12)` on the subsequent /auth/login call, returning 422 instead of 200. The end-to-end Argon2 verify assertion would never be exercised.
- **Fix:** changed the test's password literal to `"newpass-1234-strong"` (18 chars), which passes both gates. Added an inline comment documenting the dual-floor reason.
- **Files modified:** `apps/backend/tests/integration/auth/test_invitation_accept.py` (Test 1 only).
- **Commit:** `fcf17ae` (Task 1 atomic commit).

### Deferred / Out-of-Scope

None.

## Verification Results

```bash
# Both new files pass:
cd apps/backend && env $(grep -v '^#' .env.example | xargs) uv run pytest \
    tests/integration/auth/test_invitation_accept.py \
    tests/integration/auth/test_invitation_accept_insert_only.py -q
# → 10 passed in 1.99s

# Full auth + users regression — no breakage from the new fixture wiring:
cd apps/backend && env $(grep -v '^#' .env.example | xargs) uv run pytest \
    tests/integration/auth/ tests/integration/users/ -q
# → 97 passed in 19.32s  (54 prior auth + 33 prior users + 10 new)

# Lint + mypy strict:
cd apps/backend && uv run ruff check \
    tests/integration/auth/test_invitation_accept.py \
    tests/integration/auth/test_invitation_accept_insert_only.py
# → All checks passed!

cd apps/backend && uv run mypy --strict \
    tests/integration/auth/test_invitation_accept.py \
    tests/integration/auth/test_invitation_accept_insert_only.py
# → Success: no issues found in 2 source files

# Acceptance criteria greps:
grep -c "^async def test_" apps/backend/tests/integration/auth/test_invitation_accept.py
# → 9
grep -c "^async def test_" apps/backend/tests/integration/auth/test_invitation_accept_insert_only.py
# → 1
grep -c "Pitfall 4\|INSERT-only" apps/backend/tests/integration/auth/test_invitation_accept_insert_only.py
# → 21
```

## Threat Flags

None — both files are tests; no new threat surface. The tests EXERCISE existing threat mitigations (anti-oracle 410 bucket collapse for replay/expired/revoked; INSERT-only invariant against soft-deleted-user resurrection) and pin them with grep-discoverable assertions for Phase 46 verification.

## Self-Check: PASSED

- FOUND: apps/backend/tests/integration/auth/test_invitation_accept.py (752 lines, 9 tests)
- FOUND: apps/backend/tests/integration/auth/test_invitation_accept_insert_only.py (374 lines, 1 test)
- FOUND: commit fcf17ae (Task 1 — test_invitation_accept.py)
- FOUND: commit 3108bf2 (Task 2 — test_invitation_accept_insert_only.py)
- VERIFIED: 10/10 new tests pass
- VERIFIED: 97/97 auth+users regression suite passes
- VERIFIED: ruff + mypy --strict both green on both new files
- VERIFIED: all acceptance criteria greps green (Pitfall 4 ×21, distinct ids, sz_access/refresh, full_name, email_verified, user_invitation_accepted, invitation_already_accepted)
