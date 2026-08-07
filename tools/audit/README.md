# tools/audit — v4.1 defect-registry pipeline

This directory holds the tooling for the v4.1 Codebase Hardening milestone's audit phase
(Phase 122, `.planning/phases/122-audit-registry-producing-read-only-pass/`). It is **audit
tooling, not application code** — nothing here is wired into CI or `package.json` (see D-122-24;
the audit phase is read-only by construction).

## The staging → merge → freeze protocol (D-122-04, D-122-05)

The v4.1 defect registry is a single file: `.planning/audits/v4.1-DEFECT-REGISTRY.md`. Exactly
one registry exists (AUD-01) — but it is filled in by **three sub-passes that run in parallel**:

- **1a** — static hygiene sweep (no running infra)
- **1b** — live-backend hunt (needs a running seeded backend)
- **1c** — infra triage (desk review)

To make three genuinely parallel writers safe with zero merge conflicts, none of them writes the
registry file directly. Instead:

1. **Staging.** Each sub-pass appends rows only to its own file under `.planning/audits/staging/`:
   - `1a-hygiene.md` (ID prefix `V41-HYG`, primarily)
   - `1b-live.md` (ID prefix `V41-FUNC`, primarily)
   - `1c-infra.md` (ID prefix `V41-INFRA`, primarily)

   A staging file may legitimately contain rows of **more than one category** — for example,
   sub-pass 1a's static sweep also produces the reachability-manifest findings, whose `category`
   column is `FUNC`, not `HYGIENE`. The staging *file* a row lives in is just "who wrote it and
   when"; it carries no routing meaning.

2. **Merge.** `merge-registry.mjs` reads all three staging files and routes **each row** into the
   registry by reading that row's own `category` column (`FUNC` → `## FUNC`, `HYGIENE` →
   `## HYGIENE`, `INFRA` → `## INFRA`) — **never** by which staging file the row came from. It:
   - preserves every row's ID verbatim (IDs are permanent — D-122-02),
   - is idempotent (re-running with unchanged staging input produces a byte-identical registry),
   - refuses to run if any two rows anywhere share an ID,
   - asserts every emitted row's `category` column agrees with the section it lands under.

   Run it after any sub-pass appends new rows:

   ```bash
   node tools/audit/merge-registry.mjs
   ```

   Run the built-in fixture test suite (no filesystem writes) with:

   ```bash
   node tools/audit/merge-registry.mjs --self-test
   ```

3. **Freeze** (Phase 122's final plan, 122-06). The registry's frontmatter
   (`frozen_at_commit`, `frozen_at`, `row_count_at_freeze`) is populated, the three staging files
   are **deleted**, and the three registry tables become append-nothing: after freeze, only the
   `disposition` and `evidence` cells of existing rows may change, and new findings from later fix
   phases go only into the trailing `## Discovered during fix` section, tagged
   `discovered-during-fix` with the phase that found them (D-122-05). This never triggers a new
   audit sweep (D-V41-AUDIT-FREEZE).

## Read-only enforcement (AUD-08 / D-122-24)

`check-read-only.sh` (added alongside the phase-start SHA in this plan's Task 2) is the
mechanical proof that the audit phase makes zero application-code edits. It diffs the recorded
phase-start commit against `HEAD` and asserts every changed path matches the allowlist:
`.planning/**`, `tools/audit/**` (new files only), `apps/backend/scripts/seed_edge_cases.py`
(new file only). This same script is the authoritative phase-exit gate run again in 122-06.

## Files

| File | Purpose |
|------|---------|
| `merge-registry.mjs` | Staging → registry merge, routes by row `category`, idempotent, ID-collision-safe. `--self-test` runs an in-memory fixture suite. |
| `check-read-only.sh` | Diffs `<phase-start-sha>..HEAD` against the AUD-08 allowlist; exits non-zero on any disallowed path. |
| `README.md` | This file. |
