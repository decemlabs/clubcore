---
phase: 45-email-notification-mirrors
plan: 06b
type: execute
wave: 2
depends_on: [04, 05, 06]
files_modified:
  - apps/backend/app/integrations/email/dispatcher.py
  - apps/backend/.importlinter
autonomous: true
requirements: [NOTIFY-08, NOTIFY-10, NOTIFY-12]
must_haves:
  truths:
    - "dispatcher._resolve_template extended with 3 new function-scoped imports + 3 if-blocks above the existing raise KeyError (per PATTERNS.md correction #3)"
    - "_resolve_template('EMAIL_EXPIRING_7D_VARIANT_A') returns an EmailTemplate (does NOT raise KeyError) — proves memberships templates wired"
    - "_resolve_template('EMAIL_BOOKING_CONFIRMED') returns an EmailTemplate — proves bookings templates wired"
    - "_resolve_template('EMAIL_PAYMENT_RECEIPT_SALE') returns an EmailTemplate — proves payments templates wired"
    - "_resolve_template('DOES_NOT_EXIST') still raises KeyError (negative case preserved)"
    - ".importlinter modules-independent gains 3 ignore_imports entries for integrations.email → modules.{memberships,bookings,payments} so the new function-scoped imports do not break the contract"
    - "uv run lint-imports exits 0 after the additions"
  artifacts:
    - path: "apps/backend/app/integrations/email/dispatcher.py"
      contains: "MEMBERSHIPS_TEMPLATES"
    - path: "apps/backend/app/integrations/email/dispatcher.py"
      contains: "BOOKINGS_TEMPLATES"
    - path: "apps/backend/app/integrations/email/dispatcher.py"
      contains: "PAYMENTS_TEMPLATES"
    - path: "apps/backend/.importlinter"
      contains: "app.modules.memberships.email_templates"
  key_links:
    - from: "dispatcher._resolve_template"
      to: "memberships/bookings/payments email_templates TEMPLATES dicts"
      via: "3 function-scoped imports + 3 if-block branches inserted ABOVE the existing raise KeyError"
    - from: ".importlinter modules-independent contract"
      to: "the 3 new function-scoped imports"
      via: "3 ignore_imports allowlist entries — overrides D-45-24's 'zero .importlinter changes' claim per PATTERNS.md correction #3"
  references: [D-45-24, "NOTIFY-08", "NOTIFY-10", "NOTIFY-12", "PATTERNS.md correction #3", "BLOCKER-1 from Phase 45 checker pass"]
---

<objective>
Split out from the original Plan 06 per checker BLOCKER-1. The dispatcher walker extension + .importlinter ignore_imports additions REQUIRE Plans 04 (memberships templates) + 05 (bookings templates) + 06 (payments templates) to have landed first — the verify command imports and calls `_resolve_template` for template IDs from all three.

Two tightly-coupled file edits:

1. Extend `app/integrations/email/dispatcher.py:_resolve_template` walker (PATTERNS.md correction #3) with 3 new function-scoped imports + 3 if-blocks so memberships/bookings/payments template lookups don't raise KeyError at runtime.
2. Add 3 `ignore_imports` entries to `apps/backend/.importlinter` so the dispatcher's intentional function-scope imports of `app.modules.*` don't break the integrations⊥modules contract. This explicitly overrides D-45-24's "zero .importlinter changes" claim per PATTERNS.md correction #3 — without this, runtime fails on first non-auth/non-users dispatch.

Output: 2 file edits, no new files. Verify command exercises all 3 new template registries + `uv run lint-imports`.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/45-email-notification-mirrors/45-CONTEXT.md
@.planning/phases/45-email-notification-mirrors/45-PATTERNS.md
@apps/backend/app/integrations/email/dispatcher.py
@apps/backend/.importlinter
@apps/backend/app/core/audit.py
@.planning/phases/45-email-notification-mirrors/45-04-SUMMARY.md
@.planning/phases/45-email-notification-mirrors/45-05-SUMMARY.md
@.planning/phases/45-email-notification-mirrors/45-06-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend dispatcher._resolve_template walker with 3 new function-scoped imports + 3 if-blocks</name>
  <files>apps/backend/app/integrations/email/dispatcher.py</files>
  <read_first>
    - apps/backend/app/integrations/email/dispatcher.py (entire file — focus on lines 47-90 docstring + _resolve_template; note: existing AUTH_TEMPLATES + USERS_TEMPLATES function-scoped imports + if-blocks)
    - apps/backend/app/modules/memberships/email_templates.py (Plan 04 output — confirm TEMPLATES dict + key names)
    - apps/backend/app/modules/bookings/email_templates.py (Plan 05 output — confirm TEMPLATES dict + key names)
    - apps/backend/app/modules/payments/email_templates.py (Plan 06 output — confirm TEMPLATES dict + key names)
    - .planning/phases/45-email-notification-mirrors/45-PATTERNS.md §"app/integrations/email/dispatcher.py" + §"CRITICAL PRE-PLANNING CORRECTIONS" item 3
  </read_first>
  <behavior>
    - _resolve_template("EMAIL_PAYMENT_RECEIPT_SALE") returns the matching EmailTemplate (does NOT raise KeyError).
    - _resolve_template("EMAIL_EXPIRING_7D_VARIANT_A") returns the matching EmailTemplate.
    - _resolve_template("EMAIL_BOOKING_CONFIRMED") returns the matching EmailTemplate.
    - _resolve_template("DOES_NOT_EXIST") still raises KeyError.
    - Existing AUTH_TEMPLATES + USERS_TEMPLATES lookups still work (regression negative).
  </behavior>
  <action>
    Open apps/backend/app/integrations/email/dispatcher.py. Locate the _resolve_template function (around lines 75-87 per PATTERNS.md). It currently looks like:

    def _resolve_template(template_id: str) -> Any:
        from app.modules.auth.email_templates import TEMPLATES as AUTH_TEMPLATES
        from app.modules.users.email_templates import TEMPLATES as USERS_TEMPLATES
        if template_id in AUTH_TEMPLATES:
            return AUTH_TEMPLATES[template_id]
        if template_id in USERS_TEMPLATES:
            return USERS_TEMPLATES[template_id]
        raise KeyError(...)

    Extend it with 3 ADDITIONAL function-scoped imports + 3 ADDITIONAL if-blocks BEFORE the existing `raise KeyError(...)`. Insert order: MEMBERSHIPS first, BOOKINGS second, PAYMENTS third (matches Phase 45 plan landing order — Plan 45-04 / 05 / 06):

    from app.modules.memberships.email_templates import TEMPLATES as MEMBERSHIPS_TEMPLATES
    from app.modules.bookings.email_templates import TEMPLATES as BOOKINGS_TEMPLATES
    from app.modules.payments.email_templates import TEMPLATES as PAYMENTS_TEMPLATES

    if template_id in MEMBERSHIPS_TEMPLATES:
        return MEMBERSHIPS_TEMPLATES[template_id]
    if template_id in BOOKINGS_TEMPLATES:
        return BOOKINGS_TEMPLATES[template_id]
    if template_id in PAYMENTS_TEMPLATES:
        return PAYMENTS_TEMPLATES[template_id]

    Preserve the existing two imports + two if-blocks for AUTH_TEMPLATES + USERS_TEMPLATES verbatim. The 3 new imports MUST be function-scoped (inside _resolve_template body) — NOT module-level — to mirror the Phase 42 / 44 pattern and keep import graph cycles bounded.

    If the docstring lines 47-51 already mention "Phases 44/45 extend this walker", update it to reflect that Phase 45 templates are now wired. Otherwise leave the docstring untouched.
  </action>
  <verify>
    <automated>cd apps/backend &amp;&amp; uv run python -c "from app.integrations.email.dispatcher import _resolve_template; t1 = _resolve_template('EMAIL_PAYMENT_RECEIPT_SALE'); t2 = _resolve_template('EMAIL_EXPIRING_7D_VARIANT_A'); t3 = _resolve_template('EMAIL_BOOKING_CONFIRMED'); t4 = _resolve_template('EMAIL_BOOKING_REMINDER_24H'); assert t1 is not None and t2 is not None and t3 is not None and t4 is not None; raised = False\ntry:\n    _resolve_template('DOES_NOT_EXIST')\nexcept KeyError:\n    raised = True\nassert raised, 'expected KeyError for unknown template_id'\nprint('ok')"</automated>
  </verify>
  <done>
    - grep -c "MEMBERSHIPS_TEMPLATES\|BOOKINGS_TEMPLATES\|PAYMENTS_TEMPLATES" apps/backend/app/integrations/email/dispatcher.py returns ≥6 (3 imports + 3 lookups).
    - cd apps/backend && uv run python -c "from app.integrations.email.dispatcher import _resolve_template; _resolve_template('EMAIL_PAYMENT_RECEIPT_SALE')" does NOT raise KeyError.
    - cd apps/backend && uv run python -c "from app.integrations.email.dispatcher import _resolve_template; _resolve_template('EMAIL_EXPIRING_7D_VARIANT_A')" does NOT raise KeyError.
    - cd apps/backend && uv run python -c "from app.integrations.email.dispatcher import _resolve_template; _resolve_template('EMAIL_BOOKING_CONFIRMED')" does NOT raise KeyError.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 3 ignore_imports entries to apps/backend/.importlinter + run lint-imports</name>
  <files>apps/backend/.importlinter</files>
  <read_first>
    - apps/backend/.importlinter (entire file — locate the modules-independent contract block + existing ignore_imports for app.modules.auth.email_templates / app.modules.users.email_templates)
    - .planning/phases/45-email-notification-mirrors/45-PATTERNS.md §"CRITICAL PRE-PLANNING CORRECTIONS" item 3 (documents the necessity of the override)
  </read_first>
  <behavior>
    - apps/backend/.importlinter gains 3 new ignore_imports entries below the existing ones, in the exact syntactic shape the file uses.
    - cd apps/backend && uv run lint-imports exits 0 (modules-independent contract green) — proves the new function-scoped imports do NOT trip the contract.
  </behavior>
  <action>
    Open apps/backend/.importlinter. Locate the modules-independent contract block (contains existing ignore_imports lines like `app.integrations.email.dispatcher -> app.modules.auth.email_templates` and `... -> app.modules.users.email_templates`).

    Add 3 new ignore_imports entries below the existing ones, in the same TOML/INI format used by the file:

    app.integrations.email.dispatcher -> app.modules.memberships.email_templates
    app.integrations.email.dispatcher -> app.modules.bookings.email_templates
    app.integrations.email.dispatcher -> app.modules.payments.email_templates

    Match the exact syntactic shape of the existing entries (whitespace, arrow direction, prefixes — read the file first to confirm).

    This explicitly overrides D-45-24's "zero .importlinter changes" claim — PATTERNS.md correction #3 documents that the entries are mandatory: without them, lint-imports fails on the new function-scoped imports because import-linter analyses function-body imports.

    Do NOT touch any other contract entries. Do NOT add module-level imports anywhere — the function-scope discipline is what keeps the contract bounded.
  </action>
  <verify>
    <automated>cd apps/backend &amp;&amp; uv run lint-imports</automated>
  </verify>
  <done>
    - grep -c "app.modules.memberships.email_templates\|app.modules.bookings.email_templates\|app.modules.payments.email_templates" apps/backend/.importlinter returns ≥3.
    - cd apps/backend && uv run lint-imports exits 0 (modules-independent contract green).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| dispatcher._resolve_template → modules/*/email_templates | function-scope import bounded by import-linter ignore_imports whitelist |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-45-06b-01 | Tampering | Future devs adding new modules without updating dispatcher walker | mitigate | PATTERNS.md + dispatcher docstring document the extension protocol |
| T-45-06b-02 | Elevation of privilege | integrations imports modules — architectural inversion | accept | Bounded by .importlinter ignore_imports allowlist; only template registries imported (no business logic) |
</threat_model>

<verification>
- cd apps/backend && uv run lint-imports exits 0.
- cd apps/backend && uv run python -c "from app.integrations.email.dispatcher import _resolve_template; _resolve_template('EMAIL_PAYMENT_RECEIPT_SALE'); _resolve_template('EMAIL_EXPIRING_7D_VARIANT_A'); _resolve_template('EMAIL_BOOKING_CONFIRMED')" exits 0.
</verification>

<success_criteria>
- dispatcher walker resolves all 12 Phase 45 template IDs without raising KeyError.
- import-linter green after the 3 new ignore_imports entries.
- Negative case preserved: _resolve_template('DOES_NOT_EXIST') still raises KeyError.
</success_criteria>

<output>
After completion, create .planning/phases/45-email-notification-mirrors/45-06b-SUMMARY.md.
</output>
