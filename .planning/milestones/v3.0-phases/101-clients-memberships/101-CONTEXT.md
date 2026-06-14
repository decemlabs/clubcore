# Phase 101: Clients + Memberships - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the admin-app **clients**, **membership-plans**, and **memberships** (incl.
PT-packages) domains from mocks to the real backend over the transport seam built
in Phase 100. Staff manage the full client-membership lifecycle on real data: list
(server search + pagination), view, create, edit, soft-delete clients; manage plans
(owner-only); sell (cash, Idempotency-Key), freeze, unfreeze, renew, cancel, and
refund memberships. Client detail shows profile + memberships + visits + payments
from the backend (read-only narrow reads).

**In scope:** clients CRUD + list/detail; membership-plans CRUD; memberships
list/get/sell/freeze/unfreeze/renew/cancel/refund; PT-package plans + PT-package
sell (if endpoints exist — planner confirms first); client-detail child reads
(memberships/visits/payments); per-domain zod contract layer for each.

**Out of scope:** full Attendance/Finance screens (Phase 103) — only the narrow
client-detail visits/payments reads land here; dashboard/reports/settings (Phase
104); any new backend endpoints (wire-only, D-V30-SCOPE-WIRE).
</domain>

<decisions>
## Implementation Decisions

### Scope & Sequencing
- Flip **clients + membership-plans + memberships** from mock→http this phase, in
  waves (clients first, then plans, then memberships + lifecycle).
- **PT-packages:** include PT-package plans + PT-package sell (success criteria #4/#5
  name them). The planner MUST first confirm the real `pt_packages` / `pt-package-plans`
  endpoint contracts in the backend; if the endpoints are missing or too thin to wire
  meaningfully, DEFER PT-packages to a later phase with an explicit note (do not invent
  endpoints — wire-only).
- **Client detail:** wire memberships + visits + payments READ on the detail page now
  (criteria #2 requires them). These are narrow filtered reads
  (`GET /memberships?clientId=`, `GET /visits?clientId=`, `GET /payments?clientId=` —
  planner confirms the visits/payments read endpoints exist). Full Attendance/Finance
  UIs remain Phase 103.
- **Mock removal:** flip each wired domain's `queryFn` to `staffRequest` (http);
  KEEP the mock data files behind `VITE_API_MODE=mock` for tests/dev (per the P100
  documented removal path), but remove the dead default-mock branch for wired domains.

### Clients List UX (mock-UI vs real-API divergence)
- Search: **debounced (300 ms) server-side `q`**, min-2-char gate matching backend
  (`q` < 2 chars → treated as None).
- Pagination: **server-side `{items, total, page, pageSize}`**, page synced to URL;
  pageSize matches the existing UI default.
- Filters: **wire ONLY backend-supported filters** — `gender`, `tag`, `hasTelegram`,
  `createdFrom`/`createdTo` (date range), `sort`. **HIDE the mock's membership-status
  filter pills** (active/expiring/frozen/lead/expired) — `GET /clients` does not filter
  by membership status. Document this as a known UI reduction.
- Sort: backend enum is `created_at_desc` | `last_name_asc`. Map имя→`last_name_asc`,
  недавние→`created_at_desc`; **hide unsupported sorts** (expires/visits/last).

### Mutations & Membership Lifecycle
- **freeze / unfreeze** are optimistic with rollback (admin-web precedent); **sell,
  renew, cancel, refund** are non-optimistic (invalidate affected queries + Sonner
  toast + navigate where relevant).
- **Idempotency-Key:** a per-attempt `crypto.randomUUID()` sent as the `Idempotency-Key`
  header on `POST /memberships` (sell) and `/memberships/{id}/{cancel,freeze,unfreeze,renew}`.
  Extend the transport to accept a per-call idempotency key.
- **Refund:** confirm dialog with a **required reason (1–200 chars)**, **full-refund
  only** — NO amount field (backend `MembershipRefundRequest` forbids `amountKopecks`).
- **Cancel vs Refund:** two distinct actions. Cancel ends the membership (owner-only,
  optional reason ≤500); Refund is a separate endpoint (reason required, reception+owner
  per B-07). Surface backend rules; gate Cancel via `can()`.

### States & Permissions
- **can()-gate owner-only actions** so 403 is rare: membership-plans CRUD (owner-only),
  client DELETE (owner-only), membership cancel (owner-only). For reception on an
  owner-only screen (Plans), show a friendly inline «Недостаточно прав» state; if a 403
  still reaches the client, surface it as a non-blocking toast.
- Reuse existing `PageState` / `EmptyState` / `PageLoading` feedback components with
  Russian copy for loading/empty/error.
- **Zod mirrors backend constraints:** phone `^\+[1-9]\d{1,14}$`, email, tags
  (≤16, ≤32 chars each, lowercase regex `[a-z0-9а-я\-_]+`), notes ≤4096, plan
  `durationDays` 1-3650 / `priceKopecks` ≥0 / `freezeDaysLimit` 1-365 (immutable
  `durationDays` on plan PATCH — extra='forbid'). 422 `fields` → inline field errors.
- Client-detail **payments are read-only** (no refund/edit from the detail view —
  money actions live on membership lifecycle actions).

### Claude's Discretion
- New `features/memberships/` folder layout, query-key factories, component
  decomposition (sell/freeze/renew/cancel/refund dialogs), and test organization are
  at Claude's discretion, following the P100 `features/auth/` exemplar and admin-app
  conventions.
</decisions>

<code_context>
## Existing Code Insights

### Backend contracts (verified — wire is camelCase via Pydantic aliases)
- **Clients** `app/modules/clients/`: `GET /api/v1/clients` params
  `q,tag,gender,createdFrom,createdTo,hasTelegram,sort(created_at_desc|last_name_asc),page,pageSize`
  → `{data:{items,total,page,pageSize}}`; `GET /{id}`; `POST` (ClientCreateRequest:
  lastName/firstName/middleName/phone/email/birthday/gender/tags/notes/emergencyContact/telegramUserId);
  `PATCH /{id}`; `DELETE /{id}` (204, OWNER_ONLY). List/Get/Create/Update = reception+owner.
- **Membership-plans** `app/modules/memberships/`: list (`active,sort,page,pageSize`) /
  get / `POST` (name/durationDays/priceKopecks/freezeDaysLimit/active) / `PATCH`
  (durationDays immutable → 422) / `DELETE` — **all OWNER_ONLY**.
- **Memberships**: `GET /api/v1/memberships?clientId=&status=&sort=&expiring=&within=&page=&pageSize=`;
  `GET /{id}`; `POST` (sell: clientId/planId/paidAt?/notes?) + Idempotency-Key;
  `POST /{id}/cancel` (reason?≤500, OWNER_ONLY) + Idem; `POST /{id}/freeze` (empty body) + Idem;
  `POST /{id}/unfreeze` (empty) + Idem; `POST /{id}/renew` (empty, 201) + Idem;
  `POST /{id}/refund` (reason required 1-200, REFUND perm reception+owner).
  `MembershipResponse` carries plan snapshots + freeze fields (freezeDaysUsed/Remaining,
  currentFreezePeriod) + previousMembershipId.
- **PT-packages:** NOT fully mapped — planner must locate the pt-package-plans / pt-package
  sell endpoints (`app/modules/` — pt_packages?) and confirm before wiring.
- Error envelope top-level `{code,message,fields?}`; success `{data:…}` (P100 transport
  already handles both).

### admin-app current (files to flip — apps/admin-app/src/)
- `features/clients/api.ts` (`useClients`, `useClient`) + `types.ts` + `detail.ts`;
  pages `pages/clients/ClientsPage.tsx`, `pages/client/ClientPage.tsx`.
- `features/plans/api.ts` (`usePlans`) + `types.ts`; page `pages/plans/PlansPage.tsx`.
- **NEW** `features/memberships/` (lifecycle hooks + schemas + dialogs).
- Pages call hooks → hook swap is transparent (pages mostly unchanged); detail page
  child sections need wiring to the filtered reads.
- **Exemplar:** `features/auth/api.ts` + `schemas.ts` (P100) — the `staffRequest` +
  `Schema.parse(raw).data` pattern + per-domain zod layer to replicate.
- Transport: `src/api/client.ts` `staffRequest` (extend for per-call Idempotency-Key);
  `src/lib/authBus.ts`; `can()` from `src/shared/session/can.ts`.

### admin-web porting analog (apps/admin-web/src/features/)
- `clients/api/{hooks,keys}.ts` + `model/schema.ts` — useClientsList/useClient/useCreate/Update/Delete.
- `memberships/api/{hooks,keys}.ts` — useMembershipsByClient/List/Plans + create/cancel/
  freeze(optimistic)/unfreeze(optimistic)/renew + plan CRUD. Port the optimistic
  onMutate/rollback shapes.
</code_context>

<specifics>
## Specific Ideas

- The mock clients-list UI has filters (membership-status pills) and sorts
  (expires/visits/last) that the real `GET /clients` does NOT support — these are hidden,
  not faked. Surface only backend-supported filters/sorts.
- Refund is FULL-only with a required reason — no partial/amount input.
- All money is integer kopecks; format with the existing `formatMoney`-equivalent;
  dates ISO + Europe/Moscow display.
</specifics>

<deferred>
## Deferred Ideas

- Full Attendance screen + Finance/cashbox screens → Phase 103 (only narrow
  client-detail visits/payments reads here).
- Dashboard/reports/settings → Phase 104.
- Membership-status filtering on the clients list (no backend support) — future, if a
  backend filter is ever added.
- PT-packages — wired here IF endpoints exist; otherwise explicitly deferred by the planner.
</deferred>
