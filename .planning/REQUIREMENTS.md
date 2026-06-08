# Requirements: v2.6 Referral System («Приведи друга»)

Client-facing referral program. All client surfaces under `require_client()`, IDOR-safe (referrer/referee derived from the authenticated principal, never from payload). Rewards are **server-authoritative** (credited on the YooKassa `payment.succeeded` webhook, never trusted from the client) via the existing append-only `loyalty_ledger`. `apps/admin-web` stays frozen → reward amounts are owner-configurable via an owner-only API + seed (no admin UI). Staff contract stays byte-identical (drift gate green).

## v2.6 Requirements

### Referral codes & links (REFER)
- [x] **REFER-01**: Каждый клиент имеет персональный, стабильный, бессрочный реферальный код + shareable ссылку вида `…/i/<code>` (код генерируется идемпотентно при первом обращении; не меняется между запросами).
- [x] **REFER-02**: Реферальная ссылка работает как deep-link — открытие `…/i/<code>` в PWA авто-подставляет код в поток онбординга/регистрации друга.
- [x] **REFER-03**: При онбординге приглашённого друга реферал захватывается и привязывается (referrer↔referee) идемпотентно; self-referral заблокирован; на одного приглашённого начисляется не более одного реферального бонуса.

### Reward crediting (REFER)
- [x] **REFER-04**: На `payment.succeeded` ПЕРВОЙ покупки абонемента приглашённым другом обе стороны получают бонус на баланс лояльности через существующий `loyalty_ledger` (реферер — реферальный бонус; друг — приветственный), идемпотентно по `(referral_id)`/`(online_payment_id)`, переиспользуя accrual/`owner_grant` примитивы; новые LOCKED audit-события зарегистрированы до первого callsite.
- [x] **REFER-07**: Суммы реферальных бонусов (бонус рефереру, приветственный другу) конфигурируемы через owner-only API + seed (admin-web заморожен); сервер — единственный источник сумм.

### Referral screen — client PWA (REFER)
- [x] **REFER-05**: Экран «Приведи друга» выведен из ComingSoon и de-listed из D-71-09 ESLint-зоны (импорт данных через `@/data`); реализован как **пиксель-в-пиксель порт** макета `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` (промокод + ссылка + copy, share Telegram/WhatsApp/native, блок «Как это работает»), с stripped device-хромом и scoped CSS (как ChatScreen v2.5). Геймификация-тир («5 друзей → месяц») hide-for-future.
- [x] **REFER-06**: На экране отображаются реальные данные клиента: список приглашённых друзей со статусами (присоединился + начисленный бонус / перешёл-но-не-оплатил) и сумма «Уже накоплено» (фактические реферальные начисления из ledger), через `@/data`.

### API handoff (HND)
- [ ] **HND-01**: Все endpoint'ы v2.6 зафиксированы в byte-stable `openapi.json` + `schema.d.ts`; `_v26Checks` AssertNonNever покрывает новые path×method; staff-контракт байт-в-байт цел (drift gate зелёный); полный milestone gate зелёный (pytest + mypy --strict + lint-imports + Redocly + frontend vitest).

## Future Requirements (deferred)
- Геймификация реферальных вех: тир-трекер «N/5 друзей → месяц в подарок», count-up «Уже накоплено», прогресс-бар, конфетти на достижение тира (визуал есть в макете; backend тиров отложен).
- Owner-аналитика по рефералам (конверсия приглашений, топ-рефереры) — после расфриза admin-web.
- Напоминание приглашённому, который перешёл, но не оплатил («Ждём» статус → nudge).

## Out of Scope
- **Admin-web реферальный UI** — `apps/admin-web` заморожен; управление суммами только через owner-API/seed.
- **Тир-награды / месяц-за-5-друзей** — выбрано «без геймификации» (в Future); в порте тир-трекер скрыт (hide-for-future), не вырезан.
- **Реферал не-клиентами / B2B** — только client↔client.
- **Денежные выплаты рефереру** — бонус только на баланс лояльности (не вывод денег).

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REFER-01 | Phase 96 | Complete |
| REFER-02 | Phase 96 (backend) + Phase 98 (PWA) | Complete |
| REFER-03 | Phase 96 | Complete |
| REFER-04 | Phase 97 | Complete |
| REFER-05 | Phase 98 | Complete |
| REFER-06 | Phase 98 | Complete |
| REFER-07 | Phase 96 | Complete |
| HND-01 | Phase 99 | Pending |
