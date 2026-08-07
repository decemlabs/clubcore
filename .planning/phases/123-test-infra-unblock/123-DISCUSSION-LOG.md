# Phase 123: Test-Infra Unblock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 123-test-infra-unblock
**Areas discussed:** Registry row mechanics, Fresh-run protocol, Fix-vs-defer policy, Timebox & fallback

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Механика строк реестра | Frozen registry has no TEST rows; where do Phase-123 rows go, what category/tag | ✓ (delegated) |
| Протокол свежего прогона | Clean-DB run count, evidence archiving, regression definition | ✓ (delegated) |
| Fix-vs-defer по хвосту падений | Per-item disposition for F821 / freeze_race / alembic_clean / diagnosis-vs-roadmap divergence | ✓ (delegated) |
| Таймбокс и fallback | Cycles before per-module workaround; formalizing SC-2 | ✓ (delegated) |

**User's choice:** "сам все выбери и реши" — all four areas delegated to Claude; every decision resolved to Claude's recommended option (D-123-01 … D-123-11 in CONTEXT.md).
**Notes:** No follow-up questions were asked; single-turn delegation. Interactive `--chain` mode, so plan+execute auto-advance follows.

## Claude's Discretion

All areas (full delegation). Remaining open for planner/executor: DB-reset command shape, one-plan-vs-two sequencing, deferred-row reason wording.

## Deferred Ideas

- Structural asgi_lifespan pollution fix (test-architecture change, v4.2 candidate)
- Deterministic un-flaking of `test_freeze_race` (only if one-look fix fails)
- LOCKED_AUDIT_EVENTS 117→118 + `/metrics` route gate → Phase 124 locked-invariant lane via registry rows
- `test_sell_*` unscoped-select structural fix stays tracked in STATE.md Deferred Items
