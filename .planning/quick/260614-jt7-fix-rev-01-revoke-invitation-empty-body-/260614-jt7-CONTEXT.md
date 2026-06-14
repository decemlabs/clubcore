# Quick Task 260614-jt7: Fix REV-01 revoke-invitation - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Task Boundary

Fix REV-01 (HIGH) from `.planning/v3.0-UAT-VERIFICATION-PASS.md`: revoking a **pending
invitation** is broken two ways:

1. `useRevokeInvitation` (`apps/admin-app/src/features/users/api.ts:141`) POSTs **no body**,
   but the endpoint declares `payload: InvitationRevokeRequest` as a required body param
   (`apps/backend/app/modules/users/router.py:177`) → **422**.
2. The frontend passes **`user.id`** as `{token_id}` (`SectionsBottom.tsx:612`), but the
   endpoint resolves the **`password_reset_tokens.id`** row id — which `GET /api/v1/users`
   never returns.

Scope: make the pending-invitation revoke path work end-to-end and verify live
(invite → revoke pending → 204 → row disappears). Active-user deactivate already works.
</domain>

<decisions>
## Implementation Decisions

### Approach — Variant B (user deferred: "choose what's better" → B)
Surface the invitation **token row id** in the `GET /api/v1/users` list response and have
the frontend pass it. Chosen over Variant A (new revoke-by-user endpoint) because:

- **Matches the original design intent.** `repository.py:337` docstring literally says
  *"owner UI shows the token row id; revoke endpoint resolves by it."* The list simply
  never wired the id; this completes the intended contract.
- **Smallest surface.** One nullable response field + populate it via the *existing*
  invitation join. The revoke endpoint, service (`revoke_invitation`), audit emit, and RBAC
  stay **100% unchanged**. No new endpoint, no orphaned/dead code.
- **Token row id is already non-secret** — it is the existing `{token_id}` path param
  (D-43-19), distinct from the raw token (raw token only ever in the invite email).
- Variant A would either add a new endpoint (orphaning the token-id endpoint as dead code)
  or mutate the existing contract — both bigger OpenAPI / contract-test / integration-test
  surface for no benefit here.

### Reason handling — fixed reason string (user choice)
The FE sends a non-empty body with a fixed audit reason: **`«Отозвано владельцем»`**
(revoke is owner-only — `(UPDATE, USERS)` ∈ `OWNER_ONLY`). No reason-input UI is added
(out of scope). The Russian literal lives in the component layer (`SectionsBottom.tsx`),
not the transport hook, per project convention ("strings inline in components").

### Claude's Discretion
- **Query shape:** the active-invitation subquery in `list_alive` can drop its
  `MAX(expires_at)` aggregation and select `id` + `expires_at` directly — the partial-unique
  `(user_id, purpose) WHERE consumed_at IS NULL` (D-41-05) guarantees ≤1 active invitation
  per user, so the LEFT JOIN cannot fan out.
- **Expired-pending edge:** a `pending_invitation` row whose token already expired yields
  `invitationTokenId = null` (subquery filters `expires_at > now()`). FE guards: if the id
  is absent, show an error toast and skip the call (an expired invite can't be revoked
  anyway — service raises `invitation_expired`). Rare given the multi-day TTL.
- Test depth, exact gate command invocations.
</decisions>

<specifics>
## Specific Ideas

- Backend field: `invitation_token_id: UUID | None = None` on `UserListItemResponse`
  (`schemas.py`), placed beside `invitation_expires_at`. camelCase alias auto-maps to wire
  `invitationTokenId` (`to_camel` via `ResponseData`/`ContractModel`).
- Populate in `repository.list_alive` invitation subquery (carry `PasswordResetToken.id`).
- Regenerate `apps/backend/openapi.json` (`uv run python -m scripts.export_openapi`) AND
  `packages/api-client/src/schema.d.ts` (`pnpm -F @clubcore/api-client codegen`) in the
  same commit — drift gate (FRZ-08) requires them byte-stable together.
- FE `UserSchema` (`features/users/schemas.ts`): add `invitationTokenId:
  z.string().nullable().optional()`.
- FE `useRevokeInvitation`: accept `{ tokenId, reason }`, send
  `body: { reason }`, keep `params.token_id`.
- FE caller (`SectionsBottom.tsx` pending-invitation branch): pass
  `{ tokenId: user.invitationTokenId, reason: 'Отозвано владельцем' }`, guard null id,
  drop the stale `// tokenId = user.id` comment.
</specifics>

<canonical_refs>
## Canonical References

- `.planning/v3.0-UAT-VERIFICATION-PASS.md` — REV-01 origin + the invite/revoke happy path
  to verify live.
- D-43-19 / D-43-10 / D-41-05 — invitation token row id contract & one-active-invite-per-user
  partial unique.
</canonical_refs>
</content>
</invoke>
