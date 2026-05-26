# Phase 61: OpenAPI Handoff + Milestone Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 61-openapi-handoff-milestone-verification
**Mode:** `--auto` (Claude selected recommended defaults; no user prompts)
**Areas discussed:** OpenAPI regen execution, schema.d.ts regen, `_v19Checks` shape, count assertion, RBAC parity verification, route introspection coverage, runbook scope + scenarios, RBAC wording reconciliation, Postman export, test coverage delta, commit hygiene, operator-pending discipline

---

## Area 1 — OpenAPI regen mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `apps/backend/scripts/export_openapi.py` verbatim (`uv run python -m scripts.export_openapi`) | Existing byte-stable exporter; lifespan-safe; env backfill via `setdefault`; D-06 byte-stability already proven across 6 milestones | ✓ |
| Add a new regen script with extra v1.9-specific validation | Custom validator that asserts the 14 v1.9 paths are present before writing | |
| Hand-edit `openapi.json` to add missing paths | Anti-pattern; CI drift gate would catch the divergence next regen | |

**Selected:** Reuse existing exporter verbatim (D-61-01).
**Auto-rationale:** v1.4 / v1.5 / v1.6 / v1.7 / v1.8 all used the existing exporter; the script's byte-stability and lifespan-safety are proven. v1.9 follows the same precedent.

---

## Area 2 — schema.d.ts regen mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `pnpm --filter @sportzal/api-client codegen` (openapi-typescript@^7.13.0) | Existing pnpm workspace script; pinned version | ✓ |
| Bump `openapi-typescript` to latest | Could introduce breaking emit changes (e.g., 7.x → 8.x output shape) — would break the byte-stable drift gate | |
| Hand-edit `schema.d.ts` | Anti-pattern; CI drift gate reverts on next codegen | |

**Selected:** Reuse codegen verbatim, no version bump (D-61-02).

---

## Area 3 — `_v19Checks` tuple shape

| Option | Description | Selected |
|--------|-------------|----------|
| One `_v19Checks` tuple with 14 entries, one alias per path×method | Mirrors `_v18Checks` exact shape; PascalCase aliases prefixed `_` | ✓ |
| Split into `_v19PayrollChecks` / `_v19ScheduleChecks` / `_v19ReportsChecks` | Three smaller tuples with separate `it(...)` blocks; could clutter `describe()` | |
| Embed all checks inline in a single `it()` without a named tuple | Loses the compile-time tuple-length safety net | |

**Selected:** One `_v19Checks` tuple with 14 entries (D-61-03).
**Auto-rationale:** Mirrors `_v18Checks` precedent exactly. Splitting by module adds bookkeeping cost without buying anything; the count assertion already gives module-grouping clarity via the `it(...)` description string.

---

## Area 4 — Count-assertion `it(...)` block

| Option | Description | Selected |
|--------|-------------|----------|
| NEW dedicated `it('compiles against the regenerated v1.9 trainers surface (Phases 58-60)')` block with `expect(_v19Checks).toHaveLength(14)` | Additive idiom; prior counts byte-frozen | ✓ |
| Mutate the `_v18Checks` it() block to combine v1.8 + v1.9 | Breaks the per-milestone audit trail; mutates a byte-frozen count | |
| Skip count assertion; rely on compile-time tuple length alone | Loses runtime locking; ROADMAP SC#2 explicitly requires "runtime `toHaveLength(N)` assertion" | |

**Selected:** New dedicated block, prior blocks byte-frozen (D-61-04).

---

## Area 5 — Three-way RBAC parity

| Option | Description | Selected |
|--------|-------------|----------|
| Run existing `test_rbac_parity.py` + introspection; expect green; no edits | Phase 58 INFRA-15 / D-58-15 already shipped v1.9 pairs in both source-of-truth files | ✓ |
| Add new `Resource.TRAINER_PAYROLL` enum entry + new OWNER_ONLY pairs | HND-01 wording mentions this; literal enum does not exist; D-58-15 collapse already covers the surface | |
| Add per-endpoint reception-403 tests for each new v1.9 owner-only route | Duplicates route-introspection guard; D-60-13 / Phase 56 precedent says no duplication | |

**Selected:** Run + verify; no edits expected (D-61-05 + D-61-06 + D-61-08).
**Auto-rationale:** The v1.9 pairs were locked in Phase 58 with three-way parity already in place; Phases 59 / 60 added zero new pairs. The HND-01 wording slip (`Resource.TRAINER_PAYROLL`) is reconciled in D-61-08.

---

## Area 6 — Runbook scope + scenarios

| Option | Description | Selected |
|--------|-------------|----------|
| 5 scenarios (bring-up, payroll golden, schedule golden, trainer report, reception 403) mirroring v1.8 D-11 | Comparable scope to v1.8 runbook; covers every new v1.9 surface area | ✓ |
| 3 scenarios (bring-up, full v1.9 golden, reception 403) | Faster to author but loses per-area eyeball-match clarity | |
| 7+ scenarios (split payroll into config / preview / accrual / mark-paid; split schedule into recurring / time-off) | Over-detailed; operator burns time on micro-steps | |
| Skip runbook (rely on automated tests only) | Violates ROADMAP SC#4 explicit runbook requirement | |

**Selected:** 5 scenarios mirroring v1.8 D-11 (D-61-07).

---

## Area 7 — Postman v2.1 export

| Option | Description | Selected |
|--------|-------------|----------|
| Skip `v1.9-postman.json` (only v1.4 shipped Postman) | v1.5 / v1.6 / v1.7 / v1.8 precedent; HND-01 does not require it | ✓ |
| Generate `v1.9-postman.json` via `apps/backend/scripts/export_postman.py` | Would add a 4th plan with marginal value; no external-integrator demand documented | |

**Selected:** Skip Postman (D-61-09).

---

## Area 8 — Test coverage delta

| Option | Description | Selected |
|--------|-------------|----------|
| Zero new tests; verify existing Phase 58/59/60 coverage is green at milestone gate | Per-pitfall goldens + RBAC denial + introspection already shipped; gaps belong in originating phase | ✓ |
| Add a Phase 61 VER test suite duplicating v1.9 endpoint coverage | Duplicates existing coverage; violates per-phase ownership | |
| Add only the gaps Phase 61 discovers (case-by-case) | Slippery slope; opens door to scope creep | |

**Selected:** Zero new tests; verify green (D-61-10).

---

## Area 9 — Live execution discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Operator-pending (CARRY pattern; STATE.md entry; v1.4 / v1.7 / v1.8 precedent) | Runbook authored & committed in Phase 61; live walkthrough by operator post-merge | ✓ |
| Blocking (Phase 61 cannot close until operator runs the runbook live) | Breaks the established v1.4 / v1.7 / v1.8 CARRY pattern; couples agent work to operator availability | |

**Selected:** Operator-pending (D-61-12).

---

## Claude's Discretion (no auto-decision needed)

- Exact casing / wording of the 14 `_v19Checks` type-alias names (within PascalCase-with-underscore-prefix convention).
- Whether to anchor each guard to a specific 2xx status code (recommended: status-anchor for POST/PUT/DELETE where 200→201/204 regression matters; path-method only for GETs).
- Exact wording of runbook scenario titles / `curl` examples (within v1.8 sectioned format).
- Final plan count (2–4 depending on whether regen produces a diff).
- Whether the runbook adds a §6 "Audit log read-back" sanity check (recommended: SKIP — v1.8 covers audit-log; v1.9 adds zero new audit events).

## Deferred Ideas

- `apps/admin-web` UI for v1.9 surface — admin-web frozen in v1.9; v1.10+ owns FE integration.
- `v1.9-postman.json` — explicit anti-feature per D-61-09; v2.0 may reintroduce if demand emerges.
- Live operator execution of runbook — operator-pending per CARRY pattern.
- REQUIREMENTS.md wording fix for `Resource.TRAINER_PAYROLL` slip — milestone-close housekeeping, not Phase 61 work.
- Tech-debt sweep (DEFER-46-04 / DEFER-40-01) — already deferred to v1.10.
- New `Resource.TRAINER_PAYROLL` enum — unnecessary per D-61-08.
- 1C / iCal / FE dashboards / predictive analytics — v1.10+ / v2.0 research anti-features.
- Russian-Excel comma-decimal CSV dialect — only triggered if runbook §4 Excel-open check fails.
- Additional automated VER tests — Phases 58 / 59 / 60 cover the surface end-to-end.
