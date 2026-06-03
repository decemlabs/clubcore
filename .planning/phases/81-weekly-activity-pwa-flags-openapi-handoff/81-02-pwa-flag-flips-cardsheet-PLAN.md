---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/SettingsScreen.jsx
  - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
  - apps/client-pwa/src/lib/clientQueries.test.ts
autonomous: true
requirements: [WACT-02, PAYM-05]
must_haves:
  truths:
    - "PROFILE_FEATURE_FLAGS.weeklyActivity is true; the activity-bars card renders data from GET /client/activity/weekly"
    - "PROFILE_FEATURE_FLAGS.linkedCard and SETTINGS_FEATURE_FLAGS.linkedCard are true; CardSheet uses real backend endpoints"
    - "CardSheet shows real last4/expiry from GET /client/payment-method (no '4821' mock literal remains in wired paths)"
    - "Unbind action calls DELETE /client/payment-method via useUnlinkPaymentMethod (no setUnbound mock)"
    - "Enabling autopay shows the ФЗ-376 consent disclosure (amount + periodicity + cancellation) and sends consent_acknowledged:true to PATCH /autopay; disabling sends no consent"
    - "The per-booking «Авто-оплата тренировок» toggle is removed"
  artifacts:
    - path: "apps/client-pwa/src/lib/clientQueries.ts"
      provides: "useClientWeeklyActivity, useClientPaymentMethod, useUnlinkPaymentMethod, usePatchAutopay hooks + key factory entries"
      contains: "useClientWeeklyActivity"
    - path: "apps/client-pwa/src/screens/ProfileScreen.jsx"
      provides: "weeklyActivity+linkedCard flags ON; bars wired to hook"
      contains: "useClientWeeklyActivity"
    - path: "apps/client-pwa/src/screens/SettingsScreen.jsx"
      provides: "linkedCard flag ON; card row shows real last4"
      contains: "useClientPaymentMethod"
    - path: "apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx"
      provides: "CardSheet wired to real endpoints + ФЗ-376 consent modal; «Авто-оплата тренировок» removed"
      contains: "consentAcknowledged"
    - path: "apps/client-pwa/src/lib/clientQueries.test.ts"
      provides: "Vitest wiring suite for the four new hooks"
      contains: "weekly"
  key_links:
    - from: "ProfileScreen.jsx activity bars"
      to: "useClientWeeklyActivity"
      via: "hook call → bar heights from workouts"
      pattern: "useClientWeeklyActivity\\("
    - from: "ProfileExtraSheets.jsx CardSheet autopay-enable"
      to: "usePatchAutopay"
      via: "consent modal → mutateAsync({enabled:true, consentAcknowledged:true})"
      pattern: "consentAcknowledged:\\s*true"
    - from: "ProfileExtraSheets.jsx unbind"
      to: "useUnlinkPaymentMethod"
      via: "DELETE mutation replacing setUnbound mock"
      pattern: "useUnlinkPaymentMethod\\("
---

<objective>
Flip the two already-built-but-hidden PWA feature flags ON and wire the existing UI to real backend
endpoints (WACT-02, PAYM-05): the ProfileScreen weekly-activity bars to `GET /client/activity/weekly`,
and the CardSheet to the Phase-79 `GET/DELETE/PATCH /client/payment-method` (+ `/autopay`) endpoints.
Add the ФЗ-376 consent disclosure on autopay-enable and remove the anti-feature per-booking
«Авто-оплата тренировок» toggle.

Purpose: Surfaces the v2.2 client self-service depth in the PWA. This is FLIP + WIRE on existing
hidden UI, NOT a rebuild.
Output: Four new TanStack Query hooks, two flag flips, CardSheet wired with consent UI, toggle removed,
Vitest wiring suite green.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-CONTEXT.md
@.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md

<interfaces>
<!-- Contracts the executor implements/consumes. Extracted from PATTERNS.md + Phase-79 endpoints. Do NOT re-explore. -->

clientQueries.ts conventions (apps/client-pwa/src/lib/clientQueries.ts):
  - clientPortalKeys key factory (~line 38): add weeklyActivity() and paymentMethod() entries.
  - useClientHome read query (lines 131-140): staleTime: 30_000, queryFn calls clientRequest('get', path).
  - useRescheduleBooking (497-525) / useCancelBooking (474-489) mutations: use onSettled (NOT onSuccess)
    for invalidateQueries; clientRequest handles CSRF cookie transparently.

Backend contracts (Phase-79, already shipped):
  - GET  /api/v1/client/payment-method  → ResponseEnvelope, data: PaymentMethodData | null
      PaymentMethodData = { last4, brand, expiryMonth, expiryYear, autopayEnabled, consentRecordedAt }
  - DELETE /api/v1/client/payment-method → soft-delete (no body)
  - PATCH /api/v1/client/payment-method/autopay → body { enabled: bool, consentAcknowledged: bool }
      backend returns 409 code "consent_required" if enabled:true without consentAcknowledged:true (ФЗ-376 gate)
  - GET  /api/v1/client/activity/weekly  → ResponseEnvelope, data: WeeklyActivityItem[] (7 items)
      WeeklyActivityItem = { date: string ISO, workouts: number, minutes: null }

New hooks to add (signatures from PATTERNS.md lines 304-408):
  useClientWeeklyActivity()  → useQuery, key weeklyActivity(), staleTime 30_000
  useClientPaymentMethod()   → useQuery, key paymentMethod(), staleTime 30_000
  useUnlinkPaymentMethod()   → useMutation DELETE, onSettled invalidate paymentMethod()
  usePatchAutopay()          → useMutation PATCH, args {enabled, consentAcknowledged}, onSettled invalidate

PWA component anchors (from PATTERNS.md):
  ProfileScreen.jsx: PROFILE_FEATURE_FLAGS block ~line 25 (weeklyActivity:false, linkedCard:false →
    both true); hidden activity-bars card ~line 268 (7-bar Пн..Вс block); hooks added ~lines 9-16
    via `from '@/data'` import.
  SettingsScreen.jsx: SETTINGS_FEATURE_FLAGS block ~line 15 (linkedCard:false → true); hidden card
    row ~line 294 (NavRow "Привязанная карта" value="•••• 4821" onClick=onOpenCard); import line 6.
  ProfileExtraSheets.jsx: CardSheet ~line 324; unbindConfirm bottom-sheet modal ~lines 413-449
    (overlay animation 'ctx-fade 0.2s', content 'sheet-up 0.28s'); «Авто-оплата тренировок» toggle
    ~lines 393-394 (REMOVE); «Авто-продление абонемента» toggle (KEEP).

Error-code handling (BookingManageSheet.jsx 177-190): catch err, read err.code; on 'consent_required'
  surface the consent modal; else generic error.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add four TanStack Query hooks + key factory entries + wiring tests</name>
  <read_first>
    - apps/client-pwa/src/lib/clientQueries.ts (analogs: clientPortalKeys ~line 38; useClientHome 131-140; useClientMembership 165-175; useCancelBooking 474-489; useRescheduleBooking 497-525)
    - apps/client-pwa/src/lib/clientQueries.test.ts (existing wiring-test structure if present; otherwise mirror existing query/mutation test setup)
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (clientQueries section lines 304-408)
  </read_first>
  <behavior>
    - useClientWeeklyActivity issues GET /api/v1/client/activity/weekly, returns data array, staleTime 30_000.
    - useClientPaymentMethod issues GET /api/v1/client/payment-method, returns PaymentMethodData|null.
    - useUnlinkPaymentMethod issues DELETE /api/v1/client/payment-method, invalidates paymentMethod() onSettled.
    - usePatchAutopay issues PATCH /api/v1/client/payment-method/autopay with body {enabled, consentAcknowledged}, invalidates paymentMethod() onSettled.
  </behavior>
  <action>
    In clientQueries.ts add key-factory entries `weeklyActivity: () => [...clientPortalKeys.all, 'weekly-activity'] as const` and `paymentMethod: () => [...clientPortalKeys.all, 'payment-method'] as const`. Add the four hooks per the PATTERNS interface signatures: `useClientWeeklyActivity`, `useClientPaymentMethod`, `useUnlinkPaymentMethod`, `usePatchAutopay`. Reads use `staleTime: 30_000`; mutations use `onSettled` with `qc.invalidateQueries({ queryKey: clientPortalKeys.paymentMethod() })`. usePatchAutopay's mutationFn takes `{ enabled, consentAcknowledged }` and PATCHes body `{ enabled, consentAcknowledged }`. Rely on `clientRequest` for transparent CSRF. Export all four from the module (and re-export via `@/data` barrel if hooks are surfaced there — match how useClientHome/useRescheduleBooking are exported).
    Extend apps/client-pwa/src/lib/clientQueries.test.ts (create if absent, mirroring existing hook-wiring tests): assert each hook calls clientRequest with the correct method+path, that usePatchAutopay forwards {enabled, consentAcknowledged} in the body, and that mutations invalidate the paymentMethod key onSettled.
  </action>
  <verify>
    <automated>pnpm --filter client-pwa test -- clientQueries</automated>
  </verify>
  <acceptance_criteria>
    - Four hooks exported and reachable from the screen import path (`@/data`).
    - usePatchAutopay sends body containing both `enabled` and `consentAcknowledged`.
    - Mutations invalidate clientPortalKeys.paymentMethod() onSettled.
    - `pnpm --filter client-pwa test` green for the clientQueries suite.
  </acceptance_criteria>
  <done>Hooks + key entries added, wiring tests green.</done>
</task>

<task type="auto">
  <name>Task 2: Flip flags + wire ProfileScreen bars & SettingsScreen card row</name>
  <read_first>
    - apps/client-pwa/src/screens/ProfileScreen.jsx (PROFILE_FEATURE_FLAGS ~line 25; hidden activity-bars card ~line 268; hooks block ~lines 9-16; `from '@/data'` import)
    - apps/client-pwa/src/screens/SettingsScreen.jsx (SETTINGS_FEATURE_FLAGS ~line 15; hidden NavRow card row ~line 294; import line 6)
    - apps/client-pwa/src/lib/clientQueries.ts (the hooks added in Task 1)
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (ProfileScreen lines 411-451, SettingsScreen lines 455-481)
  </read_first>
  <action>
    ProfileScreen.jsx: flip `PROFILE_FEATURE_FLAGS.weeklyActivity` and `PROFILE_FEATURE_FLAGS.linkedCard` from false to true. Add `useClientWeeklyActivity` (and `useClientPaymentMethod` if the linkedCard row on this screen needs live last4) to the `from '@/data'` import. Call `useClientWeeklyActivity()` at the top alongside existing hooks; destructure `{ data: weeklyActivity }`. In the activity-bars card (~line 268) replace the 7 static placeholder bars with real data: map the 7 Mon→Sun items, compute each bar height proportional to `workouts` relative to the week's max workouts (guard divide-by-zero → all bars at minimum height when max is 0). Keep the existing Пн..Вс labels and card styling; only the bar heights become data-driven. Handle loading/empty (no data yet → render flat/minimum bars, not a crash).
    SettingsScreen.jsx: flip `SETTINGS_FEATURE_FLAGS.linkedCard` from false to true. Add `useClientPaymentMethod` to the `from '@/data'` import (line 6). Call it; replace the static `value="•••• 4821"` on the NavRow with `data ? '•••• ' + data.last4 : 'Добавить'` (when `data === null` show "Добавить"). `onClick={onOpenCard}` stays unchanged.
  </action>
  <verify>
    <automated>pnpm --filter client-pwa test && pnpm --filter client-pwa build</automated>
  </verify>
  <acceptance_criteria>
    - PROFILE_FEATURE_FLAGS.weeklyActivity === true and PROFILE_FEATURE_FLAGS.linkedCard === true.
    - SETTINGS_FEATURE_FLAGS.linkedCard === true.
    - Activity bars render heights derived from useClientWeeklyActivity workouts (no static placeholder heights remain).
    - SettingsScreen card row shows real last4 (or "Добавить" when null), no hardcoded "4821" in the wired path.
    - PWA test suite + production build both succeed.
  </acceptance_criteria>
  <done>Flags flipped, bars data-driven, settings row live, build green.</done>
</task>

<task type="auto">
  <name>Task 3: Wire CardSheet to real endpoints + ФЗ-376 consent modal + remove autopay-training toggle</name>
  <read_first>
    - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx (CardSheet ~line 324; unbindConfirm modal ~lines 413-449; «Авто-оплата тренировок» toggle ~lines 393-394; «Авто-продление абонемента» toggle to keep; static card visual •••• 4821 / 09/28 / ALEXANDRA Z.)
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx (error-code catch pattern lines 177-190 — err.code === 'consent_required')
    - apps/client-pwa/src/lib/clientQueries.ts (useClientPaymentMethod, useUnlinkPaymentMethod, usePatchAutopay from Task 1)
    - .planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-PATTERNS.md (ProfileExtraSheets section lines 484-558; bottom-sheet modal shared pattern lines 607-614)
  </read_first>
  <action>
    In CardSheet (ProfileExtraSheets.jsx): call `useClientPaymentMethod()`, `usePatchAutopay()`, `useUnlinkPaymentMethod()`. Replace the static card visual — `•••• 4821` → `•••• {data?.last4}`; expiry `09 / 28` → `{String(data.expiryMonth).padStart(2,'0')} / {String(data.expiryYear).slice(-2)}`; drop the `ALEXANDRA Z.` cardholder line (no cardholder field in API — show a generic "КАРТА CLUBCORE" or omit). Handle `data === null` (no card) gracefully.
    REMOVE the «Авто-оплата тренировок» per-booking toggle (~lines 393-394) entirely — it is the locked anti-feature (double-billing vs PT-package credit model). KEEP «Авто-продление абонемента».
    Wire «Авто-продление абонемента»: add state `autopayConsentOpen` (mirrors unbindConfirm state). On toggle-ENABLE, open the ФЗ-376 consent bottom-sheet modal (reuse the unbindConfirm modal pattern: overlay animation 'ctx-fade 0.2s ease-out', content 'sheet-up 0.28s cubic-bezier(0.32,0.72,0.2,1)', backdrop click dismisses, stopPropagation on content). The disclosure copy MUST state the three ФЗ-376 elements: списываемая сумма (стоимость текущего тарифа), периодичность (за N дней до окончания абонемента), способ отмены (в любой момент в настройках карты). Confirm button calls `await patchAutopay.mutateAsync({ enabled: true, consentAcknowledged: true })`. On toggle-DISABLE, call `await patchAutopay.mutateAsync({ enabled: false, consentAcknowledged: false })` directly with NO consent modal.
    Wire unbind: replace the `setUnbound(true)` mock in the existing unbindConfirm flow with `await unlinkCard.mutateAsync()` (DELETE), then close the sheet / refresh.
    Wrap mutation calls in try/catch per BookingManageSheet pattern: on `err.code === 'consent_required'` re-surface the consent modal; otherwise show a generic error.
  </action>
  <verify>
    <automated>pnpm --filter client-pwa test && pnpm --filter client-pwa build</automated>
  </verify>
  <acceptance_criteria>
    - CardSheet displays last4/expiry from useClientPaymentMethod (no '4821'/'09 / 28'/'ALEXANDRA Z.' literals remain in the wired card visual).
    - «Авто-оплата тренировок» toggle is removed; «Авто-продление абонемента» remains.
    - Enabling autopay opens a consent modal showing amount + periodicity + cancellation, then sends consentAcknowledged:true; disabling sends consentAcknowledged:false with no modal.
    - Unbind calls useUnlinkPaymentMethod (DELETE), not setUnbound mock.
    - consent_required error re-opens the consent modal.
    - PWA test suite + build green.
  </acceptance_criteria>
  <done>CardSheet fully wired to real endpoints, ФЗ-376 consent modal in place, anti-feature toggle removed, build + tests green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PWA client → /client/payment-method* | Authenticated client mutations cross (DELETE/PATCH); CSRF cookie required |
| PWA UI → ФЗ-376 consent | Legal-compliance gate: autopay-enable must disclose before consent flows to backend |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-81-06 | Repudiation / Compliance (ФЗ-376) | CardSheet autopay-enable | mitigate | Consent modal discloses amount+periodicity+cancellation BEFORE enable; consentAcknowledged:true sent only after explicit confirm; backend Phase-79 gate rejects enable without it (409 consent_required), mirrored client-side |
| T-81-07 | Information Disclosure | CardSheet card visual | mitigate | Only last4/brand/expiry shown (display fields from API); yookassa token never returned by backend, never referenced in PWA; no PAN/CVV |
| T-81-08 | Tampering | autopay toggle bypass | mitigate | Client cannot enable autopay without consentAcknowledged — backend enforces; UI catch on consent_required re-surfaces modal (no silent retry without consent) |
| T-81-09 | Elevation / IDOR | payment-method mutations | accept | Endpoints are client_id-scoped server-side (Phase-79, D-20-IDOR); PWA sends no client_id (derived from cookie). No client-side mitigation needed |
| T-81-10 | Spoofing | CSRF on DELETE/PATCH | mitigate | clientRequest attaches CSRF cookie transparently; backend verify_client_csrf on unsafe methods (Phase-79) |
</threat_model>

<verification>
- `pnpm --filter client-pwa test` green (clientQueries wiring suite + existing suites)
- `pnpm --filter client-pwa build` succeeds (no type/lint break from flag flips or wiring)
- Manual scan: no remaining `4821` / `09 / 28` / `ALEXANDRA Z.` literals in wired CardSheet paths; «Авто-оплата тренировок» string gone from ProfileExtraSheets.jsx
</verification>

<success_criteria>
- Roadmap SC3: weeklyActivity flag ON; ProfileScreen bars load from GET /client/activity/weekly.
- Roadmap SC4: linkedCard flag ON; CardSheet works with real GET/DELETE/PATCH endpoints; per-booking «Авто-оплата тренировок» toggle removed.
- WACT-02 + PAYM-05 satisfied; ФЗ-376 consent disclosure present on autopay enable.
</success_criteria>

<output>
Create `.planning/phases/81-weekly-activity-pwa-flags-openapi-handoff/81-02-SUMMARY.md` when done.
</output>
