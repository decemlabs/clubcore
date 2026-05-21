---
phase: 47-bedrock
plan: 03
subsystem: integrations/yookassa
tags: [INFRA-37, ast-gate, webhook-security, frozenset-lock]
dependency_graph:
  requires:
    - 47-02 (app/integrations/yookassa package + YooKassaSettings)
  provides:
    - "YOOKASSA_TRUSTED_IPS Final[frozenset[str]] (locked, AST-gated)"
    - "verify_yookassa_ip Depends()-callable skeleton (Phase 48 ADAPTER-05 fills body)"
    - "test_locked_yookassa_constants_ast.py — AST walker enforcing the two invariants"
  affects:
    - "Phase 48 ADAPTER-05 (real IP-parse body)"
    - "Phase 50 WH-01 (first Depends(verify_yookassa_ip) callsite)"
tech_stack:
  added: []
  patterns: [ast-walker-gate, final-frozenset-lock, depends-literal-name-gate]
key_files:
  created:
    - apps/backend/app/integrations/yookassa/webhook_verifier.py
    - apps/backend/tests/unit/test_locked_yookassa_constants_ast.py
    - apps/backend/tests/unit/fixtures/yookassa_ast_violations/__init__.py
    - apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_verifier_arg.py
  modified: []
key_decisions:
  - "Phase 47 ships skeleton only — verify_yookassa_ip body raises NotImplementedError; real IP parsing + sandbox bypass land in Phase 48 ADAPTER-05 (D-47-07)."
  - "AST walker scopes to YOOKASSA primitives only; audit-event literal gating stays in the existing test_audit_taxonomy.py per CONTEXT.md upstream-prompt correction."
  - "Walker flags Depends(<Name>) when name matches reserved prefixes (verify_yookassa_* or verify_some_alias) but is not the canonical verify_yookassa_ip. Synthetic fixture proves the walker fires."
  - "Walker also rejects dynamic frozenset/set/list/tuple(YOOKASSA_TRUSTED_IPS) constructions and module-scope rebinds outside the canonical declaration file — protects the Final[frozenset[str]] lock from runtime indirection."
metrics:
  completed: 2026-05-21
---

# Phase 47 Plan 03: YOOKASSA Webhook Primitives + AST Gate Summary

Locks the two ЮKassa webhook-security primitives (the 6-CIDR IP allowlist and the `Depends()`-callable name) at the import + AST level so the Phase 50 webhook handler cannot drift away from the published source-of-truth or silently bypass the gate via an aliased dependency.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Create webhook_verifier.py with YOOKASSA_TRUSTED_IPS + verify_yookassa_ip skeleton | `28798d9` | `apps/backend/app/integrations/yookassa/webhook_verifier.py` |
| 2 | Create AST gate test + synthetic-violation fixture | `41a0022` | `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py`, `apps/backend/tests/unit/fixtures/yookassa_ast_violations/__init__.py`, `apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_verifier_arg.py` |

## Artifacts

### `apps/backend/app/integrations/yookassa/webhook_verifier.py`

Exports `YOOKASSA_TRUSTED_IPS: Final[frozenset[str]]` with the 6 ЮKassa-published webhook CIDRs (sourced verbatim from https://yookassa.ru/developers/using-api/webhooks — verified 2026-05-21):

```
185.71.76.0/27
185.71.77.0/27
77.75.153.0/25
77.75.156.11/32
77.75.156.35/32
2a02:5180::/32
```

Skeleton signature:

```python
async def verify_yookassa_ip(request: Request) -> None: ...
```

Body raises:

```
NotImplementedError(
    "verify_yookassa_ip impl lands in Phase 48 ADAPTER-05 — "
    "Phase 47 ships only the import-resolvable name + the "
    "AST-gated YOOKASSA_TRUSTED_IPS frozenset."
)
```

The module docstring documents:
- The source URL for the 6 CIDRs (re-audit anchor).
- The Phase 48 implementation contract (`if settings.sandbox: return` per D-47-07 + `ipaddress` membership check + `HTTPException(403)` + audit emission on miss).
- The AST-gate contract (literal-name `Depends(verify_yookassa_ip)` only; no dynamic `YOOKASSA_TRUSTED_IPS` construction).
- The layer invariant (no `app.modules.*` imports from `integrations/`).

### `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py`

Three tests, all passing:

| Test | What it asserts |
| ---- | --------------- |
| `test_real_callsites_pass` | Walker scans `apps/backend/app/**/*.py`, collects zero violations against the production tree (Phase 47 has no `Depends(verify_yookassa_ip)` callsites yet; Phase 50 WH-01 ships the first). |
| `test_non_literal_verifier_arg_is_rejected` | Walker run against the synthetic fixture flags at least one violation that mentions both `verify_some_alias` and `verify_yookassa_ip` — proves the gate fires on aliased `Depends(...)` callsites. |
| `test_frozenset_has_six_entries` | Smoke check: `len(YOOKASSA_TRUSTED_IPS) == 6` and every entry is a non-empty `str`. |

Walker invariants:
1. **Literal-name gate.** `Depends(<Name>)` where `<Name>` matches a reserved prefix (`verify_yookassa_*` or `verify_some_alias`) but is not exactly `verify_yookassa_ip` is flagged.
2. **No dynamic construction.** Any `frozenset(YOOKASSA_TRUSTED_IPS)` / `set(YOOKASSA_TRUSTED_IPS)` / `list(YOOKASSA_TRUSTED_IPS)` / `tuple(YOOKASSA_TRUSTED_IPS)` call is flagged; module-scope `YOOKASSA_TRUSTED_IPS = ...` rebinds outside `webhook_verifier.py` are flagged.

### `apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_verifier_arg.py`

Synthetic violation: defines `verify_some_alias` and decorates a FastAPI route with `dependencies=[Depends(verify_some_alias)]`. The walker MUST reject it (proven by `test_non_literal_verifier_arg_is_rejected`).

## Verification Results

- `uv run pytest apps/backend/tests/unit/test_locked_yookassa_constants_ast.py -x` → **3 passed**.
- `uv run python -c "from app.integrations.yookassa.webhook_verifier import YOOKASSA_TRUSTED_IPS, verify_yookassa_ip; assert len(YOOKASSA_TRUSTED_IPS) == 6"` → exit 0.
- `uv run ruff check apps/backend/app/integrations/yookassa/webhook_verifier.py apps/backend/tests/unit/test_locked_yookassa_constants_ast.py apps/backend/tests/unit/fixtures/yookassa_ast_violations` → **All checks passed!**
- `uv run mypy --strict apps/backend/app/integrations/yookassa/webhook_verifier.py apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` → **Success: no issues found in 2 source files.**
- `grep -q "yookassa.ru/developers/using-api/webhooks" apps/backend/app/integrations/yookassa/webhook_verifier.py` → matched (source-URL citation present).
- `NotImplementedError` raised by `verify_yookassa_ip(stub_request)` carries the documented message and references Phase 48 ADAPTER-05.

## Scope Notes

- **Audit-event literal gating is NOT duplicated here.** Per CONTEXT.md upstream-prompt correction, the existing `apps/backend/tests/unit/test_audit_taxonomy.py` already covers `audit.emit(...)` event-name literals; the v1.7 expansion of `LOCKED_AUDIT_EVENTS` (now 80 entries, landed in 47-01) is enforced there. This AST gate intentionally scopes to YOOKASSA primitives only.
- **No real implementation of IP parsing.** Phase 47 deliberately ships only the import-resolvable name. Phase 48 ADAPTER-05 fills `if settings.sandbox: return` + `ipaddress.ip_address`/`ipaddress.ip_network` membership + `HTTPException(403)` + audit emission.

## Deviations from Plan

None — plan executed exactly as written. The walker's "reserved verifier prefix" rule (the recommended Phase 47 heuristic from the plan's `<action>`) is implemented verbatim with `_RESERVED_VERIFIER_PREFIXES = {"verify_yookassa_", "verify_some_alias"}`.

## Self-Check: PASSED

Files exist:
- `apps/backend/app/integrations/yookassa/webhook_verifier.py` — FOUND.
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` — FOUND.
- `apps/backend/tests/unit/fixtures/yookassa_ast_violations/__init__.py` — FOUND.
- `apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_verifier_arg.py` — FOUND.

Commits exist:
- `28798d9` feat(47-03): add YOOKASSA_TRUSTED_IPS frozenset + verify_yookassa_ip skeleton — FOUND in `git log`.
- `41a0022` test(47-03): add AST gate for YOOKASSA primitives + synthetic violation fixture — FOUND in `git log`.
