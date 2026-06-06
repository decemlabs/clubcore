---
phase: 89-openapi-handoff-milestone-verification
plan: "01"
subsystem: contract
tags: [openapi, codegen, contract-freeze, milestone-gate, v2.4]
dependency_graph:
  requires:
    - "Phase 86: gym-info backend (GYM-01, GYM-02)"
    - "Phase 87: notification inbox backend (INBOX-01, INBOX-02, INBOX-04)"
    - "Phase 88: trainer detail backend (TRNR-01, TRNR-02)"
  provides:
    - "HND-01: byte-stable openapi.json + schema.d.ts (v2.4 paths frozen)"
    - "_v24Checks AssertNonNever forward-guards (8 paths guarded)"
    - "v2.4 milestone gate: green"
  affects:
    - "packages/api-client/src/schema.d.ts (downstream PWA consumer)"
    - ".github/workflows/ci.yml drift gates (both now clean)"
tech_stack:
  added: []
  patterns:
    - "AssertNonNever forward-guards (_v24Checks) in schema.contract.test.ts"
    - "Byte-stable openapi.json regen: json.dumps(sort_keys=True, indent=2) + trailing newline"
    - "CISO-01 no-edit guard: can.ts/registry.ts byte-identical to baseline except additive gym RBAC"
key_files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts
    - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
decisions:
  - "photoUrl (camelCase) is the correct field name in TrainerUpdateRequest — Pydantic alias_generator renders it as camelCase in the spec; the plan's 'photo_url' refers to the Pydantic model field name, not the JSON property key"
  - "CISO-01 guard: 3 lines changed across can.ts/registry.ts/permissions.py — all additive gym RBAC entries (Phase 86 GYM-02); no existing entry modified"
  - "Rule 1 auto-fix: HomeScreen.identity.test.jsx vi.mock('@/data') missing useClientNotifications (Phase 87 addition); added to mock factory + beforeEach safe default"
metrics:
  duration: "~45 minutes"
  completed_date: "2026-06-06"
  tasks_completed: 3
  files_modified: 4
---

# Phase 89 Plan 01: OpenAPI Handoff + Milestone Verification Summary

**One-liner:** Byte-stable v2.4 contract freeze — 7 new paths regenerated into openapi.json + schema.d.ts, 8-entry `_v24Checks` AssertNonNever forward-guards added, full milestone gate green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Authoritative v2.4 regen openapi.json + schema.d.ts | fedb3e55 | apps/backend/openapi.json, packages/api-client/src/schema.d.ts |
| 2 | Add _v24Checks forward-guards + runtime toHaveLength(8) | 9870e883 | packages/api-client/src/schema.contract.test.ts |
| 3 (milestone gate) | Full gate run + drift/Redocly/no-edit verification | 8f3bea41 (Rule 1 fix) | apps/client-pwa/src/screens/HomeScreen.identity.test.jsx |

## Milestone Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| Drift gate: `git diff --exit-code apps/backend/openapi.json` | **PASS** | Second regen = zero diff (byte-stable) |
| Drift gate: `git diff --exit-code packages/api-client/src/schema.d.ts` | **PASS** | Second regen = zero diff (byte-stable) |
| Redocly lint: `npx @redocly/cli@latest lint apps/backend/openapi.json` | **PASS** | "Your API description is valid" |
| backend pytest (new v2.4 tests) | **PASS** | 2654 passed, 8 skipped |
| backend pytest (failures) | **PRE-EXISTING** | 1 failed (test_freeze_race), 7 errors (promo F821) — see below |
| mypy --strict app | **PASS** | "no issues found in 253 source files" |
| lint-imports | **PASS** | 3 contracts kept, 0 broken |
| PWA typecheck (client-pwa tsc) | **PASS** | Zero errors |
| PWA vitest (client-pwa 175 tests) | **PASS** | 175/175, 25/25 test files |
| api-client contract vitest (11 tests) | **PASS** | 11/11 (10 prior + 1 new _v24Checks it-block) |
| CISO-01 no-edit guard (can.ts) | **PASS** | Only additive `{ action: 'edit', resource: 'gym' }` line — Phase 86 GYM-02 |
| CISO-01 no-edit guard (registry.ts) | **PASS** | Only additive `\| 'gym'` Resource type — Phase 86 GYM-02 |
| CISO-01 no-edit guard (permissions.py) | **PASS** | Only additive `Resource.GYM` enum entry + `(Action.EDIT, Resource.GYM)` — Phase 86 GYM-02 |

### Pre-Existing Known Failures (NOT v2.4 regressions)

These failures are documented in STATE.md `## Deferred Items` and were present before v2.4:

1. **test_freeze_race** (`tests/integration/memberships/test_freeze_race.py::test_concurrent_freeze_race_serialised_by_partial_unique_index`) — flaky timing-dependent test: concurrent 409 reason-code distribution varies between `invalid_transition` and `already_frozen`. Pre-existing since v2.0. No fix attempted.

2. **promo F821 collection errors** (7 errors in `tests/test_client_promo_validate.py`) — `promo_codes/service.py` uses F821 undefined names; tests fail at collection time. Pre-existing since v2.0 promo module incomplete stub. No fix attempted.

3. **test_alembic_clean** — `app.modules.promo_codes.models` not registered in `alembic/env.py`; pre-existing since v2.0 (commit b61054f4). Not run in this gate (would fail at collection). No fix attempted.

No pre-existing debt was modified or worsened by v2.4 work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed HomeScreen identity test mock missing useClientNotifications**

- **Found during:** Task 3 (PWA vitest gate)
- **Issue:** Phase 87 added `useClientNotifications` import to `HomeScreen.jsx` for notification badge count. The `vi.mock('@/data', ...)` factory in `HomeScreen.identity.test.jsx` did not include this export, causing all 7 identity tests to fail with: `Error: [vitest] No "useClientNotifications" export is defined on the "@/data" mock`.
- **Fix:** Added `useClientNotifications` to vi.mock factory + `beforeEach` safe default (`{ data: { items: [], total: 0 } }`).
- **Files modified:** `apps/client-pwa/src/screens/HomeScreen.identity.test.jsx`
- **Commit:** 8f3bea41

### Plan Notes

- The plan described the TrainerUpdateRequest additive field as `photo_url` (Python snake_case). In the generated openapi.json and schema.d.ts, the field is `photoUrl` (camelCase, Pydantic alias_generator). The `_TrainerPatchBodyRealised` guard covers the entire requestBody (not a specific field) so it correctly guards the bio/specialization/photoUrl addition regardless of naming. The guard is correct as written.

## v2.4 New Contract Surface (Frozen)

| Path | Method | Phase | operationId |
|------|--------|-------|-------------|
| /api/v1/client/gym | GET | 86 GYM-01 | client_get_gym_info |
| /api/v1/gym | PUT | 86 GYM-02 | owner_update_gym_info |
| /api/v1/client/notifications | GET | 87 INBOX-01 | client_list_notifications |
| /api/v1/client/notifications/{notification_id}/read | PATCH | 87 INBOX-02 | client_mark_notification_read |
| /api/v1/client/notifications/read-all | PATCH | 87 INBOX-02 | client_mark_all_notifications_read |
| /api/v1/client/push-tokens | POST | 87 INBOX-04 | client_register_push_token |
| /api/v1/client/trainers/{trainer_id} | GET | 88 TRNR-01 | client_get_trainer |
| /api/v1/trainers/{trainer_id} (existing) | PATCH requestBody | 88 TRNR-02 | Additive bio/specialization/photoUrl on TrainerUpdateRequest |

## Byte-Stability Proof

Second regen (after commit fedb3e55) produced:

```
Wrote apps/backend/openapi.json (448343 bytes).
openapi-typescript 7.13.0: ../../apps/backend/openapi.json → src/schema.d.ts [130.1ms]
git diff --exit-code apps/backend/openapi.json  → exit 0
git diff --exit-code packages/api-client/src/schema.d.ts  → exit 0
```

Both artifacts are byte-stable (deterministic export per D-06: `json.dumps(sort_keys=True, indent=2, ensure_ascii=False)` + trailing newline).

## CISO-01 No-Edit Guard Summary

Files checked against `contract-freeze-v1.11.0`:

- `apps/admin-web/src/shared/session/can.ts`: +2 lines — additive `{ action: 'edit', resource: 'gym' }` (Phase 86 GYM-02). No existing entry modified.
- `apps/admin-web/src/shared/session/registry.ts`: +1 line — additive `| 'gym'` to Resource type (Phase 86 GYM-02). No existing type modified.
- `apps/backend/app/core/permissions.py`: +4 lines — additive `Resource.GYM = "gym"` enum value + `(Action.EDIT, Resource.GYM)` OWNER_ONLY entry + comment update (Phase 86 GYM-02). No existing permission modified.

The gym RBAC addition is the SOLE expected v2.4 RBAC delta. No other drift detected.

## Known Stubs

None. All new v2.4 paths are fully implemented (Phases 86-88) and now reflected in the authoritative contract.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced by this plan. This plan only regenerates and freezes the contract. The threat surface is covered by T-89-01 through T-89-SC in the plan's threat model — all mitigations confirmed applied.

## Self-Check: PASSED

- apps/backend/openapi.json: FOUND
- packages/api-client/src/schema.d.ts: FOUND
- packages/api-client/src/schema.contract.test.ts: FOUND
- apps/client-pwa/src/screens/HomeScreen.identity.test.jsx: FOUND
- Commit fedb3e55 (regen): FOUND
- Commit 9870e883 (_v24Checks): FOUND
- Commit 8f3bea41 (Rule 1 fix): FOUND
