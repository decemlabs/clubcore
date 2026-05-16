---
phase: 36-milestone-verification-backend-only
plan: 01
subsystem: verification-infrastructure
tags: [verification, scaffold, seed, scripts, infrastructure, backend-only]
wave: 1
dependency_graph:
  requires: []
  provides:
    - "v1.4 verification baseline seed (idempotent fixtures)"
    - "scenario script scaffold + shared helper library"
    - "operator readiness gate (_preflight.sh)"
  affects:
    - apps/backend/scripts/
    - .planning/milestones/v1.4-verification-evidence/
tech_stack:
  added: []
  patterns:
    - "idempotent UUID5-keyed pg_insert(...).on_conflict_do_nothing"
    - "TM-29-02 anti-prod guard verbatim from v1.3 analog"
    - "Argon2id password hash from env var (≥12 char guard)"
    - "bash helper library sourced by scenario stubs (set -euo pipefail)"
    - "cookie-jar based auth (sz_access HTTP-only) — no Authorization: Bearer"
    - "per-scenario evidence tee via exec > >(tee FILE) 2>&1"
key_files:
  created:
    - apps/backend/scripts/seed_v1_4_verification_fixtures.py
    - apps/backend/scripts/verify/_lib.sh
    - apps/backend/scripts/verify/_preflight.sh
    - apps/backend/scripts/verify/01_sale_with_payment.sh
    - apps/backend/scripts/verify/02_refund_of_fresh_sale.sh
    - apps/backend/scripts/verify/03_refund_frozen_409.sh
    - apps/backend/scripts/verify/04_pt_package_sale.sh
    - apps/backend/scripts/verify/05_pt_session_record_active_trainer.sh
    - apps/backend/scripts/verify/06_pt_package_exhaustion.sh
    - apps/backend/scripts/verify/07_trainer_deactivation_409.sh
    - apps/backend/scripts/verify/08_cross_phase_smoke.sh
    - apps/backend/scripts/verify/README.md
    - .planning/milestones/v1.4-verification-evidence/.gitkeep
  modified: []
decisions:
  - "Authoritative auth contract = cookies (sz_access HTTP-only), NOT bearer JWT in login body — corrected plan's _lib.sh spec to remove the Authorization: Bearer header"
  - "Liveness endpoint is /healthz NOT /health — corrected preflight check"
  - "PATH-prepend /usr/local/opt/libpq/bin in _lib.sh and _preflight.sh — libpq is keg-only on macOS Homebrew, so psql is not on default PATH"
  - "Postgres creds are app:app per docker-compose.yml:62-66 — followed PATTERNS.md correction over CONTEXT.md text"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-16"
---

# Phase 36 Plan 01: Live-stack bring-up recipe + scenario scaffold Summary

Wave 1 verification infrastructure: deterministic v1.4 fixture seed, shared bash helper library, 8 scenario stubs with evidence-tee scaffold, operator readiness gate, and evidence directory placeholder — all committed across four atomic commits.

## What was built

### Seed script (`apps/backend/scripts/seed_v1_4_verification_fixtures.py`, 259 lines)

Idempotent v1.4 verification baseline per D-36-06:
- **Users (2):** `verify_owner@local.dev` (role=owner), `verify_reception@local.dev` (role=reception). Passwords sourced from `SEED_VERIFY_OWNER_PASSWORD` / `SEED_VERIFY_RECEPTION_PASSWORD` env vars; Argon2id-hashed via `app.core.security.hash_password`.
- **MembershipPlans (2):** `Verify Standard 30d` (freeze_days_limit=14, price 3000 RUB), `Verify Long 90d` (freeze_days_limit=30, price 7500 RUB).
- **PtPackagePlans (2):** `Verify PT-5` (5 sessions, 5000 RUB), `Verify PT-10` (10 sessions, 9000 RUB).
- **Trainers (3):** `Trainer Alpha` (active), `Trainer Beta` (active), `Trainer Gamma` (`is_active=False`, `deleted_at=NULL` — the deactivated-not-deleted state scenario 07 exercises).
- **Clients (4):** `verify_sale`, `verify_refund`, `verify_pt`, `verify_smoke` with phones `+7700000000{1..4}` and `<slug>@fixture.local` emails. No memberships at seed time — scenarios provision via the API.

Guards:
- TM-29-02 anti-prod guard verbatim from `seed_verification_fixtures.py` (refuse if `DATABASE_URL` lacks `localhost`/`postgres:5432`; never prints the URL itself).
- SECRET_KEY ≥48 byte pre-flight (v1.3 first-run-failure lesson — pyjwt InsecureKeyLengthWarning under `pyproject.toml [tool.pytest.ini_options].filterwarnings = ["error"]`).
- Password length ≥12 chars (NIST 800-63B 2024 + project policy).

Idempotency strategy: every fixture row gets a deterministic `uuid5(NAMESPACE_DNS, stable_key)` PK; `pg_insert(...).on_conflict_do_nothing(index_elements=["id"])` makes re-runs no-ops. **No natural-key UNIQUE on every column required** (sidesteps the per-model unique-constraint question).

### Helper library (`apps/backend/scripts/verify/_lib.sh`, 153 lines)

Sourced by every scenario. Exports:
- `BASE_URL` (default `http://localhost:8000`)
- `COOKIE_JAR` (per-script mktemp; auto-removed via `trap … EXIT`)
- `CSRF_TOKEN` (set by `login_as`; auto-injected by `mut`)
- `login_as <owner|reception>` — POST `/api/v1/auth/login`; extracts `sportzal_csrf` from Netscape cookie jar via `awk '$6=="sportzal_csrf"{print $7}'`.
- `mut <METHOD> <PATH> <JSON_BODY>` — curl wrapper that auto-attaches `Idempotency-Key: $(uuidgen)` (D-36-04), `X-CSRF-Token: $CSRF_TOKEN`, and reuses `$COOKIE_JAR` for auth via the `sz_access` HTTP-only cookie.
- `get <PATH>` — read-only GET (CSRF-exempt server-side).
- `psql_exec <SQL>` — `psql "postgresql://app:app@localhost:5432/sportzal" -c "$sql"`.
- `assert_status <expected_code>` — pipe-friendly HTTP status assertion.
- `assert_body_jq <jq_expr> <expected_value>` — pipe-friendly JSON body assertion.

Auto-prepends `/usr/local/opt/libpq/bin` to PATH so `psql_exec` works under macOS Homebrew (libpq is keg-only).

### 8 Scenario stubs (`apps/backend/scripts/verify/0{1..8}_*.sh`, 22 lines each)

Each stub:
- `set -euo pipefail`
- Sources `_lib.sh`
- Computes per-scenario `EVIDENCE=".planning/milestones/v1.4-verification-evidence/<NN>_<slug>.txt"`
- Tees stdout+stderr via `exec > >(tee "$EVIDENCE") 2>&1` per D-36-02
- Prints `=== scenario NN_xxx ===`, `started:`, `TODO 36-02: …`, `ended:`, `result: STUB`
- Executable bit set (`chmod +x`)

Wave 2 (Plan 36-02) fills the bodies incrementally without re-engineering the scaffold.

### README (`apps/backend/scripts/verify/README.md`, 33 lines)

Operator sweep recipe — pre-flight env vars, required tools, `docker compose up -d` → seed → `_preflight.sh` → loop `0*.sh`. Includes v1.3 5d force-recreate-vs-restart lesson.

### Preflight (`apps/backend/scripts/verify/_preflight.sh`, 78 lines)

Twelve-gate Wave 1 → Wave 2 readiness check:
1. `SECRET_KEY` ≥48 bytes
2. `SEED_VERIFY_OWNER_PASSWORD` ≥12 chars
3. `SEED_VERIFY_RECEPTION_PASSWORD` ≥12 chars
4. `curl` available
5. `jq` available
6. `uuidgen` available
7. `psql` available (libpq)
8. `docker compose` available
9. `gh` CLI authenticated (advisory — for 36-04 GHA cross-link)
10. `npx` available (for 36-05 openapi-to-postmanv2)
11. Backend reachable on `http://localhost:8000/healthz`
12. Postgres reachable on `postgresql://app:app@localhost:5432/sportzal`

Emits per-gate PASS/FAIL + red/green summary; exit 1 on any failure.

### Evidence directory (`.planning/milestones/v1.4-verification-evidence/.gitkeep`)

Committed empty directory placeholder — Wave 2 writes per-scenario evidence files here per D-36-26.

## Verification

### Seed
- Syntax check: `uv run python -c "import ast; ast.parse(...)"` → OK.
- `ruff check`: clean.
- `mypy --strict`: `Success: no issues found in 1 source file`.
- **First run** against live stack: `Seeded v1.4 verification fixtures: 2 users (1 owner + 1 reception), 2 membership plans, 2 PT-package plans, 3 trainers (2 active + 1 inactive), 4 clients.`
- **Idempotency proof** — second run produces identical output, post-condition counts unchanged:

```
users:2
membership_plans:2
pt_package_plans:2
trainers:3
trainers_active:2
clients:4
```

### _lib.sh
- `bash -n`: clean.
- Sourced cleanly with stub env vars; all 6 helpers (`login_as`, `mut`, `get`, `psql_exec`, `assert_status`, `assert_body_jq`) registered as functions.
- **Live-stack smoke**: `login_as owner` against the running backend returns `HTTP/1.1 200 OK`, cookie jar contains all three expected cookies (`sportzal_csrf`, `sz_refresh`, `sz_access`), and a subsequent `get /api/v1/auth/me` returns `{"data":{"id":"86fd126a-…","role":"owner","fullName":"Verify Owner",…}}`. CSRF extraction confirmed working (64-char hex token).

### 8 Stubs
- `bash -n` on all 8: zero errors.
- All 8 contain `source …/_lib.sh`, `EVIDENCE=".planning/milestones/v1.4-verification-evidence/…"`, `exec > >(tee …) 2>&1`, and `TODO 36-02`.
- **Scaffold smoke** — running each stub end-to-end produces `result: STUB` and writes the expected evidence file (verified with scenario 01):

```
=== scenario 01_sale_with_payment ===
started: 2026-05-16T17:56:47Z
TODO 36-02: scenario body not yet implemented — scaffold-only stub
ended: 2026-05-16T17:56:47Z
result: STUB
```

All 8 stubs exited 0 with `result: STUB` in the smoke run (output verbatim in commit `95f9db3`'s description).

### _preflight.sh
- `bash -n`: clean.
- **Live run** against the operator env: **11/12 PASS, 1/12 FAIL** (the gh-CLI auth failure is expected and documented in the orchestrator's `environment_facts` — `gh auth status` reports broken keyring auth; Wave 2/4 falls back to operator-paste per D-36-10). All other gates green including SECRET_KEY (64 bytes), backend `/healthz`, and postgres connectivity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed Authorization: Bearer header from `_lib.sh::mut`**
- **Found during:** Task 2 (writing _lib.sh)
- **Issue:** Plan task 2 specified `mut` should attach `Authorization: Bearer $ACCESS_JWT` extracted from the login response body. Reading `apps/backend/app/modules/auth/router.py:69-89` and `app/core/security.py:204-254` showed that `LoginResponse` body contains ONLY the `UserPublic` envelope — no access JWT — and auth flows via the `sz_access` HTTP-only cookie automatically when curl reuses the cookie jar.
- **Fix:** Removed all references to `ACCESS_JWT`. `mut` and `get` rely on `-b "$COOKIE_JAR"` for cookie-based auth.
- **Verified:** `login_as owner` followed by `get /api/v1/auth/me` returns the authenticated user without any Authorization header — confirming cookie auth works end-to-end.
- **Files modified:** `apps/backend/scripts/verify/_lib.sh`
- **Commit:** `99438e1`

**2. [Rule 1 - Bug] Corrected liveness endpoint `/health` → `/healthz` in `_preflight.sh`**
- **Found during:** Task 4 (writing _preflight.sh)
- **Issue:** Plan task 4 specified `curl -sf … http://localhost:8000/health`. The actual liveness endpoint is `/healthz` (Phase 2 D-14 Kubernetes contract — `app/api/v1/health.py:8` + `app/api/router.py:15`). `/health` returns 404.
- **Fix:** Changed the preflight check to target `/healthz`. Verified live: `curl -s http://localhost:8000/healthz` returns `{"status":"ok"}`.
- **Files modified:** `apps/backend/scripts/verify/_preflight.sh`
- **Commit:** `4548487`

**3. [Rule 3 - Blocking] PATH-prepend `/usr/local/opt/libpq/bin` in both `_lib.sh` and `_preflight.sh`**
- **Found during:** Setup (orchestrator-flagged environment_facts).
- **Issue:** macOS Homebrew installs libpq as keg-only — `psql` is at `/usr/local/opt/libpq/bin/psql` but NOT linked into `/usr/local/bin`. The plan's `_lib.sh::psql_exec` would have failed with `psql: command not found` on the operator's machine.
- **Fix:** Both `_lib.sh` and `_preflight.sh` prepend `/usr/local/opt/libpq/bin` to PATH at the top (only if the directory exists, so no-op on non-macOS hosts).
- **Verified:** Preflight gate 7 (`psql available`) and gate 12 (`postgres reachable`) both PASS.
- **Files modified:** `apps/backend/scripts/verify/_lib.sh`, `apps/backend/scripts/verify/_preflight.sh`
- **Commits:** `99438e1`, `4548487`

**4. [Rule 1 - Doc correction] Followed PATTERNS.md app:app credentials (not CONTEXT.md's sportzal:sportzal)**
- **Found during:** Task 2.
- **Issue:** CONTEXT.md `code_context` § "Integration Points" says `postgresql://sportzal:sportzal@…`. PATTERNS.md line 240 + `apps/backend/docker-compose.yml:62-66` are authoritative: creds are `app:app`.
- **Fix:** Used `app:app` everywhere (`_lib.sh::psql_exec`, `_preflight.sh` gate 12). No code regression — this was a doc-vs-code conflict resolved in favor of code/PATTERNS.
- **Files modified:** `apps/backend/scripts/verify/_lib.sh`, `apps/backend/scripts/verify/_preflight.sh`
- **Commits:** `99438e1`, `4548487`

### Authentication Gates

None during Wave 1 execution. The preflight surfaces the known operator `gh auth status` failure (orchestrator-documented in `environment_facts`) — Wave 2/4 handles via operator paste per D-36-10.

### Inherited Regression

**REG-36-01 (pre-Wave-1, commit `c05cb5b`)** — arq-worker compose `command: uv run arq` was unbootable; fixed to `command: arq`. This was applied BEFORE Wave 1 spawn and is captured here so the Wave 3 (Plan 36-05) `overrides:` block in `v1.4-VERIFICATION-LOG.md` picks it up. Not introduced by Plan 36-01 work itself.

## Operator runbook

```bash
cd apps/backend
docker compose up -d
docker compose exec migrate alembic upgrade head  # if not already current

# Set verification creds (the seed AND _lib.sh need these)
export SEED_VERIFY_OWNER_PASSWORD='Owner!Verify2026'
export SEED_VERIFY_RECEPTION_PASSWORD='Reception!Verify2026'
export VERIFY_OWNER_PASSWORD="$SEED_VERIFY_OWNER_PASSWORD"
export VERIFY_RECEPTION_PASSWORD="$SEED_VERIFY_RECEPTION_PASSWORD"

# Seed the v1.4 verification baseline (idempotent — safe to re-run)
uv run python -m scripts.seed_v1_4_verification_fixtures

# Confirm readiness
bash scripts/verify/_preflight.sh

# Wave 2 will run the scenarios:
# for s in scripts/verify/0*.sh; do bash "$s"; done
```

## Commits

1. `81417a8` — `feat(36-01): add seed_v1_4_verification_fixtures.py`
2. `99438e1` — `feat(36-01): add scripts/verify/_lib.sh shared helpers`
3. `95f9db3` — `feat(36-01): scenario scaffold (8 stubs) + README + evidence dir`
4. `4548487` — `feat(36-01): add scripts/verify/_preflight.sh readiness gate`

## Ready for Wave 2

- Plans 36-02 (scenarios), 36-03 (race tests), 36-04 (CI gates) can now start in parallel.
- Seed is idempotent — Wave 2 plans can safely re-invoke `seed_v1_4_verification_fixtures`.
- Evidence directory exists; Wave 2 writes per-scenario `*.txt` files into it.
- Preflight surfaces all readiness gaps before Wave 2 entry (currently: only `gh auth status`, which D-36-10 covers via operator paste).

## Self-Check: PASSED

All 14 expected artifacts present on disk; all 4 commit hashes verified in `git log --oneline --all`.
