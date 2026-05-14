# Phase 29: Milestone Verification — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 3 produced files (1 mandatory script, 1 optional script, 1 milestone log) + 1 evidence dir
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/scripts/seed_verification_fixtures.py` | operator-CLI script (verification fixture seeder) | batch / one-shot DB write | `apps/backend/scripts/seed_demo_data.py` | exact (same `python -m scripts.<name>` invocation, same async-session lifecycle, same `_run() -> int` shape) |
| `apps/backend/scripts/run_expiring_cron_once.py` (optional — D-29-03 Claude's-discretion) | operator-CLI script (one-shot cron runner) | request-response (in-process invocation of an ARQ cron callable) | `apps/backend/scripts/export_openapi.py` (CLI shape) + `apps/backend/app/workers/__init__.py` lines 105–141 (`on_startup` / `ctx` construction) | role-match (CLI shape exact; runtime semantics partially borrowed — needs hybrid pattern) |
| `.planning/milestones/v1.3-VERIFICATION-LOG.md` | milestone-level verification artifact | static markdown with YAML frontmatter | v1.2 `22-VERIFICATION.md` (git history at `29d3234^`) | exact (per D-29-05 — same field names, same `human_verification:` shape, same `overrides_applied` / `re_verified` convention) |
| `.planning/milestones/v1.3-verification-evidence/` | local-only screenshot evidence dir | filesystem only (NOT committed per D-29-04) | none (new directory) | n/a — directory, not a file |

Phase 29 produces **no** application code under `apps/backend/app/` or `apps/admin-web/src/`. Two `scripts/` files + one milestone markdown + one evidence dir are the entire surface.

---

## Pattern Assignments

### `apps/backend/scripts/seed_verification_fixtures.py` (operator-CLI script, batch DB write)

**Analog:** `apps/backend/scripts/seed_demo_data.py`

**Why this analog:** Same invocation surface (`uv run python -m scripts.<name>`), same async-session lifecycle, same module-level entry-point convention (`async def _run() -> int`, sync `main()` wrapper, `raise SystemExit(main())`), and explicitly cited in D-29-02 as the script to layer on top of.

**Module-docstring pattern** (lines 1–14):
```python
"""Seed the bootstrap owner (AUTH-EP-04 / D-25).

Idempotent: INSERT ... ON CONFLICT (email) DO NOTHING. Re-running the script
after the owner exists is a no-op. The compose stack does NOT auto-run this —
it is a one-shot operator command:

    uv run python -m scripts.seed_demo_data

Reads SEED_OWNER_EMAIL + SEED_OWNER_PASSWORD from the environment. Both must
be set; otherwise the script exits 1 with a clear message.

The created owner has full_name='Owner' (D-01: single column). Operators can
update it via a future admin endpoint or `psql` once the owner has logged in.
"""
```

**Async-session lifecycle pattern** (lines 16–24, 32–35, 50–88):
```python
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
# ...domain imports (models / enums) below


async def _run() -> int:
    # ...env-var validation (return 1 on missing) — Phase 29 fixture script
    # validates that the demo-data seeder has run first (e.g. owner exists,
    # plans exist) before layering verification rows on top.

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            # ...build rows, await session.execute(...), await session.commit()
            print(f"Seeded verification fixtures: <summary>.")
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
```

**Idempotency pattern** (lines 56–66):
```python
stmt = (
    pg_insert(User)
    .values(
        email=email_lower,
        password_hash=await hash_password(password),
        role=Role.OWNER.value,
        full_name="Owner",
    )
    .on_conflict_do_nothing(index_elements=["email"])
)
await session.execute(stmt)
await session.commit()
```

**What to change vs. the analog:**
- Filename: `seed_verification_fixtures.py` (suffix `_verification` signals "throwaway-during-Phase-29" intent per D-29-02).
- `_run()` body loads **5 memberships** at deterministic offsets relative to "today" (Europe/Moscow):
  - 1 client + 1 active membership ending `today + 7` → drives 7d DM scenario.
  - 1 client + 1 active membership ending `today + 3` → drives 3d DM scenario.
  - 1 client + 1 active membership ending `today + 1` → drives 1d DM scenario.
  - 1 client + 1 active membership with full `freeze_days_limit_snapshot` remaining → drives freeze/unfreeze/renew chain in the cross-phase smoke.
  - 1 client + 1 cancelled membership → negative path for renew error code.
- Idempotency: use `on_conflict_do_nothing` keyed on the deterministic fixture email/phone (e.g. `verify_7d@fixture.local`) so re-runs are no-ops.
- Print a single-line summary on success: `Seeded verification fixtures: 5 clients, 5 memberships (3 expiring, 1 active-freezable, 1 cancelled).`
- Module docstring explicitly states **"NOT loaded by demo seed, never runs in CI, invoked only by the verification operator"** (D-29-02).

**Constraints inherited from the analog:**
- No top-level imports of `app.modules.*` other than what the seeder strictly needs (clients, memberships models — already-allowed imports from `seed_demo_data.py`).
- `async_sessionmaker(engine, expire_on_commit=False)` is the locked construction shape.
- `await engine.dispose()` MUST run in a `finally` block.
- The script must be a no-op on re-run (idempotent insert).
- No edits to `app/` — script only.

---

### `apps/backend/scripts/run_expiring_cron_once.py` (operator-CLI script, in-process cron invocation — OPTIONAL per D-29-03)

**Analog (CLI shape):** `apps/backend/scripts/export_openapi.py`
**Analog (runtime semantics):** `apps/backend/app/workers/__init__.py` lines 105–141 (`WorkerSettings.on_startup` and `ctx` construction)

**Why these two analogs:** D-29-03 allows either inline `docker compose exec backend uv run python -c "..."` OR a thin operator script. If the planner chooses the script, it must (a) follow the `scripts/` CLI convention (`export_openapi` is the cleanest analog — no env-var ceremony, just `main() -> int`) AND (b) replicate the `ctx['sessionmaker']` construction that `WorkerSettings.on_startup` performs, because the cron callable signature is `async def send_expiring_notifications(ctx: dict[str, Any]) -> int` and reads `ctx["sessionmaker"]`.

**CLI shape pattern** (from `export_openapi.py` lines 21–31, 49–71):
```python
from __future__ import annotations

import asyncio
import sys

# `from app.*` imports come AFTER any env-var setdefault block (Phase 9 D-04
# pattern). For run_expiring_cron_once the cron callable + worker module
# both expect a real DB + real Telegram bot token in env — those come from
# .env / docker compose, not from setdefault placeholders.
from app.workers import WorkerSettings
from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications


def main() -> int:
    # ...build ctx with sessionmaker via WorkerSettings.on_startup,
    # await send_expiring_notifications(ctx), then WorkerSettings.on_shutdown.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**`ctx` construction pattern** (from `app/workers/__init__.py` lines 105–141):
```python
@staticmethod
async def on_startup(ctx: dict[str, Any]) -> None:
    """Open DB lifespan + stash stack in ctx + run cron-resolution invariant."""
    function_names = {f.__name__ for f in WorkerSettings.functions}
    cron_function_names = {c.coroutine.__name__ for c in WorkerSettings.cron_jobs}
    unresolved = cron_function_names - function_names
    assert not unresolved, (
        f"cron_jobs reference function names not in WorkerSettings.functions: "
        f"{sorted(unresolved)}. ..."
    )

    stack = AsyncExitStack()
    engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
    ctx["_db_stack"] = stack
    ctx["engine"] = engine
    ctx["sessionmaker"] = sessionmaker
    _log.info("worker_startup_complete", function_count=len(function_names))

@staticmethod
async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Close the AsyncExitStack stored in ctx — disposes engine + sessionmaker."""
    stack: AsyncExitStack | None = ctx.get("_db_stack")
    if stack is not None:
        await stack.aclose()
```

**Cron-callable signature pattern** (from `app/workers/scheduled/send_expiring_notifications.py` lines 41–55):
```python
async def send_expiring_notifications(ctx: dict[str, Any]) -> int:
    """Send 7d/3d/1d expiring-soon DMs; return count of successful sends.

    Args:
        ctx: ARQ job context. Required keys:
            - ctx["sessionmaker"]: `async_sessionmaker[AsyncSession]` populated
              by `WorkerSettings.on_startup` ...
    """
    session_factory = ctx["sessionmaker"]
    # ...
```

**What to change vs. the analogs:**
- Hybrid pattern: CLI shape from `export_openapi`, runtime semantics from `WorkerSettings`. The script's `async def _run()`:
  1. Builds a `ctx: dict[str, Any] = {}`.
  2. Calls `await WorkerSettings.on_startup(ctx)` — this reuses the locked startup logic, including the cron-resolution invariant assertion. **DO NOT duplicate the `ctx["sessionmaker"]` setup inline — call the staticmethod.**
  3. Calls `await send_expiring_notifications(ctx)` once and captures the returned count.
  4. Calls `await WorkerSettings.on_shutdown(ctx)` in a `finally` block.
  5. Prints `Fired send_expiring_notifications once: count=<N>`.
- The cron's `unique=True` guard does NOT apply here (D-29-03) — we bypass ARQ scheduling entirely by calling the coroutine directly.
- **No clock manipulation** (D-29-03): the script does not touch system time; the cron's `today_msk()` resolves naturally against fixture rows whose `end_date` was set via direct `psql` UPDATE prior to invocation.
- The script may also be parameterised (CLI arg `--job expire_memberships|send_expiring_notifications`) so the same runner can fire either cron — Phase 29 only NEEDS `send_expiring_notifications`, but `expire_memberships` is useful for the cross-phase smoke if `end_date` flip needs an explicit expiration tick. Planner discretion.
- If the planner instead chooses the inline `python -c` form (D-29-03 first option), this file is NOT created — the inline command goes into the plan's action block verbatim. **Prefer the script** because the inline form duplicates the `WorkerSettings.on_startup` logic in a heredoc, which is fragile and uncopyable. The script is one file, one import, one call.

**Constraints inherited from the analogs:**
- `import` order: `from __future__ import annotations` first, stdlib next, `app.*` last. No `app.*` import before module-level env-var prep (if any).
- `_run()` returns `int`; `main()` wraps `asyncio.run(_run())`; `if __name__ == "__main__": raise SystemExit(main())`.
- The cron callable contract (`ctx["sessionmaker"]` required) is fixed — the runner MUST provide it via `WorkerSettings.on_startup`, not by re-implementing `db_lifespan_manager()` inline.
- No edits to `app/workers/__init__.py` or `app/workers/scheduled/send_expiring_notifications.py` — they are read-only for Phase 29.

---

### `.planning/milestones/v1.3-VERIFICATION-LOG.md` (milestone-level verification artifact)

**Analog:** v1.2 `22-VERIFICATION.md` — resurrect via:
```bash
git show 29d3234^:.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-VERIFICATION.md
```

**Why this analog:** D-29-05 explicitly mandates "Format mirrors v1.2 22-VERIFICATION.md". Same field names, same `human_verification:` array shape, same `overrides_applied` / `re_verified` convention. Reuse beats reinvention.

**Exact YAML frontmatter field order** (from the resurrected v1.2 file — copy this field order; do not re-order):
```yaml
---
phase: 29-milestone-verification
milestone: v1.3
verified: <ISO-8601 UTC timestamp>            # e.g. "2026-05-14T18:30:00Z"
re_verified: <ISO-8601 UTC timestamp>         # OPTIONAL — present only if a regression
                                              #   was fixed mid-phase and the scenario re-run
status: passed | gaps_found | failed
score: "<N>/7 scenarios verified"             # 6 DEBT-04 + 1 cross-phase smoke
overrides_applied: <int>                      # count of regression fixes cited in `overrides:`
overrides:                                    # OPTIONAL — one entry per fix-commit citation
  - gap: <regression-id, e.g. REG-29-01>
    resolved_in: "<git-sha> — <commit subject line>"
    evidence: "<one-sentence prose pointing at the changed code>"
gaps_resolved:                                # OPTIONAL — mirrors v1.2 "truth/status/resolution/reason/artifacts/missing" shape
  - truth: "<one-sentence Observable Truth>"
    status: resolved
    resolution: "<commit-sha> citation + one-sentence outcome"
    reason: "<diagnostic paragraph>"
    artifacts:
      - path: "<repo-relative file path>"
        issue: "<what was wrong>"
    missing:
      - "<what was changed to close the gap>"
human_verification:
  - test: "DEBT-04 #1 — /memberships expiring filter against live backend"
    expected: "<exactly what should happen, verbatim where applicable>"
    actual: "<what the operator observed>"
    result: pass | fail
    evidence: "<verbatim DM text OR path under .planning/milestones/v1.3-verification-evidence/>"
    notes: "<optional operator commentary>"
  # ...one entry per DEBT-04 scenario (6 total)
  - test: "Cross-phase smoke — sell -> freeze 5d -> unfreeze -> renew -> 7d/3d/1d DMs"
    expected: "..."
    actual: "..."
    result: pass | fail
    evidence: "..."
    notes: "<step-by-step pass/fail per D-29-08 sub-step 1..8>"
test_suites:
  backend:
    command: "uv run pytest -q"
    pass_count: <int>
    fail_count: 0
    threshold: 600
    evidence_tail: |
      <last 10 lines of pytest output, verbatim>
  admin_web:
    command: "pnpm --filter @sportzal/admin-web test run"
    pass_count: <int>
    fail_count: 0
    threshold: 190
    evidence_tail: |
      <last 10 lines of vitest output, verbatim>
ci_gates:
  workflow_url: <link to most recent green CI run on master>
  ruff: pass
  mypy_strict: pass
  import_linter: pass
  eslint: pass
  drift_gate_backend: pass
  drift_gate_frontend: pass
stack:
  backend_commit: <git rev-parse HEAD>
  backend_image: docker-compose `apps/backend` (local build)
  admin_web_mode: http
  admin_web_base: http://localhost:8000
  telegram: sandbox bot (token redacted)
regressions:
  - id: REG-29-01
    summary: "<one-sentence regression description>"
    severity: blocker | minor
    disposition: fixed_in_<commit-sha> | deferred_to_v1.4
    notes: "<owner sign-off rationale if deferred>"
operator: andre.shipunov@icloud.com
---
```

**v1.2 frontmatter field order (verbatim, for cross-reference):**
- `phase`, `verified`, `re_verified`, `status`, `score`, `overrides_applied`, `overrides:[...]`, `gaps_resolved:[...]`, `human_verification:[...]`.
- v1.2 does NOT have `milestone:` / `test_suites:` / `ci_gates:` / `stack:` / `regressions:` / `operator:` fields — those are **new in v1.3** per D-29-05. Place them after `human_verification:` in the order shown above so the v1.2 prefix stays untouched. This minimises diff against v1.2 for future grep / template-reuse.

**Body pattern** (from v1.2 22-VERIFICATION.md after the frontmatter — observed at line ~94 onwards):
```markdown
# Phase 22: admin-web wiring — memberships + visits + active sessions UI Verification Report

**Phase Goal:** "An owner/reception user can do the full v1.2 flow end-to-end ..."

**Verified:** 2026-05-08T17:45:00Z
**Re-verified:** 2026-05-08T16:23:17Z — all four BLK gaps closed via code-review-fix round 2 + UAT inline fix
**Status:** passed (was: gaps_found at initial verification)
**Re-verification:** Yes — overrides applied for BLK-01..04 with fix-commit citations

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria + plan must_haves)

| #   | Truth                                                                           | Status     | Evidence  |
| --- | ------------------------------------------------------------------------------- | ---------- | --------- |
| 1   | ...                                                                             | ✓ VERIFIED | ...       |
```

**What to change vs. the analog:**
- Header: `# v1.3 Milestone Verification Log` (not phase-level).
- **Milestone Goal**: paste from `.planning/milestones/v1.3-ROADMAP.md` top section.
- **Verified / Re-verified**: ISO-8601 UTC timestamps captured at write time.
- Drop the v1.2 "Observable Truths" table shape — Phase 29 verifies milestone-level success criteria, not phase-level truths. Replace with a **Scenarios** section that walks the 6 DEBT-04 entries + the 1 cross-phase smoke in order, each with: scenario heading, expected vs. actual prose, verbatim Russian DM strings inline (NOT linked) for the Telegram-related scenarios, screenshot file paths (relative — `./v1.3-verification-evidence/<name>.png`) where applicable.
- For each Telegram DM in a scenario's prose: paste the **exact** Russian string from `apps/backend/app/integrations/telegram/handlers.py` (`_DM_CHECKIN_OK_WITH_DAYS`, `_DM_CHECKIN_OK_LAST_DAY`) or `apps/backend/app/integrations/telegram/copy.py` (`EXPIRING_7D_VARIANT_A/B`, `EXPIRING_3D_VARIANT_A/B`, `EXPIRING_1D_VARIANT_A/B`) so the log is grep-able for the locked copy without opening Telegram.
- Body must include a final **"Hand-off"** section per D-29-07 that explicitly says: "Phase 29 stops here. Operator next runs `/gsd-complete-milestone` to produce `v1.3-MILESTONE-AUDIT.md`."

**Constraints inherited from the analog:**
- YAML frontmatter is the source-of-truth for machine-readable verification state; the body is human-readable elaboration.
- All field names are stable across milestones — do not rename `human_verification`, `overrides_applied`, `re_verified`, `gaps_resolved`. Adding fields is fine; renaming locks future grep tooling out.
- Verbatim copy strings are quoted inside the markdown (not paraphrased) so cross-version diffs catch copy regressions.
- Owner sign-off (single email in `operator:`) is one human, one signature, one milestone close.

---

### `.planning/milestones/v1.3-verification-evidence/` (local-only evidence dir)

**Analog:** none (new directory introduced by Phase 29 per D-29-04).

**Why no analog:** v1.2's 22-VERIFICATION.md kept all evidence inline (commit SHAs, code excerpts) — no separate evidence dir was created. Phase 29 adds the directory specifically to host screenshots that can't be captured as text (FE-08 outside-hours visual state, checked-in badge timestamp formatting).

**What to put in this directory:**
- PNG / JPEG screenshots referenced from `v1.3-VERIFICATION-LOG.md` body via relative paths (`./v1.3-verification-evidence/<name>.png`).
- One screenshot per FE-08 visual edge case + one per FE-09 sessions revoke flow + optional cross-phase smoke screenshots.

**Commit policy (planner-locked per D-29-04 RECOMMEND clause):**
- Screenshots stay **local** (NOT committed) — they contain sandbox bot/user identifiers per D-29-04.
- Add `.planning/milestones/v1.3-verification-evidence/` to `.gitignore` as part of Phase 29's commit (one-liner addition, no other files touched).
- The markdown log is committed; the screenshots it references exist only on the operator's machine. Anyone later auditing the log will see "screenshot referenced but not committed (sandbox identifiers)" — acceptable per D-29-04.

**Constraints inherited:**
- No application code — pure operator artifact directory.
- Markdown log references screenshots via relative paths so the local-only directory layout is preserved if the log is moved.

---

## Shared Patterns

### Operator CLI invocation
**Source:** `apps/backend/scripts/seed_demo_data.py`, `apps/backend/scripts/export_openapi.py`
**Apply to:** Both new `scripts/*.py` files.

All operator scripts under `apps/backend/scripts/`:
1. Live as a module (no package init needed) and are invoked via `cd apps/backend && uv run python -m scripts.<name>`.
2. Expose `def main() -> int` synchronously, wrapping `asyncio.run(_run())` if async work is needed.
3. End with the canonical `if __name__ == "__main__": raise SystemExit(main())` line.
4. Print a single human-readable summary line on success; write errors to `sys.stderr` and return non-zero.
5. Are NEVER invoked by CI or by the compose stack's `migrate` step — they are one-shot operator commands.

### Cron callable signature
**Source:** `apps/backend/app/workers/scheduled/send_expiring_notifications.py` lines 41–68, `apps/backend/app/workers/scheduled/expire_memberships.py` lines 41–72
**Apply to:** The optional one-shot cron runner.

All cron callables are `async def <name>(ctx: dict[str, Any]) -> int` and read `ctx["sessionmaker"]` (`async_sessionmaker[AsyncSession]`). The one-shot runner builds `ctx` via `WorkerSettings.on_startup(ctx)` — it does NOT re-implement `db_lifespan_manager()` inline. This pattern is repeated across both existing scheduled jobs and the new runner.

### Verbatim copy assertion (DM strings)
**Source:** `apps/backend/app/integrations/telegram/handlers.py` lines 83–87, `apps/backend/app/integrations/telegram/copy.py` lines 40–45
**Apply to:** `v1.3-VERIFICATION-LOG.md` body where Telegram DMs are exercised (DEBT-04 #6, cross-phase steps 7–8).

All bot DM strings are Python constants and the verification log quotes them **verbatim** (exact-string equal — no regex, no paraphrase) so future operators can grep the log for the locked copy without opening Telegram. The 8 strings to potentially quote:

```python
# apps/backend/app/integrations/telegram/handlers.py
_DM_CHECKIN_OK_WITH_DAYS = "✅ Отмечено. Абонемент действует ещё {days_remaining} дн."
_DM_CHECKIN_OK_LAST_DAY = "✅ Отмечено. Сегодня — последний день абонемента."

# apps/backend/app/integrations/telegram/copy.py
EXPIRING_7D_VARIANT_A = "Привет! Ваш абонемент истекает {end_date}. Самое время продлить — обратитесь к администратору."
EXPIRING_7D_VARIANT_B = "Напоминаем: ваш абонемент действует до {end_date}. Продление через администратора."
EXPIRING_3D_VARIANT_A = "Через 3 дня заканчивается ваш абонемент ({end_date}). Подойдите к стойке для продления."
EXPIRING_3D_VARIANT_B = "Ваш абонемент действителен до {end_date}. Не забудьте продлить!"
EXPIRING_1D_VARIANT_A = "Завтра ({end_date}) — последний день вашего абонемента. Заходите продлевать."
EXPIRING_1D_VARIANT_B = "Внимание: ваш абонемент истекает завтра, {end_date}. Зайдите к нам, чтобы продлить."
```

The 7d/3d/1d variants are picked **deterministically per `client_id`** (`copy.pick_variant`) — verification recipes can predict which variant a given fixture client will receive by inspecting `client_id.bytes[0] & 1`. Phase 29 fixtures should be seeded with deterministic UUIDs (or the log records both variants and accepts either as PASS).

### DB-level fixture manipulation
**Source:** D-29-08 cross-phase smoke recipe steps 3 + 6 + 8 (no source code analog — established as verification-only pattern by Phase 29 itself).
**Apply to:** Cross-phase smoke scenario in `v1.3-VERIFICATION-LOG.md`.

Direct `docker compose exec postgres psql -U app -d sportzal -c "UPDATE ..."` invocations are acceptable in the verification recipe because we are testing downstream side effects (DM dispatch, audit emission), not the production code path that would have generated the rows. The verification log records the exact SQL executed and the row count affected. **This is NOT a production pattern** — no `apps/backend/app/` code uses this; it's verification-time only.

### No production-code edits
**Source:** D-29-07, Roadmap "verification ≠ implementation" rule.
**Apply to:** All Phase 29 files.

Phase 29 produces ZERO new or modified files under `apps/backend/app/` or `apps/admin-web/src/`. The only writable surfaces are:
- `apps/backend/scripts/*.py` (operator scripts — already-acceptable surface per project convention).
- `.planning/milestones/v1.3-VERIFICATION-LOG.md` (new milestone artifact).
- `.planning/milestones/v1.3-verification-evidence/` (new local-only dir + `.gitignore` entry).
- `.planning/STATE.md` (status update on phase complete).
- `.planning/phases/29-milestone-verification/29-*.md` (GSD phase artifacts — PLAN, SUMMARY, VERIFICATION).

If a regression is discovered during verification, the fix MUST land as a separate commit (cited under `overrides:` in the log) on a separate plan — never inlined into Phase 29's plans. Phase 29 plans only EXECUTE verification + write the log.

---

## No Analog Found

None. All three Phase 29-produced files have close analogs already documented above. The evidence directory has no analog but doesn't need one (it's a directory, not a code artifact).

---

## Metadata

**Analog search scope:**
- `apps/backend/scripts/` (full directory listing)
- `apps/backend/app/workers/` (full directory)
- `apps/backend/app/integrations/telegram/` (full directory)
- `.planning/milestones/` (full listing)
- Git history at `29d3234^` for the v1.2 `22-VERIFICATION.md` source

**Files scanned (read in full or targeted):**
- `apps/backend/scripts/seed_demo_data.py` (97 lines, full)
- `apps/backend/scripts/export_openapi.py` (72 lines, full)
- `apps/backend/app/workers/__init__.py` (160 lines, full)
- `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (69 lines, full)
- `apps/backend/app/workers/scheduled/expire_memberships.py` (73 lines, full)
- `apps/backend/app/integrations/telegram/handlers.py` (grep for `_DM_*` constants)
- `apps/backend/app/integrations/telegram/copy.py` (80 lines, head)
- v1.2 `22-VERIFICATION.md` (via `git show 29d3234^:...` — first 120 lines of YAML frontmatter + body intro)
- `.planning/STATE.md` (top 40 lines)
- `.planning/phases/29-milestone-verification/29-CONTEXT.md` (full, 494 lines)
- `.planning/REQUIREMENTS.md` (top 40 lines for DEBT-04 acceptance text on line 20)

**Pattern extraction date:** 2026-05-14
