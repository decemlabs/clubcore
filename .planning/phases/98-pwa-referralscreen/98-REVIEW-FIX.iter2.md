---
phase: 98-pwa-referralscreen
fixed_at: 2026-06-08T15:45:00Z
review_path: .planning/phases/98-pwa-referralscreen/98-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 98: Code Review Fix Report

**Fixed at:** 2026-06-08T15:45:00Z
**Source review:** .planning/phases/98-pwa-referralscreen/98-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (all 4 Warnings; the 5 Info findings are out of scope under `critical_warning`)
- Fixed: 4
- Skipped: 0

**Verification (all green after fixes):**
- `apps/client-pwa`: `pnpm lint` ✓, `pnpm typecheck` ✓, `CI=true pnpm test` ✓ (32 files, 222 tests passed)
- `apps/backend`: `uv run mypy --strict app/modules/referrals/service.py` ✓ (no issues), `uv run ruff check app/modules/referrals/service.py` ✓ (all checks passed)

## Fixed Issues

### WR-01: Transient referral-capture failure permanently discards the pending code

**Files modified:** `apps/client-pwa/src/screens/OnboardingScreen.jsx`
**Commit:** 1f564883
**Status:** fixed: requires human verification (error-classification logic)
**Applied fix:** Moved `sessionStorage.removeItem('clubcore:pendingReferral')` so it runs only on (a) capture success or (b) a definitive non-retryable failure. Both `handleFinish` and `handleSkip` were updated.

Important deviation from the review's suggested snippet: the review proposed `e instanceof ApiError && [404,409,422].includes(e.status)`, but the PWA `ApiError` (`packages/api-client/src/errors.ts`) carries **no HTTP `status` field** — only `code`, `message`, `fields`. `e.status` would be `undefined` and the guard would never fire (silently keeping every code, including terminal ones, forever). I therefore discriminate on the backend's typed error `code` instead, via a new helper `isTerminalReferralError(e)` keyed on `TERMINAL_REFERRAL_CODES = {'referral_code_not_found' (HTTP 404), 'self_referral_not_allowed' (HTTP 422)}` — exactly the two definitive non-retryable cases named in the guidance. These codes are emitted by `referrals/service.py` (`ReferralCodeNotFoundError`, `SelfReferralError`) and surfaced verbatim by `clientFetcher` as `ApiError(body.code, ...)`. Transient classes (`network_error`, `session_expired`, `unknown_error`/5xx) keep the code for a later retry. `ApiError` is imported from `@/data` (already re-exported there). Navigation is never blocked: `setDone(true)` / `navigate('/home')` still run unconditionally after the capture attempt.

Flagged for human verification because the fix is a behavioral/logic change (which error classes are treated as terminal) that syntax checks cannot validate.

### WR-02: dead `.e-bar-fill` progress bar ships permanently empty in the visible card

**Files modified:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx`
**Commit:** 9406d7ca
**Applied fix:** The `.e-bar-track` / `.e-bar-fill` element represents tier/gamification progress (progress toward the next reward tier), which is hide-for-future per SC-5 — the sibling `.milestones` block is already `hidden`. Per guidance, did NOT invent a fake fill value. Instead moved the `.e-bar-track` markup out of the visible "Уже накоплено" area into the already-hidden `.milestones` block (`hidden aria-hidden="true"`), so no empty width:0 bar ships. The real accrued figure (`formatMoney(data?.accruedKopecks ?? 0)`) remains visible. CSS for `.e-bar-track`/`.e-bar-fill` was left in place (harmless; consumed only inside the hidden block when tiers ship later).

### WR-03: misleading "read-only" docstring on `get_referral_summary`

**Files modified:** `apps/backend/app/modules/referrals/service.py`
**Commit:** 9afae5b5
**Applied fix:** Per guidance, did NOT restructure the function — minting the stable code on first summary view is intentional and consistent with `GET /client/referral/code`. Replaced the contradictory line *"Read-only after get_or_create_referral_code (which commits only on first mint)."* with an explicit "Side effect (WR-03)" note: the summary idempotently mints-or-fetches the code and therefore COMMITS on the first call for a client (read-only no-op thereafter), matching the `GET /client/referral/code` contract; steps 2-3 remain pure reads. Removed the misleading "Read-only" wording.

### WR-04: array-index keys on the server-driven, re-orderable invitee list

**Files modified:** `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx`
**Commit:** f1217d9c
**Applied fix:** Replaced `invitees.map((inv, idx) => <div key={idx} ...>)` with a stable composite key `rowKey = `${inv.firstName ?? ''}|${inv.joinedAt ?? ''}`` derived from the PII-minimal payload (no id on the wire). `joinedAt` (= `rc.created_at`) is effectively unique per referrer, so this disambiguates duplicate first names and survives reorder/refetch, preventing the stale avatar/badge reconciliation bug. Added an inline follow-up note to add an opaque per-capture id to the wire payload.

## Skipped Issues

None — all 4 in-scope Warnings were fixed.

---

_Fixed: 2026-06-08T15:45:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
