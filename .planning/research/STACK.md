# Stack Research

**Domain:** FastAPI modular monolith — API handoff tooling + production hardening
**Researched:** 2026-05-26
**Confidence:** HIGH — all versions confirmed via npm registry live queries + direct codebase inspection

---

## Verdict: Five Targeted Additions

The locked backend stack (Python 3.12 + FastAPI + SQLAlchemy 2.0 + Redis 7 + ARQ + structlog) is not
changing. v1.11 adds exactly five new tooling concerns, all infrastructure-only. No new ORM entities,
no new auth providers, no new payment integrations, no npm/PyPI publishing.

| Concern | Tool | Where it lives | Install style |
|---|---|---|---|
| OpenAPI → Postman collection | `openapi-to-postmanv2@6.0.1` | pnpm workspace root devDep | `pnpm add -Dw openapi-to-postmanv2` |
| Newman smoke runner | `newman@6.2.2` | pnpm workspace root devDep | `pnpm add -Dw newman` |
| Private OpenAPI doc-site | `@redocly/cli@2.31.4` | pnpm workspace root devDep (or npx) | `pnpm add -Dw @redocly/cli` |
| Local email capture (dev) | `axllent/mailpit:latest` | docker-compose `--profile dev` service | docker image, no npm/pip |
| Idempotency hardening | `app/core/idempotency.py` (existing) | already in codebase | zero new packages |

---

## Recommended Stack

### Core Technologies

All existing. No new Python packages, no new ORM entities, no new test frameworks.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python 3.12 + FastAPI 0.115+ | locked | HTTP API | Existing locked stack |
| SQLAlchemy 2.0 async + Alembic async | locked | ORM + migrations | Existing locked stack |
| Redis 7 | locked | session / idempotency / circuit breakers | Existing locked stack |
| ARQ 0.26 | locked | async job queue + cron | Existing locked stack |
| ruff 0.15.12 | installed via `ruff>=0.6` pyproject.toml | linting + formatting | Existing tool; Phase 63 sweep only |
| mypy 1.20.2 | installed via `mypy>=1.10` pyproject.toml | static type checking | Existing tool; Phase 63 sweep only |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `openapi-to-postmanv2` | `6.0.1` | Convert curated `openapi.json` → Postman v2.1 collection | Phase 65: generate `clubcore-v1.11.postman_collection.json` |
| `newman` | `6.2.2` | Run Postman collection as CLI smoke test | Phase 65: operator smoke; Phase 67: runbook evidence |
| `@redocly/cli` | `2.31.4` | Lint `openapi.json` for `operationId` / tags + serve private doc-site | Phase 64 (lint gate) + Phase 65 (preview-docs) |
| `axllent/mailpit` | `latest` | SMTP trap + web UI at `localhost:8025` for dev email inspection | Phase 67: operator walkthrough evidence (DEFER-46-05) |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `ruff check --fix` | Auto-fix 80 of 158 ruff errors (RUF100, F401, I001, F541, UP017, UP037) | Phase 63 step 1 |
| `ruff format` | Auto-format 297 files | Phase 63 step 2 |
| `mypy app` (existing `--strict`) | 11 errors in 7 files; fix `models.py __all__` + Literal narrowing | Phase 63 steps 3-6 |
| `npx @redocly/cli lint` | Enforce `operationId` presence on every route | Phase 64 CI gate addition |
| `npx openapi2postmanv2` | One-shot collection generation from curated spec | Phase 65, not a CI gate |
| `newman run` | Smoke collection against `docker compose up` | Phase 65 / Phase 67 operator use |

---

## Installation

```bash
# Root workspace — Postman tooling + Newman + doc-site preview (all devDeps, no publish)
pnpm add -Dw openapi-to-postmanv2 newman @redocly/cli

# Backend Python — no new packages needed
# (ruff>=0.6 and mypy>=1.10 already in apps/backend/pyproject.toml [dependency-groups.dev])

# MailHog / Mailpit — Docker only, no pip/npm install
# Append to apps/backend/docker-compose.yml (see section 4 below)
```

---

## Detailed Notes Per Phase

### 1. OpenAPI → Postman Collection (Phase 65)

**Tool:** `openapi-to-postmanv2@6.0.1` — official Postman Labs converter
(`github.com/postmanlabs/openapi-to-postman`). Binary name: `openapi2postmanv2`.

**Why this tool:** It is the only Postman Labs-official CLI for OpenAPI 3.x → Collection v2.1
conversion. The existing `.planning/handoff/v1.6-postman.json` (145 KB, 74 items) already uses
`https://schema.getpostman.com/json/collection/v2.1.0/collection.json` — this tool produces exactly
that format. `postman-collection-transformer` and similar tools do not perform OpenAPI import.

**Dependency on Phase 64:** `folderStrategy=Tags` requires every route to have `tags=[...]` — which is
exactly what Phase 64 (Contract Freeze) adds. Without tags, all requests land in a flat "default"
folder. Phase 64 must complete before Phase 65 generates the collection.

**Conversion command** (add to root `package.json` scripts or `Makefile`):
```bash
npx openapi2postmanv2 \
  -s apps/backend/openapi.json \
  -o .planning/handoff/clubcore-v1.11.postman_collection.json \
  -p \
  -O folderStrategy=Tags,includeAuthInfoInExample=false,requestParametersResolution=Example
```

Flag rationale:
- `-p` — pretty-print JSON (human-readable diffs)
- `folderStrategy=Tags` — groups by `tags`, requires Phase 64 curation first
- `includeAuthInfoInExample=false` — keeps credentials out of committed collection bodies
- `requestParametersResolution=Example` — populates request bodies with example values

The output `.planning/handoff/clubcore-v1.11.postman_collection.json` is a committed artifact
(not gitignored), analogous to `v1.6-postman.json`. Not a CI gate — regenerate manually when spec
changes, then commit.

---

### 2. Newman Smoke Runner (Phase 65 / Phase 67)

**Tool:** `newman@6.2.2` — official Postman CLI runner.

**Scope:** Not a replacement for `pytest`. Newman verifies reachability and contract shape (HTTP status
codes, response structure) for the 10–15 most critical endpoints against a live `docker compose up`
stack. Authentication uses httpOnly cookies — captured via pre-request scripts (pattern already present
in v1.6 collection).

**Invocation:**
```bash
newman run .planning/handoff/clubcore-v1.11.postman_collection.json \
  --environment apps/backend/newman-env.json \
  --reporters cli,junit \
  --reporter-junit-export .planning/handoff/newman-results.xml \
  --bail
```

**Newman environment file** `apps/backend/newman-env.json` (committed, no real secrets):
```json
{
  "name": "clubcore-local",
  "values": [
    {"key": "base_url", "value": "http://localhost:8000", "enabled": true},
    {"key": "owner_email", "value": "owner@fixture.local", "enabled": true},
    {"key": "owner_password", "value": "ownerpass123", "enabled": true}
  ]
}
```

**CI integration:** Newman is NOT a CI gate on every push (requires live Postgres + Redis + seeded DB).
It is a local operator smoke for Phase 67 runbook walkthroughs. A dedicated CI job with `services:`
(Postgres + Redis) could run it, but is out of v1.11 scope.

---

### 3. Private OpenAPI Doc-Site (Phase 65)

**Tool:** `@redocly/cli@2.31.4` for both linting (Phase 64 CI gate) and local doc preview (Phase 65).

**Why Redocly CLI, not alternatives:**

- Single binary, zero config for basic use. `npx @redocly/cli preview-docs apps/backend/openapi.json`
  starts a hot-reloading server on `http://localhost:8080`. No HTML wrapper, no webpack.
- Actively maintained: `2.31.4` released 2026-05-22 (latest as of research date).
- Dual use: same package serves as both a spec linter (`redocly lint`) for Phase 64 CI gate AND
  the local preview server (`redocly preview-docs`) for Phase 65. One devDep, two functions.
- Doc-site is served in-memory (hot reload). No HTML build artifacts to gitignore.
- Private by definition: runs locally only, never published. No login, no external service.

**Phase 64 usage (lint gate in CI):**

Add minimal `redocly.yaml` at repo root:
```yaml
# redocly.yaml — spec linting for Phase 64 contract freeze
apis:
  clubcore:
    root: apps/backend/openapi.json
rules:
  operation-operationId: error    # every route must have operationId (required for Postman folder names)
  tag-description: warn           # tags should have descriptions
  operation-summary: warn         # operations should have summaries
```

Add one step to `.github/workflows/ci.yml` backend job after `Export OpenAPI spec`:
```yaml
- name: Lint OpenAPI spec
  run: npx --yes @redocly/cli@2.31.4 lint apps/backend/openapi.json --config redocly.yaml
```

This gate is additive to the existing byte-stability drift gate and does not change the gate behavior
for `openapi.json` itself.

**Phase 65 usage (local doc preview):**

Operator command (add to `apps/backend/scripts/` or runbook):
```bash
npx @redocly/cli preview-docs apps/backend/openapi.json
# Opens http://localhost:8080 — hot-reloads on openapi.json changes
```

Docker alternative (no local Node required):
```bash
docker run --rm -v $(pwd):/spec -p 8080:8080 redocly/cli preview-docs /spec/apps/backend/openapi.json
```

---

### 4. Local Email Capture — Mailpit `--profile dev` (Phase 67)

**Tool:** `axllent/mailpit:latest` (NOT `mailhog/mailhog`)

**Why Mailpit, not MailHog:** MailHog is archived — last Docker image update was 2019, GitHub repo
shows no commits since 2022. `axllent/mailpit` is the actively-maintained drop-in replacement:
same default ports (SMTP 1025, web UI 8025), same API shape, updated as recently as hours before
research date. One-line swap in docker-compose.

**Critical constraint:** The existing email integration (`app/integrations/email/client.py`) uses
`aioboto3` SES-V2 API against Yandex Cloud Postbox — not SMTP. Mailpit (like MailHog) is an SMTP
trap. It cannot intercept SES-V2 API calls.

This means two options exist for Phase 67:

**Option A (recommended): Use the existing `SandboxEmailClient`.**
Set `EMAIL_PROVIDER=sandbox` in `.env` or `docker-compose.override.yml`. The ARQ worker logs fully
rendered email envelopes at INFO level via structlog (to, subject, text_preview). The operator reads
structlog output in the docker-compose log stream as evidence. Zero new code, zero new infra.

**Option B: Add Mailpit + new SMTP adapter.**
This requires a new `SmtpEmailClient` class using `aiosmtplib`, a new `provider='smtp'` branch in
`factory.py`, new config fields (`EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`), and new tests. Provides a
browser-visible email UI at `http://localhost:8025`. Non-trivial code addition for a "no new
business features" milestone.

**Recommendation:** Option A (SandboxEmailClient) for Phase 67. The structlog output satisfies
evidence capture. If the team later wants browser-visible Mailpit evidence (v2.0 dev-experience),
the docker-compose addition is:

```yaml
# Append to apps/backend/docker-compose.yml
  mailpit:
    image: axllent/mailpit:latest
    profiles: ["dev"]
    ports:
      - "1025:1025"   # SMTP trap
      - "8025:8025"   # Web UI at http://localhost:8025
```

**Docker Compose profile syntax:** `profiles: ["dev"]` is the Compose v2 syntax. `docker compose
--profile dev up` brings all services including mailpit. `docker compose up` (no flag) skips it.
This is confirmed correct for the existing `docker-compose.yml` format (Compose v2, no version
field). HIGH confidence — used in Docker Compose official docs.

---

### 5. Idempotency Hardening (Phase 66 — CR-01/02/02b)

**No new package needed.** `app/core/idempotency.py` (210 lines) is fully implemented:
- `verify_idempotency`, `begin_idempotency`, `store_idempotency_response`,
  `load_idempotency_response` — all present and production-tested since v1.7.
- Redis key shape: `cc:idem:{method}:{path}:{header_value}` (route-bound, prevents cross-endpoint
  replay — CR-01 was a bug here, fixed in D-33-16).
- Current TTL: `IDEMPOTENCY_TTL_SECONDS = 3600` (1 hour).
- Replay: `IdempotencyEnvelope` with `status_code + body_b64 + body_hash`.

**IETF alignment:** `draft-ietf-httpapi-idempotency-key-header-07` (October 2025, still Internet-Draft,
not yet RFC). Relevant guidance: UUIDv4 recommended as key format; cache window is
implementation-defined. The existing `IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_:-]{1,128}$"` is
broader than UUIDv4 but valid for a private API.

**What Phase 66 actually changes in code:**

One constant change — align TTL with the ЮKassa webhook dedup window discipline (which uses `ex=86400`):
```python
# app/core/idempotency.py
IDEMPOTENCY_TTL_SECONDS: int = 86400  # 24h — aligns with webhook dedup discipline
```

Plus an audit pass: identify which mutating `POST`/`PATCH`/`DELETE` endpoints currently lack
`Depends(verify_idempotency)` and add it where appropriate (CR-02b). The existing dependency is
only wired to ЮKassa online payment endpoints. Cash sale endpoints (`POST /api/v1/sales/*`),
refund endpoints, and notification dispatch endpoints are candidates.

Plus spec curation: add `components/parameters/IdempotencyKey` as a reusable OpenAPI parameter
in Phase 64 (Contract Freeze), then reference it from all endpoints that use it (Phase 66 follow-up).

**No external idempotency package:** `fastapi-idempotent` (v0.0.3) and `idemptx` (v0.2.2) are
low-adoption, add transitive deps, and provide no capability beyond the existing implementation.
Do not replace.

---

### 6. Tech-Debt Sweep: Ruff + Mypy (Phase 63 — DEFER-46-04)

**No new tools needed.** ruff `0.15.12` and mypy `1.20.2` are already installed via
`apps/backend/pyproject.toml` dev dependencies.

**Current state (verified 2026-05-26):**

| Tool | Status | Count |
|---|---|---|
| `ruff check` | 158 errors | 80 auto-fixable with `--fix`; 14 more with `--unsafe-fixes` |
| `ruff format --check` | 297 files would reformat | All auto-fixable |
| `mypy app --strict` | 11 errors in 7 files | Mix: attr-defined (4) + arg-type (5) + no-any-return (1) + unused-ignore (1) |

**Ruff error breakdown:**
- `RUF100` (42): unused `# noqa` — auto-fix
- `F401` (21): unused imports — auto-fix
- `E501` (14): lines too long — manual
- `F811` (13): redefined-while-unused — manual (test fixtures likely)
- `RUF059` (12): unused unpacked variables — manual
- `RUF002` (11): ambiguous Unicode in docstrings (Cyrillic in comments) — accept or suppress
- `I001` (10): unsorted imports — auto-fix
- `S106` (9): hardcoded-password-func-arg (test fixtures) — suppress with `# noqa: S106`
- `DTZ011` (6): call-date-today — manual review
- `F541` (4): f-string missing placeholders — auto-fix
- Remainder: B017, RUF001, F841, N806, UP017, UP037, RUF003, S110, SIM102

**Mypy error breakdown (11 errors in 7 files):**
- `attr-defined` (4 errors): `app/modules/auth/models.py` does not `__all__`-export `User` → fix by
  adding `__all__ = ["User"]` to that file.
- `arg-type` (5 errors): `Literal['redirect', 'qr']` narrowing fails in
  `online_payments/router.py` (4) and `online_refunds/settle.py` (1) — narrow via explicit `cast()`
  or fix the Pydantic discriminator.
- `no-any-return` (1 error): `fiscal_receipts/tasks.py:182`.
- `unused-ignore` (1 error): `online_refunds/settle.py:177`.

**Recommended Phase 63 sweep order:**
1. `uv run ruff check --fix app tests` — resolves RUF100, F401, I001, F541, UP017, UP037
2. `uv run ruff format app tests` — reformats 297 files
3. Fix `app/modules/auth/models.py` `__all__` — resolves 4 mypy attr-defined errors
4. Fix Literal narrowing in `online_payments/router.py` + `online_refunds/settle.py` — resolves 5 arg-type errors
5. Fix `fiscal_receipts/tasks.py:182` no-any-return (add explicit return type or cast)
6. Fix or suppress `online_refunds/settle.py:177` unused-ignore
7. Manual review: `E501` (14), `RUF059` (12), `S106` (9), `DTZ011` (6) — accept or `# noqa` with code
8. `uv run mypy app` → 0 errors; `uv run ruff check app tests` → 0 (or only documented suppressions)
9. CI green

**Pre-commit hooks: NOT recommended.** The project does not use `pre-commit`. Adding it introduces
a new tooling layer for what is a one-time batch sweep. The existing CI gates (`ruff check`,
`ruff format --check`, `mypy app`, `lint-imports`) are the enforcement layer. They already serve
the pre-commit equivalent function at CI time.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `openapi-to-postmanv2` (Postman Labs official) | `@apimatic/postman-collection-transformer` | Not a usable published package for this use case; openapi-to-postmanv2 is the standard |
| `newman` (Postman Labs official) | `artillery`, `k6` | Those are load testers, not contract/smoke runners |
| `@redocly/cli preview-docs` | `@stoplight/elements@9.0.19` | Elements is a React component library for embedding in an existing web app, not a standalone CLI server |
| `@redocly/cli preview-docs` | `swagger-ui-watcher` | Unmaintained since 2021 |
| `axllent/mailpit` | `mailhog/mailhog` | MailHog is archived (last Docker update 2019); Mailpit is the drop-in replacement, actively maintained |
| `SandboxEmailClient` (existing) | Mailpit + new SMTP adapter | SMTP adapter requires new `aiosmtplib` code + new `SmtpEmailClient` class; sandbox logs are sufficient for Phase 67 evidence |
| `app/core/idempotency.py` (existing) | `fastapi-idempotent@0.0.3`, `idemptx@0.2.2` | Low-adoption, adds transitive deps, no new capability |
| existing ruff + mypy in CI | `pre-commit` hooks | Adds tooling complexity for a one-time batch sweep; CI gates already enforce quality |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pre-commit` hooks | Out of scope; CI already gates ruff/mypy/format; one-time sweep, not a recurring gate change | existing CI gates |
| `fastapi-idempotent` / `idemptx` | v0.0.3 / v0.2.2 — low adoption; superseded by `app/core/idempotency.py`; adds transitive deps | existing `app/core/idempotency.py` |
| `aiosmtplib` (SMTP adapter) | Only needed if Mailpit browser UI explicitly required; `SandboxEmailClient` covers Phase 67 | `SandboxEmailClient` (`EMAIL_PROVIDER=sandbox`) |
| `@stoplight/elements` | React component library — wrong tool for standalone local doc preview | `@redocly/cli preview-docs` |
| `swagger-ui-watcher` | Unmaintained (2021) | `@redocly/cli preview-docs` |
| `mailhog/mailhog` | Archived — last update 2019; no security patches | `axllent/mailpit` (drop-in replacement) |
| Any new ORM entity / Alembic migration | Milestone constraint: no new business entities | — |
| Any npm/PyPI publish workflow | Personal commercial project — publishing forbidden per PROJECT.md + D-10-NO-PUBLISH | — |
| Spectral (`@stoplight/spectral-cli`) | Viable OpenAPI linter but introduces a second linting dependency when `@redocly/cli` already serves both lint + preview | `@redocly/cli lint` |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| `openapi-to-postmanv2` | `6.0.1` | OpenAPI 3.0 + 3.1 | FastAPI 0.115+ generates OpenAPI 3.1 by default; output is Postman Collection v2.1 |
| `newman` | `6.2.2` | Postman Collection v2.1 | Matches the schema in existing `.planning/handoff/v1.6-postman.json` |
| `@redocly/cli` | `2.31.4` | OpenAPI 3.0 + 3.1 | Released 2026-05-22; reads `openapi.json` directly; no config needed for `preview-docs` |
| `axllent/mailpit` | `latest` | Docker Compose v2, SMTP 1025 / HTTP 8025 | Drop-in for MailHog same-port defaults; actively maintained; requires SMTP adapter in backend to intercept (see Option B above) |
| ruff | `0.15.12` | Python 3.12, existing `pyproject.toml` | `ruff>=0.6` constraint satisfied |
| mypy | `1.20.2` | Python 3.12, `--strict`, pydantic plugin | `mypy>=1.10` constraint satisfied |

---

## Sources

- `npm view openapi-to-postmanv2 dist-tags.latest` → `6.0.1` (confirmed 2026-05-26)
- `npm view newman dist-tags.latest` → `6.2.2` (confirmed 2026-05-26)
- `npm view @redocly/cli dist-tags.latest` → `2.31.4` (confirmed 2026-05-26; changelog shows released 2026-05-22)
- `hub.docker.com/r/axllent/mailpit` — updated ~11 hours before research; actively maintained
- `hub.docker.com/r/mailhog/mailhog` — last update 2019 (approximately 6 years before research date); archived
- `github.com/postmanlabs/openapi-to-postman` — official converter; `npm view openapi-to-postmanv2 bin` → `openapi2postmanv2`
- `datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/` — draft-07, October 2025, Standards Track, still Internet-Draft (not yet RFC)
- Direct codebase inspection:
  - `apps/backend/app/core/idempotency.py` — 210 lines; `IDEMPOTENCY_TTL_SECONDS=3600`; key shape `cc:idem:{method}:{path}:{key}`; CR-01 route-binding fix confirmed at line 89
  - `apps/backend/app/integrations/email/client.py` — `aioboto3` SES-V2 adapter; no SMTP path
  - `apps/backend/docker-compose.yml` — 6 services (backend + telegram-bot + arq-worker + migrate + postgres + redis); no `profiles:` defined yet; Compose v2 format (no `version:` field)
  - `.github/workflows/ci.yml` — existing gates: `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `Export OpenAPI spec`, drift gate on `openapi.json` + `schema.d.ts`
  - `apps/backend/pyproject.toml` — `ruff>=0.6`, `mypy>=1.10` in `[dependency-groups.dev]`; `uv run ruff --version` → `0.15.12`; `uv run mypy --version` → `1.20.2`
  - `uv run ruff check --statistics` → 158 errors; breakdown documented above
  - `uv run ruff format --check` → 297 files would reformat
  - `uv run mypy app` → 11 errors in 7 files; breakdown documented above

---

*Stack research for: v1.11 API Handoff + Production Hardening (clubcore)*
*Researched: 2026-05-26*
