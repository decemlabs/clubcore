# Requirements: clubcore (v1.10 — clubcore Rebrand)

**Defined:** 2026-05-26
**Last updated:** 2026-05-26 — milestone narrowed to Phase 62 only per D-10-SPLIT during /gsd:discuss-phase 62. Originally 32 requirements (6 phases); now 10 requirements (1 phase + 1 inserted closure phase 62.1). Remaining 24 requirements (Phases 63-67) moved to v1.11 API Handoff + Production Hardening — see "Planned for v1.11" section below; REQUIREMENTS.md will be recreated fresh when v1.11 opens (per project convention).

**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone goal:** Полностью переименовать кодовую базу `sportzal → clubcore` — code identifiers (пакеты, localStorage, Redis), operator-tier renames (Postgres DB, email FROM env с deprecated-warning fallback, DNS/DKIM checklist), `CLUB_BRAND` constant extraction в email_templates, forward-only `.planning/` rewrite (historical phase folders immutable как audit trail). Контракт замораживается под правильным именем для последующего v1.11 handoff cycle. Closure phase 62.1 (inserted 2026-05-26) finalizes the rename by removing the 4 back-compat shims and capturing local operator evidence (REB-09 + REB-10).

**Constraints carried into this milestone:**

- Backend-only — `apps/admin-web` остаётся frozen-as-of-v1.3 mock reference (внутри обновляются только package names + storage keys; UI/логика не трогается)
- Никакой публикации в публичные registry (npm/PyPI) — личный коммерческий проект
- Никаких новых бизнес-фич / ORM сущностей / `LOCKED_AUDIT_EVENTS` / `OWNER_ONLY` pairs (`CLUB_BRAND` constant extraction — pure refactor, value неизменно)
- Phase numbering continues from v1.9 — single phase: **Phase 62**. Phases 63-67 переходят в v1.11.
- Back-compat: localStorage `copy-on-read + delete`; Redis `operator FLUSHDB` (no runtime fallback); env `CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy, warning) → hardcoded` chain. Removal of shims в Phase 67 (v1.11).

## v1.10 Requirements

### Rebrand (sportzal → clubcore)

- [x] **REB-01**: pnpm packages переименованы — `@sportzal/api-client` → `@clubcore/api-client` + `@sportzal/ui` → `@clubcore/ui` (с обновлением `package.json` name + всех `workspace:` consumers + `pnpm-workspace.yaml` if needed) *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-02**: localStorage keys мигрированы — `sportzal:session:v1` → `clubcore:session:v2`, `sportzal:ui:v1` → `clubcore:ui:v2`, `sportzal:mock:v1` → `clubcore:mock:v2` (Zustand `persist` `version` bump + `migrate` callback c back-compat read из старых ключей ровно один релиз) *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-03**: Redis key namespace переименован — `sz:bot:update:*` → `cc:bot:update:*`, `sz:email:circuit:*` → `cc:email:circuit:*`, `sz:yookassa:circuit:*` → `cc:yookassa:circuit:*`, и все другие `sz:*` префиксы (с пометкой в operator-runbook о flush старых ключей при первом деплое) *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-04**: env vars без префикса `SPORTZAL_*` (проверить `.env.example` + `apps/backend/app/core/config.py` + `apps/admin-web/.env.*`); если префикс есть — переименовать на `CLUBCORE_*` (с deprecated-warning fallback для одного релиза) *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-05**: docs / comments / planning artifacts обновлены — CLAUDE.md, README.md, `docs/architecture.md`, `docs/conventions.md`, `docs/adr/*`, `.planning/PROJECT.md`, `.planning/MILESTONES.md`, `.planning/ROADMAP.md`, всё под `.planning/handoff/`, `.planning/research/`, `apps/backend/README.md`, `apps/admin-web/README.md` — заменить все упоминания "Sportzal" / "sportzal" / "@sportzal" на "clubcore" / "@clubcore" (с учётом регистра и контекста) *(satisfied 2026-05-26 via Phase 62 Plan 06 + prior plans 62-01..05; forward-only rewrite per D-62-09; HISTORICAL_NOTE.md authored per D-62-10)*
- [x] **REB-06**: `import-linter` контракты + ESLint правила обновлены под новые package names — `.importlinter` + `eslint.config.js` `no-restricted-paths` zones (если ссылаются на `@sportzal/*`) *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-07**: CI workflow `.github/workflows/ci.yml` пересматривает все ссылки на `@sportzal/*` пакеты в `pnpm --filter` инвокациях; backend Docker image labels / compose service names проверены *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [x] **REB-08**: backend + admin-web smoke-проверка после rebrand — backend `pytest` зелёный, admin-web `typecheck` + `lint` + `test` зелёные, `docker compose up` поднимается без ошибок, openapi.json + schema.d.ts регенерируются byte-stably под новым именем *(verified 2026-05-26 by /gsd:audit-milestone v1.10)*
- [ ] **REB-09**: Shim removal (4 sites) — strip the four `sportzal`-era back-compat shims tagged `TODO Phase 67 / RUN-07` AND their marker comments: (a) `apps/admin-web/src/app/main.tsx` localStorage migrator block, (b) `apps/admin-web/index.html` theme-bootstrap inline script `sportzal:ui:v1` fallback read, (c) `apps/backend/app/core/config.py:128-159` `SPORTZAL_EMAIL_FROM` deprecated-warning fallback resolver, (d) `.planning/handoff/clubcore-db-rename-runbook.md` `cc:*` Redis cutover note instructing operator FLUSHDB of `sz:*`. Acceptance: `grep -rn "TODO Phase 67 / RUN-07" .` returns 0 matches; full backend `pytest` + admin-web `vitest`/`typecheck`/`lint` remain green; admin-web boots in a browser with no localStorage migration log line emitted. *(pulled forward from v1.11/Phase 67/RUN-07 on 2026-05-26 per D-62.1-A1)*
- [ ] **REB-10**: Operator-pending evidence captured — `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` exists with (a) captured local pg_dump/restore round-trip output proving the runbook commands execute cleanly against the dev DB (restore target = dedicated `clubcore_smoke` DB so live `clubcore` DB is untouched), (b) explicit `DNS/DKIM: N/A-until-production` row with the trigger-condition documented (fires when a real `clubcore.*` domain is provisioned; resulting `Authentication-Results` headers append to the same file). *(pulled forward from v1.11/Phase 67/RUN-08 on 2026-05-26 per D-62.1-B1)*

## Planned for v1.11 (API Handoff + Production Hardening) — Not Yet Defined

The 22 requirements below originally appeared in v1.10 and are now scheduled for v1.11 (Phases 63-67). They remain unmapped in any active milestone; when v1.11 opens, `REQUIREMENTS.md` will be recreated fresh per project convention and these requirements will be re-stated there with updated context. Listed here as a snapshot of v1.11 intent.

<details>
<summary>v1.11 requirement snapshot (HND/FRZ/IDM/DEBT/RUN — 24 reqs)</summary>

### Handoff Artifacts (Phase 65 — Postman + Newman + Auth runbook + OpenAPI doc-site)

- **HND-01**: Curated Postman v2.1 collection — категоризирована по доменам (Auth / Clients / Memberships / Visits / Schedule / Bookings / Trainers / Payments / Reports / Audit-log), auth-flow scenario, env templates (`local`, `staging`), pre-filled body examples; sourced из живого OpenAPI spec
- **HND-02**: Newman CLI runner integration — smoke-scenario coverage; exit-code non-zero на любом fail
- **HND-03**: Auth runbook expanded — `.planning/handoff/v1.6-auth-runbook.md` → `clubcore-auth-runbook.md`, расширен под v1.7 + v1.6 + v1.9; live curl-flow scenarios verified
- **HND-04**: OpenAPI doc-site (private artifact) — генерируется локально через Redocly/Stoplight CLI; gitignored; НЕ публикуется публично

### Contract Freeze (Phase 64 — api-client + OpenAPI curation)

- **FRZ-01**: `@clubcore/api-client` contract freeze — `schema.d.ts` фиксируется как замороженный v1.11 контракт; `CHANGELOG.md` baseline; package.json `version: 1.11.0`
- **FRZ-02**: Pre-freeze drift gate — CI `git diff --exit-code` + operator pre-freeze verification step
- **FRZ-03**: OpenAPI tag curation — explicit `tags=[...]` на всех routes; 10 доменов; явный порядок через `app.openapi_tags`
- **FRZ-04**: Explicit `operation_id=` на ВСЕХ business endpoints (D-21-3 carry-over) — стабильные snake_case имена
- **FRZ-05**: OpenAPI spec hygiene — `info.title`/`version`/`description`/`servers`/`securitySchemes` корректны под clubcore + v1.11

### Idempotency Hardening (Phase 66 — CR-01/02/02b carry-over)

- **IDM-01**: Audit всех mutating endpoints (POST/PATCH/DELETE) на coverage `Idempotency-Key` (a/b/c per-endpoint классификация)
- **IDM-02**: CR-01 closed — `Idempotency-Key` стандартизирован: 16-128 chars UUIDv4, Redis TTL 24h, cached response replay
- **IDM-03**: CR-02 closed — integration tests на double-submit для memberships/PT-package/online payment endpoints
- **IDM-04**: CR-02b closed — semantics документирована в auth-runbook + `components.parameters.IdempotencyKey` OpenAPI reusable parameter

### Tech-debt Sweep (Phase 63)

- **DEBT-01**: DEFER-46-04 ruff errors closed — `uv run ruff check` exit 0 (79 → 0)
- **DEBT-02**: DEFER-46-04 ruff format applied — `uv run ruff format` 205 files; CI gate активирован
- **DEBT-03**: DEFER-46-04 mypy attr-defined cleaned — `uv run mypy --strict` без warnings
- **DEBT-04**: DEFER-36-04-B residual closed — 123 files под ruff format
- **DEBT-05**: DEFER-40-01 v1.5 runbook executed + hardened — `v1.5-verification-evidence/run.sh` end-to-end clean

### Operator-Pending Runbook Execution (Phase 67)

- **RUN-01**: v1.7 VER-03 — ЮKassa sandbox owner walkthrough; evidence в `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md`
- **RUN-02**: v1.7 CARRY-01 (DEFER-46-01) — live RU email-deliverability probe; `Authentication-Results` headers captured
- **RUN-03**: v1.7 CARRY-02 (DEFER-46-02) — owner countersign на 19 locked email templates (15 v1.6 + 4 v1.7)
- **RUN-04**: v1.8 VER-01 — live `docker compose up` reports runbook walkthrough
- **RUN-05**: v1.9 D-61-12 — trainers runbook walkthrough (513-line, 5 scenarios)
- **RUN-06**: DEFER-46-05 MailHog `--profile dev` integration в `docker-compose.yml`
*RUN-07 and RUN-08 pulled forward into v1.10 (Phase 62.1) on 2026-05-26 as REB-09 (shim removal) and REB-10 (operator-pending evidence) per D-62.1-X2 — see v1.10 active section above.*

</details>

## v2.0 Requirements (Out of v1.10 + v1.11 Scope)

### Frontend Integration + Launch

- **FE-01**: Дизайн-команда интегрирует production admin app против замороженного v1.10 контракта
- **FE-02**: Дизайн-команда строит production client app
- **FE-03**: Integration tests at seam — live backend + real frontends
- **FE-04**: Production deploy story (Kubernetes / Terraform / VPS — TBD)
- **FE-05**: `apps/admin-web` остаётся coexisting как mock reference

## Out of Scope

| Feature | Reason |
|---------|--------|
| `@clubcore/api-client` публикация в npm | Личный коммерческий проект; контракт раздаётся приватно дизайн-команде (v1.11 ownership) |
| OpenAPI doc-site публичный hosting (Redocly Cloud, public GitHub Pages, etc) | Тот же reason — приватный артефакт |
| Новые бизнес-фичи / новые ORM модели / новые `LOCKED_AUDIT_EVENTS` / новые `OWNER_ONLY` pairs | Не часть scope v1.10; код заморожен под handoff |
| Frontend (admin + client) production code | v2.0 milestone; дизайн-команда делает это вне репо |
| Kubernetes / Terraform / production deploy | Отдельный milestone после v2.0 |
| Multi-tenancy / RLS / `tenant_id` | Out of scope с Phase A (см. PROJECT.md Out of Scope) |
| Stripe / другие платёжные системы кроме ЮKassa | Запрещено регионом РФ |
| Архитектурные перестройки (Clean Architecture, microservices) | Modular monolith зафиксирован с Phase A |
| WR-06 (sessions_remaining restoration on owner force-cancel) | Pre-v1.9 product decision; отдельный `999.1-wr-06-*` parked phase в `.planning/phases/` |

## Traceability

Mapped 2026-05-26 by gsd-roadmapper; re-scoped 2026-05-26 to v1.10 = Phase 62 only per D-10-SPLIT. 8/8 active v1.10 requirements mapped; zero orphans, zero duplicates.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REB-01 | Phase 62 | Complete |
| REB-02 | Phase 62 | Complete |
| REB-03 | Phase 62 | Complete |
| REB-04 | Phase 62 | Complete |
| REB-05 | Phase 62 | Complete |
| REB-06 | Phase 62 | Complete |
| REB-07 | Phase 62 | Complete |
| REB-08 | Phase 62 | Complete |

**Coverage (v1.10 active):**
- v1.10 requirements: **8 total** (REB:8)
- Mapped to phases: **8/8** ✓
- Unmapped: 0

**Phase distribution (v1.10):**
- Phase 62 (Rebrand): 8 requirements

**v1.11 snapshot (22 requirements; not yet active):** see "Planned for v1.11" section above. Phases 63-67 (DEBT:5 + FRZ:5 + HND:4 + IDM:4 + RUN:4 — RUN-07/08 pulled forward into v1.10 as REB-09/10 per D-62.1-X2) — to be formally re-stated в свежем REQUIREMENTS.md когда v1.11 откроется.

---
*Requirements defined: 2026-05-26 — start of milestone v1.10 (originally clubcore Rebrand + API Handoff + Production Hardening, 32 requirements, 6 phases). Re-scoped 2026-05-26 to v1.10 = clubcore Rebrand (Phase 62 only, 8 REB requirements) per D-10-SPLIT during /gsd:discuss-phase 62 — Phase 62 scope expanded from "code-only rename" to include operator-tier renames (DB rename, CLUBCORE_EMAIL_FROM env, DNS/DKIM, FLUSHDB), making the original 6-phase milestone too heterogeneous to ship as one. Phases 63-67 (22 requirements) deferred to v1.11 API Handoff + Production Hardening (not yet opened).*
