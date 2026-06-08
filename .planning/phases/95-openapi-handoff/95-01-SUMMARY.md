---
phase: 95-openapi-handoff
plan: "01"
subsystem: backend/openapi
tags: [openapi, contract-freeze, messaging, handoff, hnd-01]
dependency_graph:
  requires: [90-01, 91-01, 92-01, 93-01, 94-01, 94-02]
  provides: [byte-stable openapi.json with v2.5 Messaging surface]
  affects: [packages/api-client codegen (Plan 02)]
tech_stack:
  added: []
  patterns: [FastAPI _customize_openapi post-processor, manual WS path injection, Redocly lint]
key_files:
  created: []
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/modules/messaging/router.py
    - apps/backend/openapi.json
decisions:
  - "D-95-WS-DOC: WS endpoint documented as GET (HTTP→WS upgrade) in _customize_openapi() — cookieAuth-only security override (no CSRF header possible on WS handshake)"
  - "D-95-DRIFT-REF: Drift gate verified vs Phase 89 baseline (fedb3e55) rather than contract-freeze-v1.11.0 (Phase 64 tag predates phases 86-89 GYM/notifications/trainer additions)"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-06-08"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 95 Plan 01: OpenAPI Handoff — Freeze v2.5 Messaging Surface Summary

**One-liner:** Messaging tag registered + five v2.5 REST paths retagged + WS endpoint manually documented via cookieAuth-only `_customize_openapi()` injection; openapi.json byte-stable and Redocly-clean.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add Messaging tag + retag five messaging REST routes | 9e45aa58 | app/main.py, messaging/router.py |
| 2 | Inject manual WS endpoint doc into _customize_openapi() + regen | 9b28ba2f | app/main.py, openapi.json |
| 3 | Byte-stability + staff drift gate + Redocly lint — verification only | (no diff) | — |

## What Was Built

### Task 1 — Messaging Tag + Router Retag
- Appended `"Messaging"` entry to `OPENAPI_TAGS` immediately after `"Client-Portal"` (D-64-TAG-ORDER preserved)
- Description names: real-time client↔gym 1:1 chat, Phases 90-94, requirements MSG/RT/RCPT/ATT/PWA
- Changed `APIRouter(tags=["Client-Portal"])` → `tags=["Messaging"]` in `messaging/router.py`
- Changed two per-route explicit `tags=["Client-Portal"]` overrides (`client_upload_attachment`, `client_serve_attachment`) → `"Messaging"`
- Zero `"Client-Portal"` literals remain in `messaging/router.py`; no other routers or spec metadata touched

### Task 2 — Manual WS Endpoint Documentation
- Injected `schema["paths"]["/api/v1/client/ws/messages"]` as a `get` operation in `_customize_openapi()` post-processor (Phase 95 HND-01 / D-95-WS-DOC)
- `operationId: client_ws_messages`, `tags: ["Messaging"]`
- `responses: {"101": {"description": "Switching Protocols — WebSocket connection established."}}`
- `security: [{"cookieAuth": []}]` — overrides global `cookieAuth+csrfHeader` default since WS handshake cannot carry `X-CSRF-Token` header; matches live endpoint (no `verify_client_csrf` dependency)
- Description captures full RT-01..04 contract: auth model, CSWSH guard, channel derivation, server→client frames, reconnect catch-up cursor
- Injection is idempotent (dict literal assigned; `sort_keys=True` in JSON serialisation normalises output)
- Regenerated `openapi.json` (469126 bytes)

### Task 3 — Verification (all gates green)
- **Byte-stability:** Second regen run → `git diff --exit-code` empty (confirmed idempotent)
- **All paths present:** `/api/v1/client/messages`, `/api/v1/client/messages/read`, `/api/v1/client/messages/attachments`, `/api/v1/client/messages/attachments/{attachment_id}`, `/api/v1/client/ws/messages` — all under Messaging tag
- **Staff drift gate:** Non-client paths byte-identical to Phase 89 baseline (`fedb3e55` — last openapi.json regen before Phase 95); v2.5 additions are exclusively client-side
- **Redocly lint:** exits 0; one warning (operation-2xx-response on WS endpoint is expected — WS uses 101, not 2xx); no errors

## Deviations from Plan

### Auto-documented Issue (Reference Tag Correction)

**[Pre-existing state — not a code deviation]**

The plan specifies the drift gate comparison as: `diff ... contract-freeze-v1.11.0 ...`. That tag was created at Phase 64 (the initial contract freeze), which predates Phases 86-89 that added GYM (`/api/v1/gym`), Notifications, and Trainer Detail paths to the staff surface. Comparing against `contract-freeze-v1.11.0` would always fail due to these legitimate v2.4 additions.

- **What was verified instead:** Staff-path subset (non-`/api/v1/client`) byte-identical to `fedb3e55` (Phase 89 final openapi.json regen — the actual last-known-good staff contract before Phase 95).
- **Result:** DRIFT-GATE-OK — zero diff. v2.5 added ONLY the six client messaging paths (`/client/messages*` + `/client/ws/messages`).
- **Impact:** The intent of the drift gate is fully satisfied. The tag reference in the plan was stale.

## Known Stubs

None. All messaging paths are fully wired to implementation (not placeholders).

## Threat Flags

None. No new staff-side endpoints introduced. WS security override (cookieAuth-only) correctly matches the live endpoint's auth model.

## Self-Check: PASSED

- [x] `apps/backend/app/main.py` modified (Messaging tag in OPENAPI_TAGS + WS injection)
- [x] `apps/backend/app/modules/messaging/router.py` modified (zero Client-Portal literals)
- [x] `apps/backend/openapi.json` regenerated (469126 bytes, byte-stable)
- [x] Commit 9e45aa58 exists: `feat(95-01): add Messaging tag to OPENAPI_TAGS + retag messaging routes`
- [x] Commit 9b28ba2f exists: `feat(95-01): inject manual WS endpoint doc into _customize_openapi() + regen openapi.json`
- [x] Redocly lint exits 0
- [x] Staff drift gate green vs Phase 89 baseline
