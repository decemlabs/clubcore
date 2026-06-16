# Plan 006: Reset modal screen state on every open (stale-form fix)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/components/modals`
> On any change to the five target files, compare the excerpts below before
> proceeding; mismatch = STOP.

## Status

- **Priority**: P2
- **Effort**: S–M
- **Risk**: MED (behavior change on user-facing forms — mitigated by following the in-repo convention)
- **Depends on**: plans/001-init-git-baseline.md (recommended: 002 for the smoke gate)
- **Category**: bug
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

Modal screens hold form state in `useState` inside components that stay mounted while the dialog is closed — so reopening a modal shows whatever the user last selected, not the defaults. Example: open «Оформить абонемент», switch the plan from «3 месяца» to «Год», cancel, reopen — «Год» is still selected, and one hasty confirm submits the wrong tier. The codebase already has the correct convention (several modals reset on open); this plan applies it consistently to the five modals that don't.

## Current state

- **The convention to follow** — `src/components/modals/SessionModal.tsx:474-479` (WaitlistScreen, verbatim):

  ```tsx
  function WaitlistScreen({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
    const [list, setList] = useState(WAITLIST);

    useEffect(() => {
      if (open) setList(WAITLIST);
    }, [open]);
  ```

  `ExtendModal.tsx:40`, `BranchModal.tsx:63`, `EditClientModal.tsx:68`, `ConfirmModal.tsx:25`, `TrainerFormModal.tsx:118` also have open-driven effects (verify each actually resets in Step 1).

- **Targets — files with `useState` and ZERO `useEffect`** (verified by grep 2026-06-12):

  | File | `useState` count | Known stateful screens |
  |------|------------------|------------------------|
  | `SubscriptionModal.tsx` | 7 | CreateScreen `:94` (`useState('m3')`), EditScreen `:152` (`useState(true)`), RenewScreen `:234`, FreezeScreen `:286`, UnfreezeScreen `:334`, CancelScreen `:388`, HistoryScreen `:497` |
  | `CashModal.tsx` | 6 | screens for `'in' | 'out' | 'recon' | 'zreport' | 'close' | 'openshift'` (e.g. OutScreen: `useState('12 000')`) |
  | `BookModal.tsx` | 6 | enumerate in Step 1 |
  | `NewClientModal.tsx` | 3 | enumerate in Step 1 |
  | `PresentModal.tsx` | 2 | enumerate in Step 1 |

  `CheckinModal.tsx` has zero `useState` — out of scope.

- All screens share the shape `type ScreenProps = { open: boolean; onOpenChange: (open: boolean) => void }` and render `<AdaptiveModal open={open} …>`; the screen component itself stays mounted, which is exactly why state survives a close/reopen.
- Conventions: Russian strings, strict TS (`noUnusedLocals` etc.), `import { useEffect } from 'react'` will need adding to files that lack it.

## Commands you will need

| Purpose   | Command             | Expected on success |
|-----------|---------------------|---------------------|
| Typecheck | `bun run typecheck` | exit 0              |
| Lint      | `bun run lint`      | exit 0              |
| Tests     | `bun run test`      | all pass            |

## Scope

**In scope**:
- `src/components/modals/SubscriptionModal.tsx`
- `src/components/modals/CashModal.tsx`
- `src/components/modals/BookModal.tsx`
- `src/components/modals/NewClientModal.tsx`
- `src/components/modals/PresentModal.tsx`
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- Modals that already have effects (`SessionModal`, `ExtendModal`, `BranchModal`, `EditClientModal`, `ConfirmModal`, `TrainerFormModal`) — UNLESS Step 1 finds a stateful screen in them without reset; then report it in your summary and fix only with the same one-effect pattern.
- `AdaptiveModal.tsx`, `ModalsProvider.tsx`, `modals-context.ts` — do not centralize/refactor the modal system (no remount-by-key rewrite, no new abstractions). This plan follows the existing per-screen convention only.
- `fields.tsx` — shared field primitives, unrelated.
- Adopting react-hook-form — explicitly rejected for now (the library is being removed in plan 007).

## Git workflow

- Branch: `advisor/006-modal-reset` off `main`.
- One commit per modal file. Message: `fix: reset <Modal> screen state on open`.
- Do NOT push.

## Steps

### Step 1: Inventory every stateful screen in the five files

For each target file, list every component containing `useState` and note: state variables + their initial values. Use `grep -n "useState" <file>` and read the surrounding component. Initial values are literals or module constants (e.g. `'m3'`, `'12 000'`, `true`) — record them exactly. Also re-check the six "already has effects" modals: confirm their effects reset state when `open` becomes true (not just sync props); report any gap.

**Verify**: your inventory lists ≥ 12 stateful screens across the five files (7+6+6+3+2 `useState` calls distribute across screens; some screens hold several).

### Step 2: Add a reset effect to each stateful screen

For every screen from the inventory, add (adjusting names to that screen's state):

```tsx
useEffect(() => {
  if (open) {
    setPlan('m3');          // каждый useState экрана — к его исходному значению
    // ...остальные set'ы этого экрана
  }
}, [open]);
```

Rules:
- Reset to the **exact original initial value** of each `useState` (from your Step 1 inventory). Where the initial value is an inline literal used twice, extract it to a module-level `const` next to the screen (matching how `WAITLIST` is used in the exemplar) so the default isn't duplicated.
- Add `useEffect` to the file's React import if missing.
- One effect per screen, placed directly under the screen's `useState` block — same shape as the `WaitlistScreen` exemplar.
- Do not change any other behavior (no validation additions, no submit changes).

**Verify after each file**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 3: Behavior check

If plan 002 landed, run `bun run test` (smoke suite catches hook-order mistakes — an effect accidentally placed after a conditional return will fail the page render).

Then check the reopen behavior. Preferred: a component test if `SubscriptionModal` (exported at `SubscriptionModal.tsx:544`) can be rendered with its props directly — read its prop signature; if it takes `open`/screen props without needing the modals context, write a test: render CreateScreen's parent with `open=true`, click «Год», set `open=false`, then `open=true`, assert «3 месяца» is the selected option again. If it is context-driven and a direct render is awkward, perform a manual check instead (`bun run dev`, open the subscription modal from a client page, change plan, close, reopen — defaults restored) and state in your summary exactly what you did.

**Verify**: the chosen check passes; record which form it took.

## Test plan

- Primary: the per-screen reset effects are mechanical; the typecheck/lint/smoke gates plus the Step 3 reopen check cover them.
- Deferred (explicitly): full modal integration tests (open → fill → submit → assert close/callback per modal). That is a follow-up testing phase, not this plan — note it in `plans/README.md` if you finish early; do not start it.

## Done criteria

ALL must hold:

- [ ] Every stateful screen in the five files contains an `if (open)` reset effect: `grep -c "useEffect" src/components/modals/SubscriptionModal.tsx` ≥ 7 (one per stateful screen found), and ≥ 1 for each of the other four files (matching your inventory count)
- [ ] `bun run typecheck` → exit 0
- [ ] `bun run lint` → exit 0
- [ ] `bun run test` → exit 0 (if tests exist)
- [ ] Step 3 reopen check performed and described in the summary
- [ ] `git status --porcelain` → only in-scope files
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back if:

- A screen's state shape doesn't fit the pattern (state initialized from props or context, derived state, refs) — adding a naive reset could fight a sync effect; report the screen instead.
- The screen components turn out to UNMOUNT on close (state loss impossible) for some modal — then that modal needs no change; report which and skip it (don't add dead effects).
- You find yourself wanting to restructure `ModalsProvider` or introduce keys/abstractions — that is out of scope by design.

## Maintenance notes

- New modal screens must include the reset-on-open effect; plan 008 can add one line to CLAUDE.md's conventions if desired (not required).
- If the team later adopts a form library or remount-by-key strategy, these effects become the inventory of what to migrate — they mark every stateful screen explicitly.
- Reviewer focus: each reset restores the *original* initial values (diff the effect against the `useState` arguments), and no effect was placed after a conditional return.
