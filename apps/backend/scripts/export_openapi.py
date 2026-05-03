"""Export the FastAPI OpenAPI spec (API-01 / Phase 9 D-04..D-06).

Lifespan-safe: calls `create_app().openapi()` directly. FastAPI's
`combined_lifespan` (db_lifespan + redis_lifespan) is NEVER entered, so
Postgres and Redis are not touched. The script can run in any environment
that has the Python deps installed.

Run from `apps/backend/`:

    uv run python -m scripts.export_openapi

Writes `apps/backend/openapi.json` (resolved relative to this file, so the
script is cwd-independent). Output is byte-stable: `indent=2, sort_keys=True,
ensure_ascii=False, trailing newline` — identical bytes on macOS and Linux.

Phase 9 D-04: `os.environ.setdefault('ENVIRONMENT', 'dev')` MUST appear
before importing `app.main`; otherwise `create_app()` may raise the
Phase 4 D-25 prod-cookie-secure assertion in a clean shell.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

# D-04: must precede any `app.*` import. Without this, a clean shell with
# ENVIRONMENT=prod (or unset settings cache) could trigger the Phase 4 D-25
# assertion. `setdefault` does not override an explicit ENVIRONMENT=dev/staging.
os.environ.setdefault("ENVIRONMENT", "dev")

# `Settings` (apps/backend/app/core/config.py) declares several required fields
# without defaults. `.openapi()` does not touch DB / Redis / Telegram, but
# instantiating `Settings` does — so we backfill harmless placeholders for any
# field that is missing from the environment / .env. `setdefault` never
# overrides values that an operator (or CI) explicitly provided.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://export:export@localhost:5432/export")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "openapi-export-placeholder")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "openapi-export-placeholder")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "openapi_export_bot")

# Import order matters: env-prep above MUST come before `from app.main`,
# which is why this import sits below module-level statements (D-04).
from app.main import create_app


def main() -> int:
    # D-05: `.openapi()` is a sync property; lifespan never runs.
    spec = create_app().openapi()
    if "paths" not in spec:
        print(
            "openapi() returned no 'paths' — FastAPI surface broken.",
            file=sys.stderr,
        )
        return 1

    # D-06: byte-stable across macOS↔Linux.
    payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    # Cwd-independent: resolve relative to this file's location.
    # __file__ = apps/backend/scripts/export_openapi.py
    # parents[1] = apps/backend/
    target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
    target.write_text(payload, encoding="utf-8")
    print(f"Wrote {target} ({len(payload)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
