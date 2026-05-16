# Phase 34: PT-Session Recording — Context

**Gathered:** 2026-05-16
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 34 --auto` — single pass; recommended defaults selected for every gray area; full audit trail in `34-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

Phase 34 materializes PT-session recording on top of three bedrock layers already landed:
1. **Phase 31** — `trainers` table + `register_trainer_by_id_resolver` Protocol slot (`TrainerById { id, is_active }`).
2. **Phase 33** — `pt_packages` instance table with `sessions_remaining INT CHECK >= 0 AND <= session_count_snapshot` and FSM `active → {exhausted, expired, cancelled}` + `register_active_pt_package_resolver` slot (silent-None semantics) + `PT_PACKAGE_STATUS_TRANSITIONS` MappingProxyType.
3. **Phase 30** — `LOCKED_AUDIT_EVENTS` already contains `pt_session_recorded`, `pt_session_cancelled`, `pt_package_exhausted`; `audit_payloads.py` schemas locked verbatim (`PtSessionRecordedPayload`, `PtSessionCancelledPayload`, `PtPackageExhaustedPayload`); `Resource.PT_SESSIONS` registered with `(CREATE, PT_SESSIONS)` reception+owner and `(CANCEL, PT_SESSIONS)` owner-only (B-12 reception-window enforcement is application-layer, not RBAC-layer); SVC001 walker glob `modules/**/service.py` auto-covers the new `pt_sessions/service.py`.

Concretely Phase 34 delivers:

- **Migration `0015_pt_sessions.py`** — `CREATE TABLE pt_sessions` with columns from PT-14 verbatim: `id UUIDv4 PK`, `pt_package_id UUID NOT NULL FK pt_packages(id) ON DELETE RESTRICT`, `trainer_id UUID NOT NULL FK trainers(id) ON DELETE RESTRICT`, `client_id UUID NOT NULL FK clients(id) ON DELETE RESTRICT` (denormalised — avoids JOIN through pt_packages on client history queries), `performed_at TIMESTAMPTZ NOT NULL`, `performed_by_user_id UUIDv4 NOT NULL FK users(id) ON DELETE RESTRICT`, `cancelled_at TIMESTAMPTZ NULL`, `cancel_reason TEXT NULL CHECK length ≤200`, `trainer_name_snapshot TEXT NOT NULL` (B-05 — captured at recording time, survives trainer rename/deactivation), `notes TEXT NULL CHECK length ≤500`, `created_at` / `updated_at` (TimestampMixin). Composite indexes `ix_pt_sessions_pt_package_id_performed_at_desc (pt_package_id, performed_at DESC)` and `ix_pt_sessions_trainer_id_performed_at_desc (trainer_id, performed_at DESC)`.
- **New module** `app/modules/pt_sessions/` (constants/models/repository/schemas/service/router/permissions). Module needs to be added to `.importlinter modules-independent` contract (currently lists 11 modules — `pt_sessions` is the 12th; this is the ONLY structural-bedrock addition in Phase 34).
- **Sale flow** (`POST /api/v1/pt-sessions`, reception+owner per PT-15): body `{pt_package_id, trainer_id, performed_at, notes?}` with `extra='forbid'` (D-32-13 / D-33-11 precedent). Server validates trainer existence+active via `resolve_trainer_by_id` Protocol slot, package status via `get_active_pt_package` slot (matches `client_id` of `pt_package_id`), `performed_at` within backdating window (B-11: reception 7d / owner unlimited). Race-safe decrement via single SQL UPDATE...RETURNING (PT-16). On 0-row return → 409 `pt_package_exhausted`. On `sessions_remaining = 0` post-decrement → auto-transition package to `'exhausted'` in same UoW + emit `pt_package_exhausted` once (PT-17).
- **Cancel flow** (`POST /api/v1/pt-sessions/{id}/cancel`, PT-18, reception ≤24h after recording OR owner anytime — B-12): body `{cancel_reason: str ≤200}` with `extra='forbid'`. Server: load session (404 / 409 already-cancelled), enforce B-12 cancel-window via actor.role + `created_at` (NOT `performed_at` — operator-action recency), set `cancelled_at = now()` + `cancel_reason`, increment `sessions_remaining` on parent package (single UPDATE with `sessions_remaining < session_count_snapshot` predicate as defence-in-depth), if package was in `'exhausted'` status transition back to `'active'` (PT-18 explicit). NOT a transition concern for `'cancelled'`/`'expired'` package status — those stay as-is (cancel restores balance only for forensic correctness; package status remains terminal-cancelled or time-expired).
- **Read API** — `GET /api/v1/pt-packages/{id}/sessions` (reception+owner, PT-19): returns paginated session history including cancelled, ordered by `performed_at DESC`. Endpoint lives in `pt_sessions/router.py` (subject-side ownership principle per D-33-18) but URL path is rooted at `/pt-packages/{id}/sessions` — router declares `prefix='/api/v1/pt-packages'` for this single endpoint, or alternative: standalone `GET /api/v1/pt-sessions?pt_package_id={id}` (D-34-08 picks).
- **Protocol slot consumption (NO new slots)** — PT-session sale uses BOTH `resolve_trainer_by_id` (Phase 31) AND `get_active_pt_package` (Phase 33). Phase 34 introduces ZERO new Protocol slots in `core/dependencies.py` (resolver-only consumer). No registration call in `app/main.py:create_app()` for PT-session-specific resolver — there is no PT-session resolver because no other module reads PT-sessions through a slot in v1.4.
- **2 audit events** (pre-registered in Phase 30 / Phase 33; payload schemas locked):
  - `pt_session_recorded` — payload `{pt_session_id, pt_package_id, client_id, trainer_id, trainer_name_snapshot, performed_at, performed_by_user_id, sessions_remaining_after}` (verbatim from `PtSessionRecordedPayload` in `audit_payloads.py:278-296`).
  - `pt_session_cancelled` — payload `{pt_session_id, pt_package_id, client_id, cancel_reason, sessions_remaining_after, package_reactivated}` (verbatim from `PtSessionCancelledPayload:299-313`).
  - PLUS `pt_package_exhausted` (subject = `pt_package`) emitted from PT-session decrement when `sessions_remaining` hits 0 — payload schema already extended with `exhausted_at: datetime` in Phase 33 D-33-15 explicitly for this Phase 34 callsite.
- **PT-sessions are orthogonal to `visits`** (PT-20 / Q3 default): recording a PT-session does NOT INSERT into `visits`; checking in via `visits` does NOT INSERT into `pt_sessions`. ZERO cross-table writes between the two domains. This is enforced by ABSENCE — Phase 34 service code never touches `visits` table.
- **Integration test PTS-TEST-01** — Postgres-only (skip on SQLite via existing `requires_postgres` marker; D-34-19). Spawn 2 concurrent `POST /api/v1/pt-sessions` against a package with `sessions_remaining=1` → exactly one 201 success, the other 409 `pt_package_exhausted` (race resolved at DB layer through the `sessions_remaining > 0` predicate in the atomic UPDATE...RETURNING).

**9 requirements in scope**: PT-14..PT-22 (see `.planning/REQUIREMENTS.md:97-105`).

**Out of scope (deferred / handled elsewhere):**
- admin-web `/pt-sessions` UI / route / form — descoped from v1.4 per 2026-05-15 frontend pivot; admin-web frozen-as-of-v1.3. Production frontend ships in v2.0 by external design team.
- OpenAPI `schema.d.ts` regen exposing `/pt-sessions` paths — **Phase 35** (backend-only handoff).
- Operator API-contract test scenarios via curl/Postman + PTS-TEST-01 evidence capture — **Phase 36** (milestone verification).
- Multi-trainer-per-session — single trainer per `pt_sessions` row (no array column); future feature if landed.
- PT-session no-show / late-cancel by client (with package balance penalty) — not on v1.4 roadmap.
- Telegram bot `/sessions` self-history — v1.5+.
- Edit-after-record (correct trainer or notes after recording) — out of v1.4; only cancel + re-record. Notes editability deferred.
- Server-side aggregation `GET /api/v1/clients/{id}/pt-sessions` cross-package history — out of v1.4; only `GET /pt-packages/{id}/sessions` per-package view in PT-19.

</domain>

<decisions>
## Implementation Decisions

### D-34-01: Migration `0015_pt_sessions.py` — single revision, no ALTER

- Revision = `"0015_pt_sessions"`, down_revision = `"0014_pt_packages"`. Single concern: `CREATE TABLE pt_sessions`.
- **Why:** No cross-table dependency requires bundling (unlike Phase 32 D-32-01 which needed ALTER memberships in the same revision for refund flow). PT-session table is purely additive — no schema changes to `pt_packages` (the `sessions_remaining` decrement uses existing column; CHECK already in place from Phase 33 D-33-03). Mirrors Phase 33 D-33-01 split-by-concern discipline.

### D-34-02: `pt_sessions` columns (PT-14)

Verbatim from PT-14 requirement + B-05 invariant:

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK DEFAULT gen_random_uuid()` | UUIDPkMixin |
| `pt_package_id` | `UUID NOT NULL FK pt_packages(id) ON DELETE RESTRICT` | balance ownership |
| `trainer_id` | `UUID NOT NULL FK trainers(id) ON DELETE RESTRICT` | TRN-05 enforces 409 on trainer hard-delete |
| `client_id` | `UUID NOT NULL FK clients(id) ON DELETE RESTRICT` | denormalised — avoids JOIN through pt_packages on client history |
| `performed_at` | `TIMESTAMPTZ NOT NULL` | wall-clock of training session (may be backdated) |
| `performed_by_user_id` | `UUID NOT NULL FK users(id) ON DELETE RESTRICT` | actor (reception or owner) |
| `cancelled_at` | `TIMESTAMPTZ NULL` | NULL if not cancelled |
| `cancel_reason` | `TEXT NULL CHECK char_length ≤ 200` | NULL iff `cancelled_at IS NULL` |
| `trainer_name_snapshot` | `TEXT NOT NULL` | B-05 — `trainers.full_name` at insert time |
| `notes` | `TEXT NULL CHECK char_length ≤ 500` | optional operator note |
| `created_at` / `updated_at` | TimestampMixin |

**Indexes:**
- `ix_pt_sessions_pt_package_id_performed_at_desc (pt_package_id, performed_at DESC)` — supports `GET /pt-packages/{id}/sessions` ordering.
- `ix_pt_sessions_trainer_id_performed_at_desc (trainer_id, performed_at DESC)` — supports future "trainer load" analytics (out of v1.4, but cheap index now).

**CHECK constraints:**
- `cancel_reason IS NULL OR cancelled_at IS NOT NULL` (consistency invariant).
- `char_length(cancel_reason) <= 200` partial.
- `char_length(notes) <= 500` partial.

**NO unique constraints.** Multiple sessions per package per day are allowed (no business rule preventing same-day re-recording).

### D-34-03: Module shape

`app/modules/pt_sessions/`:
- `__init__.py` — module marker (empty body; no public re-exports needed at module level).
- `constants.py` — `BACKDATING_WINDOW_DAYS_RECEPTION = 7` (B-11), `CANCEL_WINDOW_HOURS_RECEPTION = 24` (B-12), `MAX_NOTES_CHARS = 500`, `MAX_CANCEL_REASON_CHARS = 200`. NO local FSM (single-row mutation only — `cancelled_at` set/unset; no multi-state machine).
- `models.py` — `PtSession` ORM (mirrors PT-14 columns; SA `Mapped[]` typed).
- `repository.py` — `find_by_id`, `list_by_pt_package_id` (pagination), `atomic_decrement_pt_package` helper (raw `text()` SQL or `sa.update().returning()` — D-34-04 picks), `atomic_increment_pt_package_on_cancel`, `count_active_for_pt_package` (used in cancel logic to decide if revert exhausted→active).
- `schemas.py` — `PtSessionCreate { pt_package_id: UUID, trainer_id: UUID, performed_at: datetime, notes: str | None }`, `PtSessionCancelRequest { cancel_reason: str ≤200 }`, `PtSessionResponse { id, pt_package_id, trainer_id, client_id, performed_at, performed_by_user_id, cancelled_at, cancel_reason, trainer_name_snapshot, notes, created_at }`. ALL extend `BackendSchemaBase`; mutations use `ConfigDict(extra='forbid')`.
- `service.py` — `record_pt_session`, `cancel_pt_session`, `list_pt_sessions_by_package`, `get_pt_session_by_id`. NO helpers shared with `pt_packages` module (modules-independent contract).
- `router.py` — endpoints below; mounts on `/api/v1/pt-sessions` for POST/cancel/get, and the single nested `GET /api/v1/pt-packages/{id}/sessions` (D-34-08 decision).
- `permissions.py` — empty stub (existing precedent: memberships/pt_packages declare `require_permission(...)` inline in router).

### D-34-04: Race-safe decrement — single SQL `UPDATE ... RETURNING` (PT-16)

In `pt_sessions/repository.py`:

```python
async def atomic_decrement_pt_package(
    session: AsyncSession, pt_package_id: UUID
) -> int | None:
    """Race-safe decrement. Returns new sessions_remaining on success;
    None on 0-row update (caller raises 409 pt_package_exhausted).

    The predicate `sessions_remaining > 0 AND status = 'active'` makes the
    UPDATE the SOLE arbiter of "can we record a session" — concurrent
    callers serialise at the row lock; the loser sees 0 rows updated.
    """
    stmt = (
        sa.update(PtPackage)
        .where(
            PtPackage.id == pt_package_id,
            PtPackage.sessions_remaining > 0,
            PtPackage.status == "active",
        )
        .values(sessions_remaining=PtPackage.sessions_remaining - 1)
        .returning(PtPackage.sessions_remaining)
    )
    result = await session.execute(stmt)
    row = result.first()
    return None if row is None else int(row[0])
```

**Why:** Mirrors v1.2 D-19 visits-check-in race-safe UPDATE pattern + Phase 25 freeze CAS pattern. The DB-layer CHECK `sessions_remaining >= 0` is defence-in-depth (PT-16); the predicate `> 0` is the primary gate. Loser sees 0-row return, raises `pt_package_exhausted` 409.

**Cross-module model import allowance** — `pt_sessions/repository.py` imports `PtPackage` ORM from `pt_packages.models`. **This violates the strict `modules-independent` reading.** Two resolution options:
1. **(Recommended, D-34-04a)** Use raw `text()` SQL referencing the `pt_packages` table by name without importing the ORM model:
   ```python
   stmt = sa.text("""
       UPDATE pt_packages
       SET sessions_remaining = sessions_remaining - 1,
           updated_at = now()
       WHERE id = :pt_package_id
         AND sessions_remaining > 0
         AND status = 'active'
       RETURNING sessions_remaining
   """)
   result = await session.execute(stmt, {"pt_package_id": pt_package_id})
   row = result.first()
   return None if row is None else int(row[0])
   ```
   Same approach for cancel-increment + exhausted→active revert. Keeps `pt_sessions.repository` importing ONLY from `app.modules.pt_sessions.*` and `app.core.*` + SA + asyncpg — passes `import-linter modules-independent` contract without exception.
2. (Rejected) Introduce a Protocol slot `register_pt_package_balance_mutator` in `core/dependencies.py` callable from `pt_sessions` — over-engineering for two SQL statements; raw `text()` is the standard escape hatch used in v1.2 visits/check-in path.

**Decision: D-34-04a (raw `text()` SQL).** Planner adds `# noqa: TABLE_REF cross-module SQL` comment for grep-ability. **Auto-default selected.**

### D-34-05: Auto-exhausted transition (PT-17) — same UoW, single emit

In `pt_sessions/service.py:record_pt_session`:

```python
new_remaining = await repository.atomic_decrement_pt_package(session, pt_package_id)
if new_remaining is None:
    raise PtPackageExhaustedError("pt_package_exhausted")  # → 409

session_row = await repository.insert_pt_session(session, ...)
audit.emit("pt_session_recorded", payload=PtSessionRecordedPayload(
    pt_session_id=session_row.id,
    pt_package_id=pt_package_id,
    client_id=session_row.client_id,
    trainer_id=session_row.trainer_id,
    trainer_name_snapshot=session_row.trainer_name_snapshot,
    performed_at=session_row.performed_at.isoformat(),
    performed_by_user_id=session_row.performed_by_user_id,
    sessions_remaining_after=new_remaining,
))

if new_remaining == 0:
    await repository.atomic_transition_to_exhausted(session, pt_package_id)
    audit.emit("pt_package_exhausted", payload=PtPackageExhaustedPayload(
        pt_package_id=pt_package_id,
        client_id=session_row.client_id,
        exhausted_at=datetime.now(UTC),
    ), resource_type="pt_package")

await session.commit()
return session_row
```

`atomic_transition_to_exhausted` uses raw `text()`:
```sql
UPDATE pt_packages
SET status = 'exhausted', updated_at = now()
WHERE id = :pt_package_id AND status = 'active'
```

**Why:** Exhausted is a derived terminal state — once `sessions_remaining = 0` is observed inside the SAME UoW that just produced it, the transition is monotone. The `WHERE status = 'active'` predicate guards against a concurrent refund flipping status to cancelled mid-transaction (the SELECT-then-UPDATE would otherwise overwrite cancelled→exhausted). Phase 33 `PT_PACKAGE_STATUS_TRANSITIONS` allows `active → {exhausted, expired, cancelled}` — the predicate ensures we only flip from active, never from cancelled/expired.

Emit `pt_package_exhausted` ONCE per package (PT-17 verbatim). Sentinel `exhausted_at` is `datetime.now(UTC)` (audit-timestamp semantics, distinct from `performed_at` which is the session wall-clock).

### D-34-06: Backdating window (B-11)

In `pt_sessions/service.py:record_pt_session`, BEFORE decrement:

```python
now = datetime.now(UTC)
delta = now - performed_at

# Future-dated rejection (always — neither role can record into the future).
if delta.total_seconds() < 0:
    raise PerformedAtOutOfWindowError("performed_at_in_future")  # → 422

# Backdating window — reception 7d, owner unlimited.
if actor.role == Role.RECEPTION and delta > timedelta(days=BACKDATING_WINDOW_DAYS_RECEPTION):
    raise PerformedAtOutOfWindowError("performed_at_out_of_window")  # → 422
```

**Decisions captured:**
- **Future-dated rejection applies to BOTH roles.** Recording a session that hasn't happened yet is a semantic error (PT-session = factual record of a completed training). Owner-unlimited applies to the PAST direction only. Error code `performed_at_in_future` distinct from `performed_at_out_of_window` for UI clarity.
- **Window measured from `datetime.now(UTC)` at request time** vs. `performed_at`. NOT vs `created_at` (B-11 is about backdating distance, not retroactivity-of-edit). The 7-day window is in **calendar days**, computed as `timedelta(days=7)` exact-duration (168 hours) — NOT "7 calendar boundaries in Europe/Moscow." Pragmatic and timezone-agnostic.
- Owner is unlimited in the past — explicit allowance for migrating historical logs in v1.5+ or corrections on long-overdue paperwork.

### D-34-07: Cancel-window enforcement (B-12)

In `pt_sessions/service.py:cancel_pt_session`:

```python
session_row = await repository.find_by_id(session, pt_session_id)
if session_row is None:
    raise PtSessionNotFoundError("pt_session_not_found")  # → 404
if session_row.cancelled_at is not None:
    raise PtSessionAlreadyCancelledError("already_cancelled")  # → 409

if actor.role == Role.RECEPTION:
    age = datetime.now(UTC) - session_row.created_at
    if age > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError("cancel_window_expired")  # → 403
```

**Decisions captured:**
- **Window measured from `created_at` (recording-time), not `performed_at`.** Rationale: B-12 reception-24h is about "soon after the operator entered the record" — correction of immediate input mistakes. Owner-anytime branch ignores `created_at`. **This deviates from a literal reading of PT-18 ("reception within 24h of recording") in a confirming direction — "recording" = INSERT time = `created_at`.**
- **403 not 409** for cancel-window-expired — actor authorisation issue, not state conflict. Mirrors `OWNER_ONLY` 403 mapping convention.
- **Already-cancelled is 409** (idempotent semantics deferred; repeat cancel with same `Idempotency-Key` returns cached response via D-34-10; different keys against same row → 409 — operator can read state via GET first).

### D-34-08: Read API path — single endpoint at `/api/v1/pt-packages/{id}/sessions`

PT-19 specifies `GET /api/v1/pt-packages/{id}/sessions`. **Implementation lives in `pt_sessions/router.py`** under a `prefix='/api/v1/pt-packages'` sub-router declaration:

```python
# pt_sessions/router.py
package_scoped_router = APIRouter(prefix="/api/v1/pt-packages", tags=["pt-sessions"])

@package_scoped_router.get("/{pt_package_id}/sessions", ...)
async def list_sessions_by_package(...): ...
```

Both routers (`router` and `package_scoped_router`) are mounted from `app/main.py` (or aggregator). Subject-side ownership principle (D-33-18) is satisfied: the endpoint's IMPLEMENTATION lives with the entity that owns the data (pt_sessions), even though the URL path is rooted at the parent resource.

**No `GET /api/v1/pt-sessions` flat-list endpoint in v1.4** (PT-19 doesn't require it; cross-package aggregation deferred).

**Pagination envelope** `{items, total, page, pageSize}` — standard Phase 8 pattern. Default `pageSize=20`, max `pageSize=100`. Filter: `?include_cancelled=true|false` (default `true` — show all; UI/operator filters client-side or sets `false`). Ordering: `performed_at DESC, created_at DESC` (latest-first).

### D-34-09: Endpoints + permissions

| Method | Path | Auth | Permission | Idempotency-Key | CSRF |
|---|---|---|---|---|---|
| POST | `/api/v1/pt-sessions` | reception+owner | `(CREATE, PT_SESSIONS)` | **required** (D-34-10) | required |
| POST | `/api/v1/pt-sessions/{id}/cancel` | reception(time-gated) + owner | `(CANCEL, PT_SESSIONS)` *but checked at handler not OWNER_ONLY frozenset* | **required** | required |
| GET | `/api/v1/pt-sessions/{id}` | reception+owner | `(VIEW, PT_SESSIONS)` | — | — |
| GET | `/api/v1/pt-packages/{id}/sessions` | reception+owner | `(LIST, PT_SESSIONS)` | — | — |

**Cancel-endpoint permission carve-out (deviation from Phase 30 INFRA-19 default).** Phase 30 placed `(CANCEL, PT_SESSIONS)` in `OWNER_ONLY` frozenset (line 88 of `core/permissions.py`). PT-18 / B-12 actually grants reception a 24h window. **Resolution:** keep `(CANCEL, PT_SESSIONS)` in `OWNER_ONLY` (DB-layer 403 for reception) — but ADD an application-layer reception-bypass branch in `cancel_pt_session` that re-checks the role + 24h window AND issues an explicit `require_permission` call substitute. Two viable shapes:

- **Recommended D-34-09a:** Move `(CANCEL, PT_SESSIONS)` OUT of `OWNER_ONLY` (RBAC says "both roles can call the endpoint"), and enforce the 24h window inside `cancel_pt_session` (D-34-07). This requires an Phase 34 amendment to `core/permissions.py` (`OWNER_ONLY` shrinks by 1 entry) AND admin-web `can.ts` byte-parity update (D-34-19). Mirrors B-07 uniform-reception discipline for refund.
- (Rejected D-34-09b) Keep RBAC strict (owner-only) — reception gets 403 even within 24h. Violates B-12 verbatim wording.

**Decision: D-34-09a (move out of OWNER_ONLY, application-layer enforces 24h).** Planner adds amendment commit to `core/permissions.py` + admin-web `can.ts` byte-parity (admin-web is frozen-as-of-v1.3 per Phase 35 scope note — BUT permissions byte-parity test is a tooling concern, not a feature concern; tooling fix permitted). **Auto-default selected.**

### D-34-10: `Idempotency-Key` required on POST endpoints

Both `POST /pt-sessions` and `POST /pt-sessions/{id}/cancel` require `Idempotency-Key` header. Reuses `app.core.idempotency.idempotency_dependency` from Phase 32 verbatim — same Redis namespace `sz:idem:{key}` 1h TTL; replay returns cached envelope; same-key/different-body → 422 `idempotency_key_reuse`.

**Why:** Mirrors money-mutating discipline (D-32-10 / D-33-16) — although PT-session recording does not insert a payment row, it DOES decrement a paid-for balance. Network retry on a 5xx mid-request without idempotency could double-decrement. Cancel endpoint inherits same requirement for symmetry (refund-window equivalence).

GET endpoints — no `Idempotency-Key` (read-only).

### D-34-11: Cancel — restore balance + conditional exhausted→active revert (PT-18)

In `pt_sessions/service.py:cancel_pt_session`, after window/state guards:

```python
package = await pt_packages_repository.find_by_id_for_update(session, session_row.pt_package_id)
# NB: cross-module ORM read — see D-34-04a; use raw text() to avoid model import.
prior_status = package.status

# Update session row: cancelled_at, cancel_reason.
await repository.mark_cancelled(session, pt_session_id, cancel_reason=cancel_reason)

# Restore one balance unit, with defence-in-depth ceiling.
new_remaining = await repository.atomic_increment_pt_package(session, package_id)
# raw text(): UPDATE pt_packages SET sessions_remaining = sessions_remaining + 1, updated_at = now()
#             WHERE id=:id AND sessions_remaining < session_count_snapshot
#             RETURNING sessions_remaining, status
# 0-row return is a hard logic error (CHECK invariant violation) → raise 500.

package_reactivated = False
if prior_status == "exhausted":
    # Transition back to active. PT_PACKAGE_STATUS_TRANSITIONS does NOT include
    # exhausted → active (Phase 33 D-33-04: terminal-active-only path is forward).
    # PT-18 introduces this single reverse transition; we DO NOT extend the
    # global FSM — instead, the cancel flow performs a guarded direct UPDATE
    # under the controlled invariant "we just freed a balance unit from an
    # exhausted package," with predicate WHERE status='exhausted'.
    await repository.atomic_transition_exhausted_to_active(session, package_id)
    package_reactivated = True

audit.emit("pt_session_cancelled", payload=PtSessionCancelledPayload(
    pt_session_id=pt_session_id,
    pt_package_id=package_id,
    client_id=session_row.client_id,
    cancel_reason=cancel_reason,
    sessions_remaining_after=new_remaining,
    package_reactivated=package_reactivated,
), resource_type="pt_session")

await session.commit()
```

**FSM extension policy:**
- **Recommended D-34-11a:** Do NOT add `exhausted: frozenset({active})` to `PT_PACKAGE_STATUS_TRANSITIONS`. The transition is local to cancel-flow and gated by predicate (`WHERE status='exhausted'`). Phase 33 FSM stays unchanged. Document the carve-out in `pt_sessions/service.py` docstring + a sentence in `pt_packages/constants.py:PT_PACKAGE_STATUS_TRANSITIONS` comment ("Reverse-transition `exhausted → active` is performed ONLY by `pt_sessions.service.cancel_pt_session` under the controlled invariant of freeing a balance unit; not a general-case allowed transition").
- (Rejected D-34-11b) Extend FSM with `exhausted → {cancelled, active}` — opens the door to other callers performing the reverse transition for unrelated reasons; weakens the FSM as a documented contract.

**Decision: D-34-11a (predicate-gated direct UPDATE, FSM unchanged).** **Auto-default selected.**

**What about `cancelled` / `expired` parent package?**
- Parent status `cancelled` or `expired` at cancel-time: still increment `sessions_remaining` (data-integrity — refund of a session against a refunded package mathematically restores the balance even though the package itself is terminal). DO NOT revert status. Audit payload `package_reactivated=False`.
- Edge case: if parent package was refunded between recording and cancel, the cancel still proceeds (no 409). Forensic correctness wins; the negative payment row stays as-is.

### D-34-12: Trainer validation via Protocol slot (PT-15)

In `pt_sessions/service.py:record_pt_session`, BEFORE backdating window check:

```python
trainer = await resolve_trainer_by_id(session, trainer_id)
if trainer is None:
    raise TrainerNotFoundError("trainer_not_found")  # → 404
if not trainer.is_active:
    raise TrainerInactiveError("trainer_inactive")  # → 422
```

`TrainerById` Protocol exposes only `id` and `is_active` (Phase 31 `dependencies.py:280-285`). For `trainer_name_snapshot` (B-05), `pt_sessions/service` needs `trainer.full_name`. **Two options:**

- **Recommended D-34-12a:** Extend `TrainerById` Protocol with `full_name: str`. Single additive attribute, ORM row already satisfies structurally (no DTO change). Update Phase 31 docstring on `TrainerById` to note Phase 34 added `full_name` for B-05 snapshot capture.
- (Rejected D-34-12b) Introduce a new Protocol slot `register_trainer_name_resolver` returning `str | None`. Two calls per record-session instead of one; slot proliferation.

**Decision: D-34-12a (extend `TrainerById` with `full_name`).** Planner amendment to `core/dependencies.py:280-285` + Phase 31 trainer resolver implementation (in `trainers/__init__.py` or wherever `register_trainer_by_id_resolver` is wired from `app/main.py`) to ensure the returned object exposes `full_name`. If the existing resolver returns the SA `Trainer` ORM row, the Protocol extension is zero-code (ORM already has `full_name: Mapped[str]`). **Auto-default selected.**

`trainer_name_snapshot = trainer.full_name` captured at insert; persisted as `NOT NULL TEXT` (D-34-02).

### D-34-13: Active package validation via Protocol slot

In `pt_sessions/service.py:record_pt_session`:

```python
# Body has pt_package_id (not client_id). Resolve client via the package row
# itself — but we cannot import PtPackage ORM (modules-independent). Instead,
# we read the package row via raw text() SELECT in repository, OR we use the
# existing `get_active_pt_package(client_id)` slot indirectly. Direct read is
# simpler:
package = await repository.fetch_pt_package_metadata(session, pt_package_id)
# raw text(): SELECT id, client_id, status, sessions_remaining, end_date
#             FROM pt_packages WHERE id = :pt_package_id
if package is None:
    raise PtPackageNotFoundError("pt_package_not_found")  # → 404
if package["status"] != "active":
    raise PtPackageNotActiveError("pt_package_not_active")  # → 409
# sessions_remaining check is deferred to the atomic UPDATE (race-safe gate).
```

**The `get_active_pt_package(client_id)` Protocol slot from Phase 33 (D-33-12)** is designed for `client_id → package` lookup (Telegram bot / client-history queries). For PT-session recording the input is `pt_package_id` directly — the slot's signature doesn't fit. **Two options:**

- **Recommended D-34-13a:** Read package metadata via raw `text()` SELECT in `pt_sessions/repository.fetch_pt_package_metadata` (returns a `dict` or named tuple). Avoid the resolver slot entirely for this read path — the slot's purpose was client→active-package, not id→any-status-package. Document that `pt_sessions` reads `pt_packages` metadata via direct SQL (already the pattern from D-34-04a).
- (Rejected D-34-13b) Expand `ActivePtPackage` Protocol or add `register_pt_package_by_id_resolver` — slot proliferation; raw SQL keeps the contract tight.

**Decision: D-34-13a (raw SQL metadata read).** Phase 34 makes ZERO additions to `core/dependencies.py` for PT-package reads; only the `TrainerById.full_name` extension from D-34-12a. **Auto-default selected.**

### D-34-14: `.importlinter modules-independent` extension

Add `app.modules.pt_sessions` to the `modules` list in `.importlinter` `modules-independent` contract (currently 11 modules; becomes 12). This is the ONLY structural-bedrock change in Phase 34. Verify by running `lint-imports` locally — pt_sessions must not import `app.modules.pt_packages`, `app.modules.trainers`, `app.modules.memberships`, etc. (raw `text()` SQL strings referencing the OTHER modules' tables are NOT imports and pass the contract — D-34-04a relies on this.)

### D-34-15: SVC001 walker scope auto-coverage

`_SERVICE_GLOB = "modules/**/service.py"` (test_service_commit_gate.py:31) automatically picks up `pt_sessions/service.py`. ALL state-mutating public service functions (`record_pt_session`, `cancel_pt_session`) MUST `await session.commit()` explicitly. Helper functions stay private (`_`-prefixed) or carry the `# noqa: SVC001 caller-owns-txn` marker.

**No Phase 30 amendment needed** — glob coverage is implicit.

### D-34-16: PT-sessions ⊥ visits (PT-20 / Q3)

Phase 34 service code MUST NOT touch `visits` table. ABSENCE-enforced — no Phase 34 file imports `visits.repository` / `visits.models` (importlinter modules-independent verifies). The reverse (visits never touches pt_sessions) is already a property of the existing visits module — no Phase 34 change to `visits/*`.

Document explicitly in `pt_sessions/service.py` module-level docstring: "PT-sessions are orthogonal to visits per PT-20 / Q3. Recording a PT-session does not create a visit row; checking in does not create a PT-session. This is enforced by absence — no cross-table writes."

### D-34-17: Audit emit ordering + payload contracts

Single UoW emit order on record:
1. `pt_session_recorded` (after INSERT + balance decrement; payload includes `sessions_remaining_after = new_remaining`).
2. `pt_package_exhausted` (ONLY if `new_remaining == 0`; payload `exhausted_at = datetime.now(UTC)`).

Single UoW emit order on cancel:
1. `pt_session_cancelled` (payload `sessions_remaining_after = new_remaining`, `package_reactivated = bool`).

NO `pt_package_reactivated` event — the `package_reactivated` boolean in `pt_session_cancelled` payload subsumes the signal. The audit trail can reconstruct the reactivation via `pt_session_cancelled.package_reactivated=true`.

`audit.emit(event, payload=..., resource_type=...)` call shape: planner picks between positional vs keyword (audit.py:196-197 registry uses tuple keys; emit signature confirmed in code review).

Both payloads use the locked Pydantic schemas (`PtSessionRecordedPayload`, `PtSessionCancelledPayload`) — `audit.emit` validates against `AUDIT_PAYLOAD_SCHEMAS` registry entry verbatim. NO schema modifications by Phase 34.

### D-34-18: Error code catalogue (Phase 34 surface)

| Code | HTTP | Origin |
|---|---|---|
| `pt_package_not_found` | 404 | record_pt_session, cancel_pt_session |
| `pt_package_not_active` | 409 | record_pt_session (pre-decrement guard; race-loser uses next code) |
| `pt_package_exhausted` | 409 | record_pt_session (atomic UPDATE 0-row result) |
| `pt_session_not_found` | 404 | cancel_pt_session, GET endpoints |
| `already_cancelled` | 409 | cancel_pt_session |
| `cancel_window_expired` | 403 | cancel_pt_session (reception >24h) |
| `trainer_not_found` | 404 | record_pt_session |
| `trainer_inactive` | 422 | record_pt_session |
| `performed_at_in_future` | 422 | record_pt_session |
| `performed_at_out_of_window` | 422 | record_pt_session (reception >7d) |
| `idempotency_key_reuse` | 422 | shared core.idempotency dependency |

Existing codes from Phase 32/33 (`already_refunded`, `invalid_transition`) are NOT raised from Phase 34 directly — only via cross-module audit events (parent package refund happens in `pt_packages` module).

### D-34-19: Tests scope

- **Unit:**
  - Backdating window math (B-11): reception 7d boundary inclusive/exclusive, owner unlimited past, both roles reject future.
  - Cancel window math (B-12): reception 24h from `created_at` boundary, owner anytime.
  - FSM-revert guard: predicate `WHERE status='exhausted'` only flips that single source.
- **Integration (httpx ASGITransport):**
  - Record golden path → 201; audit chain `pt_session_recorded` only.
  - Record decrementing to 0 → 201 + audit chain `pt_session_recorded` + `pt_package_exhausted` (single emit).
  - Record against exhausted package → 409 `pt_package_exhausted` (race-loser path simulated via pre-zeroed `sessions_remaining`).
  - Record against expired/cancelled package → 409 `pt_package_not_active`.
  - Record with inactive trainer → 422 `trainer_inactive`.
  - Record future-dated → 422 `performed_at_in_future`.
  - Record 8 days back as reception → 422 `performed_at_out_of_window`; as owner → 201.
  - Cancel within 24h as reception → 200 + audit `pt_session_cancelled` (`package_reactivated=false`).
  - Cancel 25h after recording as reception → 403 `cancel_window_expired`; as owner → 200.
  - Cancel session of exhausted package → 200 + balance restored + status `exhausted → active` + `package_reactivated=true`.
  - Cancel session of cancelled (refunded) package → 200 + balance restored + status STAYS `cancelled` + `package_reactivated=false`.
  - Already-cancelled session → 409 `already_cancelled`.
  - List sessions paginated, include_cancelled filter, performed_at DESC ordering.
- **Postgres-only race test PTS-TEST-01** (`@requires_postgres` marker; SKIP on SQLite per Phase 33 D-33-19 precedent):
  - 2 concurrent `POST /pt-sessions` against `sessions_remaining=1` package → exactly one 201, one 409. Audit log shows exactly one `pt_session_recorded` + one `pt_package_exhausted`.
- **Permissions byte-parity:**
  - Backend `OWNER_ONLY` removed entry: verify `(Action.CANCEL, Resource.PT_SESSIONS)` is NOT in the frozenset.
  - Admin-web `can.ts` — verify the matching entry is also removed; existing byte-parity test (Phase 30 INFRA-19) catches drift automatically.

### D-34-20: OpenAPI / `schema.d.ts` regen — NOT Phase 34

Phase 34 ships backend endpoints WITHOUT byte-stable OpenAPI regen. **Phase 35** owns the regen + drift-gate green for all v1.4 typed paths (per ROADMAP.md descope 2026-05-15). Planner instructions: do NOT run `pnpm openapi:gen` or commit `apps/backend/openapi.json` / `packages/api-client/src/schema.d.ts` deltas inside Phase 34. Phase 35 takes the full v1.4 OpenAPI surface in one atomic regen commit.

### Claude's Discretion

- Internal helper split between `pt_sessions/service.py` (orchestration) and `pt_sessions/repository.py` (SQL) — planner picks granularity.
- `permissions.py` may be empty stub (memberships precedent).
- Test file naming follows `test_pt_sessions_<concern>.py` convention from `test_memberships_<concern>.py` / `test_pt_packages_<concern>.py`.
- Repository signature: positional vs keyword-only — planner follows file-local repo convention.
- Where to declare nested router (`/api/v1/pt-packages/{id}/sessions`): inside `pt_sessions/router.py` as a separate `APIRouter` instance with its own prefix, mounted alongside the main router from the aggregator. Planner picks the exact aggregation file (likely `app/main.py:create_app()` or `app/api/__init__.py`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap / Requirements / Locked bedrock
- `.planning/ROADMAP.md` §«Phase 34: PT-Session Recording» — phase goal, depends-on (Phases 31, 33), 5 success criteria.
- `.planning/REQUIREMENTS.md` §97-105 — PT-14..PT-22 detailed (9 requirements in scope).
- `.planning/REQUIREMENTS.md` §«Locked bedrock decisions» — B-05 (`trainer_name_snapshot`), B-07 (uniform reception RBAC — informs D-34-09a), B-11 (backdating 7d/unlimited), B-12 (cancel 24h/anytime).
- `.planning/PROJECT.md` — Sportzal core value, region/cash constraints.

### Phase 30 Bedrock (audit + RBAC consumed here)
- `.planning/phases/30-foundations-tech-debt-bedrock/30-CONTEXT.md` — full bedrock decisions.
- `.planning/phases/30-foundations-tech-debt-bedrock/30-01-PLAN.md` & `30-01-SUMMARY.md` — `LOCKED_AUDIT_EVENTS` 51 entries (includes `pt_session_recorded`, `pt_session_cancelled`, `pt_package_exhausted`); `audit_payloads.py` Pydantic schemas including `PtSessionRecordedPayload`, `PtSessionCancelledPayload`, `PtPackageExhaustedPayload`.
- `.planning/phases/30-foundations-tech-debt-bedrock/30-02-PLAN.md` & `30-02-SUMMARY.md` — `Resource.PT_SESSIONS` enum entry + `OWNER_ONLY` extension. **Phase 34 D-34-09a amends this:** `(Action.CANCEL, Resource.PT_SESSIONS)` MUST be REMOVED from `OWNER_ONLY` (originally added line 88 of `apps/backend/app/core/permissions.py`).
- `.planning/phases/30-foundations-tech-debt-bedrock/30-03-PLAN.md` & `30-03-SUMMARY.md` — `.importlinter modules-independent` contract list (Phase 34 adds `app.modules.pt_sessions` as 12th entry).
- `apps/backend/app/core/audit_payloads.py:278-313` — `PtSessionRecordedPayload` + `PtSessionCancelledPayload` exact field definitions (locked, MUST match Phase 34 emit call payloads byte-for-byte).
- `apps/backend/app/core/audit_payloads.py:237-253` — `PtPackageExhaustedPayload` with `exhausted_at: datetime` field added in Phase 33 D-33-15 explicitly for the Phase 34 callsite.
- `apps/backend/app/core/audit_payloads.py:341-345` — registry tuples `(event, resource_type)` for all three events.
- `apps/backend/app/core/audit.py:196-197` — locked event registry (already contains pt_session entries with `resource_type='pt_session'`).
- `apps/backend/app/core/permissions.py:49-50, 76-88` — Resource enum + OWNER_ONLY frozenset; Phase 34 amendment REMOVES line 88 entry.
- `apps/backend/.importlinter` lines 12-29 — modules-independent contract; Phase 34 adds 12th module entry.

### Phase 31 Trainers (Protocol slot consumed)
- `.planning/phases/31-trainers-module/31-CONTEXT.md` — trainer module decisions.
- `apps/backend/app/core/dependencies.py:270-304` — `TrainerById` Protocol + `register_trainer_by_id_resolver` + `resolve_trainer_by_id`. **Phase 34 D-34-12a amends:** extend `TrainerById` Protocol with `full_name: str` for B-05 snapshot.
- `apps/backend/app/modules/trainers/models.py:28` — `Trainer.full_name: Mapped[str]` (satisfies extended Protocol structurally; zero implementation change required to the resolver wiring if it returns the ORM row).
- `apps/backend/app/main.py` — site of `register_trainer_by_id_resolver(...)` call (Phase 31 wiring; Phase 34 consumes the registered slot via `resolve_trainer_by_id`).

### Phase 33 PT-Packages (table + resolver consumed)
- `.planning/phases/33-pt-package-plans-instances/33-CONTEXT.md` — full PT-package decisions; FSM, snapshot, refund flow.
- `.planning/phases/33-pt-package-plans-instances/33-01-PLAN.md` / `33-02-PLAN.md` / `33-03-PLAN.md` & SUMMARYs — migration 0014, status FSM, sale flow, cancel/refund, cron.
- `apps/backend/app/modules/pt_packages/constants.py:PT_PACKAGE_STATUS_TRANSITIONS` — FSM source of truth; Phase 34 D-34-11a documents the carve-out for `exhausted → active` predicate-gated reverse transition WITHOUT modifying this constant.
- `apps/backend/app/modules/pt_packages/models.py` — `PtPackage` ORM (Phase 34 reads metadata via raw `text()` SELECT per D-34-04a / D-34-13a; does NOT import this ORM).
- `apps/backend/app/core/dependencies.py:123-194` — `ActivePtPackage` Protocol + `register_active_pt_package_resolver` + `get_active_pt_package`. Phase 34 does NOT consume this slot for the recording path (D-34-13a) — slot remains for future client→active-package lookups.
- `apps/backend/alembic/versions/0014_pt_packages.py` — down_revision target for `0015_pt_sessions`.

### Pattern templates
- `apps/backend/app/modules/memberships/service.py` — orchestrator pattern (caller-owns-txn + audit emit + commit) — mirror for `record_pt_session` and `cancel_pt_session`.
- `apps/backend/app/modules/memberships/service.py:198-260` — `_assert_can_transition` central guard (mirror only loosely — PT-session doesn't have its own FSM; the only transition is parent-package exhausted↔active which is predicate-gated direct UPDATE).
- `apps/backend/app/modules/pt_packages/service.py` — pt_packages create/cancel/refund pattern; PT-session sale shape (D-34-05) follows the same shape minus payment_recorder consumption.
- `apps/backend/app/modules/visits/service.py` & `apps/backend/app/modules/visits/repository.py` — v1.2 race-safe UPDATE pattern (`check_in_visit` atomic SELECT-and-UPDATE under predicate); precedent for D-34-04a raw `text()` SQL escape hatch.
- `apps/backend/app/modules/clients/`, `apps/backend/app/modules/memberships/` — module shape reference (constants/models/repository/schemas/service/router layout).

### Cross-cutting infra
- `apps/backend/app/schemas/base.py` — `BackendSchemaBase`, `to_camel`, `BackendResponseModel`.
- `apps/backend/app/core/idempotency.py` — `idempotency_dependency` FastAPI dep (reuse verbatim for POST /pt-sessions + POST /pt-sessions/{id}/cancel per D-34-10).
- `apps/backend/app/core/audit.py` — `audit.emit(event, payload=, resource_type=)` call signature (planner confirms exact kwargs from the code).
- `apps/backend/tests/unit/test_service_commit_gate.py:31` — `_SERVICE_GLOB = "modules/**/service.py"` automatically covers `pt_sessions/service.py`; no Phase 34 amendment needed.
- `apps/backend/tests/unit/test_payments_appendonly.py` — append-only AST walker (Phase 34 INSERT/UPDATE on `pt_sessions` table is allowed; walker only guards `payments`).
- `apps/backend/tests/conftest.py` (or `requires_postgres` marker definition) — Postgres-only test gating for PTS-TEST-01.

### Admin-web (frozen — byte-parity only)
- `apps/admin-web/src/shared/session/can.ts` — `OWNER_ONLY` mirror; Phase 34 D-34-09a removes `(CANCEL, PT_SESSIONS)` entry to maintain byte-parity. NO new routes, NO new UI components.
- Existing byte-parity test (Phase 30 INFRA-19) — catches drift automatically.

### Migration ordering
- `apps/backend/alembic/versions/0014_pt_packages.py` — down_revision target for `0015_pt_sessions`.
- No other v1.4 migration depends on `0015_pt_sessions` (Phase 35 is OpenAPI-only, Phase 36 is verification-only).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (zero re-implementation)
- **`core.dependencies.TrainerById` Protocol + `resolve_trainer_by_id`** — Phase 31 already wired; Phase 34 extends Protocol with `full_name` per D-34-12a (ORM satisfies structurally; zero implementation change to the registration site).
- **`core.dependencies.get_active_pt_package`** — exists but NOT consumed by Phase 34 record path (per D-34-13a). Remains available for future client→active-package lookups.
- **`core.idempotency.idempotency_dependency`** — FastAPI Depends ready; Phase 34 reuses on both POST endpoints.
- **`PT_PACKAGE_STATUS_TRANSITIONS` MappingProxyType** — Phase 34 consumes for `status='active'` predicate validation read-side ONLY; FSM constant UNCHANGED (D-34-11a).
- **`PtSessionRecordedPayload` / `PtSessionCancelledPayload` / `PtPackageExhaustedPayload` Pydantic schemas** — already locked in Phase 30 / Phase 33; Phase 34 emit payloads must match field-for-field.
- **`audit.emit` registry lookup** — already has `(pt_session_recorded, pt_session)` and `(pt_session_cancelled, pt_session)` tuples; Phase 34 emit call sites Just Work™.
- **`Resource.PT_SESSIONS` + `OWNER_ONLY` entries** — Phase 30 INFRA-18/19 landed all relevant entries; Phase 34 D-34-09a removes ONE entry `(CANCEL, PT_SESSIONS)` to align with B-12 reception-window.
- **SVC001 walker glob** — `modules/**/service.py` auto-covers `pt_sessions/service.py`. No test amendment needed.
- **`memberships/service.refund_membership` and `pt_packages/service.refund_pt_package`** — orchestrator template (load → guard → mutate → audit → commit). Phase 34 `record_pt_session` and `cancel_pt_session` follow this shape minus payment_recorder consumption.
- **`visits/service.check_in_visit` race-safe UPDATE pattern** — direct precedent for D-34-04a single-statement `UPDATE ... WHERE predicate ... RETURNING` shape.
- **`schemas/base.BackendSchemaBase` + camelCase alias generator** — used by all module schemas.

### Established Patterns
- **Caller-owns-txn (D-03)**: `record_pt_session` and `cancel_pt_session` own UoW + commit; helpers private (`_`-prefixed) or marked `# noqa: SVC001 caller-owns-txn` (cron-style; no cron in Phase 34).
- **Race-safe single-statement UPDATE under predicate**: visits check-in pattern (v1.2), memberships freeze CAS (v1.3), payments refund_of UNIQUE (Phase 32) — Phase 34 D-34-04a is the next iteration.
- **Snapshot for historical UI integrity**: `trainer_name_snapshot` (B-05) parallels `plan_name_snapshot` in memberships/pt_packages.
- **Locked audit events + Pydantic payload schemas via `audit.emit` registry**: zero schema edits in Phase 34; emit call sites consume locked schemas.
- **Protocol slots in `core.dependencies` registered exclusively from `create_app()`**: Phase 34 adds ZERO new slots; extends `TrainerById` Protocol surface only.
- **Idempotency-Key on ALL money-or-balance-affecting POSTs**: precedent Phase 32 D-32-10 (sale + refund) → Phase 33 D-33-16 (PT-package sale/cancel/refund) → Phase 34 D-34-10 (PT-session record/cancel).
- **Cross-module SQL via raw `text()` (NOT ORM import)**: visits→clients precedent. Phase 34 D-34-04a uses this for pt_sessions→pt_packages metadata reads + balance mutations.
- **Pagination envelope `{items, total, page, pageSize}`** for GET list endpoints (Phase 8 standard).

### Integration Points
- **`app/main.py:create_app()`**: Phase 34 mounts `pt_sessions_router` + the package-scoped sub-router (`/api/v1/pt-packages/{id}/sessions`); NO new resolver registration calls (Phase 31 and 33 wirings already in place).
- **`core/dependencies.py:280-285`**: Phase 34 amendment — extend `TrainerById` Protocol with `full_name: str` (D-34-12a). Touches ~3 lines + docstring.
- **`core/permissions.py:88`**: Phase 34 amendment — REMOVE `(Action.CANCEL, Resource.PT_SESSIONS)` line from `OWNER_ONLY` frozenset (D-34-09a). Single-line delete.
- **`apps/admin-web/src/shared/session/can.ts`**: Phase 34 amendment — REMOVE mirror entry for `(CANCEL, PT_SESSIONS)` to maintain byte-parity test green. Single-line delete.
- **`.importlinter`**: add `app.modules.pt_sessions` to `modules-independent` contract (12th module).
- **Migration `0015_pt_sessions.py`**: down_revision = `"0014_pt_packages"`. FK to `pt_packages.id`, `trainers.id`, `clients.id`, `users.id` — all `ON DELETE RESTRICT`.
- **No `app/workers/*` changes** — Phase 34 introduces no cron jobs.
- **No `audit_payloads.py` changes** — all three event payload schemas (`PtSessionRecordedPayload`, `PtSessionCancelledPayload`, `PtPackageExhaustedPayload`) pre-locked in Phase 30 / 33.

</code_context>

<specifics>
## Specific Ideas

- **`Idempotency-Key` semantics for cancel-endpoint**: same key replayed within 1h → cached success response (200 + `package_reactivated` boolean preserved). Different key on already-cancelled row → 409 `already_cancelled`. The idempotency layer is the first-line guard; the application-layer `already_cancelled` check is the second-line guard.
- **`performed_at` timezone discipline**: client sends ISO-8601 with offset (e.g., `2026-05-16T10:00:00+03:00`); server stores `TIMESTAMPTZ`; emit payload `performed_at` is `str` (per `PtSessionRecordedPayload.performed_at: str` — already-locked schema). Planner uses `datetime.isoformat()` for emit.
- **`exhausted_at` semantics**: `datetime.now(UTC)` at the moment of the audit emit (audit-clock, NOT `performed_at` — `performed_at` is the wall-clock of the training; `exhausted_at` is the operator-action clock that exhausted the package).
- **Russian-locale free-text** in `notes` and `cancel_reason` — passthrough TEXT, no enum coercion; UI/operator types free-form.
- **`package_reactivated=true` audit signal** is the reconstruction key for forensic "session-cancel restored exhausted package to active" analysis. No separate `pt_package_reactivated` event needed (D-34-17).
- **CHECK `cancel_reason IS NULL OR cancelled_at IS NOT NULL`** — invariant guarantees no orphan `cancel_reason` text without `cancelled_at` timestamp; supports forensic "is this session cancelled?" via single-column check.
- **Composite index `(pt_package_id, performed_at DESC)`** — supports `GET /pt-packages/{id}/sessions` query optimally; `performed_at DESC` ordering matches the index.
- **Race PTS-TEST-01 isolation level**: `READ COMMITTED` (Postgres default; matches Phase 32 REF-TEST-01 / Phase 33 REF-TEST-02 isolation). The `WHERE sessions_remaining > 0 ... RETURNING` UPDATE acquires the row lock that serialises concurrent decrements.

</specifics>

<deferred>
## Deferred Ideas

- **Edit-after-record** (correct trainer / notes / `performed_at` after a session is recorded) — out of v1.4. Workflow: cancel + re-record. Future: `PATCH /api/v1/pt-sessions/{id}` with full audit-chain.
- **Cross-package session history aggregation** — `GET /api/v1/clients/{id}/pt-sessions` summing sessions across all packages for a client — out of v1.4 (PT-19 explicitly per-package only); v1.5+.
- **Multi-trainer-per-session** (e.g., 2-trainer specialty class) — single trainer per row in v1.4; future array/junction-table extension.
- **No-show / late-cancel by CLIENT (with penalty)** — separate workflow; not on v1.4 roadmap.
- **Trainer-side compensation / payroll roll-up** — sums per-trainer session counts × rate → trainer pay. Not on v1.4 roadmap (B-06 cash-drawer also deferred).
- **Telegram bot `/sessions` self-history** — v1.5+; matches Q15 deferred PT-package bot self-service.
- **Server-side aggregate stats**: sessions-per-day, trainer-load reports — analytics endpoint; out of v1.4.
- **admin-web `/pt-sessions` UI / form / list page** — admin-web frozen-as-of-v1.3; production frontend ships in v2.0 by external design team (per 2026-05-15 frontend pivot).
- **`pt_session_recorded` payload hash** (parity with `refund_issued` SHA-256 payment_row_hash) — explicitly deferred (Phase 30 only payment-side hash in v1.4).
- **PT-session backdating beyond 7d for reception via owner override workflow** (operator clicks "request owner approval" inline) — out of v1.4; reception simply gets 422 today.
- **Reverse cancel** (un-cancel a session) — out of v1.4; cancel is one-way + emits one audit event; future audit-chain `pt_session_uncancelled` if needed.

</deferred>

---

*Phase: 34-pt-session-recording*
*Context gathered: 2026-05-16*
