---
phase: 122-audit-registry-producing-read-only-pass
plan: 2
subsystem: testing
tags: [audit, registry, knip, jscpd, vulture, deptry, import-linter, eslint, reachability, react-router]

requires:
  - phase: 122-01
    provides: "Registry skeleton, three-file staging protocol, merge-registry.mjs (category-routed, idempotent), AUD-08 read-only guard"
provides:
  - "Raw hygiene-tool archive (.planning/audits/v4.1-HYGIENE-RAW/): markers.txt (46 TODO/FIXME/HACK/XXX matches, re-derived fresh), knip.txt, jscpd.txt, vulture.txt, deptry.txt, import-linter.txt, eslint-admin.txt"
  - "tools/audit/reachability-manifest.mjs — three-way router x nav-items x screen-component join for apps/admin and apps/client"
  - ".planning/audits/v4.1-REACHABILITY-MANIFEST.md — 36 rows, 10 admin routes not reachable, 0 client defects"
  - "72 V41-HYG rows + 8 V41-FUNC rows triaged into .planning/audits/staging/1a-hygiene.md, merged into v4.1-DEFECT-REGISTRY.md (82 rows total incl. the 2 pre-existing HARD GATE INFRA rows)"
  - "features/x -> features/y admin ESLint zone assessed (28 current cross-feature violations across 8 feature dirs), NOT enabled"
affects: [122-03, 122-04, 122-05, 122-06, 124, 125]

tech-stack:
  added: []
  patterns:
    - "Regex-based route/nav/component join script (reachability-manifest.mjs) as throwaway audit tooling — not a general React Router AST parser"
    - "Clustered registry rows for high-volume tool output (one row per false-positive class or dead-code theme, with the full member list in the anchor cell and the raw file as evidence) rather than one row per individual tool finding, to keep the registry's 'dozens, not hundreds' design intent honest against real tool volume (~1600 raw findings across knip/jscpd/vulture)"
    - "Named false-positive dispatch patterns extended by analogy: decorator-registered FastAPI routes and Pydantic @field_validator/@model_validator methods treated as the same class as the D-122-18 'lazy-loaded route' / 'Protocol slot in app/main.py' patterns; Pydantic model_config/field reflection and ARQ WorkerSettings hooks likewise named explicitly"

key-files:
  created:
    - tools/audit/reachability-manifest.mjs
    - .planning/audits/v4.1-REACHABILITY-MANIFEST.md
    - .planning/audits/v4.1-HYGIENE-RAW/ (7 files)
  modified:
    - .planning/audits/staging/1a-hygiene.md
    - .planning/audits/v4.1-DEFECT-REGISTRY.md

key-decisions:
  - "Clustered high-volume tool findings (knip's 137 unused files / 354 unused exports, vulture's ~530 findings, jscpd's 159 clone pairs) into theme-level rows rather than one row per finding — each row's anchor cell lists every member path and the evidence cell points at the exact raw-file line range, so the underlying data is fully traceable, but the registry itself stays at 82 rows instead of ~1600+"
  - "Reachability defect definition excludes chrome-less framework routes (login/error/onboarding/payment-return/referral-landing/index.html redirect) and dynamic detail pages reached by clicking a list row (client/:id, trainer/:id) from the 'no nav entry = defect' rule — these are reachable-by-design, not silently orphaned; only ComingSoon placeholders and completely unregistered ROUTES keys count as FUNC rows"
  - "Fixed a reachability-manifest.mjs parser bug during the tracer/verify loop: single-line router entries with an inline `element:` (e.g. `{ path: ROUTES.error, element: <ErrorPage ... /> }`) were mis-parsed as 'not registered' because the parser only checked resolution markers on lines *after* the path match, missing same-line markers — added a `direct` resolution kind and same-line lookahead"

requirements-completed: [AUD-02, AUD-03]

coverage:
  - id: D1
    description: "Every TODO/FIXME/HACK/XXX marker (46, re-derived via a pipe-free rg command) is a V41-HYG row in the registry, including named false positives (mktemp templates, doc-prose references)"
    requirement: AUD-02
    verification:
      - kind: other
        ref: "grep -cE \"^\\| V41-HYG-00[1-9]|^\\| V41-HYG-0[12][0-9]\" .planning/audits/staging/1a-hygiene.md == 27; rg -n --no-heading -e TODO -e FIXME -e HACK -e XXX apps/ packages/ infra/ tools/ | wc -l == 46 == wc -l of the archived markers.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "Knip, jscpd, vulture, deptry each ran once via pinned ephemeral runners (no repo-dependency changes) with raw output archived, and every finding class is a registry row (clustered by theme for high-volume tools) annotated with its false-positive dispatch pattern where applicable"
    requirement: AUD-02
    verification:
      - kind: other
        ref: "git diff --name-only <prior-commit>..HEAD | grep -E 'package.json|pnpm-lock.yaml|pyproject.toml|uv.lock' returns nothing; node tools/audit/merge-registry.mjs reports HYGIENE=72"
        status: pass
    human_judgment: false
  - id: D3
    description: "Import-linter's 3 contracts reviewed (0 broken, 5 stale ignore-list entries rowed) and the missing features/x->features/y admin ESLint zone assessed (28 current violations, rowed, NOT enabled)"
    requirement: AUD-02
    verification:
      - kind: other
        ref: ".planning/audits/v4.1-HYGIENE-RAW/import-linter.txt (Contracts: 3 kept, 0 broken); V41-HYG-071/072 rows; git diff --name-only shows no eslint.config/.eslintrc change"
        status: pass
    human_judgment: false
  - id: D4
    description: "Three-way reachability manifest (router x nav-items x screen component) built for apps/admin and apps/client; every ComingSoon/placeholder or unregistered-route screen is a V41-FUNC row with owning_phase 124"
    requirement: AUD-03
    verification:
      - kind: other
        ref: "node tools/audit/reachability-manifest.mjs (36 rows, 10 not-reachable for admin, 0 for client); grep -c 'V41-FUNC-00[1-8]' .planning/audits/staging/1a-hygiene.md == 8"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-07-26
status: complete
---

# Phase 122 Plan 2: Static Hygiene Sweep + Reachability Manifest Summary

**All static-hygiene tool output (46 markers, knip, jscpd, vulture, deptry, import-linter, admin ESLint) triaged into 72 clustered V41-HYG registry rows, plus a script-built router x nav x component reachability manifest for apps/admin and apps/client yielding 8 V41-FUNC rows (3 unregistered ROUTES keys, 5 ComingSoon placeholder groups) — apps/client has zero reachability defects.**

## Performance

- **Duration:** ~55 min (continuation of a plan a prior executor started; hygiene-tool runs and raw capture were already on disk at handoff)
- **Completed:** 2026-07-26
- **Tasks:** 3 completed
- **Files modified:** 4 (2 created fresh this session: `tools/audit/reachability-manifest.mjs`, `.planning/audits/v4.1-REACHABILITY-MANIFEST.md`; 2 modified: `1a-hygiene.md` staging, `v4.1-DEFECT-REGISTRY.md`) + 7 raw-archive files committed for the first time (captured pre-handoff, untracked until this plan)

## Accomplishments

- Re-derived the TODO/FIXME/HACK/XXX marker count fresh (46, matching the already-captured `markers.txt`) and triaged every marker into a V41-HYG row (27 rows, several clustering tight duplicate mentions in the same file per the plan's explicit allowance), correctly distinguishing genuine future-roadmap placeholders (Phase 50/91-93/99/104/117/B+/C+/X+ — none of which are v4.1 phases) from true false positives (mktemp template placeholders, ADR/README vocabulary legends, a `+7XXXXXXXXXX` phone-format example string).
- Triaged all four hygiene-tool archives (knip, jscpd, vulture, deptry) into 43 clustered V41-HYG rows spanning: legacy planning-mockup files, the entire `apps/admin/src/mocks/` layer, the parallel legacy `apps/admin/src/pages/**` surface (correlated with a large jscpd duplication cluster against the same files), shadcn/ui primitive exports (kept per convention), the `xKeys`/`ApiError` TanStack Query re-export convention, and — the largest cluster class — ~530 vulture findings resolved almost entirely to named false-positive dispatch patterns: FastAPI decorator-registered routes, Pydantic `model_config`/`cls`/reflected-field access, ARQ `WorkerSettings` lifecycle hooks, python-telegram-bot template-string dispatch, and the `LOCKED_EMAIL_TEMPLATES` AST-gate frozenset.
- Reviewed the 3 import-linter contracts (0 broken, 5 stale "ignored import — no matches" warnings rowed) and the admin ESLint boundary run (clean, zero findings). Measured the current `features/x -> features/y` cross-feature import violation count for the not-yet-enabled admin ESLint zone: 28 violations across 8 feature dirs (attendance, bookings, cashbox, dashboard, finance, load, payroll, search) — rowed per D-V41-ESLINT-ZONE-LAST, zone NOT enabled.
- Built `tools/audit/reachability-manifest.mjs`, a regex-based script joining `apps/admin/src/app/{routes.ts,router.tsx}` + `layouts/AppLayout/nav-items.ts` and `apps/client/src/{App.jsx}` + `components/TabBar.jsx`. Found and rowed 8 admin reachability defects (V41-FUNC-001..008): `clientsArchive`/`clientsDuplicates`/`trainersArchive` are defined in `ROUTES` but never registered in `router.tsx` (worse than a placeholder — the path 404s), and 5 already-known FND-04 ComingSoon groups (branches+branch detail, notifications, settings/system, settings/roles, settings/trash, settings/import-export). apps/client has zero reachability defects — every route resolves to a real, wired component.
- Merged all 82 rows (72 HYGIENE + 8 FUNC + the 2 pre-existing HARD GATE INFRA rows from 122-01) via `merge-registry.mjs`, verified idempotent (two consecutive runs produce a byte-identical registry) and self-test-clean.

## Task Commits

Each task's artifacts were committed atomically:

1. **Task 1: Marker enumeration + four hygiene tool runs (raw archive already captured pre-handoff)** — `93609dd5` (feat) — committed the raw archive (markers/knip/jscpd/vulture/deptry + import-linter/eslint-admin from Task 2, captured together in the prior session)
2. **Task 3: Reachability manifest script + manifest** — `b09fec3d` (feat)
3. **Tasks 1-3 triage: all findings appended as registry rows** — `59521be1` (feat) — 72 V41-HYG + 8 V41-FUNC rows in `1a-hygiene.md`, merged into `v4.1-DEFECT-REGISTRY.md`

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `tools/audit/reachability-manifest.mjs` - the AUD-03 three-way join script (admin + client)
- `.planning/audits/v4.1-REACHABILITY-MANIFEST.md` - 36-row manifest, methodology documented inline (reachability judgment criteria)
- `.planning/audits/v4.1-HYGIENE-RAW/{markers,knip,jscpd,vulture,deptry,import-linter,eslint-admin}.txt` - raw tool-output archive (captured by a prior executor, committed this plan)
- `.planning/audits/staging/1a-hygiene.md` - 72 V41-HYG + 8 V41-FUNC rows appended
- `.planning/audits/v4.1-DEFECT-REGISTRY.md` - regenerated by `merge-registry.mjs` from all three staging files (82 rows)

## Decisions Made

- **Row clustering for high-volume tool output** (see key-decisions in frontmatter): the raw tool runs surfaced ~1,600+ individual findings (knip alone: 137 unused files + 354 unused exports/types + assorted config hints; vulture: ~530 lines). Writing one row per literal finding would blow the registry's own "dozens, not hundreds" design intent (CONTEXT.md, D-122-01) past a thousand rows and make it useless as a triage artifact. Instead, findings were clustered by false-positive class or dead-code theme; each row's `anchor` cell lists every member path/line and `evidence` cites the exact raw-file line range, so the underlying finding-level detail remains fully traceable and re-derivable — nothing was silently dropped, per D-122-18.
- **Reachability-defect bar**: a route with no nav-sidebar/tab-bar entry is not automatically a defect if it's reachable by design — a chrome-less auth/framework route (login, error, onboarding, payment-return, referral deep-link, the `/index.html` compatibility redirect) or a dynamic detail page reached by clicking a list row (`/clients/:id`, `/trainers/:id`, and client `/settings` reached via the profile screen's gear icon). Only ComingSoon placeholders and routes that are defined in `ROUTES` but never registered in the router count as FUNC rows. This judgment is documented inline in both the manifest script's top comment and the emitted manifest file so Phase 124 (FUNC-05) consumers understand the bar applied.
- **`features/x -> features/y` ESLint zone measurement command**: used `grep -rnE "from ['\"]@/features/[a-zA-Z0-9_-]+"` per feature directory, filtering out matches against that directory's own name, rather than a single repo-wide grep, to get an accurate per-directory violation count (28 total across 8 dirs) matching the plan's exact instruction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a reachability-manifest.mjs parsing bug: single-line router entries misreported as unregistered**
- **Found during:** Task 3 verification (running the script and inspecting the emitted manifest)
- **Issue:** `router.tsx`'s `{ path: ROUTES.error, element: <ErrorPage code={500} /> }` puts both the path and its resolution on one line. The line-scanning parser only checked for `lazy`/`ComingSoon`/`Navigate` markers on lines *after* a `path:` match, so a same-line `element:` was never seen — `/error` was incorrectly reported as "not registered in router.tsx" (a false FUNC-worthy finding) when it is in fact registered with a real direct-element component.
- **Fix:** Added a `direct` resolution kind (any `element: <XxxComponent` that isn't `ComingSoon`/`Navigate`) and made the parser check the same line the `path:` match occurred on before falling through to subsequent lines.
- **Files modified:** `tools/audit/reachability-manifest.mjs`
- **Verification:** Re-ran the script; `/error` now correctly resolves to `ErrorPage` with `reachable = "yes — by design"`; not-reachable count dropped from the initially-wrong 11 to the correct 10.
- **Committed in:** `b09fec3d` (part of the Task 3 commit — the bug was caught and fixed before the first commit of this file, so there is no separate fix commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was applied before any commit of the affected script, so it required no follow-up commit — the committed script is already correct. No scope creep; no registry row was affected (the erroneous `/error` finding never made it into a committed row).

## Issues Encountered

None beyond the auto-fixed parser bug above. The prior executor's context-exhaustion handoff was clean: the raw tool archive was fully captured and untouched, and the staging file had only its header/schema row, so no reconciliation of partial/duplicate work was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Sub-pass 1a (static hygiene) is fully triaged: 82 total registry rows now exist (72 HYGIENE, 8 FUNC, 2 pre-existing INFRA HARD GATE rows from 122-01). `merge-registry.mjs` is proven idempotent against this larger payload.
- Phase 124 (FUNC-05) has its 8 reachability-defect rows plus the full manifest to work from; Phase 125 (HYG-02/HYG-04) has 72 hygiene rows with named false-positive dispatch patterns annotated, plus the 28-violation baseline for the deferred `features/x -> features/y` ESLint zone.
- Sub-passes 1b (live-backend hunt) and 1c (infra triage) remain outstanding for other plans in this phase (122-03/122-04/122-05 per the phase's plan numbering) before the final freeze (122-06).
- No blockers. `tools/audit/check-read-only.sh` passes against the full diff since phase-start (28 changed paths, all within `.planning/**`/`tools/audit/**`).

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Completed: 2026-07-26*

## Self-Check: PASSED

All 6 claimed files verified present on disk; all 3 claimed commit hashes (`93609dd5`, `b09fec3d`, `59521be1`) verified present in git history.
