---
phase: 06-rbac-wiring-parity-tests
plan: 03
subsystem: auth
tags: [fastapi, rbac, csrf, dependency-injection, auth-router, signature-deps]

# Dependency graph
requires:
  - phase: 06-rbac-wiring-parity-tests
    provides: require_authenticated() factory, verify_csrf signature dep, CsrfMismatch (Plans 06-01, 06-02)
  - phase: 05-user-schema-email-password-auth
    provides: /auth/login + /auth/refresh + /auth/logout + /auth/logout-all + /auth/me handlers, sportzal_csrf cookie minting on login, Phase 5 test_logout.py
provides:
  - "/auth/me, /auth/logout, /auth/logout-all migrated from Depends(get_current_user) → Depends(require_authenticated()) (D-02)"
  - "/auth/logout and /auth/logout-all enforce CSRF via signature dep AFTER auth dep (D-09 + D-22 RBAC-04 ordering preserved)"
  - "test_logout.py expanded from 3 → 6 tests (CSRF echo on existing tests + 3 ordering canaries)"
  - "Architectural canary: test_logout_unauthenticated_returns_401_even_without_csrf — fails the build if FastAPI ever flips signature dep ordering"
affects: [06-04 fixture router parametrized RBAC matrix, 06-05 TEST-07 introspection (depends on require_authenticated() being declared on these 3 routes), 08-clients (will adopt sub-router-level dependencies=[verify_csrf] pattern per D-05)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-route CSRF opt-in via signature Depends(verify_csrf), positioned AFTER the auth dep, on a mixed-exempt router (D-09)"
    - "Signature-dep ordering as the architectural enforcement of RBAC-04 (auth resolves before CSRF; canary test locks it)"
    - "Module-docstring contract documenting which routes carry which gates (Phase 6 wiring section)"

key-files:
  created: []
  modified:
    - apps/backend/app/modules/auth/router.py
    - apps/backend/tests/integration/auth/test_logout.py

key-decisions:
  - "verify_csrf is declared as a SIGNATURE Depends() AFTER require_authenticated() — NOT as a route-decorator dependencies=[...]. FastAPI resolves signature deps in declaration order, so unauth callers still hit 401 invalid_token before 403 csrf_mismatch can fire (RBAC-04 / D-22 preserved). Decorator-level placement was rejected because it would flip the order."
  - "/me carries require_authenticated() but no verify_csrf — GET would short-circuit verify_csrf anyway via the SAFE_METHODS gate, and omitting it makes the per-route table cleaner (D-09)."
  - "Existing Phase 5 test_logout_unauthenticated_returns_401 was PRESERVED unchanged as a second canary — proves RBAC-04 invariant survived the CSRF wiring without rewriting the assertion."

patterns-established:
  - "Mixed-exempt sub-router pattern: auth router has /login + /refresh CSRF-exempt and /logout + /logout-all CSRF-protected, all on the same APIRouter. Phase 8's clients router (uniform-protected) will use sub-router-level dependencies=[Depends(verify_csrf)] instead — D-05."
  - "Architectural canary tests: when an invariant depends on an external library's documented behavior (FastAPI signature dep ordering since 0.95+), encode it as a test that fails the build if the library ever changes the contract — explicit T-06-13 mitigation."

requirements-completed: [RBAC-02, RBAC-03, RBAC-04, CSRF-02]

# Metrics
duration: 5.6min
completed: 2026-05-02
---

# Phase 06 Plan 03: Auth Router RBAC Wiring + Per-Route CSRF Summary

**Migrated /me, /logout, /logout-all from Depends(get_current_user) → Depends(require_authenticated()), added verify_csrf as a signature dep AFTER the auth dep on /logout and /logout-all (preserving RBAC-04 401-before-403 ordering), and expanded test_logout.py from 3 → 6 tests with three explicit ordering canaries.**

## Performance

- **Duration:** 5.6 min
- **Started:** 2026-05-02T14:28:50Z
- **Completed:** 2026-05-02T14:34:26Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `/auth/me`, `/auth/logout`, `/auth/logout-all` now declare `Depends(require_authenticated())` — D-02 / D-03 invariant satisfied (no protected route in the auth router uses `get_current_user` directly).
- `/auth/logout` and `/auth/logout-all` enforce CSRF via `_csrf: Annotated[None, Depends(verify_csrf)]` placed as a signature parameter AFTER the auth dep — D-09 wiring with RBAC-04 ordering preserved.
- `/auth/login` and `/auth/refresh` remain CSRF-exempt and identity-source-as-body / identity-source-as-cookie respectively — D-09 mixed-exempt pattern.
- `test_logout.py` grew from 3 → 6 tests:
  - 2 existing tests updated to echo `sportzal_csrf` cookie as `X-CSRF-Token` header (D-24).
  - 3 new tests lock the gate semantics: auth-no-csrf → 403, auth-bad-csrf → 403, unauth-no-csrf → 401 (the RBAC-04 canary).
- All 16 integration tests in `tests/integration/auth/` pass; ruff + mypy strict + import-linter all green; route surface unchanged (`/login`, `/refresh`, `/logout`, `/logout-all`, `/me`).

## Final Route Gate Table

| Route                  | Method | Auth dep                     | CSRF dep              | Why                                                                                   |
|------------------------|--------|------------------------------|-----------------------|---------------------------------------------------------------------------------------|
| /api/v1/auth/login     | POST   | none                         | none                  | Bootstrap; identity in body. CSRF-exempt per D-09.                                    |
| /api/v1/auth/refresh   | POST   | none                         | none                  | Bootstrap; identity in `sz_refresh` cookie. CSRF-exempt per D-09.                     |
| /api/v1/auth/me        | GET    | `require_authenticated()`    | none                  | Read-only; verify_csrf would short-circuit via SAFE_METHODS anyway (omitted for clarity). |
| /api/v1/auth/logout    | POST   | `require_authenticated()`    | `verify_csrf` (after) | Mutating + authenticated. Auth-first ordering preserves RBAC-04 (D-22).               |
| /api/v1/auth/logout-all| POST   | `require_authenticated()`    | `verify_csrf` (after) | Same as /logout.                                                                      |

## Test Count Delta (`test_logout.py`)

3 tests → 6 tests:

| Test                                                                | Status   | Locks                                                                 |
|---------------------------------------------------------------------|----------|-----------------------------------------------------------------------|
| `test_logout_revokes_family_and_clears_cookies`                     | updated  | Auth+CSRF happy path (echoes `sportzal_csrf` as `X-CSRF-Token`)       |
| `test_logout_unauthenticated_returns_401`                           | preserved| RBAC-04 canary #1 (no cookies, no header → 401)                       |
| `test_logout_all_revokes_all_families`                              | updated  | Auth+CSRF happy path on /logout-all                                   |
| `test_logout_authenticated_without_csrf_header_returns_403`         | new      | D-09 wiring: signature verify_csrf after auth → 403 csrf_mismatch     |
| `test_logout_authenticated_with_wrong_csrf_header_returns_403`      | new      | Constant-time compare semantics on bad header                         |
| `test_logout_unauthenticated_returns_401_even_without_csrf`         | new      | RBAC-04 canary #2 (T-06-13 architectural enforcement of dep ordering) |

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate /me, /logout, /logout-all to require_authenticated + add verify_csrf to /logout and /logout-all** — `04e6ab7` (feat)
2. **Task 2: Update test_logout.py for CSRF + add 3 ordering canaries** — `594ac95` (test)

_The orchestrator owns the final docs commit (SUMMARY + STATE) per worktree-mode contract._

## Files Created/Modified

- `apps/backend/app/modules/auth/router.py` — Migrated 3 routes to `require_authenticated()`; added signature-level `verify_csrf` to /logout and /logout-all; updated module docstring to document Phase 6 wiring.
- `apps/backend/tests/integration/auth/test_logout.py` — Updated 2 existing POSTs to send `X-CSRF-Token` header echoing `sportzal_csrf` cookie; added 3 new tests covering CSRF-gate behavior and the RBAC-04 ordering canary; updated module docstring.

## Decisions Made

- **Signature-dep AFTER auth-dep, NOT decorator-level CSRF.** Plan called this out explicitly as the only correct placement; we adhered. Decorator-level `dependencies=[Depends(verify_csrf)]` would flip unauth /logout from 401 → 403 and break RBAC-04 (D-22). Signature placement keeps unauth callers on the 401 path.
- **/me has no verify_csrf dep declared.** GET method would short-circuit verify_csrf via the SAFE_METHODS gate anyway; omitting it makes the per-route table cleaner and matches D-09's intent ("declare a dep only where it does work").
- **Preserved Phase 5's `test_logout_unauthenticated_returns_401` test verbatim.** It remains the second RBAC-04 canary alongside the new `_even_without_csrf` test — both must pass for the build to ship.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed two stale `get_current_user` references from router.py docstrings.**
- **Found during:** Task 1 (post-edit grep audit)
- **Issue:** The plan's acceptance criterion `grep -n "get_current_user" apps/backend/app/modules/auth/router.py` expected 0 hits, but two literal `Depends(get_current_user)` mentions remained inside the module top-level docstring and the `/refresh` docstring (one was pre-existing from Phase 5; one I had introduced while writing the new Phase 6 docstring). Both were documentation-only references, but the acceptance criterion is strict.
- **Fix:** Rephrased both docstring lines to refer to the bare core-level identity loader / "the auth dep" instead of naming `get_current_user` literally. The architectural intent of the comments is preserved.
- **Files modified:** `apps/backend/app/modules/auth/router.py`
- **Verification:** Final grep audit returned 0 hits as required.
- **Committed in:** `04e6ab7` (Task 1 commit)

**2. [Rule 1 - Bug] Reduced literal `Depends(require_authenticated())` mentions in module docstring from 1 → 0 to satisfy the count-based acceptance criterion.**
- **Found during:** Task 1 (post-edit grep audit)
- **Issue:** Acceptance required `grep -nE "Depends\(require_authenticated\(\)\)"` to return EXACTLY 3 hits (one per /me, /logout, /logout-all). My initial Phase 6 module docstring contained one literal `Depends(require_authenticated())` reference, inflating the count to 4.
- **Fix:** Rephrased the docstring to say "declare the `require_authenticated()` factory dep" instead of including the literal `Depends(...)` token. Architectural narrative preserved.
- **Files modified:** `apps/backend/app/modules/auth/router.py`
- **Verification:** Final grep returned exactly 3 hits, all on actual route signatures.
- **Committed in:** `04e6ab7` (Task 1 commit)

**3. [Rule 1 - Bug] Wrapped overlong test_logout.py module docstring first line.**
- **Found during:** Task 2 (`uv run ruff check` after writing tests)
- **Issue:** The plan's specified docstring opener `"""Integration tests for /api/v1/auth/logout + /logout-all (AUTH-LO-01 / AUTH-LO-02 / Phase 6 CSRF-02)."""` is 103 columns, exceeding the project's `E501 100-char limit`.
- **Fix:** Split into two lines: title summary on line 1, then `Covers AUTH-LO-01 / AUTH-LO-02 (Phase 5) and Phase 6 CSRF-02 wiring.` on line 3 (after a blank line per PEP 257). All semantic content from the plan is preserved.
- **Files modified:** `apps/backend/tests/integration/auth/test_logout.py`
- **Verification:** `uv run ruff check` exits 0.
- **Committed in:** `594ac95` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs — all docstring-shape mismatches between the plan's exact-text directives and the project's grep-strict acceptance criteria + ruff line length).
**Impact on plan:** All three deviations were trivial documentation rewrites with semantic content preserved. No code-behavior changes. Acceptance criteria all pass.

## Issues Encountered

- **Local Redis port not exposed** — `docker compose up redis` doesn't publish 6379 to the host; integration tests require host-side Redis at localhost:6379. A wave-mate agent had spun up a temporary mapped Redis container; when it stopped its container mid-execution, my final pytest run errored on Redis connection. I started a separate `sportzal-test-redis-2` host-mapped Redis container to complete the verification. This is a pre-existing infrastructure issue unrelated to plan 06-03 — the project's `docker-compose.yml` redis service intentionally has no host port mapping for production-likeness; tests are expected to be run from inside the docker network or with a manually-published Redis. Did NOT fix the compose file (out of scope per plan boundary).
- **Flaky test_login_429_after_5_failures** — On one combined run of `tests/integration/auth/`, the rate-limit test failed once due to leftover Redis counter state from a prior test sharing the same email. Subsequent runs (after Redis flush) all green. Out of scope per scope boundary; logged here only.

## Threat Surface Scan

No new security-relevant surface introduced beyond what the plan's threat_model already enumerates (T-06-10 through T-06-14 all addressed by Task 1 + Task 2). No threat_flags raised.

## Self-Check: PENDING

[Self-check appended below after SUMMARY write.]

## Next Phase Readiness

- Plan 06-04 (fixture router + parametrized RBAC matrix) can now run — its assertions about `require_authenticated()` and `require_permission()` declarations are independent of this plan's auth-router edits.
- Plan 06-05 (TEST-07 introspection) now has its discriminator targets in place: `/auth/me`, `/auth/logout`, `/auth/logout-all` carry `require_authenticated()` (the closure name is `_checker`, qualname starts with `require_authenticated.`); `/auth/login` and `/auth/refresh` are on the EXCLUDED_PATHS list per D-04. TEST-07 will pass when wired up in Plan 06-05.
- Phase 8's clients router (uniform-protected) will adopt sub-router-level `dependencies=[Depends(verify_csrf)]` per D-05 — that pattern intentionally differs from this plan's per-route CSRF on a mixed-exempt router, and the divergence is documented in the new module docstring.

---
*Phase: 06-rbac-wiring-parity-tests*
*Completed: 2026-05-02*
