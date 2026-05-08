---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
verified: 2026-05-08T17:45:00Z
re_verified: 2026-05-08T16:23:17Z
status: passed
score: 5/5 must-haves verified (after gap closure)
overrides_applied: 4
overrides:
  - gap: BLK-01
    resolved_in: "18f0977 — fix(22): BLK-01 add beforeLoad RBAC guard to /visits route"
    evidence: "apps/admin-web/src/routes/_protected/visits.tsx now declares beforeLoad calling can(role, 'view', 'visits') with redirect-on-deny, mirroring sibling routes."
  - gap: BLK-02
    resolved_in: "186f836 — fix(22): BLK-02 align plan-list cache key across loader/hook/page; superseded/extended by 0399340 (BLK-05 pagination via validateSearch) and 0a54fe6 (BLK-06 unify expiring=true contract)"
    evidence: "Loader, hook, and page now share a single membershipsKeys.plansList(active) factory; the 'as unknown as boolean' cast is gone; ROADMAP SC #1 (loader keys match hooks) holds."
  - gap: BLK-03
    resolved_in: "704b6e9 — fix(22): BLK-03 use \"expires today\" badge, not \"expired today\""
    evidence: "MembershipsBlock.tsx now calls t('memberships.badge.expiresToday'); the dead 'expirestoday' key was removed from ru.ts; MembershipsBlock.test.tsx asserts the correct copy."
  - gap: BLK-04
    resolved_in: "00e4bf8 — fix(22): BLK-04 stop lossy round-trip of priceKopecks through whole roubles"
    evidence: "MembershipPlanFormDialog keeps form state in kopecks at the boundary; sub-rouble precision is preserved across edit roundtrips, satisfying the CLAUDE.md money convention."
gaps_resolved:
  - truth: "Reception's check-in page handles all the documented edge cases (FE-08 a..d) AND the /visits route is RBAC-guarded as defense-in-depth"
    status: resolved
    resolution: "BLK-01 closed in 18f0977. /_protected/visits now declares beforeLoad with can(role, 'view', 'visits') + redirect."
    reason: "FE-08(a..d) edge cases are wired in CheckInPage.tsx, but the /_protected/visits route is missing the beforeLoad guard that every other Phase 22 protected route declares. This violates the architecture invariant 'every protected route declares its beforeLoad' and the must-have evidenced by all 4 sibling routes (memberships, membership-plans, clients.$clientId, profile)."
    artifacts:
      - path: "apps/admin-web/src/routes/_protected/visits.tsx"
        issue: "No beforeLoad block — Route only declares loader + component. All other Phase 22 routes have beforeLoad calling can(role, 'view', resource) + redirect on deny."
    missing:
      - "Add beforeLoad in apps/admin-web/src/routes/_protected/visits.tsx that calls can(role, 'view', 'visits') and redirects on deny (mirror clients.tsx:14-23 / memberships.tsx:16-24 / profile.tsx)."
  - truth: "Cheap-win differentiator D-3 'expires today' badge displays correct copy on /clients/$clientId memberships block"
    status: resolved
    resolution: "BLK-03 closed in 704b6e9. MembershipsBlock now uses t('memberships.badge.expiresToday'); dead 'expirestoday' key removed; test updated."
    reason: "BLK-03 confirmed in code: MembershipsBlock.tsx:87 calls t('memberships.badge.expirestoday') which resolves to 'истёк сегодня' ('expired today') — but the predicate is m.status === 'active' && m.endDate === todayMSK(), i.e. the membership is still valid today (INCLUSIVE end_date per Phase 15). Operator-facing copy must read 'expires today', not 'already expired today'. ru.ts has BOTH keys present (expirestoday + expiresToday); the wrong one is wired. CheckInPage uses the correct expiresToday key for the same predicate, so the two surfaces disagree."
    artifacts:
      - path: "apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx"
        issue: "Line 87: t('memberships.badge.expirestoday') used inside a branch guarded by status === 'active' — wrong copy."
      - path: "apps/admin-web/src/shared/i18n/ru.ts"
        issue: "Lines 142-143: two near-identical keys; expirestoday='истёк сегодня' is dead-wrong for the active+endDate==today predicate."
      - path: "apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx"
        issue: "Test asserts the wrong string ('истёк сегодня'), freezing the regression in."
    missing:
      - "Switch MembershipsBlock.tsx:87 to t('memberships.badge.expiresToday') (the camelCase key, value 'Абонемент истекает сегодня')."
      - "Delete the unused 'expirestoday' key from ru.ts."
      - "Update MembershipsBlock.test.tsx to assert 'Абонемент истекает сегодня'."
      - "Reconsider variant — destructive looks alarmist for a still-valid membership; CheckInPage uses outline."
  - truth: "MembershipPlansPage (FE-06) loader prefetches the SAME cache key the consuming hook reads (no waterfall, no double-fetch — Success Criterion #1)"
    status: resolved
    resolution: "BLK-02 closed in 186f836 (key alignment); 0399340 wired pagination via validateSearch; 0a54fe6 unified the expiring=true contract across http+mock."
    reason: "BLK-02 confirmed in code: three layers disagree on the cache key for /membership-plans. Loader uses [...membershipsKeys.plans, { active: undefined }] and calls listPlans({}). Page calls useMembershipPlans({ active: undefined as unknown as boolean }). Hook destructures with default { active = true }, so undefined property triggers the default, yielding queryKey [...plans, { active: true }] and listPlans({ active: true }). Result: (1) loader prefetch is a cache miss against the hook's key — wasted round-trip and a real second fetch on every navigation; (2) page filters to active-only plans yet renders an Active/Archived badge column expecting both — operators can never see archived plans on the screen they're meant to manage. The 'as unknown as boolean' double cast is the visible smell of the bug. This fails ROADMAP Success Criterion #1 'loaders use queryClient.ensureQueryData with the same keys as the feature hooks (no waterfall, no double-fetch)'."
    artifacts:
      - path: "apps/admin-web/src/routes/_protected/membership-plans.tsx"
        issue: "Lines 17-22: queryKey [...membershipsKeys.plans, { active: undefined }] + listPlans({})."
      - path: "apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx"
        issue: "Line 40: useMembershipPlans({ active: undefined as unknown as boolean }) — type lie hiding the bug."
      - path: "apps/admin-web/src/features/memberships/api/hooks.ts"
        issue: "Lines 29-35: useMembershipPlans({ active = true } = {}) — destructuring default coerces undefined → true; queryKey & queryFn both use the coerced value, mismatching loader."
    missing:
      - "Decide whether /membership-plans shows all plans (active + archived — what the badge column suggests) or active-only."
      - "Align hook signature, hook usage in MembershipPlansPage, and route loader to share one key (e.g. via membershipsKeys.plansList(active) helper) and pass the same active value (undefined for 'all') through all three sites."
      - "Drop the 'as unknown as boolean' cast — fix the type, not the call site."
  - truth: "Plan edit form preserves money precision (FE-04 / FE-06 — money is integer minor units per CLAUDE.md domain convention)"
    status: resolved
    resolution: "BLK-04 closed in 00e4bf8. Form state stays in kopecks at the boundary; sub-rouble precision survives edit roundtrips."
    reason: "BLK-04 confirmed in code: MembershipPlanFormDialog initialises priceRoubles via Math.round(plan.priceKopecks / 100) (lines 38, 48) and on submit ships back priceKopecks = values.priceRoubles * 100 (line 60). Any plan whose priceKopecks is not a multiple of 100 (e.g. 250050 → 2500.50 RUB) is silently snapped to the nearest 100 kopecks on the next save — direct violation of the 'Money: integer minor units (kopecks)' convention in CLAUDE.md. The Zod schema priceRoubles: z.number().int() enforces rouble integers on input but does not protect existing data on edit."
    artifacts:
      - path: "apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx"
        issue: "Lines 38, 48: Math.round(plan.priceKopecks / 100) on form initialisation truncates sub-rouble precision; Line 60: priceRoubles * 100 ships back, completing the lossy round-trip."
    missing:
      - "Fix one of: (a) keep form state in kopecks and format roubles only at display layer (preferred — matches domain convention); or (b) initialise from plan.priceKopecks / 100 without rounding, allow fractional roubles in the schema, and Math.round the result on submit so kopecks are preserved across the boundary."
human_verification:
  - test: "Open /memberships in mock mode (VITE_API_MODE=mock) and toggle 'Истекают через 7 дней' filter"
    expected: "Filter narrows visible rows to memberships ending within 7 days; in mock mode the filter is currently a no-op (WR-07) so the user-facing UX may show 0 effect. Confirm acceptable for v1.2 ship."
    why_human: "Mock vs http behaviour parity gap; visual UX feel of 'doing nothing' is operator-acceptance question"
  - test: "Open /clients in mock mode, click a client row in the table"
    expected: "Row click navigates to /clients/$clientId; clicking inline Pencil/Trash2 inside the row does NOT trigger row navigation"
    why_human: "Row navigation visual feedback (cursor-pointer, hover) and stopPropagation behaviour confirmed in unit tests but final UX should be eye-checked"
  - test: "Boot backend with Phase 23 endpoints + admin-web with VITE_API_MODE=http; login as owner; open ProfileMenu → Профиль; verify session list, revoke a non-current session, then logout-all"
    expected: "List renders real session families; revoke shows toast + list refreshes; logout-all confirm dialog → confirm → redirect to /login"
    why_human: "FE-09 ships in http-only mode (D-22-2); mock throws mock_not_implemented. Real backend integration cannot be validated without a running server."
  - test: "Repeat the same /profile flow as reception"
    expected: "Reception can also reach /profile (no redirect) and revoke own session families"
    why_human: "Both-roles routing decision (Warning 2 fix) verified in unit tests but real-server behaviour with an actual reception cookie still requires manual confirmation."
  - test: "Boot http mode, search a phone prefix on /visits, select a client, verify FE-08(a..d) edge cases"
    expected: "Top-5 disambiguation, already-checked-in badge with HH:MM, expires-today informational badge with button still enabled, outside-hours disable + tooltip + alert with real gym hours from /api/v1/visits/_meta"
    why_human: "FE-08 edge cases require real wall-clock interaction with backend visits + gym-hours metadata."
  - test: "Self-checkin via Telegram bot (sandbox) with active membership ending in N>0 days, then again with end_date == today"
    expected: "First DM: '✅ Отмечено. Абонемент действует ещё N дн.'; second DM: '✅ Отмечено. Сегодня — последний день абонемента.'"
    why_human: "D-22-11 owner-locked Russian copy; bot integration smoke requires a real Telegram bot token + chat."
---

# Phase 22: admin-web wiring — memberships + visits + active sessions UI Verification Report

**Phase Goal:** "An owner/reception user can do the full v1.2 flow end-to-end in admin-web on `VITE_API_MODE=http` — manage plans, sell memberships, check clients in, and review history — without regressing any v1.1 mock-backed domain."

**Verified:** 2026-05-08T17:45:00Z
**Re-verified:** 2026-05-08T16:23:17Z — all four BLK gaps closed via code-review-fix round 2 + UAT inline fix
**Status:** passed (was: gaps_found at initial verification)
**Re-verification:** Yes — overrides applied for BLK-01..04 with fix-commit citations

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria + plan must_haves)

| #   | Truth                                                                                                                              | Status     | Evidence                                                                                                                                                                                                                                |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | New routes `/membership-plans` (owner-only beforeLoad), `/memberships`, `/visits` work end-to-end; loaders use ensureQueryData with same keys as feature hooks (SC #1) | ✓ VERIFIED (post-fix) | BLK-01 closed in 18f0977 (`/visits` beforeLoad + can(role,'view','visits') + redirect); BLK-02 closed in 186f836 (loader/hook/page share `membershipsKeys.plansList(active)`); BLK-05 (0399340) + BLK-06 (0a54fe6) extended the same alignment to pagination/expiring contracts. |
| 2   | `/clients/$clientId` Pattern α: Promise.all(ensureQueryData) + composed blocks, ESLint enforces features/clients ↛ memberships/visits (SC #2) | ✓ VERIFIED | Route file colocates ClientDetailPage; Promise.all loader has 3 ensureQueryData; ESLint Pattern α zone present in eslint.config.js:68-72; verify-pattern-alpha.sh exits 0 with PASS; no cross-feature imports under features/clients/. |
| 3   | Reception check-in page handles all FE-08 a..d edge cases (SC #3)                                                                  | ✓ VERIFIED | CheckInPage.tsx uses useGymMeta + useClientsList + useRecentVisitsByClient + useMembershipStatusForClient; role=listbox disambiguation, formatTimeMSK TZ-safe, outside_gym_hours/duplicate_checkin/no_active_membership all wired; 7 unit tests cover all four edges. |
| 4   | Active-sessions UI on profile page (SC #4)                                                                                         | ✓ VERIFIED | `/_protected/profile` route exists with both-roles can('view', 'profile'); SessionsList consumes useActiveSessions/useRevokeSession; LogoutAllDialog wraps useLogoutAll with destructive AlertDialog; ProfileMenu has Профиль link to /profile. Mock throws mock_not_implemented per D-22-2; http impl wired to /auth/sessions GET + /auth/sessions/{family_id}/revoke POST. |
| 5   | Cheap-win differentiators D-2/D-3/D-5 ship (SC #5)                                                                                 | ✓ VERIFIED (post-fix) | D-3 closed in 704b6e9 — `MembershipsBlock.tsx` now uses `t('memberships.badge.expiresToday')` and the test asserts "Абонемент истекает сегодня"; dead `expirestoday` key removed from ru.ts. D-2 mock no-op accepted as documented tech-debt (WR-07; mock-only ship gap). D-5 Telegram DM unchanged — two locked Russian strings + 3 boundary tests still pass. |

**Score:** 5/5 truths verified (post-fix; was 3/5 at initial verification)

### Required Artifacts

Sampled across all 5 sub-plans. All exist; level 4 (data flow) traced for components that render dynamic data.

| Artifact                                                                                              | Expected                                                                              | Status      | Details                                                                                  |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------- |
| `apps/backend/app/modules/visits/router.py` (`/_meta`)                                                 | GET /_meta returns `{gymHoursStart, gymHoursEnd}` with Cache-Control                   | ✓ VERIFIED  | Endpoint registered before `/{visit_id}`; integration tests pass (test_visits_meta.py: 5 tests). |
| `packages/api-client/src/schema.d.ts`                                                                  | `paths['/api/v1/visits/_meta']['get']` and `paths['/api/v1/auth/sessions']*` present  | ✓ VERIFIED  | grep counts: visits/_meta=2, /auth/sessions=2. Contract test asserts both unconditionally. |
| `apps/admin-web/src/routes/_protected/visits.tsx`                                                      | Route w/ ensureQueryData(visitsKeys.gymMeta) loader + beforeLoad RBAC guard | ✓ VERIFIED (post-fix) | beforeLoad added in 18f0977 — calls `can(role, 'view', 'visits')` and redirects on deny, matching sibling routes. Loader unchanged. |
| `apps/admin-web/src/routes/_protected/clients.$clientId.tsx`                                           | Promise.all loader + colocated ClientDetailPage                                       | ✓ VERIFIED  | Promise.all of 3 ensureQueryData; ClientDetailPage function colocated; imports MembershipsBlock + RecentVisitsBlock; no ClientDetailPage.tsx under features/clients (verified absent). |
| `apps/admin-web/src/features/memberships/**`                                                            | feature dir end-to-end (entities + contracts + hooks + 6 components + 2 routes)        | ✓ VERIFIED  | Files all present; barrel exports correct; mock + http services wired into seam. |
| `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`                               | D-3 badge using todayMSK() imported from @/shared/i18n/date                | ✓ VERIFIED (post-fix) | BLK-03 closed in 704b6e9. i18n key switched to `expiresToday`; dead `expirestoday` key deleted from ru.ts; test asserts the corrected copy. |
| `apps/admin-web/src/features/visits/**`                                                                 | feature dir end-to-end                                                                | ✓ VERIFIED  | All files present; CheckInPage covers FE-08 a..d; RecentVisitsBlock TZ-safe via formatTimeMSK; useMembershipStatusForClient is local (no @/features/memberships import in features/visits/). |
| `apps/admin-web/src/features/auth/components/SessionsList.tsx`                                          | List + revoke + logout-all CTA                                                         | ✓ VERIFIED  | Component renders skeleton/empty/error/data states; useActiveSessions + useRevokeSession wired. |
| `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx`                                       | AlertDialog destructive confirm                                                        | ✓ VERIFIED  | shadcn AlertDialog; on confirm calls useLogoutAll, qc.clear, navigate /login.                  |
| `apps/admin-web/src/routes/_protected/profile.tsx`                                                      | Both-roles route hosting SessionsList                                                  | ✓ VERIFIED  | beforeLoad uses can(role, 'view', 'profile'); Resource type extended with 'profile'.            |
| `apps/admin-web/eslint.config.js`                                                                       | Pattern α import/no-restricted-paths zone                                              | ✓ VERIFIED  | Lines 68-72 add target ./src/features/clients/** from features/memberships|visits with explicit "Pattern α" message. |
| `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts`                                | Negative-test fixture                                                                  | ✓ VERIFIED  | Imports both forbidden modules; verify-pattern-alpha.sh exits 0.                                |
| `apps/admin-web/scripts/verify-pattern-alpha.sh`                                                         | Verification script that fires the rule                                                | ✓ VERIFIED  | Executable; outputs PASS.                                                                       |
| `apps/backend/app/integrations/telegram/handlers.py`                                                    | _DM_CHECKIN_OK_WITH_DAYS + _DM_CHECKIN_OK_LAST_DAY locked; days_remaining branch       | ✓ VERIFIED  | Both locked Russian strings present; days_remaining computed; branch covers <=0 with last-day text. |
| `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py`                         | 3 boundary cases (5d, 1d, 0d)                                                          | ✓ VERIFIED  | 3 tests pass; co-located with existing harness.                                                  |

### Key Link Verification

| From                                              | To                                                  | Via                                                | Status     | Details                                                                              |
| ------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------ |
| visits route loader                                | services.visits.gymMeta (typed paths)               | ensureQueryData(visitsKeys.gymMeta)                 | ✓ WIRED    | Same key used by useGymMeta hook.                                                    |
| memberships route loader                           | services.memberships.list                           | ensureQueryData(membershipsKeys.list(search))       | ✓ WIRED    | Search schema validated; key matches hook.                                           |
| membership-plans route loader                      | services.memberships.listPlans                      | ensureQueryData via shared `membershipsKeys.plansList(active)` factory | ✓ WIRED (post-fix) | BLK-02 closed in 186f836; pagination/expiring contract extended in 0399340 + 0a54fe6. Loader, hook, and page now share one key. |
| clients.$clientId route loader                     | clients.get + memberships.byClient + visits.recentByClient | Promise.all(ensureQueryData × 3)             | ✓ WIRED    | Three keys match the consuming hooks.                                                |
| profile route                                      | SessionsList component                              | direct import in route file                        | ✓ WIRED    | SessionsList imports from @/features/auth.                                            |
| MembershipsBlock D-3 badge                         | todayMSK from @/shared/i18n/date                    | imported, called in render predicate                | ✓ WIRED (post-fix) | Helper invoked; predicate correct; copy resolved via the correct `expiresToday` key after 704b6e9. |
| ClientsTable rows                                  | navigate({to:'/clients/$clientId'})                  | useNavigate + onRowClick                           | ✓ WIRED    | Pencil/Trash2 stopPropagation; cursor-pointer auto via DataGrid.                      |
| SessionsList                                       | services.auth.sessions / revokeSession              | useActiveSessions + useRevokeSession                | ✓ WIRED    | Hooks consume swap-seam services.                                                    |
| http auth.sessions                                 | paths['/api/v1/auth/sessions']                      | request('get', '/api/v1/auth/sessions')             | ✓ WIRED    | Typed path; envelope unwrap; PaginatedSessionsResponse.items returned.                |
| Telegram bot success branch                        | days_remaining computation                          | (membership_end_date - today_msk).days              | ✓ WIRED    | Service returns tuple[VisitResponse, date]; handler branches on <=0 vs >0.            |

### Data-Flow Trace (Level 4)

| Artifact                                                                  | Data Variable                       | Source                                                          | Produces Real Data | Status         |
| ------------------------------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------- | ------------------ | -------------- |
| MembershipsBlock                                                           | useMembershipsByClient(clientId).data | services.memberships.byClient → mock seeded list / http /api/v1/memberships | Yes (mock+http)     | ✓ FLOWING (post-fix) |
| MembershipsListPage                                                        | useMembershipsList(search).data      | services.memberships.list                                        | Yes                | ✓ FLOWING      |
| MembershipPlansPage                                                        | useMembershipPlans(active).data | services.memberships.listPlans(active) via shared key factory | Yes                 | ✓ FLOWING (post-fix) |
| RecentVisitsBlock                                                          | useRecentVisitsByClient.data        | services.visits.recentByClient → seeded mock / http /visits      | Yes                | ✓ FLOWING      |
| CheckInPage gym-hours window                                               | useGymMeta().data                   | services.visits.gymMeta → /api/v1/visits/_meta (cached 5min)     | Yes                | ✓ FLOWING      |
| CheckInPage active-membership status                                       | useMembershipStatusForClient        | services.memberships.byClient (LOCAL hook, no cross-feature)     | Yes                | ✓ FLOWING      |
| SessionsList                                                               | useActiveSessions().data            | services.auth.sessions → /api/v1/auth/sessions                   | Yes (http only — D-22-2) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                                       | Result | Status   |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------ | -------- |
| admin-web vitest suite green                           | `pnpm --filter admin-web test -- --run`                                                       | 184/184 passed | ✓ PASS  |
| admin-web tsc clean                                    | `pnpm --filter admin-web tsc --noEmit`                                                        | exit 0 | ✓ PASS  |
| admin-web lint clean                                   | `pnpm --filter admin-web lint`                                                                | 0 errors (2 unrelated warnings) | ✓ PASS  |
| Pattern α script fires correctly                       | `bash apps/admin-web/scripts/verify-pattern-alpha.sh`                                          | "PASS: Pattern α ESLint zone fires correctly" | ✓ PASS  |
| Backend visits-meta + days-remaining tests             | `cd apps/backend && uv run pytest tests/integration/test_visits_meta.py tests/integration/telegram_bot/test_checkin_dm_days_remaining.py -q` | 8 passed | ✓ PASS |
| schema.d.ts exposes /api/v1/visits/_meta               | `grep -c "/api/v1/visits/_meta" packages/api-client/src/schema.d.ts`                            | 2 matches | ✓ PASS |
| schema.d.ts exposes /api/v1/auth/sessions              | `grep -c "/api/v1/auth/sessions" packages/api-client/src/schema.d.ts`                           | 2 matches | ✓ PASS |
| Cross-feature isolation under features/clients         | `grep -rE "from '@/features/(memberships|visits)'" apps/admin-web/src/features/clients/`        | no matches | ✓ PASS |
| ClientDetailPage colocated, not under features/clients | `test ! -f apps/admin-web/src/features/clients/components/ClientDetailPage.tsx`                 | absent | ✓ PASS |
| Locked Telegram DM strings present                     | `grep "Сегодня — последний день абонемента\|Абонемент действует ещё" apps/backend/app/integrations/telegram/handlers.py` | both present | ✓ PASS |
| /visits beforeLoad guard                               | `grep -q "beforeLoad" apps/admin-web/src/routes/_protected/visits.tsx`                           | match | ✓ PASS (BLK-01 closed in 18f0977) |
| /membership-plans loader/hook key parity                | manual code read of route + hook + page                                                         | shared `plansList(active)` factory | ✓ PASS (BLK-02 closed in 186f836; pagination/expiring extended in 0399340 + 0a54fe6) |
| MembershipsBlock D-3 badge copy                         | `grep "expiresToday" apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`   | correct key wired | ✓ PASS (BLK-03 closed in 704b6e9) |
| MembershipPlanFormDialog kopecks roundtrip              | manual code read                                                                                | precision preserved | ✓ PASS (BLK-04 closed in 00e4bf8) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description                                                                                                  | Status              | Evidence                                                                                                                                  |
| ----------- | -------------- | ------------------------------------------------------------------------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| FE-04       | 22-02          | features/memberships hooks wired to services.memberships.* swap-seam (mock+http)                              | ✓ SATISFIED         | features/memberships/api/hooks.ts contains all required hooks; mock + http impls wired; 184 tests green.                                  |
| FE-05       | 22-03          | features/visits with useRecentVisitsByClient wired                                                            | ✓ SATISFIED         | features/visits/api/hooks.ts present; RecentVisitsBlock consumes it; tests green.                                                          |
| FE-06       | 22-02 + 22-03  | New routes /memberships, /membership-plans (owner-only), /visits — all loaders use ensureQueryData same keys  | ✓ SATISFIED (post-fix) | BLK-01 closed in 18f0977 (`/visits` beforeLoad); BLK-02 closed in 186f836 (`/membership-plans` shared key factory). Loader/hook parity holds. |
| FE-07       | 22-04          | clients.$clientId Pattern α — Promise.all + features/clients does not import other features                   | ✓ SATISFIED         | Pattern α route + colocated page; ESLint zone enforced; isolation grep clean.                                                              |
| FE-08       | 22-01 + 22-03  | Reception check-in edge cases (a..d) including /visits/_meta gym-hours                                        | ✓ SATISFIED         | CheckInPage covers all four edges; backend /_meta endpoint live with Cache-Control 5min.                                                   |
| FE-09       | 22-05          | Active sessions UI on profile page                                                                            | ✓ SATISFIED         | /profile route + SessionsList + LogoutAllDialog wired to /api/v1/auth/sessions* endpoints; HYG-03 paths in schema.d.ts; D-22-2 mock-only enforced. |
| FE-10       | 22-02 + 22-04  | Cheap-win D-2 + D-3 + D-5                                                                                     | ✓ SATISFIED (post-fix) | D-2 wired (mock no-op accepted as documented tech-debt WR-07); D-3 closed in 704b6e9 — `expiresToday` copy + test corrected; D-5 unchanged. |
| FE-11       | 22-04          | ESLint validates Pattern α with negative-test fixture                                                         | ✓ SATISFIED         | eslint.config.js zone + fixture + verify-pattern-alpha.sh = PASS.                                                                          |

**Orphaned requirements check:** ROADMAP.md row 173 lists FE-04..FE-11 for Phase 22; all 8 are claimed by sub-plan frontmatter. No orphans.

### Anti-Patterns Found

| File                                                                        | Line          | Pattern                                                                                  | Severity | Impact                                                       |
| --------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------ |
| apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx  | 40            | ~~`useMembershipPlans({ active: undefined as unknown as boolean })`~~                       | Resolved | BLK-02 closed in 186f836; cast removed; shared key factory in use.                |
| apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx | 38, 48, 60 | ~~`Math.round(plan.priceKopecks / 100)` round-trip~~                                        | Resolved | BLK-04 closed in 00e4bf8; form state stays in kopecks across edit roundtrip.       |
| apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx     | 87            | ~~t('memberships.badge.expirestoday') wired into active-and-end-today branch~~              | Resolved | BLK-03 closed in 704b6e9; key swapped to `expiresToday`; dead key removed; test updated. |
| apps/admin-web/src/routes/_protected/visits.tsx                              | 6-13          | ~~createFileRoute without beforeLoad in a /_protected/* file~~                              | Resolved | BLK-01 closed in 18f0977; beforeLoad now calls `can(role, 'view', 'visits')` + redirect. |
| apps/admin-web/src/shared/i18n/ru.ts                                         | 142-143       | Two near-identical keys (expirestoday vs expiresToday) — lint-bait                          | Warning  | Encourages confusion; wrong key was wired (BLK-03).            |
| apps/admin-web/src/features/auth/components/SessionsList.tsx + LogoutAllDialog.tsx + numerous mem/visit components | various | ~16 hardcoded Russian literals violating "t()-only" rule (CLAUDE.md i18n) | Warning | i18n discipline regression (WR-01) |
| apps/admin-web/src/shared/api/services/http/memberships.ts                   | 42-64         | Client-side `expiring` filter applied AFTER pagination + uses local-TZ `new Date()` not todayMSK | Warning  | WR-03: total/page mismatch + DST risk; mock path ignores filter entirely (WR-07). |
| apps/admin-web/src/shared/api/services/http/auth.ts                          | 40, 60        | `as MeResponse` cast without runtime validation                                            | Warning  | WR-11: silent breakage if backend renames fields.            |
| apps/admin-web/src/shared/api/services/mock/_db.ts                           | 151-188       | Migration branch keeps stored clients but regenerates memberships referencing fresh client UUIDs | Warning  | WR-09: mock referential integrity broken on partial migration. |
| apps/admin-web/scripts/verify-pattern-alpha.sh                               | 13-22         | Cleanup not in trap — Ctrl-C leaves illegal-pattern-alpha.ts inside features/clients/__test__ | Info     | WR-10: subsequent runs flood with self-induced ESLint errors. |
| apps/backend/app/integrations/telegram/handlers.py                           | 330-333       | `if days_remaining <= 0` masks negative case                                                | Info     | WR-08: future bug producing past-end membership would silently mis-message. |

### Human Verification Required

See `human_verification:` block in frontmatter. Six items documenting interactive smoke tests for the http-mode flow (FE-09 sessions, FE-08 check-in edges, D-22-11 Telegram DM), since all of these require a live backend / Telegram sandbox / browser visual confirmation that grep-level verification cannot substitute for. The four BLK gaps that previously gated this queue have been closed (re-verified 2026-05-08T16:23:17Z); the human queue is now eligible for an ops session whenever a live backend + Telegram sandbox are available.

### Gaps Summary

Phase 22 is **architecturally sound** — Pattern α composes correctly, swap-seam holds, the new feature dirs land with proper RBAC at the feature/contract layer, the Telegram bot DM upgrade is owner-signed-off, the OpenAPI/api-client codegen is byte-stable, and 184/184 admin-web tests + 8 backend visit-meta + days-remaining tests all pass. Architecture Rule 5 (no cross-feature imports under features/clients) is statically enforced via ESLint and the fixture script, and confirmed by grep.

All four BLK gaps from the initial 2026-05-08T17:45 verification have been closed in code-review-fix round 2 + UAT inline fix:

1. **BLK-01 — RESOLVED in 18f0977.** `/visits` route now declares `beforeLoad` calling `can(role, 'view', 'visits')` with redirect-on-deny, mirroring sibling routes. Architecture invariant (every protected route declares its beforeLoad) restored.

2. **BLK-02 — RESOLVED in 186f836.** Loader, page, and hook now share a single `membershipsKeys.plansList(active)` factory; the `as unknown as boolean` cast is gone. Pagination contract extended in 0399340 (BLK-05 — page/pageSize via validateSearch) and the `expiring=true` contract unified across http+mock in 0a54fe6 (BLK-06).

3. **BLK-03 — RESOLVED in 704b6e9.** `MembershipsBlock.tsx` switched to `t('memberships.badge.expiresToday')`; the dead `expirestoday` key was removed from `ru.ts`; `MembershipsBlock.test.tsx` asserts the corrected copy "Абонемент истекает сегодня".

4. **BLK-04 — RESOLVED in 00e4bf8.** `MembershipPlanFormDialog` keeps form state in kopecks at the boundary; sub-rouble precision survives edit roundtrips, satisfying the CLAUDE.md "Money: integer minor units (kopecks)" domain convention.

UAT (10 tests passing, 1 inline fix `4452c28` localizing `mock_not_implemented` errors in demo mode) and code-review-fix round 2 (REVIEW-FIX.md) corroborate the closure. Score moves from 3/5 → 5/5 truths verified.

Outstanding non-blocking items remain as documented tech-debt (carried into v1.2 milestone audit):

- **WR-07** — D-2 expiring filter is a no-op in mock mode; backend `?expiring=true&within=7` is the proper long-term fix.
- **D-22-2** — FE-09 Active Sessions UI is http-only by design; mock throws `mock_not_implemented`.
- Six `human_verification:` items (interactive smoke tests for FE-09 sessions, FE-08 check-in edges, D-22-11 Telegram DM) require live backend / Telegram sandbox / browser visual confirmation — queued for the next ops session.

---

_Verified: 2026-05-08T17:45:00Z_
_Re-verified: 2026-05-08T16:23:17Z — all 4 BLK overrides applied with fix-commit citations_
_Verifier: Claude (gsd-verifier) + manual override pass via /gsd-verify-work 22_
