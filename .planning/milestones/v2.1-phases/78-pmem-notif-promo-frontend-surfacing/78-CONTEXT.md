# Phase 78: PMEM/NOTIF/PROMO Frontend Surfacing - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 3 grey areas accepted as recommended

<domain>
## Phase Boundary

Surface the three backend-complete v2.1 fields in the `apps/client-pwa` UI — closes the v2.1 milestone-audit frontend-surfacing tech debt. Three independent, mostly-wiring deliverables (no backend changes; Phase 75 shipped all fields/endpoints):

1. **PMEM-01 (frontend)** — the Profile membership hero shows the client's membership price (`priceKopecks` → ₽) and an auto-renew indicator (`autoRenew`), sourced from `useClientMembership()`.
2. **NOTIF-01 (frontend)** — the Settings notification toggles become server-backed: hydrate from `GET /client/me` `notifPrefs`, save via `PATCH /client/me` (full 4-key replace). localStorage is dropped as the store.
3. **PROMO-01 (frontend)** — the recommended FIT15 promo chip in checkout is surfaced (flag flip); the chip + apply handler + validation already exist and are complete.

**NOT in this phase:** no backend changes; no restyle of Profile/Settings/Checkout beyond the single new PMEM-01 price/auto-renew row; no autopay (autoRenew stays null-driven); no promo admin CRUD; no new screens. The active/lapsed Home, checkout payment path, and auth are untouched.

</domain>

<decisions>
## Implementation Decisions

### PMEM-01 — Profile price + auto-renew (accepted recommended)
- **D-78-01:** Add `useClientMembership()` to `ProfileScreen.jsx` (currently only `useClientHome()`). Render `priceKopecks` via `formatMoney()` (kopecks→₽ ru-RU) as a new row in the `.membership-hero` card (the block at ~lines 138-219; remove the "Price/auto-renew block deliberately omitted" comment at line 138). Match the existing hero row typography/tokens — no new visual language.
- **D-78-02:** Auto-renew row: render an indicator driven by `autoRenew`. When `autoRenew === null` (no autopay concept today, D-75-01), HIDE the auto-renew row entirely (do not show "—"). When it becomes a real boolean in a future autopay milestone, show on/off.
- **D-78-03:** Loading / no active membership: show nothing extra (no skeleton price row); the price/auto-renew rows render only when `useClientMembership()` returns a real membership with a `priceKopecks`.

### NOTIF-01 — Settings toggles → backend (accepted recommended)
- **D-78-04:** Server is the source of truth. `SettingsScreen.jsx` hydrates the 4 toggles (promo/schedule/trainer/sound) from `useClientMe()` `notifPrefs` instead of `localStorage['clubcore:notif:v1']` + `NOTIF_DEFAULTS`.
- **D-78-05:** DROP localStorage as the persistence store (NOTIF-01's explicit intent: "сохраняется на сервере … а не только localStorage"). Remove the `NOTIF_STORAGE_KEY` read/write. (`NOTIF_DEFAULTS` may stay only as a render fallback before server data arrives, but the server's defaults — same 4 keys — are authoritative.)
- **D-78-06:** Toggle UX: optimistic flip in local state, then `useUpdateClientProfile().mutateAsync({ notifPrefs: { promo, schedule, trainer, sound } })` — FULL 4-key replace (D-05). On failure, revert the optimistic flip and show an error toast (mirror the ProfileExtraSheets inline-error/co-toast pattern). On success, the `me()` invalidation keeps it consistent.
- **D-78-07:** Extend the `useUpdateClientProfile` mutation payload TYPE in `clientQueries.ts` (~217-239) to include `notifPrefs?: { promo: boolean; schedule: boolean; trainer: boolean; sound: boolean }` (the backend `ClientProfileUpdateRequest` already accepts `notif_prefs`/`notifPrefs`). The PATCH body passes it through.
- **D-78-08:** Persistence must survive a full reload / fresh session (success-criterion #2) — verified by the server round-trip, not localStorage.

### PROMO-01 — FIT15 chip (accepted recommended)
- **D-78-09:** Flip `CHECKOUT_FEATURE_FLAGS.recommendedPromo` from `false` to `true` in `CheckoutSheet.jsx` (~line 46). The chip JSX, `handlePromoApply('FIT15')`, and `usePromoValidate` flow are already complete — this is the "flag flip" the milestone premised.
- **D-78-10:** Keep the existing gate: chip renders only when `recommendedPromo` is on AND `!promoResult` (hidden once any promo is applied). Verify the chip surfaces in BOTH checkout contexts (sub + pt) and that one tap applies FIT15 and shows the discounted amount.

### Claude's Discretion
- Exact label/copy for the PMEM-01 price row ("Стоимость" + formatted price) and auto-renew indicator wording; whether NOTIF toggle errors use a co-toast vs inline banner — follow existing SettingsScreen/ProfileExtraSheets conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / milestone scope
- `.planning/ROADMAP.md` §"Phase 78" — goal + 3 success criteria.
- `.planning/v2.1-MILESTONE-AUDIT.md` — the tech-debt items this phase closes (PMEM-01/NOTIF-01/PROMO-01 frontend surfacing).
- `.planning/REQUIREMENTS.md` — PMEM-01, NOTIF-01, PROMO-01 (the user-facing halves).

### PMEM-01 files
- `apps/client-pwa/src/screens/ProfileScreen.jsx` — membership hero (~138-219); currently `useClientHome()` only (~73) + `toSubInfo()` (~79). Add `useClientMembership()`.
- `apps/client-pwa/src/lib/clientQueries.ts` — `useClientMembership()` + `ClientMembershipData` (now includes `priceKopecks`/`autoRenew`, ~143-175).
- `apps/client-pwa/src/utils/format.js` — `formatMoney(kopecks)` (~8-15).

### NOTIF-01 files
- `apps/client-pwa/src/screens/SettingsScreen.jsx` — notif state + `NOTIF_DEFAULTS` + `NOTIF_STORAGE_KEY` (~22-55), `SettingRow` toggles (~228-256, component ~310-349).
- `apps/client-pwa/src/lib/clientQueries.ts` — `useUpdateClientProfile()` (~217-239, add `notifPrefs` to payload type), `useClientMe()` (`ClientMeData.notifPrefs` now declared).
- `apps/backend/app/modules/client_portal/schemas.py` — `ClientProfileUpdateRequest.notif_prefs` + `NotifPrefs` strict 4-key (~283-340). Read-only (already accepts it).

### PROMO-01 files
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — `CHECKOUT_FEATURE_FLAGS.recommendedPromo` (~46), `RECOMMENDED_PROMO` (~50), chip JSX (~451-465), `handlePromoApply` (~160-181), `usePromoValidate` (imported ~4). `.co-rec-chip`/`.co-promo-rec` styles already in styles.css.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useClientMembership()` already returns `priceKopecks`/`autoRenew` (interface completed during the v2.1 audit) — PMEM-01 is a render-only add.
- `useUpdateClientProfile()` already PATCHes `/client/me` + invalidates `me()`/`home()`; NOTIF-01 only needs the `notifPrefs` field added to its payload type and the SettingsScreen wiring.
- The FIT15 chip + `handlePromoApply` + `usePromoValidate` are fully built; PROMO-01 is a one-line flag flip + verification.
- `formatMoney`, the co-toast pattern, and the SettingRow toggle component all exist.

### Established Patterns
- Optimistic-update + invalidate + error-toast/rollback (mirror Phase 76 ProfileExtraSheets save).
- camelCase wire (`priceKopecks`, `autoRenew`, `notifPrefs`); money in kopecks.
- `handlePromoApply` accepts a string code OR a click event (typeof guard) — the chip passes the string.

### Integration Points
- PMEM-01: `useClientMembership()` → ProfileScreen membership hero rows.
- NOTIF-01: `useClientMe().notifPrefs` → SettingsScreen toggles → `useUpdateClientProfile({notifPrefs})` → `PATCH /client/me`.
- PROMO-01: `recommendedPromo: true` → existing chip → `handlePromoApply('FIT15')` → `usePromoValidate` → discount.

</code_context>

<specifics>
## Specific Ideas

- This phase is the deliberate completion of the v2.1 audit's frontend-surfacing debt — keep it tight: one Profile row, one Settings wiring, one flag flip.
- localStorage notif persistence is intentionally removed (server is the point of NOTIF-01), not merely supplemented.
- autoRenew stays null-driven (hidden) until a future autopay milestone gives it a real value.

</specifics>

<deferred>
## Deferred Ideas

- Autopay / card-on-file (would make `autoRenew` a real boolean) — Group-B net-new domain, future milestone.
- Promo-code admin CRUD UI — already deferred (admin-web frozen).
- Tweak/server-config control of the recommendedPromo flag — out of scope; a hardcoded flip suffices for v2.1.

</deferred>

---

*Phase: 78-pmem-notif-promo-frontend-surfacing*
*Context gathered: 2026-06-02 via smart discuss (autonomous)*
