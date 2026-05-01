---
phase: quick-260501-ndi
plan: 01
subsystem: backend-tooling
tags: [chore, deps, uv, pep735, backend]
requires: []
provides:
  - "PEP 735 [dependency-groups].dev table in apps/backend/pyproject.toml"
  - "warning-free uv invocations in apps/backend"
affects:
  - apps/backend/pyproject.toml
  - apps/backend/docs/conventions.md
tech_added: []
patterns:
  - "PEP 735 dependency-groups (replaces deprecated [tool.uv].dev-dependencies)"
key_files:
  modified:
    - apps/backend/pyproject.toml
    - apps/backend/docs/conventions.md
  created: []
decisions:
  - "Removed the CONTEXT.md D-15 comment block: it described `[tool.uv] dev-dependencies` as user's locked choice and noted PEP 735 as the modern equivalent. After migration the new form IS the standard, so the rationale comment is obsolete (per plan instruction — no replacement comment invented)."
  - "Did NOT regenerate uv.lock: `uv lock --check` reported 'Resolved 54 packages in 3ms' immediately after the edit, confirming the lock remained consistent. No version bumps, no metadata churn."
metrics:
  duration: "~2 min"
  tasks_completed: 1
  files_modified: 2
  commits: 1
  completed_date: "2026-05-01"
---

# Quick Task 260501-ndi: Migrate Dev Deps to PEP 735 Summary

Replaced the deprecated `[tool.uv] dev-dependencies` array in
`apps/backend/pyproject.toml` with the PEP 735 `[dependency-groups].dev`
table to silence uv's persistent deprecation warning and future-proof the
backend manifest.

## What Changed

### `apps/backend/pyproject.toml` (lines 20-30)

**Before:**

```toml
# CONTEXT.md D-15 Discretion: user locked `[tool.uv] dev-dependencies = [...]`.
# (PEP 735 `[dependency-groups]` is the modern equivalent — both work; honor user's choice.)
[tool.uv]
dev-dependencies = [
    "ruff>=0.6",
    "mypy>=1.10",
    "import-linter>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "asgi-lifespan>=2.1",
]
```

**After:**

```toml
[dependency-groups]
dev = [
    "ruff>=0.6",
    "mypy>=1.10",
    "import-linter>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "asgi-lifespan>=2.1",
]
```

Diff stats: `2 files changed, 3 insertions(+), 5 deletions(-)`.

All other tables (`[tool.mypy]`, `[[tool.mypy.overrides]]`,
`[tool.pydantic-mypy]`, `[tool.pytest.ini_options]`) preserved verbatim.
Dev dep names and version pins unchanged — pure relocation.

### `apps/backend/docs/conventions.md` (line 60)

Updated single inline reference from `` `[tool.uv] dev-dependencies` `` to
`` `[dependency-groups] dev` ``. No other prose touched.

## Lock File

`uv lock --check` ran clean immediately after the edit — **no
regeneration needed**. The lock format is independent of which manifest
table holds the dev group, so existing entries remain valid.

## Verification

| Gate | Command | Result |
| --- | --- | --- |
| 1 | `uv run python -c "print('ok')"` | `ok` (no `tool.uv.dev-dependencies` deprecation warning) |
| 2 | `grep -E '^\[dependency-groups\]' pyproject.toml \| wc -l` | `1` (exactly one table) |
| 3 | `grep -E 'dev-dependencies' pyproject.toml \| wc -l` | `0` (zero refs to old key) |
| 4 | `uv lock --check` | `Resolved 54 packages in 3ms` (consistent) |
| 5 | `uv run pytest -v` | `3 passed in 0.04s` |
| 6 | `grep -rn 'tool.uv.dev-dependencies\|\[tool\.uv\]' apps/backend/` | zero hits (toml + md both clean) |

All 6 verification gates passed on first run. The deprecation warning
that previously printed on every uv invocation is gone (gate 1 confirms
uv produced only `ok` with no warning preamble).

## Test Output

```
============================== test session starts ==============================
platform darwin -- Python 3.12.12, pytest-9.0.3, pluggy-1.6.0
collected 3 items

tests/integration/test_healthz.py::test_healthz_returns_200_and_status_ok PASSED [ 33%]
tests/integration/test_healthz.py::test_healthz_emits_request_id_header PASSED   [ 66%]
tests/unit/test_security.py::test_security_module_is_importable PASSED           [100%]

============================== 3 passed in 0.04s ===============================
```

## Commit

- `71f28de` — `chore(deps): migrate uv dev deps to dependency-groups (PEP 735)`

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes (Rules 1-3) or
architectural decisions (Rule 4) triggered.

## Self-Check: PASSED

- FOUND: `apps/backend/pyproject.toml` (modified, contains `[dependency-groups]`)
- FOUND: `apps/backend/docs/conventions.md` (modified, references new table name)
- FOUND: commit `71f28de` in `git log`
- FOUND: SUMMARY.md at expected path
