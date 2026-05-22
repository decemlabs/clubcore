---
phase: 49-online-sales-orchestrator
plan: 05
subsystem: online_payments
tags: [pay-07, anti-oracle, constant-time, anonymous, return-url, yookassa]
dependency-graph:
  requires:
    - 49-04  # router.py shape with existing POST sell endpoints
  provides:
    - "GET /api/v1/online-payments/return (anonymous return-URL screen)"
    - "EXCLUDED_PATHS exemption for /api/v1/online-payments/return"
  affects:
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/tests/integration/test_route_introspection.py
    - apps/backend/tests/modules/online_payments/test_return_screen.py
tech-stack:
  added: []
  patterns:
    - "Constant-time floor (perf_counter + asyncio.sleep) — anti-oracle uniformity"
    - "Static HTML Response with explicit Cache-Control: no-store"
    - "include_in_schema=False for browser-target URLs"
key-files:
  created:
    - apps/backend/tests/modules/online_payments/test_return_screen.py
  modified:
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/tests/integration/test_route_introspection.py
decisions:
  - "D-49-17 — discard query params; static HTML body identical across all inputs"
  - "D-49-18 / W3 — constant-time floor raised from 50 ms to 60 ms (CI-jitter headroom)"
  - "D-49-26 — anonymous-by-design; registered in EXCLUDED_PATHS"
  - "W3 — test tolerance relaxed to min_elapsed >= 0.040 (20 ms below 60 ms floor)"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-22T12:14:05Z"
  tasks: 2
  files_changed: 3
  commits: 2
requirements:
  - PAY-07
---

# Phase 49 Plan 05: Anti-oracle Return Screen + Constant-time Floor Summary

Ship `GET /api/v1/online-payments/return` — pure-static HTML anti-oracle return screen with a 60 ms constant-time floor (W3 — bumped from D-49-18's 50 ms for CI-jitter headroom), `Cache-Control: no-store, max-age=0`, anonymous-by-design (no auth, no CSRF, no DB), and a 6-test HTTP suite proving byte-identical responses across diverse query-param shapes plus an empirically-verified timing floor.

## What Was Built

### Task 1 — Append GET /return handler + EXCLUDED_PATHS exemption (commit `af3a890`)

`apps/backend/app/modules/online_payments/router.py`:
- Added `import asyncio`, `import time`, `Final` to imports.
- Added file-level constants:
  - `_RETURN_HTML: Final[str]` — static Russian HTML body containing "Оплата получена" and "Ожидаем подтверждение от платёжной системы".
  - `_RETURN_FLOOR_SECONDS: Final[float] = 0.060` — constant-time floor (W3 — 60 ms; D-49-18 originally specified 50 ms).
- Appended the handler at the end of the file:

```python
@router.get(
    "/return",
    include_in_schema=False,  # PAY-07 — not documented; browser-target URL
)
async def online_payment_return() -> Response:
    start = time.perf_counter()
    response = Response(
        content=_RETURN_HTML,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
    elapsed = time.perf_counter() - start
    await asyncio.sleep(max(0.0, _RETURN_FLOOR_SECONDS - elapsed))
    return response
```

The 4 existing POST sell endpoints from 49-04 (membership×{redirect,qr}, pt-package×{redirect,qr}) are UNTOUCHED — additive change only.

`apps/backend/tests/integration/test_route_introspection.py`:
- Added `/api/v1/online-payments/return` to `EXCLUDED_PATHS` with a 4-line rationale comment citing D-49-26 and explicitly warning future modifiers not to add any DB lookup or query-param branching.

### Task 2 — HTTP tests proving anti-oracle + constant-time floor (commit `6d66751`)

`apps/backend/tests/modules/online_payments/test_return_screen.py` — 6 test functions:

1. `test_return_screen_200_anonymous` — no cookies / CSRF / Idempotency-Key → 200 with "Ожидаем подтверждение" in body.
2. `test_return_screen_body_identical_across_query_shapes` — 4 query-param variations (incl. attacker probing `?status=succeeded`) produce byte-identical response bodies (single-element set).
3. `test_return_screen_no_status_leakage` — body lower-cased MUST NOT contain `succeeded`/`pending`/`canceled`/`failed`/`статус`/`status`/`amount`/`сумма`; body MUST NOT match UUID regex.
4. `test_return_screen_cache_control_no_store` — `cache-control` header contains both `no-store` AND `max-age=0`.
5. `test_return_screen_content_type_html` — `content-type` starts with `text/html`.
6. `test_return_screen_constant_time_floor` — N=10 measurements; `min_elapsed >= 0.040` (W3 — 20 ms tolerance below 60 ms floor).

## Timing-floor measurement (sanity check on W3 60 ms / 40 ms tolerance)

Captured a one-off N=10 sample over the ASGI transport on the developer machine (after a warmup request to amortize first-request lazy-init):

| Metric | Value (ms) |
|--------|------------|
| Minimum | 61.36 |
| Median  | 61.85 |
| Maximum | 62.27 |

All 10 samples sit in a 0.91 ms band just above the 60 ms floor, with healthy 21+ ms headroom above the 40 ms test assertion. The floor is empirically tight (no over-sleep) and the test tolerance gives ample room for CI scheduler jitter without false positives. ✅

## EXCLUDED_PATHS exemption (Roadmap success-criterion #4 — anti-oracle)

The introspection test's `EXCLUDED_PATHS` now contains `/api/v1/online-payments/return`. Verification:

- The new path appears in `sorted(EXCLUDED_PATHS)` (confirmed via the failure message from the pre-existing `test_every_protected_route_declares_a_gate` failure — see Pre-existing Issues below).
- The sanity-belt tests `test_excluded_paths_set_is_locked` and `test_gate_prefixes_match_factory_names` still pass — `pytest tests/integration/test_route_introspection.py::test_excluded_paths_set_is_locked tests/integration/test_route_introspection.py::test_gate_prefixes_match_factory_names` → 2 passed in 0.01s.

## W3 acceptance criteria

| Criterion | Status |
|-----------|--------|
| `_RETURN_FLOOR_SECONDS: Final[float] = 0.060` | ✅ exactly 1 match |
| `min_elapsed >= 0.040` in test | ✅ exactly 1 match |
| Floor empirically holds at ≥40 ms over N=10 | ✅ min observed = 61.36 ms |
| Existing POST sell endpoints untouched | ✅ verified by diff (additive-only) |
| Russian "Оплата получена" + "Ожидаем подтверждение" in HTML | ✅ both present |
| `Cache-Control: no-store, max-age=0` | ✅ in response headers |
| No `Depends` on `/return` handler | ✅ verified (grep) |
| `include_in_schema=False` on `/return` | ✅ exactly 1 match |

## Verification Output

- `cd apps/backend && uv run pytest tests/modules/online_payments/test_return_screen.py -x -q` → **6 passed in 2.22s** ✅
- `cd apps/backend && uv run ruff check app/modules/online_payments/router.py tests/modules/online_payments/test_return_screen.py` → all checks passed ✅
- `cd apps/backend && uv run python -c "from app.modules.online_payments.router import router, _RETURN_FLOOR_SECONDS; assert _RETURN_FLOOR_SECONDS == 0.060; ..."` → `[(['GET'], '/return')]` ✅

## Decisions Made

- **W3 (60 ms / 40 ms tolerance)** — accepted as written in the plan. The original D-49-18 50 ms floor + 5 ms tolerance was a documented flakiness risk; the W3 revision is empirically safer with negligible UX cost (60 ms is well below the 100 ms human perception threshold).
- **No helper extraction** — the constant-time floor is embedded inline (start / response / elapsed / asyncio.sleep) per plan guidance: Phase 49 has exactly one callsite. Phase 50+ should extract to a shared helper if additional callsites are added.
- **Additive-only router.py edit** — no overlap risk with 49-06 (verified 49-06 plan `files_modified:` lists app/main.py + app/workers/__init__.py only; no router.py).

## Deviations from Plan

None — plan executed exactly as written. The W3 floor bump (60 ms) and tolerance relaxation (40 ms) were specified in the plan itself.

## Pre-existing Issues (out of scope; logged to deferred-items.md)

These pre-exist on the base commit `fccf941` and were NOT touched by Plan 49-05. Confirmed by `git stash && ruff check / mypy / pytest && git stash pop`.

1. **`ruff E501` in `tests/integration/test_route_introspection.py:35`** — `/api/v1/auth/otp/request` comment line is 108 chars (>100). Not modified by this plan.
2. **4 mypy errors in `app/modules/online_payments/router.py`** — `confirmation_type: str` vs `Literal['redirect', 'qr']` mismatch on lines 208/257/303/346 (shifted from base 185/234/280/323 due to my additive lines). Originate from Plan 49-04 (not touched by 49-05). The new `/return` handler introduces **zero** new mypy errors.
3. **`test_every_protected_route_declares_a_gate` test failure** — fails on `/api/v1/auth/password-reset/{request,confirm}` and `/api/v1/users/invitations/accept`. My `EXCLUDED_PATHS` addition for `/api/v1/online-payments/return` works correctly: the new path does NOT appear in the failure list. The sanity-belt tests in the same file pass.

## Files Changed

| File | Type | LOC delta |
|------|------|-----------|
| `apps/backend/app/modules/online_payments/router.py` | modified | +43 |
| `apps/backend/tests/integration/test_route_introspection.py` | modified | +5 |
| `apps/backend/tests/modules/online_payments/test_return_screen.py` | created | +107 |

## Commits

| Hash | Type | Summary |
|------|------|---------|
| `af3a890` | feat | add anonymous GET /return handler with 60ms constant-time floor |
| `6d66751` | test | add anti-oracle return-screen tests with 40ms floor tolerance |

## Self-Check: PASSED

- File `apps/backend/app/modules/online_payments/router.py` exists ✅
- File `apps/backend/tests/integration/test_route_introspection.py` exists ✅
- File `apps/backend/tests/modules/online_payments/test_return_screen.py` exists ✅
- Commit `af3a890` exists ✅
- Commit `6d66751` exists ✅
- 6 tests pass ✅
- W3 floor + tolerance committed (60 ms / 40 ms) ✅
- EXCLUDED_PATHS exemption registered ✅
