---
phase: 64-contract-freeze-openapi-curation
plan: "05"
subsystem: api
tags: [openapi, shared-responses, fastapi, spec-curation, ref-migration]

requires:
  - phase: 64-04
    provides: _customize_openapi() post-processor (security half) already wired in app/main.py

provides:
  - OPENAPI_ERROR_RESPONSES registry in app/core/openapi_responses.py
  - STATUS_TO_COMPONENT constant in app/main.py
  - Extended _customize_openapi() with components.responses injection + per-op $ref migration
  - openapi.json with components.responses (6 shared error envelopes) and $ref at all 401/403/404/409/422/429 callsites

affects:
  - 64-06 (Redocly lint must pass against spec that now uses $ref — no inline error schemas)
  - 64-07 (baseline tag captures the curated spec including shared responses)

tech-stack:
  added: []
  patterns:
    - Locked-registry dict pattern (OPENAPI_ERROR_RESPONSES mirrors LOCKED_AUDIT_EVENTS idiom from app/core/audit.py)
    - Post-processor extension — responses injection added after security half (Plan 64-04), before operation walk

key-files:
  created:
    - apps/backend/app/core/openapi_responses.py
  modified:
    - apps/backend/app/main.py
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts

key-decisions:
  - "D-64-RESPONSES-LOCATION: OPENAPI_ERROR_RESPONSES dict[str,dict[str,object]] declared in app/core/openapi_responses.py with 6 entries keyed 401_Unauthorized/403_Forbidden/404_NotFound/409_Conflict/422_ValidationError/429_RateLimited"
  - "D-64-RESPONSES-APPLY: post-processor approach — _customize_openapi() injects components.responses then walks every operation replacing inline error responses with $ref; no router changes required"
  - "STATUS_TO_COMPONENT constant placed alongside SECURITY_SCHEMES near module top; mutation in per-op walk is order-independent and idempotent"
  - "type: ignore[assignment] on op_responses assignment removed — mypy infers correctly without suppression"

requirements-completed: [FRZ-06]

duration: 20min
completed: "2026-05-28"
---

# Phase 64 Plan 05: Shared components.responses + $ref Migration Summary

**Six shared OpenAPI error response objects wired into spec.components.responses via OPENAPI_ERROR_RESPONSES registry; all 401/403/404/409/422/429 inline operation responses replaced with $ref in a single post-processor pass**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 3
- **Files modified:** 4 (openapi_responses.py created, main.py + openapi.json + schema.d.ts modified)

## Accomplishments

- New module `app/core/openapi_responses.py` declares `OPENAPI_ERROR_RESPONSES` — a `dict[str, dict[str, object]]` with 6 entries, each a full OpenAPI 3.1 Response Object with `{code, message, fields}` envelope schema mirroring `exceptions.py:440-449`. Comment discipline cites the AppError subclass for each entry (64-PATTERNS.md §1 table).
- `STATUS_TO_COMPONENT` constant added to `app/main.py` mapping HTTP status strings to component names.
- `_customize_openapi()` extended (Plan 64-04 security half preserved first): injects `OPENAPI_ERROR_RESPONSES` into `schema.components.responses`, then walks every operation replacing inline 401/403/404/409/422/429 responses with `{"$ref": "#/components/responses/<Name>"}`.
- Assertion battery passed: 6 shared responses in spec, zero inline offenders across all operations.
- `openapi.json` regenerated; `schema.d.ts` regenerated; drift gate green after second regen pass (byte-stable).

## Task Commits

1. **Task 1: Create openapi_responses.py with OPENAPI_ERROR_RESPONSES** - `85dd2ce5` (feat)
2. **Task 2: Extend _customize_openapi() post-processor** - `1f3fd9ef` (feat)
3. **Task 3: Regen byte-stable; drift gate green** - `66d30237` (feat)

## Files Created/Modified

- `apps/backend/app/core/openapi_responses.py` - New module: `OPENAPI_ERROR_RESPONSES` dict with 6 OpenAPI 3.1 Response Object entries; FRZ-06/D-64-RESPONSES-LOCATION header; AppError subclass annotations per 64-PATTERNS.md §1
- `apps/backend/app/main.py` - Added `from app.core.openapi_responses import OPENAPI_ERROR_RESPONSES` import; added `STATUS_TO_COMPONENT` constant; extended `_customize_openapi()` with responses injection and per-op $ref walk
- `apps/backend/openapi.json` - Regenerated: `components.responses` now contains all 6 shared error objects; 401/403/404/409/422/429 operation responses replaced with `$ref`
- `packages/api-client/src/schema.d.ts` - Regenerated to reflect spec changes

## Decisions Made

- `OPENAPI_ERROR_RESPONSES` uses `dict[str, dict[str, object]]` rather than 6 separate module-level constants — matches the registry pattern in 64-PATTERNS.md §1 and LOCKED_AUDIT_EVENTS idiom.
- `STATUS_TO_COMPONENT` placed at module level alongside `SECURITY_SCHEMES` — makes the mapping explicit and testable without threading a constant through the closure.
- No `type: ignore` suppression needed for the per-op mutation — mypy infers types correctly from the `isinstance(op, dict)` guard.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `ruff I001 (import sort)` flagged new import in wrong position twice (first after `register_exception_handlers`, then between `logging` and `middleware`). Corrected to alphabetical order: `exceptions → logging → middleware → openapi_responses → redis`. [Rule 1 auto-fix]
- `mypy unused-ignore` on a `# type: ignore[assignment]` that was not needed — removed immediately. [Rule 1 auto-fix]
- `ruff E501 line too long` on two inline comments (keys with long AppError class lists). Moved to separate comment lines above the dict entry. [Rule 1 auto-fix]

## User Setup Required

None.

## Next Phase Readiness

- `_customize_openapi()` is now complete for Phase 64 (security + responses halves). Plan 64-06 adds Redocly lint config and CI gate — no further post-processor changes needed.
- Spec is byte-stable; Redocly lint should pass against the $ref-clean spec (no inline error schemas to flag).
- Drift gate green; mypy strict (210 files) + ruff check + ruff format --check + lint-imports all exit 0.

## Self-Check: PASSED

- FOUND: apps/backend/app/core/openapi_responses.py
- FOUND: apps/backend/app/main.py (modified)
- FOUND: apps/backend/openapi.json (regenerated)
- FOUND: packages/api-client/src/schema.d.ts (regenerated)
- FOUND: 85dd2ce5 (feat: openapi_responses.py)
- FOUND: 1f3fd9ef (feat: extend _customize_openapi)
- FOUND: 66d30237 (feat: regen byte-stable)

---
*Phase: 64-contract-freeze-openapi-curation*
*Completed: 2026-05-28*
