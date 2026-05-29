# clubcore Backend Auth Runbook (v1.11)

> Расширяет структуру v1.4 runbook под именем clubcore. Охватывает все auth-потоки
> v1.11 + семантику `Idempotency-Key` (Phase 66) + план перехода на v2.0.

**Audience:** внешняя дизайн-команда v2.0 (production admin + client apps).
**Backend version:** v1.11 (post-Phase-66 frozen spec; финальный коммит Phase 66).
**Source-of-truth contract:** `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`.

---

## 1. Login (email/password)

`POST /api/v1/auth/login` принимает `{"email", "password"}`, проверяет Argon2id-хэш
через `apps/backend/app/modules/auth/router.py` и при успехе ставит три cookie:

- `sz_access` (httpOnly, `Path=/`) — короткоживущий access JWT (15 мин по умолчанию).
- `sz_refresh` (httpOnly, `Path=/api/v1/auth`) — узкоскопный refresh token; `Path=/api/v1/auth`
  минимизирует exposure (браузер отправляет его только на auth-маршруты).
- `sportzal_csrf` (**НЕ** httpOnly, `Path=/`) — JS-readable double-submit CSRF cookie; см. § 3.

Обе роли (`owner`, `reception`) используют один и тот же endpoint. RBAC прописан
per-route через `OWNER_ONLY` frozenset (`apps/backend/app/core/rbac.py`).

Ответ — `ResponseEnvelope[LoginResponse]` с `data.user` (UserPublic).

```bash
# Вход owner
curl -i -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email":"verify_owner@local.dev","password":"<owner-password>"}'
# → HTTP/1.1 200 OK
# → Set-Cookie: sz_access=...; HttpOnly; Path=/; SameSite=Lax
# → Set-Cookie: sz_refresh=...; HttpOnly; Path=/api/v1/auth; SameSite=Strict
# → Set-Cookie: sportzal_csrf=...; Path=/; SameSite=Lax
# → {"data":{"user":{"id":"...","email":"verify_owner@local.dev","role":"owner",...}}}

# Вход reception (тот же endpoint, другая роль)
curl -i -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email":"verify_reception@local.dev","password":"<reception-password>"}'
```

Cookie jar `cookies.txt` далее используется для всех последующих запросов.

> **Postman:** соответствует запросу **"Login"** в папке `Auth`
> (`POST /api/v1/auth/login`). Pre-request script коллекции автоматически
> извлекает `sportzal_csrf` → `{{csrfToken}}` и `sz_access` → `{{accessToken}}`
> из ответных заголовков.

---

## 2. Refresh rotation family

`POST /api/v1/auth/refresh` читает `sz_refresh` cookie напрямую (без авторизационной
dependency — истёкший access cookie не должен блокировать refresh). Семантика —
**rotation family**: старый refresh инвалидируется, новый выдаётся в ответе.

Параллельные клиенты **обязаны** шарить один in-flight refresh (single-flight
discipline); иначе гонка вызовет `session_expired` на всех участниках, кроме
первого. Полное описание контракта: `packages/api-client/README.md`
§ "Single-flight refresh" — модуль-уровень `inFlightRefresh: Promise<Response> | null`.

```bash
curl -i -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -b cookies.txt -c cookies.txt
# → HTTP/1.1 200 OK
# → Set-Cookie: sz_access=...  (новый access token)
# → Set-Cookie: sz_refresh=... (новый refresh token; старый инвалидирован)
# → Set-Cookie: sportzal_csrf=... (обновлён)
# → {"data":null}
```

Если refresh token уже истёк или был инвалидирован — `401 session_expired`.
Клиент редиректит пользователя на `/login`.

> **Postman:** соответствует запросу **"Refresh"** в папке `Auth`
> (`POST /api/v1/auth/refresh`).

---

## 3. CSRF on mutating requests

Каждый mutating HTTP verb (POST / PATCH / PUT / DELETE) **обязан** содержать header
`X-CSRF-Token: <значение cookie sportzal_csrf>`. Backend проверяет совпадение через
`verify_csrf` dependency; несовпадение → `403 csrf_mismatch`. GET / HEAD / OPTIONS
освобождены от CSRF (соответствует server-side `_SAFE_METHODS` short-circuit).

Fetcher из `packages/api-client` автоматически читает `sportzal_csrf` и проставляет
`X-CSRF-Token` на всех mutating методах — см. `packages/api-client/README.md` § "CSRF".

```bash
# Извлечь CSRF-значение из cookie jar (awk-way из verify-скриптов проекта)
CSRF=$(awk '$6=="sportzal_csrf"{print $7}' cookies.txt)

# Пример mutating запроса с CSRF + Idempotency-Key
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>","amountKopecks":300000}'
```

`sportzal_csrf` — v1.x carry-over name; переименование в `clubcore_csrf` отложено
до v2.0 (D-11-CSRF-DEFER). Подробнее: § 8.

> **Postman:** pre-request script коллекции на уровне всей коллекции автоматически
> добавляет `X-CSRF-Token: {{csrfToken}}` ко всем non-GET запросам. Соответствует
> паттерну во всех mutating запросах папок `Memberships`, `Bookings`, `Schedule`,
> `Payments`, `Visits` — например, **"Sell a membership (reception+owner; ...
> requires Idempotency-Key)"** в папке `Memberships`.

---

## 4. Telegram OTP (client-app path)

Трёхшаговый flow для self-service client app. Endpoints **не** авторизованы (identity
живёт в body, CSRF exempt — Phase 6 D-09).

1. **Start** `POST /api/v1/auth/telegram/start` — backend минтит deep-link token,
   возвращает `{deepLinkUrl, deepLinkToken}`. URL ведёт на `t.me/<bot>?start=<token>`.
2. **Status (poll)** `GET /api/v1/auth/telegram/status?token=<deepLinkToken>` —
   `{bound: false}` до нажатия Start в боте; `{bound: true}` после записи OTP
   bot-worker'ом (6-значный код, DM пользователю).
3. **Verify** `POST /api/v1/auth/telegram/verify` с `{deepLinkToken, code}` —
   выдаёт cookie идентично `/login` (§ 1) + эмитирует `login_success` с
   `channel='telegram'`.

Bot worker — отдельный long-polling процесс
(`apps/backend/app/workers/telegram_bot.py`).

```bash
# Шаг 1: Start — получить deep-link
curl -i -s -X POST http://localhost:8000/api/v1/auth/telegram/start \
  -H "Content-Type: application/json"
# → 200 {"data":{"deepLinkUrl":"https://t.me/<bot>?start=<token>","deepLinkToken":"abc..."}}

# Шаг 2: Poll status
curl -i -s "http://localhost:8000/api/v1/auth/telegram/status?token=<deepLinkToken>"
# → 200 {"data":{"bound":false}}   (до нажатия Start в боте)
# → 200 {"data":{"bound":true}}    (после привязки)

# Шаг 3: Verify
curl -i -s -X POST http://localhost:8000/api/v1/auth/telegram/verify \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"deepLinkToken":"<deepLinkToken>","code":"<6-digit-otp>"}'
# → 200 + три Set-Cookie (идентично /login)
```

> **Postman:** соответствуют запросам **"Telegram Start"**, **"Telegram Status"**
> и **"Telegram Verify"** в папке `Auth`.

---

## 5. Email OTP

Email OTP — механизм беспарольной аутентификации через разовый код на e-mail.
Запрос `POST /api/v1/auth/otp/request` триггерит отправку письма с OTP-кодом.
Endpoint **не** авторизован; CSRF exempt (идентично Telegram flow).

После получения кода пользователь передаёт его в отдельный verify-шаг. Endpoint
защищён circuit-breaker'ом на уровне email-отправки. Запрос не создаёт изменений
account state, поэтому классифицирован **B** (не требует `Idempotency-Key`).

```bash
# Шаг 1: Запросить OTP на email
curl -i -s -X POST http://localhost:8000/api/v1/auth/otp/request \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com"}'
# → 202 {"data":null}  (принято; письмо отправлено асинхронно)
# → 429                (rate limit превышен)
```

Код из письма используется в verify-шаге (endpoint специфичен для flow
client-app; для admin-web используется email/password login § 1).

> **Postman:** соответствует запросу **"Otp Request"** в папке `Auth`
> (`POST /api/v1/auth/otp/request`).

---

## 6. Logout-all

`POST /api/v1/auth/logout-all` уничтожает **все** живые session family текущего
пользователя (не только текущую сессию) + очищает cookie у caller'а
(`apps/backend/app/modules/auth/router.py`). Это nuke-option для UX
"подозреваю компрометацию".

Требует `X-CSRF-Token` (mutating endpoint). Остальные сессии того же пользователя
становятся невалидны: либо при следующем mutating request (CSRF пройдёт, но
access cookie уже отвергнут), либо при следующем refresh (refresh row удалён) →
клиент получает `401` и редиректит на `/login`.

Endpoint классифицирован **B** (не требует `Idempotency-Key` — повторный вызов
на уже-пустой set сессий является no-op).

```bash
CSRF=$(awk '$6=="sportzal_csrf"{print $7}' cookies.txt)
curl -i -s -X POST http://localhost:8000/api/v1/auth/logout-all \
  -H "X-CSRF-Token: $CSRF" \
  -b cookies.txt -c cookies.txt
# → 200 {"data":null}
# → Set-Cookie: sz_access=; Max-Age=0   (cookie cleared)
# → Set-Cookie: sz_refresh=; Max-Age=0
# → Set-Cookie: sportzal_csrf=; Max-Age=0
```

> **Postman:** соответствует запросу **"Logout All"** в папке `Auth`
> (`POST /api/v1/auth/logout-all`).

---

## 7. Idempotency-Key semantics

### 7.1 Назначение и формат

Phase 66 добавила `Idempotency-Key` заголовок ко всем Category-A endpoints
(финансовые / value-creating мутации). Контракт гарантирует, что повторный запрос
с тем же ключом вернёт кэшированный ответ первого успешного вызова без повторного
выполнения операции.

**Формат заголовка:**

```
Idempotency-Key: <key>
```

Регулярное выражение: `^[A-Za-z0-9_:-]{16,128}$`

- Минимум 16, максимум 128 символов.
- Допустимые символы: буквы, цифры, подчёркивание, двоеточие, дефис.
- Рекомендуется: UUIDv4 (36 символов) — `$(uuidgen)`.

### 7.2 Область действия (user-scope)

Ключ user-scoped. Redis-ключ: `cc:idem:{user_id}:{method}:{path}:{key}`.

Два разных пользователя **могут** использовать одну и ту же строку ключа без
коллизии (D-11-IDM-USER security fix). Строка `abc-123` от пользователя A никак
не пересекается с той же строкой от пользователя B.

### 7.3 Окно воспроизведения (replay window)

TTL: **24 часа (86400 секунд)** с момента первого успешного вызова.

По истечении 24 ч ключ удаляется из Redis; следующий вызов с тем же ключом
создаёт новую операцию (не replay). Если нужна гарантия сохранения ответа
за пределами 24 ч — используйте ресурсный GET (см. § 7.4).

### 7.4 Вербатимный replay

Повторный запрос с тем же `Idempotency-Key` и тем же телом возвращает **кэшированный
ответ первого успешного вызова** — не текущее состояние DB.

```
Вызов 1 → создаёт membership, кэширует {"data":{"id":"mem-uuid",...}} в Redis
Вызов 2 (тот же ключ, то же тело) → возвращает тот же {"data":{"id":"mem-uuid",...}}
           (никакой записи в DB; ответ из кэша)
```

**Важно:** если state ресурса изменился после первого вызова (например, membership
отменили), replay всё равно вернёт оригинальный ответ создания. Для актуального
состояния используйте ресурсный GET: `GET /api/v1/memberships/{membership_id}`.

### 7.5 Коды ошибок

| Ситуация | HTTP | Код ошибки |
|----------|------|------------|
| Category-A endpoint без `Idempotency-Key` | 422 | `idempotency_key_required` |
| Тот же ключ + **другое тело** (body-hash mismatch) | 422 | `idempotency_key_reuse` |
| Невалидный формат ключа (нарушает regex) | 422 | `idempotency_key_invalid` |

### 7.6 Рекомендации клиенту

- Генерируйте **свежий** UUIDv4 для каждой новой логической операции.
- Повторно используйте **тот же** ключ только для ретраев той же операции.
- Не переиспользуйте ключ для разных операций (даже на другом endpoint) — риск
  `idempotency_key_reuse` при совпадении пути + метода.

```javascript
// Правильно — retry той же операции
const key = crypto.randomUUID()
await sellMembership(planId, clientId, { 'Idempotency-Key': key })
// При сетевой ошибке:
await sellMembership(planId, clientId, { 'Idempotency-Key': key }) // тот же key

// Неправильно — новый key на каждый retry
await sellMembership(planId, clientId, { 'Idempotency-Key': crypto.randomUUID() })
// ↑ создаст новую операцию, если первый вызов прошёл
```

### 7.7 Category-A endpoints (требуют Idempotency-Key)

Полный список из `.planning/handoff/v1.11-idempotency-audit.md` (22 operationId,
все wired после Phase 66):

| endpoint | method | operationId |
|----------|--------|-------------|
| `/api/v1/memberships` | POST | `create_membership` |
| `/api/v1/memberships/{id}/cancel` | POST | `cancel_membership` |
| `/api/v1/memberships/{id}/freeze` | POST | `freeze_membership` |
| `/api/v1/memberships/{id}/unfreeze` | POST | `unfreeze_membership` |
| `/api/v1/memberships/{id}/renew` | POST | `renew_membership` |
| `/api/v1/online-payments/memberships/{id}/sell` | POST | `sell_membership_redirect` |
| `/api/v1/online-payments/memberships/{id}/sell-qr` | POST | `sell_membership_qr` |
| `/api/v1/online-payments/pt-packages/{id}/sell` | POST | `sell_pt_package_redirect` |
| `/api/v1/online-payments/pt-packages/{id}/sell-qr` | POST | `sell_pt_package_qr` |
| `/api/v1/pt-packages` | POST | `create_pt_package` |
| `/api/v1/pt-packages/{id}/cancel` | POST | `cancel_pt_package` |
| `/api/v1/pt-packages/{id}/refund` | POST | `refund_pt_package` |
| `/api/v1/pt-sessions` | POST | `record_pt_session` |
| `/api/v1/pt-sessions/{id}/cancel` | POST | `cancel_pt_session` |
| `/api/v1/bookings` | POST | `create_booking` |
| `/api/v1/bookings/{id}/cancel` | POST | `cancel_booking` |
| `/api/v1/trainer-slots` | POST | `publish_slot` |
| `/api/v1/trainer-slots/{id}/cancel` | PATCH | `cancel_slot` |
| `/api/v1/recurring-templates` | POST | `create_recurring_template` |
| `/api/v1/recurring-templates/{id}/deactivate` | POST | `deactivate_recurring_template` |
| `/api/v1/time-off` | POST | `create_time_off` |
| `/api/v1/time-off/{id}` | DELETE | `delete_time_off` |

**Исключения (Category-B — НЕ принимают header `Idempotency-Key`):**

- `refund_membership` (`POST /api/v1/memberships/{id}/refund`) — защищён DB partial
  UNIQUE `uq_payments_refund_of_alive`; повторный вызов → `409 already_refunded`.
  Router docstring явно документирует: "NO Idempotency-Key — refund flow uses DB
  partial UNIQUE (D-32-20)."
- `refund_membership_online`, `refund_pt_package_online` (online refunds) — принимают
  `idempotency_key` в **теле запроса** (forwarded в ЮKassa `Idempotence-Key`); плюс
  DB partial UNIQUE `uq_online_refunds_alive_per_online_payment`. Заголовок не нужен.

### 7.8 ЮKassa webhook dedup (информационно)

`POST /_internal/yookassa/webhook` использует **отдельный** dedup path (D-11-IDM-WEBHOOK):
Redis `SET NX EX 86400` с ключом `cc:yk:webhook:{event}:{object_id}`. Этот механизм
независим от user-scoped `Idempotency-Key` и не имеет отношения к header-идемпотентности.
IP-аутентифицированный транспортный callback (`verify_yookassa_ip`); не включён в
OpenAPI schema (`include_in_schema=False`).

### 7.9 Worked replay curl example

```bash
# Подготовка
CSRF=$(awk '$6=="sportzal_csrf"{print $7}' cookies.txt)
IDEM="$(uuidgen)"  # e.g. "f47ac10b-58cc-4372-a567-0e02b2c3d479"

# Первый вызов — создаёт membership (или возвращает 404 AppError на placeholder UUID)
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $IDEM" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>"}'
# → Ответ A (кэшируется в Redis на 24 ч)

# Replay — тот же ключ, то же тело → вернёт Ответ A из кэша
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $IDEM" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>"}'
# → Тот же Ответ A (verbatim, не live DB state)
```

> **Postman:** соответствует паре запросов **"smoke: idem-1 — create_membership
> first call (captures status)"** и **"smoke: idem-2 — create_membership replay
> (same key, asserts verbatim)"** в папке `smoke` коллекции v1.11.

### 7.10 Newman smoke (local handoff smoke — not a CI gate)

Newman smoke — **локальный handoff smoke, не CI gate** (D-11-NEWMAN-LOCAL).
Предназначен для проверки auth + CSRF + domain reachability против свежего
`docker compose` DB. Не является blocking gate в CI pipeline (отложено до v2.0).

**Запуск:**

```bash
# Требования: docker compose up + seed-скрипт с SEED_VERIFY_OWNER_PASSWORD
SEED_VERIFY_OWNER_PASSWORD=<password> pnpm newman run \
  .planning/handoff/v1.11-clubcore.postman_collection.json \
  -e tools/newman/clubcore-smoke.postman_environment.json \
  --folder smoke \
  --bail \
  --env-var "password=$SEED_VERIFY_OWNER_PASSWORD"
```

**In-smoke requests (14 запросов):**

| # | Request | Назначение |
|---|---------|------------|
| 1 | `POST /api/v1/auth/login` (smoke: Login) | Auth: аутентификация с fixture credentials; захват `sportzal_csrf` → `csrfToken` |
| 2 | `GET /api/v1/auth/me` (smoke: Auth/Me) | Auth: подтверждение активной сессии |
| 3a | `GET /api/v1/users` (smoke: Users list) | Users: safe list |
| 3b | `GET /api/v1/clients` (smoke: Clients list) | Clients: safe list |
| 3c | `GET /api/v1/membership-plans` (smoke: Membership-plans list) | Memberships: safe list |
| 3d | `GET /api/v1/visits` (smoke: Visits list) | Visits: safe list |
| 3e | `GET /api/v1/recurring-templates` (smoke: Recurring-templates list) | Schedule: safe list |
| 3f | `GET /api/v1/bookings` (smoke: Bookings list) | Bookings: safe list |
| 3g | `GET /api/v1/trainers` (smoke: Trainers list) | Trainers: safe list |
| 3h | `GET /api/v1/payments` (smoke: Payments list) | Payments: safe list |
| 3i | `GET /api/v1/reports/clients` (smoke: Reports/clients) | Reports: safe summary |
| 3j | `GET /api/v1/audit-log` (smoke: Audit-log list) | Audit-log: safe list |
| 4a | `POST /api/v1/memberships` (smoke: idem-1) | Idempotency: первый вызов (placeholder UUID → 404 AppError, кэшируется IDM-06) |
| 4b | `POST /api/v1/memberships` (smoke: idem-2) | Idempotency: verbatim replay; asserts same status + body |

**Excluded (D-65-SMOKE-SCOPE):** Финансовые мутации (online sales, cash refunds) и
деструктивные операции, требующие сложных фикстур. `--bail` отрабатывает на реальных
поломках, не на fixture gaps.

---

## 8. sportzal_csrf carry-over + v2.0 cutover plan

### 8.1 Текущее состояние (v1.11)

Cookie `sportzal_csrf` — имя из v1.x (до переименования проекта), сохранённое
в v1.11 per **D-11-CSRF-DEFER**. Переименование в `clubcore_csrf` отложено до v2.0
с координированным cutover admin-web команды.

В коде зафиксировано двумя аннотациями:

- `apps/backend/app/main.py` **строка ~199** (SECURITY_SCHEMES):
  ```
  # cookie is named `sportzal_csrf` — a v1.x carry-over retained
  # per D-11-CSRF-DEFER; rename to `clubcore_csrf` is deferred to
  # v2.0 with a coordinated admin-web cutover (see auth runbook at
  # .planning/handoff/clubcore-auth-runbook.md and D-11-CSRF-DEFER).
  ```

- `apps/backend/app/main.py` **строка ~428** (openapi info description):
  ```
  # Carry-over: the `sportzal_csrf` cookie name is retained in
  # v1.11 per D-11-CSRF-DEFER; rename to `clubcore_csrf` is
  # scheduled for v2.0 with a coordinated admin-web cutover
  ```

### 8.2 Что читать frontend-команде

В v1.11 **всегда** читайте cookie с именем `sportzal_csrf`:

```javascript
// Правильно в v1.11
const csrf = document.cookie
  .split('; ')
  .find(c => c.startsWith('sportzal_csrf='))
  ?.split('=')[1] ?? ''

// Или через Postman/api-client fetcher:
// pm.cookies.get('sportzal_csrf')
```

**Не** используйте `clubcore_csrf` — этого cookie ещё не существует в v1.11.

### 8.3 Plan v2.0 cutover

При переходе на v2.0 backend переименует cookie-ключ. Алгоритм cutover:

1. Backend выпускает v2.0 с `clubcore_csrf` (Set-Cookie выдаёт новое имя).
2. Frontend **читает то имя, которое приходит** — для совместимости рекомендуется
   fallback:
   ```javascript
   const csrf = cookies.get('clubcore_csrf') || cookies.get('sportzal_csrf') || ''
   ```
3. После полного rollout v2.0 и подтверждения, что ни один v1.x клиент не активен,
   fallback удаляется.

Этот раздел является **cutover anchor** — обновите его при выпуске v2.0.

---

## Дальнейшие шаги

- **Postman collection v1.11:** `.planning/handoff/v1.11-clubcore.postman_collection.json`
  (137 endpoints из `openapi.json`, grouped by 10 domain tags, pre-request login +
  CSRF-auto + body-shape assertions).
- **Full contract:** `apps/backend/openapi.json` (source-of-truth) +
  `packages/api-client/src/schema.d.ts` (TypeScript types, генерируются через
  `pnpm --filter @clubcore/api-client codegen`).
- **API doc-site (local-only):** `pnpm docs` запускает `redocly preview-docs
  apps/backend/openapi.json --port 8080` — приватный артефакт, не публикуется
  (D-11-DOCS-PRIVATE).
- **Newman smoke:** `pnpm newman run --folder smoke` (local handoff smoke, not a CI
  gate; D-11-NEWMAN-LOCAL).
- **v2.0:** sportzal_csrf → clubcore_csrf rename + Newman как blocking CI gate.

## Operator

andre.shipunov@icloud.com
