# Requirements: clubcore (v1.10 — clubcore Rebrand + API Handoff + Production Hardening)

**Defined:** 2026-05-26
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone goal:** Переименовать проект в кодовой базе `sportzal → clubcore` (контракт замораживается под правильным именем), подготовить curated handoff артефакты для дизайн-команды v2.0 (Postman/Newman, OpenAPI doc-site, внутренний `@clubcore/api-client` freeze), завершить идемпотентность и accumulated tech-debt sweep, отработать накопившиеся operator-pending runbook'и.

**Constraints carried into this milestone:**

- Backend-only — `apps/admin-web` остаётся frozen-as-of-v1.3 mock reference (внутри обновляются только package names + storage keys; UI/логика не трогается)
- Никакой публикации в публичные registry (npm/PyPI) — личный коммерческий проект
- Никаких новых бизнес-фич / ORM сущностей / `LOCKED_AUDIT_EVENTS` / `OWNER_ONLY` pairs
- Rebrand — первая фаза; все handoff артефакты создаются уже под clubcore-именем
- Phase numbering continues from v1.9 — starts at **Phase 62**

## v1.10 Requirements

### Rebrand (sportzal → clubcore)

- [ ] **REB-01**: pnpm packages переименованы — `@sportzal/api-client` → `@clubcore/api-client` + `@sportzal/ui` → `@clubcore/ui` (с обновлением `package.json` name + всех `workspace:` consumers + `pnpm-workspace.yaml` if needed)
- [ ] **REB-02**: localStorage keys мигрированы — `sportzal:session:v1` → `clubcore:session:v2`, `sportzal:ui:v1` → `clubcore:ui:v2`, `sportzal:mock:v1` → `clubcore:mock:v2` (Zustand `persist` `version` bump + `migrate` callback c back-compat read из старых ключей ровно один релиз)
- [ ] **REB-03**: Redis key namespace переименован — `sz:bot:update:*` → `cc:bot:update:*`, `sz:email:circuit:*` → `cc:email:circuit:*`, `sz:yookassa:circuit:*` → `cc:yookassa:circuit:*`, и все другие `sz:*` префиксы (с пометкой в operator-runbook о flush старых ключей при первом деплое)
- [ ] **REB-04**: env vars без префикса `SPORTZAL_*` (проверить `.env.example` + `apps/backend/app/core/config.py` + `apps/admin-web/.env.*`); если префикс есть — переименовать на `CLUBCORE_*` (с deprecated-warning fallback для одного релиза)
- [ ] **REB-05**: docs / comments / planning artifacts обновлены — CLAUDE.md, README.md, `docs/architecture.md`, `docs/conventions.md`, `docs/adr/*`, `.planning/PROJECT.md`, `.planning/MILESTONES.md`, `.planning/ROADMAP.md`, всё под `.planning/handoff/`, `.planning/research/`, `apps/backend/README.md`, `apps/admin-web/README.md` — заменить все упоминания "Sportzal" / "sportzal" / "@sportzal" на "clubcore" / "@clubcore" (с учётом регистра и контекста)
- [ ] **REB-06**: `import-linter` контракты + ESLint правила обновлены под новые package names — `.importlinter` + `eslint.config.js` `no-restricted-paths` zones (если ссылаются на `@sportzal/*`)
- [ ] **REB-07**: CI workflow `.github/workflows/ci.yml` пересматривает все ссылки на `@sportzal/*` пакеты в `pnpm --filter` инвокациях; backend Docker image labels / compose service names проверены
- [ ] **REB-08**: backend + admin-web smoke-проверка после rebrand — backend `pytest` зелёный, admin-web `typecheck` + `lint` + `test` зелёные, `docker compose up` поднимается без ошибок, openapi.json + schema.d.ts регенерируются byte-stably под новым именем

### Handoff Artifacts (Postman + Newman + Auth runbook + OpenAPI doc-site)

- [ ] **HND-01**: Curated Postman v2.1 collection — категоризирована по доменам (Auth / Clients / Memberships / Visits / Schedule / Bookings / Trainers / Payments / Reports / Audit-log), auth-flow scenario (login → CSRF → mutating call → refresh → logout), env templates (`local`, `staging`), все запросы с pre-filled body examples; sourced из живого OpenAPI spec (не вручную)
- [ ] **HND-02**: Newman CLI runner integration — `newman run <collection> --environment <env>` исполняется локально и в operator-runbook'е; smoke-scenario набор покрывает auth + одну CRUD-операцию + один webhook (sandbox); exit-code non-zero на любом fail
- [ ] **HND-03**: Auth runbook expanded — `.planning/handoff/v1.6-auth-runbook.md` → переименован в `clubcore-auth-runbook.md`, расширен под v1.7 (online payments + fiscal receipts), v1.6 multi-user + password-reset, v1.9 trainer payroll; live curl-flow scenarios verified
- [ ] **HND-04**: OpenAPI doc-site (private artifact) — генерируется локально из `apps/backend/openapi.json` через Redocly/Stoplight CLI; output как `apps/backend/openapi-docs/` (gitignored по-умолчанию); operator-runbook документирует как запустить + как поделиться с дизайн-командой через приватный канал (zip/S3-presigned-URL/etc); НЕ публикуется публично

### Contract Freeze (api-client + OpenAPI curation)

- [ ] **FRZ-01**: `@clubcore/api-client` contract freeze — `packages/api-client/src/schema.d.ts` фиксируется как замороженный v1.10 контракт; добавлен `packages/api-client/CHANGELOG.md` с фиксацией baseline-версии; package.json `version: 1.10.0`; semver-discipline документирована в README пакета
- [ ] **FRZ-02**: Pre-freeze drift gate — CI workflow остаётся `git diff --exit-code` на `openapi.json` + `schema.d.ts`; добавляется операторский шаг в milestone-close runbook'е, проверяющий что после rebrand + curation regeneration выдает byte-stable артефакты
- [ ] **FRZ-03**: OpenAPI tag curation — все routes имеют explicit `tags=[...]` в FastAPI декораторе; tags соответствуют 10 доменам (Auth, Clients, Memberships, Visits, Schedule, Bookings, Trainers, Payments, Reports, Audit-log); порядок tags в OpenAPI spec явный (через `app.openapi_tags = [...]`)
- [ ] **FRZ-04**: Explicit `operation_id=` на ВСЕХ business endpoints (D-21-3 carry-over) — заменить auto-derived operationIds (которые включают router prefix + method name) на стабильные snake_case имена (e.g. `list_clients`, `create_membership`, `freeze_membership`, `record_visit`); обновлённый `schema.d.ts` отражает новые имена; `schema.contract.test.ts` форвард-гарды обновлены
- [ ] **FRZ-05**: OpenAPI spec hygiene — `info.title`, `info.version`, `info.description` отражают clubcore + v1.10; `servers: [...]` явно указан; `components.securitySchemes` корректно описывает cookie-based auth + CSRF header

### Idempotency Hardening (CR-01/02/02b carry-over)

- [ ] **IDM-01**: Audit всех mutating endpoints (POST/PATCH/DELETE) на coverage `Idempotency-Key` — для каждого endpoint решено: (a) требует Idempotency-Key, (b) inherently idempotent (UPSERT semantics), (c) явно exempt с обоснованием
- [ ] **IDM-02**: CR-01 closed — `Idempotency-Key` header стандартизирован: 16-128 chars UUIDv4 рекомендован; storage в Redis с TTL 24h; response cached с body+status; повторный запрос с тем же key возвращает cached response (а не повторно вызывает handler)
- [ ] **IDM-03**: CR-02 closed — endpoints which currently rely on `Idempotency-Key` (memberships sale, PT-package sale, online payment create) проходят integration tests на double-submit (с одинаковым key → identical response; с разным key → второй вызов rejected с 409 или принимается как новый — задокументировано per-endpoint)
- [ ] **IDM-04**: CR-02b closed — Idempotency-Key semantics документирована в `clubcore-auth-runbook.md` + в OpenAPI `components.parameters.IdempotencyKey` reusable parameter; все endpoints, требующие key, имеют explicit reference

### Tech-debt Sweep

- [ ] **DEBT-01**: DEFER-46-04 ruff errors closed — `uv run ruff check` exit 0 на всём backend (79 errors → 0); ruff `--fix` + manual review; никаких `# noqa` без обоснования в комментарии
- [ ] **DEBT-02**: DEFER-46-04 ruff format applied — `uv run ruff format` на всех 205 files; CI gate активирован (если был отключен)
- [ ] **DEBT-03**: DEFER-46-04 mypy attr-defined cleaned — `uv run mypy --strict` без attr-defined warnings; либо fix, либо явный type-ignore с обоснованием
- [ ] **DEBT-04**: DEFER-36-04-B residual closed — оставшиеся 123 files под ruff format обработаны (если не покрыты DEBT-02)
- [ ] **DEBT-05**: DEFER-40-01 v1.5 runbook executed + hardened — полное исполнение `v1.5-verification-evidence/run.sh` против live `docker compose up` стека; все 4 hotfix-ситуации из v1.5 ретроспективы закрыты в run.sh (Alembic revision-id length, /healthz vs /health, table name spelling, fixture login defaults, RBAC actor on POST /trainer-slots, X-CSRF-Token header); runbook script верифицирован end-to-end

### Operator-Pending Runbook Execution

- [ ] **RUN-01**: v1.7 VER-03 — ЮKassa sandbox owner walkthrough исполнен; evidence captured (sandbox payment created → succeeded webhook → membership активирован → fiscal receipt отправлен → email доставлен); recorded in `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md`
- [ ] **RUN-02**: v1.7 CARRY-01 (DEFER-46-01) — live RU email-deliverability probe запущен; `Authentication-Results` headers захвачены для yandex.ru + mail.ru + rambler.ru; SPF/DKIM/DMARC `pass` подтверждены; evidence in operator-evidence document
- [ ] **RUN-03**: v1.7 CARRY-02 (DEFER-46-02) — owner countersign на 19 locked email templates (15 v1.6 + 4 v1.7); signed-off attestation row в operator-evidence document
- [ ] **RUN-04**: v1.8 VER-01 — live `docker compose up` reports runbook walkthrough исполнен; revenue golden-path eyeball-match + manual Excel CSV-open Cyrillic check; evidence in operator-evidence document
- [ ] **RUN-05**: v1.9 D-61-12 — trainers runbook walkthrough исполнен (513-line, 5 scenarios: docker bring-up + payroll golden-path + recurring/time-off + trainer-usage report Excel + reception-403 enumeration); evidence in operator-evidence document
- [ ] **RUN-06**: DEFER-46-05 MailHog `--profile dev` integration — `docker-compose.yml` получает optional MailHog service под `--profile dev` для локального dev-окружения email-тестов; documented в README

## v2.0 Requirements (Out of v1.10 Scope)

### Frontend Integration + Launch

- **FE-01**: Дизайн-команда интегрирует production admin app против замороженного v1.10 контракта
- **FE-02**: Дизайн-команда строит production client app
- **FE-03**: Integration tests at seam — live backend + real frontends
- **FE-04**: Production deploy story (Kubernetes / Terraform / VPS — TBD)
- **FE-05**: `apps/admin-web` остаётся coexisting как mock reference

## Out of Scope

| Feature | Reason |
|---------|--------|
| `@clubcore/api-client` публикация в npm | Личный коммерческий проект; контракт раздаётся приватно дизайн-команде |
| OpenAPI doc-site публичный hosting (Redocly Cloud, public GitHub Pages, etc) | Тот же reason — приватный артефакт |
| Новые бизнес-фичи / новые ORM модели / новые `LOCKED_AUDIT_EVENTS` / новые `OWNER_ONLY` pairs | Не часть scope v1.10; код заморожен под handoff |
| Frontend (admin + client) production code | v2.0 milestone; дизайн-команда делает это вне репо |
| Kubernetes / Terraform / production deploy | Отдельный milestone после v2.0 |
| Multi-tenancy / RLS / `tenant_id` | Out of scope с Phase A (см. PROJECT.md Out of Scope) |
| Stripe / другие платёжные системы кроме ЮKassa | Запрещено регионом РФ |
| Архитектурные перестройки (Clean Architecture, microservices) | Modular monolith зафиксирован с Phase A |
| WR-06 (sessions_remaining restoration on owner force-cancel) | Pre-v1.9 product decision; отдельный `999.1-wr-06-*` parked phase в `.planning/phases/` |

## Traceability

Mapped 2026-05-26 by gsd-roadmapper. 32/32 requirements mapped to 6 phases (62-67); zero orphans, zero duplicates.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REB-01 | Phase 62 | Pending |
| REB-02 | Phase 62 | Pending |
| REB-03 | Phase 62 | Pending |
| REB-04 | Phase 62 | Pending |
| REB-05 | Phase 62 | Pending |
| REB-06 | Phase 62 | Pending |
| REB-07 | Phase 62 | Pending |
| REB-08 | Phase 62 | Pending |
| DEBT-01 | Phase 63 | Pending |
| DEBT-02 | Phase 63 | Pending |
| DEBT-03 | Phase 63 | Pending |
| DEBT-04 | Phase 63 | Pending |
| DEBT-05 | Phase 63 | Pending |
| FRZ-01 | Phase 64 | Pending |
| FRZ-02 | Phase 64 | Pending |
| FRZ-03 | Phase 64 | Pending |
| FRZ-04 | Phase 64 | Pending |
| FRZ-05 | Phase 64 | Pending |
| HND-01 | Phase 65 | Pending |
| HND-02 | Phase 65 | Pending |
| HND-03 | Phase 65 | Pending |
| HND-04 | Phase 65 | Pending |
| IDM-01 | Phase 66 | Pending |
| IDM-02 | Phase 66 | Pending |
| IDM-03 | Phase 66 | Pending |
| IDM-04 | Phase 66 | Pending |
| RUN-01 | Phase 67 | Pending |
| RUN-02 | Phase 67 | Pending |
| RUN-03 | Phase 67 | Pending |
| RUN-04 | Phase 67 | Pending |
| RUN-05 | Phase 67 | Pending |
| RUN-06 | Phase 67 | Pending |

**Coverage:**
- v1.10 requirements: **32 total** (REB:8 + HND:4 + FRZ:5 + IDM:4 + DEBT:5 + RUN:6)
- Mapped to phases: **32/32** ✓
- Unmapped: 0

**Phase distribution:**
- Phase 62 (Rebrand): 8 requirements
- Phase 63 (Tech-Debt Sweep): 5 requirements
- Phase 64 (Contract Freeze — OpenAPI Curation): 5 requirements
- Phase 65 (Handoff Artifacts): 4 requirements
- Phase 66 (Idempotency Hardening): 4 requirements
- Phase 67 (Operator-Pending Runbook Execution): 6 requirements

---
*Requirements defined: 2026-05-26 — start of milestone v1.10 clubcore Rebrand + API Handoff + Production Hardening (Phases continue from v1.9, start at Phase 62). Traceability mapped by gsd-roadmapper 2026-05-26: 32/32 covered.*
