/**
 * HTTP service implementations (real-API, Phase 7+).
 *
 * Populated later once the backend is defined. Phase 1 ships an empty container
 * so the swap seam type-checks with `VITE_API_MODE=http` as a legal option.
 *
 * Rules:
 * - Must implement the same `Contracts` as `mock/`.
 * - No UI imports, no React — pure transport layer.
 * - Error mapping (HTTP → DomainError) lives here, not in UI.
 */
export const services = {} as const
