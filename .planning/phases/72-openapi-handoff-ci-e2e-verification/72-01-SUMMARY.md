---
phase: 72-openapi-handoff-ci-e2e-verification
plan: "01"
subsystem: backend/openapi
tags: [openapi, client-portal, tag-unification, drift-gate, HND-01, VER-03]
dependency_graph:
  requires: []
  provides: [unified-client-portal-tag, regenerated-openapi-json]
  affects: [packages/api-client/src/schema.d.ts, openapi handoff]
tech_stack:
  added: []
  patterns: [OPENAPI_TAGS ordering, D-64-TAG-INTERNAL, export_openapi byte-stable regen]
key_files:
  created: []
  modified:
    - apps/backend/app/modules/client_auth/router.py
    - apps/backend/app/main.py
    - apps/backend/openapi.json
decisions:
  - "D-72-01 default applied: unified single Client-Portal tag (no two-tag fallback needed)"
  - "EN dash -> hyphen fix in tag description (ruff RUF001)"
metrics:
  duration: ~5min
  completed: "2026-05-31"
  tasks_completed: 2
  files_modified: 3
---

# Phase 72 Plan 01: Unify Client-Portal Tag and Regenerate OpenAPI Spec Summary

**One-liner:** Unified all 23 client operations under a single `Client-Portal` tag by re-tagging `client_auth` router from `"Client"` to `"Client-Portal"`, renaming the `OPENAPI_TAGS` entry, and regenerating `openapi.json` byte-stably with zero staff path deletions/modifications.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Unify client paths under the Client-Portal tag | cbcd2ed0 | client_auth/router.py, main.py |
| 1 (fix) | Replace EN dash with hyphen in tag description | d9909ad7 | main.py |
| 2 | Regenerate openapi.json with unified tag | 059612de | openapi.json |
| 2 (fix) | Sync openapi.json with description fix | 804b896e | openapi.json |

## Implementation Notes

### Tag Scheme Used (D-72-01)

**Default: unified single `Client-Portal` tag.** The two-tag fallback was not needed.

- `apps/backend/app/modules/client_auth/router.py` L51: changed `tags=["Client"]` → `tags=["Client-Portal"]`
- `apps/backend/app/main.py` OPENAPI_TAGS: renamed the `"Client"` dict entry to `"Client-Portal"` and updated the description to cover all v2.0 surfaces (Phases 68-71)
- Position: `Client-Portal` sits between `Users` and `Clients` in the ordered tag list — business-domain section with `Internal` correctly last (D-64-TAG-INTERNAL honored)

### Staff-Path Additions-Only Assertion (HND-01 / VER-03)

Semantic diff of `paths` section vs `contract-freeze-v1.11.0`:

- **Staff paths deleted:** 0
- **Staff paths modified by our task (72-01):** 0
- **Client paths modified by our task:** 7 (the client_auth endpoints re-tagged from "Client" to "Client-Portal" — documentation change only, zero handler/auth changes)
- **New client paths added:** 22 (Phases 69-71 additions, pre-existing in code before this plan)

Note: `git diff contract-freeze-v1.11.0` shows ~27 staff paths with content changes, but those are pre-existing phase 66-71 evolution (idempotency key additions, description updates) — not caused by 72-01. This plan's two commits touch zero staff path objects.

### Byte-Stable Regen Confirmation (T-72-03)

Consecutive `uv run python -m scripts.export_openapi` runs from `apps/backend/` produce identical bytes. `git diff --exit-code -- apps/backend/openapi.json` exits 0 after the committed file is re-exported.

### 23 Client Operations Confirmed

All 23 `client_` operationIds present in regenerated `openapi.json`:
- **Auth (Phase 68, 6 ops):** `client_otp_request`, `client_otp_verify`, `client_session_refresh`, `client_session_logout`, `client_get_me`, `client_patch_me`
- **Read (Phase 69, 9 ops):** `client_get_membership`, `client_get_home`, `client_list_bookings`, `client_list_visit_history`, `client_list_pt_session_history`, `client_list_payment_history`, `client_list_plans`, `client_list_pt_packages`, `client_list_trainers`
- **Bookings/QR (Phase 70, 5 ops):** `client_create_booking`, `client_cancel_booking`, `client_list_slots`, `client_get_qr_token`, `client_check_in`
- **Checkout (Phase 71, 3 ops):** `client_checkout_membership`, `client_checkout_pt_package`, `client_get_payment_status`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed EN dash RUF001 linting error in Client-Portal description**
- **Found during:** Task 2 verification (`uv run ruff check app`)
- **Issue:** The pattern in `72-PATTERNS.md` used a Unicode EN dash `–` (U+2013) in `"Phases 68–71"` which triggered `ruff` RUF001 (ambiguous character)
- **Fix:** Changed to a hyphen-minus `"Phases 68-71"` in `app/main.py` and re-exported `openapi.json`
- **Files modified:** `apps/backend/app/main.py`, `apps/backend/openapi.json`
- **Commits:** d9909ad7, 804b896e

**Note:** Pre-existing `E501` in `apps/backend/app/integrations/yookassa/client.py:178` (line too long) is out of scope — not caused by this plan.

## Verification Results

- `uv run mypy --strict app`: Success (221 source files, 0 issues)
- `uv run ruff check app/main.py`: All checks passed
- `uv run lint-imports`: 3 contracts kept, 0 broken (1 pre-existing warning)
- 23 `client_` operationIds confirmed in `openapi.json`
- `Client-Portal` in top-level `tags` array, positioned between `Users` and `Clients`
- No standalone `"Client"` tag in spec
- Byte-stable: consecutive exports produce identical output

## Known Stubs

None — this plan is documentation/curation only; no new business logic or data flows.

## Threat Flags

None — the re-tag changes only the OpenAPI documentation metadata. Auth dependencies (`require_client`, CSRF) in `client_auth/router.py` are untouched. The drift gate confirms no staff path contract was altered by this plan.

## Self-Check: PASSED

- `apps/backend/app/modules/client_auth/router.py` — confirmed `tags=["Client-Portal"]`
- `apps/backend/app/main.py` — confirmed single `"Client-Portal"` entry, no `"Client"` entry
- `apps/backend/openapi.json` — confirmed 23 client ops, Client-Portal tag present
- Commits cbcd2ed0, 059612de, d9909ad7, 804b896e — all present in git log
