# Requirements: clubcore — v2.5 Chat / Messaging — Client↔Gym

**Defined:** 2026-06-06
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

Живая 1:1-переписка клиента с залом из PWA в реальном времени. Staff отвечает через Telegram-мост (admin-web остаётся frozen — chat-инбокс в админке → v2.6). Всё клиентское под `require_client()`, IDOR-safe; чат строго человеческий (системные события остаются в v2.4 notification inbox).

## v1 Requirements

Требования для milestone v2.5. Каждое маппится на фазу роадмапа.

### Messaging Core (MSG)

- [ ] **MSG-01**: Клиент видит историю своего 1:1-треда с залом (пагинированно, `{items,total,page,pageSize}`) с `unreadCount` — `GET /client/messages`
- [ ] **MSG-02**: Клиент отправляет текстовое сообщение в свой тред — `POST /client/messages`; `client_id` только из принципала (IDOR-safe, 404-collapse на не-свой тред)
- [ ] **MSG-03**: Сообщения упорядочены детерминированно (`created_at` + tiebreak) и идемпотентны на повтор отправки (`Idempotency-Key`)
- [ ] **MSG-04**: Клиент сбрасывает непрочитанные своего треда (mark-read) — `PATCH /client/messages`

### Real-time Transport (RT)

- [ ] **RT-01**: Клиент получает новые сообщения в реальном времени через WebSocket, без ручного refresh
- [ ] **RT-02**: WS-соединение аутентифицируется по client-принципалу (`aud:"client"`); подписка на чужой тред невозможна (IDOR over WS → close 1008/401)
- [ ] **RT-03**: Доставка корректна при >1 worker — fan-out через Redis pub/sub (не module-level state)
- [ ] **RT-04**: При обрыве PWA переподключается (reconnect/backoff) и догружает пропущенные сообщения через REST catch-up

### Receipts & Presence (RCPT)

- [ ] **RCPT-01**: Клиент видит статус своих сообщений «доставлено / прочитано» (✓ / ✓✓)
- [ ] **RCPT-02**: Клиент видит индикатор «печатает…» от стороны зала
- [ ] **RCPT-03**: Ответ staff помечает предшествующие клиентские сообщения прочитанными («reply-as-read») + WS read-receipt событие

### Attachments (ATT)

- [ ] **ATT-01**: Клиент прикрепляет фото к сообщению (upload)
- [ ] **ATT-02**: Загрузка валидируется по magic-bytes (allowlist JPEG/PNG/WebP) + size cap; `Content-Type` заголовку не доверяем
- [ ] **ATT-03**: Вложения отдаются через authenticated IDOR-safe endpoint с `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff` (anti-stored-XSS)

### Telegram Bridge (BRDG)

- [ ] **BRDG-01**: Клиентское сообщение (текст + фото) пересылается staff в Telegram через существующий bot-worker
- [ ] **BRDG-02**: Ответ staff (native Reply) маршрутизируется в правильный клиентский тред и доставляется клиенту по WS
- [ ] **BRDG-03**: Маршрутизация reply якорится в БД/Redis (`tg_message_id → thread/client`); защита от эхо-петли и misroute (видимо только при ≥2 активных тредах)

### PWA Wiring (PWA)

- [ ] **PWA-01**: ChatScreen подключён к реальному API + WS (убрать ComingSoon, graduate из D-71-09 placeholder-зоны — де-листинг 3 spots + импорт через `@/data`)
- [ ] **PWA-02**: Бейдж непрочитанных в PWA (таб/иконка) отражает реальный `unreadCount`
- [ ] **PWA-03**: Фото-picker при отправке + просмотр вложений (preview/full) в треде

### OpenAPI Handoff (HND)

- [ ] **HND-01**: byte-stable regen `openapi.json` + `schema.d.ts` + `AssertNonNever` forward-guards (`_v25Checks`); staff-пути байт-идентичны `contract-freeze-v1.11.0`; WS-endpoint задокументирован; полный milestone gate зелёный

## v2 Requirements

Отложено на будущие milestone'ы. Зафиксировано, но не в текущем роадмапе.

### admin-web Chat Inbox (ADMIN → v2.6)

- **ADMIN-01**: Расфриз `apps/admin-web` + первое боевое подключение к API
- **ADMIN-02**: Chat-инбокс staff в admin-панели (список тредов, ответ из UI вместо/вдобавок к Telegram)

### Messaging Depth (MSGX → future)

- **MSGX-01**: Групповые чаты / каналы / broadcast-рассылки
- **MSGX-02**: Голос/видео/файлы кроме фото
- **MSGX-03**: Реакции на сообщения, редактирование/удаление отправленного

## Out of Scope

Явно исключено. Документировано для предотвращения scope-creep.

| Feature | Reason |
|---------|--------|
| admin-web chat-инбокс | `apps/admin-web` остаётся frozen в v2.5; расфриз + боевое API-wiring — отдельный крупный milestone (v2.6); staff отвечает через Telegram-мост |
| Системные сообщения в треде | Чат строго человеческий; авто-события (брони/платежи/autopay) живут в v2.4 notification inbox, дублирование — анти-фича (нет `system_message` типа) |
| Групповые чаты / broadcast | Только 1:1 client↔зал для single-gym scale |
| Голос / видео / файлы кроме фото | Только текст + изображения в v2.5 |
| Django Channels / Socket.IO | FastAPI native WS + `redis.asyncio` pub/sub покрывают потребность без нового фреймворка |
| Push-доставка при закрытом PWA | Web-push отложен (INBOX-04 v2.4 был storage-only); WS покрывает foreground, Telegram-мост — staff-сторону |

## Traceability

Какие фазы покрывают какие требования. Заполняется при создании роадмапа.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MSG-01 | TBD | Pending |
| MSG-02 | TBD | Pending |
| MSG-03 | TBD | Pending |
| MSG-04 | TBD | Pending |
| RT-01 | TBD | Pending |
| RT-02 | TBD | Pending |
| RT-03 | TBD | Pending |
| RT-04 | TBD | Pending |
| RCPT-01 | TBD | Pending |
| RCPT-02 | TBD | Pending |
| RCPT-03 | TBD | Pending |
| ATT-01 | TBD | Pending |
| ATT-02 | TBD | Pending |
| ATT-03 | TBD | Pending |
| BRDG-01 | TBD | Pending |
| BRDG-02 | TBD | Pending |
| BRDG-03 | TBD | Pending |
| PWA-01 | TBD | Pending |
| PWA-02 | TBD | Pending |
| PWA-03 | TBD | Pending |
| HND-01 | TBD | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 0 (роадмап ещё не создан)
- Unmapped: 21 ⚠️

---
*Requirements defined: 2026-06-06*
*Last updated: 2026-06-06 after initial definition (v2.5 milestone open)*
