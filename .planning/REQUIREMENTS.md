# Requirements: clubcore — v2.4 Content & Communication (Client-First)

**Defined:** 2026-06-06
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone framing:** Первый Group-B контент/коммуникационный слайс, полностью на клиентской стороне. Staff-side gate решён в пользу **owner-only write-API + сиды, без admin-web UI** (D-86-STAFF). Все client-эндпоинты под `require_client()`, IDOR-safe; staff-контракт байт-в-байт с `contract-freeze-v1.11.0`. admin-web остаётся frozen; admin-UI для этих доменов — отдельный будущий milestone.

## v1 Requirements

Requirements for this milestone (v2.4). Each maps to exactly one roadmap phase.

### Gym-info / CMS

- [ ] **GYM-01**: Клиент видит инфо о зале (адрес, часы работы, удобства, правила) в PWA через `GET /client/gym`, заменяя статичный `data/gym.js`
- [ ] **GYM-02**: Owner создаёт/обновляет содержимое gym-info через owner-only write-API (reception 403; без admin-web UI)
- [ ] **GYM-03**: Базовая запись gym-info засеяна (seed/миграция), чтобы свежее окружение рендерило реальный контент

### Notification inbox

- [ ] **INBOX-01**: Клиент видит ленту своих in-app уведомлений (newest-first, пагинация) через `GET /client/notifications`
- [ ] **INBOX-02**: Клиент помечает уведомления прочитанными (одно + все) через `PATCH /client/notifications`, и счётчик непрочитанных доступен для бейджа PWA
- [ ] **INBOX-03**: Системные события (бронь подтверждена/отменена/перенесена, checkout/платёж succeeded, autopay успех/провал) автоматически создают запись в ленте для затронутого клиента
- [ ] **INBOX-04**: Клиент регистрирует push-токен устройства через API (хранение/рельсы под будущий web-push; сама доставка отложена)
- [ ] **INBOX-05**: Экран ленты уведомлений в PWA подключён к реальным эндпоинтам за feature-флагом

### Trainer detail / bio

- [ ] **TRNR-01**: Клиент видит профиль/bio тренера (имя, фото, специализация, текст bio) через `GET /client/trainers/{id}`
- [ ] **TRNR-02**: Owner задаёт/обновляет профиль/bio тренера через owner-only write-API (reception 403; без admin-web UI)
- [ ] **TRNR-03**: Профили тренеров засеяны (seed) для baseline
- [ ] **TRNR-04**: PWA TrainerDetailSheet подключён к реальному эндпоинту (сейчас ComingSoon)

### OpenAPI Handoff

- [ ] **HND-01**: `openapi.json` + `schema.d.ts` регенерированы byte-stable со всеми новыми путями v2.4; staff-пути байт-в-байт с `contract-freeze-v1.11.0`; `_v24Checks` `AssertNonNever` forward-guards; milestone-gate зелёный

## v2 Requirements

Deferred to future release. Tracked but not in this roadmap.

### Trainer reviews

- **REVW-01**: Клиент оставляет отзыв о тренере (`POST /client/trainer-reviews`)
- **REVW-02**: Отзыв скрыт до модерации (`pending → owner-approve`)
- **REVW-03**: Owner модерирует отзывы (approve/reject)

### Push delivery

- **PUSH-01**: Реальная web-push доставка in-app уведомлений на зарегистрированные токены

### Admin-web UI

- **ADM-01**: admin-web UI для gym-info / inbox / trainer-профилей поверх уже отгруженных client-путей

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Trainer reviews (submission + moderation) | Требует staff-модерационной поверхности; убрано из v2.4 → v2 (REVW-*) |
| admin-web UI для контент-доменов | admin-web заморожен (pivot 2026-05-15); UI — отдельный будущий milestone |
| Broadcast / ручные рассылки уведомлений | Anti-feature: inbox питается только системными событиями (нет staff-композера) |
| Live web-push доставка | Только регистрация токенов в v2.4; доставка → v2 (PUSH-01) |
| Live occupancy / загруженность зала | Нет источника real-time данных; статичная подача остаётся |
| Multi-tenancy / Stripe / k8s deploy | Долгоживущие project-level исключения (см. PROJECT.md Out of Scope) |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GYM-01 | TBD | Pending |
| GYM-02 | TBD | Pending |
| GYM-03 | TBD | Pending |
| INBOX-01 | TBD | Pending |
| INBOX-02 | TBD | Pending |
| INBOX-03 | TBD | Pending |
| INBOX-04 | TBD | Pending |
| INBOX-05 | TBD | Pending |
| TRNR-01 | TBD | Pending |
| TRNR-02 | TBD | Pending |
| TRNR-03 | TBD | Pending |
| TRNR-04 | TBD | Pending |
| HND-01 | TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 13 ⚠️ (resolved at roadmap creation)

---
*Requirements defined: 2026-06-06*
*Last updated: 2026-06-06 after initial v2.4 definition*
