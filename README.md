# clubcore

CRM для тренажёрного зала: клиенты, абонементы, посещения, расписание, бронирования, тренеры, биллинг и уведомления. Рынок РФ/СНГ — платежи через ЮKassa, основной канал уведомлений Telegram.

Проект развёртывается **локально в Docker**. Инфраструктура для self-hosted k3s присутствует в `infra/`, но в продакшен на данный момент не разворачивается.

---

## Стек

**Backend** — модульный монолит
Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · PostgreSQL 16 · Redis 7 · ARQ · structlog · uv

**Frontend** — две SPA в монорепозитории (pnpm workspaces)
React 19 · Vite · TanStack Router/Query/Table · Zod · Tailwind CSS v4 · shadcn/ui

**Инфраструктура**
Docker Compose (локально) · SeaweedFS (S3-совместимое хранилище) · Helm + k3s + Terraform (заготовка для self-hosted, не задействована)

---

## Структура репозитория

```
apps/
  backend/    FastAPI — модульный монолит, Alembic-миграции, ARQ-воркеры
  admin/      Админ-панель для персонала (React 19)
  client/     Клиентское PWA (React 19)
packages/
  api-client/ Типизированный клиент API (генерируется из OpenAPI)
  ui/         Общие UI-компоненты
infra/        Docker-, Helm-, nginx-, Terraform-артефакты
tools/        Вспомогательные скрипты (Newman, генерация Postman)
```

---

## Архитектура

Backend — **модульный монолит**: единое приложение FastAPI, разбитое на изолированные бизнес-домены (`app/modules/<домен>`) поверх инфраструктурного слоя (`app/core`). Границы между слоями и доменами проверяются `import-linter`. Два независимых принципала аутентификации — персонал (cookies `cc_*`) и клиент (cookies `cc_client_*`), доступ разграничивается RBAC.

Фронтенд — две SPA, обращающиеся к backend через типизированный `api-client`. Локально статика отдаётся nginx, который проксирует `/api` на backend; в k3s ту же роль выполняет ingress.

```mermaid
flowchart TB
    subgraph Users["Пользователи"]
        Staff["Персонал<br/>(браузер)"]
        Cust["Клиент<br/>(браузер / PWA)"]
    end

    subgraph Compose["Docker Compose (локально)"]
        subgraph FE["Frontend — nginx + статика"]
            Admin["admin :5173<br/>React 19 SPA"]
            ClientApp["client :5174<br/>React 19 PWA"]
        end
        Backend["backend :8000<br/>FastAPI — модульный монолит"]
        Arq["arq-worker<br/>периодические задачи"]
        Bot["telegram-bot<br/>long-polling"]
        subgraph Data["Хранилища"]
            PG[("PostgreSQL 16")]
            Redis[("Redis 7")]
            S3[("SeaweedFS · S3")]
        end
    end

    subgraph Ext["Внешние сервисы"]
        YK["ЮKassa<br/>(песочница)"]
        TG["Telegram API"]
    end

    Staff --> Admin
    Cust --> ClientApp
    Admin -- "/api" --> Backend
    ClientApp -- "/api" --> Backend

    Backend --> PG
    Backend --> Redis
    Backend --> S3
    Arq --> PG
    Arq --> Redis
    Bot --> PG

    Backend -- "создание платежа" --> YK
    YK -- "webhook payment.succeeded" --> Backend
    Bot <-->|OTP / уведомления| TG
    Arq -- "напоминания" --> TG
```

### Бизнес-домены (`app/modules`)

| Группа | Модули |
|---|---|
| Доступ и пользователи | `auth`, `client_auth`, `users`, `client_portal` |
| Клиенты и абонементы | `clients`, `memberships`, `pt_packages`, `pt_sessions`, `visits` |
| Расписание | `schedule`, `bookings`, `trainers` |
| Деньги | `payments`, `online_payments`, `online_refunds`, `payment_methods`, `autopay_charges`, `billing`, `fiscal_receipts`, `promo_codes`, `loyalty`, `referrals` |
| Коммуникации | `messaging`, `notifications`, `gym` |
| Отчётность и настройки | `reports`, `payroll`, `settings` |

Сквозные механизмы (`app/core`): аудит-лог всех значимых операций, деньги в копейках (целочисленно), идемпотентность платёжных операций, фоновые задачи и крон через ARQ (Redis), structlog с request-id.

---

## Быстрый старт (локально, всё в Docker)

Требуется Docker.

```bash
docker compose -f apps/backend/docker-compose.yml up -d
```

Команда поднимает весь стек: backend, PostgreSQL, Redis, SeaweedFS (S3), ARQ-воркер, Telegram-бот, а также обе фронтенд-SPA (nginx со статической сборкой и проксированием `/api` на backend).

### Адреса

| Сервис | URL |
|---|---|
| Админ-панель | http://localhost:5173 |
| Клиентское PWA | http://localhost:5174 |
| Backend API | http://localhost:8000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### Первичное наполнение данными

База хранится в именованном volume, поэтому сидирование выполняется один раз:

```bash
COMPOSE="docker compose -f apps/backend/docker-compose.yml"
$COMPOSE cp apps/backend/scripts backend:/app/scripts
$COMPOSE exec -T -w /app -e PYTHONPATH=/app \
  -e SEED_OWNER_EMAIL=owner@clubcore.dev -e SEED_OWNER_PASSWORD=devpassword12345 \
  backend python -m scripts.seed_demo_data
$COMPOSE exec -T -w /app -e PYTHONPATH=/app backend python -m scripts.seed_dev_client
```

### Учётные данные для входа (dev)

| Приложение | Логин | Код / пароль |
|---|---|---|
| Админ-панель | `owner@clubcore.dev` | `devpassword12345` |
| Клиентское PWA | `999 999-99-99` | OTP `111111` |

### Платежи (тестовый контур ЮKassa)

Бэкенд настроен на песочницу ЮKassa (`YOOKASSA_SANDBOX=true`). Тестовая карта для оплаты на hosted-странице: `5555 5555 5555 4477`, любой будущий срок, любой CVC.

---

## Разработка

### Фронтенд

Для разработки с hot-reload фронтенды можно запускать через Vite напрямую (backend при этом остаётся в Docker):

```bash
pnpm -F @clubcore/admin dev     # http://localhost:5173
pnpm -F @clubcore/client dev    # http://localhost:5174
```

После изменений во фронтенде для Docker-варианта образы пересобираются:

```bash
docker compose -f apps/backend/docker-compose.yml build admin client
docker compose -f apps/backend/docker-compose.yml up -d admin client
```

### Backend

Зависимости и инструменты — через `uv`:

```bash
cd apps/backend
uv run ruff check .          # линтинг
uv run mypy app              # строгая типизация
uv run lint-imports          # архитектурные границы (import-linter)
```

Тесты выполняются на хосте (PostgreSQL/Redis должны быть подняты в Docker):

```bash
cd apps/backend
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' \
REDIS_URL='redis://localhost:6379/0' \
uv run pytest
```

> Полный прогон тестов обращается к локальной БД `clubcore` и очищает её — после тестов выполните сидирование заново.

---

## Качество

- `ruff` + `mypy --strict` + `import-linter` обязательны.
- Контрактные тесты сверяют ответы реального backend с Zod-схемами фронтенда.
- OpenAPI-спека фиксируется в CI (drift-gate).

---

## Статус

Функционально полный продукт (админ-панель и клиентское PWA подключены к реальному API). Развёртывание — локальное в Docker. Боевой деплой на инфраструктуру k3s (`infra/`) не выполнялся и в ближайшие планы не входит.
