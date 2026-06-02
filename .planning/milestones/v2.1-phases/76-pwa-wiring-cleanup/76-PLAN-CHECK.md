# Phase 76 Plan Check — PWA Wiring + Cleanup

**Checked:** 2026-06-02
**Plans:** 76-01, 76-02, 76-03
**Requirements:** NHOME-01, NHOME-02, PDATA-01, PDATA-02, CLEAN-01
**Verdict:** PASS (with 1 WARNING)

---

## Overall Assessment

The three plans, executed in order (76-01 and 76-02 in Wave 1, 76-03 in Wave 2), will
collectively achieve all five phase success criteria. One warning is raised about a toast
implementation discrepancy between PATTERNS.md / Plan 76-02 and the actual codebase.
No blockers found.

---

## Dimension 1: Requirement Coverage

| Requirement | Covered By | Tasks | Status |
|-------------|-----------|-------|--------|
| NHOME-01 | 76-01 | Tasks 1, 2, 3 | COVERED |
| NHOME-02 | 76-01 | Tasks 2, 3 | COVERED |
| PDATA-01 | 76-02 | Task 1 | COVERED |
| PDATA-02 | 76-02 | Tasks 2, 3 | COVERED |
| CLEAN-01 | 76-03 | Tasks 1, 2, 3 | COVERED |

Result: PASS — all 5 requirement IDs present in plan frontmatter; each has concrete tasks.

---

## Dimension 2: Task Completeness

### Plan 76-01 (3 tasks)

| Task | type | read_first | action | verify/automated | acceptance_criteria | done |
|------|------|-----------|--------|------------------|---------------------|------|
| 1 | auto/tdd | YES | specific | YES (grep + tsc -b) | YES (4 criteria) | YES |
| 2 | auto | YES | specific | YES (grep + tsc -b) | YES (7 criteria) | YES |
| 3 | auto/tdd | YES | specific | YES (vitest run) | YES (4 criteria) | YES |

Result: PASS — all required fields present; actions are concrete and file-specific.

### Plan 76-02 (3 tasks)

| Task | type | read_first | action | verify/automated | acceptance_criteria | done |
|------|------|-----------|--------|------------------|---------------------|------|
| 1 | auto/tdd | YES | specific | YES (grep + tsc -b) | YES (5 criteria) | YES |
| 2 | auto/tdd | YES | specific | YES (grep enum check + tsc/build/lint) | YES (6 criteria) | YES |
| 3 | checkpoint:human-verify | N/A | YES (manual steps) | N/A | N/A | N/A |

Result: PASS — checkpoint task correctly has no automated verify; all auto tasks are complete.

### Plan 76-03 (3 tasks)

| Task | type | read_first | action | verify/automated | acceptance_criteria | done |
|------|------|-----------|--------|------------------|---------------------|------|
| 1 | auto | YES | specific | YES (grep + tsc -b) | YES (4 criteria) | YES |
| 2 | auto | YES | specific | YES (file check + grep + build) | YES (5 criteria) | YES |
| 3 | auto | YES | specific | YES (lint + vitest run) | YES (3 criteria) | YES |

Note: 76-03 Task 2's `<verify>` block uses HTML entity `&amp;&amp;` for `&&` in the command
string — this is XML-safe but the executor must be aware the shell command will work only if
the entity is decoded before execution (it will be, since the XML is parsed before being
handed to the shell).

Result: PASS

---

## Dimension 3: Dependency Correctness

```
76-01: wave 1, depends_on: []
76-02: wave 1, depends_on: []
76-03: wave 2, depends_on: ["76-01"]
```

- 76-01 and 76-02 are independent Wave 1 plans. They touch different files:
  76-01 modifies `clientQueries.ts`, `data/index.js`, `HomeScreen.jsx`, `HomeScreen.identity.test.jsx`.
  76-02 modifies only `ProfileExtraSheets.jsx`.
  No shared files in Wave 1 — true parallelism possible.

- 76-03 depends on 76-01 because both edit `data/index.js`. The serialization rationale is
  explicitly documented in the plan objective. This is correct — 76-03 must add the
  CONVERSATIONS removal to `data/index.js` after 76-01 has already added the
  `useClientTrainers` re-export to the same file.

- No cycles. No missing references. Wave arithmetic is consistent.

Result: PASS

---

## Dimension 4: Key Links Planned

### NHOME-01 wiring chain

```
HomeScreen.jsx → useClientTrainers() → GET /api/v1/client/trainers
```

- 76-01 Task 1 creates `useClientTrainers()` and its `@/data` re-export.
- 76-01 Task 2 calls `useClientTrainers()` inside `HomeNewbie` and renders the avatar strip.
- 76-01 Task 3 adds a test asserting the live initial ("О" from Олег, not "А" from static TRAINERS).

Chain is complete. Fallback (static TRAINERS) is wired via `STATIC_TRAINERS_FALLBACK` import.

### NHOME-02 wiring chain

```
HeroNewbie → useClientPlans() → GET /api/v1/client/plans → pluralPlan + formatMoney → .chip span
```

- `useClientPlans()` already exists; 76-01 Task 2 imports and calls it inside `HeroNewbie`.
- D-76-06 formula `Math.round(p.price_kopecks / (p.duration_days / 30))` is present in the
  action and in the acceptance_criteria grep check.
- `pluralPlan()` helper is specified precisely (Russian teen-number rule, 11-14 edge case).
- Chip renders only when `plans?.length > 0`; loading/error falls back to existing hardcoded
  layout (D-76-09). Wiring is complete.

### PDATA-01 wiring chain

```
PersonalDataSheet → useClientMe() → GET /client/me → useEffect hydration → field state
```

- 76-02 Task 1 imports `useClientMe`, replaces hardcoded initializers with empty state,
  adds `useEffect([meData])` to hydrate, derives `phone` read-only.
- Acceptance criteria greps confirm absence of 'Саша' / 'sasha@example.com'.

Chain is complete.

### PDATA-02 wiring chain

```
onSave → updateProfile.mutateAsync → PATCH /client/me → onSettled invalidates me()+home()
```

- 76-02 Task 2 wires `useUpdateClientProfile()` mutation, replaces the `setSaved(true)` no-op.
- `goal` is constrained to a 4-value enum via a segmented control (no free-text, avoiding the
  backend's HTTP 400 `invalid_goal`). This is the correct spec correction.
- Cache invalidation is built into `useUpdateClientProfile.onSettled` (already existing in
  `clientQueries.ts`; the plan does not need to add it separately).

Chain is complete.

### CLEAN-01 wiring chain

```
App.jsx: remove CONVERSATIONS import + unreadChat reduce → TabBar.unreadChat={0}
data/index.js: remove CONVERSATIONS re-export line 50 + comment line 7
data/conversations.js: deleted
```

- 76-03 Task 1 removes the import and reduce; passes literal 0 to TabBar.
- 76-03 Task 2 deletes the orphaned file and re-export.
- 76-03 Task 2 includes a pre-deletion re-confirmation grep (guarding against a surprise
  remaining importer), which is sound defensive practice.
- TRAINERS re-export at data/index.js line 55 is explicitly preserved.
- The newly added `useClientTrainers` re-export from 76-01 is also explicitly preserved.

Chain is complete.

Result: PASS

---

## Dimension 5: Scope Sanity

| Plan | Tasks | Files Modified | Wave | Notes |
|------|-------|---------------|------|-------|
| 76-01 | 3 | 4 | 1 | Within budget |
| 76-02 | 3 (1 checkpoint) | 1 | 1 | Single file, very tight scope |
| 76-03 | 3 | 3 (1 deletion) | 2 | Within budget |

Total: 9 tasks across 3 plans, 7 unique files touched (1 deleted).
No plan exceeds the 4-task warning threshold.

Result: PASS

---

## Dimension 6: Verification Derivation (must_haves)

### 76-01 must_haves

Truths are user-observable:
- "A newbie client on Home sees trainer avatars/initials from GET /client/trainers" ✓
- "The trainer overflow counter (+N) reflects the live trainer count" ✓
- "The plan info chip shows the live plan count and minimum normalized monthly price" ✓
- "On trainers fetch error/empty the avatar strip falls back to static placeholders" ✓
- "On plans fetch loading/error the existing hardcoded layout renders without crashing" ✓

Artifacts: `clientQueries.ts`, `data/index.js`, `HomeScreen.jsx` — all directly support the truths.
Key links: both hooks wired to their endpoints, pattern strings provided.

Result: PASS

### 76-02 must_haves

Truths are user-observable:
- "Opening the Personal Data sheet shows the client's real firstName, phone, and email" ✓
- "Editing name/email/goal/height/weight and tapping Сохранить calls PATCH /client/me" ✓
- "A saved change persists after a full page reload" ✓
- "On save failure an error toast is shown and fields keep their values" ✓
- "DOB and Gender are labelled 'Только на устройстве' and are not sent to the server" ✓

Result: PASS

### 76-03 must_haves

Truths are user-observable:
- "The chat unread-badge shows 0 / is hidden (TabBar receives unreadChat=0)" ✓
- "The CONVERSATIONS import is absent from App.jsx" ✓
- "The orphaned conversations mock is removed" ✓
- "The app still builds and the existing test suite still passes" ✓

Result: PASS

---

## Dimension 7: Context Compliance (CONTEXT.md Decisions)

All 16 locked decisions are traced:

| Decision | Plan | Task | Covered |
|----------|------|------|---------|
| D-76-01 useClientTrainers hook | 76-01 | Task 1 | YES |
| D-76-02 client-side avatar derivation (initials + palette) | 76-01 | Task 2 | YES |
| D-76-03 first 3 + (+N) overflow layout | 76-01 | Task 2 | YES |
| D-76-04 loading skeleton + error/empty fallback | 76-01 | Task 2 | YES |
| D-76-05 keep static TRAINERS mock file | 76-01 | Task 2 | YES (STATIC_TRAINERS_FALLBACK) |
| D-76-06 min(price_kopecks / (duration_days/30)) formula | 76-01 | Task 2 | YES |
| D-76-07 count = live plans.length | 76-01 | Task 2 | YES |
| D-76-08 formatMoney kopecks→₽ | 76-01 | Task 2 | YES |
| D-76-09 hardcoded fallback on loading/error | 76-01 | Task 2 | YES |
| D-76-10 read firstName/lastName/phone/email/goal/heightCm/weightKg from useClientMe | 76-02 | Task 1 | YES |
| D-76-11 DOB/Gender local-only, no backend persistence | 76-02 | Task 1 | YES |
| D-76-12 editable: firstName/email/goal/heightCm/weightKg; phone SMS-only; lastName read-only | 76-02 | Task 2 | YES |
| D-76-13 useUpdateClientProfile + invalidate + error toast | 76-02 | Tasks 2, 3 | YES |
| D-76-14 remove CONVERSATIONS import from App.jsx | 76-03 | Task 1 | YES |
| D-76-15 pass unreadChat={0} to TabBar | 76-03 | Task 1 | YES |
| D-76-16 delete conversations.js if orphaned (UPDATE: confirmed orphaned) | 76-03 | Task 2 | YES |

No deferred ideas from CONTEXT.md are implemented. No contradictions found.

Specific checks on the requested items:

**goal field (enum vs free text):** Plan 76-02 Task 2 action explicitly states "DO NOT use
a free-text FormRow" and replaces it with a segmented control over the 4 enum values
`{lose_weight, gain_mass, tone, maintain}` mapped to Russian labels. The verify grep
checks `grep -Eq "lose_weight|gain_mass|tone|maintain"` and `grep -q "isPending"`.
The acceptance criteria confirm "the four enum literals appear in the file and no free-text
FormRow binds to goal". This satisfies D-76-12 and the spec-correction note.

**Editable set (D-76-12):** firstName, email, goal, heightCm, weightKg — all present.
Phone: read-only (SMS verify flow). lastName: not in the editable set.

**lastName in UI:** The plan action reads firstName from meData and shows it as "Имя"
(first name only). lastName is not shown as a writable field. The plan does not explicitly
show lastName in a read-only display row, which is a minor omission but the original sheet
only had "Имя" (not a separate lastName row), so no regression occurs.

Result: PASS

---

## Dimension 7b: Scope Reduction Detection

No scope-reduction language ("v1", "static for now", "future enhancement", "hardcoded")
appears as a substitute for a decision's full scope.

The "static zero unreadChat" in CLEAN-01 is correct per D-76-15 (not a reduction — this IS
the full decision).

The "existing hardcoded fallback on loading/error" for the plan chip is correct per D-76-09.

Result: PASS — no reductions detected.

---

## Dimension 7c: Architectural Tier Compliance

No RESEARCH.md exists for Phase 76 (pure-frontend wiring phase). Skipped.

Result: SKIPPED (no RESEARCH.md)

---

## Dimension 8: Nyquist Compliance

No RESEARCH.md exists for Phase 76, no "Validation Architecture" section present.

Result: SKIPPED (not applicable — no validation architecture defined for pure-frontend wiring)

---

## Dimension 9: Cross-Plan Data Contracts

The only shared file between plans is `apps/client-pwa/src/data/index.js`:
- 76-01 Task 1 ADDS `useClientTrainers` export to the file.
- 76-03 Task 2 REMOVES `CONVERSATIONS` export and its comment.

These are additive and subtractive changes on different lines and different exports.
76-03 runs in Wave 2 (after 76-01); its action explicitly warns "Do NOT remove the
useClientTrainers export added by Plan 76-01". The acceptance criteria verify both
`useClientTrainers` and `TRAINERS` survive the cleanup.

No conflicting data transformations on shared data entities.

Result: PASS

---

## Dimension 10: CLAUDE.md Compliance

CLAUDE.md constraints checked:

- **pnpm (not npm/yarn):** All verify commands use `pnpm exec vitest run` and `pnpm exec tsc -b` and `pnpm build` and `pnpm lint`. PASS.
- **No backend changes:** All three plans are pure frontend. No `apps/backend/` files listed. PASS.
- **apps/admin-web untouched:** Not referenced. PASS.
- **No new npm packages:** UI-SPEC §Registry Safety confirms no new packages. PASS.
- **TypeScript strict:** Plan 76-01 keeps the `(res as { data: unknown[] }).data` cast pattern (no new interfaces, no TypeScript relaxation). Plan 76-02 imports from typed clientQueries.ts interfaces. PASS.
- **Frontend integrity (no mock rewrites):** The TRAINERS mock file (`data/trainers.js`) is preserved per D-76-05. The `data/conversations.js` deletion is explicitly confirmed orphaned. PASS.

Result: PASS

---

## Dimension 11: Research Resolution

No RESEARCH.md for Phase 76 (pure-frontend wiring; no backend unknowns).

Result: SKIPPED (no RESEARCH.md)

---

## Dimension 12: Pattern Compliance

PATTERNS.md exists and was read. All four file classifications have strong analogs:

| File | Analog | Plan References Analog |
|------|--------|----------------------|
| clientQueries.ts | useClientPlans() lines 307-317 | 76-01 Task 1 read_first + action cite it explicitly |
| HomeScreen.jsx | existing useClientHome/useClientMe consumption | 76-01 Task 2 read_first cites PATTERNS §2a/§2b |
| ProfileExtraSheets.jsx | CheckoutSheet.jsx mutation+toast | 76-02 Tasks 1+2 read_first cite PATTERNS §3 |
| App.jsx | self (line removal) | 76-03 Task 1 read_first cites PATTERNS §4 |

Shared patterns:
- Query hook shape: cited in 76-01 Task 1.
- Mutation with isPending: cited in 76-02 Task 2.
- Money formatting: cited in 76-01 Task 2 (formatMoney).
- @/data swap seam: cited in 76-01 Task 1.
- In-screen error toast: cited in 76-02 Task 2.

Result: PASS

---

## Warning

**W-76-01 [WARNING] — pattern_compliance / toast_implementation**

Plan 76-02 Task 2 and PATTERNS.md §3 both state "there is NO shared `.co-toast` class outside
CheckoutSheet" and instruct the executor to use inline styles with `var(--danger)`. This is
incorrect. The `.co-toast`, `.co-toast.show`, `.co-toast-ic`, and `.co-toast-tx` CSS classes
are defined globally in `apps/client-pwa/src/styles.css` lines 1997-2043, not in
CheckoutSheet's own CSS. The executor CAN use the `.co-toast` class system directly in
ProfileExtraSheets without any inline-styles workaround.

The discrepancy does not block execution — the plan's instruction to use inline styles will
produce a working toast (the behavioral contract is correct). However the executor will
produce lower-quality code than necessary (inline styles vs. the available CSS primitive).

Additionally, the `.co-toast-ic` icon uses `var(--accent)` background (green), while UI-SPEC
§Copywriting specifies "Sonner toast, `var(--danger)` icon". The executor should use
`var(--danger)` / `var(--danger-soft)` for the error toast icon, not `var(--accent)`. This
requires a custom element even if `.co-toast` is reused for layout, since the icon color in
the CSS class is accent (not danger).

Fix hint: The executor should reuse the `.co-toast` + `.co-toast.show` classes for layout
and animation, but override the icon background with `var(--danger)` / `var(--danger-soft)`
inline. Alternatively, the inline-styles approach from the plan action is acceptable.
Either way, the behavioral contract (toast appears on error, vanishes after ~2.6s) is met.

```yaml
issue:
  plan: "76-02"
  dimension: "pattern_compliance"
  severity: "warning"
  description: ".co-toast CSS class exists globally in styles.css; plan incorrectly states it is CheckoutSheet-only. Plan instruction to use inline styles is functional but suboptimal. Icon color must be var(--danger), not var(--accent)."
  task: 2
  fix_hint: "Executor may use .co-toast for layout; use inline override for icon color (var(--danger)/var(--danger-soft)) to match UI-SPEC §Copywriting."
```

---

## Special Check: Goal Field as Enum-Gated Select

The plan explicitly documents: "CONSTRAINT — `goal` is a SERVER-ENFORCED 4-value enum".
Plan 76-02 Task 2 action:
- Replaces the Цель FormRow with a segmented/select control over `{lose_weight, gain_mass, tone, maintain}`.
- Maps to Russian labels: lose_weight→«Похудение», gain_mass→«Набор массы», tone→«Тонус», maintain→«Поддержание формы».
- Styled like the existing «Пол» `.seg`/`.seg-item` segmented control.
- The `goal` state holds the enum value; the label is display-only.
- Acceptance criteria verify the four enum literals appear and no free-text FormRow binds to goal.

The PATTERNS.md §3 (Goal field, line 295) still shows `<FormRow label="Цель" value={goal} onChange={setGoal} />` (free text). The plan's action explicitly overrides this with "DO NOT use a free-text FormRow" and is the governing document. The contradiction is noted but Plan 76-02 wins — it is the explicit spec correction.

PASS — the plan correctly handles the enum constraint.

---

## Special Check: Wave Serialization Correctness

76-01 (Wave 1) and 76-03 (Wave 2, depends_on: ["76-01"]) both edit `data/index.js`.

The serialization is correct:
1. 76-01 Task 1 adds `useClientTrainers` export to `data/index.js`.
2. 76-03 Task 2 runs after 76-01 completes; it removes `CONVERSATIONS` and its comment while
   explicitly preserving the `useClientTrainers` export (verified in acceptance criteria).

76-02 is independent (Wave 1, edits only ProfileExtraSheets.jsx). No conflict with 76-01.

PASS

---

## Special Check: Automated Test Coverage (Nyquist-style sampling)

76-01 Task 3 adds:
- A mock for `useClientTrainers` and `useClientPlans` in the test factory.
- A mock for `@/data/trainers.js` (STATIC_TRAINERS_FALLBACK import).
- A mock for `@/utils/format.js` formatMoney (deterministic `(k) => String(k/100)`).
- Test NHOME-01: asserts live initial ("О" from Олег Б) renders, not static "А" from TRAINERS.
- Test NHOME-02: asserts chip text matches `/\d+ тариф\S* · от .+\/мес/`.

This provides automated coverage for success criteria 1 and 2.

Plans 76-02 and 76-03 rely on:
- 76-02 Task 2 acceptance: `pnpm build` and `pnpm lint` exit 0 (functional verification).
- 76-02 Task 3: human-verify checkpoint (the only way to confirm actual persistence across reload — legitimate).
- 76-03 Task 3: `pnpm exec vitest run` (full suite) confirms no test referenced CONVERSATIONS.

PDATA-01/PDATA-02 lack a dedicated Vitest test (the human-verify checkpoint covers persistence;
the automated gates are build/lint/TS). This is acceptable for a UI wiring task where the
mutation path requires a real backend to confirm persistence.

---

## Coverage Matrix

| Success Criterion | Plans | Automated Gate | Human Gate |
|-------------------|-------|----------------|------------|
| 1. Newbie Home trainer avatars from GET /client/trainers | 76-01 | vitest identity test (NHOME-01 case) | Plan end manual check |
| 2. Plan info chip from GET /client/plans | 76-01 | vitest identity test (NHOME-02 case) | Plan end manual check |
| 3. Personal Data sheet from GET /client/me, no placeholders | 76-02 | grep (absence of 'Саша'), tsc | 76-02 Task 3 checkpoint |
| 4. Edit+save persists after full reload | 76-02 | tsc + build + lint | 76-02 Task 3 checkpoint (reload step) |
| 5. Chat badge 0/hidden; CONVERSATIONS absent from App.jsx | 76-03 | grep + tsc + vitest run + build | — |

All five success criteria have at least one automated gate and a clear execution path.

---

## Final Verdict

**PASS**

The three plans form a coherent, dependency-correct, fully-specified execution set.
All five phase success criteria are addressed by concrete, verifiable tasks. No blockers found.

One warning (W-76-01) documents that the `.co-toast` CSS class is actually available globally
in `styles.css` — the executor should be aware when implementing the error toast in
ProfileExtraSheets.jsx, to use `var(--danger)`/`var(--danger-soft)` for the icon background
rather than the default `var(--accent)` that the `.co-toast-ic` class defines.

Run `/gsd:execute-phase 76` to proceed.
