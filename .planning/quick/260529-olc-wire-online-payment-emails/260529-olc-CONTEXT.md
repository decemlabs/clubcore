# Quick Task 260529-olc: Wire online-payment email templates into the dispatcher — Context

**Gathered:** 2026-05-29
**Status:** Ready for planning (locked email copy OWNER-SIGNED-OFF below — bake verbatim)

<domain>
## Task Boundary

Close the email-wiring gap found in Phase 67 RUN-03 (Finding RUN-03-F1). The 4 Phase-52 online-payment email identifiers are declared + registered in `LOCKED_EMAIL_TEMPLATES` but have NO rendered copy and are NOT resolvable by the dispatcher → the email channel for online-payment notifications **silently no-ops** (`_dispatch_email` calls `dispatcher(template_id="EMAIL_ONLINE_PAYMENT_*")` → `_resolve_template` raises `KeyError` → swallowed by the best-effort `try/except … continue`). Only the Telegram DM is delivered today.

Fix = (1) author the 4 locked `EmailTemplate` records, (2) add the `online_payments` branch to the dispatcher's `_resolve_template`, (3) integration test proving all 4 kinds actually send via email (no silent KeyError).
</domain>

<decisions>
## OWNER SIGN-OFF — locked Russian email copy (approved 2026-05-29, mirrors the DM copy signed 2026-05-23)

Bake these VERBATIM. Subjects are pure `Final[str]` literals (no interpolation, D-45-19). Bodies are Jinja templates. **Jinja variable names MUST match the dispatcher callsite context in `online_payments/tasks.py` exactly** (see var map). Footer line `{CLUB_BRAND} · noreply@mail.clubcore.ru` on every template (CLUB_BRAND renders "Sportzal" — brand kept per D-62-02; domain is clubcore.ru per 260529-ll9).

### 1. EMAIL_ONLINE_PAYMENT_SUCCEEDED — client-facing
- **Subject:** `Оплата получена`
- **Body:** `Здравствуйте, {{ first_name }}! Оплата на сумму {{ amount_rub }} успешно получена. Ваш абонемент / пакет тренировок активирован. Ждём вас в зале!`
- **Vars:** `first_name`, `amount_rub`

### 2. EMAIL_ONLINE_PAYMENT_REFUNDED — client-facing
- **Subject:** `Возврат обработан`
- **Body:** `Здравствуйте, {{ first_name }}! Возврат на сумму {{ amount_rub }} успешно обработан. Средства поступят на ваш счёт в течение нескольких рабочих дней. Если у вас есть вопросы — обратитесь к администратору.`
- **Vars:** `first_name`, `amount_rub`

### 3. EMAIL_ONLINE_PAYMENT_CANCELED — OWNER-ALERT (NOT-05; never to client)
- **Subject:** `Платёж отменён — требуется проверка`
- **Body:** `[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Платёж отменён. payment_id: {{ payment_id }}, yookassa_payment_id: {{ yookassa_payment_id }}. Требуется проверка.`
- **Vars:** `payment_id`, `yookassa_payment_id`

### 4. EMAIL_FISCAL_RECEIPT_FAILED — OWNER-ALERT (NOT-04)
- **Subject:** `Ошибка фискального чека — требуется проверка`
- **Body:** `[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Ошибка формирования фискального чека. payment_id: {{ payment_id }}, причина: {{ failure_reason }}. Требуется ручная проверка в ЮKassa.`
- **Vars:** `payment_id`, `failure_reason`

### Dispatcher context var map (from online_payments/tasks.py, verified 2026-05-29)
| template_id | kind | vars passed by dispatcher() |
|---|---|---|
| EMAIL_ONLINE_PAYMENT_SUCCEEDED | payment_succeeded | `first_name`, `amount_rub` |
| EMAIL_ONLINE_PAYMENT_REFUNDED | refund_succeeded | `first_name`, `amount_rub` |
| EMAIL_ONLINE_PAYMENT_CANCELED | payment_canceled | `payment_id`, `yookassa_payment_id` |
| EMAIL_FISCAL_RECEIPT_FAILED | fiscal_failed | `payment_id`, `failure_reason` |

The template Jinja vars MUST be exactly these names — do NOT rename to client_name/amount (the dispatcher already passes first_name/amount_rub).

### Claude's discretion
- Exact HTML structure (`<h1>` subject + `<p>` lines) — mirror `payments/email_templates.py` (the closest existing pattern).
- Whether `amount_rub` is pre-formatted upstream — check the callsite; pass through verbatim (do NOT add NBSP, mirror D-45-17).
</decisions>

<scope_boundaries>
## IN SCOPE
1. `apps/backend/app/modules/online_payments/email_templates.py` — add a `TEMPLATES: Final[dict[str, EmailTemplate]]` dict with the 4 records above. Mirror `payments/email_templates.py` shape: frozen `EmailTemplate` dataclass (subject/html/text), `_ENV = SandboxedEnvironment(autoescape=True)` + `_ENV_TEXT = SandboxedEnvironment(autoescape=False)`, `CLUB_BRAND` footer, RUF001 noqa on Cyrillic lines. Keep the existing `Final[str]` identifier constants (they satisfy the AST gate doc + import-linter). Do NOT change the `tasks.py` callsites (they already use literal `template_id="..."` per the AST gate — INFRA-11).
2. `apps/backend/app/integrations/email/dispatcher.py` `_resolve_template` — add `from app.modules.online_payments.email_templates import TEMPLATES as ONLINE_PAYMENTS_TEMPLATES` + an `if template_id in ONLINE_PAYMENTS_TEMPLATES: return ONLINE_PAYMENTS_TEMPLATES[template_id]` branch (place it alongside the existing 5). **The import-linter ignore ALREADY EXISTS** at `apps/backend/.importlinter:189` (`app.integrations.email.dispatcher -> app.modules.online_payments.email_templates`, Phase 47 INFRA-40) — NO new ignore line needed; just confirm `lint-imports` stays green.
3. Integration test proving the email channel actually sends for ALL 4 template_ids (resolve + render succeed; no KeyError; the rendered subject/body match the locked copy). Mirror existing dispatcher/email render tests (e.g. `tests/unit/test_*email*` or `tests/integration/.../email`). At minimum a render/resolve test per template_id asserting the locked subject + a body substring + that all 4 vars interpolate.

## OUT OF SCOPE / GUARDS
- Do NOT touch the Telegram DM copy in `online_payments/notifications.py` (already signed off).
- Do NOT change `tasks.py` dispatcher callsites or the swallow-on-error wrapper behavior (the fix is making resolution succeed, not changing error handling).
- No new ORM entity, no Alembic migration, no router/schema change → `openapi.json` unaffected.
- Do NOT alter `LOCKED_EMAIL_TEMPLATES` membership (the 4 IDs are already registered, 15→19, Phase 52).
- `apps/admin-web` frozen.
</scope_boundaries>

<verification>
## Done = green gates + email actually resolves
- `_resolve_template("EMAIL_ONLINE_PAYMENT_SUCCEEDED")` (and the other 3) returns an `EmailTemplate` (no KeyError).
- Each template renders with its dispatcher-supplied vars → subject == locked literal, body contains the locked phrasing, all `{{ vars }}` interpolated (no leftover `{{`).
- `cd apps/backend && uv run ruff check app && uv run ruff format --check app && uv run mypy --strict app && uv run lint-imports` all exit 0 (import-linter still 3 contracts kept — the online_payments→dispatcher edge ignore already present).
- New integration/unit test(s) pass; full `pytest` green.
- AST gate `tests/unit/test_locked_email_templates_ast.py` still passes (callsites unchanged, literal template_ids).
</verification>

<canonical_refs>
## Canonical References
- Source of the gap: Phase 67 RUN-03 Finding RUN-03-F1 (`.planning/handoff/v1.11-19-template-countersign.md` + `v1.11-OPERATOR-EVIDENCE.md`).
- Pattern to mirror: `apps/backend/app/modules/payments/email_templates.py` (EmailTemplate dataclass + TEMPLATES dict + sandboxed Jinja + CLUB_BRAND footer).
- Dispatcher walker: `apps/backend/app/integrations/email/dispatcher.py` `_resolve_template` (5 existing branches).
- Import-linter ignore (already present): `apps/backend/.importlinter:189`.
- DM copy mirrored (already signed off 2026-05-23): `online_payments/notifications.py` ONLINE_PAYMENT_{SUCCEEDED,REFUNDED,CANCELED}_DM + FISCAL_RECEIPT_FAILED_DM.
</canonical_refs>
