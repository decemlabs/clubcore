---
phase: 24-foundations-tech-debt-bedrock
plan: 03
subsystem: memberships
tags:
  - memberships
  - resolver
  - tech-debt
  - europe-moscow
  - DEBT-01
requirements_completed:
  - DEBT-01
dependency-graph:
  requires:
    - 24-02  # 0007_status_taxonomy migration head (no actual schema dependency, but plan ordering)
  provides:
    - resolver-end-date-filter  # Phase 25 freeze + Phase 26 renewal layer onto this same resolver path
  affects:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/tests/integration/memberships/test_resolver.py
tech-stack:
  added: []
  patterns:
    - europe-moscow-today-injection-on-resolver  # service-layer resolves None → MSK today, repository stays pure
key-files:
  created: []
  modified:
    - path: apps/backend/app/modules/memberships/service.py
      role: service orchestration
      change: resolve_active_membership_by_client gains keyword-only today: date | None = None; resolves None → datetime.now(MSK).date() before delegating to repository
    - path: apps/backend/app/modules/memberships/repository.py
      role: repository SQL query builder
      change: find_active_for_client requires keyword-only today: date; adds Membership.end_date >= today predicate; docstring REVERSED to cite DEBT-01 + missed-ARQ-tick rationale
    - path: apps/backend/tests/integration/memberships/test_resolver.py
      role: integration test
      change: new test_resolver_filters_expired_active_row guards the missed-ARQ-tick scenario
decisions:
  - "DEBT-01: defence-in-depth end_date >= today filter on resolver path (closes v1.2 MEM-04 D-13)"
  - "today=None resolves at the SERVICE layer to datetime.now(MSK).date(); repository stays pure with required keyword-only today: date (D-24-06)"
  - "Repository docstring REVERSED — removed 'Date filter is intentionally NOT applied here'; new text cites DEBT-01 + missed-ARQ-tick rationale (D-24-08)"
  - "Composite index ix_memberships_client_id_status_end_date covers the new predicate (rightmost column is range-scan friendly) — no migration needed (D-24-07)"
metrics:
  duration_minutes: 5
  completed_at: 2026-05-08T18:35:01Z
  tasks_completed: 1
  tasks_total: 1
  files_changed: 3
  commits: 2
---

# Phase 24 Plan 03: Resolver `end_date >= today (Europe/Moscow)` Filter Summary

Defence-in-depth filter on `resolve_active_membership_by_client` so a missed ARQ `expire_memberships` tick can no longer leave a stale `status='active'` row passable for visit creation or Telegram self-checkin.

## Plan Header

- **Phase:** 24 — Foundations & Tech-Debt Bedrock
- **Plan:** 03 — Resolver `end_date >= today` filter (DEBT-01)
- **Type:** TDD (RED → GREEN)
- **Wave:** 2
- **Status:** Complete
- **Duration:** ~5 minutes
- **Requirements closed:** DEBT-01

## Objective Recap

Close the v1.2 MEM-04 D-13 gap carried into v1.3 as DEBT-01. Phase 18's ARQ cron is the primary `active → expired` flipper, but the resolver is the ultimate authorisation gate for visit creation and Telegram check-in. A missed cron tick (worker crash, deploy window) previously allowed a `status='active'` row whose `end_date` had already passed to be selected by the resolver — silently authorising a visit on an expired membership. Phase 24 closes this gap before Phases 25 (freeze) and 26 (renewal) layer further logic onto the same resolver path.

## What Shipped

### Service layer (`apps/backend/app/modules/memberships/service.py`)

```python
async def resolve_active_membership_by_client(
    session: AsyncSession,
    client_id: UUID,
    *,
    today: date | None = None,
) -> Membership | None:
    ...
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    return await repository.find_active_for_client(session, client_id, today=today)
```

The signature mirrors the canonical `_expire_due_memberships(today=None)` injection pattern at `service.py:497-543`. Tests pass an explicit `today` for determinism (no `freezegun`). The Protocol slot `ActiveMembershipResolver` at `core/dependencies.py:81` (`Callable[[AsyncSession, UUID], Awaitable[ActiveMembership | None]]`) accepts the new signature because the optional keyword-only kwarg has a default — verified by `mypy --strict` clean across `app/modules/memberships/` and `app/core/dependencies.py`.

### Repository layer (`apps/backend/app/modules/memberships/repository.py`)

```python
async def find_active_for_client(
    session: AsyncSession,
    client_id: UUID,
    *,
    today: date,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, DEBT-01).
    ...
    Date filter (DEBT-01, Phase 24): we apply `end_date >= today` here as a
    defence-in-depth backstop. Phase 18's ARQ `expire_memberships` cron is
    the primary `active → expired` flipper, but a missed tick (worker crash,
    deploy window) would otherwise leave a stale `status='active'` row
    passable for visits / Telegram check-in. The resolver is the ultimate
    gate, so it filters by date as well.
    ...
    """
    stmt = (
        select(Membership)
        .where(
            Membership.client_id == client_id,
            Membership.status == "active",
            Membership.end_date >= today,
        )
        .order_by(Membership.end_date.desc(), Membership.created_at.desc())
        .limit(1)
    )
    ...
```

`today` is required keyword-only (no default) — keeps the repository pure; the service layer owns the MSK resolution. The composite index `ix_memberships_client_id_status_end_date` on `(client_id, status, end_date DESC)` covers the new predicate (rightmost column is range-scan friendly).

### Repository docstring REVERSED

The previous docstring read:

> Date filter is intentionally NOT applied here: per D-13, status field is the gate, not end_date. Phase 18 ARQ flips status -> 'expired' on its own cadence; until then a row whose end_date has passed but whose status is still 'active' is the canonical row.

This entire paragraph has been removed. The new docstring cites DEBT-01 + the missed-ARQ-tick rationale and explicitly notes the index coverage and the contract that callers MUST resolve `today` to Europe/Moscow before calling.

Verification:
```
$ grep -c -F "Date filter is intentionally NOT applied here" apps/backend/app/modules/memberships/repository.py
0
$ grep -c -F "DEBT-01" apps/backend/app/modules/memberships/repository.py
2
```

### Integration test (`apps/backend/tests/integration/memberships/test_resolver.py`)

New test `test_resolver_filters_expired_active_row` inserts a row with `status='active'` AND `end_date = today - timedelta(days=1)` (the canonical missed-ARQ-tick simulation) and asserts the resolver returns `None` when called with explicit `today=today`. All 10 pre-existing resolver tests stay green — they use `today + timedelta(days=N)` for `N > 0`, so `end_date >= today` is satisfied.

Phone uniqueness: chose `+79991232100` after grep-confirming no collision with `+79991232001` … `+79991232009` already used in the file.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED — failing test only | `7e1dbcb test(24-03): add failing test for DEBT-01 resolver date filter` | Pass — confirmed `1 failed` before impl (TypeError on unexpected `today` kwarg) |
| GREEN — minimal implementation | `429822a feat(24-03): apply end_date >= today filter on active membership resolver` | Pass — `11 passed in 1.35s` for resolver suite |
| REFACTOR | _not needed — implementation was already minimal_ | n/a |

Full git log:
```
429822a feat(24-03): apply end_date >= today filter on active membership resolver
7e1dbcb test(24-03): add failing test for DEBT-01 resolver date filter
```

## Verification Results

| Verification | Result |
|--------------|--------|
| `pytest tests/integration/memberships/test_resolver.py -x -v` | 11 passed in 1.35s (incl. new `test_resolver_filters_expired_active_row`) |
| `pytest tests/integration/memberships/ tests/unit/memberships/ -x` | 153 passed in 13.15s |
| `pytest tests/integration/visits/ tests/integration/telegram_bot/ -x` | 47 passed in 4.60s — downstream resolver consumers green |
| `pytest tests/unit/ -x` | 301 passed in 0.38s — full unit suite green |
| `ruff check app/modules/memberships/ tests/integration/memberships/test_resolver.py` | All checks passed |
| `mypy --strict app/modules/memberships/ app/core/dependencies.py` | Success: no issues found in 8 source files |

## Acceptance Criteria

| Criterion | Expected | Actual | Pass |
|-----------|----------|--------|------|
| `today: date \| None = None` in service.py | ≥ 2 | 2 | ✅ |
| `if today is None:` in service.py | ≥ 2 | 2 | ✅ |
| `today=today` pass-through in service.py | ≥ 1 | 1 | ✅ |
| `today: date` in repository.py | ≥ 1 | 2 | ✅ |
| `Membership.end_date >= today` in repository.py | exactly 1 | 1 | ✅ |
| "Date filter is intentionally NOT applied here" in repository.py | 0 | 0 | ✅ |
| `DEBT-01` in repository.py | ≥ 1 | 2 | ✅ |
| `test_resolver_filters_expired_active_row` in test file | ≥ 1 | 1 | ✅ |
| New test passes | pass | pass | ✅ |
| All existing resolver tests stay green | pass | pass | ✅ |
| `mypy --strict` clean | clean | clean | ✅ |

## Deviations from Plan

None — plan executed exactly as written. The plan-action steps A (repository), B (service), C (integration test) were applied verbatim; the verbatim docstring text from the plan was used unchanged; the proposed `+79991232100` phone literal was confirmed unique against the existing `+7999123200{1..9}` set in the file and used as-is.

The `<acceptance_criteria>` line `grep -E "today: date" apps/backend/app/modules/memberships/repository.py` returned 2 matches (one in the new signature, one in the docstring sentence "callers MUST resolve their Europe/Moscow `date`") — the criterion required `≥ 1`, so this is a pass with margin (not a deviation).

## Authentication Gates

None encountered.

## Known Stubs

None — no placeholder data, hardcoded empties, or "coming soon" markers introduced.

## Threat Model Compliance

The plan's `<threat_model>` listed three entries:

| Threat ID | Disposition | Plan said | What we did |
|-----------|-------------|-----------|-------------|
| T-24-03-01 (EoP — visit creation against expired membership) | mitigate | DEBT-01 closes the gap | Implemented the `end_date >= today` predicate AND added the regression test |
| T-24-03-02 (TOCTOU — midnight MSK boundary) | accept | inclusive `>=` matches v1.2 invariant | Implementation uses `>=`, so a check-in at 23:59:59 MSK on `end_date=today` succeeds; first MSK-second of the next day returns `None` (documented behaviour) |
| T-24-03-03 (Tampering — caller-supplied `today` in tests) | accept | tests pass explicit `today` for determinism | Test `test_resolver_filters_expired_active_row` passes explicit `today=today`; production callers go through the service-layer wrapper which resolves `None → MSK` (no remote-caller path injects `today`) |

No new threat surface introduced. Net surface change is negative (a class of escalation closed).

## Self-Check: PASSED

**Created files:** none (this plan only modifies existing files).

**Modified files (existence verified):**
- `apps/backend/app/modules/memberships/service.py` — present (file existed; modified)
- `apps/backend/app/modules/memberships/repository.py` — present (file existed; modified)
- `apps/backend/tests/integration/memberships/test_resolver.py` — present (file existed; modified)

**Commits verified in `git log --oneline`:**
- `7e1dbcb` test(24-03): add failing test for DEBT-01 resolver date filter — FOUND
- `429822a` feat(24-03): apply end_date >= today filter on active membership resolver — FOUND

**Deferred items:** none.
