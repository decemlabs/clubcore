/**
 * HTTP service implementations container.
 *
 * Rules:
 * - Must implement the same Contracts as mock/.
 * - No UI imports, no React — pure transport layer.
 * - Error mapping (HTTP -> ApiError) lives in @sportzal/api-client.
 * - Response envelope unwrap (D-07 {data:T} -> T) lives in _envelope.ts.
 */
import { auth } from './auth'
import { clients } from './clients'

export const services = { auth, clients } as const
