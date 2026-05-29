# Phase 66: Idempotency Hardening - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** `--auto` (single-pass; all gray areas auto-resolved with recommended defaults — user may override before plan-phase)

<domain>
## Phase Boundary

Harden the existing `Idempotency-Key` mechanism (`apps/backend/app/core/idempotency.py` + 3 wired callsites) into a complete, secure, spec-documented contract. Seven deliverables (IDM-01..07):

1. **IDM-01** — Classify every mutating endpoint (POST/PATCH/PUT/DELETE) under `apps/backend/app/api/v1/` as **A** (requires `Idempotency-Key` enforcement), **B** (exempt), or **C** (inconsistent → move to A). Commit the audit table to `.planning/handoff/v1.11-idempotency-audit.md`.
2. **IDM-02** (closes CR-01) — Standardize key semantics: 16–128 chars (UUIDv4 conventional), TTL → **86400s (24h)** (was 3600s), replay returns identical body+status+headers, request-body-hash mismatch on same key → 422 (no silent 200).
3. **IDM-03** (closes CR-02) — Double-submit integration tests for high-priority category-A endpoints in `memberships`, `online_payments`, `pt_packages`, `pt_sessions`, `bookings` (real Postgres, real Redis, ASGITransport); replay returns cached response **without re-emitting audit events**.
4. **IDM-04** (closes CR-02b) — Add `components.parameters.IdempotencyKey` reusable parameter to `openapi.json`; every category-A endpoint references it via `$ref`; semantics documented (runbook is a Phase 65 dependency).
5. **IDM-05** (PITFALLS C-03 / Pitfall #7) — User-scope security fix: `verify_idempotency` binds `Depends(get_current_user)`; Redis key includes `user.id` → `cc:idem:{user_id}:{method}:{path}:{key}`; closes cross-user replay under multi-user admin (v1.6). Existing 3 callsites stay green. ЮKassa webhook explicitly NOT affected (separate `cc:yk:webhook:*` dedup).
6. **IDM-06** (PITFALLS C-02 / Pitfall #8) — Exception-aware lifecycle: delete `__in_flight__` placeholder on unknown exceptions (no 24h lockout); store an error envelope on `AppError` (retries replay the error consistently); integration test covers the DB-rollback path.
7. **IDM-07** — Wire `Depends(verify_idempotency)` to ALL category-A endpoints (currently 3; ~7 more expected in `memberships` freeze/unfreeze/renew + `online_payments` create/refund + any IDM-01 gaps). ЮKassa webhook excluded with an annotating code comment.

**Scope anchor:** Hardening + coverage + documentation of the EXISTING idempotency primitive. NO new business endpoints, NO new ORM entities, NO behaviour change to the underlying business operations. Backend-only milestone; `apps/admin-web` is frozen except for mechanical `schema.d.ts` drift caused by the IDM-04 OpenAPI parameter. This phase executes **before** Phase 65 (handoff artifacts derive from the post-Phase-66 spec).

</domain>

<decisions>
## Implementation Decisions

### Lifecycle abstraction (the central architectural decision — spans IDM-05/06/07)

- **D-66-LIFECYCLE-HELPER:** Extract the full idempotency lifecycle (claim → run handler → store success/error envelope → cleanup-on-exception) into **one shared orchestrator** in `app/core/idempotency.py`, and refactor the 3 existing inline callsites (`pt_packages`, `pt_sessions`, `bookings` routers) onto it. Do NOT duplicate the ~40-line claim/replay/store block (currently copy-pasted per route, e.g. `pt_packages/router.py:244-300`) across the ~10 category-A endpoints.
  - **Why:** IDM-06's exception-aware cleanup is subtle (AppError vs unknown-exception branches). Implementing it once in a shared helper is the difference between 1 correct implementation and 10 chances to get it wrong — exactly the bug-surface hardening should eliminate. IDM-07 adds 7 more callsites; a shared helper makes wiring them a 1-line `Depends` + thin call.
  - **How to apply:** The existing composed `idempotent_response(redis, key, body_bytes)` only handles the *pre-handler* check (claim/replay/in-flight/body-diff). Extend the module with an orchestrator that ALSO owns the post-handler store and the exception branches — e.g. an async context manager or a wrapper that takes the handler as a callable so the route body becomes `return await idempotent_execute(redis, key, request, handler=lambda: service.create_x(...))`. Researcher/planner finalizes the exact shape (context-manager vs callable-wrapper) against FastAPI's `Response` return contract. The orchestrator must preserve today's verbatim replay (base64 body + status + media_type).
  - **Constraint:** Refactoring the 3 existing callsites is in-scope and MUST keep their existing tests green (regression-safe refactor, not a rewrite).

### User-scope key (IDM-05 / D-11-IDM-USER / PITFALLS C-03)

- **D-66-USER-SCOPE:** Add `current_user: Annotated[CurrentUser, Depends(get_current_user)]` to `verify_idempotency` (`app/core/dependencies.py:767` is `get_current_user`). FastAPI dedups the dependency, so adding it alongside the existing `require_permission` graph is safe and adds no extra DB hit.
  - **Key shape (LOCKED to REQUIREMENTS IDM-05):** the dependency returns `f"{current_user.id}:{request.method}:{request.url.path}:{key}"`, and with the `cc:idem:` prefix the full Redis key is **`cc:idem:{user_id}:{method}:{path}:{header_value}`**. `user_id` comes FIRST after the prefix (matches the requirement text exactly).
  - **Why:** Closes the cross-user replay attack (user A's cached response served to user B on key collision) under multi-user admin (v1.6 shipped 4 operator pairs). Real risk, not hypothetical — human-chosen keys (`retry-1`, timestamps) collide.
  - **How to apply:** The 3 existing callsites already use `Depends(verify_idempotency)` and inherit the new user-scoped key automatically (FastAPI resolves the full graph). No callsite signature change for user-scoping.

### Exception-cleanup semantics (IDM-06 / PITFALLS C-02)

- **D-66-EXC-CLEANUP:** The shared orchestrator (D-66-LIFECYCLE-HELPER) handles handler exceptions as:
  - **`AppError` (known, e.g. `ConflictError`, `ValidationAppError`)** → serialize the error envelope (matching `app/core/exceptions.py` handler shape) and `store_idempotency_response(status_code=exc.status_code, body_bytes=error_bytes)`, THEN re-raise. Retries with the same key replay the SAME error (not `idempotency_in_flight`).
  - **Unknown `Exception` (DB unreachable, 500, rollback)** → `redis.delete(_redis_key(key))` (drop the placeholder), THEN re-raise. The next retry attempts fresh rather than being locked out for 24h.
  - **Why:** Today, if the handler raises after `begin_idempotency` claims the placeholder, `store_idempotency_response` never runs — the `__in_flight__` marker stuck for the full TTL (now 24h after IDM-02). PITFALLS C-02 documents this lockout. Trading "guaranteed at-most-once" for "retry gets another chance" is correct for these non-webhook endpoints; payment endpoints are additionally DB-layer idempotent (UNIQUE + `ON CONFLICT`).
  - **Body-hash on error replay:** the stored error envelope keeps the request body-hash, so a same-key retry with a DIFFERENT body still gets 422 `idempotency_key_reuse` (consistent with success-path semantics).
  - **Test (IDM-06):** integration test submits a request that raises a service-layer `AppError` and a request that triggers a DB rollback, then retries with the same key — asserts (a) AppError path replays the original error, (b) rollback path allows a fresh retry, neither returns `idempotency_in_flight`.

### OpenAPI IdempotencyKey parameter (IDM-04 / closes CR-02b)

- **D-66-OPENAPI-PARAM:** Add `components.parameters.IdempotencyKey` (header param, `name: Idempotency-Key`, `in: header`, `required: true`, `schema: {type: string, pattern: "^[A-Za-z0-9_:-]{16,128}$"}`) and inject `$ref: "#/components/parameters/IdempotencyKey"` into every category-A operation via the **Phase 64 `create_app()` post-processor** (mirrors D-64-RESPONSES-APPLY / D-64-SEC-APPLY).
  - **Why:** Phase 64 already established a byte-stable post-processor that walks the built schema and injects `$ref`s in one place — reuse it instead of editing every router. Keeps the diff localized and drift-gate-green.
  - **How to apply:** Category-A operations are identified as those whose route declares `Depends(verify_idempotency)` (the post-processor can key off the operation set produced by IDM-07, or off an explicit allowlist frozenset mirroring D-64-SEC-APPLY's public-endpoint allowlist discipline). Add the parameter description note from PITFALLS C-05: *"The cached response is the response at time of first successful execution; retries replay it verbatim. For current resource state, use the resource's GET endpoint."* Final task: `uv run python -m scripts.export_openapi && pnpm --filter @clubcore/api-client codegen && git diff --exit-code` (byte-stable, drift gate green).
  - **Note (IDM-02 pattern reconciliation):** existing `IDEMPOTENCY_KEY_PATTERN` is `^[A-Za-z0-9_:-]{1,128}$` (min length 1). IDM-02 standardizes to **16–128 chars**. The pattern constant in `idempotency.py` AND the OpenAPI schema MUST both move to `{16,128}`. This is a behaviour change to `verify_idempotency` validation — covered by IDM-02, surfaced here because the two must stay in lockstep.

### Endpoint classification rubric (IDM-01)

- **D-66-CLASSIFY-RUBRIC:** Audit output at `.planning/handoff/v1.11-idempotency-audit.md` (path LOCKED by IDM-01). Per-endpoint classification rubric:
  - **A (enforce `Idempotency-Key`):** financial / value-creating mutations (sales, refunds, payment creation), membership state transitions (freeze/unfreeze/renew/cancel where they emit audit events or charge), and any POST create that is NOT already guarded by a DB uniqueness gate making double-submit harmless.
  - **B (exempt):** read-only routes; the ЮKassa webhook (separate `cc:yk:webhook:*` dedup, D-11-IDM-WEBHOOK); naturally idempotent absolute-value PATCH/PUT and soft-delete DELETE (re-applying the same absolute state or delete is a no-op) — UNLESS they emit audit events on every call, in which case → A.
  - **C (currently inconsistent → move to A):** endpoints that should be A but lack `Depends(verify_idempotency)` today; these become IDM-07's wiring list.
  - **How to apply:** the audit table has columns `endpoint | method | classification | emits-audit-event? | DB-unique-guarded? | rationale`. Every row gets a one-line rationale. The A-set from this table is the authoritative input to IDM-04 (`$ref` injection) and IDM-07 (wiring).

### Webhook exclusion (IDM-07 / D-11-IDM-WEBHOOK)

- **D-66-WEBHOOK-EXCLUDE:** The ЮKassa webhook (`app/api/v1/_internal/yookassa/router.py`) already uses a separate `SET NX EX 86400` dedup on `WEBHOOK_DEDUP_KEY_PREFIX` (`router.py:53-106`) and does NOT use `verify_idempotency`. It has no `current_user` to scope to. IDM-07 adds an explicit code comment at the webhook handler annotating the separate dedup path and why user-scoped `verify_idempotency` does not apply. No functional change to the webhook.

### Plan decomposition (atomic commits — mirrors Phase 63/64 discipline)

- **D-66-PLANS:** Recommended 5 atomic plans (planner finalizes; one requirement-group per plan, each leaving CI green at HEAD):
  1. **66-01 — IDM-01** (classification audit doc). Doc-only, no code; produces the authoritative A-set that 66-02..05 consume. First because everything downstream depends on the A-set.
  2. **66-02 — IDM-02 + IDM-05 + IDM-06 + lifecycle refactor** (core `app/core/idempotency.py` change: TTL 86400, pattern `{16,128}`, user-scoped key, exception-aware shared orchestrator; refactor the 3 existing callsites onto it). Bundled — all touch the same module + the same 3 callsites; splitting would churn the same lines twice.
  3. **66-03 — IDM-07** (wire `Depends(verify_idempotency)` + the shared orchestrator into the ~7 new category-A endpoints; add the webhook-exclusion comment).
  4. **66-04 — IDM-04** (OpenAPI `components.parameters.IdempotencyKey` + `$ref` injection via post-processor; byte-stable regen + drift gate).
  5. **66-05 — IDM-03 (+ IDM-06 test)** (double-submit integration tests across memberships/online_payments/pt_packages/pt_sessions/bookings; replay-without-re-emit-audit assertions; rollback-path test).
  - **Rationale:** ordering respects dependencies (audit → core primitive → coverage → spec → tests). Planner may merge 66-04/66-05 or split 66-02 if any plan's diff is too large to review atomically.

### Claude's Discretion

- Exact shape of the shared orchestrator (async context manager vs callable-wrapper vs decorator) — researcher/planner picks whichever cleanly preserves the `Response` verbatim-replay contract and FastAPI dependency ordering.
- Whether the category-A allowlist for the IDM-04 post-processor is derived dynamically (operations carrying `Depends(verify_idempotency)`) or declared as an explicit frozenset literal (D-64-SEC-APPLY style) — planner decides; explicit frozenset is preferred if drift-visibility matters.
- Exact `serialize_error` shape for IDM-06 — must match the live exception-handler envelope in `app/core/exceptions.py`; researcher confirms the precise JSON.
- Whether `IDM-02`'s replay must capture response headers beyond `Content-Type` — researcher confirms whether any category-A response sets custom headers (e.g. `Location`); if none, the existing status+body+media_type envelope is sufficient and "identical headers" is satisfied trivially.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 66 scope authority
- `.planning/ROADMAP.md` §"Phase 66: Idempotency Hardening" — goal, 7 success criteria, the non-monotonic ordering note (66 executes before 65)
- `.planning/REQUIREMENTS.md` §"Idempotency Hardening (Phase 66 — IDM-*)" lines 38-48 — the 7 authoritative IDM-* requirements
- `.planning/REQUIREMENTS.md` lines 118-119 — D-11-IDM-USER + D-11-IDM-WEBHOOK decision rationale
- `.planning/PROJECT.md` §"Current Milestone: v1.11 API Handoff + Production Hardening"

### v1.11 milestone decisions (locked 2026-05-26)
- `.planning/STATE.md` §"Key v1.11 Decisions" — D-11-IDM-USER (user-scoped key), D-11-IDM-WEBHOOK (webhook separate dedup)

### Pitfalls research (authoritative HOW-to-avoid guidance)
- `.planning/research/PITFALLS.md` §"Pitfall C-02" lines 35-72 — in-flight placeholder stuck after rollback; the try/except store-error vs delete-placeholder pattern (IDM-06)
- `.planning/research/PITFALLS.md` §"Pitfall C-03" lines 75-105 — cross-user replay; the `Depends(get_current_user)` user-scope snippet (IDM-05)
- `.planning/research/PITFALLS.md` §"Pitfall C-05" lines 129-149 — idempotency replays verbatim, NOT current DB state; the IdempotencyKey parameter description note (IDM-04)
- `.planning/research/PITFALLS.md` line 385 + line 395 — TTL 86400 rationale (matches ЮKassa webhook window) + user-scope key rationale

### Code anchors (read before planning)
- `apps/backend/app/core/idempotency.py` — current primitive: `verify_idempotency`, `begin_idempotency`, `store_idempotency_response`, `load_idempotency_response`, `idempotent_response`, `IDEMPOTENCY_KEY_PATTERN` (`{1,128}` → change to `{16,128}`), `IDEMPOTENCY_TTL_SECONDS=3600` (→ 86400), `IDEMPOTENCY_REDIS_PREFIX="cc:idem:"`
- `apps/backend/app/core/dependencies.py:767` — `get_current_user` (the dependency to bind for user-scope, IDM-05)
- `apps/backend/app/core/exceptions.py` — error-envelope shape (source for IDM-06 error serialization)
- `apps/backend/app/modules/pt_packages/router.py:207-300` — existing inline claim/replay/store callsite (refactor target + the duplication this phase eliminates)
- `apps/backend/app/modules/pt_sessions/router.py`, `apps/backend/app/modules/bookings/router.py` — the other 2 existing `verify_idempotency` callsites (refactor targets, must stay green)
- `apps/backend/app/modules/memberships/router.py` — `create_membership` (already wired) + `freeze_membership`/`unfreeze_membership`/`renew_membership`/`cancel_membership` (IDM-07 candidates)
- `apps/backend/app/modules/online_payments/router.py` — create/refund (IDM-07 candidates; refund at line ~423/471)
- `apps/backend/app/api/v1/_internal/yookassa/router.py:53-106` — separate webhook dedup (`WEBHOOK_DEDUP_KEY_PREFIX`, `SET NX EX 86400`); IDM-07 adds exclusion comment here, NOT a `verify_idempotency` wire
- `apps/backend/app/main.py` `create_app()` post-processor — the Phase 64 `app.openapi_schema` injection hook to reuse for IDM-04 (D-64-RESPONSES-APPLY / D-64-SEC-APPLY)
- `apps/backend/scripts/export_openapi.py` — byte-stable exporter (drift-gate input for IDM-04)
- `apps/backend/tests/conftest.py:109-140` — `async_client` fixture: ASGITransport + SAVEPOINT Postgres session + real `app.state.redis` (this is the real-PG/real-Redis harness IDM-03/IDM-06 tests build on)

### Prior-phase precedent
- `.planning/phases/64-contract-freeze-openapi-curation/64-CONTEXT.md` §"D-64-RESPONSES-APPLY" / "D-64-SEC-APPLY" / "D-64-BYTE-STABLE" — the post-processor + byte-stable-regen + frozenset-allowlist patterns IDM-04 reuses
- `.planning/phases/63-tech-debt-sweep/63-CONTEXT.md` — atomic-commit-per-requirement discipline (D-66-PLANS mirrors it)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/core/idempotency.py` primitive** — `begin_idempotency` / `store_idempotency_response` / `load_idempotency_response` / `body_sha256` already exist and are correct for the happy path. This phase extends (user-scope key, exception branches, shared orchestrator), it does not rewrite them.
- **Phase 64 `create_app()` OpenAPI post-processor** — the byte-stable `$ref`-injection hook; IDM-04 adds one more injection pass (the `IdempotencyKey` parameter) alongside the existing responses/security injections.
- **`async_client` test fixture** (`tests/conftest.py:109`) — real Redis (`app.state.redis`) + SAVEPOINT-wrapped Postgres over ASGITransport. IDM-03/IDM-06 double-submit + rollback tests reuse it directly; replay tests assert by sending the same `Idempotency-Key` header twice on one client.
- **ЮKassa webhook dedup** (`_internal/yookassa/router.py`) — already 86400s TTL on a separate namespace; the model for "this endpoint is idempotent by a different mechanism" (classification B).

### Established Patterns
- **RBAC-04 dependency ordering** — `auth → require_permission → verify_csrf → verify_idempotency` (documented in `pt_packages/router.py:15` and `memberships/router.py:319`). Adding `get_current_user` inside `verify_idempotency` must not disturb this; FastAPI dedups the shared `get_current_user` node.
- **Two-phase Redis claim + verbatim replay** — `Response(content=base64.b64decode(body_b64), status_code=..., media_type="application/json")`. The shared orchestrator must preserve this exact replay so existing callsite tests pass unchanged.
- **Frozenset-as-lock with AST gate** (`LOCKED_AUDIT_EVENTS`, D-64-SEC-APPLY allowlist) — candidate pattern for the category-A endpoint allowlist if planner chooses explicit declaration over dynamic derivation.
- **Byte-stable regen + drift gate per plan** (D-64-BYTE-STABLE) — IDM-04's plan ends with `export_openapi && codegen && git diff --exit-code`.

### Integration Points
- **`verify_idempotency` signature** — gains `current_user: Depends(get_current_user)`; ripples to all callsites automatically (no per-route change for user-scoping).
- **Each category-A route body** — collapses from the ~40-line inline block to a thin call into the shared orchestrator (IDM-05/06/07 refactor).
- **`create_app()` openapi post-processor** — IDM-04 injection point.
- **`.github/workflows/ci.yml`** — no new gate; existing drift gate + Redocly lint (added in Phase 64) catch IDM-04 spec regressions automatically.

</code_context>

<specifics>
## Specific Ideas

- **Replay semantics doc note (PITFALLS C-05):** the `IdempotencyKey` parameter description in the spec MUST state replay returns the response at time of first success, not current DB state — and point callers to the resource's GET endpoint for live status. This pre-empts the "smart retry" anti-pattern (querying DB inside the replay path) that breaks idempotency.
- **Key-pattern lockstep:** the `{16,128}` length bound lives in BOTH `IDEMPOTENCY_KEY_PATTERN` (validation) and the OpenAPI parameter `schema.pattern` — they must never diverge (a divergence would let a key pass validation but fail spec-conformance or vice versa).
- **No-re-emit-audit assertion (IDM-03):** the replay path must NOT re-run the service orchestrator, so audit rows are written exactly once. Tests assert the audit-event count is unchanged after the second (replayed) submit.

</specifics>

<deferred>
## Deferred Ideas

- **`Idempotency-Key` on the ЮKassa webhook** → never (D-11-IDM-WEBHOOK; webhook has its own `cc:yk:webhook:*` dedup and no `current_user`).
- **Monitoring/alerting on stuck `cc:idem:*` `__in_flight__` keys older than 10 min** (PITFALLS C-02 warning sign) → operational concern, not v1.11 phase scope — note for a future observability phase.
- **`clubcore-auth-runbook.md` idempotency section** → Phase 65 (HND-*) — IDM-04 documents semantics in the spec; the runbook prose is a Phase 65 deliverable that derives from this phase's spec.
- **Client-side retry-key generation guidance (UUIDv4 vs deterministic)** → Phase 65 handoff docs / Postman collection — out of backend scope here.

</deferred>

---

*Phase: 66-idempotency-hardening*
*Context gathered: 2026-05-29*
*Discussion mode: `--auto` (recommended defaults; user can override before plan-phase)*
