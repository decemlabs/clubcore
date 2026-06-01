# Quick Task 260601-vxr: "Plan Activated" success screen - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Task Boundary

Replace the visual of the payment-success state (`PaymentSucceededView` inside
`apps/client-pwa/src/routes/PaymentReturnScreen.jsx`) with the new "Plan Activated"
design (reference mockup `~/Downloads/Plan Activated.html`), AND add a real
membership plan card fed by the existing `GET /client/membership` endpoint.

Frontend-only. The one allowed non-visual addition is a small read hook
`useClientMembership()` in `apps/client-pwa/src/lib/clientQueries.ts` (the endpoint
already exists; only the query key + invalidation exist client-side today). NO
backend changes.
</domain>

<decisions>
## Implementation Decisions (LOCKED — do not revisit)

### Plan card — REAL, via existing endpoint (user chose "сделать по-настоящему")
- Data source: `GET /client/membership` (`ClientMembershipResponse | None`), via a NEW
  client read hook `useClientMembership(enabled)`. Fields available and to render:
  - `planNameSnapshot` → card name (e.g. "Полугодовой")
  - `status` → "Активен" badge when `status === 'active'`
  - `endDate` → "Действует до {formatted ru date}"
  - `daysUntilEnd` → "Впереди {N} дней" (server-computed; render only)
  - `expiringSoon` → optional subtle treatment (not required)
- **Anti-oracle (D-10):** the membership query MUST be gated `enabled: status === 'succeeded'`
  — never fetch/show membership details during pending. Nothing about activation
  may render until the server-confirmed succeeded branch.
- Render the card only when the membership query returns non-null data (endpoint
  returns 200 `null` when no active membership — handle gracefully: omit the card).

### Omitted from the mockup (no clean data source — do NOT fabricate)
- **Exact progress-bar %**: needs total plan duration; `durationDaysSnapshot` is
  owner-only (D-69-05) and not exposed to the client. Show "Впереди N дней" without a
  precise %. A purely decorative bar is acceptable but not required.
- **Perks list** ("Зал круглосуточно", "14 дней заморозки", "Сауна без лимита"):
  marketing copy with no field in the membership model. OMIT.
- **"Списано · сумма ₽"**: membership response excludes price (owner-only, D-69-05).
  OMIT by default. (Could later come from the existing `payment-history` endpoint's
  `amountKopecks`, but matching this specific payment is heuristic — not in scope.)
- **Achievement chip** ("Новый участник клуба"): gamification with no data. OMIT.
- **Auto-dismiss strip** (4s countdown → auto-navigate): VIOLATES D-10 ("navigate to
  '/' only after the user taps the CTA"). OMIT entirely.

### CTA (user chose "Только «Хорошо» → главная")
- Single primary button "Хорошо" → `navigate('/', { replace: true })` (preserves
  current behavior). Do NOT add the mockup's "Открыть QR-пропуск" button.

### Greeting / copy
- Personalized headline "Ты в команде, {firstName}" via `useClientMe()` (`firstName`
  available). Safe fallback when name absent: "Ты в команде!" (no trailing comma/name).
- Sub copy: keep it truthful to confirmed state, e.g. "Оплата подтверждена. Доступ
  активен." Do NOT hardcode a specific plan duration in the sub (the card carries plan
  specifics from real data).

### Visual (full transfer of the mockup's success aesthetic)
- Animated check hero (104px accent medallion, check-draw, pop, radiating waves) +
  confetti burst. Respect `prefers-reduced-motion` (no motion when reduced).
- Fade-up entrance for headline/sub/card/CTA.
- Light + dark via existing `styles.css` CSS custom properties; the mockup tokens
  already match. No raw hex except sanctioned `#06120c` (on-accent).

### Locked decisions to PRESERVE (D-10/D-11 + a11y)
- This view renders ONLY on `data.status === 'succeeded'` (anti-oracle) — unchanged.
- Receipt destination chip (`receiptEmail || receiptPhone`) — keep.
- "Открыть чек" link — render ONLY when `receiptUrl` is non-null (D-11).
- a11y: focus the primary CTA on mount; aria-live on the success region; aria-labels
  on icon-only elements. Keep `formatMoney()` for any money (if a money value is shown).
- Only `PaymentSucceededView` changes. The pending state, `PaymentCanceledView`, and
  the polling logic stay byte-for-byte.
</decisions>

<specifics>
## Specific Ideas

- Reference mockup: `~/Downloads/Plan Activated.html` (device-framed; only `.screen`
  contents in scope — strip device frame, status bar, home indicator, `.tweaks`
  panel + script, `.auto-strip` auto-dismiss, postMessage hooks).
- Target file: `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` (function
  `PaymentSucceededView`, ~lines 149-231).
- Shared styles: `apps/client-pwa/src/styles.css` (add classes there; NO Tailwind).
- New hook: `useClientMembership(enabled)` in `apps/client-pwa/src/lib/clientQueries.ts`
  — GET `/api/v1/client/membership`, key `clientPortalKeys.membership()`.
- Existing data: `useClientMe()` (firstName), `useClientPaymentStatus` data
  (`status`, `receiptUrl`, `receiptEmail`, `receiptPhone`).
- Backend shape (read-only reference): `ClientMembershipResponse` —
  `plan_name_snapshot`, `end_date`, `status`, `days_until_end`, `expiring_soon`
  (wire is camelCase: planNameSnapshot, endDate, daysUntilEnd, expiringSoon).
</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/999.4-client-pwa-checkout-visual-restyle/999.4-UI-SPEC.md`
  (design system, tokens, .state pattern, a11y, copywriting contract).
- `PaymentReturnScreen.jsx` top doc block (anti-oracle criterion #1, D-10, D-11).
- D-69-02 (server-computed days_until_end), D-69-05 (client-safe membership fields,
  owner-only economics excluded).
- Prior quick task 260601-sxf established the `.co-*` styling conventions for the
  checkout v2 restyle — match that naming/token discipline.
</canonical_refs>

<revision-1>
## REVISION 1 (2026-06-01) — pivot to full visual 1:1

User reviewed the first build against the mockup and wants a pixel-faithful 1:1.
The earlier "omit for data-honesty" calls are SUPERSEDED. Restore every mockup
element, sourcing data honestly where it exists and static/derived where it doesn't:

- **Achievement chip "Новый участник клуба"** — RESTORE. Static celebratory badge
  (star icon + label). Always shown.
- **Validity progress bar + "100%"** — RESTORE. At the activation moment the full
  term is ahead, so a full bar at "100%" is correct here. Keep the real
  "Впереди {daysUntilEnd} дней" number alongside.
- **Perks list** ("Зал круглосуточно", "14 дней заморозки в подарок", "Сауна и
  групповые без лимита") — RESTORE as HARDCODED static copy (no API field exists for
  perks; plans expose only name/price/duration). Show for membership (kind 'sub')
  success; acceptable as fixed gym copy for this single-gym project.
- **"Списано · {сумма} ₽"** — RESTORE with the REAL paid amount from the existing
  `payment-history` endpoint (`ClientPaymentItem.amountKopecks`, signed). Use a new
  `useClientPaymentHistory`-based read: pick the most recent online, positive-amount
  item (the just-completed payment). Format with `formatMoney`. If none found, hide
  the amount line but keep "Открыть чек".
- **CTA — RESTORE BOTH buttons (supersedes the earlier "only Хорошо" decision):**
  primary "Открыть QR-пропуск" + secondary "На главную". Wire "Открыть QR-пропуск" to
  actually open the client QR pass (the app opens it via `ui.setQrOpen(true)`, which
  lives in the main shell, not on the `/payment/return` route) — navigate to '/' and
  signal the shell to open the QR sheet (e.g. `navigate('/', { state: { openQr: true } })`
  and have App read `location.state.openQr` once to call `setQrOpen(true)`; keep the
  signal minimal and one-shot). "На главную" → `navigate('/', { replace: true })`.

STILL PRESERVED (do not regress): anti-oracle (membership + payment-history fetched
only when `data.status === 'succeeded'`); render only on succeeded; "Открыть чек" only
when `receiptUrl` non-null (D-11); a11y (focus a primary CTA on mount, aria-live,
aria-labels); `prefers-reduced-motion` (no motion); light + dark via tokens; pending
view, PaymentCanceledView, and polling untouched. The mockup's `.auto-strip`
auto-dismiss is NOT in the mockup's DOM body (vestigial CSS/JS) — do not add it.
</revision-1>

<deferred>
## Deferred / optional follow-ups
- "Списано · сумма" line — could be wired from the existing `payment-history` endpoint
  if the user later wants the amount shown on the success screen.
- Precise validity progress % — would need a client-safe total-duration field
  (currently owner-only); a backend change, out of scope.
</deferred>
</content>
