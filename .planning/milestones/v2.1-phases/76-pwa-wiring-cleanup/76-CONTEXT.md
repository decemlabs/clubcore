# Phase 76: PWA Wiring + Cleanup - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — all 4 grey areas accepted as recommended

<domain>
## Phase Boundary

Pure-frontend wiring of `apps/client-pwa` to existing backend client-portal endpoints, plus one mock-removal cleanup. Three deliverables:

1. **NHOME-01 / NHOME-02** — the newbie Home screen renders real trainer avatars (live count + overflow) from `GET /client/trainers` and a plan info chip (count + minimum monthly price) from `GET /client/plans`, replacing the static `TRAINERS` mock slice and the hardcoded tariff/price strings.
2. **PDATA-01 / PDATA-02** — the Personal Data sheet reads the client's real profile from `GET /client/me` and saves edits via `PATCH /client/me` (persisting across reload).
3. **CLEAN-01** — the mock chat unread-badge is removed: the `CONVERSATIONS` import is gone from `App.jsx` and the badge shows 0 / is hidden.

**NOT in this phase:** no backend changes (Phase 75 added all needed fields/endpoints; `GET /client/trainers`, `/client/plans`, `/client/me` already exist and ship the needed shapes); no new chat feature; no changes to active-subscription Home, checkout, or auth; no DOB/Gender backend persistence (no such columns — those rows stay local-only demo); `tier`/tenure excluded (v2.1 exclusion). The milestone's "feature-flag flip" framing does not apply — **the PWA has no feature-flag mechanism**; wiring is direct (gated only by the existing `membershipState === 'newbie'` render branch).

</domain>

<decisions>
## Implementation Decisions

### Trainer avatars on newbie Home (NHOME-01)
- **D-76-01:** Add a `useClientTrainers()` TanStack Query hook (mirrors `useClientPlans()` in `src/lib/clientQueries.ts`) calling `GET /api/v1/client/trainers`. No such hook exists today.
- **D-76-02:** The backend returns only `{ id, full_name }` per trainer (`ClientCatalogTrainerResponse`) — NO initials/color/avatar. Derive the avatar visual **client-side**: initials from `full_name` (first letter(s)), and a deterministic color from a fixed palette indexed by position/id. Do NOT extend the backend (out of scope; Phase 75 is closed).
- **D-76-03:** Keep the current "first 3 avatars + (+N)" layout; `N = liveTrainerCount − 3`. The overflow counter reflects the live count from the endpoint.
- **D-76-04:** Loading → skeleton/current placeholder; on error or empty list → graceful fallback (existing placeholder), never crash the Home screen.
- **D-76-05:** Keep the static `TRAINERS` mock in `src/data/trainers.js` — the Trainers tab and chat screens still consume it and are out of scope. Only the newbie-Home avatar strip + overflow counter switch to live data.

### Plan info chip (NHOME-02)
- **D-76-06:** "Minimum monthly price" = `min(price_kopecks ÷ (duration_days / 30))` across all plans from `GET /client/plans` — normalizes longer plans to a comparable monthly figure (e.g. a yearly plan reduced to its per-month cost).
- **D-76-07:** "count" in the chip = live count of plans returned by `/client/plans`.
- **D-76-08:** Format the price with the PWA's money formatter (kopecks → ₽, ru-RU).
- **D-76-09:** Show the existing hardcoded string as the fallback while loading and on error — never block the Home render on the plans fetch.

### Personal Data sheet wiring (PDATA-01, PDATA-02)
- **D-76-10:** Read `name (firstName/lastName)`, `phone`, `email`, `goal`, `height (heightCm)`, `weight (weightKg)` from `GET /client/me` via the existing `useClientMe()` hook — replacing the hardcoded placeholder values in `src/screens/sheets/ProfileExtraSheets.jsx`.
- **D-76-11:** DOB and Gender have **no backend field** in `ClientMeResponse` — they remain local-only/demo (NOT persisted). No backend scope creep. (Rows stay visible per accepted Area 3 option "keep local-only".)
- **D-76-12:** Editable fields saved via `PATCH /client/me` (`useUpdateClientProfile()`): `firstName`, `email`, `goal`, `heightCm`, `weightKg`. Height/weight become editable numeric inputs (currently read-only display). Phone changes keep the existing SMS-verify flow (PATCH does not write phone). `lastName` is not writable by PATCH — treat as read-only.
- **D-76-13:** On save, call the existing `useUpdateClientProfile` mutation and invalidate the `clientMe` query so the sheet reflects persisted values; surface failures via an error toast. Change must persist across a full page reload (success-criterion #4).

### Chat badge cleanup (CLEAN-01)
- **D-76-14:** Remove the `CONVERSATIONS` import from `apps/client-pwa/src/App.jsx` (line ~17) and the `unreadChat` reduce computation (line ~223). Success-criterion #5 requires the `CONVERSATIONS` import to be absent from `App.jsx`.
- **D-76-15:** Pass `unreadChat={0}` to `<TabBar>` so the badge is hidden/zero (TabBar already hides at 0). Do not remove the badge UI element itself.
- **D-76-16:** Keep `src/data/conversations.js` if any Chat screen still imports it; only the `App.jsx` usage is removed. (Verify importers during planning; delete the file only if orphaned.)

### Claude's Discretion
- Exact palette values for D-76-02, skeleton styling, query-key naming for `useClientTrainers`, and test placement follow existing PWA conventions — not user decisions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / milestone scope
- `.planning/ROADMAP.md` §"Phase 76: PWA Wiring + Cleanup" — goal + 5 success criteria.
- `.planning/REQUIREMENTS.md` — NHOME-01, NHOME-02, PDATA-01, PDATA-02, CLEAN-01.

### PWA files to modify
- `apps/client-pwa/src/screens/HomeScreen.jsx` — `HomeNewbie` (trainer avatars ~957-982), `HeroNewbie` tariff/price block (~330-335). Targets for NHOME-01/02. Newbie gate: `homeData?.membershipState === 'newbie'` (~292).
- `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` (~39-155) — Personal Data sheet; currently hardcoded fields + demo save (PDATA-01/02).
- `apps/client-pwa/src/App.jsx` — `CONVERSATIONS` import (~17), `unreadChat` reduce (~223), `<TabBar unreadChat=.../>` (~457). Target for CLEAN-01.
- `apps/client-pwa/src/lib/clientQueries.ts` — TanStack Query hooks + `clientPortalKeys`; add `useClientTrainers()` mirroring `useClientPlans()` (~308-317). Uses `clientRequest()` from `./clientFetcher.ts`.

### Backend contracts (read-only — already shipped, do NOT change)
- `apps/backend/app/modules/client_portal/router.py` — `GET /trainers` (~310-325, `ClientCatalogTrainerResponse` = `id` + `full_name`), `GET /plans` (~274-289, `id`/`name`/`price_kopecks`/`duration_days`), `GET /me` + `PATCH /me` (~717-780, `ClientMeResponse`: firstName/lastName/phone/email/goal/heightCm/weightKg/onboardingCompletedAt; PATCH writes firstName/goal/heightCm/weightKg/onboardingCompleted/email).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useClientMe()`, `useClientPlans()`, `useUpdateClientProfile()` already exist in `src/lib/clientQueries.ts` — Area 3 + plan chip reuse them directly; only `useClientTrainers()` is missing.
- TanStack React Query is the established data layer; `clientRequest()` (`clientFetcher.ts`) is the typed transport; `clientPortalKeys` is the query-key factory.
- A money formatter exists in the PWA for kopecks→₽ display (mirror its usage for D-76-08).

### Established Patterns
- Query hook pattern: `useQuery({ queryKey: clientPortalKeys.X(), queryFn: async () => (await clientRequest('get', '/path')).data, staleTime: 30_000 })`.
- Newbie Home renders behind `membershipState === 'newbie'`; no feature flags anywhere in the PWA (TweaksContext is dev-only, not a feature-gate).

### Integration Points
- `useClientTrainers()` → `HomeNewbie` avatar strip + overflow counter (NHOME-01).
- `useClientPlans()` → newbie-Home plan info chip (NHOME-02).
- `useClientMe()` + `useUpdateClientProfile()` → `ProfileExtraSheets.jsx` (PDATA-01/02).
- `App.jsx` TabBar `unreadChat` prop (CLEAN-01).

</code_context>

<specifics>
## Specific Ideas

- Trainer avatar visuals are derived client-side (initials + deterministic palette) because the backend trainers endpoint intentionally exposes only `id` + `full_name` (minimal client catalog) — keep it that way.
- "Minimum monthly price" is a normalized per-month figure (price ÷ months), not a raw min price, so a cheap long-duration plan reads as its true monthly cost.
- DOB/Gender intentionally stay client-local: no backend column exists and Phase 75 (the backend phase) is closed — adding columns would be out-of-milestone scope.

</specifics>

<deferred>
## Deferred Ideas

- Real chat / conversations feature (the removed mock badge) — future milestone; CLEAN-01 only removes the mock, it does not build chat.
- Backend trainer catalog enrichment (avatar image, rating, price) — not needed; client derives visuals. Future if a richer Trainers screen is wired to live data.
- DOB/Gender backend persistence — would require new `clients` columns + schema/migration; deferred to a future backend milestone.

</deferred>

---

*Phase: 76-pwa-wiring-cleanup*
*Context gathered: 2026-06-02 via smart discuss (autonomous)*
