---
phase: 66-idempotency-hardening
verified: 2026-05-29T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 66: Idempotency Hardening Verification Report

**Phase Goal:** `verify_idempotency` user-scoped (security fix); 86400s TTL; all category-A endpoints covered; `components.parameters.IdempotencyKey` in spec; double-submit integration tests pass (IDM-01..07)
**Verified:** 2026-05-29
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                              | Status     | Evidence                                                                                                                    |
|----|----------------------------------------------------------------------------------------------------|------------|-----------------------------------------------------------------------------------------------------------------------------|
| 1  | `verify_idempotency` binds `Depends(get_current_user)`; Redis key is `cc:idem:{user_id}:{method}:{path}:{header}` | VERIFIED | `idempotency.py:76` — `current_user: Annotated[_CurrentUser, Depends(_get_current_user)]`; line 107 returns `f"{current_user.id}:{request.method}:{request.url.path}:{key}"` |
| 2  | `IDEMPOTENCY_TTL_SECONDS == 86400` and `IDEMPOTENCY_KEY_PATTERN == r"^[A-Za-z0-9_:-]{16,128}$"` | VERIFIED | `idempotency.py:48-52` — both constants confirmed at correct values |
| 3  | `idempotent_execute` has AppError→store-error-envelope and unknown-Exception→delete-placeholder branches; `create_time_off` routes through orchestrator with no remaining inline wedge (CR-01 fix) | VERIFIED | `idempotency.py:293-326` (AppError branch) and `327` (Exception branch); `schedule/router.py:371-409` — `create_time_off` uses `_runner()` + `idempotent_execute`; no `begin_idempotency` calls remain in any module router |
| 4  | 4 membership transitions (cancel/freeze/unfreeze/renew) carry `Depends(verify_idempotency)`; ЮKassa webhook has exclusion comment and is NOT wired | VERIFIED | `memberships/router.py:348,403,455,507` — all 4 have `Depends(verify_idempotency)`; `yookassa/router.py:79-86` — D-11-IDM-WEBHOOK exclusion comment confirmed |
| 5  | `components.parameters.IdempotencyKey` present in `openapi.json` with 22 `$ref` injections; pattern matches runtime constant | VERIFIED | `openapi.json` — `components.parameters.IdempotencyKey` present with `pattern: ^[A-Za-z0-9_:-]{16,128}$`, `required: true`, `in: header`; 22 `$ref` injections confirmed; `main.py:79` imports `IDEMPOTENCY_KEY_PATTERN` (byte-lockstep by construction) |
| 6  | `.planning/handoff/v1.11-idempotency-audit.md` exists with A/B/C classification table and category-A operationId set | VERIFIED | File exists; line 33 has exact column header; "Category-A operationId set" section present with 22 entries |
| 7  | Integration tests exist for all 5 modules (memberships/online_payments/pt_packages/pt_sessions/bookings) covering double-submit byte-identical replay, no-re-emit-audit, cross-user isolation, AppError-replay, rollback-retry, 422 reuse; all 48 tests pass | VERIFIED | All 5 `test_idempotency_hardening.py` files exist; `uv run pytest ... -q` → **48 passed in 13.36s** |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact                                                                             | Expected                                             | Status     | Details                                                                                   |
|--------------------------------------------------------------------------------------|------------------------------------------------------|------------|-------------------------------------------------------------------------------------------|
| `apps/backend/app/core/idempotency.py`                                               | User-scoped key, 86400 TTL, {16,128} pattern, orchestrator | VERIFIED | All constants and `idempotent_execute` present; exported in `__all__`                    |
| `apps/backend/app/modules/memberships/router.py`                                     | cancel/freeze/unfreeze/renew wired                   | VERIFIED   | 5× `Depends(verify_idempotency)` at lines 291, 348, 403, 455, 507                        |
| `apps/backend/app/modules/schedule/router.py`                                        | `create_time_off` on orchestrator (CR-01 fix)        | VERIFIED   | Lines 355, 409: `Depends(verify_idempotency)` + `idempotent_execute` call                |
| `apps/backend/app/api/v1/_internal/yookassa/router.py`                               | Webhook exclusion comment                            | VERIFIED   | D-11-IDM-WEBHOOK comment at lines 79-86                                                  |
| `apps/backend/app/main.py`                                                           | `CATEGORY_A_OPERATION_IDS` frozenset (22 entries)    | VERIFIED   | Lines 254+; 22 entries; `IDEMPOTENCY_KEY_PATTERN` imported from `app.core.idempotency`  |
| `apps/backend/openapi.json`                                                          | `components.parameters.IdempotencyKey` + 22 `$refs` | VERIFIED   | Param exists; 22 category-A operations carry `$ref: '#/components/parameters/IdempotencyKey'` |
| `.planning/handoff/v1.11-idempotency-audit.md`                                       | A/B/C table + category-A list                        | VERIFIED   | Table header matches locked spec; category-A list present with 22 sorted entries         |
| `apps/backend/tests/unit/test_idempotency_orchestrator.py`                           | Unit tests for orchestrator behavior                 | VERIFIED   | Exists with 15 test functions                                                            |
| `apps/backend/tests/integration/memberships/test_idempotency_hardening.py`           | 15 tests                                             | VERIFIED   | 15 tests including cross-user (IDM-05), AppError-replay, rollback-retry (IDM-06)        |
| `apps/backend/tests/integration/online_payments/test_idempotency_hardening.py`       | 12 tests                                             | VERIFIED   | 12 tests covering 4 sell endpoints                                                       |
| `apps/backend/tests/integration/pt_packages/test_idempotency_hardening.py`           | 9 tests                                             | VERIFIED   | 9 tests covering create, cancel, refund                                                  |
| `apps/backend/tests/integration/pt_sessions/test_idempotency_hardening.py`           | 6 tests                                              | VERIFIED   | 6 tests covering record, cancel                                                          |
| `apps/backend/tests/integration/bookings/test_idempotency_hardening.py`              | 6 tests                                              | VERIFIED   | 6 tests covering create, cancel                                                          |

### Key Link Verification

| From                                              | To                                                      | Via                                                             | Status   | Details                                                                                                      |
|---------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------|----------|--------------------------------------------------------------------------------------------------------------|
| `verify_idempotency` in `idempotency.py`          | `dependencies.py get_current_user`                      | `Depends(_get_current_user)` — line 76                          | WIRED    | `current_user.id` prefixes the returned key string                                                           |
| `memberships/router.py cancel/freeze/unfreeze/renew` | `idempotency.py idempotent_execute`                  | `_runner()` closures calling `idempotent_execute`               | WIRED    | 4 endpoints all route through `idempotent_execute`; RBAC-04 ordering preserved                              |
| `schedule/router.py create_time_off`              | `idempotency.py idempotent_execute`                     | `_runner()` with TimeOffBookedConflictError handled inside runner | WIRED  | CR-01 blocker resolved in commit 92ca0def; no remaining `begin_idempotency` inline block                   |
| `main.py CATEGORY_A_OPERATION_IDS`                | `openapi.json` category-A operations                   | `_customize_openapi` per-op walk appends `$ref` when operationId in frozenset | WIRED | 22 `$ref` injections confirmed; frozenset size matches `$ref` count                                        |
| `idempotency.py IDEMPOTENCY_KEY_PATTERN`          | `openapi.json components.parameters.IdempotencyKey.schema.pattern` | Imported via `from app.core.idempotency import IDEMPOTENCY_KEY_PATTERN` in `main.py` | WIRED | Pattern byte-lockstep by construction — same object, not re-typed                                     |
| `yookassa/router.py yookassa_webhook`             | `cc:yookassa:webhook:` dedup (separate path)           | Code comment documenting the intentional exclusion               | WIRED    | D-11-IDM-WEBHOOK / D-66-WEBHOOK-EXCLUDE comment present; no `verify_idempotency` call on webhook           |

### Data-Flow Trace (Level 4)

Not applicable — this is a security/backend hardening phase with no UI data rendering. The critical data flows are Redis key construction and orchestrator exception branches, verified via live test execution (48 integration tests, real Postgres + real Redis).

### Behavioral Spot-Checks

| Behavior                                                             | Command                                                                                                               | Result       | Status |
|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|--------------|--------|
| All 48 idempotency hardening tests pass                              | `uv run pytest tests/integration/*/test_idempotency_hardening.py -q`                                                 | 48 passed    | PASS   |
| CATEGORY_A_OPERATION_IDS has 22 entries with correct values          | `uv run python3 -c "from app.main import CATEGORY_A_OPERATION_IDS; assert len(CATEGORY_A_OPERATION_IDS)==22"` | len == 22    | PASS   |
| openapi.json has IdempotencyKey component with 22 `$ref` injections  | `python3 -c "import json; s=json.load(open('openapi.json')); ..."` (confirmed in verification)                       | 22 refs      | PASS   |
| Pattern byte-lockstep (spec pattern == runtime constant)             | `uv run python3 -c "from app.core.idempotency import IDEMPOTENCY_KEY_PATTERN; assert IDEMPOTENCY_KEY_PATTERN == r'^[A-Za-z0-9_:-]{16,128}$'"` | matches  | PASS   |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                         | Status    | Evidence                                                                                         |
|-------------|-------------|-----------------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------|
| IDM-01      | 66-01       | Endpoint classification audit with A/B/C table committed to `.planning/handoff/v1.11-idempotency-audit.md` | SATISFIED | File exists; table with exact column header present; 22-entry category-A list present           |
| IDM-02      | 66-02       | 16-128 char key pattern; 86400s TTL; cached-response replay; body-hash mismatch → 422              | SATISFIED | `IDEMPOTENCY_TTL_SECONDS=86400`, `IDEMPOTENCY_KEY_PATTERN=r"^[A-Za-z0-9_:-]{16,128}$"` confirmed |
| IDM-03      | 66-05       | Integration tests for double-submit on high-priority category-A endpoints; replay without re-emitting audit | SATISFIED | 48 passing integration tests across 5 modules covering all specified behaviors                  |
| IDM-04      | 66-04       | `components.parameters.IdempotencyKey` in `openapi.json`; every category-A endpoint references via `$ref` | SATISFIED | IdempotencyKey component present; 22 `$refs` exactly matching CATEGORY_A_OPERATION_IDS          |
| IDM-05      | 66-02       | `verify_idempotency` binds `Depends(get_current_user)`; Redis key includes `user.id`               | SATISFIED | `verify_idempotency` line 76: `Depends(_get_current_user)`; return line 107: user-scoped prefix  |
| IDM-06      | 66-02       | In-flight placeholder cleanup: AppError→store-error-envelope; unknown-Exception→delete-placeholder; `create_time_off` migrated (CR-01) | SATISFIED | `idempotent_execute` exception branches at lines 293-327; `create_time_off` uses orchestrator; no inline `begin_idempotency` remains |
| IDM-07      | 66-03       | All category-A endpoints have `Depends(verify_idempotency)`; ЮKassa webhook excluded with comment  | SATISFIED | 22 endpoints wired; membership transitions (5 in router.py); webhook exclusion comment present  |

### Anti-Patterns Found

| File                                                   | Line | Pattern | Severity | Impact                                                                                                     |
|--------------------------------------------------------|------|---------|-----------|------------------------------------------------------------------------------------------------------------|
| `apps/backend/app/core/idempotency.py`                | 328-340 | Success-store `redis.set` is outside `try/except` (WR-01 from code review) | WARNING  | If Redis raises during success-store after DB commit, placeholder stays and 409 is returned on retry for 24h. Code review acknowledged; no fix applied in this phase. Phase goal not blocked by this — it is a narrow-trigger edge case documented in REVIEW.md as WR-01. |
| `apps/backend/app/core/idempotency.py`                | 107  | Colon-separator key could theoretically collide for future string path params (WR-02) | WARNING  | All current path params are UUIDs (colon-free); invariant is implicit not enforced. Documented in REVIEW.md as WR-02. No current path creates collision. |
| `apps/backend/app/core/idempotency.py`                | ~73  | `redis` parameter in `verify_idempotency` declared but not used in function body (WR-03) | INFO     | Dead code but not a correctness issue; documented in REVIEW.md WR-03. |
| `apps/backend/app/core/idempotency.py`                | ~182 | `idempotent_response` is dead code (IN-01 from code review)                    | INFO     | Defined and exported but zero callers; superseded by `idempotent_execute`. Documented in REVIEW.md IN-01. |

No TBD, FIXME, or XXX markers found in any file modified by this phase.

### Human Verification Required

None — all must-haves are verifiable programmatically for this backend-only security hardening phase. The 48 integration tests against real Postgres + real Redis provide behavioral proof.

### Gaps Summary

No gaps. All 7 IDM requirements are SATISFIED. The 4 code-review items (WR-01, WR-02, WR-03, IN-01) are quality improvements documented in the review report but none block the phase goal. The CR-01 blocker identified in REVIEW.md was fixed in commit 92ca0def before the review was written — `create_time_off` is confirmed on the `idempotent_execute` orchestrator with no remaining `begin_idempotency` inline block in any router.

---

_Verified: 2026-05-29_
_Verifier: Claude (gsd-verifier)_
