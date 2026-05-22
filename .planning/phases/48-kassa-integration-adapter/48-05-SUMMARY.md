---
phase: 48-kassa-integration-adapter
plan: 05
subsystem: integrations/yookassa
tags: [integrations, yookassa, webhook, ip-allowlist, structlog-only, adapter-05]
requirements: [ADAPTER-05]
dependency_graph:
  requires:
    - 48-01 (YookassaWebhookReceivedPayload.idempotency_outcome Literal widened with "rejected_ip")
    - 47-INFRA-37 (YOOKASSA_TRUSTED_IPS frozenset + verify_yookassa_ip skeleton)
  provides:
    - "verify_yookassa_ip body (sandbox bypass + IP allowlist + structlog-only rejection emission)"
  affects:
    - 50-WH-01 (consumer; Depends(verify_yookassa_ip) on /_internal/yookassa/webhook + audit DB row emission)
tech_stack:
  added: [respx>=0.21 (dev-dep deviation — see Deviations)]
  patterns: [structlog.warning before raise pattern, ipaddress.ip_network CIDR membership, FastAPI Depends pre-route auth]
key_files:
  created:
    - apps/backend/tests/integrations/yookassa/test_webhook_verifier.py
  modified:
    - apps/backend/app/integrations/yookassa/webhook_verifier.py
    - apps/backend/pyproject.toml (deviation — re-applied Plan 48-02's respx entry locally)
    - apps/backend/uv.lock (deviation — respx==0.23.1 wheel pin)
decisions:
  - "Emission policy is structlog-only because verify_yookassa_ip runs as a FastAPI Depends() BEFORE the route body — no AsyncSession is in scope at call time. The canonical audit DB row (event=yookassa_webhook_received, idempotency_outcome=rejected_ip) is emitted downstream by Phase 50's webhook route handler, which has the session. This decision is the architectural correction that Plan 48-05 codifies (planner originally suggested audit.emit; revised after audit.py:381 signature audit confirmed AsyncSession is required first positional arg)."
  - "source_ip lives as a structlog kwarg ONLY. It is NOT a field on YookassaWebhookReceivedPayload (Pydantic v2 model_config=ConfigDict(extra='forbid')). The audit DB row carries outcome='rejected_ip' without IP; IP forensics come from the structlog log line."
  - "X-Forwarded-For trust is DEFERRED to Phase 50. Phase 48 reads request.client.host only — the safe default when the deployment topology in front of /_internal/yookassa/webhook is unknown. Two TODO Phase 50 markers in webhook_verifier.py document the deferral."
metrics:
  duration_minutes: ~20
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  tests_added: 7
  commits: 4
completed_date: 2026-05-22
---

# Phase 48 Plan 05: ADAPTER-05 verify_yookassa_ip Body Summary

verify_yookassa_ip body wired with sandbox bypass + IP allowlist + structlog-only rejection emission; downstream Phase 50 webhook route now has a working Depends() to attach.

## One-Liner

Filled the Phase 47 NotImplementedError skeleton of `verify_yookassa_ip` with the D-48-19 4-step body (sandbox bypass → request.client.host extraction → CIDR membership → 403 + structlog warning), and locked SC4 with 7 unit tests covering sandbox/allowed-IPv4/rejected-IPv4/missing-client/malformed-IP/allowed-IPv6/structlog-event-shape.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Fill verify_yookassa_ip body with sandbox bypass + IP allowlist + STRUCTLOG-ONLY emission | `098951e` (impl), `d812f5d` (docstring polish) | apps/backend/app/integrations/yookassa/webhook_verifier.py |
| — | Re-add respx>=0.21 dev dep (Rule 3 — blocking; see Deviations) | `80f9a91` | apps/backend/pyproject.toml, apps/backend/uv.lock |
| 2 | Add 7 tests locking the D-48-19 contract + structlog emission shape | `af4e3ce` | apps/backend/tests/integrations/yookassa/test_webhook_verifier.py |

## Behaviour Locked

The verifier now performs (in order):

1. **Sandbox bypass (D-47-07)** — when `_settings.sandbox` is True, return None immediately without inspecting `request.client`. Locked by `test_sandbox_bypass_returns_none_without_inspecting_request`.
2. **Source IP extraction** — read `request.client.host` ONLY. X-Forwarded-For trust deferred to Phase 50 (TODO Phase 50 marker — T-48-05-01 mitigation).
3. **CIDR membership check** — `ipaddress.ip_address(host)` parsed, then membership tested against each `YOOKASSA_TRUSTED_IPS` entry via `ipaddress.ip_network(cidr)`. Both IPv4 (185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, 77.75.156.11/32, 77.75.156.35/32) and IPv6 (2a02:5180::/32) ranges supported. Locked by `test_trusted_ipv4_allowed` + `test_ipv6_trusted_range_accepted`.
4. **Rejection emission** — `_emit_rejected_ip_log(source_ip=<ip>)` emits exactly ONE structlog WARNING with `event="yookassa_webhook_received"`, `outcome="rejected_ip"`, `source_ip=<extracted-or-sentinel>`, then `raise HTTPException(status_code=403, detail="forbidden_ip")`. Locked by `test_untrusted_ipv4_raises_403_and_emits_structlog` + `test_missing_client_raises_403_and_emits_structlog` + `test_malformed_ip_raises_403_no_uncaught_valueerror` + `test_structlog_event_shape_for_rejected_ip`.

Error sub-paths converted to 403 (never propagated as 500):
- `request.client is None` — `source_ip="(none)"` sentinel.
- `ipaddress.ip_address(host)` raises `ValueError` on malformed input — caught, `source_ip=<raw>` logged, 403 raised with `from None` to drop the chained traceback.
- Per-CIDR `ipaddress.ip_network(cidr)` ValueError — defensively skipped (AST gate already guards the literal shape of YOOKASSA_TRUSTED_IPS).

## Emission Policy (Architectural Correction)

**Phase 48 emits via structlog ONLY. No `app.core.audit.emit` call from this module.**

Rationale: `verify_yookassa_ip` is wired into the Phase 50 webhook route as `Depends(verify_yookassa_ip)`. FastAPI runs dependencies BEFORE the route body, so at the moment `verify_yookassa_ip` executes, no `AsyncSession` exists yet (the route's own `Depends(get_session)` has not been resolved). The canonical `app.core.audit.emit(session, event, *, actor_user_id, resource_type, **payload)` signature (audit.py:381) requires `AsyncSession` as the first positional argument, so the verifier physically cannot call it.

The split is intentional:
- **Phase 48 (this plan):** structlog warning carries the source_ip kwarg (operationally useful for forensics; T-48-05-03 accepted — same exposure as TCP access logs).
- **Phase 50 (downstream):** webhook route handler, which DOES have an AsyncSession, emits the canonical audit DB row with event `yookassa_webhook_received` and `idempotency_outcome="rejected_ip"` using the widened Literal that Plan 48-01 added to `YookassaWebhookReceivedPayload`. The audit DB row carries `outcome` WITHOUT source_ip (Pydantic `extra="forbid"` rejects the field; the IP lives in the structlog line, not the audit chain).

This is why Plan 48-01 widens the Literal even though Phase 48 itself never constructs `YookassaWebhookReceivedPayload`: the consumer of the widened type is Phase 50, not Phase 48.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] B904 from-clause on chained HTTPException**
- **Found during:** Task 1 ruff check
- **Issue:** `raise HTTPException(...)` inside `except ValueError:` block triggered ruff B904 (`raise ... from err` or `raise ... from None`).
- **Fix:** Added `from None` to drop the original exception chain (the ValueError stack frame is internal to ipaddress and not useful in the 403 response).
- **Files modified:** `apps/backend/app/integrations/yookassa/webhook_verifier.py` (line ~103)
- **Commit:** `098951e` (rolled into Task 1 main commit)

**2. [Rule 3 - Blocking] respx dev dependency missing**
- **Found during:** Task 2 pytest run
- **Issue:** `tests/integrations/yookassa/conftest.py` was already tracked in this worktree's base (`013b1a1`) from a prior wave's merge but imports `respx` at module top. The corresponding Plan 48-02 commit that adds `respx>=0.21` to `pyproject.toml` is on a parallel branch not yet reachable from `013b1a1`. Result: pytest collection of ANY test under `tests/integrations/yookassa/` failed with `ModuleNotFoundError: No module named 'respx'`.
- **Fix:** Re-added the IDENTICAL `respx>=0.21` line that Plan 48-02 produces to `pyproject.toml` dependency-groups.dev + ran `uv add --dev` to refresh `uv.lock` (resolved to `respx==0.23.1`).
- **Files modified:** `apps/backend/pyproject.toml`, `apps/backend/uv.lock`
- **Commit:** `80f9a91`
- **Merge risk:** Low. The lines added are byte-identical to Plan 48-02's commit (`2a78783`); when both branches merge to master, git should resolve cleanly (or with a trivial "both added the same line" conflict resolvable by accepting either side).

**3. [Rule 3 - Blocking] SIM117 nested with blocks in tests**
- **Found during:** Task 2 ruff check
- **Issue:** `with structlog.testing.capture_logs(): with pytest.raises(...):` patterns flagged by ruff SIM117.
- **Fix:** ruff `--fix` applied — collapsed to single combined `with` statements (4 sites in test file).
- **Files modified:** `apps/backend/tests/integrations/yookassa/test_webhook_verifier.py`
- **Commit:** `af4e3ce` (rolled into Task 2 main commit)

**4. [Rule 3 - Blocking] mypy func-returns-value on `result = await verify_yookassa_ip(...)`**
- **Found during:** Task 2 mypy strict run
- **Issue:** `verify_yookassa_ip(...) -> None` cannot have its return value assigned (mypy `func-returns-value`).
- **Fix:** Dropped the `result = ` assignment in the 3 happy-path tests; success is implied by absence of HTTPException and absence of structlog warning. Comment retained for reader clarity.
- **Files modified:** `apps/backend/tests/integrations/yookassa/test_webhook_verifier.py`
- **Commit:** `af4e3ce` (rolled into Task 2 main commit)

**5. [Rule 3 - Doc polish] Acceptance-criterion grep guards on docstring text**
- **Found during:** Acceptance check after Task 1
- **Issue:** Acceptance criteria `! grep -q 'NotImplementedError'` and `! grep -q 'audit\.emit'` failed because the module docstring/comment described what the Phase 47 skeleton DID ("raised NotImplementedError") and what Phase 50 WILL do ("`audit.emit(session, ...)`"). No actual call sites — pure documentation references.
- **Fix:** Rephrased docstring to "stub-only; body deferred to Phase 48" and "canonical app.core.audit writer" (no `audit.emit` substring). Behaviour unchanged; literal grep guards now satisfied.
- **Files modified:** `apps/backend/app/integrations/yookassa/webhook_verifier.py`
- **Commit:** `d812f5d`

### Auth Gates

None — fully autonomous execution.

## Threat Model Compliance

| Threat ID | Mitigation Locked By |
|-----------|----------------------|
| T-48-05-01 (XFF spoofing) | TODO Phase 50 marker in webhook_verifier.py; X-Forwarded-For NOT read. |
| T-48-05-02 (no HMAC) | Accepted per PITFALLS.md Pitfall 1 — IP allowlist is the canonical Phase 48 mitigation. |
| T-48-05-03 (source_ip in structlog) | Accepted — source_ip is a structlog kwarg, intentionally not in the audit DB row. |
| T-48-05-04 (uncaught ValueError DOS) | Locked by `test_malformed_ip_raises_403_no_uncaught_valueerror`. |
| T-48-05-05 (unbounded retry) | Accepted — reverse-proxy concern, deferred. |
| T-48-05-06 (sandbox in prod) | Phase 47 settings tests cover; not re-tested here. |
| T-48-05-07 (rejection without log) | Locked by 4 rejection-path tests each asserting exactly ONE captured `yookassa_webhook_received` event. |

## Verification Evidence

- `cd apps/backend && uv run ruff check app/integrations/yookassa/webhook_verifier.py tests/integrations/yookassa/test_webhook_verifier.py` → exit 0.
- `cd apps/backend && uv run mypy --strict app/integrations/yookassa/webhook_verifier.py tests/integrations/yookassa/test_webhook_verifier.py` (with required YOOKASSA_* env stubs) → exit 0.
- `cd apps/backend && uv run pytest tests/integrations/yookassa/test_webhook_verifier.py tests/unit/test_locked_yookassa_constants_ast.py -q` → 14 passed (7 new + 7 AST gate).
- `! grep -q 'NotImplementedError' apps/backend/app/integrations/yookassa/webhook_verifier.py` → exit 0.
- `! grep -q 'audit\.emit\|audit_emit' apps/backend/app/integrations/yookassa/webhook_verifier.py` → exit 0.
- `uv run python -c "from app.integrations.yookassa.webhook_verifier import verify_yookassa_ip; import inspect; assert inspect.iscoroutinefunction(verify_yookassa_ip)"` → exit 0.
- TODO Phase 50 marker count: 2 (XFF + audit DB row handoff).

## Downstream Consumer

**Phase 50 WH-01** will:

1. Wire `Depends(verify_yookassa_ip)` on the `/_internal/yookassa/webhook` POST handler (per D-48-21). FastAPI's dependency ordering guarantees the IP check runs BEFORE the route body parses the webhook payload.
2. Inside the route body (which now HAS an `AsyncSession` in scope), emit the canonical audit DB row via `app.core.audit.emit(session, "yookassa_webhook_received", resource_type="yookassa_webhook", actor_user_id=None, audit_correlation_id=<uuid>, event_type=<юkassa event>, object_id=<юkassa payment/refund id>, idempotency_outcome="new" | "duplicate_blocked")`.
3. On a `verify_yookassa_ip`-raised 403 the route body never runs — FastAPI returns the 403 directly. The audit DB row for the rejection (`idempotency_outcome="rejected_ip"`) is emitted by a separate code path inside the Phase 50 route handler that catches the HTTPException, re-acquires the session, and writes the audit row before re-raising. The widened Literal in `YookassaWebhookReceivedPayload.idempotency_outcome` (Plan 48-01) supports that path.

Operator forensics on rejected requests come from BOTH:
- The Phase 48 structlog warning (carries `source_ip`).
- The Phase 50 audit DB row (carries `outcome="rejected_ip"` + the chain root `audit_correlation_id`).

## Self-Check

- [x] `apps/backend/app/integrations/yookassa/webhook_verifier.py` — modified (verified via `git log -1 --stat`).
- [x] `apps/backend/tests/integrations/yookassa/test_webhook_verifier.py` — created (verified existing on disk + tracked in git).
- [x] `apps/backend/pyproject.toml` + `apps/backend/uv.lock` — modified (deviation Rule 3).
- [x] Commits: `098951e`, `d812f5d`, `80f9a91`, `af4e3ce` — all present in `git log --oneline -5`.
- [x] 7 new tests pass; 7 AST gate tests still pass (14/14 green).
- [x] ruff + mypy --strict clean on both modified module + new test file.
- [x] No `audit.emit` / `audit_emit` substring in webhook_verifier.py.
- [x] No `source_ip` field added to `YookassaWebhookReceivedPayload` (Pydantic `extra="forbid"` preserved).
- [x] No STATE.md / ROADMAP.md edits (parallel-executor contract).

## Self-Check: PASSED
