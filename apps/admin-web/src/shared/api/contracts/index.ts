/**
 * Service contracts (Phase 1 stub — populated per-domain in later phases).
 *
 * Each domain feature will export a `<Domain>Service` interface here consumed
 * by both mock and http implementations. The swap seam at
 * `src/shared/api/services/index.ts` picks the impl via `VITE_API_MODE`.
 *
 * Contracts must be transport-agnostic: no HTTP types, no Faker types.
 * Use branded IDs, ISO strings, money as minor-unit integers.
 */
export type Contracts = Record<string, never>
