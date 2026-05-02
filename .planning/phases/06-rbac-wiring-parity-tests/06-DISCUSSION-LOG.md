# Phase 6: RBAC Wiring + Parity Tests - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 06-rbac-wiring-parity-tests
**Areas discussed:** Auth-meta route gating, CSRF placement strategy, TEST-05 surface strategy, Parity test scope, Phase 5 route migration, Fixture-router authentication

---

## Auth-meta route gating (TEST-07 introspection)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend exclusion list | Keep /auth/me, /logout, /logout-all on Depends(get_current_user); add their paths to TEST-07's allowlist alongside /healthz, /auth/login, /auth/telegram/*, /auth/refresh. | |
| require_permission with sentinel pair | Wrap each with Depends(require_permission(Action.VIEW, Resource.DASHBOARD)) — both roles can VIEW:dashboard (not in OWNER_ONLY). | |
| New require_authenticated() factory | Add a sibling Depends(require_authenticated) that wraps get_current_user; introspection test accepts EITHER require_permission OR require_authenticated as a valid gate. | ✓ |

**User's choice:** New `require_authenticated()` factory.
**Notes:** Cleanest semantically — every protected route declares its gate factory; no proxy permission pair, no exclusion-list growth.

---

## CSRF placement strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Sub-router dependencies + auth opt-in | Each business sub-router declares APIRouter(dependencies=[Depends(verify_csrf)]); auth router opts in per-route on /logout, /logout-all only. | ✓ |
| v1 router blanket + per-route exempt | Apply Depends(verify_csrf) at the v1 APIRouter level; auth router opts OUT per route via marker dep. | |
| Middleware with path allowlist | ASGI middleware inspects method + path; skips safe methods and EXEMPT_PATHS set. | |

**User's choice:** Sub-router dependencies + auth opt-in.
**Notes:** New module = new sub-router = automatic CSRF; no allowlist surface to drift. The auth router's exempt-vs-protected asymmetry is opt-in by route.

---

## TEST-05 surface strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Test-only fixture router | tests/_fixtures/owner_routes.py exposes one stub endpoint per OWNER_ONLY pair, each with Depends(require_permission(...)). Test app mounts both api + fixture router; tests parametrize over OWNER_ONLY. | ✓ |
| Unit test on require_permission directly | Call require_permission(action, resource)(stub_user) directly with fake CurrentUser; assert ForbiddenError or pass. No HTTP roundtrip. | |
| Defer to Phase 8 against real routes | Phase 6 ships only TEST-06 + TEST-07; TEST-05 lands in Phase 8 against real /clients DELETE. | |

**User's choice:** Test-only fixture router.
**Notes:** Phase 6 ships a meaningful TEST-05 today against the full HTTP stack; Phase 8 can add a smaller test against real /clients DELETE for additional coverage.

---

## Parity test scope (TEST-06)

| Option | Description | Selected |
|--------|-------------|----------|
| OWNER_ONLY pairs + enum strings | Three set-equalities: backend OWNER_ONLY == FE pairs; backend Resource StrEnum values == FE Resource union; backend Action StrEnum values == FE Action union. | ✓ |
| OWNER_ONLY pairs only | Just compare the 9 (action, resource) pairs as sets — strict letter of TEST-06. | |

**User's choice:** OWNER_ONLY pairs + enum strings.
**Notes:** Stronger parity closes the hole where renaming a Resource value not in OWNER_ONLY (e.g., 'schedule' → 'timetable') silently breaks frontend RoleGate checks at runtime without failing pair-only parity.

---

## Phase 5 auth-meta route migration

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate routes | Phase 6 edits auth router to swap Depends(get_current_user) → Depends(require_authenticated()) on /me, /logout, /logout-all. Every protected route declares EXACTLY ONE gate factory. | ✓ |
| Keep + lenient introspection | Phase 5 routes untouched; introspection test accepts {require_permission, require_authenticated, get_current_user}. | |

**User's choice:** Migrate routes.
**Notes:** One-line change per route; strong invariant — get_current_user as a direct route dep is BANNED on protected routes.

---

## Fixture-router authentication strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Seed two real DB users | Test fixtures seed owner + reception via real authenticate() / issue_tokens(); tests use real httpOnly cookies. Exercises full /auth/login + cookie + JWT decode flow on every RBAC test. | ✓ |
| Mint access cookie directly | Test helper builds an access JWT via encode_access_token(); register_user_loader is overridden with a stub. Fast; skips Argon2/Redis. | |
| Override require_permission via dependency_overrides | FastAPI app.dependency_overrides injects a stub get_current_user. Middle ground. | |

**User's choice:** Seed two real DB users.
**Notes:** Slowest but most honest — Phase 6 owns the gate, so Phase 6 tests should prove the gate works on the real auth chain that ships, not on a stripped-down approximation.

---

## Claude's Discretion

- **CSRF safe-method short-circuit (D-06):** GET/HEAD/OPTIONS/TRACE skip the cookie/header check at the top of `verify_csrf`. Standard CSRF practice; sub-router-level dep means GET endpoints in business modules MUST not 403 for missing CSRF.
- **`CsrfMismatch` as a distinct AppError subclass (D-08):** code="csrf_mismatch", status=403. Rationale: Phase 10 frontend can branch on code to silently retry on csrf_mismatch (refresh CSRF cookie + retry once) while propagating true `forbidden` to the UI.
- **Audit event names (D-23):** `event=rbac_forbidden`, `event=csrf_mismatch` — locked now so Phase 8's DB writer latches on without renaming.
- **Fixture router path prefix `/_t` (D-10):** deliberately ugly to signal "not real" at a glance in route enumerations and stack traces.
- **Parity-test regex over TS files (D-15):** simpler than a TS toolchain; the file shape is locked and any reformatting that breaks the regex is a deliberate parity-test failure (intentional anchoring).
- **Phase 5 test_logout.py update (D-24):** one-line addition per /logout call to echo `sportzal_csrf` cookie as `X-CSRF-Token` header. Phase 6 owns this update.

## Deferred Ideas

- `Depends(require_permission(...))` on real business endpoints — Phase 8 (clients).
- `audit_log` DB row writes for forbidden / csrf_mismatch events — Phase 8.
- Frontend `X-CSRF-Token` header injection in fetcher — Phase 9.
- CSRF retry-on-mismatch fetcher logic — Phase 9.
- Per-IP rate-limit on 403 responses — v1.2.
- `is_active` / `email_verified` checks in `require_authenticated` — v1.2 (columns don't exist yet).
- HMAC-bound CSRF tokens — v2+.
- `/auth/refresh` CSRF protection — explicitly NOT applied; revisit only if a concrete attack scenario emerges.
- Active-sessions UI / per-session revoke — v1.2.
- Policy engine (Casbin / Oso / OPA) — explicit OoS in REQUIREMENTS.md.
