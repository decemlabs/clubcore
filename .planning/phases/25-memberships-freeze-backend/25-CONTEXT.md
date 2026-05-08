# Phase 25: Memberships — Freeze (backend) - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude)

<domain>
## Phase Boundary

Reception/owner может бесплатно заморозить и разморозить membership; `end_date` сдвигается вперёд на использованные дни заморозки; resolver не отдаёт frozen membership на check-in; cancel-during-freeze работает корректно. Backend-only — UI wiring живёт в Phase 28 (FE-10/FE-11).

Phase 25 ships:

1. **MEM-FRZ-01** — `freeze_days_limit` INT NOT NULL CHECK > 0 на `membership_plans`, immutable post-creation (mirror `duration_days`); existing rows backfilled `14`; request/response schemas включают `freezeDaysLimit`.
2. **MEM-FRZ-02** — таблица `membership_freeze_periods` (`id`, `membership_id` FK ON DELETE RESTRICT, `started_at`, `ended_at` NULL while active, `started_by`, `ended_by`, `created_at`); partial unique index `(membership_id) WHERE ended_at IS NULL` — single source of truth для concurrency control.
3. **MEM-FRZ-03** — `freeze_days_limit_snapshot` INT NOT NULL на `memberships`; backfill из current plan (или `14` если plan archived); new sales snapshot at sale time (mirror `duration_days_snapshot`).
4. **MEM-FRZ-04** — `service.freeze_membership(session, membership_id, actor)`: only `status='active'` source; preventive `days_used + projected <= snapshot_limit`; вставка active period; transition active → frozen; 409 `invalid_transition` / 409 `freeze_limit_exceeded`.
5. **MEM-FRZ-05** — `service.unfreeze_membership(session, membership_id, actor)`: closes period, recomputes `end_date += ceil(period_days_msk)` (half-day rounds up), transition frozen → active.
6. **MEM-FRZ-06** — resolver видит frozen как not-active (already true since resolver filters `status='active'`); reception POST `/api/v1/visits` + Telegram `/checkin` оба возвращают `no_active_membership` 409 без oracle leak.
7. **MEM-FRZ-07** — `service.cancel_membership` принимает `frozen → cancelled` (owner-only); закрывает open freeze period БЕЗ extension; audit emits `membership_unfrozen` затем `membership_cancelled` в одной транзакции.
8. **MEM-FRZ-EP-01..03** — `POST /api/v1/memberships/{id}/freeze` + `POST /api/v1/memberships/{id}/unfreeze` (CSRF, `(CREATE, MEMBERSHIPS)` reception+owner), пустое тело; detail responses включают `freezeDaysLimitSnapshot`, `freezeDaysUsed`, `freezeDaysRemaining`, `currentFreezePeriod`.
9. **MEM-FRZ-AUDIT-01** — `audit.emit("membership_frozen", ...)` + `audit.emit("membership_unfrozen", ...)`; 6 audit events уже pre-registered в `LOCKED_AUDIT_EVENTS` (Phase 24 INFRA-15).
10. **MEM-FRZ-TEST-01..03** — full freeze cycle (sell 30d → freeze 5d → unfreeze → end_date+5), limit-exceeded (cumulative > snapshot → 409), concurrent freeze (partial unique index race → 409 `already_frozen`).

**State machine extension (`MEMBERSHIP_STATUS_TRANSITIONS`):** Phase 25 заполняет placeholder из Phase 24 D-24-03:
```python
"active":    frozenset({"expired", "cancelled", "frozen"}),  # +frozen
"frozen":    frozenset({"active", "cancelled"}),             # populated
"expired":   frozenset(),
"cancelled": frozenset(),
```
Unit-test parametrize matrix расширяется с 9 cells до 16 (4×4 source×target, исключая self-transitions).

**Out of Phase 25:**
- Renewal column `previous_membership_id` — Phase 26 owns миграцию `0009_renewal.py` (см. D-25-01 ниже).
- Resolver tiebreak extension для multiple active rows — Phase 26 (MEM-REN-03).
- OpenAPI byte-stable refresh + admin-web freeze UI — Phase 28 (FE-10/FE-11).
- ARQ cron auto-unfreeze (нет такого требования — only manual unfreeze).
- Любая Telegram DM на freeze/unfreeze (out of scope; expiring-soon DMs живут в Phase 27).

</domain>

<decisions>
## Implementation Decisions

### Migration scope & numbering

- **D-25-01:** Phase 25 owns Alembic migration `0008_freeze.py` — **freeze-only**, NO `previous_membership_id` column. Phase 26 ships `0009_renewal.py` cleanly on top. (Roadmap milestone note "25 and 26 share migration `0007`" уже устарело после Phase 24's `0007_status_taxonomy.py`; Phase 25 plan-агент удаляет/обновляет ту строчку в `.planning/milestones/v1.3-ROADMAP.md` § "Build Order" + § "Notes on dependencies".)
  - **Why separate, not combined:** Phase 26 may extend resolver tiebreak independently — bundling `previous_membership_id` в Phase 25's migration coupled бы две phase boundaries (если Phase 25 нужен hotfix, миграция несёт renewal column которое ещё не используется). Mirror Phase 24's reasoning for INFRA-16 in its own `0007`.
  - **Alembic chain:** `0007_status_taxonomy` → `0008_freeze` (Phase 25) → `0009_renewal` (Phase 26) → `0010_notifications` (Phase 27).
- **D-25-02:** Migration `0008_freeze.py` upgrade order:
  1. `ALTER TABLE membership_plans ADD COLUMN freeze_days_limit INTEGER NOT NULL DEFAULT 14` + `CHECK (freeze_days_limit > 0)`. Затем `ALTER TABLE membership_plans ALTER COLUMN freeze_days_limit DROP DEFAULT` (existing rows получают `14`, future inserts требуют explicit value). Mirrors `duration_days` immutability pattern.
  2. `ALTER TABLE memberships ADD COLUMN freeze_days_limit_snapshot INTEGER` (nullable initially).
  3. `UPDATE memberships SET freeze_days_limit_snapshot = COALESCE((SELECT freeze_days_limit FROM membership_plans WHERE id = memberships.plan_id), 14)` — backfill from current plan; archived plans (NULL row) → `14`.
  4. `ALTER TABLE memberships ALTER COLUMN freeze_days_limit_snapshot SET NOT NULL`.
  5. `CREATE TABLE membership_freeze_periods (...)` с partial unique index `WHERE ended_at IS NULL` (через `op.execute()` — partial unique indexes не выражаются через `Index(unique=True)` в SA 2.0 без `postgresql_where`, который ON works в declarative но autogenerate suppression лучше через explicit `op.execute()` mirror `0004_membership_plans.py`).
  6. ORM `__table_args__` updates + наименование constraint per `MetaData(...)` NAMING_CONVENTION; schema-layer `MembershipPlanResponse` + `MembershipResponse` обновляются.
- **D-25-03:** Downgrade reverses в обратном порядке, без backfill restoration (downgrade — это disaster recovery; potential data loss explicit в docstring).

### Freeze period table shape

- **D-25-04:** `MembershipFreezePeriod` ORM model — composition `Base + UUIDPkMixin + TimestampMixin` (matches `Membership` — никакого `SoftDeleteMixin`, lifecycle через `ended_at IS NULL`). Колонки точно по REQUIREMENTS MEM-FRZ-02:
  - `id` UUID PK gen_random_uuid()
  - `membership_id` UUID NOT NULL FK `memberships.id` ON DELETE RESTRICT (mirror `fk_memberships_plan_id_membership_plans` rationale — keep audit trail; never cascade-delete history).
  - `started_at` TIMESTAMPTZ NOT NULL — server-side `now()` at freeze time.
  - `ended_at` TIMESTAMPTZ NULL — set on unfreeze.
  - `started_by` UUID NOT NULL FK `users.id` ON DELETE RESTRICT.
  - `ended_by` UUID NULL FK `users.id` ON DELETE SET NULL — operator may be deleted; period stays.
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT now() (TimestampMixin).
- **D-25-05:** Partial unique index name: `uq_membership_freeze_periods_active_per_membership` (per NAMING_CONVENTION expansion); `ON membership_freeze_periods (membership_id) WHERE ended_at IS NULL`. Создаётся через `op.execute("CREATE UNIQUE INDEX ... ON ... WHERE ended_at IS NULL")` — pattern mirrors `uq_membership_plans_name_alive` в `0004_membership_plans.py`. Suppressed in `alembic/env.py:_include_object` так же.
- **D-25-06:** Дополнительный index `ix_membership_freeze_periods_membership_id` на `(membership_id)` НЕ нужен — partial unique index покрывает write-path lookups; aggregate read для `freezeDaysUsed` сканит full set по `membership_id` и redundant index убрать сэкономит INSERT cost (mirror Phase 19 visits index parsimony).

### Service-layer flows

- **D-25-07:** `service.freeze_membership(session, membership_id, actor) -> MembershipResponse`:
  1. Load via `repository.get_membership(session, membership_id)` — 404 `membership_not_found` если missing.
  2. `_assert_can_transition(membership, target="frozen")` — 409 `invalid_transition` для non-active source (uses central guard from Phase 24 D-24-04, теперь возвращает True для `active → frozen` после D-25-13 расширения).
  3. **Preventive limit check (MEM-FRZ-04):** load `freeze_days_used` via `repository.compute_freeze_days_used(session, membership_id, today_msk)`; `remaining = snapshot_limit - days_used`; если `remaining <= 0` → 409 `freeze_limit_exceeded` с payload `{limit: snapshot, used: days_used}`.
     - **Why preventive (не post-hoc на unfreeze):** UX-decision — без preventive проверки клиент мог бы заморозить membership на 99 дней при limit=14, и unfreeze всё равно прошёл бы (не отрицательное end_date), но мы хотим явно отказать ДО открытия period, чтобы клиент знал ограничение сразу. Если будущий cumulative excess detected на unfreeze (theoretical race), unfreeze всё равно завершается — limit guard одноразовый при freeze.
     - **NOT projecting future use:** preventive check считает `days_used >= limit` нарушением. Phase 25 НЕ пытается projection (e.g. "если ты заморозишь сегодня, через X дней у тебя точно превысит limit") — слишком много moving parts (когда разморозят — unknown). Гарантия: ни одна freeze не открывается при `days_used >= snapshot_limit`.
  4. INSERT `membership_freeze_periods` row — `started_at = now(UTC)`, `started_by = actor.id`, `ended_at = NULL`. Catch `IntegrityError`, проверить constraint name `uq_membership_freeze_periods_active_per_membership` → 409 `already_frozen` (D-25-22).
  5. `repository.update_membership_status(membership, status="frozen")` — narrow setter mirror Phase 17 D-12. NO `cancelled_at` / `cancel_reason` mutation.
  6. `await session.flush()`.
  7. `audit.emit("membership_frozen", actor_user_id=actor.id, resource_type="membership", resource_id=membership.id, freeze_period_id=str(period.id), client_id=str(membership.client_id), started_at=period.started_at.isoformat())` — payload schema из REQUIREMENTS MEM-FRZ-AUDIT-01 расширяется `client_id` для consistency с Phase 17 D-14.
  8. `await session.refresh(membership, attribute_names=["updated_at"])`.
  9. `await session.commit()` (SVC001 gate enforces).
  10. Return `MembershipResponse.model_validate(membership_with_freeze_view)` — see D-25-19 для shape.
- **D-25-08:** `service.unfreeze_membership(session, membership_id, actor) -> MembershipResponse`:
  1. Load via `get_membership` — 404 если missing.
  2. `_assert_can_transition(membership, target="active")` — 409 `invalid_transition` для non-frozen source.
  3. Load open period via `repository.get_open_freeze_period(session, membership_id)` — defence-in-depth invariant: status='frozen' implies open period exists, но если нет (manual SQL surgery, bug) — raise `IntegrityError` / structlog ERROR + 500 (не пытаемся "fix" inconsistent state).
  4. `now_utc = datetime.now(tz=UTC)`; `period.ended_at = now_utc`; `period.ended_by = actor.id`.
  5. **Days computation (MEM-FRZ-05 "half-day rounds up"):** convert `period.started_at` и `period.ended_at` в Europe/Moscow timestamps; `delta_seconds = (period.ended_at - period.started_at).total_seconds()`; `days_added = math.ceil(delta_seconds / 86400)` (минимум 1 — даже моментальный unfreeze считает 1 день, anti-abuse + preserves "client never loses partial days" semantics). Document: precision = full seconds, rounding favours client.
  6. `membership.end_date = membership.end_date + timedelta(days=days_added)`.
  7. `repository.update_membership_status(membership, status="active")`.
  8. `await session.flush()`.
  9. `audit.emit("membership_unfrozen", actor_user_id=actor.id, resource_type="membership", resource_id=membership.id, freeze_period_id=str(period.id), client_id=str(membership.client_id), days_added=days_added)`.
  10. `await session.refresh(membership, attribute_names=["updated_at"])`.
  11. `await session.commit()`.
  12. Return `MembershipResponse.model_validate(membership_with_freeze_view)`.
- **D-25-09:** `service.cancel_membership` extension (MEM-FRZ-07): принимает `frozen` source ТОЛЬКО для owner (existing `(CANCEL, MEMBERSHIPS)` ∈ OWNER_ONLY уже это гарантирует на router-level — RBAC уже не пропустит reception). Алгоритм:
  1. Load membership — 404 если missing.
  2. `_assert_can_transition(membership, target="cancelled")` — теперь allows `active → cancelled` AND `frozen → cancelled` (D-25-13).
  3. **Если status='frozen':** load open period; `period.ended_at = now(UTC)`; `period.ended_by = actor.id`; **НЕ** modify `membership.end_date` (cancellation supersedes freeze — REQUIREMENTS MEM-FRZ-07). Emit `audit.emit("membership_unfrozen", ..., days_added=0)` — `days_added=0` discriminates cancel-from-frozen vs normal unfreeze in audit log forensics.
  4. Mutate status='cancelled', `cancelled_at = now(UTC)`, `cancel_reason = data.reason` (existing flow).
  5. Flush.
  6. Emit `audit.emit("membership_cancelled", ...)` (existing event, payload unchanged).
  7. Refresh + commit.
  - **Audit ordering:** `unfrozen` BEFORE `cancelled` per REQUIREMENTS MEM-FRZ-07 — same UoW, both visible in `audit_log` chronologically (id auto-increment). Tests verify both rows present.
  - **`days_added=0` rationale:** sentinel value сохраняет `membership_unfrozen` payload shape stable; cancel context implied by immediately-following `membership_cancelled` event. Альтернативой был бы `via_cancel: bool` field — но adds payload variance без forensic benefit (timestamp ordering + companion event = same info).

### Schema / response shape

- **D-25-10:** `MembershipPlanCreateRequest` adds `freeze_days_limit: int = Field(ge=1, le=365)` (sane upper bound — нет membership дольше года в practice; Pydantic bound + DB CHECK >0 совпадают). NO default — owner explicit value at creation. `MembershipPlanResponse` adds `freeze_days_limit: int`.
- **D-25-11:** `MembershipPlanUpdateRequest` does NOT add `freeze_days_limit` — immutable post-creation per MEM-FRZ-01. `extra='forbid'` on BackendSchemaBase rejects payload с `freezeDaysLimit` → stock 422 (mirrors `duration_days` per Phase 16 D-04). NO service-layer guard needed.
- **D-25-12:** New schemas:
  - `FreezePeriodResponse(ResponseData)` — `{id: UUID, started_at: datetime, started_by: UUID, ended_at: datetime | None, ended_by: UUID | None}` — minimal projection; payload в `currentFreezePeriod` для detail/list; `ended_at`/`ended_by` always null when surfaced as `currentFreezePeriod` (по definition open).
  - `MembershipResponse` extends с 4 полями:
    - `freeze_days_limit_snapshot: int` (always present after migration backfill).
    - `freeze_days_used: int` (computed; sum of completed periods + ongoing days if frozen).
    - `freeze_days_remaining: int` (computed = `freeze_days_limit_snapshot - freeze_days_used`, clamped к 0).
    - `current_freeze_period: FreezePeriodResponse | None` (None when status != frozen; populated when frozen).
- **D-25-13:** `MembershipStatus` enum (`schemas.py:139`) gains `FROZEN = "frozen"`. Existing `MembershipStatus` consumers (filters, response serialisation) автоматически принимают новое значение. Backward-compat: `?status=frozen` query на list endpoint работает.

### `MEMBERSHIP_STATUS_TRANSITIONS` extension

- **D-25-14:** `app/modules/memberships/constants.py` обновляется (Phase 24 placeholder заменяется):
  ```python
  MEMBERSHIP_STATUS_TRANSITIONS = MappingProxyType({
      "active":    frozenset({"expired", "cancelled", "frozen"}),
      "frozen":    frozenset({"active", "cancelled"}),
      "expired":   frozenset(),  # terminal — Phase 26 may or may not extend (renewal creates NEW row, not transition)
      "cancelled": frozenset(),  # terminal
  })
  ```
- **D-25-15:** Unit-test matrix `tests/unit/memberships/test_state_machine.py` расширяется с 9 cells до 16 (4 sources × 4 actions: expire, cancel, freeze, unfreeze). Allowed cells:
  - `(active, freeze)` → ok
  - `(active, expire)` → ok (Phase 18 ARQ path)
  - `(active, cancel)` → ok
  - `(frozen, unfreeze)` → ok (target=active)
  - `(frozen, cancel)` → ok (Phase 25 D-25-09)
  - все остальные → `InvalidTransitionError`
  - Phase 24's `_assert_can_cancel` / `_assert_can_expire` thin wrappers остаются; Phase 25 добавляет `_assert_can_freeze` / `_assert_can_unfreeze` thin wrappers, все делегируют в `_assert_can_transition` per Phase 24 D-24-05 pattern.

### Repository helpers

- **D-25-16:** New repository functions в `apps/backend/app/modules/memberships/repository.py`:
  - `insert_freeze_period(session, *, membership_id, started_by, started_at) -> MembershipFreezePeriod` — INSERT с `ended_at=NULL`. NO try/except — caller (service) handles `IntegrityError` translation.
  - `get_open_freeze_period(session, membership_id) -> MembershipFreezePeriod | None` — SELECT WHERE `membership_id = ? AND ended_at IS NULL` LIMIT 1. Defence-in-depth invariant (но возвращаем `None`, service raises на None при ожидаемом open period).
  - `compute_freeze_days_used(session, membership_id, *, today_msk) -> int` — single SQL aggregate:
    ```sql
    SELECT COALESCE(SUM(
        CEIL(EXTRACT(EPOCH FROM (
            COALESCE(ended_at, now()) - started_at
        )) / 86400)
    ), 0)::int
    FROM membership_freeze_periods
    WHERE membership_id = :membership_id
    ```
    - **Why SQL aggregate, not Python iterate:** detail/list endpoints display `freezeDaysUsed`/`freezeDaysRemaining` per row; iterating loaded periods в Python would быть N+1 для list view. Single aggregate scalar = O(1) extra query per row. List endpoint батчит через subquery (D-25-18).
    - **`COALESCE(ended_at, now())`:** ongoing period counts up-to-the-moment days; matches REQUIREMENTS MEM-FRZ-EP-03 ("sum of completed periods + ongoing if frozen").
    - **`CEIL(seconds / 86400)`:** matches "half-day rounds up" semantic (D-25-08 step 5) byte-stable между Python и SQL.
    - **Europe/Moscow nuance:** seconds-based ceil is timezone-agnostic (UTC seconds = MSK seconds, fixed offset). REQUIREMENTS' "in Europe/Moscow days" wording — interpretive. Decision: использовать seconds-based ceil for code simplicity; document в docstring что MSK timezone interpretation collapses к seconds-based ceil because MSK is UTC+3 fixed (no DST since 2014). Если в будущем нужны calendar-day boundaries, refactor isolated.
  - `get_freeze_period_by_id(session, period_id) -> MembershipFreezePeriod | None` — для unit tests / future debug; not used by service paths.
- **D-25-17:** `repository.find_active_for_client` (Phase 17 + Phase 24 DEBT-01) — **NO change** в Phase 25. Resolver уже filters `status == 'active'`; frozen rows naturally excluded (status='frozen'). MEM-FRZ-06 satisfied by existing code; Phase 25 contributes только integration test asserting frozen membership → resolver returns None → reception POST `/api/v1/visits` → 409 `no_active_membership` AND Telegram `/checkin` → generic Russian "no active membership" DM (no oracle leak — the same DM stranger sees).
- **D-25-18:** **`MembershipResponse` list view freeze fields** — list endpoint (Phase 17 `service.list_memberships`) загружает N rows; `freezeDaysUsed`/`freezeDaysRemaining` computed via single subquery LEFT JOIN на aggregate, не per-row N+1:
  ```sql
  SELECT m.*,
         COALESCE(fp.days_used, 0) AS freeze_days_used
  FROM memberships m
  LEFT JOIN (
      SELECT membership_id,
             SUM(CEIL(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 86400))::int AS days_used
      FROM membership_freeze_periods
      GROUP BY membership_id
  ) fp ON fp.membership_id = m.id
  WHERE ...
  ```
  - **Implementation note for planner:** проще хранить subquery как CTE или scalar subquery в SA; helper `_freeze_days_used_subquery()` returning `Subquery` reusable между list и `get_membership` paths. `current_freeze_period` для frozen rows — отдельный JOIN (или separate SELECT для list — small N, default page=20). Planner picks minimal-risk approach.

### Endpoint signatures + RBAC

- **D-25-19:** Two new endpoints на `memberships_router`:
  ```python
  @memberships_router.post("/{membership_id}/freeze",
      response_model=ResponseEnvelope[MembershipResponse],
      status_code=status.HTTP_200_OK,
      summary="Freeze membership (reception+owner; 409 freeze_limit_exceeded / already_frozen / invalid_transition)")
  async def freeze_membership(
      membership_id: UUID,
      actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))],
      _csrf: Annotated[None, Depends(verify_csrf)],
      session: Annotated[AsyncSession, Depends(get_db)],
  ) -> ResponseEnvelope[MembershipResponse]: ...

  @memberships_router.post("/{membership_id}/unfreeze", ...)  # same dependencies
  ```
  - **RBAC:** `(CREATE, MEMBERSHIPS)` — reception+owner per OWNER_ONLY (15 entries from Phase 22; CREATE на memberships НЕ в OWNER_ONLY). Mirrors REQUIREMENTS MEM-FRZ-EP-01/02.
  - **CSRF:** `verify_csrf` dependency после `require_permission` (RBAC-04 ordering).
  - **Body:** empty (no Pydantic body schema needed; FastAPI accepts no body на POST).
  - **Response:** 200 OK с `ResponseEnvelope[MembershipResponse]` (NOT 201/204 — body carries new state per REQUIREMENTS).
- **D-25-20:** Existing `cancel_membership` endpoint signature/permissions unchanged — service-layer guard (D-25-09) handles `frozen → cancelled` transparently. No router change beyond docstring update mentioning frozen source acceptance.

### Exception classes

- **D-25-21:** Two new exception classes в `app/core/exceptions.py`:
  ```python
  class FreezeLimitExceededError(ConflictError):
      """Raised on POST /memberships/{id}/freeze when cumulative freeze days
      would exceed freeze_days_limit_snapshot (Phase 25 MEM-FRZ-04).

      Constructor:
          raise FreezeLimitExceededError(
              "freeze_limit_exceeded",
              fields={"limit": snapshot_limit, "used": days_used},
          )
      """
      code = "freeze_limit_exceeded"
      status_code = 409

  class AlreadyFrozenError(ConflictError):
      """Raised on POST /memberships/{id}/freeze when partial unique index
      uq_membership_freeze_periods_active_per_membership rejects concurrent
      INSERT (Phase 25 MEM-FRZ-TEST-03 race).

      Discriminated against IntegrityError by service.py:_is_already_frozen_conflict
      checking constraint name.
      """
      code = "already_frozen"
      status_code = 409
  ```
  Existing `InvalidTransitionError` reused для invalid transitions (consistent с Phase 17/24).
- **D-25-22:** `_is_already_frozen_conflict(exc: IntegrityError) -> bool` helper в `service.py` — mirrors `_is_plan_name_conflict` / `_is_plan_in_use_conflict` pattern (constraint_name attr first, substring fallback). Constraint name literal: `"uq_membership_freeze_periods_active_per_membership"`.

### Test taxonomy

- **D-25-23:** Test files (planner finalises exact paths):
  - `tests/unit/memberships/test_state_machine.py` — extend matrix from 9 → 16 cells (D-25-15).
  - `tests/unit/memberships/test_freeze_days_computation.py` — pure helper test for ceil rounding (verify min=1, fractional day round-up, multi-period sum).
  - `tests/unit/test_audit_taxonomy.py` — already passes (Phase 24 pre-registered events); Phase 25 adds callsite presence assertion (literal string AST scan finds `audit.emit("membership_frozen", ...)` in `service.py`).
  - `tests/integration/memberships/test_freeze_cycle.py` — MEM-FRZ-TEST-01: sell 30d → freeze 5d (sleep/clock-injection) → unfreeze → assert `end_date += 5`, `freeze_days_used == 5`.
  - `tests/integration/memberships/test_freeze_limit.py` — MEM-FRZ-TEST-02: snapshot_limit=14 → freeze period of 10d (close) → freeze 5d → 409 `freeze_limit_exceeded`.
  - `tests/integration/memberships/test_freeze_race.py` — MEM-FRZ-TEST-03: concurrent INSERT via two AsyncSessions → second hits IntegrityError → 409 `already_frozen` (mirrors Phase 19 visits race test pattern).
  - `tests/integration/memberships/test_freeze_resolver.py` — MEM-FRZ-06: freeze membership → call `resolve_active_membership_by_client` → returns None; reception POST `/api/v1/visits` → 409 `no_active_membership`; Telegram `/checkin` → generic DM (oracle-safe).
  - `tests/integration/memberships/test_cancel_during_freeze.py` — MEM-FRZ-07: freeze → cancel → both `membership_unfrozen (days_added=0)` AND `membership_cancelled` audit rows present in same UoW; `end_date` unchanged.
  - `tests/integration/memberships/test_freeze_endpoints.py` — RBAC matrix on POST freeze/unfreeze (anonymous → 401, reception → 200, CSRF missing → 403); response shape includes all 4 new fields.

- **D-25-24:** **Clock injection для freeze tests:** existing pattern uses explicit `today` param + `freeze_some_table_with_offset` fixtures. Phase 25 freeze period tests need TIMESTAMPTZ control — recommend mocking `datetime.now` via `monkeypatch.setattr(memberships.service, "_utc_now", lambda: ...)` helper. Planner inspects existing patterns в Phase 18 ARQ tests + Phase 19 visits race test to pick the canonical approach (likely `freeze_clock` fixture или direct injection of `now_utc` arg into private helper). Avoid `freezegun` per Phase 24 D-24-06 precedent.

### Frontend / OpenAPI implications

- **D-25-25:** Phase 25 backend changes regenerate `apps/backend/openapi.json` (new endpoints + new response fields). Phase 28 owns the cumulative drift-gate refresh — Phase 25 plan agent decides whether to:
  - (a) regenerate openapi.json + commit as part of Phase 25's last commit (если CI drift gate runs every commit), OR
  - (b) skip regen, leave for Phase 28 (если drift gate is milestone-end check).
  - **Recommended:** confirm CI behaviour first; prefer (a) for incremental drift detection — но не делать это blocker для phase completion. Phase 24 D-24-25 carried this same decision; Phase 25 plan agent reuses тот же rationale.
- **D-25-26:** Mock service `apps/admin-web/src/shared/api/services/mock/memberships.ts` is **NOT touched в Phase 25** — UI wiring + mock parity for freeze живут в Phase 28 (FE-10). Phase 25 ships pure backend; admin-web continues работать на existing endpoints (freeze не виден в UI до Phase 28 merge).

### Audit payload schemas (canonical)

- **D-25-27:** Final audit payload contracts:
  ```python
  # Phase 25 MEM-FRZ-AUDIT-01
  audit.emit(
      session,
      "membership_frozen",  # LITERAL — Phase 15 INFRA-11 AST gate
      actor_user_id=actor.id,
      resource_type="membership",  # LITERAL
      resource_id=membership.id,
      client_id=str(membership.client_id),
      freeze_period_id=str(period.id),
      started_at=period.started_at.isoformat(),
  )

  audit.emit(
      session,
      "membership_unfrozen",  # LITERAL
      actor_user_id=actor.id,
      resource_type="membership",  # LITERAL
      resource_id=membership.id,
      client_id=str(membership.client_id),
      freeze_period_id=str(period.id),
      days_added=days_added,  # int >=0; 0 sentinel for cancel-during-freeze (D-25-09)
  )
  ```
  - `client_id` extension over REQUIREMENTS-stated payload — consistent с Phase 17 D-14 pattern (always include `client_id` для cross-client audit forensics; UUID stringified для JSONB-serialisability).
  - `audit.py` docstring lines 57+59 already document expected payload shape; this CONTEXT confirms exact field names. Planner: update docstring if discrepancy with chosen names ("freeze_days" vs "days_added" — Phase 25 uses `days_added` because `freeze_days` is ambiguous — это used or remaining?).

### Claude's Discretion (planner picks)

- Exact filename для unit/integration tests above (D-25-23 names — proposals only).
- Whether `_freeze_days_used_subquery()` lives в repository.py vs separate helper module (recommend: repository.py, alongside `find_active_for_client`).
- Whether to add `unfrozen_at` / `unfrozen_by` columns on `Membership` directly OR rely entirely on freeze period table for history. Recommended: rely on freeze period table — `Membership` row stays narrow.
- Naming для thin transition wrappers (`_assert_can_freeze` / `_assert_can_unfreeze` — proposed; planner может предпочесть central guard direct calls if cleaner).
- Whether to inline `MembershipFreezePeriod` ORM в `models.py` (alongside MembershipPlan + Membership) or split into `models_freeze.py`. Recommended: inline (file is ~160 LOC, still readable).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § "Phase 25" — phase summary + 5 success criteria.
- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 25" + § "Build Order" + § "Key Risks / Watchpoints" — milestone-scoped detail; resolver touch-points serialization (24→25→26); migration `0008` ownership notes (Phase 25 amends after D-25-01 supersedes the "shared `0007`" line).
- `.planning/REQUIREMENTS.md` lines for MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03 — verbatim contract wording.
- `.planning/PROJECT.md` § "Current Milestone" + § "Key Decisions" — Membership `end_date` inclusive (carries forward to freeze date math); ARQ cron `unique=True` (NOT directly relevant, but governs cron-context); modular monolith layering.

### Phase 24 outputs (carry-forward locked)
- `.planning/phases/24-foundations-tech-debt-bedrock/24-CONTEXT.md` — D-24-01 (migration ownership), D-24-03 (`MEMBERSHIP_STATUS_TRANSITIONS` shape), D-24-04 (`_assert_can_transition` central guard), D-24-05 (thin per-action wrappers), D-24-18 (LOCKED_AUDIT_EVENTS layout — Phase 24 added the 6 v1.3 pairs).
- `.planning/phases/24-foundations-tech-debt-bedrock/24-PATTERNS.md` — pattern map for new files; Phase 25 reuses migration / service / router / test patterns established там.
- `.planning/phases/24-foundations-tech-debt-bedrock/24-DISCUSSION-LOG.md` — Phase 24 audit trail.

### Codebase contracts (read before editing)
- `apps/backend/app/core/audit.py:78-145` — `LOCKED_AUDIT_EVENTS` frozenset; `("membership_frozen", "membership")` + `("membership_unfrozen", "membership")` already present (Phase 24 D-24-18); Phase 25 adds callsites.
- `apps/backend/app/core/exceptions.py:158-181` — `InvalidTransitionError` (reuse for `invalid_transition`); `MembershipNotFoundError` (reuse for 404). Phase 25 adds `FreezeLimitExceededError` + `AlreadyFrozenError` here (D-25-21).
- `apps/backend/app/modules/memberships/constants.py` — `MEMBERSHIP_STATUS_TRANSITIONS` from Phase 24 D-24-03 with placeholder; Phase 25 fills `active → frozen` and `frozen → {active, cancelled}` edges (D-25-14).
- `apps/backend/app/modules/memberships/models.py:85-161` — `Membership.__table_args__` CHECK admits 'frozen' (Phase 24 D-24-02); `__tablename__ = "memberships"`; composite index `ix_memberships_client_id_status_end_date`. Phase 25 adds `freeze_days_limit_snapshot` column + new `MembershipFreezePeriod` ORM model.
- `apps/backend/app/modules/memberships/service.py:105-138` — `_assert_can_transition` central guard + thin wrappers; Phase 25 reuses for freeze/unfreeze/cancel-from-frozen.
- `apps/backend/app/modules/memberships/service.py:394-449` — existing `cancel_membership`; Phase 25 D-25-09 extends to handle frozen source (close period, emit unfrozen audit, then existing cancel flow).
- `apps/backend/app/modules/memberships/service.py:480-508` — `resolve_active_membership_by_client` (Phase 17 + Phase 24 DEBT-01); **NO change в Phase 25** (D-25-17) — frozen rows naturally excluded.
- `apps/backend/app/modules/memberships/repository.py:316-352` — `find_active_for_client` (resolver underlying query). NO change.
- `apps/backend/app/modules/memberships/repository.py:240-290` — list_memberships query builder; D-25-18 extends с freeze aggregate subquery for `freezeDaysUsed`/`freezeDaysRemaining` columns.
- `apps/backend/app/modules/memberships/router.py:259-311` — existing `create_membership` + `cancel_membership` endpoints; Phase 25 adds two new endpoints same shape (D-25-19).
- `apps/backend/app/modules/memberships/schemas.py:139-145` — `MembershipStatus` enum; Phase 25 adds `FROZEN = "frozen"` (D-25-13).
- `apps/backend/app/modules/memberships/schemas.py:207-265` — `MembershipResponse` + `MembershipListQuery` (Phase 24 already added `expiring`/`within`); Phase 25 extends `MembershipResponse` с 4 freeze fields (D-25-12).
- `apps/backend/alembic/versions/0007_status_taxonomy.py` — Phase 24's migration; Phase 25's `0008_freeze.py` revises from `0007_status_taxonomy` (D-25-01 chain).
- `apps/backend/alembic/versions/0004_membership_plans.py` — partial unique index pattern via `op.execute()` (`uq_membership_plans_name_alive`); Phase 25's `uq_membership_freeze_periods_active_per_membership` mirrors this approach (D-25-05).
- `apps/backend/alembic/versions/0005_memberships.py` — Membership table creation; reference for ORM-table_args / migration symmetry.
- `apps/backend/alembic/env.py` — `_include_object` suppression for partial unique indexes (autogenerate skips them so they don't reappear as unwanted ops in future revisions).
- `apps/backend/app/modules/visits/service.py:160-180` — `NoActiveMembershipError` raise site (resolver returns None → 409); Phase 25 verifies frozen path triggers same code path via integration test.
- `apps/backend/app/integrations/telegram/handlers.py:330-345` — Telegram `/checkin` handler; oracle-safe DMs (Phase 20 D-5); frozen → generic DM (no oracle leak — same as stranger / no-active path).
- `apps/backend/tests/unit/memberships/test_state_machine.py` — 9-cell parametrize matrix (Phase 17 + Phase 24); Phase 25 D-25-15 extends to 16-cell.
- `apps/backend/tests/unit/test_service_commit_gate.py:167-211` — SVC001 walker `_INSPECTED_SERVICES`; `memberships/service.py` already in scope. New freeze/unfreeze public functions get `await session.commit()` (D-25-07 step 9, D-25-08 step 11).
- `apps/backend/tests/integration/memberships/` — existing integration test directory; Phase 25's 6 new test files land here.

### Frontend contract (Phase 25 NOT touching, reference only for Phase 28 readiness)
- `apps/admin-web/src/shared/api/services/types/memberships.ts` — TypeScript types; Phase 28 (FE-10/FE-11) regenerates from new openapi.json.
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — mock service; Phase 28 syncs `frozen` status + freeze fields.

### Prior decisions still in force (carried from v1.2 + Phase 24)
- `.planning/STATE.md` § "Decisions" — Membership `end_date` inclusive; modular monolith; `import-linter` enforced; SVC001 commit-gate; AST literal-string audit gate; cross-module callbacks via Protocol+composition root.
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 17" — MEM-04 resolver tiebreak (Phase 26 will extend; Phase 25 leaves as-is).
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 19" — visits DB-level race-proof pattern (`UNIQUE` index + IntegrityError translation); Phase 25 freeze race uses same pattern.
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 20" — Telegram oracle-safe DM strings (Phase 25 frozen path inherits, no new copy needed).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_assert_can_transition(membership, *, target)`** at `service.py:105-122` — Phase 24 central guard; Phase 25 calls directly (or via thin `_assert_can_freeze`/`_assert_can_unfreeze` wrappers per D-25-15).
- **`InvalidTransitionError(ConflictError)`** at `exceptions.py:158-173` — already returns 409 `invalid_transition` with `from_status`/`to_status` fields. Reuse, do NOT add a parallel exception для freeze transitions.
- **Partial unique index pattern** at `0004_membership_plans.py` (`uq_membership_plans_name_alive`) — `op.execute("CREATE UNIQUE INDEX … WHERE deleted_at IS NULL")` + `__table_args__ Index(postgresql_where=...)` mirror; Phase 25's `uq_membership_freeze_periods_active_per_membership` shipping identically.
- **`_is_plan_name_conflict` / `_is_plan_in_use_conflict`** at `service.py:74-102` — IntegrityError discrimination via `getattr(exc.orig, "constraint_name", None)` + substring fallback. Phase 25's `_is_already_frozen_conflict` is a direct mirror.
- **`update_membership_status(session, membership, *, status, cancelled_at, cancel_reason)`** at `repository.py:293-313` — narrow setter; Phase 25 calls с `status="frozen"` (no other fields) and `status="active"` for unfreeze. NO need to extend setter signature.
- **`audit.emit` literal-string AST gate** at `tests/unit/test_audit_taxonomy.py` — Phase 24 pre-registered the 6 v1.3 pairs; Phase 25 callsites pass naturally.
- **`_expire_due_memberships(today=None)` injection pattern** at `service.py:516-575` — canonical example for Europe/Moscow `date()` defaulting; freeze service paths use `datetime.now(tz=UTC)` (TIMESTAMPTZ) but `today_msk` injection mirrors for freeze-day computation.
- **MEMBERSHIP_STATUS_TRANSITIONS placeholder** at `constants.py:21-28` — Phase 24 left `frozen: frozenset()` and `active: frozenset({expired, cancelled})` ready for Phase 25 fill-in (D-25-14).
- **`MembershipResponse` schema** at `schemas.py:207-229` — current shape; Phase 25 adds 4 fields without altering existing camelCase wire format (BackendSchemaBase handles the snake_case → camelCase mapping for new fields automatically).
- **`MembershipStatus` enum** at `schemas.py:139-144` — Phase 25 adds `FROZEN` value; consumers (filters, list query) automatically work with new value (Phase 17 used StrEnum so JSON wire stays "frozen" lowercase).

### Established Patterns

- **Migration CHECK + partial unique index** — Postgres-specific, `op.execute()` для both; ORM `__table_args__` updated for declarative awareness; alembic env.py `_include_object` suppresses autogenerate echo. Phase 25's `0008_freeze.py` follows этот pattern для freeze period unique-active-per-membership index.
- **Service layer commit ordering** — `repository.<insert/mutate>` → `session.flush()` → `audit.emit()` → `session.refresh(<for response>)` → `session.commit()`. Mirror Phase 17 / Phase 24 для freeze/unfreeze public functions (SVC001 commit-gate enforces).
- **State-machine 4×4 matrix** — Phase 17's 9-cell extends к 16-cell (4 statuses × 4 actions: expire/cancel/freeze/unfreeze). One parametrize matrix → exhaustive coverage.
- **DB-level race protection** (Phase 19 visits pattern) — `UNIQUE` constraint + IntegrityError translation; Phase 25 freeze race test uses same pattern (concurrent INSERT, partial unique catches second).
- **Audit payload UUID stringification** — UUIDs not natively JSON-serialisable; cast `client_id`, `freeze_period_id` к str for JSONB. `resource_id` stays UUID (column type).
- **Pagination envelope** — list endpoint always returns `PaginatedData[T] = {items, total, page, pageSize}`; Phase 25's freeze-augmented responses keep envelope intact.
- **Camelcase wire format via BackendSchemaBase** — `freeze_days_limit_snapshot` Python → `freezeDaysLimitSnapshot` JSON automatic; admin-web TS contract types regenerated в Phase 28.

### Integration Points

- **Resolver dispatch** — `app/core/dependencies.py:get_active_membership_for_request` consumed by reception POST `/api/v1/visits` (Phase 19) AND Telegram `/checkin` (Phase 20). Phase 25 leaves resolver unchanged; frozen rejection через existing `status='active'` filter. Integration test asserts оба paths return generic "no active membership" response.
- **`memberships_router` mounting** — `app/api/v1/router.py` mounts `memberships_router` at `/memberships`; new `/freeze` + `/unfreeze` endpoints inherit prefix automatically. NO router file outside `memberships/` needs editing.
- **Plan-archived edge case** — MEM-FRZ-03 backfill uses `COALESCE(plan.freeze_days_limit, 14)` для archived plans (LEFT JOIN на membership_plans). Mirrors snapshot-pricing rationale: existing memberships don't lose freeze rights when plan archived.
- **Alembic chain** — `0007_status_taxonomy` head → `0008_freeze` (Phase 25). Phase 26 plan agent creates `0009_renewal` revising from `0008_freeze` (D-25-01 — Phase 25 supersedes the milestone roadmap's "shared `0007`" assumption).
- **OpenAPI surface** — Phase 25 adds 2 endpoints + 4 fields on existing schema; openapi.json drift visible. Phase 28 (FE drift-gate refresh) collects cumulative changes; D-25-25 leaves Phase 25-time regen as a planner discretion (commit it if CI demands per-commit drift, else defer to Phase 28).

</code_context>

<specifics>
## Specific Ideas

- **"Half-day rounds up" interpretation:** REQUIREMENTS MEM-FRZ-05 wording is loose. Phase 25 lock: seconds-based `math.ceil(delta_seconds / 86400)` с минимум 1. Justification: client never loses partial days (anti-abuse-favouring rounding); seconds-based evades MSK calendar-boundary nuance (UTC+3 fixed since 2014, no DST → same answer either way); minimum-1 prevents "instant freeze-unfreeze" loops from gaining unbounded extension days at zero cost (anti-fraud, mirrors Phase 19 visits 1/day rule philosophy).
- **`days_added=0` sentinel для cancel-during-freeze:** preserves stable `membership_unfrozen` payload schema; cancel context implied by adjacent `membership_cancelled` event in same transaction. Future audit-log analysis tools detect this pair via SQL `WHERE event='membership_unfrozen' AND days_added = 0` and join к neighbouring `membership_cancelled` row.
- **Preventive limit guard, not post-hoc:** ставим guard на `freeze_membership` (D-25-07 step 3), not on `unfreeze_membership`. Rationale — UX: клиент знает immediately если limit исчерпан, без открытия period. Theoretical race (limit=14, used=13, two concurrent freezes) impossible because partial unique index serializes одновременные инсерты на одной membership; second freeze gets `already_frozen` (not `freeze_limit_exceeded`).
- **Phase 24 D-24-25 OpenAPI regen pattern carries over:** Phase 25 plan agent confirms CI drift-gate behaviour via `gh workflow view ci.yml` (или similar); если per-commit gate, regen openapi.json в last commit; иначе defer к Phase 28.
- **Resolver — NO touch:** the most error-prone part of v1.3 is the resolver (3 phases serialised — 24/25/26 each touch it). Phase 25 expressly contributes ZERO resolver code (D-25-17). Frozen rejection is "free" — `status='active'` filter уже исключает frozen rows. This keeps the resolver's serialized-touchpoint discipline intact (Phase 24 = `end_date >= today`; Phase 25 = nothing; Phase 26 = tiebreak).
- **Migration `0008_freeze.py` is the ONLY user-facing schema change** в Phase 25 — backfill UPDATEs run on existing `memberships` rows (production data). Plan agent should mention в plan body: backup-before-deploy reminder + downgrade path documented but data-lossy. Mirror Phase 17 D-19 production-readiness checklist.

## Risks / Watchpoints (for planner)

- **`MembershipFreezePeriod.created_at` collision with `started_at`:** TimestampMixin gives `created_at`; `started_at` is also set at INSERT time. They will be near-identical but distinct (created_at = SQLAlchemy default; started_at = explicit Python `datetime.now(tz=UTC)`). Document semantic difference в model docstring (audit row wallclock vs operational period start). Tests should not assume equality.
- **Backfill `freeze_days_limit_snapshot=14` for archived-plan rows** is a value lock-in: if owner later un-archives a plan + edits its `freeze_days_limit`, snapshot rows still carry 14. This is correct (snapshot semantics) — but plan agent should note in migration docstring that backfill isn't lossy для preserved snapshot intent.
- **Resolver `find_active_for_client` index coverage** — composite index `(client_id, status, end_date DESC)` already filters frozen rows out via status predicate; no new index needed in Phase 25. BUT — if Phase 26 changes resolver к include frozen rows для some flow (it shouldn't per CONTEXT, но planner verifies), index may become inadequate. Phase 25 leaves it alone.
- **Ceil-rounding test coverage:** edge case `period.started_at == period.ended_at` (instant unfreeze, network-induced) → `delta_seconds=0` → `ceil(0/86400)=0` → enforce min=1 explicit (D-25-08 step 5). Test must cover.
- **Cancel-during-freeze atomicity** — TWO audit emits + status change в одном UoW; if `audit.emit("membership_unfrozen")` fails between unfreeze period close и cancel mutation, transaction rolls back cleanly (single commit at end). Plan agent verifies by inserting deliberate flush failure between steps in test (advanced; optional).
- **Plan-agent docstring update for `_assert_can_cancel`** — Phase 17's docstring says "only status='active' may transition to 'cancelled'". Phase 25 makes this incorrect ("active или frozen"). Plan agent updates docstring при заменe transition guard call sites.
- **`0008_freeze.py` ordering with backfill UPDATE:** the UPDATE на `memberships.freeze_days_limit_snapshot` runs WHILE column nullable; setting NOT NULL afterwards. If the table is huge (>>1M rows), this blocks; для пет-проекта (<<1K rows) cost negligible. Plan agent notes for prod scale considerations.
- **`audit.py` docstring lines 57+59 vs Phase 25 actual payload field names** — docstring предлагает `freeze_days` / `resumed_at`; Phase 25 ships `days_added` / `started_at`. Planner либо updates docstring к match, либо documents intentional divergence.
- **OpenAPI drift на FreezePeriodResponse + extended MembershipResponse:** ~6 new schema additions, ~2 new path operations. Phase 28's drift-gate refresh accumulates; Phase 25 plan agent confirms gate behaviour (D-25-25).

</specifics>

<deferred>
## Deferred Ideas

- **Auto-unfreeze cron** — no requirement в v1.3; manual unfreeze only. Could be v1.4 if support burden grows (operator forgets to unfreeze, client returns).
- **Operator-facing freeze reason field** — `POST /freeze` body is empty per REQUIREMENTS MEM-FRZ-EP-01. Adding optional `reason` would require schema work + audit payload extension; backlog if reception requests it post-launch.
- **Freeze period editing** (e.g. "I made a mistake, started 2 days early") — out of scope; only freeze + unfreeze. Audit trail integrity preferred over operator convenience.
- **Multiple concurrent freezes** — explicitly prevented by partial unique index; no v1.3 use-case for "stack two freeze periods". If business case emerges, separate phase needs to redesign cumulative-days accounting.
- **Telegram bot exposing `/freeze` self-serve command** — not in v1.3 scope. Reception/owner-only через admin-web (Phase 28 FE-10) — clients ask staff. v1.4 candidate if customer-facing portal materializes (но `apps/client-web` only появляется в Phase J per PROJECT.md "Out of Scope").
- **Renewal during freeze** — Phase 26 (MEM-REN-02) explicitly allows `frozen` source for renewal. Phase 25 ensures `frozen` status existence + transition consistency, but renewal logic is Phase 26's territory. Cross-phase test (`freeze → renew while frozen → unfreeze later`) lives в Phase 29 milestone verification.
- **Notifications on freeze/unfreeze** — not in v1.3. Could be added в Phase 27's notification layer if owner requests, но no current ask.
- **Cancel-during-freeze charge-back / refund logic** — financial operations out of scope (no billing module in v1.3); cancellation is gym-internal only.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 25` not run interactively in --auto mode; will surface in plan-phase if matches exist.

</deferred>

---

*Phase: 25-memberships-freeze-backend*
*Context gathered: 2026-05-08 (auto mode — recommended defaults selected by Claude)*
