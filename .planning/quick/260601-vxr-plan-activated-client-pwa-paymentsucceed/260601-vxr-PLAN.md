---
phase: 260601-vxr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/utils/format.js
  - apps/client-pwa/src/styles.css
  - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
autonomous: false
requirements: [VXR-PLAN-ACTIVATED]

must_haves:
  truths:
    - "On a server-confirmed succeeded payment, the user sees the new 'Plan Activated' success screen: animated check medallion, confetti, personalized headline, real plan card, and a single 'Хорошо' CTA."
    - "The plan card shows the REAL active membership (planNameSnapshot, 'Активен' badge, 'Действует до {ru date}', 'Впереди {N} дней') fetched only after status==='succeeded'."
    - "When GET /client/membership returns null, the card is omitted and the rest of the screen still renders."
    - "Nothing about activation is fetched or shown during pending — the membership query is gated enabled: status==='succeeded'."
    - "Receipt destination chip and the conditional 'Открыть чек' link (only when receiptUrl is non-null) are preserved."
    - "Light and dark themes both render correctly; motion is suppressed under prefers-reduced-motion."
  artifacts:
    - path: "apps/client-pwa/src/lib/clientQueries.ts"
      provides: "useClientMembership(enabled) read hook"
      contains: "useClientMembership"
    - path: "apps/client-pwa/src/utils/format.js"
      provides: "formatRuDate ISO-date-only → ru long-date formatter"
      contains: "formatRuDate"
    - path: "apps/client-pwa/src/styles.css"
      provides: ".pa-* success-screen classes + animations"
      contains: ".pa-"
    - path: "apps/client-pwa/src/routes/PaymentReturnScreen.jsx"
      provides: "Rebuilt PaymentSucceededView"
      contains: "pa-check-hero"
  key_links:
    - from: "apps/client-pwa/src/routes/PaymentReturnScreen.jsx"
      to: "useClientMembership"
      via: "enabled: data?.status === 'succeeded'"
      pattern: "useClientMembership\\("
    - from: "apps/client-pwa/src/routes/PaymentReturnScreen.jsx"
      to: "formatRuDate"
      via: "render endDate as ru date"
      pattern: "formatRuDate\\("
---

<objective>
Replace `PaymentSucceededView` in `apps/client-pwa/src/routes/PaymentReturnScreen.jsx`
with the new "Plan Activated" design, and add a REAL membership plan card fed by the
existing `GET /client/membership` endpoint via a new `useClientMembership(enabled)`
read hook.

Purpose: post-payment confirmation currently shows a minimal generic "Готово!" state.
The new design transfers the mockup's success aesthetic (animated check hero, confetti,
fade-up entrance) and surfaces the user's actual activated membership — truthfully,
from real data, without fabricating perks/economics that the client API does not expose.

Output: a richer, anti-oracle-compliant success screen + one small read hook.
Frontend-only. No backend changes, no migrations, no new endpoints.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260601-vxr-plan-activated-client-pwa-paymentsucceed/260601-vxr-CONTEXT.md
@.planning/phases/999.4-client-pwa-checkout-visual-restyle/999.4-UI-SPEC.md
@apps/client-pwa/src/routes/PaymentReturnScreen.jsx
@apps/client-pwa/src/lib/clientQueries.ts
@apps/client-pwa/src/utils/format.js
@CLAUDE.md

<interfaces>
<!-- Contracts the executor needs. Use these directly — no codebase exploration needed. -->

GET /client/membership backend shape (apps/backend/.../client_portal/schemas.py — ClientMembershipResponse).
Wire is camelCase (ResponseData alias_generator=to_camel). Render-only fields:
  id: string (UUID)
  planNameSnapshot: string      // card name, e.g. "Полугодовой"
  startDate: string             // ISO date-only "YYYY-MM-DD"
  endDate: string               // ISO date-only "YYYY-MM-DD"  → "Действует до {ru date}"
  status: string                // "Активен" badge when === 'active'
  daysUntilEnd: number          // server-computed (D-69-02) → "Впереди {N} дней" (render only)
  expiringSoon: boolean         // optional subtle treatment (NOT required)
Endpoint returns 200 with body `null` (data: null) when there is no active membership.

Existing payment status hook data (clientQueries.ts — PaymentStatusData):
  status: 'pending' | 'succeeded' | 'canceled'
  receiptUrl?: string | null    // "Открыть чек" rendered ONLY when non-null (D-11)
  receiptEmail?: string | null  // receipt destination chip (succeeded only)
  receiptPhone?: string | null

useClientMe() data (ClientMeData): firstName, lastName, phone, email, ...
  Greeting "Ты в команде, {firstName}"; fallback "Ты в команде!" when firstName absent.

Existing read-hook pattern to mirror (clientQueries.ts):
  export function useClientHome() {
    return useQuery({
      queryKey: clientPortalKeys.home(),
      queryFn: async () => {
        const res = await clientRequest('get', '/api/v1/client/home')
        return (res as { data: HomeData }).data
      },
      staleTime: 30_000,
    })
  }
The key factory already has `membership: () => [...clientPortalKeys.all, 'membership'] as const`.

Icon component (components/Icon.jsx) — confirmed available names:
  check, mail, arrowRight, chevronRight, qr, x, star, starFill
Usage: <Icon name="check" size={44} strokeWidth={2.6} color="#06120c" />

styles.css / mockup token parity (CONFIRMED — mockup tokens already match styles.css):
  --accent #2dd4a4, --accent-deep #0f9b76, --accent-soft, --surface, --surface-2,
  --border, --border-strong, --text/-2/-3, --r-md/-lg/-pill, --sh-1/-2.
  Dark theme is keyed off `[data-theme="dark"]`. The ONLY sanctioned raw hex is #06120c (on-accent).
  styles.css uses NO Tailwind — author plain CSS classes with a `.pa-*` prefix
  (mirrors the `.co-*` convention from quick task 260601-sxf; do NOT collide with existing `.state*`).

CLAUDE.md date rule: NEVER `new Date(dateOnlyString)` (DST risk). Parse the ISO
"YYYY-MM-DD" string by splitting on '-' and index a genitive month-name table.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add useClientMembership read hook + formatRuDate helper</name>
  <files>
    apps/client-pwa/src/lib/clientQueries.ts,
    apps/client-pwa/src/data/index.js,
    apps/client-pwa/src/utils/format.js
  </files>
  <action>
    In clientQueries.ts: add a `ClientMembershipData` interface (camelCase fields: id,
    planNameSnapshot, startDate, endDate, status, daysUntilEnd, expiringSoon — all matching
    the ClientMembershipResponse wire shape in the interfaces block). Add a read hook
    `useClientMembership(enabled = true)` immediately after `useClientHome`, mirroring the
    useClientHome pattern: queryKey `clientPortalKeys.membership()` (already exists in the
    factory), queryFn does `clientRequest('get', '/api/v1/client/membership')` and returns
    `(res as { data: ClientMembershipData | null }).data`, with `enabled`, `staleTime: 30_000`.
    The `enabled` param is the anti-oracle gate (D-10) — the caller passes
    `data?.status === 'succeeded'` so membership is never fetched during pending.

    In data/index.js: add `useClientMembership` to the existing re-export block from
    '../lib/clientQueries' (the swap-seam barrel, D-71-07), next to useClientHome.

    In utils/format.js: add `export function formatRuDate(isoDateOnly)` that renders an ISO
    date-only string "YYYY-MM-DD" as a ru long date "27 ноября 2026". Parse by splitting on
    '-' (do NOT call `new Date(dateOnlyString)` — CLAUDE.md DST rule); index a genitive
    full-month-name table ['января','февраля','марта','апреля','мая','июня','июля','августа',
    'сентября','октября','ноября','декабря']. Return '' on falsy/malformed input so the caller
    can guard. Keep the existing monthName (short nominative) untouched — formatRuDate is a
    separate genitive long-form helper.
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm typecheck && pnpm lint</automated>
  </verify>
  <done>
    `useClientMembership` is exported from clientQueries.ts and re-exported from data/index.js;
    `formatRuDate` is exported from utils/format.js and returns "27 ноября 2026" for "2026-11-27"
    and '' for empty/malformed input. typecheck + lint pass.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Add .pa-* success-screen styles to styles.css</name>
  <files>apps/client-pwa/src/styles.css</files>
  <action>
    Append a new section of `.pa-*` classes (NO Tailwind, semantic tokens only, sole raw hex
    #06120c). Port ONLY the in-scope success aesthetic from the mockup (`~/Downloads/Plan Activated.html`),
    stripping device frame, status bar, home indicator, .tweaks panel/script, .auto-strip
    auto-dismiss, toast, postMessage, count-up JS, perks, validity progress, achievement chip,
    and the QR-pass CTA. Required classes/animations:
      - `.pa-screen` scroll container (flex column, padding mirroring the mockup `.body`).
      - `.pa-check-hero` 104px round medallion: background var(--accent), color #06120c,
        layered accent-soft ring box-shadows, `check-pop 0.6s` entrance.
      - `.pa-check-hero::before/::after` continuous radiating `wave-out` rings (delays 0 / 2s).
      - check `<svg> path` stroke-draw via `check-draw` (stroke-dasharray/offset 60).
      - `.pa-confetti` + `.pa-confetti i` 8 dots with per-child --tx/--ty/--rot custom props and
        `confetti-out` burst (copy the 8 nth-child definitions; keep #fbbf24 / #f87171 accent dots
        — these are decorative confetti colors, acceptable per "no raw hex except #06120c" intent;
        if lint's raw-palette rule flags hex in CSS it does not — that ESLint rule targets Tailwind
        classes in TSX, not styles.css. Keep the confetti hexes.).
      - `.pa-title` (28px, fade-up 0.45s delay), `.pa-sub` (15px, var(--text-2), fade-up 0.55s),
        `.pa-card` plan card (surface, 0.5px border, --r-lg, --sh-2, fade-up 0.65s),
        `.pa-card-head` (name + badge row), `.pa-card-name`, `.pa-badge` (accent-soft pill, accent-deep),
        `.pa-card-meta` (12.5px var(--text-2)), `.pa-days` "Впереди N дней" line,
        `.pa-receipt-chip` (mirrors the existing succeeded receipt chip styling), `.pa-actions`
        bottom CTA stack (fade-up 0.75s).
      - Reuse the existing `.btn`/`.btn-accent`/`.btn-ghost` classes already in styles.css for the CTA;
        do NOT redefine them.
      - A single `@media (prefers-reduced-motion: reduce)` block that sets `animation: none` (and
        sets the entrance elements to their resting opacity/transform) for ALL .pa-* animated
        elements: medallion, waves, check-draw, confetti, and every fade-up element. Reduced motion
        must show the final state immediately with no movement.
    Add a `.pa-*` dark-theme review: the tokens already adapt via [data-theme="dark"], so no
    per-class dark override should be needed — confirm visually in Task 3's checkpoint.
  </action>
  <verify>
    <automated>cd apps/client-pwa && grep -v '^[[:space:]]*\/\*' src/styles.css | grep -c 'pa-check-hero\|pa-confetti\|pa-card\|prefers-reduced-motion'</automated>
  </verify>
  <done>
    styles.css contains the `.pa-*` class set with check-pop / wave-out / check-draw / confetti-out /
    fade-up keyframes and a prefers-reduced-motion guard covering all .pa-* animations. No Tailwind.
    Grep count is non-zero. typecheck/lint deferred to Task 3 (no TSX touched yet).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Rebuild PaymentSucceededView with the Plan Activated design</name>
  <files>apps/client-pwa/src/routes/PaymentReturnScreen.jsx</files>
  <what-built>
    Rebuilt ONLY the `PaymentSucceededView` function (≈ lines 149-231). The pending view,
    `PaymentCanceledView`, the polling logic, and `useClientPaymentStatus` are byte-for-byte
    unchanged. The new view:
      - Renders only inside the existing `data?.status === 'succeeded'` branch (unchanged caller; anti-oracle preserved).
      - Calls `useClientMe()` for firstName and `useClientMembership(data?.status === 'succeeded')`
        for the real membership (D-10 gate — never fetched during pending).
      - Markup top-to-bottom using the new `.pa-*` classes:
        1. `.pa-check-hero` medallion with `.pa-confetti` (8 `<i>`) and the `<Icon name="check" size={50} color="#06120c" />` (drawn via CSS).
        2. `.pa-title`: "Ты в команде, {firstName}" — fallback "Ты в команде!" when firstName is absent (no trailing comma/name).
        3. `.pa-sub`: truthful sub copy, e.g. "Оплата подтверждена. Доступ активен." — NO hardcoded plan duration.
        4. `.pa-card` plan card, rendered ONLY when the membership query returned non-null data:
           name = planNameSnapshot; badge "Активен" when status==='active'; meta "Действует до {formatRuDate(endDate)}";
           "Впереди {daysUntilEnd} дней". OMITTED (no clean data): progress %, perks, "Списано · сумма", achievement chip.
        5. Receipt destination chip — `(receiptEmail || receiptPhone)` (preserved from current view).
        6. `.pa-actions`: "Открыть чек" link ONLY when `receiptUrl` non-null (D-11), then a SINGLE primary
           "Хорошо" button → `onDone()` (which navigates '/' replace). NO "Открыть QR-пропуск" button.
      - a11y preserved/added: focus the primary CTA on mount (existing primaryBtnRef pattern); aria-live
        on the success region; aria-label on the decorative check medallion / icon-only elements; confetti
        marked aria-hidden.
      - prefers-reduced-motion handled entirely in CSS (Task 2) — no motion when reduced.
    All client-pwa checks run green: `pnpm typecheck && pnpm lint && pnpm test && pnpm build`.
  </what-built>
  <how-to-verify>
    1. cd apps/client-pwa && pnpm dev (note the dev URL, typically http://localhost:5173).
    2. Drive a succeeded payment return so PaymentReturnScreen lands on status==='succeeded'
       (use the backend dev login + YooKassa test creds per memory; or point the return_url at a
       payment_id whose status the dev backend reports 'succeeded'). Confirm:
       a. Animated check medallion draws + pops, radiating waves loop, confetti bursts once.
       b. Headline reads "Ты в команде, {your firstName}" (or "Ты в команде!" if no name on the account).
       c. Plan card shows the real active plan name, "Активен" badge, "Действует до {ru date}", "Впереди N дней".
       d. If the account has NO active membership (membership endpoint returns null): the card is absent,
          rest of screen still renders cleanly.
       e. Receipt chip shows email or phone; "Открыть чек" appears ONLY if a receiptUrl exists.
       f. Single "Хорошо" button is focused on mount and navigates to '/' (replace). NO QR-pass button.
    3. Toggle dark theme (data-theme="dark" on <html>, or the app's theme control) — verify both themes read well.
    4. Enable OS "Reduce Motion" and reload — verify NO animation/movement; final state shown immediately.
    5. Anti-oracle check: while a payment is still pending, confirm the membership request is NOT fired
       (Network tab shows no /client/membership call until status flips to succeeded) and no activation
       details appear on the pending spinner screen.
    6. Confirm pending view + canceled view are visually unchanged from before.
  </how-to-verify>
  <resume-signal>Type "approved" or describe visual/behaviour issues (per item a–f, dark theme, reduced motion).</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ЮKassa redirect → PWA return route | Untrusted query params (`payment_id`, `idempotency_key`) land on PaymentReturnScreen. |
| PWA → backend client API | `/client/membership`, `/client/payments/{id}/status` cross the client-auth boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-vxr-01 | Information Disclosure | Premature reveal of activation state (anti-oracle, D-10) | mitigate | `useClientMembership` gated `enabled: data?.status === 'succeeded'`; the whole view renders only inside the succeeded branch; pending screen unchanged. |
| T-vxr-02 | Information Disclosure | Plan card over-exposing economics | accept | Render only client-safe fields from ClientMembershipResponse (D-69-05); price/duration are owner-only and OMITTED by design — no new fields fetched. |
| T-vxr-03 | Tampering | npm/pnpm installs | mitigate | No new dependencies added (hook reuses existing clientRequest; styles are hand-authored CSS). No install step, so no package-legitimacy gate required. |
</threat_model>

<verification>
- `cd apps/client-pwa && pnpm typecheck && pnpm lint && pnpm test && pnpm build` all pass.
- Membership request is NOT issued while status is pending (anti-oracle, T-vxr-01).
- Plan card omitted gracefully when membership is null.
- Light + dark both render; reduced motion suppresses all animation.
- Pending view, PaymentCanceledView, and polling logic are unchanged (git diff scoped to PaymentSucceededView + the four other files).
</verification>

<success_criteria>
- New "Plan Activated" success screen renders on confirmed succeeded with animated check hero, confetti, personalized greeting, real plan card, and single "Хорошо" CTA.
- Plan card data is 100% real (planNameSnapshot, status badge, endDate ru date, daysUntilEnd); no fabricated perks/economics/progress.
- D-10 anti-oracle gate (enabled on succeeded) and D-11 conditional receipt link both honored.
- a11y (focus, aria-live, aria-labels) and prefers-reduced-motion respected; both themes pass human visual review.
- Frontend-only: no backend/migration/endpoint changes; the only non-component addition is useClientMembership.
</success_criteria>

<output>
Create `.planning/quick/260601-vxr-plan-activated-client-pwa-paymentsucceed/260601-vxr-SUMMARY.md` when done.
</output>
