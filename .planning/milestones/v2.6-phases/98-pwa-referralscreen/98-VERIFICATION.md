---
phase: 98-pwa-referralscreen
verified: 2026-06-08T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open the ReferralScreen sheet in the running PWA (light + dark theme) and compare against .planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx"
    expected: "Pixel-perfect parity: hero spot illustration with float animation, two reward rows (mint-tinted 'Вам' / neutral 'Другу'), dashed code box + copy button, 3 share chips, numbered steps with connector, friends list, sticky blurred CTA footer; warm-stone+mint palette; device chrome absent; tier tracker not visible"
    why_human: "Visual fidelity / pixel parity / animation behaviour cannot be confirmed by grep — requires rendering in a browser at the SheetGate inset."
  - test: "Open …/i/<valid-code> in the PWA, tap 'Присоединиться', complete onboarding, then open the ReferralScreen as the referrer"
    expected: "Landing shows '<Name> зовёт вас в «Sportzal»'; after auth the new friend appears in the referrer's invitees list with a 'Ждём' badge (then '+bonus' after accrual); accrued figure updates"
    why_human: "Full deep-link → capture → summary round-trip across two authenticated sessions and a live backend; not statically verifiable."
  - test: "Tap Telegram / WhatsApp / Ссылка chips and the copy button"
    expected: "Telegram/WhatsApp open share intents carrying the SERVER shareUrl; Ссылка + copy write to clipboard and show the toast + confetti; native share fires on the topbar/footer buttons"
    why_human: "External share intents, clipboard, and Web Share API behaviour require a real device/browser."
---

# Phase 98: PWA ReferralScreen Verification Report

**Phase Goal:** Экран «Приведи друга» выведен из ComingSoon и отображает реальные данные: персональный код, список приглашённых, сумму накопленных бонусов
**Verified:** 2026-06-08
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ReferralSheet.jsx` de-listed from D-71-09 ESLint zone (grep = 0) AND imports referral data via `@/data` | ✓ VERIFIED | `grep -c ReferralSheet eslint.config.js` = 0; `ReferralSheet.delist.test.ts:18-20` asserts `toBe(0)`; `ReferralSheet.jsx:12` `import { useClientReferralSummary } from '@/data'` (no direct http). `data/index.js:72-75` re-exports all 3 hooks; comment line 5 lists ReferralSheet as graduated. |
| 2 | Pixel-perfect port: hero, reward rows, code box+copy, share chips, steps; chrome stripped; CSS scoped `.referral-root` | ✓ VERIFIED (code) / ⚠ visual → human | `ReferralSheet.jsx` 1008 lines; CSS block (64-510) verbatim re-scoped to `.referral-root`; no `.stage/.device/.island/.status-bar` chrome rendered; topbar/hero/rewards/earned/code-card/share-row/steps/friends/footer/toast all present in locked order. Pixel fidelity itself needs browser (human item 1). |
| 3 | Invited-friends list shows REAL data (firstName, joinedAt, status badge "+bonus"/"Ждём") + empty state; from summary `invitees[]` | ✓ VERIFIED | `ReferralSheet.jsx:659-723` `renderFriends()` maps `data.invitees`: joined → green badge `+{formatMoney(bonusKopecks)}` + "Присоединился(ась) {date}"; pending → amber "Ждём" + "Перешёл по ссылке"; empty → "Пора никого" state (673-681). Sourced from `useClientReferralSummary` → `GET /api/v1/client/referral/summary`. Backend `service.get_referral_summary` (278-360) builds invitees via real cross-module SQL join. |
| 4 | "Уже накоплено" = real SUM of referral_accrual ledger entries (accruedKopecks), NOT a mock constant | ✓ VERIFIED | `service.py:307-317` `SELECT COALESCE(SUM(amount_kopecks),0) FROM loyalty_ledger WHERE client_id=:cid AND entry_type='referral_accrual'`. Rendered at `ReferralSheet.jsx:832` `formatMoney(data?.accruedKopecks ?? 0)` — no hardcoded EARNED_TO/2000 constant. Test `test_summary_joined_invitee_status_bonus_and_accrued_sum` asserts `accruedKopecks==50000`. |
| 5 | …/i/<code> auto-populates code into onboarding (route + sessionStorage + post-auth capture); tier tracker present-but-hidden | ✓ VERIFIED | `App.jsx:295` public `/i/:code` route outside RequireAuth; `ReferralLandingScreen.jsx:144-149` stores `sessionStorage['clubcore:pendingReferral']` on valid; `OnboardingScreen.jsx:305-311 & 329-335` reads pending code post-auth, `captureReferral.mutateAsync`, clears key, best-effort try/catch never blocks. Tier tracker `.milestones` in DOM (`ReferralSheet.jsx:854`) with `hidden` attr + CSS `display:none` (417) — not deleted. |

**Score:** 5/5 truths verified in code. SC-2 visual parity and the live deep-link/share round-trips are routed to human verification (cannot be confirmed without a browser).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/referrals/schemas.py` | ReferralInviteeItem + ReferralSummaryResponse | ✓ VERIFIED | Both classes present (90-115), camelCase wire, PII-minimal. |
| `apps/backend/app/modules/referrals/service.py` | `get_referral_summary` fold + raw-SQL join | ✓ VERIFIED | 278-360, real SUM + LEFT JOIN, IDOR-safe (client_id from principal). |
| `apps/backend/app/modules/referrals/router.py` | `client_get_referral_summary` handler | ✓ VERIFIED | 109-128 delegates to `service.get_referral_summary`. |
| `apps/backend/tests/integration/test_referral_summary.py` | empty/pending/joined/PII/IDOR/401/shareUrl | ✓ VERIFIED | 7 tests, all named cases present; **7 passed in 4.52s**. |
| `apps/client-pwa/src/lib/clientQueries.ts` | 3 hooks (summary/resolve/capture) | ✓ VERIFIED | 1090-1155, all wired to real endpoints with response handling. |
| `apps/client-pwa/src/data/index.js` | `@/data` re-export of hooks | ✓ VERIFIED | 72-75 exports all 3; graduated-list comment updated. |
| `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` | Pixel-perfect data-wired screen (≥200 lines) | ✓ VERIFIED | 1008 lines, replaces ComingSoon, scoped `.referral-root`. |
| `apps/client-pwa/eslint.config.js` | D-71-09 de-list (3 spots removed) | ✓ VERIFIED | grep = 0. |
| `apps/client-pwa/src/screens/ReferralSheet.delist.test.ts` | grep-returns-0 guard | ✓ VERIFIED | asserts `toBe(0)`. |
| `apps/client-pwa/src/screens/ReferralLandingScreen.jsx` | Public /i/:code landing | ✓ VERIFIED | 247 lines; valid/invalid/loading states; stores pending code. |
| `apps/client-pwa/src/App.jsx` | /i/:code route + chrome-hidden | ✓ VERIFIED | route 295; `isReferralLandingRoute` → `hideTabBar` (278-282). |
| `apps/client-pwa/src/screens/OnboardingScreen.jsx` | Post-auth capture from pending code | ✓ VERIFIED | both submit + skip paths capture and clear key. |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| router.py | service.get_referral_summary | handler delegates | ✓ WIRED (line 127) |
| service.py | loyalty_ledger + referral_captures + clients | raw text() SQL, entry_type='referral_accrual' | ✓ WIRED (307-343) |
| ReferralSheet.jsx | useClientReferralSummary via @/data | import + render | ✓ WIRED (12, 514, 832, 672) |
| clientQueries.ts | GET /client/referral/summary | clientRequest('get', ...) | ✓ WIRED (1100) |
| ReferralLandingScreen.jsx | GET /api/v1/i/<code> | useClientReferralResolve(code) | ✓ WIRED (16,133; hook at 1131) |
| OnboardingScreen.jsx | POST /client/referral/capture | useCaptureReferral + sessionStorage | ✓ WIRED (251, 308/332) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Real Data | Status |
|----------|---------------|--------|-----------|--------|
| ReferralSheet (accrued) | `data.accruedKopecks` | summary endpoint → SUM(referral_accrual) SQL | Yes (real DB SUM) | ✓ FLOWING |
| ReferralSheet (invitees) | `data.invitees` | summary endpoint → referral_captures JOIN clients JOIN ledger | Yes (real join) | ✓ FLOWING |
| ReferralSheet (code/shareUrl) | `data.code/shareUrl` | get_or_create_referral_code + pwa_base_url | Yes (server-built) | ✓ FLOWING |
| ReferralLandingScreen (referrer name) | `data.referrerFirstName` | resolve endpoint → clients.first_name SQL | Yes | ✓ FLOWING |
| ReferralLandingScreen (bonus preview copy) | `welcomeBonusKopecks` | resolve endpoint (returned) but **discarded** by `formatBonusPreview` (static string) | No — static "14 дней" | ⚠ STATIC (see deviation) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend summary endpoint integration | `uv run pytest tests/integration/test_referral_summary.py -q` | 7 passed in 4.52s | ✓ PASS |
| ESLint de-list of ReferralSheet | `grep -c ReferralSheet eslint.config.js` | 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REFER-02 | 98-03 | Deep-link `…/i/<code>` auto-populates onboarding | ✓ SATISFIED | /i/:code route + sessionStorage pendingReferral + post-auth capture (code-verified; live flow → human item 2). |
| REFER-05 | 98-02 | ComingSoon → pixel-perfect port, de-listed, @/data | ✓ SATISFIED (visual → human) | de-list=0, scoped CSS, all sections present; pixel parity → human item 1. |
| REFER-06 | 98-01/98-02 | Real invitees + statuses + accrued sum via @/data | ✓ SATISFIED | summary endpoint + real SQL SUM/join, rendered list + empty state, 7 passing tests. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| ReferralLandingScreen.jsx | 29 | `// TODO Phase 99: wire actual days from resolver response` | ⚠ Warning | Cosmetic landing-page body copy is static; references formal follow-up (Phase 99). Not a ROADMAP SC. See deviation analysis. |

No TBD/FIXME/XXX (BLOCKER-tier) markers in any modified file. The single TODO references formal follow-up (Phase 99) so it does not trip the debt-marker BLOCKER gate.

### Flagged Deviation Analysis — `formatBonusPreview` static "14 дней"

**Finding:** `ReferralLandingScreen.jsx:25-32` receives the resolver's real `welcomeBonusKopecks` but discards it (`void welcomeBonusKopecks`) and returns the hardcoded string `"14 дней в подарок к первому абонементу"`, tagged `TODO Phase 99`.

**Assessment: ACCEPTED minor deviation — NOT an SC gap.**

Reasoning:
1. None of the 5 ROADMAP success criteria require a dynamic bonus-preview figure on the landing page. SC-5 requires only code auto-population (route + sessionStorage + post-auth capture) — all fully implemented and real.
2. The UI-SPEC §Deep-Link Landing lists the body as "welcome-bonus preview from resolver (e.g. '14 дней в подарок к первому абонементу')" — the static string matches the spec's own reference copy verbatim.
3. The server returns `welcomeBonusKopecks` as a raw kopeck amount; there is no days field, and the kopecks→days conversion was never specified. Inventing one client-side would be a fabricated mapping (worse than the verbatim reference copy).
4. The deviation is cosmetic, on a public pre-auth landing screen, and carries a referenced follow-up (Phase 99).

This is recorded as a WARNING, not a BLOCKER. No override entry is required because no must-have FAILed.

### Human Verification Required

1. **Pixel-perfect visual parity** — render the ReferralScreen sheet (light + dark) and compare to the approved reference. Confirm chrome stripped, sections in locked order, palette/typography/spacing, tier tracker not visible, animations respect reduced-motion.
2. **Live deep-link → capture → summary round-trip** — open `…/i/<valid-code>`, join, complete onboarding, then view the referrer's invitees list and accrued figure across two sessions + live backend.
3. **Share / copy interactions** — Telegram/WhatsApp/Ссылка chips, copy button, native share carry the server `shareUrl` and show toast/confetti.

### Gaps Summary

No blocking gaps. All 5 ROADMAP success criteria are provably satisfied in code: ESLint de-list (grep=0) + @/data wiring; full pixel-perfect port structure with scoped CSS and stripped chrome; real invitees list with status badges and empty state; real `accruedKopecks` SUM over referral_accrual ledger rows (not a constant); and the /i/:code deep-link with sessionStorage pending code + best-effort post-auth capture, with the gamification tier tracker present-but-hidden. Backend covered by 7 passing integration tests. The only open item is browser-only visual/interaction verification (routed to human), plus one accepted cosmetic deviation (static landing bonus-preview copy, Phase 99 follow-up).

---

_Verified: 2026-06-08_
_Verifier: Claude (gsd-verifier)_
