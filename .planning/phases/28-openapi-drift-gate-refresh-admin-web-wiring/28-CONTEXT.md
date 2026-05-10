# Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring — Context

**Gathered:** 2026-05-10
**Mode:** `--auto` (Claude picked recommended option for every gray area; review and adjust before planning)
**Status:** Ready for planning

<domain>
## Phase Boundary

Single, byte-stable regeneration of the OpenAPI surface (`apps/backend/openapi.json` →
`packages/api-client/src/schema.d.ts`) followed by admin-web wiring of the freeze /
unfreeze / renewal / expiring-soon affordances introduced in Phases 24–27, with mock
service parity for offline development.

**In scope (FE-10..FE-13 + drift-gate refresh):**

- One regenerate-then-commit cycle for both drift artifacts (mirrors v1.2 Phase 21).
- Membership domain extension: `MembershipStatus` adds `'frozen'`; new fields
  `freezeDaysLimitSnapshot / freezeDaysUsed / freezeDaysRemaining /
  currentFreezePeriod / previousMembershipId` flow through `entities/membership`,
  `shared/api/contracts`, http adapter, and mock store.
- New membership detail page hosting freeze / unfreeze / renew actions
  (RBAC-gated `(CREATE, MEMBERSHIPS)`; cancel-during-freeze stays owner-only).
- List + client overview show `frozen` as a first-class status (badge + filter).
- Existing `?expiring=true&within=N` filter (Phase 24 DEBT-02) gets a UI surface
  on the memberships list (within selector).
- Mock service implements freeze / unfreeze / renew + frozen status with semantics
  identical to backend so `VITE_API_MODE=mock` keeps working offline.

**Out of scope (separate phases / backlog):**

- Any new backend endpoints, schema changes, or migrations (locked by
  ROADMAP "regen ≠ rebuild" rule — backend Phases 25/26/27 already shipped).
- Phase 29 human-verification smoke tests (DEBT-04).
- Pagination UI for `MembershipsBlock` (still tracked as WR-06 — out of scope).
- Sales / membership-creation UX (covered by FE-08 already).
- Full freeze-history viewer (only the *current* freeze period is exposed —
  multi-period audit log is a future phase).

</domain>

<decisions>
## Implementation Decisions

### D-28-01: Single regenerate-then-commit cycle (drift-gate discipline)
The phase ships **exactly one** regen cycle, mirroring v1.2 Phase 21:
1. From `apps/backend/`, run `uv run python -m scripts.export_openapi`
   (writes `apps/backend/openapi.json`, byte-stable per `export_openapi.py:60`).
2. From repo root, run `pnpm --filter @sportzal/api-client codegen`
   (rewrites `packages/api-client/src/schema.d.ts` via openapi-typescript).
3. Commit both files in **one** commit at the very start of the phase, before
   any FE wiring touches the new shapes.
- All subsequent FE work consumes the regenerated `paths` / `components` directly.
- If a backend bug surfaces during FE wiring → fix backend, run the cycle once
  more, but only as a last resort (planner must justify in PLAN.md).
- CI gates that must stay green: `git diff --exit-code apps/backend/openapi.json`
  + `git diff --exit-code packages/api-client/src/schema.d.ts` (`.github/workflows/ci.yml:60,114`).

### D-28-02: Domain types extended in `entities/membership/types.ts`
- `MembershipStatus = 'active' | 'expired' | 'cancelled' | 'frozen'`
  (replaces the 3-value union at `apps/admin-web/src/entities/membership/types.ts:5`).
- `Membership` gains:
  - `freezeDaysLimitSnapshot: number`
  - `freezeDaysUsed: number`
  - `freezeDaysRemaining: number` (`= max(limit - used, 0)`, computed server-side)
  - `currentFreezePeriod: FreezePeriod | null` (null when `status !== 'frozen'`)
  - `previousMembershipId?: string | null` (renewal chain attribution; nullable)
- New nested type `FreezePeriod = { id: string; startedAt: string; startedBy: string; endedAt: string | null; endedBy: string | null }`
  exposed from `entities/membership/index.ts`.
- Backend wire format is already camelCase via `BackendSchemaBase` (carry-forward
  decision); adapter does identity mapping for the new fields.

### D-28-03: Service contract gains 3 mutations
Extend `MembershipsService` (`apps/admin-web/src/shared/api/contracts/memberships.ts`):
```ts
freeze(id: MembershipId): Promise<Membership>      // 200; updated source membership
unfreeze(id: MembershipId): Promise<Membership>    // 200; updated source membership
renew(id: MembershipId): Promise<Membership>       // 201; the NEW membership (chain child)
```
- All three are CSRF-required POSTs (existing `request<P,M>` already handles CSRF).
- `renew` resolves with the **new** membership — caller navigates to it on success.
- Mock and http implementations share signatures.

### D-28-04: HTTP adapter — typed via generated `paths`
`apps/admin-web/src/shared/api/services/http/memberships.ts` adds three new
operations using the regenerated paths:
- `request('post', '/api/v1/memberships/{membership_id}/freeze', { params: { membership_id: id } })`
- `request('post', '/api/v1/memberships/{membership_id}/unfreeze', { params: { membership_id: id } })`
- `request('post', '/api/v1/memberships/{membership_id}/renew', { params: { membership_id: id } })`
Response goes through `unwrap<MembershipResponse>(...)` → `responseToMembership(...)`.
`_membershipsAdapter.ts` extends `responseToMembership` to populate the new fields
(direct assignment — no snake/camel mapping needed because `BackendSchemaBase`
already camelizes; only nested `current_freeze_period`/`currentFreezePeriod` needs
a typed re-export).

### D-28-05: Mock parity — same semantics, in-memory
`apps/admin-web/src/shared/api/services/mock/memberships.ts` implements
freeze / unfreeze / renew with backend-equivalent behaviour:
- **freeze:** when `status === 'active'` AND `freezeDaysRemaining > 0` → set
  `status = 'frozen'`, allocate a new `currentFreezePeriod = { id: faker.uuid(),
  startedAt: now, startedBy: actorId, endedAt: null, endedBy: null }`. Throw
  `DomainError('freeze_limit_exceeded' | 'already_frozen' | 'invalid_transition')`
  with the exact codes the backend returns (Phase 25 router lines 354–355).
- **unfreeze:** close current period (`endedAt = now`, `endedBy = actorId`),
  extend `endDate` by `ceil((endedAt - startedAt) / 86_400_000)` days, increment
  `freezeDaysUsed`, recompute `freezeDaysRemaining`, `status = 'active'`.
- **renew:** create a NEW membership with `previousMembershipId = source.id`,
  `status = 'active'`, snapshots copied from current source plan, dates
  computed via the same rule the backend uses (D-28-08), insert into mock DB,
  return new row. Throw `DomainError('cannot_renew_cancelled' | 'plan_archived')`
  on the corresponding states.
- Mock DB key bumps to `sportzal:mock:v2` only if shape change is destructive;
  default is to extend in place (`v1` kept) and let the seed re-populate
  freeze counters with `freezeDaysLimitSnapshot = plan.durationDays / 7` rounded
  (planner picks a sensible default — value only matters for FE story testing).
- RBAC enforced inside mock service via `can(role, 'CREATE', 'MEMBERSHIPS')` /
  `can(role, 'DELETE', 'MEMBERSHIPS')` (carry-forward DomainError pattern).

### D-28-06: TanStack Query hooks
Add to `apps/admin-web/src/features/memberships/api/hooks.ts`:

- **`useFreezeMembership()` — optimistic**
  - `onMutate({ membershipId })`: cancel `lists()` + `detail(membershipId)`,
    snapshot, patch detail+lists to `status='frozen'`, optimistic
    `currentFreezePeriod` placeholder (server replaces UUID/timestamps on settle).
  - `onError`: restore snapshots; surface `DomainError.message` via Sonner toast
    using `t('memberships.freeze.errors.<code>')`.
  - `onSettled`: invalidate `lists()`, `detail(id)`, `byClient(clientId)`.

- **`useUnfreezeMembership()` — optimistic**
  - Same pattern: status flips to `'active'`, `currentFreezePeriod = null`,
    `freezeDaysUsed` bumped optimistically by computed delta (rounded up).
  - On settle, server-truth replaces optimistic counters.

- **`useRenewMembership()` — NOT optimistic**
  - Mutation creates a new resource — UUID/dates known only after 201.
  - `onSuccess(newMembership)`: toast `t('memberships.renew.success')`, then
    `navigate({ to: '/memberships/$membershipId', params: { membershipId: newMembership.id } })`.
  - `onSettled`: invalidate `lists()`, `byClient(clientId)`,
    `detail(sourceMembershipId)` (so the source row reflects new
    `previousMembershipId` chain consistency), `byClient(newMembership.clientId)`.
  - During pending: `useMutation().isPending` drives button spinner + disable.

### D-28-07: Routes — flat detail route mirrors clients pattern
Add `apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx`
(flat-route convention, mirrors the existing `clients_.$clientId.tsx` shape).
- Route loader: `queryClient.ensureQueryData(membershipsKeys.detail(id), ...)`
  using the same key as `useMembership(id)` — consistent with the Conventions
  rule "Route loader calls ensureQueryData with the same key the hook uses".
- `validateSearch`: empty Zod schema (no search params on detail).
- `beforeLoad`: no extra RBAC — both roles can read; action-level gating lives
  in components.

### D-28-08: Renew confirm dialog uses snapshot data only
- The dialog reads from the **already-loaded** source membership cache —
  no separate `services.memberships.getPlan(planId)` round-trip needed because
  `priceKopecksSnapshot`, `durationDaysSnapshot`, `planNameSnapshot` already
  live on `Membership`.
- Computed dates (display-only — backend recomputes server-side):
  - `newStartDate = max(todayMSK, currentEndDate + 1 day)`
  - `newEndDate = newStartDate + durationDaysSnapshot - 1` (inclusive end_date)
- Dates rendered via `formatDate(..., { locale: ru })` from `shared/i18n/date.ts`.
- Price rendered via `formatMoney(priceKopecksSnapshot)` (`shared/lib/money.ts`).
- Dialog uses shadcn `<AlertDialog>`; confirm calls `useRenewMembership().mutate`.
- If backend resolves a different start/end (edge: cron runs between dialog open
  and confirm) — the success toast + navigate to the new membership reflects
  the authoritative server result; we do NOT race-validate on the client.

### D-28-09: Freeze button states + tooltip
- Visible when `status === 'active'` AND user has `(CREATE, MEMBERSHIPS)`.
- **Disabled** when `freezeDaysRemaining === 0`; tooltip text from
  `t('memberships.freeze.no_days_remaining')` (locked i18n key per FE-10).
- During pending: `disabled + spinner`.
- After freeze: button swaps to "Снять заморозку"
  (`useUnfreezeMembership`), badge "Заморожено с {startedAt}" appears next to it.

### D-28-10: Frozen status badge — distinct visual
- Badge variant for `'frozen'`: shadcn semantic token, NOT a raw palette colour
  (ESLint `eslint.config.js:71-83` enforces). Recommended: use the warning /
  amber semantic token already in shadcn's neutral palette to differentiate
  from `active` (green-ish), `expired` (muted), `cancelled` (destructive).
  Planner picks the exact token — must be semantic.
- Badge appears on:
  - Membership detail header (D-28-07).
  - Memberships list page status column.
  - `clients/$clientId` overview `MembershipsBlock` (carry-forward FE-08 layout).

### D-28-11: List filter — frozen as first-class status
- `MembershipListSort` is unchanged; the **status filter chip** on
  `_protected/memberships.tsx` adds a 4th pill "Заморожен".
- Filter state lives in route search params (`?status=frozen`) via
  TanStack Router `validateSearch` (Zod). Mock + http already accept any
  `MembershipStatus` value via the `status?` query param.

### D-28-12: Within selector for expiring filter (FE-13)
- On `_protected/memberships.tsx` add a "Истекает в течение" selector visible
  ONLY when the "Истекающие" toggle is on.
- Choices: `1, 3, 7, 14, 30` (default `7` — preserves FE-08 D-2 cheap-win).
- State sync via TanStack Router search params (`?expiring=true&within=14`),
  forwarded into `useMembershipsList({ expiring, within })`.
- HTTP + mock services already accept `within` (Phase 24 DEBT-02 lines 41–53
  in `http/memberships.ts:48-54`); this phase only adds the UI surface.
- Out-of-range values (e.g., user manually edits the URL to `within=99`):
  Zod schema clamps to `[1..30]` with default `7`; backend defence-in-depth
  still 422s but the UI never sends invalid values.

### D-28-13: i18n — Russian-only, planner locks exact strings
New keys under `memberships.*` in `apps/admin-web/src/shared/i18n/ru.ts`:
- `memberships.status.frozen` ("Заморожен")
- `memberships.freeze.button` ("Заморозить")
- `memberships.freeze.no_days_remaining` (tooltip — exact text locked at planner step)
- `memberships.freeze.errors.freeze_limit_exceeded`
- `memberships.freeze.errors.already_frozen`
- `memberships.freeze.errors.invalid_transition`
- `memberships.freeze.success` ("Абонемент заморожен")
- `memberships.unfreeze.button` ("Снять заморозку")
- `memberships.unfreeze.success` ("Заморозка снята")
- `memberships.frozen.badge` ("Заморожено с {date}")
- `memberships.frozen.period_dates` ("С {startedAt} по {nowOrEndedAt}")
- `memberships.renew.button` ("Продлить")
- `memberships.renew.confirm.title` ("Продлить абонемент?")
- `memberships.renew.confirm.body` (template w/ `{plan}`, `{price}`, `{startDate}`, `{endDate}`)
- `memberships.renew.confirm.cta` ("Продлить")
- `memberships.renew.confirm.cancel` ("Отмена")
- `memberships.renew.success` ("Абонемент продлён")
- `memberships.renew.errors.cannot_renew_cancelled`
- `memberships.renew.errors.plan_archived`
- `memberships.list.expiringWithin.label` ("Истекает в течение")
- `memberships.list.expiringWithin.option_days` ("{n} дн.")
- `memberships.detail.title` ("Абонемент")
- `memberships.detail.section.freeze` ("Заморозка")
- `memberships.detail.section.renewal` ("Продление")
- `memberships.detail.previousMembership` ("Продлён из абонемента")
Planner picks final wording with the user (NTF-COPY-01 process is NOT required
here — FE strings, not Telegram DMs).

### D-28-14: RBAC reuse — no new resources
- Freeze / unfreeze / renew gated by `(CREATE, MEMBERSHIPS)` (both roles).
- Cancel-during-freeze stays **owner-only** — carry-forward from FE-08 cancel
  pattern; the cancel button on the detail page consults `OWNER_ONLY` already.
- Use existing `<RoleGate>` wrapper + `can()` for in-page action visibility.

### D-28-15: Tests — Vitest + renderWithProviders, no new infrastructure
- Mock service: parity tests for freeze / unfreeze / renew mirroring
  `memberships.expiring.test.ts` (file naming convention).
- Hooks: unit tests for optimistic patches + rollback (mock the service module).
- Route + components: integration tests via `renderWithProviders(ui, { role })`
  for both `'owner'` and `'reception'` (RBAC matrix).
- Status badge component: snapshot/role-based render test.
- Within selector: search-param round-trip test on the list route.
- Backend tests are NOT touched — Phases 25/26/27 already cover endpoints.
- Aim: no regression vs current ≥190 admin-web tests baseline.

### D-28-16: Plan order (planner discretion within these constraints)
Recommended sequencing (planner may merge plans but order is load-bearing):
1. **28-01 Drift-gate refresh** — single commit regenerating both artifacts.
   Atomic, no FE code touches yet. Verifies CI stays green.
2. **28-02 Domain + contracts + i18n stubs** — extend types, contract surface,
   adapter, i18n keys (no UI yet). Unblocks 03/04.
3. **28-03 Mock service freeze/unfreeze/renew + parity tests** — keeps
   mock-mode usable while http wiring lands.
4. **28-04 HTTP adapter freeze/unfreeze/renew** — uses regenerated `paths`.
5. **28-05 Hooks (freeze/unfreeze/renew) + tests**.
6. **28-06 Detail route + freeze/unfreeze/renew UI + RBAC + tests**.
7. **28-07 List + clients overview frozen badge + status filter**.
8. **28-08 Within selector for expiring filter (FE-13)**.

Steps 2–8 may not regenerate openapi/schema — that would re-open the drift
cycle and break D-28-01.

### Claude's Discretion (planner picks)
- Exact shadcn semantic token used for the frozen badge (must be semantic;
  raw palette banned).
- Whether `useFreezeMembership` and `useUnfreezeMembership` share an internal
  helper (cache patch utility) or stay separate hook bodies.
- Detail page section order (header / freeze / renewal / metadata) — both
  roles see the same layout.
- Whether the within selector renders as `<Select>`, segmented control, or
  inline chips — pick whatever matches existing list filter UX.
- Mock seed value for `freezeDaysLimitSnapshot` (any sensible default 14–30).
- Whether `_membershipsAdapter.ts` exports `responseToFreezePeriod` or inlines
  the mapping inside `responseToMembership` (3 fields, marginal).

</decisions>

<specifics>
## Specific Ideas

- "Один цикл регенерации, ни циклом больше — повторяем дисциплину v1.2 Phase 21,
  иначе drift-gate превращается в шум."
- Detail route follows the same flat pattern that `clients_.$clientId.tsx`
  already uses — keep the convention so new contributors don't invent a new one.
- Renew confirm dialog should feel like a one-shot decision: price + dates
  visible, single confirm CTA, no nested forms (snapshot data only).
- Frozen badge needs to be visually distinct enough that an operator scanning
  the list immediately notices "this one isn't expiring on its end_date".
- Within selector defaults to 7 to preserve the FE-08 D-2 cheap-win window;
  power users get 1/3/14/30 without breaking that default.
- All Russian strings written by the planner — no machine translations from
  English fallbacks; matches the project's Russian-only v1 stance.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements (locked scope)
- `.planning/ROADMAP.md` §"Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring"
  (lines 136–147) — 5 success criteria (drift-gate, FE-10..FE-13).
- `.planning/REQUIREMENTS.md` lines 67–70 (FE-10..FE-13 acceptance text);
  line 18 (DEBT-02 reminder); line 154 (Phase 28 mapping).
- `.planning/PROJECT.md` "Key Decisions" — backend wire format = camelCase via
  `BackendSchemaBase`; pagination envelope `{items, total, page, pageSize}`;
  membership `end_date` is inclusive.

### Drift-gate scripts + CI gates (must stay green)
- `apps/backend/scripts/export_openapi.py` — byte-stable export
  (`indent=2, sort_keys=True, ensure_ascii=False, trailing newline`).
- `packages/api-client/package.json` `scripts.codegen` — openapi-typescript invocation.
- `.github/workflows/ci.yml` lines 49–64 (backend drift-gate),
  lines 100–117 (frontend drift-gate). Both run `git diff --exit-code`.

### Backend contract (already shipped — read before regenerating)
- `apps/backend/app/modules/memberships/router.py` lines 17–22 (endpoint summary),
  328–425 (freeze / unfreeze / renew route definitions, error shapes).
- `apps/backend/app/modules/memberships/schemas.py`
  - lines 125–137 — `FreezePeriodResponse`.
  - lines 158–164 — `MembershipStatus` enum (4 values, includes `frozen`).
  - lines 227–256 — `MembershipResponse` (current source of truth for the
    frontend domain shape).
  - lines 262–289 — `MembershipListQuery` (status, expiring, within semantics).
- `apps/backend/openapi.json` — pre-Phase-28 baseline (will be regenerated).

### Carry-forward phase decisions
- `.planning/phases/24-foundations-tech-debt-bedrock/24-CONTEXT.md` — DEBT-02
  baseline (`expiring`/`within` already wired through http + mock list).
- `.planning/phases/25-memberships-freeze-backend/25-CONTEXT.md` — freeze
  endpoint semantics, error codes, `freezeDaysLimitSnapshot` rationale.
- `.planning/phases/26-memberships-renewal-backend/26-CONTEXT.md` — renewal
  chain (`previousMembershipId`), 201 + new resource pattern, plan_archived
  error code.
- `.planning/phases/27-expiring-soon-telegram-notifications/27-CONTEXT.md`
  §"Mock service / FE parity (none in Phase 27)" — Phase 27 explicitly
  deferred FE parity to Phase 28.
- `.planning/milestones/v1.2-phases/21-CONTEXT.md` (if present) — original
  v1.2 drift-gate refresh discipline pattern this phase mirrors.

### Frontend contracts + adapters (will be edited)
- `apps/admin-web/src/entities/membership/types.ts` — `MembershipStatus`,
  `Membership` (extension target).
- `apps/admin-web/src/entities/membership/index.ts` — re-exports.
- `apps/admin-web/src/shared/api/contracts/memberships.ts` — `MembershipsService`
  interface (gain freeze / unfreeze / renew).
- `apps/admin-web/src/shared/api/services/http/memberships.ts` — http impl.
- `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts`
  — `responseToMembership` mapping target.
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — mock impl.
- `apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts`
  — parity test pattern to mirror.
- `apps/admin-web/src/features/memberships/api/hooks.ts` — add three mutation
  hooks (extends existing `useCancelMembership` optimistic pattern).
- `apps/admin-web/src/features/memberships/api/keys.ts` — query keys.
- `apps/admin-web/src/routes/_protected/memberships.tsx` — list route
  (status filter, within selector).
- `apps/admin-web/src/routes/_protected/clients_.$clientId.tsx` — pattern
  reference for the new flat detail route.
- `apps/admin-web/src/shared/i18n/ru.ts` — Russian dictionary (locked here).
- `apps/admin-web/src/shared/lib/money.ts`, `apps/admin-web/src/shared/i18n/date.ts`
  — formatters consumed by the renew dialog.
- `apps/admin-web/src/shared/session/can.ts`, `OWNER_ONLY` — RBAC carry-forward.
- `apps/admin-web/src/test/utils.tsx` — `renderWithProviders` (test entry).

### Conventions enforced by lint/typecheck (must not break)
- `eslint.config.js` lines 8–9, 71–83 — raw palette ban + import boundaries.
- `tsconfig` strict + `noUncheckedIndexedAccess` — array/record access.
- `import-linter` config — module boundary enforcement (carry-forward).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `request<P,M>` + `unwrap()` + `_envelope.ts` — typed transport already in
  place; new endpoints plug in without new infrastructure.
- `useCancelMembership` (`features/memberships/api/hooks.ts:74-109`) — optimistic
  cache patch + snapshot/rollback pattern to mirror for freeze/unfreeze.
- `responseToMembership` (`http/_membershipsAdapter.ts`) — extends to populate
  the new fields; backend already camelizes via `BackendSchemaBase`.
- `RoleGate` + `can()` (`shared/session`) — action-level RBAC, no new wiring.
- `formatMoney` + `formatDate` — already locale-pinned (RUB, ru-RU, MSK).
- shadcn `<AlertDialog>` / `<Badge>` / `<Tooltip>` — confirmation flow + status
  variants (semantic tokens only).
- TanStack Router `validateSearch` + Zod — already used on visits/clients
  search params; same pattern for `?status=frozen&expiring=true&within=N`.

### Established Patterns
- **Optimistic mutations:** snapshot via `qc.getQueriesData`, patch each match,
  restore in `onError`, invalidate in `onSettled` (FE-08 cancel mutation).
- **Flat detail routes:** `clients_.$clientId.tsx` — new memberships detail
  route uses the same flat-route convention.
- **Mock parity tests:** `memberships.expiring.test.ts` — file-naming + test
  shape to mirror for `memberships.freeze.test.ts` etc.
- **Service swap seam:** `services/index.ts` chooses mock vs http via
  `VITE_API_MODE`. Both impls implement the same contract; consumers never
  touch the impl directly (lint-enforced).
- **`ensureQueryData` in route loader == hook key** — convention enforced by
  Conventions doc; new detail route follows it.

### Integration Points
- `MembershipsService` contract is the single seam between FE features and the
  two impls (mock/http) — extending it touches both.
- `entities/membership/types.ts` is upstream of: contracts, hooks, components,
  i18n consumers, tests. Land status extension first to avoid type cascades.
- New detail route auto-registers in `routeTree.gen.ts` after `pnpm dev` /
  `pnpm build`; planner verifies the generated tree commits cleanly.
- The drift-gate commit (28-01) is upstream of every other plan in this phase;
  later plans must not invalidate openapi.json.

</code_context>

<deferred>
## Deferred Ideas

- Multi-period freeze history viewer (only current freeze period exposed in v1.3).
- `MembershipsBlock` pagination on `clients/$clientId` (still WR-06; v1.4).
- Freeze period edit / backdating UX — operator currently only freezes "now".
- Renewal preview (server-side dry-run endpoint) — current dialog computes
  client-side and trusts server result. Backend would need a new endpoint.
- Bulk freeze/unfreeze (e.g., during gym closure) — operations UI, future phase.
- Export of frozen-membership list to CSV — finance/reporting domain, separate
  milestone.
- Plan-change-on-renewal (renewing into a different plan) — current renew
  endpoint reuses source plan; cross-plan renewal is a new backend feature.

</deferred>

---

*Phase: 28-openapi-drift-gate-refresh-admin-web-wiring*
*Context gathered: 2026-05-10 (mode `--auto` — review before planning)*
