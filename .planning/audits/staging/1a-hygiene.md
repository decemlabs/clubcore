<!--
Sub-pass: 1a — Static hygiene sweep (no running infra)
ID prefix: V41-HYG (rows this sub-pass primarily produces)
Note: 1a may ALSO produce rows whose `category` column is FUNC (e.g. reachability-manifest
findings). merge-registry.mjs routes every row by its own `category` column, not by this
file's name — see tools/audit/README.md.
This file is staging only. It is never read by anything except tools/audit/merge-registry.mjs,
and is deleted at freeze (122-06). Do not write to the registry directly (D-122-04).
-->

| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |
|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|
