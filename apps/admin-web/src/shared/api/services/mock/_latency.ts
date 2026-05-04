/**
 * Simulated network latency for mock services.
 * Range 120-300ms per CLAUDE.md "Mock realism".
 */
export function delay(): Promise<void> {
  const ms = 120 + Math.floor(Math.random() * 181) // 120..300
  return new Promise((resolve) => setTimeout(resolve, ms))
}
