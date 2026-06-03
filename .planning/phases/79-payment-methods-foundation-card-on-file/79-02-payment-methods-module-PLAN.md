---
phase: 79-payment-methods-foundation-card-on-file
plan: 02
type: execute
wave: 2
depends_on: ["79-01"]
files_modified:
  - apps/backend/app/modules/payment_methods/repository.py
  - apps/backend/app/modules/payment_methods/schemas.py
  - apps/backend/app/modules/payment_methods/service.py
  - apps/backend/.importlinter
autonomous: true
requirements: [PAYM-02, PAYM-03, PAYM-04]
must_haves:
  truths:
    - "Repository can fetch the active (unlinked_at IS NULL) card for a client and returns None when none exists"
    - "Repository can soft-delete the active card (set unlinked_at + autopay_enabled=false), idempotently"
    - "Service get_payment_method returns display-only data with yookassa_method_id NEVER included"
    - "Service patch_autopay enables only with consent (409 consent_required otherwise) and 409 when no active card"
    - "import-linter passes with payment_methods registered and the two new client_portal.service ignore edges"
  artifacts:
    - path: "apps/backend/app/modules/payment_methods/repository.py"
      provides: "Raw-SQL reads + soft-delete + autopay mutation for client_payment_methods"
      contains: "unlinked_at IS NULL"
    - path: "apps/backend/app/modules/payment_methods/schemas.py"
      provides: "ClientPaymentMethodResponse (no token) + ClientAutopayPatchRequest"
      contains: "class ClientPaymentMethodResponse"
    - path: "apps/backend/app/modules/payment_methods/service.py"
      provides: "get_payment_method / unlink_payment_method / patch_autopay"
      contains: "def patch_autopay"
    - path: "apps/backend/.importlinter"
      provides: "payment_methods module registration + ignore edges"
      contains: "app.modules.payment_methods"
  key_links:
    - from: "apps/backend/app/modules/payment_methods/schemas.py"
      to: "ClientPaymentMethodResponse"
      via: "no yookassa_method_id field"
      pattern: "class ClientPaymentMethodResponse"
    - from: "apps/backend/app/modules/payment_methods/service.py"
      to: "repository.fetch_active_payment_method"
      via: "consent gate before mutation"
      pattern: "consent_required"
---

<objective>
Build the `payment_methods/` domain module: a raw-SQL repository (active-card read, soft-delete,
autopay mutation), client-safe Pydantic schemas (response excludes the token; autopay-patch request),
and a service enforcing the ФЗ-376 consent gate (PAYM-04) and 200/null + idempotent-delete discipline.
Register the new module in `.importlinter` with the two `client_portal.service` ignore edges.

Purpose: This is the reusable business core the four endpoints (Plan 04) call. Isolating it here keeps
the router thin and the contract testable independent of HTTP (PAYM-02/03/04).
Output: repository.py, schemas.py, service.py, updated .importlinter.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-CONTEXT.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md
@apps/backend/app/modules/payment_methods/models.py

<interfaces>
<!-- Contracts the executor must build against. Extracted from codebase + Plan 01. -->
ClientPaymentMethod (Plan 01, app/modules/payment_methods/models.py): columns id, client_id,
yookassa_method_id, last4, brand, expiry_month, expiry_year, autopay_enabled, consent_recorded_at,
unlinked_at, created_at, updated_at. Partial unique on client_id WHERE unlinked_at IS NULL.

app/core/schemas.py: ResponseData base — provides alias_generator=to_camel + extra='forbid'.
app/core/exceptions.py: ConflictError, NotFoundError (subclasses of AppError; carry stable code=; bubble
to _app_error_handler; never caught in service).

Caller-owns-txn discipline (D-32-10/D-49-19): service functions flush only, NEVER session.commit().

.importlinter (apps/backend/.importlinter):
  - [importlinter:contract:modules-independent] at line 13; module list around lines 37-58
    (app.modules.promo_codes at line 42 — add payment_methods nearby).
  - ignore_imports block: existing client_portal.service -> promo_codes.{models,service} at lines 186-187.
  - unmatched_ignore_imports_alerting = warn (line 196) keeps forward-declared edges green.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Repository — active-card read, soft-delete, autopay mutation (raw SQL)</name>
  <files>apps/backend/app/modules/payment_methods/repository.py</files>
  <read_first>
    - apps/backend/app/modules/client_portal/repository.py (D-54-08 raw-SQL discipline — text(), :name binds, .mappings().one_or_none(), UUID->str)
    - apps/backend/app/modules/payment_methods/models.py (the table this reads/writes)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (repository section lines 209-297 — fetch_active_payment_method + unlink_payment_method patterns)
  </read_first>
  <behavior>
    - fetch_active_payment_method(session, client_id) returns a dict of display+autopay fields
      (id, last4, brand, expiry_month, expiry_year, autopay_enabled, consent_recorded_at, created_at)
      for the row WHERE client_id=:client_id AND unlinked_at IS NULL; returns None when absent.
      The SELECT MUST NOT include yookassa_method_id.
    - unlink_payment_method(session, client_id) sets unlinked_at=now() + autopay_enabled=false on the
      active row; returns True if a row was unlinked, False if none existed (idempotency feeds 204 no-op).
    - set_autopay(session, client_id, *, enabled, stamp_consent) updates autopay_enabled and, when
      stamp_consent is True, consent_recorded_at=now(); disable never touches consent_recorded_at.
  </behavior>
  <action>
    Create `app/modules/payment_methods/repository.py` with module docstring stating the D-54-08 raw-SQL
    discipline (from sqlalchemy import text; :name binds; cast UUIDs to str; .mappings().one_or_none()).
    Implement: `fetch_active_payment_method(session, client_id) -> dict | None` selecting
    id,last4,brand,expiry_month,expiry_year,autopay_enabled,consent_recorded_at,created_at WHERE
    client_id=:client_id AND unlinked_at IS NULL (NEVER select yookassa_method_id).
    `unlink_payment_method(session, client_id) -> bool` doing SELECT id ... FOR UPDATE then UPDATE
    SET unlinked_at=now(), autopay_enabled=false WHERE id=:id; return False if no active row.
    `set_autopay(session, client_id, *, enabled: bool, stamp_consent: bool) -> None` doing UPDATE
    client_payment_methods SET autopay_enabled=:enabled [, consent_recorded_at=now() when stamp_consent]
    WHERE client_id=:client_id AND unlinked_at IS NULL. No session.commit() anywhere (caller owns txn).
    Cast all UUID binds to str.
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app/modules/payment_methods/repository.py && uv run mypy app/modules/payment_methods/repository.py && uv run python -c "from app.modules.payment_methods import repository; assert hasattr(repository,'fetch_active_payment_method') and hasattr(repository,'unlink_payment_method') and hasattr(repository,'set_autopay'); print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - Import smoke prints `ok`; ruff + mypy exit 0.
    - grep confirms `unlinked_at IS NULL` present and `yookassa_method_id` ABSENT from any SELECT
      (the only mention, if any, is a comment).
    - No `session.commit(` in the file.
  </acceptance_criteria>
  <done>Repository exposes active-read (token-free), idempotent soft-delete, and autopay mutation; ruff+mypy clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Schemas + service with ФЗ-376 consent gate</name>
  <files>apps/backend/app/modules/payment_methods/schemas.py, apps/backend/app/modules/payment_methods/service.py</files>
  <read_first>
    - apps/backend/app/modules/client_portal/schemas.py (ResponseData base, camelCase alias, response/request shapes)
    - apps/backend/app/modules/promo_codes/service.py (structlog logger, ConflictError discipline, no-commit caller-owns-txn)
    - apps/backend/app/core/exceptions.py (ConflictError/NotFoundError signatures + code=)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (schemas lines 301-352 + service lines 356-411)
  </read_first>
  <behavior>
    - ClientPaymentMethodResponse has id, last4, brand, expiry_month|None, expiry_year|None,
      autopay_enabled, consent_recorded_at|None — and NO yookassa_method_id field.
    - ClientAutopayPatchRequest has enabled: bool and consent_acknowledged: bool = False; extra='forbid'.
    - get_payment_method(session, client_id) returns ClientPaymentMethodResponse | None (None passes
      through to a 200/null envelope at the router).
    - unlink_payment_method(session, client_id) is idempotent (returns without error when no active card).
    - patch_autopay: enable with no active card -> ConflictError("no_active_payment_method");
      enable with consent_acknowledged=False -> ConflictError("consent_required") and consent is stamped
      only when enabling with acknowledgement; disable succeeds with an active card and does not touch
      consent_recorded_at; returns the refreshed ClientPaymentMethodResponse.
  </behavior>
  <action>
    Create `schemas.py` with `ClientPaymentMethodResponse(ResponseData)` (fields above — NEVER add
    yookassa_method_id) and `ClientAutopayPatchRequest(ResponseData)` (enabled: bool; consent_acknowledged:
    bool = False). Create `service.py` with `_log = structlog.get_logger("modules.payment_methods.service")`
    and three functions delegating to repository. `get_payment_method` -> fetch_active then build response
    (or None). `unlink_payment_method` -> repository.unlink_payment_method (ignore the bool — caller returns
    204 regardless; idempotent). `patch_autopay` -> fetch_active first; if None and payload.enabled raise
    ConflictError("no_active_payment_method"); if None and not enabled raise
    ConflictError("no_active_payment_method") (cannot toggle a card that does not exist); if enabling and
    not payload.consent_acknowledged raise ConflictError("consent_required"); else call
    repository.set_autopay(enabled=payload.enabled, stamp_consent=(payload.enabled and
    payload.consent_acknowledged)), re-fetch, return ClientPaymentMethodResponse. No session.commit().
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app/modules/payment_methods/schemas.py app/modules/payment_methods/service.py && uv run mypy app/modules/payment_methods/schemas.py app/modules/payment_methods/service.py && uv run python -c "from app.modules.payment_methods.schemas import ClientPaymentMethodResponse, ClientAutopayPatchRequest; assert 'yookassa_method_id' not in ClientPaymentMethodResponse.model_fields; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - Import smoke prints `ok` AND asserts yookassa_method_id is NOT a model field of the response.
    - ruff + mypy exit 0 on both files.
    - grep confirms `consent_required` and `no_active_payment_method` in service.py; no `session.commit(`.
  </acceptance_criteria>
  <done>Token-free response schema + autopay-patch request + consent-gated service implemented; ruff+mypy clean.</done>
</task>

<task type="auto">
  <name>Task 3: Register payment_methods in .importlinter (module + two ignore edges)</name>
  <files>apps/backend/.importlinter</files>
  <read_first>
    - apps/backend/.importlinter (modules-independent contract at line 13; module list ~37-58; ignore_imports block ~186-189 with the promo_codes precedent)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (importlinter section lines 619-642 — exact entries to add)
  </read_first>
  <action>
    Add `app.modules.payment_methods` to the `modules-independent` module list (near
    `app.modules.promo_codes` at ~line 42), with a brief Phase 79 comment. In the ignore_imports block,
    after the existing `app.modules.client_portal.service -> app.modules.promo_codes.*` lines, add:
    `app.modules.client_portal.service -> app.modules.payment_methods.service` and
    `app.modules.client_portal.service -> app.modules.payment_methods.repository`
    (Option B direct edges, mirroring the promo_codes precedent — these are forward-declared now and
    consumed by Plan 04's router/service wiring; unmatched_ignore_imports_alerting=warn keeps the build
    green until then). Do NOT add any integrations-layer ignore edge (webhook step 8.5 in Plan 03 uses
    raw SQL — zero new edges per the locked D-decision).
  </action>
  <verify>
    <automated>cd apps/backend && uv run lint-imports</automated>
  </verify>
  <acceptance_criteria>
    - `lint-imports` exits 0.
    - grep confirms `app.modules.payment_methods` in the module list and both new
      `client_portal.service -> payment_methods.{service,repository}` ignore edges present.
    - No new edge from the integrations layer was added.
  </acceptance_criteria>
  <done>payment_methods registered in import-linter with the two ignore edges; lint-imports green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| service ↔ repository | The service is the only place the ФЗ-376 consent gate is enforced before a state change |
| repository → response projection | The repository SELECT is the last line of defense against leaking the token |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-79-04 | Information Disclosure | ClientPaymentMethodResponse / repository SELECT | mitigate | Response schema has no yookassa_method_id field (asserted in Task 2 verify); repository SELECT omits the token column (Task 1 grep gate) |
| T-79-05 | Elevation of Privilege | Autopay enable without consent (ФЗ-376) | mitigate | patch_autopay raises ConflictError("consent_required") when enabling without consent_acknowledged; consent_recorded_at stamped only on consented enable |
| T-79-06 | Tampering | Toggling/deleting a non-owned card | mitigate | All repository functions filter by client_id (supplied by the router from the principal in Plan 04) AND unlinked_at IS NULL — no row id is accepted from the caller |
| T-79-SC | Tampering | uv install (supply chain) | accept | No new packages; uv lock unchanged |
</threat_model>

<verification>
- ruff + mypy exit 0 on repository.py, schemas.py, service.py.
- lint-imports exits 0.
- Response schema provably excludes the token; service enforces consent + no-active-card 409s.
</verification>

<success_criteria>
- payment_methods module exposes a token-free read, idempotent soft-delete, and consent-gated autopay
  mutation, all caller-owns-txn.
- import-linter passes with the module registered and the two forward-declared ignore edges.
</success_criteria>

<output>
Create `.planning/phases/79-payment-methods-foundation-card-on-file/79-02-SUMMARY.md` when done.
</output>
