# Phase 35: OpenAPI Drift Gate (backend-only API handoff) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 35-OpenAPI-Drift-Gate-(backend-only-API-handoff)
**Areas discussed:** Regen mechanics & atomicity, Forward-guard scope, README format, admin-web canary handling, Plan structure, Verification & rollback
**Mode:** `--auto` — single-pass autonomous selection; recommended (precedent-matching) option chosen for every gray area. No `AskUserQuestion` calls.

---

## Regen mechanics & atomicity

### Q1 — Commit shape for the regen?

| Option | Description | Selected |
|--------|-------------|----------|
| Single atomic commit (json + d.ts together) | One commit holds both regenerated artifacts; mirrors v1.2 D-21-1 + v1.3 Phase 28; drift-gate sees a coherent delta | ✓ (recommended) |
| Two sequential commits (json first, d.ts second) | Eases revert if codegen step fails, but creates an intermediate state where openapi.json is ahead of schema.d.ts → CI red between commits | |
| Combined with router/schema edits in same commit | Mixes generated artifacts with handwritten source → review pain, harder to bisect | |

**Selected:** Single atomic commit.
**Why (auto):** Phase 21 + Phase 28 both used this; CI drift-gate is designed around it; no reason to deviate.

### Q2 — Handle byte-stable canonicalization?

| Option | Description | Selected |
|--------|-------------|----------|
| Rely on existing `export_openapi.py` discipline | Script already enforces `indent=2, sort_keys=True, ensure_ascii=False` + trailing newline; no change needed | ✓ (recommended) |
| Add post-regen normalizer step | Re-pipe through `jq -S` or similar; redundant given the script's contract | |
| Edit the script for v1.4 | Risk of churn on a load-bearing utility for no contract gain | |

**Selected:** Rely on `export_openapi.py` as-is.
**Why (auto):** D-21 precedent; script is canonical; v1.4 has no new canonicalization requirement.

---

## Forward-guard extension scope

### Q3 — What to pin in `schema.contract.test.ts`?

| Option | Description | Selected |
|--------|-------------|----------|
| Paths + methods + body-realisation + response-realisation (per-module spot-check) | Mirrors existing v1.2 surface block; catches openapi-typescript v7→v8 regressions, body-collapse-to-never, missing 2xx | ✓ (recommended) |
| Paths only (one assertion per path, no method granularity) | Cheaper to maintain; misses POST-method regressions on multi-method paths | |
| Paths + operationIds | Operation IDs are auto-generated and brittle; pinning them freezes a name the team has not curated | |
| Full schema snapshot (jest-style toMatchSnapshot) | Heavy; produces noisy diffs on minor reshapes; not the established pattern | |

**Selected:** Paths + methods + body-realisation + response-realisation (per-module spot-check).
**Why (auto):** Matches Phase 21 D-21-4 pattern exactly; full inventory of new paths enumerated in CONTEXT D-35-05.

### Q4 — Conditional (`HasPath`) probes for any v1.4 endpoints?

| Option | Description | Selected |
|--------|-------------|----------|
| All assertions hard (`AssertNonNever`) | Every v1.4 path landed in Phases 31–34; no forward-looking endpoints | ✓ (recommended) |
| Conditional probes for refund + cancel | Defensive against partial-landing scenarios; unnecessary because Phases 32–34 all merged | |

**Selected:** All hard assertions.
**Why (auto):** v1.4 backend is feature-complete; STATE.md confirms Phases 30–34 all `Complete`.

---

## README format

### Q5 — How verbose should the v1.4 changelog be?

| Option | Description | Selected |
|--------|-------------|----------|
| Concise: one bullet per module group, point to openapi.json for full surface | Stays accurate; no rot surface | ✓ (recommended) |
| Detailed table per endpoint | Big rot surface; duplicates source of truth | |
| Link-only (no inline summary) | Loses orientation for design-team readers | |

**Selected:** Concise per-module bullets + pointer.
**Why (auto):** D-35-10 — README is a directory marker, not a contract; openapi.json is authoritative.

### Q6 — Auth quick-start: inline tutorial or pointer?

| Option | Description | Selected |
|--------|-------------|----------|
| Pointer to existing § CSRF / § Single-flight refresh + path list | Concise; existing sections are accurate | ✓ (recommended) |
| Inline curl examples for login + refresh + CSRF | Big maintenance burden; v1.5 Postman collection will own examples | |
| Separate `AUTH.md` file | Adds surface; nothing to put there that isn't already in router docstrings | |

**Selected:** Pointer + path list, no inline tutorial.
**Why (auto):** Phase 35 ships contract + types + nav; v1.5 owns runnable examples.

---

## admin-web canary handling

### Q7 — How to handle the admin-web 233 vitest specs after regen?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard canary — must pass unchanged; any failure is a backend issue, fix backend | Frozen-as-of-v1.3 contract; failure proves a real BC break | ✓ (recommended) |
| Soft canary — allowed to fail with explanatory comment | Defeats the pivot's guarantee that admin-web stays compatible with v1.4 backend | |
| Downgrade admin-web CI gate to non-blocking | Premature; that's a v2.0 concern when external frontends ship | |
| Edit admin-web sources to absorb regen drift | Violates the frozen-as-of-v1.3 mandate; pivot explicitly forbids | |

**Selected:** Hard canary.
**Why (auto):** Frozen-mock-reference contract; the canary's whole purpose is to detect schema BC breaks.

### Q8 — Touch any admin-web files in Phase 35?

| Option | Description | Selected |
|--------|-------------|----------|
| Zero edits inside `apps/admin-web/` | Pivot mandate; plan-checker should reject any plan with admin-web src edits | ✓ (recommended) |
| Allow type-only updates to absorb codegen drift | Slippery slope; if drift surfaces, fix backend instead | |

**Selected:** Zero edits.
**Why (auto):** D-35-14; pivot is firm.

---

## Plan structure

### Q9 — How many plans for Phase 35?

| Option | Description | Selected |
|--------|-------------|----------|
| 2 plans: wave-1 regen + wave-2 forward-guard + README (wave-2 depends on wave-1) | Smallest coherent split; lets executor verify drift-gate green before extending guard | ✓ (recommended) |
| 1 plan: everything in one commit | Loses ability to verify drift-gate independently of test changes; harder to bisect | |
| 3 plans: regen + forward-guard + README | Ceremony without value; forward-guard + README are deterministic from the regenerated artifacts | |
| 8 plans (Phase 28 shape) | UI-heavy; doesn't fit backend-only handoff | |

**Selected:** 2 plans (wave-1 regen + wave-2 forward-guard & README).
**Why (auto):** D-35-16; backend-only scope is smaller than Phase 28; minimal-coherent split.

---

## Verification & rollback posture

### Q10 — Local verification protocol before commit?

| Option | Description | Selected |
|--------|-------------|----------|
| Full mirror of CI gates locally (export → codegen → typecheck → test → diff --exit-code) | Catches regressions before push; matches what CI will run | ✓ (recommended) |
| Trust CI to be the first run | Wastes CI minutes; slower feedback loop on drift | |
| Partial local run (skip admin-web tests) | Misses canary breakage early | |

**Selected:** Full local mirror (sequence in D-35-18).
**Why (auto):** Drift-gate is unforgiving; cheaper to catch locally.

### Q11 — Rollback posture if regen surfaces a schema regression?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix backend source, re-regen; never edit artifacts | Single source of truth discipline | ✓ (recommended) |
| Hand-edit `openapi.json` or `schema.d.ts` to absorb | Breaks reproducibility; CI will diff next time someone regens | |

**Selected:** Source fix only.
**Why (auto):** D-35-19; artifacts are generated, not authored.

---

## Claude's Discretion

- **Order of method assertions inside `schema.contract.test.ts`** — by-module in roadmap-phase order (31 → 34).
- **Comment style for the new contract-test block** — per-module section headers `// --- v1.4 trainers (Phase 31) ---` matching existing v1.2 header style.
- **README markdown style** — H2 changelog section with bullet list, no nested tables.

## Deferred Ideas

- Postman / curl integration collection (v1.5 API Handoff).
- Doc-string cleanup of stale "Phase 35 UI" / "FE-13 in Phase 35" references in `memberships/router.py` + `payments/router.py` (v1.5 cleanup wave).
- `@sportzal/api-client` package.json version bump (v1.5 publish prep).
- Auto-publishing `openapi.json` to versioned URL (v1.5 concern).
- OpenAPI tag curation (v1.5 hygiene).
- operationId hygiene with explicit `operation_id=` decorators (v1.5+ after design-team feedback).
