/**
 * Single chokepoint for `import.meta.env.VITE_API_MODE`.
 * ESLint blocks reads of this env var anywhere outside `src/shared/api/**`.
 */
const RAW = import.meta.env.VITE_API_MODE
const ALLOWED = ['mock', 'http'] as const
type ApiMode = (typeof ALLOWED)[number]

function pick(): ApiMode {
  if (RAW === 'mock' || RAW === 'http') return RAW
  if (import.meta.env.DEV && RAW !== undefined) {

    console.warn(
      `[env] Unexpected VITE_API_MODE=${String(RAW)}; falling back to "mock". Allowed: ${ALLOWED.join(', ')}`,
    )
  }
  return 'mock'
}

export const API_MODE: ApiMode = pick()
