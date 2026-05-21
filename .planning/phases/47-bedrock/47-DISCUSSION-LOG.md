# Phase 47: Bedrock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 47-bedrock
**Areas discussed:** MembershipActivator slot scope, Alembic 0033 — clients.email backfill posture, YooKassaSettings env layout

---

## MembershipActivator slot scope

### Q1 — How should membership / PT-package activation cross the webhook → module boundary?

| Option | Description | Selected |
|--------|-------------|----------|
| Declare MembershipActivator + PtPackageActivator Protocol slots NOW | Declare both Protocol slots in Phase 47 INFRA-38 alongside YooKassaClientProvider + FiscalReceiptDispatcher. Empty wiring; Phase 50 fills the concrete impl. Zero import-linter exceptions. | ✓ |
| Declare a single combined SubjectActivator Protocol | One Protocol with `activate(subject_kind, subject_id)` dispatching internally. Fewer slots, but couples membership + pt_package activation logic at the boundary. | |
| Defer to Phase 50 with import-linter ignore | No new slots in Phase 47. Phase 50 lands with `online_payments.webhook → memberships.service` + `→ pt_packages.service` in `.importlinter` ignores. | |

**User's choice:** Declare MembershipActivator + PtPackageActivator Protocol slots NOW.

### Q2 — Where do the new Protocol slots live in the file tree?

| Option | Description | Selected |
|--------|-------------|----------|
| `app/core/services.py` | Co-locate with existing Protocol slot declarations. One canonical home; matches pattern since v1.3. | ✓ |
| Per-module `protocols.py` files | `app/modules/memberships/protocols.py` + `app/modules/pt_packages/protocols.py`. New convention — no precedent. | |
| `app/integrations/yookassa/protocols.py` | Group Protocol slots near primary consumer. Risks naming them as if they only exist for online payments. | |

**User's choice:** `app/core/services.py`.

---

## Alembic 0033 — clients.email backfill posture

**Codebase finding surfaced during discussion:** `clients.email` (Text, NULL) already exists since Alembic 0002, so the real work of 0033 is the partial UNIQUE constraint, not the column.

### Q1 — How should the migration handle the already-existing clients.email column?

| Option | Description | Selected |
|--------|-------------|----------|
| Add partial UNIQUE only; keep Text type | Only `CREATE UNIQUE INDEX ix_clients_email_lower_unique ON clients (lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL`. Pre-flight duplicate check aborts if existing duplicates exist. | ✓ |
| Add partial UNIQUE + narrow Text → VARCHAR(255) | Adds `op.alter_column`. Slightly riskier (rewrites column metadata), zero behavior benefit. | |
| Add partial UNIQUE + dedup script + backfill from users.email | Pre-merges duplicates and pulls email from other tables. Bigger blast radius. | |

**User's choice:** Add partial UNIQUE only; keep Text type.
**Notes:** REQUIREMENTS.md INFRA-41 wording will be tightened during planning to reflect actual scope.

### Q2 — If the pre-flight duplicate check finds existing lower(email) duplicates, what should the migration do?

| Option | Description | Selected |
|--------|-------------|----------|
| Abort with a clear error | Migration fails fast with assertion listing offending values; operator resolves manually then re-runs. | ✓ |
| Log duplicates + soft-delete older rows | Auto-resolve by setting `deleted_at = now()` on older duplicates. Data-touching during schema migration. | |
| Skip pre-flight; let `CREATE UNIQUE INDEX` fail naturally | Postgres rejects index creation if duplicates exist. Less friendly message, zero extra code. | |

**User's choice:** Abort the migration with a clear error.

---

## YooKassaSettings env layout

### Q1 — How should sandbox vs production credentials be structured in .env / Settings?

| Option | Description | Selected |
|--------|-------------|----------|
| Single `YOOKASSA_*` set + `sandbox: bool` toggles API base URL | One env block; per-environment `.env` swap. `sandbox=True` selects sandbox API URL and bypasses IP allowlist. Matches PydanticSettings idiom. | ✓ |
| Separate `YOOKASSA_PROD_*` + `YOOKASSA_SANDBOX_*` prefixes | Both sets in `.env`; mode selects which to use. Risk: prod secrets in dev `.env` files. | |
| Single set + separate ProductionYooKassaSettings / SandboxYooKassaSettings classes | Two Settings subclasses; factory picks one based on flag. No functional advantage at this scale. | |

**User's choice:** Single `YOOKASSA_*` set + `sandbox: bool` toggles API base URL.

### Q2 — How should YooKassaSettings hook into the existing app config?

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone `YooKassaSettings(BaseSettings)` with `env_prefix="YOOKASSA_"` | Separate class in `app/integrations/yookassa/settings.py`. Composition root instantiates once. Mirrors how EmailSettings lives next to `app/integrations/email/`. | ✓ |
| Nested under main `app.core.config.Settings` as `Settings.yookassa` | One global Settings with `yookassa: YooKassaSettings` sub-model. Couples ЮKassa to core. | |
| Flat `YOOKASSA_*` fields directly on `app.core.config.Settings` | All 6 fields on the main Settings class. Pollutes core. | |

**User's choice:** Standalone `YooKassaSettings(BaseSettings)` with `env_prefix="YOOKASSA_"`.

---

## Claude's Discretion

User did not select these gray areas during the present-areas step. Defaults applied (captured in CONTEXT.md `<decisions>` § Claude's Discretion):

- **Audit-event AST gate test placement (INFRA-34)** — new `tests/unit/test_locked_audit_events_v17_ast.py` mirroring `test_locked_email_templates_ast.py`.
- **`_money.py` location (INFRA-39)** — `app/integrations/yookassa/_money.py` per REQUIREMENTS.md text; underscore-prefixed signals integration-internal.
- **Audit-event registration cadence (INFRA-34)** — all 9 events in a single frozenset extension before any callsite.

## Deferred Ideas

- REQUIREMENTS.md INFRA-41 wording tightening — minor in-phase doc edit during planning.
- Recurring autopayments `payment_method_id` column — owner has not requested; defer to v2.0.
- `payments.received_by_user_id` nullability widening — Phase 49 concern, not Phase 47.
- `.env.{dev_name}` per-developer credential overlay — premature; revisit if multiple devs collide.
