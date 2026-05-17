# Phase 37: Foundations Bedrock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 37-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 37-foundations-bedrock
**Mode:** `--auto` (Claude auto-selected the recommended default for every residual gray area; no interactive AskUserQuestion calls were made)
**Areas discussed:** RBAC Action enum extension, Resource enum naming, FSM guard placement, audit payload shape for `booking_id`, Protocol slot defensive wiring scope, import-linter contract shape, DEBT-06 scope boundary, frontend parity edit scope, audit payload file location

---

## RBAC: Action enum extension

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `Action.CREATE` for both slot publish and booking create | Resource disambiguates; preserves frontend `can.ts` parity; no enum churn | ✓ |
| Add new `Action.BOOK` member | Semantically distinct from `CREATE`; requires frontend mirror; breaks TEST-06 unless both stacks updated atomically | |

**Auto-selected rationale:** Mirrors existing `(CREATE, MEMBERSHIPS)` vs `(CREATE, MEMBERSHIP_PLANS)` precedent. Smaller blast radius for the locked enum.

---

## Resource enum value casing

| Option | Description | Selected |
|--------|-------------|----------|
| `SCHEDULE_SLOTS = "schedule-slots"`, `BOOKINGS = "bookings"` | Kebab on wire matches MEMBERSHIP_PLANS / PT_PACKAGE_PLANS / PT_PACKAGES / PT_SESSIONS precedent | ✓ |
| `SCHEDULE_SLOTS = "schedule_slots"`, `BOOKINGS = "bookings"` | Snake on wire diverges from the established kebab convention | |
| Rename existing `Resource.SCHEDULE` instead of adding `SCHEDULE_SLOTS` | Would break frontend left-nav and route guards | |

**Auto-selected rationale:** Kebab is the established wire convention. Existing `Resource.SCHEDULE = "schedule"` is preserved untouched.

---

## `Action.LIST` introduction

| Option | Description | Selected |
|--------|-------------|----------|
| Add `Action.LIST = "list"` (D-37-03a) | Semantic separation; required by REQUIREMENTS.md INFRA-27's `(LIST, *)` pairs; small frontend mirror | ✓ |
| Merge `LIST` semantics into `VIEW` | Smaller change but REQUIREMENTS.md explicitly enumerates `(LIST, SCHEDULE_SLOTS)` etc. — would require requirement rewrite | |

**Auto-selected rationale:** Stick with REQUIREMENTS.md as written; add the enum member.

---

## FSM `_assert_can_transition` guard placement

| Option | Description | Selected |
|--------|-------------|----------|
| Per-module (in each module's `constants.py`) | Mirrors v1.3 memberships + v1.4 pt_packages precedent; `app/core` stays cross-cutting only | ✓ |
| Central helper in `app/core/fsm.py` | Would create cross-module import surface that `.importlinter` discourages; no DRY win at 2-module scale | |

**Auto-selected rationale:** Established precedent + import-linter discipline.

---

## `pt_session_recorded` payload extension shape

| Option | Description | Selected |
|--------|-------------|----------|
| `booking_id: str \| None = None` (Optional, default None) | Backward-compat; no payload version bump; matches C-06 explicit choice | ✓ |
| `booking_id: str` (required) | Would break every existing v1.4 emit callsite | |
| New `pt_session_recorded_v2` event | Violates C-06 ("completion is signalled via the existing event, not a new one") | |

**Auto-selected rationale:** C-06 and INFRA-25 already constrain to optional extension.

---

## Protocol slot defensive double-wiring scope

| Option | Description | Selected |
|--------|-------------|----------|
| `SlotByIdResolver` + `register_active_pt_package_resolver` defensively wired in `telegram_bot.py:main()`; `BookingSlotRestorer` and `BookingCompleter` in `app/main.py` only | Bot `/book` (Phase 40 BOT-02) consumes slot lookup + PT-package check; the other 2 slots are consumed only inside HTTP-path services. REG-29-03 lesson applied selectively. | ✓ |
| Wire all 3 new slots in both `app/main.py` and `telegram_bot.py:main()` | Defensive overhead without correctness benefit for slots the bot never consumes | |
| Wire all in `app/main.py` only; skip bot | Loses REG-29-03 protection for slots the bot DOES consume | |

**Auto-selected rationale:** Targeted defensive wiring per actual consumption surface.

---

## `.importlinter` contract shape

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing `modules-independent` contract's `modules` list | Single contract enforces all-pairs independence; pattern continuity | ✓ |
| Define new contract `schedule-bookings-independent` | Duplicates enforcement without adding any check the existing contract doesn't already cover | |

**Auto-selected rationale:** Importlinter contracts already cover all pairs in their `modules` list.

---

## DEFER-36-04-A pytest sweep scope

| Option | Description | Selected |
|--------|-------------|----------|
| Defer the 11 remaining failures to Phase 38 pre-flight | Keeps bedrock phase pure (contracts/lock-in only); STATE.md already pins this defer path | ✓ |
| Bundle the sweep into Phase 37 plan 37-NN | Dilutes the unit-of-change in a bedrock phase; tests being fixed touch surfaces (`pt_sessions`, `pt_packages`) being modified in Phase 38 anyway | |

**Auto-selected rationale:** Bedrock phases should ship one kind of change. Sweep belongs where the test surface is also being modified.

---

## Frontend (admin-web) parity edit scope inside Phase 37

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic mirror of `Resource` + `OWNER_ONLY` + `Action.LIST` in `apps/admin-web/src/shared/session/{registry,can}.ts` only (~10 LOC) | Required for TEST-06 byte-parity test to stay green; does not violate the v2.0 "design team owns production frontends" pivot — RBAC is shared infrastructure | ✓ |
| Defer frontend mirror to a separate quick task | Would leave CI red between backend commit and frontend commit | |

**Auto-selected rationale:** RBAC parity test gates CI; the mirror must land atomically with the backend change.

---

## Audit payload schemas file location

| Option | Description | Selected |
|--------|-------------|----------|
| All 5 new schemas in existing `app/core/audit_payloads.py` (currently 346 LOC) | Canonical location; existing registry consumes from here; emit-side plumbing unchanged | ✓ |
| Split into per-module `app/modules/{schedule,bookings}/audit_payloads.py` | Would require core-to-modules import or core registry to dynamically discover schemas | |

**Auto-selected rationale:** Single canonical home for all payloads keeps the emit-time validation lookup O(1) and avoids core↔modules coupling.

---

## Claude's Discretion

None — `--auto` mode picked every default with rationale logged in CONTEXT.md `<decisions>`. The user can review CONTEXT.md and override any `D-37-NN` before `gsd-plan-phase 37` consumes it.

## Deferred Ideas

See CONTEXT.md `<deferred>` section — comprehensive list grouped by destination phase (38 / 38 pre-flight / 39 / 40 / future milestones). Notable items:

- All Alembic migrations (0016–0020) → Phase 38–39
- DEFER-36-04-A pytest sweep (11 failures) → Phase 38 pre-flight
- All routers, services, endpoints → Phase 38+
- Race tests including `BOOK-TEST-01` → Phase 38
- DM templates + cron jobs → Phase 39
- Telegram `/book` handler + OpenAPI regen → Phase 40
- Group classes / online payment / trainer DMs / configurable buffer / iCal export → future milestones
