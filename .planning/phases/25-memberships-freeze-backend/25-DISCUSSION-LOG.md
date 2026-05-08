# Phase 25: Memberships — Freeze (backend) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 25-memberships-freeze-backend
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude — no AskUserQuestion calls)
**Areas discussed:** Migration scope/numbering, Freeze period table shape, Service-layer flows (freeze/unfreeze/cancel-from-frozen), Half-day rounding, Concurrency/race handling, Schema/response shape, State machine extension, Repository helpers, Endpoint signatures + RBAC, Exception classes, Test taxonomy, Audit payload schemas, Frontend / OpenAPI implications

---

## Migration scope & numbering

| Option | Description | Selected |
|--------|-------------|----------|
| Combined `0008_freeze_and_renewal.py` (Phase 25 ships freeze cols, Phase 26 extends with `previous_membership_id`) | One revision authored in Phase 25 covering both phases' columns | |
| Separate `0008_freeze.py` (Phase 25), then `0009_renewal.py` (Phase 26) on top | Independent migrations, no cross-phase coupling | ✓ |

**Auto-selected:** Separate migrations (D-25-01).
**Rationale:** Decoupling phase boundaries — if Phase 25 needs hotfix, migration doesn't carry unused renewal columns. Mirrors Phase 24's reasoning for INFRA-16 in its own `0007`. Roadmap milestone note "shared `0007`" already superseded after Phase 24's `0007_status_taxonomy`; Phase 25 plan agent updates the milestone roadmap text.

---

## Freeze period table — index strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Partial unique index `(membership_id) WHERE ended_at IS NULL` only | DB-level race protection; small table; covers write-path lookups | ✓ |
| Add a regular `(membership_id)` index alongside | Faster aggregate scans for `freezeDaysUsed` computation | |

**Auto-selected:** Partial unique index only (D-25-05/D-25-06).
**Rationale:** Aggregate scans hit small per-membership row counts; redundant index would only inflate INSERT cost. Mirror Phase 19 visits index parsimony.

---

## Limit guard placement

| Option | Description | Selected |
|--------|-------------|----------|
| Preventive on `freeze_membership` (refuse before opening period) | Client knows immediately if limit exhausted | ✓ |
| Post-hoc on `unfreeze_membership` (cap `end_date` extension) | Allows freeze, but caps days_added | |
| Both (defence-in-depth) | Two redundant guards | |

**Auto-selected:** Preventive only (D-25-07 step 3).
**Rationale:** Better UX (immediate feedback); race window guarded by partial unique index (concurrent freezes serialise → second gets `already_frozen`, not `freeze_limit_exceeded`).

---

## Half-day rounding implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Seconds-based `math.ceil(delta / 86400)` with min=1 | Simple; UTC=MSK seconds-equivalent (no DST in MSK since 2014) | ✓ |
| MSK calendar-day boundaries (date arithmetic, not duration) | Calendar-aware; interprets "in Europe/Moscow days" literally | |

**Auto-selected:** Seconds-based ceil with min=1 (D-25-08 step 5).
**Rationale:** MSK is UTC+3 fixed → seconds-based gives same answer; min=1 prevents instant-freeze-loop abuse; tests can inject deterministic timestamps.

---

## Concurrent freeze race handling

| Option | Description | Selected |
|--------|-------------|----------|
| Rely on partial unique index; translate IntegrityError → 409 `already_frozen` | DB wins race; same pattern as Phase 19 visits | ✓ |
| `SELECT ... FOR UPDATE` on membership row before INSERT | Pessimistic locking | |

**Auto-selected:** Partial unique index + translation (D-25-22).
**Rationale:** DB-level race protection is the established pattern (Phase 19 visits). Avoids lock contention.

---

## Cancel-during-freeze audit payload

| Option | Description | Selected |
|--------|-------------|----------|
| `membership_unfrozen` with `days_added=0` sentinel + then `membership_cancelled` | Stable payload schema; cancel context implied by adjacent event | ✓ |
| Add `via_cancel: bool` flag on `membership_unfrozen` payload | Explicit discriminator | |

**Auto-selected:** `days_added=0` sentinel (D-25-09).
**Rationale:** Preserves stable `membership_unfrozen` schema; SQL forensics can detect via `days_added=0` + adjacent `membership_cancelled` row. Less payload variance.

---

## `freezeDaysUsed` computation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Single SQL aggregate (CEIL of EXTRACT EPOCH per period, SUM) | Byte-stable with Python ceil; handles ongoing period via COALESCE(ended_at, now()) | ✓ |
| Python iteration over loaded period rows | Simpler for unit testing | |

**Auto-selected:** SQL aggregate (D-25-16).
**Rationale:** N+1 avoidance for list endpoint; subquery reusable across detail/list paths.

---

## State machine extension

**Auto-selected:** Phase 24 placeholder `frozen: frozenset()` populated to `frozen: {active, cancelled}`; `active` extended to `{expired, cancelled, frozen}`. Test parametrize matrix expanded from 9 cells (Phase 17/24) to 16 cells (D-25-14/D-25-15).

---

## Endpoint shape

**Auto-selected (D-25-19):**
- `POST /api/v1/memberships/{id}/freeze` — `(CREATE, MEMBERSHIPS)` + `verify_csrf`, empty body, 200 OK with `MembershipResponse`.
- `POST /api/v1/memberships/{id}/unfreeze` — same dependencies, same response shape.
- `cancel_membership` endpoint signature unchanged; service-layer extension handles `frozen → cancelled`.

---

## Resolver touch

**Auto-selected:** NO change (D-25-17). Resolver already filters `status='active'`; frozen rows naturally excluded. Phase 25 contributes integration test only — preserves the resolver's serialised-touchpoint discipline (Phase 24 = end_date filter; Phase 25 = nothing; Phase 26 = tiebreak).

---

## OpenAPI regeneration timing

**Auto-selected:** Plan agent confirms CI drift-gate behaviour, then either commits regenerated `openapi.json` in Phase 25's last commit (per-commit gate) or defers to Phase 28 (milestone-end gate). Mirrors Phase 24 D-24-25 carry-forward.

---

## Claude's Discretion

- Exact filenames для new test files (D-25-23 are proposals).
- Whether `_freeze_days_used_subquery()` lives in repository.py vs separate helper (recommend: repository.py).
- Whether freeze ORM model inlines в `models.py` vs splits to `models_freeze.py` (recommend: inline).
- Naming для thin transition wrappers (`_assert_can_freeze` / `_assert_can_unfreeze`) — central guard direct call also acceptable.
- Backfill default value for archived plans confirmed at `14` (matches REQUIREMENTS MEM-FRZ-03 wording).

---

## Deferred Ideas

- **Auto-unfreeze cron** — manual unfreeze only in v1.3.
- **Operator-facing freeze reason field** — body is empty per REQUIREMENTS; backlog candidate.
- **Freeze period editing** — out of scope; audit trail integrity over operator convenience.
- **Multiple concurrent freezes** — prevented by partial unique index by design.
- **Telegram bot self-serve `/freeze` command** — staff-only flow in v1.3.
- **Renewal during freeze** — allowed by Phase 26 MEM-REN-02; cross-phase verification in Phase 29.
- **Freeze/unfreeze notifications** — not in v1.3.
- **Charge-back / refund logic during freeze cancel** — no billing module in v1.3.

---

*Generated 2026-05-08 — `--auto` mode (Claude selected recommended defaults; no interactive AskUserQuestion calls).*
