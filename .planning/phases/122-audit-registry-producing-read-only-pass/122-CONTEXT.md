# Phase 122: Audit — Registry-Producing Read-Only Pass - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning
**Mode:** `--auto` (all gray areas auto-resolved to the recommended option; every choice logged below)

<domain>
## Phase Boundary

This phase produces **exactly one frozen defect registry** — `.planning/audits/v4.1-DEFECT-REGISTRY.md` — covering three read-only sub-passes that share zero files and run in parallel:

- **1a — Static hygiene sweep** (no running infra): TODO/FIXME/HACK/XXX enumeration, one-shot Knip/jscpd/vulture/deptry, review of the 3 import-linter contracts + admin ESLint boundaries, and the three-way reachability manifest (`router` × `nav-items` × real screen component) for `apps/admin` and `apps/client`.
- **1b — Live-backend hunt** (needs a running seeded backend): edge-case seed dataset authored FIRST, then the mechanical Zod↔wire manifest across all `apps/admin/src/features/*` domains, then a browser UAT walk of every reachable screen against the real backend on that seed.
- **1c — Infra triage** (desk review): the v4.0 operator-pending items split into "provable locally in k3d `(k3d-scope)`" vs "genuinely hardware/credential-gated".

**Zero app-code edits.** The phase finds and records; it does not fix. Anything found later during a fix phase is appended to the frozen registry with a `discovered-during-fix` tag — it never triggers a second audit sweep (D-V41-AUDIT-FREEZE).

**Not this phase:** fixing anything found (Phases 123-126), wiring any tool into CI (Phase 125 / HYG-06), closing the v4.0 HARD GATEs (never in v4.1).

</domain>

<decisions>
## Implementation Decisions

### Registry artifact shape

- **D-122-01:** The registry is **one file** — `.planning/audits/v4.1-DEFECT-REGISTRY.md` — containing a YAML-ish frontmatter header plus **three Markdown tables**, one per category section (`## FUNC` / `## HYGIENE` / `## INFRA`). Not a database, not three files. Research explicitly says "dozens, not hundreds" of rows; a per-category file split is a contingency if volume explodes, **not** a pre-optimization.
  — **Reversibility:** reversible — a Markdown table can be re-shaped by any later phase; no consumer parses it programmatically except the CLOSE-01 grep.
- **D-122-02:** Row IDs are **category-prefixed and sequential, never renumbered**: `V41-FUNC-001`, `V41-HYG-001`, `V41-INFRA-001`. Category-prefixed (not one flat `DEFECT-NNN` sequence) because the three sub-passes allocate IDs concurrently — a flat sequence would collide. Gaps in a sequence are allowed and expected; an ID is permanent once written, even if the row is later merged or reclassified (record the reclassification in the row, do not reuse the ID).
  — **Reversibility:** costly — IDs are cross-referenced from fix-phase commits, plans, and `blocked_by` fields; renumbering breaks that trail.
- **D-122-03:** Row schema is exactly the locked contract from `REQUIREMENTS.md` — `id, category, severity, anchor, repro, evidence, disposition, owning_phase, blocks/blocked_by, locked_invariant_risk, reason (if deferred)`. Do not add columns. `anchor` = `path:line` or `path` + symbol. `evidence` at audit time is the **discovery** artifact (command + output path); it is overwritten by the **fix** artifact when the row reaches `fixed+verified`.
  — **Reversibility:** costly — the schema is the hand-off contract to four downstream phases and the CLOSE-01 mechanical check.
- **D-122-04:** **Concurrent-write protocol.** The three sub-passes never write the registry file directly. Each writes its own staging file under `.planning/audits/staging/` (`1a-hygiene.md`, `1b-live.md`, `1c-infra.md`); a final merge task concatenates them into the single registry at freeze time. This preserves "exactly one registry" (AUD-01) while making the three sub-passes genuinely parallel with zero merge conflicts. Staging files are deleted in the freeze commit.
  — **Reversibility:** reversible — purely a working-file convention.
- **D-122-05:** **"Frozen" is mechanical, not a promise.** The freeze commit records in the registry header: `frozen_at_commit: <sha>`, `frozen_at: <ISO date>`, `row_count_at_freeze: <N>`. Post-freeze additions go only into a trailing `## Discovered during fix` section, each row tagged `discovered-during-fix` and carrying the phase that found it. The main three tables are append-nothing after freeze; only the `disposition` and `evidence` cells of existing rows may change.
  — **Reversibility:** reversible.

### Supporting audit artifacts (manifests are NOT the registry)

- **D-122-06:** The registry holds **defects only**. The full manifests are separate audit artifacts that registry rows reference by row id:
  - `.planning/audits/v4.1-REACHABILITY-MANIFEST.md` (AUD-03)
  - `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.md` (+ `.json` sibling) (AUD-05)
  - `.planning/audits/v4.1-EDGE-SEED-MATRIX.md` (AUD-04)
  - `.planning/audits/v4.1-UAT-BROWSER-WALK.md` (AUD-06)
  - `.planning/audits/v4.1-HYGIENE-RAW/` — raw tool output archive (AUD-02)
  Rationale: a manifest proves **coverage** (the headline research finding — completeness is a property of the manifest, not of tester diligence); the registry proves **defects**. Mixing them makes CLOSE-01's "grep for undispositioned rows" unreliable.
  — **Reversibility:** reversible.

### AUD-03 — Reachability manifest

- **D-122-07:** Built by a script, not by hand: `tools/audit/reachability-manifest.mjs` performs the three-way join and emits the manifest. Sources are concrete and confirmed to exist:
  - `apps/admin`: `apps/admin/src/app/router.tsx` + `apps/admin/src/app/routes.ts` × `apps/admin/src/layouts/AppLayout/nav-items.ts` × the real screen component file.
  - `apps/client`: `apps/client/src/routes/**` × its nav source × `apps/client/src/screens/**`.
  A screen resolving to a `ComingSoon`/placeholder component counts as **NOT reachable** and gets a registry row — this is the exact FND-04 failure class that recurred across v3.0 and v3.2. A route present with no nav entry is likewise a row (reachable only by URL ≠ reachable).
  — **Reversibility:** reversible — the script is a throwaway audit tool.

### AUD-05 — Zod↔wire manifest

- **D-122-08:** Built by a script: `tools/audit/zod-wire-manifest.mjs` walks `apps/admin/src/features/*` and emits one row per **(feature domain, API call-site, Zod schema, backend endpoint, capture-fixture present y/n, contract-test present y/n)**. Mechanical, one pass, all domains — never screen-by-screen.
  — **Reversibility:** reversible.
- **D-122-09:** **The manifest's `capture-fixture present` column IS the definitive Phase-124 input list** (closing the STATE.md Research Flag for Phase 124). Ground truth measured during scouting: `apps/admin/src/features/` holds **29** domain directories, of which **5** have the capture-then-contract-test pattern (`promoCodes`, `reports`, `payments`, `messages`, `users`). The roadmap's "~20 of ~25" is an estimate — the manifest replaces it with the real number, and the planner must not treat "~25" as authoritative.
  — **Reversibility:** reversible.
- **D-122-10:** Divergences are found by **comparing the manifest against real captured response bytes**, not against `apps/backend/openapi.json`. Spec-vs-Zod comparison is Phase 124's `AssertEqual` layer; spec-vs-runtime is Phase 124's Schemathesis layer. Phase 122's job is the empirical layer — what the live backend actually returned on the edge-case seed vs what the production Zod schema accepts.
  — **Reversibility:** reversible.

### AUD-04 — Edge-case seed dataset

- **D-122-11:** Delivered as **one new idempotent script**, `apps/backend/scripts/seed_edge_cases.py`, following the existing `apps/backend/scripts/seed_*.py` convention (`seed_demo_data.py`, `seed_verification_fixtures.py` are the models). It is **additive on top of** the demo seed, never a replacement — it adds the edges the clean demo seed structurally cannot contain.
  — **Reversibility:** reversible — new file, deleted or promoted later at zero cost.
- **D-122-12:** The matrix it must produce (from PITFALLS + AUD-04, to be enumerated per domain at plan time — this is the acknowledged Research Flag for sub-pass 1b): nullable fields **actually null**; entities with **empty history** (client with zero visits, trainer with zero bookings, empty chat thread); **pagination past page 1** (enough rows to force page 2+); every **error family** (422/403/404/409/429 + the anti-oracle case); **money** boundaries (zero, negative/refund, very large kopeck values); **DST/TZ** boundaries in `Europe/Moscow`. Re-running the clean demo seed is **explicitly not evidence** for any AUD-04 claim.
  — **Reversibility:** reversible.
- **D-122-13:** Sub-pass 1b runs against the **local docker-compose stack**, not k3d. k3d is 1c/Phase-126 territory. Known local-stack gotchas (env reload on compose, stale-image migrate, seed/pytest interaction) are plan-time preconditions, not discoveries.
  — **Reversibility:** reversible.

### AUD-06 — Browser UAT walk

- **D-122-14:** The walk uses the **chrome-devtools MCP** interactively. **No Playwright is introduced in v4.1** — a Playwright route-sweep is `TOOL-02`, explicitly deferred to v4.2 in `REQUIREMENTS.md`, and there is currently zero Playwright anywhere in the repo. Building a net-new E2E harness inside a read-only audit phase is exactly the "while we're in here" scope creep this milestone bans.
  — **Reversibility:** reversible.
- **D-122-15:** Output format **mirrors the existing precedent** `.planning/v3.0-UAT-BROWSER-AUDIT.md` / `v3.1-` / `v3.2-` — per-screen rows with verdict, console errors, and screenshot path. Every crash, empty state, and console error becomes a registry row; a clean screen becomes a manifest row only.
  — **Reversibility:** reversible.
- **D-122-16:** Walk preconditions, treated as checklist steps rather than as bugs when they bite: hard-reload / unregister service worker before each session (a stale SW silently serves old code and masks the very drift being hunted), use dev login, confirm the edge-case seed is the loaded dataset (not a fresh demo reseed).
  — **Reversibility:** reversible.

### AUD-02 — Hygiene tooling

- **D-122-17:** **None of Knip / jscpd / vulture / deptry is installed in this repo today** (verified — no config, no dependency entries). They run via **ephemeral pinned runners, adding zero repo dependencies**: `pnpm dlx knip@6.20.0`, `pnpm dlx jscpd@5.0.12`, `uvx vulture==2.16`, `uvx deptry==0.25.1`. Any throwaway config lives under `tools/audit/`. Raw output is archived under `.planning/audits/v4.1-HYGIENE-RAW/` so triage decisions stay auditable.
  — **Reversibility:** reversible.
- **D-122-18:** **Every finding is triaged into a registry row — including the ones judged false positives.** A false positive gets a row with disposition `deferred:accepted-risk` and a reason naming the dispatch pattern that makes it a false positive (ARQ cron string-dispatch, Protocol slot registered only in `app/main.py`, `alembic/versions/*` reference, `LOCKED_AUDIT_EVENTS`/`LOCKED_EMAIL_TEMPLATES` AST gate, lazy-loaded route, python-telegram-bot string dispatch). Silently discarding tool output at audit time is what makes Phase 125's dead-code deletions unsafe.
  — **Reversibility:** reversible.
- **D-122-19:** The TODO/FIXME/HACK/XXX count is **re-derived fresh**, never quoted from prior docs. A scouting grep at context time returned **35** markers across `apps/ packages/ infra/ tools/` — versus "32" in `PROJECT.md` and "19" in the research documents. All three numbers are stale by construction; the audit's own grep is the only authority, and its exact command must be recorded in the registry as the evidence artifact.
  — **Reversibility:** reversible.
- **D-122-20:** The import-linter review covers the **3 contracts** in `apps/backend/.importlinter` (count verified). The missing `features/x → features/y` admin ESLint zone is **assessed and rowed here, added in Phase 125 and added LAST** (D-V41-ESLINT-ZONE-LAST) — Phase 122 records how many violations exist on it, and does not enable it.
  — **Reversibility:** reversible.

### AUD-07 — Infra triage

- **D-122-21:** **Authoritative source is `infra/runbooks/production.md` § Operator-Pending Boundary** (starts at line 421). The four v4.0 `*-UAT.md` files (`.planning/milestones/v4.0-phases/{118,119,120,121}-*/1NN-UAT.md`) are cross-referenced per row for the original wording, but the runbook is the list.
  — **Reversibility:** reversible.
- **D-122-22:** **The count 23 is re-derived, not assumed.** If the runbook yields a different number, the registry records the real count and adds a row flagging the discrepancy with STATE.md — it does not force-fit 23. (STATE.md's own tally is `4 + 10 + 9 + 4 = 27` UAT items across the four phases plus a planning item; the "23" figure needs reconciliation, and that reconciliation is itself an audit output.)
  — **Reversibility:** reversible.
- **D-122-23:** The two v4.0 HARD GATEs (**SEC-02** off-node sealed-secrets RSA-key custody, **BAK-03** verified restore round-trip) get registry rows that are **`deferred:operator-pending` and stay that way for all of v4.1**. Phase 126's k3d work produces *new, narrower* `(k3d-scope)` rows that reference them — never edits, closes, or replaces them (D-V41-K3D-SCOPE).
  — **Reversibility:** one-way in spirit — editing a HARD GATE row to look closed destroys the honesty guarantee the whole milestone rests on; that is the outcome this decision exists to prevent.

### AUD-08 — Read-only enforcement

- **D-122-24:** Read-only is **enforced mechanically at phase close, not by convention.** A verification task runs `git diff --name-only <phase-start-sha>..HEAD` and asserts every path matches this allowlist:
  - `.planning/**` (registry, manifests, phase artifacts)
  - `tools/audit/**` (new files only)
  - `apps/backend/scripts/seed_edge_cases.py` (**new file only**)
  Any other path — in particular any *modification* to an existing file under `apps/`, `packages/`, or `infra/` — is a phase-exit failure. Success Criterion 7 permits *adding* dedicated audit-sweep scripts; it does not permit touching app code.
  — **Reversibility:** reversible — but the check must exist as an explicit plan task, or SC-7 is unprovable.
- **D-122-25:** If a defect is trivially fixable during the sweep, it is **still not fixed here.** It gets a row and waits for its owning phase. This is the single mechanism that makes "audit once, then fix" verifiable (Pitfall 1) and it has no exceptions.
  — **Reversibility:** reversible.

### Claude's Discretion

Auto-mode resolved every area above to the recommended option. The following remain genuinely open for the planner/researcher and are **not** locked here:

- The per-domain enumeration of the edge-case seed matrix (D-122-12 gives the axes; the domain × axis grid is plan-time work — this is the acknowledged Research Flag for sub-pass 1b).
- Exact parsing strategy inside the two manifest scripts (AST vs regex vs `ts-morph`) — an implementation detail, provided the output is complete and mechanically produced.
- Whether the three sub-passes become three parallel plans or one plan with three waves — a planner sequencing call; the zero-file-overlap property (D-122-04) makes either safe.

### Folded Todos

None. The single todo match (`2026-06-02-future-milestones-sequence-post-v2-1.md`, score 0.9) was reviewed and **not** folded — see Deferred Ideas.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone contract (read first)
- `.planning/REQUIREMENTS.md` — AUD-01..08 verbatim, the locked Registry contract (row schema, 3-state disposition, 3 categories, 3 severities), and the Out-of-Scope anti-feature table
- `.planning/ROADMAP.md` § "Phase 122" (lines 502-518) — goal + 7 success criteria; § "v4.1 Codebase Hardening" (lines 483-501) — hard ordering, the two settled forks, the k3d-honesty constraint
- `.planning/STATE.md` § "v4.1 Architecture Context" — D-V41-AUDIT-FREEZE, D-V41-CLIENT-SCOPE, D-V41-HYGIENE-TOOLING, D-V41-ESLINT-ZONE-LAST, D-V41-K3D-SCOPE; § "Deferred Items" — the operator-pending ledger that AUD-07 triages; § "Research Flags"

### Research (the method this phase implements)
- `.planning/research/SUMMARY.md` § "Merged Registry Contract" (lines 83-96) — the reconciled row schema and milestone exit criterion
- `.planning/research/SUMMARY.md` § "The Layered Zod-vs-Wire Recommendation" (lines 70-81) — why manifest-first, and the mandatory edge-case-seed precondition
- `.planning/research/SUMMARY.md` § "Phase 1: Audit" (lines 100-106) — the three-sub-pass decomposition
- `.planning/research/PITFALLS.md` — Pitfall 1 (audit never closes), 2 (false-positive dead code), 7 (well-formed-data blind spot), 9 (k3d ≠ production proof)
- `.planning/research/STACK.md` — pinned versions for the four one-shot hygiene tools

### Reachability sources (AUD-03)
- `apps/admin/src/app/router.tsx`, `apps/admin/src/app/routes.ts` — admin route table
- `apps/admin/src/layouts/AppLayout/nav-items.ts` — admin nav entries
- `apps/admin/src/app/router-smoke.test.tsx` — existing smoke test over the router; shows what is already asserted
- `apps/client/src/routes/`, `apps/client/src/screens/` — client route + screen sources

### Zod↔wire sources (AUD-05)
- `apps/admin/src/features/` — 29 domain directories (the manifest's row space)
- `apps/admin/src/features/promoCodes/promo.contract.test.ts` — the canonical capture-then-contract-test example to pattern-match against
- `apps/admin/src/features/{promoCodes,payments,reports,messages,users}/capture/` — the 5 existing capture-fixture dirs
- `apps/backend/tests/integration/promo_codes/test_promo_capture.py` — the backend-side capture producer
- `packages/api-client/src/schema.contract.test.ts` — the `AssertNonNever` pattern that Phase 124's `AssertEqual` guard extends (read for context; do not modify)
- `apps/backend/openapi.json` — the declared contract (reference only; NOT the comparison baseline per D-122-10)

### Seed sources (AUD-04)
- `apps/backend/scripts/seed_demo_data.py` — the clean baseline the edge seed sits on top of
- `apps/backend/scripts/seed_verification_fixtures.py`, `apps/backend/scripts/seed_v1_4_verification_fixtures.py` — the script convention to follow

### Infra triage sources (AUD-07)
- `infra/runbooks/production.md` § "Operator-Pending Boundary" (line 421+) — **authoritative item list**, including HARD GATE 1 (SEC-02) and HARD GATE 2 (BAK-03)
- `infra/runbooks/restore.md`, `infra/runbooks/sealed-secrets-key-backup.md` — the two deep-dive runbooks the HARD GATEs point at
- `.planning/milestones/v4.0-phases/118-*/118-UAT.md`, `119-*/119-UAT.md`, `120-*/120-UAT.md`, `121-*/121-UAT.md` — original per-item wording
- `Makefile` — the already-existing targets (`up`, `smoke`, `backup`, `deploy`) that Phase 126 will execute; each is already annotated OPERATOR-PENDING

### Locked-invariant mechanics (flag `locked_invariant_risk` on any row touching these)
- `apps/backend/.importlinter` — 3 contracts
- `apps/backend/app/main.py` — composition root; Protocol slots registered only here
- `apps/backend/tests/integration/test_rbac_parity.py`, `test_route_introspection.py`
- `apps/backend/tests/unit/test_service_commit_gate.py`, `test_audit_taxonomy.py`
- `apps/admin/src/**/can.ts` (RBAC mirror), `LOCKED_AUDIT_EVENTS` / `LOCKED_EMAIL_TEMPLATES` frozensets
- `.github/workflows/ci.yml` — the single CI gate file (read to know what "all gates green" means; do not modify in this phase)

### Browser-walk precedent (AUD-06)
- `.planning/v3.0-UAT-BROWSER-AUDIT.md`, `.planning/v3.1-UAT-BROWSER-AUDIT.md`, `.planning/v3.2-UAT-BROWSER-AUDIT.md` — output format to mirror, and a catalogue of the exact failure classes this walk is hunting

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Capture-then-contract-test harness** — already working end-to-end for 5 of 29 admin domains (`promoCodes`, `reports`, `payments`, `messages`, `users`), with matching backend producers under `apps/backend/tests/integration/*/test_*_capture.py`. Phase 122 does not build it; it enumerates who lacks it.
- **`seed_*.py` script convention** — 5 existing seed scripts under `apps/backend/scripts/`; the edge-case seed is a sixth, not a new mechanism.
- **`router-smoke.test.tsx`** — an existing admin router smoke test; the reachability manifest should reconcile against what it already covers rather than duplicating it.
- **`packages/api-client` `AssertNonNever` pattern** — the type-level assertion idiom the milestone reuses in Phase 124; relevant to Phase 122 only as the reason NOT to introduce Zod codegen.
- **Prior UAT browser-audit documents** (v3.0/v3.1/v3.2) — a proven output format and a ready-made checklist of recurring failure classes.
- **`Makefile`** — every infra target already exists and is already annotated OPERATOR-PENDING; AUD-07 triage is reading annotations, not inventing a taxonomy.

### Established Patterns
- **Manifest-first, never screen-by-screen.** The project's own history is the evidence: screen-by-screen chasing let 6+ schema-divergence bugs and multiple FND-04 reachability recurrences through. Completeness must be a property of a mechanically-generated manifest.
- **Evidence is an artifact, never prose.** A command plus its output path, a log path, a screenshot path, or a contract-test name. This is inherited from D-V40-LOCAL-VALIDATE / D-72-06 and is non-negotiable in every registry row.
- **`tools/` currently holds only `tools/newman/`** — `tools/audit/` is a clean new namespace with no collision risk.

### Integration Points
- **Registry → Phases 123-127.** Every later phase consumes registry rows by ID. `owning_phase` assigned at audit time is what makes the fix phases plannable; `blocked_by` is what serializes Phase 125 behind Phase 124 on shared files.
- **Zod↔wire manifest → Phase 124 scope.** Its `capture-fixture present` column is the definitive FUNC-01 work list.
- **Reachability manifest → FUNC-05.** Each unreachable screen becomes either a wiring fix or an explicit `hide-for-future` row.
- **Hygiene raw output → Phase 125.** HYG-02's false-positive-safe deletion procedure needs the audit's dispatch-pattern annotations (D-122-18) to be safe.

### Stale-map warning (load-bearing)
`.planning/codebase/*.md` (ARCHITECTURE, CONCERNS, TESTING, STRUCTURE, STACK, CONVENTIONS, INTEGRATIONS) are all dated **2026-04-30** and describe the **deleted `apps/admin-web`** era — empty `backend/`, 8 test files, mock-only services, no `apps/` workspace. They are **not usable as audit input** and must not be cited as evidence. The same staleness class applies to the `CLAUDE.md` stack prose (a known finding, owned by HYG-05 in Phase 125). Trust the code and a fresh grep; refresh the maps only after v4.1 closes.

</code_context>

<specifics>
## Specific Ideas

- **Ground-truth numbers measured during this context pass** (all supersede the estimates in ROADMAP/research prose, and all must be re-derived by the audit itself rather than quoted from here):
  - `apps/admin/src/features/` → **29** domain dirs, **5** with contract tests (roadmap says "~25" / "~20 lacking")
  - TODO/FIXME/HACK/XXX → **35** markers (PROJECT.md says 32, research says 19)
  - `apps/backend/.importlinter` → **3** contracts (matches)
  - Knip / jscpd / vulture / deptry / Playwright / Schemathesis → **none installed**
  - `infra/runbooks/production.md` § Operator-Pending Boundary → line 421; STATE.md's per-phase UAT tally sums to 27, not the quoted 23
- **The registry's honesty invariant, stated up front:** a zero-`deferred` result is a red flag, not a win (CLOSE-04). With two HARD GATEs and a full operator-pending ledger already known, the audit that produces no deferred rows has been done wrong.
- **The three sub-passes are trivially parallel by construction** — 1a touches only static files, 1b needs docker-compose, 1c is desk review of runbooks. Nothing shares a write target once D-122-04's staging protocol is in place.

</specifics>

<deferred>
## Deferred Ideas

- **Playwright route-sweep harness** → v4.2 (`TOOL-02`). Not built in v4.1; the AUD-06 walk uses chrome-devtools MCP (D-122-14).
- **Knip / jscpd / vulture as CI gates** → v4.2 (`TOOL-01`). Only `deptry` graduates in v4.1, and that happens in Phase 125 (HYG-06), not here.
- **`trivy config` as a blocking gate** → v4.2 (`TOOL-03`). Phase 126 runs it on demand.
- **Introducing `zod` into `apps/client` + schemas for all ~21 endpoints** → v4.2 (`CLI-01`/`CLI-02`). v4.1 covers money/auth paths only (D-V41-CLIENT-SCOPE).
- **Refreshing `.planning/codebase/*.md`** — the maps are three months stale and describe a deleted app. Worth a dedicated `/gsd-map-codebase` run, but *after* v4.1 closes; regenerating them mid-milestone would just re-document a codebase that is about to change.
- **Splitting the registry per category** — contingency only, if row volume lands in the hundreds rather than dozens. Do not pre-optimize (D-122-01).

### Reviewed Todos (not folded)

- **`2026-06-02-future-milestones-sequence-post-v2-1.md` — "Future milestones sequence (post-v2.1)"** (matched at score 0.9, area `planning`). **Not folded.** The match is lexical, not substantive: the todo is a 2026-06-02 milestone-sequencing plan whose entire content (v2.2 membership depth → v2.6 referral → v3.0 production deploy) has since **shipped**. It contains no audit scope and folding it would import obsolete planning prose into a defect registry. STATE.md already carries it as `deferred → backlog`. Recommended follow-up outside this phase: retire the todo file as stale, since its canonical home (`PROJECT.md` § Next Milestone Goals) has moved on.

</deferred>

---

*Phase: 122-audit-registry-producing-read-only-pass*
*Context gathered: 2026-07-26*
