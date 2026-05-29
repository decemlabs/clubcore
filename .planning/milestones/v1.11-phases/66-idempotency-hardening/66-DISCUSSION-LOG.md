# Phase 66: Idempotency Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 66-idempotency-hardening
**Mode:** `--auto` (single-pass; recommended defaults selected without interactive prompts)
**Areas discussed:** Lifecycle abstraction, User-scope key wiring, Exception-cleanup semantics, OpenAPI IdempotencyKey injection, Endpoint classification rubric, Plan decomposition

---

## Lifecycle abstraction

| Option | Description | Selected |
|--------|-------------|----------|
| Extract shared orchestrator | One lifecycle helper in `idempotency.py`; refactor 3 existing callsites onto it; IDM-06 exception logic written once | ✓ |
| Keep inline per-route + add try/except to each | ~10 copies of the claim/replay/store block, exception cleanup duplicated 10× | |

**Auto-selected:** Extract shared orchestrator (recommended).
**Notes:** IDM-06's AppError-vs-unknown-exception branching is subtle; centralizing it eliminates the 10× bug surface that hardening exists to remove. IDM-07 adds 7 callsites — a shared helper makes each a 1-line wire. → D-66-LIFECYCLE-HELPER.

---

## User-scope key wiring (IDM-05)

| Option | Description | Selected |
|--------|-------------|----------|
| `Depends(get_current_user)` in `verify_idempotency` | Key = `cc:idem:{user_id}:{method}:{path}:{header}`; FastAPI dedups the dependency | ✓ |
| Session-token-hash in key | Hash the JWT/cookie instead of user.id | |

**Auto-selected:** `Depends(get_current_user)`, user_id-first key shape (recommended; matches PITFALLS C-03 snippet + REQUIREMENTS IDM-05 exact shape).
**Notes:** Existing 3 callsites inherit the user-scoped key automatically. → D-66-USER-SCOPE.

---

## Exception-cleanup semantics (IDM-06)

| Option | Description | Selected |
|--------|-------------|----------|
| AppError → store error envelope; unknown → delete placeholder | Retries replay known errors; unknown failures allow a fresh retry | ✓ |
| Always delete placeholder on any exception | Simpler, but loses consistent-error replay | |
| Always store (even unknown) | Risks caching transient 500s as permanent | |

**Auto-selected:** AppError → store error envelope; unknown Exception → delete placeholder (recommended; PITFALLS C-02 pattern).
**Notes:** Error envelope retains request body-hash so same-key/different-body retry still 422s. Integration test covers both branches. → D-66-EXC-CLEANUP.

---

## OpenAPI IdempotencyKey injection (IDM-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 64 `create_app()` post-processor | Inject `$ref` into category-A operations in one place; byte-stable | ✓ |
| Per-router `openapi_extra` / parameters kwarg | Edit every router; higher touch | |

**Auto-selected:** Reuse Phase 64 post-processor (recommended; mirrors D-64-RESPONSES-APPLY).
**Notes:** Includes the PITFALLS C-05 replay-semantics note in the parameter description. Pattern length `{16,128}` must stay in lockstep with `IDEMPOTENCY_KEY_PATTERN`. → D-66-OPENAPI-PARAM.

---

## Endpoint classification rubric (IDM-01)

| Option | Description | Selected |
|--------|-------------|----------|
| A=financial/state-creating + unguarded creates; B=read-only/webhook/naturally-idempotent; C=inconsistent→A | Per-endpoint table with rationale at locked path | ✓ |
| Enforce key on ALL mutating endpoints | Forces keys on naturally-idempotent PATCH/DELETE — noisy | |

**Auto-selected:** Three-tier rubric with per-endpoint rationale (recommended).
**Notes:** Naturally-idempotent absolute PATCH/soft-delete → B unless they emit audit events per call. A-set is the authoritative input to IDM-04 + IDM-07. → D-66-CLASSIFY-RUBRIC.

---

## Plan decomposition

| Option | Description | Selected |
|--------|-------------|----------|
| 5 atomic plans (audit → core → wire → spec → tests) | One requirement-group per plan; dependency-ordered | ✓ |
| One monolithic plan | Single large diff, hard to review/revert | |

**Auto-selected:** 5 atomic plans (recommended; mirrors Phase 63/64 atomicity).
**Notes:** Core plan (66-02) bundles IDM-02+05+06+refactor because they touch the same module + same 3 callsites. → D-66-PLANS.

---

## Claude's Discretion

- Exact orchestrator shape (context-manager vs callable-wrapper vs decorator).
- Dynamic vs explicit-frozenset category-A allowlist for the IDM-04 post-processor.
- Exact `serialize_error` JSON shape (must match `app/core/exceptions.py`).
- Whether replay must capture headers beyond `Content-Type`.

## Deferred Ideas

- `Idempotency-Key` on the ЮKassa webhook → never (D-11-IDM-WEBHOOK).
- Monitoring/alerting on stuck `__in_flight__` keys → future observability phase.
- Runbook idempotency prose → Phase 65.
- Client-side retry-key generation guidance → Phase 65 handoff docs.
