---
phase: 75-backend-field-additions
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - apps/backend/alembic/versions/0050_clients_notif_prefs.py
  - apps/backend/alembic/versions/0051_seed_fit15_promo.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/clients/models.py
  - apps/backend/tests/integration/client_portal/test_fit15_seed.py
  - apps/backend/tests/integration/client_portal/test_notif_prefs_route.py
  - apps/backend/tests/modules/client_portal/test_notif_prefs_service.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 75: Code Review Report

**Reviewed:** 2026-06-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 75 adds three backend field changes: a nullable `notif_prefs` JSONB column on
`clients` (NOTIF-01), the seeded `FIT15` product promo code (PROMO-01), and exposure
of the caller's own `price_kopecks` + `auto_renew` on `GET /client/membership`
(PMEM-01). The diff is small (61 lines across the three module files) plus two
migrations and three test files.

The security-critical concerns were checked and held up:

- **SQL injection / parameterization:** All raw `text()` reads and writes use `:name`
  bind params. The `update_client_profile` `SET` clause is assembled from fixed string
  literals only; the JSONB value is bound as a parameter and cast with `CAST(:notif_prefs
  AS jsonb)` (correctly avoiding the `::jsonb` syntax that collides with SQLAlchemy
  param substitution). No user-controlled SQL fragments.
- **IDOR / cross-client exposure:** `fetch_client_membership` is scoped
  `WHERE client_id = :client_id`, so the newly-exposed `price_kopecks` is always the
  caller's own snapshot — never another client's economics (D-75-03 holds). `fetch_client_me`
  keeps the mandatory `:client_id` + `deleted_at IS NULL` guard with 404-collapse.
- **FIT15 seed idempotency:** `ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO
  NOTHING` correctly infers the partial-unique index `uq_promo_codes_code_alive`
  (defined on `upper(code) WHERE deleted_at IS NULL` in 0046). Re-running `upgrade()`
  is a verified no-op. The discount math (`discount_value=1500` → 15%) is consistent
  with `promo_codes.service.validate_promo_code`.
- **JSONB round-trip:** Write path serializes via `json.dumps(model_dump())`; read path
  relies on asyncpg decoding JSONB to a `dict` for the raw `text()` read. The
  PATCH→GET round-trip integration test exercises this end-to-end.

No blockers found. Four warnings (latent robustness/correctness fragility) and three
info items follow. One warning (WR-02) is a pre-existing concern that Phase 75 did not
introduce but now sits adjacent to changed code.

## Warnings

### WR-01: Stored `notif_prefs` with extra or missing keys crashes `GET /client/me` with a 500

**File:** `apps/backend/app/modules/client_portal/service.py:149`
**Issue:** `NotifPrefs` inherits `BackendSchemaBase` which sets `extra="forbid"` and
declares all four fields as required. On the read path:

```python
notif = NotifPrefs(**raw_prefs) if raw_prefs is not None else NotifPrefs(**_NOTIF_DEFAULTS)
```

If the persisted JSONB ever contains an unknown key, or is missing one of the four keys
(e.g. a future schema migration adds a fifth flag, a manual DB edit, a partial write
from an older code version, or data restored from a backup), `NotifPrefs(**raw_prefs)`
raises a `pydantic.ValidationError` that is NOT an `AppError` subclass. It will not be
caught by `_app_error_handler` and surfaces as an unhandled 500 on a read endpoint —
turning a data-shape drift into a hard read-path outage for that client. The column is
`nullable` with no DB `CHECK` or `DEFAULT`, so the schema is the only guard, and it is
applied at read time rather than write time.

**Fix:** Validate defensively on read so drift degrades to defaults instead of a 500.
For example:

```python
raw_prefs = r.get("notif_prefs")
try:
    notif = NotifPrefs(**raw_prefs) if raw_prefs is not None else NotifPrefs(**_NOTIF_DEFAULTS)
except ValidationError:
    # tolerate legacy/partial JSONB shapes — fall back to server defaults (D-06)
    merged = {**_NOTIF_DEFAULTS, **(raw_prefs or {})}
    notif = NotifPrefs(**{k: merged[k] for k in _NOTIF_DEFAULTS})
```

Alternatively, add a DB `CHECK`/typed shape so the write path is the enforcement point.

### WR-02: Receipt-lookup join matches membership by `(plan_id, client_id)` heuristic, can return a receipt for the wrong purchase

**File:** `apps/backend/app/modules/client_portal/service.py:824-840`
**Issue:** In `get_client_payment_status`, the succeeded-branch receipt subquery resolves
the membership/PT row for the receipt by joining `online_payments` to `memberships`/`pt_packages`
on `plan_id` + `client_id`, not by a direct payment→subject link:

```sql
SELECT m.id FROM memberships m
INNER JOIN online_payments op ON op.membership_plan_id = m.plan_id
WHERE op.id = :op_id AND m.client_id = op.client_id
ORDER BY m.created_at DESC LIMIT 1
```

A client who buys the same plan twice has two memberships with identical `plan_id`.
`ORDER BY m.created_at DESC LIMIT 1` always returns the most recent one, so polling the
status of the *older* payment can surface the *newer* purchase's receipt URL (or vice
versa). The PT branch has the same shape with no ordering at all (`IN (...)` over all
matching packages), so it can match across repeat purchases of the same package.

This is IDOR-safe (still scoped to the caller's own rows), so it is not a cross-client
leak — but it can display the wrong receipt for the wrong payment on a real-money path.
Note: this code predates Phase 75 (the diff only removed an unused `# noqa` here), so it
is in-scope-adjacent rather than newly introduced. Flagged because Phase 75 touched this
function and the field exposure makes receipt correctness more user-visible.

**Fix:** Link the receipt to the specific payment that this `online_payment` produced
(e.g. via the `online_payments` → `payments` activation link / `subject_id` recorded at
succeeded-webhook time) rather than re-deriving the subject by `plan_id`. If a direct
link is unavailable, document the limitation and constrain by the payment's own
`received_at`/created window so repeat purchases cannot cross-match.

### WR-03: `NotifPrefs` reuses an inbound request base (`BackendSchemaBase`) as a nested response field

**File:** `apps/backend/app/modules/client_portal/schemas.py:283-339`
**Issue:** `NotifPrefs(BackendSchemaBase)` is embedded as a field on both
`ClientProfileUpdateRequest` (request, fine) and `ClientMeResponse` (response). Every
other response payload in this module subclasses `ResponseData`. `BackendSchemaBase`
carries `extra="forbid"`, which is request-validation semantics; mixing a `forbid` base
into a response model is what makes WR-01 reachable (a tolerant `ResponseData`-style base
would have silently dropped unknown keys instead of 500-ing). The two roles also have
different intended configs (`ResponseData` is the documented response base). Functionally
the wire shape is correct today because all four keys are single words (camelCase no-op),
but the type is doing double duty across the request/response boundary against the
module's own convention.

**Fix:** Split into two models — keep `NotifPrefs(BackendSchemaBase)` for the inbound
PATCH body, and add a `NotifPrefsOut(ResponseData)` (or relax the response nesting) for
`ClientMeResponse`. This also resolves WR-01 by making the read-side tolerant.

### WR-04: Idempotency test cannot distinguish "ON CONFLICT worked" from "no prior row existed"

**File:** `apps/backend/tests/integration/client_portal/test_fit15_seed.py:179-204`
**Issue:** `test_fit15_seed_insert_is_idempotent` re-runs the 0051 INSERT and asserts
exactly one alive FIT15 row. But if migration 0051 had NOT actually seeded the row on the
test DB (e.g. migrations skipped, or a future env where the row is absent), the re-INSERT
would simply insert one row and the count would still be `1` — the test passes either way.
The test therefore does not prove the `ON CONFLICT ... DO NOTHING` conflict-target
actually matched the partial index; a silently broken conflict clause (e.g. a future edit
to the inference expression) would still let a duplicate slip through only when two rows
collide, which this single re-run never forces against a guaranteed-present baseline row.

**Fix:** Assert the baseline first (count == 1 before the re-INSERT, proving the migration
seeded it), then re-INSERT, then assert count is still exactly 1. That makes the
ON-CONFLICT no-op the only thing keeping the count from becoming 2.

## Info

### IN-01: Email is validated but not normalized before write; uniqueness is on `lower(email)`

**File:** `apps/backend/app/modules/client_portal/service.py:196-197`, `apps/backend/app/modules/client_portal/repository.py:600-602`
**Issue:** `update_client_profile` validates email format with `_EMAIL_RE` but writes the
raw-case string. The partial-unique index is on `lower(email)` (clients/models.py:153-158),
so casing is correctly collapsed for uniqueness, but the stored display value preserves
whatever case the client sent. Not a correctness bug; just an inconsistency (mixed-case
stored emails) on a field used for 54-ФЗ receipt destinations.
**Fix:** Consider `bind["email"] = payload.email.strip().lower()` for consistent storage,
or document that display-case is intentionally preserved.

### IN-02: `_EMAIL_RE` is a permissive hand-rolled regex while the project ships `email-validator`

**File:** `apps/backend/app/modules/client_portal/service.py:91`
**Issue:** `_EMAIL_RE = r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$"` accepts many technically-invalid
addresses (e.g. consecutive dots, leading/trailing dots in the local part) and rejects
some valid ones. `email-validator>=2.0` is already a declared dependency (pyproject.toml:12).
On a real-money receipt-email gate, a stricter validator reduces bounced fiscal receipts.
**Fix:** Reuse `email-validator` (or the same validation already applied elsewhere in the
clients module) for the receipt-email gate rather than a bespoke regex.

### IN-03: `_NOTIF_DEFAULTS` key set is duplicated implicitly with `NotifPrefs` field list

**File:** `apps/backend/app/modules/client_portal/service.py:123-128`, `apps/backend/app/modules/client_portal/schemas.py:295-298`
**Issue:** The four default keys live in `_NOTIF_DEFAULTS` (service) and the four field
names live in `NotifPrefs` (schemas). Adding or renaming a flag requires editing both in
lockstep; a mismatch means `NotifPrefs(**_NOTIF_DEFAULTS)` raises at runtime (the
defaults branch is only hit when the column is NULL, so a mismatch could ship unnoticed
if tests only cover the populated path). The defaults test covers it today, so this is
informational.
**Fix:** Derive defaults from the model (e.g. give `NotifPrefs` field defaults used only
for the server-default branch, or assert `set(_NOTIF_DEFAULTS) == set(NotifPrefs.model_fields)`
in a unit test) so the two cannot drift.

---

_Reviewed: 2026-06-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
