# Phase 24: Foundations & Tech-Debt Bedrock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 24-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 24-foundations-tech-debt-bedrock
**Mode:** `--auto` (single-pass; Claude selected the recommended option for every gray area without interactive prompts)
**Areas discussed:** Migration numbering, Status transitions constant, Resolver `today` injection, Query param shape, SVC001 auth/service walker scope, Audit frozenset layout

---

## Migration numbering & ownership

| Option | Description | Selected |
|--------|-------------|----------|
| A | Phase 24 owns its own `0007_status_taxonomy.py` (CHECK extension only); Phase 25/26 shift to `0008_*` | ✓ |
| B | Fold INFRA-16 CHECK extension into Phase 25's `0007_freeze.py` | |
| C | Skip migration entirely; enforce CHECK only at app layer until Phase 25 | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** Phase 24 must ship as a self-contained green build; bundling INFRA-16 into Phase 25's freeze migration couples two phase boundaries. The milestone roadmap note "25 and 26 share migration `0007`" predated the INFRA-16 CHECK requirement and is now amended to "share `0008`" in CONTEXT.md D-24-01.
**Notes:** D-24-02 picks Postgres `op.execute("DROP CONSTRAINT … ADD CONSTRAINT …")` because Postgres does not support in-place CHECK alter.

---

## `MEMBERSHIP_STATUS_TRANSITIONS` shape & state-machine helper consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| A | New `app/modules/memberships/constants.py` with `Mapping[str, frozenset[str]]`; central `_assert_can_transition` helper; refactor existing `_assert_can_*` to delegate | ✓ |
| B | Inline constant into `models.py` near the CHECK; keep per-transition helpers as-is | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** REQUIREMENTS INFRA-16 names `app/modules/memberships/constants.py` verbatim. Single source of truth (the constant) reduces drift between CHECK, transitions matrix, and 409 raises. `MappingProxyType` makes the dict immutable at module load. `str` keys (not `MembershipStatus` enum) avoid a potential circular import.
**Notes:** D-24-04 reuses the existing `InvalidTransitionError` (`app/core/exceptions.py:158`) — no exception class added. The 9-cell matrix in `tests/unit/memberships/test_state_machine.py` keeps its shape; Phase 25 extends to 16 cells.

---

## DEBT-01 resolver `today` injection

| Option | Description | Selected |
|--------|-------------|----------|
| A | Inject `today: date | None = None` (default Europe/Moscow); mirrors `_expire_due_memberships` pattern | ✓ |
| B | Compute internally; expose seam via `freezegun` only | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** Symmetry with the Phase 18 worker injection pattern; deterministic integration tests possible without `freezegun` or `monkeypatch.setattr`. Repository docstring at `repository.py:283-297` is REVERSED by D-24-08 — the previous "no date filter by design" note becomes a defence-in-depth filter against missed ARQ ticks.
**Notes:** Existing composite index `ix_memberships_client_id_status_end_date` covers the new predicate (rightmost column is `end_date DESC`).

---

## DEBT-02 `?expiring=true&within=N` query shape & predicate

| Option | Description | Selected |
|--------|-------------|----------|
| A | Two flat params (`expiring: bool`, `within: int 1..30 default 7`) per REQUIREMENTS literal; force `status='active'` in repository when `expiring=true`; reject conflicting `status=expired&expiring=true` with 422 | ✓ |
| B | Single param `expiringWithin: int | None`; backend infers active filter | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** REQUIREMENTS DEBT-02 specifies the exact query string `?expiring=true&within=N` — backend matches verbatim. Forcing `status='active'` matches REQUIREMENTS wording ("returns only active memberships, expiring in window"). 422 on `?expiring=true&status=expired` is louder than silent override; FE will not send the conflict in practice (FE's filter UI is mutually exclusive with the status filter).
**Notes:** Mock service (D-24-13) accepts `within: number = 7` and replaces hard-coded `EXPIRING_DAYS = 7`. The http adapter strips its client-side filter + `BLK-06` pagination workaround once the backend is paginating filtered set honestly. UI `within` selector is OUT OF SCOPE — Phase 28 (FE-13) decides.

---

## DEBT-03 SVC001 walker — auth/service.py write paths

| Option | Description | Selected |
|--------|-------------|----------|
| A | Add explicit `await session.commit()` to public write paths in `auth/service.py`; extend `_INSPECTED_SERVICES`; no signature refactors | ✓ |
| B | Wrap audit emissions in private `_emit_and_commit_audit` helper carrying `# noqa: SVC001 caller-owns-txn` | |
| C | Refactor public functions to private `_*` helpers behind public `commit_*` wrappers | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** Zero signature change; aligns with the Phase 12.1 fix pattern already applied in `clients/service.py` and `memberships/service.py`. Per the walker's contract, `# noqa: SVC001 caller-owns-txn` is reserved for `_`-prefixed private helpers; auth's public functions are NOT caller-owns-txn.
**Notes:** D-24-15 inventories: `authenticate`, `issue_tokens`, `rotate_refresh`, `revoke_session`, `revoke_all_user_sessions`, `change_password`. `auth/telegram_service.py` is OUT OF SCOPE for Phase 24 (DEBT-03 wording covers `service.py` only) — deferred follow-up if planner finds problematic callsites.
**Risk noted (D-24-17):** existing `get_db` rollback drops audit rows that aren't explicitly committed. Adding commits will persist audit rows on failure paths (e.g., `login_failed`) where they were previously droppable on a downstream exception. This is the INTENDED fix (mirrors Phase 12.1). Planner verifies no integration tests assert audit-row absence.

---

## INFRA-15 audit frozenset layout

| Option | Description | Selected |
|--------|-------------|----------|
| A | Append six new pairs to v1.2 block under `# v1.3 (Phase 24 lock)` comment, in REQUIREMENTS order | ✓ |
| B | Insert new pairs near existing membership pairs (line 113-118) for thematic grouping | |

**Selected:** A — recommended default per `--auto`.
**Rationale:** Chronological grouping by phase mirrors the existing `# v1.1` / `# v1.2` comment headers in `audit.py:78-126`. Reading the frozenset top-to-bottom shows phase-ordered evolution; no callsite churn (events are pre-registered before Phase 25/26/27 emit them).
**Notes:** D-24-19 suggests a unit-test addition asserting the six pairs are present in `LOCKED_AUDIT_EVENTS` (without callsite-existence assertion — those land in downstream phases).

---

## Claude's Discretion

- Test-file naming for the new resolver date-filter test — proposed `test_resolver.py::test_resolver_filters_expired_active_row`; planner can rename if a more specific match exists.
- Order of helper refactors in `service.py` (D-24-04, D-24-05).
- Whether the `within` query param appears as `within` or `expiring_within` in the OpenAPI schema (recommended `within` to match REQUIREMENTS literal).
- Deferred follow-up scan of `auth/telegram_service.py` — surfaces during planning; if found, file as a deferred item.

## Deferred Ideas

- `auth/telegram_service.py` SVC001 audit (out of DEBT-03 scope — `service.py` only).
- `MEMBERSHIP_STATUS_TRANSITIONS` `frozen` matrix population — Phase 25.
- Operator-facing `within` selector UI — Phase 28 / FE-13.
- Renewal source `expired` start-date strategy — Phase 26 / MEM-REN-04.
- OpenAPI byte-stable regen enforcement — Phase 28 owns the cumulative `git diff --exit-code` (Phase 24 may locally refresh the JSON or punt depending on CI gate behavior; planner confirms).

## Pre-existing context applied (no re-asking)

- Membership `end_date` is **inclusive** (PROJECT.md Key Decisions; carried from v1.2). DEBT-02 predicate uses `end_date <= today + (within - 1)`.
- Backend wire format = camelCase via `BackendSchemaBase` (Phase 24's new query params follow: `expiring`, `within`).
- Pagination envelope `{items, total, page, pageSize}` mandatory (Phase 24's expiring branch keeps the envelope).
- Resolver touch-points serialized 24→25→26 (one-resolver-delta-per-phase rule from `.planning/STATE.md`).
- `gym_date` UNIQUE invariant + STORED column from Phase 19 — unaffected by Phase 24.
- ARQ cron `unique=True` + container `TZ=UTC` — unaffected by Phase 24.

## Todo cross-reference

`gsd-sdk query todo.match-phase 24` → 0 matches. Nothing folded, nothing deferred from todos.
