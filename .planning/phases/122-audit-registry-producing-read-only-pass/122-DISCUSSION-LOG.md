# Phase 122: Audit — Registry-Producing Read-Only Pass - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 122-audit-registry-producing-read-only-pass
**Mode:** `--auto` — no interactive prompts; Claude selected the recommended option for every question and logged the alternatives below

> **Interactive review (2026-07-26, `/gsd-discuss-phase 122 --chain`):** The auto-generated context above was re-opened for interactive review. Four gray areas were offered for revision — (1) edge-seed matrix breadth, (2) browser-UAT walk depth, (3) reachability strictness + client scope, (4) hygiene-triage verbosity. User selected **no preference**: all 25 auto-resolved decisions accepted unchanged. No decisions were revised. Proceeded to auto-advance (`--chain`) into plan-phase.

**Areas discussed:** Registry artifact shape, Supporting audit artifacts, Reachability manifest (AUD-03), Zod↔wire manifest (AUD-05), Edge-case seed dataset (AUD-04), Browser UAT walk (AUD-06), Hygiene tooling (AUD-02), Infra triage (AUD-07), Read-only enforcement (AUD-08)

---

## Registry artifact shape

| Option | Description | Selected |
|--------|-------------|----------|
| One Markdown file, three per-category tables | Single `.planning/audits/v4.1-DEFECT-REGISTRY.md`; git-diffable; CLOSE-01 grep works on one file | ✓ |
| Three files, one per category | Cleaner concurrent writes, but violates AUD-01's "single artifact" and complicates the close grep | |
| Structured store (JSON/SQLite) with a rendered view | Over-engineered for dozens of rows; loses git-diff review value | |

**Choice:** one file, three category sections (D-122-01).
**Notes:** Research explicitly warns against pre-optimizing for a per-category split — it is a contingency if volume lands in the hundreds. Concurrent-write pressure is solved separately by the staging protocol (D-122-04) rather than by splitting the artifact.

---

## Row ID scheme

| Option | Description | Selected |
|--------|-------------|----------|
| Category-prefixed sequential (`V41-FUNC-001`) | Three sub-passes can allocate IDs concurrently without collision | ✓ |
| Flat sequential (`DEFECT-001`) | Research's literal suggestion, but three parallel writers would collide | |
| Content-hash IDs | Stable but unreadable in commit messages and `blocked_by` fields | |

**Choice:** category-prefixed, sequential per category, never renumbered (D-122-02).
**Notes:** IDs become permanent cross-references in fix-phase commits — renumbering would break the audit trail, so reclassification is recorded in-row rather than by reassigning an ID.

---

## Concurrent-write protocol for the three sub-passes

| Option | Description | Selected |
|--------|-------------|----------|
| Per-sub-pass staging files, merged at freeze | Zero merge conflicts; final artifact is still exactly one file | ✓ |
| All three write the registry directly | Guaranteed conflicts on a shared Markdown table | |
| Serialize the sub-passes | Throws away the phase's main parallelism property for no benefit | |

**Choice:** staging files under `.planning/audits/staging/`, deleted in the freeze commit (D-122-04).

---

## Supporting audit artifacts vs registry contents

| Option | Description | Selected |
|--------|-------------|----------|
| Manifests are separate artifacts; registry holds defects only | Keeps CLOSE-01's undispositioned-row grep meaningful | ✓ |
| Everything in the registry (manifest rows + defect rows) | Coverage and defects blur; the close-grep starts matching clean rows | |

**Choice:** four separate manifests + a raw-tool-output archive; registry rows reference them (D-122-06).
**Notes:** the distinction is load-bearing — a manifest proves *coverage*, the registry proves *defects*.

---

## AUD-03 — Reachability manifest

| Option | Description | Selected |
|--------|-------------|----------|
| Script-generated three-way join | `tools/audit/reachability-manifest.mjs` over router × nav-items × screen component | ✓ |
| Manual enumeration per screen | This is the exact method that let FND-04 recur across v3.0 and v3.2 | |

**Choice:** script (D-122-07).
**Notes:** a screen resolving to `ComingSoon`/placeholder counts as NOT reachable; a route with no nav entry likewise gets a row.

---

## AUD-05 — Zod↔wire manifest

| Option | Description | Selected |
|--------|-------------|----------|
| Script-generated manifest over all 29 feature dirs | One mechanical pass; the `capture-fixture present` column becomes Phase 124's work list | ✓ |
| Compare against `openapi.json` | That is spec-vs-Zod — Phase 124's `AssertEqual` layer, not the empirical layer | |
| Per-domain manual review | Same failure mode as manual reachability review | |

**Choice:** script; compare against real captured response bytes, not the spec (D-122-08, D-122-10).
**Notes:** ground truth measured during scouting — 29 feature dirs, 5 with contract tests. The roadmap's "~20 of ~25" is an estimate the manifest replaces.

---

## AUD-04 — Edge-case seed dataset

| Option | Description | Selected |
|--------|-------------|----------|
| New idempotent `seed_edge_cases.py`, additive on the demo seed | Follows the existing 5-script convention; survives into fix phases as a regression bed | ✓ |
| Extend `seed_demo_data.py` | Modifies existing app code — violates the AUD-08 read-only allowlist | |
| Pytest fixtures only | Not usable by the browser UAT walk, which needs a real seeded database | |

**Choice:** new script (D-122-11).
**Notes:** the domain × axis grid is deliberately left to plan time — this is the acknowledged Research Flag for sub-pass 1b. Environment for 1b is docker-compose, not k3d (D-122-13).

---

## AUD-06 — Browser UAT walk

| Option | Description | Selected |
|--------|-------------|----------|
| chrome-devtools MCP interactive walk | Already the project's browser-verification method; zero new dependencies | ✓ |
| Build a Playwright route-sweep | Playwright is `TOOL-02`, deferred to v4.2; net-new E2E harness inside a read-only audit is scope creep | |

**Choice:** chrome-devtools MCP; output mirrors the v3.0/v3.1/v3.2 browser-audit format (D-122-14, D-122-15).
**Notes:** stale-service-worker and dev-login handling are walk preconditions, not discoveries (D-122-16).

---

## AUD-02 — Hygiene tooling invocation

| Option | Description | Selected |
|--------|-------------|----------|
| Ephemeral pinned runners (`pnpm dlx` / `uvx`) | Zero repo dependencies added during a read-only phase | ✓ |
| Add all four as dev dependencies | Modifies manifests; CI graduation is Phase 125's job (HYG-06), not this phase's | |

**Choice:** ephemeral runners at pinned versions; raw output archived (D-122-17).
**Notes:** every finding gets a row **including false positives**, each annotated with the dispatch pattern that makes it one — that annotation is what makes Phase 125's deletions safe (D-122-18). Marker count is re-derived fresh: 35 measured now vs 32 in PROJECT.md vs 19 in research (D-122-19).

---

## AUD-07 — Infra triage source of truth

| Option | Description | Selected |
|--------|-------------|----------|
| `infra/runbooks/production.md` § Operator-Pending Boundary | The runbook is the canonical operator-facing list | ✓ |
| The four v4.0 `*-UAT.md` files | Per-phase wording is useful cross-reference, but scattered | |
| STATE.md's Deferred Items table | A summary of the above; its counts don't reconcile | |

**Choice:** runbook authoritative, UAT files cross-referenced (D-122-21).
**Notes:** the "23 items" figure is re-derived, not assumed — STATE.md's own per-phase tally sums to 27, and reconciling that discrepancy is itself an audit output (D-122-22). The two HARD GATEs stay `deferred:operator-pending` and unedited for all of v4.1 (D-122-23).

---

## AUD-08 — Read-only enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Mechanical path-allowlist check at phase close | Makes Success Criterion 7 provable rather than asserted | ✓ |
| Convention + reviewer diligence | Unprovable; this is the failure mode Pitfall 1 describes | |

**Choice:** `git diff --name-only` against an explicit allowlist as a plan task (D-122-24).
**Notes:** trivially-fixable defects are still not fixed here — no exceptions (D-122-25).

---

## Claude's Discretion

Auto-mode resolved every area. Left genuinely open for the researcher/planner:

- Per-domain enumeration of the edge-case seed matrix (axes locked, grid is plan-time work)
- Parsing strategy inside the two manifest scripts (AST / regex / `ts-morph`)
- Whether the three sub-passes become three parallel plans or one plan with three waves

## Deferred Ideas

- Playwright route-sweep harness → v4.2 (`TOOL-02`)
- Knip / jscpd / vulture as CI gates → v4.2 (`TOOL-01`); only `deptry` graduates, in Phase 125
- `trivy config` as a blocking gate → v4.2 (`TOOL-03`)
- `zod` in `apps/client` + all ~21 endpoint schemas → v4.2 (`CLI-01`/`CLI-02`)
- Refreshing `.planning/codebase/*.md` (three months stale, describes the deleted `apps/admin-web`) → after v4.1 closes
- Splitting the registry per category → contingency only, if volume lands in the hundreds

### Reviewed Todos (not folded)

- **`2026-06-02-future-milestones-sequence-post-v2-1.md`** (score 0.9, area `planning`) — not folded. Lexical match only: the todo is a milestone-sequencing plan whose content (v2.2 → v3.0) has entirely shipped. No audit scope; folding it would import obsolete planning prose into a defect registry. Suggested follow-up outside this phase: retire the file as stale.
