# Phase 24: Foundations & Tech-Debt Bedrock - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude)

<domain>
## Phase Boundary

Foundations + tech-debt bedrock for v1.3. NO new endpoints (only query-param extension), NO new tables. Phase 24 ships:

1. **INFRA-15** — extend `LOCKED_AUDIT_EVENTS` with 6 new pairs (3 freeze/renewal events + 3 expiring-notification events) so 25/26/27 can `audit.emit(...)` literals.
2. **INFRA-16** — extend `Membership.status` CHECK with `'frozen'`; introduce declarative `MEMBERSHIP_STATUS_TRANSITIONS` constant + 409 `invalid_transition` for disallowed pairs.
3. **DEBT-01** — `resolve_active_membership_by_client` adds defence-in-depth `end_date >= today (Europe/Moscow)` filter (closes MEM-04 D-13 from v1.2).
4. **DEBT-02** — backend `GET /api/v1/memberships?expiring=true&within=N` (1..30, default 7); admin-web mock service adopts `within` param for mock/http parity (closes WR-07 from v1.2).
5. **DEBT-03** — `BusinessService` SVC001 AST commit-gate (INFRA-13) extended to `app/modules/auth/service.py`; public write paths get explicit `await session.commit()` (closes SVC001 walker scope deferral from v1.2 Phase 15).

**Out of Phase 24:** any new column on `memberships` or `membership_plans` (lives in Phase 25's freeze migration), any new endpoint beyond query-param extension, any FE wiring (Phase 28 owns `expiringWithinDaysFilter` http-mode flip).

</domain>

<decisions>
## Implementation Decisions

### Migration ownership & numbering

- **D-24-01:** Phase 24 owns its own Alembic migration `0007_status_taxonomy.py`. It performs CHECK extension only (`'active'|'expired'|'cancelled'|'frozen'`) — no column adds. Downstream phases shift up by one: Phase 25 → `0008_freeze.py` (or `0008_freeze_and_renewal.py` if combined with Phase 26), Phase 27 → `0009_notifications.py` (or `0010_*` depending on Phase 26's choice).
  - **Conflict flag:** the v1.3 milestone roadmap note "25 and 26 share migration `0007`" predated INFRA-16's CHECK requirement. Phase 25/26 plan agents MUST treat their migration as `0008` (not `0007`) and update the milestone roadmap note as part of their planning step.
  - **Why not fold INFRA-16 into Phase 25's `0007`:** Phase 24 ships independently and must be a green build before Phase 25 starts; bundling INFRA-16 into freeze migration would couple two phase boundaries unnecessarily.
- **D-24-02:** Postgres CHECK constraint extension uses `op.execute("ALTER TABLE memberships DROP CONSTRAINT ck_memberships_status; ALTER TABLE memberships ADD CONSTRAINT ck_memberships_status CHECK (status IN ('active','expired','cancelled','frozen'))")` — Postgres has no in-place CHECK alter. Downgrade reverses to the v1.2 three-status form. ORM `__table_args__` updated to match (CheckConstraint string literal).

### `MEMBERSHIP_STATUS_TRANSITIONS` shape & state-machine helper

- **D-24-03:** New file `app/modules/memberships/constants.py` exposes `MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]]` keyed by source status. Phase 24 contents (no `frozen` source/target yet — those land in Phase 25):
  ```python
  MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
      "active":    frozenset({"expired", "cancelled"}),  # Phase 25 will add "frozen"
      "expired":   frozenset(),                          # Phase 26 may extend for renewal mechanics
      "cancelled": frozenset(),                          # terminal
      "frozen":    frozenset(),                          # Phase 25 will add {"active", "cancelled"}
  })
  ```
  - **Rationale:** REQUIREMENTS INFRA-16 names this file path verbatim. `MappingProxyType` makes the dict read-only at module load. `str` keys (not `MembershipStatus` enum) keep the constant importable from `models.py` without a circular import; the schema-layer enum and the constant share string values.
- **D-24-04:** Service-layer central guard `_assert_can_transition(membership, *, target: str) -> None` lives in `app/modules/memberships/service.py`; raises `InvalidTransitionError("invalid_transition", from_status=membership.status, to_status=target)` (already-defined exception in `app/core/exceptions.py:158-172` — reuse, do not duplicate).
- **D-24-05:** Existing helpers `_assert_can_cancel(membership)` and `_assert_can_expire(membership)` are refactored to delegate: `_assert_can_cancel = lambda m: _assert_can_transition(m, target="cancelled")` (or thin wrappers). The 9-cell unit test `tests/unit/memberships/test_state_machine.py` is updated to also exercise the new central helper directly; the existing per-helper assertions keep their parametrize matrix (no test churn beyond an additional parametrize column).

### DEBT-01 — Resolver `end_date >= today` filter

- **D-24-06:** `resolve_active_membership_by_client(session, client_id, *, today: date | None = None)` mirrors `_expire_due_memberships` injection pattern. `today=None` resolves to `datetime.now(ZoneInfo("Europe/Moscow")).date()` inside the function. Tests pass explicit `today` for determinism (no `freezegun`).
- **D-24-07:** Repository function `find_active_for_client` gets the same `today` kwarg and adds predicate `Membership.end_date >= today`. The existing composite index `ix_memberships_client_id_status_end_date` on `(client_id, status, end_date DESC)` covers the new predicate (rightmost column is range-scan friendly).
- **D-24-08:** Repository docstring at `apps/backend/app/modules/memberships/repository.py:283-297` is updated — the current "Date filter is intentionally NOT applied here" note is REVERSED. The new docstring cites DEBT-01 + the missed-ARQ-tick scenario as defence-in-depth rationale.
- **D-24-09:** New integration test `tests/integration/memberships/test_resolver.py::test_resolver_filters_expired_active_row` inserts a membership with `status='active' AND end_date < today` (simulating a missed ARQ tick) and asserts resolver returns `None`. Existing tests stay green (the canonical happy-path active row has `end_date >= today`).

### DEBT-02 — `?expiring=true&within=N` query

- **D-24-10:** `MembershipListQuery` (`apps/backend/app/modules/memberships/schemas.py:235`) gains `expiring: bool = False` and `within: int = Field(default=7, ge=1, le=30)`. `within` is silently ignored when `expiring=False`. No model_validator coupling — keep the schema flat; repository decides whether to apply the predicate.
- **D-24-11:** When `expiring=True`, repository forces `Membership.status == 'active'` regardless of any user-supplied `status` filter (REQUIREMENTS DEBT-02 wording: "returns only active memberships, expiring in window"). Conflicting query — `?expiring=true&status=expired` — returns 422 `query_invalid` with `fields={status: 'incompatible_with_expiring'}` (cleaner than silent override).
- **D-24-12:** Predicate uses the inclusive end-date semantics carried forward from v1.2 (PROJECT.md Key Decisions): `Membership.end_date >= today AND Membership.end_date <= today + (within - 1)`. `today` resolves to Europe/Moscow per D-24-06.
- **D-24-13:** Mock service `apps/admin-web/src/shared/api/services/mock/memberships.ts` accepts `query.within: number = 7` and replaces the hard-coded `EXPIRING_DAYS = 7`; same for `apps/admin-web/src/shared/api/services/http/memberships.ts` — but the http impl strips its CLIENT-SIDE filter once it forwards `expiring`+`within` to the backend (no double-filter). The `BLK-06` pagination collapse comment in the http adapter is updated/removed because the backend now paginates the filtered set honestly. UI wiring of a `within` selector is OUT OF SCOPE — Phase 28 (FE-13) decides whether to expose the param to the operator.

### DEBT-03 — SVC001 walker → auth/service.py

- **D-24-14:** `tests/unit/test_service_commit_gate.py:167-169` adds `_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"` and extends `_INSPECTED_SERVICES = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE, _AUTH_SERVICE)`. The walker scope test (`test_walker_scope_is_modules_service_only`) already passes for auth/service.py because it lives under `modules/` — no glob change needed.
- **D-24-15:** Public auth-service write paths get explicit `await session.commit()` immediately after their final `audit.emit(...)` call. Initial inventory (planner verifies completeness):
  - `authenticate` — emits `login_failed` or `login_success`; needs commit on both branches before `raise` / `return`.
  - `issue_tokens` — INSERTs `RefreshToken` row + Redis writes; needs commit before returning the token tuple.
  - `rotate_refresh` — UPDATEs old token + INSERTs new token + emits audit; needs commit.
  - `revoke_session` / `revoke_all_user_sessions` — emit `session_revoked` / `session_revoked_all`; need commit.
  - `change_password` — emits `password_changed_revokes_sessions`; needs commit.
  - **Telegram OTP service paths** — `apps/backend/app/modules/auth/telegram_service.py` is OUT OF SCOPE for INFRA-13 (file is not `service.py`); DEBT-03 wording covers `auth/service.py` only. Flag as deferred follow-up if `audit.emit` callsites exist there without commits (planner: scan and report; do not fix in Phase 24).
- **D-24-16:** No signature refactors and no `_`-prefix renames in auth/service.py. The `# noqa: SVC001 caller-owns-txn` marker is reserved for genuinely caller-owns-txn private helpers; auth's public functions are NOT — they end the request-scoped UoW.
- **D-24-17:** Behavior change risk: `get_db` currently rolls back on error and (per the audit.py docstring) drops audit rows that weren't explicitly committed. Adding explicit commits in auth/service.py write paths means audit rows on `login_failed` / `session_revoked` will now persist where they previously could have been dropped on a downstream exception. This is the INTENDED fix (mirrors Phase 12.1 clients/service.py rationale). Planner: confirm no existing tests assert the absence of audit rows on the failure path; if so, those tests must be updated to assert presence.

### LOCKED_AUDIT_EVENTS extension layout

- **D-24-18:** New pairs append to the v1.2 block in `app/core/audit.py:78-126`, grouped under a `# v1.3 (Phase 24 lock — emitted in Phases 25/26/27)` comment, in this order:
  ```python
  ("membership_frozen", "membership"),
  ("membership_unfrozen", "membership"),
  ("membership_renewed", "membership"),
  ("expiring_notification_sent_7d", "membership"),
  ("expiring_notification_sent_3d", "membership"),
  ("expiring_notification_sent_1d", "membership"),
  ```
  All six use `resource_type="membership"` per REQUIREMENTS INFRA-15. The AST literal-string gate in `tests/unit/test_audit_taxonomy.py` is unaffected — Phase 24 only extends the frozenset; callsites land in 25/26/27.
- **D-24-19:** Unit test `tests/unit/test_audit_taxonomy.py` (or equivalent) gains six membership-rows asserting the new pairs are present in `LOCKED_AUDIT_EVENTS`. No callsite-existence assertion — the pairs are pre-registered for the downstream phases.

### Claude's Discretion

- Test-file naming for the new resolver date-filter test (`test_resolver.py::test_resolver_filters_expired_active_row` is the proposal; planner can rename if a more specific match exists).
- Exact ordering of helper refactors in `service.py` (D-24-04, D-24-05) — Claude picks during planning.
- Whether the `within` query param appears as `within` or `expiring_within` in the OpenAPI schema. Recommended: `within` (matches REQUIREMENTS literal `?expiring=true&within=N`).
- Deferred follow-up scan of `auth/telegram_service.py` (D-24-15) — surfaces during planning; if found, file as a deferred item rather than fixing in Phase 24.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § "Phase 24" — phase summary + 5 success criteria.
- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 24" + § "Build Order" + § "Key Risks" — milestone-scoped detail; the "Resolver touch-points" risk explicitly serializes 24→25→26 changes to one resolver.
- `.planning/REQUIREMENTS.md` — INFRA-15, INFRA-16, DEBT-01, DEBT-02, DEBT-03 verbatim wording (lines 15–19).
- `.planning/PROJECT.md` § "Key Decisions" — Membership `end_date` is **inclusive**; `gym_date` UNIQUE invariant; ARQ cron container `TZ=UTC`; modular monolith layering.

### Codebase contracts (read before editing)
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset (lines 78-126); `AuditEventNotLockedError` hard-fail (D-09 from Phase 15); `emit()` invariant — caller owns transaction (D-04, line 138-189).
- `apps/backend/app/core/exceptions.py:158-172` — `InvalidTransitionError(ConflictError)` already defined; reuse for INFRA-16 (do NOT add a parallel exception).
- `apps/backend/app/modules/memberships/models.py:144-161` — current `Membership.__table_args__` with `ck_memberships_status` CheckConstraint and the composite `ix_memberships_client_id_status_end_date` index. Update CHECK string + keep the index (DEBT-01 still uses it).
- `apps/backend/app/modules/memberships/repository.py:283-305` — `find_active_for_client` (resolver underlying query); the docstring's "Date filter is intentionally NOT applied here" note is REVERSED by DEBT-01.
- `apps/backend/app/modules/memberships/service.py:472-489` — `resolve_active_membership_by_client` (public wrapper registered at `core/dependencies.py` resolver slot).
- `apps/backend/app/modules/memberships/schemas.py:235-247` — `MembershipListQuery` (DEBT-02 extends with `expiring` + `within`).
- `apps/backend/app/modules/auth/service.py:73-189` — `_classify_verify_error` (helper, no DB), `authenticate` (public, emits audit, currently no `await session.commit()`).
- `apps/backend/tests/unit/test_service_commit_gate.py:167-211` — SVC001 walker `_INSPECTED_SERVICES` tuple + live gate test; `_SVC001_MARKER` literal; the `auth/service.py:authenticate` deferral is mentioned at line 194 (this CONTEXT closes that deferral).
- `apps/backend/tests/unit/memberships/test_state_machine.py` — 9-cell parametrize matrix; INFRA-16 extends to a 16-cell matrix when `frozen` is added in Phase 25 (Phase 24 keeps it 9-cell, only refactors to use central helper).
- `apps/backend/alembic/versions/0006_visits.py` — last v1.2 migration; Phase 24's `0007_status_taxonomy.py` is the next slot.

### Frontend contract (mock/http parity)
- `apps/admin-web/src/shared/api/services/http/memberships.ts:38-81` — current client-side expiring filter + `BLK-06` pagination workaround that DEBT-02 retires.
- `apps/admin-web/src/shared/api/services/mock/memberships.ts:28-57` — current mock filter; `EXPIRING_DAYS = 7` constant gets parametrized to `query.within`.
- `apps/admin-web/CLAUDE.md` § "Conventions" — pagination envelope `{items, total, page, pageSize}`, branded IDs, ISO date strings, Europe/Moscow TZ.

### Prior decisions still in force (carried from v1.2)
- `.planning/STATE.md` § "Decisions" — Membership `end_date` inclusive, `gym_date` STORED+UNIQUE, snapshot pricing mandatory, ARQ cron `unique=True`, cross-module callbacks via Protocol.
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 15 Foundations" — INFRA-13 SVC001 walker rationale (Phase 12.1 regression bound) + INFRA-11 audit literal-string gate.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`InvalidTransitionError`** at `app/core/exceptions.py:158` — already raises `409 invalid_transition` with `from_status`/`to_status` payload fields. INFRA-16 wires it from a new central guard; no exception class additions.
- **`_assert_can_cancel` / `_assert_can_expire`** at `app/modules/memberships/service.py` — current per-transition guards already used by Phase 17's 9-cell matrix. Refactor target for D-24-04.
- **`_expire_due_memberships(today=None)` injection pattern** at `app/modules/memberships/service.py:497-543` — the canonical example of `today` kwarg defaulting to `datetime.now(ZoneInfo("Europe/Moscow")).date()`. DEBT-01 mirrors it on the resolver path.
- **`AuditEventNotLockedError` hard-fail** at `app/core/audit.py:65-75` — D-09 enforced; extending the frozenset is a one-line append, no graceful-degradation path needed.
- **Composite index `ix_memberships_client_id_status_end_date`** at `models.py:155-160` — covers the new resolver predicate (rightmost column is `end_date DESC`, range-scan compatible).
- **Mock service `query.expiring` branch** at `mock/memberships.ts:43-52` — already implements the filter; only needs `within` parametrization (D-24-13).

### Established Patterns

- **Migration CHECK constraint update** — Postgres requires `DROP CONSTRAINT … ADD CONSTRAINT …`; convention is `op.execute()` with literal SQL plus matching `__table_args__` update (mirrors `0005_memberships.py` original CHECK creation).
- **AST literal-string gate** (`tests/unit/test_audit_taxonomy.py`) — every `audit.emit("event", resource_type="kind", …)` callsite must use string literals, not variables. Phase 24 doesn't add callsites, only frozenset entries — gate stays green.
- **SVC001 walker opt-out** — `# noqa: SVC001 caller-owns-txn` valid only on `_`-prefixed private helpers. Public functions in `modules/**/service.py` MUST contain `await session.commit()` if they emit audit or mutate via session (D-24-15, D-24-16).
- **Pagination envelope** — every list endpoint returns `PaginatedData[T] = {items, total, page, pageSize}`. DEBT-02's `expiring=true` branch keeps the envelope (do not collapse to a bare array as the http adapter currently does in `BLK-06` workaround).
- **State-machine 9-cell matrix** at `tests/unit/memberships/test_state_machine.py` — Phase 24 keeps the 9-cell shape (`active|expired|cancelled` × `cancel|expire|create-self`); Phase 25 will extend to 16 cells when `frozen` joins.

### Integration Points

- **Resolver dispatch** — `app/core/dependencies.py` registers `resolve_active_membership_by_client` via `register_active_membership_resolver()` (Phase 17 slot). Phase 24's signature change (adding `today` kwarg) is backward-compatible (kwarg has a default); no dependency-injection refactor needed at the slot site, but the slot's stored callable type may need a `Protocol` update if it pinned the signature explicitly. Planner: verify `core/dependencies.py` resolver Protocol/typing.
- **Backend → admin-web contract** — `apps/admin-web/src/shared/api/services/http/memberships.ts` is unblocked the moment backend ships `?expiring=true&within=N`. The http adapter still NEEDS to forward the params (small edit) AND remove the client-side filter pass + BLK-06 workaround. This work lands inside Phase 24's DEBT-02 (mock/http parity), NOT Phase 28 (which only flips `VITE_API_MODE` and wires UI).
- **Alembic chain** — `0006_visits.py` is the current head; `0007_status_taxonomy.py` revises from `0006_visits`. Phase 25's plan agent must rebase `0008_freeze.py` on `0007_status_taxonomy` (NOT directly on `0006_visits`).
- **Resolver consumers** — `app/core/dependencies.py:get_active_membership_for_request` (Phase 4 D-24 slot) is consumed by `/api/v1/visits` reception check-in (Phase 19) and by Telegram bot `/checkin` handler (Phase 20). Neither needs a code change for DEBT-01; the new `today` filter is transparent to callers (still returns `Membership | None`).

</code_context>

<specifics>
## Specific Ideas

- The "Resolver touch-points serialized" rule from `.planning/STATE.md` decisions block governs the resolver delta budget for Phase 24: the only allowed change is the `end_date >= today` filter. Adding `status != 'frozen'` is Phase 25's job; tiebreak extension is Phase 26's job. Each phase leaves the resolver in a green test state.
- INFRA-15's six new pairs are pre-registered in Phase 24, BEFORE any callsite exists. This is the correct sequencing — `AuditEventNotLockedError` is hard-fail at runtime, so a Phase 25/26/27 callsite would crash without Phase 24's frozenset extension already in place.
- The `MEMBERSHIP_STATUS_TRANSITIONS` constant ships in Phase 24 with `frozen` listed as a status key with empty target set. Phase 25 will populate the `active → frozen` and `frozen → active|cancelled` edges. The constant is shipped early because INFRA-16 wording locks the file path + name; making the file in Phase 25 would push the import path into a downstream phase needlessly.

## Risks / Watchpoints (for planner)

- **Migration numbering renumber in milestones doc** — the v1.3 milestone roadmap note "25 and 26 share migration `0007`" must be amended in Phase 24's plan as part of "update upstream docs" task (or explicitly punted to Phase 25's plan agent with the same note).
- **`get_db` rollback semantics behavior change** — D-24-17 calls out that adding explicit commits in auth/service.py changes which audit rows persist on the failure path. Planner: grep `tests/integration/auth/` for assertions that count `auth_log` rows on failure paths; update those tests if they assume rollback drops the row.
- **Resolver Protocol typing** — `core/dependencies.py` resolver slot may pin the signature; adding `today` as keyword-only with a default should be safe but planner verifies via `mypy --strict`.
- **Mock/http filter parity** — DEBT-02's mock service change is small but must NOT regress existing FE-08 D-2 behavior (the toggle in `MembershipsListPage`). Add a Vitest case asserting `within=7` default matches the legacy `EXPIRING_DAYS` constant.

</specifics>

<deferred>
## Deferred Ideas

- **`auth/telegram_service.py` SVC001 audit** — DEBT-03 scope is `auth/service.py` only. If the planner's scan of `telegram_service.py` finds public `audit.emit` callsites lacking commits, file as a deferred follow-up (likely v1.4 / next tech-debt sweep) rather than expanding Phase 24's blast radius.
- **`MEMBERSHIP_STATUS_TRANSITIONS` + `frozen` matrix population** — Phase 25 (D-MEM-FRZ) extends the constant with `active ↔ frozen`, `frozen → cancelled`, and updates the unit-test parametrize matrix from 9 cells to 16. Phase 24 ships the empty `frozen: frozenset()` placeholder.
- **OpenAPI byte-stable regen** — Phase 24 changes the OpenAPI surface (DEBT-02 adds query params), but the milestone roadmap puts the single drift-gate refresh in Phase 28. Phase 24 plan should update `apps/backend/openapi.json` when the FastAPI route changes, but Phase 28 owns the cumulative `git diff --exit-code` enforcement. If CI's drift gate runs every commit, Phase 24's commit will refresh the JSON; if it's gated, Phase 28 collects the diff. Planner: confirm the CI behavior and either (a) regenerate as part of Phase 24's last commit or (b) leave the regen for Phase 28.
- **Operator-facing `within` selector UI** — REQUIREMENTS DEBT-02 wires the parameter on the contract; FE-13 in Phase 28 decides whether to expose a slider/input. Phase 24 keeps the FE-08 default (7-day window) intact in the UI.
- **Renewal source `expired` source-status start-date strategy** — Phase 26 owns this (`MEM-REN-04`); Phase 24's `MEMBERSHIP_STATUS_TRANSITIONS` does NOT need a creation-edge for renewal; renewals create a new row (status=void→active), they don't transition the source row.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 24` returned 0 matches; no todos were reviewed.

</deferred>

---

*Phase: 24-foundations-tech-debt-bedrock*
*Context gathered: 2026-05-08 (auto mode)*
