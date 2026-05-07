# v1.2 Memberships + Visits — Architectural Integration

**Mode:** Project Research — Subsequent Milestone Integration
**Confidence:** HIGH (all claims backed by actual code in repo)

## Executive Summary

v1.2 introduces the first cross-module dependency (Visits → Memberships), the first real ARQ scheduled job, and the second non-trivial Telegram bot command. The existing skeleton already anticipates each of these: the `register_user_loader` Protocol pattern in `app/main.py`, the `HandlerContext` NamedTuple in `app/integrations/telegram/handlers.py`, the `app.workers ⊥ app.modules` documented exception D-06, and `app/core/audit.py` as a cross-cutting emit point all generalize cleanly. **No `.importlinter` rule needs to change** — every new edge either lives inside a module, or routes through the existing `app/main.py` composition root, or extends the existing D-06 worker exception with a parallel D-09/D-10 docstring entry.

The hard part is **not** the import graph — it's payment-of-attention to four specific seams: (1) the membership-validation callback for Visits, (2) ARQ job module placement, (3) bot `/checkin` handler ctx extension, (4) admin-web client-detail composition without `features → features` violation. All four have concrete, validated patterns from v1.1 to mirror.

---

## 1. Visits → Memberships Dependency

**Decision: Option (a) — Protocol callback registered in `app/main.py`, named `register_active_membership_resolver`.**

### Rationale

The other two options fail under scrutiny:
- **Option (b) — shared `core/` helper that queries memberships by ID.** Dead-on-arrival. `app.core` MUST NOT import `app.modules.memberships.models`. The contract `core-not-depend-on-modules` (`.importlinter:5-11`) makes this option a literal contract violation — no docstring exception covers it because the contract is a `forbidden` type, not `independence`.
- **Option (c) — FK-only at DB level + service queries the FK without importing the other module.** Possible but smelly. Visits.service would need to write raw SQL or use SQLAlchemy `Table()` definitions to query `memberships` without importing `memberships.models`. This duplicates schema knowledge, breaks type safety, and gets worse the moment validation needs more than `id, end_date, status, client_id` (e.g. plan name for a 409 message).

Option (a) is **already validated** by `register_user_loader` (see `app/core/dependencies.py:44-61` and `app/main.py:88`). It's the same shape, same boundary, same idempotency guarantee.

### Concrete Wiring

**NEW** `app/core/dependencies.py` (extend, not replace):

```python
class ActiveMembership(Protocol):
    """Structural type for an active membership lookup (visits → memberships)."""
    id: UUID
    client_id: UUID
    end_date: date  # exclusive upper bound; visit valid iff today < end_date
    status: str     # 'active' (others won't be returned by the resolver)


ActiveMembershipResolver = Callable[
    [AsyncSession, UUID],            # (session, client_id)
    Awaitable[ActiveMembership | None],
]

_active_membership_resolver: ActiveMembershipResolver | None = None


def register_active_membership_resolver(resolver: ActiveMembershipResolver) -> None:
    """Composition-root setter — called once by `app.main.create_app`.

    Returns the SINGLE active membership for the client, or None. If a client has
    multiple active memberships (overlapping purchases), the resolver picks the one
    with the latest `end_date` (Memberships service contract — see modules/memberships/service.py).
    """
    global _active_membership_resolver
    _active_membership_resolver = resolver


async def resolve_active_membership(
    session: AsyncSession, client_id: UUID
) -> ActiveMembership | None:
    if _active_membership_resolver is None:
        raise RuntimeError(
            "active_membership_resolver_not_registered — composition root must call "
            "register_active_membership_resolver in create_app()."
        )
    return await _active_membership_resolver(session, client_id)
```

**MODIFIED** `app/main.py`:

```python
from app.core.dependencies import register_active_membership_resolver, register_user_loader
from app.modules.memberships.service import resolve_active_membership_by_client

# inside create_app(), right after register_user_loader(...)
register_active_membership_resolver(resolve_active_membership_by_client)
```

**Visits service consumes via core, not via memberships:**

```python
# app/modules/visits/service.py
from app.core.dependencies import resolve_active_membership

async def create_visit(session, actor, client_id, channel):
    membership = await resolve_active_membership(session, client_id)
    if membership is None:
        raise NoActiveMembershipError("no_active_membership")
    # ... insert Visit row with membership_id=membership.id ...
```

### Why This Doesn't Break `modules-independent`

`app/modules/visits/*` only imports `app.core.dependencies.resolve_active_membership`. It never imports `app.modules.memberships.*`. The `app.main` composition root imports both — but `app.main` is OUT OF SCOPE for both `core-not-depend-on-modules` (which scopes `app.core`) and `modules-independent` (which scopes `app.modules.{auth,clients,...}`). The same exemption that lets `app.main` call `register_user_loader(load_user_by_id)` covers this.

**FK at DB level**: keep the FK `visits.membership_id → memberships.id` — that's a DB schema constraint, not a Python import. Alembic migration declares it as `ForeignKey("memberships.id", ondelete="RESTRICT")` without either module importing the other (FKs in SA are string-referenced, exactly like `audit_log.actor_user_id → users.id` in `core/audit_models.py:39`).

---

## 2. ARQ Scheduled Job Placement

**Decision: `app/workers/scheduled/expire_memberships.py` — under workers, importing `app.modules.memberships.service`. Documented as parallel to D-06.**

### Why Not Inside `modules/memberships/jobs.py`

That would force `app.workers/__init__.py` (the `WorkerSettings` cron list) to import `app.modules.memberships.jobs`. Today `app/workers/__init__.py` does NOT import any module — only the bot worker does, and only with the documented D-06 relaxation. Adding a second import path inside the ARQ settings file would invert the convention.

### Why Workers Importing Modules is OK

The import-linter contract list has only THREE rules (`apps/backend/.importlinter`):
1. `core-not-depend-on-modules` (scopes `app.core`)
2. `modules-independent` (scopes the listed modules)
3. `integrations-not-depend-on-modules` (scopes `app.integrations`)

**There is NO `workers ⊥ modules` contract.** The docstring in `app/workers/__init__.py:1-14` already states:
> "This relaxation is documented-only — no importlinter contract change is required because no current contract enforces `workers ⊥ modules`."

So `app/workers/scheduled/expire_memberships.py → app.modules.memberships.service` is **structurally legal**. We document the convention to keep it bounded:

> **D-09 (v1.2):** A scheduled worker job MAY import the single owning module's service layer when the job IS that module's lifecycle automation (e.g. `expire_memberships.py → app.modules.memberships.service`). Cross-module imports inside one worker job are still forbidden.

### Concrete Files

**NEW** `app/workers/scheduled/__init__.py` — empty namespace marker.

**NEW** `app/workers/scheduled/expire_memberships.py`:

```python
"""Daily ARQ job: flip memberships from active → expired when end_date <= today (D-09).

Per D-09: a scheduled worker MAY import its owning module's service layer; same
narrow exception shape as D-06 for the telegram bot worker.

Run via the ARQ WorkerSettings cron in app/workers/__init__.py.
"""
from datetime import date

from app.core.database import db_lifespan_manager
from app.modules.memberships import service as memberships_service  # D-09 relaxation


async def expire_memberships(ctx: dict) -> int:
    """Idempotent daily expirer. Returns count of newly expired rows."""
    sessionmaker = ctx["sessionmaker"]
    async with sessionmaker() as session:
        count = await memberships_service.expire_due_memberships(session, today=date.today())
        await session.commit()
    return count
```

**MODIFIED** `app/workers/__init__.py` — replace the placeholder docstring section with a real `WorkerSettings`:

```python
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import db_lifespan_manager
from app.workers.scheduled.expire_memberships import expire_memberships


async def startup(ctx):
    db_cm = db_lifespan_manager()
    engine, sessionmaker = await db_cm.__aenter__()
    ctx["db_cm"] = db_cm
    ctx["engine"] = engine
    ctx["sessionmaker"] = sessionmaker


async def shutdown(ctx):
    await ctx["db_cm"].__aexit__(None, None, None)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = startup
    on_shutdown = shutdown
    functions = [expire_memberships]
    cron_jobs = [cron(expire_memberships, hour=3, minute=15)]
```

**MODIFIED** `infra/docker-compose.yml` — add a 5th service:
```yaml
arq-worker:
  build: { context: ../apps/backend }
  command: python -m arq app.workers.WorkerSettings
  depends_on: [postgres, redis, migrate]
  env_file: ../apps/backend/.env
```

---

## 3. Telegram Bot `/checkin` Handler

**Decision: (a) — extend `HandlerContext` to include `visits_service` ModuleType. Add a parallel D-10 to D-06.**

### Why Not (b) Direct Import in `telegram_bot.py`

D-06 currently says `app.workers.telegram_bot` MAY import `app.modules.auth.telegram_service`. The `/checkin` handler runs inside `app.integrations.telegram.handlers` — NOT inside `app.workers.telegram_bot`. The existing handler design (`app/integrations/telegram/handlers.py:29-31`) is explicit:

> `# NOTE: NO from app.modules.auth import ... -- integrations perp modules.`
> `# Domain modules arrive via HandlerContext.`

Handlers receive everything via `HandlerContext` precisely because `integrations-not-depend-on-modules` (`.importlinter:27-33`) is a hard `forbidden` contract. Direct import in handlers.py would BREAK the contract.

### Concrete Files

**MODIFIED** `app/integrations/telegram/handlers.py`:

```python
class HandlerContext(NamedTuple):
    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType   # app.modules.auth.telegram_service (D-06)
    visits_service: ModuleType     # app.modules.visits.service          (D-10, v1.2)
    sender: ModuleType


_DM_CHECKIN_OK = "✅ Отмечено в {gym_name} в {time_msk}."
_DM_NO_MEMBERSHIP = "У вас нет активного абонемента. Обратитесь к администратору."
_DM_DUPLICATE = "Вы уже отмечались сегодня."
_DM_OUTSIDE_HOURS = "Зал сейчас закрыт. Часы работы: {hours}."


async def checkin_handler(update, context, ctx: HandlerContext) -> None:
    """ptb /checkin handler (v1.2). Errors map to the four locked DM strings."""
    bot = context.bot
    if update.effective_user is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    telegram_user_id = update.effective_user.id

    async with ctx.session_factory() as session:
        try:
            visit = await ctx.visits_service.create_visit_self_checkin(
                session, telegram_user_id=telegram_user_id, chat_id=chat_id,
            )
            await session.commit()
        except Exception as exc:
            cls_name = type(exc).__name__
            if cls_name == "NoActiveMembershipError":
                await ctx.sender.send_text_dm(bot, chat_id, _DM_NO_MEMBERSHIP)
            elif cls_name == "DuplicateCheckinError":
                await ctx.sender.send_text_dm(bot, chat_id, _DM_DUPLICATE)
            elif cls_name == "OutsideGymHoursError":
                await ctx.sender.send_text_dm(bot, chat_id, _DM_OUTSIDE_HOURS.format(hours="07:00–23:00"))
            return
        await ctx.sender.send_text_dm(bot, chat_id, _DM_CHECKIN_OK.format(...))
```

**MODIFIED** `app/workers/telegram_bot.py`:

```python
from app.modules.auth import telegram_service       # D-06 relaxation
from app.modules.visits import service as visits_service  # D-10 relaxation (v1.2)

ctx = HandlerContext(
    session_factory=sessionmaker,
    telegram_service=telegram_service,
    visits_service=visits_service,                   # v1.2
    sender=telegram_sender,
)
application = build_application(
    token=settings.telegram_bot_token.get_secret_value(),
    handlers=[("start", start_handler), ("checkin", checkin_handler)],
    ctx=ctx,
)
```

**Anti-fraud lives in `visits.service`**, not in the handler — that way reception manual check-in (router path) and self check-in (bot path) share the same validation.

---

## 4. audit_log Architecture

**Already centralized.** No new wiring needed. New modules write the same way `clients.service` does.

### Verified Locations

- ORM model: `app/core/audit_models.py` — lives in `core` (NOT in any module). FK to `users.id` is a string ref.
- Emitter: `app/core/audit.py:emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)` — async, co-transactional, never commits/flushes (caller owns the txn).
- Locked event-name list: `audit.py:11-29` — modules MUST add new event names to this list.

### v1.2 Emit Calls

`memberships.service` and `visits.service` write to audit identically to `clients.service`:

```python
await audit.emit(
    session, "membership_created",
    actor_user_id=actor.id, resource_type="membership", resource_id=membership.id,
    client_id=str(client_id), plan_id=str(plan_id),
    duration_days=plan.duration_days, price_kopecks=plan.price_kopecks,
)
await session.commit()
```

### New Locked Event Names

```
membership_plan_created   {plan_id, name, duration_days, price_kopecks}
membership_plan_updated   {plan_id, changed_fields}
membership_plan_archived  {plan_id, name}
membership_created        {membership_id, client_id, plan_id, duration_days, price_kopecks_snapshot}
membership_cancelled      {membership_id, client_id, reason?}
membership_expired        {membership_id, client_id}              # actor_user_id=None (job-driven)
visit_created             {visit_id, client_id, membership_id, channel}
visit_rejected_no_membership {client_id, channel}                 # actor_user_id=None for telegram
visit_rejected_duplicate  {client_id, channel}
visit_rejected_outside_hours {client_id, channel}
```

---

## 5. admin-web Client-Detail Composition

**Decision: route component composes; each feature exports `useXxxByClient(clientId)` hooks. Validated pattern, no architectural change.**

A route is allowed to import multiple features simultaneously because the route IS the composition layer, exactly analogous to `app/main.py` on the backend. `routes/_protected/clients.tsx:5-6` already imports both `@/features/clients/api/keys` AND `@/shared/api/services`.

### Concrete Pattern for v1.2

**NEW** `apps/admin-web/src/routes/_protected/clients.$clientId.tsx`:

```typescript
export const Route = createFileRoute('/_protected/clients/$clientId')({
  beforeLoad: ({ context }) => { /* role guard same shape as clients.tsx:14-23 */ },
  loader: async ({ params, context }) => {
    const { clientId } = params
    await Promise.all([
      context.queryClient.ensureQueryData({
        queryKey: clientsKeys.detail(clientId as ClientId),
        queryFn: () => services.clients.get(clientId as ClientId),
      }),
      context.queryClient.ensureQueryData({
        queryKey: membershipsKeys.byClient(clientId as ClientId),
        queryFn: () => services.memberships.listByClient(clientId as ClientId),
      }),
      context.queryClient.ensureQueryData({
        queryKey: visitsKeys.byClient(clientId as ClientId, { limit: 10 }),
        queryFn: () => services.visits.listByClient(clientId as ClientId, { limit: 10 }),
      }),
    ])
  },
  component: ClientDetailPage,
})
```

**Two acceptable patterns; pick Pattern α**:
- **Pattern α (preferred): page component lives in `routes/_protected/clients.$clientId.tsx`, NOT in `features/clients/components/`.** The route component IS the page, composing three feature blocks. Keeps `features/clients` sterile. Closer to the existing `clients.tsx` shape.
- **Pattern β: blocks live in route-private siblings.** Less aligned with current convention.

`MembershipsBlock` and `RecentVisitsBlock` are exported from `features/memberships` and `features/visits` respectively. The ROUTE imports them — never `features/clients` importing them.

---

## 6. New Endpoint Surface and Route Mounting

### Resource & Action Enum Additions

**MODIFIED** `app/core/permissions.py`:

```python
class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"      # ← NEW
    EDIT = "edit"
    DELETE = "delete"
    REFUND = "refund"
    CANCEL = "cancel"      # ← NEW: for membership cancel
    CHECK_IN = "check_in"  # ← NEW: for visits

class Resource(StrEnum):
    DASHBOARD = "dashboard"
    CLIENTS = "clients"
    MEMBERSHIPS = "memberships"          # ← NEW
    MEMBERSHIP_PLANS = "membership-plans" # ← NEW
    VISITS = "visits"                    # ← NEW
    SCHEDULE = "schedule"
    STAFF = "staff"
    FINANCE = "finance"
    REPORTS = "reports"
    PAYROLL = "payroll"
    COMPENSATION = "compensation"
    TEMPLATES = "templates"
    SETTINGS = "settings"
    OWNER_AREA = "owner-area"
```

**Critical:** these values must be **byte-paritetic** with `apps/admin-web/src/shared/session/registry.ts` and `can.ts`. The Phase 6 TEST-06 parity test (`permissions.py:7-9`) FAILS if frontend and backend disagree.

### OWNER_ONLY Additions

```python
OWNER_ONLY = frozenset({
    # ... existing 9 entries ...
    (Action.VIEW, Resource.MEMBERSHIP_PLANS),
    (Action.EDIT, Resource.MEMBERSHIP_PLANS),
    (Action.CREATE, Resource.MEMBERSHIP_PLANS),
    (Action.DELETE, Resource.MEMBERSHIP_PLANS),
    (Action.CANCEL, Resource.MEMBERSHIPS),
    (Action.DELETE, Resource.MEMBERSHIPS),
    # NOTE: VIEW MEMBERSHIPS / VIEW VISITS / CREATE MEMBERSHIPS / CHECK_IN VISITS are NOT
    # — reception can sell memberships and check clients in (PROJECT.md core feature).
})
```

### Endpoint Surface

**Memberships module** — `/api/v1/memberships`:

| Method | Path                          | Permission                          | CSRF | Notes                                              |
|--------|-------------------------------|-------------------------------------|------|----------------------------------------------------|
| GET    | `/memberships`                | VIEW, MEMBERSHIPS                   | —    | List by `?clientId=` filter; paginated envelope    |
| GET    | `/memberships/{id}`           | VIEW, MEMBERSHIPS                   | —    | Single                                             |
| POST   | `/memberships`                | CREATE, MEMBERSHIPS                 | ✓    | Sell — body: clientId, planId. Service snapshots price/duration |
| POST   | `/memberships/{id}/cancel`    | CANCEL, MEMBERSHIPS (→ OWNER only)  | ✓    | Manual cancel, owner-only                          |

**Membership Plans module** — `/api/v1/membership-plans`:

| Method | Path                           | Permission                            | CSRF | Notes                       |
|--------|--------------------------------|---------------------------------------|------|-----------------------------|
| GET    | `/membership-plans`            | VIEW, MEMBERSHIP_PLANS (→ OWNER)      | —    | Catalog list                |
| POST   | `/membership-plans`            | CREATE, MEMBERSHIP_PLANS (→ OWNER)    | ✓    | Create plan                 |
| PATCH  | `/membership-plans/{id}`       | EDIT, MEMBERSHIP_PLANS (→ OWNER)      | ✓    | Update name/price/active    |
| DELETE | `/membership-plans/{id}`       | DELETE, MEMBERSHIP_PLANS (→ OWNER)    | ✓    | Soft delete / archive       |

**Visits module** — `/api/v1/visits`:

| Method | Path                          | Permission                  | CSRF | Notes                                                            |
|--------|-------------------------------|-----------------------------|------|------------------------------------------------------------------|
| GET    | `/visits`                     | VIEW, VISITS                | —    | List, filter by `?clientId=`, `?from=`, `?to=`; paginated        |
| GET    | `/visits/{id}`                | VIEW, VISITS                | —    | Single                                                           |
| POST   | `/visits`                     | CHECK_IN, VISITS            | ✓    | Reception manual check-in. Body: clientId. Service: channel='reception' |

**Note:** bot-driven self check-ins do NOT have an HTTP endpoint — they enter via `visits.service.create_visit_self_checkin(...)` called from the Telegram handler with `channel='telegram_bot'`.

### Route Mounting Order

**MODIFIED** `app/api/v1/router.py`:

```python
v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(membership_plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```

Mount plans BEFORE memberships so the catalog appears first in /docs (cosmetic but stable for byte-stable diff gate). Mount visits last because it's the only consumer of the membership resolver.

---

## 7. Build Order — Phase Sequencing

Eight phases, dependencies marked. Phase numbers illustrative.

| # | Phase | Inputs | Outputs | Blocks |
|---|-------|--------|---------|--------|
| **15** | **Foundations: RBAC enums + parity** | none | New `Action.{CREATE,CANCEL,CHECK_IN}`, `Resource.{MEMBERSHIPS,MEMBERSHIP_PLANS,VISITS}`, `OWNER_ONLY` additions in BOTH `permissions.py` and admin-web `registry.ts`/`can.ts`; TEST-06 parity test extended; no functional code yet | 16, 17, 21 |
| **16** | **Memberships DB schema + plans CRUD backend** | 15 | Alembic 0004: `membership_plans` table; `app/modules/memberships/{models,schemas,repository,service,router}.py` mirroring clients template; `/api/v1/membership-plans` 4 routes; `audit.emit("membership_plan_*", ...)` event names added; tests | 17 |
| **17** | **Membership instances backend (sell + cancel + resolver)** | 16 | Alembic 0005: `memberships` table (id, client_id FK, plan_id FK, duration_days_snapshot, price_kopecks_snapshot, start_date, end_date, status, cancelled_at); `service.create_membership`, `service.cancel_membership`, `service.resolve_active_membership_by_client`; `register_active_membership_resolver` Protocol added to `core/dependencies.py`; `app/main.py` wires the resolver; `/api/v1/memberships` 4 routes; tests | 18, 19, 21 |
| **18** | **ARQ scheduled job: expire_memberships** | 17 | `app/workers/scheduled/expire_memberships.py`; `WorkerSettings` populated; `service.expire_due_memberships(session, today)`; D-09 docstring; new docker-compose `arq-worker` service; tests; `audit.emit("membership_expired", actor_user_id=None, ...)` | 21 |
| **19** | **Visits DB schema + reception check-in backend** | 17 | Alembic 0006: `visits` table (id, client_id FK, membership_id FK, checked_in_at, channel ENUM `reception\|telegram_bot`, checked_in_by FK users; UNIQUE on `(client_id, date(checked_in_at AT TIME ZONE 'Europe/Moscow'))` for the 1/day rule); `app/modules/visits/{models,schemas,repository,service,router}.py`; `service.create_visit_reception(...)` calling `core.dependencies.resolve_active_membership`; anti-fraud (gym hours via Settings); `/api/v1/visits` 3 routes; tests | 20, 21 |
| **20** | **Telegram bot `/checkin` handler** | 19 | `HandlerContext` extended with `visits_service`; `checkin_handler` in `handlers.py`; `telegram_bot.py` registers second handler + adds D-10 import; `service.create_visit_self_checkin(session, telegram_user_id, chat_id)`; locked Russian DM strings; tests with stubbed bot context | 21 |
| **21** | **OpenAPI drift gate refresh + api-client codegen** | 16, 17, 19 | `apps/backend/openapi.json` updated; `pnpm --filter @sportzal/api-client codegen` → `schema.d.ts`; both files committed; CI green | 22, 23 |
| **22** | **admin-web wiring: memberships + visits** | 21 | New `features/memberships`, `features/visits`; new routes `/_protected/memberships.tsx`, `/_protected/membership-plans.tsx` (owner-only via `beforeLoad`), `/_protected/visits.tsx`; client-detail route `/_protected/clients.$clientId.tsx` with parallel `ensureQueryData`; `services.memberships`/`services.visits` swap-seam (mock + http); ESLint passes | 23 |
| **23** | **Hygiene + v1.1 carryover (CR-01/CR-02)** | none (parallel-eligible) | Phase 04 CR-01 (Argon2 verify-error → 401) + CR-02 (invalid UUID in cookie → 401); active sessions UI + revoke; cleanup | — |

### Critical Path

```
15 → 16 → 17 → 18
              ↘
               19 → 20 → 21 → 22
              ↗
17 ────────────
```

- **15 must finish first** because it changes the RBAC contract that 16/17/19 all depend on.
- **18 and 19 are parallelizable after 17**.
- **20 must wait for 19**.
- **21 cannot start until 16+17+19 are merged** — OpenAPI drift gate is byte-stable.
- **22 cannot start until 21**.
- **23 is independent** — can run in parallel with any of 16–22.

### Import-Linter Implications Summary

| New edge | Source → Target | Contract impact | Resolution |
|----------|----------------|-----------------|------------|
| `app.main → app.modules.memberships.service` | (composition root) | None — `app.main` already exempt | Document in `main.py` docstring alongside D-15 |
| `app.modules.visits.service → app.core.dependencies.resolve_active_membership` | core function | None — modules MAY import core | OK |
| `app.modules.visits.models.Visit` FK to `memberships.id` | DB constraint | None — string FK ref | OK |
| `app.workers.scheduled.expire_memberships → app.modules.memberships.service` | worker → module | None — no `workers ⊥ modules` contract | Document as D-09 |
| `app.workers.telegram_bot → app.modules.visits.service` | worker → module | None | Document as D-10 (parallel to D-06) |
| `app.integrations.telegram.handlers → app.modules.visits.service` | **WOULD VIOLATE** `integrations-not-depend-on-modules` | **Forbidden** | NOT done — visits_service arrives via HandlerContext |
| `app.modules.memberships → app.modules.visits` (or vice versa) | **WOULD VIOLATE** `modules-independent` | **Forbidden** | NOT done — cross-module via Protocol callback in core, registered in main |

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Cross-module callback pattern (Q1) | HIGH | Direct mirror of validated `register_user_loader` |
| ARQ job placement (Q2) | HIGH | `workers/__init__.py:1-15` explicitly says no `workers ⊥ modules` contract exists |
| Bot `/checkin` ctx extension (Q3) | HIGH | `HandlerContext` is a NamedTuple already designed for extension |
| audit_log scaling (Q4) | HIGH | `audit.py` is pure stateless; pattern verified in `clients/service.py:130-141` |
| admin-web composition (Q5) | MEDIUM | Pattern α sound; haven't read `eslint.config.js` to confirm `features → features` ban — flagging for verification during phase 22 plan |
| Endpoint surface + RBAC parity (Q6) | HIGH | TEST-06 enforces FE↔BE parity |
| Build order (Q7) | HIGH | Dependency chain falls out of file-level inspection |

## Open Questions / Flags for Plan Authors

1. **`Action.CREATE` vs reusing `Action.EDIT`.** Lean toward introducing `CREATE` and `CANCEL` as new enum values (parity changes needed both sides). Decide in Phase 15 plan.
2. **Anti-fraud `gym_open_hour` / `gym_close_hour` config.** Lean toward `Settings` env-config so they're tunable per deploy. Phase 19 plan.
3. **Membership "active" definition under multiple overlapping purchases.** Resolver returns ONE — pick the one with latest `end_date`. Document in Phase 17 plan.
4. **ARQ job timezone.** `cron(hour=3, minute=15)` — confirm UTC vs Europe/Moscow. Phase 18 plan.
5. **Pattern α vs β for admin-web client-detail.** Confirm `eslint.config.js` rules in Phase 22 plan.
