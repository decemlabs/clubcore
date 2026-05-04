import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import { redirectOnSessionExpired } from '@/features/auth/api/redirect-on-session-expired'

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: redirectOnSessionExpired }),
  mutationCache: new MutationCache({ onError: redirectOnSessionExpired }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
})
