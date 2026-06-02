# Phase 75: Backend Field Additions - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Three additive field additions to **existing** client-portal schemas plus an idempotent seed of one promo code. Strictly Group-A "fill the gaps" work:

1. **PMEM-01** — `/client/membership` (and the nested `membership` in `/client/home`) exposes `price_kopecks` + `auto_renew` so the Profile screen can show what the client paid and an auto-renewal indicator.
2. **NOTIF-01** — `/client/me` accepts and persists a `notif_prefs` JSONB and returns it on GET, so notification toggles survive reload / PWA reinstall / device change (no longer localStorage-only).
3. **PROMO-01** — `FIT15` promo code is seeded and validates via the **existing** `POST /client/promo/validate` endpoint (the PWA chip `RECOMMENDED_PROMO = { code: 'FIT15' }` is already built, gated behind `recommendedPromo: false`).

**NOT in this phase:** no new backend domains; the ЮKassa checkout / activation path and server-authoritative pricing are untouched; promo-code admin CRUD is out (deferred — see Deferred Ideas); `tier`/`member_since_at`/tenure badge are explicitly excluded from v2.1.

</domain>

<decisions>
## Implementation Decisions

### Membership price & auto-renew (PMEM-01)
- **D-01:** Add `auto_renew: bool | None` to `ClientMembershipResponse`, **always returning `null`.** The domain has no auto-renewal concept (only manual `renew_membership` + the `previous_membership_id` chain — verified: `auto_renew` appears nowhere in `app/`). `null` is the explicit "not applicable" signal; the PWA hides the "Продление" row when `null`. A future autopay feature can populate the boolean without a schema break. Satisfies success-criterion #1's "boolean or null if the domain has no such flag".
- **D-02:** `price_kopecks` source = `Membership.price_kopecks_snapshot` (the immutable snapshot of what the client actually paid for *this* membership). NOT the current catalog plan price — the snapshot is historic truth and does not drift when a plan's price changes, and it requires no join to a possibly-deleted plan.
- **D-03:** Both fields go directly on `ClientMembershipResponse`, so they appear in **both** `/client/membership` and the `membership` slot of `/client/home`. The schema docstring (`schemas.py:1-10`) currently bans `price_kopecks_snapshot` as "owner-only economics" — that ban is **lifted for the client's own membership** in this phase; update the docstring to reflect the deliberate reversal (own-membership price is client-visible; other clients' economics remain owner-only via IDOR scoping).

### Notification preferences (NOTIF-01)
- **D-04:** `notif_prefs` is a **strict** Pydantic schema with exactly four boolean keys — `promo`, `schedule`, `trainer`, `sound` — matching the existing `SettingsScreen.jsx` toggles. Unknown keys are rejected. Stored as a JSONB column on `clients` (mirrors the existing `emergency_contact` JSONB pattern), but the wire contract is typed (not a free-shape blob).
- **D-05:** `PATCH /client/me` does a **full replace** of `notif_prefs` — the client sends all four keys, the server overwrites. No partial-merge / "key not sent vs false" ambiguity. The PWA already holds the whole object in state.
- **D-06:** `GET /client/me` returns **server-side defaults** when the column is NULL (never persisted): `{ promo: true, schedule: true, trainer: true, sound: false }` — identical to the current `NOTIF_DEFAULTS` in `SettingsScreen.jsx`. The server is the single source of truth for defaults. **Note for planning:** in v2.1 these prefs are persistence/consent only — no backend domain consumes them yet, so do NOT wire any notification-dispatch gating off them.

### FIT15 promo seed (PROMO-01)
- **D-07:** FIT15 is seeded via a dedicated **Alembic data-migration** (idempotent — `ON CONFLICT DO NOTHING` on the partial-unique `uq_promo_codes_code_alive` = `upper(code) WHERE deleted_at IS NULL`). This lands on **any clean DB including production**, satisfying success-criterion #3's "seed migration executed idempotently". This deliberately diverges from the FIT10/FIRST500 precedent, which live only in `scripts/seed_demo_data.py` (dev/demo only) — FIT15 is treated as a product code, not demo data.
- **D-08:** `applicable_to = NULL` (applies to both `membership` and `pt_package`) — the `RECOMMENDED_PROMO` chip in `CheckoutSheet.jsx` can appear in either checkout flow.
- **D-09:** FIT15 parameters: `discount_type='percentage'`, `discount_value=1500` (15%, encoded as percent×100 per the existing convention), `per_client_limit=1`, `max_uses=NULL` (no global cap), `valid_from=NULL` / `valid_until=NULL` (**no expiry window** — a hardcoded date in a migration would silently expire and break future UAT), `is_active=true`. Mirrors the FIT10 shape.

### Claude's Discretion
- Exact migration revision numbers (next sequential after `0048`), schema field ordering, and test file placement follow existing conventions — not user decisions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / milestone scope
- `.planning/ROADMAP.md` §"Phase 75: Backend Field Additions" — goal + 3 success criteria (including the `auto_renew` open-question resolution).
- `.planning/REQUIREMENTS.md` — PMEM-01, NOTIF-01, PROMO-01 full text + the `auto_renew` Open Question (resolved here by D-01) + the explicit v2.1 exclusion of tenure/`tier`.

### Client-portal contracts (where the new fields land)
- `apps/backend/app/modules/client_portal/schemas.py` — `ClientMembershipResponse` (lines 20-33, target for D-01/D-02/D-03; docstring lines 1-10 to update), `ClientMeResponse` (297-313) + `ClientProfileUpdateRequest` (277-294) (target for D-04/D-05/D-06), `ClientHomeResponse` (45-55, embeds membership).
- `apps/backend/app/modules/client_portal/router.py`, `service.py`, `repository.py` — `/client/membership`, `/client/me` GET+PATCH, `/client/promo/validate` implementation.

### Domain models
- `apps/backend/app/modules/memberships/models.py` §`Membership` (88-166) — `price_kopecks_snapshot` (128, D-02 source); confirms no `auto_renew` column (D-01 rationale).
- `apps/backend/app/modules/clients/models.py` §`Client` (68-128) — `emergency_contact` JSONB precedent (95-98) for the new `notif_prefs` column.
- `apps/backend/app/modules/promo_codes/models.py` §`PromoCode` (52-88) — fields + `uq_promo_codes_code_alive` partial-unique used by the FIT15 ON CONFLICT.

### Seed precedent
- `apps/backend/scripts/seed_demo_data.py` §`_seed_promo_codes` (88-130) — FIT10/FIRST500 idempotent-seed shape + the percent×100 / kopecks encoding to mirror in the FIT15 migration (D-07/D-09).
- `apps/backend/alembic/versions/0046_promo_codes.py` — table + constraints; `0048_client_onboarding_fields.py` is the latest migration (FIT15 + notif_prefs migrations follow it).

### Frontend consumers (read-only; wiring is Phase 76, but these define expected shapes)
- `apps/client-pwa/src/screens/SettingsScreen.jsx` (lines 20-23, 232-256) — `NOTIF_DEFAULTS` + the four toggle keys that define the D-04 schema.
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` (lines 35-50) — `RECOMMENDED_PROMO = { code: 'FIT15', label: '−15%' }` + `recommendedPromo` flag.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Client.emergency_contact` JSONB column — the exact pattern to copy for the `notif_prefs` JSONB column (nullable, `dict` mapped).
- `scripts/seed_demo_data.py::_seed_promo_codes` — copy-paste-able idempotent insert (pg_insert + `on_conflict_do_nothing` on `func.upper(code)` / `deleted_at IS NULL`) for the FIT15 migration body.
- `Membership.price_kopecks_snapshot` already populated on every membership row — D-02 needs no new data, just projection into the response schema.

### Established Patterns
- Money is integer kopecks (BigInteger), never float/Decimal; promo `discount_value` encodes percentage as `percent×100`.
- Client-portal schemas use camelCase wire via `alias_generator=to_camel` on `ResponseData` — `price_kopecks`→`priceKopecks`, `auto_renew`→`autoRenew`, `notif_prefs`→`notifPrefs`.
- `/client/me` PATCH already exists (Phase 999.5) with server-side validation in the service layer — `notif_prefs` validation belongs there, not in the wire schema.
- Idempotent seeding uses the `uq_promo_codes_code_alive` partial-unique index.

### Integration Points
- `ClientMembershipResponse` is shared by `/client/membership` and `/client/home` — one schema change covers both endpoints (D-03).
- `notif_prefs` adds a column to `clients` → new Alembic migration; `ClientMeResponse` + `ClientProfileUpdateRequest` gain the field.
- FIT15 validates through the **already-built** `POST /client/promo/validate` — no endpoint change, only data (D-07).

</code_context>

<specifics>
## Specific Ideas

- The PWA already ships the FIT15 chip and the four notification toggles fully built and gated/localStorage-only — this phase makes the backend able to serve them; the actual frontend wiring (flag flips) is Phase 76.
- `auto_renew` returning `null` is intentionally the "no autopay concept yet" sentinel, chosen so a future card-on-file/autopay milestone (deferred Group-B) fills the boolean without a contract change.

</specifics>

<deferred>
## Deferred Ideas

- **Promo-code admin CRUD** — the ability to create/edit/parameterize promo codes from an interface (raised during the FIT15 params discussion). Already on the v2.1 backlog as deferred; requires a staff/owner side, but `apps/admin-web` is a frozen mock-reference. Belongs to a future milestone after the staff-side decision — NOT Phase 75.
- **Autopay / card-on-file** (would give `auto_renew` a real value) — Group-B net-new domain (YooKassa saved-methods + `GET /client/payment-method`); deferred per REQUIREMENTS v2/Future table.

</deferred>

---

*Phase: 75-backend-field-additions*
*Context gathered: 2026-06-02*
