# Service Contracts

Per-domain service interfaces live here. Phase 1 ships an empty stub; each
subsequent phase adds the contract for its domain (clients, schedule, staff, ...).

**Rules**

- Transport-agnostic: never import from `mock/` or `http/`.
- Pagination: every list returns `{ items, total, page, pageSize }`.
- Errors: methods throw `DomainError { code, message, fields? }`.
- Types only (no runtime) — these files must be tree-shakable.

Consumed by:

- `src/shared/api/services/mock/**` — the Faker-backed implementation.
- `src/shared/api/services/http/**` — the real-API implementation (Phase 7+).
- `src/shared/api/services/index.ts` — the swap seam that picks impl by `VITE_API_MODE`.
