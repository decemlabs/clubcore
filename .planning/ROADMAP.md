# Roadmap: clubcore

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (shipped 2026-05-24) — see [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
- ✅ **v1.8 Reports + Audit Log read API** — Phases 54-57 (shipped 2026-05-24) — see [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 Trainers Complete** — Phases 58-61 (shipped 2026-05-26) — see [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)
- ✅ **v1.10 clubcore Rebrand** — Phases 62 + 62.1 (shipped 2026-05-26) — see [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md)
- 🔜 **v1.11 API Handoff + Production Hardening** — Phases 63-67 (in planning)

## Phases

<details>
<summary>✅ v1.0 — v1.10 SHIPPED (Phases 1-62.1)</summary>

All shipped milestones detailed in per-milestone ROADMAP archives above.

</details>

### v1.11 API Handoff + Production Hardening (Phases 63-67)

**EXECUTION ORDER: 63 → 64 → 66 → 65 → 67**

Note: Phase numbers are sequential (63-67) but execution order is non-monotonic. Phase 65 (Handoff Artifacts) executes AFTER Phase 66 (Idempotency Hardening) because the Postman collection, Newman smoke harness, and auth runbook must reflect the `components.parameters.IdempotencyKey` reusable parameter and the 7 additional `Depends(verify_idempotency)` wired endpoints added in Phase 66.

- [x] **Phase 63: Tech-Debt Sweep** — CI tree cleaned: ruff format + ruff safe-fix + mypy strict all exit 0; v1.5 run.sh hardened; all 6 backend CI gates green on swept tree (DEBT-01..05) (completed 2026-05-26)
- [x] **Phase 64: Contract Freeze — OpenAPI Curation** — Curated OpenAPI spec under clubcore name: correct `info.*`, `servers`, `securitySchemes`, explicit operation IDs, tags for 10 domains, shared `components.responses`; Redocly lint added as 7th CI gate; baseline tag committed (FRZ-01..08) (completed 2026-05-28)
- [x] **Phase 66: Idempotency Hardening** *(executes before Phase 65)* — `verify_idempotency` user-scoped (security fix); 86400s TTL; all category-A endpoints covered; `components.parameters.IdempotencyKey` in spec; double-submit integration tests pass (IDM-01..07) (completed 2026-05-29)
- [ ] **Phase 65: Handoff Artifacts** *(executes after Phase 66)* — Postman v2.1 collection + Newman smoke harness + `clubcore-auth-runbook.md` + private Redocly doc-site delivered as a complete handoff package from the post-Phase-66 frozen spec (HND-01..06)
- [ ] **Phase 67: Operator-Pending Runbook Execution** — All 4 accumulated operator-pending walkthroughs executed with captured evidence; Mailpit `--profile dev` service in docker-compose; evidence file populated (RUN-00..07)

## Phase Details

### Phase 63: Tech-Debt Sweep

**Goal**: All pre-existing CI tech-debt erased; `ruff check`, `ruff format --check`, and `mypy --strict app` exit 0 tree-wide; v1.5 runbook tooling is executable without manual patching
**Depends on**: Phase 62.1 (v1.10 rebrand complete + shims removed) — sweep operates on the clean clubcore tree
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, DEBT-05
**Success Criteria** (what must be TRUE):

  1. `uv run ruff format --check` exits 0 with zero files flagged; format commit is the sole change in its commit (no logic mixed in)
  2. `uv run ruff check` exits 0 with zero errors; safe-fix commit is separate from the format commit; no `--unsafe-fixes` used
  3. `uv run mypy --strict app` exits 0 (11 errors → 0); `auth/models.py __all__` fix + Literal narrowing fixes land in a third separate commit
  4. `v1.5-verification-evidence/run.sh` executes against `docker compose up` without the 4+2 known hotfixes (Alembic 32-char limit, `/healthz`, `trainer_availability_slots`, fixture user defaults, RBAC actor, X-CSRF-Token header); revision log updated
  5. Full backend CI (all 6 gates: ruff + ruff format + mypy + import-linter + openapi drift + export_openapi) exits 0; no new `# type: ignore`, `# noqa`, or `ignore_imports` introduced

**Plans**: 5 plans

Plans:

- [x] 63-01-PLAN.md — DEBT-01 ruff format tree-wide (~297 files, single atomic commit)
- [x] 63-02-PLAN.md — DEBT-02 ruff check --fix safe-only (158 → 0; no --unsafe-fixes)
- [x] 63-03-PLAN.md — DEBT-03 mypy strict cleanup (11 → 0) + auth/models.py __all__ fix + tests.* mypy override
- [x] 63-04-PLAN.md — DEBT-04 v1.5/run.sh hardening (4 hotfixes + RBAC actor + X-CSRF-Token header)
- [x] 63-05-PLAN.md — DEBT-05 verify all 6 backend CI gates exit 0; capture GitHub Actions CI run URL post-merge

### Phase 64: Contract Freeze — OpenAPI Curation

**Goal**: The `openapi.json` spec is the authoritative, curated single source of truth under the clubcore name — correct metadata, stable operation IDs, explicit tags for all 10 domains, shared error responses, and a passing Redocly lint gate in CI
**Depends on**: Phase 63 (clean CI tree required for byte-stable regen; drift gate must be green before any spec-touching PR lands)
**Requirements**: FRZ-01, FRZ-02, FRZ-03, FRZ-04, FRZ-05, FRZ-06, FRZ-07, FRZ-08
**Success Criteria** (what must be TRUE):

  1. `openapi.json` `info.title` is `"clubcore API"`, `info.version` is `"1.11.0"`, `info.description` is populated; `servers[]` includes the localhost:8000 dev entry; regen is byte-stable and drift gate green — all in one atomic commit
  2. All 102+ operation IDs follow the cleaned format (no `_api_v1_{method}` suffix); `schema.d.ts` compiles clean against all existing `_v18Checks`, `_v19Checks` AssertNonNever guards; admin-web typecheck exits 0
  3. Every router declares explicit `tags=[...]`; `openapi_tags` list in `app/main.py` orders all 10 business domains; `npx @redocly/cli preview-docs` groups operations under expected tag headings without stray "default" folder
  4. `securitySchemes` (cookieAuth + csrfHeader) and `components.responses` (401/403/404/409/422/429 envelopes) are present in the spec; `sportzal_csrf` cookie name documented as v2.0 carry-over per D-11-CSRF-DEFER
  5. `npx @redocly/cli lint openapi.json` exits 0; the Redocly lint step is live in `.github/workflows/ci.yml` as the 7th parallel gate; `contract-freeze-v1.11.0` baseline tag committed; `CHANGELOG.md` entry in `packages/api-client/` records the freeze

**Plans**: 7 plans

Plans:
**Wave 1**

- [x] 64-01-PLAN.md — FRZ-01 + FRZ-04 (info{} + servers[] + description; byte-stable regen)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 64-02-PLAN.md — FRZ-02 (generate_unique_id_function suffix-strip + collision audit + schema.d.ts regen)
- [x] 64-03-PLAN.md — FRZ-03 (explicit per-router tags + openapi_tags 12-domain ordering + aggregator-tag dedup + Users 11th tag)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 64-04-PLAN.md — FRZ-05 (securitySchemes cookieAuth + csrfHeader + per-route PUBLIC_ENDPOINT_OPERATION_IDS opt-out)
- [x] 64-05-PLAN.md — FRZ-06 (shared components.responses + $ref migration post-processor)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 64-06-PLAN.md — FRZ-07 (redocly.yaml + 7th CI gate redocly-lint parallel job)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 64-07-PLAN.md — FRZ-08 (CHANGELOG.md + REQUIREMENTS.md path-fix + annotated baseline tag contract-freeze-v1.11.0)

**Cross-cutting constraints:**

- Regen byte-stable; drift gate green

### Phase 65: Handoff Artifacts

**Goal**: The v2.0 frontend integration team receives a complete, usable handoff package — a Postman v2.1 collection with auth scripts and test assertions, a Newman smoke harness, an `clubcore-auth-runbook.md` covering all auth flows and `Idempotency-Key` semantics, and a private local doc-site — all generated from the post-Phase-66 frozen spec
**Depends on**: Phase 66 (Idempotency Hardening) — Postman collection and auth runbook must reflect `components.parameters.IdempotencyKey` and the 7 newly-wired `Depends(verify_idempotency)` endpoints; Phase 64 must also be complete so the spec has correct tags and operation IDs for `folderStrategy=Tags`
**Requirements**: HND-01, HND-02, HND-03, HND-04, HND-05, HND-06
**Success Criteria** (what must be TRUE):

  1. `.planning/handoff/v1.11-clubcore.postman_collection.json` exists and validates against the Postman v2.1 schema; collection is grouped under the 10 domain folders (Tags strategy); environment file ships placeholder values only — no real credentials committed
  2. Login request in the collection extracts `cc_access`, `cc_refresh`, `sportzal_csrf` cookies and stores them as collection variables; subsequent mutating requests automatically send `X-CSRF-Token` header from the stored value; running the auth flow in Postman GUI succeeds without manual header wiring
  3. Every collection request has at minimum a `pm.response.to.have.status(...)` assertion; auth happy-path and one representative request per business domain additionally assert response body shape via `pm.test()`; Newman `run` with `--bail` exits 0 against `docker compose up`
  4. `tools/newman/` directory contains the smoke script and env JSON; running `pnpm newman run` (or documented equivalent) exits non-zero on any endpoint failure; the script is documented in `clubcore-auth-runbook.md` as "local handoff smoke — not a CI gate"
  5. `clubcore-auth-runbook.md` at `.planning/handoff/clubcore-auth-runbook.md` covers: email/password + Telegram OTP + email OTP + refresh-rotation + CSRF retrieval; `sportzal_csrf` cookie documented as known carry-over with v2.0 cutover plan; Phase 66 `Idempotency-Key` semantics + 24h replay window documented with curl examples
  6. `pnpm docs` (or `make docs`) runs `npx @redocly/cli preview-docs openapi.json` on port 8080; `.docs-site/` output dir is gitignored; doc-site is confirmed private per D-11-DOCS-PRIVATE (no public publish path)

**Plans**: 4 plans
- [ ] 65-01-PLAN.md — Private repo-root package.json tooling scaffold + private doc-site (HND-06)
- [ ] 65-02-PLAN.md — Postman collection generation + augmentation: auth/CSRF wiring + assertions (HND-01/02/03)
- [ ] 65-03-PLAN.md — Newman smoke harness (curated happy-path subset, runtime-credential discipline) (HND-04)
- [ ] 65-04-PLAN.md — clubcore-auth-runbook.md: all auth flows + Idempotency-Key semantics (HND-05)
**UI hint**: no

### Phase 66: Idempotency Hardening

**Goal**: All mutating endpoints are classified, the cross-user replay security gap is closed, TTL is aligned with the 24h webhook dedup discipline, and `components.parameters.IdempotencyKey` is in the frozen spec with double-submit integration tests proving the hardened behavior
**Depends on**: Phase 64 (frozen spec with correct operation IDs required; `IDEMPOTENCY_OPERATION_IDS` frozenset uses Phase 64 operation ID strings; spec regen at Phase 66 end must include Phase 64 curation)
**Requirements**: IDM-01, IDM-02, IDM-03, IDM-04, IDM-05, IDM-06, IDM-07
**Success Criteria** (what must be TRUE):

  1. `.planning/handoff/v1.11-idempotency-audit.md` committed — every POST/PATCH/PUT/DELETE endpoint classified A (enforce), B (exempt), or C (inconsistent→A); audit table is the authoritative record for IDM-07 wiring
  2. **Security fix (IDM-05):** `verify_idempotency` Redis key includes `user.id` (`cc:idem:{user_id}:{method}:{path}:{key}`); submitting the same `Idempotency-Key` header value from two different user sessions creates two distinct Redis entries (proven by integration test); existing 3 callsites remain green
  3. `IDEMPOTENCY_TTL_SECONDS = 86400` in `app/core/idempotency.py`; request-body hash mismatch on same key returns 422 (not silent 200); in-flight placeholder is deleted on unknown exception so retries are not stuck for 24h (IDM-02 + IDM-06)
  4. Integration tests for double-submit on at minimum 3 financial endpoints (memberships sell, PT-package sell, online-payment create) pass: replay returns cached response body+status without re-emitting audit events (IDM-03)
  5. `components.parameters.IdempotencyKey` reusable parameter exists in `openapi.json`; every category-A endpoint references it via `$ref`; ЮKassa webhook endpoint has a code comment annotating the separate `cc:yk:webhook:*` dedup path (IDM-04 + IDM-07); `openapi.json` + `schema.d.ts` regen byte-stable, drift gate green

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 66-01-PLAN.md — IDM-01 (endpoint classification audit doc -> `.planning/handoff/v1.11-idempotency-audit.md`; authoritative category-A set)

**Wave 2** *(blocked on Wave 1)*

- [x] 66-02-PLAN.md — IDM-02 + IDM-05 + IDM-06 (core idempotency.py: TTL 86400, pattern {16,128}, user-scoped key, exception-aware shared orchestrator; refactor 11 existing wired callsites onto it)

**Wave 3** *(blocked on Wave 2)*

- [x] 66-03-PLAN.md — IDM-07 (wire verify_idempotency + orchestrator into membership freeze/unfreeze/renew/cancel + refunds per audit; ЮKassa webhook exclusion comment)

**Wave 4** *(blocked on Wave 1 + Wave 3)*

- [x] 66-04-PLAN.md — IDM-04 (components.parameters.IdempotencyKey + $ref injection via _customize_openapi post-processor + CATEGORY_A_OPERATION_IDS frozenset; byte-stable regen + drift gate)

**Wave 5** *(blocked on Wave 2 + Wave 3)*

- [x] 66-05-PLAN.md — IDM-03 + IDM-06 (double-submit integration tests across memberships/online_payments/pt_packages/pt_sessions/bookings: byte-identical replay, no-re-emit-audit, cross-user separation, AppError-replay, rollback-retry)

**Cross-cutting constraints:**

- Every plan leaves the full backend CI tree green at HEAD (ruff + ruff format + mypy strict + import-linter + openapi drift + Redocly lint).
- IDM-02 <-> IDM-04 lockstep: the {16,128} pattern is sourced from the single imported `IDEMPOTENCY_KEY_PATTERN` constant (validation + spec parameter cannot diverge).
- `apps/admin-web` frozen; only mechanical `packages/api-client/src/schema.d.ts` codegen drift (66-04) is permitted.

### Phase 67: Operator-Pending Runbook Execution

**Goal**: Every accumulated operator-pending walkthrough is executed with captured evidence; Mailpit `--profile dev` service added for future dev use; `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` is the complete evidence record; v1.11 milestone closes with zero operator-pending tail
**Depends on**: Phase 65 (auth runbook and Newman smoke ready for walkthrough use), Phase 63 (v1.5 run.sh hardened), Phase 66 (idempotency semantics fully documented); all backend-engineering phases complete
**Requirements**: RUN-00, RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, RUN-07
**Success Criteria** (what must be TRUE):

  1. Staleness audit (RUN-00) complete before any live walkthrough: each of the 4 runbooks has been grepped for `sz:`, `SPORTZAL_EMAIL_FROM`, stale endpoint paths; known-stale identifiers documented with inline fixes or evidence-file workaround notes
  2. v1.7 VER-03 (ЮKassa sandbox) walkthrough executed with `YOOKASSA_SANDBOX=true` confirmed as first evidence line; curl transcripts + Telegram/email DM evidence captured per scenario with PASS/FAIL recorded
  3. v1.8 VER-01 (reports live runbook) and v1.9 D-61-12 (trainers runbook) executed against `docker compose up`; CSV export samples and Cyrillic-encoding checks captured; evidence rows appended to `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md`
  4. v1.7 CARRY-01 (RU email deliverability) and CARRY-02 (19-template owner countersign) resolved — either PASS with evidence or `N/A-until-production` row with documented trigger condition (matches v1.10 RUN-08-dns-dkim-DEFERRED precedent)
  5. Mailpit service added to `apps/backend/docker-compose.yml` under `profiles: ["dev"]` (ports 1025/8025); `docker compose --profile dev up` starts mailpit alongside other services; documented in runbook as dev-only SMTP trap with note that current SES-V2 path is not intercepted

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-3. Phase A: Skeleton | v1.0 | 17/17 | Complete | 2026-05-01 |
| 4-14. Auth + Clients | v1.1 | 63/63 | Complete | 2026-05-07 |
| 15-23. Memberships + Visits | v1.2 | — | Complete | 2026-05-08 |
| 24-29. Memberships Extras + Tech-Debt | v1.3 | — | Complete | 2026-05-14 |
| 30-36. Cash Sales + PT Packages | v1.4 | — | Complete | 2026-05-16 |
| 37-40. Schedule + Bookings | v1.5 | 20/20 | Complete | 2026-05-18 |
| 41-46. Email + Multi-user admin | v1.6 | 82/82 | Complete | 2026-05-21 |
| 47-53. Online Payments + 54-ФЗ | v1.7 | 47/47 | Complete | 2026-05-24 |
| 54-57. Reports + Audit Log read API | v1.8 | 10/10 | Complete | 2026-05-24 |
| 58-61. Trainers Complete | v1.9 | 22/22 | Complete | 2026-05-26 |
| 62. clubcore Rebrand | v1.10 | 7/7 | Complete | 2026-05-26 |
| 62.1. Finalize sportzal → clubcore rename | v1.10 | 9/9 | Complete | 2026-05-26 |
| 63. Tech-Debt Sweep | v1.11 | 5/5 | Complete    | 2026-05-26 |
| 64. Contract Freeze — OpenAPI Curation | v1.11 | 7/7 | Complete    | 2026-05-28 |
| 66. Idempotency Hardening | v1.11 | 5/5 | Complete    | 2026-05-29 |
| 65. Handoff Artifacts | v1.11 | 0/TBD | Not started | — |
| 67. Operator-Pending Runbook Execution | v1.11 | 0/TBD | Not started | — |

---

*Roadmap last updated: 2026-05-26 — Phase 63 plans created (5 plans = 5 atomic commits per D-63-01; serial execution per D-63-02). v1.11 API Handoff + Production Hardening roadmap (34/34 requirements mapped; 5 phases 63-67; execution order 63 → 64 → 66 → 65 → 67 locked per SUMMARY.md + ARCHITECTURE.md + 4 milestone-opening decisions).*
*v1.11 Coverage: 34/34 requirements mapped (DEBT:5 → Phase 63, FRZ:8 → Phase 64, IDM:7 → Phase 66, HND:6 → Phase 65, RUN:8 → Phase 67) — zero orphans, zero duplicates.*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (BACKLOG)

**Goal:** Restore `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking — in both code paths: `POST /time-off?force=true` (Phase 59, `schedule/service.py:925`) and `cancel_slot` booked-cascade (`schedule/service.py:~471-504`). Closes the pre-v1.9 WR-06 documented limitation.

**Product decision (locked 2026-05-26):** Option B — always restore on owner-initiated cancellation. Rationale: client must never lose a prepaid PT session due to gym-side cancellation (industry norm; alternative leaks support burden and invites disputes).

**Requirements:** TBD (target ~3 reqs: restore-on-time-off-force, restore-on-cancel-slot-cascade, audit-event emission)

**Plans:** 0 plans

Plans:

- [ ] TBD — cross-module raw `sa.text()` UPDATE on `pt_packages.sessions_remaining` (pattern D-38-11), same UoW as booking cascade, in both schedule paths
- [ ] TBD — register `pt_session_credit_restored` in `LOCKED_AUDIT_EVENTS` with payload `{client_id, pt_package_id, booking_id, cancel_reason, sessions_remaining_before/after}`
- [ ] TBD — regression tests pinning new behavior in `tests/integration/schedule/test_time_off.py::test_create_time_off_force_cascades_booking_and_dispatches_dm` + equivalent for `cancel_slot` cascade
- [ ] TBD — remove `NOTE WR-06` block at `schedule/service.py:937` once behavior is fixed

**Source:** Phase 59 UAT WR-06 pending item; product decision recorded in this conversation 2026-05-26. Promote with `/gsd:review-backlog` when v1.11 milestone opens.
