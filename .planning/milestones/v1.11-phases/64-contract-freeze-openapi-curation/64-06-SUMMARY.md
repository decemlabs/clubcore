---
phase: 64-contract-freeze-openapi-curation
plan: "06"
subsystem: api
tags: [openapi, redocly, ci, spec-curation, lint]

requires:
  - phase: 64-04
    provides: securitySchemes + PUBLIC_ENDPOINT_OPERATION_IDS wired in _customize_openapi()
  - phase: 64-05
    provides: components.responses (6 shared error envelopes) + $ref migration complete

provides:
  - redocly.yaml at repo root extending `recommended` ruleset with 4 documented rule overrides
  - OAS 3.1-valid field `fields` schema in OPENAPI_ERROR_RESPONSES (anyOf [{type:object},{type:null}])
  - Regenerated openapi.json with structurally valid shared response schemas
  - 7th parallel CI gate `redocly-lint` in .github/workflows/ci.yml (no `needs:` dependency)

affects:
  - 64-07 (baseline tag captures spec that now passes Redocly recommended lint)

tech-stack:
  added:
    - "@redocly/cli (npx -y @redocly/cli@latest; no install — CI lint-only)"
  patterns:
    - Repo-root lint config (redocly.yaml mirrors pnpm-workspace.yaml root-tool convention)
    - Parallel CI job pattern (no `needs:` — mirrors existing backend/frontend job shape)
    - OAS 3.1 nullability via anyOf [{type:object},{type:null}] (not the 3.0 `nullable: true` keyword)

key-files:
  created:
    - redocly.yaml
  modified:
    - apps/backend/app/core/openapi_responses.py
    - apps/backend/openapi.json
    - .github/workflows/ci.yml

key-decisions:
  - "D-64-REDOCLY-RULESET: redocly.yaml at repo root with extends: [recommended]; 4 rule overrides each annotated with trade-off and decision ID"
  - "D-64-REDOCLY-CI-PLACEMENT: @latest used for CI lint step (lint-only, no runtime artifact); documented in comments for future pinning"
  - "Rule 1 auto-fix: OAS 3.0 `nullable: true` replaced with OAS 3.1 `anyOf [{type:object},{type:null}]` in all 6 OPENAPI_ERROR_RESPONSES entries"
  - "Rule overrides: info-license (D-64-NO-OPENAPI-EXTRA-INFO personal project), no-server-example.com (D-64-NO-SERVER-LIST-EXPANSION localhost is intentional), operation-4xx-response (D-64-NO-EXAMPLES FastAPI doesn't auto-add 4xx), no-unused-components (registry entries for future $ref use)"

requirements-completed: [FRZ-07]

duration: 25min
completed: "2026-05-28"
---

# Phase 64 Plan 06: Redocly Lint Config + 7th CI Gate Summary

**redocly.yaml at repo root extending recommended ruleset; OAS 3.1 nullable fix in shared responses; `redocly-lint` added as 7th parallel CI gate — npx @redocly/cli@latest exits 0 with 0 errors, 0 warnings**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 3 (Task 1: redocly.yaml + nullable fix; Task 2: CI job; Task 3: drift gate verification)
- **Files modified:** 4 (redocly.yaml created, openapi_responses.py + openapi.json fixed, ci.yml extended)

## Accomplishments

- `redocly.yaml` created at repo root with `extends: [recommended]` and 4 documented rule overrides (each with inline trade-off comment + decision reference per D-64-REDOCLY-RULESET).
- Rule 1 auto-fix: all 6 `OPENAPI_ERROR_RESPONSES` entries used OAS 3.0 `nullable: true` which is structurally invalid in OAS 3.1; replaced with `anyOf [{type:object,additionalProperties:true},{type:null}]` — fixed 6 Redocly `struct` errors.
- `openapi.json` regenerated; `schema.d.ts` unchanged (OAS 3.1 anyOf resolves to the same TypeScript type).
- `redocly-lint` job added to `.github/workflows/ci.yml` as the 7th top-level parallel job — no `needs:` dependency, runs concurrently with `backend` and `frontend`.
- `npx -y @redocly/cli@latest lint apps/backend/openapi.json` exits 0 with 0 errors and 0 warnings.
- Drift gate green; regen is byte-stable (no Python code changed, only response schema shape).

## Task Commits

1. **Task 1: Create redocly.yaml + fix OAS 3.1 nullable** - `57e3ef4f` (feat)
2. **Task 2: Add redocly-lint parallel CI job** - `4cb6615f` (feat)
3. **Task 3: Drift gate verification** - (no-op regen; drift gate green; no additional commit needed)

## Files Created/Modified

- `redocly.yaml` - New file: Redocly lint config at repo root; `extends: [recommended]`; 4 rule overrides: `info-license: off`, `no-server-example.com: off`, `operation-4xx-response: off`, `no-unused-components: off` — each with inline justification + decision ID
- `apps/backend/app/core/openapi_responses.py` - Fixed: replaced OAS 3.0 `nullable: True` with OAS 3.1 `anyOf [{type:object,additionalProperties:True},{type:null}]` in all 6 response entries
- `apps/backend/openapi.json` - Regenerated: shared response schemas now use `anyOf` structure (OAS 3.1 compliant)
- `.github/workflows/ci.yml` - Added `redocly-lint` top-level job (lines after `frontend` job); parallel execution; `permissions: contents: read`; uses `actions/checkout@v4` + `actions/setup-node@v4 (node 20)` + `npx -y @redocly/cli@latest lint apps/backend/openapi.json`

## Decisions Made

- `@latest` used for Redocly CLI in CI (per D-64-REDOCLY-CI-PLACEMENT: acceptable for lint-only steps; exact version comment in ci.yml for future pinning)
- `redocly.yaml` stays at repo root (per D-64 "Claude's Discretion" root-tool convention; no `apis:` block needed since Redocly auto-discovers from cwd and accepts relative path arg)
- 4 rule overrides chosen (not masking structural issues — only stylistic / out-of-scope warnings)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed OAS 3.1 invalid `nullable: true` in OPENAPI_ERROR_RESPONSES**
- **Found during:** Task 1 (first local lint dry-run)
- **Issue:** All 6 entries in `app/core/openapi_responses.py` used `"nullable": True` — valid in OAS 3.0 but structurally invalid in OAS 3.1 (the `struct` rule treats it as an unrecognized keyword). This caused 6 Redocly errors, blocking lint exit 0.
- **Fix:** Replaced `{"type": "object", "nullable": True, "additionalProperties": True}` with `{"anyOf": [{"type": "object", "additionalProperties": True}, {"type": "null"}]}` in all 6 entries. This is the OAS 3.1 canonical way to express nullability.
- **Files modified:** `apps/backend/app/core/openapi_responses.py`, `apps/backend/openapi.json` (regen)
- **Verification:** `npx @redocly/cli@latest lint apps/backend/openapi.json` → 0 errors, 0 warnings
- **Committed in:** `57e3ef4f` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — structural bug)
**Impact on plan:** Essential for correctness — OAS 3.0 `nullable` keyword is not valid in OAS 3.1 specs. No scope creep.

## Redocly Lint Result

```
validating apps/backend/openapi.json...
apps/backend/openapi.json: validated in 56ms

Woohoo! Your API description is valid.
```

Exit code: 0. 0 errors, 0 warnings.

## Issues Encountered

None beyond the Rule 1 auto-fix above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `redocly-lint` is the 7th CI gate; any PR that introduces structural spec regressions (broken `$ref`, OAS 3.0 keywords in a 3.1 spec, duplicate operationIds, missing required fields) will now fail CI.
- Plan 64-07 (baseline tag + CHANGELOG) can proceed — spec is structurally clean and drift gate is green.
- Drift gate: `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` exits 0.
- All quality gates: ruff check, ruff format --check, mypy --strict app, lint-imports all exit 0.

## Self-Check: PASSED

- FOUND: redocly.yaml (repo root)
- FOUND: apps/backend/app/core/openapi_responses.py (modified)
- FOUND: apps/backend/openapi.json (regenerated)
- FOUND: .github/workflows/ci.yml (modified)
- FOUND: 57e3ef4f (feat: redocly.yaml + nullable fix)
- FOUND: 4cb6615f (feat: CI redocly-lint job)

---
*Phase: 64-contract-freeze-openapi-curation*
*Completed: 2026-05-28*
