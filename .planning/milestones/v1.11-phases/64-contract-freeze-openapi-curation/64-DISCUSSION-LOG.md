# Phase 64: Contract Freeze — OpenAPI Curation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 64-contract-freeze-openapi-curation
**Areas discussed:** Plan decomposition, Operation ID rename, Tag ordering, Error response envelope, Security schemes, Redocly lint, Baseline tag + CHANGELOG, Path discrepancy resolution, Byte-stability discipline
**Mode:** `--auto` — Claude selected recommended defaults; no user interaction.

---

## Plan decomposition (atomic commits)

| Option | Description | Selected |
|--------|-------------|----------|
| 7 plans, one per FRZ-* | Mirrors Phase 63 D-63-01 atomicity; smallest blast radius per commit | ✓ |
| 4 plans (cluster: metadata, structure, security/errors, lint/baseline) | Fewer commits; some FRZ-* mixed | |
| 1 plan (single mega-commit) | Smallest plan count, largest review burden | |

**Claude's choice:** 7 plans with FRZ-01+FRZ-04 bundled into 64-01 (both edit the same `FastAPI(...)` constructor block).
**Notes:** Atomicity > plan count. Each plan keeps drift gate green at HEAD (D-64-BYTE-STABLE).

---

## Operation ID rename (FRZ-02)

| Option | Description | Selected |
|--------|-------------|----------|
| `generate_unique_id_function` suffix-strip hook | Single registration in `app/main.py`; zero per-route `operation_id=` literals | ✓ |
| Explicit `operation_id=` on every route | 102+ literals to maintain; high drift surface | |
| Hybrid: hook + per-route override only on collisions | Adds branching; researcher decides post-collision check | (fallback) |

**Claude's choice:** Hook (per locked D-11-OPID). Hybrid retained as fallback if collisions surface.
**Notes:** admin-web scout (2026-05-26) confirmed zero `_api_v1_` references in `apps/admin-web/src/` — rename impact is mechanical regen only.

---

## Tag ordering (FRZ-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Business-flow order: Auth → Clients → Memberships → Visits → Schedule → Bookings → Trainers → Payments → Reports → Audit-log | Mirrors REQUIREMENTS.md FRZ-03 line 31; narrative-friendly for runbook | ✓ |
| Alphabetical | Easier to scan but breaks narrative | |
| By route count (largest first) | Operator-utility argument, but unstable as endpoints grow | |

**Claude's choice:** Business-flow order with `Internal` appended last for `_internal/*` endpoints.

---

## Error response envelope (FRZ-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Post-processor injects `$ref` after `app.openapi()` | One-place edit; routers untouched; byte-stability risk needs research verify | ✓ |
| Per-router `responses=...` kwarg | Idiomatic FastAPI; high-touch (every router edited) | |
| Per-route `responses=...` decorator arg | Most explicit; highest diff burden | |

**Claude's choice:** Post-processor. Researcher must confirm byte-stable output.

---

## Security schemes (FRZ-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Global default `cookieAuth + csrfHeader`; per-route `security: []` opt-out for public endpoints | Smallest diff; allowlist visible in `app/main.py` | ✓ |
| Per-route `Security(...)` on every authenticated route | Explicit at usage site; high-touch | |
| No global default; document scheme but apply only via runtime middleware | Spec wouldn't reflect actual security shape; codegen consumers would misread | |

**Claude's choice:** Global default + frozenset allowlist for public-route opt-out (mirrors `LOCKED_AUDIT_EVENTS` discipline).

---

## Redocly lint (FRZ-07)

| Option | Description | Selected |
|--------|-------------|----------|
| `extends: [recommended]` | Catches structural issues only; no stylistic noise | ✓ |
| `extends: [recommended-strict]` | Adds `examples` requirements + naming-strictness; balloons scope | |
| Custom ruleset from scratch | Maximum control; maintenance burden out of proportion to project scale | |

**Claude's choice:** `recommended` with documented per-rule disables only.

**CI placement:**
| Option | Description | Selected |
|--------|-------------|----------|
| New top-level `redocly-lint` job parallel to backend/frontend | Clean separation; matches existing 2-job structure | ✓ |
| Added as a step inside the `backend` job | Reuses backend Python env unnecessarily; serializes the lint | |

---

## Baseline tag + CHANGELOG (FRZ-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Annotated tag `contract-freeze-v1.11.0` + new `packages/api-client/CHANGELOG.md` | Tag carries inline message; CHANGELOG conventional for handoff | ✓ |
| Lightweight tag only | No commit message context | |
| CHANGELOG only, no tag | Loses git-tree pinpoint of the freeze | |

---

## Path discrepancy resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Update REQUIREMENTS.md FRZ-08 to correct paths during plan 64-07 closure | Aligns spec with reality; one-line amendment | ✓ |
| Move api-client to match the stale path | Major repo restructure; no benefit | |
| Leave requirement as-is, plan against actual paths | Documentation drift baked in | |

**Notes:** Actual paths are `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`. REQUIREMENTS.md line 35 references nonexistent `apps/admin-web/packages/api-client/...` — stale.

---

## Byte-stability discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Drift gate green per-plan (not just phase-close) | Each plan owns its regen; no poisoned tree inherited | ✓ |
| Single regen at phase close | Faster individual plans, brittle integration | |

**Claude's choice:** Per-plan drift-gate-green. Mirrors Phase 63 acceptance discipline.

---

## Claude's Discretion

- Exact regex for `generate_unique_id_function` suffix-strip hook — researcher finalizes against live operation-ID corpus.
- Choice of `app.openapi_schema = curated` vs override of `app.openapi()` method — whichever produces byte-stable output across cold/warm invocations.
- Order of public-endpoint allowlist entries in `app/main.py` (cosmetic).
- Whether `redocly.yaml` lives at repo root or under `apps/backend/` (root recommended).

## Deferred Ideas

- Per-operation `examples` payloads → Phase 65 (Postman handoff).
- Production / staging `servers[]` entries → v2.0.
- `sportzal_csrf` → `clubcore_csrf` cookie rename → v2.0 (D-11-CSRF-DEFER).
- `info.contact` / `info.license` → permanently omitted (D-11-DOCS-PRIVATE).
- AST-gating the public-endpoint allowlist frozenset → consider in Phase 66.
- `components.parameters.IdempotencyKey` → Phase 66 (IDM-04). Not in Phase 64.
- Public Redocly doc-site publish path → never (D-11-DOCS-PRIVATE).
