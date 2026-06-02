# Phase 74: Обновить экраны «Профиль» и «Настройки» по новым макетам - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Рестайл клиентского PWA (`apps/client-pwa`): экран **«Профиль»** (`ProfileScreen.jsx`) приводится к макету `Profile.html`, а **«Настройки»** выделяются в **отдельный экран** по макету `Settings.html`. Чисто фронтовая фаза — новых backend-эндпоинтов не добавляем. Элементы макета, не обеспеченные текущим API, либо показываем только в подкреплённой части, либо строим, но прячем за code-флагом (`BUILT, HIDDEN`) до появления бэкенда.

**В scope:**
- Новый экран `SettingsScreen` + маршрут `/settings`; шестерёнка в карточке профиля → переход; кнопка «назад» → `/profile`; TabBar скрыт на `/settings`.
- Перенос/удаление 4-й вкладки «Настройки» из `ProfileScreen` (остаются 3 вкладки: Визиты / Тренировки / Покупки).
- Membership-hero в стиле «pass» (контраст-флип тема), stat-полоска, quick-tiles, табы истории — по макету `Profile.html`, с live-bind к реальным данным.

**НЕ в scope (см. Deferred):**
- Любые новые backend-эндпоинты: стаж/«с нами N лет», цена membership в `/client/membership`, флаг автопродления, карта-на-файле, серверные настройки уведомлений, дневные минуты/типы тренировок.
</domain>

<decisions>
## Implementation Decisions

### Структура: Настройки как отдельный экран
- **D-74-01:** «Настройки» выделяются в отдельный экран `SettingsScreen` + защищённый маршрут `/settings` (под `RequireAuth`, **без** TabBar — добавить `/settings` в `hideTabBar`-условие в `App.jsx:226`). Шестерёнка в карточке профиля → `navigate('/settings')`; кнопка «назад» в шапке → `/profile` (или `history.back()` с фолбэком на `/profile`). 4-я вкладка «Настройки» из `ProfileScreen` **удаляется** — табы истории сокращаются до 3 (Визиты / Тренировки / Покупки). Содержимое текущего `SettingsList` (тема, уведомления, аккаунт, выход, версия) переезжает в `SettingsScreen`.

### Карточка «Активность за неделю»
- **D-74-02:** Карточка строится по макету (`Profile.html`: бары по дням, цель/стрик недели), но **гейтится code-флагом и скрыта по умолчанию** — `BUILT, HIDDEN`. Причина: в API нет дневных минут, типа тренировки и даже длительности визитов. Флаг живёт в module-level const (см. D-74-05). Включится, когда появится backend с workout-минутами/типами.

### Membership-hero: только подкреплённые поля
- **D-74-03:** Hero рисуется в стиле «pass» (контраст-флип, как в макете), но показываются **только поля из API**:
  - дни до конца (`daysUntilEnd`), прогресс-бар elapsed/total (из `startDate`/`endDate` — уже считается в `ProfileScreen.toSubInfo`/`subTotalDays`), «пройдено N дней» = `total − daysLeft`, дата окончания (`endDate`), название тарифа (`planNameSnapshot`).
  - Блок «**Стоимость 42 000 ₽/год** + **Продление: Автоматически**» **НЕ показываем** (в `/client/membership` нет ни цены, ни флага автопродления). Не тянем цену из плана (хрупко, нет прямой связи id↔snapshot).
  - Кнопки «Заморозить» (для активного, `window.__openSubManage?.('freeze')`) и «Сменить тариф/Продлить» (`onOpenPlans`) — **сохраняются** (уже подключены).

### Заглушки без бэкенда
- **D-74-04:** Неподкреплённые элементы:
  - Бейдж «PREMIUM · N ЛЕТ» (тариф-тир и стаж) — **за флагом, скрыт** (нет понятия tier и tenure в API).
  - Stat-полоска: третий стат «N недель (с нами)» — **за флагом, скрыт**. Остаются 2 подкреплённых стата: **визиты** (`useClientVisitHistory().total`) и **тренировки** (`useClientPtHistory().total`). Count-up по макету разрешён.
  - Строка «Привязанная карта •••• 4821» в Настройках — **за флагом, скрыта** (нет card-on-file).
  - **Тумблеры уведомлений — ИСКЛЮЧЕНИЕ из флага:** раздел «Уведомления» **виден**, тумблеры работают **локально** (persist в localStorage — переиспользовать существующий локальный паттерн / по аналогии с `myzal_notif` из макета, но через клиентский стор/localStorage PWA), на сервер ничего не шлют. Это сохраняет соответствие макету `Settings.html` без вранья о backend-доставке.

### Флаговый механизм (canonical)
- **D-74-05:** «За флагом» = module-level const по образцу `CheckoutSheet.jsx:32-48` (`CHECKOUT_FEATURE_FLAGS`): объект `PROFILE_FEATURE_FLAGS = { weeklyActivity: false, tenureBadge: false, weeksStat: false, linkedCard: false }` с комментарием-блоком `BUILT, HIDDEN`, JSX гейтится `PROFILE_FEATURE_FLAGS.x && (...)`. **Не** dev-panel tweak (per 999.3: «No dev-panel preview toggle — purely data-driven»). Флипается в коде, когда появится соответствующий бэкенд.

### Claude's Discretion
- Точное имя/расположение флаг-const (`ProfileScreen.jsx` верх модуля vs общий `features.js`) — на усмотрение планнера; держаться образца `CheckoutSheet`.
- Способ персиста локальных тумблеров уведомлений (отдельный localStorage-ключ vs существующий механизм) — на усмотрение, лишь бы переживало перезагрузку и не маскировалось под server-prefs.
- Поведение «назад» на `/settings` (history.back vs прямой `/profile`) — выбрать надёжный фолбэк.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Макеты (источник дизайна — transient, из Downloads)
- `.planning/design-inputs/client-pwa-profile-settings/Profile.html` — макет экрана «Профиль»: identity-карточка + шестерёнка, membership-hero «pass» (контраст-флип), stat-полоска (count-up), карточка «Активность за неделю», quick-tiles (Приведи друга / О зале), табы Визиты/Тренировки/Покупки, нижний TabBar.
- `.planning/design-inputs/client-pwa-profile-settings/Settings.html` — макет отдельного экрана «Настройки»: шапка с «назад», identity-строка, раздел «Внешний вид» (тема seg), «Уведомления» (4 тумблера), «Аккаунт» (Тариф / Карта / Личные данные / Помощь и FAQ), кнопка «Выйти», версия.

### Образец флагового скаффолдинга (обязательно к соблюдению)
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` §32-48 — канонический паттерн `…FEATURE_FLAGS` (`BUILT, HIDDEN`, `flag && (...)`). Воспроизвести 1:1 для D-74-02/04/05.

### Текущая реализация (что рестайлим)
- `apps/client-pwa/src/screens/ProfileScreen.jsx` — текущий профиль: `toSubInfo`/`subTotalDays` (membership-адаптер, WR-03 — переиспользовать), `VisitsList`/`TrainingsList`/`PurchasesList`/`SettingsList`/`SettingRow`/`NavRow`, вкладка `settings` (удаляется per D-74-01).
- `apps/client-pwa/src/App.jsx` §157-176 (`ProfileRoute`), §226 (`hideTabBar`), §242-246 (routes) — точка добавления `/settings`.
- `apps/client-pwa/src/lib/clientQueries.ts` — формы данных: `ClientMembershipData` (нет цены/автопродления), `ClientMeData` (нет стажа/tier), history-хуки (visits без длительности).
- `apps/client-pwa/src/context/TweaksContext.jsx` — тема через `data-theme` (НЕ `myzal_theme` из макета); `useClientHome`/`useClientMe` уже используются профилем.
- `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — `PersonalDataSheet`/`CardSheet`/`FAQSheet` (переиспользуются как навигация из Настроек).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `toSubInfo()` / `subTotalDays()` (`ProfileScreen.jsx:18-46`) — готовый membership→render адаптер с честным расчётом прогресса (WR-03). Переиспользовать в hero без изменений.
- `useClientVisitHistory` / `useClientPtHistory` / `useClientPaymentHistory` / `useClientHome` / `useClientMe` — все нужные read-хуки уже есть; stat-полоска берёт `.total` визитов и тренировок.
- `Avatar`, `Icon`, `StatusBar`, `EmptyState`, `LoadError`, `seg`/`toggle`/`card`/`press` CSS-классы — уже в проекте, использовать.
- `CHECKOUT_FEATURE_FLAGS` (`CheckoutSheet.jsx`) — шаблон флаг-объекта.
- Sheets `PersonalData`/`Card`/`FAQ`/`Plans`/`Referral`/`GymInfo` — уже подключены через `App.jsx` `ProfileRoute`; новый `SettingsScreen` переиспользует те же `onOpen*` колбэки.

### Established Patterns
- Рестайл-философия (quick-задачи 260601-oan/sxf/vxr): live-bind к реальным данным + graceful fallback; неподкреплённый декор — `BUILT, HIDDEN` за флагом; обязательная browser-проверка перед закрытием.
- Маршрутизация — react-router; защищённые экраны под `<RequireAuth>`; TabBar скрывается через `hideTabBar` в `App.jsx`.
- Тема — `TweaksContext` через `data-theme` на `<html>` (макетные ключи `myzal_theme`/`myzal_notif` НЕ переносить буквально — адаптировать под стор PWA).
- Деньги — целочисленные копейки + `formatMoney` из `src/utils/format.js` (D-999.4-05-A).

### Integration Points
- `App.jsx`: новый `<Route path="/settings">`, `SettingsRoute`-обёртка с теми же context-derived props, добавить `/settings` в `hideTabBar`.
- `ProfileScreen`: шестерёнка в identity-карточке → `navigate('/settings')` (через проп или `useNavigate`); удалить вкладку `settings` и компонент `SettingsList` переносом в `SettingsScreen`.
- Лоадер-скелет для `/settings` (по аналогии с `ProfileSkeleton`).

</code_context>

<specifics>
## Specific Ideas

- Hero сохраняет контраст-флип «pass» из макета: в светлой теме — тёмный графитовый пропуск, в тёмной — бежевый (CSS-переменные `--mh-*` из `Profile.html`).
- Stat-полоска и count-up — визуально как в макете, но только для подкреплённых статов (визиты, тренировки).
- Quick-tiles «Приведи друга» (купон-стиль) и «О зале» уже существуют в текущем профиле — сохранить, привести к виду макета.
- Кнопка «Заморозить» остаётся только для активного абонемента (текущее поведение `sub.tone === 'ok'`).

</specifics>

<deferred>
## Deferred Ideas

- **Backend стажа клиента** («с нами N лет/недель») → раскроет бейдж tenure + 3-й стат (флаги `tenureBadge`, `weeksStat`).
- **Цена membership + флаг автопродления** в `/client/membership` → вернёт блок «Стоимость + Продление» в hero (D-74-03).
- **Workout-аналитика** (минуты/тип по дням) → включит карточку «Активность за неделю» (флаг `weeklyActivity`).
- **Card-on-file** (привязанная карта) → строка «Привязанная карта» в Настройках (флаг `linkedCard`).
- **Серверные настройки уведомлений** (notif-prefs endpoint) → перевод локальных тумблеров на реальную доставку.
- Тариф-тир/«PREMIUM» как доменное понятие — отсутствует; нужен backend-источник, прежде чем показывать бейдж тира.

</deferred>

---

*Phase: 74-downloads-profile-html-downloads-settings-html*
*Context gathered: 2026-06-02*
