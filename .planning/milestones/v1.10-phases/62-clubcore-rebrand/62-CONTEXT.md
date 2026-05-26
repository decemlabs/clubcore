# Phase 62: clubcore Rebrand - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Полная переименовка проекта `sportzal → clubcore` в кодовой базе и операционной инфраструктуре. Единственная фаза v1.10 (narrowed per D-10-SPLIT). Включает:

1. **Code identifiers**: pnpm `@sportzal/*` → `@clubcore/*`; localStorage `sportzal:*:v1` → `clubcore:*:v2`; Redis `sz:*` → `cc:*`; CI workflow + Docker labels + `import-linter` contracts + ESLint `no-restricted-paths` zones обновлены под новые имена.
2. **Operator-tier renames**: Postgres DB rename `sportzal → clubcore` (via documented pg_dump/restore operator runbook + `.env.example` + docker-compose updates); email FROM env `CLUBCORE_EMAIL_FROM` через `app/core/config.py` Settings (fallback chain: `CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy, deprecated-warning) → hardcoded default 'noreply@mail.sportzal.ru'`); DNS/DKIM/SPF/DMARC checklist под новый домен в operator runbook.
3. **`CLUB_BRAND` constant extraction**: единый источник в `app/core/branding.py`; значение неизменно ("Sportzal" placeholder); все ссылки на gym-name в `app/modules/*/email_templates.py` переводятся на эту константу. Pure refactor (zero behavioural change).
4. **Forward-only `.planning/` rewrite**: PROJECT.md / MILESTONES.md / ROADMAP.md / REQUIREMENTS.md / RETROSPECTIVE.md / STATE.md / future `handoff/`. Historical `.planning/phases/47-61/*` + `.planning/audits/*` намеренно immutable как audit trail. `.planning/HISTORICAL_NOTE.md` объясняет boundary.
5. **Smoke verification**: backend pytest зелёный (≥ 2181 passed, как v1.9 baseline); admin-web `typecheck` + `lint` + `test` зелёные; `docker compose up` поднимается без ошибок; `openapi.json` + `schema.d.ts` регенерируются byte-stably под новым именем; CI drift-gate clean.

**Out of scope (deferred to v1.11 or later):** Postman/Newman, OpenAPI doc-site, contract freeze, idempotency hardening, tech-debt sweep, operator-pending runbook execution — Phases 63-67 в **v1.11 API Handoff + Production Hardening**. Per-club configurable gym brand — future phase.

</domain>

<decisions>
## Implementation Decisions

### Brand vs Identifier Split

- **D-62-01 / D-10-BRAND-DISTINCTION**: `clubcore` = product/project name (codebase namespace), НЕ gym brand. Gym brand = per-installation operator config (future phase, out of v1.10 scope per D-10-NO-NEW-BUSINESS).
- **D-62-02 / CLUB_BRAND-EXTRACTION**: Hardcoded `"Sportzal"` string в `app/modules/{auth,users,memberships,bookings,payments}/email_templates.py` (email subjects, footers, invitation copy) extracted в **single `CLUB_BRAND` constant** в `app/core/branding.py`. Value неизменно — остаётся `"Sportzal"` placeholder. Это pure refactor (zero behaviour change), формально совместимо с D-10-NO-NEW-BUSINESS — planner MUST verify constant extraction не вводит конфиг-flag и не меняет runtime поведение.
- **Implication**: `noreply@mail.sportzal.ru` (email FROM) НЕ переименовывается просто на `noreply@mail.clubcore.ru` — это бы означало выбрать `clubcore` как gym brand. Вместо этого: см. D-62-03 (operator-tier email env).

### Operator-Tier Renames

- **D-62-03 / CLUBCORE_EMAIL_FROM**: Email FROM address пересажен с hardcode на env-driven via `app/core/config.py` Settings (Pydantic). Fallback chain:
  1. `CLUBCORE_EMAIL_FROM` (canonical)
  2. `SPORTZAL_EMAIL_FROM` (legacy; reading emits structured deprecated-warning log; one-release window)
  3. Hardcoded default `"noreply@mail.sportzal.ru"` (preserves current production behaviour if neither env set)
  Removal of legacy fallback in **v1.11 / Phase 67 / RUN-07**.
- **D-62-04 / DB-RENAME**: Postgres database `sportzal` → `clubcore`. Operator action: documented `pg_dump | pg_restore` runbook (NOT Alembic migration — DB rename is operator-tier, not schema-tier). `apps/backend/.env.example` `DATABASE_URL` updated to `.../clubcore`; `docker-compose.yml` `POSTGRES_DB` updated; documented one-time cutover step.
- **D-62-05 / DNS-CHECKLIST**: DNS/DKIM/SPF/DMARC checklist для нового email FROM domain (если оператор решает мигрировать на `mail.clubcore.ru` или другой) добавлен в operator runbook. v1.10 НЕ переименовывает действующий домен `mail.sportzal.ru` — это операторская работа за пределами кода; checklist описывает шаги, не выполняет их.

### Back-Compat Migration Mechanics

- **D-62-06 / localStorage**: Strategy = **copy-on-read + delete-old key**.
  Implementation: Zustand `persist` `version: 1 → 2` bump + `migrate(persistedState, version): if (version === 1) { return { ...persistedState, /* shape unchanged */ }; }`. Storage key namespace transitions:
  - `sportzal:session:v1` → `clubcore:session:v2`
  - `sportzal:ui:v1` → `clubcore:ui:v2`
  - `sportzal:mock:v1` → `clubcore:mock:v2`
  On first v1.10 boot: read `clubcore:*:v2`; if absent, read `sportzal:*:v1`, write to `clubcore:*:v2`, `localStorage.removeItem('sportzal:*:v1')`. Single migration event per browser; clean storage after first session.
- **D-62-07 / Redis**: Strategy = **operator FLUSHDB at deploy; NO runtime fallback**. v1.10 code reads/writes только `cc:*` namespaces; operator runbook documents `redis-cli FLUSHDB` (или scoped `SCAN + DEL` on `sz:*` prefixes) as a one-time deploy step. Tradeoffs accepted:
  - Idempotency keys (`sz:idem:*` 1h TTL) reset — brief window of in-flight idempotent requests may be replayed; documented in runbook.
  - Circuit breakers (`sz:email:circuit:*`, `sz:yookassa:circuit:*`) reset → first call after cutover may hit a stale-but-not-yet-failed external service.
  - Telegram dedup (`sz:bot:update:*` 1h TTL) reset — brief window of dup-update risk; mitigated by Telegram's own ~1-day dedup ID lifecycle.
  - Yookassa webhook dedup (`sz:yookassa:webhook:*` 24h TTL) reset — brief replay window; mitigated by FSM idempotency in handler.
  Code complexity stays low (no dual-read fallback in 7+ modules); operator pays a one-time cutover cost.
- **D-62-08 / env vars**: REB-04 was a no-op precondition check — no `SPORTZAL_*` env prefix existed prior to v1.10. New `CLUBCORE_EMAIL_FROM` env (D-62-03) is the only env-prefix work. `SPORTZAL_EMAIL_FROM` is introduced *only as the deprecated-warning legacy reader* — i.e. operators upgrading from a hypothetical earlier mid-development override are caught; on greenfield deploys only `CLUBCORE_EMAIL_FROM` (or the hardcoded default) is read.

### Historical `.planning/` Scope

- **D-62-09 / FORWARD-ONLY / D-10-HISTORY-IMMUTABLE**: REB-05 rewrite scope limited to:
  - Forward-looking docs: `.planning/PROJECT.md`, `.planning/MILESTONES.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/RETROSPECTIVE.md`, `.planning/STATE.md`, future `.planning/handoff/clubcore-*` artifacts
  - Top-level repo docs: `CLAUDE.md`, `README.md`, `apps/backend/README.md`, `apps/admin-web/README.md`, `apps/backend/CLAUDE.md`, `apps/admin-web/CLAUDE.md`, `docs/architecture.md`, `docs/conventions.md`, `docs/adr/*` (if exists)
  - Active code as defined by REB-01..08
  Historical artefacts namely **`.planning/phases/47-61/*` + `.planning/audits/*` + older `.planning/handoff/v1.X-*.md`** are intentionally immutable — they are decision-time audit trail of the project under its previous name. Rewriting them would distort retrospective context and create commit-message ↔ file-content drift (commits in those phases reference `@sportzal/api-client`; file content saying `@clubcore/api-client` would be historically false).
- **D-62-10 / HISTORICAL_NOTE**: Write `.planning/HISTORICAL_NOTE.md` (new file) explaining: `.planning/phases/47-61/*` and `.planning/audits/*` reference legacy product name `sportzal`. Audit trail intentionally immutable. Active code uses `clubcore`. Future readers don't need to ask why grep shows the name.

### Mid-Rebrand Build Stability (Claude's Discretion — flag for planner)

- **D-62-11 / ATOMIC-PACKAGE-RENAME**: Not explicitly discussed but implied by REB-01 + smoke verification — pnpm package renames (`@sportzal/*` → `@clubcore/*`) and their consumer updates (workspace + import sites) MUST land in a single atomic commit (or coordinated short sequence) because cross-package imports break mid-rename if package name and consumer references are out of sync. Planner should structure plan tasks to keep build green at every commit boundary.

### Claude's Discretion

- **Plan structure**: Planner decides whether to split into multiple plans (e.g. plan-01 code-rename / plan-02 operator-tier / plan-03 .planning rewrite / plan-04 smoke) or one large plan with task-level waves. Recommendation: split by surface so smoke verification can run after each, reducing blast radius.
- **CLUB_BRAND constant location**: `app/core/branding.py` is suggested but planner may choose `app/core/constants.py` or `app/core/config.py` (next to Settings) if alignment with existing patterns is cleaner. Constraint: single source of truth; no per-module redefinition.
- **DB rename runbook depth**: Operator runbook for pg_dump/restore can be terse (just the commands + verification step) or full-blown (covering rollback, downtime estimation, data-volume considerations). Recommendation: terse + reference v1.5/v1.8 runbook discipline.

### Folded Todos

None — `cross_reference_todos` step skipped (no relevant pending todos against Phase 62 scope).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope (Roadmap + Requirements)

- `.planning/ROADMAP.md` §"Phase 62: clubcore Rebrand" — phase boundary, dependencies, success criteria (7 SCs including operator-tier renames + CLUB_BRAND + forward-only .planning)
- `.planning/REQUIREMENTS.md` §"Rebrand (sportzal → clubcore)" — 8 REB requirements (REB-01..08) with explicit file-path enumeration
- `.planning/REQUIREMENTS.md` §"Planned for v1.11" — what is OUT of v1.10 scope (deferred to v1.11 milestone, not yet opened)

### Locked Project Decisions

- `.planning/STATE.md` §"Accumulated Context / Decisions" — v1.10 locked decisions (D-62-FIRST, D-10-NO-PUBLISH, D-10-BACKEND-ONLY, D-10-NO-NEW-BUSINESS, D-10-BACK-COMPAT, D-10-SPLIT, D-10-BRAND-DISTINCTION, D-10-HISTORY-IMMUTABLE)
- `.planning/PROJECT.md` §"Current Milestone: v1.10 clubcore Rebrand" — narrowed scope rationale + constraints
- `.planning/PROJECT.md` §"Out of Scope" — multi-tenancy, Stripe, production frontend, etc.

### Codebase Conventions (Repo-Level)

- `CLAUDE.md` — project-wide tech stack, naming, conventions, architecture
- `apps/backend/CLAUDE.md` (if exists) — backend-specific rules
- `apps/admin-web/CLAUDE.md` — frontend-specific rules (FROZEN: only package names + storage keys may change; UI/logic untouched per D-10-BACKEND-ONLY)

### Surfaces Affected by Rebrand (Code Files — verified via grep scout)

- `apps/admin-web/src/shared/session/store.ts:5` — `STORAGE_KEY = 'sportzal:session:v1'`
- `apps/admin-web/src/shared/theme/uiPrefsStore.ts:15` — `STORAGE_KEY = 'sportzal:ui:v1'`
- `apps/admin-web/src/shared/api/services/mock/_db.ts:7` — `STORAGE_KEY = 'sportzal:mock:v1'`
- `apps/admin-web/index.html` (theme-bootstrap) — references `'sportzal:ui:v1'`
- `apps/backend/app/core/idempotency.py:38` — `IDEMPOTENCY_REDIS_PREFIX = "sz:idem:"`
- `apps/backend/app/integrations/telegram/handlers.py:105` — `dedup_key = f"sz:bot:update:{update_id}"`
- `apps/backend/app/integrations/yookassa/circuit_breaker.py:41-42` — `_CIRCUIT_KEY_PREFIX = "sz:yookassa:circuit:"` + `_WINDOW_KEY_PREFIX = "sz:yookassa:circuit_window:"`
- `apps/backend/app/integrations/email/circuit_breaker.py:37-38` — `_CIRCUIT_KEY_PREFIX = "sz:email:circuit:"` + `_WINDOW_KEY_PREFIX = "sz:email:circuit_window:"`
- `apps/backend/app/api/v1/_internal/yookassa/router.py:56` — `WEBHOOK_DEDUP_KEY_PREFIX = "sz:yookassa:webhook:"`
- `apps/backend/app/modules/{auth,users,memberships,bookings,payments}/email_templates.py` — hardcoded `"Sportzal"` strings + `"noreply@mail.sportzal.ru"` (extract to CLUB_BRAND + CLUBCORE_EMAIL_FROM env)
- `apps/backend/.env.example` — `DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal` (rename DB)
- `packages/api-client/package.json` — `@sportzal/api-client` → `@clubcore/api-client` (name + workspace consumers + lockfile)
- `packages/ui/package.json` — `@sportzal/ui` → `@clubcore/ui`
- `.github/workflows/ci.yml` — `pnpm --filter @sportzal/*` invocations
- `pnpm-workspace.yaml` — if any namespaced refs
- `pnpm-lock.yaml` — autoregenerated on rename
- `.importlinter` — if references `@sportzal/*` (TypeScript-side equivalent in ESLint zones)
- `eslint.config.js` — `no-restricted-paths` zones if scoped to `@sportzal/*`

### Historical Context (Read for Context, Do NOT Modify)

- `.planning/HISTORICAL_NOTE.md` (to be authored in this phase) — explains why grep finds `sportzal` in `.planning/phases/47-61/*` and `.planning/audits/*`
- `.planning/phases/47-61/*` + `.planning/audits/*` — immutable audit trail per D-62-09

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Zustand `persist` `version` + `migrate` pattern** (`apps/admin-web/src/shared/session/store.ts:5-10`, `uiPrefsStore.ts:15-20`) — already used; bump `version: 1 → 2` and implement `migrate` callback in the same form for all three stores
- **`app/core/config.py` Pydantic Settings** — already the canonical env-loading surface (`SECRET_KEY`, `DATABASE_URL`, etc.); add `CLUBCORE_EMAIL_FROM` here with fallback resolver
- **Structured logging via `structlog`** (per stack constraints) — use for deprecated-warning emit when `SPORTZAL_EMAIL_FROM` is read; `structlog.get_logger(__name__).warning("env_fallback_used", env="SPORTZAL_EMAIL_FROM", canonical="CLUBCORE_EMAIL_FROM", removal_target="v1.11/Phase 67")`
- **AST gate pattern** (`LOCKED_AUDIT_EVENTS`, `LOCKED_EMAIL_TEMPLATES`, `YOOKASSA_TRUSTED_IPS`) — if `CLUB_BRAND` constant deserves AST-enforcement (e.g. forbid `"Sportzal"` literal in email_templates after extraction), planner may add a small AST walker similar to `tests/unit/test_locked_email_templates.py`. Probably overkill for a single constant; planner's call.

### Established Patterns

- **REG-29-03 double-wire pattern**: any new Protocol slot must register at BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup` (worker subset). N/A here unless a new slot is introduced (not expected for rename).
- **Byte-stable OpenAPI regen** — `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` must regen identically (or with only expected diffs like `info.title` if changed); CI drift-gate guards this. Phase 62 must verify drift-gate stays clean after rename.
- **Three-way RBAC parity** (`apps/backend/app/core/permissions.py` ↔ `apps/admin-web/src/shared/session/can.ts` ↔ `apps/admin-web/src/shared/session/registry.ts`) — no changes expected (D-10-NO-NEW-BUSINESS: no new OWNER_ONLY pairs), but parity tests must stay green after package rename.
- **D-39-02 module-scope copy ownership** — `app/modules/*/email_templates.py` hold locked templates; CLUB_BRAND extraction must preserve template-locality (constant imported, not centralized templates).

### Integration Points

- **localStorage migrate runs in `apps/admin-web/src/app/main.tsx:13`** (`persist.rehydrate()` awaited before React mounts) — migration callback must succeed without throwing, even on missing legacy key.
- **Redis startup probe** in `app/main.py` — if rename has any `cc:*` boot-check (probably none needed), it lives here.
- **Composition root** — any future `CLUBCORE_EMAIL_FROM` consumer wires via Settings injection at `app/main.py:create_app()` + worker startup.

### Smoke Test Surface (REB-08 success criterion)

- `cd apps/backend && uv run pytest -q` — full backend suite (≥ 2181 passed, ≤ 6 skipped per v1.9 baseline)
- `pnpm --filter @clubcore/api-client typecheck` + `pnpm --filter @clubcore/api-client test`
- `pnpm --filter @clubcore/ui typecheck` (if applicable)
- admin-web: `pnpm --filter admin-web typecheck` + `pnpm --filter admin-web lint` + `pnpm --filter admin-web test`
- `docker compose up` (backend + Postgres + Redis + bot + ARQ + migrate) — health check + smoke RBAC enumeration
- `uv run lint-imports` (import-linter) — 3 kept, 0 broken
- `cd apps/backend && uv run python scripts/export_openapi.py` + `pnpm --filter @clubcore/api-client codegen` → `git diff --exit-code` on `openapi.json` + `schema.d.ts` (drift gate)
- `git diff` on `permissions.py` / `can.ts` / `registry.ts` should remain empty post-rename (no behaviour change)

</code_context>

<specifics>
## Specific Ideas

- **clubcore (lowercase) vs Clubcore (titlecase)**: Project name is `clubcore` (lowercase per ROADMAP/PROJECT.md and existing references). Package names follow npm convention (`@clubcore/api-client`). Where titlecase appears in prose (e.g. "Clubcore API" in OpenAPI `info.title`), prefer lowercase `clubcore` unless a specific user-facing context demands titlecase — none identified in v1.10 scope.
- **Email FROM hardcoded default**: Planner SHOULD keep the hardcoded fallback default value `"noreply@mail.sportzal.ru"` unchanged (NOT switch to `"noreply@mail.clubcore.ru"`) until the operator actually configures DNS for a new domain. The fallback chain's job is to read env first; the default is just "what runs if no env is set". Switching the default to a domain that doesn't exist would silently break email delivery on greenfield boots.
- **`.planning/HISTORICAL_NOTE.md`** body should be short (under 30 lines): one paragraph explaining the audit-trail-immutability principle, the file/folder boundary (what gets rewritten vs what stays), and a pointer to D-62-09/D-10-HISTORY-IMMUTABLE in STATE.md.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to v1.11 (Phases 63-67) — original v1.10 scope per D-10-SPLIT

- Postman v2.1 collection + Newman CLI smoke (HND-01, HND-02)
- Curated auth runbook expansion (`clubcore-auth-runbook.md`, HND-03)
- Private OpenAPI doc-site (Redocly/Stoplight, HND-04)
- OpenAPI tag curation + explicit `operation_id=` (FRZ-03, FRZ-04)
- OpenAPI spec hygiene (FRZ-05)
- `@clubcore/api-client` contract freeze (`version: 1.11.0`, CHANGELOG, semver-discipline) (FRZ-01, FRZ-02)
- Idempotency hardening CR-01/02/02b (IDM-01..04)
- Tech-debt sweep: DEFER-46-04 ruff/format/mypy (DEBT-01..03), DEFER-36-04-B (DEBT-04), DEFER-40-01 run.sh hardening (DEBT-05)
- Operator-pending runbook execution: VER-03, CARRY-01/02, VER-01, D-61-12, MailHog (RUN-01..06)
- v1.10-shim removal (sportzal:* localStorage migrate logic + SPORTZAL_EMAIL_FROM env fallback) — new v1.11 reqs RUN-07, RUN-08

### Deferred to future phases (after v1.11)

- **Per-club configurable gym brand** — `CLUB_BRAND` constant is foundation; v1.11+ phase may wire it to operator config (env or runtime setting). Out of v1.10 per D-10-NO-NEW-BUSINESS.
- **Email domain migration** (`mail.sportzal.ru` → `mail.clubcore.ru` or other) — operator-controlled DNS work; v1.10 ships the env mechanism + checklist but does not change the actual sending domain.

### Reviewed Todos (not folded)

None reviewed in this discussion.

</deferred>

---

*Phase: 62-clubcore-rebrand*
*Context gathered: 2026-05-26*
