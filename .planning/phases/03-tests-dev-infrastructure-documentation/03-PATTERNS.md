# Phase 3: Tests, Dev Infrastructure & Documentation — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 16 new + 1 modified
**Analogs found:** 8 in-repo (Phase 2 backend skeleton + Phase 2 PATTERNS conventions) / 17 total
**In-repo test/Docker/docs analogs:** NONE — no `tests/` directory, no `Dockerfile`, no `docker-compose.yml`, no `docs/`, no `scripts/` exist in the repo. Pattern source for those is **CONTEXT.md `<decisions>` D-01..D-15** which already contains the literal code shapes.

---

## Analog Availability Statement

The repo at the start of Phase 3 contains:

- **Phase 2 backend skeleton** at `apps/backend/` — usable as analog for Python style, mypy-strict idioms, import conventions, package layout, and `.env` shape.
- **Frontend** at `apps/admin-web/` — irrelevant to Phase 3 (tests are pytest, infra is Docker, docs are Russian-narrative + English-code; nothing maps from a Vite/Vitest/SPA codebase).
- **No prior tests/, no Dockerfile/compose, no docs/, no scripts/, no `tests/factories/`** — first time these surfaces appear in the repo. Phase 2 PATTERNS.md (`.planning/phases/02-backend-skeleton-with-quality-tooling/02-PATTERNS.md`) is the closest **process** analog (same "no in-repo code, lock literal shape in CONTEXT" situation).

Where no in-repo analog exists, the canonical pattern source is **CONTEXT.md `<decisions>`**:

| Surface | Source of truth |
|---------|-----------------|
| Test fixtures (`conftest.py`) | CONTEXT.md D-11 (literal fixture code) |
| Test DB strategy / skip behaviour | CONTEXT.md D-10 |
| pytest config | CONTEXT.md D-14 (literal TOML) |
| Dockerfile shape | CONTEXT.md D-01 / D-02 / D-03 / D-04 (literal Dockerfile fragments) |
| docker-compose shape | CONTEXT.md D-12 (literal YAML) |
| Compose hot-reload override | CONTEXT.md D-04 |
| `seed_demo_data.py` | CONTEXT.md D-13 (literal Python) |
| `backup_db.sh` | CONTEXT.md D-13 (literal bash) |
| `.dockerignore` content | CONTEXT.md D-13 |
| `architecture.md` sections | CONTEXT.md D-07 |
| `conventions.md` sections | CONTEXT.md D-08 |
| ADR-0001 + template | CONTEXT.md D-06 (MADR 4.0 skeleton) |
| `README.md` | CONTEXT.md D-09 (literal markdown) |
| `pyproject.toml` modifications | CONTEXT.md D-14 + D-15 |
| `asgi-lifespan` dev-dep | CONTEXT.md D-15 |

External canonical references (per CONTEXT.md `<canonical_refs>`): `pytest-asyncio` docs (auto mode), `httpx.ASGITransport`, `asgi-lifespan` README (`LifespanManager`), uv Docker integration guide, MADR 4.0 spec.

---

## File Classification

All files live under `apps/backend/` unless otherwise noted.

| New / Modified File | Role | Data Flow | Closest In-Repo Analog | Match Quality |
|---------------------|------|-----------|------------------------|---------------|
| `tests/__init__.py` | package-init | — | NONE | none |
| `tests/integration/__init__.py` | package-init | — | NONE | none |
| `tests/unit/__init__.py` | package-init | — | NONE | none |
| `tests/factories/__init__.py` | package-init (placeholder) | — | NONE | none |
| `tests/conftest.py` | test-fixtures | request-response + CRUD | `apps/backend/app/main.py`, `app/core/database.py` (consumed) | consumer-of-existing |
| `tests/integration/test_healthz.py` | integration-test | request-response | `apps/backend/app/api/v1/health.py` (system-under-test) | SUT-match |
| `tests/unit/test_security.py` | unit-test (placeholder) | — | `apps/backend/app/core/security.py` (SUT placeholder) | SUT-match |
| `pyproject.toml` (MODIFY) | config | — | `apps/backend/pyproject.toml` (extend in place) | exact (in-place) |
| `Dockerfile` | dev-infra | build | NONE — see CONTEXT.md D-01..D-04 | none |
| `docker-compose.yml` | dev-infra | orchestration | NONE — see CONTEXT.md D-12 | none |
| `.dockerignore` | config | — | `apps/backend/.gitignore` (style sibling) | style-match |
| `scripts/seed_demo_data.py` | utility-script (placeholder) | — | NONE — see CONTEXT.md D-13 | none |
| `scripts/backup_db.sh` | utility-script | file-I/O | NONE — see CONTEXT.md D-13 | none |
| `docs/architecture.md` | documentation | — | NONE | none |
| `docs/conventions.md` | documentation | — | NONE | none |
| `docs/adr/0001-modular-monolith.md` | documentation (ADR) | — | NONE — MADR 4.0 spec | external |
| `docs/adr/template.md` | documentation (ADR template) | — | NONE — MADR 4.0 spec | external |
| `README.md` | documentation | — | `apps/admin-web/README.md` (style only — sibling app README) | style-only |

Match-quality legend:
- **SUT-match** — the analog is the system under test, not a code-pattern donor. Test imports it.
- **consumer-of-existing** — the new file consumes Phase 2 internals (`create_app`, `app.state.sessionmaker`, `Settings`); no pattern to copy, but tight coupling to those shapes.
- **style-only / style-match** — borrows formatting/header style only, no code.
- **external** — pattern source is an external spec (MADR 4.0), no in-repo analog.

---

## Pattern Assignments

### Wave A — Tests (TEST-01..04)

---

#### `apps/backend/tests/conftest.py` (test-fixtures)

**Analog:** NONE for the fixture pattern itself. The file is a *consumer* of:
- `apps/backend/app/main.py:21` — `def create_app() -> FastAPI` factory (per-test instantiation per Phase 2 main.py docstring lines 4-5).
- `apps/backend/app/core/database.py:21-40` — `db_lifespan` puts `app.state.sessionmaker` in scope.
- `apps/backend/app/core/config.py:10-23` — `Settings` shape (only relevant if a test wants to override env via `monkeypatch.setenv` before `create_app()`).

**Primary pattern source — CONTEXT.md D-11** (literal fixture code):

```python
# tests/conftest.py
import pytest_asyncio
from collections.abc import AsyncIterator
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from asgi_lifespan import LifespanManager

from app.main import create_app

@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    _app = create_app()
    async with LifespanManager(_app):
        yield _app

@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        yield session
        await session.rollback()
```

**Critical constraints (from CONTEXT D-10/D-11/D-15 + Phase 2 D-08 docstring):**
1. **Per-test `create_app()`** — function-scope. No module-level app singleton.
2. **`LifespanManager` from `asgi-lifespan`** — without it `httpx.ASGITransport` does not fire FastAPI lifespan, so `app.state.sessionmaker` stays unset. Add `asgi-lifespan>=2.1` to `[tool.uv] dev-dependencies`.
3. **`pytest-asyncio` auto mode** (per `pyproject.toml` `[tool.pytest.ini_options] asyncio_mode = "auto"`) — no `@pytest.mark.asyncio` decorators.
4. **Type returns are `AsyncIterator[...]` from `collections.abc`** — same convention as `app/core/database.py:43` `get_db` (mypy-strict pattern from Phase 2 PATTERNS line 263).
5. **`db_session` rolls back, never commits** — Phase A has no business writes; preserves the contract for Phase B+.
6. **`db_session` is unused in Phase A test bodies** but defined per TEST-01 (CONTEXT Specifics line 366). Do NOT delete it.
7. **DB-reachability skip** (D-10): if `DATABASE_URL` unset/unreachable, `db_session` does `pytest.skip(reason="DATABASE_URL not reachable; run `docker compose up postgres` first")`. Implement as a connectivity check inside the fixture (try a trivial `await session.execute(text('select 1'))` wrapped in try/except OSError/ConnectionError → skip).

**mypy-strict reminders (Phase 2 PATTERNS line 612-616):**
- Use `AsyncIterator[FastAPI]`, not `AsyncGenerator[FastAPI, None]`.
- Module-level `from __future__ import annotations` is OK but not required at Python 3.12.

---

#### `apps/backend/tests/integration/test_healthz.py` (integration-test)

**Analog (system under test):** `apps/backend/app/api/v1/health.py:1-11` — the entire `/healthz` endpoint:

```python
"""Health check endpoint (D-14, API-03)."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe. Returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}
```

**Pattern (no in-repo test analog — derive from CONTEXT D-11 fixtures + canonical httpx ASGITransport pattern):**

```python
"""Integration test: GET /healthz returns 200 with the documented body."""
import uuid
from httpx import AsyncClient


async def test_healthz_returns_200_and_status_ok(async_client: AsyncClient) -> None:
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_emits_request_id_header(async_client: AsyncClient) -> None:
    """Phase 2 D-09: RequestIdMiddleware echoes X-Request-ID. Proves middleware
    is wired under ASGITransport, which means LifespanManager + create_app() work."""
    response = await async_client.get("/healthz")
    assert "x-request-id" in {k.lower() for k in response.headers}
    # Generated id must be a valid UUID4 (per RequestIdMiddleware.dispatch).
    uuid.UUID(response.headers["x-request-id"])
```

**Why two assertions:**
- The body assertion satisfies TEST-02 verbatim ("returns 200 + correct body").
- The `x-request-id` assertion is a free win — it proves middleware fires under `httpx.ASGITransport`, catching a class of "tests pass but middleware is silently bypassed" bugs. Source: CONTEXT `<code_context>` line 339 ("test_healthz.py can additionally assert this header is a valid UUID4 — proves middleware wiring under ASGITransport").

**No DB needed** — `/healthz` makes no DB call (CONTEXT D-10). This test runs cleanly without `docker compose up postgres`.

---

#### `apps/backend/tests/unit/test_security.py` (unit-test placeholder)

**Analog (system under test):** `apps/backend/app/core/security.py` — empty placeholder module per Phase 2 BE-05 (docstring only, no functions yet).

**Pattern:** Minimal passing placeholder per TEST-03 ("минимальный placeholder тест, который проходит"):

```python
"""Placeholder unit test for app.core.security.

Phase A has no real auth logic (BE-05). This test exists so the unit suite
is non-empty and pytest discovery works. Real tests for password hashing /
JWT issue/verify land in Phase C+.
"""
import app.core.security  # noqa: F401  -- import smoke-test only


def test_security_module_is_importable() -> None:
    """Smoke: importing app.core.security must not raise."""
    # Importing the module above already proves this. The assertion is
    # intentionally trivial — promoted to a real assertion in Phase C+.
    assert True
```

**Constraints:**
- **Pure-Python, no DB** (CONTEXT D-10).
- **No `from app.core.security import *`** — the module is intentionally empty; star-import would be a lint nag.
- **No async** — sync `def test_*` is fine. `pytest-asyncio` auto-mode does not apply async machinery to sync defs.
- **No future-leaning import contracts** — do NOT pull `passlib`, `jose`, etc. They are not in `pyproject.toml` dependencies.

---

#### `apps/backend/tests/factories/__init__.py` (package-init placeholder)

**Pattern:** Empty file per TEST-04. CONTEXT.md `<deferred>` line 377 confirms factory-boy lands in Phase B+.

```
(empty file, 0 bytes)
```

**Do NOT** add a docstring — that would be a non-trivial change later when factories actually appear, requiring a diff to the docstring. Empty is the contract.

---

#### `apps/backend/tests/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py` (package-init)

**Pattern:** Empty files. Required so pytest discovery + import-linter (if it ever scans tests; currently it doesn't) treat `tests` as a regular package.

**Note:** `pytest` does NOT strictly require `__init__.py` in test packages with default rootdir-based discovery, but having them avoids the well-known "duplicate basename" pytest error if any future test files share names across `unit/` and `integration/`. Cheap insurance — adopt.

---

### Wave B — Pyproject changes

---

#### `apps/backend/pyproject.toml` (MODIFY)

**Analog:** Itself — extend in place. Phase 2 PATTERNS already locked the file shape (`.planning/phases/02-backend-skeleton-with-quality-tooling/02-PATTERNS.md` lines 86-109). Phase 3 adds two things:

**Addition 1 — `[tool.pytest.ini_options]` (CONTEXT D-14, literal):**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:pydantic.*",
]
```

**Addition 2 — extend `[tool.uv] dev-dependencies` (CONTEXT D-15):**

Append `"asgi-lifespan>=2.1"` to the existing list (current state at `apps/backend/pyproject.toml:23-29`). Final list:

```toml
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

**Constraints:**
- **Do NOT migrate to PEP-735 `[dependency-groups]`** — Phase 2 D-15 explicitly locked `[tool.uv] dev-dependencies` shape (`apps/backend/pyproject.toml:20-21` carries the comment).
- **Do NOT touch `[project] dependencies`** — `asgi-lifespan` is dev-only (CONTEXT D-15 line 287). Production Docker runtime stage (D-02 `uv sync --no-dev`) MUST exclude it.
- **Keep `filterwarnings = ["error", ...]`** — turning warnings into errors is intentional; the targeted ignore for `pydantic` deprecation noise is the only carve-out.

---

### Wave C — Docker / compose (INFRA-01, INFRA-02)

---

#### `apps/backend/Dockerfile` (dev-infra)

**Analog:** NONE in repo. Pattern source — CONTEXT D-01 / D-02 / D-03 / D-04 (literal fragments). Builder & runtime stage shape:

**Stage 1: builder (CONTEXT D-01, D-02):**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Layer split: deps-only first (cache-stable), then project source.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
```

**Stage 2: runtime (CONTEXT D-01, D-03):**

```dockerfile
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

**Critical constraints (CONTEXT.md D-01..D-04):**
1. **Pin `slim-bookworm`, not bare `slim`** (D-01) — avoids silent Debian version drift.
2. **Two `uv sync` invocations** (D-02) — first deps-only with `--no-install-project`, second after `COPY app` to install the project. Cache mount on `/root/.cache/uv` keeps deps layer stable.
3. **`--no-dev` on both syncs** — production runtime image excludes ruff/mypy/import-linter/pytest/asgi-lifespan.
4. **Non-root `app` user** (D-03) — `groupadd --system` + `useradd --system --gid app --create-home`.
5. **CMD matches Phase 2 verification command exactly** — `uvicorn app.main:create_app --factory ...`. NOT `python -m app` and NOT `gunicorn`.
6. **NO `alembic upgrade head` in CMD/ENTRYPOINT** (D-03) — migrations are a compose-orchestration concern (the separate `migrate` service in D-12).
7. **NO `Dockerfile.dev`** (D-04) — hot-reload lives in compose override only.

**uv binary in runtime:** D-01 says final stage does NOT carry `uv`. The `.venv` from the builder is copied via `COPY --from=builder`, and `uvicorn` is invoked from the venv on PATH. If a future phase needs `uv` at runtime (it won't in Phase A), revisit.

---

#### `apps/backend/docker-compose.yml` (dev-infra)

**Analog:** NONE. Pattern source — CONTEXT D-12 (literal compose YAML, reproduced verbatim below).

**Full literal shape (CONTEXT D-12):**

```yaml
services:
  backend:
    build: .
    command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app:ro
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_started

  migrate:
    build: .
    command: alembic upgrade head
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: sportzal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d sportzal"]
      interval: 2s
      timeout: 2s
      retries: 10
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7

volumes:
  postgres-data:
```

**Critical constraints (CONTEXT D-04, D-12):**
1. **`migrate` is a separate one-shot service** (D-12) — not a backend ENTRYPOINT prefix. Idempotent `alembic upgrade head` (no-op against empty `versions/.gitkeep` in Phase A) — this is what retires Phase 2 SC #5.
2. **Postgres healthcheck via `pg_isready`** (D-12) — required so `migrate` waits. `interval: 2s`, `retries: 10`.
3. **`backend.depends_on.migrate.condition: service_completed_successfully`** — backend never starts before migrations finish, even on first boot.
4. **Backend command override = `uvicorn ... --reload --reload-dir /app/app`** (D-04). Hot-reload is a compose-only concern.
5. **`./app:/app/app:ro`** bind-mount (D-04 / D-12) — read-only mount; uvicorn watches it for reload.
6. **DSN values in `.env` already match `app/app/sportzal`** (CONTEXT `<code_context>` line 341) — same `.env` works for both local-uv and compose. Do NOT introduce a separate `.env.compose`.
7. **Postgres `5432` IS exposed; backend `8000` IS exposed; redis is NOT exposed** (D-12) — no host-side use of redis in Phase A.
8. **Named volume `postgres-data`** (D-12) — survives `docker compose down`, dropped via `docker compose down -v`.
9. **No `version:` key at the top** — modern compose ignores it; Phase 2 PATTERNS-grade convention is "minimal".

**Env contract reminder:** Settings shape from `apps/backend/app/core/config.py:10-23` requires `DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT`, `DEBUG`, `SECRET_KEY`. All five are already present in `apps/backend/.env.example:1-15`. The compose `env_file: .env` directive picks them up unchanged.

---

#### `apps/backend/.dockerignore` (config)

**Analog:** `apps/backend/.gitignore` (style sibling — not a 1:1 copy). The two files share intent ("don't include build/cache artifacts") but `.dockerignore` is broader (also excludes `tests/`, `docs/`, `*.md`, `.env*` to keep build context lean and prevent dev artifacts leaking into the image).

**Pattern source — CONTEXT D-13:**

```
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
__pycache__/
tests/
docs/
*.md
.env*
.git/
```

**Constraints:**
- **Exclude `tests/` and `docs/` from build context** — they're not needed at runtime and bloat the image.
- **Exclude `.env*`** — never bake secrets into images. Compose injects via `env_file`.
- **Keep `pyproject.toml` and `uv.lock` IN the build context** — Dockerfile `COPY` them. Do NOT add them to `.dockerignore`.
- **Keep `app/` IN the build context** — same reason.

---

### Wave D — Scripts (INFRA-03, INFRA-04)

---

#### `apps/backend/scripts/seed_demo_data.py` (utility-script placeholder)

**Analog:** NONE. Pattern source — CONTEXT D-13 (literal Python).

**Full literal shape:**

```python
"""Phase A placeholder. Real seeding lands in Phase B+ when business modules exist."""

def main() -> int:
    print("Phase A: no data to seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Constraints (CONTEXT D-13):**
1. **No DB connection** — pure Python, runs without compose.
2. **No `app.*` imports** — does not require `Settings` to be valid.
3. **`uv run python apps/backend/scripts/seed_demo_data.py` works from a fresh checkout** — no setup needed.
4. **Exit code 0** — TEST-IDA-style verifier expects clean exit.
5. **Output text exactly `"Phase A: no data to seed"`** — INFRA-03 verifier may grep for it.

---

#### `apps/backend/scripts/backup_db.sh` (utility-script, file-I/O)

**Analog:** NONE. Pattern source — CONTEXT D-13 (literal bash).

**Full literal shape:**

```bash
#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./backups/sportzal-$(date -u +%Y%m%dT%H%M%SZ).sql.gz}"
mkdir -p "$(dirname "$OUT")"
docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$OUT"
echo "Wrote $OUT ($(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT") bytes)"
```

**Constraints (CONTEXT D-13):**
1. **`#!/usr/bin/env bash`** — portable shebang.
2. **`set -euo pipefail`** — fail loudly on any error / undefined var / pipe failure.
3. **UTC timestamp** (`date -u +%Y%m%dT%H%M%SZ`) — DST-safe, matches CLAUDE.md TZ pattern (Europe/Moscow display + UTC storage).
4. **Default output `./backups/sportzal-<utc>.sql.gz`**, overridable via `$1`.
5. **`docker compose exec -T postgres pg_dump`** — uses compose-network Postgres, host doesn't need `pg_dump` installed.
6. **`gzip`** — compressed output, satisfies SC #3 ("non-empty pg_dump output file").
7. **`stat -f%z` (BSD/macOS) || `stat -c%s` (GNU/Linux)** — portable size reporting.
8. **`chmod +x`** — file MUST be committed executable. Verify with `ls -l` after writing.
9. **Targets compose-network Postgres** — fails cleanly if compose isn't running (acceptable Phase A behaviour).

---

### Wave E — Documentation (DOCS-01..04)

---

#### `apps/backend/docs/architecture.md` (documentation)

**Analog:** NONE in repo. Sibling references:
- `apps/backend/.importlinter:1-34` — three contracts to quote verbatim in the "Архитектурные инварианты" section.
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-CONTEXT.md` D-01..D-14 — invariants list source.
- `apps/backend/app/main.py:21-44` — factory composition order (referenced in invariants).
- `apps/backend/app/core/middleware.py:48-62` — REVERSED `add_middleware` order (referenced in invariants).
- `apps/backend/app/core/database.py:21-40` — `db_lifespan` pattern (referenced in invariants).

**Section structure — CONTEXT D-07 (literal):**

```
## Обзор                       (Russian narrative; link to ADR-0001)
## Слои                        (core / modules / integrations / workers / api — что делает / НЕ делает / правила импорта)
## Архитектурные инварианты    (compressed list from Phase 2 D-01..D-14)
## Запреты на Phase A          (no multi-tenancy, no auth, no business tables, no Stripe — ЮKassa-only)
## Диаграмма                   (ASCII-only; mermaid forbidden — D-07)
```

**Mixed-language rule (CONTEXT D-05):**
- Headings + narrative + reasoning → Russian.
- Code blocks + commands + identifiers (`uv`, `ruff`, `mypy`, `import-linter`, `httpx ASGITransport`, file paths) → English.
- Library names stay in canonical English form.

**Invariants must enumerate (from Phase 2 D-01..D-14):**
- `core ⊥ modules` (`.importlinter` contract `core-not-depend-on-modules`)
- `modules ⊥ modules` (`.importlinter` contract `modules-independent`)
- `integrations ⊥ modules` (`.importlinter` contract `integrations-not-depend-on-modules`)
- factory pattern (`app.main:create_app`, `--factory` flag)
- lifespan-managed engine (`app.state.engine`, `app.state.sessionmaker`)
- `register_middleware` REVERSED add order
- exception handler placement (`register_exception_handlers` in `create_app()`, not as decorators)
- `/healthz` mount via empty-prefix v1 router (Phase B+ TODO to add `/api/v1`)

**ASCII diagram skeleton (suggestion):**

```
                ┌─────────────────────────────────────┐
                │           api / v1 routers         │
                └────────────────┬────────────────────┘
                                 │
                ┌────────────────▼────────────────────┐
                │        modules.{auth,members,…}     │  ─┐
                └────────┬──────────────┬─────────────┘   │ independence
                         │              │                 │
                ┌────────▼──────┐  ┌────▼────────────┐    │
                │    core       │  │ integrations    │ ◄──┘ (forbidden ↔ modules)
                │ (config, db,  │  │ (telegram,email)│
                │  logging,…)   │  │                 │
                └───────────────┘  └─────────────────┘
                         ▲                  ▲
                         │                  │
                         └──────────────────┘
                            allowed: integrations → core
```

---

#### `apps/backend/docs/conventions.md` (documentation)

**Analog:** NONE in repo. Sibling references:
- `apps/backend/.importlinter:1-34` — quoted in `## Quality gates`.
- `apps/backend/ruff.toml` — rule list source.
- `apps/backend/pyproject.toml:31-43` — mypy strict + pydantic plugin, alembic.env override.
- `apps/backend/app/core/exceptions.py` — AppError hierarchy reference.
- `apps/backend/app/core/logging.py` + Phase 2 D-15 — structlog renderer policy.

**Section structure — CONTEXT D-08 (literal):**

```
## Naming        (Python: snake_case modules, PascalCase classes, UPPER_SNAKE constants; test files `test_*.py`)
## Imports       (stdlib / third-party / app.*; cross-module imports inside app.modules forbidden — events / explicit service interfaces in Phase B+)
## Quality gates (ruff E/F/I/B/UP/ASYNC/S/DTZ/N/SIM/RUF; mypy strict; import-linter 3 contracts; all via `uv run`)
## Testing       (MANDATORY — ASGITransport, pytest-asyncio auto, fixtures app/async_client/db_session, /healthz integration pattern, tests/{integration,unit,factories}/)
## Logging       (structlog, request_id/path/method contextvars, ConsoleRenderer dev / JSONRenderer staging+prod)
## Errors        (AppError hierarchy from Phase 2 D-12, register_exception_handlers in create_app())
## Migrations    (alembic async, `alembic upgrade head`, versions/.gitkeep — Phase A пуст; future-naming placeholder)
```

**`## Testing` section MUST include (CONTEXT D-08 + Specifics line 367):**
- ASGITransport rationale (`httpx ASGITransport` instead of real network — CLAUDE.md constraint).
- `pytest-asyncio` auto mode (no `@pytest.mark.asyncio`).
- Fixtures `app` / `async_client` / `db_session` from `tests/conftest.py` (CONTEXT D-11).
- Why `asgi-lifespan.LifespanManager` is required (without it `app.state.sessionmaker` is unset under ASGITransport — DO NOT remove "for being unused").
- `tests/{integration,unit,factories}/` layout.
- `/healthz` integration test pattern (link to `tests/integration/test_healthz.py`).

**`## Quality gates` MUST quote three import-linter contract names verbatim:**
- `core-not-depend-on-modules`
- `modules-independent`
- `integrations-not-depend-on-modules`

These are `[importlinter:contract:*]` keys at `apps/backend/.importlinter:5,13,27`. Doc and enforcement file stay in sync.

**Mixed-language rule (CONTEXT D-05):** same as architecture.md.

---

#### `apps/backend/docs/adr/0001-modular-monolith.md` (documentation, ADR)

**Analog:** NONE in repo. External spec: MADR 4.0 (https://adr.github.io/madr/).

**Section structure — CONTEXT D-06 (literal MADR 4.0 skeleton):**

```markdown
# ADR-0001: Modular Monolith с физическим разделением core / modules / integrations / workers / api

- Status: accepted
- Date: 2026-05-01
- Deciders: Andre

## Context and Problem Statement
## Decision Drivers
## Considered Options
## Decision Outcome
### Consequences
## Pros and Cons of the Options
```

**Mandatory content beats:**
- **Context** — single-developer pet project, modular monolith over microservices, regional constraints (Russia/CIS — Stripe forbidden, ЮKassa-only, Telegram primary).
- **Decision Drivers** — solo backend dev with AI agents (CLAUDE.md Core Value), no rewrites as features grow, locally-enforceable architectural rules (ruff + mypy + import-linter from day one).
- **Considered Options** — Modular Monolith (chosen), Microservices (rejected: ops cost), Layered/Clean Architecture (rejected: vertical slices preferred), Plain monolith without import contracts (rejected: degrades fast).
- **Decision Outcome** — modular monolith with physical separation; reference Phase 2 D-01..D-14.
- **Consequences** — `modules → modules` cross-imports forbidden; cross-feature interaction goes through events / explicit service interfaces (Phase B+); test isolation via `create_app()` factory; engine lifespan-bound.
- **Pros/Cons** — table per option; canonical MADR shape.

**Mixed-language rule (CONTEXT D-05):**
- Headings + narrative → Russian.
- Library names + commands + filenames → English.

---

#### `apps/backend/docs/adr/template.md` (documentation, ADR template)

**Analog:** NONE. Pattern source — CONTEXT.md `<specifics>` line 363 ("drop a `docs/adr/template.md` (MADR skeleton) so the next ADR is one `cp` away") + MADR 4.0 spec.

**Pattern (literal MADR 4.0 skeleton, fields blank):**

```markdown
# ADR-NNNN: <Краткое название решения>

- Status: proposed | accepted | deprecated | superseded by ADR-XXXX
- Date: YYYY-MM-DD
- Deciders: <имена>

## Context and Problem Statement
<...>

## Decision Drivers
- <driver 1>
- <driver 2>

## Considered Options
- Option A: <...>
- Option B: <...>

## Decision Outcome
Chosen option: "Option X", because <...>

### Consequences
- Good, because <...>
- Bad, because <...>

## Pros and Cons of the Options

### Option A
- Good, because <...>
- Bad, because <...>

### Option B
- Good, because <...>
- Bad, because <...>
```

**Constraints:**
- Identical section set to ADR-0001 — copy-paste-rename usage (`cp template.md 0002-events.md` then edit).
- Status line uses MADR 4.0 wording (`proposed | accepted | deprecated | superseded by ADR-XXXX`).

---

#### `apps/backend/README.md` (documentation)

**Analog (style-only):** `apps/admin-web/README.md` — sibling app README, sets the bar for "what an `apps/*` README looks like in this repo". No code to copy; tone reference only.

**Section structure — CONTEXT D-09 (literal):**

```markdown
# sportzal-backend

<2-3 строки описания проекта, Russian>

## Quick start

### Вариант 1: локально (требует внешний Postgres + Redis)
\`\`\`bash
cp .env.example .env
uv sync
uv run uvicorn app.main:create_app --factory
# → http://localhost:8000/healthz
\`\`\`

### Вариант 2: docker compose (всё включено)
\`\`\`bash
cp .env.example .env
docker compose up
# → backend на :8000, postgres:16 на :5432, redis:7 на :6379
\`\`\`

## Команды
\`\`\`bash
uv run pytest               # тесты (httpx ASGITransport)
uv run ruff check .          # линтер
uv run ruff format .         # форматирование
uv run mypy app              # type check (strict)
uv run lint-imports          # архитектурные контракты
uv run alembic upgrade head  # применить миграции (в Phase A — ноль миграций)
\`\`\`

## Документация
- docs/architecture.md — модульный монолит, инварианты
- docs/conventions.md — стиль кода, тестирование, миграции
- docs/adr/ — ADR-каталог (0001 — modular monolith)
```

**Critical constraints (CONTEXT D-09):**
1. **Both paths first-class** — no "advanced users" footnote on the compose path; no "fastest" badge on the local path.
2. **Local-uv path lists Postgres+Redis as external prereq** — does NOT pretend the user can run without them.
3. **Compose path lists exact ports** — `:8000`, `:5432`, `:6379` (only Postgres and backend reach the host; redis stays in compose network — match `docker-compose.yml` D-12).
4. **`Команды` section MUST list all five quality gates** (`pytest`, `ruff check`, `ruff format`, `mypy`, `lint-imports`) — same five Phase X+ CI would run (CONTEXT `<code_context>` line 355).
5. **Mixed-language rule (CONTEXT D-05)** — section headings + descriptions in Russian; commands in English.

---

## Shared Patterns

### Phase 2 Code Reuse (Tests)

**Apply to:** `tests/conftest.py`, `tests/integration/test_healthz.py`

| What is consumed | Source | Why |
|------------------|--------|-----|
| `create_app()` factory | `apps/backend/app/main.py:21` | Per-test app instantiation — no globals (Phase 2 main.py docstring lines 4-5) |
| `app.state.sessionmaker` | `apps/backend/app/core/database.py:35-36` | `db_session` fixture pulls per-app sessionmaker |
| `Settings` shape | `apps/backend/app/core/config.py:10-23` | Tests can `monkeypatch.setenv` then `get_settings.cache_clear()` |
| `RequestIdMiddleware` echo header | `apps/backend/app/core/middleware.py:15-30` | `test_healthz` asserts `x-request-id` header is valid UUID4 |

**Constraint:** `from app.main import create_app` is the ONLY way to obtain a `FastAPI` instance in tests. Never `from app.main import app`.

---

### Mixed-Language Documentation Style (CONTEXT D-05)

**Apply to:** `architecture.md`, `conventions.md`, `adr/0001-modular-monolith.md`, `adr/template.md`, `README.md`

**Rule:**
- **Russian:** narrative paragraphs, section headings (`## Обзор`, `## Тестирование`), conceptual explanations, ADR Context/Drivers/Outcome prose.
- **English:** code blocks, command examples, file paths, identifiers, library names (`uv`, `ruff`, `mypy`, `import-linter`, `httpx ASGITransport`, `pytest-asyncio`), env-var names (`DATABASE_URL`, `REDIS_URL`).

**Anti-patterns:**
- Translating `httpx ASGITransport` → "ASGI-транспорт httpx".
- Writing prose in English "because the rest of the codebase is".
- Mixing within a single sentence — keep code-fenced sections English-only and prose Russian-only.

---

### MADR 4.0 ADR Convention (CONTEXT D-06)

**Apply to:** `docs/adr/0001-modular-monolith.md`, `docs/adr/template.md`, all future ADRs

**Section set (locked):**
1. `# ADR-NNNN: <title>`
2. Metadata block — `Status:`, `Date:`, `Deciders:`
3. `## Context and Problem Statement`
4. `## Decision Drivers`
5. `## Considered Options`
6. `## Decision Outcome`
7. `### Consequences` (subsection of Decision Outcome)
8. `## Pros and Cons of the Options`

**Constraint:** Future ADRs (0002+) MUST follow this exact section set so the `docs/adr/` directory stays predictable. NOT Nygard's classic 5-section template.

---

### Placeholder File Convention (Phase 2 inheritance)

**Apply to:** `tests/factories/__init__.py`, `tests/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py`

Phase 2 PATTERNS line 197-200 established: empty `__init__.py` files are mypy-clean and acceptable. Same convention here. Do NOT add docstrings, `__all__`, or comments to test package inits — they are pure markers.

---

### Quality Gates Run via `uv run` (CONTEXT D-08)

**Apply to:** `conventions.md ## Quality gates`, `README.md ## Команды`

All five gates are invoked via `uv run`:

| Gate | Command | Source file |
|------|---------|-------------|
| Linting | `uv run ruff check .` | `ruff.toml` |
| Formatting | `uv run ruff format .` | `ruff.toml` |
| Type check | `uv run mypy app` | `pyproject.toml [tool.mypy]` |
| Architecture | `uv run lint-imports` | `.importlinter` |
| Tests | `uv run pytest` | `pyproject.toml [tool.pytest.ini_options]` |

**Constraint:** Both `conventions.md` and `README.md` MUST list these five and MUST list them in this `uv run <tool>` form. They are the future-CI contract per CONTEXT `<code_context>` line 355.

---

### `.importlinter` File Name (correction vs Phase 2 PATTERNS)

**Note:** Phase 2 PATTERNS.md refers to the file as `importlinter.ini`, but the actual on-disk file (post-commit `72880b1`) is `apps/backend/.importlinter` (dot-prefixed for auto-discovery). When `conventions.md` quotes contract names or paths, use **`.importlinter`** — not `importlinter.ini`. Same content, different filename.

---

## No Analog Found (Cross-Reference Table)

All Phase 3 deliverables have no in-repo code analog. CONTEXT.md `<decisions>` is the canonical literal source.

| File | Role | Data Flow | CONTEXT.md decision section |
|------|------|-----------|------------------------------|
| `tests/conftest.py` | test-fixtures | request-response + CRUD | D-10, D-11 |
| `tests/integration/test_healthz.py` | integration-test | request-response | D-11 (fixtures) + Phase 2 `health.py` |
| `tests/unit/test_security.py` | unit-test | — | D-10 (skip-DB rationale) |
| `tests/factories/__init__.py` | package-init | — | TEST-04 (empty) |
| `pyproject.toml` (MODIFY) | config | — | D-14, D-15 |
| `Dockerfile` | dev-infra | build | D-01, D-02, D-03, D-04 |
| `docker-compose.yml` | dev-infra | orchestration | D-04, D-12 |
| `.dockerignore` | config | — | D-13 |
| `scripts/seed_demo_data.py` | utility-script | — | D-13 |
| `scripts/backup_db.sh` | utility-script | file-I/O | D-13 |
| `docs/architecture.md` | docs | — | D-05, D-07 |
| `docs/conventions.md` | docs | — | D-05, D-08 |
| `docs/adr/0001-modular-monolith.md` | docs (ADR) | — | D-05, D-06 |
| `docs/adr/template.md` | docs (ADR template) | — | D-06, `<specifics>` line 363 |
| `README.md` | docs | — | D-05, D-09 |

---

## Wave Dependency Summary (for Planner)

```
Wave A (tests/) ─┬─ depends on Phase 2 main.py + database.py + health.py + middleware.py (already shipped)
                 │
                 └─ requires asgi-lifespan dev-dep (Wave B item 2)

Wave B (pyproject.toml MODIFY) ─ standalone; required before `uv run pytest` runs

Wave C (Dockerfile + docker-compose.yml + .dockerignore) ─ standalone for files,
                 │  but `migrate` service first invocation closes Phase 2 SC #5
                 │  (one-time `alembic upgrade head` against compose Postgres)

Wave D (scripts/) ─ standalone

Wave E (docs/ + README.md) ─ depends on A/B/C content for accuracy
                 │  (conventions.md ## Testing references conftest.py fixtures;
                 │   README.md ## Quick start references compose services)
```

**Suggested execution order:**
1. **Wave B** first (pyproject.toml modifications) — unlocks `pytest` invocation.
2. **Wave A** + **Wave C** + **Wave D** in parallel — independent surfaces.
3. **Wave E** last — references shipped surfaces by name.
4. **Phase 2 SC #5 retirement** — after Wave C, run `docker compose up` once and verify `migrate` service exits 0 (`alembic upgrade head` against empty `versions/.gitkeep`).

---

## Metadata

**Analog search scope:** `apps/backend/` (Phase 2 deliverables), `apps/admin-web/README.md` (sibling style), Phase 2 PATTERNS.md (process analog), CONTEXT.md `<decisions>` (literal pattern source).
**In-repo files referenced:** 9 (`app/main.py`, `app/core/{config,database,middleware,exceptions,security,logging}.py`, `app/api/v1/health.py`, `.importlinter`, `pyproject.toml`).
**External spec referenced:** MADR 4.0.
**Files scanned:** 12.
**Pattern extraction date:** 2026-05-01.
