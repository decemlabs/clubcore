---
phase: 26-memberships-renewal-backend
plan: 02
subsystem: memberships
tags: [resolver, tiebreak, renewal, regression]
requires:
  - 26-01 (Membership.previous_membership_id ORM field + 0009_renewal migration)
provides:
  - find_active_for_client with start_date ASC, created_at DESC tiebreak
  - test_renewal_resolver_tiebreak.py (Phase 26 D-26-17 regression lock)
affects:
  - reception POST /api/v1/visits (Phase 19) — consumes resolver via ActiveMembership Protocol
  - Telegram /checkin handler (Phase 20) — consumes resolver via ActiveMembership Protocol
tech-stack:
  added: []
  patterns:
    - SAVEPOINT-mode db_session test fixture with direct ORM attribute set for previous_membership_id
    - asyncio.sleep(0.01) micro-pause to force measurable created_at delta within a single SAVEPOINT
key-files:
  created:
    - apps/backend/tests/integration/memberships/test_renewal_resolver_tiebreak.py
  modified:
    - apps/backend/app/modules/memberships/repository.py
decisions:
  - D-26-17 (resolver tiebreak inverted to start_date ASC, created_at DESC)
  - D-26-18 (function signature unchanged — keyword-only `today`)
  - D-26-19 (docstring updated with cross-phase regression discipline + index-adequacy)
metrics:
  duration: ~25 minutes
  completed: 2026-05-09
  tasks-completed: 2/2
  files-changed: 2
  pre-change-baseline: 93 passed (visits 33 + auth 45 + resolver 11 + freeze_resolver 3 + alembic_visits 1)
  post-change: 97 passed (baseline + 4 new tests in test_renewal_resolver_tiebreak.py)
---

# Phase 26 Plan 02: Resolver Tiebreak Inversion (start_date ASC) Summary

Inverts `find_active_for_client` ORDER BY from `end_date DESC, created_at DESC` to `start_date ASC, created_at DESC` so check-in keeps using the running membership until `source.end_date` passes (then ARQ flips it to `expired` and the renewal naturally takes over). Highest-risk Phase 26 lock isolated in its own wave; pre-change baseline + post-change rerun on Phase 19 (visits) + Phase 20 (auth/telegram) suites prove zero regressions.

## What Changed

### `apps/backend/app/modules/memberships/repository.py` (modified)
- `find_active_for_client` ORDER BY: `Membership.end_date.desc(), Membership.created_at.desc()` → `Membership.start_date.asc(), Membership.created_at.desc()`. Single-line change in body; WHERE clause and `LIMIT 1` unchanged; signature `(session, client_id, *, today)` unchanged.
- Docstring rewritten end-to-end:
  - Cites `MEM-04, DEBT-01, Phase 26 D-26-17`.
  - Explains running-source-wins rationale + ARQ-flip handoff.
  - Index-adequacy note: composite `ix_memberships_client_id_status_end_date` covers WHERE; new `start_date ASC` is sorted in memory; ≤2 active rows per client → effectively O(1); NO new index added.
  - Manual-stacking compatibility (Phase 17 D-01 silent tiebreak preserved).
  - Cross-phase regression discipline: pointer to `test_renewal_resolver_tiebreak.py` + reminder to rerun visits + auth integration suites BEFORE and AFTER any future change.

### `apps/backend/tests/integration/memberships/test_renewal_resolver_tiebreak.py` (NEW, 197 LOC)
- `test_resolver_prefers_running_source_over_renewal` — D-26-17 happy path; running source wins because `start_date ASC` puts the earlier-started row first. **This was the RED test that flipped to GREEN after Task 2.**
- `test_resolver_switches_to_renewal_when_source_expires` — simulates ARQ flip on `source.end_date+1`; resolver returns the renewal once source `status='expired'` (filtered out).
- `test_resolver_manual_stacking_same_start_date_tiebreaks_created_at_desc` — Phase 17 D-01 manual stacking preserved; same start_date → `created_at DESC` tiebreak → later-created wins (silent, no audit, no warning).
- `test_resolver_signature_unchanged` — D-26-18 lock; asserts signature is exactly `(session, client_id, *, today)` with `today` keyword-only.

`previous_membership_id` set via direct ORM attribute assignment after `make_membership` construction (the conftest helper does NOT yet accept `previous_membership_id` as a kwarg). This keeps the test self-contained — no shared-fixture surface change in this plan.

## Pre-change Baseline (PROOF — Risks/Watchpoints #1)

Captured BEFORE the ORDER BY change so a regression cannot be ascribed to Task 1's new tests:

```
cd apps/backend && uv run pytest \
  tests/integration/visits/ \
  tests/integration/auth/ \
  tests/integration/memberships/test_resolver.py \
  tests/integration/memberships/test_freeze_resolver.py
```

Result: **93 passed in 10.82s**

| Suite | Count |
|---|---|
| `tests/integration/visits/` (alembic + audit + concurrent + create + list/get + rbac + self_checkin) | 33 |
| `tests/integration/auth/` (invalid_session + login + login_argon2_hygiene + logout + refresh + sessions_endpoints + telegram_start + telegram_verify_errors + telegram_verify_happy) | 45 |
| `tests/integration/memberships/test_resolver.py` | 11 |
| `tests/integration/memberships/test_freeze_resolver.py` | 3 |
| `tests/integration/visits/test_alembic_visits.py` | 1 (counted under visits/ above) |
| **Total** | **93** |

## Post-change Result

After flipping ORDER BY + adding the 4 new tests in `test_renewal_resolver_tiebreak.py`:

```
cd apps/backend && uv run pytest \
  tests/integration/memberships/test_renewal_resolver_tiebreak.py \
  tests/integration/memberships/test_resolver.py \
  tests/integration/memberships/test_freeze_resolver.py \
  tests/integration/visits/ \
  tests/integration/auth/
```

Result: **97 passed in 10.64s** (= 93 baseline + 4 new tests). Zero regressions on Phase 19 visits or Phase 20 auth.

The previously-RED test `test_resolver_prefers_running_source_over_renewal` is now GREEN — proves the ORDER BY change actually exercises the new behaviour (single-row test scenarios are tiebreak-irrelevant; only multi-active-row scenarios surface the change).

## ORDER BY: Before / After

```python
# Before (Phase 17 D-17 / Phase 24 DEBT-01)
.order_by(Membership.end_date.desc(), Membership.created_at.desc())

# After (Phase 26 D-26-17)
.order_by(Membership.start_date.asc(), Membership.created_at.desc())
```

Function signature, WHERE clause, and `LIMIT 1` unchanged.

## Verification Gates

| Gate | Result |
|---|---|
| `uv run ruff check app/modules/memberships/repository.py tests/integration/memberships/test_renewal_resolver_tiebreak.py` | All checks passed! |
| `uv run mypy --strict app/modules/memberships/repository.py` | Success: no issues found in 1 source file |
| `uv run lint-imports` | 3 contracts kept, 0 broken (71 files / 146 deps) |
| `uv run pytest tests/integration/memberships/test_renewal_resolver_tiebreak.py` | 4/4 passed |
| `uv run pytest tests/integration/memberships/test_resolver.py` | 11/11 passed (Phase 17 unchanged) |
| `uv run pytest tests/integration/memberships/test_freeze_resolver.py` | 3/3 passed (Phase 25 unchanged) |
| `uv run pytest tests/integration/visits/` | 33/33 passed (Phase 19 unchanged) |
| `uv run pytest tests/integration/auth/` | 45/45 passed (Phase 20 unchanged) |

## Commits

- `afe8cc6` — `test(26-02): add Phase 26 D-26-17 resolver tiebreak regression test (RED)` — 1 file, +197 LOC
- `07548ec` — `feat(26-02): invert resolver tiebreak to start_date ASC for renewal stacking` — 1 file, +45/-19 LOC

## Deviations from Plan

None — plan executed exactly as written. Two-task TDD flow (RED test first, then ORDER BY flip) followed; pre-change baseline captured before any source modification per Risks/Watchpoints #1.

A single test-design choice deserves explicit call-out (not a deviation, but a documented scope-boundary decision): the conftest `make_membership` helper does NOT accept `previous_membership_id` as a kwarg. Plan 26-02 explicitly authorised either extending the helper OR setting via direct ORM attribute. **Chose direct ORM attribute** to keep this plan self-contained (no shared-fixture surface change). When Wave 3 (`renew_membership` service) lands and end-to-end renewal tests are written, extending the helper will become the natural pattern; for now the resolver-only test does not need it.

## Surprises

None during the rerun. The Phase 17 `test_resolver_tiebreak_picks_latest_end_date` test (which uses identical start_date for both rows) stays green because the `created_at DESC` second sort key still selects the later-created row (`m_long`) — the test's invariant ("longer-end-date wins") happens to hold under the new tiebreak too because `m_long` was created second. Phase 17 test author was explicit: rows tie on both fields → "natural ordering" — accepted.

Auth gates: none (no external services touched).

## Threat Flags

None. The ORDER BY change is the single mitigation surface (T-26-02-01) and was explicitly verified by the pre/post baseline rerun. No new endpoints, no new schema, no new permission surface.

## Self-Check: PASSED

- File `apps/backend/tests/integration/memberships/test_renewal_resolver_tiebreak.py`: FOUND
- File `apps/backend/app/modules/memberships/repository.py`: FOUND (modified)
- Commit `afe8cc6`: FOUND in `git log`
- Commit `07548ec`: FOUND in `git log`
- ORDER BY clause `start_date.asc(), created_at.desc()`: GREP CONFIRMED at line 376
- Docstring contains `Phase 26 D-26-17`: GREP CONFIRMED (lines 324, 326)
- Docstring contains `test_renewal_resolver_tiebreak.py`: GREP CONFIRMED (line 360)
