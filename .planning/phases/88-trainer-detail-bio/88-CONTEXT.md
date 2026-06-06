# Phase 88: Trainer Detail / Bio - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Клиент читает полный профиль тренера (имя, фото, специализация, текст bio) в PWA через
`GET /client/trainers/{id}`; owner задаёт/обновляет bio/специализацию/фото через owner-only
write-API (reception 403, без admin-web UI); профили засеяны для baseline; PWA
`TrainerDetailSheet` подключён к реальному эндпоинту (сейчас ComingSoon).

**В scope:** расширение существующей `trainers` таблицы (bio, specialization, photo_url) +
миграция; client detail-эндпоинт в `client_portal`; расширение owner PATCH `/trainers/{id}`;
seed-миграция (backfill существующих тренеров); проводка `TrainerDetailSheet` к реальным данным.

**Вне scope:** загрузка бинарных фото (только photo_url-ссылка), reviews/rating домен
(нет бэкенда), admin-web UI, новая таблица профилей, изменение существующего
`GET /client/trainers` списка (name-only catalog остаётся).

Requirements: TRNR-01, TRNR-02, TRNR-03, TRNR-04.

</domain>

<decisions>
## Implementation Decisions

### Data Model
- Расширить существующую `trainers` таблицу новыми колонками: `bio` (Text, nullable),
  `specialization` (Text, nullable, свободный текст напр. «Силовые, функционал»),
  `photo_url` (str | None). НЕ отдельная trainer_profiles таблица.
- Фото: `photo_url` — ссылка (без бинарной загрузки); фронт падает на initials/color avatar
  если null.
- Существующая модель Trainer уже имеет full_name/phone/is_active + SoftDeleteMixin.

### API Contract
- Client read: `GET /api/v1/client/trainers/{id}` в `client_portal` модуле (сосед
  существующего `client_list_trainers`); client-safe поля только (id, name, photo_url,
  specialization, bio — БЕЗ phone/rates/is_active).
- Owner write: расширить существующий `PATCH /api/v1/trainers/{id}` (update_trainer) приёмом
  bio/specialization/photo_url (owner-only, reception 403 уже enforced).
- 404 на unknown / soft-deleted / inactive тренера для client GET.
- Auth: client GET `require_client()`; owner write owner-only (существующий guard);
  client_id из принципала (не нужен для trainer read, но эндпоинт client-gated).

### PWA Wiring (TRNR-04)
- Перевести `TrainerDetailSheet` из placeholder в реальный экран: убрать из D-71-09 ESLint
  zone (3 места в `eslint.config.js`) + импорт хука через `@/data` swap seam (урок Phase 86/87).
- Поля: name, photo (или initials/color fallback), specialization, bio; сохранить существующие
  book/checkout CTA (props `onBook`/`onCheckout`/`onClose`/`trainer` уже есть). rating/reviews
  НЕ показываем (нет бэкенда). price — из PT-package контекста, не из trainer-профиля.
- Открытие: из списка тренеров (Home/trainers) с передачей trainer id; sheet фетчит detail по id.
- Состояния: стандартный loading skeleton / error / fallback.

### Seed (TRNR-03)
- Alembic data-миграция backfill `bio`/`specialization`/`photo_url` на существующих
  засеянных trainer-строках.
- Контент: портировать specialization/bio из mock `apps/client-pwa/src/data/trainers.js`
  (Аня Соколова / Марк Левин / Лиза Орлова / Денис Кравцов / Соня Бек / Игорь Раш).
- Идемпотентность: update-if-present (set полей на существующих trainer-строках; безопасный
  повторный прогон).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Существующий `trainers` модуль (models/schemas/router/service/repository) — owner CRUD:
  `GET /trainers`, `GET /trainers/{id}`, `POST`, `PATCH /trainers/{id}` (update_trainer),
  `DELETE`. Owner-only guard уже на write-эндпоинтах.
- `Trainer` модель: `trainers/models.py:23` — Base+UUIDPkMixin+TimestampMixin+SoftDeleteMixin;
  поля full_name (Text), phone (Text|None), is_active (bool).
- Существующий client trainer catalog: `client_portal/router.py:318` `GET /client/trainers`
  (`client_list_trainers`, CPLAN-03 — name-only, no phone/is_active/rates) →
  `service.list_trainers(session)`. Образец для нового detail GET (тот же require_client +
  envelope + client-safe проекция).
- Frontend: `TrainerDetailSheet.jsx` (ComingSoon placeholder, props trainer/onClose/onBook/
  onCheckout); mock `data/trainers.js` (name/spec/exp/initials/color/bg/price/rating/reviews) —
  показывает целевой визуал. `data/index.js` swap seam.
- LoyaltySheet/GymInfoSheet/NotificationsSheet — образцы real-data sheet с loading/error.

### Established Patterns
- Owner write PATCH с partial-update схемой (Pydantic v2, extra='forbid'); reception 403.
- Client-safe проекция (отдельная response-схема без чувствительных полей) — D-20-IDOR / CPLAN.
- Alembic data-миграции (образцы: 0059 seed_gym_info Phase 86, 0060/0061 Phase 87).
- D-71-09 ESLint placeholder zone — TrainerDetailSheet всё ещё в списке (3 места:
  ignores-negation, files list, no-restricted-paths zone target). Graduate как Gym/Notifications.

### Integration Points
- Migration chain: head после Phase 87 — `0061_client_push_tokens` → `0062_trainer_profile_fields`
  (DDL) → `0063_seed_trainer_profiles` (backfill) (точные номера — на этапе планирования).
- Client detail GET регистрируется в client_portal router; owner PATCH уже зарегистрирован.
- `TrainerDetailSheet.jsx` ← хук через `data/index.js`; `eslint.config.js` de-list.
- OpenAPI: новый путь + расширенный PATCH попадут в openapi.json (заморозка — Phase 89).

</code_context>

<specifics>
## Specific Ideas

- Bio-тексты можно синтезировать из mock exp+spec (напр. «Аня Соколова — силовые и
  функциональный тренинг, 7 лет опыта. ...») при backfill-миграции.
- photo_url в seed может быть null (фронт показывает initials/color) — реальные фото-ссылки
  опциональны; owner проставит позже через PATCH.
- specialization напрямую из mock `spec` поля.

</specifics>

<deferred>
## Deferred Ideas

- Бинарная загрузка фото тренера (upload/CDN) — только photo_url-ссылка сейчас.
- Reviews / rating домен (отзывы, оценки) — нет бэкенда, вне scope.
- admin-web UI для редактирования профиля тренера (TRNR-02 — без admin-web UI по требованию).
- Изменение существующего `GET /client/trainers` списка (остаётся name-only).
- Сертификаты/достижения/расписание тренера как структурированные поля.

</deferred>
