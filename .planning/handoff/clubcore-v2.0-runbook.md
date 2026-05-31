# clubcore Client-Portal Runbook (v2.0)

> Охватывает полный клиентский путь v2.0: phone-OTP аутентификация, read-path
> (home / membership / slots / booking / QR check-in / history) и ЮKassa checkout
> (OPERATOR-PENDING). Является исполнительным руководством к фазам 68–71.

**Audience:** оператор локального стенда и разработчик client-PWA.
**Backend version:** v2.0 (post-Phase-71 frozen spec; финальный коммит Phase 72).
**Source-of-truth contract:** `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`.

---

## 1. Dev-stack setup

### 1.1 Переменные окружения

Перед запуском добавьте или убедитесь в наличии в `apps/backend/.env`:

```dotenv
ENVIRONMENT=dev
DEV_OTP_PIN_ENABLED=true
```

`ENVIRONMENT=dev` активирует клиентский OTP-пин 111111 и пишет код в structlog
под событием `client_otp_dev_code`. `DEV_OTP_PIN_ENABLED=true` — отдельный флаг,
позволяющий включить/выключить пин независимо от имени окружения.

Для ЮKassa checkout-ветки (OPERATOR-PENDING, см. § 5) добавьте также:

```dotenv
YOOKASSA_SANDBOX=true
YOOKASSA_SHOP_ID=<ваш sandbox shop_id>
YOOKASSA_SECRET_KEY=test_<ваш test-ключ>
YOOKASSA_RETURN_URL=http://localhost:5173/checkout/status
```

`YOOKASSA_SANDBOX=true` отключает boot-probe ЮKassa и IP allowlist — backend
стартует без сетевого обращения к ЮKassa при init.

### 1.2 Запуск стека

```bash
# Поднять postgres + redis + backend (без mailpit)
cd apps/backend
docker compose up -d postgres redis backend

# После изменения .env — перезагрузить только backend
docker compose up -d --force-recreate backend
```

Проверка готовности:

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/healthz
# → 200
```

### 1.3 Применение миграций

Миграции накатываются автоматически через контейнер `migrate` при первом старте.
Если нужно запустить вручную:

```bash
docker compose run --rm migrate
```

### 1.4 Сиды для dev UAT

Обязательный порядок запуска:

```bash
cd apps/backend

# Шаг 1 — bootstrap owner + catalog (idempotent)
SEED_OWNER_EMAIL=owner@local.dev \
SEED_OWNER_PASSWORD=changeme123dev \
uv run python -m scripts.seed_demo_data
# → Seeded owner owner@local.dev (idempotent: no-op if existed).
# → Seeded client catalog: 1 membership plan + 1 PT-package (idempotent).

# Шаг 2 — dev-test client (requires ENVIRONMENT=dev, owner must exist first)
uv run python -m scripts.seed_dev_client
# → Seeded dev test client +79999999999 (telegram_user_id=999999999).
# → Login in the PWA with phone '999 999-99-99', then enter '111111'
```

`seed_demo_data` создаёт владельца и минимальный каталог:
- Абонемент **«Месяц безлимит»** (duration_days=30, price=5000₽).
- PT-пакет **«5 тренировок»** (session_count=5, price=15000₽).

`seed_dev_client` создаёт клиента с телефоном `+79999999999` и фиктивным
`telegram_user_id=999999999`, достаточным для OTP-flow.

### 1.5 Предусловие для book/QR шагов (D-72-07)

Шаги «Забронировать слот» (§ 3.4) и «QR check-in» (§ 3.5) требуют активного
абонемента **и** PT-пакета у dev-клиента. Способы получить их:

**A. Через sell-endpoint (staff side — рекомендуется):**

```bash
# 1. Войти как owner
curl -i -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c staff_cookies.txt \
  -d '{"email":"owner@local.dev","password":"changeme123dev"}'

CSRF_STAFF=$(awk '$6=="clubcore_csrf"{print $7}' staff_cookies.txt)

# 2. Получить client_id dev-клиента
curl -s "http://localhost:8000/api/v1/clients?phone=%2B79999999999" \
  -b staff_cookies.txt | python3 -m json.tool
# → запомнить data.items[0].id → CLIENT_ID

# 3. Продать абонемент
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_STAFF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b staff_cookies.txt \
  -d "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"<membership_plan_id>\",\"amountKopecks\":500000}"

# 4. Продать PT-пакет
curl -i -s -X POST http://localhost:8000/api/v1/pt-packages \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_STAFF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b staff_cookies.txt \
  -d "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"<pt_package_plan_id>\",\"amountKopecks\":1500000}"
```

**B. Через ЮKassa checkout (OPERATOR-PENDING, см. § 5):** клиент сам покупает
через PWA — требует ЮKassa sandbox credentials.

---

## 2. Phone-OTP login

Клиентская аутентификация — двухшаговая: `POST /otp/request` (запрос кода) →
`POST /otp/verify` (верификация + выдача cookies).

Оба endpoint pre-auth (нет `require_client()` dep), CSRF exempt (D-09).

### 2.1 Запрос OTP (dev: anti-oracle — всегда 202)

```bash
curl -i -s -X POST http://localhost:8000/api/v1/client/otp/request \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79999999999"}'
# → HTTP/1.1 202 Accepted
# → {"data":null}
```

Для любого телефона (известного / незнакомого / непривязанного) backend возвращает
202 — anti-oracle invariant (CAUTH-02). Код `111111` логируется в stdout backend
как `structlog` event `client_otp_dev_code`.

### 2.2 Верификация OTP и получение session cookies

```bash
curl -i -s -X POST http://localhost:8000/api/v1/client/otp/verify \
  -H "Content-Type: application/json" \
  -c client_cookies.txt \
  -d '{"phone":"+79999999999","code":"111111"}'
# → HTTP/1.1 200 OK
# → Set-Cookie: cc_client_access=...; HttpOnly; Path=/; SameSite=Lax
# → Set-Cookie: cc_client_refresh=...; HttpOnly; Path=/api/v1/client; SameSite=Strict
# → Set-Cookie: clubcore_client_csrf=...; Path=/; SameSite=Lax
# → {"data":null}
```

Три cookie сохраняются в `client_cookies.txt`. `clubcore_client_csrf` — не
httpOnly, читается JS и проставляется на mutating запросах (см. § 6).

### 2.3 В PWA

Откройте `http://localhost:5173` (или где запущена client-pwa). На экране логина
введите:
- Телефон: `999 999-99-99` (в поле "+7 ...")
- OTP код: `111111`

PWA вызывает `/otp/request` + `/otp/verify` автоматически.

---

## 3. Read-path walkthrough (live gate — VER-01)

Этот раздел описывает live gate для v2.0: login → home → membership →
book slot → QR check-in → history. Все шаги выполняются с `client_cookies.txt`
из § 2. CSRF нужен только для mutating запросов (POST).

```bash
# Один раз — извлечь CSRF из cookie jar
CSRF=$(awk '$6=="clubcore_client_csrf"{print $7}' client_cookies.txt)
```

### 3.1 GET /home — главная страница клиента

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/home | python3 -m json.tool
# → 200 {"data":{"nextBooking":{...}|null, "activeMembership":{...}|null,
#          "activeVisitsThisWeek":N, ...}}
```

### 3.2 GET /membership — активный абонемент

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/membership | python3 -m json.tool
# → 200 {"data":{"id":"...","planName":"Месяц безлимит",
#          "status":"active","expiresAt":"..."}}
```

Если абонемента нет — `{"data":null}` (D-69-03: empty state → 200 + null).

### 3.3 GET /slots — доступные слоты тренера

```bash
# Указать trainerId + дату (ISO date)
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/slots?trainerId=<trainer_uuid>&date=2026-06-01" \
  | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","startsAt":"...","durationMinutes":60}, ...]}}
```

Слоты нужно создать заранее через staff endpoint
`POST /api/v1/trainer-slots` (см. Postman collection или admin-web).

### 3.4 POST /booking — создание бронирования

Требует активного PT-пакета (§ 1.5). Обязателен `X-CSRF-Token` + `Idempotency-Key`.

```bash
curl -i -s -X POST http://localhost:8000/api/v1/client/booking \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b client_cookies.txt -c client_cookies.txt \
  -d '{"slotId":"<slot_uuid>"}'
# → HTTP/1.1 201 Created
# → {"data":{"id":"<booking_uuid>","status":"confirmed","startsAt":"..."}}
```

### 3.5 GET /qr-token — получить signed QR-токен

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/qr-token | python3 -m json.tool
# → 200 {"data":{"token":"<signed_jwt>","expiresAt":"..."}}
```

Rate limit: 20 req/min per IP (T-70-18).

### 3.6 POST /check-in — QR self check-in

`/check-in` — unauthenticated endpoint; токен из QR является credential'ом (D-70-11).
CSRF не требуется (identity из signed JWT). Требует активного абонемента.

```bash
QR_TOKEN=$(curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/qr-token | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['data']['token'])")

curl -i -s -X POST http://localhost:8000/api/v1/client/check-in \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$QR_TOKEN\"}"
# → HTTP/1.1 201 Created
# → {"data":{"visitId":"<uuid>","checkedInAt":"..."}}
```

Rate limit: 60 req/min per IP (multi-scanner gym tolerance).

### 3.7 GET /history/visits — история посещений

```bash
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/history/visits?page=1&pageSize=20" \
  | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","checkedInAt":"...","visitType":"..."},...],
#          "total":N,"page":1,"pageSize":20}}
```

### 3.8 GET /history/pt-sessions — история PT-сессий

```bash
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/history/pt-sessions?page=1&pageSize=20" \
  | python3 -m json.tool
# → 200 {"data":{"items":[...],"total":N,...}}
```

### 3.9 GET /history/payments — история платежей

```bash
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/history/payments?page=1&pageSize=20" \
  | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","amountKopecks":N,"status":"...","createdAt":"..."},...],
#          "total":N,...}}
```

---

## 4. Дополнительные read endpoints

### 4.1 GET /bookings — список бронирований клиента

```bash
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/bookings?page=1&pageSize=20" \
  | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","status":"confirmed|cancelled",...}],...}}
```

### 4.2 GET /plans — каталог абонементов

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/plans | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","name":"Месяц безлимит",
#          "durationDays":30,"priceKopecks":500000}]}}
```

### 4.3 GET /pt-packages — каталог PT-пакетов

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/pt-packages | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","name":"5 тренировок","sessionCount":5,...}]}}
```

### 4.4 GET /trainers — список тренеров

```bash
curl -s -b client_cookies.txt \
  http://localhost:8000/api/v1/client/trainers | python3 -m json.tool
# → 200 {"data":{"items":[{"id":"...","fullName":"...","isActive":true}]}}
```

---

## 5. ЮKassa checkout — OPERATOR-PENDING

> **ВНИМАНИЕ:** Этот раздел помечен **OPERATOR-PENDING**. Он не может быть
> выполнен без реальных ЮKassa sandbox credentials. Не используйте данные
> из примеров ниже как настоящие. Тестовая карта и тестовый payment_id — только
> для sandbox. Никогда не fabricate webhook payload с несуществующим payment_id.

**Trigger condition:** ЮKassa sandbox credentials готовы (YOOKASSA_SHOP_ID +
`test_`-prefixed YOOKASSA_SECRET_KEY + YOOKASSA_RETURN_URL) **и** `YOOKASSA_SANDBOX=true`
выставлен в `.env`.

### 5.1 Env setup для checkout leg

В `apps/backend/.env`:

```dotenv
YOOKASSA_SANDBOX=true
YOOKASSA_SHOP_ID=<ваш sandbox shop_id>
YOOKASSA_SECRET_KEY=test_<ваш test-ключ>
YOOKASSA_RETURN_URL=http://localhost:5173/checkout/status
```

Перезагрузить backend:

```bash
docker compose up -d --force-recreate backend
```

### 5.2 POST /checkout/memberships/{plan_id} — начать оплату абонемента

```bash
curl -i -s -X POST \
  "http://localhost:8000/api/v1/client/checkout/memberships/<plan_id>" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b client_cookies.txt -c client_cookies.txt \
  -d '{}'
# → 200 {"data":{"paymentId":"<yk_payment_id>","confirmationUrl":"https://yookassa.ru/..."}}
```

### 5.3 Оплата через hosted page

1. Перейдите по `confirmationUrl` в браузере.
2. На платёжной форме ЮKassa введите **тестовую карту `5555 5555 5555 4477`**.
   CVV / дата — произвольные. Это sandbox-карта ЮKassa для успешного платежа.
3. После успешной оплаты ЮKassa перенаправит на `YOOKASSA_RETURN_URL`.

### 5.4 Ручная отправка webhook (manual fire)

ЮKassa webhook `payment.succeeded` (или `payment.waiting_for_capture`) поступает
от ЮKassa серверов. В sandbox доставка происходит автоматически, но для ручной
проверки логики активации абонемента:

```bash
# КРИТИЧНО: используйте РЕАЛЬНЫЙ payment_id из шага 5.2 — никогда не fabricate.
# Пример UUID здесь показан для формата; подставьте свой <yk_payment_id>.
REAL_PAYMENT_ID="<yk_payment_id из ответа checkout>"

curl -i -s -X POST http://localhost:8000/api/v1/_internal/yookassa/webhook \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"notification\",
    \"event\": \"payment.succeeded\",
    \"object\": {
      \"id\": \"$REAL_PAYMENT_ID\",
      \"status\": \"succeeded\",
      \"amount\": {\"value\": \"500.00\", \"currency\": \"RUB\"},
      \"metadata\": {}
    }
  }"
# → 200 {"status":"ok"}
```

> **ВАЖНО:** Endpoint `/api/v1/_internal/yookassa/webhook` не включён в OpenAPI
> schema (`include_in_schema=False`). Это транспортный IP-authenticated callback.
> В sandbox окружении IP allowlist отключён (`YOOKASSA_SANDBOX=true`).

### 5.5 GET /payments/{payment_id}/status — статус платежа

```bash
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/payments/$REAL_PAYMENT_ID/status" \
  | python3 -m json.tool
# → 200 {"data":{"status":"succeeded","membershipActivated":true}}
```

После успешного webhook абонемент должен активироваться:
`GET /api/v1/client/membership` → `{"data":{"status":"active",...}}`.

---

## 6. Session management

### 6.1 Refresh token rotation

```bash
curl -i -s -X POST http://localhost:8000/api/v1/client/session/refresh \
  -b client_cookies.txt -c client_cookies.txt
# → 200
# → Set-Cookie: cc_client_access=...   (новый access token)
# → Set-Cookie: cc_client_refresh=...  (новый refresh token; старый инвалидирован)
# → Set-Cookie: clubcore_client_csrf=... (обновлён)
# → {"data":null}
```

CSRF dep exempt (identity в cookie — D-09). Требует только `cc_client_refresh`.

### 6.2 Logout

```bash
CSRF=$(awk '$6=="clubcore_client_csrf"{print $7}' client_cookies.txt)

curl -i -s -X POST http://localhost:8000/api/v1/client/session/logout \
  -H "X-CSRF-Token: $CSRF" \
  -b client_cookies.txt -c client_cookies.txt
# → 200 {"data":null}
# → Set-Cookie: cc_client_access=; Max-Age=0
# → Set-Cookie: cc_client_refresh=; Max-Age=0
# → Set-Cookie: clubcore_client_csrf=; Max-Age=0
```

---

## 7. CSRF discipline для client endpoints

Клиентские endpoints следуют тому же double-submit CSRF паттерну, что и staff
endpoints, но с отдельными cookie именами.

### 7.1 Cookie имена (v2.0)

| Cookie | Scope | HttpOnly | Назначение |
|--------|-------|----------|------------|
| `cc_client_access` | `Path=/` | да | короткоживущий access JWT (15 мин) |
| `cc_client_refresh` | `Path=/api/v1/client` | да | refresh token для ротации |
| `clubcore_client_csrf` | `Path=/` | **нет** | double-submit CSRF token (JS-readable) |

Нет пересечения со staff cookies (`cc_access`, `cc_refresh`, `clubcore_csrf`).

### 7.2 Извлечение CSRF из cookie jar

```bash
CSRF=$(awk '$6=="clubcore_client_csrf"{print $7}' client_cookies.txt)
```

### 7.3 Какие endpoints требуют CSRF

| Method | CSRF required | Примеры |
|--------|--------------|---------|
| GET / HEAD / OPTIONS | Нет | /home, /membership, /slots, /history/* |
| POST | **Да** | /booking, /session/logout, /checkout/* |
| PATCH | **Да** | /me |
| DELETE | **Да** | (нет в v2.0 client surface) |

Исключение: `POST /check-in` — unauthenticated endpoint (credential = signed QR
JWT), CSRF не имеет смысла (D-70-11). `POST /otp/request`, `POST /otp/verify`,
`POST /session/refresh` — pre-auth / CSRF exempt (D-09).

### 7.4 Пример mutating запроса с полным набором заголовков

```bash
CSRF=$(awk '$6=="clubcore_client_csrf"{print $7}' client_cookies.txt)

curl -i -s -X POST http://localhost:8000/api/v1/client/booking \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b client_cookies.txt -c client_cookies.txt \
  -d '{"slotId":"<slot_uuid>"}'
```

---

## 8. Полный curl quickstart (copy-paste)

Последовательность для нового терминала (предполагает запущенный стек и сиды):

```bash
# 1. OTP login
curl -s -X POST http://localhost:8000/api/v1/client/otp/request \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79999999999"}'

curl -s -X POST http://localhost:8000/api/v1/client/otp/verify \
  -H "Content-Type: application/json" \
  -c client_cookies.txt \
  -d '{"phone":"+79999999999","code":"111111"}'

CSRF=$(awk '$6=="clubcore_client_csrf"{print $7}' client_cookies.txt)

# 2. Read-path
curl -s -b client_cookies.txt http://localhost:8000/api/v1/client/home | python3 -m json.tool
curl -s -b client_cookies.txt http://localhost:8000/api/v1/client/membership | python3 -m json.tool

# 3. Book a slot (needs active PT-package + an open trainer slot)
curl -i -s -X POST http://localhost:8000/api/v1/client/booking \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b client_cookies.txt -c client_cookies.txt \
  -d '{"slotId":"<slot_uuid>"}'

# 4. QR token + check-in
QR_TOKEN=$(curl -s -b client_cookies.txt http://localhost:8000/api/v1/client/qr-token \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

curl -i -s -X POST http://localhost:8000/api/v1/client/check-in \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$QR_TOKEN\"}"

# 5. History
curl -s -b client_cookies.txt \
  "http://localhost:8000/api/v1/client/history/visits?page=1&pageSize=5" | python3 -m json.tool
```

---

## Дальнейшие шаги

- **Full contract:** `apps/backend/openapi.json` (source-of-truth) +
  `packages/api-client/src/schema.d.ts` (TypeScript types; codegen: `pnpm --filter @clubcore/api-client codegen`).
- **Evidence:** `.planning/milestones/v2.0-OPERATOR-EVIDENCE.md` — фиксирует
  live read-path walkthrough (RUN-00) и ЮKassa checkout leg (RUN-01, OPERATOR-PENDING).
- **ЮKassa checkout:** выполнить RUN-01 согласно § 5 данного runbook при наличии
  sandbox credentials (D-72-06 trigger condition).
- **Тесты (host-side):**
  ```bash
  cd apps/backend
  uv run pytest tests/ -x -q
  ```
  pytest не входит в runtime image — запускать на хосте через `uv run`.

## Operator

andre.shipunov@icloud.com
