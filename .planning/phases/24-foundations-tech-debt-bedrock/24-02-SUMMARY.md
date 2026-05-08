---
phase: 24-foundations-tech-debt-bedrock
plan: 02
subsystem: memberships
tags:
  - memberships
  - status-machine
  - alembic
  - check-constraint
  - infra-16
requires:
  - 0006_visits (Alembic predecessor)
  - app/core/exceptions.py:InvalidTransitionError (reused, not duplicated)
  - app/modules/memberships/service.py:_assert_can_cancel/_assert_can_expire (refactored to delegate)
provides:
  - apps/backend/alembic/versions/0007_status_taxonomy.py (CHECK swap; new chain head)
  - app/modules/memberships/constants.py:MEMBERSHIP_STATUS_TRANSITIONS (read-only declarative SM)
  - app/modules/memberships/service.py:_assert_can_transition (central guard, INFRA-16)
  - ORM CheckConstraint admits 'frozen' status (mirrors migration)
affects:
  - .planning/ROADMAP.md (v1.3 milestone block: Phase 25 SC, Phase 26 deps+SC, Phase 27 deps+SC)
  - .planning/milestones/v1.3-ROADMAP.md (Phase 25 SC, Phase 26 deps+SC, Phase 27 deps+SC, Build Order, Key Risks)
tech_stack:
  added: []
  patterns:
    - MappingProxyType for module-level immutable mappings
    - Postgres CHECK swap via op.execute (DROP + ADD; no in-place ALTER)
    - Central transition guard with delegating thin wrappers (preserves test imports)
key_files:
  created:
    - apps/backend/alembic/versions/0007_status_taxonomy.py
    - apps/backend/app/modules/memberships/constants.py
  modified:
    - apps/backend/app/modules/memberships/models.py
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/tests/unit/memberships/test_state_machine.py
    - .planning/ROADMAP.md
    - .planning/milestones/v1.3-ROADMAP.md
decisions:
  - D-24-01 (migration ownership — Phase 24 owns 0007_status_taxonomy; downstream cascade)
  - D-24-02 (Postgres DROP+ADD CHECK pattern; no in-place alter)
  - D-24-03 (constants.py + MappingProxyType + 4-key shape with frozen placeholder)
  - D-24-04 (central _assert_can_transition + reuse InvalidTransitionError)
  - D-24-05 (delegate refactor; 9-cell test shape preserved)
metrics:
  duration: ~10 min
  completed: 2026-05-08
  tasks: 2
  commits: 2
requirements_satisfied:
  - INFRA-16 (Phase 24 portion: status taxonomy + central transition guard)
---

# Phase 24 Plan 02: Migration 0007_status_taxonomy + MEMBERSHIP_STATUS_TRANSITIONS + central transition guard

INFRA-16 lands the Postgres CHECK swap (`'frozen'` admitted) plus a declarative `MEMBERSHIP_STATUS_TRANSITIONS` constant and a single central transition guard (`_assert_can_transition`) so all status-machine gates flow through one source of truth — unblocking Phase 25's freeze migration without a CHECK violation and without bundling status taxonomy into the freeze revision.

## What Shipped

### 1. New constants module: `app/modules/memberships/constants.py`

Read-only `MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]]` via `MappingProxyType`:

| source | allowed targets (Phase 24) | Phase 25 will add |
|---|---|---|
| `active` | `{expired, cancelled}` | `{frozen}` |
| `expired` | `∅` | (Phase 26 may extend for renewal) |
| `cancelled` | `∅` (terminal) | — |
| `frozen` | `∅` (placeholder) | `{active, cancelled}` |

`str` keys (not `MembershipStatus` enum) keep this importable from low-level modules without circular imports; the schema-layer enum and the constant share string values.

### 2. ORM CheckConstraint admits `'frozen'`

`app/modules/memberships/models.py` line 146:

```python
CheckConstraint(
    "status IN ('active', 'expired', 'cancelled', 'frozen')",
    name="status",  # NAMING_CONVENTION → ck_memberships_status
),
```

ORM and migration are now in lock-step.

### 3. Central transition guard `_assert_can_transition`

`app/modules/memberships/service.py`:

```python
def _assert_can_transition(membership: Membership, *, target: str) -> None:
    allowed = MEMBERSHIP_STATUS_TRANSITIONS.get(membership.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": target},
        )
```

Existing `_assert_can_cancel(m)` and `_assert_can_expire(m)` are now thin wrappers calling `_assert_can_transition(m, target=…)`. The 9-cell test imports `from app.modules.memberships.service import _assert_can_cancel, _assert_can_expire` — preserved verbatim.

`InvalidTransitionError` (already in `app/core/exceptions.py:158-172`) is reused — no parallel exception added.

### 4. Alembic migration `0007_status_taxonomy.py` (new chain head)

DDL only — no columns, no tables, no indexes:

```python
revision: str = "0007_status_taxonomy"
down_revision: str | None = "0006_visits"
```

`upgrade()` does `DROP CONSTRAINT ck_memberships_status` → `ADD CONSTRAINT ck_memberships_status CHECK (status IN ('active','expired','cancelled','frozen'))`. `downgrade()` reverses to the v1.2 three-status form. Postgres has no in-place CHECK alter, so DROP+ADD via `op.execute()` is the canonical form (D-24-02).

### 5. Test additions (3 new, 9-cell preserved)

`tests/unit/memberships/test_state_machine.py`:

- 9-cell parametrize matrix `test_state_machine_matrix` — unchanged regression contract.
- NEW `test_central_helper_matches_per_helper_guards` — central helper allows `active → cancelled|expired`, raises on terminal sources.
- NEW `test_membership_status_transitions_constant_is_immutable` — `isinstance(MEMBERSHIP_STATUS_TRANSITIONS, MappingProxyType)` + mutation raises `TypeError`.
- NEW `test_membership_status_transitions_phase24_contents` — exact 4-key shape with `frozen: ∅` placeholder.

### 6. ROADMAP cascade (both files)

Phase 24 reserves `0007_status_taxonomy`; downstream phases shift up by one.

**`.planning/milestones/v1.3-ROADMAP.md`:**
- Phase 25 SC #1: `0007_freeze.py` → `0008_freeze.py`
- Phase 26 deps: `0007` → `0008`
- Phase 26 SC #1: `0007` → `0008`
- Phase 27 deps: `0008 идёт после 0007` → `0009 идёт после 0008`
- Phase 27 SC #1: `0008_notifications.py` → `0009_notifications.py`
- Build Order: `share migration 0007` → `share migration 0008 (Phase 24 reserved 0007_status_taxonomy per D-24-01)`; `0008 must come after 0007` → `0009 must come after 0008`
- Key Risks: `Migration 0007` → `Migration 0008`

**`.planning/ROADMAP.md`** (v1.3 milestone block):
- Phase 25 SC #1: `0007_freeze.py` → `0008_freeze.py`
- Phase 26 deps: `0007` → `0008`
- Phase 26 SC #1: `0007` → `0008`
- Phase 27 deps: `0008 идёт после 0007` → `0009 идёт после 0008`
- Phase 27 SC #1: `0008_notifications.py` → `0009_notifications.py`
- **Preserved (DO-NOT-TOUCH):** Phase 24 plan-list line at `0007_status_taxonomy`.

## Verification Results

| Check | Result |
|---|---|
| `pytest tests/unit/memberships/test_state_machine.py` | 12/12 passed (9 matrix + 3 new) |
| `pytest tests/unit/` (full suite) | 301/301 passed |
| `pytest tests/integration/memberships/` | 2 ran + 102 skipped (no Postgres in env); zero failures |
| `ruff check` (modified files) | clean |
| `mypy --strict app/modules/memberships/` | clean (7 source files) |
| Alembic head detection | head == `0007_status_taxonomy` ✓ |
| ROADMAP cascade — `0007_freeze.py` count (both docs) | 0 ✓ |
| ROADMAP cascade — `0008_notifications.py` count | 0 ✓ |
| ROADMAP cascade — `0009_notifications.py` count | 1 ✓ |
| ROADMAP cascade — `share migration 0008` count | 1 ✓ |
| `0007_status_taxonomy` in ROADMAP.md (line 81 plan list preserved) | 1 ✓ |

Note: `alembic upgrade head` against a live DB and integration migration tests are unavailable in this environment (no Postgres). The migration is shape-verified against `0006_visits.py` analog and the alembic head check via `ScriptDirectory`.

## Deviations from Plan

**None — plan executed exactly as written.**

One minor inline cleanup during execution: a docstring line in `test_membership_status_transitions_phase24_contents` exceeded the 100-char width and was reformatted into a multi-line docstring. No semantic change. (Not tracked as a Rule deviation — this is an inline lint fix, no behavior change.)

## Authentication Gates

None — backend-only refactor; no auth surface change.

## Threat Flags

None — Phase 24 introduces no new request entry points, no new auth surface, and no new external inputs. The plan's `<threat_model>` is fully addressed:
- T-24-02-01 (status tampering) — mitigated by extended Postgres CHECK.
- T-24-02-02 (constant runtime mutation) — mitigated by `MappingProxyType` + immutability test.
- T-24-02-04 (migration regression) — mitigated by reversible downgrade.

## Known Stubs

`MEMBERSHIP_STATUS_TRANSITIONS["frozen"] = frozenset()` is an **intentional Phase-24 placeholder**. Phase 25 will populate `frozen → {active, cancelled}` and `active → {…, frozen}` as part of MEM-FRZ-01..07. Documented in the constants.py module docstring and in D-24-03. Not a true stub — the empty edge set is the correct Phase-24 contract (no freeze transitions exist yet at this point in time).

## TDD Gate Compliance

This plan is `type: execute` (not `type: tdd`), but Task 1 used `tdd="true"` task-level flag. Per the per-task TDD flow:

- RED: tests added first (failed with `ImportError` on `_assert_can_transition`) — verified.
- GREEN: implementation added; all 12 tests pass.
- REFACTOR: not needed; minimal-implementation form was already clean.

Note: Task 1's RED+GREEN were combined into a single `feat(24-02)` commit (rather than separate `test:` then `feat:` commits) because the new tests were appended to an existing test file that also covers the still-passing 9-cell matrix — splitting the file modification across two commits would have created a transient state where the test file referenced symbols not yet imported in the existing 9-cell tests. The unified commit preserves correctness; tdd gate intent (write test first, then implementation) was followed in the working tree even though committed atomically.

## Self-Check

- [x] FOUND: apps/backend/alembic/versions/0007_status_taxonomy.py
- [x] FOUND: apps/backend/app/modules/memberships/constants.py
- [x] FOUND: commit aeb9da2 (Task 1)
- [x] FOUND: commit 286d3c8 (Task 2)
- [x] ORM CheckConstraint string updated (verified by grep)
- [x] Service refactor: `_assert_can_transition` exists; wrappers delegate (verified by grep)
- [x] Both ROADMAP cascades applied with zero stale literals
- [x] Phase 24 plan-list line at ROADMAP.md:81 preserved at `0007_status_taxonomy`

## Self-Check: PASSED
