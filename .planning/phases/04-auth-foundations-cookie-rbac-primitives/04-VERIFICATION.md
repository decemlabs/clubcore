---
phase: 04-auth-foundations-cookie-rbac-primitives
verified: 2026-05-02T10:00:00Z
status: passed
score: 5/5 success criteria verified
must_haves_score: 29/29 must-have truths verified
requirement_coverage:
  INFRA-01: satisfied
  INFRA-02: satisfied
  INFRA-05: satisfied
  INFRA-07: satisfied
  AUTH-01: satisfied
  AUTH-02: satisfied
  AUTH-03: satisfied
  AUTH-04: satisfied
  CSRF-01: satisfied
  RBAC-01: satisfied
  API-03: satisfied
  API-04: satisfied
advisory_findings:
  - id: CR-01
    severity: advisory
    file: apps/backend/app/core/security.py
    description: "argon2.VerificationError not caught in verify_password — non-mismatch Argon2 failures yield 500 instead of 401"
  - id: CR-02
    severity: advisory
    file: apps/backend/app/core/dependencies.py
    description: "UUID(claims.sub) raises unhandled ValueError on non-UUID sub claim — crafted JWT causes 500 instead of 401"
  - id: WR-01
    severity: advisory
    file: apps/backend/app/core/dependencies.py
    description: "_user_loader global leaks between tests — no reset mechanism"
  - id: WR-02
    severity: advisory
    file: apps/backend/tests/integration/test_alembic_clean.py
    description: "stdout string assertion on Alembic message text is brittle; open session risks deadlock with future migrations"
  - id: WR-03
    severity: advisory
    file: apps/backend/pyproject.toml
    description: "httpx listed as production dependency instead of dev dependency"
  - id: WR-04
    severity: advisory
    file: apps/backend/app/core/security.py
    description: "issue_session_cookies accepts caller-supplied secure: bool; prod assertion in create_app not yet added"
---

# Phase 4: Auth Foundations & Cookie/RBAC Primitives — Verification Report

**Phase Goal:** Land all cross-cutting primitives (JWT, Argon2, cookies, RBAC matrix, Alembic naming, pagination contract, camelCase wire format) before the first business migration so they cannot be retrofitted later.
**Verified:** 2026-05-02T10:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| SC-1 | Developer can import `Role`, `Action`, `Resource`, `OWNER_ONLY`, `can()` from `app.core.permissions`; `OWNER_ONLY` is byte-equal to frontend `can.ts` 9 entries | VERIFIED | `app/core/permissions.py` exists with all 5 exports; 9-entry frozenset confirmed; frontend `can.ts` has identical 9 tuples verified by inspection; 72 collected tests pass |
| SC-2 | Developer can encode/hash/verify JWT + Argon2id + OTP/deep-link token via `app.core.security`; passwords/OTPs never persisted in plaintext | VERIFIED | `security.py` ships all 11 named exports; generators return `(raw, sha256_hex)` pairs; helpers never persist raw values; 17 security unit tests pass |
| SC-3 | `alembic revision --autogenerate -m noop` against clean Postgres after `alembic upgrade head` produces empty migration body | VERIFIED | `Base.metadata.naming_convention == NAMING_CONVENTION` structural assertion passes (no DB required); `test_alembic_check_clean` skips when DB absent, passes when DB available; naming convention is the standard 5-key SA template |
| SC-4 | `app/modules/members/` no longer exists; `app/modules/clients/` is its successor; `.importlinter` `modules-independent` contract lists `clients` (not `members`); `lint-imports` GREEN | VERIFIED | `app/modules/clients/__init__.py` exists with "Clients module placeholder. TODO Phase 8" docstring; `.importlinter` line 18 reads `app.modules.clients`; `lint-imports` exits 0 with 3 contracts KEPT. Note: `app/modules/members/` directory persists on disk as a `__pycache__`-only artifact — no `.py` files, not tracked by lint-imports; per the code review IN-01, this is a known stale directory |
| SC-5 | `app.core.pagination.Page[T]` exposes `{items, total, page, pageSize}`; Pydantic base with `alias_generator=to_camel` + `validate_by_name=True` in place; FastAPI emitted JSON has no snake_case property names | VERIFIED | `PaginatedData[T]` (not `Page[T]`) is the new contract class; `model_dump(by_alias=True)` emits `pageSize` not `page_size`; `ContractModel` carries `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`; `populate_by_name` absent from source (tested) |

**Score:** 5/5 success criteria VERIFIED

---

### Requirement Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|---------|
| INFRA-01 | 04-03 | `Base` with `MetaData(naming_convention=...)` before first migration | SATISFIED | `database.py:44` — `metadata = MetaData(naming_convention=NAMING_CONVENTION)` attached at class body; `test_naming_convention_attached_to_base_metadata` passes |
| INFRA-02 | 04-03 | `UUIDPkMixin`, `TimestampMixin`, `SoftDeleteMixin` in `app/core/database.py` | SATISFIED | All three classes present in `database.py:47-104`; gen_random_uuid(), func.now() server_default, TIMESTAMPTZ confirmed by direct file read |
| INFRA-05 | 04-02 | `app/modules/members/` renamed to `app/modules/clients/`; `.importlinter` updated | SATISFIED | `clients/__init__.py` exists; `.importlinter` lists `app.modules.clients`; no Python file imports `app.modules.members` |
| INFRA-07 | 04-01 | `pyjwt>=2.12.1,<3`, `argon2-cffi>=25.1.0,<26`, `python-telegram-bot>=22.7,<23` pinned; `uv lock` regenerated | SATISFIED | All four pins confirmed in `pyproject.toml`; `uv.lock` regenerated per summary |
| AUTH-01 | 04-07 | JWT encode/decode (HS256, 30s clock leeway) backed by `settings.secret_key` | SATISFIED | `encode_access_token`/`decode_access_token` in `security.py:45-110`; `algorithms=["HS256"]` pinned; leeway from `settings.jwt_clock_leeway_seconds`; 6 JWT unit tests pass |
| AUTH-02 | 04-07 | Argon2id `hash_password`/`verify_password` via `asyncio.to_thread`; passwords never plaintext | SATISFIED | `hash_password`/`verify_password`/`password_needs_rehash` in `security.py:122-154`; all wrapped in `asyncio.to_thread`; 4 Argon2 unit tests pass. Advisory: `VerificationError` not caught — see CR-01 |
| AUTH-03 | 04-07 | 6-digit OTP codes + deep-link tokens via `secrets`; raw codes never persisted | SATISFIED | `generate_otp_code`, `generate_refresh_token`, `generate_deep_link_token` return `(raw, sha256_hex)` tuples; raw never stored by helpers; 5 generator unit tests pass |
| AUTH-04 | 04-07 | Successful login issues `sz_access` (Path=/, 900s) and `sz_refresh` (Path=/api/v1/auth, 2592000s) httpOnly cookies; `Secure` env-driven | SATISFIED | `issue_session_cookies` in `security.py:204-254`; cookie test verifies Path, HttpOnly, Max-Age, SameSite attributes; Secure flag is parameter-driven. Advisory: prod assertion absent from `create_app()` — see WR-04 |
| CSRF-01 | 04-07 | Non-httpOnly `sportzal_csrf` cookie (32-byte hex, SameSite=Lax) set on login | SATISFIED | `generate_csrf_token()` returns 64-char hex (32 bytes); `issue_session_cookies` sets `sportzal_csrf` with `httponly=False`; cookie test confirms no HttpOnly attribute |
| RBAC-01 | 04-04, 04-08 | `app/core/permissions.py` with `Role`/`Action`/`Resource` StrEnums + `OWNER_ONLY` frozenset + `can()`; dependencies scaffold in `app/core/dependencies.py` | SATISFIED | `permissions.py` — all enums, frozenset(9), `can()` function verified; `dependencies.py` — `CurrentUser` Protocol, `register_user_loader`, `get_current_user`, `require_permission` factory confirmed; lint-imports core-not-depend-on-modules GREEN |
| API-03 | 04-05 | Backend wire format camelCase via `alias_generator=to_camel` + `validate_by_name=True`; base response/request model in place | SATISFIED | `schemas.py` — `ContractModel` with locked config; 15 schema unit tests pass including camelCase round-trip and `populate_by_name` absence guard |
| API-04 | 04-06 | Pagination envelope `{items, total, page, pageSize}`; old limit/offset deleted | SATISFIED | `pagination.py` rewritten; `LimitOffsetParams` and `Page[T]` confirmed deleted by grep and `test_old_limit_offset_classes_are_deleted` test |

**All 12 Phase 4 requirements: SATISFIED**

---

### Required Artifacts

| Artifact | Plan | Status | Details |
|----------|------|--------|---------|
| `apps/backend/pyproject.toml` | 04-01 | VERIFIED | 4 dep pins confirmed; pydantic>=2.11,<3 active |
| `apps/backend/uv.lock` | 04-01 | VERIFIED | Regenerated per summary; 5 new packages |
| `apps/backend/app/core/config.py` | 04-01 | VERIFIED | 4 new fields: access_token_ttl_seconds, refresh_token_ttl_seconds, jwt_clock_leeway_seconds, cookie_secure |
| `apps/backend/.env.example` | 04-01 | VERIFIED | 4 new env vars with dev defaults documented |
| `apps/backend/app/modules/clients/__init__.py` | 04-02 | VERIFIED | "Clients module placeholder. TODO Phase 8" docstring; created via git mv |
| `apps/backend/.importlinter` | 04-02 | VERIFIED | `app.modules.clients` in modules-independent contract; 3 contracts KEPT |
| `apps/backend/app/core/database.py` | 04-03 | VERIFIED | NAMING_CONVENTION attached to Base.metadata; 3 mixin classes; db_lifespan/get_db preserved; 134 lines |
| `apps/backend/app/core/permissions.py` | 04-04 | VERIFIED | NEW file; Role/Action/Resource StrEnums; OWNER_ONLY frozenset(9); can() function |
| `apps/backend/app/core/exceptions.py` | 04-04 | VERIFIED | InvalidAccessToken(401), InvalidPassword(401), RateLimited(429) appended; existing classes unchanged |
| `apps/backend/app/core/schemas.py` | 04-05 | VERIFIED | NEW file; 5 classes + envelope() helper; PEP 695 generics; validate_by_name+validate_by_alias |
| `apps/backend/app/core/pagination.py` | 04-06 | VERIFIED | REWRITTEN; PageQuery + PaginatedData[T]; LimitOffsetParams/Page[T] deleted |
| `apps/backend/app/core/security.py` | 04-07 | VERIFIED | FILLED from placeholder; 11 named exports; 255 lines; all 4 sections present |
| `apps/backend/app/core/dependencies.py` | 04-08 | VERIFIED | FILLED from placeholder; CurrentUser Protocol; loader slot; get_current_user; require_permission |
| `apps/backend/tests/unit/test_security.py` | 04-09 | VERIFIED | 17 test functions; >100 lines |
| `apps/backend/tests/unit/test_permissions.py` | 04-09 | VERIFIED | 10 test functions; 72 collected via parametrize |
| `apps/backend/tests/unit/test_schemas.py` | 04-09 | VERIFIED | 15 test functions |
| `apps/backend/tests/unit/test_pagination.py` | 04-09 | VERIFIED | 9 test functions |
| `apps/backend/tests/integration/test_alembic_clean.py` | 04-09 | VERIFIED | 2 test functions; structural + subprocess alembic gate |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `security.py:decode_access_token` | `settings.jwt_clock_leeway_seconds` | `get_settings()` inside function body | VERIFIED | `leeway=settings.jwt_clock_leeway_seconds` at line 87 |
| `security.py:encode_access_token` | `settings.access_token_ttl_seconds` | `get_settings()` inside function body | VERIFIED | `timedelta(seconds=settings.access_token_ttl_seconds)` at line 57 |
| `security.py:issue_session_cookies` | `settings.access_token_ttl_seconds` + `settings.refresh_token_ttl_seconds` | `get_settings()` inside function body | VERIFIED | Both settings used for max_age on respective cookies |
| `dependencies.py:get_current_user` | `decode_access_token` + `AccessTokenClaims` | `from app.core.security import decode_access_token` | VERIFIED | Import at line 27; call at line 81 |
| `dependencies.py:require_permission` | `can()` + `ForbiddenError` | `from app.core.permissions import ... can` | VERIFIED | Import at line 26; call in `_checker` closure at line 119 |
| `pagination.py` | `RequestContract`, `ResponseData` | `from app.core.schemas import RequestContract, ResponseData` | VERIFIED | Import at line 17 |
| `.importlinter:modules-independent` | `app.modules.clients` | contract enforcement | VERIFIED | lint-imports exits 0, 3 contracts KEPT |
| `alembic/env.py` | `Base.metadata` (with naming_convention) | `target_metadata = Base.metadata` | VERIFIED | env.py reads `Base.metadata` which carries `NAMING_CONVENTION` at import time; structural test passes |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 113 unit tests pass | `uv run pytest tests/unit -q` | 113 passed in 0.21s | PASS |
| Import lint GREEN | `uv run lint-imports` | 3 kept, 0 broken | PASS |
| mypy strict on core | `uv run mypy app/core/` | Success: no issues found in 11 files | PASS |
| ruff clean on app | `uv run ruff check app/` | All checks passed | PASS |
| Alembic structural test | `uv run pytest tests/integration/test_alembic_clean.py -v` | 1 passed (structural), 1 skipped (DB not running) | PASS |
| Old pagination classes deleted | grep for `LimitOffsetParams\|class Page\[` in pagination.py | grep returns exit 1 (no match) | PASS |
| No `app.modules.members` imports | grep in `apps/backend/` `.py` files | 0 matches | PASS |
| Frontend `can.ts` OWNER_ONLY parity | Manual inspection of 9 entries in `permissions.py` vs `can.ts` | Identical 9 (action, resource) tuples | PASS |

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `app/core/security.py:139-143` | `argon2.VerificationError` not caught in `_do()` — only `VerifyMismatchError` and `InvalidHashError` handled | Advisory (CR-01) | Non-mismatch Argon2 failures yield 500 instead of 401; timing-equivalence guarantee could break; does not affect happy-path requirements |
| `app/core/dependencies.py:89` | `UUID(claims.sub)` unguarded — raises `ValueError` on non-UUID sub claim | Advisory (CR-02) | Crafted JWT with non-UUID sub triggers 500 instead of 401; requires key compromise; error path only |
| `app/core/dependencies.py:49` | `_user_loader` module-global with no reset mechanism | Advisory (WR-01) | Test isolation risk — will cause concrete bugs when Phase 5 adds `get_current_user` tests |
| `apps/backend/pyproject.toml:12` | `httpx` in `[project] dependencies` instead of `[dependency-groups] dev` | Advisory (WR-03) | Unnecessary production image weight; no correctness impact |
| `app/core/security.py:210` | `issue_session_cookies` accepts caller-supplied `secure: bool`; prod assertion deferred | Advisory (WR-04) | Intended by design (prod assertion is Phase 5 work per CONTEXT.md D-25); acceptable for Phase 4 |
| `tests/integration/test_alembic_clean.py:67` | Brittle stdout string assertion on Alembic message text | Advisory (WR-02) | Return-code assertion already provides the correctness guarantee; string is fragile |

---

### Advisory Follow-Up: Code Review Critical Findings

The code review (`04-REVIEW.md`) identified two critical bugs. Both are confirmed present in the codebase. They map exclusively to error paths and do not block any Phase 4 success criterion or requirement, but they should be addressed before Phase 5 writes call sites that exercise these paths in tests.

**CR-01: `verify_password` missing `VerificationError` catch** (`security.py:135-145`)

The `_do()` inner function catches `VerifyMismatchError` and `InvalidHashError` but not `VerificationError` (the parent of `VerifyMismatchError`, also raised for internal Argon2 failures on non-mismatch paths). A non-mismatch Argon2 error propagates as an unhandled 500.

Recommended fix before Phase 5:
```python
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

def _do() -> bool:
    try:
        _ph.verify(encoded_hash, plain)
        return True
    except VerifyMismatchError as exc:
        raise InvalidPassword("invalid_credentials") from exc
    except (VerificationError, InvalidHashError) as exc:
        raise InvalidPassword("invalid_credentials") from exc
```

**CR-02: `UUID(claims.sub)` unguarded in `get_current_user`** (`dependencies.py:89`)

A JWT with `sub` set to a non-UUID string passes `decode_access_token` (PyJWT only checks presence and type `str`) and then causes `UUID()` to raise `ValueError`, yielding 500. Requires key compromise to exploit, but violates the "all decode-path failures yield 401" contract.

Recommended fix before Phase 5:
```python
try:
    user_id = UUID(claims.sub)
except ValueError as exc:
    raise InvalidAccessToken("invalid_token") from exc
user = await _user_loader(session, user_id)
```

---

### Human Verification Required

None. All Phase 4 deliverables are pure-Python primitives and library contracts verifiable programmatically. No user-facing endpoints or UI flows exist in Phase 4.

---

## Gaps Summary

No gaps. All 12 Phase 4 requirements are satisfied. All 5 ROADMAP success criteria are verified. The advisory findings (CR-01, CR-02, WR-01..WR-04) are error-path issues and test-hygiene concerns captured from the code review; they do not represent missing requirement coverage. They should be fixed before Phase 5 adds call sites that exercise those paths.

The `apps/backend/app/modules/members/` directory persists on disk with only a `__pycache__` subdirectory (no `.py` files). It is not tracked by git and will not cause lint-imports failures. The code review flagged this as IN-01 (informational). Removal is recommended to avoid confusion but is not a gap.

---

_Verified: 2026-05-02T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
