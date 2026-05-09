# Phase 26: Memberships — Renewal (backend) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 26-memberships-renewal-backend
**Mode:** `--auto` (recommended defaults selected by Claude — no interactive prompts)
**Areas discussed:** Migration scope & numbering · `previous_membership_id` semantics · Source status acceptance + plan resolution · Date computation · Service-layer flow · Resolver tiebreak · Endpoint signature + RBAC · Schema / response shape · State-machine + audit registry · Test taxonomy

---

## Migration scope & numbering

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone `0009_renewal.py` | Phase 26 ships its own migration; chain `0007 → 0008 → 0009 → 0010` | ✓ |
| Combined `0008_freeze_and_renewal.py` | Phase 25 + 26 share one migration | |
| Defer column to Phase 28 | Add `previous_membership_id` only when admin-web wires renewal | |

**Auto-selected:** Standalone `0009_renewal.py`.
**Rationale (D-26-01):** mirrors Phase 25 D-25-01 — independent shippability per phase boundary; bundling would couple Phase 25/26 hotfix paths. Original milestone roadmap "shared `0007`" wording was already superseded by Phase 24 D-24-01 + Phase 25 D-25-01.

---

## `previous_membership_id` semantics

| Option | Description | Selected |
|--------|-------------|----------|
| UUID NULL FK self-reference, ON DELETE SET NULL, immutable post-creation | Audit-chain integrity preserved if source ever hard-deleted | ✓ |
| ON DELETE CASCADE | Cascading would lose renewal row on source hard-delete | |
| Mutable (allow PATCH to fix mistakes) | Adds attack/audit-leak surface; not requested | |

**Auto-selected:** Option 1 (immutable, ON DELETE SET NULL, non-partial index).
**Rationale (D-26-04..D-26-06):** preserves audit chain even if source hard-deleted (theoretically blocked by FK RESTRICT, but defence-in-depth); immutability matches snapshot-pricing semantics.

---

## Source status acceptance + plan resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Accept active/frozen/expired; reject cancelled with `cannot_renew_cancelled` 409 | REQUIREMENTS literal MEM-REN-02 | ✓ |
| Accept everything including cancelled (treat as reactivation) | Bypasses cancellation intent; not aligned with REQUIREMENTS | |
| Accept only active (treat frozen/expired as out-of-scope) | Loses common UX flows (post-expiry renewal, frozen pre-buy) | |

**Auto-selected:** Option 1.
**Plan resolution sub-decision (D-26-08):** new `repository.get_plan_for_renewal` helper differentiates hard-deleted (404 `plan_not_found`) from soft-deleted (409 `plan_archived`); inactive plans (`active=False`) are still renewable (only NEW sales blocked).
**New exception classes:** `CannotRenewCancelledError` + `PlanArchivedError` (D-26-09).

---

## Date computation

| Option | Description | Selected |
|--------|-------------|----------|
| Strategy by source status: active/frozen → `source.end_date + 1`; expired → `today` (Europe/Moscow) | REQUIREMENTS MEM-REN-04 + UX-anti-pattern guard for retroactive expired-source dates | ✓ |
| Always `source.end_date + 1` regardless of status | Renewal of long-expired source would create instantly-expired row | |
| Always `today` regardless of status | Loses continuity for active-source renewal stacking | |

**Auto-selected:** Option 1.
**Strategy literals frozen (D-26-13):** `RENEWAL_STRATEGY_FROM_SOURCE_END_DATE` / `RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE` in `constants.py`; written into audit payload via `start_date_strategy` field.

---

## Service-layer flow (renew_membership)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Phase 25 freeze pattern: load → guard → flush → emit → refresh → commit | Standardised across module | ✓ |
| Reuse `_assert_can_transition` central guard | Renewal isn't a transition on source row — wrong abstraction | |
| In-router orchestration (skip dedicated service function) | Violates SVC001 commit-gate + module pattern | |

**Auto-selected:** Option 1.
**Audit payload (D-26-15):** `{actor_user_id, resource_type=membership, resource_id=NEW.id, client_id, source_membership_id, source_plan_id, current_price_kopecks, start_date_strategy}`. `current_price_kopecks` reads from CURRENT plan (not source snapshot) — captures the "client pays new price if plan got more expensive" lock from PROJECT.md.

---

## Resolver tiebreak (MEM-REN-03)

| Option | Description | Selected |
|--------|-------------|----------|
| `ORDER BY start_date ASC, created_at DESC` | "Currently-running" wins; renewal naturally takes over after source expiry flip | ✓ |
| Keep `ORDER BY end_date DESC, created_at DESC` (Phase 17 D-17) | Renewal would shadow source while source still valid | |
| Add explicit `previous_membership_id IS NULL` priority | Couples resolver to renewal-specific column; brittle for manual stacking | |

**Auto-selected:** Option 1.
**Rationale (D-26-17):** operator/client expect check-in to use the running membership until expiry. After source `end_date` passes → ARQ flips `active → expired` → no longer matches `status='active'` filter → renewal naturally wins. Backwards-compat for non-renewal Phase 17 D-01 manual-stacking: if `start_date`s differ, lower-start wins (matches "running" intuition); if identical, `created_at DESC` tiebreaks. Composite index `ix_memberships_client_id_status_end_date` still covers the WHERE clause; ORDER BY sort happens in-memory on ≤2-row sets (acceptable).

---

## Endpoint signature + RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| `POST /memberships/{id}/renew`, empty body, CSRF, `(CREATE, MEMBERSHIPS)` reception+owner, 201 Created | REQUIREMENTS MEM-REN-EP-01 literal + Phase 25 freeze precedent | ✓ |
| Owner-only | REQUIREMENTS explicit reception+owner | |
| Body with optional override (e.g. `start_date`) | Server-compute lock; operator override would erode auditable behaviour | |

**Auto-selected:** Option 1.
**Status code lock:** `201 Created` (NEW resource), distinct from freeze/unfreeze `200 OK` (state mutation on existing row).

---

## Schema / response shape

| Option | Description | Selected |
|--------|-------------|----------|
| `MembershipResponse` adds `previous_membership_id: UUID \| None = None` (auto-camelCased) | Backward-compat default; renewal forensics surface to admin-web in Phase 28 | ✓ |
| Separate `RenewalResponse` schema | Adds duplication; no field divergence justifies it | |
| Defer field to Phase 28 | Backend-FE drift; FE would need to re-derive from chain query | |

**Auto-selected:** Option 1.
**No new request schemas** — empty body. `MembershipListQuery` not extended (no `?previous_membership_id=` filter in v1.3).

---

## State-machine + audit registry

| Option | Description | Selected |
|--------|-------------|----------|
| No change to `MEMBERSHIP_STATUS_TRANSITIONS`; `membership_renewed` audit event already pre-registered Phase 24 | Renewal is INSERT not transition; Phase 24 INFRA-15 covered registration | ✓ |
| Add a `(active|frozen|expired) → renewing` transient status | Adds complexity for no observable benefit | |

**Auto-selected:** Option 1.
**Docstring drift closure (D-26-26):** `audit.py` lines 61-62 placeholder payload schema gets updated to match actual Phase 26 payload at callsite addition.

---

## Test taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| 7 integration tests (active / price-change / archived-plan / expired-source / endpoint RBAC / resolver tiebreak / from-frozen) + 1 unit test (constants frozen) | Full REQUIREMENTS TEST-01..04 coverage + resolver regression guard + cross-flow happy-path | ✓ |
| Minimal (4 tests, REQUIREMENTS-literal) | Misses resolver regression risk + frozen-source happy-path | |

**Auto-selected:** Option 1.
**Cross-flow stance:** basic `renewal-from-frozen` happy-path covered in Phase 26 (smoke); deeper sweeps (unfreeze-then-renewal-takes-over chains) deferred to Phase 29 milestone verification.

---

## Claude's Discretion

The following are explicitly left to plan-phase / executor (recorded in CONTEXT.md `### Claude's Discretion (planner picks)`):

- Exact filenames for unit/integration tests (proposals only).
- `get_plan_for_renewal` placement (recommend `repository.py`; alt: `repository_renewal.py`).
- Partial vs non-partial index on `previous_membership_id` (recommend non-partial).
- `RENEWAL_STRATEGY_*` constants placement (recommend `constants.py`).
- Whether to fold `renewal-from-frozen` smoke test into Phase 26 vs defer all cross-flows to Phase 29 (recommend fold smoke; deeper sweeps stay in Phase 29).
- Whether plan agent updates `audit.py` docstring at callsite addition (recommend yes).
- Whether to regenerate `openapi.json` per-commit in Phase 26 vs defer to Phase 28 cumulative refresh (depends on CI gate cadence — plan agent verifies via `gh workflow view ci.yml`).

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` block; key items:

- Renewal chain forensic API (recursive `GET /memberships/{id}/chain`).
- Auto-renew (cron-driven) — needs payments module + opt-in UX.
- Renewal preview / quote endpoint — likely client-side from existing data; backlog if backend computation needed.
- Renewal payment capture (`paid_at` / amount field on renewal) — billing module candidate.
- Notifications on renewal success — backlog if owner requests.
- Renewal across plan change — distinct intent ⇒ NEW sale, not renewal.
- Partial index on `previous_membership_id` — production-scale optimisation.
- Renewal of cancelled source override (admin "Reactivate" flow) — separate dedicated endpoint, not renewal workaround.
- `?previous_membership_id=` list filter — admin detail-page only, no v1.3 use-case.
