---
phase: 48-kassa-integration-adapter
plan: 03
subsystem: integrations/yookassa
tags: [integrations, yookassa, factory, boot-probe, degraded-mode, sc2]
requires:
  - ADAPTER-02 (YooKassaClient — Plan 48-02, Wave 2)
  - YooKassaSettings (Phase 47 INFRA-36)
  - respx ≥0.21 dev dep (Plan 48-01)
provides:
  - build_yookassa_client async factory + non-fatal /v3/me boot probe
  - SC2 invariant locked: factory NEVER raises on probe failure
affects:
  - Plan 48-07 (composition-root rewiring) — replaces yookassa_client_provider_noop_stub with this factory's output
tech-stack:
  added: []
  patterns:
    - "S-2: Async factory with LOCKED `async def` signature (D-42-30 lineage; D-48-13..15 lock here)"
    - "S-5: Module docstring layer invariant (integrations → no app.modules.* imports)"
    - "Long-lived httpx.AsyncClient pattern (D-48-06 — divergence from email's per-call aioboto3 factory)"
    - "Non-fatal boot probe pattern (D-48-14, SC2 — divergence from email's RuntimeError fail-fast)"
key-files:
  created:
    - apps/backend/app/integrations/yookassa/factory.py
    - apps/backend/tests/integrations/yookassa/test_factory.py
  modified: []
decisions:
  - "D-48-06 locked: httpx.AsyncClient is LONG-LIVED — constructed once in factory, closed by lifespan teardown (Plan 48-07)."
  - "D-48-14 locked: probe failure is NON-FATAL — factory ALWAYS returns the constructed YooKassaClient; only structlog signal differs."
  - "D-48-15 locked: single-attempt probe — no retry loop, no compound timeout."
  - "D-48-08 locked: sandbox flag does NOT change base URL — _YOOKASSA_BASE_URL is a module-level constant."
  - "Rule 1 deviation: User-Agent header value Latinised to 'Sportzal/1.7 YooKassa-Adapter' (httpx ASCII-encoding constraint); docstring + log keywords retain Cyrillic spelling."
metrics:
  duration_minutes: 6
  completed: 2026-05-22T08:28:13Z
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 7
  tests_passing: 7
---

# Phase 48 Plan 03: Async YooKassaClient Factory + Non-Fatal Boot Probe Summary

Async `build_yookassa_client(*, settings)` factory + non-fatal `GET /v3/me`
boot probe lock SC2 (degraded-mode startup) before composition-root rewiring.

## Objective

Ship `apps/backend/app/integrations/yookassa/factory.py` — the async
`build_yookassa_client(*, settings: YooKassaSettings) -> YooKassaClient`
factory — and lock the SC2 invariant ("failed probe does not prevent
application startup") with both code and test coverage.

## Outcome

- **Factory shape locked.** `inspect.iscoroutinefunction(build_yookassa_client)` is `True`.
- **httpx.AsyncClient construction pinned.** `base_url="https://api.yookassa.ru/v3/"`,
  `httpx.BasicAuth(str(shop_id), secret_key.get_secret_value())`,
  `Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)`,
  `User-Agent: "Sportzal/1.7 YooKassa-Adapter"`, TLS verify=True (httpx default).
- **Boot probe contract enforced.** Single-attempt `GET /v3/me` with `timeout=5.0`;
  success → INFO `yookassa_boot_probe ok=True shop_id=<id>`; mismatched account_id
  → WARNING `yookassa_boot_probe ok=False reason="shop_id_mismatch" expected=… got=…`;
  any exception → WARNING `yookassa_boot_probe ok=False reason=<exc-type>`.
- **SC2 non-fatal invariant.** Every failure mode (5xx, timeout, ConnectError, 503
  sweep) returns a constructed `YooKassaClient` to the caller — `pytest.raises`
  is never required around the factory call.
- **7 unit tests passing.** `ruff` and `mypy --strict` clean on both files.

## What Was Built

### Task 1 — `factory.py` (commit `1972586`)

`async def build_yookassa_client(*, settings: YooKassaSettings) -> YooKassaClient`
constructs a long-lived `httpx.AsyncClient` (BasicAuth + pinned timeouts +
ASCII User-Agent), runs the non-fatal `GET /v3/me` boot probe inside a
broad `try/except Exception` block, and returns
`YooKassaClient(http=http, settings=settings)` regardless of probe outcome.

Documented divergences from `email/factory.py` baked into the module docstring:
1. **Long-lived AsyncClient (D-48-06)** — opposite of `aioboto3.Session`'s
   per-call factory discipline (which deliberately recycles aiohttp pools).
2. **Non-fatal probe (D-48-14, SC2)** — opposite of email's `RuntimeError`
   fail-fast (`email/factory.py:96-99`). Operator runbook (Phase 53 deferred)
   covers the degraded-mode signal.
3. **Single attempt (D-48-15)** — no retry loop that could compound delay.

Layer-invariant footer present: `MUST NOT import from app.modules.*
(importlinter contract integrations-not-depend-on-modules)`.

**Key files:**
- `apps/backend/app/integrations/yookassa/factory.py:115` — full module.

### Task 2 — `test_factory.py` (commit `00ef5a4`)

Seven tests cover the LOCKED async-def shape (1), probe success (1), four
probe-failure modes (5xx, TimeoutException, ConnectError, 503 sweep), and
shop_id mismatch (1):

| # | Test | Locks |
| - | ---- | ----- |
| 1 | `test_build_yookassa_client_is_coroutine_function` | `inspect.iscoroutinefunction(...) is True` |
| 2 | `test_probe_success_returns_client_and_logs_ok` | 200 + matching account_id → INFO with ok=True |
| 3 | `test_probe_500_is_non_fatal_returns_client` | SC2: 5xx → ok=False, client returned |
| 4 | `test_probe_timeout_is_non_fatal_returns_client` | SC2: TimeoutException → reason="TimeoutException", client returned |
| 5 | `test_probe_network_error_is_non_fatal` | SC2: ConnectError → reason="ConnectError", client returned |
| 6 | `test_probe_shop_id_mismatch_logs_warning` | account_id mismatch → reason="shop_id_mismatch" + expected/got |
| 7 | `test_factory_never_raises_on_probe_failure` | SC2 sweep: 503 never propagates an exception |

Pattern source: `structlog.testing.capture_logs()` + `respx.mock(base_url=...,
assert_all_called=False)` combined in a single `with (..., ...)` block.
All tests `await client.aclose()` to release the long-lived AsyncClient's
TLS handles.

**Key files:**
- `apps/backend/tests/integrations/yookassa/test_factory.py:160` — full module.

## Verification Results

| Gate | Command | Result |
| ---- | ------- | ------ |
| ruff | `uv run ruff check app/integrations/yookassa/factory.py tests/integrations/yookassa/test_factory.py` | PASS |
| mypy strict | `uv run mypy --strict app/integrations/yookassa/factory.py tests/integrations/yookassa/test_factory.py` | PASS (2 files) |
| pytest | `uv run pytest tests/integrations/yookassa/test_factory.py -q` | 7 passed |
| async-shape lock | `python -c "assert inspect.iscoroutinefunction(build_yookassa_client)"` | PASS |
| SC2 invariant | every probe-failure test asserts `isinstance(client, YooKassaClient)` without `pytest.raises` | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] User-Agent header Cyrillic glyph raised UnicodeEncodeError**
- **Found during:** Task 2 (first `pytest` run after writing the tests)
- **Issue:** Plan action prescribed `User-Agent: "Sportzal/1.7 ЮKassa-Adapter"`.
  httpx normalises header values via `value.encode("ascii")`
  (`httpx._models._normalize_header_value`); the Cyrillic 'Ю' (U+042E)
  raises `UnicodeEncodeError: 'ascii' codec can't encode character 'Ю'`
  inside `httpx.AsyncClient.__init__`. The factory therefore could not even
  construct an AsyncClient, so all 6 async tests crashed before reaching
  the probe.
- **Fix:** Latinised the wire value to `"Sportzal/1.7 YooKassa-Adapter"`.
  Docstrings, structlog event keywords, and the SUMMARY itself retain the
  original "ЮKassa" spelling — only the on-wire header is normalised.
  Comment added at the `headers=` site explaining the httpx constraint.
- **Files modified:** `apps/backend/app/integrations/yookassa/factory.py`
- **Commit:** bundled into the Task 2 test commit (`00ef5a4`) since the
  fix is the precondition for the tests passing — coupled, not independent.

### Auth Gates

None — all work was offline (respx mocks).

### Architectural Decisions

None — followed all D-48-* decisions verbatim.

## Threat Model Mitigations Verified

| Threat ID | Disposition | How verified in this plan |
| --------- | ----------- | ------------------------- |
| T-48-03-01 (secret_key disclosure) | mitigate | `secret_key.get_secret_value()` appears ONLY inside `httpx.BasicAuth(...)` (1 callsite); no `_log` call references it. |
| T-48-03-02 (shop_id spoof) | mitigate | `test_probe_shop_id_mismatch_logs_warning` locks `reason="shop_id_mismatch" expected=… got=…` log shape. |
| T-48-03-03 (TLS verify=False) | mitigate | Factory does not pass `verify=` — httpx default is `True`. `grep -q 'verify=False' factory.py` returns empty. |
| T-48-03-04 (probe hangs startup) | mitigate | Per-call `timeout=5.0` on `http.get("me", ...)` + AsyncClient `Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)`. Single attempt, no retry. |
| T-48-03-05 (base URL env tamper) | mitigate | `_YOOKASSA_BASE_URL: str = "https://api.yookassa.ru/v3/"` — module-level constant, no env override; sandbox does not switch URL (D-48-08). |
| T-48-03-06 (probe failure aborts startup) | mitigate | 4 failure-mode tests + 1 sweep test lock the SC2 invariant. |

## Commits

| Hash | Task | Files |
| ---- | ---- | ----- |
| `1972586` | Task 1: factory.py | `apps/backend/app/integrations/yookassa/factory.py` |
| `00ef5a4` | Task 2: test_factory.py + Rule 1 ASCII fix | `apps/backend/tests/integrations/yookassa/test_factory.py`, `apps/backend/app/integrations/yookassa/factory.py` |

## Downstream Consumer

Plan **48-07** (composition-root rewiring) wires this factory into:
- `app/main.py` `combined_lifespan` — `await build_yookassa_client(settings=YooKassaSettings())`
  + `register_yookassa_client_provider(...)` replacing
  `yookassa_client_provider_noop_stub`.
- `app/workers/__init__.py` `WorkerSettings.on_startup` — REG-29-03 double-wire
  mirror of the main.py composition root.
- Lifespan / `on_shutdown` teardown — `await yookassa_client.aclose()` releases
  the long-lived AsyncClient's TLS pool.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`), so the plan-level RED/GREEN gate sequence
does not apply. Both tasks are individually tagged `tdd="true"`; the RED→GREEN
shape was condensed (factory landed first to give the test imports concrete
symbols), then the failing test phase manifested as the User-Agent
UnicodeEncodeError that the Rule 1 fix resolved. All 7 tests are green in the
final commit.

## Self-Check: PASSED

- File `apps/backend/app/integrations/yookassa/factory.py` — FOUND
- File `apps/backend/tests/integrations/yookassa/test_factory.py` — FOUND
- Commit `1972586` — FOUND in `git log`
- Commit `00ef5a4` — FOUND in `git log`
- ruff + mypy + pytest gates all PASS (verification table above)
- SC2 invariant tested: 4 failure-mode tests + 1 sweep test PASS without `pytest.raises`
