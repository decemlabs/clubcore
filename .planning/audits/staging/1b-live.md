<!--
Sub-pass: 1b — Live-backend hunt (needs a running seeded backend, docker-compose)
ID prefix: V41-FUNC (rows this sub-pass primarily produces)
Note: merge-registry.mjs routes every row by its own `category` column, not by this file's
name — see tools/audit/README.md.
This file is staging only. It is never read by anything except tools/audit/merge-registry.mjs,
and is deleted at freeze (122-06). Do not write to the registry directly (D-122-04).
-->

| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |
|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|
