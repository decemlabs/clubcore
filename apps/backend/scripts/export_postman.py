"""Export Postman v2.1 collection from apps/backend/openapi.json (HANDOFF-04 / Phase 46 D-46-08).

Reads the already-regenerated ``openapi.json`` (do NOT re-invoke
``create_app()`` — use the byte-stable artifact from
``scripts/export_openapi.py``).

Filters out any operation whose primary tag is ``'_internal'`` (e.g.
``/api/v1/_internal/email/webhook``). The external design team consumes
this collection; internal endpoints stay in the OpenAPI spec for
completeness but never leak to consumers (per D-46-08).

Run from ``apps/backend/``:

    uv run python -m scripts.export_postman

Writes ``.planning/handoff/v1.6-postman.json`` (resolved relative to this
file, so the script is cwd-independent). Output is byte-stable:
``indent=2, sort_keys=True, ensure_ascii=False, trailing newline`` —
identical bytes on macOS and Linux. Re-running produces zero git diff.

Stdlib only: ``json``, ``pathlib``, ``re``, ``sys``, ``uuid``. No
third-party deps; the script does NOT touch DB, Redis, or FastAPI.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import uuid
from typing import Any

# --- Path resolution (cwd-independent) ---------------------------------------
# __file__ = apps/backend/scripts/export_postman.py
# parents[1] = apps/backend/
# parents[3] = repo-root
HERE = pathlib.Path(__file__).resolve()
SOURCE = HERE.parents[1] / "openapi.json"
TARGET = HERE.parents[3] / ".planning" / "handoff" / "v1.6-postman.json"

# --- Constants ---------------------------------------------------------------
INTERNAL_TAG = "_internal"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
COLLECTION_NAME = "Sportzal v1.6 — Email channel + Multi-user admin"
COLLECTION_SCHEMA = (
    "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
)
NAMESPACE = uuid.NAMESPACE_URL
_PATH_PARAM_RE = re.compile(r"\{([^{}]+)\}")


def _path_segments(path: str) -> list[str]:
    """Split a URL path into segments, dropping the empty leading element."""
    return [seg for seg in path.split("/") if seg]


def _path_variables(path: str) -> list[dict[str, str]]:
    """Extract Postman ``url.variable`` entries from ``{name}`` placeholders."""
    return [{"key": name, "value": ""} for name in _PATH_PARAM_RE.findall(path)]


def _operation_is_internal(operation: dict[str, Any]) -> bool:
    """D-46-08: drop operations tagged with ``INTERNAL_TAG`` (literal
    ``'_internal'`` in openapi.json; sometimes referred to as the
    'internal' tag without the underscore prefix in older docs)."""
    tags = operation.get("tags") or []
    return INTERNAL_TAG in tags


def _build_request(method: str, path: str, operation: dict[str, Any]) -> dict[str, Any]:
    """Build a single Postman ``request`` block from an OpenAPI operation."""
    method_upper = method.upper()
    summary = operation.get("summary") or f"{method_upper} {path}"
    description_text = operation.get("description") or ""

    headers: list[dict[str, str]] = [{"key": "Accept", "value": "application/json"}]
    if method_upper != "GET":
        headers.insert(0, {"key": "Content-Type", "value": "application/json"})

    request: dict[str, Any] = {
        "name": summary,
        "description": {"content": description_text, "type": "text/plain"},
        "url": {
            "raw": "{{baseUrl}}" + path,
            "path": _path_segments(path),
            "host": ["{{baseUrl}}"],
            "query": [],
            "variable": _path_variables(path),
        },
        "header": headers,
        "method": method_upper,
    }

    if operation.get("requestBody") is not None:
        request["body"] = {
            "mode": "raw",
            "raw": "{}",
            "options": {"raw": {"language": "json"}},
        }

    return request


def _build_item(method: str, path: str, operation: dict[str, Any]) -> dict[str, Any]:
    """Build a single Postman item (request leaf) from an OpenAPI operation."""
    item_id = str(uuid.uuid5(NAMESPACE, f"{method.lower()}:{path}"))
    request = _build_request(method, path, operation)
    return {"id": item_id, "name": request["name"], "request": request}


def _ensure_folder(parent_items: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """Find or create a child folder by name; return its ``item`` list."""
    for entry in parent_items:
        if entry.get("name") == name and "item" in entry:
            return entry["item"]  # type: ignore[no-any-return]
    folder: dict[str, Any] = {"name": name, "description": "", "item": []}
    parent_items.append(folder)
    return folder["item"]


def _insert_item(
    root_items: list[dict[str, Any]],
    path: str,
    item: dict[str, Any],
) -> None:
    """Insert ``item`` into a hierarchical folder tree keyed by path segments."""
    segments = _path_segments(path)
    # Folder hierarchy = all segments except the final leaf (or all if root-level)
    folders = segments[:-1] if len(segments) > 1 else segments
    bucket = root_items
    for seg in folders:
        bucket = _ensure_folder(bucket, seg)
    bucket.append(item)


def _build_collection(spec: dict[str, Any]) -> dict[str, Any]:
    """Walk ``spec['paths']``, drop internal-tagged ops, emit Postman v2.1 tree."""
    paths_obj = spec.get("paths") or {}
    root_items: list[dict[str, Any]] = []

    # Sort paths for deterministic ordering (sort_keys=True only sorts dict keys;
    # the item list order also matters for byte-stability).
    for path in sorted(paths_obj.keys()):
        path_obj = paths_obj[path]
        if not isinstance(path_obj, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_obj.get(method)
            if not isinstance(operation, dict):
                continue
            if _operation_is_internal(operation):
                continue
            item = _build_item(method, path, operation)
            _insert_item(root_items, path, item)

    return {
        "info": {
            "_postman_id": str(uuid.uuid5(NAMESPACE, "sportzal-v1.6-handoff")),
            "name": COLLECTION_NAME,
            "schema": COLLECTION_SCHEMA,
        },
        "item": root_items,
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
    }


def main() -> int:
    if not SOURCE.exists():
        print(
            f"Source openapi.json missing at {SOURCE} — run "
            "`uv run python -m scripts.export_openapi` first.",
            file=sys.stderr,
        )
        return 1

    spec = json.loads(SOURCE.read_text(encoding="utf-8"))
    if "paths" not in spec:
        print(
            "openapi.json has no 'paths' key — FastAPI surface broken.",
            file=sys.stderr,
        )
        return 1

    collection = _build_collection(spec)

    # Byte-stable across macOS↔Linux (mirrors export_openapi.py D-06).
    payload = json.dumps(collection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(payload, encoding="utf-8")
    print(f"Wrote {TARGET} ({len(payload)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
