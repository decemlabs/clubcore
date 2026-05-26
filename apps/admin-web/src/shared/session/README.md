# Session module — RBAC contract

This is **not authentication.** The role is UI state, persisted via Zustand + `localStorage`
under the key `clubcore:session:v2`. Two roles exist in v1: `owner` (Владелец) and
`reception` (Ресепшн). Switching is a UI dropdown, not a login.

## Sources of truth

- `routeRegistry` (`./registry.ts`) — the **only** place that lists navigable routes,
  their resources, RU labels, and icons. The sidebar maps over this; the router's
  `beforeLoad` guards consume it; placeholder pages reference its `navKey` for i18n.
- `can(role, action, resource)` (`./can.ts`) — the **only** authorization decision
  function. The `OWNER_ONLY` table inside is the single matrix of restricted
  (action, resource) pairs. Owner short-circuits to `true`.

## When real auth ships (v2)

The session source flips from Zustand+localStorage to a JWT claim (or similar
server-driven role). **`can()` and `routeRegistry` do not change.** Only:

- `useSessionStore` is replaced by an auth-context provider.
- The router's `getSession` indirection in `app/router.ts` reads from that provider
  instead of the Zustand store.
- Mock-service 403-analog hooks (added in Phase 2) move to the HTTP layer.

This guarantees ROLE-05: replacing the session source preserves ACL logic.

## Consumers

1. Sidebar (`shared/ui/app-shell/Sidebar.tsx`) — filters `routeRegistry` by `can(role, 'view', entry.resource)`.
2. Router (`routes/<page>.tsx` `beforeLoad`) — second line of defense; redirects to `/?forbidden=...` if `can` returns false.
3. `<RoleGate action resource>` — render-time guard for action buttons (refund, delete, edit-template).
4. Mock services (Phase 2) — throw `DomainError({ code: 'FORBIDDEN' })` when `can` returns false.

All four consumers call the same `can()` function — there is no other implementation.
