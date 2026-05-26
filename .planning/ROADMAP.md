# Roadmap: clubcore

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (shipped 2026-05-24) — see [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
- ✅ **v1.8 Reports + Audit Log read API** — Phases 54-57 (shipped 2026-05-24) — see [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 Trainers Complete** — Phases 58-61 (shipped 2026-05-26) — see [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)
- 🚧 **v1.10 clubcore Rebrand** — Phase 62 (in progress, started 2026-05-26 — narrowed from original 6-phase scope per D-10-SPLIT)
- 🔜 **v1.11 API Handoff + Production Hardening** — Phases 63-67 (not yet opened; scope deferred from v1.10 on 2026-05-26)

## Phases

<details>
<summary>✅ v1.0 — v1.9 SHIPPED (Phases 1-61)</summary>

All shipped milestones detailed in per-milestone ROADMAP archives above.

</details>

### v1.10 clubcore Rebrand (Phase 62)

- [ ] **Phase 62: clubcore Rebrand** — Переименовать `sportzal → clubcore` во всех package names, storage keys, Redis namespaces, docs + operator-tier renames (Postgres DB rename, `CLUBCORE_EMAIL_FROM` env с deprecated-warning fallback, DNS/DKIM checklist, `CLUB_BRAND` constant extraction); smoke-проверка зелёная под новым именем

### v1.11 API Handoff + Production Hardening (Phases 63-67)

- [ ] **Phase 63: Tech-Debt Sweep** — Закрыть DEFER-46-04 (ruff/format/mypy) + DEFER-36-04-B + DEFER-40-01 (run.sh hardening) на чистом дереве перед contract-freeze артефактами
- [ ] **Phase 64: Contract Freeze — OpenAPI Curation** — Explicit `operation_id=` + `tags=[...]` + spec hygiene + pre-freeze drift gate; курированный OpenAPI становится источником для всех handoff артефактов
- [ ] **Phase 65: Handoff Artifacts** — Curated Postman v2.1 + Newman CLI smoke; расширенный auth runbook под clubcore-именем; OpenAPI doc-site как приватный артефакт
- [ ] **Phase 66: Idempotency Hardening** — CR-01/02/02b закрыты: audit всех mutating endpoints, стандартизированный `Idempotency-Key` Redis-cache flow, документация в OpenAPI + auth runbook
- [ ] **Phase 67: Operator-Pending Runbook Execution** — Все накопившиеся operator-pending walkthroughs исполнены: v1.7 VER-03 + CARRY-01/02, v1.8 VER-01, v1.9 D-61-12; MailHog `--profile dev`; evidence захвачен + v1.11-native v1.10 back-compat shim removal (sportzal:* localStorage / SPORTZAL_EMAIL_FROM fallback)

## Phase Details

### Phase 62: clubcore Rebrand

**Goal**: Кодовая база полностью переименована из `sportzal` в `clubcore` (code identifiers + operator-tier renames: Postgres DB + email FROM env + DNS); контракт фиксируется под правильным именем; единственная фаза v1.10
**Depends on**: Nothing — единственная и финальная фаза v1.10; все handoff артефакты v1.11 создаются уже под clubcore-именем (D-62-FIRST + D-10-SPLIT)
**Requirements**: REB-01, REB-02, REB-03, REB-04, REB-05, REB-06, REB-07, REB-08
**Success Criteria** (what must be TRUE):

  1. После rebrand `docker compose up` поднимается без ошибок и backend pytest зелёный (полная suite ≥ 2181 passed, как v1.9 baseline)
  2. `pnpm --filter @clubcore/api-client typecheck` и `pnpm --filter @clubcore/api-client test` зелёные; админ-веб typecheck/lint/test зелёные (старые `@sportzal/*` ссылки больше не существуют)
  3. `openapi.json` + `schema.d.ts` регенерируются byte-stably под новым именем; CI drift-gate clean
  4. localStorage `copy-on-read + delete old key` миграция (Zustand `persist` version 1→2 с `migrate` callback); Redis cutover — operator FLUSHDB (документировано в runbook, runtime fallback отсутствует); env `CLUBCORE_EMAIL_FROM` → `SPORTZAL_EMAIL_FROM` (legacy, deprecated-warning) → hardcoded default fallback chain; Postgres DB renamed via documented operator pg_dump/restore; DNS/DKIM checklist под новый домен в operator-runbook; v1.11 stripping shims задокументирован как карательное действие
  5. `CLUB_BRAND` constant extracted в `app/core/branding.py` (значение неизменно — "Sportzal" placeholder; per-club configurable branding deferred to future phase); все ссылки на гимн-имя в email_templates переведены на единую константу
  6. Forward-only `.planning/` rewrite: PROJECT.md / MILESTONES.md / ROADMAP.md / REQUIREMENTS.md / RETROSPECTIVE.md / STATE.md / future handoff/ обновлены; historical `.planning/phases/47-61/*` + `.planning/audits/*` намеренно immutable как audit trail (документировано в `.planning/HISTORICAL_NOTE.md`)
  7. Все `import-linter`, ESLint `no-restricted-paths`, CI workflow + Docker labels работают с новыми package names; ноль ссылок на "sportzal" / "@sportzal" в активном коде (исключение — back-compat миграционные shims с TODO `remove in v1.11` + историческое `.planning/` дерево)

**Plans**: 7 plans

Plans:
**Wave 1**

- [x] 62-01-PLAN.md — G-1 pnpm package rename (@sportzal → @clubcore + workspace lockfile)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 62-02-PLAN.md — G-2 frontend localStorage migration + theme bootstrap (Zustand v1→v2)
- [x] 62-03-PLAN.md — G-3 backend Redis key prefixes (sz: → cc: across 5 modules)
- [ ] 62-04-PLAN.md — G-4 CLUB_BRAND extraction + CLUBCORE_EMAIL_FROM env with deprecated fallback
- [x] 62-05-PLAN.md — G-5 Postgres DB rename + operator runbook (pg_dump/restore + DNS/DKIM checklist)
- [ ] 62-06-PLAN.md — G-6 forward-only .planning/ + repo docs rewrite + HISTORICAL_NOTE.md

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 62-07-PLAN.md — G-7 final smoke gauntlet + evidence capture (12 gates)

### Phase 63: Tech-Debt Sweep (v1.11)

**Goal**: Pre-existing tree-wide CI tech-debt + накопившийся runbook tooling приведены в зелёное состояние ДО создания contract-freeze артефактов
**Depends on**: Phase 62 (v1.10 rebrand) — sweep работает на уже-переименованном дереве, чтобы не пересекаться с REB-* изменениями
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, DEBT-05
**Success Criteria** (what must be TRUE):

  1. `uv run ruff check` exit 0 на всём backend (79 errors → 0); никаких `# noqa` без обоснования в комментарии
  2. `uv run ruff format` применён ко всем 205+123 files (DEBT-02 + DEBT-04 residual); CI gate активирован
  3. `uv run mypy --strict` без attr-defined warnings; либо fix, либо явный type-ignore с обоснованием
  4. `v1.5-verification-evidence/run.sh` исполняется end-to-end против live `docker compose up` без hotfix-ситуаций; все 4+ pre-existing бага из v1.5 ретроспективы (Alembic revision-id length, /healthz vs /health, table name, fixture login defaults, RBAC actor on POST /trainer-slots, X-CSRF-Token header) закрыты в скрипте
  5. Полный backend pytest + admin-web vitest остаются зелёными после sweep (ни один format/lint cleanup не вносит regression)

**Plans**: TBD

### Phase 64: Contract Freeze — OpenAPI Curation (v1.11)

**Goal**: OpenAPI spec курирован под explicit `operation_id` + `tags` + `info` гигиену; курированный artefact становится единственным источником истины для всех handoff артефактов; baseline для contract-freeze зафиксирован
**Depends on**: Phase 63 (tech-debt sweep) — curation работает на clean tree чтобы byte-stable regen был достижим
**Requirements**: FRZ-01, FRZ-02, FRZ-03, FRZ-04, FRZ-05
**Success Criteria** (what must be TRUE):

  1. Каждый business endpoint в FastAPI имеет explicit `operation_id="<snake_case_stable_name>"` + `tags=[...]` ровно из 10 доменных tags (Auth/Clients/Memberships/Visits/Schedule/Bookings/Trainers/Payments/Reports/Audit-log); `app.openapi_tags = [...]` фиксирует порядок
  2. Перегенерированный `apps/backend/openapi.json` отражает новые `operationId` имена; `packages/api-client/src/schema.d.ts` обновлён лockstep; `schema.contract.test.ts` `AssertNonNever` форвард-гарды переименованы под новые operation IDs; runtime count-asserts зелёные
  3. `info.title` = "clubcore API", `info.version` = "1.10.0", `info.description` отражает milestone; `servers: [...]` указан явно; `components.securitySchemes` корректно описывает cookie-based auth + CSRF header
  4. `packages/api-client/package.json` `version: 1.10.0`; `packages/api-client/CHANGELOG.md` фиксирует baseline contract-freeze; README пакета документирует semver-discipline + "internal-only" статус (никаких npm publish инвокаций)
  5. CI drift-gate (`git diff --exit-code` на `openapi.json` + `schema.d.ts`) clean после двух подряд регенов; milestone-close runbook документирует operator-step pre-freeze verification

**Plans**: TBD

### Phase 65: Handoff Artifacts (v1.11)

**Goal**: Дизайн-команда получает приватный handoff пакет (Postman + Newman + Auth runbook + OpenAPI doc-site), полностью сгенерированный из курированного OpenAPI под clubcore-именем
**Depends on**: Phase 64 (OpenAPI curation) — все артефакты sourced из курированной spec; пред-курация дала бы плохие operationId/tags в Postman + doc-site
**Requirements**: HND-01, HND-02, HND-03, HND-04
**Success Criteria** (what must be TRUE):

  1. Curated Postman v2.1 collection (`.planning/handoff/clubcore-postman.json`) категоризирована по 10 доменам с auth-flow scenario + env templates (`local`, `staging`) + pre-filled body examples; сгенерирована из живого OpenAPI spec (не вручную)
  2. `newman run <collection> --environment <env>` локально исполняется зелёным; smoke-scenario набор покрывает auth + одну CRUD-операцию + один webhook (sandbox); exit-code non-zero на любом fail; integration зафиксирована в operator-runbook
  3. `.planning/handoff/clubcore-auth-runbook.md` существует, расширен под v1.7 (online payments + fiscal receipts), v1.6 multi-user + password-reset, v1.9 trainer payroll; live curl-flow scenarios verified end-to-end
  4. OpenAPI doc-site (Redocly или Stoplight CLI) генерируется локально в `apps/backend/openapi-docs/` (gitignored); operator-runbook документирует команду генерации + способ раздачи через приватный канал (zip / S3 presigned URL / прямая передача); ноль публичных hosting артефактов
  5. Все handoff артефакты ссылаются на `clubcore` имя; ни один артефакт не содержит residual `sportzal` упоминаний

**Plans**: TBD

### Phase 66: Idempotency Hardening (v1.11)

**Goal**: `Idempotency-Key` semantics стандартизирована, документирована и покрыта тестами; CR-01/02/02b carry-over из Phase 33 закрыты до contract-freeze final lock
**Depends on**: Phase 64 (OpenAPI curation) — Idempotency-Key reusable parameter добавляется в курированный spec; ordering after curation предотвращает повторный drift OpenAPI artefact
**Requirements**: IDM-01, IDM-02, IDM-03, IDM-04
**Success Criteria** (what must be TRUE):

  1. Audit-таблица всех mutating endpoints (POST/PATCH/DELETE) существует в `clubcore-auth-runbook.md`: каждый endpoint классифицирован как (a) требует Idempotency-Key, (b) inherently idempotent, или (c) explicitly exempt с обоснованием
  2. Endpoints, требующие key, при повторном запросе с тем же ключом возвращают cached response (body + status) из Redis TTL 24h — НЕ повторно вызывают handler; integration tests покрывают double-submit с одинаковым и разным ключами (memberships sale, PT-package sale, online payment create как минимум)
  3. `Idempotency-Key` стандарт: 16-128 chars, UUIDv4 рекомендован; storage key derivation документирован; semantics одинакова на всех endpoints (либо cached-replay, либо 409 на key-conflict — задокументировано per-endpoint)
  4. OpenAPI spec содержит `components.parameters.IdempotencyKey` reusable parameter; каждый endpoint, требующий key, имеет explicit `$ref` reference; `schema.d.ts` отражает изменения; drift-gate clean
  5. Полный backend pytest зелёный включая новые double-submit integration tests; ни один inherent-idempotent или exempt endpoint не помечен ошибочно как "требует key"

**Plans**: TBD

### Phase 67: Operator-Pending Runbook Execution (v1.11)

**Goal**: Все накопившиеся operator-credential-gated walkthroughs исполнены оператором с captured evidence; v1.11 milestone закрыт без operator-pending хвостов + v1.10 back-compat shims (sportzal:* localStorage, SPORTZAL_EMAIL_FROM fallback) выдернуты
**Depends on**: Phases 62-66 (вся кодовая часть завершена) — runbook execution требует stable backend под clubcore-именем + курированный OpenAPI + handoff артефакты ready
**Requirements**: RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06
**Success Criteria** (what must be TRUE):

  1. `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` существует и содержит captured evidence для каждого из 5 runbook walkthroughs (v1.7 VER-03 ЮKassa sandbox + v1.7 CARRY-01 RU email-deliverability `Authentication-Results` headers + v1.7 CARRY-02 owner countersign 19 templates + v1.8 VER-01 reports runbook + v1.9 D-61-12 trainers runbook)
  2. ЮKassa sandbox walkthrough (RUN-01) показывает full flow: sandbox payment created → succeeded webhook → membership активирован → fiscal receipt отправлен → email доставлен; evidence приложен
  3. RU email-deliverability probe (RUN-02) подтверждает SPF/DKIM/DMARC `pass` для yandex.ru + mail.ru + rambler.ru; `Authentication-Results` headers сохранены в evidence
  4. Owner countersign (RUN-03) на 19 locked email templates (15 v1.6 + 4 v1.7) signed-off attestation row в evidence document
  5. `docker-compose.yml` имеет optional MailHog service под `--profile dev` (RUN-06); README документирует как поднять; не активируется в production profile; smoke test зелёный с поднятым MailHog

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 62. clubcore Rebrand | v1.10 | 4/7 | In Progress|  |
| 63. Tech-Debt Sweep | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 64. Contract Freeze — OpenAPI Curation | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 65. Handoff Artifacts | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 66. Idempotency Hardening | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 67. Operator-Pending Runbook Execution | v1.11 | 0/0 | Not started (milestone not opened) | — |

---

*Roadmap last updated: 2026-05-26 — v1.10 narrowed to Phase 62 (clubcore Rebrand only, 8 REB requirements) per D-10-SPLIT during /gsd:discuss-phase 62; Phases 63-67 (24 requirements: DEBT:5 + FRZ:5 + HND:4 + IDM:4 + RUN:6) moved to v1.11 API Handoff + Production Hardening (not yet opened — REQUIREMENTS.md to be recreated fresh when v1.11 starts, per project convention).*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped.*
*v1.6 Coverage: 48/48 v1.6 requirements satisfied (8 INFRA + 11 EMAIL/AUTH-EM + 7 USERS + 5 RESET + 9 NOTIFY + 8 HANDOFF/VER). VER-12 + VER-14 deferred to v1.7 as DEFER-46-01/02.*
*v1.7 Coverage: 48/51 v1.7 requirements delivered. 3 operator-credential-gated deferred at close (CARRY-01, CARRY-02, VER-03).*
*v1.8 Coverage: 30/30 v1.8 requirements mapped.*
*v1.9 Coverage: 15/15 v1.9 requirements mapped.*
*v1.10 Coverage: 8/8 v1.10 requirements mapped (8 REB → Phase 62) — narrowed scope per D-10-SPLIT 2026-05-26.*
*v1.11 Planned: 24 requirements distributed across Phases 63-67 (5 DEBT + 5 FRZ + 4 HND + 4 IDM + 6 RUN) — milestone not yet opened.*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (BACKLOG)

**Goal:** Restore `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking — in both code paths: `POST /time-off?force=true` (Phase 59, `schedule/service.py:925`) and `cancel_slot` booked-cascade (`schedule/service.py:~471-504`). Closes the pre-v1.9 WR-06 documented limitation.

**Product decision (locked 2026-05-26):** Option B — always restore on owner-initiated cancellation. Rationale: client must never lose a prepaid PT session due to gym-side cancellation (industry norm; alternative leaks support burden and invites disputes).

**Requirements:** TBD (target ~3 reqs: restore-on-time-off-force, restore-on-cancel-slot-cascade, audit-event emission)

**Plans:** 0 plans

Plans:

- [ ] TBD — cross-module raw `sa.text()` UPDATE on `pt_packages.sessions_remaining` (pattern D-38-11), same UoW as booking cascade, in both schedule paths
- [ ] TBD — register `pt_session_credit_restored` in `LOCKED_AUDIT_EVENTS` with payload `{client_id, pt_package_id, booking_id, cancel_reason, sessions_remaining_before/after}`
- [ ] TBD — regression tests pinning new behavior in `tests/integration/schedule/test_time_off.py::test_create_time_off_force_cascades_booking_and_dispatches_dm` + equivalent for `cancel_slot` cascade
- [ ] TBD — remove `NOTE WR-06` block at `schedule/service.py:937` once behavior is fixed

**Source:** Phase 59 UAT WR-06 pending item; product decision recorded in this conversation 2026-05-26. Promote with `/gsd:review-backlog` when v1.10 milestone opens.
