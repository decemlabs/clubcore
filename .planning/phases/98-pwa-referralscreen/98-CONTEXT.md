# Phase 98: PWA ReferralScreen - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Graduate the client-PWA "Привести друга" screen from the ComingSoon placeholder
into a real, data-wired, pixel-perfect port of the approved reference design,
showing the client's stable referral code, share affordances, the list of
invited friends with real statuses, and the real "Уже накоплено" referral-bonus
sum. Also wire the `…/i/<code>` deep-link on the PWA side so it auto-populates
the referral code into the friend's onboarding flow.

**Full-stack phase.** REFER-06 requires backend read surface that Phases 96/97
did NOT build (no invited-friends list endpoint; no referral-only accrued sum),
so this phase adds a backend read endpoint, the `@/data` hook, the PWA screen,
and the deep-link plumbing.

Requirements: REFER-02 (PWA deep-link handling), REFER-05, REFER-06.

Reference design (source of truth for the pixel-perfect port):
`.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx`.
</domain>

<decisions>
## Implementation Decisions

### Backend Read Surface for REFER-06
- **New aggregate endpoint `GET /api/v1/client/referral/summary`** → `{ code, shareUrl, accruedKopecks, invitees: [...] }`. One round-trip for the whole screen, one `@/data` hook. `require_client()` gate, IDOR-safe (client_id from principal only). Mounts on the existing client-prefixed referral router.
- **Invitee item shape:** `{ firstName, joinedAt, status: 'joined' | 'pending', bonusKopecks }`. `firstName` only (PII-minimal, consistent with `/i/<code>`); `joinedAt` = the `referral_captures` row creation date. NO last name, NO referee client_id in the response.
- **status:** `joined` when a `referral_accrual` `loyalty_ledger` row exists for that capture (the referee paid their first membership → both credited); otherwise `pending` ("Ждём"). `bonusKopecks` = the referrer's accrued bonus for that referee (0 while pending).
- **accruedKopecks ("Уже накоплено"):** server-computed SUM of the authenticated client's own `loyalty_ledger` rows WHERE `entry_type='referral_accrual'` (their referrer bonuses only — NOT the total loyalty balance, which would include welcome/owner_grant). Reuse the loyalty fold pattern but filtered to referral entries.
- Cross-module reads via raw `text()` SQL where they touch clients/loyalty from the referrals module (D-54-08); or implement the aggregate read in the referrals service joining referral_captures → clients → loyalty_ledger. Keep import-linter happy (no module↔module ORM imports).

### @/data Wiring & Screen States
- **One `useClientReferralSummary()` React Query hook**, defined in `apps/client-pwa/src/lib/clientQueries.ts` and re-exported through the `@/data` swap seam (`src/data/index.js`) — mirrors `useClientMessages` / `useClientLoyaltyBalance`. No mock constants for this wired screen.
- Query key `['client','referral','summary']`, global `staleTime` (30s); read-only (no invalidation needed beyond default).
- **States:** dedicated empty state ("ещё никого не пригласили" / reference's empty copy) when `invitees` is `[]`; skeleton while loading; inline error fallback — same convention as the graduated ChatScreen (Phase 94).
- **Share + copy:** copy code via `navigator.clipboard`; native share via `navigator.share`; explicit chips for Telegram (`https://t.me/share/url?url=<shareUrl>&text=…`) and WhatsApp (`https://wa.me/?text=…<shareUrl>`). Share text includes the server-built `shareUrl` (never a client-built URL).

### Deep-Link Handling (REFER-02 PWA) & Port Specifics
- **New public route `/i/:code`** in `App.jsx` (alongside `/login`): resolves the code via `GET /i/<code>`, stores it in `sessionStorage` under `clubcore:pendingReferral`, and shows a lightweight landing (referrer first name + welcome-bonus preview from the resolver) with a CTA into onboarding/login.
- **Capture timing:** AFTER the friend authenticates / completes onboarding → call `POST /client/referral/capture` with the stored code, then clear the sessionStorage key. Idempotent no-op if already bound or self-referral (handled server-side from Phase 96).
- **Invalid/expired code:** resolver returns `valid:false` → landing shows a neutral "join clubcore" CTA (no error page), proceeds to normal onboarding with no pending code.
- **Pixel-perfect port:** scope ALL reference CSS under `.referral-root { … }` (rewrite `:root`→`.referral-root`, `body.dark`→`.referral-root.dark`, prefix selectors), strip device chrome (`.device`/`.island`/`.status-bar`/`.home-indicator`), fill the SheetGate inset — exact ChatScreen v2.5 recipe.
- **Gamification tier tracker (SC-5):** present in the DOM but hidden (hide-for-future, `hidden`/`display:none`) — NOT deleted.
- **D-71-09 graduation:** de-list `ReferralSheet.jsx` from `apps/client-pwa/eslint.config.js` — remove the negated ignore (`'!src/screens/sheets/ReferralSheet.jsx'`, ~line 31) AND delete the dedicated `no-restricted-paths` block (~lines 71–109). `grep ReferralSheet eslint.config.js` must return 0. Import data only via `@/data`.

### Claude's Discretion
- Exact endpoint operation_id, response schema field casing (camelCase wire per envelope convention), and whether the summary read lives in referrals/service.py with a raw-SQL join or a small repository method.
- Count-up animation for "Уже накоплено" (reference has it) — keep if cheap, else static figure; not load-bearing.
- sessionStorage key name detail, landing-screen component name.
- Precise visual spacing/tokens — formalized by the UI-SPEC (gsd-ui-phase) against the reference.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` — current ComingSoon placeholder (~11 lines); opened via `ui.setReferralOpen(true)` from HomeScreen + ProfileScreen, rendered in `SheetGate` (App.jsx:48,123,169,346-348).
- `apps/client-pwa/src/screens/ChatScreen.jsx` (Phase 94) — the graduation + pixel-perfect port template: CSS scoped to `.chat-root`, device chrome stripped, data via `@/data` hooks, empty/loading states.
- `apps/client-pwa/src/lib/clientQueries.ts` — React Query hooks (`useClientMessages`, `useClientLoyaltyBalance`, …); add `useClientReferralSummary` here.
- `apps/client-pwa/src/data/index.js` — the `@/data` swap seam; re-export the new hook.
- `apps/client-pwa/vite.config.ts:29` — `@` alias → `src/`.
- `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` — pixel-perfect source (hero, reward rows, code box + copy, share chips, "Как это работает" steps, tier tracker, count-up).
- Backend: `apps/backend/app/modules/referrals/` (router/service/repository from Phase 96), `loyalty_ledger` with `entry_type='referral_accrual'` rows (Phase 97), `referral_captures` (referrer↔referee + created_at).

### Established Patterns
- D-71-09 graduation = remove negated ESLint ignore + delete the dedicated no-restricted-paths block (exact ChatScreen Phase 94 precedent).
- `@/data` exports ONLY React Query hooks for wired screens (no mock constants).
- PII-minimal client responses (first name only), camelCase wire via ResponseEnvelope.
- Backend client reads gated by `require_client()`, IDOR-safe (principal-only).
- import-linter: modules cannot import each other — keep the summary read self-contained in referrals (raw SQL for cross-domain reads, D-54-08).

### Integration Points
- New `GET /client/referral/summary` on the referrals client router; mounted already under `/api/v1/client`.
- New `/i/:code` public route in `apps/client-pwa/src/App.jsx`; onboarding flow (`OnboardingScreen.jsx`) reads the pending code from sessionStorage and calls `POST /client/referral/capture` post-auth.
- `eslint.config.js` D-71-09 de-list (3 spots).

</code_context>

<specifics>
## Specific Ideas

- Aggregate `GET /client/referral/summary` → `{ code, shareUrl, accruedKopecks, invitees:[{firstName, joinedAt, status, bonusKopecks}] }` — single hook `useClientReferralSummary`.
- "Уже накоплено" = SUM of own `referral_accrual` ledger rows (referral-only, not total balance).
- `/i/:code` → resolve + store `clubcore:pendingReferral` in sessionStorage → capture after onboarding auth.
- Pixel-perfect port via ChatScreen recipe (`.referral-root` scope, chrome stripped); tier tracker hidden-for-future.
- Reference: `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx`.

</specifics>

<deferred>
## Deferred Ideas

- Gamification tier backend (tier thresholds, "5 friends → free month") — DOM-hidden only; backend deferred (Future Requirements).
- Nudge/reminder to friends who clicked but didn't pay ("Ждём" → nudge) — status shown, no nudge.
- Owner referral analytics — after admin-web unfreeze.
- Avatars / last names in the invitees list — PII-minimal, first name only.

</deferred>
