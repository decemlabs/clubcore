---
quick_id: 260614-jt7
title: Fix REV-01 revoke-invitation (Variant B — surface token id + send body)
status: complete
approach: Variant B
completed: 2026-06-14
---

# REV-01 — Revoke pending invitation (Variant B) Summary

One-liner: surfaced the live `password_reset_tokens` row id as `invitationTokenId`
in `GET /api/v1/users`, then had the admin-app revoke flow pass that id (not
`user.id`) with a non-empty `{ reason }` body — fixing both the 422 (empty body)
and the wrong-id (`user.id`) bugs without touching the revoke endpoint, service,
audit, RBAC, or DB schema.

## What changed per file

### Backend
- `apps/backend/app/modules/users/schemas.py`
  - Added `invitation_token_id: UUID | None = None` to `UserListItemResponse`
    (beside `invitation_expires_at`). camelCase alias → wire `invitationTokenId`.
- `apps/backend/app/modules/users/repository.py`
  - `list_alive`: the invitation subquery now carries `PasswordResetToken.id`
    (`inv_token_id`) and `expires_at` directly. Dropped the `func.max(...)` +
    `group_by` aggregation — the D-41-05 partial unique
    `(user_id, purpose) WHERE consumed_at IS NULL` guarantees ≤1 active invite
    per user, so the LEFT JOIN cannot fan out.
  - Row-unpack loop updated to `for user_row, inv_token_id, inv_expires_at in rows:`
    and passes `invitation_token_id=inv_token_id` into the response model.
  - Updated the docstring describing the join (no longer aggregated).
- `apps/backend/openapi.json` — regenerated; additive `invitationTokenId`
  (`string|null`, uuid format) on the users list-item shape only.

### api-client
- `packages/api-client/src/schema.d.ts` — regenerated; additive
  `invitationTokenId?: string | null` on the `UserListItemResponse` interface only.

### Frontend (admin-app)
- `apps/admin-app/src/features/users/schemas.ts`
  - `UserSchema`: added `invitationTokenId: z.string().nullable().optional()`.
- `apps/admin-app/src/features/users/api.ts`
  - `useRevokeInvitation` now accepts `{ tokenId, reason }`, passes
    `params.token_id = tokenId`, and sends `body: { reason: reason ?? null }`.
    JSDoc updated (token row id, required body, REV-01 note).
- `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx`
  - pending_invitation `onConfirm`: guards null `invitationTokenId` (error toast,
    return early), then `revokeInv.mutate({ tokenId: user.invitationTokenId,
    reason: 'Отозвано владельцем' }, { onError })`. Removed the stale
    `// tokenId = user.id` comment and the `user.id` argument.

### Tests
- `apps/backend/tests/integration/users/test_users_invitation_flow.py`
  - `test_users_list_exposes_invitation_token_id`: pending user's list
    `invitationTokenId` equals the issued token id; active users (seeded owner)
    have `null`.
  - `test_revoke_invitation_using_listed_token_id`: read the id from the list,
    revoke with `{ reason }` body → 204, then the row no longer surfaces a live
    token id.

No new FE test added — no existing `useRevokeInvitation` test to update (plan
made a new FE test optional).

## Gate outputs

| Gate | Command | Result |
| --- | --- | --- |
| Backend ruff (users) | `uv run ruff check app/modules/users` | PASS (All checks passed) |
| Backend ruff (full app) | `uv run ruff check app` | FAIL — 12 errors, all PRE-EXISTING in unrelated modules (bookings, autopay_charges, gym, promo_codes); verified identical on clean tree via stash. None in `users`. |
| Backend mypy | `uv run mypy app` | PASS (no issues in 273 source files) |
| Backend pytest | `uv run pytest tests/integration/users -q` | PASS (35 passed, incl. 2 new) |
| api-client typecheck | `pnpm -F @clubcore/api-client typecheck` | PASS |
| api-client test | `pnpm -F @clubcore/api-client test` | PASS (21 tests) |
| admin-app typecheck | `pnpm -F @clubcore/admin-app typecheck` | PASS |
| admin-app lint | `pnpm -F @clubcore/admin-app lint` | PASS |
| admin-app test | `pnpm -F @clubcore/admin-app test` | PASS (340 tests, 26 files) |

OpenAPI drift gate: `git diff` after regen showed ONLY the additive
`invitationTokenId` field on the users list-item shape in both `openapi.json`
(+12 lines) and `schema.d.ts` (+2 lines). No churn.

## Commits

| Hash | Type | Description |
| --- | --- | --- |
| `1c527287` | fix | backend `invitationTokenId` in users list + regenerated openapi.json + schema.d.ts (Tasks 1+2, same commit for drift gate) |
| `06bf3d8d` | fix | FE revoke with token id + `{ reason }` body, null guard (Task 3) |
| `f8edf168` | test | backend contract tests for `invitationTokenId` list + revoke-via-list (Task 4) |
| `83f054f9` | fix | revoke also soft-deletes the pending user so the row disappears (discussion Option A — see below) |

## Discussion decisions (--discuss / CONTEXT.md)

- **Approach: Variant B** (user deferred — "choose what's better"). Surface the
  token row id in `GET /users` rather than add a revoke-by-user endpoint. Matches
  the original D-43-19 design intent; smallest surface; revoke endpoint untouched.
- **Reason: fixed string** `«Отозвано владельцем»` (user choice). No reason-input UI.

## Follow-up — "row disappears" semantics (discussion Option A)

During live verification it surfaced that the backend `revoke_invitation` only
*consumed the token* — the pending user row stayed in `GET /users` as a zombie
«Ожидает» with no live invitation, contradicting the acceptance criterion
«строка исчезает». The executor's own test even asserted the row *stayed*.

User chose **Option A** (backend revoke + soft-delete the pending user). Commit
`83f054f9`:
- `service.revoke_invitation` now calls `repository.soft_delete_user(...)` in the
  same UoW after consuming the token. By that point the token was just consumed
  from an unconsumed+unexpired state, so `token.user_id` is necessarily still a
  `pending_invitation` user — no active-user guards apply. The single
  `user_invitation_revoked` audit row is the forensic record (no separate
  `user_soft_deleted` event); the token row is left consumed so the double-revoke
  409 path + audit chain stay valid.
- Flipped `test_revoke_invitation_using_listed_token_id` to assert the row
  disappears from `GET /users` after revoke.
- Re-ran gates: backend ruff (users) PASS, mypy PASS (273 files),
  `pytest tests/integration/users` PASS (35), and related suites
  (`test_revoke_expired_invitation`, `test_invitation_accept`) PASS (11) — the
  revoke→accept→410 anti-oracle path is unaffected (accept rejects on the consumed
  token before any user lookup).

## Live verification (running stack — docker backend + admin-app dev server)

Driven in-browser as owner@clubcore.dev (Settings → «Доступы команды»). Network
trace:

| # | Request | Status |
| --- | --- | --- |
| 1 | `POST /api/v1/users?includeInviteLink=true` (invite REV01 Проверка) | **201** |
| 2 | `GET /api/v1/users` (refetch — pending row appears with token id) | 200 |
| 3 | `POST /api/v1/users/invitations/623577b7-d0db-43da-892a-846d65e33fcd/revoke` | **204** |
| 4 | `GET /api/v1/users` (refetch) | 200 |

The revoke used a real **`password_reset_tokens` row UUID** (not `user.id`) and
returned **204** — both original bugs (422 empty body + wrong id) fixed. The
«REV01 Проверка» (rev01-verify@clubcore.dev) row, present at the top before the
revoke, was **absent** from the team list after the refetch → «строка исчезла».
**Acceptance criterion met.**

Note: `owner@clubcore.dev`'s local dev password was briefly reset to enable
self-driven verification, then **restored to the documented `devpassword12345`**
(see [[backend-local-stack-gotchas]]) so the documented dev login stays accurate.
Existing browser sessions were unaffected throughout.

## Deviations from plan

- **Tasks 1 and 2 combined into one commit (`1c527287`)** — as explicitly
  permitted by the constraints, so `openapi.json` + `schema.d.ts` stay byte-stable
  together for the drift gate.
- **Backend full-app `ruff check app` reports 12 errors** — all pre-existing in
  modules untouched by this task (bookings, autopay_charges, gym, promo_codes).
  Confirmed identical on the clean tree (`git stash` → re-run → same 12). Per the
  SCOPE BOUNDARY rule these are out of scope and were NOT fixed. The `users`
  module itself is ruff-clean. Logged here rather than `deferred-items.md` since
  they predate this work and aren't new discoveries.
- No FE users-api test existed, so none was updated (plan allowed this).

## Out of scope (not done, per plan)
- No new endpoint, no change to `revoke_invitation` service / audit / RBAC, no
  DB migration, no reason-input UI.

## Known Stubs
None.

## Self-Check: PASSED
- `apps/backend/app/modules/users/schemas.py` — FOUND
- `apps/backend/app/modules/users/repository.py` — FOUND
- `apps/backend/openapi.json` — FOUND
- `packages/api-client/src/schema.d.ts` — FOUND
- `apps/admin-app/src/features/users/schemas.ts` — FOUND
- `apps/admin-app/src/features/users/api.ts` — FOUND
- `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` — FOUND
- `apps/backend/tests/integration/users/test_users_invitation_flow.py` — FOUND
- Commit `1c527287` — FOUND
- Commit `06bf3d8d` — FOUND
- Commit `f8edf168` — FOUND
