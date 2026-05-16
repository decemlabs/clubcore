# Phase 36: Milestone Verification (backend-only) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `36-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 36-milestone-verification-backend-only
**Mode:** `/gsd-discuss-phase 36 --auto` — single pass; Claude auto-selected the recommended option for every gray area without using AskUserQuestion. Each row's checked option is the auto-selected recommended default.
**Areas discussed:** Operator scenarios — authoring & evidence; Fixture seeding; Race-test execution; CI gate evidence; admin-web canary handling; Regression-handling discipline; v1.5 API Handoff scope-handoff prep; Plan structure (Wave plan); Verification log shape

---

## Operator scenarios — authoring & evidence capture (VER-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-authored bash curl scripts per scenario + per-scenario evidence txt + VERIFICATION-LOG.md summary | `apps/backend/scripts/verify/<NN>_<slug>.sh` using `curl -i`/`-v` + jq; `_lib.sh` shared cookie-jar/login helpers; raw transcripts under `.planning/milestones/v1.4-verification-evidence/`. Matches v1.3 Phase 29 discipline (29-PATTERNS.md). | ✓ |
| Postman collection + Newman CLI for non-interactive replay | Cleaner per-scenario YAML/JSON, but adds Newman dependency and conflates v1.5 handoff (curated Postman) with v1.4 verification (verbatim evidence). | |
| httpie + recorded transcripts | More readable, but adds httpie dep and breaks parity with v1.3 curl shape. | |

**Auto-selected:** Hand-authored curl scripts + per-scenario evidence files.
**Rationale (auto):** Mirrors v1.3 Phase 29 exactly; zero new deps; clean separation between v1.4 verification (raw curl evidence) and v1.5 handoff (auto-generated Postman draft).

---

## Fixture seeding (VER-01 support)

| Option | Description | Selected |
|--------|-------------|----------|
| New idempotent `seed_v1_4_verification_fixtures.py` (mirrors v1.3 `seed_verification_fixtures.py`) | Owner + reception users, 2 membership plans, 2 PT plans, 3 trainers (2 active + 1 inactive), 4 clients with no memberships. ON CONFLICT DO NOTHING. | ✓ |
| Reuse `seed_demo_data.py` + ad-hoc psql for verification deltas | Conflates exploration fixtures with verification baseline; brittle. | |
| Hand-typed curl POSTs to seed via real API | Bootstrap problem (need fixtures to test the API; can't use API to create them); rejected. | |

**Auto-selected:** New idempotent seed script.

---

## Race-test execution & evidence (VER-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Single-invocation pytest sweep targeting the 7 race/audit files + stdout tail in VERIFICATION-LOG.md `race_tests:` block | Explicit per-test path list; pass count + final footer captured. Race tests already exist in Phases 32-34; Phase 36 only executes them. | ✓ |
| Run full pytest suite and grep for race tests | Wastes time; obscures which lines correspond to which race-test requirement. | |
| Run each race-test individually for granular evidence | Verbose; no value over single sweep with `-v`. | |

**Auto-selected:** Single-invocation sweep.

---

## CI gate evidence (VER-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Local re-run on clean checkout + cross-link to known-green GitHub Actions run URL | Belt + suspenders; catches "works on CI, broken locally" drift like v1.3 SECRET_KEY 29→48 byte surprise. | ✓ |
| GHA URL only (no local re-run) | Faster but misses local-env drift. | |
| Local run only (no GHA URL) | Misses cloud-runner-specific signals. | |

**Auto-selected:** Belt + suspenders.

---

## admin-web canary handling

| Option | Description | Selected |
|--------|-------------|----------|
| Informational canary — runs `pnpm --filter @sportzal/admin-web test`+`typecheck`+`lint`, records pass count, but red is NOT a fail-blocker | Investigated outcome goes in `admin_web_canary:` block; outcome is either "backend regression → REG-36-XX fixed inline" OR "admin-web mock divergence → deferred to v2.0". | ✓ |
| Skip admin-web entirely (out of scope per pivot) | Loses early-warning signal for backwards-incompat schema changes that bypassed the contract test. | |
| Full v1.3 blocking discipline | Inappropriate now that admin-web is frozen mock-reference, not production target. | |

**Auto-selected:** Informational canary (matches roadmap SC #3).

---

## Regression-handling discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Inline-fix protocol mirroring v1.3 REG-29-01..04 with hard cap at 5 blockers | Each fix is own commit `fix(36-NN): REG-36-XX <desc>`; `overrides:` block in VERIFICATION-LOG.md tracks them; >5 blockers triggers escalation. | ✓ |
| Defer all regressions to v1.5 backlog | Breaks the "verification gate" promise; ships a known-broken milestone. | |
| Spawn Phase 36.1 hot-fix phase per regression | Ceremony without value for small fixes; reserved for >5-blocker escalation. | |

**Auto-selected:** Inline-fix protocol + hard cap.

---

## v1.5 API Handoff scope-handoff prep (VER-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal drafts: auto-generated Postman v2.1 collection from `openapi.json` + drafted auth runbook (login/refresh/CSRF/Telegram OTP) | Both committed under `.planning/handoff/v1.4-*` as DRAFTS; v1.5 polishes (sample bodies, environments, full integration cookbook). Unblocks design team's onboarding. | ✓ |
| Defer all handoff prep to v1.5 (Phase 36 only validates v1.4) | Roadmap VER-04 explicitly requires "Postman collection finalized, auth setup runbook drafted" — full deferral would fail the requirement. | |
| Hand-curate Postman collection + runbook from scratch | Massive scope creep into v1.5 territory. | |

**Auto-selected:** Minimal drafts.

---

## Plan structure (Wave plan)

| Option | Description | Selected |
|--------|-------------|----------|
| 5 plans, 3 waves: W1 bring-up + seed; W2 scenarios ∥ race-tests ∥ CI-gates; W3 finalize log + handoff drafts | Condensed v1.3 Phase 29 6-plan shape (drops `one-shot cron runner` plan — not needed for v1.4); adds Wave-3 handoff prep. | ✓ |
| Single mega-plan | Loses atomic-commit discipline; no parallelization. | |
| Per-scenario plan (10+ plans) | Excessive ceremony; scenario execution is straight-line work. | |

**Auto-selected:** 5 plans, 3 waves.

---

## Verification log artifact shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single canonical `.planning/milestones/v1.4-VERIFICATION-LOG.md` mirroring v1.3-VERIFICATION-LOG.md YAML + sectioned-body shape exactly | Tooling continuity; future `/gsd-complete-milestone` and external reviewers know the layout. | ✓ |
| Per-plan log files (`36-01-VERIFICATION.md` etc.) | Fragments evidence; no single sign-off surface. | |
| Inline log in PHASE-VERIFICATION.md only | Misses milestone-close artifact discoverability. | |

**Auto-selected:** Single canonical milestone log.

---

## Claude's Discretion

- Exact `Idempotency-Key` UUID generation strategy (planner picks `uuidgen` for POSIX availability on operator macOS + inside backend container).
- Whether to inline a `make verify` Makefile target running the full recipe.
- Exact pytest invocation flags for the race-test sweep (`-q -v` default; planner adds `--tb=short` if too noisy).
- Stdout-tail line counts (D-36-08 says "≥20 lines"; planner can include more for context).
- Markdown heading depth in VERIFICATION-LOG.md sections.
- Order of GitHub Actions URL capture (before or after local runs).
- Order of method assertions inside per-scenario script comments (planner picks by chronological scenario number).

## Deferred Ideas

(See `36-CONTEXT.md` § `<deferred>` for the canonical roll-up. Key items: Newman-CLI runner → v1.5; curated Postman environments → v1.5; `GET /api/v1/audit-log` → v1.6; pro-rata refunds → v1.5+; bot extensions for PT-packages → v1.6+; stale `Phase 35 UI` doc-strings cleanup → v1.5 cleanup wave; `260501-ndi` orphan dir → next `/gsd-cleanup`; v1.1 06/08-HUMAN-UAT advisory scenarios → v2.0 Frontend Integration; `seed_demo_data.py` reception-seed enhancement → v1.5+; `@sportzal/api-client` version bump → v1.5; auto-publishing `openapi.json` to versioned URL → v1.5; OpenAPI tag curation + operationId discipline → v1.5.)
