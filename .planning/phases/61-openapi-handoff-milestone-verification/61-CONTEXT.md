# Phase 61: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults grounded in
REQUIREMENTS HND-01, ROADMAP Phase 61 success criteria 1..4, and the
v1.8 milestone-close precedent at `.planning/milestones/v1.8-phases/57-openapi-handoff-milestone-verification/57-CONTEXT.md`;
review before planning.)

<domain>
## Phase Boundary

The **v1.9 milestone-close handoff** — the final phase of milestone
"v1.9 Trainers Complete" (Phases 58–60). Two capabilities, both already
exercised in v1.4 / v1.5 / v1.6 / v1.8 (the machinery is built, this phase
re-runs it for the v1.9 surface):

1. **OpenAPI Handoff (HND-01)** — regenerate `apps/backend/openapi.json` and
   `packages/api-client/src/schema.d.ts` byte-stably so all v1.9 path×method
   combinations appear in the typed schema, and extend
   `packages/api-client/src/schema.contract.test.ts` with `_v19Checks`
   `AssertNonNever` forward-guards plus a bumped runtime
   `toHaveLength(N)` assertion. CI `git diff --exit-code` stays green on
   BOTH artifacts (`.github/workflows/ci.yml:50-64` backend drift gate,
   `:105-117` frontend drift gate).

2. **Three-way RBAC parity check** — verify the EXISTING
   backend ↔ admin-web ↔ registry parity test
   (`apps/backend/tests/integration/test_rbac_parity.py`) is green at the
   milestone gate. Verify the EXISTING route-introspection guard
   (`apps/backend/tests/integration/test_route_introspection.py`) covers
   all new v1.9 owner-only routes with no per-endpoint duplication.
   **No code edits expected** — Phase 58 INFRA-15 / D-58-15 already shipped
   the `(CREATE, COMPENSATION)`, `(CREATE, PAYROLL)`, `(EDIT, PAYROLL)`,
   `(REFUND, PAYROLL)`, `(LIST, PAYROLL)` OWNER_ONLY pairs in BOTH
   `apps/backend/app/core/permissions.py` (L136-140) and
   `apps/admin-web/src/shared/session/can.ts` (L72-76). Phase 59 / 60 added
   ZERO new OWNER_ONLY pairs (D-59-08 / D-60-08 precedent). The HND-01
   wording "`Resource.TRAINER_PAYROLL` + новые OWNER_ONLY пары" refers to
   the already-shipped PAYROLL/COMPENSATION pairs (see D-61-08).

3. **Milestone verification runbook** — author
   `.planning/handoff/v1.9-trainers-runbook.md` in the
   `v1.8-reports-runbook.md` sectioned format covering bring-up + golden
   scenarios for the v1.9 surface (payroll comp-config + accruals + mark-paid;
   recurring slot templates; time-off blocks; trainer-usage report JSON +
   CSV; reception 403 on every new owner-only route; CSV-opens-in-Excel +
   Cyrillic-renders confirmation). **Live execution is operator-pending**
   per the v1.4 / v1.7 / v1.8 CARRY pattern (D-12 from Phase 57 precedent).

**v1.9 surface to lock in `_v19Checks` (14 path×method entries — verified
against the live FastAPI routers at planning time):**

Payroll (`/api/v1/payroll/*` — Phase 58 INFRA-15 / PAY-01..06):
- `PUT  /api/v1/payroll/trainer-configs/{trainer_id}` — upsert compensation config
- `GET  /api/v1/payroll/trainer-configs/{trainer_id}` — read compensation config
- `GET  /api/v1/payroll/preview` — read-only accrual preview
- `POST /api/v1/payroll/accruals` — append accrual ledger entry
- `GET  /api/v1/payroll/accruals` — paginated list
- `POST /api/v1/payroll/accruals/{accrual_id}/mark-paid` — mark accrual paid

Schedule v1.9 (Phase 59 REC-01..04 / TOFF-01..03):
- `POST /api/v1/recurring-templates` — create recurring slot template
- `POST /api/v1/recurring-templates/{template_id}/deactivate` — deactivate template
- `GET  /api/v1/recurring-templates` — paginated list
- `POST /api/v1/time-off` — create time-off block
- `DELETE /api/v1/time-off/{time_off_id}` — delete time-off block
- `GET  /api/v1/time-off` — paginated list

Reports v1.9 (Phase 60 RPT-01..04):
- `GET  /api/v1/reports/trainers` — trainer-usage report (JSON)
- `GET  /api/v1/reports/trainers.csv` — trainer-usage report (CSV)

**Expected runtime count:** `expect(_v19Checks).toHaveLength(14)` —
each entry is one `AssertNonNever<paths[...]>` derivation anchored to
path + method (mirrors `_v18Checks` 8-entry shape at L378-387). If the
planner finds additional v1.9 path×method combos at codification time
(e.g., a `DELETE /payroll/accruals/{id}` clawback endpoint that this
context missed), the count adjusts accordingly — the SHAPE is locked, the
exact count is verified at planning time by re-grepping the v1.9 routers.

**In scope (HND-01 success criteria 1..4):**
- Run `uv run python -m scripts.export_openapi` from `apps/backend/`;
  commit any resulting `apps/backend/openapi.json` diff.
- Run `pnpm --filter @sportzal/api-client codegen` from repo root; commit
  any resulting `packages/api-client/src/schema.d.ts` diff.
- Extend `packages/api-client/src/schema.contract.test.ts` with a NEW
  `_v19Checks` tuple covering the 14 v1.9 path×method entries plus a
  NEW dedicated `it('compiles against the regenerated v1.9 trainers
  surface (Phases 58-60)')` block with
  `expect(_v19Checks).toHaveLength(14)`. Existing `_checks` / `_v14Checks`
  / `_v15Checks` / `_v16UsersChecks` / `_v16ResetChecks` / `_v16EmailChecks`
  / `_v18Checks` blocks stay **byte-frozen** (10 / 36 / 11 / 5 / 4 / 2 / 8).
- Verify (do NOT edit) backend ↔ admin-web RBAC parity by running
  `apps/backend/tests/integration/test_rbac_parity.py` — expected green
  because Phase 58 already shipped the v1.9 OWNER_ONLY pairs in BOTH
  source-of-truth files and Phases 59 / 60 added zero new pairs.
- Verify route-introspection guard
  (`apps/backend/tests/integration/test_route_introspection.py`)
  auto-discovers all new v1.9 owner-only routes and confirms each is
  protected — no per-endpoint reception-403 test duplication needed.
- Author `.planning/handoff/v1.9-trainers-runbook.md` (sectioned format,
  operator attestation block, `OPERATOR-PENDING (D-12)` disclaimer mirroring
  v1.8 runbook).

**Out of scope (later phases / explicit anti-features):**
- New endpoint bodies — all shipped in Phases 58–60; this phase only
  reflects, verifies, and documents them.
- New `Resource` enum entries, new OWNER_ONLY pairs, or any edits to
  `permissions.py` / `can.ts` / `registry.ts` (D-61-08 — parity is already
  achieved; HND-01 "`Resource.TRAINER_PAYROLL`" wording refers to the
  already-shipped `Resource.PAYROLL` + `Resource.COMPENSATION` pairs).
- Frontend admin-web UI for any v1.9 surface (admin-web frozen in v1.9 per
  D-58-22 / D-59-08 / D-60-08; v1.10+ owns the FE integration consuming the
  regenerated `schema.d.ts`).
- Live operator execution of the runbook (`docker compose up` walkthrough
  + manual Excel CSV open) → authored now, **execution operator-pending**
  per the established CARRY/DEFER pattern (D-12 v1.8 precedent).
- Postman v2.1 export (`v1.9-postman.json`) — v1.6 / v1.7 / v1.8 milestones
  did NOT ship Postman exports; only v1.4 did (HANDOFF-04 / D-46-08). NOT
  required by HND-01 wording, NOT in success criteria. (D-61-09)
- New automated VER tests beyond what already exists — Phase 58 / 59 / 60
  already shipped per-pitfall goldens, RBAC denial assertions, route
  introspection, and CSV goldens. Phase 61 verifies these are green at
  the milestone gate; it does NOT rebuild coverage. (D-61-10)
- 1C / external payroll export, iCal sync, FE dashboards, predictive
  analytics — v1.10+ / v2.0 concerns (research anti-features).
- Russian-Excel comma-decimal CSV dialect — the runbook's "opens in Excel
  without mojibake" check is the validation point; a dialect change is
  only triggered if that check fails (v1.8 D-13 precedent).

</domain>

<decisions>
## Implementation Decisions

> **Milestone-close machinery is LOCKED by precedent** (v1.4 / v1.5 / v1.6
> / v1.8). This phase reuses it verbatim — the decisions below record HOW it
> applies to the v1.9 trainers surface, NOT new mechanisms. The Phase 57
> CONTEXT.md (`.planning/milestones/v1.8-phases/57-openapi-handoff-milestone-verification/57-CONTEXT.md`)
> is the closest analog and is authoritative on the exporter / codegen /
> contract-test idiom.

### OpenAPI regeneration (D-61-01)
- **D-61-01:** Regenerate `apps/backend/openapi.json` via the existing
  `apps/backend/scripts/export_openapi.py`
  (`uv run python -m scripts.export_openapi` from `apps/backend/`).
  Byte-stability is guaranteed by the exporter's
  `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`
  (D-06 from Phase 9 / verified in `scripts/export_openapi.py:60`).
  **NO changes to the exporter, NO env tweaks** — the script's
  `os.environ.setdefault` block already backfills DB/Redis/SECRET_KEY
  placeholders (`.py:31-42`); `create_app().openapi()` never enters the
  combined lifespan, so Postgres/Redis are not touched.
- The planner verifies (does not assume) that the regenerated
  `openapi.json` contains the 14 v1.9 path×method entries listed in
  `<domain>` before committing. If a diff appears, commit it as
  `chore(61-NN): regen openapi.json for v1.9 trainers surface`.
  If NO diff appears (artifacts kept in lockstep during Phase 58/59/60
  shipping), still commit a `chore(61-NN): verify openapi.json v1.9 paths
  present (no diff)` no-op marker — actually omit the commit when no diff
  exists (no-op commits are anti-pattern); instead the SUMMARY notes that
  the artifact was already in lockstep.

### schema.d.ts regeneration (D-61-02)
- **D-61-02:** Regenerate `packages/api-client/src/schema.d.ts` via
  `pnpm --filter @sportzal/api-client codegen` (from repo root).
  Underlying command: `openapi-typescript ../../apps/backend/openapi.json
  --output src/schema.d.ts` (`packages/api-client/package.json:16`).
  **NO `openapi-typescript` version bump, NO codegen CLI flag changes** —
  the existing pin `^7.13.0` (`:22`) is the contract.
  Same lockstep verification as D-61-01: commit any diff as
  `chore(61-NN): regen schema.d.ts for v1.9 trainers surface`.

### Forward-guards tuple (D-61-03)
- **D-61-03:** Add a NEW `const _v19Checks: [...] = [true, ...]` tuple to
  `packages/api-client/src/schema.contract.test.ts`, immediately after the
  existing `_v18Checks` block (insert around L388 — verify line at plan
  time). Mirror the `_v18Checks` shape verbatim:
  - One named `type _<Name> = AssertNonNever<paths['/api/v1/...']['<method>']>`
    alias per v1.9 path×method, declared above the tuple.
  - The tuple value `[true, true, ..., true]` length === entry count
    (compile-time TS error if any entry resolves to `never`).
  - Naming convention: `_<Resource><Action>` PascalCase, mirroring
    `_ReportsRevenueGet` / `_AuditLogCsvGet` precedent. Examples:
    `_PayrollTrainerConfigPut`, `_PayrollTrainerConfigGet`,
    `_PayrollPreviewGet`, `_PayrollAccrualPost`, `_PayrollAccrualList`,
    `_PayrollAccrualMarkPaidPost`, `_RecurringTemplatePost`,
    `_RecurringTemplateDeactivatePost`, `_RecurringTemplateList`,
    `_TimeOffPost`, `_TimeOffDelete`, `_TimeOffList`,
    `_ReportsTrainersGet`, `_ReportsTrainersCsvGet`.
    Exact casing/spelling is Claude's discretion as long as it stays
    consistent with the file's existing aliases.
- Each guard anchors path + method existence. Anchoring a specific 2xx
  status code (e.g., `['responses']['200']`) is OPTIONAL — `_v18Checks`
  mixes both (path-method only AND status-anchored variants). Default to
  path-method only for terseness; status-anchored variants may be added
  where the planner wants extra brittleness against a 200→201 regression
  (e.g., `_PayrollAccrualPost` should anchor `201` because POST returns 201;
  `_RecurringTemplatePost` returns 201 per `schedule/router.py:280`).

### Count assertion (D-61-04)
- **D-61-04:** Add a NEW `it('compiles against the regenerated v1.9
  trainers surface (Phases 58-60)')` block inside the existing
  `describe('schema.contract', () => { … })` at the bottom of the file
  (current end at L423 — verify at plan time). The block contains a
  single `expect(_v19Checks).toHaveLength(N)` runtime assertion where
  `N` matches the tuple length. **All prior `it(...)` blocks stay
  byte-frozen** (v1.2=10, v1.4=36, v1.5=11, v1.6 users=5 / reset=4 /
  email=2, v1.8=8). This is the additive idiom established at
  `schema.contract.test.ts:389-423` and is the literal "runtime count
  assertion locking the count" wording from ROADMAP Phase 61 SC#2.
- Recommended `N = 14`. The planner re-greps the v1.9 routers at
  codification time to confirm the count; if a v1.9 endpoint was missed
  in this context (e.g., a `GET /payroll/accruals/{id}` reader), the
  tuple grows accordingly and `N` updates in lockstep.

### RBAC three-way parity (D-61-05)
- **D-61-05:** Run `pytest apps/backend/tests/integration/test_rbac_parity.py`
  and assert green. This test asserts
  `apps/backend/app/core/permissions.py` `OWNER_ONLY` frozenset == the
  array in `apps/admin-web/src/shared/session/can.ts` (as a set of
  (action, resource) tuples). Phase 58 INFRA-15 / D-58-15 already
  added the 5 v1.9 pairs to BOTH source-of-truth files in lockstep
  (verified: `permissions.py:136-140` and `can.ts:72-76`); Phases 59 / 60
  added zero new pairs (D-59-08 / D-60-08). The parity test should
  pass without any edits in Phase 61.
- The `Resource` enum membership is asserted by the same parity
  mechanism (the resource string values mirror between
  `permissions.py:33-57` and `registry.ts:8-9`); no Phase 61 edits.
- **If the parity test fails** at planning time, the failure is a Phase
  58/59/60 regression — Phase 61 STOPS and the regression is fixed in
  the originating phase, not papered over here.

### Route introspection (D-61-06)
- **D-61-06:** Run
  `pytest apps/backend/tests/integration/test_route_introspection.py`
  and assert green. This test introspects all FastAPI routes mounted under
  `/api/v1/*` and asserts each protected route declares a permission gate
  (`require_permission` / `require_can` / equivalent). Phase 60 D-60-13
  + Phase 56 introspection-guard precedent: new owner-only routes are
  auto-discovered, no per-route reception-403 duplicate test needed.
- The 8 NEW owner-only routes in v1.9 (PAYROLL × 6 mutations + RECURRING
  × 2 mutations + TIME_OFF × 2 mutations + REPORTS × 2 — note that GETs
  for read-only resources are owner-gated via the `(VIEW, REPORTS)` /
  `(LIST, PAYROLL)` etc. pairs, while reception-retained ones like
  `(LIST, SCHEDULE_SLOTS)` for `GET /recurring-templates` should
  intentionally NOT 403 reception per D-59-08 booking flow) are visible
  in the introspection output. The planner cross-references the
  introspection report against the v1.9 routers to confirm coverage.
- **Reception 403 assertion** for each new owner-only route is satisfied
  by `test_route_introspection.py` + `tests/integration/rbac/test_owner_only.py`
  acting in concert — they enumerate routes and assert reception → 403
  parametrically. No new test files needed.

### Runbook authoring (D-61-07)
- **D-61-07:** Author `.planning/handoff/v1.9-trainers-runbook.md` in the
  `v1.8-reports-runbook.md` sectioned format (the v1.8 runbook is 278
  lines; the v1.9 runbook is comparable in scope — 5 numbered scenarios +
  attestation block). Scenarios (mirror v1.8 D-11 cadence):
  1. **Bring-up** — `docker compose up`, `alembic upgrade head` (head
     should be the Phase 59 / 60 latest revision — planner verifies),
     `python -m scripts.seed_demo_data` or similar bootstrap; readiness
     probe via `GET /healthz`.
  2. **Payroll golden-path** — owner sets a compensation config via
     `PUT /payroll/trainer-configs/{trainer_id}`, previews accrual via
     `GET /payroll/preview`, posts accrual via `POST /payroll/accruals`,
     marks paid via `POST /payroll/accruals/{id}/mark-paid`. Known
     fixture kopecks so the operator can eyeball-match.
  3. **Recurring schedule + time-off golden-path** — owner creates
     a recurring template (`POST /recurring-templates`), lists templates,
     creates a time-off block (`POST /time-off`), lists time-off,
     deactivates template, deletes time-off. Confirm slot generation
     respects time-off windows (REC-04 / TOFF-03 acceptance).
  4. **Trainer-usage report** — owner calls `GET /reports/trainers` with
     a known period (matching the VER fixture seed), eyeball-matches
     `session_count` / `revenue_kopecks` / `total_accrued_kopecks` against
     the seed data; downloads `/reports/trainers.csv`, opens in Excel /
     LibreOffice, confirms Cyrillic trainer names render and BOM is
     intact (no mojibake). This is the live validation of Phase 60
     D-60-11 CSV discipline.
  5. **Reception 403** — operator uses a reception token to hit every
     new v1.9 owner-only route (6 payroll mutations + 2 recurring
     mutations + 2 time-off mutations + 2 reports endpoints = 12 routes)
     and confirms each returns 403. The planner provides the exact
     `curl` examples with the reception token bootstrap (mirror v1.8
     runbook §4).
- The runbook includes an `OPERATOR-PENDING (D-12)` disclaimer block
  matching v1.8 line 256-258 wording, plus an operator attestation
  block (date / executor / outcome) at the bottom.
- File path is LOCKED by ROADMAP Phase 61 SC#4:
  `.planning/handoff/v1.9-trainers-runbook.md` (no other path / no
  directory variant).

### RBAC wording reconciliation (D-61-08)
- **D-61-08:** HND-01 wording in REQUIREMENTS.md L38 reads
  "RBAC three-way parity (`Resource.TRAINER_PAYROLL` + новые OWNER_ONLY
  пары; backend ↔ admin-web `can.ts` ↔ `registry.ts`) зелёный". The
  literal `Resource.TRAINER_PAYROLL` enum name does **not exist** in the
  codebase — Phase 58 INFRA-15 / D-58-15 used the existing
  `Resource.PAYROLL` + `Resource.COMPENSATION` enums (collapsing
  `EDIT, COMPENSATION` into `CREATE, COMPENSATION` because the INSERT-only
  versioned config model makes "edit" semantically identical to
  "create new version"). The HND-01 reference is therefore satisfied by
  the existing `(VIEW, PAYROLL)`, `(VIEW, COMPENSATION)`,
  `(CREATE, COMPENSATION)`, `(CREATE, PAYROLL)`, `(EDIT, PAYROLL)`,
  `(REFUND, PAYROLL)`, `(LIST, PAYROLL)` pairs already in
  `permissions.py:66-67, 136-140` and `can.ts:15-16, 72-76`. **No new
  `Resource.TRAINER_PAYROLL` enum is to be added.** The wording in
  REQUIREMENTS.md may be updated post-merge (out of scope for Phase 61)
  to reflect actual enum names.

### Postman export (D-61-09)
- **D-61-09:** **NO `v1.9-postman.json` is produced.** Only v1.4
  (HANDOFF-04 / D-46-08) produced a Postman v2.1 export
  (`v1.4-postman.json`); v1.5 / v1.6 / v1.7 / v1.8 milestones did not.
  HND-01 does not require Postman; ROADMAP Phase 61 success criteria do
  not require Postman. The OpenAPI spec at `apps/backend/openapi.json` is
  the canonical contract; downstream consumers (planner v1.10, external
  integrators) import it directly or use `openapi-typescript` like
  `packages/api-client` does. The `apps/backend/scripts/export_postman.py`
  helper remains available but is not invoked in Phase 61.

### Test coverage delta (D-61-10)
- **D-61-10:** **Zero new automated VER tests beyond what Phase 58 / 59
  / 60 already shipped.** Per-phase pitfall goldens, RBAC denial
  parametric tests, route introspection, CSV format goldens, and the
  three-way RBAC parity test all exist. Phase 61's job is to:
  1. Run the full `apps/backend/tests/` suite and assert green.
  2. Run `pnpm --filter @sportzal/api-client typecheck` and `test` and
     assert green (the typecheck is the compile-time `_v19Checks`
     enforcement; the test run executes the count assertion `it(...)` block).
  3. Run CI drift gates locally: `git diff --exit-code apps/backend/openapi.json`
     + `git diff --exit-code packages/api-client/src/schema.d.ts` after
     regen + commit.
  4. Verify `lint-imports` is green (no new import-linter ignores landed in
     Phases 58–60 — RPT-04 acceptance criterion, Phase 60 D-60-01).
- The phase MUST NOT introduce new test files. If a coverage gap is
  discovered, the gap is filled in the originating phase via a
  `feat(NN-MM): …` commit, not papered over in Phase 61.

### Commit hygiene (D-61-11)
- **D-61-11:** Recommended commit cadence (mirrors v1.8 Phase 57
  precedent):
  - `chore(61-01): regen openapi.json for v1.9 trainers surface`
    (only if diff exists).
  - `chore(61-02): regen schema.d.ts for v1.9 trainers surface`
    (only if diff exists).
  - `feat(61-03): add _v19Checks forward-guards to schema.contract.test`
    (always; this is the NEW code).
  - `docs(61-04): author v1.9-trainers-runbook.md` (always; the runbook
    is NEW).
  - `docs(61): mark phase 61 complete` (verification commit).
- Plan count is TBD (ROADMAP says `0/TBD`); the planner sets the final
  count. Estimate: 3–4 plans (regen + contract-test + runbook + (optional)
  verification pass). If regen produces no diff, plans collapse to 2–3.

### Operator-pending discipline (D-61-12)
- **D-61-12:** Live execution of the runbook against a real
  `docker compose up` stack is **operator-pending**, mirroring v1.4
  CARRY-01 / VER-03 and v1.8 D-12. The runbook is **authored, committed,
  and considered Phase 61 done** even though the live walkthrough is
  performed by the human operator post-merge. STATE.md is updated at
  phase close with an `OPERATOR-PENDING: v1.9 runbook live walkthrough`
  entry so the v1.10 / v2.0 audit captures it. **Automated tests
  (parity, introspection, contract-test, drift gates, full backend
  suite) MUST be green before phase close** — those are not
  operator-pending.

### Claude's Discretion
- Exact casing / wording of the 14 `_v19Checks` type-alias names (within
  the project's PascalCase-with-underscore-prefix convention).
- Whether to anchor every guard to a specific 2xx status code or only
  to path × method (recommended: status-anchor only POST/PUT/DELETE
  where a 200→201 / 204 regression would matter; path-method only for
  GETs).
- Exact wording of the runbook scenario titles / `curl` examples (within
  the v1.8 sectioned format).
- Final plan count (2–4 depending on whether regen produces a diff).
- Whether the v1.9 runbook adds a §6 "Audit log read-back" sanity check
  (NOT required; v1.8 runbook covers audit-log surface, and v1.9 adds
  zero new audit events per D-60-10). Recommended: SKIP §6 to keep the
  runbook focused on v1.9-specific surface.
- Whether the `chore(61-01)` / `chore(61-02)` regen commits exist
  depends on whether any diff is produced — if both artifacts were kept
  in lockstep during Phases 58/59/60 shipping (and the most-recent
  Phase 60 verification suggests they were), the regen is a no-op and
  those commits are omitted.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (source of truth on scope — these WIN over precedent)
- `.planning/REQUIREMENTS.md` §"HND-01" (L38) — verbatim handoff
  requirement: byte-stable regen of `openapi.json` + `schema.d.ts` with
  all v1.9 paths, `_v19Checks` `AssertNonNever` forward-guards, three-way
  RBAC parity green at the milestone gate, milestone verification.
- `.planning/ROADMAP.md` §"Phase 61: OpenAPI Handoff + Milestone
  Verification" (L236-247) — goal + success criteria 1..4 (byte-stable
  regen + CI drift gates; `_v19Checks` forward-guards with
  `toHaveLength(N)`; three-way RBAC parity + reception 403 via route
  introspection; operator runbook at
  `.planning/handoff/v1.9-trainers-runbook.md`).
- `.planning/PROJECT.md` — v1.9 milestone goal (Trainers Complete;
  admin-web frozen; payroll + recurring schedule + trainer report
  modules complete; v1.10+ owns FE integration).
- `.planning/STATE.md` §"D-58-15" / §"D-58-21" / §"D-59-*" / §"D-60-*"
  — LOCKED v1.9 RBAC / attribution / read-only-report decisions that
  must NOT be re-litigated in this phase.

### Milestone-close precedent (THIS phase mirrors v1.8 Phase 57 verbatim)
- `.planning/milestones/v1.8-phases/57-openapi-handoff-milestone-verification/57-CONTEXT.md`
  — the closest analog. D-01..D-12 are the template for D-61-01..D-61-12.
- `.planning/milestones/v1.8-phases/57-openapi-handoff-milestone-verification/`
  (entire dir) — PLAN.md / VERIFICATION.md / SUMMARY.md from v1.8 are
  the planner's reference for plan shape and verification cadence.
- `.planning/handoff/v1.8-reports-runbook.md` — **runbook format
  template** for `v1.9-trainers-runbook.md` (sectioned scenarios + curl
  + attestation block + `OPERATOR-PENDING (D-12)` disclaimer).
- `.planning/handoff/v1.4-auth-runbook.md` — alternate runbook format
  (older sectioned style); v1.8 cadence supersedes.

### OpenAPI handoff machinery (REUSE verbatim — NO edits)
- `apps/backend/scripts/export_openapi.py` — byte-stable exporter.
  Lifespan-safe (`create_app().openapi()` never enters
  `combined_lifespan`); env backfill via `setdefault` for DB / Redis /
  SECRET_KEY (`:31-42`); `json.dumps(..., indent=2, sort_keys=True,
  ensure_ascii=False) + "\n"` (`:60`). **NO edits.**
- `packages/api-client/package.json` §16 — `codegen` script
  `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`.
- `packages/api-client/package.json` §22 — `openapi-typescript` pinned
  at `^7.13.0`. **NO version bump.**
- `packages/api-client/src/schema.contract.test.ts` — current shape
  (L15 `AssertNonNever<T>`; L378-387 `_v18Checks` 8-entry tuple;
  L389-423 `describe('schema.contract')` with per-surface `it(...)`
  blocks v1.2=10 / v1.4=36 / v1.5=11 / v1.6 users=5 / reset=4 / email=2
  / v1.8=8). NEW `_v19Checks` + new `it(...)` block extend this file.
- `apps/backend/scripts/export_postman.py` — Postman exporter, available
  but NOT invoked in Phase 61 (D-61-09).
- `.github/workflows/ci.yml` §50-64 (backend `export_openapi` + drift
  gate `git ls-files --error-unmatch apps/backend/openapi.json` +
  `git diff --exit-code apps/backend/openapi.json`) — the gates that
  must stay green.
- `.github/workflows/ci.yml` §105-117 (frontend `codegen` + drift gate
  on `packages/api-client/src/schema.d.ts`) — same gate, frontend side.

### RBAC verification (RUN; NO edits expected)
- `apps/backend/app/core/permissions.py` §33-57 (Resource enum), §62-141
  (OWNER_ONLY frozenset). Lines 136-140 are the v1.9 pairs already
  shipped by Phase 58 INFRA-15 / D-58-15. **NO edits.**
- `apps/admin-web/src/shared/session/can.ts` §15-16, §72-76 — v1.9
  pairs mirror, already shipped Phase 58. **NO edits.**
- `apps/admin-web/src/shared/session/registry.ts` §8-9 — `payroll` /
  `compensation` resource entries. **NO edits.**
- `apps/backend/tests/integration/test_rbac_parity.py` — TEST-06
  parity assertion (backend `OWNER_ONLY` frozenset == frontend
  `can.ts` array). Phase 61 RUNS this; expected green.
- `apps/backend/tests/integration/test_route_introspection.py` —
  introspection gate: every protected route declares a permission
  dependency. Phase 61 RUNS this; expected green for all v1.9 routes.
- `apps/backend/tests/integration/rbac/test_owner_only.py` —
  parametric reception → 403 assertion across all OWNER_ONLY routes.
  Phase 61 RUNS this; expected green.

### v1.9 routers (source of truth for path enumeration)
- `apps/backend/app/api/v1/router.py` §58 (`/payroll`), §72-77
  (`/recurring-templates`, `/time-off`), §91 (`/reports`) — the prefix
  mounts for all v1.9 surface.
- `apps/backend/app/modules/payroll/router.py` §78 PUT
  `/trainer-configs/{trainer_id}`, §102 GET
  `/trainer-configs/{trainer_id}`, §128 GET `/preview`, §168 GET
  `/accruals`, §217 POST `/accruals`, §256 POST
  `/accruals/{accrual_id}/mark-paid`.
- `apps/backend/app/modules/schedule/router.py` §277 POST
  (recurring root), §351 POST
  `/{template_id}/deactivate`, §421 GET (recurring root), §454 POST
  (time-off root), §574 DELETE `/{time_off_id}`, §629 GET (time-off
  root).
- `apps/backend/app/modules/reports/router.py` §218 GET `/trainers`,
  §254 GET `/trainers.csv`.

### Prior phase context (read for v1.9 decision continuity)
- `.planning/phases/58-payroll-foundations-ledger/58-CONTEXT.md`
  §"D-58-15" (RBAC), §"D-58-21" (attribution), L103 (HND deferral to
  Phase 61), §"Canonical refs" L405-406 (explicit pointer to Phase 57
  v1.8 milestone-close template).
- `.planning/phases/59-recurring-schedule-time-off/59-CONTEXT.md`
  §"D-59-08" (admin-web frozen / RBAC reuse), L58 (HND deferral).
- `.planning/phases/60-trainer-usage-report/60-CONTEXT.md`
  §"D-60-08" (RBAC reuse), §"D-60-10" (zero new audit events),
  §"D-60-11" (CSV discipline — informs runbook §4 Excel-open check).

### Phase 60 verification (proof v1.9 surface is shippable)
- `.planning/phases/60-trainer-usage-report/60-VERIFICATION.md` — the
  v1.9 final-feature-phase verification report. Phase 61 starts from
  this green-state baseline.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`apps/backend/scripts/export_openapi.py`** — byte-stable OpenAPI
  exporter, lifespan-safe, env-backfill-safe; reuse verbatim
  (`uv run python -m scripts.export_openapi`).
- **`pnpm --filter @sportzal/api-client codegen`** — the
  `openapi-typescript` invocation that regenerates `schema.d.ts` from
  `apps/backend/openapi.json`; reuse verbatim.
- **`packages/api-client/src/schema.contract.test.ts:15` `AssertNonNever<T>`**
  — the compile-time guard idiom for `_v19Checks`. Already exists; no
  new type machinery needed.
- **`schema.contract.test.ts:378-387` `_v18Checks` tuple** — exact
  shape to mirror for `_v19Checks` (one alias per guard, named PascalCase,
  tuple value `[true, true, ..., true]`).
- **`schema.contract.test.ts:420-422` v1.8 `it(...)` block** — exact
  shape for the v1.9 count-assertion block.
- **`test_rbac_parity.py`** — already enforces backend ↔ admin-web
  parity; no edits needed (Phase 58 already locked the v1.9 pairs in
  both sides).
- **`test_route_introspection.py`** — auto-discovers all v1.9 routes
  and asserts permission gates; no per-endpoint duplication needed.
- **`v1.8-reports-runbook.md`** — the sectioned-format template for
  `v1.9-trainers-runbook.md`. Copy structure verbatim, substitute v1.9
  scenarios.
- **`.github/workflows/ci.yml` drift gates** — already enforce both
  `openapi.json` and `schema.d.ts` byte-stability; no CI edits needed.

### Established Patterns
- **Per-milestone `_vNNChecks` tuple + per-surface `it(...)` block** —
  established v1.2 / v1.4 / v1.5 / v1.6 / v1.8; v1.9 follows the same
  additive idiom (NEVER mutate prior blocks; prior counts stay byte-frozen).
- **Byte-stable regen** — `json.dumps(..., indent=2, sort_keys=True,
  ensure_ascii=False) + "\n"` produces identical bytes on macOS / Linux;
  `git diff --exit-code` is the CI gate (Phase 9 D-06, verified across 6
  milestones).
- **Operator-pending milestone runbooks** — every milestone since v1.4
  ships a runbook that is authored by Claude and executed live by the
  operator (v1.4 CARRY-01, v1.5 DEFER-40-01, v1.7 evidence directories,
  v1.8 D-12). v1.9 follows the same pattern (D-61-12).
- **Admin-web frozen in v1.9** — D-58-22 / D-59-08 / D-60-08 all
  established that v1.9 backend ships without any admin-web edits;
  v1.10+ owns the FE integration. Phase 61 inherits this constraint.
- **`chore(NN-MM)` for regen commits; `feat(NN-MM)` for new code;
  `docs(NN-MM)` for runbook** — commit-prefix convention from Phase 57.
- **Zero new import-linter ignores per milestone** — RPT-04 acceptance
  / D-60-01; Phase 61 inherits and verifies via `lint-imports` in CI.

### Integration Points
- `apps/backend/openapi.json` — the canonical contract artifact; consumed
  by `packages/api-client` codegen and (post-merge) by v1.10+ admin-web
  surface integration.
- `packages/api-client/src/schema.d.ts` — the typed transport layer;
  consumed by `apps/admin-web` (currently does NOT import v1.9 types per
  D-58-22 freeze, but the types are now compile-time available for v1.10).
- `apps/backend/tests/integration/` — full backend test suite must be
  green at phase close (D-61-10).
- `packages/api-client/vitest.config.ts` + `tsconfig.json` — the
  typecheck + vitest commands enforce `_v19Checks` at compile time and
  run the count assertion at runtime.

</code_context>

<specifics>
## Specific Ideas

- **`_v19Checks` count is 14** per the router enumeration in `<domain>`.
  Confirmed by grep against `apps/backend/app/modules/{payroll,schedule,reports}/router.py`
  during context gathering. If a path was missed (e.g., a `GET /payroll/accruals/{id}`
  reader for one specific accrual), the planner re-greps and adjusts the count
  before committing — the SHAPE is locked, not the literal number.
- **Naming convention for the 14 type aliases** mirrors `_ReportsRevenueGet` /
  `_AuditLogCsvGet` precedent: `_<ResourceArea><Action>` PascalCase,
  underscore prefix. The exact spelling for each is in D-61-03's example list.
- **Status anchoring per guard:** POST/PUT/DELETE routes that return non-200
  (POST returns 201 per `schedule/router.py:280` / `payroll/router.py:217`;
  DELETE may return 204 per FastAPI default) should anchor that status in the
  type derivation to catch a future status-code regression. GETs default to
  unanchored (path × method only).
- **`v1.9-trainers-runbook.md` is ~5 scenarios + attestation block**, comparable
  in scope to v1.8's 278-line runbook. The Phase 61 runbook may be ~200-300
  lines depending on how detailed each `curl` example is. The operator-pending
  disclaimer is the line-256-258 v1.8 template, slightly reworded for v1.9.
- **No `v1.9-postman.json`** — explicit anti-feature per D-61-09. Only v1.4
  shipped Postman; the precedent has been "skip Postman" since v1.5.
- **The `chore(61-NN): regen ...` commits exist only if a diff is produced.**
  Phase 58 / 59 / 60 may have already kept the artifacts in lockstep (as v1.8
  Phase 57 D-03 explicitly observed for the v1.8 surface). The planner verifies
  this at codification time and adjusts plan count accordingly (3 vs 4 plans).
- **The HND-01 wording `Resource.TRAINER_PAYROLL`** is a known wording slip in
  REQUIREMENTS.md (D-61-08). The literal enum is `Resource.PAYROLL` +
  `Resource.COMPENSATION`. Phase 61 does NOT add a `TRAINER_PAYROLL` enum
  variant — the parity / OWNER_ONLY coverage is already complete via the
  existing enums.

</specifics>

<deferred>
## Deferred Ideas

- **`apps/admin-web` UI for v1.9 surface** (payroll panels, recurring
  template editor, time-off blocks, trainer-usage report viewer + CSV
  download buttons) — admin-web frozen in v1.9 per D-58-22 / D-59-08 /
  D-60-08; v1.10+ owns the FE integration.
- **`v1.9-postman.json` Postman v2.1 export** — not required by HND-01;
  v1.5 / v1.6 / v1.7 / v1.8 milestones did not ship Postman. v2.0 may
  reintroduce Postman if external-integrator demand emerges.
- **Live operator execution of `v1.9-trainers-runbook.md`** — authored
  in Phase 61, executed by the operator post-merge per the
  CARRY/DEFER pattern. STATE.md captures this as `OPERATOR-PENDING`.
- **Tech-debt sweep (DEFER-46-04 ruff/format/mypy, DEFER-40-01 v1.5
  runbook)** — already deferred to v1.10 per REQUIREMENTS.md L75. NOT
  in Phase 61 scope.
- **REQUIREMENTS.md wording fix** — the HND-01 mention of
  `Resource.TRAINER_PAYROLL` (literal enum does not exist) may be
  updated post-merge to reflect the actual `Resource.PAYROLL` +
  `Resource.COMPENSATION` enums. NOT a Phase 61 deliverable
  (REQUIREMENTS.md edits are milestone-close housekeeping, not phase
  work).
- **1C / external payroll export, iCal sync, real-time FE dashboards,
  predictive analytics, per-client breakdown in trainer report** —
  research anti-features (Phase 60 deferred list); v1.10+ / v2.0.
- **Russian-Excel comma-decimal CSV dialect** — only triggered if the
  Phase 61 runbook §4 Excel-open check fails. Currently expected to
  pass via UTF-8 BOM + RFC-4180 dialect (Phase 56 D-13 / Phase 60
  D-60-11).
- **New `Resource.TRAINER_PAYROLL` enum entry** — D-61-08 establishes
  this is unnecessary; existing `Resource.PAYROLL` + `Resource.COMPENSATION`
  cover the surface. No future phase is expected to add it.
- **Additional automated VER tests** — Phases 58 / 59 / 60 already
  cover the v1.9 surface end-to-end with per-pitfall goldens; no
  v1.10 follow-up expected unless a new failure mode surfaces.

None of the above are scope creep into Phase 61.

</deferred>

---

*Phase: 61-openapi-handoff-milestone-verification*
*Context gathered: 2026-05-26*
