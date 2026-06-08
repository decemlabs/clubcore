---
phase: 96-referral-domain-backend
plan: "03"
subsystem: backend
tags: [referrals, service, router, integration-tests, rbac, idor, audit]
requirements: [REFER-01, REFER-02, REFER-03, REFER-07]

dependency_graph:
  requires:
    - "96-01 (audit pairs locked in LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS)"
    - "96-02 (ReferralCode/ReferralCapture/ReferralConfig ORM models + schemas + 0068 seed)"
  provides:
    - "GET /api/v1/client/referral/code — idempotent Crockford code mint for client principal"
    - "POST /api/v1/client/referral/capture — IDOR-safe referee binding from principal"
    - "GET /api/v1/i/{code} — public deep-link resolver, always 200, PII-minimal"
    - "GET /api/v1/referral/config — owner-only singleton read (Resource.GYM gate)"
    - "PUT /api/v1/referral/config — owner-only singleton write (RBAC-04 ordered)"
    - "referral_code_generated + referral_captured audit events co-transactionally emitted"
  affects:
    - "apps/backend/app/modules/referrals/repository.py"
    - "apps/backend/app/modules/referrals/service.py"
    - "apps/backend/app/modules/referrals/router.py"
    - "apps/backend/app/api/v1/router.py"
    - "apps/backend/tests/integration/test_referral_*.py (4 files)"

tech_stack:
  added: []
  patterns:
    - "caller-owns-txn (D-32-10): flush only in service; only update_referral_config commits"
    - "D-54-08 raw SQL cross-module client access (no ORM import of Client)"
    - "CROCKFORD_ALPHABET 32-char base32 (no O/I/L), 8-char codes, bounded retry=3"
    - "INFRA-15 gating: audit emit only on real inserts (no duplicate on idempotent paths)"
    - "IDOR-safe capture: referee from principal only (T-96-05)"
    - "RBAC-04 ordering: require_permission BEFORE verify_csrf in owner PUT"
    - "Anti-enumeration: GET /i/UNKNOWN → 200/valid:false (never 404 — T-96-06)"
    - "ResponseEnvelope[None] ack pattern for POST capture"

key_files:
  created:
    - path: "apps/backend/app/modules/referrals/repository.py"
      role: "Caller-owns-txn ORM helpers: get_code_by_client_id, get_code_by_value, get_capture_by_referee, get_config, upsert_config"
    - path: "apps/backend/app/modules/referrals/service.py"
      role: "CROCKFORD_ALPHABET, typed errors, 5 service functions with IDOR safety and co-transactional audit"
    - path: "apps/backend/app/modules/referrals/router.py"
      role: "Triple-router: public_router (GET /i/{code}), client_router (GET+POST), owner_router (GET+PUT) with RBAC-04"
    - path: "apps/backend/tests/integration/test_referral_code.py"
      role: "REFER-01: idempotency, Crockford validation, single audit row, distinct codes, 401 gate"
    - path: "apps/backend/tests/integration/test_referral_capture.py"
      role: "REFER-03: bind, audit, idempotent no-op, self-referral 422, unknown 404, IDOR"
    - path: "apps/backend/tests/integration/test_referral_resolve.py"
      role: "REFER-02: valid:true+first-name+welcomeBonus, exact key set, unknown→200/valid:false, case-insensitive"
    - path: "apps/backend/tests/integration/test_referral_config.py"
      role: "REFER-07: seed defaults, PUT round-trip, reception 403, owner CSRF gate, RBAC-04 ordering"
  modified:
    - path: "apps/backend/app/api/v1/router.py"
      role: "Appended Phase-96 block: three late imports + include_router x3 (no-prefix, /client, /referral)"

decisions:
  - "D-96-03-01: Resource.GYM reused for owner config gate (no new Resource.REFERRAL) — planner-locked to avoid CISO-01 byte-parity break"
  - "D-96-03-02: ResponseEnvelope[None] ack for POST /client/referral/capture (matches client_auth router convention)"
  - "D-96-03-03: resolve_public_code passes settings for welcome_bonus_kopecks from config (fallback 0 when config missing)"
  - "D-96-03-04: Two tests using a second independent AsyncClient use http_client._transport.app (not _app) to access the overridden ASGI app"

metrics:
  duration: ~35 min
  completed: "2026-06-08"
  tasks_completed: 3
  files_created: 7
  files_modified: 1
---

# Phase 96 Plan 03: Referral Service + Routers + Integration Tests Summary

**One-liner:** Full referral domain backend — CROCKFORD-base32 idempotent code mint, IDOR-safe principal-only capture, PII-minimal public resolver, owner-config CRUD with RBAC-04 ordering, and 22 integration tests proving every contract and security boundary.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Repository + service (code gen, resolve, capture, config) | cb955082 | repository.py, service.py (new) |
| 2 | Triple-router + mount in v1 router | addb7ca8 | router.py (new), app/api/v1/router.py (modified) |
| 3 | Integration tests — code, capture, resolve, config | 68e299f9 | 4 test files (new) |

## What Was Built

### Task 1: Repository + Service (commit `cb955082`)

**`repository.py`** — caller-owns-txn ORM helpers (no flush/commit):
- `get_code_by_client_id` — returns ReferralCode | None for idempotency check
- `get_code_by_value` — upper-cases the input; returns ReferralCode | None
- `get_capture_by_referee` — UNIQUE check for idempotency gate in capture
- `get_config` — singleton select limit 1
- `upsert_config` — gym singleton pattern with model_dump(exclude_unset=True)

**`service.py`** — five service functions with full discipline:
- `CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"` (32 chars, no O/I/L)
- `_generate_unique_code` — 8-char `secrets.choice` loop, raw-SQL existence check, RuntimeError after 3 attempts
- `get_or_create_referral_code` — idempotent; emits `referral_code_generated` only on real insert; returns `{code, shareUrl}` with `settings.pwa_base_url/i/{code}`
- `resolve_public_code` — always 200; D-54-08 raw SQL for first_name only; fallback 0 welcome_bonus when config missing; never raises 404
- `capture_referral` — idempotency gate first; ReferralCodeNotFoundError (404) on unknown code; SelfReferralError (422) on self-referral; referee from principal arg only (T-96-05 IDOR)
- `get_referral_config` — 404 via ReferralConfigNotFoundError if seed missing
- `update_referral_config` — upsert + flush + commit (singleton owns txn, same discipline as gym service)

Typed error classes: `ReferralCodeNotFoundError`, `SelfReferralError`, `ReferralConfigNotFoundError`

mypy --strict: clean on both files.

### Task 2: Triple-Router + v1 Mount (commit `addb7ca8`)

**`router.py`** — three APIRouter instances:
- `public_router` (tag "Referral"): `GET /i/{code}` — no auth, `public_resolve_referral_code`
- `client_router` (tag "Client-Portal"): `GET /referral/code` + `POST /referral/capture` — `require_client()` gate; capture body carries only `{code}`; referee from `client.id`
- `owner_router` (tag "Referral"): `GET /config` (require_permission gate) + `PUT /config` (RBAC-04: `require_permission` declared BEFORE `verify_csrf`)

**`app/api/v1/router.py`** — Phase-96 block appended after gym block:
```python
from app.modules.referrals.router import client_router as referral_client_router  # noqa: E402
from app.modules.referrals.router import owner_router as referral_owner_router  # noqa: E402
from app.modules.referrals.router import public_router as referral_public_router  # noqa: E402

v1.include_router(referral_public_router)                    # /api/v1/i/{code}
v1.include_router(referral_client_router, prefix="/client")  # /api/v1/client/referral/*
v1.include_router(referral_owner_router, prefix="/referral") # /api/v1/referral/config
```

Route registration verified: all 4 paths confirmed via `create_app()` routes introspection.
mypy --strict + ruff + lint-imports: all clean.

### Task 3: Integration Tests — 22 tests, all passing (commit `68e299f9`)

**`test_referral_code.py`** (5 tests, REFER-01):
- Code is 8 chars, all CROCKFORD_ALPHABET, shareUrl ends `/i/{code}`
- Second GET returns same code (idempotent)
- Two GETs → exactly 1 `referral_code_generated` audit row
- Two clients → distinct codes
- No-auth → 401

**`test_referral_capture.py`** (6 tests, REFER-03):
- B captures A's code → `referral_captures` row with referrer=A, referee=B
- `referral_captured` audit row with all 4 payload fields
- Second capture by same referee → 200 no-op, exactly 1 capture row
- Self-referral → 422 `self_referral_not_allowed`
- Unknown code → 404 `referral_code_not_found`
- Referee from principal (B.id in DB regardless of body contents)

**`test_referral_resolve.py`** (5 tests, REFER-02):
- Known code → 200, valid:true, referrerFirstName = referrer's first name, welcomeBonusKopecks = 30000
- Exact key set `{valid, referrerFirstName, welcomeBonusKopecks}` — no clientId, no lastName
- Unknown code → 200 (NOT 404), valid:false, referrerFirstName:null
- Unknown code — same exact key set
- Lower-case code → valid:true (normalised to upper)

**`test_referral_config.py`** (6 tests, REFER-07):
- Owner GET → 200 with seed defaults 50000 / 30000
- Owner PUT → 200; subsequent GET reflects new values (read-after-write)
- Reception GET → 403
- Reception PUT (with CSRF header) → 403 (RBAC fires before CSRF)
- Owner PUT without CSRF header → 403 (passes RBAC, fails CSRF — RBAC-04 proven)
- Reception PUT without CSRF header → 403 from RBAC (never reaches CSRF check)

## Verification Results

```
uv run mypy --strict app/modules/referrals/        ✅ 0 issues (6 source files)
uv run ruff check app/modules/referrals/ app/api/v1/router.py tests/integration/test_referral_*.py  ✅
uv run lint-imports                                 ✅ 3/3 contracts kept, 0 broken
uv run pytest tests/unit/test_referral_audit_events.py    ✅ 8 passed (no regression)
uv run pytest tests/integration/test_referral_*.py -q     ✅ 22 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy strict "Returning Any from function" in repository.py**
- **Found during:** Task 1 mypy check
- **Issue:** `await session.scalar(stmt)` returns `Any` in SQLAlchemy typed stubs; returning without explicit annotation caused 4 `no-any-return` errors
- **Fix:** Added explicit local type annotation `result: ReferralCode | None = await session.scalar(stmt)` in all four scalar helpers (same pattern as gym/repository.py)
- **Files modified:** `app/modules/referrals/repository.py`
- **Commit:** cb955082

**2. [Rule 1 - Bug] ASGITransport attribute name is `.app` not `._app`**
- **Found during:** Task 3 first test run
- **Issue:** Tests that create a second independent AsyncClient to authenticate as a different user used `http_client._transport._app` — `httpx.ASGITransport` exposes `.app` (public), not `._app` (private)
- **Fix:** Changed to `http_client._transport.app` in `test_referral_code.py` and `test_referral_capture.py`
- **Files modified:** Both test files
- **Commit:** 68e299f9

**3. [Rule 1 - Bug] Missing .env in worktree blocked app import for route verification**
- **Found during:** Task 2 route verification step
- **Issue:** Worktree lacked `.env`; `YooKassaSettings()` instantiated at module-import time requires env vars (same issue as 96-02)
- **Fix:** Copied `.env` from main repo (git-ignored; not committed)
- **Note:** Same workaround as documented in 96-02 SUMMARY

**4. [Rule 1 - Bug] ruff E501 + F401 in test files**
- **Found during:** Task 3 ruff check
- **Issue:** `from sqlalchemy import select, text` — `text` unused; three docstring lines > 100 chars
- **Fix:** ruff --fix removed unused import; docstrings shortened manually
- **Files modified:** test_referral_code.py, test_referral_resolve.py

## Known Stubs

None — all five service functions are fully implemented and wired to the ORM. No hardcoded placeholder values in any response path.

## Threat Flags

None — all threat model mitigations from the plan `<threat_model>` are implemented and tested:

| Threat | Mitigation | Test |
|--------|-----------|------|
| T-96-05 IDOR capture | Referee from principal only; no id field in request body | test_capture_referee_from_principal_not_body |
| T-96-06 PII disclosure | First name only; exact key set asserted | test_resolve_known_code_no_pii_leakage |
| T-96-07 Config elevation | Resource.GYM gate; reception 403; RBAC-04 ordering | test_reception_*_forbidden, test_rbac04_* |
| T-96-08 Self-referral | SelfReferralError 422 | test_capture_self_referral_returns_422 |
| T-96-09 Double-capture | App-level idempotency + DB UNIQUE on referee_client_id | test_capture_is_idempotent_second_call_no_op |
| T-96-10 Audit repudiation | Audit emitted co-transactionally, gated on real inserts | test_capture_emits_audit_row, test_get_referral_code_single_audit_row_on_two_calls |

## Self-Check: PASSED
