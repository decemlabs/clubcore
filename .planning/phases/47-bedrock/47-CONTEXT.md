# Phase 47: Bedrock - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Lay down v1.7 infrastructure primitives — audit events, ЮKassa settings/credentials, trusted-IP frozenset, kopecks↔rubles converters, Protocol slot declarations, and Alembic 0033 (`clients.email` partial UNIQUE) — **before any ЮKassa callsite exists**. This phase ships no business behavior; it ships a foundation that Phases 48–50 can land cleanly on. INFRA-15 discipline from v1.3 applies: every locked constant (`LOCKED_AUDIT_EVENTS`, `YOOKASSA_TRUSTED_IPS`) is registered and AST-gated *before* the first call site.

Requirements covered: INFRA-34, INFRA-35, INFRA-36, INFRA-37, INFRA-38, INFRA-39, INFRA-40, INFRA-41.

</domain>

<decisions>
## Implementation Decisions

### Protocol Slots (INFRA-38)
- **D-47-01:** Declare **both** `MembershipActivator` and `PtPackageActivator` Protocol slots in Phase 47, alongside `YooKassaClientProvider` and `FiscalReceiptDispatcher`. Empty/no-op wiring at composition root; Phase 50 fills the concrete implementations.
- **D-47-02:** All four Protocol slot definitions live in **`apps/backend/app/core/dependencies.py`**, co-located with existing slots (`EmailDispatcher`, `PaymentRecorder`, etc.). This matches the 12+ prior Protocol slot precedent and keeps `app/core/dependencies.py` as the single canonical home for composition-root contracts. (Initial discussion said `app/core/services.py` — that file turned out to be a docstring-only stub; corrected via pattern-mapper finding 2026-05-21.)
- **Rationale:** Zero `.importlinter` ignore entries needed for the v1.7 webhook → memberships/pt_packages boundary. Future code-review and audit-fix passes won't have to relitigate the boundary because there's nothing to relitigate.

### Alembic 0033 — `clients.email` (INFRA-41)
- **D-47-03:** **Column already exists** since Alembic 0002 (`clients.email Text NULL`). 0033 does NOT add the column and does NOT narrow `Text → VARCHAR(255)`.
- **D-47-04:** 0033 adds **only** the partial UNIQUE index:
  ```sql
  CREATE UNIQUE INDEX ix_clients_email_lower_unique
    ON clients (lower(email))
    WHERE email IS NOT NULL AND deleted_at IS NULL;
  ```
- **D-47-05:** Migration runs a **pre-flight duplicate check** (`SELECT lower(email), COUNT(*) FROM clients WHERE email IS NOT NULL AND deleted_at IS NULL GROUP BY 1 HAVING COUNT(*) > 1`) via `op.execute(...).fetchall()`. If any rows return, the migration **aborts with an assertion error** listing the offending values so the operator can resolve duplicates manually and re-run. No silent dedup, no soft-delete, no automatic backfill.
- **D-47-06:** REQUIREMENTS.md INFRA-41 wording will be tightened during planning to reflect actual scope ("add partial UNIQUE on existing column" instead of "add column").
- **Rationale:** Pet-project single-gym scale makes duplicates unlikely; fail-fast pre-flight is safer than silent dedup. Narrowing `Text → VARCHAR(255)` rewrites column metadata for zero behavior benefit. Backfill from `users.email` or other tables is a separate operator-runbook concern, not a schema migration.

### `YooKassaSettings` env layout (INFRA-36)
- **D-47-07:** Single set of `YOOKASSA_*` environment variables. The `sandbox: bool` field toggles the API base URL inside `YooKassaClient` and bypasses the IP allowlist in `verify_yookassa_ip`. Per-environment `.env` files swap the credential values.
- **D-47-08:** **Standalone** `YooKassaSettings(BaseSettings)` class in `apps/backend/app/integrations/yookassa/settings.py` with `model_config = SettingsConfigDict(env_prefix="YOOKASSA_")`. Composition root instantiates it once and passes the instance to `YooKassaClientProvider`. This mirrors how `EmailSettings` lives next to `app/integrations/email/`.
- **D-47-09:** `.env.example` documents every field (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL`, `YOOKASSA_TAX_SYSTEM_CODE`, `YOOKASSA_DEFAULT_VAT_CODE`, `YOOKASSA_SANDBOX`) with placeholder values; no real credentials in git. `YOOKASSA_SECRET_KEY` typed as `SecretStr` so structlog redaction holds.
- **Rationale:** Matches the existing email-integration pattern. Keeps `app.core.config.Settings` from accumulating per-integration field churn. Encapsulation makes adapter unit tests easier to mock.

### Claude's Discretion
The user did not select the following gray areas; defaults apply. Downstream agents may settle these without re-asking:
- **Audit-event AST gate test placement (INFRA-34):** Create a new `apps/backend/tests/unit/test_locked_audit_events_v17_ast.py` mirroring `test_locked_email_templates_ast.py`. Do not extend a single existing AST gate test.
- **`_money.py` location (INFRA-39):** Place `kopecks_to_yookassa` / `yookassa_to_kopecks` in `apps/backend/app/integrations/yookassa/_money.py` per the REQUIREMENTS.md text. Underscore-prefixed module signals integration-internal use; the existing `app/core/formatters.format_money()` stays the only public money formatter.
- **Audit-event registration cadence (INFRA-34):** Register **all 9** v1.7 events in a single frozenset extension (one PR / one commit) before any callsite. Matches the "before any callsite" wording in the requirement and the INFRA-15 discipline.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing, RF regional constraints, webhook-security correction (IP allowlist, no HMAC)
- `.planning/REQUIREMENTS.md` — INFRA-34..41 full text (Phase 47 scope)
- `.planning/ROADMAP.md` §"Phase 47: Bedrock" — success criteria
- `.planning/research/SUMMARY.md` — research synthesis (4 parallel researchers)
- `.planning/research/STACK.md` — `yookassa` 3.10.1 SDK notes; sync→async wrap discipline
- `.planning/research/ARCHITECTURE.md` — `app/integrations/yookassa/` mirroring `app/integrations/email/`
- `.planning/research/PITFALLS.md` — 6 BLOCKER pitfalls (IP allowlist, double activation, return_url oracle, off-by-100, double-tap, no HMAC)

### Codebase contracts to preserve
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset + `_assert_audit_pair_locked` guard pattern to extend
- `apps/backend/app/core/audit_payloads.py` — Pydantic v2 `extra='forbid'` payload schema pattern; carries `audit_correlation_id`
- `apps/backend/app/core/dependencies.py` — canonical Protocol slot home (`EmailDispatcher`, `PaymentRecorder`, ...); `app/core/services.py` is docstring-only and is NOT a slot home despite its name
- `apps/backend/app/core/config.py` — main `Settings`; `YooKassaSettings` is **NOT** nested here
- `apps/backend/app/integrations/email/` — template for the new `app/integrations/yookassa/` skeleton: `types.py` / `client.py` / `factory.py` / `circuit_breaker.py` analogs
- `apps/backend/app/modules/clients/models.py:67` — existing `email: Mapped[str | None]` column (do NOT re-add in 0033)
- `apps/backend/alembic/versions/0002_clients.py:48` — original `clients.email` column declaration
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — AST-gate test pattern to mirror for both `LOCKED_AUDIT_EVENTS` (v1.7 events) and `YOOKASSA_TRUSTED_IPS`

### External specs (ЮKassa / 54-ФЗ)
- https://yookassa.ru/developers/using-api/interaction-format — Idempotency-Key header semantics
- https://yookassa.ru/developers/using-api/webhooks — webhook IP ranges (6 CIDRs)
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values — `tax_system_code` + `vat_code` values for `YooKassaSettings`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/integrations/email/` structure** (`types.py`, `client.py`, `factory.py`, `circuit_breaker.py`, `dispatcher.py`, `models.py`, `templates/`) — direct template for the Phase 47 `app/integrations/yookassa/` skeleton.
- **`app/core/audit.py` `LOCKED_AUDIT_EVENTS` frozenset + AST gate test pattern** — extend the frozenset with 9 new tuples; mirror the AST-gate test under `tests/unit/`.
- **`app/core/formatters.format_money(kopecks: int) -> str`** — already implements ru-RU kopeck→string with NBSPs; the *new* `_money.py` is for ЮKassa wire-format conversion only (string `"199.00"` rubles ↔ int kopecks), NOT user-facing formatting.
- **`SecretStr` precedent** — `EmailSettings.smtp_password` and other prior credentials already use `SecretStr`; structlog formatters already redact it.

### Established Patterns
- **INFRA-15 discipline:** every locked constant ships with an AST-gate test that fails if a non-literal value is passed to the consuming function. Pattern set in v1.3 (`LOCKED_AUDIT_EVENTS`) and reused in v1.6 (`LOCKED_EMAIL_TEMPLATES`).
- **Protocol slots at composition root:** all cross-module integrations cross the boundary via a `Protocol` declared in `app/core/services.py`. Wired in the FastAPI app factory and (when relevant) the ARQ worker startup (REG-29-03 double-wiring).
- **Pydantic Settings per integration:** integration-owned `BaseSettings` subclasses (e.g., `EmailSettings`) live next to the integration code, not nested under `app.core.config.Settings`.
- **Frozen Pydantic v2 audit payloads with `extra='forbid'`** + mandatory `audit_correlation_id: UUID | None` field.

### Integration Points
- `app/integrations/yookassa/` (new) — package directory + settings/_money/webhook_verifier landed in Phase 47; types.py / client.py / factory.py / circuit_breaker.py / receipt.py land in Phase 48 as part of ADAPTER-01..04 + ADAPTER-06 (no value in shipping empty NotImplementedError stubs ahead of time).
- `app/core/audit.py` `LOCKED_AUDIT_EVENTS` — extension point (9 new tuples).
- `app/core/audit_payloads.py` — 9 new payload classes.
- `app/core/dependencies.py` — 4 new Protocol slots (`YooKassaClientProvider`, `FiscalReceiptDispatcher`, `MembershipActivator`, `PtPackageActivator`) using defensive-raise accessor pattern (mirrors `get_email_dispatcher` / `get_payment_recorder`). `YooKassaClientProvider` + `FiscalReceiptDispatcher` are double-wired (FastAPI + ARQ worker per REG-29-03); `MembershipActivator` + `PtPackageActivator` are HTTP-only single-wire.
- `app/main.py` composition root — wires Protocol slots empty/no-op in Phase 47; concrete in Phases 48–50.
- `.importlinter` — add `app.modules.online_payments` to `modules-independent` contract preemptively (the module itself ships in Phase 49, but the contract list is updated now to fail fast on misplaced imports).
- `.env.example` — 6 new `YOOKASSA_*` placeholder entries.
- `apps/backend/alembic/versions/0033_*.py` — partial UNIQUE on `clients.email` with pre-flight duplicate check.

</code_context>

<specifics>
## Specific Ideas

- The 9 new `LOCKED_AUDIT_EVENTS` identifiers (per INFRA-34): `online_payment_initiated`, `yookassa_payment_created`, `online_payment_succeeded`, `online_payment_canceled`, `online_payment_refunded`, `fiscal_receipt_dispatched`, `fiscal_receipt_succeeded`, `fiscal_receipt_failed`, `yookassa_webhook_received`.
- The 6 CIDR ranges for `YOOKASSA_TRUSTED_IPS` come from the official webhooks doc; capture them as a `frozenset[str]` literal and document the source URL in a module docstring so audits can re-verify.
- `_money.py` test coverage target: 10 edge cases — `0`, `1`, `99`, `100`, `9999999`, rounding (e.g., `"199.005"` → 19_900 or 19_901 — pin behavior in the test), negative values, leading zeros (`"00100"`), trailing decimal absence (`"199"` vs `"199.00"`), non-numeric input rejection.
- Migration 0033 pre-flight error message must include the duplicated `lower(email)` values so the operator can resolve in one query.

</specifics>

<deferred>
## Deferred Ideas

- **REQUIREMENTS.md INFRA-41 wording tightening** — minor doc edit during Phase 47 planning to reflect actual scope ("add partial UNIQUE on existing column"). Not new scope; in-phase.
- **Recurring autopayments `payment_method_id`** (research Open Q #4) — owner has not requested v2.0 recurring billing; do NOT add the column to `online_payments` preemptively. Lift in v2.0 if/when business asks.
- **`payments.received_by_user_id` nullability** (research Open Q #2) — affects Phase 49 Alembic 0034, not Phase 47.
- **Sandbox-credentials-per-developer (.env.local)** — currently single `.env` swap; if multiple devs collide, introduce `.env.{dev_name}` overlay later. Not a Phase 47 concern.

</deferred>

---

*Phase: 47-Bedrock*
*Context gathered: 2026-05-21*
