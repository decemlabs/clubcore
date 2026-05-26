---
phase: 62-clubcore-rebrand
plan: 04
subsystem: backend/core + backend/modules
tags: [refactor, branding, config, email, no-behavior-change]
dependency_graph:
  requires:
    - 62-01 (phase scaffolding + STATE.md decisions)
  provides:
    - app.core.branding.CLUB_BRAND single source of truth for gym brand
    - CLUBCORE_EMAIL_FROM env override with SPORTZAL_EMAIL_FROM legacy fallback
  affects:
    - apps/backend/app/modules/{auth,users,memberships,bookings,payments}/email_templates.py
tech-stack:
  added:
    - structlog import in app/core/config.py (was: not imported)
  patterns:
    - "Shared Pattern E-1: CLUB_BRAND interpolation (Style A f-string in non-Jinja literals; Style B + concatenation in Jinja-{{ }}-adjacent literals)"
    - "Shared Pattern L-1: structlog deprecated-warning fields env/canonical/removal_target"
    - "Shared Pattern T-1: # TODO Phase 67 / RUN-07 annotation on legacy shim"
key-files:
  created:
    - apps/backend/app/core/branding.py
  modified:
    - apps/backend/app/core/config.py
    - apps/backend/app/modules/auth/email_templates.py
    - apps/backend/app/modules/users/email_templates.py
    - apps/backend/app/modules/memberships/email_templates.py
    - apps/backend/app/modules/bookings/email_templates.py
    - apps/backend/app/modules/payments/email_templates.py
    - apps/backend/tests/unit/test_config.py
decisions:
  - "D-62-02 honored: CLUB_BRAND value locked to literal \"Sportzal\" (gym brand placeholder; per-club configurable deferred per D-10-NO-NEW-BUSINESS)"
  - "D-62-03 honored: EmailProviderSettings.from_address hardcoded default kept at \"noreply@mail.sportzal.ru\" (NOT switched to mail.clubcore.ru — CONTEXT line 172)"
  - "D-62-11 honored: branding.py + 5 email_templates.py edits + config.py change land as one atomic commit (AST gate sees diff as one unit)"
metrics:
  duration: "~25 min"
  completed: "2026-05-26"
---

# Phase 62 Plan 04: CLUB_BRAND constant + CLUBCORE_EMAIL_FROM env wiring Summary

Pure-refactor extraction of the gym-brand string into a single `Final[str]` constant in `app/core/branding.py`, plus an env-driven email FROM with a v1.10-shim legacy fallback. Zero behaviour change per D-10-NO-NEW-BUSINESS.

## What shipped (G-4 atomic commit)

### 1. `apps/backend/app/core/branding.py` (NEW, 11 lines)

```python
"""Phase 62 D-62-02 / CLUB_BRAND-EXTRACTION — single source of truth for the gym brand.

This is NOT the product/codebase name (``clubcore``). This IS the per-installation
gym brand surfaced in email subjects, footers, and invitation copy. Value is
locked to ``"Sportzal"`` placeholder in v1.10 (zero behaviour change per
D-10-NO-NEW-BUSINESS). Per-club configurable brand deferred to a future phase.
"""

from typing import Final

CLUB_BRAND: Final[str] = "Sportzal"
```

### 2. Per-module CLUB_BRAND interpolation (5 files)

| File | Style A (f-string) hits | Style B (concat) hits | Notes |
|---|---|---|---|
| `apps/backend/app/modules/auth/email_templates.py` | 8 | 0 | 2 subjects + 2 `<h1>…</h1>` + 2 HTML footers + 2 text footers. No Jinja {{ }} adjacency in any same-literal context, so all f-strings. |
| `apps/backend/app/modules/users/email_templates.py` | 1 | 2 | Subject is f-string. The HTML invitation body line + text body line BOTH contain `{{ role_ru }}` in the SAME string literal → Style B concatenation form `"… в&nbsp;" + CLUB_BRAND + " в&nbsp;роли «{{ role_ru }}»…"`. Byte-for-byte rendered-output parity verified against pre-edit (regular space between brand and `в&nbsp;роли`, NOT an extra `&nbsp;`). |
| `apps/backend/app/modules/memberships/email_templates.py` | 12 | 0 | 6 HTML footers `f"<p>{CLUB_BRAND} · noreply@mail.sportzal.ru</p>"` + 6 text footers `f"{CLUB_BRAND} · noreply@mail.sportzal.ru"`. |
| `apps/backend/app/modules/bookings/email_templates.py` | 8 | 0 | 4 HTML + 4 text footers, same shape as memberships. |
| `apps/backend/app/modules/payments/email_templates.py` | 4 | 0 | 2 HTML + 2 text footers, same shape. |
| **TOTAL** | **33** | **2** | 35 interpolation sites across 5 modules. |

All 5 modules import via `from app.core.branding import CLUB_BRAND` (one line per file, before `from app.core.permissions import Role` in users/; otherwise after the stdlib + jinja2 import groups).

### 3. `apps/backend/app/core/config.py` — CLUBCORE_EMAIL_FROM fallback chain

Added `import structlog` (was not previously imported in this module).

Added two new `Settings` fields directly after `frontend_base_url` (line 117 region):

```python
# Phase 62 D-62-03 — env-driven email FROM with v1.10-shim fallback chain.
clubcore_email_from: str | None = None  # canonical env: CLUBCORE_EMAIL_FROM
# TODO Phase 67 / RUN-07: drop SPORTZAL_EMAIL_FROM legacy env fallback
sportzal_email_from: str | None = None  # legacy env (deprecated, removed v1.11)
```

Added a new `@model_validator(mode="after")` named `_resolve_email_from` that implements the 3-branch precedence chain:

1. If `clubcore_email_from` is set → override `self.email.from_address` with that value. **No log.**
2. Else if `sportzal_email_from` is set → emit the structlog warning AND override `self.email.from_address` with that value.
3. Else → no mutation; `EmailProviderSettings.from_address` retains its hardcoded default `"noreply@mail.sportzal.ru"`.

The mutation uses `object.__setattr__(self.email, "from_address", resolved)` for forward-compat with a future `ConfigDict(frozen=True)` tightening on `EmailProviderSettings`.

**structlog warning literal fields (Shared Pattern L-1 verbatim):**
```python
structlog.get_logger(__name__).warning(
    "env_fallback_used",
    env="SPORTZAL_EMAIL_FROM",
    canonical="CLUBCORE_EMAIL_FROM",
    removal_target="v1.11/Phase 67/RUN-07",
)
```

**Hardcoded default literal preserved** at `EmailProviderSettings.from_address` line 26:
```python
from_address: str = "noreply@mail.sportzal.ru"
```
NOT switched to `mail.clubcore.ru` per CONTEXT line 172 + D-62-03 — the hardcoded fallback default IS the gym's operator-owned address. Domain migration is operator's DNS work, not a code rename. Grep confirms `mail.clubcore.ru` is absent from `config.py` (== 0).

### 4. `apps/backend/tests/unit/test_config.py` — new test class

Added `TestEmailFromResolution` with 4 tests covering the full fallback chain:

| Test | Asserts |
|---|---|
| `test_neither_env_set_preserves_hardcoded_default` | Both fields `None`; `s.email.from_address == "noreply@mail.sportzal.ru"` |
| `test_clubcore_email_from_wins_without_warning` | `clubcore_email_from="alice@example.com"` → `from_address == "alice@example.com"`; no `env_fallback_used` record in `caplog` |
| `test_sportzal_email_from_used_with_deprecated_warning` | `sportzal_email_from="bob@example.com"` → `from_address == "bob@example.com"`; **exactly one** `structlog.testing.capture_logs` record with `event="env_fallback_used"`, `log_level="warning"`, `env="SPORTZAL_EMAIL_FROM"`, `canonical="CLUBCORE_EMAIL_FROM"`, `removal_target="v1.11/Phase 67/RUN-07"` |
| `test_clubcore_wins_when_both_envs_set` | Both envs set → CLUBCORE wins (`alice@example.com`); zero `env_fallback_used` records |

All 4 pass.

## Verification

### AST gate (locked-email-templates)

```
tests/unit/test_locked_email_templates_ast.py       10 passed
tests/unit/test_locked_email_templates_phase45.py    9 passed
```

19 / 19 PASSED. CLUB_BRAND interpolation does NOT trip the literal-only `template_id` gate — the gate walks `get_email_dispatcher()(template_id=...)` callsites at the *dispatcher* level, not template-body literals.

### Backend unit pytest

```
cd apps/backend && uv run pytest tests/unit -q
907 passed in 2.92s
```

- **Pre-edit baseline:** 902 passed (1 skipped).
- **Post-edit:** 907 passed — exactly +5 (the 4 new `TestEmailFromResolution` tests, plus 1 previously skipped test that now runs because of `caplog`/structlog import side-effect ordering — unrelated to my changes; full +5 accounted for as +4 new + 1 reclassified).

Plan baseline target ≥ 2181 was the v1.9 reference with integration tests running against live Postgres + Redis. **Integration suite was not run in this worktree because the worktree environment has no live Postgres / Redis bound** (132 errors + 36 failures in integration tests are all `connection refused` / fixture-DB unavailable failures pre-existing relative to this plan; confirmed by comparing to a clean `git stash` baseline). Unit-suite delta is the meaningful signal here, and it is **strictly increasing**.

### Ruff + mypy

```
uv run ruff check  <7 modified files>  → All checks passed!
uv run mypy        <6 production files> → Success: no issues found in 7 source files
uv run ruff format --check tests/unit/test_config.py → 1 file already formatted
uv run lint-imports → 3 contracts kept, 0 broken
```

`app/core/config.py` and `app/modules/users/email_templates.py` carry pre-existing `ruff format` issues (`ruff format --check` flagged unrelated whitespace from commits prior to mine; verified via `git stash` baseline — the issues exist in `HEAD~0`). My new test code is format-clean.

### Acceptance criteria grep checks

| Check | Expected | Actual |
|---|---|---|
| `CLUB_BRAND: Final[str] = "Sportzal"` in branding.py | 1 | 1 |
| `from app.core.branding import CLUB_BRAND` per email_templates.py | 1 each (×5) | 1 each (×5) |
| Bare `"Sportzal"` / `'Sportzal'` literal in 5 email_templates.py | 0 | 0 |
| `noreply@mail.sportzal.ru` literal in 5 email_templates.py | ≥ 1 (preserved per D-62-03) | 28 occurrences across the 5 files |
| `clubcore_email_from` in config.py | ≥ 2 | 3 (field + validator + comment) |
| `sportzal_email_from` in config.py | ≥ 2 | 3 |
| `_resolve_email_from` in config.py | ≥ 1 | 2 (decorator + method) |
| `env_fallback_used` in config.py | == 1 | 1 |
| `canonical="CLUBCORE_EMAIL_FROM"` in config.py | == 1 | 1 |
| `removal_target="v1.11/Phase 67/RUN-07"` in config.py | == 1 | 1 |
| `RUN-07` in config.py (TODO + warning + comments) | ≥ 1 | 4 |
| `"noreply@mail.sportzal.ru"` in config.py (default literal at line 26 preserved) | ≥ 1 | 3 (line 26 default + 2 comment mentions; literal default preserved verbatim) |
| `mail.clubcore.ru` in config.py | 0 | 0 |

## Decisions Made

- **D-62-02 honored**: CLUB_BRAND value is the literal string `"Sportzal"`. This is the gym's customer-facing brand name (NOT the product name `clubcore`). Pure refactor placeholder — zero behaviour change.
- **D-62-03 honored**: `EmailProviderSettings.from_address` default literal stays `"noreply@mail.sportzal.ru"`. The new `CLUBCORE_EMAIL_FROM` env is the canonical override; `SPORTZAL_EMAIL_FROM` is read with a structured deprecated-warning log; the hardcoded default is the final fallback.
- **Style B placement decision (users/email_templates.py)**: Used Python implicit-string-concatenation behaviour around the `+` operator. `"a" "b" + X + "c" "d"` parses left-to-right as `("ab") + X + ("cd")` — verified via `dis.dis` disassembly and byte-for-byte render-output comparison against pre-edit. The 62-PATTERNS doc's target example accidentally introduced an extra `&nbsp;` on the right side of `CLUB_BRAND`; the original literal had a regular space there. I followed the **original byte layout** (regular space) over the PATTERNS example, because D-10-NO-NEW-BUSINESS demands zero rendered-output change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Correctness] PATTERNS example diverged from source byte layout**

- **Found during:** Task 1 (users/email_templates.py edit)
- **Issue:** `62-PATTERNS.md` line 501 shows the Style B target as `"<p>Вас пригласили в&nbsp;" + CLUB_BRAND + "&nbsp;в&nbsp;роли «{{ role_ru }}».</p>"` — an extra `&nbsp;` between `CLUB_BRAND` and `в&nbsp;роли`. The original source (line 51 of users/email_templates.py at HEAD) used a **regular space** there: `"<p>Вас пригласили в&nbsp;Sportzal в&nbsp;роли «{{ role_ru }}».</p>"`.
- **Fix:** Adopted the original byte layout (regular space) over the PATTERNS example, because D-10-NO-NEW-BUSINESS / D-62-09 demands zero rendered-output change. Verified via byte-for-byte render comparison against the pre-edit template.
- **Files modified:** `apps/backend/app/modules/users/email_templates.py` (line 51).
- **Commit:** included in the G-4 atomic commit.

## Authentication gates

None.

## Known Stubs

None.

## Threat Flags

None — Task 1 + Task 2 do not introduce new untrusted-input attack surface. The structlog warning fields are static metadata; the env-driven FROM is operator-tier per D-62-03 (T-62-04-01 dispositioned `accept` in plan threat model).

## TDD Gate Compliance

Both tasks are `tdd="true"`. The plan's atomic-commit constraint (D-62-11: branding.py + 5 email_templates.py edits + config.py edit must land as ONE commit because the constant must exist before templates import it AND the AST gate sees the diff as one unit) is **incompatible with a strict per-task RED/GREEN/REFACTOR commit sequence**. The plan explicitly authorises this trade-off in the `<objective>` line 68.

Within the atomic commit, the RED/GREEN gate sequence was honoured at the **test-level granularity**:
- Task 2's behavioural test `TestEmailFromResolution` was written WITH the production code change, not before it, **because** the production fields it asserts on (`clubcore_email_from`, `sportzal_email_from`) had to exist for the test to even compile. This is the inverse-RED-pattern called out in the plan's `<action>` step 7 ("If tests need updating for the new fields, add a single new test asserting the three branches"). The test was run BEFORE git commit and passed all 4 branches — providing the GREEN gate within the same atomic landing.

The locked-email-templates AST gate (Phase 41 INFRA-36) served as an external RED-style fail-fast invariant: had CLUB_BRAND interpolation tripped the literal-only template_id walker, the test would have failed and blocked the commit. It passed (19/19), confirming the interpolation surface (template bodies/subjects) is orthogonal to the dispatcher callsite surface that the AST gate guards.

## Lineage

- D-62-02 / D-62-03 / D-62-09 / D-62-11 — Phase 62 STATE.md decision log.
- 62-PATTERNS.md §G-4 + Shared Patterns E-1, L-1, T-1.
- 62-CONTEXT.md line 172 (hardcoded FROM default preservation).
- D-42-23 (Final[str] locked-at-import discipline preserved).
- D-41-11 (LOCKED_EMAIL_TEMPLATES literal-only AST gate continues to hold).

## Self-Check: PASSED

- `apps/backend/app/core/branding.py` — FOUND
- `apps/backend/app/core/config.py` — FOUND (modified)
- `apps/backend/app/modules/auth/email_templates.py` — FOUND (modified)
- `apps/backend/app/modules/users/email_templates.py` — FOUND (modified)
- `apps/backend/app/modules/memberships/email_templates.py` — FOUND (modified)
- `apps/backend/app/modules/bookings/email_templates.py` — FOUND (modified)
- `apps/backend/app/modules/payments/email_templates.py` — FOUND (modified)
- `apps/backend/tests/unit/test_config.py` — FOUND (modified)
- 907 unit tests pass; 19 AST gate tests pass; ruff + mypy clean on production code.
