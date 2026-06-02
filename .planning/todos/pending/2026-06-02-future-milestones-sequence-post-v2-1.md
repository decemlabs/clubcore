---
created: 2026-06-02T15:48:13.294Z
title: Future milestones sequence (post-v2.1)
area: planning
files:
  - .planning/PROJECT.md (## Next Milestone Goals — canonical home; keep in sync)
  - .planning/milestones/v2.0-MILESTONE-AUDIT.md (deferred items / Group B inventory source)
---

## Problem

Зафиксировать все дальнейшие milestones, чтобы план «полностью завершить client-PWA + закрыть остальные направления» не потерялся. Источник — инвентаризация скрытого/незавершённого функционала client-pwa (Группы A/B/C) + долги v2.0 + общие цели проекта. v2.1 (Fill the Gaps, Группы A+C) уже открыт; ниже — что идёт ПОСЛЕ него.

**Канонический дом этого плана — PROJECT.md `## Next Milestone Goals`.** Этот todo — durable-снимок на момент 2026-06-02; при открытии каждого следующего milestone сверять и обновлять PROJECT.md, а не только этот файл.

## Solution

**Кандидатная последовательность milestone'ов после v2.1** (версии и порядок — ориентир, не контракт; production может уехать раньше):

### ⚠️ Блокирующее решение ПЕРЕД контент/коммуникационными доменами
Несколько Group-B доменов бессмысленны без owner/staff-стороны (чат — отвечать, отзывы — модерировать, gym-info/FAQ — редактировать, лента уведомлений — рассылать), а `apps/admin-web` сейчас frozen mock-reference. До планирования этих доменов выбрать:
1. расфризить/расширить admin-web (большой объём, был out-of-scope), **или**
2. owner управляет через API/сиды без UI, **или**
3. часть фич — client-read-only поверх данных, вносимых owner'ом иначе.

### v2.2 — Membership self-service depth (staff-сторона НЕ нужна)
- Card-on-file + автоплатёж: YooKassa saved-payment-methods, `GET /client/payment-method`, реальный unbind/autopay → включить флаг `linkedCard` (CardSheet, «•••• 4821»).
- Перенос брони (reschedule): `POST /client/booking/{id}/reschedule` + проводка BookingManageSheet (сейчас календарь/слоты — mock).
- Активность за неделю: агрегат минут/тренировок по дням, `GET /client/activity/weekly` → включить флаг `weeklyActivity` (Profile).

### v2.3 — Loyalty / club bonuses (платёжно-смежное, security-sensitive)
- Баланс бонусов, Gold-tier прогрессия, server-authoritative `price_override_kopecks` в чекауте, redemption на succeeded-webhook → включить флаг `clubBonuses` (Checkout). Не подрывать D-06 (скидка только server-side).

### v2.4 — Content & communication domains (НУЖНА staff-сторона — после решения выше)
- Gym-info / CMS: `gym_info` таблица/конфиг + `GET /client/gym` (адрес/часы/удобства/правила) + occupancy-источник (сейчас `data/gym.js` + статичная «Свободно»).
- In-app notification inbox: `notification_inbox` домен + регистрация push-токенов + `GET/PATCH /client/notifications`.
- Trainer reviews + detail/bio: `trainer_profile` + `trainer_review`, `GET /client/trainers/{id}`, `POST /client/trainer-reviews`, модерация (TrainerDetailSheet сейчас ComingSoon).

### v2.5 — Chat / messaging (самый тяжёлый; нужна staff-сторона)
- `messaging` домен: диалоги, сообщения, unread, ws/polling. ChatScreen сейчас ComingSoon; бейдж непрочитанного убран в v2.1/CLEAN-01.

### v2.6 — Referral program
- `referral` домен: коды, награды, история (ReferralSheet сейчас ComingSoon).

### v3.0 — Production deploy / launch (можно поднять в приоритете раньше)
- Kubernetes/Terraform деплой (INFRA-01); переименование cookie `sportzal_csrf → clubcore_csrf` (NAME-01); живой ЮKassa checkout-leg (RUN-01, OPERATOR-PENDING per D-72-06) + RU email/SMS deliverability (RUN-02); секреты/мониторинг.
- Сюда же ретроактивно: `/gsd:secure-phase 70` (3 отложенных security-пункта: proxy rate-limit bucket, QR post-decode existence, cancel idempotency).

### Прочие отложенные пункты (вне явных milestone'ов)
- Promo-code admin CRUD UI (999.4 — сейчас только засеянные коды; зависит от staff-стороны/admin-web).
- Смена телефона по OTP (новый endpoint).
- FAQ static → config-эндпоинт (косметика).

**Принцип резки:** дёшево/без новых доменов и без staff-стороны — раньше (v2.2/v2.3); контент/коммуникация — после решения про staff-сторону; production — когда появятся боевые креды/инфра (можно и раньше остального).

Full inventory + A/B/C grouping: см. историю обсуждения 2026-06-02 и `.planning/milestones/v2.0-MILESTONE-AUDIT.md`.
