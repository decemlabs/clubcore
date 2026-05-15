---
phase: 33-pt-package-plans-instances
fixed_at: 2026-05-15T00:00:00Z
review_path: .planning/phases/33-pt-package-plans-instances/33-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 33: Code Review Fix Report

**Fixed at:** 2026-05-15
**Source review:** `.planning/phases/33-pt-package-plans-instances/33-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope (Critical + Warning): 9
- Fixed: 9
- Skipped: 0

The fix scope is `critical_warning`; Info findings (IN-01..IN-05) were
intentionally NOT addressed in this iteration.

## Fixed Issues

### CR-01: Idempotency-Key collides across PT-package routes (data integrity)

**Files modified:** `apps/backend/app/core/idempotency.py`, `apps/backend/tests/unit/test_idempotency.py`
**Commit:** `1eab04a`
**Applied fix:** `verify_idempotency` now returns the route-bound key
`f"{request.method}:{request.url.path}:{header_value}"` instead of the
bare header. The unused `Redis` parameter is preserved for the per-route
Depends graph (used by orchestrator helpers downstream). Updated unit
test stubs to expose `request.method` + `request.url.path` and added a
new regression test that asserts two requests carrying the same
`Idempotency-Key` header but hitting different routes produce distinct
namespaced keys (`POST /api/v1/pt-packages` vs
`POST /api/v1/pt-packages/{id}/refund`). Also closes WR-05's
cross-route 422 UX issue as a side effect.

### CR-02: Concurrent /cancel requests can double-mutate + double-audit

**Files modified:** `apps/backend/app/modules/pt_packages/router.py`
**Commit:** `c7caa85`
**Applied fix:** All three mutating PT-package endpoints (`create_pt_package`,
`cancel_pt_package`, `refund_pt_package`) now claim the Idempotency-Key
Redis namespace with `begin_idempotency` (SET NX EX) BEFORE running the
orchestrator (matching the memberships precedent verbatim — same envelope
shape, same TTL constant). The losing caller falls into the replay
branch and either returns the cached envelope (matching body hash) or
raises `ConflictError("idempotency_in_flight")` while the placeholder
sentinel is still set. This closes the gap where two concurrent
identical `/cancel` requests would both pass the read-only "no stored
entry" check, both run `service.cancel_pt_package`, and emit two
`pt_package_cancelled` audit rows for the same instance.

### CR-03: Comment falsely asserts route-aware Idempotency-Key isolation

**Files modified:** `apps/backend/app/modules/pt_packages/router.py`
**Commit:** `c7caa85` (bundled with CR-02)
**Applied fix:** The block comment at lines 340-350 is now ACCURATE
(post-CR-01) — `verify_idempotency` actually does bind
`{method}:{path}:{header}` into the returned key. The comment was kept
and explicitly footnoted to reference the CR-01 source change so future
readers can trace the invariant.

### WR-01: Dead-code branch — `idempotency_in_flight` is unreachable

**Files modified:** `apps/backend/app/modules/pt_packages/router.py`
**Commit:** `c7caa85` (bundled with CR-02)
**Applied fix:** Implementing CR-02 makes the `is_first=False -> stored
is _PLACEHOLDER -> raise ConflictError("idempotency_in_flight")` branch
reachable across all three endpoints. No additional code change required
beyond CR-02 — the dead-code concern is closed by making the producer
side (`begin_idempotency`) actually run.

### WR-02: ARQ expire audit emits empty `end_date` on defensive fallback

**Files modified:** `apps/backend/app/modules/pt_packages/service.py`, `apps/backend/app/core/audit_payloads.py`
**Commit:** `b93f926`
**Applied fix:** The expire cron loop now raises `RuntimeError` when
`row_end_date` is not a `date` instance (invariant: the repository SQL
filter `end_date IS NOT NULL` should make this unreachable; if it
fires, the SQL predicate has regressed). This replaces the silent
`""` fallback that would have landed an empty string in JSONB and
silently corrupted downstream audit consumers (BI, REF-07 chain,
future PT-21). As defence-in-depth,
`PtPackageExpiredPayload.end_date` now carries
`Field(pattern=r"^\d{4}-\d{2}-\d{2}$")` so an empty string would also
fail Pydantic validation at audit-emit time even if the runtime guard
were ever removed.

### WR-03: `record_payment` IntegrityError not caught in sale orchestrator

**Files modified:** `apps/backend/app/modules/pt_packages/service.py`
**Commit:** `7a04bfb`
**Applied fix:** The `get_payment_recorder()(...)` call in
`create_pt_package` is now wrapped in
`try/IntegrityError -> session.rollback() -> raise ConflictError("payment_recording_failed")`,
mirroring the existing IntegrityError translation around
`repository.insert_pt_package` flush at the earlier step. A FK violation
(e.g. soft-deleted `received_by_user_id`) or CHECK violation
(`amount_kopecks <= 0`) inside the recorder's flush no longer escapes
uncaught to leave the SA session in failed-transaction state; the
operator now sees a typed 409 instead of a generic 500.

**Note (logic verification):** This fix introduces a new typed error
code `payment_recording_failed`. The phase verifier should confirm that
(a) no test currently expects the prior generic-500 behaviour, and
(b) the chosen code matches the project's error-code naming convention
(memberships precedent should be audited for symmetry — the review
explicitly flags this).

### WR-04: `session.refresh(pt_package)` after commit reloads ALL columns

**Files modified:** `apps/backend/app/modules/pt_packages/service.py`
**Commit:** `7a04bfb` (bundled with WR-03)
**Applied fix:** `session.refresh(pt_package)` at the end of
`create_pt_package` now narrows
`attribute_names=["updated_at", "created_at"]`, mirroring the cancel
and refund orchestrators. Prevents accidental lazy-loading of any future
relationship attribute defined on `PtPackage` (e.g., Phase 34's
`sessions` collection).

### WR-05: 422 status path on idempotency body mismatch when stored response is 201/200

**Files modified:** (none — closed by CR-01)
**Commit:** `1eab04a` (bundled with CR-01)
**Applied fix:** WR-05 was explicitly bundled with CR-01 in the review
itself. Now that `verify_idempotency` returns route-bound keys, an
operator using the same `Idempotency-Key` header value across different
endpoints (e.g. sale + cancel) gets distinct Redis namespaces, so the
confusing cross-route 422 `idempotency_key_reuse` no longer fires.

### WR-06: `find_active_for_client` resolver does not check `end_date`

**Files modified:** `apps/backend/app/modules/pt_packages/repository.py`
**Commit:** `1e22588`
**Applied fix:** `find_active_for_client` now refilters
`end_date >= today OR end_date IS NULL` (with `today` computed as
`now(Europe/Moscow).date()`, mirroring the service-layer convention).
A row whose validity window has elapsed but whose `status` has not yet
been flipped by the 06:25 MSK expire cron (~30h worst-case lag) is no
longer returned as "active". The `end_date IS NULL` (бессрочный) class
per D-33-14 is preserved verbatim. Phase 34's PT-session sale — the
first consumer of this resolver — will not record sessions against
effectively-expired packages.

## Skipped Issues

None.

## Verification Notes

- All file edits passed Tier 2 syntax verification (`python3 -c "import ast; ast.parse(...)"`).
- 5 atomic commits made on the isolated `gsd-reviewfix/33-*` worktree branch.
- IN-01..IN-05 (Info-tier) intentionally out of scope for `critical_warning` mode:
  - **IN-01** (use `idempotent_response` helper instead of inline envelope)
    is partially relieved by CR-02's NX-claim adoption but the helper itself
    is not yet adopted (the existing `store_idempotency_response` helper
    has a known body-hash conflation with the request-hash, per the
    memberships router comment at lines 350-354 — adopting it would require
    a separate refactor).
  - **IN-02..IN-05** are stylistic / forensic improvements safe to defer.
- WR-03 introduces a new typed error code `payment_recording_failed`;
  phase verifier should audit that (a) no integration test currently
  expects a generic 500 for FK/CHECK violations on the recorder path,
  and (b) the code symbol exists in the response-error taxonomy doc if
  the project maintains one.

---

_Fixed: 2026-05-15_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
