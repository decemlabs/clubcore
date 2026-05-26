import '@/app/index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { queryClient } from './queryClient'
import { router } from './router'
import { ThemeProvider } from './providers/ThemeProvider'
import { useSessionStore } from '@/shared/session/store'
import { useUiPrefsStore } from '@/shared/theme/uiPrefsStore'
import { services, API_MODE } from '@/shared/api/services'
import { authKeys } from '@/features/auth/api/keys'
import { Splash } from '@/shared/ui/splash'

// TODO Phase 67 / RUN-07: drop v1.10 sportzal:* localStorage migration shim.
// Phase 62 D-62-06 — one-shot pre-rehydrate migrator. Copies legacy
// sportzal:*:v1 payloads to clubcore:*:v2 and deletes the legacy keys so
// Zustand `persist.rehydrate()` below reads from the new namespace cleanly.
// Runs once per browser: subsequent boots find the new keys already present
// and short-circuit. Greenfield users skip every pair (no spurious writes).
const STORE_MIGRATIONS: ReadonlyArray<readonly [string, string]> = [
  ['sportzal:session:v1', 'clubcore:session:v2'],
  ['sportzal:ui:v1', 'clubcore:ui:v2'],
  ['sportzal:mock:v1', 'clubcore:mock:v2'],
] as const

for (const [oldKey, newKey] of STORE_MIGRATIONS) {
  try {
    if (window.localStorage.getItem(newKey) !== null) continue
    const legacy = window.localStorage.getItem(oldKey)
    if (legacy === null) continue
    window.localStorage.setItem(newKey, legacy)
    window.localStorage.removeItem(oldKey)
  } catch {
    /* noop — storage quota/disabled; let store re-seed from defaults */
  }
}

await Promise.all([
  useSessionStore.persist.rehydrate(),
  useUiPrefsStore.persist.rehydrate(),
])

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root element not found')
const root = createRoot(rootEl)

if (API_MODE === 'http') {
  root.render(<Splash />)
  try {
    await queryClient.ensureQueryData({
      queryKey: authKeys.me,
      queryFn: () => services.auth.me(),
      retry: false,
    })
  } catch {
    // 401 (or any failure) — router /login route renders next
  }
}

root.render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  </StrictMode>,
)
