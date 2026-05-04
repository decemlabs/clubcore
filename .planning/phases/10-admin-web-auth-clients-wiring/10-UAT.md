---
status: diagnosed
phase: 10-admin-web-auth-clients-wiring
source:
  - 10-01-SUMMARY.md
  - 10-02-SUMMARY.md
  - 10-03-SUMMARY.md
  - 10-04-SUMMARY.md
  - 10-05-SUMMARY.md
  - 10-06-SUMMARY.md
  - 10-07-SUMMARY.md
started: 2026-05-04T20:30:00Z
updated: 2026-05-04T21:05:00Z
verifier: Claude (chrome-devtools MCP, headless)
dev_url: http://localhost:5179
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Dev-сервер стартует с нуля без ошибок. Главная страница рендерится, в консоли нет
  красных ошибок.
result: pass
note: |
  В mock-режиме (default) `_protected.beforeLoad` намеренно пропускает auth-check
  (`if (API_MODE === 'mock') return`), поэтому юзер сразу попадает в AppShell
  с persisted ролью "Владелец" — by design, не bug. Console: 3 warnings от
  TanStack Router (deprecated ScrollRestoration + router-devtools rename) — давний
  tech debt, не из Phase 10.

### 2. Email Login (owner)
expected: |
  /login → вкладка "Email" по умолчанию активна. Submit с любым валидным email/паролем
  → редирект на / (главная).
result: pass

### 3. Telegram OTP Login
expected: |
  /login → вкладка "Telegram OTP" → "Получить ссылку" → mock-сервис через ~3 опроса
  переходит в "Чат привязан" → ввод OTP 123456 → редирект на /.
result: pass
note: |
  Mock-сервис связал чат быстрее ожидаемого (3 polls × 120-300ms ≈ 600ms),
  поэтому экран с deeplink-ссылкой промелькнул и сразу появилось поле OTP.
  Корректное поведение.

### 4. /clients List Renders With Seeded Data
expected: |
  Таблица DataGrid с клиентами (faker seed=42), пагинация "1 - 20 of 30",
  поиск работает с debounce.
result: pass
note: |
  Колонки: ФИО / Телефон / Email / Дата регистрации (а не "Дата рождения" — registration date,
  не birthDate). Поиск "Wehner" → 1 result, URL обновляется (q=Wehner).

### 5. Create Client
expected: |
  Кнопка "Новый клиент" → Dialog "Добавить клиента". Заполнение фамилии/имени/телефона →
  submit → диалог закрывается, новый клиент появляется в таблице.
result: pass
note: |
  Создан "Иванов Иван +79991234567". Total 30 → 31. Toast не зафиксирован (timing).
  Возможный UX nit: если активен поиск, новосозданный клиент не виден в таблице
  (отфильтрован) — могло бы быть полезно очищать поиск или сообщать toast.

### 6. Edit Client (Optimistic Update — verifies WR-01 fix)
expected: |
  Edit "Иванов Иван" → изменить имя на "Сергей" → submit → fullName в таблице
  немедленно обновляется на "Иванов Сергей".
result: pass
note: |
  WR-01 fix (reconstruction of fullName в onMutate) работает корректно — оптимистичный
  apply показал "Иванов Сергей" сразу, без задержки до серверного ответа.

### 7. Delete Client (Optimistic Remove)
expected: |
  "Удалить клиента" → AlertDialog "Удалить клиента?" с deструктивной кнопкой "Удалить".
  Confirm → клиент исчезает немедленно, total обновляется.
result: pass
note: |
  AlertDialog показал имя "Иванов Сергей" в body. После confirm: total 31 → 30,
  Иванов исчез из таблицы.

### 8. RBAC Redirect (reception → owner-only routes)
expected: |
  Reception role → переход на /finance, /settings → редирект на /?forbidden=<path> с
  сообщением "Доступ запрещён: <path>".
result: issue
reported: |
  /finance и /settings вместо редиректа крашат с TypeError: "Cannot convert object to primitive value"
  (на странице красная ошибка "Something went wrong! Cannot convert object to primitive value",
  React error boundary ловит). Sidebar фильтруется правильно (Финансы/Настройки скрыты для
  reception); /staff и /schedule доступны (они НЕ owner-only). Crash — регрессия от CR-01 фикса.
severity: blocker
root_cause: |
  CR-01 fix заменил `location.href` на `location.pathname + (location.search ?? '')`
  в beforeLoad. В TanStack Router `location.search` — это **парсенный объект**
  (типа `{ page: 1, pageSize: 20 }`), не строка. Конкатенация объекта со строкой через `+`
  вызывает `Symbol.toPrimitive`/`toString()` на объекте → TypeError, потому что у
  ParsedLocation.search нет primitive coercion в этом контексте (или он бросает).
artifacts:
  - apps/admin-web/src/routes/_protected/finance.tsx:9
  - apps/admin-web/src/routes/_protected/settings.tsx:9
  - apps/admin-web/src/routes/_protected/schedule.tsx:9
  - apps/admin-web/src/routes/_protected/staff.tsx:9
  - apps/admin-web/src/routes/_protected/clients.tsx:19
  - apps/admin-web/src/routes/_protected.tsx (тот же паттерн в http-mode 401-ветке)
fix_options:
  - "Использовать `location.href` (в TanStack Router это **относительный** href, без origin — был ошибочно отвергнут в CR-01 review как 'full URL включая origin'; на самом деле это `pathname + searchStr + hash`, что и есть нужный формат)."
  - "Либо `location.pathname + (location.searchStr ?? '')` — searchStr это закодированная строка с лидирующим '?'."

### 9. Logout Flow
expected: |
  ProfileMenu → "Выйти" → cache очищается, редирект на /login.
result: pass
note: |
  Mock-режим: после logout попытка вернуться на / via прямой URL по-прежнему откроет
  AppShell, потому что `_protected.beforeLoad` пропускает auth-check в mock. Это by design
  (Phase 10 не делает full logout в mock — только UX-flow), для http-mode логика другая.

## Summary

total: 9
passed: 8
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Reception role accessing owner-only routes (/finance, /settings) should redirect to / with forbidden notice"
  status: failed
  reason: "User reported via verifier: TypeError 'Cannot convert object to primitive value' instead of redirect — CR-01 fix introduced regression"
  severity: blocker
  test: 8
  root_cause: "TanStack Router's `location.search` is a parsed object, not a string. CR-01 fix did `location.pathname + (location.search ?? '')` which triggers Symbol.toPrimitive on the object and throws."
  artifacts:
    - apps/admin-web/src/routes/_protected/finance.tsx:9
    - apps/admin-web/src/routes/_protected/settings.tsx:9
    - apps/admin-web/src/routes/_protected/schedule.tsx:9
    - apps/admin-web/src/routes/_protected/staff.tsx:9
    - apps/admin-web/src/routes/_protected/clients.tsx:19
    - apps/admin-web/src/routes/_protected.tsx
  missing:
    - Replace `location.search` concatenation with `location.searchStr` or use `location.href` (relative href in TanStack Router)
  debug_session: ""
