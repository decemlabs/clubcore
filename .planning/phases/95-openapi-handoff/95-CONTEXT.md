# Phase 95: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped — infrastructure/handoff phase; follows the proven Phase 89/v2.4 handoff pattern)

<domain>
## Phase Boundary

Freeze the v2.5 API surface and prove the milestone is green. Deliver HND-01:
- `apps/backend/openapi.json` regenerates **byte-stably** with all v2.5 REST messaging paths present under the `Messaging` tag; the WebSocket endpoint is documented manually in the `_customize_openapi()` post-processor (OpenAPI can't express WS); Redocly lint clean.
- `packages/api-client/src/schema.d.ts` regenerates **byte-stably**; the `_v25Checks` `AssertNonNever` tuple (in `packages/api-client/src/schema.contract.test.ts`) with a `toHaveLength(N)` assertion covers all new v2.5 path×method combos; `git diff --exit-code` on staff paths is empty (drift gate green — staff contract byte-for-byte identical to `contract-freeze-v1.11.0`).
- Full milestone gate passes: backend pytest + mypy --strict + lint-imports (incl. `app.modules.messaging` in the `modules-independent` contract) + the CISO-01 no-edit guard + frontend vitest + Redocly.

No new product behavior — this is regeneration + verification + manual WS doc only.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure/handoff phase, discuss skipped. Follow the established Phase 89 (v2.4) handoff pattern exactly. Use the existing tooling; do not invent new mechanisms.

</decisions>

<code_context>
## Existing Code Insights (handoff tooling — verified present)

- `apps/backend/scripts/export_openapi.py` — regenerates `apps/backend/openapi.json` (byte-stable export).
- `apps/backend/app/main.py` — `_customize_openapi()` post-processor (where the WS endpoint + tags/servers customization live; `_v24Checks`-era customization referenced here — extend for v2.5 / Messaging).
- `apps/backend/openapi.json` — the committed byte-stable artifact (must include the v2.5 Messaging REST paths).
- `packages/api-client/src/schema.d.ts` — generated TS types (regenerate byte-stably from openapi.json).
- `packages/api-client/src/schema.contract.test.ts` — the `_v24Checks` AssertNonNever drift gate; add `_v25Checks` covering all new v2.5 messaging path×method combos + a `toHaveLength(N)` count assertion.
- `apps/backend/tests/integration/client_auth/test_byte_parity.py` — byte-parity / contract-freeze test family (staff contract drift gate vs `contract-freeze-v1.11.0`).
- Milestone gate components: backend `uv run pytest`, `uv run mypy --strict`, `uv run lint-imports` (3 contracts incl. modules-independent with messaging), CISO-01 no-edit guard, frontend `pnpm vitest`, Redocly lint.

### Integration Points
- The v2.5 messaging REST endpoints (`/api/v1/client/messages` GET/POST, `?after=` cursor, `PATCH /messages/read`, attachment upload + serve) and the WS endpoint (`/api/v1/client/ws/messages`) must all appear correctly in openapi.json (REST auto; WS manual via `_customize_openapi()`).
- camelCase wire format (BackendSchemaBase alias_generator=to_camel) must round-trip into schema.d.ts.

</code_context>

<specifics>
## Specific Ideas

Mirror Phase 89's handoff exactly: regenerate openapi.json + schema.d.ts, add `_v25Checks` analogous to `_v24Checks`, manually document the new WS endpoint, run the full milestone gate, and ensure the staff-contract byte-parity/drift gate stays green (no staff-path drift — v2.5 only ADDS client messaging surface).

</specifics>

<deferred>
## Deferred Ideas

None — handoff phase.

</deferred>
