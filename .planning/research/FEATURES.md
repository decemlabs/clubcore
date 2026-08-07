# Feature Research — Codebase Hardening Practice (v4.1)

**Domain:** Quality/tech-debt "fix everything" milestone practice — NOT gym/CRM product features
**Researched:** 2026-07-26
**Confidence:** HIGH (practice/process claims cross-checked across multiple independent sources; MEDIUM on procedures (c)/(d) which are synthesized from general contract-testing/reachability-audit practice and adapted to clubcore's specifics — no single source describes clubcore's exact stack, so the step-by-step is opinionated synthesis, not a verbatim citation)

## Framing

This is not a feature-landscape research doc in the usual sense — there is no "domain" of gym CRMs to survey. The "features" here are **audit/fix activities**: the components of a disciplined "harden the codebase" effort. The question that matters for the roadmapper is: *which of these activities are mandatory scaffolding, which are worth doing but optional, and which will silently turn a bounded milestone into an infinite refactor.*

The project's own `PROJECT.md` already encodes the two hardest-won lessons that should anchor this milestone:
- **v3.0/v3.1 lesson:** unit tests on mocks passed twice while the frontend Zod schema had drifted from the real backend wire shape; only browser UAT against a live backend caught it. This means static/mock-based audit alone is insufficient for the FUNC category — a live-backend pass is mandatory, not optional.
- **FND-04 / D-71-09 lesson:** a screen can be fully implemented and wired and still be unreachable (`router.tsx` still renders `ComingSoon`, or `nav-items.ts` lacks the entry). Reachability is a distinct defect class from "does it work" and needs its own enumeration pass — this pattern has already been used successfully 3+ times (`NotificationsSheet`, `TrainerDetailSheet`, `ChatScreen`, `ReferralSheet`).

## Feature Landscape

### Table Stakes (Mandatory Audit/Fix Components)

These are non-negotiable for a "fix everything wrong" milestone to be honest and complete. Skipping any of these means the DEFECT registry is not actually comprehensive, and the done-bar ("every entry fixed+verified or deferred with reason") becomes unverifiable.

| Activity | Why Mandatory | Complexity | Depends On |
|---|---|---|---|
| **Reachability manifest** (cross-join `router.tsx` route tree × `nav-items.ts` entries × real screen components) | Distinct defect class from "does it work" (FND-04 precedent); cheapest static check, catches an entire category other audits miss | LOW | None — pure static analysis, no live backend needed |
| **Static hygiene sweep** (grep 32 TODO/FIXME/HACK markers, `import-linter`/ESLint boundary-violation run, dead-code scan, duplication scan) | Cheap, deterministic, fully automatable; the milestone explicitly names this category | LOW–MEDIUM | None — runs against source tree only |
| **Live-backend schema/wire-shape divergence hunt** (manifest-driven capture-and-diff harness, see procedure (c) below) | The single highest-yield defect class per project's own history (v3.0/v3.1: 6+ divergence bugs, all missed by mock-based unit tests) | MEDIUM–HIGH | Requires a running real backend + seeded data (docker/k3d) |
| **Browser UAT walk of every reachable screen on real backend** | Confirms user-visible rendering breakage that a schema-parse-level diff can miss (layout, empty-state, loading-state bugs); this is the layer that actually caught the v3.0/v3.1 bugs | MEDIUM | Reachability manifest (to know what "every screen" means) + live backend |
| **23-item v4.0 operator-pending triage** (doable-locally vs genuinely hardware-gated) | Explicitly named in scope; without it the INFRA category can't be bounded (some items are unfixable locally by design — D-V40-LOCAL-VALIDATE) | LOW–MEDIUM | None — desk review against `infra/runbooks/production.md` |
| **Single consolidated DEFECT registry** (severity × category × disposition; see scheme below) | This is the artifact everything downstream depends on; without ONE registry, "audit-once-then-fix" degenerates into ad hoc parallel bug lists that never converge | LOW (mechanically) but architecturally critical | All of the above audit passes must feed it before any fix phase opens |
| **Fix phases grouped by category, each closing with contract-test-proof** | Matches the milestone's own three directions; contract-test-against-real-response is already this project's established convention (v3.1/v3.2 gate rule) | MEDIUM | Registry must exist and be reasonably complete per category before that category's fix phase opens |
| **Full-gate re-verification after every fix batch** (ruff/mypy strict/import-linter/eslint/tsc/pytest/vitest/OpenAPI drift) | Already CI-automated in this project — the discipline is running it per batch, not just at milestone close, so regressions are caught immediately | LOW (tooling exists) | Nothing new — reuse existing CI gates |
| **Explicit disposition on every registry row** (`fixed+verified` or `deferred` + reason) | This is the actual stopping/convergence mechanism (see Convergence section) — without it, unfinishable items block milestone close forever | LOW | Registry must exist |

### Differentiators (Worth Doing, Not Mandatory)

These add real value and are cheap relative to the payoff, but the milestone converges without them if time-boxed out.

| Activity | Value Proposition | Complexity | Notes |
|---|---|---|---|
| **Promote the schema-diff harness to a permanent CI artifact** (not a throwaway audit script) | Converts a one-time hardening effort into a standing regression gate — directly prevents the v3.0/v3.1 failure mode from recurring in v4.2+ | MEDIUM | Natural extension of procedure (c); reuses the project's existing `openapi.json`/`schema.d.ts` byte-stable-regen convention as the source of truth |
| **Wire the reachability check into CI** (fails the build if a real component has no route+nav path, or if a placeholder still wraps a graduated screen) | Prevents reachability regressions from recurring the way schema drift did across three milestones | MEDIUM | Small AST/grep script; low ongoing cost once built |
| **Root-cause tagging on registry rows** (e.g. "no generated-type parity for domain X" rather than just "bug in file Y") | Feeds institutional memory / ADR log; helps the *next* hardening pass target root causes instead of re-discovering the same class of bug | LOW–MEDIUM | Purely additive metadata on the registry schema |
| **Severity-weighted burndown view of the registry** | Makes convergence visible/checkable rather than aspirational — directly serves the "concrete, checkable" requirement of this milestone | LOW | Simple derived report from the registry file; no new tooling |
| **Scripted (not just manually-proven) k3d backup/restore round-trip** | Turns a one-off manual BAK-03 proof into a repeatable runbook step, raising confidence for the next infra-touching milestone | MEDIUM | Ties directly into the INFRA category; reuses existing k3d/Helm scaffolding from v4.0 |

### Anti-Features (Things That Prevent Convergence)

Each of these looks like "being thorough" but is a documented failure mode of quality/hardening milestones.

| Anti-Feature | Why It Looks Appealing | Why It's a Problem | What To Do Instead |
|---|---|---|---|
| **Iterate-until-dry** (re-run the full audit after every fix batch, admit new findings indefinitely) | "We should keep looking until we find nothing" feels rigorous | No stopping condition; the milestone never closes because audits always find something on a codebase of this size | **Audit-once-then-fix** (already the user's chosen model): one audit phase produces the registry; findings surfaced *while fixing* get appended with a `found-during-fix` tag and dispositioned like any other row, but do NOT trigger a new audit round |
| **Blanket coverage targets** ("get to 80% test coverage while we're at it") | Coverage numbers feel like objective proof of quality | Turns a defect-driven milestone into an unrelated coverage campaign; the project's own key-context already rejects this explicitly ("тесты — не кампания за покрытие, а инструмент доказательства фиксов") | Tests exist only to prove a *specific* registry-row fix; no coverage-percentage goal |
| **Mass reformatting** (repo-wide prettier/black/ruff-format pass bundled with logic fixes) | "Since we're touching everything, let's also normalize formatting" | Destroys diff reviewability, makes git blame/bisect useless, high regression-risk-to-value ratio | If formatting drift is itself a registry item, fix it in its own isolated commit/PR, never mixed with logic changes |
| **Speculative rearchitecting** (redesigning module boundaries beyond restoring `import-linter` conformance) | "While we're fixing boundaries, let's also make the architecture better" | Classic "boiling the ocean" — scope balloons past what any fix phase can verify or roll back cleanly | Layer-boundary fixes *restore* conformance to already-decided contracts (import-linter rules that exist today); they do not redesign the module system |
| **Dependency upgrades "while we're in there"** | "We're already touching this file, may as well bump the library" | Different failure surface and rollback shape than the fix at hand; breaks causality when something goes wrong, and reviewers rubber-stamp because tests are green for unrelated reasons | Only touch a dependency version if it is the *proven root cause* of a specific registry row; otherwise it's a separate, later concern |
| **Fixing bugs during the audit pass itself** (patching a schema mismatch the moment it's spotted, mid-audit) | Feels efficient — why write it down if you can just fix it | Breaks the audit/fix phase separation, and worse: a bug fixed inline never gets a registry row, so the registry stops being the single source of truth and the done-bar becomes unverifiable | Audit passes ONLY record; every finding — even an obvious one-liner — gets a registry row before any code changes |
| **Screen-by-screen manual chasing of schema drift** (click through the app hunting for mismatches with no systematic harness) | "We'll just be thorough and check every screen by hand" | This is *exactly* the process that let 6+ divergence bugs through v3.1 unit tests before ad hoc browser UAT caught them — manual chasing doesn't scale and can't prove completeness | Use the manifest-driven capture+diff harness (procedure (c)) so completeness is a property of the manifest, not of tester diligence |
| **Treating operator-pending/hardware-gated items as "must fix this milestone"** | "Fix everything" sounds like it should include everything | Directly violates the inherited `D-V40-LOCAL-VALIDATE` decision; some items are structurally unfixable without real hardware/credentials | Disposition, not indefinite postponement: `deferred` with an explicit reason is a valid, final state — this is the actual convergence mechanism |

## Severity / Category / Disposition Scheme (recommended)

Industry practice uses many severity taxonomies (Blocker/Critical/Major/Minor/Trivial is the classic 5-tier QA scheme; ISO 25010 characteristics is a heavier framework; impact-vs-likelihood matrices are common for triage meetings). For a solo-developer + AI-agent team, a compact 3-tier scheme is enough — a 5-tier scheme adds classification overhead without changing which fix phase an item lands in.

**Severity (3-tier):**
- **Blocker** — screen crashes, flow is unusable on real data, or a screen is completely unreachable
- **Major** — feature misbehaves under real data without crashing (wrong value, partial data loss, silently-dropped field)
- **Minor** — cosmetic drift or zero-behavioral-impact hygiene item (a TODO with no runtime effect, dead code with zero references)

**Category (3, matching the milestone's own three directions):**
- **FUNC** — functional bugs on real data: schema/wire-shape divergence, crashing screens, unreachable screens
- **HYGIENE** — code hygiene + architecture: TODO/FIXME/HACK, dead code, duplication, layer-boundary violations, over-abstraction
- **INFRA** — locally-provable production readiness: k3d apply, backup/restore round-trip, sealed-secrets key backup

**Disposition (2, already implied by the milestone's done-bar — just formalize it):**
- **fixed+verified** — contract test or full-gate evidence attached, linked to the registry row
- **deferred** — explicit reason required, one of: `operator-pending` (needs real hardware/credentials per D-V40-LOCAL-VALIDATE), `out-of-scope` (belongs to a different milestone/domain), or `accepted-risk` (understood, deliberately not worth fixing now)

A registry row is therefore: `id, severity, category, screen/file, description, disposition, reason (if deferred), evidence-link (if fixed)`. This is intentionally close to what a classic bug-tracker triage matrix produces (severity × MoSCoW-style Must/Should/Could/Won't fix), adapted so "Won't Fix" always carries a reason rather than being silently dropped.

## Convergence / Stopping Rules (concrete, checkable)

1. **Audit-once-then-fix, not iterate-until-dry.** The audit phase closes with a registry snapshot. New findings discovered *while fixing* are appended (`found-during-fix` provenance) and dispositioned individually — they never trigger re-opening the audit phase itself.
2. **Category freeze at audit close.** The three categories (FUNC/HYGIENE/INFRA) are fixed once the registry is written. Anything that doesn't fit an existing category is logged to the project backlog, not absorbed into this milestone.
3. **Per-category exit criterion:** a category's fix phase is done when every row tagged with that category is either `fixed+verified` or `deferred` with a reason — not when some external quality metric (coverage %, LOC touched) is hit.
4. **Milestone exit criterion (already chosen by the user):** every registry row has a terminal disposition AND all existing CI gates are green. This is checkable by `grep`-ing the registry file for rows lacking a disposition — a literal, scriptable zero-count check, not a vibe.
5. **Deferred is a valid final state, not a failure.** Because some rows are structurally hardware-gated (`D-V40-LOCAL-VALIDATE` carry-over), the milestone can close with open items as long as each has a disposition — this is what prevents "fix everything" from becoming "fix everything, forever."
6. **No re-triage of deferred items within this milestone.** Once a row is `deferred`, it is not revisited until a future milestone explicitly reopens it (e.g., when real hardware becomes available) — this bounds effort and prevents relitigating disposition decisions mid-milestone.

## Procedure (c): Systematically Hunting FE-Schema-vs-Live-Backend-Wire-Shape Divergence

**Goal:** find every place a frontend Zod schema disagrees with what the real backend actually returns, across the whole app, in one pass — not screen-by-screen.

1. **Build the manifest first.** Grep both `apps/admin` and `apps/client` for every API-client call site (`fetch`/generated `api-client` calls) paired with the Zod schema used to parse its response. Produce one row per (domain, endpoint, HTTP method, Zod schema file) triple. This manifest IS the audit inventory — anything not in it cannot be claimed as "audited."
2. **Capture real responses once per manifest row.** Stand up the real backend against seeded data (`docker compose up` / k3d) and script a pass that calls every endpoint in the manifest with a valid session (reusing the project's existing seed/dev-login convention) and dumps the raw JSON response.
3. **Diff captured JSON against the Zod schema, not against the UI.** Feed each captured response through its corresponding `schema.parse()` in `.strict()` mode (not the app's default lenient parse) — this surfaces *added* fields Zod would otherwise silently drop as well as missing/renamed/type-mismatched fields, which is exactly the trap that let bugs through mock-based unit tests before (Zod's default behavior strips unknown keys, masking exactly this class of drift).
4. **Cross-check structurally against the backend's own source of truth.** This project already regenerates `openapi.json`/`schema.d.ts` byte-stably every milestone — use that as a second, independent check: diff each Zod schema's inferred TS shape against the corresponding generated OpenAPI type. Two independent signals (live-capture parse + generated-type diff) catch different failure modes (the former catches genuinely-wrong runtime data; the latter catches spec/schema drift even when current seed data happens not to exercise the diverging field).
5. **One harness, not N manual checks.** The harness iterates the manifest from step 1 — running it is a single command, and its output (pass/fail per manifest row) is a direct, machine-produced input to the DEFECT registry. This is what makes the hunt "systematic" instead of "thorough": completeness is a property of the manifest's coverage of API call sites, not of how many screens a human clicked through.
6. **Browser UAT is the confirmation layer, not the discovery layer.** After the harness flags a divergence, do one targeted browser check per flagged row to confirm user-visible impact (does it crash, silently show wrong data, or is it cosmetically harmless) — this determines severity, but the harness (not the click-through) is what guarantees no domain was skipped.
7. **Every flagged row becomes a registry entry** with: schema file, endpoint, specific field(s), divergence type (missing / renamed / type-mismatch / nullable-mismatch / extra-field-silently-dropped), and — once fixed — a permanent contract test that replays the captured real response through the corrected schema (this is exactly the "≥1 contract-test-per-domain against a real response" convention this project already uses; the harness output becomes that test's fixture).

## Procedure (d): Enumerating and Proving Reachability of Every Intended Screen

**Goal:** find every screen that is implemented but unreachable (`ComingSoon` placeholder still active, or missing nav entry) across the whole app, provably, not by memory.

1. **Build two independent lists and cross-join them.** List A: every route entry in `router.tsx` (path → component). List B: every entry in `nav-items.ts` (label → path). Join on path. A row present in B but missing from A is a broken nav link (dead link in the UI). A row present in A but missing from B is either an intentionally-hidden deep-link screen or a genuinely orphaned route — must be manually classified, not assumed benign.
2. **Classify each route's component.** For every path in the join, check whether its component is a real feature component or a placeholder (`ComingSoon`/lazy-stub). Grep for the placeholder component's every usage site — each one is a candidate "should be reachable but isn't" defect, directly following the project's own established `D-71-09` placeholder-zone pattern (already successfully de-listed 4 times for `NotificationsSheet`, `TrainerDetailSheet`, `ChatScreen`, `ReferralSheet`).
3. **Build list C: every real screen component that exists in the codebase** (grep feature/screen directories for exported top-level screen components), independent of whether it's wired into the router at all. Join list C against list A. A component in C missing from A entirely is either dead code (never wired) or a screen reachable only via a non-route mechanism (e.g., a sheet opened from a parent screen, which is legitimate) — this distinguishes "unreachable route" (a routing bug) from "unreachable via router but reachable via a sheet" (working as intended) from "fully orphaned dead code" (a HYGIENE-category finding, not a FUNC one).
4. **Automate the three-way join as a script**, not a manual spreadsheet: parse `router.tsx`'s route table, parse `nav-items.ts`'s path list, grep screen-component export sites, and emit one row per screen with columns `{component, has_route, has_nav_entry, is_placeholder, is_reachable_via_sheet}`. Any row where a real (non-placeholder) component lacks a route AND lacks a nav entry AND lacks a sheet-based reachability path is a defect by construction — the join itself proves completeness, the same principle as procedure (c)'s manifest.
5. **One targeted browser click-through per flagged row** to confirm the fix path (nav-entry-only fix vs. route-flip-only fix vs. both) and to catch any residual `ComingSoon` wrapper that survived the static grep (e.g., conditionally rendered placeholders).
6. **Distinguish "defect" from "intentionally deferred."** A screen with no route/nav entry that maps to an explicitly out-of-scope backlog item (e.g., Notifications Hub, Roles-editor — both explicitly out of v4.1 scope per `PROJECT.md`) is NOT a reachability defect; it must be tagged `intentionally-hidden-for-future` in the registry, distinct from an accidental gap, or the reachability sweep will manufacture false-positive "bugs" out of legitimate scope boundaries.
7. **Output: one reachability matrix row per screen** in the DEFECT registry, disposition one of: `reachable` (no action), `route-fix-needed`, `nav-fix-needed`, `both-missing`, or `intentionally-hidden-for-future` (not a defect, informational only).

## Feature Dependencies (Phase-Ordering Implications)

```
Reachability manifest (static, no infra)
Static hygiene sweep (static, no infra)
    └──feed into──> Single DEFECT registry
                       ▲
Live-backend schema-diff harness (needs running backend + seed data)
    └──feed into──┘
Browser UAT walk (needs reachability manifest + live backend)
    └──feed into──> Single DEFECT registry
                       ▲
23-item operator-pending triage (desk review, independent)
    └──feed into──┘

Single DEFECT registry (hard gate — must exist and be reasonably complete)
    └──requires──> FUNC fix phase   (contract-test-proof per divergence type)
    └──requires──> HYGIENE fix phase (static-gate-proof: ruff/import-linter/eslint/dead-code scan)
    └──requires──> INFRA fix phase   (k3d/backup/sealed-secrets proof — parallelizable with FUNC/HYGIENE, no shared files)

FUNC fix phase ──enhances──> HYGIENE fix phase (fixing schema drift often reveals adjacent dead code/duplication in the same file)
INFRA fix phase ──conflicts with nothing── (separate infra-only files/modules; safe to run concurrently with FUNC/HYGIENE)

All fix phases ──gate──> Milestone close (full registry disposition + full CI gate green)
```

### Dependency Notes

- **Static passes (reachability + hygiene) require no live backend** — they should run first/in-parallel because they're cheap and unblock nothing else; delaying them wastes the cheapest signal.
- **The live-backend schema-diff harness and browser UAT walk both require a running seeded backend** — group these together as one audit sub-phase distinct from the static passes, because they share the same infra precondition and the browser walk literally consumes the reachability manifest as its screen list.
- **The DEFECT registry is a hard gate, not a soft one.** No fix phase should open until the registry exists in a reasonably complete state — this is the literal implementation of the user's chosen "audit phase FIRST" structure.
- **INFRA fix phase has no file/module overlap with FUNC/HYGIENE** (k3d manifests, Terraform, sealed-secrets vs. application source) — it can and should run as a parallel track once the registry exists, not sequentially after FUNC/HYGIENE, to shorten wall-clock time without adding coordination risk.
- **FUNC and HYGIENE fixes share files** (a schema-drift fix and a dead-code removal can land in the same module) — sequence FUNC before HYGIENE within a shared file/module so hygiene cleanup doesn't need to be redone after a functional fix changes the code shape; but they can still be separate phases at the roadmap level since most files aren't touched by both.

## MVP Definition (What Must Be a Phase vs. What Can Merge)

### Must Be Its Own Phase (Audit)

- [ ] **Audit phase (single phase, two sub-passes)** — static (reachability + hygiene) sub-pass, then live-backend (schema-diff harness + browser UAT + operator-pending triage) sub-pass, closing with the single DEFECT registry as its deliverable. This MUST precede all fix phases per the user's chosen done-bar; merging audit into fix work would make "audit-once-then-fix" unverifiable.

### Should Be Separate Fix Phases (Different Verification Recipes + Risk Profiles)

- [ ] **FUNC fix phase** — verified by contract tests against real backend responses (per divergence type) + reachability re-check
- [ ] **HYGIENE fix phase** — verified by static gates (ruff/mypy/import-linter/eslint/tsc) + dead-code/duplication re-scan; higher regression risk (removing code) so deserves isolated review
- [ ] **INFRA fix phase** — verified by k3d apply / restore round-trip / sealed-secrets backup proof; can run as a parallel track since it shares no files with FUNC/HYGIENE

### Should Be a Short Closing Step, Not a Full Phase

- [ ] **Registry consolidation** — mechanically cheap (one artifact), but must be an explicit checkpoint/gate between audit and fix phases, not silently folded into the audit phase's own closing commit
- [ ] **Milestone close / final disposition check** — re-verify every registry row has a terminal disposition + full CI gate green; this is a checklist pass, not new work

### Explicitly Out of Scope for This Milestone (Anti-Feature Boundary)

- [ ] Blanket coverage-percentage targets
- [ ] Whole-repo reformatting passes
- [ ] Architectural redesign beyond restoring existing `import-linter` boundary contracts
- [ ] Dependency version bumps not tied to a specific registry row
- [ ] Re-opening `deferred` (operator-pending) rows mid-milestone

## Feature Prioritization Matrix

| Activity | Convergence Value | Implementation Cost | Priority |
|---|---|---|---|
| Reachability manifest | HIGH | LOW | P1 |
| Static hygiene sweep | HIGH | LOW | P1 |
| Live-backend schema-diff harness | HIGH | MEDIUM–HIGH | P1 |
| Browser UAT walk | HIGH | MEDIUM | P1 |
| Single DEFECT registry | HIGH (it IS the convergence mechanism) | LOW | P1 |
| Operator-pending triage | MEDIUM | LOW–MEDIUM | P1 |
| Contract-test-proof per fix | HIGH | MEDIUM | P1 |
| Full-gate re-verification per batch | HIGH | LOW (tooling exists) | P1 |
| Schema-diff harness → permanent CI artifact | MEDIUM (future-proofing) | MEDIUM | P2 |
| Reachability check → CI gate | MEDIUM (future-proofing) | MEDIUM | P2 |
| Root-cause tagging on registry | LOW–MEDIUM (institutional memory) | LOW | P3 |
| Burndown visualization | LOW (nice-to-have reporting) | LOW | P3 |
| Scripted k3d backup/restore runbook | MEDIUM (raises confidence for future infra milestones) | MEDIUM | P2 |

**Priority key:**
- P1: Must have — the audit-then-fix model doesn't converge without these
- P2: Should have — meaningfully reduces recurrence risk for future milestones
- P3: Nice to have — improves visibility/memory but milestone converges without it

## Reference Practices Analyzed

| Practice | How It Informed This Doc | Where It Diverges for clubcore |
|---|---|---|
| Classic 5-tier QA severity (Blocker/Critical/Major/Minor/Trivial) | Basis for the severity axis | Compressed to 3 tiers — 5 tiers add classification overhead a solo-dev+AI-agent team doesn't need |
| Martin Fowler's Technical Debt Quadrant (deliberate/inadvertent × prudent/reckless) | Confirms HYGIENE-category debt should be root-cause-tagged rather than treated uniformly | Not used directly as the registry's category axis (too abstract for a fix-tracking artifact); reserved for the P3 root-cause-tagging differentiator instead |
| SAFe "hardening sprint" | Confirms this is a recognized, if debated, pattern (dedicated stabilization period before/around a release) | clubcore's version is explicitly NOT open-ended (audit-once-then-fix with hard disposition), avoiding the "hardening sprint as recurring crutch" criticism these sources raise |
| MoSCoW-style bug triage (Must/Should/Could/Won't Fix) | Basis for the disposition axis | Collapsed to 2 states (`fixed+verified` / `deferred`+reason) since this milestone's done-bar already defines the terminal states; MoSCoW's four buckets are redundant with severity here |
| Consumer-driven contract testing / Schemathesis-style OpenAPI response validation | Direct basis for procedure (c)'s harness design (capture real responses, validate against schema in strict mode, generate from the spec of record) | clubcore already has hand-rolled Zod schemas rather than spec-generated FE types; the harness therefore diffs Zod against both live-captured JSON AND the generated `schema.d.ts`, rather than relying on a single canonical contract-testing tool |
| Feature-flag-cleanup audit practice (enumerate every flag/usage site before removing anything) | Basis for procedure (d)'s "build the manifest/join first, then automate" method | clubcore's placeholder pattern (`ComingSoon` + `nav-items.ts`) plays the same role as a feature flag; the same enumerate-then-verify discipline applies |
| "Boiling the ocean" / Chesterton's Fence / dependency-batching-risk / drive-by-refactoring anti-patterns | Direct basis for the Anti-Features table | Applied narrowly to this milestone's three named categories rather than as generic advice |

## Sources

- [What Is Defect Taxonomy? Types, Examples, and How It Improves QA — testRigor](https://testrigor.com/blog/what-is-defect-taxonomy/)
- [Code Security Audit: A Step-by-Step Guide — SentinelOne](https://www.sentinelone.com/cybersecurity-101/cybersecurity/code-security-audit/)
- [Technical Debt Quadrant — Martin Fowler / Andrew Murphy stdlib summary](https://andrewmurphy.io/stdlib/71f33d24-726e-4945-80b1-87de24b63b88)
- [Martin Fowler's Tech Debt Quadrant Explained — techdebt.works](https://techdebt.works/tech-debt-quadrant/)
- [Hardening Sprints: The Good, Bad, and Downright Ugly — Zenergy Technologies](https://www.zenergytechnologies.com/blog/agile/hardening-sprints-good-bad-ugly)
- [Scrum Anti-Patterns: The Hardening Sprint — Agile Pain Relief](https://agilepainrelief.com/blog/antipattern-hardening-sprint/)
- [Bug Triage Process: Step-by-Step Guide — Bird Eats Bug](https://birdeatsbug.com/blog/bug-triage-process)
- [Runner Core Bug Triage Decision Matrix — GitLab Handbook](https://handbook.gitlab.com/handbook/engineering/devops/runner/runner-core/bug-triage-matrix/)
- [De-bugize! Plan bug fixing in Scrum — ScrumDesk](https://www.scrumdesk.com/de-bugize-plan-fixing-bugs-scrum/)
- [What Is API Contract Testing? Pact & Schema-First — Total Shift Left](https://totalshiftleft.ai/blog/what-is-api-contract-testing)
- [Schemas Can Be Contracts | Introducing Drift — Pactflow](https://pactflow.io/blog/schemas-can-be-contracts/)
- [Consumer Driven Contract Testing — Inspeerity](https://inspeerity.com/blog/consumer-driven-contract-testing/)
- [Schemathesis — Property-based API Testing for OpenAPI and GraphQL Schemas](https://schemathesis.io/)
- [Automate API testing Using Schemathesis — Capital One](https://www.capitalone.com/tech/software-engineering/api-testing-schemathesis/)
- [Cleaning up stale feature flags — PostHog Docs](https://posthog.com/docs/feature-flags/cleaning-up-stale-flags)
- [The Complete Guide to Managing Feature Flag Technical Debt — FlagShark](https://flagshark.com/blog/feature-flag-technical-debt-guide/)
- [Software Technical Audit in 5 Steps — Edana](https://edana.ch/en/2026/03/14/software-technical-audit-securing-your-performance-and-reducing-your-risks-in-5-steps/)
- [Software Code Audit — Processes Breakdown, Tools, and Statistics — Ironhack](https://www.ironhack.com/us/blog/software-code-audit-processes-breakdown-tools-and-statistics)
- [Effectively Managing Technical Debt with TODO, FIXME, and Other Code Reminders — Medium](https://medium.com/@scottgrivner/effectively-managing-technical-debt-with-todo-fixme-and-other-code-reminders-e0b770f6180a)
- [Code freezes — Jens Rantil](https://jensrantil.github.io/posts/code-freeze/)
- [What is Code Freeze and is it Relevant Today? — testRigor](https://testrigor.com/blog/what-is-code-freeze/)
- [How to Avoid Scope Creep During Refactoring — Andrei Gridnev](https://andreigridnev.com/blog/2019-01-20-four-tips-to-avoid-scope-creep-during-refactoring/)
- [Expanding Refactoring in Git Projects: A Sign of Scope Creep? — Bitband](https://www.bitband.com/blog/expanding-refactoring-in-git-projects-a-sign-of-scope-creep/)
- [Avoid Boiling the Ocean: Taking Baby Steps Towards a Data Quality Strategy — Pythian](https://www.pythian.com/blog/technical-track/avoid-boiling-the-ocean-taking-baby-steps-towards-a-data-quality-strategy)
- [Chesterton's Fence: A Lesson in Thinking — Farnam Street](https://fs.blog/chestertons-fence/)
- [How Understanding the Chesterton Fence Can Make You a Better Programmer — Nico's Blog](https://www.nico.fyi/blog/chesterton-fence-programming)
- [How to Safely Update Your Dependencies — Anže's Blog](https://blog.pecar.me/how-to-safely-update-your-dependencies/)
- Project's own `PROJECT.md` (v3.0/v3.1/FND-04 lessons, D-71-09 placeholder-graduation precedent, D-V40-LOCAL-VALIDATE)

---
*Feature research for: codebase hardening / audit-then-fix practice (v4.1 clubcore)*
*Researched: 2026-07-26*
