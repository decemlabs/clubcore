# Mock Services

Faker-backed in-memory implementation. Per-domain service modules land here
(e.g. `clients.ts`, `schedule.ts`) and are aggregated in `index.ts`.

**Conventions**

- Central DB seeded once with `faker.seed(42)`, persisted under `sportzal:mock:v1`.
- Each service method awaits `simulateLatency()` and may throw a fake `DomainError`.
- Role checks: call `can(role, action, resource)` from `@/shared/session/can`; if
  false, throw `{ code: 'forbidden', message: ... }` (mock 403-analog).
- Never exported directly to UI — the swap seam in
  `src/shared/api/services/index.ts` owns the choice.
