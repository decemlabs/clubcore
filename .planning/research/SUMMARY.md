# Project Research Summary — v1.4 Cash Sales + PT Packages

**Project:** Sportzal
**Milestone:** v1.4 — Cash Sales + PT Packages (subsequent milestone; v1.0–v1.3 already shipped)
**Domain:** Single-gym CRM (RU/CIS) — adding cash payment ledger + refund flow + trainers catalog + PT-package tariff + PT-session recording on top of an existing modular monolith.
**Researched:** 2026-05-14
**Overall confidence:** HIGH on stack + architecture (grounded in v1.0–v1.3 patterns); MEDIUM on PT-package domain edge cases (Q1/Q2 pro-rata, Q5 multi-package, Q7 expiry policy) that require operator input at discuss-phase.

---

## TL;DR

- **Zero new runtime libraries — backend or frontend.** Every v1.4 capability composes from the locked Python (FastAPI / SQLAlchemy / asyncpg / Pydantic v2) and TS (React 19 / TanStack / shadcn / Zod) stack. Money stays integer kopecks; status guards stay declarative-constant + `_assert_can_transition`; no FSM library, no `Money` class, no fiscal SDKs, no Stripe, no ЮKassa.
- **Three new backend modules: `trainers/`, `payments/`, `pt_packages/`.** Each respects `modules-independent` via four new Protocol slots in `core/dependencies.py` (`trainer_by_id_resolver`, `payment_recorder`, `payment_refunder`, `active_pt_package_resolver`) wired exclusively from `app/main.py:create_app()`. Three import-linter contracts unchanged — only the modules-independent list grows.
- **Architectural fork resolved: PT-packages get a separate `pt_packages` module with their own tables.** Both researcher recommendations are technically viable; we pick the separate-module path because it gives clean schema (no `NULL XOR NULL` columns), clean resolver semantics (date-based vs counter-based are different queries), clean audit taxonomy (`pt_package_*` ≠ `membership_*`), and clean v1.5 reporting (no `WHERE kind=` scans). Trade-off explicitly called out in §Bedrock decisions B-04 for operator override at requirements time.
- **Foundations Phase 30 locks the bedrock before any callsite:** `LOCKED_AUDIT_EVENTS` extension (34 → 50), `Resource` + `OWNER_ONLY` extensions with byte-paritet to admin-web `can.ts`, `.importlinter` modules list, SVC001 walker scope, append-only AST guard on `payments` writes, and all 12 Bedrock Decisions (B-01..B-12) recorded in PROJECT.md Key Decisions. This mirrors the v1.3 Phase 24 INFRA-15 discipline that let Phases 25/26/27 pass CI from their first commit.
- **Recommended ship order: 7 phases (30..36).** Foundations → Trainers (smallest, validates new-module template) → Payments + Membership sale-with-payment + Membership refund → PT-package plans + instances (no sessions) → PT-session recording → OpenAPI + admin-web full sweep → Milestone-verification with cross-phase human scenarios + Postgres race tests (REF-TEST-01, PTS-TEST-01) + 6-gate CI evidence.

---

## Stack Additions

**Decision: no new runtime dependencies.** Rejection summary:

| Candidate | Status | Why rejected |
|---|---|---|
| `py-moneyed` / Pydantic Money type | REJECT | Single-currency RUB; kopecks integer locked since v1.0. |
| Postgres `MONEY` type | REJECT | Locale-sensitive, driver-dependent string output (SQLAlchemy issue #5965). |
| `transitions` / `python-statemachine` | REJECT | v1.3 declarative `MEMBERSHIP_STATUS_TRANSITIONS` + `_assert_can_transition()` is enough. |
| `eventsourcing` | REJECT | Append-only payments + `audit_log` + `LOCKED_AUDIT_EVENTS` gate already give traceability. |
| ATOL / `ofd-py` / ЮKassa SDK / Stripe | REJECT | 54-ФЗ out of scope; ЮKassa deferred to v1.6; Stripe region-banned. |
| `dinero.js` / `money.js` | REJECT | `formatMoney(minor)` + BLK-04 form-boundary precedent work. |
| `xstate` (frontend FSM) | REJECT | Refund/PT-package status server-authoritative. |
| Chart / PDF / receipt libs | REJECT | Reports deferred to v1.5; no fiscal receipts. |

**Frontend cosmetic additions only:** extend `StatusBadge` discriminated union with 4 PT-package variants; add `PaymentBadge` for sale-vs-refund tinting. No new npm packages.

---

## Feature Categories

### Category 1 — Payments (cash)
- Single `payments` ledger row per sale, server-side `received_at`, `received_by_user_id`.
- `method TEXT NOT NULL DEFAULT 'cash'` from day one (forward seam for v1.6 ЮKassa).
- Append-only: no `deleted_at`, no `updated_at`, no UPDATE/DELETE in any service path (AST-guarded).
- Mandatory snapshot: `payment.amount == subject.price_kopecks_snapshot`.
- Audit `payment_recorded` with `payment_row_hash` (SHA-256 canonical-JSON).

**Anti-features:** card payments, fiscal receipts, partial payments, discounts, multi-currency, cash drawer reconciliation.

### Category 2 — Refunds
- **Refund is a row, not a column.** New `payments` row, `subject_kind='refund'`, `amount_kopecks < 0`, `refund_of FK`, partial UNIQUE on `refund_of`.
- Endpoint surfaces on subject: `POST /memberships/{id}/refund`, `POST /pt-packages/{id}/refund`.
- Reception self-serves (no owner approval). `(REFUND, MEMBERSHIPS)`+`(REFUND, PT_PACKAGES)` NOT in `OWNER_ONLY`.
- Full-refund only in v1.4. No pro-rata.
- Refund of `frozen` → 409 `must_unfreeze_first` (B-08).
- Refund of renewed source → 409 `cannot_refund_renewed_source` (B-09).
- Audit: `payment_refunded` + `membership_refunded` (distinct from `membership_cancelled`).

**Anti-features:** partial refunds, refund reversal, refund to different method, refund-window enforcement.

### Category 3 — Trainers
- `trainers` table: `id, full_name, phone NULL, is_active BOOLEAN, deleted_at`.
- Owner-only CRUD; reception has `(LIST, TRAINERS)` for PT-session picker.
- Hard-delete → 409 `trainer_in_use` if FK references exist. Owner deactivates instead.
- `trainer_name_snapshot` on PT-sessions (mirrors v1.2 plan snapshot).
- 4 audit events: created/updated/deactivated/reactivated.

**Anti-features:** schedules, shifts, pay rate, commission, trainer login, Telegram bot for trainers, ratings, certifications.

### Category 4 — PT Packages (tariff)
- Dedicated `pt_package_plans` (mirrors `membership_plans`).
- Dedicated `pt_packages` instance table with full snapshot suite + `sessions_remaining INTEGER NOT NULL CHECK >= 0 AND <= session_count_snapshot`.
- Status enum: `('active','exhausted','expired','cancelled')`.
- One active PT-package per client (partial UNIQUE).
- Expiry = sessions=0 OR `end_date < today`; new ARQ cron `expire_pt_packages` 06:25 MSK.
- **No freeze on PT-packages in v1.4.**

**Anti-features:** half-sessions, group PT, unlimited-session pt_package, PT-only floor access, per-trainer pricing, family-sharing.

### Category 5 — PT Sessions (recording)
- `pt_sessions` table: `pt_package_id, trainer_id, client_id (denormalised), performed_at, performed_by_user_id, cancelled_at NULL, cancel_reason NULL, trainer_name_snapshot, notes NULL`.
- Race-safe decrement: `UPDATE pt_packages SET sessions_remaining = sessions_remaining - 1 WHERE id=:id AND sessions_remaining > 0 AND status='active' RETURNING sessions_remaining`. 0 rows → 409 `pt_package_exhausted`.
- Auto-transition to `'exhausted'` when balance hits 0.
- Reception logs (not trainer self-service). `(CREATE, PT_SESSIONS)` reception+owner; `(CANCEL, PT_SESSIONS)` owner-only.
- Backdating: reception 7 days, owner unlimited.
- Cancellation: reception 24h, owner anytime; restores balance atomically.
- **PT-sessions independent of visits** (orthogonal events).

**Anti-features:** trainer self-service logging, scheduling/pre-booking, multi-trainer sessions, tip tracking, client signature.

---

## Architectural Integration

### Module structure — 3 new modules

| Module | Tables | Notes |
|---|---|---|
| `trainers/` | `trainers` | OWNER CRUD; reception LIST |
| `payments/` | `payments` (single table, refund = row with `refund_of` self-FK) | Reception writes; owner reads history |
| `pt_packages/` | `pt_package_plans`, `pt_packages`, `pt_sessions` | Plans owner-only; instances + sessions reception+owner |

Module count grows from 4 → 7. Within modular monolith scope.

### PT-package architectural fork — resolved

**Variant B (separate module) chosen.** Rationale:
1. **Schema integrity:** avoids `end_date NULL XOR sessions_remaining NULL` CHECK soup.
2. **Resolver semantics:** date-based vs counter-based queries have different indexes.
3. **Audit taxonomy:** `pt_package_*` ≠ `membership_*` audit verbs.
4. **v1.5 reports forward-seam:** revenue-from-memberships vs revenue-from-PT will be separate metrics.
5. **Freeze isolation:** PT-packages don't freeze → variant B avoids `if kind == 'pt_package'` branches in freeze service.

**Trade-off:** variant B adds 1 module skeleton + 1 Protocol slot + ~30% snapshot/transition boilerplate duplication.

**Override path (B-04):** if operator prefers variant A (extend `memberships`), Phase 33 scope internals shift; phases 30/31/32/34/35/36 unchanged.

### Protocol slots (`core/dependencies.py`)

| Slot | Producer | Consumer |
|---|---|---|
| `register_trainer_by_id_resolver` | `trainers.service` | `pt_packages.service.record_pt_session` |
| `register_payment_recorder` | `payments.service.record_payment` | `memberships.service.create_membership`, `pt_packages.service.create_pt_package` |
| `register_payment_refunder` | `payments.service.issue_refund` | `memberships.service.refund_membership`, `pt_packages.service.refund_pt_package` |
| `register_active_pt_package_resolver` | `pt_packages.service.resolve_active_pt_package_by_client` | reception PT-session form prefill |

All registered exactly once in `app/main.py:create_app()`. Inverse direction (`payments → memberships`) NOT needed — refund initiates from subject's module.

### Database migrations (0011 → 0015)

- **0011_trainers** — `trainers` + partial UNIQUE on `phone WHERE deleted_at IS NULL AND phone IS NOT NULL`.
- **0012_payments** — `payments` ledger; `subject_kind ∈ {'membership','pt_package','refund'}` CHECK; amount sign CHECK; `refund_of` self-FK + partial UNIQUE. **No `deleted_at`, no `updated_at`** (append-only).
- **0013_pt_package_plans** — `lower(name)` partial UNIQUE.
- **0014_pt_packages** — instances with full snapshot suite + CHECK invariants.
- **0015_pt_sessions** — sessions with denormalised `client_id` + `trainer_name_snapshot` + composite indexes.

Memberships status enum and Phase 17/24 machinery — **untouched.**

### RBAC additions

- New `Resource`: `TRAINERS`, `PAYMENTS`, `PT_PACKAGE_PLANS`, `PT_PACKAGES`, `PT_SESSIONS`.
- No new `Action` (reuse `VIEW/CREATE/EDIT/DELETE/REFUND/CANCEL`).
- `OWNER_ONLY` grows 15 → ~26 entries.
- Three-way byte-paritet to `apps/admin-web/src/shared/session/can.ts` enforced by existing parity test.

### LOCKED_AUDIT_EVENTS additions (34 → 50)

```
trainer_created, trainer_updated, trainer_deactivated, trainer_reactivated,
payment_recorded, refund_issued, membership_refunded,
pt_package_plan_created, pt_package_plan_updated, pt_package_plan_archived,
pt_package_sold, pt_package_cancelled, pt_package_refunded, pt_package_exhausted, pt_package_expired,
pt_session_recorded, pt_session_cancelled
```

Pre-registered in Phase 30 (v1.3 INFRA-15 discipline). Canonical payload schemas locked there — especially `payment_refunded` carrying `payment_row_hash`.

### Import-linter — unchanged

Only `modules-independent` list extends with `trainers`, `payments`, `pt_packages`.

---

## HIGH-Severity Pitfalls & Prevention

| # | Pitfall | Prevention |
|---|---|---|
| H-01 | Payment row not append-only | Schema has NO `deleted_at`/`updated_at`; AST walker forbids UPDATE/DELETE on `payments`. B-01. |
| H-02 | Refund without sale | Refund endpoint requires `payment_id` FK `ON DELETE RESTRICT`. |
| H-03 | Double refund / refund > original | Partial UNIQUE on `refund_of`; full-refund-only (B-02). Test REF-TEST-01. |
| H-04 | PT-session decrement race | Atomic `UPDATE … WHERE sessions_remaining > 0 RETURNING …`; CHECK `>= 0`. Test PTS-TEST-01. |
| H-05 | Refund of frozen membership | Reject 409 `must_unfreeze_first` (B-08). |
| H-06 | Refund of renewed-source | Reject 409 `cannot_refund_renewed_source` (B-09). |
| H-07 | Refund missing audit row | Pre-register events Phase 30; SVC001 walker extended to `payments/service.py`. |
| H-08 | Trainer hard-delete breaks PT-session FK | `ON DELETE RESTRICT` + 409 `trainer_in_use` + `trainer_name_snapshot` (B-05). |
| H-09 | PT-package `session_count` mutability post-sale | Mandatory snapshot; plan-level immutable. |
| H-10 | Sale double-submit | RHF `formState.isSubmitting` + `Idempotency-Key` header + Redis 1h cache. |
| H-12 | Cash drawer reconciliation drift | NO end-of-day close in v1.4 (B-06); deferred to v1.5. |
| H-13 | Refund single-click footgun | AlertDialog + confirm checkbox; >24h refund owner-only (B-07). |
| H-14 | Audit payload missing payment hash | Lock canonical schema Phase 30: `payment_refunded` includes `payment_row_hash`. |

Full pitfalls (14 HIGH + 14 MEDIUM + 4 LOW) in PITFALLS.md.

---

## Bedrock Decisions (lock in Phase 30)

| # | Decision | Default |
|---|---|---|
| B-01 | `payments` append-only — no soft-delete, no UPDATE | LOCK; AST-enforced |
| B-02 | Refund full-amount only (no pro-rata in v1.4) | LOCK; defer pro-rata to v1.5+ |
| B-03 | `LOCKED_AUDIT_EVENTS` pre-registered in Phase 30 | LOCK (workflow) |
| B-04 | **PT-packages separate module + dedicated tables** | LOCK variant B; override path documented |
| B-05 | `trainer_name_snapshot` on PT-session | LOCK (non-negotiable) |
| B-06 | No end-of-day cash-drawer close in v1.4 | LOCK |
| B-07 | Refund permission: reception <24h, owner >24h | LOCK (confirm at requirements) |
| B-08 | Refund of frozen → 409 `must_unfreeze_first` | LOCK simpler-path |
| B-09 | Refund of renewed-source → 409 | LOCK |
| B-10 | PT-package alone does NOT grant gym entry | RECOMMENDED; flag for operator |
| B-11 | PT-session backdating: reception 7d / owner unlimited | LOCK |
| B-12 | PT-session cancellation: reception 24h / owner anytime | LOCK |

Sub-decisions deferred to discuss-phase: Q5 (multi-package), Q7 (date-expiry), Q13 (resolver tiebreak FIFO), M-13 (trainer phone uniqueness), M-10 (PT-package renewal carry-over).

---

## Suggested Phase Order

**7 phases (30..36), mirrors v1.3 cadence (6 feature + 1 verify).**

### Phase 30 — Foundations (bedrock)
**Delivers:** 12 Bedrock Decisions; `LOCKED_AUDIT_EVENTS` extended; `Resource`+`OWNER_ONLY` extended with three-way parity; `.importlinter` modules list; SVC001 walker scope; append-only AST walker; v1.3 deferred `mock/memberships.ts ?status=` parity closed.
**Mirrors:** v1.3 Phase 24.
**Research flag:** NO.

### Phase 31 — Trainers module
**Delivers:** Migration 0011; `trainers/` full module; 4 CRUD endpoints + `?active=true`; Protocol slot `register_trainer_by_id_resolver` (wired in both `main.py` and `telegram_bot.py` per REG-29-03 lesson); admin-web `/trainers` page + mock service.
**Mirrors:** v1.2 Phase 16.
**Research flag:** NO.

### Phase 32 — Payment ledger + Membership sale-with-payment + Membership refund
**Delivers:** Migration 0012; `payments/` with `record_payment` + `issue_refund`; Protocol slots `payment_recorder`+`payment_refunder`; modified `memberships.service.create_membership`; `POST /memberships/{id}/refund`; audit events; admin-web sale-form extension + refund button + AlertDialog; `Idempotency-Key` header.
**Mirrors:** v1.2 Phase 17-22 + v1.3 Phase 25.
**Research flag:** NO.

### Phase 33 — PT-package plans + instances (no sessions)
**Delivers:** Migrations 0013+0014; `pt_packages/` plans router (owner-only) + packages router (sell/cancel/refund/list/get); `PT_PACKAGE_STATUS_TRANSITIONS` constant; Protocol slot `active_pt_package_resolver`; ARQ cron `expire_pt_packages` 06:25 MSK; admin-web `/pt-package-plans` + `/pt-packages`.
**Research flag:** YES (light) — needs Q5, Q7, B-04 confirmation at discuss-phase.

### Phase 34 — PT-session recording
**Delivers:** Migration 0015; `record_pt_session` + `cancel_pt_session` with race-safe decrement; endpoints + audit; admin-web "record PT-session" panel + session history.
**Research flag:** YES (light) — Q3, Q4.

### Phase 35 — OpenAPI drift gate refresh + admin-web full sweep
**Delivers:** Regenerated byte-stable `openapi.json` + `schema.d.ts`; full http-mode validation; TanStack Query mutation hooks; `PaymentBadge` + `PtPackageStatusBadge`; locked Russian i18n; three-way RBAC parity.
**Mirrors:** v1.2 Phase 21-22 + v1.3 Phase 28.
**Research flag:** NO.

### Phase 36 — Milestone verification
**Delivers:** 7+ operator scenarios; live backend+Telegram sandbox; REF-TEST-01 + PTS-TEST-01 + PAY-TEST-01 + AUDIT-TEST-01 real-Postgres tests; 6 CI gate evidence; operator sign-off in `milestones/v1.4-VERIFICATION-LOG.md`.
**Mirrors:** v1.3 Phase 29.
**Research flag:** NO.

### Ordering rationale
- Trainers before PT-sessions (FK target).
- Payments before PT-packages (recorder slot reuse).
- PT-package instances before PT-sessions (decrement target).
- OpenAPI sweep at end (single atomic regen).
- Foundations first (all subsequent phases pass CI from commit 1).

---

## Open Questions for Discuss-Phase

| # | Phase | Question | Default |
|---|---|---|---|
| Q1 | 32 | Pro-rata refund for partial use? | Full-only (B-02) |
| Q2 | 32 | Refund permission: uniform reception OR 24h split? | 24h split (B-07) |
| Q3 | 34 | PT-session implicit visit-creation? | NO — orthogonal |
| Q4 | 34 | PT-session cancellation: 24h reception / owner anytime? | YES (B-12) |
| Q5 | 33 | Multiple active PT-packages per client? | NO — one active |
| Q6 | 33 | PT-package alone grants gym entry? | NO (B-10) |
| Q7 | 33 | PT-package expiry: time / count / both? | BOTH whichever first |
| Q8 | 33/34 | PT-package renewal carries remaining sessions? | NO |
| Q9 | 32 | Refund reason: enum / free-text / both? | Both |
| Q10 | 30 | **B-04 fork: variant A or B?** | Variant B |
| Q11 | 30 | Trainer phone E.164 validation when present? | YES |
| Q12 | 32 | Idempotency: header+Redis OR `SELECT FOR UPDATE`? | Header+Redis |
| Q13 | 33 | Active-PT-package resolver tiebreak if ≥2? | `start_date ASC, created_at DESC` FIFO |
| Q14 | 33 | `expire_pt_packages` cron slot? | 06:25 MSK |
| Q15 | 35 | Telegram bot extension for PT? | NO — out of scope |
| Q16 | 30 | Trainer soft-delete: `is_active` toggle OR `deleted_at`? | BOTH |

---

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack additions | HIGH | Zero new libs verified. |
| Features (Cat 1, 2, 3) | HIGH | Industry-triangulated. |
| Features (Cat 4, 5) | MEDIUM | PT-package edges divergent industry-wide; defaults defensible. |
| Architecture (modules+slots+migrations) | HIGH | Grounded in v1.0-v1.3 precedents. |
| Architecture (PT-package fork) | MEDIUM | Variant B recommended; A is valid override. |
| Pitfalls HIGH-severity | HIGH | Each has concrete prevention. |
| Pitfalls MEDIUM/LOW | HIGH | Same rigor. |

**Overall: HIGH** for shippability; **MEDIUM** for PT-package architectural choice + 5 policy edges (B-04/Q1/Q5/Q6/Q7) — all with explicit override paths.

### Gaps to address during planning
1. B-04 / Q10 — variant A vs B (Phase 30 discuss-phase).
2. Q1 — pro-rata refund policy (Phase 32).
3. Q7 — PT-package date-expiry (Phase 33).
4. Q6 — PT-package floor-access (Phase 33).
5. Q5 — multi-package per client (Phase 33).

None block roadmap creation.

---

## Sources

### Primary
- SQLAlchemy 2.1 PostgreSQL dialect docs
- SQLAlchemy issue #5965 — PostgreSQL MONEY returns string
- PostgreSQL official Monetary Types docs
- `.planning/PROJECT.md`, `apps/backend/.importlinter`, `apps/backend/app/main.py`, `app/core/dependencies.py`, `app/core/permissions.py`, `app/core/audit.py`
- v1.2/v1.3 verification logs

### Secondary
- Resawod, PushPress, Club-OS, Pipedrive gym CRM industry references

---

*Research completed: 2026-05-14. Ready for roadmap: yes.*
*Synthesized from: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md, PROJECT.md*
