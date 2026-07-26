# Phase 123: Test-Infra Unblock - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning
**Mode:** `--chain` interactive; user delegated all four gray areas to Claude ("сам все выбери и реши") — every decision below is Claude's recommended option, recorded as accepted.

<domain>
## Phase Boundary

This phase is a **verification-then-disposition** pass over the backend test infrastructure, not a fixing spree:

1. **Verify** that the v3.2-close deadlock fix `f438ced2` (`no_permissive_booking_config` marker on 4 module groups + booking-race teardown restore + `pytest-timeout` 180s) still holds on a **fresh full pytest run against a clean database** (TEST-01). The premise is verification — the deadlock is recorded ✅ RESOLVED in STATE.md's Deferred Items ledger; new structural work happens only if the fresh run regresses.
2. **Disposition** every residual failure of the fresh run as its own registry row with a terminal disposition — `fixed+verified` or `deferred`+reason (TEST-02). No bare "known flake" prose survives this phase.

**File footprint is locked narrow (SC-2):** `apps/backend/tests/**`, `apps/backend/pyproject.toml` (test config only), `.planning/**`. Any other path in the phase diff is a phase-exit failure. No app-code edits, no test-suite archaeology, no un-flaking campaigns.

**Not this phase:** fixing `locked_invariant_risk` findings (Phase 124 risk-first), structural asgi_lifespan pollution fixes, CI changes, anything touching `apps/backend/app/**`.

</domain>

<decisions>
## Implementation Decisions

### Registry row mechanics (frozen registry, no TEST rows exist)

- **D-123-01:** All Phase-123 rows are appended to the registry's **`## Discovered during fix`** section — the only append point D-122-05 permits (main tables are append-nothing after freeze; scouting confirmed zero rows mention `freeze_race`/`F821`/`alembic_clean`/`deadlock` and zero rows carry `owning_phase: 123`). — **Reversibility:** costly — appending anywhere else breaks the freeze protocol the whole milestone's honesty rests on.
- **D-123-02:** The `discovered-during-fix` tag is kept **mechanically** (it is section membership, per D-122-05), but honesty is preserved in the row body: each row's `repro`/`reason` cell states explicitly that the item is **known-pre-freeze, carried from TEST-01/TEST-02 requirements**, not a new audit discovery. The audit's scope was AUD-01..08; test-suite health was always Phase 123's intake, so the absence of these rows from the frozen tables is by design, not an audit miss. — **Reversibility:** reversible.
- **D-123-03:** Category is **HYGIENE** (test-suite quality defects, not app-behavior-on-live-data), IDs continue the existing `V41-HYG-NNN` sequence past the freeze-time maximum (gaps allowed, IDs permanent per D-122-02). `owning_phase: 123` for rows this phase terminates; rows found to touch locked invariants get `owning_phase: 124` (see D-123-08). Severity: `Major` for anything that blocks a full green-ish run, `Minor` for lint/flake residue. — **Reversibility:** reversible.
- **D-123-04:** SC-4 is satisfied by a dedicated **TEST-01 verification row** whose `evidence` cell cross-references commit `f438ced2` + the fresh-run log; disposition `fixed+verified` if the run completes without hanging. This row is the registry's answer to "was new work required?" — expected answer: no.

### Fresh-run protocol (TEST-01)

- **D-123-05:** The run happens on the **local docker-compose stack** with a **clean database** (drop/recreate + migrate before the run). Known local-stack gotchas are checklist preconditions, not discoveries: compose env reload, stale-image migrate, seed/pytest interaction. After the run, re-seed the demo DB (guardrail from the June fix session: pytest wipes users/clients/bookings/visits). — **Reversibility:** reversible.
- **D-123-06:** **One full run is the baseline** (~15 min, `pytest-timeout` 180s already active as the hang tripwire). Failures are then re-run **as a targeted subset only** (the failing node IDs, in isolation) to classify deterministic-vs-flaky — a second full 15-minute run is spent only if the first one hangs or shows lock-family regression. This is what "timebox held" looks like at run level. — **Reversibility:** reversible.
- **D-123-07:** Evidence is an artifact, never prose (D-V40-LOCAL-VALIDATE inheritance): the full run log is archived at **`.planning/audits/v4.1-TEST-RUNS/pytest-full-run-2026-07-26.log`** (new sibling dir to `v4.1-HYGIENE-RAW/`), plus a short summary file with the exact command, DB-reset commands, tally, and wall-clock time. Every registry row's `evidence` cell points into this directory. — **Reversibility:** reversible.

### Fix-vs-defer policy per residual (TEST-02)

**The fresh run is the sole authority on the residual set.** The roadmap's named list (`test_freeze_race`, promo F821, `test_alembic_clean`) and the June diagnosis's list (`test_freeze_race`, `test_phase51_audit_chain_invariants`, `test_route_introspection`, asgi_lifespan errors) already disagree — both are stale by construction. Scouting ground truth (2026-07-26): the F821 lint failure is **5 × `Undefined name Any` in `apps/backend/tests/messaging/test_attachment_idor.py`** (not promo); `test_freeze_race` lives at `apps/backend/tests/integration/memberships/test_freeze_race.py`; `test_alembic_clean` at `apps/backend/tests/integration/test_alembic_clean.py`.

- **D-123-08:** Per-item default dispositions (final call belongs to the fresh-run outcome):
  - **F821 (`test_attachment_idor.py`)** → **fix now** (`fixed+verified`). A missing `from typing import Any` import in one test file is squarely inside the test-file footprint; leaving 5 trivial lint errors deferred would be dishonest timeboxing in the other direction. Evidence: clean `ruff check --select F821` + the file's tests passing.
  - **`test_freeze_race` (concurrency timing)** → attempt a cheap deterministic fix **only if the cause is obvious within one look** (e.g. a sleep/ordering assertion); otherwise **`deferred:accepted-risk`** with the timing-race reason. No un-flaking campaign.
  - **`test_alembic_clean`** → status unknown (named by roadmap, absent from June diagnosis) — fresh run decides; row disposition follows the outcome, including `fixed+verified` if it simply passes.
  - **`test_phase51_audit_chain_invariants` (LOCKED_AUDIT_EVENTS count 117≠118)** → **row only, `locked_invariant_risk: yes`, `owning_phase: 124`**. Touching `LOCKED_AUDIT_EVENTS` parity belongs to Phase 124's locked-invariant-first lane (FUNC-04 policy); fixing it here would violate both the footprint lock and the risk-first ordering. — **Reversibility:** costly — fixing it out-of-lane bypasses the parity-mirror-in-same-commit rule.
  - **`test_route_introspection` (`/metrics` gate)** → same treatment: row, `locked_invariant_risk: yes`, `owning_phase: 124` (route-gate parity is RBAC-adjacent locked surface).
  - **asgi_lifespan TimeoutError errors** → **one collective row**, `deferred:accepted-risk` — known full-suite lifespan-probe pollution, tests pass in isolation; structural fix is out of scope.
  - **Anything new the fresh run surfaces** ("и остальные") → own row, same decision tree: trivial-and-in-footprint → fix; locked-invariant-adjacent → row for 124; else → `deferred:accepted-risk` with reason.

### Timebox & regression fallback

- **D-123-09:** "Deadlock regressed" means: the run **hangs** (fails to reach 100%) or `pytest-timeout` fires on lock-family tests (`working_hours_config`/`booking_config` singletons, alembic-downgrade subprocess tests) — not merely new unrelated failures appearing. — **Reversibility:** reversible.
- **D-123-10:** If regression is confirmed: at most **two diagnose-fix cycles** using the existing methodology in `.planning/debug/pytest-isolation-deadlock.md` (pg_blocking_pids live capture → marker/teardown-scope fix). If two cycles don't restore a completing run, fall back to the **documented per-module workaround**: extend the `no_permissive_booking_config` marker to the newly-affected modules, document the scope in the debug doc, and record the registry row as `deferred` with the workaround referenced (SC-1's second branch). — **Reversibility:** reversible — the marker mechanism already exists in 8 files.
- **D-123-11:** SC-2 ("timebox held") is proven **mechanically, mirroring D-122-24**: a phase-close check runs `git diff --name-only <phase-start-sha>..HEAD` and asserts every path matches the allowlist — `apps/backend/tests/**`, `apps/backend/pyproject.toml`, `.planning/**`. Any other path is a phase-exit failure. — **Reversibility:** reversible — but the check must exist as an explicit plan task or SC-2 is unprovable.

### Claude's Discretion

The user delegated all areas; within the decisions above the following remain open for planner/executor judgment:

- Exact shape of the DB-reset commands (compose down -v vs targeted drop/create) — whatever provably yields a clean DB with migrations applied.
- Whether the fresh-run + disposition work is one plan or two (run → triage) — sequencing call; the run's output is the triage's input either way.
- The wording of each row's `reason` cell — provided every deferred row names a concrete reason (`accepted-risk` timing race, lifespan pollution, locked-invariant lane).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone contract
- `.planning/REQUIREMENTS.md` — TEST-01/TEST-02 verbatim (lines 33-36), incl. the 2026-07-26 premise correction: TEST-01 is verification, not fixing from scratch
- `.planning/ROADMAP.md` § "Phase 123" — goal + 4 success criteria (completion-or-workaround, footprint lock, per-item terminal dispositions, f438ced2 cross-reference)
- `.planning/STATE.md` § "Deferred Items" → v3.2-close table — the ✅ RESOLVED `f438ced2` entry with the full fix description; § "Research Flags" note requiring Phase 123 to reconcile TEST-01's stale premise

### The prior fix (the thing being verified)
- `.planning/debug/pytest-isolation-deadlock.md` — full root-cause diagnosis (pg_blocking_pids evidence), fix rationale, the STEP 9 final tally (3058 passed / 3 failed / 2 errors / 8 skipped, 15m08s), and the documented residual-failure classification — **the methodology to reuse if regression occurs**
- Commit `f438ced2` — the fix itself: marker opt-out in `tests/integration/conftest.py` + `tests/integration/bookings/conftest.py`, booking-race teardown restore, pytest-timeout
- `apps/backend/pyproject.toml` lines 40, 101-102 — `pytest-timeout>=2.3`, `timeout = 180`, `timeout_method = "signal"` (already in place)
- `no_permissive_booking_config` marker sites (8 files): `tests/integration/conftest.py`, `tests/integration/bookings/conftest.py`, `tests/integration/test_settings_endpoints.py`, `tests/integration/client_portal/test_client_booking_race.py`, `tests/integration/migrations/test_visits_channel_client_qr.py`, `tests/integration/alembic/test_migration_0027_cleanup.py`, `tests/integration/alembic/test_migration_0033_clients_email.py` (+ `pyproject.toml` marker registration)

### Registry (append target)
- `.planning/audits/v4.1-DEFECT-REGISTRY.md` — frozen at `2ce5da33`, 136 rows; § "Schema legend" (11-column contract); § "Discovered during fix" (the ONLY append point, currently empty); highest existing `V41-HYG` ID must be checked before allocating new IDs
- `.planning/phases/122-audit-registry-producing-read-only-pass/122-CONTEXT.md` — D-122-02 (IDs permanent), D-122-05 (freeze mechanics), D-122-24 (mechanical footprint check pattern to mirror)

### Residual-failure targets (ground truth 2026-07-26)
- `apps/backend/tests/messaging/test_attachment_idor.py` — the 5 × F821 `Undefined name Any` (the roadmap's "promo F821" label is stale)
- `apps/backend/tests/integration/memberships/test_freeze_race.py` — the timing-race flake
- `apps/backend/tests/integration/test_alembic_clean.py` — named by roadmap, absent from June diagnosis; fresh run decides
- `apps/backend/app/core/audit.py` (`LOCKED_AUDIT_EVENTS`) + `apps/backend/tests/unit/test_audit_taxonomy.py` — locked-invariant surface behind the `test_phase51` 117≠118 failure; **read-only in this phase**

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The `f438ced2` fix machinery** — marker opt-out + teardown restore + pytest-timeout are all live in the tree; regression handling extends them, never reinvents.
- **`.planning/debug/pytest-isolation-deadlock.md`** — a complete, proven diagnosis playbook (isolation runs with wall-clock guard, `pg_blocking_pids` live capture, falsification test) ready to re-execute verbatim on regression.
- **`.planning/audits/v4.1-HYGIENE-RAW/` convention** — raw-output archive pattern to clone as `v4.1-TEST-RUNS/`.
- **D-122-24 footprint check** — the `git diff --name-only` allowlist assertion pattern, reused with this phase's narrower allowlist.

### Established Patterns
- **Evidence is an artifact, never prose** — every registry row cell points at a log path, commit SHA, or command output.
- **Registry freeze protocol** — main tables append-nothing; `## Discovered during fix` is the sole append point; IDs sequential and permanent.
- **Local-stack gotchas are preconditions, not discoveries** — compose env reload, stale-image migrate, seed/pytest interplay, post-pytest demo reseed (memory: backend-local-stack-gotchas).

### Integration Points
- **Registry rows → Phase 124**: the two locked-invariant rows (`test_phase51`, `test_route_introspection`) enter Phase 124's risk-first queue via `owning_phase: 124`.
- **Green-ish baseline → Phases 124-126**: every later fix phase's `fixed+verified` evidence depends on this phase proving the suite runs to completion.
- **Stale-map warning carried from 122**: `.planning/codebase/*.md` (incl. TESTING.md) describe the deleted `admin-web` era — not usable as input here; trust the tree and the debug doc.

</code_context>

<specifics>
## Specific Ideas

- **The roadmap's named residual list is knowingly stale** — "promo F821" is actually 5 lint errors in `tests/messaging/test_attachment_idor.py`; the June run's residuals include two items the roadmap doesn't name (`test_phase51`, `test_route_introspection`) which are both locked-invariant-adjacent. The fresh run's tally is the only authority; the registry rows must record what the fresh run shows, cross-referencing the stale names so the trail is auditable.
- **Expected happy path**: fresh run completes ~15 min → TEST-01 row `fixed+verified` citing `f438ced2` + new log → F821 fixed inline → 4-6 disposition rows appended → footprint check green. The whole phase can plausibly land in one working session; the timebox decisions exist for the unhappy path.

</specifics>

<deferred>
## Deferred Ideas

- **Structural fix for asgi_lifespan full-suite pollution** (per-test `create_app()`+LifespanManager startup exceeding 5s under load) — a test-architecture change, out of the SC-2 footprint; candidate for a future test-debt phase or v4.2.
- **Properly un-flaking `test_freeze_race`** (deterministic concurrency harness) — only if the one-look fix fails; otherwise stays `deferred:accepted-risk` until someone owns a concurrency-testing pass.
- **LOCKED_AUDIT_EVENTS 117→118 reconciliation + `/metrics` route-gate declaration** — explicitly handed to Phase 124's locked-invariant-first lane via registry rows; not lost, just lane-corrected.
- **The 6 unscoped `test_sell_*` online-payment tests** (STATE.md Deferred Items, v2.5-era) — if the fresh run trips on them, they get a row like everything else; their structural fix (scoped selects) remains deferred where STATE.md already tracks it.

</deferred>

---

*Phase: 123-test-infra-unblock*
*Context gathered: 2026-07-26*
