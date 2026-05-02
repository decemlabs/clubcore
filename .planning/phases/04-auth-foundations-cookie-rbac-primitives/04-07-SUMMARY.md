---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: 07
subsystem: auth
tags: [jwt, argon2, pyjwt, argon2-cffi, cookies, csrf, security, python]

# Dependency graph
requires:
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: "Plan 04-01: Settings with access_token_ttl_seconds/refresh_token_ttl_seconds/jwt_clock_leeway_seconds/cookie_secure"
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: "Plan 04-04: Role StrEnum, InvalidAccessToken, InvalidPassword exceptions"

provides:
  - "AccessTokenClaims dataclass (frozen, slots) with sub/role/typ/iat/exp"
  - "encode_access_token(user_id, role, *, now) -> str — HS256 JWT, 900s TTL"
  - "decode_access_token(token) -> AccessTokenClaims — verifies signature, required claims, typ, role"
  - "hash_password(plain) -> str — Argon2id via asyncio.to_thread"
  - "verify_password(plain, hash) -> bool — raises InvalidPassword on mismatch"
  - "password_needs_rehash(hash) -> bool — for Phase 5 transparent rehash"
  - "generate_refresh_token() -> (raw_43char, sha256_64char)"
  - "generate_otp_code() -> (6_digit_code, sha256_64char)"
  - "generate_deep_link_token() -> 43char URL-safe"
  - "generate_csrf_token() -> 64char hex"
  - "issue_session_cookies(response, *, access_token, refresh_token, csrf_token, secure) -> None"

affects:
  - "04-08-dependencies: imports decode_access_token + AccessTokenClaims"
  - "04-09-tests: test_security.py validates all 11 exports"
  - "phase-05: uses encode/decode/hash/verify/generate_refresh_token/issue_session_cookies in login service"
  - "phase-06: CSRF verifier dependency reads sportzal_csrf cookie"
  - "phase-07: uses generate_otp_code, generate_deep_link_token, issue_session_cookies"

# Tech tracking
tech-stack:
  added: ["pyjwt>=2.12.1", "argon2-cffi>=25.1.0"]
  patterns:
    - "get_settings() called inside helpers (never at module-level) — consistent with database.py:24 lru_cache pattern"
    - "asyncio.to_thread wrapping for CPU-bound Argon2 operations"
    - "Single cookie-emitter function (issue_session_cookies) to prevent drift across emission sites"
    - "Generators return (raw, sha256_hex) tuples — callers store only hash, never raw"
    - "ExpiredSignatureError caught before InvalidTokenError (parent-class ordering in except chain)"

key-files:
  created: []
  modified:
    - "apps/backend/app/core/security.py"

key-decisions:
  - "algorithms=[HS256] pinned explicitly in jwt.decode — algorithm-confusion mitigation (T-04-25)"
  - "Module-level _ph = PasswordHasher() with no constructor args — library OWASP defaults (D-27)"
  - "issue_session_cookies as single function, not three setters — drift prevention (D-25)"
  - "Generators return (raw, sha256_hex) never storing raw — callers own persistence discipline"
  - "datetime.UTC alias used (ruff UP017 — Python 3.11+ modern style)"

patterns-established:
  - "JWT claims: {sub, role, typ, iat, exp} — additive fields (jti/iss/aud) deferred (D-02)"
  - "Cookie matrix: sz_access (Path=/, httpOnly) + sz_refresh (Path=/api/v1/auth, httpOnly) + sportzal_csrf (Path=/, non-httpOnly)"
  - "All samesite=lax, secure=arg (env-driven), max_age from settings"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, CSRF-01]

# Metrics
duration: 12min
completed: 2026-05-02
---

# Phase 4 Plan 07: Security Primitives Summary

**HS256 JWT encode/decode with Argon2id password hashing + CSPRNG token generators + triple-cookie emitter locked to SameSite=Lax/httpOnly attributes**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-02T00:00:00Z
- **Completed:** 2026-05-02T00:12:00Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- Replaced the 6-line placeholder `app/core/security.py` with 255 lines of production-ready cryptographic primitives covering AUTH-01, AUTH-02, AUTH-03, AUTH-04, and CSRF-01
- Implemented HS256 JWT encode/decode with algorithm pinned, 30s clock leeway, required-claims enforcement, and four distinct failure codes (token_expired / invalid_token / wrong_token_type / unknown_role)
- Argon2id hash/verify/needs_rehash wrapped in `asyncio.to_thread` to avoid blocking the event loop; all using library OWASP defaults
- Four CSPRNG token generators returning (raw, sha256_hex) tuples — callers store only hashes
- Single `issue_session_cookies` function setting all three cookies with locked attributes, preventing attribute drift across Phase 5/7 emission sites

## Named Exports

| Export | Signature | Notes |
|--------|-----------|-------|
| `AccessTokenClaims` | `@dataclass(frozen=True, slots=True)` | sub, role, typ, iat, exp |
| `encode_access_token` | `(user_id: UUID, role: Role, *, now=None) -> str` | HS256, TTL from settings |
| `decode_access_token` | `(token: str) -> AccessTokenClaims` | algorithms=["HS256"] pinned |
| `hash_password` | `async (plain: str) -> str` | Argon2id, asyncio.to_thread |
| `verify_password` | `async (plain: str, encoded_hash: str) -> bool` | raises InvalidPassword |
| `password_needs_rehash` | `async (encoded_hash: str) -> bool` | for Phase 5 rehash flow |
| `generate_refresh_token` | `() -> tuple[str, str]` | (43-char, 64-char hex) |
| `generate_otp_code` | `() -> tuple[str, str]` | (6-digit, 64-char hex) |
| `generate_deep_link_token` | `() -> str` | 43-char URL-safe |
| `generate_csrf_token` | `() -> str` | 64-char hex |
| `issue_session_cookies` | `(response, *, access_token, refresh_token, csrf_token, secure) -> None` | 3 cookies |

## Cookie Attribute Matrix

| Cookie | Path | Max-Age | httpOnly | SameSite | Secure |
|--------|------|---------|----------|----------|--------|
| `sz_access` | `/` | `access_token_ttl_seconds` (900) | True | lax | arg |
| `sz_refresh` | `/api/v1/auth` | `refresh_token_ttl_seconds` (2592000) | True | lax | arg |
| `sportzal_csrf` | `/` | `refresh_token_ttl_seconds` | False | lax | arg |

## Task Commits

1. **Task 1: FILL app/core/security.py with JWT + Argon2 + token gens + cookie helper** - `a893891` (feat)

**Plan metadata:** committed with SUMMARY

## Files Created/Modified

- `apps/backend/app/core/security.py` — Replaced 6-line placeholder with 255-line production implementation (11 named exports, 4 sections)

## Decisions Made

- Used `algorithms=["HS256"]` pinned in `jwt.decode` — algorithm-confusion mitigation (T-04-25); acceptance criteria asserts this string is present
- `_ph = PasswordHasher()` with no constructor args — library defaults meet OWASP 2026 (D-27); `check_needs_rehash` handles future param bumps transparently
- Single `issue_session_cookies` function (not three separate setters) — central control prevents SameSite/Path/Max-Age drift across Phase 5 login, Phase 5 refresh, Phase 7 OTP-verify
- `get_settings()` called inside each helper, never at module level — required for `@lru_cache` correctness under tests that monkey-patch env vars (matches database.py:24 pattern)
- `datetime.UTC` alias instead of `timezone.utc` — ruff UP017 modern Python 3.11+ style; auto-fixed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff I001 (import sort) + UP017 (datetime.UTC alias)**
- **Found during:** Task 1 (verification step)
- **Issue:** Import block unsorted (stdlib blank line before 3rd-party block trimmed) and `timezone.utc` used instead of `datetime.UTC` alias
- **Fix:** `uv run ruff check --fix app/core/security.py` auto-fixed both; 4 total fixes applied
- **Files modified:** apps/backend/app/core/security.py
- **Verification:** `ruff check` exits 0, `mypy` still exits 0 after fix
- **Committed in:** a893891 (Task 1 commit — fixes applied before commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - style/lint)
**Impact on plan:** Trivial ruff auto-fixes; no logic changes. All checks green before commit.

## Issues Encountered

None — plan executed cleanly. The ruff auto-fixes (import sort + datetime alias) were applied before committing so the commit is already clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-08 (`dependencies.py`) can now import `decode_access_token` and `AccessTokenClaims` as planned
- Plan 04-09 (`test_security.py`) has all 11 exports available for unit testing
- Phase 5 login service can import all five key helpers: `encode_access_token`, `hash_password`, `verify_password`, `generate_refresh_token`, `issue_session_cookies`, `generate_csrf_token`
- No blockers

---
*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Completed: 2026-05-02*
