---
phase: 51
plan: 51-04
subsystem: integrations.yookassa
tags: [circuit-breaker, redis, fiscal, copy-and-adapt]
requires: [42-08]                       # D-51-14 copy source (email/circuit_breaker)
provides: [yookassa.circuit_breaker]    # consumed by plan 51-05 dispatch_fiscal_receipt
affects: []
tech_stack:
  added: []                             # no new dependencies — fakeredis + structlog + redis.asyncio already in tree
  patterns:
    - copy-and-adapt-over-generalize (D-51-14 — preserves integrations-isolated contract)
    - redis-sliding-window-circuit-breaker (Pitfall 11)
    - MULTI/EXEC atomic pipeline (transaction=True)
key_files:
  created:
    - apps/backend/app/integrations/yookassa/circuit_breaker.py
    - apps/backend/tests/unit/test_yookassa_circuit_breaker.py
  modified: []                          # .importlinter required no changes — contract already covers app.integrations.* uniformly
decisions:
  - "D-51-14 honored: copy-and-adapt from email/circuit_breaker.py instead of hoisting to app.core (keeps integrations-isolated import-linter contract intact)"
  - ".importlinter left UNCHANGED: the new module imports only stdlib + structlog + redis.asyncio; no new ignore entries needed and lint-imports reports 3 contracts kept"
metrics:
  duration_seconds: 144
  duration_human: "2m 24s"
  tasks_completed: 3
  files_created: 2
  files_modified: 0
  tests_added: 8
  commits: 2
  completed_at: "2026-05-23T04:54:25Z"
---

# Phase 51 Plan 04: ЮKassa Circuit Breaker (copy-and-adapt) Summary

Shipped the ЮKassa-scoped Redis sliding-window circuit breaker as a literal copy-and-adapt of `app/integrations/email/circuit_breaker.py` per D-51-14, with 8 unit tests locking the threshold/TTL/atomic-pipeline/provider-isolation properties; no `.importlinter` changes were required.

## What Was Built

`apps/backend/app/integrations/yookassa/circuit_breaker.py` exposes two async functions to plan 51-05's `dispatch_fiscal_receipt` ARQ task:

- `async is_circuit_open(redis, provider) -> bool` — O(1) `EXISTS` on `sz:yookassa:circuit:{provider}`; used at the head of the dispatch body so short-circuiting costs one Redis round trip rather than a full ЮKassa `/receipts` POST.
- `async record_failure(redis, provider) -> None` — atomic MULTI/EXEC pipeline of `ZADD` + `ZREMRANGEBYSCORE` + `EXPIRE` + `ZCARD` on the window sorted-set `sz:yookassa:circuit_window:{provider}`; when count ≥ 5, sets the open-marker key with `ex=300`.

Two Redis keys (per D-51-14 LOCKED constants):

| Key | Purpose | TTL |
|-----|---------|-----|
| `sz:yookassa:circuit_window:{provider}` | sorted set of recent failure timestamps (ms) | 2 × window = 120s (self-cleaning) |
| `sz:yookassa:circuit:{provider}` | EXISTS-only open-marker | 300s (the only closing surface) |

Constants: `_FAILURE_THRESHOLD=5`, `_WINDOW_SECONDS=60`, `_OPEN_TTL_SECONDS=300` — copied verbatim from the email module.

## Diff vs Email Circuit Breaker (D-51-14 audit)

The whole point of copy-and-adapt is that the diff is mechanical. Confirmed by `diff -u app/integrations/email/circuit_breaker.py app/integrations/yookassa/circuit_breaker.py` — the only changes are:

1. **Module docstring** — rewritten for the ЮKassa /receipts scope, references Pitfall 11 and D-51-14 instead of D-42-14.
2. **Key prefixes** — `_CIRCUIT_KEY_PREFIX: "sz:email:circuit:"` → `"sz:yookassa:circuit:"`; `_WINDOW_KEY_PREFIX: "sz:email:circuit_window:"` → `"sz:yookassa:circuit_window:"`.
3. **Structlog logger** — `"integrations.email.circuit_breaker"` → `"integrations.yookassa.circuit_breaker"`.
4. **`_OPEN_TTL_SECONDS` inline comment** — `(D-42-14)` → `(D-51-14)`.
5. **`is_circuit_open` docstring** — task name `dispatch_email` → `dispatch_fiscal_receipt`, "full SES-V2 send" → "full ЮKassa /receipts POST".

Function bodies (`is_circuit_open`, `record_failure`) and constants `_FAILURE_THRESHOLD=5`, `_WINDOW_SECONDS=60`, `_OPEN_TTL_SECONDS=300` are byte-identical to the source module.

## Unit Tests

`apps/backend/tests/unit/test_yookassa_circuit_breaker.py` — 8 tests, all green via `fakeredis.aioredis.FakeRedis`:

1. `test_is_circuit_open_returns_false_when_no_open_marker` — clean state → False.
2. `test_is_circuit_open_returns_true_when_marker_set` — manual `SET sz:yookassa:circuit:receipts 1 EX 300` → True.
3. `test_record_failure_increments_window_sorted_set` — one call → `ZCARD == 1`.
4. `test_record_failure_opens_circuit_at_threshold` — 5 calls → open + `290 ≤ TTL ≤ 300`.
5. `test_record_failure_does_not_open_below_threshold` — 4 calls → closed.
6. `test_record_failure_evicts_stale_entries_from_window` — pre-seeded entry at `now - (window+60)s` is removed by ZREMRANGEBYSCORE on next failure.
7. `test_atomic_pipeline_used_for_record_failure` — patches `redis.pipeline` with a MagicMock spy that wraps the real call; asserts `transaction=True` kwarg is set. **This locks the Pitfall 11 MULTI/EXEC discipline against regression.**
8. `test_record_failure_with_different_providers_uses_separate_counters` — `"receipts"` and `"other"` get independent window sorted-sets and independent open-marker keys.

## Verification

```
ruff check app/integrations/yookassa/ tests/unit/test_yookassa_circuit_breaker.py  →  All checks passed!
mypy --strict app/integrations/yookassa/circuit_breaker.py                          →  Success: no issues found
lint-imports                                                                        →  Contracts: 3 kept, 0 broken
pytest tests/unit/test_yookassa_circuit_breaker.py -x -q                            →  8 passed in 0.04s
```

## .importlinter Audit

Pre-run baseline + post-implementation: `lint-imports` reports **3 contracts kept, 0 broken**. The two unmatched-ignore warnings (`online_payments.service → users.display`, `email.dispatcher → online_payments.email_templates`) are pre-existing INFRA-40 preemptive registrations whose target module bodies ship later; they are unrelated to this plan.

No edit was applied to `.importlinter` because:

- The new `circuit_breaker.py` imports only stdlib (`time`, `typing.Final`, `uuid.uuid4`) + external (`structlog`, `redis.asyncio.Redis`). All external packages are already allowed.
- The `integrations-not-depend-on-modules` contract forbids `app.integrations.* → app.modules.*`; the new file has zero `app.modules.*` edges.
- There is no `integrations-isolated` contract literally so named in the project (D-51-14 used the conceptual term); the contract that enforces it is `integrations-not-depend-on-modules` plus the absence of cross-integration imports inside `app.integrations.yookassa.*`. The new file imports nothing from `app.integrations.email` or any other integration sibling — verified by `grep`.

This is the success path for Task 3 — the plan's `action` explicitly permitted "leave `.importlinter` UNCHANGED".

## Decisions Made

1. **D-51-14 copy-and-adapt honored end-to-end.** No generalization to `app/core/circuit_breaker.py`; the email and ЮKassa breakers are now sibling modules with shared semantics but zero shared code. This preserves the import-linter ability to keep `app.integrations.email` and `app.integrations.yookassa` strictly isolated.
2. **Test file at flat `tests/unit/` path per plan frontmatter.** Project also has `tests/unit/integrations/yookassa/`, but the plan explicitly specifies `apps/backend/tests/unit/test_yookassa_circuit_breaker.py`. Followed plan over alternative convention; if a future cleanup wants to relocate it under `tests/unit/integrations/yookassa/`, the move is a no-op git rename.
3. **Spy on `redis.pipeline` (test 7) uses `patch.object` not a bare MagicMock.** A bare MagicMock would replace the pipeline and break the real `record_failure` flow; the chosen pattern (MagicMock with `side_effect=lambda *a, **kw: real_pipeline(*a, **kw)`) preserves the real ZADD/ZREMRANGEBYSCORE/EXPIRE/ZCARD execution while still capturing the `transaction=True` kwarg for assertion.

## Deviations from Plan

**None — plan executed exactly as written.** All acceptance criteria for each task pass; the diff vs `email/circuit_breaker.py` is constrained to the documented substitutions; `.importlinter` was left UNCHANGED as the plan's success branch specified.

## Files

### Created
- `apps/backend/app/integrations/yookassa/circuit_breaker.py` — Redis sliding-window circuit breaker (~115 lines, copy-and-adapt of email module).
- `apps/backend/tests/unit/test_yookassa_circuit_breaker.py` — 8 unit tests covering threshold, TTL, stale-entry trim, atomic-pipeline guard, and per-provider isolation.

### Modified
- (none) — `.importlinter` required no changes.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | ba41be8 | `feat(51-04): add yookassa circuit breaker (copy-and-adapt from email)` |
| 2 | 3855556 | `test(51-04): unit tests for yookassa circuit breaker` |

(Task 3 produced no diff and therefore no commit — the absence-of-change is the success condition.)

## Self-Check: PASSED

- `app/integrations/yookassa/circuit_breaker.py` exists — FOUND
- `tests/unit/test_yookassa_circuit_breaker.py` exists — FOUND
- Commit `ba41be8` (feat) — FOUND in `git log --oneline`
- Commit `3855556` (test) — FOUND in `git log --oneline`
- `lint-imports` → 3 contracts kept, 0 broken — VERIFIED
- `pytest tests/unit/test_yookassa_circuit_breaker.py` → 8/8 passed — VERIFIED
- `mypy --strict` on new file → no issues — VERIFIED
- No `app.integrations.email` import in new file — VERIFIED via `grep`
