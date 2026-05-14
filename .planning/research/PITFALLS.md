# Pitfalls — v1.4 Cash Sales + PT Packages

**Domain:** Gym CRM — adding cash payment ledger + refund flow + trainer catalog + PT-package tariff + PT-session recording to a single-gym modular monolith already shipping memberships, freeze, renewal, expiring-soon notifications, and Telegram self check-in.
**Researched:** 2026-05-14
**Confidence:** HIGH (grounded in v1.2/v1.3 retrospective patterns: mandatory snapshot, anti-oracle DM, partial-unique on freeze, AST gate on `audit.emit`, SVC001 commit-gate, DB-level race-proof discipline)

## Phase code shorthand

- **FND** = Foundations bedrock (mirror v1.3 Phase 24 — audit pre-registration, RBAC extension, SVC001 walker scope, decision constants)
- **PAY** = Payment ledger backend (payments table, sale wiring, history endpoints)
- **REF** = Refund flow backend (refund mutation across memberships and PT-packages)
- **TRN** = Trainers catalog backend (CRUD, soft-delete semantics)
- **PTP** = PT-package tariff backend (plan_kind, PT-membership instance, snapshot symmetry)
- **PTS** = PT session recording backend (decrement, race-proof, cancellation, trainer attribution)
- **FE** = admin-web wiring (sale flow, refund button, /trainers, PT session UI, package detail)
- **VER** = Milestone verification (concurrent refund test, decrement race test, snapshot pricing test)

## Severity legend

- **HIGH** — will leak into v1.5+ (reports, reconciliation, audit log surface) and hurt forensically or financially. Must be addressed in bedrock or by feature-phase ship.
- **MEDIUM** — quality/UX hit, recoverable in a follow-up phase. Address by feature-phase ship.
- **LOW** — cosmetic or out-of-scope-for-v1.4-only. Flag for v1.5/v1.6.

---

## HIGH severity (must address in bedrock or by feature-phase ship)

### Pitfall H-01: Payment row not append-only (soft-delete or UPDATE allowed)

**Severity:** HIGH
**Phase:** FND (decision lock) + PAY (schema)
**What goes wrong:** A future quick-task lets reception "edit" a payment amount or soft-delete a wrong sale — financial history is no longer immutable. v1.5 reports become unauditable; refund forensics collapses.
**Why it happens:** Default project convention (clients/memberships) uses `SoftDeleteMixin`. Copy-paste momentum drags the mixin onto `payments`.
**Prevention:**
- Schema: `payments` table has NO `deleted_at`, NO `updated_at`. Only `created_at`. Document as Key Decision row (mirror "Membership `end_date` INCLUSIVE" precedent).
- Refund is a SEPARATE row (`payments.kind = 'refund'`, `amount_kopecks < 0` OR a dedicated `refunds` table referencing `payments.id`). Pick one and lock it.
- AST guard option: extend SVC001-style walker to forbid `UPDATE payments` / `DELETE FROM payments` in any service file.
- Code review checklist line: "`payments` is append-only. Refund = new row, not mutation."

### Pitfall H-02: Refund without a sale (reference integrity)

**Severity:** HIGH
**Phase:** PAY + REF
**What goes wrong:** Reception can "refund" a client who never paid (input bug or malicious). Audit log carries a phantom money-out row.
**Why it happens:** Refund endpoint takes `(client_id, amount)` directly instead of `(payment_id)`.
**Prevention:**
- Refund endpoint signature: `POST /api/v1/payments/{payment_id}/refund` — `payment_id` is REQUIRED and FK-validated in DB.
- FK: `refunds.payment_id` → `payments.id` `ON DELETE RESTRICT`.
- Service returns 404 `payment_not_found` if `payment_id` invalid (anti-oracle: same DM as cross-tenant lookup, but for single-gym v1.4 just 404).
- Integration test: refund with bogus UUID → 404.

### Pitfall H-03: Refund larger than original sale / double refund

**Severity:** HIGH
**Phase:** REF (DB constraint)
**What goes wrong:** Two reception clerks click "Refund" on the same payment concurrently → two refund rows, each ≤ original → total refunded > sale. Or reception types 5000 ₽ refund for a 3000 ₽ sale.
**Why it happens:** App-layer check on existing refunds with TOCTOU race; no DB constraint.
**Prevention:**
- DB-level: partial UNIQUE index on `refunds (payment_id) WHERE voided_at IS NULL` if refund is single-shot only (recommended for v1.4 — mirrors freeze `partial unique WHERE ended_at IS NULL`). The second concurrent refund loses with IntegrityError → service returns 409 `already_refunded`.
- Or: CHECK constraint at DB level on accumulated refund amount via trigger (more complex, NOT recommended for v1.4).
- Lock the simpler "all-or-nothing refund of full sale" policy — no partial refunds in v1.4. Pro-rata is a v1.5/v1.6 enhancement (record as Key Decision).
- Test: `REF-TEST-01` concurrent refund — real Postgres, mirrors `VIS-TEST-01` race test + freeze MEM-FRZ-TEST-03.

### Pitfall H-04: PT-package session decrement race

**Severity:** HIGH
**Phase:** PTS (DB constraint + atomic UPDATE)
**What goes wrong:** Two reception clerks record a PT session on the same `pt_membership` at the same moment. Both read `sessions_remaining = 1`, both write `sessions_remaining = 0` → one PT session recorded but only one decrement → over-spend.
**Why it happens:** App-layer "read then write" pattern; no atomic UPDATE; no DB CHECK.
**Prevention:**
- Atomic decrement: `UPDATE memberships SET sessions_remaining = sessions_remaining - 1 WHERE id = :id AND sessions_remaining > 0 AND status = 'active' RETURNING sessions_remaining`. If `rowcount == 0` → 409 `no_sessions_left`.
- DB CHECK constraint: `CHECK (sessions_remaining >= 0)` on the column. Second concurrent UPDATE attempts to go to -1, hits CHECK, IntegrityError → service returns 409.
- Both layers are defence-in-depth (atomic UPDATE alone is sufficient correctness; CHECK is forensic insurance for any future write path).
- Test: `PTS-TEST-01` concurrent decrement — real Postgres, two `asyncio.gather` clients on the same membership, expect exactly one success.

### Pitfall H-05: Refund of frozen membership — freeze period accounting breaks

**Severity:** HIGH
**Phase:** REF (cross-module decision)
**What goes wrong:** Refund cancels a membership that is currently `frozen`. The open `membership_freeze_periods` row stays `ended_at IS NULL` forever; the partial-unique index keeps blocking re-freezes of OTHER memberships? No (per-membership unique). But if the cancelled membership is later "un-cancelled" (impossible in v1.4) or queried by Phase 25 helpers, an inconsistent open freeze leaks.
**Why it happens:** Refund handler cancels but doesn't unwind freeze.
**Prevention:**
- Refund of a `frozen` membership MUST first unfreeze (set `ended_at = now()`, ceil-rounded day accounting per v1.3 MEM-FRZ-05) and THEN cancel. Two audit events emitted in order: `membership_unfrozen` then `membership_cancelled` then `payment_refunded` — symmetric to v1.3 "cancel-during-freeze" double-audit pattern (Phase 25 / D-25-?).
- Or: simpler — refund of a frozen membership is REJECTED with 409 `must_unfreeze_first` and UI forces the reception to click Unfreeze before Refund. Recommended for v1.4 (less code, harder to get wrong).
- Decision row in PROJECT.md required.
- Test: integration test refund-while-frozen → either 409 or two-audit-emit chain.

### Pitfall H-06: Refund of renewed membership orphans `previous_membership_id` chain

**Severity:** HIGH
**Phase:** REF (cross-module decision)
**What goes wrong:** Client buys membership A, renews to membership B (`B.previous_membership_id = A.id`). Reception refunds A. Now B.previous_membership_id points to a `cancelled` row. The renewal chain breaks for audit purposes; v1.5 reports show B with a phantom predecessor.
**Why it happens:** Refund mutation doesn't consider FK semantics of the renewal chain.
**Prevention:**
- Refund of a membership that has been RENEWED (i.e. another row has `previous_membership_id = this.id`) is REJECTED with 409 `cannot_refund_renewed_source`. Reception must refund B first, then A.
- Alternative: cascade-refund. Reject for v1.4 (too magical, irreversible in cash flow).
- Lock as Key Decision row.
- Test: integration test — sell A, renew to B, refund A → 409; refund B → 200, then refund A → 200.

### Pitfall H-07: Refund missing audit log row

**Severity:** HIGH
**Phase:** FND (pre-registration) + REF
**What goes wrong:** Refund commits to DB but audit log doesn't receive `payment_refunded` event — financial forensics blind spot. Mirrors the SVC001 commit-gate bug from v1.1 Phase 12.1.
**Why it happens:** New event name not in `LOCKED_AUDIT_EVENTS`; or service path forgets `await session.commit()` after `audit.emit`.
**Prevention:**
- Pre-register all v1.4 audit events in `LOCKED_AUDIT_EVENTS` frozenset BEFORE any callsite — mirror v1.3 Phase 24 INFRA-15 discipline. Events likely needed: `payment_recorded`, `payment_refunded`, `membership_sold` (if not already), `pt_membership_sold`, `pt_session_recorded`, `pt_session_cancelled`, `trainer_created`, `trainer_updated`, `trainer_deactivated`. Lock the exact list in FND.
- Bump `taxonomy_test` count from 34 → ~42 entries.
- Extend SVC001 AST commit-gate walker to `app/modules/payments/service.py` (or wherever refund lives) — `refund_payment` MUST explicitly `await session.commit()` after `audit.emit`.
- Audit payload schema: include `payment_id`, `payment_row_hash` (SHA-256 of canonical payment fields) for forensic trace; never PII like full client name.
- Test: every refund integration test asserts an `audit_log` row exists with `event='payment_refunded'`.

### Pitfall H-08: Trainer deletion breaks past PT session references

**Severity:** HIGH
**Phase:** TRN + PTS
**What goes wrong:** Owner hard-deletes a trainer who has 500 historical PT sessions. FK `pt_sessions.trainer_id` is gone → either CASCADE wipes history (DISASTER) or RESTRICT blocks deletion and owner is stuck.
**Why it happens:** Default `ON DELETE` choice not made consciously.
**Prevention:**
- Trainer has SoftDeleteMixin (`deleted_at`); `is_active BOOLEAN NOT NULL DEFAULT TRUE` for the deactivation toggle (separate from soft-delete).
- `pt_sessions.trainer_id` FK is `ON DELETE RESTRICT` so historical references are preserved.
- Owner UI offers "Deactivate" (sets `is_active=false`), not "Delete". Hard delete via API returns 409 `trainer_in_use` if any `pt_sessions` reference exists (mirrors v1.2 D-15 `plan_in_use` pattern).
- Past PT sessions render the trainer's name from a snapshot field `trainer_name_snapshot` on `pt_sessions` (mirror v1.2 mandatory snapshot pricing) — historical UI never breaks even if trainer row is deleted.
- Decision row: "Trainer snapshot on PT session, symmetric to plan snapshot on membership."

### Pitfall H-09: PT-package `session_count` mutability after sale

**Severity:** HIGH
**Phase:** PTP (schema decision)
**What goes wrong:** Owner edits plan's `session_count` from 10 to 5. Existing PT-package memberships sold at 10 sessions now show "5 sessions max" if UI reads from the plan instead of the snapshot. Or worse, decrement logic uses plan-side count and over-spends.
**Why it happens:** Snapshot discipline forgotten because PT-package is a "new feature."
**Prevention:**
- Mandatory snapshot pattern symmetric to v1.2 `duration_days_snapshot` / `price_kopecks_snapshot`: add `session_count_snapshot INT NOT NULL` on `memberships` (or new `pt_memberships` table — decision in PTP).
- `MembershipPlan.session_count` immutable post-creation (Postgres-level — mirror `duration_days` discipline; raise 409 `field_immutable` on PATCH).
- All decrement logic reads from `session_count_snapshot` and `sessions_remaining`, never from the plan row.
- Test: change plan session_count after sale, ensure existing PT-memberships unaffected.

### Pitfall H-10: Sale form double-submit creates two payments

**Severity:** HIGH
**Phase:** PAY + FE
**What goes wrong:** Reception clicks "Sell" twice rapidly (slow network, impatient finger). Two POST /sale requests → two memberships, two payments. Client is charged twice, has two overlapping memberships, audit confusion.
**Why it happens:** No idempotency key on POST; UI doesn't disable button.
**Prevention:**
- Frontend: disable submit button on first click; show spinner; re-enable only on response. RHF `formState.isSubmitting` is the standard pattern.
- Backend: idempotency key as `Idempotency-Key` header (UUID generated client-side per form submission). Backend stores `(idempotency_key, response_body, response_status)` in Redis with TTL 1h; replay returns cached response. Simpler v1.4-scoped alternative: per-client serialisation via `SELECT ... FOR UPDATE` of the client row inside the sale transaction (single-gym scale so contention is non-issue).
- Decision: pick one. Recommend `Idempotency-Key` header + Redis cache (mirrors auth refresh-rotation's Redis usage; trivial helper).
- Test: rapid double POST with same Idempotency-Key → second returns 200 with same `payment_id`, no second row in DB.

### Pitfall H-11: Anti-oracle leak in PT-package DM ("0 sessions" vs "no package")

**Severity:** HIGH
**Phase:** PTS + potentially bot extension (v1.5)
**What goes wrong:** If v1.4 ever exposes PT balance via Telegram bot (probably v1.5, but reception UI also matters): stranger queries balance, gets "Нет активного ПТ-пакета"; client with 0 sessions left gets "Осталось 0 занятий" — different DMs = oracle for account enumeration.
**Why it happens:** Forgetting v1.2 D-20-9 / v1.3 freeze-anti-oracle discipline.
**Prevention:**
- v1.4 likely keeps PT info admin-side only — no bot exposure → pitfall non-applicable. Lock as Out of Scope decision.
- If reception search by name leaks "client has 0 PT" vs "client has no PT" via different badges, that's intra-admin (acceptable — reception is trusted).
- Flag for v1.5: when PT balance hits Telegram, unify DM ("ПТ-пакет недоступен") across {no package, 0 sessions, expired, cancelled} states.

### Pitfall H-12: Cash drawer reconciliation total drifts from sum-of-payments

**Severity:** HIGH (forensically) / MEDIUM (operationally, v1.4 scope)
**Phase:** PAY (decision) + VER (smoke test)
**What goes wrong:** Owner closes day, counts cash drawer = 47,000 ₽; sums `payments WHERE created_at::date = today` = 52,000 ₽. Where's the 5,000 ₽? No reconciliation tool, no end-of-day close action.
**Why it happens:** Gym CRMs often skip this because "we'll do it manually." But the cash drawer (physical) and ledger (digital) drift silently — refund cash returned but app shows the original sale; cash sale recorded but money in wrong pocket.
**Prevention:**
- v1.4 scope: a simple `GET /api/v1/payments?from=YYYY-MM-DD&to=YYYY-MM-DD` endpoint that returns daily total (already implied by history feature).
- Decision row: NO end-of-day close action in v1.4. Owner reconciles manually. Reports phase v1.5 owns reconciliation UI.
- Flag for v1.5: add `daily_totals` precomputed view + admin UI showing "Today: 52,000 ₽ across 14 payments".

### Pitfall H-13: Refund UI single-click footgun

**Severity:** HIGH (UX irreversibility)
**Phase:** FE
**What goes wrong:** Reception clicks "Refund" on wrong client's payment row. Money is "out" of ledger (real cash is back in drawer, but record says refunded). Client comes in the next day, walks in with valid membership, app says cancelled.
**Why it happens:** Refund presented as button next to "Sell" with no friction.
**Prevention:**
- Refund button opens AlertDialog with: full client name, full payment amount via `formatMoney`, payment date, original membership type. Reception must type the client's last name OR explicitly check a "I confirm" box before the "Refund" button enables. (Mirror v1.3 RenewConfirmDialog pattern, but higher friction.)
- Hide refund button on payments older than N days (e.g. 30) — owner-only beyond that. Decision: same-day refund reception-driven; >24h refund owner-only. Lock in FND.
- Test: admin-web vitest for the dialog states + RBAC test for >24h gating.

### Pitfall H-14: Audit event payload missing payment hash for forensic trace

**Severity:** HIGH
**Phase:** FND (locked schema) + PAY/REF
**What goes wrong:** v1.5 audit log surface shows `event=payment_refunded` but the payload only has `payment_id`. Six months later the `payments` row hash is unknown — forensic chain-of-custody broken if a payment row is somehow rewritten (it shouldn't, per H-01, but defence in depth).
**Why it happens:** Payload schema is "obvious" so under-specified.
**Prevention:**
- Lock canonical payload schemas in FND for each new event. `payment_refunded` payload: `{payment_id: UUID, payment_row_hash: hex, refund_amount_kopecks: int, membership_id?: UUID, pt_membership_id?: UUID, actor_user_id: UUID, idempotency_key?: str}`.
- `payment_row_hash` = SHA-256 of canonical-JSON of payment fields (id, amount_kopecks, client_id, created_at, recorded_by, kind). Helper in `app/core/audit.py`.
- Test: integration test asserts payload shape via JSON schema or Pydantic model.

---

## MEDIUM severity (address by feature-phase ship)

### Pitfall M-01: Floating-point money leak at boundary

**Severity:** MEDIUM
**Phase:** PAY + FE
**What goes wrong:** Backend stays integer kopecks. Frontend `MoneyField` accepts decimal rubles "500.50" → parseFloat → 500.5 → ×100 → 50049.9999 → round → 50050 OR 50049 depending on rounding. Off-by-one kopeck on certain inputs.
**Why it happens:** JS Number is float64; multiplication by 100 of `500.50` yields `50049.99999999999`.
**Prevention:**
- Use the existing `formatMoney` for display ONLY. For parsing, use string-based parser that splits on `,` or `.`, takes max 2 fractional digits, parses each side as integer: `rub * 100 + kop`. Co-locate helper in `shared/lib/money.ts` with vitest covering inputs: `"500"`, `"500.5"`, `"500,50"`, `"500.50"`, `"500.500"` (reject), `"500,5"`, `""`, `" 500 ,50 "`, negative inputs (reject).
- Backend: Pydantic `amount_kopecks: int` (already enforced by camelCase wire); never accept `amount_rub: float`.
- ESLint rule (optional): forbid `Math.round` / `parseFloat` on money fields by lint code path comment.

### Pitfall M-02: Sale + payment two-step instead of single transaction

**Severity:** MEDIUM
**Phase:** PAY
**What goes wrong:** Service flow does `create_membership()` → commit → `create_payment()` → commit. If second commit fails (network blip, Postgres timeout) → membership exists, payment missing → reception confused, manual fix needed.
**Why it happens:** Two separate service-layer methods, each owning a transaction.
**Prevention:**
- Single service method `sell_membership(client_id, plan_id, payment_amount, idempotency_key)` opens ONE transaction, creates both membership and payment rows, emits both audit events, commits once. Caller-owns-txn pattern from v1.3 freeze applies here.
- SVC001 AST walker enforces single `await session.commit()` in the method.
- Test: kill DB connection between membership-insert and payment-insert (mocked) → both must rollback.

### Pitfall M-03: PT-package and duration plan unified into one table — column sparseness

**Severity:** MEDIUM
**Phase:** PTP (schema decision)
**What goes wrong:** Two design options: (a) extend `memberships` table with `kind`, `sessions_remaining`, `session_count_snapshot` columns NULLABLE for non-PT rows; (b) separate `pt_memberships` table. Option (a) wins on simplicity but creates "column always NULL for half of rows" sparseness — and the resolver, freeze, renewal helpers all need `WHERE kind = ...` clauses.
**Why it happens:** "We already have `memberships`, just add columns" momentum.
**Prevention:**
- Recommended: option (a) with explicit `kind` enum column (`'duration' | 'pt_package'`); CHECK constraint enforces "`sessions_remaining IS NOT NULL` IFF `kind = 'pt_package'`" and "`end_date IS NOT NULL` IFF `kind = 'duration'`" (or both, depending on PT expiry decision — see M-04). Single resolver, single freeze table, single renewal logic with `kind`-aware branching.
- Or option (b) if expiry semantics diverge meaningfully. Lock as Key Decision.
- Test: CHECK constraint test for cross-kind invariants.

### Pitfall M-04: PT-package expiry by date — out of scope vs cron decision

**Severity:** MEDIUM
**Phase:** PTP (decision)
**What goes wrong:** PT-packages never expire by date → clients hoard sessions forever, gym economics suffer. OR PT-packages expire by date → need a 3rd cron job, decision on what happens to remaining sessions (forfeit? refund? roll over?).
**Why it happens:** Gym economics question that engineering can't decide alone.
**Prevention:**
- Lock decision in FND. Recommendation for v1.4: NO date-based expiry on PT-packages (sessions_remaining is the only termination). Document explicitly.
- If owner wants expiry later, add `pt_membership_end_date` column + cron at 06:25 Europe/Moscow (10-min buffer after expire_memberships at 06:05 and send_expiring at 06:15) — mirror v1.3 cron ordering discipline.
- Decision row required.

### Pitfall M-05: PT-package shared between family members

**Severity:** MEDIUM (foot-gun)
**Phase:** PTP + PTS (decision)
**What goes wrong:** Mother and daughter want to share a 10-session PT-package. Reception fudges it by recording sessions under the mother's name regardless. Audit log lies; trainer attribution wrong; v1.5 reports per-client false.
**Why it happens:** Single-gym pet-project flexibility temptation.
**Prevention:**
- Lock decision: PT-packages are PER-CLIENT, no sharing. Document in PROJECT.md + i18n label.
- If owner pushes for family sharing in v1.5+, model as a "linked client group" concept — out of scope for v1.4.
- UI: PT session form requires `client_id` from the PT-package's owner — no override.

### Pitfall M-06: PT session backdating

**Severity:** MEDIUM
**Phase:** PTS (decision)
**What goes wrong:** Trainer comes in Friday and says "we did sessions Mon/Tue/Wed for client X". Reception records 3 sessions. What `recorded_at` do they get? If `now()`, audit log lies. If reception types a date, it's mutable and accusation-vulnerable.
**Why it happens:** Real-world ops sometimes need backdating.
**Prevention:**
- v1.4 lock: PT session `occurred_at` defaults to `now()` and is reception-editable within a small window (e.g. last 7 days) at recording time only — never edited after. Audit payload always includes both `recorded_at` (server clock) and `occurred_at` (user-asserted). 
- Owner-only flag for back-dating beyond 7 days; reject for reception with 422.
- Decision row.
- Test: PTS-TEST-02 backdating range + audit emission.

### Pitfall M-07: PT session cancellation flow (trainer no-show)

**Severity:** MEDIUM
**Phase:** PTS (decision)
**What goes wrong:** Trainer doesn't show up → recorded PT session is wrong. How does balance get restored? Manual SQL? Refund the package?
**Why it happens:** Not pre-designed.
**Prevention:**
- Add `cancel_pt_session` endpoint: marks `pt_session.cancelled_at = now()`, increments `sessions_remaining` atomically (`UPDATE memberships SET sessions_remaining = sessions_remaining + 1 WHERE id = :pt_membership_id`). Emits `pt_session_cancelled` audit event.
- Reception-allowed within 24h of recording; owner-allowed always. Same friction as refund (AlertDialog).
- Test: PTS-TEST-03 cancel → balance restored.

### Pitfall M-08: Visit vs PT session confusion in reception UI

**Severity:** MEDIUM (UX)
**Phase:** FE
**What goes wrong:** Reception confuses "check-in" (visits — gym door entry) with "record PT session" (PT-package decrement). Wrong action chosen; PT balance corrupted or visit missed.
**Why it happens:** Both are reception-driven, "client is here" feels similar.
**Prevention:**
- UI: PT session recording lives on the membership detail page (`/memberships/$id` for PT-package memberships), not on the main `/visits` route. Clear visual separation; different icons; different button colours.
- Reception trains on flow once; locked Russian i18n strings differentiate ("Отметить визит" vs "Зафиксировать ПТ-занятие").
- Avoid auto-decrement on visit even if client has only a PT-package — reception must explicitly record both if both happened.
- Decision row.

### Pitfall M-09: Freeze applies to PT-package — UI gating

**Severity:** MEDIUM (UX)
**Phase:** PTP + FE
**What goes wrong:** PT-package has no `end_date` (per M-04 decision) so freezing is meaningless. UI on PT-package detail shows the FreezeSection from v1.3, reception tries to freeze → 400.
**Why it happens:** Detail route is shared between duration and PT memberships.
**Prevention:**
- Backend: freeze endpoint rejects PT-package memberships with 409 `freeze_not_applicable` (CHECK at service layer: `if membership.kind == 'pt_package': raise ...`).
- Frontend: FreezeSection is conditionally rendered based on `membership.kind === 'duration'`. PT-package detail shows a `PtBalanceSection` + `PtHistorySection` instead.
- Test: integration test PT-membership freeze attempt → 409.

### Pitfall M-10: Renewal of PT-package — chain semantics

**Severity:** MEDIUM
**Phase:** PTP (decision)
**What goes wrong:** Client buys 10-session PT, uses 7, wants to "renew" with another 10-session pack. Does `previous_membership_id` apply? Does it carry over 3 remaining sessions? Does it spawn a new pt_membership and leave old at sessions_remaining=3?
**Why it happens:** v1.3 renewal was duration-only; PT semantics not designed.
**Prevention:**
- v1.4 lock: PT-package renewal is a NEW sale with NEW pt_membership row. `previous_membership_id` is set (chain audit) but remaining sessions on the old membership are NOT carried over (they remain accessible until used or the old membership is voluntarily cancelled).
- Reception sees both PT-memberships on the client detail (both active, both with their own balance).
- Decision row. Documented as user-visible behaviour.
- Alternative if owner wants roll-over: postpone to v1.5. Out of Scope for v1.4.

### Pitfall M-11: New audit events not pre-registered before callsites

**Severity:** MEDIUM
**Phase:** FND
**What goes wrong:** PAY phase lands `audit.emit("payment_recorded", ...)` but FND didn't add `"payment_recorded"` to `LOCKED_AUDIT_EVENTS` first — AST gate fails CI, phase blocked.
**Why it happens:** Forgetting the v1.3 INFRA-15 discipline.
**Prevention:**
- FND phase explicitly lists ALL v1.4 audit events upfront and updates `LOCKED_AUDIT_EVENTS` frozenset + `taxonomy_test` count in a single commit BEFORE any callsite lands.
- Pre-flight checklist item in roadmap.

### Pitfall M-12: Reception permission breadth — viewing all payment history

**Severity:** MEDIUM
**Phase:** FND (RBAC) + PAY
**What goes wrong:** Reception can list every payment ever, including owner's discretionary cash flows; owner privacy nil.
**Why it happens:** Default "list endpoint open to everyone with the role" mistake.
**Prevention:**
- `GET /api/v1/payments?client_id=X` — reception sees per-client history (their working surface). 
- `GET /api/v1/payments?from=...&to=...` (global daily/range list) — owner-only (`OWNER_ONLY` += `(LIST, PAYMENTS)` where LIST is a new Action or reuse VIEW).
- Reception sees own daily total only (`?recorded_by=me`) — useful for end-of-shift handover.
- Lock RBAC matrix in FND; mirror byte-paritet test (backend ↔ admin-web `can.ts` ↔ `registry.ts`).
- Test: three-way parity test extended; integration test for reception `GET ?from=...` → 403.

### Pitfall M-13: Trainer phone field — uniqueness

**Severity:** MEDIUM
**Phase:** TRN (schema decision)
**What goes wrong:** UNIQUE on `trainers.phone` blocks two trainers without phone (NULL collision varies by Postgres) or worse, prevents legitimately phoneless trainer entries.
**Why it happens:** Copy-paste from clients schema (which has partial unique on phone WHERE deleted_at IS NULL).
**Prevention:**
- `trainers.phone TEXT NULL` (optional, per requirement). No uniqueness constraint at all (trainers are small — 5-20 in a gym — duplicates manageable manually).
- E.164 validation if provided (reuse `clients` Pydantic validator).
- Decision row: "Trainer phone is non-unique, optional, E.164-validated when present."

### Pitfall M-14: Trainer dropdown pagination

**Severity:** LOW (single-gym scale) → folded to MEDIUM because of UX
**Phase:** FE
**What goes wrong:** PT session form Trainer select is built as `Select` with all options — for 200-trainer chain this breaks. For 20-trainer gym it's fine but the temptation to use `Combobox` with search is real.
**Why it happens:** Premature optimisation OR forgetting scale.
**Prevention:**
- For v1.4: plain `Select` listing active trainers ordered by `name ASC`. No search needed (single-gym ≤20 trainers).
- Test for >20 list works visually; if v1.5 grows, swap to Combobox.

---

## LOW severity (cosmetic or flag for v1.5+)

### Pitfall L-01: Expiring-PT-sessions notification for "low remaining sessions"

**Severity:** LOW
**Phase:** flag for v1.5
**What goes wrong:** PT-package owner doesn't know they're running out (e.g. 1 session left). Comes in, surprised.
**Why it happens:** Out of v1.4 scope; v1.3 only notifies duration memberships.
**Prevention:** Flag in PROJECT.md "Long-term" as v1.5 candidate: extend `send_expiring_notifications` to also enqueue when `kind='pt_package' AND sessions_remaining IN (1, 3)`. Reuse idempotency table with new `kind` values (`pt_sessions_3`, `pt_sessions_1`).

### Pitfall L-02: Daily total endpoint cache headers

**Severity:** LOW
**Phase:** PAY (minor)
**What goes wrong:** `GET /payments?from=today&to=today` returns daily total; refreshing every 30s on `staleTime: 30_000` is fine. No real issue.
**Prevention:** None needed — default TanStack Query settings work.

### Pitfall L-03: Refund audit event copy

**Severity:** LOW
**Phase:** FE (i18n)
**What goes wrong:** Locked Russian string for refund DM/UI might need owner sign-off if shown to clients. v1.4 likely doesn't show refund to clients (admin-only).
**Prevention:** Confirm with owner: refund is internal-only in v1.4. No Telegram DM. Skip the locked-copy ceremony unless surface emerges.

### Pitfall L-04: PT session "trainer no-longer-active" rendering

**Severity:** LOW
**Phase:** FE
**What goes wrong:** Past PT session shows deactivated trainer's name — UI looks "off" without a badge.
**Prevention:** Render trainer name with `(уволен)` suffix if `is_active=false`. Minor i18n addition.

---

## Integration pitfalls with v1.3 features

### I-01: Resolver `kind`-awareness

**Severity:** HIGH
**Phase:** PTP
`resolve_active_membership_by_client` currently returns "the duration membership for check-in." With PT-packages, the resolver semantics fork. For DOOR check-in (visits, bot `/checkin`), PT-package alone should NOT grant entry — only a duration membership does (or owner decision: PT-only client CAN enter? lock decision).

**Prevention:** Resolver filter `WHERE kind = 'duration'` for check-in path; new helper `resolve_active_pt_membership_by_client` for PT session recording. Both use the same status semantics. Decision row required: "Does PT-package alone grant gym entry?" Most likely yes (PT-package implies physical presence), so resolver returns either duration OR pt_package row with `kind` tag, and check-in accepts both. Lock and test.

### I-02: Freeze button gating on PT-package detail

**Severity:** MEDIUM (see M-09)
Already covered.

### I-03: Renewal chain on PT (see M-10)

**Severity:** MEDIUM
Already covered.

### I-04: ARQ cron job ordering for PT expiry (if implemented)

**Severity:** MEDIUM (only if M-04 decides PT expires by date)
**Phase:** PTP cron (deferred recommended)
If owner insists on PT expiry: schedule `expire_pt_memberships` at 06:25 Europe/Moscow (10-min buffer after `send_expiring_notifications` at 06:15). Mirror v1.3 cron-ordering discipline. `unique=True, keep_result=60`.

### I-05: Expiring-soon notification schema reuse

**Severity:** LOW (v1.5)
`membership_notifications.kind` is currently `{'expiring_7d', 'expiring_3d', 'expiring_1d'}`. Adding PT-flavours (`pt_sessions_3`, `pt_sessions_1`) requires either extending the CHECK constraint or moving to a separate table. Flag for v1.5.

### I-06: OpenAPI drift gate refresh

**Severity:** HIGH
**Phase:** FE phase (mirror v1.3 Phase 28)
Every new endpoint (POST /payments, POST /payments/{id}/refund, GET /payments, /trainers CRUD, POST /pt-sessions, etc.) MUST land before the OpenAPI regen so the byte-stable drift gate passes. Mirror v1.3 Phase 28 single-atomic-regen discipline.

### I-07: Three-way RBAC parity test

**Severity:** HIGH
**Phase:** FND
Every new (Action, Resource) pair added to backend `OWNER_ONLY` MUST also exist in admin-web `can.ts` `OWNER_ONLY`. The byte-paritet test catches drift. Pre-register v1.4 RBAC entries in FND.

---

## Prevention strategy summary (by mechanism)

### DB constraints (Postgres-level, race-proof)

| Constraint | What it prevents | Phase |
|---|---|---|
| `refunds (payment_id) PARTIAL UNIQUE WHERE voided_at IS NULL` | Double-refund of same payment (H-03) | REF |
| `CHECK (sessions_remaining >= 0)` on PT-memberships | Negative balance via decrement race (H-04) | PTS |
| `payments` table has NO `deleted_at`, NO `updated_at` columns | Append-only ledger (H-01) | PAY |
| `pt_sessions.trainer_id ON DELETE RESTRICT` | Orphaned PT-session history (H-08) | TRN/PTS |
| `payments.payment_id` FK to `memberships.id ON DELETE RESTRICT` | Phantom refunds (H-02) | PAY |
| `MembershipPlan.session_count` immutable post-creation (app-layer 409 + Alembic comment) | Snapshot integrity (H-09) | PTP |
| CHECK invariant `kind='pt_package' IFF sessions_remaining IS NOT NULL` | Schema sparseness coherence (M-03) | PTP |

### Integration tests (real Postgres, race-proof)

| Test | Mirrors | Phase |
|---|---|---|
| `REF-TEST-01` concurrent refund — two clients refunding same payment, exactly one wins | `VIS-TEST-01`, `MEM-FRZ-TEST-03` | REF + VER |
| `PTS-TEST-01` concurrent PT session decrement — two clients, balance=1, exactly one succeeds | `VIS-TEST-01` | PTS + VER |
| `PAY-TEST-01` snapshot pricing — change plan price between sale and refund, refund amount uses snapshot | v1.3 MEM-REN-TEST snapshot | PAY/REF |
| `AUDIT-TEST-01` every financial event emits an audit row with locked payload schema | v1.3 audit emit tests | FND/PAY/REF |
| `PTS-TEST-02` backdating range enforcement | new | PTS |
| `PTS-TEST-03` cancel PT session restores balance atomically | new | PTS |

### AST guards (CI-level, defence-in-depth)

| Guard | What it prevents | Phase |
|---|---|---|
| `LOCKED_AUDIT_EVENTS` frozenset extended +8 entries BEFORE callsites; `audit.emit` literal-string AST gate | Ad-hoc audit strings; missing event names (H-07, M-11) | FND |
| SVC001 commit-gate walker extended to `app/modules/payments/service.py` | Missing `await session.commit()` after `audit.emit` (H-07 reprise of Phase 12.1) | FND |
| (Optional) AST walker forbidding `UPDATE/DELETE payments` in any service file | Mutable ledger (H-01) | FND |

### UI affordances (admin-web)

| Affordance | What it prevents | Phase |
|---|---|---|
| Refund AlertDialog requires explicit confirm + shows formatMoney + client name + date | Wrong-client refund (H-13) | FE |
| Sell button disabled during in-flight submit; `Idempotency-Key` header on POST | Double-sale (H-10) | FE/PAY |
| FreezeSection conditionally rendered for `kind='duration'` only | Inapplicable freeze on PT (M-09) | FE |
| Trainer name suffixed `(уволен)` if `is_active=false` | Past session UI clarity (L-04) | FE |
| PT session recording lives on `/memberships/$id` detail page, separate icon/copy from `/visits` | Visit/PT confusion (M-08) | FE |
| Money parser is string-based, not parseFloat-based; vitest covers locale separator and trailing zeros | Kopeck off-by-one (M-01) | FE |
| Daily payment list endpoint UI is owner-only; reception sees per-client history only | RBAC scope (M-12) | FE |

### Audit pre-registration (FND-phase checklist)

Before any callsite lands in PAY/REF/TRN/PTP/PTS:

- [ ] Add `LOCKED_AUDIT_EVENTS` += `{'payment_recorded', 'payment_refunded', 'pt_membership_sold', 'pt_session_recorded', 'pt_session_cancelled', 'trainer_created', 'trainer_updated', 'trainer_deactivated'}` (exact list TBD with owner; lock in FND)
- [ ] Bump `taxonomy_test` count 34 → 42
- [ ] Lock canonical payload schemas (especially `payment_refunded` carrying `payment_row_hash`)
- [ ] Extend `OWNER_ONLY` frozenset with: `(LIST, PAYMENTS)` global; `(CREATE, TRAINERS)`, `(UPDATE, TRAINERS)`, `(DELETE, TRAINERS)`; possibly `(REFUND, PAYMENTS)` if granular (or reuse CANCEL)
- [ ] Add three-way parity test entries to admin-web `can.ts` + `registry.ts`
- [ ] Extend SVC001 AST commit-gate walker scope to new service files
- [ ] Lock decision rows: append-only ledger; full-refund-only (no partial); PT-package no date expiry; PT renewal does NOT carry over remaining sessions; trainer snapshot on PT session; freeze rejects PT-package with 409; refund-of-frozen rejects with 409 (or unwinds, pick one); refund-of-renewed-source rejects with 409
- [ ] Pre-register RBAC entries (mirrors v1.3 Phase 24)

### Decision rows required in PROJECT.md (Key Decisions table)

1. Payments table is append-only — no soft-delete, no UPDATE. Refund is a new row.
2. Refund is all-or-nothing on the full original sale; no partial refunds in v1.4.
3. PT-packages have NO date expiry in v1.4 — only sessions_remaining termination.
4. PT-package renewal does NOT carry remaining sessions to new pt_membership.
5. Trainer snapshot on PT session (mirror v1.2 plan snapshot on membership).
6. Trainer phone non-unique, optional, E.164 when present.
7. Refund of frozen membership → 409 `must_unfreeze_first` (or auto-unwind — pick).
8. Refund of renewed-source membership → 409 `cannot_refund_renewed_source`.
9. PT-package alone {grants / does not grant} gym entry — owner decision.
10. PT session backdating window: 7 days reception, unlimited owner.
11. Cancellation of recorded PT session: 24h reception, anytime owner; restores balance atomically.
12. Refund permission: same-day reception; >24h owner-only.

---

*Output written by `gsd-new-milestone` research phase for v1.4 — Cash Sales + PT Packages. Mirrors v1.2/v1.3 patterns (mandatory snapshot, anti-oracle DM, partial-unique on race-prone rows, AST gate on `audit.emit`, SVC001 commit-gate, DB-level race-proof discipline). Roadmapper consumes this to allocate FND-phase prevention work and surface decision rows for `/gsd-discuss-phase`.*
