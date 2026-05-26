# Phase 63: Tech-Debt Sweep — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 5 work-units (4 plans touch source/config; 1 plan is CI-only verification)
**Analogs found:** 5 / 5

> Phase 63 — это механическая гигиена (ruff format / ruff check --fix / mypy strict / shell-runbook hardening). Никаких новых feature-файлов не создаётся. "Файлы" здесь — это категории работ (массовые операции над деревом + точечные правки конфигов/скриптов), и аналоги для них — уже существующие конфиги и runbook-скрипты в репозитории.

---

## File Classification

| Work-unit (plan) | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| Plan 1 — DEBT-01 `ruff format` tree-wide (~297 .py files in `apps/backend/`) | tooling / mass-format | batch transform (whitespace-only, no semantic change) | `apps/backend/ruff.toml` (`[format]` block, lines 99–101) | exact (config IS the rule) |
| Plan 2 — DEBT-02 `ruff check --fix` (safe-only, ~80 of 158 auto + ~78 manual) on `apps/backend/{app,tests}/**/*.py` | tooling / safe auto-fix + manual refactor | batch transform + per-site refactor | `apps/backend/ruff.toml` (`[lint]` block + `per-file-ignores` lines 31–97) | exact (config IS the constraint) |
| Plan 3a — DEBT-03 mypy strict cleanup (11 errors in `apps/backend/app/**/*.py`) | type-hygiene refactor | per-site narrow edits | existing strict-mode codebase (e.g. `apps/backend/app/modules/auth/service.py`) + per-call-site fix | role-match (no single analog — pattern is "fix to satisfy mypy --strict") |
| Plan 3b — DEBT-03 `auth/models.py __all__` fix | module export hygiene | one-line addition | `apps/backend/app/modules/auth/models.py:30` `noqa: F401 — public re-export` precedent | exact (same file; analog is the existing re-export discipline) |
| Plan 3c — DEBT-03 `apps/backend/pyproject.toml` add `[[tool.mypy.overrides]]` for `module = "tests.*"` | config | insert config block | `apps/backend/pyproject.toml:43-59` (3 existing override blocks) | exact (same file, identical block shape) |
| Plan 4 — DEBT-04 `.planning/milestones/v1.5-verification-evidence/run.sh` hardening | shell runbook hotfixes | targeted find-and-replace edits | `.planning/milestones/v1.6-verification-evidence/run.sh` (v1.6 written FRESH per D-46-10 specifically to AVOID the v1.5 bugs Phase 63 now backports) | exact (analog is the "after" state the v1.5 runbook should reach) |
| Plan 5 — DEBT-05 CI verification | verification (read-only) | execute `.github/workflows/ci.yml` gates locally | `.github/workflows/ci.yml` (lines 38–51) | exact (CI workflow IS the spec) |

---

## Pattern Assignments

### Plan 1 — DEBT-01: `ruff format` tree-wide

**Analog:** `apps/backend/ruff.toml` lines 99–101 (already locks formatter config; sweep just applies it)

**Operative pattern** (`apps/backend/ruff.toml:99-101`):
```toml
[format]
quote-style = "double"
indent-style = "space"
```

**Command pattern** (single atomic commit, narrowest scope that covers all ~297 files per D-63-01 + Claude's-Discretion bullet on scope):
```bash
# From repo root — `apps/admin-web` is JS/TS, out of ruff's scope; alembic/ and tests/ live under apps/backend/
cd apps/backend && uv run ruff format .
```

**Verification (must hold post-format):**
```bash
# Exit code of ruff check is unchanged by formatter pass (D-63-01 success criterion):
cd apps/backend && uv run ruff check  # error count == pre-format count (~158)
cd apps/backend && uv run ruff format --check  # exit 0
```

**Commit shape:** one commit, whitespace-only diff, trivially reviewable by `git diff -w` showing empty.

---

### Plan 2 — DEBT-02: `ruff check --fix` (safe-only)

**Analog:** `apps/backend/ruff.toml` lines 4–17 (`[lint] select`) + lines 31–97 (`per-file-ignores`) — the existing constraint surface the fix pass operates within.

**Operative constraint pattern** (`apps/backend/ruff.toml:4-20`):
```toml
[lint]
select = [
    "E", "F", "I", "B", "UP", "ASYNC", "S", "DTZ", "N", "SIM", "RUF",
]
ignore = [
    "S101",  # allow assert (used by pytest, lands in Phase 3)
]
```

**Existing per-file-ignore SHAPE to follow if (and only if) escalation back to user is approved** — note: D-63-06 forbids NEW `# noqa`/per-file-ignores in this phase; the pattern below is what NOT to add. The existing entries (lines 31–97) are rationale-bearing tripwires from prior phases and stay untouched:
```toml
# Phase X NNN (plan NN-NN): <one-paragraph rationale; cite D-XX-NN or PITFALL>
"path/to/file.py" = ["RULE_CODE", ...]
```

**Command pattern** (single atomic commit per D-63-01, no `--unsafe-fixes` per D-63-05 / PITFALLS C-06):
```bash
# Plan 2 step 1 — safe auto-fix (~80 of 158: RUF100, F401, I001)
cd apps/backend && uv run ruff check --fix app tests   # NO --unsafe-fixes

# Plan 2 step 2 — manual refactor of residual ~78 (E501, RUF002 Cyrillic-in-docstring, RUF059 unused vars)
#   per D-63-06: refactor the offending site so the rule passes; do NOT add `# noqa: RULECODE`.
#   If a residual cannot be cleanly refactored → escalate to user (becomes a deviation), do not silence.
```

**Verification:**
```bash
cd apps/backend && uv run ruff check                  # exit 0 (158 → 0)
cd apps/backend && uv run ruff format --check         # exit 0 (Plan 1 baseline preserved)
```

**Side-effect rule (CONTEXT.md Integration Points):** if Plan 1's formatter pushed a line over E501, fix it inside Plan 2's commit — do NOT amend Plan 1.

---

### Plan 3a — DEBT-03: mypy strict cleanup (11 errors in `apps/backend/app/`)

**Analog:** any existing strict-clean module in `apps/backend/app/` — the codebase already passes `uv run mypy --strict app` modulo the 11 residual errors, so the existing strict-compliant patterns ARE the target shape. Example: `apps/backend/app/modules/auth/` modules already type-clean.

**Operative constraint** (`apps/backend/pyproject.toml:38-41`):
```toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

**Fix discipline (per D-63-06 + Out-of-scope list):**
- No new `# type: ignore` comments (zero-new-suppressions contract)
- No new `# noqa` comments
- No new `ignore_imports` in `.importlinter`
- Each fix is a real type annotation / signature correction / Protocol-aligned refactor

**Order:** planner's discretion per Claude's-Discretion bullet ("which of the 11 errors to address first") — user has no preference.

**Verification:**
```bash
cd apps/backend && uv run mypy --strict app   # exit 0 (11 → 0); this is the CI gate per D-63-03
```

---

### Plan 3b — DEBT-03: `auth/models.py __all__` fix

**Analog:** the same file `apps/backend/app/modules/auth/models.py` already documents and enforces a public re-export discipline at line 30:
```python
# Phase 41 INFRA-40 / D-41-01 — one-milestone shim. v1.7 DEFER-41-shim
# removes this re-export; downstream callers should migrate to
# `from app.core.models import User` at their convenience.
from app.core.models import User  # noqa: F401 — public re-export
```

**Pattern to apply (per PITFALLS Pitfall #6, referenced by CONTEXT.md canonical_refs):** add an explicit `__all__` declaration so the `User` re-export is part of the module's typed public surface (otherwise mypy strict flags it as "unused import" semantically while the `noqa: F401` only suppresses the ruff/pyflakes warning, not mypy's `attr-defined` chain when downstream imports `User` through this shim).

**Insertion site:** top of module, after the imports block (after line 35 `OtpChannel = ...`), before the first class definition (line 38 `class RefreshToken`). Conventional shape:
```python
__all__ = [
    "User",              # Phase 41 INFRA-40 / D-41-01 re-export shim (line 30 above)
    "OtpChannel",        # Phase 42 AUTH-EM-01 / D-42-20 (line 35 above)
    "RefreshToken",      # this module
    "OtpCode",           # this module (if present)
]
```

**Atomic with Plan 3a** per D-63-01 (Plan 3 = single commit covering 11 mypy errors + `__all__` fix).

---

### Plan 3c — DEBT-03: `pyproject.toml` add `tests.*` mypy override

**Analog:** `apps/backend/pyproject.toml` lines 43–59 — three existing `[[tool.mypy.overrides]]` blocks with the exact same shape, each carrying a rationale comment.

**Existing analog block** (`apps/backend/pyproject.toml:47-52`):
```toml
# Phase 30 INFRA-22: payments append-only AST fixtures contain intentionally
# bogus call signatures and untyped params to exercise the walker. They are
# parsed as text (ast.parse), never imported at runtime.
[[tool.mypy.overrides]]
module = "tests.unit.fixtures.*"
ignore_errors = true
```

**Insertion site:** after line 59 (after the existing `aioboto3.*`/`botocore.*` override), before line 61 `[tool.ruff.lint.per-file-ignores]`. Pattern to add per D-63-03:
```toml
# Phase 63 DEBT-03 / D-63-03: scope `mypy --strict` to app/ only. Test suite
# carries pre-existing untyped fixtures + dynamic helpers that would require
# a separate cleanup pass; CI gate stays exactly `uv run mypy --strict app`,
# so this override prevents an out-of-band `mypy app tests` ad-hoc run from
# crashing while keeping app/ strict-clean (zero deferral tracker file needed).
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_decorators = false
disallow_untyped_calls = false
```

**Why this shape:** mirrors lines 50–52 (single `module = "..."` string + flags) and lines 57–59 (list-form modules + flag). Use the string form because there's a single glob.

**Atomic with Plan 3a + 3b** per D-63-01.

---

### Plan 4 — DEBT-04: `v1.5-verification-evidence/run.sh` hardening

**Analog:** `.planning/milestones/v1.6-verification-evidence/run.sh` — written FRESH per D-46-10 specifically because v1.5/run.sh carried `DEFER-40-01` bugs. The v1.6 script's preamble (lines 1–17) names every bug Phase 63 must now backport to v1.5. v1.6 is the "after" state.

**Hotfix #1 — `/healthz` path** (CONTEXT.md "4 known hotfixes")

v1.5 today (line 45):
```bash
HEALTH_URL="${HEALTH_URL:-${BASE_URL%/api/v1}/healthz}"
```
This already says `/healthz` correctly — the hotfix is to confirm the construction is correct (verify the preflight curl actually hits it). v1.6 analog (line 47):
```bash
check "backend reachable on $BASE_URL/healthz (NOT the wrong path)" "curl -sf -o /dev/null $BASE_URL/healthz"
```

**Hotfix #2 — fixture-user email defaults** (`verify_*@local.dev`, not `@fixture.local`)

v1.5 today is already correct at lines 39 + 41:
```bash
RECEPTION_EMAIL="${RECEPTION_EMAIL:-verify_reception@local.dev}"
OWNER_EMAIL="${OWNER_EMAIL:-verify_owner@local.dev}"
```
v1.6 analog (lines 27–28):
```bash
OWNER_EMAIL="verify_owner@local.dev"
RECEPTION_EMAIL="verify_reception@local.dev"
```
**However** the legacy `@fixture.local` strings still appear inside scenario fixture lookups at v1.5 lines 76–77:
```bash
VERIFY_CLIENT_A=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM clients WHERE email='verify_smoke@fixture.local' LIMIT 1;")
VERIFY_CLIENT_B=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM clients WHERE email='verify_sale@fixture.local' LIMIT 1;")
```
These are **client** fixtures (different domain from operator users); verify against `scripts/seed_v1_4_verification_fixtures.py` whether the seed inserts `@fixture.local` or `@local.dev` for these client rows and align the SQL accordingly.

**Hotfix #3 — table name `trainer_availability_slots` (not `trainer_slots`)**

v1.5 today is **already correct** at lines 91, 124, 225 (uses `trainer_availability_slots`). The remaining risk is the API path `$BASE_URL/trainer-slots` (lines 96, 105, 107, 136, 171, 280, 340) — this is a route name, not a table name; verify against the backend router that the route is mounted at `/trainer-slots` (it is, per scenario 01 which already PASSes when run on a green stack).

**Hotfix #4 — Alembic 32-char limit**

Scan v1.5 for any `INSERT INTO`/`CREATE` statements that reference identifiers > 32 chars. None visible in current file body; this hotfix may already be resolved upstream in seed scripts. If present, truncate identifiers to ≤ 32 chars per PostgreSQL/Alembic operator constraint.

**Hotfix #5 — RBAC actor on `POST /trainer-slots`** (CONTEXT.md specifics)

v1.5 currently uses **reception** cookie jar for slot publish (lines 97–100, 136–139, 171–174, 280–283, 340–343):
```bash
curl -i -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  ...
```
Per the hotfix list, the actor must change. v1.6 analog: all `mut()` calls flow through the active `$COOKIE_JAR` after `login_as`. Verify which role can publish slots per the backend RBAC matrix; if owner-only, swap `$RECEPTION_COOKIE_JAR` → `$OWNER_COOKIE_JAR` on every `POST $BASE_URL/trainer-slots` site.

**Hotfix #6 — missing `X-CSRF-Token` header** (CONTEXT.md specifics, Phase 6 D-06-XSRF)

v1.5 has ZERO `X-CSRF-Token:` headers (`grep -n CSRF run.sh` returns nothing). v1.6 analog at lines 59–71 + 73–83 is the pattern to backport:
```bash
CSRF_TOKEN=""

login_as() {
  local email="$1" password="$2"
  rm -f "$COOKIE_JAR"
  curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -c "$COOKIE_JAR" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}" >/dev/null
  CSRF_TOKEN="$(awk '$6=="sportzal_csrf"{print $7}' "$COOKIE_JAR")"
  if [ -z "$CSRF_TOKEN" ]; then echo "login_as: failed to extract sportzal_csrf for $email" >&2; return 1; fi
  export CSRF_TOKEN
}

mut() {
  # mutating verb with CSRF threaded (POST/PUT/DELETE/PATCH)
  local method="$1" path="$2" body="${3:-}"
  local idem; idem="$(uuidgen)"
  curl -i -sS -X "$method" "$BASE_URL$path" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $idem" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    ${body:+-d "$body"}
}
```

**CLUB_BRAND placeholder note (D-62-02):** the cookie name `sportzal_csrf` in the `awk` line 68 above is the literal CSRF cookie name shipped by the backend (placeholder value retained per D-62-02). If hardening v1.5 today, use `sportzal_csrf` to match the running backend; do not rename to `clubcore_csrf` unless backend was also updated.

**Approach:** backport the `mut()` helper into v1.5/run.sh (or inline the `-H "X-CSRF-Token: $CSRF_TOKEN"` flag on every POST/PUT/DELETE/PATCH curl invocation). The v1.6 helper-function approach is cleaner; the inline approach is more localized (matches "line-level find-and-replace" framing in CONTEXT.md specifics).

**Revision log entry pattern** — add inside the runbook header (between current lines 28–29), per CONTEXT.md DEBT-04 ("revision-log entry inside the runbook"):
```bash
# Revision log:
#   2026-05-26 (Phase 63 DEBT-04): backport DEFER-40-01 hotfixes from v1.6/run.sh —
#     /healthz path, verify_*@local.dev fixture emails, trainer_availability_slots
#     table name, Alembic 32-char identifier limit, RBAC actor on POST /trainer-slots,
#     X-CSRF-Token threading on all mutating verbs (Phase 6 D-06-XSRF).
```

**Verification:** runbook executes end-to-end against a green stack without operator hotfix patches.

---

### Plan 5 — DEBT-05: CI verification (read-only, no source edits)

**Analog:** `.github/workflows/ci.yml` lines 38–51 — the 6 backend gates the sweep must satisfy.

**Operative pattern** (`.github/workflows/ci.yml:38-64`):
```yaml
- name: ruff check
  run: uv run ruff check

- name: ruff format --check
  run: uv run ruff format --check

- name: mypy
  run: uv run mypy

- name: lint-imports
  run: uv run lint-imports

- name: Export OpenAPI spec
  run: uv run python -m scripts.export_openapi

- name: Drift gate — apps/backend/openapi.json
  working-directory: ${{ github.workspace }}
  run: |
    git ls-files --error-unmatch apps/backend/openapi.json
    git diff --exit-code apps/backend/openapi.json
```

**Local re-run command sequence** (each must exit 0):
```bash
cd apps/backend
uv run ruff check
uv run ruff format --check
uv run mypy                                  # equivalent to `mypy --strict app` per pyproject.toml
uv run lint-imports
uv run python -m scripts.export_openapi
cd ../..
git diff --exit-code apps/backend/openapi.json
```

**Evidence channel per D-63-04:** capture GitHub Actions CI run URL (post-merge) in the Plan 5 commit message and `.planning/STATE.md` "Last activity". Optionally include exit codes per gate as a fallback `evidence:` line in the commit message (planner's call per D-63-04 trade-off note).

**No source edits in this plan** — it is execute-and-record only.

---

## Shared Patterns

### Atomic-Commit Discipline (PITFALLS C-07, restated by D-63-01)
**Source:** Phase 63 itself locks this in
**Apply to:** Plans 1, 2, 3, 4, 5 — each plan is exactly one commit. Never fuse a format pass with a check-fix pass or a mypy fix; each must be independently `git revert`-able and bisect-clean.
```bash
# Anti-pattern (never do this in Phase 63):
git commit -m "sweep: format + lint --fix + mypy"   # ✗ three concerns fused

# Pattern:
git commit -m "chore(backend): apply ruff format tree-wide (DEBT-01)"     # ✓
git commit -m "chore(backend): ruff check --fix safe-only (DEBT-02)"      # ✓
git commit -m "chore(backend): mypy strict cleanup + __all__ fix (DEBT-03)"  # ✓
git commit -m "chore(runbook): harden v1.5 verification script (DEBT-04)" # ✓
git commit -m "chore(ci): record post-sweep CI green run (DEBT-05)"       # ✓
```

### Zero-New-Suppressions Contract (D-63-06)
**Source:** CONTEXT.md decisions
**Apply to:** Plans 2, 3 (both DEBT-02 and DEBT-03)
- No new `# noqa: RULECODE` comments
- No new `# type: ignore[...]` comments
- No new `[[tool.mypy.overrides]] ignore_errors = true` entries on `app.*`
- No new `ignore_imports` in `.importlinter`
- No new `[tool.ruff.lint.per-file-ignores]` entries in `pyproject.toml` or `ruff.toml`

The single allowed config addition is the `tests.*` mypy override in Plan 3c (D-63-03) — scoped to `tests.*` only, never `app.*`.

### Safe-Only Auto-Fix Discipline (D-63-05 / PITFALLS C-06)
**Source:** PITFALLS C-06 — Protocol-based cross-module wiring is fragile under `--unsafe-fixes`
**Apply to:** every `ruff check --fix` invocation in Plan 2
```bash
# ✓ allowed
uv run ruff check --fix app tests

# ✗ forbidden in Phase 63 (silently strips Protocol-required params)
uv run ruff check --fix --unsafe-fixes app tests
```

### Scope Boundary (D-63-01 in-scope vs. Out-of-scope)
**Source:** CONTEXT.md domain block
**Apply to:** all 5 plans — sweep is `apps/backend/{app,tests,alembic,scripts}/**/*.py` only. Frontend (`apps/admin-web`) is JS/TS — separate toolchain, out of scope. `packages/ui` and `packages/api-client` are Phase A placeholders — no Python to sweep.

---

## No Analog Found

None — every Phase 63 work-unit has a strong pre-existing analog (existing config block, existing runbook to mirror, or existing CI workflow). This is consistent with the phase's purely-mechanical character: there is no "new feature shape" being introduced.

---

## Metadata

**Analog search scope:**
- `apps/backend/pyproject.toml` (existing mypy override blocks)
- `apps/backend/ruff.toml` (existing lint/format config)
- `apps/backend/app/modules/auth/models.py` (re-export discipline + Phase 41 INFRA-40 shim precedent)
- `.planning/milestones/v1.5-verification-evidence/run.sh` (target of Plan 4 hardening)
- `.planning/milestones/v1.6-verification-evidence/run.sh` (FRESH-written v1.6 runbook — the "after" state for v1.5)
- `.github/workflows/ci.yml` (defines the 6 CI gates Plan 5 verifies)

**Files scanned:** 6 direct analogs + auth module tree (15 files) for `__all__` discipline cross-reference

**Pattern extraction date:** 2026-05-26
