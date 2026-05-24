# Phase 57: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults; review before planning)

<domain>
## Phase Boundary

The **v1.8 milestone-close handoff**. Two capabilities, both following the
established per-milestone pattern (v1.4–v1.7 precedent — the machinery already
exists; this phase exercises it for the v1.8 reporting surface):

1. **OpenAPI Handoff (HND-01..02)** — regenerate `apps/backend/openapi.json`
   and `packages/api-client/src/schema.d.ts` byte-stably so all v1.8 paths
   (`/reports/revenue`, `/reports/clients`, `/reports/visits`, `/audit-log`
   and their four `.csv` variants) appear in the typed schema, and extend
   `packages/api-client/src/schema.contract.test.ts` with `AssertNonNever`
   forward-guards + a bumped runtime count assertion for the v1.8 surface.
   CI `git diff --exit-code` stays green on both artifacts.
2. **Milestone Verification (VER-01..02)** — an operator runbook proving the
   reports + audit read API against a live `docker compose up` stack (revenue
   golden-path, audit filtering, reception 403, CSV-opens-in-Excel), plus
   automated correctness/race tests verifying aggregates against deterministic
   fixtures (kopecks net-of-refund, Europe/Moscow day-buckets incl. DST,
   visits hour-buckets, audit-log pagination stability, RBAC denial).

**In scope (HND-01, HND-02, VER-01, VER-02):**
- Byte-stable regen of `openapi.json` (`uv run python -m scripts.export_openapi`)
  + `schema.d.ts` (`pnpm --filter @sportzal/api-client codegen`); both committed,
  CI drift gates green.
- `_v18Checks` `AssertNonNever` tuple covering the 8 v1.8 paths + a dedicated
  `it(...)` runtime length assertion in `schema.contract.test.ts`.
- Automated correctness suite (VER-02) under `apps/backend/tests/integration/reports/`,
  including a **new dedicated DST-boundary golden test** (Phase 56 explicitly
  deferred the DST golden-path here).
- Integration tests asserting reception `GET /reports/revenue` and
  `GET /audit-log` both return 403 (VER-02 RBAC-denial).
- An operator runbook authored at `.planning/handoff/v1.8-reports-runbook.md`
  in the `v1.4-auth-runbook.md` sectioned format + operator attestation block.

**Out of scope (later phases / versions):**
- New endpoint bodies — all shipped in Phases 55-56; this phase only reflects,
  verifies, and documents them.
- Frontend audit-log viewer / report dashboards / CSV download buttons → v2.0.
- Live operator execution of the runbook (docker-compose walkthrough + manual
  Excel CSV open) → authored now, **execution operator-pending** per the
  established CARRY/DEFER pattern (see Deferred Ideas).
- Russian-Excel comma-decimal CSV dialect (Phase 56 D-13 researcher flag) — the
  runbook's "opens in Excel without mojibake" check is the validation point; a
  dialect change is only triggered if that check fails.

</domain>

<decisions>
## Implementation Decisions

> **Milestone-close machinery is LOCKED by precedent** (v1.4–v1.7). This phase
> reuses it verbatim; the decisions below record HOW it applies to v1.8, not new
> mechanisms. Endpoint behavior, RBAC, ordering, and CSV discipline are already
> locked by `55-CONTEXT.md` and `56-CONTEXT.md` — NOT re-decided here.

### OpenAPI + schema regeneration (HND-01)
- **D-01:** Regenerate `openapi.json` via the existing
  `apps/backend/scripts/export_openapi.py` (`uv run python -m scripts.export_openapi`).
  Byte-stability is already guaranteed by `json.dumps(..., indent=2, sort_keys=True,
  ensure_ascii=False) + "\n"` — **no changes to the exporter**. The script calls
  `create_app().openapi()` directly (no lifespan → no DB/Redis), so regen works in
  any env.
- **D-02:** Regenerate `schema.d.ts` via the existing pnpm codegen
  (`pnpm --filter @sportzal/api-client codegen` → `openapi-typescript`). **No tool
  or config changes.** Both artifacts committed; CI `backend` + `frontend` drift
  gates (`git diff --exit-code`, guarded by `git ls-files --error-unmatch`) stay
  green — the success bar is "regen produces zero diff."
- **D-03:** Because Phases 55-56 already shipped the endpoints, the regen may
  produce **no diff at all** if the artifacts were kept in lockstep during those
  phases. The plan must **verify** the v1.8 paths are present (not assume a diff);
  if a diff appears, commit it (`chore(57-NN): regen openapi.json + schema.d.ts
  for v1.8 surface`), consistent with prior `chore(46-01)` / `feat(40-04)` commits.

### Forward-guards + count assertion (HND-02)
- **D-04:** Add a new `const _v18Checks: [...] = [true, ...]` tuple to
  `schema.contract.test.ts` (mirroring `_v15Checks` / `_v16UsersChecks` pattern),
  with **one `AssertNonNever`-derived guard per v1.8 path** — the 4 JSON GETs
  (`/reports/revenue`, `/reports/clients`, `/reports/visits`, `/audit-log`) and the
  4 CSV GETs (`/reports/revenue.csv`, `/reports/clients.csv`, `/reports/visits.csv`,
  `/audit-log.csv`) = **8 guards**. Each anchors path existence + GET method +
  a reachable 2xx response.
- **D-05:** Add a dedicated `it('compiles against the regenerated v1.8 reports/audit
  surface (Phases 55-57)')` block with `expect(_v18Checks).toHaveLength(8)` — a NEW
  per-surface assertion, **not** a mutation of the existing v1.2/v1.4/v1.5/v1.6
  blocks (those stay byte-frozen at 10/36/11/5/4/2). This is the "runtime count
  assertion bumped to the new total" the roadmap SC#2 + HND-02 require, expressed
  in the file's established additive idiom.

### Correctness / race tests (VER-02)
- **D-06:** **Reuse existing infra** — tests live under
  `apps/backend/tests/integration/reports/`, on the SAVEPOINT-per-test conftest
  fixtures and factory builders. Phase 55 (`test_reports_revenue.py`,
  `test_reports_clients.py`, `test_reports_visits.py`) and Phase 56
  (`test_audit_log.py`) already cover most of VER-02; this phase **fills the gaps
  the roadmap names**, it does not rebuild coverage.
- **D-07:** **Add a dedicated DST-boundary golden test** — Phase 56 D-16/discretion
  explicitly deferred "the DST golden-path" to Phase 57. Assert that revenue/visits
  day-buckets land on the correct Europe/Moscow calendar dates across a DST
  transition (RU has no DST since 2014, so the meaningful assertion is **UTC↔MSK
  +03:00 offset stability** at midnight boundaries — confirm a payment/visit at
  `23:30Z` buckets into the **next** MSK day). Fixtures are deterministic, known
  kopeck amounts, net-of-refund.
- **D-08:** **Pagination-stability race test** for audit-log: insert a new
  `created_at`-newer row mid-pagination and assert page-1 rows do not shift
  (keyset `created_at DESC, id DESC`). If Phase 56 already added this, extend
  rather than duplicate.
- **D-09:** **RBAC-denial integration tests** — explicit assertions that reception
  `GET /api/v1/reports/revenue` → 403 and reception `GET /api/v1/audit-log` → 403
  (roadmap SC#4). Use the existing `authed_client_reception` fixture.

### Operator runbook (VER-01)
- **D-10:** Author `.planning/handoff/v1.8-reports-runbook.md` in the
  **`v1.4-auth-runbook.md` sectioned format**: numbered scenarios with concrete
  `curl` examples against the live stack, an operator attestation block at the
  bottom, and a reference to `apps/backend/openapi.json` as source-of-truth.
- **D-11:** Runbook scenarios (roadmap SC#5): (1) `docker compose up` bring-up;
  (2) revenue golden-path with **known fixture amounts** (the same deterministic
  amounts as the VER-02 golden test, so the operator can eyeball-match);
  (3) audit-log filter narrowing (actor / action / resource_type / time-window);
  (4) reception 403 on `/reports/*` and `/audit-log` (manual curl with a reception
  token); (5) CSV download of all four `.csv` endpoints + **open in Excel, confirm
  Cyrillic renders (no mojibake)** — this is the live validation of Phase 56 D-13.
- **D-12:** **Live execution is operator-pending.** VER-02 (automated tests) ships
  and runs in CI this phase. VER-01's live `docker compose up` walkthrough +
  manual Excel check is **authored now, executed by the operator** — consistent
  with every prior milestone's runbook (`v1.4-auth-runbook.md`,
  `v1.7-email-deliverability-evidence/`). Record it as an operator-pending item in
  STATE.md at phase close, not a blocker on phase completion.

### Claude's Discretion
- Exact wording/casing of the 8 `_v18Checks` type-alias names and which 2xx
  status each guard anchors.
- Whether the DST golden test and the existing Phase 55 bucketing tests are merged
  into one file or kept separate.
- Exact fixture kopeck amounts and dates (must be deterministic and shared between
  the VER-02 golden test and the VER-01 runbook so they cross-check).
- Runbook curl auth bootstrap details (how the operator obtains owner vs reception
  tokens against the live stack).
- Whether a small `v1.8-postman.json` is derived (as v1.4 did) or curl-only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — HND-01, HND-02, VER-01, VER-02 (exact wording).
- `.planning/ROADMAP.md` §"Phase 57" — goal + 5 success criteria (authoritative on
  byte-stable regen, forward-guards + count bump, correctness fixtures, RBAC 403,
  runbook scenarios).
- `.planning/phases/55-revenue-clients-visits-reports/55-CONTEXT.md` — locked report
  endpoint behavior, response shapes, Europe/Moscow bucketing (D-55-04).
- `.planning/phases/56-audit-log-read-api-csv-export/56-CONTEXT.md` — locked audit
  read API + CSV behavior; **D-13 ru-Excel flag** (runbook CSV-open check validates it);
  D-16 deferred the DST golden-path to THIS phase.

### OpenAPI handoff machinery (reuse verbatim)
- `apps/backend/scripts/export_openapi.py` — byte-stable exporter
  (`json.dumps(..., sort_keys=True)`, `create_app().openapi()`, env backfill). NO edits.
- `packages/api-client/package.json` §16/22 — `codegen` script
  (`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`),
  `openapi-typescript@^7.13.0`.
- `packages/api-client/src/schema.contract.test.ts` §15/21 — `AssertNonNever<T>`,
  `HasPath<P>`; §354-383 — per-surface `it(...)` count-assertion blocks (v1.2=10,
  v1.4=36, v1.5=11, v1.6 users=5/reset=4/email=2). ADD `_v18Checks` + a new block here.
- `.github/workflows/ci.yml` §50-64 (backend export + drift gate), §105-117
  (frontend codegen + drift gate) — the `git diff --exit-code` guards that must stay green.

### Endpoints under verification (source of truth)
- `apps/backend/app/modules/reports/router.py` — JSON + `.csv` report routes,
  `audit_log_router`, RBAC chokepoints.
- `apps/backend/app/modules/reports/service.py` / `repository.py` — aggregation
  functions producing the kopeck/bucket values the golden tests assert.
- `apps/backend/app/core/audit_models.py` — `AuditLog` ORM + `ix_audit_log_created_at
  (created_at DESC, id DESC)` (keyset ordering for the pagination-stability test).
- `apps/backend/app/core/permissions.py` — `(VIEW, REPORTS)` + `(LIST, AUDIT_LOG)`
  owner-only pairs (RBAC-denial tests).

### Test & runbook infra
- `apps/backend/tests/conftest.py` — SAVEPOINT-per-test fixtures, `authed_client_owner`
  / `authed_client_reception`, db_session, factories.
- `apps/backend/tests/integration/reports/` — existing `test_reports_revenue.py`,
  `test_reports_clients.py`, `test_reports_visits.py`, `test_audit_log.py` (extend, don't duplicate).
- `apps/backend/docker-compose.yml` — services for the live runbook (postgres, redis,
  backend, migrate).
- `.planning/handoff/v1.4-auth-runbook.md` — **runbook format template** (sectioned
  curl + attestation block). Also `.planning/handoff/v1.7-email-deliverability-evidence/README.md`
  for the operator-pending evidence-capture pattern.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/export_openapi.py`** — byte-stable OpenAPI exporter, used unchanged.
- **`@sportzal/api-client codegen`** — openapi-typescript pipeline, used unchanged.
- **`schema.contract.test.ts` per-surface idiom** — `_vXXChecks` tuple +
  `expect(...).toHaveLength(N)`; v1.8 follows the same additive shape.
- **Phase 55-56 report/audit integration tests** — most of VER-02 already exists;
  this phase fills named gaps (DST golden-path, explicit RBAC-denial assertions).
- **`authed_client_owner` / `authed_client_reception` fixtures** — RBAC-denial tests.
- **`v1.4-auth-runbook.md`** — runbook structure to clone for v1.8.

### Established Patterns
- **Byte-stable artifacts + CI drift gate** — local regen must produce zero
  `git diff`; `git ls-files --error-unmatch` prevents gitignore pass-through.
- **Additive contract assertions** — never mutate prior milestone count blocks;
  add a new `_v18Checks` block.
- **SAVEPOINT-per-test isolation** — correctness/race tests run on rolled-back
  transactions via conftest.
- **Operator-pending live walkthrough** — runbook authored in-phase, live docker
  execution recorded as a STATE.md operator-pending item (v1.4/v1.7 precedent).

### Integration Points
- `openapi.json` ← `create_app().openapi()` (all v1.8 routes already mounted).
- `schema.d.ts` ← generated FROM `openapi.json` (downstream of D-01).
- `schema.contract.test.ts` ← new `_v18Checks` block typed against `schema.d.ts`.
- CI `backend` + `frontend` jobs ← drift gates assert both artifacts.

</code_context>

<specifics>
## Specific Ideas

- This is a **close-out / proof phase**, not a build phase — the headline
  deliverable is "the v1.8 surface is contractually frozen and verifiably correct,"
  not new behavior. Plans should bias toward verification and regeneration, with
  zero new endpoint logic.
- The deterministic fixture amounts in the VER-02 golden test and the VER-01
  runbook **must be the same numbers**, so the operator's live eyeball-check
  cross-validates the automated test.
- The RU-no-DST reality (no DST since 2014) means the DST golden test's real job is
  asserting **stable +03:00 MSK offset bucketing at UTC midnight boundaries**, which
  is the actual correctness risk in `gym_date` / `AT TIME ZONE` logic.

</specifics>

<deferred>
## Deferred Ideas

- **Live operator execution of `v1.8-reports-runbook.md`** (docker-compose
  walkthrough + manual Excel CSV open) — authored this phase, executed by the
  operator; recorded operator-pending in STATE.md (consistent with CARRY-01/02,
  VER-03). Not a phase-completion blocker.
- **Russian-Excel comma-decimal / semicolon-delimiter CSV dialect** — only if the
  runbook's "opens in Excel without mojibake / numbers parse" check fails. Default
  stays Phase 56's RFC-4180 period-decimal.
- **Frontend admin-web reports/audit viewers + CSV download buttons** — v2.0.
- **`v1.8-postman.json` derivation** — optional nicety (v1.4 had one); curl-only
  runbook is sufficient unless the operator requests Postman.

None of the above are scope creep into Phase 57.

</deferred>

---

*Phase: 57-openapi-handoff-milestone-verification*
*Context gathered: 2026-05-24*
