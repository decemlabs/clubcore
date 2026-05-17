## Phase 37-02 deferred (out-of-scope)

### Pre-existing admin-web typecheck failures (63 errors in src/routes/*)
- **Discovered:** Plan 37-02 Task 2 verification
- **Source:** `pnpm --filter @sportzal/admin-web typecheck` reports 63 errors
- **Files:** `src/routes/_protected/*.tsx` (12 routes), `src/routes/_public*` — all relate to `routeTree.gen.ts` typing (`Property 'getSession' does not exist on type 'never'`, `Argument of type "/_protected/X" not assignable to parameter of type 'undefined'`).
- **Root cause:** TanStack Router auto-generated `routeTree.gen.ts` is stale relative to current router context typing; `pnpm dev` typically regenerates it.
- **Confirmed pre-existing:** identical 63-error count when 37-02 backend commit was stashed (before any of my changes to apps/admin-web/src/shared/session/*).
- **My changes touched zero of these files** — only `src/shared/session/{registry.ts,can.ts}`. My session-file edits produced zero new errors.
- **Disposition:** out of scope per SCOPE BOUNDARY rule. Resolve in a dedicated routeTree-regeneration plan (likely a v1.5 Phase 38 pre-flight or hot-fix), not in 37-02.
