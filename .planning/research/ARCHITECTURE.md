# Architecture Research — v4.1 Codebase Hardening

**Domain:** Hardening/audit-and-fix integration into a locked modular-monolith + dual-SPA architecture
**Researched:** 2026-07-26
**Confidence:** HIGH (grounded in direct repo inspection — file paths, existing test patterns, CI gate config; no external ecosystem research needed for this milestone)

## Standard Architecture

### System Overview — where hardening work sits relative to the locked architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  AUDIT PHASE (input-gathering, read-only)                                 │
│  ┌───────────────┐ ┌──────────────────┐ ┌───────────────┐ ┌────────────┐  │
│  │ Browser-UAT   │ │ Zod-vs-wire      │ │ Reachability  │ │ Static      │  │
│  │ (agent-browser│ │ diff (generalize │ │ sweep         │ │ audit       │  │
│  │  on real API) │ │ capture pattern) │ │ router+nav    │ │ (TODO/dead/ │  │
│  │               │ │                  │ │               │ │ layer-viol) │  │
│  └───────┬───────┘ └────────┬─────────┘ └───────┬───────┘ └──────┬──────┘  │
│          └──────────────────┴──────────┬─────────┴────────────────┘        │
│                                         ▼                                   │
│                         ONE DEFECT-REGISTRY artifact                       │
│                    (.planning/audits/v4.1-DEFECT-REGISTRY.md)              │
└───────────────────────────────────┬────────────────────────────────────────┘
                                     ▼
   ┌─────────────────────┬──────────────────────┬──────────────────────────┐
   │ FIX: functional bugs│ FIX: code hygiene /   │ FIX: infra local-verify  │
   │ on real data         │ architecture           │ (k3d, backup, sealed-   │
   │ (Zod schemas,        │ (dead code, dedup,     │ secrets)                │
   │  router/nav,         │  layer boundaries,     │                        │
   │  crashing screens)   │  TODO/FIXME closure)   │                        │
   └──────────┬───────────┴───────────┬────────────┴────────────┬───────────┘
              │                       │                         │
              ▼                       ▼                         ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │        LOCKED SAFETY RAILS (existing, unchanged by this milestone)  │
   │  RBAC byte-parity · LOCKED_AUDIT_EVENTS AST gate · OpenAPI drift ·   │
   │  import-linter (2 contracts) · admin ESLint boundaries · pytest/    │
   │  vitest/mypy --strict/ruff                                          │
   └─────────────────────────────────────────────────────────────────────┘
```

The three fix categories are **downstream consumers of one artifact**, not three independent audits. This is the crux of the whole milestone: the audit phase is a fan-in (evidence gathering, no code changes), the registry is the single hand-off contract, and the fix phases fan back out — some in parallel, some serialized by the locked rails.

### Component Responsibilities

| Component | Responsibility | Status | Where it lives |
|-----------|-----------------|--------|-----------------|
| Browser-UAT harness | Drives `apps/admin` + `apps/client` against the real backend, screen by screen, domain by domain; the ONLY reliable detector of mock↔real drift per the v3.0/v3.1 lesson | NEW (harness), reuses existing `agent-browser` skill | ad hoc, invoked per-domain; findings feed the registry |
| Capture-test pattern | Backend integration test hits a real endpoint via `ASGITransport`, serializes the actual JSON response to a shared fixture file | EXISTING, partially applied | `apps/backend/tests/integration/<domain>/test_*_capture.py` → writes to `apps/admin/src/features/<domain>/capture/*.json` |
| Contract test | Frontend vitest parses the captured fixture with the REAL Zod schema the hook uses | EXISTING, partially applied | `apps/admin/src/features/<domain>/*.contract.test.ts` |
| Per-domain Zod seam | Hand-written runtime validators for wire shapes, colocated with the TanStack Query hooks | EXISTING (all ~25 `features/*` dirs), some already covered by contract tests, most not | `apps/admin/src/features/<domain>/schemas.ts` |
| Generated OpenAPI types | Structural TS types, compile-time only, no runtime validation | EXISTING | `packages/api-client/src/schema.d.ts`, generated from `apps/backend/openapi.json` |
| Reachability registry | Cross-reference of routes that are wired (have hooks/schemas/pages) vs. reachable (in `router.tsx` as real element, not `<ComingSoon/>`, AND present in `nav-items.ts`) | NEW (as an audit step; the underlying files are existing/modified) | `apps/admin/src/app/router.tsx`, `apps/admin/src/layouts/AppLayout/nav-items.ts` |
| DEFECT-REGISTRY | Single artifact all fix phases read from and write disposition back to | NEW | `.planning/audits/v4.1-DEFECT-REGISTRY.md` (or `.csv`/`.json` sidecar — see Registry Artifact section) |
| Import-linter contracts | Machine-enforced module isolation; catches illegal cross-module coupling introduced by dedup/refactor | EXISTING, unmodified | `apps/backend/.importlinter` (2 contracts: `modules-independent`, `core-not-depend-on-modules` + a third `integrations-not-depend-on-modules`) |
| RBAC byte-parity test | Set-equality of `OWNER_ONLY` pairs (46 entries) + `Resource`/`Action` enums between backend and frontend | EXISTING, unmodified — must stay green through every hygiene commit | `apps/backend/tests/integration/test_rbac_parity.py` ↔ `apps/admin/src/shared/session/can.ts` + `registry.ts` |
| Route-introspection guard | Confirms every mutating route actually has a `Depends(require_permission)` (not just RBAC-table-consistent, but present) | EXISTING, unmodified | `apps/backend/tests/integration/test_route_introspection.py`, `test_phase51_route_introspection.py` |
| Audit-event AST gate | Walks the AST of every `audit.emit(...)` / commit callsite and rejects non-literal event-name strings; only members of `LOCKED_AUDIT_EVENTS` frozenset are allowed | EXISTING, unmodified | `apps/backend/app/core/audit.py` (frozenset), `apps/backend/tests/unit/test_service_commit_gate.py`, `test_audit_taxonomy.py` |
| OpenAPI drift gate | Byte-compares `uv run python -m scripts.export_openapi` output against the committed `apps/backend/openapi.json`, and `packages/api-client/src/schema.d.ts` codegen against committed file | EXISTING, unmodified | CI job "Backend (drift gates + statics)" / "Frontend (drift gates + statics)" in `.github/workflows/ci.yml` |
| Admin ESLint boundaries | `import/no-restricted-paths` (pages/layouts/components → `api/client.ts` banned) + `VITE_API_MODE` chokepoint ban | EXISTING, unmodified, **has a real gap** (see Anti-Patterns) | `apps/admin/eslint.config.js:31-73` |
| k3d verification scripts | Local-only cluster bring-up, restore round-trip, sealed-secrets key backup | EXISTING (v4.0), to be actually EXECUTED not just statically validated | `infra/scripts/k3d-up.sh`, `Makefile` targets `up`/`smoke`/`backup`/`helm-lint`/`tf-validate` |

## Recommended Project Structure (delta only — no new top-level layout)

```
.planning/
├── audits/
│   └── v4.1-DEFECT-REGISTRY.md      # NEW — single hand-off artifact (see below)
apps/backend/
├── tests/integration/<domain>/
│   └── test_<domain>_capture.py     # MODIFIED/NEW per domain lacking one — generalizes existing pattern
apps/admin/src/features/<domain>/
├── capture/*.json                   # MODIFIED/NEW per domain lacking one
├── *.contract.test.ts               # MODIFIED/NEW per domain lacking one
├── schemas.ts                        # MODIFIED where drift is found
apps/admin/src/app/router.tsx         # MODIFIED — ComingSoon → lazy per reachability finding
apps/admin/src/layouts/AppLayout/nav-items.ts  # MODIFIED — same
```

No new top-level directories, no new packages, no new services. This is intentional — the milestone must not introduce structure the locked architecture doesn't already have a slot for.

### Structure Rationale

- **`.planning/audits/v4.1-DEFECT-REGISTRY.md`:** lives beside existing `.planning/milestones/*-MILESTONE-AUDIT.md` and `.planning/audits/` (already exists per `ls .planning/`) — this is where audit artifacts already live in this project's convention; no new location invented.
- **Capture/contract-test pairs stay per-domain:** this is not a new pattern, it is the **already-proven fix** for the exact problem this milestone is chartered to solve (the v3.1 lesson literally IS this pattern, invented in response to the first drift). The gap is coverage, not design.
- **No changes to `packages/api-client`:** it is a pure generated-types package with a byte-stability drift gate; adding runtime Zod derivation there would conflate two different concerns (compile-time shape vs. runtime validation) and would touch a package consumed by both `apps/admin` and `apps/client`, multiplying blast radius for a hardening milestone that should minimize risk.

## Architectural Patterns

### Pattern 1: Capture-then-contract-test (the answer to question (a))

**What:** A backend integration test hits a real endpoint over `ASGITransport`, serializes the actual JSON to a shared fixture under `apps/admin/src/features/<domain>/capture/*.json`. A frontend vitest file parses that captured fixture with the exact Zod schema the production hook uses (not a hand-rolled fixture — the REAL captured bytes).

**When to use:** For every domain's `schemas.ts` that has NOT yet been given this treatment. Confirmed present today for: `promoCodes`, `payments` (refund), `messages`, `users` (role-change), `reports` (load-now). Confirmed absent (schemas.ts exists, only a hand-fixture `schemas.test.ts` exists, e.g. `clients`, `memberships`, `schedule`, and most of the remaining ~20 `features/*` dirs) — **this absence is exactly the audit's job to enumerate, not to re-derive from scratch.**

**Why this is the architecturally correct seam, and why NOT to derive Zod from `schema.d.ts`:**
1. `schema.d.ts` is OpenAPI-generated **structural types** — it has no runtime behavior and cannot itself catch a live-serializer bug (OpenAPI byte-stability only proves the *spec* didn't drift, never that the *spec ever matched the runtime* — that's precisely the v3.0/v3.1 failure mode: unit tests on mocks passed, OpenAPI drift gate was green, and the bug still shipped).
2. Deriving Zod schemas mechanically from `schema.d.ts` (e.g. via a zod-from-openapi codegen step) would require a NEW build step in `packages/api-client`, touching its byte-stability drift gate, and would still not solve the actual problem — a codegen tool trusts the OpenAPI spec, and the spec is what was already proven wrong twice. The fix has to be empirical (real response bytes), not another layer of trust-the-spec.
3. The correct integration point is exactly where it already lives: `apps/admin/src/features/<domain>/schemas.ts`, validated against captured real JSON, consumed by the SAME `xKeys`/hook file in `api.ts` that ships to production. Zero new layers, zero new import edges.

**Trade-offs:** Capture tests only prove the schema parses THIS ONE seeded shape — they do not prove exhaustiveness (nulls, absent-optional fields, a second variant of the same endpoint). Mitigate cheaply: add a lightweight compile-time cross-check (mirroring the existing `AssertNonNever` pattern in `packages/api-client/src/schema.contract.test.ts`) that structurally compares `z.infer<typeof XSchema>` against the corresponding `components['schemas'][...]` type from `schema.d.ts`, so a field the OpenAPI spec knows about but the hand-written Zod schema forgot fails at `tsc` time, not only in a browser. This is a small additive TS file per domain, not a redesign.

**Data-flow implication:** NONE to production code paths. This is purely an audit/verification-layer addition — same `staffRequest` fetcher, same TanStack Query hooks, same `VITE_API_MODE` seam. The only "flow" that changes is test-time: backend test run → JSON fixture on disk → frontend test run reads it. No new runtime dependency, no new network call in production.

### Pattern 2: Composition-root Protocol slots for any NEW cross-module wiring hygiene work needs

**What:** `apps/backend/app/main.py` is the one place exempted from `core-not-depend-on-modules`; cross-module writes go through `register_*` Protocol slots wired there (e.g. `register_active_membership_resolver`, `register_payment_recorder`).

**When to use:** If hygiene work (deduping business logic across modules) legitimately needs a new cross-module call, it MUST go through this seam or a documented raw-SQL read (D-54-08 precedent), never a direct import between `app.modules.*` packages.

**Trade-off:** Adding a new Protocol slot is heavier than a direct import, by design — the friction is the point (import-linter's `modules-independent` contract would otherwise be trivially defeated). Hygiene work should almost never need a NEW slot; if it does, that's a signal the "dedup" is actually a scope-creeping cross-module feature and should be flagged in the registry as `category: architecture` with a note, not silently fixed.

### Pattern 3: Registry-as-contract for parallel/independent fix phases (answers question (c))

**What:** The audit phase produces exactly one artifact; every fix phase reads from it and writes disposition back, never re-discovers findings independently.

**Minimum required fields per finding (each is load-bearing for a specific downstream need):**

| Field | Purpose | Example |
|---|---|---|
| `id` | Stable, referenceable across phases/commits (e.g. `DEFECT-042`) — never renumber, only append | `DEFECT-042` |
| `category` | Routes the finding to the right fix phase | `functional` \| `hygiene` \| `infra` \| `security` (RBAC/audit-gate adjacent) |
| `severity` | Prioritization within a fix phase | `blocker` \| `major` \| `minor` \| `cosmetic` |
| `anchor` | Exact file(s)/route/screen — the reproduction target | `apps/admin/src/features/schedule/schemas.ts:34` + route `/schedule` |
| `repro` | How it was found — browser step sequence, static-analysis rule hit, or capture-test diff | "Navigate to /schedule as reception → console TypeError parsing `trainerId: null`" |
| `evidence` | Link to the proof artifact (screenshot path, captured JSON diff, grep hit, ruff/import-linter output line) | `.planning/audits/evidence/DEFECT-042.png` |
| `disposition` | The only field fix phases are allowed to WRITE (audit phase never sets this beyond `open`) | `open` \| `fixed+verified` \| `deferred:<reason>` |
| `owning_phase` | Which fix phase claims it (so parallel phases don't double-work the same finding) | `phase-125-functional-fixes` |
| `blocks`/`blocked_by` | Cross-references so a hygiene fix that touches a file a functional fix also needs is sequenced, not raced | `blocked_by: DEFECT-019` |
| `locked_invariant_risk` | Explicit flag if the fix touches RBAC/audit-events/OpenAPI/import-linter surface — forces the safety-rail checklist before merge | `true — touches can.ts` |

**Format:** Markdown table (human-scannable, git-diffable, matches this project's existing `.planning/` convention) is sufficient at this scale (dozens, not thousands, of findings) — do NOT introduce a database or JSON-schema-validated store; that would be over-engineering for a solo-dev pet project and adds a new artifact-format the roadmap would then need to maintain. A single `.md` file with one row per finding, sorted by category then severity, is the right level of ceremony.

### Recommended git/commit convention for closing a finding
Each fix commit references the finding id in its message (mirrors existing `T-103-03-FAKEREFUND`-style tags already used in this project's history) so `git log --grep DEFECT-042` is the audit trail — no extra tooling needed.

## Data Flow

### Audit → Registry → Fix (the only new data flow this milestone introduces)

```
[Browser-UAT session]      [Capture-test run]        [Static analysis run]
        │                          │                            │
        ▼                          ▼                            ▼
  screenshot + repro        captured JSON +             ruff/mypy/import-linter/
  note                      contract-test failure       eslint/grep TODO output
        │                          │                            │
        └──────────────┬───────────┴──────────────┬─────────────┘
                        ▼                          ▼
              .planning/audits/v4.1-DEFECT-REGISTRY.md (append-only during audit phase)
                        │
        ┌───────────────┼────────────────────────────┐
        ▼               ▼                            ▼
  functional-fix    hygiene-fix                  infra-verify
  phase reads       phase reads                  phase reads
  category=functional category=hygiene           category=infra
  rows, writes      rows, writes                 rows, writes
  disposition       disposition                  disposition
        │               │                            │
        └───────────────┴────────────────────────────┘
                        ▼
        registry re-read at milestone-audit time —
        done-bar = every row fixed+verified OR deferred+reason
```

### Key Data Flows

1. **Finding → contract-test proof (functional category):** every functional fix's disposition can only flip to `fixed+verified` once a NEW or UPDATED capture/contract-test pair exists proving the fix against a REAL backend response — mirrors the existing v3.1/v3.2 gate discipline ("≥1 contract-test per domain parsing a REAL backend response"), just applied per-finding instead of per-domain.
2. **Reachability finding → router/nav diff:** a reachability finding's evidence is a two-line diff (`router.tsx` element swap + `nav-items.ts` entry), and its "verified" state is proven by the EXISTING `router-smoke.test.tsx`-style route-render suite (already renders every registered route) plus one browser click-through — no new test infrastructure needed, just exercising what exists.
3. **Hygiene finding → gate re-run, not new test:** a dead-code/dedup/layer-boundary finding's proof of fix is that the FULL existing gate suite (ruff, mypy --strict, `lint-imports`, ESLint, ESLint `no-restricted-paths`, vitest, pytest, OpenAPI/schema.d.ts drift) stays green — hygiene work should almost never need new test files, since the rails already exist; if a hygiene fix requires a NEW test, that's a signal it silently expanded scope into functional-fix territory and should be re-tagged.
4. **Infra finding → Makefile target execution, not new scripts:** `BAK-03`/`SEC-02`-class findings are proven by actually running `make backup`, `make up`, `make smoke` against a live `k3d` cluster (scripts already exist per v4.0) — the "new" work is execution + evidence capture, not new tooling.

## Anti-Patterns

### Anti-Pattern 1: Deriving/generating Zod schemas from `schema.d.ts` to "fix" the drift architecturally

**What people would be tempted to do:** Introduce a zod-from-openapi codegen step so the Zod layer can never drift from the OpenAPI spec again.
**Why it's wrong here:** It doesn't address the actual failure mode (spec-vs-runtime drift, not spec-vs-Zod drift), adds a new build/codegen dependency to `packages/api-client` (touching its byte-stability drift gate — a locked invariant), and is a structural change disallowed by "the architecture is LOCKED, must not be redesigned."
**Do this instead:** Generalize the existing capture-then-contract-test pattern to every domain (Pattern 1 above); optionally add a compile-time `schema.d.ts`-vs-`z.infer` structural cross-check as a cheap belt-and-suspenders addition, not a replacement.

### Anti-Pattern 2: Treating "code hygiene" as license to touch RBAC/audit/OpenAPI surfaces opportunistically

**What people would be tempted to do:** While deduping a service module, also "clean up" a `Depends(require_permission)` call or rename an audit-event string for consistency.
**Why it's wrong:** Both are AST/parity-gated LOCKED invariants (`test_rbac_parity.py`, `test_service_commit_gate.py`) specifically so that no single commit can silently drift them — but the gates only catch STRUCTURAL drift (set membership, literal-string enforcement), not SEMANTIC correctness. A hygiene commit that renames an audit event to something equally frozenset-valid-looking-but-wrong, or restructures `OWNER_ONLY` in a way that keeps the same 46-count but swaps two pairs, can pass every existing gate and still be a real regression.
**Do this instead:** Any hygiene finding whose fix touches `apps/backend/app/core/permissions.py`, `apps/backend/app/core/audit.py`/`audit_payloads.py`, any `Depends(require_permission)` call, `apps/admin/src/shared/session/{can,registry}.ts`, `.importlinter`, or `apps/backend/openapi.json` must be flagged `locked_invariant_risk: true` in the registry and get a manual before/after diff review as part of its verification — not just a green CI run.

### Anti-Pattern 3: Assuming ESLint import boundaries already prevent feature-to-feature coupling

**What people would assume:** Since `apps/admin/CLAUDE.md` documents "features → entities+shared, never other features," hygiene work can rely on ESLint to catch any accidental feature-to-feature import introduced during dedup.
**Why it's wrong:** Inspection of `apps/admin/eslint.config.js:31-73` shows only two zones are machine-enforced today: (1) `pages/layouts/components → api/client.ts` banned, and (2) `VITE_API_MODE` read outside `features/*/api.ts` banned. There is **no** `import/no-restricted-paths` zone banning `features/x → features/y` — that boundary is currently convention-only, documented but not gated. This is a genuine, real gap the locked rails do NOT cover.
**Do this instead:** The static-audit sub-phase should explicitly grep/lint for cross-feature imports (`grep -rn "from '@/features/" apps/admin/src/features/*/  ` excluding self-imports) as one of its checks, and — if the audit finds live violations — the hygiene fix phase should both fix them AND add the missing ESLint zone so this stops being a silent gap. Adding that zone is itself a "new gate" the roadmap should schedule LAST in the hygiene fix phase (after violations are fixed), so the gate doesn't fail on pre-existing debt mid-milestone.

## Integration Points

### Locked rails and the gaps they do not cover (answers question (b) directly)

| Rail | Catches | Does NOT catch (gap) |
|---|---|---|
| RBAC byte-parity (`test_rbac_parity.py` ↔ `can.ts`/`registry.ts`) | Any structural drift in the 46-pair `OWNER_ONLY` set or `Resource`/`Action` enums between FE/BE | Semantically wrong-but-count-preserving swaps; a route that's reachable-but-unguarded on ONE side in a way that still parses (route introspection guard is the actual catch for missing `Depends`, separate test) |
| Route-introspection guard (`test_route_introspection.py`, `test_phase51_route_introspection.py`) | Every mutating backend route actually declares `Depends(require_permission)` | Frontend reachability (a backend route can be perfectly guarded and still be unreachable from the UI — that's the FND-04 class of bug, a DIFFERENT audit dimension entirely) |
| `LOCKED_AUDIT_EVENTS` + AST commit-gate (`test_service_commit_gate.py`, `test_audit_taxonomy.py`) | Any non-literal or non-member audit-event string at an `audit.emit`/commit callsite | Dead code removal silently deleting a truly-unreachable audit-emit call (gate has nothing to check once the callsite is gone); a business path that SHOULD emit an event but never did (gate only checks emitted strings, not coverage) |
| OpenAPI drift gate (`export_openapi` byte-compare) + `schema.d.ts` codegen drift gate | Any accidental route/schema signature change during refactor | Whether the frozen spec ever matched the LIVE runtime response (exactly the Zod-vs-wire gap — this is why Pattern 1 exists as a separate, additional rail) |
| import-linter (`modules-independent`, `core-not-depend-on-modules`, `integrations-not-depend-on-modules`) | Any new illegal `app.modules.x → app.modules.y` import, or `app.core`/`app.integrations` reaching into `app.modules` | Cross-module coupling laundered through raw-SQL `text()` reads that silently re-implement another module's business rule (a "logic duplication" smell the contract structurally cannot see, since it only inspects Python imports) |
| Admin ESLint `import/no-restricted-paths` + `VITE_API_MODE` selector ban | `pages/layouts/components → api/client.ts` direct access; `VITE_API_MODE` read outside the swap seam | Feature-to-feature imports (documented convention, NOT gated — see Anti-Pattern 3); no rule bans raw Tailwind color mentioned in CLAUDE.md conventions if that ESLint rule was ever removed (verify during static audit, don't assume) |
| Full gate suite (`ruff`, `ruff format --check`, `mypy --strict`, `pytest`, `vitest`, `tsc`) | Type errors, lint violations, test regressions across BOTH apps | Dead code that still type-checks and has no test exercising it (that's precisely what the static "dead code" hygiene finding category exists to catch manually/via tooling like `vulture`/`ts-prune`, which are NOT currently in the gate suite) |

### External/local tool integration for the audit itself

| Tool | Integration Pattern | Notes |
|---|---|---|
| `agent-browser` skill | Drives real browser sessions against `docker compose up` backend + `pnpm dev` frontends for the UAT sub-phase | Already the project's established UAT mechanism (used in prior milestones' browser-UAT closures); no new tool to introduce |
| `vulture` / `ts-prune` (or equivalent) | Static dead-code detection for Python/TS respectively | NOT currently in `ci.yml` — evaluate adding as a ONE-TIME audit-phase tool run (not necessarily a permanent CI gate, to avoid scope creep into "add new permanent gates" which is its own decision the roadmap should make explicitly) |
| `grep -rn "TODO\|FIXME\|HACK"` | Enumerates the 19 (backend+admin+client `.py`/`.ts`/`.tsx`, files-with-hits count; some files have multiple markers) currently-marked debt items | Simple, already how the milestone context in `PROJECT.md` derived its "32 TODO/FIXME/HACK" figure — reuse, don't rebuild |
| `k3d` + `Makefile` targets (`up`, `smoke`, `backup`, `helm-lint`, `tf-validate`) | Local cluster bring-up and the 8-check smoke, restore round-trip, static Helm/Terraform validation | All EXISTING from v4.0 — this milestone's infra work is EXECUTION + evidence capture against these, not new script authoring |

## Scaling Considerations

Not applicable in the traditional sense (this is a hardening milestone on a single-tenant pet-project CRM, not a scale-up). The only "scaling" axis relevant here is **finding volume**:

| Finding volume | Approach |
|---|---|
| Dozens (expected here — 19 TODO markers + N screens × few domains + 23 v4.0 operator-pending items) | Single Markdown registry file, manual `disposition` column updates, git-grep for cross-referencing — sufficient |
| Hundreds (NOT expected, but a signal if it happens) | Would justify splitting the registry per-category into separate files; do not pre-optimize for this |

### What breaks first if this milestone is executed wrong

1. **First failure mode:** Audit and fix phases interleave (an agent starts fixing while still auditing) → registry never becomes a stable hand-off artifact → parallel fix phases silently duplicate or race on the same files. **Mitigation:** audit phase is READ-ONLY by construction (no `Edit`/`Write` to app code during audit, only to the registry) — this should be an explicit phase-boundary rule in the roadmap, not just a convention.
2. **Second failure mode:** A hygiene fix (dedup/dead-code-removal) lands in the same phase/commit as a functional fix touching the same file, making it impossible to `git revert` one without the other if a locked-invariant regression surfaces later. **Mitigation:** the `blocked_by`/`owning_phase` registry fields exist precisely to force sequencing here (see Build Order below).

## Integration Points and Dependency Ordering (answers question (d))

| Work stream | Can run in parallel with… | Must serialize after/before… | Why |
|---|---|---|---|
| Browser-UAT functional audit | Static-analysis hygiene audit; infra local-verify audit | — (audit sub-phases are mutually read-only, no shared file writes) | All three audit sub-phases only WRITE to the registry, never to app code — no collision surface |
| Static-analysis hygiene audit | Browser-UAT functional audit; infra local-verify audit | — | Same reason |
| Infra local-verify audit (k3d apply, restore round-trip, sealed-secrets backup) | Both audits above | — | Entirely separate subsystem (`infra/`), zero file overlap with `apps/` |
| **Registry freeze** (audit phase closes) | — | Must come AFTER all three audits, BEFORE any fix phase starts | The registry is the hand-off contract; fix phases reading a still-mutating registry can't parallelize safely |
| Functional fixes (Zod/router/nav) | Infra local-verify fixes | Should run BEFORE or interleaved-with-care against hygiene fixes touching the SAME files (`schemas.ts`, `router.tsx`) | Functional fixes change runtime-observable behavior; a hygiene dedup pass touching the same file concurrently risks silent behavioral merge conflicts even if `git merge` succeeds cleanly |
| Hygiene fixes (dead code, dedup, boundaries) | Infra local-verify fixes | Should run AFTER functional fixes are dispositioned for any FILE it also touches (use `blocked_by` in the registry) — but CAN start immediately on files with zero functional-finding overlap | Hygiene work on untouched files has no collision risk and can proceed in full parallel with functional fixes elsewhere |
| Infra local-verify fixes (k3d, backup, sealed-secrets) | Functional fixes; hygiene fixes | Fully independent — different subsystem, different toolchain (Terraform/Helm/k3d vs. Python/TS) | Zero shared files or shared gates (infra has its own `make` targets, not `pytest`/`vitest`) |
| Final full-gate re-run + milestone audit | — | Must come AFTER every fix phase reports disposition | This is the actual "done-bar" check from `PROJECT.md`: every gate green, every registry row `fixed+verified` or `deferred+reason` |

**Rule of thumb for the roadmapper:** parallelism is safe across SUBSYSTEMS (frontend-functional vs. backend-hygiene vs. infra) and UNSAFE within the same file/module unless the registry's `blocked_by` graph says otherwise. Infra work is *always* parallelizable against the other two because it shares zero files and zero CI gates with `apps/`.

## New vs. Modified Components (answers question (e) — explicit split for the roadmapper)

### NEW components this milestone introduces

| Component | Purpose | Suggested path |
|---|---|---|
| DEFECT-REGISTRY artifact | Single hand-off artifact from audit to all fix phases | `.planning/audits/v4.1-DEFECT-REGISTRY.md` |
| Browser-UAT audit harness (a session script/checklist, not new product code) | Systematic per-domain click-through against real backend, both apps | ad hoc `agent-browser` sessions + a per-domain checklist doc, e.g. `.planning/audits/v4.1-UAT-CHECKLIST.md` |
| Capture/contract-test PAIRS for domains that currently lack them | Closes the generalization gap in the existing pattern | `apps/backend/tests/integration/<domain>/test_<domain>_capture.py` + `apps/admin/src/features/<domain>/capture/*.json` + `apps/admin/src/features/<domain>/*.contract.test.ts` — NEW per domain, though the PATTERN itself is not new |
| Reachability sweep report | Cross-reference of wired-but-unreachable screens | Feeds directly into DEFECT-REGISTRY rows; no separate artifact needed |
| Optional: `schema.d.ts`-vs-`z.infer` structural cross-check helper | Cheap compile-time belt-and-suspenders on top of capture-tests | e.g. `apps/admin/src/features/<domain>/schemas.typecheck.ts` per domain, OR one shared generic helper in `apps/admin/src/lib/` |
| Optional: `features/x → features/y` ESLint zone | Closes the Anti-Pattern 3 gap | Addition to `apps/admin/eslint.config.js` zones array — added LAST, after violations are fixed |
| Static dead-code tool invocation (`vulture`/`ts-prune` or equivalent) | One-time audit-phase sweep, not necessarily permanent CI | Run locally/in a throwaway CI job during audit; NOT wired into `.github/workflows/ci.yml` unless the roadmap explicitly decides to make it permanent |

### MODIFIED components (existing, changed IN PLACE — never redesigned)

| Component | What changes | Where |
|---|---|---|
| Per-domain `schemas.ts` | Field corrections where drift is found (nullable, type union, renamed key) | `apps/admin/src/features/<domain>/schemas.ts` |
| `router.tsx` | `<ComingSoon/>` → real lazy element for reachable-but-hidden screens found by the sweep | `apps/admin/src/app/router.tsx` |
| `nav-items.ts` | Add missing nav entry for the same screens | `apps/admin/src/layouts/AppLayout/nav-items.ts` |
| Dead/duplicated backend service code | Removed/consolidated within existing module boundaries — no module renamed, no new module created | `apps/backend/app/modules/*/service.py` etc. |
| Dead/duplicated frontend components | Removed/consolidated within existing `features/*`/`components/*` boundaries | `apps/admin/src/**` |
| TODO/FIXME/HACK markers | Closed (code changed + marker removed) or converted to a tracked, dispositioned registry `deferred` row — never left as a silent marker | wherever the 19 current hits live (re-enumerate at audit time; some may have been added/removed since this research) |
| Import-linter `.importlinter` | Only touched if a genuinely NEW legitimate cross-module edge is needed (rare, should be flagged `locked_invariant_risk`); otherwise UNCHANGED | `apps/backend/.importlinter` |
| 23 v4.0 operator-pending items | Triaged (not "fixed" in the code sense) into "provably local" (executed via `make backup`/`make up`/`make smoke` in k3d, evidence captured) vs. "genuinely needs real hardware/creds" (stays deferred, reason recorded in registry) | `infra/runbooks/production.md`, `.planning/STATE.md` "Deferred Items" |

### EXPLICITLY NOT touched / NOT redesigned

- `apps/backend/app/main.py` composition-root pattern (Protocol slots) — used as-is for any legitimate new cross-module wiring, never restructured.
- `packages/api-client` codegen pipeline (`openapi-typescript` → `schema.d.ts`) — untouched; the Zod layer stays where it is (Pattern 1).
- CI workflow structure (`.github/workflows/ci.yml` job boundaries: Backend / Frontend / Client PWA / Admin App / Redocly) — gates may gain NEW checks (e.g. a dead-code scan) but the job/stage topology is not restructured.
- RBAC model (`Role = 'owner' | 'reception'`, `OWNER_ONLY` list mechanism) — findings here are about byte-parity CORRECTNESS, never about redesigning to persisted-RBAC/Roles-editor (explicitly out of scope per `PROJECT.md`).

## Suggested Build Order (concrete, with rationale)

1. **Audit sub-phases run in parallel (read-only):**
   a. Browser-UAT functional sweep (`apps/admin` + `apps/client` against real backend, docker-compose stack)
   b. Static hygiene audit (TODO/FIXME/HACK grep, import-linter contract review, dead-code tool run, ESLint-boundary gap check per Anti-Pattern 3, feature-to-feature import grep)
   c. Infra triage (re-examine the 23 v4.0 operator-pending items against "provable locally with k3d" vs. "needs real hardware/creds")
   *Rationale: zero shared files, zero shared gates between these three — true parallelism, no ordering constraint.*

2. **Zod-vs-wire generalization sweep (part of 1a/1b, but calls out separately since it's the highest-value single action):** for every `features/<domain>/schemas.ts` lacking a `capture/*.json` + `*.contract.test.ts` pair, run the domain's real endpoints once via a capture test, diff the captured JSON against the current Zod schema by hand/eye, log any drift as a registry row.
   *Rationale: this single sweep, generalizing an already-proven pattern, directly targets the milestone's stated "Key context" lesson (mock↔real drift caught twice only by browser UAT) — it should be the audit phase's single most time-boxed-important activity, not an afterthought.*

3. **Registry freeze:** all three audit sub-phases converge into one `.planning/audits/v4.1-DEFECT-REGISTRY.md`, deduplicated (a browser-UAT finding and a capture-test finding for the same screen become ONE row), every row gets `id`/`category`/`severity`/`anchor`/`repro`/`evidence` filled, `disposition: open`.
   *Rationale: this is the explicit phase boundary — nothing downstream starts until this file stops changing shape (rows may still flip `disposition`, but the FINDING SET itself is closed).*

4. **Fix phases fan out, ordered by risk not by category:**
   a. **Functional fixes touching `locked_invariant_risk` rows FIRST** (anything referencing RBAC/audit-events/OpenAPI surface) — smallest blast radius, highest-value safety-rail verification, done while full attention is fresh.
   b. **Remaining functional fixes** (Zod schema corrections, router/nav reachability) — can run in parallel with (c) on disjoint files.
   c. **Hygiene fixes on files with NO functional-finding overlap** — parallel with (a)/(b).
   d. **Hygiene fixes on files WITH functional-finding overlap** — strictly AFTER the corresponding functional fix lands (registry `blocked_by` enforces this), to avoid concurrent-edit ambiguity on the same file.
   e. **Infra local-verify execution** (`make up`, `make smoke`, `make backup`, sealed-secrets off-node key backup to test storage) — fully parallel with a/b/c/d the whole time; only gated by k3d/toolchain availability, not by any app-code fix.
   *Rationale: risk-first within functional fixes catches the scariest regressions earliest; file-overlap-first within hygiene avoids the exact race condition named in Scaling Considerations' "first failure mode."*

5. **Full gate re-run** (`ruff`, `ruff format --check`, `mypy --strict`, `lint-imports`, `pytest`, `vitest`, `tsc`, ESLint, OpenAPI/`schema.d.ts` drift, Redocly lint) — after EVERY fix phase reports its dispositions, not once at the very end only; re-run incrementally as each fan-out branch lands, and once more, fully, before milestone-audit.
   *Rationale: this project's own precedent (every prior milestone) treats "full gate green" as the done-bar; re-running incrementally catches a hygiene regression before it compounds with the next phase's changes, cheaper to bisect early.*

6. **Milestone audit:** re-open the registry, confirm every row is `fixed+verified` or `deferred:<reason>` (no bare `open` rows survive), confirm the D-V40-LOCAL-VALIDATE boundary is honored for infra (no fabricated evidence for anything still genuinely operator-pending).
   *Rationale: mirrors this project's own `gsd-audit-milestone` convention already used at every prior close (`v3.0-MILESTONE-AUDIT.md`, `v4.0` audit, etc.) — the done-bar defined in `PROJECT.md`'s Current Milestone section is literally "every DEFECT-registry row fixed+verified or deferred with a reason; all gates green."*

## Sources

- Direct repo inspection (HIGH confidence, no external research needed for an internal-architecture-integration question):
  - `.planning/PROJECT.md` — Current Milestone v4.1 goal/scope/constraints, Current State domain table, STATE.md deferred-items ledger
  - `apps/backend/.importlinter` — both contracts, all `ignore_imports` edges and their rationale comments
  - `apps/backend/app/main.py` — composition-root Protocol-slot pattern and its documented exemption from `core-not-depend-on-modules`
  - `apps/backend/tests/integration/test_rbac_parity.py`, `test_route_introspection.py`, `test_phase51_route_introspection.py` — RBAC/route-introspection rail mechanics
  - `apps/backend/tests/unit/test_service_commit_gate.py`, `test_audit_taxonomy.py` — audit-event AST-gate mechanics
  - `apps/backend/tests/integration/promo_codes/test_promo_capture.py`, `apps/admin/src/features/promoCodes/promo.contract.test.ts` — the existing capture-then-contract-test pattern (worked example)
  - `apps/admin/src/features/clients/{schemas,api,query}.ts` — per-domain Zod/hooks seam shape
  - `apps/admin/eslint.config.js` — actual (not documented-only) ESLint boundary zones, confirming the feature-to-feature gap
  - `apps/admin/src/app/router.tsx`, `apps/admin/src/layouts/AppLayout/nav-items.ts` — reachability mechanism (`<ComingSoon/>` swap + nav registration)
  - `packages/api-client/src/schema.contract.test.ts` — `AssertNonNever` compile-time pattern reused as the recommended cross-check technique
  - `.github/workflows/ci.yml` — full gate inventory across Backend/Frontend/Client PWA/Admin App/Redocly jobs
  - `Makefile`, `infra/scripts/k3d-up.sh` — existing local infra-verification tooling (v4.0), confirmed NOT new work, only execution

---
*Architecture research for: v4.1 Codebase Hardening — audit-and-fix integration*
*Researched: 2026-07-26*
