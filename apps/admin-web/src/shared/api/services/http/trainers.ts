/**
 * HTTP trainer service implementation.
 *
 * TODO Phase 35: Wire up real HTTP transport when backend API is ready.
 * For now this module re-exports the mock service as a temporary shim so
 * the swap seam type resolves correctly during Phase 31 mock-only mode.
 */
export { trainers } from '../mock/trainers'
