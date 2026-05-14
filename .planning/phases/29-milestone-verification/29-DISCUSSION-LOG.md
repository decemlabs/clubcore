# Phase 29: Milestone Verification — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `29-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 29-milestone-verification
**Mode:** `--auto` — Claude picked the recommended option for every gray area; no interactive prompts were issued. Review and adjust `29-CONTEXT.md` before planning if any default is wrong.
**Areas discussed:** Live stack mechanism, Verification fixtures, Cron-firing approach, Telegram evidence capture, Verification log structure, Regression-handling policy, Milestone audit hand-off, Cross-phase smoke recipe

---

## Live stack mechanism (how do we boot the "live backend")

| Option | Description | Selected |
|--------|-------------|----------|
| `docker compose up` from `apps/backend/` | Reuse existing `docker-compose.yml` — backend + telegram-bot + arq-worker + postgres + redis in one command | ✓ |
| Local `uv run uvicorn` + manually started Postgres/Redis | More flexibility for fast iteration; more setup pain | |
| Deploy to a staging environment | Closer to prod; introduces deployment infrastructure as new dep | |

**Auto-selected:** `docker compose` from `apps/backend/`.
**Notes:** No new tooling. Tear down with `docker compose down -v` after verification so fixtures don't bleed into next milestone. Explicit deviation from prod parity — single-host verification only.

---

## Verification fixtures (how do we seed the data)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `seed_demo_data.py` with verification rows | Single seed entry-point; risks mixing demo-time and verification-time data | |
| Add a sibling `seed_verification_fixtures.py` invoked manually | Clear "operator-only" boundary; demo seeder stays unchanged | ✓ |
| Manual `psql` inserts only | Lightest; brittle and not repeatable | |

**Auto-selected:** sibling verification-fixture script.
**Notes:** Lives under `apps/backend/scripts/`; planner picks the exact filename. NOT invoked by CI or `seed_demo_data`. Adds: client+membership rows for 7d/3d/1d cron windows + a freeze-able active membership + a cancelled membership for negative path.

---

## Cron-firing approach (how do we exercise the 06:15 worker)

| Option | Description | Selected |
|--------|-------------|----------|
| Wait wall-clock until 06:15 MSK | Most natural; impossible during a verification window | |
| Set system clock / fake `now()` in DB | Brittle; risks polluting other workers/audit timestamps | |
| Invoke the cron `async def` one-shot via `docker compose exec backend uv run python -c ...` | Reuses production code path; instant; no time manipulation needed | ✓ |
| Manipulate data so the cron's natural `today_msk()` matches the window | Used jointly with one-shot invocation (data-side, not clock-side) | ✓ (paired) |

**Auto-selected:** one-shot invocation + data manipulation.
**Notes:** Phase 27's cron is a plain `async def f(ctx)` — buildable ctx outside ARQ. `unique=True` cron guard is irrelevant for the one-shot. Planner may extract this into `scripts/run_expiring_cron_once.py` if inline form is awkward.

---

## Telegram evidence capture (what proves a DM arrived)

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim text of received DMs pasted into the log | Greppable; preserves the exact locked Russian strings | ✓ |
| Screenshots only | Heavier; not greppable; leaks bot/user identifiers | |
| Webhook intercept / mock bot | Departs from "live Telegram sandbox" semantics required by SC #1 | |
| Hybrid: text logs + targeted screenshots where visual cues matter (FE-08 disable + alert) | Best of both | ✓ |

**Auto-selected:** verbatim text + targeted screenshots.
**Notes:** Screenshots committed only as relative paths if at all; recommend keeping them local (sandbox bot ID privacy). Markdown log committed.

---

## Verification log structure (what shape does `v1.3-VERIFICATION-LOG.md` take)

| Option | Description | Selected |
|--------|-------------|----------|
| Prose markdown only | Light; hard to machine-process and easy to miss fields | |
| YAML frontmatter mirroring v1.2 `22-VERIFICATION.md` + markdown body | Proven schema; greppable; same field names across milestones | ✓ |
| JSON / structured-only output | Machine-friendly but harder to skim during a sign-off review | |

**Auto-selected:** YAML frontmatter (v1.2 shape) + markdown body.
**Notes:** Reuse `human_verification:`, `overrides_applied`, `re_verified` field names verbatim. Add `test_suites`, `ci_gates`, `regressions[]` sections per D-29-05.

---

## Regression-handling policy (what happens when a scenario fails)

| Option | Description | Selected |
|--------|-------------|----------|
| Any FAIL hard-blocks milestone close | Safest; potentially expensive if a minor cosmetic issue stalls v1.3 ship | |
| DEBT-04 FAIL + cross-phase FAIL hard-block; minor visual regressions may defer to v1.4 backlog | Lets owner decide; explicit `regressions[].disposition` field in the log captures intent | ✓ |
| All regressions auto-defer to v1.4 | Defeats the purpose of verification | |

**Auto-selected:** stratified policy (DEBT-04 + cross-phase hard-block; minor non-requirement issues deferrable).
**Notes:** Each regression entry needs `severity`, `disposition`, and (if fixed) commit SHA. Re-run the failed scenario after a fix commit before flipping `status: passed`.

---

## Milestone audit hand-off (who writes `v1.3-MILESTONE-AUDIT.md`)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 29 writes both `v1.3-VERIFICATION-LOG.md` AND `v1.3-MILESTONE-AUDIT.md` | Single phase, single hand-off; duplicates `/gsd-complete-milestone` work | |
| Phase 29 writes only the log; `/gsd-complete-milestone` writes the audit afterwards | Reuses the dedicated GSD command; SC #4 "или эквивалентный артефакт" explicitly allows this | ✓ |
| Skip the audit artifact entirely | Violates SC #4 | |

**Auto-selected:** log-only in Phase 29 + audit produced by `/gsd-complete-milestone` post-phase.
**Notes:** Operator runs `/gsd-complete-milestone` as the **next** GSD command after Phase 29 closes. Phase 29's own `29-VERIFICATION.md` is produced by `/gsd-verify-work` per the standard GSD flow.

---

## Cross-phase smoke recipe (how do we exercise freeze → renewal → expiring)

| Option | Description | Selected |
|--------|-------------|----------|
| Free-form operator improvisation | Fast but irreproducible | |
| 8-step locked recipe (sell → freeze → 5d simulate → unfreeze → renew → set end_date → fire cron 7d → repeat for 3d/1d) | Reproducible; matches Roadmap SC #2 verbatim | ✓ |
| Multiple parallel scenarios covering each feature in isolation | Loses the "cross-phase chain" semantics SC #2 requires | |

**Auto-selected:** 8-step locked recipe per D-29-08.
**Notes:** "5-day simulation" uses a direct `UPDATE membership_freeze_periods SET started_at = now() - interval '5 days'` — verification-time data manipulation, NOT a code path being tested.

---

## Claude's Discretion

- Exact verification-fixture script filename under `apps/backend/scripts/`.
- Whether the one-shot cron runner is inline `python -c` or a new `scripts/run_expiring_cron_once.py`.
- Whether to commit screenshot evidence to git or `.gitignore` it (default: do not commit).
- Final field ordering inside the `human_verification:` frontmatter (match v1.2 22-VERIFICATION as closely as possible).
- DEBT-04 scenario execution order (source order recommended; reordering acceptable to minimise context switching).

## Deferred Ideas

- Automated end-to-end smoke (Playwright + bot mock) — future milestone investment.
- Staging environment + verification against it — post-v1.0 infrastructure work.
- Telemetry-backed verification (alerting catches regressions) — post-v1.4.
- Lift v1.2 22-VERIFICATION pre-archive scenarios out of git history into a permanent doc — bookkeeping pass for a future cleanup phase.
- `/gsd-complete-milestone` execution — handed off post-Phase-29; belongs in its own session.
