# Phase 17: Membership Instances + Resolver (backend) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 17-membership-instances-resolver-backend
**Areas discussed:** Sale validation policy, DELETE plan + plan_in_use scope, Memberships list & cancel contract
**Areas skipped (defaulted):** Resolver edge cases

---

## Sale validation policy

### Q1: Client already has an active membership — what should POST /memberships do?

| Option | Description | Selected |
|--------|-------------|----------|
| Allow stacking | Insert succeeds; resolver tiebreaks (latest end_date, then created_at DESC) per MEM-04. Owner can manually cancel an old one. Simplest, no extra failure mode. | ✓ |
| Block with 409 'already_active' | Service does pre-flight resolver call before insert; if not None → 409. Cleaner ops surface but adds a SELECT + race window, conflicts with MEM-04's tiebreak premise. | |
| Allow with start_date = previous.end_date+1 | Auto-stack: new membership starts day after previous ends. Adds complexity and breaks activation_policy='purchase_date' which is locked. | |

**User's choice:** Allow stacking (Recommended)
**Notes:** Aligns with locked MEM-04 multi-active premise. → CONTEXT.md D-01.

### Q2: Plan.active=false sale — backend behavior?

| Option | Description | Selected |
|--------|-------------|----------|
| 409 'plan_inactive' | Service fetches plan, checks plan.active. If False → PlanInactiveError. Defence-in-depth against UI bypass. | ✓ |
| Allow sale | active=false is 'hidden from sell screen' marker, not enforcement. Snapshot semantics make this safe. Trusts UI. | |
| Allow only by owner, 409 for reception | Hybrid role-branching in service. Violates 'service does not re-check RBAC' pattern. | |

**User's choice:** 409 'plan_inactive' (Recommended)
**Notes:** PlanInactiveError joins core/exceptions.py. → CONTEXT.md D-02.

### Q3: paidAt default + notes constraint?

| Option | Description | Selected |
|--------|-------------|----------|
| paidAt nullable; notes max 1000 | Omit paidAt → NULL (manual today, ЮKassa v1.3 fills it). Owner can pass explicit timestamp for back-dating. notes max 1000. | ✓ |
| paidAt defaults to now() if omitted; notes max 1000 | Convenience: omitting paidAt records 'paid at sale time'. Couples creation/payment, but v1.3 needs them separable. | |
| paidAt nullable; notes max 500 | Same as recommended but tighter notes ceiling. | |

**User's choice:** paidAt nullable; notes max 1000 (Recommended)
**Notes:** Keeps `created_at` (sale time) and `paid_at` (payment confirmation) separable for v1.3 ЮKassa flow. → CONTEXT.md D-03.

---

## DELETE plan + plan_in_use scope

### Q4: How to reconcile ROADMAP SC#4 'non-cancelled' wording with FK ON DELETE RESTRICT?

| Option | Description | Selected |
|--------|-------------|----------|
| FK is the gate; any membership blocks | Phase 17 adds FK + extends `_is_plan_in_use_conflict`. Cancelled/expired rows ALSO block — they are part of audit trail. Update ROADMAP SC#4 wording. Simplest, race-proof. | ✓ |
| App-layer pre-check + FK as backstop | Service SELECTs `WHERE plan_id=? AND status<>'cancelled'`. Honours ROADMAP wording but adds query + race window. | |
| FK as ON DELETE SET NULL for cancelled rows | Cancelled memberships orphaned (plan_id→NULL). Schema-level enforcement of 'non-cancelled blocks'. ON DELETE SET NULL conditional on status not a real PG feature. | |

**User's choice:** FK is the gate; any membership blocks (Recommended)
**Notes:** Cancelled rows preserved for audit trail. ROADMAP SC#4 wording reconciled by planner (D-07). → CONTEXT.md D-05/D-06/D-07/D-08.

---

## Memberships list & cancel contract

### Q5: GET /memberships defaults?

| Option | Description | Selected |
|--------|-------------|----------|
| clientId optional; default no status filter; sort=created_at_desc | Owner can call without clientId for global feed. Default returns all 3 statuses. Single ?status enum (no multi-value). | ✓ |
| clientId required; default no status filter; sort=end_date_desc | Force client-scoped query. Owner global feed YAGNI. Multi-value via comma-split. | |
| clientId optional; default status=active; sort=created_at_desc | Default to currently-active view; UI passes ?status=expired for history. Smaller default response. | |

**User's choice:** clientId optional; default no status filter; sort=created_at_desc (Recommended)
**Notes:** Sort enum members: created_at_desc (default), end_date_desc, start_date_desc. → CONTEXT.md D-09/D-10.

### Q6: Cancel reason + idempotency?

| Option | Description | Selected |
|--------|-------------|----------|
| reason optional, max 500; 2nd cancel → 409 invalid_transition | Body: {reason?: ≤500}. reason omitted → audit payload has no reason key. 2nd cancel → 409 with payload {from_status, to_status}. Matches MEM-03 + TESTS-10 verbatim. | ✓ |
| reason required, max 500; 2nd cancel → 409 | Force operator to record why every cancel happened. Conflicts with MEM-AUDIT-01 making reason optional in audit payload. | |
| reason optional, max 1000; 2nd cancel → 200 idempotent | 2nd cancel returns 200 with existing row. Contradicts locked MEM-03 + TESTS-10. | |

**User's choice:** reason optional, max 500; 2nd cancel → 409 invalid_transition (Recommended)
**Notes:** Audit payload omits the `reason` key entirely when None (not `reason: null`). → CONTEXT.md D-11/D-12/D-13/D-14/D-15.

---

## Claude's Discretion

- **CD-01:** Exact wording of error message strings, FastAPI route summaries, OpenAPI examples (consistency with PlanNameExistsError precedent).
- **CD-02:** Test file granularity within `tests/integration/memberships/` (single file vs split by endpoint).
- **CD-03:** State-machine helper location — free functions in `service.py` vs separate `_state.py`.
- **CD-04:** Migration ordering inside `0005_memberships.py.upgrade()`; DESC index via `op.create_index` vs raw `op.execute`.
- **CD-05:** `MembershipResponse.planId` only vs embedded `planNameCurrent` join.
- **CD-06:** Resolver helper public symbol on `app.modules.memberships.service` vs only the registered slot.

## Resolver edge cases (skipped — used defaults)

The user did not select this area for discussion. Captured as defaults:

- **D-16:** Resolver is a plain awaitable, NOT a FastAPI Depends (mirrors `register_user_loader` pattern; visits service calls it directly).
- **D-17:** Multi-active scenario silent tiebreak — no structlog warning, no audit. Stacking is a deliberate operator workflow per D-01.
- **D-18:** `ActiveMembership` Protocol exposes only consumer-needed columns (`id, client_id, end_date, status` per MEM-05); resolver returns the ORM row which structurally satisfies the Protocol.

If the user disagrees with any of these on plan review, /gsd-discuss-phase 17 can be re-run with `--update`.

## Deferred Ideas

See `<deferred>` block in 17-CONTEXT.md — 13 items captured (membership freeze, visit-count plans, hybrid plans, expiring-soon notifications, manual /expire endpoint, future-dated start_date, ?expand=plan, multi-value status filter, ?from/?to date-range, dedicated plan_id btree, refund flow, renewal endpoint, multi-active warning UX).
