---
phase: 98-pwa-referralscreen
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - apps/backend/app/modules/referrals/service.py
  - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
  - apps/client-pwa/src/screens/ReferralLandingScreen.jsx
  - apps/client-pwa/src/screens/OnboardingScreen.jsx
  - apps/client-pwa/src/lib/clientQueries.ts
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: clean
---

# Phase 98: Code Review Report (Re-review iteration 2)

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 5
**Status:** clean

## Summary

Final re-review (iteration 2) of the auto-fix loop. Prior review: 0 Critical, 4 Warning, 5 Info. All four prior warnings (WR-01..WR-04) are correctly resolved. No new Critical or Warning defects introduced. Two Info-level observations remain (pre-existing, non-blocking). Status set to `clean`.

The headline concern for this iteration — whether WR-01's terminal-vs-transient discrimination actually reaches a live `error.code` — was traced end-to-end and **confirmed correct** (see WR-01 verification below).

## Narrative Findings (AI reviewer)

### Prior-warning verification

**WR-01 — referral capture: terminal vs transient discrimination — RESOLVED (verified against real shapes).**

Traced the full error path:
- `clientFetcher.ts:151-152` — `finishResponse` throws `new ApiError(body.code, body.message, body.fields)` where `body.code` is the server's typed code string parsed from the response envelope (`parseErrorBody`, lines 83-103).
- `errors.ts:16-26` — `ApiError` is a single concrete class with a public `code: string` field. There is **no** `status` field — the fixer's note is correct; discriminating on `.code` is the only viable strategy.
- Backend `service.py:62-73` — `ReferralCodeNotFoundError.code = "referral_code_not_found"` and `SelfReferralError.code = "self_referral_not_allowed"`. These are exactly the two strings in `TERMINAL_REFERRAL_CODES` (OnboardingScreen.jsx:33). The capture service raises these (lines 398, 402, 412); they propagate through the AppError handler into the response body's `code` field, and the fetcher rethrows them verbatim.
- `useCaptureReferral` (clientQueries.ts:1144-1155) calls `clientRequest` with no error transform, so `mutateAsync` rejects with the genuine `ApiError` instance.
- Module identity is preserved: `ApiError` is defined once in `@clubcore/api-client`, re-exported by `clientQueries.ts:18`, and re-exported again by `@/data` (`data/index.js:22`). OnboardingScreen imports `ApiError` from `@/data` (line 19). The `instanceof ApiError` check (OnboardingScreen.jsx:36) therefore compares against the same class object that `clientFetcher` instantiates — `instanceof` succeeds. **No new finding.**

Transient classification is also correct: `network_error` (clientFetcher:223,258), `session_expired` (lines 236,243,261), and `unknown_error` (lines 101,144) all fall outside `TERMINAL_REFERRAL_CODES`, so the pending code is correctly retained for retry. Navigation is never blocked — the inner `try/catch` is nested inside the outer mutation flow and `setDone(true)` / `navigate('/home')` run regardless of capture outcome (OnboardingScreen.jsx:329-338, 361-370).

**WR-02 — dead progress bar moved into hidden tier-tracker — RESOLVED (no orphan / no visual break).**

`.e-bar-track`/`.e-bar-fill` now live inside `<div className="milestones" hidden aria-hidden="true">` (ReferralSheet.jsx:864-874), double-hidden via the HTML `hidden` attribute and `.referral-root .milestones { display: none }` (line 417). The visible accrued figure (`formatMoney(data?.accruedKopecks ?? 0)`, line 838) and the `{joinedCount} {pluralFriends}` badge (lines 842-854) remain in the `.e-top` block. The "Уже накоплено" label/value pairing is intact; no section header is left orphaned and the `.earned` card retains its padding. Confirmed clean.

**WR-03 — get_referral_summary docstring corrected — RESOLVED.**

Docstring now explicitly documents the side effect (service.py:298-304): step 1 calls `get_or_create_referral_code` which mints+commits on first call, matching `GET /client/referral/code`. The misleading read-only claim is gone. Behavior matches the documented contract.

**WR-04 — invitee list stable composite key — RESOLVED.**

`rowKey = \`${inv.firstName ?? ''}|${inv.joinedAt ?? ''}\`` (ReferralSheet.jsx:690) replaces the array index. Field names match the wire shape `ReferralInviteeItem { firstName, joinedAt }` (clientQueries.ts:1075-1080). `joinedAt = rc.created_at` is server-ordered DESC and effectively unique per referrer, so the key is stable across refetch/reorder. The residual collision risk (two invitees with identical first name AND identical `created_at` timestamp) is astronomically small and is already tracked by the inline follow-up comment to add an opaque per-capture id to the wire payload. Acceptable.

### New-defect scan (no Critical/Warning found)

Scanned the touched surface for newly-introduced defects across all three issue classes:
- Backend `capture_referral` / `get_or_create_referral_code` idempotency (ON CONFLICT DO NOTHING + RETURNING-gated audit) is internally consistent; the lost-race re-read paths return the winner without duplicate audit.
- `get_referral_summary` raw SQL binds `client_id` as the caller's principal only (IDOR-safe), filters `deleted_at IS NULL`, and uses parameterized `text()` binds (no injection surface).
- Frontend null-safety: all `data?.x ?? fallback` accesses are guarded; `joinedCount` (ReferralSheet.jsx:731) guards on `data` before `.filter`. `renderFriends` handles loading/error/empty/populated branches.
- `useCaptureReferral` returns `void`; OnboardingScreen never reads its return value. Consistent.

No Critical or Warning defects introduced by the fixes.

## Info

### IN-01: Referral capture mutation does not invalidate the referral summary cache

**File:** `apps/client-pwa/src/lib/clientQueries.ts:1144-1155`
**Issue:** `useCaptureReferral` has no `onSettled` invalidation. After a successful capture the referrer's `referralSummary()` cache is not invalidated, so a referrer viewing their ReferralSheet would see the new invitee only after the 30s `staleTime` lapses. In the current flow the capturer is the *referee* (not the referrer), and the referrer is a different client/session, so cross-session invalidation is not achievable client-side anyway. Non-blocking; mirrors the inherent limitation of optimistic client caches. Pre-existing design choice, not a regression.
**Fix:** No action required this phase. If a future flow surfaces the capturer's own referral summary, add `onSettled: () => qc.invalidateQueries({ queryKey: clientPortalKeys.referralSummary() })`.

### IN-02: formatBonusPreview ignores its argument (intentional, TODO-tracked)

**File:** `apps/client-pwa/src/screens/ReferralLandingScreen.jsx:25-32`
**Issue:** `formatBonusPreview(welcomeBonusKopecks)` voids its argument and returns a static string; the resolver's `welcomeBonusKopecks` is computed but not displayed. This is documented and gated behind `// TODO Phase 99` pending a server-side days field. Dead-ish parameter but deliberate.
**Fix:** No action this phase. Wire actual days from the resolver response when the server exposes a days field (already tracked).

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
