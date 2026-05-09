# Phase 26: Memberships — Renewal (backend) - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude)

<domain>
## Phase Boundary

Reception/owner может продлить membership одной кнопкой — backend создаёт follow-up row со snapshot **текущей** цены плана, резолвер корректно отдаёт текущий membership пока он ещё жив и переключается на renewal только после `end_date`. Backend-only — UI wiring живёт в Phase 28 (FE-12 / FE-13).

Phase 26 ships:

1. **MEM-REN-01** — Alembic migration `0009_renewal.py` добавляет `previous_membership_id` UUID NULL FK `memberships.id` ON DELETE SET NULL — audit-цепочка для renewal. Никаких других колонок (snapshot pricing уже NOT NULL после Phase 17; `freeze_days_limit_snapshot` уже NOT NULL после Phase 25 `0008_freeze`).
2. **MEM-REN-02** — `service.renew_membership(session, source_membership_id, actor)`: load source → 404 `membership_not_found` if missing; allowed source statuses ∈ {`active`, `frozen`, `expired`}; `cancelled` → 409 `cannot_renew_cancelled`; load current plan via `repository.get_alive(session, source.plan_id)` — 404 `plan_not_found` if hard-deleted, 409 `plan_archived` if `deleted_at IS NOT NULL`; snapshot **current** plan fields (`name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`, `freeze_days_limit_snapshot`); insert new membership с `previous_membership_id = source.id`, `status='active'`.
3. **MEM-REN-03** — Resolver tiebreak: при нескольких active membershipах с `end_date >= today` приоритет у row'а с **меньшим** `start_date` (тот, что сейчас "идёт"); затем `created_at DESC`. Чек-ин использует current до `end_date`, потом естественно переключается на renewal.
4. **MEM-REN-04** — Renewal of `expired` source: `start_date = today (Europe/Moscow)` (NOT `source.end_date + 1`) — новый membership начинается сразу, не ретроактивно. `audit.emit` payload включает `start_date_strategy='from_today_expired_source'`. Для active/frozen source — `start_date_strategy='from_source_end_date'`.
5. **MEM-REN-EP-01** — `POST /api/v1/memberships/{id}/renew` (CSRF, `(CREATE, MEMBERSHIPS)` → reception+owner); пустое тело; **201 Created** + `ResponseEnvelope[MembershipResponse]` с новым row'ом.
6. **MEM-REN-AUDIT-01** — `audit.emit("membership_renewed", actor, source_membership_id, new_membership_id, source_plan_id, current_price_kopecks, start_date_strategy)`; event уже pre-registered в `LOCKED_AUDIT_EVENTS` (Phase 24 INFRA-15, audit.py:142).
7. **MEM-REN-TEST-01..04** — full coverage: renewal-of-active, price-changed-between-sale-and-renewal (snapshot uses CURRENT plan price), expired-source-from-today, и rejection paths (cancelled source → 409 `cannot_renew_cancelled`; archived plan → 409 `plan_archived`).

**Out of Phase 26:**
- OpenAPI byte-stable refresh + admin-web "Продлить" кнопка — Phase 28 (FE-12).
- Notifications on renewal (e.g. "Спасибо за продление" DM) — нет в v1.3 scope; backlog.
- ARQ-инициированный auto-renew — не поддерживаем (always operator-initiated).
- Любые изменения payment / billing flow (никакого billing модуля в v1.3 — `paid_at` / `notes` остаются operator-fillable как сегодня).
- Изменения `MEMBERSHIP_STATUS_TRANSITIONS` — renewal не транзишит source row, а создаёт новый. State machine остаётся 4×4 (Phase 25 D-25-14) без изменений.

</domain>

<decisions>
## Implementation Decisions

### Migration scope & numbering

- **D-26-01:** Phase 26 owns Alembic migration `0009_renewal.py` — **renewal-only**, единственная schema change — добавление колонки `previous_membership_id`. Chain: `0007_status_taxonomy` → `0008_freeze` → `0009_renewal` → `0010_notifications` (Phase 27).
  - **Rationale:** mirrors Phase 25 D-25-01 — отдельные миграции на phase boundary, чтобы каждая phase shippable независимо. Bundling `previous_membership_id` в `0008_freeze` (изначальный milestone roadmap план "share migration `0007`") уже был superseded Phase 25 D-25-01; Phase 26 продолжает ту chain.
  - **Note для plan-агента:** `.planning/milestones/v1.3-ROADMAP.md` § "Build Order" / § "Notes on dependencies" уже обновлён Phase 25 (D-25-01); Phase 26 plan agent verifies + при необходимости finalizes wording (e.g. "Phase 26 ships `0009_renewal.py`").
- **D-26-02:** Migration `0009_renewal.py` upgrade order:
  1. `op.add_column("memberships", sa.Column("previous_membership_id", postgresql.UUID(as_uuid=True), nullable=True))` — nullable из коробки (existing rows не имеют source).
  2. `op.create_foreign_key("fk_memberships_previous_membership_id_memberships", "memberships", "memberships", ["previous_membership_id"], ["id"], ondelete="SET NULL")` — self-FK; ON DELETE SET NULL чтобы удаление source row (если когда-нибудь покупка hard-deleted) не сносило chain.
  3. `op.create_index("ix_memberships_previous_membership_id", "memberships", ["previous_membership_id"])` — supports forensic lookup `WHERE previous_membership_id = ?`; nullable column так что partial index на `WHERE previous_membership_id IS NOT NULL` ещё лучше для размера, но cost-benefit minimal на пет-проект scale → simple non-partial index. Plan agent может выбрать partial если хочет (Claude's discretion).
  4. ORM `Membership.__table_args__` updates + добавление атрибута `previous_membership_id: Mapped[UUID | None]` в models.py.
  5. Schema-layer `MembershipResponse` extends с `previous_membership_id: UUID | None = None` (auto-camelCased к `previousMembershipId` через BackendSchemaBase).
- **D-26-03:** Downgrade reverses в обратном порядке: drop_index → drop_constraint → drop_column. Без data-loss restoration (downgrade — disaster recovery; renewal chain attribution теряется, но row'ы остаются).

### `previous_membership_id` semantics

- **D-26-04:** `previous_membership_id` — **immutable post-creation** (как `plan_id`/snapshot fields). NO update path; NO PATCH endpoint touches it. Set ровно один раз — на INSERT через `service.renew_membership`.
- **D-26-05:** Self-FK on the same table (`memberships(previous_membership_id) → memberships(id)`). Naming convention expansion даст `fk_memberships_previous_membership_id_memberships`. PostgreSQL allows self-FK без cycle issues; ON DELETE SET NULL гарантирует, что hard-delete source (нынешняя schema запрещает hard-delete через ORM, но DBA-direct surgery возможна) не каскадирует.
- **D-26-06:** **Multi-hop chains allowed implicitly** — если client продлевает renewal (renew of renewal), `previous_membership_id` указывает на ближайший source. Chain reconstruction = recursive CTE / N-step traversal. Phase 26 НЕ добавляет helper для chain walk (нет requirement); если в будущем понадобится "show full history of this client's memberships in chronological renewal chain", добавим repo helper. Backlog noted.

### Source status acceptance + plan resolution

- **D-26-07:** Allowed source statuses (per REQUIREMENTS MEM-REN-02): `active`, `frozen`, `expired`. Rejected: `cancelled` → `CannotRenewCancelledError("cannot_renew_cancelled")` 409.
  - **Rationale:** cancelled is terminal + intentional revocation; renewing бы masked/обходил cancellation intent. Если клиент меняет mind после cancel, продаёт NEW membership (`POST /api/v1/memberships`), не renewal.
  - **`expired` is renewable:** common flow — client пропустил expiry на пару дней, приходит, оператор делает renewal с `start_date=today`. UX prefers single button над "продай новый" path.
  - **`frozen` is renewable:** клиент заморозил на отпуск, хочет купить продление заранее. Renewal сидит в `previous_membership_id`-цепочке; resolver MEM-REN-03 предпочтёт frozen current до его unfreeze + end_date passing, потом switches на renewal.
- **D-26-08:** Plan resolution via `repository.get_alive(session, source.plan_id)`:
  - **None (hard-delete или never-existed):** raise `PlanNotFoundError("plan_not_found")` 404. Practically невозможно (plan FK ON DELETE RESTRICT), но defence-in-depth.
  - **Returned, but `deleted_at IS NOT NULL`:** wait — `get_alive` уже filters `deleted_at IS NULL`. Significantly: archived plan returns None from `get_alive`. Need different signal.
  - **Decision:** load plan через NEW repo helper `repository.get_plan_for_renewal(session, plan_id) -> tuple[MembershipPlan | None, bool]` returning `(plan, is_archived)`:
    ```python
    async def get_plan_for_renewal(
        session: AsyncSession, plan_id: UUID
    ) -> tuple[MembershipPlan | None, bool]:
        """Read plan ignoring soft-delete; return (plan, is_archived) for renewal classification (D-26-08).

        Phase 26 needs to discriminate "plan never existed" (404 plan_not_found)
        from "plan exists but archived" (409 plan_archived). `get_alive` collapses
        both to None, so renewal uses this helper instead.
        """
        stmt = select(MembershipPlan).where(MembershipPlan.id == plan_id)
        plan: MembershipPlan | None = await session.scalar(stmt)
        if plan is None:
            return (None, False)
        return (plan, plan.deleted_at is not None)
    ```
  - Service: `(None, _)` → 404 `plan_not_found`; `(_, True)` → 409 `plan_archived`; `(plan, False)` → proceed.
  - **Note: plan `active=False` (not archived, just inactive)** — REQUIREMENTS MEM-REN-02 silent. Decision: **allow renewal** of inactive plan. Rationale: `active=False` pauses NEW sales (clients can't pick this plan from the catalogue for fresh purchases), but existing memberships continue их lifecycle including renewal — owner может toggle plan inactive temporarily без cancelling всех renewals. If owner wants to block renewals for plan, they archive (soft-delete) it. Document in service docstring.
- **D-26-09:** New exception class в `app/core/exceptions.py`:
  ```python
  class CannotRenewCancelledError(ConflictError):
      """Raised on POST /memberships/{id}/renew when source membership status is 'cancelled'.

      Phase 26 MEM-REN-02. Rationale: cancellation is terminal/intentional;
      renewal would mask the cancellation intent.
      """
      code = "cannot_renew_cancelled"
      status_code = 409
  ```
  - `PlanArchivedError` is **NEW** as well (existing `PlanInactiveError` semantically wrong — that's `active=False`, не archived):
    ```python
    class PlanArchivedError(ConflictError):
        """Raised on POST /memberships/{id}/renew when source.plan is soft-deleted (deleted_at IS NOT NULL).

        Phase 26 MEM-REN-02 / D-26-08. Renewal cannot use a plan that owner archived.
        Operator must sell a new membership using a current alive plan instead.
        """
        code = "plan_archived"
        status_code = 409
    ```
  - Existing `PlanNotFoundError` reused для null-plan case; existing `MembershipNotFoundError` для null-source.

### Date computation

- **D-26-10:** Date strategy decision tree:
  - **Source status ∈ {`active`, `frozen`}:** `start_date = source.end_date + timedelta(days=1)` (Europe/Moscow `date` arithmetic; no TZ conversion needed because `end_date` is `date` not `datetime`). Strategy literal: `"from_source_end_date"`.
  - **Source status == `expired`:** `start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()`. Strategy literal: `"from_today_expired_source"`.
- **D-26-11:** `end_date = start_date + timedelta(days=plan.duration_days - 1)` — INCLUSIVE end-date semantic carried forward from v1.2 (PROJECT.md Key Decisions; mirrors `service.create_membership` line 482).
- **D-26-12:** Why `from_today` for expired: ретроактивный `start_date = source.end_date + 1` дал бы `end_date < today` если source истёк давно — клиент платит за membership, который мгновенно expires. UX-anti-pattern. Lock на "renewal of expired starts today" гарантирует, что клиент всегда получает full duration_days с момента покупки.
- **D-26-13:** `start_date_strategy` literal values frozen в module-level constants для AST-safety (audit payload accepts variables, не literals — но строки в payload сами должны быть stable):
  ```python
  # apps/backend/app/modules/memberships/constants.py (extends Phase 24 file)
  RENEWAL_STRATEGY_FROM_SOURCE_END_DATE = "from_source_end_date"
  RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE = "from_today_expired_source"
  ```
  Used by service.renew_membership + by tests asserting audit payload values.

### Service-layer flow (MEM-REN-02)

- **D-26-14:** `service.renew_membership(session, source_membership_id, actor) -> MembershipResponse`:
  1. Load source via `repository.get_membership(session, source_membership_id)` — 404 `membership_not_found` if missing.
  2. **Source-status guard:**
     ```python
     if source.status == "cancelled":
         raise CannotRenewCancelledError("cannot_renew_cancelled")
     if source.status not in {"active", "frozen", "expired"}:
         # defence-in-depth — keeps source-acceptance set explicit
         raise InvalidTransitionError("invalid_renewal_source", from_status=source.status, to_status="renew")
     ```
     **NO** call to `_assert_can_transition` — renewal is NOT a status transition on source row; source row остаётся в покое.
  3. Load plan via `repository.get_plan_for_renewal(session, source.plan_id)` (D-26-08).
  4. Compute dates (D-26-10..D-26-12) — pick strategy by source status.
  5. INSERT new membership через `repository.insert_renewal_membership(session, *, source, plan, start_date, end_date)` — see D-26-16.
  6. `await session.flush()` — surfaces FK errors (e.g. self-FK constraint).
  7. `audit.emit("membership_renewed", ..., **renewal_payload)` — payload schema D-26-15.
  8. `await session.refresh(new_membership, attribute_names=["created_at", "updated_at"])`.
  9. `await session.commit()` — SVC001 gate enforces explicit commit.
  10. Return `await _build_membership_response(session, new_membership)` — same projection helper Phase 25 уже использует (включая freeze fields, которые на новой membership всегда `freezeDaysUsed=0`, `currentFreezePeriod=None`, `freezeDaysRemaining=snapshot_limit`).
- **D-26-15:** Audit payload (MEM-REN-AUDIT-01 canonical):
  ```python
  await audit.emit(
      session,
      "membership_renewed",  # LITERAL — Phase 15 INFRA-11 AST gate; pre-registered Phase 24 audit.py:142
      actor_user_id=actor.id,
      resource_type="membership",  # LITERAL
      resource_id=new_membership.id,           # NEW row's id
      client_id=str(new_membership.client_id), # str-cast for JSONB
      source_membership_id=str(source.id),     # str-cast
      source_plan_id=str(source.plan_id),      # str-cast
      current_price_kopecks=plan.price_kopecks, # int (from current plan, NOT source.price_kopecks_snapshot)
      start_date_strategy=strategy_literal,    # one of D-26-13 constants
  )
  ```
  - **Why `resource_id = new_membership.id` (NOT source.id):** the audit row is "the renewal that was created"; forensic queries `WHERE event='membership_renewed' AND resource_id=...` answer "what was the renewal record". `source_membership_id` in payload provides back-pointer to source.
  - **`current_price_kopecks` is the plan's price at renewal time**, not the source's snapshot. This is the "if plan got more expensive, client pays new price" lock from PROJECT.md — explicitly captured in audit for forensics.
- **D-26-16:** New repo helper `repository.insert_renewal_membership(session, *, source, plan, start_date, end_date) -> Membership`:
  ```python
  async def insert_renewal_membership(
      session: AsyncSession,
      *,
      source: Membership,
      plan: MembershipPlan,
      start_date: date,
      end_date: date,
  ) -> Membership:
      """Insert a follow-up membership chained to `source` (Phase 26 D-26-16).

      Snapshots from CURRENT plan (price/duration/freeze_limit/name); copies
      client_id from source; NO snapshot from source's previous snapshots.
      previous_membership_id = source.id (immutable; D-26-04).

      Caller (service) owns flush + commit (D-14 / SVC001 gate).
      """
      new_membership = Membership(
          client_id=source.client_id,
          plan_id=plan.id,
          plan_name_snapshot=plan.name,
          duration_days_snapshot=plan.duration_days,
          price_kopecks_snapshot=plan.price_kopecks,
          freeze_days_limit_snapshot=plan.freeze_days_limit,
          start_date=start_date,
          end_date=end_date,
          status="active",  # always start active; resolver tiebreak (D-26-17) handles overlap
          previous_membership_id=source.id,
          activation_policy="purchase_date",  # default; matches CHECK constraint
      )
      session.add(new_membership)
      return new_membership
  ```
  - Mirrors `repository.insert_membership` shape; difference is +`previous_membership_id` and source-derived `client_id` (no separate `data: MembershipCreateRequest`).

### Resolver tiebreak extension (MEM-REN-03)

- **D-26-17:** `repository.find_active_for_client` ORDER BY changes:
  - **Current (Phase 17 + Phase 24 DEBT-01):** `ORDER BY end_date DESC, created_at DESC LIMIT 1`.
  - **New (Phase 26):** `ORDER BY start_date ASC, created_at DESC LIMIT 1`.
  - **Rationale:** the prior `end_date DESC` tiebreak preferred the LATER-ending row, which (for renewal stacking — current active + renewal active simultaneously) would jump straight to the renewal even while the current membership is still valid. Clients/operators expect check-in to use the running membership until it expires. `start_date ASC` ⇒ pick the row that started earliest = the currently-running one. After current's `end_date` passes, ARQ flips it `active → expired` (06:05 cron) → no longer matches `status='active'` filter → renewal naturally takes over.
  - **What about manual-stacking edge case (Phase 17 D-01 allowed)?** Two memberships sold "raw" without renewal linkage (operator sold the same plan twice — supported per Phase 17 D-01). With `start_date ASC` tiebreak, operator-second-sale WITH later start_date acts как renewal-style; older one runs first. Backwards-compatible if start_dates differ; if equal (same-day double-sale), `created_at DESC` tiebreaks к the LATER-created row — but оба валидны and only one wins; matches Phase 17 D-17 "silent tiebreak, no warning, no audit event". Document in repo docstring.
  - **Index adequacy:** `ix_memberships_client_id_status_end_date(client_id, status, end_date DESC)` covers `WHERE client_id=? AND status='active' AND end_date >= today` filter (Phase 24 DEBT-01) plus `LIMIT 1`. The new ORDER BY `start_date ASC` is NOT in the index, so executor will sort the post-filter set in memory. With expected cardinality (≤2 active rows per client), this is O(1). Phase 26 does NOT add a new index — added cost > benefit. Document in repo docstring.
- **D-26-18:** Function signature unchanged (`find_active_for_client(session, client_id, *, today)`); ONLY the ORDER BY changes. Public wrapper `service.resolve_active_membership_by_client` unchanged signature too — still injected via `core/dependencies.py` Protocol slot from `app/main.py` (Phase 17 D-18 / Phase 24 D-24-06).
- **D-26-19:** Resolver docstring updates Phase 24's "ORDER BY end_date DESC" wording → "ORDER BY start_date ASC" with explicit cite to Phase 26 D-26-17 + the renewal-stacking rationale. Also flags: "If you change resolver tiebreak again, update integration test test_resolver_tiebreak.py + cross-check Phase 27 expiring-cron query selects (NTF-02 reads memberships, but doesn't depend on tiebreak — it filters all matching rows, not LIMIT 1)."

### Endpoint signature + RBAC

- **D-26-20:** New endpoint на `memberships_router`:
  ```python
  @memberships_router.post(
      "/{membership_id}/renew",
      response_model=ResponseEnvelope[MembershipResponse],
      status_code=status.HTTP_201_CREATED,
      summary="Renew membership (reception+owner; 409 cannot_renew_cancelled / plan_archived; 404 plan_not_found / membership_not_found)",
  )
  async def renew_membership(
      membership_id: UUID,
      actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))],
      _csrf: Annotated[None, Depends(verify_csrf)],
      session: Annotated[AsyncSession, Depends(get_db)],
  ) -> ResponseEnvelope[MembershipResponse]:
      new_membership = await service.renew_membership(session, membership_id, actor)
      return ResponseEnvelope(data=new_membership)
  ```
  - **RBAC:** `(CREATE, MEMBERSHIPS)` — reception+owner per OWNER_ONLY (15 entries from Phase 22; CREATE на memberships НЕ в OWNER_ONLY). Mirrors REQUIREMENTS MEM-REN-EP-01 + Phase 25 freeze/unfreeze permission shape.
  - **CSRF:** `verify_csrf` dependency после `require_permission` (RBAC-04 ordering, mirrors freeze endpoint).
  - **Body:** empty (no Pydantic body schema; FastAPI accepts no body на POST).
  - **Status code:** `201 Created` (NOT 200 — semantically a new resource is created; mirrors `POST /memberships` line 263). REQUIREMENTS MEM-REN-EP-01 explicit: "returns 201".
  - **Response:** `ResponseEnvelope[MembershipResponse]` with the NEW membership row (full projection including `previousMembershipId` field).

### Schema / response shape

- **D-26-21:** `MembershipResponse` extends с `previous_membership_id: UUID | None = None` (BackendSchemaBase auto-camelCases к `previousMembershipId`). Default `None` — backward-compat on existing rows что не имеют source.
- **D-26-22:** No new request body schemas — `POST /renew` empty body. No new query-param schemas — list endpoint NOT extended in Phase 26 (filter by `previous_membership_id` not in v1.3 scope; backlog if needed for future "show all renewals of plan X" admin view).
- **D-26-23:** No `MembershipListQuery` change — existing filters (status, client_id, expiring/within from Phase 24 DEBT-02) уже достаточны для admin-web list views. Renewal chain is detail-page concern, not list filter.

### State-machine + audit registry (carry-forward; NO change)

- **D-26-24:** `MEMBERSHIP_STATUS_TRANSITIONS` (Phase 24 D-24-03 + Phase 25 D-25-14) **NOT touched** in Phase 26. Renewal creates a NEW row `status='active'` — это INSERT, не transition. Source row keeps its original status (active/frozen/expired); никакого `from → to` арки на source.
- **D-26-25:** `LOCKED_AUDIT_EVENTS` (`app/core/audit.py:142`) уже содержит `("membership_renewed", "membership")` — pre-registered Phase 24 INFRA-15 / D-24-18. Phase 26 ровно один callsite в `service.renew_membership`. AST literal-string gate (`tests/unit/test_audit_taxonomy.py`) автоматически pass'ит т.к. event ↔ resource_type pair already authorized.
- **D-26-26:** `audit.py` docstring lines 61-62 предлагает payload `{membership_id, client_id, plan_id, new_end_date}` для `membership_renewed`. Phase 26 ships richer payload (D-26-15: + `source_membership_id`, `current_price_kopecks`, `start_date_strategy`; — `new_end_date` because `resource_id = new_membership.id` сам carries id and `MembershipResponse` retrievable via id lookup). Plan agent updates the docstring при добавлении callsite — match actual payload field names. Mirrors Phase 25's similar docstring drift (D-25-27 closing).

### `_build_membership_response` reuse

- **D-26-27:** Renewal returns `await _build_membership_response(session, new_membership)` — Phase 25's helper уже включает 4 freeze projection fields. На свеженьком renewal row они будут:
  - `freeze_days_limit_snapshot`: copied from current plan (e.g. 14).
  - `freeze_days_used`: 0 (single SQL aggregate yields 0 — no periods exist для new id).
  - `freeze_days_remaining`: snapshot_limit (since used=0, clamped result = limit).
  - `current_freeze_period`: None (status='active', not 'frozen').
  - `previous_membership_id`: source.id (D-26-21 — populated for serialised response).
  - `cancelled_at`/`cancel_reason`: None (status='active').
  - `paid_at`/`notes`: None (no payment fields filled at renewal time; operator may PATCH later if endpoint exists or backlog if not).
- **D-26-28:** `_build_membership_response` signature unchanged. The single SQL aggregate it issues for `freeze_days_used` is a no-op (0 rows in `membership_freeze_periods` for new id) but still incurs ОДИН roundtrip — acceptable cost для consistency. Plan agent verifies path through helper, не shortcut.

### Test taxonomy

- **D-26-29:** Test files (planner finalises exact paths; proposals below mirror Phase 25 D-25-23 style):
  - `tests/integration/memberships/test_renewal_active.py` — **MEM-REN-TEST-01:** sell 30d at price=2000₽ → wait 5d → renew → assert `new.start_date == source.end_date + 1 day`, `new.end_date == new.start_date + 29 days`, snapshots equal source's, `previous_membership_id == source.id`, `status='active'`. Resolver returns source until source.end_date passes (clock-injection), then returns renewal.
  - `tests/integration/memberships/test_renewal_price_change.py` — **MEM-REN-TEST-02:** sell membership при plan.price=2000₽ → owner PATCH plan.price=3000₽ → renew → assert `new.price_kopecks_snapshot == 3000_00`, `audit.payload.current_price_kopecks == 3000_00`. Snapshot uses CURRENT plan price, NOT source snapshot.
  - `tests/integration/memberships/test_renewal_archived_plan.py` — **MEM-REN-TEST-03 part A:** sell membership → owner archives plan (DELETE) → renew → 409 `plan_archived`. **MEM-REN-TEST-03 part B:** cancel membership → renew → 409 `cannot_renew_cancelled`.
  - `tests/integration/memberships/test_renewal_expired_source.py` — **MEM-REN-TEST-04:** sell 30d → wait until past `end_date` → ARQ `expire_memberships` flips status='expired' (or test injects expired state) → renew → assert `new.start_date == today (Europe/Moscow)`, `audit.payload.start_date_strategy == "from_today_expired_source"`. Compare с active-renewal test where strategy = `"from_source_end_date"`.
  - `tests/integration/memberships/test_renewal_endpoint.py` — RBAC + CSRF matrix on POST `/renew`: anonymous → 401, reception → 201, owner → 201, CSRF missing → 403, missing source UUID → 404 `membership_not_found`. Response shape includes `previousMembershipId` field.
  - `tests/integration/memberships/test_renewal_resolver_tiebreak.py` — **MEM-REN-03 carry-forward:** insert active source ending in 5 days + active renewal starting in 6 days; assert resolver returns source (lower start_date wins); inject clock 6 days forward + ARQ expiry on source → resolver returns renewal.
  - `tests/integration/memberships/test_renewal_from_frozen.py` — frozen-source renewal: freeze active membership → renew → assert renewal created с `start_date = source.end_date + 1` (NOT today; frozen ≠ expired); source stays frozen; resolver still picks source (frozen → status filter excludes both → returns None; verify check-in path returns 409 `no_active_membership` until unfreeze). NOTE: this is the cross-flow Phase 25 D-25-deferred mentioned for Phase 29 verification; Phase 26 covers basic renewal-from-frozen happy path here, full integration sweep stays in Phase 29.
  - `tests/unit/memberships/test_renewal_constants.py` — асserts `RENEWAL_STRATEGY_*` constants exist + literal values frozen.

- **D-26-30:** **Clock injection для renewal tests:** same approach as Phase 25 (D-25-24) — recommend `monkeypatch` on `service._utc_now` / `service._today_msk` helper if introduced; otherwise inject explicit `today` arg into test-only path. Avoid `freezegun` per Phase 24 D-24-06 precedent.

### Endpoint route ordering

- **D-26-31:** Router file `apps/backend/app/modules/memberships/router.py` — add new endpoint AFTER existing `/{membership_id}/unfreeze` (line 358) per declaration order. Path `/{membership_id}/renew` does NOT conflict with prior `/{membership_id}/freeze` / `/unfreeze` / `/cancel` — distinct suffix. FastAPI route resolution is exact-match по path; no shadowing risk. OpenAPI summary follows Phase 25 freeze/unfreeze precedent (lists 409 codes inline для clarity).

### Frontend / OpenAPI implications

- **D-26-32:** Phase 26 backend changes → openapi.json drift: 1 new path operation (`POST /memberships/{id}/renew`) + 1 new schema field (`MembershipResponse.previousMembershipId`). Phase 28 owns cumulative drift-gate refresh (mirrors Phase 24 D-24-25 / Phase 25 D-25-25 pattern). Phase 26 plan agent decides whether to:
  - (a) regenerate openapi.json + commit as part of last Phase 26 commit (per-commit drift-gate friendliness), OR
  - (b) defer к Phase 28.
  - **Recommended:** (a) если CI gate runs per-commit, иначе (b). Plan agent confirms via `gh workflow view ci.yml` (or local recipe) — **NOT a blocker** для phase completion.
- **D-26-33:** Mock service `apps/admin-web/src/shared/api/services/mock/memberships.ts` is **NOT touched в Phase 26** — UI wiring + mock parity for renewal живут в Phase 28 (FE-12). Phase 26 ships pure backend; admin-web continues работать без "Продлить" кнопки до Phase 28 merge.

### Claude's Discretion (planner picks)

- Exact filename для unit/integration tests above (D-26-29 names — proposals only).
- Whether `get_plan_for_renewal` lives in `repository.py` (recommended) или separate `repository_renewal.py` module — recommend `repository.py` для consistency.
- Partial vs non-partial index on `previous_membership_id` (D-26-02 step 3) — non-partial is simpler; partial saves space на пет-проект scale negligible benefit.
- Whether to inline `RENEWAL_STRATEGY_*` constants в `constants.py` (D-26-13) или в a new `service.py`-local module-level — recommend `constants.py` для testability and AST-clarity (matches Phase 24 `MEMBERSHIP_STATUS_TRANSITIONS` placement).
- Whether to fold cross-flow "renewal-from-frozen" assertion into Phase 26 (D-26-29 last test) or defer all cross-flow к Phase 29 — recommend including in Phase 26 (basic happy path) + leaving deeper sweeps (e.g. unfreeze-then-renewal-takes-over) in Phase 29.
- Whether plan agent updates `audit.py` docstring lines 61-62 (D-26-26) at callsite addition — recommend yes (close docstring drift opened by Phase 24 pre-registration).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § "Phase 26" — phase summary + 5 success criteria.
- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 26" + § "Build Order" + § "Notes on dependencies" + § "Key Risks / Watchpoints" — milestone-scoped detail; resolver touch-point serialization (24→25→26); migration `0009_renewal.py` ownership confirmed (supersedes the original "shared `0007`" wording, already updated by Phase 25 D-25-01 + Phase 24 D-24-01).
- `.planning/REQUIREMENTS.md` § "Memberships — Renewal (MEM-REN)" — verbatim contract wording for MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04.
- `.planning/PROJECT.md` § "Current Milestone: v1.3" — renewal context: snapshot pricing берёт CURRENT plan price (если plan подорожал — клиент платит новую цену); modular monolith layering; Membership `end_date` inclusive.

### Phase 24 outputs (carry-forward locked)
- `.planning/phases/24-foundations-tech-debt-bedrock/24-CONTEXT.md` — D-24-01 (migration ownership chain), D-24-03 (`MEMBERSHIP_STATUS_TRANSITIONS` shape), D-24-04 (`_assert_can_transition` central guard — Phase 26 does NOT use for renewal because renewal is INSERT not transition), D-24-06 (resolver `today` injection pattern), D-24-07 (resolver `end_date >= today` filter — Phase 26 INHERITS), D-24-18 (LOCKED_AUDIT_EVENTS pre-registration of `membership_renewed`).
- `.planning/phases/24-foundations-tech-debt-bedrock/24-PATTERNS.md` — pattern map для new files; Phase 26 reuses migration / service / router / test patterns established там.

### Phase 25 outputs (carry-forward locked)
- `.planning/phases/25-memberships-freeze-backend/25-CONTEXT.md` — D-25-01 (Alembic chain `0007 → 0008 → 0009`; Phase 26 owns `0009_renewal.py`), D-25-12 (`MembershipResponse` shape with 4 freeze fields — Phase 26 reuses via `_build_membership_response`), D-25-14 (state machine 4×4 — Phase 26 NOT touching), D-25-19 (endpoint signature pattern — Phase 26 mirrors for `/renew`), D-25-deferred (renewal-from-frozen mentioned as Phase 29 cross-flow — Phase 26 covers basic happy-path test, full sweep stays in Phase 29).
- `.planning/phases/25-memberships-freeze-backend/25-PATTERNS.md` — pattern map; Phase 26 reuses freeze migration shape + service-layer ordering + integration test scaffolding.
- `.planning/phases/25-memberships-freeze-backend/25-VERIFICATION.md` — 14/14 must-haves verified баз (proves `_build_membership_response` is production-tested before Phase 26 reuses it).

### Codebase contracts (read before editing)

#### Audit + exceptions
- `apps/backend/app/core/audit.py:61-62` + `:142` — `membership_renewed` event docstring (preliminary payload schema; Phase 26 D-26-15 ships richer payload with `start_date_strategy`); `LOCKED_AUDIT_EVENTS` frozenset entry pre-registered Phase 24.
- `apps/backend/app/core/audit.py:65-189` — `AuditEventNotLockedError` hard-fail; `emit()` invariant — caller owns transaction (D-04 Phase 15).
- `apps/backend/app/core/exceptions.py:115-205` — `PlanNotFoundError` (reuse for renewal-of-null-plan); `PlanInactiveError` (NOT used by renewal — see D-26-08 inactive-plan-still-allowed); `MembershipNotFoundError` (reuse for null-source). Phase 26 ADDS `CannotRenewCancelledError` + `PlanArchivedError` (D-26-09).

#### Memberships module
- `apps/backend/app/modules/memberships/models.py:88-165` — `Membership` ORM; Phase 26 adds `previous_membership_id` Mapped column + self-FK in `__table_args__`. `__tablename__ = "memberships"`; CHECK constraint admits `frozen` (Phase 24 D-24-02); composite index `ix_memberships_client_id_status_end_date` covers Phase 26 resolver path (D-26-17 index-adequacy note).
- `apps/backend/app/modules/memberships/repository.py:51-58` — `get_alive` (collapses null + archived to None — Phase 26 needs differentiator, see D-26-08 new helper).
- `apps/backend/app/modules/memberships/repository.py:295-315` — `update_membership_status` (Phase 17 D-12 narrow setter); Phase 26 NOT calling on source (renewal не transitions source).
- `apps/backend/app/modules/memberships/repository.py:318-354` — `find_active_for_client` resolver query; Phase 26 D-26-17 changes ORDER BY `end_date DESC` → `start_date ASC` (with rationale + index-adequacy docstring update D-26-19).
- `apps/backend/app/modules/memberships/repository.py:362-398` — `expire_due_rows` Phase 18 ARQ helper; reference for `today` arg pattern (`date` not `CURRENT_DATE`).
- `apps/backend/app/modules/memberships/service.py:449-514` — `create_membership` (Phase 17 reference shape — server-compute dates Europe/Moscow, snapshot fields, `_build_membership_response`).
- `apps/backend/app/modules/memberships/service.py:517-600` — `cancel_membership` (Phase 17 + Phase 25 D-25-09 frozen-source extension; reference для transition guard placement BEFORE mutation; reference для two-event-in-one-UoW pattern, even though renewal emits only 1 event).
- `apps/backend/app/modules/memberships/service.py:608-690` — `freeze_membership` Phase 25 reference shape для new `renew_membership` (D-26-14 mirrors order: load → guard → flush → emit → refresh → commit).
- `apps/backend/app/modules/memberships/service.py:691-760` — `unfreeze_membership` Phase 25 reference; mirror.
- `apps/backend/app/modules/memberships/service.py:899-933` — `resolve_active_membership_by_client` (public wrapper registered at `core/dependencies.py` resolver slot via `app/main.py`); signature unchanged in Phase 26.
- `apps/backend/app/modules/memberships/service.py:192-258` — `_build_membership_response` (Phase 25 D-25-18 helper); Phase 26 reuses unchanged for renewal response (D-26-27).
- `apps/backend/app/modules/memberships/router.py:324-391` — Phase 25 freeze + unfreeze endpoint declarations; Phase 26 adds `POST /{membership_id}/renew` after these (D-26-31 ordering).
- `apps/backend/app/modules/memberships/schemas.py:158-165` — `MembershipStatus` enum incl. `FROZEN` (Phase 25 D-25-13).
- `apps/backend/app/modules/memberships/schemas.py:227-258` — `MembershipResponse`; Phase 26 D-26-21 extends с `previous_membership_id: UUID | None = None`.
- `apps/backend/app/modules/memberships/constants.py` — Phase 24 file housing `MEMBERSHIP_STATUS_TRANSITIONS`; Phase 26 D-26-13 appends `RENEWAL_STRATEGY_*` constants here.

#### Migrations
- `apps/backend/alembic/versions/0007_status_taxonomy.py` — Phase 24 head; Phase 25's `0008_freeze.py` revises from this.
- `apps/backend/alembic/versions/0008_freeze.py` — Phase 25 head; Phase 26's `0009_renewal.py` revises from this.
- `apps/backend/alembic/versions/0005_memberships.py` — original Memberships table creation; reference for ORM-table_args / migration symmetry + naming convention.
- `apps/backend/alembic/env.py` — `_include_object` autogenerate suppression list (no Phase 26 additions needed; new index/FK are stock declarative-friendly).

#### Resolver downstream consumers (verify NO regressions)
- `apps/backend/app/core/dependencies.py` — `get_active_membership_for_request` consumes resolver via `ActiveMembership` Protocol slot; Phase 26 leaves Protocol shape unchanged. Reception POST `/api/v1/visits` (Phase 19) AND Telegram `/checkin` (Phase 20) inherit new tiebreak automatically.
- `apps/backend/app/modules/visits/service.py:160-180` — `NoActiveMembershipError` raise site (resolver returns None → 409); Phase 26 verifies frozen-or-no-active flow stays oracle-safe.
- `apps/backend/app/integrations/telegram/handlers.py:330-345` — Telegram `/checkin` handler; oracle-safe DMs (Phase 20 D-5); renewal-stacking case naturally returns success DM с new days_remaining once renewal kicks in.

#### Tests
- `apps/backend/tests/unit/test_audit_taxonomy.py` — AST literal-string gate; Phase 26 callsite (`audit.emit("membership_renewed", ...)`) passes naturally because event/resource_type pair pre-registered Phase 24.
- `apps/backend/tests/unit/test_service_commit_gate.py:167-211` — SVC001 walker scope; `memberships/service.py` already in `_INSPECTED_SERVICES`. Phase 26's `renew_membership` public function gets `await session.commit()` (D-26-14 step 9).
- `apps/backend/tests/unit/memberships/test_state_machine.py` — Phase 25 16-cell matrix; Phase 26 NOT extending (renewal is INSERT, not transition).
- `apps/backend/tests/integration/memberships/` — Phase 26's 6-7 new integration test files land here (D-26-29).

### Frontend contract (Phase 26 NOT touching, reference only for Phase 28 readiness)
- `apps/admin-web/src/shared/api/services/types/memberships.ts` — TypeScript types; Phase 28 (FE-12) regenerates from new openapi.json.
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — mock service; Phase 28 syncs renewal endpoint + `previousMembershipId` field for offline parity.

### Prior decisions still in force (carried from v1.2 + Phase 24 + Phase 25)
- `.planning/STATE.md` § "Decisions" — Membership `end_date` inclusive; modular monolith; `import-linter` enforced; SVC001 commit-gate; AST literal-string audit gate; cross-module callbacks via Protocol+composition root.
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 17" — MEM-04 resolver tiebreak (Phase 26 extends; original `end_date DESC` documented there reverses to Phase 26 D-26-17).
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 19" — visits DB-level race-proof pattern (Phase 26 NOT racing — single INSERT, but reference for IntegrityError translation idioms if FK conflict surfaces).
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 20" — Telegram oracle-safe DM strings (renewal does NOT add new copy — Phase 25 noted this; Phase 27 owns expiring-soon DMs).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_build_membership_response(session, membership)`** at `service.py:192-258` — Phase 25 D-25-18 projection helper; Phase 26 calls directly for renewal response (handles freeze fields + camelCase + `previous_membership_id` once schema extended). NO new projection helper needed.
- **`repository.get_alive(session, plan_id)`** at `repository.py:51-58` — collapses null + archived to None. Phase 26 needs differentiator → adds NEW `get_plan_for_renewal` helper (D-26-08); does NOT modify `get_alive` (other callers depend on collapse).
- **`repository.get_membership(session, id)`** — Phase 17 helper; load source by id; reused unchanged.
- **`PlanNotFoundError` / `MembershipNotFoundError`** at `exceptions.py:115/204` — reused as-is. Phase 26 adds 2 new exception classes (D-26-09): `CannotRenewCancelledError` + `PlanArchivedError`.
- **`InvalidTransitionError`** at `exceptions.py:158-173` — reused for defence-in-depth "unknown source status" branch (D-26-14 step 2).
- **`update_membership_status`** at `repository.py:295-315` — NOT used by Phase 26 (renewal doesn't transition source). Mentioned для context only.
- **`audit.emit` + `LOCKED_AUDIT_EVENTS`** at `audit.py:138-189 + 142` — `("membership_renewed", "membership")` already locked Phase 24; Phase 26 ships single callsite passing AST gate naturally.
- **Self-FK pattern** — Postgres native; SQLAlchemy declarative supports via `ForeignKey("memberships.id", ondelete="SET NULL", name="fk_memberships_previous_membership_id_memberships")` (mirrors Phase 17 `fk_memberships_plan_id_membership_plans` shape; only difference is target table = same).
- **`MembershipResponse` schema** at `schemas.py:227-258` — Phase 26 adds 1 field (`previous_membership_id`); BackendSchemaBase auto-camelCases. NO breaking changes for existing consumers (default None backwards-compatible).
- **Endpoint pattern** — Phase 25 freeze/unfreeze (`router.py:324-391`) is the canonical model для empty-body POST + CSRF + `(CREATE, MEMBERSHIPS)` permission; Phase 26 D-26-20 directly mirrors с `201 Created` instead of `200 OK`.
- **`create_membership` server-compute date pattern** at `service.py:480-482` — `datetime.now(ZoneInfo("Europe/Moscow")).date()` + `start + timedelta(days=duration_days - 1)` для inclusive end. Phase 26 D-26-10..D-26-12 reuse identical pattern для renewal date computation.

### Established Patterns

- **Migration single concern** — Phase 24 added CHECK only; Phase 25 added freeze tables; Phase 26 adds single column + FK + index. Each migration ships independently green; no bundling.
- **Service ordering** — `repository.<insert/mutate>` → `session.flush()` → `audit.emit()` → `session.refresh(<for response>)` → `session.commit()`. Phase 17 / 18 / 25 all conform; Phase 26 D-26-14 mirrors.
- **State-machine 4×4 matrix** — Phase 25 16-cell parametrize matrix; Phase 26 leaves untouched (renewal is NOT a transition on source).
- **`today` kwarg injection for testability** — Phase 18 `_expire_due_memberships(today=None)`; Phase 24 `find_active_for_client(*, today)`; Phase 26 follows same convention if `service.renew_membership` ends up needing test-time clock control (likely yes for `expired`-source date strategy test).
- **AST literal-string audit gate** — каждый `audit.emit("event", resource_type="kind", ...)` callsite must use string literals; Phase 26 conforms (event = `"membership_renewed"`, resource_type = `"membership"`).
- **SVC001 commit-gate** — public functions in `modules/**/service.py` MUST contain `await session.commit()` if they emit audit or mutate via session; Phase 26 `renew_membership` public function gets explicit commit (D-26-14 step 9).
- **Camelcase wire format via BackendSchemaBase** — `previous_membership_id` Python → `previousMembershipId` JSON automatic; admin-web TS contract types regenerated в Phase 28 (FE-12).
- **Pagination envelope** — list endpoints return `PaginatedData[T] = {items, total, page, pageSize}`; Phase 26 NOT touching list endpoint, only adds POST.

### Integration Points

- **Resolver dispatch** — Phase 26 D-26-17 changes ORDER BY in `repository.find_active_for_client`. Consumers: `app/core/dependencies.py:get_active_membership_for_request` → reception POST `/api/v1/visits` (Phase 19) + Telegram `/checkin` (Phase 20). NO signature change; functional change is "prefer running membership over future renewal during overlap window". Phase 19/20 integration tests should not regress (assume single active membership scenario; renewal-stacking test new в Phase 26 covers the новое behaviour explicitly).
- **`memberships_router` mounting** — `app/api/v1/router.py` mounts `memberships_router` at `/memberships`; new `/renew` endpoint inherits prefix automatically. NO router file outside `memberships/` needs editing.
- **Plan archived during renewal** — D-26-08 covers; uses NEW `get_plan_for_renewal` helper to differentiate hard-delete (404) from archive (409). `MembershipPlan` ORM has `deleted_at` column (`SoftDeleteMixin`); FK on `memberships.plan_id` is ON DELETE RESTRICT, so hard-delete impossible while ANY membership references it (audit trail integrity).
- **Plan inactive (`active=False`) during renewal** — D-26-08 covers; renewal IS allowed. Existing `PlanInactiveError` (409 `plan_inactive`) is NOT raised on renewal path. Document in `service.renew_membership` docstring.
- **Alembic chain** — `0008_freeze` head → `0009_renewal` (Phase 26). Phase 27 plan agent creates `0010_notifications` revising from `0009_renewal`.
- **OpenAPI surface** — Phase 26 adds 1 path operation + 1 schema field. Phase 28 (FE drift-gate refresh) collects cumulative changes across phases 25/26/27; D-26-32 leaves Phase 26-time regen as planner discretion.
- **No frontend changes в Phase 26** — admin-web continues работать без "Продлить" кнопки до Phase 28 FE-12 ships. Backend ready, UI deferred.

</code_context>

<specifics>
## Specific Ideas

- **`start_date` strategy literals frozen в `constants.py` (D-26-13):** `"from_source_end_date"` + `"from_today_expired_source"`. Two literals total (никогда не будут больше двух per Phase 26 scope). Tests assert exact string match. Forensic SQL example: `SELECT COUNT(*) FROM audit_log WHERE event='membership_renewed' AND payload->>'start_date_strategy' = 'from_today_expired_source'` answers "how many renewals were of expired sources".
- **`current_price_kopecks` in audit payload (D-26-15)** — explicit lock на the "if plan got more expensive, client pays new price" decision (PROJECT.md milestone bullet "Snapshot pricing на renewal — берём **текущую** цену плана"). Audit captures this for revenue-forensics: `SELECT SUM(payload->>'current_price_kopecks') ::bigint FROM audit_log WHERE event='membership_renewed' AND created_at >= ... AND created_at < ...` gives renewal revenue per period.
- **`previous_membership_id` ON DELETE SET NULL (D-26-05):** chosen over CASCADE because cascading would lose audit-attributable history if a source row hard-deleted (which schema currently disallows but DBA-direct surgery possible). NULL post-deletion at least preserves the renewal row's own data; chain just becomes orphaned (forensic queryable via `audit_log` payload `source_membership_id`).
- **Resolver tiebreak `start_date ASC` (D-26-17):** the most subtle Phase 26 decision. Current `end_date DESC` was Phase 17 D-17 (silent tiebreak; "default to highest end_date wins"). Phase 26 inverts to "currently-running takes priority". Backwards-compat for non-renewal scenarios: if only one active row exists, ORDER BY is academic. If two rows exist sin renewal linkage (Phase 17 D-01 manual stacking), behaviour shifts: previously the newer-end-date row would win; now the lower-start-date row wins. **Acceptable trade-off:** "running" semantics align with operator intuition; old behaviour had no formal use-case and was a fallback heuristic. Document inversion in repo docstring + note migration impact (no data change, only future query semantics).
- **`get_plan_for_renewal` helper (D-26-08)** — purposefully separate function not a flag on `get_alive`. Adding `?include_archived=True` to `get_alive` would risk other callers unintentionally bypassing soft-delete (e.g. `create_membership` would happily reference archived plan if mis-flagged). Keeping renewal's permissive lookup in its own function names the intent explicitly.
- **Phase 24 D-24-25 + Phase 25 D-25-25 OpenAPI regen pattern carries over (D-26-32)** — Phase 26 plan agent confirms CI drift-gate behaviour; per-commit gate → regen openapi.json в last commit; иначе defer к Phase 28.

## Risks / Watchpoints (for planner)

- **Resolver ORDER BY change is the single highest-risk Phase 26 lock** — touches Phase 19 visits + Phase 20 Telegram check-in. Plan agent runs `pytest apps/backend/tests/integration/visits/ apps/backend/tests/integration/auth/ -x` after the resolver swap and BEFORE adding renewal-specific tests, so a regression в check-in path surfaces immediately and not buried в new test changes. Phase 25 verification confirmed `_build_membership_response` integration; Phase 26 must verify resolver tiebreak doesn't break green Phase 19/20 tests (likely fine — they test single-active scenarios).
- **`previous_membership_id` non-partial index size** — на пет-проект scale negligible; на production-scale (10K+ rows) partial index `WHERE previous_membership_id IS NOT NULL` ~10× smaller. Plan agent considers; recommend non-partial для Phase 26 simplicity, file partial as backlog if forensics queries grow.
- **Date arithmetic edge case** — `source.end_date + timedelta(days=1)` for Feb 28 → Feb 29 in leap years → Mar 1 in non-leap years. Python `date` handles natively; no DST risk (Europe/Moscow is fixed UTC+3). Plan agent unit-test edge case (Feb 28 2025 → Feb 29 doesn't exist → date library correctly increments to Mar 1). Sanity check, not blocker.
- **Audit payload shape divergence от docstring** (D-26-26) — `audit.py` docstring lines 61-62 предлагает `{membership_id, client_id, plan_id, new_end_date}`; Phase 26 ships `{client_id, source_membership_id, source_plan_id, current_price_kopecks, start_date_strategy}`. Plan agent updates docstring при добавлении callsite.
- **`expired` source race with ARQ `expire_memberships`:** if operator clicks "renew" precisely as ARQ flips source `active → expired`, two pathways (`from_source_end_date` vs `from_today_expired_source`) produce different `start_date`. Phase 26 reads source.status AFTER `repository.get_membership` (snapshot at read time within transaction). If status flipped between read and dates computation, transaction sees consistent state — no race. Document in service docstring; integration test could exercise via deliberate flip mid-flow (advanced; optional per planner).
- **Renewal-of-renewal chain depth** — D-26-06 allows arbitrary depth implicitly. No requirement for depth limit. Forensic `WITH RECURSIVE` query needed if "show full history" admin view materializes (backlog).
- **Self-FK migration on existing Postgres connection** — Alembic generates `op.create_foreign_key` correctly for self-FK; verify `0009_renewal.py` upgrade runs in fresh container (`docker compose down -v && docker compose up`) before merge, in case migration ordering trips on the self-reference.
- **`PlanArchivedError` vs `PlanInactiveError` confusion** — two similarly-named exceptions (`plan_archived` 409 vs `plan_inactive` 409) — distinct semantics: archived = soft-deleted (`deleted_at IS NOT NULL`); inactive = `active=False` (paused but alive). Plan agent ensures docstrings + error-translation map (`http/errors.ts` on frontend, eventually) keep these straight; FE TS types should expose both as discrete code literals. Phase 28 wiring inherits.

</specifics>

<deferred>
## Deferred Ideas

- **Renewal chain forensic API** — `GET /api/v1/memberships/{id}/chain` returning recursive list (renewal of renewal of renewal, ...). No v1.3 use-case; backlog if admin "show client's full membership history" UI emerges.
- **Auto-renew (cron-driven)** — REQUIREMENTS explicit MEM-REN-EP-01 is operator-initiated POST. Auto-renew (e.g. "client opted in to auto-renew, charge them, create renewal") needs payments module + opt-in UX — out of v1.3 scope. ЮKassa integration milestone candidate.
- **Renewal preview / quote endpoint** — "what would renewal cost / look like before commit" for admin-web "Продлить" preview modal. Phase 28 may add client-side preview computed from existing GET data (current plan price + source end_date) without dedicated endpoint; if backend computation needed, defer к Phase 28 spec.
- **Renewal payment capture (`paid_at` / amount)** — Phase 26 leaves `paid_at` / `notes` NULL on renewal row (operator may PATCH later if endpoint exists; currently no PATCH on memberships beyond cancel). Backlog when billing module materializes.
- **Notifications on renewal success** — Telegram DM "Спасибо за продление, ваш membership продлён до {end_date}" — not in REQUIREMENTS; backlog if owner requests post-launch.
- **Renewal across plan change** — current Phase 26 lock = "renewal uses CURRENT version of source's plan". If owner wants "renew but switch to different plan", that's a NEW sale (`POST /api/v1/memberships`), not renewal. UX could surface "renew at this plan / switch plan" choice in admin-web Phase 28; backend stays as-is (separate endpoints for separate intents). Backlog if pattern emerges.
- **`previous_membership_id` partial index** — non-partial index ships in Phase 26 (D-26-02 step 3 / specifics watchpoint #2); partial `WHERE previous_membership_id IS NOT NULL` saves space at production scale. Backlog when row count > ~10K.
- **Renewal of cancelled source override (admin "Reactivate" flow)** — current lock 409 `cannot_renew_cancelled` is intentional. If owner needs an "Я ошибся, восстанови этот cancellation" path, that's a separate `POST /api/v1/memberships/{id}/uncancel` endpoint with explicit reactivation audit trail; do NOT use renewal as the workaround. Backlog if support burden grows.
- **`previous_membership_id` filter on list endpoint** — `?previous_membership_id=X` to find "all renewals of source X" — not in v1.3; admin-detail-page only concern. Backlog.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 26` not run interactively in `--auto` mode; if matches exist, plan-phase will surface them.

</deferred>

---

*Phase: 26-memberships-renewal-backend*
*Context gathered: 2026-05-09 (auto mode — recommended defaults selected by Claude)*
