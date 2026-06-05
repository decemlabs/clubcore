---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
plan: "03"
subsystem: api
tags: [openapi, contract-freeze, drift-gate, redocly, idempotence, schema-codegen]

# Dependency graph
requires:
  - phase: 81-01
    provides: [GET /client/activity/weekly endpoint]
  - phase: 81-02
    provides: [openapi.json regenerated with Phase 79+80+81 paths, schema.d.ts regenerated]
provides:
  - Frozen v2.2 API contract — openapi.json byte-stable, all 4 client-portal paths present
  - schema.d.ts byte-stable, all new client paths confirmed in TypeScript schema
  - Idempotence proof: second regen pass zero diff on both artifacts
  - CI drift gates green (git diff --exit-code passes on both artifacts)
  - Redocly lint passes on openapi.json
affects: [frontend CI drift gate, backend CI drift gate, v2.2 handoff milestone]

# Tech tracking
tech-stack:
  added: []
  patterns: [byte-stable regen (indent=2, sort_keys=True, ensure_ascii=False + trailing newline), idempotence proof (second pass zero diff), staff-contract-byte-identical assertion]

key-files:
  created: []
  modified:
    - apps/backend/openapi.json (frozen v2.2 contract — already committed by 81-02; idempotent regen confirmed)
    - packages/api-client/src/schema.d.ts (regenerated TypeScript schema — already committed by 81-02; idempotent regen confirmed)

key-decisions:
  - "Both generated artifacts were already committed in 81-02 (Rule 1 fix for pre-existing TS build failures); 81-03 proves idempotence via second regen pass producing zero diff"
  - "Staff contract byte-identical: 81 non-client-portal paths and all info/servers/components sections unchanged vs pre-regen baseline"
  - "Only client-portal paths additive: 27 client-portal paths stable between baseline and regen (no net new, none removed)"

patterns-established:
  - "OpenAPI handoff protocol: capture baseline → regen → diff vs HEAD → assert staff-contract byte-identical → Redocly lint → codegen schema.d.ts → second pass idempotence proof"

requirements-completed: [HND-01]

# Metrics
duration: 5min
completed: 2026-06-03
---

# Phase 81 Plan 03: OpenAPI Handoff Summary

**v2.2 API contract frozen: openapi.json + schema.d.ts byte-stable with all 4 client-portal paths present, staff contract byte-identical, Redocly lint clean, CI drift gates proven green via dual idempotence pass.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-03T17:56:00Z
- **Completed:** 2026-06-03T17:57:00Z
- **Tasks:** 2
- **Files modified:** 0 (artifacts already committed by 81-02; idempotence proof only)

## Accomplishments

- Proved byte-stable idempotence: re-ran both regen commands (`uv run python -m scripts.export_openapi` + `pnpm --filter @clubcore/api-client codegen`); both `git diff --exit-code` commands exit 0
- Verified all 4 required v2.2 client-portal paths present: `/api/v1/client/activity/weekly` (GET), `/api/v1/client/payment-method` (GET+DELETE), `/api/v1/client/payment-method/autopay` (PATCH), `/api/v1/client/booking/{booking_id}/reschedule` (POST)
- Asserted staff contract byte-identical: 81 non-client-portal paths and all info/servers/components sections UNCHANGED vs committed baseline; only 27 client-portal paths present (no additions, no removals in client section either — these were already committed by 81-02)
- Redocly lint: `apps/backend/openapi.json validated in 65ms — Woohoo! Your API description is valid.`
- Confirmed `schema.d.ts` contains `activity/weekly`, `payment-method`, `reschedule` patterns

## Task Commits

No new commits required for this plan — artifacts already committed by 81-02 executor (commit `0575b11b`). The idempotence proof (second regen pass → zero diff) confirms the committed artifacts are canonical and match a fresh regen.

**Plan metadata commit:** (see final commit)

## Files Created/Modified

No files modified — idempotence proof only.

- `apps/backend/openapi.json` — 414773 bytes, 108 paths total (81 staff + 27 client-portal), committed in 81-02
- `packages/api-client/src/schema.d.ts` — contains all 4 new client-portal path types, committed in 81-02

## Decisions Made

- Artifacts were already committed by 81-02 (which regenerated them as Rule 1 fix for pre-existing TS build failures from Phases 79+80). The 81-03 plan's role is to prove idempotence and assert the staff contract invariant — both confirmed.
- Staff-contract-byte-identical proof uses JSON-level comparison of non-client-portal paths and all non-path sections against the pre-regen HEAD baseline.

## Deviations from Plan

None. The plan documented that 81-02 may have already run the regen; it had. Both regen passes produced zero diff, proving idempotence. Redocly lint passed. All success criteria met.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 81 (weekly-activity-pwa-flags-openapi-handoff) COMPLETE — all 3 plans executed
- v2.2 milestone (Membership self-service depth) requirements fully satisfied:
  - WACT-01, WACT-02: weekly activity endpoint + PWA wiring (Plans 01+02)
  - PAYM-05: linkedCard feature flag flipped ON (Plan 02)
  - HND-01: OpenAPI handoff / contract freeze (Plan 03)
- CI drift gates: both `git diff --exit-code` gates provably green
- No blockers for future milestones

---
*Phase: 81-weekly-activity-pwa-flags-openapi-handoff*
*Completed: 2026-06-03*

## Threat Flags

No new threat surface. T-81-11 (staff-path leak) mitigated — staff contract byte-identical confirmed. T-81-12 (hand-edited artifacts) mitigated — both files regenerated by tooling only, idempotence proof via second pass. T-81-13 (malformed spec) mitigated — Redocly lint passes.

## Self-Check: PASSED

Files confirmed:
- apps/backend/openapi.json — FOUND (414773 bytes, `git diff --exit-code` clean)
- packages/api-client/src/schema.d.ts — FOUND (`git diff --exit-code` clean)

Path verification:
- /api/v1/client/activity/weekly — PRESENT (GET)
- /api/v1/client/payment-method — PRESENT (GET, DELETE)
- /api/v1/client/payment-method/autopay — PRESENT (PATCH)
- /api/v1/client/booking/{booking_id}/reschedule — PRESENT (POST)

Staff contract: BYTE-IDENTICAL (81 staff paths + all components sections unchanged)
Redocly lint: PASSED
schema.d.ts patterns: activity/weekly (1), payment-method (4), reschedule (7) — all present
Idempotence: CONFIRMED (second regen pass on both artifacts → zero diff)
