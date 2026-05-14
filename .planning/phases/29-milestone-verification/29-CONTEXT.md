# Phase 29: Milestone Verification — Context

**Gathered:** 2026-05-14
**Mode:** `--auto` (Claude picked recommended option for every gray area; review and adjust before planning)
**Status:** Ready for planning

<domain>
## Phase Boundary

End-of-milestone verification phase — no production code changes. Two deliverables:

1. **DEBT-04 closure:** prove all 6 inherited interactive smoke tests from
   `.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-VERIFICATION.md`
   `human_verification:` block (FE-08 edges, FE-09 sessions, D-22-11 Telegram DM copy)
   pass against a **live backend + Telegram sandbox** running on the developer machine.
2. **Cross-phase smoke:** execute one end-to-end scenario exercising freeze (Phase 25),
   renewal (Phase 26), and expiring-soon DMs (Phase 27) on the same live stack.

Plus operational gates that must already be green by the time this phase starts:

- Backend test suite ≥ 600 passing.
- admin-web test suite ≥ 190 passing.
- All CI gates green: ruff + mypy strict + import-linter + eslint + drift-gate.

**In scope:**

- Booting `apps/backend/docker-compose.yml` stack (backend + telegram-bot + arq-worker
  + postgres + redis) plus admin-web on `VITE_API_MODE=http` for smoke execution.
- Seeding a deterministic fixture set sufficient for both DEBT-04 and the cross-phase
  smoke.
- Executing the 6 DEBT-04 scenarios in order, recording pass/fail + evidence per test.
- Executing the cross-phase scenario (sell → freeze 5d → unfreeze → renew → fast-forward
  cron 06:15 → observe 7d/3d/1d DMs in sandbox).
- Capturing verbatim test-suite output + CI gate status as evidence.
- Writing `.planning/milestones/v1.3-VERIFICATION-LOG.md` with structured pass/fail per
  scenario (frontmatter mirrors v1.2's `22-VERIFICATION.md` `human_verification:` shape).
- Classifying any regression discovered as **hard-block** vs **defer-to-v1.4** with
  explicit owner sign-off rationale.

**Out of scope:**

- Any new backend endpoints, schema changes, or frontend UI work — locked by
  Roadmap "verification ≠ implementation" rule. Bug fixes for regressions found are
  permitted but only under a separate phase or quick-task (Phase 24/25/26/27/28 patch).
- `/gsd-complete-milestone` execution itself — Phase 29 stops at writing
  `v1.3-VERIFICATION-LOG.md`. The audit artifact (`v1.3-MILESTONE-AUDIT.md`) is generated
  by `/gsd-complete-milestone` invoked **after** this phase succeeds (SC #4 "или
  эквивалентный артефакт" — explicit hand-off).
- Production deployment / staging environments — verification runs against developer
  docker-compose stack only. Telegram bot uses the existing sandbox token from `.env`.
- Performance / load testing — out of scope (no SLO targets for v1.3).
- Telegram bot copy translation review — already locked under NTF-COPY-01 (Phase 27)
  and D-22-11 (Phase 22 carry-forward). Phase 29 only confirms the strings render
  in DMs unchanged.

</domain>

<decisions>
## Implementation Decisions

### D-29-01: Live stack = `apps/backend/docker-compose.yml` + admin-web `pnpm dev`
- Boot order: `cd apps/backend && docker compose up -d` (waits on `migrate` →
  `postgres` healthcheck per `docker-compose.yml:51-75`). One command, no new tooling.
- Frontend: `pnpm --filter @sportzal/admin-web dev` with `VITE_API_MODE=http` and
  `VITE_API_BASE=http://localhost:8000` (existing `.env.example` defaults).
- No staging / production deploy. Single-host verification; explicit deviation from
  prod parity (Phase 29 only proves the milestone surface works against a real backend +
  real bot, not against a production-shaped environment).
- Tear-down: `docker compose down -v` after verification (`-v` drops `postgres-data`
  volume so the next run starts clean) — captured in the plan as the final step so
  the developer machine doesn't carry verification fixtures into the next milestone.

### D-29-02: Seed via `apps/backend/scripts/seed_demo_data.py`
- Reuse the existing demo-data seeder (already in place; mentioned in
  `apps/backend/scripts/seed_demo_data.py`). Run it once after `docker compose up -d`
  exits the `migrate` step.
- Phase 29 plan adds a thin **verification-fixture script** (not a domain change —
  a test harness only) that augments the demo data with:
  - 1 client + 1 active membership ending **today+7** (drives the 7d DM scenario).
  - 1 client + 1 active membership ending **today+3** (drives 3d DM).
  - 1 client + 1 active membership ending **today+1** (drives 1d DM).
  - 1 client + 1 active membership with full `freeze_days_limit` remaining (drives
    freeze/unfreeze/renew chain in the cross-phase smoke).
  - 1 client + 1 cancelled membership (negative path for renew error code).
- The harness lives in `apps/backend/scripts/seed_verification_fixtures.py` or
  similar — planner picks the exact name. **It is NOT loaded by demo seed**, never
  runs in CI, and is invoked only by the verification operator. Calling it `_verification.py`
  signals "throwaway-during-Phase-29" intent.

### D-29-03: Cron 06:15 — invoke directly, do NOT wait wall-clock
- The 7d/3d/1d DM scenario depends on `send_expiring_notifications` cron at 06:15 MSK
  (Phase 27). Waiting real wall-clock time is unacceptable in a verification window.
- Recipe: invoke the cron function once, in-process, against the live stack:
  ```bash
  docker compose exec backend uv run python -c "
  import asyncio
  from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications
  from app.workers import WorkerSettings
  # build ctx with sessionmaker like WorkerSettings.startup does, then await once
  asyncio.run(_run_once())
  "
  ```
- Planner writes the exact one-shot runner (mirroring Phase 27's pattern — there is
  already a test-mode invocation). Acceptable to add a small CLI entry under
  `apps/backend/scripts/run_expiring_cron_once.py` if the inline form is unwieldy;
  it is operator tooling, not production code.
- **Do NOT manipulate system clock or postgres `now()`** — fixture data uses
  real future dates relative to "today", so the cron's existing `today_msk()` call
  resolves naturally.
- `unique=True` cron guard (Phase 27 D-09) is irrelevant for the one-shot invocation
  since we bypass ARQ scheduling entirely.

### D-29-04: Telegram evidence = text logs + targeted screenshots
- Sandbox bot token + sandbox chat already live in `apps/backend/.env`
  (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_SANDBOX_CHAT_ID` per Phase 18/20/27 conventions —
  planner confirms the exact env var names from `.env.example` during the
  research/setup step).
- Operator captures evidence as:
  1. **Verbatim DM text** copy-pasted into `v1.3-VERIFICATION-LOG.md` (so future-you
     can `grep` for the locked Russian strings without opening Telegram).
  2. **Screenshot** only when the test asserts visual cues a text dump can't capture
     (e.g., FE-08 outside-hours **disabled** check-in button + alert; checked-in
     badge timestamp formatting). Stored under
     `.planning/milestones/v1.3-verification-evidence/` (new directory, planner decides
     whether to commit or `.gitignore` — RECOMMEND committing only the markdown log;
     screenshots stay local since they contain sandbox bot/user identifiers).
- Bot uses existing long-polling worker (`apps/backend/app/workers/telegram_bot.py`).
  No webhook / ngrok tunnel required for the smoke.

### D-29-05: Verification log structure — YAML frontmatter + markdown body
- File: `.planning/milestones/v1.3-VERIFICATION-LOG.md` (path locked by Roadmap SC #1).
- Format mirrors v1.2 `22-VERIFICATION.md`:
  ```yaml
  ---
  phase: 29-milestone-verification
  milestone: v1.3
  verified: <ISO-8601 UTC timestamp>
  status: passed | gaps_found | failed
  score: "<N>/<7> scenarios verified"  # 6 DEBT-04 + 1 cross-phase
  operator: andre.shipunov@icloud.com
  stack:
    backend_commit: <git rev-parse HEAD>
    backend_image: docker-compose `apps/backend` (local build)
    admin_web_mode: http
    admin_web_base: http://localhost:8000
    telegram: sandbox bot (token redacted)
  human_verification:
    - test: "DEBT-04 #1 — /memberships expiring filter against live backend"
      expected: "..."
      actual: "..."
      result: pass | fail
      evidence: "..."
      notes: "..."
    # ...one entry per DEBT-04 scenario (6 total)
    - test: "Cross-phase smoke — freeze → renewal → expiring DMs"
      ...
  test_suites:
    backend:
      command: "uv run pytest -q"
      pass_count: <int>
      fail_count: 0
      threshold: 600
      evidence_tail: |
        <last 10 lines of pytest output>
    admin_web:
      command: "pnpm --filter @sportzal/admin-web test run"
      pass_count: <int>
      fail_count: 0
      threshold: 190
      evidence_tail: |
        <last 10 lines of vitest output>
  ci_gates:
    workflow_url: <link to most recent green CI run on master>
    ruff: pass
    mypy_strict: pass
    import_linter: pass
    eslint: pass
    drift_gate_backend: pass
    drift_gate_frontend: pass
  regressions:
    - id: REG-29-01
      summary: "..."
      severity: blocker | minor
      disposition: fixed_in_<commit> | deferred_to_v1.4
  ---
  ```
- Body underneath the frontmatter: prose walk-through per scenario, paste verbatim
  Russian DM strings, screenshot file paths (relative). No new fields invented —
  if a v1.2 22-VERIFICATION frontmatter field would help (e.g., `overrides_applied`,
  `re_verified`), reuse it verbatim for consistency across milestones.

### D-29-06: Regression-handling policy (locked)
- **DEBT-04 scenario FAIL** = hard-block. Fix-or-defer requires either:
  - Fix commit in current milestone (cite SHA in `regressions[]` with
    `disposition: fixed_in_<sha>`) and **re-run that specific scenario**; OR
  - Explicit deferral to v1.4 with owner sign-off recorded in `regressions[].notes`
    and a paired DEBT entry added to `.planning/REQUIREMENTS.md` for v1.4 tracking.
- **Cross-phase smoke FAIL** = hard-block on the milestone close. No partial
  credit — the chain must work to call v1.3 done. If a specific cron-DM combination
  fails (e.g., 3d DM doesn't fire), fix-or-defer follows the same policy as above.
- **Test-suite below threshold OR new red CI gate** = hard-block. Counts below
  600/190 with green pytest/vitest are acceptable only if explicit deletion is
  documented (e.g., a test was retired and replaced 1:1). Phase 29 does NOT add
  tests to hit the threshold — the threshold is descriptive, not aspirational.
- **Minor regression discovered along the way** (cosmetic copy, non-blocking UX
  oddity that's outside any v1.3 requirement): allowed to defer to v1.4 backlog
  via `gsd add-backlog` without blocking. Record under `regressions[]` with
  `severity: minor`, `disposition: deferred_to_v1.4`.

### D-29-07: Hand-off to `/gsd-complete-milestone`
- Phase 29 deliverables stop at `v1.3-VERIFICATION-LOG.md` (committed) + STATE.md
  update + the phase's own `29-VERIFICATION.md` produced by `/gsd-verify-work`.
- After Phase 29 is marked complete in STATE.md, operator runs
  `/gsd-complete-milestone`, which authors `v1.3-MILESTONE-AUDIT.md`,
  archives `.planning/phases/24-29` into `.planning/milestones/v1.3-phases/`,
  and unblocks `/gsd-new-milestone` for v1.4. SC #4 ("Verification report подшит
  в `.planning/milestones/v1.3-MILESTONE-AUDIT.md` или эквивалентный артефакт от
  `/gsd-complete-milestone`") is satisfied by that chain — Phase 29 itself does
  not write the audit artifact.

### D-29-08: Cross-phase smoke recipe (single scenario, locked steps)
Operator executes the following steps in order against the live stack, recording
the outcome of each step in the verification log:

1. **Sell**: as owner, `POST /api/v1/memberships` with a fresh client + plan that
   has `freeze_days_limit >= 7`. Confirm 201 + membership in DB.
2. **Freeze**: `POST /memberships/{id}/freeze` (reception or owner cookie).
   Confirm `status='frozen'`, `currentFreezePeriod` open, audit event
   `membership_frozen` emitted.
3. **Wait 5 simulated days**: planner picks the simulation mechanism — recommended
   is to manually `UPDATE membership_freeze_periods SET started_at = now() - interval '5 days'`
   via `docker compose exec postgres psql` so unfreeze's day-counting logic sees a
   real 5-day delta. **NOT a code change** — direct DB poke, scoped to verification.
4. **Unfreeze**: `POST /memberships/{id}/unfreeze`. Confirm `status='active'`,
   `end_date` shifted +5 days, `freeze_days_used += 5`, audit
   `membership_unfrozen` emitted.
5. **Renew**: `POST /memberships/{id}/renew`. Confirm 201 + new membership with
   `previousMembershipId = <source>`, audit `membership_renewed` emitted.
6. **Manipulate new membership end_date**: `UPDATE memberships SET end_date = today + 7`
   via `psql` so the next cron firing has a 7d-out membership to notify on.
7. **Fire cron once**: run the one-shot invocation per D-29-03. Confirm 7d DM
   lands in sandbox chat with the locked Russian copy.
8. **Repeat steps 6+7** for `today+3` and `today+1` (`UPDATE` between firings).
   Confirm 3d and 1d DMs arrive with their distinct locked strings, and
   `unique=True` does not cause double-fire of the same window.

All eight steps must pass for the cross-phase smoke to be marked PASS.

### D-29-09: Plan order (planner discretion within these constraints)

Recommended sequencing (planner may merge plans but boundaries are load-bearing):

1. **29-01 Live stack setup recipe** — Document boot + seed + tear-down. Build the
   verification fixture script (D-29-02). No domain code touched.
2. **29-02 DEBT-04 scenario execution** — Run 6 scenarios from `22-VERIFICATION.md`
   `human_verification:` block; record results inline into a working draft of
   `v1.3-VERIFICATION-LOG.md`.
3. **29-03 Cross-phase smoke** — Execute the 8-step recipe from D-29-08; record
   pass/fail per step.
4. **29-04 Test suite + CI gate evidence capture** — Run pytest + vitest, paste
   tails into the log; link the latest green CI run URL.
5. **29-05 Final `v1.3-VERIFICATION-LOG.md`** — Consolidate; resolve `regressions[]`
   classification with owner sign-off; commit.
6. **29-06 Hand-off** — Update STATE.md, mark phase complete via `/gsd-verify-work`,
   produce `29-VERIFICATION.md`; instruct operator to run `/gsd-complete-milestone`
   as the next step (NOT part of Phase 29 itself per D-29-07).

### Claude's Discretion (planner picks)
- Exact filename for the verification fixture script under `apps/backend/scripts/`.
- Exact one-shot cron runner form (inline `python -c` vs new
  `scripts/run_expiring_cron_once.py`) — pick whichever produces less surface area.
- Whether to commit the screenshot evidence directory to git or `.gitignore` it.
- Exact field order inside the `human_verification:` frontmatter — match v1.2 as
  closely as possible but minor field additions (e.g., `evidence_path`) are fine
  if they clarify operator workflow.
- Sequencing of DEBT-04 scenarios: order in the source block is recommended; reordering
  is acceptable if it minimises context-switching (e.g., grouping the two profile/sessions
  scenarios together).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements (locked scope)
- `.planning/ROADMAP.md` §"Phase 29: Milestone Verification" (lines 157–166) — 4
  success criteria + Depends-on Phase 28.
- `.planning/milestones/v1.3-ROADMAP.md` lines 84–93 — milestone-level mirror of
  Phase 29 success criteria.
- `.planning/REQUIREMENTS.md` line 20 — DEBT-04 acceptance text; line 144 (status
  Pending → Phase 29); line 155 (DEBT-04 mapping).
- `.planning/PROJECT.md` §"Tech-Debt Carry-Forward" line 32 —
  "22-VERIFICATION human_verification — 6 smoke tests прогнать через live backend +
  Telegram sandbox в рамках milestone verification."

### Source of the 6 DEBT-04 scenarios
- `.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-VERIFICATION.md`
  `human_verification:` block (lines ~71–89 in the pre-archive snapshot —
  file was archived in commit `29d3234` when v1.3 milestone started; current
  on-disk copy is now under
  `.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/`
  ONLY in git history. Planner MUST resurrect the block verbatim — quote it inside
  `29-CONTEXT.md` consumers' working notes — by running:
  ```bash
  git show 29d3234^:.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-VERIFICATION.md
  ```
  Six scenarios in summary form (full expected/why_human prose in the git-history
  copy):
  1. `/memberships` "Истекают через 7 дней" filter in mock mode (operator-acceptance
     check on WR-07 no-op behaviour).
  2. `/clients` row-click navigates to `/clients/$clientId` while inline Pencil/Trash2
     don't trigger row navigation.
  3. Live `/auth/sessions` flow as **owner** — list, revoke non-current, logout-all
     (FE-09 http-only ship per D-22-2).
  4. Same `/profile` flow as **reception** (both-roles routing decision).
  5. Live `/visits` flow — phone-prefix search → select client → FE-08(a..d) edges
     (top-5 disambiguation, already-checked-in badge HH:MM, expires-today informational
     badge, outside-hours disable + tooltip + alert via `/api/v1/visits/_meta`).
  6. Self-checkin via Telegram bot (sandbox) — DM copy locked by D-22-11:
     - N>0 days: `✅ Отмечено. Абонемент действует ещё N дн.`
     - 0 days: `✅ Отмечено. Сегодня — последний день абонемента.`

### Live stack + worker entry points (no edits — read-only)
- `apps/backend/docker-compose.yml` — boot recipe; services
  `backend`, `telegram-bot`, `arq-worker`, `migrate`, `postgres`, `redis`.
- `apps/backend/.env.example` — env vars list (DB url, Redis url, Telegram bot
  token + sandbox chat id; planner confirms exact names).
- `apps/backend/app/workers/__init__.py` lines 57–107 — `WorkerSettings`,
  `cron_jobs` list with `expire_memberships` (06:05 MSK) and
  `send_expiring_notifications` (06:15 MSK).
- `apps/backend/app/workers/scheduled/send_expiring_notifications.py` — Phase 27
  job; planner inspects to design the one-shot invocation (D-29-03).
- `apps/backend/app/workers/scheduled/expire_memberships.py` — Phase 24 job; also
  one-shot-invokable for the cross-phase recipe (D-29-08).
- `apps/backend/app/workers/telegram_bot.py` — long-polling worker; sandbox bot
  identity comes from env.
- `apps/backend/scripts/seed_demo_data.py` — base seeder; verification fixtures
  layer on top.

### Backend endpoints under smoke
- `apps/backend/app/modules/memberships/router.py` — freeze / unfreeze / renew /
  expiring list endpoints (Phases 24/25/26).
- `apps/backend/app/modules/visits/router.py` — `/_meta` + check-in (Phase 22 FE-08
  edge cases).
- `apps/backend/app/modules/auth/router.py` — `/auth/sessions` GET + revoke + logout-all
  (FE-09).
- `apps/backend/app/integrations/telegram/handlers.py` — `/checkin` DM strings
  (`_DM_CHECKIN_OK_WITH_DAYS`, `_DM_CHECKIN_OK_LAST_DAY`) + expiring DMs
  (`_DM_EXPIRING_*` per Phase 27 NTF-COPY-01).

### Frontend surface under smoke
- `apps/admin-web/src/routes/_protected/memberships.tsx` — list + status filter +
  expiring within selector (Phase 28 wiring).
- `apps/admin-web/src/routes/_protected/clients.tsx` + `clients_.$clientId.tsx`
  — row-click navigation pattern (DEBT-04 #2).
- `apps/admin-web/src/routes/_protected/visits.tsx` — `/visits` check-in page
  (DEBT-04 #5).
- `apps/admin-web/src/routes/_protected/profile.tsx` + `features/auth/components/SessionsList.tsx`
  + `LogoutAllDialog.tsx` (DEBT-04 #3, #4).
- `apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx` — freeze /
  unfreeze / renew action surface (Phase 28; consumed by cross-phase smoke).

### CI gates (must stay green)
- `.github/workflows/ci.yml` — backend lint/typecheck/tests (ruff, mypy strict,
  import-linter, pytest, drift-gate lines 49–64) + frontend lint/typecheck/tests
  (eslint, vitest, drift-gate lines 100–117).
- `apps/backend/.importlinter` — module boundary contract.
- `apps/admin-web/eslint.config.js` — import-boundary + raw-palette + VITE_API_MODE
  chokepoint.

### Carry-forward phase decisions
- `.planning/phases/24-foundations-tech-debt-bedrock/24-CONTEXT.md` — DEBT-02
  expiring/within semantics (DEBT-04 #1 source).
- `.planning/phases/25-memberships-freeze-backend/25-CONTEXT.md` — freeze semantics
  + `freeze_days_used` arithmetic (cross-phase step 2-4).
- `.planning/phases/26-memberships-renewal-backend/26-CONTEXT.md` — renewal
  chain + `previousMembershipId` (cross-phase step 5).
- `.planning/phases/27-expiring-soon-telegram-notifications/27-CONTEXT.md` —
  06:15 cron + locked DM Russian copy (cross-phase steps 6-8).
- `.planning/phases/28-openapi-drift-gate-refresh-admin-web-wiring/28-CONTEXT.md`
  §D-28-01..16 — admin-web wiring shipping in this milestone; verification confirms
  it works against live backend.
- `.planning/milestones/v1.2-MILESTONE-AUDIT.md` lines 60–80 — original DEBT-04
  deferral context.

### Verification log location (locked by Roadmap SC #1)
- `.planning/milestones/v1.3-VERIFICATION-LOG.md` — Phase 29's primary output.
  Does not exist yet; will be created during Phase 29 execution. Frontmatter shape
  per D-29-05 (mirrors v1.2 22-VERIFICATION.md).

### Audit artifact (locked by Roadmap SC #4, written outside Phase 29)
- `.planning/milestones/v1.3-MILESTONE-AUDIT.md` — produced by
  `/gsd-complete-milestone` AFTER Phase 29 completes. Phase 29 itself does NOT
  write this file.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/backend/docker-compose.yml` — full live stack in one file; no orchestration
  to invent.
- `apps/backend/scripts/seed_demo_data.py` — base seeder; extend with a sibling
  verification-fixture script rather than mutating it.
- `apps/backend/scripts/export_openapi.py` — pattern for "operator CLI under
  `scripts/`" (no top-level entry-point boilerplate; just `python -m
  scripts.<name>`).
- `apps/backend/app/workers/__init__.py:57-107` — WorkerSettings includes
  startup/shutdown lifecycle and the `cron_jobs` list; the one-shot cron
  invocation reuses the same `ctx['sessionmaker']` setup.
- `apps/backend/app/integrations/telegram/sender.py` — already configured for
  sandbox chat via env; no test-double substitution needed.
- v1.2 `22-VERIFICATION.md` frontmatter shape (git history) — proven schema for
  the verification log; reuse field names verbatim.

### Established Patterns
- **Operator scripts live under `apps/backend/scripts/`** and are invoked with
  `uv run python -m scripts.<name>` (e.g., `export_openapi`, `seed_demo_data`).
  Verification fixture + one-shot cron runner follow the same convention.
- **Bot DM strings are Python constants** (`_DM_*` in `handlers.py` /
  `tasks/expiring.py`); verification asserts exact-string equality, not regex
  matches, so the strings can be grep'd from `v1.3-VERIFICATION-LOG.md` later.
- **Cron job functions are plain `async def` callables** that accept `ctx` — they
  can be invoked outside ARQ for one-shot smoke runs (Phase 27 tests already use
  this pattern).
- **DB-level fixtures via `docker compose exec postgres psql`** is acceptable
  for verification-time data manipulation (cross-phase smoke step 3, 6 in
  D-29-08). It is **not** a production pattern.

### Integration Points
- No code under `app/` is edited by Phase 29 (verification phase, not
  implementation). Only `apps/backend/scripts/` may gain new files (D-29-02,
  D-29-03 one-shot runner).
- `.planning/milestones/v1.3-VERIFICATION-LOG.md` is the lone produced artifact
  inside `.planning/`; all phase-level work also writes
  `.planning/phases/29-milestone-verification/*.md` (PLAN/SUMMARY/VERIFICATION
  per GSD conventions).
- `/gsd-complete-milestone` is the consumer of Phase 29's output — its prompt
  reads `v1.3-VERIFICATION-LOG.md` to populate `v1.3-MILESTONE-AUDIT.md`.

</code_context>

<specifics>
## Specific Ideas

- Verification log shape mirrors v1.2's `22-VERIFICATION.md` frontmatter — same
  field names, same `human_verification:` array structure, same `overrides_applied`
  / `re_verified` convention if regressions need a fix-commit citation. Reuse
  beats reinvention.
- Cron 06:15 is invoked **directly**, never wall-clock-waited; the worker code
  is plain `async def` and accepts a `ctx` dict, so the smoke recipe can build
  that ctx in 10 lines and `await` once per window. Don't simulate the clock;
  manipulate the data (`UPDATE memberships SET end_date = today + N`) and let
  the cron's natural `today_msk()` call resolve.
- DB pokes via `psql` during the cross-phase smoke are acceptable BECAUSE this
  is verification — no code path is being tested for those rows being
  app-generated; we're testing the downstream side effects (DMs, audit events).
- Screenshot evidence stays local; only the markdown log is committed. Sandbox
  bot / chat identifiers leak otherwise.
- Owner sign-off (andre.shipunov@icloud.com) is recorded in the log frontmatter
  `operator:` field — one human, one signature, one milestone close.

</specifics>

<deferred>
## Deferred Ideas

- **Automated end-to-end smoke (Playwright + bot mock)** — current Phase 29 is
  manual operator-driven; a future milestone may invest in a recorded automated
  variant to keep verification cheap as the surface grows.
- **Staging environment + verification against it** — Phase 29 verifies against
  developer docker-compose only. A real staging deploy + verification routine
  is post-v1.0-launch infrastructure work.
- **Production telemetry-backed verification** — once metrics/logging are in
  place (post-v1.4), regressions might be caught by alerting rather than smoke
  tests. Not in scope for v1.3 close.
- **Migration of v1.2 22-VERIFICATION pre-archive copy out of git history** — the
  current arrangement requires `git show 29d3234^:...` to read the source
  scenarios. A future bookkeeping pass could lift those scenarios into a
  permanent doc (e.g., `.planning/milestones/v1.2-phases/22-VERIFICATION.md`)
  so future verification phases don't depend on git archaeology.
- **`/gsd-complete-milestone` execution** — explicitly handed off (D-29-07);
  belongs in its own session after Phase 29 commits its log.

</deferred>

---

*Phase: 29-milestone-verification*
*Context gathered: 2026-05-14 (mode `--auto` — review before planning)*
