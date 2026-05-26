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
