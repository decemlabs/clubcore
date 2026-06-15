# Phase 113: Promo Codes CRUD - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Owner-facing CRUD for promo codes in the admin app (PROMO-01, PROMO-02):

1. **Backend:** a new admin CRUD router for the EXISTING `promo_codes` module
   (`apps/backend/app/modules/promo_codes/`) — `GET /api/v1/promo-codes` (list),
   `POST` (create), `PATCH /{id}` (edit), `PATCH /{id}/deactivate`. The module already has
   `models.py` (PromoCode + PromoRedemption) and `service.py` (validate/redeem used by
   client_portal + yookassa) — this phase adds admin write/list, NOT the redemption path.
2. **Frontend:** the Plans page «Скидки и акции» section currently renders MOCK `PromoCard`s
   (`apps/admin-app/src/pages/plans/components/PromoCard.tsx`, `features/plans/types.ts` Promo).
   Replace with real data from `GET /api/v1/promo-codes`; add create/edit/deactivate modals;
   render empty state.

Out of scope: the client-side promo validation/redemption flow (already shipped — Phase 999.4
/ 82-84); promo analytics dashboards (later phases).
</domain>

<decisions>
## Implementation Decisions

### Backend CRUD — Endpoints & RBAC
- **Endpoints:** `GET /api/v1/promo-codes` (list), `POST /api/v1/promo-codes` (create),
  `PATCH /api/v1/promo-codes/{id}` (edit), `PATCH /api/v1/promo-codes/{id}/deactivate`.
- **RBAC:** add a NEW `Resource.PROMO_CODES` to `app/core/permissions.py`. Write actions
  (`CREATE`, `EDIT`, `DELETE`/deactivate) go in `OWNER_ONLY` → reception 403. Read
  (`LIST`/`VIEW`) allowed for both roles. MUST update: the RBAC parity test
  (`tests/integration/test_rbac_parity.py`) and the frontend `can.ts` + its OWNER_ONLY list,
  keeping backend↔FE parity (the staff-cookie / 41-entry RBAC parity invariant). `require_permission`
  declared BEFORE `verify_csrf` on every write route; CSRF on all writes.
- **Code handling:** normalize promo `code` to UPPER on write; enforce uniqueness among
  alive (non-soft-deleted) rows (partial UNIQUE, mirror the existing alive-uniqueness pattern).
- **Discount value semantics (per model):** `discount_type='fixed'` → `discount_value` is
  kopecks; `discount_type='percentage'` → `discount_value` is percent×100 (basis points).
  The FE converts user input (rubles / whole percent) to/from this representation.

### Schema — description column + migration
- **Add a nullable `description: str | None` column** to the `promo_codes` table (success
  criteria #2 requires editing the description). Additive nullable column, no backfill — safe
  Alembic migration. Include a `[BLOCKING]` task to create + apply the migration.
- `applicable_to` (existing nullable column) is surfaced as an optional editable field
  (default: applies to all plans / null).

### List & UI (Plans page)
- **`GET` response is the paginated envelope** `{ items, total, page, pageSize }` (project
  pagination convention — never a bare array).
- **Include a `used_count` aggregate** per code (count of `promo_redemptions` rows referencing
  it) so the card can show usage vs `max_uses`.
- **Create/edit UI:** `AdaptiveModal` form with fields — code, discount type toggle
  (percentage/fixed) + value, `max_uses`, `per_client_limit`, validity window
  (`valid_from`/`valid_until`), `applicable_to`, `description`. Deactivate = confirm dialog.
- **Reception:** create/edit/deactivate actions hidden via `can(role, ..., 'promo-codes')`;
  the list itself remains visible to reception.
- Success/error feedback via Sonner toast + invalidate the promo-codes React Query key.

### Claude's Discretion
- Exact list/create/edit Pydantic schema field names and FE Zod shapes (follow existing
  module conventions; camelCase on the wire).
- Whether deactivate is a dedicated route or `PATCH {is_active:false}` — recommended dedicated
  `PATCH /{id}/deactivate` for clarity and auditability.
- React Query key factory naming (`promoCodesKeys`).
- Whether to emit an audit event for promo create/edit/deactivate (nice-to-have; if added,
  follow INFRA-15 pre-registration like phase 112's `user_role_changed`).
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Backend promo module:** `app/modules/promo_codes/models.py` — `PromoCode`
  (code, discount_type, discount_value, max_uses, per_client_limit, valid_from, valid_until,
  is_active, applicable_to; UUIDPk + Timestamp + SoftDelete mixins) and `PromoRedemption`.
  `service.py` has `validate_promo_code` / `record_promo_redemption` + typed
  `Promo*Error(ValidationAppError)` classes — reuse the error style for CRUD errors.
- **CRUD router analog:** mirror an existing admin module router (e.g. `pt_packages/router.py`,
  `users/router.py`) for the list/create/patch + RBAC + CSRF pattern. Phase 112's
  `payments`/`users` routers are the freshest analogs (require_permission-before-verify_csrf).
- **Pagination:** existing list endpoints return `{items,total,page,pageSize}` — reuse the
  shared pagination schema/helper.
- **Migrations:** Alembic under `apps/backend/alembic/` (async). Latest revision e.g. 0036.
- **RBAC parity:** `tests/integration/test_rbac_parity.py` + `app/core/permissions.py`
  (Action/Resource enums + OWNER_ONLY) + FE `apps/admin-app/src/shared/session/can.ts`.
- **Frontend:** `pages/plans/PlansPage.tsx` («Скидки и акции» section), `components/PromoCard.tsx`,
  `features/plans/types.ts` (Promo type + mock). `mocks/plans.ts` holds the mock promo cards.
  Reuse `@/components/modals/AdaptiveModal`, `ModalButton`, `IconChip`, `ChipGroup`, and the
  feature-hook + `staffRequest` + per-feature `xKeys` pattern (see `features/users/api.ts`).

### Established Patterns
- Modular monolith: `apps/backend/app/modules/<domain>/{router,service,repository,schemas,
  models,constants}.py`. Server-side RBAC via `require_permission`; OWNER_ONLY → 403 reception.
- Money integer kopecks; dates ISO + TZ Europe/Moscow; soft-delete via SoftDeleteMixin.
- Frontend: TanStack Query per-feature keys + `staffRequest` (auto X-CSRF-Token on POST/PATCH);
  `can()` gates UI actions; semantic shadcn tokens only; Sonner toasts; AdaptiveModal dialogs.

### Integration Points
- New `promo_codes/router.py` registered in the API v1 router aggregation (wherever module
  routers are included — check `app/main.py` / api router include list).
- New `Resource.PROMO_CODES` in permissions.py + OWNER_ONLY pairs + FE can.ts + parity test.
- Alembic migration adding `promo_codes.description`.
- Frontend `features/promoCodes/` (api.ts + schemas.ts) consumed by PlansPage; PromoCard
  re-pointed from mock to real data; create/edit/deactivate modals.
- OpenAPI regen deferred to Phase 117 — note the new routes for the milestone gate.
</code_context>

<specifics>
## Specific Ideas

- `description` editable column is an explicit user-accepted addition requiring an Alembic
  migration (success criteria #2).
- New `Resource.PROMO_CODES` accepted over reusing MEMBERSHIP_PLANS — keep backend↔FE RBAC
  parity (permissions.py + can.ts + parity test all updated together).
- `used_count` aggregate from `promo_redemptions` included in the list response.
</specifics>

<deferred>
## Deferred Ideas

- Promo redemption/validation flow — already shipped (client portal, Phases 82-84 / 999.4).
- Promo analytics / conversion dashboards — out of scope for this phase.
- OpenAPI regeneration — deferred to Phase 117 milestone gate.
</deferred>
