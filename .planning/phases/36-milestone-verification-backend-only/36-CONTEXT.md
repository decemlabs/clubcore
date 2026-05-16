# Phase 36: Milestone Verification (backend-only) — Context

**Gathered:** 2026-05-16
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 36 --auto` — single pass; recommended defaults selected for every gray area; full audit trail in `36-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

Phase 36 is the **gate** that closes v1.4 — it proves the backend-only milestone is shippable by exercising the cumulative surface that Phases 30-35 built (audit/RBAC/architectural bedrock, trainers module, payment ledger + refund, PT-package plans + instances, PT-session recording, OpenAPI handoff) against a live `docker compose up` stack via curl/Postman/httpie + green race-condition Postgres integration tests + green backend CI gates + operator sign-off. It is the v1.3 Phase 29 discipline replayed for the backend-only era — admin-web smoke is downgraded to informational canary because `apps/admin-web` is now frozen-as-of-v1.3 mock-reference (production frontends ship in v2.0 from the external design team per the 2026-05-15 pivot).

Mechanically Phase 36 delivers:

- **7+ operator API-contract scenarios executed via curl/jq scripts** against a live `docker compose up` stack (NOT through admin-web UI) covering: (1) sale-with-payment golden path; (2) refund of fresh sale; (3) refund attempt on frozen membership → 409 `must_unfreeze_first`; (4) PT-package sale; (5) PT-session recording with active trainer; (6) PT-package exhaustion mid-session-flow; (7) trainer deactivation + 409 on attempt to record session with inactive trainer; (8) cross-phase smoke "sell membership → freeze → refund-attempt-rejected → unfreeze → refund-succeeds". Verbatim HTTP request/response captured per scenario.
- **Race-condition Postgres integration test sweep — all green**: `REF-TEST-01` (concurrent membership refund — already in `apps/backend/tests/integration/payments/test_payments_refund_race.py`), `REF-TEST-02` (concurrent PT-package refund — `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py`), `PTS-TEST-01` (concurrent PT-session decrement — `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py`), `PAY-TEST-01` (concurrent sale double-submit with same `Idempotency-Key` — `apps/backend/tests/integration/payments/test_idempotency.py`), `AUDIT-TEST-01` (every state-mutating service emits expected locked event — `apps/backend/tests/integration/payments/test_payments_audit_chain.py` + `test_payments_refund_audit_chain.py` + `apps/backend/tests/integration/memberships/test_audit_writes.py` + per-module audit tests across trainers/pt_packages/pt_sessions). **These race tests are already implemented in Phases 32-34 — Phase 36 only *executes* them and *captures their evidence*; it does NOT write new race tests.**
- **4 backend CI gates green + admin-web vitest canary green**: `cd apps/backend && uv run ruff check .`, `uv run mypy --strict app`, `uv run pytest -q`, `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` (Phase 35 drift-gate); plus `pnpm --filter @sportzal/admin-web test` recorded as informational canary (NOT a fail-blocker — see D-36-13).
- **Operator sign-off** filed in `.planning/milestones/v1.4-VERIFICATION-LOG.md` with verbatim HTTP evidence per scenario, race-test stdout tail per file, gate-by-gate logs, and any production-blocker regressions discovered and fixed inline (mirrors v1.3 REG-29-01..04 protocol).
- **v1.5 API Handoff scope-handoff prep (drafts)**: auto-generated Postman v2.1 collection from `apps/backend/openapi.json` committed to `.planning/handoff/v1.4-postman.json` + drafted `.planning/handoff/v1.4-auth-runbook.md` covering login/refresh/CSRF/Telegram OTP — both intentionally drafts (v1.5 polishes them; Phase 36 just unblocks the design team).

**4 requirements in scope:** VER-01 (operator scenarios), VER-02 (race tests), VER-03 (CI gates), VER-04 (sign-off + v1.5 handoff prep).

**Out of scope (deferred / handled elsewhere):**
- Authoring NEW race-condition tests — they are already in `apps/backend/tests/integration/{memberships,payments,pt_packages,pt_sessions}/test_*_race.py` from Phases 32-34. Phase 36 runs them and captures evidence; it does not extend the test corpus.
- Authoring NEW operator scenarios beyond the 7+ listed in roadmap SC #1 — additional smoke coverage is a v1.5 / v2.0 concern once the production frontends and Postman collection mature.
- Curating the Postman collection by hand (per-endpoint examples, environments, pre-request scripts) — that is the v1.5 API Handoff milestone proper; Phase 36 only ships the auto-generated draft and a drafted auth runbook to unblock the design team's onboarding.
- Touching `apps/admin-web/src/**` — frozen mock-reference; test failures are informational signal, NOT a Phase 36 fix surface. Any breakage is investigated as a Phase 31-34 backwards-compat regression (fixed in backend) OR deferred to v2.0 — never patched inside admin-web.
- Modifying any service/router/schema code under `apps/backend/app/modules/**` EXCEPT when an inline regression fix is needed (mirrors REG-29-01..04 discipline; each fix is its own commit `fix(36-NN): REG-36-XX <desc>` and recorded in VERIFICATION-LOG.md `overrides:` block).
- Telegram bot smoke — v1.4 did not add new bot flows; the v1.3 bot resolver registrations (REG-29-03 follow-up) still hold. Phase 36 confirms the bot worker starts cleanly in `docker compose up` but does NOT re-run the v1.3 6a/6b DM scenarios (no v1.4 surface change there). Bot extensions for PT-packages are explicitly deferred to v1.6+ per REQUIREMENTS.md "Future Requirements".
- Backend code-review (`/gsd-code-review`), security audit (`/gsd-secure-phase`), UI audit — Phase 36 is verification, not audit. Those run AFTER Phase 36 sign-off if the operator wants extra hygiene before `/gsd-complete-milestone`.
- v1.5 milestone scope (full Postman curation, `GET /api/v1/audit-log`, reports dashboard) — Phase 36 only stubs the handoff artifacts; v1.5 owns the real polish.

</domain>

<decisions>
## Implementation Decisions

### Operator scenarios — authoring & evidence capture (VER-01)

- **D-36-01:** **Hand-authored bash scripts per scenario** under `apps/backend/scripts/verify/<NN>_<scenario_slug>.sh`, each using `curl -i -s -X <METHOD> ... | tee` to capture full HTTP request line + response headers + body. Auth-handling: each script sources a shared `apps/backend/scripts/verify/_lib.sh` that performs login (`POST /api/v1/auth/login` for owner OR reception), captures `sportzal_session` + `sportzal_csrf` cookies into a per-script cookie jar, extracts the access JWT from the response body, and re-emits both as `-H` / `--cookie-jar` flags. Rationale: matches v1.3 Phase 29 discipline (DB-level fixture mutation + scripted recipe per scenario per `29-PATTERNS.md`); curl-native means zero new dependency; jq-extracted IDs flow scenario-to-scenario via env vars (`MEMBERSHIP_ID`, `PT_PACKAGE_ID`).
- **D-36-02:** **Per-scenario evidence file** at `.planning/milestones/v1.4-verification-evidence/<NN>_<scenario_slug>.txt` containing: invocation command, full curl `-v` request/response transcript (or `-i` body + headers), assertion result (PASS / FAIL with reason), elapsed time. VERIFICATION-LOG.md `human_verification:` block references the evidence file path per scenario and inlines a 5-10 line summary excerpt. **Why two artifacts:** evidence file = the audit-grade verbatim record (operator can re-read raw HTTP); VERIFICATION-LOG.md = the narrative summary an external reviewer (or `/gsd-complete-milestone`) can scan in 2 minutes.
- **D-36-03:** **Scenario numbering matches roadmap order** — `01_sale_with_payment`, `02_refund_of_fresh_sale`, `03_refund_frozen_409`, `04_pt_package_sale`, `05_pt_session_record_active_trainer`, `06_pt_package_exhaustion`, `07_trainer_deactivation_409`, `08_cross_phase_smoke`. Eight scripts total (the roadmap "7+" includes the cross-phase smoke explicitly). Cross-phase smoke is a single script with 5 internal steps mirroring v1.3 8-step D-29-08 cross-phase recipe, adapted: sell membership → freeze → attempt refund → 409 → unfreeze → refund succeeds.
- **D-36-04:** **Idempotency-Key discipline in scenarios** — every POST that mutates payment/membership/pt_package state MUST include `-H "Idempotency-Key: $(uuidgen)"`. PAY-TEST-01 race test already covers double-submit at the integration-test layer; operator scripts demonstrate the header is *required* and that absence yields the expected 4xx (one scenario explicitly tests missing-header rejection if applicable — otherwise this is verified implicitly by PAY-TEST-01). Header value generated per-invocation, never hardcoded.
- **D-36-05:** **Inline psql for verification-time data manipulation is allowed** (mirrors v1.3 5c/5d/6a/6b/step3 pattern). E.g., flipping `clients.telegram_user_id` to sandbox chat, advancing `freeze_periods.started_at -5 days`, marking a trainer inactive via `UPDATE trainers SET is_active = false ...`. Every psql mutation is logged in the scenario script with a `--` comment explaining intent, AND noted in the VERIFICATION-LOG.md `notes:` field for that scenario. Discipline: psql is for *verification-time time-travel and fixture state-shaping*, NOT for setting up baseline fixtures (that's the seed script — D-36-06).

### Fixture seeding (VER-01 support)

- **D-36-06:** **New idempotent seed script** `apps/backend/scripts/seed_v1_4_verification_fixtures.py` (mirrors `seed_verification_fixtures.py` shape). Creates: 1 owner user (`verify_owner@local.dev` / fixed password from env) + 1 reception user (`verify_reception@local.dev` / fixed password); 2 membership plans (`Verify Standard 30d` with `freeze_days_limit=14`, `Verify Long 90d` with `freeze_days_limit=30`); 2 PT-package plans (`Verify PT-5` with `session_count=5`, `Verify PT-10` with `session_count=10`); 2 active trainers (`Trainer Alpha`, `Trainer Beta`) + 1 inactive trainer (`Trainer Gamma`, `is_active=false`); 4 clients (`verify_sale`, `verify_refund`, `verify_pt`, `verify_smoke`) with no memberships at start (each scenario provisions its own via the API). All inserts use `INSERT ... ON CONFLICT DO NOTHING` keyed on stable natural keys (email for users, name for plans/trainers, phone for clients) so re-runs are safe. **Why a separate script instead of extending `seed_demo_data.py`:** v1.3 established the discipline of a separate verification-fixture script to keep demo data (for manual exploration) distinct from verification baseline (for deterministic scenario runs). Same pattern.
- **D-36-07:** **Seed script is run ONCE per verification sweep** as Wave-1 prerequisite (`uv run python -m apps.backend.scripts.seed_v1_4_verification_fixtures`); subsequent scenario scripts assume the fixtures exist. Re-run is idempotent so a partial sweep can resume without dropping the schema.

### Race-test execution & evidence (VER-02)

- **D-36-08:** **Single-invocation race-test sweep**:
  ```bash
  cd apps/backend && uv run pytest -q -v \
    tests/integration/payments/test_payments_refund_race.py \
    tests/integration/pt_packages/test_pt_package_refund_race.py \
    tests/integration/pt_sessions/test_pt_session_record_race.py \
    tests/integration/payments/test_idempotency.py \
    tests/integration/payments/test_payments_audit_chain.py \
    tests/integration/payments/test_payments_refund_audit_chain.py \
    tests/integration/memberships/test_audit_writes.py
  ```
  Stdout tail (last ≥20 lines including the per-file pass summary and the final `XX passed in YY.YYs` footer) pasted into VERIFICATION-LOG.md `race_tests:` block. Each test maps explicitly to its requirement-shorthand (REF-TEST-01 ↔ test_payments_refund_race; REF-TEST-02 ↔ test_pt_package_refund_race; PTS-TEST-01 ↔ test_pt_session_record_race; PAY-TEST-01 ↔ test_idempotency; AUDIT-TEST-01 ↔ aggregate of audit_chain + audit_writes + per-module audit tests).
- **D-36-09:** **No new race tests authored in Phase 36.** If a race-test fails or reveals a gap, the fix is in the test file under the *owning phase's* domain (Phases 32-34) committed as `fix(36-NN): REG-36-XX <test path> <reason>` — same inline-regression discipline as REG-29-01..04. New test FILES are flagged as out-of-scope and noted as v1.5 backlog candidates (the verification gate's job is to *prove* coverage, not to *extend* it).

### CI gate evidence (VER-03)

- **D-36-10:** **All 4 backend gates run locally on a clean checkout** (post-`docker compose down -v` + fresh `uv sync` + fresh `pnpm install`) AND cross-linked to a known-green GitHub Actions run URL via `gh run list --workflow=ci --branch=master --limit 1 --json url,conclusion,headSha`. Local stdout tail (≥10 lines including the success footer) pasted into VERIFICATION-LOG.md `ci_gates:` block per gate; GHA URL recorded under `ci_gha_url:` field. Belt + suspenders: GHA proves CI passes in the cloud runner; local proves it passes on the operator's machine (catches "works on CI, broken locally" drift like the v1.3 SECRET_KEY 29→48 byte issue surfaced at test_suites first-run).
- **D-36-11:** **Drift-gate evidence is exactly** `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` (returns 0 + empty stdout when clean). Phase 36 does NOT re-run the export script — Phase 35 already regenerated and committed both artifacts atomically. If the diff is non-empty, that is a regression in Phase 35 land-state (fix in Phase 35 follow-up, NOT in Phase 36).
- **D-36-12:** **Gate ordering for the evidence block:** `ruff` → `mypy --strict` → `pytest` → `drift-gate (openapi.json)` → `drift-gate (schema.d.ts)`. This matches `.github/workflows/ci.yml` job ordering so an external reviewer can match local evidence to CI logs line-by-line.

### admin-web canary handling

- **D-36-13:** **admin-web vitest specs are an INFORMATIONAL canary in Phase 36** (NOT a blocking gate, unlike Phase 35 D-35-13 which kept them blocking *because schema.d.ts was the contract artifact being shipped*). Justification: post-Phase-35, admin-web's role is "mock-mode reference implementation that happens to exercise the typed contract"; in Phase 36 we are verifying the BACKEND, not the contract. A red admin-web spec is investigated (it may surface a backend regression that the contract test missed) but does NOT block sign-off. If red, the investigation outcome goes in VERIFICATION-LOG.md `admin_web_canary:` field: either "investigated → backend regression → REG-36-XX fixed inline" OR "investigated → admin-web mock divergence (pre-existing or new) → deferred to v2.0 Frontend Integration".
- **D-36-14:** **Command + evidence:** `pnpm --filter @sportzal/admin-web test` + `pnpm --filter @sportzal/admin-web typecheck` + `pnpm --filter @sportzal/admin-web lint`. Pasted stdout tail under `admin_web_canary:` block in VERIFICATION-LOG.md. Pass count + threshold from v1.3 baseline (≥233 tests) recorded for trend.

### Regression-handling discipline

- **D-36-15:** **Inline-fix protocol mirrors v1.3 REG-29-01..04 exactly.** Any production-blocker regression discovered during scenario execution OR race-test run OR CI-gate run is:
  1. **Reproduced** with a minimal repro snippet logged in VERIFICATION-LOG.md `overrides:` block.
  2. **Fixed inline** in Phase 36 (own commit: `fix(36-NN): REG-36-XX <short desc>` — `NN` is the Phase 36 plan that surfaced it; `XX` is sequential).
  3. **Re-verified** by re-running the failing scenario / test / gate; evidence captured.
  4. **Cross-referenced** in the `overrides:` block with `gap` (REG-36-XX), `resolved_in` (commit SHA + message), `evidence` (verbatim post-fix HTTP / pytest / gate output).
- **D-36-16:** **Production-blocker definition** for Phase 36: any scenario that fails with 5xx, any race-test failure, any CI gate red, any wrong 2xx body shape vs `openapi.json`, any wrong audit-event emission, any RBAC byte-paritet break. **NOT a production-blocker** (defer to v1.5): cosmetic stdout differences, minor admin-web mock-mode UX drift, Postman/runbook draft incompleteness, log-level tuning, comment-only doc-debt (the `Phase 35 UI` / `FE-13 in Phase 35` stale references noted in Phase 35 deferred ideas — Phase 36 will not touch those either).
- **D-36-17:** **Hard-cap on inline regressions:** if more than 5 production-blockers are found, STOP Phase 36, escalate to operator, and reassess milestone readiness (suggests Phases 30-35 verification gaps that warrant a Phase 36.1 hot-fix phase or a milestone hold). Five is the soft signal — v1.3 closed with 3 inline fixes and that was considered healthy; double that is unhealthy.

### v1.5 API Handoff scope-handoff prep (VER-04)

- **D-36-18:** **Postman collection generation is auto-derived, not hand-curated.** Use `npx openapi-to-postmanv2 -s apps/backend/openapi.json -o .planning/handoff/v1.4-postman.json -p` (or equivalent; planner picks the exact tool — `openapi-to-postmanv2` is the Postman-official choice; `apimatic` is a backup). The output is COMMITTED to `.planning/handoff/v1.4-postman.json` as a DRAFT (header in the README clearly says "auto-derived; v1.5 will curate examples + environments + auth scripts"). **Why a draft now:** unblocks the design team to *open* the collection and start exploring; v1.5 owns the polish (sample bodies, OAuth/cookie environment, pre-request login script).
- **D-36-19:** **Auth setup runbook is drafted in markdown** at `.planning/handoff/v1.4-auth-runbook.md`. Sections (max 1-2 paragraphs each + a curl example per section): (a) "Login as owner / reception" (`POST /api/v1/auth/login` request + response shape, cookie semantics `sportzal_session` HTTP-only + `sportzal_csrf` JS-readable, access JWT in body); (b) "Refresh rotation family" (`POST /api/v1/auth/refresh` + when to call, single-flight pattern pointer to `packages/api-client/README.md § Single-flight refresh`); (c) "CSRF on mutating requests" (every POST/PATCH/DELETE needs `X-CSRF-Token: <cookie value>` — pointer to existing `packages/api-client/README.md § CSRF`); (d) "Telegram OTP for client-app path" (`POST /api/v1/auth/otp/{start,status,verify}` — same shape as bot worker uses); (e) "Logout-all" (`POST /api/v1/auth/logout-all` — kills the rotation family). Heading: "**v1.4 DRAFT — v1.5 will expand with sample integration flows and error-handling cookbook.**" Length cap: 150-200 lines.
- **D-36-20:** **Handoff artifacts are committed in a SEPARATE commit** from the verification evidence (`docs(handoff): v1.5 API handoff draft (Postman + auth runbook)`). Rationale: cleaner downstream-team discovery; if the design team only wants the handoff, they can `git log .planning/handoff/` and not get drowned in verification noise.
- **D-36-21:** **Handoff prep is the LAST plan in Phase 36** (Wave 3) — runs only after verification PASS is filed. If verification fails (>5 inline regressions per D-36-17), handoff prep is SKIPPED and the handoff is deferred to a Phase 36.1 hot-fix cycle. Don't ship a handoff for a non-shippable milestone.

### Plan structure (Wave plan)

- **D-36-22:** **Five plans, three waves**:
  - **Wave 1 (sequential start):**
    - `36-01-PLAN.md` — Live-stack bring-up recipe (`docker compose up` with `seed_v1_4_verification_fixtures` invocation) + scenario script scaffold (`apps/backend/scripts/verify/_lib.sh` + the 8 scenario stubs with TODO bodies) + new seed script `seed_v1_4_verification_fixtures.py` (D-36-06).
  - **Wave 2 (parallel after Wave 1):**
    - `36-02-PLAN.md` — Execute operator scenarios 01-08 against live stack; fill verbatim evidence into `.planning/milestones/v1.4-verification-evidence/*.txt`; populate VERIFICATION-LOG.md `human_verification:` block (D-36-01..05).
    - `36-03-PLAN.md` — Execute race-test sweep + capture stdout tails in VERIFICATION-LOG.md `race_tests:` block (D-36-08, D-36-09).
    - `36-04-PLAN.md` — Run 4 backend CI gates locally + capture GHA URL cross-link; populate VERIFICATION-LOG.md `ci_gates:` + `admin_web_canary:` blocks (D-36-10..14).
  - **Wave 3 (sequential after Wave 2 PASS):**
    - `36-05-PLAN.md` — Finalize VERIFICATION-LOG.md (operator sign-off line, deferred-items roll-up, REG-36-XX `overrides:` block); commit handoff drafts (`.planning/handoff/v1.4-postman.json` + `.planning/handoff/v1.4-auth-runbook.md`); update STATE.md milestone-close prep; tear down `docker compose down -v` if operator wants a clean slate (D-36-18..21).
- **D-36-23:** **Plan-count rationale** — v1.3 Phase 29 ran 6 plans; v1.4 Phase 36 condenses to 5 by dropping the `one-shot expiring-cron runner` plan (no v1.4 cron addition needed — the v1.3 cron runner stays as-is and is exercised only as part of the cross-phase smoke if relevant; for v1.4 the new cron is `expire_pt_packages` which is exercised by `test_expire_pt_packages_cron.py` already in the race-test sweep). Adding handoff prep as a dedicated plan (Wave 3) is the v1.4-specific addition.
- **D-36-24:** **Each plan is a single atomic commit on success** (per GSD discipline); regressions discovered during a plan get their own `fix(36-NN): REG-36-XX` commits BEFORE the plan's main commit closes. VERIFICATION-LOG.md is touched incrementally per plan (each plan owns its own section); the final sign-off line is added by `36-05-PLAN.md` only.

### Verification log artifact shape

- **D-36-25:** **Single canonical artifact** at `.planning/milestones/v1.4-VERIFICATION-LOG.md` (mirrors `v1.3-VERIFICATION-LOG.md` shape exactly). YAML frontmatter (`phase: 36-milestone-verification`, `milestone: v1.4`, `verified: <ISO>`, `status: passed|failed`, `score: "<N>/<M> scenarios verified — <K> regressions fixed inline"`, `overrides_applied: <K>`, `overrides: [...]`). Body sections: `human_verification:` (8 scenarios), `race_tests:` (5 logical tests, 7 files), `ci_gates:` (5 gates incl. drift), `admin_web_canary:` (informational), `test_suites:` (full backend + admin-web pass counts + evidence tail), `deferred_items:` (roll-up), `handoff_artifacts:` (paths + draft notes), `sign_off:` (operator confirmation timestamp + free-text).
- **D-36-26:** **Per-scenario evidence files** under `.planning/milestones/v1.4-verification-evidence/<NN>_<slug>.txt` (committed). Plain text, NOT yaml/markdown — they are raw HTTP transcripts, optimized for grep + diff over time.

### Claude's Discretion

- **Exact `Idempotency-Key` UUID generation strategy** (`uuidgen` POSIX vs Python `uuid.uuid4()` vs `openssl rand -hex 16`) — planner picks `uuidgen` since it's a POSIX one-liner already available on the operator's macOS and inside the backend container.
- **Whether to inline a `make verify` target** in `apps/backend/Makefile` that runs the seed + scenarios + race tests + gates in sequence — nice-to-have ergonomic; if the planner ships it, fine; if not, Wave 3 `36-05-PLAN.md` documents the manual recipe in VERIFICATION-LOG.md `recipe:` section.
- **Exact pytest invocation for the race-test sweep** — `-q -v` is the default; `--tb=short` if stdout is too noisy; planner has discretion to add markers if the project's `pytest.ini` exposes them.
- **Stdout-tail line counts** — D-36-08 says "≥20 lines" but planner can include more if the per-file summary needs context.
- **Markdown heading depth in VERIFICATION-LOG.md sections** — mirror v1.3 shape unless planner has a clear ergonomic reason to deviate.
- **Order of GitHub Actions URL capture** (before or after local runs) — planner's call; capturing AFTER local runs is slightly preferred because operator may push a hotfix mid-verification.

### Folded Todos

[None — `cross_reference_todos` returned 0 matches for Phase 36.]

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 36 anchor docs

- `.planning/ROADMAP.md` § "Phase 36: Milestone Verification (backend-only)" — phase goal + 4 success criteria + dependency chain (Phase 35).
- `.planning/REQUIREMENTS.md` § "VER — Milestone Verification (Phase 36, backend-only)" — VER-01..04 verbatim text; coverage map confirms 4/4 in scope.
- `.planning/PROJECT.md` § "Current Milestone: v1.4 Cash Sales + PT Packages" + § "Long-term MVP roadmap (post-v1.4)" — v1.5 API Handoff is the downstream consumer of Phase 36 handoff drafts.
- `.planning/STATE.md` § "v1.4 Milestone Plan" — confirms Phases 30-35 complete + Phase 36 is the gate; also see `### Decisions` block for the 12 bedrock decisions B-01..B-12.

### Precedent: v1.3 Phase 29 (the playbook this phase replays)

- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 29: Milestone Verification" — 4 success criteria + 6-plan shape; Phase 36 condenses to 5 plans per D-36-22/23.
- `.planning/milestones/v1.3-VERIFICATION-LOG.md` (full file) — **canonical structural template** for Phase 36's verification log. Mirror YAML frontmatter, `human_verification:` block shape, `overrides:` block shape, `test_suites:` block shape exactly. **Read in full before planning Wave 3.**
- `.planning/phases/29-*/29-PATTERNS.md` (if present) — captures verification-time patterns (DB-level fixture mutation discipline, cookie-jar reuse, scenario script shape). Read for pattern fidelity.
- `apps/backend/scripts/seed_verification_fixtures.py` — Phase 36's `seed_v1_4_verification_fixtures.py` mirrors this script's shape (idempotent `INSERT ... ON CONFLICT DO NOTHING` keyed on natural keys + bcrypt/argon2 password hash from env var). **Read structurally; do not edit.**

### Race-test files (Phase 36 executes these — does NOT modify them)

- `apps/backend/tests/integration/payments/test_payments_refund_race.py` — REF-TEST-01 (concurrent membership refund; partial UNIQUE on `refund_of` wins).
- `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py` — REF-TEST-02 (concurrent PT-package refund).
- `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py` — PTS-TEST-01 (concurrent PT-session decrement; `sessions_remaining` race-proof).
- `apps/backend/tests/integration/payments/test_idempotency.py` — PAY-TEST-01 (concurrent sale double-submit with same `Idempotency-Key`).
- `apps/backend/tests/integration/payments/test_payments_audit_chain.py` + `test_payments_refund_audit_chain.py` + `apps/backend/tests/integration/memberships/test_audit_writes.py` + per-module audit tests in `tests/integration/{trainers,pt_packages,pt_sessions}/` — AUDIT-TEST-01 (every state-mutating service emits expected locked event).

### Live-stack + CI gate surfaces

- `docker-compose.yml` (repo root) — 5-service stack (backend + postgres + redis + telegram bot worker + arq worker + one-shot migrate). `docker compose up` is the entry point for Phase 36 verification.
- `apps/backend/scripts/seed_demo_data.py` — operator-exploration fixture seed; Phase 36 does NOT use this for verification (uses `seed_v1_4_verification_fixtures.py` per D-36-06) but the planner reads it for invocation-shape parity.
- `.github/workflows/ci.yml` — 6 parallel CI gates (backend: ruff, mypy --strict, pytest, openapi.json drift; frontend: typecheck, lint, test, schema.d.ts drift). Phase 36 captures the 4 backend gates + drift-gate as evidence; admin-web typecheck/lint/test as informational canary.
- `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` — Phase 35 frozen artifacts; Phase 36 only `git diff --exit-code`s them, never re-generates.
- `apps/backend/pyproject.toml` § `[tool.pytest.ini_options].filterwarnings = ["error"]` — known foot-gun from v1.3 (dev `.env` `SECRET_KEY` 29 bytes tripped pyjwt InsecureKeyLengthWarning). Phase 36 verifies the verification env has `SECRET_KEY` of ≥48 bytes before running pytest to avoid the same first-run-failure noise.

### Module-level surface (read for scenario shape, do NOT modify)

- `apps/backend/app/api/v1/router.py` (lines 35-53) — single source of truth for v1.4 route mounting; scenario scripts derive URLs from here.
- `apps/backend/app/modules/payments/router.py` + `apps/backend/app/modules/payments/service.py` — payment ledger + refund orchestrator; scenarios 01/02/03/06 hit this surface.
- `apps/backend/app/modules/memberships/router.py` + service — sale/freeze/unfreeze/refund flows; scenarios 01/02/03/08 hit this surface.
- `apps/backend/app/modules/pt_packages/router.py` + service — PT-package sale/cancel/refund; scenarios 04/06 hit this surface.
- `apps/backend/app/modules/pt_sessions/router.py` + service — PT-session record/cancel; scenarios 05/07 hit this surface.
- `apps/backend/app/modules/trainers/router.py` + service — trainer CRUD + soft-delete; scenario 07 hits this surface.
- `apps/backend/app/core/security.py` + `apps/backend/app/modules/auth/router.py` — login/refresh/CSRF/cookie semantics; `apps/backend/scripts/verify/_lib.sh` derives cookie-jar handling from here.

### Frozen surfaces (DO NOT MODIFY in Phase 36, even on regression)

- `apps/admin-web/src/**` — frozen mock-reference; any breakage is INVESTIGATED (admin_web_canary block) but never patched in Phase 36.
- `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` — Phase 35 contract; drift = Phase 35 follow-up, not Phase 36 fix.
- `LOCKED_AUDIT_EVENTS` frozenset (51 entries post-Phase-30); `OWNER_ONLY` frozenset (~26 entries post-Phase-30) — locked v1.4 bedrock; AUDIT-TEST-01 verifies adherence but Phase 36 does not extend either.

### Handoff target surfaces (CREATED by Phase 36 Wave 3)

- `.planning/handoff/v1.4-postman.json` — auto-generated Postman v2.1 collection (NEW file, committed by Wave 3 per D-36-18).
- `.planning/handoff/v1.4-auth-runbook.md` — auth setup runbook draft (NEW file, committed by Wave 3 per D-36-19).
- `.planning/milestones/v1.4-VERIFICATION-LOG.md` — single canonical verification artifact (NEW file, populated incrementally by Waves 2-3 per D-36-25).
- `.planning/milestones/v1.4-verification-evidence/<NN>_<slug>.txt` — per-scenario raw HTTP transcripts (NEW files, committed by Wave 2 per D-36-26).
- `apps/backend/scripts/verify/_lib.sh` + `apps/backend/scripts/verify/<NN>_<slug>.sh` (8 files) — scenario script scaffold + the 8 scenarios (NEW files, scaffold in Wave 1, populated in Wave 2).
- `apps/backend/scripts/seed_v1_4_verification_fixtures.py` — verification baseline seed (NEW file, Wave 1).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/scripts/seed_verification_fixtures.py`** (v1.3 era) — idempotent natural-key seed pattern; argon2 hash from env var; ON CONFLICT DO NOTHING. Phase 36's `seed_v1_4_verification_fixtures.py` is a direct shape-mirror.
- **`apps/backend/scripts/seed_demo_data.py`** — invocation shape (`uv run python -m apps.backend.scripts.seed_demo_data`); planner reads for module-path consistency.
- **`apps/backend/scripts/run_expiring_cron_once.py`** (v1.3 era) — operator one-shot runner pattern; if Phase 36 wants to spot-check `expire_pt_packages` cron outside the integration-test layer, a similar `run_expire_pt_packages_once.py` could be added under Claude's discretion (D-36 discretion block did NOT include this — keep out of scope unless test_expire_pt_packages_cron.py coverage proves insufficient).
- **`.planning/milestones/v1.3-VERIFICATION-LOG.md`** — canonical artifact shape template (YAML frontmatter + sectioned body); mirror exactly.
- **`apps/backend/tests/conftest.py` (lines ~60-100)** — SAVEPOINT outer-transaction pattern; reassurance that live-stack data does NOT pollute pytest runs (so verification stack + race-test sweep can coexist on the same Postgres instance).
- **`apps/backend/scripts/export_openapi.py`** — D-04 ENVIRONMENT setdefault discipline (no Postgres/Redis touch on import); Phase 36 does NOT invoke this script, but the planner reads it to understand the export-side of the drift-gate.

### Established Patterns

- **Verification-as-audit gate** (v1.3 Phase 29 → v1.4 Phase 36) — third iteration of this discipline (v1.2 had it embedded in Phase 22; v1.3 Phase 29 made it standalone; v1.4 Phase 36 condenses for backend-only). Pattern is stable.
- **Inline-regression fix discipline** (REG-29-01..04) — production-blockers found at the gate get fixed inline, NOT deferred; each fix is its own commit; `overrides:` block tracks them.
- **DB-level fixture mutation during verification** (v1.3 5c psql UPDATE; 6a/6b telegram_user_id flips; step3 freeze_started_at -5d) — sanctioned for verification-time time-travel; logged in scenario script comments + VERIFICATION-LOG.md notes.
- **Force-recreate vs restart for env_file changes** (v1.3 5d lesson: `docker compose up -d --force-recreate --no-deps backend` is required when `apps/backend/.env` is mutated mid-verification; plain `restart` does NOT reload env_file). Phase 36 propagates this lesson — if any scenario needs env mutation, the script does force-recreate.
- **SECRET_KEY ≥48 bytes** (v1.3 first-run-failure lesson) — Wave 1 verifies env satisfies this before invoking pytest, to spare the operator the 38 failed / 239 errors first-run surprise.
- **Belt + suspenders on Protocol slot registration** (REG-29-03 lesson, now codified per Phase 31 D-31-3) — `create_app()` + `telegram_bot.main()` BOTH register every Protocol slot; verified at app-boot in scenario 01 implicitly (live stack boots cleanly = all registrations green).

### Integration Points

- **`docker compose up` stack** — backend on `:8000`, postgres on `:5432`, redis on `:6379`, telegram bot worker (no port), arq worker (no port), one-shot migrate. Scenario scripts target `http://localhost:8000`.
- **Cookie jar per scenario** — `_lib.sh` exports `COOKIE_JAR=$(mktemp)` for each scenario; cleaned up at script end. No global cookie state across scenarios → each scenario is hermetic.
- **psql connection** — scenarios that need DB mutation use `psql "postgresql://sportzal:sportzal@localhost:5432/sportzal" -c "<sql>"` (credentials match `docker-compose.yml` defaults; planner reads to confirm).
- **GitHub Actions URL capture** — `gh run list --workflow=ci --branch=master --limit 1 --json url,conclusion,headSha` — requires `gh` auth on operator's machine; if `gh` unavailable, fall back to raw URL pasted from browser (noted in VERIFICATION-LOG.md `ci_gha_url:` field).
- **Postman collection generation** — `npx openapi-to-postmanv2 -s apps/backend/openapi.json -o .planning/handoff/v1.4-postman.json -p` requires only Node/npm (already in dev env); no Python-side change.

</code_context>

<specifics>
## Specific Ideas

- **The "backend-only" framing is the through-line.** Every plan, every scenario script comment, every section header in VERIFICATION-LOG.md should reference it — so that a future reader (or onboarding AI agent) understands why Phase 36 looks so much smaller and curl-shaped than Phase 29. The pivot date (2026-05-15) + FE-11..18 → v2.0 deferral are the historical anchor.
- **Operator sign-off line in VERIFICATION-LOG.md** should be a verbatim free-text confirmation (e.g., `"Operator sign-off: pass — v1.4 ready to ship — 2026-05-17T1X:XXZ"`) NOT a checkbox or YAML-only flag. Matches v1.3 `result: pass` + `evidence: "Verbatim operator confirmation 'pass' at <ISO>"` pattern.
- **The 5-blocker hard cap (D-36-17) is a soft signal AND a hard escalation rule.** Plan-checker should flag any Wave 2 plan that's silently accumulating REG-36-XX entries without escalating; planner adds an explicit "if REG count > 5: STOP" check in `36-05-PLAN.md`'s exit criteria.
- **No new "human UAT" YAML block in VERIFICATION-LOG.md** — that block is reserved for admin-web UI interaction (v1.3 style). Phase 36 uses `human_verification:` for the curl/operator-script scenarios but labels each with `via: curl` (or `via: psql` for DB-mutation steps) so future reviewers immediately know this was NOT a UI test. The `human_verification` block name is kept for YAML-schema continuity with v1.3 tooling.
- **`Phase 35 UI` / `FE-13 in Phase 35` stale doc-debt** noted in Phase 35 deferred ideas is INHERITED by Phase 36 as a deferred item (not fixed); roll-up into the milestone-close deferred items block.

</specifics>

<deferred>
## Deferred Ideas

- **Newman-CLI-based Postman runner** (`newman run .planning/handoff/v1.4-postman.json`) for non-interactive replay of the collection — belongs in v1.5 API Handoff milestone (turns the draft collection into an executable contract test).
- **Curated Postman environments + pre-request login scripts** — v1.5; Phase 36 ships only the auto-derived draft.
- **`GET /api/v1/audit-log` read API** for owner — v1.6 Reports milestone (currently audit_log is write-only from the API surface; SQL queries are operator-side).
- **End-of-day cash drawer reconciliation** (B-06: explicitly deferred to v1.5+ in roadmap).
- **Pro-rata refunds** (B-02 amendment): v1.5+.
- **Bot extensions for PT-packages** (`/pt_packages` self-balance Telegram command) — v1.6+ per REQUIREMENTS.md Future Requirements.
- **Cleanup of stale `Phase 35 UI` / `FE-13 in Phase 35` doc-strings** in `apps/backend/app/modules/memberships/router.py` and `apps/backend/app/modules/payments/router.py` — inherited from Phase 35 deferred ideas; v1.5 cleanup wave.
- **`@sportzal/api-client` package.json version bump (`0.0.0` → `0.1.0`)** — inherited from Phase 35; v1.5 publish prep.
- **Auto-publishing `openapi.json` to a versioned URL** — inherited from Phase 35; v1.5.
- **OpenAPI tag curation + operationId discipline** — inherited from Phase 35; v1.5 ergonomics pass once design team gives feedback on generated method names.
- **`260501-ndi` orphan `.planning/quick/` directory cleanup** — defer to next `/gsd-cleanup` run (carried since v1.3 close).
- **v1.1 06-HUMAN-UAT.md + 08-HUMAN-UAT.md advisory scenarios** — re-evaluate at Phase 36 verification if any touch user-facing flows. **Phase 36 decision:** these are admin-web UI flows; backend-only verification scope does NOT exercise them. Re-roll to v2.0 Frontend Integration milestone where production admin-web UAT lives.
- **Add a `seed reception` option to `seed_demo_data.py` or a `POST /api/v1/users` create endpoint** (v1.3 verification surfaced this gap when reception user had to be psql-INSERTed). **Phase 36 decision:** `seed_v1_4_verification_fixtures.py` (D-36-06) explicitly seeds reception, so the verification flow is unblocked; the broader `seed_demo_data` enhancement remains a v1.5+ ergonomic backlog item.
- **Make-target ergonomics (`make verify` runs the full Phase 36 recipe)** — Claude's discretion per discuss decisions block; if not added, the manual recipe is documented in VERIFICATION-LOG.md `recipe:` section.

### Reviewed Todos (not folded)

None — `cross_reference_todos` returned 0 matches for Phase 36.

</deferred>

---

*Phase: 36-Milestone-Verification-(backend-only)*
*Context gathered: 2026-05-16*
