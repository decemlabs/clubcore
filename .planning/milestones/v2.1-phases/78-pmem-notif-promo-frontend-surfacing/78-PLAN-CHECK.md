# Plan Check: Phase 78 — PMEM/NOTIF/PROMO Frontend Surfacing

**Checker:** gsd-plan-checker (Revision Gate)
**Date:** 2026-06-02
**Plans checked:** 78-01, 78-02, 78-03
**Verdict:** PASS

---

## Verification Summary

| Dimension | Status | Notes |
|-----------|--------|-------|
| 1 — Requirement Coverage | PASS | PMEM-01, NOTIF-01, PROMO-01 each covered by exactly one plan |
| 2 — Task Completeness | PASS | All tasks have read_first + action + verify (automated) + acceptance_criteria + done |
| 3 — Dependency Correctness | PASS | All 3 plans wave=1 depends_on=[] — valid parallel wave |
| 4 — Key Links Planned | PASS | All key_links wired in task actions |
| 5 — Scope Sanity | PASS | 78-01: 2 tasks; 78-02: 3 tasks; 78-03: 1+1 tasks; all within budget |
| 6 — Verification Derivation | PASS | Truths are user-observable; artifacts map to truths; key_links present |
| 7 — Context Compliance (D-78-01..10) | PASS | All 10 locked decisions implemented; no deferred ideas included |
| 7b — Scope Reduction | PASS | No "v1/static/placeholder" language; autoRenew null-hide is D-78-02 faithful |
| 7c — Architectural Tier Compliance | SKIPPED | No RESEARCH.md / Architectural Responsibility Map for this phase |
| 8 — Nyquist Compliance | SKIPPED | No VALIDATION.md in phase directory (phase has no RESEARCH.md; Nyquist not applicable) |
| 9 — Cross-Plan Data Contracts | PASS | clientQueries.ts touched only by 78-02; no shared data pipelines between plans |
| 10 — CLAUDE.md Compliance | PASS | No violations (pnpm, Vitest, formatMoney, no Sonner, no global toast) |
| 11 — Research Resolution | SKIPPED | No RESEARCH.md for this phase |
| 12 — Pattern Compliance | SKIPPED | No PATTERNS.md for this phase |

**Result: All 3 success criteria will be TRUE if plans execute as written.**

---

## Requirement Coverage

| Requirement ID | Plan | Tasks | User-observable truth |
|----------------|------|-------|----------------------|
| PMEM-01 | 78-01 | Task 1 (render), Task 2 (tests + identity repair) | Profile shows priceKopecks via formatMoney; auto-renew hidden when null |
| NOTIF-01 | 78-02 | Task 1 (type), Task 2 (rewire), Task 3 (tests) | Settings toggles PATCH /client/me, persist after reload, hydrate from server |
| PROMO-01 | 78-03 | Task 1 (flag flip), checkpoint:human-verify | FIT15 chip surfaces in checkout, one-tap apply, discount shown |

All 3 requirement IDs are present in their respective plans' `requirements` frontmatter fields.

---

## Detailed Findings by Plan

### 78-01 (PMEM-01 — Profile membership price + auto-renew)

**SC1 traceability:**
- Task 1 wires `useClientMembership()` into ProfileScreen.jsx with `formatMoney(membership.priceKopecks)` and the null guard on auto-renew. The `<interfaces>` section documents the exact line numbers and the pre-existing `formatMoney` import at line 7. The hook is confirmed to be exported from `@/data` (verified: `apps/client-pwa/src/data/index.js` line 26).
- Task 2 adds `ProfileScreen.membership.test.jsx` and repairs the identity test mock — the concrete risk (identity test throws "useClientMembership is not a function" after the hook is added) is called out and mitigated in both the `<context>` interfaces block and the task action.

**Identity test repair — confirmed necessary and planned:**
- The existing `ProfileScreen.identity.test.jsx` mock at line 20-26 does NOT include `useClientMembership`. Once Task 1 adds the hook to ProfileScreen.jsx, Task 2 MUST add it to the mock object or tests throw. The plan explicitly handles this in Task 2's action and acceptance_criteria (`grep` assertion that `useClientMembership` appears in the mock block).

**Acceptance criteria quality:** Objective and grep-verifiable (no subjective language). The NBSP/regex note for formatMoney output is correct — the ru-RU RUB formatter produces non-breaking spaces.

**Threat model:** No high-severity threats; both T-78-01 and T-78-02 are correctly accepted (IDOR-safe read, own-data only).

**No issues.**

---

### 78-02 (NOTIF-01 — Settings toggles server-backed)

**SC2 traceability:**
- Task 1 extends the `useUpdateClientProfile` payload type in `clientQueries.ts` to include `notifPrefs`. Verified: the current type (lines 220-227) does NOT include `notifPrefs`; Task 1 adds it.
- Task 2 rewires SettingsScreen.jsx: drops `NOTIF_STORAGE_KEY` + localStorage, hydrates from `useClientMe().notifPrefs`, optimistic flip, full 4-key PATCH, revert-on-error toast. The ProfileExtraSheets local-toast pattern (no global Sonner) is correctly cited as the analog.
- Task 3 provides Vitest coverage for hydration, optimistic flip, full-replace mutation call shape, and revert.

**D-78-08 (full reload persistence) coverage:** Task 2 action includes a `useEffect` to reset local state from server value on arrival, which is the mechanism that makes the toggle survive a full reload (server round-trip, not localStorage). The must_haves truth explicitly covers this.

**The `files_modified` list does NOT include `clientQueries.ts`** in the frontmatter.

Wait — checking the frontmatter:
```
files_modified:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/SettingsScreen.jsx
  - apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx
```
`clientQueries.ts` IS listed. Confirmed. No issue.

**File overlap check:** 78-01 touches ProfileScreen.jsx and ProfileScreen tests. 78-02 touches clientQueries.ts, SettingsScreen.jsx, and SettingsScreen tests. 78-03 touches only CheckoutSheet.jsx. Zero overlap — safe for parallel wave 1.

**Threat model:** T-78-03 (extra=forbid on backend) and T-78-04 (principal scoping) are correctly handled. T-78-05 notes localStorage surface reduction — accurate.

**No issues.**

---

### 78-03 (PROMO-01 — FIT15 chip flag flip)

**SC3 traceability:**
- Task 1 flips `CHECKOUT_FEATURE_FLAGS.recommendedPromo` from `false` to `true` at line 46. Verified: the flag, chip JSX, `!promoResult` gate, and `handlePromoApply(RECOMMENDED_PROMO.code)` onClick ALL exist in the current file (confirmed by codebase inspection).
- The chip is at lines 451-465, inside the single `CheckoutSheet` component. Since `ctx.kind` is passed from the caller (PlansSheet passes `kind: 'sub'` or `kind: 'pt'`), flipping the flag surfaces the chip in BOTH contexts via the same component — no separate sub/PT component paths to wire.
- `handlePromoApply` typeof guard (line 164: `typeof codeArg === 'string' ? codeArg : promoCode`) correctly handles the chip's `onClick={() => handlePromoApply(RECOMMENDED_PROMO.code)}` string argument.

**Human-verify checkpoint assessment:** The plan uses `autonomous: false` and includes a `checkpoint:human-verify` task. This is the correct verification approach given:
1. No automated test harness exists for CheckoutSheet (noted in the plan check prompt).
2. The plan makes exactly one line change (a flag flip in an object literal).
3. The risk is revealing already-built UI, not introducing new logic.
4. The human-verify steps are concrete and unambiguous (steps 1-5, exact toast text, chip visibility, both sub + PT contexts).
This is NOT a hidden gap — it is an appropriate verification strategy for a flag-flip change where the exercised code paths (handlePromoApply, promoValidate) already exist and the only new behavior is the chip becoming visible.

**Acceptance criteria:** All grep-verifiable (`grep -c "recommendedPromo: *true"` with whitespace note, clubBonuses unchanged). The `pnpm build` in the verify block catches any import/parse issues from the edit.

**Threat model:** T-78-06 (server-authoritative discount, no client price computation) and T-78-07 (server-side code validation) are correctly accepted.

**No issues.**

---

## Independence Check (Wave 1 Parallel)

| File | Touched by |
|------|-----------|
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | 78-01 only |
| `apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx` | 78-01 only |
| `apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx` | 78-01 only (new) |
| `apps/client-pwa/src/lib/clientQueries.ts` | 78-02 only |
| `apps/client-pwa/src/screens/SettingsScreen.jsx` | 78-02 only |
| `apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx` | 78-02 only (new) |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | 78-03 only |

Zero file overlap. All three plans are safely parallelizable in wave 1.

---

## Context Compliance (D-78-01..D-78-10)

| Decision | Implementing Task | Status |
|----------|-------------------|--------|
| D-78-01: useClientMembership + formatMoney in .membership-hero | 78-01 Task 1 | Covered |
| D-78-02: auto-renew HIDDEN when null (no "—") | 78-01 Task 1 action + acceptance_criteria | Covered |
| D-78-03: no skeleton/placeholder when absent | 78-01 Task 1 action (guard: priceKopecks > 0) | Covered |
| D-78-04: hydrate from useClientMe().notifPrefs | 78-02 Task 2 action | Covered |
| D-78-05: DROP NOTIF_STORAGE_KEY localStorage | 78-02 Task 2 action + acceptance_criteria (grep returns 0) | Covered |
| D-78-06: full 4-key replace on PATCH | 78-02 Task 2 action + Task 3 assertion | Covered |
| D-78-07: notifPrefs added to payload type | 78-02 Task 1 | Covered |
| D-78-08: persistence survives full reload | 78-02 Task 2 action (useEffect re-sync from server) | Covered |
| D-78-09: flip recommendedPromo to true | 78-03 Task 1 | Covered |
| D-78-10: !promoResult gate preserved; verify both contexts | 78-03 Task 1 (read_first gate check) + checkpoint:human-verify steps 2+5 | Covered |

All deferred ideas (autopay, promo admin CRUD, config-controlled flag) are absent from all plans. No scope creep detected.

---

## CLAUDE.md Compliance Notes

- All verify blocks use `pnpm exec` (pnpm workspace convention).
- Test runner is Vitest (`pnpm exec vitest run`) — correct per CLAUDE.md.
- `formatMoney` is the project's kopecks formatter — used correctly.
- No Sonner (no global toast in PWA); plans mirror the local inline co-toast pattern from ProfileExtraSheets — correct.
- No raw Tailwind palette classes introduced (plans reuse existing hero tokens).
- TypeScript strict mode: `tsc -b --noEmit` is in every plan's verify block.

---

## Overall Verdict

**PASS — proceed to execution.**

All 3 ROADMAP success criteria are reachable from the plans as written:

- **SC1 (PMEM-01):** 78-01 Task 1 renders priceKopecks via formatMoney and hides auto-renew when null; Task 2 provides test coverage and repairs the identity mock. The hook is available in the @/data barrel.
- **SC2 (NOTIF-01):** 78-02 Task 1 adds the type field; Task 2 drops localStorage and wires optimistic PATCH with full 4-key replace + useEffect server re-sync; Task 3 covers all mutation behaviors.
- **SC3 (PROMO-01):** 78-03 Task 1 flips one flag; the chip, handler, gate, and both checkout contexts are pre-built and confirmed present in the codebase. Human-verify checkpoint is the correct gate for a single-line flag flip.

No blockers. No warnings.

---

*Plan check completed: 2026-06-02*
