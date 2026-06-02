# Phase 75: Backend Field Additions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 75-backend-field-additions
**Areas discussed:** auto_renew source, price_kopecks source & privacy, notif_prefs shape & semantics, FIT15 seed

---

## auto_renew — how to fill the field

| Option | Description | Selected |
|--------|-------------|----------|
| Field = null always | Add `auto_renew: bool \| None`, always return null — explicit "not applicable" signal; PWA hides "Продление" row; future autopay fills the bool without a schema break | ✓ |
| Don't add the field | Expose only `price_kopecks`; remove the renewal UI row; minimal contract but future autopay needs schema expansion | |
| Derive from chain | Surface "renewed" via `previous_membership_id`/successor — but that's past-renewal fact, not auto-renew; misleading semantics | |

**User's choice:** Field = null always (D-01)
**Notes:** Confirmed via code scout that `auto_renew` exists nowhere in `app/`; only manual `renew_membership` + chain.

---

## price_kopecks — source & privacy

| Option | Description | Selected |
|--------|-------------|----------|
| snapshot — what client paid | `Membership.price_kopecks_snapshot` — immutable historic price; no drift on plan price change; data already in row | ✓ |
| current plan price | `MembershipPlan.price_kopecks` from catalog — "cost to renew now"; can diverge from paid; needs join to possibly-deleted plan | |

**User's choice:** snapshot (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Everywhere the schema is used | Add fields to `ClientMembershipResponse` → appears in `/client/membership` + `/client/home`; update docstring | ✓ |
| Only /client/membership | Separate projection so /client/home stays priceless; more code/duplication | |

**User's choice:** Everywhere the schema is used (D-03)
**Notes:** Lifts the docstring's "owner-only economics" ban for the client's own membership only.

---

## notif_prefs — shape & semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Strict 4-key schema | Pydantic model, exactly promo/schedule/trainer/sound bools; unknown keys rejected; JSONB storage, typed contract | ✓ |
| Free-shape JSONB blob | Like emergency_contact, UI-owned; flexible but server can't guarantee shape / garbage risk | |

**User's choice:** Strict 4-key schema (D-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Full object replace | Client sends all 4 keys, server overwrites; simplest, no partial states | ✓ |
| Partial merge | Client sends only changed keys; less traffic, harder ("not sent" vs false) | |

**User's choice:** Full object replace (D-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Server defaults on NULL | Return `{promo:T, schedule:T, trainer:T, sound:F}` — single source of truth | ✓ |
| null / absent field | PWA applies defaults; defaults duplicated front + back | |

**User's choice:** Server defaults on NULL (D-06)
**Notes:** v2.1 prefs are persistence/consent only — no domain consumes them; do not wire dispatch gating.

---

## FIT15 seed

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic data-migration | Idempotent ON CONFLICT DO NOTHING; lands on any clean DB incl. prod; matches success-criterion #3 | ✓ |
| seed_demo_data.py | Matches FIT10/FIRST500 pattern but dev/demo only; contradicts "seed migration" | |
| Both migration + script | Migration for prod + demo script for completeness; duplicated seed source | |

**User's choice:** Alembic data-migration (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Both (membership + pt) — NULL | `applicable_to = NULL`; chip works in both checkout flows | ✓ |
| membership only | `applicable_to='membership'`; rejected on PT packages | |

**User's choice:** Both — NULL (D-08)

| Option | Description | Selected |
|--------|-------------|----------|
| 1/client, no global cap, no expiry | per_client_limit=1, max_uses=NULL, validity=NULL, active; mirrors FIT10 | ✓ |
| No limits at all | per_client_limit=NULL, max_uses=NULL; reusable, less realistic | |
| 1/client + validity window | per_client_limit=1 + valid_until; realistic but expiry-in-migration is fragile | |

**User's choice:** Safe default — 1/client, no cap, no expiry, active (D-09)
**Notes:** User raised wanting to manage promo-code params via an interface → redirected as scope creep (admin CRUD), captured as a deferred idea; the seeded FIT15 params still needed a concrete value, confirmed as the safe default.

## Claude's Discretion

- Migration revision numbers (next after 0048), schema field ordering, test placement — follow existing conventions.

## Deferred Ideas

- **Promo-code admin CRUD** — create/edit/parameterize codes from a UI; requires staff side (frozen `apps/admin-web`); future milestone, already on v2.1 backlog.
- **Autopay / card-on-file** — would give `auto_renew` a real value; Group-B net-new domain, deferred.
