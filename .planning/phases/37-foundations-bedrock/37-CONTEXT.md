# Phase 37: Foundations Bedrock - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning
**Mode:** `--auto` (Claude auto-selected recommended defaults for all residual gray areas)

<domain>
## Phase Boundary

Phase 37 is the **bedrock / contracts lock phase** for v1.5 Schedule + Bookings. No business logic, no endpoints, no migrations on the new tables. Deliverable scope is exactly:

1. Extend `LOCKED_AUDIT_EVENTS` frozenset 51 → 56 with the 5 new (event, resource_type) tuples and **pre-register** their Pydantic v2 payload schemas in `app/core/audit_payloads.py` (INFRA-24/25).
2. Extend `Resource` + `OWNER_ONLY` for the two new resources, keeping byte-for-byte parity with frontend `apps/admin-web/src/shared/session/can.ts` (INFRA-26/27).
3. Extend `.importlinter` so `app.modules.schedule` and `app.modules.bookings` are mutually independent and independent of every other module (INFRA-28).
4. Extend SVC001 AST commit-gate walker scope (INFRA-29).
5. Lock the two FSM transition constants (`BOOKING_STATUS_TRANSITIONS`, `SLOT_STATUS_TRANSITIONS`) + per-module `_assert_can_transition` guards (INFRA-30/31).
6. Add the 3 new Protocol slot types (`SlotByIdResolver`, `BookingSlotRestorer`, `BookingCompleter`) + register/get accessors in `app/core/dependencies.py` (INFRA-32).
7. Wire all 3 new Protocol slots in `app/main.py:create_app()` and defensively double-wire `SlotByIdResolver` + the missing `register_active_pt_package_resolver` in `app/workers/telegram_bot.py:main()` (INFRA-33, DEBT-06).

**Explicitly out of scope for Phase 37** (lands in Phase 38):
- Alembic 0016 (`trainer_availability_slots`), 0017 (`bookings`), 0018 (`pt_packages.trainer_id`), 0019 (`pt_sessions.booking_id`)
- Any router, service, or endpoint code for slots/bookings
- The 11 remaining DEFER-36-04-A pytest failures (see Deferred Ideas)

</domain>

<decisions>
## Implementation Decisions

All C-01..C-15 milestone-level decisions are locked in `.planning/REQUIREMENTS.md`
and are NOT re-decided here. The decisions below are Phase 37 implementation-level
choices made during this auto-discuss pass.

### D-37-01 — RBAC: Action enum stays at 7 values (no new `Action.BOOK`)
INFRA-26 left this as "decide at plan time". Decision: **reuse existing `Action.CREATE`** for both
"publish slot" (operator action on `SCHEDULE_SLOTS`) and "create booking" (action on `BOOKINGS`).

**Why:**
- Semantic disambiguation is already carried by `Resource` (mirrors the existing
  `(CREATE, MEMBERSHIPS)` vs `(CREATE, MEMBERSHIP_PLANS)` precedent — same `Action.CREATE`,
  different `Resource`).
- Adding `Action.BOOK` would diverge from the frontend `can.ts` `Action` union and break
  the Phase 6 TEST-06 byte-for-byte parity test (RBAC contract is mirrored by-set, and
  the frontend has no `BOOK` action today).
- Fewer new enum values = smaller blast radius for the locked frozenset count assert.

**How to apply:** Phase 38 plan must use `(Action.CREATE, Resource.SCHEDULE_SLOTS)` for
slot publish and `(Action.CREATE, Resource.BOOKINGS)` for booking create. No new
`Action` member is added in Phase 37.

### D-37-02 — Resource enum values: kebab on wire
New `Resource` members land as:
- `SCHEDULE_SLOTS = "schedule-slots"` (member-name uses underscore; wire value is kebab —
  mirrors `MEMBERSHIP_PLANS = "membership-plans"`, `PT_PACKAGE_PLANS = "pt-package-plans"`,
  `PT_PACKAGES = "pt-packages"`, `PT_SESSIONS = "pt-sessions"`).
- `BOOKINGS = "bookings"` (single word — mirrors `MEMBERSHIPS = "memberships"`,
  `CLIENTS = "clients"`, `VISITS = "visits"`).

**Important:** The existing `Resource.SCHEDULE = "schedule"` (used by the frontend
left-nav at `/schedule`) is **NOT renamed**. It coexists with the new
`Resource.SCHEDULE_SLOTS` which scopes the API resource. Frontend `can.ts` must add
both values in the same Phase 37 atomic change to preserve TEST-06 parity. Phase 37
plan must include a single small `apps/admin-web/src/shared/session/{registry,can}.ts`
patch alongside the backend change (no business-logic UI work — purely the type+OWNER_ONLY
mirror).

### D-37-03 — `OWNER_ONLY` deltas (10 entries added, +0 removed; new count 25 → 35)
Per INFRA-27, the additions are:
- Owner-only: `(EDIT, SCHEDULE_SLOTS)`, `(DELETE, SCHEDULE_SLOTS)`, `(CANCEL, SCHEDULE_SLOTS)`, `(CREATE, SCHEDULE_SLOTS)` — slot publication is owner-only in v1.5 (no trainer self-service per anti-feature list).
- Reception retains (NOT listed in `OWNER_ONLY`): `(VIEW, SCHEDULE_SLOTS)`, `(LIST, SCHEDULE_SLOTS)`, `(CREATE, BOOKINGS)`, `(CANCEL, BOOKINGS)`, `(VIEW, BOOKINGS)`, `(LIST, BOOKINGS)`.

**Pre-flight note for the planner:** `Action.LIST` is referenced by REQUIREMENTS.md
INFRA-27 but does NOT currently exist in `apps/backend/app/core/permissions.py:20-27`
(today's enum: `VIEW, CREATE, EDIT, DELETE, REFUND, CANCEL, CHECK_IN`). The plan must:
(a) add `Action.LIST = "list"` to the backend enum AND frontend `Action` union in the
same atomic Phase 37 patch (parity-preserving); or (b) merge `LIST` semantics into
`VIEW` and drop the `(LIST, *)` pairs from the OWNER_ONLY plan. **Default
recommendation:** add `Action.LIST` — endpoint listings (e.g., owner-only `GET /payments`
already exists today and would benefit from semantic separation in future phases).
Locked here as **D-37-03a: add `Action.LIST` enum member, byte-parity mirror in
frontend `can.ts` in the same Phase 37 plan**.

### D-37-04 — FSM guard placement: per-module, not central
`_assert_can_transition` is implemented **per-module** in:
- `app/modules/bookings/constants.py` (alongside `BOOKING_STATUS_TRANSITIONS`)
- `app/modules/schedule/constants.py` (alongside `SLOT_STATUS_TRANSITIONS`)

**Why:** mirrors v1.3 `app/modules/memberships/constants.py:MEMBERSHIP_STATUS_TRANSITIONS`
+ v1.4 `app/modules/pt_packages/constants.py:PT_PACKAGE_STATUS_TRANSITIONS` precedent.
`app/core/` stays reserved for cross-cutting primitives that multiple modules import.
A factored generic transition helper would create cross-module coupling that
`.importlinter` already forbids.

**How to apply:** Phase 38 service code calls
`from app.modules.bookings.constants import _assert_can_transition` (or the local
guard helper named per the v1.3/v1.4 precedent). No central import.

### D-37-05 — `pt_session_recorded` payload extension: optional `booking_id`
INFRA-25 and C-06 require extending the existing `pt_session_recorded` payload schema
(not introducing a new event) to carry the optional parent-booking reference.

Decision: `booking_id: str | None = None` (Optional, default `None`).

**Why:**
- Backward-compatible: every existing emit callsite from v1.4 (Phase 34
  `pt_sessions.service.record_pt_session`) continues to validate without modification.
- C-06 explicitly states `booking_completed` is **NOT** a separate event — completion
  is signalled via the existing `pt_session_recorded` event carrying `booking_id`.
- All UUIDs serialise as `str(uuid)` per REG-36-03 lesson (P13).
- `extra='forbid'` on the schema continues to reject unknown payload keys.

**How to apply:** Phase 37 plan updates `app/core/audit_payloads.py` to extend the
existing `PtSessionRecordedPayload` model with the optional field. Existing emit
callsites are untouched. Phase 38's PT-package integration (PKG-05) is the first
producer that sets `booking_id` to a non-None value.

### D-37-06 — Protocol slot defensive double-wiring scope
Per INFRA-33 and the REG-29-03 lesson, the 3 new Protocol slots + the missing v1.4
slot wire as follows:

| Slot | `app/main.py:create_app()` | `app/workers/telegram_bot.py:main()` |
|---|---|---|
| `SlotByIdResolver` | wired | wired (defensive — bot `/book` consumes it in Phase 40 BOT-02) |
| `BookingSlotRestorer` | wired | NOT wired (only `bookings.service.cancel_booking` consumes it) |
| `BookingCompleter` | wired | NOT wired (only `pt_sessions.service.record_pt_session` consumes it) |
| `register_active_pt_package_resolver` (DEBT-06 — pre-existing slot, missing from bot) | already wired | **add to bot** (this is the DEBT-06 fix) |
| Existing slots already wired in bot from v1.2/v1.3: `register_user_loader`, `register_client_by_telegram_resolver`, `register_active_membership_resolver`, `register_trainer_by_id_resolver` | unchanged | unchanged |

**Why:** REG-29-03 ("bot path silently mis-fires when only the API path wires a slot
the bot consumes"). The bot `/book` flow consumes (a) slot lookup for callback validation
and (b) active-PT-package check; both must be defensively double-wired. `BookingSlotRestorer`
and `BookingCompleter` are exclusively consumed inside service code reached only via the
HTTP API path — wiring them in the bot would be defensive overhead without correctness benefit.

**Parity test (INFRA-33):** the test asserts the set of slot-registration call-names
made by `create_app()` is a **superset** of those made by `telegram_bot.py:main()`,
and that for every slot consumed by a bot handler the bot call list contains its
register. Phase 37 ships the test fixture; subsequent phases never break it.

### D-37-07 — `.importlinter` contract shape: extend existing
INFRA-28 is implemented by adding `app.modules.schedule` and `app.modules.bookings` to
the **existing** `modules-independent` contract's `modules` list — one contract,
all modules pairwise independent.

**Why:** today's contract already enumerates `memberships`, `visits`, `trainers`,
`payments`, `pt_packages`, `pt_sessions`. A second contract would duplicate enforcement
without buying anything (importlinter independence checks every pair).

**How to apply:** edit `.importlinter` (root) to append both module names. Add a
negative-test fixture import (a one-line bad import in a `_negative_fixture.py`)
exercising the contract under CI — pattern mirrors the v1.4 INFRA-21 negative fixture
for SVC001. The fixture file is **never imported by production code** (guarded by
`if False:` or commented out — same trick as frontend ESLint negative fixtures in
`apps/admin-web/scripts/assert-eslint-fixtures.mjs`).

### D-37-08 — Frontend (admin-web) parity scope inside Phase 37
This phase touches `apps/admin-web/src/shared/session/{registry.ts, can.ts}` to mirror
the new `Resource` values and `OWNER_ONLY` deltas (and the new `Action.LIST` per D-37-03a).
**No** route additions, **no** new UI components, **no** mock service stubs.

**Why:** TEST-06 backend↔frontend RBAC parity test would FAIL the moment the backend
ships D-37-02/03 unless the frontend updates land in the same atomic phase. The change
is purely a type-level mirror — `~10 LOC across 2 files`. This does not violate the
v2.0 "design team owns production frontends" rule from the 2026-05-15 pivot: `apps/admin-web`
remains frozen at v1.3 baseline for product surface, but the shared RBAC contract is
infrastructure shared with backend and MUST stay in lock-step.

### D-37-09 — Audit payload schemas: file location
The 5 new payload schemas (`SlotPublishedPayload`, `SlotCancelledPayload`,
`BookingCreatedPayload`, `BookingCancelledPayload`, `BookingNoShowPayload`) all land in
`apps/backend/app/core/audit_payloads.py` — the existing canonical home (346 LOC today).
Registry entry per event added to the existing payload-schema-by-event-name registry
(present in `audit_payloads.py`; emit-time validation hook in `app/core/audit.py:emit()`
already consumes it — no new emit-side plumbing needed).

**UUID handling:** every UUID field in every new payload schema is typed `str`
(not `uuid.UUID`) per P13/REG-36-03. Serialiser callsite uses `str(uuid)` — never
`json.dumps(uuid_obj)`.

### Folded Todos
None — `gsd-sdk query todo.match-phase 37` returned zero matches.

### Claude's Discretion
None — `--auto` mode picked every default with rationale logged above. The user can
audit and override any D-37-NN before `gsd-plan-phase 37` consumes this file.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Milestone Decisions & Requirements (PRIMARY)
- `.planning/REQUIREMENTS.md` §C-01..C-15 — locked milestone bedrock decisions (the source of truth for v1.5 architecture)
- `.planning/REQUIREMENTS.md` §INFRA-24..INFRA-33 + DEBT-06 — Phase 37 requirements (11 items)
- `.planning/PROJECT.md` "Current Milestone: v1.5" + Key Decisions table — accumulated business-domain context
- `.planning/STATE.md` "Critical pre-emptions for Phase 37 (from PITFALLS.md)" — P1, P3, P6, P8, P13 — pre-emption checklist

### Research Outputs (already produced for v1.5)
- `.planning/research/SUMMARY.md` — 4-dimension research synthesis
- `.planning/research/PITFALLS.md` §Pitfalls 1, 2, 3, 6, 8, 13 — race, overlap, timestamptz, FSM, payload-UUID class-of-omission
- `.planning/research/ARCHITECTURE.md` — module-split + Protocol slot architecture
- `.planning/research/FEATURES.md` — feature inventory + scope guard
- `.planning/research/STACK.md` — tech stack constraints

### Roadmap & Milestone Plans
- `.planning/ROADMAP.md` §Phase 37 — goal + 5 success criteria
- `.planning/milestones/v1.4-ROADMAP.md` Phase 30 — bedrock-phase precedent (INFRA-17..23 + DEBT-05)
- `.planning/milestones/v1.3-ROADMAP.md` Phase 24 — earlier bedrock-phase precedent (INFRA-15/16 + DEBT-01/02/03)

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — modular-monolith conventions
- `.planning/codebase/STRUCTURE.md` — directory + module layout
- `.planning/codebase/STACK.md` — Python/FastAPI/SQLAlchemy stack
- `.planning/codebase/CONVENTIONS.md` — naming, ruff/mypy rules, commit conventions
- `.planning/codebase/CONCERNS.md` — known cross-cutting concerns
- `.planning/codebase/TESTING.md` — pytest + httpx ASGITransport conventions
- `.planning/codebase/INTEGRATIONS.md` — external boundaries

### Source files Phase 37 will modify (locked targets)
- `apps/backend/app/core/audit.py` — extend `LOCKED_AUDIT_EVENTS` frozenset (currently 269 LOC)
- `apps/backend/app/core/audit_payloads.py` — 5 new schemas + extend `PtSessionRecordedPayload` (currently 346 LOC)
- `apps/backend/app/core/permissions.py` — extend `Resource`, `Action` (add `LIST`), `OWNER_ONLY` (currently ~107 LOC)
- `apps/backend/app/core/dependencies.py` — 3 new Protocol classes + 3 register/get pairs (currently ~250+ LOC; pattern reference: lines 1-200 read)
- `apps/backend/app/main.py` — wire 3 new Protocol slots in `create_app()` in deterministic order BEFORE routers mount
- `apps/backend/app/workers/telegram_bot.py` — defensive register of `SlotByIdResolver` + missing `register_active_pt_package_resolver` (DEBT-06)
- `apps/backend/app/modules/schedule/constants.py` — NEW file: `SLOT_STATUS_TRANSITIONS` + `_assert_can_transition`
- `apps/backend/app/modules/bookings/constants.py` — NEW file: `BOOKING_STATUS_TRANSITIONS` + `_assert_can_transition`
- `.importlinter` (repo root) — append `app.modules.schedule` and `app.modules.bookings` to `modules-independent` contract
- `apps/backend/scripts/svc001_check.py` (or wherever SVC001 AST walker lives) — extend file-scope list to include new module service files (pre-creation placeholder is acceptable)
- `apps/admin-web/src/shared/session/registry.ts` — add Resource values
- `apps/admin-web/src/shared/session/can.ts` — add Action.LIST + OWNER_ONLY deltas (TEST-06 parity)

### Tests to add/extend in Phase 37
- `apps/backend/tests/test_audit_taxonomy.py` (existing) — count assert 51 → 56; LOCKED_AUDIT_EVENTS membership for the 5 new tuples
- `apps/backend/tests/test_audit_payloads.py` (existing) — schema validation for the 5 new payloads + extended `pt_session_recorded`
- `apps/backend/tests/test_rbac_parity.py` (existing — TEST-06) — picks up the new OWNER_ONLY pairs once frontend mirror lands
- `apps/backend/tests/test_dependencies.py` (existing) — register/get round-trip for 3 new slots
- `apps/backend/tests/test_importlinter.py` (existing) — `modules-independent` contract passes with new modules; negative fixture triggers failure
- `apps/backend/tests/test_app_wiring.py` (existing or new) — startup integration test asserting all 3 new Protocol slots are non-None after `create_app()`; parity-test asserting bot-main wires `SlotByIdResolver` and `register_active_pt_package_resolver` (DEBT-06)
- `apps/backend/tests/test_booking_fsm.py` (NEW) — `BOOKING_STATUS_TRANSITIONS` enumerates exactly 3 legal transitions; `_assert_can_transition` raises on illegal
- `apps/backend/tests/test_slot_fsm.py` (NEW) — `SLOT_STATUS_TRANSITIONS` enumerates exactly 3 legal transitions; `_assert_can_transition` raises on illegal

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`LOCKED_AUDIT_EVENTS` frozenset** (`apps/backend/app/core/audit.py:121`) — append-only pattern. Add 5 tuples; the `emit()` validation hook (`audit.py:247`) already enforces membership. No code-shape change needed beyond the literal frozenset extension.
- **`audit_payloads.py` Pydantic v2 schemas + registry** — established pattern for `extra='forbid'` + str-UUID + per-event registry entry. Mirror the existing `PaymentRecordedPayload` / `RefundIssuedPayload` shape from v1.4.
- **`OWNER_ONLY` frozenset** (`apps/backend/app/core/permissions.py:55-94`) — append-only with inline `# Phase NN INFRA-NN` comment per delta. Mirror Phase 30 INFRA-19 comment style.
- **Protocol slot pattern in `app/core/dependencies.py`** — 6 existing slots (UserLoader, ActiveMembershipResolver, ActivePtPackageResolver, ClientByTelegramResolver, TrainerByIdResolver, payment_recorder/refunder) cover both "silent-None" semantics (resolvers) and "defensive-raise" semantics (recorder/refunder). For Phase 37: `SlotByIdResolver` uses silent-None (like ActiveMembership); `BookingSlotRestorer` and `BookingCompleter` use silent-None too (the consuming service treats "no resolver registered" as test-stub scenario and skips the side-effect — same logic as v1.4 `ActivePtPackageResolver` at line 117-129 inspection). Documented decision: silent-None for all 3 new slots.
- **Per-module `*_STATUS_TRANSITIONS` constants** — mirror `app/modules/memberships/constants.py:MEMBERSHIP_STATUS_TRANSITIONS` (v1.2) and `app/modules/pt_packages/constants.py:PT_PACKAGE_STATUS_TRANSITIONS` (v1.4). Literal `dict[str, frozenset[str]]` keyed by current status → set of legal next statuses. `_assert_can_transition(current, next)` raises 409 `invalid_transition` with structured error (consistent with v1.2/v1.4 surface).

### Established Patterns
- **Frontend↔backend RBAC byte-parity (TEST-06)** — every change to `permissions.py` Resource/Action/OWNER_ONLY MUST land in the same plan as the `apps/admin-web/src/shared/session/{registry.ts, can.ts}` mirror. CI will go red otherwise. This is the only acceptable cross-stack edit inside Phase 37.
- **Composition-root wiring discipline** — `app/main.py:create_app()` calls every `register_*` BEFORE FastAPI router includes. `app/workers/telegram_bot.py:main()` mirrors the subset of slots its handlers consume. Both must be edited in the same atomic plan to preserve the INFRA-33 parity test.
- **SVC001 AST commit-gate** (v1.4 INFRA-21 / `apps/backend/scripts/svc001_check.py` or equivalent) — extend file-scope list to include `app/modules/schedule/service.py` and `app/modules/bookings/service.py` (the files don't exist yet — pattern-walker accepts the path globs without erroring on missing files; verify on running the test).
- **`extra='forbid'` Pydantic v2 audit payloads** — strict schemas reject payload-key drift at emit time. UUID-as-str discipline (P13 / REG-36-03 lesson) is enforced uniformly — every UUID-typed field is `str`, every callsite uses `str(uuid)`.

### Integration Points
- **`app/main.py:create_app()`** — single chokepoint for Protocol slot wiring. Existing slot order (from research): `register_user_loader → register_active_membership_resolver → register_active_pt_package_resolver → register_client_by_telegram_resolver → register_trainer_by_id_resolver → register_payment_recorder → register_payment_refunder`. Append the 3 new registers at the end of the registration block, BEFORE the router include line. Deterministic order matters for the INFRA-33 startup integration test snapshot.
- **`app/workers/telegram_bot.py:main()`** — second chokepoint. Today registers a subset of slots (user loader + client_by_telegram + active_membership + trainer_by_id, per the v1.3 + v1.4 research output). DEBT-06 fix appends `register_active_pt_package_resolver` (already exists from v1.4 — was missed in bot). Phase 37 ALSO appends `register_slot_by_id_resolver` (new in Phase 37) for the bot's Phase 40 `/book` consumption path.
- **`.importlinter`** (repo root) — extending the `modules-independent` contract is the only enforcement mechanism that prevents `bookings` from accidentally importing `schedule` (or vice versa) during Phase 38. Both modules MUST go through Protocol slots wired in the composition root.

</code_context>

<specifics>
## Specific Ideas

- **Atomic Phase 37 plan structure recommendation for `gsd-plan-phase`:**
  A natural plan breakdown is 4–5 small atomic plans, each commit-sized:
  1. **37-01 audit-taxonomy** — extend `LOCKED_AUDIT_EVENTS` (51→56) + 5 new Pydantic payload schemas + `PtSessionRecordedPayload.booking_id` extension + `test_audit_taxonomy.py` count assert refresh + `test_audit_payloads.py` schema tests (INFRA-24/25).
  2. **37-02 rbac-extension** — `Resource` SCHEDULE_SLOTS/BOOKINGS + `Action.LIST` + `OWNER_ONLY` deltas + frontend `registry.ts`/`can.ts` byte-parity mirror + TEST-06 refresh (INFRA-26/27 + D-37-03a).
  3. **37-03 fsm-constants** — create `app/modules/schedule/constants.py` + `app/modules/bookings/constants.py` with `*_STATUS_TRANSITIONS` + `_assert_can_transition` + `test_booking_fsm.py` + `test_slot_fsm.py` (INFRA-30/31).
  4. **37-04 protocol-slots-and-wiring** — 3 new Protocol classes + register/get pairs in `app/core/dependencies.py` + `app/main.py` wiring + `app/workers/telegram_bot.py` defensive double-wiring (SlotByIdResolver + DEBT-06 active_pt_package_resolver) + startup integration test + bot↔main parity test (INFRA-32/33 + DEBT-06).
  5. **37-05 import-linter-and-svc001** — extend `.importlinter` `modules-independent` contract + add negative fixture + extend SVC001 AST walker scope (INFRA-28/29).

  Plans 37-01 / 37-02 / 37-03 / 37-05 are mutually independent (parallel-eligible).
  Plan 37-04 depends on 37-03 (FSM constants) only indirectly (via service code that
  doesn't exist yet in Phase 37) and on 37-01 (audit) only at runtime — for plan ordering
  purposes 37-04 can run in parallel with 37-01..37-03, but commit order matters for
  test stability. **Recommendation: serial commits in numeric order; parallel coding allowed.**

- **No 0016 Alembic migration in Phase 37.** Per v1.4 Phase 30 precedent (foundations + tech-debt, zero migrations), Phase 37 ships zero schema changes. Tables `trainer_availability_slots` (0016) and `bookings` (0017) land in Phase 38, alongside the modifications to `pt_packages` (0018) and `pt_sessions` (0019).

- **Deterministic registration order in `create_app()` is a snapshot test.** When extending the wiring block, append at the end; don't insert in the middle. The startup integration test will diff against the captured snapshot of `_registered_slot_names`.

</specifics>

<deferred>
## Deferred Ideas

### To Phase 38 (Schedule Module + Booking Core)
- All Alembic migrations (0016–0019)
- All routers, services, endpoints, schemas (request/response Pydantic models)
- All race tests including `BOOK-TEST-01` (real Postgres concurrent same-slot booking)
- Slot-overlap, slot-too-close, slot-in-past, trainer-inactive guards (SLOT-03..06)
- Booking cancellation window logic (BOOK-06) and the 24h Europe/Moscow math

### To Phase 38 pre-flight (acknowledged in STATE.md)
- **DEFER-36-04-A pytest sweep** — 11 remaining failures (7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug). **Explicitly NOT in Phase 37 scope** per D-37-NN auto-decision: bedrock phase stays focused on contracts; sweep happens in Phase 38 pre-flight where the test surface area is being touched anyway. (User can override this defer if cheap sweep cycles open up during 37 execution — flag in Phase 37 verification step if appropriate.)

### To Phase 39 (Notifications + Cron)
- All DM templates (`BOOKING_CONFIRMED_DM`, etc.)
- ARQ cron jobs (`mark_no_show_bookings`, `send_booking_reminders`)
- `booking_notifications` table + Alembic 0020
- One-shot operator runners (`run_no_show_cron_once.py`, `run_booking_reminders_once.py`)

### To Phase 40 (Telegram /book + OpenAPI + Verification)
- `/book` command handler + InlineKeyboard flow + anti-oracle DM
- `HandlerContext.bookings_service` extension
- OpenAPI byte-stable regen + `AssertNonNever` forward-guard extension
- 6 operator curl scenarios + 2 bot scenarios + ARQ cron one-shot scenarios

### To Future Milestones
- Group classes (capacity > 1) — TBD
- Online payment at booking time — v1.7 ЮKassa
- Trainer Telegram DMs — v1.6
- Configurable slot buffer — v1.8 Reports
- iCal `.ics` export — v1.8 Reports
- Manual `POST /bookings/{id}/no_show` endpoint — v1.5.1 if real need
- DEFER-36-04-B (ruff format 123 files) — v1.9 doc-debt sweep

### Reviewed Todos (not folded)
None — no todos matched Phase 37.

</deferred>

---

*Phase: 37-foundations-bedrock*
*Context gathered: 2026-05-17*
*Mode: --auto (single-pass; downstream agents may override any D-37-NN before plan-phase)*
