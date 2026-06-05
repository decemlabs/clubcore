# Requirements: clubcore — v2.3 Loyalty / Club Bonuses + Real Autopay

**Defined:** 2026-06-05
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## v1 Requirements

Requirements for this milestone. Each maps to a roadmap phase. All client-facing surface lives under `require_client()`; the frozen `apps/admin-web` staff contract is byte-identical (drift gate green).

### Bonus Balance & History (LOYL)

- [ ] **LOYL-01**: Клиент видит текущий бонусный баланс через `GET /client/loyalty/balance`
- [ ] **LOYL-02**: Клиент видит историю бонусов (начисления + списания) с датой, типом и суммой
- [x] **LOYL-03**: Баланс выводится из append-only ledger (integer units; без деструктивных UPDATE — баланс = свёртка строк)

### Bonus Accrual (ACCR)

- [ ] **ACCR-01**: Новый клиент автоматически получает приветственный бонус (one-time, идемпотентно по событию онбординга/регистрации — без повторного начисления)
- [ ] **ACCR-02**: Owner начисляет бонус клиенту вручную через owner-only backend API (покрывает акционные + реферальные гранты; admin-web UI НЕ строится — прецедент: засеянные промокоды)
- [x] **ACCR-03**: Каждое начисление пишется как аудируемое ledger-событие (новый LOCKED audit event, зарегистрирован ДО любого callsite per INFRA-15)

### Bonus Redemption (REDM)

- [ ] **REDM-01**: Клиент списывает бонусы в чекауте для уменьшения суммы к оплате; сервер авторитетно пересчитывает `discount_kopecks` (клиент не задаёт размер скидки) — D-06 не подрывается (скидка только server-side)
- [ ] **REDM-02**: Списание бонусов записывается атомарно на `payment.succeeded` webhook, идемпотентно по `(online_payment_id)` (нет списания при неоплате/отмене; образец `promo_codes`)
- [ ] **REDM-03**: PWA `CheckoutSheet` показывает реальный баланс + контрол списания за флагом `clubBonuses` ON (mock `BONUS_PLACEHOLDER = { balance: 1080, toGold: 220 }` удалён)

### Real Autopay Charge (APAY)

> Закрывает реальный recurring-charge leg, отложенный из v2.2 (карта-на-файле + autopay-флаг + consent уже есть; реального списания ещё нет).

- [ ] **APAY-01**: Cron `charge_expiring_autopay` списывает с сохранённой карты off-session для абонементов, истекающих в окне, у которых `autopay_enabled=true` + записан `consent_recorded_at`
- [ ] **APAY-02**: YooKassa-адаптер умеет off-session charge по сохранённому `payment_method_id`; списание пишется в charge-ledger (дисциплина v1.4 `payments`); активация продления locked на `payment.succeeded` webhook
- [ ] **APAY-03**: Автосписание идемпотентно (нет двойного charge при повторных тиках/рестартах контейнера) и пропускает неподходящих (нет consent / autopay off / нет активной карты / уже продлён)
- [ ] **APAY-04**: Исход автосписания (успех/ошибка) аудируется + клиент уведомляется (Telegram/email mirror) по дисциплине cross-channel notifications (идемпотентность через `channel` discriminator)

### OpenAPI Handoff (HND)

- [ ] **HND-01**: `openapi.json` + `schema.d.ts` byte-stable regen со всеми новыми loyalty/autopay client-путями + `AssertNonNever` forward-guards (`_v23Checks`); staff-пути байт-идентичны `contract-freeze-v1.11.0` (drift gate зелёный)

## v2 Requirements

Deferred to future milestones. Tracked but not in this roadmap.

### Loyalty tiers (TIER) → future

- **TIER-01**: Gold-tier прогрессия (поля `tier` + `member_since_at` в `clients`; UI `tenureBadge`)
- **TIER-02**: Tenure-бейдж «PREMIUM · N ЛЕТ» + стат «N недель» (флаги `tenureBadge`/`weeksStat`)

### Referral program (REF) → v2.6

- **REF-01**: Реферальные коды (генерация + ввод)
- **REF-02**: Автоматическое реферальное начисление обоим на первой покупке приглашённого
- **REF-03**: История рефералов + награды (ReferralSheet)

## Out of Scope

Explicitly excluded for v2.3. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Gold-tier / tenure-бейдж | Отложено пользователем; флаги `tenureBadge`/`weeksStat` остаются OFF, поля `tier`/`member_since_at` не добавляем (→ future TIER) |
| Полная реферальная программа (коды/история/автонаграды) | Отдельный milestone v2.6; в v2.3 реферальный бонус = ручной owner-грант через ACCR-02 |
| Cashback % с покупок | Модель начисления не выбрана (выбраны приветственный/акционный/ручной) |
| Начисление бонусов за посещения | Не выбрано пользователем |
| admin-web UI для бонусов | `apps/admin-web` frozen; owner-грант через backend API (ACCR-02) |
| Списание бонусов при оплате наличными (cash) | v2.3 redemption завязан на ЮKassa webhook (REDM-02); cash-путь вне скоупа |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOYL-01 | Phase 82 | Pending |
| LOYL-02 | Phase 82 | Pending |
| LOYL-03 | Phase 82 | Complete |
| ACCR-01 | Phase 82 | Pending |
| ACCR-02 | Phase 82 | Pending |
| ACCR-03 | Phase 82 | Complete |
| REDM-01 | Phase 83 | Pending |
| REDM-02 | Phase 83 | Pending |
| REDM-03 | Phase 83 | Pending |
| APAY-01 | Phase 84 | Pending |
| APAY-02 | Phase 84 | Pending |
| APAY-03 | Phase 84 | Pending |
| APAY-04 | Phase 84 | Pending |
| HND-01 | Phase 85 | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14 ✓ (Phase 82: LOYL-01..03 + ACCR-01..03; Phase 83: REDM-01..03; Phase 84: APAY-01..04; Phase 85: HND-01)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-05*
*Last updated: 2026-06-05 after v2.3 roadmap creation (Phases 82-85, 14/14 mapped)*
