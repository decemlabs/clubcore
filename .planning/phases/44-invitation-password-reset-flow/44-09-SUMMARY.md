---
phase: 44-invitation-password-reset-flow
plan: 09
subsystem: auth
status: completed
completed_date: 2026-05-20
duration_minutes: ~12
tags:
  - unit-test
  - template-snapshot
  - ast-walker
  - locked-email-templates
  - anti-oracle
  - D-44-25
  - D-44-26
  - D-44-36
  - D-44-OWNER-COPY-LOCK
requirements:
  - RESET-03
depends_on:
  - 44-05
provides:
  - "Deterministic render assertions guarding D-44-OWNER-COPY-LOCK Russian copy for PASSWORD_RESET_EMAIL"
  - "AST-gate positive assertion that auth.password_reset_service.request_password_reset uses literal template_id=\"PASSWORD_RESET_EMAIL\""
affects:
  - "apps/backend/tests/unit/auth/__init__.py"
  - "apps/backend/tests/unit/auth/test_password_reset_email_render.py"
  - "apps/backend/tests/unit/test_locked_email_templates_ast.py"
key_files_created:
  - "apps/backend/tests/unit/auth/__init__.py"
  - "apps/backend/tests/unit/auth/test_password_reset_email_render.py"
key_files_modified:
  - "apps/backend/tests/unit/test_locked_email_templates_ast.py"
decisions:
  - "D-44-OWNER-COPY-LOCK enforced via pattern-match fragment assertions (HTML + text), not byte-exact golden-file (consistent with Phase 43 plan 13 approach for HTML — full snapshot is brittle to whitespace; fragment assertions still catch every owner-copy mutation)"
  - "AST walker logic INLINED in the new test function (NOT delegated to the production `_iter_dispatcher_calls` helper) per D-43-33 anti-weakening discipline — future helper refactor cannot silently weaken the PASSWORD_RESET_EMAIL gate"
  - "Pinned exactly-1 callsite count for PASSWORD_RESET_EMAIL literal in password_reset_service.py (request_password_reset only; confirm/accept never enqueue per D-44-09 / D-44-20). A future second callsite must pass anti-oracle review before this assertion is updated"
commits:
  - efeeec9  # test(44-09): add deterministic PASSWORD_RESET_EMAIL render snapshot tests
  - 38e2fe3  # test(44-09): extend locked-email AST gate with PASSWORD_RESET_EMAIL real-callsite (D-44-36)
metrics:
  tasks: 2
  tests_added: 4
  files_created: 2
  files_modified: 1
---

# Phase 44 Plan 09: PASSWORD_RESET_EMAIL Render + AST Gate Tests Summary

Two test-level safeguards for RESET-03 / D-44-36 landed: (1) 3 deterministic
fragment-assertion render tests for ``TEMPLATES["PASSWORD_RESET_EMAIL"]``
asserting subject + HTML + text are byte-stable AND that the D-44-25
anti-oracle invariant (no ``full_name`` substitution path) holds; (2) 1
positive AST-walker assertion that ``auth.password_reset_service.request_password_reset``
references the literal ``template_id="PASSWORD_RESET_EMAIL"`` exactly once,
mirroring the Phase 42 plan 11 + Phase 43 plan 13 inline-walker pattern.

## What Was Built

### Task 1 — `apps/backend/tests/unit/auth/test_password_reset_email_render.py` (NEW, 130 lines incl. docstring)

Three test functions:

1. **`test_password_reset_email_subject_is_locked_literal`** — asserts
   `tpl.subject == "Восстановление пароля Sportzal"` (D-44-26: Final[str]
   literal, no interpolation; mutation requires re-running D-44-OWNER-COPY-LOCK
   owner sign-off).

2. **`test_password_reset_email_html_renders_deterministic_snapshot`** —
   renders `tpl.html.render(reset_url=…, expires_at_human=…)` with pinned
   fixed inputs and asserts:
   - No unresolved Jinja markers (`{{` / `}}` absent — sandbox actually
     substituted).
   - **D-44-25 anti-oracle invariant**: `full_name`, `{full_name}`, "Анна",
     "Иван" all absent from rendered output.
   - `reset_url` appears exactly 2x (HTML href + visible link body, per
     `<a href="{{ reset_url }}">{{ reset_url }}</a>` at
     `email_templates.py:96`).
   - `expires_at_human` appears exactly 1x.
   - Locked Russian-copy fragments: `<h1>Восстановление пароля Sportzal</h1>`,
     "Перейдите по ссылке", "Ссылка действительна до", "проигнорируйте это
     письмо", `Sportzal · noreply@mail.sportzal.ru`.

3. **`test_password_reset_email_text_renders_deterministic_snapshot`** —
   mirrors Test 2 for the `tpl.text` (`autoescape=False`) render: same
   anti-oracle invariant, `reset_url` exactly 1x in text body, expiry once,
   same Russian-copy fragments, plus a defensive assertion that no HTML tags
   (`<h1>`, `<a `, `<p>`) leak through — guards against the text/html
   template swap regression.

The plan called these "pattern-match tests rather than byte-for-byte snapshot
files" — the alternative would have been a golden-file under
`tests/unit/fixtures/`, which was rejected (per the plan's explicit
guidance) because full-snapshot diffing is brittle to whitespace while
fragment assertions still catch every owner-copy mutation.

A new `apps/backend/tests/unit/auth/__init__.py` (empty file, project
convention — mirrors `users/`, `clients/`, `memberships/`, etc.) was created
to satisfy the package-discovery convention.

### Task 2 — `apps/backend/tests/unit/test_locked_email_templates_ast.py` (EXTENDED, +61 lines)

Appended one new test function:

**`test_password_reset_email_literal_at_password_reset_service_callsite`** —
parses `apps/backend/app/modules/auth/password_reset_service.py`, walks
the AST with an **inlined** `ast.walk(tree)` loop (NOT delegated to
`_iter_dispatcher_calls`), collects every `template_id=<keyword>` kwarg
whose value is an `ast.Constant` of type `str`, and asserts:

- `"PASSWORD_RESET_EMAIL"` is in the collected literals (D-44-36 positive
  assertion — a refactor that swaps the literal for a constant
  e.g. `template_id=PASSWORD_RESET_EMAIL_CONST` would silently bypass
  `test_real_callsites_pass` because the production walker only flags
  *non*-Constant nodes).
- The `PASSWORD_RESET_EMAIL` literal callsite count is **exactly 1**
  (confirmed at `password_reset_service.py:292` inside `request_password_reset`).
  `confirm_password_reset` and `accept_invitation` never enqueue per
  D-44-09 / D-44-20. A future second callsite would trip this assertion
  and force anti-oracle review (D-44-06 envelope parity) before the bound
  is relaxed.

The walker logic is **deliberately inlined** (mirroring the Phase 43
`test_user_invitation_email_literal_at_users_service_callsite` shape verbatim,
which itself mirrors the Phase 42 `test_email_otp_login_real_callsite_present`
shape). Per the D-43-33 anti-weakening discipline noted in STATE.md
Phase 43 plan 13: "walker logic mirrored locally so future
`_iter_dispatcher_calls` refactor cannot weaken the gate." Applied here
verbatim — a future production-walker refactor cannot weaken this
PASSWORD_RESET_EMAIL gate.

## How It Was Built

### Path resolution used in the AST test

```python
service_py = _BACKEND_APP / "modules" / "auth" / "password_reset_service.py"
tree = ast.parse(service_py.read_text(encoding="utf-8"))
```

Where `_BACKEND_APP` is the module-level constant at line 38:

```python
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
```

This matches the EXACT pattern used by both pre-existing positive-callsite
tests (`test_email_otp_login_real_callsite_present` at line 162 uses
`_BACKEND_APP / "modules" / "auth" / "service.py"`;
`test_user_invitation_email_literal_at_users_service_callsite` at line 205
uses `_BACKEND_APP / "modules" / "users" / "service.py"`). No drift; verbatim
mirror.

### AST walk pattern (inlined, verbatim mirror of Phase 43)

```python
found_literal_template_ids: list[str] = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    for kw in node.keywords:
        if (
            kw.arg == "template_id"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            found_literal_template_ids.append(kw.value.value)
```

Identical to the Phase 43 `test_user_invitation_email_literal_at_users_service_callsite`
body — only the file path, expected literal, and assertion message differ.
The additional `password_reset_literal_count == 1` cardinality assertion is
new in this plan (D-44-36 specifically calls for ONE callsite — Phase 43
did not pin cardinality for the USER_INVITATION_EMAIL case).

### Drift from Phase 43 USER_INVITATION_EMAIL test

Minimal:
- File path: `modules/auth/password_reset_service.py` (vs. `modules/users/service.py`).
- Expected literal: `"PASSWORD_RESET_EMAIL"` (vs. `"USER_INVITATION_EMAIL"`).
- Decision-ID lineage in docstring: D-44-36 (vs. D-43-33).
- **NEW**: exactly-1 cardinality assertion on the literal count (per plan
  task 2 acceptance criteria — confirms confirm/accept never enqueue).

## Verification (plan-level)

```bash
$ cd apps/backend && uv run pytest \
    tests/unit/auth/test_password_reset_email_render.py \
    tests/unit/test_locked_email_templates_ast.py -q
.........                                                                [100%]
9 passed in 0.10s

$ cd apps/backend && uv run ruff check \
    tests/unit/auth/test_password_reset_email_render.py \
    tests/unit/test_locked_email_templates_ast.py
All checks passed!

$ cd apps/backend && uv run mypy --strict \
    tests/unit/auth/test_password_reset_email_render.py \
    tests/unit/test_locked_email_templates_ast.py
Success: no issues found in 2 source files
```

All 3 verification gates from the plan pass.

## Deviations from Plan

None — plan executed exactly as written. The single minor adaptation was
to use ruff's auto-`--fix` to strip 15 unused `# noqa: RUF001` directives
from the render-test file (ruff did not flag the Cyrillic-only strings as
ambiguous, so the noqa pragmas were unused). This was applied via
`uv run ruff check --fix` after the initial Write; the resulting file is
functionally identical to what the plan called for.

## Anti-oracle Posture Cross-check (D-44-25 / D-44-OWNER-COPY-LOCK)

The HTML render test fails LOUDLY if a future edit to `TEMPLATES["PASSWORD_RESET_EMAIL"].html`:
- introduces any `{{ full_name }}` Jinja variable (D-44-25 anti-oracle breach),
- mutates the subject `"Восстановление пароля Sportzal"` (D-44-26 violation),
- mutates the locked Russian-copy fragments listed in the "What Was Built"
  section above (D-44-OWNER-COPY-LOCK signed off 2026-05-19 at plan 44-02),
- changes the `reset_url` interpolation count from 2 (HTML) or 1 (text), or
  the `expires_at_human` count from 1 in either,
- drops the `Sportzal · noreply@mail.sportzal.ru` footer.

Any of these mutations REQUIRES the owner to re-run D-27-OWNER-COPY-LOCK
sign-off AND update both this test file AND the 44-02 SUMMARY block-quote
verbatim Russian source. The AST gate test fails LOUDLY if a future edit
to `password_reset_service.py`:
- replaces the literal `template_id="PASSWORD_RESET_EMAIL"` with a constant,
  variable, or f-string (e.g. `template_id=PASSWORD_RESET_EMAIL_CONST`,
  `template_id=tpl_id`, `template_id=f"PASSWORD_RESET_{kind}"`),
- adds a second dispatcher callsite (would trip the cardinality == 1 bound;
  requires explicit anti-oracle review per D-44-06 / D-44-09 envelope parity).

## Self-Check: PASSED

Files exist:
- `apps/backend/tests/unit/auth/__init__.py` — FOUND
- `apps/backend/tests/unit/auth/test_password_reset_email_render.py` — FOUND
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — FOUND (modified)

Commits exist on branch `worktree-agent-a16168f7606d0003c`:
- `efeeec9` — FOUND (test(44-09): add deterministic PASSWORD_RESET_EMAIL render snapshot tests)
- `38e2fe3` — FOUND (test(44-09): extend locked-email AST gate with PASSWORD_RESET_EMAIL real-callsite (D-44-36))

Verification commands all green: pytest 9 passed, ruff All checks passed!, mypy --strict no issues.
