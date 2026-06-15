# Phase 111: OpenAPI Handoff + Milestone Gate - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — smart-discuss infrastructure path, no grey areas)

<domain>
## Phase Boundary

The changed staff OpenAPI contract is regenerated and forward-guarded, and the full milestone gate passes — closing v3.1. HND-01 (handoff, not one of the 13 feature reqs).

Three success criteria:
1. `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` regenerated to reflect the new v3.1 routes — **additively (NOT byte-stable)** — and a `_v31Checks` `AssertNonNever` forward-guard tuple covers each new path×method.
2. The full milestone gate is green: backend mypy `--strict` + ruff + lint-imports + openapi-drift + alembic + pytest; api-client test + schema-drift; admin-app typecheck/lint/test/build; client-pwa typecheck/lint/test/build; Redocly lint; CISO-01 RBAC byte-parity.
3. All 13 v3.1 feature requirements (PLAN/PTPKG/CLI/CFG/PROF/VER) verified satisfied with no open blockers.

This is **infrastructure/handoff only** — no new user-facing behavior. Contrast Phase 106 (v3.0 byte-stable no-op handoff): Phase 111 produces a REAL additive diff and commits it.
</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase, mechanical regen + guard + gate. Use the toolchain below.

### Regen mechanics (additive, then committed → drift-gate passes on the committed artifacts)
- **openapi.json:** `cd apps/backend && uv run python -m scripts.export_openapi` (byte-stable serializer: indent=2, sort_keys=True, ensure_ascii=False, trailing newline). The current committed openapi.json is STALE (v3.1 executors deferred regen here) → expect a non-empty additive diff with the new paths. Commit the regenerated file.
- **schema.d.ts:** `pnpm --filter @clubcore/api-client codegen` (openapi-typescript v7; reads `../../apps/backend/openapi.json`, writes `src/schema.d.ts`). Commit the regenerated file.
- **`_v31Checks` forward-guard:** add a new block to `packages/api-client/src/schema.contract.test.ts` (after the `_v26Checks` block, ~line 650), mirroring the existing `AssertNonNever<paths[...][method]>` tuple pattern + a runtime `it(...) expect(_v31Checks).toHaveLength(N)`. Cover each NEW path×method (and JSON requestBody carriers): `PATCH /api/v1/auth/me` (+body), `POST /api/v1/auth/change-password` (+body), `GET /api/v1/gym` (staff), `GET`+`PUT /api/v1/settings/hours` (+body), `GET`+`PUT /api/v1/settings/booking` (+body), `GET`+`PUT /api/v1/settings/notifications` (+body). Exact entry count at executor discretion based on the actually-emitted paths (scout proposed ~14).

### Gate (run after regen + commit; the drift gates `git diff --exit-code` pass because the regenerated artifacts are committed)
Backend (from apps/backend, Postgres+Redis up): `uv run ruff check` · `uv run ruff format --check` · `uv run mypy --strict app` · `uv run lint-imports` · `uv run python -m scripts.export_openapi` then `git diff --exit-code apps/backend/openapi.json` · `uv run alembic upgrade head` · `uv run pytest`.
Frontend root: `pnpm -F @clubcore/api-client test` · `pnpm --filter @clubcore/api-client codegen` then `git diff --exit-code packages/api-client/src/schema.d.ts` · the recursive lint/typecheck/test for non-app packages.
Admin-app: `pnpm -F @clubcore/admin-app typecheck` · `lint` · `test` · `build`.
Client-pwa: `pnpm -F @clubcore/client-pwa typecheck` · `lint` · `test` · `build`.
Redocly: `npx -y @redocly/cli@latest lint apps/backend/openapi.json` (known-acceptable `operation-2xx-response` warning for the WS 101 endpoint).
CISO-01 RBAC parity: the backend `test_rbac_parity` / OWNER_ONLY byte-parity test (now 42 entries) — part of pytest.

### Documented pre-existing acceptable flakes (gate PASSES if ONLY these fail, for the documented reasons — any OTHER failure is a v3.1 regression)
- `test_freeze_race` (timing-dependent 409; passes in isolation)
- `test_audit_taxonomy` full-suite (leaked respx/Telegram socket GC misattribution; passes in isolation)
- `tests/test_client_promo_validate.py` (pre-v2.x promo F821/ruff debt)
- `test_alembic_clean` (`promo_codes.models` unregistered in alembic/env.py since v2.0; intermittent)
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets / exact toolchain (from scout)
- `apps/backend/scripts/export_openapi.py` (regen openapi.json) — `uv run python -m scripts.export_openapi`.
- `packages/api-client/package.json:16` codegen script — `pnpm --filter @clubcore/api-client codegen` (openapi-typescript v7.13.0).
- `packages/api-client/src/schema.contract.test.ts` — `AssertNonNever<T>` (lines 14-15) + per-version guard blocks; latest is `_v26Checks` (lines 613-651, length 8). Add `_v31Checks` after it.
- CI gate: `.github/workflows/ci.yml` — backend job (lines 20-106: mypy 75, lint-imports 78, export_openapi 81, `git diff --exit-code openapi.json` 94, alembic 103, pytest 106); frontend job (139-163: api-client test 149, codegen 152, `git diff --exit-code schema.d.ts` 163); admin-app job (206-237: typecheck 228, lint 230, test 233, build 236); client-pwa job (170-201); redocly-lint job (247-262).
- New v3.1 routes confirmed mounted: `auth/router.py:292` (PATCH /me), `:331` (POST /change-password); `gym/router.py:65` (GET) `:86` (PUT); `settings/router.py` (GET+PUT hours/booking/notifications).

### Established Patterns
- Phase 106 (v3.0) was a byte-stable no-op handoff; Phase 111 mirrors its gate discipline but with a REAL additive diff committed. Look at any 106 SUMMARY/handoff doc for the gate-evidence format.
- RBAC parity test now expects 42 OWNER_ONLY entries (108 added `(EDIT, SETTINGS)`).

### Integration Points
- Dev stack is up this session (Postgres :5432 migrations 0001..0071, Redis :6379, S3 :8333) — backend pytest + alembic can run against it. The api-client schema.d.ts is regenerated from the freshly-exported openapi.json.
- Money kopecks; dates Europe/Moscow (unchanged — no behavior added).
</code_context>

<specifics>
## Specific Ideas

- The drift gates use `git diff --exit-code` — they pass once the regenerated openapi.json + schema.d.ts are COMMITTED (the additive change becomes the new committed baseline; a re-export then diffs zero).
- Produce a gate-evidence summary (which gate commands ran + result) as the handoff artifact.
- Verify the 13 v3.1 requirements (PLAN-01/02, PTPKG-01/02, CLI-04, CFG-01..04, PROF-01/02, VER-01/02) are all marked verified/satisfied with no open blockers (107-110 closed them; browser-UAT items are tracked, not blockers).
</specifics>

<deferred>
## Deferred Ideas

None — infrastructure handoff phase; all work is regen + guard + gate.
</deferred>
