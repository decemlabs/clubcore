# Phase 86: Gym-Info / CMS - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Клиент видит актуальную информацию о зале (адрес, часы работы, удобства, правила, контакты)
из базы данных вместо захардкоженного `apps/client-pwa/src/data/gym.js`. Owner управляет
содержимым через owner-only write-API (reception → 403). Базовая запись засеяна миграцией,
чтобы свежее окружение рендерило реальный контент без ручного вмешательства.

**В scope:** новый backend `gym` модуль (модель + schemas + router + service + repository),
client read endpoint, owner write endpoint, seed-миграция, проводка `GymInfoSheet` к реальным
данным через swap seam.

**Вне scope:** multi-gym, загрузка фото/бинарей, computed-поля (open-now/staffToday),
admin-web UI для редактирования, миграция прочих ссылок на `GYM_INFO` (Home chip и т.п.).

Requirements: GYM-01, GYM-02, GYM-03.

</domain>

<decisions>
## Implementation Decisions

### Data Model
- Singleton-строка (один зал — per CLAUDE.md «один зал»), не multi-gym таблица.
- Скалярные колонки для name/tagline/address/city/metro/phone/email; JSONB-колонки для
  списочных структур (hours, amenities, rules, social).
- Декоративные фото (bg/icon/tag) НЕ хранятся в БД — остаются frontend-only стилизацией.
- Computed-поля (open-now status, todayIdx, staffToday) исключены из CMS; деривируются
  на клиенте. CMS хранит только редактируемый контент.

### API Contract
- Client read: `GET /api/v1/client/gym` (следует конвенции `/client/*`).
- Owner write: `PUT /api/v1/gym` — full-document upsert, owner-only.
- Новый `gym` модуль (models/schemas/router/service/repository) хостит и client GET, и owner PUT.
- Auth: write owner-only (reception → 403); client GET через `require_client()`.

### PWA Wiring
- `GymInfoSheet` (сейчас `ComingSoon` placeholder) проводится к реальным данным через
  `data/index.js` swap seam.
- Поля вне БД: декоративные фото — статика на фронте; бейдж открыто/закрыто деривируется
  на клиенте из hours; social рендерится только если присутствует.
- Loading/error: стандартный query skeleton + error fallback, как в других sheets.
- В этой фазе мигрируется только `GymInfoSheet`; прочие ссылки на `GYM_INFO` не трогаем.

### Seed Strategy
- Alembic data-миграция вставляет baseline singleton (выполняет GYM-03).
- Контент baseline портируется из текущих значений `gym.js` (пример «Тверская»).
- Insert-if-absent — повторный прогон не перезатирает правки owner.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Backend module pattern: `apps/backend/app/modules/<domain>/` с
  `models.py` / `schemas.py` / `router.py` / `service.py` / `repository.py`
  (образцы: `trainers`, `client_portal`, `loyalty`, `promo_codes`).
- `client_portal` модуль — образец client-scoped read endpoints и `require_client()` auth.
- Owner role-guard (reception 403) — существующий паттерн в owner-only роутерах.
- Frontend swap seam: `apps/client-pwa/src/data/index.js` агрегирует data-источники;
  `GymInfoSheet.jsx` сейчас рендерит `<ComingSoon title="Информация о зале" />`.

### Established Patterns
- Async SQLAlchemy 2.0 + Alembic async; Pydantic v2 schemas; structlog.
- Data-миграции через Alembic (образцы: 0046/0047 promo_codes, 0050/0051 v2.1 поля).
- Frontend data shape для gym в `apps/client-pwa/src/data/gym.js` (`GYM_INFO`).

### Integration Points
- Регистрация роутера `gym` в backend app router.
- `GymInfoSheet.jsx` ← данные через `data/index.js` swap seam.
- OpenAPI: новый путь попадёт в openapi.json (заморозка/forward-guards — Phase 89).

</code_context>

<specifics>
## Specific Ideas

- Baseline seed дублирует текущий пример `gym.js`: «Мой зал · Тверская», адрес «Тверская, 18,
  3 этаж», часы Пн–Вс, amenities (parking/wifi/shower/locker/sauna/towel/water/kids),
  5 правил, social (tg/ig).
- Бейдж «Сейчас открыто / до 23:00» — деривируется на клиенте из hours + текущего дня/времени
  (Europe/Moscow), не хранится в БД.

</specifics>

<deferred>
## Deferred Ideas

- Multi-gym (несколько залов) — отдельная фаза при необходимости.
- Загрузка реальных фото зала (binary/CDN) — вне scope.
- admin-web UI для редактирования gym-info (GYM-02 — без admin-web UI по требованию).
- Миграция прочих фронтовых ссылок на `GYM_INFO` (Home address chip и т.п.) на API.
- Computed staffToday (админ смены / число тренеров / классов сегодня).

</deferred>
