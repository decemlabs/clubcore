# Phase 98 — UI Review

**Audited:** 2026-06-08
**Baseline:** `98-UI-SPEC.md` (pixel-perfect port contract) + `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx`
**Screenshots:** not captured (no dev server on :3000 / :5173 / :8080 — code-only audit)
**Scope:** `ReferralSheet.jsx` (primary) + `ReferralLandingScreen.jsx` (deep-link landing)
**Status:** Advisory / non-blocking. Phase passed code-verification (5/5) and code-review; visual pixel-parity routed separately to human verification.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Verbatim reference copy + 3 new states; brand `«Sportzal»` throughout; zero mock strings leaked |
| 2. Visuals | 4/4 | Chrome stripped, `.referral-root` scoped, sections in locked order, tier tracker hidden-not-deleted |
| 3. Color | 4/4 | Warm-stone + mint tokens transcribed verbatim; accent reserved-list respected; only avatar hashes add new hex (justified) |
| 4. Typography | 4/4 | All sizes/weights byte-for-byte from reference (verbatim-port exemption applies) |
| 5. Spacing | 4/4 | Spacing/half-steps transcribed exactly; landing screen uses ad-hoc inline values (own minimal style, allowed) |
| 6. Experience Design | 4/4 | Loading/error/empty/populated all handled; reduced-motion guards added; IDOR/PII/tabnabbing mitigated |

**Overall: 24/24**

---

## Top 3 Priority Fixes

No BLOCKERs and no WARNINGs that affect fidelity to the contract. The items below are LOW-priority advisory nits surfaced under FORCE stance — none gate shipping.

1. **Static reward amounts are hardcoded copy, not server-config** — `ReferralSheet.jsx:809` (`−1 000 ₽`), `:823` (`14 дней`), `:990` (`Вы получаете 1 000 ₽`). The UI-SPEC permits "amount from config if available else default", and CONTEXT defers the config source, so this is contract-compliant today. Risk: if backend reward config diverges from `1 000 ₽` / `14 дней`, the screen silently lies. Fix when config ships: thread amounts through `useClientReferralSummary` (e.g. `data.rewardConfig`).

2. **Landing-screen spot illustration is a hand-rebuilt simplified scene, not the ported `.spot`** — `ReferralLandingScreen.jsx:36-113` re-implements a smaller two-person SVG instead of reusing the reference `.spot` (animated chips/rings/scene). UI-SPEC §Deep-Link Landing explicitly allows "a minimal own style," so this is in-contract. Note only: the landing visually diverges from the sheet's hero, which is acceptable for a public pre-auth page but worth a deliberate design pass later.

3. **Landing bonus-preview copy is a static stub** — `ReferralLandingScreen.jsx:25-32` returns `"14 дней в подарок к первому абонементу"` regardless of `welcomeBonusKopecks` (documented Known Stub, `TODO Phase 99`). Matches reference copy and communicates the gift correctly; wire the real days field when the resolver exposes it.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

PASS — strongest pillar.

- Hero title/sub, reward rows, code label/validity, copy button states, share-chip labels, all 3 steps, friends header, joined/pending date+badge copy, and footer CTA are **verbatim** from the reference (`ReferralSheet.jsx:788-1015` vs reference `:797-1030`).
- Three new states added per UI-SPEC Copywriting Contract: empty (`:676` "Пока никого" + `:678` body), error (`:894` "Не удалось загрузить" + `:897` "Потяните вниз, чтобы обновить."), and the dynamic accrued badge.
- Brand correctly `«Sportzal»` (4 occurrences in sheet, 3 in landing); grep for `САША-1000|myzal|Мой зал|Миша|Даша|Егор|EARNED_TO|2 друга|2/5|18 апреля|2 мая` returns **zero** matches across both files. Every mock string the UI-SPEC flagged ("Mock strings to NOT port") was successfully stripped.
- Improvement over reference: the static "2 друга" badge became `{joinedCount} {pluralFriends(joinedCount)}` (`:852`) with a correct ru pluraliser (`:49-58`) — wired to real data, no hardcoded count.
- Toast copy (`Промокод {code} скопирован`, `Ссылка скопирована`, `Приглашение готово к отправке`, `Откройте приложение, чтобы отправить`) all match the contract and use the real `data.code`.

### Pillar 2: Visuals (4/4)

PASS.

- Device chrome (`.stage`, `.device`, `.island`, `.status-bar`, `.home-indicator`) fully stripped; root is `.referral-root` with `position:absolute; inset:0` (`:93`) filling the SheetGate inset — exact ChatScreen recipe.
- Section order matches the locked top-to-bottom contract: topbar → spot → hero title/sub → reward rows → earned → code card → steps → friends → sticky footer → toast (`:737-1018`).
- Tier tracker correctly **hidden-not-deleted**: `.milestones { display: none }` (`:417`) PLUS `hidden` attr + `aria-hidden` on the element (`:864`) — belt-and-suspenders. Inert nodes/bar kept in DOM (`:864-874`).
- Decorative spot is `aria-hidden="true"` (`:757`); icon-only topbar buttons carry `aria-label="Назад"` (`:739`) and `aria-label="Поделиться"` (`:745`). Focal hierarchy preserved (hero title 27/750 → earned figure 30/800 → CTA).
- WR-02 note (`:856-863`): the `.e-bar-track` progress fill was deliberately moved into the hidden tier block because it has no goal denominator this phase — avoids rendering a permanently-empty `width:0` bar as a broken affordance. Sound judgement; the real accrued figure stays visible.

### Pillar 3: Color (4/4)

PASS.

- Light (`:65-101`) and dark (`:103-124`) token blocks transcribed verbatim from the reference `:root` / `body.dark` — every hex matches (`--accent #2dd4a4`, `--accent-deep #0f9b76`, `--bg #f5f5f4`, warm-stone neutrals, `--warn #e9a23b`, etc.).
- Accent stays on the reserved list: CTA button, "you" reward row + amount, copy-done state, share-chip icon (`--accent-deep`), joined badge, step number chips, spot illustration. No accent bleed onto neutral surfaces.
- New hex introduced only in the avatar palette (`AVATAR_COLORS`, `:37-40`) and the pending badge text `#b9791f` (`:437`, also in reference). Avatar colors are a justified addition (server provides no avatar color; deterministic hash `:41-46`) and apply only to initials chips, not chrome — does not violate the accent reserved-list.
- Pending badge uses `--warn-soft` only (`:437`), matching the contract's amber-reserved-for-pending rule.

### Pillar 4: Typography (4/4)

PASS — verbatim-port exemption applies (UI-SPEC explicitly waives the 2-weight rule).

- Weights present: 400 / 600 / 650 / 700 / 750 / 800 — exactly the reference's set, all transcribed (`hero-title` 27/750 `:264-268`, `e-val` 30/800 `:405`, `r-amt` 19/800 `:303-307`, `code` 19/700 `:320-325`, `topbar-title` 16/650 `:152`, `btn` 16/700 `:451-463`).
- Half-step sizes (11.5, 12.5, 14.5px) carried verbatim (`:302`, `:375`, `:400`, `:429`) — explicitly exempt per UI-SPEC Typography note.
- Monospace stack for code/link (`:322`, `:349`) matches the reference.
- Inline `fontSize: 11.5/12.5/12` overrides on the accrued badge / validity / empty-body (`:847`, `:881`, `:677`) mirror reference inline values — consistent.

### Pillar 5: Spacing (4/4)

PASS — half-step exemption applies.

- Reference rhythm transcribed exactly: `.scroller 4px 16px 0` (`:156`), `.rewards margin-top 22px / padding 6px` (`:281-282`), `.rwd 13px 14px` (`:288`), `.code-card margin-top 14px / padding 16px` (`:311`), `.steps margin-top 24px` (`:378`), `.fr-row 13px 16px` (`:421`), `.footer 12px 16px 14px` (`:443`). All match the UI-SPEC Spacing Scale.
- Friends header `padding: '22px 4px 10px'` (`:997`) matches reference (`:973`).
- `ReferralLandingScreen.jsx` uses ad-hoc inline spacing (`padding: '0 28px 40px'`, `marginTop: 20/12/16/28`) — this is a separate minimal-own-style component permitted by UI-SPEC, not bound to the reference scale, so no violation.

### Pillar 6: Experience Design (4/4)

PASS.

- **Loading:** skeletons for code-box (`:884`), accrued figure (`:834`), and friends row (`:660-669`); hero/chrome render immediately — matches ChatScreen convention and UI-SPEC Data States.
- **Error:** inline neutral fallback, not a crash/error page (`:885-899`); `isError` gated to `&& !isFetching` (`:516`) so a background refetch doesn't flash an error.
- **Empty:** dedicated single-row empty state (`:673-682`) while hero/code/chips/steps still render — the screen is useful pre-first-invite as required.
- **Populated:** per-invitee row with initials avatar, ru-RU/Europe/Moscow date (`:16-28`, Intl not raw Date — project DST convention), joined (green +N ₽ via `formatMoney`) / pending (amber "Ждём") badges.
- **Reduced-motion:** guards added beyond the reference — `.fade-up` (`:176`), spot chips (`:213`), scene (`:236`), shimmer (`:474`), skeleton pulse (`:509`), and confetti bails imperatively (`:557`). Count-up dropped in favor of a static figure (CONTEXT-permitted, non-load-bearing).
- **Share/copy contract:** all handlers embed the **server** `shareUrl` (`:603`, `:627`, `:633`, `:638`, `:649`) — never a client-built URL (T-98-06). `window.open(..., 'noopener')` (`:619`, T-98-08). Copy has synchronous fallback (`:592-595`).
- **No destructive actions** — read-only screen, correctly no confirmation dialogs.
- Deep-link landing (`ReferralLandingScreen.jsx`): valid → stores `clubcore:pendingReferral` + navigate; invalid/error → neutral "Добро пожаловать" landing (anti-enumeration, no red error state) per UI-SPEC; loading skeleton present.

---

## Registry Safety

Not applicable. No `components.json` for client-PWA and the UI-SPEC Registry Safety table declares "none (verbatim CSS port, no shadcn/registry)". No third-party blocks introduced; all markup/CSS/SVG transcribed from the in-repo approved reference. Registry audit: 0 third-party blocks checked, no flags.

---

## Files Audited

- `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` (1021 lines — primary)
- `apps/client-pwa/src/screens/ReferralLandingScreen.jsx` (246 lines — deep-link landing)
- `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` (baseline reference)
- `.planning/phases/98-pwa-referralscreen/98-UI-SPEC.md` (design contract)
- `.planning/phases/98-pwa-referralscreen/98-CONTEXT.md` (locked decisions)
- `.planning/phases/98-pwa-referralscreen/98-01/02/03-SUMMARY.md` (build records)
- `apps/client-pwa/src/utils/format.js` (formatMoney fidelity check)

## Caveat

This is a **code-only** audit — no dev server was reachable, so visual pixel-parity (sub-pixel spacing, animation timing, dark-mode rendering, font metrics) is asserted from CSS transcription fidelity, not rendered screenshots. The reference→implementation CSS diff is byte-faithful where checked, but final pixel-parity sign-off remains with human visual verification as routed.
