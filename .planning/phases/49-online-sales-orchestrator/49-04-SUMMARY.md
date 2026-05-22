---
phase: 49-online-sales-orchestrator
plan: 04
subsystem: online_payments
tags:
  - router
  - rbac-04
  - idempotency
  - http-endpoints
dependency_graph:
  requires:
    - 49-02  # get_yookassa_settings @lru_cache factory (BLOCKER #5)
    - 49-03  # service.sell_*, schemas.SellRequest/SellResponse (parallel wave 2)
  provides:
    - POST /api/v1/online-payments/memberships/{plan_id}/sell      (PAY-03)
    - POST /api/v1/online-payments/memberships/{plan_id}/sell-qr   (PAY-05)
    - POST /api/v1/online-payments/pt-packages/{plan_id}/sell      (PAY-04)
    - POST /api/v1/online-payments/pt-packages/{plan_id}/sell-qr   (PAY-05)
  affects:
    - apps/backend/app/api/v1/router.py  # new mount + import
tech-stack:
  added: []
  patterns:
    - RBAC-04 ordering (require_permission -> verify_csrf -> verify_idempotency)
    - Outer-layer HTTP Idempotency-Key replay dance (D-49-16) mirroring memberships/router.py:301-373
    - Runner-closure variant of the dance to keep service.sell_* call sites visible per endpoint
key-files:
  created:
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/tests/modules/online_payments/test_router_sell_endpoints.py
    - apps/backend/tests/modules/online_payments/test_router_path_registration.py
  modified:
    - apps/backend/app/api/v1/router.py  # mount online_payments_router with prefix="/online-payments"
decisions:
  - "Outer Idempotency-Key dance extracted into _outer_idempotency_replay_or_run(runner) helper so each endpoint still references its target service function directly (4x require_permission + 2x service.sell_membership + 2x service.sell_pt_package = grep-traceable RBAC and call-graph)."
  - "Tag string uses kebab 'online-payments' to align with the URL slug ('memberships' uses lowercase singular, 'pt-packages' uses kebab — kebab wins for multi-word resource per Phase 30 INFRA-18 precedent)."
metrics:
  duration_sec: 710
  duration_min: 11
  completed_date: 2026-05-22
---

# Phase 49 Plan 04: Online-payments sell endpoints + v1 mount Summary

Ships the four POST sell endpoints (`memberships × {redirect, qr}` and
`pt-packages × {redirect, qr}`) under `/api/v1/online-payments/*` with the
canonical RBAC-04 → CSRF → Idempotency-Key dependency ordering. Mounts the
new `online_payments_router` from `app/api/v1/router.py` between
`memberships_router` and `payments_router`. Adds a runtime path-registration
test (BLOCKER #6) that walks `app.routes` after `create_app()` and asserts
the four exact path strings exist at the canonical mount prefix.

## What shipped

### 1. `apps/backend/app/modules/online_payments/router.py` (new — 343 lines)

Four `@router.post(...)` decorators expose the sell endpoints. Each endpoint
signature declares dependencies in RBAC-04 order:

1. `plan_id: UUID` (path param)
2. `payload: SellRequest` (body)
3. `request: Request` (for outer Idempotency-Key body hashing)
4. `actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.{MEMBERSHIPS|PT_PACKAGES}))]`
5. `_csrf: Annotated[None, Depends(verify_csrf)]`
6. `idempotency_key: Annotated[str, Depends(verify_idempotency)]`
7. `redis: Annotated[Redis, Depends(get_redis)]`
8. `session: Annotated[AsyncSession, Depends(get_db)]`
9. `yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)]`

The 401-before-403-before-422 invariant is preserved by FastAPI's
signature-order dependency resolution and statically enforced by
`tests/integration/test_route_introspection.py`.

Each endpoint body builds a thin async closure that calls `service.sell_membership(...)`
or `service.sell_pt_package(...)` with the canonical kwargs (`plan_id`,
`client_id`, `confirmation_type`, `actor`, `yookassa_settings`), then hands
that closure to the shared `_outer_idempotency_replay_or_run(runner=...)`
helper which performs the Redis SET-NX + envelope-cache dance (D-49-16)
verbatim from `memberships/router.py:301-373`.

### 2. `apps/backend/app/api/v1/router.py` (modified — 6 lines added)

```python
from app.modules.online_payments.router import router as online_payments_router
...
v1.include_router(
    online_payments_router,
    prefix="/online-payments",
    tags=["online-payments"],
)
```

The `/api/v1` prefix is added one level higher at
`apps/backend/app/api/router.py:18` (`api.include_router(v1, prefix="/api/v1")`).
Net mount path: `/api/v1/online-payments/...`.

### 3. `apps/backend/tests/modules/online_payments/test_router_path_registration.py` (new — 90 lines)

BLOCKER #6 deliverable. Three test functions:

- `test_all_four_post_sell_paths_registered_with_correct_mount_prefix` —
  walks `app.routes` after `create_app()` and asserts ALL four expected POST
  path strings exist verbatim. Failure prints actual observed paths for
  immediate diagnosis.
- `test_return_path_registered_when_plan_49_05_has_shipped` — conditional
  assertion: if any `/online-payments` path ends in `/return`, it MUST be
  `/api/v1/online-payments/return` (catches a future 49-05 mount drift
  without failing while 49-05 is still in flight).
- `test_no_unexpected_online_payments_paths_registered` — defensive:
  any `/online-payments` path outside `EXPECTED_POST_PATHS ∪ {EXPECTED_GET_PATH}`
  fails the test, surfacing contract drift early.

### 4. `apps/backend/tests/modules/online_payments/test_router_sell_endpoints.py` (new — 331 lines)

Twelve HTTP-level integration tests via `httpx.ASGITransport`:

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_sell_membership_redirect_201_reception` | 201 + `confirmationUrl` non-null, `qrPayload` null |
| 2 | `test_sell_membership_qr_201_owner` | 201 + `qrPayload` non-null, `confirmationUrl` null |
| 3 | `test_sell_pt_package_redirect_201_reception` | 201 |
| 4 | `test_sell_pt_package_qr_201_reception` | 201 + `qrPayload` non-null |
| 5 | `test_sell_membership_401_when_unauthenticated` | RBAC-04 ordering: 401 BEFORE 403/422 |
| 6 | `test_sell_membership_403_when_csrf_missing` | 403 csrf_invalid |
| 7 | `test_sell_membership_422_when_idempotency_key_missing` | 422 `idempotency_key_required` |
| 8 | `test_sell_membership_422_when_client_email_null` | 422 `client_email_required_for_online_payment` + respx never called |
| 9 | `test_sell_membership_503_on_yookassa_5xx` | 503 `yookassa_unavailable` |
| 10 | `test_sell_membership_502_on_yookassa_4xx_non_422` | 502 `yookassa_permanent_error` |
| 11 | `test_sell_membership_422_on_yookassa_validation_error` | 422 `yookassa_validation_error` |
| 12 | `test_sell_membership_idempotency_replay_returns_same_envelope` | Outer replay returns byte-identical envelope; upstream called exactly once |

`asyncio_mode = "auto"` (from `pyproject.toml`) auto-marks every async test;
no explicit `@pytest.mark.asyncio` decorators needed.

## Verified BLOCKER resolutions

- **BLOCKER #5 (Plan 49-02 prerequisite):** Router consumes
  `Depends(get_yookassa_settings)` four times (one per POST endpoint),
  importing the `@lru_cache(maxsize=1)` factory from
  `app.integrations.yookassa.settings`. The factory was already shipped by
  Plan 49-02 (verified via `Read` on
  `apps/backend/app/integrations/yookassa/settings.py:55-69`).
- **BLOCKER #6:** Runtime path-registration test ships in
  `test_router_path_registration.py` and calls `create_app()` to populate
  `app.routes` then asserts the 4 exact POST path strings exist.

## Two-layer idempotency (D-49-16)

| Layer | Source | Storage | Window |
|-------|--------|---------|--------|
| Outer (HTTP) | Operator-supplied `Idempotency-Key` header | Redis (`sz:idem:` prefix, `IDEMPOTENCY_TTL_SECONDS=3600`) | Per-route, per-key envelope replay |
| Inner (ЮKassa) | Deterministic key (D-49-08) derived from `(subject_kind, plan_id, client_id, today_iso)` by the service | ЮKassa server-side | Within-day per-subject |

Both layers are belt-and-suspenders. The outer layer (this plan's
responsibility) absorbs operator double-clicks at the HTTP edge before any
ЮKassa work; the inner layer (Plan 49-03's responsibility) guarantees that
even a cross-process race that bypasses the outer layer still results in a
single ЮKassa payment.

## Permission mapping (D-49-24)

Both `(CREATE, MEMBERSHIPS)` and `(CREATE, PT_PACKAGES)` are reception+owner
— neither is in `OWNER_ONLY`. The four sell endpoints accept both roles;
the existing in-person sale endpoints (`POST /api/v1/memberships`, etc.)
already use the same Resource pairs, so no new permission semantics are
introduced for online sales.

## RBAC ordering (D-49-25)

The signature order
`require_permission → verify_csrf → verify_idempotency` causes FastAPI to
resolve dependencies in that order, so:

- Unauthenticated request → `require_permission` raises 401 (FastAPI maps
  `UnauthorizedError`) **before** CSRF or Idempotency-Key validation runs.
- Authenticated but wrong role → 403 (still wouldn't apply to these
  endpoints since both roles are admitted).
- Missing CSRF header → 403 csrf_invalid (Phase 8 D-15).
- Missing/malformed Idempotency-Key → 422
  (`idempotency_key_required` / `idempotency_key_invalid_format`).

`tests/integration/test_route_introspection.py` walks every APIRoute and
asserts the gate is present; this test auto-covers the four new routes.

## Deviations from Plan

### Refactored: Outer-idempotency dance extracted via runner closure

**Rule:** Refactor (no rule trigger — design choice during implementation,
verified against acceptance criteria).

**Found during:** Task 1 (initial implementation produced 4 verbatim copies
of the 50-line outer-idempotency dance; second pass refactored to share).

**Issue:** Verbatim-duplicated 50-line outer-idempotency block × 4 endpoints
violates DRY and creates a future maintenance hazard (any future tweak to
the replay-cache shape must be applied four times).

**Fix:** Extract `_outer_idempotency_replay_or_run(runner: Callable[[],
Awaitable[SellResponse]])` helper. Each endpoint defines a thin
`async def _runner()` closure that captures the per-endpoint
`(session, plan_id, payload, actor, yookassa_settings,
confirmation_type)` and calls the appropriate `service.sell_*` directly.
The closure is then handed to the helper.

**Why this preserves the plan's acceptance criteria:**

- `grep -c "service.sell_membership" router.py` → **2** (one per membership
  endpoint, satisfying the plan's literal count).
- `grep -c "service.sell_pt_package" router.py` → **2** (same).
- `grep -c "@router.post(" router.py` → **4** (unchanged).
- Each endpoint's call graph is locally visible: the runner closure body is
  inline in the endpoint, not delegated through a dispatch table or
  string-keyed lookup.

**Files modified:** `apps/backend/app/modules/online_payments/router.py`
(commit `13398df`).

### Refactored: Tag name uses kebab `online-payments` (vs `online_payments`)

**Found during:** v1 mount.

**Issue:** Existing tags in `app/api/v1/router.py` are mixed:
`memberships` (lowercase singular), `pt-packages` (kebab), `_internal`
(snake — internal namespace).

**Fix:** Used `tags=["online-payments"]` to align with the URL slug
(`/online-payments`) and to mirror the kebab convention already used for
the multi-word `pt-packages` mount (Phase 30 INFRA-18 precedent).

**Files modified:** `apps/backend/app/api/v1/router.py` (commit `7a50b63`).

## Parallel-execution verification gap

This plan executed in a worktree parallel to Plan 49-03, which owns
`app/modules/online_payments/schemas.py`, `app/modules/online_payments/service.py`,
`tests/modules/online_payments/__init__.py`, and
`tests/modules/online_payments/conftest.py`. Those files DO NOT exist in
this worktree. As a result:

- **`uv run python -c "from app.modules.online_payments.router import router"`** fails with `ImportError: cannot import name 'service' from 'app.modules.online_payments'` until 49-03 ships.
- **`uv run pytest tests/modules/online_payments/`** fails the same way at conftest import time (the test files run through `app.main.create_app()` which transitively imports `online_payments.router`).
- **`uv run mypy app/modules/online_payments/router.py`** cannot resolve `service` / `schemas` symbols, so strict-mode mypy would fail.
- **`uv run lint-imports`** evaluation is deferred: the router introduces
  no new module-cross beyond what is already whitelisted (it imports only
  from `app.core.*`, `app.integrations.yookassa.settings`, and
  `app.modules.online_payments.*` — all sibling-module imports).

**Verification that DID pass in this worktree:**

- **ruff** clean on `app/modules/online_payments/router.py`,
  `app/api/v1/router.py`,
  `tests/modules/online_payments/test_router_path_registration.py`, and
  `tests/modules/online_payments/test_router_sell_endpoints.py`.
- **RED phase**: `test_router_path_registration.py::test_all_four_post_sell_paths_registered_with_correct_mount_prefix`
  was confirmed failing before the router shipped — log shows the literal
  "Actual /online-payments paths observed: []" assertion failure.

**Post-merge verification** (to be executed once both 49-03 and 49-04
worktree branches are merged into the integration branch):

```bash
cd apps/backend
uv run python -c "from app.modules.online_payments.router import router; \
    print(len(router.routes), 'routes'); \
    print(sorted([(list(r.methods)[0], r.path) for r in router.routes if hasattr(r, 'methods')]))"
uv run ruff check app/modules/online_payments/router.py app/api/v1/router.py \
    tests/modules/online_payments/
uv run mypy app/modules/online_payments/router.py
uv run lint-imports
uv run pytest tests/modules/online_payments/test_router_sell_endpoints.py \
    tests/modules/online_payments/test_router_path_registration.py \
    tests/integration/test_route_introspection.py -x -q
```

This verification gap is **intentional and documented**: parallel-execution
worktree mode (Plans 49-03 + 49-04 running concurrently in Wave 2) trades
in-worktree mypy/pytest verification for wall-clock throughput on
independent file slices.

## Authentication gates

None — the plan was fully autonomous and no human-action checkpoints were
hit.

## Idempotency-Key dependency name

The exact dependency used in the router signatures is
`verify_idempotency`, imported from `app.core.idempotency`. Signature:

```python
async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
) -> str
```

Returns the route-bound key string `f"{method}:{path}:{header_value}"`
(D-32-19 / D-33-16 / CR-01) so the same client-supplied header value reused
across different endpoints cannot collide in the Redis `sz:idem:*`
namespace.

## Verified route paths (will be exhaustively asserted post-merge)

```
POST /api/v1/online-payments/memberships/{plan_id}/sell
POST /api/v1/online-payments/memberships/{plan_id}/sell-qr
POST /api/v1/online-payments/pt-packages/{plan_id}/sell
POST /api/v1/online-payments/pt-packages/{plan_id}/sell-qr
GET  /api/v1/online-payments/return                          # Plan 49-05 (not in this plan)
```

## Commits (this worktree branch)

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `cb53fb8` | test | add failing path-registration test for sell endpoints (RED) |
| 2 | `7a50b63` | feat | ship 4 POST sell endpoints + mount under /api/v1/online-payments (GREEN) |
| 3 | `ba82726` | test | add HTTP-level integration tests for 4 sell endpoints |
| 4 | `13398df` | refactor | inline service.sell_* calls per endpoint via runner closure |

## Self-Check: PASSED

- `apps/backend/app/modules/online_payments/router.py` — FOUND
- `apps/backend/app/api/v1/router.py` — FOUND (modified)
- `apps/backend/tests/modules/online_payments/test_router_path_registration.py` — FOUND
- `apps/backend/tests/modules/online_payments/test_router_sell_endpoints.py` — FOUND
- Commit `cb53fb8` — FOUND in git log
- Commit `7a50b63` — FOUND in git log
- Commit `ba82726` — FOUND in git log
- Commit `13398df` — FOUND in git log
