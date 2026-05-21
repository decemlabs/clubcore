# Research Summary — v1.7 Online Payments + 54-ФЗ

**Project:** Sportzal
**Milestone:** v1.7 — Online Payments (ЮKassa) + 54-ФЗ Fiscal Receipts
**Researched:** 2026-05-21
**Confidence:** HIGH (4 parallel research outputs converged; corrections already in PROJECT.md)

---

## Executive Summary

v1.7 closes the last commercial MVP gap. Online payment intake (ЮKassa) and 54-ФЗ fiscal receipts ship bundled — Russian law forbids the former without the latter. The integration path is well-documented and low-risk:

- **REST API v3** with redirect-based confirmation
- **"Чеки от ЮKassa"** managed receipt path (embed receipt in payment creation request; no separate АТОЛ/Чек.ОФД adapter)
- **v1.4 ledger preserved** — new `online_payments` module is a sibling of `payments/`; on `payment.succeeded` it calls `record_payment(method='online')` via the existing `payment_recorder` Protocol slot. No mutation of v1.4 invariants.

**Two key research-driven corrections** (already landed in PROJECT.md):
1. **No HMAC on webhooks.** Security = IP allowlist (6 published CIDRs) + status re-fetch via `GET /v3/payments/{id}`. AST gate target = `YOOKASSA_TRUSTED_IPS: frozenset[str]`, not a signature constant.
2. **Official `yookassa` SDK is sync (requests-based).** Wrap in `httpx.AsyncClient` adapter inside `app/integrations/yookassa/`, or use community `async_yookassa`. Never call the sync SDK from an async handler without `run_in_executor`.

**Primary regulatory risk:** silent fiscal-receipt failure → КоАП Article 14.5 penalties. Mitigation: `fiscal_receipts` outbox table + ARQ cron scanning for stale `pending` rows + circuit breaker + operator Telegram alert.

---

## 1. Stack Additions

Only one new direct dependency.

| Package | Version | Role | Notes |
|---|---|---|---|
| `yookassa` | `3.10.1` | Official ЮKassa SDK | Sync — wrap in `httpx.AsyncClient` adapter; `SecurityHelper.is_ip_trusted()` or stdlib `ipaddress` for IP gate |

**Do NOT add:** Stripe (RF-banned), `aioyookassa` (stale), separate АТОЛ/Чек.ОФД adapter (managed path covers it), any 54-ФЗ tag-dictionary library (define `StrEnum`/`IntEnum` constants).

**mypy:** `[[tool.mypy.overrides]] module = "yookassa.*"; ignore_missing_imports = true`. SDK types do NOT cross integration boundary — re-type in `app/integrations/yookassa/types.py`.

---

## 2. Feature Table Stakes (must ship)

| ID | Feature | Description |
|---|---|---|
| **PAY-01** | Server-side payment creation (redirect) | `POST /online-payments/memberships/{id}/sell` + pt-packages variant; returns `confirmation_url`; `Idempotency-Key` mandatory |
| **WH-01** | Webhook endpoint, IP-verified | `POST /api/v1/_internal/yookassa/webhook`; IP allowlist BEFORE body parse; no auth cookie, no CSRF |
| **WH-02** | Payment FSM (`pending → succeeded / canceled`) | `payment.succeeded` is the ONLY activation trigger; always re-fetch payment object from ЮKassa to verify |
| **WH-03** | Refund FSM (`refund.succeeded`) | Subscription to `refund.succeeded` must be explicitly enabled during ЮKassa account setup (deployment runbook entry) |
| **WH-04** | Idempotent webhook processing | Redis `SET NX EX 86400 sz:wh:event:{event_type}:{object_id}` + DB UNIQUE `(yookassa_payment_id)` |
| **REF-01** | Online refund (full only) | Routes to ЮKassa Refund API; awaits `refund.succeeded`; v1.4 atomic audit chain preserved; B-02 still deferred |
| **REF-03** | Refund timeout / poll fallback | ARQ task polls `GET /v3/refunds/{id}` if webhook silent for 30 min |
| **FIS-01** | Receipt mechanism: "Чеки от ЮKassa" | Managed; no separate ОФД contract; email-only delivery |
| **FIS-02** | Receipt embedded in payment creation | `receipt` object in `POST /v3/payments` body — Scenario 1, satisfies 54-ФЗ timing |
| **FIS-03** | `fiscal_receipts` table + FSM | `pending → sent → succeeded / failed`; UNIQUE `(payment_id, kind)`; outbox monitoring |
| **FIS-04** | Refund receipt (возврат прихода) | `receipt` in `POST /v3/refunds`; same `customer.email` requirement |
| **FIS-05** | Client email gate | 422 `client_email_required_for_online_payment` if client has no email |
| **FIS-06** | VAT/tax config via env vars | `YOOKASSA_TAX_SYSTEM_CODE` + `YOOKASSA_VAT_CODE` in `.env`; not hardcoded |
| **NOT-01** | Payment success DM (Telegram + email) | On `payment.succeeded`; UNIQUE `(payment_id, channel)` idempotency |
| **NOT-02** | Refund success DM (Telegram + email) | On `refund.succeeded`; same pattern |
| **NOT-03** | Fiscal receipt email | ЮKassa sends directly; CRM passes `customer.email` |
| **NOT-04** | Operator alert on fiscal failure | structlog ERROR + Telegram DM to owner when `fiscal_receipts.status → failed` |

---

## 3. Differentiators (in scope if time)

| ID | Feature | Complexity | Notes |
|---|---|---|---|
| **PAY-03** | QR/SBP confirmation type | LOW | `confirmation_type='qr'`; same `payment.succeeded` webhook |
| **NOT-05** | Cancellation reason logging | LOW | Log `cancellation_details.reason` on `payment.canceled`; no client DM |

PAY-02 (embedded checkout widget) — deferred (requires frontend work).

---

## 4. Anti-features (deferred)

| Feature | Why |
|---|---|
| Recurring autopayments | Requires ЮKassa manager activation + consent flow + client portal |
| Partial online refund | v1.4 B-02 still deferred |
| Telegram WebApp native invoice | Separate API; admin SPA is not a Mini App |
| Mobile-app deep-link | No mobile app |
| Third-party АТОЛ/Чек.ОФД adapter | Inapplicable for direct gym sales |
| SMS receipt delivery | Not supported by "Чеки от ЮKassa" |
| Two-stage capture (`waiting_for_capture` hold) | Inapplicable for digital activation |
| Partial VAT (5%/7%) | УСН revenue threshold (60M RUB) unreachable at single-gym scale |
| Refund to different card | Requires separate ЮKassa Payout agreement |

---

## 5. Architecture Snapshot

**New directories** mirror established patterns:

- `app/integrations/yookassa/` follows `app/integrations/email/` exactly:
  - `types.py` (frozen dataclasses)
  - `client.py` (async httpx adapter, never re-raises)
  - `factory.py` (boot-time API probe)
  - `webhook_verifier.py` (IP allowlist `Depends()` callable)
  - `receipt.py` (`build_receipt_item()` + `PaymentSubject` / `PaymentMode` / `VatCode` enums)

- `app/modules/online_payments/` is a **sibling** of `app/modules/payments/`, NOT an extension. Critical boundary: v1.4 ledger has AST-enforced append-only + CHECK constraints that must not be widened. New module owns its FSM in a new `online_payments` table. On `payment.succeeded` → `record_payment(method='online')` through existing Protocol slot.

- New `fiscal_receipts` table FKs to `payments.id` (NOT `online_payments.id`). Fiscal obligation attaches to the committed ledger row.

**Webhook route:** `POST /api/v1/_internal/yookassa/webhook` (`_internal` namespace established in Phase 42 for email bounce webhook). Synchronous processing:

```
verify IP → re-fetch payment → FSM transition → record_payment → fiscal_receipts INSERT
  → COMMIT → enqueue notifications post-commit
```

ЮKassa retries on non-200, so transient failures propagate naturally.

**Two new Protocol slots (composition root):**
- `YooKassaClientProvider` (double-wired to FastAPI app + ARQ worker startup — REG-29-03 discipline)
- `FiscalReceiptDispatcher` (enqueues `dispatch_fiscal_receipt` ARQ task post-commit; mirrors `enqueue_email_dispatch`)
- Possibly `MembershipActivator` (Open Question #2)

**New Alembic revisions (0033–0036):**
- 0033: `clients.email` column + Pydantic config sentinel
- 0034: `online_payments` table (FSM, UNIQUE `yookassa_payment_id`, UNIQUE `idempotency_key`, partial UNIQUE `(client_id, plan_id, DATE(initiated_at)) WHERE status != 'canceled'`)
- 0035: `fiscal_receipts` table (FK to `payments.id`, UNIQUE `(payment_id, kind)`)
- 0036: Locked-events sentinel migration (~9 new entries)

**New import-linter entries:**
- `online_payments.service → payments.models` (refund row + payment_receipts; mirrors Phase 45)
- `online_payments.service → users.display`
- `email.dispatcher → online_payments.email_templates`

---

## 6. Watch Out For (Top Pitfalls)

| Severity | Pitfall | Prevention |
|---|---|---|
| **BLOCKER** | No HMAC — IP allowlist only | `Depends(verify_yookassa_ip)` BEFORE body parse; `YOOKASSA_TRUSTED_IPS` AST gate; always re-fetch `GET /v3/payments/{id}` before activation. Header is `Idempotence-Key` (one `t`) |
| **BLOCKER** | Double activation on webhook retry (24h window) | Redis `SET NX EX 86400` before any DB write + DB UNIQUE `(yookassa_payment_id)` + FSM guard |
| **BLOCKER** | Activation on redirect instead of webhook | `return_url` handler shows "ожидаем подтверждение"; activation locked to webhook path with no exceptions |
| **BLOCKER** | Payment-status oracle via `return_url` | Single `return_url` for all outcomes; `_constant_time_floor` on status-check handler; no `?status=` parameter |
| **BLOCKER** | Off-by-100 currency conversion | Dedicated `kopecks_to_yookassa(int) -> str` + `yookassa_to_kopecks(str) -> int` with unit tests; no inline conversion |
| **BLOCKER** | Double-tap payment creation | Deterministic `Idempotency-Key = sha256(f"sell-membership:{plan_id}:{client_id}:{today}")` + DB partial UNIQUE |
| **WARN** | 54-ФЗ receipt timing | Embed receipt in payment creation (Scenario 1); ARQ cron scans for `pending` rows > 90s |
| **WARN** | Wrong 54-ФЗ tags (1212/1214) | `RECEIPT_SUBJECT_MEMBERSHIP = "service"`, `RECEIPT_MODE_FULL = "full_payment"` as locked `Literal` constants; Pydantic Literal types; integration tests assert exact wire values |
| **WARN** | Missing `refund.succeeded` subscription | Deployment runbook: subscribe to `payment.succeeded`, `payment.canceled`, `payment.waiting_for_capture`, `refund.succeeded` |

---

## 7. Phase Carve Recommendation (Phase 47–53)

All 4 researchers independently converged on this 7-phase structure. v1.6 ended at Phase 46.

| # | Phase | Goal | Key deliverables |
|---|---|---|---|
| **47** | Bedrock | INFRA-15 events + credentials + slots first | `LOCKED_AUDIT_EVENTS` extended (~9 events); `YooKassaSettings` (`SecretStr`); `YOOKASSA_TRUSTED_IPS` frozenset; Protocol slot declarations; `integrations/yookassa/` skeleton; Alembic 0033 (`clients.email`); kopecks↔rubles converter + tests; `.env.example` |
| **48** | ЮKassa Integration Adapter | Integration layer before domain module (parallels Phase 42 email) | `client.py` (async httpx wrapper); `factory.py` boot probe; `receipt.py` with `PaymentSubject`/`PaymentMode`/`VatCode` enums; `webhook_verifier.py` `Depends()` (sandbox bypass); `respx` test fixtures |
| **49** | Online Sales Orchestrator | Domain module + sell endpoints | `modules/online_payments/` full structure; Alembic 0034 (`online_payments`); `POST /online-payments/memberships/{plan_id}/sell` + pt-packages; FIS-05 client email gate; `return_url` pending-screen handler; composition root wiring; import-linter updates |
| **50** | Webhook FSM + Fiscal Foundation | Webhook handler + activation + fiscal table | `_internal/yookassa/router.py` (IP gate before body parse); `handle_webhook_event()` FSM; `record_payment(method='online')`; `MembershipActivator` Protocol slot; Alembic 0035 (`fiscal_receipts`); atomic `INSERT fiscal_receipts(status='sent')` in same UoW; Redis dedup; Alembic 0036 events sentinel |
| **51** | Fiscal FSM + Refunds | Receipt status tracking + online refunds | `handle_receipt_webhook()` (`receipt.succeeded`/`.canceled`); `dispatch_fiscal_receipt` ARQ (max_tries=3, jitter); Redis circuit breaker; `POST /online-payments/{id}/refund` (REF-01); `handle_refund_webhook()`; REF-03 poll fallback; NOT-04 operator alert |
| **52** | Cross-channel Notifications + v1.6 Carry-out | DMs + DEFER-46-01/02 | `online_payments/notifications.py` Telegram DMs; `online_payments/email_templates.py` + `LOCKED_EMAIL_TEMPLATES` extended; NOT-01/02 wired post-commit; **DEFER-46-01** live RU email-deliverability probe (yandex/mail/rambler); **DEFER-46-02** owner 15-template countersign |
| **53** | Milestone Verification | Operator runbook + race tests gate | Operator curl runbook + ЮKassa sandbox walkthrough; race tests (concurrent double-delivery, duplicate after Redis restart, refund ordering); DEFER-46-03 circuit-breaker fixture re-run; 0/0 inline regressions hard cap |

**Ordering rationale:** Bedrock first (INFRA-15 discipline). Integration adapter before domain module (matches v1.6 Phase 42 → 43). Sales orchestrator before webhook FSM (need to create payments to test activation). Fiscal foundation in same phase as webhook FSM (same DB transaction). Refunds bundled with fiscal FSM (refund receipt is a fiscal obligation). Notifications last among build-out (fire-and-forget). Verification gate always last.

---

## 8. Open Questions (block phase planning)

| Question | Who answers | When needed |
|---|---|---|
| **VAT regime** — `vat_code` + `tax_system_code` per gym entity (УСН доходы=2 / УСН доходы-расходы=3 / ПСН=6). Must be set per-deployment in `.env` | Gym owner / accountant | Before Phase 53 go-live |
| **`payments.received_by_user_id` nullability** — currently `NOT NULL`; online payments have no human operator at `succeeded` time. Recommended: widen with CHECK `(method='cash' AND received_by_user_id IS NOT NULL) OR method='online'`. Affects Alembic 0034 design | Developer | Phase 49 planning |
| **`MembershipActivator` Protocol slot vs import-linter ignore** — webhook handler needs to activate a membership. (a) New Protocol slot at composition root (clean, established precedent) vs (b) import-linter ignore entry (simpler). Shapes Phase 50 | Developer | Phase 49/50 planning |
| **Recurring autopayments business demand** — ЮKassa supports it (manager-gated). If wanted for v2.0, store `payment_method_id` in `online_payments` now to avoid retro-migration | Product owner | Before v2.0 |

---

## 9. Confidence

| Area | Level | Notes |
|---|---|---|
| Stack | HIGH | Official ЮKassa PyPI (v3.10.1, 2026-04-22); 0 CVEs; async limitation confirmed |
| Features | HIGH | All table-stakes from official ЮKassa docs; FSM states + 54-ФЗ fields confirmed |
| Architecture | HIGH | Module boundary from codebase read (v1.4 AST + CHECK constraints); 12 prior Protocol slot examples |
| Pitfalls | HIGH | 6 BLOCKER pitfalls from official docs; WARN pitfalls from official docs + project patterns |
| 54-ФЗ timing rule | MEDIUM | "5-minute myth" from analyst source (klerk.ru), not official ФНС ruling; Scenario 1 embed is safe regardless |
| Fiscal webhook event names | MEDIUM | `receipt.succeeded` / `receipt.canceled` inferred; verify against ЮKassa dashboard in Phase 50 |

**Gaps to verify during implementation:**
- Exact receipt webhook event-type strings (Phase 50)
- `received_by_user_id` migration safety against existing cash rows (Phase 49)
- IP CIDR list currency vs live dashboard (Phase 48 deploy)

---

## Sources

**Primary (HIGH):**
- https://yookassa.ru/developers/using-api/interaction-format
- https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process
- https://yookassa.ru/developers/using-api/webhooks
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values
- https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds
- https://pypi.org/project/yookassa/

**Secondary (MEDIUM):**
- https://kassa.komtet.ru/blog/moment-rascheta — 54-ФЗ timing
- https://astral.ru/info/operator-fiskalnykh-dannykh/otpravka-elektronnogo-cheka-klientu/ — email/phone requirement
- https://security.snyk.io/package/pip/yookassa — security scan
