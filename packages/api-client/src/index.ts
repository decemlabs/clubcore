/**
 * @sportzal/api-client — typed transport for the Sportzal backend.
 *
 * Public surface (Phase 9 D-10):
 *  - `request<P, M>(method, path, init?)` — single typed entry point.
 *  - `ApiError` — error class mirroring the backend AppError envelope.
 *  - `paths`, `components` — generated openapi-typescript types.
 *
 * Convenience wrappers (get / post / patch / del) are intentionally NOT
 * provided. See Phase 9 D-10 (deferred to backlog).
 */
export { request } from './fetcher'
export { ApiError } from './errors'
export type { paths, components } from './schema'
