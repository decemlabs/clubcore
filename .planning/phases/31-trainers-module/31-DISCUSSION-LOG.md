# Phase 31: Trainers Module - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 31-trainers-module
**Mode:** `/gsd-discuss-phase 31 --auto` — no interactive prompts; recommended defaults selected for every gray area.
**Areas discussed:** Migration shape, Phone validation, Hard-delete + soft-delete semantics, Reception filter + is_active, Protocol slot wiring, Audit emission, admin-web /trainers route, Plan splitting

---

## Migration shape (TRN-01 → `0011_trainers.py`)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror clients full shape (4 mixins + `created_by_user_id` FK) | Strictly copy Phase 8 — adds creator-attribution audit trail | |
| Mirror clients shape WITHOUT `created_by_user_id` | 3 mixins only; TRN-* req-set doesn't mandate creator FK; smaller attack surface | ✓ |
| Bare minimum (no SoftDeleteMixin) | Drop `deleted_at` since v1.4 has no soft-delete API for trainers | |

**Auto-selected:** Mirror clients WITHOUT `created_by_user_id`.
**Rationale:** TRN-01 verbatim doesn't list creator FK. `deleted_at` retained because partial UNIQUE on phone references it. Captured as D-31-01..D-31-04.

---

## Phone validation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `PHONE_REGEX` from clients (D-10 E.164) | Single source of truth; consistency with clients | ✓ |
| New regex in trainers schemas | Independent module-local regex | |
| Free-text, no validation | TRN-01 allows free-text but spec says "E.164 validated when present" | |

**Auto-selected:** Reuse PHONE_REGEX (D-10).
**Rationale:** TRN-01 verbatim mandates E.164 when present; reusing existing regex avoids drift. Captured as D-31-05.

---

## Hard-delete vs soft-delete semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-delete with 409 trainer_in_use on FK refs | TRN-05 verbatim; `deleted_at` column inert (only for phone-uniqueness rule) | ✓ |
| Soft-delete API + separate purge endpoint | Two-tier deletion; more code | |
| Hard-delete only when force=true flag | Owner-override pattern | |

**Auto-selected:** Hard-delete with 409 mapping (pre-emptive even before `pt_sessions` exists).
**Rationale:** TRN-05 verbatim. `deleted_at` column kept because partial UNIQUE rule references it. Captured as D-31-06..D-31-08.

---

## Reception filter + `is_active` PATCH semantics

| Option | Description | Selected |
|--------|-------------|----------|
| `?active=bool\|None` query + PATCH for state flip | Single CRUD endpoint set; PATCH covers full update + state flip | ✓ |
| Separate `POST /{id}/deactivate` + `POST /{id}/reactivate` endpoints | Mirrors freeze pattern from v1.3 | |
| `?active=true` only (default `false` hidden for owner too) | Simpler filter but blocks owner from listing inactive | |

**Auto-selected:** Optional `active` query + PATCH state flip.
**Rationale:** No invariants on state flip beyond `(EDIT, TRAINERS)`; separate endpoint would be over-engineered. Audit emission distinguishes state-flip vs general-update events. Captured as D-31-09..D-31-12.

---

## Protocol slot wiring (`register_trainer_by_id_resolver`)

| Option | Description | Selected |
|--------|-------------|----------|
| Double-wire main.py + telegram_bot.py (defensive) | TRN-06 verbatim + REG-29-03 lesson | ✓ |
| Only main.py (telegram_bot adds later) | Defer bot-side wiring to consumer phase | |
| Skip Protocol slot in v1.4 (no consumer yet) | Add when Phase 34 needs it | |

**Auto-selected:** Double-wire per TRN-06 verbatim.
**Rationale:** Pre-emptive registration per uniform 3-slot pattern; resolver returns Trainer ORM (filter `deleted_at IS NULL`, not `is_active`). Captured as D-31-13..D-31-15.

---

## Audit emission (TRN-07)

| Option | Description | Selected |
|--------|-------------|----------|
| State-flip emits dedicated event + general-update emits `trainer_updated` for other fields (2 events if combined PATCH) | Cleaner audit chain; matches payload schema shapes | ✓ |
| Always emit `trainer_updated` for any PATCH (no state-flip events) | Simplest; loses lifecycle granularity | |
| Single combined event with op-type discriminator field | Requires new payload schema not locked | |

**Auto-selected:** State-flip dedicated events + parallel `trainer_updated` for other fields.
**Rationale:** Payload schemas already locked in Phase 30 with this shape. Captured as D-31-16..D-31-18.

---

## admin-web `/trainers` route shape

| Option | Description | Selected |
|--------|-------------|----------|
| Owner-only `beforeLoad` + feature folder + RHF/Zod + AlertDialog | TRN-08 verbatim; mirrors `/membership-plans` UX | ✓ |
| Reception-accessible `/trainers` with role-conditional UI | Diverges from TRN-08; reception only needs picker (Phase 35) | |
| Inline `/settings` sub-route (no separate page) | Reduces route count but TRN-08 says dedicated route | |

**Auto-selected:** Dedicated owner-only route with full feature folder.
**Rationale:** TRN-08 verbatim mandates owner-only beforeLoad + dedicated route. Captured as D-31-19..D-31-24.

---

## Plan splitting

| Option | Description | Selected |
|--------|-------------|----------|
| 2 plans: backend + admin-web mock-mode | Compact, parallel-eligible after backend types stable | ✓ |
| 3 plans: backend + mock service + UI route | More granular; redundant overhead for this domain | |
| 1 plan: everything bundled | Loses atomic rollback granularity | |

**Auto-selected:** 2 plans (Plan 31-01 backend + Plan 31-02 admin-web mock UI).
**Rationale:** Mirrors v1.3 cadence; HTTP wiring deferred to Phase 35 keeps Phase 31 scope tight. Captured as D-31-25..D-31-26.

---

## Claude's Discretion

- Pagination defaults (page=1, pageSize=50) — planner may calibrate if other endpoints diverged.
- FK-409 mapping pre-emptive test strategy — recommend monkeypatch IntegrityError (option c); planner finalises.
- Lazy vs eager mock-trainers seed — recommend lazy (mirrors clients/memberships).
- Zod schema field bounds (min/max for fullName, phone) — planner.
- Exact include_router placement order — planner confirms via existing chain inspection.

## Deferred Ideas

- HTTP-mode `apps/admin-web/src/shared/api/services/http/trainers.ts` → Phase 35.
- Trainer scheduling / payroll / commissions → out of v1.4 entirely.
- Trainer photo / bio / specializations → not in TRN-* spec; future milestone.
- `trainer_name_snapshot` on PT-sessions (B-05) → Phase 34.
- `POST /{id}/deactivate` endpoint variant → rejected (D-31-11).
- Owner-override hard-delete (force=true) → not in spec.

## Auto-mode Notes

- 0 pending todos matched phase 31 (`gsd-sdk query todo.match-phase 31` returned empty).
- No SPEC.md file — discussion drove implementation decisions directly from REQUIREMENTS.md verbatim + Phase 30 deliverables.
- No `.continue-here.md` blocking anti-patterns in Phase 31 directory.
- No prior CONTEXT.md for Phase 31 (first pass; single-pass cap respected).
- All 8 gray areas auto-selected and resolved in single pass.

---

*Auto-mode complete. CONTEXT.md is canonical; this log is reference only.*
