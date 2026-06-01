# Phase 73: downloads-home-html - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Перенести **новую визуальную вёрстку экрана «Главная»** из свежего экспорта прототипа (`/Users/andre/Downloads/Home.html`) в боевой, подключённый к API экран `apps/client-pwa/src/screens/HomeScreen.jsx` — **только визуал**.

**В scope:**
- Внешний вид экрана «Главная» для состояния **активного абонемента** (и его тоновых вариаций active/warn/danger).
- Новые визуальные элементы из макета: шапка `HomeHeroCard` (включая виджет «загруженность зала» как статичную заглушку и `GymStatusPill` со статичными часами работы), новый вид карточки абонемента `SubCardSpot`, плитки `BookTile`/`ChatTile`, CTA «Запишись» с иллюстрацией `BookSpot`, большая кнопка QR, лента `FeedSection`.

**Вне scope (НЕ трогаем):**
- API-обвязка и логика боевого экрана: `useClientHome`/`useClientMe`/`useClientBookings`, `toSubInfo`, `deriveOnboardingSteps`, авто-редирект на онбординг.
- Состояние **«новичок без абонемента»** (`HomeNewbie`, `OnboardingStrip`, `HeroNewbie`, `FirstVisitNudge`, `QrPlaceholder`, redirect) — утверждено в фазах 999.3/999.5, остаётся нетронутым.
- Любые другие экраны (`BookScreen`, `ChatScreen`, `ProfileScreen`, sheets), общий дизайн-система/токены, контракты компонентов, бэкенд.
- Никаких новых API-эндпоинтов или изменений данных.

</domain>

<decisions>
## Implementation Decisions

### Трактовка фазы
- **D-01:** Чистый рестайл вёрстки **одного** экрана «Главная». «без изменений в интерфейсе и дизайне» = не трогаем логику, API-обвязку, контракты компонентов и другие экраны. Меняется только внешний вид Home для состояния активного абонемента.

### Состояние «новичок без абонемента»
- **D-02:** Состояние новичка (999.3/999.5) **сохраняем нетронутым**. Рестайлим только ветку активного абонемента. `HomeNewbie`, `OnboardingStrip`, `HeroNewbie`, `FirstVisitNudge`, `QrPlaceholder` и авто-редирект на `/onboarding` — без изменений.

### Виджет «загруженность зала» (HomeHeroCard)
- **D-03:** Виджет показываем, но **статичной заглушкой** — фиксированно первый уровень из макета: **«Свободно»** (зелёный, `var(--accent)`, столбики `[42,60,30,38]`).
- **D-04:** Убрать `setInterval`/`Math.random()` ротацию уровней — реального API загруженности нет, анимация смены уровней не переносится. (Декоративная пульсация точки статуса допустима.)

### Карточка абонемента (SubCardSpot)
- **D-05:** Новый вид `SubCardSpot` — **канонический** (заменяет текущий прод-дефолт `subCardStyle='eyebrow'`).
- **D-06:** Применяется ко **всем тоновым состояниям** active/warn/danger через существующую логику `toSubInfo` → `subTone`/`fillTone`/`pct`. Карточка рендерит **реальные данные** абонемента из API, только в новом оформлении.
- **D-07:** Существующий `ExpiredAlert` (баннер истёкшего абонемента) **остаётся как есть** — рестайл не отменяет его поведение.

### Состав экрана (HomeClassic) — «всё из макета»
- **D-08:** Переносим полный новый состав дефолтного `HomeClassic`: `HomeHeroCard` → `SubCardSpot` → `UpcomingCard`/CTA «Запишись» (`BookSpot`) → большая кнопка QR → плитки `BookTile`+`ChatTile` → `FeedSection`.
- **D-09:** Плитки `BookTile`/`ChatTile` заменяют текущие быстрые действия (`QuickTile`). Пустое состояние ближайшей брони → CTA «Запишись на тренировку» с `BookSpot` (как в макете).
- **D-10:** Бейджи **не хардкодим**. В макете `ChatTile badge={2}` — захардкожено; чат в боевом PWA **не подключён к реальному API**, поэтому badge чата = **без бейджа** (0/скрыт). Бейдж уведомлений = текущее прод-значение `unread = 0` (уведомления не в API), без бейджа.

### Статус зала в шапке (GymStatusPill)
- **D-11:** Показываем **статичное «Открыто до 23:00»** из `GYM_INFO` (`apps/client-pwa/src/data/gym.js`) с индикатором open/closed, как в макете. `GYM_INFO` уже используется на экране как inlined static demo data (D-71-07), бэкенд статуса зала не требуется. Тап по pill открывает `GymInfoSheet` (как сейчас).

### Claude's Discretion
- Точная техника переноса (новый под-компонент vs правка существующего `HomeClassic`) — на усмотрение planner/executor, при условии сохранения сигнатур, через которые `App.jsx` монтирует `HomeScreen` (props: `tweaks`, `onOpenQR`, `onOpenPlans`, `onOpenManage`, `onOpenReferral`, `onOpenGymInfo`, `onOpenNotifications`, `onTab`, `setTweak`).
- Сохранять ли tweaks-переключатели вариантов (`homeVariant` qr-hero/minimal, `subCardStyle` eyebrow/ring/premium) как dev-only — на усмотрение; канонический прод-вид = classic + SubCardSpot + heroStyle classic. Удаление неиспользуемых вариантов не обязательно, но и не запрещено, если не ломает Tweaks-панель.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Макет (источник нового визуала)
- `/Users/andre/Downloads/Home.html` — самодостаточный экспорт прототипа PWA. Исходники встроены в `<script id="__sources" type="application/json">`. Релевантные ключи: `src/screens/HomeScreen.jsx` (новая вёрстка — 1404 строки), `src/styles.css` (токены/анимации, напр. `pulse-soft`, `book-scene-in`, `book-float`), `src/data/gym.js` (`GYM_INFO`), `src/components/Icon.jsx`, `src/components/StatusBar.jsx`, `src/components/PullToRefresh.jsx`, `src/components/QRPattern.jsx`, `src/components/SwipeRow.jsx`.
  - Для извлечения конкретного файла: распарсить JSON из `__sources` и взять нужный ключ (см. порядок действий в RESEARCH).

### Боевой экран (цель переноса)
- `apps/client-pwa/src/screens/HomeScreen.jsx` — текущий прод-экран с API-обвязкой и состоянием новичка. **Сохранить** `toSubInfo`, `deriveOnboardingSteps`, redirect-эффект, ветку `HomeNewbie`.
- `apps/client-pwa/src/screens/HomeScreen.adapters.test.jsx`, `HomeScreen.identity.test.jsx` — существующие тесты адаптеров/идентичности; рестайл **не должен** их ломать.
- `apps/client-pwa/src/App.jsx` §`HomeRoute` (≈стр. 115) — как `HomeScreen` монтируется и какие props/обработчики передаются (контракт сохранить).
- `apps/client-pwa/src/data/gym.js` — `GYM_INFO` (часы работы, статус) для `GymStatusPill`/`HomeHeroCard`.
- `apps/client-pwa/src/data/index.js` — swap-точка mock→real (D-71-07); список того, что приходит из API vs остаётся static demo.
- `apps/client-pwa/src/styles.css` — целевые токены/классы; новые анимации из макета добавлять сюда, не в инлайн-стили без необходимости.

### Прецеденты (тот же паттерн «рестайл по прототипу»)
- `.planning/quick/260601-oan-client-pwa-newbie-home-v2-restyle/` (PLAN.md, SUMMARY.md) — рестайл newbie-Home по прототипу.
- `.planning/quick/260601-vxr-plan-activated-client-pwa-paymentsucceed/` — рестайл экрана успешной оплаты по тому же подходу (реальные данные + новый вид).
- `.planning/design-inputs/client-pwa-newbie-and-payment/` — предыдущие design-input HTML-прототипы.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HomeHeroCard`, `SubCardSpot`, `SubCardPremium`, `BookTile`, `ChatTile`, `BookSpot`, `GymStatusPill` — готовые компоненты в макетном `HomeScreen.jsx`; переносятся в боевой экран с заменой демо-источников на реальные/статичные по решениям выше.
- `toSubInfo(membership)` (прод) — адаптер API→`{daysLeft,total,until,label,tone}`; `SubCardSpot` потребляет тот же `sub`/`pct`/`subTone`/`fillTone`. Маппинг данных уже есть, нужен только новый рендер.
- `GYM_INFO` (`data/gym.js`) — статичные часы работы/статус для шапки.
- `PullToRefresh`, `StatusBar`, `Icon`, `FeedSection`, `UpcomingCard`, `TrainerCancelCard`, `ExpiredAlert` — общие компоненты, присутствуют и в проде, и в макете.

### Established Patterns
- Прод-экран = «реальные данные + новый вид»: данные тянутся хуками (`useClientHome`/`Me`/`Bookings`), демо-источники прототипа (`getSubInfo`, случайная загруженность, хардкод-бейджи) **не** переносятся.
- Tweaks-driven варианты (`tweaks.homeVariant`, `tweaks.subCardStyle`, `tweaks.heroStyle`) — dev-панель; канонический прод-путь = дефолты (classic / spot / classic). Текущий прод-дефолт `subCardStyle` = `'eyebrow'` (стр. 247) — меняется на `'spot'`.
- Бейджи/счётчики, не покрытые API, → отсутствуют (`unread = 0`, без бейджа), не хардкодятся.
- Co-located тесты (`*.test.jsx`) рядом с экранами; рестайл не должен ломать adapters/identity тесты.

### Integration Points
- `App.jsx` → `HomeScreen` props-контракт (см. canonical refs) сохраняется без изменений.
- `onTab('book')`/`onTab('chat')`, `onOpenQR`, `onOpenPlans`, `onOpenManage`, `onOpenGymInfo`, `onOpenNotifications` — обработчики переходов/sheets уже прокинуты; новые плитки/кнопки вешаются на них.

</code_context>

<specifics>
## Specific Ideas

- Канонический вид = дефолты макета: `homeVariant='classic'`, `subCardStyle='spot'` (`SubCardSpot`), `heroStyle='classic'`.
- Загруженность зафиксирована на уровне «Свободно» (зелёный) — первый уровень массива `levels` в `HomeHeroCard`, без ротации.
- Статус зала: «Открыто до 23:00» из `GYM_INFO`, с pulsing-индикатором open.
- Чат-плитка — без бейджа (чат не на реальном API).

</specifics>

<deferred>
## Deferred Ideas

- **Реальный API загруженности зала** — виджет «загруженность» сейчас статичная заглушка «Свободно»; живые данные потребуют backend-эндпоинта occupancy. Отдельная будущая фаза.
- **Реальный статус/часы зала из API** — `GymStatusPill` сейчас на статичном `GYM_INFO`; вынос в API (open/closed, часы) — отдельная фаза.
- **Бейдж непрочитанных чатов/уведомлений из API** — появится, когда чат/уведомления будут подключены к реальному backend.
- **Рестайл состояния новичка под новую шапку HomeHeroCard** — рассматривалось, но в этой фазе newbie оставлен нетронутым (D-02). Кандидат на будущую фазу при желании унифицировать шапку.
- **Альтернативные варианты вёрстки (qr-hero / minimal) и стили карточки (premium / ring)** — присутствуют в макете как tweaks-варианты; в прод уходит только canonical. Остальные — потенциал для A/B или будущих итераций.

</deferred>

---

*Phase: 73-downloads-home-html*
*Context gathered: 2026-06-02*
