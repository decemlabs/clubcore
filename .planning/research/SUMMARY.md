# Project Research Summary

**Project:** clubcore — v4.1 "Codebase Hardening"
**Domain:** Quality/tech-debt milestone on an existing, fully-shipped full-stack CRM (FastAPI modular monolith + two React SPAs + locally-validated k3s infra). No new product features.
**Researched:** 2026-07-26
**Confidence:** HIGH

## Executive Summary

This milestone has no natural "done" signal of its own — it must borrow one from a strict process contract, because the surface area (~10K+ LOC backend, ~19K+ LOC frontend, 9+ milestones of accretion, 32 TODO/FIXME/HACK markers, 23 v4.0 operator-pending items) is large enough that an open-ended "fix everything" goal never converges. All four researchers independently converged on the same structure: one read-only audit phase produces exactly one DEFECT registry; category-scoped fix phases consume it; every row ends in a terminal, evidence-backed disposition. This is not a novel process invented for this milestone — it generalizes patterns clubcore has already used successfully (the capture-then-contract-test pattern that closed the v3.0/v3.1 schema-drift bugs, the D-71-09 placeholder-graduation precedent, the D-V40-LOCAL-VALIDATE "no fabricated evidence" rule). The job here is to apply these already-proven patterns exhaustively, for the first time, across the whole codebase, rather than invent anything new.

The single highest-leverage finding across all four documents is that schema-drift hunting and route-reachability auditing are the same method wearing different clothes: build a complete, mechanical manifest of the thing being checked (every API call site + its Zod schema; every route × every nav entry × every real screen component), then check the entire manifest programmatically. The project's own history shows the opposite approach — screen-by-screen manual chasing — is exactly what let the same two bug classes (schema divergence, unreachable-but-wired screens) recur across multiple milestones despite being "caught" before. The recommended Zod-vs-wire fix is a two-layer generalization of an existing pattern (compile-time AssertEqual type-guard, modeled on the repo's own AssertNonNever helper, PLUS the existing capture-then-contract-test harness extended to all ~25 domains) — not a new tool, not a schema-generation rewrite.

The key risks are procedural, not technical: the audit phase never actually closing (scope creep, "while we're in here" upgrades, iterate-until-dry); deleting code that only looks dead in this codebase's specific dispatch patterns (ARQ string-dispatch, Protocol composition-root wiring, AST-gated frozensets, migration-referenced helpers); quietly regressing a LOCKED invariant (RBAC byte-parity, audit-event AST gate, OpenAPI drift gate, import-linter contracts) while "just cleaning up"; and reporting k3d-local infra work as if it closes v4.0's two HARD GATES (off-node sealed-secrets key custody, real-hardware restore round-trip) when it structurally cannot. Mitigating all of these is a matter of discipline enforced by the registry schema and phase-exit checklists, not new tooling investment.

## Key Findings

### Recommended Stack (tooling additions only — no product-stack changes)

This is a tooling-selection question, not a technology-stack question — the underlying stack (Python 3.12/FastAPI/SQLAlchemy async/Postgres/Redis/ARQ backend; React+Vite frontends) is locked and untouched.

**Repo-reality correction (load-bearing for all downstream planning):** `CLAUDE.md` and `apps/admin/CLAUDE.md` describe `apps/admin` as React 19 + Vite 6 + TanStack Router. The actual `apps/admin/package.json` pins `react@^18.3.1`, `vite@^5.4.14`, `react-router-dom@^6.28.2` — that description belongs to the deleted `apps/admin-web`. This is itself a registry-worthy HYGIENE finding (stale tech-stack prose), and — critically — all downstream planning (roadmap, phase plans, execution) must trust the code, not `CLAUDE.md`'s prose, until this doc drift is fixed.

**Core tooling additions, all zero-or-low-cost, all one-shot-first:**
- Compile-time `AssertEqual<z.infer<Schema>, GeneratedType>` (new: `packages/api-client/src/assert-equal.ts`) — zero new dependencies, extends the existing `AssertNonNever` pattern in `packages/api-client/src/schema.contract.test.ts`. Catches FE-Zod-vs-declared-OpenAPI-type drift at `tsc` time.
- Schemathesis 4.22.4 (new backend dev-dependency) — property-based testing against the live ASGI app via `schemathesis.openapi.from_asgi(...)`, GET-only scope first. Catches backend-runtime-vs-its-own-spec drift, which layer 1 cannot see.
- The existing "≥1 live-contract-test per domain" convention, formalized as one `*.live.test.ts` file per domain hitting a real running backend — catches integration-level surprises neither of the above two layers can see (proxy/header mangling, cookie non-round-trip).
- Knip 6.20.0 (unused exports/files, framework-aware) supersedes `ts-prune`; jscpd 5.0.12 (cross-language TS+Python duplication, Rust engine); vulture 2.16 + deptry 0.25.1 (Python whole-project dead-code and dependency-graph checks ruff cannot do). All run once as one-shot audit tools, triaged into the registry, not wired into CI as blocking gates until a clean baseline exists — this repo's dynamic-import lazy routes, Protocol-slot composition-root wiring, and intentional per-domain schema repetition would otherwise produce enough false positives that the tooling gets ignored.
- `@playwright/test` 1.62.0 for a deterministic, re-runnable route-sweep script (`e2e/route-sweep.spec.ts`) reading the real route/nav sources of truth — the mechanically re-runnable proof layer that an interactive `agent-browser` session cannot cheaply provide on repeat. Manual/on-demand only, never a PR-blocking gate.
- `trivy config` (the project's existing trivy install, already used for image scanning) extended to IaC misconfiguration scanning — the one genuinely new, zero-new-dependency infra addition. `kubeconform` and the CNPG restore-verify script are already in place and sufficient; do not add `chart-testing`, `kuttl`, `tflint`, Velero, or policy-as-code engines (all solve multi-team/multi-cluster problems this solo-maintainer single-cluster project doesn't have).

**Explicitly rejected** (would be scope growth, not convergence): `orval`/`openapi-zod-client`/`zodios` (wholesale Zod-from-OpenAPI codegen — would rewrite 17 hand-tuned schema files mid-hardening-milestone and lose Russian-locale form-validation rules the spec doesn't encode); Pact (solves a multi-service coordination problem this monolith doesn't have); Prism (backend has been live since v2.0); MSW-as-drift-detector (mocks cannot detect their own drift by construction).

### Expected "Features" (audit/fix activities, not product features)

**Must have (table stakes):**
- Reachability manifest (route × nav × real-screen three-way join) — cheapest static check, catches the FND-04 defect class
- Static hygiene sweep (TODO/FIXME/HACK grep, import-linter/ESLint boundary check, dead-code + duplication scan)
- Live-backend schema/wire-shape divergence hunt via a manifest-driven capture-and-diff harness — the single highest-yield defect class per this project's own history
- Browser UAT walk of every reachable screen against the real backend
- 23-item v4.0 operator-pending triage (doable-locally vs genuinely hardware-gated)
- One consolidated DEFECT registry
- Fix phases grouped by category, each closing with contract-test-proof
- Full-gate re-verification after every fix batch

**Should have (differentiators, cut if time-boxed):** promoting the schema-diff harness and reachability check to permanent CI artifacts; root-cause tagging on registry rows; a severity-weighted burndown view; a scripted (not just manual) k3d backup/restore round-trip.

**Anti-features (loud boundary, must not happen):** blanket coverage targets, mass reformatting bundled with logic fixes, speculative rearchitecting beyond restoring `import-linter` conformance, dependency bumps "while we're in there," iterate-until-dry auditing, fixing bugs inline during the audit pass without a registry row, screen-by-screen manual drift-chasing, and treating hardware-gated items as "must fix this milestone."

### Architecture Approach

The audit phase is a pure fan-in: three read-only sub-passes (browser-UAT functional audit, static hygiene audit, infra local-verify triage) write only to the registry, never to app code, so they are trivially parallel with zero collision surface. The registry is the hand-off contract — a single git-diffable Markdown table (not a database; over-engineered for dozens-of-findings scale), with mandatory fields `id, category, severity, anchor, repro, evidence, disposition, owning_phase, blocks/blocked_by, locked_invariant_risk`. Fix phases fan back out, gated by risk (fix `locked_invariant_risk` rows first) and by file-overlap (`blocked_by` sequences a hygiene fix after a functional fix touching the same file; unrelated files run in parallel).

**Major components (all existing, only the registry and a few thin sweep scripts are new):**
1. Capture-then-contract-test pattern (`apps/backend/tests/integration/<domain>/test_*_capture.py` → `apps/admin/src/features/<domain>/capture/*.json` → `*.contract.test.ts`) — already exists for ~5 of ~25 domains (promoCodes, payments-refund, messages, users-role-change, reports-load-now); the audit's job is to enumerate the ~20 domains lacking it, not invent the pattern.
2. Composition-root Protocol slots (`app/main.py`) — the one legitimate seam for any new cross-module wiring hygiene work might need; never a direct `app.modules.x → app.modules.y` import.
3. DEFECT-REGISTRY artifact (`.planning/audits/v4.1-DEFECT-REGISTRY.md`) — new, single source of truth.
4. Locked safety rails (RBAC byte-parity, `LOCKED_AUDIT_EVENTS`/`LOCKED_EMAIL_TEMPLATES` AST gates, OpenAPI/`schema.d.ts` drift gate, 3 import-linter contracts, admin ESLint boundaries) — unchanged, but every fix phase touching adjacent code must re-run the specific gate + its negative-test fixture as an explicit phase-exit criterion, not defer to "the milestone's final gate run."

### Critical Pitfalls (top 5 of 9, all project-specific, not generic)

1. The audit phase never closes — mitigate with a hard freeze: registry is produced once; anything found during a fix phase is appended with a `discovered-during-fix` tag, never triggers a new audit sweep; no dependency bumps unless the bump IS the registered fix.
2. Deleting code that only looks dead — this codebase has architecture-specific false positives (ARQ cron string-dispatch, Protocol slots registered only at `app/main.py`, migration-referenced helpers in `alembic/versions/*`, AST literal-string gates, lazy-loaded routes, python-telegram-bot string dispatch). Require full-repo STRING-literal grep (not just import-graph) plus explicit composition-root/ARQ-registration checks before any deletion; never delete based on one tool's confidence score alone.
3. The pre-existing broken pytest suite (fixture-ordering deadlock + carried flakes) is the verification tool being partly broken. Fix ONLY the deadlock, time-boxed, early — every later fix phase depends on this to prove anything. The other pre-existing flakes (F821, `test_alembic_clean`) are logged as their own registry rows and may legitimately end `deferred` — but the deadlock itself is not optional and not a rabbit-hole target either (time-box it; fall back to per-module fixture-scoped isolation if root-causing exceeds budget).
4. Regressing a LOCKED invariant while "just cleaning up" — any touch to RBAC enums/`can.ts`/`registry.ts`/`LOCKED_AUDIT_EVENTS`/`LOCKED_EMAIL_TEMPLATES`/OpenAPI/`.importlinter`/ESLint restricted-paths must update its parity mirror in the SAME commit and re-run the specific negative-test fixture to prove the gate still catches bad input, not just that it currently passes.
5. Verification-honesty erosion — merge PITFALLS' three-state model with FEATURES' explicit-reason requirement into one registry contract (see Merged Registry Contract below); mandate re-checkable evidence (command + output/artifact path, never prose); run a milestone-close spot-audit re-running a sample of cited evidence.

Plus two domain-specific deep dives that sharpen the headline finding: Pitfall 7 (edge-case seed data must be authored BEFORE the live-backend UAT hunt, or clean seeded data hides the exact null/empty/pagination/error-shape/DST-money edges that caused the original v3.0/v3.1 bugs) and Pitfall 9 (k3d cannot prove node-failure, off-node secret custody, real network topology, or storage durability — any k3d-derived registry item must carry an explicit `(k3d-scope)` qualifier and the original v4.0 items stay open, unedited).

## The Layered Zod-vs-Wire Recommendation (reconciled, one coherent order)

The four researchers describe the same fix from different angles (root cause, existing pattern, procedure, failure-mode prevention). Reconciled into one ordered recommendation:

1. Generalize the existing capture-then-contract-test pattern to every domain lacking it (~20 of ~25). This is the architecturally correct, already-proven seam (`apps/backend/tests/integration/<domain>/test_*_capture.py` → real JSON fixture → `apps/admin/src/features/<domain>/*.contract.test.ts` parsing it with the REAL production Zod schema). Do this FIRST — it is empirical (real response bytes), not another layer of trust-the-spec, and it is the literal fix that closed the v3.0/v3.1 bugs, just not applied everywhere yet.
2. Add the compile-time `AssertEqual<z.infer<Schema>, GeneratedType>` structural guard per domain, extending the repo's own `AssertNonNever` pattern in `packages/api-client/src/schema.contract.test.ts`. Zero new dependencies, rides the existing `tsc -b --noEmit` step. This is belt-and-suspenders on top of (1): it catches drift the OpenAPI spec already documents correctly but a hand-written Zod schema missed — a class of bug (1) alone would catch only if the seed data happens to exercise the diverging field.
3. Add Schemathesis (new backend dev-dependency, GET-only scope first) as the layer that catches what neither (1) nor (2) can see: the backend's actual runtime response violating its own declared OpenAPI spec — i.e., spec-vs-runtime drift, not spec-vs-Zod drift.
4. Do NOT derive Zod schemas mechanically from `schema.d.ts` (orval/openapi-zod-client/zodios) as a wholesale replacement. It doesn't address the actual failure mode (spec-vs-runtime, not spec-vs-Zod), would touch `packages/api-client`'s byte-stability drift gate (a locked invariant), would lose hand-tuned Russian-locale form-validation rules, and is exactly the kind of "architecturally cleaner" rewrite this hardening milestone must not do mid-flight.

Method, not just fix (headline finding): both this hunt and the reachability audit converge on the same discipline — build a complete manifest first (every API-call-site × Zod-schema pair; every route × nav-entry × real-screen-component triple), then check the whole manifest mechanically, once. Never screen-by-screen. Completeness becomes a property of the manifest's coverage, not of tester diligence — this is the literal antidote to the failure mode that let 6+ divergence bugs and multiple recurrences of the FND-04 reachability bug through prior milestones' unit tests and manual click-throughs.

The mandatory precondition for the hunt to work at all: an edge-case seed dataset must be authored BEFORE live-backend UAT begins — nullable fields actually null, empty-history entities, pagination past page 1, every error-family response (422/403/404/409/429/anti-oracle), and money/date DST-boundary values. Re-running the existing clean demo seed is not new evidence; it already passed with the same blind spots.

## Merged Registry Contract (one schema, all constraints reconciled)

A registry row is: `id, category, severity, anchor, repro, evidence, disposition, owning_phase, blocks/blocked_by, locked_invariant_risk, reason (if deferred)`.

Disposition is a three-state model, merging PITFALLS' and FEATURES' requirements:
- `fixed+verified` — evidence field names a re-checkable artifact (command + actual output, log path, screenshot path, or contract-test name) — never prose alone.
- `fixed+unverified` — code changed but proof is incomplete/missing. Not a legitimate final state for anything not explicitly deferred — this is a transient/flagged state that must resolve to `fixed+verified` or be re-tagged `deferred` before milestone close.
- `deferred` — final, valid, and expected for some rows. Requires an explicit reason: `operator-pending` (needs real hardware/credentials per D-V40-LOCAL-VALIDATE), `out-of-scope` (belongs to a different milestone/domain), or `accepted-risk` (understood, deliberately not worth fixing now). A `deferred` row is not revisited within this milestone once dispositioned.

Category (3, matching the milestone's own three directions): FUNC (functional bugs on real data — schema drift, crashing/unreachable screens), HYGIENE (code hygiene + architecture — dead code, duplication, layer-boundary violations, TODO/FIXME/HACK closure), INFRA (locally-provable production readiness — k3d apply, backup/restore round-trip, sealed-secrets key backup).

Severity (3-tier, compact for a solo-dev+AI-agent team): Blocker (crash / unusable / unreachable), Major (misbehaves without crashing), Minor (cosmetic / zero-behavioral-impact hygiene).

Milestone exit criterion: every registry row has a terminal disposition (`fixed+verified` or `deferred`+reason — no bare `open`, no lingering `fixed+unverified`) AND all existing CI gates are green. Checkable by a literal grep for undispositioned rows — a scriptable zero-count check, not a vibe. An all-`fixed+verified` result with zero `deferred` rows is itself a red flag given 23 known pre-existing operator-pending items.

## Implications for Roadmap

### Phase 1: Audit (single phase, three parallel read-only sub-passes)
Rationale: All four researchers agree this must be one phase, strictly before any fix work, because it is the only mechanism that makes "audit-once-then-fix" verifiable. The three sub-passes share zero files/gates and are genuinely parallel:
- 1a. Static hygiene sweep — no infra needed: TODO/FIXME/HACK grep, import-linter contract review, Knip/jscpd/vulture/deptry one-shot runs, the feature-to-feature ESLint boundary gap check (see Named Gap below), reachability three-way join (`router.tsx` × `nav-items.ts` × real screen components).
- 1b. Live-backend hunt — requires a running seeded backend (docker-compose/k3d): edge-case seed authoring FIRST (mandatory precondition), then the manifest-driven Zod-vs-wire capture-and-diff harness generalized across all ~25 domains, then browser UAT confirmation walk of every reachable screen.
- 1c. Infra triage — desk review of the 23 v4.0 operator-pending items against "provable locally with k3d" vs. "genuinely hardware/credential-gated," entirely independent of 1a/1b.
Delivers: One frozen `.planning/audits/v4.1-DEFECT-REGISTRY.md` snapshot.
Avoids: Pitfalls 1 (scope creep), 7 (well-formed-data blind spot), 8 (reachability misses).

### Phase 2: Test-infra unblock (early, time-boxed, narrow)
Rationale: Every later fix phase's `fixed+verified` disposition depends on being able to run tests at all. Fix ONLY the autouse-fixture deadlock, time-boxed; fall back to per-module isolation if root-causing exceeds budget. Do not let this phase expand into full test-suite archaeology.
Delivers: A pytest suite that either runs to completion or has a documented, scoped isolation workaround.
Avoids: Pitfall 4 (rabbit-holing vs. unverified shipping).

### Phase 3: FUNC fix phase(s) — risk-first ordering within
Rationale: Highest-yield category per project history; verified by contract-test-proof per divergence type (extending Phase 1's harness output into permanent fixtures) + reachability re-check.
Ordering within phase: fix `locked_invariant_risk`-flagged rows first (smallest blast radius, highest-value safety-rail verification while attention is fresh), then remaining Zod/router/nav fixes.
Addresses: FUNC category rows from the registry.
Avoids: Pitfall 5 (LOCKED invariant regression) via same-commit parity-mirror updates + negative-fixture re-runs.

### Phase 4: HYGIENE fix phase
Rationale: Verified by re-running the full existing static gate suite (ruff, mypy --strict, import-linter, ESLint, tsc) rather than new tests — hygiene work should almost never need new test files; if it does, that's a sign scope silently expanded into FUNC territory.
Sequencing: Rows on files with zero FUNC overlap can run in full parallel with Phase 3; rows on files WITH overlap must serialize after the corresponding FUNC fix lands (`blocked_by` in the registry) to avoid concurrent-edit ambiguity.
Includes: closing TODO/FIXME/HACK markers (fix or convert to a dispositioned `deferred` row, never left silent), dead-code removal per the false-positive-safe procedure, adding the missing `features/x → features/y` ESLint zone — added LAST, after violations are fixed, so the gate doesn't fail on pre-existing debt mid-milestone.
Avoids: Pitfalls 2 (mass reformatting — isolated commits only), 3 (false-positive dead-code deletion).

### Phase 5: INFRA fix phase — fully parallel track
Rationale: Zero file/gate overlap with FUNC/HYGIENE (Terraform/Helm/k3d vs. Python/TS toolchains) — can and should run concurrently with Phases 3–4 to shorten wall-clock time, gated only by k3d/toolchain availability.
Delivers: Execution + evidence capture against the ALREADY-EXISTING v4.0 scripts (`make up`, `make smoke`, `make backup`, `restore-verify.sh`) plus the new `trivy config` IaC scan — this is execution, not new tool-building.
Must record: every finding with an explicit `(k3d-scope)` qualifier; the original v4.0 HARD GATE items (SEC-02, BAK-03) remain open and unedited in the registry, referenced alongside the new narrower k3d findings, never replaced by them.
Avoids: Pitfall 9 (k3d mistaken for production-equivalent proof).

### Phase 6: Registry consolidation + milestone close (short closing step, not a full phase)
Rationale: Mechanically cheap but must be an explicit checkpoint — re-open the registry, confirm every row is `fixed+verified` or `deferred`+reason (no bare `open`, no lingering `fixed+unverified`), run a milestone-close spot-audit re-running a sample of cited evidence, confirm all CI gates green, confirm the D-V40-LOCAL-VALIDATE boundary is honored (no fabricated evidence on anything still genuinely operator-pending).
Avoids: Pitfall 6 (verification-honesty erosion).

### Phase Ordering Rationale

- Audit strictly precedes all fix work — enforced as a phase-boundary rule (read-only, no Edit/Write to app code during audit), not just a convention, per the Architecture research's identified "first failure mode."
- Test-infra unblock comes early because it's the verification tool every later phase depends on — but is deliberately narrow and time-boxed to avoid becoming its own uncontrolled sub-project.
- FUNC before HYGIENE within any shared file, but the two remain separate phases at the roadmap level since most files aren't touched by both — this avoids the "second failure mode" (concurrent edits on the same file making a later revert ambiguous).
- INFRA is fully parallel to FUNC/HYGIENE the entire time — no reason to serialize a subsystem that shares no files or CI gates.
- Registry consolidation and final close are checklist passes, not new work, mirroring this project's own gsd-audit-milestone precedent used at every prior milestone close.

### Research Flags

Phases likely needing deeper research during planning:
- Phase 1 (audit), sub-pass 1b specifically: the exact shape of the edge-case seed-data authoring task (which entities/lifecycle states/error families) may need a short planning-time research pass per domain, since PITFALLS' matrix is a starting checklist, not a domain-by-domain enumeration.
- Phase 4 (HYGIENE): the open decision of whether dead-code tooling stays one-shot-forever or graduates to a CI gate needs an explicit planning-time decision (see Open Decisions below) — this affects whether Phase 4 includes a "wire Knip/jscpd/deptry into CI" sub-task.

Phases with standard patterns (skip research-phase, well-documented in this research already):
- Phase 2 (test-infra unblock): root cause and fallback are already fully specified (fixture-ordering deadlock, per-module isolation workaround).
- Phase 3 (FUNC fixes): the capture-then-contract-test + AssertEqual + Schemathesis layering is fully specified with a concrete code example.
- Phase 5 (INFRA): pure execution of already-existing v4.0 scripts plus one new trivy config wrapper script mirroring an existing pattern — no new research needed.

### Open Decisions Left for Planning (deliberately not resolved by research)

1. One-shot vs. CI-gated dead-code/duplication tooling (Knip, jscpd, vulture, deptry). All four researchers agree: run once during audit, triage into the registry, and wire into CI only after a clean baseline — but whether that graduation actually happens in v4.1 (a P2 differentiator per FEATURES) or is deferred to v4.2 is an explicit roadmap decision, not a research conclusion. `deptry` is called out as safe to wire immediately (low false-positive rate); Knip/jscpd should stay manual/local longer given this repo's dynamic-import lazy routes and intentional per-domain repetition.
2. Whether `apps/client` gets the same Zod/contract-test treatment as `apps/admin`, or is accepted as out of scope. STACK confirms `apps/client` has zero `zod` dependency today — its `client_auth`/`client_portal` consumers have no runtime response validation at all. Introducing `zod` there is a bigger lift (new dependency + net-new schema authoring, not "extend an existing pattern") than generalizing `apps/admin`'s existing 5-of-25 coverage. The roadmap must explicitly decide: (a) in-scope for v4.1 with its own fix-phase allocation, (b) logged as a `deferred:out-of-scope` registry row for a future milestone, or (c) partial — e.g., only the highest-risk `client_auth` endpoints. Research does not pick one; it flags the asymmetry.
3. Exact severity taxonomy and DEFECT-id scheme beyond the merged 3×3×3 contract above — the researchers converge on the shape (3-tier severity, 3-category, sequential DEFECT-NNN ids never renumbered) but the roadmapper/planner should confirm this against actual registry volume once the audit phase produces real numbers (dozens expected, not hundreds — if hundreds materialize, split the registry per-category, but do not pre-optimize for that).
4. Whether the `trivy config` IaC scan and the Playwright route-sweep graduate to CI-gated checks or stay permanently manual/on-demand — both are recommended as manual/`workflow_dispatch`-only for v4.1 explicitly to avoid becoming the next flaky/ignored gate; a future milestone can revisit.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All tool versions verified live (npm/PyPI/GitHub releases, 2026-07-26); all "already have it" claims verified by reading actual repo files (Makefile, scripts, package.json), not assumed from the brief |
| Features | HIGH (process/practice claims), MEDIUM (procedures (c)/(d) step-by-step, which are synthesized/adapted rather than verbatim-cited — no single external source describes clubcore's exact stack) | Cross-checked against multiple independent industry sources (defect taxonomy, contract testing, feature-flag-cleanup audit practice) and against the project's own PROJECT.md lessons |
| Architecture | HIGH | Grounded entirely in direct repo inspection — file paths, existing test patterns, CI gate config, .importlinter contracts, actual ESLint config content (not just documented conventions) |
| Pitfalls | HIGH | Grounded directly in this repo's locked invariants, documented decisions (D-V40-LOCAL-VALIDATE, D-71-09, D-20-MODULE, D-62-09), and its own two-time-repeated defect class — not generic advice |

**Overall confidence:** HIGH

### Gaps to Address

- Real registry volume is unknown until the audit phase runs. All sequencing/parallelism guidance assumes "dozens, not hundreds" of findings; if volume is much higher, the single-Markdown-file registry format and the phase structure above should be revisited (split per category) rather than forced.
- Exact list of domains lacking the capture-then-contract-test pattern is enumerated qualitatively (~20 of ~25) but not exhaustively named in research — Phase 1's static sweep must produce the definitive list.
- The precise current TODO/FIXME/HACK count (research cites "32" from PROJECT.md context and "19" from a direct grep at research time — these may have drifted since) must be re-derived fresh at audit time, not assumed from either research document.
- `apps/client` Zod-adoption decision (Open Decision #2 above) has real cost implications for phase sizing and is unresolved by design — must be settled during roadmap/phase-planning, not silently defaulted either way.

## Sources

### Primary (HIGH confidence — direct repo inspection)
- `apps/admin/package.json`, `apps/client/package.json` — actual dependency versions (React 18.3.1/Vite 5.4 vs. documented React 19/Vite 6)
- `apps/admin/src/api/client.ts`, `apps/admin/src/features/*/schemas.ts` (17 files), `packages/api-client/src/schema.d.ts`, `schema.contract.test.ts` — the AssertNonNever pattern and the Zod-vs-generated-type gap
- `apps/backend/tests/integration/promo_codes/test_promo_capture.py`, `apps/admin/src/features/promoCodes/promo.contract.test.ts` — the existing capture-then-contract-test worked example
- `apps/backend/.importlinter`, `apps/backend/app/main.py`, `apps/backend/tests/integration/test_rbac_parity.py`, `test_route_introspection.py`, `apps/backend/tests/unit/test_service_commit_gate.py`, `test_audit_taxonomy.py` — locked invariant mechanics
- `apps/admin/eslint.config.js` — confirmed the feature-to-feature import boundary is convention-only, not machine-enforced
- `Makefile`, `infra/scripts/{restore-verify,smoke,scan-images}.sh` — already-implemented infra verification (kubeconform, CNPG restore round-trip, 8-check smoke)
- `.planning/PROJECT.md` — v3.0/v3.1 schema-drift lesson, D-71-09/FND-04 reachability lesson, D-V40-LOCAL-VALIDATE, 23-item v4.0 operator-pending boundary with 2 HARD GATES
- `.github/workflows/ci.yml` — full existing CI gate inventory

### Secondary (verified live, current as of 2026-07-26)
- npm registry: `@playwright/test@1.62.0`, `knip@6.20.0`, `jscpd@5.0.12`
- PyPI: `schemathesis@4.22.4`, `vulture@2.16`, `deptry@0.25.1`
- GitHub Releases: `helm/chart-testing@v3.14.0`, `kudobuilder/kuttl@v0.26.0` (both evaluated and rejected)
- Industry practice sources on defect taxonomy, hardening-sprint anti-patterns, contract testing, feature-flag-cleanup audits, Chesterton's Fence / scope-creep-in-refactoring (see FEATURES.md Sources for full list)

---
*Research completed: 2026-07-26*
*Ready for roadmap: yes*
