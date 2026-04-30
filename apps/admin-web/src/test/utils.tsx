/* eslint-disable react-refresh/only-export-components */
import type { ReactElement, ReactNode } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useSessionStore } from '@/shared/session/store'
import type { Role } from '@/shared/session/types'

interface RenderOptions {
  role?: Role
}

export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

interface ProvidersProps {
  children: ReactNode
  client: QueryClient
}

function Providers({ children, client }: ProvidersProps) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

export function renderWithProviders(ui: ReactElement, opts: RenderOptions = {}) {
  if (opts.role) {
    useSessionStore.setState({ role: opts.role })
  }
  const client = makeTestQueryClient()
  return {
    client,
    ...render(<Providers client={client}>{ui}</Providers>),
  }
}
