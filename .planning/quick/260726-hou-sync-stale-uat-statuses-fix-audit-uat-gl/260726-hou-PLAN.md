---
quick_id: 260726-hou
slug: sync-stale-uat-statuses-fix-audit-uat-gl
date: 2026-07-26
mode: quick (inline — no subagents; see note)
description: >
  Close the three groups of findings from the 2026-07-26 cross-phase UAT audit:
  reconcile stale UAT statuses, fix the audit-uat scanner's false All Clear, and
  fix the bugs the audit surfaced.
note: >
  Executed inline rather than via gsd-planner/gsd-executor subagents — the session
  carries a standing "no subagents unless explicitly requested" constraint. GSD
  guarantees preserved: task dir, PLAN.md, atomic commits, SUMMARY.md, STATE.md row.
---

# Quick Task 260726-hou — UAT audit follow-through

## Origin

`/gsd-audit-uat` on 2026-07-26 returned `total_items: 0` — a FALSE All Clear. Its
glob only covers `.planning/phases/*`, which is empty because every milestone
through v4.0 is archived. A manual scan of `.planning/milestones/*-phases/*/`
found 96 UAT/VERIFICATION files with ~83 outstanding items, of which ~35 turned
out to be documentation lag rather than real work.

## Tasks

### Task 1 — Fix the audit-uat scanner (root cause of the false All Clear)

**Files:** `.claude/gsd-core/bin/lib/uat.cjs`,
`.claude/gsd-core/bin/lib/audit-command-router.cjs`,
`.claude/gsd-core/workflows/audit-uat.md`

- Add `--include-archived` to scan `.planning/milestones/<ver>-phases/*`.
  Archived phases must bypass `getMilestonePhaseFilter` — that filter scopes to the
  CURRENT milestone and therefore excludes every archived phase by construction.
- Tag results with `milestone` + `archived` so callers can separate historical debt
  from current-milestone blockers.
- Always emit `archived_phase_dirs` / `archived_files_unscanned` so a `0` can never
  be read as "nothing outstanding anywhere".
- Treat a `resolved` PREFIX as resolved in Gaps/Deferred entries — exact equality
  rejected the convention actually in use (`status: RESOLVED (…, 2026-06-01) — …`).
- Workflow: only claim All Clear when the archive was scanned or is empty.

**Verify:** `audit-uat` with no flag still returns the same results as before plus
the new summary fields; `--include-archived` surfaces the archive.
**Done:** archived items are reachable and a false All Clear is impossible.

**Constraint:** `.claude/` is gitignored, so this patch is NOT under version
control. Save a real unified diff against pristine `@opengsd/gsd-core@1.8.0` into
this task dir so the change is reviewable and recoverable, and re-apply via
`/gsd-reapply-patches` after `/gsd-update`.

### Task 2 — Reconcile stale UAT statuses

**Files:** `999.3` / `999.4` / `999.5` / `86` / `87` / `88` / `94` / `101` / `102` /
`103` / `104` `-VERIFICATION.md`, plus `999.4-HUMAN-UAT.md`

Each carried `status: human_needed` while a companion `*-HUMAN-UAT.md` / `*-UAT.md`
recorded the run as done. Set the status from the recorded evidence — never invent a
result — and cite the evidence file. Phases with genuinely-open remainders
(`94`, `102`) stay `human_needed` with the item list trimmed to reality.

**Verify:** re-run `audit-uat --include-archived`; item count drops by exactly the
reconciled set and nothing genuinely open disappears.
**Done:** no VERIFICATION file claims `human_needed` for work already signed off.

### Task 3 — The bugs the audit surfaced

- **REV-01** — re-check before touching code.
- **Chat typing indicator (Phase 94)** — reproduce before fixing; add a jsdom test
  pinning the consumer path either way.
- **seaweedfs-s3 CrashLoop** — not reproducible without a live cluster; document as
  open, do not blind-patch.

**Done:** each bug is either fixed with a test, or recorded as open with the reason.

## Out of scope

The 27 v4.0 operator-pending items (118–121) and the 2 HARD gates (SEC-02 RSA-key
off-node backup, BAK-03 restore round-trip). Those are the deliberate
`D-V40-LOCAL-VALIDATE` boundary awaiting a real k3s toolchain, not forgotten debt.
