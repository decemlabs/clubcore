# 47-07 SUMMARY — `.importlinter` preemptive INFRA-40 contract (Option A deferral)

**Plan:** 47-07
**Phase:** 47 — Bedrock (v1.7 INFRA primitives)
**Requirement:** INFRA-40
**Status:** ✓ Complete (with Option A scope adjustment, user-approved 2026-05-21)
**Commit:** `a659a75` — feat(47-07): preemptive INFRA-40 ignore edges + Option A deferral

## What shipped

Single-file edit to `apps/backend/.importlinter`:

1. **3 INFRA-40 `ignore_imports` edges added** (modules-independent contract):
   - `app.modules.online_payments.service -> app.modules.payments.models`
   - `app.modules.online_payments.service -> app.modules.users.display`
2. **1 INFRA-40 `ignore_imports` edge added** (integrations-not-depend-on-modules contract):
   - `app.integrations.email.dispatcher -> app.modules.online_payments.email_templates`
3. **`unmatched_ignore_imports_alerting = warn`** added to both contract blocks so the unused-ignore signal remains visible without failing CI before Phase 49 ships the module body.

## Option A deferral — what did NOT ship

`app.modules.online_payments` was **NOT** added to the `modules =` list inside the `modules-independent` contract.

### Why

import-linter 2.11 (current version, verified via `uv run lint-imports`) rejects `modules =` entries that don't resolve to a real on-disk Python package:

```
Module 'app.modules.online_payments' does not exist.
EXIT=1
```

There is no `optional_modules`, `missing_modules_alerting`, or equivalent flag in the 2.x line (verified against context7 `seddonym/import-linter` docs — only `unmatched_ignore_imports_alerting` exists). The plan's "preemptive registration" premise was therefore incompatible with the installed tooling.

The execute-plan agent paused at this discovery (Rule 4 — Decision Checkpoint) and surfaced 4 options. User selected **Option A** (2026-05-21):

> Ship ignore edges now; defer `modules =` entry to Phase 49.

### Cost

Phase 49's first commit MUST append one line to the `modules =` list in `apps/backend/.importlinter`:

```
modules =
    app.modules.auth
    ...
    app.modules.users
    app.modules.online_payments    # ← Phase 49 adds this line first thing
```

This is documented inline in `.importlinter` with a full rationale comment block. The `unmatched_ignore_imports_alerting = warn` setting will continue to emit the 3 unused-ignore warnings until the module body lands; once `online_payments.service` and `email.dispatcher` resolve those imports, the warnings clear automatically.

### Discipline preserved

- **INFRA-15 "before-callsite" discipline holds for the 3 ignore edges.** Phase 49 cannot land its module body with a misplaced import — the edges are already registered to fail fast.
- **The `modules =` half of INFRA-15 is honored at Phase 49 commit-1, not Phase 47.** A one-line `.importlinter` edit at the top of Phase 49 closes the gap.

## Verification

```
$ uv run lint-imports --config apps/backend/.importlinter
Analyzed 157 files, 436 dependencies.

core must not import modules KEPT
modules cannot import each other KEPT (2 warnings)
integrations must not import modules KEPT (1 warning)

Contracts: 3 kept, 0 broken.
```

The 3 warnings are exactly the 3 preemptive online_payments ignore edges. They are expected and will clear when Phase 49+52 ship the corresponding module bodies.

## Files modified

- `apps/backend/.importlinter` (+37 / -1 lines — 4 new ignore edges, 2 new `unmatched_ignore_imports_alerting = warn` lines, 1 deferral-rationale comment block, removed the preemptive `app.modules.online_payments` entry from `modules =`)

## Deviations from plan

**Deviation D-47-07-01 (Rule-3 scope adjustment, user-approved):**

The plan as written instructed adding `app.modules.online_payments` to the `modules =` list of the `modules-independent` contract. This was empirically incompatible with import-linter 2.11 (module-existence check fatals). User-approved Option A defers this single line to Phase 49 commit-1.

No D-47 decision was violated; the plan's `<universal_rules>` (no `app.modules.online_payments` module created in Phase 47) is honored as written.

## Phase 49 carry-out

Phase 49's first commit must:
1. Create `apps/backend/app/modules/online_payments/__init__.py` (and the module structure)
2. Append `app.modules.online_payments` to the `modules =` list in `apps/backend/.importlinter`
3. The 3 unused-ignore warnings in this commit's `lint-imports` output will clear automatically as `online_payments.service` lands its imports

A line item should be added to Phase 49's planning (47-CONTEXT.md `<deferred>` or a Phase 49-specific CONTEXT.md when it's discussed) to ensure this step is not missed.
