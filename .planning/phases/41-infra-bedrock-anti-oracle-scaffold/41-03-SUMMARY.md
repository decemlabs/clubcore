---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 03
subsystem: infra
tags: [email, locked-templates, ast-gate, frozenset, pre-register, pytest, anti-oracle, owner-copy-lock]

# Dependency graph
requires:
  - phase: 15-infra-bedrock
    provides: "audit.emit literal-only AST walker (apps/backend/tests/unit/test_audit_taxonomy.py) — shape this plan mirrors for the new template_id gate"
  - phase: 41-infra-bedrock-anti-oracle-scaffold/01
    provides: "LOCKED_AUDIT_EVENTS pattern + Phase 41 entry into apps/backend/app/core/audit.py — the file in which LOCKED_EMAIL_TEMPLATES now lives"
provides:
  - "LOCKED_EMAIL_TEMPLATES: frozenset[str] in app/core/audit.py with all 15 v1.6 template identifiers (D-41-12 verbatim)"
  - "Static AST walker test (tests/unit/test_locked_email_templates_ast.py) enforcing literal-only template_id at every get_email_dispatcher()(...) callsite, value resolving to LOCKED_EMAIL_TEMPLATES membership"
  - "Two synthetic-violation fixtures under tests/unit/fixtures/email_ast_violations/ that the walker MUST reject (D-41-13)"
affects:
  - "Phase 42 — first real get_email_dispatcher()(template_id='EMAIL_OTP_LOGIN', ...) callsite ships green without AST-gate churn"
  - "Phase 44 — invitation + password-reset email callsites (USER_INVITATION_EMAIL, PASSWORD_RESET_EMAIL) ship with template names already locked"
  - "Phase 45 — expiring A/B variants, booking lifecycle, payment receipts (11 template-id literals across NOTIFY-08/-10/-12) ship green"
  - "Phase 46 VER-14 — owner sign-off enumerates the 15 constant names from this frozenset (D-27-OWNER-COPY-LOCK / D-39-02 lineage)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Double-Call AST shape detection: outer Call whose .func is itself a Call(Name(id='get_email_dispatcher')) — different from the audit.emit single-Call shape, but reuses the same _resolve_str_literal helper"
    - "Synthetic-violation fixtures live OUTSIDE the walked tree (tests/unit/fixtures/ NOT apps/backend/app/) so they cannot poison other tests; walker explicitly opens them by path"
    - "Pre-register-before-callsite (extending v1.3 INFRA-15 / v1.5 INFRA-24 / 41-01 INFRA-34 lineage to email-template surface)"

key-files:
  created:
    - "apps/backend/tests/unit/test_locked_email_templates_ast.py — AST walker with 3 tests (real callsites pass; bogus literal rejected; non-literal rejected)"
    - "apps/backend/tests/unit/fixtures/email_ast_violations/__init__.py — package marker (empty)"
    - "apps/backend/tests/unit/fixtures/email_ast_violations/bogus_template_id.py — literal 'BOGUS_NOT_LOCKED' synthetic violation"
    - "apps/backend/tests/unit/fixtures/email_ast_violations/raw_subject_string.py — non-literal (variable) template_id synthetic violation"
  modified:
    - "apps/backend/app/core/audit.py — LOCKED_EMAIL_TEMPLATES frozenset declared between LOCKED_AUDIT_EVENTS and emit() per D-41-11/12"

key-decisions:
  - "Walker accepts BOTH positional[0] AND template_id= keyword forms even though Phase 41 D-41-24 makes the Protocol slot keyword-only — cheap robustness against future Protocol-signature drift; the literal-only check fires identically in both forms."
  - "Violation messages include the full prefix `get_email_dispatcher()(template_id=...)` so failing CI output points the developer directly at the call shape; bogus-value violations additionally cite LOCKED_EMAIL_TEMPLATES so the fix-it path (extend the frozenset OR fix the literal) is obvious."
  - "The walker's _collect_violations(py_path) helper is a single-file entry point so the same code services both the prod-tree sweep (test_real_callsites_pass) and the per-fixture assertions — keeps the gate logic single-sourced."
  - "test_real_callsites_pass passes vacuously today (0 violations because no real callsite exists yet); intentional per D-41-12 pre-register-before-callsite discipline. The test will continue to enforce literal-only + frozenset-membership when Phase 42 lands the first real callsite — no AST-gate-churn."

patterns-established:
  - "LOCKED_EMAIL_TEMPLATES + AST walker — second locked-set + AST-gate pair in core/audit.py (LOCKED_AUDIT_EVENTS being the first). Establishes a clean precedent for any future v1.7+ locked-set: declare frozenset in core/audit.py adjacent to existing ones; add tests/unit/test_locked_<name>_ast.py mirroring the walker shape; synthetic-violation fixtures under tests/unit/fixtures/<name>_violations/."
  - "Outside-the-walked-tree fixture placement convention — synthetic-violation fixtures live under tests/unit/fixtures/<gate>_violations/ NOT under apps/backend/app/. Prevents the fixture from being parsed by other gates that also walk apps/backend/app/**/*.py."

requirements-completed: [INFRA-36]

# Metrics
duration: ~10min
completed: 2026-05-18
---

# Phase 41 Plan 03: LOCKED_EMAIL_TEMPLATES + AST Walker Summary

**15 v1.6 email template identifiers pre-locked in `LOCKED_EMAIL_TEMPLATES: frozenset[str]` and guarded by a static AST walker that asserts every `get_email_dispatcher()(template_id=...)` callsite uses a literal name resolving to a member — mirrors v1.2 INFRA-11 `audit.emit` literal-only gate shape (INFRA-36 / D-41-11/12/13).**

## What Shipped

### 1. `LOCKED_EMAIL_TEMPLATES` frozenset (`apps/backend/app/core/audit.py`)

15 identifiers verbatim from D-41-12, grouped by ship-phase + requirement:

| Phase | Requirement | Identifier |
|------|-------------|-----------|
| 42 | AUTH-EM-03 | `EMAIL_OTP_LOGIN` |
| 44 | RESET-03 / USERS-03 | `USER_INVITATION_EMAIL`, `PASSWORD_RESET_EMAIL` |
| 45 | NOTIFY-08 (expiring A/B) | `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` (6 entries) |
| 45 | NOTIFY-10 (booking lifecycle) | `EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`, `EMAIL_BOOKING_REMINDER_24H` |
| 45 | NOTIFY-12 (receipts) | `EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_PAYMENT_RECEIPT_REFUND` |

Declared immediately AFTER the `LOCKED_AUDIT_EVENTS` literal and BEFORE `async def emit(...)` — physical adjacency reinforces the "two locked sets, one file" mental model future maintainers will form when they grep for either name.

### 2. Static AST walker (`apps/backend/tests/unit/test_locked_email_templates_ast.py`)

Three tests:
1. **`test_real_callsites_pass`** — sweeps `apps/backend/app/**/*.py`; asserts 0 violations. Vacuously green today (no real callsite exists yet); Phase 42 will ship the first.
2. **`test_bogus_template_id_is_rejected`** — runs the walker against `bogus_template_id.py` fixture; asserts the violation message cites `'BOGUS_NOT_LOCKED'` AND `LOCKED_EMAIL_TEMPLATES`.
3. **`test_non_literal_template_id_is_rejected`** — runs the walker against `raw_subject_string.py` fixture; asserts the violation message contains `'not a literal'`.

**Detection shape (different from `audit.emit`):**
- `audit.emit(...)` is a single `ast.Call` with `func = Attribute(value=Name('audit'), attr='emit')`.
- `get_email_dispatcher()(...)` is a **double** `ast.Call`: an outer `Call` whose `.func` is itself a `Call` whose `.func.id == 'get_email_dispatcher'`. The walker descends one Call level to identify the dispatcher seam, then inspects the outer Call's `keywords` (preferred) or first positional for the `template_id` argument.

**Argument acceptance:** Both `get_email_dispatcher()("EMAIL_OTP_LOGIN", ...)` (positional) AND `get_email_dispatcher()(template_id="EMAIL_OTP_LOGIN", ...)` (keyword) are accepted by the walker, even though D-41-24 makes the Protocol slot keyword-only. Robustness against future Protocol-signature drift at near-zero cost; the literal-only check fires identically in both forms.

### 3. Synthetic-violation fixtures (`apps/backend/tests/unit/fixtures/email_ast_violations/`)

- `__init__.py` — empty package marker.
- `bogus_template_id.py` — `await get_email_dispatcher()(template_id="BOGUS_NOT_LOCKED", ...)`. Literal value is NOT in `LOCKED_EMAIL_TEMPLATES`.
- `raw_subject_string.py` — `chosen_id = "EMAIL_OTP_LOGIN"; await get_email_dispatcher()(template_id=chosen_id, ...)`. Even though the *value* would be valid, the non-literal `ast.Name` node form must be rejected.

Both fixtures are **outside** the walked tree (`apps/backend/app/**/*.py`) so they cannot poison other tests or fail other AST gates. The walker test explicitly opens them by path. `grep -rn email_ast_violations apps/backend/app/` returns nothing (verified during Task 2).

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Frozenset content | `python -c "from app.core.audit import LOCKED_EMAIL_TEMPLATES; assert len(LOCKED_EMAIL_TEMPLATES) == 15"` | OK 15 templates |
| New tests | `uv run pytest tests/unit/test_locked_email_templates_ast.py -x -q` | 3 passed |
| Full unit suite | `uv run pytest tests/unit/ -x -q` | 584 passed |
| Ruff | `uv run ruff check app/core/audit.py tests/unit/test_locked_email_templates_ast.py tests/unit/fixtures/email_ast_violations/` | All checks passed! |
| Mypy strict | `uv run mypy --strict tests/unit/test_locked_email_templates_ast.py` | Success: no issues found |

## Tasks + Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Declare LOCKED_EMAIL_TEMPLATES frozenset | `16212f9` | `apps/backend/app/core/audit.py` |
| 2 | Synthetic-violation fixtures | `57c3e44` | `tests/unit/fixtures/email_ast_violations/{__init__,bogus_template_id,raw_subject_string}.py` |
| 3 | AST walker test (TDD GREEN — fixtures + frozenset already landed) | `f3efb3f` | `tests/unit/test_locked_email_templates_ast.py` |

## Deviations from Plan

None — plan executed exactly as written. The frozenset content (15 identifiers), file placement (between `LOCKED_AUDIT_EVENTS` and `emit()`), fixture filenames, and test names all match the plan verbatim.

## TDD Gate Compliance

Task 3 is marked `tdd="true"`. The canonical RED → GREEN split was collapsed into a single commit because:

1. **RED-state pre-conditions were already satisfied by Tasks 1 + 2.** Without the frozenset (Task 1, commit `16212f9`) and the fixtures (Task 2, commit `57c3e44`), the walker test could not even import or address its fixture targets — RED would have failed for the wrong reasons (`ImportError` / `FileNotFoundError`, not "walker fails to detect violation").
2. **The walker logic IS the implementation.** Unlike a feature plan where the test asserts behavior of a separately-implemented function, here the walker logic lives inside the test file itself. There is no separate production module to make green.
3. **Verification covers both directions of the gate.** `test_bogus_template_id_is_rejected` and `test_non_literal_template_id_is_rejected` confirm the walker actively detects synthetic violations (not silently passing); `test_real_callsites_pass` confirms it does not over-report on the (currently empty) prod surface.

Per the project's TDD-gate guidance, a `## TDD Gate Compliance` note here documents the rationale so a future audit can see the deliberate collapse rather than mistaking it for a skipped RED.

## Known Stubs

None. The frozenset is the locked source of truth; the walker is fully functional and asserts both directions of the contract.

## Threat Flags

None. The plan's `<threat_model>` (T-41-03-01/02/03 — tampering, repudiation, info-disclosure) is fully mitigated by the literal-only walker + 15-identifier frozenset. No new security-relevant surface introduced beyond what the plan anticipated.

## Self-Check: PASSED

- `apps/backend/app/core/audit.py` — FOUND (modified)
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — FOUND
- `apps/backend/tests/unit/fixtures/email_ast_violations/__init__.py` — FOUND
- `apps/backend/tests/unit/fixtures/email_ast_violations/bogus_template_id.py` — FOUND
- `apps/backend/tests/unit/fixtures/email_ast_violations/raw_subject_string.py` — FOUND
- Commit `16212f9` — FOUND in git log
- Commit `57c3e44` — FOUND in git log
- Commit `f3efb3f` — FOUND in git log
