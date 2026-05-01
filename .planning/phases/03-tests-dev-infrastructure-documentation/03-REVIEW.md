---
phase: 03-tests-dev-infrastructure-documentation
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - apps/backend/.dockerignore
  - apps/backend/.gitignore
  - apps/backend/Dockerfile
  - apps/backend/README.md
  - apps/backend/docker-compose.yml
  - apps/backend/docs/adr/0001-modular-monolith.md
  - apps/backend/docs/adr/template.md
  - apps/backend/docs/architecture.md
  - apps/backend/docs/conventions.md
  - apps/backend/pyproject.toml
  - apps/backend/ruff.toml
  - apps/backend/scripts/backup_db.sh
  - apps/backend/scripts/seed_demo_data.py
  - apps/backend/tests/__init__.py
  - apps/backend/tests/conftest.py
  - apps/backend/tests/factories/__init__.py
  - apps/backend/tests/integration/__init__.py
  - apps/backend/tests/integration/test_healthz.py
  - apps/backend/tests/unit/__init__.py
  - apps/backend/tests/unit/test_security.py
findings:
  critical: 2
  warning: 6
  info: 5
  total: 13
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-01
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 3 lays down the test scaffolding (pytest + httpx ASGITransport + asgi-lifespan), a multi-stage uv-based Dockerfile, a docker-compose dev stack, two utility scripts, and a documentation set (architecture, conventions, ADR-0001, ADR template, README). Overall the code is careful: the Dockerfile correctly separates builder and runtime, drops to a non-root user, the compose stack gates `backend` behind a successful `migrate` job and a healthy Postgres, and the test fixtures wire `LifespanManager` correctly so `app.state.sessionmaker` is populated before tests run.

Two correctness blockers were found:

1. The README's "Variant 2: docker compose" path will fail out of the box because `.env.example` ships `DATABASE_URL` and `REDIS_URL` pointing to `localhost`, which from inside the `backend` container resolves to itself, not the `postgres` / `redis` services.
2. `pyproject.toml` declares no `[build-system]` table, so the second `uv sync --frozen --no-dev` step in the Dockerfile (which is supposed to install the project itself) and any local `uv sync` are relying on uv's default-backend fallback. This is brittle and either silently skips installing the project or fails on uv version drift; for a Phase A skeleton that must be reproducible, the build backend should be pinned explicitly.

In addition, several smaller robustness and hygiene issues are worth fixing before the next phase ships business code on top of this scaffolding.

## Critical Issues

### CR-01: docker compose Variant 2 cannot connect to Postgres / Redis with shipped .env.example

**File:** `apps/backend/.env.example:2`, `apps/backend/.env.example:5`, `apps/backend/README.md:20-26`, `apps/backend/docker-compose.yml:8`

**Issue:** `.env.example` defines:

```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal
REDIS_URL=redis://localhost:6379/0
```

`README.md` then instructs the user to run `cp .env.example .env && docker compose up`. The `backend` service in `docker-compose.yml` consumes that same `.env` via `env_file: .env`. Inside the `backend` container, `localhost` resolves to the backend container itself — there is no Postgres listening there, only the FastAPI process. The first request that touches the DB (and the `migrate` one-shot, since it shares the same `env_file`) will fail with a connection refused / timeout. Compose-network DNS for the configured services is `postgres` and `redis`, not `localhost`.

The same `.env` file therefore cannot serve both Variant 1 (local processes — `localhost`) and Variant 2 (compose — `postgres`/`redis`). The README's claim that Variant 2 is "всё включено" is false with the shipped defaults.

**Fix:** Either (a) make `.env.example` compose-first and document that Variant 1 needs to override the host, or (b) introduce an in-compose env override so the documented Quick start actually works. Option (b) is the smallest change:

```yaml
# docker-compose.yml — add to backend and migrate services:
  backend:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
      REDIS_URL: redis://redis:6379/0
    ...

  migrate:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
    ...
```

`environment:` overrides `env_file:` in compose, so Variant 1's `.env` (with `localhost`) keeps working for local `uv run uvicorn ...`, and Variant 2 gets the right service-DNS values automatically. Either way, the README must call out the trade-off explicitly so a fresh checkout does not silently break.

### CR-02: pyproject.toml has no [build-system] — `uv sync --frozen --no-dev` (project install) is unspecified behavior

**File:** `apps/backend/pyproject.toml:1-30`, `apps/backend/Dockerfile:25-26`

**Issue:** `pyproject.toml` declares `[project]` and `[tool.uv]` but does not declare `[build-system]`. The Dockerfile relies on a two-stage uv sync:

```dockerfile
RUN uv sync --frozen --no-install-project --no-dev   # deps only
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev                         # install project
```

The second `uv sync` is supposed to install the `sportzal-backend` project itself into `/app/.venv`. PEP 517/518 requires a `[build-system]` table to know which backend to use; without one, uv falls back to a default backend (currently hatchling-style auto-discovery), which depends on uv's version and the package layout. This is fragile in three ways:

1. Reproducibility: an older or future uv may pick a different default and either skip the project install (so `python -m app.main` would still work but `import sportzal_backend` style wouldn't) or fail outright.
2. Console scripts / entry points cannot be safely declared later without a build backend.
3. CI parity: `uv.lock` was generated under whatever backend uv picked at lock time; a fresh contributor with a different uv version may resolve differently.

The conventions doc treats `uv run` commands as the contract for everything (lint, type, test, alembic), so this scaffolding step needs to be deterministic, not "happens to work on Andre's laptop".

**Fix:** Declare the build backend explicitly. For a single-package layout under `app/`, hatchling is the conventional pick:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

Then re-lock with `uv lock` so `uv.lock` is consistent with the declared backend. Alternatively, if the project does not need to be installed as a package (only `app` is on `sys.path` via `WORKDIR /app`), drop the second `uv sync` from the Dockerfile and remove the `[project]` `name`/`version` machinery's implicit "this is installable" promise — but that is a larger refactor.

## Warnings

### WR-01: docker-compose.yml `backend` does not declare DB/Redis service-DNS overrides

**File:** `apps/backend/docker-compose.yml:5-17`

**Issue:** Beyond CR-01, `backend` only depends on `migrate` (completed) and `redis` (started). It does not depend on `postgres` directly. While transitively `migrate` depends on `postgres` healthy, if a future change ever splits `migrate` out (e.g., run migrations as a one-off command, not a compose service), `backend` will start with no Postgres ordering guarantee. Also, `redis` has no healthcheck, so `condition: service_started` only guarantees the Docker-level "process started", not "Redis is accepting connections". The first ARQ task — once Phase B+ adds them — could race a not-yet-ready Redis.

**Fix:** Add a `redis` healthcheck and switch backend's `depends_on` to use it; also add a direct `postgres: { condition: service_healthy }` to `backend` so the ordering is explicit and survives future refactors:

```yaml
  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 10

  backend:
    ...
    depends_on:
      migrate:
        condition: service_completed_successfully
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

### WR-02: `tests/conftest.py` `.env.example` parser silently drops malformed lines, does not strip quotes or inline comments

**File:** `apps/backend/tests/conftest.py:32-39`

**Issue:** The fallback parser reads `.env.example` and seeds `os.environ` so `Settings()` does not blow up at test collection. The implementation is:

```python
for _line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
    _stripped = _line.strip()
    if not _stripped or _stripped.startswith("#") or "=" not in _stripped:
        continue
    _key, _, _value = _stripped.partition("=")
    os.environ.setdefault(_key.strip(), _value.strip())
```

Three latent bugs:

1. **Inline comments not stripped.** A `KEY=value # comment` line is loaded as `KEY="value # comment"` — Pydantic-settings would then receive a literal trailing comment in the value. The current `.env.example` has no such lines, but the parser is presented as a generic `.env` reader and will bite the moment somebody adds `DATABASE_URL=postgres://... # async DSN`.
2. **Quoted values not unquoted.** `KEY="value"` produces a value that includes the quote characters. Standard `.env` parsers (python-dotenv) strip surrounding quotes; this one does not.
3. **No diagnostic on parse failure.** If `.env.example` is reformatted in a way the parser does not understand, tests proceed with a half-loaded environment and `Settings()` may fail later with a confusing error.

**Fix:** Either pull in `python-dotenv` (already a transitive dep candidate) or harden the parser:

```python
from shlex import split as _shlex_split
...
for _line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
    _stripped = _line.strip()
    if not _stripped or _stripped.startswith("#"):
        continue
    if "=" not in _stripped:
        continue
    _key, _, _value = _stripped.partition("=")
    _key = _key.strip()
    # Strip inline comments and surrounding quotes the same way dotenv does.
    _value = _value.strip()
    if _value and _value[0] in ('"', "'") and _value.endswith(_value[0]):
        _value = _value[1:-1]
    else:
        _value = _value.split(" #", 1)[0].rstrip()
    os.environ.setdefault(_key, _value)
```

### WR-03: `db_session` fixture issues `SELECT 1` outside an explicit transaction, then claims to "rollback on teardown"

**File:** `apps/backend/tests/conftest.py:58-76`

**Issue:** The fixture reads:

```python
async with sessionmaker() as session:
    try:
        await session.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(...)
    try:
        yield session
    finally:
        await session.rollback()
```

The connectivity probe (`SELECT 1`) is executed before the test starts. With SQLAlchemy 2.0 async, this autobegins a transaction on the session. By the time the test body runs, that transaction is already open and contains the probe. The test body's writes are appended to the same transaction, and the final `rollback()` rolls back everything — that part is correct.

However, two subtle issues remain:

1. The docstring claims `rolled back on teardown` (TEST-04 contract), but if `session.execute(text("select 1"))` succeeds and then the user's test does its own `await session.commit()` mid-test (a reasonable pattern when validating commit semantics), the teardown `rollback()` becomes a no-op and rows leak between tests. The conventional pattern is the SAVEPOINT-nested-transaction pattern (`begin_nested()` plus a connection-bound session) so commits inside the test body are reversible. As written, this fixture is "rollback-on-teardown only if the test never commits".
2. The fixture has no cleanup of the probe transaction before yielding. If a test wants a clean slate (no implicit BEGIN already issued), it does not get one.

This is not currently exercised — Phase A test bodies do not use `db_session` — but the fixture is held forward as the TEST-04 contract for Phase B+. Shipping this as the contract risks future tests passing locally and silently leaving committed state on the dev DB.

**Fix:** Adopt the standard async "join a connection-level transaction with savepoints" pattern, e.g.:

```python
@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    engine = app.state.engine
    async with engine.connect() as connection:
        try:
            await connection.execute(text("select 1"))
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"DATABASE_URL not reachable: {exc!r}")
        trans = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            try:
                yield session
            finally:
                await trans.rollback()
```

This guarantees rollback even if the test body commits, which is what TEST-04 implies.

### WR-04: `docker-compose.yml` postgres uses weak hardcoded password, exposed on host port 5432

**File:** `apps/backend/docker-compose.yml:27-39`

**Issue:** Postgres is configured with `POSTGRES_USER: app`, `POSTGRES_PASSWORD: app`, and exposed on `5432:5432`. For a dev-only loopback workflow this is conventional, but: (a) by binding `5432:5432` (not `127.0.0.1:5432:5432`) on Linux hosts the port may be reachable on the LAN, (b) the password is in version control, and (c) the doc invariants ("placeholder secret" — see `.env.example:14-15`) are not echoed here. A new contributor running `docker compose up` on a laptop on a coffee-shop network exposes a Postgres with `app:app` to anyone who can route to that host.

**Fix:** Bind explicitly to localhost and document the dev-only credential:

```yaml
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app          # dev-only, see .env.example
      POSTGRES_DB: sportzal
    ports:
      - "127.0.0.1:5432:5432"
```

### WR-05: `backup_db.sh` leaves a partial gzipped file behind on `pg_dump` failure

**File:** `apps/backend/scripts/backup_db.sh:15`

**Issue:**

```bash
docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$OUT"
```

With `set -o pipefail`, the script exits non-zero if `pg_dump` fails — that is correct. But the redirection has already created `$OUT` (a file with whatever `gzip` produced for the partial input — possibly an empty or corrupt gzip stream). The `stat`/`echo` trailer is skipped due to `set -e`, so the user does not even see "wrote 0 bytes". A caller running this from cron will accumulate broken archives and only notice when restoring.

**Fix:** Stage to a temp file and rename on success; remove on failure.

```bash
TMP="${OUT}.partial"
trap 'rm -f "$TMP"' EXIT
docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$TMP"
mv "$TMP" "$OUT"
trap - EXIT
SIZE=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
echo "Wrote $OUT (${SIZE} bytes)"
```

### WR-06: pytest `filterwarnings = ["error", ...]` will trip on first deprecation outside the pydantic ignore

**File:** `apps/backend/pyproject.toml:50-53`

**Issue:** `filterwarnings = ["error", "ignore::DeprecationWarning:pydantic.*"]` turns every warning into a hard test failure with one narrow ignore. SQLAlchemy 2.0 emits `LegacyAPIWarning` / `MovedIn20Warning` in some code paths, `httpx` periodically emits `DeprecationWarning`s on minor bumps, and `pytest-asyncio` 0.23+ emits its own deprecations around fixture loop scope. Once Phase B+ adds real DB calls or upgrades httpx/pytest-asyncio, the suite will start failing on cosmetic upstream changes that have nothing to do with our code.

**Fix:** Either keep the strict policy and add ignores per known third-party origin as they appear (with TODO references), or downgrade to a per-warning allowlist:

```toml
filterwarnings = [
    "error::Warning:app",                 # our code: warnings = errors
    "ignore::DeprecationWarning:pydantic.*",
    "ignore::DeprecationWarning:httpx.*",
    "ignore::DeprecationWarning:pytest_asyncio.*",
]
```

The current "fail on every upstream warning" stance is too aggressive for a project that pins to `>=` floors (e.g. `fastapi>=0.115`, `pytest-asyncio>=0.23`).

## Info

### IN-01: `.dockerignore` excludes `*.md` but not `.git/` parents — verify image size

**File:** `apps/backend/.dockerignore:1-10`

**Issue:** `.git/` is listed in `.dockerignore` but `apps/backend/` is built from its own directory by docker compose (`build: .`), so the only `.git` that exists at the build context root is whatever happens to be in `apps/backend/.git` (none — the repo root is two levels up). The `.git/` entry is therefore a no-op. Not harmful, but the comment header in the file should clarify which paths actually matter for the `apps/backend` build context.

**Fix:** Drop the `.git/` line or add a comment that this is for defense-in-depth in case the build context is ever moved to the repo root. Also consider adding `scripts/` (currently included in build context but not COPYed by Dockerfile — wasted upload).

### IN-02: `tests/conftest.py` env loader runs at import time, mutates global state

**File:** `apps/backend/tests/conftest.py:32-39`

**Issue:** The `.env.example` loader executes at module import (when pytest first collects `conftest.py`). It mutates `os.environ` with `setdefault`. This is fine for the single-process pytest run, but a) makes the conftest harder to reason about (side effect at import time), and b) leaks env vars to xdist worker processes spawned later, which then re-import conftest and re-`setdefault`. Subtle but worth flagging now.

**Fix:** Move the loader into a session-scoped autouse fixture so the side effect is bound to a fixture lifecycle rather than module import. Or: make it idempotent and obviously safe by guarding with `if "DATABASE_URL" in os.environ: return`.

### IN-03: `seed_demo_data.py` does nothing useful but ships `from __future__ import annotations`

**File:** `apps/backend/scripts/seed_demo_data.py:1-11`

**Issue:** The file is a documented Phase A placeholder, which is fine. The `from __future__ import annotations` line is dead weight — there are no annotations in the file. Trivial but inconsistent with the conventions doc's "Sparse comments. Prefer self-explanatory names" stance.

**Fix:** Drop the `from __future__` line until there is something annotation-bearing to import for. Optional.

### IN-04: `docker-compose.yml` mounts `./app:/app/app:ro` but Dockerfile already COPYed it — double source

**File:** `apps/backend/docker-compose.yml:11-12`, `apps/backend/Dockerfile:22`

**Issue:** The Dockerfile copies `app/` into the image at build time. The compose file then bind-mounts `./app` over `/app/app:ro` for hot-reload. This works (the bind mount shadows the COPYed copy), but it means two copies of the source exist in two different file-system layers, and any contributor reading the Dockerfile would reasonably assume the COPYed copy is the one running. Worth a one-line comment in `docker-compose.yml` next to the volume.

**Fix:** Add a comment to the volume entry explaining the dev override pattern:

```yaml
volumes:
  # Dev-only override: shadow the image's /app/app with the host source
  # so uvicorn --reload picks up edits. Production runs the COPYed copy.
  - ./app:/app/app:ro
```

### IN-05: Documentation typo / consistency — "сoло" vs "соло", "proverable"

**File:** `apps/backend/docs/conventions.md:4`, `apps/backend/docs/adr/template.md:15`

**Issue:** `docs/conventions.md:4` uses the English word "proverable" — likely meant "provable" (or in Russian, "проверяемые"). `docs/adr/template.md:15` uses "соло-разработчик" with a Latin "о" mid-word in one occurrence ("сoло"). Trivial but the docs are listed as canonical phase artifacts, so cosmetic noise hurts trust.

**Fix:** s/proverable/provable/ in `conventions.md`, audit `template.md` for stray Latin glyphs.

---

_Reviewed: 2026-05-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
