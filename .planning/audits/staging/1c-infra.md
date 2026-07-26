<!--
Sub-pass: 1c — Infra triage (desk review of the v4.0 operator-pending ledger)
ID prefix: V41-INFRA
Note: merge-registry.mjs routes every row by its own `category` column, not by this file's
name — see tools/audit/README.md.
This file is staging only. It is never read by anything except tools/audit/merge-registry.mjs,
and is deleted at freeze (122-06). Do not write to the registry directly (D-122-04).

V41-INFRA-001 and V41-INFRA-002 below are the two v4.0 HARD GATE rows (SEC-02, BAK-03), seeded
here as this plan's tracer payload per D-122-23. They are permanent and stay
`deferred:operator-pending` for all of v4.1 — never edited, closed, or replaced (D-V41-K3D-SCOPE).
Sub-pass 1c continues INFRA numbering from V41-INFRA-003.
-->

| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |
|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|
| V41-INFRA-001 | INFRA | Blocker | infra/runbooks/sealed-secrets-key-backup.md | Attempt to verify off-node RSA-key custody for the sealed-secrets controller key using only the local k3d cluster — no second physical/off-node storage location exists in local dev, so custody cannot be exercised. | infra/runbooks/production.md § Operator-Pending Boundary (line 421+) HARD GATE 1; infra/runbooks/sealed-secrets-key-backup.md; carried from v4.0 `119-UAT.md` | deferred:operator-pending | 126 | — | no | real-hardware off-node custody unprovable in k3d — stays open/unedited per D-V41-K3D-SCOPE |
| V41-INFRA-002 | INFRA | Blocker | infra/runbooks/restore.md | Attempt a full backup-then-restore round-trip verification against production-equivalent hardware — k3d cannot prove real storage durability or node-failure recovery. | infra/runbooks/production.md § Operator-Pending Boundary (line 421+) HARD GATE 2; infra/runbooks/restore.md; carried from v4.0 `120-UAT.md` | deferred:operator-pending | 126 | — | no | verified restore round-trip on real hardware — stays open/unedited |
