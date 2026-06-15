# Phase 112: Critical Money & Access - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Two P0 operational gaps in the admin app:

1. **REF-01 — Arbitrary payment refund.** Owner can refund any recorded payment
   (cash / non-membership / non-PT), with a required reason, from the Cashbox or
   Finance screens. The refund is recorded in the append-only payments ledger and
   the cashbox balance reflects it. Removes the READ-ONLY `T-103-03-FAKEREFUND`
   stub in `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx`.

2. **TEAM-01 — Staff role change.** Owner can change an existing staff user's role
   (owner ↔ reception) from the Settings/Team screen via a modal; the change is
   persisted and audited. Reception cannot (403 on UI and endpoint).

Out of scope: a persisted RBAC/roles editor (frozen-contract CISO-01 byte-parity
invariant — two hardcoded roles suffice); refunding via the YooKassa online-refund
FSM (this phase is the manual/cash ledger refund, not the gateway path).
</domain>

<decisions>
## Implementation Decisions

### Refund — Behavior & Constraints
- **Refundable rows:** any non-refund payment row (`subject_kind != 'refund'`) that
  is not already fully refunded. Refund rows themselves are never refundable.
- **Partial refunds ALLOWED (user override).** The refund accepts an `amount_kopecks`
  field; the owner may refund a partial amount ≤ the original payment. Cumulative
  refunded amount across all refunds of one original MUST NOT exceed the original
  sale amount — over-refund is rejected.
  - ⚠ This is a deviation from the existing single-refund-per-sale model enforced by
    the partial UNIQUE `uq_payments_refund_of_alive`. The planner MUST address this:
    either (a) relax/replace the unique constraint to allow multiple partial refunds
    summing to ≤ original, or (b) scope v3.2 to a single partial refund of any amount
    ≤ original (keeps the unique constraint, adds an amount field). Prefer (b) if the
    constraint change is high-risk to the frozen audit/ledger invariants; document the
    choice in PLAN.md. Either way the UI must allow entering an amount defaulting to
    the full remaining amount.
- **Reason:** required free-text, minimum 3 characters; persisted in the ledger row
  and the audit payload.
- **Duplicate / over-refund handling:** backend rejects gracefully → 409 Conflict
  (or domain error) when the requested amount would exceed the remaining refundable
  amount, or when a row is already fully refunded. The UI hides/disables the refund
  action on fully-refunded rows.

### Refund — UI Integration
- **Locations:** refund action available BOTH in Cashbox (`TransactionsCard` row
  action) AND in the Finance payments table (per success criteria "Cashbox or Finance").
- **Confirmation UX:** modal dialog with a reason `textarea`, an amount field
  (defaulting to full remaining), and the original payment summary; confirm / cancel.
- **Feedback:** Sonner toast on success + invalidate the cashbox and finance React
  Query keys so the balance/ledger re-render with the new refund row.
- **Reception visibility:** the refund action is fully hidden via the `can()` gate
  (not merely disabled).

### Role Change — Behavior & UI
- **Location:** Settings screen, alongside the existing staff-user list
  (`SectionsBottom.tsx`, which already has invite/deactivate/reactivate/delete). A
  new "change role" action opens a modal (`AdaptiveModal`).
- **Endpoint:** `PATCH /api/v1/users/{user_id}/role` with body `{ role }`, guarded by
  `require_permission(Action.UPDATE, Resource.USERS)` (declared before `verify_csrf`),
  CSRF-protected, and audited. `(UPDATE, USERS)` is in OWNER_ONLY → reception → 403.
- **Guards:** reject demoting the last remaining owner (mirror the existing
  `cannot_deactivate_last_owner` guard) AND reject changing one's own role (mirror
  `cannot_deactivate_self`). Surface both as typed domain errors / ApiError codes.
- **Effect timing:** the role persists immediately; the new role is reflected on the
  user's NEXT login (existing sessions keep the old role until re-auth). No immediate
  session invalidation.

### Claude's Discretion
- Exact ApiError code strings for the new refund/role errors (follow existing
  `cannot_*` naming in users module and payments domain-error conventions).
- Whether the refund amount field is a separate input or pre-filled and editable.
- React Query key invalidation granularity (broad vs narrow) — match existing
  cashbox/finance hook conventions.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Backend refund core:** `app/modules/payments/service.py::issue_refund` already
  writes an append-only refund row (`subject_kind='refund'`, `refund_of=original.id`),
  with idempotency-key support and the `uq_payments_refund_of_alive` partial UNIQUE
  rejecting a second refund. `app/modules/payments/constants.py::SUBJECT_KIND_REFUND`.
- **Permissions:** `Action.REFUND` and `Resource.PAYMENTS`/`Resource.FINANCE` already
  exist in `app/core/permissions.py`; `(Action.REFUND, Resource.FINANCE)` is in
  OWNER_ONLY. `require_permission(...)` dependency + `verify_csrf` pattern.
- **Users module:** `app/modules/users/router.py` has the exact pattern to mirror —
  PATCH `/{user_id}/deactivate|reactivate` with `require_permission(UPDATE, USERS)` +
  CSRF, plus last-owner/self guards in `service.py`.
- **Audit:** `app/core/audit.py` + `app/core/audit_payloads.py` (refund audit payload
  already emitted from the online-refund path — reuse the taxonomy).
- **Frontend users feature:** `apps/admin-app/src/features/users/api.ts` —
  `usersKeys`, `useUsers`, `useDeactivateUser` (PATCH via `staffRequest` which
  auto-attaches `X-CSRF-Token`). Add `useChangeUserRole` here.
- **Frontend cashbox:** `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx`
  (the FAKEREFUND stub) + Finance payments table.
- **Modals:** `@/components/modals/AdaptiveModal`, `useModals`, `ModalButton`,
  `IconChip` (used by InviteModal in `SectionsBottom.tsx`).

### Established Patterns
- Backend: modular monolith under `apps/backend/app/modules/<domain>/`
  (router / service / repository / schemas / constants / models / permissions).
- RBAC enforced server-side via `require_permission`; OWNER_ONLY pairs → 403 reception.
- Money as integer kopecks; append-only payments ledger (refunds are new rows, never
  mutations); idempotency keys required on sale/refund POSTs.
- Frontend: TanStack Query per-feature `xKeys` factory + `staffRequest`; `can(role,
  action, resource)` gates UI actions; Sonner toasts; AdaptiveModal for dialogs.

### Integration Points
- New refund endpoint in `app/modules/payments/router.py` (or a cashbox/finance route)
  exposing `issue_refund` for arbitrary payment ids, RBAC-gated.
- New `PATCH /users/{user_id}/role` endpoint in `app/modules/users/`.
- Frontend: refund mutation hook (cashbox/finance feature), role-change hook in
  `features/users/api.ts`, wired into `TransactionsCard`, Finance table, and Settings
  staff-user list.
- OpenAPI regen (deferred to Phase 117 gate) will pick up the new routes.
</code_context>

<specifics>
## Specific Ideas

- Partial-refund support is an explicit user request (overrides the default
  full-only recommendation). The planner must reconcile it with the frozen
  append-only ledger + `uq_payments_refund_of_alive` invariant and pick approach
  (a) or (b) above, documenting the reasoning.
- Role change must reflect on next login, NOT kill the current session.
</specifics>

<deferred>
## Deferred Ideas

- Persisted RBAC / custom roles editor — explicitly out of scope (REQUIREMENTS.md
  Non-Goals; breaks CISO-01 byte-parity frozen-contract invariant).
- Refund through the YooKassa online-refund FSM / gateway — separate concern from
  this manual-ledger refund.
</deferred>
