# Requirements: clubcore — v2.0 Frontend Integration — Client PWA

**Defined:** 2026-05-29
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

> First full-stack milestone. v1.11 froze the **staff** OpenAPI contract; v2.0 builds a NEW **client-facing** surface (auth + client-scoped API over existing domains) and wires `apps/client-pwa` to it. Staff contract + frozen `apps/admin-web` must NOT be touched. See `.planning/research/SUMMARY.md`.

## Milestone v2.0 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Client Authentication (phone + OTP)

- [x] **CAUTH-01**: Клиент входит в PWA по номеру телефона + одноразовый код через Telegram OTP (переиспользует существующую OTP-инфраструктуру)
- [ ] **CAUTH-02**: Запрос OTP для неизвестного / дублирующегося / soft-deleted телефона возвращает ответ, неотличимый от известного (anti-oracle, `_constant_time_floor`)
- [ ] **CAUTH-03**: Номер телефона нормализуется и валидируется в E.164 при запросе OTP
- [x] **CAUTH-04**: Клиентская сессия (cookie `cc_client_access` + refresh-rotation семейство) персистит между перезапусками браузера; refresh и logout работают
- [ ] **CAUTH-05**: `GET /api/v1/client/me` возвращает профиль клиента; `PATCH /api/v1/client/me` позволяет добавить/изменить email
- [ ] **CAUTH-06**: OTP-запросы ограничены rate-limit'ом (per-IP + per-phone cooldown + дневной cap) и защищены от перебора кода

### Client RBAC + Data Isolation

- [x] **CISO-01**: Отдельный `ClientPrincipal` / `require_client()` с JWT-claim `aud:"client"`; `Role.CLIENT` НЕ добавляется в `permissions.py` (staff byte-parity с frozen admin-web сохраняется)
- [x] **CISO-02**: Staff-токен получает 401 на любом `/api/v1/client/*`; клиентский токен получает 401 на любом staff-эндпоинте (two-principal isolation тест)
- [x] **CISO-03**: Каждый client-scoped эндпоинт фильтрует по `client_id` владельца сессии; get-by-id выполняет `assert_owns()` → 404-collapse при чужом ресурсе (anti-oracle)
- [ ] **CISO-04**: Параметризованный cross-client enumeration (IDOR) тест покрывает все client-owned типы ресурсов и зелёный
- [x] **CISO-05**: Клиентские cookies (`cc_client_*`, `Path=/api/v1/client`) изолированы от staff (`cc_*`) — нет взаимной перезаписи сессий на одном origin

### My Membership / Home

- [ ] **CHOME-01**: Клиент видит свой активный абонемент (план, дни до окончания, статус заморозки)
- [ ] **CHOME-02**: Клиент видит свою ближайшую бронь на главном экране
- [ ] **CHOME-03**: Клиент видит индикатор «скоро истекает» по своему абонементу

### My Bookings + Self-Booking

- [ ] **CBOOK-01**: Клиент видит свои предстоящие и прошедшие брони
- [ ] **CBOOK-02**: Клиент видит доступные слоты тренеров для записи
- [ ] **CBOOK-03**: Клиент бронирует слот к тренеру, используя свой активный PT-пакет (idempotency-keyed, race-safe через существующий partial-UNIQUE)
- [ ] **CBOOK-04**: Клиент без активного PT-пакета не может записаться; ответ направляет в Plans/Checkout (`Booking.pt_package_id` NOT NULL)
- [ ] **CBOOK-05**: Клиент отменяет свою бронь в рамках политики окна отмены (через существующий booking FSM)

### QR Self Check-In

- [ ] **CCHK-01**: Клиент получает короткоживущий подписанный QR-токен (≈60s TTL, signed JWT — не статический UUID)
- [ ] **CCHK-02**: Чек-ин по QR создаёт визит через существующий anti-fraud-путь; сохраняется 1/день (`gym_date`) + требование активного абонемента; `visits.channel` расширен на `'client_qr'` (Alembic)
- [ ] **CCHK-03**: QR нельзя реплеить и нельзя зачекинить другого клиента

### Client Checkout (ЮKassa)

- [ ] **CPAY-01**: Клиент инициирует покупку или продление абонемента через ЮKassa
- [ ] **CPAY-02**: Клиент покупает PT-пакет через ЮKassa
- [ ] **CPAY-03**: Цена читается на сервере (клиенту не доверяем); активация ТОЛЬКО по существующему webhook `payment.succeeded`; redirect-back показывает только anti-oracle «ожидаем подтверждение»
- [ ] **CPAY-04**: Email клиента обязателен для онлайн-оплаты (54-ФЗ фискальный чек) — 422 `client_email_required_for_online_payment` при отсутствии
- [ ] **CPAY-05**: Клиентский checkout идемпотентен (no double-charge при повторной отправке)

### History

- [ ] **CHIST-01**: Клиент видит историю своих визитов
- [ ] **CHIST-02**: Клиент видит историю своих тренировок (PT-sessions, ownership через `pt_packages.client_id`)
- [ ] **CHIST-03**: Клиент видит историю своих покупок (payments, включая возвраты)

### Catalogs (client read)

- [ ] **CPLAN-01**: Клиент видит каталог абонементов (membership plans) для покупки
- [ ] **CPLAN-02**: Клиент видит каталог PT-пакетов для покупки
- [ ] **CPLAN-03**: Клиент видит каталог тренеров (имя/специализация из существующего trainers-каталога; рейтинги/отзывы — out of scope, остаются mock)

### PWA Stack Alignment + Wiring

- [ ] **PWA-01**: `client-pwa` входит в pnpm workspace (`bun.lock` удалён); единый `pnpm install` + CI
- [ ] **PWA-02**: `client-pwa` переведён на TypeScript (allowJs ramp, file-by-file); подключён общий ESLint/Prettier/import-linter
- [ ] **PWA-03**: `client-pwa` переиспользует `@clubcore/api-client` (typed fetcher + `schema.d.ts`) через тонкий `clientFetcher.ts` (свои cookie-имена + refresh-URL); **react-router v6 сохранён** (без миграции на TanStack)
- [ ] **PWA-04**: Vite 5→6 выровнен; PWA собирается и проходит typecheck + lint + test
- [ ] **PWA-05**: Экраны Home / Profile / Book / Plans / Checkout / QR работают на реальном backend через клиентский API
- [ ] **PWA-06**: Net-new экраны (Chat, Referral, отзывы тренеров, лента уведомлений, gym-info) остаются на mock-данных / плейсхолдере «в разработке» — без backend-вызовов
- [ ] **PWA-07**: PWA installable (manifest + SW shell для install-prompt), но service-worker НИКОГДА не кеширует `/api/*` запросы (нет stale authed data)

### OpenAPI Handoff + Contract Preservation

- [ ] **HND-01**: Клиентские пути добавлены в `openapi.json` под тегом `Client-Portal` с префиксом operationId `client_`; staff-пути byte-identical к baseline `contract-freeze-v1.11.0` (drift gate зелёный, diff additions-only)
- [ ] **HND-02**: `schema.d.ts` regen byte-stable; новый `_v20Checks` `AssertNonNever` блок покрывает клиентские пути; staff `_v1xChecks` блоки не тронуты
- [ ] **HND-03**: CI-гейты для `client-pwa` (typecheck / lint / test) добавлены в workflow

### E2E Verification Gate

- [ ] **VER-01**: Live `docker compose up` + PWA: сквозной клиентский флоу (phone-OTP login → home → book slot → checkout → QR check-in → history) проходит end-to-end
- [ ] **VER-02**: IDOR / anti-oracle / two-principal автотесты зелёные; межклиентский доступ невозможен
- [ ] **VER-03**: Drift gate подтверждает staff-контракт byte-identical; ни один staff-эндпоинт не сломан
- [ ] **VER-04**: Runbook v2.0 авторизован (клиентские флоу + auth); live-walkthrough служит milestone gate (per v1.6/v1.9 прецедент)

## Future Requirements

Deferred to a future release. Tracked but not in this roadmap.

### SMS OTP channel

- **SMS-01**: Клиент может получить OTP по SMS (SMS Aero / SMSC.ru / МТС Exolve — Twilio заблокирован в РФ), как fallback к Telegram-каналу

### Net-new client domains (future milestone)

- **CHAT-01**: Переписка клиент ↔ админ/тренер (требует домена сообщений + staff-стороны)
- **REF-01**: Реферальная программа (коды, начисления, статусы)
- **REV-01**: Рейтинги и отзывы клиентов на тренеров
- **NINBOX-01**: Client-readable лента уведомлений в приложении
- **GINFO-01**: Gym-info контент (адрес/часы/удобства/фото/персонал) из backend, а не хардкод

### PWA offline-first

- **OFFL-01**: Offline-first кеширование клиентских данных (мои брони/абонемент видны без сети)

## Out of Scope

Explicitly excluded for v2.0. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Chat / messaging domain | Нет домена сообщений; требует staff-стороны (admin-web заморожен) — net-new, отложено |
| Referral program | Net-new домен — отложено |
| Trainer reviews/ratings | trainers — только каталог; net-new домен — отложено (экран TrainerDetail остаётся mock) |
| In-app notification inbox | Уведомления остаются push-only (Telegram/email); client-readable лента — net-new, отложено |
| Gym-info from backend | Остаётся захардкоженным контентом в PWA |
| SMS OTP provider | v2.0 = Telegram-OTP-only; SMS-канал отложен (стоимость + abuse-поверхность) → Future SMS-01 |
| PWA offline-first / API caching | Installable PWA да, но API не кешируется; offline-first → Future OFFL-01 |
| admin-web client-domain wiring | admin-web остаётся frozen mock-reference; вне скоупа |
| `Role.CLIENT` в `permissions.py` | Сломал бы staff byte-parity с frozen admin-web; используем отдельный `ClientPrincipal` |
| Kubernetes / Terraform / production deploy | Отдельный milestone после v2.0 |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAUTH-01 | Phase 68 | Complete |
| CAUTH-02 | Phase 68 | Pending |
| CAUTH-03 | Phase 68 | Pending |
| CAUTH-04 | Phase 68 | Complete |
| CAUTH-05 | Phase 68 | Pending |
| CAUTH-06 | Phase 68 | Pending |
| CISO-01 | Phase 68 | Complete |
| CISO-02 | Phase 68 | Complete |
| CISO-03 | Phase 68 | Complete |
| CISO-04 | Phase 68 | Pending |
| CISO-05 | Phase 68 | Complete |
| CHOME-01 | Phase 69 | Pending |
| CHOME-02 | Phase 69 | Pending |
| CHOME-03 | Phase 69 | Pending |
| CHIST-01 | Phase 69 | Pending |
| CHIST-02 | Phase 69 | Pending |
| CHIST-03 | Phase 69 | Pending |
| CPLAN-01 | Phase 69 | Pending |
| CPLAN-02 | Phase 69 | Pending |
| CPLAN-03 | Phase 69 | Pending |
| PWA-01 | Phase 69 | Pending |
| PWA-02 | Phase 69 | Pending |
| PWA-03 | Phase 69 | Pending |
| PWA-04 | Phase 69 | Pending |
| PWA-06 | Phase 69 | Pending |
| PWA-07 | Phase 69 | Pending |
| CBOOK-01 | Phase 70 | Pending |
| CBOOK-02 | Phase 70 | Pending |
| CBOOK-03 | Phase 70 | Pending |
| CBOOK-04 | Phase 70 | Pending |
| CBOOK-05 | Phase 70 | Pending |
| CCHK-01 | Phase 70 | Pending |
| CCHK-02 | Phase 70 | Pending |
| CCHK-03 | Phase 70 | Pending |
| CPAY-01 | Phase 71 | Pending |
| CPAY-02 | Phase 71 | Pending |
| CPAY-03 | Phase 71 | Pending |
| CPAY-04 | Phase 71 | Pending |
| CPAY-05 | Phase 71 | Pending |
| PWA-05 | Phase 71 | Pending |
| HND-01 | Phase 72 | Pending |
| HND-02 | Phase 72 | Pending |
| HND-03 | Phase 72 | Pending |
| VER-01 | Phase 72 | Pending |
| VER-02 | Phase 72 | Pending |
| VER-03 | Phase 72 | Pending |
| VER-04 | Phase 72 | Pending |

**Coverage:**
- v2.0 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0

---
*Requirements defined: 2026-05-29*
*Last updated: 2026-05-29 — traceability filled by roadmapper (v2.0 roadmap created)*
