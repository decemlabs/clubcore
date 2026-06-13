# Plan 012: Reset SessionModal sub-screen state on open (stale-form fix, follow-up to 006)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If a
> STOP condition occurs, stop and report — do not improvise. When done, update
> the status row for this plan in `plans/README.md` — unless a reviewer
> dispatched you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/components/modals/SessionModal.tsx`
> If the file changed since baseline, compare the excerpts below against the
> live code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: MED (behavior change on user-facing forms — mitigated by following the in-file convention)
- **Depends on**: plans/001-init-git-baseline.md (recommended: 002 for the smoke/test gate)
- **Category**: bug
- **Planned at**: commit `5ceb34b`, 2026-06-12
- **Origin**: surfaced during plan 006 execution; SessionModal was out of 006's scope.

## Why this matters

Plan 006 fixed stale-form-on-reopen across five modals, but `SessionModal` was on 006's do-not-touch list and has the **same bug** in three of its sub-screens. The dispatcher (`SessionModal`, line ~603) is a `switch (screen)` returning one screen; the dispatcher resets `screen` on open (line ~597) and `WaitlistScreen` resets its own state (line ~476) — but `FormScreen`, `RescheduleScreen`, and `CancelScreen` do **not**. Two real paths keep these screens mounted across a close→reopen, so their `useState` values leak:
1. **Same-screen reopen via `payload.screen`** — if the modal is reopened to the same screen it was closed on, `setScreen(payload.screen)` is a no-op, the screen never remounts, and its fields keep the last-entered values. (This is exactly why `WaitlistScreen` already has a reset effect.)
2. **`FormScreen` across `create`↔`edit`** — both dispatcher cases render the same `FormScreen` component, so switching modes re-renders instead of remounting; `type` persists.

Result: e.g. open «Перенос» (reschedule), change room/time, close, reopen «Перенос» → the old room/time are still there. The fix is the same one-effect-per-screen pattern already used by `WaitlistScreen` in this very file.

## Current state

- **The convention to follow** — `src/components/modals/SessionModal.tsx:473-478` (`WaitlistScreen`, verbatim):

  ```tsx
  function WaitlistScreen({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
    const [list, setList] = useState(WAITLIST);

    useEffect(() => {
      if (open) setList(WAITLIST);
    }, [open]);
  ```

  `useEffect` is **already imported** in this file (used by `WaitlistScreen` and the dispatcher) — no import change needed.

- **The three target screens** (each receives `open`; each holds `useState` with NO reset effect):

  | Screen (line) | State (line) | `useState` initial value(s) |
  |---|---|---|
  | `FormScreen` (`:176`, props include `open`, `mode`) | `type` (`:185`) | `useState<'group' \| 'personal'>('group')` |
  | `RescheduleScreen` (`:300`, `{ open, onOpenChange }`) | `room`,`time`,`notify` (`:301-303`) | `useState('Зал 1')`, `useState('15:00')`, `useState(true)` |
  | `CancelScreen` (`:544`, `{ open, onOpenChange }`) | `notify` (`:545`) | `useState(true)` |

- **Out of scope, stateless or already-correct** (do NOT add effects): `DetailScreen` (`:73`, no `useState`), `ConflictScreen` (`:404`, no `useState`), `WaitlistScreen` (already resets), the `SessionModal` dispatcher (`:586`, already resets `screen` at `:597`).
- Conventions: Russian strings; strict TS; place each effect directly under the screen's `useState` block.

## Commands you will need

| Purpose   | Command             | Expected on success |
|-----------|---------------------|---------------------|
| Typecheck | `bun run typecheck` | exit 0              |
| Lint      | `bun run lint`      | exit 0              |
| Tests     | `bun run test`      | all pass            |

## Scope

**In scope**:
- `src/components/modals/SessionModal.tsx` (the three screens above only)
- A new `src/components/modals/SessionModal.reset.test.tsx` if you write the optional test (Step 3, option a)
- `plans/README.md` (status row — OVERRIDDEN if a reviewer dispatched you)

**Out of scope** (do NOT touch):
- The other five modals (already fixed by plan 006).
- `AdaptiveModal.tsx`, `ModalsProvider.tsx`, `modals-context.ts` — no refactor of the modal system, no remount-by-key.
- The dispatcher's existing `screen` reset and `WaitlistScreen`'s existing effect.
- Loading real session data into `FormScreen` edit mode — `type` resets to its current hardcoded default `'group'` (mock behavior). A real-data version is a separate, future concern; note it, don't build it.

## Git workflow

- Branch: `advisor/012-session-modal-reset` off `main` (a reviewer may override the base — follow their BASE SETUP if given).
- One commit: `fix: reset SessionModal sub-screen state on open`.
- Do NOT push.

## Steps

### Step 1: Confirm the three screens match the excerpts

Read `FormScreen` (~176-186), `RescheduleScreen` (~300-303), `CancelScreen` (~544-545) and the `WaitlistScreen` exemplar (~473-478). Confirm each target receives `open` and the `useState` initial values match the table. If any differs → STOP and report (drift).

### Step 2: Add a reset effect to each of the three screens

For each, add directly under its `useState` block (before any conditional return, before the main `return`), resetting each state to its **exact** original initial value:

```tsx
// FormScreen — after line 185
useEffect(() => {
  if (open) setType('group');
}, [open]);

// RescheduleScreen — after line 303
useEffect(() => {
  if (open) {
    setRoom('Зал 1');
    setTime('15:00');
    setNotify(true);
  }
}, [open]);

// CancelScreen — after line 545
useEffect(() => {
  if (open) setNotify(true);
}, [open]);
```

Optional consistency: plan 006 extracted module-level `const`s for the defaults (e.g. `const RESCHEDULE_ROOM_DEFAULT = 'Зал 1'`) so the value isn't duplicated between `useState` and the reset. Match that style for the **string** literals if you like; a bare `true` may stay inline. Do NOT change any other behavior.

**Verify**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 3: Behavior check

Run `bun run test` (the plan-002 router smoke suite catches hook-order mistakes — an effect after a conditional return throws on render).

Then verify the reopen behavior. `SessionModal` is **exported** (`:586`) and takes plain props `{ open, onOpenChange, payload }` — so a direct component test is feasible:
- **Option (a)** — write `SessionModal.reset.test.tsx` (model it on `src/components/modals/BookModal.reset.test.tsx`): render `<SessionModal open payload={{ screen: 'reschedule' }} onOpenChange={…} />` inside the same provider Wrapper that file uses; change a field (e.g. click a different room/time control — inspect the rendered markup for the right role/label), set `open={false}`, then `open={true}` with the **same** `payload`, and assert the field returned to its default. This reproduces bug-path #1 directly.
- **Option (b)** — if the providers or control selectors prove awkward under jsdom, do NOT force a meaningless test. Rely on typecheck+lint+smoke and a careful self-audit that each reset matches its `useState` initial value, and state in NOTES that the interactive test was deferred.

**Verify**: the chosen check passes; record which form it took.

## Test plan

- Optional `SessionModal.reset.test.tsx` per Step 3 (reproduces the same-screen-reopen path).
- Regression: the plan-002 smoke suite still green.

## Done criteria

ALL must hold:

- [ ] `FormScreen`, `RescheduleScreen`, `CancelScreen` each contain an `if (open)` reset effect resetting every one of their `useState` values to its original initial value
- [ ] `grep -c "useEffect(" src/components/modals/SessionModal.tsx` → **5** (was 2: dispatcher + WaitlistScreen; +3 new)
- [ ] `bun run typecheck` → exit 0
- [ ] `bun run lint` → exit 0
- [ ] `bun run test` → exit 0
- [ ] Step 3 reopen check performed and described in the summary
- [ ] `git status --porcelain` → only `SessionModal.tsx` (+ the optional test file)

## STOP conditions

Stop and report back if:

- A target screen's `useState` initial value doesn't match the table (drift).
- A target screen turns out NOT to receive `open` in scope (can't gate the effect) — report it.
- You find a target screen UNMOUNTS on every close (then it needs no effect) — report which; don't add a dead effect.
- You want to restructure the dispatcher or `ModalsProvider` — out of scope by design.

## Maintenance notes

- Reviewer focus: each reset restores the **original** initial value (diff the effect against the `useState` args); no effect placed after a conditional return; exactly three new effects.
- This closes the modal-reset finding across the whole `components/modals/` directory (5 modals in plan 006 + SessionModal here).
- Future: if `FormScreen` edit mode ever loads a real session, `type` must initialize/reset from that data, not the hardcoded `'group'` — revisit then.
