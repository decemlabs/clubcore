# Stack Research — v1.2 Memberships + Visits

**Domain:** Backend modular monolith (FastAPI) — adds `memberships` + `visits` modules, first real ARQ scheduled job, second Telegram bot command.
**Researched:** 2026-05-07
**Confidence:** HIGH (verified against Context7 `/python-arq/arq` v0.26.3 and `/python-telegram-bot/python-telegram-bot` v22.5; cross-checked against in-repo handler/worker code that already implements the relevant patterns)

---

## TL;DR

**No new runtime dependencies are required for v1.2.** Every capability the milestone needs is already covered by the locked stack:

- **ARQ daily `expire_memberships`** — `arq>=0.26` ships `arq.cron` with hour/minute/weekday selectors and per-cron `unique=True`, `job_id=...`, `run_at_startup=...`. The existing `WorkerSettings` skeleton in `app/workers/arq_app.py` plugs straight in.
- **`/checkin` Telegram command** — `app/integrations/telegram/bot.py:build_application` already accepts `handlers: list[tuple[str, HandlerCallable]]` and is wired via `[("start", start_handler)]`. Adding `("checkin", checkin_handler)` to the list in `app/workers/telegram_bot.py:main()` is the entire integration. The DM reply uses `update.message.reply_text(...)` — the same `python-telegram-bot>=22.7,<23` API surface already in use.
- **Membership lifecycle (`active → expired → cancelled`)** — three terminal states with deterministic transitions (date-driven expiry + manual cancel only; no fork-join, no retries, no parallel branches). A `state_machine` library would add ceremony and a runtime dependency without removing any logic that currently lives in three lines of SQL/Python. **Recommendation: keep status as a plain Postgres enum + `WHERE end_date <= now() AND status='active'` UPDATE — no library.**
- **Visit anti-fraud** (gym-hours window + 1/day/client) — pure SQL: a partial unique index `UNIQUE (client_id) WHERE date_trunc('day', checked_in_at AT TIME ZONE 'Europe/Moscow') = current_date` is overkill; simpler is a checked_in_at-day partial unique on `(client_id, (checked_in_at::date AT TIME ZONE 'Europe/Moscow'))` plus an in-service `BETWEEN gym_open AND gym_close` check pulled from `app/core/config.py`. **No anti-fraud library justified at this scale.**
- **Date/time** — stdlib `datetime` + `zoneinfo` (Python 3.12 stdlib, `Europe/Moscow` already implied by frontend convention) is sufficient. No `pendulum`, no `arrow`, no `pytz`.

The only **dev-group** addition worth weighing is `freezegun` or `time-machine` for testing the daily expiry cron + the gym-hours window edge cases — and even that is optional, because the existing test suite (`test_security.py`, `test_telegram_verify_errors.py`) already mocks time by mutating row fields (`row.expires_at = datetime.now(tz=UTC) - timedelta(seconds=1)`). Verdict below.

---

## Recommended Stack (Additions Only)

### Core Technologies — NEW DEPENDENCIES

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| _none_ | — | — | All v1.2 capabilities are covered by the locked v1.1 stack. See "Existing Stack — How v1.2 Uses It" below. |

### Dev-Group Additions (Optional, Low Priority)

| Tool | Version Pin | Purpose | When Justified |
|------|-------------|---------|----------------|
| `time-machine` | `>=2.16,<3` | Mock `datetime.now()` / `time.time()` in pytest. C-extension, faster than `freezegun`, async-safe (no thread-local pitfalls). | If `expire_memberships` cron tests or gym-hours-window tests grow brittle from row-mutation patterns. **Defer until first test pain point.** Not added in v1.2 unless a test forces it. |

**Why `time-machine` over `freezegun`** (if it's added later): freezegun patches Python-level globals and has known async/`pytest-asyncio` interaction quirks; `time-machine` patches at the C level and works cleanly with async test loops. The existing test convention (mutate row timestamps directly) avoids the question entirely for most cases.

---

## Existing Stack — How v1.2 Uses It

### `arq>=0.26` — First Real Cron Job (`expire_memberships`)

`arq` 0.26 ships first-class cron support via `arq.cron.cron()`. Verified against Context7 `/python-arq/arq` v0.26.3.

**Pattern for `app/workers/arq_app.py`:**

```python
from arq import cron
from arq.connections import RedisSettings
from typing import ClassVar, Any

from app.core.config import get_settings
from app.workers.tasks.memberships import expire_memberships  # NEW in v1.2

class WorkerSettings:
    functions: ClassVar[list[Any]] = []
    cron_jobs: ClassVar[list[Any]] = [
        cron(
            expire_memberships,
            hour=3,            # 03:05 UTC == 06:05 Europe/Moscow
            minute=5,
            unique=True,       # only one worker runs it per scheduled tick
            job_id="memberships:expire-daily",  # idempotent; surfaces in audit
            timeout=300,
        ),
    ]
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
```

**Notes:**
- `cron()` defaults `second=0` and `microsecond=0`, so omitting them is correct (avoids unintended high-frequency re-runs).
- `unique=True` plus a stable `job_id` is the standard idiom for "run exactly once per scheduled tick across N workers" — required because docker-compose may eventually scale the ARQ service.
- The job itself opens a fresh DB session via `db_lifespan_manager()` in `on_startup`, mirroring the telegram_bot worker pattern.
- **No new dependency.** The placeholder `app/workers/scheduler.py` should be deleted (its TODO is now fulfilled by `cron_jobs` directly on `WorkerSettings`); the file currently misleads by suggesting APScheduler is on the table.

**Do NOT add APScheduler.** It is a separate scheduler with its own job store, conflicts with ARQ's Redis-based persistence, and would split scheduled-job operability across two systems. ARQ's `cron_jobs` is sufficient and already locked.

### `python-telegram-bot>=22.7,<23` — `/checkin` Command Extension

The existing `build_application()` factory in `app/integrations/telegram/bot.py` already supports a list of commands. Verified against Context7 `/python-telegram-bot/python-telegram-bot` v22.5: `CommandHandler` accepts a single command string OR a list — and the codebase already uses the loop-with-default-arg pattern that avoids late-binding bugs.

**Pattern for `app/workers/telegram_bot.py:main()`:**

```python
from app.integrations.telegram.handlers import (
    HandlerContext,
    start_handler,
    checkin_handler,  # NEW in v1.2
)

# ... inside main(), after building HandlerContext:
application = build_application(
    token=settings.telegram_bot_token.get_secret_value(),
    handlers=[
        ("start", start_handler),
        ("checkin", checkin_handler),  # +1 line
    ],
    ctx=ctx,
)
```

**Notes:**
- The `checkin_handler` reuses `ctx.session_factory` for DB access. Per the existing `integrations ⊥ modules` import-linter contract (with the D-06 relaxation), the handler MUST go through a `ctx.visits_service` ModuleType passed in — analogous to how `telegram_service` is threaded today. This means `HandlerContext` gets a new optional field (`visits_service: ModuleType | None = None`) or — preferred — `HandlerContext` becomes generic over the modules each command needs and a small protocol describes the surface. **Decision deferred to architecture phase**, but no library is needed either way.
- DM reply uses `await update.message.reply_text("✅ Отмечено • <plan_name> • до <end_date>")` — straight ptb-22 API.
- Anti-fraud (gym-hours window + 1/day) is enforced **bot-side AND server-side**: bot-side fails fast with a Russian DM ("Сейчас зал закрыт" / "Уже отмечались сегодня"); server-side returns 409 from `POST /api/v1/visits` when reception triggers the same conflict from admin-web. The pattern matches the existing `/start <token>` handler's defensive style.
- **No new ptb-22 features needed.** v22.x has been stable since Feb 2025; no breaking changes in the `CommandHandler` / `Application.builder()` surface.

### Postgres 16 + SQLAlchemy 2.0 — Membership Lifecycle as Plain SQL

**Recommendation: keep status as a plain Postgres enum (`active | expired | cancelled`).** No state-machine library.

**Rationale (from a state-machine design perspective):**

| State Machine Concern | v1.2 Membership Reality |
|-----------------------|-------------------------|
| Number of states | 3 (active, expired, cancelled) |
| Number of transitions | 2 (`active→expired` automatic; `active→cancelled` manual) |
| Branching / conditional transitions | None |
| Side-effects on transition | Audit log emit (already has `audit_emit()` in `app/core/audit.py`) |
| Re-activation | Out of scope (see PROJECT.md "no freeze") |
| Concurrency / optimistic locking | A daily cron + occasional manual cancel — collision is a single `UPDATE ... WHERE status='active'` away |

A library like `transitions` or `python-statemachine` would add:
- A new runtime dependency
- A new `mypy` plugin or type-stub gap
- A new way to model state that diverges from the SQLAlchemy model the rest of the codebase uses
- A second source of truth for "is this active?" that has to stay in sync with the DB

For 3 states and 2 transitions, the cost/benefit is **strongly negative.** The existing `clients` module's soft-delete + status-as-column approach is the established pattern; `memberships` follows it.

**Plain-SQL implementation sketch:**

```python
# app/workers/tasks/memberships.py — the cron job body
async def expire_memberships(ctx: dict) -> int:
    async with db_session_factory() as session:
        stmt = (
            update(Membership)
            .where(
                Membership.status == MembershipStatus.ACTIVE,
                Membership.end_date <= func.current_date(),
            )
            .values(status=MembershipStatus.EXPIRED)
            .returning(Membership.id)
        )
        result = await session.execute(stmt)
        expired_ids = [row.id for row in result]
        for mid in expired_ids:
            await audit_emit(session, "membership_expired", resource_type="membership", resource_id=str(mid))
        await session.commit()
        return len(expired_ids)
```

That is the entire lifecycle engine. No library.

### Visit Anti-Fraud — Plain SQL, No Heuristics Library

| Anti-Fraud Rule | Enforcement Mechanism |
|-----------------|----------------------|
| Gym hours window (env-config `GYM_OPEN_HOUR`/`GYM_CLOSE_HOUR`, e.g. 06:00–23:00 Europe/Moscow) | In-service guard in `visits/service.py`: `if not (open_h <= local_now.hour < close_h): raise VisitOutsideHours()` → 409 |
| Max 1 check-in per day per client | Partial unique index on `visits` table: `UNIQUE (client_id, (checked_in_at AT TIME ZONE 'Europe/Moscow')::date)`; service catches `IntegrityError` → 409 `visit_already_today` |
| Active membership required | `service.py` query: `WHERE membership.status='active' AND now() BETWEEN start_date AND end_date` — 409 `no_active_membership` if none |

This is the same defense-in-depth pattern v1.1 used for `clients.phone` (partial unique index `WHERE deleted_at IS NULL` + service-level check + DB-level catch). **No anti-fraud library** (no `python-fraud-detection`, no `presidio`, no rate-limiter beyond the existing `rate_limit_login`) is justified for a single-gym pet project. ML/heuristic anti-fraud is out of scope per PROJECT.md.

### `pydantic>=2.11,<3` — Schemas (No Plugins Needed)

`MembershipPlan`, `Membership`, `Visit`, `VisitCreate` schemas are all standard Pydantic v2 models. They inherit the project-wide `alias_generator=to_camel` + `populate_by_name=True` from `app/core/schemas.py`. Money is `int` (kopecks); dates use `date | datetime`; status is a `StrEnum` mirrored from the DB enum.

**No Pydantic plugin** (no `pydantic-extra-types` for phone/etc.) is needed beyond what v1.1 already uses. `email-validator>=2.0` is already in deps. E.164 phone validation lives in `clients/schemas.py` and is not duplicated by memberships/visits.

### `structlog>=24.0` + `audit_emit()` — Already Wired

Every state transition (membership purchase, manual cancel, cron expiry, visit check-in via reception OR Telegram) writes to `audit_log` via the existing `app/core/audit.py:emit()`. No new logging library. No new audit primitive.

---

## Installation

**No `uv add` invocations required for v1.2.**

If `time-machine` becomes necessary during testing (low likelihood, defer until needed):

```bash
cd apps/backend
uv add --group dev "time-machine>=2.16,<3"
```

That is the only conceivable v1.2 dependency edit. The PR introducing it must be justified by a specific test that the row-mutation pattern cannot express cleanly.

---

## Alternatives Considered

| Recommended | Alternative | Why Not (for v1.2) |
|-------------|-------------|--------------------|
| `arq.cron` for `expire_memberships` | **APScheduler** | Separate scheduler with its own job store; conflicts with ARQ's Redis-based persistence; splits "what scheduled jobs run on this system" across two systems. ARQ already locked. |
| `arq.cron` for `expire_memberships` | **Postgres `pg_cron` extension** | Requires installing a PG extension on every dev machine + CI Postgres image; moves scheduling out of the application code where it can be tested. ARQ's Python cron is in-process, easier to reason about, easier to test (`time-machine` if needed). |
| `arq.cron` for `expire_memberships` | **Linux cron + `python -m app.cli expire`** | Adds a host-level moving part outside the docker-compose surface; harder to operate; nothing inside ARQ that's blocking us. |
| Plain status enum + SQL UPDATE | **`transitions`** library | 3 states, 2 transitions, no fork-join — library overhead exceeds the logic it would replace. |
| Plain status enum + SQL UPDATE | **`python-statemachine`** | Same reasoning — DSL ceremony for nothing. Would also fight with SQLAlchemy ORM as the source of truth. |
| Stdlib `datetime` + `zoneinfo` | **`pendulum`** | Adds a runtime dep for ergonomics that don't justify it; Python 3.12's `zoneinfo` is sufficient for `Europe/Moscow` boundary math. |
| Stdlib `datetime` + `zoneinfo` | **`arrow`** | Same; ergonomic API for date manipulation with no algorithmic advantage. |
| Partial unique index for "1 visit/day/client" | **In-service Redis SETNX** | Two sources of truth (Redis + Postgres); Postgres unique index is atomic and crash-safe; Redis adds an extra failure mode. |
| Existing test row-mutation pattern | **`time-machine` from day one** | New dep without a forcing function; tests so far don't need it. Add reactively. |
| Existing test row-mutation pattern | **`freezegun`** | Slower (Python-level patching), known async-test quirks; if time mocking is needed, `time-machine` is the better choice. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `transitions` / `python-statemachine` | 3-state lifecycle does not justify a state-machine framework; adds a runtime dep, type-stub gap, and a second source of truth for status. | Postgres enum + `UPDATE ... WHERE status='active' AND end_date <= current_date` |
| **APScheduler** | Conflicts with ARQ's job store; doubles the operational surface for scheduling. | `arq.cron.cron(...)` in `WorkerSettings.cron_jobs` |
| **`pg_cron` extension** | Per-environment DB extension install; moves scheduling out of the app where it can be tested with `time-machine`. | `arq.cron` |
| **`aiogram`** | Already rejected in v1.1 in favor of `python-telegram-bot`; no reason to revisit for one extra command. The ptb-22 `CommandHandler` list pattern handles this trivially. | Append `("checkin", checkin_handler)` to the existing handlers list |
| **`pendulum` / `arrow`** | Nothing in v1.2's date arithmetic exceeds what `datetime` + `zoneinfo` (Python 3.12 stdlib) handles. Adds a runtime dep for marginal ergonomics. | Stdlib `datetime` + `zoneinfo.ZoneInfo("Europe/Moscow")` |
| **Anti-fraud heuristic libraries** (`presidio`, `python-fraud-detection`, ML packages) | Out of scope per PROJECT.md ("simple time-based абонементы"); single-gym pet project; ML anti-fraud is a billing concern, not a check-in concern. | Plain SQL: gym-hours guard + partial unique index |
| **Rate-limit libraries beyond what's already in core** (`slowapi`, `aiolimiter`, etc.) | Existing `rate_limit_login` infrastructure handles login throttling; the 1-per-day-per-client visit rule is a uniqueness constraint, not a rate limit. | Partial unique index on `visits(client_id, day)` |
| **`Casbin` / policy DSLs** | Already rejected in v1.1; RBAC is the existing `Role`/`Action`/`Resource` StrEnum + `OWNER_ONLY` frozenset, which v1.2 will extend with new `(Action, Resource)` pairs for memberships/visits. | Add new entries to `OWNER_ONLY` + parity test |
| **`passlib` / `python-jose`** | Already rejected in v1.1 in favor of `argon2-cffi` + `pyjwt`. v1.2 introduces no new password/JWT surface. | (n/a) |
| **`python-dateutil`** | Stdlib `datetime` + `zoneinfo` handles every v1.2 case (no recurring-RRULE needs since cron lives in ARQ). | Stdlib only |

---

## Stack Patterns by Variant

**If the gym ever opens a second branch (multi-tenant):**
- Memberships and visits will need a `gym_id`/`tenant_id` column.
- `expire_memberships` cron stays single-job; UPDATE just covers all tenants.
- `Europe/Moscow` becomes per-tenant config, not env-global.
- **Out of scope for v1.2 per PROJECT.md.**

**If `/checkin` ever needs argument parsing (e.g. `/checkin <gym-name>`):**
- ptb-22 `context.args` already provides the parsed list (verified in Context7 docs).
- No library change.

**If membership freeze/pause arrives in v1.3+:**
- Adds states `frozen`, transitions `active→frozen→active`. 5 states, 4 transitions — still does not cross the line into needing a state-machine library, but this is the threshold to revisit.

**If notifications "expiring soon" land in v1.3+:**
- A second daily cron (`notify_expiring_soon`) joins `WorkerSettings.cron_jobs`. Same pattern. No new dep.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `arq>=0.26` | `redis>=5,<6` | ARQ 0.26 supports `redis-py` v5; both already locked. |
| `arq>=0.26` | Python 3.12 | Verified — ARQ 0.26.3 ships Python 3.12 wheels. |
| `arq.cron` | `WorkerSettings.cron_jobs` | Class attribute; takes a list of `cron()` results. Stable API since 0.20+. |
| `python-telegram-bot>=22.7,<23` | `Application.builder()` + `CommandHandler` list pattern | Verified — `CommandHandler` accepts a single command or list; existing `bot.py` uses single-command-per-handler with a per-iteration adapter, which is the safer pattern (preserves per-command logging/error handling). |
| `python-telegram-bot 22.x` | `python-telegram-bot 23.x` (future) | v23 is not yet released; staying on `<23` keeps the 22.x major's documented API guarantees. |
| `sqlalchemy>=2.0` | Postgres `daterange` types | Native SQLAlchemy 2.0 typing supports daterange via `psycopg`/`asyncpg` — but v1.2 doesn't need range types (start_date + end_date scalar columns + `BETWEEN` is simpler and matches PG enum + index conventions already in use). |
| `pydantic>=2.11,<3` | `StrEnum` for `MembershipStatus`, `VisitChannel` | Native — no plugin. |
| `time-machine` (if added) | `pytest-asyncio>=0.23` | Compatible; uses C-level patching, async-safe. |

---

## Integration Considerations

### Import-linter contracts — no changes

- `core ⊥ modules` — memberships/visits live under `modules/`, untouched.
- `modules independent` — visits MUST NOT import memberships directly. Either:
  1. Cross-module Protocol registration in `app/main.py` composition root (mirrors the `register_user_loader` pattern from v1.1 Phase 4–7), OR
  2. The "active membership lookup" goes through a thin `core/` helper that both modules consume.
  - **Decision deferred to architecture phase**, but neither path requires a library.
- `integrations ⊥ modules` — D-06 relaxation already covers `workers/telegram_bot.py` importing a single owning module's service. v1.2 either:
  1. Extends D-06 to allow `visits.service` import in the bot worker (analogous to `auth.telegram_service`), OR
  2. Threads `visits_service` through `HandlerContext` and the bot worker remains pure-routing.
  - Option 2 is more consistent with the established pattern.

### `mypy --strict` — no changes

Every recommendation here uses already-typed packages. No `# type: ignore` strategy needed beyond what v1.1 already established. The `pydantic.mypy` plugin handles new schemas without extra config.

### `ruff` — no changes

No new lint rules needed. The existing `S105` placeholder noqa pattern in `telegram_bot.py` may need to repeat for any new placeholder constants in `checkin_handler` (e.g. localized reply strings); these are unit-level decisions.

### Alembic — one new migration

`memberships_plans`, `memberships`, `visits` tables + indexes (partial unique on `visits(client_id, day)`, plain index on `memberships(status, end_date)` for the cron's `WHERE` clause). No new migration tooling.

### Docker-compose — one updated service

The `web`/`migrate`/`postgres`/`redis`/`telegram-bot` topology is unchanged. The ARQ cron now needs an actual worker process — either:
1. Add a 5th compose service `arq` running `uv run arq app.workers.arq_app.WorkerSettings`, OR
2. Run ARQ in-process inside the FastAPI container under a supervisor.
  - **Option 1 is cleaner** and matches the bot-worker-as-separate-process precedent. No new dependency; just compose plumbing.

---

## Sources

- **Context7 `/python-arq/arq`** v0.26.3 — verified `cron()` API (hour/minute/weekday/run_at_startup/unique/job_id/timeout); verified `cron_jobs` is a `WorkerSettings` class attribute; verified `enqueue_job` deferred-execution patterns. **HIGH confidence.**
- **Context7 `/python-telegram-bot/python-telegram-bot`** v22.5 — verified `CommandHandler` accepts list of commands; verified `application.add_handler(CommandHandler(name, callback))` pattern; verified `update.message.reply_text` and `context.args` API. **HIGH confidence.**
- **In-repo `apps/backend/app/integrations/telegram/bot.py:43-82`** — confirmed the `handlers: list[tuple[str, HandlerCallable]]` factory pattern is already in production for v1.1 `/start`; adding `/checkin` is a one-line append. **HIGH confidence (direct read).**
- **In-repo `apps/backend/app/workers/arq_app.py`** — confirmed `WorkerSettings` skeleton already imports `RedisSettings` and exposes `functions` as `ClassVar[list[Any]]`; adding `cron_jobs` as a parallel `ClassVar[list[Any]]` is the documented arq pattern. **HIGH confidence (direct read).**
- **In-repo `apps/backend/pyproject.toml`** — confirmed locked deps cover the v1.2 surface; no version bumps required. **HIGH confidence (direct read).**
- **In-repo `apps/backend/app/modules/clients/repository.py`** — confirmed datetime conventions (`from datetime import UTC, datetime`; `datetime.now(tz=UTC)`); v1.2 follows the same convention without `pendulum`/`arrow`. **HIGH confidence (direct read).**
- **PROJECT.md "Out of Scope"** — Stripe/multi-tenant/ML-anti-fraud explicitly out; informs the "no Casbin / no fraud lib / no daterange engine" verdicts. **HIGH confidence (direct read).**

---

*Stack research for: Sportzal v1.2 — Memberships + Visits backend modules*
*Researched: 2026-05-07*
*Verdict: zero new runtime dependencies; one optional dev-group dep (`time-machine`) deferred until a test forces it.*
