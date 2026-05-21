---
phase: 47-bedrock
plan: 02
subsystem: integrations/yookassa
tags: [INFRA-36, settings, secrets, BaseSettings, SecretStr, env-example]
requirements_completed: [INFRA-36]
dependency_graph:
  requires: []
  provides:
    - "app.integrations.yookassa package directory (consumed by 47-03, 47-04, 47-05)"
    - "YooKassaSettings type (consumed by Phase 48 client + factory)"
  affects:
    - apps/backend/.env.example
tech_stack:
  added: []
  patterns:
    - "Standalone BaseSettings per integration (mirrors EmailProviderSettings nesting deviation per D-47-08)"
    - "SecretStr redaction lineage for credential fields"
    - "Placeholder-only .env.example block with banner naming Phase + decisions"
key_files:
  created:
    - apps/backend/app/integrations/yookassa/__init__.py
    - apps/backend/app/integrations/yookassa/settings.py
    - apps/backend/tests/unit/integrations/yookassa/__init__.py
    - apps/backend/tests/unit/integrations/yookassa/test_settings.py
  modified:
    - apps/backend/.env.example
decisions:
  - "Standalone YooKassaSettings (D-47-08): not nested under app.core.config.Settings; encapsulates credential ownership next to integration code"
  - "Sandbox flag is a plain bool (D-47-07): no @model_validator here; bypass logic lives in Phase 48 webhook_verifier + client"
  - "Placeholder-only .env.example block (D-47-09): obvious-fake values, no real-credential prefixes (test_/live_/sk_)"
metrics:
  duration_minutes: ~6
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  completed_date: 2026-05-21
---

# Phase 47 Plan 02: YooKassaSettings (INFRA-36) Summary

`YooKassaSettings` ships as a standalone `BaseSettings` next to the `app.integrations.yookassa` package, with 6 INFRA-36 fields (`shop_id`, `secret_key`, `return_url`, `tax_system_code`, `default_vat_code`, `sandbox`) and an `env_prefix="YOOKASSA_"` chokepoint; `.env.example` gains a 6-entry placeholder block per D-47-09.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for YooKassaSettings | `8da5773` | `tests/unit/integrations/yookassa/__init__.py`, `tests/unit/integrations/yookassa/test_settings.py` |
| 1 (GREEN) | Implement YooKassaSettings + package marker | `4748b1f` | `app/integrations/yookassa/__init__.py`, `app/integrations/yookassa/settings.py` |
| 2 | YOOKASSA_* placeholder block in .env.example | `bd0ebcd` | `apps/backend/.env.example` |

## What Shipped

### `app/integrations/yookassa/__init__.py`
4-line module docstring announcing staged delivery (Phase 47 skeleton; Phase 48 wires the real adapter). No code, no imports — pure package marker so wave-2 plans (47-03 webhook_verifier, 47-04 dependency wiring) can target the namespace.

### `app/integrations/yookassa/settings.py`
`YooKassaSettings(BaseSettings)` with `model_config = SettingsConfigDict(env_prefix="YOOKASSA_", env_file=".env", env_file_encoding="utf-8", extra="ignore")`. The 6 fields (declared in this exact order):

1. `shop_id: int`
2. `secret_key: SecretStr`
3. `return_url: HttpUrl`
4. `tax_system_code: int`
5. `default_vat_code: int`
6. `sandbox: bool = False`

Module docstring explicitly names D-47-07/08/09 and INFRA-36 and explains the deviation from `EmailProviderSettings` (which is nested under `app.core.config.Settings`). No `@model_validator` — the sandbox-vs-credential guard lives in Phase 48 (`webhook_verifier.py` + `client.py`).

### `.env.example` — 6-entry placeholder block

```
YOOKASSA_SHOP_ID=placeholder-shop-id-not-real
YOOKASSA_SECRET_KEY=placeholder-secret-key-not-real
YOOKASSA_RETURN_URL=https://example.com/yookassa/return
YOOKASSA_TAX_SYSTEM_CODE=2
YOOKASSA_DEFAULT_VAT_CODE=1
YOOKASSA_SANDBOX=true
```

Banner explicitly names Phase 47, D-47-09, and the sandbox-bypass semantics (D-47-07). All values are obvious placeholders — `shop_id` and `secret_key` carry the literal `placeholder-*-not-real` suffix so any operator who misses the documentation still sees the intent.

## Verification Results

| Check | Outcome |
|-------|---------|
| `uv run pytest tests/unit/integrations/yookassa/test_settings.py -x` | **5 passed** (round-trip, SecretStr redaction, sandbox default, missing shop_id, malformed URL) |
| `uv run python -c "from app.integrations.yookassa.settings import YooKassaSettings"` | OK (import-resolvable) |
| `uv run ruff check app/integrations/yookassa` | All checks passed |
| `uv run mypy --strict app/integrations/yookassa` | Success: no issues found in 2 source files |
| `grep -cE '^YOOKASSA_(SHOP_ID|SECRET_KEY|RETURN_URL|TAX_SYSTEM_CODE|DEFAULT_VAT_CODE|SANDBOX)=' .env.example` | **6** |
| `grep -E "^YOOKASSA_SECRET_KEY=(live_|test_|sk_)" .env.example` | no matches (T-47-02-02 mitigation) |

## SecretStr Redaction Confirmation

The dedicated test `test_secret_key_repr_redaction` constructs `YooKassaSettings` from env, then asserts:

- `"test-secret-not-real" not in repr(s.secret_key)` — Pydantic SecretStr's `__repr__` returns `SecretStr('**********')`
- `"test-secret-not-real" not in repr(s)` — the parent settings `__repr__` inherits the redaction

This pins the structlog `redact_secrets` formatter lineage (already configured for `EmailProviderSettings.smtp_password`) — operators who accidentally log the settings object will not leak the ЮKassa credential. Mitigates T-47-02-01.

## Decisions Made / Key Rationale

- **D-47-08 deviation rationale (standalone BaseSettings):** `EmailProviderSettings` is a nested `BaseModel` under `app.core.config.Settings` (re-instantiated via `Settings.email = EmailProviderSettings()`). For ЮKassa, deliberate deviation: standalone `BaseSettings` with its own `env_prefix` so (a) credential ownership lives next to the integration code, (b) adapter unit tests in Phase 48 can construct `YooKassaSettings(...)` directly without dragging the full root `Settings` graph, and (c) `app.core.config.Settings` does not accumulate per-integration field churn.
- **D-47-07 sandbox flag semantics:** Phase 47 ships only the bare bool field; downstream consumers (Phase 47-03 `verify_yookassa_ip` skeleton, Phase 48 `YooKassaClient` + webhook verifier real impl) read it. No `@model_validator` here — keeps Phase 47 a true skeleton.
- **D-47-09 placeholder-only:** `YOOKASSA_SHOP_ID` and `YOOKASSA_SECRET_KEY` are not type-valid against the schema (`shop_id: int` rejects the string `"placeholder-shop-id-not-real"`); that is intentional. The placeholder doubles as a documentation cue ("REPLACE ME before non-sandbox boot") AND as a fail-fast tripwire: non-sandbox boot with stock `.env.example` will surface a `ValidationError` at startup rather than calling the real ЮKassa API with garbage shop_id.

## Deviations from Plan

None — plan executed exactly as written. The TDD cycle (Task 1 RED → GREEN) was honored with separate `test(...)` and `feat(...)` commits per Phase-level TDD gate enforcement.

## Self-Check: PASSED

- [x] `apps/backend/app/integrations/yookassa/__init__.py` — FOUND
- [x] `apps/backend/app/integrations/yookassa/settings.py` — FOUND
- [x] `apps/backend/tests/unit/integrations/yookassa/__init__.py` — FOUND
- [x] `apps/backend/tests/unit/integrations/yookassa/test_settings.py` — FOUND
- [x] `.env.example` — modified, 6 YOOKASSA_* entries present
- [x] Commit `8da5773` (test RED) — FOUND
- [x] Commit `4748b1f` (feat GREEN) — FOUND
- [x] Commit `bd0ebcd` (chore .env.example) — FOUND
- [x] `uv run pytest tests/unit/integrations/yookassa/test_settings.py -x` — 5 passed
- [x] `uv run ruff check app/integrations/yookassa` — All checks passed
- [x] `uv run mypy --strict app/integrations/yookassa` — Success
- [x] Negative-grep `YOOKASSA_SECRET_KEY=(live_|test_|sk_)` — no matches

## TDD Gate Compliance

- RED gate: `test(47-02): add failing tests for YooKassaSettings` — `8da5773`
- GREEN gate: `feat(47-02): implement YooKassaSettings + package marker` — `4748b1f`
- REFACTOR gate: not needed (GREEN code is minimal and clean — ruff + mypy --strict green; no cleanup pass required).
