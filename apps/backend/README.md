# sportzal-backend

Backend для Sportzal — CRM для тренажёрного зала. Модульный монолит на FastAPI 0.115+ (Python 3.12, uv, SQLAlchemy 2.0 async, Alembic, Pydantic v2, Postgres 16, Redis 7, ARQ, structlog). Phase A — каркас; бизнес-фичи лежат в `app.modules.*` как placeholders.

## Quick start

### Вариант 1: локально (требует внешний Postgres + Redis)

```bash
cp .env.example .env
uv sync
uv run uvicorn app.main:create_app --factory
# → http://localhost:8000/healthz
```

Postgres и Redis должны быть запущены отдельно (например, локальные процессы или другой compose stack). `DATABASE_URL` и `REDIS_URL` читаются из `.env`.

### Вариант 2: docker compose (всё включено)

```bash
cp .env.example .env
docker compose up
# → backend на :8000, postgres:16 на :5432, redis:7 на :6379 (внутри compose-сети)
```

Compose поднимает три сервиса (`backend`, `postgres`, `redis`) + one-shot `migrate` (alembic upgrade head). На host доступны `:8000` (backend) и `:5432` (postgres). Redis — только внутри compose-сети.

## Команды

```bash
uv run pytest               # тесты (httpx ASGITransport)
uv run ruff check .          # линтер
uv run ruff format .         # форматирование
uv run mypy app              # type check (strict)
uv run lint-imports          # архитектурные контракты (3 контракта в .importlinter)
uv run alembic upgrade head  # применить миграции (в Phase A — ноль миграций)
```

## Документация

- [`docs/architecture.md`](docs/architecture.md) — модульный монолит, инварианты, диаграмма слоёв.
- [`docs/conventions.md`](docs/conventions.md) — стиль кода, naming, тестирование, миграции.
- [`docs/adr/`](docs/adr/) — каталог ADR (MADR 4.0). Стартовая точка — [`0001-modular-monolith.md`](docs/adr/0001-modular-monolith.md). Шаблон для новых ADR — [`template.md`](docs/adr/template.md).
- [`scripts/`](scripts/) — `seed_demo_data.py` (Phase A placeholder) и `backup_db.sh` (`pg_dump` против compose-network Postgres).
