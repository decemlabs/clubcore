---
phase: 28
plan: "04"
subsystem: admin-web/http-service
tags: [http, adapter, freeze, renew, status-filter]
requirements: [FE-10, FE-11, FE-12]

dependency_graph:
  requires:
    - 28-01 (regenerated schema.d.ts — typed paths for freeze/unfreeze/renew)
    - 28-02 (MembershipsService contract with freeze/unfreeze/renew signatures)
  provides:
    - HTTP impl of freeze/unfreeze/renew against real backend transport
    - status query param forwarding in list()
    - responseToMembership mapping all 5 new MembershipResponse fields
  affects:
    - 28-05 (hooks that call memberships.freeze/unfreeze/renew via swap seam)
    - 28-06 (UI components using Membership with freeze fields)

tech_stack:
  added: []
  patterns:
    - "if (query.status) q.status = query.status — status filter forwarding analogous to clientId/expiring"
    - "responseToMembership — direct field assignment from camelCase wire format per BackendSchemaBase"
    - "FreezePeriod mapping via intermediate variable (fp) with null guard"

key_files:
  created: []
  modified:
    - apps/admin-web/src/shared/api/services/http/memberships.ts
    - apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts (Wave 2, verified only)

decisions:
  - "Wave 2 freeze/unfreeze/renew impls verified correct — no changes needed; only gap was status forwarding in list()"
  - "FreezePeriod mapped via intermediate variable pattern (fp) not inline — improves readability without extraction helper"
  - "endedAt/endedBy assigned directly (no ?? null) because FreezePeriodResponse already types them as string | null"

metrics:
  duration: "15 minutes"
  completed: "2026-05-10T12:22:51Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 28 Plan 04: HTTP Freeze/Unfreeze/Renew + Status Filter Summary

HTTP memberships service extended with status query forwarding; all five new MembershipResponse fields verified correct in adapter; freeze/unfreeze/renew paths verified against regenerated schema.d.ts typed paths.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add status forwarding to list(); verify freeze/unfreeze/renew | 2c4713f | apps/admin-web/src/shared/api/services/http/memberships.ts |
| 2 | Verify responseToMembership 5 new fields | (no-op — Wave 2 correct) | apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts |

## What Was Built

**Task 1 — Status forwarding (FE-11):**
One line added in `list()` in `http/memberships.ts`:
```ts
if (query.status) q.status = query.status
```
This is placed after `clientId` forwarding, before `expiring` forwarding, following the established pattern. The backend `GET /api/v1/memberships` accepts `status?: MembershipStatus | null` (confirmed in schema.d.ts line 1927).

**Task 1 — Freeze/unfreeze/renew verification:**
Wave 2 already implemented all three methods (lines 106-131) using the correct typed paths:
- `POST /api/v1/memberships/{membership_id}/freeze`
- `POST /api/v1/memberships/{membership_id}/unfreeze`
- `POST /api/v1/memberships/{membership_id}/renew`

All three paths confirmed present in regenerated schema.d.ts (lines 450, 515, 480). Pattern correctly mirrors `cancel()` with `unwrap<MembershipResponse>()` + `responseToMembership()`.

**Task 2 — Adapter verification:**
Wave 2 extended `responseToMembership` with all 5 new fields. Verification confirmed:
- `freezeDaysLimitSnapshot: r.freezeDaysLimitSnapshot` — direct mapping
- `freezeDaysUsed: r.freezeDaysUsed` — direct mapping
- `freezeDaysRemaining: r.freezeDaysRemaining` — direct mapping
- `currentFreezePeriod` — extracted as `fp = r.currentFreezePeriod`, mapped to `FreezePeriod | null` with null guard; `endedAt`/`endedBy` assigned directly (schema types them as `string | null`, not `undefined`)
- `previousMembershipId: r.previousMembershipId ?? null` — collapses `undefined` to `null`

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written. Wave 2 had already implemented freeze/unfreeze/renew and the adapter extension. Only the status forwarding gap (FE-11) remained.

**Note:** The acceptance criteria check `grep -q "currentFreezePeriod: r.currentFreezePeriod"` does not literally match the adapter implementation, which uses an intermediate variable pattern (`fp = r.currentFreezePeriod`). The functional result is identical — `currentFreezePeriod` IS correctly mapped from `r.currentFreezePeriod`. This is a test phrasing issue, not an implementation issue; typecheck passes cleanly.

## Verification Results

| Check | Result |
|-------|--------|
| `freeze` method present | PASS |
| `unfreeze` method present | PASS |
| `renew` method present | PASS |
| `/api/v1/memberships/{membership_id}/freeze` path | PASS |
| `/api/v1/memberships/{membership_id}/unfreeze` path | PASS |
| `/api/v1/memberships/{membership_id}/renew` path | PASS |
| `if (query.status)` forwarding | PASS |
| `freezeDaysLimitSnapshot` in adapter | PASS |
| `freezeDaysUsed` in adapter | PASS |
| `freezeDaysRemaining` in adapter | PASS |
| `previousMembershipId ?? null` in adapter | PASS |
| `pnpm --filter sportzal-adminka typecheck` | PASS (0 errors) |
| `pnpm --filter sportzal-adminka lint` | PASS (0 errors, 2 pre-existing warnings) |
| `pnpm --filter sportzal-adminka test` | PASS (190/190) |
| Drift gate (openapi.json + schema.d.ts unchanged) | PASS |

## Known Stubs

None.

## Threat Flags

None. No new network endpoints or auth paths introduced. This plan only connects existing endpoint paths (defined in 28-01 schema regen) to the FE adapter layer. CSRF handling is carried forward via the `request()` helper.

## Self-Check: PASSED

- `apps/admin-web/src/shared/api/services/http/memberships.ts` — exists and modified
- `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts` — exists and verified
- Commit `2c4713f` — confirmed in git log
