---
status: complete
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
source:
  - 22-01-SUMMARY.md
  - 22-02-SUMMARY.md
  - 22-03-SUMMARY.md
  - 22-04-SUMMARY.md
  - 22-05-SUMMARY.md
started: 2026-05-08T15:54:25Z
updated: 2026-05-08T16:08:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Dev сервер `pnpm dev` поднимается на http://localhost:5173/, AppShell + sidebar + topbar рендерятся без ошибок в консоли.
result: pass

### 2. Тарифы — список планов с пагинацией (FE-04, FE-06, BLK-02 fix)
expected: Таблица 8 планов с активными и архивированными, пагинация, кнопка «Новый тариф».
result: issue
reported: "Ошибка при сохранении тарифа. когда меняю цену"
severity: major
diagnosed: "mock updatePlan кидал DomainError(mock_not_implemented), форма перехватывала и показывала t('common.errors.saveTariff') без проверки code. Идентичная проблема в createPlan, deletePlan, create membership, cancel membership."
fixed_in: "commit 4452c28 — добавлен common.errors.demoMode + проверка err.code === 'mock_not_implemented' во всех 5 write-точках memberships."

### 3. Абонементы — список с фильтром «Истекают через 7 дней» (FE-04, FE-10 D-2)
expected: Список абонементов со статусами Активен/Истёк/Отменён, период с inclusive end_date, фильтр «Истекают через 7 дней».
result: pass

### 4. Отметки — поиск клиента по телефону + дисамбигуация (FE-05, FE-08a)
expected: Поле телефона с маской, listbox-дисамбигуация при вводе полного номера, fallback «Клиент не найден».
result: pass

### 5. Отметки — кейс «нет активного абонемента» (FE-08, VIS-03 anti-fraud)
expected: Карточка клиента + inline «Нет активного абонемента» для истёкшего абонемента.
result: pass

### 6. Отметки — mock_not_implemented локализован (Bug #2 fix this session)
expected: Локализованная inline-ошибка для клика «Отметить» с активным абонементом в mock-режиме.
result: pass

### 7. Pattern α — /clients/$clientId с тремя блоками (FE-07 fix this session)
expected: Детальная страница клиента с ClientProfileCard + MembershipsBlock + RecentVisitsBlock через Promise.all loader.
result: pass

### 8. /profile — Active Sessions UI с mock-guard (FE-09)
expected: heading «Профиль», alert «Управление сессиями недоступно…», кнопка «Выйти со всех устройств».
result: pass
verified_by: claude (chrome-devtools snapshot uid 15_27..15_31)

### 9. Cheap-win D-3 — бейдж «истекает сегодня» с правильным текстом (FE-10 D-3, BLK-03 fix)
expected: Бейдж «Абонемент истекает сегодня» для активного абонемента с end_date == сегодня (НЕ «истёк сегодня»).
result: pass
verified_by: claude — seed не содержал подходящих данных, временно подменил endDate одного абонемента (Deckow Sadye, unselfish 365) на 2026-05-08 через localStorage; бейдж появился ровно с текстом «Абонемент истекает сегодня» (BLK-03 fix); endDate восстановлен.

### 10. Переключение темы — light/dark/system (theming bootstrap)
expected: Меню Светлая/Тёмная/Системная, мгновенное применение semantic tokens, без FOUC.
result: pass
verified_by: claude — клик «Тема» → меню с 3 пунктами; «Светлая» применила white background + dark text + sun icon; «Тёмная» вернула dark; никаких визуальных артефактов.

### 11. Переключение роли — Owner→Reception (RBAC sidebar filtering)
expected: Sidebar скрывает OWNER_ONLY пункты, прямой переход на owner-only маршрут редиректит на /.
result: pass
verified_by: claude — переключение в «Ресепшн» убрало Тарифы/Финансы/Настройки из sidebar, кнопки «Отменить» в MembershipsBlock исчезли (OWNER_ONLY CANCEL); переход на /membership-plans редиректнул на /?forbidden=%2Fmembership-plans с alert «Доступ запрещён».

## Summary

total: 11
passed: 10
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Operator может изменить цену существующего тарифа через MembershipPlanFormDialog (FE-04 / FE-06 / BLK-04)"
  status: failed
  reason: "User reported: Ошибка при сохранении тарифа. когда меняю цену"
  severity: major
  test: 2
  artifacts: []  # Filled by diagnosis
  missing: []    # Filled by diagnosis
