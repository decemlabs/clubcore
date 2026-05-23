# Phase 51 — Deferred Items

Pre-existing tech-debt items discovered during plan execution that are out
of scope for the current task.

## From 51-03 (YooKassaClient.create_receipt) execution

### Pre-existing ruff errors in tests/integrations/yookassa/conftest.py

Found while running the plan 51-03 acceptance criterion
``uv run ruff check tests/integrations/yookassa/``. The two errors below
exist on the wave-base commit (a4392fcd) and are unrelated to the
``create_receipt`` work:

1. **S110** — `try`/`except`/`pass` in ``_reset_structlog_for_capture``
   fixture (line 57). Best-effort isolation that intentionally swallows
   exceptions; the existing inline comment explains the rationale.

2. **RUF100** — unused ``# noqa: BLE001`` directive on the same line; the
   BLE001 rule is no longer enabled in the project ruff config but the
   directive remained.

Both are documentation/style issues only. They do not affect runtime
behavior of any test. Sweep target: DEFER-46-04 (the ruff tree-wide
cleanup queued for v1.9).
