# Requirements: clubcore — v4.1 Codebase Hardening

**Defined:** 2026-07-26
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone framing:** quality/tech-debt milestone. Новых продуктовых фич нет. Требования описывают **аудит-и-фикс дисциплину**, а не пользовательские возможности — «пользователь» здесь maintainer, а наблюдаемый результат — состояние реестра дефектов и зелёные гейты.

**Done-bar (наследует D-V40-LOCAL-VALIDATE):** каждая строка DEFECT-реестра имеет терминальную диспозицию (`fixed+verified` либо `deferred`+причина); боевое железо и продакшн-креды вне scope, сфабрикованные доказательства запрещены.

**Registry contract:** строка реестра = `id, category, severity, anchor, repro, evidence, disposition, owning_phase, blocks/blocked_by, locked_invariant_risk, reason (если deferred)`.

- **Disposition (3 состояния):** `fixed+verified` (evidence — перезапускаемый артефакт: команда + вывод, путь к логу/скриншоту, имя contract-теста; проза не принимается) · `fixed+unverified` (транзитное, не финальное — до закрытия milestone должно стать `fixed+verified` либо `deferred`) · `deferred` (финальное, с причиной `operator-pending` / `out-of-scope` / `accepted-risk`).
- **Category (3):** FUNC · HYGIENE · INFRA.
- **Severity (3):** Blocker (падает / недоступно / неюзабельно) · Major (работает неверно без падения) · Minor (косметика, ноль поведенческого эффекта).

---

## v4.1 Requirements

### Audit (AUD) — read-only фаза, производит единственный реестр

- [x] **AUD-01**: Существует единственный артефакт `.planning/audits/v4.1-DEFECT-REGISTRY.md` со схемой строки из Registry contract выше; на закрытии аудит-фазы он заморожен (findings, обнаруженные позже, дописываются с тегом `discovered-during-fix` и НЕ порождают новый аудит-проход)
- [x] **AUD-02**: Статический прогон гигиены выполнен и весь его вывод затриажен в строки реестра: перечисление всех TODO/FIXME/HACK/XXX маркеров, одноразовые прогоны Knip + jscpd + vulture + deptry, ревизия 3 контрактов import-linter и ESLint-границ admin
- [x] **AUD-03**: Построен reachability-манифест — трёхсторонний join `router` × `nav-items` × реальный экранный компонент — для `apps/admin` и `apps/client`; каждый задуманный экран либо доказан достижимым, либо стал строкой реестра
- [x] **AUD-04**: Edge-case seed-датасет авторски создан ДО live-backend охоты: nullable-поля реально null, сущности с пустой историей, пагинация дальше первой страницы, все семейства ошибок (422/403/404/409/429/anti-oracle), денежные и DST-граничные значения. Повторный прогон чистого демо-сида доказательством не считается
- [ ] **AUD-05**: Построен Zod↔wire манифест (каждый call-site API × его Zod-схема) и проверен механически по всем ~25 доменам `apps/admin/src/features/*` за один проход; каждое расхождение — строка реестра
- [ ] **AUD-06**: Браузерный UAT-обход каждого достижимого экрана `apps/admin` и `apps/client` против реального backend на edge-case сиде; падения, пустые экраны и ошибки консоли — строки реестра
- [ ] **AUD-07**: 23 operator-pending пункта v4.0 затриажены на «доказуемо локально в k3d» vs «требует железа/кредов»; каждый — строка реестра, локальные с квалификатором `(k3d-scope)`
- [x] **AUD-08**: Во время аудит-фазы код приложения не правится (read-only): ни один дефект не починен инлайн без строки реестра

### Test infrastructure (TEST) — ранняя, таймбоксированная, узкая

- [ ] **TEST-01**: Свежий полный прогон backend pytest подтверждает, что фикс isolation-deadlock от закрытия v3.2 (`f438ced2` — маркер `no_permissive_booking_config` на 4 модулях + восстановление teardown booking-race + `pytest-timeout` 180s; диагноз в `.planning/debug/pytest-isolation-deadlock.md`) всё ещё держится: сюит доходит до конца без зависания. Если deadlock регрессировал или фикс оказался частичным — устранить либо задокументировать ограниченный per-module обход. Таймбокс соблюдён, расширение в полную археологию тестов не допущено.
  **Посылка исправлена 2026-07-26:** формулировка изначально предполагала, что deadlock всё ещё открыт — это взято из устаревшего текста закрытия v3.2 в `PROJECT.md`; реестр отложенного в `STATE.md` фиксирует его как ✅ RESOLVED. Требование = верификация, а не починка с нуля.

- [ ] **TEST-02**: Остаточные падения последнего известного полного прогона (3 failed / 2 errors при 3058 passed — `test_freeze_race`, promo F821, `test_alembic_clean` и остальные) перепроверены на свежем прогоне и занесены отдельными строками реестра; допустимо финальное `deferred` с причиной `accepted-risk`

### Functional fixes (FUNC) — баги на живых данных

- [ ] **FUNC-01**: Паттерн capture-then-contract-test распространён на каждый домен `apps/admin`, где его нет (~20 из ~25): backend-capture реального JSON → фикстура → contract-тест, парсящий её НАСТОЯЩЕЙ продакшн Zod-схемой
- [ ] **FUNC-02**: Compile-time структурный гард `AssertEqual<z.infer<Schema>, GeneratedType>` добавлен по каждому домену admin, работает в существующем `tsc` шаге, без новых зависимостей
- [ ] **FUNC-03**: Schemathesis (GET-scope) прогнан против живого ASGI-приложения; расхождения «runtime backend vs его собственная OpenAPI-спека» починены либо получили диспозицию
- [ ] **FUNC-04**: Каждая FUNC-строка реестра имеет терминальную диспозицию; строки с флагом `locked_invariant_risk` починены ПЕРВЫМИ, причём parity-зеркало обновлено тем же коммитом и negative-test фикстура перезапущена как доказательство, что гейт всё ещё ловит плохой вход
- [ ] **FUNC-05**: Каждый подключённый-но-недостижимый экран либо сделан достижимым (router + nav-запись), либо явно помечен hide-for-future строкой реестра — молча недостижимых не остаётся
- [ ] **FUNC-06**: Для `apps/client` контракт-тесты (capture-фикстуры реальных ответов, без введения `zod`) покрывают денежные и auth-пути: checkout, абонемент, `client_auth`; остальные ~21 client-эндпоинт — строка `deferred:out-of-scope`

### Hygiene (HYGIENE) — код и архитектура

- [ ] **HYG-01**: Каждый TODO/FIXME/HACK/XXX маркер либо закрыт фиксом, либо превращён в строку реестра с диспозицией — ни один не остаётся молчащим в коде
- [ ] **HYG-02**: Мёртвый код удаляется только после полнорепозиторного grep по строковым литералам ПЛЮС явной проверки регистраций в composition root (`app/main.py`), ARQ-cron string-dispatch, ссылок из `alembic/versions/*`, AST-гейтов (`LOCKED_AUDIT_EVENTS` / `LOCKED_EMAIL_TEMPLATES`) и lazy-роутов; удаление по одному confidence-скору инструмента запрещено
- [ ] **HYG-03**: Находки дублирования устранены либо получили диспозицию; намеренное повторение схем по доменам зафиксировано как `accepted-risk`, а не «исправлено»
- [ ] **HYG-04**: Контракты import-linter и ESLint-границы соблюдены; отсутствующая ESLint-зона `features/x → features/y` добавлена ПОСЛЕДНЕЙ — после устранения нарушений, чтобы гейт не падал на унаследованном долге посреди milestone
- [ ] **HYG-05**: Устаревшая документация исправлена: секции стека в `CLAUDE.md` и `apps/admin/CLAUDE.md` приведены к реальности (`react@^18.3.1`, `vite@^5.4.14`, `react-router-dom@^6.28.2`; описание React 19 + Vite 6 + TanStack Router принадлежит удалённому `apps/admin-web`)
- [ ] **HYG-06**: `deptry` подключён гейтом в CI; Knip, jscpd и vulture остаются одноразовыми локальными инструментами (осознанное решение v4.1, не упущение)
- [ ] **HYG-07**: Коммиты гигиены изолированы от логических фиксов; массовое переформатирование не смешивается с правками поведения

### Locally-provable production readiness (INFRA) — параллельный трек

- [ ] **INFRA-01**: k3d-развёртывание фактически выполнено (`make up`, `make smoke`) с зафиксированным перезапускаемым доказательством, а не с отметкой «должно работать»
- [ ] **INFRA-02**: Backup/restore round-trip фактически прогнан в k3d (`make backup`, `restore-verify.sh`) с перезапускаемым доказательством; результат записан с квалификатором `(k3d-scope)`, а исходный HARD-гейт v4.0 **BAK-03 остаётся открытым и неотредактированным**
- [ ] **INFRA-03**: Резервное копирование RSA-ключа sealed-secrets на тестовое хранилище отработано; записано с `(k3d-scope)`, исходный HARD-гейт v4.0 **SEC-02 остаётся открытым и неотредактированным**
- [ ] **INFRA-04**: `trivy config` для Terraform/Helm/K8s мисконфигураций добавлен по образцу существующего `scan-images.sh`; находки получили диспозицию
- [ ] **INFRA-05**: Каждый пункт, действительно требующий железа или боевых кредов, имеет диспозицию `deferred:operator-pending`; ни один не помечен выполненным

### Milestone close (CLOSE)

- [ ] **CLOSE-01**: Механическая проверка: grep без диспозиции строк реестра даёт ноль; нет ни `open`, ни зависших `fixed+unverified`
- [ ] **CLOSE-02**: Spot-audit — выборка строк `fixed+verified` перепроверена фактическим перезапуском указанного доказательства
- [ ] **CLOSE-03**: Все существующие гейты зелёные: ruff, mypy --strict, import-linter, ESLint (+негативные фикстуры), tsc, pytest, vitest, OpenAPI/`schema.d.ts` drift
- [ ] **CLOSE-04**: Результат с нулём `deferred` строк трактуется как красный флаг и перепроверяется — при 23 известных operator-pending пунктах он недостоверен

---

## v4.2+ Requirements (deferred)

### Client PWA validation parity

- **CLI-01**: Ввести `zod` в `apps/client` и написать схемы для всех ~21 client-эндпоинта (в v4.1 покрыты только денежные и auth-пути)
- **CLI-02**: Распространить `AssertEqual` гард на client-домены

### Tooling graduation

- **TOOL-01**: Knip / jscpd / vulture в CI-гейты после чистого baseline
- **TOOL-02**: Playwright route-sweep как CI-проверка (в v4.1 — manual/`workflow_dispatch`)
- **TOOL-03**: `trivy config` как блокирующий гейт (в v4.1 — on-demand)

### Production cutover (требует железа и кредов)

- **PROD-01**: Боевой apply на реальный сервер/VM
- **PROD-02**: HARD-гейт SEC-02 — off-node custody RSA-ключа sealed-secrets на реальном железе
- **PROD-03**: HARD-гейт BAK-03 — verified restore round-trip на реальном железе
- **PROD-04**: Живой credentialed ЮKassa leg
- **PROD-05**: RU deliverability email/SMS

---

## Out of Scope

Явно исключено. Первые семь — **анти-фичи**: документированные способы сорвать сходимость quality-milestone.

| Feature | Reason |
|---------|--------|
| Целевые проценты покрытия тестами | Кампания за покрытие ≠ качество; тесты в v4.1 — инструмент доказательства фиксов, а не метрика |
| Массовое переформатирование | Уничтожает git blame и сигнал ревью, маскирует поведенческие правки |
| Спекулятивная перестройка архитектуры | Дальше восстановления соответствия import-linter — не hardening, а новый milestone |
| Апгрейды зависимостей «раз уж мы здесь» | Вносит немонотонный риск в milestone, чья цель — снизить риск. Допустим только если сам апгрейд и есть зарегистрированный фикс |
| Iterate-until-dry аудит | Не имеет стоп-условия; выбран audit-once-then-fix |
| Инлайн-фиксы во время аудит-прохода без строки реестра | Ломает единственный механизм, делающий «аудит один раз» проверяемым |
| Ручной обход дрейфа «по экрану» | Именно этот режим отказа пропустил 6+ багов расхождения и повторы FND-04 |
| Генерация Zod из `schema.d.ts` (orval / openapi-zod-client / zodios) | Не адресует фактический режим отказа (spec-vs-runtime, а не spec-vs-Zod), задевает byte-stability drift-гейт `packages/api-client` и теряет рукописные правила валидации форм под ru-локаль |
| Pact | Решает задачу координации нескольких сервисов, которой у этого монолита нет |
| Prism (mock-сервер) | Backend живой с v2.0 |
| MSW как детектор дрейфа | Моки по построению не могут обнаружить собственный дрейф — это и есть исходная причина багов v3.0/v3.1 |
| chart-testing / kuttl / tflint / Velero / policy-as-code | Решают multi-team / multi-cluster задачи, которых нет у соло-мейнтейнера с одним кластером; `kubeconform` и `restore-verify.sh` уже на месте |
| Новые бизнес-фичи, мультифилиальность, Notifications Hub, persisted-RBAC, trainer reviews | Продуктовая поверхность — не этот milestone |
| Боевое железо и продакшн-креды | D-V40-LOCAL-VALIDATE: доказуемо только локально; остальное `deferred:operator-pending` |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUD-01 | Phase 122 | Complete |
| AUD-02 | Phase 122 | Complete |
| AUD-03 | Phase 122 | Complete |
| AUD-04 | Phase 122 | Complete |
| AUD-05 | Phase 122 | Pending |
| AUD-06 | Phase 122 | Pending |
| AUD-07 | Phase 122 | Pending |
| AUD-08 | Phase 122 | Complete |
| TEST-01 | Phase 123 | Pending |
| TEST-02 | Phase 123 | Pending |
| FUNC-01 | Phase 124 | Pending |
| FUNC-02 | Phase 124 | Pending |
| FUNC-03 | Phase 124 | Pending |
| FUNC-04 | Phase 124 | Pending |
| FUNC-05 | Phase 124 | Pending |
| FUNC-06 | Phase 124 | Pending |
| HYG-01 | Phase 125 | Pending |
| HYG-02 | Phase 125 | Pending |
| HYG-03 | Phase 125 | Pending |
| HYG-04 | Phase 125 | Pending |
| HYG-05 | Phase 125 | Pending |
| HYG-06 | Phase 125 | Pending |
| HYG-07 | Phase 125 | Pending |
| INFRA-01 | Phase 126 | Pending |
| INFRA-02 | Phase 126 | Pending |
| INFRA-03 | Phase 126 | Pending |
| INFRA-04 | Phase 126 | Pending |
| INFRA-05 | Phase 126 | Pending |
| CLOSE-01 | Phase 127 | Pending |
| CLOSE-02 | Phase 127 | Pending |
| CLOSE-03 | Phase 127 | Pending |
| CLOSE-04 | Phase 127 | Pending |

**Coverage:**

- v4.1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-26*
*Last updated: 2026-07-26 after roadmap creation (v4.1 Codebase Hardening — Phases 122-127, 100% coverage)*
