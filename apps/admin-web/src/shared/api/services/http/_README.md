# HTTP Services

Real-API implementation. Populated once the backend shape is defined (Phase 7+).
Must satisfy the same `Contracts` as `mock/` so the swap is invisible to UI.

**Rules**

- Pure transport; no React, no UI.
- Map HTTP errors to `DomainError { code, message, fields? }` at this boundary.
- Auth headers, retry/backoff, and cancellation belong here, not in hooks.
