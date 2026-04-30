/**
 * Swap seam.
 *
 * The one place in the codebase that branches on `VITE_API_MODE`. UI, features,
 * hooks, and routes import from here and never from `./mock` or `./http`.
 *
 * Eager imports (not dynamic) so the chosen bundle is fully tree-shaken at build
 * time when `VITE_API_MODE` is fixed. Dev builds include both; prod bundles only
 * the branch selected by env.
 *
 * Real-API migration = implement `./http/*`, flip default `VITE_API_MODE=http`.
 * UI/hooks/schemas/routes do not change.
 */
import { API_MODE } from '../config/env'
import { services as mockServices } from './mock'
import { services as httpServices } from './http'

export const services = API_MODE === 'http' ? httpServices : mockServices

export { API_MODE }
