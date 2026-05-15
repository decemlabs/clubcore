# Phase 33: PT-Package Plans + Instances — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 33-pt-package-plans-instances
**Mode:** Auto (recommended defaults) — single-pass; user selected "Auto (recommended defaults)" at mode prompt.
**Areas auto-resolved:** Migration split, Table columns (plans + instances), Status FSM, Module shape, Endpoints + permissions, PATCH immutability, Soft-delete with instances, Sale flow, Cancel-no-refund, Refund flow, Protocol slot, ARQ cron, Cron NULL edge case, Audit events, Idempotency, Snapshot symmetry, REF-02 router location, Tests scope.

---

## Migration split (D-33-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate revisions (0013 + 0014) | Catalog and instance separated; clean down-revision chain | ✓ (recommended) |
| One combined revision (0013 only) | Mirror Phase 32 mixed-migration pattern | |

**Rationale:** Phase 32 mixed-migration only justified by cross-table dependency (refund needed both payments + cancellation_reason); here plans must exist before instances FK them, two clean concerns better.

---

## `pt_package_plans` column shape (D-33-02 / PT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim REQUIREMENTS PT-01 (immutable session_count/price/validity + partial UNIQUE lower(name)) | Mirrors v1.2 membership_plans pattern | ✓ (recommended) |
| Mutable price_kopecks with versioned history | Out of scope; would require new table | |

---

## `pt_packages` instance column shape (D-33-03 / PT-04, PT-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Full snapshot suite + sessions_remaining + status + end_date stored | Mirrors REQUIREMENTS verbatim; computed-and-stored end_date | ✓ (recommended) |
| Postgres GENERATED ALWAYS end_date | Virtual computed column | |
| Snapshot fields nullable | Reduces snapshot discipline | |

**Rationale:** Computed-and-stored simpler for fixture parity and downstream test setup; snapshot discipline matches v1.2 memberships.

---

## `PT_PACKAGE_STATUS_TRANSITIONS` FSM (D-33-04 / PT-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Roadmap FSM verbatim (active→{exhausted, expired, cancelled}; exhausted→cancelled; expired→cancelled; cancelled terminal) | Mirror memberships pattern + ROADMAP locked | ✓ (recommended) |
| Allow exhausted→active via session cancel | Phase 34 concern; needs cross-phase coordination | (Phase 34 will add) |

**Rationale:** Phase 34 cancel-of-session may un-exhaust package via balance restore — that transition (`exhausted→active`) is a Phase 34 concern and will extend the constant there; Phase 33 ships only the refund/expire edges.

---

## Module shape (D-33-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror memberships module structure (constants/models/repo/schemas/service/router) | Established pattern | ✓ (recommended) |
| Slimmer single-file module | Diverges from precedent | |

---

## Endpoints + permissions (D-33-06 / PT-02, PT-07..10)

| Option | Description | Selected |
|--------|-------------|----------|
| 10 endpoints, RBAC matrix per ROADMAP SC + INFRA-19 | Mirror reception+owner sale/refund; owner-only plan CRUD + cancel | ✓ (recommended) |
| Reception can cancel without refund | Breaks B-07 distinction (owner-only cancel; reception+owner refund) | |

---

## PATCH plan immutability enforcement layer (D-33-07 / PT-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Service-level 409 `field_immutable` (schema includes optional fields, service compares to current) | Matches ROADMAP locked 409 code | ✓ (recommended) |
| Pydantic schema-level `extra='forbid'` 422 | Wrong status code per ROADMAP SC #2 | |

---

## Soft-deleted plan referenced by instances (D-33-08)

| Option | Description | Selected |
|--------|-------------|----------|
| 409 `plan_in_use` on DELETE if instances exist; sale filter `deleted_at IS NULL` | Snapshot pattern keeps history readable; new sales blocked | ✓ (recommended) |
| Hard-delete with CASCADE | Destroys forensic history | |

---

## Sale flow / payment_recorder consumption (D-33-09, D-33-17 / PT-07, PAY-05 mirror)

| Option | Description | Selected |
|--------|-------------|----------|
| `create_pt_package` orchestrator owns UoW; calls `get_payment_recorder()`; validates amount==plan.price; partial UNIQUE final gate | Mirror v1.2/Phase 32 sale pattern | ✓ (recommended) |
| Client passes own amount with no symmetry check | Trust-client pattern; rejected per snapshot discipline | |

---

## Cancel-no-refund flow (D-33-10 / PT-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Owner-only; free-text reason required; no payment row; emits `pt_package_cancelled` | ROADMAP locked; symmetric to v1.3 admin-cancel of membership | ✓ (recommended) |
| Owner-only with automatic balance entry | Conflates cancel and refund semantics | |

---

## Refund flow (D-33-11 / REF-02 / B-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Reception+owner; `refund_pt_package` orchestrator owns UoW; consumes `get_payment_refunder()`; no freeze/renewal guards; only `invalid_transition` + `already_refunded` + `original_payment_not_found` | ROADMAP locked + B-07 uniform reception | ✓ (recommended) |
| Owner-only refund | Breaks B-07 uniformity | |
| Allow partial refund | B-02 full-only | |

---

## `register_active_pt_package_resolver` Protocol slot (D-33-12 / PT-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror `ActiveMembership` shape with silent-None accessor; wired from `app/main.py:create_app()` only | Mirror Phase 17 D-18 pattern | ✓ (recommended) |
| Defensive-raise like PaymentRecorder | Wrong fit — consumers (Phase 34 session sale) should treat "no active pkg" as 409, not RuntimeError | |
| Double-wire from telegram_bot.py | Bot is NOT consumer for PT-sessions; v1.4 telegram has no PT touchpoints | |

---

## ARQ cron `expire_pt_packages` (D-33-13 / PT-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror `expire_memberships.py` shape; 06:25 MSK (`hour=3, minute=25` UTC; `unique=True, keep_result=60`); worker owns commit; helper caller-owns-txn | Mirror Phase 18 + ROADMAP locked | ✓ (recommended) |
| Hourly cron with smaller batches | Unnecessary frequency for daily-grained expiry | |

---

## Cron behaviour for NULL end_date instances (D-33-14)

| Option | Description | Selected |
|--------|-------------|----------|
| SQL filter `end_date IS NOT NULL AND end_date < today` excludes NULL packages permanently | NULL means "no time-expiry" — never auto-expire | ✓ (recommended) |
| Auto-expire NULL after some grace period | Violates "no time-expiry" contract | |

---

## 5 audit events payload shapes (D-33-15 / PT-03, PT-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify Plan 30-01 payload schemas match decision shapes during planning; supplement if mismatch | Pre-registered events have schemas — planner ensures parity | ✓ (recommended) |
| Re-emit events as ad-hoc strings | Banned by `audit.emit` AST gate from Phase 24 | |

---

## Idempotency-Key reuse on PT endpoints (D-33-16 / PAY-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Required on sale + refund + cancel; reuse Phase 32 `idempotency_dependency` | ROADMAP locked; matches PAY-09 forward seam | ✓ (recommended) |
| Optional / sale-only | Breaks money-mutating-endpoints universal discipline | |

---

## REF-02 router location (D-33-18)

| Option | Description | Selected |
|--------|-------------|----------|
| `pt_packages/router.py` (subject-side ownership) | Mirrors `memberships/router.py:refund_membership` | ✓ (recommended) |
| `payments/router.py` (verb-side ownership) | Breaks subject-module ownership principle | |

---

## Tests scope (D-33-19)

| Option | Description | Selected |
|--------|-------------|----------|
| Unit (FSM + immutability + cron SQL) + Integration (CRUD + sale + refund + cancel + race REF-TEST-02) + Cron tick + Worker resolution invariant | Mirror Phase 32 + Phase 18 testing discipline | ✓ (recommended) |
| Skip race test | REF-08 contract violation; concurrency landed at DB layer needs proof | |

---

## Claude's Discretion

- Exact internal helper splits within service.py (private `_validate_sale_input` etc.) — planner picks.
- `permissions.py` may be empty stub if router uses `require_permission(...)` inline (matches memberships).
- Test file naming follows `test_pt_packages_<concern>.py` convention.
- Repository helper parameter shapes (positional vs keyword-only) follow existing per-file conventions.

## Deferred Ideas

- `pt_package_refunded` payload SHA-256 hash parity — v1.5+ (subject-side hashing deferred from Phase 30).
- Pro-rata refunds — out of v1.4 (B-02 full-only).
- Multi-package per client — v1.5 (drop partial UNIQUE).
- PT-package renewal carry-over — v1.5+ (Q8 expansion); needs renewed-source refund guard when landed.
- PT-package freeze — not on roadmap.
- Telegram bot `/pt_packages` balance — v1.5+ (Q15).
- admin-web `/pt-package-plans` + `/pt-packages` UI + PtPackageStatusBadge + mock parity — **Phase 35** (FE-10..18).
- OpenAPI byte-stable regen + `schema.d.ts` — **Phase 35**.
- End-of-day cash-drawer reconciliation — v1.5+ (B-06).
