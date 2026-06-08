# Phase 97: Reward Crediting - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Server-authoritative referral reward crediting. On the YooKassa `payment.succeeded`
webhook for a captured referee's **first membership purchase**, insert two
`loyalty_ledger` rows co-transactionally — the referrer's referral bonus and the
referee's welcome-style bonus — using owner-configured amounts (Phase 96).
Idempotent and one-bonus-per-referee. Backend only; no PWA UI (Phase 98); rewards
are NEVER credited on a client request (REFER-04 server-authoritative).

Requirement: REFER-04.

Insertion point: `app/api/v1/_internal/yookassa/handlers.py` → `handle_payment_succeeded`,
inside the existing `async with session.begin():` UoW, in the membership branch
(after activation / `record_loyalty_redemption`, before post-commit enqueue), following
the exact RETURNING-gated co-transactional pattern already used there.
</domain>

<decisions>
## Implementation Decisions

### Ledger Schema for Referral Accruals
- **New `entry_type='referral_accrual'`** added to the `loyalty_ledger` CHECK constraint (`entry_type IN ('welcome','owner_grant','redemption','referral_accrual')`) via a new migration. Widen the `loyalty_accrued` audit payload only if reused — but referral uses its own audit event (see below), so the `loyalty_accrued` Literal need not change.
- **Add nullable `referral_capture_id` FK → `referral_captures.id` (ondelete RESTRICT, explicit name `fk_loyalty_ledger_referral_capture_id_referral_captures`)** to `loyalty_ledger`, set on `referral_accrual` rows only (NULL otherwise) — mirrors the Phase 83 nullable `online_payment_id` column pattern. Also set the existing `online_payment_id` column on referral rows for the audit/forensic trail.
- **Idempotency anchor:** partial UNIQUE index `uq_loyalty_ledger_referral_accrual` on `(referral_capture_id, client_id) WHERE entry_type='referral_accrual'`. Declared as a literal-named partial index in the migration (not an ORM Index), per the `uq_loyalty_ledger_welcome` precedent. This guarantees exactly one referrer-bonus row + one referee-bonus row per capture (distinct `client_id`), satisfying webhook-replay idempotency (crit 2) AND one-bonus-per-referee / no-second-purchase-bonus (crit 3) with a single guard.
- **Both rows inserted in the same UoW** — co-transactional inside the existing `async with session.begin():` block alongside activation. No deferral to ARQ.
- `amount_kopecks` is positive (accrual) for both rows. Referrer row uses `referrer_bonus_kopecks`; referee row uses `referee_welcome_kopecks`. `category` may be set to `'referral'` for human-readability (optional, Claude's discretion).

### Trigger Conditions & First-Purchase Gate
- **Membership purchases only** (`subject_kind == 'membership'`). PT-package purchases do NOT trigger referral bonuses.
- **First-purchase gate:** credit only when this `payment.succeeded` is the referee's FIRST succeeded membership payment — i.e. zero prior `online_payments` rows for this `client_id` with `status='succeeded'` and a non-null `membership_plan_id` (excluding the current row). Honors "first membership purchase by invited friend." The UNIQUE guard makes webhook replay and any later purchases natural no-ops.
- **Capture precondition:** a `referral_captures` row must exist for the referee (`referee_client_id == row.client_id`). No capture → no crediting. Self-referral was already blocked at capture time (Phase 96).
- **Referrer soft-deleted at crediting time → void the entire referral accrual** (credit neither side). Avoids an orphan bonus tied to a deleted referrer. Check referrer alive via raw SQL (D-54-08).

### Audit, Amounts & Architecture
- **New LOCKED audit event `referral_bonus_accrued` (resource_type `"loyalty"` or `"referral"` — Claude's discretion, follow precedent)** registered in `LOCKED_AUDIT_EVENTS` + a typed payload class in `audit_payloads.py` BEFORE any callsite (INFRA-15). Emitted **per ledger row** (one for the referrer, one for the referee) with a `role` marker (`'referrer' | 'referee'`), carrying `client_id`, `entry_id`, `amount_kopecks`, `referral_capture_id`, `online_payment_id`. Emitted only on a real insert (RETURNING-gated).
- **Webhook handler orchestrates** the crediting (composition layer, `app/api/...handlers.py`): it (1) looks up the referee's capture via `referrals.service`, (2) reads amounts from the `referral_config` singleton via `referrals.service`/repository, (3) performs the first-purchase check, (4) calls the new `loyalty.service.accrue_referral_bonus()` primitive for each side. This keeps `referrals` and `loyalty` modules import-independent (import-linter: modules cannot import each other) — exactly how the handler already wires `record_loyalty_redemption`.
- **Amounts come exclusively from `referral_config`** (Phase 96 owner-configurable singleton), read at crediting time. No hardcoded amounts at the callsite (crit 4).
- **New primitive `accrue_referral_bonus(session, *, client_id, amount_kopecks, referral_capture_id, online_payment_id, role)`** in `loyalty/service.py` — flush-only (caller-owns-txn, never commits; the webhook UoW owns the commit), `pg_insert(...).on_conflict_do_nothing(index_elements=["referral_capture_id","client_id"], index_where=text("entry_type = 'referral_accrual'")).returning(LoyaltyLedger.id)`, RETURNING-gated `referral_bonus_accrued` audit emit. Mirrors `accrue_welcome_bonus` exactly.

### Claude's Discretion
- Exact migration number (next after 0068 — likely 0069), index/constraint literal names (follow NAMING_CONVENTION + literal-in-migration discipline), `category` value usage.
- `resource_type` string for the new audit event and the precise payload field set (must include the role marker + linkage ids).
- Helper for the first-purchase count query (raw SQL vs repository method) — keep cross-module reads as raw SQL per D-54-08 if touching clients/online_payments from another module.
- Whether `accrue_referral_bonus` computes/returns a balance (not needed for webhook path — likely returns the inserted id or None).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/loyalty/service.py:68` `accrue_welcome_bonus` — the exact flush-only, pg_insert on_conflict_do_nothing + index_where partial-index + RETURNING-gated audit template for `accrue_referral_bonus`.
- `app/modules/loyalty/service.py:139` `owner_grant_loyalty` — category/reason ledger insert + balance fold reference.
- `app/modules/loyalty/service.py:290` `record_loyalty_redemption` — the webhook-locked, online_payment_id-anchored idempotent writer; closest analog for a referral accrual keyed to a payment.
- `app/modules/loyalty/models.py` — `LoyaltyLedger` with signed `amount_kopecks`, existing nullable `online_payment_id` FK (Phase 83), `category`/`reason`, the `entry_type` CHECK (`name="entry_type"` bare suffix), partial-UNIQUE-in-migration discipline (`uq_loyalty_ledger_welcome`, `uq_loyalty_ledger_online_payment_id`).
- `app/api/v1/_internal/yookassa/handlers.py:347` `handle_payment_succeeded` — the single `async with session.begin():` UoW; subject-kind dispatch (`membership` vs `pt_package`); already imports `loyalty.service.record_loyalty_redemption`; `_read_client_receipt_contact` raw-SQL clients read pattern (D-54-08).
- Phase 96 referral module: `referral_captures` (referee↔referrer binding), `referral_config` singleton (`referrer_bonus_kopecks`, `referee_welcome_kopecks`), `referrals.service`/`repository` for capture + config reads.
- `app/core/audit.py` `LOCKED_AUDIT_EVENTS` (~line 481, v2.6 block) + `audit_payloads.py` `AUDIT_PAYLOAD_SCHEMAS` (~line 1354 v2.6 block) — register `referral_bonus_accrued` here before callsite.

### Established Patterns
- Caller-owns-txn (D-03/D-32-10): loyalty accrual primitives flush only; the webhook `async with session.begin()` owns the commit.
- RETURNING-gated audit: emit only when `scalar_one_or_none()` returns an id (no double-audit on replay).
- `index_where=text("entry_type = '...'")` literal predicate (NOT bound param) for ON CONFLICT arbiter inference against a partial UNIQUE index (the exact gotcha documented in `accrue_welcome_bonus`).
- Cross-module reads via raw `text()` SQL — no ORM import of other modules' models (D-54-08); import-linter forbids module↔module imports.
- Migrations in `apps/backend/alembic/versions/`; latest is `0068_seed_referral_config.py` — Phase 97 migration starts at 0069. CHECK-constraint change needs drop+recreate of the named constraint in upgrade/downgrade.

### Integration Points
- `handle_payment_succeeded` membership branch — insert the referral crediting call after activation, before `_post_commit_enqueue`, all inside `async with session.begin()`.
- `LOCKED_AUDIT_EVENTS` + `AUDIT_PAYLOAD_SCHEMAS` — `referral_bonus_accrued` registration (INFRA-15).
- `referral_config` read for amounts; `referral_captures` read for the referee's capture + referrer id.

</code_context>

<specifics>
## Specific Ideas

- Single partial-UNIQUE `(referral_capture_id, client_id) WHERE entry_type='referral_accrual'` satisfies both replay-idempotency (crit 2) and one-bonus-per-referee/second-purchase (crit 3).
- First-purchase gate = zero prior succeeded membership `online_payments` for the referee (excluding the current row).
- Referrer soft-deleted → void entire accrual.
- `accrue_referral_bonus` mirrors `accrue_welcome_bonus` line-for-line (flush-only, RETURNING-gated, partial-index ON CONFLICT).

</specifics>

<deferred>
## Deferred Ideas

- Referral bonus on PT-package purchases — out of scope (membership only).
- Crediting the referee welcome even when referrer is deleted — rejected in favor of void-entire-accrual.
- Notifying both parties of the accrued bonus (DM/push) — not in REFER-04 scope; PWA surfaces it in Phase 98.
- Tier/gamification bonuses — deferred (Future Requirements).

</deferred>
