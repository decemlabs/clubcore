---
phase: quick-260501-ndi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/backend/pyproject.toml
  - apps/backend/docs/conventions.md
autonomous: true
requirements:
  - QUICK-260501-NDI-01
must_haves:
  truths:
    - "Running any uv command in apps/backend no longer prints the `tool.uv.dev-dependencies` deprecation warning"
    - "The 6 dev dependencies (ruff, mypy, import-linter, pytest, pytest-asyncio, asgi-lifespan) are still installed and usable"
    - "`uv run pytest -v` still passes (3 tests)"
    - "`uv lock --check` still passes (lock remains valid, or is regenerated cleanly)"
  artifacts:
    - path: "apps/backend/pyproject.toml"
      provides: "Backend project manifest using PEP 735 [dependency-groups].dev"
      contains: "[dependency-groups]"
  key_links:
    - from: "apps/backend/pyproject.toml"
      to: "uv resolver"
      via: "[dependency-groups].dev table (PEP 735)"
      pattern: "^\\[dependency-groups\\]"
---

<objective>
Migrate `apps/backend/pyproject.toml` dev dependencies from the deprecated
`[tool.uv] dev-dependencies` array to the modern `[dependency-groups].dev`
table (PEP 735 / uv >= 0.5).

Purpose: silence the persistent uv deprecation warning emitted on every
backend command, and align with the PEP 735 standard so future uv releases
don't break the dev workflow.

Output: edited `pyproject.toml` (no `[tool.uv]` block, new
`[dependency-groups]` table) plus a one-line docs touch-up in
`apps/backend/docs/conventions.md` so the convention doc references the new
table name.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@apps/backend/pyproject.toml
@apps/backend/docs/conventions.md

<interfaces>
<!-- Current pyproject.toml shape (verified by read at plan time). -->
<!-- The `[tool.uv]` table contains ONLY `dev-dependencies` — the whole block is removed. -->

apps/backend/pyproject.toml lines 20-30 (CURRENT — to be replaced):
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

Target shape:
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

Notes:
- `[tool.uv]` has NO other keys → remove the entire table (verified by reading the file).
- The two `# CONTEXT.md D-15 ...` comment lines are obsolete after this migration —
  delete them (the new form IS the PEP 735 standard the comment describes as the
  "modern equivalent"). Do not invent a replacement comment.
- Other tables (`[tool.mypy]`, `[[tool.mypy.overrides]]`, `[tool.pydantic-mypy]`,
  `[tool.pytest.ini_options]`) MUST be preserved verbatim.
- Dev dep contents (names, version pins) MUST NOT change — pure relocation.

apps/backend/docs/conventions.md line 60 (CURRENT):
```
**`asgi-lifespan`** — required dev-dependency (`asgi-lifespan>=2.1` в `[tool.uv] dev-dependencies`). ...
```

Change `[tool.uv] dev-dependencies` → `[dependency-groups] dev` in that one
inline reference. Do not edit other prose in the file.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Migrate dev deps to PEP 735 [dependency-groups].dev</name>
  <files>apps/backend/pyproject.toml, apps/backend/docs/conventions.md</files>
  <action>
1. Edit `apps/backend/pyproject.toml`:
   - Delete lines 20-30 (the two `# CONTEXT.md D-15 ...` comment lines, the
     `[tool.uv]` table header, the `dev-dependencies = [...]` array, and the
     closing `]`).
   - In the same location (after the `[project]` table's `dependencies` array,
     before `[tool.mypy]`), insert:
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
   - Preserve all other tables (`[tool.mypy]`, `[[tool.mypy.overrides]]`,
     `[tool.pydantic-mypy]`, `[tool.pytest.ini_options]`) byte-for-byte.

2. Edit `apps/backend/docs/conventions.md` line 60 — replace the inline
   `` `[tool.uv] dev-dependencies` `` reference with
   `` `[dependency-groups] dev` ``. Touch nothing else in that file.

3. Refresh the lock if needed: from `apps/backend/`, run
   `uv lock --check`. If it reports the lock is out of sync, run
   `uv lock` (without `--upgrade`) to regenerate against the new table
   layout — do NOT bump versions.

4. Sanity grep across `apps/backend/` to confirm no remaining references
   to the deprecated key:
   ```
   grep -rn 'tool.uv.dev-dependencies\|\[tool\.uv\]' apps/backend/ \
     --include='*.toml' --include='*.md' --include='*.py'
   ```
   Expected: zero hits (the docs reference and the toml block are both gone).
  </action>
  <verify>
    <automated>cd apps/backend &amp;&amp; uv run python -c "print('ok')" 2&gt;&amp;1 | grep -c 'tool.uv.dev-dependencies' | awk '$1 == 0 {exit 0} {exit 1}' &amp;&amp; cd /Users/andre/Workspace/Development/clubcore/apps/backend &amp;&amp; uv run pytest -v 2&gt;&amp;1 | tail -5 &amp;&amp; grep -E '^\[dependency-groups\]' /Users/andre/Workspace/Development/clubcore/apps/backend/pyproject.toml | wc -l | awk '$1 == 1 {exit 0} {exit 1}' &amp;&amp; grep -E 'dev-dependencies' /Users/andre/Workspace/Development/clubcore/apps/backend/pyproject.toml | wc -l | awk '$1 == 0 {exit 0} {exit 1}' &amp;&amp; cd /Users/andre/Workspace/Development/clubcore/apps/backend &amp;&amp; uv lock --check</automated>
  </verify>
  <done>
- `apps/backend/pyproject.toml` contains exactly one `[dependency-groups]`
  table with a `dev = [...]` array holding the same 6 packages.
- The `[tool.uv]` table and its `dev-dependencies` key are gone.
- The obsolete `# CONTEXT.md D-15 ...` comment block is removed.
- `apps/backend/docs/conventions.md` no longer references
  `[tool.uv] dev-dependencies`.
- `uv run python -c "print('ok')"` from `apps/backend/` prints no
  `tool.uv.dev-dependencies` deprecation warning.
- `uv run pytest -v` from `apps/backend/` reports `3 passed`.
- `uv lock --check` from `apps/backend/` exits 0.
  </done>
</task>

</tasks>

<verification>
Single combined automated check chain (see task `<verify>`):
1. No deprecation warning in uv command output.
2. `pytest -v` still green (3 tests).
3. Exactly one `[dependency-groups]` table in `pyproject.toml`.
4. Zero `dev-dependencies` occurrences in `pyproject.toml`.
5. `uv lock --check` confirms the lock is consistent (or was regenerated
   cleanly during the action).
</verification>

<success_criteria>
- Backend dev workflow is warning-free (`uv run …` no longer prints the
  `tool.uv.dev-dependencies` deprecation notice).
- Test suite still passes (3/3) without any change to dev dep contents
  or runtime dependencies.
- `pyproject.toml` follows the PEP 735 standard, future-proof against
  uv removing the legacy field.
</success_criteria>

<output>
After completion, create
`.planning/quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/260501-ndi-SUMMARY.md`
documenting:
- The exact diff applied to `pyproject.toml` (before/after blocks).
- Whether `uv lock` had to regenerate the lock (yes/no) and, if yes,
  the resulting `uv.lock` change scope (should be metadata-only — no
  version bumps).
- Confirmation that the deprecation warning is gone.
</output>
