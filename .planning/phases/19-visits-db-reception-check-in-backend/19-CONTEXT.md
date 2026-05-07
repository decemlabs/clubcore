# Phase 19: Visits — DB + reception check-in (backend) - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Mode:** `--auto` — Claude selected recommended option for every gray area; defaults logged inline as `CD-NN` (Claude's Discretion). User overrides at plan-phase review.

<domain>
## Phase Boundary

Phase 19 ships the **`visits` table + reception manual check-in HTTP surface + the shared anti-fraud chain that Phase 20's Telegram bot `/checkin` will reuse**. Until this phase, `app/modules/visits/` is an empty `__init__.py` placeholder from Phase A — there is no Visit ORM, no migration 0006, no router, no service. After this phase, the modular monolith owns the third business surface (clients → memberships → visits) plus the cross-module `(Action.CHECK_IN, Resource.VISITS)` RBAC pair (locked Phase 15 INFRA-08), the four `visit_*` audit events (locked Phase 15 INFRA-11), and the race-proof `(client_id, gym_date) UNIQUE` 1/day rule that Pitfall 5 calls out as the single most important DB-level invariant in v1.2.

In scope:
- **NEW** `apps/backend/alembic/versions/0006_visits.py` — creates the `visits` table per VIS-01 verbatim:
  - Columns: `id` UUID PK gen_random_uuid(), `client_id` UUID NOT NULL FK clients.id ON DELETE RESTRICT, `membership_id` UUID NOT NULL FK memberships.id ON DELETE RESTRICT, `checked_in_at` TIMESTAMPTZ NOT NULL DEFAULT now(), `gym_date` DATE NOT NULL **GENERATED ALWAYS AS `((checked_in_at AT TIME ZONE 'Europe/Moscow')::date)` STORED**, `channel` VARCHAR(16) NOT NULL CHECK IN ('reception','telegram_bot'), `checked_in_by` UUID NULL FK users.id ON DELETE SET NULL, `created_at` TIMESTAMPTZ NOT NULL DEFAULT now().
  - **UNIQUE INDEX `uq_visits_client_id_gym_date` on `(client_id, gym_date)`** — unconditional (no `WHERE deleted_at IS NULL`; visits are immutable history, no soft-delete column per CD-04).
  - Composite index `ix_visits_client_id_checked_in_at` on `(client_id, checked_in_at DESC)` for the per-client history feed (VIS-EP-01).
  - The CHECK constraint name (`ck_visits_channel`) and the UNIQUE INDEX name (`uq_visits_client_id_gym_date`) are literal-ref'd by `service.py:_is_duplicate_visit_conflict` — the migration name and the service helper string MUST match.
  - The GENERATED column is installed via `op.execute("CREATE TABLE …")` raw SQL OR `sa.Column(..., sa.Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True))` — the planner picks one in `19-01-PLAN.md`; the SA `Computed` form is the autogen-friendly path. Tested on real Postgres 16 via `test_alembic_clean.py`-style integration check (Pitfall 5 #1 + Pitfall research note "test the migration on real Postgres 16, not just SQLite").
- **NEW** `app/modules/visits/models.py` — `Visit` ORM (Base + UUIDPkMixin + TimestampMixin; **NO** SoftDeleteMixin per CD-04) with all VIS-01 columns + `__table_args__` mirroring the migration. The `gym_date` column is mapped as `Mapped[date]` with `Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)` so SA's autogenerate stays in sync.
- **NEW** `app/modules/visits/schemas.py` — `BackendSchemaBase` subclasses (Phase 15 INFRA-12 contract: `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra='forbid'`):
  - `VisitCreateRequest` — `{ clientId: UUID }` only. Every other field (membershipId, checkedInAt, gymDate, channel, checkedInBy) is server-derived per VIS-EP-03 + D-01 (sealed reception API).
  - `VisitResponse` — `id, clientId, membershipId, checkedInAt, gymDate, channel, checkedInBy, createdAt`. `from_attributes=True`.
  - `VisitListQuery` — `clientId: UUID | None`, `from: date | None`, `to: date | None`, `page` / `pageSize` from `PageQuery`. `from <= gym_date <= to` semantics inclusive on both bounds (CD-08).
  - No `VisitListSort` enum — server enforces fixed `checked_in_at DESC` order (D-09).
- **NEW** `app/modules/visits/repository.py` — module-level async helpers; **single point of access to the `Visit` ORM** (mirror of clients/memberships repository contract; the service never executes `select(Visit)` directly):
  - `get(session, visit_id) -> Visit | None`
  - `list_by_query(session, query) -> PaginatedData[Visit]` — applies `client_id`/`from`/`to` filters; default sort `checked_in_at DESC`; pagination via `PageQuery`.
  - `create(session, *, client_id, membership_id, channel, checked_in_by) -> Visit` — inserts; service awaits `flush()` and translates `IntegrityError` per D-08.
  - **NO ILIKE search** in v1.2 (D-09); Pitfall 6 mitigation deferred via "no search means no escape-helper risk".
- **NEW** `app/modules/visits/service.py` — orchestration layer; the **shared anti-fraud chain lives here, not in the router** (Pitfall 7 + Pitfall 8: reception manual + bot self check-in MUST share validation):
  - **Public reception path** `async def create_visit_reception(session, actor: CurrentUser, payload: VisitCreateRequest) -> VisitResponse` — delegates to `_create_visit_with_anti_fraud(...)` with `channel='reception'`, `checked_in_by=actor.id`, `audit_actor_user_id=actor.id`.
  - **Public bot path** `async def create_visit_self_checkin(session, telegram_user_id: int, chat_id: int) -> VisitResponse` — looks up Client via the new `core.dependencies.resolve_client_by_telegram_user_id(session, tg_user_id)` resolver (D-02); raises `ClientNotLinkedError` (NEW exception) when the resolver returns None; otherwise delegates to `_create_visit_with_anti_fraud(...)` with `channel='telegram_bot'`, `checked_in_by=None`, `audit_actor_user_id=None`. Phase 20 imports this function via `HandlerContext.visits_service` (D-10) — Phase 19 does NOT import telegram code.
  - **Private chain** `async def _create_visit_with_anti_fraud(session, *, client_id, channel, checked_in_by, audit_actor_user_id) -> VisitResponse` — runs the 3 checks IN THIS LOCKED ORDER (matches REQUIREMENTS VIS-03 + audit event sequencing):
    1. **Gym hours check** — `_assert_within_gym_hours(now_msk)` raises `OutsideGymHoursError(409 'outside_gym_hours', fields={'open': '07:00', 'close': '23:00'})` if outside `[settings.gym_hours_start, settings.gym_hours_end)`. On reject: emit `audit.emit("visit_rejected_outside_hours", actor_user_id=audit_actor_user_id, resource_type="visit", resource_id=None, client_id=client_id, channel=channel, current_local_time=now_msk_iso, gym_open=settings.gym_hours_start.isoformat(), gym_close=settings.gym_hours_end.isoformat())` → `await session.commit()` (D-08 reject-path commits) → raise.
    2. **Active membership check** — `await resolve_active_membership(session, client_id)` (Phase 17 D-18 Protocol resolver in `core/dependencies.py`) → if `None`: emit `audit.emit("visit_rejected_no_membership", actor_user_id=audit_actor_user_id, resource_type="visit", resource_id=None, client_id=client_id, channel=channel)` → `await session.commit()` → raise `NoActiveMembershipError(409 'no_active_membership', fields={'client_id': str(client_id)})`. Else: capture `membership.id` for the insert.
    3. **Insert + duplicate check** — `repository.create(session, client_id=..., membership_id=membership.id, channel=channel, checked_in_by=checked_in_by)` then `await session.flush()`. On `IntegrityError`: `await session.rollback()` (D-08 — the failed insert poisoned the session); if `_is_duplicate_visit_conflict(exc)` → emit `audit.emit("visit_rejected_duplicate", actor_user_id=audit_actor_user_id, resource_type="visit", resource_id=None, client_id=client_id, channel=channel, gym_date=str(gym_date_now_msk))` → `await session.commit()` → raise `DuplicateCheckinError(409 'duplicate_checkin', fields={'client_id': str(client_id), 'gym_date': str(gym_date)})`. Else: re-raise the original IntegrityError (untranslated DB error).
    4. **Success path** — `await audit.emit("visit_created", actor_user_id=audit_actor_user_id, resource_type="visit", resource_id=visit.id, client_id=client_id, membership_id=membership.id, channel=channel)` → `await session.commit()` → return `VisitResponse.model_validate(visit)`.
  - **Read-side** `async def list_visits(session, query) -> PaginatedData[VisitResponse]` and `async def get_visit(session, visit_id) -> VisitResponse` — direct repository delegations; raise `VisitNotFoundError` (NEW) on missing.
  - Service `_assert_within_gym_hours(now_msk: time) -> None` is a private synchronous helper for the hours check — testable without DB.
  - **All public mutation functions own `await session.commit()`** (Phase 15 INFRA-13 commit gate). Reject paths also commit (D-08); only the un-translated `else: raise` branch leaves the session dirty (the request boundary's `get_db.rollback()` cleans up).
- **NEW** `app/modules/visits/router.py` — single `APIRouter` mounted at `/visits` per CD-05. Three endpoints (VIS-EP-01..03 + VIS-EP-02 read-one; the ROADMAP Success Criteria #4 mentions list + get-by-id, REQUIREMENTS lists VIS-EP-01..03, totalling 3 routes — list, get, post):
  - `GET /api/v1/visits` (VIS-EP-01) — `Depends(require_permission(VIEW, VISITS))`. Both reception + owner can VIEW. Response: `ResponseEnvelope[PaginatedData[VisitResponse]]`.
  - `GET /api/v1/visits/{id}` (VIS-EP-02) — `Depends(require_permission(VIEW, VISITS))`. 404 `visit_not_found`.
  - `POST /api/v1/visits` (VIS-EP-03) — `Depends(require_permission(CHECK_IN, VISITS))` + `Depends(verify_csrf)` (RBAC-04 ordering: permission BEFORE csrf). 201 with VisitResponse on success; 409 with `code` discriminating `outside_gym_hours` / `no_active_membership` / `duplicate_checkin`. `(CHECK_IN, VISITS)` is **NOT in OWNER_ONLY** — reception receives 201.
- **NEW** `app/core/dependencies.py` extension — second cross-module resolver after `register_active_membership_resolver` (Phase 17 D-18 precedent):
  - `class ClientByTelegram(Protocol)` — structural type for the Client lookup result; Phase 19 only consumes `id` (visits service hands `client.id` to `_create_visit_with_anti_fraud`).
  - `ClientByTelegramResolver = Callable[[AsyncSession, int], Awaitable[ClientByTelegram | None]]`.
  - `_client_by_telegram_resolver: ClientByTelegramResolver | None = None` (module-level slot).
  - `def register_client_by_telegram_resolver(resolver) -> None` — composition-root setter (mirror Phase 17 lines 93–102).
  - `async def resolve_client_by_telegram_user_id(session, telegram_user_id) -> ClientByTelegram | None` — consumer entry (mirror lines 105–119).
- **NEW** `app/modules/clients/service.py:resolve_client_by_telegram_user_id(session, tg_user_id) -> Client | None` — narrow read; queries `select(Client).where(Client.telegram_user_id == tg_user_id, Client.deleted_at.is_(None))`. Used to register the resolver in `app.main:create_app`. Mirrors the `load_user_by_id` Phase 5 pattern.
- **MODIFY** `app/main.py:create_app()` — add ONE line `register_client_by_telegram_resolver(clients.service.resolve_client_by_telegram_user_id)` after the existing `register_active_membership_resolver(...)` call (`main.py:108`). Same idempotent semantics.
- **MODIFY** `app/api/v1/router.py` — add `v1.include_router(visits_router, prefix="/visits", tags=["visits"])` after the existing 4 mounts (auth, clients, plans, memberships). Mount LAST so /docs lists business surfaces in dependency order (clients → plans → memberships → visits) — cosmetic but stable for the byte-stable diff gate (per ARCHITECTURE.md line 450).
- **MODIFY** `app/core/config.py:Settings` — VIS-05:
  - `gym_hours_start: time = time(7, 0)` (default 07:00 Europe/Moscow)
  - `gym_hours_end: time = time(23, 0)` (default 23:00)
  - `model_validator(mode='after')` asserts `gym_hours_end > gym_hours_start` (no midnight-spanning ranges in v1.2 per CD-06; covered by `tests/unit/test_config.py`).
  - Pydantic v2 parses `GYM_HOURS_START="07:00"` env var → `time(7,0)` natively.
- **MODIFY** `apps/backend/.env.example` — add `GYM_HOURS_START=07:00` and `GYM_HOURS_END=23:00` lines under a `# Visits — gym hours window (Europe/Moscow)` comment block. Production override via docker-compose `environment:` (precedence over `env_file: .env` per CR-01 Phase 03-06 fix).
- **MODIFY** `app/core/exceptions.py` — add 4 new `AppError` subclasses:
  - `class NoActiveMembershipError(ConflictError): code = "no_active_membership"; status_code = 409`
  - `class DuplicateCheckinError(ConflictError): code = "duplicate_checkin"; status_code = 409`
  - `class OutsideGymHoursError(ConflictError): code = "outside_gym_hours"; status_code = 409`
  - `class VisitNotFoundError(NotFoundError): code = "visit_not_found"; status_code = 404`
  - `class ClientNotLinkedError(NotFoundError): code = "client_not_linked"; status_code = 404` — bot-only; Phase 20 maps to a generic Russian DM (no oracle leak per Pitfall 8). Lives here (not in modules) because both `visits.service` and Phase 20 `handlers.py` raise/catch it.
- **MODIFY** `apps/backend/openapi.json` — regenerate via `uv run python apps/backend/scripts/export_openapi.py` (mirror Phase 16/17 pattern). Phase 21 owns the FE-side `api-client` codegen + drift-gate refresh.
- Tests:
  - `tests/integration/visits/test_visits_create_reception.py` — happy-path 201; 404 client_not_found via clients-fixture absence; 409 outside_gym_hours (monkeypatched `Settings.gym_hours_start/end` to `time(0,0)`/`time(0,1)` so any test wall-clock fails the window); 409 no_active_membership (no membership row inserted); 409 duplicate_checkin (insert visit first, then POST again); 200 success when membership ends today (inclusive end_date — Pitfall 11 cross-cut test).
  - `tests/integration/visits/test_visits_list_get.py` — list filters (clientId, from, to combinations, default sort); 404 `visit_not_found`; pagination envelope shape.
  - `tests/integration/visits/test_visits_rbac.py` — three-cell matrix: anon → 401, reception → 200/201, owner → 200/201. Confirms `(CHECK_IN, VISITS)` is NOT in OWNER_ONLY (reception 201, not 403).
  - `tests/integration/visits/test_visits_audit.py` — each rejection branch writes the locked event + payload; success writes `visit_created` with `resource_id=visit.id`, `client_id`, `membership_id`, `channel='reception'`. Asserts every emit pair `(event, resource_type)` is in `LOCKED_AUDIT_EVENTS` (TESTS-09 already covers globally; this is per-event coverage).
  - `tests/integration/visits/test_visits_concurrent.py` (VIS-TEST-01) — **the headline test**. 10 parallel `httpx.AsyncClient.post(...)` against the test app for the same client_id with a single active membership; expects exactly 1×201 + 9×409 with `code='duplicate_checkin'`. Uses a non-SAVEPOINT db fixture per CD-09 (the SAVEPOINT-based isolation interferes with concurrent INSERT serialisation; this test gets a `commit_per_request` fixture variant + truncate cleanup). Asserts the audit table has exactly 1 `visit_created` row + 9 `visit_rejected_duplicate` rows after the burst.
  - `tests/integration/visits/test_visits_self_checkin.py` — calls `service.create_visit_self_checkin(session, telegram_user_id=...)` directly (no Phase 20 bot worker needed); covers all 4 rejection paths + success; asserts `channel='telegram_bot'`, `checked_in_by IS NULL`, `actor_user_id IS NULL` in the audit row. The `ClientByTelegramResolver` slot is wired by the test's `create_app(...)` call exactly as in production.
  - `tests/integration/visits/test_alembic_visits.py` — applies the 0006 migration on a real Postgres 16 fixture; asserts the `gym_date` STORED GENERATED column produces the expected date for a row inserted at `2026-05-07T22:30:00+00:00` (which is `2026-05-08` in Europe/Moscow). Pitfall 5's "test on real Postgres, not just SQLite" mandate; this is the canonical proof the migration's CREATE TABLE works.
  - `tests/unit/visits/test_schemas.py` — `BackendSchemaBase` invariants (extra='forbid' rejects `gymDate` in CreateRequest; camelCase serialisation on Response).
  - `tests/unit/visits/test_anti_fraud_helpers.py` — `_assert_within_gym_hours(now)` boundary cases: at 07:00 → ok; at 06:59 → raise; at 22:59 → ok; at 23:00 → raise (end is exclusive per CD-07); midnight crossing rejected at config-load (CD-06).
  - `tests/unit/test_config.py` extension — `Settings(gym_hours_start='23:00', gym_hours_end='07:00')` raises ValidationError (model_validator catches the no-spanning rule).
  - `tests/unit/test_audit_taxonomy.py` — Phase 15 AST walker already covers the 4 new callsites because the `(visit_*, visit)` pairs are already in `LOCKED_AUDIT_EVENTS` (`app/core/audit.py:111-114`). No extension needed; the new callsites pass verbatim.
- `.importlinter` contracts unchanged. The new `app.modules.visits.service → app.core.dependencies` edge is fine (modules → core is allowed). The new `app.modules.clients.service:resolve_client_by_telegram_user_id` registration in `app.main:create_app` follows the `register_user_loader` precedent. The new `Phase 20 future edge` (`app.integrations.telegram.handlers → app.modules.visits.service`) is documented as **D-10** in Phase 20's `app/workers/telegram_bot.py` docstring, NOT in this phase.

Out of scope (locked to later phases):
- **Phase 20** Telegram bot `/checkin` handler + Russian DM strings + Redis update_id dedup. Phase 19 ships the consumer service (`create_visit_self_checkin`) but NOT the handler, NOT the bot worker registration.
- **Phase 21** OpenAPI drift gate + `packages/api-client` codegen for visits. Phase 19 regenerates `apps/backend/openapi.json` (bytewise stable); Phase 21 propagates to the FE typed client.
- **Phase 22** admin-web `features/visits` + check-in page UX (phone-prefix search disambiguation, today's-already-checked-in badge, gym-hours button disable, D-3 expiring-soon badges).
- **`GET /api/v1/visits/_meta`** for FE gym-hours mirroring (FE-08 mention) — deferred to Phase 22; FE can read gym hours from Settings exposure or hardcode.
- **Soft-delete on visits** — visits are immutable historical records (CD-04). If reception checks in the wrong client, the audit trail is the truth; "undo" is a v1.3+ concern (would need a reversal-event taxonomy).
- **`POST /api/v1/visits/{id}/cancel` or DELETE** — no reversal endpoint in v1.2.
- **ILIKE search on visits** — not in scope (D-09); Pitfall 6 PII risk avoided structurally.
- **D-1 "Кто сейчас в зале" card** — read-side aggregate (`SELECT * FROM visits WHERE gym_date = today`), Phase 22 FE concern (FE-10 cheap-win). Phase 19 ships only the underlying data + filterable list endpoint.
- **D-6 reception per-user "сегодняшние посещения"** — same: Phase 22 concern; backend list endpoint already supports the filter shape.
- **`actor_kind: 'system' | 'user'` payload field** — Pitfall 10 mitigation; v1.1 audit_log already uses `actor_user_id IS NULL` for system events. No new field needed.
- **Photo turnstile / NFC / geofence** — explicitly deferred to v2+ per Pitfall 9 / PROJECT.md "accepted residual fraud risk".
- **`infra/docker-compose.yml`** — Phase 19 doesn't ship a new worker (no compose changes). Phase 18 already added `arq-worker`; Phase 19 piggy-backs on `web` for HTTP routes and `telegram-bot` (existing Phase 7 worker, extended in Phase 20) for the bot path.

</domain>

<decisions>
## Implementation Decisions

### Cross-module resolver pattern (the only NEW core surface)

- **D-01:** **`POST /api/v1/visits` body is sealed to `{clientId}` — every other field is server-derived.** `membershipId` resolved via `resolve_active_membership`; `checkedInAt` defaults to DB `now()`; `gymDate` is the STORED GENERATED column (app NEVER writes it — Pitfall 5 #1 invariant); `channel` is `'reception'` for the HTTP path; `checkedInBy` is `actor.id`. Rationale: removes every footgun where a malicious or buggy admin-web client could pre-date a check-in, supply a different membership, or impersonate channel='telegram_bot'. The `BackendSchemaBase` `extra='forbid'` (Phase 15 INFRA-12) rejects extra fields with 422; the request body is the smallest possible surface. Mirrors Phase 16/17's "snapshot fields are server-computed" discipline.
- **D-02:** **`ClientByTelegramResolver` Protocol pattern — second cross-module resolver after Phase 17's `ActiveMembershipResolver`.** Phase 19 visits service needs to look up Client by `telegram_user_id`, but `modules-independent` forbids `app.modules.visits → app.modules.clients`. The validated v1.1/v1.2 escape is the Protocol-callback pattern (D-18 from Phase 17, D-15 from Phase 5). `core/dependencies.py` declares `ClientByTelegram` Protocol + slot + setter + consumer; `app.main:create_app()` registers `clients.service.resolve_client_by_telegram_user_id` once. Visits service calls `resolve_client_by_telegram_user_id(session, tg_user_id)` — never imports clients. Documented in `core/dependencies.py` docstring with explicit "second slot" framing so future v1.3+ authors recognise the pattern.

### Anti-fraud chain — order, audit, transaction lifecycle

- **D-03:** **Anti-fraud check order is `gym_hours → active_membership → insert(unique)`, locked.** This order is REQUIREMENTS VIS-03 verbatim and matches the cost gradient (cheap synchronous time check before any DB work, then a single SELECT, then the INSERT that races against concurrent siblings). The audit event names were locked Phase 15 in this same order (`visit_rejected_outside_hours` → `visit_rejected_no_membership` → `visit_rejected_duplicate`). Reordering would change which rejection a client sees first when multiple constraints fail — the locked order is also the intuitive order ("zal closed" beats "no membership" beats "already checked in").
- **D-04:** **Reception manual + bot self-checkin share `_create_visit_with_anti_fraud` private function; only the public wrappers differ.** Inputs to the private chain: `(client_id, channel, checked_in_by, audit_actor_user_id)`. The two public functions are thin: they resolve their actor (HTTP CurrentUser vs telegram_user_id → Client lookup) and call the private with mapped args. Rationale: Pitfall 7 mandates "anti-fraud lives in `visits.service`, not in the handler"; one private function with two callers makes that structurally true. Adding a third channel (e.g., NFC turnstile in v2+) is one new public wrapper and one new `channel` enum value.
- **D-05:** **Rejection paths emit audit + commit + raise (DEVIATES from Phase 16/17 pattern).** Phase 16/17 services follow "no commit on raise" (the txn aborts, no audit row). Visits inverts: every rejection writes a `visit_rejected_*` audit row before raising. Rationale:
  - Pitfall 9 / fraud-detection: rejection patterns ("user kept hitting outside-hours from 02:00 each night") are the data anti-fraud reports live on. Without persistent rejections, the audit log is one-sided (only successes).
  - VIS-AUDIT-01 + ROADMAP SC#5 both say "Every successful or rejected check-in writes the locked audit event" — explicit requirement.
  - The duplicate-checkin path needs `await session.rollback()` first (the failed INSERT poisoned the session), then a fresh emit + commit. The outside-hours and no-membership paths can emit + commit cleanly because no INSERT has been attempted.
  - The `OutsideGymHoursError` / `NoActiveMembershipError` / `DuplicateCheckinError` exceptions are raised AFTER the audit commit, so HTTP 409 + body.code is what the client sees (the audit is invisible to the request but visible in the audit_log table).

### Visit ORM shape

- **D-06:** **`gym_date` is a Postgres GENERATED ALWAYS … STORED column — app code NEVER writes it.** The migration uses `sa.Column("gym_date", sa.Date, sa.Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True), nullable=False)`. The ORM mapping uses the same `Computed(..., persisted=True)`. Rationale: Pitfall 5 #1 invariant — the only way to keep the UNIQUE constraint correct under concurrency is to have Postgres compute the value, NOT the app. App-computed `gym_date` allows two requests to disagree on what "today" is (UTC vs MSK, server clock skew, race against midnight) and still INSERT both rows. A STORED GENERATED column makes this a structural impossibility.
- **D-07:** **`checked_in_at` defaults to DB `now()` — app code MAY override via the request body in tests, NEVER in production.** Standard pattern. The migration uses `server_default=sa.text("now()")`; the ORM mapping uses `Mapped[datetime]` (no Python default). The `VisitCreateRequest` does not expose `checkedInAt` (D-01), so HTTP callers can't override.
- **D-08:** **Visit `(client_id, gym_date)` UNIQUE INDEX is unconditional — NO `WHERE deleted_at IS NULL` partial.** Phase 16/17 use partial unique indexes because rows can be soft-deleted and a fresh insert with the same key should succeed. Visits have NO `deleted_at` column (CD-04). The UNIQUE is full, mirroring `users.email` (Phase 5) and `audit_log` (Phase 8). Index name: `uq_visits_client_id_gym_date`. Service `_is_duplicate_visit_conflict(exc)` matches on this literal string + asyncpg `constraint_name` (mirror of clients/memberships pattern).
- **D-09:** **No ILIKE search, no sort enum — fixed `checked_in_at DESC` order.** v1.2 visits page is small (< 500 visits/day, < 30 visits/client). Search is via `?clientId` filter; sorting needs are met by the default. Adding sort/search expands the API surface and re-introduces Pitfall 6 (LIKE-escape PII) for zero v1.2 user value (Phase 22 FE doesn't request it). Future v1.3+ can add when the visits volume exceeds reception's eyeball capacity.

### Settings / config

- **D-10:** **`gym_hours_start`/`_end` are `time` objects parsed by Pydantic v2 from `HH:MM` env strings.** Pydantic v2 supports `time` natively; no custom parser. Defaults `time(7, 0)` / `time(23, 0)` per VIS-05 — production overrides via `apps/backend/docker-compose.yml environment:` block (CR-01 precedence).
- **D-11:** **No midnight-spanning gym hours in v1.2.** `model_validator(mode='after')` asserts `gym_hours_end > gym_hours_start`. A 23:00→02:00 club doesn't fit single-zal scope — adding it requires the anti-fraud check to handle two windows, which doubles the test matrix. Documented as accepted limitation; configurable in v1.3+ if a real "круглосуточный" zal joins.

### Bot-path lookup edge case

- **D-12:** **`ClientNotLinkedError` (404) is the bot-path "no client matches this telegram_user_id" exception.** Phase 19 service raises it; Phase 20 handler catches it and replies with the generic "Обратитесь к администратору" Russian DM (Pitfall 8 #1: no oracle leak — bot doesn't say "no account found", only "couldn't check in"). The audit log records `audit.emit("visit_rejected_no_membership", ...)` is NOT used here — there's no client_id to log; instead Phase 20 will add a `telegram_unknown_checkin` audit event (NEW; lives in Phase 20's INFRA-11 frozenset addition, NOT this phase). Phase 19 raises the exception cleanly without an audit emit; Phase 20 owns the audit + DM.

### Tests / fixtures

- **D-13:** **VIS-TEST-01 concurrent test uses a `commit_per_request` (non-SAVEPOINT) db fixture.** The default `db_session` fixture (Phase 4 D-26) wraps the test in a SAVEPOINT for per-test isolation; concurrent INSERT serialisation against the UNIQUE index doesn't compose cleanly with nested savepoints (savepoint rollback on IntegrityError can mask the second-+ failures or affect ordering). Solution: a sibling fixture `db_session_real_commit` that uses real BEGIN/COMMIT per request and TRUNCATEs `visits` + `audit_log` at fixture exit. Used ONLY for `test_visits_concurrent.py`. Documented in `tests/integration/visits/conftest.py` with a one-paragraph rationale.
- **D-14:** **Test fixture for self-checkin path uses `create_app()` to register stub resolvers** — same pattern as Phase 17 D-18. Tests can inject a `lambda session, tg_id: AsyncMock(return_value=fake_client)` to stub the lookup; production path uses the real `clients.service.resolve_client_by_telegram_user_id`.
- **D-15:** **Real Postgres 16 migration test (`test_alembic_visits.py`) is REQUIRED — Pitfall 5 mandate.** A unit test with SQLite Mocks would silently pass on a broken `Computed("(checked_in_at AT TIME ZONE …)::date")` because SQLite has no GENERATED ALWAYS support. The test inserts a row with `checked_in_at = '2026-05-07T22:30:00+00:00'`, asserts `gym_date == 2026-05-08` (because 22:30 UTC = 01:30 MSK next day). This is the only test that proves the migration's headline feature.

### Audit emit payloads (locked)

- **D-16:** **Audit payload schemas, locked verbatim:**
  - `visit_created`: `{client_id, membership_id, channel}` — `resource_id=visit.id`, `actor_user_id=actor.id` for reception, `None` for bot.
  - `visit_rejected_no_membership`: `{client_id, channel}` — `resource_id=None`.
  - `visit_rejected_duplicate`: `{client_id, gym_date, channel}` — `resource_id=None`.
  - `visit_rejected_outside_hours`: `{client_id, channel, current_local_time, gym_open, gym_close}` — `resource_id=None`.
  - All event/resource_type pairs are already in `app/core/audit.py:111-114` `LOCKED_AUDIT_EVENTS`. The AST taxonomy walker (`tests/unit/test_audit_taxonomy.py`) catches typos at the new callsites.

### Plan layout (Claude's discretion — finalise at `/gsd-plan-phase`)

- **CD-01 (default applied):** **5 plans, mirroring Phase 16/17 layout.**
  - `19-01-PLAN.md` — Migration 0006_visits + Visit ORM + schemas (BackendSchemaBase) + 5 new exceptions + GYM_HOURS env + Settings validator. (VIS-01, VIS-02, VIS-05)
  - `19-02-PLAN.md` — `core/dependencies.py` `ClientByTelegram` Protocol + setter + consumer + `clients.service.resolve_client_by_telegram_user_id` + `app.main` wiring. (D-02 / cross-module resolver)
  - `19-03-PLAN.md` — `repository.py` + `service.py` (anti-fraud chain + reception path + self-checkin path + audit emits). (VIS-02, VIS-03, VIS-04, VIS-AUDIT-01)
  - `19-04-PLAN.md` — `router.py` (3 endpoints) + v1 mount + `openapi.json` regen. **BLOCKING migration apply** — same flag as Phase 17-04. (VIS-EP-01..03, VIS-AUDIT-01)
  - `19-05-PLAN.md` — Integration tests (CRUD/RBAC/audit/concurrent VIS-TEST-01/self-checkin/migration) + unit tests (schemas/anti_fraud_helpers/config). (VIS-TEST-01, TESTS-09)
- **CD-02 (default applied):** **`19-04-PLAN.md` is BLOCKING-after-migration**, mirror Phase 17-04. The router can't run until the migration applies in the test DB. The plan's BLOCKING flag triggers `/gsd-execute-phase` to apply 0006 before running 19-04.

### Defaults if user says nothing at plan-phase review

All `D-*` decisions above are RECOMMENDED options selected automatically by `--auto`. User overrides at plan-phase review by saying e.g. "actually, raise on duplicate WITHOUT emitting audit (revert D-05)" — the planner reflects the change in 19-NN-PLAN.md before execution.

### Locked-not-discussed (carried verbatim from REQUIREMENTS / Phase 15 / ROADMAP / research)

- **RBAC:** `(VIEW, VISITS)` reception+owner; `(CHECK_IN, VISITS)` reception+owner. **Neither in `OWNER_ONLY`** — Phase 15 INFRA-08 lock. CSRF on `POST /api/v1/visits` (RBAC-04 ordering: permission BEFORE csrf).
- **Audit taxonomy:** `("visit_created", "visit")`, `("visit_rejected_no_membership", "visit")`, `("visit_rejected_duplicate", "visit")`, `("visit_rejected_outside_hours", "visit")` — all already in `LOCKED_AUDIT_EVENTS` (`app/core/audit.py:111-114`). No taxonomy extension.
- **Inclusive `end_date` semantics** (Phase 15 PROJECT.md Key Decision) — a membership ending today is still active for today's check-in. `resolve_active_membership` returns it because `end_date >= today (Europe/Moscow)`. Phase 19 cross-cut test in `test_visits_create_reception.py`.
- **`gym_date` definition** (Phase 15 PROJECT.md Key Decision) — `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`. STORED GENERATED in the migration.
- **Container `TZ=UTC`** — locked Phase 15. Python uses `ZoneInfo("Europe/Moscow")` to compute MSK-local time for the gym-hours check; never via `os.environ["TZ"]`.
- **No `apps/admin-web` changes in this phase** — Phase 22 owns FE wiring.
- **No new runtime deps** — `time` is stdlib; `ZoneInfo` is stdlib via `zoneinfo`; SQLAlchemy `Computed` is stock SA 2.0.
- **Pagination contract** — `{items, total, page, pageSize}`; `PageQuery` from `core/pagination.py`. Default `page=1, pageSize=20, max=100`.
- **camelCase wire** — `BackendSchemaBase` (Phase 15 INFRA-12). FE consumes `gymDate`, `clientId`, `checkedInAt`, `checkedInBy` as camelCase; service uses `gym_date`, `client_id`, etc. snake_case.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — Constraints (РФ/СНГ; Telegram-first), Key Decisions table (incl. inclusive `end_date`, `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` STORED, accepted residual friend-fraud risk for v1.2 single-zal scope, container `TZ=UTC`).
- `.planning/REQUIREMENTS.md` — Phase 19 owns VIS-01..05, VIS-EP-01..03, VIS-AUDIT-01, VIS-TEST-01. Note: VIS-04 wording says "users.telegram_user_id ↔ users.id ↔ existing client mapping" — actual schema has `clients.telegram_user_id` directly (clients/models.py:89), so the resolver path is `clients.service.resolve_client_by_telegram_user_id` (D-02). Reconcile via REQUIREMENTS.md edit in 19-04-PLAN.md OR document as VERIFICATION deviation.
- `.planning/ROADMAP.md` §"Phase 19: Visits — DB + reception check-in (backend)" — phase goal + Success Criteria 1-5 + dependency note (depends on Phase 17, parallel-eligible with Phase 18 — Phase 18 is now complete).
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions including D-09 (ARQ exception, Phase 18) and the upcoming D-10 (Phase 20 telegram→visits).

### Phase 17 outputs (direct precursor — resolver consumer)
- `.planning/phases/17-membership-instances-resolver-backend/17-CONTEXT.md` — D-18 Protocol pattern (`ActiveMembership` in `core/dependencies.py`); the `ClientByTelegram` Protocol (Phase 19 D-02) is the second instance of the same pattern.
- `.planning/phases/17-membership-instances-resolver-backend/17-VERIFICATION.md` — confirms `Membership` model + service (sale + cancel + resolver) shipped; `register_active_membership_resolver` is wired in `app/main.py:108`.
- `apps/backend/app/modules/memberships/service.py:resolve_active_membership_by_client` — the active-membership resolver Phase 19 service consumes (via `core.dependencies.resolve_active_membership`).
- `apps/backend/app/modules/memberships/router.py:60-306` — pattern Phase 19's router mirrors (RBAC-04 ordering, CSRF on mutations, `BackendSchemaBase` request body, `ResponseEnvelope[T]` wrapping, paginated list shape).

### Phase 18 outputs (parallel sibling — context only)
- `.planning/phases/18-arq-scheduled-expire-memberships/18-CONTEXT.md` — `expire_memberships` cron flips memberships `active → expired`. Phase 19's `resolve_active_membership` correctly skips `status='expired'` rows; the test `test_visits_create_reception.py:test_expired_today_inclusive` proves the boundary (membership ending today is still `active` until tomorrow's tick).

### Phase 16 outputs (template precedent)
- `.planning/phases/16-membership-plans-catalog-backend/16-CONTEXT.md` — module template (router/service/repository/schemas) — Phase 19 mirrors structure.
- `apps/backend/app/modules/memberships/repository.py` — repo single-point-of-access invariant + `_is_plan_name_conflict` IntegrityError translation pattern; Phase 19 mirrors with `_is_duplicate_visit_conflict`.

### Phase 15 outputs (foundation contracts)
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-CONTEXT.md` — INFRA-08 RBAC pairs (`(CHECK_IN, VISITS)` NOT in OWNER_ONLY); INFRA-11 audit taxonomy (visit_*); INFRA-12 `BackendSchemaBase`; INFRA-13 service-write commit gate (Phase 19 service obeys cleanly — every public mutation `await session.commit()`s on every exit branch including reject paths per D-05).
- `apps/backend/app/core/permissions.py` — `Action.CHECK_IN`, `Resource.VISITS`, `OWNER_ONLY` confirmed via Phase 15 — reception receives 201 not 403.
- `apps/backend/app/core/audit.py:104-116` — `LOCKED_AUDIT_EVENTS` line 111-114 declares the four `visit_*` event/resource pairs. The AST taxonomy walker (`tests/unit/test_audit_taxonomy.py`) enforces literal-string callsites.
- `apps/backend/app/core/schemas.py:BackendSchemaBase` — `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra='forbid'`. Phase 19 schemas inherit.
- `apps/backend/app/core/services.py:BusinessService` template + AST commit gate `tests/unit/test_service_commit_gate.py` — Phase 19 visits service obeys without `# noqa: SVC001` (every mutation function commits on every exit branch — even reject paths per D-05).

### Phase 12.1 / Phase 14 carry-overs (PII + commit discipline)
- `apps/backend/app/core/sql.py:escape_like_pattern` — Phase 15 INFRA-10 hoist; not used in this phase (D-09 no ILIKE search) but referenced as the canonical helper if v1.3+ adds search to visits.
- `.planning/research/PITFALLS.md` Pitfall 6 — ILIKE/PII regression pattern; Phase 19 avoids structurally by not adding search.

### Research outputs (v1.2 — global)
- `.planning/research/SUMMARY.md` §"Phase 19" — explicit task list: Alembic 0006 with STORED GENERATED `gym_date` + UNIQUE on `(client_id, gym_date)`; module template; shared anti-fraud helpers; `/api/v1/visits` 3 routes; concurrent-request test (10 parallel → 1×201 + 9×409).
- `.planning/research/PITFALLS.md` Pitfall 5 — full mitigation: STORED GENERATED `gym_date` column + UNIQUE INDEX + IntegrityError → `DuplicateCheckinError(409)` + concurrent-request test. Pitfall 7 — Protocol-callback pattern for cross-module callbacks (`ClientByTelegramResolver` D-02). Pitfall 8 — bot DM oracle leak; Phase 19 raises typed exceptions, Phase 20 maps to generic Russian DM. Pitfall 9 — accepted residual friend-fraud risk; gym-hours window mitigation. Pitfall 10 — audit taxonomy lock + naming conventions (snake_case event verb-past, singular snake_case resource_type); Phase 15 already enforces.
- `.planning/research/ARCHITECTURE.md` §"D-10" (lines 195+) — `HandlerContext.visits_service` ModuleType extension for Phase 20; Phase 19 ships the consumer (`create_visit_self_checkin`), Phase 20 ships the call site.
- `.planning/research/ARCHITECTURE.md` §"Visits module" (lines 427-435) — `/api/v1/visits` route table; Phase 19 endpoints match.
- `.planning/research/ARCHITECTURE.md` §"Phase 19" (line 464) — phase scope summary.
- `.planning/research/STACK.md` — confirms zero new runtime deps; `time` + `ZoneInfo` are stdlib; SA `Computed` is stock SA 2.0.
- `.planning/research/FEATURES.md` V-1 ("Reception manual check-in") — UX shape the backend supports (search → click → 201/409). FE work in Phase 22; backend exposes the underlying capability.

### Backend codebase — direct templates
- `apps/backend/alembic/versions/0005_memberships.py` — migration shape Phase 19 mirrors (CHECK constraints, FK with explicit constraint name, composite index with raw `op.execute` for ordering qualifiers if needed).
- `apps/backend/app/modules/memberships/models.py:85-161` — Membership ORM as the closest existing template (UUIDPkMixin + TimestampMixin, NO SoftDeleteMixin, FK with literal-ref constraint name, composite index in `__table_args__`).
- `apps/backend/app/modules/memberships/repository.py` — repo single-point-of-access invariant + IntegrityError translation pattern.
- `apps/backend/app/modules/memberships/service.py:73-129` — `_is_plan_name_conflict` / `_is_plan_in_use_conflict` / `_assert_can_cancel` patterns; Phase 19 mirrors with `_is_duplicate_visit_conflict`, `_assert_within_gym_hours`.
- `apps/backend/app/modules/memberships/router.py:60-306` — RBAC-04 ordering, CSRF on mutations, `BackendSchemaBase` request body, `ResponseEnvelope[T]` wrapping.
- `apps/backend/app/modules/memberships/schemas.py` — `BackendSchemaBase` subclass conventions; pagination query shape.
- `apps/backend/app/core/dependencies.py:65-119` — `ActiveMembership` Protocol + `register_active_membership_resolver` + `resolve_active_membership` — Phase 19 D-02 mirrors with `ClientByTelegram`.
- `apps/backend/app/main.py:108` — `register_active_membership_resolver(...)` — Phase 19 adds a sibling `register_client_by_telegram_resolver(...)` line.
- `apps/backend/app/api/v1/router.py` — Phase 19 adds `v1.include_router(visits_router, prefix="/visits", tags=["visits"])` after the existing 4 mounts.
- `apps/backend/app/core/exceptions.py:81-163` — exception class shape (extends `NotFoundError` / `ConflictError`; class-level `code` + `status_code`); Phase 19 adds 5 new ones.
- `apps/backend/app/core/audit.py:119-173` — `audit.emit` signature; rejection-path emits use the same shape as success-path emits, `actor_user_id=None` for bot-path rows.
- `apps/backend/app/core/config.py:Settings` — Pydantic `time` parsing; Phase 19 adds `gym_hours_start: time` / `gym_hours_end: time`. The `model_validator(mode='after')` for cross-field assertion is a Pydantic v2 native feature.
- `apps/backend/app/core/pagination.py:PageQuery, PaginatedData` — list endpoint pagination contract.
- `apps/backend/app/modules/clients/models.py:89-104` — `clients.telegram_user_id` BIGINT NULL, UNIQUE constraint `uq_clients_telegram_user_id`. The lookup column for `resolve_client_by_telegram_user_id` (D-02) — the column is on `clients`, NOT on `users`; reconciles VIS-04 wording (REQUIREMENTS.md likely needs the wording edit).

### Backend codebase — wiring touch-points
- `apps/backend/.env.example` — Phase 19 adds `GYM_HOURS_START=07:00` and `GYM_HOURS_END=23:00` under a new `# Visits — gym hours window (Europe/Moscow)` block.
- `apps/backend/docker-compose.yml` — Phase 19 does NOT add a new service. The `web` service handles HTTP routes; the existing `telegram-bot` service (Phase 7) will gain the `/checkin` handler in Phase 20.
- `apps/backend/openapi.json` — regenerated in Phase 19 via `uv run python apps/backend/scripts/export_openapi.py`. CI byte-stable diff gate stays green after the regen lands. Phase 21 owns the FE-side `api-client` codegen.
- `apps/backend/.importlinter` — three contracts unchanged. `app.modules.visits.service → app.core.dependencies` (modules→core, allowed); `app.modules.clients.service:resolve_client_by_telegram_user_id` registered in `app.main:create_app` (composition root, OK by precedent). Phase 20 adds `app.integrations.telegram.handlers → app.modules.visits.service` (D-10 documented exception).

### Tests (Phase 19 adds; Phase 15 enforces)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Phase 15 INFRA-11 AST walker; the four new `audit.emit("visit_*", …)` callsites pass verbatim because the pairs are already locked.
- `apps/backend/tests/unit/test_service_commit_gate.py` — Phase 15 INFRA-13 AST commit gate; `app.modules.visits.service.create_visit_*` and `_create_visit_with_anti_fraud` are write paths and commit on every exit branch.
- `apps/backend/tests/integration/conftest.py` — `db_session` SAVEPOINT fixture (Phase 4 D-26). Phase 19 adds a sibling `db_session_real_commit` for VIS-TEST-01 only (D-13).
- `apps/backend/tests/integration/rbac/` — RBAC fixture conventions; Phase 19 `test_visits_rbac.py` follows.
- `apps/backend/tests/integration/test_route_introspection.py` — Phase 6 RBAC-04 ordering invariant; new `POST /api/v1/visits` is checked automatically.
- `apps/backend/tests/integration/test_alembic_clean.py` — Phase 2 migration test pattern Phase 19 mirrors with `test_alembic_visits.py`.

### ARQ / cron / Pitfall references (cross-cut)
- `.planning/research/PITFALLS.md` Pitfall 5 (full text) — the canonical "1/day enforcement at DB level" rationale + property-test recipe.
- `.planning/research/PITFALLS.md` Pitfall 11 (lines 404-411) — inclusive `end_date` × `gym_date == end_date` cross-cut test (Phase 19 ships the test in `test_visits_create_reception.py`).

### Conventions (read for style consistency)
- `.planning/codebase/CONVENTIONS.md`, `STRUCTURE.md`, `TESTING.md`.
- `apps/backend/docs/conventions.md` — backend-specific (camelCase wire / snake_case Python; service-write commit discipline).
- `apps/backend/docs/architecture.md` — modular monolith doc.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for the import-linter contracts; D-10 (Phase 20) will be a narrative addendum, NOT a contract relaxation. Phase 19 doesn't touch the ADR.

### Postgres / SA documentation (third-party)
- [Postgres 16 — Generated Columns](https://www.postgresql.org/docs/16/ddl-generated-columns.html) — `STORED` semantics; cited in PITFALLS Pitfall 5.
- [SQLAlchemy 2.0 — Computed columns](https://docs.sqlalchemy.org/en/20/core/defaults.html#computed-ddl-construct) — `sa.Computed("...", persisted=True)` — autogen-friendly form.
- [Pydantic v2 — `model_validator(mode='after')`](https://docs.pydantic.dev/latest/concepts/validators/#model-validators) — cross-field validation for the gym-hours range invariant.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`resolve_active_membership` (`core/dependencies.py:105-119`)** — Phase 17 D-18 resolver consumer. Phase 19's anti-fraud chain calls this; on `None` raises `NoActiveMembershipError` + audit-emits + commits + raises (D-05). The `ActiveMembership` Protocol's 4 attributes (id, client_id, end_date, status) are exactly what Phase 19 needs — the `id` is captured for the `membership_id` foreign key on the visit insert.
- **`audit.emit` co-transactional contract (`core/audit.py:119-173`)** — Phase 19's success-path emit slots in cleanly (same session, no flush/commit inside emit). Reject-path emits (D-05) call `audit.emit(...)` followed by an explicit `await session.commit()` — the function itself NEVER commits, so the explicit commit is the rejection path's choice.
- **`BackendSchemaBase` (`core/schemas.py`)** — Phase 15 INFRA-12 base class. Visits schemas inherit; `extra='forbid'` rejects payload tampering (D-01).
- **`PageQuery` / `PaginatedData` (`core/pagination.py`)** — list endpoint contract. Visits' `VisitListQuery` extends `PageQuery` with `clientId`/`from`/`to` filters.
- **`require_permission` / `verify_csrf` (`core/dependencies.py`)** — RBAC-04 ordering on the POST endpoint. Pattern from `memberships/router.py:259-275`.
- **`Computed("...", persisted=True)` (SA 2.0)** — Postgres GENERATED ALWAYS … STORED column shape (D-06). Used directly in the migration AND in the ORM `mapped_column` so autogen stays in sync.
- **`db_session` fixture (Phase 4 D-26)** — SAVEPOINT-based per-test isolation against real Postgres. Phase 19's `test_alembic_visits.py` and most integration tests use it. VIS-TEST-01 needs a sibling `db_session_real_commit` (D-13) to avoid SAVEPOINT interference with concurrent INSERTs.
- **`ZoneInfo("Europe/Moscow")` (stdlib)** — for app-side gym-hours check (`datetime.now(ZoneInfo("Europe/Moscow")).time()` compared against `settings.gym_hours_start`/`_end`). Container `TZ=UTC` (Phase 15 lock); MSK is computed via Python, not env.

### Established Patterns

- **Service owns mutate + audit emit + commit; router is thin** — Phase 16/17 pattern; Phase 19 mirrors. The wrinkle is reject paths (D-05) — Phase 19 service ALSO commits on reject (audit row preservation), which deviates from Phase 16/17's "no commit on raise" pattern.
- **Cross-module Protocol resolver registered in `app.main.create_app`** — Phase 5 (`register_user_loader`) + Phase 17 (`register_active_membership_resolver`); Phase 19 D-02 adds the third (`register_client_by_telegram_resolver`).
- **Repository single point of access** — only `repository.py` imports the `Visit` ORM; service calls module-level repo helpers; mypy type-checks via the repo return-type chain. Mirror of clients/memberships.
- **Literal-string `audit.emit` callsites** (Phase 15 INFRA-11 AST walker) — the four new visit_* callsites use literal strings.
- **CHECK constraint + composite index in `__table_args__` + raw `op.execute` for DESC ordering** — Phase 17 pattern; Phase 19's `ix_visits_client_id_checked_in_at(checked_in_at DESC)` follows.
- **FK constraint name literal-ref'd from service** — `_is_phone_conflict` (clients), `_is_plan_in_use_conflict` (memberships); Phase 19's `_is_duplicate_visit_conflict` references `uq_visits_client_id_gym_date`.
- **Container `TZ=UTC`** — Phase 15 Key Decisions; visits app code reads MSK only via `ZoneInfo("Europe/Moscow")`, never via process env. The Postgres GENERATED column also uses `AT TIME ZONE 'Europe/Moscow'` literally.
- **Tests under `tests/{unit,integration}/<scope>/`** — Phase 19 creates `tests/integration/visits/` and `tests/unit/visits/`.

### Integration Points

- **`app/main.py`** — adds ONE line `register_client_by_telegram_resolver(clients.service.resolve_client_by_telegram_user_id)` after the `register_active_membership_resolver(...)` call. Same idempotent pattern.
- **`app/api/v1/router.py`** — adds `v1.include_router(visits_router, prefix="/visits", tags=["visits"])`.
- **`app/modules/clients/service.py`** — adds `async def resolve_client_by_telegram_user_id(session, tg_user_id) -> Client | None`. NEW function (small read-only helper).
- **`app/core/exceptions.py`** — adds 5 new exception classes (NoActiveMembershipError, DuplicateCheckinError, OutsideGymHoursError, VisitNotFoundError, ClientNotLinkedError).
- **`app/core/config.py`** — adds 2 fields + 1 model_validator. `.env.example` mirrors.
- **`app/core/dependencies.py`** — adds `ClientByTelegram` Protocol + slot + setter + consumer (4 new top-level names; ~30 lines mirroring lines 65-119).
- **`apps/backend/openapi.json`** — regenerated (3 new operations: list_visits, get_visit, create_visit).
- **`alembic/versions/0006_visits.py`** — new file. `down_revision: str | None = "0005_memberships"`.
- **No `.importlinter` changes**, no `AGENTS.md` / `CLAUDE.md` changes, no docker-compose changes, no FE changes.
- **No Phase 20/22 surface in this phase** — the bot handler import (`app.integrations.telegram.handlers → app.modules.visits.service`) is Phase 20's `D-10` and not added in Phase 19. Phase 22 admin-web wiring is gated on Phase 21 typed `api-client`.

</code_context>

<specifics>
## Specific Ideas

- **The reception POST body is sealed (D-01).** This is the user-style anti-footgun pattern from Phase 16/17 (no FE override of snapshot fields). The sealed body also makes the FE's check-in page (Phase 22 FE-08) trivial: it just sends `{clientId}` and reads back the 409 code on rejection.
- **Reject paths emit + commit + raise (D-05) is a deliberate deviation from Phase 16/17.** It's what makes the audit log a real anti-fraud tool (Pitfall 9) instead of a one-sided success log. The planner MUST document this in the service docstring so future v1.3+ contributors don't "fix" the deviation back to Phase 16/17 shape.
- **STORED GENERATED `gym_date` is the headline structural decision (D-06).** It is the difference between race-proof and race-prone. The migration test (`test_alembic_visits.py`, D-15) is the proof; without it, the migration could silently regress to "app-computed" and the UNIQUE index would still appear correct on green tests.
- **`ClientByTelegramResolver` is the second cross-module resolver (D-02) — establishes the pattern as the v1.x convention.** Phase 5 was the first (user_loader); Phase 17 was the second (active_membership). Phase 19 makes it three. v1.3+ contributors who need cross-module read should reach for this pattern reflexively, not for `from app.modules.X import Y` (which import-linter blocks anyway).

</specifics>

<deferred>
## Deferred Ideas

- **`GET /api/v1/visits/_meta` (gym-hours mirror for FE)** — Phase 22 FE-08 mention. Defer to Phase 22; FE can hardcode or derive from a Phase 22 read-only endpoint addition.
- **D-1 "Кто сейчас в зале" aggregate card** — Phase 22 FE-10 cheap-win; pure read on `gym_date = today` filter (already supported by Phase 19's list endpoint).
- **D-6 reception per-user "today's visits" log** — Phase 22 FE; backend list endpoint already supports `?clientId` + `?from=today&to=today` + actor filter (TBD in Phase 22).
- **Visit reversal endpoint (`POST /visits/{id}/cancel` or `DELETE`)** — v1.3+ if reception ops demand. Audit log + immutable history is the v1.2 truth.
- **Photo turnstile / NFC / geofence** — explicitly v2+ per Pitfall 9 / PROJECT.md "accepted residual fraud risk".
- **Self-checkin via Telegram bot (handler + Russian DM strings + Redis update_id dedup)** — Phase 20 (depends on Phase 19's `create_visit_self_checkin` consumer). Phase 19 ships the consumer; Phase 20 ships the handler + locked Russian copy + dedup.
- **Visit-count plans / hybrid plans** — explicitly v1.3+ per PROJECT.md (`plan_kind: 'time' | 'count'` discriminator).
- **ILIKE search on visits** — D-09 deferral; v1.3+ if visit volume exceeds reception's eyeball limit.
- **Midnight-spanning gym hours** — D-11 deferral; v1.3+ if a real круглосуточный zal joins.
- **`actor_kind: 'system' | 'user'` payload field (Pitfall 10)** — v1.1 audit_log already uses `actor_user_id IS NULL` for system events; redundant.
- **Bulk-aggregated visit_created audit event for high-volume gyms** — single-zal scope makes per-row emits the right default. Revisit at >10 zals.

</deferred>

---

*Phase: 19-visits-db-reception-check-in-backend*
*Context gathered: 2026-05-07*
