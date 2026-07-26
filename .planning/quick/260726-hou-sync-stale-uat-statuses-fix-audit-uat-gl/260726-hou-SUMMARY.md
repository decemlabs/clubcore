---
status: complete
quick_id: 260726-hou
date: 2026-07-26
branch: fix/260726-hou-uat-audit-fixes
commits:
  - b8402433 — fix: audit-uat false All Clear after milestone archival (+ tracked patch)
  - 2e81c7a9 — test(94): pin the ChatScreen typing-indicator consumer path
  - 299de980 — docs: reconcile stale UAT statuses against recorded evidence
---

# Quick Task 260726-hou — Summary

## Task 1 — audit-uat's false All Clear — FIXED

`gsd-tools query audit-uat` scanned only `.planning/phases/*`. Every milestone through
v4.0 is archived, so that directory is empty and the command answered
`total_items: 0` — a false All Clear over 166 real items in 35 files across 26 phases
(84 audit files in 64 archived phase dirs).

- `--include-archived` extends the scan to `.planning/milestones/<ver>-phases/*`.
  Archived phases bypass `getMilestonePhaseFilter` on purpose: that filter scopes to
  the CURRENT milestone and so excludes every archived phase by construction.
- results carry `milestone` + `archived`; summary always reports
  `archived_phase_dirs` / `archived_files_unscanned`, so a `0` can no longer be read
  as "nothing outstanding anywhere"
- the flag is parsed in `routeAuditUat` and passed as options — `raw` is the
  output-format boolean, not an argv bag (the first attempt got this wrong)
- a `resolved` PREFIX now counts as resolved in Gaps/Deferred entries. Exact equality
  rejected the convention actually in use — `status: RESOLVED (debug session …,
  2026-06-01) — … Was: failed` — which kept closed gaps reported open forever.
  `unresolved` still reads as open.
- `workflows/audit-uat.md`: only claim All Clear when the archive was scanned or empty

Default behaviour unchanged and additive; no gate predicate consumes `audit-uat` and
`cmdAuditUat` has no other caller. Verified: bare call returns the prior result plus
the new fields; `--include-archived` surfaces the archive.

**Durability caveat:** `.claude/` is gitignored, so the runtime edit is not under
version control. The tracked deliverable is `gsd-core-audit-uat.patch` — a real
unified diff against pristine `@opengsd/gsd-core@1.8.0` (fetched via `npm pack` to
produce it). Re-apply with `/gsd-reapply-patches` after `/gsd-update`. The patch also
carries one PRE-EXISTING local delta (`/gsd:verify-work` → `/gsd-verify-work`).

## Task 2 — Stale UAT statuses — RECONCILED (166 → 105 items)

Eleven VERIFICATION files declared `status: human_needed` while a companion
`*-HUMAN-UAT.md` / `*-UAT.md` or a root-level browser audit recorded the run as done.
Every status was set FROM the recorded evidence and cites its evidence file.

| Phase | Action | Evidence |
|-------|--------|----------|
| 999.3 | → passed | 999.3-HUMAN-UAT 3/3 |
| 999.4 | → passed | 999.4-UAT 8/8; its HUMAN-UAT blocker (checkout amount 100× too small) verified fixed at HEAD |
| 999.5 | → passed | 999.5-HUMAN-UAT 15/15 + 999.5-UAT 14/14 |
| 86 / 87 / 88 | → passed | 2/2, 4/4, 2/2 |
| 101 / 103 / 104 | → passed | v3.0-UAT-BROWSER-AUDIT + v3.0-UAT-VERIFICATION-PASS (live, owner + reception) |
| 94 | stays human_needed, trimmed to 3 real remainders | 94-HUMAN-UAT 2/3 |
| 102 | stays human_needed for the BROWSER legs only | v3.1 Phase 110 closed the API/RBAC half live |

The 999.4 blocker was checked against code before being marked resolved, not taken on
faith: `App.jsx:340` now passes `plan.priceKopecks` (was `priceTotal`, rubles) and
`PlansSheet` exposes both scales, so `CheckoutSheet`'s kopeck-based `formatMoney` and
the server's `newAmountKopecks` finally agree.

Phase 102 is the subtler case: v3.1 Phase 110 ("Live Verification — Deferred P102")
closed the booking lifecycle, the slot-race 409, payroll kopecks math, reception 403
on all 4 payroll endpoints, and the repeatable seed path — but over HTTP and pytest,
never through the admin UI. Only the browser legs remain.

## Task 3 — Bugs

**REV-01 — NOT a bug; the audit mis-triaged it.** `v3.0-UAT-VERIFICATION-PASS.md`
carries a RESOLVED annotation beneath the finding (2026-06-14, quick `260614-jt7`,
variant B: `GET /users` surfaces `invitationTokenId`; live-verified invite → revoke →
204 → row gone). The audit's grep caught only the finding line. Corrected in the docs
commit.

**Chat typing indicator — consumer path proven correct, symptom still open.** Added
`ChatScreen.typing.test.jsx` (5/5 green): the `window.__chatTyping` bridge installs,
dots and «печатает…» render in the open thread, the 5s dismiss fires, and the WR-06
ownership guard restores the previous handler on unmount. So the standing
"renders correctly but never reaches the DOM" report is NOT the component's render
logic. Likeliest cause: the original console probe REPLACED `window.__chatTyping` with
its own counting wrapper — which suppresses the real handler while still reporting
`handlerCalls=1` — or a stale service worker.

Deliberately NOT claimed as fixed. It is unreachable in production regardless: no
typing PRODUCER exists (Telegram has no typing API; the staff frontend never got one
because v2.6 became Referral System). Recorded as open in `94-VERIFICATION.md` and
restored to `STATE.md`.

An honest note on process: the first repro appeared to reproduce the bug (3 tests
red), but that was the harness — the conv card opens on a pointerdown→pointerup TAP
with the pointerup listener on `document` (a 450ms long-press opens the mute sheet),
so a plain `click` does nothing. Wrong gesture, convincing false repro.

**seaweedfs-s3 CrashLoop — documented as open.** Not reproducible without a live
cluster; not blind-patched.

## Ledger repair

Four items were tracked at v2.5 close and silently dropped when that block was pruned
(v2.6 was expected to carry them and became Referral System instead). Restored to
`STATE.md ## Deferred Items`: the typing indicator, the RCPT-02 typing producer, the
seaweedfs-s3 CrashLoop, and 6 unresolved `test_sell_*` online-payment tests that
assert absolute row counts against an unscoped `select(OnlinePayment)`.

## Out of scope (unchanged)

The 27 v4.0 operator-pending items (118–121) and the 2 HARD gates — SEC-02 RSA-key
off-node backup, BAK-03 verified restore round-trip. That is the deliberate
`D-V40-LOCAL-VALIDATE` boundary awaiting a real k3s toolchain, not forgotten debt.

## Verification

- `apps/client`: 22 test files / 142 tests green (`npx vitest run src/screens/`)
- `node --check` clean on both patched gsd-core modules
- `audit-uat` bare → unchanged results + new summary fields;
  `--include-archived` → 105 items, `archived_files_unscanned: 0`
- 166 → 105 items with nothing genuinely open removed
