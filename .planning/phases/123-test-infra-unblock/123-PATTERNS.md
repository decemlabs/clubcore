# Phase 123: Test-Infra Unblock - Pattern Map

**Mapped:** 2026-07-26
**Files analyzed:** 5 (1 lint fix, 1 registry append, 1 new evidence dir, 1 possible conftest extension, 1 footprint-check task)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/tests/messaging/test_attachment_idor.py` (import fix only) | test | transform (lint fix, no behavior change) | same file's own header/imports | exact (self-fix) |
| `.planning/audits/v4.1-DEFECT-REGISTRY.md` (`## Discovered during fix` rows) | config/ledger (markdown table) | CRUD (append-only row insert) | existing `## HYGIENE` table rows (e.g. `V41-HYG-068`..`071`) in same file | exact |
| `.planning/audits/v4.1-TEST-RUNS/` (new dir: run log + summary) | utility (evidence archive) | file-I/O (write-once artifact) | `.planning/audits/v4.1-HYGIENE-RAW/` (dir + file naming convention) | exact |
| `apps/backend/tests/integration/conftest.py` / `.../bookings/conftest.py` (marker extension, only if regression) | test-fixture / middleware-analog | event-driven (autouse fixture, marker-gated skip) | same files, existing `no_permissive_booking_config` marker block | exact |
| phase-close footprint-check task (plan-file `<verify>` block, not a source file) | test / CI-gate | batch (one-shot `git diff --name-only` assertion) | `.planning/phases/122-.../122-02-PLAN.md` task `<verify>` blocks (D-122-24 pattern) | exact |

## Pattern Assignments

### `apps/backend/tests/messaging/test_attachment_idor.py` (test, transform)

**Analog:** itself — this is a one-line import fix, not a new-file pattern.

**Current imports (lines 15-26):**
```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.messaging import repository, service
from app.modules.messaging.schemas import SendMessageRequest
```

**Fix pattern:** add `from typing import Any` to the stdlib import block (alphabetically before `from uuid import ...`, after `from datetime import ...`), per ruff/isort stdlib-then-thirdparty-then-local grouping already used in this file. Verify with `ruff check --select F821 apps/backend/tests/messaging/test_attachment_idor.py` → zero findings, then run the file's tests to confirm no behavior change.

---

### `.planning/audits/v4.1-DEFECT-REGISTRY.md` — `## Discovered during fix` section (ledger, CRUD-append)

**Analog:** existing `## HYGIENE` table rows, e.g. `V41-HYG-068`–`071` (lines 145-149), and the section's own header block (lines 186-193).

**Section anchor to append into (lines 186-193):**
```markdown
## Discovered during fix

Post-freeze findings are appended here, never into the three tables above (D-122-05). Each row
carries a `discovered-during-fix` tag and names the phase that found it. Empty until a fix phase
(123-127) discovers something the frozen audit did not catch.

| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |
|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|
```

**11-column schema (from "Schema legend", lines 19-38):** `id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason`

**Row-shape analog** (`V41-HYG-071`, line 148):
```
| V41-HYG-071 | HYGIENE | Minor | apps/backend/.importlinter (contract 2: "modules cannot import each other") | `uvx --from import-linter lint-imports --config apps/backend/.importlinter` | .planning/audits/v4.1-HYGIENE-RAW/import-linter.txt:32-44 | open | 125 | — | no | 5 "No matches for ignored import" warnings — declared ignore-list exceptions with zero matching imports today (contracts remain 3 kept / 0 broken); candidates for ignore-list cleanup, not real violations |
```

**Deferred-row analog** (`V41-HYG-068`, line 145 — shows `deferred:accepted-risk` reason phrasing style):
```
| V41-HYG-068 | HYGIENE | Minor | ... | ... | ... | deferred:accepted-risk | 125 | — | no | Pydantic v2 `@field_validator`/`@model_validator`-decorated methods are invoked by the Pydantic validation engine at model-construction time via decorator registration, never called directly in source — same decorator-dispatch false-positive class as V41-HYG-057 |
```

**ID allocation:** next sequential ID continues past the highest existing `V41-HYG-NNN`. At mapping time the highest confirmed row was `V41-HYG-072` (line 149, admin cross-feature import count) — planner/executor must re-grep `grep -n "V41-HYG-" .planning/audits/v4.1-DEFECT-REGISTRY.md | tail -5` immediately before allocating to avoid staleness, per D-123-03.

**Category/owning_phase per D-123-03/D-123-08:** category always `HYGIENE`; `owning_phase: 123` for rows this phase terminates (F821, freeze_race, alembic_clean, asgi_lifespan collective row, TEST-01 verification row); `owning_phase: 124` + `locked_invariant_risk: yes` for `test_phase51_audit_chain_invariants` and `test_route_introspection` rows.

---

### `.planning/audits/v4.1-TEST-RUNS/` (new evidence dir, file-I/O)

**Analog:** `.planning/audits/v4.1-HYGIENE-RAW/` — sibling dir, same convention (flat files, tool-name-based filenames, referenced by exact path:line-range from registry `evidence` cells).

**Directory listing of the analog (naming convention to clone):**
```
v4.1-HYGIENE-RAW/
  deptry.txt
  eslint-admin.txt
  import-linter.txt
  jscpd.txt
  knip.txt
  markers.txt
  vulture.txt
```

**Pattern to apply:** `v4.1-TEST-RUNS/` gets:
- `pytest-full-run-2026-07-26.log` (D-123-07 — the fresh full run's raw output)
- a short summary file (e.g. `pytest-full-run-2026-07-26-SUMMARY.md`) with: exact command, DB-reset commands, pass/fail/error/skip tally, wall-clock time — mirrors the STEP 9 tally format already established in `.planning/debug/pytest-isolation-deadlock.md` ("3058 passed / 3 failed / 2 errors / 8 skipped, 15m08s").
- Every registry row's `evidence` cell must point into this dir by exact filename (never bare prose), matching how `V41-HYG-071`'s evidence cell reads `.planning/audits/v4.1-HYGIENE-RAW/import-linter.txt:32-44`.

---

### `apps/backend/tests/integration/conftest.py` / `apps/backend/tests/integration/bookings/conftest.py` (only if deadlock regression per D-123-10)

**Analog:** the existing `no_permissive_booking_config` marker mechanism, already live in both files.

**Marker registration** (`apps/backend/pyproject.toml` line 108):
```toml
"no_permissive_booking_config: skip the autouse permissive_booking_config fixture (alembic-downgrade subprocess tests)",
```

**Fixture opt-out check pattern** (`apps/backend/tests/integration/conftest.py` lines 63-70):
```python
@pytest_asyncio.fixture(autouse=True)
async def permissive_booking_config(
    request: pytest.FixtureRequest,
    db_session: AsyncSession,
    ...
):
    """... tests that need real working-hours enforcement (e.g. alembic-downgrade
    subprocess tests, freeze/race tests with real locking) can opt out by marking
    themselves with ``@pytest.mark.no_permissive_booking_config`` so this fixture
    ...
    """
    if request.node.get_closest_marker("no_permissive_booking_config") is not None:
        return
    ...
```

**Extension pattern (if regression confirmed):** add the same `@pytest.mark.no_permissive_booking_config` decorator to the newly-affected test module(s)/classes — do NOT invent a new marker or new fixture. Register no new pyproject marker (already registered). Document the newly-marked module(s) in `.planning/debug/pytest-isolation-deadlock.md` per D-123-10, and cite the extension in the corresponding registry row's `evidence`/`reason` cell.

**8 existing marker sites (for cross-reference / consistency check, do not re-derive):** `tests/integration/conftest.py`, `tests/integration/bookings/conftest.py`, `tests/integration/test_settings_endpoints.py`, `tests/integration/client_portal/test_client_booking_race.py`, `tests/integration/migrations/test_visits_channel_client_qr.py`, `tests/integration/alembic/test_migration_0027_cleanup.py`, `tests/integration/alembic/test_migration_0033_clients_email.py` (+ `pyproject.toml` registration).

---

### Phase-close footprint check (plan-file task, mirrors D-122-24)

**Analog:** `.planning/phases/122-audit-registry-producing-read-only-pass/122-02-PLAN.md` task `<verify>` blocks (lines 83-84, 100-105).

**Concrete excerpt (line 100, `<verify>` shell assertion style to mirror):**
```
<verify>
    <automated>test -f .planning/audits/v4.1-HYGIENE-RAW/import-linter.txt && test -f .planning/audits/v4.1-HYGIENE-RAW/eslint-admin.txt && git diff --name-only | grep -qvE "eslint.config|\.eslintrc" ; echo done</automated>
</verify>
```

**Concrete excerpt (line 83, allowlist-negative-assertion style):**
```
- Package manifests are unchanged: `git diff --name-only | grep -E "package.json|pnpm-lock.yaml|pyproject.toml|uv.lock"` returns nothing (ephemeral runners only).
```

**Pattern to apply for Phase 123's SC-2 (D-123-11):** a dedicated plan task (or final task's `<verify>` block) runs:
```bash
git diff --name-only <phase-start-sha>..HEAD | grep -vE '^(apps/backend/tests/|apps/backend/pyproject\.toml$|\.planning/)'
```
and asserts the output is empty (any line printed = phase-exit failure). This must exist as an explicit, automated plan task — not left implicit — per D-123-11's closing note ("the check must exist as an explicit plan task or SC-2 is unprovable").

## Shared Patterns

### Registry row schema (applies to every disposition row this phase writes)
**Source:** `.planning/audits/v4.1-DEFECT-REGISTRY.md` lines 19-38 (Schema legend) + lines 186-193 (append section)
**Apply to:** all ~6 rows this phase appends (TEST-01 verification row, F821, `test_freeze_race`, `test_alembic_clean`, `test_phase51_audit_chain_invariants`, `test_route_introspection`, asgi_lifespan collective row)
- 11 columns exactly, in order; `category` always `HYGIENE`; ID continues `V41-HYG-NNN` sequence (re-check current max before allocating — do not trust the `072` seen during mapping without a fresh grep).
- `evidence` cell is always a re-runnable artifact path (never prose) — points into `.planning/audits/v4.1-TEST-RUNS/`.
- `deferred` disposition always paired with `reason` = `operator-pending` / `out-of-scope` / `accepted-risk` (per D-123-08's per-item guidance: freeze_race and asgi_lifespan → `accepted-risk`; locked-invariant rows → route to 124 via `owning_phase`, not `deferred`).

### Evidence-archive dir convention
**Source:** `.planning/audits/v4.1-HYGIENE-RAW/`
**Apply to:** new `.planning/audits/v4.1-TEST-RUNS/` dir
- Flat files, descriptive tool/run-based filenames, referenced by exact `path:line-range` (or whole-file path) from registry `evidence` cells — never a bare directory reference.

### Marker-based fixture opt-out (only on regression)
**Source:** `apps/backend/tests/integration/conftest.py` lines 63-70, `apps/backend/pyproject.toml` line 108
**Apply to:** any newly-affected test module if D-123-10's regression fallback triggers
- Extend the existing `no_permissive_booking_config` marker to new modules; never introduce a parallel marker/fixture mechanism.

## No Analog Found

None — every file/artifact this phase touches has a direct, concrete analog already in the tree (registry table rows, HYGIENE-RAW dir, marker mechanism, footprint-check task pattern). This phase is verification/disposition work, not novel construction, so full pattern coverage is expected and achieved.

## Metadata

**Analog search scope:** `.planning/audits/v4.1-DEFECT-REGISTRY.md`, `.planning/audits/v4.1-HYGIENE-RAW/`, `apps/backend/tests/integration/conftest.py`, `apps/backend/tests/messaging/test_attachment_idor.py`, `apps/backend/pyproject.toml`, `.planning/phases/122-audit-registry-producing-read-only-pass/*.md`
**Files scanned:** 7 read/grepped directly, plus registry tail/HYGIENE-RAW dir listing
**Pattern extraction date:** 2026-07-26
