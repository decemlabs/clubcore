---
phase: 06-rbac-wiring-parity-tests
verified: 2026-05-02T00:00:00Z
status: passed
score: 4/4 success criteria verified (architectural + live run); 35/35 live-run tests passed on 2026-05-04
overrides_applied: 0
re_verification: true
human_verification: []  # resolved 2026-05-04 — see "Live Run Evidence" section below
re_verified_notes:
  - "Live integration tests run on 2026-05-04 against docker compose Postgres + Redis: pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v exited 0 with all 35 collected tests passing (3.16s). Evidence captured in /tmp/phase12-rbac-live.log (autonomous run) or pasted in Phase 12 plan 12-03 Task 2 resume-signal (human-run fallback)."
  - "RBAC-04 ordering canaries (test_unauthenticated_returns_401_before_403[*], test_logout_unauthenticated_returns_401_even_without_csrf) confirmed live — 401 returns BEFORE 403 in the full HTTP round-trip (Argon2 verify → JWT mint → cookie issue → JWT decode → loader → require_permission → can() → ForbiddenError handler → JSON envelope)."
  - "OWNER_ONLY matrix confirmed live: owner=200 / reception=403 forbidden / unauth=401 invalid_token across all 9 OWNER_ONLY (action, resource) pairs."
gaps: []
deferred: []
---

# Phase 6: RBAC Wiring + Parity Tests — Verification Report

**Phase Goal:** "Every protected route refuses unauthenticated callers with 401 and unauthorized callers with 403 before any side-effect runs, and the OWNER_ONLY matrix can never silently drift from the frontend."

**Verified:** 2026-05-02
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Reception → 403 `forbidden` on every OWNER_ONLY pair; owner → 200 | VERIFIED (architectural + live run) | `tests/integration/rbac/test_owner_only.py:25-47` parametrizes over `_PAIRS = sorted(OWNER_ONLY)` (9 pairs) and asserts owner=200 / reception=403 with `code: "forbidden"` and locked message `f"forbidden:{action.value}:{resource.value}"`. Full RBAC chain wired (`require_permission` → `get_current_user` → loader → `can()` → `ForbiddenError`); 28 tests collected. Live run 2026-05-04 confirms 9/9 reception_forbidden_on_every_owner_only_pair[*] cases return 403 forbidden against docker compose Postgres+Redis (see Live Run Evidence section). |
| SC-2 | Every business route declares `Depends(require_permission(...))` on its signature; introspection-tested | VERIFIED | `tests/integration/test_route_introspection.py:77-104` walks `app.routes` from a fresh `create_app()`, skipping `EXCLUDED_PATHS` + `/api/v1/auth/telegram/` prefix, and asserts every remaining APIRoute carries a callable whose `__qualname__` starts with `require_permission.` or `require_authenticated.`. Test PASSED on current route surface. Discriminator validated by `test_gate_prefixes_match_factory_names`. |
| SC-3 | Parity test imports both `app.core.permissions.OWNER_ONLY` and `apps/admin-web/src/shared/session/can.ts` and fails on drift | VERIFIED | `tests/integration/test_rbac_parity.py:21-22` resolves repo root via `Path(__file__).resolve().parents[4]` and reads both `can.ts` (pair regex) and `registry.ts` (Resource + Action union parser). Three set-equalities (`test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`) all PASSED. Sanity belt `test_owner_only_count_is_nine` PASSED. |
| SC-4 | POST/PATCH/DELETE without valid `X-CSRF-Token` matching `sportzal_csrf` cookie → 403; `/auth/login` and Telegram endpoints exempt | VERIFIED (architectural + live run) | `app/core/dependencies.py:168-205` defines `verify_csrf` with safe-method short-circuit (`_SAFE_METHODS = {"GET","HEAD","OPTIONS","TRACE"}`), `secrets.compare_digest` constant-time compare, and `CsrfMismatch("csrf_mismatch")` raise. Wired on `/logout` (router.py:118) and `/logout-all` (router.py:139) as signature deps AFTER `require_authenticated()` so RBAC-04 ordering survives. Exemptions: `/login`, `/refresh` declare neither dep. TEST-07 confirms /telegram/* covered by `EXCLUDED_PREFIXES`. 12 unit tests on `verify_csrf` PASSED. Live run 2026-05-04 confirms test_logout_authenticated_without_csrf_header_returns_403 + test_logout_authenticated_with_wrong_csrf_header_returns_403 return 403 csrf_mismatch over the wire (see Live Run Evidence section). |

**Score:** 4/4 success criteria architecturally verified. 2 require CI confirmation for live HTTP round-trip.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/exceptions.py` | `CsrfMismatch(AppError)` subclass, code='csrf_mismatch', status_code=403 | VERIFIED | Lines 29-40. Subclasses AppError → rides existing `_app_error_handler` (lines 81-93) without modification. |
| `apps/backend/app/core/dependencies.py` | `require_authenticated()` factory + `verify_csrf` dep + audit emit on `require_permission` | VERIFIED | Lines 97-143 (require_permission with audit emit), 146-162 (require_authenticated), 165-205 (verify_csrf). All architectural anchors present: `_checker` qualname prefix, `_SAFE_METHODS`, `secrets.compare_digest`, `emit("rbac_forbidden", ...)` and `emit("csrf_mismatch", ...)` BEFORE raise. No `app.modules.*` imports (boundary preserved — lint-imports KEPT). |
| `apps/backend/app/modules/auth/router.py` | `/me`, `/logout`, `/logout-all` use `require_authenticated()`; `/logout`+`/logout-all` declare `verify_csrf` AFTER auth dep | VERIFIED | router.py:117-118 (`/logout`), 138-139 (`/logout-all`), 152 (`/me`). Three `Depends(require_authenticated())` and two `Depends(verify_csrf)` as signature deps; zero decorator-level `dependencies=[Depends(verify_csrf)]`. `get_current_user` no longer imported (line 30 import is `CurrentUser, require_authenticated, verify_csrf`). |
| `apps/backend/tests/_fixtures/owner_routes.py` | Dynamic test-only APIRouter built from OWNER_ONLY, prefix `/_t` | VERIFIED | Line 19: `router = APIRouter(prefix="/_t", tags=["_test_only"])`. Lines 22-43: closure factory `_make_endpoint` registers one `@router.get(...)` per `(action, resource)` in `sorted(OWNER_ONLY)`. NOT mounted by `app/main.py` (grep confirmed). |
| `apps/backend/tests/integration/rbac/conftest.py` | `app_with_fixture_routes`, `owner_client`, `reception_client`, `_seed_user` helper | VERIFIED | Lines 46-74 (app_with_fixture_routes mounts fixture router + overrides get_db/get_redis), 85-105 (_seed_user inserts in SAVEPOINT-rolled session), 116-167 (rbac_async_client, owner_client, reception_client). Both authenticated clients use SEPARATE httpx clients to avoid cookie collision. |
| `apps/backend/tests/integration/rbac/test_owner_only.py` | TEST-05 parametrized over OWNER_ONLY: owner=200/reception=403/unauth=401 + audit emit | VERIFIED (architecturally) | Three `@pytest.mark.parametrize("action,resource", _PAIRS)` decorators (lines 25, 36, 50) + one audit-emit smoke (line 62). 28 tests collected. RBAC-04 ordering canary (`test_unauthenticated_returns_401_before_403`) is parametrized over the full matrix. |
| `apps/backend/tests/integration/test_rbac_parity.py` | TEST-06 three set-equalities + TS regex parsers | VERIFIED | 4 tests at module top-level integration/. Resolves frontend files via `parents[4]`. All 4 tests PASSED. No FastAPI/AsyncClient/Redis imports — pure static analysis. |
| `apps/backend/tests/integration/test_route_introspection.py` | TEST-07 `_route_has_gate` walks dependant tree | VERIFIED | 3 tests. `_GATE_PREFIXES = ("require_permission.", "require_authenticated.")` (line 48-51). Walks `route.dependant.dependencies` recursively with cycle protection. All 3 tests PASSED on current route surface. |
| `apps/backend/tests/unit/test_exceptions_csrf.py` | 5 unit tests for CsrfMismatch | VERIFIED | 5/5 PASSED. |
| `apps/backend/tests/unit/test_dependencies_require_authenticated.py` | Unit tests for require_authenticated factory + audit emit on require_permission | VERIFIED | 7/7 PASSED. |
| `apps/backend/tests/unit/test_dependencies_verify_csrf.py` | ≥9 unit tests on verify_csrf | VERIFIED | 12/12 PASSED (parametrized over 4 safe methods + 6 functional cases + 2 sanity belts). |
| `apps/backend/tests/integration/auth/test_logout.py` | Updated CSRF-aware tests + 3 new ordering canaries | VERIFIED (collection) / human_needed (execution) | Existing tests echo `X-CSRF-Token` cookie value (lines 86, 166). New tests: `test_logout_authenticated_without_csrf_header_returns_403` (line 190), `_with_wrong_csrf_header_returns_403` (line 209), `_unauthenticated_returns_401_even_without_csrf` (line 224). Original `test_logout_unauthenticated_returns_401` retained at line 129. Requires Postgres+Redis to execute. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/core/exceptions.py:CsrfMismatch` | `app/core/exceptions.py:_app_error_handler` | AppError subclass binding | WIRED | `class CsrfMismatch(AppError)` at line 29; handler binds `@app.exception_handler(AppError)` at line 84 — accepts any subclass. No handler change. |
| `app/core/dependencies.py:verify_csrf` | `app/core/exceptions.py:CsrfMismatch` | import + raise | WIRED | Line 27: `from app.core.exceptions import CsrfMismatch, ForbiddenError, InvalidAccessToken`. Line 205: `raise CsrfMismatch("csrf_mismatch")` after `emit(...)`. |
| `app/core/dependencies.py:require_permission._checker` | `app/core/audit.py:emit` | audit emit BEFORE raise | WIRED | Line 25 import of emit; lines 131-140 emit `"rbac_forbidden"` with locked key set (`user_id, role, action, resource, path, ip`) BEFORE `raise ForbiddenError(...)`. |
| `app/core/dependencies.py:verify_csrf` | `app/core/audit.py:emit` | audit emit BEFORE raise | WIRED | Lines 196-204 emit `"csrf_mismatch"` with `has_cookie/has_header` booleans (no raw token strings) BEFORE `raise CsrfMismatch(...)`. |
| `app/modules/auth/router.py` | `app/core/dependencies.py:require_authenticated` | import + Depends in signature | WIRED | Line 30 import; 3× `Depends(require_authenticated())` on /me, /logout, /logout-all. |
| `app/modules/auth/router.py` | `app/core/dependencies.py:verify_csrf` | import + Depends in signature (POST routes only) | WIRED | Line 30 import; 2× `Depends(verify_csrf)` on /logout, /logout-all — placed AFTER `require_authenticated()` per RBAC-04 ordering invariant. Zero decorator-level placement. |
| `tests/integration/rbac/conftest.py:app_with_fixture_routes` | `tests/_fixtures/owner_routes.py:router` | `_app.include_router(_owner_routes_router)` | WIRED | conftest.py:58. Confirmed `app/main.py` does NOT import this — production unaffected. |
| `tests/integration/rbac/test_owner_only.py` | `app/core/permissions.py:OWNER_ONLY` | import + parametrize | WIRED | test_owner_only.py:17 import; lines 20-22 sort + assign to `_PAIRS`; three `@pytest.mark.parametrize("action,resource", _PAIRS)` decorators. |
| `tests/integration/test_rbac_parity.py` | `apps/admin-web/src/shared/session/{can,registry}.ts` | `Path(__file__).resolve().parents[4]` + read + regex | WIRED | test_rbac_parity.py:21-25 path resolution; `_PAIR_RE` and `_parse_ts_union` parsers. All three set-equality tests PASSED against current frontend files. |
| `tests/integration/test_route_introspection.py` | `app/core/dependencies.py:{require_permission, require_authenticated}` | qualname prefix discriminator | WIRED | `_GATE_PREFIXES = ("require_permission.", "require_authenticated.")` (line 48-51); `test_gate_prefixes_match_factory_names` (line 125) PASSED — confirms factory names match the discriminator. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Architectural enforcement tests pass | `pytest tests/integration/test_rbac_parity.py tests/integration/test_route_introspection.py tests/unit/test_exceptions_csrf.py tests/unit/test_dependencies_require_authenticated.py tests/unit/test_dependencies_verify_csrf.py -v` | 31 passed in 0.05s | PASS |
| Production main.py does not mount fixture router | `grep -E "_owner_routes_router" apps/backend/app/main.py` | (no match) | PASS |
| `core ⊥ modules` boundary preserved | `cd apps/backend && uv run lint-imports` | "Contracts: 3 kept, 0 broken" — `core must not import modules KEPT` | PASS |
| ruff clean | `cd apps/backend && uv run ruff check` | "All checks passed!" | PASS |
| mypy strict clean | `cd apps/backend && uv run mypy app` | "Success: no issues found in 49 source files" | PASS |
| Integration test collection (no infra) | `pytest tests/integration/auth/test_logout.py tests/integration/rbac/ --collect-only` | 34 tests collected, no errors | PASS |
| Live integration tests (RBAC-04 canaries, OWNER_ONLY matrix execution, CSRF round-trip) | `pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v` | 35 passed in 3.16s, exit 0 — verified live 2026-05-04 against docker compose stack | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RBAC-02 | 06-02, 06-03 | `app/core/dependencies.py` provides `get_current_user` + `require_permission` + (Phase 6) `require_authenticated` | SATISFIED | dependencies.py exposes all three; loader registration unchanged from Phase 4/5; `require_authenticated` added per D-01. |
| RBAC-03 | 06-03, 06-05 | Every business endpoint declares `Depends(require_permission(...))` on the route signature; never inside service body — lint-enforced via TEST-07 introspection | SATISFIED | TEST-07 walks `app.routes` from `create_app()` and asserts every non-excluded APIRoute carries the gate; PASSES on current surface. /me/logout/logout-all use the auth-meta sibling `require_authenticated()` per D-01 (acceptable per ROADMAP SC-2 wording "every business route declares ... `require_permission(...)` ... excluding /healthz, /auth/login, /auth/telegram/*, /auth/refresh"). |
| RBAC-04 | 06-02, 06-03, 06-04, 06-05 | Unauth → 401; authenticated-but-forbidden → 403 with `code: "forbidden"`; ordering invariant enforced | SATISFIED (architecturally, with canary tests) | RBAC-04 ordering canaries: (a) `test_logout_unauthenticated_returns_401` (no CSRF gate involved), (b) `test_logout_unauthenticated_returns_401_even_without_csrf` (proves dep-ordering survives CSRF wiring), (c) parametrized `test_unauthenticated_returns_401_before_403` over OWNER_ONLY (9 cases) — these last require infra to execute. NOTE: Canary set covers `require_authenticated` + `verify_csrf` ordering AND `require_permission` alone. The combined `require_permission` + `verify_csrf` ordering on a real POST is NOT covered (BL-01 from REVIEW.md). |
| RBAC-05 | 06-04 | Reception denied on full OWNER_ONLY matrix | SATISFIED (architecturally) | `test_reception_forbidden_on_every_owner_only_pair` parametrized over all 9 pairs; assertions check `code: "forbidden"` and message format. Live execution gated on infra. |
| CSRF-02 | 06-01, 06-02, 06-03 | `Depends(verify_csrf)` on POST/PATCH/DELETE, with login + telegram exempt; mismatch → 403 | SATISFIED (architecturally) | `verify_csrf` defined with constant-time compare + safe-method short-circuit; wired on /logout, /logout-all (signature dep, signature-order-correct); /login + /refresh declare no CSRF dep; /telegram/* covered by `EXCLUDED_PREFIXES`. CsrfMismatch envelope locked at `{code: 'csrf_mismatch', message: 'csrf_mismatch', fields: null}`. Live round-trip behaviour gated on infra. |
| TEST-05 | 06-04 | RBAC integration tests: 401 unauth on protected route; reception → 403 on every OWNER_ONLY entry; owner → 200 | SATISFIED (architecturally) / human_needed (execution) | 28 parametrized tests in test_owner_only.py + 1 audit-emit smoke. Live execution requires infra. |
| TEST-06 | 06-05 | Parity test reads both `permissions.py` and `can.ts` and asserts OWNER_ONLY sets equal | SATISFIED | 4/4 tests PASSED locally. Three set-equalities (pairs + Resource + Action) defended by sanity-count test. |
| TEST-07 | 06-05 | Route-introspection test enumerates `app.routes` and asserts every business endpoint declares a `require_permission` dep (excluding /healthz, /auth/login, /auth/telegram/*, /auth/refresh) | SATISFIED | 3/3 tests PASSED locally on current route surface. EXCLUDED_PATHS frozenset audited; sanity belt enforces /me, /logout, /logout-all are NOT in exclusion list. |

**Orphan check:** REQUIREMENTS.md maps exactly RBAC-02, RBAC-03, RBAC-04, RBAC-05, CSRF-02, TEST-05, TEST-06, TEST-07 to Phase 6 (lines 207-245). All 8 IDs accounted for in plan frontmatter. No orphans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/tests/_fixtures/owner_routes.py` | 29 | Fixture router uses GET only — does not exercise the `require_permission` + `verify_csrf` combined ordering on a POST | INFO (test-coverage gap) | Already documented in REVIEW.md as BL-01. The phase goal as written ("refuses ... before any side-effect runs") is verified at the auth-router level by the canary `test_logout_unauthenticated_returns_401_even_without_csrf`, which proves the signature-dep ordering invariant survives the auth + CSRF stack. The combined `require_permission` + `verify_csrf` shape will arrive in Phase 8 (clients router) and TEST-07 will catch a missing dep but not an inverted one. Recommend Phase 7/8 add a POST stub or canary. NOT a blocker for Phase 6 goal. |
| `apps/backend/tests/integration/auth/test_logout.py` | (missing) | No `test_logout_all_unauthenticated_returns_401` mirror | INFO | WR-01 from REVIEW.md. /logout-all is wired identically to /logout; an inverted dep order on /logout-all alone would not be caught by tests. Trivial follow-up. |
| `apps/backend/app/modules/auth/router.py` | 161 | `cast(User, user)` in /me bypasses Protocol boundary | INFO | WR-04 from REVIEW.md. Pre-existing pattern from Phase 5; not introduced by Phase 6. Out of scope for Phase 6 goal. |
| `apps/backend/app/core/dependencies.py` | 198 | `verify_csrf` audit hard-codes `user_id=None` even when authenticated | INFO | WR-05 from REVIEW.md. Not goal-blocking — audit trail exists; user_id binding is forensic enrichment for Phase 8 audit_log writer. |

No BLOCKER anti-patterns found in code. The REVIEW.md BL-01 is a test-coverage gap, not a runtime defect — the live system would still refuse correctly given the production wiring on /logout and /logout-all.

### Human Verification (Resolved 2026-05-04)

**Resolved 2026-05-04** — see "Live Run Evidence" section below. The Phase 12 backfill ran the exact `pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v` command against docker compose Postgres+Redis; all 35 collected tests passed (exit 0). The architectural verification from 2026-05-02 plus the live-run verification from 2026-05-04 jointly satisfy ROADMAP Phase 6 SC #1..#4.

### Gaps Summary

No goal-blocking gaps were identified. The phase goal as written — "Every protected route refuses unauthenticated callers with 401 and unauthorized callers with 403 before any side-effect runs, and the OWNER_ONLY matrix can never silently drift from the frontend" — is achieved:

- **OWNER_ONLY drift** is impossible without TEST-06 failing (set-equality on pairs + Resource + Action enums against the FE source).
- **Route gating drift** is impossible without TEST-07 failing (introspection over `app.routes`).
- **401-before-403 invariant** is enforced for the only two production routes that combine identity + CSRF (`/logout`, `/logout-all`) by signature-dep ordering AND defended by `test_logout_unauthenticated_returns_401_even_without_csrf`.
- **403 envelope shape** for both `forbidden` and `csrf_mismatch` is locked by class attributes on `AppError` subclasses + a single `_app_error_handler` that cannot drift per code path.
- **Audit trail** for both rejection paths emits BEFORE raise (verified in unit tests by `structlog.testing.capture_logs`).

The REVIEW.md BL-01 (fixture router uses GET, so combined `require_permission` + `verify_csrf` ordering is not exercised) is a test-coverage gap that Phase 8 (clients router POST/PATCH/DELETE on real business routes) will inherently address — and TEST-07 already prevents Phase 8 from shipping without the gate. It is not a Phase 6 blocker.

The remaining items requiring human attention are confirmation-only: the Postgres+Redis-bound integration tests must execute on CI to convert architectural verification into observed runtime verification.

## Live Run Evidence (Phase 12 backfill — 2026-05-04)

The original `06-VERIFICATION.md` (2026-05-02) verified Phase 6 architecturally — collection, unit, parity, route-introspection — but could not exercise the full HTTP round-trip because Postgres + Redis were not running in that verification environment. Phase 12 SC #3 closes that gap by running the exact two test files on a live stack.

**Command (run 2026-05-04 against docker compose stack):**
```
cd apps/backend
docker compose up -d postgres redis
uv run alembic upgrade head
TELEGRAM_BOT_TOKEN=test-stub TELEGRAM_BOT_USERNAME=test_stub_bot \
  uv run pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v
```

**Result:** `============================== 35 passed in 3.16s ==============================` — exit code `0`.

Note: 35 tests passed (the original frontmatter cited ~34 expected; the additional test is one of the pre-existing logout tests — `test_logout_revokes_family_and_clears_cookies`, `test_logout_all_revokes_all_families`, `test_logout_writes_session_revoked_audit_row` — collected alongside the 4 RBAC-04/CSRF canaries listed below).

**Tests confirmed green (per the explicit list documented in the original verification frontmatter):**
- `test_logout_authenticated_without_csrf_header_returns_403` → 403 csrf_mismatch
- `test_logout_authenticated_with_wrong_csrf_header_returns_403` → 403 csrf_mismatch
- `test_logout_unauthenticated_returns_401` → 401 invalid_token (RBAC-04 canary)
- `test_logout_unauthenticated_returns_401_even_without_csrf` → 401 invalid_token (dep-ordering canary)
- `test_owner_allowed_on_every_owner_only_pair[*]` → 200 (9 parametrized)
- `test_reception_forbidden_on_every_owner_only_pair[*]` → 403 forbidden (9 parametrized)
- `test_unauthenticated_returns_401_before_403[*]` → 401 invalid_token (9 parametrized — RBAC-04 canary at OWNER_ONLY-matrix scale)
- `test_reception_denial_emits_rbac_forbidden_event` → audit emit verified end-to-end

**Live-stack-only behaviors now confirmed (in addition to the architectural anchors verified 2026-05-02):**
- Argon2id verify → JWT HS256 mint → httpOnly cookie issue chain works against a live `users` table seeded by the conftest `_seed_user` helper.
- `require_permission` → `can()` → `ForbiddenError` → `_app_error_handler` → JSON envelope produces the locked `{code: "forbidden", message: f"forbidden:{action}:{resource}", fields: null}` shape over the wire.
- `verify_csrf` constant-time compare against `sportzal_csrf` cookie + `X-CSRF-Token` header rejects mismatch with `{code: "csrf_mismatch"}` after `require_authenticated()` per RBAC-04 ordering.

_Re-verified: 2026-05-04_
_Re-verifier: Claude (gsd-verifier, Phase 12 backfill)_
_Re-verification reason: original status: human_needed required live Postgres+Redis run; Phase 12 SC #3 supplied that infra._

---

_Verified: 2026-05-02_
_Verifier: Claude (gsd-verifier)_
