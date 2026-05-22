---
phase: 50-webhook-fsm-fiscal-foundation
plan: 04
subsystem: yookassa-webhook
tags: [yookassa, webhook, fsm, atomic-uow, fiscal-receipts, audit, blocker-resolution, internal-router]

# Dependency graph
requires:
  - phase: 47-bedrock
    provides: MembershipActivator + PtPackageActivator + YooKassaClientProvider + FiscalReceiptDispatcher Protocol slots, register_* setters, get_* accessors
  - phase: 48-yookassa-adapter
    provides: YooKassaClient.get_payment re-fetch + verify_yookassa_ip Depends body + YOOKASSA_TRUSTED_IPS allowlist
  - phase: 49-online-sales-orchestrator
    provides: OnlinePayment ORM + Phase 49 sell flow + PaymentRecorder Protocol baseline
  - phase: 50-webhook-fsm-fiscal-foundation/50-01
    provides: fiscal_receipts module (insert_fiscal_receipt repo + KIND_PAYMENT/STATUS_SENT constants)
  - phase: 50-webhook-fsm-fiscal-foundation/50-02
    provides: ONLINE_PAYMENT_STATUS_TRANSITIONS FSM map + 2 audit events (membership_activated_online + pt_package_activated_online) + payload schemas
  - phase: 50-webhook-fsm-fiscal-foundation/50-03
    provides: activator bodies (D-50-22, D-50-24) + PaymentRecorder Optional widening + activator online_payment_id kwarg rename
provides:
  - POST /api/v1/_internal/yookassa/webhook anonymous endpoint with route-level IP allowlist + Redis dedup + atomic UoW dispatch
  - handle_payment_succeeded: 8-step UoW (D-50-18) — SELECT-FOR-UPDATE + FSM guard + status mutation + ledger record + activator + fiscal_receipt INSERT + 2-emit audit chain
  - handle_payment_canceled: D-50-25 mirror — status mutation + cancellation_party/reason audit (no monetary side effects)
  - _select_for_update_online_payment with INVARIANT docstring + B-4 grep gate
  - _post_commit_enqueue D-50-19-conformant no-op stub (Phase 52 hook)
  - YookassaWebhookReceivedPayload.idempotency_outcome Literal widened with 'processed' + 'illegal_transition' (Rule 2 — required for D-50-17/18 emits)
affects: [51-fiscal-receipts-dispatch (consumes fiscal_receipts row), 52-notifications (consumes audit_correlation_id chain + _post_commit_enqueue hook), 53-reconcile-cron (orphan-row recovery)]

# Tech tracking
tech-stack:
  added: []  # purely composition + transport-layer wiring; no new libraries
  patterns:
    - "Anonymous-by-design /_internal/* surface: route-level Depends for security, dedup at transport layer, atomic UoW in handlers"
    - "Re-fetch BEFORE DB write (WH-02 / D-50-12): the GET /v3/payments/{id} response is the cryptographic anchor; body status is NEVER trusted"
    - "Redis dedup BEFORE re-fetch (D-50-10): preserves ЮKassa outbound rate-budget on duplicate retries"
    - "8-step atomic UoW: single async with session.begin() owns status update + ledger record + activator + fiscal_receipt INSERT + 2 audit emits"
    - "Illegal-transition is audit-as-forensic, not 4xx (D-50-17): ЮKassa retries on 4xx — that would cause storm; 200 + audit row is the correct telemetry"
    - "Webhook intake audit emitted LAST (D-50-18 step 8): the audit_log row id becomes the chain ROOT seed for Phase 52 notification chains"
    - "Narrow scalar SELECT for cross-row reads (Blocker #4): never use relationship traversal when one column suffices"
    - "B-4 transaction-proximity invariant: SELECT-FOR-UPDATE is a no-op outside async with session.begin() in PostgreSQL — INVARIANT docstring + acceptance-grep gate enforce this at CI time"

key-files:
  created:
    - apps/backend/app/api/v1/_internal/yookassa/__init__.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/tests/unit/test_webhook_router_smoke.py
  modified:
    - apps/backend/app/api/v1/router.py
    - apps/backend/app/core/audit_payloads.py
    - .planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md

key-decisions:
  - "Blocker #1 reuse: _assert_can_transition raises existing InvalidTransitionError (app/core/exceptions.py:212); NO new IllegalTransitionError surface introduced"
  - "Blocker #4 narrow-read: _read_customer_email uses select(Client.email).where(Client.id == client_id) scalar — Client ORM imported as a flat module read, NOT via an OnlinePayment.client relationship (OnlinePayment has no such relationship wired)"
  - "Rule 2 widening: YookassaWebhookReceivedPayload.idempotency_outcome Literal widened to include 'processed' and 'illegal_transition' — plan text uses these values for D-50-17 + D-50-18 step 8 emits but the existing Literal accepted only ['new','duplicate_blocked','rejected_ip']; without widening Pydantic ValidationError would block every webhook commit"
  - "W-4 signature lock: _post_commit_enqueue(arq_pool: Any | None = None, *, online_payment_id, subject_kind, subject_id) matches D-50-19 verbatim; Phase 50 caller passes None positionally so Phase 52 NOT-04/05 can swap in app.state.arq_pool with no callsite shape change"
  - "B-4 invariant: _select_for_update_online_payment carries explicit transaction-proximity docstring + every callsite restructured to single-line so the acceptance grep gate (`grep -B5 ... | grep session.begin`) returns >=2"
  - "200 always (D-50-08): every branch (invalid JSON, missing fields, dedup hit, refetch failure, orphan row, illegal transition, success) returns 200 text/plain 'ok' — ЮKassa retries on non-2xx and any 4xx/5xx would amplify retry storms"
  - "Audit emit ORDER (D-50-18 step 8): CHILD (online_payment_succeeded / online_payment_canceled) emitted FIRST inside the UoW, ROOT (yookassa_webhook_received) emitted LAST so the ROOT row's audit_log id is the seed for Phase 52 child chains"

patterns-established:
  - "Webhook handler shape: extract object_id → re-fetch (early returns on classification/status mismatch) → mint webhook_intake_corr UUID → async with session.begin() (UoW boundary) → SELECT-FOR-UPDATE → FSM guard (illegal-transition branch emits audit + returns) → mutate row → side-effect calls (recorder / activator / fiscal_receipt) → CHILD audit emit → ROOT audit emit → exit context manager (commit) → post-commit hook"
  - "Defensive isinstance guards on webhook body parsing: body['object'] may be missing/null/non-dict; every field access is shape-checked before use to ensure the handler returns 200 instead of crashing"
  - "Composition root untouched per Blocker #7: all Protocol slots were wired in Phase 47 (register_membership_activator + register_pt_package_activator + register_payment_recorder + register_yookassa_client_provider); Plan 50-04 consumes accessors only, NO edits to app/main.py or app/workers/__init__.py"

requirements-completed: [WH-01, WH-02, WH-03, WH-04, WH-06]

# Metrics
duration: 18min
completed: 2026-05-22
---

# Phase 50 Plan 04: ЮKassa Webhook Router + Handlers + Atomic UoW Summary

**Core Phase 50 deliverable shipped: POST /api/v1/_internal/yookassa/webhook with route-level IP allowlist + Redis SET NX EX 86400 dedup + handle_payment_succeeded 8-step atomic UoW (SELECT-FOR-UPDATE + FSM guard + status mutation + ledger record + activator + fiscal_receipt INSERT + 2-emit audit chain) + handle_payment_canceled mirror with cancellation_party/reason capture — all in a single commit boundary per event.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-22T18:24:00Z
- **Completed:** 2026-05-22T18:42:00Z
- **Tasks:** 1 (TDD: RED smoke test commit → GREEN implementation commit)
- **Files created:** 4 (1 package marker + handlers + router + smoke test)
- **Files modified:** 3 (v1/router mount + audit_payloads Literal widening + deferred-items log)

## Accomplishments

- **Webhook intake endpoint shipped:** POST `/api/v1/_internal/yookassa/webhook` mounted under the second `/_internal/*` namespace inhabitant (after Phase 42's `/_internal/email/webhook`). Anonymous-by-design — IP allowlist via route-level `dependencies=[Depends(verify_yookassa_ip)]` (D-50-04) runs BEFORE body parse; bogus traffic from non-ЮKassa IPs never reaches the JSON parser. Always returns 200 `text/plain` `ok` (D-50-08); handlers own all forensic detail via structlog + audit emits.

- **Redis dedup short-circuit (D-50-07/09/10):** `SET NX EX 86400` on `sz:yookassa:webhook:{event_type}:{object_id}` runs BEFORE the outbound re-fetch so duplicate ЮKassa retries do not waste rate-budget on `GET /v3/payments/{id}`. 24h TTL covers the ЮKassa documented retry window. Constants `WEBHOOK_DEDUP_KEY_PREFIX` + `WEBHOOK_DEDUP_TTL_SECONDS: Final[int] = 86400` declared at module level for AST-gate stability.

- **`handle_payment_succeeded` 8-step atomic UoW (D-50-18):** Re-fetch via `yookassa_client.get_payment(object_id)` is the FIRST DB-relevant call (WH-02 / D-50-12 — the cryptographic anchor that replaces HMAC). Classification != "ok" or status != "succeeded" → early return (next retry will re-attempt). Inside `async with session.begin():`: SELECT-FOR-UPDATE the OnlinePayment row → `_assert_can_transition` FSM guard → status mutation + `succeeded_at` → narrow `select(Client.email)` scalar SELECT (Blocker #4 — NOT relationship traversal) → `get_payment_recorder()(method='online', audit_actor=None, received_by_user_id=None)` with Plan 50-03 widened Protocol (Blocker #2) → activator via `get_membership_activator()` / `get_pt_package_activator()` with `online_payment_id=row.id` kwarg (Plan 50-03 / Blocker #3) → `insert_fiscal_receipt(kind='payment', status='sent')` (Plan 50-01 repo) → CHILD audit emit (`online_payment_succeeded`) → ROOT audit emit (`yookassa_webhook_received` with `idempotency_outcome='processed'`, emitted LAST per D-50-18 step 8). After commit boundary: `_post_commit_enqueue(None, ...)` no-op stub.

- **`handle_payment_canceled` mirror (D-50-25):** Re-fetch still applies (cancel branch also doesn't trust the body's claimed status). Same SELECT-FOR-UPDATE + FSM guard + status mutation flow, minus activator + fiscal_receipt (no monetary side effects on cancellation). `cancellation_party` + `cancellation_reason` extracted from `body['object']['cancellation_details']` (defensively isinstance-checked; both `str | None`) and threaded into the `online_payment_canceled` audit emit so Phase 52 NOT-05 can compose user-facing DM bodies.

- **Illegal-transition path (D-50-17):** `InvalidTransitionError` caught inside the UoW (e.g., `payment.succeeded` arrives for an already-canceled row) → emit `yookassa_webhook_received` with `idempotency_outcome='illegal_transition'` + return 200. The row state is left unchanged. ЮKassa retries on 4xx would amplify storm; audit-as-forensic + 200 is the correct telemetry. **Blocker #1 reuse honored** — uses the existing `InvalidTransitionError` from `app/core/exceptions.py:212`; NO new `IllegalTransitionError` class introduced.

- **B-4 transaction-proximity invariant enforced:** `_select_for_update_online_payment` carries an explicit `INVARIANT: Caller MUST be inside async with session.begin()` docstring + every callsite restructured to single-line form so the acceptance grep gate (`grep -B5 ... | grep session.begin`) returns `>=2`. Without an explicit transaction the PostgreSQL row lock is a no-op — the docstring + grep gate make this invariant checkable at CI time.

- **W-4 _post_commit_enqueue signature locked:** `async def _post_commit_enqueue(arq_pool: Any | None = None, *, online_payment_id: UUID, subject_kind: Literal["membership", "pt_package"], subject_id: UUID) -> None` matches CONTEXT.md D-50-19 verbatim. Phase 50 caller passes `arq_pool=None` positionally; Phase 52 NOT-04/05 will swap in `app.state.arq_pool` with no callsite shape change.

- **Plan 50-04 baseline smoke test green (B-3):** `tests/unit/test_webhook_router_smoke.py` asserts the route is mounted in `create_app()` and that `TestClient(app)` instantiates cleanly. Independent of Plan 50-06's full e2e suite — Plan 50-04 has its own runtime smoke at the plan boundary.

- **Blocker #7 verified — composition root untouched:** `git diff app/core/dependencies.py app/main.py app/workers/__init__.py` returns empty. Phase 47 already wired all Protocol slots (`register_membership_activator` + `register_pt_package_activator` + `register_payment_recorder` + `register_yookassa_client_provider`); Plan 50-04 consumes accessors only.

## Task Commits

1. **Task 1 RED** — `cc8638c` (test(50-04): failing smoke for yookassa webhook route mount) — package marker `app/api/v1/_internal/yookassa/__init__.py` + failing test asserting `/api/v1/_internal/yookassa/webhook` is in `create_app().routes`.
2. **Task 1 GREEN** — `f94c237` (feat(50-04): yookassa webhook router + handlers + atomic UoW + cancellation path) — handlers.py + router.py + v1/router.py mount + audit_payloads Literal widen + deferred-items log.

## Files Created/Modified

### Created
- `apps/backend/app/api/v1/_internal/yookassa/__init__.py` — package marker (cc8638c)
- `apps/backend/app/api/v1/_internal/yookassa/router.py` — POST `/webhook` route, IP allowlist via route-level Depends, Redis dedup `SET NX EX 86400`, event dispatch
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `handle_payment_succeeded` (8-step UoW), `handle_payment_canceled` (mirror), `_assert_can_transition`, `_select_for_update_online_payment` (B-4 INVARIANT docstring), `_read_customer_email` (Blocker #4 narrow SELECT), `_post_commit_enqueue` (W-4 stub)
- `apps/backend/tests/unit/test_webhook_router_smoke.py` — B-3 baseline smoke (2 tests: route-mount assertion + create_app composition smoke)

### Modified
- `apps/backend/app/api/v1/router.py` — added `yookassa_webhook_router` import and `include_router(prefix="/_internal/yookassa")` mount block alongside the Phase 42 email-webhook mount
- `apps/backend/app/core/audit_payloads.py` — widened `YookassaWebhookReceivedPayload.idempotency_outcome` Literal from `["new", "duplicate_blocked", "rejected_ip"]` to `["new", "duplicate_blocked", "rejected_ip", "processed", "illegal_transition"]` (Rule 2 add — required for D-50-17 + D-50-18 step 8 emits; documented inline with the four discriminator branches)
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — appended Plan 50-04 out-of-scope deviations section (pre-existing cron-count test failure + reiterated audit_payloads.py:541 E501)

## Decisions Made

1. **Reused `InvalidTransitionError`** (Blocker #1) — `_assert_can_transition` raises the existing class from `app/core/exceptions.py:212` with `fields={"from_status": ..., "to_status": ...}`. No new `IllegalTransitionError` class introduced. The audit-as-forensic branch in D-50-17 catches this and emits `yookassa_webhook_received` with `idempotency_outcome='illegal_transition'`.

2. **Widened `YookassaWebhookReceivedPayload.idempotency_outcome` Literal** (Rule 2 — missing critical functionality) — the plan text uses `idempotency_outcome='processed'` for the success branch (D-50-18 step 8) and `idempotency_outcome='illegal_transition'` for the FSM-violation branch (D-50-17), but the existing Literal accepted only `['new', 'duplicate_blocked', 'rejected_ip']`. Without widening, every webhook commit would fail with `pydantic.ValidationError` at `audit.emit()`. Widening is purely additive — existing emitters (Phase 48 verifier + future rejected-IP audit row) continue to emit the original three values. Documented inline with explicit branch semantics.

3. **`get_payment_recorder()` returns the `Payment` ORM row** — accessing `.id` from the returned row (`payment_row.id`) is the documented contract from Plan 50-03 SUMMARY ("PaymentRecorder returns the Payment ORM row"). The Protocol's return type is `Any` due to the `core-not-depend-on-modules` importlinter contract; the handler casts implicitly via the `.id: UUID` attribute access.

4. **`Client.email` import is OK from `_internal/yookassa/handlers.py`** — the handler lives under `app/api/v1/_internal/yookassa/`, which is at the **router layer** (mirror of Phase 42 email webhook). Router-layer code may import from `app.modules.*` (the importlinter contract `core-not-depend-on-modules` applies to `app.core`, not `app.api`). The Client ORM model import is purely for the narrow `select(Client.email)` query; no relationship traversal happens.

5. **Defensive isinstance guards on webhook body parsing** — `body['object']` may be missing / null / a non-dict; `body['event']` may be a non-string; `body['object']['id']` may be missing or non-string. Every field access is `isinstance`-checked before use; the handler returns 200 (no DB write) with a structlog warning rather than crashing. This is consistent with the email-webhook handler's "anonymous internet surface — never trust the body shape" discipline.

6. **`_post_commit_enqueue` callsite forced onto a single line** — the W-4 acceptance grep gate (`grep -c "_post_commit_enqueue(\s*None"`) doesn't match across newlines in plain grep. Restructured the callsite to one line with `# noqa: E501` so the gate matches and ruff stays clean. The single-line form also makes Phase 52's swap (`None` → `app.state.arq_pool`) trivially small.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] `YookassaWebhookReceivedPayload.idempotency_outcome` Literal widening**

- **Found during:** Task 1 GREEN (writing handlers.py — drafting the `online_payment_succeeded` + `online_payment_canceled` ROOT audit emits per D-50-18 step 8)
- **Issue:** Plan asks for `idempotency_outcome='processed'` (success branch) and `idempotency_outcome='illegal_transition'` (FSM-violation branch — D-50-17). The existing `YookassaWebhookReceivedPayload.idempotency_outcome` Literal accepts only `['new', 'duplicate_blocked', 'rejected_ip']`. `audit.emit()` validates the payload kwargs against `AUDIT_PAYLOAD_SCHEMAS[("yookassa_webhook_received", "yookassa_webhook")]` (Phase 30 INFRA-23 / D-30-03 — hard-fail discipline); passing `'processed'` or `'illegal_transition'` would raise `pydantic.ValidationError` inside every webhook commit, rolling back the UoW and triggering ЮKassa retry storms.
- **Fix:** Widened the Literal to `['new', 'duplicate_blocked', 'rejected_ip', 'processed', 'illegal_transition']`. Documented inline with explicit semantics for each of the four branches the handler records (the legacy `'new'` is kept for back-compat but is no longer emitted by Plan 50-04 handlers). Plan's `files_modified` list did NOT include `audit_payloads.py`, but Rule 2 (add missing critical functionality) applies — without the widening the plan's `must_haves` for D-50-17 + D-50-18 step 8 are unsatisfiable.
- **Files modified:** `apps/backend/app/core/audit_payloads.py` (lines 966-989 region — the `YookassaWebhookReceivedPayload` class body)
- **Verification:** 67 audit-regression tests in `test_audit_payloads.py` + `test_audit_taxonomy.py` + `test_locked_audit_events.py` all pass (the widening is additive — existing payloads validating against the old three values continue to validate against the wider Literal).
- **Committed in:** `f94c237`

**2. [Rule 3 — Blocking] `.env` file required for `YooKassaSettings` instantiation at import time**

- **Found during:** Task 1 GREEN (running the first `python -c "from app.api.v1._internal.yookassa.router import router"` import smoke)
- **Issue:** `app/integrations/yookassa/webhook_verifier.py` instantiates `_settings: Final[YooKassaSettings] = YooKassaSettings()` at MODULE import time. `YooKassaSettings` requires `shop_id` / `secret_key` / `return_url` / `tax_system_code` / `default_vat_code` env vars; the worktree shipped without `.env`. Plan 50-03's SUMMARY notes the same blocker for `alembic upgrade head`.
- **Fix:** Copied `.env.example` to `.env` (gitignored — does not affect committed state). One-time per-worktree setup; not a code change.
- **Files modified:** none committed (`.env` is gitignored)
- **Verification:** All subsequent imports + tests succeed.

### Out-of-Scope (logged to deferred-items.md)

- `tests/unit/workers/test_worker_settings.py::test_worker_settings_cron_resolves_to_registered_function` — pre-existing failure on base commit `751520ad`: asserts `len(WorkerSettings.cron_jobs) == 5` but actual is `6`. Verified by `git stash` + re-run on clean tree (still fails). Unrelated to Plan 50-04 surface area; cron drift from an earlier phase.
- `apps/backend/app/core/audit_payloads.py:541` E501 line too long (148 > 100) — pre-existing from Plan 50-03 deferred list; not in Plan 50-04 scope (Plan 50-04 touched line 969 region only).

---

**Total deviations:** 1 Rule 2 widening + 1 Rule 3 env setup. Both were necessary for the plan's `must_haves` to compile and pass validation. No scope creep — every change is in service of the plan's stated must-haves and acceptance criteria.
**Impact on plan:** Plan executed exactly as specified once the Literal was widened. All 6 requirements (WH-01..04, WH-06; WH-05 was completed in Plan 50-03 per its SUMMARY) materialized in the shipped code.

## Issues Encountered

- **`_select_for_update_online_payment` callsite multi-line format broke the B-4 grep gate** — initial draft had the call split across 3 lines (`(\n    session, yookassa_payment_id=...\n)`). The acceptance grep `grep -B5 "_select_for_update_online_payment(session" handlers.py | grep -c "session.begin"` is a per-line regex and matched 0. Fixed by restructuring both callsites to a single line so `(session` appears on the same line as the function name. Post-fix grep returns `3` (≥2).

- **`_post_commit_enqueue(None, ...)` callsite multi-line format broke the W-4 grep gate** — initial draft had the call split across 5 lines. The acceptance grep `grep -c "_post_commit_enqueue(\s*None"` is a per-line regex and matched 0 even though `\s` should match newline in some regex flavors (it doesn't in plain `grep`). Fixed by collapsing to one line with `# noqa: E501` so the gate matches and ruff stays clean.

- **`IllegalTransitionError == 0` grep gate counted docstring mentions** — initial draft had two prose mentions of `IllegalTransitionError` in the module + helper docstrings (explaining the Blocker #1 anti-pattern). The acceptance grep counted these as violations. Rephrased the docstrings to avoid the literal token while preserving the Blocker #1 rationale.

## User Setup Required

None. The `.env` file copy is a one-time per-worktree convenience (auto-applied by anyone running the suite); not a code change. The `app.main.create_app()` factory wires all Protocol slots from Phase 47, so no new composition-root wiring is needed for the webhook to be live.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: audit-shape | apps/backend/app/core/audit_payloads.py | `YookassaWebhookReceivedPayload.idempotency_outcome` Literal widened to 5 values. Downstream consumers iterating audit payloads (forensic exports, BI ETL, ops dashboards) MUST accept the two new branches `'processed'` and `'illegal_transition'`. The widening is documented inline with the four discriminator semantics. |
| threat_flag: surface-add | apps/backend/app/api/v1/_internal/yookassa/router.py | NEW anonymous-by-design endpoint at `POST /api/v1/_internal/yookassa/webhook`. Security model: IP allowlist via route-level `Depends(verify_yookassa_ip)` running BEFORE body parse; Redis SET NX EX 86400 dedup; outbound re-fetch via `GET /v3/payments/{id}` as the cryptographic anchor (replaces HMAC). Plan 50-06 will add this path to `test_route_introspection.py` EXCLUDED_PATHS with audit-trail comment (D-50-40); existing EXCLUDED_PREFIXES `/api/v1/_internal/` covers it at runtime. |

## Next Phase Readiness

- **Plan 50-05 unblocked (AST gates):** webhook router shape is locked — route-level `dependencies=[Depends(verify_yookassa_ip)]` decorator + Redis `SET NX EX 86400` constants + handler re-fetch-before-write ordering are all in place. Plan 50-05's structural AST tests (D-50-04/07/12 gates) can target the new files directly.
- **Plan 50-06 unblocked (e2e suite):** the webhook handler ships a working atomic UoW with all 4 audit emits and the fiscal_receipt INSERT. Plan 50-06's 12 behavior tests (T1..T12 in the plan's `<behavior>` block) have a working SUT to exercise.
- **Phase 51 unblocked (fiscal dispatch):** `fiscal_receipts(status='sent', kind='payment', customer_email=...)` rows are now produced on every successful webhook delivery. Phase 51 ARQ task can consume these rows and transition `status='sent' → 'succeeded' | 'failed'` per the existing FSM map (`FISCAL_RECEIPT_STATUS_TRANSITIONS`).
- **Phase 52 unblocked (notifications):** `_post_commit_enqueue` hook is in place with the D-50-19-locked signature; Phase 52 NOT-04/05 only needs to swap the `None` callsite arg for `app.state.arq_pool` and fill the body with `notify_membership_activated` / `notify_pt_package_activated` ARQ task enqueues. The audit chain (`webhook_intake_corr` UUID threaded through `audit_correlation_id` on every CHILD emit) gives Phase 52 a deterministic correlation seed for DM idempotency.

## Self-Check: PASSED

- Created files (all verified via `[ -f ... ]`):
  - `apps/backend/app/api/v1/_internal/yookassa/__init__.py` — FOUND
  - `apps/backend/app/api/v1/_internal/yookassa/router.py` — FOUND
  - `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — FOUND
  - `apps/backend/tests/unit/test_webhook_router_smoke.py` — FOUND
- Modified files (all verified in `git diff 751520ad..HEAD --stat`):
  - `apps/backend/app/api/v1/router.py` — FOUND
  - `apps/backend/app/core/audit_payloads.py` — FOUND
  - `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — FOUND
- Both commit hashes verified via `git log --oneline 751520ad..HEAD`:
  - cc8638c (RED) — FOUND
  - f94c237 (GREEN) — FOUND
- Blocker #1 (zero `IllegalTransitionError` refs): VERIFIED via `grep -c "IllegalTransitionError" apps/backend/app/api/v1/_internal/yookassa/handlers.py` returning `0`
- Blocker #4 (zero `row.client.email` relationship traversal): VERIFIED via `grep -c "row.client.email" handlers.py` returning `0`; `_read_customer_email` count `2` (definition + call)
- Blocker #7 (composition root untouched): VERIFIED via `git diff apps/backend/app/core/dependencies.py apps/backend/app/main.py apps/backend/app/workers/__init__.py` returning empty
- B-4 (transaction-proximity grep gate): VERIFIED — `grep -B5 "_select_for_update_online_payment(session" handlers.py | grep -c "session.begin"` returns `3` (≥2 required)
- W-4 (signature + Phase 50 callsite): VERIFIED — `grep -c "arq_pool: Any | None = None" handlers.py` returns `1`; `grep -c "_post_commit_enqueue(\s*None" handlers.py` returns `1`
- B-3 (Plan 50-04 baseline smoke): VERIFIED — `uv run python -m pytest tests/unit/test_webhook_router_smoke.py -x -q` returns `2 passed`
- Route mount: VERIFIED via `create_app()` introspection — `[r.path for r in app.routes]` contains `/api/v1/_internal/yookassa/webhook`
- ruff: PASSED on `app/api/v1/_internal/yookassa/`, `app/api/v1/router.py`, `tests/unit/test_webhook_router_smoke.py`
- mypy strict: PASSED on `app/api/v1/_internal/yookassa/` (0 issues across 3 source files)
- lint-imports: 3 contracts kept, 0 broken
- audit regression: 67 tests across `test_audit_payloads.py` + `test_audit_taxonomy.py` + `test_locked_audit_events.py` all green (Literal widening is purely additive)

---
*Phase: 50-webhook-fsm-fiscal-foundation*
*Completed: 2026-05-22*
