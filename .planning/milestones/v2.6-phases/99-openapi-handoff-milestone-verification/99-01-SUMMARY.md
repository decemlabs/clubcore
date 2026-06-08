---
phase: 99-openapi-handoff-milestone-verification
plan: "01"
subsystem: backend/openapi
tags: [openapi, contract-freeze, referral, handoff, hnd-01, v2.6]
dependency_graph:
  requires: [96-01, 97-01, 98-01, 98-02]
  provides: [byte-stable openapi.json with v2.6 Referral surface]
  affects: [packages/api-client codegen (Plan 02)]
tech_stack:
  added: []
  patterns: [FastAPI OPENAPI_TAGS list, Redocly lint, byte-stable sort_keys export]
key_files:
  created: []
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/modules/referrals/router.py
    - apps/backend/openapi.json
decisions:
  - "D-99-TAG-ORDER: Referral tag inserted after Messaging and before Clients in OPENAPI_TAGS, preserving D-64-TAG-ORDER (Client-Portal → Messaging → Referral → CRM staff block)"
  - "D-99-DRIFT-REF: Staff drift gate verified vs 9b28ba2f (Phase 95-01 final regen — last frozen contract before v2.6) using three-prefix exclusion: /api/v1/client + /api/v1/i/ + /api/v1/referral"
  - "D-99-NO-WS: v2.6 referral endpoints are ordinary FastAPI HTTP routes — no manual path injection needed in _customize_openapi() (unlike v2.5 WS endpoint)"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-06-08"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 99 Plan 01: OpenAPI Handoff — Freeze v2.6 Referral Surface Summary

**One-liner:** Referral tag registered in OPENAPI_TAGS (after Messaging, before Clients); client_router retagged from Client-Portal to Referral; all six v2.6 referral path×method combos present and Referral-tagged; openapi.json byte-stable (484421 bytes) and Redocly-clean; staff drift gate green vs 9b28ba2f.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add Referral tag to OPENAPI_TAGS + retag client_router | 4cc16d81 | app/main.py, referrals/router.py |
| 2 | Regenerate byte-stably, prove all six paths present, staff drift gate green, Redocly clean | c557ecd8 | openapi.json |

## What Was Built

### Task 1 — Referral Tag + Router Retag

- Appended `"Referral"` entry to `OPENAPI_TAGS` immediately after `"Messaging"` and before `"Clients"` (D-64-TAG-ORDER preserved: Client-Portal → Messaging → Referral → CRM staff block)
- Description: «Приведи друга» referral programme — personal codes + deep-links, public resolver, capture/binding at onboarding, bilateral loyalty-ledger bonus on first purchase, owner-only bonus-config API; Phases 96-98 REFER-01..07
- Changed `client_router = APIRouter(tags=["Client-Portal"])` → `APIRouter(tags=["Referral"])` in `referrals/router.py` (line 83)
- `public_router` (line 51) and `owner_router` (line 160) already carried `tags=["Referral"]` — left unchanged
- Zero `Client-Portal` literals remain in `referrals/router.py`; all three APIRouter declarations now carry `tags=["Referral"]`
- No per-route tag overrides existed in this file — only the three router declarations carry tags
- No other routers, spec metadata (title/version/description), or non-referral files touched

### Task 2 — Byte-Stable Regen + Verification Gates

- Regenerated from `apps/backend/`: `ENVIRONMENT=dev uv run python -m scripts.export_openapi`
- Output: 484421 bytes (up from 469126 bytes in v2.5 baseline — the additive referral surface)

**Byte-stability:** Second consecutive run → `diff /tmp/openapi_run1.json openapi.json` empty. Confirmed idempotent.

**All six referral path×method combos present and Referral-tagged:**

| Path | Method | operation_id | Tag |
|------|--------|-------------|-----|
| `/api/v1/i/{code}` | GET | `public_resolve_referral_code` | Referral |
| `/api/v1/client/referral/code` | GET | `client_get_referral_code` | Referral |
| `/api/v1/client/referral/summary` | GET | `client_get_referral_summary` | Referral |
| `/api/v1/client/referral/capture` | POST | `client_capture_referral` | Referral |
| `/api/v1/referral/config` | GET | `owner_get_referral_config` | Referral |
| `/api/v1/referral/config` | PUT | `owner_update_referral_config` | Referral |

**Staff drift gate (CISO-01 byte-parity):** Staff-path subset (every `/api/v1/...` path that is NOT under `/api/v1/client` AND NOT `/api/v1/i/` AND NOT `/api/v1/referral`) byte-identical to `9b28ba2f` (Phase 95-01 final authoritative regen). Three-prefix exclusion required because `/api/v1/referral/config` is an owner-only staff path outside `/api/v1/client` — the Phase 95 single-prefix exclusion would have falsely flagged it (D-99-DRIFT-REF). DRIFT-GATE-OK: zero diff. v2.6 adds ONLY the referral client/owner/public surface.

**Redocly lint:** exits 0. One expected warning (`operation-2xx-response` on the WS endpoint `client_ws_messages` — that endpoint uses HTTP 101, not 2xx; carried from v2.5 and expected per redocly.yaml ruleset). No errors.

**No manual path injection needed:** All six referral endpoints are ordinary FastAPI HTTP routes that auto-emit into `schema["paths"]`. The `_customize_openapi()` post-processor was not modified (D-99-NO-WS — unlike Phase 95 which required manual WS injection).

## Deviations from Plan

None — plan executed exactly as written.

The plan correctly anticipated the three-prefix exclusion for the drift gate (`/api/v1/client + /api/v1/i/ + /api/v1/referral`) to handle the owner-only `/api/v1/referral/config` path.

## Known Stubs

None. All six referral endpoints are fully wired to implementation. The `openapi.json` contains real schema definitions for all request/response types (not placeholders).

## Threat Flags

None. No new staff-side endpoints introduced beyond those documented in the plan's threat model. The staff drift gate green confirms CISO-01 byte-parity.

## Self-Check: PASSED

- [x] `apps/backend/app/main.py` modified: `"Referral"` entry in OPENAPI_TAGS after "Messaging", before "Clients"
- [x] `apps/backend/app/modules/referrals/router.py` modified: zero `Client-Portal` literals, three `Referral` tag declarations
- [x] `apps/backend/openapi.json` regenerated (484421 bytes, byte-stable)
- [x] Commit 4cc16d81 exists: `feat(99-01): add Referral tag to OPENAPI_TAGS + retag client_router`
- [x] Commit c557ecd8 exists: `feat(99-01): regenerate byte-stable openapi.json with v2.6 Referral surface`
- [x] All six referral path×method combos present and tagged `["Referral"]`
- [x] Consecutive regen runs byte-identical
- [x] Staff drift gate green vs 9b28ba2f (CISO-01 byte-parity)
- [x] Redocly lint exits 0 (1 expected warning, 0 errors)
