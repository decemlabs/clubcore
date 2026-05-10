# Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 28-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 28-openapi-drift-gate-refresh-admin-web-wiring
**Mode:** `--auto` (Claude picked the recommended option for every gray area without prompting the user)
**Areas discussed:** drift-gate cycle, domain type extension, service contract surface, http adapter
shape, mock parity, hooks (optimistic vs not), routes, renew confirm dialog, freeze button states,
status badge visual, list filter + within selector, i18n, RBAC, plan order

---

## Drift-gate refresh cycle

| Option | Description | Selected |
|--------|-------------|----------|
| Single regenerate-then-commit cycle (mirrors v1.2 Phase 21) | Run export_openapi → codegen → commit both files in ONE commit at start of phase; subsequent FE work consumes regenerated types | ✓ |
| Iterative regen-as-you-go | Regenerate after each FE plan if backend touches happen | |
| Skip drift-gate, only do FE wiring | Trust existing schema.d.ts | |

**Auto-selected:** Single cycle. Locked by ROADMAP "exactly one cycle" success criterion #1.
**Notes:** `apps/backend/scripts/export_openapi.py` already byte-stable; codegen via openapi-typescript.

---

## Domain type extension

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `MembershipStatus` union + add freeze fields to `Membership` in entities | New value `'frozen'`, new fields freezeDays*/currentFreezePeriod/previousMembershipId | ✓ |
| Generate domain types from schema.d.ts directly | Skip the entities layer, consume `components['schemas']['MembershipResponse']` raw | |

**Auto-selected:** Extend entities (preserves Brand types + camelCase domain layer).

---

## Service contract surface

| Option | Description | Selected |
|--------|-------------|----------|
| Add `freeze`/`unfreeze`/`renew` methods to `MembershipsService` | Mirrors backend 1:1; both impls implement | ✓ |
| Generic `transition(id, action)` method | Single method dispatched server-side | |

**Auto-selected:** Three explicit methods (typed signatures + RBAC clarity).

---

## HTTP adapter

| Option | Description | Selected |
|--------|-------------|----------|
| Use generated `paths` from schema.d.ts via `request<P,M>` | Type-safe url + method; consistent with existing memberships.ts http file | ✓ |
| Hand-rolled fetch wrappers | Duplicates types | |

**Auto-selected:** `request('post', '/api/v1/memberships/{membership_id}/freeze', ...)` style.

---

## Mock service parity

| Option | Description | Selected |
|--------|-------------|----------|
| Implement freeze/unfreeze/renew with backend-equivalent semantics + DomainError codes | In-memory state mutation; identical error codes | ✓ |
| Stub mocks (no-op success) | Simpler, but breaks `VITE_API_MODE=mock` workflows | |
| Skip mock parity (http-only this phase) | Forces dev to run docker | |

**Auto-selected:** Full parity. Locked by ROADMAP success criteria #2/#3/#5 ("mock service синхронизирован").

---

## Hooks — optimistic vs not

| Option | Description | Selected |
|--------|-------------|----------|
| freeze/unfreeze optimistic; renew NOT optimistic | Renew creates a new resource; UUID known only after 201 | ✓ |
| All three optimistic | Would require placeholder navigation | |
| None optimistic | Loses snappy UX | |

**Auto-selected:** Mixed — matches resource semantics.

---

## Routes — detail page convention

| Option | Description | Selected |
|--------|-------------|----------|
| Flat route `_protected/memberships_.$membershipId.tsx` mirroring `clients_.$clientId.tsx` | Convention already established in repo | ✓ |
| Nested under `_protected/memberships/$membershipId.tsx` | Different convention | |
| Drawer/modal on list page | No route change | |

**Auto-selected:** Flat route — convention consistency.

---

## Renew confirm dialog

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot-only dialog (price + computed dates from current membership) — no extra plan fetch | Snapshot fields already on `Membership` | ✓ |
| Fetch fresh plan price before showing dialog | Extra round-trip; plan price could differ from snapshot | |
| Inline form with override fields | Out of scope | |

**Auto-selected:** Snapshot-only (server is source of truth on confirm).

---

## Freeze button states

| Option | Description | Selected |
|--------|-------------|----------|
| Disabled when `freezeDaysRemaining === 0` with tooltip key `memberships.freeze.no_days_remaining` | Locked by FE-10 description | ✓ |

**Auto-selected:** Locked by requirements — no real choice.

---

## Frozen status badge visual

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn semantic warning/amber token (planner picks exact token) | Distinct from active/expired/cancelled, no raw palette | ✓ |
| Same as expired with text suffix | Visually conflicting | |

**Auto-selected:** Semantic warning token (planner finalizes).

---

## List status filter + within selector

| Option | Description | Selected |
|--------|-------------|----------|
| 4th status filter pill "Заморожен" + within selector visible only when expiring toggle on; defaults `within=7`, choices `1/3/7/14/30` | Search params via TanStack Router `validateSearch` (Zod) | ✓ |

**Auto-selected:** Standard list filter pattern; preserves FE-08 D-2 default.

---

## i18n

| Option | Description | Selected |
|--------|-------------|----------|
| Russian-only keys under `memberships.*` in `ru.ts`; planner locks exact wording | Carry-forward Russian-only v1 stance | ✓ |
| English fallbacks | No multi-language support in v1 | |

**Auto-selected:** Russian-only.

---

## RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `(CREATE, MEMBERSHIPS)` for freeze/unfreeze/renew (both roles); cancel-during-freeze stays owner-only | Locked by FE-10/FE-12 + carry-forward FE-08 | ✓ |

**Auto-selected:** Locked by requirements.

---

## Plan order

| Option | Description | Selected |
|--------|-------------|----------|
| Drift-gate first → domain/contracts/i18n stubs → mock service → http adapter → hooks → detail UI → list/badge → within selector | Drift-gate is upstream of every other plan; sequencing prevents re-opening the cycle | ✓ |

**Auto-selected:** 8-step recommended order; planner may merge but order is load-bearing.

---

## Claude's Discretion

The following decisions were intentionally left for the planner / executor to finalize without
re-asking the user:

- Exact shadcn semantic token for the frozen badge (must be semantic; raw palette banned).
- Whether `useFreezeMembership` and `useUnfreezeMembership` share an internal cache-patch helper.
- Detail page section order (header / freeze / renewal / metadata).
- Within selector rendering — `<Select>` vs segmented control vs inline chips.
- Mock seed value for `freezeDaysLimitSnapshot` (any sensible default 14–30).
- Whether `_membershipsAdapter.ts` exports `responseToFreezePeriod` or inlines the mapping.
- Final Russian wording for new i18n keys (planner locks before merge).

## Deferred Ideas

(Carried into 28-CONTEXT.md `<deferred>` section — listed here for the audit trail.)

- Multi-period freeze history viewer.
- `MembershipsBlock` pagination (still WR-06).
- Freeze period edit / backdating UX.
- Renewal preview (server-side dry-run endpoint).
- Bulk freeze/unfreeze.
- Export of frozen-membership list to CSV.
- Plan-change-on-renewal (cross-plan renew).
