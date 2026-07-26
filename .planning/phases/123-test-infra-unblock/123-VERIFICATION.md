---
phase: 123-test-infra-unblock
verified: 2026-07-26T20:15:00Z
status: passed
score: 14/14 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:

  - test: "Confirm the f438ced2 isolation-deadlock fix (no_permissive_booking_config marker + booking-race teardown restore + pytest-timeout 180s) holds as a *general* property of the suite, not merely as an artifact of this one fresh run."
    expected: "Reviewer judgment that one green, unnarrowed, clean-DB run with zero lock-family `Failed: Timeout >180.0s` entries is sufficient standing evidence for the general claim (the plan authors this explicitly as a backstop/judgment truth — no single mechanical check can promote 'held once' to 'holds as a property')."
    why_human: "This is a `verification: backstop` truth in 123-01-PLAN.md's must_haves — by construction unresolvable by grep/presence checks. Evidence exists (0 timeout matches, terminal summary line, D-123-09 verdict NOT REGRESSED) but the generalization beyond this one run is a judgment call, not a mechanical fact."

  - test: "Confirm the residual set recorded in residuals-isolation-2026-07-26.log and the SUMMARY's per-residual table is the complete and honest residual set for this run — nothing was suppressed, deselected, or quietly excluded from the pytest invocation."
    expected: "Reviewer judgment, informed by: the full-run invocation has no -k/-m/--deselect/path narrowing (confirmed: `collected 3071 items`, command line verbatim in SUMMARY §2); the green-washing scan (independently re-run during verification) found zero added skip/xfail/deselect markers in the tests tree; exactly 5 FAILED/ERROR node IDs appear in the full log and all 5 appear in the isolation log."
    why_human: "This is a `verification: backstop` truth in 123-01-PLAN.md's must_haves. Mechanical evidence strongly supports honesty (independently re-verified: unnarrowed invocation, zero suppression markers added) but the plan author explicitly routes 'nothing was suppressed' claims to human judgment rather than a mechanical pass."

  - test: "Confirm each deferred registry row (V41-HYG-075 test_freeze_race, V41-HYG-079 asgi_lifespan) received the honest reason category (accepted-risk vs out-of-scope vs operator-pending) rather than whichever label was most convenient to close the row."
    expected: "Reviewer judgment that `deferred:accepted-risk` is the correct category for both rows given their evidence: test_freeze_race fails alone / passes together (genuine scheduling-dependent flake, not a fix-avoidance label), and the asgi_lifespan row passes in isolation both alone and together (full-suite-only pollution, structural fix explicitly named as out-of-scope-for-this-phase in the row's own prose)."
    why_human: "This is a `verification: backstop` truth in 123-02-PLAN.md's must_haves. The row cells are internally consistent with the isolation evidence (independently re-checked against residuals-isolation-2026-07-26.log during this verification) but the labeling honesty itself is a judgment call the plan explicitly defers to a human, not a mechanical check."

  - test: "Confirm every appended registry row's repro/reason cell truthfully states the item is known-pre-freeze and carried from TEST-01/TEST-02, rather than being presented as a new audit discovery."
    expected: "Reviewer judgment that the 'Known-pre-freeze... not a new audit discovery (D-123-02)' sentence appended to rows V41-HYG-073 through 079 is an accurate characterization, and that row V41-HYG-080 (the fixture-date time-bomb) is correctly labeled 'NEW finding surfaced 2026-07-26... not one of the roadmap-named or June-diagnosis residuals' rather than mislabeled as pre-existing."
    why_human: "This is a `verification: backstop` truth in 123-02-PLAN.md's must_haves. All 8 rows were read directly during verification and each row's honesty language is present and internally consistent with the surrounding evidence, but the mechanical-tag-honesty claim (D-123-02) is explicitly a judgment call per the plan, not a grep-checkable fact."
---

# Phase 123: Test-Infra Unblock Verification Report

**Phase Goal:** The backend pytest suite either runs to completion or has a documented, scoped isolation workaround, so every later fix phase can produce `fixed+verified` evidence; the fix stays narrow and does not expand into full test-suite archaeology.
**Verified:** 2026-07-26T20:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 (SC-1) | A full pytest run on a clean DB completes without hanging — the f438ced2 fix structurally resolved or a documented per-module workaround exists | ✓ VERIFIED | `pytest-full-run-2026-07-26.log` tail: `4 failed, 3058 passed, 8 skipped, 1 error in 894.00s (0:14:53)`; `grep -c "Failed: Timeout >180.0s"` → 0 (independently re-run); header shows `collected 3071 items`, `plugins: timeout-2.4.0,...`, `timeout: 180.0s` |
| 2 (SC-2) | The fix's file footprint is limited to fixture/test-config scope — timebox held | ✓ VERIFIED | Independently re-ran the D-123-11 gate: `git diff --name-only b88eb2ee..HEAD` filtered against allowlist (`apps/backend/tests/`, `apps/backend/pyproject.toml`, `.planning/`) → empty. Green-washing scan (added skip/xfail/deselect lines) independently re-run → empty. Dependency-drift check (`uv.lock`/`package.json`/`pnpm-lock.yaml`) → empty. `apps/backend/pyproject.toml` diff → empty (unchanged) |
| 3 (SC-3) | `test_freeze_race`, F821, `test_alembic_clean` each have their own registry row with a terminal disposition | ✓ VERIFIED | Registry rows V41-HYG-075 (`deferred:accepted-risk`), V41-HYG-074 (`fixed+verified`), V41-HYG-076 (`fixed+verified`, did-not-reproduce) read directly from `.planning/audits/v4.1-DEFECT-REGISTRY.md` |
| 4 (SC-4) | The registry row(s) cross-reference whether the pre-existing f438ced2 fix already satisfies TEST-01 | ✓ VERIFIED | V41-HYG-073 evidence cell cites `commit f438ced2` AND `.planning/audits/v4.1-TEST-RUNS/pytest-full-run-2026-07-26-SUMMARY.md`; disposition `fixed+verified` |
| 5 | Full-suite log exists with terminal tally line proving the suite reached the end (TEST-01, D-123-05) | ✓ VERIFIED | Same as #1 |
| 6 | Zero `Failed: Timeout >180.0s` lock-family entries | ✓ VERIFIED | `grep -c` → 0 (independently re-run) |
| 7 | SUMMARY.md records phase_start_sha, exact DB-reset commands, exact pytest invocation, tally, wall-clock (D-123-07) | ✓ VERIFIED | Read `pytest-full-run-2026-07-26-SUMMARY.md` directly — all 5 elements present verbatim |
| 8 | Every FAILED/ERROR node ID from the full run appears in the isolation log, classified deterministic vs full-suite-only (D-123-06) | ✓ VERIFIED | All 5 node IDs (`test_create_booking_pt_package_expired_before_slot_moscow_tz`, `test_concurrent_freeze_race...`, `test_locked_audit_events_count...`, `test_every_protected_route_declares_a_gate`, `test_self_checkin_happy_path`) present in `residuals-isolation-2026-07-26.log` and the SUMMARY's per-residual table |
| 9 | Exactly one full-suite run spent; all subsequent invocations are targeted node-ID subsets (D-123-06) | ✓ VERIFIED | SUMMARY §5/§6 shows one full invocation + 3 targeted/alone invocations; no second unnarrowed `uv run pytest` anywhere in the log files |
| 10 | Demo DB re-seeded after the suite (seed_demo_data + seed_dev_client exit 0) | ✓ VERIFIED | SUMMARY §7 records both commands + exit 0; independently confirmed live: `SELECT count(*) FROM users` → 1 (non-empty) against the still-running docker-compose stack |
| 11 | `uv run ruff check . --select F821` reports zero errors; before/after archived | ✓ VERIFIED | Independently re-ran `ruff check . --select F821` in `apps/backend` → `All checks passed!`; `ruff-f821-before-2026-07-26.txt` shows 5 findings, `ruff-f821-after-2026-07-26.txt` shows 0 |
| 12 | Every FAILED/ERROR node ID has exactly one registry row with a terminal disposition (TEST-02) | ✓ VERIFIED | 8 rows (V41-HYG-073..080), each with disposition `fixed+verified`/`deferred:accepted-risk`/`open`, covering all 5 residuals + TEST-01 row + 2 roadmap-named additions (test_alembic_clean, and the new bookings finding) |
| 13 | Registry `## FUNC`/`## HYGIENE`/`## INFRA` tables byte-identical to frozen state up to `## Discovered during fix` header | ✓ VERIFIED | Independently diffed `git show f02f9c68:...` prefix vs current file prefix → `PREFIX IDENTICAL` (empty diff) |
| 14 | New rows use 11-column schema, category HYGIENE, id continuing V41-HYG-NNN sequence past freeze-time max (072) | ✓ VERIFIED | Rows V41-HYG-073 through 080 read directly — all 11 columns present, category `HYGIENE` on every row, ids sequential and > 072 |

**Score:** 14/14 truths verified (0 present, behavior-unverified)

**Backstop (judgment) truths — routed to human verification, not counted toward the score above:**

- "f438ced2 holds as a general property of the suite" (123-01, backstop)
- "the residual set is complete and honest" (123-01, backstop)
- "each deferred row received the honest reason category" (123-02, backstop)
- "each row's repro/reason cell truthfully states known-pre-freeze" (123-02, backstop)

Per the honest-verifier protocol these four items cannot be resolved by presence/grep checks alone; strong supporting mechanical evidence was gathered for each (documented in the `human_verification` frontmatter above) but the verdict itself is deferred to human judgment, not silently passed.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/audits/v4.1-TEST-RUNS/pytest-full-run-2026-07-26.log` | Raw full-suite output | ✓ VERIFIED | 131,899 bytes, terminal summary line present, `collected 3071 items` |
| `.planning/audits/v4.1-TEST-RUNS/pytest-full-run-2026-07-26-SUMMARY.md` | phase_start_sha, exact commands, tally, wall-clock | ✓ VERIFIED | 9,497 bytes, all required fields present verbatim |
| `.planning/audits/v4.1-TEST-RUNS/residuals-isolation-2026-07-26.log` | Per-residual isolated re-run outcomes | ✓ VERIFIED | 93,934 bytes, all 5 residuals + 2 post-fix re-run entries present |
| `.planning/audits/v4.1-TEST-RUNS/ruff-f821-before-2026-07-26.txt` | Pre-fix F821 findings | ✓ VERIFIED | 5 findings recorded, matches measured set (3 `Any` + 2 `UUID`) |
| `.planning/audits/v4.1-TEST-RUNS/ruff-f821-after-2026-07-26.txt` | Post-fix zero-findings | ✓ VERIFIED | "All checks passed!" |
| `apps/backend/tests/messaging/test_attachment_idor.py` | `from typing import Any` added | ✓ VERIFIED | Line 18, confirmed via grep and live ruff run |
| `apps/backend/tests/modules/client_portal/test_client_me_service.py` | `from uuid import UUID, uuid4` widened | ✓ VERIFIED | Line 21, single import line (not duplicated) |
| `.planning/audits/v4.1-DEFECT-REGISTRY.md` | 8 terminal-disposition rows appended under `## Discovered during fix` | ✓ VERIFIED | V41-HYG-073..080, 11 columns each, frozen prefix byte-identical |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pytest-full-run-2026-07-26.log` | `residuals-isolation-2026-07-26.log` | every FAILED/ERROR node ID re-run and recorded | ✓ WIRED | All 5 node IDs cross-checked present in both files |
| `pytest-full-run-2026-07-26-SUMMARY.md` | `v4.1-DEFECT-REGISTRY.md` | phase_start_sha and residual tally consumed by registry rows | ✓ WIRED | Row V41-HYG-073 cites the SUMMARY path directly; footprint gate reads phase_start_sha from the SUMMARY (confirmed in 123-02-SUMMARY.md's SC-2 Evidence section and independently re-derived) |
| `v4.1-DEFECT-REGISTRY.md` | `v4.1-TEST-RUNS/` | every appended row's evidence cell points at a real archived artifact | ✓ WIRED | All `.planning/audits/v4.1-TEST-RUNS/...` paths extracted from evidence cells and confirmed to exist on disk (5/5 unique paths found) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite reaches terminal summary (no hang) | `tail` + `grep -c "Failed: Timeout >180.0s"` on archived log | 0 matches, terminal line present | ✓ PASS |
| F821 clean on live tree | `cd apps/backend && uv run ruff check . --select F821` | `All checks passed!` | ✓ PASS |
| Fixed booking test passes | `uv run pytest tests/integration/bookings/test_bookings_create.py::test_create_booking_pt_package_expired_before_slot_moscow_tz -q` | `1 passed in 0.36s` | ✓ PASS |
| Footprint gate reproduces green | `git diff --name-only b88eb2ee..HEAD \| grep -vE allowlist` | empty | ✓ PASS |
| Frozen registry prefix intact | diff of `git show f02f9c68:...` prefix vs current | empty (byte-identical) | ✓ PASS |
| Demo DB usable post-run | `SELECT count(*) FROM users` against live docker-compose postgres | `1` | ✓ PASS |
| Green-washing scan (no new skip/xfail/deselect) | `git diff -U0 b88eb2ee..HEAD -- 'apps/backend/tests/**' \| grep added-lines skip/xfail/deselect` | empty | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TEST-01 | 123-01, 123-02 | Fresh full pytest run confirms f438ced2 isolation-deadlock fix still holds | ✓ SATISFIED | Full run reached terminal summary, 0 lock-family timeouts, D-123-09 verdict NOT REGRESSED, registry row V41-HYG-073 `fixed+verified` citing f438ced2 |
| TEST-02 | 123-02 | Residual failures re-checked and entered as separate registry rows with terminal dispositions | ✓ SATISFIED | 8 registry rows, all with terminal disposition (`fixed+verified`/`deferred:accepted-risk`/`open`→124), no bare carried-forward prose |

No orphaned requirements: `.planning/REQUIREMENTS.md` maps only TEST-01 and TEST-02 to Phase 123, both marked `Complete` in the traceability table, both accounted for in the plans' `requirements` frontmatter.

### Anti-Patterns Found

No TBD/FIXME/XXX/HACK/PLACEHOLDER markers found in any of the 3 files modified this phase (`test_attachment_idor.py`, `test_client_me_service.py`, `test_bookings_create.py`). No skip/xfail/deselect markers added (independently re-verified). Code review (`123-REVIEW.md`, standard depth, 3 files) reports 0 critical, 0 warning, 3 info-level pre-existing/out-of-scope items — none introduced by this phase.

### Human Verification Required

See the four backstop-truth items in the frontmatter `human_verification` list above. All four are `verification: backstop` items explicitly authored into the plans' must_haves as judgment-shaped claims that no mechanical check can fully resolve (the general durability of the f438ced2 fix beyond one run; the honesty of "nothing was suppressed"; the honesty of each deferred row's reason category; the honesty of the known-pre-freeze framing). Strong corroborating mechanical evidence was gathered for each during this verification pass and is documented per-item above — none of the four is a bare assertion, but each still requires a human sign-off per the plan's own design.

### Gaps Summary

No gaps found. All 14 mechanically-checkable must-haves (roadmap Success Criteria 1-4 plus plan-level truths from both 123-01 and 123-02) verified directly against the codebase — evidence files, registry rows, live ruff/pytest re-runs, and git diffs were independently reproduced during this verification rather than trusted from SUMMARY prose. The only open items are the four backstop/judgment truths the plans themselves flagged as requiring human sign-off; these do not indicate missing or stub work — they indicate claims (generalization beyond one run, and honesty-of-labeling) that are inherently outside mechanical verification's reach.

---

_Verified: 2026-07-26T20:15:00Z_
_Verifier: Claude (gsd-verifier)_
