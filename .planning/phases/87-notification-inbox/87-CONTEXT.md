# Phase 87: Notification Inbox - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Клиент видит in-app ленту своих уведомлений (newest-first, пагинация), управляет статусом
прочтения (одно + все), а системные события (бронь подтверждена/отменена(клиент+owner)/
перенесена, online-payment succeeded, autopay успех/провал) автоматически создают запись
в ленте затронутого клиента. Клиент регистрирует push-токен устройства (хранение под
будущий web-push; доставка отложена). Экран ленты в PWA подключён к реальным эндпоинтам
за feature-флагом.

**В scope:** заполнение `notifications` модуля (model + create-service + client router),
`in_app_notifications` + `client_push_tokens` таблицы + миграции, client read/mark/register
endpoints, inline-хуки создания уведомлений в 6 событийных обработчиках, проводка
`NotificationsSheet` к реальным данным + unread-бейдж.

**Вне scope:** реальная доставка web-push (только хранение токена), центральная event-bus
шина, admin-web UI, новые типы событий помимо 6 названных, Telegram/email канал изменений.

Requirements: INBOX-01, INBOX-02, INBOX-03, INBOX-04, INBOX-05.

</domain>

<decisions>
## Implementation Decisions

### Data Model
- Заполнить существующий пустой `app/modules/notifications/` модуль: `models.py`
  (`in_app_notifications`), `repository.py`, `service.py` (`create_notification()` —
  вызывается другими модулями), `schemas.py`, `router.py` (client read/mark/register).
- Денормализованное хранение: rendered русский `title` + `body` пишутся в момент создания
  (стабильная история, как у email-подхода). НЕ kind+payload-render-on-read.
- Idempotency/dedup: `UNIQUE(client_id, source_type, source_id, kind)` — предотвращает
  дубль-записи при webhook-ретраях (зеркалит существующие *Notification таблицы).
- Read-state: колонка `read_at: datetime | None` (single + mark-all).
- Push-токены (INBOX-04): новая таблица `client_push_tokens` по образцу `ClientPaymentMethod`
  (client_id FK, token, platform, soft-delete через `unregistered_at`, partial-unique alive).

### API Contract
- `GET /api/v1/client/notifications` — paginated newest-first, ответ включает `unreadCount`
  в meta (бейдж без отдельного запроса). Пагинация `{items,total,page,pageSize}`.
- `PATCH /api/v1/client/notifications/{id}/read` (одно) + `PATCH /api/v1/client/notifications/read-all` (все).
- `POST /api/v1/client/push-tokens` — идемпотентный upsert по токену (доставка отложена).
- Auth: `require_client()` на чтении; CSRF на PATCH/POST (RBAC-04: require_client → csrf);
  client_id из `ClientPrincipal`, никогда из body/URL (IDOR-safe).

### Event Integration (INBOX-03)
- Inline `create_notification(...)` вызовы рядом с существующим email/telegram dispatch
  в каждом service-обработчике (без event-bus — соответствует кодовой базе).
- События в scope (6): booking confirmed; booking cancelled_by_client; booking
  cancelled_by_owner; booking rescheduled; online-payment succeeded; autopay success;
  autopay failure. Каждое → kind + русский title/body.
- Anti-oracle: соблюдать D-52-08 — client-inbox записи только для client-appropriate
  событий (никаких payment_canceled-oracle утечек).
- Транзакция: insert участвует в caller-owned транзакции (атомарно со сменой состояния);
  UNIQUE-dedup покрывает webhook-replay.

### PWA Wiring (INBOX-05)
- Перевести `NotificationsSheet` из placeholder в реальный экран: убрать из D-71-09 ESLint
  zone (3 места в `eslint.config.js`) + импорт хука через `@/data` swap seam (урок Phase 86).
- Feature-флаг: за существующим tweaks/feature-flag механизмом (INBOX-05 «за feature-флагом»,
  как clubBonuses).
- Бейдж: unread из `unreadCount` ответа списка; рендер на bell entry point.
- Mark-read UX: «mark all» action + mark-single при открытии; оптимистичный апдейт с rollback.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `client_portal/router.py` — образец client-scoped paginated GET (`PageQuery`,
  `ResponseEnvelope[PaginatedData[T]]`, `envelope(page)`) + PATCH с `verify_client_csrf`
  (`PATCH /client/me` lines ~820-855).
- Существующие per-domain dedup-таблицы: `BookingNotification` (bookings/models.py),
  `PaymentNotification` (online_payments/models.py), `AutopayChargeNotification`
  (autopay_charges/models.py) — append-only, UNIQUE-dedup, Base+UUIDPkMixin+TimestampMixin.
- `ClientPaymentMethod` (payment_methods/models.py:34-71) — образец per-client таблицы
  с partial-unique-alive + soft-delete колонкой (для `client_push_tokens`).
- `core/pagination.py` (`PageQuery`, `PaginatedData` `{items,total,page,pageSize}`).
- Frontend: `LoyaltySheet.jsx` + `clientQueries.ts` (`useClientLoyaltyHistory(page)` через
  `clientRequest('get', ...)` + `clientPortalKeys`) — образец real-data sheet с пагинацией.
- `data/index.js` swap seam; `TabBar.jsx` (badge-рендер только для chat сейчас).

### Established Patterns
- Inline dispatch per-handler (нет event-bus): email через
  `integrations/email/dispatcher.py` (`enqueue_email_dispatch`, per-module
  `email_templates.py` реестры) + inline Telegram DM render в service-слое.
- Event emission points (INBOX-03 хуки):
  - bookings/service.py: create_booking (~1088), cancel_booking_for_client (~1575),
    cancel_booking (owner, ~1427), reschedule_booking_for_client (~1740) — рядом с
    `enqueue_booking_email_fallback(...)`.
  - online_payments YooKassa webhook handler (`api/v1/_internal/yookassa/router.py`) —
    payment succeeded.
  - autopay_charges/service.py — charge succeeded (~45-63) / failed (~66-81 render fns).
- D-52-08 anti-oracle (payment_canceled — owner-only, не client-facing).
- D-03/D-32-10 caller-owns-txn (service commits; repository не flush/commit).

### Integration Points
- Регистрация client router в `api/v1/router.py`.
- Migration chain: head `0059_seed_gym_info` → `0060_in_app_notifications` →
  `0061_client_push_tokens`.
- `NotificationsSheet.jsx` ← хук через `data/index.js`; `eslint.config.js` de-list (D-71-09).
- TabBar / bell entry point ← unreadCount.
- OpenAPI: новые пути попадут в openapi.json (заморозка/forward-guards — Phase 89).

</code_context>

<specifics>
## Specific Ideas

- Русские title/body шаблоны per kind, напр.: booking confirmed → «Бронь подтверждена» /
  «{дата/время}, {тренер/услуга}»; autopay failed → «Не удалось списать автоплатёж» / «...».
  Рендерятся в `create_notification` в момент события (как email-шаблоны).
- `unreadCount` считается серверно (COUNT WHERE read_at IS NULL) и кладётся в meta ответа
  списка — клиент не делает отдельный запрос для бейджа.
- push-token POST: upsert по (client_id, token) — повторная регистрация того же токена no-op.

</specifics>

<deferred>
## Deferred Ideas

- Реальная доставка web-push (Service Worker push, VAPID) — только хранение токена сейчас.
- Центральная event-bus / outbox шина (notifications/__init__.py TODO «Phase B+ outbox»).
- Новые типы событий помимо 6 названных (напр. membership expiring, loyalty accrual).
- admin-web UI для просмотра/отправки уведомлений.
- Telegram/email-канал для in-app событий (in-app лента — отдельный канал).
- Группировка/категории уведомлений, фильтры в ленте.

</deferred>
