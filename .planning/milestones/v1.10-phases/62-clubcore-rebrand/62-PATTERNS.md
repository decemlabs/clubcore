# Phase 62: clubcore Rebrand — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 30+ rename surfaces across 6 atomic groups
**Analogs found:** N/A — this is a pure-mechanical rename phase. "Patterns" are rename mappings, not architectural analogs.

---

## Orientation

Phase 62 has **no novel architecture** — every "file to be created/modified" already exists and is being renamed in-place, with two exceptions:

1. **`apps/backend/app/core/branding.py`** — new file, single constant `CLUB_BRAND = "Sportzal"` (D-62-02).
2. **`.planning/HISTORICAL_NOTE.md`** — new file, under-30-line audit-trail boundary note (D-62-10).

The "analog" for every renamed surface is **the current file itself** — the planner copies the surrounding pattern verbatim and changes only the identifier string. Therefore this PATTERNS.md is keyed by **rename surface**, not by file role. Each entry lists:

- File path + line number(s) of the current literal
- Current literal (`before`)
- Target literal (`after`)
- Atomic-commit group (G-1 .. G-6) — must land together to keep build green per D-62-11
- Notes / cross-references

The single non-trivial code pattern (Zustand `persist` v1→v2 `migrate` with copy-on-read+delete-old) is described once in **Shared Pattern Z-1** and applied to three stores identically.

---

## Atomic-Commit Groups (D-62-11)

Cross-references break mid-rename if these don't land together. Planner MUST structure tasks so each group is one commit.

| Group | Scope | Files | Rationale |
|-------|-------|-------|-----------|
| **G-1** | pnpm package rename (`@sportzal/*` → `@clubcore/*`) | `packages/api-client/package.json`, `packages/ui/package.json`, `apps/admin-web/package.json` (name + `predev` script + dep), `.github/workflows/ci.yml` (3 invocations), `apps/admin-web/eslint.config.js:120` (error message), `pnpm-lock.yaml` (regenerated) | Workspace dep resolution + pnpm filter + lockfile must be coherent at every commit. `pnpm install` must succeed at G-1's tip. |
| **G-2** | Frontend localStorage namespace + theme bootstrap | `apps/admin-web/src/shared/session/store.ts:5,21`, `apps/admin-web/src/shared/theme/uiPrefsStore.ts:15,31`, `apps/admin-web/src/shared/api/services/mock/_db.ts:7`, `apps/admin-web/index.html:16` (bootstrap script reads `sportzal:ui:v1`) | `index.html` reads the same key Zustand persists to; mismatch causes FOUC or rehydrate failure. All three stores must bump `version: 1 → 2` and acquire the same `migrate` callback in one commit. |
| **G-3** | Backend Redis key prefixes (`sz:*` → `cc:*`) | `apps/backend/app/core/idempotency.py:38`, `apps/backend/app/integrations/telegram/handlers.py:105`, `apps/backend/app/integrations/yookassa/circuit_breaker.py:41-42`, `apps/backend/app/integrations/email/circuit_breaker.py:37-38`, `apps/backend/app/api/v1/_internal/yookassa/router.py:56` | Per D-62-07: no runtime dual-read; operator FLUSHDB at cutover. All five prefixes flip in one commit. Tests that mock Redis with `sz:*` keys (if any) must update in same commit. |
| **G-4** | `CLUB_BRAND` constant extraction (pure refactor, D-62-02) | NEW `apps/backend/app/core/branding.py` + 5 email_templates.py edits (auth, users, memberships, bookings, payments) + `apps/backend/app/core/config.py:25` (`EmailProviderSettings.from_address` default + new `CLUBCORE_EMAIL_FROM` field with fallback) | Constant must exist before templates import it. AST gate (`tests/unit/test_locked_email_templates_ast.py` per CONTEXT line 140) may reject the literal swap unless run as one diff. |
| **G-5** | Operator-tier: DB name + env | `apps/backend/.env.example:2`, `apps/backend/docker-compose.yml` (lines 10, 27, 41, 56, 66, 68 — 6 occurrences), root `CLAUDE.md`, `apps/backend/README.md`, `apps/admin-web/CLAUDE.md` (in-line stale references to `sportzal:mock:v1` etc.), `apps/admin-web/README.md`, `apps/admin-web/package.json:2` (`"name": "sportzal-adminka"` → `"clubcore-adminka"`) | docker-compose `DATABASE_URL` references must all match `POSTGRES_DB`. Stale URL in one of the 4 services = container won't reach DB. |
| **G-6** | `.planning/` forward-only rewrite + HISTORICAL_NOTE | `.planning/PROJECT.md` (15 hits), `.planning/MILESTONES.md` (3), `.planning/ROADMAP.md` (8), `.planning/REQUIREMENTS.md` (8), `.planning/STATE.md` (7), `.planning/RETROSPECTIVE.md` (1), NEW `.planning/HISTORICAL_NOTE.md` | No code coupling, but commit-message ↔ file-content coherence per D-62-09. Future `.planning/handoff/clubcore-*` artifacts inherit the new name. Historical `.planning/phases/47-61/*` + `.planning/audits/*` + `.planning/handoff/v1.4..v1.9-*` are **immutable** — do not touch. |

**Smoke verification runs after each group**, not just at the end (recommendation in CONTEXT decisions section). After G-3 backend tests must pass; after G-2 admin-web typecheck/lint/test must pass; after G-1 `pnpm install --frozen-lockfile && pnpm -r typecheck` must pass.

---

## Rename Surface Table — G-1: pnpm package rename

### `packages/api-client/package.json`

**Current** (lines 2, 6):
```json
{
  "name": "@sportzal/api-client",
  "description": "Typed transport for the Sportzal backend (request<P,M> + ApiError + generated openapi-typescript schema).",
```

**Target**:
```json
{
  "name": "@clubcore/api-client",
  "description": "Typed transport for the clubcore backend (request<P,M> + ApiError + generated openapi-typescript schema).",
```

---

### `packages/ui/package.json`

**Current** (lines 2, 5):
```json
{
  "name": "@sportzal/ui",
  "description": "Phase 1 placeholder for shared UI primitives. Real implementation lands in a later phase."
```

**Target**:
```json
{
  "name": "@clubcore/ui",
```
(description has no brand reference; leave intact.)

---

### `apps/admin-web/package.json`

**Current** (lines 2, 13, 36):
```json
"name": "sportzal-adminka",
...
"predev": "pnpm --filter @sportzal/api-client codegen",
...
"@sportzal/api-client": "workspace:*",
```

**Target**:
```json
"name": "clubcore-adminka",
...
"predev": "pnpm --filter @clubcore/api-client codegen",
...
"@clubcore/api-client": "workspace:*",
```

---

### `apps/admin-web/eslint.config.js:120`

**Current** (lint rule error message — FE-07):
```js
message:
  'Use @sportzal/api-client.request<P,M> instead of raw fetch(). Direct fetch is allowed only inside src/shared/api/services/http/**.',
```

**Target**:
```js
message:
  'Use @clubcore/api-client.request<P,M> instead of raw fetch(). Direct fetch is allowed only inside src/shared/api/services/http/**.',
```

Pure user-facing string. No behavioural change.

---

### `.github/workflows/ci.yml`

**Current** (lines 102-106):
```yaml
- name: Test @sportzal/api-client
  run: pnpm -F @sportzal/api-client test
...
- name: Codegen — packages/api-client
  run: pnpm --filter @sportzal/api-client codegen
```

**Target**:
```yaml
- name: Test @clubcore/api-client
  run: pnpm -F @clubcore/api-client test
...
- name: Codegen — packages/api-client
  run: pnpm --filter @clubcore/api-client codegen
```

---

### `pnpm-lock.yaml:47`

Current line 47: `'@sportzal/api-client':` (workspace dep entry).

**Action**: do NOT hand-edit. After all `package.json` renames land, run `pnpm install` (without `--frozen-lockfile`) to regenerate. CI `--frozen-lockfile` check in subsequent commit confirms regen was committed.

---

### `pnpm-workspace.yaml`

Current content uses globs only — no `@sportzal` reference:
```yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

**Action**: no change needed. Verify post-rename that `apps/*` and `packages/*` still match all directories.

---

### `.importlinter`

Searched: no `@sportzal` references (Python-side import-linter targets `app.*` modules only). **No change needed.**

---

## Rename Surface Table — G-2: Frontend localStorage + theme bootstrap

### Shared Pattern Z-1: Zustand `persist` v1→v2 migrate (copy-on-read + delete-old)

Per D-62-06, all three stores receive the **identical** migration shape:

```typescript
// Before (current):
{
  name: 'sportzal:<concern>:v1',
  version: 1,
  storage,
  partialize: (s) => ({ /* same fields */ }),
  skipHydration: true,
}

// After (target):
{
  name: 'clubcore:<concern>:v2',
  version: 2,
  storage,
  partialize: (s) => ({ /* same fields */ }),
  migrate: (persistedState, version) => {
    // v1 shape is identical to v2 — pass through.
    // Caller is responsible for the localStorage key migration
    // (read sportzal:*:v1 → write clubcore:*:v2 → remove old)
    // which runs as a pre-hydrate side effect in main.tsx.
    if (version === 1) return persistedState as never
    return persistedState as never
  },
  skipHydration: true,
}
```

**Key migration site** — runs in `apps/admin-web/src/app/main.tsx` BEFORE `persist.rehydrate()` (per CONTEXT line 151 "localStorage migrate runs in `main.tsx:13`"). Pseudocode:

```typescript
// Pre-rehydrate one-shot migrator.
const STORE_MIGRATIONS: ReadonlyArray<readonly [string, string]> = [
  ['sportzal:session:v1', 'clubcore:session:v2'],
  ['sportzal:ui:v1', 'clubcore:ui:v2'],
  ['sportzal:mock:v1', 'clubcore:mock:v2'],
] as const

for (const [oldKey, newKey] of STORE_MIGRATIONS) {
  try {
    if (window.localStorage.getItem(newKey) !== null) continue // already migrated
    const legacy = window.localStorage.getItem(oldKey)
    if (legacy === null) continue // greenfield user
    window.localStorage.setItem(newKey, legacy)
    window.localStorage.removeItem(oldKey)
  } catch { /* noop — storage quota/disabled; let store re-seed */ }
}
```

**Removal target**: v1.11 / Phase 67 / RUN-07 per CONTEXT line 191. Mark with `// TODO Phase 67 / RUN-07: drop v1.10 sportzal:* migration shim`.

---

### `apps/admin-web/src/shared/session/store.ts`

**Current** (line 5, 19-25):
```ts
const STORAGE_KEY = 'sportzal:session:v1'
// ...
{
  name: STORAGE_KEY,
  version: 1,
  storage,
  partialize: (s) => ({ role: s.role }),
  migrate: (state) => state as PersistedSession,
  skipHydration: true,
},
```

**Target**:
```ts
const STORAGE_KEY = 'clubcore:session:v2'
// ...
{
  name: STORAGE_KEY,
  version: 2,
  storage,
  partialize: (s) => ({ role: s.role }),
  migrate: (state) => state as PersistedSession, // shape unchanged v1→v2
  skipHydration: true,
},
```

Note: existing `migrate` callback already pass-throughs — no body change, only `version` bump.

---

### `apps/admin-web/src/shared/theme/uiPrefsStore.ts`

**Current** (line 15, 29-35):
```ts
const STORAGE_KEY = 'sportzal:ui:v1'
// ...
{
  name: STORAGE_KEY,
  version: 1,
  storage,
  partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
  skipHydration: true,
},
```

**Target**:
```ts
const STORAGE_KEY = 'clubcore:ui:v2'
// ...
{
  name: STORAGE_KEY,
  version: 2,
  storage,
  partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
  migrate: (state) => state as PersistedUi, // shape unchanged v1→v2
  skipHydration: true,
},
```

Note: this store currently has **no `migrate` callback** — must add the no-op one to declare the version bump valid (Zustand requires `migrate` when `version` increments above stored version).

---

### `apps/admin-web/src/shared/api/services/mock/_db.ts`

**Current** (line 7):
```ts
const STORAGE_KEY = 'sportzal:mock:v1'
```

**Target**:
```ts
const STORAGE_KEY = 'clubcore:mock:v2'
```

This store does NOT use Zustand `persist` (it's a raw `localStorage.getItem/setItem` shim — see lines 159-203). The mock DB key swap is purely the rename + key-migration step in `main.tsx`; no version field exists. The migrator block at `main.tsx` handles the copy-on-read+delete-old for this key just like the others.

---

### `apps/admin-web/index.html:16` (theme bootstrap)

**Current** (line 16, inside the `<script>` IIFE):
```html
var raw = localStorage.getItem('sportzal:ui:v1');
```

**Target**:
```html
// Try clubcore key first, then legacy sportzal key (v1.10 shim).
var raw = localStorage.getItem('clubcore:ui:v2') || localStorage.getItem('sportzal:ui:v1');
```

Why fallback: theme bootstrap runs **before** React mounts and before the migrator in `main.tsx` runs. Without the legacy fallback, returning users would FOUC for one boot (theme migrated, but bootstrap reads new-only key which is still empty until migrator copies).

**Title tag** (line 12): also rename `<title>SportZal</title>` → `<title>clubcore</title>` (or keep titlecase `Clubcore` — see "specifics" in CONTEXT line 171: lowercase `clubcore` preferred unless titlecase context demands otherwise).

---

## Rename Surface Table — G-3: Backend Redis prefixes (`sz:*` → `cc:*`)

Per D-62-07: **no dual-read fallback**. Operator FLUSHDB at deploy is the contract. Five files swap literal string prefixes.

### `apps/backend/app/core/idempotency.py:38`

**Current**:
```python
IDEMPOTENCY_REDIS_PREFIX: str = "sz:idem:"
```

**Target**:
```python
IDEMPOTENCY_REDIS_PREFIX: str = "cc:idem:"
```

Also update docstring at line 18: `Redis key shape: `\`sz:idem:{key}\`` → `\`cc:idem:{key}\``.

---

### `apps/backend/app/integrations/telegram/handlers.py:105`

**Current**:
```python
dedup_key = f"sz:bot:update:{update_id}"
```

**Target**:
```python
dedup_key = f"cc:bot:update:{update_id}"
```

Also update docstring at line 100: `Key prefix ``sz:bot:update:{update_id}`` → ``cc:bot:update:{update_id}``.

---

### `apps/backend/app/integrations/yookassa/circuit_breaker.py:41-42`

**Current**:
```python
_CIRCUIT_KEY_PREFIX: Final[str] = "sz:yookassa:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "sz:yookassa:circuit_window:"
```

**Target**:
```python
_CIRCUIT_KEY_PREFIX: Final[str] = "cc:yookassa:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "cc:yookassa:circuit_window:"
```

---

### `apps/backend/app/integrations/email/circuit_breaker.py:37-38`

**Current**:
```python
_CIRCUIT_KEY_PREFIX: Final[str] = "sz:email:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "sz:email:circuit_window:"
```

**Target**:
```python
_CIRCUIT_KEY_PREFIX: Final[str] = "cc:email:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "cc:email:circuit_window:"
```

---

### `apps/backend/app/api/v1/_internal/yookassa/router.py:56`

**Current**:
```python
WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"
```

**Target**:
```python
WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "cc:yookassa:webhook:"
```

---

### Test fixtures sweep (G-3 tail)

After the five swaps above, grep backend test suite for hardcoded `"sz:"` literals — any test that asserts Redis key shape needs the same flip in the same commit. Planner MUST run:
```bash
grep -rn '"sz:' apps/backend/tests/ apps/backend/app/
grep -rn "'sz:" apps/backend/tests/ apps/backend/app/
```
…and include matches in G-3.

---

## Rename Surface Table — G-4: `CLUB_BRAND` constant extraction (D-62-02)

### NEW FILE: `apps/backend/app/core/branding.py`

**Target** (full file, ~10 lines):
```python
"""Phase 62 D-62-02 / CLUB_BRAND-EXTRACTION — single source of truth for the gym brand.

This is NOT the product/codebase name (`clubcore`). This IS the per-installation
gym brand surfaced in email subjects, footers, and invitation copy. Value is
locked to "Sportzal" placeholder in v1.10 (zero behaviour change per D-10-NO-NEW-BUSINESS).
Per-club configurable brand deferred to a future phase.
"""

from typing import Final

CLUB_BRAND: Final[str] = "Sportzal"
```

**Location justification** (CONTEXT line 72): `app/core/branding.py` recommended; planner may move to `app/core/constants.py` if alignment with existing constants module is cleaner. Constraint: single import surface.

---

### `apps/backend/app/modules/auth/email_templates.py`

**Current** (lines 73-110 — see Read above). Hits: subject literals + body literals + footer literals contain `"Sportzal"`.

**Target pattern** (per template):
```python
from app.core.branding import CLUB_BRAND

# Before:
subject="Код входа в Sportzal",
html=_ENV.from_string(
    "<h1>Код входа в Sportzal</h1>"
    ...
    "<p>Sportzal · noreply@mail.sportzal.ru</p>"
),

# After (option A — f-string at module import, preserves Final[str] subject):
subject=f"Код входа в {CLUB_BRAND}",
html=_ENV.from_string(
    f"<h1>Код входа в {CLUB_BRAND}</h1>"
    ...
    f"<p>{CLUB_BRAND} · noreply@mail.sportzal.ru</p>"
),
```

**Important — AST gate compatibility** (CONTEXT line 140): the locked-template AST test (`tests/unit/test_locked_email_templates_ast.py`) reads the `template_id` literal at the dispatcher callsite, not template bodies — so f-string interpolation of `CLUB_BRAND` should not trip the gate. **Planner MUST verify** by running the AST gate test post-extraction; if it fails, fall back to module-scope concatenation (`"…" + CLUB_BRAND + "…"`) which keeps the resulting string `Final[str]` AST-stable.

**Email FROM literal** (`noreply@mail.sportzal.ru`) is **NOT** rewritten via CLUB_BRAND — per D-62-03, it stays as the hardcoded fallback default behind the new `CLUBCORE_EMAIL_FROM` env. See G-4 config.py changes below.

---

### `apps/backend/app/modules/users/email_templates.py:47,51,60`

**Current**:
```python
_SUBJECT_USER_INVITATION: Final[str] = "Приглашение в Sportzal"
# ...
"<p>Вас пригласили в&nbsp;Sportzal в&nbsp;роли «{{ role_ru }}».</p>"  # noqa: RUF001
"Вас пригласили в Sportzal в роли «{{ role_ru }}».\n\n"  # noqa: RUF001
```

**Target**:
```python
from app.core.branding import CLUB_BRAND
_SUBJECT_USER_INVITATION: Final[str] = f"Приглашение в {CLUB_BRAND}"
# ...
f"<p>Вас пригласили в&nbsp;{CLUB_BRAND} в&nbsp;роли «{{{{ role_ru }}}}».</p>"  # noqa: RUF001
f"Вас пригласили в {CLUB_BRAND} в роли «{{{{ role_ru }}}}».\n\n"  # noqa: RUF001
```

⚠ **Jinja escape note**: `{{ role_ru }}` is a Jinja variable. When wrapping the string in a Python f-string, the literal braces must be doubled (`{{{{ role_ru }}}}`) so Python emits `{{ role_ru }}` for Jinja to consume. Alternative — use `+` concatenation to avoid the f-string brace-doubling tax:
```python
"<p>Вас пригласили в&nbsp;" + CLUB_BRAND + "&nbsp;в&nbsp;роли «{{ role_ru }}».</p>"
```
**Planner recommendation**: prefer the concatenation form for any string containing Jinja `{{ }}` placeholders.

---

### `apps/backend/app/modules/memberships/email_templates.py` (lines 86, 92, 101, 107, 116, 122, 131, 137, 146, 152, 161, 167 — 12 hits, all footer-shape)

Pattern: footer literal `"<p>Sportzal · noreply@mail.sportzal.ru</p>"` / `"Sportzal · noreply@mail.sportzal.ru"` appears once per template (HTML + text variant). The leading `Sportzal` becomes `{CLUB_BRAND}`; the trailing `noreply@mail.sportzal.ru` stays as-is (D-62-03 — operator env, not brand).

**Target** (representative):
```python
"<p>" + CLUB_BRAND + " · noreply@mail.sportzal.ru</p>"
"" + CLUB_BRAND + " · noreply@mail.sportzal.ru"
```

(Or f-string if no Jinja `{{ }}` shares the literal — most footers don't.)

---

### `apps/backend/app/modules/bookings/email_templates.py` (lines 66, 71, 80, 86, 95, 101, 110, 116 — 8 hits, footer-shape only)

Same pattern as memberships. Concatenation form preferred.

---

### `apps/backend/app/modules/payments/email_templates.py` (lines 94, 102, 113, 121 — 4 hits, footer-shape only)

Same pattern. Concatenation form preferred.

---

### `apps/backend/app/core/config.py` — `CLUBCORE_EMAIL_FROM` env (D-62-03)

**Current** (line 25):
```python
from_address: str = "noreply@mail.sportzal.ru"
```

**Target** — introduce `CLUBCORE_EMAIL_FROM` with deprecated-warning fallback for `SPORTZAL_EMAIL_FROM`:

Add a new top-level Settings field (NOT inside `EmailProviderSettings` — env-var precedence works better at `Settings` scope; the resolved value is then propagated into `email.from_address` via a `@model_validator`):

```python
import os
import structlog

class Settings(BaseSettings):
    # ... existing fields ...

    # Phase 62 D-62-03 — env-driven email FROM with v1.10-shim fallback chain.
    # Removal target: v1.11 / Phase 67 / RUN-07.
    clubcore_email_from: str | None = None  # canonical env: CLUBCORE_EMAIL_FROM
    sportzal_email_from: str | None = None  # legacy env (deprecated-warning, removal v1.11)

    @model_validator(mode="after")
    def _resolve_email_from(self) -> "Settings":
        # Precedence: CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (warn) → hardcoded default.
        resolved: str | None = None
        if self.clubcore_email_from:
            resolved = self.clubcore_email_from
        elif self.sportzal_email_from:
            structlog.get_logger(__name__).warning(
                "env_fallback_used",
                env="SPORTZAL_EMAIL_FROM",
                canonical="CLUBCORE_EMAIL_FROM",
                removal_target="v1.11/Phase 67/RUN-07",
            )
            resolved = self.sportzal_email_from
        # If neither env set, EmailProviderSettings.from_address retains its
        # hardcoded default "noreply@mail.sportzal.ru" (per CONTEXT specifics:
        # NOT renamed to mail.clubcore.ru — operator's DNS work).
        if resolved is not None:
            # Re-construct nested email block with the env-driven from_address.
            object.__setattr__(
                self.email,
                "from_address",
                resolved,
            )
        return self
```

**Default literal preservation** (CONTEXT line 172): keep `EmailProviderSettings.from_address = "noreply@mail.sportzal.ru"` as the hardcoded default — do NOT switch to `mail.clubcore.ru`. The fallback resolver only overrides if env is explicitly set.

---

## Rename Surface Table — G-5: Operator-tier (DB + env + docs)

### `apps/backend/.env.example:2`

**Current**:
```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal
```

**Target**:
```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/clubcore

# Phase 62 D-62-03 — Email FROM address override.
# Falls back to SPORTZAL_EMAIL_FROM (deprecated, v1.11 removal) and then
# to the hardcoded default "noreply@mail.sportzal.ru" if unset.
# CLUBCORE_EMAIL_FROM=noreply@mail.sportzal.ru
```

---

### `apps/backend/docker-compose.yml`

**Current**: 6 hits — 4 `DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal` (lines 10, 27, 41, 56), 1 `POSTGRES_DB: sportzal` (line 66), 1 `pg_isready -U app -d sportzal` (line 68).

**Target**: replace `sportzal` → `clubcore` at all 6 sites in the same commit. All four service `DATABASE_URL` entries MUST match `POSTGRES_DB` and the healthcheck — partial rename = boot failure.

```yaml
DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/clubcore
# ...
POSTGRES_DB: clubcore
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U app -d clubcore"]
```

**Operator runbook** (D-62-04): document pg_dump/restore cutover separately (NOT in code). Recommendation (CONTEXT line 73): terse runbook + reference Phase v1.5/v1.8 discipline; add as `.planning/handoff/clubcore-db-rename-runbook.md` (new file, plain markdown, ~30-50 lines).

---

### `CLAUDE.md` (root) — 6 hits

**Current** (representative — see grep output):
- Various references like "**Sportzal**" header, "Sportzal — CRM..." prose, "`sportzal:mock:v1`" in conventions, etc.

**Target**: rename all `Sportzal`/`sportzal` to `clubcore` (lowercase per CONTEXT line 171) **except**:
- Hardcoded examples that reference the old localStorage key in the legacy fallback explanation (if any) — keep with explicit "(legacy v1.10 shim, removed v1.11)" annotation.
- The CLUB_BRAND placeholder value "Sportzal" (string literal in code examples) — that's the gym brand, not the project name.

---

### `apps/backend/README.md` — 2 hits

Same treatment as root CLAUDE.md.

---

### `apps/admin-web/CLAUDE.md` (system-reminder showed content)

Contains references:
- `# CLAUDE.md — SportZal Adminka` header
- `Versioned localStorage key (`sportzal:mock:v1`)`

**Target**: rename header to `# CLAUDE.md — clubcore Adminka`; update localStorage key example to `clubcore:mock:v2`.

---

### `apps/admin-web/README.md`

(Not yet read — planner MUST read first then apply the same rename pass.)

---

## Rename Surface Table — G-6: `.planning/` forward-only rewrite + HISTORICAL_NOTE

### Hit counts (verified via grep)

| File | Hits | Notes |
|------|------|-------|
| `.planning/PROJECT.md` | 15 | Highest-density — product overview, current milestone, etc. |
| `.planning/ROADMAP.md` | 8 | Phase 62 description references both names; only forward-looking sections rewritten. |
| `.planning/REQUIREMENTS.md` | 8 | REB-01..08 spec itself. |
| `.planning/STATE.md` | 7 | Decision log; locked v1.10 decisions reference both names by design — careful audit before rewriting (some references are historical-context citations). |
| `.planning/MILESTONES.md` | 3 | |
| `.planning/RETROSPECTIVE.md` | 1 | |

**Action pattern**: `sportzal` → `clubcore` (lowercase preference per CONTEXT line 171). For prose that *describes the rename itself* (e.g. "sportzal → clubcore rename"), keep the historical word to preserve readability. For *current state* prose ("we are building sportzal"), rewrite.

---

### NEW FILE: `.planning/HISTORICAL_NOTE.md`

**Target** (~25 lines, per CONTEXT line 173 "short, under 30 lines"):

```markdown
# Historical Note: sportzal → clubcore Rename

**Created:** 2026-05-26 (Phase 62, v1.10)

## Why grep shows `sportzal` in `.planning/phases/47-61/*` and `.planning/audits/*`

These artefacts are the **immutable audit trail** of the project under its
previous name (`sportzal`). They are intentionally NOT rewritten — historical
context (decisions, lessons, retrospective discussions) must read as written.
Rewriting them would create commit-message ↔ file-content drift: commits in
those phases reference `@sportzal/api-client`; file content saying
`@clubcore/api-client` would be historically false.

## Active code uses `clubcore`

All current artefacts — code, configs, OpenAPI, OperatorEnv, and the
forward-looking docs (`.planning/PROJECT.md`, `MILESTONES.md`, `ROADMAP.md`,
`REQUIREMENTS.md`, `STATE.md`, `RETROSPECTIVE.md`, `handoff/clubcore-*`) —
use `clubcore`.

## Boundary

| Domain | Treatment |
|---|---|
| `.planning/phases/47-61/*` | Immutable (rename source = sportzal era) |
| `.planning/phases/62+/*` | Active (sportzal references = historical-context citations) |
| `.planning/audits/*` | Immutable (audit trail) |
| `.planning/handoff/v1.4..v1.9-*.md` | Immutable (operator handoffs from prior milestones) |
| `.planning/handoff/clubcore-*` | Active (current naming) |
| Top-level forward docs | Active |
| Code, configs, OpenAPI | Active |

## Lineage

- D-62-09 / D-10-HISTORY-IMMUTABLE — locked in Phase 62 / v1.10 decision log
- See `.planning/STATE.md` for the full decision rationale.
```

---

## Shared Patterns (cross-cutting)

### Shared Pattern Z-1 — Zustand persist version bump

See G-2 section above. Applied identically to three stores: session, uiPrefs, mock_db.

### Shared Pattern E-1 — CLUB_BRAND interpolation in email templates

**Source**: NEW `apps/backend/app/core/branding.py` (G-4).
**Apply to**: All 5 email_templates.py modules.

**Two interpolation styles** depending on whether the surrounding template body contains Jinja `{{ }}`:

```python
# Style A — pure footer literal, no Jinja braces nearby → f-string is fine:
f"<p>{CLUB_BRAND} · noreply@mail.sportzal.ru</p>"

# Style B — string contains Jinja {{ }} → use concatenation to avoid f-string brace-doubling:
"<p>Вас пригласили в&nbsp;" + CLUB_BRAND + "&nbsp;в&nbsp;роли «{{ role_ru }}».</p>"
```

**Constraint**: post-interpolation, the assigned name (`_SUBJECT_*`, `_HTML_*`, `_TEXT_*`) must remain a `Final[str]` (subject) or `Final[Template]` (body) that `jinja2.SandboxedEnvironment.from_string(...)` accepts. CLUB_BRAND being a module-import-time `Final[str]` preserves the locked-at-import invariant (D-42-23).

### Shared Pattern L-1 — Deprecated env logging

**Source**: structlog (per CONTEXT line 139).
**Apply to**: G-4 config.py only (single callsite for `SPORTZAL_EMAIL_FROM` legacy read).

```python
structlog.get_logger(__name__).warning(
    "env_fallback_used",
    env="SPORTZAL_EMAIL_FROM",
    canonical="CLUBCORE_EMAIL_FROM",
    removal_target="v1.11/Phase 67/RUN-07",
)
```

### Shared Pattern T-1 — `// TODO Phase 67 / RUN-07:` annotation

**Apply to**: every v1.10 backward-compat shim (3 sites):
- `apps/admin-web/src/app/main.tsx` — pre-rehydrate migrator block
- `apps/admin-web/index.html` — theme bootstrap fallback (`getItem('sportzal:ui:v1')`)
- `apps/backend/app/core/config.py` — `sportzal_email_from` field + fallback branch

Pattern (mirrors existing `// TODO Phase 7:` convention at `apps/admin-web/index.html:7`):
```
// TODO Phase 67 / RUN-07: drop v1.10 sportzal:* localStorage shim
# TODO Phase 67 / RUN-07: drop SPORTZAL_EMAIL_FROM legacy env fallback
```

---

## No Analog Found

| Surface | Reason |
|---|---|
| `apps/backend/app/core/branding.py` | New file — no analog needed; trivial single-constant module per CONTEXT recommendation. |
| `.planning/HISTORICAL_NOTE.md` | New file — no analog; structure specified inline in CONTEXT line 173. |
| Operator pg_dump/restore runbook (deferred — not file-creating in this phase per D-62-04 unless planner wants `.planning/handoff/clubcore-db-rename-runbook.md`) | Operator-tier; runbook content is informational, no codebase analog. Closest analogs: `.planning/handoff/v1.4-auth-runbook.md`, `.planning/handoff/v1.8-reports-runbook.md`, `.planning/handoff/v1.9-trainers-runbook.md` (existing handoff docs — terse + commands + verification step). |

---

## Coverage Summary

| Group | Files | Surfaces | Pattern source |
|---|---|---|---|
| G-1 | 6 | 6 pnpm rename sites | Self (same file before-rename) |
| G-2 | 4 | 4 storage key sites + version bumps + migrator | Self + Shared Pattern Z-1 |
| G-3 | 5 | 7 Redis prefix sites | Self |
| G-4 | 7 | NEW branding.py + 5 email_templates + 1 config.py | Shared Pattern E-1 + L-1 |
| G-5 | ~7 | DB rename + env + docs | Self (mechanical rename) |
| G-6 | 7 | .planning forward docs + NEW HISTORICAL_NOTE.md | Self + new content per CONTEXT line 173 |

**Total enumerated surfaces**: ~36 across 30+ files. **Atomic-commit requirement**: 6 groups (G-1 through G-6).

---

## Metadata

**Analog search scope**: `apps/`, `packages/`, `.github/workflows/`, root configs, `.planning/`.
**Files scanned**: ~30 (directly read or grep-scouted).
**Pattern extraction date**: 2026-05-26.
**CONTEXT lineage**: `.planning/phases/62-clubcore-rebrand/62-CONTEXT.md` (D-62-01..D-62-11).
**Research status**: disabled for this phase (per pattern_mapping_context).
