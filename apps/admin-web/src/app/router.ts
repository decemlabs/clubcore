import { createRouter } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'
import { routeTree } from '@/routeTree.gen'
import { queryClient } from './queryClient'
import { useSessionStore } from '@/shared/session/store'
import type { SessionState } from '@/shared/session/types'

export interface RouterContext {
  queryClient: QueryClient
  getSession: () => SessionState
}

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  context: {
    queryClient,
    getSession: () => useSessionStore.getState(),
  } satisfies RouterContext,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
