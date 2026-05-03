/**
 * Client-side mirror of the backend AppError envelope (Phase 9 D-12).
 *
 * Server emits {code, message, fields?} on every non-2xx response (see
 * apps/backend/app/core/exceptions.py:_app_error_handler). Fetcher parses
 * that body and throws this class.
 *
 * Single class — no subclass tree. Consumers discriminate on `error.code`
 * (e.g. `if (err.code === 'invalid_credentials') ...`).
 *
 * Synthetic codes (NOT emitted by server, set client-side by fetcher):
 *  - `session_expired` — single-flight /auth/refresh failed; consumer redirects to /login (Phase 10).
 *  - `network_error`   — fetch() rejected (offline, DNS, CORS, etc.).
 *  - `unknown_error`   — non-2xx body could not be parsed as JSON.
 */
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'ApiError'
  }
}
