---
phase: 98-pwa-referralscreen
reviewed: 2026-06-08T15:28:14Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - apps/backend/app/modules/referrals/service.py
  - apps/backend/app/modules/referrals/router.py
  - apps/backend/app/modules/referrals/schemas.py
  - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
  - apps/client-pwa/src/screens/ReferralLandingScreen.jsx
  - apps/client-pwa/src/screens/OnboardingScreen.jsx
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/eslint.config.js
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 98: Code Review Report

**Reviewed:** 2026-06-08T15:28:14Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Full-stack referral phase: backend aggregate read (`GET /client/referral/summary`),
PWA `ReferralSheet`, `ReferralLandingScreen` deep-link, post-auth capture in
`OnboardingScreen`, and new `@/data` hooks.

The backend SQL is the highest-risk area, and it holds up well under scrutiny:

- **IDOR:** every query binds `:cid = str(client_id)` where `client_id` is the
  `require_client()` principal (`router.py:127`, `service.py:301-343`). No path/query/body
  source. Confirmed IDOR-safe.
- **Injection:** all cross-module reads use parametrized `text()` with bound params;
  no string interpolation of user input. Safe.
- **SUM scoping (T-98-04):** `accruedKopecks` sums only `client_id = :cid AND
  entry_type = 'referral_accrual'`. Cross-checked `loyalty/service.py:140-185`:
  `accrue_referral_bonus` writes ONE row per `(referral_capture_id, client_id)` (enforced by
  partial UNIQUE `uq_loyalty_ledger_referral_accrual`), and is called separately for the
  `referrer` and `referee` roles. So a single capture produces two rows with the same
  `referral_capture_id` but different `client_id`. The SUM filters on `client_id = :cid`,
  picking up only the referrer's own row → **no double-count**, correct scope.
- **Invitee LEFT JOIN:** the `ll.client_id = :cid` predicate inside the JOIN-ON clause is
  load-bearing — it ensures the joined accrual row is the *referrer's* row, not the
  referee's row on the same capture. Without it, the JOIN would match either side and
  surface the referee's accrual amount as the referrer's bonus. As written it is **correct**
  and produces exactly one row per `referral_captures` row (no fan-out). No N+1 — single
  round-trip for the list.

No Critical issues found. Warnings concern attribution data-loss on capture, a permanently
empty progress bar, a misleading docstring, and React list-key fragility.

## Warnings

### WR-01: Transient referral-capture failure permanently discards the pending code

**File:** `apps/client-pwa/src/screens/OnboardingScreen.jsx:305-311` (and `329-335`)
**Issue:** Both `handleFinish` and `handleSkip` run:
```js
if (pendingReferral) {
  try { await captureReferral.mutateAsync({ code: pendingReferral }) }
  catch (_e) { /* noop */ }
  sessionStorage.removeItem('clubcore:pendingReferral')   // runs unconditionally
}
```
The `removeItem` executes regardless of whether the capture succeeded. The "best-effort,
never block onboarding" requirement is satisfied for *navigation*, but it conflates two
failure classes:
- `409`/`422`/already-bound — genuinely terminal; discarding the code is correct.
- network blip / `500` / timeout — transient; the bind never happened, yet the only copy
  of the referral code is now gone. The referrer→referee attribution is **silently and
  permanently lost** with no retry path (the code is not re-derivable client-side).

For a referral feature whose entire value is the bind, a network error on this one call
silently drops the referrer's bonus. This is the "swallow that loses real errors that
matter" failure mode.

**Fix:** Only clear the pending code on success or a terminal (non-retryable) status; keep
it on transient failures so a later screen / next session can retry. For example:
```js
if (pendingReferral) {
  try {
    await captureReferral.mutateAsync({ code: pendingReferral })
    sessionStorage.removeItem('clubcore:pendingReferral')
  } catch (e) {
    // Terminal binds (self/already-captured/unknown) are 409/422/404 → drop the code.
    // Transient (network/5xx) → keep it for a later retry.
    const terminal = e instanceof ApiError && [404, 409, 422].includes(e.status)
    if (terminal) sessionStorage.removeItem('clubcore:pendingReferral')
  }
}
```
(Capture is idempotent server-side, so a retry after a successful-but-misreported call is
a safe no-op.)

### WR-02: `accruedKopecks` SUM can be silently truncated by Python `int()` on a Decimal — verify, but more importantly the e-bar progress fill is dead

**File:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx:850-852`
**Issue:** The "Уже накоплено" card renders a progress track (`.e-bar-track`) wrapping
`.e-bar-fill`, but `.e-bar-fill` is declared `width: 0` in the CSS (line 413) and **no code
ever sets its width** (no inline style, no effect, no count-up). The bar is permanently
empty regardless of `accruedKopecks`. The CSS even ships a `transition: width 0.9s ...`
that can never fire. This is shipped dead UI: the user sees an accrued amount next to a
0%-filled bar, implying "no progress" even when bonuses exist. The prompt's referenced
"count-up animation" is also absent — the value renders statically via
`formatMoney(data?.accruedKopecks ?? 0)` (line 832).

**Fix:** Either drive the fill from a target (e.g. progress toward a goal amount) with an
inline `style={{ width: pct + '%' }}`, or remove the `.e-bar-track`/`.e-bar-fill` markup
(lines 850-852) and its CSS (lines 406-414) so the screen does not ship a permanently
broken affordance. If a goal denominator is not yet defined, removing it is the honest
choice for this phase.

### WR-03: Service docstring claims `get_referral_summary` is read-only, but it can COMMIT

**File:** `apps/backend/app/modules/referrals/service.py:278-301`
**Issue:** The router summary doc and the CONTEXT both assert "no commit in read service",
and the service docstring says *"Read-only after get_or_create_referral_code (which commits
only on first mint)."* But `get_referral_summary` calls `get_or_create_referral_code`
(line 301), which **mints and `session.commit()`s** on the first call for a client
(`service.py:209`). So `GET /client/referral/summary` is a read endpoint that performs a
write+commit as a side effect on first access. That is a real behavior, not a docstring
nuance: a `GET` mutates state and is therefore not idempotent/safe in the HTTP sense, and
it diverges from the "no commit in read service" convention stated for this phase.

This is almost certainly intentional reuse (the screen needs the code to exist), but the
convention claim is misleading and the side-effecting GET is a design smell worth an
explicit decision. At minimum the docstring should not describe it as "read-only".

**Fix:** Either (a) document explicitly that this GET is write-on-first-call by design and
update the "no commit in read service" claim to carve out the mint, or (b) split: have the
summary read the existing code and 404/empty-code if none exists, leaving minting to the
dedicated `GET /referral/code` endpoint the PWA already calls. Option (a) is the smaller
change and matches current PWA behavior.

### WR-04: React list uses array index as key for a re-orderable, server-driven list

**File:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx:683-686`
**Issue:** `invitees.map((inv, idx) => <div key={idx} ...>)`. The list is ordered
`rc.created_at DESC` and items transition `pending → joined` (changing badge, color,
avatar, date copy) between refetches. When a new invitee is prepended or an item's status
flips, index-keyed reconciliation re-associates DOM nodes to the wrong logical rows,
producing stale avatar colors/initials and mismatched badges after a refetch. There is no
stable id on the wire (PII-minimal payload exposes no invitee id), so `firstName` alone is
also unstable (duplicate first names collide).

**Fix:** Add a stable, non-PII opaque key to `ReferralInviteeItem` (e.g. a per-capture
hash/opaque token already available server-side) and key on it. If a new wire field is out
of scope this phase, a composite `key={inv.joinedAt + '|' + inv.firstName}` is a strictly
better stopgap than the raw index (joinedAt = `created_at` is effectively unique per
referrer), and should be noted as a follow-up to add an opaque id.

## Info

### IN-01: `formatBonusPreview` ignores its argument and returns a hardcoded string

**File:** `apps/client-pwa/src/screens/ReferralLandingScreen.jsx:25-32`
**Issue:** `formatBonusPreview(welcomeBonusKopecks)` `void`s its parameter and always returns
`'14 дней в подарок к первому абонементу'`. The resolver returns a real
`welcomeBonusKopecks`, and the landing screen also derives `welcomeBonusKopecks` (line 142)
but never displays it — so a config change to the welcome bonus will not be reflected on the
landing page. Verification already accepted this as a known stub (TODO Phase 99). Re-flagging
only as Info: it is cosmetic (the copy is plausible) but the function signature is a trap —
it looks data-driven and is not. Consider dropping the parameter until the days field exists,
so no future caller assumes it reacts to input.
**Fix:** Drop the unused param (`function formatBonusPreview()`) and the dead
`welcomeBonusKopecks` derivation, or wire the actual value. Leave the `// TODO Phase 99`.

### IN-02: `userName` prop accepted but unused in `ReferralSheet`

**File:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx:512`
**Issue:** `export function ReferralSheet({ onClose, userName: _userName })` — `userName` is
destructured to a discarded `_userName` and never used (App.jsx:356 still passes
`userName={t.userName}`). The share copy uses the «Sportzal» brand + server code, not the
user name, so the prop is genuinely dead. Harmless, but it implies a wiring that does not
exist.
**Fix:** Remove the `userName` prop from both the component signature and the `App.jsx:356`
call site.

### IN-03: `pluralFriends` is dead — count is always rendered with a leading number that the helper handles, but joinedCount path is fine; the helper is correct, however the badge only shows when count could be 0

**File:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx:836-848`
**Issue:** The "{joinedCount} {pluralFriends(joinedCount)}" badge renders whenever
`!isLoading && !isError && data`, including when `joinedCount === 0` → "0 друзей" badge
shows next to the accrued amount even with zero joined friends. Minor UX oddity (a "0
друзей" chip), not a bug. `pluralFriends(0)` correctly returns "друзей".
**Fix:** Gate the chip on `joinedCount > 0` if a zero chip is undesirable:
`{!isLoading && !isError && data && joinedCount > 0 && (...)}`.

### IN-04: `share()` spawns confetti before the share sheet resolves / on non-share fallback

**File:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx:602-614`
**Issue:** `share()` calls `spawnConfetti(...)` unconditionally (line 606) before checking
`navigator.share`, and regardless of whether the user cancels the native share sheet. The
celebratory confetti therefore fires even when the user dismisses the share dialog without
sharing. Cosmetic only.
**Fix:** Move `spawnConfetti` into the success/fallback branches, or accept as intentional
(low priority).

### IN-05: `.referral-root` token block leaks no globals, but `prefers-reduced-motion` keyframe override in landing screen is a no-op

**File:** `apps/client-pwa/src/screens/ReferralLandingScreen.jsx:172-174`
**Issue:** CSS scoping in `ReferralSheet` is complete — every rule is prefixed with
`.referral-root` and all design tokens are declared on `.referral-root` (no `:root` leakage).
Good. However, the landing screen's reduced-motion guard redefines the `@keyframes rf-float`
inside a `@media (prefers-reduced-motion: reduce)` block (lines 172-174). Redefining keyframes
in a media query is non-standard and unreliable across engines; the floating chips may keep
animating under reduced-motion. The `ReferralSheet` does this correctly by setting
`animation: none` on the element instead (line 213).
**Fix:** Mirror the sheet's pattern — disable the animation on the elements under reduced
motion (`.spot-chip { animation: none }` equivalent) rather than redefining the keyframe.

---

_Reviewed: 2026-06-08T15:28:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
