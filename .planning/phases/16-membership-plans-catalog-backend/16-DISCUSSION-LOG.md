# Phase 16: Membership Plans Catalog (backend) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 16-Membership Plans Catalog (backend)
**Areas discussed:** Name validation + 409 conflict UX, duration_days immutability + PATCH semantics, List endpoint shape + audit payload

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Name validation + 409 conflict UX | Trim/min-length, case-insensitive uniqueness, IntegrityError→409 plan_name_exists on POST/PATCH | ✓ |
| duration_days immutability mechanism | Pydantic extra='forbid' (clean 422) vs explicit field+validator; PATCH explicit-null policy | ✓ |
| DELETE 409 plan_in_use scope (Phase 16 vs 17) | memberships table arrives in Phase 17. Ship soft-delete only here vs full FK-RESTRICT check deferred | (locked default — D-15..D-17) |
| List endpoint + audit payload shape | Sort default, ?active filter, name search, ?includeArchived; audit payload shape | ✓ |

**Notes:** User selected 3 of 4 areas; `DELETE 409 plan_in_use scope` was locked with the recommended default — soft-delete-only in Phase 16, FK + IntegrityError translation in Phase 17 (matches table dependency order). DELETE vs PATCH-active interplay also locked defaultly: DELETE→`_archived`, PATCH→`_updated`. Phase 15's deferred `auth/service.py` audit-row-loss was confirmed as Phase 23 routing (not absorbed into 16).

---

## Plan name normalization — whitespace and casing

| Option | Description | Selected |
|--------|-------------|----------|
| Trim + store as-entered | Strip leading/trailing whitespace; preserve original casing. DB partial-unique on lower(name) catches case-variant duplicates. Min length: 1 (after trim). Mirrors clients pattern. | ✓ |
| Trim + collapse internal whitespace + store as-entered | Also collapse runs of internal spaces to single space. Catches "Plan  Premium" vs "Plan Premium". Min length: 1. | |
| Trim + lowercase + store lowercased | Force lowercase on storage. UI loses display casing. Min length: 1. Cleaner uniqueness but worse UX. | |
| Trim + min-length 2 + collapse whitespace + as-entered | Reject single-char names, collapse internal spaces, preserve case. Strictest UX guard. | |

**User's choice:** Recommended (trim + as-entered).
**Notes:** Aligned with clients pattern — server-side normalization stays minimal; the DB partial-unique on `lower(name)` carries the case-insensitivity guarantee. Operators see exactly what they typed.

---

## 409 conflict translation

| Option | Description | Selected |
|--------|-------------|----------|
| Catch IntegrityError on POST + PATCH → 409 plan_name_exists | Direct mirror of clients D-11. No pre-flight SELECT. Service does insert/update → flush → catch IntegrityError on uq_membership_plans_name_alive → raise PlanNameExistsError(409). | ✓ |
| Pre-flight SELECT + IntegrityError as fallback | Service selects first; raises 409 cleanly without DB error. More code, no real win. | |
| PATCH does NOT validate name uniqueness | Only POST raises 409. Bad UX. | |

**User's choice:** Recommended (IntegrityError translation on both POST and PATCH).
**Notes:** Cements the "no pre-flight SELECT for uniqueness" pattern across business modules. New helper `_is_plan_name_conflict(exc)` and new `PlanNameExistsError(ConflictError)` in `core/exceptions.py`.

---

## duration_days immutability mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Field absent from MembershipPlanUpdateRequest → Pydantic 422 via extra='forbid' | DTO declares only name/price_kopecks/active. Any payload with durationDays gets Pydantic's stock 422 'extra fields not permitted'. Cleanest; no custom code. | ✓ |
| Explicit field + custom validator → 422 duration_immutable | Better UX (specific error code) but adds code; clients pattern doesn't do this for any field today. | |
| Silently ignore durationDays in PATCH | Strip server-side. Bad — hides bugs. | |

**User's choice:** Recommended (extra='forbid' rejection).
**Notes:** Inherits the Phase 15 `BackendSchemaBase` config; no per-module override needed. Keeps the schema layer minimal and consistent.

---

## PATCH explicit-null policy

| Option | Description | Selected |
|--------|-------------|----------|
| Reject explicit null on all PATCH fields | Mirror clients D-01: model_validator(mode='before') rejects {"name": null}. Caller must omit the key. | ✓ |
| Don't ship the explicit-null guard for plans | Plans only have 3 PATCH-able fields, all non-nullable in DB — Pydantic type validation catches it. Guard is redundant. | |

**User's choice:** Recommended (reject explicit null, mirroring clients D-01).
**Notes:** Consistency-driven. Even though all 3 PATCH fields are non-nullable, the guard's error message is more developer-friendly than Pydantic's per-field type error.

---

## POST bounds — sane upper limits

| Option | Description | Selected |
|--------|-------------|----------|
| duration_days: 1–3650 (10y); price_kopecks: 0–10¹¹ (1B ₽) | DB CHECK already enforces >0 and >=0. Pydantic adds upper bounds at the schema layer for defence-in-depth. | ✓ |
| Only DB CHECK constraints; no upper bound at schema | Pydantic enforces type only; client can submit duration_days=999999999 and get 201. | |
| Tighter caps: duration_days: 1–1825 (5y); price_kopecks: 100–100·10⁶ (1–1M ₽) | Prevent free plans + absurd durations. Loses flexibility for promo/comp memberships. | |

**User's choice:** Recommended (10y / 1B ₽ caps).
**Notes:** Free plans (price=0) remain allowed — comp/promo flexibility preserved. Upper bounds catch typos before they reach the DB.

---

## Default list behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Default: alive + sort=created_at_desc; ?active=true|false filter; ?sort=name_asc option | Mirrors clients pagination shape. Default excludes soft-deleted; ?active is optional (omit = both); ?sort enum {created_at_desc, name_asc}. No archived in default view. | ✓ |
| Default: alive + active=true only; need ?active=false to see inactive | Hide deactivated plans by default. Adds complexity for owner catalog page. | |
| Default: alive only, no sort guarantee; ?sort optional | Postgres default ordering. Bad UX — paginated list with shifting order. | |

**User's choice:** Recommended (alive + created_at_desc default; optional active+sort).
**Notes:** `?includeArchived` deferred — not needed in Phase 16; reconsider if owner archive view ships later.

---

## Name ILIKE search — ship in Phase 16 or defer

| Option | Description | Selected |
|--------|-------------|----------|
| Defer search; just paginate + sort | Plan catalog is small (≤5–20 plans for one zal). Pagination at 20/page covers it. No ?q= param. | ✓ |
| Ship ?q= ILIKE search using core/sql.py:escape_like_pattern | ILIKE on lower(name) with the escape helper. ~20 LOC + index. | |
| Ship a btree index on lower(name) — no ?q yet | Migration adds index now; Phase 22 turn-on is migration-free. | |

**User's choice:** Recommended (defer).
**Notes:** core/sql.py:escape_like_pattern stays unused for this module. The partial-unique on lower(name) already serves as the lookup index for case-insensitive equality.

---

## membership_plan_updated audit payload

| Option | Description | Selected |
|--------|-------------|----------|
| {plan_id, changed_fields} — mirror clients D-08 | Sorted list of changed field names only. Forensics: "who flipped active off?" answered by changed_fields=['active']. | ✓ |
| {plan_id, changed_fields, previous_price_kopecks?} when price changed | Add before-value for price (only). Useful for price-history forensics. | |
| Full diff: {plan_id, before:{...}, after:{...}} | Complete state delta. Heavier rows. | |

**User's choice:** Recommended (changed_fields only).
**Notes:** Cross-module consistency wins. If price-history matters, add a dedicated `membership_plan_price_history` table later — don't bloat audit payloads.

---

## Claude's Discretion

- **CD-01:** Exact wording of `PlanNameExistsError` message strings, FastAPI route summaries/descriptions, and OpenAPI examples (consistency with clients module).
- **CD-02:** Test file granularity within `tests/integration/memberships/` (single `test_plans_crud.py` vs split per-operation).
- **CD-03:** Migration file ordering inside `0004_membership_plans.py.upgrade()` — table → CHECKs → partial-unique index via `op.execute`.
- **CD-04:** `MembershipPlanSort` location (module-local schemas vs lifted to core); default to module-local mirroring `ClientSort`.
- **CD-05:** Whether to add a dedicated `tests/unit/memberships/test_audit_payloads.py` or fold the assertions into `test_audit_writes.py`.

## Deferred Ideas

- **`409 plan_in_use` IntegrityError translation** → Phase 17 (alongside the `memberships` FK migration).
- **`?includeArchived=true` owner archive view** → speculative; reconsider in Phase 22+.
- **Name ILIKE search (`?q=`)** → Phase 22 if owner UI surfaces it.
- **Membership plan price-history table** → out of scope for v1.2.
- **DELETE with cascade-cancel of dependent active memberships** → not supported; owner manually cancels first (Phase 17 returns 409 plan_in_use).
- **Plan reactivation endpoint after soft-delete** → no restore path; reconsider in v1.3+.
- **Phase 15 deferred `auth/service.py` write-path bug** → confirmed Phase 23 routing.
- **Per-event audit payload schema validation registry** → revisit when audit log read-side API ships in v1.3+.
