---
phase: 42-email-transport-layer-email-otp-fallback
plan: 02
subsystem: core/config
tags:
  - email
  - config
  - secrets
dependency-graph:
  requires: []
  provides:
    - "Settings.email: EmailProviderSettings nested block (D-42-28) consumed by Wave 2 plans 42-07 (factory) and 42-08 (dispatcher), Wave 3 plan 42-10 (webhook handler)"
  affects:
    - apps/backend/app/core/config.py
tech-stack:
  added:
    - "Pydantic v2 SecretStr (already imported)"
    - "typing.Self (new import — for @model_validator return type)"
    - "pydantic.BaseModel (new import — nested non-Settings block)"
  patterns:
    - "Nested BaseModel (NOT BaseSettings) for grouped provider settings; mounted as a field on the outer Settings(BaseSettings) instance. First such nesting in this file (Telegram is flat fields). Env-var loading of nested fields requires `env_nested_delimiter` on Settings — NOT introduced here (see Discoveries)."
    - "Sandbox-safe defaults + @model_validator(mode='after') fail-fast on production boots with missing creds — mirrors v1.1 Telegram-block discipline."
key-files:
  created: []
  modified:
    - apps/backend/app/core/config.py
decisions:
  - "Used BaseModel (per plan); kept the validator body verbatim from D-42-28"
  - "Mounted email field next to the existing Telegram block (placement convention)"
  - "Did NOT introduce env_nested_delimiter on Settings — existing file has none; plan said do not introduce a different convention. Env-var loading of EmailProviderSettings fields lands in a later plan if needed."
metrics:
  duration: "~3 min"
  completed: "2026-05-19"
---

# Phase 42 Plan 02: EmailProviderSettings — config block + boot-time validator

One-liner: Added `EmailProviderSettings` Pydantic v2 nested `BaseModel` on `Settings.email` with sandbox-safe defaults and a fail-fast `model_validator(mode='after')` that raises `ValueError` when a non-sandbox provider is configured without credentials, domain, or webhook secret — closing requirement **EMAIL-02** and unblocking every downstream Phase 42 plan.

## What Was Built

- **`EmailProviderSettings(BaseModel)`** at the top of `apps/backend/app/core/config.py` (above `class Settings`).
  - Fields: `provider: Literal['yandex_postbox','sandbox']='sandbox'`, `aws_access_key_id: SecretStr | None = None`, `aws_secret_access_key: SecretStr | None = None`, `endpoint_url: str = 'https://postbox.cloud.yandex.net'`, `from_address: str = 'noreply@mail.sportzal.ru'`, `from_domain: str = ''`, `webhook_secret: SecretStr = SecretStr('')`, `sandbox_mode: bool = False`.
  - `@model_validator(mode='after')` named `_validate_production_required` — raises `ValueError` when `provider != 'sandbox' AND sandbox_mode is False` and any of `from_domain`, `webhook_secret.get_secret_value()`, `aws_access_key_id`, `aws_secret_access_key` is empty/None.
- **`Settings.email`** field mounted as `email: EmailProviderSettings = EmailProviderSettings()` next to the Telegram block.
- Imports extended: added `Self` to `typing` import; added `BaseModel` to existing `pydantic` import (kept the existing `SecretStr` and `model_validator` imports — already in the file).

## Final Shape of the Validator (matches D-42-28 verbatim?)

Yes — copied verbatim from the plan body (which itself is verbatim from D-42-28). No deviations to the field types, defaults, or validator branch order. Error messages identical.

## BaseModel vs BaseSettings choice

Per plan: used `BaseModel` (NOT `BaseSettings`) for the nested block. This matches D-42-28 and keeps the outer `Settings(BaseSettings)` as the single env-loading boundary. No deviation here.

## Env-var convention discovered

**Discovery:** The existing `Settings` class does NOT configure `env_nested_delimiter`. Today, env vars target flat field names directly (e.g., `TELEGRAM_BOT_TOKEN`, `GYM_HOURS_START`). To populate nested email fields from env (e.g., `EMAIL__PROVIDER=yandex_postbox` or `EMAIL__WEBHOOK_SECRET=...`), `Settings.model_config` would need `env_nested_delimiter='__'` added.

I deliberately did **not** add `env_nested_delimiter` in this plan, per the plan's instruction "do NOT introduce a different convention." The current behaviour is:

- Constructing `Settings()` (e.g., in `get_settings()`) yields `settings.email = EmailProviderSettings()` with all defaults — sandbox-safe, so dev boot works on a fresh clone.
- Production deployments that need to override email fields will require either (a) a later plan to introduce `env_nested_delimiter='__'` on `Settings.model_config`, or (b) constructing `Settings(email=EmailProviderSettings(...))` explicitly somewhere in the bootstrap (less ergonomic).

This is a future-plan concern (likely Wave 2 plan 42-07 factory or a small follow-up patch) and is intentionally out of scope for 42-02 — landing `env_nested_delimiter` would change env-var loading for any subsequent nested block too, deserving its own focused plan.

## Verification

**Inline verify script (from `<verify>` block) passed:**

```
sandbox default constructs fine: provider='sandbox', sandbox_mode=False
non-sandbox without creds raises ValueError with 'from_domain' in message
non-sandbox with full creds (aws keys + from_domain + webhook_secret) constructs cleanly
=> OK
```

**Tooling:**

- `uv run ruff check app/core/config.py` — All checks passed!
- `uv run mypy --strict app/core/config.py` — Success: no issues found in 1 source file
- `uv run pytest tests/unit/test_config.py -x` — 4 passed
- `uv run pytest tests/ -x --ignore=tests/integration -k config` — 9 passed (4 test_config + 5 test_schemas)

**Acceptance-criteria greps (all match expected counts):**

| Pattern | Expected | Actual |
|---|---|---|
| `class EmailProviderSettings` | 1 | 1 |
| `provider: Literal["yandex_postbox", "sandbox"]` | 1 | 1 |
| `_validate_production_required` | 1 | 1 |
| `email: EmailProviderSettings` | ≥1 | 1 |

## Deviations from Plan

None. Plan was executed verbatim. The `env_nested_delimiter` discussion in this Summary is a **discovered note** for downstream-plan authors, NOT a deviation — the plan body explicitly told us not to introduce one in this scope.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None.

## Commits

| Hash | Type | Message |
|---|---|---|
| 9876943 | feat | feat(42-02): add EmailProviderSettings block to Settings (D-42-28) |

## Self-Check: PASSED

- File `apps/backend/app/core/config.py` exists and contains `class EmailProviderSettings`, `_validate_production_required`, and `email: EmailProviderSettings` — verified by acceptance greps above.
- Commit `9876943` exists on `worktree-agent-a18c5009dfce52850` — confirmed via `git rev-parse --short HEAD` immediately after `git commit`.
- No file deletions in the commit (`git diff --diff-filter=D HEAD~1 HEAD` empty).
