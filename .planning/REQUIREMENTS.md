# Requirements: clubcore v2.2 — Membership self-service depth

**Defined:** 2026-06-03
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

First of the staged v2.2→v2.6 sequence to bring the client PWA up to the mockup, with production (v3.0) last. v2.2 is staff-free: three client self-service features, all under `require_client()` in `app/modules/client_portal/`, zero changes to the frozen staff contract. **Autopay scope decision (locked): UI-only** — store card token + autopay preference + ФЗ-376 consent, NO recurring charges (the `charge_expiring_autopay` ARQ cron defers to v2.3).

## v1 Requirements

### Card-on-file (PAYM)

- [x] **PAYM-01**: Клиент при чекауте может явно согласиться сохранить карту; токен YooKassa захватывается из `payment.succeeded` webhook (не из синхронного ответа `create_payment`); в `client_payment_methods` хранятся только токен + display-поля (last4/brand/expiry) — никогда PAN/CVV.
- [x] **PAYM-02**: Клиент видит привязанную карту («•••• 4821») через `GET /client/payment-method` — возвращает display-данные или 200/null если карты нет; `yookassa_method_id` токен клиенту никогда не возвращается.
- [x] **PAYM-03**: Клиент может отвязать карту через `DELETE /client/payment-method` — локальный soft-delete (`unlinked_at`); YooKassa-вызова нет (DELETE API отсутствует), IDOR-safe.
- [x] **PAYM-04**: Клиент может включить/выключить автопродление (toggle); включение требует явного согласия с раскрытием суммы + периодичности + способа отмены (ФЗ-376), фиксируется `consent_recorded_at`. Реальных списаний в v2.2 нет (preference хранится, cron — v2.3).
- [ ] **PAYM-05**: PWA-флаг `linkedCard` включён; `CardSheet` подключён к реальным endpoint'ам (вместо mock); per-booking toggle «Авто-оплата тренировок» удалён.

### Booking reschedule (RESCH)

- [x] **RESCH-01**: Клиент может перенести существующую бронь через `POST /client/booking/{id}/reschedule` — атомарный cancel+create в одной транзакции (НЕ in-place `slot_id` UPDATE), тот же тренер, повторная проверка доступности целевого слота, cancel-window cutoff на исходном слоте, IDOR-safe (404-collapse на чужой брони).
- [x] **RESCH-02**: Перенос пишет audit-событие `booking_rescheduled` (предварительно добавлено в `LOCKED_AUDIT_EVENTS`) + локализованный DM-шаблон уведомления.
- [x] **RESCH-03**: `BookingManageSheet` reschedule-вид подключён к реальным available-slots + reschedule endpoint (заменяет mock-календарь/слоты).

### Weekly activity (WACT)

- [x] **WACT-01**: `GET /client/activity/weekly` возвращает 7 объектов (Пн–Вс текущей недели, Europe/Moscow, zero-fill) с количеством тренировок за день; raw-SQL агрегат по `visits.gym_date` STORED-колонке (+ pt_sessions); `minutes` = null (отложено — нет duration-колонки).
- [ ] **WACT-02**: PWA-флаг `weeklyActivity` включён; недельные бары на `ProfileScreen` подключены к реальному endpoint'у (вместо mock).

### Handoff & verification (HND)

- [ ] **HND-01**: Byte-stable регенерация `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` со всеми новыми client-путями v2.2 под тегом `Client-Portal`; CI drift-gate зелёный; staff-контракт байт-в-байт неизменён (byte-parity guard); golden TZ-тест на week-boundary (визит 21:30 UTC → следующий московский календарный день, паттерн v1.8 VER-02).

## v2 Requirements

Deferred to future releases. Tracked but not in the v2.2 roadmap.

### Autopay execution (APAY) — v2.3

- **APAY-01**: `charge_expiring_autopay` ARQ cron (06:30 MSK) — списывает сохранённую карту за N дней до конца абонемента через `payment_method_id`; активация LOCKED на `payment.succeeded` webhook (D-06).
- **APAY-02**: Обработка сбоев autopay (declined/insufficient_funds → DM + отключение autopay; `not_allowed` operator-gate → без retry); pre-charge DM за 3 дня; детерминированный idempotency-key; `SELECT FOR UPDATE` против unbind-while-charge гонки.
- **APAY-03**: Renewal-стратегия autopay-списания (`renew_membership` с сохранением `previous_membership_id` цепочки vs `sell_membership`).

### Activity depth (WACT) — v2.3+

- **WACT-03**: Minutes-per-day на барах (требует `duration_minutes` на `pt_sessions` / join к slot-длительности).

## Out of Scope

Explicitly excluded from v2.2. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Реальные autopay-списания (cron) | UI-only scope locked; деферится в v2.3 (APAY-01..03) |
| «Авто-оплата тренировок» per-booking toggle | Anti-feature: двойное списание vs PT-package credit-модель |
| Minutes-per-day на барах активности | Нет `duration_minutes` колонки; деферится (WACT-03) |
| Autopay retry-логика / предупреждение об истечении карты | Зависит от cron (v2.3) |
| Кросс-тренерский перенос брони / лимит числа переносов | Усложнение; same-trainer достаточно для v2.2 |
| Zero-amount card binding (`payment_method.active` webhook) | Save-during-payment проще и достаточно; новый event не нужен |
| `yookassa` Python SDK / `aioyookassa` | Существующий httpx `YooKassaClient` расширяется параметрами |
| Любые изменения в `apps/admin-web` | Staff-сторона frozen; решение по контент/коммуникации — на v2.4 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PAYM-01 | Phase 79 | Complete |
| PAYM-02 | Phase 79 | Complete |
| PAYM-03 | Phase 79 | Complete |
| PAYM-04 | Phase 79 | Complete |
| PAYM-05 | Phase 81 | Pending |
| RESCH-01 | Phase 80 | Complete |
| RESCH-02 | Phase 80 | Complete |
| RESCH-03 | Phase 80 | Complete |
| WACT-01 | Phase 81 | Complete |
| WACT-02 | Phase 81 | Pending |
| HND-01 | Phase 81 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-03*
*Last updated: 2026-06-03 — traceability filled by roadmapper (Phases 79-81)*
