# Phase 57: OpenAPI Handoff + Milestone Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 57-openapi-handoff-milestone-verification
**Mode:** `--auto` (all gray areas auto-resolved to recommended defaults)
**Areas discussed:** Forward-guard granularity, Correctness-test scope, Operator-runbook format & gating, Regen + commit discipline

---

## Forward-guard granularity (HND-02)

| Option | Description | Selected |
|--------|-------------|----------|
| One guard per v1.8 path (8) | New `_v18Checks` tuple, one `AssertNonNever` per JSON+CSV path, dedicated `it()` with `toHaveLength(8)` | ✓ |
| Mutate existing count blocks | Fold v1.8 into an existing milestone block | |
| Per-method+response granular | Multiple guards per path (method, body, each 2xx) | |

**User's choice:** One guard per path (8), additive new block (recommended default).
**Notes:** Mirrors the file's established `_vXXChecks` per-surface idiom; never mutate the frozen v1.2/v1.4/v1.5/v1.6 blocks.

---

## Correctness-test scope (VER-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse + fill named gaps | Extend Phase 55-56 tests, add dedicated DST-boundary golden test + explicit RBAC-denial | ✓ |
| Rebuild full coverage | Fresh correctness suite from scratch | |

**User's choice:** Reuse existing infra + add DST golden test (Phase 56 deferred it here) + explicit reception-403 assertions (recommended default).
**Notes:** RU has no DST since 2014 → the real assertion is stable +03:00 MSK offset bucketing at UTC midnight boundaries.

---

## Operator-runbook format & gating (VER-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Author now, operator-pending exec | `.planning/handoff/v1.8-reports-runbook.md` in v1.4-auth-runbook format; live docker walkthrough executed by operator | ✓ |
| Block phase on live execution | Require live docker-compose run before phase close | |

**User's choice:** Author runbook + automate VER-02 fully; VER-01 live walkthrough operator-pending (recommended default).
**Notes:** Consistent with every prior milestone (v1.4-auth-runbook, v1.7-email-deliverability-evidence). Fixture amounts shared between golden test and runbook for cross-check.

---

## Regen + commit discipline (HND-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify presence, commit any diff | Run existing exporter/codegen unchanged; verify v1.8 paths present; commit diff if any | ✓ |
| Assume diff exists | Treat a diff as guaranteed | |

**User's choice:** Verify v1.8 paths present, commit diff only if produced (may be no-diff if kept in lockstep during Phases 55-56) (recommended default).
**Notes:** No edits to `export_openapi.py` or codegen config; CI drift gates are the success bar.

---

## Claude's Discretion

- `_v18Checks` type-alias naming + which 2xx status each guard anchors.
- DST golden test file placement (merged vs separate).
- Exact deterministic fixture amounts/dates (shared between golden test + runbook).
- Runbook curl auth bootstrap details; optional `v1.8-postman.json`.

## Deferred Ideas

- Live operator execution of the v1.8 runbook (operator-pending in STATE.md).
- Russian-Excel comma-decimal CSV dialect (only if Excel-open check fails).
- Frontend reports/audit viewers + CSV buttons (v2.0).
- `v1.8-postman.json` derivation (optional).
