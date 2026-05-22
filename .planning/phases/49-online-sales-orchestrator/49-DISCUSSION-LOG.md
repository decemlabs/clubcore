# Phase 49: Online Sales Orchestrator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 49-Online-Sales-Orchestrator
**Mode:** `--auto` (no interactive prompts; Claude auto-selected recommended defaults)
**Areas discussed:** Module layout, `online_payments` ORM + Alembic 0034, Idempotency-Key strategy, FIS-05 email gate, Sell endpoint surface, `return_url` anti-oracle screen, Audit emission chain, Composition root wiring, Permission mapping, Test strategy, Plan/wave shape

---

## Module layout — `app/modules/online_payments/`

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror `memberships/` skeleton (constants/models/repository/schemas/service/router + empty placeholders for permissions + email_templates) | Standard v1.5+ module shape; satisfies Phase 47 INFRA-40 import-linter ignores in commit 1 | ✓ |
| Extend `payments/` module with online-payment endpoints | Reuses ledger code | |
| Split into `online_payments_core/` + `online_payments_api/` | Hexagonal separation | |

**Auto-selection rationale:** SUMMARY.md line 102 ("sibling, NOT extension") and Phase 47 INFRA-40 ignore-list explicitly assume the sibling module shape. Splitting is over-engineering for a single domain module.

**Notes (D-49-01..03):** Placeholder `email_templates.py` + `permissions.py` files (module docstring only) ship in Phase 49 to clear Phase 47 unmatched-ignores; bodies land in Phase 52 and never, respectively.

---

## `online_payments` ORM + Alembic 0034

| Option | Description | Selected |
|--------|-------------|----------|
| Single migration with all 4 indexes + table | Atomic per ROADMAP success-criterion #5 | ✓ |
| Two migrations: table first, indexes after | Easier rollback per index | |
| Polymorphic single partial UNIQUE on `(client_id, COALESCE(membership_plan_id, pt_package_plan_id), DATE(initiated_at))` | One index covers both subject kinds | |

**Auto-selection rationale:** Success-criterion #5 reads "Alembic 0034 applies cleanly: `online_payments` table exists with UNIQUE…" — singular migration is the natural reading; two-migration shape adds operational complexity for zero benefit. Polymorphic index rejected because Phase 16/30 precedent uses one-index-per-subject-kind.

**Notes (D-49-04..06):** Schema mirrors PAY-01 wording verbatim + adds `confirmation_type` (CHECK in ('redirect','qr')) and `audit_correlation_id` chain root. QR payload computed on-the-fly, not stored. `down_revision = "0033_clients_email_partial_unique"`.

---

## Idempotency-Key generation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic `sha256("sell-{kind}:{plan_id}:{client_id}:{today_iso_utc}")` | PAY-03 wording locks this; retries dedupe server-side | ✓ |
| Random UUIDv4 per click | Simpler; relies on outer HTTP idempotency layer for dedup | |
| Composite of Redis-issued nonce + DB row UUID | Strongest dedup; most moving parts | |

**Auto-selection rationale:** REQUIREMENTS.md PAY-03 explicitly specifies the deterministic formula. Auto-mode honours the locked spec.

**Notes (D-49-08..11):** Order of operations is **ЮKassa-first, DB-second** with a replay check by idempotency_key — half-baked rows under transient failure are the larger evil; deterministic key + ЮKassa-side dedup makes retry safe. "ЮKassa created, DB failed" rare case deferred to Phase 53 reconcile cron.

---

## FIS-05 client email gate placement

| Option | Description | Selected |
|--------|-------------|----------|
| Service-layer gate; raise `ClientEmailRequiredForOnlinePaymentError` → 422 | Single canonical site; gate post `client_id` resolution | ✓ |
| Router-level dependency: `Depends(client_with_email)` resolving `Client` then asserting email | Earlier short-circuit | |
| Pydantic root validator on `SellRequest` | Schema-time validation | |

**Auto-selection rationale:** Pydantic can't see DB state; router dependency would re-fetch the same `Client` row the service already needs. Service-layer keeps the rule single-source and matches memberships/pt-packages precedent.

**Notes (D-49-12, D-49-13):** Error code `client_email_required_for_online_payment` is a locked literal (ROADMAP success-criterion #3). The gate requires `online_payments.service → app.modules.clients.models` — added as a narrow `ignore_imports` entry in commit 1 (mirrors Phase 45 NOTIFY-11/12/13 precedent). Protocol slot alternative rejected as over-engineering for a single-field read.

---

## Sell endpoint surface (PAY-03, PAY-04, PAY-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Four separate POST endpoints (memberships/pt-packages × redirect/qr) sharing one service function with `confirmation_type` arg | Explicit URLs; easy permission mapping | ✓ |
| Single POST `/sell` with `{subject_kind, plan_id, confirmation_type}` body | Less URL surface; harder permission gating | |
| Two POSTs (memberships + pt-packages) with `?confirmation_type=qr` query param | Less surface; query-param branching | |

**Auto-selection rationale:** ROADMAP success-criteria #1 and #2 both reference URL-level differentiation (`/sell` vs `/sell-qr`). The URL split also lets permission decorators apply per-resource (MEMBERSHIPS vs PT_PACKAGES).

**Notes (D-49-14..16):** Permissions reuse `Resource.MEMBERSHIPS` / `Resource.PT_PACKAGES` + `Action.CREATE` (both reception+owner; not in OWNER_ONLY). Two-layer idempotency (outer HTTP `Idempotency-Key` + inner deterministic ЮKassa `Idempotence-Key`).

---

## `return_url` anti-oracle screen (PAY-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Static HTML response, no DB lookup, ignore query params, constant-time floor 50ms | PITFALLS Pitfall 3 + 4 mitigation; forward-compatible if Phase 50 adds lookup | ✓ |
| Static HTML + ARQ background reconcile triggered by lookup | Adds DB read for telemetry | |
| Redirect to admin-web with payment_id; admin-web polls status | Couples backend to frontend timing | |

**Auto-selection rationale:** Success-criterion #4 ("static 'ожидаем подтверждение' screen…no payment-status information exposed") is unambiguous; PITFALLS Pitfall 4 explicitly recommends constant-time floor.

**Notes (D-49-17, D-49-18):** `_RETURN_FLOOR_SECONDS = 0.050`. Handler is anonymous (no auth, no CSRF, `include_in_schema=False`). `Cache-Control: no-store`.

---

## Audit emission chain (D-49-19)

| Option | Description | Selected |
|--------|-------------|----------|
| Two synchronous emits in service: `online_payment_initiated` (chain root) then `yookassa_payment_created` (chain child) | Matches Phase 47 payload semantics; survives Phase 50 webhook correlation walk | ✓ |
| Single combined `online_payment_initiated` carrying yookassa_payment_id + idempotency_key | Fewer rows | |
| Defer audit emits to a post-commit hook | Decouples audit from transaction | |

**Auto-selection rationale:** `LOCKED_AUDIT_EVENTS` already separates the two events; payload schemas already document the chain relationship. Combining them would require widening payloads and breaks Phase 50 chain walk.

**Notes (D-49-19, D-49-20):** Both emits share the same `AsyncSession` (caller-owns-txn). On ЮKassa failure, no audit row is written (no business event happened); `yookassa_call_failed` event deferred to Phase 50 if needed.

---

## Composition root wiring split (PAY-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Wire all three remaining v1.7 slots in Phase 49 — `MembershipActivator` + `PtPackageActivator` + `FiscalReceiptDispatcher` — to stub-body callables raising `NotImplementedError` so success-criterion #6 parity test passes | Phase 50 fills bodies | ✓ |
| Wire only the two activators in Phase 49; defer `FiscalReceiptDispatcher` to Phase 50 | Strict scope adherence | |
| Wire all three with real bodies in Phase 49 | Pulls Phase 50 forward | |

**Auto-selection rationale:** Re-reading success-criterion #6 confirms `FiscalReceiptDispatcher` must be non-None in the Phase 49 parity test. The stub-body pattern is the established two-step landing for Protocol slots (D-47-01 lineage).

**Notes (D-49-21..23):** `MembershipActivator` + `PtPackageActivator` are HTTP-only single-wire (per Phase 47 docstrings); `FiscalReceiptDispatcher` is REG-29-03 double-wire. New parity test at `tests/integration/test_v17_protocol_slot_parity.py`.

---

## Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 48 respx fixtures (`yookassa_create_payment_success/422`) + add scoped fixtures for 500/404 paths inside `tests/modules/online_payments/conftest.py` | DRY; fault coverage at the right layer | ✓ |
| Build full Phase 49 conftest from scratch | Isolated | |
| Skip integration tests for failure modes; rely on Phase 48 unit tests | Saves time, loses coverage | |

**Auto-selection rationale:** Phase 48 D-48-22 explicitly designed the fixtures for downstream reuse. New 500/404 fixtures live in Phase 49 conftest because no other module needs them.

**Notes (D-49-27, D-49-28):** Real Postgres via testcontainers (Phase 4 testing convention); no SQLite divergence.

---

## Plan / wave shape preview (D-49-32)

Suggested ordering for `gsd-plan-phase`:
- **Wave 1 (sequential):** 49-01 Alembic 0034 schema; 49-02 module skeleton + import-linter append.
- **Wave 2 (parallel after Wave 1):** 49-03 service + schemas + email gate; 49-04 router + sell endpoints; 49-05 return-screen + constant-time floor; 49-06 composition-root wiring + parity test.
- **Wave 3 (sequential after Wave 2):** 49-07 E2E integration tests + success-criteria checklist.

Estimated plan count: 7.

---

## Claude's Discretion

Areas where downstream agents may settle without re-asking (full detail in CONTEXT.md `<decisions>` Claude's Discretion subsection):

- `BackendSchemaBase` + `envelope()` wire format
- `ErrorCode` StrEnum centralisation in `constants.py`
- Structlog INFO + WARNING lines for sell flows
- Reusing Phase 48 `User-Agent` header verbatim
- `return_url` value sourced from `YooKassaSettings.return_url` (Phase 47 shipped)
- QR payload extraction via `YooKassaPaymentResult.qr_payload` — Wave-1 verifier task: confirm field exists on Phase 48 dataclass; if missing, file inline plan-fix
- OWNER_ONLY parity test re-run

## Deferred Ideas

Ideas mentioned during analysis that belong in other phases (full list in CONTEXT.md `<deferred>`):

- Embedded ЮKassa widget — v1.9/v2.0
- Telegram WebApp invoice — v2.0
- Mobile deep-link confirmation — v2.0
- Reconcile cron for "ЮKassa created, DB failed" orphans — Phase 53
- `yookassa_call_failed` audit event — Phase 50 (if operational visibility demands)
- `OnlinePaymentSucceededPayload` operator-display extension — Phase 50
- `users.display` runtime import — Phase 50 (Phase 49 leaves the ignore unmatched/warn)
- Saved-card / recurring autopayment columns — v2.0
- Frontend admin-web online-sale UI — v1.9
- `X-Forwarded-For` trust toggle — Phase 50
- Webhook handler, FSM transitions, fiscal-receipt DB row — Phase 50
- Refund endpoint, ARQ retry, circuit breaker — Phase 51
- Outer HTTP `Idempotency-Key` admin-web alignment — v1.9
