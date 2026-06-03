---
phase: 79-payment-methods-foundation-card-on-file
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/backend/alembic/versions/0052_client_payment_methods.py
  - apps/backend/app/modules/payment_methods/__init__.py
  - apps/backend/app/modules/payment_methods/models.py
  - apps/backend/app/modules/online_payments/models.py
autonomous: true
requirements: [PAYM-01, PAYM-03, PAYM-04]
must_haves:
  truths:
    - "client_payment_methods table exists with a partial UNIQUE index on client_id WHERE unlinked_at IS NULL"
    - "online_payments has a save_payment_method boolean column defaulting to false"
    - "ClientPaymentMethod ORM model maps every column and the partial unique index"
    - "alembic upgrade head applies cleanly and alembic downgrade -1 reverses both DDL changes"
  artifacts:
    - path: "apps/backend/alembic/versions/0052_client_payment_methods.py"
      provides: "Migration creating client_payment_methods + save_payment_method column"
      contains: "uq_client_payment_methods_client_id_alive"
    - path: "apps/backend/app/modules/payment_methods/models.py"
      provides: "ClientPaymentMethod ORM model"
      contains: "class ClientPaymentMethod"
    - path: "apps/backend/app/modules/online_payments/models.py"
      provides: "save_payment_method column on OnlinePayment"
      contains: "save_payment_method"
  key_links:
    - from: "apps/backend/app/modules/payment_methods/models.py"
      to: "client_payment_methods table"
      via: "__tablename__ + Index with postgresql_where"
      pattern: "postgresql_where=text\\(.unlinked_at IS NULL.\\)"
---

<objective>
Build the data foundation for card-on-file: migration 0052 creating the `client_payment_methods`
table (single-active-card partial unique index) plus a `save_payment_method` intent column on
`online_payments`, the `ClientPaymentMethod` ORM model, and the matching ORM column on
`OnlinePayment`. Then apply the migration against the local stack and verify the schema landed.

Purpose: Every downstream task (module repository/service, webhook upsert, endpoints) reads or
writes these structures. They must exist and be migrate-clean first (PAYM-01/03/04).
Output: Migration 0052, `payment_methods/` package skeleton with `models.py`, updated
`online_payments/models.py`, verified live schema.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-CONTEXT.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md

<interfaces>
<!-- Existing structures the executor builds on. Extracted from codebase. -->
Migration chain: latest is `0051_seed_fit15_promo`; this phase adds `0052_client_payment_methods`
with down_revision = "0051_seed_fit15_promo".

ORM base mixins (apps/backend/app/core/database.py):
  Base, UUIDPkMixin (provides id UUID PK), TimestampMixin (provides created_at/updated_at).

OnlinePayment (apps/backend/app/modules/online_payments/models.py) — existing columns include
client_id, membership_plan_id, pt_package_plan_id, promo_code_id, yookassa_payment_id,
idempotency_key, amount_kopecks, status, confirmation_url, confirmation_type. No SoftDeleteMixin.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write migration 0052 (client_payment_methods + save_payment_method column)</name>
  <files>apps/backend/alembic/versions/0052_client_payment_methods.py</files>
  <read_first>
    - apps/backend/alembic/versions/0046_promo_codes.py (primary analog — create_table shape, op.f() constraint names, gen_random_uuid server_default, func.now())
    - apps/backend/alembic/versions/0050_clients_notif_prefs.py (column-add analog — op.add_column metadata-only pattern)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (migration section, lines 26-128 — copy the exact upgrade/downgrade shape)
  </read_first>
  <action>
    Create migration id `0052_client_payment_methods`, down_revision `0051_seed_fit15_promo`.
    upgrade() does two DDL changes:
    (1) op.create_table `client_payment_methods` with columns: `id` (postgresql.UUID, server_default
    sa.text("gen_random_uuid()")), `client_id` (UUID, NOT NULL), `yookassa_method_id` (Text, NOT NULL —
    plaintext token), `last4` (Text, NOT NULL), `brand` (Text, NOT NULL), `expiry_month` (Integer,
    nullable), `expiry_year` (Integer, nullable), `autopay_enabled` (Boolean, NOT NULL, server_default
    sa.text("false")), `consent_recorded_at` (DateTime(timezone=True), nullable), `unlinked_at`
    (DateTime(timezone=True), nullable), `created_at`/`updated_at` (DateTime(timezone=True), NOT NULL,
    server_default func.now()). PrimaryKeyConstraint via op.f("pk_client_payment_methods").
    ForeignKeyConstraint client_id -> clients.id, name via op.f("fk_client_payment_methods_client_id_clients"),
    ondelete="RESTRICT".
    (2) op.create_index `uq_client_payment_methods_client_id_alive` on (client_id), unique=True,
    postgresql_where=text("unlinked_at IS NULL") — index name is a LITERAL string, NOT wrapped in op.f()
    (per 0034/0037/0046 create_index precedent).
    (3) op.add_column on `online_payments` adding `save_payment_method` Boolean NOT NULL server_default
    sa.text("false") (intent flag read by webhook step 8.5 — PAYM-01).
    downgrade() reverses in order: drop_column save_payment_method, drop_index
    uq_client_payment_methods_client_id_alive, drop_table client_payment_methods.
    No fenced code in this plan — follow the exact pattern in 79-PATTERNS.md.
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check alembic/versions/0052_client_payment_methods.py && uv run python -c "import ast,sys; ast.parse(open('alembic/versions/0052_client_payment_methods.py').read())"</automated>
  </verify>
  <acceptance_criteria>
    - File parses and `ruff check` exits 0.
    - `revision = "0052_client_payment_methods"` and `down_revision = "0051_seed_fit15_promo"` present (grep).
    - String `uq_client_payment_methods_client_id_alive` and `unlinked_at IS NULL` both present.
    - `save_payment_method` add_column on `online_payments` present.
  </acceptance_criteria>
  <done>Migration 0052 created with both DDL changes and a clean downgrade; ruff passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create payment_methods package + ClientPaymentMethod model; add save_payment_method to OnlinePayment</name>
  <files>apps/backend/app/modules/payment_methods/__init__.py, apps/backend/app/modules/payment_methods/models.py, apps/backend/app/modules/online_payments/models.py</files>
  <read_first>
    - apps/backend/app/modules/promo_codes/models.py (exact analog — Base+UUIDPkMixin+TimestampMixin composition, Index with postgresql_where, mapped_column shapes)
    - apps/backend/app/modules/online_payments/models.py (the file being modified — match its mapped_column style; add save_payment_method near promo_code_id/amount_kopecks)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (models section lines 131-205 + the OnlinePayment column snippet lines 570-575)
  </read_first>
  <behavior>
    - ClientPaymentMethod.__tablename__ == "client_payment_methods".
    - Model declares all 9 business columns (client_id, yookassa_method_id, last4, brand, expiry_month,
      expiry_year, autopay_enabled, consent_recorded_at, unlinked_at) plus inherited id/created_at/updated_at.
    - __table_args__ contains the partial unique Index "uq_client_payment_methods_client_id_alive" with
      postgresql_where=text("unlinked_at IS NULL").
    - OnlinePayment gains save_payment_method: Mapped[bool] (NOT NULL, server_default false).
    - Importing the model module does not raise; SQLAlchemy metadata registers the table.
  </behavior>
  <action>
    Create `app/modules/payment_methods/__init__.py` (empty, package marker). Create
    `app/modules/payment_methods/models.py` with `class ClientPaymentMethod(Base, UUIDPkMixin, TimestampMixin)`,
    __tablename__ `client_payment_methods`, columns mirroring migration 0052 exactly (yookassa_method_id Text
    NOT NULL — comment that it is NEVER serialized to the client; expiry_month/expiry_year Integer nullable;
    autopay_enabled Boolean NOT NULL server_default text("false"); consent_recorded_at + unlinked_at
    DateTime(timezone=True) nullable). client_id ForeignKey "clients.id" ondelete="RESTRICT" name
    "fk_client_payment_methods_client_id_clients". __table_args__ = (Index(
    "uq_client_payment_methods_client_id_alive", "client_id", unique=True,
    postgresql_where=text("unlinked_at IS NULL")),). Add `save_payment_method: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default=text("false"))` to OnlinePayment (per PAYM-01 — read by webhook
    step 8.5). Ensure the model module is imported by Alembic's metadata aggregation (follow how
    promo_codes/models.py is wired into env.py / models registry — check and replicate).
  </action>
  <verify>
    <automated>cd apps/backend && uv run python -c "from app.modules.payment_methods.models import ClientPaymentMethod; from app.modules.online_payments.models import OnlinePayment; assert ClientPaymentMethod.__tablename__=='client_payment_methods'; assert hasattr(OnlinePayment,'save_payment_method'); print('ok')" && uv run ruff check app/modules/payment_methods/ app/modules/online_payments/models.py && uv run mypy app/modules/payment_methods/models.py</automated>
  </verify>
  <acceptance_criteria>
    - Import smoke command prints `ok` (model importable, tablename correct, OnlinePayment.save_payment_method exists).
    - `ruff check` and `mypy` exit 0 on the new/modified model files.
    - grep confirms `postgresql_where=text("unlinked_at IS NULL")` in models.py.
  </acceptance_criteria>
  <done>ClientPaymentMethod model + package created; OnlinePayment has save_payment_method; ruff + mypy clean.</done>
</task>

<task type="auto">
  <name>Task 3: Apply migration to local stack and verify schema</name>
  <files>apps/backend/alembic/versions/0052_client_payment_methods.py</files>
  <read_first>
    - apps/backend/alembic.ini (env / db url wiring)
    - .claude memory: backend local stack gotchas (docker compose env reload; stale-image migrate can mask new migrations — rebuild if migration is not detected)
  </read_first>
  <action>
    Run `alembic upgrade head` against the local stack (docker compose). If the new revision is not
    detected, the running container image is stale — rebuild/restart the backend service so the new
    migration file is in the image, then re-run. After upgrade, verify via psql/SQL: the
    `client_payment_methods` table exists with all columns; the partial unique index
    `uq_client_payment_methods_client_id_alive` exists with predicate `unlinked_at IS NULL`; and
    `online_payments` has the `save_payment_method` column. This is a verification-only task — no schema
    is invented here beyond what migration 0052 declares.
  </action>
  <verify>
    <automated>cd apps/backend && uv run alembic upgrade head && uv run alembic current | grep -q 0052_client_payment_methods && echo "MIGRATION_OK"</automated>
  </verify>
  <acceptance_criteria>
    - `alembic current` reports `0052_client_payment_methods` as head (command prints MIGRATION_OK).
    - Schema introspection confirms table `client_payment_methods`, the partial unique index with
      `unlinked_at IS NULL` predicate, and `online_payments.save_payment_method`.
    - `alembic downgrade -1` then `alembic upgrade head` round-trips cleanly (no errors).
  </acceptance_criteria>
  <done>Migration applied to head on the local stack; schema verified to match the model.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB schema → app | Schema is the storage contract for payment tokens; a wrong column nullability or missing constraint corrupts every downstream guarantee |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-79-01 | Information Disclosure | client_payment_methods.yookassa_method_id column | mitigate | Token column NOT NULL plaintext (consistent with existing YooKassa-id handling, no app crypto layer); never selected into any client-facing SELECT (enforced in Plan 02 repository + Plan 04 schema, which omit the column) |
| T-79-02 | Tampering | save_payment_method intent column | mitigate | Server-default false; column is write-once at checkout (Plan 03) and read-only at webhook (Plan 03 step 8.5); no client-writable path to flip it post-checkout |
| T-79-03 | Tampering | Multiple active cards per client (constraint bypass) | mitigate | Partial UNIQUE `uq_client_payment_methods_client_id_alive` on client_id WHERE unlinked_at IS NULL — DB enforces single active card; webhook upsert uses ON CONFLICT on this constraint |
| T-79-SC | Tampering | uv/alembic install (supply chain) | accept | No new packages installed this phase (uv lock unchanged; SQLAlchemy/Alembic already vetted in prior phases) — no Package Legitimacy Gate needed |
</threat_model>

<verification>
- `uv run ruff check` and `uv run mypy` exit 0 on all new/modified files.
- `alembic upgrade head` reaches `0052_client_payment_methods`; downgrade/upgrade round-trips.
- ClientPaymentMethod importable; OnlinePayment.save_payment_method present.
</verification>

<success_criteria>
- Migration 0052 creates client_payment_methods (with partial unique alive-index) + adds
  save_payment_method to online_payments, and reverses cleanly.
- ClientPaymentMethod ORM model maps the table 1:1 including the partial unique index.
- Live schema verified against the model on the local stack.
</success_criteria>

<output>
Create `.planning/phases/79-payment-methods-foundation-card-on-file/79-01-SUMMARY.md` when done.
</output>
