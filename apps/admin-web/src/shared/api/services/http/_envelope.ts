/**
 * Phase 10 service-boundary envelope unwrap.
 *
 * Phase 4 D-07: backend wraps every 2xx response as `{ data: <payload> }`.
 * Phase 4 D-08: errors stay top-level (no envelope).
 *
 * The Phase 9 fetcher (packages/api-client/src/fetcher.ts) intentionally does
 * NOT unwrap — it returns `JSON.parse(text)` verbatim so the transport stays
 * framework-agnostic. Phase 10 adapts here: ResponseEnvelope[T] -> T.
 *
 * 204 No Content: `request()` returns `undefined` — pass through as-is.
 */
export function unwrap<T>(raw: unknown): T {
  if (raw && typeof raw === 'object' && 'data' in raw) {
    return (raw as { data: T }).data
  }
  // 204 No Content (undefined) or already-unwrapped (test mocks): pass through.
  return raw as T
}
