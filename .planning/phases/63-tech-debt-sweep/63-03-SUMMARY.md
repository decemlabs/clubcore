---
phase: 63-tech-debt-sweep
plan: 03
subsystem: tooling
tags: [tech-debt, mypy, strict, python, types]

# Dependency graph
requires:
  - phase: 63-02
    provides: "ruff-clean apps/backend tree (0 ruff check errors, format --check exit 0); mypy --strict app baseline = 11 errors"
provides:
  - "mypy --strict app exits 0 across apps/backend/app/ (11 errors -> 0)"
  - "Explicit __all__ on apps/backend/app/modules/auth/models.py covering User + module-local symbols (PITFALLS Pitfall #6)"
  - "[[tool.mypy.overrides]] module = \"tests.*\" block in apps/backend/pyproject.toml (D-63-03 — CI gate stays `uv run mypy --strict app`)"
  - "Literal-typed CONFIRMATION_TYPE_* and SUBJECT_KIND_* constants (Final[Literal[...]]) so router/service callsites flow Literal narrowing cleanly"
affects:
  - 63-04 (DEBT-04 v1.5 runbook hardening — no overlap; orthogonal scope)
  - 63-05 (DEBT-05 CI gate verification — mypy gate now satisfies its CI requirement)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Final[Literal[...]] typed enum constants — module-level constants whose values must flow into Literal-typed parameter slots are typed as `Final[Literal[<value>]]` rather than bare `str`. Eliminates an entire class of `[arg-type]` mypy errors at the callsite without `# type: ignore`."
    - "Explicit union annotation for branch-narrowed Literal assignments — when a variable is assigned different Literal values across `if/elif` branches, declare the union upfront (`subject_kind: Literal[\"a\", \"b\"]`) before the branching block; otherwise the first branch narrows to a single Literal and subsequent branches fail [assignment]."
    - "__all__ as the canonical fix for mypy strict implicit-reexport rejection of legacy re-export shims (PITFALLS Pitfall #6)."

key-files:
  created:
    - .planning/phases/63-tech-debt-sweep/63-03-SUMMARY.md
  modified:
    - "apps/backend/app/api/v1/_internal/yookassa/handlers.py (subject_kind Literal union annotation; removed obsolete # type: ignore[assignment])"
    - "apps/backend/app/modules/auth/models.py (__all__ added per PITFALLS Pitfall #6; obsolete # noqa: F401 on User re-export removed since __all__ satisfies pyflakes)"
    - "apps/backend/app/modules/fiscal_receipts/tasks.py (typed session: Any -> session: AsyncSession on 3 private helpers; added AsyncSession import)"
    - "apps/backend/app/modules/online_payments/constants.py (CONFIRMATION_TYPE_REDIRECT/QR and SUBJECT_KIND_* typed Final[Literal[...]]; added Final, Literal imports)"
    - "apps/backend/app/modules/online_refunds/settle.py (subject_kind Literal union annotation; removed obsolete # type: ignore[arg-type] on audit_actor=None)"
    - "apps/backend/app/modules/payments/constants.py (SUBJECT_KIND_MEMBERSHIP/PT_PACKAGE/REFUND typed Final[Literal[...]]; added Final, Literal imports)"
    - "apps/backend/pyproject.toml (added 4th [[tool.mypy.overrides]] block for module = \"tests.*\" per D-63-03)"

key-decisions:
  - "Retyped `SUBJECT_KIND_*` (in app/modules/payments/constants.py AND app/modules/online_payments/constants.py) and `CONFIRMATION_TYPE_*` (in app/modules/online_payments/constants.py) as `Final[Literal[<value>]]` instead of patching each individual callsite. Rationale: single-source-of-truth fix — 5 of the 11 mypy errors (the 4 `confirmation_type` arg-type errors + the `subject_kind` arg-type error) all cascade-resolved from typing the constants once. No `# type: ignore` needed at any callsite."
  - "Added explicit `subject_kind: Literal[\"membership\", \"pt_package\"]` annotation above branch-narrowed assignments in 2 places (settle.py:145 and handlers.py:417). This is necessary because once `SUBJECT_KIND_MEMBERSHIP` carries `Literal[\"membership\"]`, the first branch's assignment narrows the variable to that single Literal, and the elif branch's `SUBJECT_KIND_PT_PACKAGE` (Literal[\"pt_package\"]) is then rejected as `[assignment]`. Declaring the union upfront tells mypy to keep the type wide for both arms."
  - "Removed the pre-existing `# noqa: F401 — public re-export` on `auth/models.py:30` (the `from app.core.models import User` shim). PITFALLS Pitfall #6 predicted the noqa would become removable once __all__ declared User as public surface, and that proved correct — ruff now accepts the import via __all__. Counted as a `noqa removed`, not a `noqa preserved`."
  - "Removed the pre-existing `# type: ignore[arg-type]` on `settle.py:174` (`audit_actor=None`) — mypy now reports it as `[unused-ignore]`. The Protocol signature was widened upstream so the ignore was already dead code."
  - "Removed the pre-existing `# type: ignore[assignment]` on `handlers.py:506` (`subject_kind_local: Literal[...] = subject_kind`) — once the explicit union annotation was added at the branching site, the local pin no longer triggers an [assignment] error."
  - "Retyped `session: Any` -> `session: AsyncSession` on three private helpers in `app/modules/fiscal_receipts/tasks.py` (_resolve_yookassa_object_id, _resolve_refund_id_via_db_join, _resolve_amount_kopecks). Real callers feed `session_factory()` AsyncSession instances; the `Any` annotation was lazy and caused `online_refund.yookassa_refund_id` to propagate as `Any` -> `no-any-return` on line 180. The `Any` from `typing` is still imported and used by other helpers in the same file (`session_factory: Any`, `arq_pool: Any | None`, `ctx: dict[str, Any]`), so the import was not removed."

patterns-established:
  - "Module-level constant retyping pattern: when a `str = \"value\"` constant flows into a Literal-typed slot, prefer `Final[Literal[\"value\"]]` over patching each callsite with `cast(...)` or `# type: ignore`. Cascade-resolves multiple errors at once and survives future callsite additions for free."
  - "Branch-narrowed Literal assignment pattern: declare `var: Literal[\"a\", \"b\"]` BEFORE the `if/elif` branches when each branch assigns a different Literal value. Otherwise mypy narrows the type to the first branch's Literal and rejects subsequent branches."
  - "When ruff/mypy enforce parallel-but-distinct rules on the same re-export shim, explicit __all__ closes BOTH concerns (mypy attr-defined + ruff F401) and obsoletes the noqa."

requirements-completed: [DEBT-03]

# Metrics
duration: ~30min (single executor; analysis + 7-file diff + iterative mypy-rerun loop)
completed: 2026-05-26
---

# Phase 63 Plan 03: mypy --strict Cleanup + __all__ Fix + tests.* Override Summary

**11 mypy `--strict` errors -> 0 in `apps/backend/app/`; auth/models.py `__all__` added per PITFALLS Pitfall #6; new `[[tool.mypy.overrides]]` block scopes test-suite leniency without weakening the `app/` strict gate. Single atomic commit (`c7bc5adc`) per D-63-01; zero new `# type: ignore` / `# noqa` / `ignore_imports`; 907 unit tests pass; ruff format --check + ruff check baselines from Plans 1+2 preserved.**

## Performance

- **Duration:** ~30 min (single executor on main working tree, sequential)
- **Started:** 2026-05-26 (after Plan 2 commit `495a0ec7` landed)
- **Completed:** 2026-05-26
- **Tasks:** 3 of 3 (all auto-mode, fused into ONE atomic commit per D-63-01)
- **Files modified:** 7 (apps/backend/{app/api,app/modules,pyproject.toml})

## Accomplishments

- `cd apps/backend && uv run mypy --strict app` exits 0 (was 11 errors -> 0)
- `cd apps/backend && uv run ruff check app tests` exits 0 (Plan 2 baseline preserved)
- `cd apps/backend && uv run ruff format --check .` exits 0 (Plan 1 baseline preserved)
- `cd apps/backend && uv run lint-imports` — `Contracts: 3 kept, 0 broken` (pre-existing warnings unchanged)
- `cd apps/backend && uv run python -m scripts.export_openapi` runs clean; `git diff --exit-code apps/backend/openapi.json` exits 0 (no schema drift)
- `cd apps/backend && uv run pytest tests/unit -x -q` — 907 passed in 3.26s
- Atomic commit `c7bc5adc` per D-63-01 — covers all three Plan-3 sub-tasks (3a mypy fixes, 3b __all__, 3c pyproject override)
- DEBT-03 success criterion (per `.planning/REQUIREMENTS.md` / `.planning/ROADMAP.md`) satisfied

## Task Commits

1. **Tasks 1+2+3 (fused atomic commit per D-63-01):** `c7bc5adc` — `chore(backend): mypy strict cleanup + __all__ fix + tests.* override (DEBT-03)`
   - Task 1 (Plan internal): `[[tool.mypy.overrides]] module = "tests.*"` added to `apps/backend/pyproject.toml`
   - Task 2 (Plan internal): `__all__ = ["OtpChannel", "OtpCode", "RefreshToken", "User"]` added to `apps/backend/app/modules/auth/models.py`; obsolete `# noqa: F401` removed
   - Task 3 (Plan internal): the 11 mypy strict errors fixed across `auth/models.py` (4 attr-defined), `online_refunds/settle.py` (1 arg-type + 1 unused-ignore), `online_payments/router.py` (4 arg-type — fixed via constants retyping), `fiscal_receipts/tasks.py` (1 no-any-return); plus 1 cascading [assignment] fix in `handlers.py` and 1 cascading [unused-ignore] in `handlers.py`

**Plan metadata commits** (follow this SUMMARY, separate per atomic-commit discipline): SUMMARY.md commit + STATE/ROADMAP/REQUIREMENTS tracking commit.

## Pre-Fix mypy Error Breakdown (11 errors)

| # | File:Line | Rule | Description | Fix |
|---|-----------|------|-------------|-----|
| 1 | `app/modules/auth/service.py:45` | `[attr-defined]` | Module `app.modules.auth.models` does not explicitly export attribute `User` | Closed by Task 2 `__all__` |
| 2 | `app/modules/auth/telegram_service.py:45` | `[attr-defined]` | Same as #1 | Closed by Task 2 `__all__` |
| 3 | `app/modules/auth/router.py:45` | `[attr-defined]` | Same as #1 | Closed by Task 2 `__all__` |
| 4 | `app/modules/users/router.py:61` | `[attr-defined]` | Same as #1 | Closed by Task 2 `__all__` |
| 5 | `app/modules/online_refunds/settle.py:174` | `[unused-ignore]` | Unused `# type: ignore` on `audit_actor=None` | Removed the now-dead `# type: ignore[arg-type]` |
| 6 | `app/modules/online_refunds/settle.py:350` | `[arg-type]` | `subject_kind` had incompatible type `str`; expected `Literal["membership", "pt_package"]` | Typed `SUBJECT_KIND_*` constants in `payments/constants.py` as `Final[Literal[...]]`; added explicit union annotation above the branching assignment at line 145 |
| 7 | `app/modules/online_payments/router.py:218` | `[arg-type]` | `confirmation_type` had incompatible type `str`; expected `Literal["redirect", "qr"]` (sell_membership redirect site) | Typed `CONFIRMATION_TYPE_*` in `online_payments/constants.py` as `Final[Literal[...]]` |
| 8 | `app/modules/online_payments/router.py:266` | `[arg-type]` | Same as #7, sell_membership QR site | Same fix as #7 (cascade) |
| 9 | `app/modules/online_payments/router.py:311` | `[arg-type]` | Same as #7, sell_pt_package redirect site | Same fix as #7 (cascade) |
| 10 | `app/modules/online_payments/router.py:353` | `[arg-type]` | Same as #7, sell_pt_package QR site | Same fix as #7 (cascade) |
| 11 | `app/modules/fiscal_receipts/tasks.py:180` | `[no-any-return]` | Returning `Any` from function declared to return `str \| None` | Retyped `session: Any` -> `session: AsyncSession` on 3 private helpers; added `AsyncSession` import |

**Sub-tasks cascading from the Literal retyping** (surfaced after the constants fix, fixed in the same commit):

| File:Line | Rule | Description | Fix |
|-----------|------|-------------|-----|
| `app/modules/online_refunds/settle.py:148` | `[assignment]` | After SUBJECT_KIND_* became Literal, first arm narrowed `subject_kind` to `Literal["membership"]` and elif arm's `Literal["pt_package"]` was rejected | Added explicit `subject_kind: Literal["membership", "pt_package"]` annotation at line 145 |
| `app/api/v1/_internal/yookassa/handlers.py:421` | `[assignment]` | Same narrowing pattern as settle.py:148 | Added explicit `subject_kind: Literal["membership", "pt_package"]` annotation at line 417 |
| `app/api/v1/_internal/yookassa/handlers.py:506` | `[unused-ignore]` | Once handlers.py:417 was properly annotated, the pin `subject_kind_local: Literal[...] = subject_kind  # type: ignore[assignment]` no longer needed the ignore | Removed the `# type: ignore[assignment]` |

**Tally:**
- 4 of 11 closed by __all__ (the `[attr-defined]` quartet for `User`)
- 5 of 11 closed by Literal-retyping the constants (settle.py:350 + 4x router.py confirmation_type)
- 1 of 11 closed by removing a dead `# type: ignore` (settle.py:174)
- 1 of 11 closed by typing `session: Any` -> `AsyncSession` (fiscal_receipts/tasks.py:180)
- 2 cascading [assignment] errors surfaced + fixed via explicit union annotations
- 1 cascading [unused-ignore] surfaced + fixed by removing the now-dead ignore

**No mypy errors required `# type: ignore` to silence.** Two were actually fixed *by removing existing # type: ignore* directives.

## Final `__all__` in `apps/backend/app/modules/auth/models.py`

```python
__all__ = [
    "OtpChannel",  # Phase 42 AUTH-EM-01 / D-42-20 (line 35 above)
    "OtpCode",  # this module
    "RefreshToken",  # this module
    "User",  # Phase 41 INFRA-40 / D-41-01 re-export shim (line 30 above)
]
```

Sorted alphabetically (RUF022 compliance). Covers:
- `User` — the Phase 41 INFRA-40 re-export shim (target of PITFALLS Pitfall #6)
- `OtpChannel` — Phase 42 AUTH-EM-01 type alias
- `RefreshToken` — module-defined ORM class
- `OtpCode` — module-defined ORM class

## Final `pyproject.toml` Override Block (Task 3c / D-63-03)

```toml
# Phase 63 DEBT-03 / D-63-03: scope `mypy --strict` to app/ only. Test suite
# carries pre-existing untyped fixtures + dynamic helpers that would require
# a separate cleanup pass; CI gate stays exactly `uv run mypy --strict app`,
# so this override prevents an out-of-band `mypy app tests` ad-hoc run from
# crashing while keeping app/ strict-clean (zero deferral tracker file needed).
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_decorators = false
disallow_untyped_calls = false
```

Inserted at the end of the existing override sequence (after the `aioboto3.*`/`botocore.*` block) and immediately before `[tool.ruff.lint.per-file-ignores]`. Total `[[tool.mypy.overrides]]` blocks now = 4 (was 3). The block does NOT contain `ignore_errors = true` — it narrows specific flags only, preserving error reporting on test files for any cleanup phase that wants to opt into stricter test typing later.

## Compliance Checks (Constraint Verification)

| Check | Command | Result |
|-------|---------|--------|
| D-63-06 — zero new `# type: ignore` directives | `git diff HEAD~1 HEAD -- apps/backend \| grep '^+' \| grep -v '^+++' \| grep -E '# type: ignore'` | Two `+` matches, both INSIDE explanatory comment text (`without # type: ignore (D-63-06)`), NOT real suppression directives. Net real directives: **-2 / +0** |
| D-63-06 — zero new `# noqa` directives | `git diff HEAD~1 HEAD -- apps/backend \| grep '^+' \| grep -v '^+++' \| grep -E '# noqa'` | Zero `+` matches. Net: **-1 / +0** (the F401 noqa on the User re-export was removed) |
| D-63-06 — zero new `[per-file-ignores]` entries | `git diff HEAD~1 HEAD -- apps/backend/pyproject.toml apps/backend/ruff.toml \| grep '^+' \| grep 'per-file-ignores\|ignore_imports'` | Zero matches |
| D-63-06 — zero new `ignore_errors = true` for `app.*` | `git diff HEAD~1 HEAD -- apps/backend/pyproject.toml \| grep '^+' \| grep -E 'ignore_errors\|module = "app'` | Zero matches |
| D-63-05 — no `--unsafe-fixes` invoked | (this plan ran no `ruff check --fix` at all) | OK |
| D-63-03 — CI gate stays `uv run mypy --strict app` | `grep -A 1 '^\[tool.mypy\]$' apps/backend/pyproject.toml` | `python_version = "3.12"` immediately follows; `strict = true` at original line position; gate untouched |
| D-63-03 — `tests.*` override scoped to tests only | `grep -B 1 -A 5 'module = "tests\.\*"' apps/backend/pyproject.toml` | Block matches scope `tests.*` only; does NOT contain `app.*` or `app.tests.*` |
| D-63-01 — single atomic commit | `git log --oneline -1` | `c7bc5adc chore(backend): mypy strict cleanup + __all__ fix + tests.* override (DEBT-03)` |
| Plan 1 baseline preserved | `cd apps/backend && uv run ruff format --check .` | exit 0 (`635 files already formatted`) |
| Plan 2 baseline preserved | `cd apps/backend && uv run ruff check app tests` | `All checks passed!`, exit 0 |
| DEBT-03 success criterion | `cd apps/backend && uv run mypy --strict app` | `Success: no issues found in 209 source files` |
| Scope discipline | `git diff HEAD~1 HEAD --name-only \| grep -v '^apps/backend/' \| wc -l` | `0` (commit touches only backend files) |
| __all__ runtime import works | `cd apps/backend && uv run python -c "import app.modules.auth.models as m; print(m.__all__); print(m.User)"` | `['OtpChannel', 'OtpCode', 'RefreshToken', 'User']` + `<class 'app.core.models.User'>` |
| Unit test smoke (regression check) | `cd apps/backend && uv run pytest tests/unit -x -q` | `907 passed in 3.26s` |
| `[[tool.mypy.overrides]]` count | `grep -c '^\[\[tool.mypy.overrides\]\]' apps/backend/pyproject.toml` | `4` (was 3) |
| `tests.*` override count | `grep -c 'module = "tests\.\*"' apps/backend/pyproject.toml` | `1` |
| `__all__` in auth/models.py | `grep -c '^__all__ = \[' apps/backend/app/modules/auth/models.py` | `1` |
| OpenAPI drift gate | `cd apps/backend && uv run python -m scripts.export_openapi && cd ../.. && git diff --exit-code apps/backend/openapi.json` | exit 0 (no schema drift introduced) |

## Decisions Made

- **Constant-retyping over callsite patching:** Five of the 11 errors (4 confirmation_type + 1 subject_kind arg-type errors) were callsite-level `[arg-type]` failures whose root cause was that the constants `CONFIRMATION_TYPE_REDIRECT`, `CONFIRMATION_TYPE_QR`, `SUBJECT_KIND_MEMBERSHIP`, `SUBJECT_KIND_PT_PACKAGE` were typed as bare `str` instead of `Literal[<value>]`. Retyping each constant once (with `Final[Literal[<value>]]`) eliminated all five errors atomically and future-proofed future callsites against the same regression class. Patching each callsite individually with `cast(...)` would have been brittle and verbose.
- **Explicit union annotation for branch-narrowed Literals:** Once the constants became Literal-typed, two pre-existing `if/elif` blocks (`settle.py:145-153` and `handlers.py:417-427`) that assign different Literal values per branch needed an explicit `subject_kind: Literal["membership", "pt_package"]` annotation upfront to prevent mypy from narrowing the variable to the first branch's single-Literal type. Documented inline with a `Phase 63 DEBT-03` rationale comment.
- **Remove obsolete suppression directives proactively:** Two pre-existing `# type: ignore[...]` directives became dead code once the underlying types were fixed (settle.py:174 `[arg-type]` on `audit_actor=None`, handlers.py:506 `[assignment]` on `subject_kind_local`). mypy reports these as `[unused-ignore]`, so removal is mandatory, not optional. Pre-existing `# noqa: F401` on the `User` re-export also became removable per PITFALLS Pitfall #6's prediction once `__all__` declared `User` as public surface.
- **Comment-text rewriting to avoid ruff parsing the rule code inline:** The first draft of the `__all__` rationale comments contained the literal string `# noqa: F401` inside explanatory prose; ruff parsed it as a real (malformed) noqa directive and emitted a warning. Rewrote the comments to refer to "the pyflakes F401 suppression" without including the literal token sequence. This is a documentation-only fix.
- **session: Any -> AsyncSession on a single file's three private helpers:** Tightly scoped to `fiscal_receipts/tasks.py` because that's where the `no-any-return` error originated. The same file has three other call-sites using `session_factory: Any`, `arq_pool: Any | None`, `ctx: dict[str, Any]` that were left untouched — they're not blocking mypy strict and broadening this plan to retype them all would have violated D-63-01's atomic-commit boundary by inflating the diff beyond DEBT-03's strict scope.

## Deviations from Plan

### Rule 1 — Bug fixes

None.

### Rule 2 — Critical missing functionality

None.

### Rule 3 — Blocking issues

None — every mypy fix was a straightforward type refinement.

### Rule 4 — Architectural / Spec refinements

**1. [Rule 4 — Spec Refinement] Plan instructed to "preserve the # noqa: F401 on the User re-export line"; PITFALLS Pitfall #6's actual prediction was that it would become removable**

- **Found during:** post-`__all__`-insertion `ruff check` run
- **Issue:** The PLAN.md Task 2 instruction said "Do NOT remove the existing `# noqa: F401 — public re-export` comment on line 30 (that one IS still required — it suppresses ruff's pyflakes-style warning; the new __all__ closes mypy's parallel concern)." However, the user's `<key_constraints>` block correctly stated "The `# noqa: F401` may then become removable (verify with ruff after)... if F401 returns, restore the noqa." Post-`__all__` `ruff check` showed `RUF100 [*] Unused `noqa` directive (unused: F401)` — i.e., once `User` was declared in `__all__`, pyflakes no longer flagged the import as unused, so the noqa became dead code.
- **Fix:** Removed the noqa per the user's key_constraints guidance (the cleaner outcome). Replaced with an explanatory comment block above the `from app.core.models import User` line explaining the rationale.
- **Outcome:** Counted as a **noqa REMOVED**, not a `noqa added`. D-63-06 compliance is strengthened, not weakened.
- **Committed in:** `c7bc5adc`

**2. [Rule 4 — Spec Refinement] Plan listed 11 mypy errors; actual fix surfaced 3 cascading errors that needed to be addressed in the same commit**

- **Found during:** post-constant-retyping `mypy --strict app` run
- **Issue:** Typing `SUBJECT_KIND_MEMBERSHIP/PT_PACKAGE` as `Final[Literal[<value>]]` (the cleanest fix for the 5 arg-type errors that flowed from these constants) surfaced 2 new `[assignment]` errors at the `if/elif` branch-narrowing sites (settle.py:148 and handlers.py:421) and 1 new `[unused-ignore]` at handlers.py:506 (the local pin `subject_kind_local: Literal[...] = subject_kind  # type: ignore[assignment]` no longer needed the ignore once the source variable was properly union-typed).
- **Why this is in scope:** All 3 cascading errors live in the same commit-scope (`apps/backend/app/`) and are directly caused by the chosen fix for the 11 plan-listed errors. Per the plan's `<action>` clause: "After all fixes, verify: `cd apps/backend && uv run mypy --strict app` exits 0" — addressing the cascade was mandatory to satisfy the exit-0 contract. The cleanup is documented per CONTEXT.md's Integration Points rule ("mypy edits land in this plan's diff even if they touch files Plans 1+2 reformatted") generalized to "even if they cascade beyond the originally-enumerated 11").
- **Fix:** Added 2 explicit union annotations + removed 1 dead `# type: ignore`. All resolved in the same atomic commit per D-63-01.
- **Committed in:** `c7bc5adc`

**3. [Rule 4 — Documentation refinement] Initial __all__ rationale comments contained the literal string `# noqa: F401` inside explanatory prose; ruff parsed it as a malformed noqa directive**

- **Found during:** first `ruff check` run after the `__all__` addition
- **Issue:** ruff scans for `# noqa` tokens in source text regardless of whether they're inside multi-line explanatory comments. The first draft's comment "even though the `# noqa: F401` silences the ruff pyflakes warning" produced two `Invalid # noqa directive` warnings (not errors, but noise).
- **Fix:** Rewrote the comments to refer to "the pyflakes F401 suppression" without using the literal `# noqa: F401` token sequence. Pure documentation change; no runtime/type impact.
- **Committed in:** `c7bc5adc`

**Total deviations:** 3 — all Rule 4 spec/documentation refinements at the implementation-detail layer. Zero business-logic deviations. Zero scope expansion: every change lives in `apps/backend/` and is directly required to satisfy `uv run mypy --strict app exits 0` per the plan's success criterion.

## Issues Encountered

- **First constant-retyping pass surfaced 3 cascading errors** (2 [assignment] at branch-narrowing sites + 1 [unused-ignore] at a local pin). All resolved in the same iteration loop; documented under Rule 4 above. Time cost: ~5 min for the cascade analysis + fix.
- **Comment-prose containing `# noqa: F401` literal** triggered ruff's noqa parser. Resolved by rewriting the comment to use the prose phrase "the pyflakes F401 suppression" instead of the literal directive token. Time cost: ~2 min.
- **No genuine blockers; no escalation needed.** Every fix landed inline without `# type: ignore` per D-63-06.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 63-04 (DEBT-04) is ready to start.** This plan ships `.planning/milestones/v1.5-verification-evidence/run.sh` hardening (4 hotfixes + RBAC actor fix + X-CSRF-Token threading). Zero overlap with `apps/backend/` — sweep commits will not be disturbed.
- **No new blockers.** D-63-02 serial ordering preserved (Plan 04 will start from `master` HEAD = `c7bc5adc`).
- **Plan 63-05 (DEBT-05) preview:** When Plan 5 runs the 6 CI gates locally, `uv run mypy` (default-scope, which now includes the `tests.*` override) is expected to exit 0 on `app/` strict subset and to either pass or have residual leniency-allowed warnings on `tests/`. The CI gate per D-63-03 is exactly `uv run mypy --strict app`, which exits 0 today.
- **STATE.md / ROADMAP.md / REQUIREMENTS.md** tracking commit follows this SUMMARY.md commit (separate per atomic-commit discipline).

## Self-Check: PASSED

**Created files exist:**
- `.planning/phases/63-tech-debt-sweep/63-03-SUMMARY.md` — FOUND (this file)

**Commits exist:**
- `c7bc5adc` — FOUND (`git log --oneline -1`)

**DEBT-03 success criterion verification:**
- `cd apps/backend && uv run mypy --strict app` — `Success: no issues found in 209 source files`, exit 0
- `cd apps/backend && uv run ruff check app tests` — `All checks passed!`, exit 0 (Plan 2 baseline preserved)
- `cd apps/backend && uv run ruff format --check .` — exit 0, `635 files already formatted` (Plan 1 baseline preserved)
- `cd apps/backend && uv run python -m scripts.export_openapi && cd ../.. && git diff --exit-code apps/backend/openapi.json` — exit 0 (no OpenAPI drift)
- `cd apps/backend && uv run pytest tests/unit -x -q` — 907 passed
- `grep -c '^\[\[tool.mypy.overrides\]\]' apps/backend/pyproject.toml` — `4` (was 3)
- `grep -c 'module = "tests\.\*"' apps/backend/pyproject.toml` — `1`
- `grep -c '^__all__ = \[' apps/backend/app/modules/auth/models.py` — `1`
- `git diff HEAD~1 HEAD --name-only | grep -v '^apps/backend/' | wc -l` — `0` (scope discipline preserved)
- D-63-06 compliance — 2 `# type: ignore` directives REMOVED, 0 added; 1 `# noqa` directive REMOVED, 0 added; net strict improvement
- D-63-05 compliance — `--unsafe-fixes` never invoked (plan does not run ruff --fix)

---

*Phase: 63-tech-debt-sweep*
*Completed: 2026-05-26*
